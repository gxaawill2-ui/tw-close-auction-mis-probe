# 已完成交接與真實雲端驗收（2026-10-16T13:21:36+08:00）

使用者13:04:36明確同意後，已將既有writer pair安全存入指定Environment的兩個Secret。1 branch / 0 tags限制不變；FUGLE_API_KEY未更動，沒有新增main admission。瀏覽器名稱列表已核對，截圖publisher-secrets-saved.jpg不含明文。本機writer明文暫存已清除。

Run38854028544通過真實私有合成canary與真正publisher發布/匿名讀回。Run38854197791在另一Runner成功取回原私有物件、驗證hash與原寫入時間、測試匯出續傳及拒絕匿名私有讀取。詳兩份acceptance/recovery JSON。

今天另有Run38854461494的兩檔少量真實私有觀察，已ARMED，最多新增6次/60秒、全程30次；有獨立第二Runner恢復步驟。現在仍等13:24～13:35真實時點，不能聲稱真實raw保存已PASS。
原Run38845027079的LocalVault沒有動態補接，新觀察不是它先前暫存的回收。

以下保留交接前的方案和限制供追溯；「待確認」段落是歷史狀態，以本節與CURRENT_HANDOFF為準。

# 私有證據保存與 publisher 交接

## 已確認的外部 API 修復

真實 Runner Run `38851357293` 取得 HTTP 403、Cloudflare code **1010**，17 bytes text/plain。
官方說明：1010 表示瀏覽器特徵被拒絕；Browser Integrity Check 可能阻擋缺少或非標準 User-Agent。

後續 Run `38851428931`、Commit `5418fe7ace7b0082821ddc94d2fc22c7aab71187` 使用誠實的專案 API 身分：

`tw-close-auction-isolated/5.0 (+https://github.com/gxaawill2-ui/tw-close-auction-mis-probe)`

2026/10/16 **12:35:48 台北時間**，`/health` 與 `/data?date=2099-01-02` 均 HTTP 200。
因此已修復這個 Runner 的外部公開 API 讀取。預設 Python 識別觸發 1010 是由錯誤碼與修正後結果推斷；沒有更改 Cloudflare 安全設定、偽裝真人瀏覽器、轉送代理或新增權限。

已把同一識別套入 publisher、私有 Fugle vault、私有 MIS bridge 與 reader。今天正在執行的 Run 是舊版本，不能因此宣稱它已修好。
外部桌機實際更新、真正實體手機仍未驗收；API 200 不等於瀏覽器 PASS。

官方依據：
- https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/
- https://developers.cloudflare.com/waf/tools/browser-integrity-check/

## 現有 writer，沒有重新建立或輪替

- 原 Worker：`tw-tail-stage4-20261015-test`。
- revision：`stage5-20261016-v1`，公開交接資料的雲端保存時間 `2026-10-16T03:08:31.744Z`。
- RSA-OAEP-SHA256 封存已可下載，使用既有本機私鑰成功解封，兩個值皆符合 64 位 hex。
- 明文只在 repo 外的 0700 私有目錄及 0600 檔案。沒有加入 source、公開 Artifact、報告或聊天。
- `stage5_handoff.py` 可重現解封流程，只輸出名稱與成功狀態，不印出任何值。
- 尚未將兩個 writer 值存入 GitHub Environment。FUGLE_API_KEY 未改動。

## 具體待執行的交接範圍

目的地是此 repo 的既有 Environment **stage4-fugle-isolated**，只允許 **stage4/20261016-fugle-probe**。
只新增兩個 Environment Secret：`STAGE5_PUBLISH_TOKEN`、`STAGE5_DECISION_KEY`，內容為上述既有測試 Worker writer pair。
不新增 main admission、不改正式權限、不碰其他 repo、正式 Worker、富果 Key 或正式 Secret。

這會讓指定隔離 workflow 具有測試 Worker 的發布及私有證據讀寫能力；這是持續憑證存取。
瀏覽器操作規則要求在新增這項持續存取前取得當下確認，所以已停在空白 Value 的表單，尚未輸入或提交憑證。
兩個 Secret 必須一起交接；若第一個成功而第二個失敗，不觸發檢查 marker，先補齊配對。

完成後只建立 `stage5_cloud_check.request.json`，觸發既有隔離分支的專用 workflow：

1. 私有合成 canary 寫入及獨立讀回，核對完整物件與 hash。
2. 真正 Publisher 寫入 **2099-01-03 合成空結果**，不是當日行情。
3. 匿名讀取、版本/hash、CORS/no-store、ETag 304、重複寫入、舊版本拒絕、程序恢復。
4. 公開 Artifact 只保存合成驗收結果與時間。工作不帶 FUGLE_API_KEY，不呼叫行情 API。

目前沒有 marker，所以此檢查尚未執行，不能列 PASS。

回滾：先停止未來隔離 publisher 的啟動，再移除這兩個新 Environment Secret；不要動既有 FUGLE_API_KEY。
同一 Worker 內的 writer 不因 routine redeploy 旋轉。若實際遭洩漏才明確輪替 revision；不要為了交接重建 Worker。

## 私有保存與恢復

- 既有 Worker `/private-evidence` 是需 Token + HMAC 的私有資料區，和公開結果 namespace 分開。
- 原始回應先在本機 0600 寫入並 fsync，再經簽章送入私有雲端。
- 雲端物件以 canonical event 的 SHA256 作不可變 id；index 保存 id/raw hash，寫入回條有實際私有保存時間。
- manifest 指向每頁、前後 quote，恢復時重新核對外層日期/id、每個 event hash、原始 bytes hash；不恢復現成 VERIFIED 判定。
- 新 launcher 在任何富果請求前執行私有 canary 寫入及讀回；私有保存失敗，停止後續來源請求，不悄悄退回會消失的本機保存。
- `stage5_archive.py DATE PRIVATE_DIRECTORY` 可從 index 匯出、續傳並驗證；拒絕 repo 內目錄，0700/0600、fsync、原子更新；不輸出 raw、不上傳公開 Artifact。
- 現有私有雲端保留期是 **7 天**，不是永久保存。長期保存應在到期前匯出到已授權的持久私有位置；本機 scratch 不能當持久目的地。
- 程式與私有 hash 恢復測試已通過；真實雲端私有寫入／讀回仍須完成上述憑證交接及專用測試。

## 今天正在執行的任務：不能追溯補接

Run `38845027079` 的固定 source 是 `2443ce0f4028b25e18cf207b8490e212e7d75c2d`。
它在啟動時已選 LocalVault，沒有 writer pair；之後更新 branch 或 Secret 不會改變該程序。
沒有已啟用的遠端 runner 存取／控制通道可安全取回其私有暫存。

因此在「不中斷、不重啟、不公開 raw」限制下，**目前無法將此 Run 的 raw 補送永久私有雲端**。
約 14:29:30 之後工作結束時原始暫存仍會清除。sanitized 診斷／數量／時間會留存，但不能代替原始證據。
不能聲稱現在交接 Secret 可以挽救這個已啟動的程序，不能利用正式資料當指令通道，也不能偷偷另跑一次收集冒充原任務。

今天真正的 VERIFIED 仍是 0；原始證據無法持續還原本身就維持 UNKNOWN 的原因。
