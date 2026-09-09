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

## What the study found

Two years, 2,650-name universe, no lookahead; bands rebuilt at every historical
date from prior bars only, with the live geometry (`demand_reentry.zone_geom`).

**Placebo** — every hot + liquid bar (n=238,857): fwd1 +0.05%, fwd3 +0.19%, 52% up.

1. **The flush and the snapback alone are worse than the placebo.** A ≥20% fall
   into a reversal close (n=5,314) gives ~50% up. The sharper the snapback
   *without* a zone, the worse: off-low ≥12% with a top-30% close measured fwd5
   −2.83%, 47% up.
2. **The demand band is load-bearing.** The same reversal NOT in a band (n=434):
   fwd1 +0.06%, bootstrap p=0.461 — nothing.
3. **The full rule** (n=65, 56 names): fwd1 +1.60% / 62% up (p=0.000),
   fwd3 +2.50% / 63% up (p=0.001).
4. **The edge dies by day five** — fwd5 +0.39%, 51% up, p=0.450.
5. **Entry:** the signal day gaps DOWN into the next open 60% of the time
   (median −0.53%), so the next open beats the close.

| entry | +1 day | +2/3 days |
|---|---|---|
| signal-day close | +1.60% / 62% up | +2.50% / 63% |
| **next open** | **+2.40% / 57%** | **+2.85% / 66%** |
| trigger over the signal-day high (fires 83%) | +0.80% | +2.37% / 65%, 17% stopped |

## The number that actually decides it

A median forward return is not expectancy. Simulating the trade the lane
places — buy the next open, stop 0.5% under the signal-day low, out at the
21-day line or after 3 sessions, intrabar stops honoured — across the same 65
events:

| | |
|---|---|
| win rate | **58%** |
| mean | **+2.29%** (median +2.37%) |
| average win / average loss | **+8.28% / −6.14%** |
| best / worst | +19.9% / **−13.3%** |
| median risk (entry → stop) | 8.4% |
| **expectancy** | **+0.27R** |
| exits | 42 clock, 15 stopped, 8 target |

**The stop is what makes it work.** The raw column's −36.1% worst case becomes
−13.3% once the stop is honoured, and no simulated trade lost more than 15%.

## What is still wrong with it

- **The trades are correlated.** 65 trades sit on only 41 distinct dates and one
  day carries six. Effective sample is nearer 41 than 65.
- **The rule is price-only and cannot see a permanent repricing.** The archetype
  is the warning: DYN fell on 2026-09-08 because *another* company
  (Avidity/Novartis) missed the Phase 3 primary endpoint that Dyne's own
  registrational study uses. A ticker-level news filter would have missed it.
  Boudoukh et al. (NBER 18725) measured exactly this fork — after extreme moves
  no-news names reverse (~40bp) while identified-news names **continue**.
- The literature's short-term reversal effect is 20–40bp; this measured 160bp.
  That gap is either the small-cap population or small-n luck.

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
