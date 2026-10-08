# 10/8 無法計算 25 檔證據分析

分析時間：2026-10-08T17:27:03.597+08:00。Live as-of：**2026-10-08T13:35:00+08:00**。
原始 capture run：37730234383；Artifact：mis-probe-37730234383；ID：11530906396。
原 ZIP SHA256：`1b4caf9efcbb0575771726b356751f177bba37439179cb14bfc9b8a9bc9a88e0`。
原 capture commit：`2dd62b249a181d7045c957f0c33501cc574723cd`；核對的 main / live replay base：`d8fcacd07b965f537a310485ddfbdfef96f5df25`。
診斷版本：UNCALCULABLE_EVIDENCE_V1；`analyze_uncalculable.py` SHA256：`be28204cf9fc4a1a9edb20ce07b6838c503e385bafa0237a6a1b04ee9857f28a`。
最終提交 SHA 由包含本報告的 Git commit 識別；不在同一提交內假造自我引用 SHA。
Official run：37742790398，檢查時間：2026-10-08T15:20:18.859+08:00；official 原始檔 SHA256 和日期驗證收錄在 root_cause / recovery JSON。

## 結果及因果

原版與本次 as-of replay 都是 P_before 1943、可計算 1943、UNKNOWN 25、±3% 候選 7，涵蓋率 **98.7296747967%**。
安全恢復 **0**；沒有新候選。原七檔的價格、成交時間、AB/BC、Decimal 報酬、confidence_level、validated=false 及整個候選 JSON 全部逐欄相等。

25 檔不是未回傳：pre A/B 全有 HTTP 200；A、B、第一次 targeted、最後一次 targeted 每檔各有四份 fresh 回應。所有成功的 pre 回應都沒有 nested trade、v=0、outer z='-'。
pre C 全 25 命中 stale cache（B 原分組的 server time，age 約 42–45 秒）；這是次要現象，四份 fresh 仍無 trade，所以不能把它說成 UNKNOWN 的主要原因。
cachedAlive 缺值只標 MISSING；有值原樣保留，不猜單位。外層 t 是行情更新時刻，pz 可能為試撮，均不能冒充 nested 成交。

互斥主要原因：官方零成交 **9**；每日有活動但 regular MIS 無實際成交證據 **13**；僅在 close 保存整股成交 **3**。
原始 pre trade 缺失是 **25** 檔共有現象；不等於 25 檔 parser bug。沒有證据支持解析誤殺、時間判斷錯誤或放寬 freshness。
3 檔 1583/8067/9937 的 close AB 已收斂，trade.t=13:30，trade.z 有價格，但仍沒有可用的 pre baseline。
13 檔每日股數均小於 1,000，開/高/低/收缺值，與零股活動一致。**沒有逐笔零股資料，不能確定各檔活動是在盤中或 14:30，也不能證明曾在 13:25 前成交。**
9 檔官方股數/金額/筆數全零，不能用昨日收盤、參考價或試撮價定義當日 pre 價格。

## 逐檔

|代號|名稱|市场|官方每日股數|官方金額|官方筆數|官方收盤|P_close|主要原因|
|---|---|---|---:|---:|---:|---:|---|---|
|1583|程泰|TWSE|2042|96576|6|47.30|AB_converged|pre v=0、trade 缺失；首次保存整股成交為 13:30|
|4581|光隆精密-KY|TWSE|300|14639|2|MISSING|unresolved|每日有成交量，但 regular MIS 無成交；缺精確 pre 時間/價格|
|5906|台南-KY|TWSE|0|0|0|MISSING|unresolved|官方當日零成交；無可定義的當日 pre 成交|
|8488|吉源-KY|TWSE|0|0|0|MISSING|unresolved|官方當日零成交；無可定義的當日 pre 成交|
|9937|全國|TWSE|2121|117126|6|55.20|AB_converged|pre v=0、trade 缺失；首次保存整股成交為 13:30|
|2073|雄順|TPEx|291|7449|2|MISSING|unresolved|每日有成交量，但 regular MIS 無成交；缺精確 pre 時間/價格|
|2718|全心投控|TPEx|608|23915|10|MISSING|unresolved|每日有成交量，但 regular MIS 無成交；缺精確 pre 時間/價格|
|3332|幸康|TPEx|0|0|0|MISSING|unresolved|官方當日零成交；無可定義的當日 pre 成交|
|4183|福永生技|TPEx|0|0|0|MISSING|unresolved|官方當日零成交；無可定義的當日 pre 成交|
|5276|達輝-KY|TPEx|191|3342|2|MISSING|unresolved|每日有成交量，但 regular MIS 無成交；缺精確 pre 時間/價格|
|5520|力泰|TPEx|35|2961|2|MISSING|unresolved|每日有成交量，但 regular MIS 無成交；缺精確 pre 時間/價格|
|5703|亞都麗緻|TPEx|122|1641|3|MISSING|unresolved|每日有成交量，但 regular MIS 無成交；缺精確 pre 時間/價格|
|6198|瑞築|TPEx|2|38|2|MISSING|unresolved|每日有成交量，但 regular MIS 無成交；缺精確 pre 時間/價格|
|6212|理銘|TPEx|0|0|0|MISSING|unresolved|官方當日零成交；無可定義的當日 pre 成交|
|6236|中湛|TPEx|0|0|0|MISSING|unresolved|官方當日零成交；無可定義的當日 pre 成交|
|6242|立康|TPEx|50|1692|1|MISSING|unresolved|每日有成交量，但 regular MIS 無成交；缺精確 pre 時間/價格|
|6661|威健生技|TPEx|0|0|0|MISSING|unresolved|官方當日零成交；無可定義的當日 pre 成交|
|6662|樂斯科|TPEx|1|27|1|MISSING|unresolved|每日有成交量，但 regular MIS 無成交；缺精確 pre 時間/價格|
|6680|鑫創電子|TPEx|58|2952|1|MISSING|unresolved|每日有成交量，但 regular MIS 無成交；缺精確 pre 時間/價格|
|6762|達亞|TPEx|1|157|1|MISSING|unresolved|每日有成交量，但 regular MIS 無成交；缺精確 pre 時間/價格|
|6904|伯鑫|TPEx|0|0|0|MISSING|unresolved|官方當日零成交；無可定義的當日 pre 成交|
|7820|立盈|TPEx|0|0|0|MISSING|unresolved|官方當日零成交；無可定義的當日 pre 成交|
|8067|志旭|TPEx|1001|11512|2|11.50|AB_converged|pre v=0、trade 缺失；首次保存整股成交為 13:30|
|8455|大拓-KY|TPEx|750|17023|6|MISSING|unresolved|每日有成交量，但 regular MIS 無成交；缺精確 pre 時間/價格|
|9949|琉園|TPEx|682|16479|23|MISSING|unresolved|每日有成交量，但 regular MIS 無成交；缺精確 pre 時間/價格|

## Targeted retry 的實際流程

batch size=50、concurrency=5 未改。139 檔與最後 25 檔都是 unresolved 子集，並非增加全市場請求。

|輪次|分組|實際 request|實際 response|截止|結果|
|---|---|---|---|---|---|
|1|139 檔，50/50/39|13:28:48.458–.459|13:28:50.437–52.051|13:28:58|139 全回傳；25 仍 trade 缺失/v0|
|2 first HTTP attempt|25 檔，1 batch|13:28:57.201|13:28:58.004|13:28:58|約 803ms timeout；超出 4ms，保留原錯誤|
|2 next attempt|同 25 檔|13:28:58.505（程式檢查時間）|同上|13:28:58|CAPTURE_DEADLINE_NO_REQUEST，這次沒有 HTTP|
|3|25 檔，1 batch|13:29:25.164|13:29:26.413|13:29:30|25 全回傳，server=13:29:26；trade 仍缺失/v0|

輪1完成後原流程等 5 秒，輪2 planned=13:28:57.201，剩不到 0.8 秒。其 timeout 不是 batch latency 0，也不是整輪完全沒有 request。終局 FetchResult 的 latency=0/timeouts=0 無法代表歷史 attempts，本診斷展開實際 attempts 正確還原。
輪3確實送出，延遲 1.249 秒並成功；截止/重試不是這 25 檔的主要 root cause。
輪2 no-request 的計時點與 planned 相差 1.304 秒，是 HTTP timeout + 0.5 秒 retry backoff；**不是已證實的 unresolved CPU 計算時間**。
pre C stale，但 targeted 139 與 25 的新 cache key 均取得新 server observation；重分組方向已经存在，本日不能證明再多 retry 能產生不存在的成交。

## 原始欄位與缺漏

`25_symbols_raw_timeline.csv` 按股票、實際 request 時間排序。逐筆保存 final selected_result 及不同的 HTTP_attempt，並附 source ZIP path、JSONL line、原 line SHA256、完整 raw_item、原 batch cache key hash。
所有不存在欄位為 MISSING，原 JSON null 為 null，不補造 trade.t/z/v/ft、outer t/z/pz、v/tv/s/d、queryTime、cachedAlive、HTTP/error。
3 檔不需 close C：NOT_SCHEDULED；25 檔都不在固定 8 檔逐秒 probe：NOT_SAMPLED。這些 coverage_note 不當成 HTTP failure 或實際快照。
特别交易欄位 io=RR 原樣保留，語義 UNVERIFIED；公司股票池 trade_flags={} 不足以推定停牌。
官方名稱 5703 為「亞都」，capture 名稱「亞都麗緻」；代號/市場一致，以原始股票池名稱還原，不改原 artifact。

## 盤後口徑與免費來源

保存的 TWSE daily table notes 明示統計含一般、零股、盤後定價，排除鉅額/拍賣/標購。TPEx 保存 notes 對 --- 表示無開高低收行情；並未提供每筆實際成交時間。
因此每日正成交股數不能推出當時存在 regular pre 價格。
官方制度參考：[TWSE 交易制度](https://www.twse.com.tw/zh/products/system/trading.html)、[TPEx 交易制度](https://www.tpex.org.tw/zh-tw/mainboard/trading/rules/system.html)、[TWSE 免費 OpenAPI](https://openapi.twse.com.tw/)。
上述網站有分开的零股行情/盤後統計；盤後表沒有精確最後 pre 時間。免費公開 MIS 另有零股行情，但本日没有保存該市場的逐筆證據，也沒有驗證穩定的程式介面、授權/持續性與日期/實際成交識別的完整契約。
本次未確認任何額外免費來源同時滿足 TWSE+TPEx、正確日期、精確 pre-13:25 成交價與時間、免費且可持續程式化。任何替代來源必須 FUTURE_LIVE_TEST_REQUIRED，不算本日恢復。
更不能把零股最後成交直接混入既有整股 P_before，造成市場定義改變。

## 安全分類與修改範圍

可安全恢復：0。已證實需要重試才能恢復：0。無法安全恢復：12（9 無成交 + 3 僅 close）；資料來源限制：13。
需要改進 retry 預算/分組是一般流程優化方向，不是本日缺失的已證實解方。
只新增離線診斷與測試；probe/convergence/close/freshness/official/status/runtime/workflow/排程完全不改。
所有恢復結果按原 live 規則 replay，官方資料僅在選價之后附加分類；沒有引入未來價格，没有發出 MIS request，ZIP 與已保存官方檔 hash 在分析前後一致。

## 驗收

Python：119 tests PASS（原101 + 新18）。Node：9 tests PASS。GitHub push CI 待提交後確認；最終 SHA 與 CI run 在交付 acceptance 記錄。
新 fixture 32 檔是原 artifact 提取的離線資料（25 UNKNOWN + 原7）；移除其他股票與重複 raw_body，保留實際證據欄位，明確標示 derived fixture，未改原始 ZIP。
全市場 replay 使用完整原 ZIP，另以 fixture 做可持續 CI 回歸。正式 capture/version/shadow hierarchy 的結果全維持。

執行命令：

```sh
python3 analyze_uncalculable.py --capture-zip /path/mis-probe-37730234383.zip --official-dir /path/validation-results --output reports/2026-10-08/uncalculable-25 --code-sha <live-base-sha>
python3 -m unittest discover -v
node --test test_status.cjs
```
