# Did buy zones actually work? — the walk-forward backtest

**Code:** `backend/supply_demand/zone_backtest.py` ·
**Shared rule:** `backend/supply_demand/demand_reentry.py::decide_from_frame` ·
**Tests:** `backend/tests/test_zone_backtest.py` (23)

> Ajay 2026-08-16: *"I want you to look at data historically and tell me if buy
> zones worked.. Record further if you want but I want you to back test and
> record and load them up there."*

## The result

300 most-liquid names, 5 years of daily bars, **694 recorded re-entries**, 686 of
them raced to a target or a stop.

| Cohort | n | raced | win % | **expectancy** | avg win | avg loss | median R:R | same-bar wins |
|---|---|---|---|---|---|---|---|---|
| **All zone re-entries** | 694 | 686 | 48.7% | **+0.02%** | +2.55% | −2.39% | 1.14 | 135 |
| Planned R:R ≥ 1 | 379 | 374 | 35.0% | +0.07% | +4.34% | −2.23% | 1.96 | 33 |
| Planned R:R ≥ 2 | 184 | 180 | 26.1% | +0.11% | +6.14% | −2.02% | 2.97 | 11 |
| **Planned R:R ≥ 3** | 90 | 86 | 23.3% | **+0.71%** | +8.75% | −1.72% | 3.92 | 3 |
| Zone strength ≥ 60 | 452 | 445 | 47.2% | **−0.15%** | +2.43% | −2.46% | 1.03 | 92 |
| Fell ≥ 10% from band top | 352 | 348 | 43.1% | +0.02% | +2.90% | −2.17% | 1.40 | 69 |

**Read expectancy, not win rate.** The board applies no minimum R:R, so a target
sitting a fraction above entry wins nearly every time and pays nearly nothing —
**135 of 694 trades hit their target on the entry bar itself.** That lifts win
rate without lifting the account.

Two findings stand out:

1. **The rule as gated has no edge.** +0.02% per trade is indistinguishable from
   zero, and that is *before* correcting for survivorship, which biases it
   upward.
2. **Zone strength is anti-predictive at the top end.** Raising the strength
   filter to 60 makes expectancy **negative** (−0.15%), while the live board
   *requires* ≥ 40. Whether that is a strength effect or the R:R effect in
   disguise — high-strength zones may systematically have closer targets — is
   under separate verification.

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
