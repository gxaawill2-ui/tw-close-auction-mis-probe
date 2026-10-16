# 來源語意、公開使用與免費額度

查閱官方文件日期：2026/10/16。以下不是完整行情或部署驗收。

## 富果

- 官方 Trades 文件提供 offset／limit、時間降冪或升冪排序，以及試撮查詢；成交 size、volume、time、serial 分別稱成交單量、總量、時間及流水號。
- 官方 Quote 區分 `lastTrade` 與 `lastTrial`；`lastPrice` 包含試撮，不能拿來證明實際成交。`closePrice` 是收盤價／最後成交價，因此單靠該欄位存在不能證明正式收盤。
- 官方資料欄位說明沒有保證每檔 serial 連號，也沒有明確說明相同微秒的多筆成交應怎樣打破排序。不能把流水號缺口直接視為遺漏，或自行用最大 serial 解決價格衝突。
- 完整日內 rows 數、size 合計與 Quote 統計相同，以及穩定 quote bracket，都是需要檢驗的條件；不能只用兩個來源相同價格當成獨立證明。
- 若未到 terminal page、分頁期間 quote 改變、有重複／缺頁／時序衝突／快取疑義／缺乏收盤信號，就維持 UNKNOWN 或 RESEARCH_ONLY。
- 目前 source contract 與 LIVE VERIFIED 都未放行；後續要根據真實保存的證據重新審查，而不是調整旗標強行通過。

基本方案官方額度為日內 API 60 次／分鐘；本輪 Source 共享上限 160 次、至少間隔 1.3 秒，且只查少量控制樣本與候選，不掃全市場。401／403／429 停止。
這是本次受控預算，並非已驗收每天能查完所有候選；超出 12 檔 queue 容量或請求預算的股票仍可能無法完成獨立確認。

原始富果回應不得進公開 Repo、公開 Artifact 或公開 Worker。對外 view 僅允許 MIS 衍生研究欄位與非原始診斷；這項過濾不等於已取得任何行情再散布授權。
當前私有 Worker 因外部 403 無法驗收，今天使用私有 runner 暫存，結束後不可還原；此缺口必須保留在結論中。

官方來源：

- https://developer.fugle.tw/docs/data/http-api/intraday/trades/
- https://developer.fugle.tw/docs/data/http-api/intraday/quote/
- https://developer.fugle.tw/docs/pricing/

## Cloudflare

已查閱官方 Workers 與 Durable Objects 免費額度文件。正式擴大使用前仍需核對帳號當時方案及帳號共用用量，不得自行升級付費。

公開頁每 5 秒讀取一次，單一瀏覽器每小時約 720 次動態讀取；100 位同時開啟一小時約 72,000 次，還要加其他請求與帳號共用用量，因此不能承諾大量使用者永久免費或無限制。
私有證據採明確容量與保存天數上限；若達到預算或回應失敗，就保留不足／待發布狀態，不回報寫入成功。

官方來源：

- https://developers.cloudflare.com/workers/platform/limits/
- https://developers.cloudflare.com/durable-objects/platform/limits/
- https://developers.cloudflare.com/durable-objects/platform/pricing/
