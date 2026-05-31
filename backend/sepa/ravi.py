"""Ravi's Strategy — a high-beta + trend screen.

A faithful port of a ThinkOrSwim study (a friend's "HIGH BETA STOCKS SCANNER",
2026-05-31). It is intentionally NOT Minervini — it's a separate setup:

    beta(lookback, vs SPY, on log returns)  >=  min_beta      AND
    close                                   >   SMA(trend_length)

Beta exactly mirrors the ThinkScript:
    rStock = ln(close / close[1]);  rBench = ln(spy / spy[1])
    cov    = mean( (rStock - mean(rStock)) * (rBench - mean(rBench)) )   over lookback
    varB   = mean( (rBench - mean(rBench))^2 )                           over lookback
    beta   = cov / varB
(population moments — divide by lookback, matching the TS Sum(...)/lookback.)

Runs off the cached daily bars (no external calls). Cached 15 min so the page
doesn't recompute the whole universe on every load.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np
import pandas as pd

from .prices import load_prices
from .universe import load_universe
from . import company_names

log = logging.getLogger("sepa.ravi")

_cache: dict = {"ts": 0.0, "key": None, "rows": []}
_CACHE_TTL_SEC = 15 * 60


def _beta(stock_lr: pd.Series, bench_lr: pd.Series, lookback: int) -> Optional[float]:
    """Date-aligned beta over the last `lookback` common bars."""
    j = pd.concat([stock_lr.rename("s"), bench_lr.rename("b")], axis=1,
                  join="inner").dropna()
    if len(j) < lookback:
        return None
    w = j.iloc[-lookback:]
    s, b = w["s"], w["b"]
    var_b = float(((b - b.mean()) ** 2).sum() / lookback)
    if var_b == 0:
        return None
    cov = float(((s - s.mean()) * (b - b.mean())).sum() / lookback)
    return cov / var_b


def scan(min_beta: float = 1.2, lookback: int = 60, trend_length: int = 50,
         require_trending: bool = True, universe_mode: str = "broad",
         min_close: float = 10.0, min_dollar_vol: float = 5_000_000.0) -> list[dict]:
    """Return symbols passing the high-beta + trend screen, sorted by beta."""
    key = (min_beta, lookback, trend_length, require_trending, universe_mode,
           min_close, min_dollar_vol)
    if _cache["key"] == key and (time.time() - _cache["ts"]) < _CACHE_TTL_SEC:
        return _cache["rows"]

    spy = load_prices("SPY")
    if spy is None:
        return []
    spy_lr = np.log(spy["close"]).diff()

    rows: list[dict] = []
    for sym in load_universe(universe_mode):
        if sym == "SPY":
            continue
        df = load_prices(sym)
        if df is None or len(df) < max(lookback, trend_length) + 2:
            continue
        close = float(df["close"].iloc[-1])
        if close < min_close:
            continue
        vol = float(df["volume"].iloc[-1]) if "volume" in df else 0.0
        if close * vol < min_dollar_vol:
            continue
        beta = _beta(np.log(df["close"]).diff(), spy_lr, lookback)
        if beta is None or beta <= min_beta:
            continue
        sma = float(df["close"].iloc[-trend_length:].mean())
        if require_trending and close <= sma:
            continue
        rows.append({
            "symbol": sym,
            "name": company_names.name_for(sym) or sym,
            "beta": round(beta, 2),
            "close": round(close, 2),
            "sma": round(sma, 2),
            "above_sma_pct": round((close / sma - 1) * 100, 2) if sma else None,
            "dollar_vol": round(close * vol),
        })

    rows.sort(key=lambda r: -r["beta"])
    _cache.update(ts=time.time(), key=key, rows=rows)
    log.info("ravi.scan: %d matches (beta>%.1f, trend=%s, mode=%s)",
             len(rows), min_beta, require_trending, universe_mode)
    return rows
