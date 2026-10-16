"""Existing formal MIS artifact -> isolated research publication; no Fugle calls.

This does not overcome the formal artifact barrier or independently verify a
stock. Actual analysis/write/read times are recorded without historical replay.
"""
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import urllib.error
import urllib.request
import freshness as f
import official_retry
from fast_selection import Engine,atomic
from stage3_selection import Pipeline
from stage3_publication import Publisher,CLOUD_CLIENT
from stage5_runtime import public_view,BASE,NoRedirect
from stage4_remote_watch import watch,capture_path

DATE='2026-10-16'
EXPECTED_FORMAL_RUN='38853538676'


def make_view(date,summary,universe,snapshots,probes,directory,as_of):
    if summary.get('trade_date')!=date:raise ValueError('ARTIFACT_DATE_MISMATCH')
    engine=Engine(date,universe,directory,'SAVED_CAPTURE_ANALYSIS')
    records=[record for snap in snapshots for record in snap['records']]+probes
    records.sort(key=lambda r:r.get('received_at') or '')
    for record in records:engine.feed(record)
    pipeline=Pipeline(engine,mode='LIVE')
    view=public_view(pipeline.compile(as_of))
    if view['verified_count'] or any(r.get('validated') or r.get('verification_status')=='VERIFIED' for r in view['rows']):
        raise ValueError('ARTIFACT_PUBLISHER_CANNOT_RELEASE_VERIFIED')
    view['version']=int(f.parsed_time(as_of).timestamp()*1000)*1000
    return view


def main():
    if os.getenv('GITHUB_REPOSITORY')!='gxaawill2-ui/tw-close-auction-mis-probe' or os.getenv('GITHUB_REF')!='refs/heads/stage4/20261016-fugle-probe':raise ValueError('REFUSE_OTHER_ENVIRONMENT')
    if datetime.now(f.TZ).date().isoformat()!=DATE:raise ValueError('NO_HISTORICAL_PUBLICATION')
    output=Path('stage5-artifact-publisher-report');output.mkdir(exist_ok=True)
    deadline=f.parsed_time(DATE+'T13:40:00+08:00')
    report={'scope':'ACTUAL_SAVED_MIS_RESEARCH_TO_ISOLATED_CLOUD_NOT_INDEPENDENT_VERIFICATION',
        'trade_date':DATE,'run_id':os.getenv('GITHUB_RUN_ID'),'source_commit':os.getenv('GITHUB_SHA'),
        'armed_at':datetime.now(f.TZ).isoformat(),'formal_journal_enabled':False,'artifact_barrier':True,
        'mis_requests':0,'fugle_requests':0,'production_modified':False,'verified_count':0,
        'first_research_at':None,'cloud_written_at':None,'anonymous_read_at':None,'physical_phone_verified':False}
    atomic(output/'publisher-day.json',report)
    print(json.dumps({'event':'MIS_ARTIFACT_PUBLISHER_ARMED','armed_at':report['armed_at'],'expected_formal_run':EXPECTED_FORMAL_RUN}),flush=True)
    with tempfile.TemporaryDirectory(prefix='stage5-mis-artifact-private-') as temporary:
        root=Path(temporary)
        result=watch(DATE,root/'formal')
        if not result:
            report.update(status='NO_VALID_ARTIFACT_AVAILABLE_BY_OBSERVER_DEADLINE',finished_at=datetime.now(f.TZ).isoformat())
            atomic(output/'publisher-day.json',report);return report
        observed=json.loads((root/'formal'/'first-capture-result.json').read_text())
        if str(observed['source_run_id'])!=EXPECTED_FORMAL_RUN:raise ValueError('REFUSE_OTHER_FORMAL_CAPTURE_OWNER')
        receipt=json.loads((root/'formal'/'download-receipt.json').read_text())
        archives=list((root/'formal').glob('capture-artifact-*.zip'))
        if len(archives)!=1:raise ValueError('AMBIGUOUS_FORMAL_ARTIFACT')
        archive=root/'formal'/'inner-capture.zip'
        if not archive.exists():archive=archives[0]
        summary,universe,snapshots,probes=official_retry.load_capture(archive.read_bytes())
        at=datetime.now(f.TZ).isoformat()
        if datetime.now(f.TZ)>=deadline:raise ValueError('PUBLICATION_TARGET_WINDOW_ENDED')
        view=make_view(DATE,summary,universe,snapshots,probes,root/'engine',at)
        view['provenance']={'kind':'SAME_DAY_SAVED_CAPTURE_ANALYSIS','artifact_barrier':True,
            'source_run_id':EXPECTED_FORMAL_RUN,'artifact_id':receipt['artifact_id'],'artifact_sha256':receipt['sha256'],
            'artifact_received_at':receipt['received_at'],'first_research_program_observed_at':at if view['rows'] else None,
            'historical_publication_time_inferred':False,'fugle_independent_validation_completed':False}
        opener=urllib.request.build_opener(NoRedirect()).open
        def read():
            req=urllib.request.Request(BASE+'/data?date='+DATE,headers={'User-Agent':CLOUD_CLIENT,'Accept':'application/json','Cache-Control':'no-cache'})
            with opener(req,timeout=6) as response:
                if response.status!=200:raise ValueError('PUBLIC_READ_UNEXPECTED_STATUS')
                return json.loads(response.read(131073))
        try:existing=read()
        except urllib.error.HTTPError as exc:
            if exc.code!=404:raise ValueError('CANNOT_READ_CURRENT_PUBLIC_VERSION') from None
            existing=None
        if existing:
            # This one-shot observer never overwrites an existing newer/live writer.
            report.update(status='EXISTING_PUBLIC_RESULT_PRESERVED_NO_OVERWRITE',existing_version=existing.get('version'))
            atomic(output/'publisher-day.json',report);return report
        publisher=Publisher(BASE,root/'publisher',publish_token=os.getenv('STAGE5_PUBLISH_TOKEN'),
            decision_key=os.getenv('STAGE5_DECISION_KEY'),opener=opener)
        write=publisher.publish(view,deadline)
        if write['status']!='WRITTEN':raise ValueError('RESEARCH_PUBLICATION_NOT_WRITTEN')
        saved=read()
        if saved.get('sha256')!=write['sha256'] or saved.get('version')!=view['version']:raise ValueError('RESEARCH_PUBLIC_READ_VERSION_HASH_MISMATCH')
        report.update(status='RESEARCH_ONLY_PUBLISHED' if view['rows'] else 'NO_RESEARCH_CANDIDATES_PUBLISHED',
            source_formal_run_id=EXPECTED_FORMAL_RUN,artifact_id=receipt['artifact_id'],artifact_sha256=receipt['sha256'],
            artifact_received_at=receipt['received_at'],formal_capture_finished_at=summary.get('finished_at'),
            universe_count=len(universe),screening_calculable_count=view['screening_calculable_count'],
            research_candidate_count=len(view['rows']),first_research_at=at if view['rows'] else None,
            cloud_written_at=write['receipt']['public_written_at'],anonymous_read_at=datetime.now(f.TZ).isoformat(),
            published_version=view['version'],public_sha256=write['sha256'],raw_fugle_data_published=False)
        atomic(output/'research-view.json',view);atomic(output/'publisher-day.json',report)
        print(json.dumps(report,indent=2));return report


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'event':'MIS_ARTIFACT_PUBLISHER_STOPPED','error_type':type(exc).__name__}));raise SystemExit(1)
