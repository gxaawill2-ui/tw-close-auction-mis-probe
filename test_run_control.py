import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import probe
import run_control as control


class ControlTests(unittest.TestCase):
    def test_dry_success_cannot_mask_missing_live(self):
        now=datetime(2026,9,30,13,41,tzinfo=probe.TZ)
        body=control.render(now,{}, {'status':'dry_run_success'}, {})
        self.assertTrue(body.startswith('# ❌ FAILED'))
        self.assertIn('dry-run 不會把上方當日失敗改成成功',body)

    def test_old_success_cannot_mask_today(self):
        now=datetime(2026,10,1,13,41,tzinfo=probe.TZ)
        body=control.render(now,{'trade_date':'2026-09-30','status':'success_raw_capture'}, {}, {})
        self.assertIn('當日漏跑',body)

    def test_dedup_completed_and_partial_capture(self):
        self.assertTrue(control.skip_existing({'status':'success_raw_capture'}))
        self.assertTrue(control.skip_existing({'status':'failed','preclose_captured':True}))
        self.assertFalse(control.skip_existing({'status':'failed','preclose_captured':False}))

    def test_late_runner_never_fetches_market(self):
        now=datetime(2026,10,1,13,24,46,tzinfo=probe.TZ)
        with tempfile.TemporaryDirectory() as d, patch.object(probe,'now_tpe',return_value=now), \
             patch.object(control,'receipt'),patch.object(control,'read_state',return_value=({},None)), \
             patch.object(control,'merge_state') as state,patch.object(control,'publish'), \
             patch.object(probe,'fetch_universe') as universe,patch.object(probe,'fetch_mis') as mis, \
             patch.dict('os.environ',{'RUNNER_STARTED_AT':now.isoformat(),'GITHUB_RUN_ID':'test'}):
            self.assertEqual(control.run('live',Path(d)),2)
            universe.assert_not_called();mis.assert_not_called()
            self.assertEqual(state.call_args[0][1]['status'],'failed_late_start')

    def test_late_ready_never_captures(self):
        now=datetime(2026,10,1,13,24,46,tzinfo=probe.TZ)
        symbols=[dict(ex=ex,code=code,market='test',name='fixture') for ex,code in probe.FIXED_PROBE]
        with tempfile.TemporaryDirectory() as d,patch.object(probe,'now_tpe',return_value=now), \
             patch.object(probe,'github_issue'),patch.object(probe,'fetch_universe',return_value=symbols), \
             patch.object(probe,'snapshot') as snapshot, \
             patch.dict('os.environ',{'RUNNER_STARTED_AT':'2026-10-01T13:07:00+08:00'}):
            with self.assertRaisesRegex(RuntimeError,'failed_late_ready'):probe.live(Path(d))
            snapshot.assert_not_called()

if __name__=='__main__':unittest.main()
