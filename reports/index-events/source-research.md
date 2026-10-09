# 台股指數／ETF事件來源研究

研究基準：2026-10-09（Asia/Taipei）。期間：2026-10-09～2027-10-31。
日期是官方公開的期程事實；不是實際ETF下單紀錄。只讀公開入口，不使用付費成分資料、不登入、不繞過robots／401／403。首次掃描結果另見source-health及CI source-smoke artifact。

|來源|官方入口|用途與範圍|
|---|---|---|
|MSCI定審期程|https://www.msci.com/eqb/pressreleases/archive/ir_dates.pdf |公開公告／生效日期；有改期風險|
|MSCI定審結果|https://www.msci.com/eqb/gimi/stdindex/index_review.html |發現Standard／Small Cap結果入口；授權成分及權重資料不自動重製|
|TIP期程|https://taiwanindex.com.tw/downloads/technical_notice?category_id=3&page=1 |最近10份公開PDF，逐指數保存官方公告、生效日|
|TIP技術通知|https://taiwanindex.com.tw/downloads/technical_notice?page=1 |最近10份公開通知；只接受明確收盤實施句型，其他送待審佇列|
|FTSE完整通知|https://research.ftserussell.com/Products/index-notices/loggedOut/index/?id=TWSE-TAIWAN |官方入口要求註冊／訂閱，停用；TIP摘要不是完整英文通知的替代|
|FTSE臺灣系列規則|https://www.lseg.com/content/dam/ftse-russell/en_us/documents/ground-rules/ftse-twse-taiwan-index-series-ground-rules.pdf |v5.2，2026/8，6.1第三個星期五收盤後實施；僅據規則推估12/18|
|FTSE高股息規則|https://www.twse.com.tw/downloads/en/products/indices/IndexSen20.pdf |v4.1，2026/3；4.6連續五個交易日過渡，非0056單日集中換股證據|
|TWSE交易日曆|https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?response=json&queryYear=115 |2026年；116年版本成功確認前不推算2027收盤日|
|TWSE／TPEx公司資料|https://openapi.twse.com.tw/v1/opendata/t187ap03_L 、 https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O |代號、公司簡稱、市場身分；不抓MIS價格或量能|
|TIP ETF對應表|https://taiwanindex.com.tw/news/452 、 https://taiwanindex.com.tw/news/454 |官方指數／ETF表格；另掃最新news可發現的公開表格|

## 已核對日期

MSCI的公開期程為：

|審核|公告日（來源日期）|生效日|台灣收盤日|
|---|---|---|---|
|2026/11|2026-11-11|2026-12-01|2026-11-30：EXPECTED_CLOSE_WATCH_DATE|
|2027/2|2027-02-09|2027-03-01|未取得2027交易日曆時留null|
|2027/5|2027-05-10|2027-05-28|未取得2027交易日曆時留null|
|2027/8|2027-08-12|2027-09-01|未取得2027交易日曆時留null|

11/11是MSCI期程表的來源日期，不自行換算為台北公告時刻；announcement_time=null，頁面提示台北時間待確認。11/30是依生效日與已保存官方2026交易日曆推算，期程PDF本身没有確認收盤實施日。未把00878的客製指數套到Global Standard／Small Cap。

TIP 10月表：https://backend.taiwanindex.com.tw/api/downloadFile/TechnicalNotices/1311/tw

TIP 11月表：https://backend.taiwanindex.com.tw/api/downloadFile/TechnicalNotices/1325/tw

两表共25個指數期程：10/19→10/20、11/3→11/4、11/17→11/18、12/1→12/2、12/3→12/4。表頭明确是「公告日期（收盤後）」及「生效日期」。不把公告日誤稱交易實施日；closing_impact_date=null。官方註記有非預期休市時順延，只有足夠官方日曆／更正資訊才更新日期。

FTSE臺灣50與中型100：12/18收盤、12/21生效為官方規則衍生的EXPECTED，非12月名單已公布。0056高股息過渡預估12/21、22、23、24、28；12/25為休市。基金實際下單時點未知。

## ETF對應與維護

初始14筆官方對應包含0050、006208、0051、0056、00878、00904、00919、00929、00934、009802、00923、00930、00936、00939。逐筆官方連結及首次得知時間見etf-index-mapping.csv。不能宣稱涵蓋所有新上市ETF；TIP公開news表格能解析的新增產品自動加入，未確認產品留UNKNOWN。主動ETF為ACTIVE／NOT_APPLICABLE，不套換股假設。

0050： https://www.yuantaetfs.com/product/detail/0050/Basic_information

0056： https://www.yuantaetfs.com/product/detail/0056/Basic_information

006208： https://websys.fsit.com.tw/FubonETF/Fund/IndexIntro.aspx?stkId=006208

00878： https://www.cathaysite.com.tw/ETF/index-trend?keyword=00878

00919／00929官方關係見TIP news/452；獨立發行商亦可核對 https://www.capitalfund.com.tw/etf/product/detail/195 、 https://www.fhtrust.com.tw/ETF/etf_detail/ETF21 。發行商頁面目前僅變更監控，不會將除息公告或配息日期誤解析成換股日期。

## as-of與研究

所有日期記錄first_seen_at、information_available_as_of、last_checked_at、updated_at。來源原始公告時間與本站首次取得時間分開。更正保留previous_version與observed_at，可還原舊資訊版本。10/8候選的live_as_of採原generated_at；事件10/9才由本站取得，不回填假裝10/8已知。

研究sidecar位於state/events/candidate-annotations/YYYY-MM-DD.json。它不改state/candidates、不改变選股門檻、不宣稱因果、無買賣方向。受影響名單必须有官方代號、市場及身分确认才关联。公司簡稱不符或市場不明時留UNKNOWN；未公布權重留null。

## 已執行的來源驗收

GitHub source-smoke run 37876233638（2026-10-09 10:49台北），正常公開HTTP與robots檢查：MSCI期程8筆解析成功，2026交易日曆、TWSE／TPEx公司資料及TIP news/452、news/454對應表成功；FTSE公開規則及元大／群益／復華頁面為變更監控。

TIP `/downloads/technical_notice` 的robots禁止自動讀取，沒有下載該入口；只保留先前人工核對的25筆期程。富邦ETF指定頁亦robots禁止；國泰指定入口HTTP400；TIP動態news列表未取得可解析的新增對應表。這些來源沒有被說成自動成功。2027交易日曆回應未公布。完整結果見source-smoke-health.json。


## 2026-10-09來源補強

完整新比較與實測證據見source-recovery.md及source-recovery-evidence.json。新增政府開放授權TWSE ETF主檔，實測271筆；66筆普通台股被動基金符合研究範圍。首次整合時64筆指數對應確認，00936、00939在來源間名稱不同，保留2筆CONFLICT，不自行猜作別名。271是含歷史紀錄的主檔數，不是目前上市數。

元大0050、0051、0056、006203的官方產品頁明確生效日期可自動解析為DATE_ONLY，未提供實際下單日與股票清單。TIP公開news/452、454可解析9個歷史指數的明確收盤後實施日及公告時刻，不替代新的完整技術通知列表。9/16公告17:13、10/2公告17:00均盤後，本站10/9才得知，不回填事前訊號。

TWSE e添富及TPEx一般ETF篩選頁使用條款限制自動下載；未找到允許ETF主檔的TPEx開放資料，因此不調用內部API。富邦替代網址200但維修頁、國泰替代入口逾時、TIP首頁與news列表未取得可用新公告連結，均不是成功。MSCI完整成分、FTSE完整通知仍受限。

全部更新仍由08:20／17:20獨立Actions執行。source-health新增A至E實際能力分類、最近失敗、解析新增／更正、衝突、待審文件、新ETF及未知對應；來源未抓到與已抓到但沒有新解析事件分開。保留PARTIAL。
