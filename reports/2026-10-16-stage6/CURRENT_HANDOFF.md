# 第六階段接手紀錄

最新權威分支仍為 `stage4/20261016-fugle-probe`，以遠端 HEAD 為準。起點 adcd926；第一個第六階段 Commit 0df864cb920e02b08f1bb43b92c577618fa1f8be。本文件與後續實作將持續提交同一分支，不要從本機舊 live-shadow 工作目錄覆蓋。

## 結論

10/16 真實結果仍：1967 股票，1938可計算（98.53%），29不可計算，公開研究4609/6228/1235共3檔，VERIFIED0。5546有可能漏選但只能私有UNKNOWN。13:35～13:40發布可信股票的目標未達成，正式部署仍未通過。

## 本輪完成

- 四檔既有私有資料在新 Runner 38885972149恢復並重新分析，新增行情請求0。6228/5546的同一serial，Quote時間比Trades/MIS早整整3分鐘；不能自行正規化時間。
- 4609截止組及收盤資料吻合；1235截止前最後組單價唯一，較早同微秒多價不直接影響此價判讀。來源完整性/統計契約未釋出，不能提高VERIFIED數量。
- 修補 stage3_ticks 的未文件化 serial tie-break假設。LIVE預設不挑最大serial；多價截止組拒絕，Synthetic契約才可明示測試該排序。
- 修補更新價格時舊查核被丟棄後可能不再排隊。另補跨Runner私有請求預算、原始proof恢復及重新追平journal後才發布，避免新的時鐘版本蓋掉尚未重播完整的資料。
- 加入獨立consumer/唯寫bridge/universe私有交接的可執行隔離程式，以及只規劃不執行的定向C2（最多12檔/2輪/5秒/13:34:50截止）。未改正式collector或任何正式workflow/排程。
- 發現原320筆journal約41.6MB、最大169KB，舊bridge會超98KB/10MB上限。新codec完整還原，最大signed packet46,464bytes，整日壓縮約10.74MB；只將MIS獨立namespace上限調20MB，Fugle仍10MB。600事件上限保留；仍有容量上限，不能承諾所有未來股票永不缺漏。
- 外部桌機真實頁面成功讀到3檔、1938/1967、29未知並驗證排序。合成2099-01-06完成RESEARCH_ONLY→UNKNOWN→撤回、舊版本409；桌機頁自動讀入撤回版。不是實體手機驗收。
- 原11:20富果Run38845027079已成功結束，12個控制觀察及3個候選診斷都有完成、總84次請求；原暫存已清除，不與後來14個可恢復bundle混淆。
- 讀到既有17:50官方核對：1830一致、0不一致、137無結果；三研究候選收盤均MATCH。這不證明P_before。
- 60個私有物件再次讀回並驗hash；第一寫入10/16 13:06:22，依7日程式推估10/23 13:06到期，建議10/21前匯出。跨Runner恢復不是長期匯出。本機匯出受URLError限制，未做不實備份聲稱。

## 隔離 Worker 與憑證

同一個 `tw-tail-stage4-20261015-test`，未重建。Cloudflare Git Integration 仍追蹤既有 `stage4/20261015-live-shadow`；只在該分支追加3個精確白名單檔案（worker、MIS bridge、codec），以CAS保護原HEAD，部署 Commit `a0f6cc587d52acfa1245cc57b8f82ff19368c383`。Build success、Version `551b8600-7dc7-41dd-9c8e-ad3fe16471c3`。其餘研究與測試仍存本主隔離分支。

沒有修改HANDOFF_REVISION、Key、publisher Secret、namespace/migration、正式relay或正式路由。bootstrap原有邏輯保留既有writer。更新後真實頁面18:30:22讀回同一版本1792129307272000，研究內容未遺失。codec健康與憑證更新後雲端驗收再由獨立Runner確認，結果看最新遠端報告。

MIS_BRIDGE_TOKEN仍未設定，不能冒充橋接已啟用。正式Environment main admission也未擴大。LIVE_CONTRACT.live_release與ALLOW_LIVE_VERIFIED仍false。本機臨時解封writer已清除，沒有把明文放入Git或報告。

## 測試與限制

本機完整Python422項、Node119項PASS（Node包含真實本機workerd）；真實雲端/桌機分開記錄，不用PASS數量代表已正式上線。正式補丁在最新main a8f25945的暫存副本apply/reverse後逐位元還原；正式probe/workflow blob未變。

`FORMAL_INTEGRATION_REVIEW.md` 是具體待批准清單；`proposed/independent-consumer.yml.proposed` 不在.github/workflows，尚無每日正式串接。不得將整個隔離分支合入main。

尚未完成：來源完整性與三分鐘衝突官方釐清；私有MIS bridge新Secret及正式journal/獨立consumer啟用核准與真實交易日驗收；實體手機；持久私有長期匯出或30日保留實測。

來源問題草稿僅存文件，未寄送任何訊息。尚未取得向第三方再散布富果資料的許可，公開端仍只收MIS衍生研究欄位及非原始診斷。

## 續作

1. 先git ls-remote確認HEAD和最新報告；本機`/workspace/scratch/52ff117b908b/stage6`基於指定最新commit建立，另一`repo`目錄有舊分支及大量工作檔，不可git add全目錄。
2. 讀 `SOURCE_REVIEW_AND_PROVIDER_QUESTIONS.md`、`FORMAL_INTEGRATION_REVIEW.md`、`STORAGE_AND_BROWSER_ACCEPTANCE.md`。
3. 假如需要主線變更，只按白名單、獲批准後重新核對main再套patch。下一交易日是10/19（須依原正式交易日calendar gate確認）；不得回填今天13:25證據或重新擷取全市場。
4. 實體手機只能用真正外部網路驗收；不得用桌機/手機模擬補PASS。保留正式網址。
