"""Optional pre retries after fixed C, isolated from the collector's clock.

Only the child calls the existing MIS transport. The parent terminates/kills it,
retains its raw journal and never changes convergence or mandatory-phase rules.
"""
import json
import multiprocessing
import os
import time
import uuid
from datetime import timedelta
from pathlib import Path

MAX_SECONDS = 12
RESERVE_SECONDS = 1
MAX_JOURNAL_BYTES = 16_000_000


def _worker(plan_path, directory):
    import probe
    plan=json.loads(Path(plan_path).read_text());directory=Path(directory)
    snapshots=[{'records':[json.loads(line) for line in Path(p).read_text().splitlines() if line.strip()]} for p in plan['references']]
    universe=json.loads(Path(plan['universe']).read_text())
    probes=[json.loads(line) for line in Path(plan['probes']).read_text().splitlines() if line.strip()]
    original=probe.snapshot
    def journalled(*args,**kwargs):return original(*args,**kwargs,retry_journal='retry_journal.jsonl')
    probe.snapshot=journalled
    # Unchanged freshness, affected-stock selection, 50-symbol batches,
    # concurrency=5, HTTP retry policy and 403/429 stop policy.
    probe.targeted_retries('pre',plan['date'],snapshots,universe,directory,probes,
                          stop_at=plan['deadline'].split('T')[1].split('+')[0])


def capture(date, snapshots, output, *, clock=None, ctx=None, child_target=None,
            max_seconds=MAX_SECONDS):
    import probe
    clock=clock or probe.now_tpe;output=Path(output)
    started=clock();tick=time.monotonic()
    end=min(probe.target(date,probe.convergence.DEADLINES['pre']),started+timedelta(seconds=max_seconds))
    seconds=max(0,(end-started).total_seconds())
    event={'scope':'OPTIONAL_PRE_RETRY_AFTER_C','started_at':started.isoformat(),
           'deadline':end.isoformat(),'max_seconds':max_seconds,'status':'SKIPPED_NO_BUDGET',
           'forced_termination':False,'records_preserved':0}
    def log():
        event['finished_at']=clock().isoformat();event['wall_seconds']=round(time.monotonic()-tick,6)
        with (output/'pre_retry_budget.jsonl').open('a') as file:file.write(json.dumps(event)+'\n')
    if started.date().isoformat()!=date or started<probe.target(date,'13:29:00') or seconds<=RESERVE_SECONDS:
        log();return []
    # Stage only new optional evidence. Read original snapshots by path, never
    # copy/replace the original raw files or let the child write official state.
    directory=output/('pre-retry-worker-'+uuid.uuid4().hex);directory.mkdir()
    event['evidence_directory']=directory.name
    child_end=end-timedelta(seconds=RESERVE_SECONDS)
    plan={'date':date,'deadline':child_end.isoformat(),
          'references':[str((output/(s['metrics']['phase']+'_raw.jsonl')).resolve()) for s in snapshots],
          'universe':str((output/'universe.json').resolve()),'probes':str((output/'probe_raw.jsonl').resolve())}
    plan_path=directory/'plan.json';plan_path.write_text(json.dumps(plan))
    ctx=ctx or multiprocessing.get_context('spawn')
    child=ctx.Process(target=child_target or _worker,args=(str(plan_path),str(directory)),daemon=True)
    try:
        child.start()
        child.join(max(0,seconds-RESERVE_SECONDS-(time.monotonic()-tick)))
        if child.is_alive():
            event['forced_termination']=True;child.terminate();child.join(.1)
        if child.is_alive():child.kill();child.join(.1)
        if child.is_alive():
            # Do not proceed into another market phase with a live retry worker.
            raise RuntimeError('PRE_RETRY_CHILD_DID_NOT_STOP')
        event['worker_exitcode']=child.exitcode
        event['status']='HARD_TIMEOUT' if event['forced_termination'] else 'COMPLETED' if child.exitcode==0 else 'WORKER_FAILED'
    except Exception as exc:
        event['status']='WORKER_START_FAILED';event['error_type']=type(exc).__name__
    finally:
        if child.pid and child.is_alive():child.kill();child.join(.1)
        if child.pid and child.is_alive():raise RuntimeError('PRE_RETRY_CHILD_DID_NOT_STOP')
    # Keep the worker directory even on timeout, crash or a torn final line.
    # Parent only adopts complete, bounded journal lines; no prices are invented.
    journal=directory/'retry_journal.jsonl';records=[]
    if journal.exists() and journal.stat().st_size<=MAX_JOURNAL_BYTES:
        with journal.open('rb') as file:
            for line in file:
                if time.monotonic()-tick>=seconds:break
                try:
                    if not line.endswith(b'\n'):raise ValueError('torn line')
                    row=json.loads(line)
                    if not isinstance(row,dict) or row.get('phase')!='pre_targeted_retry':raise ValueError('wrong phase')
                    required=('planned_at','requested_at','received_at','symbols','batch_no','http_status','error','missing','empty','duplicate','latency_ms','retry','expected_count')
                    if any(key not in row for key in required) or not isinstance(row['symbols'],list):raise ValueError('incomplete record')
                    if any(not isinstance(s,dict) or s.get('ex') not in ('tse','otc') or not isinstance(s.get('code'),str) for s in row['symbols']):raise ValueError('invalid symbols')
                    if row.get('response') is not None and not isinstance(row['response'],dict):
                        row['response']=None;row['error']='INVALID_TARGETED_RESPONSE_SHAPE'
                    received=probe.freshness.parsed_time(row.get('received_at'))
                    if not received or received>child_end:row['error']='RESPONSE_AFTER_CAPTURE_DEADLINE'
                    records.append(row)
                except (ValueError,TypeError):event['incomplete_or_invalid_journal']=True
    elif journal.exists():event['journal_oversize_preserved_not_adopted']=True
    if records:
        with (output/'pre_targeted_retry_raw.jsonl').open('a') as file:
            for row in records:file.write(json.dumps(row,ensure_ascii=False)+'\n')
            file.flush();os.fsync(file.fileno())
    event['records_preserved']=len(records);log()
    if not records:return []
    return [{'records':records,'metrics':{'phase':'pre_targeted_retry','status':event['status'],
             'retry_round':1,'stock_universe_count':len({(s['ex'],s['code']) for r in records for s in r['symbols']}),
             'hard_budget_seconds':seconds,'forced_termination':event['forced_termination']}}]
