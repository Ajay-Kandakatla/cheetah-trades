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
from datetime import datetime
from typing import Optional

log = logging.getLogger("chart_maps.live_card")

CLOSE_FOLLOWS_PRINT_RTH = True   # MINE — DECISIONS8 D1/K2 default (the ticker page's number); HIS CALL Q2
FAULT_TEXT = "live quotes unavailable — the cards keep the board's last read"
BAD_BODY_TEXT = "symbols must be a list of tickers"
# MINE — AMENDMENTS8 C2: the word served for ONE symbol whose composition failed (the others still serve).
SYMBOL_FAULT_TEXT = "live quote unavailable for this symbol — the card keeps the board's last read"


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


def compose(symbols, *, now: Optional[datetime] = None) -> dict:
    """The §3.3 answer for `symbols` (raises TooManySymbols above the cap — a direct call never cuts silently)."""
    from sepa import prices
    from rotation.api import _scrub
    from . import board
    syms = normalize(symbols)
    c = cap()
    if len(syms) > c:
        raise TooManySymbols(len(syms), c)
    now_et = (now or datetime.now(board.ET)).astimezone(board.ET)
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
