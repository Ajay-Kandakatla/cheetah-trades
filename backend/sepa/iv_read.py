"""Market IV read — VIX level, day change, 252-day percentile, term structure
and VVIX as ONE small payload for the nav badge next to the Market Gauge
(Ajay 2026-09-06: "Do we have an IV indicator in our pages? can you add that
to our regular used pages as a global indicator? May be beside Market gauge
metric?").

Sources already in the app: `sepa.prices.load_prices` serves ^VIX / ^VIX9D /
^VIX3M / ^VVIX (Massive, yfinance fallback — the same path the Market Gauge's
volatility pillar reads), and the regime cut points are the ones
`sepa.market_regime._stress_score` already uses (15 / 20 / 30). Nothing here
is a book rule; it is a house read of implied volatility. Not advice.

Every tenor is loaded with period="1y": the price cache keys on (symbol,
period) and a shorter period can hand back a weeks-old cached frame (seen
2026-09-06: the 3mo ^VIX3M frame ended 2026-07-17 while 1y was current).

Term structure is aligned on ONE date: the last session where ^VIX closed
and the shorter/longer tenors also have a close (the 9D/3M series sometimes
miss the newest bar), so a ratio never mixes two days.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from typing import Optional

log = logging.getLogger("sepa.iv_read")

# House regime cut points — the SAME levels sepa.market_regime._stress_score
# scores with (15 / 20 / 30). Locked in tests/test_iv_read.py.
CALM_BELOW = 15.0
NORMAL_BELOW = 20.0
ELEVATED_BELOW = 30.0
REGIMES = ("calm", "normal", "elevated", "stress")
LABELS = {"calm": "Calm", "normal": "Normal", "elevated": "Elevated", "stress": "Stress"}
# Term-structure shape: shorter tenor / longer tenor. Under 1 = contango
# (calm carry), over 1 = backwardation (near-term fear). FLAT_BAND keeps a
# hair either side of 1.0 from flipping the label every minute.
FLAT_BAND = 0.02
PCT_WINDOW = 252
TTL_SEC = 180
# The 9D / 3M series can stop updating at the source (seen 2026-09-06: both
# ended 2026-07-17 while ^VIX was current). A term read older than this many
# calendar days behind the VIX close is STALE: ratios and shape are nulled,
# the date stays so the badge can say "term n/a since <date>".
TERM_MAX_LAG_DAYS = 7
DISCLAIMER = ("House read of market implied volatility (CBOE VIX family) — "
              "context for option pricing and risk, not a signal, not advice.")

_LOCK = threading.Lock()
_CACHE = {"at": 0.0, "data": None}


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def classify(vix: Optional[float]) -> Optional[str]:
    v = _f(vix)
    if v is None:
        return None
    if v < CALM_BELOW:
        return "calm"
    if v < NORMAL_BELOW:
        return "normal"
    if v < ELEVATED_BELOW:
        return "elevated"
    return "stress"


def term_shape(ratio: Optional[float]) -> Optional[str]:
    r = _f(ratio)
    if r is None:
        return None
    if r > 1.0 + FLAT_BAND:
        return "backwardation"
    if r < 1.0 - FLAT_BAND:
        return "contango"
    return "flat"


def pct_rank(series, level: float, window: int = PCT_WINDOW) -> Optional[float]:
    """Share of the last `window` closes UNDER `level`, in %. None on a thin
    series (< 20 points) so the badge says 'n/a' instead of a fake rank."""
    vals = [v for v in (_f(x) for x in list(series or [])[-window:]) if v is not None]
    if len(vals) < 20:
        return None
    return round(sum(1 for v in vals if v < level) / len(vals) * 100.0, 1)


def _closes(df):
    """[(iso_date, close)] with NaNs dropped, oldest first."""
    out = []
    if df is None or len(df) == 0 or "close" not in df.columns:
        return out
    for idx, v in zip(df.index, df["close"]):
        c = _f(v)
        if c is None:
            continue
        out.append((str(idx)[:10], c))
    return out


def _load(symbol: str, period: str):
    from sepa.prices import load_prices
    try:
        return load_prices(symbol, period=period)
    except Exception as exc:                       # noqa: BLE001
        log.warning("iv_read: %s unavailable: %s", symbol, exc)
        return None


def _lag_days(newer: str, older: str) -> int:
    from datetime import date
    try:
        return (date.fromisoformat(newer[:10]) - date.fromisoformat(older[:10])).days
    except (TypeError, ValueError):
        return 0


def _one_liner(regime: Optional[str], pct: Optional[float], shape: Optional[str],
               chg: Optional[float]) -> str:
    if regime is None:
        return "VIX unavailable"
    parts = []
    if regime == "calm":
        parts.append("options are cheap")
    elif regime == "normal":
        parts.append("options fairly priced")
    elif regime == "elevated":
        parts.append("premium is rich — spreads over naked calls")
    else:
        parts.append("stress — sell premium or stand aside")
    if pct is not None:
        parts.append("%gth pct of the year" % pct)
    if shape == "backwardation":
        parts.append("near-term fear (backwardation)")
    elif shape == "contango":
        parts.append("contango")
    if chg is not None and abs(chg) >= 1.0:
        parts.append("%s %.1f on the day" % ("up" if chg > 0 else "down", abs(chg)))
    return " · ".join(parts)


def compute() -> dict:
    """Fresh read (no cache). Every field is None-safe."""
    vix = _closes(_load("^VIX", "1y"))
    out = {"vix": None, "prev": None, "chg": None, "chg_pct": None, "pct_252": None,
           "regime": None, "regime_label": None,
           "bands": {"calm_below": CALM_BELOW, "normal_below": NORMAL_BELOW,
                     "elevated_below": ELEVATED_BELOW},
           "term": {"vix9d": None, "vix3m": None, "ratio_9d_30d": None,
                    "ratio_30d_3m": None, "shape": None, "as_of": None, "stale": False},
           "vvix": None, "as_of": None, "read": None,
           "generated_at": time.time(), "disclaimer": DISCLAIMER}
    if not vix:
        out["read"] = _one_liner(None, None, None, None)
        return out
    as_of, level = vix[-1]
    prev = vix[-2][1] if len(vix) >= 2 else None
    chg = round(level - prev, 2) if prev is not None else None
    out.update({"vix": round(level, 2), "prev": round(prev, 2) if prev is not None else None,
                "chg": chg,
                "chg_pct": round((level / prev - 1) * 100.0, 1) if prev else None,
                "pct_252": pct_rank([c for _, c in vix], level),
                "as_of": as_of})
    regime = classify(level)
    out["regime"], out["regime_label"] = regime, LABELS.get(regime)

    by_date = dict(vix)
    v9 = dict(_closes(_load("^VIX9D", "1y")))
    v3 = dict(_closes(_load("^VIX3M", "1y")))
    # Align on the newest date where ^VIX and at least one tenor closed.
    term_date = None
    for d, _ in reversed(vix):
        if d in v9 or d in v3:
            term_date = d
            break
    shape = None
    if term_date is not None and _lag_days(as_of, term_date) > TERM_MAX_LAG_DAYS:
        out["term"] = {"vix9d": None, "vix3m": None, "ratio_9d_30d": None,
                       "ratio_30d_3m": None, "shape": None, "as_of": term_date,
                       "stale": True}
        term_date = None
    if term_date is not None:
        base = by_date[term_date]
        r9 = round(v9[term_date] / base, 3) if term_date in v9 and base else None
        r3 = round(base / v3[term_date], 3) if term_date in v3 and v3[term_date] else None
        # Shape from the 30d/3m leg when we have it (the classic curve read),
        # else from 9d/30d.
        shape = term_shape(r3 if r3 is not None else r9)
        out["term"] = {"vix9d": round(v9[term_date], 2) if term_date in v9 else None,
                       "vix3m": round(v3[term_date], 2) if term_date in v3 else None,
                       "ratio_9d_30d": r9, "ratio_30d_3m": r3,
                       "shape": shape, "as_of": term_date, "stale": False}
    vv = _closes(_load("^VVIX", "1y"))
    if vv:
        out["vvix"] = round(vv[-1][1], 2)
    out["read"] = _one_liner(regime, out["pct_252"], shape, chg)
    return out


def get(force: bool = False) -> dict:
    """Cached read (TTL_SEC); `age_sec` says how old the payload is."""
    now = time.time()
    with _LOCK:
        data = _CACHE["data"]
        if not force and data is not None and now - _CACHE["at"] < TTL_SEC:
            return dict(data, age_sec=round(now - _CACHE["at"], 1))
    fresh = compute()
    with _LOCK:
        _CACHE["data"], _CACHE["at"] = fresh, time.time()
    return dict(fresh, age_sec=0.0)
