"""Ravi's Strategy — volume-surge rank.

Verbatim port of Ravi's ThinkScript study (user-provided 2026-06-02):

    input volLookback   = 20;
    input breakoutThresh = 2.0;

    def avgVol   = Average(volume, volLookback);      # SMA of volume
    def diff1    = Sqr(volume - avgVol);              # squared deviation
    def avgVar   = Average(diff1, volLookback);       # SMA of diff1
    def stdVol   = Sqrt(avgVar);                      # rolling std of volume
    def volZ     = if stdVol > 0 then (volume - avgVol) / stdVol else 0;
    def volRatio = if avgVol  > 0 then  volume / avgVol           else 0;
    def rawScore = (volZ * 30) + (volRatio * 10);
    def rank     = Min(Max(rawScore, 0), 100);
    def isBullish = close > open;
    def isFlat    = close == open;

`Sqr` is x², `Sqrt` is √. `Average` is a simple moving average. Computed on the
LATEST daily bar off cached prices (no external calls). Cached 15 min.
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

VOL_LOOKBACK = 20
BREAKOUT_THRESH = 2.0

_cache: dict = {"ts": 0.0, "key": None, "rows": []}
_CACHE_TTL_SEC = 15 * 60


def volume_rank(df: pd.DataFrame, *, lookback: int = VOL_LOOKBACK,
                breakout_thresh: float = BREAKOUT_THRESH) -> Optional[dict]:
    """The ThinkScript formula on the latest bar. Returns the volume-rank record
    or None when there isn't enough history. Pure — unit-tested."""
    if df is None or "volume" not in df or len(df) < 2 * lookback:
        return None
    v = df["volume"].astype(float)
    avg_series = v.rolling(lookback).mean()                       # Average(volume, n)
    diff1 = (v - avg_series) ** 2                                 # Sqr(volume - avgVol)
    avg_var = diff1.rolling(lookback).mean()                      # Average(diff1, n)
    std_series = np.sqrt(avg_var)                                 # Sqrt(avgVar)

    volume = float(v.iloc[-1])
    avg_vol = float(avg_series.iloc[-1])
    std_vol = float(std_series.iloc[-1])
    if not (np.isfinite(avg_vol) and np.isfinite(std_vol)):
        return None

    vol_z = (volume - avg_vol) / std_vol if std_vol > 0 else 0.0
    vol_ratio = volume / avg_vol if avg_vol > 0 else 0.0
    raw_score = (vol_z * 30) + (vol_ratio * 10)
    rank = min(max(raw_score, 0.0), 100.0)

    close = float(df["close"].iloc[-1])
    open_ = float(df["open"].iloc[-1]) if "open" in df else close
    return {
        "rank":       round(rank, 1),
        "raw_score":  round(raw_score, 2),
        "vol_z":      round(vol_z, 2),
        "vol_ratio":  round(vol_ratio, 2),
        "volume":     int(volume),
        "avg_vol":    int(avg_vol),
        "is_bullish": bool(close > open_),
        "is_flat":    bool(close == open_),
        "is_breakout": bool(vol_z >= breakout_thresh),   # volZ ≥ breakoutThresh
    }


def scan(universe_mode: str = "broad", min_close: float = 10.0,
         min_dollar_vol: float = 5_000_000.0, breakout_thresh: float = BREAKOUT_THRESH,
         min_rank: float = 0.0) -> list[dict]:
    """Rank the universe by Ravi's volume-surge score (0-100), highest first.
    Liquidity floors only (min price + min $ volume); `min_rank` optionally
    trims the tail. 15-min cached."""
    key = (universe_mode, min_close, min_dollar_vol, breakout_thresh, min_rank)
    if _cache["key"] == key and (time.time() - _cache["ts"]) < _CACHE_TTL_SEC:
        return _cache["rows"]

    rows: list[dict] = []
    for sym in load_universe(universe_mode):
        if sym == "SPY":
            continue
        df = load_prices(sym)
        if df is None or len(df) < 2 * VOL_LOOKBACK:
            continue
        close = float(df["close"].iloc[-1])
        if close < min_close:
            continue
        last_vol = float(df["volume"].iloc[-1]) if "volume" in df else 0.0
        if close * last_vol < min_dollar_vol:
            continue
        vr = volume_rank(df, breakout_thresh=breakout_thresh)
        if vr is None or vr["rank"] < min_rank:
            continue
        rows.append({
            "symbol": sym,
            "name": company_names.name_for(sym) or sym,
            "close": round(close, 2),
            "dollar_vol": round(close * last_vol),
            **vr,
        })

    rows.sort(key=lambda r: -r["rank"])
    _cache.update(ts=time.time(), key=key, rows=rows)
    log.info("ravi.scan(volume-rank): %d rows (mode=%s, min_rank=%.0f)",
             len(rows), universe_mode, min_rank)
    return rows
