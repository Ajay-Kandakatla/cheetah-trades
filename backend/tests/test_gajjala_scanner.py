"""chart_maps/gajjala/scanner.py — his scanner over the whole-market snapshot (spec §3.1.1–3.1.3, DECISIONS round A).

Every edge fixture is built with the scanner's OWN expression (`prev * (1 + pct / 100)`), never a decimal literal near
the edge. The numbers come from constants.py by name; the round-A floor ($0.10) and instrument set (CS + ADRC,
unknown listed as "type unknown") are pinned here as well.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import scanner as SC
from tests.test_gajjala_store import fake_store

ET = ZoneInfo("America/New_York")
S = date(2026, 10, 13)                                           # a Tuesday


def at(hh, mm, d=S):
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET)


def _ms(dt):
    return int(dt.timestamp() * 1000)


def row(price, prev=1.0, *, vol=2_000_000, when=None, min_when=None, day_v=0, close=None, o=None, h=None, l=None):
    when = when or at(8, 0)
    return {"last_trade_price": price, "last_trade_ts_ms": _ms(when) * 1_000_000,     # ns, as Massive sends
            "prev_day_close": prev, "min_av": vol, "min_t_ms": _ms(min_when or when),
            "volume": day_v, "open": o, "high": h, "low": l, "close": close}


TYPES = {"CS1": "CS", "ADR1": "ADRC", "ETF1": "ETF", "WRT1": "WARRANT", "AAA": "CS", "BBB": "CS", "CCC": "CS",
         "ZZZ": "CS", "LOW": "CS", "HI": "CS", "P1": "CS", "P2": "CS", "P3": "CS", "Q1": "CS", "Q2": "CS"}


def scan(rows, now=None, **kw):
    kw.setdefault("types", TYPES)
    return SC.scan_rows(rows, now or at(8, 1), S, **kw)


def qsyms(res):
    return {q["symbol"] for q in res["qualifiers"]}


# ── the three numbers ─────────────────────────────────────────────────────────────────────────────────────────
def test_constants_are_his_numbers_and_the_round_a_floor():
    assert (GC.SCAN_MIN_PRICE, GC.SCAN_MAX_PRICE) == (0.10, 100.0)
    assert GC.SCAN_MIN_VOLUME == 1_000_000 and GC.SCAN_MIN_CHANGE_PCT == 25.0


def test_price_band_edges():
    lo, hi = GC.SCAN_MIN_PRICE, GC.SCAN_MAX_PRICE
    rows = {"P1": row(lo, prev=lo / 2), "P2": row(hi, prev=hi / 2),
            "P3": row(round(lo - 0.0001, 4), prev=lo / 4), "Q1": row(hi + 0.01, prev=hi / 2)}
    assert qsyms(scan(rows)) == {"P1", "P2"}


def test_volume_edges():
    rows = {"AAA": row(2.0, vol=GC.SCAN_MIN_VOLUME), "BBB": row(2.0, vol=GC.SCAN_MIN_VOLUME - 1)}
    assert qsyms(scan(rows)) == {"AAA"}


def test_change_edges_built_with_the_scanners_own_expression():
    prev = 3.3
    rows = {"AAA": row(prev * (1 + GC.SCAN_MIN_CHANGE_PCT / 100), prev=prev), "BBB": row(prev * 1.2499, prev=prev)}
    res = scan(rows)
    assert qsyms(res) == {"AAA"}
    assert res["counts"]["vol_ok"] == 2 and res["counts"]["change_ok"] == 1


def test_NEGATIVE_stale_overnight_row_is_skipped():
    """Trap T6: the overnight snapshot carries the LAST session stamped as today."""
    rows = {"AAA": row(2.0, when=at(19, 59, date(2026, 10, 12)))}
    res = scan(rows)
    assert qsyms(res) == set() and res["counts"]["dated_session"] == 0


@pytest.mark.parametrize("prev", [0, None, -1.0, "x"])
def test_NEGATIVE_prev_close_zero_or_missing(prev):
    assert qsyms(scan({"AAA": row(2.0, prev=prev)})) == set()


def test_premarket_day_v_zero_uses_min_av():
    res = scan({"AAA": row(2.0, vol=1_500_000, day_v=0)})
    q = res["qualifiers"][0]
    assert q["volume"] == 1_500_000 and q["vol_src"] == "min_av"


def test_NEGATIVE_min_t_dated_yesterday_uses_day_v():
    # pin moved to an RTH pass 2026-10-13 (critic WP1 #3): a PRE-MARKET row never falls back to day.v any more
    y = at(19, 59, date(2026, 10, 12))
    w = at(10, 59)
    res = scan({"AAA": row(2.0, vol=5_000_000, when=w, min_when=y, day_v=10),
                "BBB": row(2.0, vol=5_000_000, when=w, min_when=y, day_v=GC.SCAN_MIN_VOLUME)}, now=at(11, 0))
    assert qsyms(res) == {"BBB"}
    assert res["qualifiers"][0]["vol_src"] == "day_v"


def test_row_fields():
    q = scan({"AAA": row(2.0, prev=1.0, close=1.9, o=1.1, h=2.1, l=1.0)})["qualifiers"][0]
    assert q["symbol"] == "AAA" and q["type"] == "CS" and q["change_pct"] == 100.0 and q["prev_close"] == 1.0
    assert (q["day_o"], q["day_h"], q["day_l"], q["day_c"]) == (1.1, 2.1, 1.0, 1.9)
    assert q["last_trade_et"] == "2026-10-13 08:00:00" and q["tape_session"] == "premarket"
    assert "ah_move_pct" not in q


# ── situational-awareness strip (GG S8 43:39–44:37) ──────────────────────────────────────────────────────────
def test_strip_counts_inclusive():
    rows = {"AAA": row(1 + GC.SA_BIG_RUNNER_PCT / 100), "BBB": row(1 + GC.SA_RUNNER_PCT / 100),
            "CCC": row(1.30), "ZZZ": row(1.79)}
    st = scan(rows)["strip"]
    assert st["runners_100"] == 1 and st["runners_80"] == 2
    assert st["best_symbol"] == "AAA" and st["best_change_pct"] == 100.0 and st["quiet"] is False


def test_quiet_below_40_and_NEGATIVE_40_is_not_quiet():
    assert scan({"AAA": row(1.399)})["strip"]["quiet"] is True
    assert scan({"AAA": row(1 + GC.SA_QUIET_BEST_PCT / 100)})["strip"]["quiet"] is False


def test_best_computed_with_zero_qualifiers():
    res = scan({"AAA": row(1.10), "BBB": row(1.20)})
    assert res["qualifiers"] == []
    assert res["strip"]["best_symbol"] == "BBB" and res["strip"]["quiet"] is True


def test_NEGATIVE_strip_population_needs_band_and_volume():
    res = scan({"AAA": row(150.0, prev=50.0), "BBB": row(2.0, vol=10)})
    assert res["strip"] == {"n_population": 0, "best_change_pct": None, "best_symbol": None,
                            "runners_100": 0, "runners_80": 0, "quiet": None}


# ── instrument types (Ajay round A) ───────────────────────────────────────────────────────────────────────────
def test_cs_and_adrc_listed_etf_and_warrant_dropped():
    rows = {"CS1": row(2.0), "ADR1": row(2.0), "ETF1": row(2.0), "WRT1": row(2.0)}
    res = scan(rows)
    assert qsyms(res) == {"CS1", "ADR1"}
    assert res["counts"]["type_out"] == 2
    assert {q["symbol"]: q["type"] for q in res["qualifiers"]} == {"CS1": "CS", "ADR1": "ADRC"}


def test_NEGATIVE_an_etf_never_counts_in_the_strip():
    res = scan({"ETF1": row(3.0), "CS1": row(1.3)})
    assert res["strip"]["best_symbol"] == "CS1" and res["strip"]["runners_100"] == 0


def test_unknown_type_listed_as_type_unknown():
    res = scan({"NEWIPO": row(2.0)})
    q = res["qualifiers"][0]
    assert q["type"] == GC.SCAN_UNKNOWN_TYPE == "unknown" and GC.SCAN_UNKNOWN_TYPE_LABEL == "type unknown"
    assert res["counts"]["type_unknown"] == 1


def test_NEGATIVE_unknown_type_dropped_under_drop(monkeypatch):
    monkeypatch.setattr(GC, "SCAN_UNKNOWN_TYPE_POLICY", "drop")
    res = scan({"NEWIPO": row(2.0)})
    assert res["qualifiers"] == [] and res["counts"]["type_out"] == 1


def test_NEGATIVE_no_type_map_at_all_lists_every_name_as_unknown():
    res = scan({"CS1": row(2.0), "ETF1": row(2.0)}, types=None)
    assert qsyms(res) == {"CS1", "ETF1"} and {q["type"] for q in res["qualifiers"]} == {"unknown"}


def test_types_filter_off_lists_everything(monkeypatch):
    monkeypatch.setattr(GC, "SCAN_INSTRUMENT_TYPES", None)
    res = scan({"ETF1": row(2.0), "WRT1": row(2.0)})
    assert qsyms(res) == {"ETF1", "WRT1"} and {q["type"] for q in res["qualifiers"]} == {None}


# ── tape session of a pass ────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("hh,mm,d,want", [(4, 1, S, "premarket"), (9, 31, S, "rth"), (16, 1, S, "afterhours"),
                                          (20, 1, S, "afterhours"), (20, 5, S, "afterhours"),
                                          (20, 6, S, "closed"), (3, 59, S, "closed"),
                                          (20, 1, date(2026, 10, 17), "closed")])
def test_pass_tape_session(hh, mm, d, want):
    assert SC.pass_tape_session(at(hh, mm, d)) == want


# ── split hold-out (HIS CALL 17) ──────────────────────────────────────────────────────────────────────────────
def test_split_today_held_out_and_counted():
    res = scan({"AAA": row(2.0), "BBB": row(2.0)})
    calls = []

    def fetch(sym, since):
        calls.append(sym)
        return [{"execution_date": "2026-10-13", "split_from": 10, "split_to": 1}] if sym == "AAA" else []
    decided = SC.hold_out_splits(res, S, known={}, fetch=fetch)
    assert decided == {"AAA": "held", "BBB": "ok"}
    assert qsyms(res) == {"BBB"} and res["counts"]["held_split"] == 1 and res["counts"]["qualifiers"] == 1
    assert sorted(calls) == ["AAA", "BBB"]


def test_NEGATIVE_split_fetch_raises_is_listed_as_failed():
    res = scan({"AAA": row(2.0)})
    decided = SC.hold_out_splits(res, S, known={}, fetch=lambda s, d: (_ for _ in ()).throw(RuntimeError("503")))
    assert decided == {"AAA": "failed"}
    assert res["qualifiers"][0]["split_check"] == "failed" and res["counts"]["split_failed"] == 1


def test_NEGATIVE_an_older_split_is_not_today():
    res = scan({"AAA": row(2.0)})
    SC.hold_out_splits(res, S, known={}, fetch=lambda s, d: [{"execution_date": "2026-10-12"}])
    assert qsyms(res) == {"AAA"}


def test_known_checks_are_never_refetched():
    res = scan({"AAA": row(2.0), "BBB": row(2.0)})
    SC.hold_out_splits(res, S, known={"AAA": "held", "BBB": "ok"},
                       fetch=lambda s, d: pytest.fail("decided earlier this session"))
    assert qsyms(res) == {"BBB"} and res["counts"]["held_split"] == 1


def test_record_scan_writes_qualifiers_and_held_names_stay_off_the_list():
    st = fake_store()
    res = scan({"AAA": row(2.0), "BBB": row(2.0)})
    SC.record_scan(st, S, at(8, 1), res,
                   fetch_splits=lambda s, d: [{"execution_date": "2026-10-13"}] if s == "AAA" else [])
    assert st.split_checks(S) == {"AAA": "held", "BBB": "ok"}
    assert set(SC.listed_symbols(st, S)) == {"BBB"}
    res2 = scan({"AAA": row(2.0), "BBB": row(2.0)}, now=at(8, 6))
    SC.record_scan(st, S, at(8, 6), res2, fetch_splits=lambda s, d: pytest.fail("once per symbol per session"))
    assert qsyms(res2) == {"BBB"}


# ── listed set: today + STAY_LISTED_SESSIONS (Cheetah default 2) ─────────────────────────────────────────────
def _qualify(st, d, *syms):
    st.record_qualifiers(d, datetime(d.year, d.month, d.day, 14, tzinfo=timezone.utc),
                         [{"symbol": s, "change_pct": 30.0} for s in syms], "rth")


def test_listed_s_s1_s2_and_NEGATIVE_s3_is_graveyard():
    st = fake_store()
    _qualify(st, S, "T0")
    _qualify(st, date(2026, 10, 12), "T1")                       # Mon (Columbus Day is a trading day)
    _qualify(st, date(2026, 10, 9), "T2", "T0")                  # Fri
    _qualify(st, date(2026, 10, 8), "T3", "T2")                  # Thu — three market days back
    listed = SC.listed_symbols(st, S)
    assert set(listed) == {"T0", "T1", "T2"}
    assert listed["T0"] == {"since": "2026-10-09", "last_qualified": "2026-10-13", "day_n": 1, "of": 3}
    assert listed["T1"]["day_n"] == 2 and listed["T2"]["day_n"] == 3
    assert SC.graveyard_today(st, S) == ["T3"]                   # T2 qualified later -> still listed


def test_holiday_skipped_by_prev_market_day():
    st = fake_store()
    _qualify(st, date(2026, 11, 25), "WED")
    _qualify(st, date(2026, 11, 24), "TUE")
    assert set(SC.listed_symbols(st, date(2026, 11, 27))) == {"WED", "TUE"}       # 11-26 Thanksgiving skipped
    assert SC.listed_symbols(st, date(2026, 11, 27))["WED"]["day_n"] == 2
    assert set(SC.listed_symbols(st, date(2026, 11, 30))) == {"WED"}
    assert SC.graveyard_today(st, date(2026, 11, 30)) == ["TUE"]


def test_NEGATIVE_graveyard_only_names_that_dropped_off_today():
    st = fake_store()
    _qualify(st, date(2026, 10, 7), "OLD")                       # dropped off yesterday, not today
    assert SC.graveyard_today(st, S) == []


# ── 🌙 / ☀️ after-hours carry (K9, spec C4) ──────────────────────────────────────────────────────────────────
def ah_row(price, close=2.0, vol=10, when=None):
    return row(price, prev=1.9, vol=vol, close=close, when=when or at(17, 0))


def test_ah_carry_edge_10_0_and_NEGATIVE_9_99():
    close = 2.0
    res = scan({"AAA": ah_row(close * (1 + GC.K9_AH_CARRY_PCT / 100)), "BBB": ah_row(close * 1.0999)}, now=at(17, 1))
    assert [r["symbol"] for r in res["ah_carry"]] == ["AAA"]
    assert res["ah_carry"][0]["ah_move_pct"] == pytest.approx(10.0)


@pytest.mark.parametrize("hh,mm", [(8, 1), (11, 1), (15, 56)])
def test_NEGATIVE_no_carry_set_from_an_rth_or_premarket_pass(hh, mm):
    res = scan({"AAA": ah_row(3.0, when=at(hh, mm - 1))}, now=at(hh, mm))
    assert res["ah_carry"] is None and res["k10_candidates"] == []


def test_ah_carry_covers_non_qualifier_rows():
    """10 shares and +5% on the prior close: no scanner qualifier, still carried on its after-hours move."""
    res = scan({"AAA": ah_row(2.4, close=2.0, vol=10)}, now=at(17, 1))
    assert res["qualifiers"] == [] and [r["symbol"] for r in res["ah_carry"]] == ["AAA"]


def test_NEGATIVE_ah_carry_outside_the_price_band():
    res = scan({"AAA": ah_row(130.0, close=100.0)}, now=at(17, 1))
    assert res["ah_carry"] == []


def test_k10_prefilter_edge():
    close = 2.0
    res = scan({"AAA": ah_row(close * (1 + GC.K10_AH_MIN_GAIN_PCT / 100)), "BBB": ah_row(close * 1.0499)},
               now=at(17, 1))
    assert SC.k10_names(res) == ["AAA"]


def _ah_pass(st, hh, mm, price, *, http=200, rows=None):
    rows = rows if rows is not None else {"AAA": ah_row(price, when=at(hh, mm - 1))}
    res = scan(rows, now=at(hh, mm))
    meta = {"http": http, "n": len(rows)}
    return SC.commit_ah_carry(st, S, at(hh, mm), res, meta)


def test_NEGATIVE_12_then_3_is_NOT_carried():
    st = fake_store()
    assert _ah_pass(st, 17, 1, 2.24) == "replaced"
    assert _ah_pass(st, 19, 56, 2.06) == "replaced"
    assert st.ah_carry(S)["names"] == {}


def test_3_then_12_is_carried():
    st = fake_store()
    _ah_pass(st, 17, 1, 2.06)
    _ah_pass(st, 19, 56, 2.24)
    assert set(st.ah_carry(S)["names"]) == {"AAA"}


@pytest.mark.parametrize("http,rows", [(200, {}), (503, {})])
def test_NEGATIVE_failed_2001_pass_leaves_the_1956_set(http, rows):
    st = fake_store()
    _ah_pass(st, 19, 56, 2.24)
    assert _ah_pass(st, 20, 1, 0, http=http, rows=rows) == "failed"
    doc = st.ah_carry(S)
    assert set(doc["names"]) == {"AAA"} and doc["pass_at"] == at(19, 56)


def test_the_last_pass_that_ran_decides_when_2001_is_missing():
    st = fake_store()
    _ah_pass(st, 17, 1, 2.06)
    _ah_pass(st, 18, 31, 2.24)                                   # host slept through 18:36 … 20:01
    assert set(st.ah_carry(S)["names"]) == {"AAA"}


def test_NEGATIVE_an_rth_pass_never_touches_the_carry():
    st = fake_store()
    res = scan({"AAA": row(2.0, when=at(11, 0))}, now=at(11, 1))
    assert SC.commit_ah_carry(st, S, at(11, 1), res, {"http": 200, "n": 1}) == "skipped"
    assert st.ah_carry(S) is None


# ── instrument-type map: once per trading day ────────────────────────────────────────────────────────────────
def test_type_map_fetched_at_most_once_per_trading_day():
    st = fake_store()
    calls = []

    def fetch():
        calls.append(1)
        return {"AAA": "CS", "BBB": "ETF"}, True, 12
    assert SC.ensure_type_map(st, S, fetch=fetch) == {"AAA": "CS", "BBB": "ETF"}
    assert SC.ensure_type_map(st, S, fetch=fetch) == {"AAA": "CS", "BBB": "ETF"}       # 2nd pass reads Mongo
    assert len(calls) == 1
    SC.ensure_type_map(st, date(2026, 10, 14), fetch=fetch)
    assert len(calls) == 2
    doc = st.types_map()
    assert doc["as_of"] == "2026-10-14" and doc["complete"] is True and doc["calls"] == 12


def test_NEGATIVE_failed_type_fetch_keeps_yesterday_and_retries_next_pass():
    # pin updated 2026-10-13 (critic WP1 #1): a failed fetch used to stamp attempted_on and never retry that day —
    # an empty first-ever fetch left the type filter off all session. Now each later pass retries (once per pass).
    st = fake_store()
    SC.ensure_type_map(st, date(2026, 10, 12), fetch=lambda: ({"AAA": "CS"}, True, 12))
    calls = []

    def bad():
        calls.append(1)
        return {}, False, 1
    assert SC.ensure_type_map(st, S, fetch=bad) == {"AAA": "CS"}
    assert SC.ensure_type_map(st, S, fetch=bad) == {"AAA": "CS"}
    assert len(calls) == 2 and st.types_map()["as_of"] == "2026-10-12"


class _R:
    def __init__(self, status, body):
        self.status_code, self._b = status, body

    def json(self):
        return self._b


class _Http:
    def __init__(self, pages):
        self.pages, self.calls = list(pages), []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        return self.pages.pop(0)


def test_fetch_type_map_paginates_and_spells_class_shares_with_a_dash():
    http = _Http([_R(200, {"results": [{"ticker": "AAA", "type": "CS"}, {"ticker": "BRK.B", "type": "CS"}],
                           "next_url": "https://api.massive.com/v3/reference/tickers?cursor=x"}),
                  _R(200, {"results": [{"ticker": "SCNI", "type": "ADRC"}, {"ticker": "SPY", "type": "ETF"}]})])
    types, complete, calls = SC.fetch_type_map(http=http, key="KEY")
    assert types == {"AAA": "CS", "BRK-B": "CS", "SCNI": "ADRC", "SPY": "ETF"} and complete and calls == 2
    assert http.calls[0][1]["market"] == "stocks" and http.calls[0][1]["limit"] == GC.TYPES_PAGE_LIMIT
    assert http.calls[1] == ("https://api.massive.com/v3/reference/tickers?cursor=x", {"apiKey": "KEY"})


def test_NEGATIVE_fetch_type_map_capped_at_max_pages_is_incomplete():
    page = _R(200, {"results": [{"ticker": "AAA", "type": "CS"}], "next_url": "https://x/next"})
    http = _Http([page] * 5)
    types, complete, calls = SC.fetch_type_map(http=http, key="KEY", max_pages=3)
    assert calls == 3 and complete is False and types == {"AAA": "CS"}


def test_NEGATIVE_fetch_type_map_non_200_or_no_key():
    types, complete, calls = SC.fetch_type_map(http=_Http([_R(500, {})]), key="KEY")
    assert (types, complete, calls) == ({}, False, 1)
    assert SC.fetch_type_map(http=_Http([]), key="") == ({}, False, 0)


def test_scan_is_pure_and_deterministic():
    rows = {"AAA": row(2.0), "BBB": row(1.6), "CCC": row(1.1)}
    a = scan(rows)
    b = scan(dict(reversed(list(rows.items()))))
    assert a == b and [q["symbol"] for q in a["qualifiers"]] == ["AAA", "BBB"]
    assert rows["AAA"] == row(2.0)


def test_now_utc_and_et_clocks_agree():
    utc = at(17, 1).astimezone(timezone.utc)
    assert SC.scan_rows({"AAA": ah_row(2.4)}, utc, S, types=TYPES)["tape_session"] == "afterhours"
    assert SC.pass_tape_session(utc + timedelta(hours=3, minutes=5)) == "closed"
