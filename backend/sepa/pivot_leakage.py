"""Leaky-pivot read — shared by the Auto-Pilot engine and the SEPA scanner.

Primary source (NOT a book page) — Minervini on X, 2026:
    "…the dominant theme is right-side volatility — which often starts as
    pivot leakage… for truly low-risk buy points to emerge, that volatility
    needs to subside. Patience is key. Let the setups come to you."
    https://x.com/markminervini/status/2029213943428698253

A LEAK is a completed daily bar whose high poked above the pivot but whose
close fell back below it — a breakout attempt that failed to hold. When
>= PIVOT_LEAK_MAX leaks exist in the last PIVOT_LEAK_LOOKBACK completed bars
AND the latest is <= PIVOT_LEAK_COOLOFF_DAYS bars ago, the pivot is "leaky":
its right side is volatile and the low-risk buy point hasn't formed yet.
A full close ABOVE the pivot is the volatility subsiding — consumers treat
that as clearing the read (the engine's close-confirm path is exempt).

The numbers are OWNER choices (Ajay sign-off 2026-07-12), locked in
tests/test_trading_contracts.py. Missing/garbage data reads NOT leaky (fail
open): this is a veto heuristic layered on top of the required book gates
(trend, stage, setup, volume) — a price-cache hiccup must never block or
un-rank an otherwise-valid setup.

STDLIB-ONLY on purpose: trading/auto_entry.py imports this at module level
and must stay pandas-free at import time.
"""
from __future__ import annotations

PIVOT_LEAK_LOOKBACK = 10
PIVOT_LEAK_MAX = 2
PIVOT_LEAK_COOLOFF_DAYS = 5


def pivot_leaky(highs, closes, pivot) -> tuple:
    """The pure read (bars oldest -> newest, completed bars only).
    Returns (leaky, detail-dict) — detail is JSON-safe for scan rows and
    the engine's per-symbol checks snapshot."""
    detail = {"leaks": 0, "last_leak_bars_ago": None,
              "lookback": PIVOT_LEAK_LOOKBACK, "max": PIVOT_LEAK_MAX,
              "cooloff": PIVOT_LEAK_COOLOFF_DAYS}
    try:
        pivot = float(pivot)
        pairs = list(zip(list(highs or []), list(closes or [])))
    except (TypeError, ValueError):
        return False, detail
    if pivot <= 0 or not pairs:
        return False, detail
    leaks = 0
    last_ago = None
    window = pairs[-PIVOT_LEAK_LOOKBACK:]
    m = len(window)
    for i, (hi, cl) in enumerate(window):
        try:
            if float(hi) > pivot and float(cl) < pivot:
                leaks += 1
                last_ago = m - i
        except (TypeError, ValueError):
            continue
    detail["leaks"] = leaks
    detail["last_leak_bars_ago"] = last_ago
    leaky = bool(leaks >= PIVOT_LEAK_MAX and last_ago is not None
                 and last_ago <= PIVOT_LEAK_COOLOFF_DAYS)
    return leaky, detail


def leakage_block(df, pivot) -> dict:
    """Scanner-side convenience: the JSON block stamped on a scan row.
    `df` is the daily OHLCV frame (completed bars — at the 16:30 scan
    today's bar is complete and counts). Returns {leaky, leaks,
    last_leak_bars_ago} — always the full shape so the FE can rely on it."""
    try:
        tail = df.iloc[-PIVOT_LEAK_LOOKBACK:]
        highs = [float(v) for v in tail["high"]]
        closes = [float(v) for v in tail["close"]]
    except Exception:                              # noqa: BLE001
        highs, closes = [], []
    leaky, detail = pivot_leaky(highs, closes, pivot)
    return {"leaky": leaky, "leaks": detail["leaks"],
            "last_leak_bars_ago": detail["last_leak_bars_ago"]}
