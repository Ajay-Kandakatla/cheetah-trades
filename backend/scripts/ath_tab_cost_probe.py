"""Measure the 🏔️ ATH tab's cost and groups on the full universe. READ-ONLY.

The re-runnable measurement behind the numbers in
`docs/chart_maps/ath_tab_2026_09_29.md` — the doc quotes whatever this prints.
Run it OUTSIDE RTH in the api container (or the verify container):

    docker exec -i -w /app cheetah-market-app-api-1 \\
        python -m scripts.ath_tab_cost_probe [--fill] [--limit N]

It FORCES `ATH_HISTORY_STORE=memory`, so the long-history summaries live in
this process only and nothing is written to Mongo. It times the stages the tab
runs: the memo build (ONE `bulk_cached_frames` read + ONE history read + ONE
listing read + the closed half per name), optionally the history fill (ONE
Massive monthly call per name, paced — about 23 minutes for the universe),
the rebuild with the history in hand, ONE universe `bulk_snapshot`, and the
per-request rank for both groups.

Also times the board's side-by-side chunk fan-out of the same snapshot
(`board._bulk_snaps_fanout`, the path `ath_tiles` uses since 2026-09-29) next
to the serial call, and says whether the two maps hold the same names.

Imports ONLY `chart_maps.ath_tab`, `chart_maps.ath_history`,
`chart_maps.board` and `sepa.prices` — never the key-levels engine directly (the display-only
import guard scans scripts/). Not a study of edge: a timing and a count, no
placebo applies.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_maps import ath_history as AH              # noqa: E402
from chart_maps import ath_tab as ATH                 # noqa: E402
from sepa import prices                               # noqa: E402

os.environ[AH.STORE_ENV] = "memory"                  # never a Mongo write from here

ET = ZoneInfo("America/New_York")
NAMED = ("PLTR", "NVDA", "AAPL", "PCOR", "DJT", "XOM", "WOLF", "SPCX", "BNY", "CRCL")
TOP = 15


def _row(r: dict) -> dict:
    a = r["ath"]
    return {"symbol": r["symbol"], "text": a["text"], "label": a["label"],
            "status": a["status"], "px": a["px"], "high": a["high"],
            "high_date": a["high_date"], "adv50": r.get("adv50")}


def _named(entry: dict) -> dict:
    out = {}
    for s in NAMED:
        rd = (entry.get("reads") or {}).get(s)
        if not rd:
            out[s] = None
            continue
        out[s] = {k: rd.get(k) for k in ("hi_closed", "hi_date", "hi_date_is_month",
                                         "first_bar", "first_is_month", "listed", "status",
                                         "label", "doc_state", "refetch")}
        doc = AH.read_many([s]).get(s) or {}
        out[s]["doc"] = {k: doc.get(k) for k in ("status", "first_bar", "hi", "hi_month",
                                                 "cut_from", "n_months")}
    return out


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(prog="python -m scripts.ath_tab_cost_probe")
    ap.add_argument("--fill", action="store_true", help="fill the memory store first")
    ap.add_argument("--limit", type=int, default=None, help="fill at most N names")
    args = ap.parse_args(argv)

    now = datetime.now(ET)
    session = ATH.session_for(now)
    t0 = time.perf_counter()
    entry = ATH.build("full", session)
    t1 = time.perf_counter()
    out = {"date": now.isoformat(timespec="seconds"),
           "env": os.environ.get("MONGO_DB") or "default", "store": "memory",
           "n": len(entry["syms"]), "n_reads": len(entry["reads"]),
           "s_build_cold": round(t1 - t0, 2)}

    if args.fill:
        names = [s for s, _r in entry["pending"]]
        if args.limit is not None:
            names = names[:max(0, int(args.limit))]
        t2 = time.perf_counter()
        fc = AH.fill(names, now=now)
        t3 = time.perf_counter()
        out["fill"] = {**{k: v for k, v in fc.items() if k != "error_symbols"},
                       "error_symbols": fc["error_symbols"][:40],
                       "s_fill": round(t3 - t2, 1),
                       "s_per_name": round((t3 - t2) / max(1, len(names)), 3)}
        t4 = time.perf_counter()
        entry = ATH.build("full", session)
        t5 = time.perf_counter()
        out["s_build_warm"] = round(t5 - t4, 2)

    t6 = time.perf_counter()
    raw = prices.bulk_snapshot(entry["syms"]) or {}
    t7 = time.perf_counter()
    s_snap_serial = round(t7 - t6, 2)
    from chart_maps import board as B
    tf0 = time.perf_counter()
    fan = B._bulk_snaps_fanout(entry["syms"])
    out["s_snapshot_fanout"] = round(time.perf_counter() - tf0, 2)
    out["fanout_same_names"] = set(fan) == set(raw)
    t7 = t7 + (time.perf_counter() - tf0)
    at, counts = ATH.rank(entry, raw, now=now, group=ATH.GROUP_AT)
    t8 = time.perf_counter()
    slip, _c = ATH.rank(entry, raw, now=now, group=ATH.GROUP_SLIP)
    t9 = time.perf_counter()
    reads = list((entry.get("reads") or {}).values())
    out.update({
        "s_snapshot": s_snap_serial, "s_rank_at": round(t8 - t7, 3),
        "s_rank_slip": round(t9 - t8, 3), "n_snap": len(raw),
        "counts": counts, "history": entry.get("history"),
        "status": dict(Counter(r.get("status") for r in reads)),
        "doc_state": dict(Counter(r.get("doc_state") for r in reads)),
        "first_bar_month_2003_09": sum(1 for r in reads if r.get("first_is_month")
                                       and str(r.get("first_bar"))[:7] == "2003-09"),
        "top_at": [_row(r) for r in at[:TOP]],
        "top_slip": [_row(r) for r in slip[:TOP]],
        "named": _named(entry),
    })
    print(json.dumps(out, default=str))
    return out


if __name__ == "__main__":
    main()
