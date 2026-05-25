"""Daily calibrator — rolls resolved observations into per-source accuracy.

Writes to two collections:

* ``signal_calibration`` — current rolling stats (overwritten each run)
* ``signal_calibration_history`` — append-only daily snapshot so the UI can
  plot accuracy over time.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from learning.observations import _get_db, _eastern_date

log = logging.getLogger("learning.calibrator")

WINDOWS = (7, 30, 90)  # days
ALL_SOURCES_KEY = "ALL"


def _aggregate_window(db, source: Optional[str], window_days: int, end_ts: int) -> dict:
    """Compute accuracy stats for one (source, window) tuple ending at end_ts."""
    cutoff = end_ts - window_days * 86400
    match = {
        "status": {"$in": ["hit", "miss", "partial"]},
        "resolved_at": {"$gte": cutoff, "$lte": end_ts},
    }
    if source is not None:
        match["source"] = source

    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": None,
            "n": {"$sum": 1},
            "hits": {"$sum": {"$cond": [{"$eq": ["$status", "hit"]}, 1, 0]}},
            "partials": {"$sum": {"$cond": [{"$eq": ["$status", "partial"]}, 1, 0]}},
            "misses": {"$sum": {"$cond": [{"$eq": ["$status", "miss"]}, 1, 0]}},
            "avg_score": {"$avg": "$accuracy_score"},
            "score_squares_sum": {"$sum": {"$pow": ["$accuracy_score", 2]}},
        }},
    ]
    res = list(db.signal_observations.aggregate(pipeline))
    if not res:
        return {
            "n": 0, "hits": 0, "partials": 0, "misses": 0,
            "hit_rate": None, "weighted_hit_rate": None,
            "avg_accuracy": None, "brier_score": None,
            "recommended_weight": 1.0,
        }
    r = res[0]
    n = r["n"]
    hit_rate = (r["hits"] / n) if n else None
    # Weighted hit rate — partials count as half a hit
    weighted = (r["hits"] + 0.5 * r["partials"]) / n if n else None
    avg = r.get("avg_score")
    # Recommended weight: floor 0.3, ceiling 1.5; 0.65 hit rate = 1.0x
    if hit_rate is None or n < 5:
        weight = 1.0  # not enough data — keep neutral
    else:
        weight = max(0.3, min(1.5, hit_rate / 0.65))
    return {
        "n": n,
        "hits": r["hits"],
        "partials": r["partials"],
        "misses": r["misses"],
        "hit_rate": hit_rate,
        "weighted_hit_rate": weighted,
        "avg_accuracy": avg,
        "brier_score": None,  # placeholder — needs probabilistic predictions
        "recommended_weight": round(weight, 3),
    }


def aggregate(snapshot: bool = False) -> dict:
    """Recompute current calibration for every (source, window) pair.

    If ``snapshot`` is True, also append a row to ``signal_calibration_history``
    timestamped with today's Eastern date (used by the daily cron).
    """
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db unavailable"}

    end_ts = int(datetime.now(tz=timezone.utc).timestamp())
    today_et = _eastern_date(end_ts)

    sources = db.signal_observations.distinct("source")
    rows_written = 0
    headline_by_window: dict[int, dict] = {}

    for source in [None, *sources]:  # None = ALL
        key = ALL_SOURCES_KEY if source is None else source
        for w in WINDOWS:
            stats = _aggregate_window(db, source, w, end_ts)
            doc = {
                "source": key,
                "window_days": w,
                "updated_at": end_ts,
                **stats,
            }
            db.signal_calibration.update_one(
                {"source": key, "window_days": w},
                {"$set": doc},
                upsert=True,
            )
            rows_written += 1
            if snapshot:
                hist_doc = {
                    "date_et": today_et,
                    "source": key,
                    "window_days": w,
                    "ts": end_ts,
                    **stats,
                }
                db.signal_calibration_history.update_one(
                    {"date_et": today_et, "source": key, "window_days": w},
                    {"$set": hist_doc},
                    upsert=True,
                )
            if source is None:
                headline_by_window[w] = stats

    log.info("calibrator: wrote %d rows; ALL/30d hit_rate=%s n=%s",
             rows_written,
             headline_by_window.get(30, {}).get("hit_rate"),
             headline_by_window.get(30, {}).get("n"))
    return {"ok": True, "rows": rows_written, "headline": headline_by_window}


def backfill_history(start_date: str, end_date: str) -> int:
    """Synthesize a daily history row for every date in [start_date, end_date].

    For each date D, computes the rolling-window stats *as if* D were today.
    Used after the SEPA backfill so the accuracy timeline isn't a single point.
    """
    db = _get_db()
    if db is None:
        return 0
    start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if end < start:
        return 0

    sources = db.signal_observations.distinct("source")
    written = 0
    cur = start
    while cur <= end:
        # Use end-of-day Eastern (close enough — pin to 21:00 UTC)
        end_ts = int(cur.replace(hour=21).timestamp())
        date_et = cur.strftime("%Y-%m-%d")
        for source in [None, *sources]:
            key = ALL_SOURCES_KEY if source is None else source
            for w in WINDOWS:
                stats = _aggregate_window(db, source, w, end_ts)
                if stats["n"] == 0:
                    continue  # don't write empty rows
                hist_doc = {
                    "date_et": date_et,
                    "source": key,
                    "window_days": w,
                    "ts": end_ts,
                    **stats,
                }
                db.signal_calibration_history.update_one(
                    {"date_et": date_et, "source": key, "window_days": w},
                    {"$set": hist_doc},
                    upsert=True,
                )
                written += 1
        cur += timedelta(days=1)
    log.info("history backfill: wrote %d rows for %s..%s", written, start_date, end_date)
    return written
