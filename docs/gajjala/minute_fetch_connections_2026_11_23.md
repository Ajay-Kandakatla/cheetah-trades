# 🔌 The minute fetch's connections — 2026-11-23 (spec ggconn §3.3, WP-4)

Ajay 2026-11-23 ~12:00 ET: "Can you clean up some connection I am seeing delays price update for AKAN on the watch
chart.." and "I would like us to focus on connections of Gajjala more for the rest of the tabs."

**This is NOT the delay he saw.** The live feed was blind 28.8 % of today's window by 12:16 ET (the Massive socket is
kicked about every 110 s by a second login — HIS CALL #10–#12). This package changes the REST minute fetch only.

## What changed (`backend/daytrading/data.py`)

| item | before | after |
|---|---|---|
| the GET | bare `requests.get` — a new TCP + TLS handshake per call | `_http_get` → `sepa.prices._http().get`, the ONE recycled per-thread keep-alive session (`backend/http_hygiene.py` tool 3) |
| non-200 log line | `r.text[:200]` logged raw | passed through `sepa.prices._scrub_key`, like the exception line |
| breaker | one module breaker `_CB` for every caller | `_CB` unchanged; `new_breaker()` + an optional `cb=` on `_cb_is_open` / `_cb_record` / `_fetch_massive_minute` / `load_intraday` — a caller's OWN breaker, same trip rule (`_CB_TRIP_AFTER`) and cooldown (`_CB_COOLDOWN_SEC`). `cb` None = today, byte for byte: `load_intraday` then calls the fetch with exactly three positional args. `load_intraday_range` takes no `cb`. The 👀 Watch loader consumes it (WP-3) |
| prior-day cache | a new `MongoClient` + `create_index` per read / write, never closed | ONE client per process (keyed by the pid), cached only after `create_index` succeeded; a failure closes the client, caches nothing, and the next call tries again; `_reset_mongo()` for tests |

URL, params, timeout (`_FETCH_TIMEOUT_SEC` 6), the 429 loop, paging and status handling are unchanged. Every other
caller of the fetch (🚩 pass, 1-min, Luk, the lane's `_bars5`, ledger / tape / divergence / audited_exits, bar_close)
gets the pooled session too and keeps the module breaker.

### The test-session guard (`backend/tests/conftest.py`, critique C4)
`daytrading.data._http_get` is ASSIGNED a refuser for the whole test session (the `RS._http` / `BR._ftp` pattern),
restored on teardown. It raises `MinuteFetchRefused`, a `BaseException` ON PURPOSE: the fetch wraps its GET in
`except Exception`, so an `Exception` would be logged as a provider failure, return None and count on the breaker. A
test that needs the fetch does `monkeypatch.setattr(D, "_http_get", fake)`; `_refuse_minute.__wrapped__` is the real
seam. Never "fix" a refused test by widening a fence — give it its stub. The planner's detection run on this base: 0
existing tests reach the GET un-stubbed.

## Measured — BEFORE (spec §1.5, api container, read-only)

Planner probe 2026-11-23 12:3x ET, the 20 names on the Watch:

| shape | bare `requests.get` | `prices._http()` |
|---|---|---|
| 10 names in sequence, per call (median, two runs) | 843 / 825 ms | 299 / 302 ms |
| 10 names in sequence, total | 8.46 / 8.31 s | 3.50 / 3.10 s |
| 20 names, 8 threads (the `frames_for` shape), wall | 2.47 / 2.49 s | 1.41 / 1.41 s |

0 failures in 80 calls. Watch state doc at 12:31:30 ET: `n_names 20, n_read 20, wall_s 3.933` (ONE sample).
`_get_mongo_coll` ×10 = 22 ms (2.2 ms each) — the Mongo item is a leak fix, not a speed fix.

Planner idle-gap probe 2026-11-23 13:04–13:08 ET, one thread, four public large caps, a warm GET → idle → the timed GET:

| idle gap | n | failed | new connections opened | median ms (each) |
|---|---|---|---|---|
| 5 s | 4 | 0 | 0 | 331 (324, 322, 346, 338) |
| 10 s | 4 | 0 | 0 | 338 (339, 325, 341, 338) |
| 15 s | 4 | 0 | 0 | 338 (327, 350, 342, 333) |
| 19 s | 4 | 0 | 0 | 337 (326, 336, 342, 338) |

Same run: bare 904 / 950 / 931 / 900 ms, pooled back-to-back 323 / 324 / 340 / 341 ms. 16 calls in one hour — thin.

## Measured — AFTER (owed: run once deployed)

The container runs origin/main, so the AFTER run is only meaningful after the deploy. Read-only (no Mongo write, no
websocket; never prints a URL, params or the key — errors by type name only):

```bash
docker exec -i -w /app cheetah-market-app-api-1 python scripts/minute_fetch_cost_probe.py
docker exec -i -w /app cheetah-market-app-api-1 python scripts/minute_fetch_cost_probe.py --skip-idle --wall-readings 10
```

The first prints ONE dict: per shape (sequential, 8 threads) bare / pooled / the real `_fetch_massive_minute`,
medians of 2 runs, failure counts and error type names; then the idle-gap block (gaps 5 / 10 / 15 /
`prices.IDLE_RECYCLE_SEC − 1` s, 4 rounds each: `n`, `fail`, `errs`, `median_ms`, `new_conn`). The second adds ten
`wall_s` readings of the Watch `latest` state doc one cadence (`GG1M_CADENCE_SEC`) apart. Report the wall, the failure
counts (back-to-back AND per idle gap) and the hour beside every number.

| shape | bare | pooled | real fetch |
|---|---|---|---|
| sequential, per call median | _owed_ | _owed_ | _owed_ |
| 8 threads, wall | _owed_ | _owed_ | _owed_ |
| idle gap 5 / 10 / 15 / 19 s: fail, new_conn | — | _owed_ | — |
| Watch `wall_s`, ten readings | — | — | _owed_ |

## What it does and does not buy

- Sessions idle `IDLE_RECYCLE_SEC` (20 s) are closed by us (the Docker forwarder rule in `http_hygiene.py`), and
  `prices._http()` is thread-local while `frames_for` builds new worker threads every call. So reuse is WITHIN one
  iteration's worker threads (20 names → 8 handshakes instead of 20), NOT across minutes. Do not "fix" that with a
  shared Session — the house rule is thread-local.
- A reused connection can be closed by the provider between calls (a race bare requests never had). urllib3 drops a
  connection the server already closed before reusing it, so only the in-flight race is left; measured 0 of 80
  back-to-back and 0 of 16 after 5–19 s idle. A hit = one `failed` name for that pass. A failed connection is closed,
  never reused (`prices.py` `_Pooled.get`).
- Effect on the Watch: UNMEASURED until the AFTER run. Nothing here touches the live socket.

## Tests

`backend/tests/test_daytrading_connections_2026_11_23.py` (seam, guard NEGATIVEs, key never logged with and without
`RedactFilter`, breaker isolation both ways, `load_intraday(cb=)`, one Mongo client + its failure paths, the probe
script); `backend/tests/test_log_redaction.py` (the minute fetch scrubs its own exception and its non-200 body). Stub
seam migrated (assertions untouched): `test_daytrading_data_et_today.py` (three tests),
`test_gajjala_wp1_fixes_2026_10_13.py` (one test). Pass UNCHANGED: `test_daytrading_circuit_breaker.py`,
`test_conn_recycle.py`, `test_spy_levels_study_2026_11_05.py`.
