# 事件日曆驗收與恢復入口

基線main：491b7b07f6a0b355e627e0f1b7f4e949acb10eee。

完成：官方來源研究、32筆初始事件、14筆ETF對應、獨立掃描、公開JSON、首頁兩區塊、股票addendum、as-of歷史、來源健康、變更待審佇列、測試。

本機Python：159 PASS。Node：37 PASS（含27個首頁／事件DOM與狀態測試）。瀏覽器下載在本機受環境限制，改由GitHub CI安裝官方Chromium／WebKit執行。

嚴格保留：10/8候選JSON、P_before／P_close、量能程式、原MIS workflow、官方核對workflow均與基線逐位元一致。未重抓任何10/8MIS。首頁只增事件區與讀取，原價格、量、排序及validated=false不變。

來源掃描：GitHub push僅測試與隔離checkout source-smoke，不發布資料、不dispatch MIS。schedule／workflow_dispatch main才更新state/events與CSV；不修改候選或其他交易日市場證據。事件掃描concurrency独立于MIS；來源失敗不阻塞13:35。

部署步驟：先將驗收分支提交GitHub→CI全PASS→main快進→CI與Pages→匿名公開頁面檢查。最終run／SHA／部署證據寫入deployment.json。

恢復：先讀本檔、deployment.json（若有）、source-health.json和git status；不要重新seed、不重抓MIS、不重建Repo、不改排程憑證。若source-smoke失敗只修事件讀取，不碰市場規則。
