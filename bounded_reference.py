"""Bounded B/C transport only; price/convergence/publication rules are unchanged.

50 symbols/request, one first-pass attempt, at most eight live HTTP workers.
Completed responses are journalled immediately. Socket timeout is advisory;
process lifetime and the phase deadline are enforced by the parent.
"""
import json
import math
import multiprocessing
import os
import statistics
import time
import uuid
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path

CONCURRENCY = 8
MAX_REQUEST_SECONDS = 6.0
MIN_REQUEST_SECONDS = 1.0
SHUTDOWN_RESERVE = 1.0
C_RETRY_RESERVE = 5.0
POLL_SECONDS = .01
MAX_RESPONSE_BYTES = 4_000_000


def request_budget(remaining, batches):
    """Fair first-pass budget: a stalled worker cannot consume later waves."""
    return min(MAX_REQUEST_SECONDS, max(0., (remaining-SHUTDOWN_RESERVE) /
                                           max(1, math.ceil(batches/CONCURRENCY))))


def _atomic(path, value):
    temp = Path(str(path)+'.tmp')
    with temp.open('w', encoding='utf-8') as file:
        json.dump(value, file, ensure_ascii=False); file.flush(); os.fsync(file.fileno())
    temp.replace(path)


def _worker(group, deadline, timeout, directory):
    import probe
    directory = Path(directory)
    _atomic(directory/'started.json', {'requested_at':probe.iso()})
    result = probe.fetch_mis(group, retry=0, timeout=timeout,
                             deadline=probe.freshness.parsed_time(deadline))
    _atomic(directory/'result.json', asdict(result))


def _stop(child):
    if child.is_alive(): child.terminate(); child.join(.05)
    if child.is_alive(): child.kill(); child.join(.05)
    if child.is_alive(): raise RuntimeError('REFERENCE_HTTP_WORKER_DID_NOT_STOP')
    child.join(0)


def capture(phase, planned, universe, output, deadline, *, ctx=None, child_target=None,
            clock=None, monotonic=None, sleep=None):
    import probe
    clock = clock or probe.now_tpe; tick = monotonic or time.monotonic
    sleep = sleep or time.sleep; ctx = ctx or multiprocessing.get_context('spawn')
    output = Path(output); started = clock(); start_tick = tick()
    # Finish C early enough for the existing optional targeted retry. Neither
    # deadline extends the original allowed observation window.
    phase_end = deadline-timedelta(seconds=C_RETRY_RESERVE if phase=='pre_reference_C' else 0)
    seconds = max(0., (phase_end-started).total_seconds())
    dispatch_end = start_tick+max(0.,seconds-SHUTDOWN_RESERVE)
    directory = output/('reference-worker-'+phase+'-'+uuid.uuid4().hex); directory.mkdir()
    groups = [universe[i:i+probe.BATCH_SIZE] for i in range(0,len(universe),probe.BATCH_SIZE)]
    records = []; active = {}; next_batch = 0; blocked = False; no_budget = False
    raw = output/(phase+'_raw.jsonl'); raw.touch(exist_ok=False)
    queued_at = probe.iso(started)

    def retain(index, group, result, meta):
        nonlocal blocked
        # Late/invalid responses remain preserved in the worker directory but
        # cannot supply a comparison price.
        received = probe.freshness.parsed_time(result.received_at)
        if result.error != 'CAPTURE_DEADLINE_NO_REQUEST' and (not received or received>phase_end):
            result.error = 'RESPONSE_AFTER_CAPTURE_DEADLINE'+(':'+result.error if result.error else '')
        row = {'phase':phase,'planned_at':probe.iso(planned),'batch_no':index+1,
               'expected_count':len(group),'symbols':group,**asdict(result),**meta}
        row.update(probe.analyze(group,result)); records.append(row)
        with raw.open('a',encoding='utf-8') as file:
            file.write(json.dumps(row,ensure_ascii=False)+'\n'); file.flush(); os.fsync(file.fileno())
        if result.http_status in (403,429): blocked = True

    def finish(index, job, forced=False):
        child, group, folder, launched, limit = job
        # A complete response already on disk is retained even when the process
        # hangs during teardown. Never read partial atomic files.
        _stop(child)
        result = None
        try:
            path=folder/'result.json'
            if path.stat().st_size<=MAX_RESPONSE_BYTES:
                result=probe.FetchResult(**json.loads(path.read_text()))
        except (OSError,ValueError,TypeError): pass
        stamp=probe.iso(clock()); attempted=None
        try: attempted=json.loads((folder/'started.json').read_text())['requested_at']
        except (OSError,ValueError,KeyError,TypeError): pass
        if result is None:
            error = ('REQUEST_HARD_TIMEOUT' if forced else 'REFERENCE_WORKER_FAILED') if attempted else 'CAPTURE_DEADLINE_NO_REQUEST'
            result=probe.FetchResult(attempted or stamp,stamp,round((tick()-launched)*1000),None,0,error,None,None)
        retain(index,group,result,{'queued_at':queued_at,'worker_launched_at':job_times[index],
              'queue_wait_ms':round((launched-start_tick)*1000),
              'request_hard_budget_seconds':round(limit,6),'forced_termination':forced,
              'worker_exitcode':child.exitcode,'evidence_directory':str(folder.relative_to(output))})

    job_times = {}
    try:
        while active or next_batch<len(groups):
            # Drain completions before starting more work, so a reported rate
            # limit stops dispatch immediately (already in-flight work is bounded).
            for index, job in list(active.items()):
                child, _, folder, launched, limit = job
                if (folder/'result.json').exists() or not child.is_alive() or tick()>=min(dispatch_end,launched+limit):
                    finish(index,job,forced=child.is_alive() and not (folder/'result.json').exists())
                    del active[index]
            if tick()>=dispatch_end or blocked or no_budget:
                for index,job in list(active.items()):
                    finish(index,job,forced=job[0].is_alive()); del active[index]
                break
            while next_batch<len(groups) and len(active)<CONCURRENCY and tick()<dispatch_end and not blocked:
                index=next_batch
                limit=request_budget(start_tick+seconds-tick(),len(groups)-index+len(active))
                if limit<MIN_REQUEST_SECONDS:
                    no_budget=True; break
                next_batch+=1; group=groups[index]
                folder=directory/str(index+1); folder.mkdir()
                launched=tick(); job_times[index]=probe.iso(clock())
                child=ctx.Process(target=child_target or _worker,
                    args=(group,probe.iso(phase_end),limit,str(folder)),daemon=True)
                try:
                    child.start(); active[index]=(child,group,folder,launched,limit)
                except Exception:
                    if child.pid: _stop(child)
                    stamp=probe.iso(clock())
                    retain(index,group,probe.FetchResult(stamp,stamp,0,None,0,'CAPTURE_DEADLINE_NO_REQUEST',None,None),
                           {'queued_at':queued_at,'worker_start_failed':True})
            if active: sleep(POLL_SECONDS)
    finally:
        for job in active.values(): _stop(job[0])
    # Unsent work remains a mandatory execution failure. This is deliberately
    # the existing fatal code, never disguised as a completed HTTP attempt.
    for index in range(next_batch,len(groups)):
        stamp=probe.iso(clock())
        retain(index,groups[index],probe.FetchResult(stamp,stamp,0,None,0,'CAPTURE_DEADLINE_NO_REQUEST',None,None),
               {'queued_at':queued_at,'not_sent_reason':'HTTP_403_429' if blocked else 'PHASE_DEADLINE'})
    records.sort(key=lambda row:row['batch_no'])
    successful=set()
    for row in records:
        successful.update({s['ex']+':'+s['code'] for s in row['symbols']}-set(row['missing'])-set(row['empty']))
    latencies=sorted(r['latency_ms'] for r in records)
    metrics={'phase':phase,'stock_universe_count':len(universe),'batch_size':probe.BATCH_SIZE,
             'batch_count':len(groups),'concurrency':CONCURRENCY,'retries':0,
             'first_request_started_at':min((r['requested_at'] for r in records),default=None),
             'last_response_received_at':max((r['received_at'] for r in records),default=None),
             'wall_time_seconds':round(tick()-start_tick,3),'success_count':len(successful),
             'missing_count':len(universe)-len(successful),'symbol_set_equal':len(successful)==len(universe),
             'missing_codes':sorted({s['ex']+':'+s['code'] for s in universe}-successful),
             'http_errors':sum(r['http_status'] is not None and r['http_status']!=200 for r in records),
             'timeouts':sum('TIMEOUT' in (r['error'] or '').upper() for r in records),
             'not_requested_batches':sum(r['error']=='CAPTURE_DEADLINE_NO_REQUEST' for r in records),
             'forced_terminations':sum(r.get('forced_termination',False) for r in records),
             'failure_reasons':{reason:sum(r['error']==reason for r in records) for reason in sorted({r['error'] for r in records if r['error']})},
             'empty_count':sum(len(r['empty']) for r in records),
             'duplicate_count':sum(len(r['duplicate']) for r in records),
             'insufficient_batches':[r['batch_no'] for r in records if r['returned_count']<r['expected_count']],
             'phase_deadline':probe.iso(phase_end),'rate_limit_circuit_open':blocked,
             'fastest_batch_ms':min(latencies,default=None),'slowest_batch_ms':max(latencies,default=None),
             'average_batch_ms':round(statistics.mean(latencies),1) if latencies else None,
             'median_batch_ms':round(statistics.median(latencies),1) if latencies else None,
             'p95_batch_ms':latencies[max(0,math.ceil(len(latencies)*.95)-1)] if latencies else None}
    return {'records':records,'metrics':metrics}
