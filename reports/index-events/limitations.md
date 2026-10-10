# 已知限制

1. 目前為PARTIAL來源涵蓋率。沒有取得事件、抓取失敗或過期，首頁显示「事件資料尚未完整確認」，不以「沒有事件」代替。已知官方期程仍可閱讀。
2. MSCI公開期程可讀；Standard／Small Cap完整授權成分、自由流通及權重資料不自動再散布。臨時公司事件尚無完整免費來源。00878客製指數的審核不得直接套用MSCI全球定審。
3. FTSE完整Technical Releases需註冊／訂閱。只追蹤TIP公開通知與公開規則變更，不能保證所有FTSE臨時事件涵蓋；12/18只是規則推估，非2026/12已確認實施公告。
4. TIP掃描最近10份期程、最近10份通知，並設總HTTP上限。舊資料永久留存，不代表已完整回補所有歷史公告。未識別PDF布局及規則修訂留待審佇列；不能用任意日期或股票名稱猜成分異動。
5. 2027正式交易日曆成功取得前，2027生效日前收盤觀察日保持null。颱風等非預期休市不能仅依年度日曆確認；更正未取得时保持不完整。
6. ETF對應自動維護限能取得的TIP公開指數／ETF表格；尚未建立涵蓋全部台股ETF的新上市主檔。發行商公告目前為變更偵測及待審，未宣稱已全面自動解析換股日期。
7. 未公布成分明細，不標記個股納入／刪除／權重。市場或公司身分不符，不標記關係。沒有個股官方證據即使當日有事件，也只顯示個股關聯未確認。
8. 此次新增32筆事件：29筆具有官方公告／生效期程，3筆FTSE規則推估。初始未來範圍沒有CONFIRMED_CLOSE_IMPLEMENTATION事件。不得把29筆期程說成29筆確認尾盤爆量日。
9. 不包含任何推測资金規模、爆量保證、成交量預測、買賣建議或統計優勢。10/8價格與成交量保持原MIS研究確認，沒有提升為獨立官方成交量驗證。
10. GitHub Actions日程允許延遲；設置08:20／17:20不等於保证準時。來源robots拒絕、401／403及登入牆停止，不更換身分繞過。HTTP每run最多60次，每URL最多2次，10秒逾時，6MiB大小限制，workflow 15分鐘上限。
11. 來源失敗保留前次事件、成功時間及錯誤；發布失敗由Actions失敗紀錄與scan artifact保存。每日事件JSON及版本歷史在Git，不依賴30天artifact存活。
12. 未來10/12的MIS Live尚未發生，不能宣稱已測試其實際結果。原盤中／盤後workflow、Token、Secrets、cron-job.org全部未改。

13. 已確認實際自動化限制：TIP期程／技術通知入口ROBOTS_DISALLOWED，無法自動取得新日程或新成分名單。現在25筆TIP期程來自初始人工官方核對。TIP news/452、454的對應表可自動核對，但新news動態列表未解析，尚不能宣稱新上市ETF自動納入。富邦指定頁robots禁止，國泰指定頁HTTP400。


## 本次補強後仍然存在的限制

- TWSE正式ETF主檔已接通；66筆研究範圍普通被動基金中64筆對應確認，00936、00939來源名稱差異為CONFLICT。只證明TWSE主檔，非全台ETF當日掛牌清單；含歷史基金，完整下市與正式發行公司欄位UNKNOWN。主檔公布頻率標示每月，不承諾上市當天即時發現。
- 元大四頁為DATE_ONLY，檔數不是股票名單。TIP兩篇公開公告可確認9筆歷史指數收盤後實施，不能宣稱已打通TIP新公告列表，更不等於ETF實際委託紀錄。
- TWSE／TPEx一般ETF資訊網站條款限制自動下載，內部API不能當作允許的開放API。TPEx完整ETF主檔仍未接通；免費政府開放資料是後續合法方向。
- 第一個本機全來源掃描中TWSE日曆及舊FTSE規則URL遇HTTP307，保留先前成功證據並標STALE。GitHub runner需另實測，不以本機失敗推定所有來源永久不可用。
- 新來源分類中的VERIFIED_AUTOMATIC只描述該設定入口的取得／解析，不代表所有公告皆完整；DATE_ONLY與MONITOR_ONLY不算基金實際換股日期解析成功。
- 多來源同期間日期衝突會清除相爭欄位的單一值、保留全部來源與歷史，CONFLICT不進當日觀察或個股關聯。更正以新的可用時點入歷史，不回填舊live_as_of。

第二階段最終核對：2026-10-09T16:57:01+08:00，正式CI37907579895與Pages37907698117 SUCCESS；源掃描49事件／64確認ETF對應／2衝突，來源11成功取得解析（6自動完整語義來源＋5日期）但PARTIAL。193 Python、39 Node、36瀏覽器場景PASS。完整證據見deployment.json及source-recovery-validation.json；待審10文件不是已確認事件。

## 第三階段實測更新（2026-10-10T00:23:50.384Z）

增加TPEx官方OpenAPI quotes（政府11370OpenGov License1）：HTTP200，4,782,391 bytes／12,221行；118ETF格式代號，排除020ETN。僅OBSERVED_IN_OFFICIAL_QUOTES_AS_OF_DATE=10/8；指數、主被動、issuer及當前listing UNKNOWN，不代替完整主檔。來源截斷／JSON poison cache移除並有界重試，記錄bytes/hash/offset；原TPEx公司舊錯誤只有Unterminated string(char328678)，未保留raw所以根因UNKNOWN；失敗不清空公司或ETF資料。

新增0050／0051／0056元大官方PCF淨資產，HTTP200、robots允許；10/8 NAV valuation不是10/12PCF nextday。AUM不代表實際下單或換股日期。27來源：VERIFIED_AUTOMATIC10、DATE_ONLY5、MONITOR_ONLY3、RESTRICTED6、UNAVAILABLE3；本次15成功（基線最近10、此前正常11），PARTIAL未改。最後成功08:10:08，34/60requests；49事件／66映射保留。

MSCI公开Standard/SmallCap ADD/DEL可匿名閱讀，臺灣區只有名稱，無可靠本地股票代號／市場，不同於完整授權成分／權重／float。PDF再使用限制未解決，因此未自動取得或轉發股票清單。FTSE公开review及correction PDF也可閱讀，但實際Terms連LSEG第10節禁bots；已停止ftse-rule-0自動化并在Fetcher請求前拒絕已知FTSE/LSEG受限host。robots允許及HTTP200不等於條款允許自動化。

無新增未来官方ETF實際收盤委託時点。11/30MSCI、12/18FTSE50/Mid100預估；0056五日12/21,22,23,24,28預估，不能寫確認。3個粗略評級PROVISIONAL，16資料不足，日期證據與重要程度分欄。備援程式／HTTP實測完成但cron-job.org NOT_ACTIVATED待一次登入及新單repo憑證，不能宣稱每天外部補觸發已上線。
