# Stage 4 isolated Cloudflare deployment

Only the NEW Worker `tw-tail-stage4-20261015-test`. Never use the existing relay or Pages configuration.

## Confirmed connection

- Repository: `gxaawill2-ui/tw-close-auction-mis-probe`
- Branch: `stage4/20261015-live-shadow` (labelled Production branch for this TEST Worker)
- Repository root: `/`
- Build command: empty
- Deploy command: `npx wrangler deploy --config isolated_publication/stage4.wrangler.jsonc`
- Preview builds: user instructed to disable. Confirm actual saved state before claiming disabled.
- Fallback non-selected branch command: `node -e "process.exit(0)"` (no deployment).

`stage4.wrangler.jsonc` provisions its own SQLite-backed SelectionStore and SELECTION binding. Do not manually bind the existing `tw-index-events-relay_DispatchGate`. Exporting a class in the dashboard does not initialize its durable namespace.

## Access

The configuration keeps ALLOW_LIVE_VERIFIED=false. No real market signal may be promoted by deployment. First validate synthetic transport. No writer secrets are in this repository. PUBLISH_TOKEN and DECISION_KEY must be NEW isolated secrets provided through a safe channel. Without them /publish fails closed with 503.

GET /health does not require secrets or storage and should show live_validation_released=false. GET /data?date=YYYY-MM-DD requires the namespace and returns 404 NO_PUBLISHED_DATA before the first authorized publication. The root path / returns JSON NOT_FOUND; it is not the selection UI.

## Evidence

A successful build is only deployment evidence. Save the actual build status, namespace initialization and deployed version separately. A successful health check is not write/read success. Record server write receipt and ordinary external browser observation separately. A screenshot of Hello World is not a published selection or measured mobile latency.

## GitHub safety

This bootstrap commit uses [skip actions], the GitHub-documented push/PR workflow skip marker, to avoid starting the shared formal Actions concurrency group. This is not a modification to the formal workflow. Check Cloudflare's actual build result; do not assume its commit filtering behavior.

References: https://developers.cloudflare.com/workers/ci-cd/builds/ ; https://developers.cloudflare.com/workers/ci-cd/builds/configuration/ ; https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs

## Resumed acceptance deployment

The optional assets setting serves stage4-site/index.html at /. It displays only SYNTHETIC data for 2099-01-01. To install ephemeral acceptance-only keys and execute real cloud tests, change this TEST Worker's deploy command to `node isolated_publication/stage4-cloud-deploy.cjs`, keeping root /, exact stage4 branch and preview builds disabled. Pushing this script does not change the dashboard command. Official configuration docs confirm custom deploy commands and WORKERS_CI=1, WORKERS_CI_BRANCH, WORKERS_CI_COMMIT_SHA.

The script guards the target before mutation, deploys only this Worker, generates test keys inside the build, installs via stdin without logging values, and exercises signed writes, anonymous reads, conflicts, ETag, rejection of tampered writes and fake verification, row updates and withdrawal. The final synthetic payload includes a non-secret transport_acceptance summary; build logs additionally confirm final readback. Keys are acceptance-only, not a real publisher handoff.

Current local browser scope: desktop and iPhone Chromium PASS; WebKit BLOCKED by missing OS libraries. Real-device latency is unknown. See ../reports/2026-10-15-stage4/RESUMED_REPORT.md.
