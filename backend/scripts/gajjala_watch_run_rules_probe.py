"""▶ run Gajjala's rules on ONE Watch name — the TIMING probe, read-only (2026-11-24, spec ggrun rev 2 §4 be-run).

Ajay 2026-11-24, verbatim: "On the Watch list I need a run button to run against Gajjalas rules of a stock to see for
patterns of 5 patterns he has especially reversal squeeze.."

N timed `run_rules.run(symbol)` calls for ONE symbol, `run_rules._reset()` between them (so every call reads, never
the memo), then min / median / max wall seconds AND which steps ran on each call: the Watch list read, the 🚩 read doc
read (found or not), the float origin ("pass" = the 🚩 pass's stored read · "run" = the chain's steps 1–2 now), the
answer state. The engine writes nothing; this script writes nothing (it only wraps three engine functions in memory
to observe them, restored afterwards). One Massive minute call (today) per run + the prior day on a cache miss + the
Massive shares-out lookup off GG's scanner.

  python -m scripts.gajjala_watch_run_rules_probe --symbol AKAN [--n 5] [--now 2026-11-24T10:36:00-05:00]
  docker exec -i -w /app cheetah-market-app-api-1 python - --symbol AKAN < backend/scripts/gajjala_watch_run_rules_probe.py

The container runs origin/main: this needs the deployed `chart_maps.gajjala_watch.run_rules`. Timing only — never a
claim about what the rules are worth. Display only, UNMEASURED.
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

BACKEND = (str(Path(__file__).resolve().parents[1])
           if str(globals().get("__file__") or "").endswith(".py") else None)
if BACKEND and BACKEND not in sys.path and not __package__:
    sys.path.insert(0, BACKEND)


def summary(walls: list) -> dict:
    """{n, min, median, max} of wall seconds (3 dp); an empty list → n 0 and None."""
    if not walls:
        return {"n": 0, "min": None, "median": None, "max": None}
    return {"n": len(walls), "min": round(min(walls), 3), "median": round(statistics.median(walls), 3),
            "max": round(max(walls), 3)}


def timed_runs(symbol: str, n: int, now=None, run_rules=None, clock=time.perf_counter) -> list:
    """[{wall_s, state, list_read, read_doc, float_origin}] — one row per call, `_reset()` before each."""
    RR = run_rules
    if RR is None:
        from chart_maps.gajjala_watch import run_rules as RR
    from chart_maps.gajjala import store as GST
    real_names, real_float, real_get = RR.watch_names, RR.float_for, GST.GajjalaStore.get_read
    rows = []
    seen: dict = {}

    def names(*a, **k):
        seen["list_read"] = True
        return real_names(*a, **k)

    def float_for(*a, **k):
        out = real_float(*a, **k)
        seen["float_origin"] = out[1]
        return out

    def get_read(self, *a, **k):
        doc = real_get(self, *a, **k)
        seen["read_doc"] = "found" if isinstance(doc, dict) else "none"
        return doc

    RR.watch_names, RR.float_for, GST.GajjalaStore.get_read = names, float_for, get_read
    try:
        for _ in range(max(1, int(n))):
            RR._reset()
            seen.clear()
            t0 = clock()
            ans = RR.run(symbol, now)
            rows.append({"wall_s": clock() - t0, "state": ans.get("state"), "list_read": bool(seen.get("list_read")),
                         "read_doc": seen.get("read_doc", "not read"),
                         "float_origin": seen.get("float_origin", "not read")})
    finally:
        RR.watch_names, RR.float_for, GST.GajjalaStore.get_read = real_names, real_float, real_get
        RR._reset()
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--now", default=None, help="an ISO clock (ET-aware); default = the wall clock")
    a = ap.parse_args(argv)
    now = datetime.fromisoformat(a.now) if a.now else None
    rows = timed_runs(a.symbol, a.n, now)
    for i, r in enumerate(rows, 1):
        print(f"run {i}: {r['wall_s']:.3f} s · state {r['state']} · list read {r['list_read']} · "
              f"read doc {r['read_doc']} · float origin {r['float_origin']}")
    s = summary([r["wall_s"] for r in rows])
    print(f"n {s['n']} · wall s min {s['min']} · median {s['median']} · max {s['max']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
