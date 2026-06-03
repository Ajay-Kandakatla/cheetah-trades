"""SEPA top-picks TRACKER — how the "Top Picks" set has churned over time.

The Top-Picks rail shows what's buyable RIGHT NOW, so it changes scan-to-scan (a
name breaks out, gets extended, drops off). Ajay (2026-06-03) saw one set on the
phone's Morning Brief (BB/LBRT/NUE) and a different one on the desktop rail
(BB/TECL/CORZ/LBRT/AMAT) and wanted to *track that drift* to build confidence —
who has PERSISTED as a pick vs who was a one-scan flash.

Reconstructed from the SAME scan history (`candidate_snapshots`) the leaderboard
and rank chart already use — no new capture, so it works retroactively. Because
`is_buyable` / `setup_ready` are derived (not stored), we re-derive a pick set per
scan from stored fields, mirroring `sepa.top_picks` ordering exactly:

  buyable = qualifier (trend.pass_all) AND stage 2 AND entry_setup present AND
            (high_vol_breakout OR pocket_pivot)
  ready   = qualifier AND stage 2 AND entry_setup present AND not breakout   (backfill)

ranked buyable-first by tier (days_since_breakout: 0 today < ≤5 this week <
in-base) then score, then ready by score — the same actionability order
`top_picks.py` applies live — and the top `n` are "the picks" for that scan.

Two views (the frontend's two tabs):
  • streak + churn (granularity=intraday): per-SCAN. The current pick set with
    each name's streak (consecutive recent scans as a pick), first-seen,
    appearances and score trend; plus churn = who ENTERED / DROPPED vs the prior
    scan.
  • daily (granularity=daily): one pick set per trading day, oldest→newest, each
    day's entered/dropped vs the prior day (the "new vs last" flag) + per-name
    scores for a trend line.

Pure helpers (`pickset_from_quals`, `build_tracker`) are split from Mongo so they
unit-test on synthetic data — see tests/test_top_picks_history.py.
"""
from __future__ import annotations

import time
from typing import Optional

from . import history, rank_history, scanner

RECENT_BREAKOUT_DAYS = 5            # tier-1 window — matches top_picks.RECENT_BREAKOUT_DAYS
_cache: dict = {}
_CACHE_TTL_SEC = 180


def _tier(dsb: Optional[int]) -> int:
    if dsb == 0:
        return 0
    if dsb is not None and dsb <= RECENT_BREAKOUT_DAYS:
        return 1
    return 2


def pickset_from_quals(quals: list, n: int) -> list:
    """Pure: from one scan's QUALIFIER snapshots (trend.pass_all rows), reconstruct
    the ordered top-`n` pick set — same gate + ordering as top_picks.py."""
    picks = []
    for s in quals:
        if s.get("score") is None:
            continue
        vol = s.get("volume") or {}
        st2 = s.get("stage") == 2
        has_setup = bool(s.get("entry_setup"))
        if not (st2 and has_setup):
            continue
        breakout = bool(vol.get("high_vol_breakout") or vol.get("pocket_pivot"))
        picks.append({
            "symbol": s.get("symbol"),
            "score": s.get("score"),
            "status": "buyable" if breakout else "ready",
            "tier": _tier(vol.get("days_since_breakout")),
        })
    buyable = sorted((p for p in picks if p["status"] == "buyable"),
                     key=lambda p: (p["tier"], -p["score"]))
    ready = sorted((p for p in picks if p["status"] == "ready"),
                   key=lambda p: -p["score"])
    return (buyable + ready)[:n]


def build_tracker(sets: list, n: int) -> dict:
    """Pure: from per-scan pick sets (oldest→newest), each
    {t, date, picks:[{symbol,score,status,tier}], }, build the tracker payload:
    timeline (entered/dropped per point), the enriched CURRENT set (streak,
    appearances, first-seen, score trend, is_new) and the latest-vs-prior churn."""
    # normalize: attach syms + scoremap
    norm = []
    for s in sets:
        picks = s.get("picks") or []
        norm.append({
            "t": s.get("t"), "date": s.get("date"), "picks": picks,
            "syms": [p["symbol"] for p in picks],
            "scoremap": {p["symbol"]: p["score"] for p in picks},
        })

    timeline, prev = [], set()
    for s in norm:
        cur = set(s["syms"])
        timeline.append({
            "t": s["t"], "date": s["date"], "picks": s["syms"], "scores": s["scoremap"],
            "entered": sorted(cur - prev) if prev else [],
            "dropped": sorted(prev - cur) if prev else [],
        })
        prev = cur

    if not norm:
        return {"current": [], "churn": {"entered": [], "dropped": []}, "timeline": timeline}

    latest = norm[-1]
    prev_syms = set(norm[-2]["syms"]) if len(norm) >= 2 else set()
    current = []
    for p in latest["picks"]:
        sym = p["symbol"]
        streak = 0
        for s in reversed(norm):                       # consecutive runs from the end
            if sym in s["syms"]:
                streak += 1
            else:
                break
        appearances = sum(1 for s in norm if sym in s["syms"])
        first_date = next((s["date"] for s in norm if sym in s["syms"]), None)
        prev_score = next((s["scoremap"][sym] for s in reversed(norm[:-1])
                           if sym in s["scoremap"]), None)
        trend = "•"
        if prev_score is not None:
            trend = "▲" if p["score"] > prev_score else "▼" if p["score"] < prev_score else "•"
        current.append({
            "symbol": sym, "score": p["score"], "status": p["status"], "tier": p["tier"],
            "streak": streak, "appearances": appearances, "first_date": first_date,
            "score_trend": trend,
            "is_new": bool(prev_syms) and sym not in prev_syms,
        })

    churn = {
        "entered": sorted(set(latest["syms"]) - prev_syms) if prev_syms else [],
        "dropped": sorted(prev_syms - set(latest["syms"])) if prev_syms else [],
    }
    return {"current": current, "churn": churn, "timeline": timeline}


def top_picks_tracker(n: int = 5, days: int = 14, granularity: str = "daily") -> dict:
    granularity = granularity if granularity in ("daily", "intraday") else "daily"
    key = ("tracker", n, days, granularity)
    hit = _cache.get(key)
    if hit and time.time() - hit["ts"] < _CACHE_TTL_SEC:
        return hit["data"]

    base = {"granularity": granularity, "n": n, "days": days, "scans_in_window": 0,
            "current": [], "churn": {"entered": [], "dropped": []}, "timeline": []}
    db = history._get_db()
    if db is None:
        return base

    cutoff = int(time.time()) - days * 86400
    runs = rank_history._select_runs(db, cutoff, granularity)        # oldest→newest
    if not runs:
        return base

    sets = []
    for run in runs:
        quals = list(db.candidate_snapshots.find(
            {"scan_run_id": run["_id"], "trend.pass_all": True},
            {"symbol": 1, "score": 1, "stage": 1, "entry_setup": 1, "volume": 1}))
        sets.append({
            "t": run.get("generated_at"), "date": run.get("date_et"),
            "picks": pickset_from_quals(quals, n),
        })

    built = build_tracker(sets, n)

    # decorate the current set with company names from the live scan (best-effort)
    latest = scanner.load_latest() or {}
    names = {r.get("symbol"): r.get("name")
             for r in (latest.get("all_results") or latest.get("candidates") or [])}
    for c in built["current"]:
        c["name"] = names.get(c["symbol"])

    data = {"granularity": granularity, "n": n, "days": days,
            "scans_in_window": len(sets), **built}
    _cache[key] = {"data": data, "ts": time.time()}
    return data
