# 富果 Key 到期與安全更換

現有 Key 到期：2026/11/14 00:00（台北時間）。11/13 結束前要完成替換及真實連線測試。
11/11 已建立提醒。本次沒有重申請或重設現有 Key。

1. 在富果原帳號建立替代 Key，確認免費方案及新到期日；涉及新條款時由使用者確認。
2. 僅更新 `gxaawill2-ui/tw-close-auction-mis-probe` 的 Environment `stage4-fugle-isolated`、Secret `FUGLE_API_KEY`。不要放進聊天、程式、Commit、一般變數或公開 Artifact。
3. 在隔離分支 `stage4/20261016-fugle-probe` 新增或更新 `stage5_key_check.request.json`，只寫日期與非機密測試識別。這會觸發獨立的 5 次連線測試；不會啟動正式 MIS，也沒有每日排程。
4. 確認 5 次真實 HTTP 200、當日日期、代碼及實際成交必要欄位；401/403/429 不連續重試。這個 PASS 只表示連線正常，不能視為 VERIFIED。
5. 新 Key 確認成功後，再於富果撤銷舊 Key。失敗時保留尚未過期的舊 Key，先修正隔離 Secret；不能把 Key 貼到紀錄裡除錯。
6. 更新到期提醒與接手文件，只記錄名稱、到期時間、Secret 位置、成功 Run 與 Commit。

新增測試觸發 workflow 不包含任何 Key 值，也不會在本次提交時重新測試或更換 Key。
