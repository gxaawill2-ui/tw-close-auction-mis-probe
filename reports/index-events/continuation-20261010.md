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

# Context接續／正式保存

2026-10-10T00:23:50.384Z

已發布最終程式b6246cff62a37801d5c2c3a10115e6d77496b397；最終reviewed branch580a6c7160e6c65fd231c4102dcc8ddd524624a0；main data b061e45125e3bdbc5f72a42eb8e3fd595327542a與ack dfd003f4285fa8c609aff7f8f9b766a097643dd1。以GitHub最新main為準，程式／scanner會持續commit，因此不可拿本檔固定SHA覆蓋新資料。

242 Python、42 Node／32DOM、42browser PASS；main38007718767、MIS tests38007718825、Pages38007864341。最新收據ADHOC_PUBLISHED sourcePARTIAL 15成功；真正native抵達仍待實測，不得宣稱on-time。外部cron-job.org未登入，不可聲稱已啟用備援。全套disabled template與HTTPdriver 已測；真正不能代辦只是一登入／新repoActions憑證授權。

fund_events19/15ETF：1高2中0低16不足；初期asof誤用舊snapshot已校正19lineage，invalidhistory保存，首有效07:50:47.811603。主頁與fund-events.html深色無按鈕；不重設網站、不抓MIS／原10/8cand。

來源27 class10/5/3/6/3，TPEx quote118候選非当前掛牌；MSCI公開ADD/DEL與FTSEpublicPDF可閱但使用限制，FTSEbots被terms禁止已停止。當前49events/66maps64confirmed2conflict與MIS價格量能均保留。閱讀acceptance、deployment、scheduler-redundancy-acceptance、importance-methodology、remaining-source-restrictions再承接。

最後本機／CUA環境因environment_offline無法再連；GitHub MCP及GitHub hosted CI／公網址browser驗收仍可用。所有權威程式、資料及報告已保存GitHub，不依賴scratch；不要因本機dirty/stale覆蓋remote。只補真正auth/native驗收與合法新來源，不要重seed。

## 再次接續實測（2026-10-10T13:40:20.206Z）

GitHub main已前進5d9d543b8c0635b6851613c9a3dd7c6d430a314e，保存最新bot資料，未以4354383覆蓋。真實原生run38029017422 event=schedule、cron20 0 * * *，台北10/10 13:53:04抵達、13:53:19 runner、13:53:26 scan、13:54:56完成、13:54:57出版。收據unattributed-2026-10-10-2 resultDELAYED，scan_attempts1、duplicate=false；原定日期仍UNKNOWN、scheduled_for/delay_seconds null，不能冒稱08:20準時或任意原始日期。未完成原morning-slot，只在late-recovery bucket更新。10/10 17:20新的schedule Run截至檢查未找到，不寫明確dropped。

run38029017422 tests實際242 Python、42 Node PASS；來源15成功，27類10/5/3/6/3、PARTIAL；pending_review14。最新data d192ddb100c0647fdc77371278e7399c29738699、ack5d9d54；Pages38029124408 SUCCESS。原MIS候選blob247dbe4bf7f149950a6196ad59119a65be25599f與4354383逐位元一致（7檔、validated=false）。

正式fund-events.html以雲端瀏覽器實測全部19 article、controls0、body rgb(11,16,26)、dark、無水平溢出。0050高／0051中／0056中均暫定，006208不足；日期證據分開。沒有重新評級／修改程式。

cron-job.org本次重新開console，仍Sign in。之前安全登入request中斷並無成功證據；重新runtime只見空白tab，未假設曾登入或不存在憑證。第一優先是安全登入／手動交接，再檢查event-only新jobs、獨立repo-scoped credential；不得讀MIS Authorization或改MIS jobs。依browser安全流程不在聊天處理密碼／PAT；兩個event backup尚未啟用，不能寫成功。

剩餘限制只補新的SITCA公會候選：匿名HTTP200643756bytes，有基金代號；robots404非授權；完整追蹤index／掛牌life及可持續再用仍未驗證，未加入scanner。政府129347是分類總量，44656是投信公司身份，都不是ETF完整主檔。不因此改PARTIAL／UNKNOWN；MSCI/FTSE再用与实际ETF委託仍無新確認。詳resume-validation-20261010.json。

下一步：保持這次登入handoff分頁，使用者完成登入後直接讀UI；不重做研究，不seed、不部署既有程式、不重抓MIS。登入只影響外部備援，不阻塞既有正式網站。

## 外部備援服務建立（2026-10-10T14:35:44.753Z）

使用者完成cron-job.org雲端登入，UI Logout與工作清單確認成功。原有6個啟用MIS工作及3個停用MIS工作保留；沒有打開／修改任何MIS工作或讀取其headers。

已實際建立並重新開啟驗證兩個獨立event-only工作：8618691「TW index events backup 08:35」、8618694「TW index events backup 17:35」。Asia/Taipei每日35 8／35 17；只POST index-events.yml/main，inputs schedule_slot=08:20／17:20，self_test=false；timeout20、saveResponses=false、必要JSON/API headers皆已保存。兩工作仍停用，Authorization只放非秘密佔位文字，不能宣稱已啟用或成功觸發。

開啟GitHub獨立fine-grained PAT建立頁，已登入@gxaawill2-ui，但遇到Confirm access（Verify via email），尚未建立新憑證。下一個真正必要使用者步驟是GitHub身分驗證／授權全新repo限定Actions read/write憑證，安全填入兩event工作；不重用MIS token、不要在聊天／報告／Git保存Token。之後agent完成external Test run、自測收據與啟用。詳backup-activation-20261010.json。

GitHub查詢仍僅找到native38029017422、37957502210；17:20新的Run截至本次未找到。全部既有程式／測試／網站／事件與MIS資料未改。若context中斷，不要重新建立這兩個工作；先查看上述job IDs及最新main。

## GitHub驗證中斷後接續（2026-10-10T15:20:01.587Z）

安全OTP請求中斷，沒有身分驗證成功證據；新分頁仍GitHub Confirm access／Verify via email。尚未產生獨立Token。cron-job.org新分頁亦重新顯示Sign in（雲端session已失效），先前建立的8618691／8618694保存在服務，不要重建。先用manual handoff完成GitHub再次驗證；隨後agent填妥fine-grained PAT必要範圍，產生憑證需本人於最後動作確認／安全交接。之後安全重新登入cron，只在兩event工作填獨立憑證，測試才啟用。不得讀任何憑證值或MIS headers。

最後報告提交5e2463c4279022f5a6119b2837db51c531b1c9d1 Pages38060248642 SUCCESS；程式未改，既有242／42／42 PASS仍有效。截至本次查詢native晚間新run仍未找到。備援仍NOT_ACTIVATED；不要誤稱登入完成即觸發完成。

## 本人驗證完成／新憑證表單已準備（2026-10-10T15:28:12.944Z）

使用者完成GitHub Confirm access，已進入New fine-grained personal access token。agent已填妥：TW index events cron backup 20261010、owner gxaawill2-ui、Only select repositories唯一tw-close-auction-mis-probe、Actions Read and write、Metadata必要Read-only、Account0。尚未Generate token，沒有新Token可讀或存放。

保留原有30天expiration，GitHub顯示2026-11-09。auto-review拒絕選Custom expiration，理由是沒有具體期限授權；已改用保留30天的安全替代方案，未繞過／重試自訂期限。新憑證不能真正限制到單一workflow；只限定repo Actions，cron工作配置固定index-events.yml，不修改MIS工作。30天到期後需由本人更新Token，不能聲稱憑證永遠有效。

下一步只交接安全敏感步驟：User manually generates new token from prepared GitHub form, securely pastes Bearer token into Authorization Value of saved event jobs8618691/8618694 and saves, leaving disabled; agent tests event-only HTTP and receipts before enabling. Never inspect generated token page, clipboard, header values, or credential-bearing screenshots. cron最新UI仍Sign in，需要安全重新登入。兩工作其餘欄位全部已存，不能重建、不能先啟用佔位憑證、不能完整snapshot Advanced。權限表單證據event-pat-scope-1791646016361.jpg含非秘密草稿，無Token。若使用者回覆已產生／已貼好，嚴禁讀取GitHub新Token結果頁；只從cron Common非敏感欄位／工作清單及GitHubrun收據驗證。

## 晚間原生排程已實測抵達（2026-10-10T15:30:38.115Z）

新的真實native schedule Run 38063666867 SUCCESS；github_event_schedule=20 9 * * *，17:20 clock已證明送達。台北10/10 23:27:13 trigger、23:27:40 runner、23:27:47.404031 scan、23:29:08完、23:29:10.099475出版。原始預定日期未提供；scheduled_for與delay_seconds null，origin_date_verified=false。result=DELAYED，identity=unattributed-2026-10-10-3，original_slot_not_fulfilled=true；不得把晚到回復更新宣稱當日17:20準時或已完成原槽位。1 scan attempt、duplicate_trigger=false、來源PARTIAL15成功／27、new_events0／corrected0。242 Python／42 Node PASS（test job114246844916）。data819d782e776b88a510b90dc1cccc29116c1b9c0e、ack ff83c6c72051c7fe9d6e1affcab23275485341a2，保留bot提交。

08:20 cron38029017422在13:53抵達與17:20 cron38063666867在23:27抵達均已驗證，但準時性均未證實、原日仍UNKNOWN。外部兩job已建立但未具真憑證／停用，外部服務trigger仍未驗證；不能混稱備援已啟用。完整證據native-evening-verification-20261010.json。

## 雲端分頁失效後恢復（2026-10-10T23:32:53.123Z，台北2026-10-11）

使用者回報前次分頁無法使用。getState只見about:blank，重新開既有晨間job8618691轉Sign in；新GitHub fine-grained token清單只見既有MIS token，未見事件專用Token，未開MIS Token明細或讀取其值。透過清單Generate new token安全入口重開後為Confirm access／Verify via email，沒有重新Generate憑證。先前Token草稿分頁已失效；cron兩保存工作仍沿用ID8618691／8618694，不重建，當前不能登入驗證是否被使用者後續修改／啟用。正式main d174c158c9690f7248def1357354901a3f107261、Pages38063906450 SUCCESS，既有code/tests/data不變。

下一步只完成新雲端GitHub本人驗證，再按已保存 scope 重填未持久化的Token草稿並安全交接產生／貼入。新增Token只允許repo Actions read/write＋必要Metadata read；保留有界30天期限（新日期隨GitHub建立時呈現）；自訂更長期限需具體授權，前次auto-review拒絕不得繞過。使用者生成後不讀Token結果頁、不讀headers Value、不讀clipboard。cron重新登入後只處理event jobs，Test run與GitHubrun/receipt確認後才Enable；外部備援依然NOT_ACTIVATED，不冒稱08:35已會自動觸發。不要重做研究、seed、MIS歷史抓取或程式部署。

## 最新驗證完成／草稿全部恢復（2026-10-10T23:38:01.868Z，台北2026-10-11）

使用者再次完成GitHub Verify via email並表示後續交給agent。已恢復全部非秘密草稿欄位：TW index events cron backup 20261010、唯一repo tw-close-auction-mis-probe、Actions Read and write、必要Metadata Read-only、Account0；保留原bounded30天，今日到期日2026-11-10。沒有按Generate token、沒有任何新Token值取得／讀取。cron頁仍未登入；两saved event jobs8618691／8618694不重建。

實際安全阻擋來自瀏覽器Hand-Off Required規則：Changing a password or other authentication credential: Ask the user to take over before any new credential is entered, and have them complete the entry, confirmation, and submission steps themselves. 因此不可代讀／用clipboard搬移秘密值／以Playwright填入Token／以browserAuth把設定headers冒作登入。僅本人按Generate及安全填入兩event Authorization、Save，其他cron時間/body/headers/timeout/saveResponses先前均完成。agent之後負責HTTP外部服務測試、GitHub run與收據、防重複與Enable。生成後不要完整snapshot token結果頁或Advanced。憑證草稿證據event-pat-scope-ready-1791675423691.jpg不含任何秘密。

外部備援仍JOBS_CREATED_DISABLED_CREDENTIAL_REQUIRED，不能聲稱08:35或17:35已啟用。既有native兩cron證明遲到抵達，不證明準時；已完成程式、MIS、來源研究、基金重要程度不重做。


## 外部 HTTP 實測與必要憑證輪替（2026-10-10T23:53:23.348Z）

使用者已親自貼入並儲存兩筆event-only Authorization。晨間job8618691以未儲存self_test=true本文Test run回HTTP204（2026-10-10T23:51:09Z），對應GitHub workflow_dispatch38096440156 SUCCESS。receipt-self-test114343194975及tests114343195136 SUCCESS；scan/source-smoke/public-acceptance SKIPPED，沒有MIS、來源請求或state/main寫入。測試後將本地本文恢復self_test=false，兩jobs仍停用。

操作失誤：讀取整個測試dialog文字包含隱藏Raw request中的Authorization秘密，隨後綁定仍停留新Token顯示狀態的既有GitHub清單頁亦自動輸出同一秘密。已向使用者明確告知；不得聲稱credentials_read=false。沒有秘密寫入Git或報告。本報告僅保存非秘密事件描述。已關閉測試modal並離開產生結果頁。不要再使用此憑證完成上線；先由本人在事件專用Token20932040的Regenerate頁重新產生，使舊值失效，再填入兩job並Save。MIS Token、Secrets、排程均未動。

接續禁止：不要getTab/getAXState/snapshot任何產生新Token結果頁；既有句柄只導航到已驗證安全detail/Common。不要whole dialog allTextContents（包含隱藏raw request）；測試結果只能指定可見status元素例如204 No Content，且不可讀Raw request/headers。不要讀Authorization Value、clipboard或截圖Advanced。輪替後兩筆HTTP實測、event-only Run與防重複收據確認才可Enable。


## 輪替後安全重測未通過（2026-10-10T23:59:59.400Z）

使用者回覆已Regenerate並分別貼入Save兩event jobs。晚間8618694及晨間8618691以未儲存self_test=true本文重測均HTTP401 Unauthorized。僅查精確status元素isVisible，未讀任何secret Value、Raw request、dialog全文或GitHub產生Token頁；新秘密沒有取得／輸出。401原因未確認，不可推斷一定Token過期或權限問題。兩jobs保持disabled，本地測試本文已恢復self_test=false；沒有新GitHub event Run成功證據，也沒有來源／MIS請求。前次HTTP204 run38096440156只屬已要求輪替的旧憑證，不代替本輪通過。

已把晨間Authorization Value聚焦並選取，必須本人核對新完整Token與Bearer＋一個空格格式、Save；若新值已遺失，只能本人再Regenerate，不可讀clipboard／猜測／取回舊值。接續agent只讀targeted可見HTTPstatus，兩筆均204＋GitHubevent-only成功後才能啟用。保留MIS、正式網站、既有來源及基金重要性模型不變。


## 外部備援已真正啟用（2026-10-11T00:11:26.091Z）

使用者再次Regenerate並親自貼入Save兩job後，8618694晚間Test run HTTP204→event-only38097218020 SUCCESS（00:05:10Z）；8618691晨間HTTP204→38097264694 SUCCESS（00:05:55Z）。242 Python＋42 Node PASS；49項receipt reliability子集PASS（屬242之內），scan/source-smoke/public-acceptance均SKIPPED。這是cron-job.org實際服務HTTP，不是先前CI短期Token替代驗證；只查精確status可見性及GitHub run/job/log數量，沒有讀新秘密、Raw request、headers Value、clipboard或generated-token頁。

兩job均Enable＋Save並reload確認true，saveResponses=false，Asia/Taipei；正式body恢復self_test=false、固定index-events.yml/ref main，slots08:20／17:20。清單顯示今天08:35／17:35 next execution，非敏感畫面event-backup-enabled-1791677316657.jpg。既有MIS工作／Tokens／Secrets未動。本站19基金event正常、0050高暫定／0051中暫定／0056中暫定／006208不足、日期可信度分欄、無按鈕；10/11休市不顯示10/8當日名單，10/8candidate blob247dbe4bf7f149950a6196ad59119a65be25599f不變。

重要範圍：首次真正timer08:35／17:35尚未到達／觀察，不能把self_test=true成功寫成production source scan、RECOVERED_BY_BACKUP或DUPLICATE_SUCCESS實測。原始native預定日期仍UNKNOWN；兩clock cron晚到送達先前已證實，準時性不冒稱。下一步僅讀actual workflow_dispatch與date-slot receipts／publish ack；jobs已自動運作，不需使用者每天操作。事件憑證保留30天選定到期2026-11-10，需要本人安全更新，不能承諾無期限免維護。GitHub API／runner是共同故障點，外部timer不等於獨立運算備援。

先前秘密觀測失誤已告知使用者並要求輪替，本報告保留事件歷史；新憑證config已HTTP驗證，沒有秘密寫入Git。來源授權、TPEx完整主檔、未來基金實際委託時間無新可靠來源，保持PARTIAL／UNKNOWN，不重做研究或捏造解決。


## Stage 4隔離開發保存 2026-10-11T00:53:51.901526+00:00

work/stage4-20261011從e0基線建立；最新main39036180保留08:35timerbot提交。真實38098926958已RECOVERED_BY_BACKUP、1scan／無重複，sourcePARTIAL。新GitHub App中繼已實作但未註冊／安裝／部署／切換，現有8618691／8618694不碰。實質closewatch UI＋独立量能unknown/provisional累積完成，260Python62Node PASS、瀏覽器需hostedCI。10/8原zip僅本機重讀，池內1035/1082證據，47缺漏與混合official分母使正式値null；首次派生時間10/11，禁止偽回填。繼續從branch測試與報告，不用dirty舊mis-dashboard。先完成独立部署／網站验收，再最少必要App與Cloudflare本人安全授權，PAT新模式確認成功後才撤銷。


## Stage 4正式增量驗收（2026-10-11）

PR2在隔離分支56bc1c9f完整260Python／67Node（其中DOM/state44）／51Chromium desktop/mobile及WebKit iPhone PASS後合併777c84b7；feature38100709443、main38100842844含公開匿名JSON與三瀏覽器均SUCCESS，原MIS tests-only38100842853與事件38100842944 SUCCESS；Pages38100842781與最新資料38100952566 SUCCESS。完整機器證據stage4-final-verification.json、stage4-public-evidence/acceptance.json及桌機／手機／WebKit PNG保存。10/8candidate blob247dbe4bf7f149950a6196ad59119a65be25599f及SHA不變，未抓MIS。

首頁只列有官方實質異動證據且有收盤觀察日／期間者；49DB事件中4筆官方issuer異動數摘要尚無close date，未來符合者0。來源PARTIAL提示分開，19基金／15ETF與1高2中0低16不足保持；全唯讀research仍保存期程，不冒充homepage合資格事件。

市場量能獨立workflow38100939460在正式main手動完成holiday→公開JSON／source-health／history，未觸發MIS。每日15:05與18:05台北自動累積；普通交易日實際排程尚未到，不宣稱已驗證完整日。10/8部分池1035/1082驗證、缺47，subtotal64,393,939,140元不作全市場值；regular分母與有效20/60日仍缺，formal boolean／占比皆null，門檻PROVISIONAL。今日10/11休市；缺資料交易日顯示尚未確認。

App／relay僅完成程式及synthetic測試，GitHub App草稿已填僅Actions R/W＋Metadata R/O、private、webhook停用，尚未提交或安裝；Cloudflare登入頁未登入。必須本人最後確認新增安全權限與私鑰／caller-secret安全保存後才能繼續服務驗收。现有兩job/PAT維持，08:35真timer38098926958已RECOVERED_BY_BACKUP並出版，17:35本日仍未到；PAT未撤銷且2026-11-10到期仍是必要憑證。native原始預定日期UNKNOWN。


### 本人授權接續狀態（2026-10-11）

所有独立功能仍已正式驗收，報告commit647474df及Pages38101262261 SUCCESS。Cloudflare安全browserAuth由本人選Google，回傳submitted後頁面仍為登入頁且顯示「Unable to sign in. Try again or use your email and password.」。不是登入成功；原因UNKNOWN，不認定bot／密碼錯誤，不自動切換方式或重試。完整非秘密證據stage4-auth-handoff.json及空登入表畫面保存。必要下一步僅本人接管原Cloudflare分頁登入；GitHub App草稿仍未提交/安裝，最小新權限與私鑰秘密輸入需本人最後授權。現有兩個PAT備援始終保留，不宣稱App切換或PAT撤銷。


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



## 2026-10-12 自測 503 排錯接續（2026-10-12T04:16:06.420Z）

本人提供晨間 job8618691 Test run 畫面：503 Service Unavailable。原始 response body 未取得，不能單靠此畫面證明 caller auth 已通過或斷言 GitHub 過載。截至本輪 GitHub repository workflow_dispatch runs 查詢（前15筆），最新事件仍為38188568709/2026-10-12T00:35:11Z；未找到本次 App self-test run。Worker /health 仍HTTP200。

已對固定 relay 加入封閉 allowlist 的非秘密診斷：僅回傳 CONFIG、KEY_FORMAT、TOKEN_HTTP_status、TOKEN_SCOPE、DISPATCH_HTTP_status、DISPATCH_RECEIPT_SCOPE、BODY_TIMEOUT、TOO_LARGE、UPSTREAM_TIMEOUT、KEY_CRYPTO_FAILED、UPSTREAM_INVALID_JSON 或 UNCLASSIFIED_ERROR；另外區分 APP_AUTH_AND_DISPATCH / RECEIPT_STORE / LEDGER_CLEANUP。沒有回傳原 exception message、GitHub response body、JWT、Token、private key、caller header。診斷只在已存在的受保護 /dispatch 錯誤回應；無新入口、無放寬驗證/權限/視窗/重試限額。DO 僅保存允許的 failure_code/failure_phase，不保存憑證。所有 response 的 X-Relay-Build=20261012-diagnostics1，供匿名 health 驗證實际部署。

15項 relay Node 測試 PASS，其中新增檢查診斷不洩漏任意例外訊息與失敗 lease/attempt 保留。合成 fixture 不能代替正式授權。main 當前 parent63e9ab2a5412279e78f2868317d6c8af102eae00，以GitHubexpected_sha lease更新，不覆蓋data bot。現有兩PAT備援維持，未保存正式切換、未動MIS。重測前必須確認新build header真實部署；重試仍受每date-slot最多兩次限制，不清除ledger/重建DO；若morning self-test耗盡，可用原允許的17:20 self_test=true隔離自測槽，禁止正式時間外掃描。


### 診斷回應顯示修正（2026-10-12T04:20:00.098Z）

Cloudflare Workers Builds check114660659191對commit393977c5b37f3b24f53969b52ae4d841c7463475為SUCCESS；04:17:06Z實際/health HTTP200並帶X-Relay-Build=20261012-diagnostics1，Git連動部署已從GitHubcheck及HTTP獨立驗證。此commit的hosted regressions check114660595332亦SUCCESS，未觸發MIS抓取。

cron-job.org官方前端frontend/src/components/jobs/JobTestRun.jsx確認只有JobStatus.OK才展示response/raw response，503畫面不顯示body。因此在現有已受保護dispatch內，**仅self_test=true**的處理失敗改回HTTP200、明確result=SELF_TEST_FAILED; phase; safe_code，使本人能於Response分頁取得非秘密診斷；不能把HTTP200或cron綠色狀態当作App授權／派發成功。self_test=false任何上游錯誤仍503 DISPATCH_UNVERIFIED，未授權仍401，其餘body/slot/replay限制不變。沒有無保護測試入口。build標記20261012-diagnostics2。16項Node relay測試PASS，包括production維持503的必要回歸。

接續僅在新版health build確認後重測一次；本人只需關閉舊modal→TEST RUN，不Save，不Raw request。若显示Response内容，只提供result文字（不提供Authorization）；如果ATTEMPT_LIMIT/429則停止晨間重試，使用既有允許的晚間self_test槽位，不清除DO計數。正式App receipt仍待成功、舊PAT兩job仍保持運作、MIS仍未改。

官方介面實作：https://github.com/pschlan/cron-job.org/blob/master/frontend/src/components/jobs/JobTestRun.jsx


## 2026-10-12 診斷正式部署驗證（2026-10-12T04:23:19.524Z）

最新狀態：AUTH_SELF_TEST_503_UNRESOLVED; SAFE_DIAGNOSTIC_RETRY_READY。本人自測503未通過；不是正式遷移成功。本人正在自己的瀏覽器操作，原雲端未儲存草稿不會同步至本人瀏覽器。

- 診斷程式commit9954149dd4399d2352cff98daa5abb7243cc9131，Cloudflare check114661464629（Workers Builds: tw-index-events-relay）completed/success；production build fcaead20-5ff4-4dd1-9f62-d28383c9d1e3。
- 實際HTTP 2026-10-12T04:20:50Z /health=200，X-Relay-Build=20261012-diagnostics2；最新未授權/dispatch=401/UNAUTHORIZED。已驗證實際部署，不僅是GitHub程式完成。
- Hosted回歸Run38203361545，regressions job114661381507 completed/success，260 Python tests、70 Node tests/pass70/fail0、desktop/mobile/WebKit fixtures result=PASS；16 relay tests包含在Node測試內。額外public Pages驗收job仍在執行時，不把整個run提前宣稱全部完成。上述無MIS請求，只測試fixture及事件來源read-only隔離證據。
- 自測失敗僅在self_test=true回HTTP200與明確SELF_TEST_FAILED result，因cron官方UI只對成功HTTP展示response；這個200不是App授權成功。production false仍503，未授權仍401。安全錯誤代碼不含原exception／upstream body／auth資料。無新端點與無權限擴大。
- 已告知本人CLOSE→TEST RUN僅重測一次、只查看Response.result，不Save、不Raw request、不提供Secret。若HTTP202／DISPATCH_ACCEPTED仍需新的真正GitHub App actor/run/jobs/receipt；若SELF_TEST_FAILED須依精確safe_code修復；若429／attempt-limit不得持續重試或清ledger。
- 兩個既有PAT備援及原生排程保持；本人未回報已Save正式切換，本輪也沒有保存／停用任何cron工作。MIS程式、Token、Secrets、盤中盤後jobs與價格策略均未修改。舊PAT仍需要，未撤銷。

以下歷史狀態保留；以本節及後續新證據為準。



## 2026-10-12 12:29 本人正式自測錯誤已取得

本人提供安全Response畫面：Date=2026-10-12T04:29:41Z、X-Relay-Build=20261012-diagnostics2、HTTP200、result=`SELF_TEST_FAILED; APP_AUTH_AND_DISPATCH; UNCLASSIFIED_ERROR`。這是真實帶CALLER_SECRET的呼叫，本輪沒有讀取秘密值；證明caller authentication及既有DISPATCH_GATE路徑已通過，但JWT／Installation Token／App workflow收據仍未通過。不能把HTTP200當授權成功。原HTTP503與此次共用morning自測day-slot，已做兩次，禁止再次測morning／清除ledger。

已細分安全診斷stage為INSTALLATION_CONFIG、JWT_CONFIG、KEY_DECODE、KEY_IMPORT、JWT_ENCODE、JWT_SIGN、TOKEN_REQUEST、TOKEN_RESPONSE、TOKEN_SCOPE_CHECK、WORKFLOW_DISPATCH、WORKFLOW_RECEIPT及原receipt/storage階段；所有stage為程式固定enum，沒有raw exception text。新增安全code KEY_BASE64_INVALID、CRYPTO_UNSUPPORTED、RUNTIME_TYPE_ERROR。17項relay Node tests PASS（合成fixtures）。body/self_test/repo/scope/期限/權限/DO窗口及預算全部保持，未修改任何MIS。

下一次只能在新版X-Relay-Build=20261012-diagnostics3已實際部署後，將**晨間同一job的未儲存測試body**換成`{"schedule_slot":"17:20","self_test":true}`，使用原本已允許的獨立evening-self-test key。這不是切換正式17:35job，也不改08:35/17:35排程或正式window；production false key仍獨立。維持Authorization已由本人輸入的caller值，agent不讀取、不要求再次輸入/重新產生秘密。Test run只一次→Response.result，不Save、不Raw request。剩餘evening自測最多兩次與全日六次預算保留，不能放寬或重建DO繞過。

原PAT兩備援仍必要，App正式遷移未完成。此次僅診斷安全程式與reports/test變更；上游或Secret設定原因尚未確認，不推斷需要重新產生App私鑰。



## 2026-10-12 真實錯誤已重現並修復（2026-10-12T04:50:45.450Z）

本人安全Response證據：04:38:59Z、build diagnostics3、self-test evening slot，HTTP200、`SELF_TEST_FAILED; TOKEN_REQUEST; RUNTIME_TYPE_ERROR`；caller auth通過且JWT已完成sign，但Installation Token請求未完成。兩morning self-test嘗試已耗盡，evening self-test目前已一失敗；保持所有計數/lease/預算，不重設。

根因：Cloudflare Workers原生Request只接受follow/manual redirect模式；本relay使用Node Fetch可接受、Workers不支持的redirect:error，形成TOKEN_REQUEST TypeError。用官方Miniflare/workerd（5.20261006.1-alpha、requested compatibility_date 2026-10-10）在本機原生runtime，完全自生synthetic key/本機mock upstream重現：修復前TOKEN_REQUEST RUNTIME_TYPE_ERROR，固定本機上游呼叫0，錯誤只分類到redirect；修復後DISPATCH_ACCEPTED、固定本機上游2次（token＋workflow）。這是原生runtime程式修復證據，仍不代表真實App授權已通過。

最終僅更改redirect:error→manual並明確拒絕所有300–399，不跟隨Location，不傳憑證到其他origin，不增加新端點或放寬scope。保留既有source、workflow/main/repo限定、RSA處理、JWT lifetime、tokenscope核對、body/clock窗口、原DO class/key/migration/ledger、兩次slot及六次每日限制。診斷維持封閉enum，新增GITHUB_REDIRECT_REJECTED；build=20261012-manual-redirect-fix。18 Node relay tests PASS，新增301/302/303/307/308拒絕且每案例只1次upstream，無憑證輸出。臨時原生測試套件只在scratch安裝，不改repo package.json/lockfile，不上傳node_modules。機器證據：reports/index-events/github-app-runtime-fix-20261012.json。

需待正式新build header驗證後，只使用同一未儲存晨間job草稿body `{"schedule_slot":"17:20","self_test":true}` **再測一次**；Authorization保留本人輸入的caller值，不讀、不要求重填。只能看到DISPATCH_ACCEPTED後再核對真正App actor/GitHub Run ID/receipt。最後一次evening self-test若仍失敗，不可持續重試/清除ledger/重建DO/放寬限額；先處理精確新錯誤與安全設置，保留正式PAT備援。

尚未Save任何正式cron切換，舊PAT未撤銷且仍需要。MIS所有程式/Token/Secrets/jobs/排程與歷史資料未改。GitHub latest parent/expected_sha保留，不覆蓋botmain。

原生實作依據：https://github.com/cloudflare/workerd/blob/main/src/workerd/api/http.c++ （Request::tryParseRedirect僅follow/manual）
官方Fetch：https://developers.cloudflare.com/workers/runtime-apis/fetch/

