# 富果資料語意待確認事項（未對外傳送）

用途：補足source contract驗收依據；不是新增付費、申請新Key或公開原始行情的授權。

1. Intraday Trades在isTrial=false、未帶oddlot時，是否完整且只涵蓋一般交易實際成交？盤後定價交易是否也會出現？
2. time的微秒代表成交、交易所訊息或供應者時間？同一time有多筆不同price時，sort如何打破相同時間排序？serial是否可用且保證先後？
3. serial的範圍是全市場、每檔或每個session？是否存在特殊值或非實際成交列？
4. 終止頁及穩定quote前後包夾，是否足以證明offset分頁沒有漏掉較晚但13:25前的成交？是否有固定快照或cursor機制？
5. Trades列數與Quote.total.transaction是否嚴格對應？size合計與total.tradeVolume的單位、交易類型範圍與重設規則？volume是否一般交易逐筆累計？
6. isClose、isDelayedClose、closeTime、lastTrade在正常13:30、延後13:33及無新收盤成交三種情境，各有何最終性保證？
7. 同時點quote.lastTrade與Trades排序第一列不一致時，應採何種一致性等待條件？
8. 研究判定狀態是否可對外發布？若含富果衍生價格/成交量，需何種公開使用授權？目前僅公開MIS研究欄位，富果原始資料私有。

官方文件覆核日期2026/10/16：
https://developer.fugle.tw/docs/data/http-api/intraday/trades/
https://developer.fugle.tw/docs/data/http-api/intraday/quote/

未寄信、未附原始資料、未聯絡第三方。即使取得一般性答覆，也要用已私有保存的真實證據重驗，再考慮釋出語意設定。
