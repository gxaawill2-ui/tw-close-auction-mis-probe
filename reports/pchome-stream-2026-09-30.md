# PChome streamed-prefix test — 2026-09-30

The reader can stop after the newest eligible second of the trade table, but this full-market attempt failed on HTTP 429. The green Actions run indicates the program and artifact completed, not full-market data success.

## Offline equivalence

Replay of 95 previously saved complete pages using 4,096-byte chunks selected exactly the same time, price and cumulative quantity as the full-page parser (95 matches, zero mismatches). Total consumed prefix bytes: 2,334,720 versus full bodies 12,879,687 (81.87% less). This is offline application consumption, not measured network-wire savings. Samples were all TPEx; original data provenance and trial exclusion remain unvalidated.

## New runner test

- Run: https://github.com/gxaawill2-ui/tw-close-auction-mis-probe/actions/runs/36686727280
- Artifact: https://github.com/gxaawill2-ui/tw-close-auction-mis-probe/actions/runs/36686727280/artifacts/11083704777
- Official dynamic universe: 1,978 stocks; concurrency 5.
- Official universe retrieval: 15:57:28.880–15:58:31.188 Asia/Taipei (about 62 seconds), excluded from capture wall time.
- Capture: 15:58:31.188–15:58:40.132 Asia/Taipei; wall 8.944 seconds **until stopping**, not full-market completion.
- Requests/attempted stocks: 42.
- Valid-looking pre-cutoff observations found: 40 (TWSE 21, TPEx 19); no missing prices replaced by zero.
- HTTP 429: 2 (1220, 1742). On the first 429 new submissions stopped; already in-flight calls completed. No retries or access-limit bypass.
- HTTP 403 / timeout / retry / empty-or-invalid: 0 / 0 / 0 / 0.
- Not attempted: 1,936; total lacking a usable observation: 1,938.
- Application bytes consumed: 969,098 including HTTP error bodies.
- Successful body bytes mean: 24,220.35; median: 24,523.
- Request latency ms min / mean / median / P95 / max: 310.302 / 1027.705 / 1017.864 / 1530.975 / 1766.562.
- 39 of the 40 observations were obtained before the trade table ended; one small table was received in full.

Examples (unvalidated source observations, not proven P_before): 2330 13:24:59 2495; 2317 13:24:57 252.5; 2454 13:24:58 4980. Each consumed about 24.6 KB and stopped before the complete trade table.

## Interpretation

Smaller consumption is feasible. The test still does not establish a five-minute all-market capture, safe request quota, or guaranteed latest actual transaction. Request count remains roughly one request per stock; streaming does not eliminate request-count-based limits. The two runs have different stock order and runner conditions, so their failure thresholds and wall times are not controlled comparisons. No official fixed quota is inferred from these observations.

Reading the entire first eligible second avoids blindly selecting an arbitrary row with the same timestamp. Descending order was observed in the inspected prefix and offline samples; the source has not guaranteed chronology, trial exclusion, trade date or tick completeness. No ±3% signals are generated.

This is a postclose connectivity test, not a recovered MIS snapshot. Existing MIS workflow is unchanged (blob fe72f106c2a688af63b01731081e2184d99d1cf2, cron `7 5 * * 1-5`). No other repo or Production was modified.
