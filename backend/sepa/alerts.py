"""Intraday position alerts — runs every few minutes during market hours.

For each watchlist position, fetch a fresh quote and fire a WhatsApp alert if:
  - last ≤ stop                       → STOP_HIT
  - sell_signals.evaluate.action != HOLD → action (e.g. break of 50DMA, climax)
  - last ≥ entry × 1.20 and not yet at +20% → CONSIDER_RAISING_STOP

Idempotency: per-symbol last-alert timestamp is kept in Mongo `position_alerts`
collection (or in-memory fallback). We won't repeat the same alert kind for the
same symbol within ALERT_COOLDOWN_SEC.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

from . import prices, sell_signals, notify
from .scanner import load_watchlist

log = logging.getLogger("sepa.alerts")

ALERT_COOLDOWN_SEC = 6 * 3600  # don't repeat the same alert kind within 6h
_mem_state: dict[str, int] = {}


def _alert_state_coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        return client[db_name].position_alerts
    except Exception:
        return None


def _last_fired(coll, key: str) -> int:
    if coll is None:
        return _mem_state.get(key, 0)
    doc = coll.find_one({"_id": key})
    return int((doc or {}).get("ts") or 0)


def _mark_fired(coll, key: str) -> None:
    ts = int(time.time())
    if coll is None:
        _mem_state[key] = ts
        return
    coll.update_one({"_id": key}, {"$set": {"ts": ts}}, upsert=True)


def check_positions() -> dict:
    coll = _alert_state_coll()
    fired: list[str] = []
    skipped: list[str] = []

    for pos in load_watchlist():
        sym = pos["symbol"]
        df = prices.load_prices(sym)
        if df is None or df.empty:
            continue

        last = float(df["close"].iloc[-1])
        entry = float(pos.get("entry") or last)
        stop = float(pos.get("stop") or 0)
        shares = float(pos.get("shares") or 0)
        sells = sell_signals.evaluate(df, entry_price=entry, stop_price=stop)
        action = (sells or {}).get("action") or "HOLD"

        kind: Optional[str] = None
        if stop and last <= stop:
            kind = "STOP_HIT"
        elif action != "HOLD":
            kind = action
        elif entry and last >= entry * 1.20:
            kind = "CONSIDER_RAISING_STOP"

        if kind is None:
            continue

        key = f"{sym}:{kind}"
        if int(time.time()) - _last_fired(coll, key) < ALERT_COOLDOWN_SEC:
            skipped.append(key)
            continue

        pnl_pct = (last / entry - 1) * 100 if entry else 0
        body = notify.format_position_alert({
            "symbol": sym, "last_price": round(last, 4),
            "entry": entry, "stop": stop, "shares": shares,
            "pnl_pct": round(pnl_pct, 2), "action": kind,
        })
        if notify.send_whatsapp(body):
            _mark_fired(coll, key)
            fired.append(key)
        else:
            skipped.append(key + ":send_failed")

    log.info("alerts: fired=%s skipped=%s", fired, skipped)
    return {"fired": fired, "skipped": skipped, "checked_at": int(time.time())}
