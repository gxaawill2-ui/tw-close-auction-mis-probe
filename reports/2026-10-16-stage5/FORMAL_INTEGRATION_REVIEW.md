# 正式串接最小修改提案（尚未套用）

## 為何需要正式變更

2026/10/16 已唯讀核對最新 main：`probe.py` blob `64f4e90dde9e17cc3ff5ebf3779ac040e69b8bd4`。
正式 collector 沒有 `MIS_FAST_JOURNAL_DIR` 接口，仍按批號等待 future；隔離分支的改善尚未合併。
正式 workflow 只在完整擷取結束後上傳 Artifact，其他 runner 無法逐批讀取當下資料。
所以今天只能等待既有 Artifact 後再分析，不能聲稱已做到第一檔出現即發布。

## 具體可審閱補丁

`proposed/production-journal.patch`，共 118 行 diff；只涉及：

1. `probe.py`：啟用時依完成順序保存批次；最終舊檔仍按原批號排序。journal 初始化或寫入失敗就停用 journal，正式擷取照常繼續。沒有新增 MIS 請求或改變策略。
2. 新增獨立標準函式庫模組 `stage5_capture_journal.py`：僅寫入專用 RUNNER_TEMP 子目錄，raw 與 journal 分別 fsync；時間在 raw 實際保存後記錄。不能寫 docs 或 state。
3. 正式 workflow：選用的 journal 路徑、固定 Commit 的隔離程式 checkout、背景 shadow。正式 collector 的執行命令與既有 cron 不變。

隔離 shadow 固定程式 Commit：`1eb9c200ba4c9802587fb8935a3c69768dd8031d`。
補丁只是提案；實際套用前仍須重新核對最新 main，不可用這份檔案整份覆蓋新版本。

## 必須另行取得同意的設定

- 允許 main 使用 `stage4-fugle-isolated` Environment；目前只允許指定隔離分支。這會擴大 main 對該 Environment Secret 的存取範圍。
- 完成同一個測試 Worker 的 writer 憑證交接，將 `STAGE5_PUBLISH_TOKEN`、`STAGE5_DECISION_KEY` 安全保存於指定 Environment。不要更動其他專案或既有正式 relay Secret。
- 先於未啟用狀態驗證上述 Environment admission，才可套用綁定該 Environment 的正式 workflow；否則可能讓正式 job 被環境規則卡住。
- 只在另一個已確認交易日啟用 `STAGE5_SHADOW_ENABLED`。不能更換今天正在使用的程式、重跑今天正式 MIS，或補造已錯過的邊界。

## 風險與限制

- 每批增加兩次本機 fsync；磁碟停頓仍可能拖慢 callback。獨立 GitHub Runner 的合成測試已量測 P95 2.104ms、首批最大 5.11ms，正式正在執行的 runner 尚未量測。寫入失敗的測試已確認不會中止正式擷取。
- 共用 runner 的背景程式可能在正式 job 結束時被清理；這份最小補丁不能承諾獨立運作到 14:30。要達成完整續跑，須另行審閱私有 journal bridge 與獨立 consumer；其隔離程式已備妥但未啟用、未新增 bridge Secret。
- Source raw 只能寫私有暫存及授權私有端點，不能落入正式 `results/` 上傳範圍。
- 測試 Worker 的外部 Runner API 已恢復 HTTP 200，瀏覽器實際更新尚未驗收；publisher 憑證交接及私有雲端寫入／讀回通過前，不應啟用正式串接。
- 完整性、同微秒排序及收盤最終性尚未實盤證明；`ALLOW_LIVE_VERIFIED=false` 與 source contract release 維持關閉。這份提案不會放行 VERIFIED。

## 已執行的提案測試

三項測試使用合成資料與假的 fetch，沒有發送 MIS：

- 快批次先保存，慢批次不阻塞 journal；舊輸出仍維持原批號順序。
- 模擬磁碟寫入失敗，正式擷取仍完成並保留舊 raw 檔。
- journal 只能寫入專用 runner 暫存目錄，權限 0700／0600，hash 與保存時間可驗證。

## 停用與回復

停用 `STAGE5_SHADOW_ENABLED` 可使 journal 與背景 shadow 不再啟動，舊 collector 路徑保留。
若 workflow 的 Environment admission 尚未驗證，不能先套用 workflow 補丁。
需要完全回復時，只撤回此補丁涉及的三個檔案變更；不撤回當日正式資料、歷史資料或其他人的提交。

本提案須使用者另行批准後，才可改正式檔案與權限；本輪均未實施。

新增量測：`journal-benchmark-github-runner.json` 保存 Run 38851927830 的 2,000 檔合成測試、10 輪 on/off/on 結果。40 批最終舊 raw 逐位元一致，停用不再寫 journal；沒有 MIS/Fugle 請求。此驗證沒有套用正式補丁。
