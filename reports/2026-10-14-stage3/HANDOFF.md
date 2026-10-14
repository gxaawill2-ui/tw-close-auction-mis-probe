# 第三階段接手：獨立ticks與低延遲發布

## 範圍

分支`stage3/20261014-independent-ticks-publication`從0707902建立。使用者授權此隔離研究／開發／測試及新分支同步，**沒有授權合併main、正式部署、DNS、正式排程、Token/Secret更動、歷史raw修改或重跑全市場**。不要改tw-market-chips、Vercel或既有relay。

## 已完成／不要重做

stage3_ticks/provider/selection/run/publication＋獨立Worker/SQLite DO＋GUI。README有完整來源、時間與免費比較。raw pages／quote前後、count/size語意閘門、微秒/serial、missing/trial/cache/conflict、normal/delayed/no-close均有反例。候選網路最多50總請求、1.1秒節流、12頁/股、3回/股、deadline，新的watch只讀已存在journal，不抓MIS。

348 Python＋102 Node/前端PASS；Worker14項PASS；ChromiumWindows UA／iPhone及WebKit iPhone13模擬PASS，本機Worker寫入→瀏覽器約1.34～1.43s。真機與Cloudflare全球實測未做。新分支公開JSON匿名瀏覽器試驗結果請讀public-read-acceptance.json；不能把它叫Pages或Worker雲端發布。

10/14真實研究仍6檔、正式0；初篩1946／1970、24unknown可能漏選。歷史first研究13:32:35.533／last13:34:14.306，真實pre/close獨立驗證及VERIFIED公開時間為null。日期、原始byte和原Artifact SHA保留。

## 尚未解決

沒有FugleKey與真實tick HTTP。LIVE_CONTRACT未確認rows=count、sum(size)=regularVolume、serial與獨立傳輸，live release=false；Worker ALLOW_LIVE_VERIFIED=false；前端私人bootstrap release=false。合成TEST_CONTRACT只供test，不能改成live來假達標。

完整歷史路徑可能對熱絡股耗時／超12頁／50總請求。prefix能否完整覆蓋cutoff需來源契約證明，不能自行把短頁／同價當complete。API Key只解授權，不自動解除來源閘門。

沒有公開Cloudflare帳號測試Worker。保留正式GitHubPages網址，在未來部署授權後讀新端點即可；現在只用本機Miniflare和新分支測試檔。不可修改既有worker/wrangler config。

## 可重現

```bash
python3 -m unittest discover
npm test
python3 stage3_replay.py /original/mis-probe-2026-10-14.zip /new/isolated/directory
node stage3_worker_acceptance.cjs
node browser_stage3_acceptance.cjs
node browser_stage3_public_read.cjs
```

此工作環境Miniflare放`/workspace/scratch/52ff117b908b/stage3-runtime/node_modules/miniflare`（4.20260730.0）。MF測compat2026-07-30，部署config是2026-10-14；未證明未來雲端環境與本機完全相同。瀏覽器PLAYWRIGHT_MODULE=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright，CHROMIUM_EXECUTABLE_PATH=/workspace/scratch/52ff117b908b/fast-browser-runtime/bin/chromium。MF／writer測試key只在記憶體，不是使用者正式Secret，不寫報告。

可先用stage3_run.watch在未來受控交易日影子讀原journal；只有明確選項才collect候選或publish新隔離endpoint。現在晚於capture窗口，不可執行歷史LIVE；CLI會拒絕。其所需環境名只限FAST_FUGLE_API_KEY、STAGE3_PUBLICATION_TOKEN、STAGE3_DECISION_KEY，不得挪用其他服務Secret。

## 下一步

1. 由使用者提供／授權**專用富果免費Key**，不要貼對話，不接觸正式GitHubSecret。實測6冷門候選及少量同秒活躍樣本，確認完整性字段契約，保留raw。
2. 授權**新的獨立Cloudflare測試服務**，無cron／DNS／正式worker變更。公開token只server，browser只有GET。測真實跨網路手機匿名讀取與write receipt，free quota/CPU不可用MF數據保證。
3. 下一交易日不重跑全市場，只讀既有capture journal；確認原collector的opt-in fsync輸出如何在同runner共用，未經正式部署授權不能改main workflow。
4. 真實核對pre13:24:59最後tick、same-second/trial/late-source、close13:30/13:33、已確認必要量；晚到official只最終稽核。
5. 記錄research→pre independently proved→close proved→full VERIFIED→public write→external read→last update分段；未知要null。目標13:35～13:40，沒做到就報實際瓶頸。

目前不具正式部署條件；完成上述也須另取得合併／正式部署授權。
