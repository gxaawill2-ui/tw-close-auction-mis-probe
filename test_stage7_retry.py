import tempfile
import unittest
from fast_selection import Engine
from test_convergence import SYMBOL
from test_fast_selection import records
from test_close_research import DAY,ref
from stage7_retry import plan

class C2PlanTests(unittest.TestCase):
    def setup_engine(self,tmp,conflict=False):
        e=Engine(DAY,[SYMBOL],tmp)
        for r in records():e.feed(r)
        if conflict:e.feed(ref('close_reference_C',price='105'))
        return e
    def test_converged_not_retried_and_c_conflict_reviewed_without_public_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(plan(self.setup_engine(tmp),DAY+'T13:34:20+08:00')['symbols'],[])
            e=self.setup_engine(tmp,True);r=plan(e,DAY+'T13:34:20+08:00')
            self.assertEqual(len(r['symbols']),1);self.assertTrue(r['symbols'][0]['private_review_only']);self.assertEqual(r['mis_requests'],0)
            self.assertEqual(e.view()['research_count'],0)
    def test_round_budget_does_not_reset_when_price_fingerprint_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=self.setup_engine(tmp,True)
            ledger={'tse:2330':{'attempts':2,'last_attempt_at':DAY+'T13:34:12+08:00'}}
            self.assertEqual(plan(e,DAY+'T13:34:20+08:00',ledger)['symbols'],[])
            e.feed(ref('close_reference_C',price='106'))
            self.assertEqual(plan(e,DAY+'T13:34:20+08:00',ledger)['symbols'],[])
    def test_cooldown_deadline_and_missing_comparison_never_filled(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=self.setup_engine(tmp,True)
            self.assertEqual(plan(e,DAY+'T13:34:20+08:00',{'tse:2330':{'attempts':1,'last_attempt_at':DAY+'T13:34:19+08:00'}})['symbols'],[])
            for time in ('13:34:09','13:34:42','13:34:50'):
                self.assertEqual(plan(e,DAY+'T'+time+'+08:00')['symbols'],[])
            missing=Engine(DAY,[SYMBOL],tmp);missing.feed(ref('close_reference_C',price='106'))
            self.assertEqual(plan(missing,DAY+'T13:34:20+08:00')['symbols'],[])
    def test_bad_ledger_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):plan(self.setup_engine(tmp,True),DAY+'T13:34:20+08:00',{'tse:2330':{'attempts':-1}})
