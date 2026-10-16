# 13:24 真實證據保存確認（2026-10-16T13:25:32+08:00）

Run38854461494已於13:24:03.194922保存2330、13:24:07.214021保存6488；兩筆safe log都確認private_evidence_recoverable_after_job=true及獨立manifest id。
詳real-private-pre-cutoff-observations.json。這是新增真實回應的私有保存，不是合成資料，也不是原Run暫存的回收。
兩檔仍UNKNOWN、VERIFIED=0；13:25之後最後成交／收盤／不同Runner真實raw恢復仍待後續時點。

# Stage5 最新接手紀錄 — 2026-10-16T13:20:25+08:00

本檔取代先前 12:44 版本。先確認台北時間與下列 Run，再做唯讀檢查；不要重啟任務或重新開發。

## 已完成且有真實雲端證據

- 使用者 13:04:36 已同意特定 writer 交接及隔離驗收。兩個既有測試 Worker writer Secret 已於 13:05 安全存入 GitHub Environment `stage4-fugle-isolated`：`STAGE5_PUBLISH_TOKEN`、`STAGE5_DECISION_KEY`。
- Environment 仍只允許 `stage4/20261016-fugle-probe`，1 branch / 0 tags。沒有擴大 main admission，FUGLE_API_KEY 仍是 10:42 版本，未修改。
- 本機明文 writer 交接暫存已清除；瀏覽器明文變數已清除。只保留 repo 外原 RSA 私鑰及已公開的封存資料，未上傳任何明文。
- Cloudflare 403 的數字原因是 1010。誠實專案 User-Agent 已在外部 Runner 恢復 200，沒有更動 Cloudflare 安全設定或繞過瀏覽器政策。
- Run `38854028544` / Job `116821363568`：13:06:22.209 私有合成 canary 寫入，13:06:22.821 公開合成結果寫入，13:06:23.114 匿名讀回同 version/hash；ETag 304、no-store/CORS、重複寫入、舊版本拒絕及程序重建通過。
- 不同 Runner Run `38854197791`：13:08:18 取回前一已完成 Runner 的私有合成物件，核對原保存時間與 hash、private export/續傳；匿名 private GET=401；以遠端版本繼續合成發布並匿名讀回成功。
- 詳 `cloud-publisher-acceptance.json`、`cloud-new-runner-recovery.json`。這些是合成傳輸驗收，不能當成真實股票、真實候選發布或手機 PASS。
- 同一 Worker `tw-tail-stage4-20261015-test`，部署 source 仍是 `0ce8a58df9549651e45a74bdd2a5f529c4b8ddf7`。沒有重建 Worker，沒有動正式 relay。live VERIFIED gate 仍 false。

## 今天正在執行：都不要停止或重啟

1. 正式 MIS **38853538676** / Job **116819837674**，13:00:40 啟動、Python 13:01:01；今日股票池 **1967**，目前等待正常 preclose。此數字來自今日正式 state，不是舊資料。
2. 原富果真實任務 **38845027079** / Job **116793492688**，source `2443ce0f4028b25e18cf207b8490e212e7d75c2d`，11:20 啟動。仍採 LocalVault，沒有動態換成新 Secret。13:24:40、13:25:08、13:30:10、13:33:10、13:35:10 控制檔仍照原程式進行。它的 raw 約14:29:30結束時會清除，不能宣稱補接成功。
3. 新增少量私有真實控制觀察 **38854461494** / Job **116822705363**，source `c68a913905c6acdf302d7af8377d73f43df4308a`。13:11:23.605898 已通過私有 canary 並 ARMED。只處理2330/6488兩檔固定控制樣本；不是策略候選。真實 raw 每筆先私有 fsync，再送既有需 Token/HMAC 的私有 vault，保留7天。
4. 既有正式 MIS Artifact 研究發布器 **38854918750**，source `6563dfbfe62a77f77b8790640a13931d1809ceac`。只讀正式 Run 38853538676 的既有 Artifact，不發 MIS/Fugle 請求、不帶富果 Key。檔案在13:40前可用才計算並簽章發布到隔離 Worker；所有股票只能研究/UNKNOWN，不能 VERIFIED。

第3項每60秒最多 **6次新增實際 Fugle請求**（重試亦計入），全程最多30次。原任務以1.3秒間隔最多47次/分鐘，合計上限53次/分鐘，低於免費60次。原任務最多160次，加上此新控制任務最多190次；沒有其他 Fugle smoke 啟動。

第3項的目標時點：13:24:00、13:25:15、13:30:15、13:33:15、13:35:15。各期每檔只1頁200筆及前後quote；晚到就 missed，不補造。完整日內成交筆數不一定可證明，維持UNKNOWN。沒有改原任務，也沒有第二套MIS全市場擷取。

第3項完成後 workflow 會在**另一 Runner**用 sanitized manifest id 取回真實 raw，重新驗 hash、日期、security，輸出 sanitized 恢復報告。raw 不進 Repo、公開 Artifact、公開 Worker 或 log。預計13:35之後才可驗收，現在不可預填 PASS。

第4項依舊受完整正式 Artifact 的等待限制；不是即時 journal，也不是歷史重播發布。真正首次研究/寫入/匿名讀取時間寫在 `publisher-day.json`；2099年合成測試時間不能代填。若已有當日公開結果，這個一次性 observer 保留原結果，不用新版本號覆蓋別人的較新結果。

## 取結果的方法

- 第3項完成後，使用 GitHub 已完成 job logs 或安全 Artifact：`stage5-private-controls-sanitized-38854461494`、`stage5-private-controls-recovered-sanitized-38854461494`。只讀 sanitized reports，不把富果 raw 下載至公開目錄。
- 第4項完成後，`stage5-mis-research-publisher-38854918750` 包含 `publisher-day.json` 與 MIS-derived research view。依實際回條填驗收時間。
- 原任務完成後，`stage5-sanitized-report-38845027079` 有完整控制診斷、研究候選與錯誤。原 raw 不能追溯回收；新的私有觀察是新增證據，不是原暫存的恢復。
- Source contract（完整性、同微秒排序、筆數/量語意、收盤最終性）仍未釋出；HTTP200/同價/合成PASS不能放行VERIFIED。

## 隔離程式與測試

- 實作最新有效 Commit `6563dfbfe62a77f77b8790640a13931d1809ceac`；接手/提案/測試報告另看分支最新HEAD。
- Python完整399項通過；最新包含 rolling6/min、30 total、私有恢復、manifest hash、研究發布不誤升VERIFIED／矛盾撤回。Node先前117項通過，這輪沒有改JavaScript。
- 獨立Runner benchmark Run38851927830：2,000檔/40批/10輪/400事件hash全驗；fsync P95=2.104ms、首批最大5.11ms、開關journal舊raw逐位元一致、停用不再寫journal。不是正式collector實盤延遲。
- `patch-rollback-check.json`：正式blob基準下，在暫存副本實際apply、反向apply；回復原始bytes一致，新模組亦移除。沒有套用正式。
- `proposed/production-journal.patch`與YAML提案已將shadow固定到`c68a913905c6acdf302d7af8377d73f43df4308a`，含403修正與強制私有canary，不能再用舊1eb版本。

## 正式保護／待批准

正式 main 的 probe blob仍64f4e90dde9e17cc3ff5ebf3779ac040e69b8bd4，workflow blob仍f4e74ee3b3080a9e6ae0aef2f3e1c759384c9ecb。main會由既有bot更新state/index，不能說main SHA不變。
未改正式網站、collector、workflow、cron或Token，未dispatch或重跑正式MIS。
真正即時逐批研究仍需正式journal hook與下一交易日影子驗收；main Environment admission、正式workflow/collector修改、正式部署都須另行批准。
詳 `FORMAL_INTEGRATION_REVIEW.md`；本次的「同意」只涵蓋隔離writer交接及驗收，沒有批准正式整合。

## 剩餘限制與後續

- VERIFIED=0，P_before/P_close完整獨立證明仍不足，正式上線未通過。
- 真正桌機瀏覽器更新與實體手機未PASS；Worker瀏覽器路徑先前遭政策阻擋，不得用代理／模擬冒充。外部API實測另有證據。
- 保留正式GitHub Pages網址；不公開富果原始價格、量、逐筆資料或Secret。
- 15:35既有唯讀報告任務已更新，會檢查上述全部Run和既有官方核對；不新增正式排程。
- 11/11已設Key提醒。到期11/14 00:00台北時間，11/13結束前按KEY_ROTATION.md更換，不重新申請當前Key。
