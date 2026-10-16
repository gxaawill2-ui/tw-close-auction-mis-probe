"""One saved MIS delayed-close case; private diagnostic, never publication.

This is a new observation at its real request time, not a 13:35 reconstruction.
At most six additional provider requests, with no MIS calls or public writes.
"""
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sys
import tempfile

import freshness as f
from fast_selection import atomic
from stage5_runtime import Source, Vault, restore_bundle
from stage5_audit import audit

DATE = '2026-10-16'
CANDIDATE = {'code': '5546', 'ex': 'tse'}


def guard(now, recovery=False):
    if os.getenv('GITHUB_REPOSITORY') != 'gxaawill2-ui/tw-close-auction-mis-probe' or os.getenv('GITHUB_REF') != 'refs/heads/stage4/20261016-fugle-probe':
        raise ValueError('REFUSE_OTHER_ENVIRONMENT')
    if now.date().isoformat() != DATE:
        raise ValueError('NO_HISTORICAL_LIVE_CAPTURE')
    if not recovery and not f.parsed_time(DATE+'T13:55:00+08:00') <= now < f.parsed_time(DATE+'T14:20:00+08:00'):
        raise ValueError('OUTSIDE_BOUNDED_DIAGNOSTIC_WINDOW')


def main(recovery_path=None):
    now = datetime.now(f.TZ)
    guard(now, bool(recovery_path))
    vault = Vault(os.getenv('STAGE5_PUBLISH_TOKEN'), os.getenv('STAGE5_DECISION_KEY'))
    if recovery_path:
        prior = json.loads(Path(recovery_path).read_text())
        if prior.get('trade_date') != DATE or prior.get('symbol') != CANDIDATE['code'] or prior.get('source_job_id') == os.getenv('GITHUB_JOB'):
            raise ValueError('REQUIRE_SEPARATE_CAPTURE_JOB')
        ident = prior['diagnostic']['private_manifest_id']
        bundle = restore_bundle(vault, DATE, ident)
        requests = 0
    else:
        deadline = min(now+timedelta(minutes=3), f.parsed_time(DATE+'T14:23:00+08:00'))
        with tempfile.TemporaryDirectory(prefix='stage5-delayed-private-') as temporary:
            source = Source(os.getenv('FUGLE_API_KEY'), Path(temporary)/'raw', vault,
                            max_requests=6, min_interval=10.1, require_durable=True)
            bundle = source.collect(CANDIDATE, DATE, deadline, max_pages=2)
            requests = source.count
        ident = bundle.get('private_manifest_receipt', {}).get('id')
    at = datetime.now(f.TZ).isoformat()
    diagnostic = audit(bundle, CANDIDATE, DATE, at)
    diagnostic.pop('pre_tick_time', None)
    diagnostic['private_manifest_id'] = ident
    if not ident or not diagnostic.get('private_evidence_recoverable_after_job'):
        raise ValueError('DURABLE_DELAYED_SAMPLE_NOT_PROVEN')
    report = {'scope': 'LATE_ACTUAL_DELAYED_SAMPLE_NOT_TARGET_TIME_VERIFICATION',
              'trade_date': DATE, 'symbol': CANDIDATE['code'], 'source_formal_run': '38853538676',
              'run_id': os.getenv('GITHUB_RUN_ID'), 'source_commit': os.getenv('GITHUB_SHA'),
              'source_job_id': os.getenv('GITHUB_JOB'), 'observed_at': at,
              'fugle_requests': requests, 'mis_requests': 0, 'public_writes': 0,
              'verified_count': 0, 'diagnostic': diagnostic,
              'different_runner_recovery': bool(recovery_path)}
    output = Path('stage5-delayed-recovery-report' if recovery_path else 'stage5-delayed-report')
    output.mkdir(exist_ok=True)
    atomic(output/'safe.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    try:
        main(sys.argv[1] if len(sys.argv) > 1 else None)
    except Exception as exc:
        print(json.dumps({'status': 'DELAYED_SAMPLE_NOT_PASSED', 'error_type': type(exc).__name__}))
        raise SystemExit(1)
