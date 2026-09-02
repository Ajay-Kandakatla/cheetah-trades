# Supply watch — "when is the time to sell?"

**Ask (Ajay, 2026-09-02, Fidelity book on screen):** *"check when is the time to
sell, based on supply and demand — when will they hit supply? Give me a table in
portfolio page and also add alerts."*

**Where:** Portfolio page → **🎯 Supply ahead** table. `GET /portfolio/supply`.
Code: `backend/portfolio/supply_watch.py`, `frontend/src/components/SupplyWatch.tsx`.

## What it computes (per holding)

| Field | Meaning |
|---|---|
| Sell zone | The **first supply band going up**: the daily swing-cluster zone that contains the live price, else the lowest band whose bottom is above it. Same engine as the Chart Maps tabs (`supply_demand.price_zones.for_symbol`, 2-year daily frame). |
| Distance | `% from live to the band BOTTOM` — the first print that meets sellers. |
| ATR-days | distance ÷ 14-day ATR (`supply_demand.patterns.atr`). A *pace*, not a forecast. |
| State | `IN_SUPPLY` (inside the band) · `NEAR` (≤2% under) · `APPROACHING` (≤5%) · `FAR` · `CLEAR` (nothing overhead in 2y — trail the stop). |
| then … | The next band above, so a trim plan has a second level. |
| Support | Nearest demand band below (for the stop conversation). |

Uncited market-structure convention (zones family) — **not** SEPA book logic
(see `feedback_sepa_book_scope`). The Minervini sell rules (TLSW pp.291-315)
stay where they are; this is the *where-are-the-sellers* overlay Ajay asked for.

## Two halves, two cadences

- **Zone half** (slow, ~50 s for 8 names when Massive is sluggish): cached in
  Mongo `portfolio_supply_cache` for 30 min, keyed by user, invalidated when the
  set of held tickers changes.
- **Price half** (cheap): `portfolio.quotes.fetch_quotes` on every call, so the
  60-second page poll and the 5-minute alert cron both see the **live** print
  (pre/after-market included) against the cached zones. `derive()` is pure.

## Alerts

`check_alerts()` runs from cron (`2-57/5 4-19 * * 1-5`) and pushes on the
**existing `position_alert` kind** — Ajay's stop/target channel — no new phone
kind. Fires when a holding is `IN_SUPPLY` or within **1%** of its band, **once
per (user, symbol, band, day)** (`portfolio_supply_alerts` dedupe doc). Skips when
`timeframes.live_state()` says the tape is closed (holiday-aware). Title carries
a `PRE ·` / `AH ·` prefix outside regular hours.

## First live read (2026-09-02 10:47 ET)

BMNR NEAR (1.05% under $23.47–23.85) · UBER APPROACHING (2.1%, ~1 ATR-day) ·
LEU/CAI/VST/AAOI/EOSE/CATG FAR (12–29% of room).

## Tests

`backend/tests/test_supply_watch.py` (pure `nearest_supply` / `classify` /
`should_alert` tables, inverted-band and no-price negatives, cache reuse vs
re-price, different-book invalidation, cron + route guards);
`frontend/src/components/SupplyWatch.test.tsx` (render, closed/no-poll, poll
cadence, HTTP-error and empty negatives).
