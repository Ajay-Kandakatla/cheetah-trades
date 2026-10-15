# 🎢 High Beta down-day study — PRE-REGISTRATION (2026-10-14)

**Status: PRE-REGISTERED, NOT RUN.** This file is committed BEFORE any outcome run. The commit hash
goes into the run as `--prereg-commit <hash>` and into the artifact. Any change to a rule below after
that commit needs a new prereg file and a new commit; the old run is then void.

Script: `backend/scripts/high_beta_study.py` · artifact: `backend/scripts/high_beta_measured.json` ·
served literal: `backend/chart_maps/high_beta_measured.py` (`MEASURED`, pinned field-for-field to the
artifact by `backend/tests/test_high_beta_study.py`; until the run it is `{"state": "unmeasured"}` and
the tab says UNMEASURED).

## The ask (Ajay 2026-10-14, verbatim)

> "Can you build me a category or filter for High Beta stocks in Resilient and make a scan there were all
> down today especially a qqq series. Can you please make sure you do a full scan. I wanna see whcih stock
> have high potential to bounce back aggressively.. I need a tape burst notification specific for High Beta
> stocks from the reselinet separately and also other tape bursts from the Chart Maps page"
>
> "I am rethinking the ask now, I think Resielient and high beta will not go hand in hand. Can you create a
> new tab for High Beta stocks"
>
> (down-today answer) "a lot of AI stocks are down like 5 to 10% today like NBIS, IREN. Yeah look at
> historically but today after the CPI it was all down"

"Look at historically" = this study. The tab ORDERS today's red High-Beta names by β × today's drop. The
study asks whether a High-Beta name that closed down hard does anything different over the next sessions
than a same-β name that did not. The served words stay "reversal", never the word in the ask.

**The prior is null.** Closest prior reads, all null or worse: green-on-a-red-day NO_SIGNAL (−0.30pp
[−0.76, +0.15]); 🛡️ T1 no_signal, T2 INVERTED; Hot Pullback +0.100R (CI spans 0); S&D reversal gates flat;
Turning Bullish KC / AMD INVERTED; ICT +0.03R.

## Definitions (every one imported, never retyped)

| name | value | source |
|---|---|---|
| β_d | cov/var of the 252 daily LOG returns ending d−1 against SPY, every pair present (no holes), 2 dp | `sepa.beta._beta` (== on a gap-free name, test-pinned); `high_beta_tab.BETA_LOOKBACK` |
| σ_d | sample stdev of the 50 daily % returns ending d−1, every one present | `resiliency_tab.sigma_pct` (== test-pinned); `high_beta_tab.SIGMA_BARS` (his 50-day σ) |
| `B15_MIN` | 1.5 | `high_beta_tab` (his number) |
| `B20_MIN` | 2.0 | `high_beta_tab` (his number) |
| `TOP_PCT` | 20 — that day's rated cross-section, k = ceil(n × 20 / 100), ties at the k-th β included | `high_beta_tab.categories` (his number) |
| cut | `DOWN_CHIP_PCT` = 5 — r_d ≤ −5.00% | `high_beta_tab` (his number) |
| `MIN_BUCKET_N` | 30 | `scripts.explosive_study` |
| strata / CI / verdict / clock / as-of helpers | `assign_cells`, `cell_contrast`, `pooled`, `ci_of`, `verdict`, `shuffle_lifts`, `refused_window`, `default_as_of`, `aligned` | `scripts.resiliency_study` |

Study-only parameters (MINE, fixed here — BUILD_SPEC §8): sessions **250** (`SESSIONS_MAX`), horizons
**1 / 3 / 5** sessions, primary **3**, draws **2000**, seed **20261014**, CI **95%** (2.5 / 97.5
percentiles), moving-block length **5** sessions, leave-out **5** sessions, label-shuffle draws **200**,
β **terciles** (3), σ **terciles** (3, the volatility check only).

## Data

- Universe: `demand_reentry._resolve_universe("full")` ∪ `universe.fetch_nasdaq100()` (a failed or empty
  Nasdaq-100 read is recorded in the artifact as `nasdaq100.available false`), minus the static ETF lists
  (`fallen_tab._static_etfs`) and delisted fates (`symbols.is_delisted`). **Survivors only**: this is
  TODAY's list — a name that left it is absent from both groups (stated in the artifact `limits` and in the
  served MEASURED line as "survivors-only cohort").
- Prices: ONE `sepa.prices.bulk_cached_frames(universe + SPY)`. Calendar = SPY's cached closed days; every
  name is aligned to it with NaN where it has no bar (no gap-bridging).
- **As-of rule:** the last SPY session in the cache dated before today (a today-dated bar counts only from
  16:30 ET — the cache patches today's bar hourly). `--as-of` overrides.
- **Clock rule:** refuses 09:00–16:30 ET on any day without `--force-window`. Runs in a THROWAWAY container
  (never the live api), read-only: every pymongo write method is a recorded no-op in-process; attempted
  writes are printed and stored.
- Sessions D: the last 250 SPY sessions with a full β window behind them (index ≥ 253) and 5 sessions after
  them. A 2-year cache (~502 bars) fits about 244; the artifact serves n.
- Tab build cost, measured 2026-10-14 22:1x ET in a THROWAWAY read-only container (`--cpus 2`, pymongo
  writes blocked; one `price_cache.create_index` attempt recorded as a no-op), closed mode, session
  2026-10-14: base half **8.1 s** (2,742 scanned = full + 2 Nasdaq-100-only names; 2,621 rated, 43 ETFs,
  75 short history, 3 stale; 601 listed: β ≥ 1.5 601 · β ≥ 2.0 354 · top 20% 528 at β ≥ 1.60; Nasdaq-100 read
  101 names from cache), live half **0.0 s** (closed mode reads no snapshot; 568 of 600 read red, 272 down
  5%+). The live-session snapshot over ~600 names is not timed here.

## Q1 — PRIMARY: after a red close of 5%+, do High-Beta names close differently over the next 3 sessions?

1. Rows (d, sym): β_d ≥ 1.5 and a close-to-close return r_d on d (both closes present).
2. Cohort R: r_d ≤ −5%. Placebo P (binding): the SAME session, β_d ≥ 1.5, the SAME β tercile, r_d > −5%.
3. Cells per d: β terciles of that day's R ∪ P rows (rank-based; ties broken by symbol).
4. Outcome Y_3 = close_{d+3} / close_d − 1 (%). A row missing any bar d..d+3 is dropped for that horizon.
5. Contrast_d = Σ_cells n_R (mean Y_R − mean Y_P) / Σ n_R over cells holding both groups; pooled =
   Σ_d num_d / Σ_d w_d (R-weighted).
6. **ALL sessions** (any SPY direction) — the primary (A13). "SPY-red days only" (SPY r_d < 0) is reported
   on the line beside it, never the verdict.
7. **CI (A6):** two-way resampling — per draw, session weights from a **moving-block bootstrap over
   sessions** (blocks of 5 consecutive sessions, ceil(n / 5) block starts uniform, cut to n) times symbol
   weights from an **iid bootstrap over symbols** (multinomial counts); row weight = the product; weighted
   cell means → the pooled contrast. ONE weight pair is shared by every series. 2000 draws, seed 20261014,
   95% percentile CI. The session-only (block) CI is reported beside it.

## Verdict rules (fixed)

- The CI read: the primary's two-way CI.
- sessions carrying a contrast < `MIN_BUCKET_N` (30), or no CI → **too_small**
- else CI lower > 0 → **separates**; CI upper < 0 → **inverted**; else → **no_signal** (a bound exactly 0
  is no_signal).

## Reported beside it (never the verdict)

- Y_1 and Y_5 contrasts (same rule, same weights).
- MFE_3 = max(high_{d+1..d+3}) / close_d − 1 and MAE_3 = min(low_{d+1..d+3}) / close_d − 1 contrasts. MFE is
  mechanically larger for volatile names — said in the artifact.
- The expectancy line: raw cohort and placebo mean Y_3; the cohort's mean MAE_3; the **drawdown line** —
  the share of R whose 3-session low printed a further 5% under close_d (a proxy: no stop exists in this
  read, so no stop-out rate exists).
- SPY-red days only; SPY-green days (SPY r_d > 0).
- β ≥ 2.0 rows; top-20% rows (that day's rated cross-section, every β, ties included).
- σ tercile × β tercile cells (the volatility confound check).
- **Leave-top-5-sessions-out:** the 5 sessions with the largest contribution num_d in the direction of the
  pooled sign are dropped and the contrast + two-way CI + verdict re-read.
- A label shuffle within (d × cell), 200 draws: the share of shuffled contrasts ≥ the observed one, their
  mean and 2.5–97.5 band.
- First vs second half of the sessions (date order).

## Leak rule

β and σ read returns ending d−1 (`FEATURE_END_OFFSET = 1`); the cohort reads d's close; outcomes read
d+1..d+k only. `check_no_leak` raises otherwise; a test moves the feature window onto d and watches the
build raise.

## What the result may change

Only the served study line on the 🎢 tab (`high_beta_measured.MEASURED` pasted from the artifact,
`high_beta_tab.study_block()` prints it) and the `measured` flag. The default order (β × today's drop),
every box, the two tape-burst kinds and every gate stay as built; changing any of them is HIS call.

## Known limits (stated in the artifact)

- Survivors-only cohort (today's list).
- Two-year price cache → about one year of sessions.
- 1/3/5-session windows of adjacent sessions overlap; the moving blocks keep runs together but do not
  remove the overlap.
- MFE is mechanically larger for volatile names.
- No stop exists: the drawdown line is a proxy.
- Close-to-close daily bars; no intraday entry is modelled.

## Choices made before any outcome

1. Primary = ALL sessions; SPY-red days only beside it (A13).
2. Placebo = same session, same β tercile, r_d > −cut (never a different day).
3. The two-way CI is a moving-block (5) × iid-symbol product of weights (A6); the session-only CI beside it.
4. β is rounded to 2 dp before the cuts, as the tab's `beta_from_frame` serves it.
5. A hole anywhere in a β / σ window = no β / σ that day (stricter than `sepa.beta._beta`, which inner-joins
   the name's own returns; identical on a gap-free name — test-pinned).
6. Leave-top-5 removes sessions by contribution in the direction of the pooled sign.
7. The clock refusal applies every day, weekends included.
