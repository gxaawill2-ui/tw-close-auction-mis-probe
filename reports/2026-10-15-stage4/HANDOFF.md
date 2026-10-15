# 第四階段最新接手紀錄（10/15下午）

先讀 RESUMED_REPORT.md、recovery-status.json 與分支最新head。以下狀態優先於所有上午紀錄。

正式run38684465791於13:00:44啟動，核心完成、CAPTURE_PARTIAL。1967檔、1947可初篩、20未完整；10研究、VERIFIED=0。

影子run38668761699已在14:30結束，整體failure來自上午metadata step；Artifact分析、後續觀察成功。13:34:49.019是真正研究運算完成時間，沒有獨立逐筆或手機公開讀取。不要重啟同日MIS。

三份原始Artifact已下載並驗SHA256；recovered/artifact-index.json記錄ID／hash／到期。原ZIP及raw在本機recovered與GitHub Artifacts，部分大檔不納Git。14:50官方1075MATCH／1MISMATCH／891UNAVAILABLE；TPEx空表，非候選7818價差。補充比對最後採用研究收盤：3266／3593／8101與TWSE一致，不升級VERIFIED。不額外dispatch核對，僅唯讀看既有15:20／17:50。

Cloudflare舊版aa0470b build成功，version738acbcd-d686-4273-bace-1394f91327a4；本次/health HTTP200。root=/、隔離分支不變。新config含合成測試頁，推送僅部署新test Worker。整套雲端驗收需在Settings→Builds把Deploy command改為node isolated_publication/stage4-cloud-deploy.cjs；當前命令仍是舊npx wrangler deploy。不能假稱推送script就已執行自動驗收。代理Cloudflare瀏覽器是登入頁，使用者自己的瀏覽器先前已登入。

腳本在Build內產生驗收專用keys，只送stdin、不入repo／聊天，精確target guard，2099-01-01合成資料。真實雲端最後/data會有去密鑰transport_acceptance；核對nonce/version/sha/commit與build log。不能拿本機transport-local.json當雲端。驗收keys不是正式publisher的長期交接。

本機測試轉接壓縮標頭已修；桌機及iPhone尺寸Chromium PASS，WebKit缺OS libraries且安裝受系統權限限制。實體手機延遲null。

富果docs/key已重新確認基本用戶生效、Key清單空；新Key對話框填好tw-tail-stage4-isolated-20261015、到期2026-11-14，未按確定。頁面明示取得金鑰等同同意行情使用規範，需處理最後條款確認。先安排安全隔離Secret目的地，不能將Key貼聊天／repo或讀正式Secret。取得時間在14:30後的證據不得冒充13:40前。

授權仍有效：隔離研究開發安全推送、新test Worker／儲存／測試keys及專用免費富果Key。未授權main合併、正式部署、正式collector／排程／既有Worker／Secret變動或第二套MIS。推送精確隔離分支，expected_sha、force=false、commit帶[skip actions]。保留其他未提交檔案。

376Python、105既有+3新增前端部署檢查通過；最新部署3項log在cloud-preparation/deploy-test-results.log。所有測試類別分開標示。

## 上午舊紀錄（保留作歷程，不可作最新狀態）

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


## 11:55 Git 連接已完成（覆蓋前段 root／command 指引）

使用者截圖確認新test Worker已連本repo，Production branch=stage4/20261015-live-shadow，root=/，build空，Deploy command=`npx wrangler deploy --config isolated_publication/stage4.wrangler.jsonc`。Preview command=no-op；已指示取消Enable Preview builds，但尚無保存後關閉狀態證據。不要再用前段root=isolated_publication搭配新full-path命令，否則路徑重複。畫面顯示需要push第一筆commit啟動build。本次bootstrap使用GitHub官方[skip actions] marker，避免啟動正式Actions共用concurrency；不是變更正式workflow。CF是否建置以實際check為準。

詳細部署設定與唯讀驗收規則見isolated_publication/STAGE4_DEPLOYMENT.md。根路徑/在新程式是404 NOT_FOUND，測試用/health及/data?date=2026-10-15；健康成功不代表私有write/read或逐檔驗證成功。observer38668761699在11:55再次connector確認等待正式capture，未重跑MIS。
