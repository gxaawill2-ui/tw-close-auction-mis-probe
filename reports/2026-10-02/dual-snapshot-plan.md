# 下一交易日雙快照研究版

本次只使用既存 `mis-probe-36856545941` 做離線測試，沒有重抓 10/2 盤中 MIS，也沒有把當天其他時点改名為 A/B。10/2 公司池 1977、可交易池 1970；三份原快照皆 1970/1970。原 Artifact 與 state/live/2026-10-02.json 保持原樣。

10/2 2330 在 planned 13:25:50 的回應（received 13:25:51.165）顯示 trade.t=13:24:59、trade.z=2505.0000；planned 13:26:00 又回到 server 13:24:51、trade.t=13:24:25、trade.z=2500.0000。原始完整記錄節選保存於 fixtures/cache-regression-20261002.json。固定等待秒數與 request 時間均不能證明新鮮度；13:25:25 的新鮮 server clock 也仍伴隨尚未追到最後成交的個股資料。

|工作|Asia/Taipei 時間|用途|
|---|---|---|
|既有提前啟動|11:47；13:07／12／17／22 備援|runner 自行等待；13:24:45 後才啟動不得補盤中|
|原全市場快照|13:24:50|僅研究，不用作 P_before|
|pre_reference_A|13:27:00|第一份全市場參考|
|pre_reference_B|13:28:15|第二份全市場參考|
|pre targeted retry deadline|13:29:30|只抓 affected symbols，仍不收斂 unknown|
|close_reference_A|13:32:30|第一份全市場收盤參考|
|close_reference_B|13:33:20|實際延後收盤後的第二份參考|
|close targeted retry deadline|13:35:00|只抓 affected symbols，仍不收斂 unknown|
|盤後官方重驗|14:50／15:20／17:50|重讀保存 Artifact；指定交易日官方表；不抓 MIS|

全市場維持 batch 50、concurrency 5；固定 2330／2317／2454／1341／1410／1240／1781／1813 探針及其每秒區間、後續 checkpoints 完整保留。下一交易日依既存官方日曆為 2026/10/05；原 schedule 保持 enabled。GitHub 排程仍可能延遲，未聲稱準點保證。

研究 freshness gate 要求 HTTP 成功、個股與 server 同日、clock plausible、收到回應距 server 時間最多 15 秒。15 秒僅為可調研究門檻；queryTime 的 Asia/Taipei 解讀尚未獨立驗證，cachedAlive 單位仍 UNVERIFIED。pre server 必須已進入 13:25 後；close B／retry server 必須已進入 13:33 後。

兩筆不同且遞增的新鮮 server observation，trade.t／trade.z／v 必須完全一致。pre trade.t 必須 <13:25:00。原 A/B 與後來採用的替代配對證據分開保存。任何 stale、缺資料、非單調時間或 probe 矛盾都中斷候選收斂；不以較大的 trade.t 或連續不變的舊 cache 補值。

正常 13:30 成交與晚看到的 13:30 成交同屬 normal candidate。A/B 變動且 trade.t 約 13:33 先列 delayed transition candidate，再用新鮮 targeted observation 確認相同結果。若 A/B 都保留 pre-13:25 成交，列 no_closing_new_trade_candidate，保留最後实际成交候選等待官方收盤核對。官方 PENDING 不算擷取失敗；已發布但 mismatch 的股票排除 research 名單。

報告列原 A/B 收斂率、targeted recovery、最終 pre／close／both 收斂、stale batches、server regression、定向重抓、delayed candidates、無新收盤成交、research 可計算及 ±3% 數量。`convergence.csv` 保留使用者指定的 per-stock A/B timestamp 與價格欄位；raw 全量保存。

研究 ±3% 只在 both converged 中計算 `P_close/P_before - 1`。PENDING 官方案例清楚標記為尚未核對；官方 mismatch 或高頻探針矛盾不得入選。所有 p_before/p_close/both validated=false，正式訊號 NOT_GENERATED；volume 差額與 tv/s/trade.v 保持 UNVERIFIED。

10/2 新版 A/B 時點未採樣，離線回放為 NOT_SAMPLED；計數 0 代表沒有本版配對證據，不是雙快照策略失败。原 8 個 confirmed_candidate 不升級為 validated。要到下一交易日實測才能判斷全市場收斂率，後續跨日資料與官方核對才可能支持升級規則。
