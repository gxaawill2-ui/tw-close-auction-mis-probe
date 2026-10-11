# Stage 4接續

work/stage4-20261011：實作已保存，260Python/62Node本機PASS，hosted完整browser及CI仍待。以最新main為準，不能覆蓋39036180之後的事件bot資料；本次只提交新市場namespace／程式與增量report，19基金、49事件資料原樣。

1. 完整hosted Stage4 regression＋browser＋bounded官方source probe，修任何實際失敗；不要重新跑MIS或改其workflow。
2. PASS後合併main，驗證Pages真實events4＋market1 HTML／公開JSON／手機深色零按鈕；更新acceptance/deployment。
3. GitHub App＋Cloudflare Workers Free登入／create install secret安全交接（private key/caller secret本人），完成全部非秘密設定後才暫停必要步驟。App未建立／安裝，CF未部署，不能宣稱免PAT已上線。
4. App服務self_test＋date-slot→published receipt→同既有兩cron改relay→實際trigger→驗證舊PAT不再依赖，最後本人撤銷20932040。現有兩PATbackup保持啟用到切換驗證。
5. 市場只累積完整/partial saved evidence；免費regular denominator與全普通股身份仍待官方交叉核对，history0正式閾值PROVISIONAL，不能為數字完成度編造YES/NO。

現有08:35真timer38098926958已RECOVERED_BY_BACKUP；17:35本日尚未抵達；native原始scheduled dateUNKNOWN不猜。MIS所有tokens／排程／價格量能／候選完全保留。
