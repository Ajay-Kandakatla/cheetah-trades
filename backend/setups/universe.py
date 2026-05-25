"""Shared helper: get the symbol universe for the three scanners.

The three setup scanners (PEG / ORB / Inside-Day) all need the same input:
"the latest SEPA candidate list." Centralizing the lookup here keeps the
data plumbing in one place and lets us tune the universe (top-N by score,
include WATCH-rated names, etc.) without touching the scanners.

Today's policy:
  - Pull the most recent SEPA scan run from Mongo via sepa.history.
  - Keep candidates rated STRONG_BUY / BUY / WATCH.
  - Sort by score DESC, take top N (configurable per scanner).
  - Skip if the SEPA scan is more than 36 hours stale (means cron is
    broken — better to no-op the setups than scan a stale universe).

If Mongo is unreachable, return an empty list. The scanner logs the
no-op so the operator notices.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

log = logging.getLogger("setups.universe")


_STALE_HOURS = 36


def get_sepa_candidates(top_n: int = 30) -> list[dict]:
    """Return up to top_n recent SEPA candidates sorted by score desc.

    Each entry includes: symbol, score, rating, rs_rank, last_close,
    day_change_pct, volume.
    """
    try:
        from sepa import history
        runs = history.get_recent_runs(limit=1)
    except Exception as exc:
        log.warning("get_sepa_candidates: history fetch failed: %s", exc)
        return []
    if not runs:
        log.info("get_sepa_candidates: no scan runs in history")
        return []
    run = runs[0]
    gen = run.get("generated_at") or 0
    if gen and (time.time() - gen) > _STALE_HOURS * 3600:
        log.warning(
            "get_sepa_candidates: latest scan is %.1fh stale; skipping",
            (time.time() - gen) / 3600,
        )
        return []
    date_et = run.get("date_et")
    if not date_et:
        return []
    try:
        scan = history.get_scan_by_date(date_et)
    except Exception as exc:
        log.warning("get_sepa_candidates: scan-by-date failed: %s", exc)
        return []
    if not scan:
        return []
    rows = scan.get("candidates") or []
    # Fallback: if there are no VCP-confirmed candidates today, use the
    # broader pool of analyzed names filtered by rating. The setup scanners
    # look for patterns OTHER than VCP (Bull Flag, HTF, Episodic Pivot, etc.),
    # so they should still get to scan BUY/WATCH/STRONG_BUY rated names even
    # when the strict is_candidate gate is empty.
    if not rows:
        rows = scan.get("all_results") or []
    # Only quality ratings — PEG/ORB/Inside-Day all need a name that's
    # already passed the SEPA filter, otherwise we're trading garbage on
    # a tactical setup.
    rows = [r for r in rows if r.get("rating") in ("STRONG_BUY", "BUY", "WATCH")]
    rows.sort(key=lambda r: (r.get("score") or 0), reverse=True)
    return rows[:top_n]


def is_bull_regime() -> Optional[bool]:
    """Return True if the market regime is bullish, False if bearish,
    None if we can't determine (treat as 'cautious — go ahead').

    The user explicitly chose to sit out bear markets. The scanners
    short-circuit when this returns False — they still run but produce
    zero setups. The result of `False` is intentional: a clear signal
    on the dashboard that "no setups today because regime is bearish",
    not a silent empty list.
    """
    try:
        from sepa.market_regime import classify_regime
    except Exception:
        return None
    try:
        r = classify_regime()
        if not isinstance(r, dict):
            return None
        label = (r.get("label") or "").lower()
        safe = r.get("safe_to_long")
        if safe is True:
            return True
        if safe is False:
            return False
        # Heuristic fallback if safe_to_long isn't set
        if "bull" in label or "uptrend" in label or "confirmed" in label:
            return True
        if "bear" in label or "downtrend" in label or "correction" in label:
            return False
        return None
    except Exception as exc:
        log.warning("is_bull_regime check failed: %s", exc)
        return None


__all__ = ["get_sepa_candidates", "is_bull_regime"]
