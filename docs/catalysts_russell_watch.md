# Russell inclusion watch (2026-09-01)

Ajay, off EMAT (+21% on its preliminary Russell 3000/2000 inclusion,
effective 2026-09-21): "check if there are more stock like about to get
added to russel 2000 or 1000 ... so we can track those entries."

## Endpoint + page

`GET /catalysts/russell-watch` → adds_r2000 / promotions_r1000, rendered
as the 🧺 Russell Watch tab on the Catalysts page. Stale-while-revalidate:
an expired cache is served immediately with `stale: true` while a daemon
thread rebuilds (a cold build takes minutes — bulk snapshots + yfinance
share fetches — and the proxy kills ~100s requests).

## Method (backend/catalysts/russell_watch.py — approximation, uncited)

cap = shares_outstanding (weekly shares_cache, budgeted yfinance top-up,
catalyst-scan names get the budget first) × live bulk-snapshot price,
judged against CURRENT member cap percentiles from the iShares baselines:

* **add_r2000**: not in R3000 baseline AND p25(R2000 caps) ≤ cap <
  p10(R1000 caps). Bounded ABOVE on purpose: the first live run's "top
  adds" were ASML/BABA/RY — oversized outsiders are foreign/ineligible,
  not missed adds. A hand-kept NON_US_BLOCKLIST removes the known ones;
  the method note owns the rest of the leakage.
* **promote_r1000**: in R2000 baseline AND cap ≥ p10(R1000 caps). Flagged
  as usually NET tracker selling (more money follows R2000).

Known limits, printed in the payload: membership baseline = manual iShares
XLS snapshots (2026-06-03 — refresh after each recon; names added since
still show as candidates), plain cap vs FTSE's float-adjusted banding,
US-company requirement unverifiable. FTSE runs SEMI-ANNUAL reconstitution
from 2026; the second 2026 recon is effective 2026-09-21 and preliminary
lists are already published — this board is the cap-screen guess at them.

Verified: EMAT classifies as add_r2000 at $2.46B (the known answer).

Tests: backend/tests/test_russell_watch.py (11, pure classify/_pctl incl.
the ASML rejection and the EMAT window) ·
frontend/src/components/RussellWatch.test.tsx (3).
