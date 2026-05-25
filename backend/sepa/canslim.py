"""CANSLIM-style fundamentals layer.

Minervini's "S" (Specific entry-point setups built on Strong fundamentals)
explicitly requires earnings acceleration and institutional sponsorship,
not just price action. This module emits the C/A/I checks:

  C — Current Q EPS growth ≥ 25% Y/Y (canonical O'Neil threshold)
  A — Annual EPS growth ≥ 25% Y/Y trailing 3 years (canonical CANSLIM "A")
  I — Institutional ownership 40-80% (some sponsorship, not over-owned)

Note: these thresholds are O'Neil/IBD canonical, NOT directly from Minervini's
book. They serve as a fundamentals filter complementing SEPA's price action.

Data sources — feature-flag controlled by ``CANSLIM_SOURCE`` env var:

  * "hybrid"   (default, 2026-05-24+) — C and A from Massive
    /vX/reference/financials (faster, complete diluted-EPS history);
    I from yfinance (Polygon doesn't expose institutional ownership %).
    Falls back to full-yfinance when Massive returns empty or errors.

  * "massive"  — strict; uses Massive for C+A and yfinance for I.
    Fails C/A with None if Massive has no data (no yfinance fallback).
    Useful for testing the Massive path in isolation.

  * "yfinance" — legacy path. Pure yfinance. Useful for parity tests.

Output contract is identical across paths — see ``fundamentals_for()``.

Why hybrid:
  • Massive provides clean SEC-filing-backed diluted_earnings_per_share
    with quarterly + annual timeframes; yfinance scrapes Yahoo and
    occasionally returns stale or missing quarters.
  • yfinance's heldPercentInstitutions doesn't have a Massive equivalent
    on the Options Advanced plan, so we keep yfinance for I.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

log = logging.getLogger("sepa.canslim")


CANSLIM_SOURCE = os.getenv("CANSLIM_SOURCE", "hybrid").lower()


# ---------- Public entry point ------------------------------------------------

def fundamentals_for(symbol: str) -> dict:
    """Return CANSLIM-style fundamentals snapshot for a symbol.

    Output shape (all fields nullable — preserve across data sources):
        {
            "q_eps_growth_pct":   float | None,    # Most recent Q vs same Q prior yr
            "y_eps_growth_pct":   float | None,    # Trailing 3yr avg annual EPS growth
            "rev_growth_q_pct":   float | None,    # Revenue Q growth (bonus)
            "inst_ownership_pct": float | None,
            "checks": {
                "c_strong_q_eps":   bool,   # ≥ 25%
                "a_strong_y_eps":   bool,   # ≥ 25%
                "i_institutional":  bool,   # 40-80%
            },
            "passed":  int,    # /3
            "_source": str,    # 'massive' | 'yfinance' | 'hybrid' | 'empty'
        }
    """
    if CANSLIM_SOURCE == "yfinance":
        return _from_yfinance(symbol)
    if CANSLIM_SOURCE == "massive":
        return _from_massive(symbol, strict=True)
    # default: hybrid — Massive for C/A, yfinance for I, with full-yfinance
    # fallback when Massive returns nothing.
    return _from_hybrid(symbol)


# ---------- Source: hybrid (default) -----------------------------------------

def _from_hybrid(symbol: str) -> dict:
    """Massive for EPS/revenue, yfinance for institutional ownership.

    Falls back to full yfinance if Massive returns no data (avoids
    breaking on tickers without complete SEC filings on Polygon).
    """
    m = _fetch_massive_financials(symbol)
    if not m or (m.get("q_eps_growth_pct") is None and m.get("y_eps_growth_pct") is None):
        # Massive had nothing usable — fall back to pure yfinance so we
        # never lose CANSLIM data we previously had.
        result = _from_yfinance(symbol)
        result["_source"] = "yfinance"  # fallback path took over
        return result

    # Got EPS data from Massive — now pull just the institutional ownership
    # from yfinance (cheaper than fetching the whole income statement).
    inst = _inst_ownership_yfinance(symbol)

    checks = {
        "c_strong_q_eps":  (m["q_eps_growth_pct"] is not None and m["q_eps_growth_pct"] >= 25),
        "a_strong_y_eps":  (m["y_eps_growth_pct"] is not None and m["y_eps_growth_pct"] >= 25),
        "i_institutional": (inst is not None and 40 <= inst <= 80),
    }
    return {
        "q_eps_growth_pct":   m.get("q_eps_growth_pct"),
        "y_eps_growth_pct":   m.get("y_eps_growth_pct"),
        "rev_growth_q_pct":   m.get("rev_growth_q_pct"),
        "inst_ownership_pct": inst,
        "checks":  checks,
        "passed":  sum(1 for v in checks.values() if v),
        "_source": "hybrid",
    }


# ---------- Source: Massive (strict) -----------------------------------------

# Process-level lazy-disable mirrors the pattern in options/soir.py — once
# we see 401/403/429 on the financials endpoint we stop hammering it for
# the rest of this scan run.
_massive_financials_disabled = False


def _fetch_massive_financials(symbol: str) -> Optional[dict]:
    """Pull last 6 quarterly + 4 annual reports from Massive. Computes the
    same q_eps_growth / y_eps_growth / rev_growth_q numbers yfinance does.

    Returns dict with the three growth metrics, or None on failure.
    """
    global _massive_financials_disabled
    if _massive_financials_disabled:
        return None
    api_key = os.getenv("MASSIVE_API_KEY")
    if not api_key:
        return None

    try:
        import requests
    except ImportError:
        log.warning("canslim.massive: requests not installed")
        return None

    sess = requests.Session()
    base = "https://api.massive.com/vX/reference/financials"

    try:
        # Quarterly — need 5 quarters for YoY comparison (Q vs Q-4)
        rq = sess.get(base, params={
            "ticker":    symbol.upper(),
            "limit":     6,
            "timeframe": "quarterly",
            "apiKey":    api_key,
        }, timeout=8)
        # Annual — need 4 years for trailing 3yr average growth
        ra = sess.get(base, params={
            "ticker":    symbol.upper(),
            "limit":     4,
            "timeframe": "annual",
            "apiKey":    api_key,
        }, timeout=8)
    except Exception as exc:
        log.warning("canslim.massive: fetch failed for %s: %s", symbol, exc)
        return None

    if rq.status_code in (401, 403):
        if not _massive_financials_disabled:
            log.warning("canslim.massive: %s returned %s — plan doesn't include "
                        "financials. Disabling Massive financials for this run.",
                        symbol, rq.status_code)
            _massive_financials_disabled = True
        return None
    if rq.status_code != 200 or ra.status_code != 200:
        log.debug("canslim.massive: %s quarterly=%s annual=%s",
                  symbol, rq.status_code, ra.status_code)
        return None

    q_results = (rq.json() or {}).get("results") or []
    a_results = (ra.json() or {}).get("results") or []

    return {
        "q_eps_growth_pct": _compute_q_eps_growth(q_results),
        "y_eps_growth_pct": _compute_y_eps_growth(a_results),
        "rev_growth_q_pct": _compute_q_rev_growth(q_results),
    }


def _income_value(report: dict, key: str) -> Optional[float]:
    """Pull a value from a Massive financials report safely.

    Massive structure: {'financials': {'income_statement': {'<key>': {'value': X, 'unit': 'USD'}}}}
    """
    try:
        v = ((report.get("financials") or {})
                  .get("income_statement") or {}).get(key, {}).get("value")
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _compute_q_eps_growth(quarterly: list[dict]) -> Optional[float]:
    """Q EPS growth YoY: latest Q vs same Q prior year (index 0 vs index 4).

    Massive returns newest first when ordered by filing date, same as yfinance.
    """
    if len(quarterly) < 5:
        return None
    latest = _income_value(quarterly[0], "diluted_earnings_per_share")
    prior_yr = _income_value(quarterly[4], "diluted_earnings_per_share")
    if latest is None or prior_yr is None or prior_yr == 0:
        return None
    return round((latest - prior_yr) / abs(prior_yr) * 100, 2)


def _compute_y_eps_growth(annual: list[dict]) -> Optional[float]:
    """3yr-trailing average annual EPS growth — same formula as the
    yfinance path so the gate threshold stays apples-to-apples."""
    if len(annual) < 4:
        return None
    growths = []
    for i in range(3):
        cur = _income_value(annual[i], "diluted_earnings_per_share")
        prev = _income_value(annual[i + 1], "diluted_earnings_per_share")
        if cur is None or prev is None or prev == 0:
            continue
        growths.append((cur - prev) / abs(prev) * 100)
    return round(sum(growths) / len(growths), 2) if growths else None


def _compute_q_rev_growth(quarterly: list[dict]) -> Optional[float]:
    """Q revenue growth YoY — bonus metric, not gated."""
    if len(quarterly) < 5:
        return None
    latest = _income_value(quarterly[0], "revenues")
    prior_yr = _income_value(quarterly[4], "revenues")
    if latest is None or prior_yr is None or prior_yr == 0:
        return None
    return round((latest - prior_yr) / abs(prior_yr) * 100, 2)


def _from_massive(symbol: str, strict: bool = True) -> dict:
    """Strict-massive entry point. C+A come from Massive; I still from
    yfinance because Polygon doesn't expose institutional ownership %.
    No fallback to yfinance for C+A when `strict=True`."""
    m = _fetch_massive_financials(symbol) or {}
    inst = _inst_ownership_yfinance(symbol)

    q = m.get("q_eps_growth_pct")
    y = m.get("y_eps_growth_pct")
    checks = {
        "c_strong_q_eps":  (q is not None and q >= 25),
        "a_strong_y_eps":  (y is not None and y >= 25),
        "i_institutional": (inst is not None and 40 <= inst <= 80),
    }
    return {
        "q_eps_growth_pct":   q,
        "y_eps_growth_pct":   y,
        "rev_growth_q_pct":   m.get("rev_growth_q_pct"),
        "inst_ownership_pct": inst,
        "checks":  checks,
        "passed":  sum(1 for v in checks.values() if v),
        "_source": "massive",
    }


# ---------- Source: yfinance (legacy / fallback) -----------------------------

def _from_yfinance(symbol: str) -> dict:
    """Original yfinance path. Used directly when CANSLIM_SOURCE=yfinance
    and as the fallback when hybrid's Massive call fails."""
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
    except Exception as exc:
        log.warning("yfinance import failed: %s", exc)
        return _empty()

    q_eps = _q_eps_growth_yf(t)
    y_eps = _y_eps_growth_yf(t)
    rev_q = _rev_q_growth_yf(t)
    inst = _inst_ownership_yf(t)

    checks = {
        "c_strong_q_eps":  (q_eps is not None and q_eps >= 25),
        "a_strong_y_eps":  (y_eps is not None and y_eps >= 25),
        "i_institutional": (inst is not None and 40 <= inst <= 80),
    }
    return {
        "q_eps_growth_pct":   q_eps,
        "y_eps_growth_pct":   y_eps,
        "rev_growth_q_pct":   rev_q,
        "inst_ownership_pct": inst,
        "checks":  checks,
        "passed":  sum(1 for v in checks.values() if v),
        "_source": "yfinance",
    }


def _empty() -> dict:
    return {
        "q_eps_growth_pct": None, "y_eps_growth_pct": None,
        "rev_growth_q_pct": None, "inst_ownership_pct": None,
        "checks": {"c_strong_q_eps": False, "a_strong_y_eps": False, "i_institutional": False},
        "passed": 0,
        "_source": "empty",
    }


def _q_eps_growth_yf(t) -> Optional[float]:
    try:
        df = t.quarterly_income_stmt
        if df is None or df.empty or "Diluted EPS" not in df.index:
            return None
        eps = df.loc["Diluted EPS"].dropna()
        if len(eps) < 5:
            return None
        latest = float(eps.iloc[0])
        prior_yr = float(eps.iloc[4])
        if prior_yr == 0:
            return None
        return round((latest - prior_yr) / abs(prior_yr) * 100, 2)
    except Exception:
        return None


def _y_eps_growth_yf(t) -> Optional[float]:
    try:
        df = t.income_stmt
        if df is None or df.empty or "Diluted EPS" not in df.index:
            return None
        eps = df.loc["Diluted EPS"].dropna()
        if len(eps) < 4:
            return None
        growths = []
        for i in range(3):
            cur = float(eps.iloc[i])
            prev = float(eps.iloc[i + 1])
            if prev != 0:
                growths.append((cur - prev) / abs(prev) * 100)
        return round(sum(growths) / len(growths), 2) if growths else None
    except Exception:
        return None


def _rev_q_growth_yf(t) -> Optional[float]:
    try:
        df = t.quarterly_income_stmt
        if df is None or df.empty or "Total Revenue" not in df.index:
            return None
        rev = df.loc["Total Revenue"].dropna()
        if len(rev) < 5:
            return None
        latest = float(rev.iloc[0])
        prior_yr = float(rev.iloc[4])
        if prior_yr == 0:
            return None
        return round((latest - prior_yr) / abs(prior_yr) * 100, 2)
    except Exception:
        return None


def _inst_ownership_yf(t) -> Optional[float]:
    try:
        info = t.info or {}
        held = info.get("heldPercentInstitutions")
        if held is None:
            return None
        return round(float(held) * 100, 2)
    except Exception:
        return None


def _inst_ownership_yfinance(symbol: str) -> Optional[float]:
    """Thin wrapper so hybrid path can grab institutional ownership without
    constructing a full yfinance Ticker for the (Massive-already-fetched)
    income data. Stays cheap when called per-symbol in the scanner pool."""
    try:
        import yfinance as yf
        return _inst_ownership_yf(yf.Ticker(symbol))
    except Exception as exc:
        log.debug("inst ownership lookup failed for %s: %s", symbol, exc)
        return None
