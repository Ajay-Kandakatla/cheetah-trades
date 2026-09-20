"""🆕 IPO tab — corroboration, the two price stats, the forward strip, the tab.

Ajay 2026-09-20: *"Can you build be an IPO tab of the hot sectors please?"* /
*"IPO of hot sector theme of stocks and then add them as a tab in Chart maps"*
/ *"Also potential future IPOs coming up if stocktwitz has"*.

    .venv/bin/python -m pytest tests/test_ipo_tab.py -q

The defect this module exists to prevent is a RECYCLED ticker printing another
company's day-one move as an IPO pop (profile2's `ipo` field is ~21.4% corrupt
on this universe), so the negative cases here are the point: a claimed date
nothing supports is DROPPED, a claimed date the bars contradict is FLAGGED and
blanked, a future date is not a listing, and a calendar outage turns the whole
board honest instead of turning it into a different board.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_maps import ipo as IPO                                    # noqa: E402
from finnhub_client import cache as FH_CACHE                         # noqa: E402
from sepa import ipo_age as IA                                       # noqa: E402

TODAY = date(2026, 9, 20)


# ── the book bound is IMPORTED, never retyped ────────────────────────────────
def test_RECENT_YEARS_equals_the_bound_ipo_age_actually_enforces():
    """`RECENT_YEARS` is read out of a real `_block()` call, not copied from
    the docstring. If anybody moves `is_recent_ipo` in sepa/ipo_age.py, this
    fails by name instead of the two modules silently disagreeing."""
    at = IA._block("2025-01-02", float(IPO.RECENT_YEARS), "profile")
    just_over = IA._block("2025-01-02", float(IPO.RECENT_YEARS) + 0.01, "profile")
    assert at["is_recent_ipo"] is True
    assert just_over["is_recent_ipo"] is False


def test_the_trailing_window_is_the_same_two_years_in_days():
    assert IPO.TRAILING_DAYS == IPO.RECENT_YEARS * 365


# ── corroboration: the four buckets ──────────────────────────────────────────
def _cal(sym="NEWCO", d="2026-06-01", status="priced", price="18.00-20.00"):
    return {"symbol": sym, "date": d, "status": status, "price": price,
            "name": f"{sym} Inc", "exchange": "NASDAQ Global",
            "numberOfShares": "5,000,000", "totalSharesValue": "95000000"}


def test_confirmed_when_the_calendar_prices_it_and_the_bars_start_with_it():
    r = IPO.corroborate("NEWCO", "2026-06-01", [_cal()], "2026-06-01", False)
    assert r["status"] == IPO.CONFIRMED
    assert r["in_calendar"] is True
    assert r["bars"] == "agree"


def test_bars_a_few_sessions_late_still_AGREE_with_the_claimed_date():
    late = (date(2026, 6, 1) + timedelta(days=IPO.BAR_SLACK_DAYS)).isoformat()
    assert IPO.corroborate("NEWCO", "2026-06-01", [_cal()], late, False)["bars"] == "agree"


def test_bucket_B_recycled_calendar_agrees_but_bars_pre_date_the_listing():
    """The whole reason this module exists. Bars from 2019 under a 2026
    listing date means the ticker carried another company's history."""
    r = IPO.corroborate("NEWCO", "2026-06-01", [_cal()], "2019-03-04", False)
    assert r["status"] == IPO.RECYCLED
    assert r["bars"] == "before"
    assert "recycled" in r["why"]


def test_bucket_A_bogus_nothing_supports_the_claimed_date():
    r = IPO.corroborate("NEWCO", "2026-06-01", [], "2019-03-04", False)
    assert r["status"] == IPO.BOGUS
    assert r["in_calendar"] is False


def test_uncorroborated_when_the_calendar_is_silent_but_the_bars_agree():
    r = IPO.corroborate("NEWCO", "2026-06-01", [], "2026-06-02", False)
    assert r["status"] == IPO.UNCORROBORATED


def test_a_first_bar_AT_THE_FETCH_CAP_is_truncation_so_the_bars_cannot_say():
    """SAIC, 2026-08-31: a frame that starts at the provider's cap is history
    truncation, not a listing. `ipo_age._at_fetch_cap` decides; this board
    never re-derives it."""
    r = IPO.corroborate("NEWCO", "2026-06-01", [_cal()], "2019-03-04", True)
    assert r["bars"] == "inconclusive"
    assert r["status"] == IPO.CONFIRMED          # calendar alone decides
    off = IPO.corroborate("NEWCO", "2026-06-01", [], "2019-03-04", True)
    assert off["status"] == IPO.UNCORROBORATED   # …and it is flagged when silent


def test_a_calendar_deal_beyond_NEAR_DAYS_is_a_DIFFERENT_deal():
    far = (date(2026, 6, 1) + timedelta(days=IPO.NEAR_DAYS + 1)).isoformat()
    r = IPO.corroborate("NEWCO", "2026-06-01", [_cal(d=far)], "2026-06-01", False)
    assert r["in_calendar"] is False
    assert r["status"] == IPO.UNCORROBORATED


def test_a_WITHDRAWN_or_FILED_calendar_row_corroborates_NOTHING():
    for status in ("withdrawn", "filed", "expected"):
        r = IPO.corroborate("NEWCO", "2026-06-01", [_cal(status=status)],
                            "2026-06-01", False)
        assert r["in_calendar"] is False, status


def test_a_calendar_row_for_a_DIFFERENT_symbol_corroborates_nothing():
    r = IPO.corroborate("NEWCO", "2026-06-01", [_cal(sym="OTHER")], "2026-06-01", False)
    assert r["in_calendar"] is False


def test_corroborate_survives_junk_rows_and_an_unparseable_claimed_date():
    assert IPO.corroborate("NEWCO", "not-a-date", [None, 7, {}, _cal()],
                           "2026-06-01", False)["bars"] == "inconclusive"
    assert IPO.corroborate("", "", None, None, False)["status"] == IPO.UNCORROBORATED


# ── the two price stats, and their labels' basis ─────────────────────────────
def _frame(start="2026-06-01", n=10, opens=None, closes=None):
    idx = pd.bdate_range(start=start, periods=n)
    o = opens or [10.0] * n
    c = closes or [11.0] * n
    return pd.DataFrame({"Open": o, "High": [max(a, b) for a, b in zip(o, c)],
                         "Low": [min(a, b) for a, b in zip(o, c)],
                         "Close": c, "Volume": [1_000_000] * n}, index=idx)


def test_day1_is_the_first_sessions_OPEN_to_CLOSE_and_week1_is_bar5_vs_that_open():
    df = _frame(opens=[20.0] + [21.0] * 9, closes=[24.0, 25, 26, 27, 30.0] + [31.0] * 5)
    m = IPO.first_moves(df, "2026-06-01")
    assert m["day1_pct"] == 20.0                      # 20 -> 24
    assert m["week1_pct"] == 50.0                     # bar 5 close 30 vs day-1 open 20
    assert m["day1_date"] == "2026-06-01"


def test_week1_is_None_until_the_fifth_session_has_happened():
    df = _frame(n=3, opens=[20.0] * 3, closes=[24.0] * 3)
    m = IPO.first_moves(df, "2026-06-01")
    assert m["day1_pct"] == 20.0
    assert m["week1_pct"] is None


def test_a_frame_that_only_picks_up_WEEKS_later_is_not_this_listings_first_session():
    df = _frame(start="2026-07-15")
    assert IPO.first_moves(df, "2026-06-01") == {
        "day1_pct": None, "week1_pct": None, "day1_date": None}


def test_first_moves_refuses_an_empty_frame_a_None_frame_and_a_bad_date():
    assert IPO.first_moves(None, "2026-06-01")["day1_pct"] is None
    assert IPO.first_moves(pd.DataFrame(), "2026-06-01")["day1_pct"] is None
    assert IPO.first_moves(_frame(), "nonsense")["day1_pct"] is None


def test_a_zero_or_negative_open_yields_no_percentage_rather_than_a_divide():
    df = _frame(opens=[0.0] * 10, closes=[11.0] * 10)
    assert IPO.first_moves(df, "2026-06-01")["day1_pct"] is None


# ── the forward strip ────────────────────────────────────────────────────────
def _forward():
    """The measured 2026-09-20 forward calendar (spec §1.6)."""
    return [
        _cal("PTT", "2026-09-30", "expected", "14.00-16.00"),
        _cal("AMRO", "2026-09-23", "expected", "4.00-5.00"),
        _cal("BMB", "2026-09-23", "expected", "8.00"),
        _cal("OLDCO", "2026-06-01", "priced"),
        _cal("FAROUT", (TODAY + timedelta(days=IPO.FORWARD_DAYS + 1)).isoformat(),
             "expected"),
        _cal("NODATE", None, "expected"),
        _cal("WD", "2026-09-25", "withdrawn"),
    ]


def test_upcoming_keeps_only_expected_rows_inside_the_forward_window_sorted_by_date():
    rows = IPO.upcoming(_forward(), TODAY)
    assert [r["symbol"] for r in rows] == ["AMRO", "BMB", "PTT"]


def test_upcoming_carries_the_feeds_keys_and_strings_VERBATIM():
    rows = IPO.upcoming(_forward(), TODAY)
    ptt = [r for r in rows if r["symbol"] == "PTT"][0]
    assert set(ptt) == {"symbol", "name", "date", "exchange", "price",
                        "numberOfShares", "totalSharesValue", "status"}
    # A RANGE, never parsed into a number.
    assert ptt["price"] == "14.00-16.00"
    assert ptt["numberOfShares"] == "5,000,000"
    assert ptt["status"] == "expected"


def test_upcoming_is_an_empty_list_not_a_None_when_nothing_is_coming():
    assert IPO.upcoming([], TODAY) == []
    assert IPO.upcoming(None, TODAY) == []
    assert IPO.upcoming([None, 5, "x"], TODAY) == []


def test_a_PAST_expected_row_is_not_upcoming():
    stale = [_cal("STALE", (TODAY - timedelta(days=2)).isoformat(), "expected")]
    assert IPO.upcoming(stale, TODAY) == []


# ── the calendar wrapper ─────────────────────────────────────────────────────
def test_ipo_calendar_cache_key_is_synthetic_per_window_and_the_TTL_is_six_hours():
    """Not a per-symbol endpoint: the WINDOW is the cache key, so two windows
    are two rows rather than one silently overwriting the other."""
    assert FH_CACHE.ttl_for("ipo_calendar") == 6 * 3600
    k1 = FH_CACHE._key("ipo_calendar", "__CAL__2026-01-01_2026-03-31")
    k2 = FH_CACHE._key("ipo_calendar", "__CAL__2026-04-01_2026-06-30")
    assert k1 == "ipo_calendar:__CAL__2026-01-01_2026-03-31"
    assert k1 != k2


def test_calendar_hands_the_thread_back_with_its_event_loop_INTACT(monkeypatch):
    """`asyncio.run()` sets the thread's current loop to None on the way out,
    which on 3.9 breaks the next thing in that thread to ask for one. The
    board runs inside asyncio.to_thread — it must leave the thread as it
    found it."""
    import asyncio

    async def fake(frm, to):
        return []

    from finnhub_client import client as FH
    monkeypatch.setattr(FH, "ipo_calendar", fake)

    # ORDER-INDEPENDENT: any earlier `asyncio.run()` in this process leaves
    # MainThread with no current loop, and on 3.9 a bare `get_event_loop()`
    # then raises. Install a known loop so the assertion is about
    # `IPO.calendar`, not about whatever test ran before this one.
    before = asyncio.new_event_loop()
    asyncio.set_event_loop(before)
    try:
        IPO.calendar("2026-01-01", "2026-02-01")
        assert asyncio.get_event_loop() is before
        assert before.is_closed() is False       # not the one it ran on
    finally:
        before.close()
        asyncio.set_event_loop(asyncio.new_event_loop())   # usable, for the rest


def test_calendar_leaves_no_CLOSED_loop_behind_on_an_already_cleared_thread(monkeypatch):
    """NEGATIVE: the thread arrives with no current loop (the state an earlier
    `asyncio.run()` leaves). The call must still work, and must not hand the
    thread back the closed loop it ran on — the next `get_event_loop()` there
    would return a corpse."""
    import asyncio

    async def fake(frm, to):
        return []

    from finnhub_client import client as FH
    monkeypatch.setattr(FH, "ipo_calendar", fake)

    asyncio.set_event_loop(None)
    try:
        assert IPO.calendar("2026-01-01", "2026-02-01")["ok"] is True
        try:
            after = asyncio.get_event_loop()
        except RuntimeError:
            after = None
        assert after is None or after.is_closed() is False
    finally:
        asyncio.set_event_loop(asyncio.new_event_loop())   # usable, for the rest


def test_the_finnhub_http_client_is_per_EVENT_LOOP_not_per_process():
    """An httpx.AsyncClient binds its pool to the loop that first used it.
    One process-wide client plus a second caller on its own loop is the
    'Event loop is closed' failure, in whichever direction it arrives."""
    import asyncio
    from finnhub_client import client as FH

    async def grab():
        return await FH._get_http()

    a, b = asyncio.new_event_loop(), asyncio.new_event_loop()
    try:
        ca, cb = a.run_until_complete(grab()), b.run_until_complete(grab())
    finally:
        a.close()
        b.close()
    assert ca is not cb


def test_calendar_chunks_the_window_and_merges_the_rows(monkeypatch):
    seen = []

    async def fake(frm, to):
        seen.append((frm, to))
        return [_cal(f"S{len(seen)}", frm)]

    from finnhub_client import client as FH
    monkeypatch.setattr(FH, "ipo_calendar", fake)
    out = IPO.calendar("2026-01-01", "2026-09-20")
    assert out["ok"] is True
    assert len(seen) == 3                       # 263 days / 90
    assert [r["symbol"] for r in out["rows"]] == ["S1", "S2", "S3"]
    assert seen[0][0] == "2026-01-01"
    assert seen[1][0] == "2026-04-01"           # no gap, no overlap


def test_one_failed_chunk_makes_the_WHOLE_calendar_not_ok_and_says_why(monkeypatch):
    """A half-fetched calendar would confirm some names and silently fail to
    confirm others — the asymmetry that makes a flag meaningless."""
    calls = {"n": 0}

    async def fake(frm, to):
        calls["n"] += 1
        return None if calls["n"] == 2 else [_cal("OK", frm)]

    from finnhub_client import client as FH
    monkeypatch.setattr(FH, "ipo_calendar", fake)
    out = IPO.calendar("2026-01-01", "2026-09-20")
    assert out["ok"] is False
    assert "calendar" in (out["reason"] or "").lower()
    assert len(out["rows"]) == 2                # what arrived is still returned


def test_calendar_refuses_a_backwards_or_unparseable_window_without_calling_out(monkeypatch):
    called = []

    async def fake(frm, to):
        called.append(1)
        return []

    from finnhub_client import client as FH
    monkeypatch.setattr(FH, "ipo_calendar", fake)
    assert IPO.calendar("2026-09-20", "2026-01-01")["ok"] is False
    assert IPO.calendar("junk", "2026-01-01")["ok"] is False
    assert called == []


# ── the population ───────────────────────────────────────────────────────────
class _Coll:
    def __init__(self, docs):
        self.docs = docs

    def find(self, q, proj=None):
        gte = ((q or {}).get("ipo") or {}).get("$gte")
        return [d for d in self.docs if not gte or str(d.get("ipo") or "") >= gte]


@pytest.fixture
def _universe(monkeypatch):
    from sepa import universe as U
    monkeypatch.setattr(U, "load_universe", lambda mode=None: ["NEWCO", "OLDCO", "PTT"])


def test_candidates_takes_in_universe_profile_dates_inside_the_trailing_window(
        monkeypatch, _universe):
    recent = (IPO._today() - timedelta(days=30)).isoformat()
    stale = (IPO._today() - timedelta(days=IPO.TRAILING_DAYS + 5)).isoformat()
    monkeypatch.setattr(IA, "_ipo_coll", lambda: _Coll([
        {"_id": "NEWCO", "ipo": recent},
        {"_id": "OLDCO", "ipo": stale},          # outside ≤2y
        {"_id": "NOTINUNIV", "ipo": recent},     # not in the universe
    ]))
    out = IPO.candidates("full")
    assert [r["symbol"] for r in out] == ["NEWCO"]
    assert out[0]["claimed_source"] == "profile"


def test_a_FUTURE_claimed_listing_date_is_not_a_candidate(monkeypatch, _universe):
    """`ipo_age.age()` already returns all-None for a future date — a company
    that has not listed has no age, and it is not on a ≤2y board either."""
    ahead = (IPO._today() + timedelta(days=5)).isoformat()
    monkeypatch.setattr(IA, "_ipo_coll", lambda: _Coll([{"_id": "NEWCO", "ipo": ahead}]))
    assert IPO.candidates("full") == []


def test_a_brand_new_PRICED_calendar_listing_joins_the_population(
        monkeypatch, _universe):
    monkeypatch.setattr(IA, "_ipo_coll", lambda: _Coll([]))
    d = (IPO._today() - timedelta(days=3)).isoformat()
    out = IPO.candidates("full", cal_rows=[_cal("PTT", d, "priced")])
    assert [r["symbol"] for r in out] == ["PTT"]
    assert out[0]["claimed_source"] == "calendar"


def test_a_calendar_symbol_OUTSIDE_the_universe_never_becomes_a_candidate(
        monkeypatch, _universe):
    monkeypatch.setattr(IA, "_ipo_coll", lambda: _Coll([]))
    d = (IPO._today() - timedelta(days=3)).isoformat()
    assert IPO.candidates("full", cal_rows=[_cal("OFFLIST", d, "priced")]) == []


def test_candidates_survives_a_dead_mongo_and_a_dead_universe(monkeypatch):
    from sepa import universe as U
    monkeypatch.setattr(U, "load_universe", lambda mode=None: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(IA, "_ipo_coll", lambda: None)
    assert IPO.candidates("full") == []


# ── build(), end to end on mocked data ───────────────────────────────────────
def _install(monkeypatch, cal_rows, ok=True, frames=None, docs=None):
    from sepa import universe as U
    from sepa import prices as P
    from finnhub_client import client as FH

    monkeypatch.setattr(U, "load_universe",
                        lambda mode=None: ["GOODCO", "RECYC", "SILENT", "FAKE"])
    monkeypatch.setattr(IA, "_ipo_coll", lambda: _Coll(docs or []))
    monkeypatch.setattr(P, "load_prices", lambda s, period="2y", force=False:
                        (frames or {}).get(s))

    async def fake(frm, to):
        return cal_rows if ok else None
    monkeypatch.setattr(FH, "ipo_calendar", fake)


def _docs(listed):
    return [{"_id": s, "ipo": d} for s, d in listed.items()]


def test_build_confirms_flags_and_DROPS_across_the_four_buckets(monkeypatch):
    listed = (IPO._today() - timedelta(days=40))
    d = listed.isoformat()
    frames = {
        "GOODCO": _frame(start=d, opens=[20.0] + [21.0] * 9,
                         closes=[24.0, 25, 26, 27, 30.0] + [31.0] * 5),
        "RECYC": _frame(start="2019-03-04"),
        "SILENT": _frame(start=d),
        "FAKE": _frame(start="2019-03-04"),
    }
    _install(monkeypatch,
             [_cal("GOODCO", d, "priced"), _cal("RECYC", d, "priced")],
             frames=frames,
             docs=_docs({"GOODCO": d, "RECYC": d, "SILENT": d, "FAKE": d}))

    out = IPO.build(limit=10)
    by = {r["symbol"]: r for r in out["rows"]}
    assert "FAKE" not in by                                   # bucket A: dropped
    assert by["GOODCO"]["status"] == IPO.CONFIRMED
    assert by["GOODCO"]["day1_pct"] == 20.0
    assert by["GOODCO"]["week1_pct"] == 50.0
    assert by["RECYC"]["status"] == IPO.RECYCLED              # bucket B: flagged
    assert by["RECYC"]["recycled"] is True
    assert by["RECYC"]["day1_pct"] is None and by["RECYC"]["week1_pct"] is None
    assert by["SILENT"]["status"] == IPO.UNCORROBORATED
    assert out["counts"] == {"candidates": 4, "confirmed": 1, "recycled": 1,
                             "uncorroborated": 1, "dropped_bogus": 1, "upcoming": 0}
    assert out["corroboration"]["available"] is True
    assert "not measured" in out["note"].lower() or "Nothing here is measured" in out["note"]


def test_a_CALENDAR_OUTAGE_still_builds_the_board_and_marks_every_row(monkeypatch):
    d = (IPO._today() - timedelta(days=40)).isoformat()
    _install(monkeypatch, [], ok=False,
             frames={"GOODCO": _frame(start=d), "FAKE": _frame(start="2019-03-04")},
             docs=_docs({"GOODCO": d, "FAKE": d}))
    out = IPO.build(limit=10)
    assert {r["status"] for r in out["rows"]} == {IPO.UNCORROBORATED}
    # Nothing is dropped: the board did not quietly become a different board.
    assert out["counts"]["dropped_bogus"] == 0
    assert out["corroboration"]["available"] is False
    assert out["corroboration"]["reason"]
    # …and the one whose bars pre-date its claim STILL prints no price stat.
    fake = [r for r in out["rows"] if r["symbol"] == "FAKE"][0]
    assert fake["recycled"] is True and fake["day1_pct"] is None


def test_build_orders_newest_listing_first(monkeypatch):
    old = (IPO._today() - timedelta(days=400)).isoformat()
    new = (IPO._today() - timedelta(days=5)).isoformat()
    _install(monkeypatch, [_cal("GOODCO", old, "priced"), _cal("RECYC", new, "priced")],
             frames={"GOODCO": _frame(start=old), "RECYC": _frame(start=new)},
             docs=_docs({"GOODCO": old, "RECYC": new}))
    out = IPO.build(limit=10)
    assert [r["symbol"] for r in out["rows"]] == ["RECYC", "GOODCO"]


def test_build_counts_the_forward_rows_it_serves(monkeypatch):
    d = (IPO._today() - timedelta(days=40)).isoformat()
    ahead = (IPO._today() + timedelta(days=4)).isoformat()
    _install(monkeypatch, [_cal("GOODCO", d, "priced"), _cal("PTT", ahead, "expected")],
             frames={"GOODCO": _frame(start=d)}, docs=_docs({"GOODCO": d}))
    out = IPO.build(limit=10)
    assert out["counts"]["upcoming"] == 1
    assert out["upcoming"][0]["symbol"] == "PTT"


# ── the tab ──────────────────────────────────────────────────────────────────
def test_the_board_registers_the_ipo_tab():
    from chart_maps import board as B
    assert "ipo" in B.TABS


def test_the_dispatcher_routes_tab_ipo_to_ipo_tiles(monkeypatch):
    from chart_maps import board as B
    seen = {}

    def fake(limit, days, themes_first=False, min_tier=None):
        seen.update(limit=limit, days=days)
        return {"tiles": [], "upcoming": [], "counts": {}, "note": "n"}

    monkeypatch.setattr(B, "ipo_tiles", fake)
    out = B.board(tab="ipo", limit=7, days=60)
    assert seen == {"limit": 7, "days": 60}
    assert out["tab"] == "ipo"


def _tile_rows(**over):
    base = {"symbol": "GOODCO", "claimed": "2026-08-01", "claimed_source": "profile",
            "status": IPO.CONFIRMED, "in_calendar": True, "bars": "agree",
            "why": "w", "first_bar": "2026-08-01", "days_since": 50,
            "recycled": False, "day1_pct": 20.0, "week1_pct": 50.0,
            "day1_date": "2026-08-01"}
    base.update(over)
    return base


def _stub_board(monkeypatch, rows, **payload):
    from chart_maps import board as B
    from chart_maps import ipo as I
    data = {"rows": rows, "upcoming": [], "counts": {}, "as_of": "2026-09-20",
            "corroboration": {"available": True, "reason": None,
                              "trailing_from": "2024-09-21", "forward_to": "2026-10-20"},
            "note": I.NOTE}
    data.update(payload)
    monkeypatch.setattr(I, "build", lambda **k: data)
    monkeypatch.setattr(B, "_attach_bars",
                        lambda tiles, days: [t.update(bars=[{"c": 1}]) for t in tiles])
    monkeypatch.setattr(B, "_name_for", lambda s: f"{s} Inc")
    monkeypatch.setattr(B, "_theme", lambda s: "ai_software")
    from sepa import research as R
    monkeypatch.setattr(R, "sales_snapshot",
                        lambda syms, **k: {"GOODCO": {"sales": {"tier": "explosive"}}})
    return B


def test_a_confirmed_tile_prints_the_two_stats_under_labels_that_state_the_basis(
        monkeypatch):
    B = _stub_board(monkeypatch, [_tile_rows()])
    t = B.ipo_tiles(limit=5, days=60)["tiles"][0]
    stats = {s["k"]: s["v"] for s in t["stats"]}
    # The labels are the fix: neither number is the pop off the OFFER price.
    assert stats["Day-1 open→close"] == "+20.0%"
    assert stats["Week-1 vs day-1 open"] == "+50.0%"
    assert "Day 1" not in stats and "Pop" not in stats
    assert stats["Listed"] == "2026-08-01"
    assert stats["Days since"] == "50"
    assert stats["Sales tier"] == "explosive"
    assert t["href"] == "/sepa/GOODCO?tab=supply"
    assert any(b["text"] == f"Recent IPO ≤{IPO.RECENT_YEARS}y" for b in t["badges"])


def test_a_recycled_tile_carries_the_warn_badge_and_prints_NO_price_stat(monkeypatch):
    B = _stub_board(monkeypatch, [_tile_rows(
        symbol="RECYC", status=IPO.RECYCLED, recycled=True,
        day1_pct=None, week1_pct=None)])
    t = B.ipo_tiles(limit=5, days=60)["tiles"][0]
    stats = {s["k"]: s["v"] for s in t["stats"]}
    assert stats["Day-1 open→close"] == "—"
    assert stats["Week-1 vs day-1 open"] == "—"
    assert t["recycled"] is True
    assert any("recycled ticker" in b["text"] for b in t["badges"])
    assert any(b["tone"] == "warn" for b in t["badges"])


def test_an_uncorroborated_tile_says_the_calendar_has_no_record(monkeypatch):
    B = _stub_board(monkeypatch, [_tile_rows(status=IPO.UNCORROBORATED,
                                             in_calendar=False)])
    t = B.ipo_tiles(limit=5, days=60)["tiles"][0]
    assert any(b["text"] == "calendar: no record" and b["tone"] == "warn"
               for b in t["badges"])


def test_the_tab_serves_the_not_measured_note_the_upcoming_rows_and_the_counts(
        monkeypatch):
    B = _stub_board(monkeypatch, [_tile_rows()],
                    upcoming=[{"symbol": "PTT", "date": "2026-09-30",
                               "status": "expected"}],
                    counts={"candidates": 4, "confirmed": 1, "recycled": 1,
                            "uncorroborated": 1, "dropped_bogus": 1, "upcoming": 1})
    out = B.ipo_tiles(limit=5, days=60)
    assert "Nothing here is measured or claims an edge." in out["note"]
    assert "sepa/ipo_age" in out["note"] and "TLSW Ch.11" in out["note"]
    assert out["upcoming"][0]["symbol"] == "PTT"
    assert out["counts"]["dropped_bogus"] == 1
    assert out["corroboration"]["available"] is True


def test_the_tab_says_out_loud_that_it_is_FLAT_and_applies_neither_control(
        monkeypatch):
    B = _stub_board(monkeypatch, [_tile_rows()])
    out = B.ipo_tiles(limit=5, days=60, themes_first=True, min_tier="strong")
    assert "Flat" in out["criteria"]
    assert "liquidity" in out["criteria"]
    # The control did not silently drop the tile it would have dropped elsewhere.
    assert [t["symbol"] for t in out["tiles"]] == ["GOODCO"]


def test_the_tab_returns_an_empty_board_with_the_reason_when_the_read_THROWS(
        monkeypatch):
    from chart_maps import board as B
    from chart_maps import ipo as I

    def boom(**k):
        raise RuntimeError("mongo down")

    monkeypatch.setattr(I, "build", boom)
    out = B.ipo_tiles(limit=5, days=60)
    assert out["tiles"] == [] and out["upcoming"] == []
    assert out["corroboration"]["available"] is False
    assert "mongo down" in out["corroboration"]["reason"]
