# Back in Demand — the live track record

Ajay 2026-08-17:

> *"Can you maintain history of our In deman page please.. I think its working
> out.. I saw CIEN you recommended is bouncing out of the zone now.. I would
> imagine the same with other stocks. Want you to track it"*

Code: `backend/supply_demand/demand_history.py`, recorded from
`demand_reentry.scan()`, graded by cron, read at
`GET /supply-demand/demand-reentry/history`.
FE: `frontend/src/components/DemandTrackRecord.tsx`,
`frontend/src/lib/demandTrackRecord.ts`.
Tests: `backend/tests/test_demand_history.py` (41),
`frontend/src/lib/demandTrackRecord.test.ts` (13),
`frontend/src/components/DemandTrackRecord.test.tsx` (9).

---

## 1. One correction first

**CIEN was never recommended.** It is the name the falling-knife guard was
*built to remove* (see `demand_reentry`'s module docstring), and it is still
refused today. It is up 2.7% since 08-13 — and 17% off its 08-11 low, which is
the move the guard declined to buy into. The request stands on its own; the
example does not support it, and a ledger seeded on that belief would have
started out measuring the wrong thing.

## 2. Why not just read `zone_backtest`

The walk-forward is the right tool for **choosing** a rule and the wrong one for
answering **"is it working"**:

| `zone_backtest` | this ledger |
|---|---|
| re-derives the past from *today's* liquid S&P names → survivorship, biased up | records the universe as it actually resolved that day |
| re-run from scratch whenever the rule changes | append-only; a later tweak cannot rewrite what the page said |
| cannot see venue/liquidity enrichment, which only the live pass computes | records the row the page rendered |
| 13.5 months of one bull tape | starts 2026-08-17 and only grows |

Both stay. They answer different questions.

## 3. The unit is an EPISODE, not a day

A name sits inside its band for days or weeks — SWKS sat there from a Thursday.
One observation per day would count a single setup twenty times and let one
stubborn name carry every statistic.

So an episode is a continuous stretch offering the **same zone**, and identity
is the band rather than the calendar:

* matched to an open episode when the band **midpoint** is within
  `EPISODE_BAND_TOL_PCT = 2.0` and the gap since it was last seen is
  ≤ `EPISODE_MAX_GAP_DAYS = 10`
* midpoints, not overlap — `HALF_WIDTH_PCT` makes every band 3.5% wide, so an
  overlap test would chain adjacent zones into one
* the tolerance is pinned **≤ `MERGE_PCT` (4.0)** by test: bands closer than
  that are the same zone *by construction*, so a looser tolerance would swallow
  a genuinely new adjacent band into a stale episode
* a **resolved** episode never absorbs a later sighting, or a graded trade would
  keep accruing appearances and the band's second offer would go unrecorded

## 4. Honesty contract

| Rule | Why |
|---|---|
| The plan is **frozen at first sight** | Grading against a stop that crept up underneath the trade measures hindsight, not the board. |
| Entry is the **next session's open** | The board publishes post-close. Entering on the qualifying bar is one day of lookahead — and always a favourable one, since the name qualified *by* closing inside its band. |
| A plan already broken at that open is **VOID** | You never got the fill. Not a win, not a loss, outside the raced denominator. Scoring these wrong was worth 8.1% of trades and more than the entire backtest P&L (2026-08-16). Surfaced as **Never filled**. |
| A bar holding **both** levels is a LOSS | A daily bar cannot order the two touches. |
| Grading is **imported**, never reimplemented | `ZB.walk_forward` — pinned by `test_grading_is_IMPORTED_from_the_backtest_never_reimplemented`, which also forbids a local race loop. The gap and ambiguous-bar rules are exactly the subtle ones that drift. |
| Every aggregate carries `excess_vs_spy_pct` | A dip-buying board in a rising tape shows profit with or without skill. |
| Rows are recorded **unfiltered by the R:R floor** | `rr` is stored per episode, so the floor is a question you can ask of history (`?min_rr=`) rather than a decision baked into it — the same reason the floor never touches `is_reentry`. |
| An empty ledger **says** it is empty | `verdict()` returns `'empty'` and the UI prints no win rate. "0.0%" is a claim; a blank is not that. |
| Below 20 finished episodes it says **"too few to lean on"** | An episode can run 60 bars. A usable sample is months out, and saying so is the point. |

## 5. Where it plugs in

**Recording needs no cron.** `scan()` writes the run and its episodes itself,
so the existing 4:55/4:57pm warms already capture the board. Two things had to
happen *before* the two lines that follow it in `scan()`:

* **before `limit`** — the cron warms with `limit=1`; recording after the slice
  would write a one-name board every evening
* **before the R:R floor** — that is applied at read time by `cached_or_warm`

A Mongo outage costs the record, not the page: the call is wrapped and logged.

**Grading** is the only cron — 5:40pm ET weekdays,
`python -m supply_demand.demand_history resolve`. As an import, not over HTTP
(unlike the warms): it touches Mongo and the shared price cache, neither of
which lives in the api process.

## 6. Separate collection, deliberately

`demand_board_runs` + `demand_episodes`, **not** `pattern_observations`.

That ledger's reader knows two kinds, `pattern` and `candle`. Live zone rows
written there would sit in the patterns page's `pending` counter forever,
because nothing there can grade them — which is very nearly the defect this work
uncovered on the way past (§7). Same shape is not the same question.

## 7. What building this turned up

Three live defects in `patterns/history.py`, all fixed here:

| defect | measured | cause |
|---|---|---|
| a candle formation named `None` with **n = 4,976** and a 0.0% hit rate, published next to hammer's real n = 125 | 80% of the candle table by count | `zone_backtest.record()` writes simulated trades into that collection; the aggregate's `else` branch bucketed every one into `candles` |
| **395** rows stuck pending forever | pending 647 → 252 | no zone branch in `resolve_pending`, so they fell to `_grade_candle`, raised `KeyError('read')`, and were swallowed by a blanket `except` |
| `since` claimed **2025-07-07** | earliest live row is 2026-06-10 | the backtest's earliest decision day; the page claimed 13 months of record over ~2 months of observations |

Fix: one `LIVE_ONLY = {"backtested": {"$ne": True}}` filter on all three read
paths, and `GRADABLE_KINDS` so an unknown kind is skipped and **counted**
(`skipped_ungradable`) rather than guessed at. A silently-skipped row looks
identical to a healthy one.

---

## Where the honesty is enforced

| Decision | Guard |
|---|---|
| A multi-day stay is one episode | `test_a_name_sitting_on_the_board_for_days_is_ONE_episode` |
| The plan cannot drift | `test_the_plan_is_FROZEN_at_first_sight` |
| A re-scan does not double-count | `test_a_rescan_on_the_SAME_day_does_not_double_count` |
| A new band is a new setup | `test_a_return_to_a_DIFFERENT_band_opens_a_new_episode` |
| A graded trade cannot reopen | `test_a_RESOLVED_episode_never_absorbs_a_later_sighting` |
| Tolerance ≤ merge width | `test_the_episode_tolerance_is_no_looser_than_the_zone_merge_width` |
| Entry is the next open | `test_entry_is_the_NEXT_sessions_open_not_the_observation_bar` |
| Both levels in one bar = loss | `test_a_bar_holding_BOTH_levels_is_a_loss` |
| A gapped plan is void | `test_a_plan_already_broken_at_the_open_is_VOID_not_a_win` |
| A plan with no target is counted, not hidden | `test_an_episode_with_no_target_is_COUNTED_as_incomplete_not_silently_skipped` |
| SPY missing ≠ grading blocked | `test_a_benchmark_outage_does_not_block_grading` |
| Excess leads the read | `test_accuracy_leads_with_expectancy_and_excess_not_the_win_rate`, `headline` tests |
| The floor re-slices, never bakes in | `test_the_rr_floor_re_slices_history_after_the_fact` |
| `since` is when recording began | `test_since_reports_when_recording_began_not_a_backtest_window` |
| Empty means empty | `test_an_empty_ledger_answers_with_nulls_rather_than_a_fake_zero`, `never prints a win rate for a ledger with nothing graded` |
| Mongo down ≠ page down | `test_no_mongo_is_reported_and_never_raises` |
| Recording precedes limit and floor | `test_recording_happens_before_the_limit_and_before_the_rr_floor` |
