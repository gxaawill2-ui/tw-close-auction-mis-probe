import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime
import zipfile
import stage4_shadow as shadow
import stage4_observation as observation
import stage4_remote_watch as remote
from test_fast_selection import records
from test_convergence import SYMBOL
from test_close_research import DAY


class Stage4Tests(unittest.TestCase):
    def test_remote_watcher_rejects_historical_launch_without_network(self):
        with tempfile.TemporaryDirectory() as d,patch.object(remote,'state',side_effect=AssertionError('network')):
            with self.assertRaisesRegex(ValueError,'HISTORICAL_WATCH'):
                remote.watch('2000-01-01',d,clock=lambda:datetime.fromisoformat('2026-10-15T09:40:00+08:00'))

    def test_remote_read_paths_cannot_access_secrets_or_dispatch(self):
        for path in ('actions/workflows/1/dispatches','contents/../secrets','/contents/state/live.json'):
            with self.assertRaisesRegex(ValueError,'READ_PATH_NOT_ALLOWED'):remote.api(path)

    def test_remote_observer_uses_existing_capture_without_second_mis(self):
        at=datetime.fromisoformat('2026-10-15T13:35:00+08:00')
        def fake_api(path):
            return {'artifacts':[{'id':1,'name':'mis-probe-7'}]} if '/artifacts?' in path else {'workflow_runs':[]}
        body={'research_count':1,'verified_count':0,'provenance':{'first_verified_at':None}}
        with tempfile.TemporaryDirectory() as d,patch.object(remote,'state',return_value={'run_id':7}),patch.object(remote,'api',side_effect=fake_api),patch.object(remote,'download',return_value=(Path(d)/'capture.zip',{'received_at':at.isoformat(),'persisted_at':at.isoformat()})),patch.object(remote,'capture_path',side_effect=lambda p,_:p),patch.object(remote,'analyze',return_value=body),patch.object(shadow.probe,'fetch_mis',side_effect=AssertionError('MIS forbidden')):
            self.assertEqual(remote.watch('2026-10-15',d,clock=lambda:at,wait=lambda _:self.fail('should finish')),body)
            self.assertEqual(json.loads(Path(d,'first-capture-result.json').read_text())['source_run_id'],7)

    def test_artifact_inner_zip_is_not_confused_with_outer_digest(self):
        with tempfile.TemporaryDirectory() as d:
            inner=self.capture(d);outer=Path(d)/'outer.zip'
            with zipfile.ZipFile(outer,'w') as z:z.writestr('mis-probe-2026-10-15.zip',inner.read_bytes())
            derived=remote.capture_path(outer,Path(d));self.assertNotEqual(derived,outer)
            self.assertEqual(derived.read_bytes(),inner.read_bytes())
            self.assertTrue(Path(d,'inner-capture-receipt.json').exists())

    def test_isolated_workflow_has_no_schedule_or_write_permission(self):
        text=Path('.github/workflows/stage4-validation.yml').read_text()
        self.assertNotIn('schedule:',text);self.assertNotIn('contents: write',text);self.assertNotIn('secrets.',text)
        self.assertIn("github.ref == 'refs/heads/stage4/20261015-live-shadow'",text)
        self.assertNotIn('group: twse-mis-live',text);self.assertNotIn('python run_control.py',text)

    def test_preflight_rejects_another_day_without_network(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'CURRENT_DATE'):
                shadow.preflight('2000-01-01',d,opener=lambda *_:self.fail('network'),clock=lambda:datetime.fromisoformat('2026-10-15T09:40:00+08:00'))

    def test_company_metadata_never_claims_tradability(self):
        class Response(io.BytesIO):status=200
        rows=[{'code':str(x),'name':'test'} for x in range(1000,1400)]
        sources=(('TWSE','tse','https://example.test/metadata','code','name'),)
        with tempfile.TemporaryDirectory() as d,patch.object(shadow.probe,'UNIVERSE_SOURCES',sources):
            result=shadow.preflight('2026-10-15',d,opener=lambda *_,**__:Response(json.dumps(rows).encode()),clock=lambda:datetime.fromisoformat('2026-10-15T09:40:00+08:00'))
            self.assertEqual(result['company_count'],400);self.assertFalse(result['tradable_universe_verified'])
            check=result['checks'][0];self.assertLessEqual(check['received_at'],check['persisted_at'])

    def test_unavailable_metadata_is_not_empty_success(self):
        def fail(*_,**__):raise TimeoutError()
        with tempfile.TemporaryDirectory() as d:
            result=shadow.preflight('2026-10-15',d,opener=fail,clock=lambda:datetime.fromisoformat('2026-10-15T09:40:00+08:00'))
        self.assertEqual(result['status'],'INCOMPLETE');self.assertFalse(result['tradable_universe_verified'])

    def capture(self,d):
        path=Path(d)/'capture.zip'
        with zipfile.ZipFile(path,'w') as archive:
            for name,data in {'run_summary.json':json.dumps({'trade_date':DAY,'status':'partial'}),
                'universe.json':json.dumps([SYMBOL]),'preclose_raw.jsonl':'','probe_raw.jsonl':'',
                'close_raw.jsonl':'\n'.join(json.dumps(x) for x in records()),'delayed_close_raw.jsonl':''}.items():archive.writestr(name,data)
        return path

    def test_capture_date_rejects_wrong_day_instead_of_oct14_hardcode(self):
        with tempfile.TemporaryDirectory() as d:
            archive=self.capture(d)
            with self.assertRaisesRegex(ValueError,'TRADE_DATE_MISMATCH'):shadow.analyze(archive,'2026-10-15',Path(d)/'view')

    def test_capture_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):shadow.analyze(self.capture(d),DAY,Path(d)/'view',expected_sha256='wrong')

    def test_artifact_receive_save_cannot_be_backdated(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'RECEIVE_SAVE_TIME'):
                shadow.analyze(self.capture(d),DAY,Path(d)/'view',artifact_received_at=DAY+'T13:36:00+08:00',artifact_persisted_at=DAY+'T13:35:00+08:00')

    def test_import_time_is_distinct_from_original_candidate_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            at=DAY+'T13:39:00+08:00'
            result=shadow.analyze(self.capture(d),DAY,Path(d)/'view',clock=lambda:datetime.fromisoformat(at))
            self.assertEqual(result['verified_count'],0);self.assertEqual(result['research_count'],1)
            p=result['provenance'];self.assertEqual(p['first_research_program_observed_at'],at)
            self.assertNotEqual(p['first_research_program_observed_at'],p['first_research_event_evidence_at'])
            self.assertIsNone(p['runtime_original_raw_persisted_at']);self.assertIsNone(p['first_external_browser_observed_at'])

    def test_no_run_before_due_is_not_a_scheduler_failure(self):
        result=observation.classify({'workflow_runs':[]},'2026-10-15','2026-10-15T09:40:00+08:00')
        self.assertEqual(result['status'],'NOT_DUE');self.assertIsNone(result['research_candidates'])

    def test_future_capture_events_cannot_be_reported_as_already_available(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'AFTER_ANALYSIS_START'):
                shadow.analyze(self.capture(d),DAY,Path(d)/'view',clock=lambda:datetime.fromisoformat(DAY+'T09:40:00+08:00'))

    def test_success_does_not_prove_capture(self):
        run={'id':1,'path':'.github/workflows/twse-mis-probe.yml','head_branch':'main','event':'workflow_dispatch','display_title':'MIS live / manual / 1','created_at':'2026-10-15T05:00:00Z','status':'completed','conclusion':'success'}
        result=observation.classify({'workflow_runs':[run]},'2026-10-15','2026-10-15T13:35:00+08:00')
        self.assertEqual(len(result['matching_runs']),1);self.assertFalse(result['actual_capture_confirmed'])

    def test_wrong_branch_date_or_tests_not_todays_live(self):
        rows=[{'path':'.github/workflows/twse-mis-probe.yml','head_branch':'main','event':'push','display_title':'MIS tests / push','created_at':'2026-10-15T05:00:00Z'},
            {'path':'.github/workflows/twse-mis-probe.yml','head_branch':'stage4/test','event':'workflow_dispatch','display_title':'MIS live / manual / 1','created_at':'2026-10-15T05:00:00Z'}]
        result=observation.classify({'workflow_runs':rows},'2026-10-15','2026-10-15T13:35:00+08:00')
        self.assertEqual(result['status'],'NO_MATCHING_RUN_OBSERVED')
