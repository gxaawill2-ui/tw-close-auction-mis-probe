# 四檔成交驗證與富果詢問草稿

本輪只從已完成30日封存的私有證據恢復分析；沒有新增MIS或富果行情查詢。真正取得時間仍是10/16 13:37～13:58，19:22為重新分析，不能回填為13:35驗證。

| 股票 | 保存資料檢查 | 截止價與收盤的未決事項 | 正式結論 |
| --- | --- | --- | --- |
| 4609 | 終止頁5筆，筆數、size總和、累計量鏈、Quote/Trades/MIS吻合 | 截止前最後組1筆，價格唯一；仍缺來源完整區間/統計範圍契約 | RESEARCH_ONLY；非VERIFIED |
| 6228 | 終止頁5筆，筆數/量吻合 | 截止前最後同微秒組2個價格；同serial收盤時間相差180秒 | UNKNOWN |
| 1235 | 終止頁11筆，筆數/量/量鏈吻合 | 最後截止組1筆、與MIS相同；較早同微秒多價格不決定截止價，仍缺完整性契約 | 公開研究候選；非VERIFIED |
| 5546 | 終止頁87筆，筆數/量/量鏈吻合 | 截止組價格唯一；同serial時間差180秒，MIS缺第二次有效延後收盤確認 | 私有待查核UNKNOWN |

現有公開初篩三檔都保留；依逐檔驗證狀態為研究2、UNKNOWN1、VERIFIED0。5546不混入這三檔。涵蓋1938/1967=98.53%，29檔仍不能完整初篩，不能宣稱無漏選。

## 三分鐘差：已證明什麼

6228、5546保存回應的 `Quote.lastTrade.time`、`closeTime`、`lastUpdated`、`total.time` 全為13:30；對應相同serial的 `Trades.time` 為13:33，MIS亦為13:33。Quote前後括取穩定，當時HTTP回應為成功；保存的Age欄位缺失。這能證明跨端點矛盾，**不能證明快取已排除，也不能直接認定某端點有bug**。不加減180秒、不用最大serial、不用累計量自行裁決同時不同價。

Quote的isClose=true；isTrial/isDelayedClose在這些回應中沒有提供，不等於回傳false。原舊audit的NORMAL_CLOSE是只按Quote欄位分類的中間診斷，不能用來越過同serial矛盾；stage7 review已將矛盾時的收盤分類改為UNCONFIRMED_CONFLICTING_CLOSE_TIME。

官方文件將lastTrade.time定義為最後成交時間、closeTime為收盤價（最後成交價）時間、total.time為統計時間、lastUpdated為最後更新時間。Trades的sort為時間升/降序，serial只標示流水號；未見同微秒tie-break、逐檔連續性、分頁一致快照或完整資料最終性保證。筆數及量吻合是很強的實證核對，仍不足以自行創造這些契約。

P_close的官方日收盤價比對可支持三檔價格一致；它不能證明P_before。四檔的完整P_before/P_close獨立證明均未通過，LIVE_CONTRACT與Worker放行旗標保持關閉。

## 聯絡草稿（尚未寄出）

收件對象：官方文件列出的 tech.support@fugle.tw。主旨：股票REST Trades完整性、同微秒排序與延後收盤時間契約確認。

您好，我們使用股票REST /intraday/quote/{symbol}、/intraday/trades/{symbol}，交易範圍為一般整股、EQUITY，Trades使用isTrial=false、sort=desc、offset/limit。用途為本人研究13:25前最後實際成交及正式收盤；不會以試撮、昨收或零股替代。

1. Trades的time、Quote.lastTrade.time/closeTime/lastUpdated/total.time是否使用相同事件時間定義？10/16 6228及5546，同一serial在Quote四個時間欄位為13:30、Trades及MIS為13:33。請說明是否為暫緩收盤正規化、不同處理階段或已知問題；何者能用來判定成交先後？
2. sort=desc相同微秒的多筆不同價是否有保證的次序？serial屬全市場訊息序號、單商品成交序號或其他？是否會修正/重送/重置？不能僅依「流水號」推定最大值為最後成交。
3. offset/limit是否使用一致快照？更新中分頁如何防止漏筆/重複？終止頁之後是否可能補進更早時間成交？何種條件能證明13:25前完整區間已最終化？
4. 請精確界定total.transaction、tradeVolume、Trades.size/volume的關係：是否為逐row一對一、是否包含開收盤集合競價、拆合筆、修正、零股或盤後定價？當所有筆數和量都吻合時，還需要哪些條件才能認定沒有漏掉最後成交？
5. isClose/isDelayedClose/isTrial欄位缺失時應如何解讀？延後收盤完成後isDelayedClose是否會消失？如何證明正式收盤已完成或沒有新收盤成交？
6. Quote前後相同但HTTP Age缺失時，如何區別舊快取與來源最終快照？是否有更新版本或完整性水位可核對？
7. 本人研究證據能否在現有僅本人可讀雲端保留30日、到期自動清除？只發布MIS研究欄位與驗證狀態是否需額外授權？請提供適用條款及限制。

最小示意（欄位關係，非完整原始回應；不含Key、價格、流水號值或使用者交易）：

```json
{"quote":{"lastTrade":{"serial":"<same-redacted-serial>","time":"13:30:00"},"closeTime":"13:30:00","lastUpdated":"13:30:00","total":{"time":"13:30:00"}},"trades":{"serial":"<same-redacted-serial>","time":"13:33:00"},"mis_trade_time":"13:33:00"}
```

原始回應已做私有SHA256保存，可在取得本人另行寄送授權後，按官方安全方式提供必要細節。目前未寄信、開issue或對新對象傳送資料。

## 免費替代來源的實際能力

| 來源 | 能支持的證據 | 缺口 |
| --- | --- | --- |
| TWSE/TPEx官方盤後日資料 | 收盤價、當日統計；沿用已有1830一致/0不一致/137無可比資料 | 不提供13:25前完整逐筆 |
| 既有官方MIS | 已保存的成交/比較/收盤觀察；定向C2可補第二次觀察 | 同一來源不能自行充當富果的獨立完整逐筆契約 |
| 富果WebSocket Trades | 下一交易日少數股票即時成交/試撮/收盤訊號的研究選項 | 同一供應商，不能修復10/16過去串流；仍須確認排序、斷線補齊及免費限制 |
| FinMind官方TaiwanStockPriceTick文件 | 歷史逐筆資料 | 官方文件列backer/sponsor，不能當作已可免費使用的替代 |
| 官方資訊商店 | 可申購正式成交資料 | 不符合免費及13:35即時目標；沒有購買 |
| 分鐘K、一般網站報價 | 合理性比對 | 無法證明截止前最後實際成交 |

沒有找到可立即合法免費補齊完整逐筆證明的替代，不等於斷言所有免費來源不存在。

查閱：
- https://developer.fugle.tw/docs/data/http-api/intraday/quote/
- https://developer.fugle.tw/docs/data/http-api/intraday/trades/
- https://developer.fugle.tw/docs/data/intro/
- https://developer.fugle.tw/docs/data/websocket-api/market-data-channels/trades/
- https://github.com/FinMind/FinMind-MCP/blob/master/knowledge/datasets.md

第七階段再次核對FinMind官方技術文件：https://finmind.github.io/tutor/TaiwanMarket/Technical/ 。逐筆仍列backer/sponsor限制，未註冊或付費。
