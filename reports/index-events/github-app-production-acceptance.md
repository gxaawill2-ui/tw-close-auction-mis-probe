# App正式驗收

NOT_ACTIVATED_AUTH_REQUIRED。App註冊、安裝、Cloudflare free-account部署／加密secret、installation token實際API、App實際dispatch、cron URL切換及PAT撤銷均尚未驗證，不宣稱完成。

已完成本機測試：RS256 synthetic key簽章驗證、PKCS1/8、JWT時間、固定scope、Installation Token到期重取、200/204、401/403/500／transport failure、repo/permissions/expiry mismatch、授權錯誤、超大本文、任意ref/workflow/repo拒絕、台北跨日及視窗、DO ledger duplicate/in-progress/attempt-limit。synthetic為測試自生fixture，不是真實App。

現有PAT備援首次timer38098926958 eventworkflow_dispatch，2026-10-11T00:35:09Z抵達；08:35:35.209580開始、08:36:44結束、08:36:46.156830出版，RECOVERED_BY_BACKUP、1scan、duplicate=false，data28d1ffd9a0dcbff799b28e904ba9e640b5183375／ack39036180e0a9bb04d404ec573e3bc3e73389784b。planned_for是本站date-slot政策；scheduled_for與delay_seconds為null，GitHub原始預定日期仍UNKNOWN。來源15成功／27、PARTIAL，不把missed_slot=true當GitHub已drop的證明。

App授權完成前現有兩備援維持；PAT所選到期2026-11-10不變，不能宣稱已免人工更新。新增程式不是新timer已啟用的證據。GitHub API／runner共同故障仍存在。


## Stage 4正式增量驗收（2026-10-11）

PR2在隔離分支56bc1c9f完整260Python／67Node（其中DOM/state44）／51Chromium desktop/mobile及WebKit iPhone PASS後合併777c84b7；feature38100709443、main38100842844含公開匿名JSON與三瀏覽器均SUCCESS，原MIS tests-only38100842853與事件38100842944 SUCCESS；Pages38100842781與最新資料38100952566 SUCCESS。完整機器證據stage4-final-verification.json、stage4-public-evidence/acceptance.json及桌機／手機／WebKit PNG保存。10/8candidate blob247dbe4bf7f149950a6196ad59119a65be25599f及SHA不變，未抓MIS。

首頁只列有官方實質異動證據且有收盤觀察日／期間者；49DB事件中4筆官方issuer異動數摘要尚無close date，未來符合者0。來源PARTIAL提示分開，19基金／15ETF與1高2中0低16不足保持；全唯讀research仍保存期程，不冒充homepage合資格事件。

市場量能獨立workflow38100939460在正式main手動完成holiday→公開JSON／source-health／history，未觸發MIS。每日15:05與18:05台北自動累積；普通交易日實際排程尚未到，不宣稱已驗證完整日。10/8部分池1035/1082驗證、缺47，subtotal64,393,939,140元不作全市場值；regular分母與有效20/60日仍缺，formal boolean／占比皆null，門檻PROVISIONAL。今日10/11休市；缺資料交易日顯示尚未確認。

App／relay僅完成程式及synthetic測試，GitHub App草稿已填僅Actions R/W＋Metadata R/O、private、webhook停用，尚未提交或安裝；Cloudflare登入頁未登入。必須本人最後確認新增安全權限與私鑰／caller-secret安全保存後才能繼續服務驗收。现有兩job/PAT維持，08:35真timer38098926958已RECOVERED_BY_BACKUP並出版，17:35本日仍未到；PAT未撤銷且2026-11-10到期仍是必要憑證。native原始預定日期UNKNOWN。
