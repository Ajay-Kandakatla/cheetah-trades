"""Walk-forward backtest for the DEMAND-ZONE RE-ENTRY rule.

Ajay 2026-08-16: *"I want you to look at data historically and tell me if buy
zones worked.. Record further if you want but I want you to back test and record
and load them up there."*

This is a different question from `sd_backtest.py`, which tests the intraday
liquidity-SWEEP strategy. This one tests the rule that actually drives the Back
in Demand board: **price left a demand band it had tested, came back down into
it, the trend is not a falling knife, and the band is good enough.**

ONE RULE, NOT TWO
-----------------
Every decision here goes through `demand_reentry.decide_from_frame` — the exact
function the live board calls. It was extracted from `analyze_symbol` for this
purpose. A backtest that reimplements the rule tests a rule nobody trades;
`test_zone_backtest.py::test_backtest_and_live_agree_on_the_same_frame` pins
that the two cannot drift apart.

NO LOOKAHEAD — the five rules, carried over verbatim from sd_backtest.py
------------------------------------------------------------------------
1. The decision for day D sees bars **strictly up to and including D's close**
   and nothing after. `_upto` slices positionally before any zone is computed.
2. Entry is the **next session's OPEN**, never D's close. You cannot see a close
   and also trade it.
3. Outcomes walk forward bar by bar on daily OHLC after the entry bar.
4. A day whose range contains BOTH the stop and the target is scored a **LOSS**.
   Daily bars cannot say which came first, and assuming the win inflates every
   result.
5. Costs are charged on entry and exit.

WHAT WOULD MAKE THIS DISHONEST, AND WHAT STOPS IT
--------------------------------------------------
* **Re-entry episodes last several days.** Price sits inside a band for a week
  and each day re-qualifies, so counting every day would record the same trade
  five times and let one good week dominate the sample. Only the FIRST bar of an
  episode is recorded; `EPISODE_COOLDOWN_BARS` governs when a new one may start.
* **Survivorship.** The universe is read from the current scan, so names that
  delisted are absent and the result is biased upward. Stated in the output as
  `survivorship_note` rather than buried here — it cannot be fixed without a
  point-in-time universe we do not have.
* **Unresolved trades are not wins.** A position still open at the end of the
  data is `outcome="open"` and is excluded from the win rate, with its count
  reported.

Not a book method. Not advice. Past behaviour of a rule on historical bars is
not a forecast.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("supply_demand.zone_backtest")

# Bars the decision needs before it can be made at all (mirrors
# demand_reentry.MIN_BARS — a shorter frame is not a read).
from .demand_reentry import MIN_BARS  # noqa: E402

# How long a trade is given to reach target or stop before it is abandoned.
# Zone re-entries are swing trades, not the 1-5 day holds sd_backtest measures.
MAX_HOLD_BARS = 60

# A new episode for the same symbol may not start within this many bars of the
# previous one. Without it a single multi-week stay inside a band records as
# dozens of "trades".
EPISODE_COOLDOWN_BARS = 20

# Round-trip cost, charged per side. Same value as sd_backtest.
COST_BPS_PER_SIDE = 2.0

# Decision days are sampled every N bars to bound runtime. 1 = every bar.
# The cooldown already collapses consecutive days of one episode, so a stride
# above 1 trades recall for speed rather than changing what qualifies.
DEFAULT_STRIDE = 1

OUTCOME_WIN = "target_first"
OUTCOME_LOSS = "stop_first"
OUTCOME_OPEN = "open"
OUTCOME_TIMEOUT = "expired"
# The next session opened beyond the stop or the target, so the plan never
# existed at a tradeable price. Voided, not scored either way — see
# `walk_forward`.
OUTCOME_GAPPED = "gapped"


def _upto(df, i: int):
    """Bars 0..i inclusive — the lookahead firewall. PURE."""
    return df.iloc[:i + 1]


def _net(entry: float, exit_px: float) -> float:
    """Percent return after costs on both sides. PURE."""
    if not entry:
        return 0.0
    gross = (exit_px / entry) - 1.0
    return round((gross - 2 * COST_BPS_PER_SIDE / 10_000.0) * 100.0, 3)


def walk_forward(df, entry_idx: int, stop: float, target: float,
                 max_hold: int = MAX_HOLD_BARS) -> dict:
    """Score one trade from its entry bar. PURE.

    Entry is the OPEN of `entry_idx`. Rule 4 applies: a bar that touches both
    levels is a loss.
    """
    if entry_idx >= len(df):
        return {"outcome": OUTCOME_OPEN, "bars": 0, "exit": None, "net_pct": None}
    entry = float(df["open"].iloc[entry_idx])
    if not entry or entry <= 0:
        return {"outcome": OUTCOME_OPEN, "bars": 0, "exit": None, "net_pct": None}

    # THE PLAN MUST STILL EXIST AT THE OPEN.
    #
    # Found 2026-08-16 by adversarial review of this very file. The loop below
    # starts at the entry bar, so a name that gapped overnight THROUGH a level
    # satisfied `lo <= stop` (or `hi >= target`) on bar one and was booked out
    # AT that level — a price it never traded at after entry.
    #
    # The damage was not marginal. 56 of 694 trades (8.1%) were mis-signed, and
    # they contributed +83.6pp against a whole-sample P&L of +23.5pp — more than
    # the entire result. SNDK 2026-07-27: plan stop 1258.17, next open 1173.60,
    # scored "stop_first" at net +7.166%. A loss that made seven percent.
    #
    # If price opened past a level you never got the entry, so the trade is
    # VOID: not a win, not a loss, and excluded from the raced denominator.
    if entry <= stop or entry >= target:
        return {"outcome": OUTCOME_GAPPED, "bars": 0, "exit": None,
                "net_pct": None, "gapped_through": "stop" if entry <= stop else "target"}

    hi_col, lo_col = df["high"], df["low"]
    last = min(len(df) - 1, entry_idx + max_hold)
    max_gain = 0.0
    for j in range(entry_idx, last + 1):
        hi, lo = float(hi_col.iloc[j]), float(lo_col.iloc[j])
        max_gain = max(max_gain, (hi / entry - 1.0) * 100.0)
        hit_stop = lo <= stop
        hit_target = hi >= target
        if hit_stop and hit_target:
            # Rule 4 — a daily bar cannot order the two touches.
            return {"outcome": OUTCOME_LOSS, "bars": j - entry_idx,
                    "exit": stop, "net_pct": _net(entry, stop),
                    "max_gain_pct": round(max_gain, 2), "ambiguous_bar": True}
        if hit_stop:
            return {"outcome": OUTCOME_LOSS, "bars": j - entry_idx,
                    "exit": stop, "net_pct": _net(entry, stop),
                    "max_gain_pct": round(max_gain, 2)}
        if hit_target:
            return {"outcome": OUTCOME_WIN, "bars": j - entry_idx,
                    "exit": target, "net_pct": _net(entry, target),
                    "max_gain_pct": round(max_gain, 2)}

    ran_out_of_data = last >= len(df) - 1 and (entry_idx + max_hold) >= len(df) - 1
    close = float(df["close"].iloc[last])
    return {"outcome": OUTCOME_OPEN if ran_out_of_data else OUTCOME_TIMEOUT,
            "bars": last - entry_idx, "exit": close,
            "net_pct": _net(entry, close), "max_gain_pct": round(max_gain, 2)}


BENCHMARK = "SPY"


def benchmark_return(bench_df, start_date: str, bars_held: int) -> Optional[float]:
    """SPY's return over the SAME window this trade was held. PURE.

    The single most important thing missing from the first version of this
    backtest. A dip-buying rule run through a 25% bull market produces positive
    raw returns whether or not the rule has any skill — the question is not
    "did it make money", it is "did it beat owning the same days".
    """
    if bench_df is None or len(bench_df) == 0 or not start_date:
        return None
    try:
        dates = bench_df.index.strftime("%Y-%m-%d")
    except Exception:
        return None
    idx = None
    for k, d in enumerate(dates):
        if d >= start_date:
            idx = k
            break
    if idx is None or idx >= len(bench_df):
        return None
    end = min(len(bench_df) - 1, idx + max(0, int(bars_held)))
    a = float(bench_df["open"].iloc[idx])
    b = float(bench_df["close"].iloc[end])
    if a <= 0:
        return None
    return round((b / a - 1.0) * 100.0, 3)


def _date_at(df, i: int) -> str:
    try:
        return str(df.index[i])[:10]
    except Exception:
        return ""


def observations_for(symbol: str, df, stride: int = DEFAULT_STRIDE,
                     max_hold: int = MAX_HOLD_BARS, bench_df=None) -> list:
    """Every recorded zone re-entry for one symbol, scored. PURE given `df`.

    Returns ledger-shaped dicts so `record()` can insert them unchanged.
    """
    from .demand_reentry import decide_from_frame

    out: list = []
    if df is None or len(df) < MIN_BARS + 2:
        return out

    last_episode = -10 ** 9
    for i in range(MIN_BARS, len(df) - 1, max(1, stride)):
        if i - last_episode < EPISODE_COOLDOWN_BARS:
            continue
        try:
            rec = decide_from_frame(_upto(df, i), symbol)
        except Exception as exc:
            log.debug("zone-backtest: %s bar %d failed: %s", symbol, i, exc)
            continue
        if not rec or not rec.get("is_reentry"):
            continue
        plan = rec.get("plan") or {}
        stop, target = plan.get("stop"), plan.get("target")
        entry_ref = plan.get("entry_ref")
        if not all(isinstance(x, (int, float)) and x > 0 for x in (stop, target)):
            continue
        if target <= stop:
            continue

        last_episode = i
        res = walk_forward(df, i + 1, float(stop), float(target), max_hold)
        zone = rec.get("entry_zone") or {}
        out.append({
            "kind": "zone",
            "symbol": symbol,
            "status": "confirmed",
            "et_date": _date_at(df, i),
            "confirmed_date": _date_at(df, i + 1),
            "obs_close": round(float(df["close"].iloc[i]), 4),
            "entry_open": round(float(df["open"].iloc[i + 1]), 4),
            "entry_ref": entry_ref,
            "stop": round(float(stop), 4),
            "target": round(float(target), 4),
            "rr": plan.get("rr"),
            "zone_lo": zone.get("lo"),
            "zone_hi": zone.get("hi"),
            "zone_touches": zone.get("touches"),
            "zone_strength": zone.get("strength"),
            "fell_from_pct": rec.get("fell_from_pct"),
            "outcome": res["outcome"],
            "bars_to_outcome": res["bars"],
            "net_pct": res.get("net_pct"),
            "max_gain_pct": res.get("max_gain_pct"),
            "ambiguous_bar": bool(res.get("ambiguous_bar")),
            "bench_pct": benchmark_return(bench_df, _date_at(df, i + 1), res["bars"]),
            "resolved": res["outcome"] in (OUTCOME_WIN, OUTCOME_LOSS),
            "gapped_through": res.get("gapped_through"),
            "backtested": True,
        })
    return out


def summarize(obs: list, label: str = "all") -> dict:
    """Honest summary. Open trades are excluded from the win rate, not counted
    as anything. PURE."""
    wins = [o for o in obs if o.get("outcome") == OUTCOME_WIN]
    losses = [o for o in obs if o.get("outcome") == OUTCOME_LOSS]
    opens = [o for o in obs if o.get("outcome") == OUTCOME_OPEN]
    timeouts = [o for o in obs if o.get("outcome") == OUTCOME_TIMEOUT]
    gapped = [o for o in obs if o.get("outcome") == OUTCOME_GAPPED]
    raced = len(wins) + len(losses)

    def _avg(rows, key):
        vals = [r.get(key) for r in rows if isinstance(r.get(key), (int, float))]
        return round(sum(vals) / len(vals), 2) if vals else None

    win_pct = round(100.0 * len(wins) / raced, 1) if raced else None
    aw, al = _avg(wins, "net_pct"), _avg(losses, "net_pct")
    # Mean net over every raced trade. Mathematically identical to
    # p*avg_win + (1-p)*avg_loss, but it survives a cohort with no losses (or
    # no wins), where the two-term form divides by a missing average and
    # reports None for a perfectly well-defined number.
    _raced_nets = [o.get("net_pct") for o in (wins + losses)
                   if isinstance(o.get("net_pct"), (int, float))]
    expectancy = (round(sum(_raced_nets) / len(_raced_nets), 2)
                  if _raced_nets else None)

    same_bar = sum(1 for o in wins if o.get("bars_to_outcome") == 0)
    # Excess over holding the index for the identical days. THE number.
    excess = [round(o["net_pct"] - o["bench_pct"], 3)
              for o in (wins + losses)
              if isinstance(o.get("net_pct"), (int, float))
              and isinstance(o.get("bench_pct"), (int, float))]
    beat = sum(1 for e in excess if e > 0)
    return {
        "label": label,
        "n": len(obs),
        "raced": raced,
        "wins": len(wins),
        "losses": len(losses),
        "open": len(opens),
        "expired": len(timeouts),
        # Opened beyond stop or target — the plan never existed at a tradeable
        # price. Never scored as either outcome.
        "gapped": len(gapped),
        "win_pct": win_pct,
        "avg_win_pct": aw,
        "avg_loss_pct": al,
        # THE HEADLINE NUMBER, not win_pct. A 0.17R target sitting 0.19% above
        # entry "wins" almost every time and pays almost nothing, so win rate
        # rises while the account does not. Expectancy prices that correctly.
        "expectancy_pct": expectancy,
        # Raw expectancy minus what SPY did over the same holding windows. A
        # dip-buying rule in a bull market shows positive raw returns with or
        # without skill; this is the only column that separates the two.
        "excess_vs_spy_pct": (round(sum(excess) / len(excess), 3) if excess else None),
        "beat_spy_pct": _pct_of(beat, len(excess)),
        "median_rr": _median_of(obs, "rr"),
        "median_bars_to_win": (sorted(o["bars_to_outcome"] for o in wins)[len(wins) // 2]
                               if wins else None),
        # Wins resolved on the ENTRY bar itself. A high count means the target
        # was inside the entry day's range — the plan was barely a trade.
        "same_bar_wins": same_bar,
        "same_bar_win_pct": _pct_of(same_bar, len(wins)),
        "ambiguous_bars": sum(1 for o in obs if o.get("ambiguous_bar")),
        "note": ("Read expectancy_pct, not win_pct. win_pct counts RACED trades "
                 "only (target or stop hit); open and expired are reported "
                 "separately, never as wins. A bar touching both levels is a "
                 "loss. same_bar_wins are targets hit on the entry bar — the "
                 "live board applies no minimum R:R, so trivially close targets "
                 "inflate win rate while paying nothing."),
    }


def _median_of(rows, key):
    vals = sorted(r.get(key) for r in rows if isinstance(r.get(key), (int, float)))
    return round(vals[len(vals) // 2], 2) if vals else None


def _pct_of(n, d):
    return round(100.0 * n / d, 1) if d else None


# ---------------------------------------------------------------------------
# Runner + ledger
# ---------------------------------------------------------------------------
LEDGER_KIND = "zone"


def _universe(limit: Optional[int] = None) -> list:
    """Liquid names to test, largest tape first.

    SURVIVORSHIP: this is TODAY's universe, so names that delisted or were
    acquired never appear and the result is biased upward. We have no
    point-in-time universe to fix it with, so it is reported, not hidden.
    """
    from sepa import scanner
    rows = (scanner.load_latest() or {}).get("all_results") or []
    liquid = []
    for r in rows:
        sym = (r.get("symbol") or "").upper()
        dv = (r.get("liquidity") or {}).get("avg_dollar_vol")
        px = r.get("last_close")
        if not sym or not isinstance(dv, (int, float)) or dv < 20_000_000:
            continue
        if not isinstance(px, (int, float)) or px < 10:
            continue
        liquid.append((dv, sym))
    liquid.sort(reverse=True)
    syms = [s for _, s in liquid]
    return syms[:limit] if limit else syms


def run(symbols: Optional[list] = None, limit: Optional[int] = 300,
        period: str = "5y", stride: int = DEFAULT_STRIDE,
        max_hold: int = MAX_HOLD_BARS, workers: int = 6) -> dict:
    """Backtest the zone re-entry rule across the liquid universe."""
    from concurrent.futures import ThreadPoolExecutor
    from sepa import prices

    syms = [s.upper() for s in (symbols or _universe(limit))]
    log.info("zone-backtest: %d symbols, period=%s stride=%d", len(syms), period, stride)

    try:
        bench_df = prices.load_prices(BENCHMARK, period=period)
    except Exception as exc:
        log.warning("zone-backtest: benchmark load failed: %s", exc)
        bench_df = None

    def one(sym):
        try:
            df = prices.load_prices(sym, period=period)
        except Exception as exc:
            log.debug("zone-backtest: prices %s failed: %s", sym, exc)
            return []
        try:
            return observations_for(sym, df, stride=stride, max_hold=max_hold,
                                    bench_df=bench_df)
        except Exception as exc:
            log.debug("zone-backtest: %s failed: %s", sym, exc)
            return []

    obs: list = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for got in pool.map(one, syms):
            obs.extend(got)

    def _rr_at_least(x):
        return [o for o in obs if isinstance(o.get("rr"), (int, float)) and o["rr"] >= x]

    strong = [o for o in obs if (o.get("zone_strength") or 0) >= 60]
    deep = [o for o in obs if (o.get("fell_from_pct") or 0) >= 10]
    dates = sorted(o["et_date"] for o in obs if o.get("et_date"))
    return {
        "symbols": len(syms),
        # `period` is REPORTED, not trusted: sepa.prices.load_prices serves a
        # cached frame and ignores it, so period="5y" silently returns whatever
        # the cache holds (measured 2026-08-16: 500 bars for every value). The
        # decision-day span below is what actually happened.
        "period_requested": period,
        "decision_days": {"first": dates[0] if dates else None,
                          "last": dates[-1] if dates else None,
                          "n": len(dates)},
        "period": period,
        "stride": stride,
        "max_hold_bars": max_hold,
        "overall": summarize(obs, "all zone re-entries"),
        # R:R cohorts FIRST: they are the ones that decide whether the rule is
        # tradeable, because the live board applies no R:R floor of its own.
        "by_cohort": [summarize(_rr_at_least(1.0), "planned R:R >= 1"),
                      summarize(_rr_at_least(2.0), "planned R:R >= 2"),
                      summarize(_rr_at_least(3.0), "planned R:R >= 3"),
                      summarize(strong, "zone strength >= 60"),
                      summarize(deep, "fell >= 10% from the band top")],
        "observations": obs,
        "survivorship_note": (
            "Universe is TODAY's liquid names, so delisted and acquired tickers "
            "are absent. This biases results UPWARD and cannot be corrected "
            "without a point-in-time universe we do not have."),
        "disclaimer": ("Historical behaviour of a rule on past bars. Not a "
                       "forecast, not advice."),
    }


def record(obs: list, replace: bool = True) -> dict:
    """Write backtested observations into the pattern ledger as kind='zone'.

    Marked `backtested: True` so they are never mistaken for live-recorded
    observations. `replace` clears prior backtested zone rows first, so re-runs
    do not accumulate duplicates of the same trade.
    """
    from patterns import history
    coll = history._coll()
    if coll is None:
        return {"ok": False, "reason": "ledger unavailable", "written": 0}

    removed = 0
    if replace:
        try:
            removed = coll.delete_many({"kind": LEDGER_KIND,
                                        "backtested": True}).deleted_count
        except Exception as exc:
            return {"ok": False, "reason": f"purge failed: {exc}", "written": 0}

    rows = [dict(o) for o in obs if o.get("symbol") and o.get("et_date")]
    if not rows:
        return {"ok": True, "written": 0, "removed": removed}
    try:
        coll.insert_many(rows, ordered=False)
    except Exception as exc:
        return {"ok": False, "reason": f"insert failed: {exc}", "written": 0,
                "removed": removed}
    return {"ok": True, "written": len(rows), "removed": removed}


def main(argv=None):
    import argparse, json as _json
    ap = argparse.ArgumentParser(description="Backtest the demand-zone re-entry rule")
    ap.add_argument("--limit", type=int, default=300, help="symbols to test")
    ap.add_argument("--period", default="5y")
    ap.add_argument("--stride", type=int, default=DEFAULT_STRIDE)
    ap.add_argument("--max-hold", type=int, default=MAX_HOLD_BARS)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--symbols", default="", help="comma-separated override")
    ap.add_argument("--record", action="store_true", help="write results to the ledger")
    a = ap.parse_args(argv)

    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()] or None
    res = run(symbols=syms, limit=a.limit, period=a.period, stride=a.stride,
              max_hold=a.max_hold, workers=a.workers)
    obs = res.pop("observations")
    if a.record:
        res["recorded"] = record(obs)
    print(_json.dumps(res, indent=2, default=str))
    return res


if __name__ == "__main__":
    main()
