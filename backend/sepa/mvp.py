"""David Ryan's MVP indicator ("ants") — Minervini, *Think & Trade Like a
Champion* (TTLAC), Section 1 (ebook p.33) + Section 9 (p.199, reverse/sell use).

The setup that separated stocks that "continued much higher" (the GOOGL 2004
+625%/40-month example) from the rest, measured over a 15-day window:
  - Momentum : the stock is up 12 of 15 days.
  - Volume   : volume increases 25% or more during the 15-day period.
  - Price    : the stock price is up 20% or more during the 15 days.
(TTLAC §1, ebook p.33 — quoted verbatim in docs/sepa/mvp_methodology.md.)

Interpretation is CONTEXT-dependent and decided by the CALLER, not here
(TTLAC §1 p.34 + §9 p.199):
  - From an early/mid-stage base — or when the 15-day window began near a base
    bottom — the MVP footprint is BULLISH continuation: "in position to be
    bought immediately" even if now a few % past the pivot (§1 p.34).
  - Extended from a LATE-STAGE base it is the SAME pattern read in REVERSE: a
    SELL/exhaustion signal (§9 p.199 — "sell when you have 70 percent more up
    days than down days ... a late-stage exhaustion move versus an early-stage
    breakout move").

PURE module (no I/O, no Mongo, no scanner imports). It returns the raw footprint
plus the window-origin facts the buyability gate needs; the bullish vs bearish
call is made in scanner.py against the base count + climax/extension context.

Page cites trace to backend/books/ttlac.md (Section + ebook page).
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

# ── Book constants (TTLAC §1, ebook p.33) — LOCKED in test_sepa_contracts.py ──
MVP_WINDOW = 15            # "up 12 of 15 days" / "during the 15-day period"
MVP_UP_DAYS_MIN = 12       # "the stock is up 12 out of 15 days"
MVP_PRICE_PCT_MIN = 20.0   # "the stock price is up 20 percent or more"
MVP_VOLUME_PCT_MIN = 25.0  # "the volume increases 25 percent or more"

# ── House values (NOT book numbers — the book is silent on these specifics;
# documented as house choices in docs/sepa/mvp_methodology.md) ───────────────
# "the volume increases 25 percent or more during the 15-day period" gives no
# baseline, so we read it as: average daily volume over the 15-day window vs the
# average over the PRIOR 15 days (volume stepped up as the move began).
# "began near the bottom of a base" (§1 p.34): the window's START close must sit
# within this % of the prior base low to count as off-the-bottom (buy exception).
MVP_BASE_BOTTOM_BAND_PCT = 10.0
# Bars BEFORE the window used to locate the base low (the consolidation the run
# emerged from).
MVP_BASE_LOOKBACK = 50


def compute(df: pd.DataFrame, window: int = MVP_WINDOW) -> Optional[dict]:
    """Compute the MVP footprint over the last `window` trading days.

    Needs window+1 closes (window daily changes); the volume baseline uses the
    prior `window` days when available. Returns None when there isn't enough
    data (never raises)."""
    if df is None or "close" not in df or "volume" not in df:
        return None
    c = df["close"].astype(float).reset_index(drop=True)
    v = df["volume"].astype(float).reset_index(drop=True)
    if len(c) < window + 1:
        return None

    # Momentum — up days over the last `window` daily changes ("12 of 15").
    rets = c.diff().iloc[-window:]
    up_days = int((rets > 0).sum())

    # Price — % change over the window (start = window+1 bars back; window days).
    start_px = float(c.iloc[-(window + 1)])
    end_px = float(c.iloc[-1])
    price_pct = round((end_px / start_px - 1) * 100.0, 2) if start_px > 0 else 0.0

    # Volume — avg daily volume in the window vs the prior `window` days.
    win_vol = float(v.iloc[-window:].mean())
    prior = v.iloc[-(2 * window):-window]
    prior_vol = float(prior.mean()) if len(prior) else 0.0
    volume_pct = round((win_vol / prior_vol - 1) * 100.0, 2) if prior_vol > 0 else 0.0

    has_mvp = bool(up_days >= MVP_UP_DAYS_MIN
                   and price_pct >= MVP_PRICE_PCT_MIN
                   and volume_pct >= MVP_VOLUME_PCT_MIN)

    # Near-base-bottom (§1 p.34): did the 15-day window START near the prior base
    # low? If so the move began inside the consolidation and is buyable even when
    # now extended. Base low = min LOW over MVP_BASE_LOOKBACK bars BEFORE window.
    near_base_bottom = False
    base_low = None
    lo = df["low"].astype(float).reset_index(drop=True) if "low" in df else c
    base_window = lo.iloc[-(window + 1) - MVP_BASE_LOOKBACK:-(window + 1)]
    if len(base_window):
        base_low = float(base_window.min())
        if base_low > 0:
            near_base_bottom = start_px <= base_low * (1 + MVP_BASE_BOTTOM_BAND_PCT / 100.0)

    return {
        "window": window,
        "up_days": up_days,
        "up_days_required": MVP_UP_DAYS_MIN,
        "price_pct": price_pct,
        "volume_pct": volume_pct,
        "has_mvp": has_mvp,
        "window_start_price": round(start_px, 2),
        "base_low": round(base_low, 2) if base_low is not None else None,
        "near_base_bottom": bool(near_base_bottom),
    }
