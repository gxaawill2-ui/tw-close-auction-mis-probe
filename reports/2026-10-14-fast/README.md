# 台股尾盤 ±3%：快速研究結果與最終官方稽核分離

日期：2026-10-14（Asia/Taipei）。隔離分支：`fix/20261014-capture-reliability`。

## 驗收結論

**快速研究發布的隔離原型通過；13:35～13:40 完整正式驗證目標尚未達成，不宜作為已完成的交易訊號系統部署。**

10/14 的已保存證據足以在 13:32:35 開始形成研究名單，13:34:14 形成全部 6 檔；不必把 14:50、15:20、17:50 官方完整盤後檔案當作研究名單的等待門檻。但在本次可取得的證據中，13:25 前最後成交獨立確認仍不足，新保存功能也不能倒補 10/14 的保存時間。正式驗證始終為 0。

這是離線時間順序重播的可用時間，**不是證明當時曾上網發布**。正式網站、正式排程、Secrets、Token、原始 Artifact 都沒有修改；沒有執行歷史盤中重抓，沒有啟動新全市場網路擷取。

## 時間與成功率

| 指標 | 10/14 原始／基線 | 隔離重播或本次測試 | 解讀 |
|---|---|---|---|
| close B 原始 HTTP 股票取得 | 1,920/1,970，97.4619% | 同一份歷史資料，沒有增加 | 不能把程式修復當作歷史成功率提高 |
| 研究可計算（先前完整調查） | 1,946/1,970，98.7817% | 同一份歷史資料 | 研究涵蓋率不是正式驗證率 |
| 第一檔研究候選證據到齊 | 原網站沒有可靠當日發布證據 | 13:32:35.533，收盤後 155.533 秒 | 允許單一 fresh 收盤觀察的研究級別，成交量可能仍待確認 |
| 第一檔價格研究收斂且必要成交量到齊 | 原網站發布被擷取失敗門檻阻擋 | 13:33:51.351，收盤後 231.351 秒 | 仍缺獨立價格證明，不是完整驗證 |
| 6 檔研究結果最後證據更新 | 全流程約 13:34:25 結束，發布阻擋 | 13:34:14.306，收盤後 254.306 秒 | 不等待其他股票及整個 controller 結束 |
| 第一檔完整驗證 | 未取得 | 未取得，JSON 為 null | 禁止用 0 秒、13:35 或官方匹配時間代替 |
| 當日真正公開發布／公開讀取 | 未證明 | 未證明，JSON 為 null | 本次 16 時後本機寫檔時間另存，不能冒充歷史公開時間 |
| 正式驗證率 | 0/1,970 | 0/1,970 | 未降低驗證標準 |
| 全部 319 筆保存批次的離線分析 | — | 本機約 1.43 秒 | 不是網路擷取或真實盤中發布耗時 |

本機 journal → fsync → 雜湊核對 → 分析 → JSON 寫檔的 4 筆合成小批次約 0.68～1.81ms；僅為本機小樣本，不代表整個市場的 fsync 或網路負載。watch 每秒讀取新增批次，本機 HTTP 頁每 2 秒刷新：正常路徑額外等待約 0～3 秒，加上實際處理與磁碟時間。此為設計界限，沒有真實交易日實測。

## 已實作的資料路徑

1. `probe.snapshot` 改以 completion order 取得已完成批次，不等較慢的前一批。傳統 raw 檔及回傳順序仍按 batch_no 排序。
2. 只有設定新的 `MIS_FAST_JOURNAL_DIR` 才會啟用隔離 journal。既有正式 workflow 未設定、未修改。
3. `fast_capture_journal.Journal` 每批 raw bytes flush/fsync 後才記 `persisted_at`，保存 offset、length、SHA256，再 fsync journal。reader 檢查 bytes、hash 和時間，不接受部分寫入或 receive 晚於 save 的證據。
4. `capture_pre_boundary.py` 是未排程的實驗收集器：13:24:30 開始，最多兩輪，沿用動態股票池、50/5 基準，13:25 截止，13:24:45 後拒絕新啟動，403/429 停止。它**只能證明實際觀察已保存，不能保證捕捉最後一瞬間的成交**。
5. `fast_selection.Engine` 每個批次逐檔重算，沿用現有 freshness、A/B/C、probe conflict、volume evidence、±3% Decimal 公式。不等待整個市場完成。後續價格衝突、regression 或跌回門檻內，撤回先前候選並保留理由。
6. `watch --check-sources` 以單一獨立 worker 查核候選，慢來源不阻塞 MIS journal intake。最多 12 檔、兩檔間至少 1.1 秒，401/403/429 停止；14:30 前 20 秒不再新增來源查核。來源慢或錯誤不改變 research/unknown 為成功。
7. 預設公開查核用 PChome；有獨立選用 `FAST_FUGLE_API_KEY` 才使用富果候選 quote + trades。沒有設定或修改任何使用者金鑰。此介面是 raw observation adapter，**不是已經通過驗收的正式 validator**。
8. `fast-results.json` 原子更新，包含每檔初次出現、pre receive/save、close receive、更新時間、checks、尚缺條件與撤回名單。隔離 HTML 可直接開啟；在 localhost HTTP 服務時才自動刷新旁邊 JSON。
9. `fast_gate` 不信任外部 dict 的 `validated=true`。未有有效獨立成交與收盤 finality adapter 前，強制保留 `RESEARCH_ONLY`。沒有新增策略門檻，也沒有把盤後交易量放入盤中量。
10. 現有官方核對保持獨立：14:50、15:20、17:50 仍是預定最終稽核，不是研究名單的阻塞條件。新模組沒有改動 `official_retry.py`、正式 state 或 workflow。

原型目前只寫隔離本機，沒有完成將每個批次公開寫到正式網站的 transport。GitHub Pages 的正式部署及其實際延遲尚未測試，不能把本機發布時間視為真實網頁發布時間。

## 免費來源研究與可行最快時間

| 來源 | 本次證據 | 可用性與限制 | 能否直接通過完整驗證 |
|---|---|---|---|
| TWSE MIS、TWSE/TPEx 官方日資料 | 已保存 10/14 原始逐批行情及先前 15:20 官方核對 | MIS 提供 actual trade nested 欄位，A/B/C 可先形成研究證據；晚到官方日資料可最終比對收盤，但沒有 pre-13:25 逐筆獨立真值 | 本次不能 |
| PChome 公開成交明細 | 6 檔實際匿名 GET → 頁面自行公開的 is_check POST，取得 4～100 列。6 檔 pre/close 價格及採用時間全與 MIS 相同 | 4.40～5.49 秒／檔；不保證每頁是完整 tick，同日標記與試撮排除契約不足，upstream 獨立性未確認；此次下午16時後觀察，不是13:35測試 | 不能；一致只提供額外研究證據 |
| 富果免費基本會員 | 官方文件：60 次日內 API/min；5個WS訂閱；API需Key；quote 有 isClose/isTrial/lastTrade/lastTrial；trades有date/time/serial與分頁 | 候選6檔 quote+trades 共12請求，比全市場有希望；全市場單輪每檔1req理論就需1,970/60≈32.8分鐘，免費WS也無法全市場訂閱。沒有Key，沒有實際HTTP驗收，分頁／finality／保存證明尚未完成 | 可能可作候選獨立交叉來源；本次仍不能 |
| Yahoo 1分鐘K | 既有研究曾無 exact 13:30K | 聚合K不能證明13:25前最後一筆，不能取代逐筆／收盤證據 | 不能 |

查核文件（2026-10-14讀取）：

- TWSE 交易制度：https://www.twse.com.tw/zh/products/system/trading.html
- 富果成交明細：https://developer.fugle.tw/docs/data/http-api/intraday/trades/
- 富果報價：https://developer.fugle.tw/docs/data/http-api/intraday/quote/
- API驗證及限流：https://developer.fugle.tw/docs/data/http-api/getting-started/
- 免費方案：https://developer.fugle.tw/docs/pricing/
- 來源說明：https://developer.fugle.tw/docs/data/intro/

TWSE 文件區分 13:25～13:30 模擬撮合與 13:30 正式集合競價，以及暫緩至13:33的收盤。不能把試撮價、最後成交價欄位名稱或延後收盤誤當普遍13:30正式收盤。保留原有延後收盤研究分類，不能任意把延後成交冒充13:30成交。

**最快時間結論：**10/14 的研究分析證據可在13:32:35開始、13:34:14全6檔到齊；下一日能否實際於13:35～13:40發布，還需盤前保存、來源與public transport的實測。完整正式驗證沒有可證明的最早時間；不能承諾13:35，亦不能說15:20即可完成，因為晚到官方收盤仍無法倒證13:25前最後成交與保存。

## P_before 的真正瓶頸

「13:25前最後一筆實際成交」是成交事件時間，`persisted_at` 是檔案保存時間，兩者不能混用。10/14 main全市場資料是在13:25或較晚收到，只有probe少數股票可能更早；6候選沒有原始durable-save時間可以證明已於cutoff前保存。

13:27～13:29 reference 僅採用 nested actual trade 時間 `<13:25:00` 的觀察，不採用晚發生的新成交。這種穩定一致增加研究可信度，但沒有另一個來源證明「沒有漏掉更晚但仍在13:25前的成交」。把13:24:30的一次觀察存檔，也不能證明13:24:59沒有新成交。

獨立驗證需要：已保存的最後實際成交與cutoff後完整／可信的歷史ticks相符，或有可核對完整性與時間的實際成交stream，加上同日、常規整張市場、排除trial及收盤finality。富果候選查核值得下一階段測試，但沒有取得來源契約和真實資料前不能寫成已解決。

## 驗收與保留風險

- Python：301項 PASS（原275 + 新增26）；Node/前端：96項 PASS（原93 + 新3）。
- 新增測試：批次completion order、完整性hash、晚保存、禁止歷史回填、±3%精確邊界、無新pre成交、延後收盤、價格衝突撤回、stale拒絕、少數股票失敗不阻擋他檔、限流停止、資料源未配置不請求、slow source不阻塞journal、外部verified flag不能升級。
- Chromium Windows UA桌機、Chromium iPhone13模擬、WebKit26.5 iPhone13模擬：六種排序、缺值置底邏輯、深色、逐檔時間、零正式驗證、空狀態、防偽validated及無橫向頁面溢出 PASS。Linux引擎，不是Windows或iPhone真機。
- localhost HTTP：頁面透過正常poll從1檔更新到6檔，仍0正式驗證，沒有production請求。原始319筆離線重播hash前後一致。
- source smoke已修正只拿到PChome公開auto-form的問題；完整GET/POST與compressed raw保留於交付包。全部6檔匹配仍明確validated=false。
- 尚未有下一真實交易日、富果金鑰驗收、完整ticks證明、盤前保存覆蓋率、Windows/iPhone真機、正式公開transport延遲。
- 不要額外讓實驗盤前全市場收集與正式全市場流程同時運行。下一交易日應先規劃共用原請求與獨立輸出，避免增加正式API負荷。
- 本次提交標記 `[skip ci]`：既有probe workflow的push測試共用`twse-mis-live` concurrency group，避免隔離提交佔用正式群組。本機測試皆已執行；不聲稱新commit已通過GitHubCI，也不修改正式workflow。

建議：保留隔離原型繼續測試候選獨立來源與public transport；**目前不建議以「完整即時交易驗證已完成」進正式部署**。是否將研究名單提前呈現，與是否允許正式verified發佈，是兩個不同的決策。
