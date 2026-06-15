"""Breakout COUNT board + per-symbol read — "how often does this name actually
break out, and on what ACTUAL volume?" (Ajay 2026-06-13).

Display-only. Reads `volume.analyze()`'s `breakout_count` (distinct
volume-confirmed breakouts over the trailing ~year, book p.203 definition:
volume > 1.5× the 50-day average AND a close above the prior 21-bar high) plus
the actual `last_vol` / `avg_vol_50` so the UI can show real share counts, not
just a "2.4×" ratio. Never feeds the score.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("sepa.breakout")


def _row(symbol: Optional[str], vol: Optional[dict],
         last_close=None, name=None) -> Optional[dict]:
    if not symbol or not vol:
        return None
    bc = vol.get("breakout_count")
    if bc is None:
        return None
    return {
        "symbol":              str(symbol).upper(),
        "name":                name,
        "breakout_count":      int(bc),
        "window_bars":         int(vol.get("breakout_window_bars") or 0),
        "last_vol":            vol.get("last_vol"),
        "avg_vol_50":          vol.get("avg_vol_50"),
        "days_since_breakout": vol.get("days_since_breakout"),
        "high_vol_breakout":   bool(vol.get("high_vol_breakout")),
        "last_close":          last_close,
    }


def leaders(top: int = 30) -> dict:
    """Top names by breakout count from the latest scan — the Leaderboard board."""
    from sepa import scanner
    scan = scanner.load_latest() or {}
    rows = []
    for r in scan.get("all_results") or []:
        row = _row(r.get("symbol"), r.get("volume"), r.get("last_close"), r.get("name"))
        if row:
            rows.append(row)
    rows.sort(key=lambda x: (-x["breakout_count"], x["symbol"]))
    return {"rows": rows[:top], "scan_ts": scan.get("generated_at"), "n": len(rows)}


def for_symbol(symbol: str) -> dict:
    """Per-symbol breakout read — used by the Portfolio holding chip, since a held
    name isn't always in the latest scan. Loads its prices + runs volume.analyze."""
    sym = (symbol or "").upper().strip()
    try:
        from sepa import prices, volume
        df = prices.load_prices(sym)
        if df is None or len(df) == 0:
            return {"ok": False, "symbol": sym}
        vol = volume.analyze(df)
        row = _row(sym, vol, float(df["close"].iloc[-1]))
        if row:
            return {"ok": True, **row}
    except Exception as exc:                           # noqa: BLE001
        log.debug("breakout.for_symbol(%s) failed: %s", sym, exc)
    return {"ok": False, "symbol": sym}


def history_for_symbol(symbol: str) -> dict:
    """Per-symbol breakout HISTORY for the drill chart — "where did each breakout
    actually fire?" (Ajay 2026-06-15). Returns the trailing-year close/volume
    series PLUS the breakout markers (same definition as the count, via
    volume.breakout_points), so the modal can plot the line and pin a 🚀 at
    every breakout bar:

        {ok, symbol, last_close, breakout_count, window_bars, avg_vol_50,
         series:    [{date, close, volume}, ...],   # oldest -> newest
         breakouts: [{date, close, volume, vol_ratio}, ...]}

    Display-only. Soft-fails to {ok: False, symbol}."""
    sym = (symbol or "").upper().strip()
    try:
        from sepa import prices, volume
        df = prices.load_prices(sym)
        if df is None or len(df) == 0:
            return {"ok": False, "symbol": sym}
        window = df.iloc[-volume.BREAKOUT_COUNT_LOOKBACK:]
        series = [
            {
                "date":   volume._date_str(idx),
                "close":  round(float(prow["close"]), 4),
                "volume": int(prow["volume"]),
            }
            for idx, prow in window.iterrows()
        ]
        vol = volume.analyze(df) or {}
        return {
            "ok":             True,
            "symbol":         sym,
            "last_close":     round(float(df["close"].iloc[-1]), 4),
            "breakout_count": vol.get("breakout_count"),
            "window_bars":    int(len(window)),
            "avg_vol_50":     vol.get("avg_vol_50"),
            "series":         series,
            "breakouts":      volume.breakout_points(df),
        }
    except Exception as exc:                           # noqa: BLE001
        log.debug("breakout.history_for_symbol(%s) failed: %s", sym, exc)
    return {"ok": False, "symbol": sym}
