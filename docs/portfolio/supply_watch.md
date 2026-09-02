# Supply watch — "when is the time to sell?"

**Ask (Ajay, 2026-09-02, Fidelity book on screen):** *"check when is the time to
sell, based on supply and demand — when will they hit supply? Give me a table in
portfolio page and also add alerts."*

**Where:** Portfolio page → **🎯 Supply ahead** table. `GET /portfolio/supply`.
Code: `backend/portfolio/supply_watch.py`, `frontend/src/components/SupplyWatch.tsx`.

## What it computes (per holding)

| Field | Meaning |
|---|---|
| Sell zone | The **first supply band going up**: the daily swing-cluster zone that contains the live price, else the lowest band whose bottom is above it. Same engine as the Chart Maps tabs (`supply_demand.price_zones.for_symbol`) — but with **every** cluster (`max_zones=None`): the tabs keep only the 4 *strongest* bands, and the first band overhead is routinely not among them (review 2026-09-02: UBER was inside a band the truncated list did not carry; VST's first band was 2% away, not 19%). Frame = `price_zones.LOOKBACK_BARS` = 252 daily bars (~1y). |
| Distance | `% from live to the band BOTTOM` — the first print that meets sellers. |
| ATR-days | distance ÷ 14-day ATR (`supply_demand.patterns.atr`). A *pace*, not a forecast. |
| State | `IN_SUPPLY` (inside the band) · `NEAR` (≤2% under) · `APPROACHING` (≤5%) · `FAR` · `CLEAR` (nothing overhead in the 1y frame — trail the stop) · `UNKNOWN` (no live print, or the zone engine missed — reads *"Sell zones unavailable — retrying"*, never a false CLEAR; an errored book retries within 2 min). |
| then … | The next band above, so a trim plan has a second level. |
| Support | Nearest demand band below (for the stop conversation). |

Uncited market-structure convention (zones family) — **not** SEPA book logic
(see `feedback_sepa_book_scope`). The Minervini sell rules (TLSW pp.291-315)
stay where they are; this is the *where-are-the-sellers* overlay Ajay asked for.

## Two halves, two cadences

- **Zone half** (slow, ~50 s for 8 names when Massive is sluggish): cached in
  Mongo `portfolio_supply_cache` for 30 min, keyed by user, invalidated when the
  set of held tickers changes.
- **Price half** (cheap): `quote_book()` on every call — `sepa.prices.bulk_live_prices`
  taking the **last trade** over the day bar's close (`last_trade_price or price`:
  the day bar is the 16:00 print all evening and `0` before the open), with the
  portfolio quote cache as fallback. So the 60-second page poll and the 5-minute
  alert cron both see the pre/after-market print against the cached zones, and
  the row carries a PRE / AH session badge. `derive()` is pure. Holdings are
  aggregated per ticker across accounts first (shares and total cost add).
- The zone engine is called **without** a live anchor (`for_symbol(sym, max_zones=None)`):
  a pre-open `0.0` once made `compute()` divide by zero and cache an empty
  book as CLEAR for 30 minutes.

## Alerts

`check_alerts()` runs from cron (`2-57/5 4-19 * * 1-5`) and pushes on the
**existing `position_alert` kind** — Ajay's stop/target channel — no new phone
kind. Fires when a holding is `IN_SUPPLY` or within **1%** of its band, **once
per (user, symbol, band, ET trading day)** (`portfolio_supply_alerts` dedupe doc —
the day key is ET, a 19:02 ET tick in winter is already tomorrow in UTC). The
dedupe doc is written on a *terminal* outcome: delivered, **or nobody targeted**
(muted pref / quiet hours / no device) — only a genuine send failure retries, so
a muted kind cannot turn every 5-minute run into a duplicate feed row. Skips when
`timeframes.live_state()` says the tape is closed (holiday-aware). Title carries
a `PRE ·` / `AH ·` prefix outside regular hours; the payload carries top-level
`url` / `kind` / `ticker` so a tap opens `/portfolio`.

## First live read (2026-09-02 10:47 ET)

BMNR NEAR (1.05% under $23.47–23.85) · UBER APPROACHING (2.1%, ~1 ATR-day) ·
LEU/CAI/VST/AAOI/EOSE/CATG FAR (12–29% of room).

## Tests

`backend/tests/test_supply_watch.py` (pure `nearest_supply` / `classify` /
`should_alert` tables, inverted-band and no-price negatives, cache reuse vs
re-price, different-book invalidation, errored-cache 2-min retry, per-ticker
aggregation, last-trade-over-day-bar pricing incl. the pre-open zero, ET day key,
dedupe-on-terminal-outcome, deep-link payload, `max_zones=None` source guard;
`tests/test_price_zones.py` proves the additive `max_zones` kwarg leaves the
default byte-identical) ;
`frontend/src/components/SupplyWatch.test.tsx` (render, closed/no-poll, poll
cadence, HTTP-error and empty negatives).
