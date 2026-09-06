# Proven lids — the room read skips bands that are not real structure

**Ask (Ajay 2026-09-06, after the KLAC bounce):** "ok please all 3" — (1) ignore
weak 1-touch lids in the room read, (2) put the buy zone / stop / room inside
the push text, (3) put-selling under the band floor in the options lane
(see `docs/trading_options_lane.md`).

**Basis:** house Supply & Demand rule, no book, no Minervini cites
(`feedback_sepa_book_scope`). Decision support, not advice.

## The KLAC lesson (2026-09-02..03, real bands from the zone store)

| band | range | touches | strength |
|---|---|---|---|
| demand (support) | 164.60–169.81 | 3 | 100 |
| supply lid A | 166.37–172.30 | 1 | 32 |
| supply lid B | 191.11–193.94 | 2 | 53 |

Sep 2, print 169.50 inside the demand band. The gate asked "how far to the
first ceiling?" and found lid A — the print was INSIDE it, room 0, state
IN_BAND. No push, no paper buy, two days running; Sep 4 gapped +7%. Lid A
was a one-touch, strength-32 band: the Back in Demand board itself refuses
to list a band under **2 touches / strength 40** (`demand_reentry.MIN_TOUCHES`
/ `MIN_ZONE_STRENGTH`), so the room read was trusting a ceiling the board
would never trust as a floor.

## The rule — `alert_gates.is_proven_band(band)`

A band counts as OVERHEAD only when `touches >= LID_MIN_TOUCHES (2)` AND
`strength >= LID_MIN_STRENGTH (40)`.

- touches missing / non-positive → **keep the lid** (nobody counted it; a
  legacy `{"lo": ...}` level still blocks — conservative);
- strength missing → judged on touches alone;
- both constants live in the leaf module and are pinned equal to the
  board's in `tests/test_supply_demand_contracts.py`.

KLAC now: lid A skipped, first proven lid = B at 191.11 → room 12.7% →
push + paper buy at 169.50, stop 163.78 (0.5% under the floor), ~3.8R.
The same lid with 2 touches / strength 53 still blocks (IN_BAND) — a real
ceiling right overhead is still a real ceiling.

## Where it applies (one bar, every reader)

| reader | surface |
|---|---|
| `alert_gates.overhead_bands` → `room_read` / `room_gate` | every zone push (🧲 🪃 🚀), the paper lanes' alert gate, the options lane |
| `bounce_room.overhead_bands` | SEPA 🪃 chip, Demand board sort, Catalysts room sort, `/supply-demand/bounce-room` |
| `portfolio.supply_watch.overhead_bands` | Portfolio 🎯 Supply-ahead table, `promo_live` room |
| `trading.zone_edge_entry.room_ok` | the 2R room check before a paper zone entry |
| `room_floor.plan_bands` → `room_block` / `demand_reentry.trade_plan` | the Back in Demand / Deep Demand plan target and room stat |

Boards still LIST every band — only the room measurement changed. The
Chart overlay is untouched.

## The plan inside the push — `alert_gates.plan_txt(print, band, room)`

🧲 (`demand_alerts.at_message`, which also serves zone_edge's near-demand
push) and 🪃 (`zone_bounce_alerts.single_message`) bodies end with:

`buy $164.6-169.81 · stop $163.78 (0.5% under the floor, 3.4% risk) · target $191.11 (3.8R)`

- stop = band floor × (1 − `STOP_BUFFER_PCT`/100) — the stop the paper lane
  places (`trading.zone_edge_entry.STOP_BUFFER_PCT`, pinned equal);
- risk % is measured from the PRINT (a fill here risks this much);
- target = the first proven lid; `target: clear runway` when nothing
  proven sits overhead; the R multiple is omitted when the target is
  under the print (stale room).
- Digest pushes (many names in one) keep one line per name, no plan.
- 🚀 breakout pushes are unchanged (no buy zone to quote).

## Tests

`tests/test_alert_gates.py` (truth table, KLAC regression, plan text),
`tests/test_bounce_room.py` (skip + supply_watch parity standalone),
`tests/test_zone_edge_entry.py` (room_ok), `tests/test_demand_reentry.py`
(plan_bands / room_block), push bodies in `tests/test_demand_alerts.py`,
`tests/test_zone_edge.py`, `tests/test_zone_bounce_alerts.py`; the contract
guard `test_proven_lid_rule_2026_09_06_one_bar_every_overhead_reader`.

## Trap

A 1-touch BROKEN-supply shelf can still be the band a 🪃 bounce is read
OFF (NTAP 2026-09-03: support = the reclaimed 161.78–167.54 shelf). The
proven rule is about what counts as a ceiling ABOVE the print; the touched
band itself is judged by `zone_bounce_alerts.is_eligible`, unchanged.
