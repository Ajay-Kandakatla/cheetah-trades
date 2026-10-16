# 🕯️ Doji Sweep study — PRE-REGISTRATION (2026-10-16)

**Status: PRE-REGISTERED, NOT RUN.** This file is written and committed BEFORE any outcome run. Nothing in it
changes after that commit; a change to any rule below needs a NEW prereg file, and a run made under this one is then
void.

- Script: `backend/scripts/doji_sweep_study.py` (the detector it replays: `backend/chart_maps/doji_sweep_tab.py`).
- Artifact: `backend/scripts/doji_sweep_measured.json` (copied byte for byte from the run's `--out`).
- Served literal: `backend/chart_maps/doji_sweep_measured.py` `MEASURED`, built by `measured_literal(art)` and pinned
  field for field to the artifact by `backend/tests/test_doji_sweep_study.py`. Until the run it is
  `{"state": "unmeasured"}` and the tab says UNMEASURED.
- An outcome run carries TWO identifiers: `--prereg-commit <hash>` (the commit holding this file) AND
  `--prereg-blob <git hash-object of this file>`. The blob survives the planned rebase; the commit hash does not. The
  literal pin re-hashes this file and must equal the artifact's `prereg_blob` — this file never changed after the run.
- The artifact also carries (AMENDMENTS6 B12) the git blob hashes of the script, the detector module and the measured
  module, the worktree HEAD, and whether `git status --porcelain` was empty. An outcome run REFUSES without a HEAD and
  a clean tree (the throwaway container holds no `.git`, so the launcher passes the host's `--git-head` and
  `--git-clean`), and REFUSES (exit 2) when this file is not on disk: the launcher MUST mount `docs/research`
  read-only at `/docs/research` (`-v <worktree>/docs/research:/docs/research:ro`); the run re-hashes this file
  against `--prereg-blob`. The `git` block serves its `source` (`GIT_KEYS`): "measured" (git read in-process) or
  "attested" (the launcher's flags) — an attested clean tree is never served as a measured one.

## 1. The ask (Ajay 2026-10-16, verbatim)

> "create me a new tab for Doji candle after a sweep. For any stocks after a down trend. May be from all chart maps
> especially on the 60% 70% down stocks"

K1, verbatim: "I heard but do some research and back test please on accuracy".
K4, verbatim: "Within 5% either side counts as a test".

## 2. What "accuracy" means here, in his words

How often a doji printed on a test of the prior low, in a downtrend, was followed by a reversal up — measured
against the SAME names' other days in the SAME downtrend, two ways:

- (a) the **confirmation rate**: a close above the doji's HIGH within `CONFIRM_SESSIONS` (5) sessions, before any
  close under its LOW;
- (b) what holding from the **next open** for `PRIMARY_H` (10) sessions returned — the **median** is the verdict
  statistic, the mean sits beside it before and after a `COST_ROUND_TRIP_PCT` (0.5%) round trip.

The **stop-out rate** (a close under the doji's low within the horizon) is always served beside both. A hit rate is
never served alone, never without its matched-day rate beside it, and never without its CI.

## 3. The prior is null (each is the source's claim, unverified by us)

- Bulkowski (*Encyclopedia of Candlestick Charts*, 2008; thepatternsite.com): the southern doji (a doji in a
  downtrend) is a bullish reversal 52% of the time, overall rank 78 of 103; the dragonfly doji — the shape a
  sweep-and-reclaim doji makes — reverses 50% of the time, rank 98 of 103; his verdict on doji: "near random".
- Marshall, Young & Rose (DJIA stocks 1992–2002, 500 bootstrap series): no candlestick rule significant after the
  bootstrap; the dragonfly doji's mean daily return −0.0001 (N = 270, not significant).
- Horton (2009), "Stars, crows, and doji": little value.
- George & Hwang (2004, *Journal of Finance*): names far from their 52-week high earn LOWER later returns — the 60–70%
  down cohort starts against the setup.
- No source tests "doji + sweep" as one rule; no source sets a 60–70% drawdown filter (that filter is his).
- In this app: the candle ledger never grades an "indecision" read; a shooting star near highs carried zero signal;
  every S&D reversal gate measured flat; the 🎢 High Beta primary measured no_signal.

## 4. Definitions (every constant by name — the study assigns none of the tab's)

The detector (`chart_maps/doji_sweep_tab.py`, "DJ"):

| name | value | source |
|---|---|---|
| `DOJI_BODY_PCT` | 0.05 (body STRICTLY under 5% of the day's range) | Cheetah default — `scalping/candles.DOJI_BODY_PCT`, imported (HIS CALL Q2) |
| `DOJI_BODY_WIDE_PCT` | 0.10 | Cheetah default (PivotBoss; Liberated Stock Trader) — the 10% switch and the study's second body |
| `SWEEP_REF_SESSIONS` | 20 — the reference low = the lowest low of the 20 sessions before the candle | Cheetah default (Connors & Raschke, *Street Smarts*, 1995 — Turtle Soup) |
| `SWEEP_REF_MIN_AGE` | 4 — that low printed at least 4 sessions before the candle; equal lows: the MOST RECENT sets the age (Q18) | Cheetah default (Connors & Raschke 1995) |
| `SWEEP_TEST_PCT` | 5.0 — the candle's low within ±5% of the reference low (either side) | **Ajay 2026-10-16** |
| `TEST_ROUND_DP` | 2 — the test and the depth reads compare the % rounded to 2 dp (AMENDMENTS6 B9) | MINE |
| `DOWN_PCT` | 60.0 — reads (a) and (b) qualify at ≥ 60% | **Ajay 2026-10-16** ("60% 70%") |
| `DEPTH_CHIPS` | (40, 60, 70) | **Ajay 2026-10-16** K3, from the 📉 tab's own steps |
| `SMA_FAST` / `SMA_SLOW` | 50 / 200 — read (c): the close under BOTH simple averages | **Ajay 2026-10-16** K3 |
| `YEAR_BARS` | 252 — the 52-week window and the minimum history | imported (`key_levels.YEAR_BARS`) |
| `SMALL_WICK_PCT` | 0.15 — dragonfly / gravestone shapes | imported (`patterns/candles_daily.py`) |
| `LONG_LEG_BARS` | 10 — long-legged = a range at least the prior 10 sessions' mean range | Cheetah default (TA-Lib) |
| `VOL_AVG_BARS` | 50 | imported (the house last-bar volume average) |
| `VOL_QUIET_X` / `VOL_HEAVY_X` | 1.0 / 1.5 × the 50-session average | MINE (Q9) / borrowed from `scalping/candles.py` (Q9) |
| `GLITCH_RATIO` | 5.0 — a one-session close move of 5× either way marks the 252-session window suspect | imported (`fallen_tab.GLITCH_RATIO`) |

The schema (`chart_maps/doji_sweep_measured.py`, "DSM"):

| name | value | source |
|---|---|---|
| `MIN_CELL_EVENTS` | 100 | MINE (HIS CALL Q10) |
| `MIN_CELL_DATES` | 30 | house — `scripts.explosive_study.MIN_BUCKET_N` |
| `BLOCK_SESSIONS` | 10 — the date-block length of the binding bootstrap | MINE (AMENDMENTS6 B2) |
| `VERDICT_CELLS` | (`primary`, `any_read`, `test_no_doji`) | AMENDMENTS6 B4 / B5 / B6 |
| `PREDECLARED_TOO_SMALL` | (`w52_70`) | AMENDMENTS6 B4 |

The study (`scripts/doji_sweep_study.py`, "S"):

| name | value | source |
|---|---|---|
| `HORIZONS` | (5, 10, 20) sessions | MINE (DECISIONS6 scope) |
| `PRIMARY_H` | 10 | MINE (HIS CALL Q17; Bulkowski's 10-day moves, MYR's 10-day hold) |
| `CONFIRM_SESSIONS` | 5 | MINE (DECISIONS6) |
| `PLACEBO_K` | 5 matched days per event | MINE |
| `PLACEBO_GAP` | 20 (= max `HORIZONS`) | derived (AMENDMENTS6 B1) |
| `DRAWS_DEFAULT` | 2000 bootstrap draws | MINE |
| `SEED_DEFAULT` | 20261016 | MINE |
| `COOLDOWN` | 10 (= `PRIMARY_H`) — the `independent` cell | MINE |
| `COST_ROUND_TRIP_PCT` | 0.5 — a sensitivity line, never the verdict | MINE (Lu, Chen & Hsu 2015 used 0.5%) |
| `CI_PCT` / `ALPHA` | 95 / 0.05 | imported (`scripts.resiliency_study.CI_PCT`) / derived |
| `LIQ_FLOOR_USD` | $10M/day on the 50-session mean $ volume through t | derived — `board.LIQ_TIERS[board.default_min_tier("doji_sweep")]` (Q6) |
| `OUTCOME_START` | 1 — outcomes read t+1 onward only | MINE (the leak rule) |

## 5. Data

- **Universe**: `demand_reentry._resolve_universe("full")` − the static ETF lists − `symbols.is_delisted` — TODAY's list
  (survivors-only).
- **Prices**: ONE `sepa.prices.bulk_cached_frames` read of the universe + SPY (a Mongo find, never a fetch).
  `--no-fetch` is the only mode; every `sepa.prices` fetcher in `NO_FETCH_FUNCS` raises in-process; the artifact
  serves `provider_calls` (must be 0).
- **The as-of day follows the tab (AMENDMENTS6 B11)**: a session counts only after the `KL.ROLL_AT` 20:00 ET roll —
  as-of = the last SPY session on or before `KL.prev_market_day(KL.levels_session(now))`; every frame is cut to bars
  dated ≤ as-of. (Never `RS.default_as_of`'s 16:30.)
- **The universe read never fetches (fix round 2, 2026-10-16)**: in the run's process `sepa.universe` reads every
  cached list WHATEVER ITS AGE (its 30-day TTL is lifted in-process; a list is never refetched) and its HTTP entry
  point and its two cache writers (`UNIVERSE_NO_FETCH_FUNCS`) raise and are counted in `provider_calls`. A list with
  no cache file at all is therefore a counted provider call: the run exits 3 and writes no artifact. The shared
  universe cache is never written.
- **The clock**: the run refuses 09:00–16:30 ET without `--force-window`; it runs in a THROWAWAY container on the live
  database.
- **Read-only (AMENDMENTS6 B18)**: before anything connects, every pymongo data write method raises (and is recorded);
  an index create is a recorded no-op. A run that recorded a data write or a provider call exits 3 and writes no
  artifact.
- **The all-time high, point-in-time (Q12)**: `DJ.ath_series` — with a usable `ath_history` doc (the 🏔️ read reports
  `doc_state` "ok" and the doc has no `cut_from`), a bar whose month is AFTER the stored high's month reads
  max(running high, stored high); every other bar reads the frame's running high (a lower bound — a name may be
  missed, never falsely included). The misses are not random: a name that LATER set a new all-time high (the later
  big runners) gets only the frame read, so it is under-included in the `ath` read and in `any_read`.
- **The liquidity floor**: `LIQ_FLOOR_USD` on the 50-session mean of close × volume through t (an unknown turnover
  fails it — `board.passes_liquidity`).
- **Held out**: a bar whose 252-session window holds a scale glitch is neither an event nor a placebo.

## 6. Events

Every (name, session t) with ≥ `YEAR_BARS` closed bars through t, a valid bar, not suspect. All events count (no
cooldown); the `independent` cell is the sensitivity. The detector is the tab's own: `DJ.frame_features` (every
column reads bars ≤ t) and `DJ.row_statuses` (the one classifier) — "fired" = a doji (body < 5% of the range), the
reference low readable and ≥ 4 sessions old, the low within ±5% of it, and at least one downtrend read met.

**The three pre-registered verdict cells** (AMENDMENTS6 B4 / B5 / B6; `DJ.study_cells` defines them):

1. `primary` — **his "60% 70%"**: fired at the 5% body, the floor passed, and ≥ 60% under the 52-week high (read (a)).
   10 sessions from the next open, **market-adjusted** (every outcome minus SPY's return over the identical window);
   the raw read beside it.
2. `any_read` — the tab's default view: fired at the 5% body, the floor passed, ANY downtrend read (≥ 60% under the
   52-week high · ≥ 60% under the all-time high · below the 50- and 200-day). Same horizon and statistic.
3. `test_no_doji` — **the doji's control** (B5): the same test of the prior low (the reference low ≥ 4 sessions old,
   the low within ±5%), the same floor, the same 52-week read as the primary, but a body of 10% of the range or more
   (no doji at either body) — against its OWN matched days. Its verdict says ONLY how tests without a doji did
   against their own matched days. **The primary and the control are compared as numbers only, never as an
   inference** — never "the test alone carries it", never "the doji adds". The reason (fix round 2, 2026-10-16): the
   control's own-pool rule (§7) empties or shortens the pool of names that keep testing, so the control reads a
   different set of names than the primary, and its matched days sit further from the low (the critic's count-only
   probe, §17). No "primary minus control" statistic is computed. Served beside the control: `n_detected`,
   `n_unmatched` and `placebo_short_pool` — the control's **unmatched share** (`n_unmatched` / `n_detected`) and its
   short-pool share are always served — and the exploratory sensitivity cell `test_no_doji_fire_pool` (§7).

## 7. Placebo (binding)

For each event, `PLACEBO_K` (5) sessions of the SAME name drawn from its pool. The pool = sessions s ≠ t that are
eligible, pass the floor (the `all_liquidity` cell: without the floor), carry the SAME read set (the exact
combination of the three reads; the code w52 = 1, ath = 2, mas = 4), are NOT a fired candle at the 10% body, have
`PRIMARY_H` sessions after them, and (AMENDMENTS6 B1) lie MORE than `PLACEBO_GAP` (20) sessions from t and NOT inside
the 20 sessions after any 10%-body fire of the same name. A pool of ≥ 5 → drawn without replacement; 1–4 → 5 drawn
with replacement, the event kept and counted in `placebo_short_pool`; 0 → the event is `n_unmatched` (counted, out of
the contrast). RNG `numpy.random.default_rng([SEED, symbol_index, t, floor_flag])` (symbol_index = the position in
the sorted universe). Placebos are drawn ONCE per (name, t, floor flag) and shared by every cell holding that event.

**The cells whose events are not 10%-body fires** (fix round 1, 2026-10-16 — B1 "a placebo inside another event's
window on the same name is never drawn"): `test_no_doji` (a body of 10%+ is never a fire), `undercut_deep`,
`doji_no_test` and `swing_sweep` (no test required) — the script's `OWN_POOL_CELLS`. The fire-based exclusions above
never remove these cells' own events, so their pool ALSO drops every one of the cell's own event sessions on the name
and the 20 (`PLACEBO_GAP`) sessions after each. Their draws are their own (never shared with another cell): RNG
`default_rng([SEED, symbol_index, t, floor_flag, 1 + the cell's index in CELLS])`. Every other cell's events are a
subset of the 10%-body fires (test-pinned), so the fire exclusions already cover them — except the sensitivity
below.

**The control's sensitivity (fix round 2, 2026-10-16)**: `test_no_doji_fire_pool` (the script's
`FIRE_POOL_SENSITIVITY`) holds exactly the `test_no_doji` events, with their matched days drawn from the PRIMARY's
pool rule — the fire-based exclusions above only, WITHOUT the control's own-event exclusion (so its pool may hold
other no-doji test days of the name, and it leaves no more events unmatched than the control). Its draws use the
shared stream `default_rng([SEED, symbol_index, t, floor_flag])`. It is exploratory — numbers only, never a verdict
word, never compared with the primary as a verdict — and sits LAST in `CELLS`, so no earlier cell's seed moves.

**Served for every cell**: `n_detected` (every detected event), `n_unmatched` (events with an empty pool, out of the
contrast) and `placebo_short_pool` (a pool of 1–4); the unmatched share = `n_unmatched` / `n_detected`.

## 8. Outcomes (identical rules on each day's own bar)

- R_h = close_{t+h} / open_{t+1} − 1 (%), h ∈ (5, 10, 20), every bar t+1..t+h present.
- Market-adjusted R_h = R_h − (SPY close on the exit day / SPY open on the entry day − 1) (%) — the identical window.
- Confirmation = the first j = 1..5 with close_{t+j} > high_t ("up") or close_{t+j} < low_t ("down"), else "neither";
  None when the 5-session window is incomplete.
- Stop-out_h = any close_{t+1..t+h} < low_t. MFE_h / MAE_h = the max high / min low of t+1..t+h vs open_{t+1}.
- Variant cells: `from_close` (entry at the doji close, R_h = close_{t+h} / close_t − 1); `confirm_entry` (only the
  events that confirmed "up"; entry at the confirming close j*, R_h = close_{j*+h} / close_{j*} − 1; their placebos
  conditioned the same way — a placebo that did not confirm on its own high is dropped).

## 9. Statistic and CIs (AMENDMENTS6 B2)

- Δmedian = median(event R_10) − median(placebo R_10) over the matched events and their placebos (an event with no
  finite placebo is out of the contrast).
- 95% percentile bootstrap, `DRAWS_DEFAULT` (2000) draws; the resampled unit is the event WITH its placebos.
  - **Binding axis — session blocks**: the SPY calendar cut into fixed `BLOCK_SESSIONS` (10)-session blocks; an
    event's cluster = its block (outcomes overlap for up to 10 sessions and events bunch on a date).
  - **Second axis — names**: an event's cluster = its symbol.
  - The naive per-date CI is reported beside them (`ci_date`), never used for a verdict.
- The same machinery for Δmean (block axis) and Δconfirm (0/1 × 100, block axis). Seeds:
  `default_rng([SEED, cell_index, axis_index, stat_index, horizon])`.
- p-value per axis = 2 × the smaller share of the bootstrap draws at or beyond zero on either side, capped at 1.

## 10. Verdict rules (fixed)

For the three verdict cells only (B6), read on the **market-adjusted Δmedian at 10 sessions**:

1. Every count a verdict reads is the **contrast set's** (fix round 1, 2026-10-16): the events with a finite
   market-adjusted R_10 AND at least one finite placebo — never the detection count (an event in the last 10
   sessions before as-of has no R_10; an unmatched event has no placebo). The served `n_events` / `n_dates` /
   `n_symbols` are those counts; the detection count is the count-only artifact's `n_events` and the outcome
   artifact's `n_detected`. n_events < `MIN_CELL_EVENTS` (100) or n_dates < `MIN_CELL_DATES` (30) →
   **too_small**; the name axis also reads its own cluster count: n_symbols < 30 (`MIN_BUCKET_N`) → **too_small**.
   The block axis is gated on the cell's sessions (n_dates). **No block-count floor applies** (fixed here, fix round
   2, 2026-10-16 — the stated default; Ajay may replace it only with a NEW prereg before the run): the block axis's
   own cluster count `n_blocks` (about 25 blocks of 10 sessions in a one-year window) is SERVED in every cell and in
   the literal's primary beside `n_detected`, and never gates a verdict. A reader sees how few blocks the binding
   CI resampled.
2. **Holm across the three** (those not too_small): the cell's p = the LARGER of its block-axis p and its name-axis p;
   Holm-adjusted p (`p_holm`) over the family; the cell ranked r (0 = smallest p) of m reads its CIs at the level
   100 − 5 / (m − r) % (served as `ci_pct`).
3. At that level, each axis reads separates (lower > 0) / inverted (upper < 0) / no_signal (a bound exactly 0 is
   no_signal — `RS.verdict`). **Both axes agree** → that word; they disagree → **axes_disagree** (worded "no verdict —
   the axes disagree").
4. A separates / inverted read whose `p_holm` > 0.05 (the step-down stopped at an earlier cell) → **no_signal**.

`robust` = the block-axis and the name-axis words agree. Every other cell is served as numbers with the label
"exploratory — no verdict" and NEVER a verdict word. `w52_70` (≥ 70% under the 52-week high) is pre-declared
**too small** (the critic's count-only probe: 69 events on 59 dates) and served with its count only.

What the words mean:

- **separates** — on this record the dojis returned more than the matched days of the same names in the same
  downtrend, on both axes, after the Holm correction. It describes the record, not what comes next.
- **no_signal** — no difference this study can separate from zero.
- **inverted** — on this record they returned less than the matched days.
- **too_small** — under 100 measured events, 30 sessions or 30 names; nothing is read from it.
- **axes_disagree** — the session-block CI and the by-name CI disagree: no verdict.

## 11. Cells (each with its definition string in the script's `CELL_DEFS`)

Verdict: `primary`, `any_read`, `test_no_doji`. Exploratory (numbers only; "the tab's view" = `any_read`, BUILD_SPEC6
§3.11.4's cells with its "primary" read as `any_read`):
`w52_40` / `w52_70` (any_read and ≥ 40% / ≥ 70% under the 52-week high — `w52_60` IS the primary), `ath_60`, `mas`,
`mas_only`, `doji10` (the any_read rule at the 10% body), `above` (low at or above the prior low), `undercut`,
`undercut_reclaimed`, `undercut_closed_under`, `undercut_deep` (a doji whose low sits MORE than 5% under the prior low —
outside his test), `swing_sweep` (a doji with a sell-side sweep of an smc swing low, window 3, lookback 60, read on a
slice ending at t — Q4), `dragonfly` / `gravestone` / `long_legged` / `plain`, `vol_quiet` / `vol_heavy`,
`doji_no_test` (a doji whose low sits more than 5% ABOVE the prior low), `independent` (one per name per 10
sessions, greedy in date order), `all_liquidity` (no floor, placebos without it), `from_close`, `confirm_entry`,
`test_no_doji_fire_pool` (the control's events against the primary's pool rule — §7, fix round 2).

## 12. Baselines (descriptive)

Per read (w52, ath, mas, any): every eligible floor-passing day with that read — n days, n dates, median and mean
R_10 from the next open. Never a verdict.

## 13. Stopping rules — no peeking

- ONE outcome run per prereg. `--limit` smokes and `--count-only` runs write COUNTS ONLY (no outcome key exists in
  their artifact) and need no prereg; they never write the real artifact path.
- The outcome run's knobs are pinned (final-critic fix 2026-10-16): it REFUSES (exit 2) a `--seed` other than
  `SEED_DEFAULT`, a `--draws` other than `DRAWS_DEFAULT`, any `--as-of`, and a SPY cache that ends before the tab's
  last closed session (`as_of_cut(now)`; that refusal spends nothing). The as-of is therefore always the tab's
  default for the run date. The literal pin (`pin_violations`) re-checks seed, draws, as-of against the run date
  (`as_of_cuts`), a committed clean tree and zero provider calls, so a re-run with other knobs can never be pasted.
- A crashed outcome run may be re-run with the SAME prereg. A completed outcome run is final: no parameter, cell,
  threshold or horizon changes after it without a new prereg.
- A run passing 60 minutes is stopped (`docker rm -f cheetah-tmp-doji-study`) and nothing from it is quoted.
- The count-only run is read for sanity only: `primary.n_events` under 100 or over 20,000 means an engine bug, not a
  result.

## 14. What the result may change

ONLY `doji_sweep_measured.MEASURED` → the served study line, the `measured` flag and the ℹ️ study line. The fire rule,
the order, the chips, the body default, the floor and the ledger stay as built whatever the verdict — any change is
HIS call (Q21).

## 15. Known limits (= the artifact's `limits`)

- Survivors-only: today's universe; deep-drawdown names that delisted are absent (absolute returns biased up; the
  same-name matched days only partly cancel it).
- The two-year cache gives about one year of evaluable sessions (a 252-session window first) — one market regime.
- Adjacent events' outcome windows overlap; the session-block and the by-name resampling keep them together, they do
  not remove the overlap.
- The all-time high before the stored high's month is the frame's running max — a lower bound; the misses follow
  later returns (a name that later set a new all-time high is under-included in `ath` and `any_read`).
- Next-open entries assume the open print; close-to-close daily bars, no intraday fill.
- The sizing probe says about 90% of his tests never undercut the prior low — the undercut cells are thin.

## 16. Choices made before any outcome (numbered)

1. Primary = his "60% 70%" (≥ 60% under the 52-week high) with the 5% body, his 5% test and the floor (B4); the tab's
   default view is the second verdict cell; the no-doji test is the third (B5).
2. Horizon 10 sessions from the next open (Q17); 5 and 20 beside it.
3. The median, not the mean; market-adjusted for the verdict, raw beside it (B2).
4. Session blocks of 10 bind; names are the second axis; both must agree (B2); Holm across the three (B6).
5. Exact read-set matching; no 10%-body fire and nothing within 20 sessions of the event or after a 10%-body fire in
   any placebo pool (B1); for the cells whose events are not fires (`test_no_doji`, `undercut_deep`, `doji_no_test`,
   `swing_sweep`), nothing on or within 20 sessions after one of the cell's own events either (fix round 1).
6. The most-recent-minimum tie rule for the reference low's age (Q18).
7. The smc swing-low read on a slice ending at t, never the full frame.
8. The all-time-high point-in-time rule (Q12).
9. `MIN_CELL_EVENTS` = 100 (Q10); `w52_70` pre-declared too small (B4).
10. The as-of day follows the tab's 20:00 ET roll (B11).
11. The verdict counts are the contrast set's (finite market-adjusted R_10 and a finite placebo), never the
   detection count; the name axis is gated on its own name count (fix round 1).
12. No block-count floor; `n_blocks` and `n_detected` served (fix round 2).
13. The primary and the control are compared as numbers only; the control's unmatched share is served; the
   `test_no_doji_fire_pool` sensitivity is exploratory (fix round 2).
14. The universe is read from the cached lists whatever their age, never fetched; a missing list is a counted
   provider call and voids the run (fix round 2).

## 17. The sizing probe (counts only, no outcome read)

Planner, 2026-10-16, a read-only mongosh over the first 600 `price_cache` docs: doji < 5% + low within ±5% of the
prior-20 low (≥ 4 sessions old) + (≥ 60% under the 252-bar high OR below both averages) = 791 candles on 260 dates
(≥ 60% under the 52-week high: 173; ≥ 70%: 116; below the averages: 778); only 82 undercut the prior low (61 closed
back above it). The spec critic's count-only probe (2,803 names, the $10M floor): 3,169 events on 253 dates; the ≥ 70%
cell 69 events on 59 dates. The WP-S critic's count-only probe (fix round 2, 400 random `price_cache` names, 338
evaluable, as-of 2026-10-15, the real pool rule, no outcome read): events with an EMPTY placebo pool — primary 1 of
21, any_read 15 of 217, test_no_doji 139 of 417 (71 more with a short pool); the control's pool days sat a median
7.32% above the 20-day low against 5.95% for the primary's (33.7% of them test days against 40.9%). Counts only —
nothing quotable.

## 18. The run

The launcher's `docker compose run` line carries `-v <worktree>/docs/research:/docs/research:ro` beside the
`backend:/app` and `/out` mounts (without it an outcome run refuses, exit 2). The launcher itself reads
`git -C <worktree> status --porcelain -- . ':!frontend/node_modules'` (the symlinked node_modules is always listed)
and passes `--git-clean` and `--git-head $(git rev-parse HEAD)` ONLY when that is empty; on a dirty tree it refuses
an outcome run and starts no container (a count-only run goes ahead without the flags).

```
bash <scratchpad>/doji/doji_study_run.sh --count-only --out /out/doji_sweep_counts.json
bash <scratchpad>/doji/doji_study_run.sh --prereg-commit <hash> --prereg-blob <blob>
```
