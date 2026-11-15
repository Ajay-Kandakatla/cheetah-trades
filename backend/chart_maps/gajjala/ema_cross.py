"""🔀 ema_cross — THE fast / slow EMA cross engine (9 over / under 21 by default), pure, closed bars only (2026-11-15).

Ajay, verbatim (2026-11-15): "I like how you put the 9 EMA and 21 ema cross over for OMH can you add an alert in
horizonal fade when that happens?" · "For any stocks that crossing over and add the same feedback in to that horizontal
fade charts".

ONE engine, no sub and no timeframe of its own: the ➖ Fade card marks (tab.ema_cross_block, over the card's served
curves), the ➖ Fade push (alerts.run_fade_cross, over the pass's Frame) and any later board (1 / 3 / 5-minute charts)
call it. The EMA is the house one (orderflow.signals.ema through bars._masked_ema — the warm-up masked to None, never a
guess); the spans default to constants EMA_FAST / EMA_SLOW (9 / 21), read at CALL time. Nothing here is a threshold,
a gate or an A+ rule: a cross is information only.

THE RULE (bar i, both bars closed, all four EMA values finite):
  up   = fast[i] >  slow[i]  and fast[i − 1] <= slow[i − 1]
  down = fast[i] <  slow[i]  and fast[i − 1] >= slow[i − 1]
A bar whose EMAs are still warming up, a NaN, a bool or junk is not judgeable — never a cross. The bar still printing is
never judged: the caller hands closed bars (bars.closed_only / the stored tile), and `crosses(..., through=stamp)` drops
every bar stamped after `through` (a live overlay bar).

API (stable):
  crosses(bars, fast=None, slow=None, *, start=0, through=None) -> [cross]
      bars = closed bars oldest first, each {"t": "YYYY-MM-DD HH:MM" (the bar's CLOSE, ET), "c": close} (the house tile
      shape; extra keys ignored). EMAs run over ALL the bars handed in (hand the prior session for warm-up) and crosses
      are judged from index `start` on.
  crosses_from_emas(ema_fast, ema_slow, ts, closes=None, idx=None) -> [cross]
      the core over already-computed, index-aligned EMA series (a Frame's ema9 / ema21, a card's curves).
  frame_crosses(F) -> [cross]           a bars.Frame's TODAY bars (its own ema9 / ema21).
  session_crosses(xs, session) -> [cross]   only the crosses whose stamp is on that ET session date.
  latest_up_cross(xs, session=None) -> cross | None   the last UP cross (of that session when given).
  cross = {"i": index in the input, "ts": stamp, "dir": "up" | "down", "ema_fast": float, "ema_slow": float,
           "close": float | None}
"""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Optional

from . import constants as GC

UP = "up"
DOWN = "down"
DIRS = (UP, DOWN)


def _num(x) -> Optional[float]:
    """A finite number, else None (None / NaN / inf / bool / junk)."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    x = float(x)
    return x if math.isfinite(x) else None


finite = _num                                           # public: the same finite-number read for callers (alerts' floor)


def crosses_from_emas(ema_fast, ema_slow, ts, closes=None, idx=None) -> list:
    """Every cross over index-aligned series; `idx` = the indices to judge (None = every bar). The prior bar i − 1 may sit
    outside `idx` (a Frame's prior-session bar warms the first bar of today). Never raises on short / ragged input."""
    fast, slow, ts = list(ema_fast or []), list(ema_slow or []), list(ts or [])
    cl = list(closes or [])
    n = min(len(fast), len(slow), len(ts))
    out = []
    for i in (idx if idx is not None else range(n)):
        if isinstance(i, bool) or not isinstance(i, int) or i < 1 or i >= n:
            continue
        a1, b1, a0, b0 = _num(fast[i]), _num(slow[i]), _num(fast[i - 1]), _num(slow[i - 1])
        if a1 is None or b1 is None or a0 is None or b0 is None:
            continue
        if a1 > b1 and a0 <= b0:
            d = UP
        elif a1 < b1 and a0 >= b0:
            d = DOWN
        else:
            continue
        out.append({"i": i, "ts": ts[i], "dir": d, "ema_fast": a1, "ema_slow": b1,
                    "close": _num(cl[i]) if i < len(cl) else None})
    return out


def crosses(bars, fast: Optional[int] = None, slow: Optional[int] = None, *, start: int = 0,
            through: Optional[str] = None) -> list:
    """Crosses over closed bars ({"t", "c"} oldest first). A bar without a stamp or a finite close is dropped first; with
    `through`, every bar stamped after it is dropped too (the live bar). `i` indexes the KEPT bars."""
    import pandas as pd
    from .bars import _masked_ema                               # the pass's ONE EMA rule (signals.ema + warm-up mask)
    f = int(fast if fast is not None else GC.EMA_FAST)
    s = int(slow if slow is not None else GC.EMA_SLOW)
    kept = [b for b in (bars or []) if isinstance(b, dict) and isinstance(b.get("t"), str) and b.get("t")
            and _num(b.get("c")) is not None and (through is None or b["t"] <= through)]
    if not kept:
        return []
    close = pd.Series([float(b["c"]) for b in kept])
    e_f, e_s = _masked_ema(close, f), _masked_ema(close, s)
    return crosses_from_emas(e_f, e_s, [b["t"] for b in kept], list(close), range(max(0, int(start)), len(kept)))


def frame_crosses(F) -> list:
    """crosses_from_emas over a bars.Frame's TODAY bars (its ema9 / ema21 — computed with EMA_FAST / EMA_SLOW)."""
    if F is None:
        return []
    return crosses_from_emas(F.ema9, F.ema21, F.t, F.c, F.today)


def _iso(session) -> str:
    return session.isoformat()[:10] if isinstance(session, (date, datetime)) else str(session or "")[:10]


def session_crosses(xs, session) -> list:
    """The crosses whose stamp is on the ET session date `session` (a stamp "YYYY-MM-DD HH:MM" = the bar's close)."""
    d = _iso(session)
    return [x for x in (xs or []) if isinstance(x, dict) and str(x.get("ts") or "")[:10] == d] if d else []


def latest_up_cross(xs, session=None) -> Optional[dict]:
    """The last UP cross of `xs` (only that session's when given), else None."""
    pool = session_crosses(xs, session) if session is not None else list(xs or [])
    ups = [x for x in pool if isinstance(x, dict) and x.get("dir") == UP]
    return ups[-1] if ups else None


__all__ = ["UP", "DOWN", "DIRS", "finite", "crosses", "crosses_from_emas", "frame_crosses", "session_crosses",
           "latest_up_cross"]
