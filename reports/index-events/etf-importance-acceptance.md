# ETF重要程度正式驗收

更新2026-10-10T00:23:50.384Z；程式b6246cff62a37801d5c2c3a10115e6d77496b397。資料19筆fund×index event×週期，15檔基金：高1、中2、低0、資料不足16。資料庫仍49事件、66對應（64確認、2衝突）；未以新評級刪除既有事件。

|觀察期間|ETF|重要程度|日期證據|官方AUM與估值日|
|---|---|---|---|---|
|2026/12/18|0050|高，PROVISIONAL|EXPECTED_CLOSE_WATCH_DATE（指數）|2,551,521,434,557 TWD；10/8|
|2026/12/18|0051|中，PROVISIONAL|EXPECTED_CLOSE_WATCH_DATE（指數）|3,823,531,781 TWD；10/8|
|2026/12/18|006208|資料不足|EXPECTED_CLOSE_WATCH_DATE（指數）|未取得可靠AUM，不填0|
|2026/12/21,22,23,24,28|0056|中，PROVISIONAL|EXPECTED_MULTIDAY_TRANSITION（指數）|829,080,886,073 TWD；10/8|

AUM來源：https://www.yuantaetfs.com/tradeInfo/pcf/0050 、/0051、/0056；匿名HTTP200且robots允許；取同頁NAV資料日，PCF下一交易日10/12不誤作規模日期。只保存淨資產事實，不重發完整holdings。其他官方清單／權重缺失保留null。

242 Python PASS（含新增49）：高／中／低、資料不足、同日不同ETF、同ETF不同季度、主動式／衝突排除、過期規模、日期／重要性分離、官方股票市場匹配、歷史更正／as-of、refresh實際時鐘、無效prototype lineage排除。Node42 PASS，其中DOM／狀態32。

完整分支browser38007381758 SUCCESS，三引擎42場景PASS；main38007718767的public-acceptance SUCCESS。完整頁驗證全部19項、固定深色（系統light仍dark）、無button或表單控制、手機無水平溢出。長清單WebKit全頁截圖曾超過32767px，改取viewport截圖；保留全19筆DOM與版型斷言，沒有刪除中／低項。公開fund-events.html及首頁來源失效fixture皆可用；新模型不變更原選股條件。

正式資料first_rated_at／information_available_as_of最早2026-10-10T07:50:47.811603+08:00，修正詳methodology。舊錯誤prototype時間保留但標invalid，不作事前回測。MIS10/8候選SHA256=794cdb1749a7318612fad5003bceb47b126b5d03a8cbda16abf14332954c111b不變；P_before/P_close/return/全部量能及validated=false未改。
