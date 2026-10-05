# 一次性設定 cron-job.org 主排程

本檔只有公開 endpoint 和佔位符，沒有 PAT。不要把 Token 貼進 Work、Issue、repo、截圖、log 或 workflow。Token 只由本人填入 cron-job.org 的 Authorization header。

## 1. 開啟 GitHub Pages（一次）

https://github.com/gxaawill2-ui/tw-close-auction-mis-probe/settings/pages

Build and deployment → Source → **Deploy from a branch**；Branch → **main**；Folder → **/docs**；Save。

等待 GitHub 內建 Pages build 完成後，開啟：

https://gxaawill2-ui.github.io/tw-close-auction-mis-probe/

這一步需要 repository 的管理權限，不能用僅 Actions 權限的外部 PAT 代做，也不應擴張外部 PAT 權限。狀態頁每 60 秒讀取 public repo 的 state；不需要重新部署才能看到 state 變更。

## 2. 建立最小權限 fine-grained PAT（一次）

https://github.com/settings/personal-access-tokens/new

- Token name：`mis-cron-dispatch`
- Resource owner：`gxaawill2-ui`
- Expiration：自行選擇，例如 90 天；到期前須更新 cron-job.org 的 Header。不要用永久 Token。
- Repository access：**Only select repositories** → **tw-close-auction-mis-probe**（只選這一個）
- Repository permissions：**Actions → Read and write**
- Metadata 的 Read-only 是 GitHub 自動附帶；其他 permissions 全部維持 No access。
- 不加 Contents、Issues、Pages、Administration、其他 repo 或組織權限。
- Generate token；本人複製到下一步的 cron-job.org Header。不要回傳 Token 給 Work。

官方 Create a workflow dispatch event 要求 Actions write；Pages 首次開啟是另外的管理設定，不是外部排程 Token 的用途。

## 3. 建立今天的外部 dry-run Test

登入 https://console.cron-job.org/ → Cronjobs → Create cronjob。

先建立名稱 `MIS external dry-run acceptance` 的測試工作，**保持 disabled**，只用 Test run；不要讓 dry-run 取代 live 主排程。

URL：

```text
https://api.github.com/repos/gxaawill2-ui/tw-close-auction-mis-probe/actions/workflows/twse-mis-probe.yml/dispatches
```

Advanced → Request method：**POST**。

Headers：

|Name|Value|
|---|---|
|Authorization|`Bearer ` 加上本人剛建立的 Token（中間有一個空白）|
|Accept|`application/vnd.github+json`|
|Content-Type|`application/json`|
|X-GitHub-Api-Version|`2022-11-28`|

Request body：

```json
{"ref":"main","inputs":{"mode":"dry-run","trigger_source":"cron-job.org-test"}}
```

Timezone：**Asia/Taipei**。開啟保存 response／execution history；不要分享含 Authorization header 的截圖。按 **Test run**（或介面顯示的 Run now）。

GitHub 接受請求可能回 HTTP 204；它只證明接受 dispatch，不證明 runner 已啟動。必須在下列頁面看到 **新的 workflow_dispatch run id**，宣告來源 cron-job.org-test、mode dry-run，且建立時間對應這次外部 Test：

https://github.com/gxaawill2-ui/tw-close-auction-mis-probe/actions/workflows/twse-mis-probe.yml

Work 要核對 runner、Python、MIS 回傳、Issue/state 更新及 `mis-probe-<run_id>` Artifact。回覆「已按 Test」和非機密的 run id／cron-job.org execution 時間即可，**不要貼 Token**。

本 repo 自己的 push dry-run 和 dispatch-safety workflow 不是外部 Test，不能冒充這項驗收。

## 4. 建立三個正常 live 主排程

另建三個 enabled 工作，URL、POST、Headers 完全相同，Body 改為：

```json
{"ref":"main","inputs":{"mode":"live","trigger_source":"cron-job.org"}}
```

Schedule → 自訂／Custom；Timezone **Asia/Taipei**；只選週一至週五。

|名稱|台北時間|若介面使用五欄 Cron expression|
|---|---|---|
|MIS live primary|13:00|`0 13 * * 1-5`|
|MIS live backup 1|13:10|`10 13 * * 1-5`|
|MIS live backup 2|13:18|`18 13 * * 1-5`|

若介面提供 Month / Day / Hour / Minute / Weekday 分開選擇：Month 和 Day 選全部；Hour 選 13；Minute 分別選 0、10、18；Weekday 選 Monday–Friday。不要設成每 10 分鐘，也不要設在 UTC 的 13 點。

GitHub runner 會重新核對官方休市日，提早啟動後自行等待 13:24:50、13:27:00、13:28:15、13:32:30、13:33:20。晚於 13:24:45 才啟動就不補抓。

主 live run 與後續重複觸發共享 concurrency，且在 repo 原子 claim 當日 execution。已有 claim／preclose evidence／完成資料／當日封鎖時，後續 run skip，不覆蓋 raw Artifact。不會因 GitHub Cron 失靈就依賴 ChatGPT 喚醒。

原 GitHub schedule 保留第二層備援，但外部設定必須在 cron-job.org 帳號中真的保存，僅這份程式碼無法代替外部排程。

## 完成的證據

1. 三個 live cron jobs enabled，排程時區與時間正確。
2. cron-job.org Test request 成功，對應新的 GitHub workflow_dispatch run id。
3. 該 run runner 真正啟動、Python 執行、MIS dry-run 回資料、Artifact 與 state/Issue 更新成功。
4. Pages URL 能開，今日狀態與 state 一致。

在以上證據齊全前，`state/external_scheduler.json` 維持 `PENDING_USER_SETUP`，不能宣稱已完全自動完成。

## 官方文件

- https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event
- https://docs.github.com/en/rest/pages/pages#create-a-github-pages-site
- https://docs.cron-job.org/creating-cron-jobs.html
