# 本輪續接更新（2026-10-16T12:44:59+08:00）

優先以本節為準；下方是先前檢查的歷史狀態。

- 今日真實 Fugle Run `38845027079`／Job `116793492688` 再確認 in_progress，未停止或重啟。
- Cloudflare 外部 403 已確定 code 1010；誠實專案 User-Agent 後，Run `38851428931` 在 12:35:48 台北時間 health 與 encrypted handoff 皆 200。詳 `cloud-external-recovery.json`。
- 此修正已套入隔離 Python publisher/vault/bridge。沒有修改 Cloudflare 安全設定，也沒有重建 Worker。
- 既有 writer pair 已安全本機解封，未印明文，尚未存入 GitHub；瀏覽器安全規則要求新增持續憑證存取前當下確認，詳 `PRIVATE_STORAGE_AND_HANDOFF.md`。不可把交接當作已完成。
- 新增私有 canary、完整 hash export/續傳、archive failure 停止來源；launcher 必須先通過私有雲端 canary。新程式不影響固定 source 的今日 Run。
- 今日 Run 仍是 LocalVault；更新 Secret 無法讓它動態補接，約14:29:30結束會清除 raw。未找到不改動執行中工作且不公開 raw 的安全取回路徑。此限制不能省略。
- 本機完整 Python 395 項通過。新增 archive/recovery/hash/持續保存失敗測試，無 MIS/Fugle 真實請求。
- GitHub 獨立合成 benchmark Run `38851927830`／Job `116814836213` 成功，2,000 檔、40 批、10 輪、400 筆 journal hash 全驗證；fsync P95 2.104ms、首批最大 5.11ms、on/off 舊輸出逐位元相同，停用不再寫 journal。這不是正式 collector 的實盤延遲。
- 正式 main 因既有 index bot 自行產生新 commit，不能說 main SHA 完全沒變。唯讀比對 3f0b... 與 cee24d...：probe blob 都是64f4e90dde9e17cc3ff5ebf3779ac040e69b8bd4，正式workflow blob都是f4e74ee3b3080a9e6ae0aef2f3e1c759384c9ecb；本輪沒有修改。
- 最新已推送實作 Commit `e14e3eaf260dc09bcbd0799e489972231fe5130b`；最新 reports commit 請看分支 HEAD。
- 專用 cloud publisher 檢查 workflow 已備妥但 marker 不存在，尚未執行；不帶富果 Key、只測合成公開結果和私有合成 canary，不應重開今日 capture marker。
- 13:05、15:35 與11/11提醒沿用原任務，不新增重複排程。外部桌機與實體手機仍未 PASS；VERIFIED=0，正式上線未通過。

# Stage5 接手紀錄 — 2026/10/16 12:13 台北時間

## 最重要：不要停掉或重跑今天的任務

- 隔離真實證據任務已於 11:20:40.715917 啟動，目前 GitHub 回報 in_progress。
- Run `38845027079`；Job `116793492688`。
- 固定使用 Commit `2443ce0f4028b25e18cf207b8490e212e7d75c2d`。後續程式提交不會中途替換此任務。
- 分支 `stage4/20261016-fugle-probe`；既有 Environment `stage4-fugle-isolated`；Secret `FUGLE_API_KEY`。
- 沒有第二套 MIS 全市場擷取，沒有改正式網站、main、正式 workflow 或排程。
- 今天正式 MIS 在 12:11 的 GitHub 觀測中尚無 matching live Run。既有外部設定檔記錄 13:00 主觸發、13:10／13:18 備援；該設定檔不是今日實際觸發證明。
- 已安排 13:05 唯讀檢查正式 MIS 是否啟動；禁止為此自動重跑或另啟正式擷取。

## 今日真實擷取計畫（不能提前聲稱通過）

控制樣本只有 2330、6488；不是 ±3% 策略候選名單。
使用同一個共享 Source，總計最多 160 次 Fugle 請求，請求起始間隔至少 1.3 秒；401／403／429 停止。

| 階段 | 真實目標時間 | 範圍 |
| --- | --- | --- |
| 初始化 | 已於 11:20 完成 | 每檔 quote → 1 頁 200 筆 → quote |
| 截止前 | 13:24:40 | 保存當時實際回應；錯過時段就標記 missed，不補造 |
| 截止後 | 13:25:08 | 每檔最多 16 頁，嘗試完整日內筆數／成交量一致性 |
| 正常收盤 | 13:30:10 | 查實際成交、收盤旗標及截止區間 |
| 延後收盤 | 13:33:10 | 查延後收盤及試撮差異 |
| 穩定性 | 13:35:10 | 再次檢查，維持不足為 UNKNOWN |

正式 Artifact 若在 13:40 前可取得，既有唯讀 observer 會匯入實際原始證據，再計算 MIS 研究候選並逐檔排隊查核。匯入時間是真正的現在，不是當時的發布時間。
會記錄來源 Artifact 的接收時間、正式擷取結束時間與首次實際研究計算時間。

## 已觀測的真實結果

- 2330：11:20:46，1 頁、200 筆。報價在分頁期間改變，完整日內筆數未證明、尚無收盤最終性，因此 UNKNOWN。
- 6488：11:20:47，1 頁、200 筆。另有同微秒不同價格排序疑義及 quote head 衝突；盤中報價變動，UNKNOWN。
- 兩檔均不構成 VERIFIED；不是今日 ±3% 候選數。沒有把 Fugle 價格、成交量、序號或 API Key 寫入公開紀錄。

## 證據保存的實際限制

- 當前 Run 的模式是 `RUNNER_PRIVATE_TEMPORARY_ONLY`；raw 位於 checkout 之外的私有暫存，0700／0600，不列入任何公開 Artifact。
- 原始資料會在此 Run 結束時被清理，不能宣稱工作結束後仍可還原。今日永久私有 raw 保存尚未達成。
- 唯一上傳的 Artifact 是 `stage5-sanitized-report-38845027079`，只含診斷／數量／時間／hash 等安全資料及 MIS 研究輸出。
- `stage5_audit.py` 把無法永久還原列為 `PRIVATE_ARCHIVE_UNAVAILABLE_RUNNER_COPY_ONLY`，不因此放行驗證。
- 完整性 source contract、獨立排序及真正收盤最終性仍未放行，Worker 也維持 `ALLOW_LIVE_VERIFIED=false`。

## 已完成的隔離開發

- `stage5_runtime.py`：禁止轉址、同一請求預算、節流、bounded retry、私有 raw、私有雲端 receipts、manifest hash 恢復、公開 allowlist、兩個 worker 的逐檔 fair queue、過期結果丟棄。
- `stage5_session.py`：journal → 即時計算 → 逐檔查核 → 版本保護 → 背景 signed publisher；MIS 變動撤回／降級，不等全市場完成。提供 CLI 外的可測 Session。
- `stage5_audit.py`：時間、排序、分頁、quote bracket、全日筆數與量、cumulative volume、收盤／延後／無新收盤診斷。經驗相等不等於完整證明。
- `stage5_launcher.py`：準備好的共同 runner shadow，等待正式自己的 universe／journal；目前沒有接上正式 workflow。
- `stage5_journal_bridge.py`、`stage5_remote_journal.py`、`stage5-mis-bridge.mjs`：另一個較窄寫入權限的 bridge 草案；沒有 bridge Secret、沒有啟用。
- 隔離 UI：沿用深色、手機、排序；總研究候選包含尚待確認者，另列 VERIFIED／不足，顯示全部價格、量與時間欄位；按日期輪詢並防止舊版本覆蓋。
- Key 更換檢查 workflow 與作業說明已備妥，不會在本次提交時再跑連線測試。

主要隔離程式已推送 Commit `1eb9c200ba4c9802587fb8935a3c69768dd8031d`；本接手檔及最後提案／測試紀錄會在後續 reports commit 保存，接續時先讀取該分支最新 HEAD。

## Cloudflare：已部署不代表外部驗收通過

- 仍是同一個 Worker `tw-tail-stage4-20261015-test`，沒有重建，沒有動其他 relay。
- 已接受 source Commit `0ce8a58df9549651e45a74bdd2a5f529c4b8ddf7`。
- Build `cfa1a0d9-7f40-4373-95d5-8512c15c7003`；11:28:31 成功；Worker version `6fab5555-791f-4fab-9dbf-4e600624cd0c`。
- 私有證據與公開結果不同 namespace；私有端點需 Token，寫入需 HMAC，公開路徑拒絕 raw／tick 證據。
- Writer 改為持續保存，例行重新部署不會重新隨機產生；初次交接採公開 RSA Key 封存，不在 source 或 log 顯示明文。
- 兩個 GitHub writer Secret 尚未完成交接，今天 Run 沒有 publisher 憑證，因此不會擅自發布。
- 11:37 的真實 GitHub runner 前置檢查：health 和封存交接資料均 HTTP 403，Server Cloudflare；沒有觀測到 challenge 頁標記，不能臆測原因。
- 雲端瀏覽器首次讀取被 client 阻擋，之後工具明確回報 URL 安全政策阻擋並禁止繞過。停止該瀏覽器路徑，不得改用代理或其他表面冒充外部瀏覽器 PASS。
- Desktop 實際更新：未取得；真正外部實體手機：未取得。禁止把模擬手機當實體測試。
- 初次 RSA 私鑰只在本輪私有 scratch 暫存，沒有推入 repo。若之後已遺失且交接仍未完成，只能在同一個測試 Worker 明確旋轉隔離 writer revision；先確認無運作中 publisher，不能重建富果 Key 或動正式 Secret。

## 正式整合必須另外批准

先讀 `FORMAL_INTEGRATION_REVIEW.md` 與 `proposed/production-journal.patch`。
正式 main 的 journal hook 根本尚未存在，不能只加環境變數便宣稱整合完成。
提案包含新的 callback、獨立 journal 模組及 workflow 背景程序；Environment main admission 擴權必須先批准及驗證。
不要套用整份舊 snapshot 覆蓋 main，不要合併隔離分支全部檔案，不要重跑今天正式 collector。

## 提醒與後續報告

- 已設 2026/11/11 到期提醒；Key 到期是 11/14 00:00 台北時間，11/13 結束前更換並驗證，免費會員方案本身不是這天到期。
- 已設今天 15:35 唯讀檢查 Run 與既有官方核對的報告任務；不會自動修改或重跑正式 MIS。
- 下一次先核對當前台北時間、此 Run／正式 Run、最新遠端 HEAD 和今日 sanitized report，禁止重開發或補造前時點。

當前答案：研究與連線有真實進展，但沒有任何真正 VERIFIED；13:35～13:40 找出並公開可信股票仍未證明，正式部署條件未通過。
