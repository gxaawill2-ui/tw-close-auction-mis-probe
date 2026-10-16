"""Already-private evidence recovery and synthetic cloud lifecycle; zero market requests."""
from datetime import datetime,timedelta
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.request
import urllib.error
import freshness as f
from fast_selection import atomic
from stage3_publication import Publisher,CLOUD_CLIENT
from stage5_runtime import Vault,BASE,NoRedirect,restore_bundle
from stage5_archive import checked
from stage6_evidence import diagnose

REPORT=Path('stage6-safe-report')

def read_public(date):
    request=urllib.request.Request(BASE+'/data?date='+date,headers={'User-Agent':CLOUD_CLIENT,'Accept':'application/json','Cache-Control':'no-cache'})
    with urllib.request.build_opener(NoRedirect()).open(request,timeout=6) as r:
        if r.status!=200:raise ValueError('PUBLIC_READ_FAILED')
        return json.loads(r.read(100000))

def run():
    if os.getenv('GITHUB_REPOSITORY')!='gxaawill2-ui/tw-close-auction-mis-probe' or os.getenv('GITHUB_REF')!='refs/heads/stage4/20261016-fugle-probe':
        raise ValueError('REFUSE_OTHER_ENVIRONMENT')
    REPORT.mkdir(exist_ok=True)
    vault=Vault(os.getenv('STAGE5_PUBLISH_TOKEN'),os.getenv('STAGE5_DECISION_KEY'))
    root=Path('reports/2026-10-16-stage5');date='2026-10-16'
    refs=json.loads((root/'mis-comparison-references.json').read_text())['rows']
    ids={}
    for name in ('real-candidate-private-audit.json','real-remaining-candidate-audit.json'):
        for a in json.loads((root/name).read_text())['audits']:ids[a['symbol']]=a['private_manifest_id']
    ids['5546']=json.loads((root/'real-delayed-private-audit.json').read_text())['diagnostic']['private_manifest_id']
    report={'scope':'REAL_PRIVATE_RECOVERY_ANALYSIS_NOT_INTRADAY_PUBLICATION','trade_date':date,
        'run_id':os.getenv('GITHUB_RUN_ID'),'source_commit':os.getenv('GITHUB_SHA'),
        'started_at':datetime.now(f.TZ).isoformat(),'fugle_requests':0,'mis_requests':0,
        'live_public_writes':0,'verified_count':0,'raw_provider_values_exported':False,'results':[]}
    for ref in refs:
        bundle=restore_bundle(vault,date,ids[ref['code']])
        # Diagnose now and retain original acquisition times; never relabel replay as live.
        report['results'].append(diagnose(bundle,ref,date,datetime.now(f.TZ).isoformat()))
    index=vault.read(date,'index');entries=index['entries'];times=[];size=0
    for entry in entries:
        saved=checked(vault.read(date,entry['id']),date,entry['id'])
        if saved['event']['sha256']!=entry['sha256']:raise ValueError('INDEX_HASH_MISMATCH')
        times.append(f.parsed_time(saved['private_written_at']));size+=len(saved['event']['raw'].encode())
    # Existing namespace alarm is seven days from its first write, not each object.
    first=min(times)
    report['private_storage']={'authenticated_objects_verified':len(entries),'raw_bytes':size,
        'first_private_write':first.isoformat(),'conservative_export_before':(first+timedelta(days=5)).isoformat(),
        'estimated_namespace_expiry':(first+timedelta(days=7)).isoformat(),
        'expiry_is_observed_alarm':False,'retention_days':7,'long_term_archive_completed':False}
    report['finished_at']=datetime.now(f.TZ).isoformat()
    atomic(REPORT/'real-evidence.json',report)
    print(json.dumps(report,ensure_ascii=False),flush=True)

    # A separate 2099 namespace cannot overwrite today's real research data.
    synthetic_date='2099-01-06';version=int(time.time()*1000)*1000
    row={'code':'2330','name':'合成驗收（非真實股票訊號）','ex':'tse','P_before':'100','P_close':'104',
        'tail_return_pct':'4','closing_auction_volume':'5','intraday_total_volume':'20','closing_volume_ratio_pct':'25',
        'verification_status':'RESEARCH_ONLY','validated':False,'simulated_only':True}
    base={'schema_version':'STAGE3_SELECTION_V1','trade_date':synthetic_date,'mode':'SYNTHETIC','is_synthetic':True,
        'verified_count':0,'universe_count':1,'screening_calculable_count':1,'screening_unresolved_count':0}
    outcomes=[]
    with tempfile.TemporaryDirectory(prefix='stage6-outbox-') as tmp:
        publisher=Publisher(BASE,tmp,publish_token=vault.token,decision_key=vault.key,opener=vault.opener)
        states=[('RESEARCH_ONLY',[row],[]),('UNKNOWN',[{**row,'verification_status':'UNKNOWN'}],[]),
                ('RETRACTED',[],[{'code':'2330','ex':'tse','reason':'SYNTHETIC_PRICE_CONFLICT'}])]
        for i,(state,rows,retracted) in enumerate(states):
            now=datetime.now(f.TZ);v=version+i
            body={**base,'version':v,'generated_at':now.isoformat(),'rows':rows,'retracted':retracted,
                'research_count':int(state=='RESEARCH_ONLY'),'unknown_candidate_count':int(state=='UNKNOWN')}
            result=publisher.publish(body,now+timedelta(minutes=1))
            if result['status']!='WRITTEN':raise ValueError('SYNTHETIC_PUBLICATION_FAILED')
            read=read_public(synthetic_date)
            if read['version']!=v or read['sha256']!=result['sha256']:raise ValueError('SYNTHETIC_READ_MISMATCH')
            outcomes.append({'state':state,'version':v,'calculated_at':body['generated_at'],
                'cloud_written_at':result['receipt']['public_written_at'],'api_read_at':datetime.now(f.TZ).isoformat(),
                'sha256':result['sha256']})
            atomic(REPORT/'synthetic-cloud.json',{'scope':'SYNTHETIC_ONLY_NOT_REAL_MARKET_OR_PHONE_ACCEPTANCE',
                'trade_date':synthetic_date,'run_id':os.getenv('GITHUB_RUN_ID'),'states':outcomes})
            print(json.dumps({'synthetic_state':outcomes[-1]}),flush=True)
            if i<2:time.sleep(40)
        stale=publisher.publish({**body,'version':version},datetime.now(f.TZ)+timedelta(seconds=30),max_attempts=1)
        if not any(a.get('http_status')==409 for a in stale['attempts']):raise ValueError('STALE_WRITE_WAS_NOT_REJECTED')
        print(json.dumps({'synthetic_stale_rejected':True}),flush=True)
    atomic(REPORT/'synthetic-cloud.json',{'scope':'SYNTHETIC_ONLY_NOT_REAL_MARKET_OR_PHONE_ACCEPTANCE',
        'trade_date':synthetic_date,'run_id':os.getenv('GITHUB_RUN_ID'),'states':outcomes,'stale_version_rejected':True,
        'physical_phone_tested':False,'status':'PASS'})

if __name__=='__main__':
    try:run()
    except Exception as exc:
        REPORT.mkdir(exist_ok=True);atomic(REPORT/'failure.json',{'status':'NOT_PASSED','error_type':type(exc).__name__})
        print(json.dumps({'status':'NOT_PASSED','error_type':type(exc).__name__}),flush=True);raise SystemExit(1)
