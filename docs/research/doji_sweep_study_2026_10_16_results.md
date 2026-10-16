# 🕯️ Doji Sweep study — RESULTS (2026-10-16)

The one pre-registered outcome run. The pre-registration is `docs/research/doji_sweep_study_2026_10_16.md` and is not
edited (its git blob still equals the artifact's `prereg_blob`, pinned by `backend/tests/test_doji_sweep_study.py`).
Every number below is copied from the artifact `backend/scripts/doji_sweep_measured.json` by a one-off script — none
retyped, none rounded again.

## The run

| field | value |
|---|---|
| run date | 2026-10-16 |
| as of | 2026-10-15 |
| head (the run's worktree) | `2845fe2458bdead69d1db1c2b96245e80f4d6b06` (git source: attested, porcelain empty: True) |
| prereg commit | `2845fe2458bdead69d1db1c2b96245e80f4d6b06` |
| prereg blob | `77cd374b966631fbb95bc9e60231e912bff76c3b` |
| event window | 2025-10-10 → 2026-10-15 (255 sessions) |
| cohort | survivors-only |
| universe / with bars / eligible | 2699 / 2699 / 2623 |
| provider calls | 0 |
| script | `backend/scripts/doji_sweep_study.py` |

## Verdict in plain words

- **The primary (60%+ under the 52-week high) reads `no_signal`** — -3.85 pp net of SPY,
  CI by 10-session block [-7.23, 0.72], by name [-6.41, 0.68] (98.33%).
- **The control (a test of the low without a doji) reads `no_signal`** — 0.17 pp,
  [-2.07, 2.88] / [-1.09, 2.0] (95.0%).
- **The any-read cell reads `axes_disagree`** — its two bootstrap axes disagree: by 10-session block
  [-1.75, 0.68] spans zero, by name [-0.89, -0.13] does not (97.5%). A verdict needs both, so
  it is a null.
- **None of the three is an edge.** The tab stays a scanner, not an entry.
- About one year of events (255 sessions, 2025-10-10 → 2026-10-15) although
  the cached bars span about two years: the 52-week read needs a year of history before the first event. One market
  regime.
- Survivors-only names: today's list; names that fell hard and delisted are absent.

## Limits (the artifact's `limits`, verbatim)

- survivors-only: the universe is today's list — deep-drawdown names that delisted are absent; absolute returns are biased up, and the same-name matched days only partly cancel it
- the two-year price cache gives about one year of evaluable sessions (a 252-session window first) — one market regime
- adjacent events' outcome windows overlap; the session-block and the by-name resampling keep them together, they do not remove the overlap
- the all-time high before the stored high's month is the frame's running max — a lower bound, so a name may be missed, never falsely included; the misses are not random — a name that later set a new all-time high (the later big runners) gets only the frame read, so it is under-included in the ath and any_read cells
- next-open entries assume the open print; close-to-close daily bars, no intraday fill is modelled
- the sizing probe says about 90% of his tests never undercut the prior low — the undercut cells are thin

## The three pre-registered verdict cells

The words are the ones the tab serves (`doji_sweep_tab._verdict_words()` = W31; `axes_disagree` is served as the
null-with-axes-disagree sentence per AMENDMENTS6 B2; the control's served sentence is
`doji_sweep_tab.CONTRAST_WORDS`). The verdict uses the market-adjusted read; Holm-corrected across the three.

### `primary` — Primary — 60%+ under the 52-week high

| field | value |
|---|---|
| key | `primary` |
| label | Primary — 60%+ under the 52-week high |
| definition | a body under 5% of the range, the low within 5% either side of the prior 20-session low (set 4+ sessions before), the $10M/day floor, 60%+ under the 52-week high (his "60% 70%"); next open, 10 sessions, net of SPY |
| n_events | 145 |
| n_dates | 98 |
| n_symbols | 102 |
| median diff (pp, raw) | -3.1 |
| CI by 10-session block (raw) | [-7.62, 2.4] |
| CI by name (raw) | [-7.51, 1.9] |
| market-adjusted median diff (pp) | -3.85 |
| market-adjusted CI by 10-session block | [-7.23, 0.72] |
| market-adjusted CI by name | [-6.41, 0.68] |
| CI level (%) | 98.33 |
| verdict | `no_signal` |
| pre-registered words (W31, as doji_sweep_tab serves them) | no difference this study can separate from zero |
| served words | no difference this study can separate from zero |
| Holm p | 0.129 |
| confirm vs placebo (%) | 46.36 vs 47.68 |
| stop vs placebo (%) | 78.62 vs 66.76 |

### `any_read` — Any downtrend read (the tab's default view)

| field | value |
|---|---|
| key | `any_read` |
| label | Any downtrend read (the tab's default view) |
| definition | a body under 5% of the range, the low within 5% either side of the prior 20-session low (set 4+ sessions before), the $10M/day floor, any of 60%+ under the 52-week high, 60%+ under the all-time high, or below the 50- and 200-day |
| n_events | 2802 |
| n_dates | 242 |
| n_symbols | 1218 |
| median diff (pp, raw) | -0.38 |
| CI by 10-session block (raw) | [-1.48, 0.82] |
| CI by name (raw) | [-0.74, -0.02] |
| market-adjusted median diff (pp) | -0.5 |
| market-adjusted CI by 10-session block | [-1.75, 0.68] |
| market-adjusted CI by name | [-0.89, -0.13] |
| CI level (%) | 97.5 |
| verdict | `axes_disagree` |
| pre-registered words (W31, as doji_sweep_tab serves them) | no verdict — the session-block CI and the by-name CI disagree (AMENDMENTS6: a verdict needs both) |
| served words | no verdict — the session-block CI and the by-name CI disagree (AMENDMENTS6: a verdict needs both) |
| Holm p | 0.612 |
| confirm vs placebo (%) | 47.28 vs 45.29 |
| stop vs placebo (%) | 69.49 vs 65.69 |

### `test_no_doji` — The control — a test of the low without a doji

| field | value |
|---|---|
| key | `test_no_doji` |
| label | The control — a test of the low without a doji |
| definition | a body of 10% of the range or more, the same test, floor and 52-week read as the primary, against its own matched days |
| n_events | 2563 |
| n_dates | 241 |
| n_symbols | 226 |
| median diff (pp, raw) | 0.96 |
| CI by 10-session block (raw) | [-2.12, 4.13] |
| CI by name (raw) | [-0.87, 2.97] |
| market-adjusted median diff (pp) | 0.17 |
| market-adjusted CI by 10-session block | [-2.07, 2.88] |
| market-adjusted CI by name | [-1.09, 2.0] |
| CI level (%) | 95.0 |
| verdict | `no_signal` |
| pre-registered words (W31, as doji_sweep_tab serves them) | no difference this study can separate from zero |
| served words | the tests without a doji show no difference from their matched days that this study can separate from zero |
| Holm p | 0.832 |
| confirm vs placebo (%) | 37.16 vs 41.41 |
| stop vs placebo (%) | 74.76 vs 72.88 |

## exploratory — no verdict

Every other cell: numbers only, never a verdict word (AMENDMENTS6 B6). `w52_70` was pre-declared too small (B4).

### `w52_40` — 40%+ under the 52-week high

| field | value |
|---|---|
| key | `w52_40` |
| label | 40%+ under the 52-week high |
| definition | any_read and 40%+ under the 52-week high |
| n_events | 643 |
| n_dates | 211 |
| n_symbols | 402 |
| median diff (pp, raw) | -0.01 |
| CI by 10-session block (raw) | [-1.73, 1.89] |
| CI by name (raw) | [-0.93, 1.3] |
| market-adjusted median diff (pp) | -0.09 |
| market-adjusted CI by 10-session block | [-1.45, 1.65] |
| market-adjusted CI by name | [-1.1, 1.03] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 45.68 vs 44.43 |
| stop vs placebo (%) | 72.94 vs 68.55 |

### `w52_70` — 70%+ under the 52-week high (pre-declared too small)

| field | value |
|---|---|
| key | `w52_70` |
| label | 70%+ under the 52-week high (pre-declared too small) |
| definition | any_read and 70%+ under the 52-week high |
| n_events | 53 |
| n_dates | 47 |
| n_symbols | 40 |
| median diff (pp, raw) | -1.36 |
| CI by 10-session block (raw) | [-5.94, 3.7] |
| CI by name (raw) | [-7.17, 4.59] |
| market-adjusted median diff (pp) | -1.98 |
| market-adjusted CI by 10-session block | [-5.84, 1.35] |
| market-adjusted CI by name | [-6.92, 2.98] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 42.59 vs 40.0 |
| stop vs placebo (%) | 83.02 vs 71.7 |

### `ath_60` — 60%+ under the all-time high

| field | value |
|---|---|
| key | `ath_60` |
| label | 60%+ under the all-time high |
| definition | any_read and the all-time-high read |
| n_events | 1027 |
| n_dates | 235 |
| n_symbols | 448 |
| median diff (pp, raw) | -0.41 |
| CI by 10-session block (raw) | [-1.7, 0.81] |
| CI by name (raw) | [-1.19, 0.16] |
| market-adjusted median diff (pp) | -0.73 |
| market-adjusted CI by 10-session block | [-1.75, 0.28] |
| market-adjusted CI by name | [-1.25, -0.11] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 48.1 vs 46.09 |
| stop vs placebo (%) | 69.62 vs 65.59 |

### `mas` — Below the 50- and 200-day

| field | value |
|---|---|
| key | `mas` |
| label | Below the 50- and 200-day |
| definition | any_read and the averages read |
| n_events | 2359 |
| n_dates | 241 |
| n_symbols | 1104 |
| median diff (pp, raw) | -0.46 |
| CI by 10-session block (raw) | [-1.55, 0.84] |
| CI by name (raw) | [-0.8, -0.09] |
| market-adjusted median diff (pp) | -0.47 |
| market-adjusted CI by 10-session block | [-1.67, 0.66] |
| market-adjusted CI by name | [-0.88, -0.12] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 46.95 vs 45.22 |
| stop vs placebo (%) | 70.62 vs 65.71 |

### `mas_only` — Below the averages only

| field | value |
|---|---|
| key | `mas_only` |
| label | Below the averages only |
| definition | any_read whose ONLY read is the averages |
| n_events | 1775 |
| n_dates | 238 |
| n_symbols | 815 |
| median diff (pp, raw) | -0.37 |
| CI by 10-session block (raw) | [-1.45, 0.88] |
| CI by name (raw) | [-0.73, 0.01] |
| market-adjusted median diff (pp) | -0.4 |
| market-adjusted CI by 10-session block | [-1.59, 0.9] |
| market-adjusted CI by name | [-0.85, -0.02] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 46.81 vs 44.83 |
| stop vs placebo (%) | 69.41 vs 65.75 |

### `doji10` — Body under 10%

| field | value |
|---|---|
| key | `doji10` |
| label | Body under 10% |
| definition | the any_read rule at a body under 10% of the range |
| n_events | 5578 |
| n_dates | 242 |
| n_symbols | 1534 |
| median diff (pp, raw) | -0.31 |
| CI by 10-session block (raw) | [-1.39, 0.84] |
| CI by name (raw) | [-0.56, -0.04] |
| market-adjusted median diff (pp) | -0.34 |
| market-adjusted CI by 10-session block | [-1.41, 0.65] |
| market-adjusted CI by name | [-0.6, -0.09] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 47.28 vs 45.74 |
| stop vs placebo (%) | 70.06 vs 65.81 |

### `above` — Low at or above the prior low

| field | value |
|---|---|
| key | `above` |
| label | Low at or above the prior low |
| definition | any_read and the low at or above the prior low (0 … +5%) |
| n_events | 2517 |
| n_dates | 242 |
| n_symbols | 1148 |
| median diff (pp, raw) | -0.36 |
| CI by 10-session block (raw) | [-1.38, 0.67] |
| CI by name (raw) | [-0.72, -0.06] |
| market-adjusted median diff (pp) | -0.51 |
| market-adjusted CI by 10-session block | [-1.61, 0.63] |
| market-adjusted CI by name | [-0.87, -0.17] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 46.94 vs 45.2 |
| stop vs placebo (%) | 70.12 vs 65.92 |

### `undercut` — Undercut the prior low

| field | value |
|---|---|
| key | `undercut` |
| label | Undercut the prior low |
| definition | any_read and the low under the prior low (−5% … 0) |
| n_events | 285 |
| n_dates | 136 |
| n_symbols | 267 |
| median diff (pp, raw) | -0.62 |
| CI by 10-session block (raw) | [-2.36, 1.26] |
| CI by name (raw) | [-2.02, 0.81] |
| market-adjusted median diff (pp) | -0.23 |
| market-adjusted CI by 10-session block | [-1.41, 1.07] |
| market-adjusted CI by name | [-1.4, 1.03] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 50.35 vs 46.11 |
| stop vs placebo (%) | 63.86 vs 63.65 |

### `undercut_reclaimed` — Undercut and reclaimed

| field | value |
|---|---|
| key | `undercut_reclaimed` |
| label | Undercut and reclaimed |
| definition | any_read, the low under the prior low and the close back above it |
| n_events | 237 |
| n_dates | 126 |
| n_symbols | 228 |
| median diff (pp, raw) | -1.34 |
| CI by 10-session block (raw) | [-2.94, 0.48] |
| CI by name (raw) | [-2.62, 0.21] |
| market-adjusted median diff (pp) | -0.52 |
| market-adjusted CI by 10-session block | [-1.91, 0.95] |
| market-adjusted CI by name | [-1.77, 0.88] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 51.46 vs 47.11 |
| stop vs placebo (%) | 64.56 vs 62.87 |

### `undercut_closed_under` — Undercut, closed under

| field | value |
|---|---|
| key | `undercut_closed_under` |
| label | Undercut, closed under |
| definition | any_read, the low under the prior low and the close not above it |
| n_events | 48 |
| n_dates | 40 |
| n_symbols | 47 |
| median diff (pp, raw) | 2.22 |
| CI by 10-session block (raw) | [-0.86, 4.05] |
| CI by name (raw) | [-0.47, 4.11] |
| market-adjusted median diff (pp) | 1.88 |
| market-adjusted CI by 10-session block | [-1.79, 4.46] |
| market-adjusted CI by name | [-1.66, 4.58] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 44.9 vs 41.22 |
| stop vs placebo (%) | 60.42 vs 67.5 |

### `undercut_deep` — Undercut by more than 5% (outside his test)

| field | value |
|---|---|
| key | `undercut_deep` |
| label | Undercut by more than 5% (outside his test) |
| definition | a doji (5%), the prior low 4+ sessions old, the low more than 5% under it, any read, the floor |
| n_events | 35 |
| n_dates | 31 |
| n_symbols | 35 |
| median diff (pp, raw) | -1.98 |
| CI by 10-session block (raw) | [-7.63, 1.51] |
| CI by name (raw) | [-6.66, 0.25] |
| market-adjusted median diff (pp) | -1.8 |
| market-adjusted CI by 10-session block | [-4.44, 1.33] |
| market-adjusted CI by name | [-4.37, 0.87] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 43.24 vs 46.49 |
| stop vs placebo (%) | 54.29 vs 57.14 |

### `swing_sweep` — The smc swing-low sweep (Q4)

| field | value |
|---|---|
| key | `swing_sweep` |
| label | The smc swing-low sweep (Q4) |
| definition | a doji (5%), any read, the floor, and a sell-side sweep of a swing low (window 3, lookback 60) on the candle |
| n_events | 2386 |
| n_dates | 242 |
| n_symbols | 1174 |
| median diff (pp, raw) | -0.44 |
| CI by 10-session block (raw) | [-1.62, 0.97] |
| CI by name (raw) | [-0.86, -0.07] |
| market-adjusted median diff (pp) | -0.29 |
| market-adjusted CI by 10-session block | [-1.35, 0.86] |
| market-adjusted CI by name | [-0.76, 0.13] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 48.57 vs 45.21 |
| stop vs placebo (%) | 68.73 vs 67.43 |

### `dragonfly` — Dragonfly doji

| field | value |
|---|---|
| key | `dragonfly` |
| label | Dragonfly doji |
| definition | any_read and the dragonfly shape |
| n_events | 184 |
| n_dates | 110 |
| n_symbols | 170 |
| median diff (pp, raw) | -0.58 |
| CI by 10-session block (raw) | [-2.38, 1.47] |
| CI by name (raw) | [-2.08, 0.68] |
| market-adjusted median diff (pp) | -0.2 |
| market-adjusted CI by 10-session block | [-1.31, 0.85] |
| market-adjusted CI by name | [-1.49, 1.15] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 62.83 vs 47.64 |
| stop vs placebo (%) | 53.26 vs 66.85 |

### `gravestone` — Gravestone doji

| field | value |
|---|---|
| key | `gravestone` |
| label | Gravestone doji |
| definition | any_read and the gravestone shape |
| n_events | 255 |
| n_dates | 128 |
| n_symbols | 226 |
| median diff (pp, raw) | -0.68 |
| CI by 10-session block (raw) | [-2.11, 0.1] |
| CI by name (raw) | [-1.89, 0.0] |
| market-adjusted median diff (pp) | -1.83 |
| market-adjusted CI by 10-session block | [-3.18, -0.32] |
| market-adjusted CI by name | [-2.61, -0.75] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 30.77 vs 43.08 |
| stop vs placebo (%) | 81.96 vs 66.35 |

### `long_legged` — Long-legged doji

| field | value |
|---|---|
| key | `long_legged` |
| label | Long-legged doji |
| definition | any_read and the long-legged shape |
| n_events | 576 |
| n_dates | 189 |
| n_symbols | 467 |
| median diff (pp, raw) | -0.44 |
| CI by 10-session block (raw) | [-1.97, 1.0] |
| CI by name (raw) | [-1.24, 0.36] |
| market-adjusted median diff (pp) | -0.7 |
| market-adjusted CI by 10-session block | [-2.25, 0.42] |
| market-adjusted CI by name | [-1.51, -0.02] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 44.01 vs 45.43 |
| stop vs placebo (%) | 64.24 vs 64.06 |

### `plain` — Plain doji

| field | value |
|---|---|
| key | `plain` |
| label | Plain doji |
| definition | any_read and no named shape |
| n_events | 1787 |
| n_dates | 239 |
| n_symbols | 981 |
| median diff (pp, raw) | -0.27 |
| CI by 10-session block (raw) | [-1.27, 1.1] |
| CI by name (raw) | [-0.62, 0.1] |
| market-adjusted median diff (pp) | -0.26 |
| market-adjusted CI by 10-session block | [-1.33, 0.98] |
| market-adjusted CI by name | [-0.69, 0.12] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 49.05 vs 45.31 |
| stop vs placebo (%) | 71.07 vs 66.0 |

### `vol_quiet` — Quiet volume

| field | value |
|---|---|
| key | `vol_quiet` |
| label | Quiet volume |
| definition | any_read and volume at or under 1× the 50-day average |
| n_events | 1862 |
| n_dates | 241 |
| n_symbols | 1005 |
| median diff (pp, raw) | -0.26 |
| CI by 10-session block (raw) | [-1.44, 0.94] |
| CI by name (raw) | [-0.66, 0.12] |
| market-adjusted median diff (pp) | -0.54 |
| market-adjusted CI by 10-session block | [-1.6, 0.49] |
| market-adjusted CI by name | [-1.02, -0.16] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 47.0 vs 44.86 |
| stop vs placebo (%) | 71.0 vs 66.31 |

### `vol_heavy` — Heavy volume

| field | value |
|---|---|
| key | `vol_heavy` |
| label | Heavy volume |
| definition | any_read and volume at 1.5× the 50-day average or more |
| n_events | 251 |
| n_dates | 126 |
| n_symbols | 226 |
| median diff (pp, raw) | -0.43 |
| CI by 10-session block (raw) | [-1.32, 1.21] |
| CI by name (raw) | [-1.2, 0.76] |
| market-adjusted median diff (pp) | -0.27 |
| market-adjusted CI by 10-session block | [-2.06, 1.57] |
| market-adjusted CI by name | [-1.38, 0.73] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 49.61 vs 44.65 |
| stop vs placebo (%) | 63.75 vs 65.1 |

### `doji_no_test` — A doji, no test

| field | value |
|---|---|
| key | `doji_no_test` |
| label | A doji, no test |
| definition | a doji (5%), the prior low 4+ sessions old, the low more than 5% above it, any read, the floor |
| n_events | 4486 |
| n_dates | 242 |
| n_symbols | 1232 |
| median diff (pp, raw) | 0.15 |
| CI by 10-session block (raw) | [-0.88, 1.26] |
| CI by name (raw) | [-0.28, 0.55] |
| market-adjusted median diff (pp) | 0.28 |
| market-adjusted CI by 10-session block | [-0.69, 1.25] |
| market-adjusted CI by name | [-0.2, 0.7] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 43.86 vs 44.08 |
| stop vs placebo (%) | 73.29 vs 69.02 |

### `independent` — One per name per 10 sessions

| field | value |
|---|---|
| key | `independent` |
| label | One per name per 10 sessions |
| definition | any_read, greedy in date order: an event within 10 sessions after a kept one of the same name is dropped |
| n_events | 2317 |
| n_dates | 240 |
| n_symbols | 1215 |
| median diff (pp, raw) | -0.55 |
| CI by 10-session block (raw) | [-1.62, 0.58] |
| CI by name (raw) | [-0.84, -0.19] |
| market-adjusted median diff (pp) | -0.58 |
| market-adjusted CI by 10-session block | [-1.73, 0.48] |
| market-adjusted CI by name | [-0.98, -0.24] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 47.63 vs 45.68 |
| stop vs placebo (%) | 70.35 vs 65.51 |

### `all_liquidity` — No liquidity floor

| field | value |
|---|---|
| key | `all_liquidity` |
| label | No liquidity floor |
| definition | the any_read rule without the floor (placebos without it too) |
| n_events | 3612 |
| n_dates | 242 |
| n_symbols | 1515 |
| median diff (pp, raw) | -0.3 |
| CI by 10-session block (raw) | [-1.2, 0.8] |
| CI by name (raw) | [-0.58, -0.04] |
| market-adjusted median diff (pp) | -0.34 |
| market-adjusted CI by 10-session block | [-1.39, 0.7] |
| market-adjusted CI by name | [-0.63, -0.04] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 47.22 vs 45.61 |
| stop vs placebo (%) | 68.58 vs 65.36 |

### `from_close` — Entry at the doji close

| field | value |
|---|---|
| key | `from_close` |
| label | Entry at the doji close |
| definition | any_read; the return from the doji's own close |
| n_events | 2802 |
| n_dates | 242 |
| n_symbols | 1218 |
| median diff (pp, raw) | -0.37 |
| CI by 10-session block (raw) | [-1.45, 0.89] |
| CI by name (raw) | [-0.65, -0.01] |
| market-adjusted median diff (pp) | -0.6 |
| market-adjusted CI by 10-session block | [-1.49, 0.59] |
| market-adjusted CI by name | [-0.9, -0.21] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 47.28 vs 45.29 |
| stop vs placebo (%) | 69.49 vs 65.69 |

### `confirm_entry` — Entry at the confirming close

| field | value |
|---|---|
| key | `confirm_entry` |
| label | Entry at the confirming close |
| definition | any_read events that closed above the doji's high within 5 sessions; the return from that close (placebos conditioned the same way) |
| n_events | 1182 |
| n_dates | 235 |
| n_symbols | 775 |
| median diff (pp, raw) | -0.42 |
| CI by 10-session block (raw) | [-1.85, 0.61] |
| CI by name (raw) | [-1.01, 0.22] |
| market-adjusted median diff (pp) | -0.31 |
| market-adjusted CI by 10-session block | [-1.61, 0.9] |
| market-adjusted CI by name | [-0.86, 0.3] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 100.0 vs 100.0 |
| stop vs placebo (%) | 45.18 vs 36.61 |

### `test_no_doji_fire_pool` — The control against the primary's pool (a sensitivity)

| field | value |
|---|---|
| key | `test_no_doji_fire_pool` |
| label | The control against the primary's pool (a sensitivity) |
| definition | the test_no_doji events, their matched days drawn from the primary's pool rule (the fire-based exclusions only, without the control's own-event exclusion) — numbers only, never compared with the primary as a verdict |
| n_events | 3057 |
| n_dates | 241 |
| n_symbols | 260 |
| median diff (pp, raw) | -0.85 |
| CI by 10-session block (raw) | [-3.89, 2.55] |
| CI by name (raw) | [-2.03, 0.22] |
| market-adjusted median diff (pp) | -0.95 |
| market-adjusted CI by 10-session block | [-3.15, 1.61] |
| market-adjusted CI by name | [-1.85, -0.13] |
| CI level (%) | 95.0 |
| verdict | exploratory — no verdict |
| confirm vs placebo (%) | 37.49 vs 44.74 |
| stop vs placebo (%) | 74.45 vs 68.38 |

## The served line (verbatim, `DJ.study_block()` from the api image on this worktree)

```json
{"status": "measured", "text": "🕯️ MEASURED 2026-10-16 (prereg 2845fe2458bdead69d1db1c2b96245e80f4d6b06, survivors-only, candles 2025-10-10 to 2026-10-15): 145 dojis testing the prior low 60%+ under the 52-week high, on 98 sessions across 102 names. Bought at the next open and held 10 sessions, net of SPY over the same sessions: median −3.32% against +0.54% on 770 matched days of the same names in the same downtrend (13 with a short placebo pool, 14 with none) — −3.85 pp (before SPY −3.10 pp), 98.33% CI by 10-session block [−7.23, +0.72], by name [−6.41, +0.68]: no difference this study can separate from zero. Any downtrend read: 2,802 dojis, −0.50 pp, 97.5% CI [−1.75, +0.68] / [−0.89, −0.13]: no verdict — the session-block CI and the by-name CI disagree (AMENDMENTS6: a verdict needs both). The control — a test of the low without a doji, against its own matched days: 2,563 tests, +0.17 pp, 95% CI [−2.07, +2.88] / [−1.09, +2.00]: the tests without a doji show no difference from their matched days that this study can separate from zero. Under the 52-week high by 70%+: 53 dojis on 47 sessions — too few to read (pre-declared). Verdicts are Holm-corrected across these three pre-registered reads (Holm p 0.129 / 0.612 / 0.832); every other cell is exploratory — no verdict. Closed above the doji's high within 5 sessions before closing under its low 46% vs 48% (difference CI by block [−11.78, +8.40] pp); closed under its low within 10 sessions 79% vs 67%. Mean −0.63% (before SPY) against +1.72% on the matched days (difference CI by block [−6.55, +2.46] pp), before costs; −1.13% after a 0.5% round trip. Not advice.", "verdict": "no_signal", "prereg": "docs/research/doji_sweep_study_2026_10_16.md", "script": "backend/scripts/doji_sweep_study.py"}
```
