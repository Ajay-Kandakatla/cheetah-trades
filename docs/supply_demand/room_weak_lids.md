# Room wording names the weak lid the rule dropped (2026-09-08)

Ajay, FSLR 12:10 ET push: *"room +17.3% → $250.99"* while the 1-year Support chart drew
overhead at 214.0–216.72 (+0.4%), then shelves at 227, 233 and 241. *"Do we really have that
much room? If so are the time frames different?"*

## Why the two disagreed

- **Structure**: the push reads the zone store (2-year frame, board geometry, merged bands);
  the Support tab reads its own window (1 year here) with finer geometry. The store's one
  demand band 214.0–221.62 (6 touches) is the chart's two bands 214.0–216.72 and
  219.02–221.62. At the 12:10 print of 214.04 the band CONTAINED the print (support); at the
  chart's 213.13 the same shelf sat just above it (overhead). Four cents flipped the label.
- **Room**: `alert_gates.overhead_bands` counts only PROVEN lids (touches ≥ 2 AND strength ≥ 40
  — the KLAC bar, Ajay 2026-09-06). FSLR's 233–241 (2×, strength 27), 240.84–248.04 (2×, 35)
  and 248.66–249 (2×, 31) all failed it, so the first proven lid was 250.99–252.52 (3×, 47).
  The chart draws every band, 1-touch included.

Both were right by their rules. The push simply did not say what it had skipped.

## The change (wording only — no gate moved)

`alert_gates.first_weak_lid(bands, print, target)` = the first band above the print and
under the proven target that fails `is_proven_band`. `room_read` carries it as `weak`;
`room_txt` appends *"· weak lid $233 first (+8.9%, 2×)"*; `room_floor.room_block` carries it
for the boards and `room_stat` prints *"+17.3% -> 250.99 · weak 233.00 first"*. With nothing
weak in between, every string is byte-identical to before (pinned).

The 5% room gate, the ≥2-touch / strength ≥ 40 bar and the geometry are unchanged. Two rule
options are on the table for Ajay's call, not made:

1. room bar = touches only (drop the strength ≥ 40 half): FSLR's room would read +8.9% → 233
   (still passes 5%); DYN's 20.91–21.65 (1×) would still be ignored.
2. gap-day trapped supply (from DYN −29%): bands between the print and yesterday's close are
   overhead today — never "demand", and they count for the room gate.

## Tests

`backend/tests/test_alert_gates.py`: the FSLR bands reproduce the 17.3% read with `weak`
233.0 (+8.9%, 2×) and the gate unchanged; a 1-touch lid is weak; NEGATIVE — nothing weak,
weak above the target, weak below the print, garbage bands, and the pinned wording without a
weak key all unchanged; the board block + stat.
