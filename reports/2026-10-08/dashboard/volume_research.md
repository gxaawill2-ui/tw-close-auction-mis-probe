# October 8 dashboard / volume acceptance

The seven original HIGH_RESEARCH candidates and all price rules are unchanged.
The public daily file is derived from capture run 37730234383, artifact
mis-probe-37730234383 (11530906396). The original ZIP remains untouched.
Official price annotations use saved 15:20 run 37742790398 (11534034875).
See `acceptance.json` for source hashes, audit timestamps, as-of time and version.

## Semantics and units

The primary sources are the actual TWSE MIS production frontend assets listed
with SHA256 in root `volume_contract.json`. Both regular TWSE/TPEx tables map
transaction volume to `tv` and accumulated volume to `v`. The official fallback
maps nested actual `trade.v` into missing `tv`/`s` while choosing actual `trade.t`
and `trade.z`. The official UI states regular quotes use trading units, ordinary
stock units are 1,000 shares, and excludes odd-lot, block, off-hour fixed price,
auction and tender transactions. Existing company universe excludes ETF/TDR /
foreign second listings with different unit sizes. No unit is inferred from a
variable name alone. See source URLs and immutable fetched-asset hashes.

For each displayed stock, use the two adopted fresh P_before observations and
the two adopted fresh P_close observations. Locate their exact raw records by
phase/request/response timestamps, not the latest available quote. Require:

- Same stock, market, date; two fresh advancing server observations per pair.
- Same pre-auction cumulative `v` on both adopted pre observations.
- Same final cumulative `v` on both adopted close observations.
- Actual outer quote (`ts=0`), outer `t/z` matches nested selected closing trade.
- `trade.v = tv = s = final v − pre-auction v`, positive, on both close observations.
- Final trade time is 13:30:00 or 13:33:00. Unsupported times/units stay unknown.

This confirms seven **MIS research volumes**, not independent official volume
validation. Missing/inconsistent fields produce null for volume and ratio and
never block a valid price candidate. A single fresh A fallback is insufficient
for this two-observation volume gate, although its original price rule remains.

| Code | Final time | Pre v | trade.v / tv / s / delta | Final v | Ratio |
|---|---|---:|---:|---:|---:|
| 3073 | 13:33:00 | 27 | 17 | 44 | 38.636364% |
| 3259 | 13:33:00 | 7 | 1 | 8 | 12.500000% |
| 3684 | 13:33:00 | 1189 | 66 | 1255 | 5.258964% |
| 4706 | 13:30:00 | 462 | 36 | 498 | 7.228916% |
| 5355 | 13:30:00 | 120 | 1 | 121 | 0.826446% |
| 5543 | 13:30:00 | 2 | 6 | 8 | 75.000000% |
| 2024 | 13:30:00 | 66 | 7 | 73 | 9.589041% |

All counts in this table use the confirmed 1,000-share trading unit (張).
The three delayed stocks use BC, not their earlier A pre-closing trade. For
4706 the adopted pre pair is B + targeted retry, preserving the original identity.

## Official cross-check and timing

Official daily shares for 2024/3073/3259/3684/4706/5355/5543 are respectively
74,329 / 48,861 / 8,099 / 1,275,775 / 506,741 / 121,065 / 8,010. These differ
from regular MIS final accumulated volume ×1,000; daily totals have a different
scope and are never substituted into either volume field. Their presence does
not establish a last-auction volume. Per-stock evidence retains both numbers.

Live selection is replayed strictly as of 2026-10-08 13:34:12.719 +08:00 with
empty official checks. Exact original candidate equality is mandatory. Official
annotations are added afterwards with the real 15:20 verification timestamp.
The volume semantic audit occurred after market close and is separately stamped;
it is not presented as information already audited at 13:35 on October 8.
Prices/P_before times/confidence/false validation remain the original evidence.

## Publication and operations

The live controller publishes only after mandatory saved captures and derived
outputs pass completion checks. It publishes one permanent date-isolated JSON
using Contents API CAS, three bounded retries and an immutable price fingerprint.
Repeated identical calls do not create another commit. A live retry cannot erase
later official annotations. Date conflicts, incomplete data and price conflicts
fail closed. Publication failures retain true capture outcome and exit nonzero;
official reports still persist even if the separate website publication fails.
The existing official saved-artifact workflow can recover a missing public file.

The homepage reads credential-free raw main data directly, avoiding daily Pages
rebuild latency and the GitHub-token Actions suppression rule. It polls every
60 seconds, or 20 seconds during 13:30–13:40 Taipei, with cache bypass and bounded
timeouts. No manual controls. Closed days, missing results, completed empty lists,
partial coverage, publication delays and failed reads remain distinct. No prior
date is shown as today. Stable rows are not rebuilt on each refresh.

Existing schedules and secrets are untouched. Push CI skips controlled live and
artifact steps. Pricing/freshness/cache/convergence modules remain byte-identical
to the accepted base. No additional MIS market requests were made by this work.
