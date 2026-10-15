"""Read-only same-day capture analysis and official-universe preflight.

Never calls MIS, dispatches Actions, writes production, or releases VERIFIED.
Artifact receive/save, event availability and actual calculation are separate.
"""
import argparse
import concurrent.futures
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import urllib.request
import uuid

import freshness as f
import probe
import official_retry
from fast_selection import Engine, atomic, safe_output, stamp
from stage3_selection import Pipeline
from build_stage3_preview import build


def preflight(date, output, *, opener=urllib.request.urlopen, clock=None):
    clock=clock or (lambda:datetime.now(f.TZ))
    if clock().astimezone(f.TZ).date().isoformat()!=date:
        raise ValueError('PREFLIGHT_MUST_BE_CURRENT_DATE')
    directory=safe_output(output); checks=[];universe=[]
    def one(source):
        market,ex,url,code_key,name_key=source
        ident=uuid.uuid4().hex
        began=clock().isoformat();result={'market':market,'url':url,'requested_at':began}
        atomic(directory/(market+'-'+ident+'-request.json'),{**result,'status':'REQUEST_STARTED_NOT_RECEIVED'})
        try:
            # Official company metadata only. No MIS market-wide prices.
            request=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'tw-tail-isolated-preflight'})
            with opener(request,timeout=8) as response:
                status=response.status;raw=response.read(5_000_001)
            received=clock().isoformat()
            if len(raw)>5_000_000:raise ValueError('BODY_TOO_LARGE')
            path=directory/(market+'-'+ident+'.json')
            with path.open('xb') as file:file.write(raw);file.flush();os.fsync(file.fileno())
            result.update(http_status=status,received_at=received,persisted_at=clock().isoformat(),
                raw_file=path.name,sha256=hashlib.sha256(raw).hexdigest())
            if status!=200:raise ValueError('HTTP_STATUS_NOT_200')
            rows=probe.parse_universe_rows(json.loads(raw.decode('utf-8-sig')),market,ex,code_key,name_key)
            if len(rows)<300:raise ValueError('INSUFFICIENT_COMPANY_ROWS')
            result.update(status='RECEIVED_COMPANY_METADATA',parsed_count=len(rows))
            atomic(directory/(market+'-'+ident+'-receipt.json'),result)
            return result,rows
        except Exception as exc:
            result.update(status='UNAVAILABLE',error=type(exc).__name__)
            atomic(directory/(market+'-'+ident+'-receipt.json'),result)
            return result,[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for result,rows in pool.map(one,probe.UNIVERSE_SOURCES):checks.append(result);universe.extend(rows)
    complete=all(x['status']=='RECEIVED_COMPANY_METADATA' for x in checks)
    result={'trade_date':date,'observed_at':clock().isoformat(),'scope':'OFFICIAL_COMPANY_METADATA_ONLY_NO_MIS',
        'status':'COMPANY_METADATA_RECEIVED' if complete else 'INCOMPLETE',
        'company_count':len(universe),'tradable_universe_verified':False,'checks':checks,
        'limitations':['Company lists do not prove current tradability or full MIS availability. Formal collector must still apply its own date-specific exclusions.']}
    atomic(directory/'preflight.json',result)
    if complete:atomic(directory/'company-universe.json',universe)
    return result


def analyze(archive,date,output,*,artifact_received_at=None,artifact_persisted_at=None,
            expected_sha256=None,clock=None):
    clock=clock or (lambda:datetime.now(f.TZ));started=clock()
    directory=safe_output(output);raw=Path(archive).read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if expected_sha256 and digest!=expected_sha256:raise ValueError('CAPTURE_HASH_MISMATCH')
    summary,universe,snapshots,probes=official_retry.load_capture(raw)
    if summary.get('trade_date')!=date:raise ValueError('CAPTURE_TRADE_DATE_MISMATCH')
    received=f.parsed_time(artifact_received_at);persisted=f.parsed_time(artifact_persisted_at)
    if bool(received)!=bool(persisted) or received and not received<=persisted<=started:
        raise ValueError('INVALID_ARTIFACT_RECEIVE_SAVE_TIME')
    # Reconstruct the original event order for evidence inspection, never for
    # historical public timestamps. Offline imports cannot emit LIVE VERIFIED.
    engine=Engine(date,universe,directory/'research','SAVED_CAPTURE_ANALYSIS')
    pipeline=Pipeline(engine,mode='OFFLINE_REPLAY')
    records=[r for snap in snapshots for r in snap['records']]+probes
    records.sort(key=lambda r:(r.get('received_at') or '',r.get('phase') or ''))
    if any(not f.parsed_time(r.get('received_at')) or f.parsed_time(r['received_at'])>started for r in records):
        raise ValueError('CAPTURE_OBSERVATION_AFTER_ANALYSIS_START')
    for record in records:engine.feed(record)
    body=pipeline.compile(clock().isoformat())
    now=clock().isoformat();same_day=started.astimezone(f.TZ).date().isoformat()==date
    provenance={'kind':'SAME_DAY_SAVED_CAPTURE_ANALYSIS' if same_day else 'HISTORICAL_SAVED_CAPTURE_ANALYSIS',
        'source_capture_status':summary.get('status'),'source_capture_finished_at':summary.get('finished_at'),
        'capture_sha256':digest,'capture_received_at':artifact_received_at,'capture_persisted_at':artifact_persisted_at,
        'analysis_started_at':started.isoformat(),'analysis_finished_at':now,
        'first_research_program_observed_at':now if body['rows'] else None,
        'first_research_event_evidence_at':engine.first_ready,
        'last_candidate_event_evidence_at':engine.last_update,
        'first_independent_pre_at':None,'first_independent_close_at':None,'first_verified_at':None,
        'first_cloud_written_at':None,'first_external_browser_observed_at':None,
        'artifact_barrier':True,'runtime_original_raw_persisted_at':None,
        'note':'Artifact imported after upload; original batch fsync/public availability times are not inferred from event timestamps.'}
    body['provenance']=provenance
    atomic(directory/'stage4-results.json',body);atomic(directory/'stage4-timing.json',provenance)
    build(body,directory/'stage4-preview.html')
    assert digest==hashlib.sha256(Path(archive).read_bytes()).hexdigest()
    return body


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
    a=sub.add_parser('preflight');a.add_argument('date');a.add_argument('output',type=Path)
    a=sub.add_parser('analyze');a.add_argument('archive',type=Path);a.add_argument('date');a.add_argument('output',type=Path)
    a.add_argument('--artifact-received-at');a.add_argument('--artifact-persisted-at');a.add_argument('--expected-sha256')
    args=p.parse_args()
    if args.mode=='preflight':result=preflight(args.date,args.output)
    else:result=analyze(args.archive,args.date,args.output,artifact_received_at=args.artifact_received_at,
        artifact_persisted_at=args.artifact_persisted_at,expected_sha256=args.expected_sha256)
    print(json.dumps({k:result[k] for k in ('trade_date','status','company_count','research_count','verified_count') if k in result},ensure_ascii=False))
