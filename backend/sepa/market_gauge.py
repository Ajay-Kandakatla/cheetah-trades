"""Market Gauge — a book-grounded, multi-pillar read of the GENERAL MARKET.

OUR OWN model — NOT a clone of any paid indicator (those formulas are
undisclosed; per Rule #1 we won't reverse-engineer a real-money signal). It
composes the market signals the app ALREADY computes into a single 0-100 health
score + a Constructive / Caution / Risk-Off state + a Minervini exposure band.

Every pillar is REAL data or honestly degraded — nothing is fabricated. Where a
feed isn't in the app (true order-flow / dark-pool need a tape feed), the pillar
says so and stays neutral rather than inventing a number. The Economic pillars
read live from FRED (free key) and degrade to neutral if FRED_API_KEY is unset.

PILLARS (category → signal → source):
  • Quant      — Index trend "in gear" (SPY/QQQ Trend Template, Minervini p.79)
                 Volatility (VIX level + 252-day percentile, market_regime)
  • Trend tech — Index distribution days + follow-through (SPY/QQQ; concept p.248)
  • Breadth    — % of the latest scan red today
  • Flow/Liq   — Net up/down $-volume + Chaikin Money Flow aggregated across the
                 scan (institutional accumulation vs distribution)
  • Sentiment  — Options put/call: median SOIR across the optionable universe
  • Alt-data   — Insider cluster-BUY breadth (SEC Form 4 open-market buys)
  • Economic   — FRED macro feed (free key): CPI YoY (CPIAUCSL), unemployment
                 level+trend (UNRATE), Fed-funds level+direction (FEDFUNDS), and
                 the 10y−3m recession curve (T10Y3M). Neutral if no FRED_API_KEY.
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
import os
import time
from typing import Optional

from . import fred
from . import prices
from . import scanner as sepa_scanner

log = logging.getLogger("sepa.market_gauge")

INDEXES = ("SPY", "QQQ")

# ── Pillar weights (sum = 100) ───────────────────────────────────────────────
# 13 pillars. The Economic block is now FRED-wired and weighted HEAVY (34/100 —
# Ajay 2026-06-06): the four macro pillars together outweigh the price-trend
# block. The 9 non-economic pillars were trimmed proportionally (×66/89) so the
# total stays 100. Locked by test_sepa_contracts.py::test_market_gauge_locked.
W_TREND = 15            # index Trend Template "in gear" (Minervini p.79, Ch.5)
W_MACRO = 9             # macro-risk regime + news events
W_VOLATILITY = 8        # VIX level + percentile (Quant)
W_FLOW = 8              # net $-volume + CMF aggregated across the scan
W_BREADTH = 6           # participation
W_DISTRIBUTION = 6      # institutional selling on the indices
W_FOLLOW_THROUGH = 4    # rally confirmation
W_SENTIMENT = 6         # options put/call (SOIR)
W_INSIDER = 4           # insider cluster-buy breadth (alt-data)
# Economic block (FRED) — sum 34:
W_YIELD = 8             # 10y−3m recession curve (FRED T10Y3M)
W_CPI = 9               # CPI YoY inflation (FRED CPIAUCSL)
W_UNEMP = 9             # unemployment level + 6mo trend (FRED UNRATE)
W_FEDFUNDS = 8          # Fed-funds level + 12mo direction (FRED FEDFUNDS)
# (legacy alias so older callers/tests referencing W_REGIME still resolve)
W_REGIME = W_MACRO

# ── Distribution-day read (CONFIGURED — O'Neil-style, no book in repo) ───────
DIST_LOOKBACK = 25
DIST_DOWN_PCT = -0.2
DIST_TOPPING = 5
# ── Follow-through (CONCEPT Minervini p.248; trigger CONFIGURED) ─────────────
FTD_LOOKBACK = 12
FTD_UP_PCT = 1.4

# ── Weekly gauge (the SAME book concepts on WEEKLY bars) ─────────────────────
# Horizon companion to the daily gauge: "what kind of WEEK are we in." Minervini's
# Trend Template (p.79) maps the daily 50/150/200-day MAs to the classic weekly
# 10/30/40-week MAs; distribution + follow-through (concept p.248) recomputed on
# weekly bars. The weekly-MA lengths + weekly lookbacks/thresholds are CONFIGURED
# (no book in the repo prescribes weekly numbers) — clearly labelled, locked by
# the source-guard. NOT a forecast: a longer-horizon read of the CURRENT regime.
WK_MA_FAST = 10           # ≈ 50-day  (Minervini p.79 short-term gate, weekly)
WK_MA_MID = 30            # ≈ 150-day (intermediate gate, weekly)
WK_MA_SLOW = 40           # ≈ 200-day (long-term gate, weekly)
WK_TREND_RISING = 4       # 40-week MA must exceed its value this many weeks ago to be "rising"
# Frame floor MUST cover the full trend template: the 40-week MA is first valid at
# bar 39, and the "rising" gate looks back WK_TREND_RISING more — so a frame needs
# WK_MA_SLOW + WK_TREND_RISING + 1 (= 45) bars for ALL 5 gates to be evaluable.
# Admitting shorter frames would silently drop the 45-pt trend pillar and make
# Constructive unreachable (locked by test_weekly_min_bars_admits_full_trend_pillar).
WK_MIN_BARS = WK_MA_SLOW + WK_TREND_RISING + 1   # = 45 weekly bars
WK_DIST_LOOKBACK = 8      # distribution WEEKS over the trailing 8 weeks
WK_DIST_DOWN_PCT = -1.0   # a down WEEK <= -1.0% (weekly bar; wider than the daily -0.2%)
WK_DIST_TOPPING = 4       # >= this many distribution weeks in 8 = topping
WK_FTD_LOOKBACK = 5       # a power up-WEEK within the trailing 5 weeks
WK_FTD_UP_PCT = 2.5       # >= +2.5% on the week, on higher weekly volume, above the 10-week MA
WK_MOM_FULL = 8.0         # weekly close >= +8% above the 30-week MA -> full momentum
WK_MOM_ZERO = -8.0        # weekly close <= -8% below the 30-week MA -> zero

# Weekly pillar weights (sum = 100; kept separate from the daily `weights`)
WK_W_TREND = 45           # weekly trend-template structure (the dominant weekly read)
WK_W_DISTRIBUTION = 20    # weekly distribution-week count
WK_W_MOMENTUM = 15        # index distance above/below the 30-week MA
WK_W_FOLLOW_THROUGH = 10  # weekly follow-through (re-accumulation tell)
WK_W_MACRO = 10           # macro-risk regime (weekly backdrop, reused)

# ── Economic pillars (FRED) — series ids + CONFIGURED thresholds ─────────────
# Data: St. Louis Fed FRED (cited per series in each pillar's `basis`). The
# thresholds that map a series to a 0-1 health score are standard-macro defaults
# (Fed ~2% inflation target; Sahm-rule rising-unemployment recession signal;
# policy tightening-vs-easing; curve inversion) — NOT from any book we hold.
# Clearly labelled, locked by the source-guard, like the O'Neil-style numbers.
FRED_CPI_SERIES = "CPIAUCSL"        # CPI, All Urban Consumers, All Items (YoY = inflation)
FRED_UNEMP_SERIES = "UNRATE"        # civilian unemployment rate (%)
FRED_FEDFUNDS_SERIES = "FEDFUNDS"   # Fed funds effective rate (%)
FRED_CURVE_SERIES = "T10Y3M"        # 10y − 3m constant-maturity spread (recession curve)

CPI_COOL = 2.0          # YoY <= this (Fed target) -> full health
CPI_HOT = 6.0           # YoY >= this -> zero (restrictive-Fed headwind)
CPI_DRIVER = 4.0        # YoY >= this surfaces an "inflation hot" driver

UNEMP_LOW = 3.5         # rate <= this -> strong labour market (level leg full)
UNEMP_HIGH = 7.0        # rate >= this -> weak labour market (level leg zero)
UNEMP_RISE_BAD = 0.5    # +this many pp over 6 months -> Sahm-style recession signal
UNEMP_RISE_DRIVER = 0.3 # +this many pp over 6 months surfaces a "rising" driver

FF_EASY = 2.0           # funds <= this -> accommodative (level leg full)
FF_RESTRICTIVE = 5.5    # funds >= this -> restrictive (level leg zero)
FF_TIGHTEN = 1.0        # +/- this many pp over 12 months defines the direction leg
FF_TIGHTEN_DRIVER = 0.5 # +this many pp over 12 months surfaces a "tightening" driver

CURVE_INVERT = -0.5     # spread <= this -> zero
CURVE_STEEP = 1.5       # spread >= this -> full

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


def _to_weekly(df):
    """Resample a daily OHLCV DataFrame (DatetimeIndex) to weekly (Fri-anchored)
    bars. Returns None if input is empty/unusable. Used by the weekly gauge."""
    if df is None or not len(df):
        return None
    try:
        w = df.resample("W-FRI").agg(
            {"open": "first", "high": "max", "low": "min",
             "close": "last", "volume": "sum"}).dropna()
        return w if len(w) else None
    except Exception:
        return None


# ── raw index-price helpers (timeframe-agnostic — daily OR weekly bars) ───────
def _distribution_count(df, lookback: int = DIST_LOOKBACK,
                        down_pct: float = DIST_DOWN_PCT) -> Optional[int]:
    """Down closes <= `down_pct` on HIGHER volume than prior, over `lookback` bars.
    Daily defaults reproduce the original behaviour; weekly callers pass weekly
    bars + weekly thresholds."""
    if df is None or len(df) < lookback + 2:
        return None
    c = df["close"].to_numpy(dtype=float)
    v = df["volume"].to_numpy(dtype=float)
    n = len(c)
    cnt = 0
    for i in range(max(1, n - lookback), n):
        chg = (c[i] / c[i - 1] - 1.0) * 100.0 if c[i - 1] else 0.0
        if chg <= down_pct and v[i] > v[i - 1]:
            cnt += 1
    return cnt


def _follow_through(df, lookback: int = FTD_LOOKBACK, up_pct: float = FTD_UP_PCT,
                    ma_window: int = 50, min_bars: int = 60) -> bool:
    """A power up-bar (>= `up_pct` on higher volume, above the `ma_window`-bar MA).
    Daily defaults reproduce the original behaviour; weekly callers pass weekly
    bars + a 10-week MA + a lower bar-count gate."""
    if df is None or len(df) < min_bars:
        return False
    c = df["close"].to_numpy(dtype=float)
    v = df["volume"].to_numpy(dtype=float)
    ma = df["close"].rolling(ma_window).mean().to_numpy(dtype=float)
    n = len(c)
    for i in range(max(1, n - lookback), n):
        chg = (c[i] / c[i - 1] - 1.0) * 100.0 if c[i - 1] else 0.0
        if chg >= up_pct and v[i] > v[i - 1] and ma[i] == ma[i] and c[i] > ma[i]:
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
    # FRED T10Y3M publishes the 10y−3m spread directly (the recession curve).
    spread = fred.latest(FRED_CURVE_SERIES)
    if spread is None:
        return ({"key": "yield_curve", "category": "Economic", "label": "Yield curve (10y − 3m)",
                 "value": "n/a — set FRED_API_KEY", "points": round(W_YIELD * 0.5),
                 "max": W_YIELD, "basis": f"FRED {FRED_CURVE_SERIES} (10y−3m); set FRED_API_KEY"}, None)
    spread = round(spread, 2)
    pts = round(W_YIELD * _clamp01((spread - CURVE_INVERT) / (CURVE_STEEP - CURVE_INVERT)))
    drv = f"yield curve inverted ({spread})" if spread < 0 else None
    return ({"key": "yield_curve", "category": "Economic", "label": "Yield curve (10y − 3m)",
             "value": f"{spread}%", "points": pts, "max": W_YIELD,
             "basis": f"FRED {FRED_CURVE_SERIES} — 10y−3m constant-maturity spread"}, drv)


def _cpi_component():
    infl = fred.yoy(FRED_CPI_SERIES)
    if infl is None:
        return ({"key": "cpi", "category": "Economic", "label": "Inflation (CPI YoY)",
                 "value": "n/a — set FRED_API_KEY", "points": round(W_CPI * 0.5),
                 "max": W_CPI, "basis": f"FRED {FRED_CPI_SERIES} YoY; set FRED_API_KEY"}, None)
    # Lower, target-anchored inflation = less Fed pressure = healthier tape. One-
    # sided (high inflation is THE regime risk); disinflation lifts the score
    # automatically as YoY falls. CONFIGURED, standard-macro (Fed ~2% target).
    pts = round(W_CPI * _clamp01((CPI_HOT - infl) / (CPI_HOT - CPI_COOL)))
    drv = f"inflation hot ({infl}% YoY)" if infl >= CPI_DRIVER else None
    return ({"key": "cpi", "category": "Economic", "label": "Inflation (CPI YoY)",
             "value": f"{infl}% YoY", "points": pts, "max": W_CPI,
             "basis": f"FRED {FRED_CPI_SERIES} year-over-year; CONFIGURED (Fed ~2% target)"}, drv)


def _unemployment_component():
    rate = fred.latest(FRED_UNEMP_SERIES)
    chg6 = fred.change(FRED_UNEMP_SERIES, 6)
    if rate is None:
        return ({"key": "unemployment", "category": "Economic", "label": "Unemployment (UNRATE)",
                 "value": "n/a — set FRED_API_KEY", "points": round(W_UNEMP * 0.5),
                 "max": W_UNEMP, "basis": f"FRED {FRED_UNEMP_SERIES}; set FRED_API_KEY"}, None)
    level01 = _clamp01((UNEMP_HIGH - rate) / (UNEMP_HIGH - UNEMP_LOW))
    # Rising unemployment is the recession signal (Sahm rule): +UNEMP_RISE_BAD pp
    # over 6 months -> trend leg zero, falling -> full. CONFIGURED, standard-macro.
    trend01 = 0.5 if chg6 is None else _clamp01((UNEMP_RISE_BAD - chg6) / (2 * UNEMP_RISE_BAD))
    pts = round(W_UNEMP * (0.5 * level01 + 0.5 * trend01))
    drv = (f"unemployment rising ({rate}%, +{chg6}pp/6mo)"
           if (chg6 is not None and chg6 >= UNEMP_RISE_DRIVER) else None)
    val = f"{rate}%" + (f" ({'+' if chg6 >= 0 else ''}{chg6}pp/6mo)" if chg6 is not None else "")
    return ({"key": "unemployment", "category": "Economic", "label": "Unemployment (UNRATE)",
             "value": val, "points": pts, "max": W_UNEMP,
             "basis": f"FRED {FRED_UNEMP_SERIES} level + 6mo trend; CONFIGURED (Sahm-style)"}, drv)


def _fed_funds_component():
    rate = fred.latest(FRED_FEDFUNDS_SERIES)
    chg12 = fred.change(FRED_FEDFUNDS_SERIES, 12)
    if rate is None:
        return ({"key": "fed_funds", "category": "Economic", "label": "Fed funds rate",
                 "value": "n/a — set FRED_API_KEY", "points": round(W_FEDFUNDS * 0.5),
                 "max": W_FEDFUNDS, "basis": f"FRED {FRED_FEDFUNDS_SERIES}; set FRED_API_KEY"}, None)
    level01 = _clamp01((FF_RESTRICTIVE - rate) / (FF_RESTRICTIVE - FF_EASY))
    # Policy DIRECTION dominates the regime: cutting = tailwind, hiking = headwind.
    # +/- FF_TIGHTEN pp over 12 months spans the direction leg. CONFIGURED.
    dir01 = 0.5 if chg12 is None else _clamp01((FF_TIGHTEN - chg12) / (2 * FF_TIGHTEN))
    pts = round(W_FEDFUNDS * (0.6 * dir01 + 0.4 * level01))
    drv = (f"Fed tightening (funds {rate}%, +{chg12}pp/yr)"
           if (chg12 is not None and chg12 >= FF_TIGHTEN_DRIVER) else None)
    val = f"{rate}%" + (f" ({'+' if chg12 >= 0 else ''}{chg12}pp/yr)" if chg12 is not None else "")
    return ({"key": "fed_funds", "category": "Economic", "label": "Fed funds rate",
             "value": val, "points": pts, "max": W_FEDFUNDS,
             "basis": f"FRED {FRED_FEDFUNDS_SERIES} level + 12mo direction; CONFIGURED"}, drv)


PILLARS = (
    _trend_component, _volatility_component, _distribution_component,
    _follow_through_component, _breadth_component, _flow_component,
    _sentiment_component, _insider_component,
    # Economic block (FRED)
    _yield_curve_component, _cpi_component, _unemployment_component, _fed_funds_component,
    _macro_component,
)


def _state_of(score: int) -> tuple[str, str]:
    if score >= STATE_CONSTRUCTIVE:
        return "constructive", "Constructive"
    if score >= STATE_CAUTION:
        return "caution", "Caution"
    return "risk_off", "Risk-Off"


def _et_hhmm() -> str:
    """Weekday + HH:MM in US/Eastern (market time), regardless of container TZ.
    The weekday keeps a persisted pre-open doc from reading as 'today' over a
    weekend/holiday (e.g. a Friday read shown Saturday is 'pre-open Fri 08:32')."""
    try:
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        return datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York")).strftime("%a %H:%M ET")
    except Exception:
        return time.strftime("%a %H:%M")


# ── Weekly gauge — the SAME book concepts on WEEKLY bars ─────────────────────
def _weekly_trend_score(wdf) -> Optional[float]:
    """Minervini Trend Template (p.79) on WEEKLY bars → fraction of 5 structural
    gates passed. p.79 gives the weekly equivalents in parentheses verbatim
    (50-day=10-week, 150-day=30-week, 200-day=40-week), so these gates map straight
    onto the book's criteria: close>10wk (crit 5), close>30wk & close>40wk (crit 1),
    10wk>30wk (crit 4), 40wk MA rising ≥1 month (crit 3)."""
    if wdf is None or len(wdf) < WK_MA_SLOW:
        return None
    c = wdf["close"]
    ma_f = c.rolling(WK_MA_FAST).mean()
    ma_m = c.rolling(WK_MA_MID).mean()
    ma_s = c.rolling(WK_MA_SLOW).mean()
    i = len(c) - 1
    px, f, m, s = float(c.iloc[i]), float(ma_f.iloc[i]), float(ma_m.iloc[i]), float(ma_s.iloc[i])
    if any(x != x for x in (px, f, m, s)):          # NaN guard
        return None
    j = i - WK_TREND_RISING
    s_prev = float(ma_s.iloc[j]) if j >= 0 else float("nan")
    rising = bool(s_prev == s_prev and s > s_prev)  # 40-wk (≈200-day) trending up
    gates = [px > f, px > m, f > m, rising, px > s]
    return sum(1 for g in gates if g) / len(gates)


def _weekly_frames() -> list:
    out = []
    for sym in INDEXES:
        try:
            w = _to_weekly(prices.load_prices(sym))
        except Exception:
            w = None
        if w is not None and len(w) >= WK_MIN_BARS:
            out.append(w)
    return out


def compute_weekly() -> Optional[dict]:
    """Longer-horizon companion to `compute()`: the structural read of the WEEK,
    from SPY/QQQ weekly bars. Returns None when index data is unavailable."""
    frames = _weekly_frames()
    if not frames:
        return None
    comps: list[dict] = []
    drivers: list[str] = []

    # 1) Weekly trend template (avg per-index gate fraction)
    ts = [t for t in (_weekly_trend_score(w) for w in frames) if t is not None]
    if ts:
        frac = sum(ts) / len(ts)
        comps.append({"key": "wk_trend", "category": "Weekly structure",
                      "label": "Weekly trend template (10/30/40-wk)",
                      "value": f"{round(frac * 5)}/5 gates", "points": round(WK_W_TREND * frac),
                      "max": WK_W_TREND,
                      "basis": "Minervini Trend Template p.79 on weekly bars (10/30/40-wk ≈ 50/150/200-day)"})
        if frac < 0.6:
            drivers.append("weekly trend structure broken (below key weekly MAs)")
        elif frac >= 0.8:
            drivers.append("weekly trend in gear (above stacked, rising weekly MAs)")

    # 2) Weekly distribution
    wd = [d for d in (_distribution_count(w, lookback=WK_DIST_LOOKBACK, down_pct=WK_DIST_DOWN_PCT)
                      for w in frames) if d is not None]
    if wd:
        dist = max(wd)
        comps.append({"key": "wk_distribution", "category": "Weekly structure",
                      "label": "Weekly distribution",
                      "value": f"{dist} in {WK_DIST_LOOKBACK}wk",
                      "points": round(WK_W_DISTRIBUTION * _clamp01((WK_DIST_TOPPING - dist) / float(WK_DIST_TOPPING))),
                      "max": WK_W_DISTRIBUTION, "basis": "configured (O'Neil-style) on weekly bars"})
        if dist >= WK_DIST_TOPPING:
            drivers.append(f"{dist} distribution weeks (sustained weekly selling)")

    # 3) Weekly momentum — distance from the 30-week MA
    moms = []
    for w in frames:
        c = w["close"]
        ma = c.rolling(WK_MA_MID).mean()
        if len(c) and ma.iloc[-1] == ma.iloc[-1] and float(ma.iloc[-1]):
            moms.append((float(c.iloc[-1]) / float(ma.iloc[-1]) - 1.0) * 100.0)
    if moms:
        mom = sum(moms) / len(moms)
        comps.append({"key": "wk_momentum", "category": "Weekly structure",
                      "label": "Weekly momentum (vs 30-wk MA)",
                      "value": f"{'+' if mom >= 0 else ''}{round(mom, 1)}%",
                      "points": round(WK_W_MOMENTUM * _clamp01((mom - WK_MOM_ZERO) / (WK_MOM_FULL - WK_MOM_ZERO))),
                      "max": WK_W_MOMENTUM, "basis": "index distance from the 30-week MA (configured)"})

    # 4) Weekly follow-through
    wftd = any(_follow_through(w, lookback=WK_FTD_LOOKBACK, up_pct=WK_FTD_UP_PCT,
                               ma_window=WK_MA_FAST, min_bars=WK_MIN_BARS) for w in frames)
    comps.append({"key": "wk_follow_through", "category": "Weekly structure",
                  "label": "Weekly follow-through",
                  "value": "yes" if wftd else "no",
                  "points": WK_W_FOLLOW_THROUGH if wftd else round(WK_W_FOLLOW_THROUGH * 0.4),
                  "max": WK_W_FOLLOW_THROUGH,
                  "basis": "Minervini p.248 (concept) on weekly bars; configured trigger"})
    if wftd:
        drivers.append("weekly follow-through (institutional re-accumulation)")

    # 5) Macro backdrop (reused)
    level, _score = _macro_level()
    mpts = {"low": WK_W_MACRO, "elevated": round(WK_W_MACRO * 0.55), "high": round(WK_W_MACRO * 0.2),
            "severe": 0, "unknown": round(WK_W_MACRO * 0.5)}.get(level, round(WK_W_MACRO * 0.5))
    comps.append({"key": "wk_macro", "category": "Macro", "label": "Macro backdrop",
                  "value": level, "points": mpts, "max": WK_W_MACRO,
                  "basis": "macro_risk regime (weekly backdrop)"})

    score = max(0, min(100, round(sum(c["points"] for c in comps))))
    state, state_label = _state_of(score)
    return {"score": score, "state": state, "state_label": state_label,
            "drivers": drivers, "components": comps,
            "basis": "Minervini Trend Template p.79 + distribution/FTD concept p.248, on weekly bars"}


def _premarket_gap() -> Optional[dict]:
    """SPY/QQQ ETF pre-market gap vs prior close — NOT index futures (no futures
    feed exists; Massive carries the cash ETFs, not /ES,/NQ). Freshness-guarded:
    only returns a print from the last ~18h. {symbol: gap_pct} or None."""
    try:
        snap = prices.bulk_snapshot(list(INDEXES)) or {}
    except Exception:
        return None
    out = {}
    now_ms = time.time() * 1000.0
    for sym in INDEXES:
        d = snap.get(sym) or {}
        last, prev, ts = d.get("last_trade_price"), d.get("prev_day_close"), d.get("last_trade_ts_ms")
        if (isinstance(last, (int, float)) and isinstance(prev, (int, float)) and prev
                and isinstance(ts, (int, float)) and (now_ms - ts) <= 18 * 3600 * 1000):
            out[sym] = round((last / prev - 1.0) * 100.0, 2)
    return out or None


def _outlook(score: int, state: str, comps: list, weekly: Optional[dict],
             premarket: Optional[dict]) -> dict:
    """Conditions-based NEXT-DAY read: where the regime stands + exactly what would
    flip it. NOT a price prediction — leading signals + regime-flip triggers."""
    by = {c.get("key"): c for c in comps}
    watch: list[str] = []

    # Imminent high-impact macro events lead the watch list — they're the most
    # actionable "hold vs add" context (a FOMC/CPI readout can gap the whole
    # tape). Informational: does NOT change the gauge score or exposure band.
    try:
        from macro_calendar import imminent_events
        for ev in imminent_events(within_days=5, max_tier=1)[:2]:
            watch.append(f"📅 {ev['label']} {ev['when_label']} ({ev['date']}) — binary macro event; "
                         f"reduce NEW risk into it and let the readout confirm before adding")
    except Exception:
        pass

    # distance to the nearest regime flip (the cutoffs ARE the flip lines)
    if score >= STATE_CONSTRUCTIVE:
        watch.append(f"{score - STATE_CONSTRUCTIVE} pts of cushion above the Constructive line ({STATE_CONSTRUCTIVE})")
    elif score >= STATE_CAUTION:
        watch.append(f"{STATE_CONSTRUCTIVE - score} pts would flip it up to Constructive; "
                     f"{score - STATE_CAUTION} down to Risk-Off")
    else:
        watch.append(f"{STATE_CAUTION - score} pts to climb back into Caution ({STATE_CAUTION})")

    dist = by.get("distribution") or {}
    dval = dist.get("value")
    if isinstance(dval, str) and " in " in dval:
        try:
            n = int(dval.split()[0])
            if n >= DIST_TOPPING - 1:
                watch.append(f"distribution at {n}/{DIST_TOPPING} — one more index distribution day tips it weaker")
        except Exception:
            pass

    ft = by.get("follow_through") or {}
    if ft.get("value") == "no" and state != "constructive":
        watch.append(f"no recent follow-through — a +{FTD_UP_PCT}% up-day on higher volume would confirm a turn")

    vol = by.get("volatility") or {}
    if isinstance(vol.get("value"), str) and "pct" in vol.get("value", ""):
        watch.append(f"VIX {vol.get('value')} — a spike above the 70th percentile pressures the tape")

    if weekly:
        order = {"risk_off": 0, "caution": 1, "constructive": 2}
        d_rank, w_rank = order.get(state, 1), order.get(weekly["state"], 1)
        if w_rank - d_rank >= 1:
            watch.append("WEEKLY structure stronger than the day — near-term softness inside a "
                         "healthier larger trend (historically a pullback within an uptrend "
                         "rather than a top)")
        elif d_rank - w_rank >= 1:
            watch.append("day stronger than the WEEKLY structure — treat strength as counter-trend "
                         "until the week confirms")

    if premarket:
        gtxt = ", ".join(f"{s} {'+' if g >= 0 else ''}{g}%" for s, g in premarket.items())
        watch.append(f"pre-market (SPY/QQQ ETF print, not futures): {gtxt}")

    # Band descriptors restate Minervini's exposure FRAMEWORK (pp.304-305),
    # educational — not a personalized position-sizing instruction.
    label = {"constructive": "Trend in gear — Minervini's high-exposure band",
             "caution": "Mixed tape — reduced-exposure band",
             "risk_off": "Risk-off — capital-preservation band"}[state]
    note = f"Daily gauge {score} ({state.replace('_', ' ')})"
    if weekly:
        note += f" · weekly {weekly['score']} ({weekly['state'].replace('_', ' ')})"
    note += (". Reads the CURRENT regime and the triggers that would change it — "
             "not a prediction of where price closes. " + EXPOSURE[state]["note"])
    return {"bias": state, "label": label, "note": note, "watch": watch}


def _config() -> dict:
    return {
        "weights": {"trend": W_TREND, "macro": W_MACRO, "volatility": W_VOLATILITY,
                    "flow": W_FLOW, "breadth": W_BREADTH, "distribution": W_DISTRIBUTION,
                    "follow_through": W_FOLLOW_THROUGH, "sentiment": W_SENTIMENT,
                    "insider": W_INSIDER, "yield_curve": W_YIELD, "cpi": W_CPI,
                    "unemployment": W_UNEMP, "fed_funds": W_FEDFUNDS},
        "distribution": {"lookback": DIST_LOOKBACK, "down_pct": DIST_DOWN_PCT,
                         "topping": DIST_TOPPING},
        "follow_through": {"lookback": FTD_LOOKBACK, "up_pct": FTD_UP_PCT},
        "state_cutoffs": {"constructive": STATE_CONSTRUCTIVE, "caution": STATE_CAUTION},
        "fred_series": {"cpi": FRED_CPI_SERIES, "unemployment": FRED_UNEMP_SERIES,
                        "fed_funds": FRED_FEDFUNDS_SERIES, "yield_curve": FRED_CURVE_SERIES},
        # Weekly gauge weights kept SEPARATE from `weights` (which sums to 100 on
        # the daily pillars); the weekly set sums to 100 independently.
        "weekly_weights": {"trend": WK_W_TREND, "distribution": WK_W_DISTRIBUTION,
                           "momentum": WK_W_MOMENTUM, "follow_through": WK_W_FOLLOW_THROUGH,
                           "macro": WK_W_MACRO},
        "weekly": {"ma_weeks": [WK_MA_FAST, WK_MA_MID, WK_MA_SLOW],
                   "dist_lookback": WK_DIST_LOOKBACK, "dist_topping": WK_DIST_TOPPING,
                   "ftd_lookback": WK_FTD_LOOKBACK, "ftd_up_pct": WK_FTD_UP_PCT,
                   "min_bars": WK_MIN_BARS},
        "not_wired": ["index futures (/ES, /NQ) — only SPY/QQQ ETF pre-market is available",
                      "true order-flow / dark-pool tape", "fear/greed index"],
    }


def compute(include_premarket: bool = False) -> dict:
    """Compose every pillar (real data or honestly degraded) into the gauge, plus
    the WEEKLY companion gauge and a conditions-based next-day outlook.

    `include_premarket` makes a live SPY/QQQ ETF snapshot call for the pre-market
    gap — only the pre-open cron sets it True; the per-page badge path leaves it
    False (no live call on every refresh)."""
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
    state, state_label = _state_of(score)

    weekly = None
    try:
        weekly = compute_weekly()
    except Exception as exc:
        log.debug("market_gauge weekly failed: %s", exc)

    premarket = _premarket_gap() if include_premarket else None
    outlook = _outlook(score, state, comps, weekly, premarket)

    return {
        "generated_at": int(time.time()),
        "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "as_of_label": "live " + _et_hhmm(),
        "duration_sec": round(time.time() - t0, 3),
        "score": score,
        "state": state,
        "state_label": state_label,
        "exposure_band": EXPOSURE[state],
        "components": comps,
        "drivers": drivers,
        "weekly": weekly,
        "next_day_outlook": outlook,
        "implied_open": ({"source": "SPY/QQQ ETF pre-market gap (no index-futures feed)",
                          "gaps": premarket}
                         if premarket else
                         {"source": "not wired — no index-futures feed; only the SPY/QQQ "
                                    "ETF pre-market print is available", "gaps": None}),
        "config": _config(),
        "disclaimer": ("Educational market-health read, not a forecast or "
                       "personalized buy/sell/position-sizing advice. The weekly "
                       "gauge and outlook read the CURRENT regime across horizons — "
                       "they do not predict where price closes. Economic pillars read "
                       "live from FRED (neutral if no key); index futures are not "
                       "wired (only the SPY/QQQ ETF pre-market print), and true "
                       "order-flow / dark-pool tape needs a feed."),
    }


# ── Persistence — the 8:30 ET pre-open cron writes "latest"; the badge reads it ─
_PERSIST_FRESH_SEC = 20 * 3600    # a pre-open read stands as "today's" for ~20h


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        return client[os.getenv("MONGO_DB", "cheetah")].market_gauge
    except Exception:
        return None


def run_and_persist() -> dict:
    """Compute the gauge (with the pre-market gap) and upsert it as the pre-open
    'latest' doc. Called by the `sepa.cli market-gauge-preopen` 8:30am ET cron."""
    payload = compute(include_premarket=True)
    payload["as_of_label"] = "pre-open " + _et_hhmm()
    payload["source"] = "preopen"
    coll = _coll()
    if coll is not None:
        try:
            doc = dict(payload)
            doc["_id"] = "latest"
            doc["computed_at"] = int(time.time())
            coll.update_one({"_id": "latest"}, {"$set": doc}, upsert=True)
            log.info("market_gauge persisted pre-open: score=%s state=%s",
                     payload.get("score"), payload.get("state"))
        except Exception as exc:
            log.warning("market_gauge persist failed: %s", exc)
    _record_history(payload)                         # keep the dated series too
    _CACHE.update(at=time.time(), data=payload)     # warm the in-proc cache too
    return payload


def load_persisted() -> Optional[dict]:
    """Read the cron-persisted pre-open gauge (with age_sec), or None."""
    coll = _coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"_id": "latest"})
        if not doc:
            return None
        doc.pop("_id", None)
        doc["age_sec"] = int(time.time()) - int(doc.get("computed_at") or 0)
        return doc
    except Exception:
        return None


# ── History — one point per ET day so the FE can chart the trend over time
#    (Ajay 2026-06-13). The 'latest' doc above is OVERWRITTEN each run; this keeps
#    the series. History starts accumulating now — older reads weren't retained. ─
def _hist_coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        return client[os.getenv("MONGO_DB", "cheetah")].market_gauge_history
    except Exception:
        return None


def _today_et() -> str:
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def _record_history(payload: dict) -> None:
    """Upsert today's gauge point (idempotent per ET day — the latest read of the
    day wins). Never raises."""
    coll = _hist_coll()
    if coll is None or not payload or payload.get("score") is None:
        return
    try:
        day = _today_et()
        coll.update_one(
            {"_id": day},
            {"$set": {"date_et": day, "score": payload.get("score"),
                      "state": payload.get("state"), "source": payload.get("source"),
                      "computed_at": int(time.time())}},
            upsert=True,
        )
    except Exception as exc:                           # noqa: BLE001
        log.debug("market_gauge history record failed: %s", exc)


def history(days: int = 90) -> dict:
    """The gauge trend — one point per ET day, oldest→newest."""
    coll = _hist_coll()
    if coll is None:
        return {"rows": [], "available": False}
    try:
        rows = [r for r in coll.find({}, {"_id": 0}).sort("date_et", 1)
                if r.get("score") is not None]
        return {"rows": rows[-int(days):], "available": True}
    except Exception as exc:                           # noqa: BLE001
        log.debug("market_gauge history read failed: %s", exc)
        return {"rows": [], "available": False}


# ── In-process cache (the top-right badge hits this on every page) ───────────
_CACHE: dict = {"at": 0.0, "data": None}
_TTL_SEC = 300


def get_gauge(force: bool = False, prefer_persisted: bool = True) -> dict:
    """Serve the gauge. Default order: in-proc cache → the fresh pre-open doc
    (so the badge shows the morning read all day) → a live recompute. `force`
    always recomputes live and ignores the persisted pre-open doc."""
    now = time.time()
    if not force and _CACHE["data"] is not None and (now - _CACHE["at"]) < _TTL_SEC:
        return _CACHE["data"]
    if not force and prefer_persisted:
        doc = load_persisted()
        if doc is not None and doc.get("age_sec", 1e12) < _PERSIST_FRESH_SEC:
            _CACHE.update(at=now, data=doc)
            return doc
    data = compute()
    _record_history(data)                            # record live recomputes too
    _CACHE.update(at=now, data=data)
    return data
