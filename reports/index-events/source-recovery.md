# 官方來源恢復研究（2026-10-09）

承接45e2085fe83e793cecff0d9be5efb035e7ab78f8；不重新seed、不改MIS。以下均先用匿名標準HTTP及robots檢查，失敗不更換身分或繞過。具體時間、URL、HTTP結果見source-recovery-evidence.json；GitHub獨立source-smoke將再驗證部署環境。

|来源／原狀態|新測試網址|實測與分類|日期／股票能力|整合|
|---|---|---|---|---|
|TWSE ETF主檔／未使用|https://openapi.twse.com.tw/v1/opendata/t187ap47_L |200，271筆；VERIFIED_AUTOMATIC；政府資料集157399免費、政府資料開放授權第一版|基金類型、指數、上市日、出表日；非换股公告，无股票清單|是|
|元大／首頁MONITOR_ONLY|https://www.yuantaetfs.com/product/detail/0050/Basic_information |200；DATE_ONLY|明確生效日2026/9/21，新增1刪除1；無基金實際交易日及個股明細|是|
|元大0051|https://www.yuantaetfs.com/product/detail/0051/Basic_information |200；DATE_ONLY|9/21生效，新增4刪除4；非收盤實施證據|是|
|元大0056|https://www.yuantaetfs.com/product/detail/0056/Basic_information |200；DATE_ONLY|6/26生效，新增0刪除4；五日過渡另依規則預估|是|
|元大006203|https://www.yuantaetfs.com/product/detail/006203/Basic_information |200；DATE_ONLY|9/1生效，新增3刪除6；不是MSCI授權全名單|是|
|TIP公開新聞／只有對應表|https://taiwanindex.com.tw/news/452 、 /news/454 |200；VERIFIED_AUTOMATIC（僅既知公開頁）|明確指數收盤後實施句、官方公告17:13／17:00、9個指數與ETF；沒有個股清單|是，新增日期解析|
|TIP新聞列表／UNAVAILABLE|https://taiwanindex.com.tw/news |200但沒有可解析的公告列表連結；UNAVAILABLE|不可說今天沒有新公告|保留失敗狀態|
|TIP首頁／未使用|https://taiwanindex.com.tw/ |200但未取得可用news連結；UNAVAILABLE|不枚舉猜測新聞ID，不讀受限內部API|否|
|TIP技術／期程／robots拒絕|原downloads/technical_notice兩入口|逐次robots檢查；RESTRICTED時停止|人工已核對期程保存；沒有合法替代自動列表|維持原處理|
|FTSE完整通知／RESTRICTED|原Technical Releases登入入口|登入／訂閱及授權限制未解除；RESTRICTED|公開規則可監測，不能宣稱取得新名單|停用完整通知|
|MSCI成分／RESTRICTED|原index_review.html|授權再散布限制未解除；RESTRICTED|ir_dates.pdf可DATE_ONLY，自由流通與權重仍未知|維持日期追蹤|
|國泰／HTTP400|https://www.cathaysite.com.tw/ETF/detail/ECN |匿名HTTP逾時；UNAVAILABLE|搜尋頁可見不等於自動取得成功|否|
|富邦／robots拒絕|https://www.fubon.com/asset-management/ph/Taiwan50/intro.html |200但維修頁；UNAVAILABLE|不能把200當成功；006208指數改由授權TWSE主檔核對|未整合維修頁|
|群益／產品頁MONITOR_ONLY|https://www.capitalfund.com.tw/service/news |200且有公告連結；MONITOR_ONLY|未證明全量解析；不把募集、配息、追蹤差距誤判换股|保留監控，未宣稱事件解析|
|復華／MONITOR_ONLY|原ETF21官方頁|保持變動監控；MONITOR_ONLY|無可靠的實施日／受影響股完整Parser|維持|
|TPEx目錄／公司資料可用|https://www.tpex.org.tw/openapi/swagger.json |200；正式OpenAPI目錄未列ETF基本資料|當日指數成分是快照，不能據差集推定官方新增／刪除或尾盤實施|未新增錯誤事件來源|
|TPEx ETF篩選器／未使用|https://info.tpex.org.tw/ETF/zh/filter.html |HTTP200，但網站條款第五、七項要求同意才可自動下載；RESTRICTED|未找到此主檔的開放資料授權；不調用頁面內部POST API|否|

元大頁面只保存公開日期與檔數事實、來源連結；不重製授權指數股票清單。TWSE主檔使用政府資料開放授權，明確註明來源；不使用一般e添富網頁的內部API，其使用條款限制自動下載。TPEx同理。公開HTTP取得並不等於可再散布完整著作；此服務只保留必要事件事實，授權成分資料仍RESTRICTED。

## 正確的收盤含義

TIP公開新聞明確寫指數變動在9/16／10/2交易結束後生效，因此確認的是**指數收盤後實施日**；不代表知道ETF基金真的何時下單。9/16公告17:13，10/2公告17:00，均在收盤後；本站10/9才取得，所有历史關聯均保留first_seen_at，不能製造當天13:25已知的訊號。

未來12月FTSE與11月MSCI維持規則／交易日曆推估，沒有因本次加入歷史資料而提升證據等級。00878的客製指數不套MSCI全球審核期程。新聞網站沒有被用作確認來源。

第二階段最終核對：2026-10-09T16:57:01+08:00，正式CI37907579895與Pages37907698117 SUCCESS；源掃描49事件／64確認ETF對應／2衝突，來源11成功取得解析（6自動完整語義來源＋5日期）但PARTIAL。193 Python、39 Node、36瀏覽器場景PASS。完整證據見deployment.json及source-recovery-validation.json；待審10文件不是已確認事件。
