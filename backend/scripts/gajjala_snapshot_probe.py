#!/usr/bin/env python
"""Gajjala's tab — WP1 step 0: what the whole-market snapshot really carries, measured.

READ-ONLY. One whole-market Massive snapshot + one 1-minute range per sampled name (+ the instrument-type map with
`--types`, at most TYPES_MAX_PAGES calls). It writes NOTHING to Mongo or any cache: the minute bars come straight from
`daytrading.data._fetch_massive_minute` (no `intraday_cache` write), the snapshot through
`sepa.prices.market_snapshot_with_meta`. `--record DIR` writes the raw rows as JSON fixtures only when asked.

What it prints (re-run before quoting any of it — memory feedback_ship_the_backtest):
  1. the snapshot table of spec §1.6: http, wall, bytes, tickers, rows with day.v == 0 / min.av / lastTrade /
     prevDay.c, todaysChangePerc vs lastTrade/prevDay.c within 0.5 pp, his scanner's qualifier count (= the
     listed-set size for today) through `chart_maps.gajjala.scanner.scan_rows`;
  2. the step-0 rows, per name (20 liquid + up to 20 of today's small-cap runners): day.v vs min.av vs the summed
     1-minute volume (all / RTH), and — after 16:00 — day.c vs the 15:59 minute close, day.h/day.l vs the 09:30–16:00
     minute high/low, and the 16:00 closing-cross minute's share of after-hours volume (spec trap T7).

Where to run it — a THROWAWAY container (never `docker exec` into api/cron), the worktree mounted read-only:

    docker run --rm --env-file /Users/ajay/clinet-test/cheetah-market-app/backend/.env \
        -e PYTHONDONTWRITEBYTECODE=1 -v /Users/ajay/clinet-test/wt-gajjala/backend:/app:ro -w /app \
        cheetah-api:latest python -u scripts/gajjala_snapshot_probe.py --types

or on the host: backend/.venv/bin/python backend/scripts/gajjala_snapshot_probe.py (key from the environment).
The key is never printed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

ET = ZoneInfo("America/New_York")
LIQUID = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "AVGO", "JPM",
          "XOM", "BAC", "INTC", "PLTR", "F", "T", "PFE", "WMT", "KO", "MU")
SMALL_MAX = 20


def _f(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def snapshot_table(rows: dict, meta: dict, now_et: datetime, types) -> dict:
    from chart_maps.gajjala import scanner as SC
    session = now_et.date()
    n_day_zero = sum(1 for r in rows.values() if not _f(r.get("volume")))
    n_av = sum(1 for r in rows.values() if _f(r.get("min_av")))
    n_lt = sum(1 for r in rows.values() if _f(r.get("last_trade_price")))
    n_prev = sum(1 for r in rows.values() if _f(r.get("prev_day_close")))
    agree = disagree = 0
    for r in rows.values():
        px, pc, tcp = _f(r.get("last_trade_price")), _f(r.get("prev_day_close")), _f(r.get("change_pct"))
        if px and pc and tcp is not None:
            if abs((px / pc - 1) * 100 - tcp) <= 0.5:
                agree += 1
            else:
                disagree += 1
    res = SC.scan_rows(rows, now_et, session, types=types)
    return {"et": now_et.strftime("%Y-%m-%d %H:%M:%S %Z"), "http": meta.get("http"), "wall_s": meta.get("wall_s"),
            "bytes": meta.get("bytes"), "tickers": meta.get("n"), "day_v_zero": n_day_zero, "min_av": n_av,
            "last_trade": n_lt, "prev_day_c": n_prev, "change_pct_within_0_5pp": agree,
            "change_pct_off_by_more": disagree, "tape_session": res["tape_session"], "counts": res["counts"],
            "strip": res["strip"], "types_used": types is not None,
            "qualifiers": [(q["symbol"], q.get("type"), round(q["price"], 4), round(q["change_pct"], 1),
                            int(q["volume"]), q["vol_src"]) for q in res["qualifiers"]],
            "ah_carry_n": None if res["ah_carry"] is None else len(res["ah_carry"]),
            "k10_candidates_n": len(res["k10_candidates"]), "_qualifiers_rows": res["qualifiers"]}


def step0_row(sym: str, snap: dict, now_et: datetime) -> dict:
    """day.v / min.av vs the summed 1-minute bars; after 16:00 the regular-session fields vs the minute bars."""
    from daytrading.data import _fetch_massive_minute
    d = now_et.date()
    out = {"symbol": sym, "day_v": _f(snap.get("volume")), "min_av": _f(snap.get("min_av")),
           "day_c": _f(snap.get("close")), "day_h": _f(snap.get("high")), "day_l": _f(snap.get("low")),
           "last": _f(snap.get("last_trade_price"))}
    df = _fetch_massive_minute(sym, d, d)
    if df is None or df.empty:
        out["minutes"] = 0
        return out
    et_idx = df.index.tz_localize("UTC").tz_convert(ET)
    hm = et_idx.hour * 60 + et_idx.minute
    v = df["volume"].astype(float)
    rth = (hm >= 570) & (hm < 960)
    out.update({"minutes": int(len(df)), "sum_v_all": float(v.sum()), "sum_v_rth": float(v[rth].sum()),
                "sum_v_pre": float(v[hm < 570].sum())})
    if out["min_av"]:
        out["min_av_over_sum_all"] = round(out["min_av"] / out["sum_v_all"], 4) if out["sum_v_all"] else None
    if out["day_v"]:
        out["day_v_over_sum_rth"] = round(out["day_v"] / out["sum_v_rth"], 4) if out["sum_v_rth"] else None
        out["day_v_over_sum_all"] = round(out["day_v"] / out["sum_v_all"], 4) if out["sum_v_all"] else None
    if now_et.hour >= 16 and rth.any():
        last_rth = df[rth].iloc[-1]
        out.update({"rth_high_1m": float(df["high"][rth].max()), "rth_low_1m": float(df["low"][rth].min()),
                    "close_1559": float(last_rth["close"]),
                    "v_1600": float(v[hm == 960].sum()), "v_ah_from_1600": float(v[hm >= 960].sum())})
        out["cross_share_of_ah"] = (round(out["v_1600"] / out["v_ah_from_1600"], 4)
                                    if out["v_ah_from_1600"] else None)
        out["day_c_eq_1559"] = out["day_c"] is not None and abs(out["day_c"] - out["close_1559"]) < 1e-9
        out["day_h_eq_rth"] = out["day_h"] is not None and abs(out["day_h"] - out["rth_high_1m"]) < 1e-9
        out["day_l_eq_rth"] = out["day_l"] is not None and abs(out["day_l"] - out["rth_low_1m"]) < 1e-9
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--types", action="store_true", help="also fetch the instrument-type map (≤ TYPES_MAX_PAGES calls)")
    ap.add_argument("--no-minutes", action="store_true", help="snapshot table only (one call)")
    ap.add_argument("--record", metavar="DIR", help="write the raw snapshot rows of the sampled names as JSON")
    a = ap.parse_args(argv)

    from sepa import prices
    from chart_maps.gajjala import scanner as SC
    now_et = datetime.now(ET)
    rows, meta = prices.market_snapshot_with_meta()
    types = None
    types_meta = None
    if a.types:
        t0 = time.perf_counter()
        types, complete, calls = SC.fetch_type_map()
        types_meta = {"n": len(types), "complete": complete, "calls": calls,
                      "wall_s": round(time.perf_counter() - t0, 2)}
    table = snapshot_table(rows, meta, now_et, types)
    small = [q["symbol"] for q in table.pop("_qualifiers_rows")][:SMALL_MAX]
    print(json.dumps({"snapshot": table, "types": types_meta}, indent=1, default=str))
    sample = [s for s in LIQUID if s in rows] + [s for s in small if s not in LIQUID]
    if not a.no_minutes:
        step0 = [step0_row(s, rows[s], now_et) for s in sample]
        print(json.dumps({"step0": step0}, indent=1, default=str))
    if a.record:
        os.makedirs(a.record, exist_ok=True)
        path = os.path.join(a.record, f"snapshot_rows_{now_et.strftime('%Y%m%d_%H%M')}.json")
        with open(path, "w") as fh:
            json.dump({"et": table["et"], "rows": {s: rows[s] for s in sample}}, fh, indent=1, default=str)
        print("recorded", path)
    return 0 if meta.get("http") == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
