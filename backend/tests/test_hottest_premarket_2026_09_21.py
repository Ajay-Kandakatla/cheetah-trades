"""🔥 Hottest — the ☀️ Pre-market scan (Ajay 2026-09-21).

  *"In the hot sector table can I get a pre market scan please"*

WHAT IS PINNED HERE
-------------------
1. A pre-market print counts only when it is PRE-MARKET and TODAY. Friday's
   after-hours print is still sitting in Monday's snapshot; 09:31 is the open.
2. Nothing RELATIVE is served without RSP's own pre-market print — a raw move
   in a relative column is a different measurement wearing the same header.
3. The day column is BYTE-IDENTICAL whether or not the pre leg ran.
4. ONE fan-out for both legs (7 chunks, not 14).
5. ONE clock per block: calendar, session and date all read the SAME `now`.
6. ONE clock FORMAT: `9:30 ET`, never `09:30 ET`.
7. The stored read is re-clocked on every serve — a doc written at 07:20 can
   never re-enable the ☀️ button at 10:05.
8. `sort=pre_1d` with nothing to rank on is DEMOTED, and `sorted_by` says so.
9. `moves` / `_id` / `stored_at` never reach the wire.

NOTHING HERE IS MEASURED. A pre-market move has no measured forward edge on
this board or any other; this is a read of the tape before the open.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, time as dtime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rotation import hottest as H   # noqa: E402
from sepa import prices as P        # noqa: E402


ET = ZoneInfo("America/New_York")
MON = datetime(2026, 9, 21, 7, 42, tzinfo=ET)      # Monday pre-market
SAT = datetime(2026, 9, 19, 7, 0, tzinfo=ET)       # Saturday
RTH = datetime(2026, 9, 21, 10, 5, tzinfo=ET)      # Monday, session open
NIGHT = datetime(2026, 9, 21, 1, 0, tzinfo=ET)     # Monday, before 4:00
EVE = datetime(2026, 9, 21, 17, 0, tzinfo=ET)      # Monday, after-hours

BENCH = {"symbol": "RSP", "ret_1d": -0.28, "ret_5d": -1.08,
         "ret_21d": -3.76, "ret_63d": 0.71}


def _ns(dt: datetime) -> int:
    """Massive's real stamp shape — nanoseconds (memory trap)."""
    return int(dt.timestamp() * 1e9)


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1e3)


def _snap(last: float, prev: float, at: datetime, *, ms: bool = False) -> dict:
    """A pre-open `bulk_live_prices` row: the day bar is 0, the print moves."""
    return {"price": 0, "change_pct": 0, "low": None, "open": None,
            "volume": 0, "last_trade_price": last,
            "last_trade_ts_ms": _ms(at) if ms else _ns(at),
            "prev_day_close": prev}


def _payload(symbols=None) -> dict:
    """Two names in one sector/industry, plus a theme roster over the same
    names — the shape `test_hot_sectors_rescan_2026_09_18.py:42` uses."""
    syms = symbols or ["TENB", "QLYS"]
    by = {}
    for i, s in enumerate(syms):
        by[s] = {"last_close": 100.0 + i, "ret_1d": 1.0 + i, "ret_5d": 2.0 + i,
                 "ret_21d": 3.0 + i, "ret_63d": 4.0 + i,
                 "sector": "Technology",
                 "industry": "Software - Infrastructure"}
    return {
        "as_of": "2026-09-18",
        "sectors": [{"group": "Technology", "n": 40, "rel_1d": -0.59,
                     "rel_5d": 2.0, "rel_21d": -4.27, "pct_positive_1d": 30}],
        "industries": [], "themes": [], "sampled": {},
        H.T.MEMBERS_KEY: {
            "benchmark": dict(BENCH),
            "by_symbol": by,
            "groups": {"sector": {"Technology": {"median_21d": -4.27,
                                                 "symbols": list(syms)}},
                       "theme": {"ai_semis": {"median_21d": -1.0,
                                              "symbols": list(syms)}}},
        },
    }


def _build_with(pre=None, live=None, sort="rel_5d", direction="desc",
                symbols=None) -> dict:
    return H._build(_payload(symbols), sort=sort, direction=direction,
                    names_per_group=25, decisions={}, earnings={},
                    live=live, pre=pre)


def _rows(board: dict) -> dict:
    return {r["symbol"]: r for r in board["sectors"][0]["names"]}


def _live_day() -> dict:
    """A LIVE day block, built by hand so no clock is consulted."""
    return {"basis": H.D1_LIVE, "live": True, "benchmark": "RSP",
            "benchmark_move": -0.50, "symbols": 2, "live_names": 2,
            "moves": {"TENB": -3.70, "QLYS": -2.79}, "as_of": "x",
            "reason": None, "market_closed": None, "in_session": True,
            "session_window": "9:30-16:00 ET"}


def _close_day() -> dict:
    return {"basis": H.D1_CLOSE, "live": False, "benchmark": "RSP",
            "benchmark_move": None, "symbols": 2, "live_names": 0,
            "moves": {}, "as_of": None, "reason": "no live price for RSP",
            "market_closed": None, "in_session": False,
            "session_window": "9:30-16:00 ET"}


# RSP +0.50% pre-market (212.29 → 213.35); TENB +2.00%; QLYS flat.
_PRE_SNAPS = {
    "RSP": _snap(213.35, 212.29, datetime(2026, 9, 21, 5, 0, tzinfo=ET)),
    "TENB": _snap(102.0, 100.0, datetime(2026, 9, 21, 7, 27, tzinfo=ET)),
    "QLYS": _snap(101.0, 101.0, datetime(2026, 9, 21, 7, 30, tzinfo=ET)),
}


def _pre_live(symbols=None, snaps=None, now=MON) -> dict:
    calls = []

    def _fetch(syms):
        calls.append(list(syms))
        return dict(snaps or _PRE_SNAPS)

    block = H.premarket_moves(symbols or ["TENB", "QLYS"], "RSP",
                              fetch=_fetch, now=now)
    block["_calls"] = calls
    return block


class _Coll:
    """The smallest thing `store_premarket` / `load_premarket` need."""

    def __init__(self, docs=None):
        self.docs = dict(docs or {})
        self.writes = 0

    def update_one(self, flt, update, upsert=False):
        self.writes += 1
        self.docs[flt["_id"]] = dict(update["$set"])

    def find_one(self, flt):
        d = self.docs.get(flt["_id"])
        return dict(d) if d else None


# ---------------------------------------------------------------------------
# 1-3 — what counts as a pre-market print
# ---------------------------------------------------------------------------
def test_a_print_today_in_the_window_counts_and_is_relative_to_rsp():
    b = _pre_live()
    assert b["live"] is True and b["ran"] is True
    assert b["benchmark_pre_move"] == 0.50
    # 102.0 / 100.0 - 1 = +2.00%, minus RSP's +0.50% = +1.50%
    assert b["moves"]["TENB"]["pre_raw"] == 2.00
    assert b["moves"]["TENB"]["pre_1d"] == 1.50
    assert b["moves"]["QLYS"]["pre_raw"] == 0.0
    assert b["moves"]["QLYS"]["pre_1d"] == -0.50
    assert b["pre_names"] == 2 and b["symbols"] == 2


def test_a_ms_stamp_reads_the_same_as_an_ns_stamp():
    snaps = dict(_PRE_SNAPS)
    snaps["TENB"] = _snap(102.0, 100.0,
                          datetime(2026, 9, 21, 7, 27, tzinfo=ET), ms=True)
    b = _pre_live(snaps=snaps)
    assert b["moves"]["TENB"]["pre_1d"] == 1.50
    assert b["moves"]["TENB"]["pre_at_et"] == "7:27 ET"


def test_negative_fridays_after_hours_print_is_not_mondays_premarket():
    friday_ah = _snap(120.0, 100.0, datetime(2026, 9, 18, 17, 30, tzinfo=ET))
    assert P.extended_print(friday_ah)["session"] == "afterhours"
    assert H._pre_print(friday_ah, "2026-09-21") is None
    # and a print dated today but stamped 03:59 is not in the window either
    early = _snap(120.0, 100.0, datetime(2026, 9, 21, 3, 59, tzinfo=ET))
    assert H._pre_print(early, "2026-09-21") is None


def test_negative_a_friday_premarket_print_still_fails_the_date_check():
    """Same SESSION, wrong DAY — the date check is what catches this one."""
    fri_pre = _snap(120.0, 100.0, datetime(2026, 9, 18, 7, 0, tzinfo=ET))
    assert P.extended_print(fri_pre)["session"] == "premarket"
    assert H._pre_print(fri_pre, "2026-09-21") is None


@pytest.mark.parametrize("hh,mm,counts", [(3, 59, False), (4, 0, True),
                                          (9, 29, True), (9, 30, False),
                                          (9, 31, False)])
def test_the_window_boundaries_both_sides(hh, mm, counts):
    snap = _snap(102.0, 100.0, datetime(2026, 9, 21, hh, mm, tzinfo=ET))
    assert (H._pre_print(snap, "2026-09-21") is not None) is counts


# ---------------------------------------------------------------------------
# 4-5 — the negatives that decide whether anything is served at all
# ---------------------------------------------------------------------------
def test_negative_no_rsp_print_serves_nothing_relative():
    snaps = dict(_PRE_SNAPS)
    snaps["RSP"] = {"price": 0, "change_pct": 0, "last_trade_price": 0,
                    "last_trade_ts_ms": 0, "prev_day_close": 212.29}
    b = _pre_live(snaps=snaps)
    assert b["live"] is False and b["ran"] is True and b["moves"] == {}
    assert "RSP" in b["reason"] and "nothing can be measured" in b["reason"]
    board = _build_with(pre=b, live=_close_day())
    for r in _rows(board).values():
        assert r["pre_1d"] is None
    assert board["sectors"][0]["pre_n"] == 0
    assert board["sectors"][0][H.PRE_SORT] is None


def test_negative_a_name_without_a_print_is_none_not_zero():
    snaps = dict(_PRE_SNAPS)
    snaps["QLYS"] = {"price": 0, "change_pct": 0, "last_trade_price": None,
                     "last_trade_ts_ms": None, "prev_day_close": 101.0}
    b = _pre_live(snaps=snaps)
    assert "QLYS" not in b["moves"] and b["pre_names"] == 1
    r = _rows(_build_with(pre=b, live=_close_day()))["QLYS"]
    assert r["pre_1d"] is None
    assert r["pre_raw"] is None and r["pre_print"] is None
    assert r["pre_at"] is None and r["pre_at_et"] is None


@pytest.mark.parametrize("prev", [0, None, -1.0, "x"])
def test_negative_an_unusable_previous_close_yields_no_move(prev):
    snap = _snap(102.0, 100.0, datetime(2026, 9, 21, 7, 0, tzinfo=ET))
    snap["prev_day_close"] = prev
    assert H._pre_print(snap, "2026-09-21") is None


def test_negative_no_name_printed_at_all():
    snaps = {"RSP": _PRE_SNAPS["RSP"]}
    b = _pre_live(snaps=snaps)
    assert b["live"] is False and b["ran"] is True
    assert b["reason"] == "no name on this board has printed pre-market yet"


def test_negative_a_failed_read_still_says_it_ran():
    def _boom(_syms):
        raise RuntimeError("provider down")

    b = H.premarket_moves(["TENB"], "RSP", fetch=_boom, now=MON)
    assert b["ran"] is True and b["live"] is False
    assert b["reason"] == "the pre-market read failed (RuntimeError)"


def test_negative_no_symbols_never_reaches_the_fetcher():
    calls = []
    b = H.premarket_moves([], "RSP", fetch=lambda s: calls.append(s) or {},
                          now=MON)
    assert b["reason"] == "no symbols to price" and calls == []
    assert b["ran"] is False


# ---------------------------------------------------------------------------
# 6-7 — group rows
# ---------------------------------------------------------------------------
def test_group_median_is_over_the_members_that_printed_only():
    syms = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    at = datetime(2026, 9, 21, 7, 0, tzinfo=ET)
    snaps = {"RSP": _PRE_SNAPS["RSP"]}
    for s, last in zip(syms[:3], (101.0, 102.0, 105.0)):
        snaps[s] = _snap(last, 100.0, at)
    for s in syms[3:]:
        snaps[s] = {"price": 0, "change_pct": 0, "last_trade_price": 0,
                    "last_trade_ts_ms": 0, "prev_day_close": 100.0}
    b = _pre_live(symbols=syms, snaps=snaps)
    board = _build_with(pre=b, live=_close_day(), symbols=syms)
    sector = board["sectors"][0]
    ind = sector["industries"][0]
    theme = board["themes"][0]
    # raw +1 / +2 / +5 minus RSP's +0.5 → 0.5 / 1.5 / 4.5, median 1.5
    for row in (sector, ind, theme):
        assert row[H.PRE_SORT] == 1.5
        assert row["pre_n"] == 3
        assert row["n_full"] == 5
        assert row["pre_basis"] == H.PRE_GROUP_BASIS


@pytest.mark.parametrize("printed,thin", [(H.THIN_N, False),
                                          (H.THIN_N - 1, True)])
def test_pre_thin_boundary_reuses_the_boards_own_thin_rule(printed, thin):
    syms = [f"S{i:02d}" for i in range(H.THIN_N + 2)]
    at = datetime(2026, 9, 21, 7, 0, tzinfo=ET)
    snaps = {"RSP": _PRE_SNAPS["RSP"]}
    for i, s in enumerate(syms):
        snaps[s] = (_snap(101.0, 100.0, at) if i < printed
                    else {"price": 0, "change_pct": 0, "last_trade_price": 0,
                          "last_trade_ts_ms": 0, "prev_day_close": 100.0})
    b = _pre_live(symbols=syms, snaps=snaps)
    sector = _build_with(pre=b, live=_close_day(), symbols=syms)["sectors"][0]
    assert sector["pre_n"] == printed
    assert sector["pre_thin"] is thin
    # the MEMBERSHIP flag is a different question and is never overwritten
    assert sector.get("thin") is None or "thin" not in sector


def test_the_membership_thin_flag_is_untouched_on_industry_and_theme_rows():
    b = _pre_live()
    board = _build_with(pre=b, live=_close_day())
    ind = board["sectors"][0]["industries"][0]
    theme = board["themes"][0]
    for row in (ind, theme):
        assert row["thin"] is True          # 2 MEMBERS, under THIN_N
        assert row["pre_thin"] is True      # 2 PRINTED, under THIN_N — a
        assert row["pre_n"] == 2            # second flag, never the same one


# ---------------------------------------------------------------------------
# 8 — the stored read
# ---------------------------------------------------------------------------
def _stored_doc(as_of: datetime, date="2026-09-21", live=True) -> dict:
    iso, hhmm = H._et_stamp(as_of)
    return {"_id": date, "date": date, "basis": H.D1_PREMARKET, "live": live,
            "ran": True, "stored": False, "ended": False, "show": True,
            "open": True, "session": "premarket", "pre_window": "4:00-9:30 ET",
            "market_closed": None, "benchmark": "RSP",
            "benchmark_pre_move": 0.50, "benchmark_pre_print": 213.35,
            "benchmark_pre_at": "2026-09-21T05:00:00-04:00",
            "benchmark_pre_at_et": "5:00 ET", "symbols": 2, "pre_names": 2,
            "moves": {"TENB": {"pre_1d": 1.5, "pre_raw": 2.0,
                               "pre_print": 102.0, "pre_at": "x",
                               "pre_at_et": "7:27 ET"}},
            "as_of": iso, "as_of_et": hhmm,
            "group_basis": H.PRE_GROUP_BASIS, "reason": None, "note": "n",
            "stored_at": 1.0}


def _counting():
    calls = []

    def _fetch(syms):
        calls.append(list(syms))
        return dict(_PRE_SNAPS)
    return _fetch, calls


def test_a_fresh_stored_read_is_served_without_a_fan_out():
    coll = _Coll({"2026-09-21": _stored_doc(MON - timedelta(minutes=5))})
    fetch, calls = _counting()
    b = H.premarket_block(["TENB"], "RSP", fetch=fetch, now=MON, coll=coll)
    assert calls == [] and b["stored"] is True and b["live"] is True
    assert b["open"] is True and b["session"] == "premarket"


def test_negative_a_stale_stored_read_refetches_and_restores():
    coll = _Coll({"2026-09-21": _stored_doc(MON - timedelta(minutes=16))})
    fetch, calls = _counting()
    b = H.premarket_block(["TENB", "QLYS"], "RSP", fetch=fetch, now=MON,
                          coll=coll)
    assert len(calls) == 1 and b["stored"] is False and b["live"] is True
    assert coll.writes == 1
    assert coll.docs["2026-09-21"]["as_of_et"] == "7:42 ET"


def test_negative_yesterdays_doc_is_never_todays_read():
    coll = _Coll({"2026-09-18": _stored_doc(MON - timedelta(minutes=1),
                                            date="2026-09-18")})
    fetch, calls = _counting()
    H.premarket_block(["TENB"], "RSP", fetch=fetch, now=MON, coll=coll)
    assert len(calls) == 1


def test_negative_a_stored_doc_that_is_not_live_is_never_served():
    coll = _Coll({"2026-09-21": _stored_doc(MON - timedelta(minutes=1),
                                            live=False)})
    fetch, calls = _counting()
    b = H.premarket_block(["TENB"], "RSP", fetch=fetch, now=MON, coll=coll)
    assert len(calls) == 1 and b["stored"] is False


def test_negative_store_premarket_refuses_a_block_with_nothing_in_it():
    coll = _Coll()
    assert H.store_premarket(H._idle_pre(MON), coll) is None
    assert coll.writes == 0
    b = _pre_live()
    assert H.store_premarket(b, coll) == "2026-09-21"
    assert coll.writes == 1


# ---------------------------------------------------------------------------
# 9 — outside the window nothing is spent
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("now,reason", [
    (NIGHT, "the pre-market session is not open (4:00-9:30 ET)"),
    (EVE, "the pre-market session is not open (4:00-9:30 ET)"),
    (SAT, "the market is closed (weekend)"),
])
def test_outside_the_window_costs_zero_provider_calls(now, reason):
    calls = []
    b = H.premarket_moves(["TENB"], "RSP",
                          fetch=lambda s: calls.append(s) or {}, now=now)
    assert calls == [] and b["reason"] == reason
    assert b["open"] is False and b["ran"] is False


# ---------------------------------------------------------------------------
# 10 — after the open
# ---------------------------------------------------------------------------
def test_rth_with_a_stored_read_ends_the_session_and_keeps_the_line():
    doc = _stored_doc(datetime(2026, 9, 21, 7, 20, tzinfo=ET))
    coll = _Coll({"2026-09-21": doc})
    fetch, calls = _counting()
    b = H.premarket_block(["TENB"], "RSP", fetch=fetch, now=RTH, coll=coll)
    assert calls == []
    assert b["ended"] is True and b["show"] is True and b["live"] is False
    assert b["reason"] == ("the pre-market session ended at 9:30 ET — "
                           "last read 7:20 ET")
    board = _build_with(pre=b, live=_live_day())
    assert board[H.PRE_KEY]["show"] is False        # the day column is live
    board = _build_with(pre=b, live=_close_day())
    assert board[H.PRE_KEY]["show"] is True
    assert board[H.PRE_KEY]["live"] is False
    for r in _rows(board).values():
        assert r["pre_1d"] is None


def test_negative_rth_with_no_stored_read_says_none_was_stored():
    fetch, calls = _counting()
    b = H.premarket_block(["TENB"], "RSP", fetch=fetch, now=RTH, coll=_Coll())
    assert calls == []
    assert b["ended"] is True and b["show"] is False
    assert b["reason"] == ("the pre-market session ended at 9:30 ET and no "
                           "read was stored today")


# ---------------------------------------------------------------------------
# 11 — one fan-out, not two
# ---------------------------------------------------------------------------
def test_both_legs_share_exactly_one_fan_out():
    seen = []

    def _raw(syms):
        seen.append(list(syms))
        return dict(_PRE_SNAPS)

    fetch = H._memo_fetch(_raw)
    syms = ["TENB", "QLYS"]
    H.premarket_block(syms, "RSP", fetch=fetch, now=MON, coll=_Coll())
    H.live_day_moves(syms, "RSP", fetch=fetch)
    assert len(seen) == 1
    assert seen[0] == sorted({"TENB", "QLYS", "RSP"})
    assert "RSP" in seen[0]


def test_negative_a_different_symbol_list_is_not_a_memo_hit():
    seen = []
    fetch = H._memo_fetch(lambda s: seen.append(list(s)) or dict(_PRE_SNAPS))
    fetch(["A", "B"])
    fetch(["A", "C"])
    fetch(["A", "C"])
    assert len(seen) == 2


# ---------------------------------------------------------------------------
# 12 — the day column does not move
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("day", [_live_day(), _close_day()])
def test_the_day_column_is_byte_identical_with_and_without_the_pre_leg(day):
    pre = _pre_live()
    a = _build_with(pre=None, live=dict(day))
    b = _build_with(pre=pre, live=dict(day))
    assert a[H.D1_KEY] == b[H.D1_KEY]
    ra, rb = _rows(a), _rows(b)
    for s in ra:
        for k in ("rel_1d", "rel_1d_close", "ret_1d", "ret_1d_close",
                  "d1_source"):
            assert ra[s][k] == rb[s][k]
    for ga, gb in zip(a["sectors"], b["sectors"]):
        for k in ("rel_1d", "rel_1d_close", "d1_source"):
            assert ga[k] == gb[k]
        for ia, ib in zip(ga["industries"], gb["industries"]):
            for k in ("rel_1d", "rel_1d_close", "d1_source"):
                assert ia[k] == ib[k]
    for ta, tb in zip(a["themes"], b["themes"]):
        for k in ("rel_1d", "rel_1d_close", "d1_source"):
            assert ta[k] == tb[k]


# ---------------------------------------------------------------------------
# 13 — ranking on the new column
# ---------------------------------------------------------------------------
def test_the_new_column_is_sortable_and_blanks_rank_last_both_ways():
    assert H.PRE_SORT in H.SORT_KEYS
    syms = ["AAA", "BBB", "CCC"]
    at = datetime(2026, 9, 21, 7, 0, tzinfo=ET)
    snaps = {"RSP": _PRE_SNAPS["RSP"],
             "AAA": _snap(101.0, 100.0, at),      # +0.50 rel
             "BBB": _snap(105.0, 100.0, at),      # +4.50 rel
             "CCC": {"price": 0, "change_pct": 0, "last_trade_price": 0,
                     "last_trade_ts_ms": 0, "prev_day_close": 100.0}}
    pre = _pre_live(symbols=syms, snaps=snaps)
    desc = _build_with(pre=pre, live=_close_day(), sort=H.PRE_SORT,
                       symbols=syms)
    assert desc["sorted_by"] == H.PRE_SORT
    assert [r["symbol"] for r in desc["sectors"][0]["names"]] == ["BBB", "AAA", "CCC"]
    asc = _build_with(pre=pre, live=_close_day(), sort=H.PRE_SORT,
                      direction="asc", symbols=syms)
    order = [r["symbol"] for r in asc["sectors"][0]["names"]]
    assert order == ["AAA", "BBB", "CCC"]
    assert order[-1] == "CCC"           # a blank is LAST in both directions


def test_group_rows_rank_on_the_new_column_too():
    pre = _pre_live()
    board = _build_with(pre=pre, live=_close_day(), sort=H.PRE_SORT)
    sector = board["sectors"][0]
    assert sector[H.PRE_SORT] is not None
    assert board["sorted_by"] == H.PRE_SORT


# ---------------------------------------------------------------------------
# 14 — the window string is pinned to the engine that enforces it
# ---------------------------------------------------------------------------
def test_the_window_string_matches_the_session_engine():
    assert H._pre_window() == "4:00-9:30 ET"


@pytest.mark.parametrize("hh,mm,session", [(3, 59, "closed"), (4, 0, "premarket"),
                                           (9, 29, "premarket"), (9, 30, "rth")])
def test_the_printed_window_is_the_one_trade_session_uses(hh, mm, session):
    assert P.trade_session(datetime(2026, 9, 21, hh, mm, tzinfo=ET)) == session


# ---------------------------------------------------------------------------
# 15 — the pure build
# ---------------------------------------------------------------------------
def test_the_pure_build_says_it_made_no_pre_market_read():
    board = H.build(_payload())
    pre = board[H.PRE_KEY]
    assert pre["ran"] is False and pre["show"] is False
    assert pre["open"] is None and pre["session"] is None
    assert pre["reason"] == "this build made no pre-market read"
    assert "moves" not in pre


# ---------------------------------------------------------------------------
# 16 — the endpoint's coercion
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("premarket", H.D1_PREMARKET), ("close", H.D1_CLOSE),
    ("junk", H.D1_CLOSE), ("", H.D1_CLOSE), (None, H.D1_CLOSE),
    (object(), H.D1_CLOSE),
])
def test_the_endpoint_coerces_basis_and_never_4xxs(monkeypatch, raw, expected):
    import asyncio

    from rotation import api as A

    seen = {}
    monkeypatch.setattr(A, "_members_table",
                        lambda: ({"by_symbol": {}, "benchmark": {}}, {}))
    monkeypatch.setattr(A, "_members_payload", lambda: _payload())

    def _fake(payload, **kw):
        seen.update(kw)
        return {"sectors": []}

    monkeypatch.setattr(A.H, "build_live", _fake)
    resp = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        A.rotation_hottest(sort="rel_5d", dir="desc", names=25, basis=raw))
    assert resp.status_code == 200
    assert seen["basis"] == expected


# ---------------------------------------------------------------------------
# 17-18 — ONE clock, three reads  [C1]
# ---------------------------------------------------------------------------
def test_idle_pre_on_an_open_premarket_clock_invites_the_click():
    b = H._idle_pre(MON)
    assert b["open"] is True and b["session"] == "premarket"
    assert b["market_closed"] is None
    assert b["reason"] == "not requested — click ☀️ Pre-market scan"
    assert b["date"] == "2026-09-21"


def test_one_now_feeds_the_calendar_the_session_and_the_date():
    b = H._idle_pre(SAT)
    assert b["market_closed"] == "weekend"
    assert b["session"] == "closed"
    assert b["open"] is False
    assert b["reason"] == "the market is closed (weekend)"
    assert b["date"] == "2026-09-19"


def test_closed_reason_takes_the_injected_clock_and_still_works_without_one():
    assert H._closed_reason(SAT) == "weekend"
    assert H._closed_reason(MON) is None
    got = H._closed_reason()
    assert got is None or isinstance(got, str)


def test_negative_a_weekend_now_never_reaches_the_fetcher():
    calls = []
    H.premarket_moves(["TENB"], "RSP",
                      fetch=lambda s: calls.append(s) or {}, now=SAT)
    assert calls == []


# ---------------------------------------------------------------------------
# 19 — the yardstick's own print time is served  [C2]
# ---------------------------------------------------------------------------
def test_the_benchmarks_own_print_time_rides_in_the_block_and_the_note():
    b = _pre_live()
    assert b["benchmark_pre_at_et"] == "5:00 ET"
    assert b["benchmark_pre_print"] == 213.35
    assert b["benchmark_pre_at"] == "2026-09-21T05:00:00-04:00"
    assert b["as_of_et"] == "7:42 ET"
    assert b["moves"]["TENB"]["pre_at_et"] == "7:27 ET"
    board = _build_with(pre=b, live=_close_day())
    note = board[H.PRE_KEY]["note"]
    assert "5:00 ET print" in note
    assert "7:42 ET snapshot" in note
    assert "2 of 2 names had printed" in note
    assert "2026-09-18 close" in note
    assert "Not measured, not a signal." in note


def test_negative_no_served_clock_string_is_zero_padded():
    b = _pre_live()
    board = _build_with(pre=b, live=_close_day())
    for v in board[H.PRE_KEY].values():
        if isinstance(v, str):
            assert not re.search(r"\b0\d:\d\d ET", v)
    for r in _rows(board).values():
        assert not re.search(r"\b0\d:\d\d ET", str(r["pre_at_et"]))


# ---------------------------------------------------------------------------
# 20 — a stored doc is re-clocked on every serve  [C3]
# ---------------------------------------------------------------------------
def test_a_stored_doc_never_re_enables_the_button_after_the_open():
    doc = _stored_doc(datetime(2026, 9, 21, 7, 20, tzinfo=ET))
    assert doc["open"] is True and doc["session"] == "premarket"
    coll = _Coll({"2026-09-21": doc})
    b = H.premarket_block(["TENB"], "RSP", fetch=lambda s: {}, now=RTH,
                          coll=coll)
    assert b["open"] is False
    assert b["session"] == "rth"
    assert b["market_closed"] is None
    assert b["ended"] is True and b["show"] is True and b["live"] is False


def test_a_fresh_stored_doc_keeps_the_button_live_inside_the_window():
    coll = _Coll({"2026-09-21": _stored_doc(
        datetime(2026, 9, 21, 7, 45, tzinfo=ET))})
    b = H.premarket_block(["TENB"], "RSP", fetch=lambda s: {},
                          now=datetime(2026, 9, 21, 7, 50, tzinfo=ET),
                          coll=coll)
    assert b["open"] is True and b["session"] == "premarket"
    assert b["stored"] is True


# ---------------------------------------------------------------------------
# 21 — the sort demotion  [C5]
# ---------------------------------------------------------------------------
def _order(board: dict) -> list:
    return [r["symbol"] for r in board["sectors"][0]["names"]]


def test_a_sort_on_an_empty_pre_column_is_demoted_and_says_so():
    snaps = dict(_PRE_SNAPS)
    snaps["RSP"] = {"price": 0, "change_pct": 0, "last_trade_price": 0,
                    "last_trade_ts_ms": 0, "prev_day_close": 212.29}
    dead = _pre_live(snaps=snaps)
    demoted = _build_with(pre=dead, live=_close_day(), sort=H.PRE_SORT)
    baseline = _build_with(pre=dead, live=_close_day(), sort=H.DEFAULT_SORT)
    assert demoted["sorted_by"] == H.DEFAULT_SORT
    assert _order(demoted) == _order(baseline)
    assert [g["group"] for g in demoted["sectors"]] == \
           [g["group"] for g in baseline["sectors"]]


@pytest.mark.parametrize("pre", [None, "idle", "ended"])
def test_every_pre_less_path_demotes_the_pre_sort(pre):
    if pre == "idle":
        block = H._idle_pre(MON)
    elif pre == "ended":
        block = {**H._idle_pre(RTH), "ended": True, "show": True,
                 "reason": "the pre-market session ended at 9:30 ET"}
    else:
        block = None
    board = _build_with(pre=block, live=_close_day(), sort=H.PRE_SORT)
    assert board["sorted_by"] == H.DEFAULT_SORT


def test_a_live_pre_column_keeps_the_sort_it_was_asked_for():
    board = _build_with(pre=_pre_live(), live=_close_day(), sort=H.PRE_SORT)
    assert board["sorted_by"] == H.PRE_SORT


def test_negative_no_other_sort_key_is_ever_demoted():
    board = _build_with(pre=H._idle_pre(MON), live=_close_day(),
                        sort="rel_21d")
    assert board["sorted_by"] == "rel_21d"


# ---------------------------------------------------------------------------
# 22 — the private keys  [C7]
# ---------------------------------------------------------------------------
def test_the_private_keys_never_reach_the_wire_on_any_path():
    doc = _stored_doc(MON - timedelta(minutes=5))
    paths = {
        "fresh": _pre_live(),
        "stored": H.premarket_block(["TENB"], "RSP", fetch=lambda s: {},
                                    now=MON,
                                    coll=_Coll({"2026-09-21": doc})),
        "ended": H.premarket_block(["TENB"], "RSP", fetch=lambda s: {},
                                   now=RTH,
                                   coll=_Coll({"2026-09-21": doc})),
        "idle": H._idle_pre(MON),
        "pure": None,
    }
    for name, block in paths.items():
        served = _build_with(pre=block, live=_close_day())[H.PRE_KEY]
        assert set(served) & set(H.PRE_PRIVATE_KEYS) == set(), name


def test_the_mongo_doc_itself_does_carry_id_and_stored_at():
    coll = _Coll()
    H.store_premarket(_pre_live(), coll)
    doc = coll.docs["2026-09-21"]
    assert doc["_id"] == "2026-09-21"
    assert isinstance(doc["stored_at"], float)
    assert doc["moves"]                      # stored, just never served


# ---------------------------------------------------------------------------
# 23 — ONE clock format  [C10]
# ---------------------------------------------------------------------------
def test_one_clock_renderer_for_every_served_string():
    assert H._hhmm(dtime(9, 30)) == "9:30 ET"
    assert H._hhmm(dtime(16, 0)) == "16:00 ET"
    assert H._hhmm(dtime(4, 0)) == "4:00 ET"
    assert H._et_stamp(datetime(2026, 9, 21, 7, 42, tzinfo=ET))[1] == "7:42 ET"
    assert H._pre_window() == "4:00-9:30 ET"
    assert H._rth_open_hhmm() == "9:30 ET"


def test_negative_the_ended_reason_uses_the_same_format():
    coll = _Coll({"2026-09-21": _stored_doc(
        datetime(2026, 9, 21, 7, 20, tzinfo=ET))})
    b = H.premarket_block(["TENB"], "RSP", fetch=lambda s: {}, now=RTH,
                          coll=coll)
    assert b["reason"] == ("the pre-market session ended at 9:30 ET — "
                           "last read 7:20 ET")
    assert not re.search(r"\b0\d:\d\d ET", b["reason"])
