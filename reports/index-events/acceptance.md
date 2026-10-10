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


## 第二階段正式驗收（2026-10-09T16:57:01+08:00）

本次承接45e2085；程式94cb366cd32af8ce9b0dd70eef498ab01ff7b6d1，正式資料d5ba3b1c0ca40c365a9ca240d632a28f0c6f6d06。正式main CI 37907579895 SUCCESS；193 Python、39 Node（29 DOM／狀態）、36 Chromium桌機／手機／WebKit iPhone場景PASS。Pages程式37907579165及資料37907698117 SUCCESS。完整執行URL：https://github.com/gxaawill2-ui/tw-close-auction-mis-probe/actions/runs/37907579895 。

|驗收範圍|結果與證據|
|---|---|
|官方API、400／403、robots、timeout、PDF改版|實際TWSE主檔／元大／TIP匿名HTTP加獨立GitHub掃描；錯誤回復與拒絕繞過測試PASS；source-recovery-evidence.json及source-recovery-validation.json|
|新被動、主動、境外、槓反、未知類型、下市／缺漏、更名|官方基金類型分類；缺漏不猜下市、明確下市日期才生效；193 Python內各情境PASS|
|公告／生效／收盤／多日過渡|四元大頁只DATE_ONLY；TIP兩篇9指數明確歷史收盤後實施；未來MSCI／FTSE維持預估，0056五日過渡跳12/25|
|重複公告、更正、衝突|精確指數身分、跨來源source_evidence及previous_version；不同官方日期CONFLICT；相同兩來源反覆掃描不製造更正；39 Node內衝突排除與多日標籤PASS|
|股票與市場、未公布清單、as-of|未取得正式股票清單不產生納入／刪除；首次取得與官方公告分開；10/8 live_as_of仍無10/9新知；掃描完成時間才可用|
|失敗保留與未取得≠沒有公告|PARTIAL；FETCH_FAILED_NOT_NO_ANNOUNCEMENTS／UNKNOWN；舊事件、主檔及來源證據保留；503瀏覽器仍顯示七檔fixture|
|原始MIS／七檔／成交量|23個保護檔案含全部9個原MIS workflow逐位元一致；10/8候選SHA256=794cdb1749a7318612fad5003bceb47b126b5d03a8cbda16abf14332954c111b，匿名公開JSON再次一致；regression-preservation.json|
|深色、無按鈕、手機／桌機、公開事件|三瀏覽器全PASS；公開HTML／新版JS HTTP200且內容相符；今天10/9休市，按原邏輯顯示休市，不借用昨天名單|
|事件與MIS隔離|事件排程仍UTC20 0,9 * * *，台北08:20／17:20；沒有MIS dispatch、沒有市場抓取；push只既有tests；來源失敗不拖慢MIS發布|

初次正式掃描新增13筆歷史事實，庫36→49；指定期間仍32＝29官方期程＋3規則推估，未來確認收盤實施仍0。9筆確認為歷史指數收盤後實施（9/16、10/2），不是ETF實際下單時點。其他4筆為元大歷史指數生效日。

23來源：VERIFIED_AUTOMATIC 6、DATE_ONLY 5、MONITOR_ONLY 4、RESTRICTED 5、UNAVAILABLE 3；原本6個成功取得／解析來源→11個，其中5個只日期。ETF對應14→66（64確認、2衝突），271主檔紀錄不是271檔目前掛牌ETF。最新重複掃描2026-10-09T16:52:46+08:00：0新事件、0更正、0新主檔紀錄、64確認與2衝突不變，請求32次／上限60。待審文件10；變動監測不等於新公告。

公開JSON維持既有GitHub raw免費只讀資料路徑；Pages首頁直接讀取。Pages /state 不是既有資料服務，不將其404宣稱成功。來源／完整性證據、公開HTTP與JSON雜湊見public-verification.json、source-coverage-comparison.json及deployment.json。

首次GitHub MIS tests因假PDF在magic檢查前import可選套件而失敗，已僅調整事件解析器檢查順序；修正後CI全PASS，未更動MIS workflow。正式觀察日與成分仍不得猜測，沒有宣稱回測收益或隔日修正規律。

## 第三階段正式驗收（2026-10-10T00:23:50.384Z）

承接5fc6341ef1e2c8195b586df014aec290a41cb0a9。最終程式b6246cff62a37801d5c2c3a10115e6d77496b397，資料b061e45125e3bdbc5f72a42eb8e3fd595327542a，出版ack dfd003f4285fa8c609aff7f8f9b766a097643dd1。原始MIS工作及候選完全不變，沒有重抓10/8。

|驗收項目|結果／實際證據|
|---|---|
|全部Python|242 PASS；main38007718767 tests；49新增測試|
|Node／DOM|42 PASS；其中DOM／狀態32|
|完整三瀏覽器|42場景PASS：Chromium桌機／手機、WebKit iPhone；feature38007381758|
|正式網址三瀏覽器|main38007718767 public-acceptance SUCCESS；深色／無按鈕／原名單／事件／完整ETF頁|
|GitHub CI|main38007718767 SUCCESS；MIS tests38007718825 SUCCESS，只測試不抓市場|
|GitHub Pages|程式38007718622 SUCCESS；資料及收據38007864341 SUCCESS|
|HTTP備援協定|真實driver38007381758→child38007391304 SUCCESS；CI短期token、no-source/no-main-write self_test|
|收據與CAS出版|ADHOC_PUBLISHED，08:08:14 run建立、08:08:35 runner、08:08:44 scan、08:10:08完成、08:10:10出版ack；不冒充native準時|
|外部cron-job.org|NOT_ACTIVATED_AUTH_REQUIRED；登入牆、新repo-scoped Actions憑證需要一次使用者授權；範本不是已部署備援|
|原native事故|10/9 08:20時workflow未建立；17:20準時證據未取得；00:13 run原定slot UNKNOWN，具體根因未證實|
|ETF重要程度|19筆／15ETF，高1、中2、低0、資料不足16；PROVISIONAL、模型政策非爆量預測|
|評級as-of|已修復旧snapshot時間錯用；19筆first有效評級>=07:50:47.811603；舊版本invalid_for_asof_backtest仍保存|
|來源限制|27來源：自動10、日期5、監測3、受限6、不可得3；15成功，PARTIAL；FTSE條款禁bots已停止該來源自動化|
|TPEx|官方free quotes118代號候選as-of10/8；非完整ETF主檔／目前掛牌證據；JSON截斷有界重試保留舊資料|
|真正基金換股|沒有新增可靠未来實際ETF下單時間；指數close／ETF執行明確分開，推估仍推估|
|原10/8七檔|SHA256=794cdb1749a7318612fad5003bceb47b126b5d03a8cbda16abf14332954c111b；所有價格／量／validated=false及MIS workflow不變|

正式fund-events.html完整唯讀；首頁只加每基金重要程度與資料不足／預估標籤。來源失敗不清空事件或阻塞MIS13:35。10/10休市沿用原休市邏輯，不假裝當日有10/8七檔。公開JSON沿用GitHub raw免費路徑，不將Pages /state404當成功。

現在可發布的改善已完成；未授權外部備援與尚未抵達的native實測不寫PASS。詳細事故、備援、模型、来源限制及接續工作分別見本階段報告。沒有任何回測收益／隔日修正結論。
