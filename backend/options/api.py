"""FastAPI handlers for the options analytics module."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from . import soir as soir_mod
from . import scanner as soir_scanner
from . import tomorrow_bias as bias_mod

log = logging.getLogger("options.api")
router = APIRouter(tags=["options"])


@router.get("/options/bias/{symbol}")
async def get_tomorrow_bias(symbol: str):
    """Per-ticker Tomorrow Bias — overnight/after-hours move + options flow +
    market backdrop → a single LEAN_UP / LEAN_DOWN / NEUTRAL for the next open,
    with a confluence-gated confidence. Powers the options-flow tab block.

    Computed on-demand: reads the cached SOIR snapshot (no fresh chain pull),
    the latest extended-hours bars, and the cached market backdrop. Degrades to
    NEUTRAL ("react at the open") when there's no extended-hours move yet.
    """
    import asyncio
    out = await asyncio.to_thread(bias_mod.compute_bias, symbol.upper())
    return out


@router.get("/options/market-bias")
async def get_market_bias():
    """Market-level Tomorrow Bias — SPY/QQQ extended-hours gap (the ES/NQ proxy)
    + VIX + regime → one market lean for the next session. Powers the Overnight
    page panel. Cached ~3 min via the shared backdrop."""
    import asyncio
    return await asyncio.to_thread(bias_mod.market_bias)


@router.get("/options/opex/{symbol}")
async def get_opex(symbol: str):
    """OpEx mechanics for one ticker — nearest expiration (+ type/DTE), the
    max-pain magnet strike, and a dealer-gamma pinning/amplifying read with the
    call/put gamma walls. Powers the options-flow tab OpEx panel.

    A tendency into expiration, not a guarantee; the gamma sign is a heuristic
    most reliable on index/ETF and weakest on single-name leaders."""
    import asyncio
    from . import opex as opex_mod
    out = await asyncio.to_thread(opex_mod.compute_opex, symbol.upper())
    if not out:
        return {"symbol": symbol.upper(), "found": False,
                "message": "No options chain for this ticker (illiquid or no listed options)."}
    return {"found": True, **out}


@router.get("/options/soir")
async def get_soir_scan(
    signal: Optional[str] = Query(None, description="Filter to BULLISH | BEARISH | WATCH | NEUTRAL"),
    limit:  int = Query(50, ge=1, le=200),
):
    """Latest SOIR scan results, sorted by signal strength.

    Default: returns the three top-pick lists (bullish/bearish/watch)
    derived from the most recent scanner run. Pass `signal=BULLISH` to
    flatten to a single sorted list.
    """
    rows = soir_mod.load_latest()
    if not rows:
        return {
            "as_of":   None,
            "rows":    [],
            "message": "No SOIR scan yet — run cron or POST /options/soir/refresh",
        }

    # Sort by absolute distance from neutral (stronger signals first)
    def _strength(r: dict) -> float:
        pct = r.get("soir_percentile")
        if pct is None:
            return -1.0
        return abs(pct - 50.0)

    rows.sort(key=lambda r: -_strength(r))

    if signal:
        sig = signal.upper()
        rows = [r for r in rows if r.get("signal") == sig]

    return {
        "as_of": rows[0].get("scanned_at") if rows else None,
        "rows":  rows[:limit],
        "n":     len(rows),
        "filter_signal": signal.upper() if signal else None,
    }


SOIR_STALE_HOURS = 24


def _soir_row_is_stale(row: dict, now=None) -> bool:
    """True when the snapshot is older than SOIR_STALE_HOURS (or undated).

    Self-healing hook (2026-07-06): names outside every scan universe — the
    UI watchlist lives client-side, so the nightly cron can't see it — used
    to serve 5-week-old SOIR forever (AMBA/CRWV). Viewing a ticker now
    freshens it in the background."""
    from datetime import datetime, timedelta
    ts = row.get("scanned_at") or row.get("as_of")
    if ts is None:
        return True
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", ""))
        except Exception:
            return True
    now = now or datetime.utcnow()
    try:
        return (now - ts) > timedelta(hours=SOIR_STALE_HOURS)
    except Exception:
        return True


def _background_scan_one(sym: str) -> None:
    try:
        sepa_record = None
        try:
            from sepa import scanner as sepa_scanner
            latest = sepa_scanner.load_latest() or {}
            sepa_record = next((c for c in (latest.get("all_results") or [])
                                if c.get("symbol") == sym), None)
        except Exception:
            pass
        snap = soir_mod.compute_for_symbol(sym, sepa_record)
        if snap:
            soir_mod.save_latest([snap])
            log.info("soir self-heal: refreshed stale snapshot for %s", sym)
    except Exception as exc:
        log.warning("soir self-heal failed for %s: %s", sym, exc)


@router.get("/options/soir/{symbol}")
async def get_soir_for_symbol(symbol: str, background_tasks: BackgroundTasks):
    """SOIR snapshot + Schaeffer signal for a single ticker. Serves the most
    recent cached snapshot instantly; when that snapshot is older than 24h
    (ticker outside the nightly universe), a background refresh is kicked so
    the NEXT view is fresh — `refreshing: true` flags it.
    """
    sym = symbol.upper()
    rows = soir_mod.load_latest(symbol=sym)
    if not rows:
        return {"symbol": sym, "found": False,
                "message": "No SOIR data yet for this ticker — wait for next scan."}
    row = rows[0]
    refreshing = _soir_row_is_stale(row)
    if refreshing:
        background_tasks.add_task(_background_scan_one, sym)
    return {"symbol": sym, "found": True, "refreshing": refreshing, **row}


@router.post("/options/soir/refresh")
async def refresh_soir(
    background_tasks: BackgroundTasks,
    symbols: Optional[str] = Query(None, description="comma-separated symbols; omit for full SEPA universe"),
):
    """Trigger a SOIR scan in the background. Also runs an immediate
    re-classification on existing rows so the page updates instantly with
    refreshed trend + fundamental pillars (without waiting 5-15min for
    the new chain fetches to complete).

    The two-step flow:
      1. INSTANT (synchronous): re-classify existing soir_latest rows
         using current SEPA trend/score → page shows updated signals NOW.
      2. BACKGROUND: re-fetch all chains for fresh OI numbers → eventual
         consistency once the scan completes.
    """
    universe = None
    if symbols:
        universe = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    # Instant re-classify so the page isn't empty for 10 minutes
    instant = soir_mod.reclassify_latest()

    def _run():
        try:
            soir_scanner.run(universe_override=universe)
        except Exception as exc:
            log.exception("background SOIR scan failed: %s", exc)

    background_tasks.add_task(_run)
    return {
        "status":  "scan_started",
        "message": ("Re-classified existing rows now; fresh chain scan running "
                    "in background. Poll /options/soir for results."),
        "universe_override": universe,
        "instant_reclassify": instant,
    }


@router.post("/options/soir/reclassify")
async def reclassify_only():
    """Re-run the Schaeffer classifier over every row in soir_latest using
    the current SEPA trend + score, WITHOUT fetching any options chains.
    Cheap (~1s) — use after fixing the classifier or when SEPA scan refreshes.
    """
    return soir_mod.reclassify_latest()


@router.post("/options/soir/scan_one/{symbol}")
async def scan_one(symbol: str):
    """Synchronously fetch + persist a single ticker's SOIR snapshot.

    Designed for the SEPA-detail Options Flow tab's "Scan options flow"
    CTA. With the Massive Options Advanced plan a chain pull is ~200ms,
    so we can block the request and return the snapshot in one round-trip
    instead of the previous fire-and-poll pattern.

    `compute_for_symbol` already runs the three-pillar Schaeffer classifier
    inline (using SEPA trend/score from the latest cached scan when
    available), so we just persist + return.

    Added 2026-05-24 alongside the $200 Massive plan migration. The older
    background-task path (`POST /options/soir/refresh`) stays for the
    full-universe scan that the nightly cron uses.
    """
    sym = symbol.upper()
    import asyncio
    # Pull the SEPA record so the Schaeffer trend pillar gets populated.
    # Falls back to None if SEPA hasn't scanned this ticker yet — the
    # classifier degrades to NEUTRAL with a "no SEPA context" reason.
    sepa_record = None
    try:
        from sepa import scanner as sepa_scanner
        latest = sepa_scanner.load_latest() or {}
        sepa_record = next(
            (c for c in (latest.get("all_results") or []) if c.get("symbol") == sym),
            None,
        )
    except Exception as exc:
        log.warning("scan_one %s: SEPA lookup failed: %s", sym, exc)

    snap = await asyncio.to_thread(soir_mod.compute_for_symbol, sym, sepa_record)
    if not snap:
        return {"symbol": sym, "found": False,
                "message": "Massive returned no chain for this ticker — "
                           "likely illiquid, ADR with thin options, or invalid symbol."}
    soir_mod.save_latest([snap])
    return {"symbol": sym, "found": True, **snap}


@router.get("/options/gex-board")
async def get_gex_board():
    """Cross-sectional GEX board (2026-07-17): the latest nightly snapshot's
    universe bucketed 🟢 bullish / 🔴 bearish / mixed on the dealer-gamma
    regime + the zero-gamma flip, each row carrying its key nodes (call wall,
    put wall, flip, magnet) + net GEX/VEX dollars. Pure Mongo read — the
    17:50 ET cron (or POST refresh) populates it."""
    import asyncio
    from . import gex_history
    return await asyncio.to_thread(gex_history.board)


@router.post("/options/gex-board/add/{symbol}")
async def add_gex_board_symbol(symbol: str):
    """Add ONE ticker to today's board on demand (earnings movers the
    tracked universe doesn't know yet — Ajay 2026-08-03 PLTR/SNAP). One
    Massive chain pull (~1s); 404 when the name has no options chain."""
    import asyncio
    from . import gex_history
    row = await asyncio.to_thread(gex_history.add_symbol, symbol)
    if row is None:
        raise HTTPException(404, "no options chain for %s — illiquid, "
                                 "invalid, or Massive has no data"
                                 % symbol.upper())
    return row


@router.post("/options/gex-board/refresh")
async def refresh_gex_board():
    """On-demand re-snapshot of the GEX universe (same job the 17:50 cron
    runs — portfolio + watchlists + SOIR bullish/watch + top SEPA). Threaded;
    ~30-60s for the ~200-name universe. Returns the run summary."""
    import asyncio
    from . import gex_history
    return await asyncio.to_thread(gex_history.run)


@router.get("/options/gex-history/{symbol}")
async def get_gex_history(symbol: str, days: int = Query(90, ge=1, le=365)):
    """Daily dealer-GEX ledger for one ticker (regime, net GEX, max-pain vs
    spot, walls) — recorded by the 17:50 ET cron so 'did GEX flag this move?'
    can be answered from data instead of a post-move guess."""
    from . import gex_history
    rows = gex_history.series(symbol.upper(), days=days)
    return {"symbol": symbol.upper(), "days": days, "rows": rows,
            "note": ("Recording began 2026-07-06 — the series fills in one "
                     "row per trading day from here.")}


# ---------------------------------------------------------------------------
# Historical scrub — mirrors /sepa/history/* shape so the frontend pattern
# (date scrubber + SepaScanByDate adaptation) ports cleanly.
# ---------------------------------------------------------------------------
@router.get("/options/soir/history/runs")
async def soir_history_runs(limit: int = Query(60, ge=1, le=200)):
    """List of dates we have SOIR history for, newest first."""
    return {"runs": soir_mod.list_run_dates(limit=limit)}


@router.get("/options/soir/history/date/{date_iso}")
async def soir_history_by_date(date_iso: str):
    """Full SOIR snapshot as it stood on the given date (YYYY-MM-DD).

    Re-runs the Schaeffer classifier using historical percentile. The
    technical (trend) and fundamental (SEPA score) pillars aren't
    re-derived from history — only the sentiment pillar is fully
    historical. Use for "what would I have seen on day X" review.
    """
    run = soir_mod.get_scan_by_date(date_iso)
    if not run:
        raise HTTPException(404, f"no SOIR history for {date_iso}")
    return run


@router.get("/options/soir/history/{symbol}")
async def soir_history_for_symbol(symbol: str, days: int = Query(90, ge=1, le=365)):
    """Trajectory of one ticker's SOIR over the last N days. Useful for
    plotting "is the options crowd getting more bearish on AAPL?" over time.
    """
    return {
        "symbol":   symbol.upper(),
        "days":     days,
        "snapshots": soir_mod.get_symbol_history(symbol, days=days),
    }


__all__ = ["router"]
