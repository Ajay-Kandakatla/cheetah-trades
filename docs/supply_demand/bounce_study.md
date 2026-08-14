# Do stocks bounce at demand zones? — the S&P 1500 study

_Run 2026-08-14. Ajay: "test data to see historically that had quick bounces as
they entered demand zones… Try to test all the 1500 stocks and tell me which
ones bounce back quickly. That will [mean] there are limit orders."_

> **ANSWER IN TWO PARTS.**
> **1. Demand zones are real, but weak** — +3.3 percentage points over a
> random day.
> **2. You cannot pick which stocks will bounce** — the per-name ranking does
> not survive out of sample, so the "top bouncers" list is noise.

## The hypothesis was the right one to test

A resting bid is invisible: there is no L2 on our data, and stop orders are
broker-side conditionals that exist in no feed until they fire. But a bid that
is genuinely there leaves a footprint — price arrives and **turns quickly**. A
level with nothing behind it gets absorbed and drifts through. So "how fast did
it turn" is a legitimate proxy for "was there size resting there".

## Method

`supply_demand/sd_bounce.py`. Zones are recomputed at anchors every
`ANCHOR_STEP_BARS` (21) using only bars up to that anchor; entry events are
detected in the 21 bars that FOLLOW it; outcomes walk forward from the bar
after the event. Nothing about a band is derived from the price action it is
used to judge — locked by
`test_zones_never_see_the_bars_they_are_judged_on`.

**A bounce** = price closes ≥ `BOUNCE_PCT` (2%) above the entry close within
`BOUNCE_LOOKAHEAD_BARS` (5) **without first closing more than
`BREAK_BUFFER_PCT` (1%) below the band floor.** Breaking the floor and only
then rallying is a *failed zone*, not a slow bounce; counting it either way
would flatter every number here.

## Result 1 — the zone effect is real and small

| | events | bounced ≤5 bars |
|---|---|---|
| **Demand-zone entries** | 2,937 | **45.1%** |
| **Random days** (same floor distance, 2.02%) | 2,937 | **41.8%** |

**Edge: +3.3 percentage points**, ≈2.6σ (p ≈ 0.01).

The control matters. Without it, "45% of zone entries bounce" sounds like a
coin flip and would have been dismissed. Against the base rate of a +2% move in
5 days, it is a genuine — if modest — effect.

## Result 2 — the per-name ranking does not persist

Across the full 1,500 (1,081 names with enough history), the top of the
ranking looks spectacular:

| | events | bounce % | med bars | med gain |
|---|---|---|---|---|
| MSM | 10 | 90.0% | 3 | 3.12% |
| SANM | 9 | 88.9% | 1 | 5.23% |
| CELH | 9 | 88.9% | 1 | 3.79% |
| UAL | 8 | 87.5% | 1 | 4.00% |
| NVDA | 8 | 87.5% | 2 | 3.46% |

**That list is a mirage.** With ~1,000 names tested at ~10 events each and a
47% base rate, a handful printing 85%+ by luck alone is the expected outcome,
not evidence. A per-name binomial p-value does not rescue it — this is a
multiple-comparisons problem, and Bonferroni at 0.05/1081 eliminates every name
at that sample size.

The test that settles it is out-of-sample persistence: rank on the first half
of history, measure the second.

| | second-half bounce rate |
|---|---|
| Top quartile by first half | **50.5%** |
| Bottom quartile by first half | **50.1%** |
| **Gap** | **0.4 pts** |
| Rank correlation | **0.036** |

Repeated at a shorter warm-up (832 names instead of 635): gap 1.7 pts, rho
0.043. Same conclusion.

**A stock's past bounce rate carries essentially no information about its
future bounce rate.** "This name respects its levels" is not a stable property
on this data.

## What this means for trading

- **Do not build a watchlist of "bouncy" names.** That is the one thing the
  study rules out directly.
- The zone effect itself (+3.3pp) is real but far too small to carry a strategy
  on its own — consistent with `sd_backtest.py`, which found no positive
  expectancy for the sweep entry on either horizon.
- Bounce SIZE matters as much as rate and is reported alongside it. A name that
  turns 80% of the time for 0.4% is not tradeable after spread.

## Limits

- **Two years of daily bars is the hard ceiling** — `prices.load_prices` caps
  at 505 bars whatever period is requested. That is what forces ~10 events per
  name and makes the per-name question unanswerable rather than merely
  negative. With 10 years the persistence test could be re-run properly.
- Survivorship: today's S&P 1500 membership.
- The 2%/5-bar definition is a house choice. A different threshold would move
  the absolute rates, though the control comparison and the persistence result
  are both differences, so they are far less sensitive to it.

## Re-running it

```python
from sepa import universe as U
from supply_demand import sd_bounce as B
B.run(U.fetch_sp1500())                    # the per-name board
B.persistence(U.fetch_sp1500(), half_min_bars=150)   # the honesty check
```

Always read `persistence` before acting on `run`.
