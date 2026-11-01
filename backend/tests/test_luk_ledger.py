"""chart_maps/luk/ledger.py — 🥇 Luk's 🏁 Track record graded by LUK's trade math (BUILD_SPEC luk-tab §3.9, WP-B,
2026-11-01).

Ajay 2026-11-01: "look at other winners of US stocks champion ship and pic the next best one like Gajjala. Implement
their strategy please if they have online resources."

Every store is the in-memory FakeColl set (tests/conftest.py refuses a real MongoClient); every loader and the daily
fetch are injected — never the network. The house daily cache (`sepa.prices.cached_frame_meta`) is stubbed by the
`cache` fixture only to prove the grader NEVER reads it (REFIX 2026-11-01: closed days come only from Luk's own
post-close fetch). Every bar is SYNTHETIC. NEGATIVES are marked.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import alerts as GA
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import store as GS
from chart_maps.luk import constants as LC
from chart_maps.luk import ledger as LL
from chart_maps.luk import store as LS
from chart_maps.luk.variant import LUK
from tests.test_gajjala_store import FakeColl

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
PRE = date(2026, 10, 30)                       # Fri — before LUK_RECORD_FROM (2026-11-01, a Sunday)
D, D2, D3, D4 = date(2026, 11, 2), date(2026, 11, 3), date(2026, 11, 4), date(2026, 11, 5)
B_WORD = re.compile("b" + "ounc", re.I)
EDGE = re.compile(r"\bedge\b", re.I)


def et(d, hh, mm, ss=0) -> datetime:
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=ET).astimezone(UTC)


def bar(d, hh, mm, o, h, lo, c) -> tuple:
    return (et(d, hh, mm), float(o), float(h), float(lo), float(c))


def flat(d, start, end, px) -> list:
    out, t, stop = [], et(d, *start), et(d, *end)
    while t <= stop:
        out.append((t, float(px), float(px), float(px), float(px)))
        t += timedelta(minutes=1)
    return out


def merge(*parts) -> list:
    by = {}
    for p in parts:
        for b in p:
            by[b[0]] = b
    return [by[k] for k in sorted(by)]


def alert_doc(sym="ABC", setup="pullback_reversal", d=D, at=None, trig=10.0, stop=9.5, px=10.0, state="shadow",
              _id=None) -> dict:
    at = at or et(d, 10, 0, 15)
    return {"_id": _id or GA.shadow_key(d, sym, setup, LUK), "date": d.isoformat(), "symbol": sym, "setup": setup,
            "mode": "shadow", "frame": "5m", "trigger": trig, "stop": stop, "price": px, "kind": LUK.push_kind_setup,
            "state": state, "at": at.isoformat(), "note": GA.SHADOW_NOTE}


def make_store(alerts=(), ledger=(), fail_alerts=False):
    colls = {n: FakeColl() for n in LS.LOGICAL}
    colls[GS.ALERTS] = FakeColl(list(alerts), fail=fail_alerts)
    colls[GS.LEDGER] = FakeColl(list(ledger))
    colls[LS.SCREENS_KEY] = FakeColl()
    return LS.LukStore(colls=colls)


def row_for(doc) -> dict:
    r = LL.row_of(doc)
    assert r is not None
    return r


def daily_frame(closes: dict, base=10.0, n_hist=30) -> pd.DataFrame:
    """SYNTHETIC daily bars: n_hist sessions at `base` before the first dated close, then `closes` {date: close}."""
    first = min(closes)
    hist = pd.bdate_range(end=pd.Timestamp(first) - pd.Timedelta(days=1), periods=n_hist)
    idx = list(hist) + [pd.Timestamp(d) for d in sorted(closes)]
    cl = [base] * n_hist + [closes[d] for d in sorted(closes)]
    return pd.DataFrame({"open": cl, "high": cl, "low": cl, "close": cl, "volume": [1e6] * len(cl)},
                        index=pd.DatetimeIndex(idx))


def cached_at(d, hh, mm, ss=0) -> float:
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=ET).timestamp()


class _CacheBox(dict):
    """{SYM: {"frame", "cached_at"}}; `.reads` = every symbol the house cache was asked for."""

    def __init__(self):
        super().__init__()
        self.reads: list = []

    def meta(self, sym):
        self.reads.append(sym)
        return self.get(sym)


@pytest.fixture
def cache(monkeypatch):
    """The house daily cache, stubbed: {SYM: {"frame", "cached_at"}} (absent → None). The grader must never read it."""
    box = _CacheBox()
    from sepa import prices
    monkeypatch.setattr(prices, "cached_frame_meta", box.meta)
    return box


def _epoch(t: datetime) -> float:
    return t.timestamp()


class Loader:
    """load_day(sym, d) → (bars, failed); counts calls."""

    def __init__(self, by_day):
        self.by_day = by_day
        self.calls = []

    def __call__(self, sym, d):
        self.calls.append((sym, d))
        return list(self.by_day.get(d, [])), False


class Fetch:
    def __init__(self, frame=None):
        self.frame = frame
        self.calls = []

    def __call__(self, sym):
        self.calls.append(sym)
        return self.frame


# ── rows ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_shadow_claim_is_a_row_with_the_plan():
    r = row_for(alert_doc())
    assert r["id"] == "2026-11-02|ABC|pullback_reversal|aplus" == LL.row_id("2026-11-02", "abc", "pullback_reversal")
    assert r["plan"] == "ok" and r["r_usd"] == pytest.approx(0.5) and r["r_pct"] == pytest.approx(5.0)
    assert r["rang"] == "rth" and r["at_et"] == "10:00"
    assert r["url"] == "/chart-maps?tab=luk&sub=pullback_reversal&focus=ABC"


def test_NEGATIVE_a_row_dated_before_record_from_is_not_a_row():
    assert LL.record_from() == date(2026, 11, 1)
    assert LL.row_of(alert_doc(d=PRE)) is None
    st = make_store([alert_doc(d=PRE), alert_doc(d=D)])
    assert [r["date"] for r in LL.rows_for([PRE, D], st)] == ["2026-11-02"]
    assert LL.rows_for([PRE], st) == []                    # the session itself is clipped: no read at all


@pytest.mark.parametrize("over", [
    {"state": "late"},                                                 # a refusal state
    {"_id": GA.claim_key(D, "ABC", "pullback_reversal", LUK) + "#late"},   # a `#state` refusal id
    {"_id": GA.shadow_key(D, "ABC", "pullback_reversal", None)},       # GG's shadow key, not Luk's
    {"setup": "bull_flag"},                                            # not one of his setups
])
def test_NEGATIVE_a_doc_that_is_not_a_luk_shadow_claim_is_not_a_row(over):
    doc = dict(alert_doc(), **over)
    assert LL.row_of(doc) is None


def test_NEGATIVE_an_unreadable_alerts_collection_raises_not_empty():
    with pytest.raises(LL.LedgerReadError):
        LL.rows_for([D], make_store([alert_doc()], fail_alerts=True))


# ── the fill (the house convention, pinned equal to gajjala.ledger.grade) ────────────────────────────────────────
def _gg_fill(doc, bars):
    row = row_for(doc)
    gg = {"at_utc": row["at_utc"], "trigger": row["trigger"], "stop": row["stop"], "plan": "ok"}
    g = LG.grade(gg, bars, LG.session_bounds(D, row["at_utc"]), "same")
    return g["fill_px"], g["fill_t"]


def test_fill_equals_gajjala_ledger_grade_on_a_shared_fixture():
    doc = alert_doc(at=et(D, 10, 0, 15), trig=10.0, stop=9.5)
    bars = merge(flat(D, (9, 30), (10, 5), 9.9), [bar(D, 10, 6, 10.02, 10.3, 10.0, 10.2)],
                 flat(D, (10, 7), (15, 59), 10.2))
    f = LL.fill(row_for(doc), bars)
    assert f is not None and f["entry"] == "filled"
    assert (f["fill_px"], f["fill_t"]) == _gg_fill(doc, bars)
    assert f["fill_px"] == pytest.approx(10.02) and f["fill_t"] == et(D, 10, 6).isoformat()


def test_fill_waits_bar_settle_after_the_alert():
    doc = alert_doc(at=et(D, 10, 0, 45))
    bars = [bar(D, 10, 1, 10.0, 10.1, 9.9, 10.0), bar(D, 10, 2, 10.05, 10.1, 9.9, 10.0)]
    f = LL.fill(row_for(doc), bars)
    assert f["fill_t"] == et(D, 10, 2).isoformat()          # 10:01:00 < 10:00:45 + 30 s
    assert (f["fill_px"], f["fill_t"]) == _gg_fill(doc, bars)


def test_fill_from_the_regular_open_where_gg_waits_to_0945():
    doc = alert_doc(at=et(D, 9, 31, 10))
    bars = merge([bar(D, 9, 33, 10.0, 10.2, 9.9, 10.1)], flat(D, (9, 34), (15, 59), 9.9))
    f = LL.fill(row_for(doc), bars)
    assert f["fill_t"] == et(D, 9, 33).isoformat()          # HIS CALL #16: 09:30, not GG's 09:45
    assert _gg_fill(doc, bars) == (None, None)              # GG's window never fills it — the documented difference


def test_fill_px_is_the_open_on_a_gap_through_the_trigger():
    f = LL.fill(row_for(alert_doc()), [bar(D, 10, 5, 10.3, 10.4, 10.2, 10.35)])
    assert f["fill_px"] == pytest.approx(10.3)


def test_NEGATIVE_no_fill_by_the_close_is_no_entry_and_after_hours_never_fills():
    doc = alert_doc()
    bars = merge(flat(D, (10, 1), (15, 59), 9.9), [bar(D, 16, 0, 10.5, 10.6, 10.4, 10.5)])
    assert LL.fill(row_for(doc), bars) is None
    nxt = [bar(D2, 9, 31, 10.5, 10.6, 10.4, 10.5)]          # same session only (HIS CALL #16)
    assert LL.fill(row_for(doc), nxt) is None


def test_NEGATIVE_no_plan_never_fills():
    assert LL.fill(row_for(alert_doc(trig=9.5, stop=9.5)), [bar(D, 10, 5, 10, 11, 9.9, 10)]) is None


# ── the walk (LUK's exits) ───────────────────────────────────────────────────────────────────────────────────────
FILL = {"entry": "filled", "fill_px": 10.0, "fill_t": et(D, 10, 5).isoformat(), "fill_date": D.isoformat()}


def day(d, bars, close=None, ema9=None) -> dict:
    return {"date": d.isoformat(), "bars": bars, "close": close, "ema9_close": ema9}


def test_stop_first_is_minus_one_r_with_no_flags():
    row = row_for(alert_doc())
    bars = [bar(D, 10, 5, 10, 10.1, 9.9, 10), bar(D, 10, 12, 9.8, 9.8, 9.45, 9.5)]
    w = LL.walk(row, FILL, [day(D, bars, 9.6, 9.0)])
    assert (w["exit"], w["state"], w["r"], w["sessions"]) == ("stop", "stopped", -1.0, 1)
    assert w["exit_t"] == et(D, 10, 12).isoformat() and w["exit_px"] == 9.5
    assert w["reached_3r"] is False and w["reached_5r"] is False


def test_the_fill_minute_low_counts_for_the_stop():
    row = row_for(alert_doc())
    w = LL.walk(row, FILL, [day(D, [bar(D, 10, 5, 10, 10.1, 9.5, 10)], 10.5, 9.0)])
    assert w["exit"] == "stop" and w["exit_t"] == et(D, 10, 5).isoformat()


def test_exit_on_the_first_daily_close_below_the_9_ema_after_two_sessions_above():
    row = row_for(alert_doc())
    days = [day(D, [bar(D, 10, 6, 10, 10.4, 9.9, 10.3)], 10.3, 10.1),
            day(D2, [bar(D2, 10, 0, 10.3, 10.6, 10.2, 10.5)], 10.5, 10.2),
            day(D3, [bar(D3, 10, 0, 10.5, 10.6, 10.1, 10.15)], 10.15, 10.2)]
    w = LL.walk(row, FILL, days)
    assert (w["exit"], w["sessions"], w["exit_date"]) == ("ema9_close", 3, D3.isoformat())
    assert w["r"] == pytest.approx((10.15 - 10.0) / 0.5) and w["exit_px"] == 10.15


def test_a_close_equal_to_the_9_ema_is_not_below_it():
    w = LL.walk(row_for(alert_doc()), FILL, [day(D, [bar(D, 10, 6, 10, 10.1, 9.9, 10)], 10.2, 10.2)])
    assert w["exit"] is None and w["state"] == "open"


def test_3r_reached_before_a_later_stop_flags_and_still_minus_one():
    row = row_for(alert_doc())
    bars = [bar(D, 10, 6, 10, 11.5, 9.9, 11.4), bar(D, 11, 0, 11, 11, 9.5, 9.5)]
    w = LL.walk(row, FILL, [day(D, bars, 9.5, 9.0)])
    assert w["reached_3r"] is True and w["reached_3r_t"] == et(D, 10, 6).isoformat()
    assert w["reached_5r"] is False and (w["exit"], w["r"]) == ("stop", -1.0)
    assert w["best_r"] == pytest.approx(3.0)


def test_5r_reached_and_exit_by_the_9_ema():
    row = row_for(alert_doc())
    days = [day(D, [bar(D, 10, 6, 10, 12.6, 9.9, 12.4)], 12.4, 11.0),
            day(D2, [bar(D2, 10, 0, 12, 12.1, 11.0, 11.2)], 11.2, 11.5)]
    w = LL.walk(row, FILL, days)
    assert w["reached_3r"] and w["reached_5r"] and w["exit"] == "ema9_close" and w["sessions"] == 2
    assert w["r"] == pytest.approx(2.4)
    assert LL.flags_text(w) == "+3R and +5R reached" and LL.flags_text({"reached_3r": True}) == "+3R reached"


def test_NEGATIVE_the_fill_minutes_high_never_sets_a_flag():
    w = LL.walk(row_for(alert_doc()), FILL, [day(D, [bar(D, 10, 5, 10, 13, 9.9, 10.1)], 10.1, 9.0)])
    assert w["reached_3r"] is False and w["reached_5r"] is False and LL.flags_text(w) == ""


def test_NEGATIVE_a_bar_with_the_stop_and_a_target_is_a_stop_with_no_flag():
    w = LL.walk(row_for(alert_doc()), FILL, [day(D, [bar(D, 10, 7, 10, 11.6, 9.4, 10)], 10, 9.0)])
    assert w["exit"] == "stop" and w["reached_3r"] is False


def test_a_row_with_no_exit_stays_open_with_r_now():
    row = row_for(alert_doc())
    days = [day(D, [bar(D, 10, 6, 10, 10.3, 9.9, 10.2)], 10.2, 10.0),
            day(D2, [bar(D2, 10, 0, 10.2, 10.5, 10.1, 10.4)], 10.4, 10.1)]
    w = LL.walk(row, FILL, days)
    assert (w["exit"], w["state"], w["sessions"], w["through_date"]) == (None, "open", 2, D2.isoformat())
    assert w["r_now"] == pytest.approx(0.8)
    w2 = LL.walk(row, FILL, [day(D3, [bar(D3, 10, 0, 10.4, 10.5, 10.3, 10.0)], 10.0, 10.2)], prior=w)
    assert w2["exit"] == "ema9_close" and w2["sessions"] == 3


def test_NEGATIVE_a_day_without_daily_numbers_is_never_a_held_session():
    w = LL.walk(row_for(alert_doc()), FILL, [day(D, [bar(D, 10, 6, 10, 10.3, 9.9, 10.2)])])
    assert w["sessions"] == 0 and w["through_date"] is None and w["exit"] is None


# ── grade_step: the C2 / C9 pins and the caps ────────────────────────────────────────────────────────────────────
def _filled_day_bars(d, low=9.9, close=10.2):
    return merge(flat(d, (9, 30), (10, 5), 9.95), [bar(d, 10, 6, 10.0, 10.3, low, close)],
                 flat(d, (10, 7), (15, 59), close))


def test_grade_step_grades_from_its_own_post_close_fetch(cache):
    st = make_store([alert_doc()])
    fetch = Fetch(daily_frame({D: 10.2}))
    now = et(D, 20, 0)
    out = LL.grade_step(st, now, load_day=Loader({D: _filled_day_bars(D)}), fetch_daily=fetch, clock=lambda: 0.0)
    assert out["extended"] == 1 and out["written"] == 1 and fetch.calls == ["ABC"]
    assert out["loads"] == {"daily": 1, "minute": 1} and out["open"] == 1
    doc = st.coll(GS.LEDGER).find_one({"_id": "2026-11-02|ABC|pullback_reversal|aplus"})
    assert doc["fill"]["fill_px"] == pytest.approx(10.0) and doc["walk"]["sessions"] == 1
    assert doc["graded_from"]["daily_cached_at"] == pytest.approx(_epoch(now))       # the fetch time
    assert doc["version"] == LC.LUK_GRADE_VERSION and doc["kind"] == "aplus"
    assert cache.reads == []


def test_NEGATIVE_a_closed_day_whose_fetch_brings_no_frame_defers_daily_then_retries(cache):
    st = make_store([alert_doc()])
    first = Fetch(None)
    out = LL.grade_step(st, et(D, 20, 0), load_day=Loader({D: _filled_day_bars(D)}), fetch_daily=first,
                        clock=lambda: 0.0)
    assert out["deferred_daily"] == 1 and out["deferred"] == 1 and out["extended"] == 0
    assert out["not_settled"] == 0 and out["deferred_cap"] == 0
    assert first.calls == ["ABC"] and out["loads"] == {"daily": 1, "minute": 1}
    doc = st.coll(GS.LEDGER).find_one({"_id": "2026-11-02|ABC|pullback_reversal|aplus"})
    assert doc["fill"]["entry"] == "filled" and doc["walk"] is None      # the fill only — never a half-session close
    assert LL.cells(row_for(alert_doc()), doc)["exit_text"] == LL.PENDING_TEXT
    # retried, never frozen: the next pass with a fresh fetch grades it
    fetch = Fetch(daily_frame({D: 10.2}))
    out2 = LL.grade_step(st, et(D, 20, 5), load_day=Loader({D: _filled_day_bars(D)}), fetch_daily=fetch,
                         clock=lambda: 0.0)
    assert out2["extended"] == 1 and fetch.calls == ["ABC"] and out2["loads"]["daily"] == 1


def test_a_name_off_the_shortlist_is_graded_after_one_counted_force_fetch(cache):
    st = make_store([alert_doc(sym="OFF")])
    fetch = Fetch(daily_frame({D: 10.2}))
    out = LL.grade_step(st, et(D, 20, 0), load_day=Loader({D: _filled_day_bars(D)}), fetch_daily=fetch,
                        clock=lambda: 0.0)
    assert fetch.calls == ["OFF"] and out["loads"] == {"daily": 1, "minute": 1} and out["extended"] == 1


def test_NEGATIVE_the_cap_refuses_then_a_later_call_grades(cache):
    st = make_store([alert_doc(sym="OFF")])
    fetch = Fetch(daily_frame({D: 10.2}))
    out = LL.grade_step(st, et(D, 20, 0), load_day=Loader({D: _filled_day_bars(D)}), fetch_daily=fetch,
                        max_loads=1, clock=lambda: 0.0)
    assert out["deferred_cap"] == 1 and out["deferred"] == 1 and out["extended"] == 0 and fetch.calls == []
    assert out["loads"]["minute"] + out["loads"]["daily"] <= 1
    out2 = LL.grade_step(st, et(D, 20, 5), load_day=Loader({D: _filled_day_bars(D)}), fetch_daily=fetch,
                         max_loads=2, clock=lambda: 0.0)
    assert out2["extended"] == 1 and out2["deferred"] == 0 and fetch.calls == ["OFF"]


def test_NEGATIVE_the_minute_cap_defers_before_any_load(cache):
    st = make_store([alert_doc()])
    load = Loader({D: _filled_day_bars(D)})
    out = LL.grade_step(st, et(D, 20, 0), load_day=load, fetch_daily=Fetch(), max_loads=0, clock=lambda: 0.0)
    assert out["deferred_cap"] == 1 and load.calls == []


def test_NEGATIVE_a_missing_daily_bar_defers_never_a_grade(cache):
    st = make_store([alert_doc()])
    fetch = Fetch(daily_frame({PRE: 10.0}))                  # the fetch answers, but holds no bar dated D
    out = LL.grade_step(st, et(D, 20, 0), load_day=Loader({D: _filled_day_bars(D)}), fetch_daily=fetch,
                        clock=lambda: 0.0)
    assert out["deferred_daily"] == 1 and out["extended"] == 0
    assert out["deferred_text"] == LL.DEFERRED_TEXT == "not graded yet — Luk's own post-close fetch brought no daily bar"


def test_NEGATIVE_the_deferred_sentence_never_blames_the_house_cache():
    """REFIX 2026-11-01: the house cache is never read for a close, so the served sentence must not name it."""
    assert "cache" not in LL.DEFERRED_TEXT.lower()
    assert LL.DEFERRED_TEXT.startswith(LL.PENDING_TEXT) and "post-close fetch" in LL.DEFERRED_TEXT


def test_NEGATIVE_the_budget_defers_and_is_counted(cache):
    st = make_store([alert_doc(sym="AAA"), alert_doc(sym="BBB")])
    ticks = iter([0.0, 999.0, 999.0, 999.0, 999.0])
    out = LL.grade_step(st, et(D, 20, 0), load_day=Loader({D: _filled_day_bars(D)}), fetch_daily=Fetch(),
                        budget_sec=30, clock=lambda: next(ticks))
    assert out["deferred_budget"] == 2 and out["extended"] == 0 and out["written"] == 0


def test_a_stop_on_the_fill_day_needs_no_daily_bar(cache):
    st = make_store([alert_doc()])
    fetch = Fetch()
    bars = merge(_filled_day_bars(D), [bar(D, 11, 0, 9.8, 9.8, 9.4, 9.5)])
    out = LL.grade_step(st, et(D, 20, 0), load_day=Loader({D: bars}), fetch_daily=fetch, clock=lambda: 0.0)
    assert out["extended"] == 1 and fetch.calls == [] and out["loads"]["daily"] == 0
    doc = st.coll(GS.LEDGER).find_one({})
    assert doc["walk"]["exit"] == "stop" and doc["walk"]["r"] == -1.0
    out2 = LL.grade_step(st, et(D2, 20, 0), load_day=Loader({}), fetch_daily=fetch, clock=lambda: 0.0)
    assert out2["final"] == 1 and out2["loads"] == {"daily": 0, "minute": 0}


def test_no_entry_is_final_and_never_reloaded(cache):
    st = make_store([alert_doc()])
    load = Loader({D: flat(D, (9, 30), (15, 59), 9.8)})
    out = LL.grade_step(st, et(D, 20, 0), load_day=load, fetch_daily=Fetch(), clock=lambda: 0.0)
    assert out["no_entry"] == 1 and st.coll(GS.LEDGER).find_one({})["fill"] == {"entry": "no_entry"}
    out2 = LL.grade_step(st, et(D2, 20, 0), load_day=load, fetch_daily=Fetch(), clock=lambda: 0.0)
    assert out2["final"] == 1 and len(load.calls) == 1


def test_NEGATIVE_a_session_not_closed_plus_settle_is_not_due(cache):
    st = make_store([alert_doc()])
    load = Loader({D: _filled_day_bars(D)})
    out = LL.grade_step(st, et(D, 16, 0, 29), load_day=load, fetch_daily=Fetch(), clock=lambda: 0.0)
    assert out["not_due"] == 1 and load.calls == []


def test_NEGATIVE_a_provider_failure_or_an_empty_day_defers(cache):
    st = make_store([alert_doc()])
    out = LL.grade_step(st, et(D, 20, 0), load_day=lambda s, d: (None, True), fetch_daily=Fetch(),
                        clock=lambda: 0.0)
    assert out["load_failed"] == 1 and out["written"] == 0
    out2 = LL.grade_step(st, et(D, 20, 0), load_day=lambda s, d: ([], False), fetch_daily=Fetch(),
                         clock=lambda: 0.0)
    assert out2["no_bars"] == 1 and out2["written"] == 0


def test_the_walk_extends_across_sessions_to_the_9_ema_exit(cache):
    st = make_store([alert_doc()])
    bars = {D: _filled_day_bars(D, close=10.5), D2: flat(D2, (9, 30), (15, 59), 10.6),
            D3: flat(D3, (9, 30), (15, 59), 9.9)}
    fetch = Fetch(daily_frame({D: 10.5, D2: 10.6, D3: 9.9}))
    now = et(D3, 20, 0)
    out = LL.grade_step(st, now, load_day=Loader(bars), fetch_daily=fetch, clock=lambda: 0.0)
    # no stop printed → one own fetch per session the walk needed a daily close for (D, D2, D3)
    assert out["extended"] == 3 and out["loads"] == {"daily": 3, "minute": 3}
    assert fetch.calls == ["ABC", "ABC", "ABC"] and cache.reads == []
    doc = st.coll(GS.LEDGER).find_one({})
    w = doc["walk"]
    assert (w["exit"], w["sessions"], w["exit_date"]) == ("ema9_close", 3, D3.isoformat())
    assert w["r"] == pytest.approx(-0.2)
    assert doc["graded_from"] == {"daily_cached_at": pytest.approx(_epoch(now)), "date": D3.isoformat()}


def test_NEGATIVE_dry_writes_nothing(cache):
    st = make_store([alert_doc()])
    fetch = Fetch(daily_frame({D: 10.2}))
    out = LL.grade_step(st, et(D, 20, 0), load_day=Loader({D: _filled_day_bars(D)}), fetch_daily=fetch,
                        clock=lambda: 0.0, dry=True)
    assert out["extended"] == 1 and out["written"] == 0 and st.coll(GS.LEDGER).writes == 0
    assert out["loads"] == {"daily": 1, "minute": 1} and fetch.calls == ["ABC"]


def test_NEGATIVE_the_writer_refuses_a_key_outside_its_shape():
    st = make_store()
    assert LL._write(st, "x", {"date": "2026-11-02", "same": {}}) is False
    assert st.coll(GS.LEDGER).writes == 0
    assert LL._write(st, "x", {"date": "2026-11-02", "fill": {"entry": "no_entry"}}) is True


def test_NEGATIVE_a_read_fault_is_reported_never_graded(cache):
    out = LL.grade_step(make_store([alert_doc()], fail_alerts=True), et(D, 20, 0), load_day=Loader({}),
                        fetch_daily=Fetch(), clock=lambda: 0.0)
    assert out["read_fault"] is True and out["written"] == 0


# ── served_block ─────────────────────────────────────────────────────────────────────────────────────────────────
def _ledger_doc(doc, f, w):
    r = row_for(doc)
    return {"_id": r["id"], "date": r["date"], "symbol": r["symbol"], "setup": r["setup"], "kind": "aplus",
            "alert": {}, "fill": f, "walk": w, "version": LC.LUK_GRADE_VERSION}


def _walk(**kw):
    w = LL._blank_walk()
    w.update(kw)
    return w


def _served_fixture():
    a1, a2, a3, a4 = (alert_doc(sym="STP"), alert_doc(sym="EMA", setup="inside_day_pdh"),
                      alert_doc(sym="OPN", setup="opening_range_high"), alert_doc(sym="NOE"))
    fill1 = dict(FILL, fill_px=12.41, fill_t=et(D, 9, 47).isoformat())
    led = [_ledger_doc(a1, fill1, _walk(exit="stop", state="stopped", exit_t=et(D, 10, 12).isoformat(), r=-1.0,
                                        sessions=1)),
           _ledger_doc(a2, FILL, _walk(exit="ema9_close", state="ema9_close", exit_date=D4.isoformat(), r=2.3,
                                       sessions=3, reached_3r=True)),
           _ledger_doc(a3, FILL, _walk(r_now=0.8, sessions=2, through_date=D2.isoformat())),
           _ledger_doc(a4, {"entry": "no_entry"}, None)]
    return make_store([a1, a2, a3, a4, alert_doc(sym="OLD", d=PRE)], led)


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)


def test_served_block_words_counts_and_row_texts():
    b = LL.served_block(_served_fixture(), D4, et(D4, 20, 0), span="5d")
    assert b["title"] == ("🏁 Track record — every 🥇 A+ recorded here since 2026-11-01, graded by Luk's trade math · "
                          "UNMEASURED")
    assert "at least 30 s after the alert" in b["rule_text"] and "partials at 3R and 5R" in b["rule_text"]
    assert ("The alert itself can print up to 5 minutes after his bar closed (one Luk pass per 5 minutes), so a 🏁 "
            "fill is later than his would have been — a fact (HIS CALL #29).") in b["rule_text"]
    assert b["honesty"].endswith("UNMEASURED until the strategy lab's 30-entry-week floor (1 entry weeks so far).")
    c = b["counts"]
    assert (c["n"], c["filled"], c["no_entry"], c["stopped"], c["ema9_exits"], c["open"]) == (4, 3, 1, 1, 1, 1)
    assert (c["closed_positive"], c["closed_negative"], c["reached_3r"], c["reached_5r"]) == (1, 1, 1, 0)
    assert c["mean_r_closed"] == pytest.approx(0.65) and c["entry_weeks"] == 1
    assert b["counts_text"] == ("4 A+ recorded · 3 filled · 1 stopped · 1 closed below the 9 EMA · 1 open · mean "
                                "+0.65R over 2 closed · 1 of 30 entry weeks")
    rows = {r["symbol"]: r for dd in b["days"] for r in dd["rows"]}
    assert "OLD" not in rows                                 # NEGATIVE: before the record start
    assert rows["STP"]["fill_text"] == "filled 12.41 at 09:47"
    assert rows["STP"]["exit_text"] == "stopped 10:12 · −1.0R"
    assert rows["EMA"]["exit_text"] == "closed below the 9 EMA on 11-05 · +2.3R · 3 sessions"
    assert rows["EMA"]["flags_text"] == "+3R reached"
    assert rows["OPN"]["exit_text"] == "open · +0.8R after 2 sessions" and rows["OPN"]["flags_text"] == ""
    assert rows["NOE"]["state"] == "no_entry" and rows["NOE"]["exit_text"] == ""
    assert rows["STP"]["plan_text"] == "trigger 10.00 · stop 9.50 (−5.0%) · R $0.50"
    assert rows["STP"]["rang_text"] == "recorded 10:00 ET (regular session) — shadow, never sent"
    assert b["n_rows"] == 4 and b["days"][0]["label"] == "Mon 11-02"


def test_every_number_in_the_rule_and_counts_text_is_a_constant_value():
    b = LL.served_block(_served_fixture(), D4, et(D4, 20, 0), span="5d")
    allowed = {"30", "3", "5", "9", "1", "11", "29", "2", "17"}     # settle · partials · EMA · cite ts · HIS CALL ids
    nums = set(re.findall(r"\d+", b["rule_text"].replace("VKNEJA5r8zw", "")))   # the video id is a name
    assert nums <= allowed, nums - allowed
    from chart_maps.gajjala import constants as GC
    assert str(GC.BAR_SETTLE_SEC) in nums and {str(m) for m in LC.LUK_PARTIAL_R} <= nums
    assert str(LC.LUK_PULLBACK_DAILY_EMA) in nums
    assert f"of {LC.MEASURE_FLOOR_WEEKS} entry weeks" in b["counts_text"]


def test_NEGATIVE_no_b_word_and_no_edge_anywhere_served():
    b = LL.served_block(_served_fixture(), D4, et(D4, 20, 0), span="all")
    for s in _strings(b):
        assert not B_WORD.search(s) and not EDGE.search(s), s


def test_span_defaults_and_today_narrows():
    st = _served_fixture()
    assert LL.served_block(st, D4, et(D4, 20, 0), span="junk")["span"] == LC.LUK_LEDGER_SPAN_DEFAULT
    assert LL.served_block(st, D4, et(D4, 20, 0), span="today")["n_rows"] == 0
    b = LL.served_block(st, D4, et(D4, 20, 0), span="today")
    assert b["counts"]["entry_weeks"] == 1                   # the floor counts the WHOLE record, never the span
    assert b["spans"] == list(LC.LUK_LEDGER_SPANS)


def test_NEGATIVE_a_read_fault_serves_the_fault_not_an_empty_record():
    b = LL.served_block(make_store([alert_doc()], fail_alerts=True), D, et(D, 20, 0))
    assert b["fault"] is True and b["fault_text"] and b["days"] == []


def test_mean_text_without_a_closed_row():
    b = LL.served_block(make_store([alert_doc()]), D, et(D, 12, 0), span="today")
    assert b["counts"]["mean_r_closed"] is None and "no closed row yet" in b["counts_text"]
    row = b["days"][0]["rows"][0]
    assert row["state"] == "pending" and row["fill_text"] == "not graded yet"


def test_NEGATIVE_the_package_imports_only_the_allowed_gajjala_ledger_names():
    import ast
    import inspect
    allowed = {"bars_from_frame", "_default_load_day", "_today_load", "plan_of", "rang_of", "_D", "_num", "_aware",
               "_iso_t", "_px", "_pct", "SETTLE", "ONE_MIN", "ET", "UTC"}
    from chart_maps.luk import tape as LT
    for mod in (LL, LT):
        tree = ast.parse(inspect.getsource(mod))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "chart_maps.gajjala.ledger":
                assert {a.name for a in node.names} <= allowed
            if isinstance(node, ast.ImportFrom) and node.module == "chart_maps.gajjala":
                assert "ledger" not in {a.name for a in node.names}


# ── REFIX 2026-11-01: closed days come ONLY from Luk's own post-close fetch ──────────────────────────────────────────
HALF = date(2026, 11, 27)                      # Fri after Thanksgiving — the regular session closes 13:00 ET


def test_step_keys_carry_not_settled_and_never_untrusted():
    assert "not_settled" in LL.STEP_KEYS and "untrusted" not in LL.STEP_KEYS
    assert LL.STEP_KEYS == ("rows", "final", "extended", "written", "not_due", "no_time", "no_entry", "deferred",
                            "deferred_cap", "deferred_budget", "deferred_daily", "not_settled", "load_failed",
                            "no_bars", "faulted")
    out = LL.grade_step(make_store(), et(D, 20, 0), load_day=Loader({}), fetch_daily=Fetch(), clock=lambda: 0.0)
    assert "untrusted" not in out and out["not_settled"] == 0


def test_NEGATIVE_ledger_source_never_names_the_house_cache_readers():
    import inspect
    text = inspect.getsource(LL)
    for name in ("cached_frame_meta", "closed_daily_frame", "_mongo_get", "_cache_untrusted"):
        assert name not in text, name


def test_NEGATIVE_before_1600_30_on_a_full_day_the_due_rule_catches_it_first_not_due(cache):
    st = make_store([alert_doc()])
    load, fetch = Loader({D: _filled_day_bars(D)}), Fetch(daily_frame({D: 10.2}))
    out = LL.grade_step(st, et(D, 16, 0, 29), load_day=load, fetch_daily=fetch, clock=lambda: 0.0)
    assert out["not_due"] == 1 and out["not_settled"] == 0 and out["deferred"] == 0 and out["extended"] == 0
    assert load.calls == [] and fetch.calls == [] and out["loads"] == {"daily": 0, "minute": 0}
    assert st.coll(GS.LEDGER).writes == 0


def test_NEGATIVE_a_half_day_after_its_1300_close_but_before_1600_30_is_not_settled_no_fetch(cache):
    assert LL.close_utc(HALF) == et(HALF, 13, 0)           # the due rule is due at 13:00:30 ET on this day
    st = make_store([alert_doc(d=HALF, at=et(HALF, 10, 0, 15))])
    fetch = Fetch(daily_frame({HALF: 10.2}))
    bars = merge(flat(HALF, (9, 30), (10, 5), 9.95), [bar(HALF, 10, 6, 10.0, 10.3, 9.9, 10.2)],
                 flat(HALF, (10, 7), (12, 59), 10.2))
    out = LL.grade_step(st, et(HALF, 14, 0), load_day=Loader({HALF: bars}), fetch_daily=fetch, clock=lambda: 0.0)
    assert out["not_settled"] == 1 and out["deferred"] == 1 and out["deferred_daily"] == 0
    assert out["extended"] == 0 and fetch.calls == [] and out["loads"] == {"daily": 0, "minute": 1}
    doc = st.coll(GS.LEDGER).find_one({})
    assert doc["fill"]["entry"] == "filled" and doc["walk"] is None      # the fill only — never a half-session close
    # past 16:00:30 ET the same day: one own fetch grades it
    out2 = LL.grade_step(st, et(HALF, 16, 0, 31), load_day=Loader({HALF: bars}), fetch_daily=fetch,
                         clock=lambda: 0.0)
    assert out2["extended"] == 1 and out2["not_settled"] == 0 and fetch.calls == ["ABC"]


def _grade_pair(cache, fetch_frame, cache_row):
    """The same pass on two fresh stores: without, then with `cache["ABC"]` set. -> ((out, doc), (out, doc))."""
    res = []
    for with_cache in (False, True):
        cache.clear()
        if with_cache:
            cache["ABC"] = cache_row
        st = make_store([alert_doc()])
        fetch = Fetch(fetch_frame)
        out = LL.grade_step(st, et(D, 20, 0), load_day=Loader({D: _filled_day_bars(D)}), fetch_daily=fetch,
                            clock=lambda: 0.0)
        doc = st.coll(GS.LEDGER).find_one({})
        res.append((out, doc, list(fetch.calls)))
    return res


@pytest.mark.parametrize("cache_row", [
    {"frame": daily_frame({D: 11.0}), "cached_at": cached_at(D, 16, 0, 30)},   # a "trusted" stamp, other close
    {"frame": daily_frame({D: 9.0}), "cached_at": cached_at(D, 15, 0)},        # a half-session stamp
])
@pytest.mark.parametrize("fetch_frame", [None, "frame"])
def test_NEGATIVE_the_house_cache_being_set_changes_nothing(cache, cache_row, fetch_frame):
    frame = daily_frame({D: 10.2}) if fetch_frame == "frame" else None
    (o1, d1, c1), (o2, d2, c2) = _grade_pair(cache, frame, cache_row)
    assert o1 == o2 and d1 == d2 and c1 == c2 == ["ABC"]
    assert cache.reads == []
    if frame is None:
        assert o2["deferred_daily"] == 1 and o2["extended"] == 0 and d2["walk"] is None
    else:
        assert o2["extended"] == 1 and d2["walk"]["r_now"] == pytest.approx((10.2 - 10.0) / 0.5)
