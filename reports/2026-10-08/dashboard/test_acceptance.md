# Local test acceptance before deployment

2026-10-08: all Python tests PASS (144); all Node tests PASS (25), including
16 actual homepage model/DOM tests and 9 preserved diagnostic tests. Original
capture ZIP and official ZIP hashes match the source receipt in acceptance.json.
Full-market saved replay took 2.231 seconds; no market HTTP requests occurred.

Covered gates include pending/no data, complete zero/multiple candidates, partial
UNKNOWN coverage, holiday / timezone / previous-day rejection, real normal and
delayed auction times, positive/negative returns, exact seven-stock regression,
thousand-share units and fractional conversion, inconsistent/missing/simulated
volume, unsupported unit contract, fresh pair/as-of checks, date-isolated CAS
idempotence, bounded transient failures, immutable prices during postmarket
annotation, failure retention and true nonzero results. Official validation
reports persist if its separate website update fails. Existing deadline/cache /
date/capture failure cases remain passing. Push steps explicitly skip real MIS.

GitHub CI and live Pages desktop/mobile acceptance are recorded separately in
deployment_acceptance.json after deployment; this file does not claim they have
already run. Mobile DOM/CSS tests confirm card layout, viewport meta, no homepage
manual controls, red-up/green-down, unit labels and stable updates without node
replacement when the list is unchanged.

Actual browser acceptance: PASS, 21 checks across Chromium desktop, Chromium
390px mobile and WebKit iPhone profile, including the deployed anonymous public
Pages URL. No horizontal overflow or homepage controls. Branch run 37764761846,
main CI 37764953838 and Pages deployment 37764953367 all succeeded. Browser tests
are push-only and do not install/run during scheduled live captures.
