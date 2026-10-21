"""SYNTHETIC transport/process/clock cases; never requests live MIS."""
import json
import multiprocessing
import signal
import tempfile
import threading
import time
import unittest
import copy
import os
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import bounded_pre_retry as bounded
import probe
from test_convergence import SYMBOL
from test_convergence import reference, saved_probe_fixture

DAY='2026-10-21'


def synthetic_row(plan,late=False):
    stamp=probe.freshness.parsed_time(plan['deadline'])+timedelta(seconds=1 if late else -.01)
    at=stamp.isoformat()
    return {'phase':'pre_targeted_retry','planned_at':at,'requested_at':at,'received_at':at,
            'symbols':[SYMBOL],'expected_count':1,'batch_no':1,'http_status':200,
            'response':{'rtcode':'0000','msgArray':[]},'raw_body':'SYNTHETIC_ONLY',
            'error':None,'missing':[],'empty':[],'duplicate':[],'latency_ms':0,'retry':0}


def synthetic_hang(plan,directory):
    signal.signal(signal.SIGTERM,signal.SIG_IGN)
    (Path(directory)/'started').write_text('SYNTHETIC_ONLY')
    time.sleep(120)


def synthetic_completed(plan,directory):
    p=json.loads(Path(plan).read_text())
    (Path(directory)/'retry_journal.jsonl').write_text(json.dumps(synthetic_row(p))+'\n')


def synthetic_late(plan,directory):
    p=json.loads(Path(plan).read_text())
    (Path(directory)/'retry_journal.jsonl').write_text(json.dumps(synthetic_row(p,True))+'\n')


def synthetic_corrupt(plan,directory):
    (Path(directory)/'retry_journal.jsonl').write_text('[]\n{"phase":"pre_targeted_retry"}\n')


def synthetic_bad_response(plan,directory):
    p=json.loads(Path(plan).read_text());row=synthetic_row(p);row['response']=['SYNTHETIC_INVALID_BODY']
    (Path(directory)/'retry_journal.jsonl').write_text(json.dumps(row)+'\n')


def synthetic_partial_then_hang(plan,directory):
    synthetic_completed(plan,directory)
    with (Path(directory)/'retry_journal.jsonl').open('a')as out:out.write('{"torn":')
    synthetic_hang(plan,directory)


def synthetic_crash(plan,directory):
    raise RuntimeError('SYNTHETIC_TRANSPORT_FAILURE')


def synthetic_threadpool_hang(plan_path,directory):
    """Exercise the real snapshot/threadpool with one stalled first HTTP batch."""
    import bounded_pre_retry as b
    p=json.loads(Path(plan_path).read_text());now=probe.freshness.parsed_time(p['deadline'])-timedelta(seconds=.1)
    symbols=[{**SYMBOL,'code':str(2000+i)}for i in range(301)]
    def fetch(group,*args):
        if group[0]['code']=='2000':time.sleep(120)
        stamp=now.isoformat();body={'rtcode':'0000','msgArray':[]}
        return probe.FetchResult(stamp,stamp,0,200,0,None,json.dumps(body),body)
    with patch.object(probe,'now_tpe',return_value=now), \
         patch.object(probe.convergence,'unresolved',return_value=symbols), \
         patch.object(probe,'fetch_mis',side_effect=fetch), \
         patch('urllib.request.urlopen',side_effect=AssertionError('NO_LIVE_MIS')):
        b._worker(plan_path,directory)


def synthetic_throttle(plan_path,directory,code):
    p=json.loads(Path(plan_path).read_text());current=[probe.freshness.parsed_time(p['deadline'])-timedelta(seconds=.2)]
    calls=[]
    def fetch(*args):
        calls.append(1);(Path(directory)/'http-count.json').write_text(json.dumps(len(calls)))
        return code,b'SYNTHETIC_RATE_LIMIT'
    with patch.object(probe,'now_tpe',side_effect=lambda:current[0]), \
         patch.object(probe,'wait_until',side_effect=lambda x:current.__setitem__(0,x)), \
         patch.object(probe.convergence,'unresolved',return_value=[SYMBOL]), \
         patch.object(probe,'get_bytes',side_effect=fetch):
        bounded._worker(plan_path,directory)


def synthetic_403(plan,directory):synthetic_throttle(plan,directory,403)
def synthetic_429(plan,directory):synthetic_throttle(plan,directory,429)


class BoundedPreRetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.out=Path(self.tmp.name)
        self.snapshots=[]
        for phase in ['pre_reference_A','pre_reference_B','pre_reference_C']:
            (self.out/(phase+'_raw.jsonl')).write_text('')
            self.snapshots.append({'records':[],'metrics':{'phase':phase}})
        (self.out/'universe.json').write_text(json.dumps([SYMBOL]));(self.out/'probe_raw.jsonl').write_text('')
        self.existing={p.name:p.read_bytes()for p in self.out.iterdir()}
        self.children={c.pid for c in multiprocessing.active_children()}
    def tearDown(self):
        self.assertEqual({c.pid for c in multiprocessing.active_children()},self.children)
        for name,body in self.existing.items():self.assertEqual((self.out/name).read_bytes(),body)
    def capture(self,target,at='13:29:05',seconds=1.5):
        start=time.monotonic()
        with patch.object(bounded,'RESERVE_SECONDS',.3):
            result=bounded.capture(DAY,self.snapshots,self.out,clock=lambda:probe.target(DAY,at),
                                   max_seconds=seconds,child_target=target)
        self.assertLess(time.monotonic()-start,seconds+.6)
        return result
    def event(self):return json.loads((self.out/'pre_retry_budget.jsonl').read_text().splitlines()[-1])
    def test_no_worker_before_fixed_C(self):
        self.assertEqual(self.capture(synthetic_crash,'13:28:47'),[])
        self.assertEqual(list(self.out.glob('pre-retry-worker-*')),[])
    def test_no_worker_without_budget_after_original_pre_deadline(self):
        self.assertEqual(self.capture(synthetic_crash,'13:29:30'),[])
        self.assertEqual(self.event()['status'],'SKIPPED_NO_BUDGET')
    def test_hang_and_ignored_terminate_are_killed_with_no_background_worker(self):
        self.assertEqual(self.capture(synthetic_hang),[])
        self.assertEqual(self.event()['status'],'HARD_TIMEOUT')
        self.assertTrue(self.event()['forced_termination'])
        self.assertLess(self.event()['worker_exitcode'],0)
    def test_completed_actual_callback_record_kept_without_relabelling_as_C(self):
        result=self.capture(synthetic_completed)
        self.assertEqual(result[0]['records'][0]['phase'],'pre_targeted_retry')
        self.assertEqual(result[0]['records'][0]['raw_body'],'SYNTHETIC_ONLY')
        self.assertEqual(self.event()['status'],'COMPLETED')
    def test_partial_evidence_survives_hard_kill_and_torn_last_line(self):
        result=self.capture(synthetic_partial_then_hang)
        self.assertEqual(len(result[0]['records']),1)
        self.assertTrue(self.event()['incomplete_or_invalid_journal'])
        raw=next(self.out.glob('pre-retry-worker-*/retry_journal.jsonl')).read_bytes()
        self.assertTrue(raw.endswith(b'{"torn":'))
    def test_completed_late_response_preserved_but_rejected(self):
        result=self.capture(synthetic_late)
        self.assertEqual(result[0]['records'][0]['error'],'RESPONSE_AFTER_CAPTURE_DEADLINE')
        self.assertFalse(probe.freshness.fresh_candidate(probe.freshness.observations(result[0]['records'],DAY)[0],DAY))
    def test_worker_crash_is_optional_and_does_not_raise_capture_failure(self):
        self.assertEqual(self.capture(synthetic_crash),[])
        self.assertEqual(self.event()['status'],'WORKER_FAILED')
    def test_real_threadpool_stall_keeps_other_batches_and_is_killed(self):
        result=self.capture(synthetic_threadpool_hang)
        self.assertTrue(result and result[0]['records'])
        self.assertTrue(all(r['symbols'][0]['code']!='2000'for r in result[0]['records']))
        self.assertEqual(self.event()['status'],'HARD_TIMEOUT')
    def test_worker_staging_does_not_duplicate_archive_raw_basenames(self):
        self.capture(synthetic_completed)
        self.assertEqual(len(list(self.out.rglob('pre_targeted_retry_raw.jsonl'))),1)
        self.assertEqual(len(list(self.out.rglob('retry_journal.jsonl'))),1)
    def test_start_failure_returns_optional_diagnostic(self):
        with patch('multiprocessing.process.BaseProcess.start',side_effect=OSError('SYNTHETIC_START_FAILURE')):
            self.assertEqual(self.capture(synthetic_completed),[])
        self.assertEqual(self.event()['status'],'WORKER_START_FAILED')
    def test_absolute_pre_deadline_caps_total_budget(self):
        self.assertEqual(self.capture(synthetic_hang,'13:29:29',5),[])
        self.assertEqual(self.event()['deadline'],DAY+'T13:29:30+08:00')
    def test_http_403_and_429_keep_raw_and_stop_followup_rounds(self):
        for child,code in [(synthetic_403,403),(synthetic_429,429)]:
            result=self.capture(child);self.assertEqual(result[0]['records'][0]['http_status'],code)
            self.assertEqual(result[0]['records'][0]['raw_body'],'SYNTHETIC_RATE_LIMIT')
        self.assertTrue(all(json.loads(p.read_text())==1 for p in self.out.glob('pre-retry-worker-*/http-count.json')))
    def test_corrupt_complete_journal_records_are_not_adopted(self):
        self.assertEqual(self.capture(synthetic_corrupt),[])
        self.assertTrue(self.event()['incomplete_or_invalid_journal'])
    def test_invalid_http_body_remains_raw_and_never_becomes_price_evidence(self):
        result=self.capture(synthetic_bad_response)
        self.assertEqual(result[0]['records'][0]['error'],'INVALID_TARGETED_RESPONSE_SHAPE')
        self.assertIsNone(result[0]['records'][0]['response'])
        self.assertIn('SYNTHETIC_INVALID_BODY',next(self.out.glob('pre-retry-worker-*/retry_journal.jsonl')).read_text())
    def test_production_12_second_budget_forces_stalled_process_to_stop(self):
        started=time.monotonic()
        self.assertEqual(bounded.capture(DAY,self.snapshots,self.out,
                         clock=lambda:probe.target(DAY,'13:29:05'),child_target=synthetic_hang),[])
        elapsed=time.monotonic()-started
        self.assertLess(elapsed,bounded.MAX_SECONDS+.6)
        self.assertEqual(self.event()['status'],'HARD_TIMEOUT')
        print(json.dumps({'scope':'SYNTHETIC_STALLED_PROCESS_REAL_PRODUCTION_BUDGET',
                         'configured_seconds':bounded.MAX_SECONDS,'actual_wall_seconds':round(elapsed,6),
                         'worker_exitcode':self.event()['worker_exitcode'],'forced_termination':True}),flush=True)


class FixedReferencePriorityTests(unittest.TestCase):
    def run_schedule(self,child,day=DAY):
        symbols=[dict(ex=ex,code=code,market='TWSE'if ex=='tse'else'TPEx',name='SYNTHETIC')for ex,code in probe.FIXED_PROBE]
        current=[probe.target(day,'13:00:00')];events=[]
        real_capture=bounded.capture
        def wait(at):current[0]=max(current[0],at)
        def snapshot(phase,planned,universe,output,deadline=None):
            events.append((phase,current[0].strftime('%H:%M:%S.%f')))
            closing=phase.startswith('close_')
            row=reference(phase,planned.strftime('%H:%M:%S'),price='104'if closing else'100',
                          trade='13:30:00'if closing else'13:24:59',volume='20'if closing else'10')
            row=json.loads(json.dumps(row).replace('2026-10-02',day).replace('20261002',day.replace('-','')))
            row['synthetic_test']=True;row['symbols']=universe
            item=row['response']['msgArray'][0]
            row['response']['msgArray']=[{**copy.deepcopy(item),'ex':s['ex'],'c':s['code']}for s in universe]
            row.update(missing=[],empty=[],duplicate=[])
            (output/(phase+'_raw.jsonl')).write_text(json.dumps(row)+'\n')
            # Actual Oct21 B wall duration; C duration is explicitly synthetic.
            if phase=='pre_reference_B':current[0]=planned+timedelta(seconds=32.132)
            if phase=='pre_reference_C':current[0]=planned+timedelta(seconds=24.374)
            return {'records':[row],'metrics':{'phase':phase,'success_count':len(universe),'stock_universe_count':len(universe),'symbol_set_equal':True}}
        def optional(date,sn,out):
            events.append(('optional_retry',current[0].strftime('%H:%M:%S.%f')))
            start=current[0];tick=time.monotonic()
            with patch.object(bounded,'RESERVE_SECONDS',.2):
                result=real_capture(date,sn,out,clock=lambda:start+timedelta(seconds=time.monotonic()-tick),max_seconds=.9,child_target=child)
            current[0]=start+timedelta(seconds=time.monotonic()-tick)
            return result
        with tempfile.TemporaryDirectory()as tmp,patch.object(probe,'now_tpe',side_effect=lambda:current[0]), \
             patch.object(probe,'wait_until',side_effect=wait),patch.object(probe,'github_issue'), \
             patch.object(probe,'fetch_universe',return_value=symbols), \
             patch.object(probe.tradable,'build',return_value=(symbols,{'status':'OFFICIAL_SOURCES_DATE_CHECKED','excluded_symbol_count':0})), \
             patch.object(probe,'snapshot',side_effect=snapshot),patch.object(probe,'per_second_probe',side_effect=saved_probe_fixture), \
             patch.object(probe,'targeted_retries',side_effect=AssertionError('UNCAPPED_RETRY_ON_MAIN_THREAD')), \
             patch.object(bounded,'capture',side_effect=optional),patch.dict(os.environ,{'RUNNER_STARTED_AT':probe.iso(current[0])}), \
             patch('urllib.request.urlopen',side_effect=AssertionError('NO_LIVE_MIS')):
            output=Path(tmp);self.assertEqual(probe.live(output),0)
            completion=json.loads((output/'capture_completion.json').read_text());self.assertTrue(completion['core_capture_complete'])
            self.assertEqual(completion['errors'],[])
        by_phase=dict(events)
        self.assertEqual(by_phase['pre_reference_A'],'13:27:00.000000')
        self.assertEqual(by_phase['pre_reference_B'],'13:28:15.000000')
        self.assertEqual(by_phase['pre_reference_C'],'13:29:00.000000')
        self.assertGreater(by_phase['optional_retry'],by_phase['pre_reference_C'])
        self.assertEqual(by_phase['close_reference_A'],'13:32:30.000000')
        self.assertEqual(by_phase['close_reference_B'],'13:33:20.000000')
    def test_fixed_C_before_fast_retry(self):self.run_schedule(synthetic_completed)
    def test_fixed_C_before_hung_retry(self):self.run_schedule(synthetic_hang)
    def test_fixed_C_before_failed_retry(self):self.run_schedule(synthetic_crash)
    def test_tomorrow_fixed_C_is_not_blocked_by_hung_retry(self):self.run_schedule(synthetic_hang,'2026-10-22')


if __name__=='__main__':unittest.main()
