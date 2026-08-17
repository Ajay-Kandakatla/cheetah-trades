"""Multi-day accumulation/distribution detector.

A single day's price/volume move is too noisy to call "smart money buying"
or "selling pressure". The classic technical approach is to look at the
relationship between close-within-range and volume across many sessions.

We compute three signals per ticker, blended into one score in [-100, +100]:

  1. Chaikin Money Flow (CMF) over 10 days — the workhorse:
       MF Multiplier = ((close - low) - (high - close)) / (high - low)
       MF Volume     = MF Multiplier × volume
       CMF           = sum(MF Volume over N) / sum(volume over N)
     Range -1 to +1. Positive = bulls in control of close vs range.

  2. Up-day / down-day volume ratio over 10 days:
       up_vol  = sum of volume on days where close > prev_close
       down_vol = sum of volume on days where close < prev_close
     ratio = (up_vol - down_vol) / (up_vol + down_vol)
     Positive = volume preceded by buyers; negative = sellers.

  3. Recent close-vs-range trend (5 days):
       avg_close_pos = mean of (close - low) / (high - low) over last 5
     >0.6 = consistently closes near high (accumulation behaviour)
     <0.4 = consistently closes near low (distribution).

Final score = weighted blend, scaled to [-100, +100].
Labels:
   ≥ +60  → "STRONG ACCUMULATION"
   +30..+60 → "ACCUMULATION"
   -30..+30 → "NEUTRAL"
   -60..-30 → "DISTRIBUTION"
   ≤ -60  → "STRONG DISTRIBUTION"

Data source: yfinance multi-ticker download (free, single HTTP).
Cache: 1h in Mongo (daily bars don't change intraday).
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from sepa import symbols

log = logging.getLogger("supply_demand.accumulation")

_CACHE_TTL_SEC = 60 * 60  # 1 hour


# --- Mongo cache --------------------------------------------------------

def _cache_coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        return client[db]["accumulation_cache"]
    except Exception as exc:
        log.warning("accumulation cache mongo unavailable: %s", exc)
        return None


def _cache_get(tickers_key: str) -> Optional[dict]:
    coll = _cache_coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"_id": tickers_key})
        if not doc:
            return None
        ts = doc.get("cached_at")
        if not isinstance(ts, datetime):
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - ts).total_seconds() > _CACHE_TTL_SEC:
            return None
        return doc.get("payload")
    except Exception:
        return None


def _cache_put(tickers_key: str, payload: dict) -> None:
    coll = _cache_coll()
    if coll is None:
        return
    try:
        coll.update_one(
            {"_id": tickers_key},
            {"$set": {"cached_at": datetime.now(timezone.utc), "payload": payload}},
            upsert=True,
        )
    except Exception as exc:
        log.warning("accumulation cache put failed: %s", exc)


# --- Compute score per ticker -----------------------------------------

def _compute_score(df) -> Optional[dict]:
    """Compute accumulation score from a multi-day OHLCV DataFrame.

    Expects pandas DataFrame with columns: Open, High, Low, Close, Volume.
    Index is dates (newest last).

    Returns dict with score (-100..+100) and breakdown signals, or None
    if the data is too thin.
    """
    try:
        import pandas as pd
    except Exception:
        return None

    if df is None or len(df) < 5:
        return None

    df = df.dropna()
    if len(df) < 5:
        return None

    n = min(10, len(df))
    recent = df.tail(n).copy()

    # 1) Chaikin Money Flow over n days
    high_low = recent["High"] - recent["Low"]
    # Avoid divide-by-zero on doji days
    high_low = high_low.where(high_low > 0, 1e-9)
    mf_mult = ((recent["Close"] - recent["Low"]) - (recent["High"] - recent["Close"])) / high_low
    mf_vol = mf_mult * recent["Volume"]
    total_vol = recent["Volume"].sum()
    cmf = float(mf_vol.sum() / total_vol) if total_vol > 0 else 0.0

    # 2) Up-day vs down-day volume
    closes = recent["Close"].values
    vols = recent["Volume"].values
    up_vol = 0.0
    down_vol = 0.0
    for i in range(1, len(closes)):
        if closes[i] > closes[i-1]:
            up_vol += float(vols[i])
        elif closes[i] < closes[i-1]:
            down_vol += float(vols[i])
    vol_ratio = 0.0
    if up_vol + down_vol > 0:
        vol_ratio = (up_vol - down_vol) / (up_vol + down_vol)

    # 3) Recent close-position-in-range (last 5 days)
    last5 = recent.tail(5)
    h_l = last5["High"] - last5["Low"]
    h_l = h_l.where(h_l > 0, 1e-9)
    close_pos = ((last5["Close"] - last5["Low"]) / h_l).mean()
    # Center around 0: 0.5 → 0; >0.5 → positive; <0.5 → negative
    close_pos_signal = (float(close_pos) - 0.5) * 2  # range [-1, +1]

    # Blend (weights sum to ~1)
    raw = cmf * 0.5 + vol_ratio * 0.3 + close_pos_signal * 0.2

    # Scale to [-100, +100], clip at edges
    score = max(-100.0, min(100.0, raw * 100))

    label = (
        "STRONG ACCUMULATION" if score >= 60 else
        "ACCUMULATION"        if score >= 30 else
        "DISTRIBUTION"        if score <= -30 and score > -60 else
        "STRONG DISTRIBUTION" if score <= -60 else
        "NEUTRAL"
    )

    return {
        "score": round(score, 1),
        "label": label,
        "cmf": round(cmf, 4),
        "up_down_vol_ratio": round(vol_ratio, 4),
        "close_position_5d": round(float(close_pos), 4),
        "n_days": n,
    }


# --- Public API ---------------------------------------------------------

def get_accumulation_scores(tickers: list[str], force: bool = False) -> dict:
    """Fetch + compute accumulation score for many tickers in one call.

    Returns dict keyed by ticker:
      { "NVDA": {score, label, cmf, up_down_vol_ratio, ...},
        "AAPL": {...} }
    """
    if not tickers:
        return {}

    cache_key = "accum_v1:" + ",".join(sorted(tickers))[:500]  # mongo key cap
    if not force:
        cached = _cache_get(cache_key)
        if cached:
            return cached

    out: dict[str, dict] = {}
    try:
        import yfinance as yf
        import pandas as pd  # noqa: F401  (used by _compute_score)

        t0 = time.time()
        # Single-ticker path: use Ticker.history() which always returns a
        # flat DataFrame with Open/High/Low/Close/Volume columns.
        # Multi-ticker path: use download() which gives MultiIndex columns
        # under each ticker.
        if len(tickers) == 1:
            t = tickers[0]
            try:
                df = symbols.yf_ticker(t).history(period="15d", interval="1d", auto_adjust=True)
                if df is not None and not df.empty:
                    score = _compute_score(df)
                    if score:
                        out[t.upper()] = score
            except Exception as exc:
                log.warning("yfinance Ticker(%s).history failed: %s", t, exc)
        else:
            df = yf.download(
                tickers=" ".join(tickers),
                period="15d",
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                progress=False,
                threads=True,
            )
            for t in tickers:
                try:
                    sub = df[t]
                except (KeyError, AttributeError):
                    continue
                score = _compute_score(sub)
                if score:
                    out[t.upper()] = score
        log.info("accumulation: yfinance fetch for %d tickers in %.2fs",
                 len(tickers), time.time() - t0)
    except Exception as exc:
        log.warning("accumulation fetch failed: %s", exc)

    _cache_put(cache_key, out)
    return out


__all__ = ["get_accumulation_scores"]


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    test = ["NVDA", "AAPL", "TSLA"]
    print(json.dumps(get_accumulation_scores(test, force=True), indent=2, default=str))
