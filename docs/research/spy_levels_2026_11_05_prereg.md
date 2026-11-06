# 📐 SPY levels study: pre-registration (2026-11-05, frozen before the OOS read)

Written 2026-11-05 23:46 ET, after the fetch, smoke and IS stages and BEFORE stage 3 (the one OOS read). Every value below is frozen. Any edit to this file after its sha256 is written to `backend/scripts/spy_levels_prereg.sha256` means a new sha and a new commit BEFORE the outcome run; the script refuses (rc 3) when the two differ.

## The ask (verbatim)

Ajay 2026-11-05: "can you also setup SPY calls and shorts please based on Supply demand and previous day high and lows and improved strategy with some resarch and bake that in to Auto pilot I wanna check it out"

The owner typed no number in this ask. Every number below is imported from a house file by name, typed in the design (`design.md`, cited by section), or labelled MINE.

Study question: on SPY intraday, do LONG/SHORT entries keyed to (a) the house S&D FINE index bands and (b) the previous session's high/low (PDH/PDL), cross vs touch-and-reverse, stop at the signal bar's extreme, target = next level / 2R / none, inside the 0DTE lane's RTH window, show positive expectancy after costs OOS against size-matched placebos, with DSR over every variant? Which ONE rule (if any) a PAPER Auto-Pilot lane would trade. Long and short separately and pooled.

This study is the first edge claim on the strip's bands: `docs/supply_demand/index_zones.md:220-221` says the strip "gates nothing, alerts nothing, orders nothing, enters no lane and claims **no edge**". Nothing in this study changes a rule, gate, lane or push; no lane is built in this pass.

## Script

- `backend/scripts/spy_levels_study_2026_11_05.py`, sha256 **`b49006694ce1995152648a74c0327e6fc977030db6244568760fb55e4a030731`** (the file as committed with this prereg; it includes the one-retry fix in `fetch_history` and the "at signal bars, per variant-row" scale label, both from the audit).
- Tests: `backend/tests/test_spy_levels_study_2026_11_05.py` (test_12 pins this file's sha against the sha file).
- The script never imports `trading.*`; the 0DTE lane's window constants are re-typed and pinned by test 10.

## Sources

- Published anchors already in the house: `daytrading/signals/orb.py:1-18` (Crabel 1990 / Raschke 1995); `vwap_reversion.py:1-13` (Steenbarger / Bellafiore); Zarattini & Aziz 2023, SSRN 4416622 (5-minute ORB on QQQ/TQQQ, stop at the opposite side of the range, EOD exit, zero slippage; an MQL5 replication: gross reproduces, net about zero after costs); Zarattini, Barbon & Aziz 2024 (SFI 24-98); Zarattini & Aziz 2023, SSRN 4631351 (VWAP long-above / short-below, QQQ 2018-2023).
- The often-quoted "10R" and "10 %-ATR" figures were NOT confirmed from the publisher pages: **unverified, not used**.
- `eod-audits/research/QUEUE.md` "Not queued": ORB / VWAP evidence = one author group, short samples, zero slippage; ORB and ICT measured null here before; SPY intraday momentum compressed since 2024. Memory `cheetah_ict_tab`: ICT board = no edge over its own placebo. **Prior on this signal: null.**

## The stop rule and why (file:line)

- Stop = the 5-minute SIGNAL BAR's extreme: LONG `stop = L`, SHORT `stop = H`.
  - `daytrading/signal_lab.py:161` `stop = sw["wick"]`; `:162-163` `if entry <= stop: continue`; `:174-179` the short mirror (the 0DTE lane's own signal module).
  - `chart_maps/luk/constants.py:108` `LUK_STOP_ALTS = ("breakout_bar_low", "prev_bar_low")`; `chart_maps/gajjala/constants.py:64` "stop = prior bar's low".
  - Entry at or beyond the stop → skipped, counted `entry_beyond_stop` (`signal_lab.py:162`).
- What forced it (the critique's read-only probe `probe_ranges.py`, 2026-11-05, on `price_cache` SPY 500 rows and `intraday_cache` SPY 151 sessions): day range % median 0.871 / p25 0.613; sessions with range < 1.2 % = 71.8 %; < 0.6 % = 22.8 %; daily ATR14 % median 1.048; from a 09:45 entry ±1.2 % reached before 15:45 on 11/151 (7 %), ±2.4 % on 1/151. A band-width stop (≥ 1.2 %) never rings on SPY; the stop must live on the 5-minute scale.
- Not run (each would be a new family): an ATR buffer below the signal bar (`ict/engine.py:85` `STOP_BUFFER_ATR`), a minimum stop, ORB's tighter-of rule (`orb.py:7`, its ATR is on 1-minute bars).

## Levels

- **PDHL** = LINES (`lo == hi`, no half-width): `indicators.session_high_low(prev_doc, "rth")` (`daytrading/indicators.py:159-166`) on the previous session's cached 1-minute doc. The daily bar never enters a PDH/PDL trade. Previous session = the nearest earlier weekday with a non-empty doc whose RTH rows are non-empty; a half-day may serve; more than `PREV_SESSION_MAX_GAP_DAYS = 4` calendar days back (design §3.1) → excluded `prev_session_gap`.
- **FINE** = the strip's FINE bands: `zone_store.build_doc("SPY", daily5y, d, compute=index_zones._fine_compute)` (`index_zones.py:672-682`, `zone_store.py:187-255`) = `price_zones.compute(frame, max_zones=None)` with the module defaults `SWING_WINDOW = 4`, `ZONE_MERGE_PCT = 1.75`, `ZONE_HALF_WIDTH_PCT = 0.6`, `LOOKBACK_BARS = 252` (`price_zones.py:25-28`), `zone_store.MIN_BARS = 120` (`zone_store.py:91`); rows dated before d only (`drop_today`).
- **Overlap union rule** (FINE only; no number): sort by `lo`; two bands overlap when `b.lo <= cur.hi` (touching counts); overlapping bands become ONE band `{lo: min, hi: max, kind: "merged"}`; non-overlapping bands pass through untouched. No `ZONE_MERGE_PCT` across kinds. The edges of overlapping bands are merged for the trigger; the strip's list is unchanged.

## The 24 variants (frozen)

Family = source {pdhl, fine} × mode {cross, touch_reverse} × target {next_or_flatten, 2R, flatten_only} × vwap {off, on}. Trial ids T02…T25 in this order.

| # | trial | variant key | source | mode | target | vwap |
|---|---|---|---|---|---|---|
| 1 | T02 | `pdhl\|cross\|next_or_flatten\|vwap_off` | pdhl | cross | next_or_flatten | off |
| 2 | T03 | `pdhl\|cross\|next_or_flatten\|vwap_on` | pdhl | cross | next_or_flatten | on |
| 3 | T04 | `pdhl\|cross\|2R\|vwap_off` | pdhl | cross | 2R | off |
| 4 | T05 | `pdhl\|cross\|2R\|vwap_on` | pdhl | cross | 2R | on |
| 5 | T06 | `pdhl\|cross\|flatten_only\|vwap_off` | pdhl | cross | flatten_only | off |
| 6 | T07 | `pdhl\|cross\|flatten_only\|vwap_on` | pdhl | cross | flatten_only | on |
| 7 | T08 | `pdhl\|touch_reverse\|next_or_flatten\|vwap_off` | pdhl | touch_reverse | next_or_flatten | off |
| 8 | T09 | `pdhl\|touch_reverse\|next_or_flatten\|vwap_on` | pdhl | touch_reverse | next_or_flatten | on |
| 9 | T10 | `pdhl\|touch_reverse\|2R\|vwap_off` | pdhl | touch_reverse | 2R | off |
| 10 | T11 | `pdhl\|touch_reverse\|2R\|vwap_on` | pdhl | touch_reverse | 2R | on |
| 11 | T12 | `pdhl\|touch_reverse\|flatten_only\|vwap_off` | pdhl | touch_reverse | flatten_only | off |
| 12 | T13 | `pdhl\|touch_reverse\|flatten_only\|vwap_on` | pdhl | touch_reverse | flatten_only | on |
| 13 | T14 | `fine\|cross\|next_or_flatten\|vwap_off` | fine | cross | next_or_flatten | off |
| 14 | T15 | `fine\|cross\|next_or_flatten\|vwap_on` | fine | cross | next_or_flatten | on |
| 15 | T16 | `fine\|cross\|2R\|vwap_off` | fine | cross | 2R | off |
| 16 | T17 | `fine\|cross\|2R\|vwap_on` | fine | cross | 2R | on |
| 17 | T18 | `fine\|cross\|flatten_only\|vwap_off` | fine | cross | flatten_only | off |
| 18 | T19 | `fine\|cross\|flatten_only\|vwap_on` | fine | cross | flatten_only | on |
| 19 | T20 | `fine\|touch_reverse\|next_or_flatten\|vwap_off` | fine | touch_reverse | next_or_flatten | off |
| 20 | T21 | `fine\|touch_reverse\|next_or_flatten\|vwap_on` | fine | touch_reverse | next_or_flatten | on |
| 21 | T22 | `fine\|touch_reverse\|2R\|vwap_off` | fine | touch_reverse | 2R | off |
| 22 | T23 | `fine\|touch_reverse\|2R\|vwap_on` | fine | touch_reverse | 2R | on |
| 23 | T24 | `fine\|touch_reverse\|flatten_only\|vwap_off` | fine | touch_reverse | flatten_only | off |
| 24 | T25 | `fine\|touch_reverse\|flatten_only\|vwap_on` | fine | touch_reverse | flatten_only | on |

Definitions (on 5-minute closed bars; `c_prev` = the previous 5-minute close; the first bar has none):

- `cross` LONG: `c_prev <= B.hi` and `c > B.hi`. SHORT: `c_prev >= B.lo` and `c < B.lo`.
- `touch_reverse` LONG: `c_prev > B.hi` and `L <= B.hi` and `c > B.hi`. SHORT: `c_prev < B.lo` and `H >= B.lo` and `c < B.lo`.
- `vwap_on`: LONG also needs `c > vwap`, SHORT `c < vwap`, `indicators.vwap_session(day1m, "rth")` read at the signal bar's last minute (`t_close − 1 min`).
- Several bands firing on one bar, same side → the band whose fired side is nearest to `c` (MINE tie rule), counted `multi_band_same_bar`. Both sides on one bar → the bar is skipped, counted `both_sides_same_bar` (impossible under `cross`, pinned by a test).
- `next_or_flatten` = the nearest same-source (merged) level strictly beyond the entry in the trade's direction; none → the trade is KEPT with no target (flatten), counted `no_next_level`, reported as a `fallback` sub-block.
- `2R` = `entry + side × TARGET_R × |entry − stop|`.
- `flatten_only` = no target.

Every value and its source:

| value | frozen as | source |
|---|---|---|
| symbol | SPY | the ask |
| bar | 5-minute closed bars, `timeframes.resample_ohlcv(rth1m, "5min")` (left-closed, right-labelled) | `BAR_MINUTES = 5` design §2; the house resampler `timeframes.py:266-293` (Gajjala's 5-minute frame) |
| entry | the open of the 1-minute bar labelled `t_close` (first later minute if missing); none before `FLATTEN_ET` → skipped `no_entry_bar` | design §3.4 |
| entry window | `ENTRY_OPEN_ET = 09:45` <= t_entry < `LAST_ENTRY_ET = 14:30` | `trading/zero_dte_lane.py:54-55`, re-typed, pinned (test 10) |
| flatten | `FLATTEN_ET = 15:45`, exit at that bar's open | `trading/zero_dte_lane.py:56`, re-typed, pinned |
| one trade per session | the first eligible signal; later ones counted `signals_skipped_same_day` | the 0DTE lane's one entry per name per day |
| stop | signal bar L (long) / H (short) | `signal_lab.py:161/174`; `luk/constants.py:108` |
| 2R | `TARGET_R = 2.0` | `daytrading/signal_lab.py:40` (imported; "uncited convention") |
| exit walk | bars `j >= i` from the fill minute; stop before target; same-minute both → STOP | `ict/backtest.py:35` (house tie rule) |
| PDHL gap | `PREV_SESSION_MAX_GAP_DAYS = 4` | design §3.1 |
| FINE geometry | 4 / 1.75 / 0.6 / 252 / `zone_store.MIN_BARS = 120` | `price_zones.py:25-28`, `zone_store.py:91` (imported) |
| ATR (diagnostic only) | `indicators.atr(bars5, period=14)` | `indicators.py:53-62` default (imported) |
| costs | `COST_BPS = 1.0` bp of the fill + `SLIP_USD = 0.01` per share, per SIDE | MINE (task-given; per-side reading = HIS CALL #9) |
| suspect daily row | `SUSPECT_DAILY_PCT = 1.0` % beyond the RTH print, or `prices._is_scale_glitch` | MINE |
| fetch pace | `FETCH_PAUSE_SEC = 1.0` | MINE (≤ 60 Massive calls/min) |
| B2 window | `PLACEBO_WINDOW_MIN = 30` | MINE |
| placebo exclusion | `PLACEBO_EXCL_MIN = 3` = `SIGNAL_MAX_AGE_SEC // 60` (180 s) | `trading/zero_dte_lane.py:57`, re-typed, pinned |
| B2 thin | `B2_THIN_N = 5` candidates (reported, still scored) | design §3.6 |
| duplicate trials | `DUP_RHO = 0.95` | MINE (the critic's threshold) |
| bootstrap | `BOOT_DRAWS = 10_000`, `SEED = 20261029` (B1 `SEED + 1`, B2 `SEED + 2`) | `strategy_lab_2026_10_29.py:140,160` (imported) |
| placebo sets / beat share | `PLACEBO_SETS = 1_000`, `PLACEBO_BEAT_SHARE = 0.95` | `strategy_lab_2026_10_29.py:141-142` (imported) |
| DSR pass | `DSR_PASS = 0.95` | `strategy_lab_2026_10_29.py:143` (imported) |
| TOO SMALL | `MIN_CLUSTERS = 30` entry-weeks | `strategy_lab_2026_10_29.py:121` (imported) |
| glitch share | `GLITCH_VERDICT_MAX_SHARE = 0.05` | `strategy_lab_2026_10_29.py:155` (the lab's rule as is) |
| options overlay | delta `TARGET_DELTA = 0.35` and `OVERLAY_DELTA_ATM = 0.50` | `options/zero_dte.py:92` (imported); 0.50 = design §3.6 (task) |

## Cost model

Per side: 1 bp of the fill price + $0.01 per share. `gross_pct = side × (exit − entry)/entry × 100`; `net_pct = gross_pct − 2 × (COST_BPS/100 + SLIP_USD/entry × 100)`; `net_r = net_usd / |entry − stop|`. `net_pct` is the gated unit; `net_r` is reported beside it. `breakeven_cost_bps` is reported. Gross is never quoted as the result.

## Cohort and split (RULES, not values)

- `as_of` = the last ET session strictly before the run's ET date → 2026-11-04. `from_day = as_of − PERIOD_DAYS["2y"]` (`prices.py:51`) → 2024-11-04 = the request window.
- `cohort_first` = the first weekday in `[from_day, as_of]` with a non-empty cached doc, MEASURED in the fetch stage: **2024-11-04** (`out/fetch/stats.json`). Fetch stage: requested 523 · cached before 151 · fetched 350 · failed 1 (`fetch_failed = ["2026-01-05"]`, one Massive read timeout; the old `fetch_history` slept the cooldown but never retried).
- Split = the CALENDAR weekdays of `[cohort_first, as_of]` in halves: `IS = W[:len(W)//2]`, `OOS = W[len(W)//2:]`; boundary = `OOS[0]` = **2025-11-04**.
- Usable trade session (every exclusion listed with its reason): weekday; not in `timeframes.HALF_DAYS`; not in `market_hours.reminder.ALL_HOLIDAYS`; cached doc present; the 5-minute RTH frame has every label 09:35 … 16:00 ET (no hole); FINE: `build_doc` returned bands; a previous session exists (above). IS: 261 weekdays, 246 usable.
- Daily bars (FINE only): `prices.closed_daily_frame("SPY", period="5y", use_cache=False)` once in the fetch stage → `data/spy_daily_5y.csv` (1253 rows 2021-11-08 → 2026-11-04; price_cache mismatches 0 of 501; suspect rows 0). Suspect rows are not removed from the FINE frame; OOS trades whose 252-row window contains one are `n_flagged`.

## The seal

- **IS 2024-11-04 … 2025-11-03: READ** (stage 2, `out/is/`, run 2026-11-05 23:32 ET; "attempted fetches [] · recorded puts 0").
- **OOS 2025-11-04 … 2026-11-04: SEALED, read ONCE** by stage 3 (`--mode outcome`), which reads all 24 variants on the OOS half in one run and never again. The script refuses a second run (an existing `<out>/stats.json` → rc 3).
- What touched OOS-dated bars before this prereg, stated plainly (no variant rule was scored on any of them): the fetch stage's cache accounting and its daily-vs-RTH high/low diff (n 501, max 0.419 %); the fidelity check on the 6 strip days 2026-10-29 … 2026-11-05 (6/6 index_zones, 6/6 zone_store); and the critique's scale probe above (151 sessions 2026-04-01 … 2026-11-04: day ranges and the ±1.2 % / ±2.4 % reach from 09:45). The probe's numbers are what moved the stop to the signal bar; they are scale, not a variant outcome.
- 2026-01-05 (OOS) has no cached doc. With the retry now in `fetch_history`, a re-run of the fetch stage would retry it once; if the fetch stage is not re-run before stage 3, the outcome lists 2026-01-05 as excluded `no_doc`. Either way the usability rule above decides; nothing is filled in by hand.

## Judgement: A + B + C

The strategy lab's definition, pasted unchanged from `LAB.POSITIVE_TEXT`:

> ## POSITIVE (exact definition, all three required)
> A. **OOS expectancy.** Split by calendar time: the last third of the available sessions is the test set, sealed until design is frozen and the prereg doc is committed. On test-set trades only: mean net return per trade (after the cost model) > 0, and the 95% bootstrap CI excludes 0. The bootstrap resamples **whole entry weeks** (clustered; trades opened the same week are not independent), 10,000 draws, percentile CI. Report beside it: win rate, stop-out rate, median trade, top-1% share of total return (tail check).
> B. **Placebo fails to reproduce.** For each test-set trade, draw a random entry date for the SAME name within the same calendar month that the strategy was eligible to trade (passes the same liquidity floor), apply the SAME holding/exit rule and costs; 1,000 placebo sets. The strategy passes only if (strategy minus placebo-mean) per-trade expectancy has a clustered 95% CI excluding 0 AND the strategy beats >= 95% of the placebo sets. A placebo that is also positive means the return is market/name beta, not the rule.
> C. **Deflated Sharpe Ratio >= 0.95**, with N = every variant tried in this lab across ALL candidates (not per candidate), using the per-trade (or per-rebalance) return series' skew and kurtosis; PSR (benchmark SR 0) reported beside it. The trial count is written in the prereg log before each run; it never resets.
> Anything short of A+B+C = not positive. A pass on survivor-biased data is labelled provisional.

Deviations for this study (stated, frozen):

1. **Split** = calendar-weekday HALVES (not the last third): the OOS half is 2025-11-04 … 2026-11-04.
2. **A clusters** = whole entry DATES (one trade per session per variant), `cluster_mean_ci(net_frac, dates, draws=10_000, seed=SEED)`; pass = mean > 0 and the 95 % CI excludes 0 (`word == "separates"`). **TOO SMALL** runs on distinct entry-WEEKS (`LAB._week_monday`) below `MIN_CLUSTERS = 30`; MDE on weekly means.
3. **B = two placebos, pass = BOTH.** Same date, same side, same `stop_dist` / `target_dist` / flatten, the SAME exit engine (`candidate_outcomes`), costs as above:
   - B1 (whole window): every entry minute in `[09:45, 14:30)`, excluding `|m − t_entry| < 3` min.
   - B2 (holding-time matched): `[t_entry − 30, t_entry + 30]` ∩ the window, same exclusion; < 5 candidates → `b2_thin`, still scored.
   - Each: 1,000 sets, one random candidate minute per trade; `beat_share = mean(strategy_mean > set_mean)`; `diff = net − pool_mean` → `cluster_mean_ci(diff, dates)`. Pass = `word == "separates"` and `beat_share >= 0.95`.
4. **C = DSR over the EFFECTIVE trial list.** `x = gate_c_series(trades, "per_entry_day")`; `deflated(x, prior + effective)` → `sr0, dsr, N`; pass = `dsr >= 0.95`. ALSO `deflated(x, prior + all 24)` → `dsr_naive` (reported, not gated). PSR(0) beside it.
5. **Glitch rule** as the lab's: `positive_verdict(A, B, C, n_weeks, a_clean, b_clean, n_flagged, n_rows)`; > 5 % flagged → `UNMEASURED-glitch`.

Verdict words: `POSITIVE | NOT POSITIVE | TOO SMALL | UNMEASURED-glitch`, per variant and per side.

## Trial counter N

- **Narrative N = 39** = 15 prior (LEDGER.md) + 24 this study. It never resets (HIS CALL #6 on the counting).
- **SRs fed to DSR** = the 5 prior SRs that exist (T01 `sr_per_entry_day` 0.05062907476117 from `strategy_lab_ledger.json`; the gates study's G1 −0.3576889839813701, G2 −0.38937424723195746, G3 −0.4212988477256451, G4 −0.5453635618098126 from `gajjala_gates_2026_10_30/results.json`) + ONE SR per duplicate cluster of the 24 variants.
- **Effective clusters**: per-variant OOS date series `s_v[d] = net_pct` of v's trade on d (0 on a usable OOS date without a trade); Pearson ρ over the OOS date axis; greedy clustering in family order (a variant joins the first representative with `|ρ| > DUP_RHO = 0.95`, else opens a cluster); the fed SR = the representative's. The cluster count is measured in stage 3 and printed beside 24 (`N.effective_variants`, `variant_corr.csv`).

## The pick (pre-registered, mechanical)

**Rule: among variants whose pooled IS block has >= 30 IS entry-weeks, the highest LOWER bound of the IS 95 % CI of `net_pct`; ties → family order; none qualifies → pick = null, the OOS is not read, rc 3, TOO SMALL. No sign clause: the pick does not require a positive IS mean or a positive lower bound.**

What the IS stage produced (`out/is/stats.json`):

- **pick = `fine|touch_reverse|2R|vwap_off`** (T22): IS lower 95 % CI −0.062283693361 %, 40 IS entry-weeks.
- Its IS pooled block: n 83 trades on 83 dates · mean −0.029 % · CI [−0.062, 0.006] · word no_signal · win 0.313 · stop-out 0.663 · target 0.289 · flatten 0.048 · risk median 0.079 % · room/risk 12.799.
- Read plainly: **the pick's IS mean is negative and its IS CI spans 0.** It is the pick because the rule chooses the highest lower bound, and the rule has no sign clause. The IS stage did not find a positive variant.

All 24 variants qualified (>= 30 IS weeks). IS lower bounds, pooled (`ci_raw_pct[0]`, %):

| variant | n | weeks | mean % | IS CI lower % |
|---|---|---|---|---|
| `pdhl\|cross\|next_or_flatten\|vwap_off` | 163 | 52 | −0.038 | −0.11357240452 |
| `pdhl\|cross\|next_or_flatten\|vwap_on` | 163 | 52 | −0.035 | −0.110570876949 |
| `pdhl\|cross\|2R\|vwap_off` | 163 | 52 | −0.02 | −0.088378663014 |
| `pdhl\|cross\|2R\|vwap_on` | 163 | 52 | −0.017 | −0.086543383586 |
| `pdhl\|cross\|flatten_only\|vwap_off` | 163 | 52 | −0.036 | −0.11154941657 |
| `pdhl\|cross\|flatten_only\|vwap_on` | 163 | 52 | −0.033 | −0.108468472743 |
| `pdhl\|touch_reverse\|next_or_flatten\|vwap_off` | 164 | 52 | −0.044 | −0.085070088544 |
| `pdhl\|touch_reverse\|next_or_flatten\|vwap_on` | 124 | 52 | −0.043 | −0.094857327764 |
| `pdhl\|touch_reverse\|2R\|vwap_off` | 164 | 52 | −0.027 | −0.064476262894 |
| `pdhl\|touch_reverse\|2R\|vwap_on` | 124 | 52 | −0.035 | −0.070658453707 |
| `pdhl\|touch_reverse\|flatten_only\|vwap_off` | 164 | 52 | −0.037 | −0.084264806226 |
| `pdhl\|touch_reverse\|flatten_only\|vwap_on` | 124 | 52 | −0.047 | −0.098404950007 |
| `fine\|cross\|next_or_flatten\|vwap_off` | 99 | 41 | −0.127 | −0.229579097126 |
| `fine\|cross\|next_or_flatten\|vwap_on` | 76 | 40 | −0.143 | −0.279618535219 |
| `fine\|cross\|2R\|vwap_off` | 99 | 41 | −0.126 | −0.225707262145 |
| `fine\|cross\|2R\|vwap_on` | 76 | 40 | −0.152 | −0.280848653027 |
| `fine\|cross\|flatten_only\|vwap_off` | 99 | 41 | −0.132 | −0.237495513058 |
| `fine\|cross\|flatten_only\|vwap_on` | 76 | 40 | −0.133 | −0.285571755785 |
| `fine\|touch_reverse\|next_or_flatten\|vwap_off` | 83 | 40 | −0.035 | −0.079963311676 |
| `fine\|touch_reverse\|next_or_flatten\|vwap_on` | 60 | 35 | 0.007 | −0.089355802876 |
| **`fine\|touch_reverse\|2R\|vwap_off`** | 83 | 40 | −0.029 | **−0.062283693361** |
| `fine\|touch_reverse\|2R\|vwap_on` | 60 | 35 | 0.003 | −0.071487022313 |
| `fine\|touch_reverse\|flatten_only\|vwap_off` | 83 | 40 | −0.017 | −0.074706011261 |
| `fine\|touch_reverse\|flatten_only\|vwap_on` | 60 | 35 | 0.049 | −0.082589247394 |

IS scale (at signal bars, per variant-row): stop median 0.1 % · 5-min ATR 0.122 % · stop/ATR 0.789; day range median (per session) 0.885 %. FINE bands/day median raw 16.0, merged 10.0; sessions with an overlap 246.

## Ship rule

- Candidate = the IS pick. `POSITIVE` on the candidate (pooled) → the word is "HIS CALL" (instrument / size / ON, and the side if the long and short words differ). Anything else → "OFF" + the ledger rows.
- Long and short get the full A + B + C + verdict each, printed on their own lines in `report.md` and `trials.csv`; they are never selected. Pooled is the candidate.
- The other 23 variants' OOS results are the family picture, `selectable: false`.
- Options overlay = an approximation only (`delta × side × (exit − entry) × 100`, delta 0.35 and 0.50); premium, theta, gamma and the `MAX_SPREAD_PCT` = 25 % cap are not modelled.
- A null is a result: NOT POSITIVE / TOO SMALL / UNMEASURED-glitch ship nothing and still get the ledger rows, the LEDGER.md line and the report.
- Ledger: stage 3 appends 24 rows T02…T25 (`candidate = "spy_levels:<key>"`, `prereg_sha256`, `prereg_commit`, `sr_per_entry_day`, `verdict`, `verdict_long`, `verdict_short`, `dup_cluster`, `selected`).

## What is NOT tried

- BOARD geometry (`demand_reentry.zone_geom()`, 3.0 % median width) as a source (HIS CALL #7).
- A 1-minute signal frame (HIS CALL #10; GG rejects the frame).
- A confirmation bar after the cross (HIS CALL #11).
- 15-minute ORB (measured null here before).
- Other entry windows than 09:45–14:30 / flatten 15:45.
- ATR-buffered stops, a minimum stop, ORB's tighter-of stop (HIS CALL #14).
- Multi-entry days (one trade per session only).
- A FINE re-run with suspect daily rows dropped (HIS CALL #13; 0 suspect rows were found).

## Run order

1. Stage 0 fetch — DONE 2026-11-05 23:19 ET (`out/fetch/`).
2. Stage 1 smoke — DONE 2026-11-05 23:32 ET (`out/smoke/`, 10 IS sessions at a stride, no ledger).
3. Stage 2 IS — DONE 2026-11-05 23:32 ET (`out/is/`, the pick above).
4. Commit this prereg (byte-identical copy at `docs/research/spy_levels_2026_11_05_prereg.md`), the sha file, the script and the test on `feat/spy-levels-lane-2026-11-05`.
5. Stage 3 outcome — ONCE, outside 09:00–16:30 ET, in a throwaway `--rm` container on `cheetah-market-app_default` with the worktree backend mounted read-only: `--mode outcome --cohort-stats /strat/out/fetch/stats.json --prereg /research/2026-11-05_spy_levels_prereg.md --prereg-commit <hash> --ledger /research/strategy_lab_ledger.json --out /strat/out/outcome`.
6. LEDGER.md rows (the candidate's three side words + one family line), and one paragraph in `docs/supply_demand/index_zones.md` stating the verdict and that the strip still gates nothing.

## Amendment A1 (2026-11-06 00:0x ET — written BEFORE any OOS number existed)

Stage 3 run #1 (`--prereg-commit f9feb00dda6d`, container `spy-levels-outcome`, 23:58 ET 2026-11-05) crashed with
`TypeError: 'bool' object is not callable` at the `fallback` block of the `next_or_flatten` variants
(`main()`'s network flag `block=True` shadowed the module function `block()`; that branch runs only in outcome mode,
so the smoke and IS stages never reached it). No OOS statistic was computed, printed or written: `out/outcome/` is
empty, `strategy_lab_ledger.json` unchanged (1 entry), the log holds only the traceback. Fix: the flag is renamed
`net_block` in `main()` / `run_fetch()` and the tests; no decision logic, value, cohort or seal changed. Guard:
`test_13_no_parameter_of_main_or_run_fetch_shadows_a_module_callable` (+ its NEGATIVE). New script sha256
`84096282f9ceed70e540ac519f1a834ff7ac92626e1104b3c5335f834bc1eaf3`. Stage 3 is re-run ONCE with the commit that carries this amendment as `--prereg-commit`. The seal is
intact: the OOS half has still not been read into any number.
