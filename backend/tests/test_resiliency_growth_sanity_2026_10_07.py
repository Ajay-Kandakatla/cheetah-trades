"""🛡️ 🚀 two legs first, SNDK's missing numbers, and every gap says why (2026-10-07 b).

Ajay 2026-10-07, replying to "say if you want DBRG-style one-leg names out of
the top block": "yes please also no #s for SNDK can you do a deep analysis of
data and make sure you do a sanity chcek fo missing data pieces over all."

Pins: the 🚀 order (both ranked legs, then one, then none); a reason code on
every leg and NO bare dash on any chip; his rule #7 on the sales leg
(`SALES_AGREE_REQUIRED`, compared on the 2-dp field, the 1-dp fallback with
its own tolerance); an ETF never ranks; a filing `STALE_FILING_QUARTERS`
behind the quarter now due never ranks; the coverage line + fold only on the
🚀 order (Rule #5); the fates that landed. POSITIVE and NEGATIVE cases.
Hermetic: every `build` gets `fund_fn` AND `etf_fn` injected.
"""
from __future__ import annotations

import inspect
import json
from datetime import date

import pytest

from chart_maps import resiliency_tab as R
from sepa import etf_info, qoq, research, symbols as S
from tests.test_resiliency_tab import (CAL, NOW, SESSION, SNAPS, _events, _frame,  # noqa: F401
                                       _no_numpy, _spy_frame)

TODAY = date(2026, 10, 7)
CACHED = 1790700000.0
PER = [8105, 8104, 8103, 8102, 8101, 8100, 8099, 8098]          # FY2026 Q2 newest-first


def _fund(*, rev_pct=None, sales1=None, eps_pct=None, rev=None, eps=None, ni=None,
          periods=PER, src="massive"):
    return {"sales": {"growth_yoy_pct": sales1} if sales1 is not None else {},
            "rev_growth_q_pct": rev_pct, "q_eps_growth_pct": eps_pct,
            "q_period_series": periods, "rev_q_series": rev, "eps_q_series": eps,
            "ni_q_series": ni, "_source": src, "cached_at": CACHED}


# VST: both legs agree with their own series
VST = _fund(rev_pct=-5.48, eps_pct=-6.17, rev=[4.0e9, 4.1e9, 4.1e9, 4.1e9, 4.232e9, 4.0e9],
            eps=[0.76, 1.0, 1.0, 1.0, 0.81, 1.0])
# SNDK as cached today (MEASURED, SPEC §1.2)
SNDK_PER = [8107, 8106, 8105, 8104, 8103, 8102]
SNDK = _fund(periods=SNDK_PER, src="hybrid",
             rev=[8.965e9, 5.95e9, 3.025e9, 2.308e9, 1.901e9, 1.695e9],
             eps=[44.83, 23.03, 5.15, 0.75, None, -13.33],
             ni=[6.903e9, None, None, None, -23e6, None])
# SNDK after the heal (yfinance shape, calendar periods)
SNDK_HEALED = _fund(periods=[8105, 8104, 8103, 8102, 8101, 8100], src="yfinance",
                    rev_pct=371.59, eps_pct=27581.25,
                    rev=[8.965e9, 5.95e9, 3.025e9, 2.308e9, 1.901e9, 1.695e9],
                    eps=[44.0, 23.03, 5.15, 0.75, -0.16, -13.33])
# BAC-like: stored sales 19.25 vs its own series 3.67
BAC = _fund(rev_pct=19.25, eps_pct=10.0, rev=[1.0367e9, 1, 1, 1, 1.0e9, 1],
            eps=[1.1, 1, 1, 1, 1.0, 1])
# PBF-like: sales ranked, EPS year-ago loss (one leg)
PBF = _fund(rev_pct=56.25, eps_pct=15180.0, rev=[9.0e9, 1, 1, 1, 5.76e9, 1],
            eps=[7.54, 1, 1, 1, -0.05, 1])


def _chip(f, **k):
    g = R.growth_read(f, **k)
    R.score_growth([g])
    return g, R.growth_chip(g)


# --------------------------------------------------------------------------
# 1 — SNDK as cached today
# --------------------------------------------------------------------------
def test_sndk_as_cached_today_shows_its_sales_and_says_why_eps_is_blank():
    g, chip = _chip(SNDK, today=TODAY)
    assert g["sales_series_pct"] == 371.59
    assert g["sales_reason"] == "stored_missing" and not g["sales_ranked"]
    assert g["eps_reason"] == "year_ago_loss" and g["eps_year_ago_ni"] == -23e6
    assert g["eps_yoy_pct"] is None and not g["eps_ranked"]
    assert chip == "Sales +371.6%* · EPS yr-ago loss YoY (FY2026 Q4)"
    st = R._growth_stat(g)
    assert "$8.97B vs $1.90B" in st and "net income -$23.0M" in st
    assert "research refresh" in st
    assert R.coverage_class(g, bars=300, min_bars=research.MIN_RESEARCH_BARS) == "pending"
    assert g["score"] is None and g["legs"] == 0


def test_sndk_after_the_heal_is_one_leg_sales_ranked():
    g, chip = _chip(SNDK_HEALED, today=TODAY)
    assert g["sales_ranked"] and g["sales_reason"] is None
    assert g["eps_base"] == "non_positive" and g["eps_reason"] == "year_ago_loss"
    assert not g["eps_ranked"] and g["legs"] == 1
    assert chip == "Sales +371.6% · EPS yr-ago loss YoY (Q2 2026)"
    assert "sign flip" in R._growth_stat(g)


# --------------------------------------------------------------------------
# 3 — his YES: both legs first, then one, then none (the DBRG negative)
# --------------------------------------------------------------------------
def _row(sym, *, score, legs, eps_ranked):
    return {"symbol": sym, "resiliency": {"t1": None, "growth": {
        "score": score, "legs": legs, "eps_ranked": eps_ranked}}}


ROWS = [_row("NONE", score=None, legs=0, eps_ranked=False),
        _row("SNDK_LIKE", score=99.3, legs=1, eps_ranked=False),
        _row("DBRG_LIKE", score=99.4, legs=1, eps_ranked=True),
        _row("TWO", score=40.0, legs=2, eps_ranked=True)]


def test_order_two_legs_then_one_then_none():
    order = [r["symbol"] for r in sorted(ROWS, key=lambda r: R.order_key(r, R.SORT_GROWTH))]
    assert order == ["TWO", "DBRG_LIKE", "SNDK_LIKE", "NONE"]


def test_NEG_a_one_leg_name_with_a_higher_score_still_sorts_after_every_two_leg_name():
    rows = ROWS + [_row("TWO_LOW", score=1.0, legs=2, eps_ranked=True)]
    order = [r["symbol"] for r in sorted(rows, key=lambda r: R.order_key(r, R.SORT_GROWTH))]
    assert order.index("TWO_LOW") < order.index("DBRG_LIKE")
    assert order.index("TWO_LOW") < order.index("SNDK_LIKE")


def test_NEG_the_old_key_would_put_dbrg_first_mutation_guard():
    def old_key(r):
        g = r["resiliency"]["growth"]
        sc = g.get("score")
        return (sc is None, not bool(g.get("eps_ranked")), -(sc or 0.0), r["symbol"])
    old = [r["symbol"] for r in sorted(ROWS, key=old_key)]
    new = [r["symbol"] for r in sorted(ROWS, key=lambda r: R.order_key(r, R.SORT_GROWTH))]
    assert old[0] == "DBRG_LIKE" and new != old


# --------------------------------------------------------------------------
# 4 — the sales leg obeys his rule #7
# --------------------------------------------------------------------------
def test_sales_disagreement_is_shown_with_a_star_not_ranked():
    g, chip = _chip(BAC, today=TODAY)
    assert g["sales_series_pct"] == 3.67 and g["sales_agrees"] is False
    assert g["sales_reason"] == "stored_disagrees" and not g["sales_ranked"]
    assert chip.startswith("Sales +19.3%* · ")
    assert "agree" in R._growth_stat(g)
    v, _c = _chip(VST, today=TODAY)
    assert v["sales_ranked"] and v["eps_ranked"] and v["legs"] == 2


def test_NEG_the_1dp_fallback_still_agrees_under_its_own_tolerance():
    ser = qoq.yoy_pct([1.0367e9, 1, 1, 1, 1.0e9, 1])
    f = {**BAC, "rev_growth_q_pct": None, "sales": {"growth_yoy_pct": round(ser, 1)}}
    g = R.growth_read(f, today=TODAY)
    assert g["sales_stored_pct"] == 3.7 and g["sales_ranked"] and g["sales_reason"] is None
    # the 2-dp tolerance alone would refuse it — the verifier-4 trap
    assert abs(3.7 - ser) > R.PCT_AGREE_TOL and abs(3.7 - ser) <= R.PCT_AGREE_TOL_1DP


def test_sales_agree_required_off_ranks_bac_the_revert_works(monkeypatch):
    monkeypatch.setattr(R, "SALES_AGREE_REQUIRED", False)
    g, chip = _chip(BAC, today=TODAY)
    assert g["sales_ranked"] and g["sales_reason"] == "stored_disagrees"
    assert chip.startswith("Sales +19.3% · ")


# --------------------------------------------------------------------------
# 5 — stale filings
# --------------------------------------------------------------------------
def _per_from(top: int, n: int = 8) -> list:
    return [top - i for i in range(n)]


def _stale_fund(top):
    return _fund(rev_pct=10.0, eps_pct=10.0, periods=_per_from(top),
                 rev=[1.1e9, 1, 1, 1, 1.0e9, 1], eps=[1.1, 1, 1, 1, 1.0, 1])


def test_stale_filing_never_ranks_and_says_so():
    g, chip = _chip(_stale_fund(8050), today=TODAY)
    assert g["state"] == "stale_filings" and g["score"] is None
    assert not g["sales_ranked"] and not g["eps_ranked"]
    assert chip == "Sales · EPS: latest filing FY2012 Q3, a year or more past due"
    assert R.expected_quarter_idx(TODAY) == 8105
    assert "quarters behind the quarter now due (Q2 2026)" in R._growth_stat(g)


@pytest.mark.parametrize("top,stale", [(8102, False), (8101, True), (8109, False)])
def test_NEG_stale_boundaries(top, stale):
    g = R.growth_read(_stale_fund(top), today=TODAY)
    assert (g["state"] == "stale_filings") is stale
    if not stale:
        assert g["sales_ranked"] and g["eps_ranked"]


def test_NEG_no_today_runs_no_stale_check():
    g = R.growth_read(_stale_fund(8050))
    assert g["state"] == "read" and g["sales_ranked"] and g["expected_idx"] is None


def test_NEG_stale_quarters_constant_is_live(monkeypatch):
    monkeypatch.setattr(R, "STALE_FILING_QUARTERS", 99)
    assert R.growth_read(_stale_fund(8050), today=TODAY)["state"] == "read"


# --------------------------------------------------------------------------
# 6 — ETF
# --------------------------------------------------------------------------
def test_etf_never_ranks_even_with_figures():
    g, chip = _chip(VST, today=TODAY, is_etf=True)
    assert g["state"] == "etf" and g["score"] is None and g["etf"] is True
    assert chip == "Sales · EPS: ETF/fund, no filings"
    assert R._growth_stat(g).startswith("ETF/fund — no company filings; never ranked")
    aiq_like = _stale_fund(8068)                                 # AIQ-class recycled ticker
    gs = [R.growth_read(aiq_like, is_etf=True), R.growth_read(VST, is_etf=True)]
    R.score_growth(gs)
    assert all(x["score"] is None for x in gs)


# --------------------------------------------------------------------------
# 7 — year-ago net income
# --------------------------------------------------------------------------
def test_year_ago_ni_positive_with_eps_missing_is_n_a_never_loss():
    f = _fund(rev_pct=10.0, rev=[1.1e9, 1, 1, 1, 1.0e9, 1], eps=[1.1, 1, 1, 1, None, 1],
              ni=[5e6, 1, 1, 1, 4e6, 1])
    g, chip = _chip(f, today=TODAY)
    assert g["eps_reason"] == "year_ago_missing" and "EPS yr-ago n/a" in chip
    assert "loss" not in chip and g["eps_year_ago_ni"] is None
    assert R.coverage_class(g, bars=300, min_bars=220) == "one_leg"


def test_NEG_an_ni_based_loss_never_yields_a_pct_and_never_ranks():
    f = _fund(rev_pct=10.0, eps_pct=500.0, rev=[1.1e9, 1, 1, 1, 1.0e9, 1],
              eps=[1.1, 1, 1, 1, None, 1], ni=[5e6, 1, 1, 1, -4e6, 1])
    g = R.growth_read(f, today=TODAY)
    assert g["eps_reason"] == "year_ago_loss" and g["eps_yoy_pct"] is None
    assert not g["eps_ranked"] and g["eps_year_ago_ni"] == -4e6


# --------------------------------------------------------------------------
# 8 — build + rank over a mixed universe
# --------------------------------------------------------------------------
PEND = [f"PEND{i}" for i in range(7)]


def _mixed():
    frames = {"SPY": _spy_frame()}
    fund = {}
    vol = {"TWO": 9e6, "ONE": 8e6, "SMH": 7e6, "N81": 6e6, "N300": 5e6, "GAP": 4e6,
           "STALE": 3e6, "RULE": 2e6, "NOFIL": 1.5e6, "YAM": 1.2e6}
    for i, s in enumerate(PEND):
        vol[s] = 1e5 * (i + 1)                                   # PEND6 trades most
    for s, v in vol.items():
        frames[s] = _frame(n=81 if s == "N81" else (300 if s == "N300" else 400), volume=v)
    fund.update(TWO=VST, ONE=PBF, SMH=VST, STALE=_stale_fund(8050),
                GAP=_fund(rev_pct=10.0, periods=[8105, 8104, 8103, 8102, 8100, 8099, 8098, 8097],
                          rev=[1.1e9, 1, 1, 1, 1.0e9, 1]),
                RULE=_fund(rev_pct=900.0, eps_pct=900.0, rev=[5e6, 1, 1, 1, -3e6, 1],
                           eps=[1.0, 1, 1, 1, -0.1, 1]),
                NOFIL=_fund(),
                YAM=_fund(rev=[1.1e9, 1, 1, 1, None, 1], eps=[1.0, 1, 1, 1, None, 1]))
    for s in PEND:
        fund[s] = SNDK
    return frames, fund


def _mixed_entry():
    frames, fund = _mixed()
    return R.build("full", SESSION, universe_fn=lambda u: [s for s in frames if s != "SPY"],
                   frames_fn=lambda syms: {s: frames[s] for s in syms if s in frames},
                   events_fn=lambda a, b: _events(), calendar_fn=lambda: CAL,
                   fund_fn=lambda syms: dict(fund), etf_fn=lambda syms: {"SMH"} & set(syms))


WANT_GAP = {"TWO": "two_legs", "ONE": "one_leg", "SMH": "etf", "N81": "new_listing",
            "N300": "not_researched", "GAP": "period_gap", "STALE": "stale_filings",
            "RULE": "by_rule", "NOFIL": "no_filings", "YAM": "year_ago_missing",
            **{s: "pending" for s in PEND}}


def test_build_classes_every_card_and_the_identity_holds():
    e = _mixed_entry()
    got = {s: rd["growth"]["gap"] for s, rd in e["reads"].items()}
    assert got == WANT_GAP
    assert e["reads"]["N81"]["growth"]["bars"] == 81
    cov = e["growth_coverage"]
    assert sum(cov["classes"].values()) == cov["n"] == len(e["reads"]) == 17
    assert cov["min_bars"] == research.MIN_RESEARCH_BARS
    assert cov["ttl_days"] == research.CACHE_TTL_SEC // 86400
    assert cov["pending_legs"] == 7 and cov["n_doc"] == 15


def test_growth_line_and_gaps_exact_strings():
    e = _mixed_entry()
    cov = e["growth_coverage"]
    asof = R._as_of_day(CACHED)
    assert R.growth_line(cov) == (
        "\U0001F680 Growth on file: 1 both legs · 1 one leg · 7 pending refresh · 1 blank by "
        "rule · no figure 7 (1 ETF/fund, 1 new listing, 1 not researched, 1 no quarterly "
        "figures, 1 a year past due, 1 quarters not a year apart, 1 year-ago quarter missing) "
        f"· of 17 · 7 figures marked * wait on a research refresh · most figures cached {asof}.")
    blk = R.growth_gaps_block(cov)
    assert blk["summary"] == "Why a card has no ranked growth — most-traded names first"
    lines = blk["lines"]
    assert [ln.split(" (")[0] for ln in lines] == [
        "pending refresh", "blank by rule", "ETF/fund", "new listing", "not researched",
        "no quarterly figures", "a year past due", "quarters not a year apart",
        "year-ago quarter missing"]
    assert lines[0].endswith("— PEND6, PEND5, PEND4, PEND3, PEND2 +2 more")
    assert len(cov["top"]["pending"]) == R.GROWTH_GAP_TOP
    assert "fewer than 220 daily bars" in lines[3] and lines[3].endswith("— N81")
    assert "$0.10" in lines[1] and "$1M" in lines[1]


def test_rank_orders_two_legs_first_on_the_built_entry():
    e = _mixed_entry()
    rows, counts, *_ = R.rank(e, SNAPS, None, now=NOW, sort=R.SORT_GROWTH)
    legs = [int(r["resiliency"]["growth"]["legs"] or 0)
            if r["resiliency"]["growth"]["score"] is not None else 0 for r in rows]
    assert legs == sorted(legs, reverse=True)
    assert rows[0]["symbol"] == "TWO" and rows[1]["symbol"] == "ONE"


# --------------------------------------------------------------------------
# 9 — Rule #5: the line + fold only on the 🚀 order
# --------------------------------------------------------------------------
def test_NEG_growth_line_only_on_the_growth_sort_and_never_warming_or_error():
    e = _mixed_entry()
    rows, counts, filters, today, _su = R.rank(e, SNAPS, None, now=NOW, sort=R.SORT_GROWTH)
    g = R.ready_block(counts, entry=e, now=NOW, sort=R.SORT_GROWTH, filters=filters, today=today)
    assert g["growth_line"] and g["growth_gaps"]["lines"] and g["growth_coverage"]["n"] == 17
    for srt in (R.SORT_TODAY, R.SORT_T1, R.DEFAULT_SORT_KEY):
        b = R.ready_block(counts, entry=e, now=NOW, sort=srt, filters=filters, today=today)
        assert b["growth_line"] is None and b["growth_gaps"] is None
        assert b["growth_coverage"] is not None
    for b in (R.warming_block(now=NOW, sort=R.SORT_GROWTH),
              R.error_block("x", now=NOW, sort=R.SORT_GROWTH)):
        assert b["growth_line"] is None and b["growth_gaps"] is None
        assert b["growth_coverage"] is None


# --------------------------------------------------------------------------
# 10 — NO chip contains a bare dash
# --------------------------------------------------------------------------
def test_NEG_no_growth_chip_contains_a_dash():
    e = _mixed_entry()
    reads = [rd["growth"] for rd in e["reads"].values()]
    extra = [R.growth_read(None), R.growth_read({}), R.growth_read(SNDK),
             R.growth_read(BAC, today=TODAY), R.growth_read(VST, is_etf=True),
             R.growth_read(_stale_fund(8050), today=TODAY), {**R.growth_read(None), "gap": "new_listing", "bars": 81}]
    for g in reads + extra:
        chip = R.growth_chip(g)
        assert "—" not in chip, chip
        assert chip.startswith(R.GROWTH_CHIP_PREFIX)
    assert R.growth_chip(extra[-1]) == "Sales · EPS: new listing, 81 bars, not researched"


# --------------------------------------------------------------------------
# 11 — the rules line is built from the constants
# --------------------------------------------------------------------------
def test_rules_line_is_built_from_constants(monkeypatch):
    base = R.growth_rule_line()
    assert "BOTH legs first" in base and "4 or more quarters past due" in base
    assert base in R.rules_block()["lines"]
    rb = R.rules_block()
    assert rb["stale_filing_quarters"] == qoq.YOY_GAP and rb["sales_agree_required"] is True
    monkeypatch.setattr(R, "EPS_MIN_BASE", 0.25)
    monkeypatch.setattr(R, "STALE_FILING_QUARTERS", 6)
    txt = R.growth_rule_line()
    assert "$0.25" in txt and "6 or more quarters past due" in txt and txt != base


# --------------------------------------------------------------------------
# 12 — the ETF set never fetches
# --------------------------------------------------------------------------
def test_NEG_etf_set_with_mongo_unavailable_never_fetches(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("fetched")
    monkeypatch.setattr(etf_info, "etf_data_for", boom)
    monkeypatch.setattr(etf_info, "is_etf", boom)
    monkeypatch.setattr(etf_info, "_coll", lambda: None)
    got = R._etf_set(["SPY", "SMH", "NVDA"])
    from supply_demand import demand_reentry as D
    from sepa import universe as U
    assert {"SPY", "QQQ", "IWM"} <= got and set(D.PINNED_ETFS) <= got
    assert "NVDA" not in got and set(U.RS_ANCHORS) <= got


def test_cached_etf_set_one_projected_find_and_raising_is_empty(monkeypatch):
    calls = []

    class Coll:
        def find(self, q, proj):
            calls.append((q, proj))
            return [{"_id": "DRAM", "payload": {"is_etf": True}},
                    {"_id": "BAD", "payload": {"is_etf": False}}]
    monkeypatch.setattr(etf_info, "_coll", lambda: Coll())
    assert etf_info.cached_etf_set(["dram", "nvda", "BAD"]) == {"DRAM"}
    assert len(calls) == 1 and calls[0][1] == {"_id": 1, "payload.is_etf": 1}

    class Boom:
        def find(self, *a, **k):
            raise RuntimeError("down")
    monkeypatch.setattr(etf_info, "_coll", lambda: Boom())
    assert etf_info.cached_etf_set(["DRAM"]) == set()
    assert etf_info.cached_etf_set([]) == set()


# --------------------------------------------------------------------------
# 13 — payload
# --------------------------------------------------------------------------
def test_NEG_payload_serializes_clean_without_numpy():
    e = _mixed_entry()
    rows, counts, filters, today, _su = R.rank(e, SNAPS, None, now=NOW, sort=R.SORT_GROWTH)
    blk = R.ready_block(counts, entry=e, now=NOW, sort=R.SORT_GROWTH, filters=filters, today=today)
    payload = {"rows": rows, "block": blk,
               "tiles": [{"badges": R.tile_badges(r), "stats": R.tile_stats(r)} for r in rows]}
    json.dumps(payload, allow_nan=False)
    _no_numpy(payload)


# --------------------------------------------------------------------------
# supporting changes
# --------------------------------------------------------------------------
def test_min_research_bars_is_named_and_used():
    assert research.MIN_RESEARCH_BARS == 220
    src = inspect.getsource(research.compute_research)
    assert "len(df) < MIN_RESEARCH_BARS" in src and "< 220" not in src


@pytest.mark.parametrize("sym", ["DBRG", "QRVO", "GBTG", "PSKY"])
def test_fates_the_dead_names_are_delisted_with_evidence(sym):
    assert S.is_delisted(sym) and len(S.DELISTED[sym]) > 40
    assert "delisted_utc" in S.DELISTED[sym]


def test_fates_modg_is_renamed_to_caly_and_never_carried_twice():
    from sepa import universe as U
    new, eff, ev = S.RENAMES["MODG"]
    assert (new, eff) == ("CALY", "2026-01-16") and "BBG000CPCVY1" in ev and "837465" in ev
    assert U._resolve_fates(["MODG", "CALY", "DBRG", "NVDA"]) == ["CALY", "NVDA"]
    assert not S.is_delisted("CALY") and not S.is_delisted("WBD")


def test_NEG_live_names_are_not_delisted():
    for s in ("WBD", "BLFS", "SLP", "SWKS", "SNDK"):
        assert not S.is_delisted(s) and s not in S.RENAMES
