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

        # Real-time price for the stop comparison; fall back to daily close.
        live = prices.last_trade_price(sym)
        last = float(live) if live is not None else float(df["close"].iloc[-1])
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
        # Route position alerts to the ticker's SEPA detail page on tap.
        title_emoji = "🛑" if kind in ("STOP_HIT", "STOP_OUT") else "🎯"
        if notify.send_alert(
            title=f"{title_emoji} {kind}: {sym} @ {last:.2f}",
            body=body,
            url=f"/sepa/{sym}",
            kind="position_alert",
            ticker=sym,
        ):
            _mark_fired(coll, key)
            fired.append(key)
        else:
            skipped.append(key + ":send_failed")

    log.info("alerts: fired=%s skipped=%s", fired, skipped)
    return {"fired": fired, "skipped": skipped, "checked_at": int(time.time())}


def _topping_watch_symbols() -> set:
    """Names we fire topping (Stage-2 → Stage-3) alerts on: the rank-leaderboard
    set ∪ owner portfolio holdings (Ajay 2026-06-03 — only alert on what he's
    tracking or owns, not the whole Stage-2 universe). Empty set = alert nobody."""
    syms: set = set()
    try:
        from . import leaderboard as lb
        for l in (lb.leaderboard(30, 14) or {}).get("leaders", []):
            if l.get("symbol"):
                syms.add(str(l["symbol"]).upper())
    except Exception as exc:
        log.warning("topping watch: leaderboard load failed: %s", exc)
    try:
        import auth
        from portfolio import store as pstore
        for em in auth.HOUSE_OWNER_EMAILS:
            for h in pstore.list_holdings(em):
                # Holdings store the symbol under "ticker" (not "symbol") — the
                # old "symbol" lookup silently dropped EVERY portfolio name, so
                # owned stocks like ST/DINO never got their topping alerts.
                t = h.get("ticker") or h.get("symbol")
                if t:
                    syms.add(str(t).upper())
    except Exception as exc:
        log.warning("topping watch: portfolio load failed: %s", exc)
    return syms


def check_stage_outs() -> dict:
    """Intraday Stage-2 preservation check.

    For each active Stage-2 SEPA candidate, fetch a live price via Massive
    bulk snapshot and check whether it has fallen:
      - Below MA50 × 0.97  → ⚠️ Stage warning (early sign)
      - Below MA200 × 0.98 → 🚨 Stage-out alert (breaks Stage-2 gate)

    Cooldown: 4h per symbol per alert kind (avoids spam on grinding days).
    Only fires during regular trading hours (9:30–16:00 ET, Mon–Fri).
    """
    import datetime as _dt

    # ── Market-hours guard ───────────────────────────────────────────────
    now_et = _dt.datetime.now(_dt.timezone.utc).astimezone(
        _dt.timezone(offset=_dt.timedelta(hours=-4))  # EDT; -5 for EST
    )
    if now_et.weekday() >= 5:          # Saturday/Sunday
        return {"fired": [], "skipped": [], "reason": "weekend"}
    hour = now_et.hour + now_et.minute / 60
    if not (9.5 <= hour < 16.0):
        return {"fired": [], "skipped": [], "reason": "outside_market_hours"}

    # ── Load Stage-2 SEPA candidates ────────────────────────────────────
    from .scanner import load_latest, LATEST_PATH
    latest = load_latest() or {}
    # Scope to leaderboard ∪ portfolio only (Ajay 2026-06-03).
    watch = _topping_watch_symbols()
    if not watch:
        return {"fired": [], "skipped": [], "reason": "empty_watch_set"}
    candidates = [
        c for c in (latest.get("all_results") or latest.get("candidates") or [])
        if (c.get("stage") or {}).get("stage") == 2
        and str(c.get("symbol", "")).upper() in watch
    ]
    if not candidates:
        return {"fired": [], "skipped": [], "reason": "no_watched_stage2_candidates"}

    # ── Bulk live prices ─────────────────────────────────────────────────
    syms = [c["symbol"] for c in candidates]
    live_map = prices.bulk_live_prices(syms)

    coll = _alert_state_coll()
    fired: list[str] = []
    skipped: list[str] = []
    COOLDOWN = 4 * 3600  # 4h between same alert kind per symbol

    for cand in candidates:
        sym = cand["symbol"]
        live_info = live_map.get(sym)
        if not live_info or live_info.get("price") is None:
            continue
        live = float(live_info["price"])

        # Compute MA50 and MA200 from the cached daily series
        df = prices.load_prices(sym)
        if df is None or len(df) < 50:
            continue

        ma50  = float(df["close"].iloc[-50:].mean()) if len(df) >= 50  else None
        ma200 = float(df["close"].iloc[-200:].mean()) if len(df) >= 200 else None

        kind = None
        if ma200 and live < ma200 * 0.98:
            kind = "STAGE_OUT"
        elif ma50 and live < ma50 * 0.97:
            kind = "MA50_BREACH"

        if kind is None:
            continue

        key = f"{sym}:{kind}"
        if int(time.time()) - _last_fired(coll, key) < COOLDOWN:
            skipped.append(key)
            continue

        change_pct = live_info.get("change_pct") or 0
        if kind == "STAGE_OUT":
            title = f"🚨 Stage-out: {sym} @ {live:.2f}"
            body = (f"{sym} is breaking its Stage-2 MA200 requirement intraday "
                    f"({live:.2f} vs MA200 {ma200:.2f}). "
                    f"Change today: {change_pct:+.1f}%. Review position size.")
        else:
            title = f"⚠️ MA50 breach: {sym} @ {live:.2f}"
            body = (f"{sym} has dipped 3%+ below MA50 intraday "
                    f"({live:.2f} vs MA50 {ma50:.2f}). "
                    f"Change today: {change_pct:+.1f}%. Watch for stage degradation.")

        if notify.send_alert(
            title=title,
            body=body,
            url=f"/sepa/{sym}",
            kind="stage_out_alert",
            ticker=sym,
        ):
            _mark_fired(coll, key)
            fired.append(key)
        else:
            skipped.append(key + ":send_failed")

    log.info("stage_outs: checked=%d fired=%s skipped=%s", len(candidates), fired, skipped)
    return {"fired": fired, "skipped": skipped, "checked": len(candidates)}
