"""FastAPI handlers for the overnight tracker."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from . import movers as mv
from daytrading.api import DEFAULT_WATCHLIST as DAY_WATCHLIST

router = APIRouter(tags=["overnight"])


@router.get("/overnight/movers")
async def overnight_movers(
    symbols: Optional[str] = Query(None, description="comma-sep override; default = day-trading watchlist"),
    min_gap_pct: float = Query(0.5, ge=0, le=20),
    include_sepa: bool = Query(True, description="also scan top-20 SEPA candidates"),
    force: bool = Query(False, description="bypass 30min cache and re-scrape"),
):
    """Overnight gap tracker — what moved while you slept and *why*.

    Cached per-symbol for 30 minutes (overnight prices stop changing after RTH
    opens). Pass `?force=true` to re-scrape on demand.
    """
    syms = set([s.strip().upper() for s in symbols.split(",")] if symbols else DAY_WATCHLIST)
    if include_sepa:
        try:
            from sepa import scanner as sepa_scanner
            scan = sepa_scanner.load_latest()
            rows = (scan or {}).get("all_results") or []
            top = sorted(rows, key=lambda r: -(r.get("score") or 0))[:20]
            syms.update(r.get("symbol") for r in top if r.get("symbol"))
        except Exception:
            pass
    syms.discard(None)
    syms.discard("")

    movers = mv.overnight_movers(sorted(syms), min_gap_pct=min_gap_pct, force=force)
    cached_count = sum(1 for m in movers if m.get("_cached"))

    # Decorate movers with SOIR snapshot (Schaeffer signal) when available.
    # No chain fetches here — just look up cached SOIR per symbol so the
    # overnight tape shows "this gapper also has crowd-loaded-with-puts
    # (bullish setup)" or "crowd already long calls (caution)" inline.
    try:
        from options import soir as soir_mod
        soir_by_sym: dict[str, dict] = {}
        for row in soir_mod.load_latest():
            sym = (row.get("symbol") or "").upper()
            if sym:
                soir_by_sym[sym] = row
        for m in movers:
            sym = (m.get("symbol") or "").upper()
            s = soir_by_sym.get(sym)
            if s:
                m["soir_pulse"] = {
                    "soir":              s.get("soir"),
                    "soir_percentile":   s.get("soir_percentile"),
                    "expected_move_pct": s.get("expected_move_pct"),
                    "atm_iv":            s.get("atm_iv"),
                    "signal":            s.get("signal"),
                    "reason":            s.get("reason"),
                }
    except Exception:
        # SOIR enrichment is opt-in; failures shouldn't break the tape
        pass

    # Expose the active TTL + market state so the UI can:
    #   • show "auto-refresh in 2m during premarket"
    #   • auto-force-refresh once when entering premarket if cached_count > 0
    active_ttl_sec = mv._cache_ttl_sec()
    market_phase = (
        "premarket"        if active_ttl_sec == 120 else
        "regular_hours"    if active_ttl_sec == 600 else
        "closed"
    )
    return {
        "as_of": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "min_gap_pct": min_gap_pct,
        "active_ttl_sec": active_ttl_sec,
        "market_phase": market_phase,
        "n_scanned": len(syms),
        "n_moved": len(movers),
        "n_cached": cached_count,
        "cache_ttl_min": 30,
        "force_used": force,
        "movers": movers,
    }


@router.get("/overnight/symbol/{symbol}")
async def overnight_symbol(symbol: str):
    """Full overnight picture for a single symbol — includes the news candidate list."""
    r = mv.overnight_for_symbol(symbol.upper())
    if r is None:
        return {"symbol": symbol.upper(), "error": "no data"}
    return r
