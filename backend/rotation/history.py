"""Daily rotation history — so the strip can say what CHANGED, not what is hot.

Ajay 2026-09-12, looking at the six-row, ~35-chip Hot-sectors strip:
*"this is what I mean when I said messy"* · *"I am trying to see what changed
if there is no change continously same sectors continue to show the top for
example energy has been continous."*

THE PRODUCT INSIGHT, and the whole reason this module exists: **Energy at #1
for eight days is ONE fact, not eight.** The strip re-printed the same wall of
chips every session, so the reader had to diff it by eye and nothing told him
when the answer was simply "no change". A rank with no history behind it cannot
say that, and NOTHING in the app stored one — `scan_context` keeps exactly
three documents (iv / rotation / summary), latest-only, and yesterday's ranking
was gone the moment today's scan finished.

WHAT IS STORED
──────────────
One document per SESSION DATE (`_id` = the payload's own `as_of`, never
"today"): the ranked order of every grain, plus each group's leg values. Keyed
by as_of so a re-run, a backfill or a Saturday read all land on the session
they describe instead of creating a phantom day.

WHAT IS COMPUTED
────────────────
`changes()` answers three questions against the previous stored session:
  entered / left  — groups that crossed into or out of the top band
  moved           — rank deltas, biggest first
  streaks         — how many CONSECUTIVE stored sessions a group has held its
                    current rank, which is what turns "Energy is #1" into
                    "Energy #1 · 8 days" and lets the strip collapse to a line

NOTHING HERE PREDICTS ANYTHING. It is a change detector over a ranking the app
already measured as having no forward edge: the 2026-09-09 sector-heat study
found heat does NOT predict demand outcomes (-0.57pp, CI spans zero) and COLD
sectors beat hot ones over 5 days by 2.55pp, and the rotation backtest gives
top-3 rotation 158.22% against RSP 155.42%. A shift being visible is not a
reason to trade it.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

log = logging.getLogger("rotation.history")

COLL = "rotation_history"
GRAINS = ("sectors", "industries", "themes", "cohorts")
# How many ranks deep counts as "the top band" for entered/left. A group
# oscillating around 20th is noise; crossing into the top 6 is the event.
TOP_N = 6
# A rank move smaller than this is not worth a line on a strip built to be read
# in two seconds.
MIN_MOVE = 2
KEEP_DAYS = 400
RANK_KEY = "rel_5d"          # the leg the strip itself ranks by


def _coll():
    try:
        from pymongo import MongoClient
        c = MongoClient(os.environ.get("MONGO_URL", "mongodb://mongo:27017"),
                        serverSelectionTimeoutMS=2000)
        return c.get_database(os.environ.get("MONGO_DB", "cheetah"))[COLL]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("rotation.history: no mongo: %s", exc)
        return None


def _f(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (f != f or f in (float("inf"), float("-inf"))) else f


def snapshot(payload: dict, rank_key: str = RANK_KEY) -> Optional[dict]:
    """The storable shape for one session. None when the payload has no date.

    A snapshot with no `as_of` is REFUSED rather than stamped with today: a
    document keyed by the wrong day corrupts every delta computed after it, and
    that is far worse than a missing day."""
    payload = payload or {}
    as_of = payload.get("as_of")
    if not as_of:
        return None
    out = {"_id": str(as_of), "as_of": str(as_of),
           "benchmark": payload.get("benchmark"), "rank_key": rank_key,
           "grains": {}}
    for g in GRAINS:
        rows = payload.get(g) or []
        ranked = sorted(
            [r for r in rows if r.get("group")],
            key=lambda r: (_f(r.get(rank_key)) is None, -(_f(r.get(rank_key)) or 0.0)))
        out["grains"][g] = [
            {"group": r["group"], "rank": i + 1,
             "rel_1d": _f(r.get("rel_1d")), "rel_5d": _f(r.get("rel_5d")),
             "rel_21d": _f(r.get("rel_21d")), "n": r.get("n")}
            for i, r in enumerate(ranked)]
    return out


def store(payload: dict, coll=None) -> Optional[str]:
    """Upsert today's snapshot. Returns the as_of stored, or None."""
    snap = snapshot(payload)
    if snap is None:
        log.info("rotation.history: payload has no as_of — not stored")
        return None
    coll = coll if coll is not None else _coll()
    if coll is None:
        return None
    try:
        coll.update_one({"_id": snap["_id"]}, {"$set": snap}, upsert=True)
        return snap["as_of"]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("rotation.history: store failed: %s", exc)
        return None


def recent(limit: int = 30, coll=None, before: Optional[str] = None) -> list:
    """Stored snapshots, NEWEST FIRST."""
    coll = coll if coll is not None else _coll()
    if coll is None:
        return []
    q = {"_id": {"$lt": str(before)}} if before else {}
    try:
        return list(coll.find(q).sort("_id", -1).limit(int(limit)))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("rotation.history: read failed: %s", exc)
        return []


def _ranks(snap: dict, grain: str) -> dict:
    return {r["group"]: r["rank"] for r in ((snap.get("grains") or {}).get(grain) or [])}


def streaks(history: list, grain: str) -> dict:
    """{group: consecutive sessions at its CURRENT rank}. `history` newest
    first. A group absent from an older session ends its streak there."""
    if not history:
        return {}
    now = _ranks(history[0], grain)
    out = {g: 1 for g in now}
    # "still counting" is tracked SEPARATELY from the count. The first version
    # marked a broken streak by setting the count itself to None and then
    # restored it as 1 — silently throwing away the sessions already counted,
    # so a genuine 2-day streak reported as 1. Pinned by
    # test_a_streak_BREAKS_when_the_rank_changed_and_does_not_count_past_it.
    live = set(now)
    for snap in history[1:]:
        if not live:
            break
        prev = _ranks(snap, grain)
        for g in list(live):
            if prev.get(g) == now[g]:
                out[g] += 1
            else:
                live.discard(g)        # streak ends HERE; the count stands
    return out


def changes(current: dict, history: Optional[list] = None,
            grain: str = "themes", top_n: int = TOP_N,
            min_move: int = MIN_MOVE, coll=None) -> dict:
    """What moved since the previous stored session.

    Returns {"baseline", "entered", "left", "moved", "streaks", "quiet",
             "top"}. `quiet` is True when nothing crossed the band and nothing
    moved by `min_move` — the answer that lets the strip collapse to one line,
    and a real answer rather than an empty render."""
    snap = snapshot(current) if "grains" not in (current or {}) else current
    if snap is None:
        return {"baseline": None, "entered": [], "left": [], "moved": [],
                "streaks": {}, "quiet": True, "top": [], "reason": "no as_of"}
    hist = history if history is not None else recent(60, coll=coll)
    # the previous DIFFERENT session, never today's own row
    prior = next((h for h in hist if str(h.get("_id")) < snap["as_of"]), None)

    rows = (snap.get("grains") or {}).get(grain) or []
    top = [r["group"] for r in rows[:top_n]]
    now = {r["group"]: r["rank"] for r in rows}

    if prior is None:
        return {"baseline": None, "entered": [], "left": [], "moved": [],
                "streaks": {g: 1 for g in now}, "quiet": True, "top": top,
                "reason": "first snapshot — no prior session to compare"}

    was = _ranks(prior, grain)
    was_top = [g for g, r in sorted(was.items(), key=lambda kv: kv[1])[:top_n]]
    entered = [{"group": g, "rank": now[g], "prev_rank": was.get(g)}
               for g in top if g not in was_top]
    left = [{"group": g, "rank": now.get(g), "prev_rank": was.get(g)}
            for g in was_top if g not in top]
    moved = []
    for g, r in now.items():
        pr = was.get(g)
        if pr is None:
            continue
        d = pr - r                       # positive = climbed
        if abs(d) >= min_move:
            moved.append({"group": g, "rank": r, "prev_rank": pr, "delta": d})
    moved.sort(key=lambda m: -abs(m["delta"]))

    st = streaks([snap] + list(hist), grain)
    return {"baseline": prior.get("as_of"), "entered": entered, "left": left,
            "moved": moved, "streaks": st, "top": top,
            "quiet": not (entered or left or moved)}


def prune(keep_days: int = KEEP_DAYS, coll=None) -> int:
    coll = coll if coll is not None else _coll()
    if coll is None:
        return 0
    try:
        ids = [d["_id"] for d in coll.find({}, {"_id": 1}).sort("_id", -1)]
        old = ids[keep_days:]
        if not old:
            return 0
        coll.delete_many({"_id": {"$in": old}})
        return len(old)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("rotation.history: prune failed: %s", exc)
        return 0


def changes_all(current: dict, history: Optional[list] = None,
                top_n: int = TOP_N, min_move: int = MIN_MOVE,
                coll=None) -> dict:
    """Every grain in ONE answer.

    The Hot-sectors strip renders cohorts, industries AND themes. Asking
    `changes()` for a single grain would let it print "no change since
    2026-09-11" on a session where themes reshuffled underneath — a confident
    sentence that is simply false, which is worse than the wall of chips it
    replaced.

    So `quiet` here is the AND across every grain: true only when nothing
    crossed the band and nothing moved by `min_move` anywhere. Each grain's
    own answer is kept under `grains` so the strip can name where a move
    happened ("themes: robotics 7→3") rather than saying something moved.
    """
    snap = snapshot(current) if "grains" not in (current or {}) else current
    if snap is None:
        return {"baseline": None, "grains": {}, "quiet": True,
                "reason": "no as_of"}
    # Read the history ONCE and hand the same list to every grain. Four reads
    # of the same collection would also risk four different baselines if a
    # scan landed mid-request.
    hist = history if history is not None else recent(60, coll=coll)
    out: dict = {"grains": {}, "baseline": None, "quiet": True}
    reasons = []
    for g in GRAINS:
        c = changes(snap, history=hist, grain=g, top_n=top_n,
                    min_move=min_move, coll=coll)
        out["grains"][g] = c
        out["baseline"] = out["baseline"] or c.get("baseline")
        if not c.get("quiet"):
            out["quiet"] = False
        if c.get("reason"):
            reasons.append(c["reason"])
    if reasons and out["baseline"] is None:
        out["reason"] = reasons[0]
    return out


def snapshot_persisted(coll=None) -> Optional[str]:
    """Store the snapshot for the LAST PERSISTED rotation build.

    The scan's own `context_refresh.refresh_rotation` already stores one after
    every scan, so this is the end-of-day belt-and-braces pass: it reads the
    same `scan_context` document the API serves and writes the session's final
    ranking, idempotently — the `_id` is the payload's `as_of`, so running it
    twice upserts the same day rather than inventing a second one.

    It deliberately does NOT rebuild. `tracker.build` is a multi-minute full
    refetch whose cache is in-process, so a cron-container rebuild would burn
    the provider quota to warm a cache the API server never sees — the same
    mistake the demand-reentry warm made before 2026-08-15.
    """
    try:
        from sepa import context_refresh as MC
        payload = (MC.load_doc(MC.ROTATION_ID) or {}).get("payload") or {}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("rotation.history: no persisted rotation doc: %s", exc)
        return None
    if not payload:
        log.info("rotation.history: persisted rotation doc is empty — nothing stored")
        return None
    return store(payload, coll=coll)


if __name__ == "__main__":                                     # pragma: no cover
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    if cmd == "snapshot":
        as_of = snapshot_persisted()
        print(f"rotation history: stored {as_of}" if as_of
              else "rotation history: nothing stored")
        dropped = prune()
        if dropped:
            print(f"rotation history: pruned {dropped} session(s) past {KEEP_DAYS}")
    elif cmd == "prune":
        print(f"rotation history: pruned {prune()}")
    elif cmd == "show":
        for s in recent(int(sys.argv[2]) if len(sys.argv) > 2 else 10):
            n = {g: len(v) for g, v in (s.get("grains") or {}).items()}
            print(s.get("as_of"), n)
    else:
        print(__doc__)
        raise SystemExit(2)
