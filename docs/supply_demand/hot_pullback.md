# 🔥 Hot Pullback — the flush into demand that turns the same day

Ajay 2026-09-09: *"Can you create a new tab for hot pull back like 21 day moving
average drops but have a reversal from demand zones? The drop should be someting
like DYN today which bounced back quick. I wanna see such names whcih dropped
huge but have been hot in the market. Are having reversals"* … *"Can you make
sure we paper trade this in autopilot too?"*

Code: `backend/supply_demand/hot_pullback.py` (board),
`backend/trading/hot_pullback_entry.py` (paper lane).
Endpoint: `GET /supply-demand/hot-pullback`. Tab: `/chart-maps?tab=hot_pullback`
(`frontend/src/components/HotPullbackBoard.tsx`).

**Owner rules on price structure. No book, no cites — Supply & Demand /
day-trade scope, never Minervini. Not advice.**

## The archetype

DYN, 2026-09-08, measured on closed bars:

| | |
|---|---|
| prev close → open | 24.28 → 17.08 |
| low | **17.00**, inside a 4-touch demand band at 16.56–17.02 (strength 92) |
| close | 20.31 = **+19.5% off the low**, 85% up the day's range |
| vs the 21-day line | **−20.6%** |
| vs the prior 10-day high | **−36.3%** |
| volume | 11× average |

## The rule — all four parts required

| part | rule | constant |
|---|---|---|
| hot first | prior close ≥30% above its own 52-week low; ≥$5M median 50-day dollar volume | `HOT_ABOVE_52W_LOW_PCT`, `MIN_DOLLAR_VOL_USD` |
| the flush | today's LOW ≥12% under the prior 10-day high **and** the close ≥10% under the 21-day line | `FALL_FROM_10D_HIGH_PCT`, `UNDER_MA21_PCT` |
| into demand | that low landed inside a **tested** demand band | `band_for_low` |
| the snapback | close ≥8% off the low **and** in the top 30% of the range | `OFF_LOW_PCT`, `RANGE_POS_MIN` |

A **proven** band (2+ touches) is deliberately NOT required — requiring one
measured *worse* (52% up vs 53%; 3+ touches 50%). `alert_gates` is not imported
here at all, and a test pins that.

## ⚠️ CORRECTED 2026-09-09 — this rule has NO measured edge

**The numbers this board first shipped were wrong.** They claimed 58% win,
+2.29% mean and **+0.27R**. Ajay sizes real money off this board.

### The corrected measurement

2,594 usable names, bands rebuilt at every historical date from prior bars only,
no lookahead. The trade: buy the next open, stop 0.5% under the signal-day low,
out at the 21-day line or after 3 sessions, intrabar stops honoured.

| | |
|---|---|
| trades / dates / names | **83 / 50 / 71** |
| window | 2025-10-21 → 2026-08-25 |
| win rate | **51.8%** |
| mean / median | **+0.75%** / +0.21% |
| avg win / avg loss | +7.82% / −6.85% |
| worst / best | **−14.61%** / +19.94% |
| median risk | 8.8% |
| **expectancy** | **+0.10R** |
| **95% CI (date-block bootstrap)** | **−0.188R to +0.405R — includes zero**, P(R≤0)=0.264 |
| exits | 54 clock, 21 stopped, 8 target |

And +0.10R is the *most favourable defensible* figure. It does not survive:

| stress | result |
|---|---|
| one trade per date (these are correlated market-wide flush days) | **+0.094R**, n=50, 54% win |
| drop the single best date, 2025-11-24 | **+0.015R** |

83 trades sit on **50 dates**, so the effective sample is nearer 50 than 83.
**The honest number for a sizing decision is 0.0R ± 0.2.** A separate
survivorship check (the cache holds delisted names the survivors-only universe
does not) put it near 0.00R; that one is *not* reproduced by the shipped script,
so it is not quoted on the board.

### Why it was wrong

The original feature pass computed the rolling columns, called `dropna()`, and
only *then* applied `rolling(252)` — so the event window began at bar **301**,
not 252. That off-by-49 deleted the first 49 eligible sessions: **17 trades
running 23.5% win and −0.418R**, twelve of them on the 2025-11-06/07/11
market-wide flush days. The backtest started one week after the sample's worst
cluster.

| | n | win | mean | R | worst | exits |
|---|---|---|---|---|---|---|
| shipped (wrong) | 65 | 58% | +2.29% | +0.27 | −13.3% | 42/15/8 |
| re-run at `--floor 300` | 66 | 59.1% | +2.40% | +0.233 | −13.3% | 43/15/8 |
| **re-run at `--floor 252`** | **83** | **51.8%** | **+0.75%** | **+0.100** | −14.61% | 54/21/8 |

Four independent re-derivations — one inline, three by agents that did not
share code — agree on the corrected row, and all four reproduce the original by
that single change.

**The process failure is the real lesson: the module, docs, tests and paper
lane all shipped; the backtest did not.** Nothing could re-run the number, so
nothing caught it. The measurement now lives at
`backend/studies/hot_pullback_study.py` and `--floor 300` reproduces the bug on
demand.

### What else the correction overturned

1. **No gate in this rule separates — and the demand band least of all.** This
   doc used to call it "the one that matters".

   | gate | kept | excluded cohort | separation | p |
   |---|---|---|---|---|
   | demand band | +0.100R | **+0.007R** (n=467) | +0.093R | **0.198** |
   | snapback pair | +0.100R | −0.026R (n=3,906) | +0.126R | **0.234** |

   Neither clears p<0.05. `studies/hot_pullback_study.py` measures each gate
   against the cohort it removes, so both are re-runnable.
3. **Flush depth carries no information.** The −10%-under-the-21-day gate
   already implies a deep flush, so the flush gate is effectively inert: 10%,
   12% and 15% select the **same 83 events**. Ajay asked on 2026-09-09 to
   loosen it to 10% — measured, that adds **zero** names. The only stable read
   is that deeper than 30% is worse (−0.059R, n=39). **No constant was changed.**
4. **The forward medians were shifted a session.** From the next open: +0.79%
   by that close (52% up), +2.39% by day two (59%), +0.61% by day three (57%).
   The old "+2.40% by the next close" was the day-two figure; the old "+2.85%"
   existed nowhere.
5. **"2 years" was never reachable.** The cache holds ~501 bars and the 252-day
   hot gate eats half, so the window is ~12 months — and the original run saw
   only ~9.5 of them.
6. Worst simulated trade is **−14.61%**, not −13.3%. The old sentence "no
   simulated trade lost more than 15%" survived on 0.4pp of luck.

### What it is still good for

A watchlist. "A hot name took one hard flush into structure and turned the same
day" is a real, rare, legible thing to look at — ~83 a year. It is not a trade
signal, the board says so on every row and in a correction notice, and the paper
lane stays on to keep measuring it forward.

## What verified practitioners actually do

Researched before building, on Ajay's ask. **No trader with a dated, verifiable
record trades this exact rule.** The nearest cousins:

- **Oliver Kell** (2020 US Investing Championship, +941.1%, broker-statement
  verified). His *Reversal Extension* (Victory in Stock Trading, pp. 16, 22-23)
  is the same bar shape but at the end of a **downtrend** — 5+ closes below the
  10 EMA. DYN would have failed that gate. Kell names the *later* 10/20-EMA
  reclaim ("Wedge Pop") as the first clean buy and calls the reversal-extension
  stage bottom-picking. This app implements his version at
  `backend/kell/reversal_extension.py`; it has fired 4 times and triggered none,
  and its sibling `exhaustion_extension` fired 122 times and triggered none.
- **Kacher & Morales** "Undercut & Rally" — needs a prior low undercut and
  reclaimed; the reclaim is the trigger.
- **Linda Raschke** "Turtle Soup" (Street Smarts, 1995) — a new 20-day low that
  fails, entered on a buy stop back above the prior low.
- **Minervini refuses it** (TLSW p.215), and his universe is exactly Ajay's.
  But TTLAC ch.5 p.89 says to wait until the stock *starts turning up* rather
  than buying the nosedive — which is what the ≥8% off-low and top-30% close
  requirement enforces.
- Everyone loudly *selling* this trade is unverified. The FTC sued Warrior
  Trading in April 2022 over day-trading claims; $3M judgment.

Where all the verified versions agree with the measurement: **stop under the
reversal bar's low, a near first target, and a hold measured in days.** That is
the fwd5 death, arrived at independently.

## The paper lane

`trading/hot_pullback_entry.py`, engine step **(m)**, flag `hot_pullback_entry`
(default ON, **paper only** — the lane refuses a live broker).

| | |
|---|---|
| buys | yesterday's signals, at **today's open** (the measured entry) |
| window | 09:30–10:00 ET only |
| stop | 0.5% under the signal-day low; refuses a stop wider than 20% |
| exits | stop → target (the 21-day line) → **the 3-session clock**, in that order |
| caps | 2 entries a day, 3 open |
| journal | `strategy: hot_pullback`; state in `hot_pullback_positions` |

The clock exit is a rule, not a preference: the edge is gone by day five, so a
lane that held would be trading something unmeasured.

## The scan, and the bug it was hiding

Ajay 2026-09-09: *"hot pull back doesn't have scan."* It had none — the board
recomputed only when the tab was opened. Two consequences, one cosmetic and one
that cost the lane everything:

- opening the tab on a cold API process met a "warming" page;
- **the paper lane could never fire.** The board is built off the *latest* bar.
  At 09:35 that bar is today's partial session, so every row is dated today,
  and `hot_pullback_entry.signal_is_fresh` rejects anything that is not the
  *previous* session. It skipped 100% of rows, silently.

The signal day is a **closed session**, so it is now written down when it
closes and read back the next morning.

| | |
|---|---|
| `hot_pullback.record(data)` | writes the closed session to Mongo `hot_pullback_runs`, one doc per `day`, `replace_one(upsert)` so a re-run cannot stack |
| what is written | only rows with `live: False`; a board that is all live (the RTH case) writes **nothing**, on purpose |
| gate | `market_hours.gate.closed_reason` — the board still renders on a closed day, only `record` is gated |
| `last_closed_signals(before=today)` | what the lane reads: the newest recorded day strictly before today |
| no history | the lane buys nothing and says `the post-close scan has not written one` |

| cron (ET, Mon-Fri) | what it does |
|---|---|
| **17:05** | the one that matters — records, after the 16:30 broad fast-scan patched the closed bars and the 16:55 warm rebuilt the bands |
| **08:05** | backstop — if 17:05 failed, still writes yesterday's session before the 09:30 lane |
| 09:25 | pre-open record + warm |
| 09:35, `*/20` 10-15 | warm only; `record` finds no closed row mid-day and writes nothing |

All five **curl the API**. A `python -m` in the cron container would warm a
different process's memory and leave the page cold — the trap the 09:25
demand-reentry curl exists to avoid.

A source guard (`test_the_lane_never_goes_back_to_a_live_rescan`) asserts
`run()` calls `last_closed_signals` and never `cached_or_warm`, so this cannot
regress quietly.

## Tests

`backend/tests/test_hot_pullback.py` (39): the DYN archetype passes every part;
the owner constants; the study block including the simulated expectancy; each
missing part blocks and names itself; the inclusive edges; any tested band
counts and `alert_gates` is not imported; the band must contain the low; the
strongest containing demand band wins and supply is ignored; garbage in → None;
the plan stops under the low; sort order; every rules line built from its
constant. Lane: the entry window, only yesterday's flush, the stop and its
budget boundary, the clock exit, the stop/target/clock precedence, the live
broker refusal, both gates, the status block, the narrative. The scan: only a closed session is written
down; record replaces rather than stacks; record refuses on a closed market,
while warming, mid-session when every row is live, and on an empty board; the
lane reads yesterday's recorded session and never today's; no history means it
buys nothing; the source guard against a live re-scan; the crontab actually
carries the passes.

`frontend/src/components/HotPullbackBoard.test.tsx` (10): formatters never print
NaN; the headline; the study line carries the horizon and the tail; the DYN row
renders every fact and the horizon; the empty board says the setup is rare; the
near-misses; the rules panel; warming and error; a row of nulls.

Frontend contracts: "Hot Pullback tab prints its measured horizon" and "Chart
Maps carries the Hot Pullback tab".

## Traps hit building this

- **The pre-market restamp.** Before the open, Massive rolls the snapshot's
  `date` to today while the aggregate still holds *yesterday's* session. Taken
  at face value that dated DYN's 09-08 flush as 09-09 and printed a 0.0% day
  change on it. `_today_bar` now compares the snapshot's OHLC to the last cached
  bar and treats an exact match as a restamp, not a live session.
- Today's bar is never taken from `price_cache` — a doc written during the
  session holds a partial bar (the PHVS trap, 2026-09-08).
