"""Small, rate-bounded public candidate checks. An observation is not validation."""
import argparse
import gzip
import hashlib
import json
import time
import os
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime
import freshness as f
from pchome_benchmark import parse_page


def check_pchome(symbol,output,opener=None):
    from fast_selection import safe_output
    directory=safe_output(output)
    code=symbol['code'];url=f'https://stock.pchome.com.tw/stock/sto0/ock3/sid{code}.html'
    started=datetime.now(f.TZ).isoformat();tick=time.monotonic();raw=b'';status=None;error=None;attempts=[]
    try:
        for index in range(2):
            at=datetime.now(f.TZ).isoformat()
            request=urllib.request.Request(url,data=b'is_check=1' if index else None,
                headers={'User-Agent':'Mozilla/5.0','Accept':'text/html','Referer':url})
            with (opener or urllib.request.urlopen)(request,timeout=8) as response:
                status=response.status;raw=response.read(2_000_001)
            if len(raw)>2_000_000:raise ValueError('BODY_SIZE_LIMIT')
            attempts.append({'requested_at':at,'received_at':datetime.now(f.TZ).isoformat(),
                'method':request.get_method(),'http_status':status,'raw_sha256':hashlib.sha256(raw).hexdigest()})
            if index==0 and len(raw)<2000 and b"name='is_check'" in raw:
                (directory/(symbol['ex']+'-'+code+'-auto-form.html.gz')).write_bytes(gzip.compress(raw))
                continue
            break
    except urllib.error.HTTPError as exc:status=exc.code;error='HTTP_'+str(status)
    except Exception as exc:error=type(exc).__name__+':'+str(exc)
    ended=datetime.now(f.TZ).isoformat();parsed=parse_page(raw.decode('utf-8','replace'),code) if status==200 and not error else {}
    body=directory/(symbol['ex']+'-'+code+'.html.gz');body.write_bytes(gzip.compress(raw))
    result={'source':'PCHOME','ex':symbol['ex'],'code':code,'url':url,'requested_at':started,'received_at':ended,
       'http_status':status,'error':error,'attempts':attempts,'latency_ms':round((time.monotonic()-tick)*1000,3),
       'raw_sha256':hashlib.sha256(raw).hexdigest(),'raw_path':body.name,
       'observations':{k:parsed.get(k) for k in ('code_match','trade_row_count','before_cutoff_observation','close_time_observation','trade_table_date_literals')},
       'status':'OBSERVATION_ONLY' if parsed.get('trade_row_count') else 'NO_USABLE_OBSERVATION',
       'trade_date_verified':False,'trial_exclusion_verified':False,'full_tick_completeness_verified':False,
       'independent_lineage_verified':False,'validated':False,
       'limitation':'Public table does not prove same-date actual-tick completeness or independent upstream lineage. Never a formal gate.'}
    pre=parsed.get('before_cutoff_observation') or {};close=parsed.get('close_time_observation') or {}
    match=bool(parsed.get('code_match') and f.decimal_value(pre.get('price'))==f.decimal_value(symbol.get('P_before'))
        and f.decimal_value(close.get('price'))==f.decimal_value(symbol.get('P_close'))
        and pre.get('time')==symbol.get('P_before_trade_time') and close.get('time')==symbol.get('P_close_trade_time')
        and pre.get('price') is not None and close.get('price') is not None)
    result['comparison_to_mis']={'prices_and_times_match':match,'formal_verification':False}
    if match:result['status']='OBSERVATION_MATCH_UNPROVEN'
    return result


def check_fugle(symbol,output,api_key=None,opener=None):
    """Optional candidate-only adapter. Never exposes keys or certifies finality.

    Two requests per candidate, >=1.1 seconds apart. Pagination is intentionally
    not claimed complete: an old last tick absent from this page stays unknown.
    """
    key=api_key or os.getenv('FAST_FUGLE_API_KEY')
    if not key:return {'source':'FUGLE','status':'NOT_CONFIGURED','validated':False}
    from fast_selection import safe_output
    directory=safe_output(output);results={};errors=[]
    for index,kind in enumerate(('quote','trades')):
        if index:time.sleep(1.1)
        url=f'https://api.fugle.tw/marketdata/v1.0/stock/intraday/{kind}/{symbol["code"]}'
        if kind=='trades':url+='?sort=desc&limit=500&isTrial=false'
        try:
            req=urllib.request.Request(url,headers={'X-API-KEY':key,'Accept':'application/json'})
            with (opener or urllib.request.urlopen)(req,timeout=8) as response:
                raw=response.read(2_000_001);status=response.status
            if len(raw)>2_000_000:raise ValueError('BODY_SIZE_LIMIT')
            data=json.loads(raw)
            path=directory/(symbol['ex']+'-'+symbol['code']+'-'+kind+'.json')
            path.write_bytes(raw)
            results[kind]={'http_status':status,'raw_path':path.name,'raw_sha256':hashlib.sha256(raw).hexdigest(),
                'received_at':datetime.now(f.TZ).isoformat(),'data':data}
        except urllib.error.HTTPError as exc:
            errors.append({'http_status':exc.code,'error':'HTTP_'+str(exc.code)})
            if exc.code in (401,403,429):break
        except Exception as exc:
            # Exception messages can contain headers; keep only the type.
            errors.append({'error':type(exc).__name__})
    return {'source':'FUGLE','status':'OBSERVATION_ONLY' if results else 'SOURCE_ERROR',
      'results':results,'errors':errors,'validated':False,'independent_lineage_verified':False,
      'full_tick_completeness_verified':False,
      'limitation':'Same-date/symbol, regular-session, trial exclusion, finality and complete tick coverage require assessment. API success alone is not verification.'}


def candidate_checks(rows,output,fetch=check_pchome,wait=time.sleep,max_requests=12):
    # Candidate-only: never reconstruct a full-market PChome scraping queue.
    seen=set();results=[]
    for row in rows:
        key=row['ex'],row['code']
        if key in seen:continue
        if len(results)>=max_requests:break
        seen.add(key);r=fetch(row,output);results.append(r)
        if r.get('http_status') in (403,429):break
        wait(1)
    return results


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('candidates',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();payload=json.loads(a.candidates.read_text());rows=payload.get('rows',payload.get('candidate_list',[]))
    result=candidate_checks(rows,a.output)
    (a.output/'source-checks.json').write_text(json.dumps({'scope':'POSTCLOSE_SOURCE_RESEARCH_NOT_1335_TEST','checks':result,'formal_signals':0},ensure_ascii=False,indent=2))
    print(json.dumps([{'code':r['code'],'http_status':r['http_status'],'rows':r['observations']['trade_row_count'],'validated':False} for r in result],ensure_ascii=False))
