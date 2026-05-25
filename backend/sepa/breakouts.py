"""Breakout + rising-momentum detector for SEPA candidates.

Two signal types are detected and persisted as alerts:

1. ``volume_breakout`` — fresh ``high_vol_breakout`` flag on a candidate
   (volume > 1.5× 50-day average AND close > prior high). Cooldown of 24h
   per ticker so we don't re-alert on the same move.

2. ``rising_momentum`` — the TWLO-style pre-breakout pattern that the
   structural detectors miss:
     - On candidate list (any rating) ≥3 consecutive days
     - RS_rank climbed ≥8 points over the last 5 days
     - Score climbed ≥4 points over the last 5 days
   Designed to catch tickers BEFORE the volume spike, when the
   underlying conditions are improving but no setup pattern has formed.

Alerts are stored in ``sepa_breakouts`` and surface to the frontend
via ``GET /sepa/breakouts``. Each alert has ``dismissed_at`` so the UI
can mark them ack'd.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

log = logging.getLogger("sepa.breakouts")

_db = None
_disabled = False
ALERT_COOLDOWN_HOURS = 24


def _get_db():
    global _db, _disabled
    if _disabled:
        return None
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient, ASCENDING, DESCENDING
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _db = client[os.getenv("MONGO_DB", "cheetah")]
        _db.sepa_breakouts.create_index([("ts", DESCENDING)])
        _db.sepa_breakouts.create_index([("ticker", ASCENDING), ("kind", ASCENDING)])
        _db.sepa_breakouts.create_index([("dismissed_at", ASCENDING)])
        return _db
    except Exception as exc:
        log.warning("breakouts: Mongo unavailable (%s) — disabling", exc)
        _disabled = True
        return None


def _now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def _recent_alert_exists(db, ticker: str, kind: str) -> bool:
    """Cooldown check — was the same kind of alert fired for this ticker
    in the last ALERT_COOLDOWN_HOURS hours?"""
    cutoff = _now() - ALERT_COOLDOWN_HOURS * 3600
    return db.sepa_breakouts.find_one({
        "ticker": ticker.upper(),
        "kind": kind,
        "ts": {"$gte": cutoff},
    }) is not None


def _record_alert(db, *, kind: str, ticker: str, reason: str,
                  context: dict, score: float | None = None):
    """Insert an alert record. Returns the inserted _id as str.

    Push fanout goes through ``push.scope.allowed_for`` — only top-5 SEPA
    candidates + watchlist names buzz the phone by default. The in-app
    banner alert is still persisted regardless so you can browse all
    fired alerts from /sepa, but the phone stays quiet.
    """
    doc = {
        "ts": _now(),
        "ts_iso": datetime.now(tz=timezone.utc).isoformat(),
        "ticker": ticker.upper(),
        "kind": kind,
        "reason": reason,
        "score": score,
        "context": context,
        "dismissed_at": None,
    }
    res = db.sepa_breakouts.insert_one(doc)
    log.info("breakout alert: %s %s · %s", kind, ticker, reason)

    # Push the breakout to every open browser tab via the SSE bus so
    # the BreakoutAlertBanner re-renders immediately instead of waiting
    # for its next 30s poll. Inline import + try/except so a bus
    # failure cannot break the insert.
    try:
        from events import publish as _bus_publish
        _bus_publish("breakout.fired", {
            "id":      str(res.inserted_id),
            "ts":      doc["ts"],
            "ticker":  doc["ticker"],
            "kind":    kind,
            "reason":  reason,
            "score":   score,
            "context": context,
        })
    except Exception as exc:
        log.debug("bus publish breakout.fired failed: %s", exc)

    # Fire push notification — gated by scope (top-5 SEPA + watchlist by default)
    try:
        from push import scope
        if not scope.allowed_for(ticker):
            log.info("push suppressed (out of scope): %s %s", kind, ticker)
        else:
            from push import hooks
            on_watchlist = db.watchlist.find_one({"ticker": ticker.upper()}) is not None
            hooks.notify_breakout(
                kind=kind,
                ticker=ticker.upper(),
                reason=reason,
                score=score,
                last_close=context.get("last_close"),
                day_change_pct=context.get("day_change_pct"),
                on_watchlist=on_watchlist,
            )
    except Exception as exc:
        log.warning("push notification failed: %s", exc)

    return str(res.inserted_id)


def detect_volume_breakouts(limit: int = 50) -> dict:
    """Scan the most recent scan_run's candidates for fresh high-vol breakouts."""
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db unavailable"}

    # Find latest scan run
    latest_run = db.scan_runs.find_one({}, sort=[("generated_at", -1)])
    if not latest_run:
        return {"ok": True, "alerts": 0, "reason": "no scans yet"}

    # Pull all candidates from that run with high_vol_breakout flag
    cands = db.candidate_snapshots.find({
        "scan_run_id": latest_run["_id"],
        "volume.high_vol_breakout": True,
    })

    fired = 0
    for c in cands:
        ticker = c.get("symbol")
        if not ticker:
            continue
        if _recent_alert_exists(db, ticker, "volume_breakout"):
            continue
        ctx = {
            "score": c.get("score"),
            "rating": c.get("rating"),
            "rs_rank": c.get("rs_rank"),
            "stage_label": c.get("stage_label"),
            "last_close": c.get("last_close"),
            "day_change_pct": c.get("day_change_pct"),
            "volume": c.get("volume"),
            "entry_setup": c.get("entry_setup"),
            "pioneer_themes": c.get("pioneer_themes") or [],
            "scan_date": c.get("date_et"),
        }
        vol_x = (c.get("volume") or {}).get("ratio") or (c.get("volume") or {}).get("vol_ratio")
        reason = (
            f"{c.get('rating', 'WATCH')} tier · score {c.get('score'):.0f} · "
            f"high-vol breakout"
            + (f" ({vol_x:.1f}× avg)" if vol_x else "")
            + (f" · {c.get('day_change_pct'):+.1f}% today" if c.get('day_change_pct') is not None else "")
        )
        _record_alert(db, kind="volume_breakout", ticker=ticker,
                      reason=reason, context=ctx, score=c.get("score"))
        fired += 1
        if fired >= limit:
            break

    return {"ok": True, "alerts": fired, "kind": "volume_breakout"}


def detect_rising_momentum(min_days_on_list: int = 3,
                           rs_climb_threshold: int = 8,
                           score_climb_threshold: float = 4.0,
                           lookback_days: int = 5,
                           limit: int = 50) -> dict:
    """The TWLO-style detector. Finds tickers that:
      - Appeared on the candidate list >= min_days_on_list of the last lookback_days
      - Whose RS rank climbed >= rs_climb_threshold over the window
      - Whose score climbed >= score_climb_threshold over the window
    """
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db unavailable"}

    cutoff = _now() - lookback_days * 86400
    pipeline = [
        {"$match": {
            "generated_at": {"$gte": cutoff},
            "rating": {"$in": ["STRONG_BUY", "BUY", "WATCH"]},
        }},
        {"$sort": {"generated_at": 1}},
        {"$group": {
            "_id": "$symbol",
            "days_on_list": {"$addToSet": "$date_et"},
            "first_score": {"$first": "$score"},
            "last_score": {"$last": "$score"},
            "first_rs": {"$first": "$rs_rank"},
            "last_rs": {"$last": "$rs_rank"},
            "last_rating": {"$last": "$rating"},
            "last_close": {"$last": "$last_close"},
            "themes": {"$last": "$pioneer_themes"},
            "stage_label": {"$last": "$stage_label"},
        }},
    ]
    rows = list(db.candidate_snapshots.aggregate(pipeline))

    fired = 0
    for r in rows:
        ticker = r["_id"]
        if not ticker:
            continue
        days = len(r.get("days_on_list") or [])
        first_rs = r.get("first_rs") or 0
        last_rs = r.get("last_rs") or 0
        first_score = r.get("first_score") or 0
        last_score = r.get("last_score") or 0
        rs_delta = last_rs - first_rs
        score_delta = last_score - first_score

        if (days >= min_days_on_list
                and rs_delta >= rs_climb_threshold
                and score_delta >= score_climb_threshold):
            if _recent_alert_exists(db, ticker, "rising_momentum"):
                continue
            ctx = {
                "days_on_list": days,
                "first_score": round(first_score, 1),
                "last_score": round(last_score, 1),
                "score_delta": round(score_delta, 1),
                "first_rs": first_rs,
                "last_rs": last_rs,
                "rs_delta": rs_delta,
                "last_rating": r.get("last_rating"),
                "last_close": r.get("last_close"),
                "stage_label": r.get("stage_label"),
                "pioneer_themes": r.get("themes") or [],
                "lookback_days": lookback_days,
            }
            reason = (
                f"Rising momentum — RS climbed {first_rs} → {last_rs} (+{rs_delta}), "
                f"score {first_score:.0f} → {last_score:.0f} (+{score_delta:.0f}) "
                f"over {days}d. {r.get('last_rating')}-tier sustained — pre-breakout setup."
            )
            _record_alert(db, kind="rising_momentum", ticker=ticker,
                          reason=reason, context=ctx, score=last_score)
            fired += 1
            if fired >= limit:
                break

    return {"ok": True, "alerts": fired, "kind": "rising_momentum"}


def detect_all() -> dict:
    """Run all detectors. Called by the live cron.

    Includes stage-transition detection (stage 2→3, 2→4, 3→4) which uses
    the same `sepa_breakouts` collection + push fanout, so the existing
    cron + UI banner picks them up with no extra wiring.
    """
    a = detect_volume_breakouts()
    b = detect_rising_momentum()
    # Stage breakdowns — sell-side signals (topping / decline). Best-effort
    # so a regression here can't break the breakout side of the cron run.
    c = {"alerts": 0}
    try:
        from sepa import stage_transitions
        c = stage_transitions.detect_all()
    except Exception as exc:
        log.warning("stage_transitions detect_all failed: %s", exc)
    return {"volume_breakouts": a.get("alerts", 0),
            "rising_momentum": b.get("alerts", 0),
            "stage_breakdowns": c.get("alerts", 0)}


def list_active(since_ts: int = 0, limit: int = 50) -> list[dict]:
    """Return all alerts since `since_ts` that haven't been dismissed."""
    db = _get_db()
    if db is None:
        return []
    rows = list(db.sepa_breakouts.find(
        {"ts": {"$gte": since_ts}, "dismissed_at": None},
    ).sort("ts", -1).limit(limit))
    for r in rows:
        r["_id"] = str(r["_id"])
    return rows


def dismiss(alert_id: str) -> bool:
    db = _get_db()
    if db is None:
        return False
    from bson import ObjectId
    try:
        db.sepa_breakouts.update_one(
            {"_id": ObjectId(alert_id)},
            {"$set": {"dismissed_at": _now()}},
        )
        # Other tabs need to drop the alert from their banner too — push
        # the dismissal so they don't keep showing it until the next poll
        # (which they won't have anymore once they switch to SSE).
        try:
            from events import publish as _bus_publish
            _bus_publish("breakout.dismissed", {"id": alert_id})
        except Exception:
            pass
        return True
    except Exception:
        return False


def dismiss_all() -> int:
    db = _get_db()
    if db is None:
        return 0
    res = db.sepa_breakouts.update_many(
        {"dismissed_at": None},
        {"$set": {"dismissed_at": _now()}},
    )
    try:
        from events import publish as _bus_publish
        _bus_publish("breakout.dismissed_all", {"n": res.modified_count})
    except Exception:
        pass
    return res.modified_count
