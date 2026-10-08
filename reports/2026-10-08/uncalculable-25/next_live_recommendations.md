# 10/12 實測準備

依 capture 保存的 2026 官方交易日曆：10/9 國慶補假、10/10–11 週末，下一正常交易日為 2026/10/12。日曆仍以當天官方 gate 為準。
基礎程式版本：d8fcacd07b965f537a310485ddfbdfef96f5df25；原 capture 37730234383 / artifact 11530906396；本研究 as-of 2026-10-08T13:35:00+08:00。診斷版本 UNCALCULABLE_EVIDENCE_V1。程序詳細版本與檔案 hash 見 recovery JSON。

## 現有自動執行保留

cron-job.org 13:00 主觸發、13:10/13:18 備援，14:50/15:20/17:50 官方核對沿用上一輪已驗收 Enabled 設定，本次沒有重新設定、讀取 token 或新建工作。
GitHub backup schedule 的檔案與原 main byte-identical；控制器保留已存在 capture 去重、非交易日與晚啟動 gate。Push CI 只跑 tests，controlled probe/upload 在 push skip。
13:35 前候選輸出目標不變。本次工具不掛入 live，所以不增加 HTTP、CPU 排程或延遲；不需使用者操作。

## 是否增加 live 診斷

本次不必：原始 JSONL 已保存 nested/outer/量、server clock、raw_body 與每次 attempts，足以區分 sparse 股票。離線工具會拆開 terminal result 与先前 HTTP timeout。
建議盤後持續跑同型診斷，將 NO_OBSERVED_PRE_TRADE 与 stale/cache/inconsistent 分清；不要把當日零量的股票列為漏掉的 ±3% 候選。

## 可評估的有界 retry 優化（本次未實作）

B 完成即重試已存在。10/8 B 最後 response=13:28:48.261，輪1 request=13:28:48.458，約 0.197秒後開始，没有不必要延後。
輪1后等5秒使下一次只剩0.799秒；日后可用已觀察 latency + 寫檔/下一phase餘裕判斷是否值得重試，預算不足就記錄 RETRY_BUDGET_EXHAUSTED，保留真實失敗。
若未來 unresolved 是已有完整 identity 但 stale/不一致，可比較 deterministic rotation / 不同 boundary；保留 batch50/concurrency5、固定deadline與有限輪次，403/429停。
已有 10/8 targeted 子集新分組實際 fresh 證據，所以不是推翻可行性；但對本日25缺成交的股票，改善分組不能產生 absent trade。
對前述優化標記 FUTURE_LIVE_TEST_REQUIRED，不宣稱本日安全恢復，也不以沒有保存的 hypothetical HTTP 回應算進 replay。

## 免費來源

若要研究零股最後 pre 成交，必須另外界定市場語義，保存日期、實際成交時計及價格，并驗證 TWSE/TPEx 都有可持續免費程式介面。現存每日盤後統計不足。
目前未驗證完整替代来源，既有 pre 規則保持；25 UNKNOWN 不補値。

## 回退

本次只有 offline tool/tests/reports；live runtime 無變動，下一日繼續原 1943 成功證據所驗收流程。不得為提高百分比取消 nested trade identity/freshness/date/cutoff 或使用官方價格補算。
