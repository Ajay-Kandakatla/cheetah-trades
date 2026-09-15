"""2026-09-14 review fixes — Explosive Growth (E1, E4, E6) and Hot sectors
(H1, H2, H5). Verified on live data the same day:

  E1  7 of 29 board rows cleared the 100%/100% screen on quarter pairs that
      are NOT four fiscal quarters apart (ECHO: FY2026 Q2 vs FY2020 Q4).
  E4  DBRG sat #1 at +15,961.5% off a NEGATIVE year-ago revenue base.
  E6  the board printed no fiscal period, so cadence could not be checked.
  H1  the streak double-counted today's own stored session ("#1 · 2d" on the
      day a sector took #1).
  H2  "＋ entered" printed a below-benchmark group as green inflow.
  H5  the rotation build read today's LIVE bar through chart_maps.bars_for.

Every fix is DATA-CORRECTNESS on the growth board / the strip. The book-cited
modules (sepa/sales.py, sepa/canslim.py) are untouched and a test below pins
that. No threshold is invented: adjacency reuses sepa.qoq._adjacent, the stale
rule reuses observability.period_freshness, the session split reuses
supply_demand.demand_reentry.split_today_partial.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from growth import tracker as T
from observability import period_freshness as PF
from rotation import history as H
from rotation import tracker as RT

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")


def _src(rel: str) -> str:
    with open(os.path.join(HERE, rel), encoding="utf-8") as fh:
        return fh.read()


# ECHO's cached series, verbatim from the research cache 2026-09-14. Slot 0 is
# FY2026 Q2 (8105) and slot 4 is FY2020 Q4 (8083): 22 quarters apart, and the
# cached "YoY" of +374.1% was computed across exactly that gap.
ECHO_PERIODS = [8105, 8086, 8085, 8084, 8083, 8082, 8081, 8080]
ECHO_REVS = [3576164000.0, 985590000.0, 934524000.0, 800802000.0,
             754252000.0, 691495000.0, 514719000.0, 551049000.0]
# DBRG, verbatim: slot 4 is a NEGATIVE revenue base (-$3.2M), which sepa/sales
# turns into +15,961.5% because it divides by abs(base).
DBRG_PERIODS = [8105, 8104, 8103, 8102, 8101, 8100, 8099, 8097]
DBRG_REVS = [508679000.0, 72236000.0, 47901000.0, 3818000.0,
             -3207000.0, 45447000.0, None, 390336000.0]
# A clean, gap-free series: every slot one quarter apart.
CLEAN_PERIODS = [8105, 8104, 8103, 8102, 8101, 8100, 8099, 8098]
CLEAN_REVS = [200.0, 150.0, 120.0, 110.0, 80.0, 70.0, 60.0, 50.0]


def periods_from(p0: int, n: int = 8) -> list:
    """A gap-free newest-first series whose latest quarter is `p0`."""
    return [p0 - i for i in range(n)]


def fund(sales=145.9, prior=7.2, eps=185.0, periods=CLEAN_PERIODS,
         revs=CLEAN_REVS, source="hybrid", **kw):
    f = {"sales": {"growth_yoy_pct": sales, "prior_yoy_pct": prior,
                   "tier": "explosive", "accelerating": True,
                   "consecutive_growth_q": 3},
         "q_eps_growth_pct": eps,
         "earnings_quality": {"components": {"eps_prior_yoy_pct": 75.0,
                                             "npm_latest_pct": 27.4,
                                             "npm_expanding": True}},
         "inst_ownership_pct": 73.38,
         "q_period_series": periods, "rev_q_series": revs, "_source": source}
    f.update(kw)
    return f


# ============================================================ E1 — adjacency
def test_E1_echo_a_pair_22_quarters_apart_does_NOT_qualify():
    ok, legs = T.qualifies(fund(sales=374.1, prior=42.5, eps=5782.93,
                                periods=ECHO_PERIODS, revs=ECHO_REVS))
    assert ok is False
    assert legs["period_mismatch"] is True
    # the cached number is still carried, so the refusal is explainable
    assert legs["sales_growth_pct"] == 374.1


def test_E1_a_pair_that_really_is_a_year_apart_qualifies():
    ok, legs = T.qualifies(fund())
    assert ok is True
    assert legs["period_mismatch"] is False


def test_E1_the_PRIOR_leg_is_checked_too():
    """Slot 1 vs slot 5 must also be four quarters apart — the prior leg is the
    gate that separates a ramp from an easy base, and a mislabelled prior is
    exactly the easy base it exists to catch."""
    periods = [8105, 8104, 8103, 8102, 8101, 8099, 8098, 8097]   # slot 5 skips 8100
    ok, legs = T.qualifies(fund(periods=periods))
    assert legs["period_mismatch"] is True
    assert ok is False


def test_E1_NEGATIVE_a_legacy_row_with_no_period_keys_is_accepted_not_blanked():
    """sepa.qoq._adjacent ACCEPTS an unverifiable pair on purpose: refusing
    every older cached document would blank the board rather than fix it."""
    ok, legs = T.qualifies(fund(periods=None))
    assert ok is True and legs["period_mismatch"] is False
    ok, legs = T.qualifies(fund(periods=[8105, None, None, None, None, None]))
    assert ok is True and legs["period_mismatch"] is False


def test_E1_uses_the_apps_ONE_adjacency_definition(monkeypatch):
    """No second 'are these a year apart' rule. The tracker must call
    sepa.qoq._adjacent with gap=4 on both pairs and do no period arithmetic
    of its own."""
    import sepa.qoq as Q
    calls = []

    def spy(periods, i, j, gap=1):
        calls.append((i, j, gap))
        return True

    monkeypatch.setattr(Q, "_adjacent", spy)
    T.qualifies(fund())
    assert (0, 4, 4) in calls and (1, 5, 4) in calls
    src = _src("growth/tracker.py")
    assert "from sepa.qoq import _adjacent" in src
    assert "int(a) - int(b)" not in src           # qoq's arithmetic, not copied here


# ======================================================= E4 — negative base
def test_E4_dbrg_negative_year_ago_base_is_refused_and_the_leg_is_blanked():
    ok, legs = T.qualifies(fund(sales=15961.5, prior=59.0, eps=250.0,
                                periods=DBRG_PERIODS, revs=DBRG_REVS))
    assert ok is False
    assert legs["sales_growth_pct"] is None        # blank, never a number
    assert legs["base_negative"] is True


def test_E4_a_ZERO_base_is_refused_the_same_way():
    revs = list(CLEAN_REVS)
    revs[4] = 0.0
    ok, legs = T.qualifies(fund(revs=revs))
    assert ok is False and legs["base_negative"] is True
    assert legs["sales_growth_pct"] is None


def test_E4_a_negative_PRIOR_base_blanks_the_prior_leg():
    revs = list(CLEAN_REVS)
    revs[5] = -1.0
    ok, legs = T.qualifies(fund(revs=revs))
    assert ok is False
    assert legs["sales_prior_pct"] is None and legs["base_negative"] is True
    assert legs["sales_growth_pct"] == 145.9       # the headline leg is untouched


def test_E4_NEGATIVE_a_positive_base_changes_nothing():
    ok, legs = T.qualifies(fund())
    assert ok is True and legs["base_negative"] is False
    assert legs["sales_growth_pct"] == 145.9 and legs["sales_prior_pct"] == 7.2


def test_E4_NEGATIVE_an_unknown_base_is_unknown_not_negative():
    for revs in (None, [], [200.0, 150.0], [200.0, 150.0, 120.0, 110.0, None]):
        ok, legs = T.qualifies(fund(revs=revs))
        assert ok is True, revs
        assert legs["base_negative"] is False, revs


def test_E4_the_book_cited_sales_module_is_UNTOUCHED():
    """The refusal lives on THIS board only. sepa/sales.py still returns its
    own number for the DBRG series — that is the proof nothing upstream was
    edited to make the board look right."""
    from sepa import sales as S
    assert S.compute(DBRG_REVS)["growth_yoy_pct"] == pytest.approx(15961.5, abs=0.1)
    src = _src("growth/tracker.py")
    assert "from sepa import sales" not in src and "sepa.sales" not in src
    assert "from sepa import canslim" not in src and "sepa.canslim" not in src


# ============================================================ E6 — the period
def test_E6_the_period_is_the_slot_zero_key_in_fiscal_words():
    assert T.qualifies(fund())[1]["period"] == "FY2026 Q2"
    assert T.period_label(8105) == "FY2026 Q2"
    assert T.period_label(8084) == "FY2021 Q1"


def test_E6_the_yfinance_path_is_labelled_as_the_CALENDAR_quarter_it_is():
    assert T.qualifies(fund(source="yfinance"))[1]["period"] == "Q2 2026"


def test_E6_a_calendar_row_gets_an_age_and_a_stale_verdict_from_period_freshness():
    today = date(2026, 9, 14)
    # Q1 2026 ended 2026-03-31; by 2026-09-14 the Q2 report is past due.
    _, old = T.qualifies(fund(source="yfinance", periods=periods_from(8104)),
                         today=today)
    assert old["period_end"] == "2026-03-31"
    assert old["period_age_days"] == (today - date(2026, 3, 31)).days == 167
    assert old["period_stale"] is True
    # Q2 2026 is the quarter the data SHOULD show on that date — fresh.
    _, cur = T.qualifies(fund(source="yfinance"), today=today)
    assert cur["period_end"] == "2026-06-30"
    assert cur["period_stale"] is False
    # and the boundary IS period_freshness's, not a number typed here
    assert old["period_stale"] == (date(2026, 3, 31) < PF.expected_13f_quarter(today))
    assert cur["period_stale"] == (date(2026, 6, 30) < PF.expected_13f_quarter(today))


def test_E6_NEGATIVE_a_fiscal_period_has_NO_age_and_NO_stale_verdict():
    """The Massive path stores fiscal indices and no end date. NVDA's FY2027
    Q2 ended 2026-07-26; a calendar read of the same index would say
    2027-06-30. Unknown must stay unknown."""
    _, legs = T.qualifies(fund(source="hybrid", periods=periods_from(8109)),
                          today=date(2026, 9, 14))
    assert legs["period"] == "FY2027 Q2"
    assert legs["period_end"] is None
    assert legs["period_age_days"] is None
    assert legs["period_stale"] is None


def test_E6_NEGATIVE_no_period_keys_means_no_period_never_a_guess():
    _, legs = T.qualifies(fund(periods=None))
    assert legs["period"] is None and legs["period_age_days"] is None
    assert legs["period_stale"] is None
    assert T.period_label(None) is None and T.period_label("x") is None


def test_E6_a_stale_row_carries_a_warning_and_a_fresh_or_unknown_one_does_not():
    today = date(2026, 9, 14)
    _, stale = T.qualifies(fund(source="yfinance", periods=periods_from(8104)),
                           today=today)
    w = T.period_warning(stale)
    assert w and w.startswith("⚠️") and "Q1 2026" in w and "167 days" in w
    _, fresh = T.qualifies(fund(source="yfinance"), today=today)
    assert T.period_warning(fresh) is None
    _, unknown = T.qualifies(fund(source="hybrid"), today=today)
    assert T.period_warning(unknown) is None
    assert T.period_warning({}) is None and T.period_warning(None) is None


def test_E6_no_day_count_is_typed_in_the_tracker():
    src = _src("growth/tracker.py")
    assert "135" not in src
    assert "from observability import period_freshness" in src
    assert "expected_13f_quarter" in src


def test_E6_screen_puts_the_period_and_its_warning_on_the_row(monkeypatch):
    """End to end through screen(): the stored row carries `period`, and a
    stale calendar period lands in the same `warnings` list the Flags column
    prints. Q1 2025 is stale on any date after 2025-09-04, so this does not
    depend on the wall clock."""
    docs = [{"symbol": "OLD", "name": "Old Print",
             "fundamentals": fund(source="yfinance", periods=periods_from(8100)),
             "liquidity": {"avg_dollar_vol": 50e6, "avg_shares": 1e6}},
            {"symbol": "ECHO", "name": "Echo",
             "fundamentals": fund(sales=374.1, prior=42.5, eps=5782.93,
                                  periods=ECHO_PERIODS, revs=ECHO_REVS),
             "liquidity": {"avg_dollar_vol": 50e6, "avg_shares": 1e6}},
            {"symbol": "DBRG", "name": "DigitalBridge",
             "fundamentals": fund(sales=15961.5, prior=59.0, eps=250.0,
                                  periods=DBRG_PERIODS, revs=DBRG_REVS),
             "liquidity": {"avg_dollar_vol": 50e6, "avg_shares": 1e6}},
            {"symbol": "AXTI", "name": "AXT",
             "fundamentals": fund(),
             "liquidity": {"avg_dollar_vol": 50e6, "avg_shares": 1e6}}]

    class _Coll:
        def find(self, *_a, **_k):
            return list(docs)

    class _DB:
        sepa_research_cache = _Coll()

    monkeypatch.setattr(T, "_db", lambda: _DB())
    monkeypatch.setattr(T, "_caps", lambda syms: {s: 5e9 for s in syms})
    monkeypatch.setattr(T, "_sectors", lambda syms: {})
    monkeypatch.setattr(T, "_promo_tagged", lambda syms: set())
    monkeypatch.setattr(T, "_prices", lambda syms: {s: 50.0 for s in syms})
    monkeypatch.setattr(T, "_zone_read", lambda s: {"missing": True, "in_band": False,
                                                    "intact": None, "band": None,
                                                    "order_block": False})
    rows = {r["symbol"]: r for r in T.screen()}
    assert set(rows) == {"OLD", "AXTI"}            # ECHO (E1) and DBRG (E4) refused
    assert rows["AXTI"]["period"] == "FY2026 Q2"
    assert not any("past due" in w for w in rows["AXTI"]["warnings"])
    assert rows["OLD"]["period"] == "Q1 2025" and rows["OLD"]["period_stale"] is True
    assert any(w.startswith("⚠️") and "past due" in w for w in rows["OLD"]["warnings"])
    # the standing warnings are still there, unchanged in kind
    assert any("no zone bands" in w for w in rows["AXTI"]["warnings"])


# ==================================================== H1 — streak double-count
def payload(as_of, order, key="rel_5d", values=None):
    """`order` is best-first; values descend so the rank IS the list order."""
    vals = values or [10.0 - i for i in range(len(order))]
    return {"as_of": as_of,
            "sectors": [{"group": g, key: vals[i], "n": 10}
                        for i, g in enumerate(order)]}


def snap(as_of, order, values=None):
    return H.snapshot(payload(as_of, order, values=values))


def test_H1_todays_own_stored_session_is_counted_ONCE():
    """The scan stores today's snapshot BEFORE the strip reads history, so
    today's `_id` is in the list. It must not count behind `snap` as well."""
    order = ["Communication Services", "Energy", "Technology"]
    hist = [snap("2026-09-14", order)] + \
           [snap("2026-09-%02d" % d, order) for d in (11, 10, 9, 8)]
    c = H.changes(payload("2026-09-14", order), history=hist, grain="sectors")
    assert c["streaks"]["Communication Services"] == 5      # today + four, not six


def test_H1_the_day_a_sector_takes_number_one_reads_1d_not_2d():
    """The live symptom: 'Communication Services #1 · 2d' on the day it took
    #1, because today's stored row was counted as yesterday."""
    hist = [snap("2026-09-14", ["Communication Services", "Energy"]),   # today's own
            snap("2026-09-11", ["Energy", "Communication Services"])]  # it was #2
    c = H.changes(payload("2026-09-14", ["Communication Services", "Energy"]),
                  history=hist, grain="sectors")
    assert c["streaks"]["Communication Services"] == 1
    assert c["baseline"] == "2026-09-11"


def test_H1_NEGATIVE_older_sessions_still_count_and_a_break_still_breaks():
    hist = [snap("2026-09-11", ["Energy", "Tech"]),
            snap("2026-09-10", ["Tech", "Energy"]),
            snap("2026-09-09", ["Energy", "Tech"])]
    c = H.changes(payload("2026-09-14", ["Energy", "Tech"]), history=hist, grain="sectors")
    assert c["streaks"]["Energy"] == 2                       # today + 09-11 only


def test_H1_changes_all_carries_the_same_single_count():
    order = ["Energy", "Tech"]
    hist = [snap("2026-09-14", order), snap("2026-09-11", order)]
    out = H.changes_all(payload("2026-09-14", order), history=hist)
    assert out["grains"]["sectors"]["streaks"]["Energy"] == 2


# ============================================= H2 — entered must be inflow
def test_H2_a_below_benchmark_group_does_NOT_print_as_entered():
    """Real Estate at -0.23 crossed into the top 6 on a red day and printed as
    green inflow. Entering the band is not money in unless the leg is > 0."""
    prior = snap("2026-09-11", ["A", "B", "C", "D", "E", "F", "Real Estate", "H"])
    today = payload("2026-09-14", ["A", "B", "C", "D", "E", "Real Estate", "F", "H"],
                    values=[1.0, 0.8, 0.6, 0.4, 0.2, -0.23, -0.5, -0.9])
    c = H.changes(today, history=[prior], grain="sectors", top_n=6)
    assert [e["group"] for e in c["entered"]] == []
    # it still LEFT-side reports F dropping out — the cold end is information
    assert [e["group"] for e in c["left"]] == ["F"]


def test_H2_an_above_benchmark_entrant_still_prints():
    prior = snap("2026-09-11", ["A", "B", "C", "D", "E", "F", "Utilities", "H"])
    today = payload("2026-09-14", ["A", "B", "C", "D", "E", "Utilities", "F", "H"],
                    values=[1.0, 0.8, 0.6, 0.4, 0.2, 0.05, -0.5, -0.9])
    c = H.changes(today, history=[prior], grain="sectors", top_n=6)
    assert [e["group"] for e in c["entered"]] == ["Utilities"]


def test_H2_NEGATIVE_a_missing_leg_or_exactly_zero_never_enters():
    prior = snap("2026-09-11", ["A", "B", "C"])
    today = {"as_of": "2026-09-14",
             "sectors": [{"group": "A", "rel_5d": 1.0}, {"group": "Z", "rel_5d": 0.0},
                         {"group": "B", "rel_5d": -0.1}, {"group": "Q"}]}
    c = H.changes(today, history=[prior], grain="sectors", top_n=2)
    assert c["entered"] == []


def test_H2_NEGATIVE_left_is_unfiltered_even_when_the_leaver_is_positive():
    prior = snap("2026-09-11", ["A", "B", "C"])
    today = payload("2026-09-14", ["A", "C", "B"], values=[3.0, 2.0, 1.0])
    c = H.changes(today, history=[prior], grain="sectors", top_n=2)
    assert [e["group"] for e in c["left"]] == ["B"]
    assert [e["group"] for e in c["entered"]] == ["C"]


def test_H2_the_band_is_ONE_constant_for_every_grain_not_scaled():
    """His call: do not scale TOP_N per grain."""
    assert isinstance(H.TOP_N, int)
    src = _src("rotation/history.py")
    assert "TOP_N_BY_GRAIN" not in src and "top_n_for" not in src
    p = {"as_of": "2026-09-14",
         "sectors": [{"group": f"s{i}", "rel_5d": 9 - i} for i in range(9)],
         "industries": [{"group": f"i{i}", "rel_5d": 9 - i} for i in range(9)]}
    hist = [H.snapshot({"as_of": "2026-09-11",
                        "sectors": [{"group": f"s{8 - i}", "rel_5d": 9 - i} for i in range(9)],
                        "industries": [{"group": f"i{8 - i}", "rel_5d": 9 - i} for i in range(9)]})]
    out = H.changes_all(p, history=hist, top_n=3)
    assert len(out["grains"]["sectors"]["top"]) == 3
    assert len(out["grains"]["industries"]["top"]) == 3


# ============================================ H5 — closed bars only, always
def _frame(days_back: int, end: date, partial_last=True):
    """A daily frame ending on `end`, indexed at 04:00 like the price cache."""
    idx = [pd.Timestamp(f"{(end - pd.Timedelta(days=days_back - 1 - i)).isoformat()} 04:00:00")
           for i in range(days_back)]
    closes = [100.0 + i for i in range(days_back)]
    return pd.DataFrame({"open": closes, "high": [c + 1 for c in closes],
                         "low": [c - 1 for c in closes], "close": closes,
                         "volume": [1_000_000 + i for i in range(days_back)]}, index=idx)


def test_H5_the_rotation_read_drops_todays_PARTIAL_bar_mid_session(monkeypatch):
    import sepa.prices as P
    today = datetime.now(ET).date()
    monkeypatch.setattr(P, "load_prices", lambda *_a, **_k: _frame(6, today))
    noon = datetime(today.year, today.month, today.day, 12, 31, tzinfo=ET)
    bars = RT._bars_for("AAPL", days=260, now_et=noon)
    assert len(bars) == 5
    assert bars[-1]["t"] == (today - pd.Timedelta(days=1)).isoformat()
    assert set(bars[-1]) >= {"t", "o", "h", "l", "c", "v"}     # chart_maps' shape


def test_H5_after_the_close_todays_bar_is_WHOLE_and_stays(monkeypatch):
    import sepa.prices as P
    today = datetime.now(ET).date()
    monkeypatch.setattr(P, "load_prices", lambda *_a, **_k: _frame(6, today))
    after = datetime(today.year, today.month, today.day, 16, 5, tzinfo=ET)
    bars = RT._bars_for("AAPL", days=260, now_et=after)
    assert len(bars) == 6 and bars[-1]["t"] == today.isoformat()


def test_H5_NEGATIVE_a_frame_ending_on_a_prior_day_is_untouched(monkeypatch):
    import sepa.prices as P
    today = datetime.now(ET).date()
    yday = today - pd.Timedelta(days=1)
    monkeypatch.setattr(P, "load_prices", lambda *_a, **_k: _frame(6, yday))
    noon = datetime(today.year, today.month, today.day, 12, 31, tzinfo=ET)
    bars = RT._bars_for("AAPL", days=260, now_et=noon)
    assert len(bars) == 6 and bars[-1]["t"] == yday.isoformat()


def test_H5_NEGATIVE_no_frame_is_an_omission_never_an_exception(monkeypatch):
    import sepa.prices as P
    monkeypatch.setattr(P, "load_prices", lambda *_a, **_k: None)
    assert RT._bars_for("DEAD") == []
    monkeypatch.setattr(P, "load_prices", lambda *_a, **_k: pd.DataFrame())
    assert RT._bars_for("DEAD") == []


def test_H5_the_window_is_still_the_trailing_days(monkeypatch):
    import sepa.prices as P
    today = datetime.now(ET).date()
    yday = today - pd.Timedelta(days=1)
    monkeypatch.setattr(P, "load_prices", lambda *_a, **_k: _frame(40, yday))
    assert len(RT._bars_for("AAPL", days=10)) == 10


def test_H5_the_build_no_longer_reads_the_live_tile_bars():
    """Source guard: the rotation frame is the shared price cache split by the
    app's ONE session test, not chart_maps.bars_for (which overlays today's
    live bar for the tiles, on purpose, and must keep doing so THERE)."""
    import ast
    tree = ast.parse(_src("rotation/tracker.py"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_bars_for")
    imported = {a.asname or a.name for n in ast.walk(fn)
                if isinstance(n, ast.ImportFrom) for a in n.names}
    called = {n.func.attr for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    named = {n.func.id for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "bars_for" not in imported and "bars_for" not in called
    assert "with_today_bar" not in imported and "with_today_bar" not in called
    assert "split_today_partial" in imported and "split_today_partial" in named
    assert "load_prices" in called
