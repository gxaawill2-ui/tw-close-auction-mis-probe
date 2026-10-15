# 台股尾盤 ±3%：第三階段續作與證據時間稽核

2026-10-15，Asia/Taipei。從已交付第三階段 `aa3998d26e534e73b6042df92c778382d943b836` 接續，新增隔離分支 `stage3/20261015-evidence-time-audit`。它繼承最新修復分支 `07079029fea4bef8f0bc9b60fb2c006a32d712a9`，沒有重寫或覆蓋原分支。

**隔離程式與離線驗收可交付；真實 13:35～13:40 VERIFIED 公開發布仍未達成，不具正式部署條件。** 沒有新的富果 Key、真實成交 HTTP、Cloudflare 雲端部署或下一交易日證據。不要把本次早上重新運算的時間當成 10/14 當時發布的時間，也不要把本機瀏覽器延遲當成全球公開延遲。

## A～E 結論

| 問題 | 結論 |
|---|---|
| A. 可獨立確認 13:25 前最後實際成交？ | 尚不能對真實候選成立。完整性、筆數／累積量語意與獨立傳輸仍待實證；正式 0 檔。已實作完整逐筆證據的核對與拒絕條件。 |
| B. 能在 13:35～13:40 公開完整驗證結果？ | 未證明。離線研究 6 檔，本機逐檔發布可運作，但沒有第一檔真實 VERIFIED 或匿名公開瀏覽器讀取時間。 |
| C. 真正瓶頸？ | 專用行情授權與真實 raw、完整性契約、同一 runner 安全讀取現有 journal 的整合，以及可操作且獨立的公開測試服務／網路驗收。再快的本機運算不能補出不存在的真值。 |
| D. 可完全免費且正式網址不變？ | 技術架構可保留 Pages 網址、改讀獨立 Worker JSON。免費額度和行情公開使用範圍仍有條件，不能保證任何流量都零成本。API 可免費讀取不等於已獲准公開轉傳。 |
| E. 下一交易日需驗什麼？ | 真實候選完整 ticks、末秒／同秒／試撮、正常及延後收盤、必要量、與晚到官方檔核對，再量測外部匿名桌機／手機實際讀取。若沒有足夠證據就維持 RESEARCH_ONLY／UNKNOWN。 |

## 本次修正及其原因

1. 成交時間不得晚於該頁實際收到時間；quote 的更新時間不得超前收到時間，統計時間不得落後最後成交或超前更新時間。截止前的 quote 不能證明截止前最後成交，收盤前請求的 quote 不能證明收盤完成。這些是證據成立的時間條件，不是新的交易策略。
2. `stage3_provider` 分開保存 `received_at` 與 fsync 後 `persisted_at`；manifest 也 fsync。驗證拒絕倒置的保存時間。原本收到時間其實記在落盤後，現在不再混用。
3. 尾盤報酬由有效價格重新計算，未知保持 null，拒絕沿用外部 `tail_return_pct=999`。Python 與 Worker 用十進位交叉乘法保留 ±3% 含等號，避免 JavaScript 浮點造成邊界漏選。
4. quote.lastTrade.size 如存在，必須與最新實際 tick.size 相符，否則不能通過收盤量核對；錯誤字串不會拋出未處理 Decimal 例外。
5. 頁面第一次輪詢也不能以較舊版本覆蓋已嵌入的較新資料；不完整 schema 不改動目前狀態及更新時間。
6. watch 重啟接續同日 LIVE 本機結果／outbox 最大版本號；只恢復序號，不恢復任何 VERIFIED 旗標。發布收據接續既有紀錄，不覆寫先前收據。若換新輸出目錄接上已有端點，仍須先解決端點版本協調；此情境沒有被自動宣稱可復原。
7. Worker／瀏覽器測試支援新的報告目錄與測試頁路徑，避免覆寫 10/14 已保存的測試證據。原正式程式、排程、歷史資料、既有報告均未修改。

三個 live release 閘門仍為 false：來源契約、Worker、前端私人 bootstrap。取得 Key 不會自動解除它們。所有合成成功仍不是正式 VERIFIED。

## 來源及免費方案核對

完整比較沿用 [第三階段研究](../2026-10-14-stage3/README.md)，沒有重做前次 MIS/PChome 調查。本次重新閱讀 Fugle 官方 quote、trades、來源說明及方案，確認 closeTime／lastTrade／total／isClose／isTrial／微秒型態範例與分頁欄位存在，但文件沒有提供本專案所需全部完整性保證。

| 來源／發布方案 | 可用證據 | 本階段限制 |
|---|---|---|
| TWSE MIS／TPEx 即時行情 | 已保存實際成交欄位及研究觀察；試撮需分開 | 快照與兩次相同價格不足以證明無漏掉截止前最後成交。 |
| Fugle 基本會員 | 官方列免費、60 次日內 API/min、5 WS 訂閱；quote/trades 有時間及序號 | 需要專用 Key。並未實證列數等於 transaction、sum(size) 等於 regular volume、序號排序／範圍和資料完整性；不得假設個股流水號連號。 |
| PChome | 原研究有候選價及成交列交叉比對 | 不具完整性與來源獨立保證；價格相同不能升級。 |
| Shioaji／富邦／FinMind／官方歷史成交檔 | 先前研究記錄保留 | 帳戶授權、時效、費用或完整性未滿足本次匿名免費即時驗證。 |
| GitHub Pages + JSON 重新部署 | 可保留既有網址 | 不適合作為逐檔秒級更新保證；沒有變更正式站或測試正式部署。 |
| Pages 介面 + 獨立 Worker/SQLite DO | 本機真實 workerd/SQLite 有逐檔版本、HMAC、重試、no-store | 沒有雲端實測。免費 quota 仍有限；正式流量應採受限時段及較慢輪詢。 |
| Cloudflare KV | 可跨區讀取 | 最終一致性不適合以嚴格最新版本為基準；不選作本次立即發布的主儲存。 |

Fugle 官方說明指出行情由時報資訊與富果提供、來源含 TWSE/TPEx；這是另一個傳輸管道的候選，並不代表交易所上游互不相關。其公開使用條款亦要求遵守來源交易資訊規範，因此完全免費公開轉傳仍需確認使用範圍。本次未對外轉傳任何新取得的真實 Fugle 行情。

官方文件（2026-10-15 重新讀取）：

- [Quote](https://developer.fugle.tw/docs/data/http-api/intraday/quote/)
- [Trades](https://developer.fugle.tw/docs/data/http-api/intraday/trades/)
- [方案](https://developer.fugle.tw/docs/pricing/)
- [資料來源及規範](https://developer.fugle.tw/docs/data/intro/)

## 收盤與延遲

P_close 模組要求來源 isClose、排除 isTrial，closePrice/time 與實際 lastTrade、最新 tick 一致，再與 MIS 個股價格及必要量核對；區分正常 13:30、延後 13:33 及沒有新收盤成交。來源 finality 語意仍待實測，所以不能只靠欄位名把它當成真實收盤證明。沒有新收盤成交保留實際成交與 0 收盤盤量分類，不跳過原必要量條件。後續官方盤後核對完整保留。

| 13:30 後階段 | 10/14 原始證據／本次結果 | 性質 |
|---|---|---|
| 第一檔研究候選 | 13:32:35.533；+155.533 秒 | 歷史證據到齊，非真實公開時間 |
| 第一檔研究收斂及必要量 | 13:33:51.351；+231.351 秒 | 歷史研究，非獨立驗證 |
| 第一檔 P_before 獨立成立 | null | 未取得真實完整證據 |
| 第一檔 P_close 獨立成立 | null | 未取得真實完整證據 |
| 第一檔完整 VERIFIED | null；0 檔 | 不降標準 |
| 第一檔真實公開可讀 | null | 先前匿名讀取有網路阻擋，本次未假稱解決 |
| 全 6 檔研究證據到齊 | 13:34:14.306；+254.306 秒 | 歷史證據到齊 |

本次實際運算、Worker 寫入與瀏覽器讀取的時間分別記在 `replay/stage3-latency.json`、`worker-acceptance.json`、`browser/acceptance.json`。它們是本機測試，不能填進真實交易日上述 null 欄位。最早真正完整驗證時間尚無可證明的數字；晚到官方收盤也無法補出 13:25 前最後成交的獨立真值。

初篩可研究計算 1,946/1,970、未知 24；仍可能漏選，沒有聲稱全市場無漏選。重播仍 6 檔研究、0 檔正式。內層歷史 capture ZIP 前後 SHA256 均 `c57da5c49487fd7b9fcfde0680db494c5ff99eec13869a9d77e6932fb4cfd03f`；它不是 GitHub 外層 artifact ZIP 的 digest。

## 驗收及交付入口

- Python：360 項通過，包含原 301 項；前端／Node：104 項通過，包含原 96 項。新增時間錯序、最後成交量矛盾、十進位門檻、首次讀取版本回退與中斷續號／收據保留反例。
- Worker：14 項本機 HTTP/workerd/SQLite 檢查通過，沒有雲端部署。
- 瀏覽器：以 `browser/acceptance.json` 的實際完成記錄為準；模擬手機不是實體手機，模擬 Windows UA 不是 Windows 作業系統。
- 隔離頁：`replay/stage3-preview.html` 為 10/14 歷史重播，`replay/synthetic-preview.html` 為清楚標示合成測試。均不是真實交易訊號或正式站更新。
- 程式：根目錄 `stage3_ticks.py`、`stage3_provider.py`、`stage3_selection.py`、`stage3_run.py`、`stage3_publication.py`、`stage3_view.js` 及 `isolated_publication/`。
- 接手：[HANDOFF.md](HANDOFF.md)，基線完整來源研究及先前驗收仍在原第三階段目錄。

沒有觸發 GitHub 新 CI；同步 Commit 使用 `[skip ci]`，避免既有 workflow 共用正式收集 concurrency 而互相中斷。本機 PASS 不等於 GitHub CI PASS，也不等於真實交易日成功率。

本次最終瀏覽器結果：Chromium 桌機 UA、Chromium iPhone 13、WebKit iPhone 13 共 3 個模擬設定 PASS；本機 Worker 寫入至瀏覽器觀察 1371～1436ms。首次補跑因環境缺 WebKit 函式庫及中文字型而受阻，恢復依賴後完成全套；手機與桌機截圖已人工檢查中文字形、深色版面及無橫向溢出。這不是實體手機或公開雲端成功率。
