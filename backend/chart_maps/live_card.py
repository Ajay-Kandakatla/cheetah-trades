"""🔴 Live card overlay (Ajay 2026-10-16: "Can you make this chart more live please like when its 24 hour or todays
entry" / "actual price is this  above but it stale value"). READ ONLY: one snapshot call, one cached-frames find, the
board's own bar and now-line helpers BY CALL; writes nothing to any cache. Display only — scans read closed bars.

`POST /chart-maps/live` (chart_maps/api.py) hands this module the symbols of the tiles on screen; `compose` answers the
card's last bar (built by `prices.with_today_bar` → `board._norm_frame` → `board._frame_to_bars` →
`board._tag_live_bar`, the board's own candle chain) and the now block (built by `board.attach_live_now` on a probe
tile, the board's own now-line rule). BUILD_SPEC8 §3.1 / §3.3, AMENDMENTS8 C2 (one symbol never fails the read) and C4
(`prev_bar`, the session before the served bar as a closed bar).

Imports live inside the functions (house style): the tests stub `sepa.prices`.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger("chart_maps.live_card")

CLOSE_FOLLOWS_PRINT_RTH = True   # MINE — DECISIONS8 D1/K2 default (the ticker page's number); HIS CALL Q2
FAULT_TEXT = "live quotes unavailable — the cards keep the board's last read"
BAD_BODY_TEXT = "symbols must be a list of tickers"
# MINE — AMENDMENTS8 C2: the word served for ONE symbol whose composition failed (the others still serve).
SYMBOL_FAULT_TEXT = "live quote unavailable for this symbol — the card keeps the board's last read"

# 🔴 Live vs the card's levels (Ajay 2026-10-21: "Are we not real time SAIQ already broke the EMA" / "If something is
# Potential add min on min for pricing and other updates to make them more realtime and give us a better edge";
# BUILD_SPEC20 D2). DISPLAY ONLY: the words say where the live print sits against the trigger / stop the tab already
# served; the pass, store, potentials, pushes, ledger and lane never read them (tests/test_gajjala_live_vs_2026_10_21.py
# import guard). The read itself still moves at the closed bar. UNMEASURED — freshness, not an edge. Not advice.
VS_KINDS = ("over_trigger", "under_stop", "between", "none")   # "none" = no `vs` key on the quote
VS_TEXT = {   # MINE — BUILD_SPEC20 D2 (2026-10-21), the contracts block pins these strings
    "over_trigger": ("🔴 {px} over the trigger {trigger} on the live bar — the read moves when the {tf}-minute bar "
                     "closes ({next_close} ET)"),
    "under_stop": ("🔴 {px} under the stop {stop} on the live bar — the read moves when the {tf}-minute bar closes "
                   "({next_close} ET)"),
    "between": "🔴 {px} · between the stop {stop} and the trigger {trigger}",
}
# MIRROR (2026-10-21, BUILD_SPEC20 D6) of the FE's CARD_LIVE_MS 30_000 (frontend/src/lib/cardLive.ts, MINE — = the
# SessionPrice poll): the ℹ️ panel prints it; a repo test pins equality with the FE constant. Not read by any poll.
CARD_LIVE_SEC = 30


class TooManySymbols(ValueError):
    """More symbols than one snapshot call carries — refused whole, never cut."""

    def __init__(self, n: int, cap_: int):
        self.n = int(n)
        self.cap = int(cap_)
        super().__init__(too_many_text(self.n, self.cap))


def cap() -> int:
    """The per-read symbol cap = the snapshot chunk (`prices._SNAP_CHUNK`)."""
    from sepa import prices
    return int(prices._SNAP_CHUNK)


def too_many_text(n: int, cap_: int) -> str:
    """W4 — the 413 detail."""
    return f"up to {int(cap_)} symbols per live read — {int(n)} sent"


def normalize(symbols) -> list[str]:
    """str items only, stripped and upper-cased, empties dropped, de-duplicated in order."""
    out: list[str] = []
    seen: set[str] = set()   # O(n) dedupe — the route runs this on the event loop before the cap check
    if not isinstance(symbols, (list, tuple)):
        return out
    for s in symbols:
        if not isinstance(s, str):
            continue
        s = s.strip().upper()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def now_labels() -> list[str]:
    """W7 — every label the board's now line can carry (the FE swaps only these)."""
    from . import board
    return [board.now_label("now", s) for s in (None, "premarket", "afterhours")]


def footer(now_et: datetime, session: Optional[str]) -> dict:
    """W1 / W2 — the freshness words, off the server's ET clock."""
    return {"live": None if session == "closed" else f"live · {now_et:%H:%M:%S} ET",
            "stale": f"last refresh {now_et:%H:%M} ET"}


def card_bar(frame, sym: str, snap: dict) -> tuple:
    """(bar, prev_t, prev_bar) — the card's last bar off the CLOSED frame + the snapshot row, built by the board's own
    chain; prev_t / prev_bar = the session before it in that frame (prev_bar a closed bar, no `s` tag — C4)."""
    from sepa import prices
    from . import board
    if frame is None or not snap:
        return None, None, None
    out, info = prices.with_today_bar(frame, sym, snap=snap)
    df = board._norm_frame(out)
    if df is None or len(df) == 0:
        return None, None, None
    info = info or {}
    tail = df.tail(1).copy()
    if CLOSE_FOLLOWS_PRINT_RTH and info.get("session") == "rth" and (info.get("appended") or info.get("adjusted")):
        lt = prices.extended_print(snap)
        # a print of another day or session never touches the bar (stale-print guard)
        if lt and lt.get("session") == "rth" and lt.get("date") == info.get("date"):
            prices._extend_last_row(tail, lt["price"])
    bars = board._tag_live_bar(board._frame_to_bars(tail), info)
    bar = bars[-1] if bars else None
    if bar is None:
        return None, None, None
    prev_t = board._row_date(df.index[-2]) if len(df) >= 2 else None
    prev_bar = None
    if len(df) >= 2:
        prev = board._frame_to_bars(df.iloc[-2:-1])
        prev_bar = prev[0] if prev else None
    return bar, prev_t, prev_bar


def card_now(probe: dict, snap: dict) -> Optional[dict]:
    """The now block off a probe tile `board.attach_live_now` already moved; None when it found no print."""
    from sepa import prices
    from . import board
    if not isinstance(probe, dict) or "live_price" not in probe:
        return None
    lines = probe.get("lines") or []
    label = lines[0].get("label") if lines and isinstance(lines[0], dict) else None
    ep = prices.extended_print(snap) or {}
    epoch = ep.get("epoch")
    as_of = None
    if epoch:
        try:
            as_of = f"{datetime.fromtimestamp(float(epoch), tz=board.ET):%H:%M:%S} ET"
        except (OverflowError, OSError, ValueError, TypeError):
            as_of = None
    sess = probe.get("live_session")
    return {"price": probe["live_price"], "label": label, "session": sess,
            "add_line": bool(sess), "as_of_epoch": epoch or None, "as_of": as_of}


def vs_tf_minutes() -> tuple:
    """The bar sizes the 🚩 tab reads, in minutes, off `chart_maps.gajjala.tab.TFS` ("5m", "15m") — the first is the
    default (BUILD_SPEC20 D2: tf 5 default, 15 accepted, any other → 5). Never retyped here."""
    from chart_maps.gajjala import tab as GT
    return tuple(int(str(s).rstrip("m")) for s in GT.TFS)


def _vs_sizes() -> tuple:
    """The bar sizes `_vs_tf` accepts: GG5's TFS FIRST (vs_tf_minutes — the first is still the default), then every
    other variant frame's minutes (chart_maps.gajjala.variant — 2026-10-27, the 🚩 1-minute page's "1m" → 1). Never
    retyped here."""
    sizes = list(vs_tf_minutes())
    from chart_maps.gajjala import variant as V
    for v in V.VARIANTS:
        for tf in v.tfs:
            m = V.frame_minutes(tf, v)
            if m not in sizes:
                sizes.append(m)
    return tuple(sizes)


def _vs_tf(tf) -> int:
    """A served tf ("5m" / "15m" / 5 / 15 / "15") → its minutes; anything else → the default (the first TFS).
    2026-10-27: every variant frame is accepted too ("1m" / 1 → 1, the 🚩 1-minute page); the default stays 5."""
    sizes = _vs_sizes()
    if isinstance(tf, bool):
        return sizes[0]
    if isinstance(tf, int):
        return tf if tf in sizes else sizes[0]
    if isinstance(tf, str):
        t = tf.strip().lower()
        for m in sizes:
            if t in (str(m), f"{m}m"):
                return m
    return sizes[0]


def _vs_level(v):
    """(ok, value): a missing / None level is absent (ok, None); a finite positive number is the level; anything else
    (a string, a bool, NaN, inf, ≤ 0) is unparsable → (False, None), and the symbol gets no `vs`."""
    if v is None:
        return True, None
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False, None
    f = float(v)
    if not math.isfinite(f) or f <= 0:
        return False, None
    return True, f


def next_close(now_et: datetime, tf_min: int) -> str:
    """HH:MM of the next `tf_min`-minute boundary of the ET clock after `now_et` (the close of the live bar; a clock
    exactly on a boundary is the open of a new bar, so its close is one bar later)."""
    mins = now_et.hour * 60 + now_et.minute
    nxt = (mins // tf_min + 1) * tf_min
    day0 = now_et.replace(hour=0, minute=0, second=0, microsecond=0)
    return f"{day0 + timedelta(minutes=nxt):%H:%M}"


def live_vs(price, level, now_et: datetime) -> Optional[dict]:
    """{kind, text} for one served now price against one tile's {trigger, stop, tf}; None = kind "none" (no price, no
    level dict, an unparsable level, or a price with only one side's level that sits on the other side). Compared on
    the broker grid (trading.broker.round_price — the same grid `tab._px` prints), so the kind and the printed words
    never disagree: px ≥ trigger → over_trigger, else px ≤ stop → under_stop, else between (both levels needed)."""
    from chart_maps.gajjala import tab as GT
    from trading.broker import round_price
    if not isinstance(level, dict):
        return None
    ok_p, px = _vs_level(price)
    ok_t, trig = _vs_level(level.get("trigger"))
    ok_s, stop = _vs_level(level.get("stop"))
    if not (ok_p and ok_t and ok_s) or px is None or (trig is None and stop is None):
        return None
    tf = _vs_tf(level.get("tf"))
    g_px = round_price(px)
    words = {"px": GT._px(px), "trigger": GT._px(trig) if trig is not None else None,
             "stop": GT._px(stop) if stop is not None else None, "tf": tf}
    if trig is not None and g_px >= round_price(trig):
        kind = "over_trigger"
    elif stop is not None and g_px <= round_price(stop):
        kind = "under_stop"
    elif trig is not None and stop is not None:
        kind = "between"
    else:
        return None
    if kind != "between":
        words["next_close"] = next_close(now_et, tf)
    return {"kind": kind, "text": VS_TEXT[kind].format(**words)}


def _norm_levels(levels, syms: list) -> dict:
    """The `levels` body, keyed like `normalize` (stripped, upper-cased), only for symbols asked; anything else is
    dropped (never a 422 — BUILD_SPEC20 D2)."""
    if not isinstance(levels, dict):
        return {}
    asked = set(syms)
    out: dict = {}
    for k, v in levels.items():
        if not isinstance(k, str) or not isinstance(v, dict):
            continue
        s = k.strip().upper()
        if s in asked and s not in out:
            out[s] = v
    return out


def compose(symbols, *, levels=None, now: Optional[datetime] = None) -> dict:
    """The §3.3 answer for `symbols` (raises TooManySymbols above the cap — a direct call never cuts silently).
    `levels` {SYM: {trigger, stop, tf}} (optional, display only) adds `vs` {kind, text} to that symbol's quote."""
    from sepa import prices
    from rotation.api import _scrub
    from . import board
    syms = normalize(symbols)
    c = cap()
    if len(syms) > c:
        raise TooManySymbols(len(syms), c)
    now_et = (now or datetime.now(board.ET)).astimezone(board.ET)
    lv = _norm_levels(levels, syms)
    meta: dict = {}
    # stamps meta["tape_session"] with the board's own clock; no tiles → no snapshot read
    board.attach_live_now([], meta, live={}, now=now_et)
    quotes: dict = {}
    missing: list[str] = []
    faults: dict = {}
    fault = None
    if syms:
        try:
            raw = prices.bulk_snapshot(syms) or {}
        except Exception as exc:                                # noqa: BLE001
            log.debug("live card: snapshot for %d symbols failed: %s", len(syms), exc)
            raw = {}
        if not raw:
            fault = FAULT_TEXT
            missing = list(syms)
        else:
            answered = [s for s in syms if raw.get(s)]
            frames: dict = {}
            if answered:
                try:
                    frames = prices.bulk_cached_frames(answered) or {}
                except Exception as exc:                        # noqa: BLE001
                    log.debug("live card: cached frames for %d symbols failed: %s", len(answered), exc)
                    frames = {}
            probes = {s: {"symbol": s, "lines": [{"price": 0.0, "label": "now", "tone": "now"}]}
                      for s in answered}
            live = board._live_from_snaps(list(probes.values()), raw)
            for s in syms:
                if s not in probes:
                    missing.append(s)
                    continue
                try:
                    board.attach_live_now([probes[s]], meta, live=live, now=now_et)
                    bar, prev_t, prev_bar = card_bar(frames.get(s), s, raw[s])
                    nb = card_now(probes[s], raw[s])
                except Exception as exc:                        # noqa: BLE001
                    log.debug("live card: %s failed: %s", s, exc)
                    missing.append(s)
                    faults[s] = SYMBOL_FAULT_TEXT
                    continue
                if bar is None and nb is None:
                    missing.append(s)
                    continue
                quotes[s] = {"bar": bar, "prev_t": prev_t, "prev_bar": prev_bar, "now": nb}
                if s in lv and nb is not None:
                    try:
                        vs = live_vs(nb.get("price"), lv[s], now_et)
                    except Exception as exc:                    # noqa: BLE001 — display words never fail a quote
                        log.debug("live card: %s vs words failed: %s", s, exc)
                        vs = None
                    if vs is not None:
                        quotes[s]["vs"] = vs
        # every asked symbol faulted → a read that served nothing claims no "live · HH:MM" (critic LOW, WP-A)
        if not quotes and faults and fault is None:
            fault = FAULT_TEXT
    session = meta.get("tape_session")
    return _scrub({
        "session": session,
        "as_of_epoch": now_et.timestamp(),
        "as_of": f"{now_et:%Y-%m-%d %H:%M:%S} ET",
        "footer": {"live": None, "stale": None} if fault else footer(now_et, session),
        "now_labels": now_labels(),
        "cap": c,
        "asked": len(syms),
        "served": len(quotes),
        "missing": missing,
        "fault": fault,
        "faults": faults,
        "quotes": quotes,
    })
