"""A new runner recovers the prior runner's private synthetic canary only."""
from datetime import datetime,timedelta
import json
import os
from pathlib import Path
import tempfile
import urllib.error
import urllib.request
import freshness as f
from stage3_ticks import canonical
from stage3_publication import CLOUD_CLIENT,Publisher
from stage5_runtime import BASE,Vault,NoRedirect
from stage5_archive import checked,export


def run():
    if os.getenv('GITHUB_REPOSITORY')!='gxaawill2-ui/tw-close-auction-mis-probe' or os.getenv('GITHUB_REF')!='refs/heads/stage4/20261016-fugle-probe':raise ValueError('REFUSE_OTHER_ENVIRONMENT')
    prior=json.loads(Path('reports/2026-10-16-stage5/cloud-publisher-acceptance.json').read_text())
    if prior.get('status')!='PASS' or prior.get('run_id')==os.getenv('GITHUB_RUN_ID'):raise ValueError('REQUIRE_COMPLETED_DIFFERENT_PRIOR_RUN')
    date=prior['private_storage']['read_back_at'][:10];ident=prior['private_storage']['id']
    opener=urllib.request.build_opener(NoRedirect()).open
    token,key=os.getenv('STAGE5_PUBLISH_TOKEN'),os.getenv('STAGE5_DECISION_KEY')
    vault=Vault(token,key,opener=opener)
    saved=checked(vault.read(date,ident),date,ident);event=saved['event'];payload=json.loads(event['raw'])
    if event.get('kind')!='SYNTHETIC_STORAGE_CANARY' or payload.get('is_synthetic') is not True or payload.get('purpose')!='PRIVATE_STORAGE_CANARY_NOT_MARKET_DATA':raise ValueError('REFUSE_NONCANARY_RECOVERY_TEST')
    if saved['private_written_at']!=prior['private_storage']['private_written_at']:raise ValueError('ORIGINAL_PRIVATE_WRITE_TIME_CHANGED')
    index=vault.read(date,'index')
    entry={'id':ident,'sha256':event['sha256']}
    if entry not in index.get('entries',[]):raise ValueError('CANARY_NOT_IN_DURABLE_INDEX')
    # Restrict this export test to this one already identified synthetic object.
    class CanaryVault:
        def read(self,date_,ident_):
            if date_!=date:raise ValueError('REFUSE_OTHER_DATE')
            if ident_=='index':return {'entries':[entry]}
            if ident_!=ident:raise ValueError('REFUSE_OTHER_OBJECT')
            return vault.read(date_,ident_)
    with tempfile.TemporaryDirectory(prefix='stage5-private-recovery-') as temporary:
        root=Path(temporary)/'private'
        first=export(CanaryVault(),date,root);second=export(CanaryVault(),date,root)
        if first['status']!='SNAPSHOT_COMPLETE' or second['manifest_sha256']!=first['manifest_sha256']:raise ValueError('PRIVATE_EXPORT_RESUME_FAILED')
    request=urllib.request.Request(BASE+'/private-evidence/'+date+'/'+ident,headers={'User-Agent':CLOUD_CLIENT,'Accept':'application/json'})
    try:
        with opener(request,timeout=6):raise ValueError('ANONYMOUS_PRIVATE_READ_ALLOWED')
    except urllib.error.HTTPError as exc:
        if exc.code!=401:raise ValueError('PRIVATE_READ_AUTH_TEST_FAILED') from None
    public_url=BASE+'/data?date=2099-01-03'
    def public_read():
        request=urllib.request.Request(public_url,headers={'User-Agent':CLOUD_CLIENT,'Accept':'application/json','Cache-Control':'no-cache'})
        with opener(request,timeout=6) as response:return json.loads(response.read(32000))
    current=public_read()
    if current.get('mode')!='SYNTHETIC' or current.get('is_synthetic') is not True or current.get('version')!=prior['final_public_write']['version'] or current.get('sha256')!=prior['final_public_write']['sha256']:raise ValueError('PRIOR_PUBLIC_STATE_NOT_RECOVERED')
    now=datetime.now(f.TZ)
    body={k:v for k,v in current.items() if k not in ('public_written_at','sha256')}
    body.update(version=max(current['version']+1,int(now.timestamp()*1000)*1000),generated_at=now.isoformat())
    body['transport_acceptance']={'scope':'SYNTHETIC_REAL_NEW_RUNNER_RESUME_NOT_MARKET','prior_run_id':prior['run_id']}
    with tempfile.TemporaryDirectory(prefix='stage5-recovered-publisher-') as temporary:
        result=Publisher(BASE,temporary,publish_token=token,decision_key=key,opener=opener).publish(body,now+timedelta(minutes=1))
    if result['status']!='WRITTEN':raise ValueError('NEW_RUNNER_PUBLISH_FAILED')
    final=public_read()
    if final.get('version')!=body['version'] or final.get('sha256')!=result['sha256']:raise ValueError('NEW_RUNNER_PUBLIC_READ_MISMATCH')
    return {'scope':'REAL_CLOUDFLARE_NEW_RUNNER_SYNTHETIC_RECOVERY_NOT_MARKET_OR_BROWSER','status':'PASS',
        'run_id':os.getenv('GITHUB_RUN_ID'),'source_commit':os.getenv('GITHUB_SHA'),'prior_completed_run_id':prior['run_id'],
        'private_id':ident,'original_private_written_at':saved['private_written_at'],
        'new_runner_read_back_at':now.isoformat(),'private_export_resume_verified':True,
        'private_anonymous_get_http_status':401,'private_objects_exported':1,
        'public_version_resumed_from':current['version'],'new_public_write':result['receipt'],
        'new_anonymous_read_at':datetime.now(f.TZ).isoformat(),'fugle_requests':0,
        'raw_market_data_published':False,'production_modified':False,'physical_phone_verified':False,'external_desktop_verified':False}


if __name__=='__main__':
    output=Path('stage5-cloud-recovery-report');output.mkdir(exist_ok=True)
    try:
        report=run();(output/'cloud-recovery.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
    except Exception as exc:
        report={'status':'NOT_PASSED','scope':'SYNTHETIC_NEW_RUNNER_RECOVERY','error_type':type(exc).__name__}
        (output/'cloud-recovery.json').write_text(json.dumps(report));print(json.dumps(report));raise SystemExit(1)
