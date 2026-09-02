"""Promo-circuit LIVE — real-time % on every tagged name + movers alerts.

Ajay 2026-09-02: "Give me a real time page.. with percentage and alerting
system ... just give me alerts from the topstock alerts only.. I need the
pre market alerts as well. After hours alerts."

Reads the promo board already in Mongo (never rebuilds it), prices every
SEEDING/RAN/DUMPED ticker off one Massive bulk snapshot (extended-hours
last trade), and pushes a ``promo_alert`` when a roster-tagged name moves
>= PROMO_MOVE_PCT vs the prior close — once per symbol per direction per
day, pre-market / regular / after-hours, off the 5-minute cron.
Reminder printed on every alert: the tag IS the promotion.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("catalysts.promo_live")

PROMO_MOVE_PCT = 8.0
# Ajay 2026-09-02: "just give me alerts from the topstock alerts only". Alerts
# fire ONLY on names carrying a tag from these handles; the live table still
# prices the whole board. User-editable; empty set = every roster handle.
PROMO_ALERT_HANDLES: frozenset = frozenset({"topstockalerts"})
LIVE_REFRESH_SEC = 30
_TTL = 20.0
_cache: dict = {"at": 0.0, "payload": None}
_lock = threading.Lock()


def _to_ms(ts: float) -> float:
    """Massive stamps trades in NANOSECONDS (19 digits) despite the field
    name; the snapshot's day bars use ms. Normalise by magnitude."""
    ts = float(ts)
    if ts > 1e15:
        return ts / 1e6
    if ts > 1e11:
        return ts
    return ts * 1000.0


def session_from_ts(ts_ms: Optional[float], now=None) -> str:
    """premarket | rth | afterhours | closed from a last-trade epoch-ms.
    A print older than 6h is not a live session (weekend/holiday tape)."""
    if not ts_ms:
        return "closed"
    try:
        import pandas as pd
        from daytrading.data import _classify_session
        ts = pd.Timestamp(int(_to_ms(ts_ms)), unit="ms", tz="UTC")
        ref = now if now is not None else pd.Timestamp.now(tz="UTC")
        if (ref - ts).total_seconds() > 6 * 3600:
            return "closed"          # a stale print is not a live session
        return _classify_session(ts)
    except Exception as exc:                                # pragma: no cover
        log.debug("promo_live: session classify failed: %s", exc)
        return "closed"


def _trading_day_et(now: Optional[datetime] = None) -> str:
    """Dedupe day in ET — a 19:02 ET after-hours mover in winter is already
    tomorrow in UTC (double alert tonight, suppressed alert tomorrow)."""
    now = now or datetime.now(timezone.utc)
    return now.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def is_alertable(handles: list) -> bool:
    return (not PROMO_ALERT_HANDLES) or any(h in PROMO_ALERT_HANDLES for h in handles)


def alert_gate(day_pct: Optional[float], threshold: float = PROMO_MOVE_PCT) -> Optional[str]:
    """Pure: 'up' | 'down' | None."""
    if day_pct is None:
        return None
    if day_pct >= threshold:
        return "up"
    if day_pct <= -threshold:
        return "down"
    return None


def _board_rows() -> list[dict]:
    from catalysts.promo_circuit import _coll
    cache = _coll("promo_circuit_cache")
    if cache is None:
        return []
    try:
        doc = cache.find_one({"_id": "latest"}) or {}
        rows = (doc.get("payload") or {}).get("rows") or []
        return [r for r in rows if r.get("status") in ("SEEDING", "RAN", "DUMPED")]
    except Exception as exc:
        log.warning("promo_live: board read failed: %s", exc)
        return []


def live_rows(force: bool = False) -> dict:
    with _lock:
        if not force and _cache["payload"] and time.time() - _cache["at"] < _TTL:
            return _cache["payload"]
    rows = _board_rows()
    syms = [r["ticker"] for r in rows]
    quotes: dict = {}
    if syms:
        try:
            from sepa import prices
            quotes = prices.bulk_live_prices(syms) or {}
        except Exception as exc:
            log.warning("promo_live: bulk prices failed: %s", exc)
    try:
        from supply_demand import timeframes as tf_mod
        st = tf_mod.live_state()
    except Exception:                                       # pragma: no cover
        st = {"state": "closed", "refresh_sec": 0, "as_of": None}
    out = []
    for r in rows:
        q = quotes.get(r["ticker"]) or {}
        last = q.get("last_trade_price") or q.get("price")
        prev = q.get("prev_day_close")
        rth_close = q.get("price") or None      # Massive day.c: today's regular close, 0 pre-open
        day_pct = (round((float(last) / float(prev) - 1) * 100, 2)
                   if last and prev else None)
        # After the bell the move that matters is vs TODAY's close, not
        # yesterday's — an AH dump after an RTH run still reads +% on day_pct.
        ah_pct = (round((float(last) / float(rth_close) - 1) * 100, 2)
                  if (st["state"] == "afterhours" and last and rth_close) else None)
        handles = [a["handle"] for a in (r.get("accounts") or [])]
        base = r.get("base_close")
        out.append({
            "ticker": r["ticker"], "status": r["status"], "best_tier": r.get("best_tier"),
            "accounts": handles[:3], "alertable": is_alertable(handles),
            "days_since_last_tag": r.get("days_since_last_tag"),
            "last": float(last) if last else None, "prev_close": float(prev) if prev else None,
            "rth_close": float(rth_close) if rth_close else None,
            "day_pct": day_pct, "ah_pct": ah_pct,
            "session": session_from_ts(q.get("last_trade_ts_ms")),
            "pct_since_tag": r.get("pct_since_tag"),
            # LIVE since-tag: the last print vs the same base the board uses
            "pct_since_tag_live": (round((float(last) / float(base) - 1) * 100, 1)
                                   if (last and base) else None),
            "first_tagged_at": r.get("first_tagged_at"),
            "last_tagged_at": r.get("last_tagged_at"),
            "edgar": r.get("edgar"),
        })
    out.sort(key=lambda r: (r["day_pct"] is None, -(r["day_pct"] or 0)))
    payload = {
        "as_of": datetime.now(timezone.utc).isoformat(), "rows": out, "n": len(out),
        "live": {"state": st["state"], "refresh_sec": LIVE_REFRESH_SEC if st["refresh_sec"] else 0,
                 "as_of": st.get("as_of")},
        "alert_threshold_pct": PROMO_MOVE_PCT,
        "alert_handles": sorted(PROMO_ALERT_HANDLES),
        "method_note": ("Live prints from the Massive snapshot incl. pre/post market; "
                        "% is vs the prior regular close (after the bell, also vs "
                        "today's close). Alerts: |move| ≥ "
                        f"{PROMO_MOVE_PCT:.0f}% on a name tagged by "
                        + (", ".join("@" + h for h in sorted(PROMO_ALERT_HANDLES)) or "any roster account")
                        + ", once per direction per trading day. The tag is the "
                        "promotion — this is a do-not-chase radar."),
    }
    with _lock:
        _cache.update(at=time.time(), payload=payload)
    return payload


def check_alerts(owner: Optional[str] = None) -> dict:
    from portfolio.alerts import _resolve_owner
    from push import sender
    from catalysts.promo_circuit import _coll
    owner = (owner or _resolve_owner()).lower()
    payload = live_rows(force=True)
    if payload["live"]["state"] == "closed":
        return {"ok": True, "skipped": "tape closed", "pushed": 0}
    coll = _coll("promo_alerts")
    day = _trading_day_et()
    state = payload["live"]["state"]
    tag = {"premarket": "PRE", "afterhours": "AH", "rth": "RTH"}.get(state, "")
    pushed, fired = 0, []
    for r in payload["rows"]:
        if not r.get("alertable") or r.get("session") == "closed":
            continue
        # After the bell: the AH move vs today's close is the signal; before
        # and during: the move vs the prior close.
        if state == "afterhours":
            d = alert_gate(r.get("ah_pct"))
            if not d:
                continue
            key = f"{r['ticker']}:{day}:ah:{d}"
            move = f"{r['ah_pct']:+.1f}% vs close (day {r['day_pct']:+.1f}%)" if r.get("day_pct") is not None else f"{r['ah_pct']:+.1f}% vs close"
            base_px = r.get("rth_close")
        else:
            d = alert_gate(r.get("day_pct"))
            if not d:
                continue
            key = f"{r['ticker']}:{day}:{d}"
            move = f"{r['day_pct']:+.1f}%"
            base_px = r.get("prev_close")
        if coll is not None:
            try:
                if coll.find_one({"_id": key}):
                    continue
            except Exception as exc:                        # pragma: no cover
                log.warning("promo alert dedupe read failed: %s", exc)
        who = ", ".join("@" + h for h in r["accounts"][:2]) or "the circuit"
        age = r.get("days_since_last_tag")
        msg = {
            "title": f"🎪 {tag} {r['ticker']} {move} — tagged by {who}"
                     + (f" {age:.0f}d ago" if age is not None else ""),
            "body": (f"${r['last']:.2f} vs ${base_px:.2f} · {r['status']} · "
                     "the tag IS the promotion — do not chase"),
            "icon": "/icon.svg",
            "tag": f"promo-{r['ticker'].lower()}",
            "url": "/catalysts?tab=promo", "kind": "promo_alert", "ticker": r["ticker"],
            "data": {"url": "/catalysts?tab=promo", "symbol": r["ticker"], "source": "promo_live"},
        }
        res = sender.send_to_user(owner, msg, kind="promo_alert") or {}
        sent, targets = res.get("sent", 0), res.get("total_targets", 0)
        if sent > 0:
            pushed += 1
        # Terminal outcomes dedupe (delivered, or nobody targeted: muted pref /
        # quiet hours / no device) — else every 5-min run re-logs a feed row.
        if (sent > 0 or targets == 0) and coll is not None:
            try:
                coll.update_one({"_id": key}, {"$set": {
                    "at": datetime.now(timezone.utc), "symbol": r["ticker"],
                    "move": move, "session": state, "sent": sent, "targets": targets}}, upsert=True)
            except Exception as exc:                    # pragma: no cover
                log.warning("promo alert dedupe write failed: %s", exc)
        fired.append({"symbol": r["ticker"], "move": move,
                      "session": state, "sent": sent})
    out = {"ok": True, "pushed": pushed, "fired": fired, "session": payload["live"]["state"]}
    log.info("promo_live: %s", out)
    return out


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    print(json.dumps(check_alerts(), indent=2, default=str))
