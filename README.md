# TWSE MIS Closing Auction Probe

Independent, private test repository for the 2026-09-30 TWSE/TPEx closing-auction MIS capture. It has no Production, Vercel, database, domain, or other-repository dependency.

## Schedule

- GitHub Actions starts at `05:07 UTC` on weekdays (`13:07 Asia/Taipei`).
- The process fetches the official same-day TWSE/TPEx common-stock universe, then waits inside the runner.
- If the runner actually starts after `13:24:45`, the run is marked `failed_late_start`; it does not backfill 13:25 evidence.
- Full-market batch size is 50 and concurrency is 5.
- Full snapshots start around 13:24:50, 13:30:02, and 13:33:15.
- Eight representative securities are sampled once per scheduled second during 13:24:50–13:25:10 and 13:29:50–13:33:15.

GitHub scheduled workflows can be delayed. Every request stores its planned, sent, and received timestamps to milliseconds. A workflow merely starting is not proof that the capture succeeded.

## Safety and evidence rules

- Yahoo testing is not repeated.
- 2026-09-29 remains `missing / incomplete`.
- Missing values are never filled with zero.
- `c,n,z,pz,t,v,tv,s,d` are preserved without assuming field meaning.
- The first live run does not output ±3% signals. Official daily close matching is observational evidence only until trial-matching and volume semantics are proven.
- Results and the daily ZIP are retained as a GitHub Actions Artifact for 30 days.
- Issue #1 is the single status page and is updated only with this repository's built-in `GITHUB_TOKEN`.

## Manual dry-run

Open **Actions → TWSE MIS Closing Auction Probe → Run workflow**, leave `dry-run` selected, and run. It verifies GitHub permissions, official-universe parsing, MIS connectivity, Issue updates, and Artifact upload without waiting for market times or generating a strategy signal.
