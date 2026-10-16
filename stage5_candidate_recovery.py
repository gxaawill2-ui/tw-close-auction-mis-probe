"""Restore the three privately archived candidate bundles on another runner.

Only safe diagnostics leave memory. No market provider calls or public writes.
"""
from datetime import datetime
import json
import os
from pathlib import Path
import freshness as f
from fast_selection import atomic
from stage5_runtime import Vault,restore_bundle
from stage5_audit import audit


def main():
    if os.getenv('GITHUB_REPOSITORY')!='gxaawill2-ui/tw-close-auction-mis-probe' or os.getenv('GITHUB_REF')!='refs/heads/stage4/20261016-fugle-probe':raise ValueError('REFUSE_OTHER_ENVIRONMENT')
    vault=Vault(os.getenv('STAGE5_PUBLISH_TOKEN'),os.getenv('STAGE5_DECISION_KEY'))
    results=[];seen=set();prior_runs=[]
    for filename in ('real-candidate-private-audit.json','real-remaining-candidate-audit.json'):
        prior=json.loads((Path('reports/2026-10-16-stage5')/filename).read_text())
        if prior.get('trade_date')!='2026-10-16' or prior.get('run_id')==os.getenv('GITHUB_RUN_ID'):raise ValueError('REQUIRE_DIFFERENT_PRIOR_RUN')
        prior_runs.append(prior['run_id'])
        for original in prior['audits']:
            ident=original.get('private_manifest_id')
            if not ident or ident in seen:raise ValueError('MISSING_OR_DUPLICATE_CANDIDATE_MANIFEST')
            seen.add(ident)
            candidate={'code':original['symbol'],'ex':original['exchange']}
            bundle=restore_bundle(vault,'2026-10-16',ident)
            result=audit(bundle,candidate,'2026-10-16',datetime.now(f.TZ).isoformat())
            result.pop('pre_tick_time',None)
            result['private_manifest_id']=ident
            if result.get('private_evidence_recoverable_after_job') is not True or result.get('row_count')!=original.get('row_count'):
                raise ValueError('PRIVATE_CANDIDATE_RESTORE_FAILED')
            results.append(result)
    if len(results)!=3:raise ValueError('EXPECTED_THREE_DISTINCT_CANDIDATE_BUNDLES')
    report={'scope':'REAL_THREE_CANDIDATE_PRIVATE_RAW_RECOVERED_ON_DIFFERENT_RUNNER_NO_RAW_PUBLIC',
        'status':'RECOVERED','run_id':os.getenv('GITHUB_RUN_ID'),'source_commit':os.getenv('GITHUB_SHA'),
        'prior_capture_runs':prior_runs,'recovered_at':datetime.now(f.TZ).isoformat(),
        'recovered_candidates':len(results),'results':results,'fugle_requests':0,
        'public_market_data_written':False,'verified_count':0}
    output=Path('stage5-candidate-recovery-report');output.mkdir(exist_ok=True)
    atomic(output/'recovered.json',report);print(json.dumps(report,indent=2));return report


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'status':'PRIVATE_CANDIDATE_RECOVERY_NOT_PASSED','error_type':type(exc).__name__}));raise SystemExit(1)
