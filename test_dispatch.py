import base64
import copy
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import run_control as c
import probe
import convergence
from test_convergence import all_references,SYMBOL,DATE


class DispatchTests(unittest.TestCase):
    def test_claim_once_duplicate_never_overwrites_first_state(self):
        saved={};writes=[]
        def read(path):return copy.deepcopy(saved),'first_sha' if saved else None
        def api(path,method,payload):
            writes.append(payload);saved.update(json.loads(base64.b64decode(payload['content'])))
            return {'content':{'sha':'first_sha'}}
        with patch.object(c,'read_state',side_effect=read),patch.object(c,'api',side_effect=api):
            first=c.claim_capture('state/live/test.json',{'status':'running','run_id':'first'})
            second=c.claim_capture('state/live/test.json',{'status':'running','run_id':'second'})
        self.assertTrue(first[0]);self.assertFalse(second[0]);self.assertEqual(len(writes),1)
        self.assertEqual(saved['capture_owner_run_id'],'first')

    def test_compare_and_swap_conflict_rechecks_owner_not_blind_merge(self):
        competing={'capture_claimed':True,'capture_owner_run_id':'other','run_id':'other'}
        conflict=urllib.error.HTTPError('https://api.github.com',409,'Conflict',{},None)
        with patch.object(c,'read_state',side_effect=[({},None),(competing,'owner_sha')]), \
             patch.object(c,'api',side_effect=conflict) as api:
            claimed,state,sha=c.claim_capture('state/live/test.json',{'run_id':'mine'})
        self.assertFalse(claimed);self.assertEqual(sha,'owner_sha');self.assertEqual(api.call_count,1)

    def test_orphaned_running_claim_does_not_auto_unlock(self):
        with patch.object(c,'read_state',return_value=({'status':'running','run_id':'old'},'sha')),patch.object(c,'api') as api:
            self.assertFalse(c.claim_capture('state/live/test.json',{'run_id':'new'})[0])
        api.assert_not_called()

    def test_blocked_october5_live_never_fetches_MIS_or_changes_daily_state(self):
        now=probe.target('2026-10-05','14:08:00')
        state={'trade_date':'2026-10-05','status':'missing_incomplete','capture_blocked':True}
        with tempfile.TemporaryDirectory() as d,patch.object(probe,'now_tpe',return_value=now), \
             patch.object(c,'receipt'),patch.object(c,'read_state',return_value=(state,'sha')), \
             patch.object(c,'merge_state') as write,patch.object(probe,'live') as live, \
             patch.object(probe,'fetch_mis') as mis,patch.object(probe,'fetch_universe') as universe:
            self.assertEqual(c.run('live',Path(d)),0)
            self.assertEqual(json.loads((Path(d)/'skipped.json').read_text())['status'],'skipped_existing_capture')
        write.assert_not_called();live.assert_not_called();mis.assert_not_called();universe.assert_not_called()

    def test_same_date_evidence_always_skips_before_late_gate(self):
        for state in ({'preclose_captured':True},{'status':'partial'},{'capture_claimed':True},{'capture_blocked':True}):
            self.assertTrue(c.skip_existing(state))

    def test_caller_source_is_only_declaration_no_credential_in_receipt(self):
        with patch.dict('os.environ',{'GITHUB_EVENT_NAME':'workflow_dispatch','TRIGGER_SOURCE':'cron-job.org-test',
                 'GITHUB_RUN_ID':'123','GITHUB_TOKEN':'NEVER_PERSIST_THIS','PROBE_MODE':'dry-run'}),patch.object(c,'merge_state') as write:
            c.receipt()
        payload=write.call_args_list[0].args[1]
        self.assertFalse(payload['source_verified'])
        self.assertEqual(payload['event'],'workflow_dispatch')
        self.assertNotIn('NEVER_PERSIST_THIS',json.dumps(write.call_args_list,default=str))

    def test_saved_prices_and_csv_include_requested_evidence_fields(self):
        with tempfile.TemporaryDirectory() as d:
            report=convergence.write_report(DATE,[{'records':all_references()}],[],[SYMBOL],{'checks':[]},Path(d))
            candidate=json.loads((Path(d)/'research_candidates.json').read_text())['candidates'][0]
            for k in ('p_before_trade_time','close_trade_time','tail_return_pct','pre_pair_evidence','close_pair_evidence'):
                self.assertIn(k,candidate)
            self.assertEqual(candidate['tail_return_pct'],'4.00')
            self.assertFalse(candidate['validated'])
            self.assertIn('p_close_A_server_time',(Path(d)/'convergence.csv').read_text())
            self.assertIn('stale_seen',(Path(d)/'research_candidates.csv').read_text())
            self.assertEqual(json.loads((Path(d)/'unknown_symbols.json').read_text())['unknown_count'],0)
            self.assertEqual(report['securities'][0]['p_close_convergence_status'],'normal_close_converged_candidate')


if __name__=='__main__':unittest.main()
