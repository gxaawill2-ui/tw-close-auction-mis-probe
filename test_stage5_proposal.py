"""Exercise proposed formal changes without editing or running the formal collector."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch


PROPOSED=Path(__file__).parent/'reports/2026-10-16-stage5/proposed'


def load(name,file):
    spec=importlib.util.spec_from_file_location(name,PROPOSED/file)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


class ProposedJournalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.journal=load('stage5_capture_journal','stage5_capture_journal.py')
        cls.collector=load('stage5_proposed_formal_probe','probe_with_journal.py')

    def test_new_journal_cannot_write_public_checkout(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'RUNNER_TEMP':tmp}):
            for path in (tmp,Path(__file__).parent/'docs'):
                with self.assertRaises(ValueError):self.journal.Journal(path)
            journal=self.journal.Journal(Path(tmp)/'journal')
            at=self.collector.iso()
            event=journal.append({'received_at':at})
            from fast_capture_journal import verify
            self.assertEqual(verify(event,journal.path),event)
            self.assertFalse(event['pre_finality_proven'])
            self.assertEqual(journal.raw.stat().st_mode&0o777,0o600)

    def test_proposed_callback_saves_fast_batch_before_slow_batch_and_preserves_legacy_order(self):
        collector=self.collector;gate=threading.Event();order=[]
        symbols=[{'ex':'tse','code':'2330'},{'ex':'tse','code':'2317'}]
        def fetch(group,*args):
            if group[0]['code']=='2330':gate.wait(.5)
            return collector.FetchResult(collector.iso(),collector.iso(),1,200,0,None,None,{'msgArray':[]})
        def append(record):
            order.append(record['symbols'][0]['code'])
            if order[-1]=='2317':gate.set()
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'RUNNER_TEMP':tmp,'MIS_FAST_JOURNAL_DIR':str(Path(tmp)/'journal')}),patch.object(collector,'BATCH_SIZE',1),patch.object(collector,'fetch_mis',side_effect=fetch),patch.object(self.journal.Journal,'append',side_effect=append):
            result=collector.snapshot('close_reference_A',collector.now_tpe(),symbols,Path(tmp))
        self.assertEqual(order,['2317','2330']);self.assertEqual([r['batch_no'] for r in result['records']],[1,2])

    def test_journal_failure_is_fail_open_for_formal_capture(self):
        collector=self.collector
        def fetch(*args):return collector.FetchResult(collector.iso(),collector.iso(),1,200,0,None,None,{'msgArray':[]})
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'RUNNER_TEMP':tmp,'MIS_FAST_JOURNAL_DIR':str(Path(tmp)/'journal')}),patch.object(collector,'BATCH_SIZE',1),patch.object(collector,'fetch_mis',side_effect=fetch),patch.object(self.journal.Journal,'append',side_effect=OSError('synthetic disk failure')):
            result=collector.snapshot('close_reference_A',collector.now_tpe(),[{'ex':'tse','code':'2330'},{'ex':'tse','code':'2317'}],Path(tmp))
            self.assertEqual(len(result['records']),2)
            self.assertTrue((Path(tmp)/'close_reference_A_raw.jsonl').exists())


if __name__=='__main__':unittest.main()
