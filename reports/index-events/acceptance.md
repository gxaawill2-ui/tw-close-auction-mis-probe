# 事件日曆驗收與恢復入口

基線main：491b7b07f6a0b355e627e0f1b7f4e949acb10eee。

完成：官方來源研究、32筆初始事件、14筆ETF對應、獨立掃描、公開JSON、首頁兩區塊、股票addendum、as-of歷史、來源健康、變更待審佇列、測試。

本機Python：160 PASS。Node：37 PASS（含27個首頁／事件DOM與狀態測試）。瀏覽器下載在本機受環境限制，改由GitHub CI安裝官方Chromium／WebKit執行。

嚴格保留：10/8候選JSON、P_before／P_close、量能程式、原MIS workflow、官方核對workflow均與基線逐位元一致。未重抓任何10/8MIS。首頁只增事件區與讀取，原價格、量、排序及validated=false不變。

來源掃描：驗收分支push僅測試與隔離checkout source-smoke，不發布資料、不dispatch MIS。main首次程式部署及schedule／workflow_dispatch會更新state/events與CSV；不修改候選或其他交易日市場證據。事件掃描concurrency独立于MIS；來源失敗不阻塞13:35。

部署步驟：先將驗收分支提交GitHub→CI全PASS→main快進→CI與Pages→匿名公開頁面檢查。最終run／SHA／部署證據寫入deployment.json。

恢復：先讀本檔、deployment.json（若有）、source-health.json和git status；不要重新seed、不重抓MIS、不重建Repo、不改排程憑證。若source-smoke失敗只修事件讀取，不碰市場規則。

驗收分支7c785f520e33fd5f66e47ddc84226926c7208947：MIS tests CI 37876374002 SUCCESS（159 Python、37 Node、36 Chromium桌機／手機／WebKit場景）；独立Index event calendar CI 37876374052 SUCCESS。源驗收明細見source-smoke-health.json。

## 正式驗收結果（2026-10-09）

正式網址：https://gxaawill2-ui.github.io/tw-close-auction-mis-probe/

事件程式最終版本：382439f5a82870197cc41eee76587e6fb544d61d。

最終獨立分支 CI 37877015574 SUCCESS；main CI 37877204478 的 tests 與 public-acceptance SUCCESS。Python 160 PASS、Node 37 PASS，其中首頁／事件 DOM 與狀態測試27項。Chromium桌機、Chromium手機、WebKit iPhone共36個場景PASS，包含匿名正式網址、來源503時仍顯示七檔fixture、預估11/30、12/1生效與收盤實施分離、深色不依賴系統外觀、無按鈕及无橫向溢出。Pages 37877204392 SUCCESS。

最後新增的回測測試：掃描13:34開始、13:36才取得的事件，不可出現在13:35的live_as_of；只可出現在取得後的latest_as_of。新來源觀察以整次取得／處理完成時間記錄，採保守的資訊可用時點。

|要求|證據與結果|
|---|---|
|1–4 公告、生效、收盤、休市|MSCI11/11公告與12/1生效分欄；11/30只為EXPECTED；官方日曆及跨年測試PASS|
|5 ETF多日過渡|0056五交易日測試PASS，跳過12/25|
|6 推估不冒充確認|Python、DOM及三瀏覽器預估標示PASS|
|7–8 一指數多ETF與重複事件|去重ID、對應及ACTIVE排除測試PASS|
|9 更正與歷史|previous_version、as-of還原及冪等測試PASS|
|10 失效／timeout|保留舊事件及UNKNOWN／STALE；503瀏覽器隔離PASS|
|11 跨年|未取得2027官方日曆時不推算收盤日，PASS|
|12–13 股票市場／無名單|精確代號＋官方市場身分匹配；缺名單不標納入／刪除，PASS|
|14 未取得不是無事件|PARTIAL及來源錯誤首頁文案測試PASS|
|15 10/8七檔不變|JSON SHA256為794cdb1749a7318612fad5003bceb47b126b5d03a8cbda16abf14332954c111b，与基線完全相同|
|16–18 固定深色／版型／無按鈕|桌機、手機、WebKit iPhone皆PASS|
|19 公開JSON更新|main scanner只發布state/events及CSV；已由bot提交且公開JSON可讀|
|20–21 排程隔離與push不抓MIS|原全部MIS workflow未改；事件workflow沒有dispatch；push只跑原tests，PASS|
|22 首次知道時間|盤後首次得知與掃描跨13:35測試PASS；10/8 live_as_of不回填10/9新知|

公開HTTP再次核對：首頁有events.js、今日區及日曆區，沒有button；10/8候選原檔hash不變。實際10/9為休市，首頁依原交易日邏輯顯示休市，不冒充今天有10/8七檔。

範圍內32筆事件＝29筆官方公告／生效期程＋3筆FTSE規則推估；官方確認的未來收盤實施事件為0。完整資料庫36筆，另外4筆MSCI期程超出所要求範圍。對應表14筆。來源完整性維持PARTIAL。這次沒有足夠資料支持任何隔日修正統計結論。

可用来源與未完成來源分別記錄於source-research.md、limitations.md及公開source-health.json。未把robots禁止、授權限制、HTTP400或未解析結果當成自動追蹤成功。完整部署執行ID與資料提交記錄見deployment.json。
