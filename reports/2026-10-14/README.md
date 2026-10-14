# 2026/10/14 MIS 收盤擷取調查與隔離修復

本次只建立修復分支，未合併 main、未部署 GitHub Pages、未修改任何正式排程或 Secret。尚未經下一個真實交易日驗證。此版本可供程式審查及隔離測試，不能宣稱已證明每日真實擷取成功。

## 來源與完整性

- Repo：`gxaawill2-ui/tw-close-auction-mis-probe`
- 開發基線與工作結束前唯讀核對的 main：`4f0eb6c7ae238f876d25223d178c88fdee9bf12a`
- 修復分支：`fix/20261014-capture-reliability`
- 原主執行：`38514354547`，執行程式版本：`ad54d960d889785f73f91bb5bb68251a36e5307a`
- 原 Artifact：`mis-probe-38514354547`，ID `11872406874`
- 原 ZIP SHA256：`4ea6e228ce86d965584203dfbf5f04d7707a238d74d24cafe133e3994a98cf6f`，下載後與 GitHub digest 一致。原始輸入不變。
- 備援執行 `38515898607` 的 Action SUCCESS 是 `Skipped: existing capture is immutable for this date.`，不是擷取成功。Issue #1、state/live 的原始擷取仍為失敗，沒有被該 skip 改為成功。

## 已證明的失敗鏈

close B 全市場40批，batch size 50、concurrency 5。缺漏50檔全部屬第29批（上櫃6185～6290，逐檔見CSV）。

| 時間（台北） | 實際證據 |
|---|---|
| 13:33:20 | close B 階段開始 |
| 13:33:51.352 | 第29批第一次 HTTP 請求開始 |
| 13:34:08 | B階段截止，保留13:34:10的C時刻 |
| 13:34:08.415 | 第29批請求以 `URLError: timed out` 結束；實際17.063秒，已晚於B截止 |
| 13:34:08.915 | 舊程式等待0.5秒後進入重試，已超過截止；回傳新 sentinel `CAPTURE_DEADLINE_NO_REQUEST` |
| 13:34:10 | C定向請求76檔開始，包含全部50檔缺漏 |
| 13:34:14.306 | C全部76檔回傳 |

根本原因有三層：

1. **實際網路取得失敗**：B29 HTTP請求逾時，沒有 msgArray。不是50檔被freshness篩掉，也不是HTTP200少回50檔。
2. **錯誤證據被摘要遮蔽**：fetch_mis在重試截止時新建sentinel，覆蓋最後實際請求的頂層錯誤、request/receive時間與latency。attempts還保留第一次timeout，但舊摘要只讀頂層，造成timeout=0、latency=0、retry=1等誤導。
3. **全日發布被過嚴的執行分類阻斷**：classify把一批的deadline sentinel當成整個必要階段未執行，產生`MANDATORY_CAPTURE_NOT_EXECUTED`，因此CAPTURE_FAILED並跳過研究名單發布。實際上B有39批成功，C另已提供恢復證據。

B整階段48.98秒；A37.941秒。B20另有25.461秒慢回應，B12為11.347秒，B24為10.079秒。可證明尾端延遲與可用重試時間不足；**無法證明**是併發過高、特定伺服器限流或TWSE快取節點故障。原證據沒有403/429；此次維持50/5基準，不以推測修改併發。

## 50檔及價格未收斂分類

- B50檔全為同批transport timeout，歷史B的50檔缺漏仍保留。
- C選76檔＝B缺50檔＋另外26檔未研究收斂；沒有漏掉B缺漏股票。
- 50檔中48檔以原始A與實際C觀察完成**研究**AC收斂；6198、6212仍無有效實際成交資料，不能補價格。
- 額外26檔：6檔以BC恢復研究收斂，20檔無有效實際成交資料。
- P_before有24檔未知：保存的pre A/B/C中v=0且沒有nested實際成交價/時間。最後一輪pre retry的deadline sentinel遮住了這個底層原因；不能把零成交量補成價格0，也不能用後續價格倒填。
- 3516、6641雖有收盤研究價格，仍沒有13:25前可用價，故不能計算。
- 嚴格舊AB close收斂1894、pre1946、兩者1892；研究close納入AC/BC後為1948、研究可計算1946、未知24、±3%研究候選6。
- 222檔「沒有新收盤成交」有較早的有效實際成交候選；與整日沒有可用成交的股票分開。仍待官方核對，不自動標準確收盤。
- 原報告stale batch=9、server regression response=0。沒有把stale轉fresh。修復後測試另覆蓋fresh server時間倒退。

逐批與逐檔詳情：`replay/batch-report.csv`、`attempt-report.csv`、`missing-50.csv`、`unknown-prices.csv`。日期、request/receive、HTTP、attempt、缺漏與收斂類型均保留。

## 修復內容

- fetch_mis遇重試截止時保留最後實際結果，另寫retry_stop_reason；不以新sentinel覆蓋已發生的timeout。
- 依實際attempt計算timeout（含“timed out”）、HTTP錯誤、request errors、request次數與總latency。沒有發出請求與HTTP非200分開。retry只計真正再次發出的請求。
- C之後對affected symbols進行最多6輪、5/10秒backoff的bounded retry；不重抓全市場。不足2秒不再開始新一輪，pre與close原截止不變。403/429停止後續重試。成功後立即結束，不空等backoff。
- 新觀察使用獨立`close_targeted_retry`及真實時間，研究類型`TARGETED_converged`，不得冒充A/B/C快照。仍要求不同fresh server observation、相同成交價/時間/累積量；新鮮矛盾或server regression不採舊配對。
- 必要階段整個沒有可用回應、缺檔、日期不對、壞檔仍CAPTURE_FAILED；只有部分批次失敗且其餘證據完整則CAPTURE_PARTIAL，保留缺漏/warnings。這是執行完成度的會計修正，不是把價格驗證放寬。
- 保存`source_capture_outcome`與completion policy版本，標示是否由歷史證據重新分類，避免把新政策當成原run已成功。
- 官方核對開始時發布RECHECKING，讀取Artifact/核對發生例外時保存PENDING_RECHECK_ERROR，不覆蓋live；前端獨立讀取live與official；即使已有候選也持續更新核對狀態。顯示股票池、研究可計算、未知、B原始缺漏、最近更新與下次預定核對。
- official MATCH不覆蓋CAPTURE_FAILED；skip/dry-run不能產生每日成功。深色介面、手機卡片及原六向排序保持。
- 離線audit與合成fault工具沒有網路副作用；原始ZIP與JSON不修改。

## 成功率與時間影響（分清真實證據和模擬）

| 指標 | 修復前真實10/14 | 同一Artifact離線重播 | 合成成功回應測試 |
|---|---:|---:|---:|
| B原始HTTP完整率 | 1920/1970＝97.46% | **仍97.46%** | 缺50→定向恢復後100% |
| 嚴格AB close收斂 | 1894/1970＝96.14% | 仍1894，不拿C偽裝B | 另列研究定向配對 |
| 研究可計算 | 1946/1970＝98.78% | 仍1946＝98.78% | 僅測試樣本，非10/14補值 |
| 研究候選 | 6（被全日失敗擋住發布） | 6，可在隔離頁示範PARTIAL | 不產生正式訊號 |
| 正式策略驗證 | 0 | **仍0** | 仍不授權正式訊號 |

合成全市場1970檔：正常回傳100%且無重試；集中50檔與分散50檔，均由97.4619%到100%，只請求50檔、1輪，假設每輪3秒故額外3秒。持續失敗則仍97.4619%，4輪、含backoff46秒並於13:35停止，沒有虛構恢復。

真實耗時尚未證明。10/14 C兩批latency為2.711與4.306秒，可作少量定向重試的一個參考，**不是保證**。健康資料不增加重抓；持續unknown可能用完剩餘close研究窗。底層urllib的socket timeout不是嚴格total wall-clock上限，過期才返回的資料必須標錯誤且不得採用；不能承諾作業系統/網路一定準秒返回。

## 測試與瀏覽器驗收

- 基線：260 Python、86 Node/DOM測試通過。
- 修復：275 Python、93 Node/DOM測試通過（0失敗）；另有4種合成市場scenario及真實Artifact離線重播。
- 覆蓋全市場正常、單批/集中50/分散50、timeout、空回應、403/429停止、stale、server regression、A/B價格衝突、C部分恢復、retry截止、13:25前時間拒絕較晚成交、正常與延後收盤、無新成交、Decimal ±3%、成交量必要欄位、未知禁止正式訊號。
- 原有正式候選、官方缺值/錯日期/空表、成交量證據、排序與狀態回歸均保留。
- 新10/14測試頁：真實Chromium153桌機Windows UA、Chromium iPhone13模擬、WebKit26.5 iPhone13模擬均PASS。每個profile驗證6種排序、缺漏、官方pending/來源失敗、原capture失敗保留、深色、無橫向溢出及零外部網路/零pageerror。
- **不是Windows原生或iPhone真機驗收**，需保留此限制。原版完整離線回歸另有57項瀏覽器檢查PASS。完整瀏覽器紀錄與圖片在交付ZIP，機器報告在`browser/capture-acceptance.json`。
- `oct14-isolated-preview.html`為可直接開啟的單一離線成品；時鐘固定14:10且有隔離標示，不能當即時正式網站。

## 官方核對與排程檢查

現有workflow為UTC 06:50/07:20/09:50，對應台北14:50/15:20/17:50。程式只下載已保存的capture Artifact與指定日期官方資料，空表/錯日期/來源失敗保持PENDING，與capture失敗分開；後續可以再讀同一Artifact。

查到10/14 01:10的`PENDING_NO_CAPTURE`來自較早排程延遲執行，不能當成今天盤後已檢查。GitHub歷史中有多次scheduled run明顯延遲，預定時間不保證準點。目前帳號內cron-job.org頁面需登入，本次只核對repo保存的10/5外部排程驗收與10/14實際13:00啟動紀錄，**沒有重新登入驗證cron設定**；manual來源宣告不能單獨證明來源。

沒有改任何workflow、cron-job.org、Token或Secret。本次所有回歸為offline，不把官方資料延遲誤當MIS失敗，也不以官方成功掩蓋MIS失敗。

## 上線建議與剩餘工作

建議先審查分支及隔離結果，再由使用者決定部署。尚不宜宣稱整個策略正式可交易：P_before獨立真值、全部必要策略條件及真實下一交易日穩定性仍未證明。PARTIAL_VERIFIED正式發布設計見同目錄文件；本次正式訊號維持關閉。

下一個交易日應在使用者核准後安排不影響正式capture的受控驗證，觀察實際延遲、targeted請求數、403/429、deadline及官方一致性。不得為測試而同時重跑整個正式全市場擷取。main若由其他Work繼續更新，先重新比較最新main再整合，不覆蓋最新資料。
