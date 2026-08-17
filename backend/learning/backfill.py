"""One-shot retroactive backfill — grade existing SEPA snapshots.

Pulls every (ticker, date_et) from ``candidate_snapshots`` where the rating is
SEPA-positive (STRONG_BUY/BUY/WATCH), pretends we made an "expect up over 1d"
prediction at that snapshot, fetches the actual close for the next trading day,
and inserts a resolved observation in ``signal_observations``.

After the backfill, the calibrator is run with ``backfill_history()`` so the
accuracy timeline has a row per past day, not just a single point at "today".
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from learning import observations, calibrator
from sepa import symbols

log = logging.getLogger("learning.backfill")

POSITIVE_TIERS = {"STRONG_BUY", "BUY", "WATCH"}


def _fetch_close_window(ticker: str, start_date: str, end_date: str):
    """Pull historical OHLC between two dates (inclusive). Returns {date_str: close}."""
    try:
        import yfinance as yf
        t = symbols.yf_ticker(ticker)
        # Pad each end so the start/end dates are included in yfinance's
        # half-open [start, end) interval.
        s = datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=2)
        e = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=4)
        hist = t.history(start=s.strftime("%Y-%m-%d"),
                         end=e.strftime("%Y-%m-%d"),
                         auto_adjust=False)
        if hist.empty:
            return {}
        out = {}
        for idx, row in hist.iterrows():
            d = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
            out[d] = float(row["Close"])
        return out
    except Exception as exc:
        log.warning("backfill price fetch failed for %s: %s", ticker, exc)
        return {}


def _next_trading_close(prices: dict, target_date: str) -> Optional[float]:
    """Return the first available close on or after target_date+1 day."""
    if not prices:
        return None
    target = datetime.strptime(target_date, "%Y-%m-%d") + timedelta(days=1)
    sorted_dates = sorted(prices.keys())
    for d in sorted_dates:
        if d >= target.strftime("%Y-%m-%d"):
            return prices[d]
    return None


def _entry_close(prices: dict, target_date: str) -> Optional[float]:
    """The close of target_date (or the last available trading day before it)."""
    if not prices:
        return None
    sorted_dates = sorted(prices.keys())
    on_or_before = [d for d in sorted_dates if d <= target_date]
    if not on_or_before:
        return None
    return prices[on_or_before[-1]]


def backfill_sepa(horizon_hours: int = 24, max_tickers: int = 500) -> dict:
    """Insert resolved observations for every SEPA-positive snapshot.

    horizon_hours is the prediction window — 24 means "predict the next-day
    close > entry close". The grade is direction-only (predicted_pct=0).
    """
    db = observations._get_db()
    if db is None:
        return {"ok": False, "reason": "db unavailable"}

    # Gather one observation candidate per (ticker, date_et) where rating is positive.
    # Uses the most recent snapshot per (ticker, date_et) to avoid intraday duplicates.
    pipeline = [
        {"$match": {"rating": {"$in": list(POSITIVE_TIERS)}}},
        {"$sort": {"generated_at": -1}},
        {"$group": {
            "_id": {"ticker": "$symbol", "date_et": "$date_et"},
            "ts": {"$first": "$generated_at"},
            "rating": {"$first": "$rating"},
            "score": {"$first": "$score"},
            "rs_rank": {"$first": "$rs_rank"},
        }},
        {"$sort": {"_id.date_et": 1}},
    ]
    rows = list(db.candidate_snapshots.aggregate(pipeline))
    log.info("backfill: %d (ticker,date) pairs to process", len(rows))

    if not rows:
        return {"ok": True, "n": 0, "reason": "no SEPA history found"}

    # Group by ticker so we can batch the yfinance calls
    by_ticker: dict[str, list] = {}
    for r in rows:
        by_ticker.setdefault(r["_id"]["ticker"], []).append(r)

    inserted = 0
    skipped_price = 0
    skipped_dup = 0
    by_status: dict[str, int] = {}

    for i, (ticker, entries) in enumerate(by_ticker.items()):
        if i >= max_tickers:
            log.info("backfill: hit max_tickers cap of %d", max_tickers)
            break
        if not ticker or "." in ticker:
            # Skip foreign / non-standard tickers — yfinance struggles
            continue

        date_min = min(e["_id"]["date_et"] for e in entries)
        date_max = max(e["_id"]["date_et"] for e in entries)
        prices = _fetch_close_window(ticker, date_min, date_max)
        if not prices:
            skipped_price += len(entries)
            continue

        for e in entries:
            d = e["_id"]["date_et"]
            ts = int(e["ts"])
            rating = e["rating"]
            value = float(e.get("score") or 0.0)

            entry_px = _entry_close(prices, d)
            actual_px = _next_trading_close(prices, d)
            if entry_px is None or actual_px is None:
                skipped_price += 1
                continue

            # Idempotency — don't re-insert the same (source,ticker,ts)
            source = f"sepa_tier_{rating}"
            existing = db.signal_observations.find_one({
                "source": source, "ticker": ticker, "ts": ts,
            })
            if existing is not None:
                skipped_dup += 1
                continue

            status, score, actual_pct = observations.score_outcome(
                direction="up",
                predicted_pct=0.0,
                baseline_price=entry_px,
                actual_price=actual_px,
            )
            doc = {
                "source": source,
                "ticker": ticker,
                "ts": ts,
                "ts_iso": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
                "date_et": d,
                "direction": "up",
                "value": value,
                "baseline_price": entry_px,
                "horizon_hours": horizon_hours,
                "expires_at": ts + horizon_hours * 3600,
                "predicted_pct": 0.0,
                "prediction_id": None,
                "status": status,
                "resolved_at": ts + horizon_hours * 3600,  # synthetic: backfill fills this in
                "actual_price": actual_px,
                "actual_pct": actual_pct,
                "accuracy_score": score,
                "backfilled": True,
            }
            db.signal_observations.insert_one(doc)
            inserted += 1
            by_status[status] = by_status.get(status, 0) + 1

    # Recompute calibration + history snapshots
    calibrator.aggregate(snapshot=False)
    if rows:
        first_date = min(r["_id"]["date_et"] for r in rows)
        last_date = max(r["_id"]["date_et"] for r in rows)
        calibrator.backfill_history(first_date, last_date)

    log.info("backfill done: inserted=%d skipped_price=%d skipped_dup=%d by_status=%s",
             inserted, skipped_price, skipped_dup, by_status)
    return {
        "ok": True,
        "inserted": inserted,
        "skipped_price": skipped_price,
        "skipped_dup": skipped_dup,
        "by_status": by_status,
    }
