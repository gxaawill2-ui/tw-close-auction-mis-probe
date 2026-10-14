import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import official_retry


class OfficialStateTests(unittest.TestCase):
    def test_recheck_failure_is_persisted_as_pending_and_never_mutates_live(self):
        control=SimpleNamespace(read_state=Mock(return_value=({'status':'PENDING'},None)),merge_state=Mock(),publish=Mock())
        clock=SimpleNamespace(iso=lambda:'2026-10-14T14:50:00+08:00',package=Mock())
        with tempfile.TemporaryDirectory() as tmp,patch.object(official_retry,'_run',side_effect=TimeoutError('saved artifact unavailable')):
            code=official_retry.run('2026-10-14',Path(tmp),control,clock)
            result=json.loads((Path(tmp)/'validation_summary.json').read_text())
        self.assertEqual(code,5);self.assertEqual(result['status'],'PENDING_RECHECK_ERROR');self.assertFalse(result['in_progress'])
        self.assertEqual(control.merge_state.call_args_list[0].args[1]['status'],'RECHECKING')
        self.assertTrue(all(c.args[0]=='state/validation/2026-10-14.json' for c in control.merge_state.call_args_list))
        self.assertTrue(all('capture_outcome' not in c.args[1] for c in control.merge_state.call_args_list));clock.package.assert_called_once()
