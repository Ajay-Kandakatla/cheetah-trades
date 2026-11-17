"""🚩 Gajjala card → the three-chart view (spec ggcard3 §3.1, WP-C, 2026-11-16).

Ajay, verbatim (2026-11-16): "Also when I click on a card from any of the Gajjala I would like us to open the 3 chart
extension like in the Watch list... Also put a SEPA page link for it separaetely on the card I I want to but default its
3 chart extension with 1 min, 3 min and 5 mins" and then "Actually instead of 3 mins make it 15 mins timeframe".

ONE read-only GET (`API_PATH`) serves a card name's three frames — 15m / 5m / 1m, big → small (HIS CALL #1) — off the
read docs the 🚩 5-minute pass and the 1-minute loop ALREADY store: the GG5 doc holds 15m + 5m, the GG1 doc holds 1m
(no GG5 doc → GG1's own 5m frame). Nothing is fetched, nothing is written, no frame is rebuilt from another: the stored
frame is read through `tab._tile_frame` (the ONE reader), laid on the Watch's 04:00 axis (`gajjala_watch.build.axis`)
with ONE end computed from ALL three frames' bars (`build.axis_end` — [C2]: a 15m bar that closes after the RTH cut
moves every frame's end to the extended close, so no bar sits off the right edge), and its 9/21 blinker read by THE
engine (`chart_maps.ema_blink.block_from_curves`).

[C3] Each frame carries ITS OWN source stamp (`as_of_et` = the source doc's `at`, the Watch's `_clock`) and stale flag:
in the pass window, older than `variant.stale_after_sec` of the variant whose doc it is (GG5 → STALE_AFTER_SEC, GG1 →
GG1M_STALE_AFTER_SEC, read BY NAME at call time — no number here). A doc with no readable `at` → no stamp, not stale.
A frame with no stored bars serves `empty_text`, never an empty chart. No owner gate — the same audience as the cards.
Display only: no rule, gate, push or trade reads this. UNMEASURED — a chart view is information, not an entry.
"""
from __future__ import annotations

import logging
import math
from datetime import timedelta
from typing import Optional

import pandas as pd

from chart_maps import ema_blink as EB
from chart_maps.gajjala import bars as B
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import build as BLD
from chart_maps.gajjala_watch import payload as PL

log = logging.getLogger("chart_maps.gajjala.card_frames")

API_BASE = "/chart-maps/gajjala/frames"            # == FE lib/gajjalaCardView.GGC_PATH (a source-read test pins it)
API_PATH = API_BASE + "/{symbol}"
FRAMES = (("15m", "15min"), ("5m", "5min"), ("1m", "1min"))   # big → small (= FE GGC_STRETCH_ORDER; HIS CALL #1)
SOURCE = {"15m": V.GG5, "5m": V.GG5, "1m": V.GG1}             # which variant's stored read doc holds each frame
FALLBACK_5M = V.GG1                                            # no GG5 doc → GG1's own 5m frame (the same pipeline)

EMPTY_TEXT = "No {minutes}-minute bars stored for {sym} this session yet — a pass has to read it first"
NO_FRAMES_TEXT = "No bars stored for {sym} this session yet"
BAD_SYMBOL_TEXT = "Not a ticker"


def frame_minutes(tf: str) -> int:
    """The frame's length in minutes from its rule in FRAMES (the Watch's `_frame_min` rule)."""
    return int(pd.Timedelta(dict(FRAMES)[tf]).total_seconds() // 60)


def frame_words(tf: str) -> str:
    return f"{frame_minutes(tf)}-min"


def frame_stale(at, now, in_window: bool, v) -> bool:
    """The Watch's stale formula (gajjala_watch.payload.pass_block) with the threshold of the variant whose doc it is,
    `variant.stale_after_sec(v)` — read at call time. Out of the window → never stale; an unreadable stamp → False."""
    at_et = PL._to_et(at)
    if not in_window or at_et is None:
        return False
    return bool((now - at_et) > timedelta(seconds=V.stale_after_sec(V.of(v))))


def _last_finite(vals) -> Optional[float]:
    for x in reversed(vals if isinstance(vals, list) else []):
        if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x):
            return float(x)
    return None


def ema_tail(curves) -> Optional[dict]:
    """{"ema9", "ema21"} = the LAST finite stored value of each curve (the engine's 6-dp values, bars._masked_ema);
    None when either curve is absent or holds no finite value."""
    by = {c.get("tone"): c.get("values") for c in (curves or []) if isinstance(c, dict)}
    out = {}
    for tone, _label, _period in B.EMA_TONES:
        v = _last_finite(by.get(tone))
        if v is None:
            return None
        out[tone] = v
    return out


def _blink(curves, bars, tf: str) -> Optional[dict]:
    try:
        return EB.block_from_curves(curves, bars, tf=tf)
    except Exception as exc:                                   # noqa: BLE001 — a frame never breaks on it
        log.debug("card_frames: ema_blink %s unavailable: %s", tf, exc)
        return None


def _stores(stores) -> tuple:
    if stores is not None:
        return stores
    return ST.default(), ST.for_variant(V.GG1)


def _frame_block(sym: str, tf: str, fr: dict, src, src_v, session, end, now, in_window: bool) -> dict:
    bars = list(fr.get("bars") or [])
    curves = list(fr.get("curves") or [])
    vol_avg = fr.get("vol_avg") if isinstance(fr.get("vol_avg"), dict) else None
    return {"tf": tf, "label": frame_words(tf),
            "tile": {"symbol": sym, "href": "", "bars": bars, "curves": curves, "markers": [], "lines": [],
                     "bands": [], "stats": [], "why": "", "vol_avg": vol_avg},
            "axis": BLD.axis(session, frame_minutes(tf), bars, end) if bars else None,
            "ema_cross": None, "uptrend": None, "held": None,
            "ema_blink": _blink(curves, bars, tf) if bars else None,
            "ema_tail": ema_tail(curves) if bars else None,
            "as_of_et": PL._clock(src.get("at"), now) if src else None,
            "stale": frame_stale(src.get("at"), now, in_window, src_v) if src else False,
            "empty_text": None if bars else EMPTY_TEXT.format(minutes=frame_minutes(tf), sym=sym)}


def _build(symbol, now, stores) -> dict:
    sym = ST.broker_symbol(symbol)
    if sym is None:
        return {"state": "bad_symbol", "reason": BAD_SYMBOL_TEXT}
    now = GT._et(now)
    session, is_today, in_window = GT.session_for(now)
    s5, s1 = _stores(stores)
    g5 = s5.get_read(session, sym)
    g1 = s1.get_read(session, sym)
    g5 = g5 if isinstance(g5, dict) else None
    g1 = g1 if isinstance(g1, dict) else None

    picked = []
    for tf, _rule in FRAMES:
        src_v = SOURCE[tf]
        src = g5 if src_v is V.GG5 else g1
        if tf == "5m" and g5 is None and g1 is not None:
            src, src_v = g1, FALLBACK_5M
        fr = GT._tile_frame(src, tf, src_v) if src else {"bars": [], "curves": [], "vol_avg": None}
        picked.append((tf, fr, src, src_v))

    every_bar = [b for _tf, fr, _s, _v in picked for b in (fr.get("bars") or [])]
    end = BLD.axis_end(session, every_bar)                     # [C2] the ONE end over ALL three frames' bars
    frames = [_frame_block(sym, tf, fr, src, src_v, session, end, now, in_window) for tf, fr, src, src_v in picked]
    by = {f["tf"]: f for f in frames}
    head = by["15m"] if g5 is not None else by["1m"]           # the CARD's own doc (GG5 lists the name); GG1-only → GG1
    has_bars = any(f["tile"]["bars"] for f in frames)
    return {"state": "ok", "symbol": sym, "session": session.isoformat(), "is_today": bool(is_today),
            "in_window": bool(in_window), "as_of_et": head["as_of_et"], "stale": bool(head["stale"]),
            "text": None if has_bars else NO_FRAMES_TEXT.format(sym=sym), "frames": frames}


def build(symbol: str, now=None, *, stores=None) -> dict:
    """The view's answer for one symbol. Never raises: any fault → {"state": "error", "reason": <exception name>}.
    `stores` = (GG5 store, GG1 store) for tests; None → the real ones (two find_one reads, nothing else)."""
    try:
        return _build(symbol, now, stores)
    except Exception as exc:                                   # noqa: BLE001 — the view serves the fault, never a 500
        log.warning("card_frames: build failed: %s", type(exc).__name__)
        return {"state": "error", "reason": type(exc).__name__}
