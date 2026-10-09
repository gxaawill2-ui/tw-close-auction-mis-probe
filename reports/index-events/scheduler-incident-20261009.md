# 2026/10/9 事件排程事故調查

08:20：NOT_APPLICABLE。事件 workflow 首次加入 main 為40c318a，2026-10-09T10:44:21+08:00，當日早盤槽位尚不存在。

17:20：可取得的58筆schedule執行中沒有此時準時抵達的事件workflow。唯一事件 schedule 為37957502210，created_at/run_started_at=2026-10-09T16:13:06Z（台北10/10 00:13:06）。這是未取得準時執行證據，不是證明GitHub丟棄了一個特定觸發。

該run使用6d3eac214faa371eca48e7a0c384c87942c64c38。tests runner 16:13:10Z；scan job 16:13:24Z；source scan16:13:30–16:14:21Z；publish16:14:21–23Z，資料commit311ef073e218ae23ff057900a04068da049b9489。runner排隊僅數秒，無證據支持concurrency造成數小時延遲。

舊版合併cron20 0,9 * * *且未記錄github.event.schedule，GitHub API未提供預定日期；00:13原始排程槽位UNKNOWN。不能將其SUCCESS寫為17:20準時完成，也不能斷言對應10/9某一槽位。

GitHub官方文件允許schedule延遲及丟棄；服務端送達延遲是可能原因，具體根因未證實。actor為gxaawill2-ui，該run授權成功；無停用、取消或MIS資料commit阻塞的直接證據。MIS資料提交不匹配事件程式push paths。原MIS concurrency各自隔離。

TPEx公司來源錯誤：Unterminated string starting at: line 315 column 104 (char 328678)。來源此前10/9 16:52:46成功。舊程式未保存原始回應、Content-Length或傳輸雜湊，因此不能判定伺服器壞JSON、網路截斷或parser根因；不能將其判為全部下市。新程式對不完整傳輸及JSON做有界重試並保留舊資料。

證據：https://github.com/gxaawill2-ui/tw-close-auction-mis-probe/actions/runs/37957502210
官方說明：https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

實際研究／更新時間：2026-10-10T07:28:34+08:00
