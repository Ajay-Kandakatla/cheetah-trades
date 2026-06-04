"""Portfolio Drop-Attribution — is a holding's move driven by the MARKET, its
SECTOR, or the STOCK itself?

Plain idea (CAPM decomposition): a stock's move is partly "the whole market
moved" and partly "this company specifically." We measure how much of the move
each benchmark explains:

    expected_from_market = beta_market × market_move      (SPY)
    expected_from_sector = beta_sector × sector_move      (sector ETF, e.g. XLK)
    residual (idiosyncratic) = actual_move − expected_from_sector

Verdict (works for drops AND rallies — it's signed):
    🌍 Macro          market explains ≥60% of the move
    🏭 Sector         sector (not the broad market) explains ≥60%
    🎯 Stock-specific neither does — the residual is the story, go find the news

Honest limits (this is a real-money tool): beta drifts over time; single-day
splits are noisy; a non-zero residual means "not explained by SPY/sector," NOT
"confirmed news." It tells you WHERE to look, not the reason.

Reuses sepa.ravi._beta + sepa.prices; no new data source.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from sepa import prices

log = logging.getLogger("portfolio.drop_attribution")


def _beta(stock_lr: "pd.Series", bench_lr: "pd.Series", lookback: int):
    """Date-aligned beta over the last `lookback` common bars. Inlined here after
    sepa.ravi dropped its high-beta screen (commit 9040264) — the import was
    broken, which 500'd drop-attribution + the portfolio diagnosis. Verbatim from
    the original sepa.ravi._beta."""
    j = pd.concat([stock_lr.rename("s"), bench_lr.rename("b")], axis=1, join="inner").dropna()
    if len(j) < lookback:
        return None
    w = j.iloc[-lookback:]
    s, b = w["s"], w["b"]
    var_b = float(((b - b.mean()) ** 2).sum() / lookback)
    if var_b == 0:
        return None
    cov = float(((s - s.mean()) * (b - b.mean())).sum() / lookback)
    return cov / var_b

MARKET_ETF = "SPY"
FALLBACK_SECTOR_ETF = "QQQ"   # when we can't determine a stock's sector
BETA_LOOKBACK = 60
EXPLAINED_THRESHOLD = 0.60    # ≥60% explained by one factor → that's the verdict


def _notable_threshold(window_days: int) -> float:
    """Below this |move| the attribution is just noise — don't force a verdict.
    ~1.5% for a day, scaling up with the window."""
    return max(1.5, window_days * 0.7)

# yfinance GICS sector string → SPDR sector ETF.
SECTOR_ETF = {
    "Technology":             "XLK",
    "Financial Services":     "XLF",
    "Financial":              "XLF",
    "Healthcare":             "XLV",
    "Consumer Cyclical":      "XLY",
    "Consumer Defensive":     "XLP",
    "Energy":                 "XLE",
    "Industrials":            "XLI",
    "Basic Materials":        "XLB",
    "Utilities":              "XLU",
    "Real Estate":            "XLRE",
    "Communication Services": "XLC",
}


_CASH_SYMS = {"CASH", "SPAXX", "FDRXX", "FZFXX", "FNSXX", "FCASH", "SPRXX"}


def is_individual_stock(symbol: str) -> bool:
    """True only for individual equities — excludes mutual funds, ETFs, CUSIP
    fund holdings, and cash. The macro/sector attribution is meaningless for an
    index/bond fund, so the portfolio analysis only runs on real stocks.

      ARM/BB/IONQ → True;  FTIHX/FXNAX (5-letter ·X mutual funds) → False;
      09260L455 (CUSIP target-date fund) → False;  cash/money-market → False.
    """
    s = (symbol or "").upper().strip()
    if not s or s in _CASH_SYMS or "CASH" in s:
        return False
    if len(s) == 9 and any(c.isdigit() for c in s):     # CUSIP, not a ticker
        return False
    if len(s) == 5 and s.isalpha() and s.endswith("X"):  # US mutual fund convention
        return False
    try:
        from sepa import etf_info
        d = etf_info.etf_data_for(s)
        if d and d.get("is_etf"):                        # ETFs / yfinance-detected funds
            return False
    except Exception:
        pass
    return True


def _sector_etf_for(symbol: str) -> tuple[str, Optional[str]]:
    """Return (sector_etf, sector_name) for a stock. Uses the cached company
    sector; falls back to QQQ when unknown."""
    try:
        from companies import store as company_store
        sector = (company_store.get(symbol) or {}).get("sector")
    except Exception as exc:
        log.debug("sector lookup failed for %s: %s", symbol, exc)
        sector = None
    return SECTOR_ETF.get(sector or "", FALLBACK_SECTOR_ETF), sector


def _ret_pct(df, n: int) -> Optional[float]:
    if df is None or len(df) < n + 1:
        return None
    a, b = float(df["close"].iloc[-1]), float(df["close"].iloc[-1 - n])
    if b <= 0:
        return None
    return (a / b - 1) * 100


def _explained_fraction(actual: Optional[float], expected: float) -> float:
    """Fraction of `actual` that `expected` accounts for, clamped to [0,1].
    Opposite-sign (e.g. stock down while the benchmark predicts up) → 0."""
    if actual is None or abs(actual) < 1e-9:
        return 0.0
    return max(0.0, min(1.0, expected / actual))


def attribute(symbol: str, window_days: int = 5,
              beta_lookback: int = BETA_LOOKBACK) -> Optional[dict]:
    """Decompose one symbol's `window_days` move into market / sector / stock."""
    df = prices.load_prices(symbol)
    spy = prices.load_prices(MARKET_ETF)
    if df is None or spy is None or len(df) < beta_lookback + 2:
        return None
    sector_etf, sector_name = _sector_etf_for(symbol)
    sec_df = prices.load_prices(sector_etf)

    r = _ret_pct(df, window_days)
    mkt = _ret_pct(spy, window_days)
    sec = _ret_pct(sec_df, window_days) if sec_df is not None else None
    if r is None or mkt is None:
        return None

    slr = np.log(df["close"]).diff()
    beta_mkt = _beta(slr, np.log(spy["close"]).diff(), beta_lookback)
    beta_sec = _beta(slr, np.log(sec_df["close"]).diff(), beta_lookback) if sec_df is not None else None

    exp_mkt = (beta_mkt if beta_mkt is not None else 1.0) * mkt
    exp_sec = (beta_sec if beta_sec is not None else 1.0) * sec if sec is not None else None

    frac_mkt = _explained_fraction(r, exp_mkt)
    frac_sec = _explained_fraction(r, exp_sec) if exp_sec is not None else 0.0
    idiosyncratic = round((1.0 - max(frac_mkt, frac_sec)) * 100, 0)

    notable = abs(r) >= _notable_threshold(window_days)
    if not notable:
        verdict, conf = "quiet", 1.0          # move too small to attribute
    elif frac_mkt >= EXPLAINED_THRESHOLD:
        verdict, conf = "macro", frac_mkt
    elif frac_sec >= EXPLAINED_THRESHOLD:
        verdict, conf = "sector", frac_sec
    else:
        verdict, conf = "stock", 1.0 - max(frac_mkt, frac_sec)

    return {
        "symbol": symbol,
        "window_days": window_days,
        "move_pct": round(r, 2),
        "notable": notable,
        "market_move_pct": round(mkt, 2),
        "sector_move_pct": round(sec, 2) if sec is not None else None,
        "sector_etf": sector_etf,
        "sector_name": sector_name,
        "beta_market": round(beta_mkt, 2) if beta_mkt is not None else None,
        "beta_sector": round(beta_sec, 2) if beta_sec is not None else None,
        "expected_from_market_pct": round(exp_mkt, 2),
        "expected_from_sector_pct": round(exp_sec, 2) if exp_sec is not None else None,
        "explained_by_market_pct": round(frac_mkt * 100, 0),
        "explained_by_sector_pct": round(frac_sec * 100, 0),
        "idiosyncratic_pct": idiosyncratic,
        "verdict": verdict,                 # macro | sector | stock
        "confidence": round(conf, 2),
        "summary": _summary(symbol, verdict, r, mkt, sec, beta_mkt, frac_mkt, frac_sec, idiosyncratic),
    }


def _summary(sym, verdict, r, mkt, sec, beta_mkt, frac_mkt, frac_sec, idio) -> str:
    move = f"{sym} {r:+.1f}%"
    if verdict == "quiet":
        return f"{move}: too small to attribute — noise."
    if verdict == "macro":
        return f"{move}: market {mkt:+.1f}% × β{(beta_mkt or 1):.1f} explains ~{frac_mkt*100:.0f}% — ride it out, it's the market."
    if verdict == "sector":
        return f"{move}: its sector ({sec:+.1f}%) explains ~{frac_sec*100:.0f}% but the broad market didn't — it's sector rotation."
    return f"{move}: market/sector only explain ~{max(frac_mkt, frac_sec)*100:.0f}% — ~{idio:.0f}% is {sym} itself. Check the news."


def attribute_portfolio(user_email: str, window_days: int = 5) -> dict:
    """Run attribution for every holding in a user's portfolio."""
    from portfolio import store as pstore
    holdings = pstore.list_holdings(user_email)
    syms = []
    seen = set()
    for h in holdings:
        t = (h.get("ticker") or "").upper()
        if t and t not in seen and is_individual_stock(t):   # stocks only — skip funds/cash
            seen.add(t)
            syms.append(t)
    rows = [a for s in syms if (a := attribute(s, window_days)) is not None]
    rows.sort(key=lambda x: x["move_pct"])   # worst movers first
    counts = {
        "macro":  sum(1 for r in rows if r["verdict"] == "macro"),
        "sector": sum(1 for r in rows if r["verdict"] == "sector"),
        "stock":  sum(1 for r in rows if r["verdict"] == "stock"),
    }
    return {"rows": rows, "counts": counts, "n": len(rows), "window_days": window_days}


# --------------------------------------------------------------------------
# Beta profile — "what to expect on a down day" per holding + blended.
# Reuses sepa.ravi._beta. Beta = how much a stock moves per 1% market move.
# --------------------------------------------------------------------------
TECH_ETF = "QQQ"


def _round2(v: Optional[float]) -> Optional[float]:
    return round(float(v), 2) if v is not None else None


def _beta_profile(symbol: str, market_lr, tech_lr) -> Optional[dict]:
    df = prices.load_prices(symbol)
    if df is None or len(df) < 70:
        return None
    lr = np.log(df["close"]).diff()
    return {
        "beta_spy_60": _round2(_beta(lr, market_lr, 60)),    # recent sensitivity
        "beta_spy_1y": _round2(_beta(lr, market_lr, 252)),   # steadier
        "beta_qqx_60": _round2(_beta(lr, tech_lr, 60)),
        "last_price":  round(float(df["close"].iloc[-1]), 2),
    }


def portfolio_betas(user_email: str) -> dict:
    """Per-holding beta (vs SPY 60d/1y + QQX) + expected move on a -1%/-3% day,
    plus a $-weighted blended portfolio beta. Individual stocks only."""
    from portfolio import store as pstore
    from sepa import company_names

    spy = prices.load_prices(MARKET_ETF)
    qqq = prices.load_prices(TECH_ETF)
    if spy is None:
        return {"rows": [], "n": 0, "total_value": 0,
                "blended_beta_60d": None, "blended_beta_1y": None}
    mlr = np.log(spy["close"]).diff()
    tlr = np.log(qqq["close"]).diff() if qqq is not None else mlr

    rows: list[dict] = []
    total = 0.0
    seen = set()
    for h in pstore.list_holdings(user_email):
        sym = (h.get("ticker") or "").upper()
        if not sym or sym in seen or not is_individual_stock(sym):
            continue
        seen.add(sym)
        prof = _beta_profile(sym, mlr, tlr)
        if prof is None:
            continue
        shares = float(h.get("shares") or 0)
        value = shares * (prof["last_price"] or 0)
        b60 = prof["beta_spy_60"]
        rows.append({
            "symbol": sym,
            "name": company_names.name_for(sym) or sym,
            **prof,
            "shares": shares,
            "market_value": round(value),
            "expect_down_1pct": _round2(-b60) if b60 is not None else None,
            "expect_down_3pct": _round2(-b60 * 3) if b60 is not None else None,
        })
        total += value

    rows.sort(key=lambda r: -(r["beta_spy_60"] or 0))

    def _blended(key: str) -> Optional[float]:
        pairs = [(r["market_value"], r[key]) for r in rows
                 if r.get(key) is not None and r.get("market_value")]
        tv = sum(v for v, _ in pairs)
        return round(sum(v * b for v, b in pairs) / tv, 2) if tv else None

    return {
        "rows": rows,
        "n": len(rows),
        "total_value": round(total),
        "blended_beta_60d": _blended("beta_spy_60"),
        "blended_beta_1y": _blended("beta_spy_1y"),
    }
