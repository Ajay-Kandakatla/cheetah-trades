"""FastAPI handlers for the day-trading module.

Routes:
  GET  /day/symbols                    — default day-trading watchlist
  GET  /day/bars/{symbol}              — recent 1m bars (today + N prior days)
  GET  /day/signals/today              — live signals firing today across watchlist
  GET  /day/signals/{symbol}/today     — signals for one symbol
  GET  /day/backtest/{symbol}          — walk-forward backtest
  GET  /day/backtest/yesterday         — yesterday's stats across the watchlist
  GET  /day/explain/{symbol}           — AI second opinion (gated; off by default)
"""
from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from . import backtest as bt_mod
from . import data as data_mod
from . import paper_trading as paper_mod
from .indicators import (
    atr, opening_range, premarket_levels,
    relative_volume, session_high_low, vwap_session,
)
from .signals import orb, gap_and_go, bull_flag, vwap_reversion, momentum_failure

log = logging.getLogger("daytrading.api")
router = APIRouter(tags=["daytrading"])


def _json_safe(o):
    """Recursively replace NaN/Inf floats with None so the strict JSON encoder
    can serialize backtest/paper payloads. Intraday stats divide by trade counts
    and read indicator columns (ATR/VWAP at session start) that can be NaN; a
    single NaN/Inf 500s the whole route (observed on /day/backtest/{symbol})."""
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else o
    if isinstance(o, dict):
        return {k: _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    return o


# Default watchlist — high-volume, high-volatility names where ORB has edge.
# Combines mega-cap movers + volatile fintech/crypto-adjacent + biotech beta.
DEFAULT_WATCHLIST = ["TSLA", "NVDA", "COIN", "MSTR", "AMD", "PLTR", "META", "AAPL", "AVGO", "CRWD"]


# Strategy descriptors — what they look for + 30d backtest stats baseline.
STRATEGY_INFO = {
    "orb": {
        "name": "Opening Range Breakout",
        "description": "Break above/below first 15min RTH high/low on volume.",
        "research": "Toby Crabel (1990), Linda Raschke (1995)",
        "side": "both",
        "30d_baseline_winrate": 43.4, "30d_baseline_avgR": 0.20, "30d_baseline_pf": 1.39,
    },
    "gap_and_go": {
        "name": "Gap and Go",
        "description": "Premarket gap ≥1% + first-bar confirmation + breakout above 5-min range.",
        "research": "Ross Cameron / Warrior Trading; classic gappers framework.",
        "side": "both",
        "note": "Rare-fire on calm tape (0 trades in last 30d on this watchlist). Catches big premarket-driven days.",
    },
    "bull_flag": {
        "name": "Bull/Bear Flag continuation",
        "description": "Strong impulse move (≥2%) + tight consolidation + volume-confirmed breakout.",
        "research": "Stockbee / classical chart patterns",
        "side": "both",
        "30d_baseline_winrate": 44.4, "30d_baseline_avgR": 0.31, "30d_baseline_pf": 1.9,
    },
    "vwap_reversion": {
        "name": "VWAP Reversion",
        "description": "Price extended ≥1.5 ATR from VWAP with reversal candle. Mean-reversion fade.",
        "research": "Brett Steenbarger / Mike Bellafiore",
        "side": "both",
        "warning": "Negative expectancy on momentum names (-0.11 avgR over 30d). Works better in choppy regimes.",
    },
    "momentum_failure": {
        "name": "Momentum Failure (short-only)",
        "description": "Parabolic +3% move + topping candle + confirmation. Fade exhausted moves.",
        "research": "Bo Yoder / Steenbarger",
        "side": "short",
        "warning": "Asymmetric — shorts are harder than longs in equity markets. Works best on COIN-like names.",
    },
}


@router.get("/day/symbols")
async def list_symbols():
    return {"watchlist": DEFAULT_WATCHLIST}


@router.get("/day/strategies")
async def list_strategies():
    return {"strategies": STRATEGY_INFO}


@router.get("/day/bars/{symbol}")
async def get_bars(symbol: str, days: int = Query(1, ge=1, le=10),
                   include_premarket: bool = Query(True),
                   include_afterhours: bool = Query(False)):
    """Return recent 1m bars + the indicators a chart needs (VWAP, ORB, prem H/L)."""
    end = datetime.utcnow().date()
    start = (datetime.utcnow() - timedelta(days=days * 2)).date()  # over-fetch to cover weekends
    df = await asyncio.to_thread(data_mod.load_intraday_range, symbol.upper(), start, end,
                                 include_premarket=include_premarket,
                                 include_afterhours=include_afterhours)
    if df is None or df.empty:
        return JSONResponse({"symbol": symbol.upper(), "bars": [], "indicators": {}}, status_code=200)

    # Indicators
    vw = vwap_session(df, session="rth")
    atr14 = atr(df, period=14)
    orb_ = opening_range(df, minutes=15)
    pre = premarket_levels(df)
    rth_hi_lo = session_high_low(df, session="rth")
    rel_vol = relative_volume(df, lookback_days=10)

    # Serialize bars with their indicator values
    bars_out = []
    for ts, row in df.iterrows():
        bars_out.append({
            "ts": ts.isoformat(),
            "o": round(float(row["open"]), 4),
            "h": round(float(row["high"]), 4),
            "l": round(float(row["low"]), 4),
            "c": round(float(row["close"]), 4),
            "v": float(row["volume"]),
            "session": row.get("session", ""),
            "vwap": round(float(vw.loc[ts]), 4) if ts in vw.index and not str(vw.loc[ts]) in ("nan", "NaN") and vw.loc[ts] == vw.loc[ts] else None,
            "atr14": round(float(atr14.loc[ts]), 4) if ts in atr14.index and atr14.loc[ts] == atr14.loc[ts] else None,
        })

    return {
        "symbol": symbol.upper(),
        "bars": bars_out,
        "indicators": {
            "opening_range": orb_,
            "premarket": pre,
            "rth_hi_lo": rth_hi_lo,
            "relative_volume": rel_vol,
        },
    }


_STRATEGIES = {
    "orb": orb, "gap_and_go": gap_and_go, "bull_flag": bull_flag,
    "vwap_reversion": vwap_reversion, "momentum_failure": momentum_failure,
}


@router.get("/day/signals/today")
async def signals_today(
    symbols: Optional[str] = Query(None, description="comma-sep override"),
    strategies: Optional[str] = Query(None, description="comma-sep filter; default = all"),
):
    """Live signals for today across the watchlist + all strategies (or filtered)."""
    syms = [s.strip().upper() for s in symbols.split(",")] if symbols else DEFAULT_WATCHLIST
    selected = [s.strip() for s in strategies.split(",")] if strategies else list(_STRATEGIES.keys())
    today = datetime.utcnow().date()
    out = []
    for s in syms:
        df = await asyncio.to_thread(data_mod.load_intraday, s, today, include_premarket=True)
        if df is None or df.empty:
            continue
        for name in selected:
            mod = _STRATEGIES.get(name)
            if mod is None:
                continue
            try:
                sigs = mod.detect(df)
            except Exception:
                continue
            for sig in sigs:
                out.append({**sig, "symbol": s, "et_date": str(today)})
    return {"signals": out, "as_of": datetime.utcnow().isoformat() + "Z",
            "strategies_scanned": selected, "symbols_scanned": syms}


@router.get("/day/signals/{symbol}/today")
async def signals_symbol_today(symbol: str,
                               strategies: Optional[str] = Query(None)):
    selected = [s.strip() for s in strategies.split(",")] if strategies else list(_STRATEGIES.keys())
    today = datetime.utcnow().date()
    df = await asyncio.to_thread(data_mod.load_intraday, symbol.upper(), today, include_premarket=True)
    if df is None or df.empty:
        return {"symbol": symbol.upper(), "signals": [], "reason": "no bars yet"}
    out = []
    for name in selected:
        mod = _STRATEGIES.get(name)
        if mod is None:
            continue
        try:
            sigs = mod.detect(df)
        except Exception:
            continue
        for sig in sigs:
            sig["symbol"] = symbol.upper()
            sig["et_date"] = str(today)
            out.append(sig)
    return {"symbol": symbol.upper(), "signals": out}


# --- Paper trading -----------------------------------------------------------
@router.get("/day/paper/today")
async def paper_today(
    symbols: Optional[str] = Query(None),
    strategies: Optional[str] = Query(None),
):
    """Run scan + close-exited workflow, then return today's paper trades + stats."""
    syms = [s.strip().upper() for s in symbols.split(",")] if symbols else DEFAULT_WATCHLIST
    strats = [s.strip() for s in strategies.split(",")] if strategies else None
    update = paper_mod.scan_and_update(syms, strategies=strats)
    state = paper_mod.list_today(symbols=syms)
    return _json_safe({**state, "scan_summary": update})


@router.post("/day/paper/reset")
async def paper_reset(symbols: Optional[str] = Query(None)):
    syms = [s.strip().upper() for s in symbols.split(",")] if symbols else None
    return paper_mod.reset_today(symbols=syms)


@router.get("/day/backtest/yesterday")
async def backtest_yesterday(symbols: Optional[str] = Query(None)):
    """Yesterday-only stats: did each strategy fire and what was the outcome."""
    syms = [s.strip().upper() for s in symbols.split(",")] if symbols else DEFAULT_WATCHLIST
    return _json_safe(bt_mod.backtest_universe(syms, days=2, strategy="orb"))  # 2-day window covers yesterday


@router.get("/day/backtest/{symbol}")
async def backtest_symbol(symbol: str, days: int = Query(30, ge=5, le=365),
                          strategy: str = Query("orb")):
    return _json_safe(bt_mod.backtest_symbol(symbol.upper(), days=days, strategy=strategy))


@router.get("/day/explain/{symbol}")
async def explain(symbol: str):
    """LLM second-opinion. Uses local LLM via LLM_BASE_URL/LLM_MODEL env vars."""
    import llm
    if not llm.is_enabled():
        return JSONResponse(
            {"enabled": False,
             "message": "Set LLM_BASE_URL and LLM_MODEL in backend/.env and restart api."},
            status_code=503,
        )
    try:
        from .ai_review import explain_setup
        return await explain_setup(symbol.upper())
    except Exception as exc:
        log.exception("LLM explain failed")
        return JSONResponse({"enabled": True, "error": str(exc)}, status_code=500)
