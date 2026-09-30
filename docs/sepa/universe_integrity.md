# Universe integrity — making a wrong ticker list impossible to ship quietly

**Code:** `backend/sepa/universe.py` (`_COMPONENT_FETCHERS`, `_UNIVERSE_ALIASES`,
`_EXPECTED_COUNTS`, `_record_count`, `_count_guarded`, `universe_counts`) ·
`backend/observability/health_audit.py::check_universe_counts` ·
**Tests:** `backend/tests/test_universe_resolution.py`

> Ajay 2026-08-16: *"May be add a count checks for returned values for all the
> tickers API like Russel 3000 and S&P 500 as well."*

## The two bugs this fixes

Both are the same shape: **a universe silently became a different universe while
every label kept saying the right thing.** Neither raised. Neither logged.

### 1. `load_universe` fell through to the curated 158

`load_universe` resolved single keys with an if/elif chain covering only
`curated / sp500 / russell1000 / russell3000 / broad / all_us / expanded`.
`_fetch_component` had a *separate*, longer map. Every key in one but not the
other fell off the end into `return _with_benchmarks(UNIVERSE)` — the curated
158 names.

Measured before the fix:

| key | resolved to |
|---|---|
| `sp1500_plus` | **158** |
| `sp1500` | **158** |
| `sp400` | **158** |
| `sp600` | **158** |
| `nasdaq100` | **158** |
| `themes` | **158** |
| `totally_bogus_key_xyz` | **158** |

A real key and a garbage key were **indistinguishable**. `/supply-demand`
defaults to `universe="sp1500"`, so that page ran a 158-name scan while its own
dropdown said "S&P 1500".

After: `sp1500` → 1,509 · `sp1500_plus` → 1,620 · `sp400` → 403 · `sp600` → 606 ·
`nasdaq100` → 105 · `themes` → 85. A genuinely unknown key still falls back to
curated — but now logs at **ERROR** saying so.

**Root cause was the duplication itself**, so the fix removes it: the explicit
per-list branches are gone and every single key resolves through
`_COMPONENT_FETCHERS`. One map, one lookup, nothing to drift.

### 2. `sp1500_plus` promised themes and delivered none

`demand_reentry.UNIVERSES["sp1500_plus"]` was labelled
*"S&P 1500 + themes (quantum · nuclear · robotics · AI semis)"* and its lambda
was `fetch_sp1500()` — the identical list to the plain `sp1500` entry.

Theme coverage in that universe: **48 of 82**. The 34 missing were exactly the
names the S&P tiers structurally exclude, which is the entire reason the rosters
exist: ASTS, IONQ, ARM, CRDO, LUNR, AAOI, ARQQ, BKSY, GSAT, APLD, CRWV …

After: **82 of 82**, 1,540 names.

## The size guards

`_EXPECTED_COUNTS` gives each list a sane band, anchored on a **measured** count
taken 2026-08-16 and widened for index churn:

| list | measured | band |
|---|---|---|
| sp500 | 503 | 450–530 |
| sp400 | 400 | 350–430 |
| sp600 | 603 | 540–650 |
| nasdaq100 | 102 | 95–115 |
| sp1500 | 1,506 | 1,350–1,700 |
| russell1000 | 1,001 | 900–1,150 |
| russell3000 | 2,559 | 1,800–3,200 |
| microcap | 1,278 | 0–2,500 |
| etf | 373 | 150–600 |
| themes | 82 | 20–300 |
| broad | 3,707 | 1,800–6,000 |

Two bands are deliberate rather than mechanical:

- **russell3000 floors at 1,800**, above the ~1,030-name clean fallback
  (curated ∪ sp500 ∪ sp400). That fallback is a perfectly good universe but it
  is **not** the Russell 3000, and the band exists to say so rather than let it
  pass under the wrong name.
- **microcap has no lower bound.** It is an optional layer sourced from an IWC
  holdings file; absent is legitimate, so only a bad parse (an implausibly large
  list) is worth flagging.

### Where the check runs

`_count_ok` already existed but only guarded the four lists routed through
`_resolve_with_fallbacks`. Russell 1000/3000, sp1500, microcap, ETFs and broad
each had bespoke cache/fallback chains with **up to six exit points** — cache
hit, local file, network, mirror, stale cache, clean fallback — and no check on
any of them.

`_count_guarded` wraps each public fetcher by name at the bottom of the module,
so **every** return path is observed, including the stale-cache and
clean-fallback returns, which is precisely where a list quietly becomes a
different universe.

Two distinct behaviours, on purpose:

- `_count_ok` — **rejects** a source mid-fallback-chain, so a bad parse is
  skipped and the next loader gets a turn.
- `_record_count` — runs at the **boundary**, where rejecting would leave the
  caller with nothing. Logs at ERROR and records into `LAST_COUNTS`.

### Monitoring

`check_universe_counts` in the health audit reports every list against its band.
**WARN, never CRITICAL** — a source going stale means a narrower scan, not a
wrong trade, and the push keep-set is deliberately three kinds.

Live in the api container after the fix: `all 11 ticker lists within their sane
range`.

## Not advice

Universe membership decides who gets **looked at**. Nothing here changes a gate,
a score, or an entry. A wider universe is not a reason to own anything.

## 2026-09-07 — `full` carries the Russell 3000

Ajay: *"Yes please add 3000, I wanna be able to scan more.. becuz there is so much growth
to small cap."* Asked after "Do we scan russell 2000 in our app?" — the answer was no:
`full` = russell1000 ∪ sp1500 ∪ curated ∪ themes, 1,751 names measured that morning,
which held 659 of the ~1,560 Russell 2000-sized names and missed 901.

**Change:** `_UNIVERSE_ALIASES["full"]` = `("russell3000", "sp1500", "curated", "themes")`.
One line, because every consumer already reads the alias: the SEPA scan
(`SEPA_UNIVERSE_MODE=full` in the gitignored `backend/.env`), `zone_store.warm`, the
demand boards (`demand_reentry.UNIVERSES["full"]`), `chart_maps.board` (Gabbar /
undervalue), the weekly quick-bounce study. Labels that said "Russell 1000" now say
"Russell 3000" (demand_reentry, DemandReentryPanel).

**Why the alias, not `SEPA_UNIVERSE_MODE=russell3000`:** the raw mode measured 2,556
names — 900 new, but it DROPS 95 that only curated / themes / sp1500 carry (pre-profit
names, ADRs, S&P 600 names the iShares file lags on). Layering keeps them.

**Expected size:** ~2,650 (R3000 2,556 ∪ the 95). `russell3000` keeps its own count band
(1,800–3,200) in `_EXPECTED_COUNTS`; `full` has none — it is a union of guarded parts.

**Operational notes:** the research cache (`sepa/research.py`, weekly Sunday 20:00 +
nightly `--only-if-stale`) has to warm the ~900 new names or the first fast-scan runs
900 fallback analyses; run `python -m sepa.cli research-refresh --symbols <delta>` once
after the flip. The 16:30 fast-scan grows from ~49 s (1,680 analysed) — measured after
the flip in the session log.

## 2026-09-12 — curating four blind names, and the SECOND gate

Ajay pointed his own watchlist at the app: *"Can you check if these companies
are in our scans?"* **Four of twelve came back blind**, in two different ways.

| Ticker | Company | Was | Now |
|---|---|---|---|
| UMAC | Unusual Machines | in `broad` only — daily fast-scan, **no zone doc** | curated into `full` |
| CLYM | Climb Bio | in `broad` only — same | curated into `full` |
| LWLG | Lightwave Logic | **not in `companies`, no universe, never scanned** | company filed + curated |
| WYFI | WhiteFiber | **same** | company filed + curated |

`full` 2,652 → **2,656**.

Two more from the same check, reported but not changed:

- **`AST` is a dead ticker** on his watchlist — Asterias Biotherapeutics, gone
  years ago. The live company he means is **`ASTS`** (AST SpaceMobile), already
  in `full`.
- **`RUN`** is fully scanned with 11 demand bands, but absent from the 🔥
  Hottest grid — see the separate coverage gap below.

### Nothing here was hand-written

Both missing company records were filed by the REAL fetcher
(`companies.store.get(sym, force=True)`), and every price checked through
`sepa.prices.load_prices` before the ticker was added: 276–504 bars apiece
through 2026-09-11. One result is a surprise worth recording — **LWLG files as
Basic Materials / Specialty Chemicals**, not optical, so it would never have
appeared under the `optical` theme on a GICS-grouped board regardless.

### The second gate — curating is necessary and NOT sufficient

`supply_demand/zone_store.big_cap_universe()` keeps only names with a **KNOWN**
market cap ≥ `MIN_CAP_USD` ($700M). LWLG and WYFI were curated into `full` and
**still had no zone document**, because neither had a `shares_cache` row at all
— an unknown cap is dropped, not assumed.

Warmed through `volume_movers.shares_for()` (the same path the app uses):

```
UMAC  $1,182M      CLYM  $760M      LWLG  $806M      WYFI  $744M
```

All four now clear the floor. **Two of them barely.** CLYM at $760M and WYFI at
$744M sit 6–9% over a floor computed as shares × price — the circularity
already documented in `trading/safety_floor.py`. A normal down week drops either
one back under it and it silently leaves every zone board again.

**WYFI's float is 11.3M of 38.8M shares outstanding — 29%.** At $19.14 that is
roughly $217M of actually tradeable stock inside a $744M "cap". This is exactly
the whale-movable shape the safety floors do **not** catch, because nothing in
the app reads float as a gate.

### Known gap this exposed, not fixed

A newly curated name has **no `shares_cache` row until the weekly warm runs**,
so it sits in `full` and out of every zone board for up to a week — invisible
in a way that looks like coverage. These four were warmed by hand. Curation
should trigger the shares warm; it does not.

### Tests

`backend/tests/test_curated_blind_names.py` — 23 tests pinning the CLASS, not
the four names: every curated-blind ticker (NTSK, AXTI, UMAC, CLYM, LWLG, WYFI)
is in `full`, is an AST literal in `UNIVERSE` so an index refresh cannot drop
it, is not delisted and is not a rename source; `big_cap_universe` drops an
unknown cap and a NaN cap; the floor matches `safety_floor.MIN_CAP_USD`; and a
source guard that `zone_store` still builds from `full` — without which every
`full`-vs-`broad` assertion above would pass vacuously.

All 5 mutations caught, including "unknown cap admitted" and "zone_store
switched to broad".

## 2026-09-21 — the `promo` component, and two bands that were never enforced

Ajay: *"[the promo page] keeps pulling new stocks.. add them to our list as they
come through"*.

**Change:** `_UNIVERSE_ALIASES["full"]` =
`("russell3000", "sp1500", "curated", "themes", "traders", "promo")`. The new
`promo` component resolves to the `promo_universe_adds` rows that the curation
lane (`catalysts/promo_curate.py`) admitted — a real common stock on a listing
exchange, real price history, over `safety_floor.MIN_SHARE_PRICE` ($2 last
close) and `hot_pullback.MIN_DOLLAR_VOL_USD` ($5M median 50-day dollar volume).
Being tagged by a pump account is the **input**, never the test, and an add
means only that the app can SEE the name: every downstream gate applies to it
unchanged. Band `(0, 200)` — zero is the legitimate starting state and the
upper bound (12 adds/run × the 14-day window = 168) is the real guard. Full
rationale and the dry run: `docs/catalysts/promo_curation.md`.

**Bug fixed in the same pass:** `fetch_trader_adds` and `fetch_promo_adds` are
now **count-guarded**. `traders` has carried a `(0, 200)` band since 2026-09-12,
but the fetcher was missing from the `_count_guarded` list at the bottom of
`universe.py` — so `LAST_COUNTS["traders"]` had never once been written and the
band was documentation, not enforcement. `_record_count` records the size and
logs ERROR outside the band; it **never rejects** (that is `_count_ok`'s job,
mid-fallback-chain), so the fail-EMPTY contract and the universe size are
unchanged. This is observability only. `universe_counts()` now reports both.

## 2026-09-29 — the Russell layer was four months old; now it reads the live holdings

**What was wrong.** `full`'s Russell layer came from the iShares exports in
`backend/sepa/data`, "Fund Holdings as of May 28, 2026": before the June 26
reconstitution and the Sep 21 Q3 IPO adds. The local file was tried FIRST and
always parsed, so the network branch never ran. That branch was dead anyway:
iShares redesigned its site and the old `1467271812596.ajax?fileType=csv` URL
now returns 1.45 MB of product-page HTML with a `text/csv` header. It is not a
TLS block; curl_cffi Chrome impersonation gets the same HTML. The page now
links `/us/products/<id>/<slug>/latest-holdings.csv`, which plain `requests`
with our UA can fetch.

**The ladder now** (`sepa/universe._resolve_ishares`, used by
`fetch_russell1000` / `fetch_russell3000` / `fetch_microcap`):

| step | source label | cached? |
|---|---|---|
| 1. live `latest-holdings.csv` (IWB 239707, IWV 239714, IWC 239716) | `ishares-network` | yes, 30 days |
| 2. committed snapshot `sepa/data/iShares-*_holdings.csv` | `ishares-snapshot` + WARNING | **no** |
| 3. curated ∪ S&P 500 ∪ S&P 400 (R1000/R3000), `[]` (microcap) | `curated` / `empty` | no |

- The snapshot is not cached, so a cached fallback can never read back as a
  plain `cache` hit, and the next call retries the live list.
- A truncated live parse (outside `_EXPECTED_COUNTS`) is rejected, and the
  snapshot serves.
- The snapshots were refreshed on 2026-09-29 from "as of Sep 28, 2026". The
  three May `.xls` files are gone. The `.xls` loader stays for the IWM drop-in.

**One cleanup for both formats** (`_clean_ishares_records`):
1. `Asset Class == Equity`. The CSV branch used to have no such filter.
2. Residual rows are dropped by the fund's own marks: Exchange starting with
   `NO MARKET` or `Non-Nms` (HOLX at $0.01, VUECF, P5N994), or a Price of
   exactly 0 (THRD, SBT, PDLI, GTXI). No threshold is involved. NTRB's $0.00
   "SERIES A" row goes, but its real $8.23 row stays.
3. Class shares written with a space (`BRK B`, `HEI A`, `UHAL B`) go through
   the curated remap first and otherwise become the dash form. Before this
   they were silently dropped, and HEI-A ($69M/day), BF-A, GEF-B, LEN-B and
   UHAL-B would have left `full`.

**No silent staleness.** `ISHARES_SNAPSHOT_STALE_DAYS = 120` (the old loader's
existing 120-day warning, now named). Age is measured from the "Fund Holdings
as of" date inside the file, not the mtime; in the image the mtime is the
build time.
- A served snapshot older than that logs `STALE`.
- `universe_counts()` gives every iShares list its `source` and `snapshot`
  status, and names the stale served ones in `_stale`.
- `health_audit.check_universe_counts` WARNs on `_stale`, even when every
  count is inside its band.

**Measured in the api container, read-only** (branch modules loaded in
memory; no cache, Mongo or `/app` writes; Massive bars fetched in memory):

| | before | after |
|---|---|---|
| `full` | 2,685 | **2,725** (+90 / −50) |
| russell3000 | 2,559 (cache ← May xls) | 2,587 (live, as of 09-28) |
| russell1000 | 1,001 | 1,022 |
| microcap | 1,278 | 1,353 |
| themes | 296 / 300 | 296 / 300 (untouched) |

- **44 adds pass the $20M floor** (HOLX is now excluded). They include FIG,
  SUNB, FROG, TTAN, CHYM, INIO, QNT, FRVO, DPC and BXDC.
- JMKE (43 bars), STLN (40) and HUCK (4) fail on history, not on dollars.
- Of the 50 removes, three are liquid:
  - PGY ($54M) and RZLV ($36M): no longer in IWV. **HIS CALL**: keep them via curated?
  - VSCO: stale since 06-01, and VSXY is already in `full`.
- Q3 adds now in `full`:
  - R1000: all 5 (INIO QNT JMKE FRVO DPC).
  - R2000: 7 of 28 (PBLS CSQR EROC COAG LCLN BXDC BRUN).
- Still missing:
  - 19 are held only by IWM. That is IWV sampling; **Option B (IWB ∪ IWM) is
    HIS CALL.**
  - EMAT and FRBT are in no iShares fund yet.
  - The 5 microcap-only names reach `broad`, not `full`.

The liquidity floor is still the only gate on what gets scanned. No names
were added by hand. `THEME_UNIVERSE` is untouched.

**Tests:** `backend/tests/test_russell_universe_refresh_2026_09_29.py`.

### 2026-09-29 (round 2) — critic fixes on the live-holdings ladder

| # | was | now |
|---|---|---|
| 1 | a parent re-baseline left the derived russell2000 publishing the backlog | it re-baselines with its parents in the same run (`universe_changes.md` §round 2) |
| 2 | a cache hit dropped the holdings date (`as_of=None`), and russell_watch stamped a live list with the snapshot's date | cache files versioned (`_CACHE_KEY_VERSIONS`: `russell1000_v2`, `russell3000_v2`, `microcap_v2`), so the May caches in the shared volume stop matching on deploy. Each file has a `<key>.as_of` sidecar, and a cache hit records `as_of`. `russell_watch._baseline` takes `files_date` from the list it used. It reports None for the curated fallback and never borrows the snapshot's date. |
| 3 | an iShares outage re-downloaded on every `load_universe` call | a failed or rejected live fetch is memoised per fund for `ISHARES_LIVE_FAILURE_MEMO_SEC = 3600`, so the ladder goes straight to the snapshot. The outage logs one WARNING, then INFO. The resolved list is memoised per cache generation (path, mtime_ns, size of the list + sidecar), and the snapshot is parsed once per file generation. |
| 4 | the health audit warned only on a snapshot past 120 days | `universe_counts()["_snapshot_served"]` names every served snapshot at any age. `check_universe_counts` WARNs with each one's holdings date, and adds `STALE` for the `_stale` subset. |
| 5 | microcap's band `(0, 2500)` accepted a truncated IWC parse | a live list under `ISHARES_LIVE_MIN_SNAPSHOT_FRACTION = 0.60` of the committed snapshot's count is rejected, and the snapshot serves. Applied to all three lists; it never loosens a static floor (R1000 614 < 900, R3000 1,553 < 1,800). Microcap floor today: 812 (snapshot 1,353). No snapshot means no floor. |

**Re-measured in the api container, read-only** (branch modules in memory,
TEMP cache; no `_v2` file appeared in the shared cache volume):

- `full` = **2,725** (unchanged from round 1), 4.2 s cold, one iShares fetch.
- R1000 1,022 · R3000 2,587 · microcap 1,353 · derived R2000 1,565, all live
  as of 2026-09-28. A cache hit keeps `as_of` 2026-09-28.
- Simulated outage: three `load_universe("full")` calls plus five
  `fetch_russell3000` calls made **1** iShares attempt, and `full` stayed 2,725
  off the snapshot. The next attempt came after the memo expired (fake clock
  +3600 s). The health check WARNed "served from the committed iShares
  snapshot … holdings as of 2026-09-28".

**Tests:** `backend/tests/test_russell_universe_refresh_round2_2026_09_29.py`.

