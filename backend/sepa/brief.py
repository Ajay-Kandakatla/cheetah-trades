"""Morning brief — "what to watch when I open the app at 8:30am".

Consumes the 5pm scan (latest.json) + watchlist and produces a compact,
action-oriented JSON the UI banner renders:

  - top_candidates: 5 SEPA picks with pivot/stop/score.
  - watchlist_alerts: for each held position — sell signals, near-pivot, etc.
  - market_context: safe_to_long flag + SPY/QQQ state.
  - catalyst_today: earnings reporting today + fresh 13Ds + insider clusters.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import prices, sell_signals, market_context
from .catalyst import catalyst_for
from .insider import insider_activity
from .scanner import load_latest, load_watchlist, CACHE_DIR

BRIEF_PATH = CACHE_DIR / "brief.json"


def _watchlist_status(item: dict) -> dict:
    sym = item["symbol"]
    df = prices.load_prices(sym)
    if df is None:
        return {**item, "error": "no_price"}
    sells = sell_signals.evaluate(df, entry_price=item.get("entry"),
                                   stop_price=item.get("stop"))
    last = float(df["close"].iloc[-1])
    entry = item.get("entry") or last
    stop = item.get("stop") or last * 0.92
    pnl_pct = (last / entry - 1) * 100 if entry else 0
    to_stop_pct = (last / stop - 1) * 100 if stop else 0
    return {
        **item,
        "last_price": round(last, 4),
        "pnl_pct": round(pnl_pct, 2),
        "distance_to_stop_pct": round(to_stop_pct, 2),
        "sell_signals": sells,
        "action": sells.get("action") if sells else "HOLD",
    }


def generate_brief(with_catalyst: bool = True) -> dict:
    scan = load_latest() or {}
    mkt = scan.get("market_context") or market_context.market_state()

    top_candidates = (scan.get("candidates") or [])[:5]
    # Strip heavy fields for a slim brief payload
    slim = []
    for c in top_candidates:
        slim.append({
            "symbol": c["symbol"],
            "score": c["score"],
            "rs_rank": c["rs_rank"],
            "stage": c.get("stage"),
            "entry_setup": c.get("entry_setup"),
            "trend_passed": c["trend"]["passed"],
            "vcp_summary": {
                "n": (c.get("vcp") or {}).get("n_contractions"),
                "depth": (c.get("vcp") or {}).get("base_depth_pct"),
                "tight": (c.get("vcp") or {}).get("tight_right_side"),
            } if c.get("vcp") else None,
        })

    # Watchlist status (real-time price pull from cache)
    watchlist = [_watchlist_status(x) for x in load_watchlist()]

    # Catalyst sweep for slim candidates + watchlist
    catalyst_today: list[dict] = []
    insider_today: list[dict] = []
    if with_catalyst:
        targets = list({x["symbol"] for x in slim} | {x["symbol"] for x in watchlist})

        async def do() -> None:
            sem = asyncio.Semaphore(4)

            async def one(sym: str) -> None:
                async with sem:
                    try:
                        cat = await catalyst_for(sym)
                        if cat.get("earnings_upcoming") or cat.get("news_sentiment_score", 0) != 0:
                            catalyst_today.append(cat)
                    except Exception:
                        pass
                    try:
                        ins = await insider_activity(sym)
                        if ins.get("form4_cluster_buy") or ins.get("has_recent_13d"):
                            insider_today.append(ins)
                    except Exception:
                        pass

            await asyncio.gather(*(one(s) for s in targets))

        asyncio.run(do())

    # Watchlist sell-alerts = action != HOLD
    watchlist_alerts = [w for w in watchlist if w.get("action") and w["action"] != "HOLD"]

    # Personal todos slice — important + today's, for the brief page + push body
    # Cron-driven brief uses the default user identity. The frontend's
    # MorningTodosCard hits /todos/brief-slice live so each user sees their own.
    todos_slice: dict = {"important": [], "today": [], "upcoming_count": 0}
    try:
        from todos import store as todos_store
        import os
        default_user = os.getenv("DEFAULT_USER_EMAIL", "ajay@example.com")
        todos_slice = todos_store.list_for_brief(user_email=default_user)
    except Exception as exc:
        import logging
        logging.getLogger("sepa.brief").warning("todos slice failed: %s", exc)

    payload = {
        "generated_at": int(time.time()),
        "generated_at_iso": datetime.utcnow().isoformat() + "Z",
        "market_context": mkt,
        "top_candidates": slim,
        "watchlist": watchlist,
        "watchlist_alerts": watchlist_alerts,
        "catalyst_today": catalyst_today,
        "insider_today": insider_today,
        "todos": todos_slice,
        "scan_generated_at": scan.get("generated_at"),
    }
    BRIEF_PATH.write_text(json.dumps(payload, default=str))

    # Push notification — taps route to /morning so the user lands on the
    # full Morning Brief view from a phone notification.
    try:
        from . import notify
        top_count = len(payload.get("top_candidates") or [])
        alerts_count = len(payload.get("watchlist_alerts") or [])
        important_count = len(todos_slice.get("important") or [])
        today_count = len(todos_slice.get("today") or [])
        mkt = (payload.get("market_context") or {}).get("label") or "?"
        body_parts = [f"{top_count} candidate(s)"]
        if alerts_count:
            body_parts.append(f"{alerts_count} position alert(s)")
        if important_count:
            body_parts.append(f"⭐ {important_count} important task(s)")
        if today_count:
            body_parts.append(f"📅 {today_count} due today")
        notify.send_alert(
            title=f"📰 Morning brief — {mkt}",
            body=" · ".join(body_parts),
            url="/morning",
            kind="morning_brief",
        )
    except Exception as exc:
        import logging
        logging.getLogger("sepa.brief").warning("brief notify failed: %s", exc)

    return payload


def load_brief() -> Optional[dict]:
    if not BRIEF_PATH.exists():
        return None
    try:
        return json.loads(BRIEF_PATH.read_text())
    except Exception:
        return None
