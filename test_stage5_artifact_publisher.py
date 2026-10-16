from pathlib import Path
import tempfile
import unittest
from stage5_artifact_publisher import make_view
from test_fast_selection import records
from test_close_research import DAY
from test_convergence import SYMBOL


class ArtifactPublisherTests(unittest.TestCase):
    def test_real_research_values_come_only_from_mis_and_never_become_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            view=make_view(DAY,{'trade_date':DAY},[SYMBOL],[{'records':records()[:3]}],[],tmp,DAY+'T13:35:00+08:00')
        self.assertEqual(view['research_candidate_count'],1)
        self.assertEqual(view['verified_count'],0)
        self.assertEqual(view['rows'][0]['price_source'],'MIS')
        self.assertFalse(view['rows'][0]['validated'])
        self.assertEqual(view['rows'][0]['verification_status'],'RESEARCH_ONLY')
        self.assertFalse(view['full_market_no_false_negative_claim'])
        self.assertNotIn('raw',view['rows'][0]['independent_evidence'])

    def test_wrong_date_and_conflicting_mis_cannot_be_published_as_candidate(self):
        from test_close_research import ref
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'DATE'):make_view(DAY,{'trade_date':'1999-01-01'},[SYMBOL],[],[],tmp,DAY+'T13:35:00+08:00')
            view=make_view(DAY,{'trade_date':DAY},[SYMBOL],[{'records':records()[:3]+[ref('close_reference_C',price='105')]}],[],tmp,DAY+'T13:35:00+08:00')
        self.assertEqual(view['rows'],[]);self.assertEqual(view['verified_count'],0)


if __name__=='__main__':unittest.main()
