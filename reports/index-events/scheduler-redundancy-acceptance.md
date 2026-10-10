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
- 程式Pages38007718622、最新資料／收據Pages38007864341 SUCCESS。真實native08:20／17:20須等GitHub實際抵達再驗收，不能事前或用ADHOC冒充。

## 外部授權狀態與最少操作

**NOT_ACTIVATED_AUTH_REQUIRED**。已開cron-job.org但顯示Sign in；無已授權session，沒有代建服務或讀取／修改原MIS排程與token。config/index-events/cron-job-backup-template.json是两個disabled jobs完整範本，非部署收據。

使用者只需：登入cron-job.org；用新建、只授權此repo Actions read/write的fine-grained credential，將兩個event-only POST job的Authorization header設好並啟用08:35／17:35（Asia/Taipei）。不要將token貼聊天、程式、GitHub報告或重用MIS token。無須日常手動整理；在完成此一次授權之前，外部每日備援尚不存在。

官方API格式：https://docs.cron-job.org/rest-api.html 。requestMethod=1為POST；saveResponses=false；固定index-events.yml/dispatches與ref=main；bounded client retry。獨立的是觸發服務；GitHub運算／API仍是共同故障點，沒有承諾GitHub全面故障時也能掃描。
