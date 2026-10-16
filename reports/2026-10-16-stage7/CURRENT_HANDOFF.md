# 第七階段目前接手位置

先git ls-remote核對遠端，使用stage4/20261016-fugle-probe最新HEAD。本文件所在的遠端commit才是有效報告版本；實作/驗收commit與run詳STATUS.md。不要把舊stage6或舊本機worktree覆蓋回來；不要force push。main、正式網站、collector/workflow/schedule/cron-job.org/正式Secret均未變更。

## 本輪已完成

1. 同一既有Worker新增固定30日私有複製封存；已真實複製60物件並由另一Runner只讀封存恢復14組、核對250,517 bytes全部SHA256。期限11/15台北13:06:22；不是七日區重新讀取冒充備份。
2. 四檔從私有長期封存重新研究；Quote四個時間欄位與Trades對應serial在6228/5546差180秒，根因仍未由官方釐清；Age及isDelayedClose缺失不能自動當0/false。
3. C2規劃補強C未收斂/矛盾、每檔每日2次總限、3秒冷卻與截止。320批真實保存MIS離線重播仍只把5546列待查，不新增行情請求，公開初篩三檔不變。
4. 本機與GitHub Runner真正workerd的journal→壓縮bridge→consumer→研究→UNKNOWN→撤回、重啟、舊版本拒收、背景來源/bridge失敗隔離通過。明確是合成資料，未作實盤聲稱。
5. 修正隔離頁研究/UNKNOWN重複計數：總3=研究2+UNKNOWN1+VERIFIED0。真實外部Chrome19:26讀取與排序通過，手機未測。
6. 正式journal hook、唯寫bridge workflow、獨立consumer、正式同網址只讀即時區各有分開白名單提案。只在reports/proposed與暫存副本apply/reverse；所有正式檔案原bytes還原。新網站預設enabled=false、live_released=false。
7. 分支專用stage7-live-shadow.yml準備好10/19一次性Artifact影子驗收（無cron），新日程/原始資料防公開/請求預算/重新啟動/來源選取/後續30日archive+第二Runner recover均備妥。已建立10/19 13:00啟動及14:55核對的一次性工作；11/12 13:06到期提醒。

## 不能宣稱已完成

VERIFIED仍0。4609及1235截止價格組唯一、量/筆數實證一致，但來源完整性/統計/分頁最終性契約未確認。6228最後截止組多價且收盤時間矛盾；5546亦有時間矛盾且缺第二次MIS延後收盤。不得解除LIVE_CONTRACT或Worker旗標來湊數。官方收盤價MATCH不等於P_before已證明。

正式journal/bridge雲端串接未啟用：新唯寫Token與Environment權限未批准，不能拿現有完整publisher/Fugle憑證塞進正式collector補做。正式網站讀API的patch也未部署。

實體手機沒有回傳；桌機與模擬測試不能代替。10/19尚未到來，沒有當日實盤PASS或過去盤中發布時間。本輪0個MIS/富果行情請求。

## 下一個Work直接繼續

優先讀SOURCE_VALIDATION_AND_PROVIDER_DRAFT.md、STORAGE_AND_PHONE_ACCEPTANCE.md、FORMAL_INTEGRATION_REVIEW.md、LIVE_ACCEPTANCE_20261019.md與STATUS.md。

- 等本人批准才可寄技術問題草稿。不得自動寄信或提供原始行情給新對象。
- 等本人逐項批准A/B/C/D或E才可正式變更，不整個分支合併。
- 10/19啟動時先檢查同日既有consumer/影子workflow，避免重複，再依LIVE_ACCEPTANCE_20261019更新唯一request檔。不要現在觸發。
- 手機由本人Safari開隔離頁，依最短四步回傳；若要刷新/撤回測試，在本人準備好後沿用2099合成日期受控輪替，不污染真實資料。
- 私有封存只使用既有隔離Environment；安全proof保存於real-private-archive-proof.json。若七日區已刪，仍從/private-archive讀並核對manifest，不能再依賴/private-evidence。

## 可重現指令（隔離checkout）

```sh
python3 -m unittest discover -v
npm ci --ignore-scripts
npm install --prefix "$RUNNER_TEMP/stage7-workerd" --ignore-scripts miniflare@4.20260730.0
MINIFLARE_MODULE="$RUNNER_TEMP/stage7-workerd/node_modules/miniflare" npm test
MINIFLARE_MODULE="$RUNNER_TEMP/stage7-workerd/node_modules/miniflare" node stage7_local_e2e.cjs
python3 stage7_prepare_review.py
```

最後一個e2e使用當日日期的合成fixture通過私有路由日期保護，須台北13:35:10後執行；不是即時行情。prepare_review需事先唯讀fetch origin/main，只改暫存副本/reports。Node舊測試會更新舊transport-local.json測試輸出；不要把那個無關檔案跟著提交。

API Key/raw只可存在私有記憶體/0700目錄/既有私有Worker。public Artifact只上傳safe-report指定目錄；不要add整個workspace或私有測試資料。
