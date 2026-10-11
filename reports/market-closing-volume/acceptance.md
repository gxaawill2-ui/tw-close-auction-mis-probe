# Stage 4市場量能正式驗收

260 Python、67 Node／DOM/state44、51瀏覽器場景 PASS。feature38100709443、main38100842844（含公開JSON與三瀏覽器）SUCCESS；Pages38100842781／38100952566 SUCCESS。詳細stage4-final-verification.json及stage4-public-evidence/acceptance.json。

正式獨立流程38100939460 SUCCESS，讀官方年度calendar保存10/11 HOLIDAY及attempt health、保留舊revision；沒有新MIS擷取。公開首頁休市、深色、無按鈕、無橫向溢出。全部7個10/8候選既有値完全不變，回歸仍用原保存檔。

18項新增Python驗證雙條件／PROVISIONAL／歷史asof與更正／跨日去重／scope與NaN／缺檔／前收盤與holiday／來源失敗保留；12項Stage4 DOM包含 material-only、來源提示獨立、未評級ETF不足、共同公告保留每指數內容、market unknown及synthetic calibrated邊界。實際全市場同範圍資料與20/60日基準尚無，正常／指數日有效样本均0，不宣稱统计校準；yes/no僅為synthetic測試，不是實際成功取得市場訊號。

來源Hosted實測三個200、5次HTTP，官方範圍note與SHA保存official-source-probe.json；MI_INDEX混合regular+零股+盤後+鉅額，MI_5MINS含股票/基金/權證/其他，均不作普通股regular分母。10/8可驗證1035股池內subtotal只是研究證據，47missing＋完整身份範圍未知，正式值null。每日15:05/18:05自動累積流程已設定；下一個普通交易日實際成功與完整数据覆盖仍待觀察。
