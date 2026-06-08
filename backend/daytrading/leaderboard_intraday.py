"""Leaderboard ∩ intraday — the rank-consistent SEPA leaders ranked by TODAY's
intraday move, with a live buyable flag.

Powers the Day-Trading "Leaderboard leaders · intraday movers" section: of the
names that persist near the top of the SEPA leaderboard, which are MOVING today
and which are buyable right now. Derived view — reuses the rank leaderboard +
live prices + the latest scan's buyable flag; computes nothing new and leaves
scanner.py untouched (Rule #2). Educational, NOT advice.
"""
from __future__ import annotations

import logging
import time

log = logging.getLogger("daytrading.leaderboard_intraday")

_CACHE: dict = {"at": 0.0, "data": None, "key": None}
_TTL_SEC = 120          # live prices move; 2-min cache (matches /sepa/live-prices)


def _market_session() -> str:
    """premarket | open | afterhours | closed (US/Eastern, weekday clock; no
    holiday calendar — honest-enough for the 'wait for the open' framing)."""
    from datetime import datetime, timezone
    try:
        from zoneinfo import ZoneInfo
        et = datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York"))
    except Exception:
        return "unknown"
    if et.weekday() >= 5:
        return "closed"
    hm = et.hour * 60 + et.minute
    if 4 * 60 <= hm < 9 * 60 + 30:
        return "premarket"
    if 9 * 60 + 30 <= hm < 16 * 60:
        return "open"
    if 16 * 60 <= hm < 20 * 60:
        return "afterhours"
    return "closed"


def _compute(n: int, lookback_days: int) -> dict:
    from sepa import leaderboard as lb, scanner as sc, prices as px

    lb_data = lb.leaderboard(n=n, lookback_days=lookback_days) or {}
    leaders = list(lb_data.get("leaders") or [])
    session = _market_session()
    base = {
        "as_of": int(time.time()),
        "as_of_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "market_session": session,         # premarket | open | afterhours | closed
        "is_open": session == "open",
        # When closed/pre-open this list is the LAST-CLOSE watch list for the open;
        # when open the same names carry a live intraday move.
        "as_of_close": session != "open",
        "scans_in_window": lb_data.get("scans_in_window"),
        "lookback_days": lookback_days,
        "disclaimer": "Rank-consistent SEPA leaders by today's intraday move. Educational, not advice.",
    }
    if not leaders:
        return {**base, "available": False, "leaders": [], "n": 0, "buyable_count": 0}

    symbols = [r.get("symbol") for r in leaders if r.get("symbol")]
    try:
        live = px.bulk_live_prices(symbols) or {}
    except Exception as exc:
        log.warning("leaderboard_intraday live prices failed: %s", exc)
        live = {}
    latest = sc.load_latest() or {}
    by_sym = {r.get("symbol"): r for r in (latest.get("all_results") or []) if r.get("symbol")}

    rows = []
    for r in leaders:
        sym = r.get("symbol")
        snap = live.get(sym) or {}
        rec = by_sym.get(sym) or {}
        chg = snap.get("change_pct")
        # In premarket/closed the regular-session `price` is 0 — fall back to the
        # extended-hours last trade so the list still shows a live number.
        last = snap.get("price") or snap.get("last_trade_price") or r.get("close")
        rows.append({
            **r,
            "intraday_change_pct": round(chg, 2) if isinstance(chg, (int, float)) else None,
            "last_price": last,
            "prev_close": snap.get("prev_day_close"),     # the "as of yesterday close" anchor
            "volume_today": snap.get("volume"),
            "is_buyable": bool(rec.get("is_buyable")),
            "setup_ready": bool(rec.get("setup_ready")),
            "rating": rec.get("rating") or r.get("status"),
        })

    # Rank by today's move — gainers first; missing prices sink to the bottom.
    rows.sort(key=lambda x: (x["intraday_change_pct"] is None, -(x["intraday_change_pct"] or 0)))
    for i, r in enumerate(rows, 1):
        r["intraday_rank"] = i

    return {
        **base,
        "available": True,
        "leaders": rows,
        "n": len(rows),
        "buyable_count": sum(1 for r in rows if r["is_buyable"]),
        "up_count": sum(1 for r in rows if (r["intraday_change_pct"] or 0) > 0),
    }


def get_leaders_intraday(n: int = 12, lookback_days: int = 14, force: bool = False) -> dict:
    """Cached entry point (2-min). The badge/section hits this on every refresh."""
    now = time.time()
    key = (n, lookback_days)
    if (not force and _CACHE["data"] is not None and _CACHE.get("key") == key
            and (now - _CACHE["at"]) < _TTL_SEC):
        return _CACHE["data"]
    data = _compute(n, lookback_days)
    _CACHE.update(at=now, data=data, key=key)
    return data
