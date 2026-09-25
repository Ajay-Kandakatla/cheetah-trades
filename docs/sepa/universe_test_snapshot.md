# The backend suite runs on a committed universe snapshot, never live

*2026-09-24. Branch `fix/hermetic-universe-tests-2026-09-24`.*

## What broke

Five tests went red on a clean `origin/main` on the afternoon of 2026-09-24,
with no code change. They had passed that morning.

| When (CDT) | What |
|---|---|
| 2026-08-25 15:30:02 | every file in the Mac's `~/.cheetah/universe/` written |
| 2026-09-24 15:30:02 | `UNIV_CACHE_TTL_SEC` (30 days) lapses on all of them at once |
| after that | the suite resolves the index lists **live** |

What the live path did on the host:

| List | Ladder | Result |
|---|---|---|
| russell3000 | local iShares xls → needs **lxml**, absent from the host venv → iShares CSV (Cloudflare page) → curated ∪ sp500 ∪ sp400 | **1,020 names**, the wrong universe (band 1800–3200) |
| sp400, sp600 | Wikipedia via `pandas.read_html` → needs lxml | stale cache (still correct) |
| sp500 | Wikipedia fails → datahub CSV **succeeds over the network** | rewrote the host's cache file mid-run |

Three causes, all needed:

1. **Tests read a real, expiring cache** — `~/.cheetah/universe`, or inside the
   api container (where `make contracts` runs) the production `cheetah-scans`
   volume.
2. **Tests reached the live network** — measured on a full run: 147 Wikipedia
   and 49 iShares requests, all from `sepa.universe`. A second pass that also
   watched curl_cffi (yfinance and StockTwits use libcurl, invisible to a
   socket log) found 122 Yahoo Finance requests from 10 more tests.
3. **Provenance leaked between tests.** `sepa.universe._LAST_SOURCE` is module
   global. `test_cloud_infra_theme.py` resolved `russell3000` to `curated`;
   three `test_russell2000_derived_2026_09_18.py` tests then read that as
   their parent's provenance and refused to derive. That file passes 28/28 on
   its own.

The missing lxml is a host-venv gap (`requirements.txt` pins `lxml==5.3.0`).
It decided which fallback the tests landed on, not whether they broke.

## Production: not affected

Checked read-only on 2026-09-24:

- api and cron containers have **lxml 5.3.0** (html5lib absent, bs4 4.14.3).
- Their cache is the `cheetah-scans` docker volume, not the Mac's home
  directory. It was refreshed **2026-09-20 06:30 ET** by the Sunday
  `sepa.universe_changes` cron, so it next lapses around 2026-10-20.
- `load_universe("full")` = **2,734** names; russell3000 = 2,559 from cache.
- With the russell1000/3000 caches forced expired (writes disabled) the api
  container rebuilds them from the committed xls: **2,559 / 1,001**, source
  `ishares-local`, and `full` is the identical set.
- No `OUTSIDE the sane range`, `local-xls parse failed` or curated-fallback
  lines in the cron container's log (up 9 h) or the api container's log (it
  had been restarted by a deploy minutes earlier, so that window is short;
  the probe above is the stronger evidence).

Two things to watch, both unchanged by this branch:

- The iShares exports in `backend/sepa/data/` are dated 2026-06-03, 113 days
  old on 2026-09-24. The loader starts warning at 120 days (around
  2026-10-01). Refreshing them is already a HIS-CALL item in
  `docs/sepa/russell2000_derived.md`.
- `massive_universe.txt` and `nasdaq_listed.txt` in the prod volume are past
  their TTL (2026-08-21). Nothing in `full` reads them. The `all_us` mode and
  the `nasdaq_listed` component would re-fetch from Massive on the next call.

## What the suite does now (`backend/tests/conftest.py`)

Everything is installed when conftest is **imported**, before collection:
`test_cloud_infra_theme.py` calls `load_universe("full")` at module level, and
a fixture would run too late.

1. **Snapshot, not cache.** `sepa.universe.UNIV_CACHE_DIR` points at a
   per-session temp copy of `backend/tests/fixtures/universe/*.txt`. Every
   file is stamped with the current time on copy, so the TTL runs from session
   start and cannot lapse during a run. A test that writes or expires a list
   only changes the copy, which is re-seeded after that test.
2. **No live network.** Socket connects and DNS lookups to any non-loopback
   host are refused, and so is any curl_cffi request. The error is
   `LiveNetworkBlocked`, an `OSError`, so each caller's own offline path runs.
   Those paths hide the error (that is how "1,020 names" hid the cause), so:
   - a failing test gets a **live network refused** section naming the hosts;
   - the run ends with a list of every test that tried.
3. **Provenance cleared around every test** (`_LAST_SOURCE`, `LAST_COUNTS`).
4. The Mongo guard (2026-08-17) moved from a session fixture to import time,
   for the same collection-time reason.

A test that drives code into the network guard on purpose requests the
`blocked_network_attempts` fixture. It returns the refused targets and
consumes them.

Side effect: the full backend suite went from **~6m20s to ~1m11s**, because
it no longer waits on network timeouts.

### Still reaching for Yahoo (refused, deterministic, listed at the end of every run)

9 tests in `test_alert_gates.py`, `test_amd_chips_2026_09_21.py`,
`test_market_gauge.py` and `test_promo_live.py` call a price read for junk or
placeholder symbols (`"NOPE"`, `"X"`). Refused, they get the no-data path they
were written for. Before this branch they depended on live Yahoo data (`X` is
a real ticker). Stubbing the price read in each would clear the list.

## The snapshot

`backend/tests/fixtures/universe/` holds sp500, sp400, sp600, nasdaq100,
russell1000, russell3000 and microcap. `MANIFEST.json` records each list's
count and sha256, plus the sha256 of each iShares export the Russell lists
were parsed from.

Taken 2026-09-24:

| List | Names | Source |
|---|---:|---|
| sp500 | 503 | api container cache (2026-09-20) |
| sp400 | 400 | api container cache (2026-09-20) |
| sp600 | 603 | api container cache (2026-09-20) |
| nasdaq100 | 101 | api container cache (2026-09-20) |
| russell1000 | 1,001 | parse of `iShares-Russell-1000-ETF_fund.xls` |
| russell3000 | 2,559 | parse of `iShares-Russell-3000-ETF_fund.xls` |
| microcap | 1,278 | parse of `iShares-Micro-Cap-ETF_fund.xls` |

These are the same sets the Mac's cache held when the tests last passed. The
Russell lists match a fresh parse of the committed xls in the same order.

`tests/test_hermetic_universe_2026_09_24.py` fails when:

- a list was edited by hand (sha256 ≠ manifest);
- a list falls outside its `_EXPECTED_COUNTS` band;
- an iShares export in `sepa/data/` changed or was added (for example the IWM
  file) and the snapshot was not regenerated.

### Regenerate (after dropping in a fresh iShares export, or to follow the index)

From `backend/`, with the api container up:

```bash
.venv/bin/python scripts/refresh_universe_test_snapshot.py
```

The script parses this checkout's exports inside the api container, because
the host has no lxml. It copies each one to the container's `/tmp`, never
`/app`, and removes it afterwards. It reads the S&P and Nasdaq-100 lists from
the container's cache, refuses to write any list outside its size band, and
rewrites `MANIFEST.json`. Review the diff and commit the lists and the
manifest together.

## Guard tests (all verified to go red when their guard is removed)

| Guard removed | Tests that fail |
|---|---|
| cache redirect | every test in `test_hermetic_universe_2026_09_24.py` refuses to run (it would age or rewrite the real cache), plus `test_cloud_infra_theme` and `test_sectors_security_biotech` |
| provenance clear (both sides) | `test_provenance_does_not_survive_into_the_next_test_part_2` |
| socket guard | live-network test + both real-ladder fallback tests |
| curl_cffi guard | `test_NEGATIVE_live_network_is_refused_and_recorded` |
| import-time Mongo guard | `test_NEGATIVE_mongo_is_refused_at_collection_too` |
| fresh stamp on seed | `test_an_old_committed_snapshot_is_still_served_fresh` |

The three russell2000 tests stay green with the redirect removed: their
`parents` fixture now records its stubs' provenance itself, as the real
fetchers do, so they no longer depend on what an earlier test left behind.
