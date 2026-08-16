# Did buy zones actually work? — the walk-forward backtest

**Code:** `backend/supply_demand/zone_backtest.py` ·
**Shared rule:** `backend/supply_demand/demand_reentry.py::decide_from_frame` ·
**Tests:** `backend/tests/test_zone_backtest.py` (33)

> Ajay 2026-08-16: *"I want you to look at data historically and tell me if buy
> zones worked.. Record further if you want but I want you to back test and
> record and load them up there."*

## The result

**Corrected 2026-08-16** after adversarial review broke three of the first
version's claims. What is below is the corrected run; what was wrong is recorded
at the bottom, because a backtest whose errors are hidden is worth less than none.

**2,011 liquid names, 5,371 recorded re-entries, 4,976 raced, 339 voided.**
Decision days span **2025-07-07 → 2026-08-13** — thirteen months, not five years.

| Cohort | n | raced | win % | expectancy | **excess vs SPY** | beat SPY |
|---|---|---|---|---|---|---|
| **All zone re-entries** | 5,371 | 4,976 | 51.0% | +0.19% | **−0.035%** | 49.1% |
| Planned R:R ≥ 1 | 3,064 | 2,887 | 39.7% | +0.30% | +0.023% | 40.8% |
| Planned R:R ≥ 2 | 1,504 | 1,395 | 31.9% | +0.40% | +0.081% | 34.2% |
| Planned R:R ≥ 3 | 762 | 694 | 24.9% | +0.45% | +0.095% | 28.0% |
| Zone strength ≥ 60 | 3,381 | 3,144 | 51.7% | +0.15% | −0.085% | 49.6% |
| Fell ≥ 10% from band top | 2,727 | 2,484 | 46.5% | +0.16% | −0.023% | 45.7% |

**The verdict: no edge.** The raw +0.19% per trade is real, but SPY returned
+0.22% over the identical holding windows. Excess is **−0.035%**, and only
**49.1% of trades beat the index** — a coin flip. The rule bought market beta
during a 25% bull run.

The R:R cohorts lift raw expectancy and their excess is still ~zero: +0.023% /
+0.081% / +0.095%, and **fewer than half** of even the R:R ≥ 1 trades beat SPY
(40.8%). Higher R:R buys a better raw number by holding longer in a rising
market, not by picking better.

## Three claims from the first version that were wrong

1. **"5 years of daily bars."** `sepa.prices.load_prices` serves a cached frame
   and **ignores `period`** — measured, `1y` / `5y` / `10y` / `max` all return
   the identical 500 bars. It is a **13-month, single-regime** test. `run()` now
   reports `period_requested` and the real `decision_days` span so this cannot
   masquerade again.

2. **"Only R:R ≥ 3 shows edge (+0.71%)."** That was n=86 with a confidence
   interval spanning zero, on an arbitrary top-300-by-dollar-volume slice.
   On the full universe R:R ≥ 3 is +0.45% raw and +0.095% excess — the same
   ~zero as every other cohort.

3. **"Zone strength is anti-predictive."** A bad comparison: a subset measured
   against the whole sample rather than against its complement. On the full
   universe strength ≥ 60 is +0.15% and strength < 60 is +0.23% — overlapping,
   and the sign of the 300-name result flips. Zone strength is **inert**. The
   `≥ 40` floor stays; nothing here justifies changing it.

## The scoring defect this review found

`walk_forward` began scanning at the entry bar without checking the entry price
was still between the stop and the target. A name that **gapped overnight
through a level** satisfied `low <= stop` on bar one and was booked out **at**
that level — a price it never traded at after entry.

Measured on the 694-trade run: **56 mis-signed (8.1%), contributing +83.6pp
against a whole-sample P&L of +23.5pp** — more than the entire result. Real case:
SNDK 2026-07-27, plan stop 1258.17, next open **1173.60**, scored `stop_first`
at net **+7.166%**. A loss that made seven percent.

Such trades are now `outcome="gapped"`: void, carrying no P&L, excluded from the
raced denominator. 339 of 5,371 on the corrected run.

## One rule, not two

Every decision goes through **`demand_reentry.decide_from_frame`**, the exact
function the live board calls. It was extracted from `analyze_symbol` for this
purpose. A backtest that reimplements the rule tests a rule nobody trades, so
`test_the_backtest_calls_the_live_decision_function` fails the build if
`observations_for` ever grows its own copy of `price_zones.compute`,
`is_falling_knife` or `reentry_read`.

## The five no-lookahead rules

Carried over verbatim from `sd_backtest.py`, which established them for the
liquidity-sweep test:

1. The decision for day D sees bars **strictly up to and including D's close**.
   `_upto` slices positionally before any zone is computed, and
   `test_the_decision_function_reads_only_its_frame` greps `decide_from_frame`
   for `load_prices` / `datetime.now` / `_cache` so it cannot quietly reach past
   the frame.
2. Entry is the **next session's OPEN**, never D's close.
3. Outcomes walk forward bar by bar on daily OHLC.
4. A bar whose range contains **both** the stop and the target scores a **loss**.
   Daily bars cannot order the two touches, and assuming the win inflates every
   result.
5. Costs charged **both sides** at 2bp.

## Three ways this could have been flattered, and what stops each

- **Episode double-counting.** Price sits inside a band for a fortnight and every
  day re-qualifies. Only the first bar of an episode is recorded
  (`EPISODE_COOLDOWN_BARS = 20`), so one good week cannot become a dozen wins.
- **Unresolved trades.** Anything still open at the end of the data is
  `outcome="open"`, and anything hitting the 60-bar cap is `"expired"`. Neither
  counts toward the win rate; both are reported separately.
- **Survivorship.** The universe is **today's** liquid names, so delisted and
  acquired tickers are absent. This biases the result **upward** and cannot be
  fixed without a point-in-time universe we do not have. It is reported in the
  payload as `survivorship_note`, not buried.

## The ledger

`record()` writes observations as `kind="zone", backtested=True`, so they are
never mistaken for live-recorded outcomes. Re-runs purge prior backtested rows
first rather than accumulating duplicates.

The Past Winners tab reads them via `chart_maps.board.zone_winner_tiles`
(`?tab=winners&source=zone`), which **excludes the same-bar wins** — a chart of a
target that was never far away teaches nothing about a re-entry.

## Not advice

Historical behaviour of a rule on past bars. Not a forecast, not a
recommendation, and explicitly not a reason to take the next zone signal.
