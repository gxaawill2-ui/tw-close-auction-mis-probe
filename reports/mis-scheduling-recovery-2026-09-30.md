# MIS scheduling recovery — 2026-09-30

## Actual missed capture

The original weekday cron `7 5 * * 1-5` was observed creating a scheduled run only at 2026-09-30 19:05 Taipei. The GitHub job started at 19:05:10; probe Python started at 19:05:13.318. It exited with failed_late_start and saved that result. No preclose snapshot was reconstructed, and no ±3% list was generated.

- Scheduled run: https://github.com/gxaawill2-ui/tw-close-auction-mis-probe/actions/runs/36706343364
- Original failure evidence: https://github.com/gxaawill2-ui/tw-close-auction-mis-probe/actions/runs/36706343364/artifacts/11091459706
- Persistent state: state/live/2026-09-30.json

The previous generic failure step overwrote the specific late-start explanation in Issue #1. The new controller preserves the actual reason.

## Changes in this independent repository only

- Keep the original 13:07 Taipei launch; add 11:47 early launch and 13:12/13:17/13:22 backups. Standard ubuntu-latest runner; builtin GITHUB_TOKEN only.
- Live runs share a concurrency group. Persistent daily records prevent a backup from overwriting an existing complete or partial preclose capture.
- Capture deadline is checked at actual runner start, after official universe preparation, and before starting preclose capture. Late runs don't backfill.
- Issue/file IO during precision phases runs on a background queue. The old code synchronously updated GitHub at 13:24:50 before launching capture, which could delay it.
- Live status, dry-run status, schedule receipts and the pre-armed relay have separate persistent JSON records under state/. SHA-based writes protect concurrent updates. Prior days are retained.
- Fixed Issue #1 displays an explicit date, daily failure reason and a separate dry-run section. Old/dry success cannot turn today's missing capture into success.
- Health checks are scheduled for 13:40/13:50. These depend on GitHub's scheduler too, so exact health-check execution time is not guaranteed.
- Official universe downloads retry transient truncation/network failures at most three times, with every attempt recorded. No old universe fallback; no retry after HTTP 403/429.
- Official TWSE market holiday calendar is checked. The next verified trading date is 2026-10-01.

## Verification

Six local regression checks passed: late-start refusal; late-ready refusal; daily deduplication; old-success isolation; dry-success isolation; interrupted official-download recovery.

First new push test failed on a truncated official stock-universe download. That failure was preserved. The retry/timestamp fixes were then verified by a successful new runner:

- Successful connectivity run: https://github.com/gxaawill2-ui/tw-close-auction-mis-probe/actions/runs/36711548475
- Runner's recorded start: 2026-09-30 19:55:50.038 Taipei.
- Python executed; dynamically fetched official TWSE+TPEx universe: 1,978.
- MIS 8/8 returned; not a full-market or field-semantics verification.
- Workflow updated Issue #1 and durable state automatically.
- Artifact uploaded: https://github.com/gxaawill2-ui/tw-close-auction-mis-probe/actions/runs/36711548475/artifacts/11094283676

The date-specific 19:57 actual-schedule test had not appeared in run history by the last check at approximately 20:08. Push success is not reported as schedule success. Receipt code will persist any actual schedule event that arrives later.

## Tomorrow's workflow is already running tonight

To reduce reliance on tomorrow's cron, the 2026-10-01 workflow was started today by the authorized configuration push:

https://github.com/gxaawill2-ui/tw-close-auction-mis-probe/actions/runs/36712518342

Verified runner start: 2026-09-30 20:05:06.436 Taipei. The first waiting job is in_progress, Python wrote state/armed/2026-10-01.json, and Issue #1 shows armed_running / hold_1.

Relay targets, all Asia/Taipei:

1. Current runner waits until 2026-10-01 00:47.
2. Next dependent runner waits until 06:07.
3. Next dependent runner waits until 11:47.
4. The live runner fetches that day's official universe, waits until 13:24:50, captures the close interval and preserves results.

Waiting jobs are limited to 350 minutes each, below GitHub's hosted-job six-hour limit. The live job shares the normal live concurrency group and daily deduplication. The original cron and backups remain as additional paths. A failure in a relay segment is recorded by a final outcome job when possible. Hosting/queue failures can still occur; tomorrow's live success has not yet been observed.

No user computer, ChatGPT or Work session is required after today's launch. No Production, other repository, Vercel, Cloudflare or production database was changed.

## Data validation remains unfinished

Scheduling recovery is not proof of MIS field semantics. z/pz/t/v/tv/s trial-matching behavior, actual pre-13:25 trade price, formal close identification, delayed-close handling and price comparisons still require live evidence. All signals remain NOT_GENERATED until that evidence is established. The current delayed raw capture does not itself certify a formal close.

Issue: https://github.com/gxaawill2-ui/tw-close-auction-mis-probe/issues/1

Primary platform documentation:
- Scheduling can be delayed or dropped: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- Hosted job execution limits: https://docs.github.com/en/actions/reference/limits
