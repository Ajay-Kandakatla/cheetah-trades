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

⏹ 2026-11-18 — the 🚩 1-minute page retired by his word ("This is good info stop 1 min tab it was a good experiment"),
and "But keep the one min chart in the watch list I still want them". Its pass no longer writes a GG1 read doc, so the
1m frame now falls back to the 👀 Watch's stored 1m tile (`gajjala_watch_tiles`, the SAME session only — a prior day's
"last good frames" never draws as today) when the page's own doc is absent: ONE `find_one`, no fetch, no write. The
stamp is the tile's `loaded_at` (the frames' own load time — a failed read moves `at` but keeps the old frames), else
its `at`; stale through GG1M_STALE_AFTER_SEC by name (`variant.stale_after_sec(GG1)`, the Watch's own threshold). A
name not on the Watch serves the retired words (`variant.word("card_1m_empty", GG1, sym=…)`) while the switch is off,
EMPTY_TEXT while on. Reversible: a GG1 read doc for the session always wins (the page running again leads).
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
from chart_maps.gajjala_watch import colls as WCOLLS
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
    """(GG5 store, GG1 store, Watch tiles coll or None). A 2-tuple (tests) reads no Watch tile; None → the real ones,
    the tiles coll from `gajjala_watch.colls` (no database → None → skipped)."""
    if stores is not None:
        st = tuple(stores)
        return (st[0], st[1], st[2]) if len(st) >= 3 else (st[0], st[1], None)
    return ST.default(), ST.for_variant(V.GG1), (WCOLLS.colls() or {}).get("tiles")


def _watch_1m(tiles_coll, sym: str, session) -> tuple:
    """(frame, source) of the 👀 Watch's stored 1m tile for `sym` — ONE find_one; only a doc of the SAME session with
    non-empty 1m bars counts. source = {"at": the tile's loaded_at, else its at}. No coll / a fault → (None, None)."""
    if tiles_coll is None:
        return None, None
    try:
        doc = tiles_coll.find_one({"_id": sym}, {"session": 1, "at": 1, "loaded_at": 1, "frames.1m": 1})
        if not isinstance(doc, dict) or doc.get("session") != session.isoformat():
            return None, None
        frames = doc.get("frames") if isinstance(doc.get("frames"), dict) else {}
        t = frames.get("1m") if isinstance(frames.get("1m"), dict) else {}
        bars = t.get("bars")
        if not isinstance(bars, list) or not bars:
            return None, None
        va = t.get("vol_avg")
        at = doc.get("loaded_at") if doc.get("loaded_at") is not None else doc.get("at")
        return ({"tf": "1m", "bars": list(bars), "curves": list(t.get("curves") or []),
                 "vol_avg": va if isinstance(va, dict) else None}, {"at": at})
    except Exception as exc:                                   # noqa: BLE001 — the view never breaks on it
        log.debug("card_frames: watch 1m tile of %s unavailable: %s", sym, type(exc).__name__)
        return None, None


def _empty_text(tf: str, sym: str) -> str:
    """The served words of a frame with no bars. The 1m frame while the 1-minute page is retired → the variant's
    retired words (`card_1m_empty`); every other case → EMPTY_TEXT."""
    if tf == "1m" and not V.enabled(V.GG1):
        w = V.word("card_1m_empty", V.GG1, sym=sym)
        if isinstance(w, str) and w:
            return w
    return EMPTY_TEXT.format(minutes=frame_minutes(tf), sym=sym)


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
            "empty_text": None if bars else _empty_text(tf, sym)}


def _build(symbol, now, stores) -> dict:
    sym = ST.broker_symbol(symbol)
    if sym is None:
        return {"state": "bad_symbol", "reason": BAD_SYMBOL_TEXT}
    now = GT._et(now)
    session, is_today, in_window = GT.session_for(now)
    s5, s1, wt = _stores(stores)
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
        if tf == "1m" and not fr.get("bars"):                  # 2026-11-18: no GG1 bars → the Watch's 1m tile
            wfr, wsrc = _watch_1m(wt, sym, session)
            if wfr is not None:
                fr, src, src_v = wfr, wsrc, V.GG1
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
    `stores` = (GG5 store, GG1 store[, Watch tiles coll]) for tests; None → the real ones (two find_one reads, plus
    one of the Watch's tile when the 1m frame has no GG1 bars — nothing else)."""
    try:
        return _build(symbol, now, stores)
    except Exception as exc:                                   # noqa: BLE001 — the view serves the fault, never a 500
        log.warning("card_frames: build failed: %s", type(exc).__name__)
        return {"state": "error", "reason": type(exc).__name__}
