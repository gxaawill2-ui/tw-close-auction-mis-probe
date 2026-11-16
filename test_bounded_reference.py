"""SYNTHETIC ONLY: 2,200-stock clock/transport stress; no live MIS requests."""
import json
import multiprocessing
import signal
import tempfile
import time
import unittest
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import bounded_reference as bounded
import probe

DAY='2026-11-16'
SYMBOLS=[{'ex':'tse','code':str(1000+i)} for i in range(2200)]
REPORT=[]

class FakeClock:
    def __init__(self, start): self.start=start; self.t=0.
    def now(self): return self.start+timedelta(seconds=self.t)
    def sleep(self, seconds): self.t+=seconds

class FakeContext:
    def __init__(self, clock, delays, errors=None, late=False, inconsistent=False):
        self.clock=clock; self.delays=delays; self.errors=errors or {}; self.late=late
        self.inconsistent=inconsistent; self.children=[]; self.peak=0
    def Process(self, target, args, daemon):
        child=FakeProcess(self,args); self.children.append(child); return child

class FakeProcess:
    def __init__(self, context, args):
        self.ctx=context; self.group,self.deadline,self.timeout,self.directory=args
        self.directory=Path(self.directory); self.pid=None; self.exitcode=None; self.live=False
    def start(self):
        self.pid=len(self.ctx.children); self.live=True; self.started=self.ctx.clock.t
        self.delay=self.ctx.delays.get(self.group[0]['code'],1.)
        bounded._atomic(self.directory/'started.json',{'requested_at':probe.iso(self.ctx.clock.now())})
        self.ctx.peak=max(self.ctx.peak,sum(c.live for c in self.ctx.children))
    def is_alive(self):
        if self.live and self.ctx.clock.t-self.started>=self.delay:
            received=self.ctx.clock.now(); status=self.ctx.errors.get(self.group[0]['code'],200)
            if self.ctx.late: received=probe.freshness.parsed_time(self.deadline)+timedelta(seconds=1)
            items=[{'ex':s['ex'],'c':s['code'],'n':'SYNTHETIC','d':'20261116','z':'10','t':'13:24:59'} for s in self.group]
            if self.ctx.inconsistent: items.append(items[0].copy())
            body={'rtcode':'0000','msgArray':items}
            result=probe.FetchResult(probe.iso(self.ctx.clock.start+timedelta(seconds=self.started)),
                   probe.iso(received),round(self.delay*1000),status,0,None if status==200 else 'HTTP_'+str(status),
                   json.dumps(body),body)
            bounded._atomic(self.directory/'result.json',asdict(result)); self.live=False; self.exitcode=0
        return self.live
    def terminate(self): self.live=False; self.exitcode=-15
    def kill(self): self.live=False; self.exitcode=-9
    def join(self, timeout=0): pass


def hang(group, deadline, timeout, directory):
    signal.signal(signal.SIGTERM,signal.SIG_IGN)
    bounded._atomic(Path(directory)/'started.json',{'requested_at':probe.iso()})
    time.sleep(120)


def crash_before_request(group, deadline, timeout, directory):
    return

def synthetic_complete(group, deadline, timeout, directory):
    started=probe.iso()
    bounded._atomic(Path(directory)/'started.json',{'requested_at':started})
    if group[0]['code'] in ('1000','1050') and (Path(directory).parent/'hang_first_two').exists():
        signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(120)
    body={'rtcode':'0000','msgArray':[{'ex':s['ex'],'c':s['code'],'n':'SYNTHETIC_ONLY'} for s in group]}
    result=probe.FetchResult(started,probe.iso(),0,200,0,None,json.dumps(body),body)
    bounded._atomic(Path(directory)/'result.json',asdict(result))


class BoundedReferenceTests(unittest.TestCase):
    def run_case(self,name,delays=None,phase='pre_reference_C',errors=None,late=False,inconsistent=False,start_offset=0):
        clock=FakeClock(probe.target(DAY,'13:29:00' if phase.endswith('_C') else '13:28:15')+timedelta(seconds=start_offset))
        context=FakeContext(clock,delays or {},errors,late,inconsistent)
        with tempfile.TemporaryDirectory() as directory,patch('urllib.request.urlopen',side_effect=AssertionError('NO_LIVE_MIS')):
            result=bounded.capture(phase,probe.target(DAY,'13:29:00' if phase.endswith('_C') else '13:28:15'),
                SYMBOLS,Path(directory),probe.target(DAY,'13:29:30' if phase.endswith('_C') else '13:28:58'),
                ctx=context,clock=clock.now,monotonic=lambda:clock.t,sleep=clock.sleep)
            rows=[json.loads(line) for line in (Path(directory)/(phase+'_raw.jsonl')).read_text().splitlines()]
            self.assertEqual(len(rows),44); self.assertEqual(len({s['code'] for r in rows for s in r['symbols']}),2200)
            self.assertFalse(any(c.live for c in context.children)); self.assertLessEqual(context.peak,8)
            self.assertLessEqual(clock.t,24.1 if phase.endswith('_C') else 42.1)
            self.assertEqual(len(rows),len(result['records']))
            REPORT.append({'scope':'SYNTHETIC_NOT_LIVE','case':name,**result['metrics']})
            return result,context
    def test_normal_2200(self):
        result,ctx=self.run_case('normal')
        self.assertEqual(result['metrics']['success_count'],2200)
        self.assertLess(result['metrics']['wall_time_seconds'],7)
    def test_delayed_2200(self):
        result,_=self.run_case('partial_delay',{str(1000+i*50):3.5 for i in range(0,44,7)})
        self.assertEqual(result['metrics']['success_count'],2200)
    def test_stalled_requests_do_not_block_first_pass(self):
        result,ctx=self.run_case('two_hanging',{str(1000+i*50):120 for i in (0,1)})
        self.assertEqual(result['metrics']['success_count'],2100)
        self.assertEqual(result['metrics']['forced_terminations'],2)
        self.assertEqual(len(ctx.children),44)
        self.assertEqual(result['metrics']['not_requested_batches'],0)
    def test_every_request_hangs_is_not_claimed_complete(self):
        result,ctx=self.run_case('all_hanging',{str(1000+i*50):120 for i in range(44)})
        self.assertEqual(result['metrics']['success_count'],0)
        self.assertGreater(result['metrics']['timeouts'],0)
        self.assertTrue(all(r['response'] is None for r in result['records']))
    def test_slow_B_finishes_before_C(self):
        result,_=self.run_case('B_all_hanging',{str(1000+i*50):120 for i in range(44)},phase='pre_reference_B')
        self.assertLess(result['metrics']['wall_time_seconds'],43)
        self.assertEqual(result['metrics']['not_requested_batches'],0)
    def test_403_429_stop_further_requests(self):
        for status in (403,429):
            result,ctx=self.run_case('rate_'+str(status),errors={'1000':status})
            self.assertTrue(result['metrics']['rate_limit_circuit_open'])
            self.assertEqual(len(ctx.children),8)
            self.assertEqual(result['metrics']['not_requested_batches'],36)
            self.assertTrue(any(r['error']=='CAPTURE_DEADLINE_NO_REQUEST' for r in result['records']))
    def test_temporary_503_preserved_not_retried_inline(self):
        result,ctx=self.run_case('temporary_503',errors={'1000':503})
        self.assertEqual(result['metrics']['http_errors'],1)
        self.assertEqual(result['metrics']['success_count'],2150)
        self.assertEqual(len(ctx.children),44)
    def test_near_deadline_never_labels_unsent_as_timeout(self):
        result,_=self.run_case('near_deadline',start_offset=23.9)
        self.assertGreater(result['metrics']['not_requested_batches'],0)
        self.assertTrue(any(r['error']=='CAPTURE_DEADLINE_NO_REQUEST' for r in result['records']))
    def test_late_success_is_retained_but_rejected(self):
        result,_=self.run_case('late_response',late=True)
        self.assertEqual(result['metrics']['success_count'],0)
        self.assertTrue(all(r['error']=='RESPONSE_AFTER_CAPTURE_DEADLINE' for r in result['records']))
        self.assertTrue(all(r['raw_body'] for r in result['records']))
    def test_inconsistency_evidence_is_preserved(self):
        result,_=self.run_case('duplicate_response',inconsistent=True)
        self.assertEqual(result['metrics']['duplicate_count'],44)
        self.assertTrue(all(r['duplicate'] for r in result['records']))
    def test_real_2200_spawn_workers_and_journal(self):
        start=probe.now_tpe(); children={c.pid for c in multiprocessing.active_children()}
        with tempfile.TemporaryDirectory() as directory:
            result=bounded.capture('pre_reference_C',start,SYMBOLS,Path(directory),start+timedelta(seconds=30),child_target=synthetic_complete)
            self.assertEqual(result['metrics']['success_count'],2200)
            self.assertEqual(result['metrics']['not_requested_batches'],0)
            self.assertLess(result['metrics']['wall_time_seconds'],25)
            REPORT.append({'scope':'SYNTHETIC_REAL_44_PROCESS_NO_NETWORK','case':'spawn_2200',**result['metrics']})
        self.assertEqual({c.pid for c in multiprocessing.active_children()},children)

    def test_real_process_ignoring_terminate_is_killed(self):
        children={c.pid for c in multiprocessing.active_children()}; start=probe.now_tpe();tick=time.monotonic()
        with tempfile.TemporaryDirectory() as directory:
            result=bounded.capture('pre_reference_B',start,SYMBOLS[:50],Path(directory),start+timedelta(seconds=3),child_target=hang)
            self.assertEqual(result['metrics']['forced_terminations'],1)
            self.assertEqual(result['records'][0]['error'],'REQUEST_HARD_TIMEOUT')
            self.assertIsNone(result['records'][0]['response'])
        self.assertLess(time.monotonic()-tick,3.4)
        self.assertEqual({c.pid for c in multiprocessing.active_children()},children)
    def test_worker_exit_without_request_is_mandatory_failure(self):
        start=probe.now_tpe()
        with tempfile.TemporaryDirectory() as directory:
            result=bounded.capture('pre_reference_B',start,SYMBOLS[:50],Path(directory),start+timedelta(seconds=3),child_target=crash_before_request)
            self.assertEqual(result['records'][0]['error'],'CAPTURE_DEADLINE_NO_REQUEST')
    def test_router_leaves_A_and_close_untouched(self):
        with patch.object(bounded,'capture',return_value='bounded') as capture:
            self.assertEqual(probe.snapshot('pre_reference_B',None,[],None,None),'bounded')
            self.assertEqual(probe.snapshot('pre_reference_C',None,[],None,None),'bounded')
            self.assertEqual(capture.call_count,2)
        with tempfile.TemporaryDirectory() as directory,patch.object(bounded,'capture',side_effect=AssertionError('not B/C')):
            for phase in ('pre_reference_A','close_reference_A','close_reference_B','close_reference_C'):
                probe.snapshot(phase,probe.now_tpe(),[],Path(directory),probe.now_tpe())

if __name__=='__main__':unittest.main()
