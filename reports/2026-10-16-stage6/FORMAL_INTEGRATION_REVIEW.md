# 第六階段正式最小串接審查（未實施）

## 本次保護範圍

沒有修改 main、正式 collector/workflow、cron-job.org、正式網站、正式 Token/Secret 或既有正式 relay；沒有新增全市場擷取。本輪只更新同一隔離 Worker 的私有 journal codec/容量保護，未更動正式 relay。雲端 Build a0f6cc5 已成功，版本551b8600-7dc7-41dd-9c8e-ad3fe16471c3；既有研究資料在18:30:22重新讀到，版本/內容保留。

## 最新正式差異

核對 main `a8f25945f94ce45300d5e97c9d6a7f622586663e`，正式 probe blob `64f4e90dde9e17cc3ff5ebf3779ac040e69b8bd4`、workflow blob `f4e74ee3b3080a9e6ae0aef2f3e1c759384c9ecb`。正式資料由 bot 正常更新，不能要求 main 的 HEAD 完全不變。
不要合併整個隔離分支：分支另含先前實驗性 collector 與 UI。只審核白名單補丁。

## 可審核的最小操作

1. 沿用 stage5 `production-journal.patch`，只在正式 `probe.py` 加入預設關閉的 journal hook，另加入 `stage5_capture_journal.py`。不改價格、擷取時間、批次請求數或舊 raw 排序。
2. 正式工作增加「唯寫橋接」背景程序 `stage6_bridge.py`，只讀正式已產生的 universe 和已 fsync journal，輸出到私有 bridge。啟用開關預設 false；程式碼固定為經審核 Commit。正式程序只拿 `STAGE5_MIS_BRIDGE_TOKEN`，不拿富果 Key、publisher Token 或私有讀取權。
3. 新增獨立 consumer workflow，提案為 `proposed/independent-consumer.yml.proposed`。由既有正式 workflow 的 in_progress 事件啟動，不新增 cron，不變更 cron-job.org 或其備援。獨立 Runner 運作至 14:30，不被正式 collector 結束清理。
4. 允許該 consumer 對隔離 Environment 的最小存取；目前 Environment 只准隔離分支。**須核准 admission 及正式 workflow 設定，不能直接加 environment 導致正式 job 卡住。** 建議先獨立驗證 admission，再以預設關閉方式合入。
5. 同一隔離 Worker 的 bounded-zlib bridge codec 已部署，並完成本機 workerd 驗證；由於唯寫 bridge Secret 尚未設定，雲端 MIS bridge 真正寫入仍未驗收。建立/交接唯寫 bridge Secret 屬新增權限，須另行同意。既有 Key、publisher Secret 與 Worker 都不重建。
6. 如核准定向 C2，只在現有 C 後針對已保存比較基準、單次延後收盤且變動超過 3% 的股票，最多 12 檔、2 輪、單次 5 秒、冷卻 3 秒，13:34:50 前收完。`stage6_retry.py` 只會產生計畫，不會呼叫 MIS；此項目前未實施。不得擴為第二套全市場。

## 新發現且已在隔離修復的容量問題

10/16 原始 320 批次約 41.6 MB，最大單筆約 169 KB，舊 bridge 的 98 KB/事件、10 MB/namespace 上限會使實際串接失敗。新 codec 壓縮 journal 並同時核對壓縮包、原始 journal 與原始 record 的 SHA256，解壓上限 512 KB；私有 universe 也以有上限的壓縮包交接，不等待公開 Artifact。壓縮後約 10.74 MB，仍略超舊 10 MB；因此隔離程式只將 MIS 獨立 namespace 上限設為 20 MB（600 個事件不變），Fugle 仍 10 MB。7 天最壞 140 MB，小於官方 Free 5 GB 儲存額度，但須核對帳號共用用量，未加購。實際重播量測見 `journal-compression-real-replay.json`。codec 雲端建置成功，但未啟用 bridge，不能算真實逐批串接成功。

## 風險與回滾

- journal 在 collector callback 增加本機 fsync，已有失敗時停用 journal、原擷取繼續的測試；雲端傳輸在獨立背景程序，慢速驗證在另一 Runner。
- consumer workflow 只讀 repository、單一專用 concurrency group、cancel=false，與正式 `twse-mis-live` 無關。須確認帳號並行額度足夠；不承諾 GitHub 啟動一定即時。
- 新 Runner 會重播私有 immutable journal、重新核對證據，不用舊 verdict；每次行情請求前私有保存序號預算，重啟不會重獲 160 次額度。這依賴單一 consumer，並非跨所有 App 的全域限流。
- 雲端版本目前只保證「較小版本不得覆蓋較大版本」。仍須用下一交易日實際檢驗來源事件順序與 crash 恢復。
- 停用正式 journal/bridge 開關及獨立 consumer workflow 即可停止；原 capture 命令、排程、歷史資料不撤回。必要時只反向撤回正式白名單補丁。提案 patch 的 apply/reverse bytes 驗證見 `patch-rollback-latest.json`。
- 源端完整性、6228/5546 三分鐘時間衝突未釐清，LIVE source contract 與 Worker `ALLOW_LIVE_VERIFIED=false` 繼續保留。

本文件供下一次核准範圍使用；不代表已取得正式變更許可，也不建議在來源問題未解決前直接上線。
