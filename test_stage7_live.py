from datetime import datetime
from pathlib import Path
import tempfile
import unittest
import freshness as f
from stage7_live import guard,ordered_records,ArtifactSession,DATE,PRODUCER
from test_fast_selection import records
from test_convergence import SYMBOL
class FakeSource:
    def __init__(self,directory):
        self.directory=directory;directory.mkdir();self.calls=[]
    def collect(self,*a,**kw):self.calls.append(a);raise AssertionError('NO_REQUEST_DURING_REPLAY')

class LivePreparationTests(unittest.TestCase):
    def test_one_off_window_exact_day_and_no_late_replay(self):
        guard(DATE,f.parsed_time(DATE+'T13:00:00+08:00'))
        for stamp in ('2026-10-16T13:00:00+08:00',DATE+'T12:44:59+08:00',DATE+'T13:40:00+08:00'):
            with self.assertRaises(ValueError):guard(DATE,f.parsed_time(stamp))
        with self.assertRaises(ValueError):guard('2026-10-20',f.parsed_time('2026-10-20T13:00:00+08:00'))
    def test_artifact_scope_and_sorted_replay(self):
        with self.assertRaises(ValueError):ordered_records({'trade_date':'bad'},[],[],DATE)
        r=ordered_records({'trade_date':DATE},[{'records':[{'received_at':'b'},{'received_at':'a'}]}],[],DATE)
        self.assertEqual([a['received_at'] for a in r],['a','b'])
        with self.assertRaises(ValueError):ordered_records({'trade_date':DATE},[{'records':[{}]*1201}],[],DATE)
    def test_replay_has_no_provider_requests_or_publication_before_full_catchup(self):
        # Historical synthetic fixture, injected clock. This is not live evidence.
        from test_close_research import DAY
        with tempfile.TemporaryDirectory() as tmp:
            source=FakeSource(Path(tmp)/'source')
            s=ArtifactSession(DAY,[SYMBOL],Path(tmp)/'session',source,clock=lambda:f.parsed_time(DAY+'T13:35:00+08:00'),provenance={'producer':PRODUCER,'artifact_barrier':True})
            try:
                for r in records()[:3]:s.feed(r)
                self.assertEqual(source.calls,[])
                self.assertIsNone(s.publisher);self.assertEqual(s.last['verified_count'],0)
                self.assertEqual(s.last['provenance']['producer'],PRODUCER)
                self.assertTrue(s.last['provenance']['artifact_barrier'])
            finally:s.close()
