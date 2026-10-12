## 2026-10-12 15:10 台北：晚間 caller 與 production Durable Object 防重複實測通過

最新狀態覆蓋下方12:55 checkpoint的尚待防重複／晨間儲存描述，歷史保留。

- 本人於13:57回報已按 SAVE 保存晨間8618691；依此前指示正式body為 `{"schedule_slot":"08:20","self_test":false}`、08:35 Asia/Taipei。此為本人保存回報；agent雲端登入已失效，尚未獨立重讀已保存設定或觀察明日08:35首次App正式run。
- 晚間8618694的原有設定畫面實際確認每日17:35、Asia/Taipei、Enable job開啟、Save responses關閉；截至修改前URL仍為GitHub index-events.yml dispatch。未更改排程時間／時區／啟用狀態。
- 本人在晚間既有工作安全欄位更換caller header並使用Worker /dispatch、自測17:20,true。2026-10-12 15:10提供的安全Response截圖證明HTTP200、128ms、X-Relay-Build=20261012-manual-redirect-fix、`{"result":"DUPLICATE_ACCEPTED"}`。
- 這是**真實production Worker與現有Durable Object的第二次同日self-test防重複證據**：caller auth通過且先前accepted ledger仍在部署後生效；不重新dispatch，不增加slot attempts／daily budget。未取得私鑰、CALLER_SECRET或Installation Token，也未讀取Raw Request。
- agent重新讀GitHub workflow_dispatch全部51個run（single page per_page100），App actor只有原本run38205706376（04:54:52Z、completed/success），沒有本次15:10新增App run；因此HTTP防重複結果與GitHub實際執行數一致。
- **晚間正式保存仍待本人執行**：CLOSE→將Request body改成 `{"schedule_slot":"17:20","self_test":false}`→SAVE；保持已驗證的Worker URL／caller header、17:35 Asia/Taipei。不得把true保存為每日正式掃描設定。
- 今日17:35以及明日08:35首次App正式定時觸發仍待驗收：核對cron history的Worker回應、App actor真實Run ID／結論、slot receipt、來源掃描／資料提交或原生已完成時的去重收據。自測及duplicate成功不代表正式來源已掃描。
- 原生08:20／17:20、MIS全部排程／tokens／logic／历史raw保持未修改；本次僅更新三份事件報告。舊PAT仍保留，尚未確認其所有其他服務依賴；不得撤銷，尤其不得影響既有MIS cron。
- 此次以最新main `2fafea30d5a41b772400ecd24a9756a13349f22c`為parent並以expected_sha lease更新，保留12:55後的資料／MIS自動提交，不用先前固定SHA覆蓋。

---

## 最新驗收狀態：真實 GitHub App 自測成功（2026-10-12）

本節更新取代下方歷史段落中的「真實 App 尚未驗證」狀態；歷史錯誤與修復證據保留。

| 項目 | 實際證據／狀態 |
| --- | --- |
| Production Worker | build `20261012-manual-redirect-fix`；健康檢查 200；來源 commit `2ea1d1551bda414d36aebff180f62a7397fd5086` |
| 真實 caller 授權 | 本人在 cron-job.org 安全欄位输入既有 CALLER_SECRET；2026-10-12T04:54:52Z（台北12:54:52）自測 POST 回應202，`DISPATCH_ACCEPTED; WORKFLOW_RECEIPT_PENDING` |
| JWT／Installation Token | 已由實際 Worker → GitHub App workflow run 證實：程式必須完成 JWT 簽名、取得201 token回應並通過期限、actions:write／metadata:read及唯一 repo ID 1395186758 / full_name 檢查，才會 dispatch；未讀取或輸出 JWT/token/私鑰 |
| 真實 GitHub Run | [38205706376](https://github.com/gxaawill2-ui/tw-close-auction-mis-probe/actions/runs/38205706376)，actor `tw-close-auction-event-backup[bot]`，main `2ea1d1551bda414d36aebff180f62a7397fd5086`，completed/success，結束2026-10-12T04:55:11Z |
| 自測收據 | job114668615410 `receipt-self-test` success；`python -m unittest test_event_reliability -v`，49 tests OK |
| Workflow完整狀態 | tests job114668615247 success；scan / public-acceptance / source-smoke 全部 skipped，符合 self_test=true，不做正式來源掃描 |
| 修復回歸 | sourcefix run38205459124 的 regressions 與 public 均 success；本機18個relay測試PASS；原生 workerd修復重現見runtime-fix報告 |
| Durable Object | 真實請求已通過現有 DISPATCH_GATE 並記錄 accepted；同日相同self-test再次呼叫的 DUPLICATE_ACCEPTED 實測尚待完成；49項hosted收據測試含重複／lease／晚到原生排程防重複，不能當作第二次production HTTP證據 |
| 晨間 Job8618691 | 自測使用晨間工作的未儲存草稿與17:20,true；尚未證實保存正式08:20,false。保留08:35 Asia/Taipei |
| 晚間 Job8618694 | 尚未切換；保留17:35 Asia/Taipei及既有可用PAT路徑 |
| 正式來源掃描 | 新App路徑尚未正式執行；僅允許既有08:35–09:20／17:35–18:20台北時間窗，午間不可用false測試。晨間舊PAT run38188568709已成功，原有來源狀態PARTIAL |
| MIS | 本次提交僅relay、relay測試及事件遷移報告；MIS tokens/secrets/workflows/排程/P_before/P_close/±3%/历史資料未修改；hosted test_no_mis_change通過 |
| 舊PAT | 仍需保留，尚未完成兩工作保存／首次正式執行及其他服務依賴檢查；未撤銷 |
| 仍須本人處理 | 本人的瀏覽器儲存晨間正式body，再於既有晚間job的安全Authorization欄输入同一CALLER_SECRET、測試／保存；不用再次輸入Google密碼或GitHub App私鑰，不把秘密貼入對話 |

後續順序：先保存8618691的Worker URL、現有已驗證caller header與 `{"schedule_slot":"08:20","self_test":false}`，不改08:35/timezone/啟用狀態。再改8618694的URL/安全caller header，先以 `17:20,true` 驗證同日DO返回DUPLICATE_ACCEPTED並核對沒有新增App run，最後保存 `{"schedule_slot":"17:20","self_test":false}`，不改17:35/timezone。今日17:35及次日08:35首次定時觸發後核對cron history、真實GitHub run與slot receipt；不能因自測成功提前宣稱完整production驗收。

Installation Token每次dispatch取得、只存在該次函式記憶體，不寫入Durable Object/Git/Log；期限檢查限制在短期範圍。跨token到期後重新取得的真實定時執行仍待後續證據。keep_vars:true與非機密APP_INSTALLATION_ID同步已保存，且此次自動部署後真實App授權及caller授權仍成功，證明部署保留所需Production設定。未新增未授權入口、未重設DO ledger／嘗試計數，也未修改時間窗。

---

## 2026-10-12 真實錯誤已重現並修復（2026-10-12T04:50:45.450Z）

本人安全Response證據：04:38:59Z、build diagnostics3、self-test evening slot，HTTP200、`SELF_TEST_FAILED; TOKEN_REQUEST; RUNTIME_TYPE_ERROR`；caller auth通過且JWT已完成sign，但Installation Token請求未完成。兩morning self-test嘗試已耗盡，evening self-test目前已一失敗；保持所有計數/lease/預算，不重設。

根因：Cloudflare Workers原生Request只接受follow/manual redirect模式；本relay使用Node Fetch可接受、Workers不支持的redirect:error，形成TOKEN_REQUEST TypeError。用官方Miniflare/workerd（5.20261006.1-alpha、requested compatibility_date 2026-10-10）在本機原生runtime，完全自生synthetic key/本機mock upstream重現：修復前TOKEN_REQUEST RUNTIME_TYPE_ERROR，固定本機上游呼叫0，錯誤只分類到redirect；修復後DISPATCH_ACCEPTED、固定本機上游2次（token＋workflow）。這是原生runtime程式修復證據，仍不代表真實App授權已通過。

最終僅更改redirect:error→manual並明確拒絕所有300–399，不跟隨Location，不傳憑證到其他origin，不增加新端點或放寬scope。保留既有source、workflow/main/repo限定、RSA處理、JWT lifetime、tokenscope核對、body/clock窗口、原DO class/key/migration/ledger、兩次slot及六次每日限制。診斷維持封閉enum，新增GITHUB_REDIRECT_REJECTED；build=20261012-manual-redirect-fix。18 Node relay tests PASS，新增301/302/303/307/308拒絕且每案例只1次upstream，無憑證輸出。臨時原生測試套件只在scratch安裝，不改repo package.json/lockfile，不上傳node_modules。機器證據：reports/index-events/github-app-runtime-fix-20261012.json。

需待正式新build header驗證後，只使用同一未儲存晨間job草稿body `{"schedule_slot":"17:20","self_test":true}` **再測一次**；Authorization保留本人輸入的caller值，不讀、不要求重填。只能看到DISPATCH_ACCEPTED後再核對真正App actor/GitHub Run ID/receipt。最後一次evening self-test若仍失敗，不可持續重試/清除ledger/重建DO/放寬限額；先處理精確新錯誤與安全設置，保留正式PAT備援。

尚未Save任何正式cron切換，舊PAT未撤銷且仍需要。MIS所有程式/Token/Secrets/jobs/排程與歷史資料未改。GitHub latest parent/expected_sha保留，不覆蓋botmain。

原生實作依據：https://github.com/cloudflare/workerd/blob/main/src/workerd/api/http.c++ （Request::tryParseRedirect僅follow/manual）
官方Fetch：https://developers.cloudflare.com/workers/runtime-apis/fetch/


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
