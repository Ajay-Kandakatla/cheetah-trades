"""📋 The Bonde PICK LINE (`sepa/bonde_picks.py`), Ajay 2026-09-20.

The negatives carry this file, and they carry it for one reason: every leg here
is a claim about a company, made in HIS words, on a board he reads. The three
ways to get that wrong are all pinned below.

  1. An UNKNOWN rendered as a FAIL. A cold cache, a fiscal pair that is not a
     year apart and a year-ago loss are all "we cannot say". A ✗ beside his
     sentence says the company failed his criterion.
  2. A confident number off arithmetic. `qoq.yoy_pct` divides by |base|, so
     −0.20 → +0.30 is +250% — a sign flip printed as a doubling. Every y/y EPS
     leg refuses a non-positive base.
  3. A `why` code with no sentence beside it. ONE vocabulary (`WHY_CODES`); the
     frontend's WHY_TEXT keys are pinned equal to it by the contract sweep, and
     a board walked end to end here must never serve a code outside it.

Plus the cost pin: `bonde.board()` reaches no network at all — `requests.get`
is monkeypatched to raise and a full stubbed board is built through it.
"""
from __future__ import annotations

import importlib
import re

import pytest

from sepa import bonde as BD
from sepa import bonde_picks as BP
from sepa import first_seen as FS
from sepa import qoq as Q


# ─────────────────────────────────────────────────────────── fixtures
def scan_row(symbol, **kw):
    f = {"eps_q_series": kw.get("eps"),
         "rev_q_series": kw.get("rev", [200_000_000, 0, 0, 0, 100_000_000]),
         "q_period_series": kw.get("periods"),
         "inst_ownership_pct": kw.get("inst"),
         "sales": kw.get("sales") or {}}
    if "inst" not in kw:
        f.pop("inst_ownership_pct")
    return {"symbol": symbol, "name": kw.get("name"), "sector": kw.get("sector"),
            "last_close": 10.0, "fundamentals": f}


def pillar(growth=100.0, **kw):
    return {"passed": kw.get("passed", True), "growth_yoy_pct": growth,
            "tier": kw.get("tier", "strong"), "score": 80,
            "accelerating": kw.get("accelerating", True),
            "consecutive_growth_q": kw.get("consec", 4),
            "sales_led": None, "reason": ""}


def legs(symbol="AAA", *, row=None, cleared=True, **kw):
    sr = scan_row(symbol, **kw)
    p = pillar(kw.get("growth", 100.0))
    r = {"growth_yoy_pct": kw.get("growth", 100.0),
         "prior_yoy_pct": kw.get("prior", 50.0),
         "period_ok": kw.get("period_ok", True),
         "prior_hole": kw.get("prior_hole", False)}
    r.update(row or {})
    return BP.legs_from_scan_row(sr, p, r, cleared)


# ══════════════════════════════════════════ the contract: keys, quotes, cites
def test_the_served_leg_keys_are_exactly_the_CRITERIA_computed_keys():
    got = set(legs(eps=[0.30, 0.10, 0.09, 0.08, 0.10, 0.05],
                   periods=[8105, 8104, 8103, 8102, 8101, 8100],
                   sector="Technology", inst=30.0))
    assert got == set(BP.SCAN_KEYS)
    assert set(BP.SCAN_KEYS) | set(BP.CACHE_KEYS) == set(BP.COMPUTED_KEYS)
    assert len(BP.COMPUTED_KEYS) == 14
    assert len(BP.LEGEND_ONLY_KEYS) == 6
    assert len(BP.CRITERIA) == 20


def test_every_criterion_carries_a_VERBATIM_sentence_and_one_of_his_links():
    """A criterion without his sentence is this app's opinion in his voice."""
    for c in BP.CRITERIA:
        assert c["quote"] and c["quote"].strip(), c["key"]
        assert ("stockbee.blogspot.com" in c["url"]
                or "x.com/PradeepBonde" in c["url"]), c["key"]
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", c["date"]), c["key"]
        assert c["source"] in ("stockbee", "x"), c["key"]
        assert c["data"], c["key"]
        if not c["computed"]:
            assert c["not_computed_why"], c["key"]


# The frozen set: every sentence this module is allowed to put in his mouth.
# A paraphrase — even a tidier one — fails here.
ALLOWED_QUOTES = frozenset({
    "I only track companies whose earnings are up 100% or more quarter over "
    "quarter and the earnings should be at least 5 cents.",
    "Sales/revenue should be up 5% or more.",
    "Now what one is looking for is earnings acceleration.",
    "Even better is stock which has no analyst coverage and is neglected.",
    "Besides that I look for price action on that stock by looking at how much "
    "they are up in last 65 days or so. I am looking for stocks which have not "
    "rallied in anticipation of earnings.",
    "An earnings surprise on stock which has not rallied significantly will "
    "lead to breakout next day.",
    "PEAD or post earnings announcement drift is a well studied and proven "
    "market anomaly.",
    "On such stocks a significant earnings acceleration compared to last year "
    "same quarter as well as quarter over quarter is what to look for. I like "
    "to look for companies which had earnings acceleration of 100% plus in "
    "such cases.",
    "Stock with no analyst coverage",
    "Float below 25 million is ideal for this. The best moves happen on float "
    "below 10 million. Earnings breakouts on companies with 100 million plus "
    "float tend to have pullbacks.",
    "Beats analyst estimate",
    "In top 10 sector",
    "Top Sector",
    "Earnings 40% plus",
    "Marketsmith to find earnings and earnings trends, float, fund holding",
    "The most explosive Episodic Pivots occur in stocks that have Gone Public "
    "in the last 10 years and have a capitalization of less than $ 10 billion "
    "once they enter their growth phase.",
    "They will have very low capitalization, low fund ownership, and low "
    "interest from analysts and general investors.",
    "This scan finds stocks incorporated or IPOed in last 10 years that have a "
    "market capitalization below 11 billion and have two quarters of revenue "
    "growth of 39% plus.",
    "Stocks with lower floats (under 25M shares) tend to see the biggest "
    "episodic pivot moves … This coupled with high short interest ( 5 plus "
    "days to cover) can result in explosive moves",
    "If you want to make money from Earnings Episodic Pivots, focus on three "
    "sectors: technology, healthcare, and consumer discretionary.",
    "there is 100 times more money on story stocks EP … Understanding what "
    "theme is working and finding story EP in them is now my major focus",
    "Post earnings announcements drift is well known markrt anomaly and EP is "
    "based on that.",
    "Keep a watchlist of stocks that reacted positively to earnings (earnings "
    "Episodic Pivots) , they always offer another lower risk entry opportunity "
    "after few weeks or months.",
})


def test_SOURCE_GUARD_every_quote_is_one_of_his_frozen_sentences():
    for c in BP.CRITERIA:
        for part in c["quote"].split(" · "):
            assert part in ALLOWED_QUOTES, (c["key"], part)


def test_NEGATIVE_a_paraphrase_of_one_of_his_sentences_is_not_allowed():
    """The guard has to bite, or it is decoration."""
    assert "Sales should be up 5% or more." not in ALLOWED_QUOTES
    assert "Sales/revenue should be up 5% or more." in ALLOWED_QUOTES


def test_the_two_EARNINGS_legs_cite_the_post_that_carries_THAT_leg():
    """He names BOTH bases and they are in different posts: the y/y leg is the
    2010 sentence ('compared to last year same quarter'), the sequential leg is
    the 2007 sentence ('up 100% or more quarter over quarter')."""
    crit = {c["key"]: c for c in BP.CRITERIA}
    assert crit["eps_yoy_100"]["url"] == BP.URL_2010
    assert "last year same quarter" in crit["eps_yoy_100"]["quote"]
    assert crit["eps_seq_100"]["url"] == BP.URL_2007
    assert "quarter over quarter" in crit["eps_seq_100"]["quote"]


def test_NEGATIVE_no_key_or_label_carries_a_MOMENTUM_word():
    """His correction: *"momentum does not need to be a criteria for his pics
    … I am looking fro static info"*. A dynamic leg sneaking onto this line is
    the one thing the ask ruled out by name."""
    banned = ("momentum", "rs_", "persistence", "return", "today", "rel_")
    for c in BP.CRITERIA:
        blob = (c["key"] + " " + c["label"]).lower()
        for word in banned:
            assert word not in blob, (c["key"], word)
    for k in BP.COMPUTED_KEYS:
        for word in banned:
            assert word not in k.lower(), (k, word)


def test_NEGATIVE_no_quote_or_label_says_bounce():
    """STANDING: 'reversal', never 'bounce', on any surface he reads."""
    blob = " ".join(c["quote"] + c["label"] + c["data"] for c in BP.CRITERIA)
    assert "bounce" not in blob.lower()


# ══════════════════════════════════════════════════ the ONE why vocabulary
def test_INCOME_BASE_TO_WHY_covers_every_qoq_base_state_except_OK():
    """Read off `qoq`'s own names, never retyped: a rename there must be an
    ImportError here, not a silently missing sentence on his board."""
    base_names = {getattr(Q, n) for n in dir(Q) if n.startswith("BASE_")}
    assert set(BP.INCOME_BASE_TO_WHY) == base_names - {Q.BASE_OK}
    assert set(BP.INCOME_BASE_TO_WHY.values()) <= BP.WHY_CODES


def test_WHY_CODES_has_the_twenty_four_codes_the_frontend_is_pinned_to():
    assert len(BP.WHY_CODES) == 24
    assert BP.legend()["why_codes"] == sorted(BP.WHY_CODES)


def test_NEGATIVE_a_leg_built_with_an_unknown_why_code_raises():
    with pytest.raises(ValueError):
        BP._leg(why="bogus")
    assert BP._leg(why=None)["why"] is None
    assert BP._leg(why="no_sector")["why"] == "no_sector"


def test_every_leg_always_carries_all_three_keys():
    for leg in legs(eps=[0.30, 0.10], sector="Energy").values():
        assert set(leg) >= {"ok", "value", "why"}


# ══════════════════════════════════════════════ the scan legs, branch by branch
def test_NO_eps_series_leaves_all_four_earnings_legs_UNKNOWN_never_FALSE():
    """THE DEFECT THIS EXISTS TO STOP. A missing series is not a company that
    earns nothing — a ✗ beside his sentence is a claim, and this one would be
    made about every name the provider has no filings for."""
    got = legs(eps=None)
    for k in ("eps_5c", "eps_yoy_100", "eps_seq_100", "eps_accel"):
        assert got[k]["ok"] is None, k
        assert got[k]["why"] == "no_eps_series", k


def test_a_YEAR_AGO_LOSS_is_UNKNOWN_not_a_250_percent_tick():
    """`qoq.yoy_pct` divides by |b|: −0.20 → +0.30 comes back +250%. That is a
    sign flip rendered as a doubling, and it would tick his 100% criterion."""
    got = legs(eps=[0.30, 0.10, 0.09, 0.08, -0.20, 0.05])
    assert got["eps_yoy_100"]["ok"] is None
    assert got["eps_yoy_100"]["why"] == "year_ago_loss"
    assert got["eps_yoy_100"]["value"] is None


def test_the_five_cent_level_sits_exactly_on_his_number():
    assert legs(eps=[0.04, 0.01])["eps_5c"]["ok"] is False
    assert legs(eps=[0.05, 0.01])["eps_5c"]["ok"] is True
    assert legs(eps=[0.05, 0.01])["eps_5c"]["value"] == 0.05
    assert BP.EPS_MIN_USD == 0.05


def test_the_doubling_legs_sit_exactly_on_his_hundred_percent():
    eps = [0.20, 0.10, 0.09, 0.08, 0.10, 0.05]
    p = [8105, 8104, 8103, 8102, 8101, 8100]
    g = legs(eps=eps, periods=p)
    assert g["eps_yoy_100"]["value"] == 100.0 and g["eps_yoy_100"]["ok"] is True
    assert g["eps_seq_100"]["value"] == 100.0 and g["eps_seq_100"]["ok"] is True
    assert legs(eps=[0.19, 0.10, 0.09, 0.08, 0.10, 0.05],
                periods=p)["eps_yoy_100"]["ok"] is False


def test_a_pair_that_is_NOT_a_year_apart_makes_every_y_slash_y_leg_unknown():
    """`period_ok False` means the pair was CHECKED and is wrong. The row may
    still carry a growth number (it does on 🔎 and pivot rows) — the leg must
    refuse it anyway, so the order of the board's own blanking cannot matter."""
    got = legs(eps=[0.30, 0.10, 0.09, 0.08, 0.10, 0.05],
               growth=200.0, prior=150.0, period_ok=False)
    for k in ("eps_yoy_100", "eps_accel", "sales_5", "rev_39_x2"):
        assert got[k]["ok"] is None, k
        assert got[k]["why"] == "pair_not_a_year_apart", k
    # the SEQUENTIAL leg is a different pair and is not refused by it
    assert got["eps_seq_100"]["why"] != "pair_not_a_year_apart"


def test_an_UNVERIFIABLE_pair_still_computes_and_says_so():
    """`period_ok None` = no keys on file, so nothing could be checked. The
    tiers already print the number with the word 'unverified'; the leg does the
    same rather than pretending to a check it never made."""
    got = legs(eps=[0.30, 0.10, 0.09, 0.08, 0.10, 0.05], period_ok=None)
    assert got["eps_yoy_100"]["ok"] is True
    assert got["eps_yoy_100"]["why"] == "no_period_keys"
    assert got["sales_5"]["why"] == "no_period_keys"


def test_non_adjacent_filings_refuse_the_SEQUENTIAL_leg_by_qoqs_own_state():
    got = legs(eps=[0.30, 0.10, 0.09], periods=[8105, 8103, 8102])
    assert got["eps_seq_100"]["ok"] is None
    assert got["eps_seq_100"]["why"] == "seq_not_adjacent"
    assert got["eps_seq_100"]["why"] == BP.INCOME_BASE_TO_WHY[Q.BASE_NOT_ADJACENT]


def test_a_LOSS_MAKING_prior_quarter_refuses_the_sequential_leg_and_keeps_the_turn():
    got = legs(eps=[0.30, -0.10, 0.09], periods=[8105, 8104, 8103])
    assert got["eps_seq_100"]["ok"] is None
    assert got["eps_seq_100"]["why"] == "seq_base_non_positive"
    assert got["eps_seq_100"]["value_note"] == "to_profit"


def test_a_PRIOR_HOLE_costs_the_acceleration_and_the_two_quarter_read():
    got = legs(eps=[0.30, 0.10, 0.09, 0.08, 0.10, 0.05], prior_hole=True)
    assert got["eps_accel"]["why"] == "prior_hole"
    assert got["rev_39_x2"]["why"] == "prior_hole"
    assert got["eps_accel"]["ok"] is None and got["rev_39_x2"]["ok"] is None


def test_earnings_acceleration_is_this_quarters_y_slash_y_against_last_quarters():
    eps = [0.30, 0.12, 0.09, 0.08, 0.10, 0.10]     # +200% now, +20% prior
    got = legs(eps=eps, periods=[8105, 8104, 8103, 8102, 8101, 8100])
    assert got["eps_accel"]["ok"] is True
    assert got["eps_accel"]["value"] == {"now": 200.0, "prior": 20.0}
    slow = [0.11, 0.30, 0.09, 0.08, 0.10, 0.10]    # +10% now, +200% prior
    assert legs(eps=slow)["eps_accel"]["ok"] is False


def test_the_sales_leg_reads_the_PILLARS_rounded_seam_not_its_own_comparison():
    assert legs(cleared=True, growth=4.6)["sales_5"]["ok"] is True
    assert legs(cleared=False, growth=4.4)["sales_5"]["ok"] is False
    assert BP.SALES_FLOOR_PCT == 5.0


def test_NEGATIVE_no_sales_read_is_UNKNOWN_not_a_failed_floor():
    assert legs(cleared=None)["sales_5"]["why"] == "no_sales_read"
    assert legs(cleared=None)["sales_5"]["ok"] is None
    assert legs(cleared=True, row={"growth_yoy_pct": None})["sales_5"]["ok"] is None


def test_his_two_quarter_revenue_leg_needs_BOTH_quarters_over_his_number():
    assert legs(growth=45.0, prior=52.0)["rev_39_x2"]["ok"] is True
    assert legs(growth=45.0, prior=20.0)["rev_39_x2"]["ok"] is False
    assert legs(growth=39.0, prior=39.0)["rev_39_x2"]["ok"] is True
    assert BP.REV_TWO_Q_PCT == 39.0
    note = legs(growth=45.0, prior=52.0)["rev_39_x2"]["value_note"]
    assert "his post does not say which base" in note


def test_FUND_HOLDING_never_passes_or_fails_because_he_publishes_no_number():
    """Rule #1: reuse his number or say there isn't one. Inventing a fund-
    ownership threshold and ticking it in his voice is the whole trap."""
    assert legs(inst=60.0)["fund_holding"]["ok"] is None
    assert legs(inst=1.0)["fund_holding"]["ok"] is None
    assert legs(inst=60.0)["fund_holding"]["why"] == "no_threshold_in_his_writing"
    assert legs(inst=60.0)["fund_holding"]["value"] == 60.0
    assert "never a flow" in legs(inst=60.0)["fund_holding"]["source"]
    assert legs()["fund_holding"]["why"] == "no_inst_read"


def test_his_three_sectors_read_in_the_SCANS_vocabulary():
    """He wrote 'consumer discretionary'; the scan rows say 'Consumer
    Cyclical'. Matching his words literally would fail every name in it."""
    assert legs(sector="Consumer Cyclical")["sector_3"]["ok"] is True
    assert legs(sector="Technology")["sector_3"]["ok"] is True
    assert legs(sector="Energy")["sector_3"]["ok"] is False
    assert legs(sector=None)["sector_3"]["ok"] is None
    assert legs(sector=None)["sector_3"]["why"] == "no_sector"


# ══════════════════════════════════════════════════ the cache legs, via attach
class _Readers:
    """The five bulk readers, monkeypatched by NAME so this file works whether
    or not they have landed yet — `attach` answers {} for a reader that is not
    there, which is the same answer as a cold cache."""

    PATHS = (("sepa.board_metrics", "snapshot"),
             ("sepa.earnings_watch", "last_report_map"),
             ("short_interest.client", "short_interest_map"),
             ("sepa.analyst_pulse", "coverage_map"),
             ("sepa.ipo_age", "listing_dates_map"))


def set_readers(monkeypatch, metrics=None, reports=None, si=None,
                analysts=None, listings=None, raise_all=False):
    maps = [metrics, reports, si, analysts, listings]
    for (path, name), payload in zip(_Readers.PATHS, maps):
        mod = importlib.import_module(path)

        if raise_all:
            def fn(*a, **k):
                raise RuntimeError("reader down")
        else:
            def fn(*a, _p=payload, **k):
                return dict(_p or {})
        monkeypatch.setattr(mod, name, fn, raising=False)


def attach_one(monkeypatch, **kw):
    rows = [{"symbol": "AAA", "pick": {"legs": {}}}]
    set_readers(monkeypatch, **kw)
    BP.attach(rows)
    return rows[0]["pick"]["legs"], rows[0]["pick"]


def test_EVERY_cold_cache_reads_UNKNOWN_with_the_reason_named(monkeypatch):
    got, _ = attach_one(monkeypatch)
    expect = {"surprise": "not_on_calendar", "float_25m": "no_metrics_doc",
              "cap_10b": "no_metrics_doc", "short_dtc_5": "not_warmed",
              "neglect_analysts": "no_analyst_doc", "ipo_10y": "no_listing_date"}
    for k, why in expect.items():
        assert got[k]["ok"] is None, k
        assert got[k]["why"] == why, k


def test_NEGATIVE_a_reader_that_RAISES_leaves_unknowns_and_never_the_board(monkeypatch):
    """`board()` runs inside crons. A reader that throws must cost six legs,
    not the tab."""
    got, _ = attach_one(monkeypatch, raise_all=True)
    assert all(leg["ok"] is None for leg in got.values())
    assert got["short_dtc_5"]["why"] == "not_warmed"


def test_attach_on_rows_with_no_symbol_does_not_raise():
    rows = [{"name": "nothing"}]
    BP.attach(rows)
    assert rows[0]["pick"]["n_unknown"] == 14


# ── surprise ──────────────────────────────────────────────────────────────
def _days_ago(n):
    from datetime import timedelta
    return (BP._today() - timedelta(days=n)).isoformat()


def test_a_STALE_surprise_is_LABELLED_and_still_counts_as_his_beat(monkeypatch):
    """Rule #7 is about the reported PERIOD, and a beat two quarters ago is
    still the last thing he had to react to. The label never flips the leg."""
    got, _ = attach_one(monkeypatch, reports={
        "AAA": {"date": _days_ago(200), "surprise_pct": 12.0}})
    leg = got["surprise"]
    assert leg["ok"] is True and leg["value"] == 12.0
    assert leg["stale"] is True and leg["age_days"] == 200


def test_a_FRESH_surprise_is_not_labelled_stale(monkeypatch):
    got, _ = attach_one(monkeypatch, reports={
        "AAA": {"date": _days_ago(30), "surprise_pct": 12.0}})
    assert got["surprise"]["stale"] is False and got["surprise"]["age_days"] == 30


def test_a_MISS_is_a_fail_and_a_report_without_a_surprise_is_unknown(monkeypatch):
    got, _ = attach_one(monkeypatch, reports={
        "AAA": {"date": _days_ago(10), "surprise_pct": -8.0}})
    assert got["surprise"]["ok"] is False
    got, _ = attach_one(monkeypatch, reports={"AAA": {"date": _days_ago(10)}})
    assert got["surprise"]["ok"] is None
    assert got["surprise"]["why"] == "no_surprise_in_report"


def test_the_stale_bound_is_BUILT_from_the_named_freshness_constants():
    """Rule #7's constants by name, never a number typed twice."""
    from observability.period_freshness import FILING_LAG_DAYS, GRACE_DAYS
    assert BP.SURPRISE_STALE_DAYS == BP.QUARTER_DAYS + FILING_LAG_DAYS + GRACE_DAYS
    assert BP.SURPRISE_STALE_DAYS == 157


# ── float / cap ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("shares,ok,tier", [
    (9_900_000, True, "best"),
    (24_900_000, True, "ideal"),
    (40_000_000, False, None),
    (100_000_000, False, "pullback_prone"),
])
def test_the_float_leg_carries_BOTH_of_his_bands_and_his_pullback_warning(
        monkeypatch, shares, ok, tier):
    got, _ = attach_one(monkeypatch, metrics={"AAA": {"float_shares": shares}})
    assert got["float_25m"]["ok"] is ok
    assert got["float_25m"]["tier"] == tier


def test_a_metrics_doc_WITHOUT_the_float_key_is_not_the_same_as_no_doc(monkeypatch):
    """Docs cached before 2026-09-20 have no float at all. Reading that as 'no
    doc' would tell him to run a warm that has already run."""
    got, _ = attach_one(monkeypatch, metrics={"AAA": {"market_cap": 1e9}})
    assert got["float_25m"]["why"] == "no_float_in_doc"
    assert got["cap_10b"]["ok"] is True


def test_the_cap_leg_passes_at_his_PROSE_bound(monkeypatch):
    got, _ = attach_one(monkeypatch, metrics={"AAA": {"market_cap": 9.9e9}})
    assert got["cap_10b"]["ok"] is True
    got, _ = attach_one(monkeypatch, metrics={"AAA": {"market_cap": 1.05e10}})
    assert got["cap_10b"]["ok"] is False        # his scan line says 11B — §7.7
    got, _ = attach_one(monkeypatch, metrics={"AAA": {"float_shares": 1e6}})
    assert got["cap_10b"]["why"] == "no_cap_in_doc"


# ── short interest ────────────────────────────────────────────────────────
def test_a_REMEMBERED_MISS_is_not_the_same_answer_as_NEVER_WARMED(monkeypatch):
    got, _ = attach_one(monkeypatch, si={"AAA": {"settlement_date": None}})
    assert got["short_dtc_5"]["why"] == "no_si_record"
    got, _ = attach_one(monkeypatch)
    assert got["short_dtc_5"]["why"] == "not_warmed"


def test_the_days_to_cover_leg_sits_on_his_five_and_keeps_ok_when_stale(monkeypatch):
    got, _ = attach_one(monkeypatch, si={"AAA": {
        "settlement_date": "2026-08-31", "days_to_cover": 6.1,
        "pct_of_shares": 19.46, "stale": True, "age_days": 60}})
    leg = got["short_dtc_5"]
    assert leg["ok"] is True and leg["stale"] is True
    assert leg["as_of"] == "2026-08-31" and leg["pct_of_shares"] == 19.46
    got, _ = attach_one(monkeypatch, si={"AAA": {
        "settlement_date": "2026-08-31", "days_to_cover": 4.9}})
    assert got["short_dtc_5"]["ok"] is False
    assert BP.SHORT_DTC_MIN == 5.0


# ── analysts ──────────────────────────────────────────────────────────────
def test_NO_COVERAGE_is_his_criterion_and_the_reading_is_labelled(monkeypatch):
    """Yahoo never prints a zero — an EMPTY estimate frame is the only evidence
    of no coverage there is, so the ✓ says out loud where it came from and that
    the reading is pending his nod."""
    got, _ = attach_one(monkeypatch, analysts={"AAA": {"n_analysts": 0}})
    leg = got["neglect_analysts"]
    assert leg["ok"] is True
    assert leg["source"] == "Yahoo carries no estimate rows"
    assert leg["his_call"] and len(leg["his_call"]) > 20


def test_a_COVERED_name_fails_the_leg_and_says_by_how_many(monkeypatch):
    got, _ = attach_one(monkeypatch, analysts={"AAA": {"n_analysts": 3}})
    assert got["neglect_analysts"]["ok"] is False
    assert got["neglect_analysts"]["value_note"] == "covered by 3"


def test_NEGATIVE_an_unread_estimate_frame_is_unknown_never_no_coverage(monkeypatch):
    """A doc that predates the count, or a property that raised, is silence.
    Reading silence as 'no analyst coverage' ticks his criterion on a name the
    whole street follows."""
    got, _ = attach_one(monkeypatch, analysts={"AAA": {"n_analysts": None}})
    assert got["neglect_analysts"]["ok"] is None
    assert got["neglect_analysts"]["why"] == "no_estimate_read"
    got, _ = attach_one(monkeypatch)
    assert got["neglect_analysts"]["why"] == "no_analyst_doc"


# ── listing date ──────────────────────────────────────────────────────────
def test_the_ipo_leg_is_years_since_listing_and_names_its_own_weakness(monkeypatch):
    got, _ = attach_one(monkeypatch, listings={"AAA": "2019-01-01"})
    leg = got["ipo_10y"]
    assert leg["ok"] is True and leg["as_of"] == "2019-01-01"
    assert isinstance(leg["value"], float) and leg["value"] > 5
    assert "uncorroborated" in leg["source"]
    got, _ = attach_one(monkeypatch, listings={"AAA": "1995-01-01"})
    assert got["ipo_10y"]["ok"] is False


def test_NEGATIVE_a_listing_date_in_the_FUTURE_is_unknown_not_a_zero_year_old(
        monkeypatch):
    """A recycled ticker's profile date is the classic corruption here, and a
    future one would render as the youngest name on the board."""
    from datetime import timedelta
    future = (BP._today() + timedelta(days=30)).isoformat()
    got, _ = attach_one(monkeypatch, listings={"AAA": future})
    assert got["ipo_10y"]["ok"] is None
    assert got["ipo_10y"]["why"] == "future_listing_date"
    got, _ = attach_one(monkeypatch, listings={"AAA": "not-a-date"})
    assert got["ipo_10y"]["why"] == "no_listing_date"


# ══════════════════════════════════════════════════════ counts and coverage
def test_the_counts_always_add_up_to_his_fourteen_computed_criteria(monkeypatch):
    _, pick = attach_one(monkeypatch, metrics={"AAA": {"market_cap": 1e9,
                                                       "float_shares": 5e6}})
    assert pick["n_pass"] + pick["n_fail"] + pick["n_unknown"] == 14


def test_coverage_says_what_is_KNOWN_per_leg_over_the_rows(monkeypatch):
    rows = [{"symbol": "AAA", "pick": {"legs": {}}},
            {"symbol": "BBB", "pick": {"legs": {}}}]
    set_readers(monkeypatch, metrics={"AAA": {"market_cap": 1e9}})
    BP.attach(rows)
    cov = BP.coverage(rows)
    assert cov["cap_10b"] == {"known": 1, "rows": 2}
    assert cov["short_dtc_5"] == {"known": 0, "rows": 2}
    assert set(cov) == set(BP.COMPUTED_KEYS)


def test_the_legend_is_SERVED_whole_and_says_the_entries_are_his():
    lg = BP.legend()
    assert lg["header"] == BP.PICK_HEADER
    assert "entries are yours" in lg["header"]
    assert "nothing on it is measured" in lg["header"]
    assert lg["criteria"] is BP.CRITERIA
    assert lg["computed_keys"] == BP.COMPUTED_KEYS
    assert "YouTube" in lg["not_a_source"]
    assert "warm-si" in lg["warm_note"]


# ══════════════════════════════════════════ the board, end to end, offline
def _stub_board(monkeypatch, rows, **readers):
    from sepa import scanner, board_metrics as BM, buyable_verdict as BV
    monkeypatch.setattr(scanner, "load_latest", lambda *a, **k: {"all_results": rows})
    monkeypatch.setattr(BD, "_pivots", lambda *a, **k: {})
    monkeypatch.setattr(BD, "regime_state", lambda *a, **k: {"scanners_paused": False})
    monkeypatch.setattr(BM, "attach", lambda *a, **k: None)
    monkeypatch.setattr(FS, "record", lambda *a, **k: 0)
    monkeypatch.setattr(FS, "newly_found", lambda *a, **k: set())
    monkeypatch.setattr(FS, "first_seen_map", lambda *a, **k: {})
    assert hasattr(BV, "_bonde_pillar")
    set_readers(monkeypatch, **readers)
    return BD.board()


def _branchy_rows():
    """One row per branch this module has: a clean name, no series, a negative
    year-ago base, a non-adjacent pair, a refused pair, no period keys, and a
    row with no sector at all."""
    ok_p = [8105, 8104, 8103, 8102, 8101, 8100]
    s = {"score": 80, "tier": "strong", "growth_yoy_pct": 60.0,
         "prior_yoy_pct": 55.0, "accelerating": True, "consecutive_growth_q": 4}
    return [
        scan_row("CLEAN", eps=[0.30, 0.10, 0.09, 0.08, 0.10, 0.05],
                 periods=ok_p, sector="Technology", inst=30.0, sales=dict(s)),
        scan_row("NOEPS", periods=ok_p, sector="Healthcare", sales=dict(s)),
        scan_row("LOSSY", eps=[0.30, 0.10, 0.09, 0.08, -0.20, 0.05],
                 periods=ok_p, sector="Energy", sales=dict(s)),
        scan_row("GAPPY", eps=[0.30, 0.10, 0.09], periods=[8105, 8103, 8102],
                 sector="Technology", sales=dict(s)),
        scan_row("BADPAIR", eps=[0.30, 0.10, 0.09, 0.08, 0.10, 0.05],
                 periods=[8105, 8104, 8103, 8102, 8098, 8097],
                 sector="Technology", sales=dict(s)),
        scan_row("NOKEYS", eps=[0.30, 0.10, 0.09, 0.08, 0.10, 0.05],
                 sector="Technology", sales=dict(s)),
        scan_row("NOSECT", eps=[0.30, 0.10, 0.09, 0.08, 0.10, 0.05],
                 periods=ok_p, sales=dict(s)),
    ]


def test_EVERY_why_served_by_a_real_board_is_in_the_ONE_vocabulary(monkeypatch):
    """THE PIN BEHIND THE FRONTEND'S WHY_TEXT. Every branch of every leg is
    walked through the real `board()`, and a code with no sentence beside it
    would reach the page as a raw token."""
    b = _stub_board(monkeypatch, _branchy_rows(),
                    metrics={"CLEAN": {"market_cap": 1e9, "float_shares": 5e6}},
                    reports={"CLEAN": {"date": _days_ago(10), "surprise_pct": 5.0}},
                    si={"CLEAN": {"settlement_date": None}},
                    analysts={"CLEAN": {"n_analysts": 0},
                              "LOSSY": {"n_analysts": None}},
                    listings={"CLEAN": "2019-01-01"})
    seen = set()
    n_rows = 0
    for sec in b["sections"].values():
        for r in sec:
            n_rows += 1
            legs_ = r["pick"]["legs"]
            assert set(legs_) == set(BP.COMPUTED_KEYS), r["symbol"]
            for k, leg in legs_.items():
                assert leg["why"] is None or leg["why"] in BP.WHY_CODES, (k, leg)
                seen.add(leg["why"])
            assert (r["pick"]["n_pass"] + r["pick"]["n_fail"]
                    + r["pick"]["n_unknown"]) == 14, r["symbol"]
    assert n_rows >= 6
    # the branches really were exercised, not merely tolerated
    for why in ("no_eps_series", "year_ago_loss", "seq_not_adjacent",
                "no_sector", "not_on_calendar", "no_si_record"):
        assert why in seen, why
    assert b["pick_legend"]["why_codes"] == sorted(BP.WHY_CODES)
    assert set(b["pick_coverage"]) == set(BP.COMPUTED_KEYS)


def test_NEGATIVE_the_whole_board_makes_ZERO_network_calls(monkeypatch):
    """The cost rule: five bulk Mongo reads and nothing else. A provider read
    per row is how a tab stops being served."""
    import requests

    def boom(*a, **k):
        raise AssertionError("the board path reached the network")

    for name in ("get", "post", "request"):
        monkeypatch.setattr(requests, name, boom)
    b = _stub_board(monkeypatch, _branchy_rows())
    assert b["sections"]["strong"]
    assert all(r["pick"]["legs"]["short_dtc_5"]["ok"] is None
               for v in b["sections"].values() for r in v)


def test_a_pivot_mismatch_row_carries_UNKNOWN_y_slash_y_legs(monkeypatch):
    """Those rows have their growth numbers BLANKED after `_row` builds them.
    The legs must not depend on which happened first."""
    rows = _branchy_rows()
    b = _stub_board(monkeypatch, rows)
    by_sym = {r["symbol"]: r for v in b["sections"].values() for r in v}
    bad = by_sym.get("BADPAIR")
    if bad is not None:
        for k in ("eps_yoy_100", "sales_5", "rev_39_x2", "eps_accel"):
            assert bad["pick"]["legs"][k]["ok"] is None, k
            assert bad["pick"]["legs"][k]["why"] == "pair_not_a_year_apart", k


def test_the_board_serves_the_legend_ONCE_and_never_a_count_to_render(monkeypatch):
    b = _stub_board(monkeypatch, _branchy_rows())
    assert b["pick_legend"]["header"] == BP.PICK_HEADER
    assert len(b["pick_legend"]["criteria"]) == 20
    # served for the doc and coverage, and rendered nowhere — the FE contract
    # sweep pins that the components never read these three.
    row = next(r for v in b["sections"].values() for r in v)
    assert {"n_pass", "n_fail", "n_unknown"} <= set(row["pick"])


# ══════════════════════════════════════════════════════════ import hygiene
def test_SOURCE_GUARD_the_five_readers_are_imported_INSIDE_attach():
    """`short_interest.client._main` imports `sepa.bonde`, which imports this
    module. A top-level import in either direction closes the cycle."""
    src = open(BP.__file__).read()
    head = src.split("def attach(", 1)[0]
    imports = [ln.strip() for ln in head.splitlines()
               if ln.startswith(("import ", "from "))]      # top level only
    for token in ("short_interest", "board_metrics", "analyst_pulse",
                  "ipo_age", "earnings_watch"):
        assert not any(token in ln for ln in imports), token
    # and what it DOES import at module level: the constants it must not retype
    assert any("from sepa.sales import SALES_FLOOR_PCT" in ln for ln in imports)
    assert any("period_freshness" in ln for ln in imports)


def test_SOURCE_GUARD_bonde_picks_never_imports_the_board_it_feeds():
    src = open(BP.__file__).read()
    assert "import bonde" not in src
    assert "from sepa.bonde" not in src


def test_SOURCE_GUARD_the_module_says_nothing_here_is_measured():
    src = open(BP.__file__).read()
    assert "NOTHING HERE IS MEASURED" in src
    assert "YouTube summary is NOT a source" in src or "YouTube" in BP.NOT_A_SOURCE
