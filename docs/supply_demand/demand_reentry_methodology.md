# Demand-zone re-entry — methodology

_Added 2026-08-13 (Ajay: "update my Supply and demand page with stocks that
entering back in to demand zones and give me a scan button … scan only S&P 500
stocks for this", plus a hand-marked SNDK TradingView chart for the per-stock
drawing)._

> **METHOD HONESTY.** This is a **configured, pragmatic price-structure read —
> NOT a named book methodology.** Every threshold below is a house value chosen
> from measurement, not a Minervini (or any author's) number. Two things are
> borrowed rather than invented: the **trend gate** reuses the contract-locked
> `sepa.trend_template` (the 8 Stage-2 criteria), and the **stop sanity cap**
> reuses `trading.risk_rules.ABS_MAX_STOP_PCT`. Decision-support only — not a
> buy signal and not advice.

## What the signal actually is

A **transition**, not a snapshot:

1. price is **inside** a demand band today, and
2. price traded **≥ `MIN_RISE_ABOVE_PCT` above that band's top** inside the last
   `REENTRY_LOOKBACK_BARS` sessions (it *left*, then came back), and
3. the band is real support — **≥ `MIN_TOUCHES` tests** and
   **≥ `MIN_ZONE_STRENGTH`** strength, and
4. the **trend still holds** — `sepa.trend_template` passes ≥ `MIN_TREND_CHECKS`
   of 8.

A name that has simply sat inside a band for months is **not** "entering back
in" and is excluded (`test_not_a_reentry_when_price_never_left_the_band`). A
name **below** the band has broken support — the opposite signal — and is also
excluded (`test_not_a_reentry_when_price_is_below_the_band`).

## Parameters (all house values)

| Constant | Value | Why |
|---|---|---|
| `SWING_WINDOW` | 5 | bars each side for a swing point |
| `MERGE_PCT` | 4.0 | swings within 4% merge into one band |
| `HALF_WIDTH_PCT` | 1.75 | width given to a single-swing band |
| `REENTRY_LOOKBACK_BARS` | 40 | window the run-up must sit inside |
| `MIN_RISE_ABOVE_PCT` | 5.0 | how far above the band it must have traded |
| `MIN_TOUCHES` | 2 | an untested band is not support |
| `MIN_ZONE_STRENGTH` | 40 | 0–100, tests + volume at the band |
| `MIN_TREND_CHECKS` | 6 of 8 | no falling knives |
| `STOP_BUFFER_PCT` | 1.5 | stop sits under the floor, not on it |

### Why the bands are WIDER here than on the /zones page

The `/zones` defaults (`ZONE_MERGE_PCT` 1.75, `ZONE_HALF_WIDTH_PCT` 0.6) produce
**~1%-wide bands**. Measured across the S&P 500 on 2026-08-13, those produced 21
"re-entries" — almost all utilities (AEP, DTE, LNT, AEE, DUK, ED, ATO), most of
them 1 bar after price crossed a band **0.5–0.8% wide**. Example: AON, band
`348.00–350.83`. That is price wiggling inside a line, not demand absorbing
supply.

Widening to merge 4.0 / half-width 1.75 and adding the trend gate produced 9
hits from the same 200 names — CMI, FIX, CIEN, COHR, GOOG — real pullbacks into
multi-tested bands (COHR fell **23.9%** from its high into a 3×-tested band).

The geometry is passed **per call** into `price_zones.compute(...)`. It must
**never** be applied by mutating the module globals — that would silently change
the `/zones` page and `orderflow.signals`, which share the module. Locked by
`test_price_zones_defaults_are_untouched_by_this_module`.

## The written entry / exit

`trade_plan()` (pure, unit-tested):

- **Entry band** = the demand band itself — buy *into* support, not through it.
- **Stop** = `STOP_BUFFER_PCT` under the band floor. Below the floor the reason
  for the trade is gone.
- **Target** = the **low of the nearest overhead supply band** — the first place
  sellers are known to be waiting. When there is no supply band above,
  **`target` is `None`** and no R:R is shown. We do not invent a target
  (`test_trade_plan_without_overhead_supply_has_no_target_or_rr`).
- **`risk_exceeds_max`** flags a stop wider than `ABS_MAX_STOP_PCT` — the plan
  is surfaced as undefendable rather than silently handed over.

Display note: actionable levels use `level()` on the FE, which always keeps
cents. `money()` rounds $98.50 → "$99", which would show a **tighter stop than
the one computed** — never round a risk level
(`zonePlan.test.ts › level — actionable risk levels must never round`).

## Universe — "S&P 500 only" must mean the S&P 500

**Bug found + fixed 2026-08-13.** `sepa.universe.fetch_sp500()` fetches from
Wikipedia, which now answers **403** to the container. The old fallback returned
`UNIVERSE` — the **158-name curated momentum list**, a completely different
universe. Anything asking for "S&P 500 only" silently scanned 158 mega-caps.

The on-disk cache held the real **503 constituents** but was 76 days old, past
the 30-day TTL, so it was ignored.

New order: **fresh fetch → stale cache → curated.** An expired snapshot of the
real index (membership turns over a few names a quarter) beats a fresh list of
the wrong universe. If we ever *do* fall through to curated, the payload sets
`universe_is_sp500: false` and the page renders a warning — it must never
quietly claim "S&P 500" over the wrong names
(`test_scan_reports_when_the_universe_is_not_actually_sp500`).

## Surfaces

| Where | Component | Endpoint |
|---|---|---|
| `/supply-demand` → 🟢 Back in Demand tab | `DemandReentryPanel` | `GET /supply-demand/demand-reentry`, `POST …/scan` (the Scan button) |
| Individual stock → Setup tab | `ZoneMap` | `GET /supply-demand/zone-map/{symbol}` |

The zone map draws red supply bands, green demand bands, the entry band outlined
**BUY**, and dashed **STOP** / **TARGET** rules — the plan reads off the picture.
It renders for **any** symbol, including names sitting in overhead supply (the
SNDK case in Ajay's screenshot), not only re-entry hits.

Caching: 3h in-process, `force=True` on the Scan button.

## What it is NOT

Not a buy signal, and it feeds **no** scanner score and **no** Auto-Pilot gate.
It is a structural "where would I buy this, and where am I wrong" read. The
strict `is_buyable` gate still decides buyable-now.
