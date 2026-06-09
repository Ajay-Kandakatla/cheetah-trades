"""Pankaj-pick alerts — runs with the `alerts` cron (every ~5 min in market
hours). Fires when a price reaches one of Pankaj's own levels:

  • APPROACH      🟡 — within ~1.5% below a breakout trigger (set the buy-stop).
  • TRIGGER       🟢 — price tagged the breakout trigger intraday (watch for the
                       close-above confirmation Pankaj wants).
  • CLOSE_CONFIRM ✅ — price is above the trigger in the 15:55-16:10 ET close
                       window (the conservative daily-close entry).
  • ZONE          🟡 — price pulled into a demand zone (the conservative buy area).

The level/event logic is the PURE ``pankaj_picks.alert_events`` — this module is
just the IO shell: live price + once-per-day Mongo dedup + delivery. Alerts are
scoped to the owner only (Ajay: "add some alerts for me") and framed as Pankaj's
calls, not advice. Dedup collection: ``pankaj_alerts``.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Callable, Optional

log = logging.getLogger("sepa.pankaj_alerts")
_mem: dict = {}


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        return c[os.getenv("MONGO_DB", "cheetah")].pankaj_alerts
    except Exception:
        return None


def _now_et():
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    return datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York"))


def _et_date(now=None) -> str:
    try:
        return (now or _now_et()).strftime("%Y-%m-%d")
    except Exception:
        return time.strftime("%Y-%m-%d")


def _already(coll, key: str) -> bool:
    if coll is None:
        return key in _mem
    try:
        return coll.find_one({"_id": key}) is not None
    except Exception:
        return False


def _mark(coll, key: str) -> None:
    if coll is None:
        _mem[key] = 1
        return
    try:
        coll.update_one({"_id": key}, {"$set": {"ts": int(time.time())}}, upsert=True)
    except Exception as exc:
        log.debug("pankaj_alerts mark failed: %s", exc)


def _owner_email() -> Optional[str]:
    try:
        from auth import HOUSE_OWNER_EMAIL
        return HOUSE_OWNER_EMAIL
    except Exception:
        return None


def _live_price(sym: str) -> Optional[float]:
    try:
        from . import prices
        return prices.last_trade_price(sym)
    except Exception as exc:
        log.debug("pankaj_alerts price fetch failed for %s: %s", sym, exc)
        return None


def check_pankaj_alerts(
    *,
    dry_run: bool = False,
    price_fn: Optional[Callable[[str], Optional[float]]] = None,
    now=None,
) -> dict:
    """Fire Pankaj-level alerts for newly-qualifying prices. ``dry_run`` reports
    what WOULD fire without sending. ``price_fn``/``now`` are injectable for
    tests (default to live price + real ET clock)."""
    from . import pankaj_picks, notify

    coll = _coll()
    now = now or _now_et()
    d = _et_date(now)
    now_hm = now.strftime("%H:%M")
    owner = _owner_email()
    get_price = price_fn or _live_price

    fired: list[str] = []
    skipped: list[str] = []
    would: list[str] = []

    for pick in pankaj_picks.load_picks():
        sym = pick["symbol"]
        price = get_price(sym)
        for ev in pankaj_picks.alert_events(pick, price, now_hm):
            key = f"{sym}:{ev['setup_id']}:{ev['event']}:{d}"
            if _already(coll, key):
                skipped.append(key)
                continue
            would.append(f"{ev['event']}:{sym}")
            if dry_run:
                continue
            ok = notify.send_alert(
                title=f"{ev['emoji']} {ev['title']}",
                body=ev["body"],
                url="/pankaj",
                kind="pankaj_alert",
                ticker=sym,
                user_email=owner,
            )
            if ok:
                _mark(coll, key)
                fired.append(key)
            else:
                skipped.append(key + ":send_failed")

    log.info("pankaj_alerts: fired=%d skipped=%d%s", len(fired), len(skipped),
             f" would={would}" if dry_run else "")
    return {"fired": fired, "skipped": skipped, "would_fire": would,
            "checked_at": int(time.time()), "dry_run": dry_run}
