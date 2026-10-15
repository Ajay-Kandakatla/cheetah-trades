"""US bonds, US dollar and gold beside SPY · QQQ on the 🧭 strip (2026-10-15).

Ajay 2026-10-15: *"how can.I check us bonds and us dollar and gold can you add
them to the SPY and QQQ please? I wanna see their progress"*.

TLT / UUP / GLD (`index_zones.MACRO`, ETF proxies — MINE) are warmed by the
SAME 04:15 job through the existing `computed` fallback, off ONE fresh frame
that never touches the shared price cache, and every served entry gains a
serve-time `progress` overlay (5d / 21d off the stored closed bars, today off
the strip's own print vs the official prior close, gated on the stored close
being the prior session's).

HERMETIC: hand-built frames and rows, a fake collection, every provider and
cache reader monkeypatched. Every group carries at least one NEGATIVE.
"""
from __future__ import annotations

import copy
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# C2 (AMENDMENTS3): pre-import the REAL modules the progress read reaches for
# lazily, BEFORE any fixture in the suite stubs sys.modules — the same hazard
# tests/test_chart_maps.py:28-46 documents.
import chart_maps.high_beta_tab  # noqa: E402,F401
import chart_maps.resiliency_tab  # noqa: E402,F401
import chart_maps.drop10_tab  # noqa: E402,F401
import supply_demand.key_levels  # noqa: E402,F401
import rotation.tracker  # noqa: E402,F401
import market_hours.reminder  # noqa: E402,F401
import supply_demand.demand_reentry  # noqa: E402,F401

from chart_maps import high_beta_tab as HB  # noqa: E402
from chart_maps import resiliency_tab as RES  # noqa: E402
from rotation import tracker as RT  # noqa: E402
from sepa import prices as P  # noqa: E402
from supply_demand import demand_reentry as D  # noqa: E402
from supply_demand import index_zones as IZ  # noqa: E402
from supply_demand import zone_store as ZS  # noqa: E402
from tests.test_index_zones_2026_09_16 import (  # noqa: E402
    _BANNED, SPY_BANDS, QQQ_BANDS, BrokenColl, FakeColl, _doc, _frame, qqq_doc, spy_doc)

UTC = timezone.utc
THU = date(2026, 10, 15)          # a Thursday session
WED = date(2026, 10, 14)


def _ns(y, m, d, hh, mm=0):
    """A Massive lastTrade.t stamp (nanoseconds) for a UTC wall-clock."""
    return int(datetime(y, m, d, hh, mm, tzinfo=UTC).timestamp()) * 10 ** 9


def _ms(y, m, d, hh, mm=0):
    return int(datetime(y, m, d, hh, mm, tzinfo=UTC).timestamp()) * 1000


def _row(px=80.40, prev=78.89, ts=None):
    """One bulk_live_prices row (prices.py:1499 shape) — no `close`, no min_t_ms."""
    return {"price": px, "change_pct": None, "volume": 1_000_000.0,
            "last_trade_price": px,
            "last_trade_ts_ms": _ns(2026, 10, 15, 13, 30) if ts is None else ts,
            "prev_day_close": prev, "low": px * 0.99, "open": prev, "high": px * 1.01}


def _read(as_of="2026-10-14", close=78.89, live_px=80.40, available=True):
    return {"symbol": "TLT", "available": available, "as_of": as_of,
            "close": close, "live_px": live_px, "bars": []}


def _bars(closes, end="2026-10-14"):
    idx = pd.bdate_range(end=end, periods=len(closes))
    return [{"t": d.date().isoformat(), "o": c, "h": c, "l": c, "c": c, "v": 1000.0}
            for d, c in zip(idx, closes)]


def _frames(end="2026-09-16"):
    return {"SPY": _frame(end=end), "QQQ": _frame(end=end, base=140.0),
            "TLT": _frame(end=end, base=90.0), "UUP": _frame(end=end, base=28.0),
            "GLD": _frame(end=end, base=380.0)}


# ---------------------------------------------------------------------------
# T1 constants
# ---------------------------------------------------------------------------
def test_T1_the_strip_is_spy_qqq_then_the_three_macro_proxies():
    assert IZ.INDEXES == ("SPY", "QQQ"), "the two cards — a deliberate pin"
    assert IZ.STRIP_SYMBOLS == IZ.INDEXES + IZ.MACRO_SYMBOLS
    assert IZ.MACRO_SYMBOLS == ("TLT", "UUP", "GLD")
    assert all(s == s.upper() and s for s in IZ.STRIP_SYMBOLS)
    assert len(set(IZ.STRIP_SYMBOLS)) == len(IZ.STRIP_SYMBOLS)
    assert all(IZ.MACRO_LABELS[s] for s in IZ.MACRO_SYMBOLS)
    assert IZ.MACRO_LABELS == {"TLT": "US bonds (20y+)", "UUP": "US dollar", "GLD": "Gold"}
    assert set(IZ.TODAY_NOTES) == set(IZ.TODAY_STATES)


def test_T1_NEGATIVE_no_macro_symbol_is_an_index_card():
    """A macro symbol in INDEXES would be warmed twice and drawn as a card."""
    assert not set(IZ.MACRO_SYMBOLS) & set(IZ.INDEXES)
    assert IZ.PROGRESS_KEY not in IZ.INDEX_KEYS + IZ.LIVE_KEYS + IZ.PAYLOAD_KEYS


def test_T1_the_macro_tuple_keeps_the_raw_pin_format():
    """The FE ?raw pin parses this exact multi-line shape (BUILD_SPEC3 §3.1)."""
    import re
    src = (Path(IZ.__file__)).read_text()
    m = re.search(r"^MACRO = \(\n([\s\S]*?)\n\)\n", src, re.M)
    assert m, "MACRO = ( … ) must stay multi-line at column 0"
    pairs = re.findall(r'\("([A-Z]+)", "([^"]+)"\)', m.group(1))
    assert tuple(pairs) == IZ.MACRO


# ---------------------------------------------------------------------------
# T2 warm default
# ---------------------------------------------------------------------------
def test_T2_warm_defaults_to_all_five_and_computes_the_macro_three(monkeypatch):
    frames = _frames()
    real = ZS.build_doc
    seen = []

    def spy(sym, df, today, **kw):
        seen.append((sym, kw.get("compute")))
        return real(sym, df, today, **kw)

    monkeypatch.setattr(ZS, "build_doc", spy)
    coll = FakeColl()
    res = IZ.warm(coll=coll, store_docs={"SPY": spy_doc(), "QQQ": qqq_doc()},
                  loader=lambda s: frames[s], today=date(2026, 9, 17), namer=lambda s: s)
    idx = coll.docs["2026-09-17"]["indexes"]
    assert list(idx) == list(IZ.STRIP_SYMBOLS) and res["symbols"] == list(IZ.STRIP_SYMBOLS)
    assert res["sources"] == {"zone_store": 2, "computed": 3, "unavailable": 0}
    assert idx["SPY"]["source"] == idx["QQQ"]["source"] == "zone_store"
    for sym in IZ.MACRO_SYMBOLS:
        e = idx[sym]
        assert e["source"] == "computed" and e["available"] is True
        assert set(e) == set(IZ.INDEX_KEYS)
        for r in e["resolutions"].values():
            assert r["available"] is True and r["bands"]
        assert e["bars"] and e["bars_basis"] == IZ.BARS_BASIS
        # board geometry = build_doc(compute=None) = zone_geom(); fine = _fine_compute
        assert (sym, None) in seen and (sym, IZ._fine_compute) in seen


def test_T2_NEGATIVE_one_unreadable_macro_symbol_is_stored_unavailable_alone():
    frames = _frames()
    coll = FakeColl()
    res = IZ.warm(coll=coll, store_docs={"SPY": spy_doc(), "QQQ": qqq_doc()},
                  loader=lambda s: None if s == "GLD" else frames[s],
                  today=date(2026, 9, 17), namer=lambda s: s)
    idx = coll.docs["2026-09-17"]["indexes"]
    assert set(idx) == set(IZ.STRIP_SYMBOLS), "present, never dropped"
    assert idx["GLD"]["available"] is False and idx["GLD"]["reason"]
    assert idx["GLD"]["source"] == "unavailable" and idx["GLD"]["close"] is None
    for sym in ("SPY", "QQQ", "TLT", "UUP"):
        assert idx[sym]["available"] is True, sym
    assert res["sources"]["unavailable"] == 1


# ---------------------------------------------------------------------------
# T3 closed_moves
# ---------------------------------------------------------------------------
def test_T3_closed_moves_are_the_trackers_trailing_return_raw():
    bars = _bars([100.0 + i * 0.37 + (i % 3) * 0.11 for i in range(30)])
    mv = IZ.closed_moves(bars)
    assert mv["ret_5d"] == RT.trailing_return(bars, RT.WINDOW_FAST)
    assert mv["ret_21d"] == RT.trailing_return(bars, RT.WINDOW_SHORT)
    assert mv["ret_5d"] is not None and mv["ret_21d"] is not None
    assert mv["through"] == bars[-1]["t"] == "2026-10-14"
    p = IZ.progress_read({"available": True, "as_of": "2026-10-14", "close": 1.0,
                          "live_px": None, "bars": bars}, None, session=THU)
    assert p["ret_5d"] == round(RT.trailing_return(bars, 5), 2)
    assert p["ret_21d"] == round(RT.trailing_return(bars, 21), 2)
    assert p["through"] == "2026-10-14"


def test_T3_NEGATIVE_short_empty_and_zero_based_bars_never_read_as_zero():
    ten = _bars([100.0 + i for i in range(10)])
    mv = IZ.closed_moves(ten)
    assert mv["ret_21d"] is None and mv["ret_5d"] is not None
    assert IZ.closed_moves([]) == {"through": None, "ret_5d": None, "ret_21d": None}
    assert IZ.closed_moves(None) == {"through": None, "ret_5d": None, "ret_21d": None}
    zero = _bars([100.0] * 24 + [0.0] + [101.0] * 5)   # c[-6] = 0 -> the 5d base
    z = IZ.closed_moves(zero)
    assert z["ret_5d"] is None, "a 0 base is no read, never 0.0"


# ---------------------------------------------------------------------------
# T4 day_move
# ---------------------------------------------------------------------------
def test_T4_today_is_the_print_against_the_official_prior_close():
    dm = IZ.day_move(_read(), _row(), session=THU)
    assert dm == {"today_pct": (80.40 - 78.89) / 78.89 * 100.0,
                  "today_prev_close": 78.89, "today_state": "read"}
    p = IZ.progress_read(_read(), _row(), session=THU)
    assert p["today_pct"] == 1.91 and p["today_prev_close"] == 78.89
    assert p["today_state"] == "read"


def test_T4_the_snapshots_official_close_replaces_a_cached_one_within_tolerance():
    dm = IZ.day_move(_read(close=78.80), _row(prev=78.89), session=THU)
    assert dm["today_prev_close"] == 78.89 and dm["today_state"] == "read"


def test_T4_NEGATIVE_a_disagreeing_snapshot_close_is_never_the_base():
    dm = IZ.day_move(_read(), _row(prev=85.0), session=THU)
    assert dm["today_prev_close"] == 78.89, "beyond PREV_CLOSE_TOL_PCT -> the stored close"
    assert dm["today_state"] == "read"


@pytest.mark.parametrize("read,row,session,state", [
    (_read(as_of="2026-10-13"), _row(), THU, "basis_behind"),
    (_read(as_of="2026-10-16"), _row(), date(2026, 10, 17), "no_session"),      # Sat
    (_read(as_of="2026-11-25"), _row(), date(2026, 11, 26), "no_session"),      # Thanksgiving
    (_read(), _row(ts=_ns(2026, 10, 14, 19, 0)), THU, "no_print"),             # 10-14 trade
    (_read(), None, THU, "no_print"),
    (_read(live_px=None), _row(), THU, "no_print"),
    (_read(available=False), _row(), THU, "unavailable"),
    (_read(live_px=80.40), _row(px=81.00), THU, "no_print"),                  # not the shown print
    (_read(), _row(px=0.0), THU, "no_print"),
])
def test_T4_NEGATIVE_every_unread_state_serves_none_never_zero(read, row, session, state):
    dm = IZ.day_move(read, row, session=session)
    assert dm["today_state"] == state
    assert dm["today_pct"] is None and dm["today_prev_close"] is None
    p = IZ.progress_read(read, row, session=session)
    assert p["today_state"] == state and p["today_pct"] is None
    assert p["text"]["today"] == "—"


def test_T4_the_same_print_rounded_is_still_the_print_the_row_shows():
    dm = IZ.day_move(_read(live_px=80.40), _row(px=80.4049), session=THU)
    assert dm["today_state"] == "read"
    assert dm["today_pct"] == (80.4049 - 78.89) / 78.89 * 100.0, "the UNROUNDED print"


# ---------------------------------------------------------------------------
# T5 _snapshot_view
# ---------------------------------------------------------------------------
def _item(*, c, prev, day_t, trade_t, min_t, o=None):
    o = c if o is None else o
    return {"ticker": "TLT",
            "day": {"o": o, "h": c * 1.01 if c else 0, "l": c * 0.99 if c else 0,
                    "c": c, "v": 1_000_000 if c else 0, "vw": c, "t": day_t},
            "lastTrade": {"p": c or prev * 1.002, "t": trade_t},
            "prevDay": {"c": prev}, "min": {"av": 1000, "t": min_t},
            "todaysChangePerc": 0.0, "todaysChange": 0.0}


_T5_CASES = [
    # dated the session, agrees with the ref
    _item(c=80.40, prev=78.89, day_t=_ms(2026, 10, 15, 4), trade_t=_ns(2026, 10, 15, 14),
          min_t=_ms(2026, 10, 15, 14)),
    # dated the session, disagrees
    _item(c=80.40, prev=85.0, day_t=_ms(2026, 10, 15, 4), trade_t=_ns(2026, 10, 15, 14),
          min_t=_ms(2026, 10, 15, 14)),
    # the previous day's snapshot
    _item(c=78.89, prev=78.10, day_t=_ms(2026, 10, 14, 4), trade_t=_ns(2026, 10, 14, 19),
          min_t=_ms(2026, 10, 14, 19)),
    # pre-open: the day bar is all zeros, a pre-market trade dated the session
    _item(c=0, prev=78.89, o=0, day_t=_ms(2026, 10, 15, 4), trade_t=_ns(2026, 10, 15, 12),
          min_t=_ms(2026, 10, 15, 12)),
]


@pytest.mark.parametrize("item", _T5_CASES)
def test_T5_the_row_view_reads_the_official_close_exactly_like_the_raw_snapshot(item):
    raw = P._snapshot_row(item)
    row = P.bulk_live_prices(["TLT"], snaps={"TLT": raw})["TLT"]
    assert "close" not in row and "min_t_ms" not in row
    for ref in (78.80, 78.89):
        assert (RES.official_prev_close(IZ._snapshot_view(row), ref, THU)
                == RES.official_prev_close(raw, ref, THU))


def test_T5_NEGATIVE_no_row_is_no_view_and_a_present_close_is_kept():
    assert IZ._snapshot_view(None) is None
    assert IZ._snapshot_view("nope") is None
    row = {"price": 80.40, "close": 80.10}
    view = IZ._snapshot_view(row)
    assert view["close"] == 80.10, "an existing close is never overwritten"
    assert IZ._snapshot_view({"price": 1.0})["close"] == 1.0
    assert row == {"price": 80.40, "close": 80.10}, "the row is never mutated"


# ---------------------------------------------------------------------------
# T6 with_progress
# ---------------------------------------------------------------------------
def _warmed(today=date(2026, 9, 16), symbols=IZ.STRIP_SYMBOLS):
    frames = _frames()
    coll = FakeColl()
    IZ.warm(symbols=symbols, coll=coll, store_docs={}, loader=lambda s: frames[s],
            today=today, namer=lambda s: s)
    return coll


def test_T6_with_progress_adds_its_own_key_and_nothing_else():
    entry = _warmed().docs["2026-09-16"]["indexes"]["TLT"]
    lit = IZ.with_live(entry, 95.0)
    out = IZ.with_progress(lit, None, session=date(2026, 9, 16))
    assert set(out) - set(lit) == {IZ.PROGRESS_KEY}
    assert set(out[IZ.PROGRESS_KEY]) == set(IZ.PROGRESS_KEYS)
    for k in IZ.INDEX_KEYS + IZ.LIVE_KEYS:
        assert out[k] == lit[k], k
    assert out["resolutions"] == lit["resolutions"]
    assert out[IZ.PROGRESS_KEY]["today_state"] != "unavailable", "the real-module path"


def test_T6_NEGATIVE_never_mutates_and_never_raises(monkeypatch):
    entry = _warmed().docs["2026-09-16"]["indexes"]["TLT"]
    before = copy.deepcopy(entry)
    IZ.with_progress(entry, _row(), session=date(2026, 9, 16))
    assert entry == before and IZ.PROGRESS_KEY not in entry

    def boom(*a, **kw):
        raise RuntimeError("progress exploded")

    monkeypatch.setattr(IZ, "progress_read", boom)
    out = IZ.with_progress(entry, _row(), session=date(2026, 9, 16))
    assert out[IZ.PROGRESS_KEY] == IZ._progress_unread()
    p = out[IZ.PROGRESS_KEY]
    assert set(p) == set(IZ.PROGRESS_KEYS) and p["today_state"] == "unavailable"
    assert all(p[k] is None for k in ("ret_5d", "ret_21d", "today_pct", "today_prev_close"))
    assert set(p["text"].values()) == {"—"}
    assert p["note"] == "Progress is unavailable right now."
    assert {k: out[k] for k in entry} == entry


# ---------------------------------------------------------------------------
# T7 text — 1 dp of the RAW move, never of the 2 dp number
# ---------------------------------------------------------------------------
def test_T7_text_is_leg_text_of_the_raw_moves_and_windows_come_from_rt():
    bars = _bars([100.0 + i * 0.41 for i in range(30)])
    p = IZ.progress_read({"available": True, "as_of": "2026-10-14", "close": 78.89,
                          "live_px": 80.40, "bars": bars}, _row(), session=THU)
    assert p["text"]["ret_5d"] == HB.leg_text(RT.trailing_return(bars, RT.WINDOW_FAST))
    assert p["text"]["ret_21d"] == HB.leg_text(RT.trailing_return(bars, RT.WINDOW_SHORT))
    assert p["text"]["today"] == HB.leg_text((80.40 - 78.89) / 78.89 * 100.0)
    assert p["windows"] == {"ret_5d": RT.WINDOW_FAST, "ret_21d": RT.WINDOW_SHORT}
    assert IZ._move_text(1.25) == "+1.3%"
    assert IZ._move_text(-0.25) == "−0.3%"


@pytest.mark.parametrize("last,served,text", [(101.2496, 1.25, "+1.2%"),
                                              (101.1503, 1.15, "+1.2%")])
def test_T7_NEGATIVE_the_text_is_never_rounded_twice(last, served, text):
    closes = [100.0] * 25 + [100.0, 100.3, 100.6, 100.9, last]   # c[-6] = 100.0
    bars = _bars(closes)
    p = IZ.progress_read({"available": True, "as_of": "2026-10-14", "close": 100.0,
                          "live_px": None, "bars": bars}, None, session=THU)
    assert p["ret_5d"] == served
    assert p["text"]["ret_5d"] == text
    assert HB.leg_text(served) != text, "what a double round would have printed"


def test_T7_NEGATIVE_the_today_text_is_never_rounded_twice():
    read = {"available": True, "as_of": "2026-10-14", "close": 100.0,
            "live_px": 101.25, "bars": []}
    p = IZ.progress_read(read, _row(px=101.2496, prev=100.0), session=THU)
    assert p["today_state"] == "read"
    assert p["today_pct"] == 1.25 and p["text"]["today"] == "+1.2%"
    assert HB.leg_text(1.25) == "+1.3%", "what a double round would have printed"
    unread = IZ.progress_read(dict(read, as_of="2026-10-13"), _row(px=101.2496, prev=100.0),
                              session=THU)
    assert unread["text"] == {"today": "—", "ret_5d": "—", "ret_21d": "—"}


# ---------------------------------------------------------------------------
# T8 served
# ---------------------------------------------------------------------------
def _session_row(close, mult=1.01):
    px = round(close * mult, 2)
    return {"price": px, "change_pct": None, "volume": 5.0e5, "last_trade_price": px,
            "last_trade_ts_ms": _ns(2026, 9, 16, 15, 0), "prev_day_close": close,
            "low": px * 0.99, "open": close, "high": px * 1.01}


def test_T8_served_with_rows_puts_progress_on_every_entry_off_the_same_rows(monkeypatch):
    coll = _warmed()
    stored = coll.docs["2026-09-16"]["indexes"]
    rows = {s: _session_row(stored[s]["close"]) for s in IZ.STRIP_SYMBOLS}

    def no_fetch(*a, **kw):
        raise AssertionError("served fetched although rows were handed")

    monkeypatch.setattr(IZ, "live_rows", no_fetch)
    out = IZ.served(rows=rows, coll=coll, today=date(2026, 9, 16))
    assert set(out["indexes"]) == set(IZ.STRIP_SYMBOLS)
    for s, e in out["indexes"].items():
        assert set(e[IZ.PROGRESS_KEY]) == set(IZ.PROGRESS_KEYS)
        assert e["live_px"] == round(D._snapshot_print(rows[s]), 2)
        p = e[IZ.PROGRESS_KEY]
        assert p["today_state"] == "read", (s, p)
        assert p["today_prev_close"] == stored[s]["close"]
        assert p["through"] == e["as_of"] == "2026-09-15"


def test_T8_NEGATIVE_handed_live_and_rows_means_no_fetch(monkeypatch):
    coll = _warmed()

    def boom(*a, **kw):
        raise AssertionError("served fetched although live + rows were handed")

    monkeypatch.setattr(IZ, "live_rows", boom)
    out = IZ.served(live={"TLT": 95.0}, rows={}, coll=coll, today=date(2026, 9, 16))
    assert out["indexes"]["TLT"]["live_px"] == 95.0


def test_T8_a_bare_served_fetches_once_with_the_docs_symbols(monkeypatch):
    coll = _warmed()
    calls = []

    def rec(symbols):
        calls.append(list(symbols))
        return {}

    monkeypatch.setattr(IZ, "live_rows", rec)
    IZ.served(coll=coll, today=date(2026, 9, 16))
    assert calls == [list(IZ.STRIP_SYMBOLS)]


def test_T8_NEGATIVE_prints_without_rows_never_fake_a_today_read(monkeypatch):
    coll = _warmed()
    monkeypatch.setattr(IZ, "live_rows", lambda *a, **kw: pytest.fail("fetched"))
    out = IZ.served(live={s: 95.0 for s in IZ.STRIP_SYMBOLS}, coll=coll,
                    today=date(2026, 9, 16))
    for e in out["indexes"].values():
        assert e[IZ.PROGRESS_KEY]["today_state"] == "no_print"
        assert e[IZ.PROGRESS_KEY]["today_pct"] is None


def test_T8_NEGATIVE_a_cold_store_fetches_nothing(monkeypatch):
    monkeypatch.setattr(IZ, "live_rows", lambda *a, **kw: pytest.fail("fetched"))
    out = IZ.served(coll=FakeColl(), today=date(2026, 9, 16))
    assert out["indexes"] == {}
    assert IZ.served(coll=BrokenColl(), today=date(2026, 9, 16))["indexes"] == {}


# ---------------------------------------------------------------------------
# C1 — the header's date and age are measured on SPY / QQQ
# ---------------------------------------------------------------------------
def _mixed_coll(index_as_of, macro_as_of):
    idx = {"SPY": IZ.read_doc("SPY", _doc("SPY", 757.39, 5.86, 779.37, SPY_BANDS,
                                          as_of=index_as_of, stored="2026-10-15")),
           "QQQ": IZ.read_doc("QQQ", _doc("QQQ", 704.54, 7.76, 748.65, QQQ_BANDS,
                                          as_of=index_as_of, stored="2026-10-15"))}
    for s in IZ.MACRO_SYMBOLS:
        a = macro_as_of[s] if isinstance(macro_as_of, dict) else macro_as_of
        idx[s] = IZ.read_doc(s, _doc(s, 100.0, 2.0, 130.0,
                                     [("supply", 110.0, 115.0, 3, 50.0)],
                                     as_of=a, stored="2026-10-15"))
    return FakeColl({"2026-10-15": {"_id": "2026-10-15", "date": "2026-10-15",
                                    "indexes": idx}})


class _Clock(datetime):
    """IZ's wall clock, frozen (served passes today=None in production)."""
    at = None

    @classmethod
    def now(cls, tz=None):
        return cls.at if tz is None else cls.at.astimezone(tz)


def _freeze(monkeypatch, hh, mm=0):
    _Clock.at = datetime(2026, 10, 15, hh, mm, tzinfo=IZ.ET)
    monkeypatch.setattr(IZ, "datetime", _Clock)


def test_C1_NEGATIVE_fresher_macro_rows_never_hide_a_stale_spy_qqq_header(monkeypatch):
    """SPY/QQQ as_of 10-13, the three macro rows 10-14. The newest-of-all rule
    dated the header 10-14 and read it FRESH on 10-15 before the close; the
    header dates the index cards, so it is 10-13 and a session old."""
    coll = _mixed_coll("2026-10-13", "2026-10-14")
    monkeypatch.setattr(IZ, "live_rows", lambda *a, **kw: {})
    _freeze(monkeypatch, 12, 0)
    out = IZ.served(coll=coll)
    assert out["as_of"] == "2026-10-13"
    assert out["stale_sessions"] == 1, "the newest-of-all basis would have read 0"
    assert "1 session old" in out["note"]
    # after the 10-15 close, 10-14 AND 10-15 have elapsed since the 10-13 basis
    _freeze(monkeypatch, 16, 30)
    late = IZ.served(coll=coll)
    assert late["as_of"] == "2026-10-13" and late["stale_sessions"] == 2
    # the macro rows keep their own dates
    assert late["indexes"]["TLT"]["as_of"] == "2026-10-14"


def test_C1_NEGATIVE_one_stale_macro_row_never_ages_a_fresh_header(monkeypatch):
    coll = _mixed_coll("2026-10-14", {"TLT": "2026-10-14", "UUP": "2026-09-01",
                                      "GLD": "2026-10-14"})
    monkeypatch.setattr(IZ, "live_rows", lambda *a, **kw: {})
    _freeze(monkeypatch, 12, 0)
    out = IZ.served(coll=coll)
    assert out["as_of"] == "2026-10-14" and out["stale_sessions"] == 0
    assert "session old" not in out["note"]
    uup = out["indexes"]["UUP"]
    assert uup["as_of"] == "2026-09-01"
    assert uup[IZ.PROGRESS_KEY]["today_state"] == "basis_behind"


def test_C1_with_no_readable_index_the_macro_rows_date_the_header():
    coll = _mixed_coll("2026-10-14", "2026-10-13")
    doc = coll.docs["2026-10-15"]
    for s in IZ.INDEXES:
        doc["indexes"][s] = IZ.read_doc(s, None)
    out = IZ.served(live={}, rows={}, coll=coll, today=THU)
    assert out["as_of"] == "2026-10-13"


# ---------------------------------------------------------------------------
# T9 wording
# ---------------------------------------------------------------------------
def test_T9_the_disclaimer_names_every_instrument_and_says_context_only():
    for s in IZ.INDEXES + IZ.MACRO_SYMBOLS:
        assert s in IZ.DISCLAIMER
    for label in IZ.MACRO_LABELS.values():
        assert label in IZ.DISCLAIMER
    assert "gates nothing" in IZ.DISCLAIMER and "not advice" in IZ.DISCLAIMER


def test_T9_and_joins_any_iterable_including_a_generator():
    assert IZ._and(x for x in ("A", "B", "C")) == "A, B and C"
    assert IZ._and(["A"]) == "A"
    assert IZ._and(("A", "B")) == "A and B"


def test_T9_NEGATIVE_and_of_nothing_is_empty_and_the_built_disclaimer_is_exact():
    assert IZ._and([]) == ""
    assert IZ._and(iter(())) == ""
    assert IZ.DISCLAIMER == (
        "Structure drawn on closed bars — context for where SPY and QQQ are standing, and "
        "for US bonds (20y+), US dollar and Gold through the ETF proxies TLT, UUP and GLD. "
        "It gates nothing, is not a signal and is not advice.")


def _every_note():
    bars = _bars([100.0 + i for i in range(30)])
    base = {"available": True, "as_of": "2026-10-14", "close": 78.89, "live_px": 80.40,
            "bars": bars}
    cases = [(base, _row(), THU),
             (dict(base, as_of="2026-10-16"), _row(), date(2026, 10, 17)),
             (dict(base, as_of="2026-10-13"), _row(), THU),
             (base, None, THU),
             (dict(base, available=False, bars=[]), None, THU)]
    notes = [IZ.progress_read(r, row, session=s)["note"] for r, row, s in cases]
    states = {IZ.progress_read(r, row, session=s)["today_state"] for r, row, s in cases}
    assert states == set(IZ.TODAY_STATES), "every state rendered"
    return notes + [IZ._progress_unread()["note"]]


def test_T9_NEGATIVE_no_progress_sentence_says_a_banned_word():
    notes = _every_note()
    assert any("are not read: the stored doc carries no closed bars" in n for n in notes)
    assert any("closed sessions through the 2026-10-14 close" in n for n in notes)
    assert any("Today: the live print 80.40 against the 2026-10-14 close 78.89." in n
               for n in notes)
    for n in notes:
        low = n.lower()
        for word in _BANNED:
            assert word not in low, f"{word!r} in: {n}"


def test_T9_NEGATIVE_bounce_appears_in_no_served_string():
    strings = [v for k, v in vars(IZ).items()
               if isinstance(v, str) and not k.startswith("__")]
    strings += list(IZ.TODAY_NOTES.values()) + _every_note()
    strings.append(IZ.empty_payload()["note"])
    for s in strings:
        assert "bounce" not in s.lower(), s


# ---------------------------------------------------------------------------
# T10 the board attach
# ---------------------------------------------------------------------------
def test_T10_the_board_fetches_the_strips_symbols_and_hands_only_their_rows(monkeypatch):
    from chart_maps import board as B
    assert B._index_symbols() == list(IZ.STRIP_SYMBOLS)
    got = {}
    monkeypatch.setattr(IZ, "served", lambda **kw: got.update(kw) or IZ.empty_payload("n"))
    B._index_strip({"SPY": 1.0}, {"SPY": {"price": 1.0}, "NVDA": {"price": 2.0}})
    assert set(got["live"]) == set(IZ.STRIP_SYMBOLS)
    assert got["live"]["SPY"] == 1.0 and got["live"]["TLT"] is None
    assert got["rows"] == {"SPY": {"price": 1.0}}


def test_T10_NEGATIVE_a_tiles_row_never_reaches_the_strip_and_warming_fetches_itself(
        monkeypatch):
    from chart_maps import board as B
    got = {}
    monkeypatch.setattr(IZ, "served", lambda **kw: got.update(kw) or IZ.empty_payload("n"))
    B._index_strip({}, {"NVDA": {"price": 2.0}, "AMD": {"price": 3.0}})
    assert got["rows"] == {}, "no tile row is handed to the strip"
    got.clear()
    B._index_strip()
    assert got["live"] is None and got["rows"] is None, "warming: served fetches once itself"


# ---------------------------------------------------------------------------
# T11 the default loader's scope (Revision 1, finding 1)
# ---------------------------------------------------------------------------
def _recorders(monkeypatch):
    calls = {"load_prices": [], "closed_daily_frame": []}

    def lp(sym, *a, **kw):
        calls["load_prices"].append((sym, a, kw))
        return _frame()

    def cdf(sym, *a, **kw):
        calls["closed_daily_frame"].append((sym, a, kw))
        return _frame()

    monkeypatch.setattr(P, "load_prices", lp)
    monkeypatch.setattr(P, "closed_daily_frame", cdf)
    return calls


NOW_0415 = datetime(2026, 10, 16, 4, 15, tzinfo=IZ.ET)


def test_T11_spy_qqq_read_load_prices_and_the_macro_three_read_fresh(monkeypatch):
    calls = _recorders(monkeypatch)
    IZ.warm(coll=FakeColl(), store_docs={"SPY": spy_doc(), "QQQ": qqq_doc()},
            today=date(2026, 10, 16), now=NOW_0415, namer=lambda s: s)
    assert [c[0] for c in calls["load_prices"]] == ["SPY", "QQQ"]
    assert all(c[2] == {"period": "2y"} and not c[1] for c in calls["load_prices"])
    assert [c[0] for c in calls["closed_daily_frame"]] == list(IZ.MACRO_SYMBOLS)
    for _sym, a, kw in calls["closed_daily_frame"]:
        assert not a and kw == {"now": NOW_0415, "period": "2y", "use_cache": False}


def test_T11_NEGATIVE_no_zone_store_doc_means_no_cache_read_for_any_symbol(monkeypatch):
    calls = _recorders(monkeypatch)
    IZ.warm(coll=FakeColl(), store_docs={}, today=date(2026, 10, 16), now=NOW_0415,
            namer=lambda s: s)
    assert calls["load_prices"] == [], "load_prices reads the shared cache"
    assert [c[0] for c in calls["closed_daily_frame"]] == list(IZ.STRIP_SYMBOLS)
    assert all(c[2]["use_cache"] is False for c in calls["closed_daily_frame"])


# ---------------------------------------------------------------------------
# T12 the intraday-bar NEGATIVE, through the REAL closed_daily_frame
# ---------------------------------------------------------------------------
def _tlt_partial_and_final():
    hist = _frame(n=300, end="2026-10-15", base=80.0)
    last = pd.Timestamp("2026-10-15")
    partial = hist.copy()
    partial.loc[last, ["open", "high", "low", "close", "volume"]] = [80.0, 80.6, 79.0, 80.40, 400_000.0]
    final = hist.copy()
    final.loc[last, ["open", "high", "low", "close", "volume"]] = [80.0, 80.6, 78.9, 79.10, 1_500_000.0]
    pre = pd.DataFrame([{"open": 79.2, "high": 79.5, "low": 79.0, "close": 79.3,
                         "volume": 10_000.0}], index=[pd.Timestamp("2026-10-16")])
    return partial, pd.concat([final, pre])


def _t12(monkeypatch, fetch):
    partial, final = _tlt_partial_and_final()
    reads = []

    def cached(sym):
        reads.append(sym)
        return partial.copy()

    def no_write(*a, **kw):
        raise AssertionError("the macro read wrote the shared price cache")

    monkeypatch.setattr(P, "_mongo_get", cached)
    monkeypatch.setattr(P, "_parquet_get", cached)
    monkeypatch.setattr(P, "_mongo_put", no_write)
    monkeypatch.setattr(P, "_parquet_put", no_write)
    monkeypatch.setattr(P, "_fetch", lambda sym, period: (final.copy() if fetch else None))
    monkeypatch.setattr(P, "load_prices", lambda sym, **kw: _frame(end="2026-10-15"))
    coll = FakeColl()
    res = IZ.warm(coll=coll, store_docs={"SPY": spy_doc(), "QQQ": qqq_doc()},
                  today=date(2026, 10, 16), now=NOW_0415, namer=lambda s: s)
    return coll.docs["2026-10-16"]["indexes"], res, reads


def test_T12_the_cached_unfinished_bar_is_never_stored_as_the_close(monkeypatch):
    idx, res, reads = _t12(monkeypatch, fetch=True)
    tlt = idx["TLT"]
    assert tlt["available"] is True and tlt["source"] == "computed"
    assert tlt["close"] == 79.10, "the FINAL close, never the 10:00 print 80.40"
    assert tlt["as_of"] == "2026-10-15"
    assert tlt["bars"] and tlt["bars"][-1]["t"] == "2026-10-15"
    assert all(b["t"] != "2026-10-16" for b in tlt["bars"]), "today's bar is dropped"
    assert reads == [], "the shared cache was never read for TLT / UUP / GLD"
    assert res["sources"]["unavailable"] == 0


def test_T12_NEGATIVE_a_failed_fresh_fetch_is_unavailable_never_the_cache(monkeypatch):
    idx, res, reads = _t12(monkeypatch, fetch=False)
    for s in IZ.MACRO_SYMBOLS:
        assert idx[s]["available"] is False and idx[s]["reason"], s
        assert idx[s]["source"] == "unavailable" and idx[s]["close"] is None
    assert res["sources"]["unavailable"] == 3
    assert reads == [], "the partial cached frame is never a fallback"
    assert idx["SPY"]["available"] is True and idx["QQQ"]["available"] is True
