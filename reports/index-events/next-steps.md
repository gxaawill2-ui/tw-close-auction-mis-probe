# 承接入口與剩餘工作

本次可靠來源恢復已正式發布並验收。先讀acceptance.md、deployment.json、source-recovery-validation.json、source-coverage-comparison.json、source-health.json及GitHub實際main。不要seed、不要重抓歷史MIS、不改市場規則、排程或Secrets。193 Python、39 Node（29 DOM／狀態）、36三瀏覽器場景PASS；正式執行SHA／run以deployment.json為準。

已整合：TWSE開放基金主檔分類、每次掃描新代號、元大四頁生效日、TIP兩已知公開新聞的歷史指數收盤實施及公告時間、多來源去重／衝突與更正歷史、反覆衝突不產生假更正、來源分類及完整性統計。66對應＝64確認＋2衝突；271主檔包括歷史基金，不是目前掛牌清單。每天08:20／17:20由GitHub Actions執行，已整合部分無需日常手動整理。

後續優先找合法來源：TIP可解析新聞列表／RSS及技術日程feed；TPEx開放授權ETF主檔；完整上市／下市狀態及經理公司正式名稱；其他發行商有明確日期、指數與正式股票清單的公告格式；00936／00939官方名稱對照證據。未找到就PARTIAL／UNKNOWN／RESTRICTED。

MSCI與FTSE成分再散布或完整通知未有免費合法替代；不能以猜測新聞ID、繞過robots、受限內部API或新聞報導充當官方確認。元大DATE_ONLY、MONITOR_ONLY、基金實際交易時間UNKNOWN須分開。

TWSE政府目錄標示每月更新；每天查詢不能承諾新上市當日即時發現。主檔缺漏不能判斷下市。newly_observed_etfs為首次觀察主檔代號，不等於新上市數；new_confirmed_etf_mappings為確認對應淨增。變動監測的雜湊更新不等於新換股公告；待審文件保留且不轉成無證據事件。

任何新Parser先實測HTTP／robots／授權、語義格式與錯誤回復，再跑完整測試及CI。沒有歷史MIS13:25證據不補造；晚取得的歷史事件只補latest_as_of，不能穿越回live_as_of。仍沒有足夠資料支持統計結果。
