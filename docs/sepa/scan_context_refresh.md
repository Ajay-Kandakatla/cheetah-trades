# Market context in the scans — VIX frames, IV read, sector rotation

**Ask (Ajay 2026-09-06):** "Can you make VIX, IV and Hot sectors part of the
scans please? For full scans" — after learning that the IV badge's VIX level
came from whatever the 20-hour price cache held and that the Hot sectors strip
was rebuilt on demand by the first page visit (89 s cold, measured that day;
the IV read 16 s cold).

**Code:** `backend/sepa/context_refresh.py` (the three parts + persistence +
`after_scan`), hooks at the end of `sepa.cli scan` and `sepa.cli fast-scan`,
manual run `python -m sepa.cli scan-context` (or `python -m
sepa.context_refresh`), persisted-first reads in `rotation/api.py`
(`_persisted_hit`, `warm_cache`) and `sepa/iv_read.get`, audit check
`observability.health_audit.check_scan_context`.

## What a scan now does at its end

| part | what | why |
|---|---|---|
| `vix` | `prices.load_prices(sym, period="2y", force=True)` for ^VIX, ^VIX9D, ^VIX3M, ^VVIX | the IV badge and the gauge's volatility pillar read the session's close, not a frame the cache kept |
| `iv` | `iv_read.get(force=True)` → Mongo `scan_context` `_id: iv` | a cold API process answers the last scan's read at once |
| `rotation` | `tracker.build(DEFAULT_START)` → `_id: rotation` + `rotation.api.warm_cache` | `/rotation` and `/rotation/hot` open on the last scan's build |

Each part is fenced: ok / error / seconds go into `_id: summary`; a failure
never fails the scan. Runs Mon–Fri after the 16:30 ET fast-scan and after any
full `scan`.

## How the API uses it

- `/rotation/hot` and `/rotation` (default key only): in-process cache (30 min)
  → the persisted build if younger than `PERSIST_FRESH_SEC` (20 h) → build on
  request. The payload carries `source` (`scan` | `live`) and `built_at_iso`;
  the Hot sectors strip prints "scan HH:MM ET" for a scan build. `?refresh=true`
  still rebuilds on request.
- `/market/iv`: a cold process (nothing computed yet, e.g. right after a
  deploy) returns the persisted read immediately (`source: "scan"`,
  `built_at_iso`, `age_sec` from its build) and starts the live compute in a
  background thread so the badge's next 3-minute poll is live. A warm process
  behaves as before (3-minute cache, live compute).

## Health audit

`check_scan_context` (WARN only, never CRITICAL — a stale badge is not a
dead pipeline): never built → WARN; any part failed in the last scan → WARN
naming it; older than `STALE_AFTER_H` (30 h) on a weekday → WARN. Shows in the
nav's Scans chip like every other check.

## Tests

`backend/tests/test_context_refresh.py`: forced 2y refetch per family symbol
(a failure is a None), IV + rotation persisted and the API cache warmed, the
fence (a raising part is recorded, the summary says ok=false), `after_scan`
never raises, both scans call the hook (source guard), `/rotation/hot` serves
the persisted build before a cold build (and not a stale one, and not on
`?refresh=true`), `iv_read.get` answers cold from the scan then refreshes
live (and computes synchronously with nothing persisted), the audit check's
four states. Frontend: `scanStamp` in `HotSectors.test.tsx`.

Not advice — plumbing for reads that already exist.
