# 🌀 Raid-low entry — pre-registered study (2026-09-24)

**Status: PRE-REGISTERED (Amendment 1, 2026-09-25, before any outcome), NOT RUN.** A Rule #10 research step. Nothing in the app changes because of this file or its script: no surface, lane, gate, alert, sort, rule line or ✨ entry.

## 1. The ask, verbatim

- Ajay 2026-09-17: *"I am rely on manipulation.. I wanna use that as an entry the bottom of manipulation"*
- Ajay 2026-09-24, asked whether to measure it: *"yes please build raid low"*

The level is the **raid low**: `raid_price` from `supply_demand/amd.py::find_raids`, the low that printed on the raid bar. It is NOT `raid_level` (the swept base edge). This measures HIS rule on the ONE raid engine (the detector is untouched).

His rule has never been measured. The 2026-09-14 result (`rotation/hottest_amd.py::AMD_MEASURED`, −4.2pp, INVERTED) answered a different bet — a close above the base top within 21 sessions — and is not an answer to this one.

## 2. Files

- Script: `backend/scripts/amd_raid_low_study.py` (stages `walk`, `sanity`, `match`, `stats`; `--explain SYM DATE`).
- Tests: `backend/tests/test_amd_raid_low_study_2026_09_24.py` (order mechanics, point-in-time walk, placebo draw, statistics, verdict; negatives marked (N)).
- Result (after the run): `backend/scripts/amd_raid_low_measured.json`.

## 3. PRE-REGISTRATION — frozen before the full run; committed at <sha>

Copied from the design spec, sections 3.1–3.8. After the first `stats` print nothing below changes; the only changes allowed before the full run are Ajay's overrides of the HIS CALL items (section 7).

### 3.1 Data, universe, snapshot
- Walk the **cache universe**: `ES.symbols_for("cache", need_bars=NEED_BARS)`, `NEED_BARS = WARMUP_PIT + 2` (a dead name with 122+ bars still contributes). Tag `in_study = sym in AS.study_universe()`; write the list to `OUT/in_study.txt` and its sha256 into the JSON.
- PRIMARY = `in_study` rows. Everything else is the survivorship check.
- **Snapshot (run start, written once to `OUT/snapshot_t0.json`, reused on resume):**
  - `AS_OF` = the last date (`YYYY-MM-DD`) of `split_today_partial(bulk_cached_frames([BENCH])[BENCH])[0]`;
  - `stamps_t0 = {symbol: cached_at}` for every walked name (projection-only `find`);
  - `t0_max_cached_at`.
- Frame per name: `bulk_cached_frames([sym]).get(sym)` → `split_today_partial(df)[0]` → `cap_as_of(df, AS_OF)` (keep rows whose `YYYY-MM-DD` ≤ AS_OF). Store `bars_digest` = sha1 of the capped O/H/L/C/V float64 bytes.
- Skip the name, counted by reason, when None / `len < NEED_BARS` / any O/H/L/C non-finite or ≤ 0 (`bad_ohlc`). Rows are never dropped.
- `ended = last_date < AS_OF − ENDED_GRACE_DAYS (7 calendar days)`. A name one refresh behind is not `ended`.
- **Snapshot verify (end of `walk`):** re-read stamps; for every walked name whose `cached_at` moved, re-load, re-cap at AS_OF, and compare `bars_digest`. Any difference → write `OUT/snapshot_fail.json` (names + chunk ids), exit code 4, and `stats` refuses to print a status (`invalid_snapshot`). Appended bars after AS_OF never trip it.
- Never `load_prices`, never `_fetch`, never a write of any kind.

### 3.2 Events — point-in-time by construction
```
WARMUP_PIT = A.MAX_BASE_BARS + A.MAX_RAID_AGE      # 120
for t in range(WARMUP_PIT, n):
    R = A.find_raids(df.iloc[:t + 1], direction="bullish")
    rows = R["raids"]
    if rows and rows[-1]["idx"] == t: -> EVENT at t (fields from rows[-1])
    elif pool rule (3.5) holds on R: -> POOL row at t
```
- Lookahead: the frame ENDS at bar t. Only fields from bars ≤ t are read: `raid_price L`, `raid_level E`, `raid_close C`, `base_lo`, `base_hi T`, `base_bars`, `depth_pct`, `vol_ratio`, `sweep_seq`. Never `outcome*` / `markup_bars_left`.
- `RAID_FIELDS = ("date","raid_level","raid_price","raid_close","depth_pct","vol_ratio","base_lo","base_hi","base_bars","base_date","base_end_date")`. Why `WARMUP_PIT = 120`: a raid at t belongs to a base ending ≥ t−30 (:232) that starts ≥ end−89, so with t ≥ 119 the base is never clipped and the `LOOKBACK` floor never binds. **The RAID_FIELDS and `open_base` of the event at t equal those of any longer frame.** The chain fields (`sweep_seq`, `resweep_of`, `chain_root`) do NOT have this property (1.1); they are read from the prefix frame (the cache's full history to t, which is what the app's frame showed) and used only for a secondary cut.
- Integrity: `L < E <= C` or the row is `bad_event` (expect 0).
- Derived: `atr = ES.atr14_series(h,l,c)[t]`, `delta = (C−L)/C`, `rho = (T−L)/L`, `nu = atr/C`.
- Row flags (one rule for every arm, whatever the fill):
  - `complete = t + W + HOLD <= n−1`;
  - `terminal = not complete and ended` (the frame stopped early: the trade ends with the data);
  - `evaluable = complete or terminal`; `open` = neither (excluded from every outcome statistic, counted).

### 3.3 PRIMARY rule E1 (his) — frozen
- Order: a buy limit at `L`, resting on bars `t+1 .. min(t+W, n−1)`, `W = ORDER_WINDOW = TB.MAX_RAID_BARS_AGO` (3). **No cancel.**
- Fill (STRICT): the first bar `j` in the window with `low_j < L`. Fill price `P = min(open_j, L)`. An exact touch (`low_j == L`) is NOT a fill.
- Stop `S0 = L × (1 − STOP_BUFFER_PCT/100)`. Target `T = base_hi`.
- Fill bar (conservative, fixed): `open_j <= S0` → `gap_stop`, `ret = 0.0`, counted as a stop-out; else `low_j <= S0` → `stop` at `S0`; the target is NEVER credited on the fill bar.
- After the fill, bars `j+1 .. min(j+HOLD, n−1)`, `HOLD = AS.REACH_H` (21): stop first (`low_k <= S0` → exit `min(open_k, S0)`), then target (`high_k >= T` → exit `max(open_k, T)`), same-bar tie → STOP; otherwise exit at `close[j+HOLD]` (`clock`), or at `close[n−1]` when the frame ends first on an `ended` name (`terminal`).
- `ret = exit/P − 1`. Why-codes: `unfilled, gap_stop, stop, target, clock, terminal` (+ `cancelled` in CX, `gap_skip` in E0N).
- **PRIMARY OUTCOME: mean `ret` of filled E1 trades.** Two populations, both fixed:
  - **Δ uses MATCHED events only**: E1 arm = filled trades of evaluable in_study events that got ≥1 P1 draw; P1 arm = filled trades of those draws.
  - **The headline E1 mean and the absolute leg (b) use ALL filled evaluable in_study events** (matched or not).
- Reported beside it: fill rate, stop-out rate (stop + gap_stop), target, clock, terminal rates, win rate (`ret > 0`), median, `ES.trimmed_mean`, per-event expectancy (unfilled = 0), mean fill delay, and the RSP excess (3.7).

### 3.4 References (SECONDARY, labelled; same S0/T/HOLD unless stated)
- **E0** — buy at the raid close `C` on bar t; walk `t+1 .. t+HOLD`.
- **E0N** — buy at `open[t+1]`; `gap_skip` when `open[t+1] <= S0` (`explosive_study.py:526`).
- **E2** — a strict limit at `E` (the swept edge), same window, no cancel, stop still `S0`.
- Paired per-event differences (unfilled = 0): E1−E0, E1−E2.
- **Selection diagnostic:** E0's return on events where E1 FILLED vs did NOT fill.
- **HINDSIGHT (NOT TRADABLE, never scored or quoted):** entry at `L` on bar t.

### 3.5 Placebo (the null for "the raid low")
- Pool row at t when ALL hold: not a PIT raid bar; `R["last_break_base"] is None`; `ob = R["open_base"]` exists with `ob.hi > ob.lo`; `ob.lo <= close_t <= ob.hi`; `pos = (low_t − ob.lo)/(ob.hi − ob.lo) <= PLACEBO_LOWER_FRACTION (1/3)`.
- Placebo order: IDENTICAL mechanics to the E1 primary — strict fill at `L' = low_t`, no cancel, `S0' = L' × (1 − STOP_BUFFER_PCT/100)`, `T' = ob.hi`, same W, HOLD, fill-bar, terminal and exit rules. `delta', rho', nu'` defined the same way.
- **Cells (45):** edges computed on evaluable in_study EVENTS only, before any outcome exists: terciles of `delta`, **quintiles of `rho`**, terciles of `nu`. `cell = 15·b3(delta) + 3·b5(rho) + b3(nu)`. Pool rows outside the event ranges fall into the open-ended edge bins. **→ Amendment 1: record only (balance_v1).**
- **P1 (PRIMARY placebo) — cross-name, same date, same cell:** for each evaluable in_study event draw `K_PLACEBO = 5` evaluable in_study pool rows with the same `date`, same `cell`, `sym != event sym`; without replacement when ≥ K candidates, with replacement when 1..K−1; 0 → widen to `|date_pos diff| <= DATE_WIDEN (2)` (`widened`); still 0 → `unmatched` (out of Δ, counted, reported). Deterministic: `np.random.default_rng(SEED)`, events in `eid` order. **→ Superseded by Amendment 1, A1.1.**
- **P1s (SECONDARY, same symbol):** same cell, same symbol, `|t' − t| > W + HOLD`, any date, K=5, same replacement rule. **→ Amendment 1: same NN matcher, same symbol (A1.1).**
- **Balance gate (pre-outcome, computed in `match`):** `SMD(x) = (mean_ev − mean_draw) / sqrt((var_ev + var_draw)/2)` (ddof=1), events = matched evaluable in_study events (once each), draws = all their P1 draws. `balanced = |SMD(delta)| < BALANCE_SMD_MAX (0.1) and |SMD(rho)| < BALANCE_SMD_MAX`. SMD of `nu`, `depth`, `pos` printed. The same SMDs on the FILLED subsets are printed in `stats` for information only. **→ Superseded by Amendment 1, A1.2 (rho, delta AND nu gated).**

### 3.6 Secondary grid (ONE axis varied from the primary; labelled SECONDARY; no verdict)
| Key | Change | Placebo arm |
|---|---|---|
| S1 | stop `L − max(STOP_BUFFER_ATR·atr, L·MIN_STOP_BUFFER_PCT/100)` | P_S1 |
| S2 | stop `L − 1.0·atr` (the brief's "1 ATR"; a study convention) | P_S2 |
| X1 | target = `E` (swept-edge reclaim) | none |
| X2 | no target (stop + clock) | P_X2 |
| X3 | no stop, no target: `close[j+HOLD]/P − 1` | P_X3 |
| W10 | window `AS.BARS_AGO_MAX` | P_W10 |
| W25 | window `A.MAX_MARKUP_BARS` | P_W25 |
| FT | touch fill `low_j <= L` | P_FT (`low <= L'`) |
| CX | cancels: a close `> T` or `< E` (evaluated at the close after the intrabar fill check, effective next bar, only while unfilled) | none — the placebo's floor cancel can never fire before its own fill; reported as E1_CX mean + paired E1_CX − E1 |

Cuts on the primary: `L >= SF.MIN_SHARE_PRICE`; first sweep (`sweep_seq == 1`) vs re-sweep (> 1, prefix-frame chains). Each secondary row prints the E1 mean with CI, the placebo mean, Δ with CI.

### 3.7 Statistics
- Rows: one array holds events and draws; a draw carries its EVENT's cluster labels (the matched set is the unit).
- `AS.boot_diff(vals, mask_a, mask_b, groups, B=BOOT_B (2000), seed=7)` twice: groups = event symbol; groups = event date block (`dpos // HOLD`, `dpos` = position among the unique in_study event dates). **CI = `AS.widest`** of the two. A per-date CI is printed for context only.
- **Absolute leg (b) — excess over RSP:** `rsp_ret = BENCH.close[exit_date] / BENCH.open[fill_date] − 1` (BENCH frame from the same snapshot, capped at AS_OF, dates keyed `YYYY-MM-DD`); `xs = ret − rsp_ret`; NaN when either date is missing (`no_bench`, counted). `boot_mean(xs, mask, groups, B, seed)`, widest of symbol and date-block. The raw E1 mean and its CI are printed beside it.
- Fill-rate difference E1 vs P1: `boot_diff` on the 0/1 fill indicator.
- MDL = 2.8 × SD of the wider Δ bootstrap distribution.
- **Stability (point Δ; CI where stated):**
  - date halves (the matched events' unique dates sorted: H1 = the first ⌊D/2⌋ unique dates, H2 = the rest — the explosive_study unique-date split; Amendment 1, A1.5), symbol halves (`zlib.crc32(sym) % 2`);
  - one-per-date, one-per-symbol (seeded, with their draws);
  - P1s;
  - **drop-one-date-block:** Δ with each date block removed in turn; print every block's Δ, the minimum, and the block dates of the minimum;
  - **largest block:** the date block with the most matched evaluable in_study events (counted in `match`, before outcomes); the full primary (Δ + CI, E1 mean, xs + CI) with and without it.
- **Unmatched / widened:** count, share, fill rate and filled E1 mean of the unmatched events (these sit in the headline E1 mean but not in Δ).
- **Survivorship:** Δ and the E1 mean on (a) cache-all (every walked name, P1 drawn from the whole cache pool), (b) cache-only names, (c) `ended` names incl. `terminal` rows; the terminal row count and mean per arm. A price_cache doc exists only for names the app ever cached (since ~2024-09): a PARTIAL check. Say so.
- Every secondary row is labelled SECONDARY. The verdict reads only the primary.

### 3.8 Verdict rule (mechanical, `verdict(res) -> {"status","tags","failed"}`) — frozen
- `invalid_snapshot` if the snapshot verify failed (no other status is computed).
- If NOT `balanced` → `no_signal` + tag `imbalanced` (neither `edge` nor `inverted` can be called on an unbalanced match) (`balanced` as defined in Amendment 1, A1.2; `stats` stops before opening any outcome file).
- `inverted` if balanced and `CI_Δ.hi < 0`.
- `edge` only if balanced and ALL of:
  - (a) `CI_Δ.lo > 0`;
  - (b) `CI_xs.lo > 0` (beats RSP over the same bars, not just the tape);
  - (c) Δ > 0 in all four halves;
  - (c2) Δ > 0 in every drop-one-date-block run;
  - (d) Δ > 0 one-per-date AND one-per-symbol;
  - (e) Δ(P1s) > 0;
  - (f) Δ(cache-all) > 0;
  - (g) matched share ≥ `MIN_MATCHED_SHARE` (0.90) of evaluable in_study events.
- Otherwise `no_signal` with tags: `relative_only` ((a) passes, (b) fails); `absolute_only` ((b) passes, (a) fails: "an ordinary base low makes the same money"); `fragile` ((a),(b) pass, any of (c),(c2),(d),(e),(f) fails); `undermatched` ((g) fails).
- The printed status is this function's output, never hand-edited.

### Amendment 1 (2026-09-25, before any outcome)

**Status.** Written 2026-09-25, before any forward return, fill or outcome of any arm was computed. Every run so far was `--features-only`, so no `_arms` file has ever existed. Amendment 1 replaces only what A1.1–A1.5 name. A1.7 lists what stays frozen.

**Why: the smoke numbers.** The frozen features-only smoke failed the 3.5 balance gate. It ran at `--stride 25`: 229 names walked, 2,431 evaluable in_study events, 11,970 evaluable in_study pool rows; 2,215 events matched (527 widened, 216 unmatched). The SMDs were:
- **rho +0.114** (limit 0.1);
- delta +0.047;
- nu **−0.170** (printed, not gated);
- depth +1.733 and pos −2.119 (these two differ by construction).

A re-run on 2026-09-25 at 01:00 ET gave the same numbers to the third decimal. A features-only walk at `--stride 5` (1,154 names, 11,406 evaluable in_study events) gave rho +0.111, delta +0.052, nu −0.171, so more data does not fix it.

The imbalance is structural. A raid low sits BELOW the base floor by construction, while a placebo low sits inside an unbroken base. So inside every rho quintile the events' mean rho is higher. A symbol-cluster bootstrap of the stride-25 rho SMD gives [0.086, 0.143], and only 17% of resamples pass. Run as frozen, the study ends `no_signal + imbalanced` and never answers "enter at the raid low".

**A1.1 — P1 matcher (replaces the 3.5 P1 cells and random draws).**
- **Population (unchanged):** evaluable, non-`bad_event`, in_study events, and evaluable in_study pool rows. A draw is never the event's own symbol.
- **Covariates:** `MATCH_VARS = ("rho", "delta", "nu")`, raw, as defined in 3.2.
- **Standardisation:** `s_x = sqrt((var_ev(x) + var_pool(x)) / 2)`, ddof = 1.
  - It is computed ONCE in `match`, before any draw, over the WHOLE P1 population: every evaluable in_study event and every evaluable in_study pool row. Rows with a non-finite x are left out of that variance.
  - `z = x / s_x`.
  - P1, P1s and cache-all all use the same `s`, written to `match.json` as `match_sd`.
  - At the stride-5 walk, s = rho 0.0662, delta 0.0231, nu 0.0267.
- **Caliper:** a pair (event e, pool row p) is admissible only if `|z_e − z_p| <= CALIPER_SD` on EACH of rho, delta and nu. It is a per-covariate box, not a radius. **`CALIPER_SD = 0.4`.**
  - Reason: 0.4 SD removes about 96% of a normal covariate's bias (Cochran & Rubin 1973).
  - It is also the narrowest value on a 0.1 grid whose projected full-run matched share clears criterion (g) (≥ 0.90) with margin. 0.2 projects ~84% (the verdict would read `undermatched` after outcomes were spent). 0.3 projects ~90.5% (a coin flip). 0.4 projects ~94%.
  - The projection fits logit(share) against ln(events) over sub-samples of the stride-5 walk (table below).
  - The caliper only bounds each pair. The gate (A1.2) decides balance.
- **Distance:** Euclidean on the three z values.
- **K: `K_NN = 1`**, one nearest twin per event. The v1 value K = 5 is retired.
  - Reason: without replacement, K = 5 gives each event 1 to 5 draws. An unweighted draw arm then over-weights raids that sit in dense parts of the pool.
  - On the stride-5 features at the same caliper 0.2, K = 5 gives rho SMD +0.363, delta +0.259, nu +0.166. K = 1 gives +0.054, +0.010, −0.051.
  - Exact 1/k weights would need a weighted bootstrap that 3.7 does not have, and 3.7 stays frozen.
  - The cost is a placebo arm of about one row per event instead of five. The MDL printed by `stats` shows that price.
- **Without replacement:** a pool row serves at most ONE event within a draw set. P1, P1s and cache-all are separate sets.
- **Order:** greedy by distance, deterministic, no RNG.
  1. **Exact date.** List every admissible (event, pool row) pair with the same `dpos`. Sort by (distance, eid, pid) ascending. Walk the list and accept a pair when the event has fewer than `K_NN` draws and the pool row is unused. Kind `exact`. Running this per date gives the same result as one global list, because dates share no pool rows.
  2. **Widened, only if needed.** Only events with no draw after step 1, all dates together. List the admissible pairs with `|dpos_p − dpos_e| <= DATE_WIDEN (2)` among still-unused pool rows, sort them globally by (distance, eid, pid), and apply the same acceptance rule. Kind `widened`. An event that got an exact draw never gets a widened one.
  3. **Unmatched.** Still no draw → `unmatched`.
  - `dpos` is unchanged: the position in the sorted union of event and pool dates.
- **Tie-break:** (distance, eid, pid), smallest first. The same input always gives the same draws.
- **P1s (secondary):** the same function, `s`, caliper and K.
  - Candidates: the same symbol, `|t' − t| > ORDER_WINDOW + HOLD`, any date.
  - One pass, no widening, without replacement within P1s.
- **Cache-all (survivorship, 3.7):** the same function as P1, run on every walked name (events and pool rows not restricted to in_study), with the same `s`.
- **The v1 cell matcher** (`bin_edges`, `cell_of`, `draw_matched`, `K_PLACEBO`, `DELTA_BINS` / `RHO_BINS` / `NU_BINS`) stays in the script for ONE purpose: `match` prints its SMDs as `balance_v1`, labelled "SUPERSEDED by Amendment 1 — record only". Nothing downstream reads it.

Pre-outcome density read. Features only, K = 1, sub-samples of the stride-5 walk by `crc32(name)`. Matched share (%) of evaluable in_study events:

| in_study events in the sample | 938 | 2,086 | 3,129 | 5,281 | 7,623 | 11,406 | full run (projected, ~57,000) |
|---|---|---|---|---|---|---|---|
| caliper 0.2 | 35.6 | 47.8 | 53.1 | 59.1 | 63.2 | 68.2 | ~84 |
| caliper 0.3 | 54.5 | 65.3 | 69.5 | 74.7 | 77.7 | 81.0 | ~90.5 |
| caliper 0.4 | 65.7 | — | 78.6 | 82.5 | — | 87.2 | ~94 |

At 11,406 events with caliper 0.4:
- SMD rho +0.079, delta +0.022, nu −0.075;
- with the pre-match denominator: +0.066, +0.016, −0.060;
- pair distance p50 0.20, p90 0.41;
- P1s matched 72.7%, cache-all 84.4%.

Balance improves with density: rho SMD at caliper 0.4 runs +0.131 → +0.100 → +0.094 → +0.079 across 938 → 3,129 → 5,281 → 11,406 events. On the frozen stride-25 sample it is +0.113. **So a stride-25 sample is too sparse to judge an NN matcher.** The re-smoke reads the stride-5 walk, and the full run's own `match` stage is the real gate.

**A1.2 — Balance gate (replaces the 3.5 gate line).**
- `balanced` = `|SMD(rho)| < BALANCE_SMD_MAX` AND `|SMD(delta)| < BALANCE_SMD_MAX` AND `|SMD(nu)| < BALANCE_SMD_MAX`, with `BALANCE_SMD_MAX` = 0.1. A NaN SMD fails.
- The SMD formula is unchanged from 3.5: matched events once each vs their draws, denominator `sqrt((var_ev + var_draw)/2)` over those two sets, ddof = 1.
- **nu is now gated.** The fixed 0.5% stop makes stop-outs depend mechanically on ATR/price.
- depth and pos stay printed only.
- Printed for information only: the three SMDs with the pre-match denominator `s_x` (`smd_fixed_*`).
- **If the gate fails:** `match` prints IMBALANCED, and `stats` STOPS before it opens any `_arms` file. It prints status `no_signal (imbalanced)`, which is the 3.8 rule's own status, and writes no result JSON. No outcome is looked at.

**A1.3 — Unmatched events.**
- Events with no admissible draw stay out of Δ (as before). They are counted and reported:
  - `match` prints their n and share, and their mean rho/delta/nu beside the matched events' means (pre-outcome);
  - `stats` prints their fill rate and filled E1 mean (as before).
- They are the widest, deepest, most volatile raids. At the stride-5 read with caliper 0.4, their means were rho 0.242 / delta 0.065 / nu 0.080, against 0.108 / 0.022 / 0.041 for matched events.
- **So Δ speaks for raids that have an ordinary-base-low twin.** The unmatched raids' own mean prints beside it.
- Criterion (g), `matched share >= MIN_MATCHED_SHARE (0.90)`, is unchanged.

**A1.4 — Headline (replaces the 3.9 headline line; audit finding #8).**
- The per-fill number shown beside the placebo is now the MATCHED E1 mean, so `e1 − p1 == lift`.
- The all-fills E1 mean moves to its own clause.

`🌀 Raid-low entry (buy limit at the raid low for {W} sessions, filled only when price trades below it, stop {STOP_PCT}% under): {STATUS} — matched raids {e1m:+.2f}% per fill vs {p1:+.2f}% at an ordinary base low · lift {d:+.2f}pp [{lo:+.2f}, {hi:+.2f}] · all raid fills {e1a:+.2f}% · vs RSP {xs:+.2f}pp [{xlo:+.2f}, {xhi:+.2f}] · filled {f1:.0f}% vs {fp:.0f}% · stopped {s:.0f}%`

Keys: `e1m` = `primary.e1_mean_matched`, `p1` = `primary.p1_mean`, `d` = `primary.diff`, `e1a` = `primary.e1_mean_all`. The RSP excess is over all fills, as before.

**A1.5 — Date-halves wording (3.7; audit finding #11).** The code already uses the unique-date split from `explosive_study.py:1791-1793`. The old spec text ("split at the median event date") was wrong. Corrected text:
- Sort the matched events' unique dates. H1 = the first ⌊D/2⌋ unique dates, H2 = the rest.
- A half is half of the DATES, not half of the events.

**A1.6 — Rejected alternatives** (one line each):
- More rho bins: the skew is inside every bin, so any cell grid keeps it.
- K = 5 without weights: rho SMD +0.363.
- K = 5 with 1/k weights: needs a new weighted bootstrap, and 3.7 is frozen.
- Reusing a pool row across events: ruled out. One placebo row shared by two symbols ties the arms together in a way the symbol clusters cannot see.
- Caliper 0.2: projected ~84% matched, so (g) fails.
- Caliper 0.3: projected ~90.5%, a coin flip on (g).
- Mahalanobis distance or log(rho): the gate reads raw rho/delta/nu, so the per-covariate box on raw z matches what is gated.
- A pre-match-SD gate denominator (Stuart 2010): looser than the frozen formula. Printed only.
- Re-smoke at stride 25: too sparse for NN (+0.113 there vs +0.079 at stride 5), so it would give a false STOP.

**A1.7 — Unchanged (frozen).** Nothing below changes:
- the primary rule E1: limit at the raid low for 3 sessions, filled only when a later low goes BELOW it, no cancel, stop 0.5% under, target the base top, 21 sessions after the fill;
- the pool rule, and the W / HOLD / terminal / evaluable flags;
- the references and the secondary grid;
- the RSP-excess leg;
- `AS.boot_diff` with CI = widest of symbol and date-block, and the MDL;
- drop-one-date-block and the largest block;
- survivorship and terminal handling;
- criterion (g) and the rest of the verdict rule, except the gate definition it points to;
- the snapshot / AS_OF;
- the run window (Friday at or after 21:15 ET, or Saturday 09:30–19:30 ET) and the memory limits.

#### Re-smoke 2026-09-25 (features only, NOT QUOTABLE — no outcome computed)

`--stage match` run locally on the planner's stride-5 features-only walk (1,154 names, AS_OF 2026-09-24, 12 `_feat` chunks, 0 `_arms` files). Descriptive only; the full run's own `match` is the gate that counts.

- Matcher: 1:1 nearest twin, caliper 0.4 pooled SD on rho/delta/nu, same date then ±2, without replacement.
- Pooled SD: rho 0.0662, delta 0.0231, nu 0.0267. Pair distance p50 0.20, p90 0.41.
- Evaluable in_study events 11,406: matched 9,951 (87.2%), widened 1,116, unmatched 1,455.
- **Gated SMDs: rho +0.079, delta +0.022, nu −0.075 → BALANCED.**
- Pre-match-denominator SMDs (printed only): rho +0.066, delta +0.016, nu −0.060. depth +1.895, pos −2.246 (differ by construction).
- v1 cells on the same sample (SUPERSEDED, record only): matched 97.4%, rho +0.111, delta +0.052, nu −0.171.
- Unmatched profile: 1,455 events (12.8%), mean rho 0.242 / delta 0.065 / nu 0.080, vs matched rho 0.107 (0.1075) / delta 0.022 / nu 0.041.
- P1s matched 72.7%. Cache-all: 15,992 events, 13,504 matched (84.4%). Half-density read: 82.7% of 5,802 events.
- 87.2% is a sample share at 1/5 density, NOT criterion (g).

**Reproduced 2026-09-25 02:22–02:50 ET in a capped throwaway container** (`--stage walk,sanity,match --features-only --universe cache --stride 5 --procs 4`, 1.5 GB / 4 CPUs, 0 `_arms` files written). The planner's probe input had been deleted, so this re-walk is what backs the BALANCED line above. It printed the SAME block: 1,149 names walked (5 `bad_ohlc`), 17,090 events, PIT check 0 / 0 / 0 over 793 events, snapshot verify OK; evaluable in_study events 11,406, matched 9,951 (87.2%), widened 1,116, unmatched 1,455; **rho +0.079, delta +0.022, nu −0.075 → BALANCED**; peak worker RSS 101 MB, container peak 262 MB, 5.74 s per name. Largest date block 2026-02-17..2026-03-17 (n = 900 matched).

**Stride-25 re-smoke under Amendment 1** (the runner, same day, also features only): 2,431 evaluable in_study events, matched 1,885 (77.5%), widened 406, unmatched 546; rho +0.113, delta +0.046, nu −0.098 → IMBALANCED. Recorded so the doc does not show only the passing sample. This is the sparse-density false STOP the amendment predicted (+0.113 at stride 25 vs +0.079 at stride 5): NN balance rises with candidates per date. The gate that counts is the FULL run's own `match`.


## 4. How it is run

Read-only, in a throwaway container (never the live api container), outside RTH: Friday at or after 21:15 ET, or Saturday 09:30–19:30 ET. Pre-flight: no heavy cron job running, ≥ 1.8 GB free in the Docker VM, and the image's `amd.py` sha256 equal to the worktree's.

```bash
cd /Users/ajay/clinet-test/wt-heatlink
OUT=/private/tmp/claude-501/-Users-ajay-clinet-test/656642d4-5050-4aec-a1a8-e7114785de7b/scratchpad/raid_low_out
mkdir -p $OUT
docker cp cheetah-market-app-api-1:/root/.cheetah/universe $OUT/universe_snapshot
docker run --rm -d --name raidlow-study --memory 1.5g --memory-swap 1.5g --cpus 4 --network cheetah-market-app_default -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York -v /Users/ajay/clinet-test/wt-heatlink/backend/scripts/amd_raid_low_study.py:/study/amd_raid_low_study.py:ro -v $OUT/universe_snapshot:/root/.cheetah/universe -v $OUT:/out cheetah-api:latest sh -c 'cd /app && PYTHONPATH=/app python -u /study/amd_raid_low_study.py --stage all --universe cache --procs 4 --out /out/run --git-head PREREG_SHA > /out/run.log 2>&1'
```

- **Run it in TWO steps (critic, 2026-09-25) so no outcome exists unless the full-density gate passes:**
  1. The same `docker run` with `--stage walk,sanity,match --features-only` (no `--stride`). Read its `match` block. If it prints IMBALANCED, STOP and report it. No outcome is computed, so Amendment 2 is still possible, and only before any outcome.
  2. Only if it printed BALANCED: the same `docker run` with `--stage walk,stats --git-head PREREG_SHA`. The walk resumes and writes the `_arms` chunks. `feat_fingerprint` and `snapshot_verify` guard against a changed walk, and `stats` re-checks the gate before it opens any `_arms` file.
- `PREREG_SHA` = the commit that holds this file. Resume = the same command (finished chunks are skipped; `snapshot_t0.json` keeps AS_OF fixed).
- Exit 3 = a worker died (rerun with `--procs 3`). Exit 4 = a walked name's bars ≤ AS_OF changed during the run (remove the chunks named in `snapshot_fail.json`, rerun).
- 2026-09-24 repair: `match.json` stores a `feat_fingerprint` (chunk list, walked names + bar digests, event/pool row counts). `--stage stats` exits if it differs from the current feat files, so a re-walk followed by `stats` alone can never index stale draws. Rerun `--stage match,stats` (or `all`).
- Smoke runs (`--features-only --stride 5 --stage walk,sanity,match`; the NN matcher needs the density, spec 3.10) compute no outcome and are NOT QUOTABLE.
- His surface: `--explain ORCL 2026-08-19` / `--explain ORCL 2026-09-01` (and CRDO, GLW) must show the same date, `raid_price` and `raid_level` as the bullish rows of `amd_raids` on `GET /chart-maps/support?symbol=X&studies=true`.

Descriptive facts known before the run (read-only probe, no outcome computed):

**No forward return, fill rate or outcome was computed. Pre-registration is intact.**
- Universe: `study_universe()` = full 2,734 ∪ broad 3,728 = **3,766**, 3,761 in `price_cache`. Bars per name median 504, max 1,242. First bar 2024-09 for 3,552 names; last bar 2026-09-24 for 3,680.
- `price_cache`: 6,233 docs, 5,660 with ≥150 bars. 1,933 cache-only names with ≥150 bars (last bar 2026-09 for 1,070, 2026-08 for 691, earlier ~130).
- 24-name sample (10,319 bars): 483 bullish raids (4.7% of bars). Full-frame vs prefix walk: identical. 211-bar tail slice: identical. 9.1 ms per prefix call.
- `open_base` exists on 73.7% of non-raid bars; the close sits inside it on 52%.
- Geometry: raid low under the edge (`depth_pct`) median **0.69%** (p10 0.13, p90 3.00) — the brief's "~1-4% apart" is wrong; raid low under the raid close median 2.23%; raid low to base top median 12.0% (p10 5.5, p90 24.2).
- ORCL fixture, t ≥ 120: prefix vs 120/100/60/40-bar slices, 0 raid-field and 0 `open_base` mismatches (chain fields were not compared).

## 5. Results — RUN 2026-09-25 21:22 → 2026-09-26 00:55 ET · **NO_SIGNAL**

From `backend/scripts/amd_raid_low_measured.json`, written by `stats` at `--git-head b90edd9` (the pre-registration commit; `script_sha256` 507bf9ad…, `amd_sha256` 18bd410a… = the image's, the worktree's and the live api's `amd.py`). AS_OF 2026-09-25. Run in the two steps of §4. Nothing in §3 was changed after the first `stats` print.

**Headline (verbatim from `stats`):**

> 🌀 Raid-low entry (buy limit at the raid low for 3 sessions, filled only when price trades below it, stop 0.5% under): NO_SIGNAL — matched raids +0.02% per fill vs +0.03% at an ordinary base low · lift -0.01pp [-0.06, +0.03] · all raid fills +0.03% · vs RSP +0.10pp [-0.06, +0.26] · filled 57% vs 60% · stopped 95%

**Verdict (mechanical, §3.8):** `no_signal`, tags none, failed (a) (b) (c) (c2) (d) (e). (f) and (g) passed. Balanced, so `inverted` was callable and was not met: the lift CI straddles zero.

### 5.1 Step 1: the gate, features only (no outcome existed)
- Walked 5,744 names (29 skipped `bad_ohlc`); 87,111 events (`bad_event` 0), 454,963 pool rows; 2017-03-16 .. 2026-09-25, 1,091 sessions. `in_study` list 3,766, walked 3,738; 1,663 ended names.
- In study: 57,780 evaluable events, 5,473 open (excluded, counted), 60 terminal.
- PIT check (50 names, 760 events): set / attr / history / `open_base` mismatches all 0. Snapshot verify: 0 docs moved, 0 bars differ (both steps).
- **Amendment 1 match: 53,605 matched (92.8%), 3,416 widened, 4,175 unmatched. SMD rho +0.057, delta +0.014, nu −0.060 → BALANCED** (the stride-25 re-smoke's IMBALANCED was the sparse-density false stop the amendment predicted). Filled subsets: rho +0.054, delta −0.017, nu −0.050. v1 cells (record only): rho +0.116, nu −0.168.

### 5.2 Primary
| | value |
|---|---|
| E1 mean per fill, all evaluable in_study | **+0.03%** [−0.07, +0.13], n 32,699 fills |
| Matched E1 vs P1 (nearest twin, same date) | +0.02% vs +0.03% |
| **Lift Δ** (widest of symbol [−0.05, +0.02] and date-block [−0.06, +0.03]) | **−0.01pp [−0.06, +0.03]**, MDL 0.06pp |
| Excess over RSP (leg b) | +0.10pp [−0.06, +0.26], n 32,672 (no_bench 27) |
| Fill rate E1 / P1 / E2 | 56.6% / 60.5% / 70.7%; E1 − P1 **−2.63pp [−3.31, −1.95]** |
| E1 exits | stopped 94.7% (gap-stop 10.2%), target 5.0%, clock 0.3%, terminal 0.0% |
| Win rate · median · trimmed mean | 5.3% · −0.50% · −0.17% |
| Per-event expectancy (unfilled = 0) · mean fill delay | +0.02% · 1.48 sessions |
| Unmatched 4,175 (7.2%, in the headline mean, not in Δ) | fill rate 40.2%, filled E1 mean +0.25% |

### 5.3 Stability (point Δ)
- Date halves −0.06pp / +0.03pp; symbol halves −0.01pp / −0.02pp; one-per-date −0.29pp; one-per-symbol +0.09pp; same-symbol twin (P1s) −0.03pp.
- Drop-one-date-block: every one of the 18 runs is ≤ 0; minimum −0.03pp without 2026-03-09..04-07.
- Largest block (2026-02-05..03-06, n 4,112): with it Δ −0.01pp [−0.06, +0.03], xs +0.10pp [−0.06, +0.26]; without it Δ −0.01pp [−0.06, +0.04], xs +0.13pp [−0.03, +0.30].
- Survivorship (PARTIAL — `price_cache` holds only names the app ever cached, since ~2024-09): cache-all Δ +0.01pp (81,270 events); cache-only Δ −0.01pp (23,490); ended names Δ −0.01pp (19,859). Terminal rows: E1 645 fills, mean +0.12%; placebo 5,357 fills, mean −0.01%.

### 5.4 SECONDARY — labelled, no verdict
| Key | E1 mean per fill | Δ vs its placebo |
|---|---|---|
| S1 ATR-scaled stop | +0.12% [−0.10, +0.36] | −0.02pp [−0.09, +0.06] |
| S2 1-ATR stop | +0.63% [−0.18, +1.49] | +0.07pp [−0.09, +0.24] |
| X1 target = swept edge (no placebo) | −0.10% [−0.13, −0.06] | — |
| X2 no target | +0.09% [−0.05, +0.23] | −0.01pp [−0.09, +0.08] |
| X3 no stop, no target, 21 sessions | +2.76% [+1.04, +4.63] | +0.03pp [−0.29, +0.35] |
| W10 window | +0.03% [−0.06, +0.13] | −0.03pp [−0.07, +0.01] |
| W25 window | +0.04% [−0.05, +0.14] | −0.03pp [−0.07, +0.01] |
| FT touch fill | +0.12% [+0.01, +0.24] | −0.03pp [−0.08, +0.02] |
| Price ≥ $2 | +0.04% [−0.06, +0.14] | −0.00pp [−0.04, +0.04] |
| First sweep | +0.03% [−0.07, +0.14] | +0.00pp [−0.06, +0.07] |
| Re-sweep | +0.02% [−0.07, +0.14] | −0.03pp [−0.11, +0.04] |
| CX cancels (no placebo) | +0.02% [−0.07, +0.12] | paired CX − E1 −0.00pp [−0.01, +0.00] |

References: E0 (buy the raid close) +0.29% [−0.20, +0.74]; E0N (next open, 95.8% taken) +0.29% [−0.10, +0.67]; E2 (limit at the swept edge, 70.7% filled) +0.19% [−0.08, +0.50]. Paired per event: E1 − E0 −0.27pp [−0.68, +0.16]; E1 − E2 −0.12pp [−0.28, +0.03].

Selection diagnostic (conditions on the future; descriptive only): E0 on events where the E1 limit later FILLED −2.22% [−2.49, −1.97]; where it never filled +3.57% [+3.08, +4.05]. Price trading back under the raid low is itself the bad news, which is why the limit at the low collects the losers. The HINDSIGHT row is in the JSON and is not quoted (§6).

X3's E1 mean is the only primary-family mean whose CI clears zero, and the ordinary base low makes the same (+0.03pp [−0.29, +0.35]): it is the tape over 21 sessions, not the raid.

### 5.5 His surface — the study's events are the tile's raids
`--explain` against the bullish rows of `amd_raids` on `GET /chart-maps/support?symbol=X&studies=true` (live api, 2026-09-25 evening). Date, `raid_price` and `raid_level` agree to the cent on all seven:

| Raid | L / E | Study |
|---|---|---|
| ORCL 2026-08-19 | 137.43 / 138.72 | unfilled (evaluable) |
| ORCL 2026-09-01 | 139.95 / 141.02 | filled 09-02 at 139.95, target 153.99 on 09-03 (+10.03%) — but **open** (the 21-session hold runs past AS_OF), so excluded |
| ORCL 2026-09-24 | 133.48 / 139.00 | open, excluded (today's raid) |
| CRDO 2026-08-19 | 229.18 / 231.25 | filled 08-20, stopped the same bar, −0.50% |
| CRDO 2026-07-28 | 184.68 / 185.865 | filled 07-29, stopped the same bar, −0.50% |
| GLW 2026-08-19 | 150.70 / 150.73 | filled 08-20, stopped the same bar, −0.50% |
| GLW 2026-06-09 | 166.00 / 172.43 | unfilled (evaluable) |

### 5.6 Hand-audit (seed 20260925: 3 filled E1, 3 filled P1 draws, 1 terminal)
All seven re-walked by `--explain` from the raw bars and checked by eye: fill bar strict, fill price `min(open, L)`, stop / target / terminal, `ret`. **7 / 7 correct.**
- CAMT 2026-02-03, NKTX 2025-11-05, RNA 2026-05-19 (E1): filled next bar at L, low through S0 on the fill bar → stop at S0, −0.50%.
- NET 2025-11-14, DNLI 2025-12-19 (P1): same, −0.50%. DNLI's first window bar printed a low EQUAL to L (16.81) → correctly NOT a fill (strict); filled the next bar.
- RMNI 2025-12-24 (P1): fill-bar low 3.925 (prints 3.92 at 2 dp) is above S0 3.9203 → no fill-bar stop; the next bar opened 3.90 under S0 → exit at the open, −1.015%. Correct; the 2-dp print is what made it look wrong.
- FFIC 2026-05-11 (terminal, ended name): opened 15.48 under L 15.54 → filled at the open; low through S0 15.4623 → −0.114%. Correct.

### 5.7 What this does NOT say
- It does not say raids are meaningless. It says **this entry** — a limit at the raid low, 0.5% stop, target the base top — earns what the same order at an ordinary low in the lower third of a base earns: about nothing, because 95% of fills are stopped within a session or two.
- It does not test a wider stop as a claim. S2 (1 ATR) and X3 (no stop) are SECONDARY; neither beats its placebo.
- It does not measure bearish (high) raids, the markup claim (`AMD_MEASURED`, −4.2pp) or any lane. No surface line, sort, alert or paper variant follows from it (§6, §7.6).
- Survivorship is partial (§5.3).

## 6. What this can never say

- It does not answer the −4.2pp markup claim (`AMD_MEASURED`), and that number does not answer this rule — in either direction.
- The HINDSIGHT line (entry at the raid low ON the raid bar) is lookahead. It is not a result and is never quoted.
- A per-fill mean conditions on price coming back through the low. It is always read beside the fill rate, the per-event expectancy and E0 given fill / no fill.
- Bearish (high) raids are not measured. X1, CX and HINDSIGHT have no placebo and are descriptive only.
- No lane, alert, sort or surface line follows from any verdict, `edge` included, without a named paper variant and his call (a separate Rule #10 step).
- Survivorship is only partly covered: `price_cache` holds names the app ever cached (since ~2024-09).

## 7. HIS CALL (frozen defaults below stand unless he overrides BEFORE the full run)

1. **The primary rule:** W = 3 board sessions, strict fill (price trades below the raid low), no cancel, stop 0.5% under the raid low, target = base top, 21 sessions after the fill.
2. **The absolute leg (b) reads the excess over RSP**, not the raw return (critique 3). Also: whether "loses less than an ordinary base low" counts for anything — as written it reads `no_signal` + `relative_only`.
3. **Strict fill vs touch fill as the primary** (critique 7). Default strict; touch is secondary FT.
4. **Primary universe = full ∪ broad incl. ETFs and sub-$2 names.** The lanes' $2 floor is a secondary cut only.
5. **The detector is untouched.** "Make the manipulation a lil better" is still unanswered; this measures the shipped `find_raids`.
6. **Any wiring after a result** (surface line, sort, alert, paper lane variant) is a separate Rule #10 step: a named paper variant, then his promote. Nothing follows automatically from `edge`.

