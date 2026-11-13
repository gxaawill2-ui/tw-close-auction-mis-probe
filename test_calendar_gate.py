"""Offline synthetic failure tests; one separately recorded real annual response."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import probe
import run_control as c
import official_calendar_gate as gate

NOW=probe.target('2026-11-13','13:00:40')
RAW={'stat':'ok','queryYear':2026,'data':[['2026-01-01','休市',''],['2026-01-02','國曆新年開始交易日',''],['2026-02-11','農曆春節前最後交易日',''],['2026-10-26','補假','']]}
CACHE={'year':2026,'status':'OFFICIAL_ANNUAL_CALENDAR','source':gate.SOURCE+'?response=json&queryYear=115','verified_at':'2026-11-11T13:00:00+08:00','closed_dates':['2026-01-01','2026-10-26']}

class CalendarGateTests(unittest.TestCase):
    def test_current_date_selector_and_row_semantics(self):
        self.assertIn('date=20260101',gate.url(2026))
        self.assertNotIn('queryYear=',gate.url(2026))
        self.assertEqual(gate.closed_dates(RAW,2026),set(CACHE['closed_dates']))

    def test_wrong_year_or_bad_rows_fail_closed(self):
        variants=[{**RAW,'queryYear':2027},{**RAW,'queryYear':'2026'},{**RAW,'stat':'error'},{**RAW,'data':[]},{**RAW,'data':[['2027-01-01','休市']]},{**RAW,'data':[['2026-02-30','休市']]},{**RAW,'data':[['2026-01-01']]},{**RAW,'data':[['2026-01-01',None]]}]
        for d in variants:
            with self.subTest(d=d),self.assertRaises((ValueError,TypeError)):gate.closed_dates(d,2026)

    def test_cache_rejects_untrusted_stale_future_and_wrong_year(self):
        variants=[{}, {**CACHE,'year':2027},{**CACHE,'status':'UNKNOWN'},{**CACHE,'source':'https://example.com'},{**CACHE,'closed_dates':[]},{**CACHE,'closed_dates':['2027-01-01']},{**CACHE,'verified_at':'2026-11-01T13:00:00+08:00'},{**CACHE,'verified_at':'2026-11-14T13:00:00+08:00'},{**CACHE,'verified_at':'2026-11-11T13:00:00'}]
        for d in variants:
            with self.subTest(d=d),self.assertRaises((ValueError,TypeError,KeyError)):gate.cached_dates(d,NOW)

    def calendar(self,root,now=NOW):
        return c.calendar_state(now,Path(root))

    def test_live_valid_response_never_uses_cache(self):
        with tempfile.TemporaryDirectory() as root,patch.object(probe,'get_bytes',return_value=(200,json.dumps(RAW).encode())) as fetch,patch.object(c,'read_state') as read,patch.object(c,'merge_state') as write:
            result=self.calendar(root)
            self.assertTrue(result['is_trading_day']);read.assert_not_called()
            self.assertEqual(fetch.call_args.args,(gate.url(2026),6))
            self.assertEqual(write.call_count,2)
            self.assertTrue((Path(root)/'official_calendar.json').exists())

    def test_transport_retry_can_recover_without_cache(self):
        with tempfile.TemporaryDirectory() as root,patch.object(probe,'get_bytes',side_effect=[TimeoutError(),(200,json.dumps(RAW).encode())]) as fetch,patch.object(c,'read_state') as read,patch.object(c,'merge_state'):
            self.assertTrue(self.calendar(root)['is_trading_day']);self.assertEqual(fetch.call_count,2);read.assert_not_called()

    def test_cache_does_not_refresh_its_timestamp_or_overwrite_annual(self):
        for response in [TimeoutError(),(200,b''),(200,b'{}'),(503,b'{}'),(200,json.dumps({**RAW,'queryYear':2027}).encode())]:
            with self.subTest(response=response),tempfile.TemporaryDirectory() as root,patch.object(probe,'get_bytes',side_effect=response if isinstance(response,Exception) else None,return_value=response if not isinstance(response,Exception) else None) as fetch,patch.object(c,'read_state',return_value=(copy.deepcopy(CACHE),None)),patch.object(c,'merge_state') as write:
                result=self.calendar(root)
                self.assertEqual(result['verified_at'],CACHE['verified_at'])
                self.assertEqual(result['calendar_gate']['status'],'CACHED_OFFICIAL_CALENDAR')
                self.assertEqual(write.call_count,1);self.assertEqual(fetch.call_count,2)
                self.assertEqual(write.call_args.args[0],'state/calendar_latest.json')

    def test_weekend_holiday_and_cached_holiday_skip(self):
        for now in [probe.target('2026-11-14','13:00:00'),probe.target('2026-10-26','13:00:00')]:
            with tempfile.TemporaryDirectory() as root,patch.object(probe,'get_bytes',return_value=(200,json.dumps(RAW).encode())),patch.object(c,'merge_state'):
                self.assertFalse(self.calendar(root,now)['is_trading_day'])
        cache={**CACHE,'verified_at':'2026-10-25T13:00:00+08:00'}
        with tempfile.TemporaryDirectory() as root,patch.object(probe,'get_bytes',side_effect=TimeoutError()),patch.object(c,'read_state',return_value=(cache,None)),patch.object(c,'merge_state'):
            self.assertFalse(self.calendar(root,probe.target('2026-10-26','13:00:00'))['is_trading_day'])

    def test_new_valid_official_closure_overrides_cache(self):
        response=copy.deepcopy(RAW);response['data'].append(['2026-11-13','臨時休市',''])
        with tempfile.TemporaryDirectory() as root,patch.object(probe,'get_bytes',return_value=(200,json.dumps(response).encode())),patch.object(c,'read_state') as read,patch.object(c,'merge_state'):
            self.assertFalse(self.calendar(root)['is_trading_day']);read.assert_not_called()

    def test_missing_calendar_leaves_failure_evidence_without_mis(self):
        with tempfile.TemporaryDirectory() as root,patch.object(probe,'now_tpe',return_value=NOW),patch.object(c,'receipt'),patch.object(c,'read_state',return_value=({},None)),patch.object(c,'merge_state') as write,patch.object(c,'publish'),patch.object(probe,'get_bytes',side_effect=TimeoutError()),patch.object(probe,'live') as live,patch.object(probe,'fetch_mis') as mis,patch.dict('os.environ',{'GITHUB_RUN_ID':'calendar-test','RUNNER_STARTED_AT':NOW.isoformat()}):
            self.assertEqual(c.run('live',Path(root)),1)
            live.assert_not_called();mis.assert_not_called()
            summary=json.loads((Path(root)/'run_summary.json').read_text())
            self.assertEqual(summary['capture_outcome'],'CAPTURE_FAILED')
            self.assertFalse(summary['capture_blocked'])
            self.assertEqual(summary['candidate_publication']['status'],'NOT_PUBLISHED')
            self.assertTrue((Path(root)/'calendar_gate.json').exists())
            self.assertTrue((Path(root)/'controller_status.json').exists())
            self.assertTrue(list(Path(root).parent.glob('mis-probe-2026-11-13.zip')))
            self.assertEqual(write.call_args.args[1]['phase'],'calendar_gate_failed')

    def test_remote_write_failure_still_leaves_local_artifact(self):
        with tempfile.TemporaryDirectory() as root,patch.object(c,'read_state',return_value=({},None)),patch.object(c,'merge_state',side_effect=TimeoutError()),patch.object(c,'publish'):
            self.assertEqual(c.calendar_startup_failure(Path(root),'2026-11-13','test',NOW.isoformat()),1)
            self.assertEqual(json.loads((Path(root)/'controller_status.json').read_text())['status_errors'],['TimeoutError'])

    def test_failure_cannot_replace_completed_or_claimed_state(self):
        for state in [{'status':'success_raw_capture'},{'capture_claimed':True},{'capture_blocked':True}]:
            with tempfile.TemporaryDirectory() as root,patch.object(c,'read_state',return_value=(state,None)),patch.object(c,'merge_state') as write,patch.object(c,'publish'):
                c.calendar_startup_failure(Path(root),'2026-11-13','test',NOW.isoformat());write.assert_not_called()

    def test_atomic_failure_write_rechecks_new_capture_owner(self):
        with patch.object(c,'read_state',return_value=({'capture_claimed':True,'run_id':'new-owner'},'sha')),patch.object(c,'api') as write:
            result=c.merge_state('state/live/2026-11-13.json',{'status':'failed_calendar'})
            self.assertEqual(result['run_id'],'new-owner');write.assert_not_called()

    def test_real_saved_candidate_files_not_touched(self):
        import candidate_publication
        for day,count in [('2026-10-19',11),('2026-11-03',20)]:
            data=json.loads(Path('state/candidates/'+day+'.json').read_text())
            candidate_publication.validate(data,day)
            self.assertEqual(data['candidate_count'],count)

if __name__=='__main__':unittest.main()
