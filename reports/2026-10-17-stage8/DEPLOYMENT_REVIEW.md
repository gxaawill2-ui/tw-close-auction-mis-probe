# 第一輪正式部署審查與回滾（尚未部署）

目前正式基準：`79b071962fff0ea2e3a715822cfa1fa2e9cdf1f0`。真正整合前必須再次讀取最新 main；不可 reset、整支 stage4 merge 或 force push。本輪正式 main、collector、正式 workflow、排程、Secret、網址均無寫入。

## 可分開批准的最小範圍

1. **純演算法修正**：把 Private `lab/stage8/selection.before()` 的已回放規則適配到正式 `convergence.py`，更新必要測試。保留 A/B/C 固定時刻、原請求數、股池與成交量契約；不需新增 MIS 請求，不需改正式 workflow。效果為 10/13 恢復 40 檔可計算、6276 新增候選，另把五個交易日合計五筆有矛盾的原計算結果轉 UNKNOWN。這份私有實作尚未寫進公開 repo；如第一輪沿用公開 Python，修改內容也將是公開的，必須在批准時說清楚。
2. **C2 定向收盤確認**：適配 `retry.C2`、既有隔離 `close.assess()` TARGETED 邏輯到 `probe.py`／`close_research.py`，以及 `volume_evidence.py` 實際 raw 定位相容性。只處理 P_before 已可用且有一筆有效 13:30 或13:33成交、尚未多次確認者；不只挑已見 ±3%，避免篩選偏誤。最多12檔、每日兩批、每檔兩次、相隔至少3秒；13:34:42不再啟動，最晚13:34:50接收，保留發布時間；遇403/429停止。持久化次數先寫後發，重啟不能重置。`bounded_fetch` 以子程序限時，stall 可結束；正式適配尚需驗證實際 HTTP adapter、runner 與檔案保存。**此項需要新增實際MIS請求的正式批准及未來實盤樣本。** 不新增第二套全市場；不預設要改 workflow 或排程。
3. **同日結果更新/UNKNOWN/撤回**：Private `updates.py`/`publication.py` 與 `proposed/stage8/candidate_publication.py`、`status.js` 是審查方案。保留原 `state/candidates/YYYY-MM-DD.json`、GitHub Pages與20秒讀取；同capture_run、連續revision、遞增evidence_sequence、前版fingerprint與Contents API SHA CAS；錯誤不回報假成功，後續舊資料被拒絕。UNKNOWN另列、撤回從有效候選移除；保留日期/更新時間與量能排序。新資料來源仍需正式 collector 提供，因此writer與reader應配套整合。沒有引入Worker、bridge、consumer、新權限或每日排程。原官方盤後核對仍使用保存的當日資料。
4. **Private核心正式切換**：另一次獨立決策，這次不做。不要與上述修復同時上線。

## 具體待改檔案

最小核心修復為 `convergence.py` 及對應測試；C2加 `probe.py`、`close_research.py`、對應測試及持久化ledger；結果更新加 `candidate_publication.py`、`docs/status.js`、測試。既有股池、事件、CSS、正式網址、cron-job.org與Secrets不需因這些功能更動。現有 `candidate_publication` 是immutable價格契約，未修writer就不能只改前端宣稱會撤回；現前端不接受TARGETED，故也不能只改collector發出新分類。

本輪沒有準備可一鍵直接合併的正式核心補丁，因需從**當時最新 main**適配且新核心目前保持Private。兩份writer/reader審查diff已做暫存副本apply/reverse，`rollback.json`證明原bytes完全恢復，沒有套用正式檔案。

## 回滾

- 第一步先關閉新C2入口，只停止新請求；保留已接收的真實證據、ledger及當日JSON，不能把事後未抓到的內容補造。
- 以針對本輪檔案的revert恢復已核准之前版本；不reset main、不刪其他Work的新commit。新舊writer/reader需配套，不能讓舊前端遇到TARGETED而整份拒收；先產生相容投影或同時revert兩端。
- 當日撤回紀錄與新版本不可直接由舊JSON覆蓋。以更高revision保留錯誤更正與說明；必要時顯示資料不足及實際日期。不能讓回滾恢復錯誤候選而不留紀錄。
- 合成/離線回滾已驗證；正式部署、實際線上回滾與C2真實延後收盤未發生，不宣稱通過。
