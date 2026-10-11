import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import market_closing_volume as m
import market_closing_runner as runner

DATE = '2026-10-12'
ASOF = DATE+'T18:00:00+08:00'


def evidence(closing=200, total=1000):
    return {'market_scope': m.SCOPE, 'source_quality': 'VERIFIED_SAME_SCOPE', 'coverage_ratio': 1,
            'missing_stocks': [], 'closing_auction_turnover_twd': closing, 'daily_turnover_twd': total,
            'official_reconciliation': {'status': 'MATCH_SAME_SCOPE'},
            'source_evidence': [{'observed_at': DATE+'T17:00:00+08:00'}]}


def history(n=20):
    result = []
    for i in range(n):
        day = (datetime.fromisoformat(DATE)-timedelta(days=n-i)).date().isoformat()
        result.append({'trade_date': day, 'generated_at': day+'T18:00:00+08:00',
            **evidence(100), 'closing_turnover_share_pct': 10})
    return result


class MarketClosingTests(unittest.TestCase):
    def test_provisional_never_makes_formal_yes_or_no(self):
        for closing in (199, 200, 250):
            r = m.calculate(DATE, evidence(closing), history(), ASOF)
            self.assertIsNone(r['is_closing_volume_spike'])
            self.assertEqual(r['threshold_status'], 'PROVISIONAL')
            self.assertEqual(r['provisional_rule_result'], closing >= 200)

    def test_calibrated_synthetic_boundary_both_conditions(self):
        rule = {**m.THRESHOLD, 'status': 'CALIBRATED', 'calibration_evidence': 'SYNTHETIC_TEST_ONLY'}
        for closing, expected in ((199, False), (200, True), (300, True)):
            self.assertEqual(m.calculate(DATE, evidence(closing), history(), ASOF, threshold=rule)['is_closing_volume_spike'], expected)
        h = history()
        for r in h:
            r.update(closing_auction_turnover_twd=150, closing_turnover_share_pct=15)
        self.assertFalse(m.calculate(DATE, evidence(200), h, ASOF, threshold=rule)['is_closing_volume_spike'])

    def test_under20_is_unknown_even_with_complete_today(self):
        for count in (0, 1, 19):
            r = m.calculate(DATE, evidence(), history(count), ASOF)
            self.assertIsNone(r['historical_median_share_pct'])
            self.assertIsNone(r['provisional_rule_result'])

    def test_60_day_statistics_require60_same_scope_days(self):
        self.assertIsNone(m.calculate(DATE, evidence(), history(59), ASOF)['historical_p90_60_share_pct'])
        r = m.calculate(DATE, evidence(), history(60), ASOF)
        self.assertEqual(r['historical_median_60_share_pct'], 10)
        self.assertEqual(r['historical_p90_60_share_pct'], 10)
        self.assertEqual(r['historical_sample_count'], 20)

    def test_no_same_day_or_future_history(self):
        h = history(19)+[{**history(1)[0], 'trade_date': DATE}, {**history(1)[0], 'trade_date': '2026-10-13'}]
        self.assertEqual(m.calculate(DATE, evidence(), h, ASOF)['historical_sample_count'], 19)

    def test_later_correction_is_not_known_before_it_arrives(self):
        old = history(1)[0]
        corrected = {**old, 'generated_at': DATE+'T19:00:00+08:00', 'source_quality': 'UNVERIFIED', 'change_history': [old]}
        self.assertEqual(len(m.history_as_of([corrected], DATE, ASOF)), 1)
        self.assertEqual(len(m.history_as_of([corrected], DATE, DATE+'T20:00:00+08:00')), 0)

    def test_duplicate_days_not_independent_samples(self):
        h = history()
        self.assertEqual(m.calculate(DATE, evidence(), h+h, ASOF)['historical_sample_count'], 20)
        conflict = {**h[0], 'closing_turnover_share_pct': 11}
        self.assertEqual(len(m.history_as_of(h+[conflict], DATE, ASOF)), 19)

    def test_history_scope_mismatch_and_bad_figures_are_excluded(self):
        h = history()
        h[0]['market_scope'] = 'TWSE_ETF'
        h[1]['closing_turnover_share_pct'] = 40
        h[2]['daily_turnover_twd'] = 0
        self.assertEqual(len(m.history_as_of(h, DATE, ASOF)), 17)

    def test_missing_stocks_or_partial_coverage_never_yields_market_total(self):
        for patch_value in ({'coverage_ratio': .99}, {'missing_stocks': ['2330']}, {'official_reconciliation': {'status': 'MI_INDEX_MIXED_SCOPE'}}, {'market_scope': 'TPEx'}):
            r = m.calculate(DATE, {**evidence(), **patch_value}, history(), ASOF)
            self.assertIsNone(r['closing_auction_turnover_twd'])
            self.assertIsNone(r['is_closing_volume_spike'])

    def test_invalid_turnover_zero_denominator_negative_nan_infinity(self):
        for closing, total in ((1, 0), (-1, 100), ('NaN', 100), (101, 100), ('Infinity', 100)):
            r = m.calculate(DATE, evidence(closing, total), history(), ASOF)
            self.assertIsNone(r['is_closing_volume_spike'])
            self.assertIsNone(r['closing_turnover_share_pct'])

    def test_zero_closing_with_verified_positive_denominator_can_be_observed(self):
        r = m.calculate(DATE, evidence(0), history(), ASOF)
        self.assertEqual(r['closing_turnover_share_pct'], 0)
        self.assertFalse(r['provisional_rule_result'])
        self.assertIsNone(r['is_closing_volume_spike'])

    def test_preclose_and_holiday_no_false_negative(self):
        self.assertIsNone(m.calculate(DATE, evidence(), history(), DATE+'T13:25:00+08:00')['is_closing_volume_spike'])
        self.assertEqual(m.calculate(DATE, {}, [], ASOF, 'HOLIDAY')['status'], 'HOLIDAY')

    def test_source_observed_after_asof_cannot_leak(self):
        e = evidence()
        e['source_evidence'][0]['observed_at'] = DATE+'T19:00:00+08:00'
        self.assertIsNone(m.calculate(DATE, e, history(), ASOF)['closing_turnover_share_pct'])

    def test_wrong_future_trade_date_rejected(self):
        with self.assertRaises(ValueError):
            m.calculate('2026-10-13', {}, [], ASOF)

    def test_older_update_refused_and_history_preserved(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            first = m.calculate(DATE, {}, [], ASOF)
            m.save(root, first)
            later = m.calculate(DATE, {}, [], DATE+'T19:00:00+08:00')
            m.save(root, later)
            stored = json.loads((root/'state/market-closing-volume'/f'{DATE}.json').read_text())
            self.assertEqual(stored['change_history'][0]['generated_at'], ASOF)
            with self.assertRaises(ValueError):
                m.save(root, first)

    def test_failed_capture_preserves_previous_and_records_failure(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            now = datetime.now(m.TZ)
            day = now.date().isoformat()
            cal = root/'state/calendars'/f'{now.year}.json'
            cal.parent.mkdir(parents=True)
            # No calendar proof: force source failure without any network.
            prior = m.calculate(day, {}, [], now.isoformat())
            m.save(root, prior)
            original = (root/'state/market-closing-volume'/f'{day}.json').read_bytes()
            self.assertEqual(runner.run(root), 2)
            self.assertEqual(original, (root/'state/market-closing-volume'/f'{day}.json').read_bytes())
            health = json.loads((root/'state/market-closing-volume/source-health.json').read_text())
            self.assertEqual(health['result'], 'FAILED')

    def test_immutable_oct8_candidate_bytes(self):
        self.assertEqual(hashlib.sha256(Path('state/candidates/2026-10-08.json').read_bytes()).hexdigest(), '794cdb1749a7318612fad5003bceb47b126b5d03a8cbda16abf14332954c111b')

    def test_new_workflow_never_dispatches_or_captures_mis(self):
        text = Path('.github/workflows/market-closing-volume.yml').read_text()
        self.assertNotIn('workflow_run:', text)
        self.assertNotIn('workflow_dispatch/', text)
        self.assertNotIn('run_control.py', text)
        self.assertNotIn('probe.py', text)
        self.assertIn('git add state/market-closing-volume', text)
        self.assertIn("cron: '5 7,10 * * *'", text)


if __name__ == '__main__':
    unittest.main()
