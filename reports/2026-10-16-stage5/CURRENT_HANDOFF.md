# 第五階段最新接手紀錄 — 2026-10-16T13:49:13+08:00

## 目前結論

真實MIS研究結果已在13:34:40發布到隔離Cloudflare，3檔候選都有後續富果私有查核，VERIFIED仍0。可信股票於13:35～13:40發布的目標**未達成**；研究發布目標已達。
正式上線未通過：來源完整性/同微秒排序、29檔不可計算、正式每日journal串接、實際桌機/實體手機仍有缺口。
不得把同價、HTTP200、合成測試、RESEARCH_ONLY冒充VERIFIED。

## 最新有效成果

遠端分支 `stage4/20261016-fugle-probe`，實作有效Commit `a7fae1cbe27006a695dff832899e7739dea7042c`；最新報告看分支HEAD。
本機git仍在舊live-shadow分支且有工作檔，不要直接git add全部或git push。使用明確白名單更新指定隔離分支，避免觸發另一分支的自動建置。
主網站 https://gxaawill2-ui.github.io/tw-close-auction-mis-probe/ 保留，未部署新正式版。
Worker仍為同一個 `tw-tail-stage4-20261015-test`，原部署source `0ce8a58df9549651e45a74bdd2a5f529c4b8ddf7`，未重建，未碰正式relay。

## 今天實際結果（不是合成）

| 項目 | 實際結果 |
| --- | --- |
| 股票池 | 1967 |
| 研究可計算 | 1938；其餘29不可排除漏選 |
| ±3%研究候選 | 3 |
| 完整VERIFIED | 0 |
| 首次研究計算 | 13:34:38.998282 |
| 首次真實研究雲端寫入 | 13:34:40.743 |
| 匿名API讀回同version/hash | 13:34:41.050889 |
| 首次VERIFIED／實體手機 | 未取得 |
| 官方價格核對 | 截至本紀錄尚未觀測，等既有盤後流程，不可代跑 |

正式MIS Run `38853538676` / Job `116819837674`：13:00:40啟動，正式capture 13:34:17.128結束，Artifact `12026934850`於13:34:36.918573被隔離observer接收；正式state completed但status=partial，不代表全1967皆可計算。
研究publisher Run `38854918750` / Job `116824118632`，source `6563dfbfe62a77f77b8790640a13931d1809ceac`，已success；只讀既有正式Artifact，MIS/Fugle額外擷取均0。
`real-mis-cloud-publication.json`含實際時間及外層Artifact SHA256。仍有完整Artifact等待限制，不是正式即時journal，不可說第一個完成的批次已直接對外發布。

## 真實富果私有保存：已通過不同Runner恢復

私有控制Run `38854461494` / 擷取Job `116822705363` / 恢復Job `116829234513`，source `c68a913905c6acdf302d7af8377d73f43df4308a`，兩個job都success。
2330/6488兩檔在13:24、13:25、13:30、13:33、13:35，共10份bundle。13:24:03/07與13:25:18/22皆有真實私有manifest回條；13:30:18/22的樣本已出現NORMAL_CLOSE分類。沒有真實延後收盤/無新收盤成交樣本，不得冒充該兩類也已實盤通過。
13:35:39.319585，第二Runner成功恢復10份真實raw並驗證hash，未公開raw。詳 `real-private-raw-recovery.json`。

三檔真實研究候選也已個別查核並寫入隔離結果：

| 股票 | 查核Run | 雲端更新（台北） | 真實診斷 |
| --- | --- | --- | --- |
| 4609 | 38856613147 | 13:37:52.190 | 5筆完整頁，筆數/量吻合，正常收盤；來源契約未釋出，RESEARCH_ONLY |
| 6228 | 38856613147 | 13:38:02.409 | 5筆完整頁，筆數/量吻合；同微秒多價格、quote head衝突，UNKNOWN |
| 1235 | 38857068920 | 13:41:47.521 | 11筆完整頁，筆數/量吻合；同微秒排序未明，UNKNOWN |

第三檔是在13:40之後補查，不能算目標時間內完成。這些診斷不是完整VERIFIED。
第一個候選任務source `0ebfc35133f8c7e9a940dc5fc865f4189da3f2b1`，實際Fugle請求6；剩餘一檔source `6e8ec62d4569e30fffcff06dd653f6a2f0f7d3ac`，實際請求3。後者明確排除前兩檔，沒有重做已查候選。
兩任務採10.1秒共享起始間隔，每分鐘最多6次新增Fugle請求；不與私有控制時段重疊。加上原Source每分鐘最多47次，總量仍保守控制在53次/分鐘內。
候選真實raw後續於新Runner Run `38857337896`、13:44:31.217910全部3份恢復成功；沒有富果Key、沒有Fugle API呼叫，只從已授權私有vault驗證恢復。詳 `real-candidate-raw-recovery.json`。

所有raw只存需Token/HMAC的私有DO及repo外0700/0600暫存。公開Artifact/Repo只保存safe metadata，公開研究價格仍只來自MIS。7日保留自當日私有namespace首筆寫入起計；需更長保存時，於到期前匯出到已授權持久私有位置。

## 原富果任務：仍不可停止或重啟

Run `38845027079` / Job `116793492688`，固定source `2443ce0f4028b25e18cf207b8490e212e7d75c2d`。11:20啟動，原版LocalVault不能動態補接新Secret；原暫存約14:29:30結束清除。新任務不是原暫存的回收。
截至13:27重整GitHub頁面，原任務仍in_progress，但只看到11:20控制日誌，未觀測到13:24/13:25新紀錄；不能只憑in_progress聲稱所有時點正常。
其sanitized day-report預期14:29後可讀；15:35檢查control_capture_error_type、control_captures及candidate_audits，確認控制程序是否提前失敗或是日誌問題。**禁止重啟、取消、dispatch或補造時點。**
原任務最多160次；私有控制最多30次、兩輪真實候選實際共9次，因此本輪新增實際Fugle請求39次。其他恢復/發布任務都0次Fugle。

## 憑證、傳輸及保護

使用者13:04:36已同意特定writer交接與隔離驗收；13:05已將既有 `STAGE5_PUBLISH_TOKEN` / `STAGE5_DECISION_KEY` 存入 `stage4-fugle-isolated`。
Environment仍只允許本隔離分支，1 branch/0 tags；未新增main admission。FUGLE_API_KEY仍10:42版本，未變動，未重建Key。repo外本機明文writer暫存及瀏覽器明文變數均已清除。
403的數字原因1010；誠實專案User-Agent後外部Runner HTTP200，沒有改Cloudflare安全設定或瀏覽器指紋。真正Publisher及私有合成canary Run38854028544於13:06通過；不同Runner合成恢復Run38854197791於13:08通過。這些合成時間不能填真實股票欄位。
Worker `ALLOW_LIVE_VERIFIED=false`、Source contract未釋出，兩者都維持關閉。
正式main會由既有bot更新state，不能說main SHA不變；已比對probe blob仍64f4e90dde9e17cc3ff5ebf3779ac040e69b8bd4、workflow blob仍f4e74ee3b3080a9e6ae0aef2f3e1c759384c9ecb。未改正式collector/workflow/cron/Token，未重跑MIS，未另開全市場擷取。

## 測試與正式整合提案

Python401項通過；Node先前117項通過，本輪未改JavaScript。真實雲端驗收與上述真實行情證據另列，不用PASS數代表上線。
獨立Runner benchmark38851927830：2,000檔/40批/10輪/400事件驗hash；fsyncP95=2.104ms、首批最大5.11ms；journal開關舊raw逐位元一致。
`patch-rollback-check.json`確認暫存副本實際apply/reverse後回復原始bytes，沒有套用正式。
`proposed/production-journal.patch`與提案YAML固定shadow至c68a913905c6acdf302d7af8377d73f43df4308a，已有403修正及強制私有canary；尚未套用。
正式journal hook、Environment main admission、正式workflow/collector及每日排程整合、正式發布全部仍須另行批准。今天的「同意」沒有涵蓋這些。
本輪是明確單日隔離任務，不能宣稱明日起每天都已自動接上正式網站。

## 待辦與提醒

1. 釐清可信成交區間、同微秒排序及筆數/量語意，不能因價格相同就解鎖VERIFIED；4609也不能只靠經驗相等放行。
2. 盤後查29檔MIS不可計算原因、原Fugle控制日誌缺口及既有官方核對，不能回填偽造13:25資料。
3. 正式journal/每日流程獲批准後，下一交易日shadow驗收，再討論正式部署。
4. 真正桌機與實體手機尚未PASS；先前Worker瀏覽器路徑被安全政策阻擋，禁止代理/換表面或模擬手機冒充。
5. 15:35既有唯讀自動報告已更新全部Run；不新增正式排程。11/11 Key提醒保留；11/14 00:00台北到期，11/13結束前依KEY_ROTATION.md更換。
