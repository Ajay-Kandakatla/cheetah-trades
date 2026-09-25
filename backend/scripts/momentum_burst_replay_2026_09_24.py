#!/usr/bin/env python
"""⚡ Momentum-burst replay — minute by minute through one session.

PROBE, NOT A STUDY. One day, a handful of names: it answers "when, on that
day, would the ⚡ read have said burst?" and nothing about whether a burst
name then went anywhere. The rule is UNMEASURED; this script does not change
that.

READ-ONLY. 1-min bars come from the intraday cache read
(`daytrading.data._mongo_get_day`) or, when a day is not cached, a plain
Massive fetch (`_fetch_massive_minute`) that is NOT written back. The average
comes from `prices.bulk_cached_frames` (one find, never a fetch). Nothing is
stored anywhere.

MODEL (the same as the board's live read, per RTH minute):
  day volume = cumulative from 04:00 ET (pre-market included, as the snapshot
               counts it) through the minute's close;
  low        = the RTH low so far;
  print      = the minute's close;
  frac       = minutes done / SESSION_MINUTES (the bar's END time);
  verdict    = momentum_burst.rvol_leg + momentum_burst.off_low_pct, with the
               projection start picked by --start:
                 display = BURST_PROJECTION_MIN_FRAC (the board's default)
                 lane    = LANE_VOL_CONFIRM_MIN_FRAC (the Auto-Pilot's 120 min)

Run outside RTH (09:30-16:00 ET):

    container:  docker exec -i -w /app cheetah-market-app-api-1 \
                    sh -c 'PYTHONPATH=/app python -u scripts/momentum_burst_replay_2026_09_24.py \
                           --day 2026-09-24 --symbols ORCL,AMD,RAPP --start display'
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supply_demand import momentum_burst as MB                   # noqa: E402

ET_TZ = "America/New_York"
RTH_OPEN_MIN = 9 * 60 + 30
RTH_CLOSE_MIN = 16 * 60


def _minute_bars(sym: str, day: date):
    from daytrading import data as D
    df = D._mongo_get_day(sym, day)
    src = "cache"
    if df is None or df.empty:
        df = D._fetch_massive_minute(sym, day, day)
        src = "fetch"
    if df is None or df.empty:
        return None, src
    df = df.sort_index()
    idx = df.index
    if getattr(idx, "tz", None) is None:
        idx = idx.tz_localize("UTC")
    et = idx.tz_convert(ET_TZ)
    return df.assign(_et=et), src


def replay_one(sym: str, day: date, frame, start_frac: float) -> dict:
    avg = MB.avg_volume_before(frame, day)
    if avg is None:
        return {"error": "no_avg"}
    df, src = _minute_bars(sym, day)
    if df is None:
        return {"error": "no_1min"}
    mins = [ts.hour * 60 + ts.minute for ts in df["_et"]]
    cum = 0.0
    low = None
    hits = []
    last_rvol = None
    saved = MB.BURST_PROJECTION_MIN_FRAC
    MB.BURST_PROJECTION_MIN_FRAC = start_frac
    try:
        for m, (_, row) in zip(mins, df.iterrows()):
            if m >= RTH_CLOSE_MIN:
                break
            v = MB._f(row.get("volume")) or 0.0
            cum += v
            if m < RTH_OPEN_MIN:
                continue
            lo = MB._f(row.get("low"))
            if lo is not None and lo > 0:
                low = lo if low is None else min(low, lo)
            px = MB._f(row.get("close"))
            frac = min(1.0, (m + 1 - RTH_OPEN_MIN) / MB.SESSION_MINUTES)
            leg = MB.rvol_leg(cum, avg, "rth", frac)
            off = MB.off_low_pct(px, low)
            last_rvol = leg.get("actual")
            if leg["verdict"] == "pass" and off is not None and 0 < off <= MB.BURST_MAX_OFF_LOW_PCT:
                hits.append(row["_et"].strftime("%H:%M"))
    finally:
        MB.BURST_PROJECTION_MIN_FRAC = saved
    return {"src": src, "minutes": len(hits),
            "first": hits[0] if hits else None, "last": hits[-1] if hits else None,
            "full_day_rvol": last_rvol}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="⚡ momentum-burst replay (probe, not a study)")
    ap.add_argument("--day", required=True, help="YYYY-MM-DD")
    ap.add_argument("--symbols", required=True, help="comma list, e.g. ORCL,AMD")
    ap.add_argument("--start", choices=("display", "lane"), default="display")
    a = ap.parse_args(argv)
    day = date.fromisoformat(a.day)
    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    start_frac = (MB.BURST_PROJECTION_MIN_FRAC if a.start == "display"
                  else MB.LANE_VOL_CONFIRM_MIN_FRAC)
    from sepa import prices
    frames = prices.bulk_cached_frames(syms)
    res = {}
    for s in syms:
        try:
            res[s] = replay_one(s, day, frames.get(s), start_frac)
        except Exception as exc:                                # noqa: BLE001
            res[s] = {"error": type(exc).__name__}
    names = [k for k, v in res.items() if v.get("minutes")]
    print(json.dumps({
        "label": "probe, not a study",
        "day": day.isoformat(), "start": a.start,
        "start_min": int(round(start_frac * MB.SESSION_MINUTES)),
        "rule": MB.rule_text(),
        "names": res,
        "totals": {"names_ever_burst": len(names),
                   "burst_minutes": sum(int(v.get("minutes") or 0) for v in res.values())},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
