# 🛡️ Resiliency persistence study — PRE-REGISTRATION (2026-09-30)

**Status: PRE-REGISTERED, NOT RUN.** This file is committed BEFORE any outcome run. The commit hash
goes into the run as `--prereg-commit <hash>` and into the artifact. Any change to a rule below after
that commit needs a new prereg file and a new commit; the old run is then void.

Script: `backend/scripts/resiliency_study.py` · artifact: `backend/scripts/resiliency_measured.json` ·
served literal: `backend/chart_maps/resiliency_measured.py` (`MEASURED`, pinned field-for-field to the
artifact by `backend/tests/test_resiliency_study.py`).

## The ask (Ajay 2026-09-30, verbatim)

> "Can you build me a new tab- Resileincy.
>
> This is to help me with
> #1 - Stocks that are not going to by more than 0.5% during a T1 event like FOMC or any others like todays Inflation and GDP track T2s as well.
> #3 - Tape is positive and bullish EOD or Pre market. but volume has to be accounted for. We have all of this data already."

The tab SHOWS which names held on past data days. The study asks whether that says anything about the
NEXT data day. **The prior is null**: the closest prior read, green-on-a-red-day (2026-09-28, branch
only), measured NO_SIGNAL (−0.30pp vs same-day red twins at 10 sessions, CI [−0.76, +0.15]).

## Definitions (every one imported, never retyped)

| name | value | source |
|---|---|---|
| held | event-day return (prior session close → event close) ≥ −`HOLD_MAX_DROP_PCT` | `resiliency_tab.held` |
| `HOLD_MAX_DROP_PCT` | 0.5 | `resiliency_tab` (his number; down-only = his call #1) |
| `HOLD_WINDOW_DAYS` | 365 | `resiliency_tab` (his call #4) |
| `HOLD_RATE_MIN_PCT` | 75.0 | `resiliency_tab` (his call #5) |
| `T2_EXCLUDES_T1_DAYS` | True | `resiliency_tab` (his call #7) |
| the 🛡️ box (label R) | `box_pass(tier_stats(...))` — a close on every window session AND held/n ≥ 75% | `resiliency_tab` |
| σ | `sigma_pct`, sample stdev of the last `VOL_AVG_BARS` = 50 daily % returns | `resiliency_tab` |
| β | `beta`, cov/var of the last `BETA_BARS` = 252 daily returns vs `BENCH` = SPY | `resiliency_tab` |
| event sessions | `event_sessions` over `macro_calendar.past_events` (FRED release dates + FOMC calendar) | `resiliency_tab`, `macro_calendar` |
| accumulation day | `sepa.volume.accumulation_day` — up close, close ≥ 50% of range, volume > the 50-session average | `sepa.volume` |
| `MIN_BUCKET_N` | 30 | `scripts.explosive_study` |

Study-only parameters (fixed here): draws **2000**, seed **20260930**, CI **95%** (2.5 / 97.5
percentiles), label-shuffle draws **200**, σ **quintiles** (5), β **terciles** (3).

## Data

- Prices: ONE `sepa.prices.bulk_cached_frames(universe + SPY)`; universe =
  `demand_reentry._resolve_universe("full")`. Closes ≤ as-of only. Days = SPY's own cached calendar;
  a name with no bar on a day has no return there (no gap-bridging).
- Events: `macro_calendar.past_events(first SPY bar, as-of)`; the list used is written into the
  artifact (`events_used`) and can be replayed with `--events-json`.
- **As-of rule:** the last SPY session in the cache dated before today (a today-dated bar counts only
  from 16:30 ET, because the cache patches today's bar hourly). `--as-of` overrides.
- **Clock rule:** the script refuses to run 09:00–16:30 ET on any day without `--force-window`. The
  outcome run happens outside that window, detached, in the api container, read-only (every pymongo
  write method is a recorded no-op in-process; the attempted writes are printed and stored).

## Q1 — PRIMARY: does the T1 box persist? (walk-forward, out of sample by construction)

1. Test events E = T1 sessions whose date minus 365 days is on or after the first cached SPY bar.
2. At each E, per name: window = the T1 sessions in **[E − 365 days, E)** — E itself never
   (`check_no_leak` raises otherwise; a test mutates the window and watches it fail). Label R =
   `box_pass(tier_stats(window))` is True; control C = `box_pass` is False (rated, not in the box);
   `None` (unrated) is dropped.
3. Outcome Y = `held(return on E)` (0/1, reported ×100 as pp). A name with no return on E is dropped.
4. Covariates at E: σ over the 50 returns before E, β over the 252 returns before E; a name missing
   either is dropped.
5. Strata per E: σ quintile × β tercile of that day's remaining cross-section (rank-based; ties broken
   by symbol) = 15 cells.
6. Lift_E = Σ_cells n_R · (mean Y_R − mean Y_C) / Σ n_R, over cells holding BOTH groups (a cell with no
   control or no R contributes nothing). Pooled lift = Σ_E numerators / Σ_E weights (R-weighted).
7. CI: bootstrap over event dates — resample the events that carry a stratified contrast, with
   replacement, 2000 draws, seed 20260930. **One index matrix is shared by every series below**, so
   every difference uses the same resampled dates.
8. Also reported (none of these changes the verdict): the stratified lift of step 6 + CI; raw
   (unstratified) lift + CI (shows the low-volatility confound); share of R rows in the lowest σ quintile; the stratified event-day RETURN
   difference in pp + CI (the expectancy line); first half vs second half of the events (date order),
   each with its own lift and CI.

## P1 — placebo (ordinary days) — THE VERDICT READS THIS CONTRAST

Same labels and cells, Y measured on the **first trading day after E that is neither a T1 nor a T2
session**. Event-specific lift = lift(E) − lift(P1), CI from the SAME resampled event dates. **The Q1/Q2
verdict is read on this event-specific CI, not on the stratified lift** (see Verdict rules).

Why (critic, 2026-09-30, before this prereg was committed): σ quintile × β tercile does not remove the
low-volatility confound. On a synthetic universe with NO persistence (800 names, iid returns, holding set only
by σ and β, 52 T1 events) the stratified lift "separated" in 3 of 3 seeds (+5.78pp [4.26, 7.77], +3.36pp
[1.61, 5.26], +2.17pp [0.91, 3.52]) while the placebo lift was as large and the event-specific CI spanned 0
every time. A quiet-name trait holds on ordinary days too; only the contrast against them is an event read.
`backend/tests/test_resiliency_study.py` pins that null to `no_signal` (through `run_study`, and over 30
seeded nulls: never `separates`).

## Q2 — T2

Q1 exactly, on T2-only sessions (a session with any T1 print is T1 only).

## Q3 — EOD tape vs volume-unconfirmed twins

- Rows: every name × session d with ≥ 51 prior bars (the 50-bar average + the prior close), a next
  session in the cache, and a σ over the 50 returns before d.
- Cohort: up close vs the prior close AND close in the upper half of the range (h > l).
- R = `accumulation_day(...)` (volume > the mean volume of the 50 sessions before d); C = the same two
  price legs on volume ≤ that average ("volume-unconfirmed twins").
- Y = next-session close→close %; also next-session open→close %.
- Strata: σ quintile within d. Lift per d as in Q1; pooled R-weighted; bootstrap over d (2000 draws,
  same seed).
- Placebo: R shuffled WITHIN each d × σ cell, 200 draws; `placebo_pct` = % of shuffled lifts ≥ the
  observed lift; the shuffled mean and 2.5–97.5 band are reported.
- Reported beside it: R and C mean next-session return and share of next sessions up. **No stop exists
  in this read, so there is no stop-out rate** — the next-session return is the expectancy line.

## Q4 — pre-market

`{"verdict": "unmeasured", "reason": "pre-market volume history is the intraday cache: ≤31 sessions,
patchy — too short to measure"}`. Not run.

## Verdict rules (fixed)

- The CI read: Q1/Q2 = the **event-specific** CI (lift(E) − lift(P1), same resampled dates); Q3 = the
  stratified lift's CI (Q3 has its own label-shuffle placebo).
- clusters (events with a stratified contrast for Q1/Q2; days for Q3) < `MIN_BUCKET_N` (30), or no CI →
  **too_small**
- else CI lower > 0 → **separates**; CI upper < 0 → **inverted**; else → **no_signal**
  (a bound exactly at 0 is no_signal).
- Q1/Q2 `specific`: the verdict `separates` → **event_specific**; else the stratified lift's CI lower > 0 →
  **general** (the names also hold more on ordinary days — a trait, not an event read); else → **unclear**.
  `too_small` → `unclear`.

## What the result may change

Only the served sentence: `resiliency_measured.MEASURED` is pasted from the artifact and
`resiliency_tab.study_block()` prints it in the box notes and the tab note. No gate, threshold, sort,
push or lane changes on any verdict — each of those stays HIS call.

## Known limits (stated in the artifact)

- Survivorship: today's universe; names that left it are absent from both groups.
- Two-year price cache → about one year of test events (the first year only labels).
- FRED revision dates (e.g. retail sales 2026-09-28, GDP 2024-10-02) count as event sessions, as the
  tab counts them (his call #9).
- ISM and Fed-speaker remarks have no dated source and are absent from T2.
- T2 is about half weekly jobless-claims Thursdays.
- Pre-market (Q4) is not measured.

## Choices the spec left open (made here, before any outcome)

1. The bootstrap resamples only the events (days) that carry a stratified contrast; every other series
   (placebo, raw, return difference) is read over those same clusters.
2. Quantile ties are broken by symbol, so the cells are deterministic.
3. Q3's σ uses the 50 returns BEFORE d (d's own up move is excluded); Q3 bars are aligned to SPY's
   calendar, so a name with a hole inside the 50-bar window has no row that day (stricter than
   `momentum_burst.avg_volume_before`, which skips holes; identical on a gap-free name — test-pinned).
4. The clock refusal applies on every day, weekends included (the conservative reading).
5. `general` vs `unclear` as defined above.
6. (Fix round 2026-09-30, before the commit) the Q1/Q2 verdict reads the event-specific contrast, not the
   stratified lift — the synthetic null above.
