"""Mongo-backed observation logger + grading primitives.

A signal observation is one row per (signal source, ticker, prediction time).
It starts pending and gets resolved by ``resolver.resolve_pending()`` once the
horizon expires.

Collections
-----------
signal_observations
  source             "sepa_tier_BUY" | "catalyst_tier_a" | "sentiment_stocktwits" | ...
  ticker             "AAPL"
  ts                 epoch seconds when observed
  date_et            "2026-05-02"
  direction          "up" | "down" | "range"
  value              float — magnitude of the signal (e.g. SEPA score 75.0)
  baseline_price     price at observation time
  horizon_hours      24
  expires_at         ts + horizon_hours*3600
  predicted_pct      expected move pct (default 0 = direction-only prediction)
  status             "pending" | "hit" | "miss" | "partial"
  resolved_at        epoch when graded
  actual_price       price at expires_at
  actual_pct         (actual - baseline) / baseline * 100
  accuracy_score     -1.0..1.0  (1=perfect, 0=neutral, -1=worst)

signal_calibration
  Per-source rolling stats — overwritten by ``calibrator.aggregate()``.

signal_calibration_history
  Per-source daily snapshots — append-only so we can plot accuracy over time.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

log = logging.getLogger("learning.observations")

_client = None
_db = None
_disabled = False
_DB_NAME = os.getenv("MONGO_DB", "cheetah")


def _get_db():
    global _client, _db, _disabled
    if _disabled:
        return None
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient, ASCENDING, DESCENDING
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        _client = MongoClient(url, serverSelectionTimeoutMS=2000)
        _client.admin.command("ping")
        _db = _client[_DB_NAME]
        _db.signal_observations.create_index([("source", ASCENDING), ("ts", DESCENDING)])
        _db.signal_observations.create_index([("ticker", ASCENDING), ("ts", DESCENDING)])
        _db.signal_observations.create_index([("status", ASCENDING), ("expires_at", ASCENDING)])
        _db.signal_calibration.create_index([("source", ASCENDING), ("window_days", ASCENDING)], unique=True)
        _db.signal_calibration_history.create_index([("date_et", ASCENDING), ("source", ASCENDING), ("window_days", ASCENDING)], unique=True)
        log.info("learning: connected to %s/%s", url, _DB_NAME)
        return _db
    except Exception as exc:
        log.warning("learning: Mongo unavailable (%s) — disabling", exc)
        _disabled = True
        return None


def _eastern_date(epoch: int) -> str:
    et = datetime.fromtimestamp(epoch, tz=timezone(timedelta(hours=-5)))
    return et.strftime("%Y-%m-%d")


def record_observation(
    source: str,
    ticker: str,
    ts: int,
    direction: str,                # "up" | "down" | "range"
    value: float = 0.0,
    baseline_price: Optional[float] = None,
    horizon_hours: int = 24,
    predicted_pct: float = 0.0,
    prediction_id: Optional[str] = None,
) -> Optional[str]:
    """Append an observation. Returns the inserted _id as str, or None if disabled."""
    db = _get_db()
    if db is None:
        return None
    try:
        doc = {
            "source": source,
            "ticker": ticker.upper(),
            "ts": int(ts),
            "ts_iso": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
            "date_et": _eastern_date(ts),
            "direction": direction,
            "value": float(value),
            "baseline_price": float(baseline_price) if baseline_price is not None else None,
            "horizon_hours": int(horizon_hours),
            "expires_at": int(ts + horizon_hours * 3600),
            "predicted_pct": float(predicted_pct),
            "prediction_id": prediction_id,
            "status": "pending",
            "resolved_at": None,
            "actual_price": None,
            "actual_pct": None,
            "accuracy_score": None,
        }
        return str(db.signal_observations.insert_one(doc).inserted_id)
    except Exception as exc:
        log.warning("record_observation failed: %s", exc)
        return None


def score_outcome(
    direction: str,
    predicted_pct: float,
    baseline_price: float,
    actual_price: float,
) -> tuple[str, float, float]:
    """Tolerant grading.

    Returns (status, accuracy_score, actual_pct).

    Rules:
      - direction match alone earns ≥ partial credit
      - direction match AND magnitude in [50%, 150%] of predicted = HIT
      - direction match but magnitude wildly off = PARTIAL
      - direction mismatch = MISS
      - "range" predictions hit if abs(actual_pct) < 2%
    """
    actual_pct = (actual_price - baseline_price) / baseline_price * 100.0

    if direction == "range":
        if abs(actual_pct) < 2.0:
            return "hit", 1.0, actual_pct
        if abs(actual_pct) < 5.0:
            return "partial", 0.4, actual_pct
        return "miss", -0.5, actual_pct

    pred_dir = "up" if direction == "up" else "down"
    actual_dir = "up" if actual_pct > 0 else ("down" if actual_pct < 0 else "flat")

    # Direction-only predictions (predicted_pct == 0): just check the sign
    if predicted_pct == 0.0:
        if pred_dir == actual_dir:
            # Stronger move = better score
            score = min(1.0, abs(actual_pct) / 5.0)  # +5% = perfect, +1% = 0.2
            return "hit" if abs(actual_pct) >= 0.5 else "partial", max(0.2, score), actual_pct
        if actual_dir == "flat":
            return "partial", 0.0, actual_pct
        return "miss", -1.0, actual_pct

    # Magnitude predictions: signed direction matters too
    direction_match = (predicted_pct > 0) == (actual_pct > 0)
    if not direction_match:
        return "miss", -1.0, actual_pct

    if predicted_pct == 0:
        return "partial", 0.0, actual_pct

    ratio = actual_pct / predicted_pct  # 1.0 = exactly hit
    if 0.5 <= ratio <= 1.5:
        return "hit", 1.0, actual_pct
    if ratio > 0:
        # Right direction, wrong magnitude — partial
        score = ratio if ratio < 1 else max(0.0, 2.0 - min(2.0, ratio))
        return "partial", float(max(0.2, score)), actual_pct
    return "miss", -1.0, actual_pct


def find_pending(limit: int = 500) -> list[dict]:
    db = _get_db()
    if db is None:
        return []
    now = int(datetime.now(tz=timezone.utc).timestamp())
    cur = db.signal_observations.find(
        {"status": "pending", "expires_at": {"$lte": now}},
    ).limit(limit)
    return [{**d, "_id": str(d["_id"])} for d in cur]


def update_resolution(
    obs_id: str,
    status: str,
    actual_price: float,
    actual_pct: float,
    accuracy_score: float,
):
    db = _get_db()
    if db is None:
        return
    from bson import ObjectId
    db.signal_observations.update_one(
        {"_id": ObjectId(obs_id)},
        {"$set": {
            "status": status,
            "actual_price": float(actual_price),
            "actual_pct": float(actual_pct),
            "accuracy_score": float(accuracy_score),
            "resolved_at": int(datetime.now(tz=timezone.utc).timestamp()),
        }},
    )
