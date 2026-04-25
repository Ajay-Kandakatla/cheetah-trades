"""CANSLIM-style fundamentals layer.

Minervini's "S" (Specific entry-point setups built on Strong fundamentals)
explicitly requires earnings acceleration and institutional sponsorship,
not just price action. This module pulls fundamentals via yfinance and
emits the C/A/I checks:

  C — Current Q EPS growth ≥ 25% Y/Y (canonical O'Neil threshold)
  A — Annual EPS growth ≥ 25% Y/Y trailing 3 years (canonical CANSLIM "A")
  I — Institutional ownership 40-80% (some sponsorship, not over-owned)

Note: these thresholds are O'Neil/IBD canonical, NOT directly from Minervini's
book. They serve as a fundamentals filter complementing SEPA's price action.

Free-tier safe: uses only yfinance. Returns None / partial when data missing.
"""
from __future__ import annotations

from typing import Optional
import logging

log = logging.getLogger("sepa.canslim")


def fundamentals_for(symbol: str) -> dict:
    """Return CANSLIM-style fundamentals snapshot for a symbol.

    Output shape (all fields nullable):
        {
            "q_eps_growth_pct": float | None,    # Most recent Q vs same Q prior yr
            "y_eps_growth_pct": float | None,    # Trailing 3yr avg annual EPS growth
            "rev_growth_q_pct": float | None,    # Revenue Q growth (bonus)
            "inst_ownership_pct": float | None,
            "checks": {
                "c_strong_q_eps":    bool,   # ≥ 25%
                "a_strong_y_eps":    bool,   # ≥ 25%
                "i_institutional":   bool,   # 40-80%
            },
            "passed": int,  # /3
        }
    """
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
    except Exception as exc:
        log.warning("yfinance import failed: %s", exc)
        return _empty()

    q_eps = _q_eps_growth(t)
    y_eps = _y_eps_growth(t)
    rev_q = _rev_q_growth(t)
    inst = _inst_ownership(t)

    checks = {
        "c_strong_q_eps": (q_eps is not None and q_eps >= 25),
        "a_strong_y_eps": (y_eps is not None and y_eps >= 25),
        "i_institutional": (inst is not None and 40 <= inst <= 80),
    }
    return {
        "q_eps_growth_pct": q_eps,
        "y_eps_growth_pct": y_eps,
        "rev_growth_q_pct": rev_q,
        "inst_ownership_pct": inst,
        "checks": checks,
        "passed": sum(1 for v in checks.values() if v),
    }


def _empty() -> dict:
    return {
        "q_eps_growth_pct": None, "y_eps_growth_pct": None,
        "rev_growth_q_pct": None, "inst_ownership_pct": None,
        "checks": {"c_strong_q_eps": False, "a_strong_y_eps": False, "i_institutional": False},
        "passed": 0,
    }


def _q_eps_growth(t) -> Optional[float]:
    try:
        df = t.quarterly_income_stmt
        if df is None or df.empty or "Diluted EPS" not in df.index:
            return None
        eps = df.loc["Diluted EPS"].dropna()
        if len(eps) < 5:
            return None
        latest = float(eps.iloc[0])
        prior_yr = float(eps.iloc[4])  # 4 quarters back
        if prior_yr == 0:
            return None
        return round((latest - prior_yr) / abs(prior_yr) * 100, 2)
    except Exception:
        return None


def _y_eps_growth(t) -> Optional[float]:
    try:
        df = t.income_stmt
        if df is None or df.empty or "Diluted EPS" not in df.index:
            return None
        eps = df.loc["Diluted EPS"].dropna()
        if len(eps) < 4:
            return None
        # 3-yr CAGR-ish: avg YoY growth over last 3 years
        growths = []
        for i in range(3):
            cur = float(eps.iloc[i])
            prev = float(eps.iloc[i + 1])
            if prev != 0:
                growths.append((cur - prev) / abs(prev) * 100)
        return round(sum(growths) / len(growths), 2) if growths else None
    except Exception:
        return None


def _rev_q_growth(t) -> Optional[float]:
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


def _inst_ownership(t) -> Optional[float]:
    try:
        info = t.info or {}
        held = info.get("heldPercentInstitutions")
        if held is None:
            return None
        return round(float(held) * 100, 2)
    except Exception:
        return None
