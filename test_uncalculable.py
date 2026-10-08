import copy
import gzip
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import analyze_uncalculable as audit
import convergence as c
import freshness as f
import probe
from test_freshness import record


def ref(phase, clock, server=None, trade='13:20:00', price='100', volume='1'):
    row = record(clock, server or clock, trade, price, volume)
    row = json.loads(json.dumps(row).replace('2026-10-02', audit.DATE).replace('20261002', '20261008'))
    row.update(phase=phase, planned_at=audit.DATE+'T'+clock+'+08:00')
    return row


def pair(a=None, b=None, *extra):
    records = [a or ref('pre_reference_A', '13:27:00'), b or ref('pre_reference_B', '13:28:15'), *extra]
    return c.pair(f.observations(records, audit.DATE), audit.DATE, 'pre')


class SparseEvidenceTests(unittest.TestCase):
    def test_long_unchanged_real_trade_keeps_pre_baseline(self):
        self.assertTrue(pair()['converged'])
        self.assertEqual(pair()['A']['trade_z'], '100')

    def test_no_daily_trade_never_uses_simulation(self):
        a, b = ref('pre_reference_A', '13:27:00'), ref('pre_reference_B', '13:28:15')
        for r in (a, b):
            item = r['response']['msgArray'][0]; item.pop('trade'); item.update(v='0', pz='104', z='105')
        self.assertFalse(pair(a, b)['converged'])
        self.assertEqual(audit.identity_diagnostic(a['response']['msgArray'][0]), 'NO_NESTED_TRADE_ZERO_REPORTED_VOLUME')

    def test_missing_time_never_recovers_from_outer_time(self):
        a = ref('pre_reference_A', '13:27:00'); a['response']['msgArray'][0]['trade'].pop('t')
        self.assertFalse(pair(a)['converged'])
        self.assertEqual(audit.identity_diagnostic(a['response']['msgArray'][0]), 'NESTED_TRADE_TIME_MISSING_OR_INVALID')

    def test_missing_price_never_recovers_from_outer_price(self):
        a = ref('pre_reference_A', '13:27:00'); a['response']['msgArray'][0]['trade'].pop('z')
        self.assertFalse(pair(a)['converged'])
        self.assertEqual(audit.identity_diagnostic(a['response']['msgArray'][0]), 'NESTED_TRADE_PRICE_MISSING_OR_INVALID')

    def test_nested_price_differs_from_simulation(self):
        self.assertEqual(pair()['A']['trade_z'], '100')  # fixture pz=2510, outer z='-'

    def test_stale_AB_not_recoverable(self):
        self.assertFalse(pair(ref('pre_reference_A','13:27:00','13:26:30'), ref('pre_reference_B','13:28:15','13:27:00'))['converged'])

    def test_inconsistent_trade_identity_not_converged(self):
        self.assertFalse(pair(b=ref('pre_reference_B','13:28:15',trade='13:21:00'))['converged'])

    def test_server_regression_rejected(self):
        out = pair(None, None, ref('pre_targeted_retry','13:28:20','13:28:14'))
        self.assertFalse(out['converged']); self.assertEqual(out['reason'], 'server_time_regression')

    def test_two_fresh_retries_can_recover_real_identity(self):
        b = ref('pre_reference_B','13:28:15',volume='2')
        out = pair(None, b, ref('pre_targeted_retry','13:28:20',volume='2'))
        self.assertTrue(out['converged'])

    def test_retry_without_trade_stays_unknown(self):
        r = ref('pre_targeted_retry','13:29:25'); r['response']['msgArray'][0].pop('trade')
        self.assertFalse(pair(None, None, r)['converged'])

    def test_delayed_trade_not_pre_baseline(self):
        self.assertFalse(pair(b=ref('pre_reference_B','13:28:15',trade='13:33:00'))['converged'])

    def test_wrong_date_rejected(self):
        b = ref('pre_reference_B','13:28:15'); b['response']['msgArray'][0]['d']='20261007'
        self.assertFalse(pair(b=b)['converged'])

    def test_late_or_undated_record_never_enters_asof_replay(self):
        ontime=ref('pre_reference_A','13:27:00')
        late=ref('pre_targeted_retry','14:50:00')
        undated=copy.deepcopy(ontime);undated.pop('received_at')
        self.assertEqual(audit.as_of_records([ontime,late,undated],audit.AS_OF),[ontime])

    def test_malformed_asof_rejected(self):
        with self.assertRaises(ValueError):audit.as_of_records([], '2026-10-08T13:35:00')

    def test_missing_and_null_are_distinct(self):
        self.assertEqual(audit.field({},'trade','z'),'MISSING')
        self.assertIsNone(audit.field({'trade':{'z':None}},'trade','z'))

    def test_terminal_no_request_preserves_actual_prior_timeout(self):
        r=ref('pre_targeted_retry','13:28:58');r.update(response=None,error='CAPTURE_DEADLINE_NO_REQUEST',http_status=None)
        r['attempts']=[{'requested_at':audit.DATE+'T13:28:57.201+08:00','received_at':audit.DATE+'T13:28:58.004+08:00',
                        'error':'RESPONSE_AFTER_CAPTURE_DEADLINE:URLError:timeout','http_status':None,'response':None}]
        timeline=audit.record_timeline(r,r['symbols'][0],{},'raw',1,'hash')
        self.assertEqual(len(timeline),2)
        self.assertFalse(timeline[0]['HTTP_request_sent']);self.assertTrue(timeline[1]['HTTP_request_sent'])
        self.assertEqual(timeline[1]['request_started_at'],r['attempts'][0]['requested_at'])

    def test_actual_oct8_25_unknown_and_seven_exactly_unchanged_offline(self):
        path=Path(__file__).parent/'fixtures/oct8_sparse_evidence.json.gz'
        before=path.read_bytes();fixture=json.loads(gzip.decompress(before))
        with patch.object(probe,'get_bytes',side_effect=AssertionError('No HTTP allowed in replay')):
            report=audit.replay(audit.DATE,[{'records':fixture['records']}],[],fixture['universe'],audit.AS_OF)
        actual=c.research_candidates(report)['candidates']
        self.assertEqual(actual,fixture['candidates'])
        unknown=[s for s in report['securities'] if not s['research_calculable']]
        self.assertEqual({s['code'] for s in unknown},set(audit.CODES))
        self.assertEqual(report['research_calculable_count'],7)
        for s in unknown:
            self.assertIsNone(s['p_before']);self.assertFalse(s['pre_pair_evidence']['converged'])
        self.assertEqual(path.read_bytes(),before)

    def test_actual_25_primary_causes_official_diagnostic_only(self):
        fixture=json.loads(gzip.decompress((Path(__file__).parent/'fixtures/oct8_sparse_evidence.json.gz').read_bytes()))
        report=audit.replay(audit.DATE,[{'records':fixture['records']}],[],fixture['universe'],audit.AS_OF)
        from collections import Counter
        counts=Counter()
        for symbol in fixture['universe']:
            if symbol['code'] not in audit.CODES:continue
            timeline=[]
            for r in fixture['records']:
                if symbol in r['symbols']:timeline+=audit.record_timeline(r,symbol,{},'fixture',1,'derived')
            s=next(s for s in report['securities'] if s['code']==symbol['code'])
            result=audit.classify_symbol(symbol,timeline,s,fixture['official'][symbol['ex']][symbol['code']])
            counts[result['primary_root_cause']]+=1
            self.assertTrue(result['all_saved_pre_responses_missing_nested_trade_and_v_zero'])
            self.assertGreaterEqual(result['fresh_pre_observations'],2)
            self.assertFalse(result['deadline_primary_cause'])
        self.assertEqual(counts,{'OFFICIAL_ZERO_DAILY_ACTIVITY_NO_PRE_TRADE':9,
            'NO_OBSERVED_PRE_TRADE_FIRST_SAVED_TRADE_AT_CLOSE':3,'DAILY_ACTIVITY_WITHOUT_REGULAR_SESSION_TRADE_EVIDENCE':13})


if __name__=='__main__':unittest.main()
