# Bullish reversal, not a falling knife

**Ajay, 2026-09-09, hours after the bouncing-only gate shipped:**

> I think we got alerts wrong.. I need only bullish reversal stocks that touched
> demand zone and bouncing back.. Those are the only alerts I need and mood has
> to be bullish too with reversal. After a stationary bottommed stocks as I
> caught a fallig knife today with Casy

and, choosing between the two readings of "mood":

> #1 but I need them to be looking at GEX and other bullish patterns to see and
> also most recent sentiment and they have to be <1% of reversal from demand
> with a minimum of 5% room to Supply

and, on scope:

> Keep the other criteria that exist do not create a new flow but add on more
> things to see which ones are bullish i am not trying to catch falling knifes
> as I am with the alerts now

## What was wrong

The morning's `PUSH_DIRECTIONS = ("bouncing",)` was necessary and **not
sufficient**. `approach_read` is an **intraday** read: the day's low touched the
band and the print is ≥ 0.5% off it. CASY satisfied that at 08:13 ET while it was
in free-fall on a post-earnings repricing.

Both things that would have stopped it were **already computed in this repo**,
and neither was wired to the phone:

| read | CASY, 2026-09-09 | where it lived |
|---|---|---|
| `sd_liquidity.is_falling_knife` | **True** — swing lows 811.19 → 740.00 under a 50-day falling 825.82 → 822.61 | `demand_reentry` (board only) |
| `mood` | **−24.3 "leaning bearish"** (floor for a long is +25.0) | attached to pushes as *context*, never a gate |

## The gates

Both live in `alert_gates.py`, both **fail closed**, both apply to
`demand_alerts` (5-min) and `zone_edge` (per-minute).

1. **`knife_gate`** — not a falling knife. Swing lows stepping DOWN **and** the
   50-day falling, both required, so a single shakeout low inside an uptrend does
   not disqualify a name. Neutral price structure; **no book**.
2. **`reversal_mood_gate`** — the mood of the **turn**, `≥ +25` over the last
   **60 sessions**.

### Why the mood frame changed

`mood()` is a **trend** read. 25 of its points are price vs EMA20/EMA50, 10 are
position in the frame's range, 10 are higher-highs/higher-lows. A stock that has
genuinely **bottomed** scores **−45** on those three before momentum and pressure
are counted, and `vwap` is dead at 0 on daily bars. It can never reach +25 on a
2-year frame.

So the literal reading of *"mood has to be bullish"* would have silently deleted
the exact setup he described — *"after a stationary bottommed stock"* — and left
only strong names pulling back.

**Measured** across 1,172 names with a demand band:

| | share |
|---|---|
| mood ≥ +25 on the 2-year frame | 22.6% |
| within 8% of the 60-day low | 37.5% |
| **both** | **1.19%** |

Mean position in the 60-day range by mood bucket: `+25..60` sits at **72%** of
range and **+28.8%** above the 60-day low; `< −10` sits at **22%** and **+8.6%**.
The two requirements are near-disjoint by construction.

He was shown this and chose the **turn** read. It surfaces names like MOS
(2-year +21.5, turn **+53.1**) and NTNX (2-year +20.0, turn **+41.7**) that the
literal floor would have dropped.

## Measured impact

**His own pushes**, 2026-09-01 → 09-09, 433 scored (`skipped` computed on closed
bars as of each push day, `mood_read`'s own frame and `closed_only`):

| | n | share |
|---|---|---|
| falling knife on the push day | 138 | **32%** |
| mood below +25 | 347 | **80%** |
| blocked by **either** | 355 | **82%** |
| would still have pushed | 78 | 18% |

131 of those pushes went out on names whose mood read outright **"bearish"**.

⚠️ **Those 433 pushes are 4 trading days** (09-03, 09-04, 09-08, 09-09). The 82%
is an honest *volume* claim and **not** evidence about outcomes — forward returns
over that window are dominated by two market-wide down days. Do not quote it as
edge.

**Live funnel**, last closed session, 1,355 distinct names with a demand band:

```
1,355  with a demand band + history
  402  bouncing off it
  151  ... >= 5% room to the first proven lid
  108  ... within 1% above the band        <- what the phone sent this morning
   69  ... NOT a falling knife             (-36%)   <- CASY dies here
   15  ... turn mood >= +25                (-78%)
```

## Things to SEE — never gates

`supply_demand/bullish_context.py`, a **separate module** so that "context can
never block a push" is a fact about the import graph rather than a promise:
`alert_gates` is a leaf by contract and cannot see it.

- **GEX** — reuses `gex_history.board_bucket` verbatim (bullish = dealers net
  long gamma, pinning, spot at/above the flip). Written post-close, so the row is
  always a prior session's; never same-day lookahead. Coverage is thin — the
  snapshot walks ~200 names a day — so a missing row means nothing either way.
- **Bullish patterns** — `patterns.timeframe.scan`, with **`flat_top` excluded**:
  it fired on **120 of 120** random names. A pattern present on everything reads
  as confirmation while carrying no information.
- **Sentiment** — `catalysts.chatter`: % of tagged StockTwits messages bullish,
  and the 24h count. An outage answers `None`, never "0 chatter".

### Why none of them gates

`pattern_observations`, 760 resolved observations, 21 sessions forward:

| pattern | n | closed up | mean |
|---|---|---|---|
| cup_with_handle | 434 | 45% | −0.12% |
| double_bottom | 248 | 43% | +0.35% |
| triple_bottom | 68 | 37% | −0.98% |
| inverse_head_shoulders | 10 | 10% | −4.78% |
| **placebo (all resolved)** | **659** | **50%** | **−0.10%** |

Not one beats the placebo. Gating on them would make the signal **worse**, which
is the opposite of the ask. Every rate is printed beside its placebo and he
decides. A contract test fails if any record ever rises above the placebo without
someone promoting it deliberately.

## The 🔪 badge

> Also add falling knife indicator to the alerts if they are true so I know not
> to buy them

The phone now refuses a knife outright, so a knife can only reach him via a
**board** — which is exactly where he browses for something to buy. Every Back in
Demand and Deep Demand tile carries `_knife` from its row (`demand_reentry`
already computes it) and `_knife_decor` appends a **`🔪 falling knife`** badge,
tone `warn`. Unlike the dwell tag this one is coloured, because it *has* been
measured: 32% of his own pushes were knives.

## Still open

`stationary_bottom` — a positive test that the stock has **based**, distinct from
the knife guard's negative. Three definitions are measured in
`studies/bounce_quality_study.py`; the strongest single clause found so far is
**no new low in the last 5 sessions**, which alone rejects CASY *and* rejects
KBH, a real losing trade that both `is_falling_knife` and `structure_read` waved
through. Not shipped until the study says which constants earn their place.

## Files

- `supply_demand/alert_gates.py` — `knife_read/gate`, `reversal_mood_read/gate`,
  `daily_frame`, `REVERSAL_MOOD_BARS`, `REVERSAL_MOOD_FLOOR`, `KNIFE_MA_LEN`
- `supply_demand/bullish_context.py` — GEX / patterns / sentiment (new)
- `supply_demand/demand_alerts.py`, `supply_demand/zone_edge.py` — wiring +
  `skipped_knife` / `skipped_mood`
- `chart_maps/board.py` — `_knife_decor`, `KNIFE_BADGE_TEXT`
- `frontend/src/pages/Alerts.tsx` — the three skip reasons, non-zero only
- `studies/bounce_quality_study.py` + three `stationary_bottom_*_study.py`
