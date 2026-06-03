"""Per-symbol RANK history — feeds the SEPA detail page's "Ranking" tab.

"Like TradingView, but for rank": how a stock has moved through the SEPA ranking
over time, so you can *see* it climb into (or fall out of) the top, and line the
moves up against real events (breakout / became-buyable / stage change).

Plugs straight into the existing scan history (sepa.history.candidate_snapshots)
— the same data the leaderboard uses. Rank is DERIVED per scan: a symbol's rank =
how many qualifiers (trend.pass_all) scored higher, +1. Count-based so we never
load a whole scan into memory.

Granularity:
  daily     — the latest scan per ET date (clean day-over-day trend), ~30 days
  intraday  — every scan in the window (shows within-day churn), ~10 days
"""
from __future__ import annotations

import time
from typing import Optional

from . import history

MAX_POINTS_DAILY = 45
MAX_POINTS_INTRADAY = 90
_cache: dict = {}
_CACHE_TTL_SEC = 180


def derive_events(snap: dict, is_qual: bool, prev_buyable: Optional[bool],
                  prev_stage: Optional[int]) -> tuple[list[str], bool, Optional[int]]:
    """Pure: from one snapshot + the previous point's state, return
    (events, buyable_now, stage). Separated from Mongo so it's unit-testable.
    'became_buyable' is an EDGE (False→True), not a level."""
    vol = snap.get("volume") or {}
    breakout = bool(vol.get("high_vol_breakout") or vol.get("pocket_pivot"))
    stage = snap.get("stage")
    buyable = bool(is_qual and stage == 2 and snap.get("entry_setup") and breakout)
    events: list[str] = []
    if breakout:
        events.append("breakout")
    if prev_buyable is False and buyable:
        events.append("became_buyable")
    if prev_stage is not None and stage is not None and stage != prev_stage:
        events.append(f"stage_{stage}")
    return events, buyable, stage


def _select_runs(db, cutoff: int, granularity: str) -> list[dict]:
    runs = list(db.scan_runs.find(
        {"generated_at": {"$gte": cutoff}},
        {"generated_at": 1, "date_et": 1}).sort("generated_at", 1))   # oldest first
    if granularity == "daily":
        by_date: dict = {}
        for r in runs:                                 # asc → last per date = latest that day
            by_date[r.get("date_et")] = r
        runs = [by_date[d] for d in sorted(by_date) if d]
        return runs[-MAX_POINTS_DAILY:]
    return runs[-MAX_POINTS_INTRADAY:]


def rank_history(symbol: str, days: int = 30, granularity: str = "daily") -> dict:
    symbol = (symbol or "").upper().strip()
    granularity = granularity if granularity in ("daily", "intraday") else "daily"
    key = (symbol, days, granularity)
    hit = _cache.get(key)
    if hit and time.time() - hit["ts"] < _CACHE_TTL_SEC:
        return hit["data"]

    base = {"symbol": symbol, "granularity": granularity, "days": days, "points": [],
            "best_rank": None, "worst_rank": None, "current_rank": None}
    db = history._get_db()
    if db is None or not symbol:
        return base

    cutoff = int(time.time()) - days * 86400
    runs = _select_runs(db, cutoff, granularity)

    points: list[dict] = []
    prev_buyable: Optional[bool] = None
    prev_stage: Optional[int] = None
    for run in runs:
        rid = run["_id"]
        snap = db.candidate_snapshots.find_one(
            {"scan_run_id": rid, "symbol": symbol},
            {"score": 1, "last_close": 1, "stage": 1, "volume": 1, "entry_setup": 1, "trend": 1})
        t = run.get("generated_at")
        date = run.get("date_et")
        if not snap or snap.get("score") is None:
            points.append({"t": t, "date": date, "rank": None, "total": None,
                           "score": None, "price": None, "events": []})
            prev_buyable = None                          # gap resets the became-buyable edge
            continue

        s = snap["score"]
        is_qual = bool((snap.get("trend") or {}).get("pass_all"))
        total = db.candidate_snapshots.count_documents(
            {"scan_run_id": rid, "trend.pass_all": True})
        rank = None
        if is_qual:
            higher = db.candidate_snapshots.count_documents(
                {"scan_run_id": rid, "trend.pass_all": True, "score": {"$gt": s}})
            rank = higher + 1

        events, buyable, stage = derive_events(snap, is_qual, prev_buyable, prev_stage)
        prev_buyable = buyable
        prev_stage = stage

        points.append({
            "t": t, "date": date, "rank": rank, "total": total,
            "score": round(float(s), 1), "price": snap.get("last_close"),
            "events": events,
        })

    ranked = [p["rank"] for p in points if p["rank"]]
    data = {
        "symbol": symbol, "granularity": granularity, "days": days, "points": points,
        "best_rank": min(ranked) if ranked else None,
        "worst_rank": max(ranked) if ranked else None,
        "current_rank": next((p["rank"] for p in reversed(points) if p["rank"]), None),
    }
    _cache[key] = {"data": data, "ts": time.time()}
    return data


MAX_COMPARE = 12


def rank_history_batch(symbols: list, days: int = 30, granularity: str = "daily") -> dict:
    """Rank trajectories for SEVERAL symbols sharing one date axis — feeds the
    multi-stock compare chart. Ranks each scan ONCE (qualifiers by score) and
    reads every requested symbol off it, so cost is per-run not per-symbol."""
    syms = [s.upper().strip() for s in (symbols or []) if s and s.strip()][:MAX_COMPARE]
    granularity = granularity if granularity in ("daily", "intraday") else "daily"
    key = ("batch", tuple(syms), days, granularity)
    hit = _cache.get(key)
    if hit and time.time() - hit["ts"] < _CACHE_TTL_SEC:
        return hit["data"]

    base = {"symbols": syms, "days": days, "granularity": granularity, "series": {}}
    db = history._get_db()
    if db is None or not syms:
        return base

    cutoff = int(time.time()) - days * 86400
    runs = _select_runs(db, cutoff, granularity)          # oldest → newest
    series: dict[str, list] = {s: [] for s in syms}
    for run in runs:
        snaps = list(db.candidate_snapshots.find(
            {"scan_run_id": run["_id"]}, {"symbol": 1, "score": 1, "trend.pass_all": 1}))
        quals = [s for s in snaps
                 if s.get("score") is not None and (s.get("trend") or {}).get("pass_all")]
        quals.sort(key=lambda s: -s["score"])
        rankmap = {s["symbol"]: i + 1 for i, s in enumerate(quals)}
        scoremap = {s["symbol"]: s["score"] for s in quals}
        total = len(quals)
        t, date = run.get("generated_at"), run.get("date_et")
        for sym in syms:
            r = rankmap.get(sym)
            series[sym].append({
                "t": t, "date": date, "rank": r, "total": total,
                "score": round(float(scoremap[sym]), 1) if sym in scoremap else None,
            })

    out = {}
    for sym in syms:
        pts = series[sym]
        ranked = [p["rank"] for p in pts if p["rank"]]
        out[sym] = {
            "points": pts,
            "best_rank": min(ranked) if ranked else None,
            "worst_rank": max(ranked) if ranked else None,
            "current_rank": next((p["rank"] for p in reversed(pts) if p["rank"]), None),
        }

    data = {"symbols": syms, "days": days, "granularity": granularity, "series": out}
    _cache[key] = {"data": data, "ts": time.time()}
    return data
