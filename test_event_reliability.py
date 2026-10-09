import copy
import hashlib
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from event_scheduler import identify, claim, finish, recovery_scope, freshness_blocks_recovery, git
from event_dispatch import dispatch
from fund_importance import evaluate, build
from index_events import Fetcher,parse_tpex_etf_observations,parse_yuanta_aum

ROOT=Path(__file__).parent
NOW='2026-10-10T17:20:05+08:00'

class SchedulerTests(unittest.TestCase):
    def native(self,stamp=NOW):return identify('schedule','20 9 * * *','',stamp,'1')
    def test_normal_1720(self):
        r=self.native();self.assertEqual(r['schedule_slot'],'17:20');self.assertTrue(r['eligible']);self.assertIsNone(r['scheduled_for']);self.assertIsNone(r['delay_seconds'])
    def test_unattributed_recovery_never_fulfills_slot(self):
        late=self.native('2026-10-11T00:13:06+08:00')
        recovery=recovery_scope(late,'2026-10-10T17:20:00+08:00')
        self.assertTrue(recovery['eligible']);self.assertIsNone(recovery['planned_for']);self.assertTrue(recovery['original_slot_not_fulfilled'])
        self.assertTrue(recovery['identity'].startswith('unattributed-'))
    def test_fresh_data_prevents_late_source_requests(self):
        late=self.native('2026-10-11T00:13:06+08:00')
        self.assertFalse(recovery_scope(late,'2026-10-10T23:20:00+08:00')['eligible'])
    def test_delay_unattributed(self):
        r=self.native('2026-10-11T00:13:06+08:00');self.assertFalse(r['eligible']);self.assertEqual(claim({},r,NOW,'1')[1],'UNATTRIBUTED_DELAYED_NATIVE')
    def test_backup_recovers_no_success(self):
        r=identify('workflow_dispatch','','17:20','2026-10-10T17:35:01+08:00','2');p,d=claim({},r,'2026-10-10T17:35:02+08:00','2');self.assertEqual(d,'CLAIMED');self.assertTrue(p['missed_slot']);self.assertEqual(finish(p,'2','2026-10-10T17:36:00+08:00',True)['result'],'RECOVERED_BY_BACKUP')
    def test_duplicate_success(self):
        r=self.native();p,_=claim({},r,NOW,'1');p=finish(p,'1',NOW,True);self.assertEqual(claim(p,r,NOW,'2')[1],'DUPLICATE_SUCCESS')
    def test_simultaneous_lease(self):
        r=self.native();p,_=claim({},r,NOW,'1');self.assertEqual(claim(p,r,NOW,'2')[1],'LEASE_HELD')
    def test_cross_day_identity(self):self.assertNotEqual(self.native()['identity'],self.native('2026-10-11T17:20:00+08:00')['identity'])
    def test_lease_cas_owner(self):
        p,_=claim({},self.native(),NOW,'1')
        with self.assertRaises(ValueError):finish(p,'2',NOW,True)
    def test_bounded_retries(self):
        p,_=claim({},self.native(),NOW,'1');p=finish(p,'1',NOW,False)
        p,_=claim(p,self.native(),NOW,'2');p=finish(p,'2',NOW,False)
        self.assertEqual(claim(p,self.native(),NOW,'3')[1],'RETRY_LIMIT')
    def test_backup_published_while_late_native_waited(self):
        recovery=recovery_scope(self.native('2026-10-11T00:13:06+08:00'),'2026-10-10T17:20:00+08:00')
        self.assertTrue(freshness_blocks_recovery(recovery,{'last_successful_scan_at':'2026-10-11T00:14:00+08:00'},'2026-10-11T00:15:00+08:00'))
    def test_unknown_cron(self):
        with self.assertRaises(ValueError):identify('schedule','20 0,9 * * *','',NOW,'1')
    def test_early_backup_rejected(self):self.assertFalse(identify('workflow_dispatch','','17:20',NOW,'2')['eligible'])
    def test_adhoc_never_fulfills_slot(self):self.assertTrue(identify('push','','',NOW,'2')['identity'].startswith('adhoc-'))
    def test_dispatch_no_main(self):
        with self.assertRaises(ValueError):dispatch('test','main')
    def test_permission_failures_no_retry(self):
        for code in [400,401,403,404,422]:
            calls=[]
            def opener(req,timeout):calls.append(req);raise HTTPError(req.full_url,code,'error',{},None)
            with self.assertRaises(RuntimeError):dispatch('redacted-test','improve/test',opener)
            self.assertEqual(len(calls),1)
    def test_timeout_bounded(self):
        calls=[]
        def opener(req,timeout):calls.append(timeout);raise TimeoutError()
        with self.assertRaises(RuntimeError):dispatch('redacted-test','improve/test',opener)
        self.assertEqual(calls,[10,10])
    def test_realistic_http_dispatch(self):
        class Response:
            status=204
            def __enter__(self):return self
            def __exit__(self,*args):pass
        def opener(req,timeout):
            self.assertEqual(req.method,'POST');self.assertIn('index-events.yml',req.full_url);self.assertTrue(json.loads(req.data)['inputs']['self_test']);return Response()
        self.assertEqual(dispatch('redacted-test','improve/test',opener)['http_status'],204)
    def test_git_errors_never_disclose_header(self):
        sensitive=['git','config','header','private-test-credential']
        with patch('event_scheduler.subprocess.check_output',side_effect=subprocess.CalledProcessError(1,sensitive)):
            with self.assertRaises(RuntimeError) as error:git(sensitive[1:],ROOT)
        self.assertNotIn('private-test-credential',str(error.exception))
    def test_git_network_timeout_is_bounded(self):
        with patch('event_scheduler.subprocess.check_output',side_effect=subprocess.TimeoutExpired(['git','fetch'],45)) as mock:
            with self.assertRaises(RuntimeError):git(['fetch','origin','main'],ROOT)
        self.assertEqual(mock.call_args.kwargs['timeout'],45)
    def test_no_mis_change(self):
        p=ROOT/'state/candidates/2026-10-08.json'
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),'794cdb1749a7318612fad5003bceb47b126b5d03a8cbda16abf14332954c111b')

class ImportanceTests(unittest.TestCase):
    def setUp(self):
        self.fund={'etf_code':'0050','etf_name':'test','management_type':'PASSIVE','mapping_status':'CONFIRMED','information_available_as_of':NOW,'source_url':'https://official.example/fund'}
        self.event={'event_id':'test','event_name':'test','related_etf_codes':['0050'],'index_name':'test','event_status':'EXPECTED','close_date_status':'EXPECTED_CLOSE_WATCH_DATE','information_available_as_of':NOW,'source_url':'https://official.example/event','effective_date':'2026-12-01','closing_impact_date':'2026-11-30'}
        self.metric={'fund_code':'0050','fund_aum':200e9,'currency':'TWD','source_url':'https://official.example/aum','aum_as_of':'2026-10-08','information_available_as_of':NOW}
    def test_high(self):self.assertEqual(evaluate(self.fund,self.event,self.metric,NOW)['importance_level'],'HIGH')
    def test_medium(self):
        self.metric['fund_aum']=1e9;self.assertEqual(evaluate(self.fund,self.event,self.metric,NOW)['importance_level'],'MEDIUM')
    def test_low(self):
        self.metric['fund_aum']=1e9;self.event['implementation_window']={'dates':['2026-11-30','2026-12-01']};self.assertEqual(evaluate(self.fund,self.event,self.metric,NOW)['importance_level'],'LOW')
    def test_missing_not_low(self):self.assertEqual(evaluate(self.fund,self.event,None,NOW)['importance_level'],'DATA_INSUFFICIENT')
    def test_active_not_passive(self):
        self.fund['management_type']='ACTIVE';self.assertEqual(evaluate(self.fund,self.event,self.metric,NOW)['importance_level'],'DATA_INSUFFICIENT')
    def test_stale_aum(self):
        self.metric['aum_as_of']='2026-09-01';self.assertEqual(evaluate(self.fund,self.event,self.metric,NOW)['importance_level'],'DATA_INSUFFICIENT')
    def test_future_asof(self):
        self.metric['information_available_as_of']='2026-10-11T17:20:00+08:00';self.assertEqual(evaluate(self.fund,self.event,self.metric,NOW)['importance_level'],'DATA_INSUFFICIENT')
    def test_date_rating_independent(self):
        r=evaluate(self.fund,self.event,self.metric,NOW);self.assertEqual(r['importance_level'],'HIGH');self.assertEqual(r['importance_confidence'],'PROVISIONAL');self.assertEqual(self.event['close_date_status'],'EXPECTED_CLOSE_WATCH_DATE')
    def test_no_changes_invented(self):self.assertIsNone(evaluate(self.fund,self.event,self.metric,NOW)['affected_stock_count'])
    def test_weights_not_invented(self):self.assertIsNone(evaluate(self.fund,self.event,self.metric,NOW)['estimated_exposure_change'])
    def test_different_funds_same_date(self):
        second={**self.fund,'etf_code':'0051'};self.event['related_etf_codes'].append('0051');metrics=[self.metric,{**self.metric,'fund_code':'0051','fund_aum':1e9}]
        rows=build([self.event],[self.fund,second],metrics,NOW);self.assertEqual({r['importance_level'] for r in rows},{'HIGH','MEDIUM'})
    def test_different_quarters(self):
        second={**self.event,'event_id':'second','implementation_window':{'dates':['2026-12-01']}}
        rows=build([self.event,second],[self.fund],[self.metric],NOW);self.assertEqual({r['importance_level'] for r in rows},{'HIGH','MEDIUM'})
    def test_unchanged_source_check_does_not_rewrite_history(self):
        old=build([self.event],[self.fund],[self.metric],NOW)
        self.metric['last_checked_at']='2026-10-11T17:20:00+08:00'
        new=build([self.event],[self.fund],[self.metric],'2026-10-11T17:20:00+08:00',old)
        self.assertEqual(new[0]['rating_history'],[]);self.assertEqual(new[0]['information_available_as_of'],NOW)
    def test_correction_history(self):
        old=build([self.event],[self.fund],[self.metric],NOW);self.metric['fund_aum']=1e9
        new=build([self.event],[self.fund],[self.metric],'2026-10-11T17:20:00+08:00',old);self.assertEqual(len(new[0]['rating_history']),1);self.assertEqual(new[0]['first_rated_at'],NOW)

class SourceReliabilityTests(unittest.TestCase):
    def test_terms_restriction_before_network(self):
        client=Fetcher()
        with self.assertRaisesRegex(RuntimeError,'TERMS_AUTOMATION_RESTRICTED'):client.get('https://www.lseg.com/public.pdf')
        self.assertEqual(client.attempts,0)
    def test_truncated_json_retry(self):
        c=Fetcher();c.get=lambda url: next(responses);responses=iter([b'[{"name":"cut',b'[{"name":"ok"}]'])
        self.assertEqual(json.loads(c.get_json('https://official.example/api'))[0]['name'],'ok');self.assertEqual(len(c.json_diagnostics),1)
    def test_both_truncated_reject(self):
        c=Fetcher();c.get=lambda url:b'[{"name":"cut'
        with self.assertRaises(json.JSONDecodeError):c.get_json('https://official.example/api')
        self.assertEqual(len(c.json_diagnostics),2)
    def test_tpex_partial_no_inferred_aum(self):
        raw=json.dumps([{'Date':'1151008','SecuritiesCompanyCode':'006201','CompanyName':'test','Capitals':'999'},{'Date':'1151008','SecuritiesCompanyCode':'020001','CompanyName':'ETN'}]).encode()
        rows=parse_tpex_etf_observations(raw,'https://official.example',NOW);self.assertEqual(len(rows),1);self.assertIsNone(rows[0]['index_name']);self.assertFalse(rows[0]['calendar_eligible']);self.assertNotIn('fund_aum',rows[0])
    def test_tpex_missing_not_delisting(self):
        with self.assertRaises(ValueError):parse_tpex_etf_observations(b'[]','https://official.example',NOW)
    def test_tpex_wrong_date(self):
        with self.assertRaises(ValueError):parse_tpex_etf_observations(b'[{"Date":"1151011","SecuritiesCompanyCode":"006201","CompanyName":"test"}]','https://official.example',NOW)
    def test_pcf_real_labels(self):
        raw=b'<p>0050</p><p>\xe4\xb8\x8a\xe5\x82\xb3\xe6\x99\x82\xe9\x96\x93:2026-10-08 15:51:37</p>'
        raw+= '<p>基金淨資產價值 NTD 2,551,521,434,557</p><p>2026/10/08 每受益權單位淨資產價值</p>'.encode()
        metric=parse_yuanta_aum(raw,'https://official.example','0050',NOW);self.assertEqual(metric['fund_aum'],2551521434557);self.assertEqual(metric['aum_as_of'],'2026-10-08')
    def test_pcf_format_changed(self):
        with self.assertRaises(ValueError):parse_yuanta_aum(b'0050 changed','https://official.example','0050',NOW)

if __name__=='__main__':unittest.main()
