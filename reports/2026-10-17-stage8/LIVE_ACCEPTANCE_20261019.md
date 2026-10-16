# 10/19 MIS影子驗收準備（尚未發生）

官方115年休市表未列10/19，該日星期一，預定正常交易；臨時休市必須當天再次查。來源：https://www.twse.com.tw/holidaySchedule/holidaySchedule?response=html&queryYear=115 。

沿用既有ChatGPT一次性任務：13:00 `6ad2096242f881918c7a2e125ed74d50`、14:55 `6ad2096488148191928517d014ba5025`。不重建、不更改正式cron-job.org。任務要求MIS多次確認，不再要求富果VERIFIED。

13:00先讀公開隔離分支最新 `reports/2026-10-17-stage8/CURRENT_HANDOFF.md`，確認正式probe已進入in_progress且沒有正式probe等待Runner。至13:05仍未可用則不啟動隔離job。檢查同日既有影子任務，避免重複。只CAS、force=false更新既有 `stage7_live.request.json`；scope仍為`ISOLATED_ONE_OFF_EXISTING_FORMAL_ARTIFACT_SHADOW`、trade_date=2026-10-19、requested_at=真正當下時間。此分支的既有影子workflow改為只執行 `stage8_mis_shadow.py`；移除富果與Worker Secret使用、雲端發布及archive後置job。這是**隔離分支專用workflow**，正式workflow完全不變。既有10/16私有封存與到期提醒不受影響。

影子job僅讀當日正式Artifact，原始下載與中間分析都在TemporaryDirectory，不進公開Artifact；只上傳safe-report。使用現成公開MIS引擎作同日原版影子診斷，不誤稱Private V2已在該public runner運作。Private V2於14:55由Work讀取本私人分支並對同一當日Artifact離線比對；原始資料不足就保持UNKNOWN。兩者無MIS新請求、無正式寫入、無富果門檻。

必記：正式run與job真正開始/結束、快照數、同日Artifact ID/hash/接收/保存/計算時間；原站JSON published_at與匿名HTTP實際讀到當日結果時間；可計算/UNKNOWN/候選數；延後收盤證據是否兩次一致；14:50官方核對是否完成及逐候選MATCH/MISMATCH。API取得不等同實體手機顯示。

目標13:35～13:40要以正式JSON與真實外網讀取紀錄判斷；Artifact上傳時間不等於網站更新時間，也不能用歷史回放時間替代。若當天無足夠延後收盤樣本，C2仍待實盤；本輪未批准C2正式啟用，因此10/19不會因這次隔離工作自動修好正式5546類型。不得另起第二套全市場。

尚未進行：10/19啟動、擷取、準時公布、官方核對、實體手機及新C2真實請求。現況只能是READY_FOR_READONLY_SHADOW，不是PASS。
