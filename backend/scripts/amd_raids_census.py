"""🌀 AMD raids census — DESCRIPTIVE density only (2026-09-24). READ-ONLY.

How many raids / chains `amd.find_raids` lists per name, how often a raid
re-sweeps an earlier raid's base, how long chains get, and what the two walks
cost — so the Support tile's chip and circles are sized against real frames.

NOT A MEASURED CLAIM. No outcome shares are printed on purpose: they have no
CI, no placebo, and chains inflate them. The only measured AMD claim in the app
is `rotation.hottest_amd.AMD_MEASURED` (INVERTED).

    PYTHONPATH=/app python -m scripts.amd_raids_census --sample 200 --seed 7

Reads the shared price cache (closed bars via
`demand_reentry.split_today_partial`); writes nothing.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics as st
import time

DIRS = ("bullish", "bearish")
ONE_YEAR = 252


def _q(xs, p):
    xs = sorted(xs)
    return xs[int(p * (len(xs) - 1))] if xs else None


def _dist(xs):
    return {"n": len(xs), "median": (st.median(xs) if xs else None),
            "p90": _q(xs, 0.9), "max": (max(xs) if xs else None)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sample", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--mode", default=None, help="sepa.universe mode (default: active)")
    args = ap.parse_args(argv)

    import pandas as pd
    from chart_maps.board import _norm_frame
    from sepa import prices
    from sepa.universe import load_universe
    from supply_demand import amd as A
    from supply_demand.demand_reentry import split_today_partial

    uni = list(dict.fromkeys(load_universe(args.mode)))
    random.seed(args.seed)
    sample = random.sample(uni, min(args.sample, len(uni)))

    rows_2y = {d: [] for d in DIRS}
    rows_1y = {d: [] for d in DIRS}
    chains_2y = {d: [] for d in DIRS}
    chains_1y = {d: [] for d in DIRS}
    longest = {d: [] for d in DIRS}
    resweeps = {d: 0 for d in DIRS}
    total = {d: 0 for d in DIRS}
    t_closed, t_synth, bars, skipped = [], [], [], 0

    for sym in sample:
        try:
            df = _norm_frame(prices.load_prices(sym))
        except Exception:                                      # noqa: BLE001
            df = None
        if df is None or len(df) < 60:
            skipped += 1
            continue
        closed, _partial = split_today_partial(df)
        n = len(closed)
        bars.append(n)
        t0 = time.perf_counter()
        walks = {d: A.find_raids(closed, direction=d) for d in DIRS}
        t_closed.append(time.perf_counter() - t0)

        nxt = (closed.index[-1] + pd.offsets.BDay(1)).strftime("%Y-%m-%d")
        px = float(closed["close"].iloc[-1])
        t0 = time.perf_counter()
        for d in DIRS:
            A.provisional_raid(closed, open_base=walks[d]["open_base"], date=nxt,
                               price=px, day_low=float(closed["low"].iloc[-1]),
                               day_high=float(closed["high"].iloc[-1]), direction=d)
        t_synth.append(time.perf_counter() - t0)

        cut = closed.index[max(0, n - ONE_YEAR)].strftime("%Y-%m-%d")
        for d in DIRS:
            rs = walks[d]["raids"]
            rs1 = [r for r in rs if (r.get("date") or "") >= cut]
            rows_2y[d].append(len(rs))
            rows_1y[d].append(len(rs1))
            chains_2y[d].append(len({r["chain_root"] for r in rs}))
            chains_1y[d].append(len({r["chain_root"] for r in rs1}))
            longest[d].append(max((r["sweep_seq"] for r in rs), default=0))
            resweeps[d] += sum(1 for r in rs if r["sweep_seq"] > 1)
            total[d] += len(rs)

    out = {
        "descriptive_only": True,
        "note": "density and timing only — no outcome shares (no CI, no placebo)",
        "sample": len(sample), "walked": len(bars), "skipped": skipped,
        "seed": args.seed, "bars_median": (st.median(bars) if bars else None),
        "per_direction": {
            d: {"rows_2y": _dist(rows_2y[d]), "rows_1y": _dist(rows_1y[d]),
                "chains_2y": _dist(chains_2y[d]), "chains_1y": _dist(chains_1y[d]),
                "longest_chain": _dist(longest[d]),
                "resweep_share": (round(resweeps[d] / total[d], 4) if total[d] else None),
                "resweeps": resweeps[d], "rows": total[d]}
            for d in DIRS},
        "resweep_share_both": (round(sum(resweeps.values()) / sum(total.values()), 4)
                               if sum(total.values()) else None),
        "timing_s": {"closed_walk_both_dirs": _dist([round(x, 4) for x in t_closed]),
                     "synthetic_walk_both_dirs": _dist([round(x, 4) for x in t_synth])},
    }
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main()
