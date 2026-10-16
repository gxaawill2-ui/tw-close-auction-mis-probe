import tempfile
import json
import unittest
from unittest.mock import patch
from pathlib import Path
import freshness as f
from fast_selection import Engine
from stage5_session import pending_delayed_reviews, Session
from test_close_research import DAY, ref
from test_convergence import SYMBOL
from test_fast_selection import records


class PendingReviewTests(unittest.TestCase):
    def engine(self, directory, price='104', valid_pre=True):
        e=Engine(DAY,[SYMBOL],directory)
        if valid_pre:
            for record in records()[:2]:e.feed(record)
        e.feed(ref('close_reference_C',trade='13:33:00',price=price))
        return e

    def test_delayed_single_enters_private_review_without_public_admission(self):
        with tempfile.TemporaryDirectory() as directory:
            e=self.engine(directory)
            self.assertEqual(e.view()['rows'],[])
            pending=pending_delayed_reviews(e)
            self.assertEqual([r['code'] for r in pending],['2330'])
            self.assertTrue(pending[0]['private_review_only'])
            self.assertFalse(pending[0]['validated'])

    def test_threshold_and_missing_pre_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            for price,valid_pre in [('102.99',True),('104',False)]:
                self.assertEqual(pending_delayed_reviews(self.engine(directory,price,valid_pre)),[])

    def test_unchanged_queue_does_not_rescan_market(self):
        import convergence
        with tempfile.TemporaryDirectory() as directory:
            e=self.engine(directory)
            pending_delayed_reviews(e)
            with patch('stage5_session.convergence.pre_with_c', wraps=convergence.pre_with_c) as assess:
                self.assertEqual(len(pending_delayed_reviews(e)),1)
                self.assertEqual(len(pending_delayed_reviews(e)),1)
                assess.assert_not_called()

    def test_session_offers_pending_to_bounded_queue_without_changing_view(self):
        class Source:
            def collect(self,*args,**kwargs):return {'status':'SOURCE_INCOMPLETE','error':'SOURCE_TEST_ONLY'}
        with tempfile.TemporaryDirectory() as directory:
            source=Source();source.directory=Path(directory)/'private';source.directory.mkdir()
            session=Session(DAY,[SYMBOL],Path(directory)/'session',source,clock=lambda:f.parsed_time(DAY+'T13:35:00+08:00'))
            try:
                for record in records()[:2]:session.feed(record)
                session.feed(ref('close_reference_C',trade='13:33:00'))
                self.assertIn(('tse','2330'),session.queue.pending)
                self.assertEqual(session.last['research_candidate_count'],0)
                self.assertEqual(session.last['verified_count'],0)
                retry=ref('close_targeted_retry',server='13:34:15',trade='13:33:00',price='101')
                retry=json.loads(json.dumps(retry).replace('13:24:50','13:34:15'))
                session.feed(retry)
                self.assertNotIn(('tse','2330'),session.queue.pending)
            finally:session.close()


if __name__=='__main__':unittest.main()
