"""Offline, synthetic transport/clock tests plus read-only saved publication checks."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import candidate_publication
import dispatch_safety_driver
import probe
import run_control as control
import schedule_health as health

DATE = '2026-11-06'
CALENDAR = {'year': 2026, 'closed_dates': ['2026-10-26']}


def clock(time='13:41:00', day=DATE):
    return probe.target(day, time)


def run(mode='live', event='workflow_dispatch', created='2026-11-06T05:00:33Z', status='in_progress'):
    return {'id': 123, 'event': event, 'path': health.WORKFLOW, 'head_branch': 'main',
            'created_at': created, 'display_title': 'MIS '+mode+' / manual / 200',
            'status': status, 'conclusion': None}


def listed(*runs):
    return {'total_count': len(runs), 'workflow_runs': list(runs)}


def zero_payload():
    payload = {'trade_date': DATE, 'generated_at': DATE+'T13:34:00+08:00',
               'capture_run_id': '123', 'source_artifact': 'mis-probe-123',
               'status': 'RESEARCH_ONLY', 'validated': False, 'completion_status': 'COMPLETE',
               'coverage': {'tradable_universe': 1975, 'research_calculable': 1941, 'unknown': 34},
               'candidate_list': [], 'candidate_count': 0}
    payload['price_fingerprint'] = candidate_publication.fingerprint(payload)
    return payload


class ScheduleHealthTests(unittest.TestCase):
    def summary(self, live=None, candidates=None, runs=None, now=None, calendar=None):
        return health.summarize(now or clock(), calendar or CALENDAR, live or {},
                                candidates or {}, listed() if runs is None else runs)

    def test_missing_primary_is_not_zero_candidates(self):
        result = self.summary()
        self.assertEqual(result['state'], 'NOT_STARTED')
        self.assertEqual(result['trigger_status'], 'NO_LIVE_RUN_BY_1302')
        self.assertIsNone(result['candidate_count'])

    def test_grace_period_includes_observed_33_second_external_jitter(self):
        self.assertEqual(self.summary(now=clock('13:01:00'))['state'], 'WAITING_FOR_1302')
        self.assertEqual(self.summary(runs=listed(run()))['trigger_status'], 'RUN_CREATED_BY_1302')

    def test_native_late_creation_does_not_fulfill_primary(self):
        result = self.summary(runs=listed(run(event='schedule', created='2026-11-06T11:35:03Z', status='completed')),
                              now=clock('20:00:00'))
        self.assertEqual(result['trigger_status'], 'NO_LIVE_RUN_BY_1302')

    def test_workflow_queue_and_started_are_not_mis_success(self):
        self.assertEqual(self.summary(runs=listed(run(status='queued')))['state'], 'WORKFLOW_QUEUED')
        self.assertEqual(self.summary(runs=listed(run()))['state'], 'WORKFLOW_STARTED_MIS_PENDING')

    def test_armed_and_actually_capturing_are_separate(self):
        live = {'trade_date': DATE, 'status': 'running', 'phase': 'starting'}
        self.assertEqual(self.summary(live=live)['state'], 'RUNNER_ARMED_MIS_PENDING')
        live['preclose_captured'] = True
        self.assertEqual(self.summary(live=live)['state'], 'CAPTURING')

    def test_completed_capture_pending_or_failed_publication(self):
        live = {'trade_date': DATE, 'phase': 'completed', 'capture_outcome': 'CAPTURE_SUCCESS'}
        self.assertEqual(self.summary(live=live)['state'], 'CAPTURE_COMPLETED_PUBLICATION_PENDING')
        live['candidate_publication'] = {'status': 'FAILED'}
        self.assertEqual(self.summary(live=live)['state'], 'PUBLICATION_FAILED')

    def test_zero_is_only_a_real_valid_saved_publication(self):
        result = self.summary(candidates=zero_payload())
        self.assertEqual(result['state'], 'PUBLISHED_ZERO_CANDIDATES')
        self.assertEqual(result['candidate_count'], 0)
        broken = zero_payload(); broken['price_fingerprint'] = 'wrong'
        self.assertEqual(self.summary(candidates=broken)['state'], 'INVALID_OR_WRONG_DAY_PUBLICATION')

    def test_original_saved_oct19_and_nov3_publications_unchanged(self):
        for date in ('2026-10-19', '2026-11-03'):
            path = Path('state/candidates/'+date+'.json'); before = path.read_bytes()
            payload = json.loads(before)
            result = self.summary(candidates=payload, now=clock('23:59:59', date))
            self.assertEqual(result['state'], 'PUBLISHED_CANDIDATES')
            self.assertEqual(result['candidate_count'], payload['candidate_count'])
            self.assertEqual(path.read_bytes(), before)

    def test_yesterday_future_and_conflicting_capture_never_pass(self):
        payload = zero_payload(); payload['generated_at'] = DATE+'T23:00:00+08:00'
        payload['price_fingerprint'] = candidate_publication.fingerprint(payload)
        self.assertEqual(self.summary(candidates=payload)['state'], 'INVALID_OR_WRONG_DAY_PUBLICATION')
        self.assertEqual(self.summary(candidates=zero_payload(), now=clock(day='2026-11-09'))['state'],
                         'INVALID_OR_WRONG_DAY_PUBLICATION')
        self.assertEqual(self.summary(candidates=zero_payload(), live={'trade_date': DATE, 'run_id': '456'})['state'],
                         'INVALID_OR_WRONG_DAY_PUBLICATION')

    def test_failed_capture_stays_failed_beside_existing_publication(self):
        self.assertEqual(self.summary(candidates=zero_payload(), live={
            'trade_date': DATE, 'capture_outcome': 'CAPTURE_FAILED'})['state'], 'CAPTURE_FAILED')

    def test_weekend_holiday_and_unknown_calendar_are_not_missing(self):
        for day in ('2026-11-07', '2026-11-08', '2026-10-26'):
            self.assertEqual(self.summary(now=clock(day=day))['state'], 'NONTRADING_DAY')
        self.assertEqual(self.summary(calendar={'year': 2025})['state'], 'UNKNOWN_CALENDAR')

    def test_dry_safety_other_workflow_branch_and_future_runs_do_not_count(self):
        wrong = run(); wrong['path'] = '.github/workflows/index-events.yml'
        branch = run(); branch['head_branch'] = 'test'
        result = self.summary(runs=listed(run(mode='dry-run'), run(mode='dispatch-safety'), wrong, branch,
                                         run(created='2026-11-06T15:00:00Z')))
        self.assertEqual(result['state'], 'NOT_STARTED')

    def test_unavailable_malformed_or_truncated_run_list_is_unknown(self):
        for runs in ({}, {'total_count': 101, 'workflow_runs': []}):
            self.assertEqual(self.summary(runs=runs)['trigger_status'], 'UNKNOWN_RUN_LOOKUP')
        self.assertEqual(health.summarize(clock(), CALENDAR, {}, {}, None)['trigger_status'], 'UNKNOWN_RUN_LOOKUP')

    def test_run_lookup_uses_taipei_day_in_utc_bounds(self):
        query = health.run_query(clock())
        self.assertIn('2026-11-05T16:00:00Z..2026-11-06T05:41:00Z', query)

    def test_monitor_transport_errors_preserve_artifact_and_never_touch_mis(self):
        for code in (401, 403, 404, 422):
            error = HTTPError('https://api.github.com', code, 'secret-must-not-be-logged', {}, None)
            with tempfile.TemporaryDirectory() as folder, patch.object(probe, 'now_tpe', return_value=clock()), \
                 patch.object(control, 'receipt', side_effect=error), \
                 patch.object(control, 'read_state', side_effect=error), patch.object(control, 'api', side_effect=error), \
                 patch.object(control, 'merge_state', side_effect=error), patch.object(control, 'publish', side_effect=error), \
                 patch.object(probe, 'fetch_mis') as mis, patch.object(probe, 'live') as live:
                self.assertEqual(control.run('health', Path(folder)), 1)
                result = json.loads((Path(folder)/'health.json').read_text())
                self.assertEqual(result['health']['state'], 'UNKNOWN_CALENDAR')
                self.assertEqual(result['monitor_errors'][0]['http_status'], code)
                self.assertNotIn('secret-must-not-be-logged', json.dumps(result))
                mis.assert_not_called(); live.assert_not_called()

    def test_receipt_timeout_keeps_later_monitor_evidence_and_failed_exit(self):
        saved = {'state/calendars/2026.json': CALENDAR}
        def read(path): return copy.deepcopy(saved.get(path, {})), None
        with tempfile.TemporaryDirectory() as folder, patch.object(probe, 'now_tpe', return_value=clock()), \
             patch.object(control, 'receipt', side_effect=TimeoutError), patch.object(control, 'read_state', side_effect=read), \
             patch.object(control, 'api', return_value=listed()), patch.object(control, 'merge_state') as write, \
             patch.object(control, 'publish', side_effect=TimeoutError), patch.object(probe, 'fetch_mis') as mis:
            self.assertEqual(control.run('health', Path(folder)), 1)
            result = json.loads((Path(folder)/'health.json').read_text())
            self.assertEqual(result['health']['state'], 'NOT_STARTED')
            self.assertEqual([e['stage'] for e in result['monitor_errors']], ['execution_receipt', 'publish_status_issue'])
            self.assertTrue(any(c.args[0] == 'state/health/'+DATE+'.json' for c in write.call_args_list))
            mis.assert_not_called()

    def test_complete_claim_or_read_error_never_overwritten_by_missing_watchdog(self):
        for record in ({'trade_date': DATE, 'phase': 'completed', 'capture_outcome': 'CAPTURE_FAILED'}, None):
            def read(path):
                if path == 'state/calendars/2026.json': return CALENDAR, None
                if path == control.live_path(DATE):
                    if record is None: raise TimeoutError()
                    return record, 'sha'
                return {}, None
            with tempfile.TemporaryDirectory() as folder, patch.object(probe, 'now_tpe', return_value=clock()), \
                 patch.object(control, 'read_state', side_effect=read), patch.object(control, 'api', return_value=listed()), \
                 patch.object(control, 'merge_state') as write, patch.object(control, 'publish'):
                control.health(Path(folder))
                self.assertFalse(any(c.args[0] == control.live_path(DATE) for c in write.call_args_list))

    def test_http_204_without_created_run_times_out_in_original_safety_driver(self):
        with patch.object(dispatch_safety_driver.time, 'monotonic', side_effect=[0, 0, 301]), \
             patch.object(dispatch_safety_driver.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                dispatch_safety_driver.wait_for(lambda: [], bool)

    def test_corrupt_state_keeps_local_diagnostic_and_never_becomes_missing(self):
        def read(path): return (CALENDAR if 'calendars/' in path else []), None
        with tempfile.TemporaryDirectory() as folder, patch.object(probe, 'now_tpe', return_value=clock()), \
             patch.object(control, 'read_state', side_effect=read), patch.object(control, 'api', return_value=listed()), \
             patch.object(control, 'merge_state') as write, patch.object(control, 'publish'):
            self.assertEqual(control.health(Path(folder)), 1)
            result = json.loads((Path(folder)/'health.json').read_text())
            self.assertTrue(result['monitor_errors'])
            self.assertFalse(any(c.args[0] == control.live_path(DATE) for c in write.call_args_list))
        corrupt = zero_payload(); corrupt['candidate_list'] = [None]; corrupt['candidate_count'] = 1
        self.assertEqual(self.summary(candidates=corrupt)['state'], 'INVALID_OR_WRONG_DAY_PUBLICATION')


if __name__ == '__main__': unittest.main()
