## 2026-10-12 12:29 本人正式自測錯誤已取得

本人提供安全Response畫面：Date=2026-10-12T04:29:41Z、X-Relay-Build=20261012-diagnostics2、HTTP200、result=`SELF_TEST_FAILED; APP_AUTH_AND_DISPATCH; UNCLASSIFIED_ERROR`。這是真實帶CALLER_SECRET的呼叫，本輪沒有讀取秘密值；證明caller authentication及既有DISPATCH_GATE路徑已通過，但JWT／Installation Token／App workflow收據仍未通過。不能把HTTP200當授權成功。原HTTP503與此次共用morning自測day-slot，已做兩次，禁止再次測morning／清除ledger。

已細分安全診斷stage為INSTALLATION_CONFIG、JWT_CONFIG、KEY_DECODE、KEY_IMPORT、JWT_ENCODE、JWT_SIGN、TOKEN_REQUEST、TOKEN_RESPONSE、TOKEN_SCOPE_CHECK、WORKFLOW_DISPATCH、WORKFLOW_RECEIPT及原receipt/storage階段；所有stage為程式固定enum，沒有raw exception text。新增安全code KEY_BASE64_INVALID、CRYPTO_UNSUPPORTED、RUNTIME_TYPE_ERROR。17項relay Node tests PASS（合成fixtures）。body/self_test/repo/scope/期限/權限/DO窗口及預算全部保持，未修改任何MIS。

下一次只能在新版X-Relay-Build=20261012-diagnostics3已實際部署後，將**晨間同一job的未儲存測試body**換成`{"schedule_slot":"17:20","self_test":true}`，使用原本已允許的獨立evening-self-test key。這不是切換正式17:35job，也不改08:35/17:35排程或正式window；production false key仍獨立。維持Authorization已由本人輸入的caller值，agent不讀取、不要求再次輸入/重新產生秘密。Test run只一次→Response.result，不Save、不Raw request。剩餘evening自測最多兩次與全日六次預算保留，不能放寬或重建DO繞過。

原PAT兩備援仍必要，App正式遷移未完成。此次僅診斷安全程式與reports/test變更；上游或Secret設定原因尚未確認，不推斷需要重新產生App私鑰。


## 2026-10-12 診斷正式部署驗證（2026-10-12T04:23:19.524Z）

最新狀態：AUTH_SELF_TEST_503_UNRESOLVED; SAFE_DIAGNOSTIC_RETRY_READY。本人自測503未通過；不是正式遷移成功。本人正在自己的瀏覽器操作，原雲端未儲存草稿不會同步至本人瀏覽器。

- 診斷程式commit9954149dd4399d2352cff98daa5abb7243cc9131，Cloudflare check114661464629（Workers Builds: tw-index-events-relay）completed/success；production build fcaead20-5ff4-4dd1-9f62-d28383c9d1e3。
- 實際HTTP 2026-10-12T04:20:50Z /health=200，X-Relay-Build=20261012-diagnostics2；最新未授權/dispatch=401/UNAUTHORIZED。已驗證實際部署，不僅是GitHub程式完成。
- Hosted回歸Run38203361545，regressions job114661381507 completed/success，260 Python tests、70 Node tests/pass70/fail0、desktop/mobile/WebKit fixtures result=PASS；16 relay tests包含在Node測試內。額外public Pages驗收job仍在執行時，不把整個run提前宣稱全部完成。上述無MIS請求，只測試fixture及事件來源read-only隔離證據。
- 自測失敗僅在self_test=true回HTTP200與明確SELF_TEST_FAILED result，因cron官方UI只對成功HTTP展示response；這個200不是App授權成功。production false仍503，未授權仍401。安全錯誤代碼不含原exception／upstream body／auth資料。無新端點與無權限擴大。
- 已告知本人CLOSE→TEST RUN僅重測一次、只查看Response.result，不Save、不Raw request、不提供Secret。若HTTP202／DISPATCH_ACCEPTED仍需新的真正GitHub App actor/run/jobs/receipt；若SELF_TEST_FAILED須依精確safe_code修復；若429／attempt-limit不得持續重試或清ledger。
- 兩個既有PAT備援及原生排程保持；本人未回報已Save正式切換，本輪也沒有保存／停用任何cron工作。MIS程式、Token、Secrets、盤中盤後jobs與價格策略均未修改。舊PAT仍需要，未撤銷。

以下歷史狀態保留；以本節及後續新證據為準。

## 2026-10-12 接續查證（2026-10-12T03:58:37.512Z）

目前狀態：RELAY_ALIVE_AUTH_SELF_TEST_PENDING_CALLER_SECRET。未宣稱正式遷移完成。

- 本人回報 GitHub App `tw-close-auction-event-backup` 已建立，App ID 5280614、Installation ID 170450126；唯一 repo、Actions write / Metadata read，Private Key 已由本人放入 Cloudflare Secret。這些設定尚未由本輪 authenticated API 獨立核對。
- 本人回報 Production 已設定 APP_CLIENT_ID、APP_INSTALLATION_ID、APP_PRIVATE_KEY、CALLER_SECRET；本輪沒有讀取任何私鑰、Secret、Authorization 值或 clipboard。Cloudflare 管理頁／正式版本及四 bindings 尚未登入獨立驗證。
- 本輪實測 `GET https://tw-index-events-relay.gxaawill2.workers.dev/health`：HTTP 200，`RELAY_ALIVE; AUTH_AND_INSTALLATION_NOT_PROVEN`。無 Authorization 的 POST /dispatch（08:20/self_test=true）：HTTP 401，UNAUTHORIZED；未授權不進入 DO / GitHub 的程式路徑已核對。
- 最新 main 查證基線 3d32b126685ec68979e3fd371e3b510bcdbd110d。GitHub App JWT、實際 Installation Token、scope、App workflow dispatch、DO 正式去重尚未實測；13 項既有 Node relay 測試本輪全部 PASS，使用自生測試 fixture，不是真實 App 憑證。
- cron-job.org 安全登入成功，Logout 與 jobs UI 確認。既有 8618691 / 8618694 仍使用原 GitHub dispatch URL，保持啟用、Asia/Taipei、08:35 / 17:35；晨間 Common 顯示 saveResponses=false。未 Save、未停用、未重建任何 job。
- 真實舊 PAT 晨間 timer：cron UI 今天 08:35:09 成功；GitHub Run [38188568709](https://github.com/gxaawill2-ui/tw-close-auction-mis-probe/actions/runs/38188568709) event=workflow_dispatch、actor=gxaawill2-ui、created_at=2026-10-12T00:35:11Z、completed/success；tests 与 scan 均 success，receipt-self-test skipped。main date-slot receipt RECOVERED_BY_BACKUP、scan_attempts=1、duplicate_trigger=false，08:38:16.141818+08:00 出版、data commit 8252e0f899976b97f41e087cf4bc6f1957d420c2、source PARTIAL。這是舊 PAT 路徑的證據，不能當作 App 路徑驗收。
- Wrangler 非機密修正：keep_vars=true 保留 Dashboard APP_CLIENT_ID；同步本人提供的 APP_INSTALLATION_ID=170450126。未寫入任何 Secret。保留 SQLite DO、原 class/migration/name/endpoint。Cloudflare 官方配置文件說明 Dashboard vars 默認會被下次 Wrangler deploy 覆蓋，而 keep_vars 可保留；Wrangler 不會刪除 encrypted secrets，除非執行 secret delete。尚未驗證連動部署版本及 build command 使用本 config。
- 原生事件排程 `20 0 * * *` / `20 9 * * *` 保留；event workflow self_test=true 只執行 tests / receipt-self-test，scan 不執行。檢查了 relay 固定 repo/workflow/main、每次新一小時 Token、權限及 repository 核對、DO 台北 day-slot lease/replay、workflow git CAS 第二層去重；正式雙層去重仍待帶 CALLER_SECRET 實測。
- 免费額度結論仍為預估：每日兩次正常呼叫／最多六次授權嘗試、七日小型 ledger，符合既有官方免費量級的設計；實際帳戶方案與 RS256 CPU usage 尚未測，不保證已完成成本驗收。Worker 上游失敗現有輸出 DISPATCH_UNVERIFIED，不足以單靠 response 分辨具體錯誤；若自測失敗，後續只做不含秘密的分類診斷。
- 自動審核拒絕讀取 cron 現有欄位值（包括 request body / header values 的風險）；該讀取未執行，沒有秘密輸出。改用已知明文測試設定，不讀現有值。

### 精確下一步

晨間既有 job 8618691 的雲端表單已準備 **未儲存** 的自測草稿：URL /dispatch，POST body `{"schedule_slot":"08:20","self_test":true}`；時區與時間未改，伺服器仍保留舊 PAT 正式設定。缺少 CALLER_SECRET，不能代讀 Cloudflare Secret，也不能冒用 browserAuth 作非登入秘密輸入。本人安全接管後，只需將該草稿 Authorization Value 改成 Bearer 加一空格及已保存 CALLER_SECRET，點 Test run；**不得點 Save**。如此可先實測 App 而不切換／停用原有備援。

接續 agent 不可完整讀 Advanced、Test dialog、Raw request 或截圖憑證；只精確檢查可見 HTTP status／安全 response，再以 GitHub MCP 核對實際 App actor/run ID/jobs/self-test receipt 成功。成功後才逐一保存正式 URL／slot／self_test=false 設定，秘密輸入與提交由本人完成。若已走 user 手動 Test run，待 user 確認結束才能觀測，禁止看中途秘密。晚間 job 保留，僅晨間驗證後才切第二筆。正式 17:35→17:20 只能在既有 window 17:35–18:20 測，不能降低時間／身份防護或偽造時間。

舊 PAT 仍需要，未撤銷；只有兩新路徑正式驗證且依賴核對後才由本人撤銷事件專用 PAT。MIS token、Secrets、jobs、排程、P_before/P_close/±3%、歷史盤中資料、本轮全部未改／未抓。GitHub report/config commit 使用最新 parent 與 expected_sha lease，不覆蓋 bot 較新 main。

官方依據：
- https://developers.cloudflare.com/workers/wrangler/configuration/#source-of-truth
- https://developers.cloudflare.com/workers/configuration/secrets/


---

以下保留先前實作與歷史狀態，當前狀態以本頁頂端為準。

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


## 2026-10-12 自測 503 排錯接續（2026-10-12T04:16:06.420Z）

本人提供晨間 job8618691 Test run 畫面：503 Service Unavailable。原始 response body 未取得，不能單靠此畫面證明 caller auth 已通過或斷言 GitHub 過載。截至本輪 GitHub repository workflow_dispatch runs 查詢（前15筆），最新事件仍為38188568709/2026-10-12T00:35:11Z；未找到本次 App self-test run。Worker /health 仍HTTP200。

已對固定 relay 加入封閉 allowlist 的非秘密診斷：僅回傳 CONFIG、KEY_FORMAT、TOKEN_HTTP_status、TOKEN_SCOPE、DISPATCH_HTTP_status、DISPATCH_RECEIPT_SCOPE、BODY_TIMEOUT、TOO_LARGE、UPSTREAM_TIMEOUT、KEY_CRYPTO_FAILED、UPSTREAM_INVALID_JSON 或 UNCLASSIFIED_ERROR；另外區分 APP_AUTH_AND_DISPATCH / RECEIPT_STORE / LEDGER_CLEANUP。沒有回傳原 exception message、GitHub response body、JWT、Token、private key、caller header。診斷只在已存在的受保護 /dispatch 錯誤回應；無新入口、無放寬驗證/權限/視窗/重試限額。DO 僅保存允許的 failure_code/failure_phase，不保存憑證。所有 response 的 X-Relay-Build=20261012-diagnostics1，供匿名 health 驗證實际部署。

15項 relay Node 測試 PASS，其中新增檢查診斷不洩漏任意例外訊息與失敗 lease/attempt 保留。合成 fixture 不能代替正式授權。main 當前 parent63e9ab2a5412279e78f2868317d6c8af102eae00，以GitHubexpected_sha lease更新，不覆蓋data bot。現有兩PAT備援維持，未保存正式切換、未動MIS。重測前必須確認新build header真實部署；重試仍受每date-slot最多兩次限制，不清除ledger/重建DO；若morning self-test耗盡，可用原允許的17:20 self_test=true隔離自測槽，禁止正式時間外掃描。


### 診斷回應顯示修正（2026-10-12T04:20:00.098Z）

Cloudflare Workers Builds check114660659191對commit393977c5b37f3b24f53969b52ae4d841c7463475為SUCCESS；04:17:06Z實際/health HTTP200並帶X-Relay-Build=20261012-diagnostics1，Git連動部署已從GitHubcheck及HTTP獨立驗證。此commit的hosted regressions check114660595332亦SUCCESS，未觸發MIS抓取。

cron-job.org官方前端frontend/src/components/jobs/JobTestRun.jsx確認只有JobStatus.OK才展示response/raw response，503畫面不顯示body。因此在現有已受保護dispatch內，**仅self_test=true**的處理失敗改回HTTP200、明確result=SELF_TEST_FAILED; phase; safe_code，使本人能於Response分頁取得非秘密診斷；不能把HTTP200或cron綠色狀態当作App授權／派發成功。self_test=false任何上游錯誤仍503 DISPATCH_UNVERIFIED，未授權仍401，其餘body/slot/replay限制不變。沒有無保護測試入口。build標記20261012-diagnostics2。16項Node relay測試PASS，包括production維持503的必要回歸。

接續僅在新版health build確認後重測一次；本人只需關閉舊modal→TEST RUN，不Save，不Raw request。若显示Response内容，只提供result文字（不提供Authorization）；如果ATTEMPT_LIMIT/429則停止晨間重試，使用既有允許的晚間self_test槽位，不清除DO計數。正式App receipt仍待成功、舊PAT兩job仍保持運作、MIS仍未改。

官方介面實作：https://github.com/pschlan/cron-job.org/blob/master/frontend/src/components/jobs/JobTestRun.jsx
