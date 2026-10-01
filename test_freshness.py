import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import freshness as f
import official_quotes as official
import tradable


def record(clock,server,trade_time='13:24:59',price='2505',v='14277',cached=None):
    requested='2026-10-02T'+clock+'.000+08:00'
    received=(datetime.fromisoformat(requested)+timedelta(milliseconds=500)).isoformat()
    body={'queryTime':{'sysDate':'20261002','sysTime':server},'msgArray':[
        {'ex':'tse','c':'2330','n':'台積電','d':'20261002','z':'-','pz':'2510','t':'13:25:30',
         'v':v,'tv':'-','s':'-','trade':{'t':trade_time,'z':price,'v':13,'ft':12}}]}
    if cached is not None:body['cachedAlive']=cached
    return {'window':'preclose_window','planned_at':requested,'requested_at':requested,
            'received_at':received,'latency_ms':500,'http_status':200,'error':None,
            'response':body,'symbols':[{'ex':'tse','code':'2330','market':'TWSE','name':'台積電'}]}


class FreshnessTests(unittest.TestCase):
    def test_checkpoint_plan_exact_and_no_duplicates(self):
        ticks=f.planned_ticks('2026-10-02','13:24:50','13:25:10',f.PRECLOSE_CHECKPOINTS)
        self.assertEqual(len(ticks),33)
        self.assertEqual(ticks[-1].strftime('%H:%M:%S'),'13:26:10')
        self.assertEqual(len(f.planned_ticks('2026-10-02','13:29:50','13:30:15',f.CLOSE_CHECKPOINTS)),35)

    def test_repeated_old_cache_never_converges(self):
        rows=f.observations([record('13:25:20','13:24:50'),record('13:25:30','13:24:50'),record('13:25:40','13:24:50')],'2026-10-02')
        self.assertEqual(f.pre_convergence(rows,'2026-10-02')['status'],'stale_cache')

    def test_request_time_is_not_server_time(self):
        row=f.observations([record('13:25:05','13:24:50')],'2026-10-02')[0]
        self.assertEqual(row['server_age_ms'],15000)
        self.assertEqual(row['server_age_at_receive_ms'],15500)
        self.assertFalse(f.pre_eligible(row,'2026-10-02'))

    def test_three_distinct_fresh_times_only_candidate(self):
        rows=f.observations([record('13:25:20','13:25:20'),record('13:25:30','13:25:30'),record('13:25:40','13:25:40')],'2026-10-02')
        out=f.pre_convergence(rows,'2026-10-02')
        self.assertEqual(out['status'],'confirmed_candidate');self.assertFalse(out['validated'])

    def test_new_last_trade_resets_candidate_convergence(self):
        records=[record('13:25:20','13:25:20'),record('13:25:30','13:25:30'),record('13:25:40','13:25:40'),
                 record('13:25:45','13:25:45','13:24:59','2500','14280')]
        rows=f.observations(records,'2026-10-02')
        out=f.pre_convergence(rows,'2026-10-02')
        self.assertEqual(out['status'],'not_converged');self.assertEqual(out['candidate'],'2500')

    def test_same_server_payload_not_three_fresh_responses(self):
        rows=f.observations([record('13:25:20','13:25:20'),record('13:25:21','13:25:20'),record('13:25:22','13:25:20')],'2026-10-02')
        self.assertEqual(f.pre_convergence(rows,'2026-10-02')['status'],'not_converged')

    def test_nulls_and_missing_never_become_zero(self):
        r=record('13:25:20','13:25:20');r['response']['msgArray']=[];r['error']='TIMEOUT'
        row=f.observations([r],'2026-10-02')[0]
        self.assertIsNone(row['trade_z']);self.assertIsNone(row['v'])
        self.assertIsNone(f.decimal_value('-'))

    def test_wrong_data_date_rejected(self):
        r=record('13:25:20','13:25:20');r['response']['queryTime']['sysDate']='20261001'
        self.assertFalse(f.fresh_candidate(f.observations([r],'2026-10-02')[0],'2026-10-02'))

    def test_late_observation_is_not_delayed_trade(self):
        rows=f.observations([record('13:32:00','13:32:00','13:30:00','2510','18496')],'2026-10-02')
        out=f.close_evidence(rows,'2026-10-02',{'official_close':'2510'})
        self.assertEqual(out['close_classification'],'normal_close_candidate')
        self.assertEqual(out['close_trade_time'],'13:30:00');self.assertFalse(out['validated'])

    def test_undated_or_yesterday_official_is_pending(self):
        for date in (None,'20261001'):
            self.assertEqual(official.parse_quotes('otc','2026-10-02',{'date':date,'stat':'ok'})[1],'PENDING_WRONG_OR_MISSING_DATE')
        self.assertEqual(official.parse_quotes('otc','2026-10-02',{'date':'20261002','stat':'ok','tables':[]})[1],'PENDING_EMPTY_TABLE')

    def test_reduction_resume_date_rejoins_pool_without_blacklist(self):
        company=[{'ex':'otc','code':'4806'}]
        e=tradable.event('otc','4806','capital_reduction_suspension','115/09/23','115/10/02','official',{})
        self.assertEqual(len(tradable.active_events(company,[e],'2026-10-01')[0]),0)
        self.assertEqual(len(tradable.active_events(company,[e],'2026-10-02')[0]),1)

    def test_relisted_symbol_not_removed_by_old_termination(self):
        company=[{'ex':'tse','code':'1234','listing_date':'20200101'}]
        e=tradable.event('tse','1234','delisted','108/01/01',None,'official',{})
        self.assertEqual(len(tradable.active_events(company,[e],'2026-10-02')[0]),1)

    def test_historical_same_code_different_security_not_removed(self):
        company=[{'ex':'tse','code':'2301','name':'光寶科','company_name':'光寶科技股份有限公司'}]
        e=tradable.event('tse','2301','delisted','091/04/01',None,'official',{})
        e['security_name']='光寶'
        self.assertEqual(len(tradable.active_events(company,[e],'2026-10-02')[0]),1)

    def test_report_signal_gate_stays_closed(self):
        rs=[record('13:25:20','13:25:20'),record('13:25:30','13:25:30'),record('13:25:40','13:25:40')]
        with tempfile.TemporaryDirectory() as directory:
            out=f.write_report('2026-10-02',[],rs,rs[0]['symbols'],{'checks':[]},Path(directory))
            self.assertEqual(out['signals']['status'],'NOT_GENERATED')
            self.assertEqual(out['both_validated_count'],0)


if __name__=='__main__':unittest.main()
