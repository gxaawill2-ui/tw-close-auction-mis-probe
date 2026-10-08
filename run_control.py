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
import candidate_publication

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
            raw=response.read()
            return json.loads(raw) if raw else {}
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
        if patch.get('status') == 'failed_missing' and (current.get('capture_claimed') or current.get('capture_blocked')):
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
    merge_state('state/calendars/'+str(year)+'.json',{'year':year,'closed_dates':sorted(closed),
        'source':url,'verified_at':state['verified_at'],'status':'OFFICIAL_ANNUAL_CALENDAR',
        'limitations':'Intraday emergency closures not independently monitored; live runner rechecks official calendar.'})
    return state


def render(now, record, dry, receipt, calendar=None, armed=None, validation=None, next_armed=None, external=None, execution=None):
    date = now.date().isoformat()
    calendar=calendar or {}
    if record.get('trade_date') != date:record = {}
    status = record.get('status','waiting')
    if not record and now.strftime('%H:%M:%S') >= '13:40:00' and now.weekday() < 5:
        status = 'failed_missing'
    if not record and calendar.get('today')==date and not calendar.get('is_trading_day'):
        status = 'nontrading_day'
    titles = {'waiting':'⏳ 等待當日排程','running':'🟡 RUNNING',
        'missing_incomplete':'❌ NOT RUN — missing / incomplete — scheduler did not trigger',
        'success_raw_capture':'✅ 原始資料擷取完成（欄位未驗證）','partial':'⚠️ PARTIAL',
        'failed_missing':'❌ FAILED — 當日漏跑','failed_late_start':'❌ FAILED — 啟動過晚',
        'failed_incomplete':'❌ FAILED — 13:40 尚未完成','failed':'❌ FAILED',
        'nontrading_day':'⏸️ 官方休市日'}
    heading = titles.get(status,'❌ FAILED — '+status)
    performance = record.get('snapshots',{})
    pre,close = performance.get('preclose',{}),performance.get('close',performance.get('close_reference_B',{}))
    dry_good = dry.get('status') == 'dry_run_success'
    next_date=calendar.get('next_trade_date') if calendar.get('today')==date else None
    armed=armed or {}
    validation=validation or {}
    next_armed=next_armed or {}
    fresh=record.get('freshness',{})
    dual=record.get('convergence',{})
    official_dual=validation.get('convergence',{})
    research=validation if official_dual.get('status') == 'RESEARCH_ONLY' else record
    research_status=research.get('candidate_status','NOT_GENERATED')
    research_count=research.get('candidate_count','—')
    external=external or {}
    execution=execution or {}
    close_label='13:30' if 'close' in performance else '13:33:20 close B'
    reference_table='\n'.join(
        f"|{phase}|{performance.get(phase,{}).get('success_count','—')}/{performance.get(phase,{}).get('stock_universe_count','—')}|{performance.get(phase,{}).get('wall_time_seconds','—')}|{performance.get(phase,{}).get('first_request_started_at','—')}|"
        for phase in probe.convergence.reference_times(date))
    return f'''# {heading}｜{date}

- trade date：`{date}`
- 當日狀態：`{status}`
- phase：`{record.get('phase','waiting')}`
- runner startedAt：`{record.get('runner_started_at','尚未啟動')}`
- Python startedAt：`{record.get('python_started_at','—')}`
- finishedAt：`{record.get('finished_at','—')}`
- executionId：`{record.get('run_id','—')}`
- 股票池：`{record.get('universe_count','尚未取得')}`
- 13:25 成功數／總數：`{pre.get('success_count','—')}/{pre.get('stock_universe_count','—')}`
- {close_label} 成功數／總數：`{close.get('success_count','—')}/{close.get('stock_universe_count','—')}`
- 13:33 回傳數（正式收盤辨識未驗證）：`{performance.get('delayed_close',{}).get('success_count','—')}`
- 13:24:50 研究快照／{close_label} 耗時：`{pre.get('wall_time_seconds','—')} / {close.get('wall_time_seconds','—')} 秒`
- missing：`{pre.get('missing_count','—')} / {close.get('missing_count','—')}`
- timeout：`{pre.get('timeouts','—')} / {close.get('timeouts','—')}`
- retry：`{pre.get('retries','—')} / {close.get('retries','—')}`
- error：`{record.get('error','—')}`
- capture outcome：`{record.get('capture_outcome',status)}`；warning 數：`{len(record.get('capture_completion',{}).get('warnings',[]))}`；研究無法計算：`{record.get('capture_completion',{}).get('research_unresolved_count','—')}`。
- 官方核對：`{record.get('official_validation','未驗證')}`
- research ±3%：`{research_status}`／候選 ` {research_count} `；正式 validated=false，Production 訊號未產生。
- Artifact：`{record.get('artifact','—')}`
- 最後成功更新：`{record.get('updated_at','—')}`

## 外部主觸發／GitHub Pages

- cron-job.org 設定狀態：`{external.get('status','PENDING_USER_SETUP')}`；實際外部 Test 證明：`{external.get('verified_test_run_id','尚未驗收')}`。
- 主觸發 13:00、備援 13:10／13:18，Asia/Taipei。未完成外部 Test 前不能宣稱外部排程已設定成功。
- GitHub Cron 僅第二層備援。workflow_dispatch 的 source 欄位只是呼叫端聲明，不能單憑它证明來自 cron-job.org。
- [手機狀態頁](https://gxaawill2-ui.github.io/tw-close-auction-mis-probe/)；未啟用時請 Settings → Pages → main /docs → Save。
- 最近 workflow：`{execution.get('run_id','—')}`；event：`{execution.get('event','—')}`；宣告來源：`{execution.get('declared_source','—')}`。
- 外部 Test、dry-run 或防重複測試，不能把今天漏跑改成 SUCCESS。

## Freshness Probe（研究版）

- 下一交易日保持同一組 8 檔；batch 50 / concurrency 5。
- 13:24:50–13:25:10 每秒；13:25:15–13:26:10 每 5 秒。
- 13:29:50–13:30:15 每秒；13:30:20／30／45、13:31:00／30、13:32:00／30、13:33:00／15。
- 下一版全市場 P_before：13:27:00 A／13:28:15 B；13:24:50 僅研究資料。
- 下一版全市場 P_close：13:32:30 A／13:33:20 B；13:30 保留 8 檔探針研究。
- A/B 必須為不同 fresh server observation，trade.t／trade.z／v 一致；單靠固定等待時間或 cachedAlive 不算 fresh。
- 不一致／stale／server regression，只補 affected symbols；pre 最晚 13:29:30、close 最晚 13:35，未收斂 unknown，不補值。
- 13:33 新成交變化先列 delayed candidate，再以定向新鮮觀察確認；晚看到 13:30 成交仍是正常收盤候選。
- 當日無新收盤成交保留最後實際成交候選，之後官方核對；官方尚未發布 PENDING 不算失敗。
- 當日雙快照版本：`{dual.get('version','尚未採樣此版')}`；狀態：`{dual.get('status','NOT_SAMPLED')}`。
- P_before／P_close／both converged：`{dual.get('p_before_converged_count','—')} / {dual.get('p_close_converged_count','—')} / {dual.get('both_converged_count','—')}`。
- stale batches／targeted retry requests：`{dual.get('stale_batch_count','—')} / {dual.get('targeted_retry_count','—')}`。
- delayed-close candidates／無新收盤成交：`{dual.get('true_delayed_close_candidate_count','—')} / {dual.get('no_closing_new_trade_count','—')}`。
- research 可計算股票數：`{research.get('research_calculable_count',research.get('convergence',{}).get('research_calculable_count','—'))}`。收盤量 UNVERIFIED。
- 原始 A/B、替代配對、unknown 清單、探針交叉比較與 research 名單保存在 Artifact。

|全市場 reference phase|成功／股票池|耗時秒|第一個 request|
|---|---|---|---|
{reference_table}

- 公司池／可交易池：`{record.get('company_universe_count','—')} / {record.get('universe_count','—')}`；股票池核對：`{record.get('universe_audit_status','—')}`。
- confirmed_candidate：`{fresh.get('confirmed_candidate_count','—')}`；P_before／P_close／both validated：`{fresh.get('p_before_validated_count','—')} / {fresh.get('p_close_validated_count','—')} / {fresh.get('both_validated_count','—')}`。
- server_age 為 Asia/Taipei 研究假設；cachedAlive 的單位／語意仍 UNVERIFIED。候選不代表 validated。
- [10/1 原始證據審查](https://github.com/{REPO}/tree/main/reports/2026-10-01)；新版時間線、收斂表、官方核對在每日 Artifact。

## 盤後官方重新核對

- 交易日期：`{validation.get('trade_date','尚未執行')}`；狀態：`{validation.get('status','PENDING')}`；檢查時間：`{validation.get('checked_at','—')}`。
- 官方價格一致／不一致／缺值：`{validation.get('matches','—')} / {validation.get('mismatches','—')} / {validation.get('unavailable','—')}`。
- Artifact：`{validation.get('artifact','—')}`。
- 14:50／15:20／17:50 排程只重讀已保存 Artifact 及指定日期官方資料，不重抓 MIS，不補盤中資料。
- 空表／錯誤日期維持 PENDING；保存實際檢查時間，發布確切時間未驗證。

## 10/1 官方例外離線核對（歷史）

- 6 筆不一致：未觀察到收盤新成交，nested trade 與官方收盤不同；原因仍未確定，不能直接宣稱 MIS 錯誤或延後成交。
- 33 筆缺值：9 檔官方排除、10 檔官方當日成交股數為零、14 檔有成交股數但整股收盤價空白。
- 已排除股票不計入 tradable 分母；24 檔無整股收盤價仍留在可交易池，禁止補零或沿用前日價格。
- [逐檔證據與分類](https://github.com/{REPO}/blob/main/reports/2026-10-01/official-exception-review.md)。

## 10/2 一次性預備等待任務

- 日期：`{next_armed.get("trade_date","尚未啟動")}`；狀態：`{next_armed.get("status","尚未啟動")}`。
- runner 啟動：`{next_armed.get("runner_started_at","—")}`；階段：`{next_armed.get("stage","—")}`。
- 下一接力時間：`{next_armed.get("next_target","—")}`。
- [實際等待任務](https://github.com/{REPO}/actions/runs/{next_armed.get("run_id","")})。
- 沿用原本接力方式，最後在 11:47 啟動正式 runner；原 cron 備援保留，接力仍受 GitHub runner 可用性影響。

## 下一次預定執行

- Next run date：`{next_date or next_weekday(now)}`（{'官方開休市日曆已核對' if next_date else '平日排程；官方日曆待核對'}）
- 外部主排程（待使用者設定／Test）：**13:00／13:10／13:18 Asia/Taipei**。
- GitHub 第二層備援提前啟動：**11:47 Asia/Taipei**，UTC `47 3 * * 1-5`
- GitHub 原排程保留：**13:07**，UTC `7 5 * * 1-5`
- 備援：**13:12／13:17／13:22**，UTC `12,17,22 5 * * 1-5`
- runner 內等待 **13:24:50／13:27:00／13:28:15／13:32:30／13:33:20**；13:24:45 後啟動不得補抓。
- 同日完成或已有 preclose 證據就跳過備援，避免覆蓋原始資料。
- 漏跑檢查預定：**13:40／13:50**。GitHub 排程可能延遲，這兩次檢查也不是準點保證。
- 排程不需要 ChatGPT、Work 或使用者電腦開機。

## 獨立連線測試（不代表盤中完成）

- dry-run：`{'SUCCESS' if dry_good else dry.get('status','尚未執行')}`
- 時間：`{dry.get('finished_at','—')}`；run：`{dry.get('run_id','—')}`
- 股票池：`{dry.get('stock_universe_count','—')}`；MIS 回傳：`{dry.get('returned_count','—')}`
- 公司池：`{dry.get('company_universe_count','—')}`；可交易池来源状态：`{dry.get('universe_audit_status','—')}`
- dry-run 不會把上方當日失敗改成成功。

## 實際排程回執

- event：`{receipt.get('event','尚未觀察')}`
- cron：`{receipt.get('cron','—')}`
- 實際 runner 啟動：`{receipt.get('runner_started_at','—')}`
- run：`{receipt.get('run_id','—')}`

2026-09-29：missing / incomplete。2026-09-30 原排程直到 19:05 才啟動，failed_late_start；沒有補值。
狀態永久保存在本獨立 repo 的 state/；這是資料驗證環境，沒有 Production 變更。

## 10/1 一次性預備 workflow（歷史紀錄）

- 狀態：`{armed.get('status','尚未啟動')}`
- 階段：`{armed.get('stage','—')}`
- 下一個接力時間：`{armed.get('next_target','—')}`
- workflow：[查看實際執行](https://github.com/{REPO}/actions/runs/{armed.get('run_id','')})
- 這是 9/30 先啟動、接力至 10/1 11:47 的一次性備援，並非下一交易日的預備工作。
- 任一段 runner／接力出錯仍可能失敗，原有 cron 備援繼續保留。
'''


def publish():
    now = probe.now_tpe()
    record,_ = read_state(live_path(now.date().isoformat()))
    dry,_ = read_state('state/dry_run_latest.json')
    receipt,_ = read_state('state/schedule_latest.json')
    calendar,_ = read_state('state/calendar_latest.json')
    armed,_ = read_state('state/armed/2026-10-01.json')
    validation,_=read_state('state/validation/'+now.date().isoformat()+'.json')
    armed_index,_=read_state('state/armed_latest.json')
    next_armed={}
    if armed_index.get('state_path'):
        next_armed,_=read_state(armed_index['state_path'])
    external,_=read_state('state/external_scheduler.json')
    execution,_=read_state('state/execution_latest.json')
    api('issues/'+str(ISSUE),'PATCH',{'body':render(now,record,dry,receipt,calendar,armed,validation,next_armed,external,execution)})


def receipt():
    event=os.getenv('GITHUB_EVENT_NAME')
    if event not in ('schedule','workflow_dispatch','push'):return
    source=os.getenv('TRIGGER_SOURCE','manual')
    if source not in ('manual','cron-job.org','cron-job.org-test','dispatch-safety-test'):source='unknown'
    data = {'event':event,'cron':os.getenv('SCHEDULE_CRON',''),
        'declared_source':source, 'source_verified':False,'mode':os.getenv('PROBE_MODE'),
        'run_id':os.getenv('GITHUB_RUN_ID'),
        'runner_started_at':os.getenv('RUNNER_STARTED_AT') or probe.iso(),'received_at':probe.iso()}
    kind='schedule' if event=='schedule' else 'dispatch'
    merge_state('state/'+kind+'_receipts/'+str(data['run_id'])+'.json',data)
    merge_state('state/'+kind+'_latest.json',data)
    merge_state('state/execution_latest.json',data)
    print(json.dumps({'execution_receipt':data}),flush=True)


def skip_existing(record):
    return (record.get('status') in ('success_raw_capture','partial') or bool(record.get('preclose_captured'))
            or bool(record.get('capture_blocked')) or bool(record.get('capture_claimed'))
            or record.get('status')=='running')


def claim_capture(path, patch):
    """Atomic claim: a 409/422 re-reads ownership rather than overwriting it.

    Once claimed the day is never auto-unlocked, even after a crash. An orphaned
    claim is failed/incomplete evidence, not permission to replay a market window.
    """
    for _ in range(4):
        current,sha=read_state(path)
        if skip_existing(current):return False,current,sha
        current.update(patch)
        current.update(capture_claimed=True,capture_owner_run_id=patch['run_id'],
                       claimed_at=probe.iso(),updated_at=probe.iso())
        payload={'message':'Claim isolated MIS daily capture','branch':'main',
                 'content':base64.b64encode((json.dumps(current,ensure_ascii=False,indent=2)+'\n').encode()).decode()}
        if sha:payload['sha']=sha
        try:
            result=api('contents/'+path,'PUT',payload)
            return True,current,(result.get('content') or {}).get('sha')
        except urllib.error.HTTPError as exc:
            if exc.code not in (409,422):raise
    raise RuntimeError('Daily capture claim conflict; refusing MIS capture')


def dispatch_safety(output):
    test_id=os.getenv('DISPATCH_TEST_ID','')
    if not re.fullmatch(r'\d{1,24}',test_id):raise ValueError('Numeric dispatch test id required')
    path='state/tests/dispatch-'+test_id+'.json'
    run_id=os.getenv('GITHUB_RUN_ID','local')
    claimed,state,sha=claim_capture(path,{'run_id':run_id,'status':'TEST_ONLY',
        'scope':'DISPATCH_SAFETY_ONLY_NOT_MARKET_EVIDENCE','sentinel':test_id,
        'started_at':os.getenv('RUNNER_STARTED_AT') or probe.iso()})
    report={'test_id':test_id,'run_id':run_id,'decision':'CLAIMED_TEST_ONLY' if claimed else 'SKIPPED_EXISTING_CAPTURE',
            'owner_run_id':state.get('capture_owner_run_id'),'state_sha':sha,'mis_requests':0,
            'market_evidence_generated':False,'daily_live_state_mutated':False}
    (output/'dispatch_safety.json').write_text(json.dumps(report,indent=2))
    (output/'controller_status.json').write_text(json.dumps({'mode':'dispatch-safety','exit_code':0,'status_errors':[]}))
    # Keep the first workflow active long enough to dispatch a queued duplicate.
    if claimed:probe.wait_until(probe.now_tpe()+timedelta(seconds=30))
    publish()
    probe.package(output,probe.now_tpe().date().isoformat())
    return 0


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
    if mode == 'dispatch-safety':return dispatch_safety(output)
    if mode == 'validation':
        import official_retry
        return official_retry.run(probe.now_tpe().date().isoformat(),output,__import__(__name__),probe)
    if mode == 'health':return health(output)
    if mode == 'workflow-failure':
        date=probe.now_tpe().date().isoformat()
        record,_=read_state(live_path(date))
        upload_failed=os.getenv('ARTIFACT_UPLOAD_OUTCOME')=='failure'
        if record.get('run_id')==os.getenv('GITHUB_RUN_ID') and (record.get('status')=='running' or upload_failed):
            merge_state(live_path(date),{'status':'failed','phase':'artifact_upload_failed' if upload_failed else 'workflow_failure',
                'capture_outcome':'CAPTURE_FAILED',
                'artifact_upload_status':'FAILED' if upload_failed else record.get('artifact_upload_status','UNKNOWN'),
                'finished_at':probe.iso(),'error':'ARTIFACT_UPLOAD_FAILED' if upload_failed else 'Workflow stopped unexpectedly; inspect Actions logs'})
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
        claimed,prior,_=claim_capture(live_path(date),{'trade_date':date,'status':'running','phase':'starting',
            'run_id':run_id,'runner_started_at':started,'python_started_at':probe.iso(),
            'artifact':'mis-probe-'+run_id,'error':None,'finished_at':None,
            'snapshots':{},'official_validation':'unverified'})
        if not claimed:
            (output/'skipped.json').write_text(json.dumps({'status':'skipped_existing_capture','prior_run':prior.get('run_id')}))
            return 0
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
                # A persisted progress view must not pretend an in-flight phase
                # already completed; only an existing raw file provides counts.
                for reference in probe.convergence.reference_times(date):
                    file=output/(reference+'_raw.jsonl')
                    if file.exists():
                        try:rows=[json.loads(line) for line in file.read_text().splitlines()]
                        except (OSError,json.JSONDecodeError):continue
                        phase_state={'status':'partial' if any(r.get('error') or r.get('missing') for r in rows) else 'captured','requested_at':min((r.get('requested_at') for r in rows),default=None),
                            'received_at':max((r.get('received_at') for r in rows),default=None),
                            'returned_count':sum(r.get('returned_count',0) for r in rows),
                            'missing_count':sum(len(r.get('missing',[])) for r in rows)}
                        patch.setdefault('reference_progress',{})[reference]=phase_state
                merge_state(live_path(date),patch)
                publish()
        updates.append(pool.submit(work))  # Never block the precise capture clock.
    probe.github_issue = status_update
    code = 1
    failure = None
    candidate_publication_result = None
    try:
        code = probe.dry_run(output) if mode == 'dry-run' else probe.live(output)
        if mode == 'live' and code == 0:
            # After raw packaging; before waiting for diagnostic status IO.
            # This never delays a market snapshot.
            try:
                candidate_publication_result = candidate_publication.publish_live(
                    output,date,run_id,__import__(__name__),probe)
            except Exception as exc:
                candidate_publication_result = {'status':'FAILED','error':type(exc).__name__+':'+str(exc)}
                (output/'candidate_publication.json').write_text(json.dumps(candidate_publication_result,ensure_ascii=False,indent=2))
                code = 4  # Publication failure; retain the true capture outcome.
    except Exception as exc:
        failure = {'status':'failed','capture_outcome':'CAPTURE_FAILED','error':f'{type(exc).__name__}:{exc}',
                   'finished_at':probe.iso(),'trade_date':date,'run_id':run_id}
        (output/'run_summary.json').write_text(json.dumps(failure,ensure_ascii=False,indent=2))
        try:
            probe.package(output,date)
        except Exception as exc:
            if mode == 'live':
                merge_state(live_path(date),{'status':'failed','capture_outcome':'CAPTURE_FAILED',
                    'phase':'artifact_package_failed','error':f'{type(exc).__name__}:{exc}'})
            raise
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
                'runner_started_at':started,'event':os.getenv('GITHUB_EVENT_NAME'),'declared_source':os.getenv('TRIGGER_SOURCE','manual'),
                'company_universe_count':summary.get('company_universe_count'),'universe_audit_status':summary.get('universe_audit_status'),
                'returned_count':analysis.get('returned_count'),'error':(failure or {}).get('error')})
        else:
            patch=dict(summary,finished_at=probe.iso(),trade_date=date,run_id=run_id,
                runner_started_at=started,preclose_captured=(output/'preclose_raw.jsonl').exists())
            if failure:patch.update(failure)
            if status_errors:patch['status_update_errors']=status_errors
            if candidate_publication_result:
                patch['candidate_publication']=candidate_publication_result
            merge_state(live_path(date),patch)
        publish()
        (output/'controller_status.json').write_text(json.dumps({'mode':mode,'exit_code':code,
            'status_errors':status_errors,'finished_at':probe.iso()},ensure_ascii=False,indent=2))
        try:
            probe.package(output,date)
        except Exception as exc:
            if mode == 'live':
                merge_state(live_path(date),{'status':'failed','capture_outcome':'CAPTURE_FAILED',
                    'phase':'artifact_package_failed','error':f'{type(exc).__name__}:{exc}'})
            raise
    return code


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['live','dry-run','health','workflow-failure','validation','dispatch-safety'],required=True)
    parser.add_argument('--output',type=Path,default=Path('results'))
    args=parser.parse_args()
    raise SystemExit(run(args.mode,args.output))
