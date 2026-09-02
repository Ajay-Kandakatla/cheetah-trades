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

log = logging.getLogger("catalysts.promo_live")

PROMO_MOVE_PCT = 8.0
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
    out = []
    for r in rows:
        q = quotes.get(r["ticker"]) or {}
        last = q.get("last_trade_price") or q.get("price")
        prev = q.get("prev_day_close")
        day_pct = (round((float(last) / float(prev) - 1) * 100, 2)
                   if last and prev else None)
        out.append({
            "ticker": r["ticker"], "status": r["status"], "best_tier": r.get("best_tier"),
            "accounts": [a["handle"] for a in (r.get("accounts") or [])][:3],
            "days_since_last_tag": r.get("days_since_last_tag"),
            "last": float(last) if last else None, "prev_close": float(prev) if prev else None,
            "day_pct": day_pct,
            "session": session_from_ts(q.get("last_trade_ts_ms")),
            "pct_since_tag": r.get("pct_since_tag"),
            "edgar": r.get("edgar"),
        })
    out.sort(key=lambda r: (r["day_pct"] is None, -(r["day_pct"] or 0)))
    try:
        from supply_demand import timeframes as tf_mod
        st = tf_mod.live_state()
    except Exception:                                       # pragma: no cover
        st = {"state": "closed", "refresh_sec": 0, "as_of": None}
    payload = {
        "as_of": datetime.now(timezone.utc).isoformat(), "rows": out, "n": len(out),
        "live": {"state": st["state"], "refresh_sec": LIVE_REFRESH_SEC if st["refresh_sec"] else 0,
                 "as_of": st.get("as_of")},
        "alert_threshold_pct": PROMO_MOVE_PCT,
        "method_note": ("Live prints from the Massive snapshot incl. pre/post market; "
                        "% is vs the prior regular close. Alerts: |move| ≥ "
                        f"{PROMO_MOVE_PCT:.0f}% on a roster-tagged name, once per "
                        "direction per day. The tag is the promotion — this is a "
                        "do-not-chase radar."),
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
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pushed, fired = 0, []
    for r in payload["rows"]:
        d = alert_gate(r.get("day_pct"))
        if not d or r.get("session") == "closed":
            continue
        key = f"{r['ticker']}:{day}:{d}"
        if coll is not None:
            try:
                if coll.find_one({"_id": key}):
                    continue
            except Exception as exc:                        # pragma: no cover
                log.warning("promo alert dedupe read failed: %s", exc)
        tag = {"premarket": "PRE", "afterhours": "AH", "rth": "RTH"}.get(r["session"], "")
        who = ", ".join("@" + h for h in r["accounts"][:2]) or "the circuit"
        age = r.get("days_since_last_tag")
        msg = {
            "title": f"🎪 {tag} {r['ticker']} {r['day_pct']:+.1f}% — tagged by {who}"
                     + (f" {age:.0f}d ago" if age is not None else ""),
            "body": (f"${r['last']:.2f} vs close ${r['prev_close']:.2f} · {r['status']} · "
                     "the tag IS the promotion — do not chase"),
            "icon": "/icon.svg",
            "tag": f"promo-{r['ticker'].lower()}",
            "data": {"url": "/catalysts", "symbol": r["ticker"], "source": "promo_live"},
        }
        res = sender.send_to_user(owner, msg, kind="promo_alert")
        if (res or {}).get("sent", 0) > 0:
            pushed += 1
            if coll is not None:
                try:
                    coll.update_one({"_id": key}, {"$set": {
                        "at": datetime.now(timezone.utc), "symbol": r["ticker"],
                        "day_pct": r["day_pct"], "session": r["session"]}}, upsert=True)
                except Exception as exc:                    # pragma: no cover
                    log.warning("promo alert dedupe write failed: %s", exc)
        fired.append({"symbol": r["ticker"], "day_pct": r["day_pct"],
                      "session": r["session"], "sent": (res or {}).get("sent", 0)})
    out = {"ok": True, "pushed": pushed, "fired": fired, "session": payload["live"]["state"]}
    log.info("promo_live: %s", out)
    return out


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    print(json.dumps(check_alerts(), indent=2, default=str))
