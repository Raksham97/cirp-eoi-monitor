# CIRP EOI Monitor reliability hardening v1

This patch changes source monitoring from fixed-depth crawling to fail-closed, date-horizon coverage.

Key controls:
- crawls the unpaginated IBBI landing page first (`page 0`) so the newest page cannot be skipped by paginator semantics;
- validates expected IBBI table headers and official `Total Records` before accepting a run;
- retries transient HTTP failures;
- crawls until two consecutive pages are entirely older than the required horizon instead of assuming 8 pages is enough;
- twice-daily normal checks plus a deeper 120-day Sunday reconciliation;
- row SAVEPOINTs prevent one malformed record from rolling back good rows/counters;
- partial/anomalous runs fail the workflow and therefore do not replace the last known-good dashboard;
- an independent canary and a post-ingest freshness audit must both pass before publish;
- dashboard turns visibly stale after 30 hours without a fully verified refresh.

This materially improves reliability but does not claim that an external government website can never change or fail.

## End-to-end publication verification

The neutral Cloudflare Pages workflow now verifies that the production `data.json` has the exact `generated_at` value committed by the audited crawl and that the Excel file is downloadable. A successful crawler followed by a failed/stale neutral-site publication therefore produces a failed Cloudflare workflow rather than a silent stale site.
