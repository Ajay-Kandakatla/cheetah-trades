"""Market Gauge — a book-grounded, multi-pillar read of the GENERAL MARKET.

OUR OWN model — NOT a clone of any paid indicator (those formulas are
undisclosed; per Rule #1 we won't reverse-engineer a real-money signal). It
composes the market signals the app ALREADY computes into a single 0-100 health
score + a Constructive / Caution / Risk-Off state + a Minervini exposure band.

Every pillar is REAL data or honestly degraded — nothing is fabricated. Where a
feed isn't in the app (CPI / jobs / Fed-funds need FRED; true order-flow /
dark-pool need a tape feed), the pillar says so and stays neutral rather than
inventing a number.

PILLARS (category → signal → source):
  • Quant      — Index trend "in gear" (SPY/QQQ Trend Template, Minervini p.79)
                 Volatility (VIX level + 252-day percentile, market_regime)
  • Trend tech — Index distribution days + follow-through (SPY/QQQ; concept p.248)
  • Breadth    — % of the latest scan red today
  • Flow/Liq   — Net up/down $-volume + Chaikin Money Flow aggregated across the
                 scan (institutional accumulation vs distribution)
  • Sentiment  — Options put/call: median SOIR across the optionable universe
  • Alt-data   — Insider cluster-BUY breadth (SEC Form 4 open-market buys)
  • Economic   — Treasury yield curve (10y − 3m via ^TNX/^IRX). CPI/jobs/Fed-funds
                 are NOT wired (need FRED) — flagged, not faked.
  • Macro      — macro_risk regime + major-news event detection

WHY (book): O'Neil's "M" — ~3 of 4 stocks follow the market. Minervini Ch.5
(p.79): trade WITH the trend, indices "in gear". Ch.12-13 (pp.303-305): scale
exposure DOWN in weak tapes, pyramid UP when in gear, pace re-entry. The
exposure band restates that framework — educational, NOT advice.

It does NOT predict. Nobody forecasts a week ahead; this reads the CURRENT
regime so you react on probabilities. Configured (non-book) thresholds are
labelled and locked by a source-guard test.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from . import prices
from . import scanner as sepa_scanner

log = logging.getLogger("sepa.market_gauge")

INDEXES = ("SPY", "QQQ")

# ── Pillar weights (sum = 100) ───────────────────────────────────────────────
W_TREND = 20            # index Trend Template "in gear" (Minervini p.79, Ch.5)
W_MACRO = 12            # macro-risk regime + news events
W_VOLATILITY = 11       # VIX level + percentile (Quant)
W_FLOW = 11             # net $-volume + CMF aggregated across the scan
W_BREADTH = 8           # participation
W_DISTRIBUTION = 8      # institutional selling on the indices
W_FOLLOW_THROUGH = 5    # rally confirmation
W_SENTIMENT = 8         # options put/call (SOIR)
W_INSIDER = 6           # insider cluster-buy breadth (alt-data)
W_YIELD = 11            # treasury yield curve (economic)
# (legacy alias so older callers/tests referencing W_REGIME still resolve)
W_REGIME = W_MACRO

# ── Distribution-day read (CONFIGURED — O'Neil-style, no book in repo) ───────
DIST_LOOKBACK = 25
DIST_DOWN_PCT = -0.2
DIST_TOPPING = 5
# ── Follow-through (CONCEPT Minervini p.248; trigger CONFIGURED) ─────────────
FTD_LOOKBACK = 12
FTD_UP_PCT = 1.4

# ── State cutoffs on the 0-100 score ─────────────────────────────────────────
STATE_CONSTRUCTIVE = 67
STATE_CAUTION = 34

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


# ── raw index-price helpers ──────────────────────────────────────────────────
def _distribution_count(df, lookback: int = DIST_LOOKBACK) -> Optional[int]:
    """Down closes <= DIST_DOWN_PCT on HIGHER volume than prior, over `lookback`."""
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
    """A power up-day (>= FTD_UP_PCT on higher volume, above the 50-day)."""
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
    return max(counts) if counts else None


def _index_follow_through() -> bool:
    return any(_follow_through(prices.load_prices(s)) for s in INDEXES)


def _breadth_red_pct() -> Optional[int]:
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


def _scan_rows() -> list:
    try:
        return (sepa_scanner.load_latest() or {}).get("all_results") or []
    except Exception:
        return []


def _treasury_yield(sym: str) -> Optional[float]:
    """Latest yield from a CBOE yield index (^TNX = 10y, ^IRX = 3m). yfinance
    sometimes quotes these x10 (e.g. 42.5 = 4.25%); normalise that."""
    try:
        df = prices.load_prices(sym)
        if df is None or not len(df):
            return None
        v = float(df["close"].iloc[-1])
        if v != v:  # NaN
            return None
        return round(v / 10.0, 2) if v > 20 else round(v, 2)
    except Exception:
        return None


# ── pillar components — each returns (component_dict, driver_or_None) ─────────
def _trend_component():
    label, _ = _trend_state()
    pts = {"confirmed_uptrend": W_TREND, "mixed": round(W_TREND * 0.55),
           "caution": 0}.get(label, round(W_TREND * 0.5))
    drv = None
    if label == "confirmed_uptrend":
        drv = "S&P & Nasdaq in a confirmed uptrend (in gear)"
    elif label == "caution":
        drv = "S&P/Nasdaq NOT in a confirmed uptrend"
    return ({"key": "trend", "category": "Quant", "label": "Index trend (SPY + QQQ)",
             "value": label, "points": pts, "max": W_TREND,
             "basis": "Minervini Trend Template p.79; Ch.5"}, drv)


def _macro_component():
    level, score = _macro_level()
    pts = {"low": W_MACRO, "elevated": round(W_MACRO * 0.55), "high": round(W_MACRO * 0.2),
           "severe": 0, "unknown": round(W_MACRO * 0.5)}.get(level, round(W_MACRO * 0.5))
    drv = f"macro risk {level}" if level in ("high", "severe") else None
    return ({"key": "macro", "category": "Macro", "label": "Macro risk regime + news",
             "value": level + (f" ({int(score)})" if score is not None else ""),
             "points": pts, "max": W_MACRO, "basis": "macro_risk (VIX/distribution/news)"}, drv)


def _volatility_component():
    s = None
    try:
        from . import market_regime
        s = market_regime._stress_score("^VIX")
    except Exception:
        s = None
    if not s or s.get("vix") is None:
        return ({"key": "volatility", "category": "Quant", "label": "Volatility (VIX)",
                 "value": "n/a", "points": round(W_VOLATILITY * 0.5), "max": W_VOLATILITY,
                 "basis": "VIX 252-day percentile (market_regime)"}, None)
    pct = s.get("percentile_252d")
    if pct is None:
        pts = round(W_VOLATILITY * 0.5)
    else:
        pts = round(W_VOLATILITY * _clamp01((80 - pct) / 60.0))  # <=20th full, >=80th zero
    drv = f"VIX elevated ({s.get('vix')}, {pct}th pct)" if (pct is not None and pct >= 70) else None
    val = f"{s.get('vix')}" + (f" · {pct}th pct" if pct is not None else "")
    return ({"key": "volatility", "category": "Quant", "label": "Volatility (VIX)",
             "value": val, "points": pts, "max": W_VOLATILITY,
             "basis": "VIX level + 252-day percentile"}, drv)


def _flow_component():
    rows = _scan_rows()
    nets = [(r.get("volume") or {}).get("net_dollar_vol_50") for r in rows]
    nets = [x for x in nets if isinstance(x, (int, float))]
    cmfs = [(r.get("volume") or {}).get("cmf_20") for r in rows]
    cmfs = [x for x in cmfs if isinstance(x, (int, float))]
    if not nets and not cmfs:
        return ({"key": "flow", "category": "Flow & Liquidity", "label": "Money flow / liquidity",
                 "value": "n/a", "points": round(W_FLOW * 0.5), "max": W_FLOW,
                 "basis": "scan net $-volume + Chaikin MF"}, None)
    inflow_share = (sum(1 for x in nets if x > 0) / len(nets)) if nets else 0.5
    avg_cmf = (sum(cmfs) / len(cmfs)) if cmfs else 0.0
    flow01 = _clamp01(0.5 * inflow_share + 0.5 * ((avg_cmf + 1) / 2))
    pts = round(W_FLOW * flow01)
    drv = (f"net distribution across the tape (avg CMF {round(avg_cmf, 2)})"
           if flow01 < 0.4 else None)
    val = f"{round(inflow_share * 100)}% inflow · CMF {round(avg_cmf, 2)}"
    return ({"key": "flow", "category": "Flow & Liquidity", "label": "Money flow / liquidity",
             "value": val, "points": pts, "max": W_FLOW,
             "basis": "scan up/down $-volume + Chaikin Money Flow"}, drv)


def _breadth_component():
    breadth = _breadth_red_pct()
    if breadth is None:
        return ({"key": "breadth", "category": "Breadth", "label": "Breadth (latest scan)",
                 "value": "n/a", "points": round(W_BREADTH * 0.5), "max": W_BREADTH,
                 "basis": "% of scanned names red"}, None)
    pts = round(W_BREADTH * _clamp01((70 - breadth) / 40.0))
    drv = f"{breadth}% of scanned names red" if breadth >= 60 else None
    return ({"key": "breadth", "category": "Breadth", "label": "Breadth (latest scan)",
             "value": f"{breadth}% red", "points": pts, "max": W_BREADTH,
             "basis": "% of scanned names red today"}, drv)


def _distribution_component():
    dist = _index_distribution()
    if dist is None:
        return ({"key": "distribution", "category": "Trend tech", "label": "Index distribution days",
                 "value": "n/a", "points": round(W_DISTRIBUTION * 0.5), "max": W_DISTRIBUTION,
                 "basis": "configured (O'Neil-style)"}, None)
    pts = round(W_DISTRIBUTION * _clamp01((DIST_TOPPING - dist) / float(DIST_TOPPING)))
    drv = f"{dist} index distribution days (under distribution)" if dist >= DIST_TOPPING else None
    return ({"key": "distribution", "category": "Trend tech", "label": "Index distribution days",
             "value": f"{dist} in {DIST_LOOKBACK}d", "points": pts, "max": W_DISTRIBUTION,
             "basis": "configured (O'Neil-style)"}, drv)


def _follow_through_component():
    ftd = _index_follow_through()
    label, _ = _trend_state()
    pts = W_FOLLOW_THROUGH if ftd else (0 if label == "caution" else round(W_FOLLOW_THROUGH * 0.5))
    drv = "recent index follow-through day" if ftd else None
    return ({"key": "follow_through", "category": "Trend tech", "label": "Follow-through",
             "value": "yes" if ftd else "no", "points": pts, "max": W_FOLLOW_THROUGH,
             "basis": "Minervini p.248 (concept); configured trigger"}, drv)


def _sentiment_component():
    median_soir = None
    try:
        from . import history
        db = history._get_db()
        if db is not None:
            vals = [d.get("soir") for d in db.soir_latest.find({}, {"_id": 0, "soir": 1})
                    if isinstance(d.get("soir"), (int, float)) and d.get("soir") > 0]
            if vals:
                vals.sort()
                median_soir = round(vals[len(vals) // 2], 2)
    except Exception:
        median_soir = None
    if median_soir is None:
        return ({"key": "sentiment", "category": "Sentiment", "label": "Options put/call (SOIR)",
                 "value": "n/a", "points": round(W_SENTIMENT * 0.5), "max": W_SENTIMENT,
                 "basis": "median SOIR (run the options scanner)"}, None)
    # SOIR = put_oi/call_oi. Call-leaning (<~0.9) = risk-on; put-heavy (>~1.2) =
    # defensive/hedged. Directional for a TAPE-HEALTH read (contrarian at
    # extremes — see methodology doc).
    pts = round(W_SENTIMENT * _clamp01((1.3 - median_soir) / 0.8))
    drv = f"options skew defensive (median put/call {median_soir})" if median_soir >= 1.15 else None
    return ({"key": "sentiment", "category": "Sentiment", "label": "Options put/call (SOIR)",
             "value": f"{median_soir} median", "points": pts, "max": W_SENTIMENT,
             "basis": "median Schaeffer's OI ratio across optionable names"}, drv)


def _insider_component():
    rows = [r for r in _scan_rows() if isinstance(r.get("insider"), dict)]
    if not rows:
        return ({"key": "insider", "category": "Alt-data", "label": "Insider cluster buying",
                 "value": "n/a", "points": round(W_INSIDER * 0.5), "max": W_INSIDER,
                 "basis": "SEC Form 4 (scan-enriched)"}, None)
    buys = sum(1 for r in rows if (r.get("insider") or {}).get("cluster_buy"))
    sells = sum(1 for r in rows if (r.get("insider") or {}).get("cluster_sell"))
    net01 = (buys + 1) / (buys + sells + 2)   # Laplace-smoothed buy share
    pts = round(W_INSIDER * net01)
    drv = f"{buys} insider cluster-buys across the scan" if buys else None
    return ({"key": "insider", "category": "Alt-data", "label": "Insider cluster buying",
             "value": f"{buys} buys / {sells} sells ({len(rows)} checked)", "points": pts,
             "max": W_INSIDER, "basis": "SEC Form 4 open-market buys"}, drv)


def _yield_curve_component():
    ten = _treasury_yield("^TNX")
    three = _treasury_yield("^IRX")
    if ten is None or three is None:
        return ({"key": "yield_curve", "category": "Economic", "label": "Yield curve (10y − 3m)",
                 "value": "n/a — CPI/jobs need FRED", "points": round(W_YIELD * 0.5),
                 "max": W_YIELD, "basis": "^TNX/^IRX (yfinance); CPI/jobs need FRED"}, None)
    spread = round(ten - three, 2)
    pts = round(W_YIELD * _clamp01((spread + 0.5) / 2.0))  # <=-0.5 zero, >=1.5 full
    drv = f"yield curve inverted ({spread})" if spread < 0 else None
    return ({"key": "yield_curve", "category": "Economic", "label": "Yield curve (10y − 3m)",
             "value": f"{spread}% ({ten} − {three})", "points": pts, "max": W_YIELD,
             "basis": "10y ^TNX − 3m ^IRX; CPI/jobs/Fed-funds need FRED"}, drv)


PILLARS = (
    _trend_component, _volatility_component, _distribution_component,
    _follow_through_component, _breadth_component, _flow_component,
    _sentiment_component, _insider_component, _yield_curve_component,
    _macro_component,
)


def _config() -> dict:
    return {
        "weights": {"trend": W_TREND, "macro": W_MACRO, "volatility": W_VOLATILITY,
                    "flow": W_FLOW, "breadth": W_BREADTH, "distribution": W_DISTRIBUTION,
                    "follow_through": W_FOLLOW_THROUGH, "sentiment": W_SENTIMENT,
                    "insider": W_INSIDER, "yield_curve": W_YIELD},
        "distribution": {"lookback": DIST_LOOKBACK, "down_pct": DIST_DOWN_PCT,
                         "topping": DIST_TOPPING},
        "follow_through": {"lookback": FTD_LOOKBACK, "up_pct": FTD_UP_PCT},
        "state_cutoffs": {"constructive": STATE_CONSTRUCTIVE, "caution": STATE_CAUTION},
        "not_wired": ["CPI", "unemployment", "Fed funds", "FRED yield series",
                      "true order-flow / dark-pool tape", "fear/greed index"],
    }


def compute() -> dict:
    """Compose every pillar (real data or honestly degraded) into the gauge."""
    t0 = time.time()
    comps: list[dict] = []
    drivers: list[str] = []
    for pillar in PILLARS:
        try:
            comp, drv = pillar()
        except Exception as exc:                      # a bad pillar never sinks the gauge
            log.debug("market_gauge pillar %s failed: %s", getattr(pillar, "__name__", "?"), exc)
            continue
        comps.append(comp)
        if drv:
            drivers.append(drv)

    score = max(0, min(100, round(sum(c["points"] for c in comps))))
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
        "config": _config(),
        "disclaimer": ("Educational market-health read, not a forecast or "
                       "personalized buy/sell/position-sizing advice. CPI, jobs, "
                       "Fed-funds and true order-flow are not wired (need FRED / a "
                       "tape feed) — those pillars stay neutral, not faked."),
    }


# ── In-process cache (the top-right badge hits this on every page) ───────────
_CACHE: dict = {"at": 0.0, "data": None}
_TTL_SEC = 300


def get_gauge(force: bool = False) -> dict:
    now = time.time()
    if not force and _CACHE["data"] is not None and (now - _CACHE["at"]) < _TTL_SEC:
        return _CACHE["data"]
    data = compute()
    _CACHE.update(at=now, data=data)
    return data
