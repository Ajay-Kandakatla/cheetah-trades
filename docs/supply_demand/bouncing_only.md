# 🧲 Bouncing only — falling-into-demand pushes are off

Ajay 2026-09-09, after CASY: *"Turn off falling in to deman alerts all together.
only bouncing off alerts."*

Code: `supply_demand/alert_gates.py` — `PUSH_DIRECTIONS`, `direction_gate()`.
Applied in `supply_demand/demand_alerts.py` (the 5-minute board pass) and
`supply_demand/zone_edge.py` (the per-minute near-demand pass).

## What happened

| time (ET) | |
|---|---|
| **Tue 9/8, after the close** | CASY reports earnings |
| **Wed 9/9 08:13:02** | 🧲 *"CASY ↓ falling into demand $627.49–651"* · $646 · **buy $627.49–651 · stop $624.35 · target $678.67** |
| **Wed 9/9 08:15:01** | 🎪 *"PRE CASY −11.9% — tagged by @topstockalerts … the tag IS the promotion — do not chase"* |
| **Wed 9/9 morning** | prints **$604.51** — 3% through the stop |

Two pushes, two minutes apart, opposite conclusions. The zone board had no idea
CASY had reported: `earnings_calendar` holds 3,127 symbols and **no CASY row**.

The demand alert was not wrong by its own rules — at $646.00 the room to the
3-touch lid at $678.67 was 5.06%, just over the 5% floor. It was wrong because a
demand band under a post-earnings repricing is a line on a chart.

## The rule now

```
PUSH_DIRECTIONS = ("bouncing",)
```

`approach_read` classifies six approaches. Only **bouncing** — the day's low
touched the band and the print is ≥0.5% off that low — reaches the phone.

| approach | board | phone |
|---|---|---|
| **bouncing** — low touched the band, price already turning | ✅ | ✅ |
| falling into — the print IS the day's low | ✅ | ❌ |
| settling into — between the low and yesterday's close | ✅ | ❌ |
| reclaiming — a run UP into the band from underneath | ✅ | ❌ |
| resting in / lifting off | ✅ | ❌ |

**Nothing is removed from the boards.** They still list every arrival with its
direction chip. Only the push is gated, and the skip is counted as
`skipped_direction` in both passes' status, so `/alerts` can say why the phone
is quiet rather than leaving it a mystery.

**It fails closed.** No approach, a null `dir`, a non-string `dir` — all read as
"not a bounce". There is no evidence of a turn, so there is no push.

**It reads `dir`, never the arrow `tag`.** `approach_read` returns both
(`dir='bouncing'`, `tag='↑ bouncing off'`), and matching the tag is exactly how
the premarket-entry reclaim drag silently failed earlier the same day. A test
pins the field.

## Why this is a tightening, not a preference

It matches the 2026-09-08 autopsy of his own 286 pushes:

- reclaims from below were **40% of pushes** and **66% of them hit the floor stop**;
- same-day arrivals on a −3..−8% day closed above the print only **22%** of the time;
- same-day demand alerts overall were a coin flip (52% up).

A bounce is the only approach where price has already turned. Everything else
asks him to catch it.

**Expect a much quieter phone.** Of the 240 demand pushes since the direction
read shipped on 2026-09-08, only **5 said "bouncing"** — though 64% came from
the zone-edge path, whose title never carried the word, so the true bouncing
share is higher than 2% and is not knowable from the history. The live
`skipped_direction` counter is the honest measure from here.

## Tests

`backend/tests/test_alert_gates.py` — the constant; every non-bouncing direction
blocked; fails closed on None/{}/null/blank/non-string; reads `dir` not `tag`;
case-folded; and a round trip through the real `approach_read` including **the
exact CASY shape**, asserting that push can never fire again.

`backend/tests/test_demand_alerts.py` and `test_zone_edge.py` — the board still
lists a falling arrival while the phone stays silent, `skipped_direction`
counts it, and every push-intent fixture was converted to a bounce (`_bounce`,
`_live_bouncing`) so those tests keep testing caps, dedupe, digests and mood
rather than accidentally re-testing this gate.

## Still open

The earnings gap that let CASY through: no `earnings_calendar` row, so nothing
knew it had reported. Proposed but **not** shipped — suppressing a demand plan
when a name reported inside 48h is a methodology change and wants measuring
first.
