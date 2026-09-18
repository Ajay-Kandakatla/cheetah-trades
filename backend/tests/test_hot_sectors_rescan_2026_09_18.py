"""🔥 Hottest — the ↻ Re-scan button's backend half (Ajay 2026-09-18).

He asked twice:

  *"Can you give me scan button this for to rescan this for latest it says
   precious close but during market hours I want it to re calculate in the
   moment."*
  *"Yes add it and also can you give me rebuild or rescan button in hot sectors
   please"*

WHAT THE BUTTON ACTUALLY DOES, AND WHAT IT DOES NOT
---------------------------------------------------
It re-runs `GET /rotation/hottest`, which re-runs the live NAME leg — one
`prices.bulk_live_prices` fan-out over every priced name — and re-ranks the
table on it. **`D1_GROUP_BASIS` does not move.** A sector / industry / roster row
is a median over its FULL membership, and a median taken over live values for
some members and last-close values for the rest is true of neither set. Making
those rows live is HIS CALL.

WHAT IS PINNED HERE
-------------------
1. Three additive `d1` keys — `market_closed`, `in_session`, `session_window` —
   so the FE can say honestly why a re-scan will not help, without
   string-matching prose or retyping a clock.
2. The session window is RENDERED FROM `bounce_room.SESSION_OPEN/SESSION_CLOSE`,
   the one RTH engine. A second clock in this module would be the start of the
   two-surfaces-disagree bug.
3. The fan-out STILL fires outside 9:30-16:00 ET. That is deliberate — extended
   hours prints are a surface he asked for elsewhere — and it is pinned, so
   flipping it is a decision somebody has to make on purpose.
4. A closed calendar day still spends ZERO provider calls.
"""
from __future__ import annotations

import sys
from datetime import time as dtime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rotation import hottest as H   # noqa: E402


BENCH = {"symbol": "RSP", "ret_1d": -0.28, "ret_5d": -1.08,
         "ret_21d": -3.76, "ret_63d": 0.71}


def _payload() -> dict:
    return {
        "as_of": "2026-09-17",
        "sectors": [{"group": "Technology", "n": 40, "rel_1d": -0.59,
                     "rel_5d": 2.0, "rel_21d": -4.27, "pct_positive_1d": 30}],
        "industries": [], "themes": [], "sampled": {},
        H.T.MEMBERS_KEY: {
            "benchmark": dict(BENCH),
            "by_symbol": {
                "TENB": {"last_close": 37.88, "ret_1d": 7.98, "ret_5d": 12.4,
                         "ret_21d": -1.18, "ret_63d": 36.65,
                         "sector": "Technology",
                         "industry": "Software - Infrastructure"},
                "QLYS": {"last_close": 100.0, "ret_1d": 1.0, "ret_5d": 2.0,
                         "ret_21d": 3.0, "ret_63d": 4.0,
                         "sector": "Technology",
                         "industry": "Software - Infrastructure"},
            },
            "groups": {"sector": {"Technology": {
                "median_21d": -4.27, "symbols": ["TENB", "QLYS"]}}},
        },
    }


def _open_market(monkeypatch):
    monkeypatch.setattr(H, "_closed_reason", lambda: None)


def _build_with(live: dict) -> dict:
    return H._build(_payload(), sort="rel_5d", names_per_group=25,
                    decisions={}, earnings={}, live=live)


def _live(fetch, monkeypatch):
    _open_market(monkeypatch)
    return H.live_day_moves(["TENB", "QLYS"], "RSP", fetch=fetch)


_GOOD = {"RSP": {"price": 190.0, "change_pct": -0.50},
         "TENB": {"price": 36.68, "change_pct": -3.70},
         "QLYS": {"price": 99.0, "change_pct": -2.79}}


# ---------------------------------------------------------------------------
# the calendar key
# ---------------------------------------------------------------------------
def test_market_closed_rides_in_the_d1_block(monkeypatch):
    monkeypatch.setattr(H, "_closed_reason", lambda: "weekend")
    board = _build_with(H.live_day_moves(["TENB"], "RSP", fetch=lambda s: _GOOD))
    d1 = board[H.D1_KEY]
    assert d1["market_closed"] == "weekend"
    assert d1["basis"] == H.D1_CLOSE and d1["live"] is False


def test_market_closed_is_none_on_a_live_build(monkeypatch):
    board = _build_with(_live(lambda s: _GOOD, monkeypatch))
    d1 = board[H.D1_KEY]
    assert d1["market_closed"] is None
    assert d1["basis"] == H.D1_LIVE


def test_closed_market_spends_no_provider_call(monkeypatch):
    """A weekend re-scan must not cost a single chunk."""
    calls = []
    monkeypatch.setattr(H, "_closed_reason", lambda: "holiday 2026-11-26")
    H.live_day_moves(["TENB", "QLYS"], "RSP", fetch=lambda s: calls.append(s) or {})
    assert calls == []


def test_group_basis_is_still_close_after_a_live_build(monkeypatch):
    """THE LIMITATION, pinned. If this test ever fails, the sector ranking
    started moving on a click and every surface's wording is now wrong."""
    board = _build_with(_live(lambda s: _GOOD, monkeypatch))
    assert board[H.D1_KEY]["group_basis"] == H.D1_CLOSE
    assert H.D1_GROUP_BASIS == H.D1_CLOSE
    for sec in board["sectors"]:
        assert sec["d1_source"] == H.D1_CLOSE
        for ind in sec.get("industries") or []:
            assert ind["d1_source"] == H.D1_CLOSE


# ---------------------------------------------------------------------------
# the session keys
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("open_now", [True, False])
def test_in_session_rides_in_the_d1_block(monkeypatch, open_now):
    from supply_demand import bounce_room as BR
    monkeypatch.setattr(BR, "in_session", lambda now=None: open_now)
    board = _build_with(_live(lambda s: _GOOD, monkeypatch))
    assert board[H.D1_KEY]["in_session"] is open_now


def test_session_window_is_rendered_from_the_constants(monkeypatch):
    """Pins that no clock is retyped in this module — move the constants and
    the served string moves with them."""
    from supply_demand import bounce_room as BR
    monkeypatch.setattr(BR, "SESSION_OPEN", dtime(10, 0))
    monkeypatch.setattr(BR, "SESSION_CLOSE", dtime(15, 0))
    assert H._session_window() == "10:00-15:00 ET"
    board = _build_with(_live(lambda s: _GOOD, monkeypatch))
    assert board[H.D1_KEY]["session_window"] == "10:00-15:00 ET"


def test_the_real_window_is_the_regular_session():
    assert H._session_window() == "9:30-16:00 ET"


# ---------------------------------------------------------------------------
# NEGATIVES
# ---------------------------------------------------------------------------
def test_pre_open_is_flagged_not_silently_live(monkeypatch):
    """Weekday 03:00 ET. The calendar says nothing is wrong, but the day bar is
    0, so `_live_move` returns None for every name and the board is on the
    close — and now it also SAYS the session is shut instead of leaving him to
    infer it from a missing number."""
    from supply_demand import bounce_room as BR
    monkeypatch.setattr(BR, "in_session", lambda now=None: False)
    pre_open = {"RSP": {"price": 0, "change_pct": 0.0},
                "TENB": {"price": 0, "change_pct": 0.0}}
    board = _build_with(_live(lambda s: pre_open, monkeypatch))
    d1 = board[H.D1_KEY]
    assert d1["in_session"] is False
    assert d1["market_closed"] is None          # a clock fact, not a calendar one
    assert d1["basis"] == H.D1_CLOSE


def test_a_broken_session_clock_leaves_in_session_none(monkeypatch):
    """The button then behaves exactly as it does today — it never guesses."""
    import builtins
    real = builtins.__import__

    def _boom(name, *a, **kw):
        if name == "supply_demand" or name.startswith("supply_demand.bounce_room"):
            raise ImportError("bounce_room is unimportable in this test")
        return real(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", _boom)
    assert H._in_session() is None
    assert H._session_window() is None


def test_the_fan_out_still_fires_outside_rth(monkeypatch):
    """DELIBERATE NON-CHANGE. Short-circuiting the fan-out outside 9:30-16:00
    would silently remove the after-hours read Ajay uses elsewhere (Chart Maps,
    04:00-20:00, his call). If this test ever has to be edited, a default moved
    and that is a stop, not a cleanup."""
    from supply_demand import bounce_room as BR
    monkeypatch.setattr(BR, "in_session", lambda now=None: False)
    _open_market(monkeypatch)
    calls = []

    def _fetch(syms):
        calls.append(list(syms))
        return _GOOD

    H.live_day_moves(["TENB", "QLYS"], "RSP", fetch=_fetch)
    assert len(calls) == 1, "the live read must still fire outside the session"


def test_partial_snapshot_marks_the_missing_rows(monkeypatch):
    """THE NORMAL CASE, not an edge: 1,720 of 1,721 names were priced at 10:45
    ET on 2026-09-18. The name that missed keeps its close number and says so."""
    partial = {"RSP": {"price": 190.0, "change_pct": -0.50},
               "TENB": {"price": 36.68, "change_pct": -3.70}}
    live = _live(lambda s: partial, monkeypatch)
    assert live["symbols"] == 2 and live["live_names"] == 1
    rows = {n["symbol"]: n for n in _build_with(live)["sectors"][0]["names"]}
    assert rows["TENB"]["d1_source"] == H.D1_LIVE
    assert rows["QLYS"]["d1_source"] == H.D1_CLOSE
    assert rows["QLYS"]["rel_1d_close"] == pytest.approx(1.28)


def test_no_live_prints_at_all_falls_back_whole(monkeypatch):
    """A DATA failure, not a calendar one — so `market_closed` stays None and
    the button stays enabled. Clicking again is the right move here."""
    only_bench = {"RSP": {"price": 190.0, "change_pct": -0.50}}
    board = _build_with(_live(lambda s: only_bench, monkeypatch))
    d1 = board[H.D1_KEY]
    assert d1["basis"] == H.D1_CLOSE
    assert "no live prices came back" in (d1["reason"] or "")
    assert d1["market_closed"] is None


def test_no_benchmark_print_keeps_the_whole_board_on_close(monkeypatch):
    no_bench = {"TENB": {"price": 36.68, "change_pct": -3.70}}
    board = _build_with(_live(lambda s: no_bench, monkeypatch))
    d1 = board[H.D1_KEY]
    assert d1["live"] is False and "RSP" in (d1["reason"] or "")
    assert d1["market_closed"] is None
    rows = {n["symbol"]: n for n in board["sectors"][0]["names"]}
    assert all(r["d1_source"] == H.D1_CLOSE for r in rows.values())


def test_a_raising_fetch_never_raises_out(monkeypatch):
    def _boom(syms):
        raise TimeoutError("provider timed out")

    board = _build_with(_live(_boom, monkeypatch))
    d1 = board[H.D1_KEY]
    assert d1["basis"] == H.D1_CLOSE
    assert "the live price read failed" in (d1["reason"] or "")
    assert d1["market_closed"] is None
    # the session keys survive a failed read — the button still knows what to say
    assert d1["session_window"] == "9:30-16:00 ET"


def test_the_pure_build_carries_the_keys_as_unknown():
    """`build()` makes no live read at all. The three keys must exist and be
    None rather than absent, so the FE has one shape to reason about."""
    d1 = H.build(_payload())[H.D1_KEY]
    assert d1["market_closed"] is None
    assert d1["in_session"] is None
    assert d1["session_window"] is None
    assert d1["group_basis"] == H.D1_CLOSE
