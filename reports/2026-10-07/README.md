# 2026-10-07 saved-evidence official validation and close A shadow comparison

TPEx-only transport retry commit: `c899f3f2dea45d4ff8fb738baf8f7a6f1c8cadc0`.
Five total attempts, exponential delays 1/2/4/8 seconds, fresh `get_bytes` request each attempt.
Retries incomplete reads, disconnected/reset connections, timeouts, URL transport errors, HTTP 5xx, invalid UTF-8 and incomplete JSON. Exhaustion remains `PENDING_SOURCE_ERROR`; strict response date, status and nonempty table checks remain unchanged. TWSE parser and all capture/convergence rules remain unchanged.

Validation: 65 Python unittest tests PASS (including 7 new retry test methods), 8 Node status tests PASS.
No 10/7 MIS requests or capture reruns were performed.

## Official validation

- Capture run: `37574207304`; artifact: `mis-probe-37574207304`, ID `11463187978`.
- Capture SHA-256: `8bfdeef4e81d6baabc8d83e6cdcbcdf974b20b07f15a348fd28a72cd66d66e57`, unchanged after offline analysis.
- New validation run: `37597653369`, event `workflow_dispatch`, conclusion `success`.
- Validation artifact: `mis-validation-37597653369`, ID `11471157076`.
- Checked at `2026-10-07T17:01:02.476+08:00`.
- TWSE: `AVAILABLE_SAME_DATE`, 1,380 rows, response date `20261007`.
- TPEx: `AVAILABLE_SAME_DATE`, 12,245 table rows (all instruments), response date `20261007`.
- Formal selected-convergence comparison: MATCH 0, MISMATCH 0, UNAVAILABLE 1,971.
- Status is now `SAME_DATE_COMPARISON_ONLY`; the 1,971 unavailable formal checks reflect absent converged P_close, not incorrect MIS quotes.
- P_before converged remains 1,947 (ABC 1,742; AB 205); P_close converged remains 0; all validated flags remain false.

## close_reference_A shadow

Use only saved phase `close_reference_A`, nested `trade.z`, with exact Decimal comparison to same-day TWSE/TPEx closes. Capture started at the planned 13:32:30 reference; each batch's actual receive time is preserved. Universe has 1,971 securities; 1,969 had saved A records. One returned record outside the saved tradable universe was excluded.

| Market | MATCH | MISMATCH | UNAVAILABLE |
|---|---:|---:|---:|
| TWSE | 1,075 | 2 | 7 |
| TPEx | 869 | 4 | 14 |
| Total | 1,944 | 6 | 21 |

Total comparable: 1,950. Match rate: 1,944 / 1,950 = **99.6923076923%**.
All six mismatches have nested trade timestamps before 13:25; this classification is descriptive and does not establish the reason for each price discrepancy.

| Code | Name | Market | MIS trade.t | MIS trade.z | Official close | MIS minus official | Classification |
|---|---|---|---|---:|---:|---:|---|
| 3226 | 龍鋒 | TPEx | 13:24:53 | 55.70 | 57.80 | -2.10 | EARLIER_LAST_TRADE |
| 3516 | 亞帝歐 | TPEx | 13:02:30 | 26.25 | 26.40 | -0.15 | EARLIER_LAST_TRADE |
| 4192 | 杏國 | TPEx | 13:10:53 | 17.50 | 17.80 | -0.30 | EARLIER_LAST_TRADE |
| 4406 | 新昕纖 | TPEx | 10:52:03 | 10.00 | 10.05 | -0.05 | EARLIER_LAST_TRADE |
| 1213 | 大飲 | TWSE | 11:58:18 | 7.06 | 7.31 | -0.25 | EARLIER_LAST_TRADE |
| 3593 | 力銘 | TWSE | 11:19:33 | 10.65 | 10.75 | -0.10 | EARLIER_LAST_TRADE |

## Shadow ±3% candidates

Require existing P_before convergence AND close A official MATCH, then compute `official_close / P_before - 1` using Decimal. Four candidates, all **RESEARCH_ONLY**, all P_close validated false.

| Code | Name | Market | P_before | P_before trade time | A and official close | Tail return | Pre convergence |
|---|---|---|---:|---|---:|---:|---|
| 6204 | 艾華 | TPEx | 108.00 | 13:24:00 | 111.50 | +3.240741% | ABC |
| 6228 | 全譜 | TPEx | 17.35 | 13:07:40 | 18.15 | +4.610951% | ABC |
| 6855 | 數泓科 | TPEx | 112.00 | 13:23:26 | 115.50 | +3.125000% | ABC |
| 8047 | 星雲 | TPEx | 43.50 | 13:19:25 | 46.95 | +7.931034% | ABC |

Deliverables: `shadow_candidates_2026-10-07.csv`, JSON, and `mis-close-A-shadow-2026-10-07.zip` containing per-security comparison, all mismatch/unavailable rows, same-day official raw JSON, validation summary and cron screenshot. These outputs were saved as downloadable artifacts. Original capture artifact remains the authoritative MIS source.

Offline reproduction: run `compare_close_a.py --capture <original capture ZIP> --official-dir <validation artifact validation-results directory> --output <new report directory>`. The script performs no network calls and hashes the original capture before and after comparison.

## External official schedules

Verified through the signed-in cron-job.org UI: existing 14:50 job `8596586`; missing 15:20 job `8596641` and 17:50 job `8596664` were cloned from saved official jobs, preserving existing request authorization. All three enabled, Asia/Taipei, Monday-Friday, POST to `mis-official-validation.yml/dispatches`, body `{"ref":"main"}` and required four headers. Token was neither re-entered nor extracted/output. GitHub backup schedules at 14:50/15:20/17:50 Taipei remain unchanged. New recurring jobs' future executions are not yet observed.

No action required from the user.
