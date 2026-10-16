# 正式修改最小審核清單（均未實施）

正式main核對a8f25945f94ce45300d5e97c9d6a7f622586663e。最新probe/workflow/網站原始blob及SHA256見patch-rollback-latest.json；正式有bot更新時應重新取最新main再比對，不能整檔覆蓋。不要合併整個隔離分支。

## 可逐項批准的具體差異

| 項目 | 正式檔案/權限 | 新增排程 | 目前證據 |
| --- | --- | --- | --- |
| A journal hook | probe.py、stage5_capture_journal.py；production-journal-hook.patch | 無 | 本機/Runner故障隔離、寫入延遲、原輸出排序、apply/reverse逐bytes還原 |
| B 唯寫bridge | .github/workflows/twse-mis-probe.yml；production-write-only-bridge.patch | 不改既有cron及dispatch | 預設STAGE7_JOURNAL_ENABLED=false；只傳已保存批次，不新增MIS |
| C 獨立consumer | 新增 .github/workflows/stage7-independent-consumer.yml，內容見independent-consumer.yml.proposed | workflow_run既有正式live開始事件，無新cron | 單一concurrency，160次持久預算，至14:30；斷線恢復/舊版本拒收已隔離測試 |
| D 同網址即時區 | docs/index.html + docs/live-tail.js/css + docs/live-tail-config.json；formal-site-read-only-panel.patch | 無 | 檔案只存在proposed；DOM/日期/合成拒收/舊版本/撤回測試與patch回滾通過，預設enabled=false/live_released=false |
| E 定向C2（獨立選項） | 正式collector增加少量請求，精確實作尚須另審 | 不增全市場排程 | stage7_retry.py只產生計畫、不發HTTP；最多12檔，每檔每日2次，13:34:42後不啟動、13:34:50前收完 |

D沿用現有隔離逐檔renderer，在正式同網址頂部新增獨立驗證區，保留既有研究、事件及官方核對。讀取既有隔離Worker公開API，不帶任何憑證；不改DNS、Pages位置或舊資料。啟用需另同意把config.enabled設true。正式VERIFIED顯示仍須來源與Worker解除gate的證據及單獨審核，不能只改config旗標。此patch尚未套正式，也未宣稱正式端到端驗收完成。

## B/C 必要新權限（未建立）

1. 一個新「唯寫MIS bridge」隨機Token，保存於既有隔離Worker的MIS_BRIDGE_TOKEN及專用GitHub Environment stage7-mis-bridge的STAGE5_MIS_BRIDGE_TOKEN。只能寫私有MIS journal，不能讀私有富果、發布公開結果。正式collector不拿富果或publisher憑證。
2. 專用stage7-mis-bridge Environment允許正式main job；先驗證admission再綁定正式workflow，否則正式job會在步驟開始前被擋住。它只有上述唯寫Token。
3. 專用stage7-tail-consumer Environment允許獨立main consumer workflow，使用既有FUGLE_API_KEY、STAGE5_PUBLISH_TOKEN、STAGE5_DECISION_KEY值；不申請/輪替現有Key。這是新增存取權，須明確批准。checkout固定已審核056dd9757bbce4febd04409858ffa15d239260c9，不追浮動分支。
4. 需確認帳號Runner並行容量足夠。隔離流程獨立concurrency，不使用twse-mis-live；正式capture仍由既有run_control與cron-job.org主備去重。workflow_run可能收到多個備援事件，singleton與持久預算會避免並行重複驗證，但正式事件/Environment admission仍需實際雲端驗收。

未改任何正式Token/Secret、Environment admission、cron-job.org或正式排程。舊stage5提案把全部行情憑證交給正式job的workflow區段，已被本份唯寫提案取代；不要使用舊workflow hunk。

## 風險、剩餘驗收與回滾

- 每批增加本機兩次fsync，磁碟延遲可能增加；既有合成Runner P95約2.1ms不是實盤保證。例外停用journal，正式原流程繼續。
- 背景bridge或consumer錯誤不進入collector主程序；bridge隨正式Runner結束會被清理，consumer在另一Runner仍可讀已交接journal至14:30。不能保證最後一批一定在Runner結束前交接；需真實交易日核對320類批次覆蓋、失敗警示與Artifact後備。沒有把這一點寫成已解決。
- 雲端MIS bridge尚缺新Token，所以只完成本機真正workerd的完整合成流程；目前不能說正式bridge雲端逐批傳輸已驗收。來源完整性/180秒矛盾未解，VERIFIED gate不解除。
- Runner存活至14:30不等於每檔持續有新證據。隊列有有限次數/請求總預算；collector結束後無新MIS批次，不能憑空製造後續成交。C2另待批准。
- A/B/C停用STAGE7_JOURNAL_ENABLED並停用獨立consumer，即回原正式擷取；預設關閉。完全撤回時僅反向apply指定hook/bridge patch和移除新consumer，不回滾當日/歷史資料、不改既有排程。先停止consumer再停用bridge權限。
- D設enabled=false停止新讀取、原網站照常；必要時只反向site patch。三份patch均在臨時副本apply/reverse並校驗原檔bytes完全一致，見patch-rollback-latest.json。
- 同一隔離Worker新增封存區不影響上述正式路徑；不應為回滾UI而回滾掉已完成的30日私有封存功能。

目前沒有要求一次批准整個分支。A/B/C/D可以分開同意；E是額外行情請求，單獨處理。寄送富果問題草稿亦需另行同意。
