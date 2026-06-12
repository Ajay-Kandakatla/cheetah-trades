"""Racing to R1/R2 — post-breakout names in motion (Leaderboard + Portfolio).

Ajay 2026-06-12: "a section called Racing to R1 and R2 — stocks that broke
the PIVOT and are racing toward R1 and potentially R2. I may have missed the
pivot but I think these are good stocks to get into."

HONEST framing: the book buys near the pivot (TLSW pp.198-203 — buy as the
stock clears the pivot, not after it's extended). This board therefore tells
the truth about extension on every row: `in_buy_range` is true only while the
name is within the scanner's own buy-range cap past the pivot; beyond that
the row is explicitly a CHASE, shown for awareness, not a book entry.

R-ladder convention — REUSED, not invented (sepa/position_lens.py:188,
`risk_per_share = entry - stop_used`). For a setup row:

    risk = pivot - setup_stop
    R1   = pivot + 1 * risk
    R2   = pivot + 2 * risk

Display-only: feeds no score, and the Auto-Pilot does NOT trade off it.

One scanner.load_latest() + ONE bulk_live_prices() call per refresh;
projected RelVol via live_gate for at most LIVE_GATE_CAP rows (it reloads
the daily frame per symbol — heavier). 60s in-process cache so the two
pages polling this stay cheap.
"""
from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("sepa.racing")

# Mirrors scanner.BUYABLE_MAX_EXT_PCT (sepa/scanner.py:140) — the scanner's
# own "% past pivot and still in the buy zone" cap. NEVER drift these apart:
# tests/test_sepa_contracts.py cross-locks racing.RACING_BUY_RANGE_PCT ==
# scanner.BUYABLE_MAX_EXT_PCT.
RACING_BUY_RANGE_PCT = 3.0

# live_gate reloads the cached daily frame per symbol — cap how many rows get
# the projected-RelVol enrichment so the board stays fast.
LIVE_GATE_CAP = 30

CACHE_TTL_S = 60

# module-level cache: (monotonic ts, payload)
_CACHE: dict = {"ts": 0.0, "payload": None}


def _fin(x) -> Optional[float]:
    """float(x) if it is a real finite number, else None — every numeric on
    this board passes through here because the FE JSON.parses the payload."""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _r(x: Optional[float], nd: int = 2) -> Optional[float]:
    return round(x, nd) if x is not None else None


def _build_rows(max_rows: int) -> dict:
    from . import scanner, prices  # lazy — house rule

    now_iso = datetime.now(timezone.utc).isoformat()
    scan = scanner.load_latest() or {}
    empty = {"rows": [], "as_of": now_iso, "scan_ts": scan.get("generated_at")}

    # ---- 1. setup rows from the latest scan + the R ladder -----------------
    setups: dict[str, dict] = {}
    for row in scan.get("all_results") or []:
        if not (row.get("qualifier") or row.get("is_candidate")):
            continue
        es = row.get("entry_setup") or {}
        pivot, stop = _fin(es.get("pivot")), _fin(es.get("stop"))
        if not pivot or not stop or pivot <= 0 or stop <= 0 or stop >= pivot:
            continue
        sym = row.get("symbol")
        if not sym:
            continue
        risk = pivot - stop                      # position_lens.py:188 convention
        setups[sym] = {
            "row": row, "pivot": pivot, "stop": stop, "risk": risk,
            "r1": pivot + risk, "r2": pivot + 2 * risk,
            "setup_type": es.get("type"),
        }
    if not setups:
        return empty

    # ---- 2. ONE bulk live-quote call; keep names strictly past pivot, ------
    #         not yet through R2.
    quotes = prices.bulk_live_prices(list(setups.keys())) or {}
    rows: list[dict] = []
    for sym, s in setups.items():
        q = quotes.get(sym) or {}
        live = _fin(q.get("price")) or _fin(q.get("last_trade_price"))
        if live is None or live <= 0:
            continue                              # NaN / missing quote → skip, never crash
        pivot, stop, risk, r1, r2 = s["pivot"], s["stop"], s["risk"], s["r1"], s["r2"]
        if not (live > pivot and live < r2):
            continue                              # strictly past pivot, not yet through R2
        leg = "to_r1" if live < r1 else "to_r2"

        prev = _fin(q.get("prev_day_close"))
        day_pct = _r((live / prev - 1) * 100) if prev else None

        # round before comparing so live == pivot*1.03 lands INSIDE the range
        # (float noise would otherwise push exactly-3.0% to 3.0000000000000027)
        pct_past_pivot = round((live / pivot - 1) * 100, 4)
        in_buy_range = pct_past_pivot <= RACING_BUY_RANGE_PCT

        if leg == "to_r1":
            progress = (live - pivot) / (r1 - pivot)
        else:
            progress = (live - r1) / (r2 - r1)
        progress = max(0.0, min(1.0, progress))

        rows.append({
            "symbol":          sym,
            "score":           _fin(s["row"].get("score")),
            "leg":             leg,
            "live":            _r(live, 4),
            "day_pct":         day_pct,
            "pivot":           _r(pivot),
            "stop":            _r(stop),
            "risk":            _r(risk),
            "r1":              _r(r1),
            "r2":              _r(r2),
            "pct_past_pivot":  _r(pct_past_pivot),
            "in_buy_range":    bool(in_buy_range),
            "progress":        _r(progress, 4),
            # % gain still needed from the live price (negative = already past)
            "pct_to_r1":       _r((r1 - live) / live * 100),
            "pct_to_r2":       _r((r2 - live) / live * 100),
            "setup_type":      s["setup_type"],
            "is_buyable":      bool(s["row"].get("is_buyable")),
            "relvol":          None,
        })
    if not rows:
        return empty

    # ---- 3. sort: in-buy-range first, to_r1 before to_r2, progress desc ----
    rows.sort(key=lambda r: (not r["in_buy_range"],
                             r["leg"] != "to_r1",
                             -(r["progress"] or 0.0)))
    rows = rows[:max_rows]

    # ---- 4. projected RelVol — heavier per-symbol call, only for the rows --
    #         actually shown (sorted first so the cap hits the best rows),
    #         each isolated so one failure never kills the board.
    from . import live_gate as _lg
    for r in rows[:LIVE_GATE_CAP]:
        try:
            lg = _lg.live_gate(r["symbol"]) or {}
            r["relvol"] = _fin((lg.get("volume_live") or {}).get("projected_relvol"))
        except Exception as exc:
            log.debug("racing relvol failed %s: %s", r["symbol"], exc)

    return {"rows": rows, "as_of": now_iso, "scan_ts": scan.get("generated_at")}


def get_board(max_rows: int = 40) -> dict:
    """The Racing-to-R1/R2 board. 60s in-process cache — Leaderboard and
    Portfolio both poll this; within the TTL they share one payload."""
    now = time.monotonic()
    if _CACHE["payload"] is not None and now - _CACHE["ts"] < CACHE_TTL_S:
        return _CACHE["payload"]
    payload = _build_rows(max_rows)
    _CACHE["ts"], _CACHE["payload"] = now, payload
    return payload
