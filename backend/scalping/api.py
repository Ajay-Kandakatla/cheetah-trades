"""Scalping API — live Phase-1 intraday signals with the net-of-cost honesty
layer. The chart reuses the existing /day/bars/{symbol} endpoint.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter(tags=["scalping"])


@router.get("/scalping/signals")
async def scalping_signals(profile: str = Query("aggressive"),
                           force: bool = Query(False, description="Bypass the short cache")):
    """Live scalping signals across today's liquid universe — Stocks-in-Play ORB
    + volatility-normalized shock-fade — each with the intraday-momentum regime,
    the live spread gate, and the gross-beside-net cost read. Educational, NOT
    advice; most retail day-trading is net-losing (see the disclaimer)."""
    from . import engine
    data = await asyncio.to_thread(engine.get_signals, profile, force)
    return JSONResponse(data)


@router.get("/scalping/regime")
async def scalping_regime():
    """The intraday-momentum direction regime (Gao et al. 2018) on its own —
    cheap; the page polls this more often than the full scan."""
    from . import regime
    return JSONResponse(await asyncio.to_thread(regime.intraday_regime))


@router.get("/scalping/backtest")
async def scalping_backtest(days: int = Query(20, ge=5, le=90),
                           profile: str = Query("aggressive"),
                           force: bool = Query(False, description="Bypass the 6h cache")):
    """Historical walk-forward backtest of the detectors over real Massive 1-min
    bars — GROSS beside NET-of-cost. The spread is ASSUMED (no historical NBBO),
    so net is an optimistic upper bound; caveats travel in the payload."""
    from . import backtest
    data = await asyncio.to_thread(backtest.get_backtest, days, profile, force)
    return JSONResponse(data)


@router.get("/scalping/paper")
async def scalping_paper(days: int = Query(30, ge=1, le=120)):
    """Forward paper-trade track record — every live signal recorded with its
    REAL captured spread and resolved on the tape. The honest net read; builds
    up over sessions."""
    from . import paper
    return JSONResponse(await asyncio.to_thread(paper.track_record, days))


@router.get("/scalping/watch")
async def scalping_watch(refresh: bool = Query(False, description="Recompute if the cron snapshot is stale")):
    """SEPA-cross tape watch — holdings + buyable + at-pivot + leaderboard names
    with the live 5-min candle read at their levels (pivot/VWAP/OR/day-high),
    today's alerts, and the LIVE per-state hit-rate (every alert is graded
    against the next 30 minutes). Descriptive reads, not predictions."""
    from . import sepa_watch
    return JSONResponse(await asyncio.to_thread(sepa_watch.snapshot, refresh))


@router.get("/scalping/tape-read/{symbol}")
async def scalping_tape_read(symbol: str):
    """On-demand single-symbol tape read: the latest completed 5-min candle vs
    its levels (SEPA pivot, forming daily-pattern line, VWAP, opening range,
    day high). Powers the live read strip on the Day Trading + Scalping pages."""
    from . import sepa_watch
    return JSONResponse(await asyncio.to_thread(sepa_watch.tape_read, symbol))


@router.get("/scalping/watch/backtest")
async def scalping_watch_backtest(days: int = Query(15, ge=5, le=60),
                                  force: bool = Query(False)):
    """Backtest of the tape READ itself — classify historical 5-min candles at
    levels and measure the +30-min outcome per state. Follow-through ≈50% means
    the read adds nothing; the verdict says so honestly."""
    from . import tape_backtest
    return JSONResponse(await asyncio.to_thread(tape_backtest.get, days, force))


@router.get("/scalping/config")
async def scalping_config():
    """The thresholds + sources behind the detectors, for the page's info panel."""
    from . import detectors as d
    from . import nbbo, costs
    return JSONResponse({
        "detectors": [
            {"id": "stocks_in_play_orb", "label": "Stocks-in-Play 5-min ORB",
             "source": "Zarattini, Barbon & Aziz (2024), SSRN 4729284",
             "params": {"orb_minutes": d.ORB_MINUTES, "relvol_min": d.RELVOL_MIN,
                        "atr_mult": d.ORB_ATR_MULT, "max_ext_pct": d.MAX_EXT_PAST_TRIGGER_PCT}},
            {"id": "shock_fade", "label": "Volatility-normalized shock fade",
             "source": "Zawadowski, Andor & Kertesz (2004), arXiv cond-mat/0406696",
             "params": {"lookback_min": d.SHOCK_LOOKBACK_MIN, "min_move_pct": d.SHOCK_MIN_MOVE_PCT,
                        "sigma_mult": d.SHOCK_SIGMA_MULT, "time_stop_min": d.SHOCK_TIME_STOP_MIN}},
            {"id": "intraday_momentum_regime", "label": "Intraday-momentum regime (direction gate)",
             "source": "Gao, Han, Li & Zhou (2018), JFE 129(2):394-414"},
        ],
        "spread_gate": {"caution_pct": nbbo.SPREAD_PCT_CAUTION,
                        "kill_vs_target": nbbo.SPREAD_VS_TARGET_KILL},
        "costs": {"commission_per_share": costs.COMMISSION_PER_SHARE,
                  "slippage_bps_per_side": costs.DEFAULT_SLIPPAGE_BPS_PER_SIDE},
        "honest_note": ("Documented patterns, not proven retail edges. Account-level "
                        "studies find the large majority of retail day-traders net lose "
                        "after costs. See docs/scalping_methodology.md."),
    })
