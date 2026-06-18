"""Beta — a stock's volatility relative to the market (SPY).

    beta = cov(stock daily log-returns, SPY daily log-returns) / var(SPY log-returns)

over the trailing ``BETA_LOOKBACK`` (252 ≈ one trading year) common bars. This is
the **canonical app beta** — the same cov/var-of-log-returns formula used by
``portfolio/drop_attribution._beta`` (itself "verbatim from the original
``sepa.ravi._beta``"). One year of daily returns is the conventional window for a
published "beta" figure.

    beta < 1  → LESS volatile than the market (defensive / "low volatility")
    beta ≈ 1  → moves with the market
    beta > 1  → MORE volatile — amplifies market swings

Display-only / informational — never feeds the SEPA score, gates, or verdict.
Soft-fails to ``None`` everywhere (a missing beta must never break the board).
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

log = logging.getLogger("sepa.beta")

MARKET_ETF = "SPY"
BETA_LOOKBACK = 252                       # ≈ 1 trading year of daily bars

_cache: Dict[str, tuple] = {}             # symbol -> (iso_date, beta)
_spy_lr_cache: dict = {"date": None, "lr": None}


def _today_iso() -> str:
    return date.today().isoformat()


def _log_returns(df) -> Optional["pd.Series"]:
    """Daily log returns from a price frame indexed by date (prices.load_prices)."""
    if df is None or "close" not in df or len(df) < 2:
        return None
    c = df["close"].astype(float)
    lr = np.log(c / c.shift(1)).replace([np.inf, -np.inf], np.nan).dropna()
    return lr if len(lr) else None


def _beta(stock_lr: "pd.Series", bench_lr: "pd.Series",
          lookback: int = BETA_LOOKBACK) -> Optional[float]:
    """Date-aligned beta over the last ``lookback`` common bars. Canonical
    cov/var-of-log-returns formula (same as portfolio/drop_attribution._beta)."""
    if stock_lr is None or bench_lr is None:
        return None
    j = pd.concat([stock_lr.rename("s"), bench_lr.rename("b")],
                  axis=1, join="inner").dropna()
    if len(j) < lookback:
        return None
    w = j.iloc[-lookback:]
    s, b = w["s"], w["b"]
    var_b = float(((b - b.mean()) ** 2).sum() / lookback)
    if var_b == 0:
        return None
    cov = float(((s - s.mean()) * (b - b.mean())).sum() / lookback)
    return cov / var_b


def _spy_log_returns():
    """SPY's daily log-return series, loaded once per day."""
    today = _today_iso()
    if _spy_lr_cache["date"] == today and _spy_lr_cache["lr"] is not None:
        return _spy_lr_cache["lr"]
    try:
        from sepa import prices
        lr = _log_returns(prices.load_prices(MARKET_ETF))
    except Exception as exc:                      # noqa: BLE001
        log.debug("beta: SPY load failed: %s", exc)
        lr = None
    _spy_lr_cache.update(date=today, lr=lr)
    return lr


def beta_for(symbol: str, spy_lr=None) -> Optional[float]:
    """1-year daily beta vs SPY for ``symbol`` (2dp). Cached per day; soft-fails
    to ``None``. Pass ``spy_lr`` to avoid reloading SPY in a batch."""
    sym = (symbol or "").upper().strip()
    if not sym:
        return None
    today = _today_iso()
    hit = _cache.get(sym)
    if hit and hit[0] == today:
        return hit[1]
    try:
        from sepa import prices
        if spy_lr is None:
            spy_lr = _spy_log_returns()
        if spy_lr is None:
            return None
        stock_lr = _log_returns(prices.load_prices(sym))
        if stock_lr is None:
            _cache[sym] = (today, None)
            return None
        b = _beta(stock_lr, spy_lr)
        b = round(b, 2) if b is not None else None
        _cache[sym] = (today, b)
        return b
    except Exception as exc:                       # noqa: BLE001
        log.debug("beta_for(%s) failed: %s", sym, exc)
        return None


def betas_for(symbols: List[str]) -> Dict[str, Optional[float]]:
    """Batch beta for many symbols — loads SPY once, threads the per-name reads.
    Returns ``{symbol: beta_or_None}``. Never raises."""
    syms = []
    for s in symbols or []:
        u = (s or "").upper().strip()
        if u and u not in syms:
            syms.append(u)
    spy_lr = _spy_log_returns()
    if spy_lr is None:
        return {s: None for s in syms}

    out: Dict[str, Optional[float]] = {}
    try:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as ex:
            for s, b in ex.map(lambda x: (x, beta_for(x, spy_lr=spy_lr)), syms):
                out[s] = b
    except Exception as exc:                       # noqa: BLE001
        log.debug("betas_for batch failed: %s", exc)
        for s in syms:
            out.setdefault(s, beta_for(s, spy_lr=spy_lr))
    return out
