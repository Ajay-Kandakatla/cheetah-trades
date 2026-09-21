"""🌀 AMD: "These chips are not working" (Ajay 2026-09-21, ~09:05 ET).

His screenshot of the AMD Raided tab in pre-market: `🔄 Reclaimed today · 43`,
`🛡️ Holding the edge · 0`. Both numbers were fabrications of the same shape.

WHAT THE FEED ACTUALLY SENDS BEFORE THE FIRST REGULAR-SESSION PRINT. Two rows,
both real, both measured in-container this morning:

  1. the ZERO aggregate — ANAB at 09:30:09 ET:
     {"open": 0, "high": 0, "low": 0, "close": 0, "volume": 0,
      "date": "2026-09-21", "last_trade_price": 56, "prev_day_close": 55.2}
     `_f(0)` is `0.0`, not None, so `day_low < base_lo` was True for every
     name with a base — 43 of them read "today's low pierced the edge".
     Note the clock: 09:30:09 is INSIDE regular hours. The zero outlives the
     bell, so nothing here may key on the time of day.

  2. the PHANTOM ECHO — the shape `prices._drop_phantom_tail` documents
     (caught 2026-09-14 09:22 ET, every Hot Sectors member +0.1%): the prior
     session's COMPLETED aggregate re-stamped with today's date. Its low is a
     real, positive number belonging to a session that is over. A value-only
     guard reads Friday's low as today's and serves `reclaimed` / `holding`
     with full confidence.

The only field that says WHICH session a row is from is its own print stamp —
`prices.extended_print(snap)`, the ET date and session of the last trade. Not
`snap["date"]` (stamped today-ET whenever `day.t` is absent, so on a Saturday
it dates Friday's aggregate Saturday) and not the wall clock (see ANAB).

So: no session low -> `state: "unknown"` with the served reason, and
`flight_scope` says how many names that is. NOTHING about the AMD detector,
its grades or any threshold changes here — the read is still MEASURED INVERTED
(-4.2pp vs placebo, 2026-09-14, 3,712 names) and still gates nothing.
"""
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from chart_maps import board as B
from supply_demand import turning_bullish as TBm

ET = ZoneInfo("America/New_York")
SESSION = "2026-09-21"                       # a Monday
_BASE = {"base_lo": 53.41, "base_hi": 60.0, "grade": "raided"}


def _ns(y, mo, d, h, mi):
    """A Massive last-trade stamp: NANOSECONDS (memory cheetah_supply_watch —
    `_trade_epoch` divides by 1e9 above 1e15; milliseconds here would read as
    a 1970 date and `extended_print` would come back None)."""
    return int(datetime(y, mo, d, h, mi, tzinfo=ET).timestamp() * 1_000_000_000)


# ── 1. the two pre-session shapes ──────────────────────────────────────────
def test_the_ANAB_repro_is_unknown_never_reclaimed():
    """The row off the live stack at 09:30:09 ET. Before 2026-09-21 this
    served `reclaimed` — 0.0 is under every base floor ever drawn."""
    f = B._amd_flight(_BASE, {"last_trade_price": 55.35, "low": 0.0},
                      low_session=SESSION)
    assert f["state"] == B.AMD_FLIGHT_UNKNOWN
    assert f["state"] != "reclaimed"
    assert f["above_edge"] is True
    assert f["day_low"] is None
    assert f["pierce_pct"] is None
    assert f["swept_today"] is None
    assert f["low_session"] is None
    assert f["reason"] == B.NO_SESSION_LOW_REASON


def test_the_PHANTOM_ECHO_is_unknown_even_though_its_low_looks_real():
    """Monday 08:05 ET. The low (53.00) is under the base floor (53.41) and
    positive — a value-only guard calls this `reclaimed` with a straight face.
    It is Friday's low, re-stamped with Monday's date."""
    echo = {"last_trade_price": 55.9, "price": 55.9, "close": 55.2,
            "low": 53.0, "date": SESSION,
            "last_trade_ts_ms": _ns(2026, 9, 21, 8, 5)}
    f = B._amd_flight(_BASE, echo, low_session=SESSION)
    assert f["state"] == B.AMD_FLIGHT_UNKNOWN
    assert f["state"] != "reclaimed"
    assert f["day_low"] is None
    assert f["print_session"] == "premarket"
    assert f["print_date"] == SESSION
    assert f["low_session"] is None
    assert f["reason"] == B.NO_SESSION_LOW_REASON


def test_the_ECHO_with_no_premarket_print_yet_is_unknown_by_DATE():
    """Same row, but nothing has traded since Friday 19:59 — the stamp is
    Friday's. The session check is the date, not only the session name."""
    echo = {"last_trade_price": 55.9, "low": 53.0, "date": SESSION,
            "last_trade_ts_ms": _ns(2026, 9, 18, 19, 59)}
    f = B._amd_flight(_BASE, echo, low_session=SESSION)
    assert f["state"] == B.AMD_FLIGHT_UNKNOWN
    assert f["print_session"] == "afterhours"
    assert f["print_date"] == "2026-09-18"
    assert f["day_low"] is None


def test_NEGATIVE_the_same_low_with_a_REGULAR_SESSION_stamp_IS_reclaimed():
    """The mirror of the echo test — this is what must NOT be broken. Once the
    print is from this session, the low is this session's and the state is a
    measurement again."""
    live = {"last_trade_price": 55.9, "low": 53.0, "date": SESSION,
            "last_trade_ts_ms": _ns(2026, 9, 21, 10, 15)}
    f = B._amd_flight(_BASE, live, low_session=SESSION)
    assert f["state"] == "reclaimed"
    assert f["day_low"] == 53.0
    assert f["low_session"] == SESSION
    assert f["print_session"] == "rth"
    assert f["reason"] is None
    assert f["pierce_pct"] is not None


def test_NEGATIVE_an_AFTER_HOURS_print_from_today_still_reads():
    """After 16:00 the day aggregate is complete and it IS today's. Treating
    every non-rth print as unusable would blank the board every evening."""
    live = {"last_trade_price": 56.4, "low": 53.0, "date": SESSION,
            "last_trade_ts_ms": _ns(2026, 9, 21, 18, 30)}
    f = B._amd_flight(_BASE, live, low_session=SESSION)
    assert f["state"] == "reclaimed"
    assert f["print_session"] == "afterhours"
    assert f["low_session"] == SESSION


# ── 2. negatives on the low itself ─────────────────────────────────────────
@pytest.mark.parametrize("snap,why", [
    ({"last_trade_price": 110.0}, "no low key at all"),
    ({"last_trade_price": 110.0, "low": None}, "an explicit None low"),
    ({"last_trade_price": 110.0, "low": -1.0}, "a negative low"),
    ({"last_trade_price": 110.0, "low": "0"}, "the string zero"),
    ({"last_trade_price": 110.0, "low": 0}, "the integer zero"),
])
def test_NEGATIVE_no_usable_low_is_unknown_never_holding(snap, why):
    """`holding` means "today's low never reached the edge" — a claim about a
    low. Without one it is not a quiet default, it is unknown."""
    f = B._amd_flight(_BASE, snap, low_session=SESSION)
    assert f["state"] == B.AMD_FLIGHT_UNKNOWN, why
    assert f["state"] != "holding", why
    assert f["day_low"] is None
    assert f["reason"] == B.NO_SESSION_LOW_REASON


def test_SWEEPING_is_read_from_the_live_print_alone():
    """The one state that never needed a low: the print is under the edge NOW.
    It survives the zero aggregate and it survives the echo."""
    zero = B._amd_flight(_BASE, {"last_trade_price": 52.0, "low": 0.0},
                         low_session=SESSION)
    assert zero["state"] == "sweeping"
    assert zero["swept_today"] is True
    assert zero["pierce_pct"] is None            # no low to measure the pierce
    assert zero["reason"] is None
    assert zero["above_edge"] is False

    echo = B._amd_flight(_BASE, {"last_trade_price": 52.0, "low": 53.0,
                                 "last_trade_ts_ms": _ns(2026, 9, 21, 8, 5)},
                         low_session=SESSION)
    assert echo["state"] == "sweeping"


def test_NEGATIVE_nothing_known_is_still_None_not_an_unknown_block():
    """No base edge, or no print at all — there is nothing to serve, not even
    a state. The 09-17 contract for those rows is untouched."""
    assert B._amd_flight({}, {"last_trade_price": 10.0}) is None
    assert B._amd_flight(_BASE, {}) is None
    assert B._amd_flight(_BASE, {"low": 99.0}) is None
    assert B._amd_flight({"base_lo": 0}, {"last_trade_price": 10.0}) is None
    assert B._amd_flight(None, None) is None


def test_the_three_09_17_triples_are_unchanged_on_an_unstamped_row():
    """The 2026-09-17 fixtures carry no `last_trade_ts_ms`, so `extended_print`
    is None and the value-only rule applies — exactly as it did then."""
    v = {"base_lo": 100.0, "base_hi": 120.0}

    def _snap(price, low):
        return {"last_trade_price": price, "price": price, "low": low}

    assert B._amd_flight(v, _snap(97.0, 96.0))["state"] == "sweeping"
    assert B._amd_flight(v, _snap(101.0, 98.0))["state"] == "reclaimed"
    assert B._amd_flight(v, _snap(110.0, 105.0))["state"] == "holding"
    # with a session passed they now say WHICH session the low belongs to
    assert B._amd_flight(v, _snap(110.0, 105.0),
                         low_session=SESSION)["low_session"] == SESSION
    assert B._amd_flight(v, _snap(110.0, 105.0))["print_session"] is None


def test_low_session_is_None_whenever_the_low_is_not(monkeypatch):
    """Passing a session must never LABEL a low that does not exist."""
    f = B._amd_flight(_BASE, {"last_trade_price": 110.0, "low": 0},
                      low_session=SESSION)
    assert f["low_session"] is None


# ── 3. the weekend / holiday read ──────────────────────────────────────────
def test_a_SATURDAY_read_labels_FRIDAYS_low_friday():
    """`_session_day` is the shipped calendar, not the calendar date. On a
    Saturday the row IS Friday's completed aggregate and its print stamp is
    Friday's — a real low, correctly labelled, not "today"."""
    sat = datetime(2026, 9, 19, 10, 0, tzinfo=ET)
    assert B._session_day(sat).isoformat() == "2026-09-18"

    fri = "2026-09-18"
    row = {"last_trade_price": 56.0, "low": 53.0,
           "last_trade_ts_ms": _ns(2026, 9, 18, 15, 59)}
    f = B._amd_flight(_BASE, row, low_session=fri)
    assert f["state"] == "reclaimed"
    assert f["low_session"] == fri
    assert f["print_date"] == fri


def test_a_HOLIDAY_monday_reads_the_prior_session_too():
    """Labor Day 2026-09-07: the calendar date is not a session, the shipped
    holiday list backs up to Friday the 4th."""
    holiday = datetime(2026, 9, 7, 11, 0, tzinfo=ET)
    assert B._session_day(holiday).isoformat() == "2026-09-04"


# ── 4. the source pins ─────────────────────────────────────────────────────
def test_NO_THRESHOLD_is_invented_inside_the_flight_read():
    """The 2026-09-17 pin, still standing: not one bucket, level or stop is
    typed in this function — the sentence it serves lives at module level."""
    import inspect
    src = inspect.getsource(B._amd_flight)
    for invented in ("0.5", "1.0", "2.0", "3.0", "5.0"):
        assert invented not in src, invented
    assert "no session low yet" not in src
    assert isinstance(B.NO_SESSION_LOW_REASON, str)
    assert isinstance(B.AMD_FLIGHT_UNKNOWN, str)


def test_the_served_wording_says_neither_bounce_nor_an_ungiven_number():
    """"Reversal", never "bounce", on a surface he reads — and no number in
    the prose that did not come from a measurement or the clock."""
    import re
    for text in (B.NO_SESSION_LOW_REASON, B.FLIGHT_COST_NOTE):
        assert "bounce" not in text.lower()
    assert "bounce" not in B.NO_SESSION_LOW_REASON.lower()
    # the only digits in the reason are the opening bell
    assert set(re.findall(r"\d+", B.NO_SESSION_LOW_REASON)) == {"09", "30"}
    # every digit in the cost note comes from the measured dict
    m = B.FLIGHT_COST_MEASURED
    for key in ("n_default", "n_all"):
        assert str(m[key]) in B.FLIGHT_COST_NOTE
    assert m["date"] in B.FLIGHT_COST_NOTE


def test_unknown_is_NOT_a_state_and_NOT_a_selectable_filter():
    """The chip row iterates AMD_FLIGHT_STATES; a fourth member would print a
    chip nobody asked for and make "unknown" a filter that means "broken"."""
    assert B.AMD_FLIGHT_STATES == ("sweeping", "reclaimed", "holding")
    assert B.AMD_FLIGHT_UNKNOWN not in B.AMD_FLIGHT_STATES
    assert B.parse_flight("unknown") is None
    assert B.parse_flight("unknown,sweeping") == frozenset({"sweeping"})


# ── 5. the board: counts, scope, and the population rule ───────────────────
def _row(sym, base_lo=100.0):
    return {"symbol": sym, "amd": {"base_lo": base_lo, "base_hi": base_lo * 1.2,
                                   "grade": "raided"},
            "last_close": base_lo}


@pytest.fixture
def amd_board(monkeypatch):
    """`turning_bullish_tiles` with every I/O leg replaced by a double.

    The TB.board double mirrors the REAL signature
    `board(kind, limit=120, db=None, grades=None)` (memory
    cheetah_amd_manipulation) and, like the real one, sorts THEN slices.
    """
    from sepa import scanner

    state = {"pool": [], "snaps": {}, "tb_calls": [], "snap_calls": []}

    def _tb(kind, limit=120, db=None, grades=None):
        state["tb_calls"].append({"kind": kind, "limit": limit, "grades": grades})
        rows = state["pool"]
        return {"kind": kind, "rows": rows[:limit], "n": len(rows),
                "n_all": len(rows), "capped": False, "n_scanned": len(rows),
                "n_rows": len(rows), "counts": {}, "built_at": None,
                "params": {}, "grades": ["raided"], "grades_all": ["raided"],
                "grade_counts": {"raided": len(rows)}}

    def _snaps(syms):
        syms = sorted({(s or "").upper() for s in syms if s})
        state["snap_calls"].append(syms)
        return {s: state["snaps"][s] for s in syms if s in state["snaps"]}

    monkeypatch.setattr(TBm, "board", _tb)
    monkeypatch.setattr(B, "_bulk_snaps", _snaps)
    monkeypatch.setattr(scanner, "load_latest", lambda *a, **k: {"all_results": []})
    monkeypatch.setattr(B, "bars_for",
                        lambda sym, days=130, **k: [{"t": SESSION, "o": 1, "h": 1,
                                                     "l": 1, "c": 1, "v": 1}])
    monkeypatch.setattr(B, "_attach_bars", lambda tiles, days, **k: None)
    monkeypatch.setattr(B, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(B, "attach_velocity", lambda tiles, **k: 0)
    monkeypatch.setattr(B, "_velocity_decor", lambda tiles: None)
    monkeypatch.setattr(B, "_session_day", lambda *a, **k: __import__(
        "datetime").date(2026, 9, 21))
    return state


def test_a_PREMARKET_pool_counts_unknown_and_says_why(amd_board):
    """His morning, reproduced over a pool: every priced name carries the zero
    aggregate, three of them print under their edge."""
    amd_board["pool"] = [_row("S%d" % i) for i in range(40)]
    for i in range(40):
        sym = "S%d" % i
        px = 95.0 if i < 3 else 105.0            # three are sweeping
        amd_board["snaps"][sym] = {"last_trade_price": px, "low": 0.0,
                                   "date": SESSION}
    # four more names the live call never answered for
    amd_board["pool"] += [_row("Q%d" % i) for i in range(4)]

    out = B.turning_bullish_tiles("amd", limit=80)
    fc, scope = out["flight_counts"], out["flight_scope"]

    assert fc == {"sweeping": 3, "reclaimed": 0, "holding": 0, "unknown": 37}
    assert sum(fc.values()) == scope["priced"] == 40
    assert scope["counted"] == 44
    assert scope["no_print"] == 4
    assert scope["no_session_low"] == fc["unknown"] == 37
    assert scope["unknowable"] == ["reclaimed", "holding"]
    assert scope["low_session"] is None
    assert scope["reason"] == B.NO_SESSION_LOW_REASON
    assert scope["reason_line"] == (
        "37 of 40 priced names have " + B.NO_SESSION_LOW_REASON)
    assert scope["note"] == B.FLIGHT_COST_NOTE
    assert str(B.FLIGHT_COST_MEASURED["n_default"]) in scope["note"]


def test_a_MIXED_pool_is_measured_again_and_nothing_is_unknowable(amd_board):
    """Once some names have a real session low, `reclaimed`/`holding` are
    answerable — the `—` chips go back to numbers even while others are
    unknown."""
    amd_board["pool"] = [_row(s) for s in ("A", "B", "C", "D")]
    stamp = _ns(2026, 9, 21, 10, 30)
    amd_board["snaps"] = {
        "A": {"last_trade_price": 105.0, "low": 98.0, "last_trade_ts_ms": stamp},
        "B": {"last_trade_price": 105.0, "low": 102.0, "last_trade_ts_ms": stamp},
        "C": {"last_trade_price": 95.0, "low": 94.0, "last_trade_ts_ms": stamp},
        "D": {"last_trade_price": 105.0, "low": 0.0},
    }
    out = B.turning_bullish_tiles("amd", limit=80)
    fc, scope = out["flight_counts"], out["flight_scope"]
    assert fc == {"sweeping": 1, "reclaimed": 1, "holding": 1, "unknown": 1}
    assert sum(fc.values()) == scope["priced"] == 4
    assert scope["unknowable"] == []
    assert scope["no_session_low"] == 1
    assert scope["low_session"] == SESSION
    assert scope["reason"] == B.NO_SESSION_LOW_REASON
    assert scope["reason_line"].startswith("1 of 4 priced names have ")


def test_NEGATIVE_a_fully_measured_pool_says_nothing_at_all(amd_board):
    """No unknowns -> no reason, no line. The surface must not carry a
    permanent caveat once the tape is answering."""
    amd_board["pool"] = [_row("A"), _row("B")]
    stamp = _ns(2026, 9, 21, 11, 0)
    amd_board["snaps"] = {
        "A": {"last_trade_price": 105.0, "low": 98.0, "last_trade_ts_ms": stamp},
        "B": {"last_trade_price": 105.0, "low": 102.0, "last_trade_ts_ms": stamp},
    }
    scope = B.turning_bullish_tiles("amd", limit=80)["flight_scope"]
    assert scope["no_session_low"] == 0
    assert scope["reason"] is None
    assert scope["reason_line"] is None
    assert scope["unknowable"] == []


def test_NEGATIVE_no_live_quotes_at_all_says_so(amd_board):
    """A tape outage is not "0 reclaimed". Nothing was counted and the scope
    says which of the two it is."""
    amd_board["pool"] = [_row("A"), _row("B")]
    amd_board["snaps"] = {}
    out = B.turning_bullish_tiles("amd", limit=80)
    assert out["flight_counts"] == {"sweeping": 0, "reclaimed": 0,
                                    "holding": 0, "unknown": 0}
    scope = out["flight_scope"]
    assert scope["priced"] == 0
    assert scope["no_print"] == 2
    assert scope["reason"] == "no live quotes came back"
    assert scope["reason_line"] is None
    assert scope["unknowable"] == []


# ── 6. D3: the count IS what the click returns ─────────────────────────────
def test_the_chip_count_equals_the_names_a_click_returns(amd_board):
    """His actual complaint: the chips said 43 and the click showed 14, because
    the count was over the page and the filter searched the sweep. One pool
    now feeds both."""
    import datetime as _dt
    amd_board["pool"] = [_row("N%03d" % i) for i in range(300)]
    stamp = _ns(2026, 9, 21, 11, 0)
    for i in range(300):
        sym = "N%03d" % i
        if i % 3 == 0:
            snap = {"last_trade_price": 95.0, "low": 94.0, "last_trade_ts_ms": stamp}
        elif i % 3 == 1:
            snap = {"last_trade_price": 105.0, "low": 98.0, "last_trade_ts_ms": stamp}
        else:
            snap = {"last_trade_price": 105.0, "low": 102.0, "last_trade_ts_ms": stamp}
        amd_board["snaps"][sym] = snap

    counts = B.turning_bullish_tiles("amd", limit=80)["flight_counts"]
    for st in B.AMD_FLIGHT_STATES:
        picked = B.turning_bullish_tiles("amd", limit=1000, flight=st)
        assert counts[st] == len(picked["tiles"]), st


def test_the_whole_sweep_is_scanned_on_EVERY_amd_request(amd_board):
    """Not only when a filter is on. The counts promise the grade set, so the
    pool has to be the grade set even for the plain board."""
    amd_board["pool"] = [_row("A"), _row("B")]
    amd_board["snaps"] = {"A": {"last_trade_price": 105.0, "low": 98.0}}

    B.turning_bullish_tiles("amd", limit=5)
    B.turning_bullish_tiles("amd", limit=5, flight="sweeping")
    assert [c["limit"] for c in amd_board["tb_calls"]] == \
        [B.TB_FLIGHT_SCAN_LIMIT, B.TB_FLIGHT_SCAN_LIMIT]

    amd_board["tb_calls"].clear()
    B.turning_bullish_tiles("keltner", limit=5)
    assert amd_board["tb_calls"][0]["limit"] == 5


def test_the_unfiltered_page_is_IDENTICAL_to_the_old_one(amd_board):
    """TB.board sorts then slices, so asking for the sweep and cutting to
    `limit` is the same rows in the same order as asking for `limit`. If this
    ever drifts, widening the count silently changed the board he reads."""
    amd_board["pool"] = [_row("P%03d" % i) for i in range(200)]
    out = B.turning_bullish_tiles("amd", limit=25)
    assert [t["symbol"] for t in out["tiles"]] == \
        ["P%03d" % i for i in range(25)]


def test_ONE_bulk_call_per_request_even_with_a_filter(amd_board):
    amd_board["pool"] = [_row("A"), _row("B"), _row("C")]
    amd_board["snaps"] = {"A": {"last_trade_price": 95.0, "low": 0.0}}
    B.turning_bullish_tiles("amd", limit=80, flight="sweeping")
    assert len(amd_board["snap_calls"]) == 1
    assert set(amd_board["snap_calls"][0]) == {"A", "B", "C"}


# ── 7. the ctx handoff (no private payload key) ────────────────────────────
def test_the_payload_carries_NO_private_key_and_json_dumps_bare(amd_board):
    """Raw snapshot rows hold pandas Timestamps. If one ever rode on the
    payload, `json.dumps` without `default=` is where it shows up — which is
    what FastAPI does for real."""
    import pandas as pd
    amd_board["pool"] = [_row("A")]
    amd_board["snaps"] = {"A": {"last_trade_price": 105.0, "low": 98.0,
                                "date": pd.Timestamp("2026-09-21")}}
    out = B.turning_bullish_tiles("amd", limit=5)
    assert "_snaps" not in out
    assert [k for k in out if k.startswith("_")] == []
    json.dumps(out)                              # no default= on purpose


def test_ctx_receives_exactly_one_key_and_it_is_the_raw_map(amd_board):
    amd_board["pool"] = [_row("A")]
    amd_board["snaps"] = {"A": {"last_trade_price": 105.0, "low": 98.0}}
    ctx: dict = {}
    B.turning_bullish_tiles("amd", limit=5, ctx=ctx)
    assert list(ctx) == ["snaps"]
    assert ctx["snaps"] == {"A": {"last_trade_price": 105.0, "low": 98.0}}


def test_keltner_carries_no_flight_scope(amd_board):
    """The other turning-bullish tab has no in-flight read at all — it must
    not inherit an empty scope block that the page would then render."""
    amd_board["pool"] = [{"symbol": "K", "keltner": {}, "last_close": 10.0}]
    out = B.turning_bullish_tiles("keltner", limit=5)
    assert out["flight_scope"] is None
