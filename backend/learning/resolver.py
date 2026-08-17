"""Hourly resolver — grades observations whose horizon has expired."""
from __future__ import annotations

import logging
from typing import Optional

from learning import observations
from sepa import symbols

log = logging.getLogger("learning.resolver")


def _fetch_actual_price(ticker: str, ts_at_or_after: int) -> Optional[float]:
    """Fetch the close price for ``ticker`` at or just after ``ts_at_or_after``.

    Uses yfinance — same library the rest of the app uses for price data.
    Returns None if the ticker can't be priced (delisted, foreign, etc.).
    """
    try:
        import yfinance as yf
        from datetime import datetime, timezone, timedelta

        # Pull a 5-day window starting from the expiry date — the first
        # available close at or after expiry is what we want.
        start_dt = datetime.fromtimestamp(ts_at_or_after, tz=timezone.utc)
        start = (start_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        end = (start_dt + timedelta(days=7)).strftime("%Y-%m-%d")

        t = symbols.yf_ticker(ticker)
        hist = t.history(start=start, end=end, auto_adjust=False)
        if hist.empty:
            return None

        # Filter to the first row at or after the target time
        target = start_dt.replace(tzinfo=None)
        hist.index = hist.index.tz_localize(None) if hist.index.tz is not None else hist.index
        eligible = hist[hist.index >= target]
        if eligible.empty:
            # Use the last available — the ticker may be too recent
            return float(hist["Close"].iloc[-1])
        return float(eligible["Close"].iloc[0])
    except Exception as exc:
        log.warning("price fetch failed for %s: %s", ticker, exc)
        return None


def resolve_pending(limit: int = 500) -> dict:
    """Find every pending observation past its expires_at, grade and update.

    Returns a small summary so cron logs are useful.
    """
    pending = observations.find_pending(limit=limit)
    if not pending:
        return {"checked": 0, "resolved": 0, "skipped": 0}

    resolved = 0
    skipped = 0
    by_status: dict[str, int] = {}
    for obs in pending:
        if obs.get("baseline_price") is None:
            skipped += 1
            continue
        actual = _fetch_actual_price(obs["ticker"], obs["expires_at"])
        if actual is None:
            skipped += 1
            continue
        status, score, actual_pct = observations.score_outcome(
            direction=obs["direction"],
            predicted_pct=float(obs.get("predicted_pct") or 0.0),
            baseline_price=float(obs["baseline_price"]),
            actual_price=actual,
        )
        observations.update_resolution(
            obs_id=obs["_id"],
            status=status,
            actual_price=actual,
            actual_pct=actual_pct,
            accuracy_score=score,
        )
        resolved += 1
        by_status[status] = by_status.get(status, 0) + 1

    log.info("resolver: %d resolved (%s) %d skipped",
             resolved, by_status, skipped)
    return {"checked": len(pending), "resolved": resolved,
            "skipped": skipped, "by_status": by_status}
