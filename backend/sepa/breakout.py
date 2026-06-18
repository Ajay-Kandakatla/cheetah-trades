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


def _verdict_for(r: dict) -> Optional[dict]:
    """The row's Minervini+Bonde verdict — CONFIRMED even when the persisted scan
    didn't annotate it (e.g. a scan written by an older worker). The scan row
    always carries the price-side fields buyable_verdict.compute() needs
    (is_candidate / is_buyable / stage), so we recompute on the fly rather than
    show "verdict pending". ETFs get no Minervini verdict (the page says so)."""
    bv = r.get("buy_verdict")
    if bv is not None:
        return bv
    if r.get("is_etf"):
        return None
    try:
        from sepa import buyable_verdict
        return buyable_verdict.compute(r)
    except Exception:                               # noqa: BLE001
        return None


def board(top: int = 250, min_count: int = 1) -> dict:
    """Rich breakout-ranked board for the dedicated /breakouts page (Ajay
    2026-06-16: "a page to track only breakouts and # of breakouts, highest
    first ... some passing Minervinis and some not, and Bonde, but mainly around
    breakouts").

    Every name in the latest scan that has actually broken out (>= ``min_count``
    volume-confirmed breakouts over the trailing year), ranked by breakout COUNT
    descending, each carrying the Minervini+Bonde ``buy_verdict`` (see
    sepa/buyable_verdict.py) plus RS / stage / day-change context so the page can
    slice "passing Minervinis vs not" without another fetch. Display-only.
    """
    from sepa import scanner
    scan = scanner.load_latest() or {}
    rows = []
    for r in scan.get("all_results") or []:
        base = _row(r.get("symbol"), r.get("volume"), r.get("last_close"), r.get("name"))
        if not base or base["breakout_count"] < min_count:
            continue
        stage = r.get("stage") or {}
        # R1/R2 = the trade-plan R-multiple targets (entry + 1R / +2R, see
        # analysis/trade_plan._targets) — the overhead levels a breakout is
        # "marching toward". Carried so the page can show distance-to-target
        # without re-fetching the full plan (Ajay 2026-06-16: "if they are s2
        # and if they marching towards r1 or r2"). None when no usable plan.
        targets = (r.get("trade_plan") or {}).get("targets") or {}
        rows.append({
            **base,
            "broke_out_today": base.get("days_since_breakout") == 0,
            "day_change_pct":  r.get("day_change_pct"),
            "rs_rank":         r.get("rs_rank"),
            "stage":           stage.get("stage") if isinstance(stage, dict) else None,
            "stage_label":     stage.get("label") if isinstance(stage, dict) else None,
            "r1":              targets.get("r1"),
            "r2":              targets.get("r2"),
            "industry":        r.get("industry"),
            "is_etf":          bool(r.get("is_etf")),
            "buy_verdict":     _verdict_for(r),
        })
    # Highest breakout count first; RS then symbol break ties deterministically.
    rows.sort(key=lambda x: (-x["breakout_count"], -(x.get("rs_rank") or 0), x["symbol"]))
    rows = rows[:top]

    # Beta (1y daily vs SPY) for the displayed names only — the volatility
    # column + "sort by low volatility" on the page. Computed here (≤top names,
    # SPY loaded once, per-symbol day-cache) so it doesn't touch the scan hot
    # path. Display-only; None on any failure (never blocks the board).
    try:
        from sepa import beta as _beta
        _betas = _beta.betas_for([x["symbol"] for x in rows])
    except Exception as exc:                        # noqa: BLE001
        log.debug("board: beta batch failed: %s", exc)
        _betas = {}
    for x in rows:
        x["beta"] = _betas.get(x["symbol"])

    def _mp(x):
        return ((x.get("buy_verdict") or {}).get("minervini") or {}).get("passed")

    def _bp(x):
        return ((x.get("buy_verdict") or {}).get("bonde") or {}).get("passed")

    summary = {
        "total":           len(rows),
        "broke_out_today": sum(1 for x in rows if x["broke_out_today"]),
        "minervini_pass":  sum(1 for x in rows if _mp(x) is True),
        "minervini_fail":  sum(1 for x in rows if _mp(x) is False),
        "bonde_pass":      sum(1 for x in rows if _bp(x) is True),
        "bonde_fail":      sum(1 for x in rows if _bp(x) is False),
        "both_pass":       sum(1 for x in rows if (x.get("buy_verdict") or {}).get("both_pass")),
    }
    return {"rows": rows, "scan_ts": scan.get("generated_at"), "n": len(rows), "summary": summary}


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
