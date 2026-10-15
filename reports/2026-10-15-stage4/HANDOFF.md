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
