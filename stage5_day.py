"""One-date isolated real capture; public output is sanitized metadata only.

Uses the existing formal MIS artifact. No MIS request, no dispatch, no production write.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.request

import freshness as f
import official_retry
from fast_selection import atomic
from stage4_remote_watch import watch as watch_formal
from stage5_runtime import Source, Vault, LocalVault, BASE, NoRedirect
from stage5_audit import audit
from stage5_session import Session
from stage3_publication import Publisher

DATE='2026-10-16'
CONTROLS=[{'ex':'tse','code':'2330'},{'ex':'otc','code':'6488'}]


def now():return datetime.now(f.TZ)


def log(event, **fields):
    print(json.dumps({'event':event,'observed_at':now().isoformat(),**fields},ensure_ascii=False),flush=True)


def controls(source, private, report):
    phases=[('CONNECTION_AND_PRIVATE_STORAGE',None,1,True),
        ('BEFORE_CUTOFF','13:24:40',1,True),('AFTER_CUTOFF','13:25:08',16,False),
        ('NORMAL_CLOSE','13:30:10',3,True),('DELAYED_CLOSE','13:33:10',3,True),
        ('POST_CLOSE_STABILITY','13:35:10',3,True)]
    for name,clock,pages,tail in phases:
        target=f.parsed_time(DATE+'T'+clock+'+08:00') if clock else now()
        while now()<target:time.sleep(min(15,(target-now()).total_seconds()))
        if clock and (now()-target).total_seconds()>15:
            result={'phase':name,'status':'MISSED_REAL_CAPTURE_SLOT_NO_BACKFILL','observed_at':now().isoformat()}
            report['control_captures'].append(result);log('CONTROL_SLOT_MISSED',phase=name);continue
        deadline=now()+timedelta(seconds=150 if pages>3 else 45)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[(c,pool.submit(source.collect,c,DATE,deadline,max_pages=pages,tail_only=tail)) for c in CONTROLS]
            for c,future in futures:
                bundle=future.result()
                atomic(private/(name+'-'+c['code']+'-bundle.json'),bundle)
                result=audit(bundle,c,DATE,now().isoformat());result['phase']=name
                report['control_captures'].append(result)
                log('CONTROL_DIAGNOSTIC',phase=name,symbol=c['code'],status=result['status'],
                    pages=result.get('page_count'),rows=result.get('row_count'),
                    private_archive_recoverable=result.get('private_evidence_recoverable_after_job',False),reasons=result['reasons'])
        log('CONTROL_PHASE_COMPLETE',phase=name)


def cloud_resume(publisher,session,report):
    try:
        request=urllib.request.Request(BASE+'/data?date='+DATE,headers={'Cache-Control':'no-cache'})
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=6) as response:data=json.load(response)
        if data.get('trade_date')==DATE and isinstance(data.get('version'),int):
            session.pipeline.version=max(session.pipeline.version,data['version'])
            report['cloud_resume_version']=data['version']
    except Exception:report['cloud_resume_status']='NO_CURRENT_PUBLIC_VERSION_READ'


def main():
    if os.getenv('GITHUB_REPOSITORY')!='gxaawill2-ui/tw-close-auction-mis-probe' or os.getenv('GITHUB_REF')!='refs/heads/stage4/20261016-fugle-probe':
        raise ValueError('REFUSE_NONISOLATED_RUN')
    if now().date().isoformat()!=DATE or now()>=f.parsed_time(DATE+'T13:24:40+08:00'):
        raise ValueError('REAL_PRE_CUTOFF_ARMING_WINDOW_MISSED_NO_BACKFILL')
    public=Path('stage5-public-report');public.mkdir(exist_ok=True)
    report={'scope':'ONE_DATE_REAL_ISOLATED_CAPTURE_NO_PRODUCTION_CHANGE','trade_date':DATE,
        'run_id':os.getenv('GITHUB_RUN_ID'),'source_commit':os.getenv('GITHUB_SHA'),
        'armed_at':now().isoformat(),'formal_mis_recaptured':False,'production_modified':False,
        'control_symbols':[c['code'] for c in CONTROLS], 'controls_are_strategy_candidates':False,
        'control_captures':[],'verified_count':0,'first_research_at':None,'first_verified_at':None,
        'cloud_written_at':None,'external_phone_read_at':None,'desktop_browser_read_at':None,
        'official_reconciliation':'NOT_YET_OBSERVED','deployment_readiness':'NOT_PASSED',
        'limitations':['Formal journal is not enabled; saved artifact availability is a real barrier.',
            'No public Fugle raw artifacts. Runner-only fallback is not recoverable after job end.',
            'Source contract and live VERIFIED release remain closed.']}
    token,key=os.getenv('STAGE5_PUBLISH_TOKEN'),os.getenv('STAGE5_DECISION_KEY')
    vault=Vault(token,key) if token and key else LocalVault()
    report['private_storage_mode']='CLOUDFLARE_PRIVATE_VAULT' if token and key else 'RUNNER_PRIVATE_TEMPORARY_ONLY'
    # The raw directory is outside checkout and outside the sole uploaded artifact.
    with tempfile.TemporaryDirectory(prefix='stage5-private-') as temporary:
        private=Path(temporary);source=Source(os.getenv('FUGLE_API_KEY'),private/'fugle',vault,max_requests=160)
        log('ISOLATED_DAY_ARMED',private_storage_mode=report['private_storage_mode'],maximum_fugle_requests=160)
        atomic(public/'day-report.json',report)
        session=None
        with ThreadPoolExecutor(max_workers=2) as pool:
            control=pool.submit(controls,source,private,report)
            formal=pool.submit(watch_formal,DATE,private/'formal')
            imported=False
            while now()<f.parsed_time(DATE+'T14:29:30+08:00'):
                if not imported and formal.done():
                    imported=True
                    try:
                        result=formal.result()
                        archives=list((private/'formal').glob('capture-artifact-*.zip'))
                        inner=private/'formal'/'inner-capture.zip'
                        archive=inner if inner.exists() else archives[0] if archives else None
                        if result and archive:
                            summary,universe,snapshots,probes=official_retry.load_capture(archive.read_bytes())
                            if summary.get('trade_date')!=DATE:raise ValueError('FORMAL_DATE_MISMATCH')
                            publisher=Publisher(BASE,public/'publication',publish_token=token,decision_key=key,
                                opener=urllib.request.build_opener(NoRedirect()).open) if token and key else None
                            session=Session(DATE,universe,private/'session',source,publisher)
                            session.engine.mode='SAVED_CAPTURE_ANALYSIS'
                            if publisher:cloud_resume(publisher,session,report)
                            records=[r for snap in snapshots for r in snap['records']]+probes
                            records.sort(key=lambda r:r.get('received_at') or '')
                            # Import together, then compute NOW. Never pretend this was live at event time.
                            for record in records:session.engine.feed(record)
                            view=session.update()
                            report.update(universe_count=len(universe),screening_calculable_count=view['screening_calculable_count'],
                                research_candidate_count=len(view['rows']),first_research_at=session.first_research,
                                formal_capture_status=summary.get('status'),formal_capture_finished_at=summary.get('finished_at'),
                                formal_artifact_received_at=result['provenance']['capture_received_at'])
                            log('FORMAL_SAVED_CAPTURE_IMPORTED_NOW',universe_count=len(universe),
                                research_candidate_count=len(view['rows']),first_research_at=session.first_research)
                        else:report['formal_capture_status']='NO_SAVED_CAPTURE_AVAILABLE_BY_OBSERVER_DEADLINE'
                    except Exception as exc:
                        report['formal_capture_status']='SAVED_CAPTURE_IMPORT_FAILED_'+type(exc).__name__
                if session:
                    completed=session.tick()
                    if completed:
                        report['candidate_audits']=list(session.audits.values())
                        report['verified_count']=session.last['verified_count']
                        atomic(public/'research-view.json',session.last)
                        log('CANDIDATE_CHECK_FINISHED',completed_count=len(completed),verified_count=report['verified_count'])
                if control.done():
                    try:control.result()
                    except Exception as exc:report['control_capture_error_type']=type(exc).__name__
                report['last_updated_at']=now().isoformat();report['fugle_request_count']=source.count
                if session and session.publisher:
                    receipts=session.publisher.publisher.receipts
                    writes=[r['receipt']['public_written_at'] for r in receipts if r.get('receipt')]
                    report['cloud_written_at']=min(writes) if writes else None
                atomic(public/'day-report.json',report)
                time.sleep(1 if session else 10)
        if session:
            session.close()
            atomic(public/'research-view.json',session.last)
        report['finished_at']=now().isoformat();report['runner_raw_copy_destroyed_after_job']=True
        atomic(public/'day-report.json',report)
        log('ISOLATED_DAY_FINISHED',verified_count=report['verified_count'],fugle_request_count=source.count)
        print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        log('ISOLATED_DAY_FAILED_NO_RAW_OR_KEYS_LOGGED',error_type=type(exc).__name__)
        raise SystemExit(1)
