"""Two real MIS research candidates -> private Fugle audit -> safe cloud updates.

Runs after the small control captures, <=6 added requests/minute, <=60 total.
The existing formal collector/original source are never changed or restarted.
"""
from datetime import datetime,timedelta
import copy
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.error
import urllib.request
import freshness as f
from fast_selection import atomic
from stage3_selection import decide
from stage3_publication import Publisher,CLOUD_CLIENT
from stage5_runtime import BASE,NoRedirect,Vault,Source,FairQueue,public_view
from stage5_archive import probe
from stage5_audit import audit

DATE='2026-10-16'


def compile_update(current,initial,bundle,as_of):
    if current.get('mode')!='LIVE' or current.get('trade_date')!=DATE:raise ValueError('REFUSE_OTHER_PUBLIC_DATE_OR_MODE')
    rows=copy.deepcopy(current['rows'])
    if any(r.get('validated') or r.get('verification_status')=='VERIFIED' for r in rows):raise ValueError('DO_NOT_OVERWRITE_RELEASED_WRITER')
    index=next((i for i,r in enumerate(rows) if (r['ex'],r['code'])==(initial['ex'],initial['code'])),None)
    if index is None or FairQueue.fingerprint(rows[index])!=FairQueue.fingerprint(initial):return None
    acquired=(bundle.get('quote_after') or {}).get('received_at')
    prior=rows[index].get('source_acquired_at')
    if acquired and prior and f.parsed_time(prior)>f.parsed_time(acquired):return None
    rows[index]=decide(rows[index],bundle,DATE,as_of,mode='LIVE')
    if rows[index]['validated']:raise ValueError('LIVE_SOURCE_CONTRACT_REMAINS_CLOSED')
    view=copy.deepcopy(current);view.update(rows=rows,verified_count=0,
        research_count=sum(r['verification_status']=='RESEARCH_ONLY' for r in rows),
        unknown_candidate_count=sum(r['verification_status']=='UNKNOWN' for r in rows),generated_at=as_of,assessment_as_of=as_of,
        version=max(current['version']+1,int(f.parsed_time(as_of).timestamp()*1000)*1000))
    safe=public_view(view);safe['provenance']=current.get('provenance',{})
    safe['independent_check_progress']={'scope':'BOUNDED_PRIVATE_FUGLE_RESEARCH_AUDIT','last_checked_symbol':initial['code'],
        'checked_at':as_of,'source_contract_live_released':False,'raw_fugle_public':False}
    return safe


def main():
    if os.getenv('GITHUB_REPOSITORY')!='gxaawill2-ui/tw-close-auction-mis-probe' or os.getenv('GITHUB_REF')!='refs/heads/stage4/20261016-fugle-probe':raise ValueError('REFUSE_OTHER_ENVIRONMENT')
    now=lambda:datetime.now(f.TZ)
    if now().date().isoformat()!=DATE:raise ValueError('NO_HISTORICAL_CANDIDATE_VERIFICATION')
    output=Path('stage5-candidate-verifier-report');output.mkdir(exist_ok=True)
    report={'scope':'REAL_TWO_CANDIDATE_PRIVATE_FUGLE_AUDIT_NOT_RELEASED_VERIFIED','trade_date':DATE,
        'run_id':os.getenv('GITHUB_RUN_ID'),'source_commit':os.getenv('GITHUB_SHA'),'armed_at':now().isoformat(),
        'maximum_candidates':2,'maximum_added_requests_per_minute':6,'maximum_added_requests':60,
        'mis_requests':0,'production_modified':False,'verified_count':0,'audits':[],'publication_receipts':[]}
    atomic(output/'candidate-checks.json',report)
    print(json.dumps({'event':'BOUNDED_CANDIDATE_VERIFIER_ARMED','armed_at':report['armed_at'],'provider_requests_before_133710':0}),flush=True)
    start=f.parsed_time(DATE+'T13:37:10+08:00');end=f.parsed_time(DATE+'T13:50:00+08:00')
    while now()<start:time.sleep(min(10,max(0,(start-now()).total_seconds())))
    opener=urllib.request.build_opener(NoRedirect()).open
    def read():
        req=urllib.request.Request(BASE+'/data?date='+DATE,headers={'User-Agent':CLOUD_CLIENT,'Accept':'application/json','Cache-Control':'no-cache'})
        try:
            with opener(req,timeout=6) as response:return json.loads(response.read(131073))
        except urllib.error.HTTPError as exc:
            if exc.code==404:return None
            raise ValueError('CURRENT_PUBLIC_RESEARCH_UNAVAILABLE') from None
    current=None
    while now()<f.parsed_time(DATE+'T13:40:00+08:00'):
        current=read()
        if current:break
        time.sleep(10)
    if not current or current.get('mode')!='LIVE' or current.get('trade_date')!=DATE or current.get('provenance',{}).get('source_run_id')!='38853538676':
        report.update(status='NO_CURRENT_FORMAL_RESEARCH_AVAILABLE',finished_at=now().isoformat());atomic(output/'candidate-checks.json',report);return report
    selected=current.get('rows',[])[:2]
    if not selected:
        report.update(status='NO_RESEARCH_CANDIDATES',finished_at=now().isoformat());atomic(output/'candidate-checks.json',report);return report
    token,key=os.getenv('STAGE5_PUBLISH_TOKEN'),os.getenv('STAGE5_DECISION_KEY')
    vault=Vault(token,key);report['private_canary']=probe(vault,DATE)
    with tempfile.TemporaryDirectory(prefix='stage5-real-candidates-private-') as temporary:
        root=Path(temporary)
        source=Source(os.getenv('FUGLE_API_KEY'),root/'raw',vault,max_requests=60,require_durable=True,min_interval=10.1)
        publisher=Publisher(BASE,root/'publisher',publish_token=token,decision_key=key,opener=opener)
        queue=FairQueue(lambda row:source.collect(row,DATE,min(end,now()+timedelta(minutes=8)),max_pages=16),workers=2,max_candidates=2,max_attempts=1)
        original={(r['ex'],r['code']):r for r in selected};queue.offer(selected);queue.tick()
        try:
            while now()<end and (queue.tasks or queue.pending):
                for identity,bundle in queue.tick():
                    row=original[identity];at=now().isoformat();diagnostic=audit(bundle,row,DATE,at)
                    report['audits'].append(diagnostic)
                    latest=read()
                    view=compile_update(latest,row,bundle,at) if latest else None
                    if view:
                        write=publisher.publish(view,end)
                        if write.get('receipt'):
                            saved=read()
                            if not saved or saved.get('version')!=view['version'] or saved.get('sha256')!=write['sha256']:raise ValueError('PER_CANDIDATE_PUBLIC_READ_MISMATCH')
                            report['publication_receipts'].append({'symbol':row['code'],'public_written_at':write['receipt']['public_written_at'],
                                'anonymous_read_at':now().isoformat(),'version':view['version'],'sha256':write['sha256']})
                    atomic(output/'candidate-checks.json',report)
                    print(json.dumps({'event':'PRIVATE_CANDIDATE_AUDITED','symbol':row['code'],'at':at,'status':diagnostic['status'],
                        'private_manifest_id':diagnostic.get('private_manifest_id'),'verified_count':0,'reasons':diagnostic['reasons']}),flush=True)
                time.sleep(.5)
        finally:queue.close()
        report.update(status='BOUNDED_CHECKS_FINISHED_NOT_VERIFIED',fugle_requests=source.count,
            finished_at=now().isoformat(),checked_candidates=len(report['audits']))
        atomic(output/'candidate-checks.json',report);print(json.dumps(report,indent=2));return report


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'event':'CANDIDATE_VERIFIER_STOPPED_NO_RAW_LOGGED','error_type':type(exc).__name__}));raise SystemExit(1)
