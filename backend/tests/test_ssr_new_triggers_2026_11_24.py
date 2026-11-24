"""⛔ SSR — the names NEW on one trigger day: `ssr.new_triggers` + `ssr_lists.symbols_on` (W1 be-engine, 2026-11-24).

Ajay 2026-11-24, in order: "What are the SSR stocks today" · "Can you add it to short interest tab" · "The new ones".
Spec: scratchpad ssrlist/spec.md §3.1, §3.2, W1 tests 1–25. Every name is SYNTHETIC ("ZZ…") unless it comes from the
VERBATIM exchange files under tests/fixtures/ssr/ (stored through the module's own `refresh_one` via `hold`).

The fakes are the ssr-core ones, by import. TRAP (spec §1.1): a bare `FakeCorp()` answers None for every day = the
dividends / splits are UNREAD — a "read" corp day is `acts={iso: {}}`.
"""
from __future__ import annotations

import inspect
import json
import math
from datetime import date, datetime
from pathlib import Path

import pytest

from short_interest import reg_sho as RS
from short_interest import ssr as SSR
from short_interest import ssr_lists as SL
from tests.test_ssr_lists_2026_11_24 import ANSWERS, StandIn, hold
from tests.test_ssr_rule_201_2026_11_24 import (FORBIDDEN, FakeColl, FakeCorp, FakeDB, FakeLists, day as day_doc,
                                                 et, nasdaq_row, nyse_row, trig)

D19, D20, D21 = date(2026, 11, 19), date(2026, 11, 20), date(2026, 11, 21)
D23, D24, D25 = date(2026, 11, 23), date(2026, 11, 24), date(2026, 11, 25)
NOW = et(D24, 15, 0)
GT = (SSR.GLYPH, SSR.TAG)

CLEAN_VIEWS = [
    {"key": "nasdaq", "exchange": "Nasdaq", "ok": True, "status": "ok", "as_of": "2026-11-24", "edition_et": "04:15",
     "final": False, "n": 333, "error": None,
     "text": "Nasdaq short sale list for 11/24 · edition 04:15 ET · 333 rows (today's triggers not in it yet)"},
    {"key": "nyse", "exchange": "NYSE Group", "ok": True, "status": "ok", "as_of": "2026-11-23", "edition_et": None,
     "final": True, "n": 114, "error": None,
     "text": "NYSE Group short sale list for 11/24 not published yet (after 20:10 ET)"}]
CORP_TEXT = "dividends and splits read for 11/24 · 2 names"


class Lists(FakeLists):
    """FakeLists + the new enumerator + a recorder of the clock `load` / `source_views` receive."""

    def __init__(self, rows=(), complete=(), due=False, views=None):
        super().__init__(rows=rows, complete=complete, due=due, views=views if views is not None else CLEAN_VIEWS)
        self.loads = []
        self.view_clocks = []

    def load(self, coll, now_et):
        self.loads.append(now_et)
        return {"fake": True}

    def symbols_on(self, loaded, T):
        return sorted({r["_sym"] for r in self.rows if r["trigger_date"] == T.isoformat()})

    def source_views(self, loaded, now_et):
        self.view_clocks.append(now_et)
        return super().source_views(loaded, now_et)


class Corp(FakeCorp):
    def __init__(self, acts=None, due=False, load_raises=False):
        super().__init__(acts=acts, due=due)
        self.load_raises = load_raises

    def load(self, coll, days):
        if self.load_raises:
            raise RuntimeError("synthetic: corp store fails")
        return {"fake": True}

    def source_view(self, loaded, days, now_et):
        return {"key": "corp_actions", "exchange": None, "ok": True, "status": "ok", "as_of": "2026-11-24", "n": 2,
                "error": None, "text": CORP_TEXT}


def read_corp(D=D24, **extra):
    """A READ corp day for D and its prior market day (no action unless given)."""
    from catalysts.medical.reaction import prev_market_day
    acts = {D.isoformat(): {}, prev_market_day(D).isoformat(): {}}
    for k, v in extra.items():
        acts[k] = v
    return Corp(acts=acts)


def run(docs=(), now=NOW, lists=None, corp=None, D=D24, coll=None):
    coll = coll if coll is not None else FakeColl(docs)
    lists = lists if lists is not None else Lists()
    corp = corp if corp is not None else read_corp(D)
    SSR._reset_cache()
    return SSR.new_triggers(D, db=FakeDB(coll), now=now, lists=lists, corp=corp)


def by_sym(out):
    return {r["symbol"]: r for r in out["rows"]}


def fresh_day(T=D24, at=None):
    return day_doc(T, at or et(T, 14, 58))


def snap_doc(T, sym, seen="10:05", drop=-20.0, **kw):
    return trig(T, sym, "snapshot", at=None, seen_at=seen, low=4.0, drop_pct=drop, prev_close=5.0, **kw)


def served_texts(obj):
    """Every served string (the row dicts, sources, computed row included)."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("kind", "status", "day", "prior_day", "through", "off_from", "source", "time_basis", "key"):
                continue
            yield from served_texts(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from served_texts(v)


@pytest.fixture(autouse=True)
def _clean():
    SSR._reset_cache()
    SL._reset_cache()
    yield
    SSR._reset_cache()
    SL._reset_cache()


# ═════════════════════════════════════════════ 1–4 the rows
def test_01_rth_minute_and_snapshot_docs_two_rows_with_their_words():
    docs = [trig(D24, "ZZM", "minute_bar", at="10:00", low=2.5, drop_pct=-12.4, prev_close=2.85),
            snap_doc(D24, "ZZS"), fresh_day()]
    out = run(docs)
    assert out["status"] == "ok" and out["kind"] == SSR.NEW_KIND == "ssr_new_triggers"
    rows = by_sym(out)
    assert list(rows) == ["ZZM", "ZZS"]
    assert rows["ZZM"]["at_text"] == "10:00 ET" and rows["ZZM"]["time_basis"] == "minute_bar"
    assert rows["ZZM"]["drop_pct"] == -12.4 and rows["ZZM"]["drop_text"] == "-12.4%"
    assert rows["ZZS"]["at_text"] == "by 10:05 ET" and rows["ZZS"]["time_basis"] == "first_seen"
    for r in rows.values():
        assert r["source_text"] == "computed" and r["source"] == "computed" and r["retriggered"] is False
        assert r["mark_text"] is None and r["exchange"] is None
    assert out["title"] == "⛔ SSR — new today (Tue 11/24)" and out["is_today"] is True
    assert out["window_text"] == "Each is in force through Wed 11/25, after-hours included; off from Fri 11/27."
    assert out["through"] == "2026-11-25" and out["off_from"] == "2026-11-27" and out["half_day"] is False
    live = SSR.COMPUTED_TEXT_LIVE % ("Tue 11/24", "14:58")
    assert out["asof_text"] == "; ".join([live] + [v["text"] for v in CLEAN_VIEWS] + [CORP_TEXT])
    assert out["partial_text"] is None and out["corp_checked"] is True
    assert out["n"] == 2 and out["n_computed"] == 2 and out["n_official"] == 0 and out["n_retriggered"] == 0
    assert out["sources_text"] == "0 on an exchange list · 2 computed here" and out["retriggered_text"] is None
    assert out["empty_text"] is None and out["fault_text"] is None and out["status_text"] is None
    assert out["prior_day"] == "2026-11-23" and out["withheld"] == {r: [] for r in SSR.NEW_WITHHELD}


def test_02_an_exchange_row_prints_the_list_and_its_time_and_the_doc_drop():
    lists = Lists(rows=[nasdaq_row("ZZN", "2026-11-24", "09:45:36", stamp="20261124163004"),
                        nasdaq_row("ZZO", "2026-11-24", "11:02:10", stamp="20261124163004")])
    out = run([snap_doc(D24, "ZZN", drop=-13.0), fresh_day()], lists=lists)
    rows = by_sym(out)
    assert rows["ZZN"]["source_text"] == "Nasdaq list" and rows["ZZN"]["source"] == "official"
    assert rows["ZZN"]["exchange"] == "Nasdaq" and rows["ZZN"]["at_text"] == "09:45:36 ET"
    assert rows["ZZN"]["time_basis"] == "exchange" and rows["ZZN"]["drop_text"] == "-13.0%"
    assert out["n_official"] == 2 and out["n_computed"] == 0
    assert out["sources_text"] == "2 on an exchange list · 0 computed here"


def test_02_NEGATIVE_an_exchange_row_without_a_doc_has_no_drop():
    lists = Lists(rows=[nasdaq_row("ZZO", "2026-11-24", "11:02:10")])
    r = by_sym(run([fresh_day()], lists=lists))["ZZO"]
    assert r["drop_pct"] is None and r["drop_text"] is None and r["at_text"] == "11:02:10 ET"


def test_03_a_list_only_name_is_listed():
    lists = Lists(rows=[nyse_row("ZZL", "2026-11-24", "13:01:02", exchange="NYSE Arca")])
    r = by_sym(run([fresh_day()], lists=lists))["ZZL"]
    assert r["source_text"] == "NYSE Arca list" and r["at_et"] == "13:01:02"


def test_03_NEGATIVE_one_name_in_two_spellings_is_ONE_row():
    lists = Lists(rows=[nasdaq_row("ZZB.WS", "2026-11-24", "10:00:00"), nasdaq_row("ZZB-WS", "2026-11-24", "10:00:01")])
    out = run([snap_doc(D24, "ZZB.WS"), fresh_day()], lists=lists)
    assert [r["symbol"] for r in out["rows"]] == ["ZZB.WS"]
    assert out["n"] == 1 and out["faults"] == []


def test_04_NEGATIVE_a_name_triggered_only_on_the_prior_day_is_not_listed():
    lists = Lists(rows=[nasdaq_row("ZZP", "2026-11-23", "09:40:00", file_date="2026-11-24")])
    out = run([snap_doc(D23, "ZZP"), fresh_day()], lists=lists)
    assert out["rows"] == [] and out["faults"] == [] and all(v == [] for v in out["withheld"].values())
    assert out["empty_text"] == SSR.NEW_EMPTY_TEXT % ("Tue 11/24", SSR.COMPUTED_TEXT_LIVE % ("Tue 11/24", "14:58"))


# ═════════════════════════════════════════════ 5 triggered again [C1]
def test_05_on_the_prior_day_and_today_is_marked_with_the_prior_market_day():
    lists = Lists(rows=[nasdaq_row("ZZR", "2026-11-23", "09:31:00", file_date="2026-11-24")])
    out = run([snap_doc(D24, "ZZR", seen="11:00"), fresh_day()], lists=lists)
    r = by_sym(out)["ZZR"]
    assert r["retriggered"] is True and r["mark_text"] == "also triggered Mon 11/23"
    assert r["source"] == "computed" and r["at_text"] == "by 11:00 ET"   # governed by the NEWEST on-day
    assert out["prior_day"] == "2026-11-23" and out["n_retriggered"] == 1
    assert out["retriggered_text"] == "1 were already restricted and triggered again"


def _c1_fixture():
    """ZZA official on P + computed D → marked. ZZC a P doc on P's dividend day → P off → NOT marked. ZZE a P doc
    with P's lists complete and no row → P overruled → NOT marked."""
    lists = Lists(rows=[nasdaq_row("ZZA", "2026-11-23", "09:31:00", file_date="2026-11-24")], complete={D23})
    corp = Corp(acts={"2026-11-24": {}, "2026-11-23": {"ZZC": "dividend"}})
    docs = [snap_doc(D23, "ZZC"), snap_doc(D23, "ZZE"), snap_doc(D24, "ZZA"), snap_doc(D24, "ZZC"),
            snap_doc(D24, "ZZE"), day_doc(D24, et(D24, 14, 59), final=True)]
    return docs, lists, corp


def _marks(out):
    return ([(r["symbol"], r["retriggered"], r["mark_text"]) for r in out["rows"]], out["n_retriggered"],
            out["retriggered_text"])


@pytest.mark.parametrize("now", [et(D24, 15, 0), et(D24, 19, 59), et(D24, 20, 1), et(D24, 23, 30), et(D25, 0, 30)])
def test_05a_NEGATIVE_the_marks_never_change_with_the_clock(now):
    docs, lists, corp = _c1_fixture()
    base = _marks(run(docs, now=et(D24, 15, 0), lists=lists, corp=corp))
    assert base[0] == [("ZZA", True, "also triggered Mon 11/23"), ("ZZC", False, None), ("ZZE", False, None)]
    assert base[1] == 1
    docs, lists, corp = _c1_fixture()
    out = run(docs, now=now, lists=lists, corp=corp)
    assert out["status"] == "ok" and _marks(out) == base and out["prior_day"] == "2026-11-23"


def test_05a_at_2001_the_prior_day_has_left_in_play_yet_the_mark_stands():
    assert D23 not in SSR.in_play(et(D24, 20, 1))                # the rev 1 rule would have printed 0 here
    docs, lists, corp = _c1_fixture()
    out = run(docs, now=et(D24, 20, 1), lists=lists, corp=corp)
    assert out["n_retriggered"] == 1 and by_sym(out)["ZZA"]["mark_text"] == "also triggered Mon 11/23"


@pytest.mark.parametrize("now", [et(D20, 15, 0), et(D21, 12, 0)])
def test_05a_NEGATIVE_a_friday_list_read_on_saturday_keeps_its_marks(now):
    lists = Lists(rows=[nasdaq_row("ZZA", "2026-11-19", "09:31:00", file_date="2026-11-20")])
    docs = [snap_doc(D20, "ZZA"), snap_doc(D20, "ZZB"), day_doc(D20, et(D20, 16, 5), final=True)]
    out = run(docs, now=now, lists=lists, corp=read_corp(D20), D=D20)
    assert out["status"] == "ok"
    assert _marks(out) == ([("ZZA", True, "also triggered Thu 11/19"), ("ZZB", False, None)], 1,
                           "1 were already restricted and triggered again")


def test_05b_NEGATIVE_triggered_the_day_before_the_prior_day_is_not_marked():
    lists = Lists(rows=[nasdaq_row("ZZG", "2026-11-20", "09:31:00", file_date="2026-11-23")])
    r = by_sym(run([snap_doc(D24, "ZZG"), fresh_day()], lists=lists))["ZZG"]
    assert r["retriggered"] is False and r["mark_text"] is None


def test_05c_NEGATIVE_the_prior_days_own_overrule_holds_and_without_it_the_mark_prints():
    docs = [snap_doc(D23, "ZZH"), snap_doc(D24, "ZZH"), fresh_day()]
    r = by_sym(run(docs, lists=Lists(complete={D23})))["ZZH"]
    assert r["retriggered"] is False and r["mark_text"] is None
    r = by_sym(run(docs, lists=Lists(complete=set())))["ZZH"]
    assert r["retriggered"] is True and r["mark_text"] == "also triggered Mon 11/23"


# ═════════════════════════════════════════════ 6–8 left off
def test_06_NEGATIVE_a_dividend_day_withholds_the_computed_name_and_a_split_keeps_the_official_one():
    corp = read_corp(D24, **{"2026-11-24": {"ZZD": "dividend", "ZZT": "split"}})
    lists = Lists(rows=[nasdaq_row("ZZT", "2026-11-24", "10:10:10")])
    out = run([snap_doc(D24, "ZZD"), snap_doc(D24, "ZZT"), fresh_day()], lists=lists, corp=corp)
    rows = by_sym(out)
    assert "ZZD" not in rows and out["withheld"]["corp_action"] == ["ZZD"]
    assert rows["ZZT"]["source"] == "official" and rows["ZZT"]["drop_text"] is None
    assert out["withheld_text"] == ("Left off this list: ZZD — a dividend or a split took effect on Tue 11/24, so the "
                                    "prior close on file is not the exchange's.")


def test_07_DEFENSIVE_complete_lists_without_the_name_withhold_it_and_the_switch_off_lists_it(monkeypatch):
    out = run([snap_doc(D24, "ZZK"), fresh_day()], lists=Lists(complete={D24}))
    assert out["rows"] == [] and out["withheld"]["computed_only"] == ["ZZK"]
    assert "neither exchange list carries it" in out["withheld_text"]
    monkeypatch.setattr(SSR, "SSR_COMPUTED_UNTIL_LISTS_COMPLETE", False)
    out = run([snap_doc(D24, "ZZK"), fresh_day()], lists=Lists(complete={D24}))
    assert [r["symbol"] for r in out["rows"]] == ["ZZK"] and out["withheld"]["computed_only"] == []


# real stored lists: Nasdaq file(P), Nasdaq file(D), a PLANTED Nasdaq file(next market day), NYSE file(D)
PLANTED_NASDAQ_1124 = {"_id": "list|nasdaq|2026-11-24", "kind": "list", "source": "nasdaq",
                       "file_date": "2026-11-24", "stamp": "20261124041515",
                       "rows": [["ZZPL", "2026-11-23", "10:00:00", "Q"]], "n": 1, "rev": "20261124041515|1"}


def real_coll(*keys, extra=(), docs=()):
    st = hold(StandIn(), *keys)
    return FakeColl(list(st.docs.values()) + list(extra) + list(docs))


@pytest.fixture
def no_outside(monkeypatch):
    calls = []

    def refuse(*a, **k):
        calls.append(("call", a))
        raise RuntimeError("synthetic: no outside call here")

    def no_kick(*a, **k):
        calls.append(("kick", a))
        raise RuntimeError("synthetic: no kick here")
    monkeypatch.setattr(SL, "_http", refuse)
    monkeypatch.setattr(SL, "kick_refresh", no_kick)
    yield calls
    assert calls == []


@pytest.mark.parametrize("now", [et(D23, 9, 31), et(D23, 15, 0), et(D23, 20, 1), et(D24, 0, 30)])
def test_07b_NEGATIVE_the_real_lists_never_withhold_a_computed_name_on_its_own_day(now, no_outside):
    coll = real_coll(("nasdaq", D20), ("nasdaq", D23), ("nyse", D23), extra=[PLANTED_NASDAQ_1124],
                     docs=[snap_doc(D23, "ZZQX"), day_doc(D23, et(D23, 9, 30))])
    SL._reset_cache()
    assert SL.complete_for(SL.load(coll, et(D24, 4, 30)), D23) is True   # the planted file WOULD complete 11/23
    out = run(now=now, lists=SL, corp=read_corp(D23), D=D23, coll=coll)
    assert out["status"] == "ok" and "ZZQX" in by_sym(out)
    assert out["withheld"]["computed_only"] == [] and by_sym(out)["ZZQX"]["source"] == "computed"
    assert coll.writes == []


def test_07b_NEGATIVE_a_friday_name_read_on_saturday_with_the_real_lists(no_outside):
    coll = real_coll(("nasdaq", D20), ("nyse", D20), ("nasdaq", D23), docs=[snap_doc(D20, "ZZQX")])
    SL._reset_cache()
    assert SL.complete_for(SL.load(coll, et(D23, 15, 0)), D20) is True   # Monday's file WOULD complete Friday
    out = run(now=et(D21, 12, 0), lists=SL, corp=read_corp(D20), D=D20, coll=coll)
    assert out["status"] == "ok" and "ZZQX" in by_sym(out) and out["withheld"]["computed_only"] == []


def test_08_NEGATIVE_a_void_doc_is_left_off_as_bars_disagree():
    out = run([snap_doc(D24, "ZZV", void="bars_disagree"), fresh_day()])
    assert out["rows"] == [] and out["withheld"]["bars_disagree"] == ["ZZV"]
    assert "1-minute bars disagree at the %d%% line" % SSR.SSR_TRIGGER_DROP_PCT in out["withheld_text"]


# ═════════════════════════════════════════════ 9–17 status + honesty
def _assert_failed(out):
    assert out["status"] == "failed" and isinstance(out["fault_text"], str) and out["fault_text"]
    assert out["rows"] == [] and out["empty_text"] is None and set(out) == set(SSR.NEW_KEYS)
    assert "A missing list does not mean no name triggered." in out["fault_text"]


def test_09_NEGATIVE_no_db_a_raising_store_unresolvable_lists_an_unreadable_day(monkeypatch):
    out = SSR.new_triggers(D24, db=None, now=NOW, lists=Lists(), corp=read_corp())
    _assert_failed(out)
    assert out["fault_text"] == SSR.NEW_FAULT_TEXT % (GT + ("Tue 11/24",))
    coll = FakeColl([snap_doc(D24, "ZZS")])
    coll.raise_all = True
    _assert_failed(run(coll=coll))
    for bad in ("x", None, 12, "2026-13-45", object()):
        out = SSR.new_triggers(bad, db=FakeDB(FakeColl()), now=NOW, lists=Lists(), corp=read_corp())
        _assert_failed(out)
        assert out["title"] == SSR.NEW_TITLE_BARE % GT and out["day"] is None
    def boom(lists):
        raise ImportError("synthetic: ssr_lists cannot import")
    monkeypatch.setattr(SSR, "_resolve_lists", boom)
    _assert_failed(SSR.new_triggers(D24, db=FakeDB(FakeColl()), now=NOW, corp=read_corp()))


def test_09_NEGATIVE_a_raising_lists_load_is_failed_never_empty():
    class Bad(Lists):
        def load(self, coll, now_et):
            raise RuntimeError("synthetic")
    _assert_failed(run([fresh_day()], lists=Bad()))


def test_10_NEGATIVE_nothing_on_file_is_not_read_never_the_empty_sentence():
    out = run([])
    assert out["status"] == "not_read" and out["rows"] == [] and out["empty_text"] is None
    assert "not run yet" in out["fault_text"] and out["fault_text"].startswith("⛔ SSR — the names new on Tue 11/24")
    assert CLEAN_VIEWS[0]["text"] in out["fault_text"] and out["prior_day"] == "2026-11-23"


def test_11_a_fresh_day_doc_and_no_trig_is_ok_with_the_empty_sentence():
    out = run([fresh_day()])
    assert out["status"] == "ok" and out["rows"] == [] and out["fault_text"] is None
    assert out["empty_text"] == "No name has newly triggered it on Tue 11/24 (%s)." % (
        SSR.COMPUTED_TEXT_LIVE % ("Tue 11/24", "14:58"))
    assert "14:58" in out["empty_text"] and out["n"] == 0 and out["sources_text"] is None


def test_12_NEGATIVE_a_stale_scan_with_rows_is_partial_and_without_rows_not_read():
    stale = day_doc(D24, et(D24, 12, 0))
    out = run([stale, snap_doc(D24, "ZZS")])
    assert out["status"] == "ok" and [r["symbol"] for r in out["rows"]] == ["ZZS"]
    assert out["partial_text"] == SSR.NEW_PARTIAL_TEXT % (SSR.COMPUTED_TEXT_STALE % ("Tue 11/24", "12:00"))
    out = run([stale])
    assert out["status"] == "not_read" and out["empty_text"] is None and "12:00" in out["fault_text"]


def test_12b_NEGATIVE_unread_dividends_and_splits_are_said_on_computed_rows_only():
    note = SSR.CORP_UNREAD_NOTE.strip()
    sentence = SSR.NEW_CORP_UNREAD_TEXT % note
    out = run([fresh_day(), snap_doc(D24, "ZZS")], corp=Corp())
    assert out["status"] == "ok" and out["corp_checked"] is False and out["partial_text"] == sentence
    assert note in out["partial_text"] and CORP_TEXT in out["asof_text"]
    out = run([fresh_day(), snap_doc(D24, "ZZS")], corp=Corp(load_raises=True))
    assert out["corp_checked"] is False and out["partial_text"] == sentence and CORP_TEXT not in out["asof_text"]
    out = run([day_doc(D24, et(D24, 12, 0)), snap_doc(D24, "ZZS")], corp=Corp())
    missing = SSR.NEW_PARTIAL_TEXT % (SSR.COMPUTED_TEXT_STALE % ("Tue 11/24", "12:00"))
    assert out["partial_text"] == missing + " " + sentence
    assert out["partial_text"].index(missing) < out["partial_text"].index(note)
    out = run([fresh_day(), snap_doc(D24, "ZZS")])                    # corp READ
    assert out["corp_checked"] is True and out["partial_text"] is None
    lists = Lists(rows=[nasdaq_row("ZZN", "2026-11-24", "09:45:36")])
    out = run([fresh_day()], lists=lists, corp=Corp())                # exchange rows only
    assert out["n"] == 1 and out["corp_checked"] is False and out["partial_text"] is None
    out = run([fresh_day()], corp=Corp())                             # no rows
    assert out["rows"] == [] and out["partial_text"] is None


def test_13_NEGATIVE_before_the_open_is_pre_open_with_no_rows():
    out = run([snap_doc(D24, "ZZS"), fresh_day()], now=et(D24, 8, 0))
    assert out["status"] == "pre_open" and out["rows"] == []
    assert out["status_text"] == SSR.NEW_PRE_OPEN_TEXT % ("Tue 11/24", SSR._rth_open_dt(D24).strftime("%H:%M"))
    assert SSR._rth_open_dt(D24).strftime("%H:%M") in out["status_text"]
    assert out["empty_text"] is None and out["fault_text"] is None and out["prior_day"] is None
    assert out["corp_checked"] is None


def test_14_saturday_reads_fridays_list_with_the_closed_words():
    docs = [day_doc(D20, et(D20, 16, 5), final=True), snap_doc(D20, "ZZW")]
    out = run(docs, now=et(D21, 12, 0), corp=read_corp(D20), D=D20)
    assert out["status"] == "ok" and out["market_day_today"] is False and out["is_today"] is False
    assert out["title"] == "⛔ SSR — new on Fri 11/20, the last session · the market is closed today"
    assert out["title"].endswith(SSR.NEW_CLOSED_TODAY)
    assert out["computed"]["text"] == SSR.COMPUTED_TEXT_FINAL % ("Fri 11/20", "16:05")


def test_15_after_midnight_the_lists_are_read_as_of_the_list_day_itself():
    lists = Lists()
    out = run([snap_doc(D23, "ZZS"), day_doc(D23, et(D23, 16, 5), final=True)], now=et(D24, 0, 30), lists=lists,
              corp=read_corp(D23), D=D23)
    assert out["status"] == "ok" and out["title"] == "⛔ SSR — new on Mon 11/23, the last session"
    assert SSR.NEW_CLOSED_TODAY not in out["title"]
    assert [c.date() for c in lists.loads] == [D23] and [c.date() for c in lists.view_clocks] == [D23]
    lists = Lists()
    run([snap_doc(D23, "ZZS")], now=et(D23, 15, 0), lists=lists, corp=read_corp(D23), D=D23)
    assert lists.loads == [et(D23, 15, 0)] and lists.view_clocks == [et(D23, 15, 0)]
    lists = Lists()
    run([snap_doc(D20, "ZZS")], now=et(D21, 12, 0), lists=lists, corp=read_corp(D20), D=D20)
    assert [c.date() for c in lists.loads] == [D20]


def test_16_NEGATIVE_an_older_day_is_out_of_play_and_yesterday_is_not_latest():
    out = run([snap_doc(D20, "ZZS")], D=D20)
    assert out["status"] == "out_of_play" and out["rows"] == [] and out["empty_text"] is None
    assert out["status_text"] == SSR.NEW_OUT_OF_PLAY_TEXT % "Fri 11/20"
    out = run([snap_doc(D23, "ZZS")], D=D23)
    assert D23 in SSR.in_play(NOW) and out["status"] == "not_latest" and out["rows"] == []
    assert out["status_text"] == "This list covers the newest trigger day only (Tue 11/24)."
    assert out["fault_text"] is None and out["empty_text"] is None


def test_17_a_wednesday_trigger_runs_through_the_friday_half_day():
    out = run([snap_doc(D25, "ZZS"), day_doc(D25, et(D25, 14, 58))], now=et(D25, 15, 0), corp=read_corp(D25), D=D25)
    w = SSR.window(D25)
    assert out["half_day"] is True and out["through"] == "2026-11-27"
    assert out["window_text"].endswith(SSR.HALF_DAY_TEXT % ("Fri 11/27", w["rth_close"].strftime("%H:%M")))
    assert "Fri 11/27 is a half day" in out["window_text"]


# ═════════════════════════════════════════════ 18–25 shape, words, guards
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "x", None, True])
def test_18_NEGATIVE_a_junk_drop_prints_nothing(bad):
    out = run([snap_doc(D24, "ZZS", drop=bad), fresh_day()])
    r = by_sym(out)["ZZS"]
    assert r["drop_pct"] is None and r["drop_text"] is None
    json.dumps(out, allow_nan=False)


def _every_status(monkeypatch=None):
    lists = Lists(rows=[nasdaq_row("ZZN", "2026-11-24", "09:45:36")])
    outs = [run([snap_doc(D24, "ZZS"), snap_doc(D24, "ZZD"), snap_doc(D24, "ZZV", void="bars_disagree"),
                 fresh_day()], lists=lists, corp=read_corp(D24, **{"2026-11-24": {"ZZD": "dividend"}})),
            run([]), run([snap_doc(D24, "ZZS")], now=et(D24, 8, 0)), run([], D=D23), run([], D=D20),
            SSR.new_triggers(D24, db=None, now=NOW, lists=Lists(), corp=read_corp())]
    return outs


def test_18_every_status_is_strict_json():
    outs = _every_status()
    assert [o["status"] for o in outs] == ["ok", "not_read", "pre_open", "not_latest", "out_of_play", "failed"]
    for o in outs:
        json.dumps(o, allow_nan=False)


def test_19_NEGATIVE_the_percent_prints_through_the_constant(monkeypatch):
    monkeypatch.setattr(SSR, "SSR_TRIGGER_DROP_PCT", 15)
    out = run([snap_doc(D24, "ZZV", void="bars_disagree"), fresh_day()])
    for t in (out["note_text"], out["rule_text"], out["withheld_text"]):
        assert "15%" in t and "10%" not in t, t


def test_20_NEGATIVE_zero_writes_zero_kicks():
    coll = FakeColl([snap_doc(D24, "ZZS"), fresh_day()])
    lists = Lists(due=True)
    corp = read_corp()
    corp.due = True
    out = run(coll=coll, lists=lists, corp=corp)
    assert out["n"] == 1 and coll.writes == [] and lists.kicks == []


def test_21_every_key_for_every_status():
    assert "prior_day" in SSR.NEW_KEYS and "corp_checked" in SSR.NEW_KEYS
    assert len(SSR.NEW_KEYS) == len(set(SSR.NEW_KEYS))
    outs = _every_status()
    assert {o["status"] for o in outs} == set(SSR.NEW_STATUSES)
    for o in outs:
        assert set(o) == set(SSR.NEW_KEYS), o["status"]
        for r in o["rows"]:
            assert tuple(r) == SSR.NEW_ROW_KEYS
        if o["status"] not in ("ok", "not_read"):
            assert o["prior_day"] is None and o["corp_checked"] is None
    assert outs[0]["rows"]


def test_22_NEGATIVE_a_junk_symbol_is_skipped_and_one_raising_name_is_a_fault(monkeypatch):
    junk = [dict(snap_doc(D24, "X"), _id="trig|2026-11-24|j%d" % i, symbol=s) for i, s in enumerate((7, None, ""))]
    out = run(junk + [snap_doc(D24, "ZZS"), snap_doc(D24, "ZZBAD"), fresh_day()])
    assert out["faults"] == [] and [r["symbol"] for r in out["rows"]] == ["ZZBAD", "ZZS"]
    real = SSR._day_eval

    def flaky(ctx, sym, T, trigs):
        if sym == "ZZBAD":
            raise RuntimeError("synthetic")
        return real(ctx, sym, T, trigs)
    monkeypatch.setattr(SSR, "_day_eval", flaky)
    out = run(junk + [snap_doc(D24, "ZZS"), snap_doc(D24, "ZZBAD"), fresh_day()])
    assert out["status"] == "ok" and [r["symbol"] for r in out["rows"]] == ["ZZS"]
    assert out["faults"] == ["ZZBAD"] and out["faults_text"] == SSR.NEW_FAULTS_TEXT % 1
    out = run([snap_doc(D24, "ZZBAD"), fresh_day()])
    assert out["rows"] == [] and out["faults"] == ["ZZBAD"] and out["empty_text"] is None   # a fault is never "none"


def test_22_NEGATIVE_a_list_name_its_own_rows_do_not_carry_is_a_fault_never_dropped():
    class Odd(Lists):
        def symbols_on(self, loaded, T):
            return ["ZZGHOST"]
    out = run([fresh_day()], lists=Odd())
    assert out["rows"] == [] and out["faults"] == ["ZZGHOST"] and out["empty_text"] is None


def test_23_symbols_on_over_the_real_stored_lists():
    coll = real_coll(("nasdaq", D20), ("nasdaq", D23), ("nyse", D23))
    loaded = SL.load(coll, et(D23, 22, 9))
    on23 = SL.symbols_on(loaded, D23)
    nyse23 = {r[0] for r in SL.parse_nyse(ANSWERS[("nyse", D23)].content, D23)[0]}
    assert on23 and on23 == sorted(on23) and set(on23) == nyse23   # the 04:15 Nasdaq edition holds no 11/23 row
    for s in on23:
        assert any(r["trigger_date"] == "2026-11-23" for r in SL.rows_for(loaded, s)), s
    for s in set(loaded["index"]) - set(on23):
        assert not any(r["trigger_date"] == "2026-11-23" for r in SL.rows_for(loaded, s)), s
    on20 = SL.symbols_on(loaded, D20)
    assert on20 and set(on20) != set(on23)
    assert all(any(r["trigger_date"] == "2026-11-20" for r in SL.rows_for(loaded, s)) for s in on20)


def test_23_NEGATIVE_an_unread_or_empty_load_or_an_unreadable_day_is_empty():
    assert SL.load(None, et(D23, 22, 9))["read"] is False
    assert SL.symbols_on(SL.load(None, et(D23, 22, 9)), D23) == []
    assert SL.symbols_on({}, D23) == [] and SL.symbols_on(None, D23) == [] and SL.symbols_on({"index": 7}, D23) == []
    coll = real_coll(("nyse", D23))
    loaded = SL.load(coll, et(D23, 22, 9))
    assert SL.symbols_on(loaded, D25) == [] and SL.symbols_on(loaded, "2026-11-23") == []
    assert SL.symbols_on(loaded, datetime(2026, 11, 23, 12, 0)) == SL.symbols_on(loaded, D23) != []


def test_24_every_served_text_is_clean_and_the_note_promises_nothing():
    outs = _every_status()
    for o in outs:
        for t in served_texts(o):
            assert not FORBIDDEN.search(t), t
            assert "nan" not in t.lower().split() and "None" not in t, t
        assert o["note_text"].endswith(RS.NOT_A_SIGNAL)
        assert "comes off" not in o["note_text"] and SSR.NOT_ON_LIST_YET not in o["note_text"]
        assert o["rule_text"] == o["rule_text"].strip() and o["rule_text"].startswith("The rule (")
    assert SSR.COMPUTED_TAIL.endswith(SSR.NEW_SRC_COMPUTED)
    assert "comes off" not in SSR.NEW_NOTE_TEXT


def test_25_NEGATIVE_the_new_read_holds_no_writer_and_no_kick():
    fns = [SSR.new_triggers, SSR._new_triggers, SSR._new_row, SSR._new_base, SSR._new_failed, SSR._new_title,
           SSR._new_note, SSR._new_rule, SSR._finite]
    src = "\n".join(inspect.getsource(f) for f in fns)
    for banned in ("kick_refresh", "update_one", "insert", "replace_one", "record_pass", ".payload(", "_http"):
        assert banned not in src, banned
    enum = inspect.getsource(SL.symbols_on)
    for banned in ("coll", "find", "_http", "refresh"):
        assert banned not in enum, banned
    lsrc = Path(SL.__file__).read_text()
    assert "from short_interest import ssr\n" not in lsrc and "import short_interest.ssr\n" not in lsrc
