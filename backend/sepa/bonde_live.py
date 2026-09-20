"""📈 Bonde — the LIVE day leg, bolted onto the board without touching it.

Ajay 2026-09-20: *"can you improve Bondes page a lil bit more and add trackers
and also make his page more live"*.

═══════════════════════════════════════════════════════════════════════════
ONE LIVE ENGINE, NOT A SECOND ONE
═══════════════════════════════════════════════════════════════════════════
Every number on `bonde.board()` comes out of the last SCAN — the board never
scans on the request path and it must not start now. What "live" means here is
narrow and stated on the page: ONE snapshot fan-out over the names the board is
already showing, read through `rotation.hottest.live_day_moves`, which is the
app's only same-day move engine. It owns the market calendar
(`market_hours.gate.closed_reason`), the RTH clock
(`supply_demand.bounce_room.in_session`), the session window and the rule that
a non-positive day bar is a MISSING price rather than a flat one. None of that
is re-derived here, because a second copy of a clock is how two boards start
disagreeing about whether the market is open.

WHAT MUST NOT DRIFT — the board is never half live. `live_day_moves` serves a
live block only when the benchmark itself printed live; if it did not, the
whole block comes back on the close basis and EVERY row on this board carries
`today_pct = None`. A table where some rows show this session and the rest show
the last one is true of neither session. The basis is stated once, in `d1`, and
the column renders an em-dash rather than a number it cannot label.

The benchmark (RSP, the app's equal-weight benchmark, same constant Hottest
uses) is not printed in Bonde's Today column — this column is each name's OWN
move, not a relative one. It rides the same call because it is the engine's
liveness proof: if RSP has no live print, nothing in that snapshot is this
session's.

Nothing here gates a scan, fires an alert or buys in any lane.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from rotation.hottest import D1_CLOSE, D1_LIVE, live_day_moves

log = logging.getLogger("sepa.bonde_live")

# The app's benchmark, the same one the Hottest board measures against
# (`rotation/hottest.py`, `rotation/tracker.BENCHMARK`). Named, not retyped as
# a bare string in a call site.
BENCH = "RSP"

# Exactly the keys `d1` carries. Pinned as a constant because the FE reads
# every one of them and a test asserts the set: a key that quietly appears or
# vanishes is a column that starts rendering blank.
D1_KEYS = ("basis", "live", "market_closed", "in_session", "session_window",
           "as_of", "close_as_of", "symbols", "live_names", "reason",
           "tape_session", "note")


def _symbols(board: dict) -> list:
    """Every symbol the board is SHOWING, deduped, order-independent.

    The capped sections are what the page renders, so this is what gets priced
    — the uncapped passer list would spend provider reads on rows nobody can
    see (`bonde.SECTION_CAP` is 60/60/60/40/40 = 260 names at most).
    """
    out: list = []
    seen: set = set()
    for rows in ((board or {}).get("sections") or {}).values():
        for r in rows or []:
            sym = str((r or {}).get("symbol") or "").upper()
            if sym and sym not in seen:
                seen.add(sym)
                out.append(sym)
    return out


def _tape_session(now: Optional[datetime] = None) -> Optional[str]:
    """'premarket' | 'rth' | 'afterhours' | 'closed' from the ONE tagger
    (`supply_demand.zone_edge.session_state`). The board carries it as
    `tape_session`, never `session` — that name is taken elsewhere in this app
    and the two have been confused before."""
    try:
        from supply_demand import zone_edge as ZE
        return ZE.session_state(now)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("bonde_live: session tagger unavailable (%s)", exc)
        return None


def _close_day(scan_ts) -> Optional[str]:
    """The DATE of the scan the rest of the board comes from, as YYYY-MM-DD.

    `bonde.board()` serves `scan_ts` as whatever the scan file carried — an ISO
    string today, an epoch in older payloads, `None` when the file has neither.
    An epoch is converted in US/Eastern (the app's session timezone) rather
    than printed as ten digits, which is what a bare slice would have done.
    """
    if scan_ts is None or scan_ts == "":
        return None
    if isinstance(scan_ts, (int, float)) and not isinstance(scan_ts, bool):
        try:
            from supply_demand.zone_edge import ET
            return datetime.fromtimestamp(float(scan_ts), ET).date().isoformat()
        except Exception:                                      # noqa: BLE001
            return None
    return str(scan_ts)[:10]


def _note(live_ok: bool, close_day: Optional[str], reason: Optional[str]) -> str:
    """What the Today column is showing, in THIS board's words.

    Bonde's own sentence, not Hottest's: the columns beside it are sales tiers,
    a character clause and an Episodic Pivot, none of which exist on that board.
    """
    day = close_day or "last"
    if live_ok:
        return (
            "Today is each name's own move so far in this session, read live "
            "off one snapshot. Everything else on this board — the sales tier, "
            "the year-over-year growth, the character chips, the Episodic "
            f"Pivot and the CPA metrics — comes from the {day} scan."
        )
    return (
        f"Every column on this board, Today included, comes from the {day} "
        "scan. That is the last finished session, not the current one"
        + (f" — {reason}." if reason else ".")
    )


def attach(board: dict, *, fetch=None, now: Optional[datetime] = None) -> dict:
    """Add the live Today leg to an already-built `bonde.board()` payload.

    Mutates and returns `board`. NEVER raises: a board that renders on the
    scan's numbers with honest labels beats a board that 500s because a price
    provider blinked. Every failure path lands on the close basis with the
    reason in plain English, which is exactly what the engine already does.
    """
    if not isinstance(board, dict):
        return board
    syms = _symbols(board)
    try:
        live = live_day_moves(syms, BENCH, fetch=fetch) or {}
    except Exception as exc:                                   # noqa: BLE001
        # live_day_moves is documented never to raise; this is the belt for
        # the braces, because this board must not 500 over a price read.
        log.warning("bonde_live: live day read failed: %s", exc)
        live = {"reason": f"the live price read failed ({type(exc).__name__})"}

    moves = live.get("moves") or {}
    # EFFECTIVE liveness, not the block's optimism: a block that came back
    # `live` with nothing in `moves` served no live row and must say close.
    live_ok = bool(live.get("live")) and bool(moves)
    basis = D1_LIVE if live_ok else D1_CLOSE

    for rows in (board.get("sections") or {}).values():
        for r in rows or []:
            if not isinstance(r, dict):
                continue
            sym = str(r.get("symbol") or "").upper()
            # Never mixed: on the close basis EVERY row is None, including the
            # ones that did have a print in the snapshot.
            r["today_pct"] = moves.get(sym) if live_ok else None
            r["today_basis"] = basis

    close_day = _close_day(board.get("scan_ts"))
    reason = live.get("reason") or (None if live else "no live price read was made")
    board["d1"] = {
        "basis": basis,
        "live": live_ok,
        # The calendar's OWN words, so the FE never string-matches prose to
        # decide whether the tape is shut.
        "market_closed": live.get("market_closed"),
        "in_session": live.get("in_session"),
        "session_window": live.get("session_window"),
        "as_of": live.get("as_of") if live_ok else None,
        "close_as_of": close_day,
        "symbols": live.get("symbols") or len(syms),
        "live_names": (live.get("live_names") or 0) if live_ok else 0,
        "reason": None if live_ok else reason,
        "tape_session": _tape_session(now),
        "note": _note(live_ok, close_day, reason),
    }
    return board
