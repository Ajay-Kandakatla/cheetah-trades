# Green on a red day: measured 2026-09-28 (pre-registered rev 1)

**Status: MEASURED, `NO_SIGNAL` with no tags.** This is a Rule #10 research step. Nothing in the app changes: no surface, lane, gate, alert, sort, chip, rule line or newFeatures.ts entry.

- Frozen design: `docs/research/green_on_red_2026_09_28_prereg.md` (sha256 `0d3c1c6e…c44d2`), sections 3.2–3.15. It is not repeated here.
- Script: `backend/scripts/green_on_red_study.py` (sha256 `b3108d58…f14280`).
- Pins: `backend/tests/test_green_on_red_study_2026_09_28.py` (30 tests).
- Result: `backend/scripts/green_on_red_measured.json`. Every number below comes from that file.

## 1. The ask, verbatim

Ajay, Mon 2026-09-28, after the close:
> "I have a theory, Stocks that are green in this bearish day are lilly to be in high demand what are those? I saw Voyager is one of the,"

**Testable form (prereg §0):** take names that close green on a bearish day, on heavy volume and near the day's high. Buy them at the next session's open and hold 10 sessions. The theory predicts they beat RSP by more than same-day red-closing twins that looked the same the day before.

## 2. The answer

> Green on a red day (up on the day, ≥ $2, ≥ $10M traded, volume ≥ 1.5× its 50-day average, closed in the upper half of the day's range), bought at the next open and held 10 sessions: -0.30pp vs same-day red twins [-0.76, +0.15], +0.14pp vs RSP [-0.38, +0.71] — NO_SIGNAL. Measured from the signal-day close instead: -0.30pp. n = 4416 pairs on 78 red days (21 independent periods), 2025-01-10 → 2026-09-10.

In plain words:
- **The theory is not supported at this sample size.** The CI for the lift over the twins includes zero.
- Every point estimate below the primary is negative: both date halves, every drop-one block, one-per-symbol, the entry at the close, the cache universe and the house caliper. But the primary CI's upper end is +0.15pp, so the pre-registered rule does **not** read INVERTED. The mirror (a-) fails.
- The MDL at h10 is **0.65pp**. An edge smaller than about 0.65pp over 10 sessions, in either direction, cannot be detected with this data. This result is "not detectable at this n", not "proven zero".
- **What stays true:** the 56-name list answers "what are those?" as a watchlist. It is not a demand claim.

## 3. Sample

| item | value |
|---|---|
| AS_OF | 2026-09-28 (run 23:26 ET, outside the refusal window) |
| universe | `full` 2,730 → 2,712 after 18 ETFs/anchors; 2,708 with a cached frame |
| sessions | 500 (2024-09-30 → 2026-09-28); first eligible t = 64 = FIRST_T (2024-12-31) |
| red days scored | h5 78 · **h10 78** · h21 73 (80 red days from t ≥ 64, AS_OF included and never scored) |
| non-red / unclassified / SPY ≤ −0.5% days | 353 / 0 / 86 |
| S2 rows on red days | 5,425 (6 without features) |
| S1 rows on red days | 37,169 |
| twin pool rows on red days | 115,390 |
| primary pairs (h10-eligible) | 4,418; matched_share **0.815** (floor 0.80) |
| complete pairs at h10, next open | **4,416** (1 signal no-outcome, 1 signal glitch row) |
| clusters at h10 | red day 78 · `t//10` 38 · `t//21` **21** → G_min 21 (floor 20) |
| clusters at h21 | 73 · 20 · 20 → G_min 20, exactly the floor, so the CI is non-null |
| snapshot verify | ok, 5,617 names re-read, 0 moved |
| PIT check | 50 names, **0 mismatches** |
| peak RSS / wall | 1,578 MB / 24 s |

**Repro (his list):** 2026-09-28 is red (RSP −0.649%, breadth 0.297, 2,660 valid names). **S2 = 56 names, an exact match to the list he saw** (0 missing, 0 extra). 9 are leaders (ABUS, AMC, AMPH, ASC, CLMB, FDMT, IDT, KOD, XERS). VOYG is present.

**Balance (gated on the h10-eligible pairs, |SMD| < 0.1):** r21 +0.006, r63 +0.018, off52 −0.017, ldv20 −0.025, vol20 +0.065, beta63 −0.020, above50 0.000. The primary is **balanced**. Diagnostic (not gated, different by construction): day-t change 1.53, RVOL 0.89, close position 2.20, ln(close) 0.06.

## 4. Primary table (excess over RSP, pp; CI = widest of three groupings)

| h | entry | pairs | red days | signal excess [CI] | twin excess [CI] | **lift [CI]** | MDL |
|---|---|---|---|---|---|---|---|
| 5 | next open | 4,416 | 78 | +0.02 [−0.36, +0.44] | +0.29 [−0.05, +0.63] | −0.26 [−0.69, +0.10] | 0.57 |
| **10** | **next open (PRIMARY)** | **4,416** | **78** | **+0.14 [−0.38, +0.71]** | **+0.44 [+0.11, +0.81]** | **−0.30 [−0.76, +0.15]** | **0.65** |
| 21 | next open | 4,219 | 73 | +0.55 [−0.21, +1.28] | +0.85 [+0.06, +1.68] | −0.30 [−1.12, +0.54] | 1.19 |
| 5 | signal-day close | 4,416 | 78 | +0.06 [−0.34, +0.49] | +0.33 [+0.06, +0.65] | −0.27 [−0.71, +0.14] | 0.61 |
| 10 | signal-day close | 4,416 | 78 | +0.18 [−0.42, +0.78] | +0.48 [+0.13, +0.89] | −0.30 [−0.82, +0.17] | 0.71 |
| 21 | signal-day close | 4,219 | 73 | +0.62 [−0.26, +1.52] | +0.91 [+0.07, +1.78] | −0.29 [−1.12, +0.57] | 1.21 |

Per arm at h10, next open. Hit rate, the stop proxy (undercut) and MAE are shown beside the means; none is ranked on its own.

| arm | mean excess | median | trimmed mean | raw mean return | hit rate | undercut rate* | MAE p50 | MAE p90** |
|---|---|---|---|---|---|---|---|---|
| signal | +0.14 | −0.13 | −0.22 | +0.91 | 49.3% | 55.6% | −4.9% | −13.4% |
| twin | +0.44 | −0.08 | +0.07 | +1.21 | 49.6% | 80.6% | −4.4% | −12.5% |

\* Undercut = traded below the signal day's own low within the hold. It is descriptive, not a stop. The twin's reference low is its own red-day low, so the two rates are not like for like.
\** The 90th-percentile adverse excursion (the 10th percentile of the signed MAE).

## 5. Stability (h10, next open)

| check | value | positive criterion | mirror |
|---|---|---|---|
| (c) date halves | H1 −0.51 (2,271 pairs, → 2025-10-09) · H2 −0.07 (2,145, 2025-10-10 →) | fail | holds |
| (c2) drop one 21-session block | min −0.39 (block 17) · max −0.19 (block 21), 21 blocks | fail | holds |
| (d) one per symbol | −0.38 (1,903 pairs) | fail | holds |
| (e) entry at the signal-day close, same pairs | −0.30 | fail | holds |
| (f) cache universe (5,609 names, 1,864 ended, red days frozen) | −0.27 [−0.81, +0.21], 5,657 pairs, balanced | fail | holds |
| (f2) house caliper 0.4 | −0.38 [−0.89, +0.06], 3,329 pairs, balanced | fail | holds |

- **Verdict (mechanical, `verdict()`):** `no_signal`, tags none.
- Failed: a, b, c, c2, d, e, f, f2 and **a-**.
- Gates (g) and (k) hold.
- Every mirror stability check holds. Only (a-) fails: the primary CI's upper end is above zero. `inverted_fragile` needs (a-), so it is not set.
- The brief's own single-CI rule gives the same answer: neither lo > 0 nor hi < 0.

## 6. Secondary (labelled; the primary is not SIGNAL, so none of these is a finding)

| id | question | lift [CI] or value | n pairs | balanced / share |
|---|---|---|---|---|
| S1 | plain green, no volume/range filter | −0.15 [−0.51, +0.16] | 29,459 | yes / 0.798 |
| S3 | red-day lift minus non-red-day lift | −0.29 [−0.81, +0.23]; non-red lift −0.01 [−0.24, +0.25] | 29,004 non-red | yes / 0.696 |
| S4 | leaders vs rest | leaders −0.20 [−0.99, +0.60] (1,811); rest −0.37 [−1.05, +0.17] (2,605); difference +0.17 [−0.64, +1.08] | — | — |
| S5 | without > +20% event pops | −0.32 [−0.80, +0.12] | 4,344 | — |
| S6 | SPY ≤ −0.5% days only | −0.06 [−0.52, +0.35] | 5,674 | yes / 0.742 |
| S7 | S2 vs same-day S1-but-not-S2 (does the volume add anything?) | +0.22 [−0.21, +0.67] | 3,802 | yes / 0.702 |
| S8 | the app's $20M floor | −0.33 [−0.83, +0.13] | 3,966 | — |
| S9 | rev-0 match without beta | +0.00 [−0.54, +0.51]; beta63 SMD −0.166 (diagnostic) | 4,771 | yes / 0.881 |
| S10 | strict 252-bar lookback | +0.01, CI **n/a: 12 periods** | 2,091 | — |
| S11 | the 1,001 unmatched signals vs RSP (descriptive, no comparison) | +2.19 [−0.22, +4.73], n 997 | — | — |

- S9 is the beta confound the rev 1 match removed. Without beta in the match, the twins carry more market beta (SMD −0.166) and the lift reads +0.00. With beta matched, it reads −0.30. Neither CI excludes zero.
- S11 covers the ~18% of signals the matcher could not twin (the extremes). Their own mean vs RSP is wide and spans zero.

**Data audit:**
- |close-to-close| ≥ 40% inside the window: 22 signal rows, 18 twin rows of 4,416 (under 1%, so the T5 flag is not raised).
- Glitch rows excluded: 1 signal.
- Near the $2 floor ([$2, $4)): 41 signals, 54 twins (L9 proxy).

**Anecdote (not a measurement):**
- VOYG on 2026-09-28: +5.84%, RVOL 1.55, close position 0.88, S2, not a leader. Its features at t−1: below the 50-day, −40.2% off its high.
- It has **no** earlier S2-on-red rows in the scored window.

## 7. Deviations from the pre-registration (none touches the primary test)

1. **The pre-registration was committed AFTER a first, unstamped run — disclosed, not hidden.** The first full run (23:26 ET 2026-09-28) happened while the frozen prereg rev 1 was still untracked; that run carried `git_head` = the base commit `4395282` and pinned the frozen state by `script_sha256` and `prereg_doc_sha256` (the flag `--prereg-doc-sha256` and its JSON key were added for this). The main session then committed the byte-identical prereg (sha256 `0d3c1c6e…`) and re-ran the unchanged script (sha256 `b3108d58…`) at 23:43 ET, same AS_OF, with `--expect` for the repro check. **Every result field of the two runs is identical**; only `run_date`, `git_head` and the memory/wall readings differ. The committed JSON is the stamped re-run, and its `git_head` is the prereg commit.
2. `load_frames` returns a `FrameSet` (a dict subclass that carries `dup_day_keys` and digests). `run_study` takes two extra keywords: `verify_snapshot` (main injects the re-read) and `quiet`.
3. `off52_bars` is the count of finite highs in the lookback. S10 requires both members at 252.
4. `beta63` regresses the glitch-filtered day change on RSP's simple return.
5. `sample.etf_excluded` is split into top-level `universe_excluded` (18) and `sample.etf_excluded_present` (0 frames reached the panel).
6. Peak RSS was 1,578 MB, against a ~0.6 GB estimate. The cache-universe panel is the difference, and it has no effect on any number.
7. The script's design print gives 4,418 pairs and a share of 0.815. The planner probe gave 4,434 and 0.818, because it approximated the script. The §5 stop rule passed on the script's own print.

## 8. Limitations

L1 to L9 are as in the prereg §6. The ones that matter most here:
- **L2:** one ~20-month regime, 21 independent 21-session periods, MDL 0.65pp.
- **L1:** survivorship. The cache-universe check (f) agrees in sign.
- **L4:** the red-day thresholds come from the brief, not from him.
- **L8:** the study is not a trading rule.

## 9. HIS CALL

1. Nothing ships on this result. Per prereg §7-5, the 56-name list stays a watchlist answer.
2. If he wants a different definition before any re-run, each change is a new pre-registration: a "bearish day" definition, entry at the close, leaders only, or the $20M floor. None of the secondaries above is a finding.
