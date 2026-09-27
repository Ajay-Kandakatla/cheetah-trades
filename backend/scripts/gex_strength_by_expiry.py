"""Does the 🧲 strength (net dealer gamma ÷ 50-day average $ volume) run larger
when the nearest expiry is a day out? — descriptive, READ-ONLY.

Shipped with the Chart Maps 🧲 chip (2026-09-27) so the number the tile title,
RULE_TEXT and docs/chart_maps/gex_chips_2026_09_27.md disclose can be re-run
before it is quoted. It is NOT a predictive study (no forward outcome, so no
placebo): it only measures a bias in the ranking key itself.

Cohort: every `gex_history` ledger row since --since whose nearest expiry had
NOT settled when it was read (chart_maps.gex_read.settled — the same rule the
tile uses) and whose symbol has ≥50 closed sessions in the price cache
(chart_maps.gex_read.adv_before over sepa.prices.bulk_cached_frames — never a
fetch). Split: nearest expiry ≤1 calendar day out vs ≥2.

Prints: median |net ÷ ADV50| per side, their ratio, a row-level bootstrap CI95
AND a symbol-clustered bootstrap CI95 (rows cluster by symbol), plus the count
of settled-chain rows per ledger day. Writes nothing.

Run in the api or cron container (Mongo + the price cache live there):
    docker exec -i -w /app cheetah-market-app-api-1 \
        python -m scripts.gex_strength_by_expiry --since 2026-08-01
"""
from __future__ import annotations

import argparse
import random
import statistics as st
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ET = ZoneInfo("America/New_York")
NEAR_MAX_DAYS = 1          # "a day out" — the disclosure's own wording


def _ratio(near, far):
    if not near or not far:
        return None
    mf = st.median(far)
    return st.median(near) / mf if mf else None


def _ci(vals):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return (None, None)
    lo = vals[int(0.025 * (len(vals) - 1))]
    hi = vals[int(0.975 * (len(vals) - 1))]
    return (lo, hi)


def collect(rows, frames, settled, adv_before):
    """(points, settled_by_day). points = [(symbol, dte, |net/adv|)]."""
    points, settled_by_day = [], {}
    for r in rows:
        d, exp, net = r.get("date_et"), r.get("expiration_date"), r.get("net_gex_dollars")
        if not d or not exp or net is None:
            continue
        rec = r.get("recorded_at")
        read_at = datetime.fromtimestamp(float(rec), ET) if rec is not None else None
        day = settled_by_day.setdefault(d, [0, 0])
        day[1] += 1
        if settled(exp, read_at, d):
            day[0] += 1
            continue
        adv = adv_before(frames.get(r.get("symbol")), date.fromisoformat(d))
        if adv is None:
            continue
        dte = (date.fromisoformat(exp) - date.fromisoformat(d)).days
        points.append((r.get("symbol"), dte, abs(float(net) / adv)))
    return points, settled_by_day


def summarize(points, n_boot=2000, seed=7):
    near = [v for _, d, v in points if d <= NEAR_MAX_DAYS]
    far = [v for _, d, v in points if d > NEAR_MAX_DAYS]
    rng = random.Random(seed)
    row_bs = []
    if near and far:
        for _ in range(n_boot):
            row_bs.append(_ratio([rng.choice(near) for _ in near],
                                 [rng.choice(far) for _ in far]))
    by_sym: dict = {}
    for s, d, v in points:
        by_sym.setdefault(s, []).append((d, v))
    syms = sorted(by_sym)
    cl_bs = []
    if syms:
        for _ in range(n_boot):
            pick = [rng.choice(syms) for _ in syms]
            nn = [v for s in pick for d, v in by_sym[s] if d <= NEAR_MAX_DAYS]
            ff = [v for s in pick for d, v in by_sym[s] if d > NEAR_MAX_DAYS]
            cl_bs.append(_ratio(nn, ff))
    return {
        "n_near": len(near), "n_far": len(far), "n_symbols": len(syms),
        "median_near": st.median(near) if near else None,
        "median_far": st.median(far) if far else None,
        "ratio": _ratio(near, far),
        "ci95_rows": _ci(row_bs),
        "ci95_symbol_clustered": _ci(cl_bs),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", default="2026-08-01")
    ap.add_argument("--boot", type=int, default=2000)
    a = ap.parse_args(argv)

    from chart_maps.gex_read import adv_before, settled
    from options import gex_history as GH
    from sepa import prices

    coll = GH._coll()
    if coll is None:
        print("no mongo")
        return 1
    rows = list(coll.find({"date_et": {"$gte": a.since}}, {"_id": 0}))
    frames = prices.bulk_cached_frames(sorted({r["symbol"] for r in rows
                                               if r.get("symbol")})) or {}
    points, settled_by_day = collect(rows, frames, settled, adv_before)
    s = summarize(points, n_boot=a.boot)
    print(f"as of {datetime.now(timezone.utc).isoformat()} · ledger rows since {a.since}: "
          f"{len(rows)} · days: {len(settled_by_day)}")
    print("settled-chain rows per day (settled/all):")
    for d in sorted(settled_by_day):
        k, n = settled_by_day[d]
        if k:
            print(f"  {d}: {k}/{n}")
    if s["ratio"] is None:
        print("not enough rows on one side")
        return 0
    rl, rh = s["ci95_rows"]
    cl, ch = s["ci95_symbol_clustered"]
    print(f"median |net/ADV50|: ≤{NEAR_MAX_DAYS} day out {s['median_near'] * 100:.3f}% "
          f"(n={s['n_near']}) vs later {s['median_far'] * 100:.3f}% (n={s['n_far']}), "
          f"{s['n_symbols']} symbols")
    print(f"ratio {s['ratio']:.2f}  row CI95 [{rl:.2f}, {rh:.2f}]  "
          f"symbol-clustered CI95 [{cl:.2f}, {ch:.2f}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
