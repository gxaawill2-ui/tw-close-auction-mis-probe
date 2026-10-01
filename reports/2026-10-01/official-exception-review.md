# 2026/10/01 官方例外離線核對

僅使用已保存的 10/1 MIS raw 與 Artifact `mis-validation-36827501177`。没有重新請求 MIS，沒有回補 checkpoint。新增的指定日期官方零股盤後表只用於市場別分類。

## 分母與官方核對

| 項目 | 數量 |
| --- | ---: |
| 公司池 | 1978 |
| 官方排除 | 9 |
| 可交易池／MIS 可辨識回傳 | 1969／1969 |
| 同日官方價格一致（不是 freshness validated） | 1939 |
| nested 價格不一致 | 6 |
| 可交易但無普通收盤價 | 24 |

原 33 unavailable = 9 官方排除 + 10 官方日成交股數為零 + 14 官方有成交股數但普通收盤價空白。24 檔仍留在可交易池；不能把沒有整股成交視為停止交易，也不能補零或沿用前日價格。

TPEx 使用 `dailyQuotes?date=2026%2F10%2F01&response=json`，回應日期 `20261001`、`stat=ok`。14:56:50.924 Asia/Taipei 保存的表有 11871 個所有證券代號（含權證，不能當股票池分母）。早期 14:50:41.904 空表保留 PENDING，確切發布時間 UNVERIFIED。兩次觀察不能證明資料實際發布時刻。

上櫃可交易 887：859 價格一致、5 不一致、23 無普通收盤價。上市可交易 1082：1080 一致、1 不一致、1 無普通收盤價。

## 六檔不一致：原因仍未確定

| 市場／代號 | 名稱 | nested trade.t | nested trade.z | 官方收盤 | 最後 server time | request − server |
| --- | --- | --- | ---: | ---: | --- | ---: |
| TPEx／4995 | 晶達 | 12:20:25 | 49.7000 | 50.00 | 13:32:11 | 65926.0 ms |
| TPEx／5548 | 安倉 | 13:10:41 | 20.0500 | 20.00 | 13:32:13 | 64722.0 ms |
| TPEx／6865 | 偉康科技 | 13:14:23 | 28.2000 | 27.65 | 13:32:18 | 61935.0 ms |
| TPEx／6953 | 家碩 | 13:22:49 | 251.5000 | 252.50 | 13:32:18 | 61935.0 ms |
| TPEx／8472 | 納維康 | 13:24:55 | 68.6000 | 69.20 | 13:33:23 | -1883.0 ms |
| TWSE／4755 | 三福化 | 13:24:40 | 118.0000 | 119.00 | 13:33:33 | -1258.0 ms |

4995、5548、6865、6953 最後 server 約落後 61–66 秒；8472、4755 server 已接近 request，但 nested trade 仍停在收盤前。六檔外層 z 都為 `-`，保存的 MIS 累計 v 沒出現收盤跳增。這是「尚未觀察到收盤成交」證據，不能据此認定真正延後成交、沒有收盤撮合或 MIS 計算錯誤。server clock fresh 不能單獨證明每檔 payload fresh。

部分 pz 恰好等於官方收盤，其他 pz 不同；不將 pz 當收盤成交價。官方日成交股數包含其他交易市場，不能單憑它比 MIS v×1000 大就宣稱漏了收盤量。精確原因仍 UNRESOLVED；需要跨日或獨立最後成交證據。

## 全部 39 檔分類

| 市場／代號 | 名稱 | 原結果 | 官方日成交股數 | 分類／證據 |
| --- | --- | --- | ---: | --- |
| TPEx／2235 | 謚源 | UNAVAILABLE | 0 | 官方日成交股數零；無價格 |
| TPEx／2937 | 集雅社 | UNAVAILABLE | 0 | 官方日成交股數零；無價格 |
| TPEx／2949 | 欣新網 | UNAVAILABLE | 2 | 普通收盤價空白；有其他市場成交；官方盤中零股 2 股 |
| TPEx／3067 | 全域 | UNAVAILABLE | 0 | 官方日成交股數零；無價格 |
| TPEx／3085 | 新零售 | UNAVAILABLE | — | 官方排除：capital_reduction_suspension, trading_suspended |
| TPEx／4192 | 杏國 | UNAVAILABLE | 124 | 普通收盤價空白；有其他市場成交；官方盤中零股 1 股 |
| TPEx／4419 | 皇家美食 | UNAVAILABLE | 0 | 官方日成交股數零；無價格 |
| TPEx／4527 | 方方土霖 | UNAVAILABLE | — | 官方排除：capital_reduction_suspension, trading_suspended |
| TPEx／4804 | 大略-KY | UNAVAILABLE | — | 官方排除：trading_suspended |
| TPEx／4806 | 桂田文創 | UNAVAILABLE | — | 官方排除：capital_reduction_suspension, trading_suspended |
| TPEx／4995 | 晶達 | MISMATCH | 7,077 | nested 未觀察到收盤新成交；原因未定 |
| TPEx／5301 | 寶得利 | UNAVAILABLE | — | 官方排除：capital_reduction_suspension, trading_suspended |
| TPEx／5455 | 昇益 | UNAVAILABLE | 193 | 普通收盤價空白；有其他市場成交；官方盤中零股 13 股 |
| TPEx／5548 | 安倉 | MISMATCH | 77,825 | nested 未觀察到收盤新成交；原因未定 |
| TPEx／5703 | 亞都麗緻 | UNAVAILABLE | 222 | 普通收盤價空白；有其他市場成交；官方盤中零股 222 股 |
| TPEx／6114 | 久威 | UNAVAILABLE | 60 | 普通收盤價空白；有其他市場成交；官方盤中零股 60 股 |
| TPEx／6198 | 瑞築 | UNAVAILABLE | 0 | 官方日成交股數零；無價格 |
| TPEx／6222 | 立軒 | UNAVAILABLE | 0 | 官方日成交股數零；無價格 |
| TPEx／6242 | 立康 | UNAVAILABLE | 304 | 普通收盤價空白；有其他市場成交；官方盤中零股 304 股 |
| TPEx／6661 | 威健生技 | UNAVAILABLE | 0 | 官方日成交股數零；無價格 |
| TPEx／6855 | 數泓科 | UNAVAILABLE | 5 | 普通收盤價空白；有其他市場成交；官方盤中零股 5 股 |
| TPEx／6865 | 偉康科技 | MISMATCH | 21,142 | nested 未觀察到收盤新成交；原因未定 |
| TPEx／6904 | 伯鑫 | UNAVAILABLE | 0 | 官方日成交股數零；無價格 |
| TPEx／6929 | 佑全 | UNAVAILABLE | 0 | 官方日成交股數零；無價格 |
| TPEx／6953 | 家碩 | MISMATCH | 101,006 | nested 未觀察到收盤新成交；原因未定 |
| TPEx／6997 | 博弘 | UNAVAILABLE | 8 | 普通收盤價空白；有其他市場成交；官方盤中零股 8 股 |
| TPEx／7767 | 仁大資訊 | UNAVAILABLE | 33 | 普通收盤價空白；有其他市場成交；官方盤中零股 33 股 |
| TPEx／8183 | 精星 | UNAVAILABLE | — | 官方排除：otc_terminated |
| TPEx／8424 | 惠普 | UNAVAILABLE | 55 | 普通收盤價空白；有其他市場成交；官方盤中零股 55 股 |
| TPEx／8444 | 綠河-KY | UNAVAILABLE | 30 | 普通收盤價空白；有其他市場成交 |
| TPEx／8472 | 納維康 | MISMATCH | 181,956 | nested 未觀察到收盤新成交；原因未定 |
| TPEx／8917 | 欣泰 | UNAVAILABLE | 122 | 普通收盤價空白；有其他市場成交；官方盤中零股 120 股 |
| TPEx／8921 | 沈氏 | UNAVAILABLE | 0 | 官方日成交股數零；無價格 |
| TPEx／8923 | 時報 | UNAVAILABLE | 150 | 普通收盤價空白；有其他市場成交；官方盤中零股 1 股 |
| TWSE／1589 | 永冠-KY | UNAVAILABLE | — | 官方排除：trading_suspended |
| TWSE／2323 | 中環 | UNAVAILABLE | — | 官方排除：capital_reduction_suspension |
| TWSE／2601 | 益航 | UNAVAILABLE | — | 官方排除：capital_reduction_suspension |
| TWSE／4755 | 三福化 | MISMATCH | 155,047 | nested 未觀察到收盤新成交；原因未定 |
| TWSE／6655 | 科定 | UNAVAILABLE | 465 | 普通收盤價空白；有其他市場成交；官方盤中零股 465 股 |

8444 綠河-KY 的同日官方狀態為變更交易、分盤 30 分鐘，停止交易欄位空白，所以仍保留在 tradable 池；不可將處置／分盤自動排除。13 檔已在同日盤中零股表看到正股數（含科定 465 股）；8444 的盤中零股股數為零，其 30 股需盤後市場別進一步核對。

## 下一交易日驗收與未驗證項目

- 保持 batch 50／concurrency 5；同樣八檔：2330、2317、2454、1341、1410、1240、1781、1813。
- preclose 33 個 planned ticks：13:24:50–13:25:10 每秒，13:25:15–13:26:10 每五秒。close 35 個 planned ticks：13:29:50–13:30:15 每秒，另九個 checkpoint 至 13:33:15。
- raw 保存完整 queryTime、cachedAlive、外層 t/z/pz/v/tv/s、完整 trade 與 trade.t/z/v/ft；正規化記錄 planned/request/response/latency、server_age_ms。
- 15 秒 server-age 與三個不同 server timestamp 收斂只屬研究候選，另做 5／15／30 秒敏感度比較。MIS timezone、cachedAlive 單位、個股 payload freshness 仍未獨立驗證。
- first_observed_reference_at、last_preclose_change_observed_at、stable_at 是最新已觀察參考值的收斂，不是已證明交易所真正最終成交。
- confirmed_candidate 保持 validated=false；P_before／P_close／both validated 皆 0。±3% NOT_GENERATED，不能解讀為零檔符合 3%。
- 10/1 沒採樣的新 checkpoint 維持 NOT_SAMPLED。

10/2 官方日曆確認為交易日。原 cron 保留：11:47、13:07，備援 13:12／17／22（Asia/Taipei）。因 10/1 cron 曾晚到數小時，沿用原接力方式新增 10/2 一次性預備任務，每個等待 job 小於六小時，最後 11:47 交给原 live controller。實際啟動證據看 Issue #1／Actions；接力仍受 GitHub runner 可用性影響，不承諾準點。

尚未完成：六檔 mismatch 精確原因、每檔真正最終 P_before、cache 指標的個股可靠性、跨日正式收盤與收盤量驗證。明天不需要開啟使用者電腦、ChatGPT 或 Work。

[逐檔完整證據 JSON](official-exception-review.json)；[39 檔 CSV](official-exception-review.csv)；[原始證據審查](README.md)。
