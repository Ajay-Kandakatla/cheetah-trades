"""Moat coverage census over `sepa_research_cache` — re-runnable count.

2026-10-11: the weekly research refresh hit Yahoo 429s and wrote `moat: null`
over last week's good value (`sepa.moat.compute_moat` returned None on ANY
yfinance exception). Measured that night: ~80% of blobs had no moat. This
script is the before/after number for the carry-forward fix + the moat-only
backfill (`python -m sepa.cli moat-backfill`).

It is a CENSUS of every document, not a sample — no confidence interval
applies; re-run it to re-quote the number.

Usage (throwaway container, never exec into api/cron):
    docker run --rm --network cheetah-market-app_default \
      -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah \
      -v "$PWD/backend:/app" -w /app cheetah-api:latest \
      python scripts/moat_coverage.py [--since-hours 24] [--out /tmp/x.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _pct(n: int, d: int) -> float | None:
    return round(100.0 * n / d, 1) if d else None


PROJECTION = {"symbol": 1, "cached_at": 1, "moat.tier": 1,
              "moat.data_completeness": 1, "moat_status": 1, "moat_as_of": 1}


def census(docs, *, now: float, since: float, ttl_sec: int) -> dict:
    """Coverage counts over research docs (PURE — feed it `coll.find({},
    PROJECTION)`). A moat counts as present only when it is a dict."""
    fresh_cut = now - ttl_sec
    groups = {k: {"docs": 0, "moat_present": 0} for k in (
        "all", "fresh", "stale", "refreshed_since", "not_refreshed_since")}
    statuses = {"ok": 0, "no_data": 0, "fetch_failed": 0, "legacy_unset": 0}
    age = {"le_7d": 0, "le_16d": 0, "gt_16d": 0, "unstamped": 0}
    unknown_tier0 = zero_inputs = 0
    day = 86400

    for d in docs:
        cached = d.get("cached_at")
        cached = cached if isinstance(cached, (int, float)) else 0
        moat = d.get("moat")
        has = isinstance(moat, dict)
        keys = ["all",
                "fresh" if cached >= fresh_cut else "stale",
                "refreshed_since" if cached >= since else "not_refreshed_since"]
        for k in keys:
            groups[k]["docs"] += 1
            groups[k]["moat_present"] += int(has)
        st = d.get("moat_status")
        statuses[st if st in statuses else "legacy_unset"] += 1
        if not has:
            continue
        # a present-but-empty moat (tier 0 / 0 of 6 inputs) is still a dict —
        # split it out so it cannot hide a gap
        unknown_tier0 += int(moat.get("tier") == 0)
        zero_inputs += int(moat.get("data_completeness") == 0)
        ts = d.get("moat_as_of")
        if not isinstance(ts, (int, float)) or ts <= 0:
            age["unstamped"] += 1
        elif now - ts <= 7 * day:
            age["le_7d"] += 1
        elif now - ts <= 16 * day:
            age["le_16d"] += 1
        else:
            age["gt_16d"] += 1

    out: dict = {"measured_at": int(now), "since": int(since), "ttl_sec": ttl_sec}
    for k, g in groups.items():
        null = g["docs"] - g["moat_present"]
        # `fresh` is what the boards serve (get_all_research TTL filter)
        out[k] = {**g, "moat_null": null, "moat_null_pct": _pct(null, g["docs"])}
    out["present_unknown_tier0"] = unknown_tier0
    out["present_zero_inputs"] = zero_inputs
    out["moat_status"] = statuses          # written from 2026-10-11 on
    out["moat_value_age"] = age            # age of the moat VALUE, not the blob
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--since-hours", type=float, default=24.0,
                    help="split 'refreshed since' at now - N hours (default 24)")
    ap.add_argument("--out", default=None, help="also write the JSON here")
    args = ap.parse_args(argv)

    from pymongo import MongoClient
    from sepa.research import CACHE_TTL_SEC

    client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"),
                         serverSelectionTimeoutMS=5000)
    coll = client[os.getenv("MONGO_DB", "cheetah")].sepa_research_cache
    now = time.time()
    res = census(coll.find({}, PROJECTION), now=now,
                 since=now - args.since_hours * 3600, ttl_sec=CACHE_TTL_SEC)
    text = json.dumps(res, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
