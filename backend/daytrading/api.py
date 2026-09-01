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

from fastapi import APIRouter, Depends, Query

from auth import current_user_email
from fastapi.responses import JSONResponse

from . import backtest as bt_mod
from . import data as data_mod
from . import paper_trading as paper_mod
from .indicators import (
    atr, opening_range, premarket_levels,
    relative_volume, session_high_low, vwap_session,
)
from .signals import orb, gap_and_go, bull_flag, vwap_reversion, momentum_failure
from . import universe as universe_mod
from . import premarket as premarket_mod
from . import leaderboard_intraday as lbi_mod

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
        "description": "Break above the first 15-min RTH high on volume (long).",
        "research": "Toby Crabel (1990), Linda Raschke (1995)",
        "side": "long",
        "30d_baseline_winrate": 43.4, "30d_baseline_avgR": 0.20, "30d_baseline_pf": 1.39,
    },
    "gap_and_go": {
        "name": "Gap and Go",
        "description": "Premarket gap-UP ≥1% + first-bar confirmation + breakout above the 5-min high (long).",
        "research": "Ross Cameron / Warrior Trading; classic gappers framework.",
        "side": "long",
        "note": "Rare-fire on calm tape (0 trades in last 30d on this watchlist). Catches big premarket-driven days.",
    },
    "bull_flag": {
        "name": "Bull Flag continuation",
        "description": "Strong up-impulse (≥2%) + tight consolidation + volume-confirmed breakout (long).",
        "research": "Stockbee / classical chart patterns",
        "side": "long",
        "30d_baseline_winrate": 44.4, "30d_baseline_avgR": 0.31, "30d_baseline_pf": 1.9,
    },
    "vwap_reversion": {
        "name": "VWAP Reversion",
        "description": "Price extended ≥1.5 ATR BELOW VWAP with a reversal candle — fade back up to VWAP (long).",
        "research": "Brett Steenbarger / Mike Bellafiore",
        "side": "long",
        "warning": "Long dip-fades only. Works in choppy/range days, weak in strong trends — use selectively.",
    },
}


def _live_scan_symbols(symbols: Optional[str], profile: str) -> list[str]:
    """Bounded symbol set for the LIVE 1-minute scan. A small explicit list is
    honored as-is; anything larger (or no list) falls back to today's active
    movers so the per-symbol Massive fetches stay within budget."""
    if symbols:
        syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if 0 < len(syms) <= universe_mod.LIVE_SCAN_CAP:
            return syms
    return universe_mod.active_movers(profile)["symbols"] or DEFAULT_WATCHLIST


@router.get("/day/symbols")
async def list_symbols(profile: str = Query("aggressive", description="aggressive | conservative")):
    """Dynamic day-trade universe — today's liquid, volatile movers (replaces the
    old static 10-name list). `watchlist` is the bounded set to chart + live-scan;
    `universe_size` is the full day-tradeable pool the movers were drawn from."""
    movers = await asyncio.to_thread(universe_mod.active_movers, profile)
    uni = await asyncio.to_thread(universe_mod.day_trade_universe, profile)
    return {
        "watchlist": movers["symbols"] or DEFAULT_WATCHLIST,
        "movers": movers["active"],
        "profile": movers["profile"],
        "live": movers["live"],
        "universe_size": uni["n"],
        "criteria": uni["criteria"],
        "as_of": movers["as_of"],
    }


@router.get("/day/strategies")
async def list_strategies():
    return {"strategies": STRATEGY_INFO}


@router.get("/day/gappers")
async def day_gappers(profile: str = Query("aggressive", description="aggressive | conservative"),
                      force: bool = Query(False, description="bypass the 2-min cache")):
    """Overnight gappers — the pre-market 'set the day' scan made live: names
    gapping ≥2% on real volume, ranked by gap × relative-volume, with premarket
    high/low + 10-day RelVol + earnings-ahead on the top names. Educational, not
    advice."""
    return _json_safe(await asyncio.to_thread(premarket_mod.gappers, profile, force))


@router.get("/day/leaderboard")
async def day_leaderboard(n: int = Query(14, ge=1, le=30),
                          days: int = Query(14, ge=1, le=45),
                          force: bool = Query(False, description="bypass the 2-min cache")):
    """Leaderboard leaders crossed with TODAY's intraday move + a live buyable flag.
    The rank-consistent SEPA leaders, sorted by today's % move (gainers first), each
    tagged buyable/not. When the market is closed this is the 'as of last close'
    watch list for the open (market_session/is_open say which). Educational, not advice."""
    return _json_safe(await asyncio.to_thread(lbi_mod.get_leaders_intraday, n, days, force))


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


# Long-only (bull swing): momentum_failure is short-only so it's excluded; the
# rest are filtered to long signals at the scan call sites below.
_STRATEGIES = {
    "orb": orb, "gap_and_go": gap_and_go, "bull_flag": bull_flag,
    "vwap_reversion": vwap_reversion,
}


@router.get("/day/signals/today")
async def signals_today(
    symbols: Optional[str] = Query(None, description="comma-sep override (small lists honored; larger lists fall back to active movers)"),
    strategies: Optional[str] = Query(None, description="comma-sep filter; default = all"),
    profile: str = Query("aggressive", description="aggressive | conservative"),
):
    """Live signals for today across today's active movers (bounded) + all
    strategies (or filtered)."""
    syms = await asyncio.to_thread(_live_scan_symbols, symbols, profile)
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
                sigs = [x for x in mod.detect(df) if x.get("side") == "long"]   # long-only (bull swing)
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
            sigs = [x for x in mod.detect(df) if x.get("side") == "long"]   # long-only (bull swing)
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
    profile: str = Query("aggressive", description="aggressive | conservative"),
):
    """Run scan + close-exited workflow, then return today's paper trades + stats."""
    syms = await asyncio.to_thread(_live_scan_symbols, symbols, profile)
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


# ── Signal Lab — Ajay's own tickers, 1-minute BUY/SELL tags ────────────────
@router.get("/day/signal-lab/board")
async def signal_lab_board(symbols: str = ""):
    """One tile per requested symbol: last session's 1-minute candles with
    ORB / sweep / BOS / composite BUY-SELL events, plus the event feed.
    Closed bars only — see the payload's method_note."""
    import asyncio
    from . import signal_lab as sl
    syms = [s for s in (symbols or "").split(",") if s.strip()]
    return await asyncio.to_thread(sl.board, syms)


@router.get("/day/signal-lab/watchlist")
async def signal_lab_watchlist(email: str = Depends(current_user_email)):
    from . import signal_lab as sl
    return {"symbols": sl.get_watchlist(email)}


@router.post("/day/signal-lab/watchlist/{symbol}")
async def signal_lab_watch_add(symbol: str, email: str = Depends(current_user_email)):
    from . import signal_lab as sl
    return {"symbols": sl.add_symbol(email, symbol)}


@router.delete("/day/signal-lab/watchlist/{symbol}")
async def signal_lab_watch_remove(symbol: str, email: str = Depends(current_user_email)):
    from . import signal_lab as sl
    return {"symbols": sl.remove_symbol(email, symbol)}
