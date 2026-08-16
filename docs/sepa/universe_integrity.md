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
