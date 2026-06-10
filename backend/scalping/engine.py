"""Scalping engine — selects today's liquid universe, loads intraday bars, runs
the Phase-1 detectors, and wraps every signal in the honesty layer (live spread
gate + net-of-cost + regime alignment). Reuses the existing daytrading stack.

Live + on-demand: a short in-process cache (the page polls). Educational, not
advice — and the page carries the base-rate reality banner.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, time as dtime, timedelta, timezone
from typing import Optional

import numpy as np
import pandas as pd

from . import costs, detectors, nbbo, regime as regime_mod

log = logging.getLogger("scalping.engine")

UNIVERSE_LIMIT = 20
PRIOR_DAYS = 21                # calendar days back for RelVol + daily-ATR history
_TTL_SEC = 45                 # live page; short cache
_FALLBACK_UNIVERSE = ["AAPL", "NVDA", "TSLA", "AMD", "META", "AMZN", "MSFT", "SPY", "QQQ", "GOOGL"]


def _now_et() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        # Container TZ is America/New_York (compose) — local time IS ET, and
        # this stays DST-correct (a fixed UTC-5 was wrong half the year).
        return datetime.now().astimezone()


def _market_open(now_et: Optional[datetime] = None) -> bool:
    n = now_et or _now_et()
    if n.weekday() >= 5:
        return False
    try:
        from market_hours.reminder import is_market_day
        if not is_market_day(n):
            return False
    except Exception:
        pass
    return dtime(9, 30) <= n.time() <= dtime(16, 0)


def _universe(profile: str, limit: int) -> list:
    try:
        from daytrading.universe import day_trade_universe
        # BUG FIX 2026-06-10: day_trade_universe returns {"names": [...]}, not a
        # list — iterating the dict raised inside the comprehension and this
        # silently fell back to the static list on EVERY scan.
        rows = (day_trade_universe(profile=profile, limit=limit) or {}).get("names") or []
        syms = [r.get("symbol") for r in rows if r.get("symbol")]
        if syms:
            return syms[:limit]
    except Exception as exc:
        log.warning("scalping universe load failed: %s", exc)
    return _FALLBACK_UNIVERSE[:limit]


def _daily_atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    """Daily ATR(period) from a multi-day 1-min RTH frame (paper uses daily ATR
    for the stop). Groups bars by ET date → daily OHLC → Wilder TR mean.

    Excludes the most recent (developing) day — including today's partial bar
    biased the live ATR vs the backtest's strictly-prior _daily_atr_asof
    (review fix 2026-06-09)."""
    if df is None or df.empty:
        return None
    rth = df[df["session"] == "rth"]
    if rth.empty:
        return None
    et = rth.index.tz_localize("UTC").tz_convert("America/New_York")
    day = pd.Series(et.date, index=rth.index)
    daily = rth.groupby(day).agg(high=("high", "max"), low=("low", "min"), close=("close", "last"))
    if len(daily) >= 2:
        daily = daily.iloc[:-1]              # drop the developing day
    if len(daily) < 3:
        return None
    prev_close = daily["close"].shift(1)
    tr = pd.concat([(daily["high"] - daily["low"]).abs(),
                    (daily["high"] - prev_close).abs(),
                    (daily["low"] - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(min(period, len(daily))).mean().iloc[-1]
    return float(atr) if atr == atr else None          # NaN-safe


def _scan_symbol(symbol: str, regime_bias: Optional[str]) -> list:
    """Load one name's recent intraday, compute RelVol + daily ATR, run detectors."""
    from daytrading.data import load_intraday_range
    from daytrading.indicators import relative_volume
    today = _now_et().date()
    from_day = today - timedelta(days=PRIOR_DAYS)
    try:
        df = load_intraday_range(symbol, from_day, today, include_premarket=True)
    except Exception as exc:
        log.debug("scalping load %s failed: %s", symbol, exc)
        return []
    if df is None or df.empty:
        return []
    rel_vol = relative_volume(df, lookback_days=14)
    atr14 = _daily_atr(df)
    out = []
    try:
        orb = detectors.stocks_in_play_orb(df, rel_vol=rel_vol, atr14=atr14, regime_bias=regime_bias)
        if orb:
            out.append(orb)
    except Exception as exc:
        log.debug("orb detector %s failed: %s", symbol, exc)
    try:
        fade = detectors.shock_fade(df, atr14=atr14)
        if fade:
            out.append(fade)
    except Exception as exc:
        log.debug("shock_fade detector %s failed: %s", symbol, exc)
    for s in out:
        s["symbol"] = symbol
    return out


def scan_now(profile: str = "aggressive", limit: int = UNIVERSE_LIMIT) -> dict:
    n = _now_et()
    regime = regime_mod.intraday_regime(n)
    bias = regime.get("bias")
    open_now = _market_open(n)

    signals: list = []
    if open_now:
        syms = _universe(profile, limit)
        # Parallel — sequential 21-day loads for ~20 names blew past the 45s TTL
        # whenever Massive was slow (review fix 2026-06-09).
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as ex:
            for sigs in ex.map(lambda s: _scan_symbol(s, bias), syms):
                signals.extend(sigs)

        # Live spread gate + net-of-cost on the active set only.
        quotes = nbbo.fetch_nbbo_bulk([s["symbol"] for s in signals])
        for s in signals:
            q = quotes.get(s["symbol"]) or {}
            spread_pct = q.get("spread_pct")
            gate = nbbo.spread_gate(spread_pct, s.get("target_move_pct"))
            s["spread"] = {"bid": q.get("bid"), "ask": q.get("ask"),
                           "spread_pct": spread_pct, **gate}
            s["tradeable"] = gate.get("ok", False) and s.get("status") != "too_extended"
            costs.annotate_net_of_cost(s, spread_pct)

        # Triggered + tradeable first, then armed, then the rest.
        rank = {"triggered": 0, "armed": 1}
        signals.sort(key=lambda s: (0 if s.get("tradeable") else 1,
                                    rank.get(s.get("status"), 2),
                                    -(s.get("rel_vol") or 0)))

    return {
        "generated_at": int(time.time()),
        "as_of_et": n.strftime("%Y-%m-%d %H:%M ET"),
        "market_open": open_now,
        "profile": profile,
        "regime": regime,
        "signals": signals,
        "n": len(signals),
        "disclaimer": (
            "Educational, NOT advice. Phase-1 documented intraday patterns with a "
            "net-of-cost overlay. On the weight of account-level evidence the "
            "activity these surface is net-LOSING for the large majority of retail "
            "traders — gross signal is shown beside net-of-cost reality; no backtest "
            "changes that base rate. See docs/scalping_methodology.md."),
    }


# Per-profile cache entries — a single shared slot let two concurrent requests
# for different profiles clobber each other (review fix 2026-06-09).
_CACHE: dict = {}


def get_signals(profile: str = "aggressive", force: bool = False) -> dict:
    now = time.time()
    hit = _CACHE.get(profile)
    if not force and hit and (now - hit["at"]) < _TTL_SEC:
        return hit["data"]
    data = scan_now(profile=profile)
    _CACHE[profile] = {"at": now, "data": data}
    return data
