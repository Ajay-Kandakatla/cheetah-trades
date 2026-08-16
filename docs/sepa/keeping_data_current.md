# Keeping the data current — warms, membership changes, accumulation alerts

> Ajay 2026-08-16: *"Can you run this for all the russel 3000 and all the
> tickers we have.. we have too keep updating.. 1. Latest tickers as they change
> like getting added to SP 500 or Russel 3000 and Nasdaq. 2. Also check
> Accumulation data and Filing of 10F or 13Fs. Also give me updated and
> notification as Accumulations change as money moving I need a comparison.
> Def make a rule to check data time to time please"*

Four pieces, all scheduled. See also `docs/sepa/period_freshness.md`.

---

## 1. The 13F holder cache had no warmer at all

`warm_whales_13d.py` opens with *"Mirror of warm_whales.py"* — and
`warm_whales.py` **was never written**. So `whales_cache` was lazy-only since
day one: a ticker's institutional holders were fetched when someone opened that
ticker's modal, and never otherwise.

Measured 2026-08-16:

| | |
|---|---|
| Cached tickers | 1,379 |
| Older than the 24h TTL | **1,377** |
| Sample of 40 re-fetched | **32 returned a different quarter** (cached Q1, live Q2) |

So the board was showing a quarter-old picture of who owns what, on names
nobody had clicked recently.

**`backend/sepa/warm_whales.py`** — Sundays 6:00am ET. First full sweep:
**2,611 tickers, 0 failures, 2,212 rolled to a new quarter, 128 seconds** at 4
workers. ETFs are excluded (a fund files no 13F about itself; the provider 404s
and the empty result caches under a 1-hour TTL, so ~400 of them would be
re-asked every sweep). `--stale-only` is the default, so later runs skip
anything already on the current quarter.

## 2. Index membership now has history

`universe.py` re-fetched constituent lists but on a **30-day** disk cache and
kept **no history**, so an S&P 500 add could take a month to enter the scan and
nothing recorded that it was new.

**`backend/sepa/universe_changes.py`** — Sundays 6:30am ET. Expires each cache,
refetches, diffs against the last snapshot, stores adds/drops. Read at
`GET /universe/changes`.

Tracked: `sp500`, `sp400`, `sp600`, **`nasdaq100`**, `russell1000`, `russell3000`.

**Nasdaq was in no fetcher before this.** `fetch_nasdaq100()` is new. Note the
source URL: the components table lives on
`List_of_NASDAQ-100_companies`, **not** on the `Nasdaq-100` article, which now
carries only index history — that one yields 0 tickers. Verified live: 102
symbols (100 companies; GOOG/GOOGL and FOX/FOXA are dual-class), financials
correctly absent.

Two guards, because a change log that invents adds is worse than none:

- **Churn gate** — a diff above `max(8, 35% of the list)` is treated as a
  broken parse, and is neither snapshotted nor logged. A Wikipedia reshape that
  returns 12 names would otherwise publish "488 companies left the S&P 500".
  Russell's annual June reconstitution (~8%) stays well under it.
- **Provenance gate** — a list that resolved to the curated fallback or a stale
  cache is refused outright. The Russell lists read local iShares files and
  record no provenance, so they report `provenance_known: false` rather than
  implying we verified freshness.

## 3. Accumulation comparison — and why it needs a snapshot store

> *"give me updated and notification as Accumulations change as money moving
> I need a comparison"*

**`backend/supply_demand/accumulation_changes.py`** — Sundays 7:00am ET, after
the warm.

### The two wrong answers this avoids

**Wrong answer #1 — sum the quarters.** The existing modal adds every holder's
dollars regardless of which quarter they filed, producing APGE's
`+$2.1B bought · −$1.0B sold · Net inflow: +$1.1B`. Measured: 1,322 of 1,379
payloads mix quarters. That total describes no period.

**Wrong answer #2 — difference the quarter totals.** The first version of this
module did exactly that and printed **NVDA +$1,520B (+968%)**. The provider
returns only the top ~10 holders, so this compared "the 2 funds still on Q1"
against "the 8 that had filed Q2". Pure sample size; no money moved.

### What it actually does

Measured on live data: **within a single payload, each fund appears exactly
once**, at its own latest report date — so the overlap between the two quarters
inside one payload is **zero, on every ticker sampled**. There is no
quarter-over-quarter comparison to be extracted from one payload at all.

So the comparison runs against **our own stored snapshot**
(`whales_snapshots`), and:

- the headline is computed only over funds present in **both** pictures
- entrants and exits are reported separately, **never folded into** that figure
  (a fund "leaving" may just have dropped out of the provider's top-N)
- fewer than 3 overlapping funds → `comparable: false`, not a confident number

Baselines banked 2026-08-16: **3,594** (1,942 on Q2 2026, 1,648 still on Q1).
Empty pictures are refused — a snapshot with no holders would still match the
"different quarter" lookup and fabricate a 100% outflow.

**Comparisons therefore start at the next roll.** The 1,648 names still showing
Q1 will produce one as their funds file Q2 over the coming weeks; the rest at
the Q3 deadline (Nov 14).

### The notification

New push kind **`accumulation_change`**, default on. This is a **4th kind** on a
deliberately-small keep-set (`todo_reminder`, `pivot_alert`, `position_alert`),
added because Ajay asked for it explicitly. It stays tolerable because:

- 13F rolls **quarterly**, so the natural rate is ~4 events per name per year
- scope is **holdings + watchlist only** — a universe-wide version would be
  ~2,600 pushes a quarter
- all names go in **one consolidated message**, top 5 by size plus a count
- idempotent per `(symbol, quarter)` — a quarter's move is announced **once**,
  not re-announced every Sunday for three months

Read at `GET /supply-demand/accumulation-changes` and
`GET /supply-demand/accumulation-changes/{symbol}`.

## 4. The periodic data check now covers the filings too

`observability/period_freshness.py` gained two event-driven checks alongside the
quarterly one, because they ask a different question — *has anything arrived
lately?* rather than *which quarter is this?*

| Check | Question | Limit |
|---|---|---|
| `13f_institutional_holders` | is the reported quarter current? | SEC 45-day rule + 21d grace |
| `13f_edgar_filings` | has `giants_13f_filings` received anything? | 120 days |
| `13dg_filings` | has `whales13d_cache` received anything? | 60 days |

Live 2026-08-16: all three green — holders 100% at Q1-or-newer, EDGAR filings
1 day old, 13D/G 1 day old.

---

## Schedule summary

| When | Job |
|---|---|
| Sun 06:00 ET | `sepa.warm_whales` — refresh 13F holders across the universe |
| Sun 06:30 ET | `sepa.universe_changes` — index membership refresh + diff |
| Sun 07:00 ET | `supply_demand.accumulation_changes` — bank baselines, compare, alert |
| 1st of month 08:20 ET | `observability.period_freshness` — are the dated sources current? |

**Not advice.** 13F is filed up to 45 days after quarter end, so "money moved
in" describes a position built up to four and a half months ago. Context for a
setup, never a trigger. The Auto-Pilot engine never reads any of this.
