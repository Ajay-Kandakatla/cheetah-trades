# Strategy lab 2026-10-29 (study doc)

**Verdict: nothing is POSITIVE. All five candidates are UNMEASURED.** C5 short-term reversal (trial T01) is built, tested and calibrated. Its out-of-sample window (signals 2026-03-20 to 2026-10-21) is still sealed, because the prereg doc is not yet written or committed (HIS CALL #0). An outcome run attempted at 19:18 ET did not start for that reason, so T01 stays UNMEASURED. C1 to C4 need history the app does not store, so the script refused them before reading anything.

This is research only. No rule here is served, no lane or constant was changed, and no order was placed. Rules are described here, not advised.

## The asks (Ajay, 2026-10-29, verbatim)

> "Look in to strategies yourself like ema based and Quant based reliable ones and also research baked in to this task but try and improve the strategy until you are postive in results"

> "Also please a trading skil in to the mix I heard Claude now has a trading skill"

## POSITIVE: the definition every candidate is judged by

Verbatim from the shortlist (shortlist.md:23-27), fixed before any run:

> A. **OOS expectancy.** Split by calendar time: the last third of the available sessions is the test set, sealed until design is frozen and the prereg doc is committed. On test-set trades only: mean net return per trade (after the cost model) > 0, and the 95% bootstrap CI excludes 0. The bootstrap resamples **whole entry weeks** (clustered; trades opened the same week are not independent), 10,000 draws, percentile CI. Report beside it: win rate, stop-out rate, median trade, top-1% share of total return (tail check).
>
> B. **Placebo fails to reproduce.** For each test-set trade, draw a random entry date for the SAME name within the same calendar month that the strategy was eligible to trade (passes the same liquidity floor), apply the SAME holding/exit rule and costs; 1,000 placebo sets. The strategy passes only if (strategy minus placebo-mean) per-trade expectancy has a clustered 95% CI excluding 0 AND the strategy beats >= 95% of the placebo sets. A placebo that is also positive means the return is market/name beta, not the rule.
>
> C. **Deflated Sharpe Ratio >= 0.95**, with N = every variant tried in this lab across ALL candidates (not per candidate), using the per-trade (or per-rebalance) return series' skew and kurtosis; PSR (benchmark SR 0) reported beside it. The trial count is written in the prereg log before each run; it never resets.
>
> Anything short of A+B+C = not positive. A pass on survivor-biased data is labelled provisional.

How design v2 computes the gates:
- A passes only when the house verdict engine (`RS.verdict`) returns "separates" on the unrounded CI.
- B's same-name placebo pool drops the dates t-10 to t-1. Those placebo holds overlap the trade's own 5-session selection window plus its 5-session hold.
- C runs on the mean net return per entry day.
- With fewer than 30 OOS entry weeks the script prints TOO SMALL.

## Scoreboard

| trial | candidate | verdict | OOS mean net / trade | 95% CI (entry weeks) | placebo (B) | PSR / DSR | max drawdown | n |
|---|---|---|---|---|---|---|---|---|
| T01 | C5 short-term reversal | **UNMEASURED** (OOS sealed, prereg not committed; the outcome run attempted 19:18 ET did not start) | not read | not read | IS null calibration: 0 of 400 false passes | not computed (ledger empty, N = 1) | not computed | IS 14,600 trades / 61 entry weeks; OOS 0 read |
| none | C1 all-time-high breakout, 10 x ATR(42) stop | **UNMEASURED** (refused, rc 3) | none | none | none | none | none | 0 |
| none | C2 12-1 momentum, top decile | **UNMEASURED** (refused, rc 3) | none | none | none | none | none | 0 |
| none | C3 earnings-announcement-return drift | **UNMEASURED** (refused, rc 3) | none | none | none | none | none | 0 |
| none | C4 SPY above its 10-month SMA, else T-bills | **UNMEASURED** (refused, rc 3) | none | none | none | none | none | 0 |

A refused candidate reads no bar and burns no DSR trial. The trial count N stays at 1: T01 is registered, with 0 OOS reads.

## C5 short-term reversal (T01)

Sources: Jegadeesh (1990) and Lehmann (1990). De Groot, Huij and Zhou (2012, JBF) find that it survives costs only in the largest, most liquid names. Nagel (2012, RFS) reads it as a premium for providing liquidity. The literature figure is 30 to 50 bps a week net, **long-short**, in large caps (lit.md:243-246). It contradicts all four of his frameworks, because it buys weakness. It was included as a control: it is one of the best-replicated anomalies.

### Rule (frozen; shortlist.md:58, design 3.3)
- **Universe on day t.** The 500 largest names by median close x volume over their last 50 own bars. A name must also pass the house liquidity floor (`adr.liquidity_check` defaults: mean 50-bar dollar volume of at least $20M) on bars up to t. Funds, crypto pairs and index docs are excluded. Names that later died are kept.
- **Signal.** The lowest tenth of those 500 by 5-session return (close t / close t-5 - 1), taken at the close of t.
- **Trade.** In at the open of t+1, out at the open 5 sessions later (t+6). No stop, long only.
- **Account.** Cash account with T+1 settlement, which the book models as 6 sleeves.
- **Cost.** 15 bps per side: 10 bps for the top-1,000 tier plus 5 bps slippage. The 25 + 5 bps tier cannot apply, because every rank is 500 or better. The run asserts 0 tier-2 trades.
- **Split hygiene.** The house engine is `prices._is_scale_glitch`, which flags any jump of 5x or more.
  - A flagged jump inside the 5-session signal window: the name is not ranked that day.
  - A flagged jump inside a hold: the trade is kept and flagged, and A prints both with and without the flagged rows.

### Frozen parameters
| parameter | value | parameter | value |
|---|---|---|---|
| universe | top 500 by 50-bar median $ volume | cost per side | 15 bps (tier 1), 30 bps (tier 2, unreachable) |
| signal | bottom decile of 5-session return | position cap | 1% of 20-day median $ volume (capacity only) |
| entry / exit | open t+1 / open t+6 | bootstrap | 10,000 draws, whole entry weeks |
| stop | none | placebo | 1,000 sets, beat share >= 0.95 |
| as_of | 2026-10-29 | placebo exclusion window | t-10 .. t-1 (5 + 5) |
| oos_from | 2026-03-20 | gate C series | mean net per entry day |
| DSR pass | 0.95 | seed | 20261029 |

### Cohort and dates
- **Calendar.** SPY bars from 2024-10-29 to 2026-10-29: 502 sessions, with 446 signal sessions (2025-01-13 to 2026-10-21).
- **IS.** 292 signal sessions from 2025-01-13. An embargo of 5 sessions follows.
- **OOS.** 149 signal sessions from 2026-03-20 to 2026-10-21, which is **31 entry weeks**, one more than the 30-week minimum.
- **Universe build.** 6,510 cached docs.
  - Excluded: 833 in all.
    - by kind: index 9, crypto pair 1
    - by fund list: static ETF list 381, cached ETF 18, levered fund 101
    - by instrument type: non-equity 323
  - Kept although the type map has no entry for them: 393, mostly dead names.
  - Merged as renames: 12.
  - Names ever eligible for the top 500: 691.
  - Read-only: the only attempted write was `price_cache.create_index`, which ran as a no-op. There were no fetches.
- **Survivorship runs in the rule's favour.**
  - The IS is close to survivors only: 106 of 6,510 docs end before 2026-05.
  - Names that died before the app cached them are absent.
  - A stopped name exits at its last cached close, so delisting returns are not modelled.

### In-sample vs out-of-sample
| line | IS (sealed slice) | OOS 2026-03-20 .. 2026-10-21 |
|---|---|---|
| trades | 14,600 | sealed, 0 read |
| entry weeks / signal sessions | 61 / 292 | 31 / 149 (calendar counts) |
| universe-cohort rows (top 500 x day) | 145,995 | sealed |
| exit reasons | time 14,600, late 0, data_end 0 | sealed |
| flagged split-glitch rows in holds | 0 | sealed |
| SD per trade / SD of week means | 8.477% / 3.609% | sealed |
| p90 minus p10 per trade | 17.631 pp | sealed |
| mean net per trade (A) | not computed: by design the seal prints no mean and no sign | sealed |
| minimum detectable effect (80% power, two-sided 95%) | 1.816% per trade over 31 OOS weeks, from the IS week SD | n/a |

**Power.** The test can only detect about 1.8% per 5-session trade. That is 4 to 6 times the published 0.30-0.50% per week, and the published figure is long-short. A null result would therefore be no surprise (design risk 1).

### Placebo and CI calibration (IS only; 200 random-selection nulls per window)
Each null draws, on every IS signal day, the same number of names as that day's bottom decile, at random from the same eligible set. It uses their real outcomes.

| window of 31 IS entry weeks | sessions | B CI false | B full-gate false | same-day excess CI false |
|---|---|---|---|---|
| 2025-01-13 .. 2025-08-11 | 148 | 0/200 [0.0, 1.9%] | 0/200 [0.0, 1.9%] | 7/200 = 3.5% [1.7, 7.1] |
| 2025-08-11 .. 2026-03-09 | 149 | 0/200 [0.0, 1.9%] | 0/200 [0.0, 1.9%] | 13/200 = 6.5% [3.8, 10.8] |
| **pooled** | | **0/400 [0.0, 0.95%]** | **0/400 [0.0, 0.95%]** | **20/400 = 5.0% [3.3, 7.6]** |

On his IS data, gate B never fired on a random selection. The same-day excess CI fired at its nominal 5% rate.
- **The concern the design raised.** An iid synthetic same-day-excess null showed a false rate of 17%. 62% of selected names repeat from one day to the next, and the IS week means have a lag-1 autocorrelation of 0.235.
- **Limit.** These nulls keep the real cross-correlation of his names, but not the bottom decile's day-to-day repeats (design risk 18). They are not his data's true null.
- **Synthetic checks.** Tests 19b and 20 cover the repeat structure on synthetic data.
  - B passes 0 of 20 iid nulls with the exclusion window and 20 of 20 without it.
  - The full POSITIVE word fired at most once per drift.

### PSR / DSR
- Not computed: the OOS is sealed.
- The ledger is empty, so N = 1, and DSR equals PSR(0) by construction (test 18).
- The per-entry-day Sharpe overstates PSR, because adjacent cohorts share 4 of 5 hold days. The outcome run prints the lag-1 autocorrelation and the range over the 5 non-overlapping sleeves beside it.

### Max drawdown
Not computed. The daily book's CAGR, volatility and max drawdown are outcome-run lines. The IS block holds counts and dispersion only, by design.

### Verdict
**UNMEASURED.** The outcome run is blocked until the prereg is written and committed (HIS CALL #0). An attempt at 19:18 ET did not start; see "T01 C5 outcome read" below.

### Audit note (critic, 2026-10-29)
- **Repairs 1, 2 and 4 hold.**
  - Repair 1: the ledger clash check runs before any bar read.
  - Repair 2: the ledger path is checked and the script no longer creates the folder.
  - Repair 4: each candidate has its own fact.
  - Mutation tests: moving the clash check after the bar read, putting the mkdir back, dropping the path check and dropping the glitch rows each turn a repair test red.
  - Lab tests: 57 of 57 pass. The full suite shows the same 14 host-env failures as the executor's baseline, none of them in the lab.
- **Defect 1 (MEDIUM, open; the fix form is HIS CALL).**
  - Where: `strategy_lab_2026_10_29.py:1320` (A passes on all rows) and `:1766` (the verdict word).
  - What: the verdict counts the flagged split-glitch rows.
  - Probe: `critic_re/glitch_up.py`, an iid null with 500 names and 7,250 trades per row. It plants 10x unadjusted reverse splits inside holds:

  | seed | planted | flagged rows | A, all rows | A / B / C | DSR | word | A without flagged rows |
  |---|---|---|---|---|---|---|---|
  | 1 | 0 | 0 | -0.385% [-0.912, 0.185] | no / no / no | 0.010 | NOT POSITIVE | -0.385%, no_signal |
  | 1 | 4 | 12 | +0.951% [-0.378, 2.595] | no / no / yes | 0.998 | NOT POSITIVE | -0.381%, no_signal |
  | **2** | **4** | **13** | **+1.198% [0.059, 2.512]** | **yes / yes / yes** | **0.9999** | **POSITIVE** | **-0.309% [-0.841, 0.196], no_signal** |
  | 3 | 0 | 0 | +0.346% [-0.295, 1.043] | no / no / yes | 0.966 | NOT POSITIVE | +0.346%, no_signal |
  | 3 | 4 | 13 | +1.595% [0.465, 2.854] | yes / no / yes | >0.9999 | NOT POSITIVE | +0.346%, no_signal |

  The table shows 5 of the 9 probe rows; all 9 are in `glitch_up.out`.

  - **Result.** 13 flagged rows out of 7,250 turned a pure null into POSITIVE.
  - **Exposure on his data.** His IS slice has 0 flagged rows. The design's own probe found 6 universe-cohort rows straddling a jump, none of them selected. The OOS count is unknown until the window is read.
  - **Fix options.**
    - (a) A and B must also pass with the flagged rows removed.
    - (b) Print no verdict word while any row is flagged.
  - **Gate C on its own.** The same probe shows C passing on 1 of the 3 clean nulls (seed 3, DSR 0.966, A no_signal). With N = 1, A and B carry the test (design risk 3).
- **Defect 2 (LOW, open).**
  - Line 168 cites `earnings_watch.py:151-162`, which is the `last_report_map` docstring.
  - The code that keeps only the latest report is at `:99-107` (`max(past)`) and `:240-250` (`replace_one`).
  - The fact is true; only the cite needs fixing.

## T01 C5 outcome read, 2026-10-29 19:18 ET

**Verdict: UNMEASURED.** The outcome run did not start. The out-of-sample window (signals 2026-03-20 to 2026-10-21, 31 entry weeks) is still sealed and was not read. There is no A, B or C result.

### Why the run did not start
Checked read-only on the host at 19:20 ET:
- `docs/research/strategy_lab_2026_10_29_prereg.md` does not exist in the worktree.
- Nothing is committed on `study/strategy-lab-2026-10-29`; HEAD is `9aa6ef1e`. The script, both test files and `docs/studies/` are untracked.
- The outcome command needs `--prereg` and `--prereg-commit <hash>`. There is no commit, so there is no hash, and none was made up.
- The clock was not the cause: 19:18 EDT is outside 09:00-16:30 ET.
- No OOS artefacts exist:
  - `scratchpad/strat/out/c5_reversal/` holds only `calibration/`.
  - `out/c5_reversal_oos/` does not exist.
  - The machine ledger `strategy_lab_ledger.json` does not exist.

### Numbers
| line | value |
|---|---|
| OOS trades / entry weeks read | 0 / 0 (all 31 weeks still sealed) |
| A: mean net per trade, 95% CI (entry weeks) | not computed |
| B: placebo | not computed |
| C: DSR / PSR(0) | not computed. N = 1, so DSR would equal PSR(0). |
| max drawdown | not computed |
| flagged split-glitch rows, OOS | not computed (IS: 0) |
| IS sealed slice (unchanged) | 14,600 trades / 61 entry weeks / 292 sessions; MDE 1.816% per trade |
| IS null calibration (unchanged) | B CI 0/400 [0.0, 0.95%]; same-day excess 20/400 = 5.0% [3.3, 7.6] |
| lab tests | 62 passed (both lab test files, run with the main tree's venv) |

### Audit (critic, 2026-10-29 evening)
**Audit verdict: UNMEASURED.** No verdict word can be given, because A, B and C were never computed. The runner's refusal matches both the code and the filesystem.

The checks that could be done without reading the OOS window all pass:
- **The split.** `oos_from` 2026-03-20 equals the last-third rule date: 149 OOS sessions and 31 weeks, after 292 IS sessions plus a 5-session embargo.
- **The seal.** `seal_panel` keeps only the open at `idx_oos`. `calibrate_null` raises `LeakError` on any finite OOS close.
- **The glitch rule (defect 1).** It is now in code: see the script header and `GLITCH_VERDICT_MAX_SHARE` at `:155`.
  - Flagged rows are kept.
  - A and B must pass both with and without the flagged rows.
  - Above 5% flagged rows, no verdict word is printed (`UNMEASURED_GLITCH`).
  - IS flagged rows: 0.
  - The earlier audit note left the fix form as HIS CALL. These docs have no record of his call on it.

Not done:
- **Matching the prereg commit hash.** There is no commit to match against.
- **The 30-trade hand recompute.** There are no OOS trades. Computing them from the bars would itself be the one-time OOS read, done before the prereg commit.

| # | severity | defect | fix |
|---|---|---|---|
| 1 | HIGH (a blocker, not a code bug) | No prereg doc and no commit, so there is no OOS result. | Write and commit the prereg (HIS CALL #0). Then re-run with `--prereg-commit` set to that hash. |
| 2 | MEDIUM (his call) | With N = 1, gate C does no deflating. `dsr_sr0` returns 0 when N < 2 (script:1146-1150), so DSR equals PSR(0). Gate C's text says N goes in a prereg log before each run, and no prereg log exists. On the audit probe, C passed on 1 of the 3 clean nulls. | Before the run, write N into the prereg, with the reason C1 to C4 are not counted in it. |
| 3 | LOW (his call) | B's placebo pool drops the dates t-10 to t-1 (`PLACEBO_EXCLUDE_BACK`, script:144 and :1088). That exclusion is not in gate B's verbatim text. | State it in the prereg. |
| 4 | LOW | The worktree has no `backend/.venv` symlink, which cheetah-ops expects. The suites were run on the main tree's venv. | Add the symlink. Until then, the recipe's explicit venv path works. |

### What changes
- Nothing was measured, so nothing changes.
- N stays 1: T01 is registered, with 0 OOS reads.
- The one-time OOS read is still owed, and it waits on HIS CALL #0.
- No lane, gate, board or constant was changed, and no order was placed.

## C1 to C4: refused (rc 3, nothing read, no ledger entry)

| candidate | rules (frozen; the paper's own values) | sources | refusal (script's words) |
|---|---|---|---|
| **C1** all-time-high breakout | Entry: a new all-time closing high (at least 252 bars), in at the next open. Stop: ATH - 10 x ATR(42); it only ratchets up, and a close below it means out at the next open. Unadjusted close above $10. Liquidity uses the house $20M / 50-day floor, against the paper's $1M / 42-day; this is the one logged deviation. | Wilcox and Crittenden 2005. Zarattini, Pagani and Wilcox 2025 (Norgate data including delisted names; win rate 43.9%; 0.39R per trade before 2005, 0.31R after; average winner held 370 days). | needs >= 10 years of daily bars back to each listing (point-in-time ATH) |
| **C2** 12-1 momentum | Formation: return from t-252 to t-21. Hold: the top decile of the point-in-time liquid universe, equal weight. Rebalance every 21 sessions. No volatility scaling or regime filter. | Jegadeesh and Titman 1993 and 2001; Israel and Moskowitz 2013 (the long side supplies about half). Crash risk after sharp bear-market recoveries (Daniel and Moskowitz 2016). | needs >= 10 years of daily bars (>= 30 OOS rebalances) |
| **C3** earnings-announcement-return drift | Day 0 is the first session that reflects the report: the same day if before the open, the next day if after the close. EAR = name minus SPY, close day -1 to close day +1. In at the day +2 open if EAR > 0 and in the top decile of trailing-63-session EARs. Hold 60 sessions, no stop. | Chan, Jegadeesh and Lakonishok 1996; Brandt et al. 2008. Surprise-based drift has decayed in large caps (Martineau 2022). The weakest evidence of the five. | needs a historical BMO/AMC-stamped announcement-date series |
| **C4** SPY 10-month SMA | Signal: SPY's month-end close vs the 10-month average of month-end closes. Above: hold SPY next month. Below: T-bills. RSP would be a separate variant. | Faber 2007, updated 2013 and 2018: it beat buy-and-hold in only 3 of 7 OOS years (2006-2012). Moskowitz, Ooi and Pedersen 2012. Its documented effect is smaller drawdowns, not higher return. | needs >= 25 years of SPY daily bars |

## What was not replicable on his data, and why

| item | fact (file:line or probe) | what unlocks it |
|---|---|---|
| C1, C2, C4 history | `price_cache` is a rolling 2-year window (`sepa/prices.py:635`), and SPY has 502 bars. C1 needs ATHs back to each listing; `ath_history` stores one summary per name. C2 has about 4 OOS rebalances against the 30 needed. C4 makes about one trade a year. | HIS CALL #1: a one-off pull of 10+ years (SPY 25+) into a study-only store, off RTH, in its own container (Massive cost) |
| C3 announcement dates | Only each name's latest Yahoo `last_report` is kept (`earnings_watch.py:99-107`, `:240-250`), with no BMO/AMC history. The 10-Q filing date lags day 0 by days to weeks. | HIS CALL #2: EDGAR 8-K Item 2.02 acceptance times, or C3 stays UNMEASURED |
| A point-in-time universe (all candidates) | `HISTORY_RETENTION_DAYS = 45` (`sepa/history.py:78-90`). `universe_snapshots` start on 2026-08-16. Today's `full` list is survivors only. C5 used every cached doc, with eligibility from its own bars, so names that died before the cache are missing. | Massive grouped-daily bars per date (part of HIS CALL #1) |
| Delisting returns | A stopped name exits at its last cached close | same |
| Splits under 5x | Splits of 2:1 or 3:2 appended between full refetches sit unadjusted, and the 5x engine (`prices.py:562-585`) does not catch them. The 20 largest single-session moves inside holds are listed for the audit. | no new threshold (Rule #1) |
| Dividends | The bars are `adjusted=true`, which covers splits only (`prices.py:258`) | not modelled; this slightly understates long returns |
| Intraday candidates (ORB, VWAP, SPY intraday momentum) | The intraday cache is fetched per name, on demand (selection bias). SPY has 146 minute-bar days, from 2026-04-01. | not shortlisted |

## The trading skill

- **What exists.**
  - No Anthropic skill named "trading" is installed. This session's skill list and `~/.claude/skills/` were checked on 2026-10-29.
  - The closest match is the attached **third-party quant connector** (release 2.15.0): `workflow_run_sharpe_stats` (Lo-corrected Sharpe plus PSR), `workflow_run_dsr` (Deflated Sharpe) and `workflow_run_portfolio_tearsheet` (max drawdown, Sortino, Calmar and others).
  - The `whale-lens` skill covers investor frameworks. It is a lens, not evidence; the shortlist's framework lines were written from the published books (shortlist.md:6).
- **Its role here.** The connector is an independent cross-check of the in-script PSR/DSR, and it supplies the tearsheet for the OOS book once that exists. The in-script formula stays the gate of record (design section 0). The Kelly, VaR and sizing tools are not used.
- **Cross-check run today, on a SYNTHETIC series.** 149 values (Student-t, 5 df, seed 20261029) plus 4 made-up trial Sharpes. None of his data was sent.

  | line | in-script formula | connector |
  |---|---|---|
  | per-period SR / skew / kurtosis | 0.08307 / -0.0631 / 3.9365 | identical |
  | PSR(0) | 0.842658430422 | 0.842658430422 (differs by 1e-16) |
  | DSR threshold with trials [0.02, 0.05, 0.08, 0.11] | 0.040749 (zero-skill null) | 0.105749 (= 0.040749 + the trials' mean SR 0.065) |
  | DSR | 0.6958 | 0.3919; the formula's PSR at the connector threshold also gives 0.391864 |

  PSR agrees exactly. The DSRs differ only by the documented convention: the connector tests against the best of the trials actually observed, which is stricter whenever the trials' mean Sharpe is above 0. With N = 1 the question does not arise (the connector needs at least 2 trial Sharpes). **New HIS CALL #12:** which convention is the gate once N reaches 2 or more. Inputs and outputs are saved in `scratchpad/strat/out/connector_xcheck_synthetic.json`.
- **Not done.** No OOS return array of his was sent; that waits on HIS CALL #8. A plugin (QuanterLab) was offered earlier as a card. It needs his account and is his choice.

## Open decisions (HIS CALL; none decided here)

0. **Prereg.** Write `docs/research/strategy_lab_2026_10_29_prereg.md` in the house format, with these calibration numbers in it. The evening audit adds three lines it must state: N = 1 and why C1 to C4 are not counted in it, B's t-10 to t-1 placebo exclusion, and the defect 1 fix form. Then decide: commit it on the study branch so the T01 outcome run can start? Reading the OOS is irreversible (design risk 11).
1. **Defect 1 fix form.** The script now holds (a), A and B must also pass with the flagged rows removed, plus a cap: above 5% flagged rows no verdict word is printed. The other option was (b), print no verdict word while any row is flagged. His call on the form is not on record.
2. **History pull** for C1, C2 and C4 and a point-in-time universe (#1). The **C3 date source** (#2).
3. **Gates.** Gate C series (#3, default per entry day). B pool (#4, default same-name, same-month, with t-10 to t-1 removed).
4. **Costs** (#6). 15 bps per side as written, against the roughly 19 bps per side implied by de Groot's 75 bps a week. The outcome run prints the break-even cost.
5. **Connector.** Send unlabeled OOS return arrays to it (#8)? And the DSR convention (#12, new).
6. **Calibration remedy** (#11). The rates came in at or below nominal, so the default "keep the gate, print the rate" holds.

## Conclusion

Today's lab produced no measured result, and nothing in it supports changing a lane, a gate or a board.
- Five candidates were pre-registered from published, replicated evidence.
- Four (ATH breakout, 12-1 momentum, earnings drift, the SPY 10-month regime) cannot be tested on a rolling 2-year cache. They stay UNMEASURED.
- The fifth, C5 weekly reversal (a rule that runs against his buy-strength frameworks), is built, tested and calibrated on his in-sample data.
  - Its placebo gate never fired on 400 random selections (0/400).
  - Its same-day excess CI held its nominal 5% (20/400).
  - The out-of-sample read can only detect about 1.8% per trade, several times the published long-short figure, so a null would be the plain outcome.
  - The audit found that 13 unadjusted-split rows can turn a pure null into POSITIVE. The script now holds a fix: A and B must pass with and without the flagged rows, and above 5% flagged rows no word is printed. His call on that form is not on record.
- **The T01 outcome read was attempted at 19:18 ET and did not start.** The prereg is not written or committed (HIS CALL #0), so no OOS bar was read.
  - T01 is UNMEASURED, not NOT POSITIVE: there is no A, B or C result.
  - The evening audit agreed. It found the seal intact and the refusal correct.
  - It added that the prereg must state N, because gate C does no deflating at N = 1, and the placebo's t-10 to t-1 exclusion.

"Improve until positive" cannot be met by tuning C5 on the same window: that is the data mining the DSR count exists to penalize. The honest routes are the queue: forward sessions after 2026-10-29, or the one-off longer history (his call).

## Next hypotheses

These are in `QUEUE.md`, each with its source and pre-registered values. Each one adds a DSR trial, and N never resets.
1. T01 outcome read: attempted 2026-10-29 19:18 ET, did not start. It is still owed, blocked on #0, and his call on the defect 1 fix form goes in the prereg.
2. T01's frozen rule on forward sessions only. It can be read once 30 entry weeks have accrued, not before June 2027.
3. C1 ATH breakout (needs #1).
4. C2 12-1 momentum (needs #1).
5. C4 SPY 10-month SMA (needs #1).
6. Single-stock time-series momentum, long only (needs #1).
7. C3 EAR drift (needs #2).
8. RSI(2), Connors: too small on the 2-year cache, and in the same family as T01.
9. Donchian 20/10, System 1 (futures-era evidence only).
10. 8/21 EMA pullback: no values are registered because the source rule is ambiguous, so the next step is to ask him for his exact rule.

## Files

| what | where |
|---|---|
| script / tests | `/Users/ajay/clinet-test/wt-stratlab/backend/scripts/strategy_lab_2026_10_29.py`; `backend/tests/test_strategy_lab_2026_10_29.py`, `test_strategy_lab_repair_2026_10_29.py`. All untracked on `study/strategy-lab-2026-10-29` and not committed. |
| study doc (re-run recipe) | `/Users/ajay/clinet-test/wt-stratlab/docs/studies/strategy_lab_2026_10_29.md` |
| design / shortlist / literature | `scratchpad/strat/design.md`, `shortlist.md`, `lit.md` |
| calibration artefacts | `scratchpad/strat/out/c5_reversal/calibration/` (`calibration.json`, `stats.json`, `report.md`, `run.log`) |
| refusals | `scratchpad/strat/out/c{1..4}_*/status.json` |
| audit probe | `scratchpad/strat/critic_re/glitch_up.py`, `glitch_up.out` |
| connector cross-check | `scratchpad/strat/out/connector_xcheck_synthetic.json` |
| ledger / queue | `/Users/ajay/clinet-test/eod-audits/research/LEDGER.md`, `QUEUE.md`. The machine ledger `strategy_lab_ledger.json` is written only by an outcome run and does not exist yet. |

`scratchpad` = `/private/tmp/claude-501/-Users-ajay-clinet-test/656642d4-5050-4aec-a1a8-e7114785de7b/scratchpad`

## Reproduce: script, container recipe, re-run

### Where the code is
- **Worktree.** `/Users/ajay/clinet-test/wt-stratlab`, branch `study/strategy-lab-2026-10-29`. Nothing is committed: the script, its tests and this doc are untracked, and `frontend/node_modules` is never added.
- **Script.** `backend/scripts/strategy_lab_2026_10_29.py` (2,019 lines after the glitch fix).
  - Mongo access is read-only. `RS.block_writes` records writes as no-ops; the only attempted write is `price_cache.create_index`.
  - There is no network. `block_network()` is on, and the script refuses to run when a Massive key is in the environment. It never calls `prices.load_prices`.
  - It imports no `trading.*`, `alpaca*`, `autopilot*` or `notifications*` module, and no alert-gate module.
- **Tests.** `backend/tests/test_strategy_lab_2026_10_29.py` and `backend/tests/test_strategy_lab_repair_2026_10_29.py`. They need no Mongo and no network, and run on synthetic bars. 62 pass (evening audit, 2026-10-29).
- **CLI.**
  - Required: `--candidate {c5_reversal,c1_ath_atr10,c2_xsmom_12_1,c3_ear_drift,c4_spy_sma10m}` and `--out DIR`. The out dir must be outside the repo.
  - Modes: `--smoke` (IS counts only; `--stride K` with a default of 10), `--calibrate` (IS null calibration), or neither flag for the outcome run.
  - Exit 3: the candidate cannot be measured; nothing is read and no ledger entry is written.
  - Exit 2: a one-line refusal. The causes are:
    - the clock is inside 09:00-16:30 ET without `--force-window`
    - `--out` is inside the repo
    - a Massive key is in the environment
    - `--smoke` is combined with `--calibrate`
    - `--calibrate` is missing `--oos-from`
    - the outcome run is missing `--prereg`, `--prereg-commit`, `--oos-from` or `--ledger`
    - the commit is not 12-40 hex characters
    - `--ledger` is not `/research/strategy_lab_ledger.json`, or that folder is not mounted
    - a ledger trial clashes; this is checked before any bar is read
- **When to run.** After 16:30 ET or before 09:00 ET. Today's bar is patched hourly during the session.
- **Container.** Each run gets its own throwaway `--rm` container on the compose network. Never run inside `cheetah-market-app-api-1`, and never pass `--env-file`.

### 1. Tests (host venv)
```
cd /Users/ajay/clinet-test/wt-stratlab/backend && rm -rf ~/Library/Caches/com.apple.python && /usr/bin/find . -name __pycache__ -type d -prune -exec rm -rf {} + && PYTHONDONTWRITEBYTECODE=1 /Users/ajay/clinet-test/cheetah-market-app/backend/.venv/bin/python -m pytest tests/test_strategy_lab_2026_10_29.py tests/test_strategy_lab_repair_2026_10_29.py -q -p no:cacheprovider
```
Expected: `62 passed`.

### 2. Container recipe
`S` is any scratch folder outside the repo. This run used `/private/tmp/claude-501/-Users-ajay-clinet-test/656642d4-5050-4aec-a1a8-e7114785de7b/scratchpad/strat`.

Refused candidates (each exits 3 and reads nothing):
```
S=/private/tmp/claude-501/-Users-ajay-clinet-test/656642d4-5050-4aec-a1a8-e7114785de7b/scratchpad/strat
for c in c1_ath_atr10 c2_xsmom_12_1 c3_ear_drift c4_spy_sma10m; do docker run --rm --cpus 4 --memory 3g --network cheetah-market-app_default -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 -v /Users/ajay/clinet-test/wt-stratlab/backend:/app:ro -v cheetah-market-app_cheetah-scans:/root/.cheetah:ro -v "$S":/strat -w /strat cheetah-api:latest python -u /app/scripts/strategy_lab_2026_10_29.py --candidate "$c" --out /strat/out/"$c"; echo "$c rc=$?"; done
```

C5 smoke (IS counts; this prints no mean and no sign). `--stride 1` gives the full IS slice:
```
docker run --rm --cpus 4 --memory 3g --network cheetah-market-app_default -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 -v /Users/ajay/clinet-test/wt-stratlab/backend:/app:ro -v cheetah-market-app_cheetah-scans:/root/.cheetah:ro -v "$S":/strat -w /strat cheetah-api:latest python -u /app/scripts/strategy_lab_2026_10_29.py --candidate c5_reversal --smoke --stride 1 --out /strat/out/smoke_full
```

C5 calibration (IS only, about 36 s):
```
docker run --rm --cpus 4 --memory 3g --network cheetah-market-app_default -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 -v /Users/ajay/clinet-test/wt-stratlab/backend:/app:ro -v cheetah-market-app_cheetah-scans:/root/.cheetah:ro -v "$S":/strat -w /strat cheetah-api:latest python -u /app/scripts/strategy_lab_2026_10_29.py --candidate c5_reversal --calibrate --as-of 2026-10-29 --oos-from 2026-03-20 --out /strat/out/c5_reversal/calibration
```
Expected output lines:
- `IS sealed slice: trades 14600 · entry weeks 61 · sessions 292 · MDE 1.816 pct · OOS sealed`
- `B CI 0.0% [0.0, 0.9] · B full 0.0% [0.0, 0.9] · same-day excess 5.0% [3.3, 7.6] (200 of 200 reps)`

The SPY doc head rolls daily, so a later run sees a shorter IS head. Some IS counts may then differ slightly; as_of and oos_from stay frozen as dates.

### 3. C5 outcome run: BLOCKED until HIS CALL #0
Steps, in order:
1. Write `docs/research/strategy_lab_2026_10_29_prereg.md`.
2. Get his call on the defect 1 fix form. The script already holds form (a) plus the 5% no-word cap; record his call in the prereg, and change and re-test the code only if he picks otherwise. The prereg also states N = 1 (with why C1 to C4 are not counted) and B's t-10 to t-1 exclusion.
3. Fix the C3 cite (defect 2).
4. On his "commit the prereg", commit only that doc on the study branch.
5. Run the host check below. `HASH` is that commit.
6. Run the outcome command. It reads the OOS window (2026-03-20 to 2026-10-21) **once and for good**, and appends T01 to the ledger.

Host check:
```
git -C /Users/ajay/clinet-test/wt-stratlab show HASH:docs/research/strategy_lab_2026_10_29_prereg.md > "$S"/prereg_committed.md
shasum -a 256 "$S"/prereg_committed.md /Users/ajay/clinet-test/wt-stratlab/docs/research/strategy_lab_2026_10_29_prereg.md
```
The two sums must match, and the run's `stats.json` `prereg_sha256` must equal both.

Outcome command:
```
docker run --rm --cpus 4 --memory 3g --network cheetah-market-app_default -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 -v /Users/ajay/clinet-test/wt-stratlab/backend:/app:ro -v /Users/ajay/clinet-test/wt-stratlab/docs:/docs:ro -v cheetah-market-app_cheetah-scans:/root/.cheetah:ro -v /Users/ajay/clinet-test/eod-audits/research:/research -v "$S":/strat -w /strat cheetah-api:latest python -u /app/scripts/strategy_lab_2026_10_29.py --candidate c5_reversal --as-of 2026-10-29 --oos-from 2026-03-20 --prereg /docs/research/strategy_lab_2026_10_29_prereg.md --prereg-commit HASH --ledger /research/strategy_lab_ledger.json --out /strat/out/c5_reversal
```
Artefacts:
- `$S/out/c5_reversal/`: `trades.json`, `daily.csv`, `stats.json`, `report.md`, `connector_payloads.json` (no symbols) and `run.log`.
- The ledger at `/Users/ajay/clinet-test/eod-audits/research/strategy_lab_ledger.json`. It is written atomically.

The connector cross-check of `connector_payloads.json` (Sharpe stats, DSR, tearsheet) runs only on HIS CALL #8. Its replies go to `connector_results.json`, with the formula and connector values side by side. The formula is the gate.

After the run:
- Add the T01 row to `LEDGER.md`.
- Copy `report.md` beside this lab's report in `/Users/ajay/clinet-test/eod-audits/research/`.
- Move Q01 off `QUEUE.md`.
