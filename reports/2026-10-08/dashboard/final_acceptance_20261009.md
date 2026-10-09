# 2026-10-09 final acceptance continuation

Base main: `5942856042178434d3308389d9fffac5b45ee89c`.
Prior implementation CI: `37765644724` (success); base Pages: `37813114039` (success).
Acceptance performed on 2026-10-09. The public homepage automatically displayed
`2026-10-09 · 台北`, `今日休市`, and no candidate list. October 8 remains historical.

The only functional change removes the diagnostic refresh button and its click
listener. Initial automatic loading, 60-second polling, timeout, cache handling,
and diagnostics are preserved. A DOM test executes the diagnostic script and
checks both its initial seven requests and the next automatic polling cycle.
Browser CI now checks this page on desktop Chromium, mobile Chromium and iPhone
WebKit, and explicitly checks the public October 9 holiday with no stale list.

Local regression: Python 144 PASS; Node 26 PASS, including 16 homepage DOM/model
tests and the new diagnostic DOM/polling test. Actual browser rendering is gated
by the existing GitHub Actions browser job (local browser binaries unavailable).
Use the commit's Actions run and `dashboard-browser-<run ID>` acceptance artifact
for current browser results; do not substitute an old run's screenshots.

Seven candidate values, prices, times, convergence types, confidence and return
percentages match the previous accepted source. Decimal checks verified all
volume ratios, all returns, and the following MIS research volumes in lots:

| Code | Final trade time | Final auction | Intraday total | Ratio % |
| --- | --- | ---: | ---: | ---: |
| 3073 | 13:33:00 | 17 | 44 | 38.636364 |
| 3259 | 13:33:00 | 1 | 8 | 12.500000 |
| 3684 | 13:33:00 | 66 | 1255 | 5.258964 |
| 4706 | 13:30:00 | 36 | 498 | 7.228916 |
| 5355 | 13:30:00 | 1 | 121 | 0.826446 |
| 5543 | 13:30:00 | 6 | 8 | 75.000000 |
| 2024 | 13:30:00 | 7 | 73 | 9.589041 |

All are RESEARCH_ONLY and validated=false. Volume is MIS_EVIDENCE_CONFIRMED;
independent official volume validation remains false. Official P_close MATCH
does not validate P_before or volume. No source JSON was modified in this change.

Capture run `37730234383`, artifact `mis-probe-37730234383`, ID `11530906396`.
Original archive SHA256: `1b4caf9efcbb0575771726b356751f177bba37439179cb14bfc9b8a9bc9a88e0`.
Official archive run `37742790398`, SHA256:
`c44478870abc6ef1269565825738c014cf904870ba81a6b2aca17ea4998f3a15`.
Both saved archives were hash checked and unchanged; zero market requests.
Price fingerprint: `3951327c7d3f99fc46ebee67380c2498fc4ebb6014f255c7090bf2f1ef5ffa39`.

Daily publication remains wired after completed live capture, before diagnostic
status IO. The permanent `state/candidates/YYYY-MM-DD.json` is read anonymously
from main without requiring Pages redeployment. Bounded CAS retries, per-day
paths, fingerprint protection and explicit failed-publication records remain.
Postmarket validation adds annotations and preserves original live evidence.
All original market rules, schedules, scheduler records, secrets and tokens are
unchanged. Push CI skips controlled MIS live capture and its raw artifact upload.
October 12 is an open date in the persisted official calendar. Existing 13:00,
13:10, 13:18 capture and 14:50, 15:20, 17:50 validation settings are retained.
October 12 is configured, not a live run that has already been tested.

Final code SHA: resolve with `git log -1 --format=%H -- docs/diagnostic.js`.
