# 接續入口：事件備援已啟用，首次定時收據待觀察

更新：2026-10-11T00:11:26.091Z。目前正式程式b6246cff62a37801d5c2c3a10115e6d77496b397未改；不得重seed、重抓10/8 MIS或覆蓋bot較新資料。

## 自動化已啟用

cron-job.org 8618691（08:35）／8618694（17:35），Asia/Taipei，每日；固定POST index-events.yml、ref main、schedule_slot08:20／17:20、self_test=false、timeout20秒、saveResponses=false。兩筆Enable儲存並reload驗證；新獨立repo Actions憑證由本人輪替貼入，實際HTTP204、event runs38097264694／38097218020 SUCCESS。242 Python、42 Node、49排程子集PASS；沒有來源或MIS請求。不要重建jobs或重新要求登入／範圍授權，除非觀察到session或credential失效。

## 下一個必要驗收

首次timer今日2026-10-11 08:35／17:35尚未觀察。只讀GitHub workflow_dispatch與state/events/scheduler/slots、attempts；確認正常來源掃描→data commit→published ack，或原生已完成後DUPLICATE_SUCCESS。不要把HTTP self_test=true當source scan。native原定日期與scheduled_for仍UNKNOWN；clock cron到達不證明準時。併發／延遲／lease/CAS已49單元測試驗證，live故障沒有發生就不寫實測PASS。

## 憑證安全

先前tool讀取whole dialog包含hidden Raw request秘密，已公開告知並由本人Regenerate。新秘密未讀取。禁止Advanced／generated-token頁full snapshot、whole dialog allTextContents、headers Value、clipboard、credential截图；用既有句柄先導航已驗證安全Common/detail再觀察。HTTP狀態只能getByText精確204／401／403 isVisible，不讀Raw request；範圍只此repo Actions，Token本身不能限制單一workflow。所選30天到期2026-11-10，需本人安全更新；不得讀或重用MIS憑證。

## 既有功能与剩餘限制

基金研究19筆／15ETF：高1、中2、低0、資料不足16；PROVISIONAL、日期與重要性分開、缺資料不判低。0050高／0051中／0056中／006208不足；first有效as-of與歷史invalid版本保留。固定深色、零按鈕、MIS候選blob及成交量完全不變。MSCI／FTSE再用授權、TPEx完整ETF主檔／持續掛牌、未來基金實際委託時間仍PARTIAL／UNKNOWN；沒有可靠免費替代來源就維持限制，不重做已完成研究。完整證據continuation-20261010.md、backup-activation-20261010.json、deployment.json。
