"""One-off same-day isolated shadow acceptance, using ONLY the existing MIS artifact.

No collector/dispatch/cron writes and no additional MIS requests. Bounded Fugle
requests use the existing private archive and durable budget. This still has the
artifact barrier; LIVE verification contract is deliberately not released.
"""
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.error
import urllib.request

import freshness as f
import official_retry
from fast_selection import atomic
from stage3_publication import Publisher,BackgroundPublisher,CLOUD_CLIENT
from stage4_remote_watch import watch,capture_path
from stage5_runtime import Source,Vault,BASE,NoRedirect
from stage5_archive import probe
from stage5_session import Session,pending_delayed_reviews
from stage6_daily import DurableBudget
from stage3_ticks import LIVE_CONTRACT

REPO='gxaawill2-ui/tw-close-auction-mis-probe'
DATE='2026-10-19'
PRODUCER='STAGE7_ONE_OFF_ARTIFACT_SHADOW'


def guard(date,now):
    if date!=DATE or now.astimezone(f.TZ).date().isoformat()!=date or not f.parsed_time(date+'T12:45:00+08:00')<=now<f.parsed_time(date+'T13:40:00+08:00'):
        raise ValueError('ONE_OFF_TRADE_DATE_OR_START_WINDOW_REJECTED')


def ordered_records(summary,snapshots,probes,date):
    if summary.get('trade_date')!=date:raise ValueError('ARTIFACT_DATE_MISMATCH')
    records=[r for s in snapshots for r in s['records']]+probes
    if len(records)>1200:raise ValueError('ARTIFACT_RECORD_BUDGET')
    return sorted(records,key=lambda r:r.get('received_at') or '')


class ArtifactSession(Session):
    def __init__(self,*args,provenance,**kwargs):
        self.artifact_provenance=provenance
        super().__init__(*args,**kwargs)
        self.engine.mode='SAVED_CAPTURE_ANALYSIS'
    def compile(self):
        # No publication of intermediate catch-up views, and no provider values
        # in public provenance. Keep source/analysis/write/read clocks separate.
        publisher=self.publisher;self.publisher=None
        try:view=super().compile()
        finally:self.publisher=publisher
        view['provenance'].update(self.artifact_provenance)
        atomic(self.directory/'stage3-results.json',view)
        if publisher and self.clock()>=f.parsed_time(self.date+'T13:30:00+08:00'):publisher.submit(view)
        return view


def public_read(vault,date):
    req=urllib.request.Request(BASE+'/data?date='+date,headers={'User-Agent':CLOUD_CLIENT,'Accept':'application/json','Cache-Control':'no-cache'})
    try:
        with vault.opener(req,timeout=6) as r:
            raw=r.read(150001)
            if r.status!=200 or len(raw)>150000:raise ValueError('PUBLIC_READ_REJECTED')
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        if e.code==404:return None
        raise


def main():
    if os.getenv('GITHUB_REPOSITORY')!=REPO or os.getenv('GITHUB_REF')!='refs/heads/stage4/20261016-fugle-probe':raise ValueError('REFUSE_OTHER_ENVIRONMENT')
    request=json.loads(Path('stage7_live.request.json').read_text());date=request.get('trade_date')
    guard(date,datetime.now(f.TZ))
    if LIVE_CONTRACT.live_release:raise ValueError('ONE_OFF_UNRELEASED_CONTRACT_EXPECTED_REVIEW_REQUIRED')
    if request.get('scope')!='ISOLATED_ONE_OFF_EXISTING_FORMAL_ARTIFACT_SHADOW':raise ValueError('REQUEST_SCOPE_REJECTED')
    out=Path('stage7-live-safe-report');out.mkdir(exist_ok=True)
    report={'scope':PRODUCER,'trade_date':date,'observer_run_id':os.getenv('GITHUB_RUN_ID'),
        'commit':os.getenv('GITHUB_SHA'),'armed_at':datetime.now(f.TZ).isoformat(),'formal_modified':False,
        'mis_requests':0,'artifact_barrier':True,'verified_count':0,'physical_phone_tested':False,
        'contract_live_released':False,'first_research_at':None,'first_cloud_write_at':None,'first_api_read_at':None}
    atomic(out/'acceptance.json',report)
    v=Vault(os.getenv('STAGE5_PUBLISH_TOKEN'),os.getenv('STAGE5_DECISION_KEY'))
    with tempfile.TemporaryDirectory(prefix='stage7-private-shadow-') as temporary:
        root=Path(temporary);os.chmod(root,0o700)
        result=watch(date,root/'formal')
        if result is None:
            report.update(status='NO_VALID_FORMAL_ARTIFACT_BY_TARGET_DEADLINE',finished_at=datetime.now(f.TZ).isoformat())
            atomic(out/'acceptance.json',report);return report
        observed=json.loads((root/'formal'/'first-capture-result.json').read_text())
        receipt=json.loads((root/'formal'/'download-receipt.json').read_text())
        archives=list((root/'formal').glob('capture-artifact-*.zip'))
        if len(archives)!=1:raise ValueError('AMBIGUOUS_FORMAL_ARTIFACT')
        source_path=root/'formal'/'inner-capture.zip'
        if not source_path.exists():source_path=capture_path(archives[0],root/'formal')
        summary,universe,snapshots,probes=official_retry.load_capture(source_path.read_bytes())
        records=ordered_records(summary,snapshots,probes,date)
        prior=public_read(v,date)
        provenance={'producer':PRODUCER,'source_run_id':str(observed['source_run_id']),
            'artifact_id':receipt['artifact_id'],'artifact_sha256':receipt['sha256'],
            'artifact_received_at':receipt['received_at'],'artifact_barrier':True,
            'observer_run_id':os.getenv('GITHUB_RUN_ID'),'historical_publication_time_inferred':False}
        if prior and (prior.get('provenance',{}).get('producer')!=PRODUCER or str(prior['provenance'].get('source_run_id'))!=provenance['source_run_id']):
            report.update(status='OTHER_EXISTING_WRITER_PRESERVED',existing_version=prior.get('version'))
            atomic(out/'acceptance.json',report);return report
        probe(v,date);budget=DurableBudget(v,date)
        provider=Source(os.getenv('FUGLE_API_KEY'),root/'fugle',v,require_durable=True,reservation=budget,max_requests=160,min_interval=1.3)
        budget.restore_proofs(provider.directory,universe)
        session=ArtifactSession(date,universe,root/'session',provider,provenance=provenance)
        if prior:session.pipeline.version=max(session.pipeline.version,prior['version'])
        publisher=Publisher(BASE,root/'outbox',publish_token=v.token,decision_key=v.key,opener=v.opener)
        try:
            # Saved batch replay completes before queue workers or cloud writes.
            for record in records:session.feed(record)
            session.publisher=BackgroundPublisher(publisher,session.deadline)
            session.compile()
            last_version=None
            while datetime.now(f.TZ)<session.deadline:
                try:session.tick()
                except ValueError:
                    if datetime.now(f.TZ)>=session.deadline:break
                    raise
                if session.last and session.last['version']!=last_version:
                    view=session.last;last_version=view['version']
                    report.update(universe_count=len(universe),screening_calculable_count=view['screening_calculable_count'],
                        screening_unresolved_count=view['screening_unresolved_count'],research_count=view['research_count'],
                        unknown_candidate_count=view['unknown_candidate_count'],verified_count=view['verified_count'],
                        pending_delayed_reviews=len(pending_delayed_reviews(session.engine)),fugle_requests=provider.count,
                        first_research_at=session.first_research,last_analysis_at=view['generated_at'])
                    atomic(out/'research-view.json',view)
                    atomic(out/'acceptance.json',report)
                # Anonymous read timestamp proves API delivery only, never phone.
                if report.get('first_api_read_at') is None:
                    try:
                        saved=public_read(v,date)
                        if saved and saved.get('provenance',{}).get('observer_run_id')==os.getenv('GITHUB_RUN_ID'):
                            report.update(first_cloud_write_at=saved['public_written_at'],first_api_read_at=datetime.now(f.TZ).isoformat(),first_read_version=saved['version'])
                            atomic(out/'acceptance.json',report)
                    except (OSError,ValueError):pass
                time.sleep(.5)
            report.update(status='ISOLATED_SHADOW_WINDOW_ENDED',finished_at=datetime.now(f.TZ).isoformat(),fugle_requests=provider.count,
                source_run_id=provenance['source_run_id'],artifact_id=receipt['artifact_id'],
                official_final_audit='SEPARATE_EXISTING_FORMAL_AUDIT_NOT_RUN_BY_THIS_JOB')
            atomic(out/'acceptance.json',report)
            # Audits contain boolean diagnostics and hashes, never provider raw.
            atomic(out/'private-audit-safe.json',{'scope':'SAFE_DIAGNOSTICS_ONLY','results':list(session.audits.values())})
            print(json.dumps(report),flush=True)
        finally:
            session.close()
            atomic(out/'publication-receipts-safe.json',{'scope':'ACTUAL_PUBLIC_WRITE_RECEIPTS_NOT_PHONE_READS','receipts':publisher.receipts})
            atomic(out/'private-audit-safe.json',{'scope':'SAFE_DIAGNOSTICS_ONLY','results':list(session.audits.values())})
    return report

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'status':'ISOLATED_SHADOW_STOPPED_FORMAL_UNAFFECTED','error_type':type(exc).__name__}),flush=True)
        raise SystemExit(1)
