"""Fidelity-style multi-panel stock analysis.

Reproduces the four panels from Fidelity's Sentiment + Analyst Ratings + ESG
views using only free data sources (yfinance + Finnhub + cached prices):

  1. Fundamental analysis  — Valuation, Quality, Growth Stability, Financial Health
                              (S&P Global-style 0-100 horizontal bars)
  2. Technical sentiment   — Short/Mid/Long-term Weak/Neutral/Strong cells
                              (Trading Central-style)
  3. ESG                   — Overall + Environment / Social / Governance
                              (MSCI-style Laggard/Average/Leader bars)
  4. Analyst consensus     — composite Equity Summary Score 0-10 + 1y history
                              (LSEG StarMine-style consolidated rating)

Caching: results land in the Mongo collection `stock_analysis_cache` for
60 minutes. Fundamentals + ESG change slowly, so the cache is generous.

Graceful degradation: every panel returns `None` (or an empty distribution)
when its upstream is unavailable — the frontend skips missing panels rather
than failing the whole tab.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import httpx

log = logging.getLogger("sepa.stock_analysis")

CACHE_TTL_SEC = 60 * 60  # 1 hour — fundamentals/ESG are slow-changing
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

# ---------------------------------------------------------------------------
# Mongo cache
# ---------------------------------------------------------------------------
_mongo_coll = None
_mongo_disabled = False


def _get_cache():
    """Return Mongo `stock_analysis_cache` collection or None."""
    global _mongo_coll, _mongo_disabled
    if _mongo_disabled:
        return None
    if _mongo_coll is not None:
        return _mongo_coll
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        coll = client[db_name].stock_analysis_cache
        coll.create_index([("symbol", ASCENDING)], unique=True)
        _mongo_coll = coll
        return _mongo_coll
    except Exception as exc:
        log.warning("stock_analysis: Mongo unavailable (%s)", exc)
        _mongo_disabled = True
        return None


def _cache_get(symbol: str) -> Optional[dict]:
    coll = _get_cache()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"symbol": symbol.upper()})
        if not doc:
            return None
        if (time.time() - (doc.get("cached_at") or 0)) >= CACHE_TTL_SEC:
            return None
        return doc.get("payload")
    except Exception:
        return None


def _cache_put(symbol: str, payload: dict) -> None:
    coll = _get_cache()
    if coll is None:
        return
    try:
        coll.update_one(
            {"symbol": symbol.upper()},
            {"$set": {"symbol": symbol.upper(), "payload": payload, "cached_at": int(time.time())}},
            upsert=True,
        )
    except Exception as exc:
        log.warning("stock_analysis cache write failed for %s: %s", symbol, exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _clip(v: Optional[float], lo: float, hi: float) -> Optional[float]:
    if v is None:
        return None
    return max(lo, min(hi, float(v)))


def _scale_linear(v: Optional[float], lo_at_0: float, hi_at_100: float) -> Optional[int]:
    """Linear scale a metric to 0-100 using the supplied endpoints.

    `lo_at_0` is the metric value that maps to 0, `hi_at_100` maps to 100.
    Set them in either order — the function infers direction.
    """
    if v is None:
        return None
    span = hi_at_100 - lo_at_0
    if span == 0:
        return 50
    pct = (v - lo_at_0) / span * 100.0
    return int(round(_clip(pct, 0, 100)))


def _label_0_100(score: Optional[int], inverted: bool = False) -> str:
    """0-100 → human label. inverted=True flips weak<->strong."""
    if score is None:
        return "—"
    s = 100 - score if inverted else score
    if s >= 70:
        return "Strong"
    if s >= 40:
        return "Neutral"
    return "Weak"


def _esg_label(score: Optional[float]) -> str:
    """MSCI-style label from 0-10 ESG risk-adjusted score (higher = better)."""
    if score is None:
        return "—"
    if score >= 7:
        return "Leader"
    if score >= 4:
        return "Average"
    return "Laggard"


# ---------------------------------------------------------------------------
# 1. Fundamental analysis
# ---------------------------------------------------------------------------
def fundamental_panel(symbol: str) -> dict:
    """Compute the four fundamental axes from yfinance `.info`.

    All four scores are 0-100 (higher = better). Returns the raw metric values
    too, so the UI can show "P/E 18 vs sector 22" tooltips.
    """
    try:
        import yfinance as yf
        info = yf.Ticker(symbol).info or {}
    except Exception as exc:
        log.warning("yfinance fundamentals failed for %s: %s", symbol, exc)
        return _empty_fundamentals()

    pe = info.get("trailingPE")
    fwd_pe = info.get("forwardPE")
    pbv = info.get("priceToBook")
    psales = info.get("priceToSalesTrailing12Months")
    peg = info.get("pegRatio")

    # ── Headline figures the user asked to see explicitly ─────────────────
    # marketCap         = current "company net worth" the market is paying
    #                     (price × shares outstanding)
    # totalRevenue      = TTM revenue from yfinance's income-statement summary
    # bookValue         = per-share equity book value
    # sharesOutstanding × bookValue ≈ total shareholders' equity
    market_cap = info.get("marketCap")
    revenue_ttm = info.get("totalRevenue")
    book_value_per_share = info.get("bookValue")
    shares_out = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
    shareholder_equity = None
    if book_value_per_share and shares_out:
        try:
            shareholder_equity = float(book_value_per_share) * float(shares_out)
        except Exception:
            shareholder_equity = None
    enterprise_value = info.get("enterpriseValue")
    total_debt = info.get("totalDebt")
    total_cash_short = info.get("totalCash")

    roe = info.get("returnOnEquity")  # decimal e.g. 0.32
    roa = info.get("returnOnAssets")
    profit_margin = info.get("profitMargins")
    op_margin = info.get("operatingMargins")

    rev_growth = info.get("revenueGrowth")    # YoY decimal
    earn_growth = info.get("earningsGrowth")

    debt_to_equity = info.get("debtToEquity")  # %
    current_ratio = info.get("currentRatio")
    fcf = info.get("freeCashflow")
    total_cash = info.get("totalCash")

    # ── Valuation: lower P/E + lower P/B + lower P/S → higher score
    # PE  10 → 90, PE 50 → 10
    # PBV 1  → 90, PBV 10 → 10
    # PS  1  → 90, PS  20 → 10
    valuation_parts: list[int] = []
    if pe is not None and pe > 0:
        valuation_parts.append(_scale_linear(pe, 50, 10) or 50)
    if pbv is not None and pbv > 0:
        valuation_parts.append(_scale_linear(pbv, 10, 1) or 50)
    if psales is not None and psales > 0:
        valuation_parts.append(_scale_linear(psales, 20, 1) or 50)
    valuation_score = round(sum(valuation_parts) / len(valuation_parts)) if valuation_parts else None

    # ── Quality: ROE / ROA / margins
    # ROE 0% → 0, ROE 30%+ → 100
    quality_parts: list[int] = []
    if roe is not None:
        quality_parts.append(_scale_linear(roe * 100, 0, 30) or 0)
    if roa is not None:
        quality_parts.append(_scale_linear(roa * 100, 0, 15) or 0)
    if profit_margin is not None:
        quality_parts.append(_scale_linear(profit_margin * 100, 0, 25) or 0)
    if op_margin is not None:
        quality_parts.append(_scale_linear(op_margin * 100, 0, 30) or 0)
    quality_score = round(sum(quality_parts) / len(quality_parts)) if quality_parts else None

    # ── Growth Stability: revenue + earnings growth
    growth_parts: list[int] = []
    if rev_growth is not None:
        growth_parts.append(_scale_linear(rev_growth * 100, 0, 30) or 0)
    if earn_growth is not None:
        growth_parts.append(_scale_linear(earn_growth * 100, 0, 50) or 0)
    growth_score = round(sum(growth_parts) / len(growth_parts)) if growth_parts else None

    # ── Financial Health: debt/equity (lower better), current ratio, FCF positive
    health_parts: list[int] = []
    if debt_to_equity is not None:
        # 0 → 100, 200 → 0 (D/E in %)
        health_parts.append(_scale_linear(debt_to_equity, 200, 0) or 50)
    if current_ratio is not None:
        # 1 → 30, 2.5+ → 100
        health_parts.append(_scale_linear(current_ratio, 1, 2.5) or 30)
    if fcf is not None:
        health_parts.append(80 if fcf > 0 else 20)
    if total_cash is not None and fcf is not None:
        # cash buffer
        health_parts.append(70 if total_cash > 0 else 30)
    health_score = round(sum(health_parts) / len(health_parts)) if health_parts else None

    return {
        "available": any(v is not None for v in [valuation_score, quality_score, growth_score, health_score]),
        "headline": {
            "market_cap": market_cap,
            "shareholder_equity": shareholder_equity,
            "book_value_per_share": book_value_per_share,
            "shares_outstanding": shares_out,
            "revenue_ttm": revenue_ttm,
            "enterprise_value": enterprise_value,
            "total_debt": total_debt,
            "total_cash": total_cash_short,
        },
        "valuation": {
            "score": valuation_score,
            "label": "Undervalued" if (valuation_score or 0) >= 70 else
                     "Overvalued" if (valuation_score or 50) < 30 else "Fair",
            "metrics": {"pe": pe, "forward_pe": fwd_pe, "price_to_book": pbv,
                        "price_to_sales": psales, "peg": peg},
            "formula": (
                "Lower multiples = cheaper. Composite of P/E, P/B and P/S. "
                "P/E 50→0pts, P/E 10→100pts; P/B 10→0pts, P/B 1→100pts; "
                "P/S 20→0pts, P/S 1→100pts. Score = average of available legs."
            ),
        },
        "quality": {
            "score": quality_score,
            "label": _label_0_100(quality_score),
            "metrics": {"roe_pct": _pct(roe), "roa_pct": _pct(roa),
                        "profit_margin_pct": _pct(profit_margin),
                        "operating_margin_pct": _pct(op_margin)},
            "formula": (
                "How efficiently the business turns capital into profit. "
                "ROE 0→0pts, ROE 30%+→100pts; ROA 0→0pts, ROA 15%+→100pts; "
                "profit margin 0→0pts, 25%+→100pts; operating margin 0→0pts, "
                "30%+→100pts. Score = average."
            ),
        },
        "growth_stability": {
            "score": growth_score,
            "label": _label_0_100(growth_score),
            "metrics": {"revenue_growth_pct": _pct(rev_growth),
                        "earnings_growth_pct": _pct(earn_growth)},
            "formula": (
                "Year-over-year revenue + earnings growth. "
                "Revenue YoY 0→0pts, 30%+→100pts; earnings YoY 0→0pts, "
                "50%+→100pts. Score = average."
            ),
        },
        "financial_health": {
            "score": health_score,
            "label": "Healthy" if (health_score or 0) >= 65 else
                     "Less Healthy" if (health_score or 50) < 40 else "Average",
            "metrics": {"debt_to_equity": debt_to_equity, "current_ratio": current_ratio,
                        "free_cashflow": fcf, "total_cash": total_cash},
            "formula": (
                "Balance-sheet resilience. Debt/Equity 200%→0pts, 0→100pts; "
                "current ratio 1.0→30pts, 2.5+→100pts; positive free cashflow "
                "→80pts (negative→20); positive cash buffer →70pts. "
                "Score = average."
            ),
        },
    }


def _pct(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return round(float(v) * 100, 2)
    except Exception:
        return None


def _empty_fundamentals() -> dict:
    base = {"score": None, "label": "—", "metrics": {}}
    return {
        "available": False,
        "valuation": base, "quality": base,
        "growth_stability": base, "financial_health": base,
    }


# ---------------------------------------------------------------------------
# 2. Technical sentiment
# ---------------------------------------------------------------------------
def technical_panel(symbol: str) -> dict:
    """Trading-Central-style three-horizon sentiment.

    Short-term  (2-6 weeks): 21-day return + price vs 10/20-day MA
    Mid-term    (6 weeks-9 months): stage classifier + 50-day MA + 6-month return
    Long-term   (9 months-2 years): 200-day trend + RS-style 12-month return
    """
    try:
        from . import prices, stage as stage_mod
    except Exception:
        return _empty_technical()
    df = prices.load_prices(symbol)
    if df is None or len(df) < 252:
        return _empty_technical()

    close = df["close"]

    def _ret(days: int) -> Optional[float]:
        if len(close) < days + 1:
            return None
        return float(close.iloc[-1] / close.iloc[-days - 1] - 1.0)

    def _ma(days: int) -> Optional[float]:
        if len(close) < days:
            return None
        return float(close.iloc[-days:].mean())

    px = float(close.iloc[-1])
    r_21 = _ret(21)
    r_63 = _ret(63)
    r_126 = _ret(126)
    r_252 = _ret(252)
    ma10 = _ma(10)
    ma20 = _ma(20)
    ma50 = _ma(50)
    ma200 = _ma(200)
    ma200_30d_ago = float(close.iloc[-30:-1].rolling(200).mean().iloc[-1]) if len(close) >= 230 else None

    stg = stage_mod.classify(df) or {}

    # Short-term score (0-100)
    short_parts: list[int] = []
    if r_21 is not None:
        short_parts.append(_scale_linear(r_21 * 100, -10, 10) or 50)
    if ma10 and ma20:
        short_parts.append(80 if px > ma10 > ma20 else 60 if px > ma20 else 30)
    short_score = round(sum(short_parts) / len(short_parts)) if short_parts else None

    # Mid-term
    mid_parts: list[int] = []
    if stg.get("stage") == 2:
        mid_parts.append(85)
    elif stg.get("stage") == 1:
        mid_parts.append(50)
    elif stg.get("stage") in (3, 4):
        mid_parts.append(20)
    if ma50 and ma200:
        mid_parts.append(80 if px > ma50 > ma200 else 50 if px > ma50 else 25)
    if r_126 is not None:
        mid_parts.append(_scale_linear(r_126 * 100, -20, 30) or 50)
    mid_score = round(sum(mid_parts) / len(mid_parts)) if mid_parts else None

    # Long-term
    long_parts: list[int] = []
    if r_252 is not None:
        long_parts.append(_scale_linear(r_252 * 100, -30, 50) or 50)
    if ma200 is not None and ma200_30d_ago is not None:
        long_parts.append(75 if ma200 > ma200_30d_ago else 30)
    if px and ma200:
        long_parts.append(70 if px > ma200 else 30)
    long_score = round(sum(long_parts) / len(long_parts)) if long_parts else None

    return {
        "available": True,
        "short_term": {
            "horizon": "2-6 weeks",
            "score": short_score,
            "label": _label_0_100(short_score),
            "metrics": {"return_21d_pct": _round(r_21 * 100 if r_21 is not None else None),
                        "ma10": _round(ma10), "ma20": _round(ma20)},
        },
        "mid_term": {
            "horizon": "6 weeks – 9 months",
            "score": mid_score,
            "label": _label_0_100(mid_score),
            "metrics": {"stage": stg.get("stage"), "stage_label": stg.get("label"),
                        "return_6m_pct": _round(r_126 * 100 if r_126 is not None else None),
                        "ma50": _round(ma50)},
        },
        "long_term": {
            "horizon": "9 months – 2 years",
            "score": long_score,
            "label": _label_0_100(long_score),
            "metrics": {"return_12m_pct": _round(r_252 * 100 if r_252 is not None else None),
                        "ma200": _round(ma200),
                        "ma200_rising": (ma200 is not None and ma200_30d_ago is not None and ma200 > ma200_30d_ago)},
        },
    }


def _round(v: Optional[float], digits: int = 2):
    if v is None:
        return None
    return round(float(v), digits)


def _empty_technical() -> dict:
    base = {"horizon": "", "score": None, "label": "—", "metrics": {}}
    return {"available": False, "short_term": base, "mid_term": base, "long_term": base}


# ---------------------------------------------------------------------------
# 3. ESG
# ---------------------------------------------------------------------------
def esg_panel(symbol: str) -> dict:
    """MSCI-style ESG via yfinance Sustainalytics fields.

    yfinance returns Sustainalytics risk scores (lower=better) in `.sustainability`.
    We invert them to a 0-10 quality score (higher=better) and bucket into
    Laggard / Average / Leader bands matching MSCI's UI.
    """
    try:
        import yfinance as yf
        df = yf.Ticker(symbol).sustainability
    except Exception as exc:
        log.warning("yfinance ESG failed for %s: %s", symbol, exc)
        return {"available": False}

    if df is None or df.empty:
        return {"available": False}

    try:
        col = df.columns[0]
        s = df[col]

        def _g(key: str) -> Optional[float]:
            try:
                if key in s.index:
                    v = s.loc[key]
                    return float(v) if v is not None else None
            except Exception:
                pass
            return None

        # Sustainalytics risk scores: 0-100, lower = better risk profile.
        # Map to a 0-10 "quality" score so higher = better (MSCI convention).
        total_risk = _g("totalEsg")
        env_risk = _g("environmentScore")
        soc_risk = _g("socialScore")
        gov_risk = _g("governanceScore")
        peer_pct = _g("percentile")  # percentile in industry (lower = better risk)
        peer_count = _g("peerCount")

        def _to_quality(risk: Optional[float]) -> Optional[float]:
            # 0 risk → 10 (Leader), 40+ risk → 0 (Laggard)
            if risk is None:
                return None
            v = 10.0 - (risk / 4.0)
            return round(max(0.0, min(10.0, v)), 1)

        def _to_quartile(percentile: Optional[float]) -> Optional[int]:
            # peer percentile is "lower better" — convert to quartile (1=worst, 4=best)
            if percentile is None:
                return None
            inv = 100 - percentile
            if inv >= 75:
                return 4
            if inv >= 50:
                return 3
            if inv >= 25:
                return 2
            return 1

        return {
            "available": True,
            "provider": "Sustainalytics (via yfinance)",
            "overall": {"score": _to_quality(total_risk), "label": _esg_label(_to_quality(total_risk)),
                        "industry_quartile": _to_quartile(peer_pct), "peer_count": peer_count},
            "environment": {"score": _to_quality(env_risk), "label": _esg_label(_to_quality(env_risk))},
            "social": {"score": _to_quality(soc_risk), "label": _esg_label(_to_quality(soc_risk))},
            "governance": {"score": _to_quality(gov_risk), "label": _esg_label(_to_quality(gov_risk))},
        }
    except Exception as exc:
        log.warning("ESG parse failed for %s: %s", symbol, exc)
        return {"available": False}


# ---------------------------------------------------------------------------
# 4. Analyst consensus (Equity Summary Score-like)
# ---------------------------------------------------------------------------
def analyst_panel(symbol: str) -> dict:
    """Composite analyst rating with 1-year history.

    Uses Finnhub's `/stock/recommendation` (free tier returns the last 12
    monthly buckets of strongBuy/buy/hold/sell/strongSell counts) plus
    `/stock/price-target` (mean/median/high/low/n).

    Synthesizes:
      - score_0_10:  weighted bullish % → 0-10 (LSEG StarMine-style)
      - label:       Very Bullish / Bullish / Neutral / Bearish / Very Bearish
      - distribution: latest month bucket counts
      - history:     last 12 months as a list (for the timeline chart)
      - target:      mean/median/high/low/n
    """
    if not FINNHUB_API_KEY:
        return {"available": False, "reason": "FINNHUB_API_KEY not set"}

    try:
        with httpx.Client(timeout=10) as client:
            rec = client.get(
                "https://finnhub.io/api/v1/stock/recommendation",
                params={"symbol": symbol.upper(), "token": FINNHUB_API_KEY},
            )
            tgt = client.get(
                "https://finnhub.io/api/v1/stock/price-target",
                params={"symbol": symbol.upper(), "token": FINNHUB_API_KEY},
            )
    except Exception as exc:
        log.warning("analyst fetch failed for %s: %s", symbol, exc)
        return {"available": False, "reason": str(exc)}

    if rec.status_code != 200:
        return {"available": False, "reason": f"finnhub {rec.status_code}"}

    rec_data = rec.json() or []
    tgt_data = tgt.json() if tgt.status_code == 200 else {}

    if not rec_data:
        return {"available": False, "reason": "no analyst data"}

    # Finnhub returns most recent first
    latest = rec_data[0]
    sb = int(latest.get("strongBuy") or 0)
    b = int(latest.get("buy") or 0)
    h = int(latest.get("hold") or 0)
    s = int(latest.get("sell") or 0)
    ss = int(latest.get("strongSell") or 0)
    total = sb + b + h + s + ss

    # Weighted bullish: strongBuy=2, buy=1, hold=0, sell=-1, strongSell=-2
    if total > 0:
        weighted = (sb * 2 + b * 1 - s * 1 - ss * 2) / total  # range -2..+2
        score_0_10 = round((weighted + 2) / 4 * 10, 1)        # 0..10
    else:
        weighted = None
        score_0_10 = None

    # Label like LSEG: 9.5+ Very Bullish, 7+ Bullish, 4-7 Neutral, 2-4 Bearish, <2 Very Bearish
    if score_0_10 is None:
        label = "—"
    elif score_0_10 >= 8:
        label = "Very Bullish"
    elif score_0_10 >= 6.5:
        label = "Bullish"
    elif score_0_10 >= 4:
        label = "Neutral"
    elif score_0_10 >= 2:
        label = "Bearish"
    else:
        label = "Very Bearish"

    history = []
    for bucket in rec_data:
        sb_ = int(bucket.get("strongBuy") or 0)
        b_  = int(bucket.get("buy") or 0)
        h_  = int(bucket.get("hold") or 0)
        s_  = int(bucket.get("sell") or 0)
        ss_ = int(bucket.get("strongSell") or 0)
        tot = sb_ + b_ + h_ + s_ + ss_
        w = ((sb_ * 2 + b_ - s_ - ss_ * 2) / tot) if tot > 0 else None
        score = round((w + 2) / 4 * 10, 1) if w is not None else None
        history.append({
            "period": bucket.get("period"),
            "strongBuy": sb_, "buy": b_, "hold": h_, "sell": s_, "strongSell": ss_,
            "total": tot,
            "score": score,
        })
    # Order chronologically for the chart
    history.sort(key=lambda x: x["period"] or "")

    return {
        "available": True,
        "provider": "Finnhub (consolidated)",
        "score_0_10": score_0_10,
        "label": label,
        "firms_consolidated": total,
        "distribution": {
            "strongBuy": sb, "buy": b, "hold": h, "sell": s, "strongSell": ss,
            "bullish_pct": round((sb + b) / total * 100, 1) if total else None,
        },
        "target": {
            "mean": tgt_data.get("targetMean"),
            "median": tgt_data.get("targetMedian"),
            "high": tgt_data.get("targetHigh"),
            "low": tgt_data.get("targetLow"),
            "analyst_count": tgt_data.get("numberOfAnalysts"),
        },
        "history": history,
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def analysis_for(symbol: str) -> dict:
    """Return all four panels for a symbol, cached 60 min in Mongo."""
    sym = symbol.upper()
    cached = _cache_get(sym)
    if cached is not None:
        cached["cached"] = True
        return cached

    payload = {
        "symbol": sym,
        "fetched_at": int(time.time()),
        "fetched_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "fundamental": fundamental_panel(sym),
        "technical": technical_panel(sym),
        "esg": esg_panel(sym),
        "analyst": analyst_panel(sym),
        "cached": False,
    }
    _cache_put(sym, payload)
    return payload
