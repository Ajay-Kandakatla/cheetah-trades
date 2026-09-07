# Last-lid break → prior high — does breaking the last resistance carry price to the old high?

Ajay, 2026-09-07: *"I would like to understand when the last resistance break will the
price go to ATH."*

Module: `backend/supply_demand/lid_break.py`. Weekly cron Sundays 07:30 ET (after the
quick-bounce study). Store: Mongo `lid_break_stats` (one row per name + `_meta`). Surface:
the 🚀 Breaking tab prints the pooled read under its pass line and each card a
"Lid breaks" stat. **A study board — nothing here changes a rule, a gate or a lane.**

## The question, made measurable (no lookahead)

- Anchors every 21 bars; supply bands recomputed on the bars **before** the anchor only
  (`price_zones.compute` with the demand board's `zone_geom`), exactly the quick-bounce
  study's scheme.
- **Last lid** = the highest valid supply band whose top sits above the anchor close — the
  last resistance in the lookback.
- **Event** = the first close through that lid's top in the next window (previous close at
  or under it). One per lid per window.
- **Prior high** = the 52-week high (max high of the 252 bars before the break).
  **Frame high** = the highest bar the 2-year frame holds before the break — the stand-in
  for the all-time high. The study says "frame high", never "ATH": the frame is 2 years.
- Outcomes from the break close: high reaches the prior 52-week high within 5 / 10 / 21 /
  63 sessions; reaches the frame high; best run-up in 21 / 63; a close back under the lid
  top within 21 sessions ("failed"); sessions to the high.
- A lid already at the 52-week high (top ≥ 99.5% of it) is the `at_52w` bucket: breaking it
  *is* the new high, so the 52w question is moot there (frame / run-up / fail still read).
- Splits: proven lid (`alert_gates.is_proven_band`, 2+ touches and strength ≥ 40) vs
  single-touch; volume-confirmed break (≥ 1.5× the 50-day average, `sepa.breakout`'s bar)
  vs not; distance from the lid top to the 52-week high at the event (≤5%, 5–15%, >15%).
- **Placebo:** from every day (and from every up-day, since a break day is an up-day by
  construction), does the high reach that day's own prior 52-week high within the same
  horizon. Every break rate is printed beside it.
- **Persistence:** names ranked on the first half of their events, judged on the second
  (`quick_bounce.persistence`, mapped onto the 21-session hit).

## Measured 2026-09-07 (first run, full universe = 2,650 names, 2-year daily frames)

| | value |
|---|---|
| names studied / with events | 2,597 / 2,138 |
| events (breaks of the last lid) | 6,393 |
| reached the prior 52-week high within 21 sessions | **57.5%** (n=3,967) vs placebo any-day 24.0% / up-day 26.4% |
| within 63 sessions | 75.9% (n=3,634) vs 44.2% / 46.8% |
| median sessions to get there | 2 |
| closed back under the lid within 21 sessions | **75.2%** |
| median best run-up | +7.5% in 21 · +13.1% in 63 |
| proven lid vs single-touch (21 sessions) | 57.6% (n=1,673) vs 57.5% (n=2,294) — **no difference** |
| volume-confirmed breaks | 56.7% (n=1,452) — **no edge** |
| by distance from the lid to the 52-week high | ≤5% away **89.6%** (n=1,835) · 5–15% away **51.8%** (n=856) · >15% away **15.3%** (n=1,276) |
| persistence (top vs bottom quartile, second half) | 71.6% vs 59.5%, gap 12.1 pts, rank corr 0.16 — weak |
| run time | 45.8 s |

### Read

- **Distance is the whole answer.** When the last lid sits within 5% of the old high, the
  break almost always prints the high (it is nearly the same level). Between 5% and 15%
  away it is a coin flip. More than 15% away, the break reaches the old high only 15% of
  the time within 21 sessions — a lid far below the high is one step, not the trip.
- **The touch is fast and does not hold.** Median 2 sessions to the high, but three of
  four breaks close back under the lid within 21 sessions. The break-day pop is the edge;
  the hold is not.
- **Proven vs single-touch, volume-confirmed vs not: no separation** for this question.
  The lid's quality predicts the bounce read elsewhere, not the carry to the high.
- Per-name rates persist weakly (rank correlation 0.16); read a name's own count as
  colour, not a forecast.

## Caveats

- 2-year frames → the "ATH" is the frame high; a name with a 2019 high above the frame is
  not measured against it.
- Event-weighted rates: one name with many lids counts many times.
- The ≤5% bucket includes lids that *are* the 52-week high area minus a hair; the
  `at_52w` bucket (top ≥ 99.5% of the high) is excluded from the 52w rates.
- Placebo is per-day, not per-break-day; the up-day placebo is the fairer bar.
- Re-runs weekly; numbers above are the first run and will drift.

## Tests

`backend/tests/test_lid_break.py`: last-lid selection, prior-high exclusion, reach/unresolved
tail, distance buckets, outcome (hit / run-up / fail / at-52w moot), placebo (flat tape, run
at the end, up-day filter), one name end-to-end (break to the high, failed break, single-touch
split, volume confirmation, no lid → no event, short history skipped, bands computed on prior
bars only), the pooled run + persistence + save/load, the card text, the cron line.
Frontend: `chartMaps.test.ts` (`lidBreakStudyText`), `ChartMaps.test.tsx` (the line under the
pass line), contract "Breaking tab prints the last-lid-break study".
