# 第四階段 10/15 當日續作

先讀 README。基線732025e，新分支 `stage4/20261015-live-shadow`。禁止main merge／正式部署／正式排程、collector、Token、Secret、既有Worker、DNS、歷史raw變更；不可再啟動全市場MIS。

現在是上午準備，沒有今天收盤候選。`observations/actions-latest.json` 是真正 connector 收到時刻的觀察，NOT_DUE不能判漏跑；`preflight/observed-main/`為開始時真正main檔案，不是本分支改寫版本。

main目前沒有journal，Artifact只在正式capture結束後可下載。`stage4_remote_watch.py`會用自己job的唯讀GitHub token等待既有state/live當天runid及同runArtifact，驗digest／實際receive／fsync後動態日期分析，再上傳獨立first-capture Artifact；之後follow直到14:30。不能把事件時間當首次程式觀察時間，不得用10/14的6檔代替10/15。

新分支的stage4-validation.yml是已登記manualworkflow的分支版本，只有精確分支可跑、沒有schedule或write／deploy權限，concurrency獨立。**不能選main跑同名舊工作流程**。若已有本分支正在跑，不再重複啟動；唯讀觀察其first-capture及order-cutoff artifacts。GitHub run id與實際手動啟動證據另存本目錄runtime-start.json；若沒有，表示尚未確認啟動，不可假稱正在執行。

下次Work先查GitHub分支最新與Actions，不使用舊sha覆蓋其他修改；safe push用expected_sha force=false，所有commit skip ci。本機測試不是GitHub CI成功。以最新測試log及runtime artifacts為準。

下載正式artifact：用 `github_fetch_workflow_run_artifacts` 列出，再 `github_download_workflow_artifact`。保留外層archive及GitHub digest、實際收到與fsync時間。`stage4_shadow.py analyze ARCHIVE 2026-10-15 NEW_DIR --artifact-received-at ... --artifact-persisted-at ...`；內層digest不要拿外層digest驗。日期、event receive晚於程式start、hash、接收／保存倒序都拒絕。不要執行固定DAY=10/14的stage3_replay來冒充今天。

第一份分析保守採OFFLINE_REPLAY欄位但provenance.kind=SAME_DAY_SAVED_CAPTURE_ANALYSIS，前端明示今日已保存資料驗收；沒有source raw independent proof時正式0。不是歷史10/14重播，也不是逐批live公開服務。

富果、Cloudflare、cron管理頁都需登入，目前無專用Key。不要讀其他服務Secret。先完成專用富果Key安全授權才可少量候選查核；來源語意未實證不能放行。Cloudflare僅準備stage4.wrangler.jsonc，未部署。用合成nonce先做公開匿名GET／私有POST、回執／版本測試；轉傳許可未確認不要發布真實行情。

本機官方metadata未取得完整結果，不將其叫交易所故障；已準備GitHub runner限時35秒的另一環境測試。測試請用新輸出目錄，保留raw與所有失敗紀錄。原始歷史檔與正式docs／state等不改。

應在今天13:40取得first-capture結果時，回報run是否實際啟動、today研究數／unknown／正式數、事件/收到/保存/分析各時間，公開write/read未知保持null。17:55再唯讀看既有14:50/15:20/17:50核對結果，不觸發新officialworkflow。若下游授權仍缺，繼續保存證據，不承諾達標。


## 10:18 授權後續作與瀏覽器中斷

使用者已同意專用免費富果行情 Key、新隔離環境 Secret，以及新 Cloudflare 測試 Worker `tw-tail-stage4-20261015-test`／SQLite DO／測試寫入憑證與必要登入。不要重問相同授權；正式變更仍未授權。詳見 `authorization-progress.json`。

富果已經由使用者安全選擇 Google 與帳戶，送出一般登入後 callback／首頁空白，尚無正面登入成功證據。沒有取得 Key、沒有建立 Secret。Cloudflare 最後可見是登入頁，未登入、未建立服務。控制連線及一次 reset 恢復均 300 秒逾時，因此停止重試；這不是證明服務封鎖、密碼錯誤或授權不足。不要請使用者在聊天貼任何憑證。

GitHub connector 確認原影子 runner 仍在等待正式 capture，未重啟或新增 MIS。13:40／17:55 既有接續任務維持；下一 Work 先讀本段與 JSON，恢復瀏覽器後使用新鮮狀態檢查登入，再做安全 Key 保存與合成 nonce 雲端驗收，所有真實公開寫入／外部讀取時間仍未知。


## 11:43 手動 Cloudflare 進度（優先於前段舊狀態）

富果11:11 UI已正面確認基本用戶生效，API Key清單空，尚無Key。使用者在自己瀏覽器完成 Cloudflare Google登入，建立獨立 `tw-tail-stage4-20261015-test`；Hello World公開頁面由使用者截圖確認。代理瀏覽器讀取同網址為ERR_BLOCKED_BY_CLIENT，非來源bot封鎖證據。不可稱完成外部手機延遲驗收。

使用者已從本repo的 `isolated_publication/worker.mjs` 複製完整121行到Dashboard，畫面顯示04e6e68c Active／Ready。沒有secret值進聊天。Bindings下拉只有正式 `tw-index-events-relay_DispatchGate`，已明確禁止選取，尚未綁定任何物件。只貼程式並不建立SQLite namespace；此處先前UI指引漏了migration初始化，必須補上，不能重用正式namespace。

已備妥stage4.wrangler.jsonc（名稱精確匹配新test Worker、SelectionStore SQLite migration、SELECTION binding、ALLOW_LIVE_VERIFIED=false）。下一步使用test Worker自身Settings > Builds連接既有repo，分支僅stage4/20261015-live-shadow、根目錄isolated_publication、deploy command `npx wrangler deploy --config stage4.wrangler.jsonc`。最後連接／啟用前核對分支及目標；不要使用預設main或預設stage3 wrangler.jsonc，不啟用其他分支預覽。不可改正式GitHub Actions或既有Worker。若GitHub授權要求擴大到所有repositories，改只選本repo，由使用者確認授權。寫入secret及真正發布仍未完成。
