# Stage 4 Cloudflare ETag regression

Scope: `stage4/20261015-live-shadow`, Worker `tw-tail-stage4-20261015-test` only.

The user's Cloudflare build c17292ed deployed the Worker and installed its ephemeral synthetic writer credentials, then failed with `etag-current-304_HTTP_200`.

Read-only requests to the deployed synthetic data reproduced the cause:

- Identity encoding returned a strong ETag; that tag revalidated with HTTP 304.
- Gzip encoding returned the same opaque tag prefixed with `W/`; that weak tag returned HTTP 200 before this fix.
- Sending the corresponding strong tag still returned HTTP 304.

The Worker incorrectly used exact string equality for If-None-Match. It now uses weak comparison, accepts a matching list member or wildcard, and leaves authorization, HMAC, data version checks, no-store, and the closed live-verification gate unchanged.

References:
- https://developers.cloudflare.com/cache/reference/etag-headers/
- https://www.rfc-editor.org/rfc/rfc9110#section-13.1.2

Verification:
- Added a regression that simulates Cloudflare's weak ETag transformation while using actual local workerd and SQLite. Before the fix it reproduced `etag-current-304_HTTP_200`.
- After the fix, both the ordinary and transformed transport acceptance flows pass, including detecting newer data and candidate withdrawal.
- Cloud acceptance now explicitly checks weak tags, tag lists, and wildcard revalidation.
- `npm test`: 110 passed, 0 failed.
- `git diff --check`: passed.

Cloud build acceptance remains pending at the time of this commit. No real market verification or physical mobile latency is claimed. Formal collector, main, Pages, schedules, and existing relay credentials were not modified.
