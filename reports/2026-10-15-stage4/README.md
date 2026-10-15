# 2026-10-15 第四階段：當日影子驗收

本報告是上午準備與接續點，**不是已完成 13:25／13:30 的收盤驗收報告**。目前仍在 10/15 上午；當天候選數與首次完整驗證時間尚未取得，必須維持 null，不能拿 10/14 的 6 檔填入今天。

基線 `732025ea67a1e26d1c0741b1c92ce949f5186ea7`；隔離分支 `stage4/20261015-live-shadow`。開始時 main `e8083da77af7c3a575babf39be18addd917906ed`、原修復分支 0707902、舊 stage3 aa3998d，分支清單已保存。沒有修改 main、正式收集程式、正式排程、既有 Worker、DNS、Token／Secret 或歷史 raw。

## 今天能安全執行的真實路徑

1. 正式 MIS 現有 collector 照常執行。上午 Actions 尚未出現今天的 MIS run；13:00 前為 NOT_DUE，不能判成漏跑。GitHub UI 可顯示既有 Run workflow 與歷史執行，沒有看到 disabled 提示；不等於保證今天能準時啟動。
2. repo 已保存 cron-job.org 13:00／13:10／13:18 三個外部觸發設定；GitHub 備援 crons 保留。cron 管理頁本次停在登入畫面，**沒有實際重新確認目前 enabled 狀態**，不能將 10/5 設定紀錄當成本日控制台證明。
3. 已讀取真正 main 的 workflow 與 probe.py。main 沒有 opt-in journal，也沒有第三階段的逐批即時輸出；Artifact 在收集完畢後才上傳。隔離分支有 journal 不代表正式 runner 有它。
4. 本次新增獨立唯讀 runner，讀取 `state/live/2026-10-15.json` 指向的既有 capture run，等待同一 run 的 `mis-probe-RUN_ID` Artifact。沒有呼叫 MIS、沒有 dispatch 第二個 collector，也沒有修改正式 claim。
5. Artifact 可讀後立即驗證 GitHub 外層 digest、記錄實際收到與 fsync 時間，重用既有研究引擎分析，保存真實本次程式算出時間。原始行情事件時間另存，沒有倒填原 runner 的 fsync 或公開時間。
6. 第一份結果用獨立 Artifact `stage4-first-capture-RUN_ID` 保存，不必等影子 job 到 14:30 結束。之後唯讀觀察正式 state/candidates 至 14:30，另存收據。這是 **Artifact 完成後分析**，仍有全市場收集／上傳屏障，尚不是逐批即時串流或匿名公開服務。

## 隔離 workflow 範圍

只在新分支改寫已登記的 `.github/workflows/stage4-validation.yml` 版本，使它能由 GitHub UI 選擇本分支手動執行。main 的同名 workflow 完全不變。新分支版本只有 workflow_dispatch、固定分支 guard、read-only contents/actions 權限、獨立 concurrency `stage4-tail-shadow-*`，沒有 schedule、deploy、contents write、issues write 或 repository Secret 引用。使用的是此測試 job 自己的短效唯讀 GitHub token，不是正式服務 Token。

單一 job 上限 300 分鐘；僅輪詢 GitHub，13:00 前最多每分鐘一次，之後每 20 秒一次；錯誤連續 3 次停止。只讀本 repo 的 state／runs／artifacts，禁止 secrets 與 dispatch URL。正式收集失敗或 Artifact 不完整時，記為未知，不能因 Actions SUCCESS 就當作擷取成功。未啟動第二套全市場 MIS。

## 已準備的程式

- `stage4_observation.py`：區分 NOT_DUE、未看到 run、看到 run 但 capture 未證明；測試、其他分支、其他日期與晚於讀取時間的 run 不算今天正式執行。
- `stage4_shadow.py`：少量官方公司名單連通檢查及動態交易日期的已保存資料分析，不再沿用只適用 10/14 的 replay 日期。公司名單成功仍不代表當天可交易池已核對。
- `stage4_remote_watch.py`：同日唯讀 runner；安全下載不把 GitHub token 帶到 storage redirect、不保存 signed URL，區分外層與內層 ZIP 雜湊。保留每次下載原始檔、回執、分析及時間，錯誤不抹除前次資料。
- `isolated_publication/stage4.wrangler.jsonc`：準備新的 `tw-tail-stage4-20261015-test` 服務、獨立 SQLite DO、無 cron/DNS、live release=false。**尚未部署，也沒有建立新資源或 Secret。**
- 前端僅新增「今日已保存資料驗收｜非逐批即時串流」說明；深色、排序、三狀態與舊介面保持。原正式 docs 完全不動。

## 真實網路與授權狀態

- GitHub connector 與 Actions 簽入頁可讀；普通匿名 API 讀取先前遇到的阻擋仍沒有被本次登入成功解決。登入 GitHub 成功不是匿名公開 GET 成功。
- 本機對兩個官方公司名單端點的嘗試沒有取得完整結果，程序已停止；不宣稱交易所服務故障，也不宣稱今天股票池可用。新 runner 的限時 35 秒 metadata 檢查才是另一個具體測試結果，需讀其 Artifact。
- 富果 Key 尚未設定，官方金鑰頁要求登入；沒有真實 Fugle HTTP。取得 Key 不會解除 LIVE_CONTRACT 或 VERIFIED 閘門。
- Cloudflare 控制台目前在登入頁，新的測試資源未建立。不能宣稱雲端發布或外部手機延遲成功。
- cron-job.org 控制台要求登入；這只阻擋重新查核 enabled 狀態，不表示現有正式排程失效。

富果官方文件與金鑰頁已重新確認：基本會員可申請免費行情 Key，日內 API 60/min、5 WS 訂閱。金鑰頁明示取得 Key 表示同意行情規範；新增 Key、公開轉傳範圍與新的 Cloudflare 服務需使用者確認。不要把 Key 貼在對話、原始碼、HTML 或 Log。

## 必要授權清單（優先順序）

1. **影響獨立成交查核：**富果會員登入、專用免費行情 Key，以及安全設定到新的隔離 Secret 位置；不能挪用既有正式 Secret。登入／申請同意必須由使用者完成必要確認。現有 safe collector 可接 `FAST_FUGLE_API_KEY`，但它不是可直接貼入對話的欄位。
2. **影響公開驗收：**Cloudflare 登入並准許只新增 `tw-tail-stage4-20261015-test`、其獨立 DO 與新測試 writer secrets；不碰既有 Worker、DNS、正式網址。先發合成／非行情 nonce 驗證公開傳輸，行情轉傳範圍未確認前不公開真實來源資料。
3. **僅影響排程控制台確認：**cron-job.org 登入後唯讀確認三個 live jobs 與三個 official jobs，不修改或重測現有 Token。

逐批分析需要正式 collector 提供資料，而 main 目前沒有此路徑。今日先採上述不改正式系統的 Artifact 替代方案；若必須在全市場完畢前發表，正式接入仍須另有最小變更設計與授權。本次未擅自要求或執行合併 main。

## 結果分類與時間規則

完整性來源契約、Worker、私人前端 release 均仍 false。真實 P_before／P_close／VERIFIED 及公開讀取時間未取得時保持 null。必要成交量、嚴格 `<13:25:00`、±3% 未四捨五入門檻、正常／延後／無新收盤成交處理均保持；未知價不補零。

合成測試、10/14 歷史重播、今天真實公司名單、今天正式 capture、今天 Artifact 收到、程式分析、雲端寫入與外部匿名讀取須分開記錄。官方收盤一致不能倒證 P_before；14:50／15:20／17:50 原有核對照舊，影子工作不重跑或修改正式核對。

現在尚未完成今天收盤驗收；正式部署條件仍未滿足。後續同日真實結果以新 Artifact、續作報告與 GitHub Commit 為準。

## 上午實際執行更新

10:01:10 已啟動唯讀影子 run 38668761699（程式 commit 131e59b），10:02 已確認 runner 正在等待正式 capture；不是正式 MIS 收集 run。隔離 Python step 通過，metadata step 失敗但後續等待仍運作。其已完成 preflight Artifact 11943218183 已下載並驗證外層 SHA256 `049c3bc1d4b33b1587d2834ef3370ff9d69f3708e4a27b7b4589dcf68d216a74`。

真實 TPEx 公司名單 HTTP 200，10:01:19.863937 收到、10:01:19.865581 fsync，解析 893 家；這不是今日完整可交易池。TWSE 公司名單在此限時 35 秒測試內沒有保存到回應；不能說正式今日 collector 一定可用，也不能說 TWSE 全站故障。請保留主 collector 自己的重試及動態池核對，未授權前不修改。

本輪本機 376 Python、105 Node、14 Worker 通過。今日實盤收盤與公開瀏覽器驗收尚未發生，沒有使用既有三個模擬瀏覽器結果冒充今天外網成功。已建立今天 13:40 初批檢查及 17:55 盤後整體核對的單次接續任務，不影響正式排程；排定不等於已實際執行或保證及時成功。

上午靜態進度頁已由 Chromium 桌機／手機與 WebKit 手機模擬三設定驗收：無橫向溢出、沒有 JavaScript 例外，顯示「尚無今日選股結果」。這只驗證進度頁，不是當日選股或外部匿名讀取成功。
