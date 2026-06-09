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
