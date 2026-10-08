import copy
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import close_research as r
import convergence as c
import freshness as f
import official_retry
import probe
from test_convergence import reference, SYMBOL, saved_probe_fixture

DAY = '2026-10-08'


def ref(phase, server=None, trade='13:30:00', price='104', volume='20'):
    clock = c.reference_times(DAY).get(phase,'13:24:50')
    original = reference(phase, clock, server or clock, price=price, trade=trade, volume=volume)
    original = json.loads(json.dumps(original).replace('2026-10-02', DAY).replace('20261002', '20261008'))
    original['planned_at'] = DAY+'T'+clock+'.000+08:00'
    return original


def assess(*records):
    return r.assess(f.observations(records, DAY), DAY)


class CloseResearchTests(unittest.TestCase):
    def test_fresh_A_1330_is_medium_research_never_converged_or_validated(self):
        out = assess(ref('close_reference_A'))
        self.assertEqual(out['classification'], 'A_1330_fresh_candidate')
        self.assertEqual(out['confidence_level'], 'MEDIUM_RESEARCH')
        self.assertFalse(out['converged']); self.assertFalse(out['validated'])

    def test_stale_A_1330_is_not_candidate(self):
        self.assertEqual(assess(ref('close_reference_A', server='13:32:00'))['classification'], 'unresolved')

    def test_fresh_earlier_trade_is_not_single_A_close(self):
        self.assertEqual(assess(ref('close_reference_A', trade='13:24:53'))['classification'], 'unresolved')

    def test_fresh_post_1330_is_delayed_and_not_calculable_without_confirmation(self):
        out = assess(ref('close_reference_A', trade='13:31:00'))
        self.assertEqual(out['classification'], 'delayed_close_candidate')
        self.assertIsNone(out['p_close']); self.assertFalse(out['validated'])

    def test_stale_B_can_be_bridged_by_fresh_AC(self):
        out = assess(ref('close_reference_A'), ref('close_reference_B', server='13:24:51'), ref('close_reference_C'))
        self.assertEqual(out['classification'], 'AC_converged')
        self.assertEqual(out['confidence_level'], 'HIGH_RESEARCH')

    def test_stale_A_can_be_recovered_by_fresh_BC(self):
        out = assess(ref('close_reference_A', server='13:24:51'), ref('close_reference_B'), ref('close_reference_C'))
        self.assertEqual(out['classification'], 'BC_converged')

    def test_missing_price_is_unresolved(self):
        self.assertEqual(assess(ref('close_reference_A', price='-'))['classification'], 'unresolved')

    def test_AB_is_highest_priority_and_all_hierarchy_levels_unvalidated(self):
        cases = [([ref('close_reference_A'), ref('close_reference_B'), ref('close_reference_C')], 'AB_converged'),
                 ([ref('close_reference_A'), ref('close_reference_B',server='13:24:51'), ref('close_reference_C')], 'AC_converged'),
                 ([ref('close_reference_A',server='13:24:51'), ref('close_reference_B'), ref('close_reference_C')], 'BC_converged'),
                 ([ref('close_reference_A')], 'A_1330_fresh_candidate')]
        pre = [ref('pre_reference_A',trade='13:24:59',price='100',volume='10'),
               ref('pre_reference_B',trade='13:24:59',price='100',volume='10')]
        for records, label in cases:
            with self.subTest(label=label):
                report = c.build_report(DAY,[{'records':pre+records}],[],[SYMBOL],{'checks':[]})
                candidates = c.research_candidates(report)
                candidate = candidates['candidates'][0]
                self.assertEqual(candidate['P_close_convergence_type'],label)
                self.assertFalse(candidate['validated']); self.assertFalse(candidates['validated'])
                self.assertEqual(candidate['P_close'],'104')
                self.assertEqual(candidate['tail_return'],'0.04')
                self.assertFalse(report['securities'][0]['p_close_validated'])
                self.assertEqual(report['p_before_converged_count'],1)
                if label=='A_1330_fresh_candidate':
                    self.assertEqual(report['p_close_converged_count'],0)
                    self.assertIsNone(report['securities'][0]['p_close'])

    def test_fresh_conflicting_B_or_C_blocks_A_fallback_and_older_AB(self):
        for records in ([ref('close_reference_A'),ref('close_reference_B',price='105')],
                        [ref('close_reference_A'),ref('close_reference_B'),ref('close_reference_C',price='105')],
                        [ref('close_reference_A'),ref('close_reference_B',price='-')]):
            self.assertEqual(assess(*records)['classification'],'unresolved')

    def test_volume_conflict_wrong_date_duplicate_and_fake_schedule_are_rejected(self):
        self.assertEqual(assess(ref('close_reference_A'),ref('close_reference_B',volume='21'))['classification'],'unresolved')
        for field in ('date','duplicate','schedule'):
            rows = f.observations([ref('close_reference_A')],DAY)
            if field=='date': rows[0]['d']='20261007'
            elif field=='duplicate': rows[0]['duplicate']=True
            else: rows[0]['planned_at']=DAY+'T13:32:00+08:00'
            self.assertEqual(r.assess(rows,DAY)['classification'],'unresolved')

    def test_same_cached_server_is_not_two_fresh_observations(self):
        a = ref('close_reference_A',server='13:32:31')
        b = ref('close_reference_B',server='13:32:31')
        self.assertEqual(assess(a,b)['classification'],'A_1330_fresh_candidate')

    def test_delayed_trade_needs_two_agreeing_fresh_observations(self):
        a = ref('close_reference_A',trade='13:31:00')
        b = ref('close_reference_B',trade='13:31:00')
        self.assertEqual(assess(a,b)['classification'],'AB_converged')
        self.assertEqual(assess(a,b)['trade_time'],'13:31:00')

    def test_grouping_preserves_stock_set_batch_size_and_determinism(self):
        universe = [{'code':str(i),'ex':'tse'} for i in range(123)]
        original = copy.deepcopy(universe)
        keys = lambda xs: ['|'.join(v['code'] for v in xs[i:i+50]) for i in range(0,len(xs),50)]
        for label in ('B','C'):
            order = r.ordered_symbols(universe,label)
            self.assertEqual(set(v['code'] for v in order),set(v['code'] for v in universe))
            self.assertEqual(order,r.ordered_symbols(universe,label))
            self.assertFalse(set(keys(order)) & set(keys(universe)))
        self.assertNotEqual(keys(r.ordered_symbols(universe,'B')),keys(r.ordered_symbols(universe,'C')))
        self.assertEqual(universe,original)
        self.assertEqual((probe.BATCH_SIZE,probe.CONCURRENCY),(50,5))

    def test_C_targets_only_unconfirmed_symbols(self):
        healthy = {'ex':'tse','code':'2317','market':'TWSE','name':'fixture'}
        a,b = ref('close_reference_A'),ref('close_reference_B',server='13:24:51')
        for record in (a,b):
            record['symbols'] = [SYMBOL,healthy]
            extra = copy.deepcopy(record['response']['msgArray'][0]);extra['c']='2317'
            record['response']['msgArray'].append(extra)
        # Different response batches model only 2330's stale B cache.
        healthy_b = ref('close_reference_B');healthy_b['symbols']=[healthy]
        healthy_b['response']['msgArray'][0]['c']='2317'
        b['symbols']=[SYMBOL];b['response']['msgArray']=b['response']['msgArray'][:1]
        self.assertEqual(r.affected(DAY,[{'records':[a,b,healthy_b]}],[SYMBOL,healthy]),[SYMBOL])

    def test_live_oct8_outputs_before_official_network_and_preserves_C_evidence(self):
        symbols=[dict(ex=ex,code=code,market='TWSE' if ex=='tse' else 'TPEx',name='fixture') for ex,code in probe.FIXED_PROBE]
        current=[probe.target(DAY,'13:07:00')];captured=[]
        def wait(until):current[0]=max(current[0],until)
        def snapshot(phase,planned,universe,output,deadline=None):
            captured.append((phase,planned.strftime('%H:%M:%S'),[s['code'] for s in universe],deadline))
            closing=phase.startswith('close_')
            row=ref(phase,server='13:24:51' if phase=='close_reference_B' else None,
                trade='13:30:00' if closing else '13:24:59',price='104' if closing else '100',volume='20' if closing else '10')
            row['symbols']=universe;item=row['response']['msgArray'][0]
            row['response']['msgArray']=[{**copy.deepcopy(item),'ex':s['ex'],'c':s['code']} for s in universe]
            row.update(missing=[],empty=[],duplicate=[])
            (output/(phase+'_raw.jsonl')).write_text(json.dumps(row)+'\n')
            return {'records':[row],'metrics':{'phase':phase,'stock_universe_count':len(universe),'success_count':len(universe),'symbol_set_equal':True}}
        with tempfile.TemporaryDirectory() as d, patch.object(probe,'now_tpe',side_effect=lambda:current[0]), \
             patch.object(probe,'wait_until',side_effect=wait),patch.object(probe,'github_issue'), \
             patch.object(probe,'fetch_universe',return_value=symbols), \
             patch.object(probe.tradable,'build',return_value=(symbols,{'status':'OFFICIAL_SOURCES_DATE_CHECKED','excluded_symbol_count':0})), \
             patch.object(probe,'snapshot',side_effect=snapshot),patch.object(probe,'per_second_probe',side_effect=saved_probe_fixture), \
             patch.object(probe.official_quotes,'validate') as official, \
             patch.dict('os.environ',{'RUNNER_STARTED_AT':probe.iso(current[0])}):
            out=Path(d);self.assertEqual(probe.live(out),0);official.assert_not_called()
            summary=json.loads((out/'live_research_summary.json').read_text())
            self.assertEqual(summary['P_close']['AC_converged'],len(symbols))
            self.assertEqual(summary['candidate_count'],len(symbols))
            self.assertLessEqual(summary['generated_at'][11:19],'13:35:00')
            self.assertFalse(summary['validated'])
            rows=json.loads((out/f'research_candidates_{DAY}.json').read_text())['candidates']
            for row in rows:
                self.assertEqual(row['confidence_level'],'HIGH_RESEARCH');self.assertFalse(row['validated'])
                for field in ('P_before','P_before_trade_time','P_close','P_close_trade_time',
                              'P_before_convergence_type','P_close_convergence_type','tail_return'):
                    self.assertIn(field,row)
            (out/'probe_raw.jsonl').write_text('')
            archive=io.BytesIO()
            with zipfile.ZipFile(archive,'w') as z:
                for file in out.iterdir():
                    if file.is_file():z.write(file,file.name)
            _,_,snaps,_=official_retry.load_capture(archive.getvalue())
            self.assertTrue(any(rec.get('phase')=='close_reference_C' for snap in snaps for rec in snap['records']))
        self.assertEqual([x[:2] for x in captured],[('preclose','13:24:50'),*c.reference_times(DAY).items()])
        b=next(x for x in captured if x[0]=='close_reference_B')
        self.assertEqual(b[2],[s['code'] for s in reversed(symbols)])
        self.assertEqual(b[3].strftime('%H:%M:%S'),'13:34:08')

    def test_no_C_when_AB_healthy_and_no_MIS_on_empty_C_selection(self):
        records=[ref('close_reference_A'),ref('close_reference_B')]
        self.assertEqual(r.affected(DAY,[{'records':records}],[SYMBOL]),[])

    def test_offline_replay_does_not_change_archive_or_raw_evidence(self):
        records=[ref(p,trade='13:24:59' if p.startswith('pre') else '13:30:00',
                     price='100' if p.startswith('pre') else '104')
                 for p in c.reference_times(DAY)]
        with tempfile.TemporaryDirectory() as d:
            archive=Path(d)/'capture.zip'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('universe.json',json.dumps([SYMBOL]))
                z.writestr('run_summary.json',json.dumps({'trade_date':DAY,'capture_architecture':c.VERSION,
                    'pre_reference_C_enabled':True,'close_reference_C_enabled':True}))
                z.writestr('probe_raw.jsonl','');z.writestr('preclose_raw.jsonl','')
                for rec in records:z.writestr(rec['phase']+'_raw.jsonl',json.dumps(rec)+'\n')
            digest=hashlib.sha256(archive.read_bytes()).hexdigest()
            _,universe,snapshots,probes=official_retry.load_capture(archive.read_bytes())
            before=copy.deepcopy(snapshots)
            c.build_report(DAY,snapshots,probes,universe,{'checks':[]})
            self.assertEqual(snapshots,before)
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),digest)


if __name__=='__main__':unittest.main()
