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
