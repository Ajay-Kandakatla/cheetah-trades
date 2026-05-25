"""IBD-style Relative Strength rank.

Per IBD's formula: weight 3-, 6-, 9-, 12-month price returns 40/20/20/20 and
percentile-rank across the full universe. Output is 1-99 where higher = leader.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, TYPE_CHECKING

import pandas as pd

from .prices import load_prices

if TYPE_CHECKING:
    from .progress import ProgressEmitter


def _return(df: pd.DataFrame, lookback_days: int) -> Optional[float]:
    if df is None or len(df) < lookback_days + 1:
        return None
    start = df["close"].iloc[-lookback_days - 1]
    end = df["close"].iloc[-1]
    if start == 0:
        return None
    return float(end / start - 1)


def rs_score(df: pd.DataFrame) -> Optional[float]:
    r63 = _return(df, 63)    # ~3 months
    r126 = _return(df, 126)  # ~6 months
    r189 = _return(df, 189)  # ~9 months
    r252 = _return(df, 252)  # ~12 months
    parts = [r63, r126, r189, r252]
    if any(p is None for p in parts):
        return None
    return 0.4 * r63 + 0.2 * r126 + 0.2 * r189 + 0.2 * r252


def _score_one(symbol: str) -> tuple[str, Optional[float]]:
    """Worker: fetch prices + compute RS score for one ticker."""
    try:
        return symbol, rs_score(load_prices(symbol))
    except Exception:
        return symbol, None


def rs_ranks(symbols: list[str],
             emitter: Optional["ProgressEmitter"] = None,
             *,
             workers: int = 8) -> Dict[str, int]:
    """Return {symbol: rank 1-99}. Symbols with insufficient data are omitted.

    Parallelizes the slow `load_prices` step across `workers` threads (was
    sequential, which made Russell-1000 RS take 5-10 minutes of dead air
    before the per-ticker scan loop could start).

    Optional `emitter` fires `phase` events with per-batch progress so the
    SSE stream can show RS progress instead of staring at a "Computing RS
    ranks…" message.
    """
    scores: Dict[str, float] = {}
    total = len(symbols)
    completed = 0

    if emitter:
        emitter.emit("phase", phase="rs", total=total,
                     message=f"Computing RS ranks over {total} symbols")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_score_one, s): s for s in symbols}
        for fut in as_completed(futures):
            sym, val = fut.result()
            completed += 1
            if val is not None:
                scores[sym] = val
            # Emit a heartbeat every 25 tickers (or on the final tick) — fine
            # granularity would flood the SSE channel, none would look frozen.
            if emitter and (completed % 25 == 0 or completed == total):
                emitter.emit("rs_progress",
                             current=completed, total=total,
                             scored=len(scores))

    if not scores:
        return {}

    series = pd.Series(scores)
    # percentile rank: 0-1 → 1-99
    pct = series.rank(pct=True)
    return {sym: max(1, min(99, int(round(pct[sym] * 99)))) for sym in scores}
