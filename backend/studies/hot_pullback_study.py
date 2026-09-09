"""The Hot Pullback measurement, re-runnable.

    docker exec -i cheetah-market-app-api-1 sh -c \
        'cd /app && PYTHONPATH=/app python -u -' < studies/hot_pullback_study.py

WHY THIS FILE EXISTS. On 2026-09-09 this app shipped a board claiming 58% win
and +0.27R, and Ajay sizes real money off it. The number was wrong by ~2.3x.
The module, its docs, its tests and its paper lane all shipped; the backtest
that produced the number did not, so nothing could re-run it and nothing caught
the bug. Rule #4 says a methodology change ships its measurement. This is it.

THE BUG, so it cannot recur silently. The original feature pass computed the
rolling columns, called `dropna()`, and only THEN applied `rolling(252)`. That
made the first eligible event index 301 rather than 252 — an off-by-49 that
deleted the first 49 signal-eligible sessions: 17 trades running 23.5% win and
-0.418R, twelve of them on the 2025-11-06/07/11 market-wide flush days. The
backtest began one week after the sample's worst cluster.

`MIN_HISTORY_BARS = 252` below is the whole fix, and `--floor 300` reproduces
the original run exactly (stop count, target count and worst case to the
decimal) so the claim above is checkable rather than asserted.

NO LOOKAHEAD. Bands at bar j are computed from bars[:j] only, with
`max_zones=None` — the geometry `zone_store` itself passes. Anything less trims
the band list and finds far fewer events.
"""
import argparse
import sys

import numpy as np
import pandas as pd

from sepa import prices, universe
from supply_demand import price_zones, demand_reentry, hot_pullback as HP

MIN_HISTORY_BARS = 252      # the 52-week hot gate needs this many prior closes
HOLD_SESSIONS = 3           # the lane's clock
STOP_UNDER_LOW = 0.995      # 0.5% under the signal-day low
BOOTSTRAP_DRAWS = 20_000


def _frame(coll, sym):
    doc = coll.find_one({"symbol": sym}, {"bars": 1, "_id": 0})
    f = pd.DataFrame((doc or {}).get("bars") or [])
    if f.empty or "close" not in f:
        return None
    for c in ("open", "high", "low", "close", "volume"):
        if c not in f:
            f[c] = np.nan
        f[c] = pd.to_numeric(f[c], errors="coerce")
    f["d"] = f["date"].astype(str).str[:10]
    f = f.dropna(subset=["open", "high", "low", "close"]).sort_values("d")
    return f.reset_index(drop=True)


def events(floor: int = MIN_HISTORY_BARS, limit_names: int = 0) -> pd.DataFrame:
    """Every event the rule fires on, with its simulated trade."""
    coll = prices._get_mongo()
    geom = demand_reentry.zone_geom()
    syms = universe.load_universe("full")
    if limit_names:
        syms = syms[:limit_names]
    rows = []
    for i, sym in enumerate(syms):
        if i % 250 == 0:
            print(f"  {i}/{len(syms)}  events={len(rows)}", file=sys.stderr, flush=True)
        f = _frame(coll, sym)
        if f is None or len(f) < floor + HOLD_SESSIONS + 2:
            continue
        c, lo, hi, op = (f[k].values for k in ("close", "low", "high", "open"))
        # Feature windows mirror the live scan's non-live branch EXACTLY.
        ma21 = f["close"].rolling(HP.MA_LEN).mean().values           # includes bar j
        hi10 = f["high"].shift(1).rolling(HP.HIGH_LOOKBACK).max().values
        lo252 = f["close"].shift(1).rolling(252).min().values        # CLOSES, per live code
        dvol = (f["close"] * f["volume"]).rolling(50).median().values
        prev = f["close"].shift(1).values

        hot = (prev >= lo252 * (1 + HP.HOT_ABOVE_52W_LOW_PCT / 100.0)) & (dvol >= HP.MIN_DOLLAR_VOL_USD)
        flush = np.round((lo / hi10 - 1.0) * 100.0, 2)
        undma = np.round((c / ma21 - 1.0) * 100.0, 2)
        offlow = np.round(np.where(lo > 0, (c / lo - 1.0) * 100.0, np.nan), 2)
        rng = hi - lo
        rpos = np.round(np.where(rng > 0, (c - lo) / rng, np.nan), 3)

        # NOTE the snapback pair is NOT in this mask: it is measured as a gate
        # in report() instead, which needs the cohort it would have excluded.
        gate = (hot & (flush <= HP.FALL_FROM_10D_HIGH_PCT) & (undma <= HP.UNDER_MA21_PCT)
                & np.isfinite(offlow) & np.isfinite(rpos))
        for j in np.where(gate)[0]:
            j = int(j)
            if j < floor or j + HOLD_SESSIONS >= len(f):
                continue
            z = price_zones.compute(f.iloc[:j], last_price=float(c[j]),
                                    max_zones=None, **geom)
            band = HP.band_for_low(float(lo[j]), (z or {}).get("demand_zones") or [])
            # The no-band cohort is KEPT, not skipped. The module's original
            # headline was "the demand band is the load-bearing condition"; the
            # only way to check that is to trade the identical reversal without
            # one and compare. (It is not. See report().)
            entry = float(op[j + 1])
            stop = round(float(lo[j]) * STOP_UNDER_LOW, 2)
            if entry <= stop:
                continue
            target = float(ma21[j])
            exit_px, why = None, None
            for k in range(1, HOLD_SESSIONS + 1):
                t = j + k
                if lo[t] <= stop:
                    exit_px, why = stop, "stop"
                    break
                if target and hi[t] >= target:
                    exit_px, why = target, "target"
                    break
            if exit_px is None:
                exit_px, why = float(c[j + HOLD_SESSIONS]), "clock"
            rows.append({
                "symbol": sym, "date": f["d"].iloc[j],
                "has_band": bool(band),
                "snapback": bool(offlow[j] >= HP.OFF_LOW_PCT and rpos[j] >= HP.RANGE_POS_MIN),
                "flush": flush[j], "undma": undma[j],
                "trade_pct": (exit_px / entry - 1.0) * 100.0,
                "R": (exit_px - entry) / (entry - stop),
                "risk_pct": (entry - stop) / entry * 100.0,
                "why": why,
            })
    return pd.DataFrame(rows)


def _perm_p(a: np.ndarray, b: np.ndarray, draws: int = 20_000) -> float:
    """One-sided permutation p for mean(a) - mean(b), labels shuffled."""
    obs = a.mean() - b.mean()
    pool = np.concatenate([a, b])
    n = len(a)
    rng = np.random.default_rng(11)
    hits = 0
    for _ in range(draws):
        p = rng.permutation(pool)
        if (p[:n].mean() - p[n:].mean()) >= obs:
            hits += 1
    return hits / draws


def report(ALL: pd.DataFrame, floor: int) -> None:
    if ALL.empty:
        print("no events")
        return
    # The RULE is band + snapback. Everything else in ALL is a control cohort.
    D = ALL[ALL.has_band & ALL.snapback].reset_index(drop=True)
    if D.empty:
        print("no events pass the full rule")
        return
    R, T = D["R"], D["trade_pct"]
    print()
    print(f"floor=bar {floor}   n={len(D)}   dates={D.date.nunique()}   names={D.symbol.nunique()}")
    print(f"  window            {D.date.min()} -> {D.date.max()}")
    print(f"  win rate          {(R > 0).mean() * 100:.1f}%")
    print(f"  mean / median     {T.mean():+.2f}% / {T.median():+.2f}%")
    print(f"  avg win / loss    {T[R > 0].mean():+.2f}% / {T[R <= 0].mean():+.2f}%")
    print(f"  worst / best      {T.min():+.2f}% / {T.max():+.2f}%")
    print(f"  median risk       {D.risk_pct.median():.1f}%")
    print(f"  EXPECTANCY        {R.mean():+.3f}R")
    print(f"  exits             {D.why.value_counts().to_dict()}")

    # Bootstrap over DATES, not trades: the events cluster on market-wide flush
    # days, so a per-trade resample understates the interval.
    rng = np.random.default_rng(7)
    days = D.date.unique()
    by_day = {d: D[D.date == d]["R"].values for d in days}
    draws = np.empty(BOOTSTRAP_DRAWS)
    for i in range(BOOTSTRAP_DRAWS):
        pick = rng.choice(days, size=len(days), replace=True)
        draws[i] = np.concatenate([by_day[d] for d in pick]).mean()
    lo_ci, hi_ci = np.percentile(draws, [2.5, 97.5])
    print(f"  95% CI (by date)  {lo_ci:+.3f}R to {hi_ci:+.3f}R   P(R<=0)={float((draws <= 0).mean()):.3f}")

    one = D.sort_values("date").groupby("date").first()
    print(f"  ONE PER DATE      {one.R.mean():+.3f}R on {len(one)} trades, {(one.R > 0).mean()*100:.0f}% win")
    top = D.groupby("date")["R"].sum().idxmax()
    print(f"  drop {top}   {D[D.date != top].R.mean():+.3f}R")
    print()
    print("  WHICH GATE IS LOAD-BEARING (kept vs the cohort it excludes):")
    band_no = ALL[(~ALL.has_band) & ALL.snapback]["R"].values
    snap_no = ALL[ALL.has_band & (~ALL.snapback)]["R"].values
    for lab, other in (("demand band", band_no), ("snapback pair", snap_no)):
        if len(other) < 15:
            print(f"    {lab:<16} excluded cohort too small (n={len(other)})")
            continue
        print(f"    {lab:<16} kept {R.mean():+.3f}R  vs excluded {other.mean():+.3f}R "
              f"(n={len(other)})  separation {R.mean() - other.mean():+.3f}R  "
              f"p={_perm_p(R.values, other):.3f}")
    print()
    print("  flush depth (cumulative — the gate Ajay asked to loosen):")
    for cut in (-10, -12, -15, -20, -25, -30):
        s = D[D.flush <= cut]
        if len(s) >= 15:
            print(f"    <= {abs(cut):2d}%   n={len(s):4d}  {(s.R > 0).mean()*100:5.1f}% win  {s.R.mean():+.3f}R")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--floor", type=int, default=MIN_HISTORY_BARS,
                    help="min bars of history before an event counts. 300 reproduces "
                         "the invalidated 2026-09-09 run; 252 is correct.")
    ap.add_argument("--names", type=int, default=0, help="cap the universe (smoke runs)")
    a = ap.parse_args()
    report(events(a.floor, a.names), a.floor)
