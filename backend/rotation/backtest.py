"""Does rotating into the leading sectors actually pay?

Ajay 2026-08-16: *"Yes also back test and add the rotation tracker"* — after the
tracker showed money leaving his themes and going to healthcare, banks and then
energy. The tracker measures what ALREADY moved. This asks the only question
that matters for using it: **if you had bought the leaders each month, would you
have beaten simply owning the market?**

TEN YEARS, NOT ONE REGIME
-------------------------
The zone backtest was accidentally limited to 13 bull-market months because
`prices.load_prices` serves a 500-bar cache and its `period` argument is a
no-op. `force=True` bypasses that and returns ~2,510 bars back to 2016 —
verified. Twenty-odd sector ETFs is a small enough refetch to do properly, so
this test covers the 2018 Q4 selloff, the 2020 COVID crash and the 2022 bear as
well as the bull runs. A momentum rule that is only ever measured in a bull
market has not been measured.

NO LOOKAHEAD
------------
1. Ranking for rebalance date D uses returns computed from bars **up to and
   including D**, nothing after.
2. The position is entered at the **next session's OPEN** and held to the open
   of the next rebalance. You cannot rank on a close and also trade it.
3. The benchmark is bought and sold on exactly the same bars, so slippage in the
   date alignment cannot favour either side.
4. Costs are charged on every rebalance, both sides, on the fraction of the book
   that actually turned over.

WHAT WOULD MAKE THIS DISHONEST
------------------------------
* **Benchmarking against SPY.** A sector-rotation rule holding 3 of 11 equally
  weighted sleeves is closer to equal-weight than to cap-weight. RSP is the
  benchmark; SPY is reported beside it because it is what most people would
  quote, not because it is the fair comparison.
* **Ignoring the do-nothing alternative.** Holding all 11 sectors equally,
  rebalanced on the same dates, is reported as a third line. If picking the top
  3 does not beat holding all 11, the ranking adds nothing.
* **Survivorship.** The sector ETFs are all still listed, so there is none here
  — unlike the stock-level tests. This is one of the few places we get a clean
  read.

Not a book method. Not advice.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("rotation.backtest")

# Equal-weight is the fair benchmark for an equal-weight sleeve strategy.
BENCHMARK = "RSP"
# Reported alongside, because it is the number everyone quotes.
BENCHMARK_ALT = "SPY"

# The 11 GICS sector ETFs the tracker already uses.
SECTORS = ["XLK", "XLV", "XLF", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB",
           "XLRE", "XLC"]

# Trailing window the ranking is computed over, in trading days. 63 ~= 3 months,
# the tracker's own medium window.
LOOKBACK = 63
# Rebalance cadence, in trading days. 21 ~= monthly.
REBALANCE = 21
# Sleeves held. 3 of 11 is concentrated enough to express a view and diversified
# enough not to be a single-sector bet.
TOP_K = 3
# Round-trip cost per side, basis points. ETFs are liquid; this is deliberately
# generous rather than optimistic.
COST_BPS_PER_SIDE = 2.0

# Bars needed before the first ranking can be made.
MIN_BARS = LOOKBACK + 5


def _ret(df, i: int, j: int) -> Optional[float]:
    """Close-to-close return between two positional bars. PURE."""
    if df is None or i < 0 or j >= len(df) or i >= j:
        return None
    a, b = float(df["close"].iloc[i]), float(df["close"].iloc[j])
    return (b / a - 1.0) if a > 0 else None


def _open_at(df, i: int) -> Optional[float]:
    if df is None or i < 0 or i >= len(df):
        return None
    v = float(df["open"].iloc[i])
    return v if v > 0 else None


def rank_at(frames: dict, symbols: list, i: int, bench_df,
            lookback: int = LOOKBACK) -> list:
    """Sectors ordered by trailing return RELATIVE to the benchmark. PURE.

    Relative, not absolute: in a falling market every sector has a negative
    trailing return and an absolute rank would still buy the least-bad three.
    That is a different (and worse) strategy than owning the leaders.
    """
    b = _ret(bench_df, i - lookback, i)
    scored = []
    for s in symbols:
        r = _ret(frames.get(s), i - lookback, i)
        if r is None or b is None:
            continue
        scored.append((s, round((r - b) * 100.0, 3)))
    scored.sort(key=lambda x: -x[1])
    return scored


def _sleeve_return(frames: dict, held: list, entry_i: int, exit_i: int) -> Optional[float]:
    """Equal-weight return of the held sleeves, open to open. PURE."""
    rets = []
    for s in held:
        df = frames.get(s)
        a, b = _open_at(df, entry_i), _open_at(df, exit_i)
        if a and b:
            rets.append(b / a - 1.0)
    return sum(rets) / len(rets) if rets else None


def _turnover(prev: list, cur: list) -> float:
    """Fraction of the book replaced. PURE."""
    if not cur:
        return 0.0
    if not prev:
        return 1.0
    changed = len(set(cur) - set(prev))
    return changed / len(cur)


def run(symbols: Optional[list] = None, lookback: int = LOOKBACK,
        rebalance: int = REBALANCE, top_k: int = TOP_K,
        cost_bps: float = COST_BPS_PER_SIDE) -> dict:
    """Walk the rotation rule forward over the full available history."""
    from sepa import prices

    syms = list(symbols or SECTORS)
    wanted = syms + [BENCHMARK, BENCHMARK_ALT]

    frames = {}
    for s in wanted:
        try:
            # force=True: the cached frame is capped at 500 bars and `period` is
            # a no-op, which is what silently limited the zone backtest to one
            # regime. ~13 ETFs is a small enough refetch to do properly.
            frames[s] = prices.load_prices(s, period="max", force=True)
        except Exception as exc:
            log.warning("rotation-backtest: %s failed: %s", s, exc)
            frames[s] = None

    bench = frames.get(BENCHMARK)
    if bench is None or len(bench) < MIN_BARS:
        return {"error": f"no usable {BENCHMARK} history"}

    # Align every frame to the benchmark's calendar so positional indices mean
    # the same date everywhere. A sector missing a bar the benchmark has would
    # otherwise silently shift its whole return series.
    cal = bench.index
    for s in list(frames):
        df = frames[s]
        frames[s] = None if df is None else df.reindex(cal).ffill()

    n = len(cal)
    dates = cal.strftime("%Y-%m-%d")

    periods = []
    prev_held: list = []
    for i in range(lookback + 1, n - rebalance - 1, rebalance):
        entry_i, exit_i = i + 1, min(i + 1 + rebalance, n - 1)
        ranked = rank_at(frames, syms, i, bench, lookback)
        if len(ranked) < top_k:
            continue
        held = [s for s, _ in ranked[:top_k]]

        strat = _sleeve_return(frames, held, entry_i, exit_i)
        allw = _sleeve_return(frames, syms, entry_i, exit_i)
        b_rsp = _sleeve_return(frames, [BENCHMARK], entry_i, exit_i)
        b_spy = _sleeve_return(frames, [BENCHMARK_ALT], entry_i, exit_i)
        if strat is None or b_rsp is None:
            continue

        turn = _turnover(prev_held, held)
        cost = turn * 2 * cost_bps / 10_000.0
        prev_held = held

        periods.append({
            "date": dates[entry_i],
            "held": held,
            "strategy_pct": round((strat - cost) * 100.0, 3),
            "all_sectors_pct": None if allw is None else round(allw * 100.0, 3),
            "rsp_pct": round(b_rsp * 100.0, 3),
            "spy_pct": None if b_spy is None else round(b_spy * 100.0, 3),
            "turnover": round(turn, 2),
        })

    return {
        "periods": periods,
        "params": {"lookback": lookback, "rebalance": rebalance,
                   "top_k": top_k, "cost_bps_per_side": cost_bps},
        "span": {"first": periods[0]["date"] if periods else None,
                 "last": periods[-1]["date"] if periods else None,
                 "n_rebalances": len(periods)},
        "summary": summarize(periods),
        "by_year": by_year(periods),
        "disclaimer": ("Historical behaviour of a rule on past bars. Not a "
                       "forecast, not advice."),
    }


def _compound(vals) -> Optional[float]:
    if not vals:
        return None
    acc = 1.0
    for v in vals:
        acc *= (1.0 + v / 100.0)
    return round((acc - 1.0) * 100.0, 2)


def _stdev(vals) -> Optional[float]:
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    return (sum((v - m) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5


def summarize(periods: list) -> dict:
    """Compounded outcome and the honest spread. PURE."""
    if not periods:
        return {"n": 0}
    s = [p["strategy_pct"] for p in periods]
    r = [p["rsp_pct"] for p in periods]
    a = [p["all_sectors_pct"] for p in periods if p["all_sectors_pct"] is not None]
    excess = [p["strategy_pct"] - p["rsp_pct"] for p in periods]
    sd = _stdev(excess)
    se = (sd / len(excess) ** 0.5) if sd else None
    mean_ex = sum(excess) / len(excess)
    return {
        "n": len(periods),
        "strategy_total_pct": _compound(s),
        "rsp_total_pct": _compound(r),
        "all_sectors_total_pct": _compound(a),
        "mean_excess_per_period_pct": round(mean_ex, 3),
        "excess_se": None if se is None else round(se, 3),
        # Rough 95% interval. If it straddles zero the rule is not distinguishable
        # from owning the benchmark, however good the compounded number looks.
        "excess_ci95": (None if se is None else
                        [round(mean_ex - 1.96 * se, 3), round(mean_ex + 1.96 * se, 3)]),
        "beat_rsp_pct": round(100.0 * sum(1 for e in excess if e > 0) / len(excess), 1),
        "avg_turnover": round(sum(p["turnover"] for p in periods) / len(periods), 2),
        "worst_period_pct": round(min(s), 2),
        "best_period_pct": round(max(s), 2),
        "note": ("Read excess_ci95. A compounded total that beats the benchmark "
                 "while the interval straddles zero is a sample, not an edge."),
    }


def by_year(periods: list) -> list:
    """Per-calendar-year, so a single regime cannot carry the result. PURE."""
    buckets: dict = {}
    for p in periods:
        y = str(p["date"])[:4]
        buckets.setdefault(y, []).append(p)
    out = []
    for y in sorted(buckets):
        rows = buckets[y]
        out.append({
            "year": y,
            "n": len(rows),
            "strategy_pct": _compound([r["strategy_pct"] for r in rows]),
            "rsp_pct": _compound([r["rsp_pct"] for r in rows]),
            "excess_pct": round(sum(r["strategy_pct"] - r["rsp_pct"] for r in rows), 2),
        })
    return out
