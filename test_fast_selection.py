"""Fast-path safety and incremental evidence tests, without live MIS requests."""
import copy
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import fast_capture_journal as journal
import fast_gate
import fast_selection as fast
import fast_sources
import capture_pre_boundary
import probe
from test_close_research import DAY, ref
from test_convergence import SYMBOL


def records():
    return [ref('pre_reference_A',trade='13:24:59',price='100',volume='10'),
            ref('pre_reference_B',trade='13:24:59',price='100',volume='10'),
            ref('close_reference_A'),ref('close_reference_B')]


class FastSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.engine=fast.Engine(DAY,[SYMBOL],self.temp.name)

    def test_incremental_candidate_is_visible_before_other_batches(self):
        for record in records()[:3]:self.engine.feed(record)
        view=self.engine.view()
        self.assertEqual(view['research_count'],1);self.assertEqual(view['verified_count'],0)
        self.assertEqual(view['metrics']['first_candidate_evidence_available_at'],records()[2]['received_at'])
        self.assertFalse(view['rows'][0]['checks']['close_research_converged'])

    def test_identical_record_is_not_reprocessed(self):
        self.engine.feed(records()[0]);self.engine.feed(records()[0])
        self.assertEqual(self.engine.batch_count,1)

    def test_wrong_observation_date_rejected(self):
        record=records()[0];record['received_at']='2026-10-07T13:27:00+08:00'
        with self.assertRaisesRegex(ValueError,'OBSERVATION_DATE'):self.engine.feed(record)

    def test_late_reference_prices_never_replace_pre_cutoff(self):
        for clock in ('13:25:00','13:27:00','13:29:59'):
            with self.subTest(clock=clock):
                e=fast.Engine(DAY,[SYMBOL],self.temp.name)
                for record in records():
                    if record['phase'].startswith('pre'):record['response']['msgArray'][0]['trade']['t']=clock
                    e.feed(record)
                self.assertEqual(e.view()['research_count'],0)

    def test_official_matching_and_supplied_validated_flag_cannot_promote(self):
        for record in records():self.engine.feed(record)
        self.engine.crosscheck(('tse','2330'),{'validated':True,'status':'VERIFIED','official_close':'104'},DAY+'T13:36:00+08:00')
        self.assertEqual(self.engine.view()['verified_count'],0)
        self.assertEqual(self.engine.view()['rows'][0]['verification_status'],'RESEARCH_ONLY')

    def test_fresh_conflict_retracts_old_candidate(self):
        for record in records():self.engine.feed(record)
        self.engine.feed(ref('close_reference_C',price='105'))
        self.assertEqual(self.engine.view()['research_count'],0)
        self.assertEqual(self.engine.view()['retracted'][0]['verification_status'],'RETRACTED')

    def test_single_stock_failure_does_not_block_another_candidate(self):
        missing={**SYMBOL,'code':'2317'};e=fast.Engine(DAY,[SYMBOL,missing],self.temp.name)
        for record in records():e.feed(record)
        self.assertEqual(e.view()['research_count'],1)
        self.assertEqual(e.view()['pending_or_unproven'],2)
        self.assertEqual(e.view()['universe_count'],2)

    def test_stale_single_close_is_not_candidate(self):
        for record in records()[:2]:self.engine.feed(record)
        self.engine.feed(ref('close_reference_A',server='13:24:55'))
        self.assertEqual(self.engine.view()['research_count'],0)

    def test_no_new_pre_trade_is_research_eligible_with_consistency(self):
        for record in records():
            if record['phase'].startswith('pre'):record['response']['msgArray'][0]['trade']['t']='12:00:00'
            self.engine.feed(record)
        self.assertEqual(self.engine.view()['research_count'],1)
        self.assertEqual(self.engine.view()['rows'][0]['P_before_trade_time'],'12:00:00')

    def test_exact_positive_and_negative_three_percent(self):
        for price in ('103','97'):
            e=fast.Engine(DAY,[SYMBOL],self.temp.name)
            for record in records():
                if record['phase'].startswith('close'):record['response']['msgArray'][0]['trade']['z']=price
                e.feed(record)
            self.assertEqual(e.view()['research_count'],1)

    def test_below_three_percent_is_excluded(self):
        for record in records():
            if record['phase'].startswith('close'):record['response']['msgArray'][0]['trade']['z']='102.9999'
            self.engine.feed(record)
        self.assertEqual(self.engine.view()['research_count'],0)

    def test_delayed_1333_close_remains_research(self):
        for record in records()+[ref('close_reference_C')]:
            if record['phase'].startswith('close'):record['response']['msgArray'][0]['trade']['t']='13:33:00'
            self.engine.feed(record)
        self.assertEqual(self.engine.view()['research_count'],1)
        self.assertEqual(self.engine.view()['verified_count'],0)

    def test_local_publication_is_not_historical_publication(self):
        for record in records():self.engine.feed(record)
        self.engine.publish_local();metrics=self.engine.view()['metrics']
        self.assertIsNotNone(metrics['first_local_publication_at'])
        self.assertIsNone(metrics['first_public_observed_at'])
        self.assertIsNone(metrics['close_to_first_verified_seconds'])
        self.assertFalse(metrics['historical_publication_proven'])

    def test_production_output_forbidden(self):
        for name in ('docs','state','.github','reports/2026-10-14'):
            with self.assertRaisesRegex(ValueError,'ISOLATED'):fast.safe_output(Path(fast.__file__).parent/name/'danger')

    def test_watch_cannot_backfill_a_past_date(self):
        with self.assertRaisesRegex(ValueError,'DEADLINE_ALREADY_PASSED'):
            fast.watch(Path(self.temp.name)/'none',[], '2020-01-01',self.temp.name)


class DurableJournalTests(unittest.TestCase):
    def test_fast_batch_is_saved_before_slow_earlier_batch_finishes(self):
        with tempfile.TemporaryDirectory() as d:
            release=threading.Event();saved=[]
            def fetch(symbols,*args):
                if symbols[0]['code']=='2330':
                    if not release.wait(2):raise AssertionError('fast batch was blocked behind slow batch')
                return probe.FetchResult(probe.iso(),probe.iso(),1,200,0,None,None,{'msgArray':[]})
            def append(row):
                saved.append(row['batch_no']);release.set()
            with patch.dict('os.environ',{'MIS_FAST_JOURNAL_DIR':d}),patch.object(probe,'BATCH_SIZE',1),patch.object(probe,'fetch_mis',side_effect=fetch),patch.object(journal.Journal,'append',side_effect=append):
                result=probe.snapshot('close_reference_A',probe.now_tpe(),[SYMBOL,{**SYMBOL,'code':'2317'}],Path(d))
            self.assertEqual(saved,[2,1]);self.assertEqual([r['batch_no'] for r in result['records']],[1,2])

    def test_saved_timestamp_taken_after_raw_fsync_and_hash_verified(self):
        with tempfile.TemporaryDirectory() as d:
            record=records()[0];saved=DAY+'T13:27:10+08:00'
            event=journal.Journal(d,clock=lambda:saved).append(record)
            self.assertEqual(journal.verify(event,d)['record'],record)
            raw=Path(d)/event['raw_file'];raw.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):journal.verify(event,d)

    def test_future_receive_time_cannot_be_marked_as_saved(self):
        with tempfile.TemporaryDirectory() as d:
            event=journal.Journal(d,clock=lambda:DAY+'T13:24:50+08:00').append(records()[0])
            with self.assertRaisesRegex(ValueError,'DURABILITY_TIME'):journal.verify(event,d)

    def test_pre_save_does_not_prove_last_tick_completeness(self):
        with tempfile.TemporaryDirectory() as d:
            e=fast.Engine(DAY,[SYMBOL],d)
            record=ref('pre_reference_A',server='13:24:59',trade='13:24:59',price='100')
            record.update(requested_at=DAY+'T13:24:59+08:00',received_at=DAY+'T13:24:59.5+08:00')
            e.feed(record,DAY+'T13:24:59.8+08:00')
            for r in records():e.feed(r)
            row=e.view()['rows'][0]
            self.assertTrue(row['checks']['pre_durably_saved_before_1325'])
            self.assertFalse(row['checks']['pre_last_trade_independently_proven'])
            self.assertFalse(row['validated'])

    def test_boundary_saver_refuses_late_start(self):
        with tempfile.TemporaryDirectory() as d,patch.object(probe,'now_tpe',return_value=probe.target(DAY,'13:25:01')):
            with self.assertRaisesRegex(ValueError,'NO_LATE_START'):capture_pre_boundary.collect(DAY,[SYMBOL],d)


class SourceTests(unittest.TestCase):
    def response(self,raw):
        obj=io.BytesIO(raw);obj.status=200;return obj

    def test_public_ordinary_auto_form_followed_once(self):
        form=b"<form><input name='is_check' value='1'></form>";seen=[]
        def opener(req,timeout):
            seen.append(req.get_method());return self.response(form if len(seen)==1 else b'<title>(2330)</title>')
        with tempfile.TemporaryDirectory() as d:r=fast_sources.check_pchome(SYMBOL,d,opener)
        self.assertEqual(seen,['GET','POST']);self.assertFalse(r['validated'])
        self.assertEqual(len(r['attempts']),2)

    def test_optional_fugle_key_absence_performs_no_request(self):
        with patch.dict('os.environ',{},clear=True),patch.object(fast_sources.urllib.request,'urlopen') as get:
            r=fast_sources.check_fugle(SYMBOL,'unused')
        get.assert_not_called();self.assertEqual(r['status'],'NOT_CONFIGURED')

    def test_fugle_raw_preserved_but_api_success_not_validation(self):
        seen=[]
        def opener(req,timeout):
            seen.append(req.full_url)
            return self.response(b'{"date":"2026-10-08","symbol":"2330","isClose":true}')
        with tempfile.TemporaryDirectory() as d,patch.object(fast_sources.time,'sleep'):
            r=fast_sources.check_fugle(SYMBOL,d,'fake-key',opener)
            self.assertEqual(len(list(Path(d).glob('*.json'))),2)
        self.assertIn('isTrial=false',seen[1]);self.assertFalse(r['validated'])
        self.assertNotIn('fake-key',json.dumps(r))

    def test_rate_limit_stops_candidate_queue(self):
        rows=[{**SYMBOL,'code':str(1000+i)} for i in range(20)]
        def fetch(row,output):return {'http_status':429}
        r=fast_sources.candidate_checks(rows,'.',fetch=fetch,wait=lambda _:None)
        self.assertEqual(len(r),1)

    def test_checks_are_candidate_only_and_bounded(self):
        rows=[{**SYMBOL,'code':str(1000+i)} for i in range(20)]
        r=fast_sources.candidate_checks(rows,'.',fetch=lambda *_:{'http_status':200},wait=lambda _:None,max_requests=3)
        self.assertEqual(len(r),3)

    def test_slow_secondary_source_never_blocks_feed(self):
        with tempfile.TemporaryDirectory() as d:
            e=fast.Engine(DAY,[SYMBOL],d)
            for r in records()[:3]:e.feed(r)
            released=threading.Event()
            def fetch(*args):released.wait(5);return {'status':'OBSERVATION_ONLY'}
            checks=fast.CandidateChecks(e,fetch=fetch)
            try:
                checks.tick(DAY+'T13:35:00+08:00')
                e.feed(records()[3]);e.publish_local()
                self.assertFalse(checks.future[1].done())
                self.assertEqual(e.view()['research_count'],1)
            finally:released.set();checks.close()


if __name__=='__main__':unittest.main()
