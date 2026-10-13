"""WP1 critic fixes (2026-10-13): the instrument-type map under a partial fetch, the pre-market volume fallback,
the after-hours `day.c` tripwire, class-share spelling + provider-failure counting in the bar pass, and the
holiday-aware "last session" in `closed_daily_frame`. Positive + NEGATIVE cases."""
from __future__ import annotations

import threading
from datetime import date

import pandas as pd
import pytest

from chart_maps.gajjala import bars as B
from chart_maps.gajjala import scanner as SC
from daytrading import data as D
from sepa import prices as P
from tests.test_daytrading_data_et_today import _R
from tests.test_gajjala_bars import PREV, S, et, raw_day
from tests.test_gajjala_scanner import at, row, scan
from tests.test_gajjala_store import fake_store
from tests.test_prices_market_snapshot import _daily

Y = date(2026, 10, 12)


@pytest.fixture(autouse=True)
def _clean_breaker(monkeypatch):
    D._CB["fails"] = 0
    D._CB["open_until"] = 0.0
    D.clear_fetch_failed()
    monkeypatch.setattr(D, "stocks_key", lambda: "k")
    monkeypatch.setattr(D.time, "sleep", lambda s: None)
    yield
    D._CB["fails"] = 0
    D._CB["open_until"] = 0.0
    D.clear_fetch_failed()


# ── #1 type map: only a COMPLETE fetch replaces it ──────────────────────────────────────────────────────────
def _seed_yesterday(st):
    SC.ensure_type_map(st, Y, fetch=lambda: ({"AAA": "CS", "SOXL": "ETF", "ZVZZW": "WARRANT"}, True, 14))


def test_NEGATIVE_partial_fetch_never_drops_a_known_etf_to_unknown():
    st = fake_store()
    _seed_yesterday(st)
    calls = []

    def partial():
        calls.append(1)
        return {"AAA": "CS"}, False, 7
    m = SC.ensure_type_map(st, S, fetch=partial)
    assert SC.row_type("SOXL", m) == "ETF" and SC.row_type("ZVZZW", m) == "WARRANT"
    doc = st.types_map()
    assert doc["as_of"] == Y.isoformat() and doc["complete"] is False
    assert doc["last_partial"] == {"session": S.isoformat(), "n": 1, "calls": 7}
    SC.ensure_type_map(st, S, fetch=partial)
    assert len(calls) == 2                                        # the next pass retries


def test_NEGATIVE_partial_map_still_keeps_the_etf_off_the_board():
    st = fake_store()
    _seed_yesterday(st)
    m = SC.ensure_type_map(st, S, fetch=lambda: ({"AAA": "CS"}, False, 7))
    res = scan({"AAA": row(2.0), "SOXL": row(2.0), "ZVZZW": row(2.0)}, types=m)
    assert {q["symbol"] for q in res["qualifiers"]} == {"AAA"}
    assert res["counts"]["type_out"] == 2 and res["counts"]["type_unknown"] == 0


def test_partial_merges_new_names_then_a_complete_fetch_replaces_and_stops_retrying():
    st = fake_store()
    _seed_yesterday(st)
    m = SC.ensure_type_map(st, S, fetch=lambda: ({"NEWCO": "CS", "SOXL": "ETF"}, False, 3))
    assert m == {"AAA": "CS", "SOXL": "ETF", "ZVZZW": "WARRANT", "NEWCO": "CS"}
    calls = []

    def full():
        calls.append(1)
        return {"AAA": "CS", "NEWCO": "CS"}, True, 14
    assert SC.ensure_type_map(st, S, fetch=full) == {"AAA": "CS", "NEWCO": "CS"}
    assert SC.ensure_type_map(st, S, fetch=full) == {"AAA": "CS", "NEWCO": "CS"}
    assert len(calls) == 1 and st.types_map()["as_of"] == S.isoformat() and st.types_map()["complete"] is True


def test_NEGATIVE_first_ever_fetch_failing_is_retried_not_empty_all_day():
    st = fake_store()
    seq = [({}, False, 1), ({"AAA": "CS", "SOXL": "ETF"}, True, 14)]
    assert SC.ensure_type_map(st, S, fetch=lambda: seq.pop(0)) == {}
    assert SC.ensure_type_map(st, S, fetch=lambda: seq.pop(0)) == {"AAA": "CS", "SOXL": "ETF"}


def test_NEGATIVE_complete_but_empty_listing_never_wipes_the_map():
    st = fake_store()
    _seed_yesterday(st)
    assert SC.ensure_type_map(st, S, fetch=lambda: ({}, True, 1))["SOXL"] == "ETF"
    assert st.types_map()["as_of"] == Y.isoformat()


def test_NEGATIVE_raised_fetch_keeps_the_map_and_retries():
    st = fake_store()
    _seed_yesterday(st)
    n = []

    def boom():
        n.append(1)
        raise RuntimeError("apiKey=SECRET")
    assert SC.ensure_type_map(st, S, fetch=boom)["ZVZZW"] == "WARRANT"
    SC.ensure_type_map(st, S, fetch=boom)
    assert len(n) == 2


# ── #3 pre-market never qualifies on the prior session's day.v ─────────────────────────────────────────────
def test_NEGATIVE_premarket_stale_min_never_falls_back_to_day_v():
    res = scan({"ECHO": row(1.30, prev=1.0, vol=5_000_000, when=at(6, 59), min_when=at(19, 59, Y),
                            day_v=5_000_000)}, now=at(7, 0))
    assert res["qualifiers"] == []
    assert res["counts"]["vol_ok"] == 0 and res["strip"]["n_population"] == 0
    assert SC._volume(row(1.3, vol=5e6, when=at(6, 59), min_when=at(19, 59, Y), day_v=5e6), S.isoformat(),
                      "premarket") == (0.0, "none")


def test_premarket_min_dated_today_still_qualifies():
    res = scan({"ECHO": row(1.30, vol=1_500_000, when=at(6, 59), min_when=at(6, 59))}, now=at(7, 0))
    assert [(q["symbol"], q["vol_src"]) for q in res["qualifiers"]] == [("ECHO", "min_av")]


def test_rth_stale_min_still_uses_day_v():
    res = scan({"AAA": row(1.30, vol=5_000_000, when=at(10, 59), min_when=at(19, 59, Y), day_v=2_000_000)},
               now=at(11, 0))
    assert [(q["symbol"], q["vol_src"], q["volume"]) for q in res["qualifiers"]] == [("AAA", "day_v", 2_000_000)]


# ── #2 after-hours day.c tripwire ───────────────────────────────────────────────────────────────────────────
def _ah(price, close):
    return row(price, prev=1.0, vol=10, when=at(17, 0), close=close)


def test_ah_close_eq_last_counts_rows_whose_day_c_is_the_last_print():
    res = scan({"AAA": _ah(2.4, 2.4), "BBB": _ah(2.4, 2.0)}, now=at(17, 1))
    assert res["counts"]["ah_rows"] == 2 and res["counts"]["ah_close_eq_last"] == 1
    assert [r["symbol"] for r in res["ah_carry"]] == ["BBB"]


def test_NEGATIVE_tripwire_untouched_outside_after_hours():
    res = scan({"AAA": row(2.4, close=2.4, when=at(10, 59))}, now=at(11, 0))
    assert res["counts"]["ah_rows"] == 0 and res["counts"]["ah_close_eq_last"] == 0


# ── #4/#5 bar pass: Massive spelling + provider failures counted as failed ───────────────────────────────────
def test_class_share_loaded_in_massive_spelling_keyed_by_the_listed_symbol():
    asked = []

    def load(sym, day, force=False, **k):
        asked.append(sym)
        return raw_day(day, end=(10, 10)) if sym == "MOG.A" else None
    stats = {}
    out = B.frames_for(["MOG-A"], S, et(10, 6), load_day=load, stats=stats)
    assert set(out) == {"MOG-A"} and set(asked) == {"MOG.A"} and stats["loaded"] == 1


def test_NEGATIVE_provider_failure_counts_failed_not_no_bars():
    def throttled(sym, day, force=False, **k):
        if sym == "THR":
            return D._provider_failed()                         # what the 429 cap / open breaker does
        return {PREV: raw_day(PREV)}.get(day)                   # EMPTY: a genuine no-bar-today name
    stats = {}
    out = B.frames_for(["THR", "EMPTY"], S, et(10, 6), load_day=throttled, stats=stats)
    assert out == {} and stats["failed"] == 1 and stats["no_bars"] == 1


def test_NEGATIVE_a_failed_prev_day_does_not_leak_into_the_next_name():
    def load(sym, day, force=False, **k):
        if sym == "A1" and day == PREV:
            return D._provider_failed()
        if sym == "A1":
            return raw_day(day, end=(10, 10))
        return None
    stats = {}
    out = B.frames_for(["A1", "B2"], S, et(10, 6), load_day=load, stats=stats, workers=1)
    assert set(out) == {"A1"} and stats["loaded"] == 1 and stats["no_bars"] == 1 and stats["failed"] == 0


def test_fetch_flags_the_429_cap_and_the_open_breaker_but_not_an_empty_200(monkeypatch):
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: _R(429))
    assert D._fetch_massive_minute("AAA", Y, Y) is None and D.last_fetch_failed() is True
    monkeypatch.setattr(requests, "get", lambda *a, **k: _R(200, {"results": []}))
    assert D._fetch_massive_minute("AAA", Y, Y) is None and D.last_fetch_failed() is False
    D._CB["open_until"] = D.time.time() + 60
    monkeypatch.setattr(requests, "get", lambda *a, **k: pytest.fail("breaker open: no call"))
    assert D._fetch_massive_minute("AAA", Y, Y) is None and D.last_fetch_failed() is True


def test_NEGATIVE_the_failure_flag_is_per_thread():
    D._provider_failed()
    seen = []
    t = threading.Thread(target=lambda: seen.append(D.last_fetch_failed()))
    t.start()
    t.join()
    assert seen == [False] and D.last_fetch_failed() is True


# ── #6 closed_daily_frame: the house calendar's last session, not BDay ──────────────────────────────────────
AFTER_HOLIDAY = pd.Timestamp("2026-11-27 11:00", tz="America/New_York")   # Fri after Thanksgiving


def test_after_a_weekday_holiday_the_cache_holding_the_last_session_is_used(monkeypatch):
    monkeypatch.setattr(P, "_mongo_get", lambda s: _daily("2026-11-25"))
    monkeypatch.setattr(P, "_fetch", lambda *a: pytest.fail("Wed 11-25 is the last session; no re-fetch"))
    assert P.closed_daily_frame("AAA", now=AFTER_HOLIDAY).index.max() == pd.Timestamp("2026-11-25")


def test_NEGATIVE_a_cache_missing_the_last_session_still_fetches(monkeypatch):
    fetched = []
    monkeypatch.setattr(P, "_mongo_get", lambda s: _daily("2026-11-24"))
    monkeypatch.setattr(P, "_fetch", lambda sym, period: fetched.append(sym) or _daily("2026-11-27", 8))
    out = P.closed_daily_frame("AAA", now=AFTER_HOLIDAY)
    assert fetched == ["AAA"] and out.index.max() < pd.Timestamp("2026-11-27")
