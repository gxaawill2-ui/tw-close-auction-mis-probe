# App正式驗收

NOT_ACTIVATED_AUTH_REQUIRED。App註冊、安裝、Cloudflare free-account部署／加密secret、installation token實際API、App實際dispatch、cron URL切換及PAT撤銷均尚未驗證，不宣稱完成。

已完成本機測試：RS256 synthetic key簽章驗證、PKCS1/8、JWT時間、固定scope、Installation Token到期重取、200/204、401/403/500／transport failure、repo/permissions/expiry mismatch、授權錯誤、超大本文、任意ref/workflow/repo拒絕、台北跨日及視窗、DO ledger duplicate/in-progress/attempt-limit。synthetic為測試自生fixture，不是真實App。

現有PAT備援首次timer38098926958 eventworkflow_dispatch，2026-10-11T00:35:09Z抵達；08:35:35.209580開始、08:36:44結束、08:36:46.156830出版，RECOVERED_BY_BACKUP、1scan、duplicate=false，data28d1ffd9a0dcbff799b28e904ba9e640b5183375／ack39036180e0a9bb04d404ec573e3bc3e73389784b。planned_for是本站date-slot政策；scheduled_for與delay_seconds為null，GitHub原始預定日期仍UNKNOWN。來源15成功／27、PARTIAL，不把missed_slot=true當GitHub已drop的證明。

App授權完成前現有兩備援維持；PAT所選到期2026-11-10不變，不能宣稱已免人工更新。新增程式不是新timer已啟用的證據。GitHub API／runner共同故障仍存在。
