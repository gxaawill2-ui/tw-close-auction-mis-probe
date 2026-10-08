import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import capture_completion as c
import probe
import run_control
from test_close_research import ref, DAY
from test_convergence import SYMBOL


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.out=Path(self.tmp.name)
        self.summary={'trade_date':DAY,'runner_started_at':DAY+'T13:00:00+08:00',
            'universe_count':1,'universe_audit_status':'OFFICIAL_SOURCES_DATE_CHECKED',
            'snapshots':{},'candidate_count':0,'research_calculable_count':1,
            'official_validation':'PENDING','live_close_research_enabled':True}
        self.write('universe.json',[SYMBOL])
        for phase in ('preclose','pre_reference_A','pre_reference_B','close_reference_A','close_reference_B'):
            row=ref(phase);self.write(phase+'_raw.jsonl',row,lines=True)
            self.summary['snapshots'][phase]={'symbol_set_equal':True}
        self.write('probe_raw.jsonl',ref('preclose'),lines=True)
        self.write('error_missing_report.json',{'probe_errors':[],'snapshot_errors':[]})
        self.outputs(0)

    def write(self,name,data,lines=False):
        (self.out/name).write_text(json.dumps(data)+'\n')

    def outputs(self,count):
        self.summary['candidate_count']=count
        candidates=[{'code':str(2330+i),'status':'RESEARCH_ONLY','validated':False} for i in range(count)]
        self.write('research_candidates.json',{'trade_date':DAY,'validated':False,'candidate_count':count,'candidates':candidates})
        self.write('convergence_report.json',{'trade_date':DAY,'validated':False,'securities':[SYMBOL],'research_calculable_count':self.summary['research_calculable_count']})
        self.write('live_research_summary.json',{'trade_date':DAY,'validated':False,'candidate_count':count,'research_calculable_count':self.summary['research_calculable_count']})
        for name in ('research_candidates.csv','research_candidates_'+DAY+'.csv','research_candidates_'+DAY+'.json'):
            (self.out/name).write_text('code\n' if name.endswith('.csv') else '{}')

    def classify(self):return c.classify(self.out,self.summary)

    def test_complete_pending_is_success_not_program_failure(self):
        result=self.classify()
        self.assertEqual((result['capture_outcome'],result['exit_code']),('CAPTURE_SUCCESS',0))
        self.assertEqual(result['official_validation'],'PENDING')

    def test_zero_candidates_is_valid_complete_execution(self):
        self.outputs(0);self.assertEqual(self.classify()['exit_code'],0)

    def test_multiple_candidates_is_valid_complete_execution(self):
        self.outputs(7);self.assertEqual(self.classify()['exit_code'],0)

    def test_unresolved_is_explicit_partial_exit_zero(self):
        self.summary['research_calculable_count']=0;self.outputs(0)
        result=self.classify()
        self.assertEqual((result['capture_outcome'],result['exit_code'],result['research_unresolved_count']),('CAPTURE_PARTIAL',0,1))

    def test_optional_probe_errors_are_partial_not_failed(self):
        self.write('error_missing_report.json',{'probe_errors':[{'error':'MIS_EMPTY_BODY','missing':['tse:2330']}],'snapshot_errors':[]})
        self.assertEqual(self.classify()['capture_outcome'],'CAPTURE_PARTIAL')
        self.assertEqual(self.classify()['exit_code'],0)

    def test_mandatory_phase_all_http_errors_is_failed(self):
        row=ref('close_reference_A');row.update(http_status=503,error='HTTP_503',response={})
        self.write('close_reference_A_raw.jsonl',row,True)
        self.assertEqual((self.classify()['capture_outcome'],self.classify()['exit_code']),('CAPTURE_FAILED',1))

    def test_some_symbols_missing_or_http_batches_allow_explicit_partial(self):
        other={**SYMBOL,'code':'2317'};self.write('universe.json',[SYMBOL,other]);self.summary['universe_count']=2
        self.write('convergence_report.json',{'trade_date':DAY,'validated':False,'securities':[SYMBOL,other],'research_calculable_count':1})
        result=self.classify()
        self.assertEqual(result['exit_code'],0);self.assertEqual(result['capture_outcome'],'CAPTURE_PARTIAL')
        self.assertEqual(result['phases']['preclose']['missing_symbols'],['tse:2317'])

    def test_required_phase_not_executed_or_missing_fails(self):
        (self.out/'pre_reference_A_raw.jsonl').unlink()
        self.assertEqual(self.classify()['exit_code'],1)

    def test_deadline_no_request_is_failure_not_partial(self):
        row=ref('pre_reference_A');row['error']='CAPTURE_DEADLINE_NO_REQUEST'
        self.write('pre_reference_A_raw.jsonl',row,True)
        self.assertEqual(self.classify()['exit_code'],1)

    def test_corrupt_raw_evidence_is_failure(self):
        (self.out/'pre_reference_B_raw.jsonl').write_text('{broken')
        self.assertEqual(self.classify()['exit_code'],1)

    def test_wrong_trade_date_is_failure(self):
        row=ref('close_reference_A');row['response']['msgArray'][0]['d']='20261007'
        self.write('close_reference_A_raw.jsonl',row,True)
        self.assertEqual(self.classify()['exit_code'],1)

    def test_wrong_runner_date_is_failure(self):
        self.summary['runner_started_at']='2026-10-07T13:00:00+08:00'
        self.assertEqual(self.classify()['exit_code'],1)

    def test_missing_or_corrupt_outputs_fail(self):
        (self.out/'research_candidates.json').unlink()
        self.assertEqual(self.classify()['exit_code'],1)

    def controller(self,side_effect=None,code=0):
        now=probe.target(DAY,'13:00:00')
        def live(out):
            if side_effect:raise side_effect
            self.write('run_summary.json',{**self.summary,'status':'partial','capture_outcome':'CAPTURE_PARTIAL'})
            return code
        with patch.object(probe,'now_tpe',return_value=now),patch.object(run_control,'receipt'), \
             patch.object(run_control,'read_state',return_value=({},None)),patch.object(run_control,'claim_capture',return_value=(True,{},None)), \
             patch.object(run_control,'calendar_state',return_value={'is_trading_day':True}), \
             patch.object(run_control,'publish'),patch.object(run_control,'merge_state') as merge, \
             patch.object(probe,'live',side_effect=live),patch.dict(os.environ,{'RUNNER_STARTED_AT':now.isoformat(),'GITHUB_RUN_ID':'test'}):
            return run_control.run('live',self.out),merge

    def test_controller_keeps_partial_success_exit_zero(self):
        self.assertEqual(self.controller()[0],0)

    def test_controller_true_exception_is_nonzero(self):
        code,merge=self.controller(RuntimeError('core interrupted'))
        self.assertNotEqual(code,0)
        self.assertEqual(merge.call_args.args[1]['capture_outcome'],'CAPTURE_FAILED')

    def test_package_write_failure_remains_nonzero(self):
        with patch.object(probe,'package',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.controller()

    def test_upload_failure_marks_completed_capture_failed(self):
        state={'trade_date':DAY,'run_id':'test','status':'partial','phase':'completed'}
        with patch.object(probe,'now_tpe',return_value=probe.target(DAY,'13:35:00')), \
             patch.object(run_control,'receipt'),patch.object(run_control,'publish'), \
             patch.object(run_control,'read_state',return_value=(state,None)),patch.object(run_control,'merge_state') as merge, \
             patch.dict(os.environ,{'GITHUB_RUN_ID':'test','ARTIFACT_UPLOAD_OUTCOME':'failure'}):
            run_control.run('workflow-failure',self.out)
            self.assertEqual(merge.call_args.args[1]['capture_outcome'],'CAPTURE_FAILED')
            self.assertEqual(merge.call_args.args[1]['error'],'ARTIFACT_UPLOAD_FAILED')

    def test_backup_existing_capture_makes_zero_market_requests(self):
        state={'capture_claimed':True,'preclose_captured':True,'run_id':'original','status':'partial'}
        with patch.object(run_control,'receipt'),patch.object(run_control,'read_state',return_value=(state,None)), \
             patch.object(probe,'live') as live,patch.object(run_control,'merge_state') as merge:
            self.assertEqual(run_control.run('live',self.out),0)
            live.assert_not_called();merge.assert_not_called()
            self.assertEqual(json.loads((self.out/'skipped.json').read_text())['prior_run'],'original')

    def test_push_workflow_never_runs_capture_or_upload(self):
        yaml=Path('.github/workflows/twse-mis-probe.yml').read_text()
        self.assertIn("if: github.event_name != 'push'",yaml)
        self.assertIn("if: always() && github.event_name != 'push'",yaml)
        self.assertNotIn('continue-on-error',yaml)
        self.assertIn('ARTIFACT_UPLOAD_OUTCOME: ${{ steps.artifact.outcome }}',yaml)


if __name__=='__main__':unittest.main()
