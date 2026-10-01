# 🧱 Zone-pad study — pre-registration (2026-09-30)

Script: `backend/scripts/zone_pad_study_2026_09_30.py` · tests: `backend/tests/test_zone_pad_study.py` ·
results: `backend/scripts/zone_pad_measured.json` (written by the run) → the `MEASURED` literal in
`backend/supply_demand/zone_pad_measured.py` → `verdict_line()` on the ℹ️ Rules panel (🧱 Pad).
The rule being measured: `docs/supply_demand/zone_pad_2026_09_30.md`.

§1–§4 were written **before any outcome was computed** (including the smoke run) and are not
edited after a run. Results go in §5 only.

## 0. The ask, verbatim

Ajay, 2026-09-30:

> "Also increase our Demand zone and key levels sizes by 1%. becuz Generally we are missing this, I
> been noticing if the demand zone or key level is 133, it holding at 132. My theory is MMs know
> stoplosses are beyond 133."

His theory makes a testable claim: **price that pierces a demand floor or a support low by less than
1% reverses more often than chance would put it there**, so a stop placed under a 1% pad survives
the pierce and still catches the move. The prior on this is NULL-to-negative: the 2026-09-09 stop-hunt
study found swept floors (pierced and reclaimed) win 22.7% vs 30.7% for untouched floors, Δwin
−2.37pp CI[−3.76,−1.01] (`docs/supply_demand/stop_hunt.md`). The ≤1% sweep subset was never reported
on its own — that is his case.

## 1. Questions (pre-registered)

Every threshold is an imported house constant: the pad = `sd_liquidity.STOP_SHELF_PCT` (1.0),
pierce = `SWEEP_MIN_PIERCE_PCT` (0.15), cooldown / reclaim window = `RECLAIM_MAX_BARS` (12),
reversal = `alert_gates.ALERT_MIN_ROOM_PCT` (5.0), touch tolerance = `APPROACH_TOUCH_TOL_PCT` (1.0),
stop buffer = `STOP_BUFFER_PCT` (0.5), clock = `bounce_quality_study.HOLD_SESSIONS` (20), clocks
`BQ.CLOCKS` (5/10/20/60), minimum cell `entry_trigger_study.MIN_CELL_N` (120), key-level touch
`key_levels.AT_LEVEL_PCT`. Three numbers come from the spec itself: kept falling = 3 pads under,
≤ 50 placebo draws per event, quotable only with ≥ 100 dates.

**Q1 — his observation, zones.** Touch = the first bar j where `close[j−1] > hi` and
`low[j] ≤ hi × 1.01` for a drawn demand band (board geometry `demand_reentry.zone_geom()`, bands from
`bars[j−252:j]`, any `demand_pad_pct` key stripped), cooldown 12 bars per band (2-dp identity); all
bands, and proven-only (touches ≥ `LID_MIN_TOUCHES`). Two windows that never overlap: U = deepest low
under the drawn lo over the **depth window** j … j + 12 (`RECLAIM_MAX_BARS`), bucketed: held (< 0.15%),
**[0.15%, pad)**, [pad, 2 pads), [2, 3 pads), ≥ 3 pads. Then, on the 20 bars **after** the depth window
only: **reversed** = a high ≥ close[j] × 1.05; **kept falling** = a close < lo × (1 − 3 × pad) (same bar
as a reversal high → kept falling); else the clock. A reversal or a fall inside the depth window is not
an outcome (see the amendment below). Report (a) the bucket shares of reversals,
(b) per bucket P(reversed) / P(kept falling) / P(clock), (c) the same on placebo levels, (d) real −
placebo for P(reversed | [0.15%, pad)) and for the [0.15%, pad) share of reversals, date-clustered 95% CI.

**Q2 — the pad vs today (PRIMARY).** Cohort A = today's phone chain minus knife/mood: proximity,
approach = a reversal read (internal dir "bouncing"), room ≥ 5%, one event per symbol-date, highest
floor wins (`bounce_quality_study`'s rule). Same events, same entry (close[j]) and target (the room
target); stop_A = lo × (1 − 0.5%), stop_B = pad-floor × (1 − 0.5%), pad-floor = round(lo × (1 − pad), 2);
stop checked before target inside a bar. Paired B − A: stop-out rate, win rate, mean R (each arm its
own R), median R, mean % at each clock. **PRIMARY = DiD: (B − A mean % at 20 on real bands) − (the
same on matched placebo levels)**, date-clustered 95% CI, on the real events that have an accepted
placebo. Plus **B_new** = events only the pad chain admits (print in [pad-floor, lo)), their stats with
stop_B vs cohort A with stop_B. The "approach-flip" events (pad chain admits, print ≥ lo, because a
prior close inside the pad is no longer "from below") are counted, not analysed.

**Q2 sub-cohort A_held (added 2026-09-30, before any full run).** A_held = cohort A where
`alert_gates.floor_held_gate` passes on the DRAWN floor (15-bar sweep window ending at the event bar;
`FLOOR_HELD_STATES`; the pad's HIS CALL #1 `PAD_FLOOR_HELD = False` keeps the gate on the drawn floor).
Every demand push path runs this gate, so A_held is the population the phone actually sends; cohort A
alone measures the wider stop on events the phone never pushes. A_held gets the same paired B − A
table (win, stop-out, mean R, median R, mean % at each clock) and its own DiD against the placebo pairs
of its own events, date-clustered 95% CI. It is reported beside the primary; it does NOT change the
primary or the verdict rule (§4) — which of the two decides is HIS CALL. The cap floor is still not
applied to either cohort. The emulation of arm B and the A_held gate are pinned equal to the branch
engine in `backend/tests/test_zone_pad_study_pin.py`.

**Q3 — key levels.** Support tests of the board's lows (`key_levels.BOARD_PERIODS` = prior week /
prior month / 52 weeks × `BOARD_KINDS` = lows), vectorized from closed bars and pinned equal to
`key_levels.period_levels` in a test: prior close > L and low ≤ L × (1 + AT_LEVEL_PCT). One event per
symbol-date (the highest L tested), cooldown 12 bars per level. Depth buckets and the two windows as
Q1 (depth over j … j + 12, reversed / kept falling scored only after it); reclaim = a close
≥ L at or after a pierce within 12 bars; forward % at every clock; reversed / kept falling as Q1;
real − placebo. **Q3b suppressed sells:** the first close within 20 sessions that breaks L by ≥ 0.15%
(today's 🔑 close-through) but NOT the padded edge round(L × (1 − pad), 4) by ≥ 0.15% — the sell the
pad silences. Share that closed back ≥ L within 12 bars vs share that later broke the padded edge within
20, and the extra % lost at that later padded close vs the raw signal close (date-clustered CI + placebo).

**Amendment 2026-10-01 (Q1 and Q3 buckets — before any full run; Q2, the primary and the verdict rule
are untouched).** The first text measured U "from j to resolution". That fixes the per-bucket outcome
rates by construction: "kept falling" needs a close under 3 pads, so every fall landed in ≥ 3 pads, and
the shallow buckets could only read reversed / clock — the round-2 critic's 6-name smoke (numbers never
quoted) showed the shallow buckets pinned and the real − placebo contrast on [0.15%, pad) a degenerate
zero-width interval on Q1 and Q3. His observation could not separate from placebo whatever the data
said. The fix closes the depth window (12 bars,
`RECLAIM_MAX_BARS`, the house reclaim window) BEFORE the outcome is scored. `tests/test_zone_pad_study.py`
pins it: a pierce-to-pad event can now keep falling and a ≥ 3-pad event can reverse; a synthetic world
where his observation is true separates from placebo (CI above 0); one where it is false does not (CI
spans 0), and a worse-than-placebo world reads below 0.

**Q4 — the floor-held flip (HIS CALL #1).** On cohort A (no floor gate), `alert_gates.sweep_read` over
the 15-bar window ending at the event bar, on the drawn floor vs on the pad floor. **Rescued** = swept
or broken on the drawn floor AND intact on the pad floor. Win / stop-out / mean % (stop_B) rescued vs
drawn-intact, date-clustered CI, plus a size-matched date-block placebo band on cohort A.

## 2. Arms and data

Runs on `origin/main` inside the api container (read-only: Mongo bars cache via
`bounce_quality_study._frame` + `explosive_study`'s tail hygiene, `zone_store.load_latest()` for the
universe; no provider calls, no writes). Arm A = the main-code gates on drawn bands (on the branch,
`level_pad.DEMAND_PAD_PCT` is set to 0 for the run). Arm B is emulated from the one number:
B-proximity `pad-floor ≤ px ≤ hi × 1.01`; B-approach = `approach_read` on the band with lo = pad-floor;
B-room = `room_gate` with the entry band removed by identity (never its own ceiling). The main session
pins emulation == branch engine (`tests/test_zone_pad_study_pin.py`).

Universe `store` (the names the live alerts see) by default; `--universe full` optional. Window: every
bar with ≥ 252 prior bars and the 60-session clock after it.

## 3. Placebo and statistics

**Placebo — a random level, matched.** For each real event (date d, gap g = (close[j−1] − hi)/close[j−1],
height h = (hi − lo)/lo), draw another name with a bar on d (seeded per event, ≤ 50 draws):
hi' = close'[j'−1] × (1 − g), lo' = hi'/(1 + h), both at the 2-dp band grain; accept only if the real
event's own entry test holds on d — the Q1 touch for Q1; the Q1 touch plus proximity plus a reversal
read for Q2 (target = entry' × (1 + the real event's room %)); for key levels L' = close'[j'−1] × (1 − g)
with the Q3 touch. g ≤ 0, no touch, or a NaN bar → rejected. The acceptance rate is reported.

**Intervals** resample WHOLE DATES (5,000 draws, `explosive_study.cluster_boot` over the union of the two
cohorts' dates); a placebo row carries its real event's date, so the DiD resample is paired by date.
Win rate is never shown without the stop-out rate and expectancy beside it, and nothing is ranked on
win rate.

## 4. Verdict rule (pre-registered)

- **supports** if the Q2 DiD 95% CI lower bound > 0; **inverted** if its upper bound < 0; else
  **no_signal**.
- **Quotable** only if the real and placebo pair counts are each ≥ 120 (`MIN_CELL_N`) and the DiD spans
  ≥ 100 dates. Any secondary cell under 120 prints "not shown". `--emit-measured` REFUSES to write the
  `MEASURED` literal for an unquotable run, so the panel keeps saying UNMEASURED.
- Q1, Q3, Q3b and Q4 are descriptive: they say where the reversals sit and what the pad silences; they
  do not change the verdict.
- A smoke run (`--limit-names`) is never quoted.

## 5. Results

**Pending.** The full run is for after 20:00 ET (never during RTH, never while a deploy is pending).
The main session pastes the emitted `MEASURED` literal into `zone_pad_measured.py` and quotes the verdict
line here, verbatim, with its CI.

Pipeline check, 2026-09-30 10:10 ET: a 50-name smoke (`--limit-names 50`) ran end to end in 15 s in a
throwaway read-only container. All four stages ran, the placebo accepted matches for every question and
the stats printed. **Its numbers are not quoted anywhere.**

Full run (outside RTH), touching nothing inside the live container:

```bash
docker run --rm --cpus 4 --memory 1.5g --network cheetah-market-app_default -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 -v /Users/ajay/clinet-test/wt-zonepad/backend:/app:ro -v /tmp/zp_out:/out -w /out cheetah-api:latest python -u /app/scripts/zone_pad_study_2026_09_30.py --stage all --events /out/zp_events.csv --kl /out/zp_kl.csv --placebo /out/zp_placebo.csv --stats-json /out/zp_stats.json --measured-out /out/zone_pad_measured.json --emit-measured
cp /tmp/zp_out/zone_pad_measured.json /Users/ajay/clinet-test/wt-zonepad/backend/scripts/
```
