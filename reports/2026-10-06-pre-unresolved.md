# 2026-10-06：74 檔 P_before 未收斂研究

只重播 run 37416416998 / Artifact 11391549138，沒有任何 MIS 網路请求。Artifact SHA256：7f89e906862b76f5d5c22edcd116d0a7308d9ce81d974d3730b090889dd0906a

分類指保存規則的拒絕原因；cache 的服務端根因仍未證明。

|分類|檔數|
|---|---:|
|stale_cache|70|
|server_time_regression|0|
|inconsistent_trade_state|0|
|no_trade_or_sparse_trade|0|
|missing_trade_fields|4|
|freshness_rule_too_strict|0|
|other|0|
|unknown|0|

|市場|Universe|未收斂|比例|Server age median / P95(ms)|原 A/B 未收斂|retry 救回|retry 成功率|
|---|---:|---:|---:|---|---:|---:|---:|
|TWSE|1083|0|0.00%|1312.0 / 3408.0|1|1|100.00%|
|TPEx|888|74|8.33%|2378.0 / 55515.0|236|162|68.64%|

Metadata 以涉及該市場的不同 HTTP batch 統計；不把同批每檔股票當成獨立 server 樣本。完整 JSON 另保存 A/B/targeted retry 分層統計，避免用 retry 的選樣直接推論 cache 機制。

TWSE 沒有 cachedAlive；TPEx 有 13/49 個 batch 報 cachedAlive，median 41078，P95 61364。單位尚未驗證。兩市場均無 server timestamp regression。trade.t 有變動股票：TWSE 1、TPEx 86；外層 v 變動股票皆為 0。單日證據支持 TPEx 本次 stale 回應較多，不能證明固有 cache 行為不同。

|Shadow 規則|收斂|未收斂|多救回|可疑量欄位衝突|
|---|---:|---:|---:|---:|
|trade.t + trade.z + v|1897|74|0|0|
|trade.t + trade.z|1897|74|0|0|
|trade.t + trade.z + trade.v|1897|74|0|0|

可疑 false conflict 是同 trade.t/trade.z、不同量欄位之 fresh distinct observation 的 proxy；沒有獨立成交真值，因此 proven_false_conflict_count=null，不把 proxy 當成確定誤判。移除 v 救回 0 檔，v 不是本次主要 blocker。

重點：46 檔有兩筆不同 server time 且 trade.t/trade.z/v 相同的 fresh 觀察，但中間 stale 回應 reset 了 pending 配對。最後一筆 retry 即使 fresh，也只算 reset 後第一筆。因此報告的最後 reason 可能仍寫 stale_cache，不能誤讀為最後一筆本身必定 stale。允許跨 stale 配對可能改變 46 檔，只是 shadow，沒有修改舊規則。

74 檔中：35 檔所有非缺值價格相同；38 檔最大報告 v <=10（僅低量指標）；4 檔所有可讀成交時間早於 13:00。4 檔 missing_trade_fields 是 1813、2035、2073、2724：盘前 nested trade.t/z/v 缺失、外層 v=0，但官方盤後成交股數大於 0，不能判全天無成交。

## 10/7 C 實驗

新增 13:29:00 pre_reference_C，全市場 batch 50 / concurrency 5，date gate 從 2026-10-07 啟用。原 A/B 時刻及嚴格 identity 完全保留；C fallback 仍要求 trade.t/trade.z/v 一致，不採用放寬 v 的 shadow 規則。

為保留 C 的時間窗，10/7 起 pre B 和 C 前的 targeted pass 截止 13:28:58；C 後仍可 targeted retry 至原截止 13:29:30。請求串行，不增加 batch concurrency。若錯過 C 750ms 起跑容許或截止，明確 NOT_SAMPLED，不事後補造。

原 A/B 成功不被壞 C 撤銷；原 A/B 未收斂才可使用 fresh AC/BC，並擋 fresh contradiction/regression。ABC 類別與 AB/AC/BC 互斥；AB 包括舊 targeted-retry 救回者，另有原始純 A/B 指標。所有 validated=false。

P_close 13:32:30 / 13:33:20 及 close targeted retry 未改。輸出 pre_reference_C_summary.json、日期版 research_candidates_2026-10-07.csv/json；數字必須等真實 10/7 Artifact，不能用測試 fixture 當實績。

驗證：58 Python tests、8 Node status tests PASS；保存 10/6 raw hash 與 1897/1947/74 replay PASS。GitHub workflow、cron-job.org state、Token、Pages、Production 無變更。
