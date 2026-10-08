# October 8 live capture completion and candidate verification

Verified at 2026-10-08 16:54:40.906 +08:00.

## Provenance

- Original capture run: **37730234383**, event `workflow_dispatch`, historical conclusion `failure` (not rewritten or rerun).
- Original capture artifact: **11530906396**, `mis-probe-37730234383`.
- Original archive SHA-256: `1b4caf9efcbb0575771726b356751f177bba37439179cb14bfc9b8a9bc9a88e0`.
- Capture code commit: `2dd62b249a181d7045c957f0c33501cc574723cd`.
- Official validation run: **37742790398**, artifact **11534034875**, `mis-validation-37742790398`.
- Official archive SHA-256: `c44478870abc6ef1269565825738c014cf904870ba81a6b2aca17ea4998f3a15`.
- Official tables checked at `2026-10-08T15:20:18.859+08:00`; TWSE and TPEx both `AVAILABLE_SAME_DATE`, response dates `20261008`.
- Verification/fix code commit: `9e32bc6e8975782916bd06b527f0dac31d0a7031`.
- Candidate version: `DUAL_SNAPSHOT_RESEARCH_V1` with October 8 fresh A/B/C research hierarchy.
- Raw official URLs, table hashes, per-stock original observations and official rows are retained in the verification JSON files.
- Verification is `RESEARCH_ONLY`; all candidates remain `validated=false`.

## Exact root cause

The full `probe` job log (job **113157464714**) shows:

1. `13:34:12.719 +08:00`: live research summary produced seven candidates.
2. `13:34:25.432 +08:00`: Python terminated with **exit code 3**.
3. Artifact upload step succeeded and finalized artifact **11530906396**.

The original `results/controller_status.json` confirms `exit_code=3`, `status_errors=[]`. The persisted live record and original run summary both have `status=partial`, `phase=completed`, no controller exception.

Original `probe.live()` computed:

```python
raw_complete = all(x['metrics']['symbol_set_equal'] for x in primary) and not errors['probe_errors']
```

All five primary full-market snapshots had 1968/1968, `symbol_set_equal=true`, zero missing, and zero final HTTP errors. The official universe audit was date checked. However, **23 optional fixed-eight-stock research-probe records** had errors/missing symbols: 2 `MIS_EMPTY_BODY`, 20 records with missing symbols but `error=null`, and 1 final read timeout at the 13:33:15 checkpoint. Consequently `raw_complete=false`, the summary became `partial`, and the final `return 0 if headline == '✅ SUCCESS' else 3` returned 3.

There was also one pre-targeted-retry `CAPTURE_DEADLINE_NO_REQUEST` record for 25 symbols, preserved in the error report. This was not in the original `raw_complete` predicate and was **not the direct cause** of exit 3. The mandatory pre-C full-market capture and a later bounded retry both completed. No observations are fabricated to replace the skipped retry.

Official `PENDING_SCHEDULED_POSTMARKET` was **not the trigger for this failure**. It remains a distinct publication/verification state.

Backup run **37731689570** succeeded by skipping an existing immutable capture. It is not the original capture and does not make run 37730234383 successful.

## Fixed outcome contract

| Outcome | Required condition | Python exit |
|---|---|---:|
| CAPTURE_SUCCESS | Every mandatory raw phase executed and saved, same-day readable evidence, consistent saved research outputs, no incompleteness warnings | 0 |
| CAPTURE_PARTIAL | Same mandatory integrity requirements; some symbols/research prices unresolved, optional probe/retry failures or partial responses; exact counts and reasons retained | 0 |
| CAPTURE_FAILED | Missing/skipped mandatory phase, no usable mandatory response, corrupt raw data/output, incorrect trade date or universe-date audit, storage/package exception, true controller exception | non-zero |

Official PENDING and zero research candidates are not execution failures. Successful capture does not mean verified prices. The rule allows missing-symbol PARTIAL only when each mandatory phase has usable saved evidence; a complete mandatory-phase HTTP failure remains FAILED. Optional targeted close-C is either captured, `NOT_REQUIRED`, or explicitly warned `BLOCKED_HTTP_403_429`; it is never silently replaced.

GitHub upload remains a mandatory separate step with `if-no-files-found: error`, no `continue-on-error`. Its failure keeps the job red and marks the same capture `CAPTURE_FAILED`/`ARTIFACT_UPLOAD_FAILED`, even if Python had already marked phase completed. Package write failures and exceptions remain non-zero. Push CI skips both the controlled probe and artifact upload, so tests cannot call live MIS.

The corrected immutable October 8 replay is **CAPTURE_PARTIAL, exit 0**, with 23 probe-error records, one optional targeted-retry error, and **25 uncalculable stocks** retained. The original GitHub run remains historical failure; it is not recaptured to turn it green.

## Independent seven-stock audit

Original raw capture was loaded offline, replayed with unchanged convergence/freshness rules, and the entire saved candidate JSON matched replay exactly. Decimal arithmetic was independently recomputed over all **1943** calculable securities. The qualifying set is exactly seven, with zero omitted, duplicate, below-threshold or unresolved entries.

All seven saved research closes independently equal the same-date official raw-table closes: **7 MATCH / 0 MISMATCH / 0 UNAVAILABLE**. In particular, the three BC-only candidates (3073, 3259, 3684) were compared independently; their formal close was unresolved, so the formal 1939-MATCH summary alone could not establish their correctness.

The three BC candidates use **13:33:00 delayed trades confirmed by B and C**, not normal 13:30 closes. Four AB candidates use 13:30:00. All selected values were traced to same-day nested `trade.z`, not top-level simulation prices; each before trade time is earlier than 13:25. This proves consistency with the saved evidence and official close, **not independent official verification of the last pre-13:25 trade**.

The 25 uncalculable stocks remain `UNVERIFIED / UNKNOWN` and are listed with rejection reasons. It is not possible to assert whether any would exceed ±3% without qualifying evidence. No prices are guessed.

## Tests and unchanged boundaries

- Python: **101 tests PASS**. Node: **9 tests PASS**.
- Fix CI run **37752998025**, head `9e32bc6e8975782916bd06b527f0dac31d0a7031`, event `push`, success. Controlled-probe and raw-upload steps skipped.
- Cases cover official PENDING, zero/multiple candidates, unresolved/partial data, mandatory HTTP failure, missing/corrupt raw evidence, wrong date, true exception, package failure, upload failure after completion, duplicate backup skip and push no-live gates.
- Original capture archive and all raw inputs were hash checked before and after verification; unchanged.
- `convergence.py`, `close_research.py`, `freshness.py`, `tradable.py`, `official_quotes.py` and the official-validation workflow are unchanged. No price threshold, batch size, concurrency, token, secret, external schedule or hosting configuration changed.
- Status rendering adds capture outcome/warnings separately from official verification. It does not promote research to validated.

## Next trading day and preserved automation

The saved official 115-year calendar was checked by the October 8 live runner. October 9 is the National Day substitute holiday; October 10–11 is the weekend. **October 12 is the next normal trading day** in that calendar. The current TWSE official holiday page confirms October 9 closure: https://wwwc.twse.com.tw/zh/trading/holiday.html . Each live runner still rechecks the official calendar; exceptional/emergency future closure and runner availability cannot be guaranteed.

Existing cron-job.org primary/backups at 13:00/13:10/13:18 and official rechecks at 14:50/15:20/17:50 remain unchanged. Repository scheduler records retain all six enabled jobs, Asia/Taipei weekdays, and today's original/backup live and 14:50/15:20 dispatch runs demonstrate today's triggering. An attempted read-only console recheck reached a sign-in wall; no credentials were requested, rebuilt or extracted, and no cron settings were changed. Live confirmation of the console's current Enabled flags therefore rests on the prior verified configuration, not a new signed-in inspection.

GitHub backup schedule expressions remain unchanged. On a normal trading day with timely runner startup and functioning upstream sources, the existing live code writes RESEARCH_ONLY ±3% output before 13:35, even for zero candidates, and scheduled official comparison follows. No user operation is needed for the code fix or existing configured automation.
