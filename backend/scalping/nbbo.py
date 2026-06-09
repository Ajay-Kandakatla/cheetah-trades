"""Live NBBO (bid/ask) for the spread kill-switch — Massive snapshot endpoint.

The research made the live spread the dominant cost gate for scalps. The live
WS feed only carries last trades, so we pull the National Best Bid/Offer on
demand for the small set of ACTIVE signal symbols via Massive's REST snapshot
(`/v2/snapshot/.../tickers/{T}` → lastQuote.p = bid, .P = ask). Best-effort: on
any failure we return None and the cost layer flags the spread UNKNOWN — never
silently zero.
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

log = logging.getLogger("scalping.nbbo")

BASE_URL = "https://api.massive.com"
_TIMEOUT = 6


def _key() -> str:
    return os.getenv("MASSIVE_API_KEY", "").strip()


def fetch_nbbo(symbol: str) -> Optional[dict]:
    """Live NBBO for one symbol → {bid, ask, mid, spread, spread_pct} or None."""
    key = _key()
    if not key:
        return None
    try:
        import requests
    except ImportError:
        return None
    try:
        r = requests.get(
            f"{BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers/{symbol.upper()}",
            params={"apiKey": key}, timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        t = (r.json() or {}).get("ticker") or {}
        q = t.get("lastQuote") or {}
        bid, ask = q.get("p"), q.get("P")
        if not bid or not ask or bid <= 0 or ask <= 0 or ask < bid:
            return None
        mid = (bid + ask) / 2.0
        spread = ask - bid
        return {
            "bid": round(bid, 4), "ask": round(ask, 4), "mid": round(mid, 4),
            "spread": round(spread, 4),
            "spread_pct": round(spread / mid * 100.0, 4) if mid > 0 else None,
        }
    except Exception as exc:
        log.debug("nbbo fetch failed for %s: %s", symbol, exc)
        return None


def fetch_nbbo_bulk(symbols: list, max_workers: int = 8) -> dict:
    """NBBO for several symbols (the active signal set). Missing/failed → absent."""
    out: dict = {}
    syms = [s for s in dict.fromkeys(symbols) if s]
    if not syms or not _key():
        return out
    with ThreadPoolExecutor(max_workers=min(max_workers, len(syms))) as ex:
        for sym, q in zip(syms, ex.map(fetch_nbbo, syms)):
            if q:
                out[sym] = q
    return out


# Spread kill-switch thresholds (CONFIGURED — realism survey, not a book rule).
# A scalp targeting ~0.5-1% can't absorb a spread that's a large fraction of it.
SPREAD_PCT_CAUTION = 0.10     # spread > 0.10% of price → caution
SPREAD_VS_TARGET_KILL = 0.25  # spread ≥ 25% of the intended move → refuse


def spread_gate(spread_pct: Optional[float], target_move_pct: Optional[float]) -> dict:
    """Classify the live spread for a signal. Returns a verdict the UI shows and
    the engine uses to suppress/flag a setup."""
    if spread_pct is None:
        return {"state": "unknown", "ok": False,
                "note": "Live spread unavailable — assume you pay it."}
    if target_move_pct and target_move_pct > 0 and (spread_pct / target_move_pct) >= SPREAD_VS_TARGET_KILL:
        return {"state": "too_wide", "ok": False,
                "note": f"Spread {spread_pct:.2f}% is ≥{int(SPREAD_VS_TARGET_KILL*100)}% of the target move — skip."}
    if spread_pct >= SPREAD_PCT_CAUTION:
        return {"state": "wide", "ok": True,
                "note": f"Spread {spread_pct:.2f}% is wide — fills will hurt."}
    return {"state": "tight", "ok": True, "note": f"Spread {spread_pct:.2f}% — tradeable."}
