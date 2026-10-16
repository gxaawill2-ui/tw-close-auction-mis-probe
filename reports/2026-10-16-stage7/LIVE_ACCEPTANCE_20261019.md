# 2026/10/19 一次性隔離影子驗收準備

官方TWSE民國115年休市表未列10/19；該日星期一，依公告日曆是預定交易日。臨時休市須當天再查，不能當成無條件保證。
來源：https://www.twse.com.tw/holidaySchedule/holidaySchedule?response=html&queryYear=115

已建立ChatGPT一次性工作（Asia/Taipei）：10/19 13:00啟動準備好的影子workflow；14:55核對安全報告與既有官方盤後結果。不是修改正式GitHub/cron-job.org排程，不保證任務或Runner毫秒準時。

啟動方式：先取隔離分支最新HEAD、讀CURRENT_HANDOFF，確定當日沒有同一workflow/正式新consumer已在運作，再CAS、force=false寫stage7_live.request.json：

```json
{"scope":"ISOLATED_ONE_OFF_EXISTING_FORMAL_ARTIFACT_SHADOW","trade_date":"2026-10-19","requested_at":"<真正當下時間，不回填>"}
```

不要現在寫這個觸發檔。程式只准10/19 12:45～13:40開始；錯日/太晚立即拒絕。新workflow是分支push事件，無schedule，沿用stage4-fugle-isolated既有Secret。未修改正式workflow或Environment。

## 會做的事

- 只唯讀既有正式state與同日正式Artifact，核對日期/來源run/下載SHA，不呼叫MIS、不dispatch正式任務。
- 不硬編今日10/16的正式run id；從同日既有正式狀態選擇來源。重複/不同發布者已存在時保留原結果。
- 使用同日保存的13:25前比較與正式收盤研究；全部Artifact重播完畢才啟動背景驗證/第一次發布，防止重啟的半份資料蓋掉新版。
- 少量候選與延後收盤私有佇列使用既有Source/Session：2 workers、最多12檔、每指紋2次，整日最多160次、至少1.3秒起始間隔，先保存每次預算再發HTTP。不是新增全市場擷取。
- 每檔獨立更新，來源矛盾保留UNKNOWN或撤回，不阻擋其他股票；原始行情只進私有暫存與私有Worker。
- 程序運作至14:30；不因正式Runner先結束被清掉。有限嘗試用完後不會憑空持續取得新資料。
- 若確實產生私有證據，後續archive job固定30日複製；另一recover Runner只讀封存，核對雜湊/manifest。使用本次已真實通過的程式，不另開服務。10/19資料成功保存與否要當日run證據，不能預先寫PASS。
- 14:55工作讀既有14:50官方核對；未產生則標待確認，17:50仍由正式既有機制處理，不能冒稱已完成。

## 必須各自記錄的時間與結果

| 欄位 | 判準 |
| --- | --- |
| source_run_id/artifact_id/hash | 今日原正式來源，不重新抓全市場 |
| P_before | <13:25:00最後實際成交，不能填昨收/0 |
| P_close | 正式成交及官方價格核對分開 |
| first_research_at | 程式當下真正看到候選 |
| first_cloud_write_at | Worker寫入回條 |
| first_api_read_at | 真正匿名API讀取，非手機 |
| browser_observed_at/version | 桌機或手機各自紀錄 |
| physical_phone_seen_at | 本人實體手機回傳，未取得留空 |
| research/UNKNOWN/VERIFIED/coverage | 不混算，不以沒有結果當零候選 |
| archive copy/recovery | 真實當日job、固定到期、全物件SHA |

安全輸出：stage7-live-safe-report/、stage7-copy-report/、stage7-recover-report/；禁止上傳temporary私有根目錄、Source原始檔或密鑰。workflow只給contents:read/actions:read。

## 尚不能承諾

正式journal尚未批准，本次影子工作仍要等Artifact，13:35～13:40不是保證時間。來源契約未釐清時LIVE_CONTRACT與Worker release仍false，預期VERIFIED可能仍0；不是啟動影子工作就解決了逐筆完整性。實體手機、真實交易日逐批延遲及持續驗證都尚未發生。

後續私有archive/recover job採!cancelled()及直接依賴結果判斷，不以整串success()跳過已成功封存的恢復；本人手動取消會停止後續。參考：https://docs.github.com/en/actions/reference/workflows-and-actions/expressions 。目前僅審查控制語意，10/19主job真實失敗/取消尚未發生。
