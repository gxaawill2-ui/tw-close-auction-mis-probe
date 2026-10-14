# 第三階段：獨立逐筆證據＋低延遲發布

2026-10-14；分支 `stage3/20261014-independent-ticks-publication`，基線為修復分支 `07079029fea4bef8f0bc9b60fb2c006a32d712a9`。正式main開始時為`b1fbc88`，正常正式排程可能繼續更新state；本工作沒有更新main、正式Pages、正式workflow、cron-job.org、Secrets或歷史raw。

## A～E 結論

| 問題 | 本次結論 |
|---|---|
| A. 能否獨立確認13:25前最後成交？ | **真實行情尚不能**。完整tick檢查、候選查核介面和完整性／價格反例測試已實作，但沒有富果API Key；其列數對交易筆數、size加總對常規量及序號語意也尚未實證。合成證據可成功通過，不能當作真實行情證明。 |
| B. 能否13:35～13:40真正發布完整VERIFIED？ | **尚未達成**。歷史研究證據13:32:35開始、13:34:14六檔到齊；0檔正式VERIFIED。本機Worker→瀏覽器刷新成功；公開GitHub分支檔案的一次性匿名讀取另列實測結果，不能當作真實交易日或Cloudflare部署成功。 |
| C. 真正瓶頸？ | 富果合法候選查核授權／Key、實際完整性契約驗證、下一交易日實證，以及將消費journal與公開writer放在原收集器同一runner但獨立輸出的安全整合。現在尚沒有新的公開Cloudflare測試帳號服務。 |
| D. 能否免費及不換正式網址？ | **架構可行，但不是已部署承諾**。保留GitHub Pages介面，未來經授權後讀獨立Worker公開JSON即可；不用DNS或更換正式網址。Workers/SQLite Durable Objects有免費額度，須控制讀取量與確認行情使用範圍。 |
| E. 下一交易日需要什麼？ | 既有journal影子讀取、不重跑全市場；少量候選取得真實quote/ticks；核對時間／序號／trial／count／volume語意；實際發布與外部手機讀取；再與晚到官方日資料稽核。不能只測模擬或等15:20才認定及時成功。 |

**目前不符合正式部署條件。** 本次是隔離開發及驗收交付，未達成實盤完整驗證目標，沒有把研究結果升級成交易訊號。

## 新增模組與證據標準

- `stage3_ticks.py`：讀raw bytes／SHA256、同日股票市場範圍、微秒時間、來源receipt、快取Age、分頁offset/limit/末頁、排除trial、quote前後版本一致、最新tick與quote一致、逐筆筆數及成交量檢查、13:25前最後tick、MIS價格與量矛盾、正常／延後／無新收盤成交分類。
- `stage3_provider.py`：只查候選的 quote→完整降冪分頁→quote。每批raw先fsync、唯一檔名、原始觀察時間；共用最多50請求、每次至少1.1秒、每檔最多12頁（500列／頁），接近deadline拒絕新請求；401/403/429停止。沒有Key不請求；沒有查看其他服務Secret。
- `stage3_selection.py`：逐檔重算 ±3% Decimal、既有必要MIS成交量及獨立來源價格證據；外部validated旗標不採信。區分LIVE／OFFLINE_REPLAY／SYNTHETIC。缺證据維持RESEARCH_ONLY，矛盾為UNKNOWN；合成通過只記`simulation_passed`，不正式verified。
- `stage3_run.py`：未排程的journal讀取器，不抓MIS。候選來源及發布各自單worker；最多3次候選重試及5/10/15秒backoff。結構性缺證據才重試，不為未確認來源契約不停重抓。沒有production呼叫、沒有自動部署。
- `stage3_publication.py`：HMAC決策簽章、私有writer token、outbox、最多3次bounded retry、內容SHA與version回執核對。背景publisher讓slow publication不阻塞擷取，待傳版本可合併為最新，不以舊版本覆蓋新結果。
- `isolated_publication/worker.mjs`：獨立Worker＋單一SQLite Durable Object。公開匿名GET、簽章及token保護POST、10交易日期快照、原子version比較、相同版本冪等、409拒絕舊版／衝突、no-store、CORS、公開寫入receipt。`public_written_at`在payload transaction成功後取得；GET可另外量測外部實際讀取時間。
- `stage3_view.js`／HTML：三種狀態、取得／更新／程式產生／端點寫入／瀏覽器讀取時間、原深色及手機卡片、三量六向排序、缺值置底、未知初篩可能漏選提示。live release只讀私有bootstrap設定，不採API提供的release旗標。

沒有修改原13:25前事件時間、正式收盤定義、±3%或既有必要量條件。13:25以後收到的歷史成交，可以用來核對原事件時間，但不聲稱它曾在13:25前已保存；沒有倒寫10/14 raw。

## 不能把來源完整性猜成已驗證

1. 時间欄位 `time` 按微秒解析，來源`lastUpdated`是更新標記，不能當成交時間。13:25:00與其後新成交皆不作P_before。
2. 同秒多筆保留微秒與serial，降冪順序矛盾不偷偷重新排序掩蓋；相同微秒用serial作測試契約的tie-breaker。
3. 富果文件只說serial為流水號，未承諾每檔連續。預設`serial_scope=UNSPECIFIED`，間隔記錄但不直接當掉包；若後續有已確認逐檔連續契約，才採連續性拒絕。
4. 完整性要求末頁、連續offset、沒有重複serial、quote查詢前後一致；再核對完整列數／累計成交筆數與size／常規累計量。**目前最後兩個對應只是待確認契約**，沒有硬宣稱文件已保證。單靠自行聲稱complete=true、兩網頁同價或多次快照一致，不能解除。
5. `LIVE_CONTRACT`與Worker／頁面live release預設皆未放行。用API Key取得資料，也不會自動解除契約閘門；需真實觀察確認與審查後才調整受信設定。
6. 完整全日ticks是本次保守的完整性路徑。冷門候選一頁可完成；熱絡候選可能超過12頁／50請求／deadline，維持UNKNOWN。未來可研究「可信完整降冪prefix已跨越cutoff」的較快方法，但不能只取第一筆pre就自稱無漏筆。

## 免費來源比較

| 來源 | 能取得／已知 | 限制與本次採用 |
|---|---|---|
| TWSE MIS＋TPEx即時揭露 | actual trade、行情及量；既有動態TWSE/TPEx池與A/B/C研究 | TPEx官方區分逐筆資訊、5秒快照與試撮；本次沒有找到可直接證明完整逐檔最後tick的匿名契約。MIS兩次快照不是獨立完整性證明。保留原pipeline。 |
| 富果免費HTTP | documented date/time/serial/size/volume；quote.isClose/isTrial、lastTrade、total；60/min、5WS訂閱 | 需要Key。已完成raw collector與反例檢查；真實HTTP、量／筆數對應、同秒序號及public usage尚未核對。候選6檔若各1頁共18請求，節流間隔理論至少約18.7秒，另加網路時間；不是實測。 |
| PChome | 前階段已保存6檔觀察，pre/close價格時間與MIS一致；最大只觀察到100列 | 未證明同日完整tick、trial排除、序號及獨立上游，不作正式gate。不重抓已完成研究。 |
| 富邦行情API | 官方文件提供類似quote/trades及登入後SDK | 需要證券帳戶登入／服務授權；不能當作已可匿名免費取得，也不能假定與富果上游獨立。本次未使用任何帳戶憑證。 |
| 永豐Shioaji | 官方提供全日／區間／最後N筆歷史ticks | 文件明說historical ticks不供即時輪詢，需登入與資料使用限制。本次不拿其歷史API反覆輪詢當即時來源。 |
| FinMind | 歷史ticks與即時snapshot文件 | snapshot不能證明完整最後tick；歷史資料沒有本次13:35發布時效／權限實證，未列為已可達標的免費替代來源。 |
| TWSE資訊商店 | 歷史成交檔 | 官方採訂購、付款後製檔；不符合完全免費及13:35候選驗證目標，未購買。 |

不同供應商可以有獨立傳輸／快取，市場原始上游仍可能都是同一交易所。不能聲稱「資料來自兩家」就保證所有共同來源錯誤已排除。本次驗證涵蓋多欄位、完整性和時間，不是單純價格相等。

## 發布方案比較與正式網址

| 方案 | 延遲／免費／限制 | 判斷 |
|---|---|---|
| GitHub Pages＋每次deploy JSON | 官方一般來源每小時10次build軟限制，custom Actions例外；部署超過10分鐘timeout不代表平常一定要10分鐘 | 適合保留靜態介面，不應把每檔到齊後重deploy當作秒級發布承諾。沒有修改或實測正式Pages部署。 |
| GitHub Raw／Contents API隔離檔 | 不用Pages部署，適合本次一次性公開可讀驗收；匿名REST API 60/hour/IP | 不推薦每1.5秒向REST長時間poll；Raw快取時效沒有本次持續刷新SLA。公開測試報告獨立記錄，不能當Cloudflare成功。 |
| Cloudflare KV | eventually consistent，其他地區可能60秒以上才見新值 | 不作即時單一真值儲存。 |
| Worker＋SQLite Durable Object | 官方free 100,000 Workers requests/day；DO 100,000 requests/day、5M rows read/day、100K rows write/day、5GB | 本次已實作並用Miniflare/workerd＋SQLite真實引擎測試。新Worker設定完全獨立、無cron；尚未在Cloudflare帳號部署，沒有雲端／全球讀取實測。 |
| 其他公開免費API／靜態服務 | 需各自驗證授權、quota、快取及寫入一致性 | 未以新服務包裝成本機成功冒充公開成功。本次選擇無新增外部帳號的隔離試驗。 |

建議將正式GitHub Pages當介面、未來授權後fetch新Worker公開JSON，CORS可讓**正式網址不變**。writer token、decision key、Fugle Key均僅在server/runner，不放HTML、不寫query、不公開回應。

免費容量必須量化：正式建議5秒輪詢，60分鐘約720requests／讀者；100人約72,000/day，另留writes及其他Worker共享額度。驗收用1.5秒並非建議永久全日輪詢。free quota耗盡會失敗，不保證任何流量下完全免費且永不失敗。

## 延遲：不得混用四種時間

| 階段 | 10/14原證據／本次結果 |
|---|---|
| 13:30→第一研究候選證據 | 155.533秒，13:32:35.533；歷史可用時間 |
| 13:30→首P_before獨立驗證 | 未取得，null |
| 13:30→首P_close正式即時驗證 | 未取得，null |
| 13:30→首完整VERIFIED | 未取得，null |
| 13:30→首真正公開已驗證訊號 | 未取得，null；後來公開的研究測試檔不能倒算13:35 |
| 原6候選最後證據更新 | 254.306秒，13:34:14.306 |
| 程式產生 | 本次實際執行時間，與歷史as_of分欄；見stage3-results/latency |
| 本機Worker寫入→實際瀏覽器讀取 | 約1.34～1.43秒，三profile實測；loopback，非Cloudflare全球網路 |
| 新分支公開檔寫入ack／外部瀏覽器 | 另見public-read-acceptance及GitHub同步receipt，測試在下午較晚執行，不是實盤 |

沒有可證明的「最早正式時間」；目前不能承諾13:40前會有VERIFIED。低量候選的資料與讀取路徑有機會滿足，但仍待真實API、下一交易日及隔離雲端實測。14:50／15:20／17:50最終官方稽核保留，而且官方收盤一致不能倒證pre或遮住MIS擷取失敗。

## 測試／交付狀態

- 基線301 Python／96前端沒有減少。新增47 Python、6前端：**348 Python／102前端PASS**；Worker真實引擎14項PASS另列。
- 逐筆：13:24:30→13:24:59新成交、same-second及same-microsecond、13:25邊界、長時間無成交、缺頁／末頁／inner tick、count與volume、seq gap契約、trial、cache、delay、date/symbol範圍、source/MIS衝突、正常／延後／無新close、外部旗標、原hash與截止。
- 發布：auth/signature、版本race／冪等／回歸、部分候選、no-store/CORS、body budget、receipt mismatch、503重試與401停止、背景coalesce不阻擋capture。
- Chromium桌機Windows UA、Chromium iPhone13模擬、WebKit iPhone13模擬：1→6刷新、三狀態、六排序、缺值置底測試、false verified、failed read提示與保留state、深色、無overflow。Linux引擎，未有Windows／iPhone真機。
- 本次未啟動MIS全市場網路收集、未新設定Fugle Key、未部署Cloudflare、未改正式網頁或正式排程。
- 所有新成果推送新分支，commit用skip ci避免與正式共享concurrency；本次GitHubCI不是success，不重跑正式workflow。

## 原始來源文件

- https://developer.fugle.tw/docs/data/http-api/intraday/trades/
- https://developer.fugle.tw/docs/data/http-api/intraday/quote/
- https://developer.fugle.tw/docs/pricing/
- https://developer.fugle.tw/docs/data/intro/
- https://www.tpex.org.tw/zh-tw/mainboard/trading/rules/system.html
- https://www.fbs.com.tw/TradeAPI/docs/market-data/http-api/getting-started/
- https://sinotrade.github.io/tutor/market_data/historical/
- https://finmind.github.io/tutor/TaiwanMarket/Technical/
- https://www.twse.com.tw/zh/products/dataeshop.html
- https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits
- https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- https://developers.cloudflare.com/kv/concepts/how-kv-works/
- https://developers.cloudflare.com/workers/platform/limits/
- https://developers.cloudflare.com/durable-objects/platform/pricing/
