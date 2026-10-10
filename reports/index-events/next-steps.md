# 最新承接入口（第三階段）

更新2026-10-10T00:23:50.384Z。已部署程式b6246cff，完整242 Python／42 Node（32DOM）／42三瀏覽器PASS；main38007718767、MIS tests38007718825、Pages38007864341 SUCCESS。GitHub實際main及deployment.json為權威；不可seed、不重抓10/8、不動MIS市場判斷、Secrets、原外部排程。新source／scheduler／fund評級只處理事件資料。

## 尚需一次授權的最少操作

cron-job.org未登入，兩個獨立event backup jobs未啟用。登入後按config/index-events/cron-job-backup-template.json新增08:35／17:35（Taipei）job，使用只授權此repo Actions read/write的新憑證並存Authorization header；不要重用MIS token或貼入Git。HTTP協定與child self-test已實測成功。啟用後檢查成功收據RECOVERED_BY_BACKUP／duplicate，不把範本當已運作。觸發服務独立，GitHubAPI／runner仍共同依賴。

## 後續驗證與研究

1. 等原生08:20／17:20實際抵達，讀state/events/scheduler/slots與attempts；scheduled_for原定日期在GitHubnative無公開證據，保持null，不從抵達時間冒認延遲slot。17:20事故根因未證實。
2. 取得合適可持續的官方基金規模及本次股票／權重異動明細。模型observation-priority-v1，目前19筆／15ETF，高1中2不足16；規模30日失效，不能將未知當低，不能把指數生效當ETF委託。
3. TPEx完整ETF主檔、基金發行商／指數／掛牌與正式下市證據仍UNKNOWN；118quote candidates僅10/8官方市場觀察。禁止missing=delisted及月報=即時AUM。
4. MSCI公開ADD/DEL可閱讀但限制使用／再散布；FTSE公開PDF連LSEG Section10禁止bots，已停止自動來源。找TWSE／issuer明確允許之公告feed，不繞過robots／登入／授權。TIP禁止downloads不改，已允許新聞保留。
5. 00936／00939映射仍CONFLICT；2027官方交易日曆未公布。新Parser先實測HTTP、robots、條款、日期／名單語义，再全套回歸、CI、Pages。

as-of已校正：初期將00:14舊event snapshot誤用作模型時間，19lineage已重評且舊版本invalid_for_asof_backtest保存。首次有效評級07:50:47.811603（Taipei10/10），不可回填為10/8或10/10盤前更早已知。回測按交易日群聚，不將同日多ETF當多個獨立交易日。
