import os,unittest
from unittest.mock import patch
from pathlib import Path
import freshness as f
from stage8_mis_shadow import guard,DATE
class Shadow(unittest.TestCase):
 def test_same_isolation_branch_and_exact_window(self):
  with patch.dict(os.environ,{'GITHUB_REPOSITORY':'gxaawill2-ui/tw-close-auction-mis-probe','GITHUB_REF':'refs/heads/stage4/20261016-fugle-probe'}):
   guard(f.parsed_time(DATE+'T13:00:00+08:00'))
   for at in ('2026-10-16T13:00:00+08:00',DATE+'T13:40:00+08:00'):
    with self.assertRaises(ValueError):guard(f.parsed_time(at))
  with patch.dict(os.environ,{'GITHUB_REPOSITORY':'gxaawill2-ui/tw-close-auction-mis-probe','GITHUB_REF':'refs/heads/main'}):
   with self.assertRaises(ValueError):guard(f.parsed_time(DATE+'T13:00:00+08:00'))
 def test_workflow_has_only_read_permissions_and_safe_output_no_secret(self):
  source=Path('.github/workflows/stage7-live-shadow.yml').read_text()
  self.assertNotIn('secrets.',source);self.assertNotIn('schedule:',source)
  self.assertIn('contents: read',source);self.assertIn('actions: read',source)
  self.assertIn('path: stage7-live-safe-report/',source);self.assertNotIn('stage4-runtime/',source)
if __name__=='__main__':unittest.main()
