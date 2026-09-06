# Quick Bounce — which names turn at a demand band the same day

**Ask (Ajay 2026-09-06):** "Can you create a 'quick bounce potential' list? ...
These stocks the expectation is they touched the demand zone and bounced in
the same day. Like NTAP, KLAC ... I want this list in one place under
chartmaps.. Sort them by nearest of the Demand zones again with 5% supply
zone. First you do the data analysis and get all the stocks that had same day
bounce or sometimes overnight down and gapped up on the morning ...
automating this with paper trade I think we will see more value for day
trading."

**Basis:** house Supply & Demand study, no book, no Minervini cites
(`feedback_sepa_book_scope`). Decision support, not advice.

Code: `backend/supply_demand/quick_bounce.py` (study + list rule),
`backend/chart_maps/board.py::quick_bounce_tiles` (the tab),
`backend/trading/zone_edge_entry.py` (`quick_bounce` lane tag + `quick_bounce_eod`),
`backend/crontab` (Sundays 07:00 ET), Mongo `quick_bounce_stats`.
Tests: `backend/tests/test_quick_bounce.py`, the two `quick_bounce` tests in
`backend/tests/test_chart_maps.py`, `frontend/src/lib/chartMaps.test.ts`,
`frontend/src/pages/ChartMaps.test.tsx`.

## 1. The event (daily closed bars)

Bands are recomputed at anchors every `ANCHOR_STEP_BARS` (21) using only the
bars up to the anchor — `sd_bounce.py`'s discipline, so a band never sees
the bars it is judged on. Only PROVEN demand bands count (touches ≥ 2,
strength ≥ 40 — `alert_gates.is_proven_band`, the same bar the room read
uses since 2026-09-06).

| term | rule | where the number comes from |
|---|---|---|
| touch day | day low ≤ band top × 1.01 and ≥ band floor × 0.985 | `zone_bounce_alerts.TOUCH_TOL_PCT` / `WICK_PCT` (his 🪃 rule) |
| episode | consecutive touch days of one band; one non-touch day still joins | one event per visit, so a name sitting in a band for a week counts once |
| **same_day** | the close lifts ≥ max(3 %, 1 ATR14) off the day's low | `zone_bounce_alerts.BOUNCE_MIN_PCT` + ATR (his 🪃 floor; NTAP 09-03) |
| **gap_up** | the next session opens ≥ 2 % above the touch-day close | `GAP_MIN_PCT` (builder default; KLAC 09-04 opened +2.9 %) |
| **quick** | same_day or gap_up on one of the first 3 touch days | `QUICK_MAX_TOUCH_DAYS` (builder default; KLAC turned on day 3) |
| slow | a close ≥ 2 % above the last touch-day close inside 5 bars, before a close 1 % under the floor | `sd_bounce` rules |
| failed | closed under the floor first / nothing inside the window | |

**Placebo:** the same quick-day test on EVERY day of the same windows — a
name's quick rate at demand only means something against how often it does
that anyway (a volatile name lifts 3 % off its low on many days).

**Persistence:** rank names by first-half quick rate, judge on the second
half (top vs bottom quartile, rank correlation). The 2026-08-14 bounce study
(`bounce_study.md`) found NO per-name persistence for 5-bar bounces; this
module re-asks it for same-day turns and prints the answer under the board.

## 2. The list (Chart Maps ▸ 🪃 Quick Bounce)

A name is on the list when its stats clear `MIN_EVENTS` (3) visits and
`MIN_QUICK_RATE_PCT` (50) — builder defaults — and it shows only while:

- the live print is INSIDE a proven demand band, or ≤ `NEAR_MAX_PCT` (5 %)
  above its top (`nearest_demand`; under the band = fell through, not listed);
- ≥ 5 % room to the first proven lid overhead (`alert_gates.room_gate`, the
  phone's rule; the Room ≥ 5 % / Any room toggle works like the demand boards).

Nearest to the band first (inside = 0), most room as the tie-break
(`order_key`). Each tile: quick n/N (%), first-day n/N, the name's own
any-day base rate, distance to the band, room → target, risk → stop
(0.5 % under the floor, the paper lane's stop), last quick date; the plan
line as the "why". The study strip under the blurb prints the universe
numbers and the persistence verdict.

No live print (a tape outage): the print falls back to the zone doc's
`prev_close` (the store's last closed bar). On a weekend the live snapshot
still carries Friday's last trade, so the list reads as it will at the open.

## 3. Paper Auto-Pilot — the `quick_bounce` day-trade variant

A demand-zone entry on a listed name is journaled as strategy
**`quick_bounce`** (same entry rules, same alert gate, same stop) and tick
step **(h2)** flattens whatever the lane bought today and still holds at
**15:55 ET** (`QB_EOD_FLATTEN_ET`, owner switch `quick_bounce_eod_flatten`,
default ON). Refused closes queue like any owner exit. The Journal's by-lane
table reports it next to `demand_zone`. See `zone_edge_autopilot.md` §3b.

## 4. Catalyst lane (same ask)

"for catalyst look at other rules like I established in the past Like >700
mil enterprise value and also, Sales are intact" → `catalyst_entry.size_gate`
(EV from the scan row, market cap when EV is unknown, ≥ $700M) and
`sales_gate` (Bonde pass tiers, cache-only in the tick, the warm cron
fetches; unknown fails closed). See `catalyst_entry.md`.

## 5. Results — first full run, 2026-09-06 (read-only, api container)

RESULTS_PLACEHOLDER

## 6. Traps

- Stats are rebuilt weekly; a new listing needs ~150 bars of history before
  it can produce an event (`MIN_HISTORY_BARS`).
- A name's `avg_dollar_vol_50` rides on the stats doc for the liquidity
  floor — stats written by an older module lack it and the tab's default
  tier hides them; rerun the study after a schema change.
- `nearest_demand` measures against PROVEN demand bands only; NTAP-style
  bounces off a 1-touch broken-supply shelf are the 🪃 alert's business, not
  this list's.
