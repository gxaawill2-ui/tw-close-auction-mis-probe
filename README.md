# TWSE MIS Closing Auction Probe

Independent public test repository for TWSE/TPEx closing-auction MIS evidence. It has no Production, Vercel, database, domain, or other-repository dependency. The 2026-10-01 capture and its raw Artifact are immutable evidence.

## Schedule

- GitHub Actions is scheduled early at `03:47 UTC` (`11:47 Asia/Taipei`), with the original `7 5 * * 1-5` and `12,17,22 5 * * 1-5` backups retained. Actual start may be delayed; completed/saved same-day captures are not rerun.
- The process retrieves the official company universe and official date-effective trading exclusions, then waits inside the runner. Company and tradable pools and source errors are separately saved.
- If the runner actually starts after `13:24:45`, the run is marked `failed_late_start`; it does not backfill 13:25 evidence.
- Full-market batch size is 50 and concurrency is 5.
- Full snapshots start around 13:24:50, 13:30:02, and 13:32:30. The last snapshot has a 13:33:15 cutoff: responses after it are retained but invalid for an on-time capture. Socket timeout is not a hard total request-duration guarantee, so actual response timestamps are checked.
- Samples remain 2330, 2317, 2454, 1341, 1410, 1240, 1781, 1813, subject to that day's official tradability. No substitute is silently selected if a fixed sample cannot trade.
- Preclose: 13:24:50–13:25:10 once per second, then 13:25:15–13:26:10 every five seconds (33 planned requests).
- Close: 13:29:50–13:30:15 once per second, then 13:30:20, 13:30:30, 13:30:45, 13:31:00, 13:31:30, 13:32:00, 13:32:30, 13:33:00, 13:33:15 (35 planned requests).
- Official checks at 14:50, 15:20, 17:50 only download the original capture Artifact and date-specific official tables; they never request MIS or backfill market evidence. Actual publication observations are saved. These are retry times, not claimed official release times.

GitHub scheduled workflows can be delayed. Every request stores its planned, sent, and received timestamps to milliseconds. A workflow merely starting is not proof that the capture succeeded.

## Safety and evidence rules

- Yahoo testing is not repeated.
- 2026-09-29 remains `missing / incomplete`.
- Missing values are never filled with zero.
- Outer fields, nested `trade` (t/z/v/ft and full object), full `queryTime`, `cachedAlive`, planned/request/response times and all retry attempts are preserved. Null, `-`, and empty values are never converted to zero.
- `server_age_ms = requested_at - server_time` is signed; received-at minus server time is also saved. queryTime contains no timezone offset: Asia/Taipei is an explicitly unverified interpretation. `cachedAlive` unit/meaning is UNVERIFIED, not assumed to be an official age field.
- Freshness/convergence tests compare age thresholds 5/15/30 seconds and 2/3 distinct server timestamps. Default research candidate: server has reached 13:25, valid same-date trade.t <13:25, age at receive <=15 seconds, stable trade.t/trade.z/v over three distinct fresh server timestamps. A repeated old cache cannot count as three new responses. This rule is provisional and has not proved independent final-trade truth.
- A `confirmed_candidate` is never `validated`. `P_before`, `P_close`, observation/server/trade times, classifications and evidence are saved per stock. No validated rule is enabled in this research version; validated counts remain 0 and strategy lists stay NOT_GENERATED until independent/cross-day evidence justifies a versioned rule. This is not a claim of zero ±3% stocks.
- Official closing-price matching alone does not prove P_before or volume semantics. `V_close - fresh V_before`, tv/s/trade.v comparisons remain UNVERIFIED.
- Daily official-source exclusions cover suspension snapshots, capital-reduction intervals and listing termination, with effective dates and URLs. No code blacklist; altered/periodic matching is tagged separately. Missing sources retain unproven symbols and mark denominator incomplete. Historical termination code/name/relisting conflicts do not silently remove current stocks.
- Reduction lookup is ±90 days; unannounced resume dates and other intraday temporary halt announcements remain a coverage limitation. Do not claim a fully verified normal-tradability denominator if source coverage is uncertain.
- Results and the daily ZIP are retained as a GitHub Actions Artifact for 30 days.
- Issue #1 is the single status page and is updated only with this repository's built-in `GITHUB_TOKEN`.

## Manual dry-run

Open **Actions → TWSE MIS Closing Auction Probe → Run workflow**, leave `dry-run` selected, and run. It verifies GitHub permissions, official-universe parsing, MIS connectivity, Issue updates, and Artifact upload without waiting for market times or generating a strategy signal.

Code/configuration pushes also invoke the same controlled dry-run and automated tests. Only actual schedules or an explicit `mode: live` wait for market captures. State/report commits do not trigger new capture jobs.

## Daily evidence and reports

`company_universe.json`, `tradable_universe.json`, `universe_exclusions.json`, full raw snapshots/probes, `normalized_freshness.csv`, `freshness_timeline.csv`, `freshness_report.json/md`, performance/errors, dated `official_validation.json`, candidates gate and ZIP are saved to Actions Artifacts.

The report includes per-sample first observed reference/last change/stability times, close trade time versus first observation time, volume comparisons, checkpoint convergence and rule sensitivity. Percentages are observational comparisons against a later fresh observed reference, not independent proof of final preclose trade completeness. Unsupported full-market stocks stay unverified.

[Status Issue #1](https://github.com/gxaawill2-ui/tw-close-auction-mis-probe/issues/1) / [2026-10-01 evidence review](reports/2026-10-01/README.md).
