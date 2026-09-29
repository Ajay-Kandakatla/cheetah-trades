"""Measure the 🔑 Key Levels tab's cost on the full universe. READ-ONLY.

The re-runnable measurement behind the cost numbers in
`docs/chart_maps/key_levels_tab_2026_09_28.md` — the doc quotes whatever this
prints. Run it OUTSIDE RTH in the api container (or the verify container):

    docker exec -i -w /app cheetah-market-app-api-1 \\
        python -m scripts.key_levels_tab_cost_probe

It times the three stages the tab runs: the memo build (ONE
`bulk_cached_frames` read + the closed-bar levels per name, over the tab's own
universe `demand_reentry._resolve_universe("full")`), ONE universe
`bulk_snapshot`, and the per-request rank. Nothing is written: the build and
the rank are pure, the first-seen read is skipped (`{}`).

Imports ONLY `chart_maps.key_levels_tab` and `sepa.prices` — never the
key-levels engine directly (the display-only import guard scans scripts/).
Not a study of edge: a timing, no placebo applies.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_maps import key_levels_tab as KLT          # noqa: E402
from sepa import prices                               # noqa: E402

ET = ZoneInfo("America/New_York")


def main() -> dict:
    now = datetime.now(ET)
    session = KLT.session_for(now)
    t0 = time.perf_counter()
    entry = KLT.build("full", session)
    t1 = time.perf_counter()
    raw = prices.bulk_snapshot(entry["syms"]) or {}
    t2 = time.perf_counter()
    ranked, counts = KLT.rank(entry, raw, now=now, first_seen={})
    t3 = time.perf_counter()
    out = {"date": now.isoformat(timespec="seconds"),
           "env": os.environ.get("MONGO_DB") or "default",
           "n": len(entry["syms"]),
           "s_build": round(t1 - t0, 2), "s_snapshot": round(t2 - t1, 2),
           "s_rank": round(t3 - t2, 3), "counts": counts}
    print(json.dumps(out))
    return out


if __name__ == "__main__":
    main()
