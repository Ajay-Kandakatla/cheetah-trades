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
