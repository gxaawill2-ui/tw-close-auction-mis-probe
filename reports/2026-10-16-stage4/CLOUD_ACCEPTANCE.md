# Stage 4 synthetic transport acceptance — 2026-10-16

Cloudflare build 87562867-f531-48ea-bcbc-6d6a98e0170d succeeded at 2026-10-16T02:05:59Z (10:05:59 Asia/Taipei).

- Accepted source commit: 6ee41f6680f94ea3260dc55e63d751536aeee745
- Worker: tw-tail-stage4-20261015-test
- Worker version: 8636f298-e11e-443a-85ee-ccfd5b26e422
- Local tests: 112 passed, 0 failed.
- Public data embeds 22 successful pre-final checks, including all four ETag variants, authorization/signature rejection, version conflicts, per-row updates, and withdrawal.
- Successful build additionally confirms the final synthetic write and read assertions.
- Public server write receipt: 2026-10-16T02:05:56.004Z.
- Anonymous public JSON was retrieved separately and matched the accepted source commit.

The initial weak comparison fix alone did not make the immediate build pass: build fb8e409a-fb47-4dba-b82d-ce90dc0911d4 still reported etag-current-304_HTTP_200, although later standalone requests all returned 304. The accepted version waits for the validator revision and performs bounded retries only for the identical version and hash. Every ETag check must still actually receive 304. Persistent 200 responses fail. This supports deployment propagation as the cause of the transient result; it does not establish the exact serving instance used by the earlier failed build.

Scope limits: SYNTHETIC future date 2099-01-01 only; VERIFIED=0. No real market evidence, external browser acceptance, physical phone test, or mobile latency is claimed. Fugle key and persistent publisher credential handoff remain outstanding. Main, formal collector, formal Pages, schedules, and existing relay secrets were not modified.

Evidence is saved on a separate non-production evidence branch to avoid another deployment of the already accepted Worker.
