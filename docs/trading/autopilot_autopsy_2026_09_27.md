# Auto-Pilot money autopsy — 2026-09-27 (paper, READ-ONLY)

**Script:** `backend/scripts/autopilot_autopsy_2026_09_27.py` (re-runnable, read-only;
runs in the api image). **Numbers:** `backend/scripts/autopilot_autopsy_2026_09_27_measured.json`.

Ground truth is the **broker fills** (Alpaca paper FILL activities, 303 fills → 80
closed round-trip legs → 76 positions), not the journal. Each round-trip is tied to
its lane **by order id** against the engine ledger (current + the 2026-07-12
archive): 35/35 stock trips matched by order id, 0 unledgered. Win rate has a Wilson
95% CI; expectancy ($ and R) has a bootstrap 95% CI (seed 20260927, 5,000
resamples). Buckets describe what happened; they are not rules. Where n < 10 the
table says "small n". Nothing is extrapolated.

```
PYTHONPATH=/app python autopilot_autopsy_2026_09_27.py OUT.json [--no-bars]
```

## 1. Account

| | |
|---|---|
| Account created | 2026-06-12, $100,000.00 |
| Equity now (2026-09-26) | **$88,938.60** |
| Change | **−$11,061.40 (−11.06%)** |
| Realised on closed round-trips | −$11,260.91 |
| Unrealised on 6 open positions | +$228.04 |
| Fees | −$28.53 |
| Reconcile residual | $0.00 |
| Max drawdown | −11.98% (peak 2026-07-07 → 2026-09-26) |

Weekly equity change: +$746 (wk 06-29), **−$2,800 (wk 07-06)**, flat 07-13 → 08-31
(the engine was idle), **−$5,348 (wk 09-07)**, −$2,451 (wk 09-14), −$1,492 (wk 09-21).

## 2. Where the money went

**Overall:** n=76, win 27.6% (18.8–38.6), payoff 1.08, stop-out 59.2%,
expectancy **−$148/trade (−274..−32)**, −0.18R (−0.35..−0.01).
Stocks −$10,423 (n=35, −0.35R, CI −0.61..−0.07). Options −$838 (n=41, −0.04R, CI
−0.22..+0.17; not distinguishable from zero).

### The headline: two opening-bell clusters

| ET entry day | entries | win | total $ |
|---|---|---|---|
| **2026-09-09** | 9 (in 61 s, 09:30:03–09:31:04) | 0/9 | **−$8,947** |
| **2026-07-06** | 5 (09:36–09:37) | 0/5 | **−$3,785** |
| every other day | 21 | 10/21 | **+$2,309** |

Those 14 trades are **−$12,732, more than the whole loss**. Twelve of the 15 biggest
losers are from those two days.

| Open stock positions at entry | n | win % | exp $ | exp R | total $ |
|---|---|---|---|---|---|
| **> MAX_POSITIONS (5)** | 7 | 0 (0–35) | −1,123 (−1,397..−848) | −1.09 | **−7,859** (small n) |
| ≤ MAX_POSITIONS (5) | 28 | 35.7 (20.7–54.2) | −92 (−323..+117) | −0.16 | −2,564 |

Up to **10** stock positions were open at once, against `risk_rules.MAX_POSITIONS = 5`.
How it happened: `entries.py` checks `len(broker.positions())`, and that count
leaves out orders that are sent but not yet filled. On 09-09 the Minervini lane
(SM, NWL, SABR), the breakout lane (IBKR, CNQ, ZM, ASX) and the demand lane (ASML,
FSLR) all sent orders in the same minute, before any of them showed up as a
position. Each order had `size_multiplier 1.0` (streak 1), so each risked about
0.6–1.6% of equity, and every one of those entries was exposed to the same
opening-bell tape at the same time.

### By lane (sorted by $ lost)

| lane | n | win % (95% CI) | payoff | stop % | exp $ (95% CI) | exp R (95% CI) | total $ |
|---|---|---|---|---|---|---|---|
| minervini | 16 | 31.2 (14.2–55.6) | 0.68 | 31.2 | −318 (−700..+45) | −0.21 (−0.60..+0.20) | **−5,094** |
| breakout (zone) | 13 | 7.7 (1.4–33.3) | 0.98 | 61.5 | −361 (−767..−70) | **−0.70 (−1.04..−0.32)** | **−4,694** |
| demand_zone | 2 | 0 | – | 100 | −736 | −1.09 | −1,473 (small n) |
| zero_dte | 31 | 25.8 (13.7–43.2) | 2.51 | 74.2 | −17 (−112..+92) | −0.03 (−0.27..+0.23) | −513 |
| options_zone | 10 | 30.0 (10.8–60.3) | 1.66 | 70.0 | −33 (−153..+105) | −0.05 (−0.21..+0.14) | −325 |
| zone_edge (pre-tag breakout) | 4 | 100 | – | 0 | +209 | +0.62 | +838 (small n) |

Minervini by era: pre-reset (before 07-13) n=12, −$1,796, −0.09R; post-reset n=4,
**−$3,298, payoff 0.02** (small n). Signal kinds: `minervini:close_confirm` n=6,
average win $88 against an average loss of −$847 (payoff 0.10, small n).
`zone:breakout/broke` (breakout + zone_edge) n=17, −$3,856, −0.39R (CI −0.78..+0.04).

### By exit reason (stocks)

| exit | n | win % | exp $ | total $ |
|---|---|---|---|---|
| stop (bracket leg) | 14 | 0 | −674 (−958..−391), −1.04R | **−9,430** |
| watchdog stop (**no working broker stop**) | 1 | 0 | −2,435, −1.87R | −2,435 |
| broker market (unledgered) | 1 | 0 | −319 | −319 |
| distribution_exit (stage 3) | 11 | 36.4 | −16 | −174 |
| take_profit | 1 | 100 | +249 | +249 |
| flatten (manual / queue) | 3 | 100 | +275 | +826 |
| flatten_all | 4 | 50 | +215 | +860 |

Only **1 of 35** stock trades reached its target. Winners were closed early, by the
distribution exit or a flatten.

### Other cuts (descriptive; most CIs overlap)

- **Hold time:** trades held 1–3 days: n=14, **0 wins, −$7,816** (−0.64R, CI −0.89..−0.41).
  Same-day: n=44, −$1,581. 4–10 days: n=16, −$3,212. Over 10 days: n=2, +$1,348.
- **Session window** (autopsy `FIRST_MINUTES` / `LATE_MINUTES`): first 30 min n=49,
  **−$12,409** (−0.25R, CI −0.45..−0.04). Mid-session n=26, **+$1,213**
  (−0.04R, CI −0.34..+0.28).
- **App regime at entry (stocks):** "difficult" n=33, −$10,521. "normal" n=2.
- **SPY vs its 50/200-day averages:** above both n=67, −$10,352. Below the 50 n=9,
  −$909. A trending tape did not save these entries.
- **VIX (`iv_read.classify`):** normal n=59, −$11,027. Calm n=17, −$233.
- **Weekday:** Wed −$9,272 and Mon −$4,847 are the two cluster days. Not a weekday effect.
- **Price and cap terciles:** every tercile is negative and their CIs overlap. No
  size effect shows.

### Risk per trade (R)

| lane | mean R $ | mean R % equity | max R $ | mean loss in R | mean win in R |
|---|---|---|---|---|---|
| minervini | 992 | 0.99 | 1,596 | −0.66 | +0.77 |
| breakout | 430 | 0.44 | 1,300 | −0.83 | +0.87 |
| options_zone | 722 | 0.77 | 970 | −0.23 | +0.37 |
| zero_dte | 406 | 0.44 | 480 | −0.43 | +1.11 |

For the stock lanes, **the average win in R is about the same size as the average
loss**. The book's asymmetry (average win at least 2–3 times the average loss) is
not being produced.

## 3. Execution quality (stocks)

- **Entry slippage vs intended price:** +14 bps mean (CI −12..+38). Worst +198 bps
  (LUNR 14.94 vs 14.65).
- **Stops filled below the stop price:** −$1,986 in total. Two trades account for it:
  - **ASX −$1,135:** the watchdog found no working broker stop, and the exit filled
    4.81% under the stop. This is an execution failure.
  - **UFPT −$617:** filled 2.63% under the stop.
  - Every other stop filled within 0.5% of its level.
- **Fills vs band:** no breakout fill was more than `CHASE_BREAKOUT_PCT` (2%) above
  the band high. The highest were 1.73% (ASX) and 1.67% (AEIS).
- **Orders rejected:** 0. **Flatten-queue failures:** 3 × HTTP 403 (AEIS, APLD, LUNR,
  2026-09-06: shares held for orders). All three were later drained.
- **Duplicates:** no same-symbol, same-day stock trips. No 0DTE symbol was entered
  twice on the same day.
- **Alert gate / safety floors:** 0 entries recorded with `gate.ok = false`. 0 fills
  under `MIN_SHARE_PRICE`. 0 under `MIN_CAP_USD` where the cap was recorded.
  SABR was bought at $2.23, 11,043 shares, just above the $2 floor.
- **Stop distance vs ATR14:** 14 of 35 stops sat inside 1 ATR: −$2,314 (exp −$165,
  CI −413..+87). The other 21: −$8,109 (exp −$386, CI −731..−58). Wider stops did not
  lose less.
- **Position size:** 0 over `MAX_POSITION_FRACTION`. **7 entries over `MAX_POSITIONS`**
  (section 2).

## 4. Options

| | n | win % | payoff | exp $ (95% CI) | total $ |
|---|---|---|---|---|---|
| zero_dte | 31 | 25.8 (13.7–43.2) | 2.51 | −17 (−112..+92) | −513 |
| options_zone (28–60 DTE) | 10 | 30.0 (10.8–60.3) | 1.66 | −33 (−153..+105) | −325 |

- **0DTE, direction vs decay:** the delta × underlying-move part of the P&L sums to
  **−$728**. The residual (theta, spread and gamma) sums to **+$215**. The lane loses
  on **direction**, not on time decay. The underlying moved the way the trade needed
  in **10 of 31 (32.3%, CI 18.6–49.9)**.
- **0DTE exits:**
  - Premium stop at −50%: n=11, all losers, −$2,201.
  - Signal stop: n=12, all losers, −$1,882.
  - 2R stock target: n=5, +$2,240.
  - Premium +100%: n=3, +$1,330.
- **0DTE GEX regime:** PINNED n=16, −$1,425. AMPLIFYING n=15, +$912. Small n and the
  CIs overlap, so this is not a finding.
- **0DTE by underlying** (all small n): IWM n=8, +$1,058. SPY n=2, +$360.
  TSLA −$594. GOOGL −$578. QQQ −$407.
- **SPY in particular:** 6 SPY 0DTE orders, **4 never filled** (limit missed), 2
  filled. Across all symbols, 8 of 39 0DTE orders missed. The lane also skipped 57
  single-name attempts for "no same-day chain".
- **options_zone:**
  - Exits under the band-floor stop: 7, −$1,133.
  - Supply target reached: 3, +$808.
  - DTE at exit was 22–35 on every closed position, so time decay was small.
  - The lane mostly doesn't trade. Its dry-run blocks are led by "earnings inside the
    window" (958) and "underlying < $#" (866).

## 5. The 15 biggest losers (Rule #9)

Classes come from the owner rules in `trading/autopsy.classify`. "owner:" means a
stored `trade_autopsies` doc. "daily-approx" means `classify()` was run on
daily-bar MFE, because there is no minute-bar doc.

| # | trade | lane | $ | R | class | one line |
|---|---|---|---|---|---|---|
| 1 | ASX 09-09 | breakout | −2,435 | −1.87 | no_follow_through (daily-approx) | 09-09 cluster; no working broker stop, so the watchdog sold 4.8% under the stop; MFE +0.9% |
| 2 | CACC 07-06 | minervini | −1,593 | −1.00 | no_follow_through (daily-approx) | 07-06 cluster, 6th open position; MFE +1.4%, full stop |
| 3 | UFPT 07-06 | minervini | −1,583 | −1.64 | unclassified (daily-approx) | 07-06 cluster, 7th position; stop filled 2.6% through |
| 4 | NWL 09-09 | minervini | −1,449 | −1.03 | band_failed | 09-09 cluster, 10th position; closed 5.9% under the floor |
| 5 | SABR 09-09 | minervini | −989 | −0.75 | band_failed | 09-09 cluster; $2.23 stock, 11,043 shares |
| 6 | SM 09-09 | minervini | −884 | −0.56 | unclassified (daily-approx) | 09-09 cluster; MFE +7.5% given back, then the distribution exit |
| 7 | ASML 09-09 | demand_zone | −826 | −1.14 | band_failed | 09-09 cluster; demand band broke on day 1 |
| 8 | IBKR 09-09 | breakout | −772 | −1.04 | band_failed | 09-09 cluster; closed back under the broken lid |
| 9 | FSLR 09-09 | demand_zone | −646 | −1.04 | band_failed | 09-09 cluster; stopped in 10 minutes |
| 10 | ZM 09-09 | breakout | −626 | −1.00 | stop_clamped | 09-09 cluster; 1.72% stop clamped to 1.5%, stopped in 26 minutes |
| 11 | LAMR 07-06 | minervini | −436 | −0.29 | unclassified (daily-approx) | 07-06 cluster; closed by flatten_all at the reset |
| 12 | CNQ 09-09 | breakout | −319 | −0.28 | no_follow_through (daily-approx) | 09-09 cluster; closed by an unledgered market sell |
| 13 | HOOD 09-08 | breakout | −316 | −1.01 | band_failed | closed 5.6% under the broken lid on the same day |
| 14 | AMZN 0DTE 09-09 | zero_dte | −252 | −0.53 | wrong direction | put; the stock rose 0.22% |
| 15 | INTC opt 09-08 | options_zone | −245 | −0.25 | band-floor stop | long call; the underlying broke the band floor |

**Classes with 3 or more members:**

- **Opening-bell cluster over MAX_POSITIONS (analyst class):** 12 of 15
  (#1–12). This is the dominant class.
- **band_failed (owner):** 6 (NWL, SABR, ASML, IBKR, FSLR, HOOD).
- **no_follow_through (daily-approx):** 3 (ASX, CACC, CNQ).
- **unclassified (daily-approx):** 3 (UFPT, SM, LAMR).

Rule #9 → propose a rule: a **global in-flight position cap** that counts pending
entry orders as well as filled positions, and a **one-entry-per-tick opening
throttle**. This is **HIS call** (Rule #10). Nothing has been changed.

## 6. Signal vs execution — is the lane trading a measured edge?

| lane | live result | prior evidence for the ENTRY signal (memory/docs; not re-measured here) |
|---|---|---|
| minervini | −$5,094, −0.21R | **UNMEASURED.** There is no placebo study of the auto_entry trigger. Lid-break 57.5% vs 24–26% measures a touch of the prior high, not P&L |
| breakout / zone_edge | −$3,856, −0.39R | Zones beat SPY nowhere. The entry-trigger / ENTERABLE study found **no_signal** |
| demand_zone | −$1,473 (n=2) | Same-day demand alerts are a **coin flip**. Reversal-gate baseline: 24% win / 75% stop-out |
| options_zone | −$325 | Uses the same zone signal, so it inherits the null |
| zero_dte | −$513 | The signal_lab tags have **no placebo study**. ICT +0.03R (no edge). Raid-low no_signal |
| catalyst / hot_pullback | no fills | 8-K = volatility, not direction; promo INVERTED. Hot pullback is null |

**Every lane that traded is either unmeasured or trading a signal already measured
null.** The two measured positives (Gabbar levels, OOS 72% recovered vs 26% failed;
lid-break to prior high, distance decides) are not wired in as the entry for any lane.

## Not done / limits

- n is small everywhere. Most CIs cross zero except overall, stocks, breakout, stop
  exits, 1–3-day holds, first-30-min entries and the >MAX_POSITIONS bucket.
- MFE/MAE here come from daily bars. Only the 11 stored autopsy docs used minute
  bars.
- The VIX, SPY-trend and cap reads are taken at the prior close. The cap is the
  recorded zone cap, otherwise today's cap.
- No placebo is run in this script. The per-lane evidence is quoted, not re-measured.
- **Nothing** changes a live lane without Ajay's call. This is read-only.
