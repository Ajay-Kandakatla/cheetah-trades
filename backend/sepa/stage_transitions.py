"""Weinstein stage-transition detector.

Mirrors `sepa.breakouts` but for the SELL side. Watches the candidate
snapshot stream and fires alerts when a ticker rolls down a stage:

  - 2 → 3   "topping" — distribution starting; tighten stops
  - 2 → 4   "cliff"   — stage 2 collapsed straight to decline (rare; high signal)
  - 3 → 4   "decline" — confirmed downtrend; sell longs / short candidate

Stage 1/2/3/4 numbers come from `sepa.stage.classify` (Minervini Ch.4 +
Weinstein Stage Analysis). The geometry is:
  Stage 2: price > 50 > 150 > 200 MA, 200 rising
  Stage 3: 50-day rolled, price < 50 but still > 200×0.9
  Stage 4: price < 50 < 150 < 200 MA, 200 falling

Watchlist tickers fan out under TWO push kinds so users can subscribe to
"all stage breakdowns" or "only my watchlist":
  - stage_breakdown          (universe-wide)
  - watchlist_stage_breakdown (only fires when ticker is on user's list)

Alerts persist in the same `sepa_breakouts` collection used by the volume
breakout detector, so the BreakoutAlertBanner UI picks them up
automatically — no separate plumbing.

Cooldown: 24h per (ticker, kind), same as breakouts.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("sepa.stage_transitions")

ALERT_COOLDOWN_HOURS = 24

# Transitions we alert on. Each tuple maps (prior_stage, current_stage) → alert kind.
# Upgrades (e.g. 4→2 or 1→2) are not alerted here — those are the "new candidate"
# / breakout side, already handled by sepa.breakouts and the SEPA scan flow.
TRANSITIONS: dict[tuple[int, int], str] = {
    (2, 3): "stage_breakdown_2_3",
    (2, 4): "stage_breakdown_2_4",
    (3, 4): "stage_breakdown_3_4",
}

REASON_TEMPLATES = {
    "stage_breakdown_2_3": (
        "Stage 2 → 3 · Topping. 50-day rolled and price lost the 50-day, "
        "still holding 200. Distribution starting — tighten stops."
    ),
    "stage_breakdown_2_4": (
        "Stage 2 → 4 · Cliff. Straight to decline (price < 50 < 150 < 200, "
        "200-day falling). Hard sell signal."
    ),
    "stage_breakdown_3_4": (
        "Stage 3 → 4 · Decline confirmed. Below all major MAs with 200-day "
        "rolling over. Sell longs / short candidate."
    ),
}


_db = None
_disabled = False


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
        # Reuse sepa_breakouts collection so the existing alert UI picks
        # these up automatically — same `kind`/`ts`/`dismissed_at` shape.
        _db.sepa_breakouts.create_index([("ts", DESCENDING)])
        _db.sepa_breakouts.create_index([("ticker", ASCENDING), ("kind", ASCENDING)])
        # Per-ticker stage history — one row per (ticker, stage) so we
        # can detect transitions cheaply.
        _db.sepa_stage_history.create_index([("ticker", ASCENDING)], unique=True)
        return _db
    except Exception as exc:
        log.warning("stage_transitions: Mongo unavailable (%s)", exc)
        _disabled = True
        return None


def _now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def _recent_alert_exists(db, ticker: str, kind: str) -> bool:
    cutoff = _now() - ALERT_COOLDOWN_HOURS * 3600
    return db.sepa_breakouts.find_one({
        "ticker": ticker.upper(),
        "kind": kind,
        "ts": {"$gte": cutoff},
    }) is not None


def _record_alert(db, *, kind: str, ticker: str, reason: str,
                  prior_stage: int, current_stage: int,
                  context: dict, score: Optional[float] = None) -> str:
    """Insert alert into sepa_breakouts (shared with breakouts module) and
    fan out push notifications. Returns the inserted _id as str."""
    doc = {
        "ts": _now(),
        "ts_iso": datetime.now(tz=timezone.utc).isoformat(),
        "ticker": ticker.upper(),
        "kind": kind,
        "reason": reason,
        "score": score,
        "context": {**context, "prior_stage": prior_stage, "current_stage": current_stage},
        "dismissed_at": None,
    }
    res = db.sepa_breakouts.insert_one(doc)
    log.info("stage transition: %s %s · %d→%d", kind, ticker, prior_stage, current_stage)

    # Push fanout — gated by scope (top-5 SEPA + watchlist by default) so the
    # phone only buzzes for tickers the user actually cares about. The Mongo
    # alert record + in-app banner still happen for every transition.
    try:
        from push import scope, sender
        if not scope.allowed_for(ticker):
            log.info("stage push suppressed (out of scope): %s %s", kind, ticker)
            return str(res.inserted_id)
        on_watchlist = db.watchlist.find_one({"ticker": ticker.upper()}) is not None
        last_close = context.get("last_close")
        day_change_pct = context.get("day_change_pct")
        emoji = "⚠️" if current_stage == 3 else "🔻"
        title = f"{emoji} {ticker.upper()}"
        if last_close is not None:
            title += f" · ${last_close:.2f}"
        if day_change_pct is not None:
            title += f" {'+' if day_change_pct >= 0 else ''}{day_change_pct:.1f}%"
        payload = {
            "title": title,
            "body": reason,
            "tag": f"{kind}-{ticker.upper()}",
            "url": f"/sepa/{ticker.upper()}",
            "ticker": ticker.upper(),
            "kind": kind,
        }
        # Always fire under "stage_breakdown" pref (universe-wide).
        sender.send_to_all(payload, kind="stage_breakdown")
        # Watchlist-only listeners get an additional fan-out.
        if on_watchlist:
            sender.send_to_all(payload, kind="watchlist_stage_breakdown")
    except Exception as exc:
        log.warning("stage_transitions push failed for %s: %s", ticker, exc)

    return str(res.inserted_id)


def detect_all() -> dict:
    """Diff today's scan stages vs the last-seen stage per ticker; alert
    on the configured transitions. Called from the existing breakouts cron."""
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db unavailable", "alerts": 0}

    latest_run = db.scan_runs.find_one({}, sort=[("generated_at", -1)])
    if not latest_run:
        return {"ok": True, "alerts": 0, "reason": "no scans yet"}

    cands = list(db.candidate_snapshots.find(
        {"scan_run_id": latest_run["_id"]},
        {"symbol": 1, "stage": 1, "rating": 1, "score": 1, "rs_rank": 1,
         "last_close": 1, "day_change_pct": 1, "name": 1, "trade_plan": 1,
         "entry_setup": 1, "pioneer_themes": 1, "date_et": 1},
    ))

    fired = 0
    skipped_cooldown = 0
    new_seen = 0
    for c in cands:
        ticker = (c.get("symbol") or "").upper()
        if not ticker:
            continue
        # `stage` may be a plain int (current candidate_snapshots schema) or
        # a dict {stage, label, dist_200_pct, ...} (live-scan in-memory shape).
        # Handle both so historical rows and fresh writes both work.
        raw_stage = c.get("stage")
        if isinstance(raw_stage, dict):
            stage_doc = raw_stage
            cur = stage_doc.get("stage")
        else:
            cur = raw_stage
            stage_doc = {
                "stage": cur,
                "label": c.get("stage_label"),
                "dist_200_pct": c.get("dist_200_pct"),
            }
        if cur not in (1, 2, 3, 4):
            continue

        prior_doc = db.sepa_stage_history.find_one({"ticker": ticker})
        prior = (prior_doc or {}).get("stage")

        if prior is None:
            new_seen += 1
        elif prior != cur and (prior, cur) in TRANSITIONS:
            kind = TRANSITIONS[(prior, cur)]
            if _recent_alert_exists(db, ticker, kind):
                skipped_cooldown += 1
            else:
                ctx = {
                    "name": c.get("name"),
                    "score": c.get("score"),
                    "rating": c.get("rating"),
                    "rs_rank": c.get("rs_rank"),
                    "stage_label": stage_doc.get("label"),
                    "dist_200_pct": stage_doc.get("dist_200_pct"),
                    "last_close": c.get("last_close"),
                    "day_change_pct": c.get("day_change_pct"),
                    "trade_plan": c.get("trade_plan"),
                    "entry_setup": c.get("entry_setup"),
                    "pioneer_themes": c.get("pioneer_themes") or [],
                    "scan_date": c.get("date_et"),
                }
                _record_alert(
                    db, kind=kind, ticker=ticker,
                    reason=REASON_TEMPLATES[kind],
                    prior_stage=prior, current_stage=cur,
                    context=ctx, score=c.get("score"),
                )
                fired += 1

        # Always update the last-known stage so the next run sees the diff.
        db.sepa_stage_history.update_one(
            {"ticker": ticker},
            {"$set": {
                "ticker": ticker,
                "stage": cur,
                "stage_label": stage_doc.get("label"),
                "last_seen_ts": _now(),
                "last_close": c.get("last_close"),
            }},
            upsert=True,
        )

    log.info("stage_transitions: fired=%d cooldown_skipped=%d first_seen=%d "
             "from %d candidate_snapshots", fired, skipped_cooldown, new_seen, len(cands))
    return {
        "ok": True,
        "alerts": fired,
        "cooldown_skipped": skipped_cooldown,
        "first_seen": new_seen,
        "kind": "stage_breakdown",
    }
