# 排程備援與驗收

原定08:20／17:20保持；拆為20 0 * * *、20 9 * * *以記錄具體cron時鐘槽位。GitHub不提供預定日期，scheduled_for/delay_seconds保留null；planned_for是本站政策，origin_date_verified=false。ON_TIME只是政策窗口內抵達，非證明GitHub原定日期。

native窗口15分鐘；外部explicit slot HTTP窗口15–60分鐘。成功收據擋重複，30分鐘lease防重入，git fast-forward push作CAS且最多3次。每槽位最多2次來源掃描；HTTP全域60次、逾時10秒、資料6MiB。失敗不清空歷史。lease正在使用時外部僅健康檢查。

晚到native不可冒認原定日期。若資料超過2小時未更新，使用實際抵達時間六小時bucket獨立補更新，每bucket至多一次成功；它不補認任何08:20／17:20槽位。原排程尚可繼續更新，未因外部未啟用而全面拒絕延遲更新。

收據位於state/events/scheduler/slots與attempts，包含實際run建立／runner／scan起訖／成功push後確認時間、來源摘要、出版commit、policy delay與未知scheduled date。FAILED明確釋放lease；部分來源失敗為PARTIAL，不是來源完整。未完成槽位missed定義為備援檢查時無成功收據，不等於證明GitHub漏觸發。

外部服務狀態：NOT_ACTIVATED。已實際開啟cron-job.org，顯示Sign in。未存取、變更MIS token或排程。兩個禁用的完整job範本位於config/index-events/cron-job-backup-template.json；必須由使用者登入及建立新的單一repo Actions read/write憑證，存於cron-job.org Authorization header，才能啟用08:35／17:35。不得將範本當成已部署的獨立備援。

38個新測試涵蓋正常、延遲、跨日、未完成、備援恢復、重複、lease owner、重試上限、401/403/400/timeout、ETF模型和截斷JSON。真實HTTP dispatch及分支完整瀏覽器驗收待CI，將補入deployment。未來native排程抵達不可提前宣稱已測。
官方cron REST格式：https://docs.cron-job.org/rest-api.html

實際研究／更新時間：2026-10-10T07:28:34+08:00
