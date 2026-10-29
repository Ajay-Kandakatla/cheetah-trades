# Strategy lab T01 C5 short-term reversal — PRE-REGISTRATION (2026-10-29)

**Status: PRE-REGISTERED — NOT RUN.** This file is committed BEFORE any outcome run. The commit hash
goes into the run as `--prereg-commit <hash>` and into the artefact (`stats.json` `prereg_commit`,
`prereg_sha256`). Any change to a rule below after that commit needs a new prereg file and a new
commit; a changed prereg is a new trial (`ledger_conflict` refuses the run, rc 2, before any bar is read).

Script: `backend/scripts/strategy_lab_2026_10_29.py` · tests: `backend/tests/test_strategy_lab_2026_10_29.py`,
`backend/tests/test_strategy_lab_repair_2026_10_29.py` · study doc (re-run recipe):
`docs/studies/strategy_lab_2026_10_29.md` · artefacts (never in the repo): `$S/out/c5_reversal/`
(`trades.json`, `daily.csv`, `stats.json`, `report.md`, `connector_payloads.json`, `run.log`) · machine
ledger: `/Users/ajay/clinet-test/eod-audits/research/strategy_lab_ledger.json` (mounted as
`/research/strategy_lab_ledger.json`). Nothing here is served: no lane, gate, board or constant reads it.

## The asks (Ajay 2026-10-29, verbatim)

> "Look in to strategies yourself like ema based and Quant based reliable ones and also research baked in to this task but try and improve the strategy until you are postive in results"

> "Also please a trading skil in to the mix I heard Claude now has a trading skill"

"Improve until positive" is NOT met by tuning C5 on the window this file seals: that is the data mining
the DSR trial count exists to penalize. Successor variants run only on sessions after 2026-10-29 (or on a
longer history, HIS CALL #1), each one a new counted trial.

The "trading skill": no Anthropic skill named "trading" is installed (checked 2026-10-29). The closest
match is the attached third-party quant connector (`workflow_run_sharpe_stats`, `workflow_run_dsr`,
`workflow_run_portfolio_tearsheet`). It is an independent cross-check of the in-script PSR / DSR only;
the in-script formula is the gate of record. Sending it the unlabeled OOS arrays is HIS CALL #8.

**The prior is null.** High Beta down-day Y_3 no_signal +0.16pp [-0.45, +0.82]; green-on-red no_signal
-0.30pp [-0.76, +0.15]; Hot Pullback null; Auto-Pilot: no lane net positive since 07-13. The literature figure for weekly
reversal is 30 to 50 bps a week net, LONG-SHORT, large caps; this trial is long only.

## Trial ledger (N is written here before the run; it never resets)

| trial | candidate | status at this commit | counts in N |
|---|---|---|---|
| T01 | C5 short-term reversal (this file) | registered, 0 OOS reads | yes |

**N = 1 (T01).** C1–C4 were REFUSED and add no trial:

| candidate | refusal (script exit 3, before any read; no ledger entry) |
|---|---|
| C1 all-time-high breakout, 10 x ATR(42) stop | rolling 2-year price cache: needs >= 10 years of daily bars back to each listing (point-in-time ATH) |
| C2 12-1 momentum, top decile | rolling 2-year price cache: needs >= 10 years of daily bars (>= 30 OOS rebalances) |
| C3 earnings-announcement-return drift | no announcement-date history: needs a historical BMO/AMC-stamped announcement-date series (only each name's latest Yahoo `last_report` is kept) |
| C4 SPY above its 10-month SMA, else T-bills | rolling 2-year price cache: needs >= 25 years of SPY daily bars |

A refused candidate reads no bar and burns no DSR trial. With N = 1, `dsr_sr0` returns 0 and DSR equals
PSR(0) by construction: gate C does no deflating at N = 1. A and B carry the test (design risk 3).

## Frozen values

| parameter | value | source |
|---|---|---|
| as_of | **2026-10-29** (a date) | design 3.4 |
| oos_from | **2026-03-20** (a date; = the last-third rule date) | design 3.4; `OOS_NUM, OOS_DEN = 1, 3` |
| universe | top 500 by median close x volume over the last 50 own bars | `C5_UNIVERSE_TOP_N = 500`, `C5_RANK_BARS = 50` |
| liquidity floor | `adr.liquidity_check` defaults: mean 50-bar dollar volume >= $20M | `LIQ_MIN_DV`, `LIQ_PERIOD` by `inspect.signature` |
| signal | bottom decile of the 5-session return at close t | `C5_R_LOOKBACK = 5`, `C5_BINS = 10` |
| entry / exit | open t+1 / open t+6 | `C5_HOLD = 5`, `SIGNAL_OFFSET = 0` |
| stop | none; long only | |
| cost per side | 15 bps (tier 1); 30 bps (tier 2, unreachable) | `COST_TIER1_BPS + SLIPPAGE_BPS` |
| position cap | 1% of 20-day median $ volume (capacity only) | `CAP_PCT_OF_MDV = 1.0`, `CAP_MDV_BARS = 20` |
| bootstrap | 10,000 draws, whole entry weeks, 95% percentile CI | `BOOT_DRAWS`, `RS.CI_PCT` |
| placebo | 1,000 sets, beat share >= 0.95 | `PLACEBO_SETS`, `PLACEBO_BEAT_SHARE` |
| placebo exclusion window | [t-10, t-1] (5 + 5) | `PLACEBO_EXCLUDE_BACK = C5_R_LOOKBACK + C5_HOLD` |
| gate C series | mean net per entry day | `GATE_C_SERIES = "per_entry_day"` |
| DSR pass | 0.95 | `DSR_PASS` |
| min clusters | 30 entry weeks, else TOO SMALL | `MIN_BUCKET_N` (`scripts.explosive_study`) |
| glitch cap | 5% flagged rows, above it no verdict word | `GLITCH_VERDICT_MAX_SHARE = 0.05`, `UNMEASURED_GLITCH = "UNMEASURED-glitch"` |
| seed | 20261029 | `SEED` |
| cash account | T+1 settlement, 6 sleeves (book and capacity only) | `SETTLE_SESSIONS = 1`, `BOOK_SLEEVES = 6` |

## Rule (design 3.3; parameters frozen)

Calendar `days` = SPY bar dates <= `as_of` (`RS.frame_days`). Panel = `RS.aligned(frame, days)`: arrays
(n_sym, n_days), NaN where no bar.

1. Own bars = slots with finite close AND finite volume. `dv = close * volume`.
2. Liquid(s,t) = >= `LIQ_PERIOD` own bars at or before t AND mean `dv` over the last `LIQ_PERIOD` own bars
   >= `LIQ_MIN_DV` (== `adr.liquidity_check(frame[<=t])["liquid"]`, test-pinned).
3. Rank(s,t): liquid, non-excluded, finite close at t; descending MEDIAN `dv` over the last `C5_RANK_BARS`
   own bars; ties by symbol. U_t = rank <= `C5_UNIVERSE_TOP_N`.
4. r5(s,t) = close[t]/close[t-5] - 1, only if the six closes t-5..t are finite AND no adjacent own-bar pair
   in [t-5, t] (close/prev close, open/prev close) is a `prices._is_scale_glitch`; else the name is not
   ranked that day (`skip_reason="scale_glitch_signal"` counted).
5. Selected(t) = names in U_t with finite r5 and `RS.quantile_bins(r5, C5_BINS, tiebreak=symbols) == 0`.
6. Signal sessions S = {t : FIRST_SIGNAL_IDX <= t <= n_days - 2 - C5_HOLD}. No row has a signal date after
   S[-1] (no current-day list).
7. Entry e = t+1 at open[s,e]; finite open > 0 and finite close at e, else `skip_reason="no_entry_bar"`.
8. Exit x_nom = t+1+C5_HOLD; x = first index >= x_nom with finite open > 0 -> `exit_reason "time"` if
   x == x_nom else `"late_exit"`; no bar at/after x_nom -> last finite close in [e, x_nom-1], `"data_end"`.
9. Hold hygiene (as amended by repair 3, 2026-10-29): a row with a `_is_scale_glitch` pair in [e, x] is
   KEPT in trades AND cohort and flagged (`glitch_hold`, counted under `scale_glitch_hold`). The verdict
   reads it under the glitch-row rule below.
10. Cost c per side = (COST_TIER1_BPS + SLIPPAGE_BPS)/1e4 if rank <= COST_TIER1_TOP_N else
    (COST_TIER2_BPS + SLIPPAGE_BPS)/1e4. net = exit*(1-c)/(entry*(1+c)) - 1; 100 -> 103 at 15 bps:
    0.0269146281.
11. MAE / MFE reported only; R multiple and stop-out rate = null (no stop).
12. Exclusions (logged per symbol AND per reason): `index_caret` (starts "^"); `static_etf`
    (`fallen_tab._static_etfs()`); `cached_etf` (`etf_info.cached_etf_set`); `levered_fund`
    (`levered_etf.load(ensure=False)` by_underlying items' `etf`); `crypto_pair` (endswith `CRYPTO_SUFFIX`
    "-USD"); `type_not_equity`: `ty = scanner.row_type(symbols.resolve(sym), types)`, if
    `ty == GC.SCAN_UNKNOWN_TYPE` then `ty = scanner.row_type(sym, types)`; excluded iff
    `ty not in GC.SCAN_INSTRUMENT_TYPES and ty != GC.SCAN_UNKNOWN_TYPE`. Unknown-type names are KEPT (dead
    names). Share classes with "-" are KEPT. `symbols.DELISTED` is NOT applied.
13. Duplicates: `canonical_dedupe` via `symbols.resolve`; keep the doc with the later last bar (SQ -> XYZ
    keeps XYZ).
14. Settlement (cash account, long only, no margin): proceeds of a sale at session k are usable from session
    k + SETTLE_SESSIONS. The book runs `BOOK_SLEEVES` = 6 sleeves; the cohort entering at open e uses sleeve
    e mod 6. `check_settlement` asserts every buy is funded only by sales with index <= e - SETTLE_SESSIONS.
    Affects `daily_book` and `capacity_usd` only.
15. `capacity_usd` = min over OOS trades of `BOOK_SLEEVES * m_c * CAP_PCT_OF_MDV/100 * mdv20_i`.

## Cost model

Shortlist cost model, fixed before any run: 10 bps per side for the top 1,000 by 50-day median dollar
volume, else 25 bps per side, plus 5 bps slippage per side, position capped at 1% of 20-day median dollar
volume. For C5 every rank is 500 or better, so every trade pays tier 1 = **15 bps per side**; tier 2
(30 bps) is unreachable and the run asserts `tier2_trades == 0`. The cap is used for capacity only. The
outcome run prints the break-even cost per side (`breakeven_cost_bps` = 1e4 * g/(2+g), g = mean gross).
Beside it, for HIS CALL #6: de Groot's ~75 bps a week for the 500 largest implies ~19 bps per side on a
long-short round trip.

## POSITIVE (verbatim from `2026-10-29_strategy_lab.md`, shortlist.md:23-27; all three required)

> A. **OOS expectancy.** Split by calendar time: the last third of the available sessions is the test set, sealed until design is frozen and the prereg doc is committed. On test-set trades only: mean net return per trade (after the cost model) > 0, and the 95% bootstrap CI excludes 0. The bootstrap resamples **whole entry weeks** (clustered; trades opened the same week are not independent), 10,000 draws, percentile CI. Report beside it: win rate, stop-out rate, median trade, top-1% share of total return (tail check).
>
> B. **Placebo fails to reproduce.** For each test-set trade, draw a random entry date for the SAME name within the same calendar month that the strategy was eligible to trade (passes the same liquidity floor), apply the SAME holding/exit rule and costs; 1,000 placebo sets. The strategy passes only if (strategy minus placebo-mean) per-trade expectancy has a clustered 95% CI excluding 0 AND the strategy beats >= 95% of the placebo sets. A placebo that is also positive means the return is market/name beta, not the rule.
>
> C. **Deflated Sharpe Ratio >= 0.95**, with N = every variant tried in this lab across ALL candidates (not per candidate), using the per-trade (or per-rebalance) return series' skew and kurtosis; PSR (benchmark SR 0) reported beside it. The trial count is written in the prereg log before each run; it never resets.
>
> Anything short of A+B+C = not positive. A pass on survivor-biased data is labelled provisional.

## How the gates are computed (design v2 3.6)

- **Units.** Every statistic converts fractions to PERCENT at its input; NaN into a gate raises
  `NaNGateError`.
- **A.** Mean net per OOS trade, 95% CI over whole entry weeks (`RS.boot_draws`, 10,000 draws); the word is
  read on the unrounded CI (`RS.ci_of(..., dp=VERDICT_DP)`, `VERDICT_DP = 12`); pass iff `RS.verdict`
  returns "separates". Beside it: win rate, stop-out rate (null, no stop), median, top-1% share, MAE p10,
  gross mean, break-even cost per side.
- **B.** Per trade i, the pool P_i = universe-cohort rows of the SAME symbol, SAME calendar month, SAME
  split, **EXCLUDING every signal index in [t_i - 10, t_i - 1]** (`PLACEBO_EXCLUDE_BACK = C5_R_LOOKBACK +
  C5_HOLD`; those placebo holds overlap the trade's own 5-session selection window plus its 5-session
  hold). The trade's own row always stays in the pool. This exclusion is not in gate B's verbatim text; it
  is stated here so it is fixed before the run. 1,000 sets drawn with replacement (`default_rng(SEED + 1)`);
  d_i = r_i - mean(P_i), week-cluster CI. Pass iff the diff word is "separates" AND beat share >= 0.95.
- **C.** Series = `GATE_C_SERIES` "per_entry_day": x_t = mean net over the trades with signal t, one value
  per OOS signal session with >= 1 trade (the shortlist's "per-rebalance" option). N and the trial Sharpes
  = every distinct trial in the ledger. Pass iff DSR >= 0.95. Beside it: PSR(0), lag-1 autocorrelation of
  x_t (adjacent cohorts share 4 of 5 hold days), per-trade PSR/DSR, the min/max PSR over the 5
  non-overlapping sleeve sub-series.
- **Word.** `positive_verdict`: "TOO SMALL" if OOS entry weeks < 30; "POSITIVE" iff A and B and C (and the
  glitch-row rule); else "NOT POSITIVE". A POSITIVE carries the label "provisional — survivor-biased in the
  rule's favour (dead names before the cache absent; delisting returns not modelled)".
- **Reported, never the verdict:** same-day universe excess; A without `data_end`; daily book SR/PSR/DSR,
  CAGR, vol, max drawdown; capacity; `late_exit` / `data_end` / skip counts; the 20 largest |net| trades;
  the 20 largest single-session moves inside any hold window.

## Glitch-row rule (dated 2026-10-29)

Audit defect 1: 13 flagged rows out of 7,250 (4 planted 10x reverse splits inside holds) turned a pure
iid null POSITIVE. The script holds **form (a)**:

- Gates A and B must pass BOTH on all rows AND with the flagged (`glitch_hold`) rows removed from trades
  and cohort (`verdict_of`, same seeds; no flagged row -> identical to the all-rows gates).
- **5% cap:** when the flagged rows are more than `GLITCH_VERDICT_MAX_SHARE` (5%) of the trade rows, no
  verdict word is printed: the run prints **"UNMEASURED-glitch"**.
- The report prints n_flagged and both lines.

The other option was (b): print no verdict word while any row is flagged. Ajay's call on the form is not
on record in the lab docs as of 2026-10-29; if he picks (b), the code changes and is re-tested and this
file is re-written before any commit.

## Split and seal (design 3.4)

- Calendar: SPY bars 2024-10-29 .. 2026-10-29, 502 sessions; 446 signal sessions (2025-01-13 .. 2026-10-21).
- IS: 292 signal sessions from 2025-01-13; then an **embargo of 5 sessions**.
- **OOS: signal sessions 2026-03-20 .. 2026-10-21 = 149 sessions, 31 entry weeks** (one more than the
  30-week minimum; one empty week -> TOO SMALL).
- Smoke and `--calibrate` build their IS from `seal_panel(panel, idx_oos)`: only the open survives at
  `idx_oos`; `calibrate_null` raises `LeakError` on any finite OOS close. No OOS bar has been read.
- **The read is irreversible.** Once the outcome run reads 2026-03-20 .. 2026-10-21, that window is no
  longer out-of-sample for any C5 / reversal-family variant; successors need sessions after 2026-10-29.

## CALIBRATION (IS only, sealed slice; measured 2026-10-29 before this commit)

| line | value |
|---|---|
| IS sealed slice | **14,600 trades / 61 entry weeks / 292 sessions** |
| universe-cohort rows (top 500 x day) | 145,995 |
| exit reasons | time 14,600, late 0, data_end 0 |
| flagged split-glitch rows in IS holds | **0** |
| SD per trade / SD of week means | 8.477% / 3.609% |
| p90 minus p10 per trade | 17.631 pp |
| mean net per trade | not computed: the seal prints no mean and no sign |
| MDE (80% power, two-sided 95%, IS week SD, 31 OOS weeks) | **1.816% per trade** |

Null calibration: 200 random-selection nulls per window (`CALIB_REPS`), each drawing on every IS signal
day the same count as that day's bottom decile, at random from the same eligible set, with their real
outcomes.

| window of 31 IS entry weeks | sessions | B CI false | B full-gate false | same-day excess CI false |
|---|---|---|---|---|
| 2025-01-13 .. 2025-08-11 | 148 | 0/200 [0.0, 1.9%] | 0/200 [0.0, 1.9%] | 7/200 = 3.5% [1.7, 7.1] |
| 2025-08-11 .. 2026-03-09 | 149 | 0/200 [0.0, 1.9%] | 0/200 [0.0, 1.9%] | 13/200 = 6.5% [3.8, 10.8] |
| **pooled** | | **0/400 [0, 0.95%]** | **0/400 [0, 0.95%]** | **20/400 = 5.0% [3.3, 7.6]** |

Power: the test can only detect about 1.8% per 5-session trade, 4 to 6 times the published 0.30-0.50% a
week (and that figure is long-short). A null is the plain outcome. These nulls keep the real
cross-correlation of the names but not the bottom decile's day-to-day repeats (62% of selected names repeat
from one day to the next; IS week means lag-1 autocorrelation 0.235); they are not the data's true null.
Synthetic checks (tests 19b and 20): B passes 0 of 20 iid nulls with the exclusion window, 20 of 20
without it; the full POSITIVE word fired at most once per drift.

## HIS CALLs (build defaults recorded; none decided here)

| # | question | default the script holds |
|---|---|---|
| 0 | Commit this file on the study branch so the T01 outcome run can start (the OOS read is irreversible)? | wait; commit only on his "commit the prereg" |
| 3 | Gate C series | per entry day (the shortlist's "per-rebalance"); alternatives: per-trade, non-overlapping sleeves, daily book |
| 4 | B pool and beta control | same-name, same-month placebo with [t-10, t-1] removed; same-day universe excess and A on excess stay reported |
| 6 | Costs | 15 bps per side as written; break-even printed; ~19 bps per side implied by de Groot beside it |
| 11 | Calibration remedy if the false rate is above nominal | keep the gate, print the rate; the rates came in at or below nominal (B 0/400, excess 20/400 = 5.0%), so the default holds |

## Seal procedure

1. On his "commit the prereg", commit ONLY this file on `study/strategy-lab-2026-10-29`. That commit is
   `HASH`; it goes into the run as `--prereg-commit HASH` (12-40 lowercase hex; a placeholder is refused).
2. On the host, `git show HASH:docs/research/strategy_lab_2026_10_29_prereg.md` must equal the working copy:

```
S=/private/tmp/claude-501/-Users-ajay-clinet-test/656642d4-5050-4aec-a1a8-e7114785de7b/scratchpad/strat
git -C /Users/ajay/clinet-test/wt-stratlab show HASH:docs/research/strategy_lab_2026_10_29_prereg.md > "$S"/prereg_committed.md
shasum -a 256 "$S"/prereg_committed.md /Users/ajay/clinet-test/wt-stratlab/docs/research/strategy_lab_2026_10_29_prereg.md
```

   The two sums must match, and the run's `stats.json` `prereg_sha256` must equal both.
3. Run the outcome command (outside 09:00-16:30 ET, its own `--rm` container, no `--env-file`). It reads
   the OOS window once and for good and appends T01 to the ledger:

```
docker run --rm --cpus 4 --memory 3g --network cheetah-market-app_default -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 -v /Users/ajay/clinet-test/wt-stratlab/backend:/app:ro -v /Users/ajay/clinet-test/wt-stratlab/docs:/docs:ro -v cheetah-market-app_cheetah-scans:/root/.cheetah:ro -v /Users/ajay/clinet-test/eod-audits/research:/research -v "$S":/strat -w /strat cheetah-api:latest python -u /app/scripts/strategy_lab_2026_10_29.py --candidate c5_reversal --as-of 2026-10-29 --oos-from 2026-03-20 --prereg /docs/research/strategy_lab_2026_10_29_prereg.md --prereg-commit HASH --ledger /research/strategy_lab_ledger.json --out /strat/out/c5_reversal
```

## What the result may change

Nothing served. The result is one row in `LEDGER.md` / the machine ledger and one report beside this lab's
report in `/Users/ajay/clinet-test/eod-audits/research/`. A POSITIVE becomes a PAPER lane only on his word;
no lane, gate, board, alert or constant changes because of this run.

## Known limits (stated in the artefact, `LIMITS`)

- Survivor-biased in the rule's favour: names that died before the app cached them are absent (the IS
  slice is close to survivors only: 106 of 6,510 docs end before 2026-05); a stopped name exits at its last
  cached close (delisting returns not modelled).
- The instrument-type map is TODAY's active list: a fund that died before today reads unknown and is kept
  unless a fund list names it; some live stocks read unknown too.
- A split appended below 5x (2:1, 3:2) between full refetches is NOT caught by the 5x glitch engine; the 20
  largest single-session moves inside hold windows are listed for the audit (no new threshold).
- A >= 5x jump inside a hold is KEPT and flagged: a real crash and an unadjusted split look alike (the
  glitch-row rule above).
- C5 cost tier 2 is unreachable (rank <= 500 < 1,000): every trade pays 15 bps per side.
- Dividends are not in the bars (`adjusted=true` covers splits only).
- The week-cluster CI can run below its nominal level on this design (adjacent cohorts share 4 of 5 hold
  days); the IS calibration rate prints beside the word.
- Per-entry-day Sharpe overstates PSR when cohorts overlap; the lag-1 autocorrelation and the sleeve range
  print beside it.

## Choices made before any outcome

1. N = 1 (T01); C1–C4 refused, no trial.
2. B's pool drops [t-10, t-1]; the symmetric window was rejected (power 3/20 vs 13/20 on a planted reversal).
3. Gate C on the per-entry-day series.
4. The word is read on the unrounded CI, in percent units.
5. Glitch-row rule form (a) + the 5% cap (2026-10-29).
6. as_of and oos_from frozen as dates; a later run sees a shorter IS head (the SPY doc head rolls daily),
   the OOS verdict is unaffected.
7. The clock refusal (09:00-16:30 ET) applies every day.
