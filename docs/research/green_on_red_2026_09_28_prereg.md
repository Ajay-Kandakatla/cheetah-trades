# Green on a red day — PRE-REGISTRATION + build spec (planner, 2026-09-28)

Status: **PRE-REGISTERED, FROZEN at rev 1 (2026-09-28 23:05 ET), NOT RUN.** Rule #10 research step. Nothing in the app changes because of this study: no surface, lane, gate, alert, sort, chip, rule line, and no newFeatures.ts entry.
Rev 1 applies the critic's seven findings (probe `scratchpad/crit_gor/probe.py`, 22:57 ET). The changelog is §8. Rev 0 is kept at `scratchpad/plan_gor_rev/green_on_red_prereg.rev0.md`. Any further change, before the full run, is a new revision with its own changelog line. After the full run, nothing in §3 changes.
Worktree `/Users/ajay/clinet-test/wt-gord`, branch `feat/green-on-red-study-2026-09-28` (off origin/main, head `4395282`).

---------------------------------------------------------------------------------------------------
## 0. The ask, verbatim

Ajay, Mon 2026-09-28, after the close:
> "I have a theory, Stocks that are green in this bearish day are lilly to be in high demand what are those? I saw Voyager is one of the,"

**Hypothesis, in his words, made testable:** a stock that closes green on a bearish day, on heavy volume and near its high of the day, is "in high demand". If that is true, it should keep beating the market afterwards **from the first price he can actually get**. He saw the list after the close, so that price is the next session's open. Test: bought at the next open and held **10 sessions**, these names beat RSP by more than names that closed red on the **same** day and looked the same **the day before** (the matched twins).

The "what are those?" half is already answered: the main session's 56-name list at `scratchpad/gor_dem_2026_09_28.json`, with VOYG in it. This study answers the "theory" half only.

---------------------------------------------------------------------------------------------------
## 1. Facts (file:line), constants by name, prior measurements

### 1.1 Data engine (read-only)
- `sepa/prices.py:105` `bulk_cached_frames(symbols)`: ONE `find` on `price_cache` and never a fetch. It returns a DatetimeIndex frame with open/high/low/close/volume, then applies `_drop_phantom_tail` (`:149`). It does no TTL check. Its docstring says the cache is **not** closed-bars-only inside the session, because `crontab:407` (`0 9-16 * * 1-5 … vcp-watch`) patches today's bar every hour. The 16:30 post-close fast-scan (`crontab:34`) patches it again.
- `sepa/prices.py:409` `_drop_phantom_tail`: drops at most ONE trailing bar, and only when its close equals the prior close exactly AND its volume is within 0.5%. After the close, a real 09-28 bar is dropped only in that coincidence. The name then has no AS_OF bar. The effect is confined to AS_OF-day breadth and to carry-forward outcomes (3.7). No scored signal day is lost, because AS_OF is never a signal day.
- `supply_demand/demand_reentry.py:1363` `split_today_partial(df)`: splits off a today-dated bar only while `_session_fraction(now) < 1.0` (`:233`). After 16:00 ET the bar stays. In pre-market (04:00–09:30) a today-stamped bar is dropped.
- `sepa/prices.py:469-472` `_SCALE_GLITCH_RATIO = 5.0` and `_is_scale_glitch(new, prev)`: the house detector for decimal-shift and unadjusted-split artefacts.
- Index: tz-naive, with MIXED stamps. Historical bars are 04:00. Today's snapshot-patched bar is 00:00 (probe: RSP `…2026-09-25 04:00`, `2026-09-28 00:00`; 2,677 names end on a 00:00 bar). **Compare by `YYYY-MM-DD` day key only.** This is the house `cap_as_of` rule (raid-low script `amd_raid_low_study.py:194`, branch).
- Cache depth: **500 bars per name**, 2024-09-30 → 2026-09-28. Frame-length percentiles are 5%=433, median 500, min 29, max 1016 (probe). RSP has 500 bars.
- Volume: historical aggregate bars carry fractional volume. The snapshot-patched today bar carries rounded volume (VOYG 2,519,069.10 vs 2,857,972.0). This affects only the AS_OF-day repro RVOL.
- `sepa/universe.py:2209` `load_universe('full')` returns **2,730** names. It includes **18 ETFs** (IBIT, FBTC, BITO, BLOK, WGMI, BITQ, DAPP, BOTZ, ROBO, ARKQ, ROBT, SPY, QQQ, IWM, IGV, XLE, JETS, SMH). `:2025` `fetch_etf_universe()` is a static list of 373 with no network. `:40` `RS_ANCHORS = ("SPY","QQQ","IWM")`.
- `scripts/explosive_study.py:617` `symbols_for("cache", need_bars)` = every `price_cache` doc with ≥ need_bars bars, dead names included. This is the survivorship universe. The raid-low run walked 5,744 names this way, 1,663 of them ended.
- `sepa/market_gauge.py:220` `_breadth_red_pct()` reads only the LATEST scan's rows, so it cannot give historical breadth. There is no historical breadth engine in the repo. This study defines one (3.3), on its own universe.
- House cluster conventions (rev 1): `scripts/turning_bullish_amd_study.py:311-313` builds FIXED calendar blocks `blk[h] = (dpos // h)` and `:256-259` `report_cell` takes the wider of two groupings. `scripts/promo_tag_study.py:98` `MIN_CLUSTERS = 20` ("a percentile CI over fewer than this many independent clusters is not a CI, it is the clusters … it is his to move") and `:536` returns a NULL CI below it or below 100 usable draws (`scripts/explosive_study.py:904` the same 100 literal). `scripts/promo_tag_study.py:110` `PRIMARY = ("pooled", 5, "open", …)`: the house precedent for a next-open primary. `tests/test_promo_tag_study.py:25` imports that module hermetically.

### 1.2 Constants reused BY NAME (never retyped)
| study name | source | value |
|---|---|---|
| `BENCH` | `rotation/tracker.py:81` `RT.BENCHMARK` | "RSP" |
| `R_SHORT` | `rotation/tracker.py:90` `RT.WINDOW_SHORT` | 21 |
| `R_MED` | `rotation/tracker.py:91` `RT.WINDOW_MED` | 63 |
| `VOL_BARS` | `sepa/breakout_audit.py:30` `BA.VOL_AVG_BARS` (prior-only denominator, `:41` `rolling(VOL_AVG_BARS).mean().shift(1)`) | 50 |
| `RVOL_MIN` | `supply_demand/momentum_burst.py:48` `MB.BURST_RVOL_MIN` (inclusive `>=`, `:222`) | 1.5 |
| `PRICE_FLOOR` | `trading/safety_floor.py:48` `SF.MIN_SHARE_PRICE` | 2.00 |
| `DVOL_APP` | `trading/safety_floor.py:50` `SF.MIN_DOLLAR_VOL` (secondary cut only) | 20,000,000 |
| `HIGH_BARS` | `supply_demand/stock_supply_demand.py:48` `SSD.LOOKBACK_DAYS` | 252 |
| `LEADER_NEAR_HIGH_PCT` | `supply_demand/stock_supply_demand.py:53` `SSD.NEAR_HIGH_PCT` ("within 15% of the 52w high") | 15.0 |
| `HORIZONS` | `scripts/turning_bullish_amd_study.py:77` `AS.HORIZONS` | (5, 10, 21) |
| `MIN_CLUSTERS` (rev 1) | `scripts/promo_tag_study.py:98` `PT.MIN_CLUSTERS` | 20 |
| bootstrap | `scripts/turning_bullish_amd_study.py:223` `AS.boot_diff` (paired cluster, returns `reps`), `:216` `AS._clusters`, `:247` `AS.widest` | — |
| RVOL arithmetic | `scripts/explosive_study.py:456` `ES._rvol` (pinned equal on a gap-free frame) | — |
| `ES.trimmed_mean` `:1062`, `ES._clean` `:1493` (JSON NaN→null) | | — |
| glitch | `sepa/prices.py:472` `PR._is_scale_glitch` | 5x |

The 50-day SMA has no named constant. The literal is `sepa/trend_template.py:40` `close.rolling(50)`. It is typed as `MA50_BARS = 50` with that cite. The 100-draw floor has no named constant. The literal is `scripts/explosive_study.py:904` / `scripts/promo_tag_study.py:536`. It is typed as `MIN_BOOT_REPS = 100` with those cites.

### 1.3 Today (2026-09-28), measured by the main session and re-derived by the planner probe (no forward returns)
- RSP −0.65%, SPY −0.74%, QQQ −1.07%, IWM −0.69%. Main session: 788 green / 1,850 red of 2,672.
- Planner probe (`scratchpad/gor_prereg_count.py`: full universe minus the ETF set, 2,712 names, 2,657 valid on 09-28): **789 up, breadth 0.297, red-day rule = TRUE, S1 = 616, S2 = 56**. S2 reproduces the 56-name list exactly in count.
- VOYG: +5.84%, RVOL 1.55, cr 0.88, below its 50-day, −36.7% off its 52w high, 326 bars (listed 2025-06-11). It is **not** a leader. 9 of the 56 are leaders.

### 1.4 Pre-outcome design diagnostics (planner and critic probes, calendar-aligned panel, NO return computed)
Rev 0 from `scratchpad/gor_prereg_count.py` and `scratchpad/gor_prereg_match.py`. Rev 1 from `scratchpad/plan_gor_rev/probe_rev.py`, run 23:02 ET, output `scratchpad/plan_gor_rev/probe_rev.out`. It computes no return: its only look past t is whether `O[t+1]` is finite. The probes approximate the script (no `split_today_partial`, no glitch filter, frames ≥ 70 bars). The script's own `--stage match` reprints every number below, and the §5 stop rule reads THAT print.

| window for t (h=10 must fit) | sessions | red days | SPY ≤ −0.5% days | S2 on red | S1 on red | S2 on non-red |
|---|---|---|---|---|---|---|
| bar ≥ 64 (2024-12-31 → 2026-09-14) | 426 | **78** | 86 | 5,427 | 37,157 | 41,800 (348 days) |
| bar ≥ 126 | 364 | 65 | 69 | 4,466 | 31,573 | 36,023 |
| bar ≥ 252 (strict 52w lookback) | 238 | 40 | 48 | 2,722 | 21,746 | 23,537 |

1:1 same-day nearest-neighbour matching, exact on above50, without replacement. These are red-day S2 rows with every feature: 5,419 signals, h10-eligible.
| match set | caliper 0.6: share | max abs SMD | caliper 0.4: share | max abs SMD |
|---|---|---|---|---|
| rev 0: r21, r63, off52, ldv20, vol20 | 0.882 (4,777 pairs) | **beta63 −0.165** (ungated; signals 1.17 vs twins 1.29) | 0.751 | beta63 −0.157 |
| **rev 1: + beta63** | **0.818 (4,434 pairs)** | vol20 0.067 (beta63 −0.022) | 0.619 (3,355) | vol20 0.044 |
| rev 1, S3 non-red days | 0.700 (29,182 of 41,686) | — | — | — |

Cluster counts. The rev 1 match (4,434 pairs), per h, pairs with t ≤ T−1−h:
| h | pairs | red days | G fixed blocks `t // h` | G month blocks `t // 21` | largest month block's pair share | entry O present, both members |
|---|---|---|---|---|---|---|
| 5 | 4,434 | 78 | 54 | 21 | 12.2% | 99.98% |
| 10 | 4,434 | 78 | 38 | **21** | 12.2% | 99.98% |
| 21 | 4,236 | 73 | 20 | **20** | 12.8% | 100% |

Rev 0's chained episodes gave h5 32, **h10 10**, **h21 1** (critic probe). Three of them held 77% of the pairs. The S3 non-red match gives G 43 (`t // 10`) and 21 (`t // 21`).
Near the price floor (PRICE_FLOOR ≤ C_t < 2 × PRICE_FLOOR), h10 pairs: **41 signals, 54 twins of 4,434** (~1% per arm).

The 91 red days in the whole cache run from 2024-10-01 → 2026-09-28. The April-2025 cluster (04-03, 04-04, 04-07, 04-08, 04-10) has overlapping 10-session windows.

### 1.5 Prior measurements (the prior on a new signal is NULL)
- Nothing in `docs/` or memory measures "green on a red day". This is new.
- Related nulls: 🧨 explosiveness (2026-09-15): RVOL, dollar volume and the 52w box predict nothing beyond ~2.2pp on 24,922 reversal episodes. Sector heat (2026-09-09): no signal, −0.57pp with a CI spanning 0. ⚡ momentum burst: UNMEASURED.
- Board-growth (2026-09-21): boards ran BEFORE the filing. Incumbency ≠ future.
- Hot Pullback (2026-09-09): a claimed +0.27R was a **dropna-before-rolling** off-by-49 bug. The corrected result was +0.10R with a CI through 0.
- Literature risk (named, no number quoted): the short-term (1-day to 1-month) cross-sectional reversal effect predicts that same-day winners give back against same-day losers. Priced at the close, the bid-ask spread effect pushes the same way. The prior leans AGAINST his theory at short horizons. This is why rev 1 prices the primary at the next open and makes the verdict symmetric.

---------------------------------------------------------------------------------------------------
## 2. Decision

**Build one vectorised, read-only study script on a calendar-aligned panel.** It matches each green-on-red name 1:1 to a same-day red-closing twin, nearest-neighbour on pre-signal features including beta. The outcome is the 10-session excess return over RSP, **bought at the next session's open**. The CI is the widest of three paired cluster bootstraps (`AS.boot_diff`): by red day, by fixed `t // h` blocks, and by fixed 21-session blocks. It is null below `MIN_CLUSTERS`. The verdict is mechanical and symmetric. The script is copied into `cheetah-market-app-api-1:/tmp` and run with `docker exec` after 17:30 ET. Artefacts are copied out.

Refinements to the brief's defaults. Each one tightens or disambiguates. Rev 1 changes are marked:
1. **vol20 and (rev 1) beta63 are in the matching set.** Volatility alone drives the spread of 10-day excess. Beta is the red-day confound the twins exist to remove. The 5-covariate match left beta63 SMD −0.165.
2. **(rev 1) CI = widest of red-day, `t // h` and `t // BLOCK_SESSIONS` groupings, all FIXED calendar blocks (house `AS:311-313`).** If any grouping has fewer than `MIN_CLUSTERS` clusters or fewer than `MIN_BOOT_REPS` usable draws, the CI is NULL. It never falls back to a narrower grouping. G is recorded.
3. **(rev 1) The verdict is symmetric.** INVERTED needs the mirrored stability checks, the same way SIGNAL needs the positive ones (3.12). A red-day-specificity tag comes from S3.
4. **Caliper 0.6 pooled SD, MIN_MATCHED_SHARE (rev 1) 0.80.** The floor rule, unchanged from rev 0, is "the pre-outcome design share, rounded down to the 0.05 grid": rev 0 0.882 → 0.85, rev 1 0.818 → 0.80. The house 0.4 caliper is kept as stability run (f2).
5. **(rev 1) The primary entry is the next session's open (house precedent `PT.PRIMARY` "open").** Red-day status, breadth, cr and the final volume are known only at the close, and he saw the list after the close. Entry at the signal-day close is criterion (e), a same-sign check.
6. **The 52w-high feature uses up to 252 bars, with a floor of 63.** A strict 252 halves the red days (78 → 40). Twins come from the same day and so carry the identical truncation. Strict-252 is secondary S10.
7. **Calendar-aligned panel.** "Prior close" is the prior SESSION. NaN marks a missing bar, and rows are never dropped before a rolling window (the Hot Pullback bug).
8. **ETFs are excluded** (`fetch_etf_universe()` ∪ `RS_ANCHORS` ∪ BENCH). His question is about stocks. The S2 count on 09-28 stays 56.

Alternatives rejected:
- Coarsened strata with random draws (`promo_tag_study.matched_placebo`): these do not balance continuous features. The raid-low v1 cells stayed imbalanced (Amendment 1).
- Importing `match_nn`/`balance_gate` from `amd_raid_low_study.py`: that file exists only on unmerged branch `feat/amd-raid-low-study-2026-09-24`, and the container runs origin/main. The semantics are copied; the file is not imported.
- Raw mean of S2 vs RSP only: a red-day beta confound. Low-beta names are green because they are low beta.
- (rev 1) Chained overlap episodes (rev 0): 10 clusters at h10 and 1 at h21. Three held 77% of the pairs.
- (rev 1) Keeping the 5-covariate match and gating beta63's SMD: −0.165 measured before any outcome, so the run would be `imbalanced` by construction.
- (rev 1) Keeping MIN_MATCHED_SHARE 0.85 with beta63 in the match: share 0.818 measured before any outcome, so the run would be `undermatched` by construction.
- (rev 1) Widening the caliper to win back matched share: this trades balance for coverage and was not probed. The caliper stays 0.6.
- (rev 1) Keeping the at-close entry primary and adding an entry-O CI: the headline number would still be a price nobody can get.
- A per-symbol event walk: not needed. The features are closed-form rolling windows, so a vectorised panel is exact and runs in minutes.
- Fetching longer history: that is a network write path, and the brief makes it read-only.
- The throwaway-container recipe (raid-low): the brief mandates `docker exec` in the api container. The job is light, under ~0.6 GB peak.

---------------------------------------------------------------------------------------------------
## 3. Design (exact) — FROZEN rev 1

### 3.1 Files (house layout)
- Script: `backend/scripts/green_on_red_study.py` (house: `amd_raid_low_study.py`, `board_growth_study.py`).
- Tests: `backend/tests/test_green_on_red_study_2026_09_28.py`.
- Result: `backend/scripts/green_on_red_measured.json`, written by the run and copied out.
- Doc: `docs/research/green_on_red_2026_09_28.md` (house: `docs/research/board_growth_2026_09_21.md`).

### 3.2 Study-design constants (typed; each labelled `# STUDY DESIGN`)
Every function reads these as MODULE GLOBALS at call time. None is bound as a default argument, so tests can monkeypatch them (test 17 proves this).
```
STUDY = "green_on_red_study_2026_09_28"
PREREG_REV = 1
UNIVERSE_MODE = "full"
RED_RSP_PCT = -0.5            # RSP close-to-close %, rounded to 4 dp, inclusive <=
RED_BREADTH_MAX = 0.35        # share of valid names with close > prior close, inclusive <=
MIN_BREADTH_NAMES = 1000      # a day with fewer valid names is UNCLASSIFIED (never red, never non-red)
SPY_SYMBOL = "SPY"; SPY_RED_PCT = -0.5   # sensitivity definition
DVOL_MIN = 10_000_000.0       # the list he saw: close_t * volume_t
CR_MIN = 0.5                  # (close-low)/(high-low) >= 0.5; high == low -> not S2
MA50_BARS = 50                # sepa/trend_template.py:40 literal
FIRST_T = R_MED + 1           # 64: r63 at t-1 needs close[t-64]
HIGH_MIN_BARS = R_MED         # off52 lookback floor (63 of up to HIGH_BARS=252)
H_PRIMARY = 10                # assert in HORIZONS
PRIMARY_ENTRY = "O"           # rev 1: next session's open (house precedent PT.PRIMARY "open")
CHECK_ENTRY = "C"             # rev 1: signal-day close; criterion (e), same-sign check only
ENTRIES = ("O", "C")
EVENT_POP_PCT = 20.0          # secondary: signal day change > +20% excluded
MATCH_VARS = ("r21", "r63", "off52", "ldv20", "vol20", "beta63")   # rev 1: + beta63
MATCH_VARS_REV0 = ("r21", "r63", "off52", "ldv20", "vol20")        # secondary S9 only
EXACT_VARS = ("above50",)
CALIPER_SD = 0.6              # per-covariate box in pooled SDs (1.4 diagnostic)
CALIPER_SD_HOUSE = 0.4        # amd_raid_low_study Amendment 1 value; stability run (f2)
BALANCE_SMD_MAX = 0.1         # same value as amd_raid_low_study (branch)
MIN_MATCHED_SHARE = 0.80      # rev 1 (was 0.85): design share 0.818 rounded down to the 0.05 grid; HIS CALL §7-8
MIN_BOOT_REPS = 100           # house literal: explosive_study.py:904, promo_tag_study.py:536
BOOT_B = 2000; BOOT_SEED = 7  # house values (AS.boot_diff seed default 7)
MDL_Z = 2.8
BLOCK_SESSIONS = R_SHORT      # rev 1: 21-session fixed blocks, a grouping in EVERY CI and the unit of drop-one (c2)
BETA_MIN_PAIRS = 60           # beta63 needs >= 60 finite paired returns
BIG_MOVE_PCT = 40.0           # data audit only (never a filter)
NEAR_FLOOR_BAND = 2.0         # rev 1, audit only (L9): PRICE_FLOOR <= C_t < NEAR_FLOOR_BAND*PRICE_FLOOR, counted by arm
PIT_CHECK_NAMES = 50; PIT_SEED = 20260928
ENDED_GRACE_DAYS = 7          # house value; cache check only
REFUSE_WINDOW_ET = ("09:00", "17:30")   # Mon-Fri; exit 5 unless --force-window
REPRO_DAY = "2026-09-28"; ANECDOTE_SYMBOL = "VOYG"
VERDICT_RULE_TEXT = "..."     # the text of 3.12, verbatim
TAG_TEXT = {...}              # 3.13, verbatim
```
`MIN_CLUSTERS` is IMPORTED as `PT.MIN_CLUSTERS` (`scripts/promo_tag_study.py:98`, 20) and never retyped. Test 17: every reused name is an import (identity pin), and a regex guard proves none of them is retyped as a literal.

### 3.3 Universe, snapshot, panel
- `EXCLUDE = set(U.fetch_etf_universe()) | set(U.RS_ANCHORS) | {BENCH}`.
- `names = [s for s in dict.fromkeys(U.load_universe(UNIVERSE_MODE)) if s not in EXCLUDE]`. Write the sorted list to `OUT/universe.txt` and its sha256 into the JSON.
- `AS_OF` = the last day key of `DR.split_today_partial(bulk_cached_frames([BENCH])[BENCH])[0]`.
- `load_frames(symbols, as_of) -> dict[str, DataFrame]`: `bulk_cached_frames(symbols)` → `split_today_partial(df)[0]` → `cap_as_of(df, as_of)` (day keys ≤ AS_OF) → duplicate day keys keep the LAST row (count `dup_day_keys`). Store `bars_digest` (sha1 of O/H/L/C/V float64 bytes).
- Calendar `cal` = BENCH's day keys ≤ AS_OF. `T = len(cal)`.
- `build_panel(frames, cal) -> Panel` (dataclass: `syms`, `cal`, `O,H,L,C,V` as N×T float64). Each name is reindexed on its day keys onto `cal`. A missing session is NaN. A bar on a day outside `cal` is dropped and counted. Non-finite or ≤0 O/H/L/C becomes NaN. **Never dropna before a rolling window.**
- **Snapshot verify (end of run):** re-read `bulk_cached_frames` for every name, run the same `split_today_partial`/`cap_as_of`, and compare digests. Any difference → `snapshot.ok = False` → status `invalid_snapshot`, exit 4. Bars appended after AS_OF never trip it.
- **Refusal window:** `in_refusal_window(now_et)` is True Mon–Fri 09:00 ≤ now < 17:30 ET. The script exits 5 in that window unless `--force-window` is given (tests only). This covers the hourly `crontab:407` patches and the 16:00/16:30 post-close patches.

### 3.4 Day change, breadth, red days
- `day_change(P) -> ndarray N×T`: `chg[:,t] = C[:,t]/C[:,t-1] - 1`, valid only when both are finite and > 0 and `not PR._is_scale_glitch(C[:,t], C[:,t-1])`. Otherwise NaN. The prior close is always the prior SESSION (`cal[t-1]`). A name with no bar on `cal[t-1]` has NaN on t.
- `breadth(chg) -> (share[T], n_valid[T])`: `n_valid = count(isfinite(chg[:,t]))`; `share = count(chg[:,t] > 0) / n_valid`. It is computed on the SAME panel whose rows produce signals and twins. Unchanged names (`chg == 0`) are valid but not green.
- `red_days(bench_close, share, n_valid) -> bool[T]`: red iff `round(100*(B[t]/B[t-1]-1), 4) <= RED_RSP_PCT` AND `share[t] <= RED_BREADTH_MAX` AND `n_valid[t] >= MIN_BREADTH_NAMES`.
- `nonred = classified & ~red`, where `classified = n_valid >= MIN_BREADTH_NAMES` and BENCH has both closes.
- `spy_red_days(spy_close)`: `round(100*(S[t]/S[t-1]-1), 4) <= SPY_RED_PCT`, with no breadth leg.
- Cache-universe check: the red/non-red day vector is **FROZEN** from the primary panel and never recomputed on a different universe.

### 3.5 Signal sets on day t (bars ≤ t only)
- `rvol(P)`: `V[:,t] / mean(V[:,t-VOL_BARS .. t-1])`. All VOL_BARS prior values must be finite and the mean > 0, else NaN. **Day t is never in the denominator.** On a gap-free frame this equals `ES._rvol(v, i, VOL_BARS)`.
- `close_pos(P)`: `(C-L)/(H-L)`. NaN when `H <= L`.
- `liquid = C >= PRICE_FLOOR & C*V >= DVOL_MIN`.
- `S1 = chg > 0 & liquid`.
- `S2 = S1 & rvol >= RVOL_MIN & close_pos >= CR_MIN`.
- `POOL (twins) = chg < 0 & liquid` (strictly red; unchanged is never a twin).
- `leader_at_t` (split only, the list's definition, includes t): `C[t] > mean(C[t-49..t])` AND `C[t]/max(H[max(0,t-251)..t]) - 1 >= -LEADER_NEAR_HIGH_PCT/100`.

### 3.6 Match features at t−1 (`features_prev(P, bench_close)`; nothing at index ≥ t)
- `r21 = C[t-1]/C[t-1-R_SHORT] - 1`
- `r63 = C[t-1]/C[t-1-R_MED] - 1`
- `off52 = C[t-1] / max(H[max(0,t-HIGH_BARS) .. t-1]) - 1`, requiring ≥ HIGH_MIN_BARS finite highs. `off52_bars` (the lookback actually used) is recorded.
- `above50 = C[t-1] > mean(C[t-MA50_BARS .. t-1])`, with all 50 finite (else NaN, and the row is dropped from matching).
- `ldv20 = ln(mean(C[k]*V[k], k = t-20 .. t-1))`, with all 20 finite and > 0.
- `vol20 = std(ddof=1) of ln(C[k]/C[k-1]), k = t-20 .. t-1`, with all 20 finite.
- `beta63` (rev 1: a MATCH_VAR, gated by balance): OLS slope of the name's simple daily returns on BENCH's over k = t−63 .. t−1, with ≥ BETA_MIN_PAIRS finite pairs. Otherwise NaN, and the row is `no_features`.
- Eligible t: `FIRST_T <= t <= T-1-h` for the horizon being scored. **AS_OF (t = T−1) is never a signal day.** A row with any NaN in MATCH_VARS/EXACT_VARS is `no_features` (counted, not matched).
- Implementation: pandas `rolling(...).shift(1)` on the T axis (`DataFrame(C.T)`), `min_periods` equal to the full window, except off52 (`min_periods=HIGH_MIN_BARS`).

### 3.7 Outcomes (per row, per h in HORIZONS, per entry e in ENTRIES)
- Exit day index `x`: the last `k` in `(t, t+h]` with finite `C[i,k]` (carry-forward through a halt). None → `no_outcome`.
- Entry O (**PRIMARY**, bought next morning): requires finite `O[i,t+1] > 0`. `ret = C[i,x]/O[i,t+1] - 1`, `bench = B_C[x]/B_O[t+1] - 1`.
- Entry C (check (e)): `ret = C[i,x]/C[i,t] - 1`, `bench = B_C[x]/B_C[t] - 1`.
- `excess = ret - bench`. `hit = excess > 0`.
- Descriptive, never a rule: `undercut = min(L[i,t+1..x]) < L[i,t]` (traded below the signal day's own low), and MAE `= min(L[i,t+1..x])/entry - 1` (p50, p90).
- A pair enters a (h, e) statistic only if BOTH members have the outcome, which keeps it 1:1.
- Data audit, never a filter: count rows by arm whose window t−R_MED..x holds a |close-to-close| ≥ BIG_MOVE_PCT. Any row whose window holds an `_is_scale_glitch` jump is excluded and counted (`glitch_rows`). (rev 1) `near_floor{sig, twin}`: the matched H_PRIMARY rows with `PRICE_FLOOR <= C_t < NEAR_FLOOR_BAND*PRICE_FLOOR`, by arm (L9).

### 3.8 Twin matching — `match_same_day(sig, pool, sd, *, caliper, match_vars) -> (pairs, unmatched)`
- `caliper` and `match_vars` are required keywords. The primary passes `CALIPER_SD` and `MATCH_VARS`. (f2) passes `CALIPER_SD_HOUSE`. S9 passes `MATCH_VARS_REV0`.
- Inputs: DataFrames with `id` (int, deterministic: index of (day, sym) sorted), `sym`, `day`, `above50`, and match_vars, all finite.
- `sd = pooled_sd(sig, pool, match_vars)`: per var, `sqrt((var_sig + var_pool)/2)`, ddof=1, over THIS run's rows. It is computed once, before any outcome.
- For each day ascending, and for each above50 value (exact): `Z = x/sd`; `D = Zs[:,None,:] - Zp[None,:,:]`. The pair is admissible iff `all(|D| <= caliper)` on EVERY covariate. `dist = sqrt(sum D^2)`.
- Candidates are ordered by `np.lexsort((pid, sid, dist))`. Greedy: take a pair if neither side is used. **Without replacement; same day only; no date widening; no RNG.**
- Returns `pairs[sid, pid, day, dist]` and the sorted unmatched sids.
- Matching runs on the days eligible for min(HORIZONS). Each statistic subsets pairs by its own h. A pair never splits.
- **(rev 1) The balance gate and matched_share are computed on the H_PRIMARY-eligible subset only** (pairs and signal rows with `t <= T-1-H_PRIMARY`). This subset is outcome-free: it is defined by the calendar index, not by any return. `matched_share = n_pairs / n_signal_rows_with_features` on that subset.
- Balance: house `smd(a, b)` (pooled SD, ddof=1) per var in the run's match_vars + above50, on those pairs. `balanced` = every |SMD| < BALANCE_SMD_MAX, and NaN fails. Diagnostic SMDs, NOT gated: day-t chg, rvol, close_pos, ln(close), plus beta63 in the S9 run.
- **(rev 1) Every re-match (f, f2, S3, S6, S7, S9, cache) carries its own `balanced` flag.** In (f) and (f2), an imbalanced re-match counts as a FAILED criterion in both verdict directions. For S3 it forces `not_red_specific` (3.12).

### 3.9 Clusters and CI (rev 1: fixed blocks, never chained)
- `blocks(t_idx, size) -> ndarray`: `t_idx // size` on the calendar index (house `AS:311-313`). Adjacent red days are NEVER merged across a block edge.
- `groupings(t_idx, h) -> dict`: `{"day": t_idx, "blk_h": t_idx // h, "blk_m": t_idx // BLOCK_SESSIONS}`. When `h == BLOCK_SESSIONS`, `blk_h` and `blk_m` coincide, and the CI and G are computed once.
- `lift_ci(vals, is_sig, is_twin, t_idx, h) -> dict`:
  - For each grouping g, `r_g = AS.boot_diff(vals, is_sig, is_twin, g, B=BOOT_B, seed=BOOT_SEED)`.
  - `G_g` = the number of distinct labels among rows in `is_sig | is_twin`.
  - A grouping with `G_g < MIN_CLUSTERS` or `r_g["reps"] < MIN_BOOT_REPS` is NULL.
  - `ci = AS.widest(*diff_cis)` only if NO grouping is NULL. Otherwise `ci = None`, with no fallback to the narrower groupings. The same rule gives `sig_ci` (from `a_ci`) and `twin_ci` (from `b_ci`).
  - Returned: `lift = r_day["diff"]` (the mean pair difference), `ci`, `sig_ci`, `twin_ci`, `G = {g: G_g}`, `G_min = min(G_g)`, `reps = {g: r_g["reps"]}`, and `mdl = MDL_Z*(ci.hi-ci.lo)/3.92` (null when `ci` is null).
- S3 (red vs non-red difference in lift): `vals = pair_diff`, `mask_a = red pairs`, `mask_b = non-red pairs`, the same three groupings over both sets' t_idx, and the same NULL rule.
- Design expectation (1.4, not a gate): at h10 the G values are day 78, `t // 10` 38, `t // 21` 21. `G_min = 21 ≥ MIN_CLUSTERS`.

### 3.10 Tests of the claim
**PRIMARY:** S2 on red days vs twins, `h = H_PRIMARY = 10`, **entry O (the next session's open)**, excess over RSP. The lift is the mean signal excess minus the mean twin excess over complete matched pairs, with the CI from 3.9.

Reported beside it, for every (h ∈ 5/10/21) × (entry O/C): n pairs, n red days, G per grouping, signal and twin mean excess with CIs, lift with CI, raw mean return per arm, median, `ES.trimmed_mean`, hit rate per arm, undercut rate per arm, MAE p50/p90, and MDL.

**STABILITY** (h10, entry O unless stated; they feed the verdict in BOTH directions):
- (c) lift in date halves H1/H2: H1 = the first floor(D/2) unique red days.
- (c2) lift with each `t // BLOCK_SESSIONS` block dropped in turn: per block, min, max, argmin, argmax.
- (d) lift one-per-symbol: each signal symbol's earliest complete pair only.
- (e) lift at entry C (the signal-day close), h10, same pairs.
- (f) lift on the cache universe: `ES.symbols_for("cache", FIRST_T + 2)` minus EXCLUDE, red days frozen, re-matched, SD recomputed, own balance flag. `ended = last day < AS_OF − ENDED_GRACE_DAYS`, with carry-forward exit (a terminal close). Also report the count of cache-only names and their signals.
- (f2) lift at `CALIPER_SD_HOUSE`, with its own balance flag.

**SECONDARY** (labelled; each with a CI or null; entry O, h10; none is a finding unless the primary is SIGNAL):
- S1 red vs twins ("is plain green enough?").
- S3 red vs non-red difference-in-lift (3.9). The non-red lift uses the same twin rule (red-closing names that day). **Rev 1: S3 feeds the `not_red_specific` tag (3.12). It never changes the status.**
- S4 leaders vs rest (pairs split on the signal's `leader_at_t`).
- S5 excluding event pops (signal day chg > EVENT_POP_PCT).
- S6 SPY-only red days (re-matched).
- S7 "does the volume add anything?": S2 vs twins drawn from `S1 & ~S2` the same day (same matcher).
- S8 dollar volume ≥ DVOL_APP (the app's $20M floor) subset.
- S9 (rev 1, redefined) the rev 0 5-covariate match (`MATCH_VARS_REV0`, no beta63). It shows how much the beta gap moved the lift. Its beta63 SMD is printed as a diagnostic.
- S10 strict 252: pairs with `off52_bars == HIGH_BARS`.
- S11 the unmatched signals' own mean excess vs RSP with CI. This is descriptive: it shows what the extremes the matcher could not twin did. It is not a comparison.

### 3.11 Runtime sanity (all go into the JSON; the first two are printed before anything else)
- **Repro (the list he saw):** if AS_OF ≥ REPRO_DAY, compute the S2 set on REPRO_DAY and compare it to `--expect <json>` (the 56-name list). Record `{rsp_pct, breadth, n_valid, is_red, n_expected, n_got, missing, extra, leaders, match}`. Expected: red = True, 56 names, 9 leaders, VOYG present. It is NOT a verdict gate. A mismatch is printed loudly and explained in the doc.
- **PIT check:** for PIT_CHECK_NAMES names drawn with `default_rng(PIT_SEED)` from those with S2 rows, rebuild a one-name panel from the frame truncated at `cal[t]` (and BENCH truncated the same way). Every feature at t (beta63 included) and every S1/S2/POOL flag must equal the full-panel value exactly (NaN == NaN). Any mismatch → status `invalid_pit`, exit 6.
- **Window start:** print the first eligible t and assert `== FIRST_T`. Print the first and last scored red day per h.
- **Design print (rev 1; `--stage match` and `all`, before any outcome):** matched_share, the gated SMDs, `balanced`, and G per grouping at H_PRIMARY, for the primary, (f2) and S3. §5's stop rule reads this print.
- **Anecdote (labelled "not a measurement"):** VOYG's REPRO_DAY row, and its past S2-on-red rows with h10 entry-O excess (n, values). No CI claim.

### 3.12 Verdict — `verdict(res) -> {"status", "tags", "failed", "rev"}` (mechanical; the printed status is its output)
```
invalid_snapshot        if not res.snapshot.ok
invalid_pit             if res.pit.mismatch > 0
no_signal [imbalanced]  if not res.balance.primary.balanced
                        (gated on the H_PRIMARY-eligible pairs; stats stops BEFORE any outcome is computed)

Gates common to both directions:
  (g) matched_share >= MIN_MATCHED_SHARE                 (H_PRIMARY-eligible subset)
  (k) primary ci is not null                             (every grouping has >= MIN_CLUSTERS clusters
                                                          and >= MIN_BOOT_REPS usable draws)
Primary = S2 red vs twins, h = H_PRIMARY, entry PRIMARY_ENTRY (next open).

signal    iff (g) and (k) and ALL of:
  (a)   primary ci.lo > 0
  (b)   primary sig_ci.lo > 0                            (the signal arm itself beats RSP)
  (c)   lift_H1 > 0 and lift_H2 > 0
  (c2)  min drop-one-block lift > 0
  (d)   one-per-symbol lift > 0
  (e)   entry-C h10 lift > 0
  (f)   cache-universe lift > 0 and that re-match balanced
  (f2)  CALIPER_SD_HOUSE lift > 0 and that re-match balanced

inverted  iff (g) and (k) and ALL of the mirrors:
  (a-)  primary ci.hi < 0
  (c-)  lift_H1 < 0 and lift_H2 < 0
  (c2-) max drop-one-block lift < 0
  (d-)  one-per-symbol lift < 0
  (e-)  entry-C h10 lift < 0
  (f-)  cache-universe lift < 0 and that re-match balanced
  (f2-) CALIPER_SD_HOUSE lift < 0 and that re-match balanced
  ((b) has no mirror: INVERTED is a claim about the twin comparison; the arm-vs-RSP CI is reported.)

else no_signal, tags (additive):
  relative_only    (a and not b)
  absolute_only    (b and not a)
  fragile          (a and b and any of c, c2, d, e, f, f2 fails)
  inverted_fragile (a- and any of c-, c2-, d-, e-, f-, f2- fails)
  undermatched     (not g)
  few_clusters     (not k)

status signal or inverted also gets:
  not_red_specific unless S3 (red lift minus non-red lift, entry O, h10) points the same way:
  signal needs S3 ci.lo > 0; inverted needs S3 ci.hi < 0.
  A null S3 CI or an imbalanced S3 re-match sets the tag.
```
`failed` lists every criterion that did not hold, in both directions. The brief's rule (SIGNAL iff CI lo > 0 at h10; INVERTED iff hi < 0) is (a)/(a-). It is applied to the widest non-null CI at the next-open entry.

### 3.13 Headline (built from constants and the JSON; test-locked wording)
"Green on a red day (up on the day, ≥ $PRICE_FLOOR, ≥ $DVOL_MIN traded, volume ≥ RVOL_MIN× its VOL_BARS-day average, closed in the upper half of the day's range), bought at the next open and held H_PRIMARY sessions: {lift:+.2f}pp vs same-day red twins [{lo}, {hi}], {sig:+.2f}pp vs RSP [{lo}, {hi}] — {STATUS}{TAGS}. Measured from the signal-day close instead: {lift_C:+.2f}pp. n = {pairs} pairs on {days} red days ({G_min} independent periods), {first} → {last}."
- A null CI prints as `[n/a: {G_min} periods]`.
- `{TAGS}` = `" (" + "; ".join(TAG_TEXT[t] for t in tags) + ")"`, or empty. `TAG_TEXT`:
  - relative_only: "beats the twins, not RSP"
  - absolute_only: "beats RSP, not the twins"
  - fragile: "fails a stability check"
  - inverted_fragile: "the shortfall fails a stability check"
  - undermatched: "too few signals found a twin"
  - few_clusters: "too few independent periods for an interval"
  - not_red_specific: "not specific to red days"
  - imbalanced: "the twins did not match the signals"
- Banned words (the test fails on them): "bounce", "fake", "Minervini", "TLSW", "TTLAC", and any book page cite.

### 3.14 JSON keys (`green_on_red_measured.json`)
`study, prereg_rev, run_date, as_of, git_head, script_sha256, universe_sha256, prereg{every 3.2 constant + reused values incl. MIN_CLUSTERS + VERDICT_RULE_TEXT + TAG_TEXT}, snapshot{as_of, ok, names_moved, bars_differ}, sample{names, etf_excluded, dup_day_keys, off_calendar_bars, sessions, first_t, red_days{h: n}, red_day_list, clusters{h: {day, blk_h, blk_m, G_min}}, nonred_days, spy_red_days, signals{S1,S2 by day type}, pool_rows, no_features, glitch_rows, no_outcome{arm: n}}, repro, pit, design{primary, house_caliper, S3_nonred: {matched_share, smd_*, balanced, G}}, balance{primary, S1, S3_nonred, S6, S7, S9, cache, house_caliper: {smd_*, diag_*, balanced, matched_share, n_pairs, n_unmatched, sd, caliper, match_vars}}, primary{"h10_O" (THE primary), "h5_O", "h21_O", "h5_C", "h10_C", "h21_C"}, stability{date_h1, date_h2, drop_one_block{per, min, max, argmin, argmax}, one_per_symbol, entry_C, cache_all{lift, balanced}, house_caliper{lift, balanced}}, secondary{S1..S11}, data_audit{big_move, glitch_rows, near_floor{sig, twin}}, anecdote, memory{peak_rss_mb, wall_s}, verdict{status, tags, failed, rev}, headline`. NaN is written as null (`ES._clean`).

### 3.15 CLI and stages
`python green_on_red_study.py --stage {features|match|all} --out DIR --git-head SHA [--expect PATH] [--no-cache-check] [--force-window]`
- `features`: snapshot, panel, red days, signals, repro, PIT, window start. **No outcome is computed.**
- `match`: + every matching run + balance + the design print (3.11). **No outcome is computed.** This is the smoke run and is NOT quotable.
- `all`: + outcomes, CIs, stability, secondaries, verdict, snapshot verify, JSON.
- Exit codes: 0 ok; 4 snapshot moved; 5 refusal window; 6 PIT mismatch.
- `run_study(frames, bench_df, spy_df, as_of, *, cache_frames=None, expect=None, stage="all") -> dict` is PURE given frames. `main()` only does I/O.

---------------------------------------------------------------------------------------------------
## 4. Work packages (disjoint files)

### WP-A — script + tests (one executor; the tests need the exact API)
**Files owned:**
- `backend/scripts/green_on_red_study.py` (new)
- `backend/tests/test_green_on_red_study_2026_09_28.py` (new)

**Steps:**
1. Write the module docstring in the house style: THE ASK verbatim, a PRE-REGISTRATION summary (rev 1), READ-ONLY, the RUN recipe (section 5), and "RESULTS: NOT RUN".
2. Implement 3.2–3.15 exactly, with the functions named in 3.3–3.12.
3. Import only origin/main modules: `sepa.prices`, `sepa.universe`, `sepa.breakout_audit`, `supply_demand.demand_reentry`, `supply_demand.momentum_burst`, `supply_demand.stock_supply_demand`, `trading.safety_floor`, `rotation.tracker`, `scripts.turning_bullish_amd_study`, `scripts.explosive_study`, and (rev 1) `scripts.promo_tag_study` (for `MIN_CLUSTERS` only). Nothing from the raid-low branch.

**Tests** (no Mongo, no network; every data read is monkeypatched or synthetic; (N) = negative):
- 01 (N) a red close (`C_t < C_{t-1}`) is never in S1/S2. An unchanged close is never green and never a twin. A green close is never a twin.
- 02 (N) RVOL excludes day t: multiplying `V_t` by 100 leaves the denominator unchanged; changing `V_{t-51}` leaves RVOL unchanged; changing `V_{t-1}` changes it. Equals `ES._rvol` on a gap-free frame. A 49-bar history gives NaN.
- 03 (N) no bar after t: mutate every bar > t → all features, flags and the red-day flag at t are unchanged. Mutate bar t (name AND BENCH) → MATCH_VARS (beta63 included)/above50 at t are unchanged. Truncated-panel equality (`features_prev` on `cal[:t+1]`).
- 04 (N) today's signals are excluded: a planted S2 on the last calendar index enters no outcome statistic for any h. A signal at T−1−h is scored at h and not at the next longer horizon.
- 05 (N) a non-red day never counts as red: RSP −0.49% with breadth 0.10 → not red; RSP −0.60% with breadth 0.36 → not red; n_valid < MIN_BREADTH_NAMES → unclassified (neither red nor non-red). Boundary: RSP exactly −0.5000% and breadth exactly 0.35 → red.
- 06 (N) breadth uses the same universe: an EXCLUDE (ETF) name never counts. A name missing `cal[t-1]` is not in the denominator. A scale-glitch jump is not counted. Breadth is computed from the same panel object that yields signals (identity check). The cache-check red vector equals the primary one (frozen).
- 07 prior close = prior SESSION: a name with a gap (no bar on `cal[t-1]`) has NaN chg on t even though its previous bar is green-relative.
- 08 close_pos: `H == L` → never S2. `cr == 0.5` inclusive → S2. `rvol == 1.5` inclusive. `C == 2.00` inclusive. `C*V == 10M` inclusive.
- 09 leader_at_t matches the list's formula (includes t) on a hand frame; off52 with fewer than 252 bars uses what exists, with the HIGH_MIN_BARS floor (62 → NaN).
- 10 matcher: same day only (N: a perfect twin on another day is never used); exact above50 (N); per-covariate caliper box on EVERY var incl. beta63 (N: small Euclidean distance but beta63 alone beyond the caliper → rejected); without replacement (N: two identical signals and one pool row → one pair, one unmatched); closest pair wins, not id order; deterministic ties by (dist, sid, pid); no RNG (source guard); `caliper`/`match_vars` are required keywords (N: calling without them raises).
- 11 pooled_sd, smd, balance gate (NaN fails; |SMD| = 0.1 fails; an SMD of 0.165 on beta63 fails the primary gate (N)).
- 12 (rev 1) blocks: `t // size` is fixed. At size 10, t = 19 and t = 20 are different blocks (N: never chained). A 30-session run of consecutive red days spans ≥ 3 blocks (N: never one episode). G counts distinct labels among the pair rows only. At h == BLOCK_SESSIONS the two block groupings coincide. Date halves use unique days.
- 13 (rev 1) bootstrap: clustered (duplicating every row of one cluster does not shrink the CI the way iid would, house test 25b pattern). Widest of the three groupings. (N) one grouping with G = MIN_CLUSTERS − 1 → the whole CI is null. It is NOT the other groupings' CI, and NOT `AS.widest` over the non-null ones. (N) `reps < MIN_BOOT_REPS` → null. G = MIN_CLUSTERS exactly → non-null.
- 14 (rev 1) verdict, every branch and tag:
  - imbalanced: stats computes no outcome (monkeypatch an outcome function to raise).
  - signal, inverted.
  - relative_only, absolute_only.
  - fragile, one per criterion c/c2/d/e/f/f2: flip each one alone → not signal (N).
  - inverted_fragile, one per mirrored criterion: a CI with hi < 0 and each mirror flipped alone → `no_signal` + `inverted_fragile`, never `inverted` (N).
  - An imbalanced (f) or (f2) re-match with a lift of the right sign fails the criterion, for signal AND for inverted (N).
  - undermatched: share 0.79 with ci.lo > 0 → not signal (N), and share 0.79 with ci.hi < 0 → not inverted (N).
  - few_clusters: G_min = MIN_CLUSTERS − 1 → CI null → neither signal nor inverted (N).
  - not_red_specific: set when S3 spans 0, is null, or its re-match is imbalanced. Not set when signal has S3 lo > 0, or inverted has S3 hi < 0. The tag never changes the status (N).
  - invalid_snapshot, invalid_pit.
- 15 outcomes: carry-forward exit through a halt; no bar in (t, t+h] → no_outcome; entry O with missing `O[t+1]` → no_outcome; the bench uses the same entry and exit dates and the same entry type (RSP's open for entry O); a pair with one missing member is dropped from that (h, e).
- 16 refusal window: Mon 10:00 ET True; Mon 17:30 False; Sat 12:00 False; `--force-window` bypasses.
- 17 constants imported by name, identity-pinned (`MIN_CLUSTERS is PT.MIN_CLUSTERS`, `HORIZONS is AS.HORIZONS`, …), plus a regex guard that none is retyped. `H_PRIMARY in HORIZONS`. `FIRST_T == R_MED + 1`. `PRIMARY_ENTRY == "O"`. `"beta63" in MATCH_VARS`. `MATCH_VARS_REV0 == MATCH_VARS[:5]`. Module globals are read at call time: monkeypatching `MIN_BREADTH_NAMES` changes `red_days` output (N: a default-arg binding would not).
- 18 read-only guard (house test_29 pattern): no `load_prices`, `_fetch`, `_mongo_put`, `insert`, `update_`, `replace_one`, `delete`, `bulk_write`, `create_index`, `bulk_snapshot`, `patch_latest_closes`.
- 19 JSON NaN → null; the headline is built from constants and TAG_TEXT, and contains no banned word (N). It says "next open". A null CI prints `n/a`.
- 20 (rev 1) end-to-end synthetic (`run_study`). Setup: `MIN_BREADTH_NAMES` and `MIN_CLUSTERS` monkeypatched on the study module; ~60 names × ~300 bars; planted red days in ≥ 10 distinct 21-session blocks.
  - A planted +3% drift from the next open → `signal`.
  - Pure noise → NOT `signal` (N).
  - A planted −3% drift (plus the mirrored checks) → `inverted`.
  - (N) A planted gain confined to the signal-day close → next open gap (flat afterwards) gives a positive entry-C lift but is NOT `signal`: the primary is entry O.
  - (N) The same synthetic with the REAL constants → unclassified days / `few_clusters`, never `signal`.
  - The first eligible t == FIRST_T. The repro block works with an `--expect` list.
- 21 cap_as_of by day key with mixed 00:00/04:00 stamps (N: a 00:00 bar on AS_OF+1 is dropped); duplicate day keys keep the last.
- 22 (rev 1) beta63: equals a hand OLS on a 63-bar frame. With fewer than BETA_MIN_PAIRS finite pairs → NaN → `no_features` (N). Mutating BENCH's close at t leaves beta63 at t unchanged; mutating it at t−1 changes it.
- 23 (rev 1) the balance gate and matched_share use the H_PRIMARY-eligible subset. A planted imbalance confined to pairs with `t > T-1-H_PRIMARY` does not trip the gate (N). The same imbalance inside the subset does.
- 24 (rev 1) near_floor audit: counts by arm on the band `[PRICE_FLOOR, NEAR_FLOOR_BAND*PRICE_FLOOR)`. It never filters (N: the pair set is identical with and without the audit).

**Docs:** none (WP-B owns the doc).

**Verification:** run the full backend suite with the cache purge (section 5). Mutation-check these lines and assert each mutation applied:
- `>` → `>=` in green
- RVOL window includes t
- `shift(1)` removed on r21
- `<=` → `<` in the red rule
- (rev 1) the null-CI rule replaced by `AS.widest` over the non-null groupings (test 13 must fail)
- (rev 1) `PRIMARY_ENTRY = "C"` (tests 17 and 20 must fail)
- (rev 1) the inverted branch reduced to `ci.hi < 0` (test 14 must fail)

Purge `~/Library/Caches/com.apple.python` between mutations.

### WP-B — doc (parallel with WP-A)
**Files owned:** `docs/research/green_on_red_2026_09_28.md` (new).

**Steps:**
1. Banner: "PRE-REGISTERED (rev 1), NOT RUN — research only (Rule #10); nothing changes in the app".
2. §1 The ask, verbatim, plus the testable hypothesis (spec §0).
3. §2 Files (spec 3.1).
4. §3 PRE-REGISTRATION: copy spec 3.2–3.13 verbatim, and "frozen at commit <sha>, rev 1". Include the §8 changelog as "What the pre-registration review changed".
5. §4 Limitations (spec §6, items L1–L9).
6. §5 "Results — NOT RUN" placeholder.
7. §6 HIS CALL (spec §7).

**Wording:** "reversal"/"hold", never "bounce"; never "fake"; no book cites.

**Tests:** none (the measured-doc pin is added by the main session after the run).

### MAIN SESSION (sequential, after WP-A and WP-B)
1. Review. Run the suites. Commit the pre-registration (script + tests + doc) = `PREREG_SHA` (`export COMPOSE_PROJECT_NAME=cheetah-market-app`; never stage the `.venv`/`node_modules`/`.env` symlinks).
2. Smoke: `--stage match` (not quotable). Apply the §5 stop rule to its design print.
3. Full run with `--git-head PREREG_SHA`.
4. Copy out the JSON to `backend/scripts/green_on_red_measured.json`.
5. Append the measured pins to the test file (house tests 1013/1024 pattern):
   - `git_head == PREREG_SHA`
   - `script_sha256` matches
   - `prereg_rev == 1`
   - status and tags == `verdict()` re-run on the JSON
   - the doc's Results section names that status and every tag, and no stronger word
   - repro.match recorded
6. Fill doc §5 from the JSON only. Write the memory note.
7. No `newFeatures.ts` entry, no `rules_info` line, no deploy (nothing user-facing).

---------------------------------------------------------------------------------------------------
## 5. Verification plan

**His surface is the list he saw** (the 56 names, VOYG in it), plus the answer in chat. The study proves it measures THAT list via the repro block. On 2026-09-28 it must return:
- red = True, breadth ≈ 0.297
- 56 names = the scratchpad list, 9 leaders, VOYG present

Any diff is explained before a number is quoted.

**Stop rule (rev 1, pre-outcome).** If the `--stage match` design print shows any of the following, the main session STOPS before `--stage all` and asks Ajay:
- the primary `balanced` is False
- matched_share < MIN_MATCHED_SHARE
- `G_min` at H_PRIMARY < MIN_CLUSTERS

These are design facts, not outcomes. The fix for each is his call (§7). The expected values are in 1.4: balanced, 0.818, 21.

**Run** (after 17:30 ET or before 09:00 ET; never RTH):
```
cd /Users/ajay/clinet-test/wt-gord
docker cp backend/scripts/green_on_red_study.py cheetah-market-app-api-1:/tmp/green_on_red_study.py
docker cp /private/tmp/claude-501/-Users-ajay-clinet-test/656642d4-5050-4aec-a1a8-e7114785de7b/scratchpad/gor_dem_2026_09_28.json cheetah-market-app-api-1:/tmp/gor_dem_2026_09_28.json
docker exec -d -w /app -e PYTHONPATH=/app cheetah-market-app-api-1 sh -c 'mkdir -p /tmp/gor_out && python -u /tmp/green_on_red_study.py --stage all --out /tmp/gor_out --git-head PREREG_SHA --expect /tmp/gor_dem_2026_09_28.json > /tmp/gor_out.log 2>&1'
docker cp cheetah-market-app-api-1:/tmp/gor_out/green_on_red_measured.json backend/scripts/green_on_red_measured.json
```
- Wait with an until-loop no faster than once a minute.
- Expected wall time: a few minutes; peak < ~0.6 GB (logged in `memory`).

**Suites:**
- Backend: `cd backend && rm -rf ~/Library/Caches/com.apple.python; /usr/bin/find . -name __pycache__ -type d -prune -exec rm -rf {} + ; .venv/bin/python -m pytest tests/ -q --ignore=tests/test_portfolio_eq_risk.py --ignore=tests/test_accumulation.py -p no:cacheprovider`
- New file alone first.
- The hermetic-suite offender list must stay EMPTY: the new tests touch no network and no Mongo. `scripts.promo_tag_study` is already imported hermetically by `tests/test_promo_tag_study.py:25`.

**Pins that break:** none expected. All four files are new, and no existing module is edited.

**Quoting rule:** numbers go to Ajay only from the committed JSON, with the CI (or "n/a: G periods"), beside the stop-proxy (undercut rate) and the hit rate, and with every tag in plain words. Never a smoke number.

---------------------------------------------------------------------------------------------------
## 6. Risks, traps, limitations

**Traps:**
- **T1 — Mixed 00:00/04:00 stamps:** use day keys only (`cap_as_of`). A timestamp compare silently drops or keeps AS_OF.
- **T2 — Intraday patches:** `crontab:407` hourly, 16:00, and the 16:30 fast-scan patch. Hence the refusal window and the snapshot digest verify. `split_today_partial` keeps today's bar only after 16:00.
- **T3 — `_drop_phantom_tail`:** can remove a genuine unchanged AS_OF bar. The only effect is AS_OF-day breadth (a repro, not scored) and carry-forward exits. The JSON counts names whose last day ≠ AS_OF.
- **T4 — dropna-before-rolling (Hot Pullback off-by-49):** the panel keeps NaN, `min_periods` is set to the full window, and the first eligible t is asserted.
- **T5 — Unadjusted splits / decimal shifts:** `_is_scale_glitch` (5x) catches only large ones. A 2:1 split would read as −50%. The data audit counts |move| ≥ 40% by arm, and the doc flags it if it exceeds 1% of rows.
- **T6 — Overlapping windows** (April 2025: 5 red days in 6 sessions). Rev 1 uses fixed blocks. Two red days either side of a block edge still share their windows. This is the house trade-off (`AS:311-313`). The 21-session grouping halves the edge share, and the day grouping is kept.
- **T7 — Short-term reversal / bid-ask at the close:** rev 1 prices the primary at the next open. The at-close number is (e), a same-sign check, and appears in the headline.
- **T8 — The container runs origin/main:** the script must import main-only modules. The raid-low matcher is semantics-copied, not imported. When that branch merges, consolidate `match_same_day`/`match_nn` into one helper (a follow-up, not this build).
- **T9 — macOS bytecode cache** defeats mutation tests: purge `~/Library/Caches/com.apple.python` and assert each mutation applied.
- **T10 — Scope lock:** the main session's other relayed asks (key levels, GEX, Auto-Pilot, tape) are out of scope.
- **T11 — Wording:** "reversal"/"hold"; never "bounce", never "fake"; no book cites. The headline and TAG_TEXT are test-locked.
- **T12 — Twelve secondaries = forking paths.** Only the primary drives the status. S3 only adds a tag. A secondary CI that excludes zero is not a finding unless the primary is SIGNAL.
- **T13 — Never quote the smoke run.** Never hand-edit the status.
- **T14 (rev 1) — G sits one above the floor at h10** (21 vs MIN_CLUSTERS 20). A few more `no_outcome` or glitch exclusions in the real script could drop a block. The run then reads `few_clusters`, and the §5 stop rule catches it BEFORE outcomes.
- **T15 (rev 1) — Monkeypatchable globals:** a function that binds MIN_CLUSTERS/MIN_BREADTH_NAMES as a default argument silently ignores the test's patch. Test 17 guards it.

**Limitations (for the doc):**
- **L1 — Survivorship and membership look-ahead:** today's `full` list omits names delisted, acquired or dropped before 2026-09-28. It also includes names that EARNED membership by rising into the 2026 Russell reconstitution. Both arms are lifted. The bias on the LIFT is unknown in sign: it depends on whether green-on-red names and red twins left the universe at different rates. It is measured by (f) on the cache universe, which is itself partial (only names the app ever cached since ~2024-09).
- **L2 — Depth (rev 1 numbers):** 500 cached bars → 78 red days (h10) from 2024-12-31 to 2026-09-14. That is 21 independent 21-session periods (38 ten-session blocks), and the largest period holds 12% of the pairs. It is one regime, including the April-2025 tariff crash. The MDL is reported. A null here is "not detectable at this n", not "proven zero".
- **L3 — No news or earnings archive:** event days (earnings, M&A) are inside S2. S5 cuts only > +20% pops.
- **L4 — The red-day thresholds** (−0.5% RSP, 35% breadth) come from the brief, not from Ajay. SPY-only is S6.
- **L5 — The ETF exclusion** differs slightly from the main session's count (788 vs 789 green). The S2 count is unchanged (56).
- **L6 — Volume mixes** fractional aggregate bars with rounded snapshot bars. This matters only for the AS_OF repro.
- **L7 — ATT on the matchable region (rev 1):** with beta63 in the match, about 18% of S2 signals (the extremes) have no twin (design share 0.818). S11 describes them without a comparison.
- **L8 — The study is not a trading rule:** no stop or size is implied. The undercut rate is descriptive.
- **L9 (rev 1) — Split adjustment leaks the future into the $2 floor:** the cache holds split-ADJUSTED history. A name that later did a reverse split shows adjusted closes ≥ $2 on days it really traded below $2. Such future decliners can enter both arms. This is argued, not measured: the cache has no unadjusted price and no split archive. `data_audit.near_floor` counts the matched rows in `[$2, $4)` by arm (design: 41 signals, 54 twins of 4,434). That band is a proxy, not a bound, because a 1:10 reverse split lifts a $0.50 print to $5.

---------------------------------------------------------------------------------------------------
## 7. HIS CALL (the run proceeds on the defaults shown unless he overrides BEFORE the full run)

1. **What "bearish day" means:**
   - Default: RSP ≤ −0.5% AND ≤ 35% of names green (the brief's thresholds, not his).
   - Today qualifies (−0.65%, 29.7%).
   - SPY-only is reported as S6.
2. **What "high demand" means:**
   - Default: bought at the next open, beats RSP AND beats same-day red twins over the next 10 sessions (h5 and h21 are reported too).
   - If he means "keeps going up in absolute terms", that is criterion (b) plus the raw return columns.
3. **Verdict strictness:**
   - Default: the house rule (3.12), symmetric in rev 1, and stricter than the brief's single-CI rule.
   - The brief's rule is (a)/(a-) and is printed.
   - Loosening to CI-only is his call only.
4. **Liquidity floor:**
   - Default: $10M (the list he saw).
   - The app's own `MIN_DOLLAR_VOL` of $20M is reported as S8.
   - Which one would define any future list is his call.
5. **If SIGNAL:** any chip, board, tab, alert or lane built on it is his call, through the Rule #10 paper-variant path. **If NO_SIGNAL or INVERTED:** nothing ships, and the 56-name list stays a watchlist answer, not a demand claim. An INVERTED result changes no board by itself.
6. **VOYG:** it is on his list, but it is below its 50-day and 36.7% off its high (not a leader). Whether "leaders only" should be the list he watches is his call after S4.
7. **(rev 1) Cluster floor:**
   - Default: `MIN_CLUSTERS` = 20, the house study convention `PT.MIN_CLUSTERS`. Its own comment calls it his to move.
   - The design gives G = 21 at h10, so it passes by one (T14).
   - Below the floor, the CI is n/a and the status is `no_signal [few_clusters]`. SIGNAL and INVERTED both need the floor.
8. **(rev 1) Matched-share floor lowered from 0.85 to 0.80:**
   - This follows from adding beta63 to the match, which moved the design share to 0.818.
   - The floor rule itself is unchanged: design share, rounded down to the 0.05 grid.
   - If he keeps 0.85, the run is `undermatched` by construction and can return only `no_signal`.
9. **(rev 1) Entry price:**
   - Default: the next session's open, the first price available after a list built at the close.
   - The at-close number is reported, shown in the headline, and must agree in sign.
   - If he would buy at the close (MOC off a 15:55 read), he should say so before the run.
10. **(rev 1) What "inverted" means:**
    - It now needs the mirrored stability checks.
    - A lone negative CI prints `no_signal [inverted_fragile]`.

---------------------------------------------------------------------------------------------------
## 8. Rev 1 changelog (critic, 2026-09-28 22:57 ET; applied 23:05 ET; frozen)

1. **HIGH, chained episodes → FIXED.** `episodes()` is removed. CIs use FIXED blocks `t // h` and `t // BLOCK_SESSIONS` (house `AS:311-313`) plus the red day, widest of the three (3.9). G per grouping and `G_min` go into the JSON. A CI is NULL below `MIN_CLUSTERS` (`PT.MIN_CLUSTERS` = 20) or below 100 draws. There is no silent fallback: h21 now has G 20 (was one episode), and any grouping under the floor prints n/a. SIGNAL and INVERTED both need `G_min ≥ MIN_CLUSTERS`, as default (k), and the floor is HIS CALL §7-7. Design G at h10 is 38 / 21 (was 10 episodes). The largest block holds 12.2% (was 77% in three episodes). Drop-one (c2) now drops one 21-session block at a time. L2 is rewritten.
2. **HIGH, lopsided verdict → FIXED.** INVERTED needs (g), (k) and the mirrors c-, c2-, d-, e-, f-, f2-. Otherwise the result is `no_signal [inverted_fragile]` (3.12). (b) has no mirror, and the reason is stated in 3.12. Test 14 covers each mirror alone.
3. **MEDIUM, beta unbalanced → FIXED by matching.** beta63 is in MATCH_VARS and gated by balance. The design SMD is −0.022 (was −0.165), and the max gated SMD is 0.067. S9 is redefined as the rev 0 5-covariate match. Gating beta63 without matching it was REJECTED, because the run would be `imbalanced` by construction. Consequence: the design share falls to 0.818, so MIN_MATCHED_SHARE moves 0.85 → 0.80 by the unchanged floor rule. This is flagged HIS CALL §7-8. L7 is updated (≈18% unmatched).
4. **MEDIUM, red-day specificity → FIXED.** A `not_red_specific` tag is added to signal/inverted unless S3 points the same way with a non-null CI and a balanced re-match (3.12). It is in the headline as "not specific to red days". The status is unchanged, per the critic's fix.
5. **MEDIUM, untradeable entry → FIXED (option 1 of 2).** The PRIMARY is now entry O, the next session's open (house precedent `PT.PRIMARY` "open"). Entry C becomes criterion (e)/(e-), a same-sign check, and is printed in the headline. Option 2 (keep C primary and add an entry-O CI) was REJECTED: the headline number would still be one he cannot trade. Flagged HIS CALL §7-9. The design has entry O present for both members in 99.98% of pairs.
6. **LOW, split adjustment and the $2 floor → FIXED as a disclosure.** L9 is added. `data_audit.near_floor{sig, twin}` is on the band `[PRICE_FLOOR, NEAR_FLOOR_BAND×PRICE_FLOOR)`, never a filter. Design: 41 / 54 of 4,434. L9 states that the band is a proxy, not a bound.
7. **LOW, ambiguous inputs → FIXED.** Balance and matched_share are gated on the H_PRIMARY-eligible subset (3.8, test 23). An imbalanced (f)/(f2) re-match counts as FAILED in both directions (3.12, test 14). An imbalanced S3 re-match sets `not_red_specific`.
- **Not changed** (the critic checked these and found no defect): features at t−1, RVOL excluding t, same-day twin separation, twins later becoming S2 (outcome, not leakage), the S2 repro filter (CASY 0.5004 passes), the single primary test, and the red-day thresholds fixed before any outcome.
- **Also rev 1** (consequences, not findings):
  - Every study constant is read as a module global at call time (test 17).
  - Test 20 is redesigned, because its 40-name synthetic could never classify a day under MIN_BREADTH_NAMES = 1000.
  - Added: the §5 pre-outcome stop rule; three mutation checks; tests 22–24.
