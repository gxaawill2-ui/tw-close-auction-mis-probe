#!/usr/bin/env python3
"""One-date 10:00 full-universe MIS benchmark, separate from close-auction evidence."""
import argparse
import concurrent.futures
import json
import os
import statistics
import threading
import time
from dataclasses import asdict
from pathlib import Path

import probe
import run_control as control

DATE='2026-10-01'
OUT=Path('morning-results')
STATE='state/bench/'+DATE+'-1000.json'
STOP=threading.Event()


def eligible(items, expected):
    good=set();duplicates=[];empty=[];unexpected=[]
    for item in items if isinstance(items,list) else []:
        if not isinstance(item,dict):continue
        key=f'{item.get("ex")}:{item.get("c")}'
        if key not in expected:unexpected.append(key);continue
        if key in good:duplicates.append(key)
        if not item.get('n'):empty.append(key);continue
        good.add(key)
    return good,duplicates,empty,unexpected


def capture_batch(no, symbols):
    expected={f'{s["ex"]}:{s["code"]}' for s in symbols}
    row={'phase':'morning_1000','batch_no':no,'planned_at':probe.iso(probe.target(DATE,'10:00:00')),
         'symbols':symbols,'expected_count':len(symbols),'attempts':[],
         'requested_at':None,'received_at':None,'latency_ms':None,
         'http_status':None,'retry':0,'error':None,'raw_body':None,'response':None}
    if STOP.is_set():
        row['error']='NOT_REQUESTED_AFTER_HTTP_403_OR_429'
    else:
        tick=time.monotonic()
        for attempt in range(2):
            result=probe.fetch_mis(symbols,retry=0,timeout=20)
            evidence=asdict(result)
            evidence['attempt']=attempt+1
            row['attempts'].append(evidence)
            row.update(asdict(result))
            row['retry']=attempt
            if result.http_status in (403,429):
                STOP.set();break
            if not result.error or attempt==1 or STOP.is_set():break
            time.sleep(.5)
        row['requested_at']=row['attempts'][0]['requested_at']
        row['latency_ms']=round((time.monotonic()-tick)*1000,3)
    response=row.get('response')
    items=response.get('msgArray',[]) if isinstance(response,dict) else []
    good,duplicates,empty,unexpected=eligible(items,expected)
    if row['error']:good=set()
    row.update(returned_count=len(items) if isinstance(items,list) else 0,
        successful_codes=sorted(good),missing=sorted(expected-good),duplicate=duplicates,
        empty=empty,unexpected=unexpected)
    return row


def capture(universe):
    groups=[universe[i:i+50] for i in range(0,len(universe),50)]
    tick=time.monotonic();started=probe.iso();records=[]
    with (OUT/'morning_raw.jsonl').open('w') as log:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures=[pool.submit(capture_batch,no,group) for no,group in enumerate(groups,1)]
            for future in concurrent.futures.as_completed(futures):
                row=future.result();records.append(row)
                log.write(json.dumps(row,ensure_ascii=False)+'\n');log.flush()
    finished=probe.iso();wall=time.monotonic()-tick
    records.sort(key=lambda r:r['batch_no'])
    expected={f'{s["ex"]}:{s["code"]}' for s in universe}
    good=set().union(*(set(r['successful_codes']) for r in records))
    attempts=[a for r in records for a in r['attempts']]
    latencies=sorted(r['latency_ms'] for r in records if r['latency_ms'] is not None)
    p95=latencies[max(0,__import__('math').ceil(len(latencies)*.95)-1)] if latencies else None
    metrics={'trade_date':DATE,'kind':'morning_connectivity_only','planned_at':probe.iso(probe.target(DATE,'10:00:00')),
        'started_at':started,'finished_at':finished,'stock_universe_count':len(universe),
        'batch_count':len(groups),'batch_size':50,'concurrency':5,'request_count':len(attempts),
        'first_request_started_at':min((a['requested_at'] for a in attempts),default=None),
        'last_response_received_at':max((a['received_at'] for a in attempts),default=None),
        'wall_time_seconds':round(wall,3),'success_count':len(good),'missing_count':len(expected-good),
        'missing_codes':sorted(expected-good),'symbol_set_equal':good==expected,
        'fastest_batch_ms':min(latencies) if latencies else None,
        'average_batch_ms':statistics.mean(latencies) if latencies else None,
        'median_batch_ms':statistics.median(latencies) if latencies else None,
        'p95_batch_ms':p95,'slowest_batch_ms':max(latencies) if latencies else None,
        'http_errors':sum(a['http_status'] is not None and a['http_status']>=400 for a in attempts),
        'http_429':sum(a['http_status']==429 for a in attempts),
        'timeouts':sum('timeout' in (a['error'] or '').lower() or 'timed out' in (a['error'] or '').lower() for a in attempts),
        'retries':sum(max(0,len(r['attempts'])-1) for r in records),
        'empty_response':sum(isinstance(a.get('response'),dict) and not a['response'].get('msgArray') for a in attempts),
        'duplicate_count':sum(len(r['duplicate']) for r in records),
        'empty_symbol_count':sum(len(r['empty']) for r in records),
        'insufficient_batches':[r['batch_no'] for r in records if r['missing']],
        'response_errors':sum(bool(r['error']) for r in records),
        'signals_generated':False,'trial_exclusion_verified':False,'price_semantics_verified':False}
    return records,metrics


def summary_body(state):
    metrics=state.get('metrics',{})
    return f'''## 10/1 10:00 MIS 全市場預測試：{state['status']}

- 日期：{DATE}，Asia/Taipei
- runner 啟動：{state.get('runner_started_at','—')}
- phase：{state.get('phase','—')}
- 股票池：{state.get('universe_count','尚未取得')}
- batch size / concurrency：50 / 5
- 第一個 request：{metrics.get('first_request_started_at','—')}
- 最後 response：{metrics.get('last_response_received_at','—')}
- 全市場耗時：{metrics.get('wall_time_seconds','—')} 秒
- 成功／總數：{metrics.get('success_count','—')}/{metrics.get('stock_universe_count','—')}
- missing / timeout / retry：{metrics.get('missing_count','—')} / {metrics.get('timeouts','—')} / {metrics.get('retries','—')}
- HTTP error / 429：{metrics.get('http_errors','—')} / {metrics.get('http_429','—')}
- error：{state.get('error','—')}
- Artifact：mis-morning-{os.getenv('GITHUB_RUN_ID','local')}
- [本次 workflow](https://github.com/{control.REPO}/actions/runs/{os.getenv('GITHUB_RUN_ID','')})

只驗證全市場抓取速度與完整率，不是 13:25 快照，不驗證試撮欄位，不產生 ±3% 訊號。尾盤接力任務不受本測試修改。
'''


def notify(state):
    current,_=control.read_state(STATE)
    comment_id=current.get('comment_id')
    if comment_id:
        control.api('issues/comments/'+str(comment_id),'PATCH',{'body':summary_body(state)})
    else:
        response=control.api('issues/1/comments','POST',{'body':summary_body(state)})
        state['comment_id']=response['id']
    control.merge_state(STATE,state)


def main():
    OUT.mkdir(exist_ok=True)
    if probe.now_tpe().date().isoformat()!=DATE:raise RuntimeError('Benchmark restricted to 2026-10-01')
    state={'trade_date':DATE,'status':'⏳ WAITING','phase':'waiting_0950','run_id':os.getenv('GITHUB_RUN_ID'),
           'runner_started_at':os.getenv('RUNNER_STARTED_AT') or probe.iso(),'signals_generated':False}
    notify(state)
    code=1
    try:
        probe.wait_until(probe.target(DATE,'09:50:00'))
        state.update(phase='fetch_universe');notify(state)
        universe=probe.fetch_universe(OUT)
        (OUT/'universe.json').write_text(json.dumps(universe,ensure_ascii=False,indent=2))
        state.update(universe_count=len(universe),phase='waiting_1000');notify(state)
        if probe.now_tpe()>probe.target(DATE,'09:59:45'):
            raise RuntimeError('failed_late_ready; do not label a later capture as the 10:00 snapshot')
        probe.wait_until(probe.target(DATE,'10:00:00'))
        if probe.now_tpe()>probe.target(DATE,'10:00:00')+probe.timedelta(milliseconds=750):
            raise RuntimeError('failed_late_capture; no backfill')
        # No Issue or persistence IO is performed before starting the timed requests.
        records,metrics=capture(universe)
        state.update(metrics=metrics,phase='completed',status='✅ SUCCESS' if metrics['symbol_set_equal'] and not metrics['duplicate_count'] else '⚠️ PARTIAL',finished_at=probe.iso())
        (OUT/'performance_report.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2))
        (OUT/'error_missing_report.json').write_text(json.dumps([r for r in records if r['error'] or r['missing'] or r['duplicate']],ensure_ascii=False,indent=2))
        probe.normalized_csv([{'records':records,'metrics':metrics}],[],OUT)
        code=0 if state['status']=='✅ SUCCESS' else 3
    except Exception as exc:
        state.update(status='❌ FAILED',phase='failed',error=f'{type(exc).__name__}:{exc}',finished_at=probe.iso())
        print(state['error'],flush=True)
    finally:
        (OUT/'run_summary.json').write_text(json.dumps(state,ensure_ascii=False,indent=2))
        notify(state)
        probe.package(OUT,DATE+'-morning')
    print(json.dumps(state,ensure_ascii=False),flush=True)
    return code


if __name__=='__main__':raise SystemExit(main())
