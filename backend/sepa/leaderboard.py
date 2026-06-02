"""SEPA rank leaderboard — day-level "honourable mentions" for the portfolio page.

Built from scan history (sepa.history): across every scan in the lookback window
it re-ranks each run by score, then per symbol computes where it has been —
best / worst / current rank, how CONSISTENTLY it sat near the top (persistence),
and how VOLATILE its rank was (range). The point (user 2026-06-02): surface the
names that have been scoring high *before* they break out — "if BB was in
honourable mentions I'd have caught the breakout ahead of time" — plus flag the
volatile movers (BB went #1 → #100 → #1).

Complements `top_picks` (what's buyable RIGHT NOW) with "who's been strong, and
who's primed." Reads the same history other tabs use; cached briefly.
"""
from __future__ import annotations

import time
from typing import Optional

from . import history, scanner

LOOKBACK_DAYS = 14          # ≈ 10 business days
TOP_TIER = 20               # "scored high" = ranked within the top this many
VOLATILE_RANGE = 30         # best→worst rank spread that counts as "volatile"
MAX_RUNS = 40               # cap runs processed per call (cost guard)

_cache: dict = {}
_CACHE_TTL_SEC = 180


def _rank_runs(db, cutoff: int) -> list[dict]:
    """Most-recent runs in the window, each as {symbol: rank} by score desc."""
    runs = list(db.scan_runs.find({"generated_at": {"$gte": cutoff}},
                                   {"generated_at": 1})
                .sort("generated_at", -1).limit(MAX_RUNS))
    out = []
    for run in runs:
        snaps = list(db.candidate_snapshots.find(
            {"scan_run_id": run["_id"]}, {"symbol": 1, "score": 1}))
        snaps = [s for s in snaps if s.get("score") is not None]
        if not snaps:
            continue
        snaps.sort(key=lambda s: -s["score"])
        out.append({
            "generated_at": run["generated_at"],
            "rank": {s["symbol"]: i + 1 for i, s in enumerate(snaps)},
            "score": {s["symbol"]: s["score"] for s in snaps},
        })
    return out  # newest first


def aggregate(runs: list[dict], live: dict, n: int) -> list[dict]:
    """Pure: collapse ranked runs (newest first) + a live-status map into the
    sorted leaderboard rows. Separated from Mongo so it's unit-testable."""
    agg: dict[str, dict] = {}
    for run in runs:                                      # newest first
        for sym, rk in run["rank"].items():
            a = agg.setdefault(sym, {"ranks": [], "scores": []})
            a["ranks"].append(rk)
            a["scores"].append(run["score"][sym])

    rows = []
    for sym, a in agg.items():
        ranks = a["ranks"]
        appearances = len(ranks)
        best, worst = min(ranks), max(ranks)
        avg = round(sum(ranks) / appearances, 1)
        persistence = round(100.0 * sum(1 for r in ranks if r <= TOP_TIER) / appearances)
        cur = live.get(sym) or {}
        buyable = bool(cur.get("is_buyable"))
        ready = bool(cur.get("setup_ready"))
        flag = ("breaking_out" if buyable else "primed" if ready
                else "volatile" if (worst - best) >= VOLATILE_RANGE else "steady")
        rows.append({
            "symbol":        sym,
            "name":          cur.get("name"),
            "current_rank":  ranks[0],            # newest run
            "current_score": a["scores"][0],
            "rs_rank":       cur.get("rs_rank"),
            "best_rank":     best,
            "worst_rank":    worst,
            "avg_rank":      avg,
            "rank_range":    worst - best,        # volatility
            "appearances":   appearances,
            "persistence_pct": persistence,       # % of scans in the top TOP_TIER
            "status":        "buyable" if buyable else "ready" if ready else "watch",
            "flag":          flag,
        })

    # Honourable mentions: most consistently high first; ties → best rank.
    rows.sort(key=lambda r: (-r["persistence_pct"], r["avg_rank"], r["best_rank"]))
    return rows[:n]


def leaderboard(n: int = 12, lookback_days: int = LOOKBACK_DAYS) -> dict:
    key = (n, lookback_days)
    hit = _cache.get(key)
    if hit and time.time() - hit["ts"] < _CACHE_TTL_SEC:
        return hit["data"]

    db = history._get_db()
    empty = {"leaders": [], "scans_in_window": 0, "lookback_days": lookback_days}
    if db is None:
        return empty

    cutoff = int(time.time()) - lookback_days * 86400
    runs = _rank_runs(db, cutoff)
    if not runs:
        return empty

    latest = scanner.load_latest() or {}
    live = {r.get("symbol"): r
            for r in (latest.get("all_results") or latest.get("candidates") or [])}

    data = {
        "leaders":         aggregate(runs, live, n),
        "scans_in_window": len(runs),
        "lookback_days":   lookback_days,
        "top_tier":        TOP_TIER,
    }
    _cache[key] = {"data": data, "ts": time.time()}
    return data
