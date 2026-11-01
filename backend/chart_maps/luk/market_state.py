"""🥇 Luk's market state — a WORD for QQQ and IWM, never a gate (BUILD SPEC luk-tab §3.5, HIS CALL #8 / #18).

He reads the Qs and IWM every day (VKNEJA5r8zw 3:47:45); "if the indices is uh trending down the 9 EMA is under the 21
favorable time for doing a long" (lS9zbnLi1Gg 1:57:45 — the caption drops the "not"). The 9 / 21 order and the distance
to the 9 EMA are served as facts; his "almost 2% above the 9 EMA" (297D7gVsLY4 1:02:42) was an example, not a
threshold — no number is applied here.
"""
from __future__ import annotations

from typing import Optional

from chart_maps.luk import constants as LC

WORD_UNDER = "{sym}: 9 EMA under 21 — his not-favourable-for-longs read"
WORD_OVER = "{sym}: 9 EMA over 21"
WORD_NONE = "{sym}: daily bars not cached — no read"
DIST_TEXT = "{sym} {pct:+.1f}% vs its 9 EMA"
TITLE = "🧭 Indices"
NOTE = ("A state word, never a gate (HIS CALL #8). He reads the Qs and IWM every day (VKNEJA5r8zw 3:47:45); 'almost 2% "
        "above the 9 EMA' (297D7gVsLY4 1:02:42) was an example, not a threshold — no number is applied here.")


def _num(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def word(sym: str, state) -> str:
    """WORD_UNDER when the 9 EMA is strictly under the 21, WORD_OVER otherwise (equal included); WORD_NONE when the
    state is None or an EMA is missing."""
    if not isinstance(state, dict):
        return WORD_NONE.format(sym=sym)
    e9, e21 = _num(state.get("ema9")), _num(state.get("ema21"))
    if e9 is None or e21 is None:
        return WORD_NONE.format(sym=sym)
    return (WORD_UNDER if e9 < e21 else WORD_OVER).format(sym=sym)


def dist_text(sym: str, state) -> Optional[str]:
    """The close's distance to its 9 EMA as a fact ("QQQ +1.8% vs its 9 EMA"); None when it cannot be computed."""
    if not isinstance(state, dict):
        return None
    pct = _num(state.get("dist_9_pct"))
    if pct is None:
        close, e9 = _num(state.get("close")), _num(state.get("ema9"))
        if close is None or e9 is None or e9 == 0:
            return None
        pct = (close / e9 - 1.0) * 100.0
    return DIST_TEXT.format(sym=sym, pct=pct)


def block(states: dict) -> dict:
    """{"title", "rows": [{"symbol", "text", "dist_text"}], "note"} — one row per LUK_INDEX_SYMBOLS, in that order (a
    symbol missing from `states` reads WORD_NONE)."""
    states = states if isinstance(states, dict) else {}
    rows = []
    for sym in LC.LUK_INDEX_SYMBOLS:
        st = states.get(sym)
        rows.append({"symbol": sym, "text": word(sym, st), "dist_text": dist_text(sym, st)})
    return {"title": TITLE, "rows": rows, "note": NOTE}
