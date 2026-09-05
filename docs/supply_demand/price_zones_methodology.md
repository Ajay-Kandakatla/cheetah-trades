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
is unreachable **or has no usable print for the name** (2026-09-05, Ajay: "yes please fix the
bugs": the live print is the last trade, else the day bar, and a non-positive value — the day bar
is 0 before the open — is *missing*, not a price; `0.0` had made the gate inert pre-market). Payload carries `dropped_bounced` + `bounce_done_pct`; the page says how many
were hidden. Measured from the band top because price re-enters from above — the top is where
the bounce starts. Tests: `test_chart_maps.py` "already-bounced gate" block.

## 2026-09-05 — engine fixes (Ajay: *"yes please fix the bugs"*)

A six-agent review of the zone logic reproduced four defects in this module's
path; Ajay signed off on every fix, including the ones that change what the
boards print. No threshold changed. Tests: `tests/test_price_zones.py` block
"engine fixes 2026-09-05", guards in `tests/test_supply_demand_contracts.py`.

**`AT_DEMAND` no longer forces `support_pct` to 0.0.** `nearest_support` is the
band *below* price, never the one it stands in, and the /zones page prints
`nearest_support lo–hi (−support_pct%)` as one statement — so a name inside a
79.5–80.5 demand band printed "$69.58–$70.42 (−0.0%)" for a band 12% down. Both
sides now carry the true distance to the band the payload names, exactly as the
`AT_SUPPLY` side always did; the containing band is in the label ("In a demand
zone ($lo–$hi, N× tested) — support is right here"). `demand_reentry` still sets
`support_pct: None` on `DEMAND_BROKEN` — that withdrawal is unchanged.

**Structure is read off CLOSED bars only — a deliberate narrowing of the
2026-09-03 live-bar decision.** `for_symbol` still overlays today's snapshot bar
(and the intraday path still ends on the in-progress bucket), but swings/bands,
fair value gaps, ATR and `trade_levels` are computed on the frame *before* that
bar. The live bar supplies only the price the verdict and distances are read at
and the `live_bar` block the chart draws. Why: a displacement bar followed by
today's live bar produced a "three-bar imbalance" whose top edge was the live
bar's low-so-far — it shrank or vanished as the session moved, and the same bar
leaked a partial-day true range into the ATR the stop buffer scales by.
`bars_since_test` / `oldest_touch_bars` therefore count closed sessions. CHPT's
read is unaffected: the verdict still sees the +76% print.

**Degenerate multi-touch bands get the single-swing width.** Two swing highs a
fraction of a cent apart (1.2001 / 1.2004) merged into a 2-touch band that
rounded to 1.20–1.20 — zero width, so `trade_levels` returned None and
`in_price` needed a one-cent hit. When a cluster's span rounds below one tick at
2dp (`_TICK_2DP = 0.01`, the rounding grain, not a threshold) it receives the
same symmetric `ZONE_HALF_WIDTH_PCT` half-width a lone swing gets. **Only the
degenerate case** is widened — a one-tick span (110.00–110.01) or any real span
is left as the swings drew it; widening every multi-touch band would reshape
every board and needs a re-measure first.

**`with_today_bar` rejects phantom and weekend bars.** The overlay had none of
the guards `patch_latest_closes` applies to the cache, so a pre-session snapshot
echoing yesterday's completed aggregate under today's date (the case
`_drop_phantom_tail`'s own docstring documents) was appended as "today's live
bar" — a duplicated session for every zone / ATR / gap read, flagged
`appended: true`. It now applies the same phantom test (identical close AND
volume to the last closed bar, via `_drop_phantom_tail`) and the same weekend
rejection (`bulk_snapshot` falls back to today-ET when `day.t` is absent, so a
Saturday read stamps Friday's aggregate with Saturday's date). A rejected
snapshot returns the frame untouched with `appended: false` and a `reason`.
Tests: `tests/test_prices_today_bar.py` block "engine fixes 2026-09-05".
