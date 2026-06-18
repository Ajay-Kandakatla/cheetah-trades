"""Leaderboard breakout watcher (Ajay 2026-06-03).

Pushes a notification titled "Leaderboard" when a name that's ON the rank
leaderboard breaks out today. Runs every 15 min during the regular session.

  • breakout = the live scan's own flag: high_vol_breakout AND days_since_breakout==0
    (i.e. it cleared its pivot on volume TODAY, not a stale multi-day-old breakout).
  • de-dup per (symbol, ET day) so a name pushes at most once a day.
  • backfills prefs.leaderboard_breakout=True onto existing subscriptions, because
    send_to_all filters on prefs.{kind}==True and a brand-new kind is absent from
    older subs (the silent-drop trap that bit price_alerts before).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from push import hooks
from . import history, leaderboard as lb, scanner

log = logging.getLogger("sepa.leaderboard_breakout_watch")
ET = ZoneInfo("America/New_York")


def _today_et() -> str:
    return datetime.now(ET).strftime("%Y-%m-%d")


def _is_fresh_breakout(row: dict) -> bool:
    """Broke out TODAY on volume (not a multi-day-old breakout)."""
    v = row.get("volume") or {}
    return bool(v.get("high_vol_breakout") and v.get("days_since_breakout") == 0)


def fresh_breakouts(leader_syms, live: dict) -> list[dict]:
    """Pure: leaderboard names whose live row is a fresh breakout today."""
    out = []
    for sym in leader_syms:
        r = live.get(sym)
        if r and _is_fresh_breakout(r):
            out.append({
                "symbol": sym,
                "last_close": r.get("last_close"),
                "day_change_pct": r.get("day_change_pct"),
                "rs_rank": r.get("rs_rank"),
            })
    return out


def _ensure_pref_backfill(db) -> None:
    """Grant the new kind to existing subscriptions so the push actually lands."""
    try:
        db.push_subscriptions.update_many(
            {"prefs.leaderboard_breakout": {"$exists": False}},
            {"$set": {"prefs.leaderboard_breakout": True}},
        )
    except Exception as exc:
        log.warning("leaderboard_breakout pref backfill failed: %s", exc)


def run() -> dict:
    db = history._get_db()
    if db is None:
        return {"ok": False, "reason": "db unavailable"}
    _ensure_pref_backfill(db)

    leaders = (lb.leaderboard(30, 14) or {}).get("leaders") or []
    rankmap = {l["symbol"]: l.get("current_rank") for l in leaders}
    if not rankmap:
        return {"ok": True, "broke_out": 0}

    latest = scanner.load_latest() or {}
    live = {r.get("symbol"): r for r in (latest.get("all_results") or [])}
    fresh = fresh_breakouts(set(rankmap), live)
    # BUYABLE-ONLY (Ajay 2026-06-18: "kill all random breakout push besides the
    # buyable"). Only push a leaderboard breakout if the name passes the strict
    # Minervini buy gate (is_buyable) in the live scan.
    fresh = [b for b in fresh if bool((live.get(b.get("symbol")) or {}).get("is_buyable"))]

    today = _today_et()
    new = []
    for b in fresh:
        key = {"symbol": b["symbol"], "date_et": today}
        if db.leaderboard_breakout_alerts.find_one(key):
            continue                                     # already pushed this name today
        db.leaderboard_breakout_alerts.insert_one({**key, "ts": int(time.time())})
        b["rank"] = rankmap.get(b["symbol"])
        new.append(b)

    if not new:
        return {"ok": True, "broke_out": 0}
    res = hooks.notify_leaderboard_breakout(broke_out=new, today_et=today)
    log.info("leaderboard breakout: pushed %d %s", len(new), [b["symbol"] for b in new])
    return {"ok": True, "broke_out": len(new), "symbols": [b["symbol"] for b in new], "push": res}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run())
