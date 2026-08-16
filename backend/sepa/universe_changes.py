"""Track index membership as it changes — who joined, who dropped out.

Ajay 2026-08-16: *"we have too keep updating. 1. Latest tickers as they change
like getting added to SP 500 or Russel 3000 and Nasdaq."*

THE PROBLEM THIS SOLVES
-----------------------
`universe.py` already re-fetches each constituent list — but on a **30-day disk
cache** (`UNIV_CACHE_TTL_SEC`), and it keeps no history. Two consequences:

1. A name added to the S&P 500 could take up to a month to enter the scan, and
   nothing anywhere said so.
2. Even once it arrived, there was no record that it was NEW. An index add is
   itself a tradeable event — forced index-fund buying, a step-change in
   liquidity — and it was landing silently in a list of 500.

So this refreshes each list past its cache and DIFFS it against the last
snapshot, keeping the adds and drops.

WHY IT FORCES PAST THE CACHE
----------------------------
A weekly job that honours a 30-day cache would fetch nothing 3 weeks in 4 and
report "no changes" — which is indistinguishable from real quiet. It expires
the cache entry for each index first, so every run asks the source.

WHAT IT DOES NOT DO
-------------------
It never edits the universe. `universe.py` remains the single source of truth
for who gets scanned; this only observes and records. A diff that looks wrong
is therefore always safe to ignore.

NOT a trading signal. An index add is a liquidity event, not a setup.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from typing import Optional

log = logging.getLogger("sepa.universe_changes")

# Indices we track membership for. Keyed by the same names universe.py caches
# under, so `last_source()` and the count gates line up.
TRACKED = ("sp500", "sp400", "sp600", "nasdaq100", "russell1000", "russell3000")

# A diff bigger than this share of the list means the SOURCE changed shape
# (a renamed column, a truncated parse), not that the index reconstituted.
# Recorded but flagged, never trusted. Russell's annual June reconstitution is
# the one legitimately large event and still lands well under half.
SANE_CHURN_FRACTION = 0.35

# Absolute floor, so the fractional gate cannot misfire on a short list. A
# quarterly S&P rebalance moves a handful of names; on a 100-name index that is
# already 10%, and on a test fixture of three names ANY change would otherwise
# read as a collapsed parse. Real indices are large enough that the fraction
# always dominates.
MIN_ABS_CHURN = 8


def _fetchers() -> dict:
    from sepa import universe as U
    return {
        "sp500": U.fetch_sp500,
        "sp400": U.fetch_sp400,
        "sp600": U.fetch_sp600,
        "nasdaq100": U.fetch_nasdaq100,
        "russell1000": U.fetch_russell1000,
        "russell3000": U.fetch_russell3000,
    }


def _db():
    try:
        from sepa import history
        return history._get_db()
    except Exception as exc:
        log.warning("universe-changes: mongo unavailable: %s", exc)
        return None


def _expire_cache(name: str) -> None:
    """Make universe.py's disk cache miss, so the next fetch hits the source.

    Deletes the cache FILE rather than reaching into module state: the stale
    fallback (`_read_cached_stale`) also reads that file, so leaving it would
    let a failed live fetch silently resolve to the very snapshot we are trying
    to diff against — and report zero changes forever.
    """
    try:
        from sepa import universe as U
        p = U._cache_path(name)
        if p.exists():
            p.unlink()
    except Exception as exc:
        log.debug("universe-changes: could not expire %s cache: %s", name, exc)


def diff_lists(before: list, after: list) -> dict:
    """Adds and drops between two constituent lists. PURE."""
    b, a = set(before or []), set(after or [])
    return {
        "added": sorted(a - b),
        "removed": sorted(b - a),
        "n_before": len(b),
        "n_after": len(a),
    }


def is_sane_churn(d: dict, fraction: float = SANE_CHURN_FRACTION) -> bool:
    """False when the diff is too big to be a real membership change.

    A parse that loses a column returns a handful of names and reads as "480
    companies left the S&P 500". Marking that insane keeps a broken source out
    of the change log.
    """
    n_before = d.get("n_before") or 0
    if not n_before:
        return True                      # first ever snapshot — nothing to compare
    churn = len(d.get("added") or []) + len(d.get("removed") or [])
    return churn <= max(MIN_ABS_CHURN, n_before * fraction)


def _latest_snapshot(db, name: str) -> Optional[dict]:
    try:
        return db.universe_snapshots.find_one({"index": name}, sort=[("taken_at", -1)])
    except Exception:
        return None


def refresh_one(name: str, *, force: bool = True, db=None) -> dict:
    """Refetch one index, diff it against the last snapshot, persist both."""
    fetchers = _fetchers()
    if name not in fetchers:
        return {"index": name, "ok": False, "reason": "unknown index"}

    db = db if db is not None else _db()
    if force:
        _expire_cache(name)

    try:
        syms = list(fetchers[name]() or [])
    except Exception as exc:
        log.warning("universe-changes: %s fetch failed: %s", name, exc)
        return {"index": name, "ok": False, "reason": f"fetch failed: {exc}"}

    from sepa import universe as U
    src = U.last_source(name) or {}
    source = src.get("source")
    # A list that resolved to the curated fallback or to an expired snapshot is
    # not evidence of anything — diffing it would invent adds and drops.
    if not syms or source in ("curated", "empty", "stale-cache"):
        return {"index": name, "ok": False, "n": len(syms), "source": source,
                "reason": f"resolved to {source} — not a live list"}
    # universe.py only records provenance inside _resolve_index, which the S&P
    # ladder and nasdaq100 use — the Russell lists read local iShares .xls files
    # and record nothing, so `source` is None for them. That is expected, not a
    # failure, but it means we CANNOT tell a fresh Russell read from a stale
    # one. Say so in the payload instead of implying we verified it; the churn
    # gate below is the only guard those lists get.
    provenance_known = source is not None

    prev = _latest_snapshot(db, name) if db is not None else None
    d = diff_lists((prev or {}).get("symbols") or [], syms)
    sane = is_sane_churn(d)

    out = {
        "index": name, "ok": True, "source": source,
        "provenance_known": provenance_known,
        "n": len(syms), "first_snapshot": prev is None,
        "sane": sane, **d,
        "previous_taken_at": (prev or {}).get("taken_at"),
    }

    if db is None:
        return out
    now = datetime.now(timezone.utc)
    try:
        # Only snapshot a list we believe. Storing an insane parse would make it
        # the baseline and turn one bad fetch into two bogus diffs.
        if sane:
            db.universe_snapshots.insert_one({
                "index": name, "symbols": syms, "n": len(syms),
                "source": source, "taken_at": now,
            })
            db.universe_snapshots.delete_many({
                "index": name,
                "taken_at": {"$lt": now.replace(year=now.year - 2)},
            })
        # `sane` gates the change log too, not just the snapshot. A collapsed
        # parse would otherwise be published as "488 companies left the S&P
        # 500" — the change log is the thing Ajay actually reads, so a bad
        # parse must not reach it either.
        if sane and (d["added"] or d["removed"]) and not out["first_snapshot"]:
            db.universe_changes.insert_one({
                "index": name, "detected_at": now, "date": date.today().isoformat(),
                "added": d["added"], "removed": d["removed"],
                "n_before": d["n_before"], "n_after": d["n_after"],
                "sane": sane, "source": src.get("source"),
            })
    except Exception as exc:
        log.warning("universe-changes: persist failed for %s: %s", name, exc)
    return out


def run(names: Optional[list] = None, *, force: bool = True) -> dict:
    """Refresh + diff every tracked index."""
    db = _db()
    t0 = time.time()
    results = [refresh_one(n, force=force, db=db) for n in (names or TRACKED)]
    changed = [r for r in results if r.get("ok") and (r.get("added") or r.get("removed"))
               and not r.get("first_snapshot")]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "took_sec": round(time.time() - t0, 1),
        "indices": results,
        "changed": [r["index"] for r in changed],
        "total_added": sum(len(r.get("added") or []) for r in changed),
        "total_removed": sum(len(r.get("removed") or []) for r in changed),
    }


def recent(days: int = 90, limit: int = 50) -> list:
    """Recent membership changes, newest first — powers the endpoint."""
    db = _db()
    if db is None:
        return []
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    try:
        rows = list(db.universe_changes.find({}, {"_id": 0})
                    .sort("detected_at", -1).limit(int(limit)))
    except Exception as exc:
        log.warning("universe-changes: read failed: %s", exc)
        return []
    out = []
    for r in rows:
        ts = r.get("detected_at")
        if hasattr(ts, "timestamp") and ts.timestamp() < cutoff:
            continue
        r["detected_at"] = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        out.append(r)
    return out


if __name__ == "__main__":                                   # pragma: no cover
    import json
    res = run()
    print(json.dumps(res, indent=2, default=str))
    for r in res["indices"]:
        if r.get("ok") and not r.get("first_snapshot"):
            if r.get("added"):
                print(f"  {r['index']} ADDED   : {', '.join(r['added'][:20])}")
            if r.get("removed"):
                print(f"  {r['index']} REMOVED : {', '.join(r['removed'][:20])}")
