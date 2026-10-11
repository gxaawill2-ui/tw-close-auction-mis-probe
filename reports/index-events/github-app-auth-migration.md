# GitHub App 事件備援遷移（Stage 4）

狀態：IMPLEMENTED_AND_UNIT_TESTED；尚未建立／安裝 App，尚未部署 Cloudflare 中繼，既有 PAT 備援保留。不得把程式完成寫成服務切換成功。

固定範圍：gxaawill2-ui/tw-close-auction-mis-probe（repo ID 1395186758）、index-events.yml、main；呼叫端只可提交 schedule_slot 08:20／17:20 及 self_test boolean。App只需Actions write＋Metadata read，私有App、webhook停用、Install只選這個repo。App本身Actions權限不能只限一個workflow；中繼以硬編碼端點限制。

Cloudflare Workers Free官方公開額度：100,000 requests/day、10ms CPU/Worker invocation；SQLite Durable Objects免費，100,000 requests/day、13,000GB-s/day、5GB儲存。預計每日2個正常呼叫，全球單SQLite DO按台北date-slot去重／60秒lease、每slot最多2個dispatch嘗試、每日最多6個授權嘗試；七日bounded ledger。未授權请求不碰GitHub。正常規模推估在免費額度內，但部署CPU與免費帳戶實測未完成，不承諾已驗證運行成本。超額Free拒絕，不升級付費。workers.dev不需自購網域；Cloudflare帳戶需要本人登入。

CALLER_SECRET須獨立32-byte以上base64url（43–128chars），以Workers Secret保存，cron只存Bearer caller-secret。APP_PRIVATE_KEY只存Workers Secret，不進Git／log／JSON；APP_CLIENT_ID與APP_INSTALLATION_ID非秘密設定。GitHub下載PKCS#1及PKCS#8皆可WebCrypto RS256；JWT iat退60秒，exp+540秒。每次重新取得1h Installation Token，不長期儲存Token，限定repository_ids及permissions並核對回應；401/403/timeout不回傳錯誤本文／憑證，不追redirect。GitHub API 2026-03-10 dispatch官方成功200含run-id，亦兼容舊204；200回應驗證固定repo URL。授權本文256bytes、GitHubtoken回應32KiB、dispatch回應4KiB上限。

重放保護是授權呼叫的台北date-slot ledger＋08:35–09:20／17:35–18:20視窗；cron靜態Bearer沒有每次HMAC/nonce，不能宣稱抵抗已外洩密鑰。TLS與獨立Secret是身分防線；洩漏仍須輪替。中繼accepted只表示GitHub接收，必須另外觀察workflow收據，不能把HTTP202當掃描發布成功。既有GitHub event_scheduler lease/CAS仍為掃描層去重，兩者分離。

部署：relay/wrangler.jsonc使用new_sqlite_classes，observability=false，無付費方案要求／無自動讀取憑證。本人最後完成App建立／安裝確認、Generate private key→Cloudflare Secret安全上傳及獨立caller-secret；agent可處理所有非秘密部署設定與驗收。必須新App派發self_test成功→真實槽位收據與原生去重→修改既有8618691/8618694 URL及caller Authorization→服務真實觸發成功→確認舊PAT不再使用，才由本人撤銷舊PAT；現階段不修改或停用兩job，不碰MIS。

官方來源（2026-10-11查閱）：
- https://developers.cloudflare.com/workers/platform/pricing/
- https://developers.cloudflare.com/durable-objects/platform/pricing/
- https://developers.cloudflare.com/workers/configuration/secrets/
- https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app
- https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation
- https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event
