"""Central allowlist gate for push notifications.

Goal: only let alerts buzz the phone for tickers the user actually cares about.
Without this every detector (volume breakouts, rising momentum, stage
breakdowns, catalyst surges, VCP-watch) fans out across the entire universe
and the phone gets noisy.

Default scope = "top5_watchlist":
  - Top 5 SEPA candidates of the latest scan_run, ranked by
    (rating tier → score) — same order the SEPA page's "Top picks" rail uses.
  - Every ticker on the user's watchlist.

Override with env var ALERT_SCOPE:
  - "top5_watchlist" (default) — narrow
  - "watchlist"               — only watchlist (drop top-5 entirely)
  - "universe"                — old behaviour, anything fires

The result is cached for ALLOWLIST_TTL_SEC so a cron run that fires 30
breakout alerts only computes the allowlist once.

Every alert source MUST go through ``allowed_for(ticker)`` before sending push.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

log = logging.getLogger("push.scope")

ALLOWLIST_TTL_SEC = 60                # 60s — fast enough to react to user edits
DEFAULT_TOP_N = 5

# Rating-tier ordering for "top 5" — same as the SEPA page's top-picks rail.
_RATING_RANK = {
    "STRONG_BUY": 5,
    "BUY":         4,
    "WATCH":       3,
    "NEUTRAL":     2,
    "AVOID":       1,
}


_cache: dict = {"ts": 0, "scope": None, "tickers": frozenset()}


def _scope_mode() -> str:
    return (os.getenv("ALERT_SCOPE") or "top5_watchlist").strip().lower()


def _top_n() -> int:
    try:
        return max(0, int(os.getenv("ALERT_TOP_N") or DEFAULT_TOP_N))
    except Exception:
        return DEFAULT_TOP_N


def _get_db():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        return client[os.getenv("MONGO_DB", "cheetah")]
    except Exception as exc:
        log.warning("push.scope: mongo unavailable: %s", exc)
        return None


def _compute_top_picks(db, n: int) -> list[str]:
    """Return the top-N tickers from the latest scan_run, ranked by rating
    tier first, then composite score. Mirrors Sepa.tsx topPicks logic."""
    if db is None:
        return []
    latest = db.scan_runs.find_one({}, sort=[("generated_at", -1)])
    if not latest:
        return []
    cands = list(db.candidate_snapshots.find(
        {"scan_run_id": latest["_id"]},
        {"symbol": 1, "rating": 1, "score": 1, "is_candidate": 1},
    ))
    # Prefer tickers tagged is_candidate (full SEPA gate passes); if none,
    # fall back to the highest-rated names so an empty-candidate day still
    # sees alerts on the strongest WATCH tier.
    primary = [c for c in cands if c.get("is_candidate")]
    pool = primary if primary else cands
    pool.sort(
        key=lambda c: (
            _RATING_RANK.get((c.get("rating") or "AVOID").upper(), 0),
            float(c.get("score") or 0),
        ),
        reverse=True,
    )
    return [(c.get("symbol") or "").upper() for c in pool[:n] if c.get("symbol")]


def _compute_watchlist(db) -> list[str]:
    if db is None:
        return []
    try:
        rows = db.watchlist.find({}, {"ticker": 1})
        return [(r.get("ticker") or "").upper() for r in rows if r.get("ticker")]
    except Exception:
        return []


def _refresh_if_stale(force: bool = False) -> frozenset[str]:
    now = time.time()
    scope = _scope_mode()
    if (
        not force
        and _cache["scope"] == scope
        and (now - _cache["ts"]) < ALLOWLIST_TTL_SEC
    ):
        return _cache["tickers"]

    if scope == "universe":
        # No filter — empty-set sentinel meaning "everything is allowed".
        result = frozenset(["__UNIVERSE__"])
    else:
        db = _get_db()
        tickers: set[str] = set()
        if scope in ("top5_watchlist", "top5", "topn"):
            tickers.update(_compute_top_picks(db, _top_n()))
        if scope in ("top5_watchlist", "watchlist", "wl"):
            tickers.update(_compute_watchlist(db))
        result = frozenset(tickers)

    _cache["ts"] = now
    _cache["scope"] = scope
    _cache["tickers"] = result
    log.info("push.scope refreshed: scope=%s n=%d sample=%s",
             scope, len(result), list(result)[:8])
    return result


def allowed_for(ticker: str) -> bool:
    """Return True if push alerts for ``ticker`` should fire under the
    current scope. Always True when ALERT_SCOPE=universe."""
    if not ticker:
        return False
    allowed = _refresh_if_stale()
    if "__UNIVERSE__" in allowed:
        return True
    return ticker.upper() in allowed


def current_allowlist() -> dict:
    """Diagnostic — what is currently in the allowlist? Used by the
    /push/scope endpoint for transparency."""
    allowed = _refresh_if_stale(force=True)
    if "__UNIVERSE__" in allowed:
        return {"scope": "universe", "tickers": [], "size": -1, "note": "all tickers allowed"}
    return {
        "scope": _scope_mode(),
        "top_n": _top_n(),
        "tickers": sorted(allowed),
        "size": len(allowed),
    }


def invalidate() -> None:
    """Force the next allowed_for() call to recompute. Call after the user
    edits their watchlist or after a fresh scan persists."""
    _cache["ts"] = 0
