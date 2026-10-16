"""Existing formal Artifact only. No MIS/Fugle/cloud publisher; no raw upload."""
from datetime import datetime
import json,os,tempfile
from pathlib import Path
import freshness as f
import official_retry,convergence,volume_evidence
from fast_selection import atomic
from stage4_remote_watch import watch,capture_path

DATE='2026-10-19'
REF='refs/heads/stage4/20261016-fugle-probe'

def guard(now):
    if os.getenv('GITHUB_REPOSITORY')!='gxaawill2-ui/tw-close-auction-mis-probe' or os.getenv('GITHUB_REF')!=REF:raise ValueError('ISOLATED_BRANCH_REQUIRED')
    if now.astimezone(f.TZ).date().isoformat()!=DATE or not f.parsed_time(DATE+'T12:45:00+08:00')<=now<f.parsed_time(DATE+'T13:40:00+08:00'):raise ValueError('ONE_OFF_WINDOW_ONLY')


def summarize(raw,at):
    summary,universe,snapshots,probes=official_retry.load_capture(raw)
    if summary.get('trade_date')!=DATE:raise ValueError('ARTIFACT_WRONG_DATE')
    report=convergence.build_report(DATE,snapshots,probes,universe,{'checks':[]})
    lookup={(r['ex'],r['code']):r for r in universe};rows=[]
    for candidate in convergence.research_candidates(report)['candidates']:
        volume=volume_evidence.assess(candidate,lookup[candidate['ex'],candidate['code']],snapshots,DATE,at)
        pair=candidate['close_research_evidence'].get('pair') or []
        multi=len(pair)==2 and pair[0]['server_time']<pair[1]['server_time'] and candidate['P_close_trade_time'] in ('13:30:00','13:33:00') and volume['volume_status']=='MIS_EVIDENCE_CONFIRMED'
        rows.append({'ex':candidate['ex'],'code':candidate['code'],'selection_status':'MIS_CONFIRMED' if multi else 'UNKNOWN',
            'basis':'EXISTING_MIS_MULTI_OBSERVATIONS_NOT_PRIVATE_V2','volume_status':volume['volume_status']})
    return {'trade_date':DATE,'scope':'EXISTING_FORMAL_ARTIFACT_MIS_ONLY_SHADOW','actually_calculated_at':at,
      'universe':len(universe),'calculable':report['research_calculable_count'],
      'unknown':len(universe)-report['research_calculable_count'],'candidates':rows,
      'new_market_requests':0,'fugle_required':False,'formal_writes':0,
      'private_v2_replay':'SEPARATE_PRIVATE_REVIEW_AT_1455','publication_success':False,
      'note':'Artifact barrier remains; observer calculation is not formal publication or browser/physical phone confirmation.'}


def main():
    now=datetime.now(f.TZ);guard(now)
    request=json.loads(Path('stage7_live.request.json').read_text())
    if request.get('scope')!='ISOLATED_ONE_OFF_EXISTING_FORMAL_ARTIFACT_SHADOW' or request.get('trade_date')!=DATE:raise ValueError('INVALID_REQUEST')
    requested=f.parsed_time(request.get('requested_at'))
    if not requested or not f.parsed_time(DATE+'T12:45:00+08:00')<=requested<=now:raise ValueError('INVALID_REQUEST_TIME')
    out=Path('stage7-live-safe-report');out.mkdir(exist_ok=True)
    # All downloaded raw and intermediate files are temporary and excluded from Artifact.
    with tempfile.TemporaryDirectory(prefix='mis-only-private-') as directory:
        root=Path(directory);watch(DATE,root/'watch')
        receipt_path=root/'watch'/'download-receipt.json'
        if not receipt_path.exists():raise ValueError('NO_SAVED_FORMAL_ARTIFACT')
        receipt=json.loads(receipt_path.read_text());source=capture_path(root/'watch'/receipt['raw_file'],root)
        result=summarize(source.read_bytes(),datetime.now(f.TZ).isoformat())
        result['provenance']={k:receipt[k] for k in ('artifact_id','sha256','received_at','persisted_at')}
        atomic(out/'mis-only-acceptance.json',result)
        print(json.dumps({'status':'MIS_ONLY_ARTIFACT_ANALYZED','date':DATE,'candidate_count':len(result['candidates']),'at':result['actually_calculated_at']}))
    return result
if __name__=='__main__':main()
