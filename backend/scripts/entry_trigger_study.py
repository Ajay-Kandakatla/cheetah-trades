"""🎯 ENTERABLE — the ENTRY-TRIGGER study (Phase A: a measurement; nothing is wired).

THE ASK (Ajay 2026-09-15, verbatim from the brief): "We really need to figure out
the entries, I only wanna see the stocks that are enterable. i don't know if its
volume burst or candle stick patterns we need to read. Research the best strategy
and make sure its applicable across all chart maps. ... look for any good tested
entry methods or strategies and apply them. across board.."

THE QUESTION this script answers is NOT "which stock" (measured null on 2026-09-15:
RSI, rvol, ATR, KC, AMD, CMF, dollar volume and the 52w box all sit under the
2.2pp MDL) but WHEN inside the episode: does an entry TRIGGER or a CONFIRMATION
lift HIT5 from the ENTRY price, among the rows that reached the same bar unstopped,
like-for-like on room and risk — and does entering only when it fires beat always
entering at the print (the policy view)?

HOUSE RULES this file is written under: his ONE typed number is the 5%
(`alert_gates.ALERT_MIN_ROOM_PCT`, imported); every other threshold is an existing
constant imported by name (`premarket_entry.CONFIRM_MAX_LIFT_PCT`,
`premarket_entry.WEAK_DAY_LO/HI_PCT`, `alert_gates.KNIFE_MA_LEN`,
`alert_gates.APPROACH_TOUCH_TOL_PCT`, `alert_gates.STOP_BUFFER_PCT`,
`zone_store.MIN_BARS`) or a quantile of the cohort; the windows that are NOT in his
words (confirmation within 3 bars, higher-low within 10, delays 1/2/3, the 120-row
cell floor) come from the 2026-09-15 brief and are labelled
"brief 2026-09-15 — unconfirmed" in the code, the JSON (`windows.source`), the
report and the docs — never "his". No book, no internet stat. The backtest ships
with the claim. Nothing here gates an alert, a lane or a push; paper only.

WHAT IT REUSES (nothing is copied). `scripts.explosive_study` (ES) is imported and
its functions are used BY NAME:
  cohort/replay  `frame_with_tail_rule`, `drop_nonpositive`, `apply_tail_rule`,
                 `symbols_for`, `join_features`, `flag_episodes`, `load_events`
  event/floor    `served_band`, `intact_replica` (aliased here, pinned identical),
                 `event_bar_row`, `_rvol`, `_first_k`
  outcomes       `outcome_block`, `next_open_block`
  statistics     `_by_key`, `cluster_boot`, `boot_delta_col`, `two_way_ci`,
                 `placebo_dates`, `reweight_delta`, `dedupe_deltas`, `perm_p`,
                 `trimmed_mean`, `conventions`, `feat_kind`, `assign_buckets`,
                 `orientation`, `top_bucket`, `bucket_stats`, `fmt_row`,
                 `evaluate_bucket`, `fmt_ci_line`, `fmt_eval`, `fit_edges`,
                 `score_rows`, `top_frac_mask`, `run_split`, `_clean`, `RULE_TEXT`,
                 `P`, `_f`, `_nanmean`, `spearman`, `_today_et`
The cohort itself is the UNTOUCHED `studies.bounce_quality_study.events()` — the
touch bar j, the board's own geometry, the two standing gates, the engine's forward
pass. The event condition is restated ONCE as the importable `event_at()` so the
live survivor reader replays the identical rule (no third definition of a touch);
`test_entry_trigger_study.py` pins `event_at` against a direct replay of
bounce_quality_study.py:467-489.

NEW HERE (each pinned by a test): `event_at`, `trigger_c1/c2/hl/l1` (the four
confirmation rules, pure, also imported by the live reader), `cond_boot` /
`cond_mdl` (the one statistic ES lacks: a pooled multi-cell conditional delta with
ONE shared date resample per draw).

THE IDENTITY THAT SHAPES THE STATISTICS. A trigger that fires at bar k IS the
delay-k entry on that row: same entry `close[k]`, same stop, same target, same
forward bars, and `ES.outcome_block` is deterministic on those — so a self-paired
"matched delay" placebo is 0 by construction. The deciding lift is therefore the
CONDITIONAL contrast `d_cond`: fired rows against the OTHER rows that survived to
the same bar k unstopped, pooled over k with the fired weights. `d_raw` (fired vs
all P) is reported and labelled "includes survival to bar k", never a condition,
and `d_delay_only_k` prints beside it so the reader sees how much of it is the
waiting. The decomposition `d_raw - Σ w_k·d_delay_only_k == d_cond` is printed.

RUN (read-only; both scripts are piped to /tmp, never written into /app):
  cd /Users/ajay/clinet-test/.wt-chart-studies
  docker exec -i cheetah-market-app-api-1 sh -c 'cat > /tmp/explosive_study.py' \
      < backend/scripts/explosive_study.py
  docker exec -i cheetah-market-app-api-1 sh -c 'cat > /tmp/entry_trigger_study.py' \
      < backend/scripts/entry_trigger_study.py
  # smoke — NOT QUOTABLE (a stride, never the first N names)
  docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app:/tmp python -u \
      /tmp/entry_trigger_study.py --stage both --universe broad --floor 120 --stride 18 \
      --out /tmp/entry_smoke.csv --json /tmp/entry_smoke.json'
  # full — two detached replays (broad = the boards' universe, cache = survivorship)
  docker exec -d -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app:/tmp python -u \
      /tmp/entry_trigger_study.py --stage replay --universe broad --floor 120 \
      --out /tmp/entry_events.csv > /tmp/entry_broad.log 2>&1'
  docker exec -d -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app:/tmp python -u \
      /tmp/entry_trigger_study.py --stage replay --universe cache --floor 120 \
      --out /tmp/entry_events_cache.csv > /tmp/entry_cache.log 2>&1'
  # stats (+ the MEASURED literal)
  docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app:/tmp python -u \
      /tmp/entry_trigger_study.py --stage stats --from-csv /tmp/entry_events.csv \
      --cache-csv /tmp/entry_events_cache.csv --json /tmp/entry_measured.json \
      --emit-measured' | tee entry_report.txt
Poll a detached job no faster than once a minute; `<out>.meta.json` means done.
Never during RTH (the hourly cache patch rewrites frames from ~10:00 ET).

SURVIVORSHIP IS A PRECONDITION, NOT A FOOTNOTE. The cache-universe replay is a
SEPARATE run, so `--stage stats` can MERGE its result instead of re-reading the
whole events CSV: the first stats run that is given `--cache-csv` writes the
computed block to `<cache-csv>.survivorship.json` (SURVIVORSHIP_SUFFIX), and a
later run picks it up either from `--survivorship <json>` or, with no flag at
all, from that sidecar sitting beside the events cache. `d_hit5_vs_broad` is
always RECOMPUTED against the broad base of the run doing the merge, never
carried over. `quotable` is True only when BOTH hold — no stride/names subsample
AND the survivorship replay is in hand — so the flag can never disagree with the
"NO NUMBER ABOVE IS QUOTABLE WITHOUT THE CACHE LINE" banner; `quotable_reasons`
names every reason it is False.

DEVIATIONS (each stated, none silent)
  1. `ES.bucket_stats` reads `K["room_pct"]` (explosive_study.py:1183) — the P-entry
     room — so the per-feature bucket tables under N and PC print P's room, not the
     convention's own. The CONVENTION table uses `room_pct_X` / `risk_pct_X`, which
     are the convention's own entry. Stated rather than patched: bucket_stats is
     imported, never re-implemented.
  2. The MDL of `d_cond` is 1.96 x the SD of `cond_boot` under a RANDOM RELABEL (for
     each k a random subset of base_k of size |kept_k| stands in for kept_k) — the
     ES deviation #5 construction ("random decile keep") carried over to a pooled
     multi-cell delta. The MDL of `d_paired` (N / PC, which have no fire bar) is
     1.96 x the bootstrap SD of the paired delta itself.
  3. A convention's entry bar needs `entry_bar + max_clock <= n-1` forward bars or
     the row is skipped with `skip_reason = "no_bars"` (counted per convention).
     The engine's own event guard only promises `j + max_clock < n`, so the late
     delays (D4..D10) lose the events that sit in the last bars of a frame.
     Every convention's `fire_rate` and `n_skipped` are reported over the FULL
     bouncing-episode base, never over the frame the convention happens to be
     scored on: N is scored on the gapless rows (`gap_N == False`) but its
     `n_base` is the whole cohort and the excluded episodes appear in `n_skipped`
     under their own `skip_reason_N` (`gap_N`), so `n_fired + Σ n_skipped` closes
     on `n_base`. The C1 window sweep excludes the same `no_bars` rows the C1
     convention excludes (it reads `fired_D<k>`, which carries that guard), so
     the sweep at the confirmation window equals `conventions.C1.n_fired`.
  4. When a fire bar k has fewer than `MIN_CELL_N` fired or base rows it is dropped
     from the pool (listed as `dropped_k`) and the fired weights are RENORMALISED
     over the surviving k, so the pooled delta stays a weighted mean.
  5. The `_policy` columns (`R20_policy_X`, `hit5_policy_X`, `stop_policy_X`) are
     DERIVED in the stats stage from `fired_X` rather than written to the CSV: 16
     conventions x 3 columns x ~150k rows is memory the container does not have.
  6. Only the reported conventions carry a full `outcome_block`; D4..D10 (the
     placebo base for HL) carry `hit5_20 / stop_20 / R20 / risk_pct / room_pct`
     only, for the same memory reason. Everything the JSON quotes for them is in
     that set.
  7. `above_sma200_pre` is EXPLORATORY (printed, never scored): `sepa/` has no named
     200-day MA constant — stage.py:67 types the 200 inline — so it is a number by
     proxy, like `vol_slope3_at` (3 = `turning_bullish.MAX_RAID_BARS_AGO`) and
     `rs20_pre` (20 bars).
  8b. Family 5 (`interactions`) is CONTEXT and is never read by `select_survivor`:
     a cell has no reweight and no policy column, so it can clear condition (a)
     only. It therefore prints `cushion` (CI above zero, and the reweight when the
     cell has one) or `not selected` — never `separates`, which in this file means
     the full (a)-(f) guard `convention_conditions` applies.
  8. The 120-row cell floor is enforced on every table this study prints by setting
     `ES.MIN_BUCKET_N = MIN_CELL_N` for the duration of the stats stage (restored in
     a `finally`), so `ES.evaluate_bucket` / `orientation` / `top_bucket` inside the
     imported machinery obey the same floor.

RESULTS — 2026-09-15 (broad, floor 120, clocks [5, 10, 20], hold 20, primary hit5, cell floor 120)
  quotable: True
  cohort: 3,585 names · 157,894 events · 92,732 reversal events · 24,922 EPISODES · 361 dates · window 2025-03-10 -> 2026-08-14
  windows: confirmation 3 bars · higher low 10 bars · delays [1, 2, 3]  (brief 2026-09-15 — unconfirmed)
  base P  (entry at the print):    HIT5@5/10/20 28.5 / 32.6 / 34.2 % · HIT5B@20 31.9 % · HIT_LID@20 21.2 % (n=21942) · stop@20 74.5 % · R20 0.288 / med -1.000 / trim 0.067 · room 15.63 % · risk 2.57 %
  base N  (entry at the next open): HIT5@5/10/20 27.7 / 33.0 / 35.0 % · HIT5B@20 34.8 % · HIT_LID@20 22.8 % (n=19962) · stop@20 72.2 % · R20 0.302 / med -1.000 / trim -0.046 · room 15.43 % · risk 2.99 %
  base PC (same close, PRINT-ONLY): HIT5@5/10/20 28.5 / 32.6 / 34.2 % · HIT5B@20 31.9 % · HIT_LID@20 21.2 % (n=21942) · stop@20 74.5 % · R20 0.288 / med -1.000 / trim 0.067 · room 15.63 % · risk 2.57 %
  conventions — the conditional lift is fired rows vs UNFIRED rows that reached the same bar unstopped:
    N    n=22,884  fire 0.918   HIT5@20 35.0   d_cond n/a       CI n/a                MDL n/a     d_paired -2.24pp   Δstop n/a       policyR -0.100   splits no_signal no_signal no_signal → no_signal
    PC   n=24,922  fire 1.000   HIT5@20 34.2   d_cond n/a       CI n/a                MDL n/a     d_paired +0.00pp   Δstop n/a       policyR 0.000    splits no_signal no_signal no_signal → no_signal
    D1   n=15,059  fire 0.604   HIT5@20 44.6   d_cond n/a       CI n/a                MDL n/a     d_paired -11.87pp  Δstop n/a       policyR -0.169   splits no_signal no_signal no_signal → no_signal
    D2   n=12,243  fire 0.491   HIT5@20 48.3   d_cond n/a       CI n/a                MDL n/a     d_paired -18.21pp  Δstop n/a       policyR -0.198   splits no_signal no_signal no_signal → no_signal
    D3   n=10,615  fire 0.426   HIT5@20 51.0   d_cond n/a       CI n/a                MDL n/a     d_paired -22.10pp  Δstop n/a       policyR -0.245   splits no_signal no_signal no_signal → no_signal
    C1   n=7,876   fire 0.316   HIT5@20 53.6   d_cond +7.03pp   CI [+5.75, +8.36]     MDL 0.93    d_paired -24.75pp  Δstop -14.14pp  policyR -0.271   splits separates separates separates → no_signal
    C2   n=6,467   fire 0.259   HIT5@20 52.2   d_cond +6.32pp   CI [+5.00, +7.60]     MDL 1.07    d_paired -25.17pp  Δstop -10.14pp  policyR -0.265   splits separates separates separates → no_signal
    HL   n=5,905   fire 0.237   HIT5@20 57.4   d_cond +8.00pp   CI [+6.48, +9.53]     MDL 1.28    d_paired -22.93pp  Δstop -16.51pp  policyR -0.284   splits separates separates separates → no_signal
    L1   n=10,390  fire 0.417   HIT5@20 52.3   d_cond +6.40pp   CI [+5.49, +7.37]     MDL 0.79    d_paired -22.69pp  Δstop -8.97pp   policyR -0.255   splits separates separates separates → no_signal
  delays — what waiting alone buys, same survivorship:
    D1   n=15,059  HIT5@20 44.6   stop 58.8   R20 0.197    policyR 0.119    d_delay_only +10.42pp  CI [+8.63, +12.20]
    D2   n=12,243  HIT5@20 48.3   stop 51.1   R20 0.183    policyR 0.090    d_delay_only +14.13pp  CI [+11.82, +16.39]
    D3   n=10,615  HIT5@20 51.0   stop 45.3   R20 0.101    policyR 0.043    d_delay_only +16.80pp  CI [+14.52, +19.13]
    D4   n=9,473   HIT5@20 52.7   stop 40.6   R20 0.069    policyR 0.026    d_delay_only +18.56pp  CI [+15.96, +21.18]
    D5   n=8,652   HIT5@20 54.2   stop 37.1   R20 0.022    policyR 0.008    d_delay_only +19.97pp  CI [+17.34, +22.72]
    D6   n=8,010   HIT5@20 54.6   stop 34.0   R20 0.007    policyR 0.002    d_delay_only +20.42pp  CI [+17.72, +23.28]
    D7   n=7,553   HIT5@20 54.8   stop 32.0   R20 -0.025   policyR -0.008   d_delay_only +20.63pp  CI [+17.47, +23.77]
    D8   n=7,141   HIT5@20 54.7   stop 29.8   R20 -0.005   policyR -0.001   d_delay_only +20.50pp  CI [+17.15, +23.80]
    D9   n=6,773   HIT5@20 54.5   stop 27.8   R20 -0.010   policyR -0.003   d_delay_only +20.33pp  CI [+16.73, +23.89]
    D10  n=6,467   HIT5@20 55.2   stop 26.3   R20 -0.053   policyR -0.014   d_delay_only +20.98pp  CI [+17.44, +24.48]
  intact reconciliation (must land ≈ +8pp or the harness is wrong, not the market): {'d_hit5_P': 8.297637442664257, 'n_intact': 7166, 'expected_2026_09_15': 8.3}
  stratifiers:
    intact_at            top=yes   ΔHIT5@20 +8.30pp   CI [+6.66, +9.93]     Δstop -9.16pp   reweighted +3.79pp   → selects smaller trades
    weak_day_at          top=yes   ΔHIT5@20 +0.03pp   CI [-1.62, +1.72]     Δstop +2.74pp   reweighted +1.02pp   → inert
    above_sma200_pre     top=yes   ΔHIT5@20 +0.69pp   CI [-1.02, +2.32]     Δstop -2.41pp   reweighted +0.05pp   → inert
    rs20_pre             top=Q1    ΔHIT5@20 +1.91pp   CI [+0.10, +3.68]     Δstop +3.03pp   reweighted +2.28pp   → selects wider stops
    above_sma200_pre     top=yes   ΔHIT5@20 +0.41pp   CI [-1.22, +1.92]     Δstop -2.25pp   reweighted -0.42pp   → inert
    rs20_pre             top=Q1    ΔHIT5@20 +1.99pp   CI [+0.21, +3.71]     Δstop +2.91pp   reweighted +1.51pp   → selects wider stops
    above_sma200_pre     top=yes   ΔHIT5@20 +0.69pp   CI [-1.02, +2.32]     Δstop -2.41pp   reweighted +0.05pp   → inert  [PRINT-ONLY]
    rs20_pre             top=Q1    ΔHIT5@20 +1.91pp   CI [+0.10, +3.68]     Δstop +3.03pp   reweighted +2.28pp   → selects wider stops  [PRINT-ONLY]
  per-feature top buckets, convention N (ship-eligible):
    rvol20_pre           top=Q1    ΔHIT5@20 +0.33pp   CI [-1.20, +1.83]     Δstop +0.85pp   reweighted +0.03pp   → inert
    rvol50_pre           top=Q1    ΔHIT5@20 +0.28pp   CI [-1.11, +1.60]     Δstop +0.96pp   reweighted -0.06pp   → inert
    updn_vol10_pre       top=Q1    ΔHIT5@20 +0.95pp   CI [-0.55, +2.43]     Δstop -0.64pp   reweighted +0.62pp   → inert
    above_sma50_pre      top=no    ΔHIT5@20 +0.42pp   CI [-0.46, +1.34]     Δstop +0.89pp   reweighted +2.29pp   → inert
    close_pos_at         top=Q1    ΔHIT5@20 +0.35pp   CI [-1.46, +2.19]     Δstop +2.01pp   reweighted +0.19pp   → inert
    lower_wick_at        top=Q1    ΔHIT5@20 +1.13pp   CI [-0.32, +2.63]     Δstop -0.20pp   reweighted +0.32pp   → inert
    body_at              top=Q5    ΔHIT5@20 +0.20pp   CI [-1.48, +1.85]     Δstop -0.04pp   reweighted -0.20pp   → inert
    up_close_at          top=yes   ΔHIT5@20 +0.43pp   CI [-1.13, +1.99]     Δstop -2.08pp   reweighted -0.49pp   → inert
    close_gt_prev_high_at top=yes   ΔHIT5@20 +1.07pp   CI [-1.71, +3.92]     Δstop -3.77pp   reweighted -1.33pp   → inert
    engulf_at            top=yes   ΔHIT5@20 +3.33pp   CI [-2.67, +9.57]     Δstop -5.96pp   reweighted -0.02pp   → inert
    inside_at            top=no    ΔHIT5@20 +0.09pp   CI [-0.20, +0.36]     Δstop -0.17pp   reweighted -1.09pp   → inert
    rvol20_at            top=Q5    ΔHIT5@20 -0.46pp   CI [-2.09, +1.12]     Δstop -1.13pp   reweighted -0.97pp   → inert
    gap_up_next          top=yes   ΔHIT5@20 +10.90pp  CI [+7.94, +14.06]    Δstop -18.20pp  reweighted +0.65pp   → selects smaller trades
    weak_day_at          top=yes   ΔHIT5@20 +0.34pp   CI [-1.31, +2.00]     Δstop +2.20pp   reweighted +0.48pp   → inert
    intact_at            top=yes   ΔHIT5@20 +6.90pp   CI [+5.44, +8.41]     Δstop -7.99pp   reweighted +3.19pp   → selects smaller trades
  per-feature top buckets, convention P (_pre features, ship-eligible):
    rvol20_pre           top=Q1    ΔHIT5@20 -0.41pp   CI [-1.96, +1.08]     Δstop +1.25pp   reweighted -1.03pp   → inert
    rvol50_pre           top=Q1    ΔHIT5@20 +0.29pp   CI [-1.07, +1.64]     Δstop +1.15pp   reweighted -0.05pp   → inert
    updn_vol10_pre       top=Q1    ΔHIT5@20 +1.59pp   CI [+0.08, +3.10]     Δstop -0.83pp   reweighted +1.88pp   → selects wider stops
    above_sma50_pre      top=no    ΔHIT5@20 +0.32pp   CI [-0.60, +1.29]     Δstop +0.97pp   reweighted +2.40pp   → inert
  per-feature top buckets, convention PC (PRINT-ONLY — never selected):
    rvol20_pre           top=Q1    ΔHIT5@20 -0.41pp   CI [-1.96, +1.08]     Δstop +1.25pp   reweighted -1.03pp   → inert  [PRINT-ONLY]
    rvol50_pre           top=Q1    ΔHIT5@20 +0.29pp   CI [-1.07, +1.64]     Δstop +1.15pp   reweighted -0.05pp   → inert  [PRINT-ONLY]
    updn_vol10_pre       top=Q1    ΔHIT5@20 +1.59pp   CI [+0.08, +3.10]     Δstop -0.83pp   reweighted +1.88pp   → selects wider stops  [PRINT-ONLY]
    above_sma50_pre      top=no    ΔHIT5@20 +0.32pp   CI [-0.60, +1.29]     Δstop +0.97pp   reweighted +2.40pp   → inert  [PRINT-ONLY]
    close_pos_at         top=Q1    ΔHIT5@20 +0.77pp   CI [-1.13, +2.68]     Δstop +1.99pp   reweighted +1.87pp   → inert  [PRINT-ONLY]
    lower_wick_at        top=Q1    ΔHIT5@20 +1.06pp   CI [-0.44, +2.65]     Δstop -0.12pp   reweighted +0.85pp   → inert  [PRINT-ONLY]
    body_at              top=Q5    ΔHIT5@20 -0.16pp   CI [-1.91, +1.56]     Δstop +0.08pp   reweighted +0.01pp   → inert  [PRINT-ONLY]
    up_close_at          top=yes   ΔHIT5@20 +0.33pp   CI [-1.27, +1.93]     Δstop -2.32pp   reweighted -1.43pp   → inert  [PRINT-ONLY]
    close_gt_prev_high_at top=yes   ΔHIT5@20 +0.60pp   CI [-2.29, +3.55]     Δstop -4.88pp   reweighted -4.07pp   → inert  [PRINT-ONLY]
    engulf_at            top=yes   ΔHIT5@20 +3.71pp   CI [-2.45, +10.20]    Δstop -7.14pp   reweighted +0.16pp   → inert  [PRINT-ONLY]
    inside_at            top=no    ΔHIT5@20 +0.20pp   CI [-0.08, +0.47]     Δstop -0.21pp   reweighted +0.40pp   → inert  [PRINT-ONLY]
    rvol20_at            top=Q5    ΔHIT5@20 -0.31pp   CI [-2.10, +1.42]     Δstop -0.92pp   reweighted +0.22pp   → inert  [PRINT-ONLY]
    weak_day_at          top=yes   ΔHIT5@20 +0.03pp   CI [-1.62, +1.72]     Δstop +2.74pp   reweighted +1.02pp   → inert  [PRINT-ONLY]
    intact_at            top=yes   ΔHIT5@20 +8.30pp   CI [+6.66, +9.93]     Δstop -9.16pp   reweighted +3.79pp   → selects smaller trades  [PRINT-ONLY]
  survivorship: 5,277 names · 37,317 episodes · HIT5@20 32.7 % · stop@20 77.0 % · Δ vs broad -1.48pp (cache-csv:/tmp/ets_cache_events.csv)
  liquidity control: {'min_dvol': 10000000.0, 'n': 14380, 'hit5_20': 34.88873435326843, 'stop_20': 73.11543810848401, 'R20': 0.277424791518337}
  feature notes: {}
  STATUS: no_signal · survivor none — no trigger is wired into the read; fallback P — enter at the print; the READY read is unchanged · selected [] · fallback P — enter at the print; the READY read is unchanged
"""
from __future__ import annotations

import argparse
import json
import os
import pprint
import time
import types
import zlib
from typing import Optional

import numpy as np
import pandas as pd

try:                                             # the container runs origin/main
    from scripts import explosive_study as ES    # (both files are piped to /tmp)
except ImportError:                              # noqa: F401
    import explosive_study as ES                 # type: ignore

from studies import bounce_quality_study as BQ
from supply_demand import alert_gates as AG
from supply_demand import demand_reentry as DR
from supply_demand import premarket_entry as PE
from supply_demand import price_zones as PZ
from sepa import prices

SCRIPT = "backend/scripts/entry_trigger_study.py"

P = ES.P
_f = ES._f
_nanmean = ES._nanmean
_today_et = ES._today_et

# ── the two container replicas live in ES; imported, never re-written ────────
served_band = ES.served_band
intact_replica = ES.intact_replica

# ── every threshold IMPORTED; the 5% is his and it is the only typed number ──
FIVE_PCT = ES.FIVE_PCT                      # 5.0  = AG.ALERT_MIN_ROOM_PCT
STOP_BUFFER_PCT = ES.STOP_BUFFER_PCT        # 0.5  = AG.STOP_BUFFER_PCT
FLOOR_DEFAULT = ES.FLOOR_DEFAULT            # 120  = ZS.MIN_BARS
HOLD_DEFAULT = ES.HOLD_DEFAULT              # 20   = BQ.HOLD_SESSIONS
CLOCKS_DEFAULT = ES.CLOCKS_DEFAULT          # (5, 10, 20)
BOX_BARS = ES.BOX_BARS                      # 252  = PZ.LOOKBACK_BARS
RVOL_SHORT = ES.RVOL_SHORT                  # 20   = amd.VOL_REF_BARS
RVOL_LONG = ES.RVOL_LONG                    # 50   = breakout_audit.VOL_AVG_BARS
SWEEP_WINDOW = ES.SWEEP_WINDOW              # 15   = AG.SWEEP_WINDOW_BARS
POCKET_LOOKBACK = ES.POCKET_LOOKBACK        # 10   = sepa.volume._pocket_pivot's own
DIRECTION_BASE = ES.DIRECTION_BASE          # "bouncing" — what pushes today
SEED_BOOT, SEED_PLACEBO = ES.SEED_BOOT, ES.SEED_PLACEBO
LIFT_PCT = PE.CONFIRM_MAX_LIFT_PCT          # 1.0  — the autopsy's "after the lift"
WEAK_LO = PE.WEAK_DAY_LO_PCT                # -8.0 — the measured drag band
WEAK_HI = PE.WEAK_DAY_HI_PCT                # -3.0
SMA_SHORT = AG.KNIFE_MA_LEN                 # 50   — the knife gate's own MA
TOUCH_TOL = AG.APPROACH_TOUCH_TOL_PCT       # 1.0  — the approach read's touch tol
VOL_SLOPE_BARS = ES.VOL_BURST_BARS          # 3 = TB.MAX_RAID_BARS_AGO -> BY PROXY
SMA_LONG = 200                              # no named constant in sepa/ -> EXPLORATORY
RS_BARS = 20                                # BY PROXY -> EXPLORATORY
RS_SYMBOL = "RSP"                           # the equal-weight benchmark the boards use

# brief 2026-09-15 — unconfirmed (§7.11 asks him to confirm or replace)
C_WINDOW_BARS = 3                           # brief 2026-09-15 — unconfirmed, §7.11
HL_WINDOW_BARS = 10                         # brief 2026-09-15 — unconfirmed, §7.11
DELAYS_REPORTED = (1, 2, 3)                 # brief 2026-09-15 — unconfirmed, §7.11
DELAYS_PLACEBO = tuple(range(1, 11))        # the base for a HL that fires at k > 3
MIN_CELL_N = 120                            # brief 2026-09-15 — unconfirmed, §7.11
C1_SWEEP_WINDOWS = (1, 2, 3, 5)             # printed beside C1, never scored
WINDOW_SOURCE = "brief 2026-09-15 — unconfirmed"

# the survivorship replay is a SEPARATE run; this is where its block is parked so a
# later `--stage stats` can MERGE it without re-reading the cache-universe events CSV
SURVIVORSHIP_SUFFIX = ".survivorship.json"
SURVIVORSHIP_MISSING = "no survivorship replay — the cache-universe line is missing"
SUBSAMPLE_NOT_QUOTABLE = "stride/names subsample"
INTER_CUSHION = "cushion"                   # family 5 is context: never "separates"
INTER_NOT_SELECTED = "not selected"

# PC = the MOC twin of P (bar-j shape read into a close[j] entry). An MOC order is
# placed BEFORE the close prints, so a bar-j shape is not knowable at order time:
# PC is PRINT-ONLY and can never ship.
SHIP_ELIGIBLE_CONVENTIONS = ("P", "N")

TRIGGER_KEYS = ("C1", "C2", "HL", "L1")
DELAY_KEYS = tuple("D%d" % k for k in DELAYS_PLACEBO)
REPORT_KEYS = ("N", "PC") + tuple("D%d" % k for k in DELAYS_REPORTED) + TRIGGER_KEYS
ALL_CONV_KEYS = ("N", "PC") + DELAY_KEYS + TRIGGER_KEYS

# ── pre-registered feature sets — FROZEN before the first full run ───────────
PREREG_P_TRIG = ("rvol20_pre", "rvol50_pre", "updn_vol10_pre", "above_sma50_pre")
PREREG_N_TRIG = PREREG_P_TRIG + (
    "close_pos_at", "lower_wick_at", "body_at", "up_close_at", "close_gt_prev_high_at",
    "engulf_at", "inside_at", "rvol20_at", "gap_up_next", "weak_day_at", "intact_at")
PREREG_PC_TRIG = tuple(f for f in PREREG_N_TRIG if f != "gap_up_next")
assert len(PREREG_P_TRIG) == 4 and len(PREREG_N_TRIG) == 15 and len(PREREG_PC_TRIG) == 14

STRATIFIERS = ("intact_at", "weak_day_at", "above_sma50_pre", "above_sma200_pre", "rs20_pre")
EXPLORATORY = ("vol_slope3_at", "above_sma200_pre", "rs20_pre", "rvol_conf_C1",
               "day_ret_at", "intact_state_at")

TRIG_BOOL_FEATS = {"up_close_at", "close_gt_prev_high_at", "engulf_at", "inside_at",
                   "gap_up_next", "weak_day_at", "above_sma50_pre", "above_sma200_pre",
                   "c2_na"}
TRIG_BOOL_FEATS |= {"fired_%s" % k for k in ALL_CONV_KEYS}
TRIG_BOOL_FEATS |= {"target_passed_%s" % k for k in ALL_CONV_KEYS}
ES.BOOL_FEATS |= set(TRIG_BOOL_FEATS)            # so ES.load_events casts them
ES.STATE_FEATS |= {"intact_state_at"}

OUTCOMES = ES.OUTCOMES


# ═════════════════════════════════════════════════════════════════════════════
# THE EVENT — bounce_quality_study.events():467-489 restated ONCE, importable
# ═════════════════════════════════════════════════════════════════════════════
def event_at(o, h, l, c, j: int, bands) -> Optional[dict]:
    """The engine's own event condition at bar `j`, given the bands drawn from
    bars STRICTLY BEFORE j (BQ.events :467-489). The live survivor reader calls
    THIS, so there is never a second definition of "the touch".

    {"band", "stop", "target", "room", "hits"} or None when the bar is not an
    event: no demand band passes BOTH standing reads (proximity <= 1% above the
    top AND an `approach_read` that returns a dict), or the room gate fails, or
    the print is already at/under the stop."""
    if j < 1 or j >= len(c):
        return None
    px, prev, day_low = _f(c[j]), _f(c[j - 1]), _f(l[j])
    if px is None or prev is None or day_low is None or px <= 0:
        return None
    hits = []
    for b in bands or []:
        if not isinstance(b, dict):
            continue
        if str(b.get("kind") or "demand").lower() != "demand":
            continue
        if not AG.demand_proximity_gate(px, b):
            continue
        if not isinstance(AG.approach_read(px, b, prev, day_low), dict):
            continue
        lo = _f(b.get("lo"))
        if lo is None:
            continue
        hits.append((lo, b))
    if not hits:
        return None
    band_lo, band = max(hits, key=lambda t: t[0])       # the nearest support UNDER
    ok_room, room = AG.room_gate(px, bands, prev)
    if not ok_room:
        return None
    stop = float(band_lo) * (1.0 - STOP_BUFFER_PCT / 100.0)
    if px <= stop:
        return None
    target = float(room["target"]) if room else None
    return {"band": band, "stop": stop, "target": target, "room": room,
            "hits": len(hits)}


# ═════════════════════════════════════════════════════════════════════════════
# THE TRIGGERS — pure, importable, the ONE definition the live reader mirrors
# ═════════════════════════════════════════════════════════════════════════════
def _floor_scan(l, stop, t) -> bool:
    """True when bar t already broke the floor (so no later bar can fire)."""
    v = _f(l[t])
    return v is None or v <= stop


def trigger_c1(o, h, l, c, j: int, stop: float, band_hi, W: int = C_WINDOW_BARS) -> tuple:
    """First CLOSE above the touch bar's high within W bars, with the floor never
    broken on the way (the trigger bar included). -> (k | None, skip_reason)."""
    n = len(c)
    hj = _f(h[j])
    if hj is None:
        return None, "no_bar_j"
    for k in range(j + 1, min(j + W, n - 1) + 1):
        if _floor_scan(l, stop, k):
            return None, "floor_broke_before_trigger"
        if float(c[k]) > hj:
            return k, None
    return None, ("no_bars" if j + 1 > n - 1 else "no_trigger")


def trigger_c2(o, h, l, c, j: int, stop: float, band_hi, W: int = C_WINDOW_BARS) -> tuple:
    """First CLOSE back above the BAND TOP within W bars. Requires an in-band
    close at j (else the row is not in the C2 denominator at all: `c2_na`)."""
    n = len(c)
    hi = _f(band_hi)
    if hi is None:
        return None, "no_band"
    if float(c[j]) > hi:
        return None, "c2_na"
    for k in range(j + 1, min(j + W, n - 1) + 1):
        if _floor_scan(l, stop, k):
            return None, "floor_broke_before_trigger"
        if float(c[k]) > hi:
            return k, None
    return None, ("no_bars" if j + 1 > n - 1 else "no_trigger")


def trigger_hl(o, h, l, c, j: int, stop: float, band_hi, W: int = HL_WINDOW_BARS) -> tuple:
    """A CONFIRMED higher low: the lowest low of j+1..k (k INCLUDED) sits above
    l[j], is not bar k itself, and bar k closes above that bar's high — i.e. a
    second touch that held and that no later bar, k included, undercut."""
    n = len(c)
    lj = _f(l[j])
    if lj is None:
        return None, "no_bar_j"
    for k in range(j + 2, min(j + W, n - 1) + 1):
        if _floor_scan(l, stop, k):
            return None, "floor_broke_before_trigger"
        win = np.asarray(l[j + 1:k + 1], dtype=float)
        if win.size < 2 or not np.isfinite(win).all():
            continue
        m = j + 1 + int(np.argmin(win))
        if m >= k:                                   # the low IS bar k — not confirmed
            continue
        if float(l[m]) <= lj:                        # undercut the touch bar's low
            continue
        if float(c[k]) > float(h[m]):
            return k, None
    return None, ("no_bars" if j + 2 > n - 1 else "no_trigger")


def trigger_l1(o, h, l, c, j: int, stop: float, band_hi, W: int = C_WINDOW_BARS) -> tuple:
    """The autopsy's "after the +1% lift": the first close at/above
    close[j] x (1 + CONFIRM_MAX_LIFT_PCT/100) within W bars."""
    n = len(c)
    cj = _f(c[j])
    if cj is None:
        return None, "no_bar_j"
    want = cj * (1.0 + LIFT_PCT / 100.0)
    for k in range(j + 1, min(j + W, n - 1) + 1):
        if _floor_scan(l, stop, k):
            return None, "floor_broke_before_trigger"
        if float(c[k]) >= want:
            return k, None
    return None, ("no_bars" if j + 1 > n - 1 else "no_trigger")


TRIGGERS = {"C1": trigger_c1, "C2": trigger_c2, "HL": trigger_hl, "L1": trigger_l1}
TRIGGER_WINDOW = {"C1": C_WINDOW_BARS, "C2": C_WINDOW_BARS, "HL": HL_WINDOW_BARS,
                  "L1": C_WINDOW_BARS}


def delay_fire(l, c, j: int, stop: float, k: int) -> tuple:
    """The unconditional delay-k entry: skipped when the floor broke on any bar
    j+1..j+k, or the entry close itself is at/under the stop."""
    n = len(c)
    e = j + k
    if e > n - 1:
        return None, "no_bars"
    for t in range(j + 1, e + 1):
        if _floor_scan(l, stop, t):
            return None, "stopped_before_entry"
    if float(c[e]) <= stop:
        return None, "stopped_before_entry"
    return e, None


# ═════════════════════════════════════════════════════════════════════════════
# CONVENTION COLUMNS — each entry has its OWN price, room, risk and outcomes
# ═════════════════════════════════════════════════════════════════════════════
def conv_kind(key: str) -> str:
    if key in ("P", "N", "PC"):
        return "full"
    if key in TRIGGER_KEYS or key in tuple("D%d" % k for k in DELAYS_REPORTED):
        return "reported"
    return "delay"


def block_keys(kind: str, clocks, hold: int, sfx: str) -> list:
    if kind == "full":
        keys = ["k_5pct" + sfx, "k_stop" + sfx, "k_target" + sfx]
        for cl in sorted(set(clocks) | {hold}):
            keys += ["hit5_%d%s" % (cl, sfx), "hit5b_%d%s" % (cl, sfx),
                     "hit_lid_%d%s" % (cl, sfx), "stop_%d%s" % (cl, sfx),
                     "R%d%s" % (cl, sfx), "why%d%s" % (cl, sfx)]
        keys += ["hit5c_%d%s" % (hold, sfx), "max_gain_pct_%d%s" % (hold, sfx)]
        return keys
    if kind == "reported":
        return ["hit5_%d%s" % (hold, sfx), "hit5b_%d%s" % (hold, sfx),
                "hit_lid_%d%s" % (hold, sfx), "stop_%d%s" % (hold, sfx),
                "R%d%s" % (hold, sfx), "why%d%s" % (hold, sfx)]
    return ["hit5_%d%s" % (hold, sfx), "stop_%d%s" % (hold, sfx), "R%d%s" % (hold, sfx)]


def _blank(keys: list) -> dict:
    return {k: (None if k.startswith("why") else np.nan) for k in keys}


def close_entry_cols(key: str, k_bar, reason, h, l, c, j: int, n: int, stop: float,
                     target, band_hi, clocks, hold: int) -> dict:
    """Every column of one CLOSE-entry convention (PC, D_k, C1, C2, HL, L1)."""
    sfx = "_" + key
    kind = conv_kind(key)
    keys = block_keys(kind, clocks, hold, sfx)
    max_clock = max(max(clocks), hold)
    e = k_bar
    if e is not None and e + max_clock > n - 1:
        e, reason = None, "no_bars"
    if e is None:
        out = _blank(keys)
        out.update({"fired" + sfx: False, "entry" + sfx: np.nan, "entry_bar" + sfx: np.nan,
                    "skip_reason" + sfx: reason, "risk_pct" + sfx: np.nan,
                    "room_pct" + sfx: np.nan, "target_passed" + sfx: np.nan})
        return out
    entry = float(c[e])
    fh = h[e + 1:e + 1 + max_clock]
    fl = l[e + 1:e + 1 + max_clock]
    fc = c[e + 1:e + 1 + max_clock]
    blk = ES.outcome_block(fh, fl, fc, entry, stop, target, band_hi, clocks, hold, suffix=sfx)
    blk = {k: v for k, v in blk.items() if k in keys}
    tgt = _f(target)
    passed = bool(tgt is not None and entry >= tgt)
    if passed:                                   # the lid is already behind the entry
        for k in list(blk):
            if k.startswith("hit_lid_"):
                blk[k] = np.nan
    blk.update({"fired" + sfx: True, "entry" + sfx: entry, "entry_bar" + sfx: float(e),
                "skip_reason" + sfx: None,
                "risk_pct" + sfx: (entry - stop) / entry * 100.0 if entry else np.nan,
                "room_pct" + sfx: ((tgt - entry) / entry * 100.0
                                   if (tgt is not None and not passed) else np.nan),
                "target_passed" + sfx: passed})
    return blk


def convention_cols(o, h, l, c, j: int, n: int, stop: float, target, band_hi,
                    clocks, hold: int) -> dict:
    """N, PC, D1..D10 and the four triggers for one event row."""
    out = {}
    max_clock = max(max(clocks), hold)
    fh = h[j + 1:j + 1 + max_clock]
    fl = l[j + 1:j + 1 + max_clock]
    fc = c[j + 1:j + 1 + max_clock]
    # ── N: entry open[j+1] (ES owns the gap rule) ──
    blk = ES.next_open_block(o[j + 1], fh, fl, fc, stop, target, band_hi, clocks, hold)
    out.update(blk)
    gap = bool(blk.get("gap_N"))
    entry_n = _f(blk.get("entry_N"))
    tgt = _f(target)
    passed_n = bool((not gap) and entry_n is not None and tgt is not None and entry_n >= tgt)
    if passed_n:
        for k in list(out):
            if k.startswith("hit_lid_") and k.endswith("_N"):
                out[k] = np.nan
    out.update({"fired_N": (not gap), "entry_bar_N": float(j + 1) if not gap else np.nan,
                "skip_reason_N": None if not gap else "gap_N",
                "target_passed_N": passed_n if not gap else np.nan,
                "room_pct_N": ((tgt - entry_n) / entry_n * 100.0
                               if (not gap and entry_n and tgt is not None and not passed_n)
                               else np.nan)})
    # ── PC: the MOC twin of P (same entry, bar-j features allowed) ──
    out.update(close_entry_cols("PC", j, None, h, l, c, j, n, stop, target, band_hi,
                                clocks, hold))
    # ── the unconditional delays ──
    for k in DELAYS_PLACEBO:
        e, why = delay_fire(l, c, j, stop, k)
        out.update(close_entry_cols("D%d" % k, e, why, h, l, c, j, n, stop, target,
                                    band_hi, clocks, hold))
    # ── the four confirmation triggers ──
    for key in TRIGGER_KEYS:
        e, why = TRIGGERS[key](o, h, l, c, j, stop, band_hi, TRIGGER_WINDOW[key])
        out.update(close_entry_cols(key, e, why, h, l, c, j, n, stop, target, band_hi,
                                    clocks, hold))
        if key == "C2":
            out["c2_na"] = (why == "c2_na")
    return out


# ═════════════════════════════════════════════════════════════════════════════
# FEATURES — a post-hoc LEFT join on the engine's rows (hard assert on the count)
# ═════════════════════════════════════════════════════════════════════════════
def candle_cols(o, h, l, c, j: int) -> dict:
    """Family 1 — the reversal-bar shape at j. DATA features: no book is cited,
    nothing is claimed from a text (Rule #1)."""
    rng = float(h[j]) - float(l[j])
    body_lo = min(float(o[j]), float(c[j]))
    day_ret = (float(c[j]) / float(c[j - 1]) - 1.0) * 100.0 if float(c[j - 1]) > 0 else np.nan
    return {
        "close_pos_at": ((float(c[j]) - float(l[j])) / rng) if rng > 0 else np.nan,
        "lower_wick_at": ((body_lo - float(l[j])) / rng) if rng > 0 else np.nan,
        "body_at": (abs(float(c[j]) - float(o[j])) / rng) if rng > 0 else np.nan,
        "up_close_at": bool(float(c[j]) > float(o[j])),
        "close_gt_prev_high_at": bool(float(c[j]) > float(h[j - 1])),
        "engulf_at": bool(float(c[j]) > float(o[j]) and float(c[j - 1]) < float(o[j - 1])
                          and float(o[j]) <= float(c[j - 1]) and float(c[j]) >= float(o[j - 1])),
        "inside_at": bool(float(h[j]) <= float(h[j - 1]) and float(l[j]) >= float(l[j - 1])),
        "day_ret_at": day_ret,
        "weak_day_at": bool(day_ret == day_ret and WEAK_LO <= day_ret <= WEAK_HI),
    }


def volume_cols(v, c, j: int) -> dict:
    """Family 2 — volume at the touch and the dry-up before it."""
    up = dn = 0.0
    for t in range(max(1, j - POCKET_LOOKBACK), j):
        if float(c[t]) > float(c[t - 1]):
            up += float(v[t]) if np.isfinite(v[t]) else 0.0
        elif float(c[t]) < float(c[t - 1]):
            dn += float(v[t]) if np.isfinite(v[t]) else 0.0
    ref = v[max(0, j - RVOL_SHORT):j]
    ref = ref[np.isfinite(ref)]
    base = float(ref.mean()) if ref.size else np.nan
    slope = ((float(v[j]) - float(v[j - VOL_SLOPE_BARS])) / base
             if (j - VOL_SLOPE_BARS >= 0 and base == base and base > 0
                 and np.isfinite(v[j]) and np.isfinite(v[j - VOL_SLOPE_BARS])) else np.nan)
    return {"rvol20_at": ES._rvol(v, j, RVOL_SHORT),
            "rvol20_pre": ES._rvol(v, j - 1, RVOL_SHORT),
            "rvol50_pre": ES._rvol(v, j - 1, RVOL_LONG),
            "updn_vol10_pre": (up / dn) if dn > 0 else np.nan,
            "vol_slope3_at": slope}


def _sma_above(c, j: int, length: int) -> float:
    """c[j-1] > mean(c[j-1-length : j-1]) — the bars BEFORE the touch bar."""
    if j - 1 - length < 0:
        return np.nan
    w = np.asarray(c[j - 1 - length:j - 1], dtype=float)
    w = w[np.isfinite(w)]
    if w.size < length:
        return np.nan
    return bool(float(c[j - 1]) > float(w.mean()))


def features_for_symbol(sym: str, f: pd.DataFrame, ev: pd.DataFrame, hold: int, clocks,
                        geom: dict, counters: dict, rsp: Optional[dict] = None) -> list:
    pos_of = {d: i for i, d in enumerate(f["d"].tolist())}
    dates = f["d"].tolist()
    o = f["open"].to_numpy(dtype=float)
    h = f["high"].to_numpy(dtype=float)
    l = f["low"].to_numpy(dtype=float)
    c = f["close"].to_numpy(dtype=float)
    v = f["volume"].to_numpy(dtype=float)
    n = len(f)
    dvol = pd.Series(c * v).rolling(RVOL_LONG, min_periods=RVOL_LONG).median().to_numpy()
    max_clock = max(max(clocks), hold)
    buf = 1.0 - STOP_BUFFER_PCT / 100.0
    out = []
    for r in ev.itertuples(index=False):
        j = pos_of.get(str(r.date))
        if j is None or j < 2 or j + max_clock >= n:
            counters["no_bar"] += 1
            continue
        px, stop = float(r.entry), float(r.stop)
        target = _f(r.target)
        day_low = float(l[j])
        row = {"symbol": sym, "date": str(r.date), "bar_idx": j}
        # ── bands at j from bars STRICTLY BEFORE j (the engine's own call) ──
        z = PZ.compute(f.iloc[max(0, j - BOX_BARS):j], last_price=px, max_zones=None, **geom)
        dz = (z or {}).get("demand_zones") or []
        bands_all = ((z or {}).get("supply_zones") or []) + dz
        ea = event_at(o, h, l, c, j, bands_all)
        band = ea["band"] if ea else None
        if band is None:
            counters["no_band"] += 1
            band_lo = band_hi = None
        else:
            band_lo, band_hi = float(band["lo"]), float(band["hi"])
            if abs(band_lo * buf - stop) > 1e-6:
                counters["band_mismatch"] += 1
        served = ES.served_band(px, dz)
        row.update({"band_lo": band_lo if band_lo is not None else np.nan,
                    "band_hi": band_hi if band_hi is not None else np.nan,
                    "served_lo": served["lo"] if served else np.nan,
                    "served_hi": served["hi"] if served else np.nan,
                    "dvol50_pre": float(dvol[j - 1]) if np.isfinite(dvol[j - 1]) else np.nan})
        # ── families 1, 2 and the stratifiers ──
        row.update(candle_cols(o, h, l, c, j))
        row.update(volume_cols(v, c, j))
        row["gap_up_next"] = bool(float(o[j + 1]) > float(h[j]))
        row["above_sma50_pre"] = _sma_above(c, j, SMA_SHORT)
        row["above_sma200_pre"] = _sma_above(c, j, SMA_LONG)
        row["rs20_pre"] = np.nan
        if rsp:
            d1, d0 = str(dates[j - 1]), str(dates[j - 1 - RS_BARS]) if j - 1 - RS_BARS >= 0 else None
            b1, b0 = rsp.get(d1), rsp.get(d0) if d0 else None
            if b1 and b0 and b0 > 0 and float(c[j - 1 - RS_BARS]) > 0:
                row["rs20_pre"] = (float(c[j - 1]) / float(c[j - 1 - RS_BARS])) / (b1 / b0)
        st = intact_replica(f.iloc[:j], served["lo"], served["hi"], day_low, px) if served else None
        row["intact_state_at"] = st if st else np.nan
        row["intact_at"] = (st == "intact") if st else np.nan
        # ── P (the engine baseline) and every other convention ──
        fh = h[j + 1:j + 1 + max_clock]
        fl = l[j + 1:j + 1 + max_clock]
        fc = c[j + 1:j + 1 + max_clock]
        blk = ES.outcome_block(fh, fl, fc, px, stop, target, band_hi, clocks, hold)
        for cl in sorted(set(clocks) | {hold}):
            blk.pop("R%d" % cl)                  # the engine's R{cl}/why{cl} stay authoritative
            blk.pop("why%d" % cl)
        row.update(blk)
        row.update(convention_cols(o, h, l, c, j, n, stop, target, band_hi, clocks, hold))
        k1 = trigger_c1(o, h, l, c, j, stop, band_hi, max(C1_SWEEP_WINDOWS))[0]
        row["entry_bar_c1_sweep"] = float(k1) if k1 is not None else np.nan
        row["rvol_conf_C1"] = (ES._rvol(v, int(row["entry_bar_C1"]), RVOL_SHORT)
                               if row.get("fired_C1") else np.nan)
        out.append(row)
    return out


def rsp_closes(coll) -> Optional[dict]:
    """{date: close} for the equal-weight benchmark, or None when it is not cached
    (then `rs20_pre` is all-NaN and the report says so)."""
    try:
        f = ES.frame_with_tail_rule(coll, RS_SYMBOL)
    except Exception:                                            # noqa: BLE001
        return None
    if f is None or len(f) == 0:
        return None
    return {str(d): float(x) for d, x in zip(f["d"].tolist(), f["close"].tolist())}


def add_features(E: pd.DataFrame, hold: int, clocks, counters: dict) -> pd.DataFrame:
    coll = prices._get_mongo()
    geom = DR.zone_geom()
    rsp = rsp_closes(coll)
    if rsp is None:
        counters["no_rsp"] = counters.get("no_rsp", 0) + 1
    rows = []
    for sym, ev in E.groupby("symbol", sort=True):
        f = ES.frame_with_tail_rule(coll, sym)
        if f is None:
            counters["no_frame"] += 1
            continue
        rows.extend(features_for_symbol(sym, f, ev, hold, clocks, geom, counters, rsp))
    F = pd.DataFrame(rows)
    X = ES.join_features(E, F)
    X["bar_idx"] = pd.to_numeric(X["bar_idx"], errors="coerce")
    X["episode"] = ES.flag_episodes(X, hold)
    X["episode_dir"] = ES.flag_episodes(X, hold, within="dir")
    return X


# ═════════════════════════════════════════════════════════════════════════════
# STAGE: replay
# ═════════════════════════════════════════════════════════════════════════════
def replay(a) -> None:
    t0 = time.time()
    clocks = tuple(int(x) for x in str(a.clocks).split(","))
    hold, floor = int(a.hold), int(a.floor)
    need = floor + hold + 2
    syms = ES.symbols_for(a.universe, need, stride=a.stride, names=a.names)
    if a.names or a.stride > 1:
        P("NOT QUOTABLE — smoke (--stride %d --names %d)" % (a.stride, a.names))
    BQ.CLOCKS = clocks
    BQ._frame = ES.frame_with_tail_rule
    P("replay  universe=%s  n=%d  floor=%d  hold=%d  clocks=%s  stride=%d  min_dvol=%g  today=%s"
      % (a.universe, len(syms), floor, hold, clocks, a.stride, a.min_dvol, _today_et()))
    counters = {"no_bar": 0, "no_band": 0, "band_mismatch": 0, "no_frame": 0}
    n_rows, first = 0, True
    chunk = max(1, int(a.chunk))
    if os.path.exists(a.out):
        os.remove(a.out)
    for k0 in range(0, len(syms), chunk):
        part = syms[k0:k0 + chunk]
        BQ.universe = types.SimpleNamespace(load_universe=lambda uni=None, ch=part: list(ch))
        E = BQ.events(hold, floor, 0, float(a.min_dvol), a.universe)
        if E.empty:
            continue
        X = add_features(E, hold, clocks, counters)
        X.to_csv(a.out, index=False, mode="a", header=first)
        first = False
        n_rows += len(X)
        P("  chunk %d..%d  events=%d  total=%d  %.0fs"
          % (k0, k0 + len(part), len(X), n_rows, time.time() - t0))
    meta = {"universe_mode": a.universe, "n_universe": len(syms), "symbols": syms,
            "n_frames": ES.TAIL["names"], "tail": dict(ES.TAIL), "counters": counters,
            "clocks": list(clocks), "floor": floor, "hold": hold, "today": _today_et(),
            "n_rows": n_rows, "walltime_s": round(time.time() - t0, 1),
            "stride": a.stride, "names": a.names, "min_dvol": a.min_dvol}
    with open(a.out + ".meta.json", "w") as fh:
        json.dump(meta, fh)
    P("replay done  rows=%d  frames=%d  counters=%s  %.0fs"
      % (n_rows, ES.TAIL["names"], counters, time.time() - t0))


# ═════════════════════════════════════════════════════════════════════════════
# THE ONE STATISTIC ES LACKS — a pooled multi-cell conditional delta
# ═════════════════════════════════════════════════════════════════════════════
def cond_boot(D: pd.DataFrame, ycols: dict, base_masks: dict, kept_masks: dict,
              weights: dict, draws: int, seed: int = SEED_BOOT) -> np.ndarray:
    """Bootstrap draws of `Σ_k w_k · (mean(kept_k) − mean(base_k))` with ONE date
    resample per draw SHARED across every fire bar k (the cells overlap: a row can
    sit in base_1 and base_2). Sums and counts per date come from `ES._by_key`, so
    this is `cluster_boot`'s construction lifted to several cells at once. A draw
    where any cell loses its whole denominator is dropped."""
    ks = sorted(ycols)
    if not ks or D.empty:
        return np.array([])
    keys = np.array(sorted(D["date"].unique()))
    n = len(keys)
    if n < 3:
        return np.array([])
    BS, BC, KS, KC, W = [], [], [], [], []
    for k in ks:
        col = ycols[k]
        bs, bc = ES._by_key(D[base_masks[k]], keys, col, "date")
        kks, kc = ES._by_key(D[kept_masks[k]], keys, col, "date")
        BS.append(bs)
        BC.append(bc)
        KS.append(kks)
        KC.append(kc)
        W.append(float(weights[k]))
    BS, BC, KS, KC = (np.vstack(x) for x in (BS, BC, KS, KC))
    W = np.asarray(W, dtype=float)
    rng = np.random.default_rng(seed)
    out = []
    step = max(1, int(4_000_000 // max(n * len(ks), 1)))
    done = 0
    while done < draws:
        m = min(step, draws - done)
        idx = rng.integers(0, n, size=(m, n))
        bn = np.stack([BS[i][idx].sum(1) for i in range(len(ks))])       # (K, m)
        bd = np.stack([BC[i][idx].sum(1) for i in range(len(ks))])
        kn = np.stack([KS[i][idx].sum(1) for i in range(len(ks))])
        kd = np.stack([KC[i][idx].sum(1) for i in range(len(ks))])
        ok = (bd > 0).all(0) & (kd > 0).all(0)
        if ok.any():
            with np.errstate(invalid="ignore", divide="ignore"):
                d = (W[:, None] * (kn / np.maximum(kd, 1) - bn / np.maximum(bd, 1))).sum(0)
            out.append(d[ok])
        done += m
    return np.concatenate(out) if out else np.array([])


def cond_mdl(D: pd.DataFrame, ycols: dict, base_masks: dict, keep_n: dict, weights: dict,
             draws: int, seed: int = SEED_PLACEBO) -> float:
    """The study's RESOLUTION on `d_cond`: 1.96 x the SD of `cond_boot` under a
    RANDOM RELABEL — for each k a random subset of base_k of size |kept_k| stands
    in for kept_k (ES deviation #5, "random keep", carried to the pooled delta)."""
    rng = np.random.default_rng(seed)
    fake = {}
    for k in sorted(ycols):
        base = base_masks[k]
        idx = np.flatnonzero(base.to_numpy(dtype=bool))
        want = int(min(keep_n.get(k, 0), len(idx)))
        if want <= 0:
            return float("nan")
        pick = rng.choice(idx, size=want, replace=False)
        m = pd.Series(False, index=D.index)
        m.iloc[pick] = True
        fake[k] = m
    d = cond_boot(D, ycols, base_masks, fake, weights, draws, seed=SEED_BOOT)
    return float(1.96 * d.std(ddof=1)) if d.size >= 100 else float("nan")


# ═════════════════════════════════════════════════════════════════════════════
# CONVENTIONS — cells, the conditional contrast, the policy view
# ═════════════════════════════════════════════════════════════════════════════
def policy_cols(D: pd.DataFrame, key: str, hold: int) -> pd.DataFrame:
    """The miss is priced: R/hit5/stop = the convention's own when it fired, 0.0
    when it did not. DERIVED here, never written to the CSV (deviation #5)."""
    sfx = "_" + key
    fired = D["fired" + sfx].fillna(False).astype(bool) if ("fired" + sfx) in D else \
        pd.Series(False, index=D.index)
    out = {}
    for stem, col in (("R%d_policy" % hold, "R%d%s" % (hold, sfx)),
                      ("hit5_%d_policy" % hold, "hit5_%d%s" % (hold, sfx)),
                      ("stop_%d_policy" % hold, "stop_%d%s" % (hold, sfx))):
        v = pd.to_numeric(D[col], errors="coerce") if col in D else pd.Series(np.nan, index=D.index)
        out[stem + sfx] = v.where(fired, 0.0).fillna(0.0)
    return pd.DataFrame(out, index=D.index)


def add_policy(D: pd.DataFrame, keys, hold: int) -> pd.DataFrame:
    """ONLY the policy columns, index-aligned — never a copy of the wide event
    table (~290 columns x ~150k rows would not fit twice in the container)."""
    parts = [policy_cols(D, k, hold) for k in dict.fromkeys(keys)]
    return pd.concat(parts, axis=1)


def _ydf(D: pd.DataFrame, y, with_symbol: bool = False) -> pd.DataFrame:
    """The narrow (date[, symbol], y) frame every cluster bootstrap actually
    reads. Keeps the wide table out of every resample and every mask select."""
    cols = {"date": D["date"].to_numpy()}
    if with_symbol:
        cols["symbol"] = D["symbol"].to_numpy()
    cols["y"] = pd.to_numeric(pd.Series(np.asarray(y, dtype=float)), errors="coerce").to_numpy()
    return pd.DataFrame(cols, index=D.index)


def cond_cells(D: pd.DataFrame, key: str, W: int, hold: int) -> dict:
    """base_k = rows that reached bar k unstopped (fired_Dk); kept_k = rows where
    THIS convention fired FIRST at k. kept ⊂ base (the identity)."""
    sfx = "_" + key
    cells, keep_n, dropped = {}, {}, []
    fired = D["fired" + sfx].fillna(False).astype(bool) if ("fired" + sfx) in D else \
        pd.Series(False, index=D.index)
    kbar = pd.to_numeric(D.get("entry_bar" + sfx), errors="coerce") - \
        pd.to_numeric(D.get("bar_idx"), errors="coerce")
    for k in range(1, W + 1):
        bcol = "fired_D%d" % k
        if bcol not in D:
            continue
        base = D[bcol].fillna(False).astype(bool)
        kept = base & fired & (kbar == k)
        cells[k] = (base, kept)
        keep_n[k] = int(kept.sum())
    ks = []
    for k, (base, kept) in cells.items():
        if int(kept.sum()) < MIN_CELL_N or int(base.sum()) < MIN_CELL_N:
            if int(kept.sum()):
                dropped.append(k)
            continue
        ks.append(k)
    tot = float(sum(keep_n[k] for k in ks))
    weights = {k: keep_n[k] / tot for k in ks} if tot else {}
    return {"cells": cells, "ks": ks, "weights": weights, "dropped_k": sorted(dropped),
            "keep_n": keep_n, "n_fired": int(fired.sum()),
            "n_base_k": {k: int(cells[k][0].sum()) for k in cells}}


def pooled_delta(D: pd.DataFrame, cl: dict, col_tpl: str) -> float:
    if not cl["ks"]:
        return float("nan")
    d = 0.0
    for k in cl["ks"]:
        base, kept = cl["cells"][k]
        col = col_tpl % k
        if col not in D:
            return float("nan")
        d += cl["weights"][k] * (_nanmean(D.loc[kept, col]) - _nanmean(D.loc[base, col]))
    return float(d)


def _cell_args(D, cl, col_tpl):
    ycols = {k: col_tpl % k for k in cl["ks"]}
    base = {k: cl["cells"][k][0] for k in cl["ks"]}
    kept = {k: cl["cells"][k][1] for k in cl["ks"]}
    return ycols, base, kept


def cond_block(D: pd.DataFrame, key: str, W: int, hold: int, a, primary: str) -> dict:
    """(i), (v), (vi), (viii) of §3A for one convention on one cohort."""
    cl = cond_cells(D, key, W, hold)
    out = {"n_base_k": cl["n_base_k"], "dropped_k": cl["dropped_k"],
           "n_fired": cl["n_fired"], "pooled_k": cl["ks"]}
    if not cl["ks"]:
        out.update({"d_cond": None, "ci_cond": [None, None], "mdl_cond": None,
                    "d_stop_cond": None, "ci_stop_cond": [None, None],
                    "d_cond_reweighted": None, "ci_rw": [None, None],
                    "one_per_date": None, "one_per_symbol": None,
                    "contrast": "no pooled fire bar reached %d rows — contrast undefined" % MIN_CELL_N})
        return out
    hit_tpl = "%s_%d_D%%d" % (primary, hold)
    stop_tpl = "stop_%d_D%%d" % hold
    d = pooled_delta(D, cl, hit_tpl)
    need = [hit_tpl % k for k in cl["ks"]] + [stop_tpl % k for k in cl["ks"]]
    small = pd.DataFrame({"date": D["date"].to_numpy(), "symbol": D["symbol"].to_numpy(),
                          **{c: pd.to_numeric(D[c], errors="coerce").to_numpy() for c in need}},
                         index=D.index)
    ycols, base_m, kept_m = _cell_args(D, cl, hit_tpl)
    boot = cond_boot(small, ycols, base_m, kept_m, cl["weights"], a.boot_draws)
    ci = ([float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]
          if boot.size >= 100 else [None, None])
    mdl = cond_mdl(small, ycols, base_m, cl["keep_n"], cl["weights"], a.placebo_draws)
    ds = pooled_delta(D, cl, stop_tpl)
    yc2, b2, k2 = _cell_args(D, cl, stop_tpl)
    boot_s = cond_boot(small, yc2, b2, k2, cl["weights"], a.boot_draws)
    ci_s = ([float(np.percentile(boot_s, 2.5)), float(np.percentile(boot_s, 97.5))]
            if boot_s.size >= 100 else [None, None])
    # (vi) room x risk reweight per k, pooled with the fire weights
    rw_d, rw_lo, rw_hi, w_used = 0.0, 0.0, 0.0, 0.0
    for k in cl["ks"]:
        base, kept = cl["cells"][k]
        room_col, risk_col = "room_pct_D%d" % k, "risk_pct_D%d" % k
        if room_col not in D or risk_col not in D:
            continue
        col = hit_tpl % k
        Dk = pd.DataFrame({"date": D.loc[base, "date"].to_numpy(),
                           "room_pct": pd.to_numeric(D.loc[base, room_col], errors="coerce").to_numpy(),
                           risk_col: pd.to_numeric(D.loc[base, risk_col], errors="coerce").to_numpy(),
                           col: pd.to_numeric(D.loc[base, col], errors="coerce").to_numpy()},
                          index=D.index[base])
        mask = kept[base]
        r = ES.reweight_delta(Dk, mask, col, risk_col, a.boot_draws)
        if r["delta"] != r["delta"]:
            continue
        w = cl["weights"][k]
        rw_d += w * r["delta"]
        rw_lo += w * (r["lo"] if r["lo"] == r["lo"] else 0.0)
        rw_hi += w * (r["hi"] if r["hi"] == r["hi"] else 0.0)
        w_used += w
    # (viii) one-per-date / one-per-symbol point deltas
    d1 = s1 = 0.0
    for k in cl["ks"]:
        base, kept = cl["cells"][k]
        col = hit_tpl % k
        a1, b1 = ES.dedupe_deltas(_ydf(D[["date", "symbol"]][base], D.loc[base, col], True),
                                  _ydf(D[["date", "symbol"]][kept], D.loc[kept, col], True), "y")
        d1 += cl["weights"][k] * a1
        s1 += cl["weights"][k] * b1
    out.update({"d_cond": 100.0 * d, "ci_cond": [100.0 * ci[0], 100.0 * ci[1]] if ci[0] is not None else [None, None],
                "mdl_cond": 100.0 * mdl if mdl == mdl else None,
                "d_stop_cond": 100.0 * ds,
                "ci_stop_cond": [100.0 * ci_s[0], 100.0 * ci_s[1]] if ci_s[0] is not None else [None, None],
                "d_cond_reweighted": 100.0 * rw_d / w_used if w_used else None,
                "ci_rw": [100.0 * rw_lo / w_used, 100.0 * rw_hi / w_used] if w_used else [None, None],
                "one_per_date": 100.0 * d1, "one_per_symbol": 100.0 * s1,
                "contrast": "fired vs unfired survivors at the same bar"})
    return out


def excluded_skips(D_full: pd.DataFrame, kept, reason_col: str, fallback: str) -> dict:
    """The episodes a convention's own frame NEVER SAW, counted by their own
    `skip_reason` (DEVIATION #3). `kept` is the boolean mask of D_full that the
    convention was scored on; everything else is a skip, not a silent drop."""
    drop = D_full[~np.asarray(kept, dtype=bool)]
    if not len(drop):
        return {}
    if reason_col not in drop:
        return {fallback: int(len(drop))}
    sr = drop[reason_col].where(drop[reason_col].notna(), fallback)
    return {str(k): int(v) for k, v in sr.value_counts().items()}


def convention_block(D: pd.DataFrame, key: str, hold: int, clocks, a, primary: str,
                     with_splits: bool = True, base_n: Optional[int] = None,
                     excluded: Optional[dict] = None) -> dict:
    """Every number §3A asks for on one convention, on the bouncing episodes.

    `base_n` / `excluded` (DEVIATION #3): when the convention is scored on a SUBSET
    of the episode cohort — N is scored on `gap_N == False` — the fire rate is still
    reported over the FULL base and the episodes that never entered the frame are
    counted in `n_skipped` under their own reason, so `n_fired + Σ n_skipped` closes
    on `n_base` instead of quietly disappearing."""
    sfx = "_" + key
    hit_c = "%s_%d%s" % (primary, hold, sfx)
    hitP = "%s_%d" % (primary, hold)
    stop_c, stopP = "stop_%d%s" % (hold, sfx), "stop_%d" % hold
    R_c, RP = "R%d%s" % (hold, sfx), "R%d" % hold
    W = TRIGGER_WINDOW.get(key, max(DELAYS_PLACEBO))
    fired = D["fired" + sfx].fillna(False).astype(bool)
    K = D[fired]
    n_base = int(base_n) if base_n is not None else len(D)
    out = {"n_fired": int(fired.sum()), "n_base": n_base,
           "fire_rate": (float(fired.sum()) / n_base) if n_base else None,
           "window_bars": W if key in TRIGGER_KEYS else None}
    kbar = pd.to_numeric(D.get("entry_bar" + sfx), errors="coerce") - pd.to_numeric(D["bar_idx"], errors="coerce")
    out["fire_bar_dist"] = {str(int(k)): int(n) for k, n in kbar[fired].value_counts().sort_index().items()}
    sk = D["skip_reason" + sfx] if ("skip_reason" + sfx) in D else pd.Series(dtype=object)
    skipped = {str(k): int(v) for k, v in sk.dropna().value_counts().items()}
    for reason, n_ in (excluded or {}).items():
        skipped[str(reason)] = skipped.get(str(reason), 0) + int(n_)
    out["n_skipped"] = skipped
    if key == "C2":
        out["c2_na"] = int(D["c2_na"].fillna(False).astype(bool).sum()) if "c2_na" in D else None
    if out["n_fired"] < MIN_CELL_N:
        out["verdict"] = "n<%d — not shown" % MIN_CELL_N
        return out
    R = pd.to_numeric(K[R_c], errors="coerce").to_numpy(dtype=float)
    lid = pd.to_numeric(K["hit_lid_%d%s" % (hold, sfx)], errors="coerce") if \
        ("hit_lid_%d%s" % (hold, sfx)) in K else pd.Series(dtype=float)
    out.update({
        "hit5_20": 100.0 * _nanmean(K[hit_c]), "stop_20": 100.0 * _nanmean(K[stop_c]),
        "hit_lid_20": 100.0 * _nanmean(lid) if len(lid) else None,
        "n_lid": int(lid.notna().sum()) if len(lid) else 0,
        "R20": _nanmean(R), "R20_median": float(np.nanmedian(R)) if R.size else None,
        "R20_trim": ES.trimmed_mean(R),
        "room_pct": _nanmean(K["room_pct" + sfx]), "risk_pct": _nanmean(K["risk_pct" + sfx]),
    })
    out["room_risk"] = (out["room_pct"] / out["risk_pct"]
                        if out["risk_pct"] and out["risk_pct"] == out["risk_pct"] else None)
    # (i) (v) (vi) (viii) — the conditional contrast
    if key in TRIGGER_KEYS:
        out.update(cond_block(D, key, W, hold, a, primary))
    else:
        out.update({"d_cond": None, "ci_cond": [None, None], "mdl_cond": None,
                    "d_stop_cond": None, "ci_stop_cond": [None, None],
                    "d_cond_reweighted": None, "ci_rw": [None, None],
                    "one_per_date": None, "one_per_symbol": None,
                    "contrast": ("unconditional delay — kept == base by construction"
                                 if key.startswith("D") else
                                 "no fire bar — the deciding lift is the paired delta")})
    # (ii) paired: X vs P on the SAME rows
    diff = pd.to_numeric(K[hit_c], errors="coerce") - pd.to_numeric(K[hitP], errors="coerce")
    out["d_paired"] = 100.0 * _nanmean(diff)
    pb = ES.cluster_boot(_ydf(K, np.zeros(len(K))), _ydf(K, diff), "y", "date", a.boot_draws)
    out["ci_paired"] = ([100.0 * float(np.percentile(pb, 2.5)), 100.0 * float(np.percentile(pb, 97.5))]
                        if pb.size >= 100 else [None, None])
    out["mdl_paired"] = 100.0 * 1.96 * float(pb.std(ddof=1)) if pb.size >= 100 else None
    # (iii) raw — REPORTED, never a condition
    out["d_raw"] = 100.0 * (_nanmean(K[hit_c]) - _nanmean(D[hitP]))
    rb = ES.cluster_boot(_ydf(D, pd.to_numeric(D[hitP], errors="coerce")),
                         _ydf(K, pd.to_numeric(K[hit_c], errors="coerce")), "y", "date",
                         a.boot_draws)
    out["ci_raw"] = ([100.0 * float(np.percentile(rb, 2.5)), 100.0 * float(np.percentile(rb, 97.5))]
                     if rb.size >= 100 else [None, None])
    out["raw_note"] = "includes survival to bar k (not a trigger effect)"
    # (iv) what WAITING alone buys, same survivorship
    cl = cond_cells(D, key, W, hold) if key in TRIGGER_KEYS else None
    dd = {}
    for k in (cl["ks"] if cl else []):
        base = cl["cells"][k][0]
        col = "%s_%d_D%d" % (primary, hold, k)
        dd[str(k)] = 100.0 * (_nanmean(D.loc[base, col]) - _nanmean(D[hitP]))
    out["d_delay_only"] = dd
    if cl and cl["ks"]:
        pooled_delay = sum(cl["weights"][k] * dd[str(k)] for k in cl["ks"])
        out["decomp_gap"] = (out["d_raw"] - pooled_delay - (out.get("d_cond") or 0.0))
    else:
        out["decomp_gap"] = None
    # (vii) the policy view
    Dp = add_policy(D, [key] + ["D%d" % k for k in DELAYS_PLACEBO], hold)
    pol = "R%d_policy%s" % (hold, sfx)
    out["policy_R20"] = float(Dp[pol].mean())
    out["policy_R20_P"] = _nanmean(D[RP])
    out["d_policy_R"] = out["policy_R20"] - out["policy_R20_P"]
    cb = ES.cluster_boot(_ydf(D, pd.to_numeric(D[RP], errors="coerce")),
                         _ydf(D, Dp[pol]), "y", "date", a.boot_draws)
    out["ci_policy_R"] = ([float(np.percentile(cb, 2.5)), float(np.percentile(cb, 97.5))]
                          if cb.size >= 100 else [None, None])
    if cl and cl["ks"]:
        wait = sum(cl["weights"][k] * float(Dp["R%d_policy_D%d" % (hold, k)].mean()) for k in cl["ks"])
        out["d_policy_R_vs_delay"] = out["policy_R20"] - wait
    else:
        out["d_policy_R_vs_delay"] = None
    # OOS x 3
    out["splits"] = {}
    if with_splits:
        for name, mask in split_masks(D):
            Ds = D[mask]
            s = {"name": name, "n_scored": int(len(Ds))}
            if key in TRIGGER_KEYS:
                s.update({k: v for k, v in cond_block(Ds, key, W, hold, a, primary).items()
                          if k in ("d_cond", "ci_cond", "mdl_cond")})
            else:
                Ks = Ds[Ds["fired" + sfx].fillna(False).astype(bool)]
                dfs = pd.to_numeric(Ks[hit_c], errors="coerce") - pd.to_numeric(Ks[hitP], errors="coerce")
                s["d_paired"] = 100.0 * _nanmean(dfs)
                b = ES.cluster_boot(_ydf(Ks, np.zeros(len(Ks))), _ydf(Ks, dfs), "y", "date",
                                    a.boot_draws)
                s["ci_paired"] = ([100.0 * float(np.percentile(b, 2.5)),
                                   100.0 * float(np.percentile(b, 97.5))] if b.size >= 100 else [None, None])
                s["mdl_paired"] = 100.0 * 1.96 * float(b.std(ddof=1)) if b.size >= 100 else None
                s.update({"d_cond": None, "ci_cond": [None, None], "mdl_cond": None})
            Dps = add_policy(Ds, [key], hold)
            s["d_policy_R"] = float(Dps[pol].mean()) - _nanmean(Ds[RP])
            s["verdict"] = split_verdict(s, key)
            out["splits"][name.split()[0]] = s
    out["conditions"] = convention_conditions(out, key)
    out["verdict"] = ("separates" if all(out["conditions"].values()) else "no_signal")
    return out


def split_masks(D: pd.DataFrame) -> list:
    ds = sorted(D["date"].unique())
    in_h1 = D["date"].isin(set(ds[:len(ds) // 2]))
    parity = D["symbol"].map(lambda s: zlib.crc32(str(s).encode()) % 2)
    return [("s1 date H2 (score H2)", ~in_h1), ("s2 date H1 (score H1)", in_h1),
            ("s3 symbol parity 1", parity == 1)]


def split_verdict(s: dict, key: str) -> str:
    if key in TRIGGER_KEYS:
        d, ci, mdl = s.get("d_cond"), s.get("ci_cond") or [None, None], s.get("mdl_cond")
    else:
        d, ci, mdl = s.get("d_paired"), s.get("ci_paired") or [None, None], s.get("mdl_paired")
    if d is None or ci[0] is None:
        return "n<%d — not shown" % MIN_CELL_N
    if ci[0] > 0 and mdl is not None and d >= mdl:
        return "separates"
    return "no_signal"


def convention_conditions(out: dict, key: str) -> dict:
    """The pre-registered selection rule (a)-(f), §3A."""
    ci = out.get("ci_cond") or [None, None]
    cis = out.get("ci_stop_cond") or [None, None]
    rw = out.get("ci_rw") or [None, None]
    pol = out.get("ci_policy_R") or [None, None]
    splits = list((out.get("splits") or {}).values())
    if key in TRIGGER_KEYS:
        d, mdl = out.get("d_cond"), out.get("mdl_cond")
        a_ = bool(d is not None and ci[0] is not None and ci[0] > 0
                  and mdl is not None and d >= mdl)      # no MDL = no resolution = no claim
        b_ = not (cis[0] is not None and cis[0] > 0)
        c_ = bool(out.get("d_cond_reweighted") is not None and out["d_cond_reweighted"] > 0
                  and rw[0] is not None and rw[0] > 0)
        d_ = bool(out.get("d_policy_R") is not None and out["d_policy_R"] >= 0
                  and not (pol[1] is not None and pol[1] < 0)
                  and (out.get("d_policy_R_vs_delay") or 0.0) > 0)
        e_ = bool((out.get("one_per_date") or 0.0) > 0 and (out.get("one_per_symbol") or 0.0) > 0)
        f_ = bool(splits and all(s.get("verdict") == "separates" for s in splits))
        return {"a_cond_beats_mdl": a_, "b_stop_not_raised": b_, "c_reweighted_sign": c_,
                "d_policy_not_worse": d_, "e_one_per_date_symbol": e_, "f_all_three_splits": f_}
    d, mdl = out.get("d_paired"), out.get("mdl_paired")
    cip = out.get("ci_paired") or [None, None]
    a_ = bool(d is not None and cip[0] is not None and cip[0] > 0
              and mdl is not None and d >= mdl)
    d_ = bool(out.get("d_policy_R") is not None and out["d_policy_R"] >= 0)
    f_ = bool(splits and all(s.get("verdict") == "separates" for s in splits))
    return {"a_paired_beats_mdl": a_, "d_policy_not_worse": d_, "f_all_three_splits": f_}


def ship_eligible(convention: str) -> bool:
    """PC is PRINT-ONLY: a bar-j shape is not knowable when an MOC order is placed."""
    return convention in SHIP_ELIGIBLE_CONVENTIONS


def select_survivor(convs: dict, per_feature: list, splits_features: dict) -> tuple:
    """The pre-registered decision. Conventions C1/C2/HL/L1 need (a)-(f); N needs
    its paired rule; a FEATURE bucket needs `separates` on all three splits under a
    SHIP-ELIGIBLE convention (never PC). Largest `d_policy_R` ships."""
    selected, cands = [], []
    for key in TRIGGER_KEYS + ("N",):
        r = convs.get(key) or {}
        cond = r.get("conditions") or {}
        if cond and all(cond.values()):
            selected.append(key)
            cands.append({"key": key, "type": "convention",
                          "definition": CONV_DEFINITION.get(key, key),
                          "entry": CONV_ENTRY.get(key, "close[k]"),
                          "window_bars": r.get("window_bars"),
                          "d_cond": r.get("d_cond"), "ci_cond": r.get("ci_cond"),
                          "mdl_cond": r.get("mdl_cond"), "d_paired": r.get("d_paired"),
                          "d_policy_R": r.get("d_policy_R"), "fire_rate": r.get("fire_rate"),
                          "splits": r.get("splits")})
    for p in per_feature:
        p["ship_eligible"] = bool(ship_eligible(p.get("convention")))
    for conv, sp in (splits_features or {}).items():
        if not ship_eligible(conv):
            continue
        vs = [(sp.get(k) or {}).get("verdict") for k in ("s1", "s2", "s3")]
        if vs and all(v == "separates" for v in vs):
            for feat in ((sp.get("s1") or {}).get("selected") or []):
                selected.append("%s:%s" % (conv, feat))
                cands.append({"key": feat, "type": "feature", "definition": feat,
                              "entry": "close[j]" if conv == "P" else "open[j+1]",
                              "window_bars": None, "d_cond": None, "ci_cond": [None, None],
                              "mdl_cond": (sp.get("s1") or {}).get("mdl"),
                              "d_policy_R": None, "fire_rate": None, "splits": sp})
    if not cands:
        return [], None
    best = max(cands, key=lambda cd: (cd.get("d_policy_R") if cd.get("d_policy_R") is not None else -1e9))
    return selected, best


CONV_DEFINITION = {
    "C1": "first close above the touch bar's high within %d bars, floor never broken" % C_WINDOW_BARS,
    "C2": "first close back above the band top within %d bars, floor never broken" % C_WINDOW_BARS,
    "HL": "a confirmed higher low within %d bars (second touch held)" % HL_WINDOW_BARS,
    "L1": "first close at/above the print +%.1f%% within %d bars" % (LIFT_PCT, C_WINDOW_BARS),
    "N": "enter at the next open",
}
CONV_ENTRY = {"C1": "close[k]", "C2": "close[k]", "HL": "close[k]", "L1": "close[k]",
              "N": "open[j+1]", "PC": "close[j]"}


# ═════════════════════════════════════════════════════════════════════════════
# STAGE: stats
# ═════════════════════════════════════════════════════════════════════════════
def conventions(primary: str, hold: int) -> dict:
    """ES's P and N, plus PC (the MOC twin, PRINT-ONLY), with this study's sets."""
    base = ES.conventions(primary, hold)
    base["P"]["feats"] = PREREG_P_TRIG
    base["N"]["feats"] = PREREG_N_TRIG
    base["PC"] = {
        "tag": "PC", "label": "PC (same-close read: _at features, entry close[j]) — PRINT-ONLY",
        "hit": "%s_%d_PC" % (primary, hold), "hit5": "hit5_%d_PC" % hold,
        "hit5b": "hit5b_%d_PC" % hold, "hit_lid": "hit_lid_%d_PC" % hold,
        "stop": "stop_%d_PC" % hold, "R": "R%d_PC" % hold, "why": "why%d_PC" % hold,
        "risk": "risk_pct_PC", "feats": PREREG_PC_TRIG, "suffix": "_PC"}
    return base


def wanted_columns(clocks, hold: int, primary: str) -> list:
    """Only what §3A reads — the CSV is ~260 columns wide and the container has
    ~750 MB (ES.load_events takes an explicit list)."""
    cols = ["symbol", "date", "dir", "entry", "stop", "target", "room_pct", "clear",
            "risk_pct", "R", "why", "knife", "mood", "episode", "episode_dir", "bar_idx",
            "band_lo", "band_hi", "served_lo", "served_hi", "dvol50_pre",
            "entry_bar_c1_sweep", "rvol_conf_C1", "c2_na"]
    for cl in sorted(set(clocks) | {hold}):
        cols += ["R%d" % cl, "why%d" % cl, "pct%d" % cl]
    cols += list(dict.fromkeys(PREREG_N_TRIG + PREREG_PC_TRIG + PREREG_P_TRIG
                               + STRATIFIERS + EXPLORATORY))
    cols += block_keys("full", clocks, hold, "")
    for key in ALL_CONV_KEYS:
        sfx = "_" + key
        cols += block_keys(conv_kind(key), clocks, hold, sfx)
        cols += ["fired" + sfx, "entry" + sfx, "entry_bar" + sfx, "skip_reason" + sfx,
                 "risk_pct" + sfx, "room_pct" + sfx, "target_passed" + sfx]
    cols += ["gap_N"]
    return list(dict.fromkeys(cols))


def load_events(path: str, clocks, hold: int, primary: str) -> pd.DataFrame:
    return ES.load_events(path, columns=wanted_columns(clocks, hold, primary))


def feature_table(D: pd.DataFrame, conv: dict, a, clocks, hold: int, feats,
                  per_feature: list, label: str) -> None:
    """ES's per-feature bucket machinery, with the study's 120-row cell floor."""
    if len(D) < MIN_CELL_N:
        P("  cohort too small (n=%d)" % len(D))
        return
    base = ES.bucket_stats(D, D, conv, clocks, hold)
    for feat in feats:
        if feat not in D:
            P("  %s: column missing" % feat)
            continue
        kind = ES.feat_kind(feat)
        lab, order, edges = ES.assign_buckets(D[feat], kind)
        o = ES.orientation(D, feat, kind, lab, order, conv["hit"])
        top = ES.top_bucket(lab, order, kind, o, D, conv["hit"])
        mask = lab == top
        P("  %s [%s] orientation %+d (top = %s) n=%d" % (feat, kind, o, top, int(mask.sum())))
        if int(mask.sum()) < MIN_CELL_N or int((~mask).sum()) < MIN_CELL_N:
            P("      -> n<%d — not shown" % MIN_CELL_N)
            per_feature.append({"name": feat, "convention": conv["tag"], "kind": kind,
                                "orientation": o, "ship_eligible": ship_eligible(conv["tag"]),
                                "top": {"label": top, "n": int(mask.sum()),
                                        "verdict": "n<%d — not shown" % MIN_CELL_N}})
            continue
        P(ES.fmt_row("base", base))
        P(ES.fmt_row(str(top), ES.bucket_stats(D, D[mask], conv, clocks, hold)))
        r = ES.evaluate_bucket(D, mask, conv, a, base)
        P(ES.fmt_eval(r))
        per_feature.append({"name": feat, "convention": conv["tag"], "kind": kind,
                            "orientation": o, "ship_eligible": ship_eligible(conv["tag"]),
                            "top": {"label": top, **{k: r.get(k) for k in (
                                "n", "d_hit5", "ci", "p_le0", "d_stop", "ci_stop", "d_R", "ci_R",
                                "d_hit5_reweighted", "ci_rw", "perm_p", "placebo_dates",
                                "placebo_iid", "one_per_date", "one_per_symbol", "room_risk",
                                "room_risk_base", "d_risk", "conditions", "verdict")}}})


def interactions(D: pd.DataFrame, a, hold: int, primary: str, per_feature: list) -> list:
    """Family 5 — intact x (top candle bucket under N) and intact x fired_C1."""
    out = []
    hitN = "%s_%d_N" % (primary, hold)
    if "intact_at" not in D:
        return out
    intact = D["intact_at"] == True                                         # noqa: E712
    cand = None
    for p in per_feature:
        if p.get("convention") == "N" and p["name"] in PREREG_N_TRIG and p["name"] != "intact_at":
            top = p.get("top") or {}
            if top.get("d_hit5") is not None and (cand is None or top["d_hit5"] > cand[1]):
                cand = (p["name"], top["d_hit5"], top.get("label"))
    if cand and cand[0] in D:
        lab, order, _ = ES.assign_buckets(D[cand[0]], ES.feat_kind(cand[0]))
        m = lab == cand[2]
        for name, cell in (("intact x %s=%s" % (cand[0], cand[2]), intact & m),
                           ("not-intact x %s=%s" % (cand[0], cand[2]), (~intact) & m)):
            out.append(_inter_cell(D, name, cell, hitN, hold, a))
    if "fired_C1" in D:
        fired = D["fired_C1"].fillna(False).astype(bool)
        for name, sub in (("intact x fired_C1", intact), ("not-intact x fired_C1", ~intact)):
            Ds = D[sub]
            if len(Ds) < MIN_CELL_N:
                out.append({"name": name, "n": int(len(Ds)), "verdict": "n<%d — not shown" % MIN_CELL_N})
                continue
            cb = cond_block(Ds, "C1", C_WINDOW_BARS, hold, a, primary)
            out.append({"name": name, "cell": "fired", "n": int(fired[sub].sum()),
                        "hit5_20": 100.0 * _nanmean(Ds.loc[fired[sub], "%s_%d_C1" % (primary, hold)]),
                        "d_cond": cb.get("d_cond"), "ci_cond": cb.get("ci_cond"),
                        "d_cond_reweighted": cb.get("d_cond_reweighted"), "ci_rw": cb.get("ci_rw"),
                        "verdict": inter_verdict((cb.get("ci_cond") or [None, None])[0],
                                                 d_rw=cb.get("d_cond_reweighted"),
                                                 ci_rw=cb.get("ci_rw"))})
    return out


def inter_verdict(ci_lo, d_rw=None, ci_rw=None, d_policy=None) -> str:
    """Family 5 is CONTEXT, never a selection (DEVIATION #8b). `select_survivor`
    never reads an interaction cell, and a cell carries no policy column, so a
    positive CI clears condition (a) of `convention_conditions` and nothing else.
    It therefore reads `cushion` — or `not selected` the moment any guard the
    conventions apply is available and fails — and never `separates`."""
    if ci_lo is None or ci_lo != ci_lo or not ci_lo > 0:            # (a) fails
        return INTER_NOT_SELECTED
    if d_rw is not None or ci_rw is not None:                      # (c) when the cell has it
        rw_lo = (ci_rw or [None, None])[0]
        if not (d_rw is not None and d_rw == d_rw and d_rw > 0
                and rw_lo is not None and rw_lo == rw_lo and rw_lo > 0):
            return INTER_NOT_SELECTED
    if d_policy is not None and d_policy == d_policy and d_policy < 0:   # (d)
        return INTER_NOT_SELECTED
    return INTER_CUSHION


def _inter_cell(D, name, cell, hit, hold, a) -> dict:
    n = int(cell.sum())
    if n < MIN_CELL_N:
        return {"name": name, "n": n, "verdict": "n<%d — not shown" % MIN_CELL_N}
    b = ES.boot_delta_col(D, D[cell], hit, a.boot_draws)
    return {"name": name, "cell": "yes", "n": n, "hit5_20": 100.0 * _nanmean(D.loc[cell, hit]),
            "stop_20": 100.0 * _nanmean(D.loc[cell, "stop_%d_N" % hold]),
            "d_cond": 100.0 * (_nanmean(D.loc[cell, hit]) - _nanmean(D[hit])),
            "ci_cond": [100.0 * b["lo"], 100.0 * b["hi"]],
            "verdict": inter_verdict(100.0 * b["lo"])}


def c1_window_sweep(D: pd.DataFrame, hold: int, primary: str, a) -> dict:
    """The C1 window printed at 1/2/3/5 bars — never scored. The outcome of a C1
    that fires at k IS the delay-k outcome (the identity), so the sweep reads the
    D_k columns and needs no second replay.

    The sweep column is written for every row a C1 pattern appears on, INCLUDING
    the rows `close_entry_cols` skips for `no_bars` (not enough forward bars for
    the entry + the longest clock). `conventions.C1` drops those, so the sweep has
    to drop exactly the same rows or the two n_fired disagree at the confirmation
    window: `fired_D<k>` carries that identical guard, so it IS the filter — never
    a second no_bars rule (DEVIATION #3)."""
    out = {}
    if "entry_bar_c1_sweep" not in D:
        return out
    k = pd.to_numeric(D["entry_bar_c1_sweep"], errors="coerce") - pd.to_numeric(D["bar_idx"], errors="coerce")
    for w in C1_SWEEP_WINDOWS:
        m = k.notna() & (k <= w)
        n, hits = 0, []
        for kk in range(1, w + 1):
            col = "%s_%d_D%d" % (primary, hold, kk)
            fcol = "fired_D%d" % kk
            if col not in D or fcol not in D:
                continue
            sel = m & (k == kk) & D[fcol].fillna(False).astype(bool)
            n += int(sel.sum())
            if sel.any():
                hits.append((int(sel.sum()), _nanmean(D.loc[sel, col])))
        tot = sum(c_ for c_, _ in hits)
        hit = sum(c_ * v for c_, v in hits) / tot if tot else float("nan")
        out[str(w)] = {"n_fired": n, "n_no_bars": int(m.sum()) - n,
                       "hit5_20": 100.0 * hit if hit == hit else None,
                       "note": "printed, never scored; no_bars rows excluded as conventions.C1 does"}
    return out


def survivorship_path(a) -> Optional[str]:
    """Where a previous run's survivorship block would be: the explicit
    `--survivorship <json>`, else the sidecar beside the events cache."""
    if getattr(a, "survivorship", None):
        return a.survivorship
    if getattr(a, "cache_csv", None):
        return a.cache_csv + SURVIVORSHIP_SUFFIX
    return None


def survivorship_present(surv) -> bool:
    """A block counts as IN HAND only when it carries the cache-universe hit rate."""
    return bool(isinstance(surv, dict) and surv.get("cache_hit5_20") is not None)


def survivorship_read(a, convP: dict, broad_hit5) -> dict:
    """The cache-universe (survivorship) replay, which is a SEPARATE `--stage replay`
    run. Either COMPUTE it from `--cache-csv` — and park it beside that CSV so a later
    stats run can MERGE it without re-reading a multi-GB events file — or MERGE the
    block a previous run wrote. `d_hit5_vs_broad` is ALWAYS recomputed against the
    broad base of the run doing the merge; nothing about the broad cohort is carried
    over from the file."""
    blank = {"cache_n_names": None, "cache_hit5_20": None, "d_hit5_vs_broad": None,
             "source": None}
    if getattr(a, "cache_csv", None) and os.path.exists(a.cache_csv):
        C = ES.load_events(a.cache_csv, columns=["symbol", "date", "dir", "episode_dir",
                                                 convP["hit5"], convP["stop"], convP["R"]])
        CB = C[(C["dir"] == DIRECTION_BASE) & (C["episode_dir"] == True)]    # noqa: E712
        surv = {"cache_n_names": int(CB["symbol"].nunique()), "cache_n_episodes": int(len(CB)),
                "cache_hit5_20": 100.0 * _nanmean(CB[convP["hit5"]]),
                "cache_stop_20": 100.0 * _nanmean(CB[convP["stop"]]),
                "d_hit5_vs_broad": 100.0 * _nanmean(CB[convP["hit5"]]) - (broad_hit5 or 0.0),
                "source": "cache-csv:%s" % a.cache_csv, "run_date": _today_et()}
        park = a.cache_csv + SURVIVORSHIP_SUFFIX
        try:
            with open(park, "w") as fh:
                json.dump(surv, fh, indent=1)
            surv["written_to"] = park
        except OSError as exc:                      # read-only /tmp is not a study failure
            P("    SURVIVORSHIP: could not park %s (%s)" % (park, exc))
        return surv
    path = survivorship_path(a)
    if path and os.path.exists(path):
        try:
            with open(path) as fh:
                got = json.load(fh)
        except (OSError, ValueError) as exc:
            P("    SURVIVORSHIP: %s is unreadable (%s)" % (path, exc))
            return blank
        if not survivorship_present(got):
            P("    SURVIVORSHIP: %s carries no cache_hit5_20 — not merged" % path)
            return blank
        surv = {k: got.get(k) for k in ("cache_n_names", "cache_n_episodes",
                                        "cache_hit5_20", "cache_stop_20")}
        surv["d_hit5_vs_broad"] = float(surv["cache_hit5_20"]) - (broad_hit5 or 0.0)
        surv["source"] = "merged:%s" % path
        surv["merged_from"] = got.get("source")
        surv["merged_run_date"] = got.get("run_date")
        return surv
    return blank


def stats(a) -> dict:
    t0 = time.time()
    clocks = tuple(int(x) for x in str(a.clocks).split(","))
    hold = int(a.hold)
    primary = a.primary
    X = load_events(a.from_csv, clocks, hold, primary)
    meta = {}
    if os.path.exists(a.from_csv + ".meta.json"):
        with open(a.from_csv + ".meta.json") as fh:
            meta = json.load(fh)
    # the SAMPLE half of quotable — the survivorship half is only known after the
    # cache line below, so the flag itself is not decided until then (m1 2026-09-15:
    # a `quotable: True` beside an all-None survivorship block contradicted the banner)
    sample_ok = not (a.names or meta.get("names") or a.stride > 1 or (meta.get("stride") or 1) > 1)
    banner = "" if sample_ok else "NOT QUOTABLE — smoke (%s)" % SUBSAMPLE_NOT_QUOTABLE
    if banner:
        P("=" * 118 + "\n" + banner + "\n" + "=" * 118)
    if a.min_dvol and "dvol50_pre" in X:
        d = pd.to_numeric(X["dvol50_pre"], errors="coerce")
        X = X[d >= float(a.min_dvol)].reset_index(drop=True)
        P("LIQUIDITY CONTROL RUN — cohort restricted to dvol50_pre >= %g" % a.min_dvol)
    E_all = X
    B_all = X[X["dir"] == DIRECTION_BASE].reset_index(drop=True)
    B = B_all[B_all["episode_dir"] == True].reset_index(drop=True)          # noqa: E712
    BN = B[B["gap_N"] == False].reset_index(drop=True)                      # noqa: E712
    dates = sorted(X["date"].unique())
    window = "%s -> %s" % (dates[0], dates[-1]) if dates else "n/a"
    convs = conventions(primary, hold)
    convP, convN, convPC = convs["P"], convs["N"], convs["PC"]

    P("=" * 118)
    P("🎯 ENTRY-TRIGGER STUDY  (%s)   script %s" % (_today_et(), SCRIPT))
    P("COHORT  the engine's own demand-band events (room >= %g%% to the first proven lid, print <= %g%% "
      "above the band top); floor=%s bars, clocks=%s, hold=%d; stop = band floor -%g%%; universe=%s"
      % (FIVE_PCT, AG.ALERT_MAX_ABOVE_DEMAND_PCT, meta.get("floor", a.floor), clocks, hold,
         STOP_BUFFER_PCT, meta.get("universe_mode", "?")))
    P("        all events n=%d   bouncing n=%d   bouncing EPISODES n=%d   names=%d   dates=%d   window %s"
      % (len(E_all), len(B_all), len(B), B["symbol"].nunique() if len(B) else 0, len(dates), window))
    P("        windows: confirmation %d bars, higher-low %d bars, delays %s, cell floor %d — %s"
      % (C_WINDOW_BARS, HL_WINDOW_BARS, list(DELAYS_REPORTED), MIN_CELL_N, WINDOW_SOURCE))
    P("        primary outcome = %s from the ENTRY price | PC is PRINT-ONLY (never ship-eligible)" % primary)
    P("=" * 118)
    P(ES.RULE_TEXT)
    P("THE IDENTITY: a trigger that fires at k IS the delay-k entry on that row, so the deciding lift is the "
      "CONDITIONAL contrast d_cond (fired vs the OTHER rows that survived to k unstopped), NOT a self-paired delay.")

    base_json = {}
    P()
    P("BASE RATES — bouncing EPISODES, three entry conventions:")
    for tag, D_, conv in (("P", B, convP), ("N", BN, convN), ("PC", B, convPC)):
        if len(D_) < MIN_CELL_N:
            P("  %s: n<%d — not shown" % (tag, MIN_CELL_N))
            continue
        s = ES.bucket_stats(D_, D_, conv, clocks, hold, E_ev=B_all)
        P(ES.fmt_row(tag, s))
        base_json[tag] = s
    P("    (DEVIATION #1: ES.bucket_stats reads room_pct = the P-entry room; the convention table below "
      "uses each convention's OWN room_pct_X / risk_pct_X.)")

    # ── the delays: what WAITING alone gives ──
    P()
    P("DELAYS (unconditional wait of k bars; the placebo base for every trigger):")
    delays = {}
    Bp = add_policy(B, ["D%d" % k for k in DELAYS_PLACEBO], hold)
    for k in DELAYS_PLACEBO:
        col = "%s_%d_D%d" % (primary, hold, k)
        fcol = "fired_D%d" % k
        if col not in B or fcol not in B:
            continue
        m = B[fcol].fillna(False).astype(bool)
        n = int(m.sum())
        row = {"n_fired": n}
        if n >= MIN_CELL_N:
            b = ES.cluster_boot(_ydf(B, pd.to_numeric(B["%s_%d" % (primary, hold)], errors="coerce")),
                                _ydf(B[["date"]][m], pd.to_numeric(B.loc[m, col], errors="coerce")),
                                "y", "date", a.boot_draws)
            row.update({"hit5_20": 100.0 * _nanmean(B.loc[m, col]),
                        "stop_20": 100.0 * _nanmean(B.loc[m, "stop_%d_D%d" % (hold, k)]),
                        "R20": _nanmean(B.loc[m, "R%d_D%d" % (hold, k)]),
                        "policy_R20": float(Bp["R%d_policy_D%d" % (hold, k)].mean()),
                        "d_delay_only": 100.0 * (_nanmean(B.loc[m, col])
                                                 - _nanmean(B["%s_%d" % (primary, hold)])),
                        "ci": ([100.0 * float(np.percentile(b, 2.5)), 100.0 * float(np.percentile(b, 97.5))]
                               if b.size >= 100 else [None, None])})
            P("    D%-2d n=%-6d hit5@20 %5.1f%%  stop %5.1f%%  R20 %+.3f  policy R20 %+.3f  Δdelay-only %+.2fpp"
              % (k, n, row["hit5_20"], row["stop_20"], row["R20"], row["policy_R20"], row["d_delay_only"]))
        else:
            row["verdict"] = "n<%d — not shown" % MIN_CELL_N
            P("    D%-2d n=%-6d  n<%d — not shown" % (k, n, MIN_CELL_N))
        delays[str(k)] = row

    # ── the conventions ──
    P()
    P("=" * 118)
    P("CONVENTIONS — each has its OWN entry, room and risk. d_cond = fired vs unfired survivors at the same bar.")
    P("=" * 118)
    conv_json = {}
    gapless = B["gap_N"] == False if "gap_N" in B else None                 # noqa: E712
    for key in REPORT_KEYS:
        D_ = BN if key == "N" else B
        if ("fired_" + key) not in D_:
            continue
        # DEVIATION #3: N is SCORED on the gapless rows, but it is REPORTED over the
        # whole episode cohort — the gap_N episodes are skips, not a smaller universe.
        base_n = len(B) if (key == "N" and gapless is not None) else None
        excl = (excluded_skips(B, gapless, "skip_reason_N", "gap_N")
                if (key == "N" and gapless is not None) else None)
        r = convention_block(D_, key, hold, clocks, a, primary, base_n=base_n, excluded=excl)
        conv_json[key] = r
        if r.get("verdict", "").startswith("n<"):
            P("  %-3s n_fired=%-6d  %s" % (key, r["n_fired"], r["verdict"]))
            continue
        P("  %-3s n_fired=%-6d fire_rate %5.1f%%  hit5@20 %5.1f%%  stop %5.1f%%  R20 %+.3f  room %5.2f  risk %4.2f"
          % (key, r["n_fired"], 100.0 * (r["fire_rate"] or 0), r["hit5_20"], r["stop_20"], r["R20"],
             r["room_pct"], r["risk_pct"]))
        P("      d_cond %s  CI %s  MDL %s | d_paired %+.2fpp CI %s | d_raw %+.2fpp (%s) | decomp gap %s"
          % (_pp(r.get("d_cond")), _ci(r.get("ci_cond")), _pp(r.get("mdl_cond")), r["d_paired"],
             _ci(r.get("ci_paired")), r["d_raw"], r["raw_note"], _pp(r.get("decomp_gap"))))
        P("      Δstop_cond %s CI %s | reweighted %s CI %s | 1/date %s 1/sym %s | policy R %+.3f vs P (CI %s) "
          "vs waiting %s | fire bars %s | skipped %s"
          % (_pp(r.get("d_stop_cond")), _ci(r.get("ci_stop_cond")), _pp(r.get("d_cond_reweighted")),
             _ci(r.get("ci_rw")), _pp(r.get("one_per_date")), _pp(r.get("one_per_symbol")),
             r["d_policy_R"], _ci(r.get("ci_policy_R"), 3), _pp(r.get("d_policy_R_vs_delay"), 3),
             r.get("fire_bar_dist"), r.get("n_skipped")))
        P("      splits %s  -> %s  conditions %s"
          % ({k: v.get("verdict") for k, v in (r.get("splits") or {}).items()}, r["verdict"],
             r.get("conditions")))

    sweep = c1_window_sweep(B, hold, primary, a)
    P("  C1 window sweep (printed, never scored): %s" % sweep)

    # ── per-feature tables + the OOS splits on the combined score ──
    per_feature, strat_json, splits_features = [], [], {}
    prev_floor = ES.MIN_BUCKET_N
    ES.MIN_BUCKET_N = MIN_CELL_N                 # DEVIATION #8 (restored below)
    try:
        for conv, D_ in ((convP, B), (convN, BN), (convPC, B)):
            P()
            P("=" * 118)
            P("PER-FEATURE BUCKETS — %s — n=%d%s"
              % (conv["label"], len(D_), "" if ship_eligible(conv["tag"]) else "   [PRINT-ONLY]"))
            P("=" * 118)
            feature_table(D_, conv, a, clocks, hold, conv["feats"], per_feature, conv["tag"])
            P("  STRATIFIERS (%s):" % conv["tag"])
            feature_table(D_, conv, a, clocks, hold,
                          [f for f in STRATIFIERS if f not in conv["feats"]], strat_json, conv["tag"])
            if len(D_) >= 200:
                ds = sorted(D_["date"].unique())
                in_h1 = D_["date"].isin(set(ds[:len(ds) // 2]))
                parity = D_["symbol"].map(lambda s: zlib.crc32(str(s).encode()) % 2)
                res = {"s1": ES.run_split(D_, in_h1, ~in_h1, conv, a, "S1 date halves", clocks, hold),
                       "s2": ES.run_split(D_, ~in_h1, in_h1, conv, a, "S2 reverse", clocks, hold),
                       "s3": ES.run_split(D_, parity == 0, parity == 1, conv, a,
                                          "S3 symbol-disjoint", clocks, hold)}
                splits_features[conv["tag"]] = {k: {kk: v.get(kk) for kk in (
                    "name", "n_fit", "n_scored", "d_hit5", "ci", "mdl", "verdict", "selected")}
                    for k, v in res.items()}
    finally:
        ES.MIN_BUCKET_N = prev_floor

    inter = interactions(BN, a, hold, primary, per_feature)
    P()
    P("INTERACTIONS: %s" % inter)

    # ── EXPLORATORY (printed, never scored) ──
    P()
    P("EXPLORATORY (printed, never scored; typed by proxy or uncited): %s" % list(EXPLORATORY))
    for feat in EXPLORATORY:
        if feat not in B:
            continue
        kind = ES.feat_kind(feat)
        lab, order, _ = ES.assign_buckets(B[feat], kind)
        cells = ["%s %.1f(%d)" % (b_lab, 100.0 * _nanmean(B.loc[lab == b_lab, convP["hit"]]),
                                  int((lab == b_lab).sum()))
                 for b_lab in order if (lab == b_lab).any()]
        P("  %-20s %s" % (feat, "  ".join(cells)))

    # ── reconciliation, survivorship, liquidity ──
    rec = {}
    if "intact_at" in B:
        m = B["intact_at"] == True                                          # noqa: E712
        if m.sum() >= MIN_CELL_N:
            rec = {"d_hit5_P": 100.0 * (_nanmean(B.loc[m, convP["hit"]]) - _nanmean(B[convP["hit"]])),
                   "n_intact": int(m.sum()), "expected_2026_09_15": 8.30}
            P("    INTACT reconciliation (P): ΔHIT5 %+.2fpp on n=%d (2026-09-15: +8.30pp)"
              % (rec["d_hit5_P"], rec["n_intact"]))
    liq = {"min_dvol": ES.MIN_DVOL_CONTROL, "n": 0, "hit5_20": None, "stop_20": None, "R20": None}
    if "dvol50_pre" in B:
        dv = pd.to_numeric(B["dvol50_pre"], errors="coerce")
        L = B[dv >= ES.MIN_DVOL_CONTROL]
        if len(L):
            liq.update({"n": int(len(L)), "hit5_20": 100.0 * _nanmean(L[convP["hit"]]),
                        "stop_20": 100.0 * _nanmean(L[convP["stop"]]), "R20": _nanmean(L[convP["R"]])})
        P("    liquidity control (dvol50_pre >= %g): n=%d hit5@20 %s"
          % (ES.MIN_DVOL_CONTROL, liq["n"], liq["hit5_20"]))
    surv = survivorship_read(a, convP, base_json.get("P", {}).get("hit5_20"))
    if survivorship_present(surv):
        P("    SURVIVORSHIP cache names=%s hit5@20 %.1f%% Δ vs broad %+.2fpp   [%s]"
          % (surv.get("cache_n_names"), surv["cache_hit5_20"], surv["d_hit5_vs_broad"],
             surv.get("source")))
    else:
        P("    SURVIVORSHIP: no cache replay (%s) — NO NUMBER ABOVE IS QUOTABLE WITHOUT THE CACHE LINE"
          % (survivorship_path(a) or "no --cache-csv / --survivorship given"))

    quotable_reasons = ([] if sample_ok else [SUBSAMPLE_NOT_QUOTABLE]) + \
                       ([] if survivorship_present(surv) else [SURVIVORSHIP_MISSING])
    quotable = not quotable_reasons
    if quotable_reasons:
        banner = "NOT QUOTABLE — " + " · ".join(quotable_reasons)

    selected, survivor = select_survivor(conv_json, per_feature, splits_features)
    status = "separates" if survivor else "no_signal"
    n_nan = {c: int(X[c].isna().sum()) for c in dict.fromkeys(PREREG_N_TRIG + STRATIFIERS) if c in X}
    notes = {}
    if "rs20_pre" in X and int(X["rs20_pre"].notna().sum()) == 0:
        notes["rs20_pre"] = "RSP not cached — not measured"
        P("    rs20_pre: RSP not cached — not measured")
    measured = {
        "run_date": _today_et(), "universe_mode": meta.get("universe_mode"),
        "n_names": int(B["symbol"].nunique()) if len(B) else 0,
        "n_names_universe": meta.get("n_universe"),
        "n_events_all": int(len(E_all)), "n_events_bouncing": int(len(B_all)),
        "n_episodes": int(len(B)), "n_episodes_N": int(len(BN)), "n_dates": int(len(dates)),
        "window": window, "floor": meta.get("floor", a.floor), "clocks": list(clocks),
        "hold": hold, "primary_outcome": primary, "min_cell_n": MIN_CELL_N,
        "windows": {"c": C_WINDOW_BARS, "hl": HL_WINDOW_BARS, "delays": list(DELAYS_REPORTED),
                    "source": WINDOW_SOURCE},
        "base": base_json, "delays": delays, "conventions": conv_json,
        "c1_window_sweep": sweep, "per_feature": per_feature, "stratifiers": strat_json,
        "interactions": inter, "splits_features": splits_features,
        "selected": selected, "survivor": survivor, "status": status,
        "fallback": "P — enter at the print; the READY read is unchanged",
        "survivorship": surv, "liquidity_control": liq, "script": SCRIPT,
        "cohort_note": ("bouncing EPISODES at board demand bands; every convention keeps the event's own "
                        "band, stop and target and moves only the ENTRY; outcomes walk from the ENTRY bar; "
                        "no costs; PC is print-only"),
        "intact_reconcile": rec, "quotable": quotable,
        "quotable_reasons": quotable_reasons, "min_dvol_filter": a.min_dvol,
        "tail": meta.get("tail"), "counters": meta.get("counters"), "n_feature_nan": n_nan,
        "feature_notes": notes, "walltime_stats_s": round(time.time() - t0, 1),
    }
    measured = ES._clean(measured)
    P()
    P("=" * 118)
    P("VERDICT: status=%s  selected=%s  survivor=%s  fallback=%s%s"
      % (status, selected, (survivor or {}).get("key"), measured["fallback"],
         "   " + banner if banner else ""))
    P("=" * 118)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(measured, fh, indent=1)
        P("wrote %s" % a.json)
    if a.emit_measured:
        P()
        P("# ---- MEASURED literal (paste verbatim into supply_demand/enterable.py) ----")
        P("MEASURED = " + pprint.pformat(measured, width=100, sort_dicts=False))
    P("stats done %.0fs" % (time.time() - t0))
    return measured


def _pp(v, nd: int = 2) -> str:
    return "n/a" if v is None or v != v else ("%+.*f" % (nd, v))


def _ci(v, nd: int = 2) -> str:
    if not v or v[0] is None or v[0] != v[0]:
        return "[n/a]"
    return "[%+.*f,%+.*f]" % (nd, v[0], nd, v[1])


# ═════════════════════════════════════════════════════════════════════════════
def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stage", default="both", choices=("replay", "stats", "both"))
    ap.add_argument("--universe", default="broad", choices=ES.UNIVERSE_MODES)
    ap.add_argument("--floor", type=int, default=FLOOR_DEFAULT)
    ap.add_argument("--hold", type=int, default=HOLD_DEFAULT)
    ap.add_argument("--clocks", default=",".join(str(c) for c in CLOCKS_DEFAULT))
    ap.add_argument("--stride", type=int, default=1, help="every Nth of the sorted symbol list")
    ap.add_argument("--names", type=int, default=0, help="smoke only (NOT QUOTABLE)")
    ap.add_argument("--min-dvol", type=float, default=0.0)
    ap.add_argument("--chunk", type=int, default=300, help="symbols per events() call (memory)")
    ap.add_argument("--perm-draws", type=int, default=BQ.PERM_DRAWS)
    ap.add_argument("--boot-draws", type=int, default=BQ.BOOT_DRAWS)
    ap.add_argument("--placebo-draws", type=int, default=BQ.PLACEBO_DRAWS)
    ap.add_argument("--seed", type=int, default=SEED_BOOT)
    ap.add_argument("--primary", default="hit5", choices=OUTCOMES)
    ap.add_argument("--out", default="/tmp/entry_events.csv")
    ap.add_argument("--from-csv", default=None)
    ap.add_argument("--cache-csv", default=None,
                    help="the cache-universe events CSV (survivorship); its block is parked "
                         "at <path>" + SURVIVORSHIP_SUFFIX + " for a later --stage stats to merge")
    ap.add_argument("--survivorship", default=None,
                    help="merge a survivorship block a previous --cache-csv run wrote; with "
                         "neither flag's file present the run is NOT quotable")
    ap.add_argument("--json", default=None)
    ap.add_argument("--emit-measured", action="store_true")
    a = ap.parse_args(argv)
    if a.stage in ("replay", "both"):
        replay(a)
        a.from_csv = a.out
    if a.stage in ("stats", "both"):
        if not a.from_csv:
            ap.error("--from-csv is required for --stage stats")
        stats(a)


if __name__ == "__main__":
    main()
