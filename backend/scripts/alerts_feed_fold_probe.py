"""Measure the Alerts-feed repeat collapse on HIS read. READ-ONLY.

Ajay 2026-09-21, asked "Collapse the 2,022 old rows on the Alerts page?":
*"Yes to all.."*. This is the re-runnable measurement behind every number in
`docs/notifications/alerts_feed_collapse.md` — the doc quotes whatever this
prints, never a retyped figure.

Run it in the api container:

    docker exec -i -w /app cheetah-market-app-api-1 \\
        python -m scripts.alerts_feed_fold_probe

It opens Mongo read-only (`find` + `sort` + `limit`, no write of any kind, no
`push_history` document touched) and reports, per window:

    raw fetched · after the retired filter · served after the collapse ·
    rows removed · which kinds folded · the run-length histogram

**The visibility query is the one `push.history.list_recent` uses** —
`{"$or": [{"user_email": <owner>}, {"user_email": None}]}`, i.e. HIS rows plus
the broadcasts. The collection also holds the co-owner's and Karthik's rows;
an all-users read is a different, much larger number that his page never
serves, and it is not what this prints.

The identity and the tagging are IMPORTED from `push.recent`
(`repeat_key`, `derive_tickers`, `known_symbols`) — nothing here retypes the
key, so a change to the engine shows up in the measurement instead of drifting
away from it. `derive_tickers` needs the universe, so the first call loads it.

Not a study of edge: the collapse is presentation, nothing is gated, ranked or
hidden by it, and there is no placebo to run against a layout change.
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from push.recent import derive_tickers, known_symbols, repeat_key  # noqa: E402

ET = ZoneInfo("America/New_York")
PROJECTION = {"kind": 1, "ticker": 1, "tickers": 1, "title": 1, "ts": 1, "body": 1}


def _db():
    from pymongo import MongoClient
    url = (os.environ.get("MONGO_URL") or os.environ.get("MONGODB_URL")
           or "mongodb://mongo:27017")
    return MongoClient(url)[os.environ.get("MONGO_DB", "cheetah")]


def _retired() -> frozenset:
    from push import subs
    return frozenset(subs.RETIRED_2026_09_20)


def _owner() -> str:
    """The same address `push.recent` serves: auth's house owner, falling back
    to DEFAULT_USER_EMAIL."""
    try:
        from auth import HOUSE_OWNER_EMAIL
        if HOUSE_OWNER_EMAIL:
            return str(HOUSE_OWNER_EMAIL).lower()
    except Exception:                                        # noqa: BLE001
        pass
    return (os.environ.get("DEFAULT_USER_EMAIL") or "").lower()


def run(db, label: str, query: dict, cap: int, retired: frozenset, known) -> dict:
    """One window: fetch exactly as the feed does, filter, tag, fold."""
    rows = list(db.push_history.find(query, PROJECTION).sort("ts", -1).limit(cap))
    raw = len(rows)
    rows = [r for r in rows if r.get("kind") not in retired]
    for r in rows:
        r["source"] = "push"
        r["tickers"] = derive_tickers(r, known)

    groups = Counter()
    removed = Counter()
    runlen = Counter()
    served = 0
    i = 0
    while i < len(rows):
        key = repeat_key(rows[i])
        j = i
        while j + 1 < len(rows) and repeat_key(rows[j + 1]) == key:
            j += 1
        size = j - i + 1
        if size >= 2:
            groups[rows[i].get("kind")] += 1
            removed[rows[i].get("kind")] += size - 1
            runlen[size] += 1
        served += 1
        i = j + 1

    kept = len(rows)
    pct = 100 * (kept - served) / max(1, kept)
    print(f"{label}")
    print(f"  raw={raw} (cap {cap})  after_retired={kept}  served={served}  "
          f"removed={kept - served} (-{pct:.1f}%)  raw_truncated={raw >= cap}")
    print(f"  folded groups by kind: {dict(groups.most_common(8))}")
    print(f"  rows removed by kind:  {dict(removed.most_common(8))}")
    print(f"  run lengths:           {dict(sorted(runlen.items()))}")
    pa = [r for r in rows if r.get("kind") == "price_alert"]
    print(f"  price_alert rows: {len(pa)}  distinct titles: {len({r.get('title') for r in pa})}")
    return {"raw": raw, "kept": kept, "served": served, "removed": kept - served}


def main() -> int:
    db = _db()
    retired = _retired()
    owner = _owner()
    known = known_symbols()
    vis = {"$or": [{"user_email": owner}, {"user_email": None}]}
    now = datetime.now(ET)
    midnight = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

    print(f"owner={owner!r}  now ET={now:%Y-%m-%d %H:%M}  "
          f"retired={sorted(retired)}  universe={len(known)} symbols")
    print("visibility = his rows UNION the broadcasts (push.history.list_recent's own query)\n")

    run(db, "HIS FEED · 90 days (everything the TTL still holds)", vis, 100_000, retired, known)
    print()
    run(db, "HIS FEED · today since 00:00 ET, raw cap 500 (the /alerts page read)",
        {"$and": [vis, {"ts": {"$gte": midnight}}]}, 500, retired, known)
    print()
    run(db, "HIS FEED · last 5 ET days, raw cap 500",
        {"$and": [vis, {"ts": {"$gte": midnight - 4 * 86400}}]}, 500, retired, known)
    print()
    run(db, "HIS FEED · the bell's default read, raw 50", vis, 50, retired, known)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
