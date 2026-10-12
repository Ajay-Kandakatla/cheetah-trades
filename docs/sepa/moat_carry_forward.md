# 🏰 Moat carry-forward + moat-only backfill (2026-10-11)

## What broke

The Sunday research refresh (`python -m sepa.cli research-refresh --mode broad`,
3,854 names, 6 threads) read yfinance `.info` for the Buffett moat on every
name. Yahoo answered with **429 Too Many Requests**: 1,283 log lines by name
~1,750. `sepa.moat.compute_moat` returned `None` on ANY exception — the same
value as "Yahoo has no fundamentals for this company" — and
`research._put_research` `$set` the whole blob, so a throttled night wrote
`moat: null` over last week's good moat.

Measured 2026-10-11 23:03 ET (`backend/scripts/moat_coverage.py`, census of
every `sepa_research_cache` doc — no sample, no CI):

| group | docs | moat present | moat null |
|---|---:|---:|---:|
| fresh (served, `cached_at` ≤ 16 d) | 3,906 | 482 | **3,424 (87.7%)** |
| refreshed tonight | 3,726 | 466 | 3,260 (87.5%) |
| all | 4,012 | 574 | 3,438 (85.7%) |

`fundamentals` was never affected (Massive v1, not yfinance).

## The fix

**1. Could-not-read ≠ no-moat** (`sepa/moat.py`).
`compute_moat` raises `MoatFetchError` when the yfinance call raises (429,
transport, parse). `rate_limited=True` for yfinance's `YFRateLimitError`
(matched by class name or the "Too Many Requests" / "Rate limited" message).
Only an EMPTY `.info` (Yahoo answered, nothing there) returns `None`.
A 429 opens a process-wide breaker for `RATE_LIMIT_COOLDOWN_SEC` (600 s, env
`MOAT_RATE_LIMIT_COOLDOWN_SEC`): `compute_moat(breaker=True)` raises at once
without calling Yahoo, because hammering a throttled endpoint extends the
throttle. Every moat dict now carries `as_of` (epoch seconds of the read).

`moat.lost_inputs(new, prev)`: yfinance swallows a non-429 HTTP error on the
fundamentals request and still returns the price quote, so `.info` is
non-empty with no ROE / margins / FCF — a read failure that looks like data.
A 0-of-6-inputs read never replaces a stored moat that had inputs; it is
treated as `fetch_failed`.

**2. Carry-forward** (`sepa/research.py::compute_research`).

| moat read | stored `moat` | `moat_as_of` | `moat_status` |
|---|---|---|---|
| scored | the new dict | read time | `ok` |
| `.info` empty | `null` | read time | `no_data` |
| raised / 0-of-6 over a moat with inputs | **kept** (left out of the `$set`) | kept; a legacy moat gets its old `cached_at` | `fetch_failed` (+ `moat_failed_at`) |
| not attempted (`with_moat=False`) | **kept** | kept / legacy stamp | unchanged |

The carried moat is left OUT of the `$set` (never rewritten from a read), so
a concurrent backfill write between the read and the write wins.
`research.with_moat_as_of(blob)` attaches `as_of` to the moat a scan row
serves (from `moat_as_of`, else a legacy blob's `cached_at`).
`research.moat_live_or_cached(symbol)` — the scanner top-20 enrichment and
the moat-peers target — falls back to the cached moat when Yahoo cannot be
read.

**3. Moat-only backfill** (`sepa/moat_backfill.py`, `python -m sepa.cli moat-backfill`).
One read at a time, ≥ `--interval` (1.0 s) apart. A 429 sleeps 60 s,
doubling to 900 s, and retries the same name; after 6 retries the run stops
(exit 2) and is resumable. A non-429 failure marks that name `fetch_failed`
for the pass and moves on; 20 in a row stops the run (`unreachable`). Writes
only `moat`, `moat_as_of`, `moat_status`, `moat_failed_at` — never
`cached_at`, never an upsert.

Resumable cursor = the pass start (`sepa_moat_backfill_state`,
`_id: moat_backfill:<mode>`). A name read or tried in the pass carries a
stamp ≥ the pass start, so a resumed run skips it. `--restart` begins a new
pass.

Modes: `null` (default) = names with no moat. `refresh` = also every moat
read before the pass began. Order: no-moat first, then oldest `moat_as_of`,
then symbol — so a pass that is cut short fills the worst gaps first, and the
same tail of the universe is not left out every week.

**4. Concurrency** (`sepa/cli.py research-refresh`).
The 6-thread refresh no longer reads Yahoo for the moat
(`refresh_universe(with_moat=False)` carries every moat). Afterwards ONE
sequential `refresh` pass re-reads the moats of the names it refreshed
(budget `--moat-max-minutes`, 240). The Mon–Sat 20:30 ET catch-up line
(`--only-if-stale`) still skips a healthy research refresh, but resumes an
unfinished moat pass (`resume_only`). An ad hoc `--symbols` run stays
threaded with the moat read (the breaker and the carry-forward protect it).
`--skip-moat-pass` / `--no-canslim` skip the pass. The API's
`POST /sepa/research/refresh` is unchanged (threaded, now carry-forward +
breaker).

**5. The age is visible.** The 🏰 chip tooltip on the /sepa cards ends with
"Moat data as of Oct 4, 2026 (7d old)" (`frontend/src/lib/moatAge.ts`).

## Re-run the number

```bash
docker run --rm --network cheetah-market-app_default -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -v "$PWD/backend:/app:ro" -w /app cheetah-api:latest python scripts/moat_coverage.py --since-hours 24
```

## Run the backfill (throwaway container, never exec into api/cron)

```bash
docker run -d --name moat-backfill --network cheetah-market-app_default -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York -v cheetah-market-app_cheetah-scans:/root/.cheetah -w /app cheetah-api:latest python -m sepa.cli moat-backfill
```

It needs no API key (yfinance). Re-running the same command (after `docker rm moat-backfill`) resumes the pass.

## After

_Filled in after the 2026-10-11 backfill run — see below._

## Tests

`backend/tests/test_moat_carry_forward.py` (hermetic). Includes the pinned
`test_REGRESSION_2026_10_11_a_429_never_blanks_a_cached_moat` (real
`YFRateLimitError`, real `compute_moat`, real `compute_research` +
`refresh_universe`). Mutation-checked: reverting the carry-forward, or
returning `None` on a fetch error, fails it.
`frontend/src/lib/moatAge.test.ts`,
`frontend/src/components/SepaCandidateCard.moatAge.test.tsx`.
