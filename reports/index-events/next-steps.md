# 承接入口與剩餘工作

本次分支improve/index-events-20261009。先讀acceptance.md、deployment.json、source-coverage-comparison.json、source-health.json及git status。不要seed；不要重抓歷史MIS；不要更動現有workflow憑證及市場規則。

已完成：合法TWSE基金主檔分類與每日發現、元大四個生效日頁、TIP公開已知新聞收盤實施／公告時間解析、多來源事件及對應衝突、健康分類與完整性統計、188＋3個新TIP測試，Node39。正式CI／來源／Pages結果以acceptance最後更新為準。

仍需合法來源：TIP新新聞的可解析列表或RSS、TIP新日程／技術通知的授權公開feed、FTSE完整通知與MSCI成分再散布許可、TPEx基金主檔開放資料、完整上市／下市狀態及正式發行公司欄位、其他發行商帶日期與受影響股票的公告格式。找不到就保留PARTIAL／UNKNOWN／RESTRICTED。

不可用猜測新聞ID、繞過robots、直接調用有自動下載限制的網站內部API達成表面完整。新來源必須先確認授權，再實測HTTP、語義Parser與來源錯誤回復；不能用ETF配息日充當換股。

沒有歷史MIS13:25資料不補造；歷史事件只屬於latest_as_of，不回填曾經的live_as_of。尚無統計優勢或價格修正結論。

2026-10-09 補測：再次掃描官方期程不降低已確認實施等級，且保留期程與實施兩個來源；Python總計192項、Node39項，本機PASS。GitHub完整瀏覽器及正式發布證據待本次CI完成後補入。
