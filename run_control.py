#!/usr/bin/env python3
"""Persistent isolated-repo state, live deduplication and asynchronous status IO."""
import argparse
import base64
import concurrent.futures
import json
import os
import re
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import probe

REPO = 'gxaawill2-ui/tw-close-auction-mis-probe'
ISSUE = 1
LOCK = threading.Lock()


def api(path, method='GET', payload=None):
    if os.getenv('GITHUB_REPOSITORY') != REPO:
        raise RuntimeError('Controller restricted to the independent probe repo')
    token = os.environ['GITHUB_TOKEN']
    req = urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,
        data=json.dumps(payload).encode() if payload is not None else None, method=method,
        headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
                 'X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json',
                 'User-Agent':'independent-mis-probe'})
    try:
        with urllib.request.urlopen(req,timeout=8) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404 and method == 'GET': return None
        raise


def read_state(path):
    data = api('contents/'+path+'?ref=main')
    if data is None:return {},None
    return json.loads(base64.b64decode(data['content'])),data['sha']


def merge_state(path, patch):
    # Contents API SHA implements compare-and-swap; live and watchdog can't
    # silently overwrite each other's newer state.
    for _ in range(4):
        current,sha = read_state(path)
        if patch.get('status') == 'failed_incomplete' and current.get('phase') == 'completed':
            return current
        current.update(patch)
        current['updated_at'] = probe.iso()
        payload = {'message':'Record isolated MIS execution state', 'branch':'main',
            'content':base64.b64encode((json.dumps(current,ensure_ascii=False,indent=2)+'\n').encode()).decode()}
        if sha:payload['sha'] = sha
        try:
            api('contents/'+path,'PUT',payload)
            return current
        except urllib.error.HTTPError as exc:
            if exc.code not in (409,422):raise
    raise RuntimeError('Persistent state write conflict')


def live_path(date):return 'state/live/'+date+'.json'


def next_weekday(now):
    day = now.date() + timedelta(days=1)
    while day.weekday() >= 5:day += timedelta(days=1)
    return day.isoformat()


def calendar_state(now, output):
    year=now.year
    url=f'https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?response=json&queryYear={year-1911}'
    status,raw=probe.get_bytes(url,25)
    data=json.loads(raw)
    if status!=200 or data.get('stat')!='ok' or data.get('queryYear')!=year or not data.get('data'):
        raise RuntimeError('Official market calendar unavailable; no presumed trading day')
    (output/'official_calendar.json').write_bytes(raw)
    closed={r[0] for r in data['data'] if '最後交易日' not in r[1] and '開始交易日' not in r[1]}
    day=now.date()+timedelta(days=1)
    while day.weekday()>=5 or day.isoformat() in closed:day+=timedelta(days=1)
    state={'verified_at':probe.iso(),'source':url,'year':year,
        'next_trade_date':day.isoformat(),'today':now.date().isoformat(),
        'is_trading_day':now.weekday()<5 and now.date().isoformat() not in closed}
    merge_state('state/calendar_latest.json',state)
    return state


def render(now, record, dry, receipt, calendar=None):
    date = now.date().isoformat()
    calendar=calendar or {}
    if record.get('trade_date') != date:record = {}
    status = record.get('status','waiting')
    if not record and now.strftime('%H:%M:%S') >= '13:40:00' and now.weekday() < 5:
        status = 'failed_missing'
    if not record and calendar.get('today')==date and not calendar.get('is_trading_day'):
        status = 'nontrading_day'
    titles = {'waiting':'⏳ 等待當日排程','running':'🟡 RUNNING',
        'success_raw_capture':'✅ 原始資料擷取完成（欄位未驗證）','partial':'⚠️ PARTIAL',
        'failed_missing':'❌ FAILED — 當日漏跑','failed_late_start':'❌ FAILED — 啟動過晚',
        'failed_incomplete':'❌ FAILED — 13:40 尚未完成','failed':'❌ FAILED',
        'nontrading_day':'⏸️ 官方休市日'}
    heading = titles.get(status,'❌ FAILED — '+status)
    performance = record.get('snapshots',{})
    pre,close = performance.get('preclose',{}),performance.get('close',{})
    dry_good = dry.get('status') == 'dry_run_success'
    next_date=calendar.get('next_trade_date') if calendar.get('today')==date else None
    return f'''# {heading}

- trade date：`{date}`
- 當日狀態：`{status}`
- phase：`{record.get('phase','waiting')}`
- runner startedAt：`{record.get('runner_started_at','尚未啟動')}`
- Python startedAt：`{record.get('python_started_at','—')}`
- finishedAt：`{record.get('finished_at','—')}`
- executionId：`{record.get('run_id','—')}`
- 股票池：`{record.get('universe_count','尚未取得')}`
- 13:25 成功數／總數：`{pre.get('success_count','—')}/{pre.get('stock_universe_count','—')}`
- 13:30 成功數／總數：`{close.get('success_count','—')}/{close.get('stock_universe_count','—')}`
- 13:33 回傳數（正式收盤辨識未驗證）：`{performance.get('delayed_close',{}).get('success_count','—')}`
- 13:25／13:30 耗時：`{pre.get('wall_time_seconds','—')} / {close.get('wall_time_seconds','—')} 秒`
- missing：`{pre.get('missing_count','—')} / {close.get('missing_count','—')}`
- timeout：`{pre.get('timeouts','—')} / {close.get('timeouts','—')}`
- retry：`{pre.get('retries','—')} / {close.get('retries','—')}`
- error：`{record.get('error','—')}`
- 官方核對：`{record.get('official_validation','未驗證')}`
- ±3%：**未產生；價格與試撮欄位尚未驗證**
- Artifact：`{record.get('artifact','—')}`
- 最後成功更新：`{record.get('updated_at','—')}`

## 下一次預定執行

- Next run date：`{next_date or next_weekday(now)}`（{'官方開休市日曆已核對' if next_date else '平日排程；官方日曆待核對'}）
- 提前啟動：**11:47 Asia/Taipei**，UTC `47 3 * * 1-5`
- 原排程保留：**13:07**，UTC `7 5 * * 1-5`
- 備援：**13:12／13:17／13:22**，UTC `12,17,22 5 * * 1-5`
- runner 內等待 **13:24:50／13:30:02**；13:24:45 後啟動不得補抓。
- 同日完成或已有 preclose 證據就跳過備援，避免覆蓋原始資料。
- 漏跑檢查預定：**13:40／13:50**。GitHub 排程可能延遲，這兩次檢查也不是準點保證。
- 排程不需要 ChatGPT、Work 或使用者電腦開機。

## 獨立連線測試（不代表盤中完成）

- dry-run：`{'SUCCESS' if dry_good else dry.get('status','尚未執行')}`
- 時間：`{dry.get('finished_at','—')}`；run：`{dry.get('run_id','—')}`
- 股票池：`{dry.get('stock_universe_count','—')}`；MIS 回傳：`{dry.get('returned_count','—')}`
- dry-run 不會把上方當日失敗改成成功。

## 實際排程回執

- event：`{receipt.get('event','尚未觀察')}`
- cron：`{receipt.get('cron','—')}`
- 實際 runner 啟動：`{receipt.get('runner_started_at','—')}`
- run：`{receipt.get('run_id','—')}`

2026-09-29：missing / incomplete。2026-09-30 原排程直到 19:05 才啟動，failed_late_start；沒有補值。
狀態永久保存在本獨立 repo 的 state/；這是資料驗證環境，沒有 Production 變更。
'''


def publish():
    now = probe.now_tpe()
    record,_ = read_state(live_path(now.date().isoformat()))
    dry,_ = read_state('state/dry_run_latest.json')
    receipt,_ = read_state('state/schedule_latest.json')
    calendar,_ = read_state('state/calendar_latest.json')
    api('issues/'+str(ISSUE),'PATCH',{'body':render(now,record,dry,receipt,calendar)})


def receipt():
    if os.getenv('GITHUB_EVENT_NAME') != 'schedule':return
    data = {'event':'schedule','cron':os.getenv('SCHEDULE_CRON',''),
        'run_id':os.getenv('GITHUB_RUN_ID'),
        'runner_started_at':os.getenv('RUNNER_STARTED_AT') or probe.iso(),'received_at':probe.iso()}
    merge_state('state/schedule_receipts/'+str(data['run_id'])+'.json',data)
    merge_state('state/schedule_latest.json',data)
    print(json.dumps({'schedule_receipt':data}),flush=True)


def skip_existing(record):
    return record.get('status') in ('success_raw_capture','partial') or bool(record.get('preclose_captured'))


def health(output):
    now = probe.now_tpe();date=now.date().isoformat()
    try:calendar=calendar_state(now,output)
    except Exception as exc:
        print('Calendar check unavailable: '+type(exc).__name__,flush=True)
        calendar={}
    record,_ = read_state(live_path(date))
    if calendar.get('is_trading_day',now.weekday()<5) and now.strftime('%H:%M:%S') >= '13:40:00' and record.get('phase') != 'completed':
        if not record:
            record = merge_state(live_path(date),{'trade_date':date,'status':'failed_missing',
                'phase':'watchdog','error':'No live execution record by the health check; no backfill'})
        elif record.get('status') == 'running':
            record = merge_state(live_path(date),{'status':'failed_incomplete',
                'error':'No completion by 13:40 health check','watchdog_at':probe.iso()})
    publish()
    result = {'mode':'health','checked_at':probe.iso(),'live_state':record,
              'event':os.getenv('GITHUB_EVENT_NAME'),'cron':os.getenv('SCHEDULE_CRON')}
    (output/'health.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return 0


def run(mode, output):
    output.mkdir(parents=True,exist_ok=True)
    receipt()
    if mode == 'health':return health(output)
    if mode == 'workflow-failure':
        date=probe.now_tpe().date().isoformat()
        record,_=read_state(live_path(date))
        if record.get('run_id')==os.getenv('GITHUB_RUN_ID') and record.get('status')=='running':
            merge_state(live_path(date),{'status':'failed','phase':'workflow_failure',
                'finished_at':probe.iso(),'error':'Workflow stopped unexpectedly; inspect Actions logs'})
        publish()
        return 0
    date = probe.now_tpe().date().isoformat()
    run_id = os.getenv('GITHUB_RUN_ID','local')
    started = os.getenv('RUNNER_STARTED_AT') or probe.iso()
    if mode == 'live':
        record,_ = read_state(live_path(date))
        if skip_existing(record):
            (output/'skipped.json').write_text(json.dumps({'status':'skipped_existing_capture','prior_run':record.get('run_id')}))
            print('Skipped: existing capture is immutable for this date.',flush=True)
            return 0
        # All live jobs share workflow concurrency; backups cannot run alongside it.
        if datetime.fromisoformat(started).astimezone(probe.TZ) > probe.target(date,'13:24:45'):
            merge_state(live_path(date),{'trade_date':date,'status':'failed_late_start',
                'phase':'failed_late_start','runner_started_at':started,'run_id':run_id,
                'python_started_at':probe.iso(),'error':'Started after 13:24:45; no backfill permitted',
                'artifact':'mis-probe-'+run_id})
            publish()
            (output/'run_summary.json').write_text(json.dumps({'status':'failed_late_start','runner_started_at':started}))
            probe.package(output,date)
            return 2
        calendar=calendar_state(probe.now_tpe(),output)
        if not calendar['is_trading_day']:
            (output/'skipped.json').write_text(json.dumps({'status':'official_nontrading_day'}))
            return 0
        merge_state(live_path(date),{'trade_date':date,'status':'running','phase':'starting',
            'run_id':run_id,'runner_started_at':started,'python_started_at':probe.iso(),
            'artifact':'mis-probe-'+run_id,'error':None,'finished_at':None,
            'snapshots':{},'official_validation':'unverified'})
        publish()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    updates = []
    def status_update(body):
        def work():
            phase = re.search(r'- phase：`([^`]+)`',body)
            count = re.search(r'- 股票池數量：`([^`]+)`',body)
            if mode == 'live':
                patch={'phase':phase.group(1) if phase else 'unknown',
                       'preclose_captured':(output/'preclose_raw.jsonl').exists()}
                if count and count.group(1).isdigit():patch['universe_count']=int(count.group(1))
                merge_state(live_path(date),patch)
                publish()
        updates.append(pool.submit(work))  # Never block the precise capture clock.
    probe.github_issue = status_update
    code = 1
    failure = None
    try:
        code = probe.dry_run(output) if mode == 'dry-run' else probe.live(output)
    except Exception as exc:
        failure = {'status':'failed','error':f'{type(exc).__name__}:{exc}',
                   'finished_at':probe.iso(),'trade_date':date,'run_id':run_id}
        (output/'run_summary.json').write_text(json.dumps(failure,ensure_ascii=False,indent=2))
        probe.package(output,date)
    finally:
        pool.shutdown(wait=True)
        status_errors = []
        for future in updates:
            try:future.result()
            except Exception as exc:status_errors.append(type(exc).__name__+':'+str(exc))
        summary_path=output/'run_summary.json'
        summary=json.loads(summary_path.read_text()) if summary_path.exists() else {}
        if mode == 'dry-run':
            analysis=summary.get('analysis',{})
            merge_state('state/dry_run_latest.json',{'status':'dry_run_success' if code==0 and not failure else 'dry_run_failed',
                'run_id':run_id,'finished_at':probe.iso(),'stock_universe_count':summary.get('stock_universe_count'),
                'returned_count':analysis.get('returned_count'),'error':(failure or {}).get('error')})
        else:
            patch=dict(summary,finished_at=probe.iso(),trade_date=date,run_id=run_id,
                runner_started_at=started,preclose_captured=(output/'preclose_raw.jsonl').exists())
            if failure:patch.update(failure)
            if status_errors:patch['status_update_errors']=status_errors
            merge_state(live_path(date),patch)
        publish()
        (output/'controller_status.json').write_text(json.dumps({'mode':mode,'exit_code':code,
            'status_errors':status_errors,'finished_at':probe.iso()},ensure_ascii=False,indent=2))
        probe.package(output,date)
    return code


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['live','dry-run','health','workflow-failure'],required=True)
    parser.add_argument('--output',type=Path,default=Path('results'))
    args=parser.parse_args()
    raise SystemExit(run(args.mode,args.output))
