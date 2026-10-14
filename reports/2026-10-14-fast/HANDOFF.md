# 中斷續作：快速選股隔離原型

請讀本目錄README.md以及同分支最新commit，不要重做10/14擷取調查，不要覆寫main。

## 不可改

使用者明確要求：不得合併main、部署正式網站、改正式GitHub Actions/cron-job.org、Token或Secret、歷史raw、其他repo/Vercel。Git分支為`fix/20261014-capture-reliability`，上個基線3d35dce，取樣時origin/main c37e21e（狀態資料更新）。請以最新remote核對。

## 已完成

逐批立即fsync保存；completion-order journal；逐檔增量分析與衝突撤回；candidate-only背景查核；PChome公開表普通POST；選用Fugle raw adapter；逐檔時間/缺漏/研究狀態的獨立HTML；晚到官方稽核保持獨立。

301 Python、96 Node、Chromium桌機/iPhone模擬/WebKit模擬、本機HTTP 1→6刷新PASS。原始ZIP SHA256不變。離線first研究13:32:35.533、first收斂+必要量13:33:51.351、last13:34:14.306。正式驗證始終0，不可稱13:35正式目標達成。

6檔PChome在16時後取得，pre及close價格/時間一致但date/fulltick/trial/upstream證明不足；reports/public-source-corrected有比較JSON及raw壓縮檔。Fugle免費60requests/min、5WS訂閱（官方文件），需要Key；沒有設定使用者Key，也沒有實際HTTP測試。fast_gate對獨立finality仍不放行。

## 重現

```bash
python3 -m unittest discover
npm test
python3 fast_selection.py replay /path/to/mis-probe-2026-10-14.zip /new/isolated/output
python3 build_fast_preview.py /new/isolated/output/fast-results.json /new/isolated/output/preview.html
node browser_fast_acceptance.cjs
```

受限環境測試用PLAYWRIGHT_MODULE=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright（1.62.1）；CHROMIUM_EXECUTABLE_PATH=/workspace/scratch/52ff117b908b/fast-browser-runtime/bin/chromium；WebKit2336；已補CJK fonts與WebKit函式庫。包內沒有真機驗收。

未安排的實驗入口：`capture_pre_boundary.py DATE tradable_universe.json NEW_ISOLATED_DIR`；watch入口：`fast_selection.py watch JOURNAL UNIVERSE DATE OUTPUT --check-sources`。過時啟動拒絕。請先避免與正式收集器重複請求，**不要因為文件列命令就立即去跑live**。

## 下一步真正缺項

1. 候選獨立tick／quote的來源契約、同日/常規市場/trial排除/完整tick coverage/finality驗證；不能用supplied validated bool或兩個相同網頁價替代。
2. 在下一交易日證明盤前fsync覆蓋和最後成交，且不增加正式流程API負載。13:24:30預抓可能漏最後數秒新成交，不能當最後成交真值。
3. 公開transport仍未接上：現在本機HTTP刷新不是GitHubPages公開發布。需驗證first_public_observed_at，不能以離線record.received_at冒充。
4. 實測13:30→首候選、首完整驗證、最後公開更新；未驗證要null，不可填假0或固定13:35。
5. 當前GitHubprobe push workflow共享twse-mis-live群組；本次commit用[skip ci]保護正式流程，沒有新GitHubCI。不要未檢查就觸發它。

使用者下一步仍要先收到隔離報告再決定部署；目前建議尚不部署正式verified系統。


## 使用者授權後的 GitHub 同步（2026-10-14）

使用者只批准同步此隔離修復分支，未批准合併main或正式部署。遠端在更新前為3d35dce，沒有其他Work新修改；以expected_sha與force=false安全更新。

已確認程式Commit：c05c0029bb95a4c57be8b04b979c3a59bbb9d8a9。透過GitHub介面建立的Commit metadata與本機1bf2cd1不同，但tree完全相同：f9230fc95b01d597ef069551b09e30f939880e3e。26個已驗收檔案內容完全一致，沒有重新開發。

GitHub已確認包含301 Python、96 Node/前端及瀏覽器驗收紀錄。新的CI沒有執行（skip ci）；不能把空status列表說成CI success。main仍c37e21e，正式workflow/state/Token/Secret與歷史raw均未修改。

下一階段以13:25前最後成交的獨立證明為第一優先：
1. 候選查核取得同日、常規整張市場、排除試撮的完整tick區間，按微秒時間及serial辨識cutoff前最後一筆；不能以分鐘K或網頁最後一列推定完整。
2. 與既有盤前durable保存證據核對，包含最後數秒新成交、同秒多成交、來源掉包/缺頁/快取、沒有新成交等情境；證明不足維持unknown。
3. 收盤獨立確認正常13:30與延後13:33，不能將isTrial或一般lastPrice當成正式close finality。
4. 候選逐檔完成必要成交量/±3%/價格證明後才允許VERIFIED；證據未齐仍research，不因13:40截止放寬。
5. 在隔離環境驗證public transport与13:30→first candidate/first VERIFIED/last public update的實測，目標13:35～13:40，未達成要明示。
尚未進行以上下一階段實作或下一真實交易日，亦未設定任何新Key、排程或live收集。
