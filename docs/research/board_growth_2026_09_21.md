# Did the Explosive-Growth and Bonde boards already run? — MEASURED 2026-09-21

> **NOT A SIGNAL, NOT A GATE — research only (Rule #10).** Nothing here changes a
> rule, a gate, a threshold or a tier. No number below is served to a board.

**He asked (2026-09-21):** *"I felt like all the explosive growth stocks and Bondes
stocks have grown a great extent I exited the CRDO today but can you look in to
this more?"*

Every number in this file is read out of `backend/scripts/board_growth_measured.json`,
which `backend/scripts/board_growth_merge.py` builds from the three study scripts.
`backend/tests/test_board_growth_measured.py` pins the headline set, so a re-run that
moves a number fails the suite instead of quietly changing the story.

---

## 1. The answer

**His impression is right about the past and wrong about the present, and the split
is the filing date.** The names on these boards ran hard *before* the quarter that
qualified them, and have gone sideways-to-down *since*.

| read | growth board (21 names) | Bonde visible (160) | scan universe (2,090) |
|---|---|---|---|
| 126 sessions *before* the qualifying filing | **+46.40%** median, 80.0% positive | +8.19%, 66.4% | +8.14%, 65.5% |
| since that filing became public | **−2.21%** median, 40.0% positive | −4.41%, 37.5% | −4.63%, 31.0% |
| trailing 3 months vs RSP | **−8.81pp** [−16.70, +5.93] | **−4.80pp** [−8.89, −1.15] | −1.78pp [−2.52, −1.13] |
| trailing 6 months vs RSP | **+34.99pp** [+4.03, +69.46] | +2.21pp [−4.76, +5.72] | −1.27pp [−2.71, +0.16] |
| members at a 52-week high | **0 of 21** | **0 of 160** | 40 of 2,090 |
| median distance below the 52-week high | 21.14% | 25.39% | 17.17% |

Read the first two rows together. The growth board's median member gained 46.40% in
the six months *up to* its qualifying 10-Q and has lost 2.21% in the time since. The
board is a record of a move that had already happened. The Bonde visible board did
not even have the "before" leg — its members ran no harder than the universe.

So: **over six months the impression holds for the growth board and only the growth
board. Over three months both boards are negative against RSP, the Bonde board
significantly so. Not one of the 181 visible names on either board is at a 52-week
high.**

## 2. What was measured

Three scripts, all read-only against the live Mongo and the audit price/fundamental
pickles. A `NoWriteDB` wrapper refused every write during the runs and a before/after
probe of the three ledgers (`growth_seen`, `bonde_seen`, `growth_board`) came back
byte-equal.

- **Members** (`board_growth_study.py --stage members`) — who is on the boards *today*
  and what their trailing returns look like, benchmarked against **RSP**, reported as
  the **median member** with a bootstrap CI.
- **Replay** (`board_growth_replay.py`) — a point-in-time walk over 24 cross-sections
  21 sessions apart, re-screening each date from filings that were public on that
  date. 54,786 panel rows, **45,425 scored bars**, 2,669 symbols. `strict=True`: a
  filing available *on* the cross-section is excluded, and `refuse_lookahead` asserts
  the boundary case.
- **CRDO** (`board_growth_crdo.py`) — a fact dump on the one name he named.

**Repro gate.** Before any new cell was quoted, the replay reproduced the shipped
explosive-read study on the same panel: median lift **+0.45pp**, CI **[−0.31, +1.36]**,
`gate_passed: true`. Exactly the published pair, so the panel is the same panel.

## 3. Arriving on the board is where the lift is

The replay splits each board into names that **arrived** at that cross-section
(first qualified there) and names that were already **incumbents**. Lift is the
median forward return minus the same cross-section's all-scored median, in
percentage points; CI is bootstrapped over symbols.

| cohort | h=21 | h=63 | h=126 |
|---|---|---|---|
| Bonde explosive — arrivals | **+3.33** [+1.24, +5.42] | **+7.49** [+3.68, +11.46] | **+12.83** [+6.70, +20.91] |
| Bonde explosive — incumbents | +0.27 [−0.99, +1.31] | +0.19 [−2.21, +2.84] | +5.47 [+1.09, +10.04] |
| growth 100/100 — arrivals | +3.69 [−0.22, +10.13] | +5.58 [−2.25, +12.44] | +8.93 [−5.45, +15.04] |
| growth 100/100 — incumbents | −0.26 [−2.97, +2.14] | +3.16 [−4.43, +8.33] | +7.55 [−0.80, +15.79] |
| Bonde strong tier | +0.02 [−0.45, +0.56] | −0.01 [−1.00, +1.26] | +0.67 [−1.66, +2.69] |
| Bonde steady tier | **−0.21** [−0.40, −0.04] | −0.52 [−0.89, +0.02] | −0.51 [−1.18, +0.25] |

Only the **arrivals** row has a CI clear of zero at every horizon, and only on the
explosive tier (n = 224 / 219 / 158 arrivals). The incumbent row — which is what a
board looks like on any given morning — is flat for three months and only separates
by six. The **steady tier is a measured drag**: its CI sits below zero at h=21 and its
momentum-controlled mean is negative at all three horizons.

**Momentum control.** Each row is also compared to the all-scored **mean** of its own
trailing-momentum quintile, so "it was already running" cannot explain the lift. The
explosive tier survives it — mean excess **+3.52pp** [+1.44, +5.94] at h=21,
**+12.51pp** [+3.51, +22.34] at h=126 — but the *median* excess does not move away
from the baseline. That combination means a **fat right tail, not a better typical
name**: a handful of members carry the cohort mean while the middle of the board
tracks its momentum peers.

The quintile cells say the same thing from the other side. The board's lift
concentrates in the members that were **beaten down** over the prior quarter, not the
ones already running:

| momentum quintile (trailing, Q1 = worst) | Bonde explosive, h=126 lift | growth 100/100, h=126 lift |
|---|---|---|
| Q1 (below −19.2%) | **+19.10** [+12.09, +33.04] | **+18.16** [+12.71, +51.39] |
| Q5 (above +26.3%) | +3.41 [−8.05, +10.42] | +9.04 [+1.19, +23.79] |

The universe shows a weaker version of the same shape (Q1 +3.21pp, Q5 +4.41pp at
h=126), so most of the Q1/Q5 gap belongs to the boards, not to the market.

**The screen number does not predict the run.** Spearman rho between a member's
screen number (sales growth, EPS growth) and its trailing 3-month return spans zero
in every cohort — growth board sales rho 0.1987 [−0.2484, +0.5639] (n 21), Bonde
explosive sales rho 0.0882 [−0.1680, +0.3428] (n 60). A bigger number on the board
does not mean a bigger move.

## 4. CRDO

Facts only. The app does not store his fill, so the reference is the 2026-09-21 close.

| | |
|---|---|
| exit reference | entry 167.65 × 196.973 shares → close 187.27 = **+11.7% (+$3,864.61)** |
| trailing 1 week | **+24.77%** — 92.9th percentile of its own board, **99.4th of the scan universe** |
| trailing 1 month | −19.05% — **2.4th percentile** of its board |
| trailing 3 months | −38.10% — 2.4th percentile of its board, 2.8th of the universe |
| trailing 6 months | +81.11% — 69th of its board, 92.8th of the universe |
| trailing 1 year | +8.68% — 31st of its board |
| 52-week high | 302.52 close on 2026-06-22, **38.10% below it** |
| 2026-09-21 close | 187.27, **inside** the stored demand band 182.61–189.12 |
| stop pushes on the name | 3, stop band 163.81–165.79 |

**When the screens first saw it.** Walking 20 filing-availability dates and anchoring
at the first bar *after* each filing:

| screen | first true | anchor | to 2026-09-21 |
|---|---|---|---|
| Bonde explosive | filed 2025-03-10 | 2025-03-11 @ 43.36 | **+331.9%** |
| 100/100 sales+EPS | filed 2025-08-01 | 2025-08-04 @ 114.70 | +63.27% |
| 100/100 with a positive EPS base | filed 2026-03-03 | 2026-03-04 @ 102.54 | +82.63% |

The ledger stamps `growth_seen` 2026-09-12 and `bonde_seen` 2026-09-14 are **day-one
backfill** — "present on that day", not "arrived that day". The screens would have
flagged CRDO eighteen months earlier; the boards only started keeping arrival
records this month.

CRDO's shape is the board's shape in one name: a very large move that was over by
June, a quarter in the worst 3% of the universe, and one violent week at the end.

## 5. What this does not say

- **Survivorship.** The universe is today's membership of the audit price pickle.
  Delisted names are absent by construction, so every cohort here is flattered.
- **Overlap.** Cross-sections are 21 sessions apart, so h=63 and h=126 forwards
  overlap 3× and 6×. Date CIs use block bootstrap (`block = h // 21`) and `n_dates`
  is printed per cell.
- **Derived availability.** Unfiled quarters are assumed available at end + 90 days
  (`derived: "plus90"`). Dropping them instead is the sensitivity, not the headline.
- **Static sectors.** The sector stratum is today's GICS applied to past bars.
- **Not an edge claim.** Arrival lift is a *measurement over 24 cross-sections*, not a
  tradable rule. It has no entry, no stop, no cost model and no out-of-sample test.
  Nothing in this file may be wired to a gate without its own study.
- **398 symbols** in the members pass had no fundamentals in the audit pickle and are
  absent from the screen-number legs.

## 6. His call

1. **Arrival vs incumbency is the only cell with a clean CI at every horizon.** Worth
   surfacing an "arrived this week" marker on the Explosive Growth and Bonde boards,
   the way the S/D boards stamp `first_seen`? The data exists; the boards only started
   keeping it on 2026-09-12 / 09-14, so it is forward-only from here.
2. **The steady tier measures as a drag** (h=21 lift −0.21pp, CI below zero; momentum-
   controlled mean negative at all three horizons, n 14,353 rows / 1,611 symbols).
   666 names carry that tier. Leave it, label it, or drop it from the visible board?
3. **The "before the filing" split is the strongest thing in this study** (+46.40%
   before, −2.21% since, on the growth board). Should the board print a *since
   qualifying filing* column so the run-already-happened case is visible on the tile?
4. **The screen number does not track the run** in any cohort. The boards currently
   sort by it. Sort by something else, or keep it and say what it is?
5. **Re-run cadence.** This is a snapshot of 2026-09-21. Monthly, quarterly, or only
   when he asks?
6. **CRDO** is back inside its 182.61–189.12 demand band with 3 stop pushes on file.
   Does he want it kept on a watch list, or off the boards entirely?

---

*Scripts: `backend/scripts/board_growth_study.py`, `board_growth_replay.py`,
`board_growth_crdo.py`, merged by `board_growth_merge.py`.
Artifact: `backend/scripts/board_growth_measured.json`.
Pins: `backend/tests/test_board_growth_measured.py`.*
