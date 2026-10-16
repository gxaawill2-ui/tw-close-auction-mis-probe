import copy
import tempfile
import unittest
from stage5_candidate_verifier import compile_update,DATE
from stage5_runtime import Source,LocalVault


class CandidateVerifierTests(unittest.TestCase):
    def test_stale_or_removed_candidate_cannot_overwrite_newer_research(self):
        row={'code':'2330','ex':'tse','P_before':'100','P_close':'104','verification_status':'RESEARCH_ONLY','validated':False}
        view={'mode':'LIVE','trade_date':DATE,'version':1,'rows':[{**row,'P_close':'105'}]}
        self.assertIsNone(compile_update(view,row,{},DATE+'T13:38:00+08:00'))
        self.assertIsNone(compile_update({**view,'rows':[]},row,{},DATE+'T13:38:00+08:00'))
        with self.assertRaises(ValueError):compile_update({**view,'rows':[{**row,'validated':True,'verification_status':'VERIFIED'}]},row,{},DATE+'T13:38:00+08:00')

    def test_provider_rate_can_only_be_slowed_and_minute_cap_is_six(self):
        from datetime import timedelta
        import freshness as f
        from test_stage5_runtime import Response
        from stage3_fixtures import example,DAY
        row,bundle=example();at=[f.parsed_time(DAY+'T13:38:00+08:00')];starts=[]
        def wait(seconds):at[0]+=timedelta(seconds=seconds)
        def opener(*a,**k):starts.append(at[0]);return Response(bundle['quote_before']['raw'].encode())
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):Source('K'*30,tmp,LocalVault(),min_interval=1)
            source=Source('K'*30,tmp,LocalVault(),clock=lambda:at[0],wait=wait,opener=opener,min_interval=10.1)
            for _ in range(8):source.request(row,'quote',{},at[0]+timedelta(minutes=2))
        for start in starts:self.assertLessEqual(sum(0<=(at_-start).total_seconds()<60 for at_ in starts),6)


if __name__=='__main__':unittest.main()
