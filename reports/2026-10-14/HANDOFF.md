# 新 Work 接手：10/14 擷取修復已隔離驗收

## 優先限制

禁止直接合併 main、部署 GitHub Pages、修改正式 workflow/cron-job.org、Token、Secret 或歷史 MIS。不得碰其他repo/Vercel。使用者要先收到隔離報告，再決定是否正式上線。尚未授權正式部署。

## Git 與成果

- repo：gxaawill2-ui/tw-close-auction-mis-probe
- 基線 main：4f0eb6c7ae238f876d25223d178c88fdee9bf12a
- 修復分支：fix/20261014-capture-reliability
- 程式修復 commit：e25f671a5f49f51b5646a61764acec4238952f3f
- 該commit已存在GitHub；後續交付文件commit可直接從此分支最新HEAD讀取，不要退回舊main覆蓋。
- 調查：reports/2026-10-14/README.md
- 逐批/逐檔CSV：reports/2026-10-14/replay/
- 正式PARTIAL_VERIFIED設計：partial-verified-design.md
- 可直接開啟離線頁：oct14-isolated-preview.html（固定日期時鐘與隔離banner，不是正式即時站）

## 已完成，勿重做

1. 下載並完整分析10/14原Artifact，SHA256與GitHub digest一致：4ea6e228ce86d965584203dfbf5f04d7707a238d74d24cafe133e3994a98cf6f。52個解壓檔均與ZIP原始byte完全相同。
2. 證明B29第一次請求13:33:51.352→13:34:08.415逾時，0.5秒後重試已過B截止。舊sentinel遮住timeout造成摘要timeout=0。
3. C76檔包含B缺50；48檔AC恢復研究、6198/6212無有效實際成交不能補價；另6檔BC恢復。原B缺漏50仍保留。
4. pre24檔無可用實際成交；研究可計算1946/1970、候選6，正式驗證0。
5. 保留實際attempt、分離停止重試原因與統計；C後定向bounded retry、6輪、backoff5/10秒、403/429停止、不足2秒不啟動，pre/close原截止不變。
6. 僅部分批失敗分類PARTIAL；整個必要階段無有效回應/錯日期/壞檔仍FAILED。不是放寬價格門檻。
7. research TARGETED_converged有獨立時間與來源，全部validated=false。fresh server regression保守拒絕。
8. 前端獨立讀live與official，即使candidate API壞掉仍顯示真實擷取/核對狀態。官方RECHECKING與PENDING_RECHECK_ERROR不覆蓋live。
9. 275 Python、93 Node/DOM；原57項瀏覽器回歸；新增Chromium桌機Windows UA、Chromium iPhone13模擬、WebKit26.5 iPhone13模擬皆PASS。Linux測試，沒有Windows/iPhone真機驗收。未做下一真實交易日。
10. 合成集中/分散50缺漏測試97.4619%→100%，假設定向回應3秒；持續失敗仍97.4619%，截止停止。不可當真實市場績效。

## 可重現命令（全離線，原始Artifact只讀）

```bash
python -m unittest discover
npm ci --ignore-scripts
npm test
python replay_capture.py /path/to/mis-probe-38514354547.zip /new/output/path
python simulate_capture_recovery.py
python build_isolated_preview.py reports/2026-10-14/replay/research-preview.json /new/output/preview.html
npx playwright install --with-deps chromium webkit
SKIP_PUBLIC=true node browser_acceptance.cjs
node browser_capture_acceptance.cjs
```

replay輸出路徑必須新建，防止覆寫；simulate只輸出獨立的合成報告，不寫歷史raw。Browser tests只讀本機fixture。受限環境測試曾使用runtime Playwright1.62.1、Chromium153與WebKit26.5；repo依賴仍保持原pin，沒有變更package.json/lock。測試瀏覽器需要CJK字型。

## 原執行與現有排程

- capture run38514354547、Artifact11872406874、原程式SHA ad54d960d889785f73f91bb5bb68251a36e5307a。
- 備援38515898607是skip SUCCESS，不是擷取成功；原live失敗與Issue#1均未改。
- official workflow的14:50/15:20/17:50沒有改。只重讀Artifact與同日官方資料。
- 查到較早排程延遲到10/14 01:10執行，當時PENDING_NO_CAPTURE。不能算當日盤後已核對。
- cron-job.org頁面目前未登入，沒有重建帳號、讀取Token或改設定；只核對repo保存的10/5設定與10/14實際啟動證據。不要聲稱本次重新驗證帳號內排程。

## 下一步

先向使用者報告並等正式上線決策。若使用者核准部署，先重新取得最新main，檢查其他Work對核心程式保護/開發隔離的修改與此分支差異；不要直接以本分支舊state覆蓋最新state。需安排受控的下一交易日驗證，不能同時額外重跑全市場影響正式資料來源。

P_before獨立真值仍未解決，不得把official MATCH、研究名單或dry-run/skip升級成可交易訊號。官方價格比對成功也不得掩蓋capture的真正缺漏。
