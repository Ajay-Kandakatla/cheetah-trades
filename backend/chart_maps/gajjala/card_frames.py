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

📈 2026-11-18 (Ajay: "Also I need to keep 1 min charts when I am viewing specific stock") — his Watch is full, so most
card names had no 1m chart. When NEITHER a GG1 doc NOR a same-session Watch 1m tile has bars, the 1m frame is built ON
DEMAND for that ONE symbol by the Watch's own builder: `gajjala_watch.build.frames([sym], …)` (bars.frames_for — the
prior day from the 1-minute day cache, today re-fetched: ONE minute fetch for today, this name only) and
`build.tile_update(…)` for the tile bytes the Watch would store — its update is READ, never written (no tile doc, no
Watch seat). Only the real path (`stores=None`) or a test's 4th `stores` element fetches; a 2- / 3-tuple never does.
A fetch fault / no bar → the served empty words above (fail open; 15m / 5m untouched). Every frame now serves
`source` = {"kind": gajjala | gajjala_1m | watch | on_demand, "at": ISO ET or None} (None with no bars); the stamp of
an on-demand frame is its build time, never stale. No board load calls this — only the ⤢ view's GET.

📈📐 2026-11-23 (spec vwapzones §3.7, Ajay: "Add vwap and supply demand too") — the Watch's VWAP + daily zones on the
three frames. The ONE Watch `find_one` of a GET (`_watch_1m`) also projects every other Watch frame's bar stamps + its
stored `vwap` and the tile's `levels` (built from the Watch's FRAMES, never typed); the frame it returns carries ONE
private key `_ov` that is never served. VWAP: `vwap.align` by bar stamp → a `vwap` curve on every served frame with
bars (a stamp the Watch tile lacks → None there; no Watch tile and no on-demand build → no curve). Zones:
`levels.for_card` — a stored Watch `levels` of this session, else (real path only) a single-flight queued daily read that
the GET never waits on → `ctx` bands on every frame with bars + the payload's `levels` line. A stores tuple of 2–4
elements never reads daily bars; a 5th element (a callable (sym, now) → frame) is the daily loader, run inline. Any fault
→ no curve, no bands, `levels` None — the view still answers. Display only. UNMEASURED.
"""
from __future__ import annotations

import importlib
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
from chart_maps.gajjala_watch import constants as WC
from chart_maps.gajjala_watch import levels as LV
from chart_maps.gajjala_watch import payload as PL

log = logging.getLogger("chart_maps.gajjala.card_frames")

API_BASE = "/chart-maps/gajjala/frames"            # == FE lib/gajjalaCardView.GGC_PATH (a source-read test pins it)
API_PATH = API_BASE + "/{symbol}"
FRAMES = (("15m", "15min"), ("5m", "5min"), ("1m", "1min"))   # big → small (= FE GGC_STRETCH_ORDER; HIS CALL #1)
SOURCE = {"15m": V.GG5, "5m": V.GG5, "1m": V.GG1}             # which variant's stored read doc holds each frame
FALLBACK_5M = V.GG1                                            # no GG5 doc → GG1's own 5m frame (the same pipeline)

EMPTY_TEXT = "No {minutes}-minute bars stored for {sym} this session yet — a pass has to read it first"
NO_FRAMES_TEXT = "No bars stored for {sym} this session yet"
SOURCE_WATCH, SOURCE_ON_DEMAND = "watch", "on_demand"         # a frame's `source.kind` beyond the variant keys
BAD_SYMBOL_TEXT = "Not a ticker"
VWAP_MODULE = "chart_maps.gajjala_watch.vwap"                  # 📈 2026-11-23 — imported LAZILY (a fault → no curve)
OV_KEY = "_ov"                                                 # the private overlay key of a Watch / on-demand frame


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


def _tile_1m(frames) -> Optional[dict]:
    """The 1m frame of a Watch tile's `frames` map ({tf: tile}) → {tf, bars, curves, vol_avg}; None without 1m bars."""
    frames = frames if isinstance(frames, dict) else {}
    t = frames.get("1m") if isinstance(frames.get("1m"), dict) else {}
    bars = t.get("bars")
    if not isinstance(bars, list) or not bars:
        return None
    va = t.get("vol_avg")
    return {"tf": "1m", "bars": list(bars), "curves": list(t.get("curves") or []),
            "vol_avg": va if isinstance(va, dict) else None}


def _vw():
    """📈 2026-11-23: the Watch's VWAP wrapper module, imported lazily; absent / a fault → None (no curve)."""
    try:
        return importlib.import_module(VWAP_MODULE)
    except Exception as exc:                                   # noqa: BLE001 — the view never breaks on it
        log.debug("card_frames: vwap module unavailable: %s", type(exc).__name__)
        return None


def _overlays_on() -> bool:
    """📈📐 2026-11-23: `WC.VWAP_ON or WC.ZONES_ON`, read at call time; any fault → False."""
    try:
        return bool(WC.VWAP_ON or WC.ZONES_ON)
    except Exception:                                          # noqa: BLE001
        return False


def _watch_projection() -> dict:
    """The ONE Watch find_one's projection: the 1m frame whole + every other Watch frame's bar stamps and stored
    `vwap` (from the Watch's own FRAMES — never typed) + the tile's `levels`."""
    proj = {"session": 1, "at": 1, "loaded_at": 1, "frames.1m": 1, "levels": 1}
    for tf, _rule in WC.FRAMES:
        if tf != "1m":
            proj[f"frames.{tf}.bars.t"] = 1
            proj[f"frames.{tf}.vwap"] = 1
    return proj


def _ov_of(frames, levels, session) -> dict:
    """The private overlay key: {"vwap": {tf: {bar t: value}} by stamp, "levels": the tile's stored levels or None,
    "session": the tile's session}. A missing VWAP module / frame → that part empty."""
    frames = frames if isinstance(frames, dict) else {}
    VW = _vw()
    vw: dict = {}
    if VW is not None:
        for tf, f in frames.items():
            if isinstance(f, dict):
                try:
                    by = VW.by_stamp(f)
                except Exception:                              # noqa: BLE001
                    by = {}
                if by:
                    vw[tf] = by
    return {"vwap": vw, "levels": levels if isinstance(levels, dict) else None, "session": session}


def _watch_1m(tiles_coll, sym: str, session) -> tuple:
    """(frame, source) of the 👀 Watch's stored 1m tile for `sym` — ONE find_one; only a doc of the SAME session with
    non-empty 1m bars counts. source = {"at": the tile's loaded_at, else its at}. No coll / a fault → (None, None).
    📈📐 2026-11-23: the frame carries the private `_ov` (VWAP by stamp of every Watch frame + the tile's `levels`)."""
    if tiles_coll is None:
        return None, None
    try:
        doc = tiles_coll.find_one({"_id": sym}, _watch_projection())
        if not isinstance(doc, dict) or doc.get("session") != session.isoformat():
            return None, None
        fr = _tile_1m(doc.get("frames"))
        if fr is None:
            return None, None
        try:
            fr[OV_KEY] = _ov_of(doc.get("frames"), doc.get("levels"), doc.get("session"))
        except Exception as exc:                               # noqa: BLE001 — overlays only; the frame stays
            log.debug("card_frames: watch overlays of %s unavailable: %s", sym, type(exc).__name__)
        at = doc.get("loaded_at") if doc.get("loaded_at") is not None else doc.get("at")
        return fr, {"at": at}
    except Exception as exc:                                   # noqa: BLE001 — the view never breaks on it
        log.debug("card_frames: watch 1m tile of %s unavailable: %s", sym, type(exc).__name__)
        return None, None


def _on_demand_1m(sym: str, session, now, *, load_day=None) -> tuple:
    """📈 2026-11-18: (frame, source) of the 1m frame built NOW for `sym` by the 👀 Watch's own builder —
    `BLD.frames([sym], …)` (ONE name; today's minutes re-fetched, the prior day from the 1-minute day cache) then
    `BLD.tile_update(…)`, whose update is only READ for its `frames.1m` tile (nothing is written). source = {"at": the
    update's loaded_at}. `load_day` = the minute loader (None → the Watch's own default). Any fault / no bar today /
    no 1m bars → (None, None): the caller serves its empty words."""
    try:
        F = BLD.frames([sym], session, now, load_day=load_day, stats={}, per_name={})
        fr = F.get(sym) if isinstance(F, dict) else None
        if fr is None:
            return None, None
        _flt, upd = BLD.tile_update(sym, fr, session, now, "loaded")
        sets = upd.get("$set") if isinstance(upd, dict) and isinstance(upd.get("$set"), dict) else {}
        out = _tile_1m(sets.get("frames"))
        if out is None:
            return None, None
        try:
            out[OV_KEY] = _ov_of(sets.get("frames"), None, sets.get("session"))
        except Exception as exc:                               # noqa: BLE001 — overlays only; the frame stays
            log.debug("card_frames: on-demand overlays of %s unavailable: %s", sym, type(exc).__name__)
        return out, {"at": sets.get("loaded_at")}
    except Exception as exc:                                   # noqa: BLE001 — the view never breaks on it
        log.debug("card_frames: on-demand 1m of %s unavailable: %s", sym, type(exc).__name__)
        return None, None


def _fetcher(stores):
    """The on-demand 1m builder of this call: the real path (`stores=None`) → `_on_demand_1m` with the Watch's own
    loader; a test's 4th `stores` element (a callable (sym, session, now) → (frame, source)) → that; a 2- / 3-tuple →
    None (never fetches)."""
    if stores is None:
        return _on_demand_1m
    st = tuple(stores)
    return st[3] if len(st) >= 4 and callable(st[3]) else None


def _daily(stores) -> tuple:
    """(daily loader, inline runner) of this call: the real path (`stores=None`) → (`levels.default_loader`, None = the
    single-flight queue); a test's 5th `stores` element (a callable (sym, now) → frame) → it, run inline; a 2–4 element
    tuple → (None, None): never reads daily bars."""
    if stores is None:
        return LV.default_loader, None
    st = tuple(stores)
    if len(st) >= 5 and callable(st[4]):
        fn = st[4]
        return (lambda s, *, now: fn(s, now)), (lambda job: job())
    return None, None


def _last_close(bars) -> Optional[float]:
    for b in reversed(bars or []):
        v = b.get("c") if isinstance(b, dict) else None
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
            return float(v)
    return None


def _add_overlays(sym: str, session, now, frames: list, ov, stores) -> Optional[dict]:
    """📈📐 2026-11-23: the VWAP curve + the zone bands on every served frame with bars; → the payload's `levels`
    ({state, text, title, as_of}) or None. Fenced by the caller."""
    ov = ov if isinstance(ov, dict) else {}
    with_bars = [f for f in frames if f["tile"]["bars"]]
    VW = _vw() if WC.VWAP_ON else None
    if VW is not None and VW.sessions() is not None:
        by_tf = ov.get("vwap") if isinstance(ov.get("vwap"), dict) else {}
        for f in with_bars:
            vals = VW.align(by_tf.get(f["tf"]) or {}, f["tile"]["bars"])
            if vals is not None:
                f["tile"]["curves"] = list(f["tile"]["curves"]) + [
                    {"tone": WC.VWAP_TONE, "label": WC.VWAP_LABEL, "values": vals}]
    if not WC.ZONES_ON:
        return None
    by = {f["tf"]: f for f in frames}
    price = None
    for tf in ["1m"] + [t for t, _r in FRAMES if t != "1m"]:
        price = _last_close(by[tf]["tile"]["bars"]) if tf in by else None
        if price is not None:
            break
    loader, run = _daily(stores)
    blk = LV.for_card(sym, session, now, price=price, levels=ov.get("levels"), tile_session=ov.get("session"),
                      loader=loader, run=run)
    if not isinstance(blk, dict):
        return None
    for f in with_bars:
        f["tile"]["bands"] = list(f["tile"]["bands"]) + [dict(b) for b in blk.get("bands") or []]
    return LV.row_levels(blk)


def _source(kind, src) -> Optional[dict]:
    """A frame's served `source` = {"kind", "at": the stamp as ISO ET (None when unreadable)}; None without a source."""
    if not src or not kind:
        return None
    at_et = PL._to_et(src.get("at"))
    return {"kind": kind, "at": at_et.isoformat() if at_et is not None else None}


def _empty_text(tf: str, sym: str) -> str:
    """The served words of a frame with no bars. The 1m frame while the 1-minute page is retired → the variant's
    retired words (`card_1m_empty`); every other case → EMPTY_TEXT."""
    if tf == "1m" and not V.enabled(V.GG1):
        w = V.word("card_1m_empty", V.GG1, sym=sym)
        if isinstance(w, str) and w:
            return w
    return EMPTY_TEXT.format(minutes=frame_minutes(tf), sym=sym)


def _frame_block(sym: str, tf: str, fr: dict, src, src_v, kind, session, end, now, in_window: bool) -> dict:
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
            "source": _source(kind, src) if bars else None,
            "empty_text": None if bars else _empty_text(tf, sym)}


def _build(symbol, now, stores) -> dict:
    sym = ST.broker_symbol(symbol)
    if sym is None:
        return {"state": "bad_symbol", "reason": BAD_SYMBOL_TEXT}
    now = GT._et(now)
    session, is_today, in_window = GT.session_for(now)
    s5, s1, wt = _stores(stores)
    fetch = _fetcher(stores)
    g5 = s5.get_read(session, sym)
    g1 = s1.get_read(session, sym)
    g5 = g5 if isinstance(g5, dict) else None
    g1 = g1 if isinstance(g1, dict) else None

    picked, ov, asked = [], None, False
    for tf, _rule in FRAMES:
        src_v = SOURCE[tf]
        src = g5 if src_v is V.GG5 else g1
        if tf == "5m" and g5 is None and g1 is not None:
            src, src_v = g1, FALLBACK_5M
        fr = GT._tile_frame(src, tf, src_v) if src else {"bars": [], "curves": [], "vol_avg": None}
        kind = src_v.key
        if tf == "1m" and not fr.get("bars"):                  # 2026-11-18: no GG1 bars → the Watch's 1m tile
            wfr, wsrc = _watch_1m(wt, sym, session)
            asked = True
            if wfr is not None:
                fr, src, src_v, kind = wfr, wsrc, V.GG1, SOURCE_WATCH
                ov = wfr.get(OV_KEY)
            elif fetch is not None:                            # 📈 neither → built on demand (ONE name, ONE fetch)
                ofr, osrc = fetch(sym, session, now)
                if ofr is not None:
                    fr, src, src_v, kind = ofr, osrc, V.GG1, SOURCE_ON_DEMAND
                    ov = ofr.get(OV_KEY)
        picked.append((tf, fr, src, src_v, kind))
    if not asked and _overlays_on():                           # 📈📐 a GG1 doc won the 1m frame → the Watch tile for `_ov` only
        wfr, _wsrc = _watch_1m(wt, sym, session)
        ov = wfr.get(OV_KEY) if wfr is not None else None

    every_bar = [b for _tf, fr, _s, _v, _k in picked for b in (fr.get("bars") or [])]
    end = BLD.axis_end(session, every_bar)                     # [C2] the ONE end over ALL three frames' bars
    frames = [_frame_block(sym, tf, fr, src, src_v, kind, session, end, now, in_window)
              for tf, fr, src, src_v, kind in picked]
    levels = None
    if _overlays_on():
        try:
            levels = _add_overlays(sym, session, now, frames, ov, stores)
        except Exception as exc:                               # noqa: BLE001 — the view still answers
            log.debug("card_frames: overlays of %s unavailable: %s", sym, type(exc).__name__)
            levels = None
    by = {f["tf"]: f for f in frames}
    head = by["15m"] if g5 is not None else by["1m"]           # the CARD's own doc (GG5 lists the name); GG1-only → GG1
    has_bars = any(f["tile"]["bars"] for f in frames)
    return {"state": "ok", "symbol": sym, "session": session.isoformat(), "is_today": bool(is_today),
            "in_window": bool(in_window), "as_of_et": head["as_of_et"], "stale": bool(head["stale"]),
            "text": None if has_bars else NO_FRAMES_TEXT.format(sym=sym), "frames": frames, "levels": levels}


def build(symbol: str, now=None, *, stores=None) -> dict:
    """The view's answer for one symbol. Never raises: any fault → {"state": "error", "reason": <exception name>}.
    `stores` = (GG5 store, GG1 store[, Watch tiles coll[, on-demand 1m builder]]) for tests; None → the real ones (two
    find_one reads, plus one of the Watch's tile when the 1m frame has no GG1 bars, plus — 📈 2026-11-18 — ONE
    on-demand minute fetch for this symbol when that tile is absent too; nothing is written)."""
    try:
        return _build(symbol, now, stores)
    except Exception as exc:                                   # noqa: BLE001 — the view serves the fault, never a 500
        log.warning("card_frames: build failed: %s", type(exc).__name__)
        return {"state": "error", "reason": type(exc).__name__}
