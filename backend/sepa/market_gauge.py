"""Market Gauge — a book-grounded read of the GENERAL MARKET's health.

This is OUR OWN market-direction model. It is NOT a clone of any third-party
indicator: those formulas are proprietary/undisclosed and we will not
reverse-engineer a real-money signal from a competitor's marketing page
(Ajay's Rule #1). Instead it composes the market signals the app already
computes — all book-grounded — plus an index distribution-day / follow-through
read, into a single 0-100 health score + a Constructive / Caution / Risk-Off
state and a Minervini exposure band.

WHY a market read matters (book-cited):
  - O'Neil's CANSLIM "M": roughly 3 of 4 stocks follow the general market.
  - Minervini, *Trade Like a Stock Market Wizard* (2013), Ch.5: trade WITH the
    market's trend. The index Trend Template (SPY/QQQ above a rising 50/150/200
    stack, p.79) tells you whether the market is "in gear".
  - Minervini Ch.12-13 (pp.303-305): in a correction/bear "even good selection
    criteria can show poor results ... it's not time to buy; it's time to
    sell." SCALE DOWN exposure in a weak tape and "pyramid back up" when the
    plan is working; PACE re-entry after a correction (p.305). The gauge's
    exposure band encodes exactly this.
  - Follow-through (p.248): wait for a move to "pause and then follow through"
    before committing — confirmation, not prediction. Nobody forecasts a week
    ahead; you read the regime and react.

COMPONENTS (each book-cited OR transparently configured):
  1. Index trend   — market_context.market_state() — SPY+QQQ Trend Template (p.79)
  2. Macro regime  — macro_risk.get_market() — level/score
  3. Breadth       — % of the latest scan's names red today
  4. Distribution  — index higher-volume DOWN days over ~5 weeks. The down-day
                     and count thresholds are CONFIGURED (O'Neil-style, but NOT
                     verified against a book we hold — see the methodology doc;
                     drop *How to Make Money in Stocks* in the repo to lock the
                     exact O'Neil rules).
  5. Follow-through — a recent index power-up day on rising volume above the
                     50-day. The CONCEPT is Minervini p.248; the numeric trigger
                     is CONFIGURED.

NOT FINANCIAL ADVICE: an educational market-health read, not a forecast and not
a personalized buy/sell or position-sizing instruction. The exposure band
restates Minervini's general framework, not advice for any individual.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from . import prices
from . import scanner as sepa_scanner

log = logging.getLogger("sepa.market_gauge")

# ── Index universe for the breadth-independent (price) signals ───────────────
INDEXES = ("SPY", "QQQ")

# ── Component weights (sum = 100) ────────────────────────────────────────────
W_TREND = 40            # index Trend Template "in gear" (Minervini p.79, Ch.5)
W_REGIME = 20           # macro-risk regime
W_BREADTH = 15          # participation
W_DISTRIBUTION = 15     # institutional selling on the indices
W_FOLLOW_THROUGH = 10   # rally confirmation

# ── Distribution-day read (CONFIGURED — see module docstring + methodology) ──
DIST_LOOKBACK = 25      # sessions (~5 weeks)
DIST_DOWN_PCT = -0.2    # a down close this size on HIGHER volume = a distribution day
DIST_TOPPING = 5        # >= this many over the window = market under distribution

# ── Follow-through read (CONCEPT: Minervini p.248; trigger CONFIGURED) ───────
FTD_LOOKBACK = 12       # sessions to look back for a power up-day
FTD_UP_PCT = 1.4        # an up close this size on HIGHER volume = a follow-through day

# ── State cutoffs on the 0-100 health score ──────────────────────────────────
STATE_CONSTRUCTIVE = 67
STATE_CAUTION = 34

# ── Minervini exposure bands (educational; pp.304-305) ───────────────────────
EXPOSURE = {
    "constructive": {"low": 75, "high": 100,
                     "note": "Market in gear — Minervini: pyramid exposure up (p.304)."},
    "caution":      {"low": 25, "high": 50,
                     "note": "Mixed tape — trade smaller, be selective (p.304)."},
    "risk_off":     {"low": 0,  "high": 25,
                     "note": "Not time to buy — raise cash, pace re-entry (pp.304-305)."},
}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _distribution_count(df, lookback: int = DIST_LOOKBACK) -> Optional[int]:
    """Index distribution days: down closes <= DIST_DOWN_PCT on HIGHER volume
    than the prior session, over the last `lookback` bars."""
    if df is None or len(df) < lookback + 2:
        return None
    c = df["close"].to_numpy(dtype=float)
    v = df["volume"].to_numpy(dtype=float)
    n = len(c)
    cnt = 0
    for i in range(max(1, n - lookback), n):
        chg = (c[i] / c[i - 1] - 1.0) * 100.0 if c[i - 1] else 0.0
        if chg <= DIST_DOWN_PCT and v[i] > v[i - 1]:
            cnt += 1
    return cnt


def _follow_through(df, lookback: int = FTD_LOOKBACK) -> bool:
    """A recent power/follow-through day: up >= FTD_UP_PCT on HIGHER volume while
    trading above the 50-day MA (a confirmed-rally proxy; concept Minervini
    p.248)."""
    if df is None or len(df) < 60:
        return False
    c = df["close"].to_numpy(dtype=float)
    v = df["volume"].to_numpy(dtype=float)
    ma50 = df["close"].rolling(50).mean().to_numpy(dtype=float)
    n = len(c)
    for i in range(max(1, n - lookback), n):
        chg = (c[i] / c[i - 1] - 1.0) * 100.0 if c[i - 1] else 0.0
        if chg >= FTD_UP_PCT and v[i] > v[i - 1] and ma50[i] == ma50[i] and c[i] > ma50[i]:
            return True
    return False


def _index_distribution() -> Optional[int]:
    counts = [c for c in (_distribution_count(prices.load_prices(s)) for s in INDEXES)
              if c is not None]
    return max(counts) if counts else None   # worst (most distributed) of the two


def _index_follow_through() -> bool:
    return any(_follow_through(prices.load_prices(s)) for s in INDEXES)


def _breadth_red_pct() -> Optional[int]:
    """% of the latest scan's names that are red today."""
    try:
        rows = (sepa_scanner.load_latest() or {}).get("all_results") or []
        ch = [r.get("day_change_pct") for r in rows if r.get("day_change_pct") is not None]
        if ch:
            return round(100 * sum(1 for x in ch if x < 0) / len(ch))
    except Exception:
        pass
    return None


def _trend_state() -> tuple[str, dict]:
    try:
        from . import market_context
        ms = market_context.market_state() or {}
        return (ms.get("label") or "unknown"), ms
    except Exception:
        return "unknown", {}


def _macro_level() -> tuple[str, Optional[float]]:
    try:
        from . import macro_risk
        m = macro_risk.get_market() or {}
        return (m.get("level") or "unknown"), m.get("score")
    except Exception:
        return "unknown", None


def compute() -> dict:
    """Compose the market gauge. Cheap — reuses cached index frames + the cached
    macro regime + the latest scan's breadth. Safe to call per request."""
    t0 = time.time()
    drivers: list[str] = []
    comps: list[dict] = []

    # 1) Index trend — "in gear" (Minervini p.79, Ch.5) ----------------------
    label, _ms = _trend_state()
    trend_pts = {"confirmed_uptrend": W_TREND, "mixed": round(W_TREND * 0.55),
                 "caution": 0}.get(label, round(W_TREND * 0.5))
    comps.append({"key": "trend", "label": "Index trend (SPY + QQQ)",
                  "value": label, "points": trend_pts, "max": W_TREND,
                  "basis": "Minervini Trend Template p.79; Ch.5"})
    if label == "confirmed_uptrend":
        drivers.append("SPY & Nasdaq in a confirmed uptrend (in gear)")
    elif label == "caution":
        drivers.append("SPY/Nasdaq NOT in a confirmed uptrend")

    # 2) Macro regime --------------------------------------------------------
    level, mscore = _macro_level()
    regime_pts = {"low": W_REGIME, "elevated": round(W_REGIME * 0.55),
                  "high": round(W_REGIME * 0.2), "severe": 0,
                  "unknown": round(W_REGIME * 0.5)}.get(level, round(W_REGIME * 0.5))
    comps.append({"key": "regime", "label": "Macro risk regime",
                  "value": level + (f" ({int(mscore)})" if mscore is not None else ""),
                  "points": regime_pts, "max": W_REGIME, "basis": "macro_risk"})
    if level in ("high", "severe"):
        drivers.append(f"macro risk {level}")

    # 3) Breadth -------------------------------------------------------------
    breadth = _breadth_red_pct()
    if breadth is None:
        breadth_pts = round(W_BREADTH * 0.5)
        breadth_val = "n/a"
    else:
        # 30% red -> full credit, 70% red -> zero (linear)
        breadth_pts = round(W_BREADTH * _clamp01((70 - breadth) / 40.0))
        breadth_val = f"{breadth}% red"
        if breadth >= 60:
            drivers.append(f"{breadth}% of scanned names red")
    comps.append({"key": "breadth", "label": "Breadth (latest scan)",
                  "value": breadth_val, "points": breadth_pts, "max": W_BREADTH,
                  "basis": "participation"})

    # 4) Index distribution days (CONFIGURED) --------------------------------
    dist = _index_distribution()
    if dist is None:
        dist_pts = round(W_DISTRIBUTION * 0.5)
        dist_val = "n/a"
    else:
        dist_pts = round(W_DISTRIBUTION * _clamp01((DIST_TOPPING - dist) / float(DIST_TOPPING)))
        dist_val = f"{dist} in {DIST_LOOKBACK}d"
        if dist >= DIST_TOPPING:
            drivers.append(f"{dist} index distribution days (under distribution)")
    comps.append({"key": "distribution", "label": "Index distribution days",
                  "value": dist_val, "points": dist_pts, "max": W_DISTRIBUTION,
                  "basis": "configured (O'Neil-style)"})

    # 5) Follow-through ------------------------------------------------------
    ftd = _index_follow_through()
    if ftd:
        ft_pts = W_FOLLOW_THROUGH
        drivers.append("recent index follow-through day")
    else:
        ft_pts = 0 if label == "caution" else round(W_FOLLOW_THROUGH * 0.5)
    comps.append({"key": "follow_through", "label": "Follow-through",
                  "value": "yes" if ftd else "no", "points": ft_pts,
                  "max": W_FOLLOW_THROUGH,
                  "basis": "Minervini p.248 (concept); configured trigger"})

    score = max(0, min(100, trend_pts + regime_pts + breadth_pts + dist_pts + ft_pts))
    if score >= STATE_CONSTRUCTIVE:
        state, state_label = "constructive", "Constructive"
    elif score >= STATE_CAUTION:
        state, state_label = "caution", "Caution"
    else:
        state, state_label = "risk_off", "Risk-Off"

    return {
        "generated_at": int(time.time()),
        "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_sec": round(time.time() - t0, 3),
        "score": score,
        "state": state,
        "state_label": state_label,
        "exposure_band": EXPOSURE[state],
        "components": comps,
        "drivers": drivers,
        "config": {
            "weights": {"trend": W_TREND, "regime": W_REGIME, "breadth": W_BREADTH,
                        "distribution": W_DISTRIBUTION, "follow_through": W_FOLLOW_THROUGH},
            "distribution": {"lookback": DIST_LOOKBACK, "down_pct": DIST_DOWN_PCT,
                             "topping": DIST_TOPPING},
            "follow_through": {"lookback": FTD_LOOKBACK, "up_pct": FTD_UP_PCT},
            "state_cutoffs": {"constructive": STATE_CONSTRUCTIVE, "caution": STATE_CAUTION},
        },
        "disclaimer": ("Educational market-health read, not a forecast or "
                       "personalized buy/sell/position-sizing advice."),
    }


# ── In-process cache (the top-right badge hits this on every page) ───────────
_CACHE: dict = {"at": 0.0, "data": None}
_TTL_SEC = 300  # 5 min — market health doesn't change second-to-second


def get_gauge(force: bool = False) -> dict:
    """compute() behind a 5-minute per-process cache."""
    now = time.time()
    if not force and _CACHE["data"] is not None and (now - _CACHE["at"]) < _TTL_SEC:
        return _CACHE["data"]
    data = compute()
    _CACHE.update(at=now, data=data)
    return data
