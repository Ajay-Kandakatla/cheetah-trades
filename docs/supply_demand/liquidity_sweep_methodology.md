# Liquidity sweeps — methodology, and the backtest that killed the strategy

_Added 2026-08-13. Ajay asked for a supply/demand strategy **independent of
Minervini** ("The Supply demand are outside of this strategy"), built on
"Demand zones and Prints and darkpools … to track smart money and how they use
stop losses to entry and lower price", then asked for it to be backtested._

> **BOTTOM LINE: the sweep strategy did not survive its own backtest.** It is
> NOT shipped as a signal board. What shipped is the falling-knife guard (which
> measured well), the instrumentation, and this record. Read
> [§ Results](#results) before reviving the idea.

## The idea

Retail protective stops rest just BELOW an obvious support band. Those stops are
resting sell orders — the only pool of guaranteed supply. A size buyer pushes
price *through* the floor, triggers them, absorbs the forced selling cheaper,
and lets price return. Mechanically:

1. price pierces the band floor by ≥ `MIN_PIERCE_PCT` (stops hit)
2. it closes back above the floor within `RECLAIM_MAX_BARS` (reclaim)
3. the sweep bar trades ≥ `MIN_SWEEP_VOL_X` of local average volume (absorption)

The payoff for detecting it is the **sweep low** — where forced sellers were
filled, and therefore a real stop reference instead of a guessed buffer.

Lineage: Wyckoff's *spring* / the modern "liquidity grab". Not a book method
here; every threshold is a configured house value.

## Why the levels are built the way they are

Measured across three horizons on 2026-08-13:

| Zone source | Result |
|---|---|
| **Daily** bands | Sit too far from price to ever be swept — VRT's daily demand band was $158–162 against a $288 price. Every symbol read `intact`. |
| **One session** of 1-min bars | Bands ~0.3% wide, sweeps ~0.24%. Real, but noise for a multi-day hold. |
| **Ten sessions** of intraday bars | CAT band $852.11–861.58 (1.11% wide, 8× tested) swept to $842.11 and reclaimed in 1 bar on **11.9×** volume. Tradeable. |

Hence `LOOKBACK_SESSIONS = 10`, `SWING_WINDOW = 12`, `MERGE_PCT = 1.2`,
`HALF_WIDTH_PCT = 0.45` — passed per-call into `price_zones.compute`, leaving
the `/zones` page defaults untouched.

## Results

`sd_backtest.py`, walk-forward, 20 liquid names, 60 days, 2bp costs each way.

### Multi-day (Ajay's stated horizon: "a day or two, sometimes a week")

| Target | Hold | n | Win rate | Avg win | Avg loss | **Expectancy** |
|---|---|---|---|---|---|---|
| Nearest supply | 5d | 65 | 53.8% | +0.65% | −0.73% | **+0.01%** |
| 2R | 5d | 152 | 48.0% | +1.71% | −1.83% | **−0.13%** |
| 3R | 5d | 169 | 39.1% | +2.45% | −2.07% | **−0.31%** |
| 2R | 10d | 152 | 47.4% | +1.81% | −1.91% | **−0.15%** |
| 3R | 10d | 169 | 37.3% | +2.79% | −2.13% | **−0.30%** |

### Intraday (the horizon Osler's research actually supports)

| Target | n | Win rate | **Expectancy** |
|---|---|---|---|
| 1.5R / ~3h | 236 | 41.9% | **−0.25%** |
| 2R / ~3h | 236 | 39.8% | **−0.26%** |
| 3R / ~3h | 236 | 38.6% | **−0.23%** |
| 2R, vol ≥ 2× | 141 | 38.3% | **−0.44%** |

### Why this is "no edge" and not "needs tuning"

1. **Widening the target makes expectancy WORSE.** Win rate falls faster than
   payoff rises (54% → 48% → 39% as targets go 0.3R → 2R → 3R). A real edge
   would improve as you let it run. This is the signature of a random walk
   after entry.
2. **The absorption filter hurts.** Requiring vol ≥ 2× on the sweep bar made
   every intraday cohort worse. If "someone big was filling here" carried
   information, that filter would help.
3. **Osler predicted it.** Stop-cascade effects are significant *for hours, not
   days* — and our intraday test says even the hours version doesn't survive
   costs on US large-cap equities in this window.

### What the original design got wrong (fixed, still lost)

- **Median planned R:R was 0.26** — risking 1.4% to make 0.36%. Unwinnable at
  any hit rate. The target was "nearest supply band", which with this tight
  geometry often sat on top of the demand band.
- **214 of 300 setups never got a fillable entry** — price gapped past the
  target or through the stop overnight. With levels ~1% apart, one overnight
  gap covers both.

## Two backtest bugs found and fixed (both would have lied)

1. **Gaps scored as wins-at-a-loss.** A next-open gap *above* the target was
   recorded as a "target hit" that settled below the fill, producing a
   contradictory *140 target hits at an 11% win rate*. Entries that gap out of
   the setup are now `gap_past_target` / `gap_below_stop` and are **not trades**.
2. **Same-day ambiguity crushed everything.** When a daily bar's range contains
   both stop and target, daily OHLC cannot say which came first. Scoring all of
   them losses was defensible but distorting; those days are now resolved by
   replaying that day's **intraday bars in order**, falling back to the
   conservative loss only when intraday data is missing.

Locked by `tests/test_sd_liquidity.py`. The single most important test is
`test_window_upto_cannot_see_the_future` — the lookahead firewall. If it ever
breaks, every number above becomes fiction.

## The one thing that DID work: the falling-knife guard

`sd_liquidity.is_falling_knife` — swing lows stepping DOWN **and** a falling
50-day average. Both must agree, so a single shakeout low inside an uptrend does
not disqualify a zone.

It improved expectancy in **every** configuration tested, and the knives-only
cohort was the worst performer in all of them.

It has therefore **replaced the Minervini trend template** as the gate in
`demand_reentry.py`. The template was not just off-strategy, it was doing the
job badly: on 2026-08-13 it passed CIEN at **7/8** while CIEN's swing lows read
424 → 404 → 359 → 323, its 50-day was falling, and its big prints ran 7:1 to the
sell side. Three of that day's four board names (CIEN, VRT, CAT) were falling
knives the template waved through. After the swap, all three dropped off.

## Limits of this study

- 60 days, 20 large-caps, one market regime. Small sample, wide error bars.
- Survivorship: today's symbol list.
- Costs modelled at 2bp/side with no slippage or borrow; real fills are worse,
  so the true numbers are lower than shown, not higher.
- It does **not** prove sweeps never work — only that this implementation, on
  these names, over this window, on both tested horizons, did not.

## What is shipped

| Module | Status |
|---|---|
| `sd_liquidity.py` | shipped — sweep detector + knife guard (the guard is live in `demand_reentry`) |
| `sd_sweep.py` | shipped as instrumentation, **no signal board** |
| `sd_backtest.py` | shipped — `python -m supply_demand.sd_backtest [--intraday] [--rmult N]` |
| a "buy these sweeps" page | **not shipped**, deliberately |
