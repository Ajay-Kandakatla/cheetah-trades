# 🚩 Gajjala gates G1–G4: the pre-registered replay (2026-10-30 00:43 ET)

**Verdict: every gate is TOO SMALL to read (UNMEASURED).** Nothing ships to the paper lane from this run.

- Prereg: `2026-10-30_gajjala_gates_prereg.md` sha256 `4ebc30d20e7f3eb19aa6df5fbe2b620d9c19e0e22144ae6620e66ca7bf8d14b6` (frozen before this run). Script `backend/scripts/gajjala_gates_study_2026_10_30.py` sha256 `e308ab74f8cced519e61029fbb19a795de382c9a6d8e84eb0339bb2a27dfff08`, worktree HEAD `380eb7c13c380ae6de3bf898840e058b59d3c0ef`.
- Run 2026-10-30 00:43:25 ET, outside 09:30–16:00 ET; a throwaway container, Mongo read-only handles, no broker import (display-only price-grid stub), bars = the app's intraday_cache; 3 symbol-day(s) the cache lacks read once through the study's as-printed GET, never written: PRCH 2026-10-29, CRIS 2026-10-29, INLF 2026-10-29.
- Cohort: 35 A+ rows that rang (28 live 🏁 rows, 7 ⏪ replay rows); 26 filled trades; 0 trades not judgeable (none) — out of every trial and the baseline; **26 trades read**.
- Split (the lab's last-third rule over 11 sessions): in-sample 2026-10-09…2026-10-23 (7 sessions, 21 trades); out-of-sample 2026-10-26…2026-10-29 (4 sessions, 5 trades, 1 entry week(s)).
- R = the 🏁 grade's same-session math minus 10 bps per side. Baseline (no gate): in-sample mean 0.027 R; OOS mean -0.664 R, no interval (1 entry week).
- **N honestly: 5 OOS trades in 1 entry week(s), against the lab's 30-week floor.** A CI over fewer than 30 weeks is not an interval anyone should read.

## Per gate

| gate | in-sample pick (IS n · IS mean R) | OOS n (weeks) | OOS mean R | 95% CI (entry weeks) | baseline OOS mean R | placebo beat | DSR (N 14) | POSITIVE | SHIP |
|---|---|---|---|---|---|---|---|---|---|
| G1 break-bar proof (close > trigger, vol ≥ k × base mean) | k=2 (2 · 0.401) | 4 (1) | -0.470 | no interval (1 entry week) | -0.664 | 0.597 | 0.106 | **TOO SMALL = UNMEASURED** | **UNMEASURED (rule alone: OFF)** |
| G2 red closes (≤ 3 in a row) | max_red=3 (18 · -0.060) | 4 (1) | -0.531 | no interval (1 entry week) | -0.664 | 0.391 | 0.099 | **TOO SMALL = UNMEASURED** | **UNMEASURED (rule alone: OFF)** |
| G3 stale / missed at the tick (age ≤ m min, fill ≤ trigger + MISSED_R × R) | m=30, missed_r=0.5 (11 · -0.267) | 3 (1) | -0.558 | no interval (1 entry week) | -0.664 | 0.595 | 0.165 | **TOO SMALL = UNMEASURED** | **UNMEASURED (rule alone: OFF)** |
| G4 stop-distance cap (risk ≤ c %, 🎾 stop frozen at the first armed read) | c=10 (20 · 0.103) | 5 (1) | -0.664 | no interval (1 entry week) | -0.664 | 0.000 | 0.052 | **TOO SMALL = UNMEASURED** | **UNMEASURED (rule alone: OFF)** |
| Combined (every gate's in-sample pick) | G1 k=2 · G2 max_red=3 · G3 m=30, missed_r=0.5 · G4 c=10 (2 · 0.401) | 1 (1) | 0.965 | no interval (1 entry week) | -0.664 | 0.804 | — | **TOO SMALL = UNMEASURED** | **UNMEASURED (rule alone: SHIP)** |

POSITIVE = the strategy lab's A + B + C (95% placebo, DSR ≥ 0.95); TOO SMALL under 30 OOS entry weeks. SHIP = the prereg's weaker rule (OOS mean ≥ baseline AND placebo beat ≥ 80%); UNMEASURED under 30 OOS entry weeks, the rule's mechanical answer beside it. DSR: PSR of the pick's OOS per-trade R against LAB.dsr_sr0 of the 14 trials' in-sample per-trade Sharpes (12 finite).

## Per trial (in-sample; OOS sealed except the picks)

| trial | params | IS n pass / cohort | IS mean net R | IS SR | picked |
|---|---|---|---|---|---|
| G1_k1 | k=1 | 7 / 21 | -0.601 | -0.504 |  |
| G1_k1.5 | k=1.5 | 3 / 21 | -0.128 | -0.121 |  |
| G1_k2 | k=2 | 2 / 21 | 0.401 | — | yes |
| G2_red3 | max_red=3 | 18 / 21 | -0.060 | -0.053 | yes |
| G3_m10_mr0.5 | m=10, missed_r=0.5 | 8 / 21 | -0.454 | -0.453 |  |
| G3_m10_mr1 | m=10, missed_r=1 | 10 / 21 | -0.458 | -0.411 |  |
| G3_m20_mr0.5 | m=20, missed_r=0.5 | 10 / 21 | -0.380 | -0.377 |  |
| G3_m20_mr1 | m=20, missed_r=1 | 12 / 21 | -0.395 | -0.359 |  |
| G3_m30_mr0.5 | m=30, missed_r=0.5 | 11 / 21 | -0.267 | -0.260 | yes |
| G3_m30_mr1 | m=30, missed_r=1 | 13 / 21 | -0.299 | -0.269 |  |
| G4_c8 | c=8 | 19 / 21 | 0.057 | 0.054 |  |
| G4_c10 | c=10 | 20 / 21 | 0.103 | 0.098 | yes |
| G4_c12 | c=12 | 20 / 21 | 0.103 | 0.098 |  |
| COMBINED | G1 k=2 · G2 max_red=3 · G3 m=30, missed_r=0.5 · G4 c=10 | 2 / 21 | 0.401 | — | yes |

## Run history

- **Run 1, 2026-10-30 00:41 ET (DEFECTIVE, kept in `run1_defective_0041/`, not the result).** Two defects found on reading its output: (1) the split was taken over the *judgeable trades'* sessions (9) instead of every cohort session (11), so 10-23 landed out-of-sample and 10-26 in-sample; (2) the three 10-29 trades (PRCH, CRIS, INLF, all losses) had no minutes in intraday_cache (the 20:15 nightly grades the live session off a fetch that is never cached) and were dropped, which flattered the out-of-sample baseline (-0.232 R on 3 trades). Its verdicts were the same words: every gate TOO SMALL / UNMEASURED.
- **Run 2, 2026-10-30 00:43 ET (this report).** Fixes only those two defects: the split over all 11 cohort sessions (prereg "sessions ordered by date"), and the three missing symbol-days read once through the study's as-printed GET (never written). No variant, threshold or rule changed between the runs. The out-of-sample window was therefore read twice; with 1 entry week the read is UNMEASURED either way, so the second read cannot have moved a verdict word.
- Numbers come from script sha256 `e308ab74…dfff08` (run 2). The file was then edited only to print a one-week CI as "no interval" and to re-render these files from `results.json` (`--render-only`, no data read).

## Judgement calls and caveats

- G2 reads the detectors' own `red_closes` (the longest run among the pullback / base bars — the RED_CLOSES_MODE 'criterion' engine). The prereg says 'the base's last run'; on the trades read, the two readings disagree on **4** trade(s).
- G3's tick = the 🏁 grader's fill minute (the lane enters at the first tick the tape trades the trigger); the price at the tick = the grader's fill price. Ring age = whole minutes, floor (LG._whole_min).
- G4 is a filter only; on 🎾 the cap reads the stop of the first armed read (10 of 10 🎾 trades had one with the alert's trigger; the rest read the alert's stop). The trade's stop and R stay the alert's.
- G1: a break with no base bars reads 'no proof' (not passed): 0 trade(s).
- In-sample pick = the highest in-sample mean net R; ties → prereg order.
- The live 🏁 grades were made at the 20:15 ET nightly on the live minute fetch; the gate inputs are re-read on the intraday_cache copy of those minutes with TODAY's detectors.
- The study cache named in the run brief was not used: its scratch directory is gone (empty); the replay rows carry their own stored grades.

