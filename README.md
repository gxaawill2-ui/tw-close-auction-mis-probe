# TWSE MIS Closing Auction Probe

Independent public test repository for TWSE/TPEx closing-auction MIS evidence. It has no Production, Vercel, database, domain, or other-repository dependency. The 2026-10-01 and 2026-10-02 captures and their raw Artifacts are immutable evidence.

## Schedule

- Primary design: cron-job.org → REST workflow_dispatch → the existing GitHub live workflow. External weekday triggers are 13:00 / 13:10 / 13:18 Asia/Taipei. Actual account setup and an external Test run are still PENDING_USER_SETUP until verified; no credential is stored in this repo. [Exact one-time setup](docs/cron-job-setup.md).
- GitHub Cron remains second-layer backup, not the sole scheduling claim. GitHub Pages publishes the credential-free `/docs` status UI and reads permanent public state directly. [Status page](https://gxaawill2-ui.github.io/tw-close-auction-mis-probe/) requires one-time Settings → Pages → main /docs → Save.
- GitHub Actions is scheduled early at `03:47 UTC` (`11:47 Asia/Taipei`), with the original `7 5 * * 1-5` and `12,17,22 5 * * 1-5` backups retained. Actual start may be delayed; completed/saved same-day captures are not rerun.
- The process retrieves the official company universe and official date-effective trading exclusions, then waits inside the runner. Company and tradable pools and source errors are separately saved.
- If the runner actually starts after `13:24:45`, the run is marked `failed_late_start`; it does not backfill 13:25 evidence.
- The first live run atomically claims the date with the Contents SHA CAS. Duplicate dispatch cannot overwrite it. Claims do not auto-expire after crashes; an incomplete claimed day stays incomplete. `capture_blocked` prevents replay of expressly missing historical dates. Actual two-dispatch safety acceptance uses a separate `state/tests/` namespace, no MIS and no market evidence.
- Full-market batch size is 50 and concurrency is 5.
- The 13:24:50 full snapshot is research context, never strategy P_before. P_before references start at 13:27:00 (A) and 13:28:15 (B). P_close references start at 13:32:30 (A) and 13:33:20 (B). There is no new full-market 13:30 snapshot; fixed probes retain that transition evidence.
- Only affected symbols are retried, until 13:29:30 for preclose or 13:35 for close. Every retry retains its own raw records. A phase missed by over 750 ms is explicitly NOT_SAMPLED; any later replacement is labelled targeted_retry, never backdated to A/B.
- Socket timeout is not a hard total request-duration guarantee. Actual response timestamps are checked against deadlines; late responses are retained and rejected by the evidence gate. HTTP 403/429 stops targeted retries.
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
- `freshness.py` preserves the earlier fixed-probe convergence/sensitivity research. `convergence.py` is the new full-market candidate gate: two distinct increasing fresh server observations with exactly equal nested trade.t/trade.z and outer cumulative v. Missing price/volume, wrong dates, stale clocks, clock regression, duplicate symbols and probe contradictions cannot certify a pair. Receive/server age <=15 seconds is explicitly a research threshold, not a cache guarantee. Clock freshness alone does not prove a stock's final trade.
- A/B equality produces `p_before_converged_candidate` only for trade.t <13:25:00. Original references and adopted replacement pairs are saved separately; a rejection breaks the consecutive stable sequence. Recovery requires a new pair of distinct fresh observations, not choosing the largest trade.t or assuming a fixed wait is sufficient.
- Close B/retries must have server time >=13:33:00. A fresh pair with trade.t=13:30:00 is normal even if first observed late. A 13:33 transition is flagged delayed candidate and targeted again to establish a stable pair. Unchanged pre-13:25 trades remain no-closing-new-trade candidates, not missing symbols, pending official cross-check.
- Every candidate remains `validated=false`. Research-only ±3% candidates use only both-converged positive prices; official price mismatches and probe conflicts are excluded. PENDING official prices remain explicitly unverified research. Formal signals stay NOT_GENERATED until independent/cross-day evidence justifies a versioned rule.
- Official closing-price matching alone does not prove P_before or volume semantics. `V_close - fresh V_before`, tv/s/trade.v comparisons remain UNVERIFIED.
- Daily official-source exclusions cover suspension snapshots, capital-reduction intervals and listing termination, with effective dates and URLs. No code blacklist; altered/periodic matching is tagged separately. Missing sources retain unproven symbols and mark denominator incomplete. Historical termination code/name/relisting conflicts do not silently remove current stocks.
- Reduction lookup is ±90 days; unannounced resume dates and other intraday temporary halt announcements remain a coverage limitation. Do not claim a fully verified normal-tradability denominator if source coverage is uncertain.
- Results and the daily ZIP are retained as a GitHub Actions Artifact for 30 days.
- Issue #1 is the single status page and is updated only with this repository's built-in `GITHUB_TOKEN`.
- Issue #1 and GitHub Pages expose the same permanent state. Pages calculates today's date in Asia/Taipei and reads `state/live/<today>.json`; it never shows yesterday's SUCCESS as today's, even when both schedulers failed to trigger. A same-day dry-run cannot mask a missing live day. PAT creation and cron-job.org Authorization header entry are performed only by the user, outside Work.

## Manual dry-run

Open **Actions → TWSE MIS Closing Auction Probe → Run workflow**, leave `dry-run` selected, and run. It verifies GitHub permissions, official-universe parsing, MIS connectivity, Issue updates, and Artifact upload without waiting for market times or generating a strategy signal.

Code/configuration pushes also invoke the same controlled dry-run and automated tests. Only actual schedules or an explicit `mode: live` wait for market captures. State/report commits do not trigger new capture jobs.

## Daily evidence and reports

`company_universe.json`, `tradable_universe.json`, `universe_exclusions.json`, full raw snapshots/probes, `normalized_freshness.csv`, `freshness_timeline.csv`, `freshness_report.json/md`, `convergence_report.json/md`, `convergence.csv`, `unknown_convergence.json`, `unknown_symbols.json`, performance/errors, dated `official_validation.json`, research `candidates.json` / `research_candidates.json` / `research_candidates.csv` and ZIP are saved to Actions Artifacts. Candidate exports retain trade times, return percentage, convergence evidence and validated=false; full-market rows also retain requested server-time aliases, per-symbol targeted_retry_count and stale_seen.

2026-10-05 is permanently marked `missing / incomplete — scheduler did not trigger`, blocked from live backfill. No October 5 strategy candidates exist. Infrastructure dry-runs and isolated guard tests after the missed window are not market evidence or proof that cron-job.org is configured.

The dual report separates original A/B convergence from targeted recovery, lists stale batches/clock regressions/retry counts, delayed candidates, no-new-close stocks and research-calculable counts. Per stock it retains adopted A/B observations and server timestamps, original evidence, price/trade time, unknown reasons, probe agreement and volume research. Official validation compares the selected converged close candidate rather than a later stale response.

2026-10-02 Artifact `mis-probe-36856545941` has no new reference A/B samples. Its dual offline replay is NOT_SAMPLED, without reconstructing market evidence. [Next-session design and saved-cache test](reports/2026-10-02/dual-snapshot-plan.md).

The report includes per-sample first observed reference/last change/stability times, close trade time versus first observation time, volume comparisons, checkpoint convergence and rule sensitivity. Percentages are observational comparisons against a later fresh observed reference, not independent proof of final preclose trade completeness. Unsupported full-market stocks stay unverified.

[Status Issue #1](https://github.com/gxaawill2-ui/tw-close-auction-mis-probe/issues/1) / [2026-10-01 evidence review](reports/2026-10-01/README.md).
