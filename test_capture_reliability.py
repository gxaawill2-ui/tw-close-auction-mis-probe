"""Fault injection tests: no network, no persisted live state."""
import copy
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import close_research
import convergence
import freshness
import probe
from test_close_research import DAY, ref, assess
from test_convergence import SYMBOL


class TransportReliabilityTests(unittest.TestCase):
    def test_timeout_before_deadline_retains_actual_error_and_attempt_times(self):
        start=probe.target(DAY,'13:34:07');end=probe.target(DAY,'13:34:08.4')
        with patch.object(probe,'now_tpe',side_effect=[start,end,end]),patch.object(probe,'get_bytes',side_effect=TimeoutError('timed out')),patch.object(probe.time,'sleep') as sleep:
            r=probe.fetch_mis([SYMBOL],deadline=probe.target(DAY,'13:34:08'))
        self.assertIn('TimeoutError',r.error);self.assertIn('RESPONSE_AFTER_CAPTURE_DEADLINE',r.error)
        self.assertEqual(r.retry_stop_reason,'INSUFFICIENT_RETRY_BUDGET');self.assertEqual(r.retry,0)
        self.assertEqual(r.requested_at,probe.iso(start));self.assertEqual(len(r.attempts),1);sleep.assert_not_called()

    def test_empty_response_retries_and_preserves_both_attempts(self):
        with patch.object(probe,'get_bytes',side_effect=[(200,b''),(200,b'{"rtcode":"0000","msgArray":[]}')]),patch.object(probe.time,'sleep') as sleep:
            r=probe.fetch_mis([SYMBOL])
        self.assertEqual(r.attempts[0]['error'],'MIS_EMPTY_BODY');self.assertIsNone(r.error)
        self.assertEqual(len(r.attempts),2);sleep.assert_called_once_with(.5)

    def test_throttled_service_is_never_retried(self):
        for status in (403,429):
            with self.subTest(status=status),patch.object(probe,'get_bytes',return_value=(status,b'{}')) as get:
                r=probe.fetch_mis([SYMBOL],retry=4)
                self.assertEqual(get.call_count,1);self.assertEqual(r.error,'HTTP_'+str(status))

    def test_after_deadline_http_200_is_not_accepted_as_fresh(self):
        start=probe.target(DAY,'13:34:07');end=probe.target(DAY,'13:34:09')
        with patch.object(probe,'now_tpe',side_effect=[start,end,end]),patch.object(probe,'get_bytes',return_value=(200,b'{"rtcode":"0000","msgArray":[]}')):
            r=probe.fetch_mis([SYMBOL],deadline=probe.target(DAY,'13:34:08'))
        self.assertEqual(r.error,'RESPONSE_AFTER_CAPTURE_DEADLINE');self.assertTrue(probe.analyze([SYMBOL],r)['missing'])

    def test_expired_stage_performs_no_http_request(self):
        with patch.object(probe,'now_tpe',return_value=probe.target(DAY,'13:35:00')),patch.object(probe,'get_bytes') as get:
            r=probe.fetch_mis([SYMBOL],deadline=probe.target(DAY,'13:35:00'))
        get.assert_not_called();self.assertEqual(r.error,'CAPTURE_DEADLINE_NO_REQUEST')

    def test_full_market_normal_and_missing_50_concentrated_or_scattered(self):
        universe=[{**SYMBOL,'code':str(1000+i)} for i in range(1970)]
        for mode in ('normal','batch','scatter'):
            missing=set() if mode=='normal' else set(str(1000+i) for i in (range(50) if mode=='batch' else list(range(0,1970,39))[:50]))
            def fetch(symbols,*args):
                items=[{'ex':s['ex'],'c':s['code'],'n':'fixture'} for s in symbols if s['code'] not in missing]
                return probe.FetchResult(probe.iso(),probe.iso(),1,200,0,None,None,{'rtcode':'0000','msgArray':items})
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as d,patch.object(probe,'fetch_mis',side_effect=fetch):
                result=probe.snapshot('close_reference_B',probe.now_tpe(),universe,Path(d))
            metrics=result['metrics'];self.assertEqual(metrics['success_count'],1970-len(missing));self.assertEqual(metrics['batch_count'],40)
            self.assertEqual(metrics['symbol_set_equal'],not missing)

    def test_metrics_count_prior_timeout_even_after_success(self):
        r=probe.FetchResult(probe.iso(),probe.iso(),3,200,1,None,None,{'msgArray':[{'ex':'tse','c':'2330','n':'fixture'}]},
            [{'latency_ms':20000,'http_status':None,'error':'URLError:timed out'}, {'latency_ms':3,'http_status':200,'error':None}])
        with tempfile.TemporaryDirectory() as d,patch.object(probe,'fetch_mis',return_value=r):
            m=probe.snapshot('close_reference_B',probe.now_tpe(),[SYMBOL],Path(d))['metrics']
        self.assertEqual(m['timeouts'],1);self.assertEqual(m['http_errors'],0);self.assertEqual(m['http_attempt_count'],2)
        self.assertEqual(m['slowest_batch_ms'],20003);self.assertEqual(m['retries'],1)


class RecoveryTests(unittest.TestCase):
    def retry_ref(self,clock='13:34:25',**kwargs):
        r=ref('close_reference_C',**kwargs);r.update(phase='close_targeted_retry',planned_at=DAY+'T'+clock+'.000+08:00',
            requested_at=DAY+'T'+clock+'.000+08:00',received_at=DAY+'T'+clock+'.500+08:00')
        r['response']['queryTime'].update(sysTime=clock)
        return r

    def test_C_missing_partial_then_targeted_recovers_without_relabelling(self):
        a,b=ref('close_reference_A'),ref('close_reference_B',server='13:24:51')
        c=ref('close_reference_C');c.update(response={'msgArray':[]},missing=['tse:2330'])
        retry=self.retry_ref();result=assess(a,b,c,retry)
        self.assertEqual(result['classification'],'TARGETED_converged');self.assertFalse(result['validated'])
        self.assertEqual(result['selected']['phase'],'close_targeted_retry');self.assertEqual(result['selected']['planned_at'],retry['planned_at'])

    def test_conflict_or_server_regression_prevents_using_old_pair(self):
        a,b=ref('close_reference_A'),ref('close_reference_B')
        for retry in (self.retry_ref(price='105'),self.retry_ref(server='13:32:20')):
            # Explicit fresh lower server timestamp is a regression even if the
            # research age bound would also reject it as stale.
            if retry['response']['msgArray'][0]['trade']['z']=='104':
                retry['response']['queryTime']['sysTime']='13:34:24'
                b['response']['queryTime']['sysTime']='13:34:25'
                b['received_at']=DAY+'T13:34:25.500+08:00'
                retry['requested_at']=DAY+'T13:34:26.000+08:00';retry['received_at']=DAY+'T13:34:26.500+08:00'
            self.assertEqual(assess(a,b,retry)['classification'],'unresolved')

    def test_post_1325_reference_cannot_supply_pre_1325_price(self):
        for trade in ('13:25:00','13:27:00','13:28:00','13:29:00'):
            rows=freshness.observations([ref('pre_reference_A',trade=trade),ref('pre_reference_B',trade=trade)],DAY)
            self.assertFalse(convergence.pair(rows,DAY,'pre')['converged'])
        rows=freshness.observations([ref('pre_reference_A',trade='13:24:59'),ref('pre_reference_B',trade='13:24:59')],DAY)
        self.assertTrue(convergence.pair(rows,DAY,'pre')['converged'])

    def test_no_new_trade_and_delayed_close_stay_research_only(self):
        for trade in ('10:55:13','13:30:00','13:33:00'):
            a=ref('close_reference_A',trade=trade)
            if trade>'13:30:00':
                a['response']['queryTime']['sysTime']='13:33:05'
                a['received_at']=DAY+'T13:33:05.500+08:00'
            out=assess(a,ref('close_reference_B',trade=trade))
            self.assertTrue(out['converged']);self.assertFalse(out['validated']);self.assertEqual(out['trade_time'],trade)

    def test_affected_only_retry_stops_at_deadline_and_records_real_clock(self):
        current=[probe.target(DAY,'13:34:20')];calls=[]
        a,b=ref('close_reference_A'),ref('close_reference_B',server='13:24:51')
        def snap(phase,planned,selected,output,deadline):
            calls.append((phase,planned,selected,deadline));current[0]+=timedelta(seconds=3)
            return {'records':[self.retry_ref('13:34:20')],'metrics':{'phase':phase}}
        with tempfile.TemporaryDirectory() as d,patch.object(probe,'now_tpe',side_effect=lambda:current[0]), \
             patch.object(probe,'wait_until',side_effect=lambda t:current.__setitem__(0,t)),patch.object(probe,'snapshot',side_effect=snap):
            rounds=probe.targeted_retries('close',DAY,[{'records':[a,b]}],[SYMBOL],Path(d))
        self.assertEqual(len(rounds),1);self.assertEqual(calls[0][2],[SYMBOL]);self.assertEqual(calls[0][0],'close_targeted_retry')
        current[0]=probe.target(DAY,'13:34:59')
        with patch.object(probe,'now_tpe',side_effect=lambda:current[0]),patch.object(probe,'snapshot') as snap:
            self.assertEqual(probe.targeted_retries('close',DAY,[],[SYMBOL],Path('/unused')),[])
        snap.assert_not_called()

    def test_unrecoverable_failure_has_bounded_rounds(self):
        current=[probe.target(DAY,'13:34:10')]
        failed=ref('close_reference_C');failed.update(error='HTTP_503',http_status=503,response={})
        def wait(t):current[0]=t
        with patch.object(probe,'now_tpe',side_effect=lambda:current[0]),patch.object(probe,'wait_until',side_effect=wait), \
             patch.object(probe,'snapshot',return_value={'records':[failed],'metrics':{}}) as snap:
            rounds=probe.targeted_retries('close',DAY,[],[SYMBOL],Path('/unused'))
        self.assertLessEqual(len(rounds),6);self.assertLessEqual(current[0],probe.target(DAY,'13:35:00'))
        self.assertTrue(rounds)
