"""👀 Gajjala's Watch — what the 1 / 5 / 15 frames + 📈 VWAP cost the minute build (spec vwapzones rev 2, be-watch step 8).

Ajay, verbatim (2026-11-23): "Can you remove 3 mins just add 15 mins instead.. So 1 min, 5 and 15 accross board" · "Add
vwap and supply demand too".

Read-only, no network: N synthetic two-session names (prior day 04:00–20:00 + today 04:00 → the clock), the frames built
ONCE per name (`bars.build_frames`, the minute loop's engine — not timed: it is the same fetch-and-resample for both
shapes), then the median wall-clock ms of `build.tile_update` per name for
  * main's shape — frames 1 / 3 / 5, VWAP off;
  * the new shape — frames 1 / 5 / 15, VWAP on, once per anchor of `vwap.SESSION_SETS` (HIS CALL #1).
The daily zones are NOT in the minute build (they run in the levels thread) — not measured here. Host-machine numbers:
a cost READ, not a budget; compare the totals with the live state doc's `wall_s`.

  python -m scripts.gajjala_watch_build_cost [--names 36] [--repeats 3] [--json]
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

ET = ZoneInfo("America/New_York")
S, PREV = date(2026, 11, 20), date(2026, 11, 19)
NOW = datetime(2026, 11, 20, 15, 59, 50, tzinfo=ET)          # a near-full regular session (the heaviest RTH minute)
MAIN_FRAMES = (("1m", "1min"), ("3m", "3min"), ("5m", "5min"))
MAIN_WORDS = {"1m": "1-min", "3m": "3-min", "5m": "5-min"}


def raw(d, seed, end=(20, 0)):
    t0 = pd.Timestamp(datetime(d.year, d.month, d.day, 4, 0), tz=ET)
    t1 = pd.Timestamp(datetime(d.year, d.month, d.day, *end), tz=ET)
    idx = pd.date_range(t0, t1, freq="1min", inclusive="left")
    rows = []
    for i, ts in enumerate(idx):
        m = ts.hour * 60 + ts.minute
        p = 5.0 + 0.6 * math.sin((i + seed) / 29.0) + 0.2 * math.sin((i + seed * 3) / 7.0)
        rows.append({"open": p - 0.01, "high": p + 0.03, "low": p - 0.03, "close": p,
                     "volume": float(1000 + ((i + seed) * 37) % 900),
                     "session": "premarket" if m < 570 else ("rth" if m < 960 else "afterhours")})
    return pd.DataFrame(rows, index=idx.tz_convert("UTC").tz_localize(None))


def run(names: int = 36, repeats: int = 3) -> dict:
    sys.dont_write_bytecode = True
    from chart_maps.gajjala import bars as B
    from chart_maps.gajjala_watch import build as BLD
    from chart_maps.gajjala_watch import constants as C
    from chart_maps.gajjala_watch import vwap as VW
    keep = (C.FRAMES, C.FRAME_WORDS, C.VWAP_ON, C.VWAP_SESSIONS)
    rules_all = MAIN_FRAMES + (("15m", "15min"),)
    frs = [B.build_frames(f"N{i:02d}", S, NOW, raw(PREV, i), raw(S, i + 100, end=(16, 0)), rules=rules_all)
           for i in range(names)]
    shapes = [("main 1/3/5, VWAP off", MAIN_FRAMES, MAIN_WORDS, False, VW.SESSION_SETS[0])]
    shapes += [(f"new 1/5/15, VWAP {'+'.join(s)}", keep[0], keep[1], True, s) for s in VW.SESSION_SETS]
    out = {"names": names, "repeats": repeats, "now": NOW.isoformat(), "rows": []}
    try:
        for label, frames, words, on, sets in shapes:
            C.FRAMES, C.FRAME_WORDS, C.VWAP_ON, C.VWAP_SESSIONS = frames, words, on, sets
            per = []
            for fr in frs:
                best = []
                for _ in range(repeats):
                    t0 = time.perf_counter()
                    BLD.tile_update(fr.symbol, fr, S, NOW, "loaded")
                    best.append((time.perf_counter() - t0) * 1000.0)
                per.append(min(best))
            out["rows"].append({"shape": label, "median_ms": round(statistics.median(per), 1),
                                "p90_ms": round(sorted(per)[int(0.9 * (len(per) - 1))], 1),
                                "total_s": round(sum(per) / 1000.0, 3)})
    finally:
        C.FRAMES, C.FRAME_WORDS, C.VWAP_ON, C.VWAP_SESSIONS = keep
    base = out["rows"][0]["median_ms"]
    for r in out["rows"]:
        r["delta_ms"] = round(r["median_ms"] - base, 1)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="scripts.gajjala_watch_build_cost", description=__doc__.split("\n")[0])
    ap.add_argument("--names", type=int, default=36)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    out = run(args.names, args.repeats)
    if args.json:
        print(json.dumps(out))
        return 0
    print(f"{out['names']} names, best of {out['repeats']}, clock {out['now']}")
    print(f"{'shape':<50} {'median ms':>10} {'p90 ms':>8} {'Δ ms':>7} {'total s':>8}")
    for r in out["rows"]:
        print(f"{r['shape']:<50} {r['median_ms']:>10} {r['p90_ms']:>8} {r['delta_ms']:>7} {r['total_s']:>8}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
