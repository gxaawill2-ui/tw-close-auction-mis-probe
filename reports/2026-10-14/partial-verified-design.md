# 部分完成與正式驗證的發布設計

本次沒有啟用正式訊號。現有 P_before 的獨立驗證仍未成立，不能藉由官方收盤價相同或研究收斂而升級。

| 層次 | 狀態／欄位 | 意義 |
|---|---|---|
| 原始擷取 | CAPTURE_SUCCESS / CAPTURE_PARTIAL / CAPTURE_FAILED | 檔案、日期、階段及逐批擷取完整性；不保證策略正確 |
| 研究 | RESEARCH_ONLY，coverage.research_calculable / unknown | 原研究價格規則保持；任何候選 validated=false |
| 官方價格 | PENDING / SAME_DATE_COMPARISON_ONLY，各股 MATCH / MISMATCH / UNAVAILABLE | 對同日期官方收盤價進行比對；不驗證 P_before |
| 正式策略（尚未啟用） | per-symbol VERIFIED / UNKNOWN / REJECTED | 每檔獨立檢查全部必要證據，才能成為正式候選 |
| 全市場完成度（尚未啟用） | FULL_VERIFIED / PARTIAL_VERIFIED / NOT_VERIFIED | VERIFIED 不能取代全市場完成度，需同時顯示分母與未知數 |

未來正式發布必須逐檔全部通過：

1. 同日動態可交易股票池，身分、交易資格與排除原因均有來源。
2. P_before 的「13:25 前最後實際成交」已獨立驗證；13:27～13:29 只作觀察快照，trade.t 必須 <13:25，不能用較晚成交替代。僅有較早 trade.t 並不證明 MIS 沒漏掉最後成交。
3. P_close 有可追溯、無衝突的有效收盤證據及同日官方收盤價比對；正常13:30與延後收盤分開。
4. 使用 Decimal 計算 |P_close/P_before - 1|≥0.03，不用四捨五入後的3.00%判定。
5. 所有已核定成交量條件、單位與市場範圍通過；研究量證據不能偽裝獨立官方驗證，不自行創造新的成交量門檻。
6. 無未解決 stale、server regression、時間矛盾、價格/成交量衝突或其他必要條件缺漏。

證據不足的股票必須 UNKNOWN，不能標可交易。官方價格不同的股票不能升級。若未來確有1,900檔 VERIFIED、70檔 UNKNOWN，可發布其中完整符合±3%及原成交量條件的股票，頁面仍標 PARTIAL_VERIFIED 1900/1970，不得宣稱全市場完成。

目前所有股票 P_before validated=false，故正式可發布股票為0；本次只恢復既有門檻下的部分研究發布能力與透明狀態，不把研究資料轉為正式交易訊號。
