# 四檔真實證據與來源問題（2026/10/16）

本輪只恢復既有私有資料，沒有新增富果或 MIS 行情請求。資料取得時間仍保留為原本 13:37～13:58；18:15 是重新分析時間，不能算盤中驗證成功。

| 股票 | 重新分析結果 | 阻止完整驗證的原因 |
| --- | --- | --- |
| 4609 | 終止頁 5 筆、筆數/量、累計量鏈、Quote/Trades/MIS、截止前最後組均吻合 | 尚缺完整區間及跨端點統計語意的來源確認 |
| 6228 | 終止頁 5 筆，筆數/量吻合；截止前最後組含兩個不同價格 | 同微秒排序未明；同一 serial 的 Quote 時間比對應 Trades/MIS 收盤早 3 分鐘 |
| 1235 | 終止頁 11 筆；最後截止組只有一筆，價格及時間吻合 MIS | 其他較早時點有同微秒多價格，不能因此推定截止價衝突；完整性來源契約仍未確認 |
| 5546 | 終止頁 87 筆，筆數/量吻合；截止前最後組價格唯一，Trades 存在 MIS 收盤成交 | 同一 serial 的 Quote 時間比對應 Trades/MIS 收盤早 3 分鐘；MIS 只有一次有效延後收盤證據 |

前三檔仍為公開研究候選；5546 只進私有待查核。LIVE source contract 未釋出，Worker LIVE release 保持 false。沒有把 UNKNOWN 改為 VERIFIED。

## 官方文件能確定的範圍

- Trades 提供 offset/limit 與時間升降冪；serial 僅標為流水號。文件未明示同微秒 tie-break、每檔連續性或一致性快照保證。
- Quote 將 lastTrade、lastTrial 分開；lastPrice 含試撮，closePrice/closeTime 的說明仍包含最後成交，不能單憑這些欄位證明正式收盤。
- 富果使用規範說明一般行情的成交值量不含零股/鉅額；但沒有在本次查閱頁面明示每個 Trades row 與 total.transaction 的一對一保證。
- TWSE 說明 13:25～13:30 是模擬試算，正常收盤與暫緩至 13:33 的實際收盤要分清楚。不能把試撮當成交，也不能把所有 Quote 13:30 自行改為 13:33。

## 可寄給富果技術客服的問題草稿（尚未傳送）

對象：官方文件所列 tech.support@fugle.tw。
主旨：確認股票 REST Trades 完整性、同微秒排序及暫緩收盤 Quote 時間語意。

1. EQUITY、未指定 oddlot、isTrial=false 的 Trades 是否提供當日完整一般交易成交？是否包含盤後定價成交？請界定精確交易範圍、資料產生延遲與停止更新時間。
2. offset/limit 分頁是否為一致快照？同一 serial 會重送或修正嗎？如何確認 terminal page 之後不會補進較早時間但當時未提供的成交？
3. sort=desc 的相同微秒資料是否保證依真實成交先後？若有，tie-break 欄位為何？serial 是否是全市場訊息序號、同商品交易序號、或另一種序號？請不要只回覆「流水號」。
4. total.transaction 是否精確等於此範圍的 Trades rows？size 總和是否等於 tradeVolume？row.volume 是否為該筆成交後的累計量？開收盤集合競價會不會拆成多 row 或合成一 row？是否可能更正、歸零、缺欄位？
5. 2026/10/16 的 6228、5546，保存回應中同一 serial 在 Quote.lastTrade.time/closeTime 與 Trades.time 差整整 3 分鐘，且 MIS 與 Trades 時間吻合。這是時間正規化、欄位定義、批次時間或已知錯誤？目前未將任一方的時間自動改寫。
6. isClose、isDelayedClose 的有效期間與撤回/更正語意為何？已暫緩收盤後 isDelayedClose=false 是否正常？如何證明有正式收盤成交，或當日沒有新收盤成交？
7. 這些原始回應能否在僅本人可讀的加密雲端保存 30 天供錯誤調查？對外僅發布 MIS 研究欄位及驗證狀態，是否仍需額外授權？需要何種書面許可？

可在獲使用者明確寄送授權後，以私有方式提供原始證據；目前沒有寄信、留言或傳送原始行情給任何新對象。

## 其他來源調查

| 來源 | 能補什麼 | 目前限制 |
| --- | --- | --- |
| TWSE/TPEx 官方盤後日資料 | 收盤價格與整日統計，沿用既有核對 | 不能證明 13:25 前最後成交；已有 1830 一致仍不等於 P_before 已驗證 |
| 富果 WebSocket Trades | 有實際成交與收盤/試撮旗標，適合下一交易日少量候選/控制驗證 | 尚未即時保存本日串流；事後不能補回。仍須確認排序、斷線補齊、免費訂閱限制 |
| FinMind TaiwanStockPriceTick | 官方文件列歷史逐筆資料 | 文件列為 Backer 方案，非目前可直接使用的免費替代；沒有加購、申請 Token 或呼叫 |
| TWSE Data E-Shop / TPEx 資訊商店 | 正式歷史成交/揭示資料申購 | 不符合免費且 13:35 即時條件；未購買 |
| 分鐘 K / 一般網頁報價 | 價格合理性比對 | 沒有完整逐筆與交易範圍保證，不能替代截止前最後實際成交證明 |

本次沒有找到可立即取代完整逐筆證明、同時免費且無需新授權的來源。不把「沒有找到」寫成所有免費來源都不存在。

## 查閱來源

- https://developer.fugle.tw/docs/data/http-api/intraday/trades/
- https://developer.fugle.tw/docs/data/http-api/intraday/quote/
- https://developer.fugle.tw/docs/data/websocket-api/market-data-channels/trades/
- https://developer.fugle.tw/docs/data/intro/
- https://investoredu.twse.com.tw/Pages/TWSE_InvestmentQA.aspx?ID=14
- https://github.com/FinMind/FinMind-MCP/blob/master/knowledge/datasets.md
- https://eshop.twse.com.tw/zh/
- https://www.tpex.org.tw/web/service/info_service/info_service.php?l=zh-tw
