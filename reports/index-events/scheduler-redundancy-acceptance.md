# 排程收據、備援與正式驗收

更新：2026-10-10T00:23:50.384Z；程式b6246cff62a37801d5c2c3a10115e6d77496b397。

原08:20／17:20保留，cron拆成20 0 * * *、20 9 * * *以辨識時鐘槽位。GitHub不提供某次native執行的原定日期，因此scheduled_for與delay_seconds為null、origin_date_verified=false；planned_for／policy_completion_delay_seconds只是本站政策窗口。舊run37957502210來源槽位UNKNOWN，不把00:13 SUCCESS當作17:20準時。詳scheduler-incident-20261009.md。

native政策窗口15分鐘；外部explicit slot備援窗口15–60分鐘。日期×slot身分、成功收據、30分鐘lease、git fast-forward CAS（最多3次、網路45秒）、每槽最多2次來源掃描防重複。超時lease或確認原同repo同workflow/main owner已終止才可接手；查owner用API至多2次／10秒，401/403/timeout為UNKNOWN，不能偷取仍活躍lease。CAS每次重新讀main與source-health，避免晚到native在備援完成後重掃。六小時late-arrival bucket只補資料，不冒認原定槽位。

全部收據位於state/events/scheduler/slots及attempts：run建立時間、runner、scan起訖、成功push後published_at、source_health、出版commit、github_event_schedule、missed／duplicate、未知預定時間及結果。MISSED意為備援檢查時沒有成功收據，不能證明GitHub丟棄觸發。PARTIAL是部分來源成功，不能當完整來源涵蓋。來源全域60次、每URL至多2次、10秒逾時／6MiB body；scan job15分鐘；失败保留舊資料。

## 真實執行證據

- main CI38007718767 SUCCESS：242 Python、42 Node；實際scan→CAS data b061e45125e3bdbc5f72a42eb8e3fd595327542a→成功ack dfd003f4285fa8c609aff7f8f9b766a097643dd1，來源15成功、PARTIAL。
- runner08:08:35、scan08:08:44.538487–08:10:08、published08:10:10.565471（Asia/Taipei）。這是ADHOC_PUBLISHED，明確不是native準時排程驗證。
- HTTP實測driver38007381758 SUCCESS，child38007391304 SUCCESS；實際POST固定event workflow dispatcher，self_test=true，只測收據，不抓來源、不寫main、不dispatch MIS。使用短期CI token，測通HTTP不等於cron-job.org已啟用。
- 49個新增Python回歸測試（193→242）覆蓋正常17:20、延遲、跨日、未完成、備援恢復、同時重複、延後native、lease/CAS競爭、owner查詢權限錯誤、重試上限、截斷JSON及評級as-of；全部PASS。併發狀態／錯誤以可重現隔離測試，不宣稱live故障已發生。
- 程式Pages38007718622、最新資料／收據Pages38007864341 SUCCESS。真實native晨間38029017422、晚間38063666867已晚到抵達，原定日期UNKNOWN，準時性不宣稱PASS。

## 外部服務最新驗收



## 外部備援已真正啟用（2026-10-11T00:11:26.091Z）

使用者再次Regenerate並親自貼入Save兩job後，8618694晚間Test run HTTP204→event-only38097218020 SUCCESS（00:05:10Z）；8618691晨間HTTP204→38097264694 SUCCESS（00:05:55Z）。242 Python＋42 Node PASS；49項receipt reliability子集PASS（屬242之內），scan/source-smoke/public-acceptance均SKIPPED。這是cron-job.org實際服務HTTP，不是先前CI短期Token替代驗證；只查精確status可見性及GitHub run/job/log數量，沒有讀新秘密、Raw request、headers Value、clipboard或generated-token頁。

兩job均Enable＋Save並reload確認true，saveResponses=false，Asia/Taipei；正式body恢復self_test=false、固定index-events.yml/ref main，slots08:20／17:20。清單顯示今天08:35／17:35 next execution，非敏感畫面event-backup-enabled-1791677316657.jpg。既有MIS工作／Tokens／Secrets未動。本站19基金event正常、0050高暫定／0051中暫定／0056中暫定／006208不足、日期可信度分欄、無按鈕；10/11休市不顯示10/8當日名單，10/8candidate blob247dbe4bf7f149950a6196ad59119a65be25599f不變。

重要範圍：首次真正timer08:35／17:35尚未到達／觀察，不能把self_test=true成功寫成production source scan、RECOVERED_BY_BACKUP或DUPLICATE_SUCCESS實測。原始native預定日期仍UNKNOWN；兩clock cron晚到送達先前已證實，準時性不冒稱。下一步僅讀actual workflow_dispatch與date-slot receipts／publish ack；jobs已自動運作，不需使用者每天操作。事件憑證保留30天選定到期2026-11-10，需要本人安全更新，不能承諾無期限免維護。GitHub API／runner是共同故障點，外部timer不等於獨立運算備援。

先前秘密觀測失誤已告知使用者並要求輪替，本報告保留事件歷史；新憑證config已HTTP驗證，沒有秘密寫入Git。來源授權、TPEx完整主檔、未來基金實際委託時間無新可靠來源，保持PARTIAL／UNKNOWN，不重做研究或捏造解決。
