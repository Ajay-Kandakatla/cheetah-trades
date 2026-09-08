# Gap-day rule + touches-only lids (2026-09-08, Ajay: "ok push please")

Two alert-rule changes signed off the same afternoon. Both live in
`supply_demand/alert_gates.py` and reach every reader through it.

## 1. A lid is proven by touches alone

`is_proven_band` = `touches >= LID_MIN_TOUCHES (2)`. The strength half of the 2026-09-06
KLAC bar (`>= 40`, the board's `MIN_ZONE_STRENGTH`) is gone: FSLR's 2-touch shelves at
233–241 (strength 27) and 240.84–248.04 (35) were skipped and the push read "room +17.3% →
$250.99" while the chart drew them. Now the room from 214.04 reads **+8.9% → 233** (still over
the 5% gate). Unknown touches still keep the lid; a 1-touch shelf is still noise (KLAC), and the
wording still names it as the *weak lid* (`docs/supply_demand/room_weak_lids.md`).

Follows everywhere `is_proven_band` is read: `alert_gates.overhead_bands`,
`bounce_room.overhead_bands`, `portfolio.supply_watch.overhead_bands`, `room_floor.plan_bands`
(the card plan's target), `trading.zone_edge_entry.room_ok`, and the quick-bounce / lid-break
studies from their next weekly run (their stored params drop `lid_min_strength`).

## 2. Gap day: the shelves the gap fell through are trapped supply

`gap_day(print, prev_close)` = print `GAP_DOWN_PCT` (8%) or more under yesterday's close.
DYN 2026-09-08 (−29% pre-market) pushed "above demand" **four times** on the way back up from
17.2 — 18.99–19.61 and 19.90–20.03 are supply shelves, but the house rule *"a supply band
yesterday CLOSED above is broken = support"* was judged against a 24.28 close the gap had just
invalidated, and the room read ran over the same shelves to 23.96.

On a gap day:

- supply bands are **never support** — `zone_edge.read_near_demand` drops the broken-supply
  list, `zone_bounce_alerts.is_eligible(band, prev_close, print_px)` refuses them (the print is
  now passed in; without it the ordinary rule stands);
- the broken-supply skip is **off** in every overhead reader (`alert_gates.overhead_bands`,
  `bounce_room.overhead_bands`, `portfolio.supply_watch.overhead_bands`) — the shelves count
  for the 5% room gate and for the Portfolio 🎯 supply-ahead table.

Same-day replay (tests): DYN pushes **once**, at 09:09 (16.56–17.02, room +6.4% → 18.21). The
09:34 "in demand 18.21–18.43" now fails the gate (room +4.2% to 18.99); 11:19 and 11:44 never
read as demand. An ordinary −5% day keeps every old role (pinned).

The catalyst lane inherits both through `bounce_room` (`tests/test_catalyst_entry.py`: prev close
5.42 → broken = support → enters; 5.45 (−8.3%) → trapped → skipped on room).

## Where it shows

ℹ️ Rules panel ▸ proven-lid line: "tested ≥ 2× (touches only since 2026-09-08 — FSLR) … Gap day
(print ≥ 8% under yesterday's close, 2026-09-08 DYN): every shelf between the print and that
close is trapped supply — never support, always counted for room."

## Tests

`backend/tests/test_alert_gates.py`: touches-only bar (a weak 3-touch shelf is a lid; one touch is
not), the FSLR replay (+8.9% → 233, weak 1-touch shelf named), the gap clock (−8.03% yes, −7.95%
no, gap up no, garbage no), the DYN replay in `overhead_bands` / `room_gate` /
`zone_edge.read_near_demand` / `zone_bounce_alerts.is_eligible` / `bounce_room` /
`supply_watch` (standalone) with the ordinary-day NEGATIVE beside each;
`test_supply_demand_contracts.py`: no `LID_MIN_STRENGTH`, `GAP_DOWN_PCT == 8`, `gap_day(` in every
reader, `is_eligible(band, pc, print_px)` in the bounce read, the `and not gap` in supply_watch.
