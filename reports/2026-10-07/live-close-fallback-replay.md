# Saved October 7 evidence: fresh 13:30 close research fallback

Capture `37574207304`, artifact `11463187978`; same-date official validation `37597653369`.
Original artifact SHA-256 before and after replay:
`8bfdeef4e81d6baabc8d83e6cdcbcdf974b20b07f15a348fd28a72cd66d66e57`.
No MIS request or artifact write was performed. A freshness/statistics pass was completed before implementation.

## Offline evidence gate

Freshness uses the unchanged saved-response rule: correct symbol date, plausible server clock, receive/server age from -1 to 15 seconds, successful nonduplicate observation, valid reference schedule, trade identity and capture deadline. `cachedAlive` is preserved without assuming its unit.

| Saved A group | Count | MATCH | MISMATCH | UNAVAILABLE | Comparable match rate |
|---|---:|---:|---:|---:|---:|
| trade.t = 13:30:00, all freshness states | 1,715 | 1,715 | 0 | 0 | 100% |
| trade.t > 13:30:00 | 0 | 0 | 0 | 0 | N/A |
| trade.t < 13:30:00 | 235 | 229 | 6 | 0 | 97.446809% |
| Missing trade time | 21 | 0 | 0 | 21 | N/A |
| Fresh A, all trade times | 1,919 | 1,895 | 6 | 18 | 99.684377% |
| Stale or otherwise unusable A | 52 | 49 | 0 | 3 | 100% |
| Fresh A and exactly 13:30:00, fallback eligible | **1,675** | **1,675** | **0** | **0** | **100%** |
| Fresh A and trade.t < 13:30:00 | 226 | 220 | 6 | 0 | 97.345133% |

Rates exclude unavailable prices from the denominator. Stale price equality does not make an observation eligible. This is one saved session's result, not a guarantee for future sessions.

Each security's downloadable CSV/JSON records request start, received time, queryTime.sysTime, cachedAlive, request/server and receive/server age, nested trade.t/z/v, total v, freshness, eligibility and official result.

## New rule replay

Existing P_before unchanged: 1,947 converged, ABC 1,742, AB 205, AC/BC 0, unresolved 24.
Original formal P_close convergence remains 0. Optional new research layer on the same unmodified October 7 evidence yields:

- AB/AC/BC research convergence: 0/0/0 (October 7 has no close C; none fabricated).
- A_1330_fresh_candidate: 1,675.
- Delayed unconfirmed: 0.
- Unresolved: 296.
- Both research prices calculable: 1,672.
- ±3% research candidates: 4, all MEDIUM_RESEARCH, all validated=false.

| Code | Name | Tail return |
|---|---|---:|
| 6204 | 艾華 | +3.240741% |
| 6228 | 全譜 | +4.610951% |
| 6855 | 數泓科 | +3.125000% |
| 8047 | 星雲 | +7.931034% |

## October 8 live implementation

The original `pair`, `pre_with_c`, `rejection` and probe-conflict functions remain byte-for-byte equivalent by AST comparison. The additional close research layer has priority AB, AC, BC, then fresh A with trade.t exactly 13:30. Pair identity retains trade.t/trade.z/total-v equality and strictly advancing distinct fresh server timestamps. Fresh contradictions or regressions block an earlier pair or A fallback. Delayed single observations do not get a calculable price. A trade before 13:30 cannot supply a singleton fallback. Existing formal P_close fields and all validated flags remain independent and unpromoted.

- Close A: original order, 13:32:30.
- Close B: reversed saved universe order, 13:33:20; bounded at 13:34:08 to reserve C.
- Close C: 13:34:10, only symbols lacking nonconflicting dual fresh evidence, rotated/reversed deterministic grouping, bounded at 13:35:00. Healthy AB symbols are excluded; no extra full-market unconditional round or repeated close retry loop. HTTP 403/429 blocks C.
- All snapshots keep batch size 50 and concurrency 5. Expired requests cannot become accepted evidence.
- Before postmarket work, live writes dated CSV/JSON, `live_research_summary.json`, stdout and GitHub step summary. HIGH_RESEARCH applies to AB/AC/BC; MEDIUM_RESEARCH to A-only; all validated=false. Empty candidate lists are valid outputs.
- Live no longer waits for official HTTP downloads after October 8. Official validation still runs through the unchanged 14:50/15:20/17:50 schedules, reads saved C if present, and compares formal selected closes while the research report independently checks its research MIS prices against official values. Official prices never substitute the live research P_close.
- Push-triggered runs execute tests only, preventing today's commit from issuing MIS connectivity/capture requests. Dispatch and scheduled live behavior are unchanged.

Read-only cron-job.org verification on October 7 shows existing live jobs' next executions on October 8 at 13:00, 13:10 and 13:18, all enabled. October 8 is not closed in the saved official annual calendar; the live runner retains its calendar recheck and no-late-backfill guard. The code is ready for automatic output around 13:35 if the runner starts on time and valid evidence is captured; tomorrow's candidate count cannot be predicted.

Validation: 82 Python tests and 8 Node status tests PASS, including an October 8 mocked-clock orchestration/loader test, all requested fallback cases, conflicting fresh observations, cache-key grouping, targeted symbol selection and byte-preserving replay. TPEx retry and official-validation workflow remain unchanged.
