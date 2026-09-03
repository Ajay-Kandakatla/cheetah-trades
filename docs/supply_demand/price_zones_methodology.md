# Price-Structure Supply/Demand Zones — Methodology (2026-06-09)

**On-demand, per-ticker.** For any symbol, find the price *bands* where supply
and demand showed up, and read whether the current price is a clean place to enter.

- **Code:** `backend/supply_demand/price_zones.py`
- **Endpoint:** `GET /supply-demand/price-zones/{symbol}`
- **Page/Tool:** on-demand symbol lookup (frontend `PriceZonesTool`).

## Method (CONFIGURED — not a book methodology)

Ajay chose "plain price-structure zones" (2026-06-09), explicitly **not** a named
method (not Minervini, not Seiden). So **every threshold here is a configured house
value**, documented as such — nothing is presented as a book rule (Rule #1).

1. **Swings:** local highs (on `high`) and lows (on `low`) over the last
   `LOOKBACK_BARS` (252), each a local extremum vs `SWING_WINDOW` (4) bars per side.
2. **Bands:** swings within `ZONE_MERGE_PCT` (1.75%) of each other merge into one
   band. **Swing-high clusters = SUPPLY (resistance); swing-low clusters = DEMAND
   (support).** A single-swing band gets a `ZONE_HALF_WIDTH_PCT` (0.6%) half-width.
3. **Strength (0–100):** half from **test count** (how many swings formed the band),
   half from **volume** traded at those bars. More tests + more volume = stronger.
4. **Relative to the live price:** nearest band ABOVE = overhead resistance, nearest
   band BELOW = support (a broken support band above the price counts as resistance).

## Entry read (decision-support, NOT advice)

| State | Meaning | Read |
|---|---|---|
| `AT_DEMAND` | price inside a demand band | favorable — support is right here |
| `CLEAR_RUNWAY` | runway above **and** support within `NO_SUPPORT_PCT` (6%) below | favorable — room up, risk defined |
| `MID_RANGE` | between bands, nothing within the near thresholds | neutral |
| `INTO_SUPPLY` | overhead supply within `NEAR_PCT` (3%) above | caution — risk of stalling |
| `AT_SUPPLY` | price inside a supply band | caution — resistance here |
| `EXTENDED_NO_SUPPORT` | at/near highs, no overhead **and** no nearby support | caution — extended, no defined risk |

`EXTENDED_NO_SUPPORT` is the same shape as the **ARCB** buyable bug (at highs, ran
past structure, nothing to lean on) — so this tool agrees with the `is_buyable`
3%-past-pivot gate rather than contradicting it.

## Configured constants (locked by `tests/test_price_zones.py`)

`LOOKBACK_BARS=252`, `SWING_WINDOW=4`, `ZONE_MERGE_PCT=1.75`,
`ZONE_HALF_WIDTH_PCT=0.6`, `NEAR_PCT=3.0`, `CLEAR_RUNWAY_PCT=8.0`,
`NO_SUPPORT_PCT=6.0`, `MAX_ZONES_PER_SIDE=4`.

> **Not advice.** A pragmatic structural read of where supply/demand previously
> traded. Not a buy signal and not personalized financial advice.

## 2026-09-02 — surfaced bands are the NEAREST, not the strongest

`supply_zones` / `demand_zones` used to carry the 4 *strongest* clusters per
side. Every consumer (Support tab, Portfolio supply watch, demand re-entry's
entry-zone pick, signal watch, the board tiles) asks "what is nearest / what
am I standing in", and the strongest-4 cut routinely dropped exactly that
band: CRWD's 6-month view lost the 216–219 and 227 swing highs its SMC ledger
was sweeping; UBER's portfolio row missed the band price was inside. The cut
is now by **distance from price** (`nearest_first`, inside-band first, ties by
strength), output order still high → low, `strength` still on every band, and
`max_zones=None` returns every cluster. `nearest_resistance` / `nearest_support`
were always computed over every band and are unchanged.


## Today's live bar overlay (2026-09-03)

Ajay (CHPT): *"This is inaccurate.. Because it bounced off of demand"* — the Supply/Demand
tab said "nearest support $5.08–5.12 · 1.4% below" off the 09-02 close of 5.19 while the
tape printed 9.14 (+76%). The daily parquet is refreshed by the 4:30pm fast-scan, so every
intraday read of the frame was a day stale.

`sepa.prices.with_today_bar(df, symbol)` appends the Massive snapshot's day bar
(open/high/low/close/volume, indexed at `<today> 04:00` like the frame) when the frame ends
on an earlier session. Wired into `price_zones.for_symbol` (daily branch; the payload carries
`live_bar {appended, date, last_price, as_of_epoch}`), `chart_maps/support._frame_for` (the
S/D tab — `as_of` becomes the snapshot's last-trade time) and `chart_maps/board.bars_for`
(tile candles). Silent no-op when there is no snapshot, the snapshot has pre-market zeros, or
the frame already holds today (after the close + fast-scan). **Nothing is written back**: the
cached frame stays closed-bars-only and the scanner never sees a partial bar.

Tests: `tests/test_prices_today_bar.py`.

## The 7% already-bounced gate on Chart Maps demand boards (2026-09-03)

Ajay: *"from all chart maps Demand zones remove anything that already did about 7% bounce
from Demand Zone."* `chart_maps/board.py` `BOUNCE_DONE_PCT = 7.0`, `drop_bounced()`:
every demand board (zones reached / approaching × zone / order block, Deep Demand) drops a
name whose **live** print is ≥ 7% above the band top (order block top when that is the
target; the second band for Deep Demand); the scan's `last_price` decides only when the tape
is unreachable. Payload carries `dropped_bounced` + `bounce_done_pct`; the page says how many
were hidden. Measured from the band top because price re-enters from above — the top is where
the bounce starts. Tests: `test_chart_maps.py` "already-bounced gate" block.
