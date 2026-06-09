"""Intraday-momentum regime gate — Gao, Han, Li & Zhou (2018), 'Market Intraday
Momentum', Journal of Financial Economics 129(2):394-414.

The strongest-evidenced finding in the research dossier (peer-reviewed, out-of-
sample, robust to costs): the SIGN of the market's first-half-hour return
predicts the sign of the last-half-hour return. We use it ONLY as a directional
REGIME gate for the single-name detectors — NOT as a tradeable magnitude on a
single stock (R^2 is ~1-2%; the edge is an index-timing effect). Strongest on
high-volatility / high-volume / macro-news days.

  r1 = SPY price at 10:00 ET / prior RTH close - 1   (includes the overnight gap)
  r1 > 0  → long_bias    r1 < 0 → short_bias    (flat → stand_aside)

Before 10:00 ET the first-30-min window isn't complete → 'pending'.
"""
from __future__ import annotations

import logging
from datetime import datetime, time as dtime, timedelta, timezone
from typing import Optional

log = logging.getLogger("scalping.regime")

REGIME_SYMBOL = "SPY"
FLAT_BAND_PCT = 0.05          # |r1| < 0.05% → too flat to take a side


def _now_et() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        # Container TZ is America/New_York — local time IS ET and stays
        # DST-correct (fixed UTC-5 was wrong half the year; review fix 2026-06-09).
        return datetime.now().astimezone()


def _spy_first30_return(now_et: Optional[datetime] = None) -> Optional[dict]:
    """r1 = SPY 10:00 ET price / prior RTH close - 1, in %. None if not ready."""
    from daytrading import data as dt_data
    n = now_et or _now_et()
    today = n.date()

    df_today = dt_data.load_intraday(REGIME_SYMBOL, today, force=True,
                                     include_premarket=False)
    if df_today is None or df_today.empty:
        return None
    rth = df_today[df_today["session"] == "rth"]
    if rth.empty:
        return None
    et_idx = rth.index.tz_localize("UTC").tz_convert("America/New_York")
    # price at/just after 10:00 ET (the close of the first 30 min)
    cutoff = dtime(10, 0)
    at_or_after = [ts for ts, et in zip(rth.index, et_idx) if et.time() >= cutoff]
    if not at_or_after:
        return None                                    # before 10:00 ET → pending
    r1_close = float(rth.loc[at_or_after[0], "close"])

    # prior RTH close — last RTH bar of the previous trading day
    prev_close = None
    for back in range(1, 6):
        d = today - timedelta(days=back)
        if d.weekday() >= 5:
            continue
        pdf = dt_data.load_intraday(REGIME_SYMBOL, d, include_premarket=False)
        if pdf is not None and not pdf.empty:
            prth = pdf[pdf["session"] == "rth"]
            if not prth.empty:
                prev_close = float(prth.iloc[-1]["close"])
                break
    if not prev_close:
        return None
    r1 = (r1_close / prev_close - 1.0) * 100.0
    return {"r1_pct": round(r1, 3), "spy_1000": round(r1_close, 2),
            "prev_close": round(prev_close, 2)}


def intraday_regime(now_et: Optional[datetime] = None) -> dict:
    """Directional regime for the single-name detectors. Bias ∈
    {long_bias, short_bias, stand_aside, pending}."""
    n = now_et or _now_et()
    base = {
        "symbol": REGIME_SYMBOL,
        "as_of_et": n.strftime("%Y-%m-%d %H:%M ET"),
        "source": "Gao, Han, Li & Zhou (2018), JFE 129(2):394-414 — Market Intraday Momentum",
        "note": ("Direction gate only — an index-timing effect (R²~1-2%), not a "
                 "single-name magnitude. Strongest on high-vol / macro-news days."),
    }
    # Before 10:00 ET the signal isn't formed yet.
    if n.time() < dtime(10, 0):
        return {**base, "bias": "pending", "r1_pct": None,
                "label": "Forming — first 30-min window not complete"}
    r = _spy_first30_return(n)
    if not r:
        return {**base, "bias": "pending", "r1_pct": None,
                "label": "No data yet"}
    r1 = r["r1_pct"]
    if abs(r1) < FLAT_BAND_PCT:
        bias, label = "stand_aside", f"Flat open (SPY r₁ {r1:+.2f}%) — no directional edge"
    elif r1 > 0:
        bias, label = "long_bias", f"SPY up {r1:+.2f}% in the first 30 min → long bias into the close"
    else:
        bias, label = "short_bias", f"SPY down {r1:+.2f}% in the first 30 min → short bias into the close"
    return {**base, "bias": bias, "label": label, **r}
