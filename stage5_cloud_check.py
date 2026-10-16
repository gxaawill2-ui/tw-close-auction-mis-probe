"""Only synthetic publication and private canary; no market provider calls."""
from datetime import datetime,timedelta
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.error
import urllib.request
import freshness as f
from stage3_publication import Publisher,CLOUD_CLIENT
from stage5_runtime import BASE,Vault,NoRedirect
from stage5_archive import probe


def run(directory):
    if os.getenv('GITHUB_REPOSITORY')!='gxaawill2-ui/tw-close-auction-mis-probe' or os.getenv('GITHUB_REF')!='refs/heads/stage4/20261016-fugle-probe':
        raise ValueError('REFUSE_OTHER_ENVIRONMENT')
    token,key=os.getenv('STAGE5_PUBLISH_TOKEN'),os.getenv('STAGE5_DECISION_KEY')
    opener=urllib.request.build_opener(NoRedirect()).open;vault=Vault(token,key,opener=opener)
    at=datetime.now(f.TZ);date=at.date().isoformat()
    report={'scope':'REAL_ISOLATED_CLOUD_SYNTHETIC_PUBLICATION_AND_PRIVATE_CANARY_NOT_MARKET_OR_BROWSER',
        'started_at':at.isoformat(),'run_id':os.getenv('GITHUB_RUN_ID'),'source_commit':os.getenv('GITHUB_SHA'),
        'fugle_requests':0,'production_modified':False,'external_desktop_verified':False,'physical_phone_verified':False}
    report['private_storage']=probe(vault,date)
    publisher=Publisher(BASE,directory,publish_token=token,decision_key=key,opener=opener)
    version=int(time.time()*1000)*1000
    body={'schema_version':'STAGE3_SELECTION_V1','trade_date':'2099-01-03','mode':'SYNTHETIC',
        'is_synthetic':True,'version':version,'generated_at':at.isoformat(),'rows':[],
        'verified_count':0,'research_count':0,'unknown_candidate_count':0,'universe_count':0,
        'screening_calculable_count':0,'screening_unresolved_count':0,
        'transport_acceptance':{'scope':'SYNTHETIC_REAL_PUBLISHER_NOT_MARKET','source_commit':report['source_commit']}}
    deadline=at+timedelta(minutes=2)
    result=publisher.publish(body,deadline)
    if result['status']!='WRITTEN':raise ValueError('SIGNED_PUBLISHER_NOT_WRITTEN')
    report['public_write']=result['receipt']
    def read(headers=None):
        request=urllib.request.Request(BASE+'/data?date=2099-01-03',headers={'User-Agent':CLOUD_CLIENT,'Accept':'application/json','Cache-Control':'no-cache',**(headers or {})})
        return opener(request,timeout=6)
    with read() as response:
        saved=json.loads(response.read(32000));etag=response.headers.get('ETag')
        if response.status!=200 or saved.get('version')!=version or saved.get('sha256')!=result['sha256'] or saved.get('mode')!='SYNTHETIC':
            raise ValueError('PUBLIC_READ_VERSION_HASH_MISMATCH')
        if response.headers.get('Access-Control-Allow-Origin')!='*' or 'no-store' not in response.headers.get('Cache-Control',''):
            raise ValueError('PUBLIC_READ_CORS_OR_CACHE')
    report['anonymous_read_at']=datetime.now(f.TZ).isoformat()
    try:
        with read({'If-None-Match':etag}):raise ValueError('EXPECTED_304')
    except urllib.error.HTTPError as exc:
        if exc.code!=304:raise ValueError('ETAG_CHECK_FAILED') from None
    duplicate=publisher.publish(body,deadline)
    if not duplicate.get('receipt',{}).get('duplicate'):raise ValueError('IDEMPOTENT_RESUME_FAILED')
    stale=publisher.publish({**body,'version':version-1},deadline,max_attempts=1)
    if stale['receipt'] or not any(a.get('http_status')==409 for a in stale['attempts']):raise ValueError('STALE_VERSION_NOT_REJECTED')
    # New Publisher instance simulates a process restart using the durable outbox directory.
    resumed=Publisher(BASE,directory,publish_token=token,decision_key=key,opener=opener)
    recovered=resumed.publish({**body,'version':version+1},deadline)
    if recovered['status']!='WRITTEN':raise ValueError('RESTART_PUBLICATION_FAILED')
    with read() as response:
        final=json.loads(response.read(32000))
        if final.get('version')!=version+1 or final.get('sha256')!=recovered['sha256']:raise ValueError('RESTART_READ_MISMATCH')
    report.update(status='PASS',etag_revalidation_304=True,idempotent_write=True,stale_rejected=True,
        process_restart_write_read=True,finished_at=datetime.now(f.TZ).isoformat(),
        final_public_write=recovered['receipt'],raw_market_data_published=False)
    return report


if __name__=='__main__':
    output=Path('stage5-cloud-check-report');output.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='stage5-synthetic-publisher-') as tmp:report=run(tmp)
        (output/'cloud-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
    except Exception as exc:
        report={'status':'NOT_PASSED','error_type':type(exc).__name__,'scope':'SYNTHETIC_CLOUD_CHECK_NO_MARKET_DATA'}
        (output/'cloud-check.json').write_text(json.dumps(report));print(json.dumps(report));raise SystemExit(1)
