import os
import unittest
from unittest.mock import patch
import freshness as f
import stage5_delayed_sample as sample


class WindowTests(unittest.TestCase):
    def test_only_isolated_branch(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY':'gxaawill2-ui/tw-close-auction-mis-probe', 'GITHUB_REF':'refs/heads/main'}):
            with self.assertRaisesRegex(ValueError, 'REFUSE_OTHER_ENVIRONMENT'):
                sample.guard(f.parsed_time('2026-10-16T14:00:00+08:00'))

    def test_expired_or_early_capture_refused(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY':'gxaawill2-ui/tw-close-auction-mis-probe', 'GITHUB_REF':'refs/heads/stage4/20261016-fugle-probe'}):
            for when in ('2026-10-16T13:54:59+08:00','2026-10-16T14:20:00+08:00','2026-10-19T14:00:00+08:00'):
                with self.subTest(when=when), self.assertRaises(ValueError):
                    sample.guard(f.parsed_time(when))
            sample.guard(f.parsed_time('2026-10-16T14:00:00+08:00'))

    def test_same_job_recovery_refused_before_private_read(self):
        import tempfile, json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'safe.json'
            path.write_text(json.dumps({'trade_date':'2026-10-16','symbol':'5546','source_job_id':'capture_delayed'}))
            with patch.dict(os.environ, {'GITHUB_REPOSITORY':'gxaawill2-ui/tw-close-auction-mis-probe', 'GITHUB_REF':'refs/heads/stage4/20261016-fugle-probe', 'GITHUB_JOB':'capture_delayed'}), patch.object(sample,'Vault') as vault, patch.object(sample,'datetime') as clock:
                clock.now.return_value=f.parsed_time('2026-10-16T14:00:00+08:00')
                with self.assertRaisesRegex(ValueError,'REQUIRE_SEPARATE_CAPTURE_JOB'):
                    sample.main(str(path))
                vault.return_value.read.assert_not_called()


if __name__=='__main__':unittest.main()
