# 🩳 Short interest — on every Chart Maps tab and the ticker page (2026-10-03)

**Display only. UNMEASURED on this app's universe. Not advice.**
Nothing here gates, sorts, sizes, pushes or enters a lane.

## The ask (Ajay, 2026-10-03, verbatim)

> "I would like to see a new field for sotcks about short interest I heard EOSE has about 40% short interest is Short Interest always accurate about a stocks down fall?
> can you add this field to all our chart maps scan. also the individual tickers please"

## His question — "is short interest always accurate about a stock's down fall?"

**No. Short interest is not a forecast.** It is a count of open short positions at a FINRA
settlement date (twice a month), published about 7 business days later.

- What the literature finds is an *average* across many stocks, and it is small:
  Asquith, Pathak & Ritter (2005, JFE) report about −2.15%/month equal-weighted for the most-shorted
  names, but −0.39% value-weighted and not significant. The effect shrank after publication
  (McLean & Pontiff 2016, JF). No peer-reviewed single-stock hit rate exists — never quote one.
- Part of any name's short interest is hedging, not a bet on a fall. EOSE has $600M of 1.75%
  convertible notes due 2031 (EOSE 8-K, 2025-11-24); convertible arbitrage shorts the stock.
- On this app's universe the claim is **UNMEASURED**. A study would ship with a script, a CI and a
  placebo (his call #12); the prior from the literature is a small, faded effect.

**EOSE** (probe 2026-10-03 — re-run `backend/scripts/short_interest_live_check.py` before quoting):

| item | value |
|---|---|
| settlement | 2026-09-15 (published 2026-09-24) |
| shares short | 120,015,346 (+7.8% vs 2026-08-31's 111,323,398) |
| % of float | ~33.6% (yfinance float 357.3M) |
| % of shares outstanding | ~33.2% (yfinance 361.7M); 33.0% of the 10-Q count (364.2M) |
| days to cover | 4.13 |
| the app's cache before this change | 2026-08-31: 30.57% of shares outstanding, 4.95 days — one settlement behind |

His "about 40%" matches ChartExchange's 42.21% "of float", which divides by a smaller float.
Finviz and StockAnalysis show about 33.6%. Same count, different denominator.

## Definitions (the ℹ️ `short_interest` section says the same, built from the constants)

- **Short interest** — shares sold short and not yet bought back, reported by FINRA member firms
  for two settlement dates a month (the 15th, or the business day before, and the last business
  day), published on the 7th business day after (FINRA Rule 4560). The app reads it from Massive,
  which aggregates the FINRA reports.
- **% of float** = shares short ÷ float. **% of shares outstanding** = shares short ÷ shares
  outstanding. Both counts are yfinance's (`floatShares` / `sharesOutstanding`, cached in
  `shares_cache`) and carry their own date; older per-name records use Massive's reference shares
  outstanding (`LEGACY_SHARES_SOURCE`) — the hover names which. The chip leads with % of float when a float is on file,
  otherwise % of shares outstanding, and **says which** — a shares-outstanding % is never called
  "float".
- **Days to cover** = shares short ÷ average daily volume, as the provider computes it; the
  volume window differs between sites.
- **Short VOLUME** (the daily share of trades marked short, `short_volume_*` collections) is a
  different series and is not this number.

## What is served

`GET /short-interest/map?symbols=A,B,…` (first 200 read; ONE `$in` Mongo read, off the event loop,
never a provider call). Built by `backend/short_interest/read.py` — the FE prints `chip`, `title`
and `rows` verbatim and computes nothing.

| status | chip | ticker page |
|---|---|---|
| `ok` | `🩳 SI 33.6% float · 4.1d · 9/15` | settlement, shares short + change, % of float, % of shares outstanding, days to cover, freshness, source |
| `stale` | `🩳 SI 30.6% shs out · 5.0d · 8/31 · stale` | the same rows; Freshness reads `STALE — …` |
| `no_record` | nothing | "not read — no FINRA record at the last warm" |
| never warmed | nothing (absent from the map) | "Not read — no short-interest record is cached for this name yet." |
| request failed | nothing | "Not read — the short-interest request failed." (never "no record"; retried after `SI_RETRY_MS`) |

- No float on file → `🩳 SI 33.2% shs out · …`; neither count → `🩳 SI 440.3K sh · …`.
- Missing days to cover → the `· Xd` segment is dropped (never `0.0d`); a provider `0` is dropped
  from the chip too (the hover and the ticker page still print it). Missing = not shown, never 0.
- Float larger than shares outstanding (share classes, e.g. UHAL) → a ⚠ "counts disagree" line on
  hover and on the ticker page. Definitional, not a tuned filter.
- The cached `squeeze` label is never served; no colour or threshold on the chip.

## Freshness — FINRA's calendar, not a cache age

- Settlements: the 15th (or the business day before) and the last business day of each month.
- Publication: the 7th NYSE business day after (`FINRA_PUBLICATION_BDAYS = 7`). It reproduces all
  six published 2026 pairs, checked against `market_hours.reminder.ALL_HOLIDAYS`:

  | settlement | published |
  |---|---|
  | 2026-08-14 | 2026-08-25 |
  | 2026-08-31 | 2026-09-10 (Labor Day skipped) |
  | 2026-09-15 | 2026-09-24 |
  | 2026-09-30 | 2026-10-09 |
  | 2026-10-15 | 2026-10-26 |
  | 2026-10-30 | 2026-11-10 |

- **STALE** once the *next* settlement's publication day plus `SI_INGEST_GRACE_BDAYS = 2` business
  days has passed and the app still holds the older one (his call #3). A label, never a gate.
  Example: 2026-09-15 reads current through 2026-10-13 and stale from 2026-10-14.
- `ALL_HOLIDAYS` stops at 2027; extend it yearly (existing practice).

## The warm (cron, `python -m short_interest.client warm-si`)

Bulk by settlement date (`warm_short_interest_bulk`), over the `full` universe:

| situation | provider calls | writes |
|---|---|---|
| FINRA's calendar says no newer settlement can be out yet | **0** | none |
| one can be out, Massive still answers the held one | **1** | none |
| a new settlement is out | **3** (~5 s): newest-settlement probe on AAPL + latest + prior whole-market settlement | every FINRA ticker as a v2 doc; a remembered miss for a universe name FINRA has no row for |
| any call fails, or latest has < 90% of the prior's rows (`SI_BULK_MIN_ROWS_RATIO`, his call #11) | ≤ 3 | **none** (atomic; retried next run) |

- Denominators: ONE `shares_cache` read at warm time (yfinance float / shares outstanding + date),
  so the served read stays one query.
- A good older doc is never replaced by a miss and never moved backwards; a held name absent from
  the new settlement only gets `checked_settlement` set.
- **Ingest window (fixed 2026-10-03, critic finding).** Massive can be partway through loading a
  settlement on its publication day while still above the 90% guard. Until `due_date(latest)`
  (publication + `SI_INGEST_GRACE_BDAYS`) has passed, a universe name missing from the new
  settlement is `deferred`: no `checked_settlement`, no miss doc. It stays pending, so the next run
  fetches again (3 calls) and fills it. After the window it is recorded once (`kept` / `misses`)
  and later runs go back to 0 calls. The CLI line prints the `deferred` count.
- The old per-name warm survives as `warm-si --per-symbol`. Fixed the same day: a `None` answer
  (which is also what an HTTP error looks like) no longer overwrites a good doc (`kept`).
- Logs carry a status code or an exception type only — never `str(exc)` or a URL (key-leak lesson).
- `--dry-run` writes nothing; `show-si` prints v2 vs legacy counts and the max checked settlement.
- Comparison: the per-name path for 2,744 names is ~5,488 calls (~79 min).

Cron lines (repo `backend/crontab`, weekdays 07:40 and 18:40 ET, no closed-day gate — not a price
read). **The repo crontab is not the live crontab**: installing them is HIS ops step (#7).

## Per-tab coverage

| surface | how the chip reaches it |
|---|---|
| 20 board tabs (zones, deep_demand, quick_bounce, breaking, keltner, amd, key_levels, dual_momentum, ath, resiliency, fallen, ipo, gabbar, vcp, topping, ict, undervalue, zero_dte, earnings, winners) | `PatternChart` tile chip |
| support, holdings, potus, ema_frames | wrapper head (the tile skips its copy via `OuterChip 'short'`) |
| session, signals, hot_pullback, overnight, hot_sectors, bonde, growth, gnt, catalysts, patterns | their row chip |
| ticker page `/sepa/{SYM}` | header chip on every tab + `ShortInterestPanel` in the Smart Money tab |
| news | **none** — no ticker rows on this tab |
| IPO upcoming strip (not yet trading), SPY/QQQ index strip | **none** |
| ℹ️ | one `short_interest` pill per tab, beside 🧨 |

## Traps

- **BYND**: Massive reference shares outstanding 17.2M vs `shares_cache` 515.8M → the old path reads
  29.6% short for a name that is ~1%. The new read never calls Massive reference.
- GME and RZLV share counts differ > 10% between sources; UHAL float > shares outstanding (share
  classes); IIIV float 4.5M (77% of float, suspect); FCG, COAG, FIG have no `shares_cache` row.
  Every number shows its as-of; no outlier filter is tuned (Rule #1).
- `shares_cache` median age ~29 days (weekly TTL writer); the as-of is printed.
- **Two 🩳 numbers in the app**: the SEPA list cards (`RealtimeChips`, live per-card provider calls,
  Massive shares outstanding, elevated/high only) can disagree with the Chart Maps / ticker-page
  chip (his call #10).
- `pct_of_shares` keeps its legacy key name (📈 Bonde displays it); with v2 docs it is computed
  from `shares_cache`, so Bonde's displayed % changes (pass/fail is days to cover ≥ 5, unchanged).
- `sepa/scanner.py` reads `short_interest.si_pct` for the tiny-stock score; that input is dead
  (0 of 1,853 rows) and is deliberately NOT wired to this read (that would be a score change).
- `chart_maps/board.py` is untouched: `ATTACH_OWNED_KEYS` stays `("explosive", "band_structure")`
  and no `SORTS` key reads short interest (pinned by tests).
- Until his ops step runs, the live site shows only the 199 legacy 2026-08-31 docs, marked stale.

## HIS CALLS (defaults shipped as stated)

1. Headline basis: % of float when on file, else % of shares outstanding (alternative: always % of
   shares outstanding).
2. Denominators from `shares_cache` (yfinance) for both percentages — changes Bonde's displayed %.
3. Stale grace `SI_INGEST_GRACE_BDAYS = 2` business days (label only).
4. Bonde's 45-day stale label (`SI_STALE_DAYS`) left as is.
5. No colour, threshold or squeeze band on the chip.
6. No sort and no filter by short interest on any tab.
7. **Ops:** install the two `warm-si` lines in the live host crontab, then one first populate run
   (`docker exec cheetah-market-app-cron-1 python -m short_interest.client warm-si`, ≤ 3 calls,
   ~5 s). Agents do not run either.
8. Ticker page placement: header chip + Smart Money panel.
9. One more ℹ️ pill per Chart Maps tab.
10. The SEPA-card 🩳 chip: leave it (default) or repoint it to this cache.
11. Partial-settlement guard `SI_BULK_MIN_ROWS_RATIO = 0.9`.
12. Not built: 12-month history on the ticker page (~24 bulk calls); a short-interest study on this
    universe (script + CI + placebo).

## Sources

- FINRA Rule 4560 — https://www.finra.org/rules-guidance/rulebooks/finra-rules/4560
- FINRA short-interest schedule — https://www.finra.org/filing-reporting/regulatory-filing-systems/short-interest
- Massive short interest — https://massive.com/docs/rest/stocks/fundamentals/short-interest
- Asquith, Pathak & Ritter (2005), *Journal of Financial Economics*.
- Boehmer, Huszar & Jordan (2010), *Journal of Financial Economics*.
- McLean & Pontiff (2016), *Journal of Finance*.
- Brent, Morse & Stice (1990), *Journal of Financial and Quantitative Analysis*.
- Choi, Getmansky & Tookes (2009), *Journal of Financial Economics* (convertible arbitrage).
- Schultz (2024), *Journal of Financial and Quantitative Analysis*.
- SEC staff report on equity and options market structure (GameStop), 2021.
- Hong et al. (2015) — **working paper**.
- EOSE 8-K, 2025-11-24 (1.75% convertible notes due 2031).

## Files

- `backend/short_interest/read.py` (served read, calendar, ℹ️ section), `client.py` (bulk warm,
  per-name fix), `api.py` (`/short-interest/map`), `supply_demand/rules_info.py` (section wiring),
  `backend/crontab`.
- Tests: `backend/tests/test_short_interest_read_2026_10_03.py`, two in `test_short_interest.py`;
  shared FE↔BE fixture `backend/tests/fixtures/short_interest_blocks_2026_10_03.json`.
- Live check: `backend/scripts/short_interest_live_check.py` (writes blocked, ≤ 3 calls).
