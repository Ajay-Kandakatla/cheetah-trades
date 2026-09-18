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
# russell2000 is LAST deliberately: it is DERIVED from russell1000 and
# russell3000 (FTSE's own definition), so both parents must have been refreshed
# in this run before it is asked for. Ajay 2026-09-18: "Yes add it."
TRACKED = ("sp500", "sp400", "sp600", "nasdaq100", "russell1000", "russell3000",
           "russell2000")

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
        "russell2000": U.fetch_russell2000,
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


def _construction(source) -> str:
    """How the list was BUILT, not which mirror served it.

    Two sources in the same class describe the same membership, so a diff
    between them is a real corporate event. A class change means the list
    itself was rebuilt on a different basis, and the delta is an artefact of
    that rebuild — the case the re-baseline exists for.

      published — the interchangeable mirrors of one published list
                  (wikipedia / datahub / the cache holding either)
      src:<x>   — every other source stands alone, because a flip into or out
                  of it changes the list's VINTAGE or its BASIS, not just who
                  served it
    """
    src = str(source or "")
    # The ONLY sources that are interchangeable views of the SAME published
    # membership. Wikipedia and datahub both carry the full S&P/Nasdaq lists,
    # and `cache` is whichever of them last answered — so a flip among these is
    # a mirror change and any diff across it is a REAL corporate event.
    #
    # Everything else is its own class on purpose:
    #   ishares-local vs ishares-network — the same product at different
    #     VINTAGES. The local russell3000 xls resolves 2,559 names; a fresh
    #     network pull would be ~3,000, so that flip alone would publish ~440
    #     additions that never happened.
    #   derived-r3000-minus-r1000 vs ishares-local — a subtraction becoming a
    #     real list the day an IWM export lands. A file copy, not 410 events.
    #   curated / empty — the wrong universe, or none. Never a membership claim.
    if src in ("wikipedia", "datahub", "cache", "stale-cache"):
        return "published"
    return "src:" + src


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

    # THE SOURCE-FLIP RE-BASELINE.
    # The day Ajay drops an iShares IWM export on disk, russell2000 stops being
    # a 1,560-name derivation and becomes a ~1,970-name real list. That churn
    # is well inside the sane window (max(8, 1560*0.35) = 546), so without this
    # guard the change log would publish "410 additions to the Russell 2000" —
    # a fabricated corporate event produced by a file copy. Same for a fresh
    # IWV lifting russell3000. The previous snapshot already stores `source`,
    # so the guard needs no new field and no new number: when the SOURCE
    # changes, the new list is the new BASELINE, not a membership change.
    # NARROWED 2026-09-18, before ship. The guard above is right about a
    # DERIVATION becoming a real export. It was wrong to fire on every source
    # string change, because most flips are the same index arriving from a
    # different MIRROR, not a different list: sp500's ladder is
    # wikipedia -> datahub and the module already documents Wikipedia 403-ing
    # for weeks at a time. On any week the winning loader changed, a genuine
    # S&P addition was zeroed out of the log Ajay reads for corporate events.
    #
    # So re-baseline on a change of CONSTRUCTION, not of mirror. Same class in,
    # same class out -> the diff is real and gets published.
    prev_source = (prev or {}).get("source")
    rebaselined = bool(prev is not None
                       and _construction(prev_source) != _construction(source))

    # A DERIVED list's diff cannot name the parent that moved. `CBC`/`FRMI`
    # prove the two iShares exports are already out of step, so an attribution
    # built on them would be confidently wrong some of the time. We say so on
    # the row instead of guessing.
    cov = None
    if name == "russell2000":                      # ONE call, never per-branch
        try:
            cov = U.russell2000_coverage()
        except Exception as exc:                   # noqa: BLE001
            log.warning("universe-changes: russell2000 coverage failed: %s", exc)
    attributable = True if cov is None else bool(cov.get("attributable"))

    out = {
        "index": name, "ok": True, "source": source,
        "provenance_known": provenance_known,
        "n": len(syms), "first_snapshot": prev is None,
        "sane": sane, **d,
        "previous_taken_at": (prev or {}).get("taken_at"),
        "complete": True if cov is None else bool(cov.get("complete")),
        "attributable": attributable,
        "coverage": cov,
    }
    if rebaselined:
        # The raw diff is reported under a key whose NAME says it was not
        # published, so nobody downstream reads it as a change.
        out["rebaselined"] = True
        out["raw_diff_not_published"] = {"added": len(d["added"]),
                                         "removed": len(d["removed"])}
        out["added"], out["removed"] = [], []
        out["reason"] = (f"source changed ({prev_source} -> {source}) — "
                         f"re-baselined, no membership change published")
    else:
        out["rebaselined"] = False

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
        if (sane and (d["added"] or d["removed"]) and not out["first_snapshot"]
                and not rebaselined):
            row = {
                "index": name, "detected_at": now, "date": date.today().isoformat(),
                "added": d["added"], "removed": d["removed"],
                "n_before": d["n_before"], "n_after": d["n_after"],
                "sane": sane, "source": src.get("source"),
                "attributable": attributable,
            }
            if not attributable:
                row["attribution_note"] = (
                    "Derived list (russell3000 minus russell1000). A name "
                    "leaving may have entered the Russell 1000 or may only "
                    "have moved in one parent export; this diff cannot tell "
                    "which.")
                row["derived_from"] = (cov or {}).get("derived_from")
            db.universe_changes.insert_one(row)
    except Exception as exc:
        log.warning("universe-changes: persist failed for %s: %s", name, exc)
    return out


def tracked_coverage() -> dict:
    """``{index: coverage-dict}`` for every tracked index that has to qualify
    its own list. Only ``russell2000`` does today — it is DERIVED and short of
    the real index, and a reader quoting it needs both facts.

    Never raises: a broken universe module returns ``{}`` so ``/universe/changes``
    still answers.
    """
    out: dict = {}
    try:
        from sepa import universe as U
        out["russell2000"] = U.russell2000_coverage()
    except Exception as exc:                                   # noqa: BLE001
        log.warning("universe-changes: tracked_coverage failed: %s", exc)
        return {}
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
