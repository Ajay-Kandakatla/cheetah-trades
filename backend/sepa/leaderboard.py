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
MAX_DAYS = 30               # cap trading days processed per call (cost guard)

_cache: dict = {}
_CACHE_TTL_SEC = 180


def _rank_runs(db, cutoff: int) -> list[dict]:
    """ONE scan per trading day (the latest that day), each as {symbol: rank} by
    score desc. Day-LEVEL on purpose: persistence then means "% of DAYS in the
    top", which is what "how often is it on top this week" actually asks. Ranking
    by raw scans instead over-weighted the last few dense-intraday days (recent
    days have ~10 scans each, so the most-recent-N-scans window only spanned ~3
    days) and dropped week-strong names — BB read 28% over recent scans but 88%
    over recent DAYS (top-20 on 7 of 8 days). 2026-06-02."""
    runs = list(db.scan_runs.find({"generated_at": {"$gte": cutoff}},
                                   {"generated_at": 1, "date_et": 1})
                .sort("generated_at", 1))                  # oldest first
    by_date: dict = {}
    for r in runs:
        if r.get("date_et"):
            by_date[r["date_et"]] = r                      # last per date = latest that day
    daily = [by_date[d] for d in sorted(by_date)][-MAX_DAYS:]
    out = []
    for run in reversed(daily):                            # newest first (aggregate uses ranks[0] = current)
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


def _drop_reason(stage, dist_days, accum) -> str:
    """Human 'why the rank slipped', from the current scan's weakening signals,
    most-severe first: a Stage downgrade > a distribution cluster (book p.76) >
    volume turning, else a relative ease vs stronger peers. Pure → unit-testable.
    Only meaningful for names whose rank fell well below their best."""
    if stage is not None and stage != 2:
        return f"Stage {stage} — advance stalling"
    if dist_days is not None and dist_days >= 4:
        return f"{dist_days} distribution days — institutions selling"
    if accum == "distributing":
        return "volume distributing — supply > demand"
    if accum == "neutral":
        return "demand cooled — volume neutral"
    return "score eased vs stronger peers"


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
        vol = cur.get("volume") or {}
        stage = cur.get("stage")
        stage = stage.get("stage") if isinstance(stage, dict) else stage
        last_vol = vol.get("last_vol")
        avg50 = vol.get("avg_vol_50")
        close = cur.get("last_close")
        dist_days = vol.get("distribution_days_25")
        accum = vol.get("accumulation_strength")
        dropped = ranks[0] > best + 5            # rank fell well below its best
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
            # Enrichment (Ajay 2026-06-03 "add total volume + why these went down"):
            "volume":        last_vol,                                          # today's share volume
            "dollar_vol":    int(last_vol * close) if (last_vol and close) else None,
            "vol_x":         round(last_vol / avg50, 2) if (last_vol and avg50) else None,  # relative vol
            "stage":         stage,
            "distribution_days": dist_days,
            "accumulation":  accum,
            "drop_reason":   _drop_reason(stage, dist_days, accum) if dropped else None,
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
