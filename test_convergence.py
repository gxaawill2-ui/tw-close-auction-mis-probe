import copy
import io
import json
import tempfile
import unittest
import zipfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import convergence as c
import freshness as f
import official_quotes
import official_retry
import probe
from test_freshness import record

DATE = '2026-10-02'
SYMBOL = {'ex': 'tse', 'code': '2330', 'market': 'TWSE', 'name': '台積電'}


def reference(phase, request=None, server=None, price='100', trade='13:24:59', volume='10'):
    clock = request or c.REFERENCE_TIMES.get(phase, '13:28:30')
    row = record(clock, server or clock, trade, price, volume)
    row['phase'] = phase
    row['planned_at'] = DATE+'T'+c.REFERENCE_TIMES.get(phase, clock)+'.000+08:00'
    row['batch_no'] = 1
    return row


def rows(*records):
    return f.observations(records, DATE)


def all_references():
    return [reference('pre_reference_A'), reference('pre_reference_B'),
            reference('close_reference_A', price='104', trade='13:30:00', volume='20'),
            reference('close_reference_B', price='104', trade='13:30:00', volume='20')]


class ConvergenceTests(unittest.TestCase):
    def test_dual_equal_is_candidate_never_validated(self):
        out = c.pair(rows(reference('pre_reference_A'), reference('pre_reference_B')), DATE, 'pre')
        self.assertTrue(out['converged'])
        self.assertEqual(out['status'], 'p_before_converged_candidate')
        self.assertFalse(out['validated'])

    def test_stale_cache_and_unchanged_price_cannot_converge(self):
        a, b = reference('pre_reference_A'), reference('pre_reference_B', server='13:27:00')
        out = c.pair(rows(a, b), DATE, 'pre')
        self.assertFalse(out['converged']); self.assertEqual(out['reason'], 'stale_cache')

    def test_regression_breaks_stable_pair_and_needs_two_new_fresh_observations(self):
        a, b = reference('pre_reference_A'), reference('pre_reference_B')
        regression = reference('pre_targeted_retry', '13:28:20', '13:28:14')
        series = rows(a, b, regression)
        out = c.pair(series, DATE, 'pre')
        self.assertFalse(out['converged']); self.assertEqual(out['reason'], 'server_time_regression')
        series += rows(reference('pre_targeted_retry', '13:28:25'))
        self.assertFalse(c.pair(series, DATE, 'pre')['converged'])
        series += rows(reference('pre_targeted_retry', '13:28:30'))
        out = c.pair(series, DATE, 'pre')
        self.assertTrue(out['converged']); self.assertEqual(out['A']['phase'], 'pre_targeted_retry')
        self.assertEqual(out['original_A']['phase'], 'pre_reference_A')

    def test_distinct_server_and_volume_identity_required(self):
        for b in (reference('pre_reference_B', volume='11'), reference('pre_reference_B', volume='-')):
            self.assertFalse(c.pair(rows(reference('pre_reference_A'), b), DATE, 'pre')['converged'])
        # Two targeted observations of the same server cache remain one observation.
        a = reference('pre_reference_A', volume='9')
        b = reference('pre_reference_B')
        same = reference('pre_targeted_retry', '13:28:20', '13:28:15')
        out = c.pair(rows(a, b, same), DATE, 'pre')
        self.assertFalse(out['converged']); self.assertEqual(out['reason'], 'same_server_observation')

    def test_wrong_date_future_clock_trade_cutoff_and_deadline_rejected(self):
        bad = []
        r = reference('pre_reference_B'); r['response']['queryTime']['sysDate'] = '20261001'; bad.append(r)
        bad.append(reference('pre_reference_B', server='13:29:00'))
        bad.append(reference('pre_reference_B', trade='13:25:00'))
        bad.append(reference('pre_targeted_retry', request='13:29:30'))  # response arrives after deadline
        for r in bad:
            with self.subTest(r=r['response']['queryTime']):
                self.assertFalse(c.pair(rows(reference('pre_reference_A'), reference('pre_reference_B'), r), DATE, 'pre')['converged'])

    def test_old_probes_cannot_substitute_unsampled_references(self):
        rs = [record('13:25:20', '13:25:20'), record('13:25:30', '13:25:30')]
        self.assertEqual(c.pair(rows(*rs), DATE, 'pre')['reason'], 'NOT_SAMPLED')
        out = c.build_report(DATE, [], rs, [SYMBOL], {'checks': []})
        self.assertEqual(out['status'], 'NOT_SAMPLED'); self.assertEqual(out['both_converged_count'], 0)
        self.assertIsNone(out['securities'][0]['p_before'])

    def test_normal_close_late_observed_does_not_become_delayed(self):
        rs = all_references()
        out = c.build_report(DATE, [{'records': rs}], [], [SYMBOL], {'checks': []})
        self.assertEqual(out['p_close_converged_count'], 1)
        self.assertEqual(out['securities'][0]['close_classification'], 'normal_close_candidate')
        self.assertEqual(out['true_delayed_close_candidate_count'], 0)

    def test_delayed_transition_gets_targeted_confirmation(self):
        rs = all_references()
        rs[-1] = reference('close_reference_B', trade='13:33:00', price='105', volume='21')
        first = c.pair(rows(*rs), DATE, 'close')
        self.assertTrue(first['delayed_transition_candidate']); self.assertFalse(first['converged'])
        rs.append(reference('close_targeted_retry', '13:33:40', trade='13:33:00', price='105', volume='21'))
        out = c.build_report(DATE, [{'records': rs}], [], [SYMBOL], {'checks': []})
        self.assertEqual(out['p_close_converged_count'], 1)
        self.assertEqual(out['true_delayed_close_candidate_count'], 1)
        self.assertFalse(out['securities'][0]['p_close_validated'])

    def test_no_new_close_trade_is_not_missing(self):
        rs = all_references()
        rs[-2] = reference('close_reference_A')
        rs[-1] = reference('close_reference_B')
        out = c.build_report(DATE, [{'records': rs}], [], [SYMBOL], {'checks': []})
        self.assertEqual(out['no_closing_new_trade_count'], 1)
        self.assertEqual(out['securities'][0]['p_close'], '100')

    def test_close_B_must_follow_actual_1333(self):
        a = reference('close_reference_A', trade='13:30:00')
        b = reference('close_reference_B', server='13:32:59', trade='13:30:00')
        self.assertFalse(c.pair(rows(a, b), DATE, 'close')['converged'])

    def test_research_threshold_official_mismatch_and_production_gate(self):
        rs = all_references()
        for price, count in (('104', 1), ('105', 0)):
            out = c.build_report(DATE, [{'records': rs}], [], [SYMBOL], {'checks': [{**SYMBOL, 'official_close': price}]})
            candidates = c.research_candidates(out)
            self.assertEqual(candidates['candidate_count'], count)
            self.assertFalse(candidates['validated']); self.assertEqual(out['both_validated_count'], 0)
        # PENDING official publication permits only explicitly unverified research.
        out = c.build_report(DATE, [{'records': rs}], [], [SYMBOL], {'checks': []})
        self.assertEqual(c.research_candidates(out)['candidates'][0]['official_price_result'], 'PENDING')

    def test_probe_conflict_blocks_research_without_substituting_price(self):
        rs = all_references()
        probe_row = record('13:29:59', '13:29:59', price='99', v='11')
        out = c.build_report(DATE, [{'records': rs}], [probe_row], [SYMBOL], {'checks': []})
        self.assertEqual(out['research_calculable_count'], 0)
        self.assertIsNone(out['securities'][0]['p_before'])
        self.assertEqual(c.unresolved(DATE, [{'records': rs}], [SYMBOL], 'pre', [probe_row]), [SYMBOL])

    def test_targeted_retry_requests_only_affected_symbols(self):
        healthy = {'ex': 'tse', 'code': '2317', 'market': 'TWSE', 'name': 'fixture'}
        rs = all_references()[:2]
        rs[-1]['response']['msgArray'][0]['v'] = '11'
        for r in rs:
            r['symbols'].append(healthy)
            item = copy.deepcopy(r['response']['msgArray'][0]); item['c'] = '2317'; item['v'] = '10'
            r['response']['msgArray'].append(item)
        def replacement(phase, planned, symbols, output, deadline):
            r = reference(phase, request=planned.strftime('%H:%M:%S'), volume='11')
            return {'records': [r], 'metrics': {'phase': phase}}
        clock_times = [probe.target(DATE, t) for t in ('13:28:30', '13:28:30', '13:28:30', '13:28:40', '13:28:40', '13:28:40', '13:28:50')]
        with tempfile.TemporaryDirectory() as d, patch.object(probe, 'now_tpe', side_effect=clock_times), \
             patch.object(probe, 'wait_until'), patch.object(probe, 'snapshot', side_effect=replacement) as capture:
            retries = probe.targeted_retries('pre', DATE, [{'records': rs}], [SYMBOL, healthy], Path(d))
        self.assertEqual(len(retries), 1)
        for call in capture.call_args_list:
            self.assertEqual(call.args[2], [SYMBOL])

    def test_official_comparison_uses_chosen_pair_not_latest_stale_payload(self):
        rs = all_references()
        chosen = c.build_report(DATE, [{'records': rs}], [], [SYMBOL], {'checks': []})
        stale = reference('close_targeted_retry', '13:34:00', '13:24:51', price='90')
        tse = {'date': '20261002', 'stat': 'OK', 'tables': [{'fields': ['證券代號', '收盤價'], 'data': [['2330', '104']]}]}
        otc = {'date': '20261002', 'stat': 'ok', 'tables': []}
        with tempfile.TemporaryDirectory() as d:
            out = official_quotes.validate(DATE, [SYMBOL], [{'records': [*rs, stale]}], Path(d),
                lambda url, timeout: (200, json.dumps(tse if 'twse' in url else otc).encode()), chosen['securities'])
        self.assertEqual(out['matches'], 1); self.assertEqual(out['status'], 'PENDING')

    def test_capture_loader_accepts_new_phases_without_inventing_old_1330_snapshot(self):
        buff = io.BytesIO()
        with zipfile.ZipFile(buff, 'w') as z:
            z.writestr('universe.json', json.dumps([SYMBOL]))
            z.writestr('run_summary.json', json.dumps({'trade_date': DATE, 'capture_architecture': c.VERSION}))
            z.writestr('probe_raw.jsonl', '')
            z.writestr('preclose_raw.jsonl', '')
            for r in all_references():
                z.writestr(r['phase']+'_raw.jsonl', json.dumps(r)+'\n')
        summary, universe, snaps, probes = official_retry.load_capture(buff.getvalue())
        self.assertEqual(len(snaps), 5)
        self.assertFalse(any(r.get('phase') == 'close' for s in snaps for r in s['records']))

    def test_live_orchestrator_runs_exact_reference_plan_without_full_1330_capture(self):
        symbols = [dict(ex=ex, code=code, market='TWSE' if ex=='tse' else 'TPEx', name='fixture') for ex,code in probe.FIXED_PROBE]
        current = [probe.target(DATE, '13:07:00')]
        captured = []
        def wait(until):
            current[0] = max(current[0], until)
        def snapshot(phase, planned, universe, output, deadline=None):
            captured.append((phase, planned.strftime('%H:%M:%S')))
            closing = phase.startswith('close_')
            r = reference(phase, planned.strftime('%H:%M:%S'), price='104' if closing else '100',
                          trade='13:30:00' if closing else '13:24:59', volume='20' if closing else '10')
            r['symbols'] = universe
            item = r['response']['msgArray'][0]
            r['response']['msgArray'] = [{**copy.deepcopy(item), 'ex':s['ex'], 'c':s['code']} for s in universe]
            r.update(missing=[], empty=[], duplicate=[])
            (output/(phase+'_raw.jsonl')).write_text(json.dumps(r)+'\n')
            return {'records':[r], 'metrics':{'phase':phase,'success_count':len(universe),
                    'stock_universe_count':len(universe),'symbol_set_equal':True}}
        with tempfile.TemporaryDirectory() as d, patch.object(probe, 'now_tpe', side_effect=lambda:current[0]), \
             patch.object(probe, 'wait_until', side_effect=wait), patch.object(probe, 'github_issue'), \
             patch.object(probe, 'fetch_universe', return_value=symbols), \
             patch.object(probe.tradable, 'build', return_value=(symbols, {'status':'OFFICIAL_SOURCES_DATE_CHECKED','excluded_symbol_count':0})), \
             patch.object(probe, 'snapshot', side_effect=snapshot), patch.object(probe, 'per_second_probe', return_value=[]), \
             patch.object(probe.official_quotes, 'validate', return_value={'status':'PENDING','checks':[]}), \
             patch.dict('os.environ', {'RUNNER_STARTED_AT':probe.iso(current[0])}):
            self.assertEqual(probe.live(Path(d)), 0)
            summary=json.loads((Path(d)/'run_summary.json').read_text())
            self.assertEqual(summary['convergence']['both_converged_count'], 8)
            self.assertEqual(summary['convergence']['both_validated_count'], 0)
            self.assertEqual(summary['candidate_count'], 8)
            self.assertEqual(summary['official_validation'], 'PENDING')
        self.assertEqual(captured, [('preclose','13:24:50'), *c.REFERENCE_TIMES.items()])

    def test_saved_1002_regression_fixture_is_not_AB_evidence(self):
        fixture = json.loads((Path(__file__).parent/'fixtures/cache-regression-20261002.json').read_text())
        obs = rows(*fixture['records'])
        stock = [r for r in obs if r['code'] == '2330']
        final = next(r for r in stock if r['planned_at'][11:19] == '13:25:50')
        stale = next(r for r in stock if r['planned_at'][11:19] == '13:26:00')
        self.assertEqual((final['trade_t'], final['trade_z']), ('13:24:59', '2505.0000'))
        self.assertTrue(f.fresh_candidate(final, DATE))
        self.assertFalse(f.fresh_candidate(stale, DATE)); self.assertLess(stale['server_time'], final['server_time'])
        self.assertEqual(c.pair(stock, DATE, 'pre')['reason'], 'NOT_SAMPLED')


if __name__ == '__main__':
    unittest.main()
