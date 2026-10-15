# 2026-10-15 第三階段接手

先讀本目錄 README，再讀 `reports/2026-10-14-stage3/HANDOFF.md`。禁止合併 main、正式部署、修改正式 workflow／排程／Secret／Token／歷史資料；不得重啟第二個全市場 collector。

本分支 `stage3/20261015-evidence-time-audit` 繼承 aa3998d，原修復分支仍 0707902，舊第三階段仍 aa3998d。新工作只修正附加 stage3 模組及新增本報告，沒有覆蓋其他 Work。具體 GitHub Commit 見交付同步收據及新遠端分支 HEAD。

已完成：來源時間與收到時間矛盾拒絕、received/persisted 分離、manifest fsync、quote/tick size 衝突拒絕、Decimal ±3% 含等號、顯示報酬重新計算、首次頁面更新不得回退、壞 schema 保留狀態、同目錄 watch 重啟序號與收據接續。LIVE_CONTRACT、Worker ALLOW_LIVE_VERIFIED、前端 liveReleased 都仍 false。

真實資料依然只有 10/14 研究 6、正式 0；不能把合成 TEST_CONTRACT 改成真實放行，也不能以取得 Key 直接放行。沒有真實 Fugle HTTP 或公開 Cloudflare 部署；先前 GitHub 匿名瀏覽器讀取受阻沒有被本次 connector 讀取取代。正式目標仍未達。

重現（輸出必須用新隔離目錄，不覆寫舊證據）：

```bash
python3 -m unittest discover
npm test
python3 stage3_replay.py /original/mis-probe-2026-10-14.zip /new/output/replay
STAGE3_REPORT_DIR=/new/output node stage3_worker_acceptance.cjs
STAGE3_REPORT_DIR=/new/output STAGE3_PREVIEW_PATH=/new/output/replay/stage3-preview.html node browser_stage3_acceptance.cjs
```

此環境 MINIFLARE_MODULE 預設 `../stage3-runtime/node_modules/miniflare`。PLAYWRIGHT_MODULE 使用 `/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright`；CHROMIUM_EXECUTABLE_PATH 使用 `/workspace/scratch/52ff117b908b/fast-browser-runtime/bin/chromium`；新的 WebKit 下載目錄用 PLAYWRIGHT_BROWSERS_PATH 指向 `/workspace/scratch/52ff117b908b/stage3-browsers`。系統函式庫若遺失，必須先恢復；不能只看到 browser 進程啟動就說 PASS。

下一步缺的是專用富果免費 Key 的安全設定，以及能操作獨立公開測試服務的帳號／憑證與外部讀取驗收。既有授權允許本機隔離實作；不要重問已授權的可逆工作。不能讀取其他服務 Secret，不要讓使用者貼 Key 到對話。正式合併／部署需要另有明確授權。

取得實際資料後，先核對 rows/transaction、sum(size)/tradeVolume、serial 排序／範圍、缺頁與常規市場範圍，再調整私有來源契約；保留每頁 raw 與時間。候選查核需控制共享免費額度，熱絡股超過頁數／請求上限仍 UNKNOWN。下一交易日只消費已有 journal，不增加全市場 API；目前正式 workflow 沒有啟用新 journal，安全 runner 整合尚待驗證。

端點若已有版本，應在同一隔離目錄接續；新空目錄接已有端點的版本協調尚未實作。外部瀏覽器延遲、真實首 VERIFIED、每日成功率都沒有可宣稱的數字。沒有足夠證據就不升級。
