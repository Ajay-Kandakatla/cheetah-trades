"""🩳 % of float — dilution, splits, filings (2026-11-24): the PURE math + verdict (short_interest.basis_math).

Ajay 2026-11-24, verbatim, in order: "Yeah please" · "Make sure we are looking for Dilution.." ·
"Also split related events and filing so we flag them in the right way"

Spec: scratchpad sidilute/spec.md REV 2 §3.3. Hermetic and pure: share-basis docs are built by hand in the FROZEN §3.1
shape with the numbers measured 11-24 (§1.5 SMTK, §1.8, the captured basis/sec/CLRO inputs). NEGATIVES throughout:
a split ON a compared date, S-11 / 13.02 / RW, the KALA near-miss, an unknown mode, a carried split not yet executed,
an ADR cover, NaN / inf / negative / bool leaves.
"""
from __future__ import annotations

import copy
import json
import math
from datetime import date

import pytest

from short_interest import basis_math as BM
from short_interest import read as SR

TODAY = date(2026, 11, 24)
FWD = date(2026, 12, 10)
OK_AT = "2026-11-24T18:05:11Z"


# ───────────────────────────────────────────── builders (the §3.1 shape, by hand)
def _ok(**kw):
    d = {"status": "ok", "read_at": OK_AT, "error": None, "error_at": None, "strikes": 0}
    d.update(kw)
    return d


def _split(e, f, t):
    return {"execution_date": e, "split_from": f, "split_to": t}


def _rec(sym="SMTK", **over):
    d = {"_id": sym, "symbol": sym, "v": 2, "settlement_date": "2026-10-30", "short_interest": 432313,
         "prev_settlement_date": "2026-10-15", "prev_short_interest": 99473, "si_change_pct": 334.6,
         "days_to_cover": 1.0, "float_shares": 546875, "float_asof": "2026-11-02",
         "shares_outstanding": 1035799, "shares_asof": "2026-11-02"}
    d.update(over)
    return d


SMTK_COVERS = [{"as_of": "2026-05-18", "shares": 21446213, "form": "10-Q", "filed": "2026-05-20"},
               {"as_of": "2026-08-12", "shares": 28263733, "form": "10-Q", "filed": "2026-08-14"},
               {"as_of": "2026-11-11", "shares": 4859369, "form": "10-Q", "filed": "2026-11-13"}]
SMTK_FILINGS = [{"form": "8-K", "filed": "2026-11-23", "items": "5.03,9.01"},
                {"form": "10-Q", "filed": "2026-11-13", "items": ""},
                {"form": "S-4", "filed": "2026-11-13", "items": ""},
                {"form": "8-K", "filed": "2026-11-04", "items": "1.01,9.01"},
                {"form": "S-3", "filed": "2026-09-18", "items": ""}]
SMTK_SPLITS = [_split("2026-08-21", 50, 1), _split("2026-11-23", 5, 1)]
SMTK_TRACK = {"value": 546875, "since": "2026-11-02", "shares": 1035799, "shares_asof": "2026-11-02",
              "basis_asof": "2026-11-02", "origin": "si_doc", "carried": []}


def _doc(sym="SMTK", *, covers=None, filings=None, splits=None, rtype="CS", yahoo="default", track=None,
         ref=None, sec=None, sp=None):
    d = {"_id": sym, "v": 1, "checked_at": OK_AT,
         "ref": ref if ref is not None else _ok(cik="0001817760", type=rtype),
         "sec": sec if sec is not None else _ok(since="2026-08-01", top_accn="a",
                                                covers=SMTK_COVERS if covers is None else covers,
                                                filings=SMTK_FILINGS if filings is None else filings),
         "splits": sp if sp is not None else _ok(since="2026-08-01",
                                                 rows=SMTK_SPLITS if splits is None else splits),
         "yahoo": ({"float_shares": 546875, "shares_outstanding": 4859369, "as_of": "2026-11-18"}
                   if yahoo == "default" else yahoo),
         "float_track": track}
    return d


def _keys(v):
    return [f["key"] for f in v["flags"]]


@pytest.fixture
def mode(monkeypatch):
    def set_(m):
        monkeypatch.setattr(BM, "FLOAT_STALE_WHEN", m)
    return set_


# ═════════════════════════════════════════════ the split math
def test_side_and_day_after():
    assert BM.side("2026-11-02", "2026-11-23") == "pre"
    assert BM.side("2026-11-24", "2026-11-23") == "post"
    assert BM.side("2026-11-23", "2026-11-23") == "same"
    assert BM.day_after("2026-11-23") == "2026-11-24" and BM.day_after("2026-12-31") == "2027-01-01"


def test_rebase_is_the_product_both_ways():
    two = [_split("2026-09-15", 2, 1), _split("2026-10-15", 3, 1)]
    assert BM.rebase(600, "2026-09-01", "2026-10-30", two) == pytest.approx(100)
    assert BM.rebase(100, "2026-10-30", "2026-09-01", two) == pytest.approx(600)
    assert BM.rebase(28263733, "2026-08-12", "2026-11-11", SMTK_SPLITS) == pytest.approx(565274.66)
    assert BM.rebase(1000, "2026-10-01", "2026-10-30", [_split("2026-10-15", 1, 2)]) == pytest.approx(2000)


@pytest.mark.parametrize("d_from,d_to", [("2026-11-23", "2026-11-24"), ("2026-11-02", "2026-11-23")])
def test_NEGATIVE_rebase_is_None_when_a_split_executes_ON_a_compared_date(d_from, d_to):
    assert BM.rebase(1000, d_from, d_to, SMTK_SPLITS) is None


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), "x", True])
def test_NEGATIVE_rebase_of_a_missing_value_is_None(bad):
    assert BM.rebase(bad, "2026-11-02", "2026-11-24", SMTK_SPLITS) is None
    assert BM.rebase(1000, bad, "2026-11-24", SMTK_SPLITS) is None


def test_same_side():
    assert BM.same_side("2026-11-18", "2026-11-02", SMTK_SPLITS)
    assert not BM.same_side("2026-11-24", "2026-11-02", SMTK_SPLITS)
    assert not BM.same_side("2026-11-23", "2026-11-23", SMTK_SPLITS)          # ON the split
    assert BM.same_side("2026-11-24", "2026-11-02", [])


def test_split_and_ratio_words():
    assert BM.split_words(5, 1) == "1-for-5 reverse split"
    assert BM.split_words(1, 2) == "2-for-1 split"
    assert BM.split_words(2.8, 1) == "1-for-2.8 reverse split"
    assert BM.ratio_words(21.157) == "21" and BM.ratio_words(4.691) == "4.7" and BM.ratio_words(1.0001) == "1.000"
    assert BM.ratio_words(13.822) == "14" and BM.ratio_words(8.596) == "8.6"


# ═════════════════════════════════════════════ filing_kind [C13]
@pytest.mark.parametrize("form,items,kind", [
    ("S-1/A", "", "registration"), ("S-3ASR", "", "registration"), ("F-1/A", "", "registration"),
    ("S-4", "", "registration"), ("F-3MEF", "", "registration"), ("s-1", "", "registration"),
    ("424B5", "", "prospectus"), ("424B3", "", "prospectus"),
    ("8-K", "1.01,3.02", "unregistered_sale"), ("8-K", "1.01,3.02,7.01,9.01", "unregistered_sale"),
    ("8-K", "5.03,9.01", "charter"), ("8-K", "3.03,5.03,8.01,9.01", "charter"),
    ("8-K", "3.02,5.03", "unregistered_sale"),                                 # a 3.02 wins over 5.03
    ("8-K/A", " 3.02 ", "unregistered_sale"),
])
def test_filing_kind(form, items, kind):
    assert BM.filing_kind(form, items) == kind


# 2026-11-26 sitrack A2: S-11 / S-11/A moved OUT of this list — they are registrations now (S-1 still never
# catches them by prefix; see test_si_chip_accuracy_2026_11_26.py). "S-111" / "F-11" stand in as the near-misses.
@pytest.mark.parametrize("form,items", [
    ("S-111", ""), ("F-11", ""), ("RW", ""), ("DEF 14A", ""), ("PRE 14A", ""), ("S-8", ""), ("10-Q", ""),
    ("8-K", "13.02"), ("8-K", "1.01,9.01"), ("8-K", ""), ("6-K", "3.02"), (None, "3.02"), (42, ""),
    ("S-1X", ""), ("F-10", ""),
])
def test_NEGATIVE_filing_kind_is_None(form, items):
    assert BM.filing_kind(form, items) is None


# ═════════════════════════════════════════════ track_update [C3][C4]
def test_track_fresh_from_the_record():
    t = BM.track_update(None, _rec(), SMTK_SPLITS)
    assert t == SMTK_TRACK


def test_track_unchanged_value_keeps_the_first_seen_date_across_rewarms():
    held = dict(SMTK_TRACK)
    t = BM.track_update(held, _rec(float_asof="2026-11-18", shares_outstanding=4859369, shares_asof="2026-11-18"),
                        SMTK_SPLITS)
    assert t == SMTK_TRACK


def test_track_SMX_carries_at_1_2e_5():
    held = {"value": 791704, "since": "2026-11-05", "shares": 892857, "shares_asof": "2026-11-05",
            "basis_asof": "2026-11-05", "origin": "si_doc", "carried": []}
    t = BM.track_update(held, _rec("SMX", float_shares=282748, float_asof="2026-11-24"), [_split("2026-11-09", 2.8, 1)])
    assert t["origin"] == "carried" and t["since"] == "2026-11-05" and t["value"] == 282748
    assert t["shares"] is None and t["shares_asof"] is None and t["basis_asof"] == "2026-11-10"
    assert t["carried"] == [_split("2026-11-09", 2.8, 1)]
    assert abs(282748 - 791704 / 2.8) / (791704 / 2.8) < BM.CARRY_REL_TOL


def test_NEGATIVE_track_KALA_does_not_carry_at_3e_3():
    held = {"value": 19338819, "since": "2026-09-01", "shares": 30000000, "shares_asof": "2026-09-01",
            "basis_asof": "2026-09-01", "origin": "si_doc", "carried": []}
    t = BM.track_update(held, _rec("KALA", float_shares=642712, float_asof="2026-11-20"),
                        [_split("2026-10-01", 30, 1)])
    assert t["origin"] == "si_doc" and t["since"] == "2026-11-20" and t["basis_asof"] == "2026-11-20"


def test_track_RETO_carries_on_the_k2_prefix():
    held = {"value": 3269702, "since": "2026-08-01", "shares": 4000000, "shares_asof": "2026-08-01",
            "basis_asof": "2026-08-01", "origin": "si_doc", "carried": []}
    rows = [_split("2026-09-10", 20, 1), _split("2026-10-20", 8, 1)]
    t = BM.track_update(held, _rec("RETO", float_shares=20436, float_asof="2026-11-20"), rows)
    assert t["origin"] == "carried" and t["basis_asof"] == "2026-10-21" and t["carried"] == rows


def test_track_a_match_on_the_first_of_two_splits_dates_after_the_FIRST():
    held = {"value": 1000000, "since": "2026-08-01", "shares": 2000000, "shares_asof": "2026-08-01",
            "basis_asof": "2026-08-01", "origin": "si_doc", "carried": []}
    rows = [_split("2026-09-10", 10, 1), _split("2026-12-20", 4, 1)]
    t = BM.track_update(held, _rec("X", float_shares=100000, float_asof="2026-11-20"), rows)
    assert t["basis_asof"] == "2026-09-11" and t["carried"] == rows[:1]


def test_NEGATIVE_track_value_changed_with_splits_unread_is_fresh():
    t = BM.track_update(dict(SMTK_TRACK), _rec(float_shares=109375, float_asof="2026-12-01"), None)
    assert t["origin"] == "si_doc" and t["since"] == "2026-12-01"


@pytest.mark.parametrize("prev", [None, {}, "x", {"value": 0, "since": "2026-11-02"}, {"value": 5, "since": "bad"},
                                  {"value": float("nan"), "since": "2026-11-02"}])
def test_NEGATIVE_track_malformed_prev_is_fresh(prev):
    assert BM.track_update(prev, _rec(), SMTK_SPLITS) == SMTK_TRACK


@pytest.mark.parametrize("over", [{"float_shares": None}, {"float_shares": 0}, {"float_asof": None}, {"v": 1}])
def test_NEGATIVE_track_needs_a_float_and_its_date(over):
    assert BM.track_update(None, _rec(**over), SMTK_SPLITS) is None


# ═════════════════════════════════════════════ stale_trigger modes
def test_stale_trigger_modes(mode):
    smtk = (432313, 546875, 1035799, 4859369)
    meds = (371417, 1455606, 5182529, 5724857)
    jeld = (8033885, 80352436, 86763382, 86774941)
    want = {"any_increase": (True, True, True), "added_exceeds_float": (True, False, False),
            "tier_moves": (True, True, False)}
    for m, (a, b, c) in want.items():
        mode(m)
        assert (BM.stale_trigger(*smtk), BM.stale_trigger(*meds), BM.stale_trigger(*jeld)) == (a, b, c), m


@pytest.mark.parametrize("m", ["", "ANY_INCREASE", None, "added"])
def test_NEGATIVE_unknown_mode_never_fires(mode, m):
    mode(m)
    assert BM.stale_trigger(432313, 546875, 1035799, 4859369) is False


def test_NEGATIVE_stale_trigger_missing_inputs(mode):
    mode("tier_moves")
    assert BM.stale_trigger(None, 546875, 1035799, 4859369) is False
    assert BM.stale_trigger(432313, None, 1035799, 4859369) is False
    assert BM.stale_trigger(432313, 546875, 1035799, float("nan")) is False


# ═════════════════════════════════════════════ change_across_split [C2]
def test_change_OMEX_and_KNDI():
    o = BM.change_across_split(195353, "2026-10-30", 4766804, "2026-10-15", [_split("2026-10-29", 25, 1)])
    assert o["pct"] == 2.5 and o["prev_adj"] == 190672 and o["same_day"] is False
    assert o["words"] == ("the 1-for-25 reverse split 10/29 turns the 4,766,804 counted then into 190,672 of "
                          "today's shares")
    k = BM.change_across_split(127620, "2026-10-30", 1198836, "2026-10-15", [_split("2026-10-16", 10, 1)])
    assert k["pct"] == 6.5 and k["prev_adj"] == 119884


def test_change_two_splits_is_the_product():
    c = BM.change_across_split(1100, "2026-10-30", 6000, "2026-09-14",
                               [_split("2026-09-15", 2, 1), _split("2026-10-15", 3, 1)])
    assert c["prev_adj"] == 1000 and c["pct"] == 10.0 and " and the " in c["words"] and " turn " in c["words"]


@pytest.mark.parametrize("e", ["2026-10-30", "2026-10-15"])
def test_NEGATIVE_change_split_ON_a_settlement_day_gives_no_pct(e):
    c = BM.change_across_split(1000, "2026-10-30", 25000, "2026-10-15", [_split(e, 25, 1)])
    assert c["pct"] is None and c["prev_adj"] is None and c["same_day"] is True
    assert c["words"].endswith("a settlement day, and which side of it that count is on is not known")


@pytest.mark.parametrize("args", [
    (195353, "2026-10-30", 4766804, "2026-10-15", [_split("2026-09-01", 25, 1)]),   # split before prevS
    (195353, "2026-10-30", 4766804, "2026-10-15", [_split("2026-11-02", 25, 1)]),   # split after S
    (195353, "2026-10-30", 4766804, "2026-10-15", []),
    (195353, "2026-10-30", 0, "2026-10-15", [_split("2026-10-29", 25, 1)]),
    (195353, "2026-10-30", None, "2026-10-15", [_split("2026-10-29", 25, 1)]),
    (195353, "2026-10-30", 4766804, None, [_split("2026-10-29", 25, 1)]),
    (None, "2026-10-30", 4766804, "2026-10-15", [_split("2026-10-29", 25, 1)]),
])
def test_NEGATIVE_change_is_None(args):
    assert BM.change_across_split(*args) is None


# ═════════════════════════════════════════════ verdict — SMTK (captured, today 11-24)
def test_verdict_SMTK_captured():
    v = BM.verdict(_rec(), _doc(), TODAY)
    assert v["float_refused"] == "diluted" and v["refused_reasons"] == ["diluted"]
    assert v["float_pct_on_file"] == 79.05
    assert v["count"] == {"shares": 4859369, "as_of": "2026-11-11", "source": "sec", "form": "10-Q"}
    assert v["count_changed"] is True and v["pct_of_shares_out"] == 8.9
    assert _keys(v) == ["float_stale", "split", "filing"]
    assert v["growth"]["ratio"] == 4.691 and v["growth"]["from_source"] == "yahoo"
    assert [f["short"] for f in v["flags"]] == ["⚠️ float stale", "✂️ split 11/23", "📄 S-4 11/13"]
    lines = " ".join(v["title_lines"])
    assert "565,275 on 8/12 → 4,859,369 on 11/11 — 8.6×" in lines
    assert "86,463 of today's shares" in lines and "8-K Item 5.03 11/23" in lines
    assert v["status"] == "ok" and v["change"] is None
    json.dumps(v, allow_nan=False)


@pytest.mark.parametrize("m,refused", [("any_increase", True), ("added_exceeds_float", True), ("tier_moves", True)])
def test_verdict_SMTK_refused_in_every_mode(mode, m, refused):
    mode(m)
    assert (BM.verdict(_rec(), _doc(), TODAY)["float_refused"] == "diluted") is refused


def _meds():
    rec = _rec("MEDS", short_interest=371417, float_shares=1455606, float_asof="2026-11-05",
               shares_outstanding=5182529, shares_asof="2026-11-05")
    doc = _doc("MEDS", splits=[], filings=[], covers=[
        {"as_of": "2026-08-17", "shares": 3061919, "form": "10-Q", "filed": "2026-08-17"},
        {"as_of": "2026-11-13", "shares": 5724857, "form": "10-Q", "filed": "2026-11-13"}],
        yahoo={"float_shares": 1455606, "shares_outstanding": 5724857, "as_of": "2026-11-20"})
    return rec, doc


def _jeld():
    rec = _rec("JELD", short_interest=8033885, float_shares=80352436, float_asof="2026-11-04",
               shares_outstanding=86763382, shares_asof="2026-11-04", days_to_cover=8.56)
    doc = _doc("JELD", splits=[], filings=[{"form": "8-K", "filed": "2026-11-23", "items": "1.01,2.03,9.01"}],
               covers=[{"as_of": "2026-10-30", "shares": 86774941, "form": "10-Q", "filed": "2026-11-04"}],
               yahoo={"float_shares": 80095874, "shares_outstanding": 86774941, "as_of": "2026-11-23"})
    return rec, doc


# 2026-11-24 later: JELD's Yahoo row (11-23) holds a newer float; it is only divided by — the growth check keeps the
# replaced float's date and count, so the modes judge JELD exactly as before
@pytest.mark.parametrize("m,meds,jeld", [("any_increase", True, True), ("tier_moves", True, False),
                                         ("added_exceeds_float", False, False)])
def test_verdict_modes_MEDS_and_JELD(mode, m, meds, jeld):
    mode(m)
    assert (BM.verdict(*_meds(), TODAY)["float_refused"] == "diluted") is meds
    assert (BM.verdict(*_jeld(), TODAY)["float_refused"] == "diluted") is jeld


def test_NEGATIVE_JELD_under_the_built_mode_has_no_flag():
    v = BM.verdict(*_jeld(), TODAY)                           # 2026-11-24 later: the newer Yahoo float is the only mark
    assert v["float_refused"] is None and [f["key"] for f in v["flags"]] == ["float_updated"]
    assert v["growth"]["ratio"] == 1.0
    assert v["count"] is None and v["count_changed"] is False


def test_NEGATIVE_unknown_mode_refuses_nothing_for_dilution(mode):
    mode("whatever")
    v = BM.verdict(_rec(), _doc(), TODAY)
    assert v["float_refused"] is None and "float_stale" not in _keys(v)


# ═════════════════════════════════════════════ verdict — SMTK forward (synthetic records, today 12-10)
def test_forward_B_rewarm_still_diluted_on_the_11_02_pairing():
    rec = _rec(settlement_date="2026-11-13", short_interest=440000, float_asof="2026-11-18",
               shares_outstanding=4859369, shares_asof="2026-11-18")
    v = BM.verdict(rec, _doc(track=dict(SMTK_TRACK)), FWD)
    assert v["float_refused"] == "diluted" and v["growth"]["from_shares"] == 1035799
    assert v["pct_of_shares_out"] == 9.05


def _rec_C(**over):
    d = dict(settlement_date="2026-11-28", short_interest=88000, prev_settlement_date="2026-11-13",
             prev_short_interest=440000, float_asof="2026-12-01", shares_outstanding=971874, shares_asof="2026-12-01")
    d.update(over)
    return _rec(**d)


def test_forward_C_sticky_float_across_the_split_refused_for_both_reasons():
    v = BM.verdict(_rec_C(), _doc(track=dict(SMTK_TRACK), yahoo=None), FWD)
    assert v["float_refused"] == "split" and v["refused_reasons"] == ["split", "diluted"]
    assert "float_stale" in _keys(v) and "split" in _keys(v)
    assert v["count"]["shares"] == 971874 and v["pct_of_shares_out"] == 9.05
    assert "the float on file dates from before it (first seen, 11/2)" in v["float_line"]


def test_forward_D_carried_float_diluted_on_the_SEC_baseline():
    stored = _doc(track=dict(SMTK_TRACK), yahoo=None)
    before = copy.deepcopy(stored)
    v = BM.verdict(_rec_C(float_shares=109375), stored, FWD)
    t = v["track"]
    assert (t["origin"], t["since"], t["shares"], t["basis_asof"]) == ("carried", "2026-11-02", None, "2026-11-24")
    assert v["float_refused"] == "diluted" and v["refused_reasons"] == ["diluted"]
    g = v["growth"]
    assert (g["from_source"], g["from_asof"]) == ("sec", "2026-08-12")
    assert g["from_shares"] == round(28263733 / 50 / 5)
    assert "8.6×" in v["flags"][0]["text"] and "SEC cover, the count on file before the float was read" in \
        v["flags"][0]["text"]
    assert stored == before                                   # the read never writes the doc


def test_forward_E_a_new_float_is_a_fresh_track_and_trusted():
    rec = _rec_C(float_shares=700000, float_asof="2026-12-09", shares_asof="2026-12-09")
    v = BM.verdict(rec, _doc(track=dict(SMTK_TRACK), yahoo=None), FWD)
    assert v["track"]["since"] == "2026-12-09" and v["track"]["origin"] == "si_doc"
    assert v["float_refused"] is None and v["flags"] == []


def test_C3_sticky_case_with_the_settlement_BEFORE_the_split_is_not_refused():
    v = BM.verdict(_rec(), _doc(covers=[], yahoo=None, filings=[]), TODAY)
    assert v["float_refused"] is None and v["refused_reasons"] == []


def test_C3_rewarmed_carried_float_while_the_stored_track_holds_the_old_value():
    v = BM.verdict(_rec_C(float_shares=109375), _doc(track=dict(SMTK_TRACK)), FWD)
    assert v["track"]["origin"] == "carried"


# ═════════════════════════════════════════════ carried SMX [C4]
def _smx_doc():
    held = {"value": 791704, "since": "2026-11-05", "shares": 892857, "shares_asof": "2026-11-05",
            "basis_asof": "2026-11-05", "origin": "si_doc", "carried": []}
    return _doc("SMX", splits=[_split("2026-11-09", 2.8, 1)], track=held, filings=[],
                covers=[{"as_of": "2025-12-31", "shares": 1795943, "form": "20-F", "filed": "2026-03-20"}],
                yahoo={"float_shares": 282748, "shares_outstanding": 897717, "as_of": "2026-11-24"})


def _smx_rec(**over):
    d = dict(short_interest=47715, float_shares=282748, float_asof="2026-11-24", shares_outstanding=897717,
             shares_asof="2026-11-24", prev_short_interest=None, prev_settlement_date=None)
    d.update(over)
    return _rec("SMX", **d)


def test_carried_SMX_is_a_split_refusal_and_no_false_float_stale():
    v = BM.verdict(_smx_rec(), _smx_doc(), TODAY)
    assert v["float_refused"] == "split" and v["refused_reasons"] == ["split"]
    assert "float_stale" not in _keys(v)
    assert "carried across it" in v["float_line"]


def test_carried_SMX_next_settlement_reads_the_float():
    v = BM.verdict(_smx_rec(settlement_date="2026-11-13", short_interest=16965), _smx_doc(), TODAY)
    assert v["float_refused"] is None


def test_carried_track_with_no_SEC_cover_before_since_is_dilution_unchecked():
    doc = _smx_doc()
    doc["sec"]["covers"] = [{"as_of": "2026-11-20", "shares": 900000, "form": "6-K", "filed": "2026-11-20"}]
    v = BM.verdict(_smx_rec(settlement_date="2026-11-13", short_interest=16965), doc, TODAY)
    assert v["float_refused"] is None
    u = [f for f in v["flags"] if f["key"] == "unchecked"]
    assert u and u[0]["short"] == "❔ dilution unchecked"
    assert "carried across the 1-for-2.8 reverse split 11/9" in u[0]["text"] and "before 11/5" in u[0]["text"]


def test_NEGATIVE_a_carried_split_not_yet_executed_has_no_baseline_and_no_check_flag():
    held = {"value": 1000000, "since": "2026-11-05", "shares": 2000000, "shares_asof": "2026-11-05",
            "basis_asof": "2026-11-05", "origin": "si_doc", "carried": []}
    doc = _doc("EARLY", splits=[_split("2026-12-01", 10, 1)], track=held, filings=[], covers=[], yahoo=None)
    rec = _rec("EARLY", short_interest=10000, float_shares=100000, float_asof="2026-11-20",
               shares_outstanding=200000, shares_asof="2026-11-20", prev_short_interest=None)
    v = BM.verdict(rec, doc, TODAY)
    assert v["track"]["origin"] == "carried" and v["growth"] is None
    assert v["float_refused"] == "split"                      # Yahoo applied it early: refused, no ❔ for it
    assert "unchecked" not in _keys(v)


# ═════════════════════════════════════════════ the named names
def test_KITT_refused_split_then_diluted():
    rec = _rec("KITT", short_interest=203890, float_shares=5527831, float_asof="2026-09-03",
               shares_outstanding=7471960, shares_asof="2026-09-03", days_to_cover=3.58)
    doc = _doc("KITT", splits=[_split("2026-09-25", 6, 1)],
               covers=[{"as_of": "2026-08-12", "shares": 7471960, "form": "10-Q", "filed": "2026-08-12"},
                       {"as_of": "2026-11-16", "shares": 2643176, "form": "10-Q", "filed": "2026-11-16"}],
               filings=[{"form": "10-Q", "filed": "2026-11-16", "items": ""},
                        {"form": "S-1", "filed": "2026-11-12", "items": ""},
                        {"form": "8-K", "filed": "2026-09-23", "items": "3.03,5.03,8.01,9.01"}],
               yahoo={"float_shares": 1612787, "shares_outstanding": 2643176, "as_of": "2026-11-23"})
    v = BM.verdict(rec, doc, TODAY)
    # 2026-11-24 later: Yahoo's 11-23 float (post-split, the 10-30 count's side) is the one divided by, so the split
    # refusal goes; the dilution since the REPLACED float's 09-03 date still refuses it (the split + diluted result is
    # pinned with the Yahoo float removed in test_si_float_newer_2026_11_24.py)
    assert v["refused_reasons"] == ["diluted"] and v["pct_of_shares_out"] == 7.71
    assert v["growth"]["ratio"] == pytest.approx(2.122, abs=1e-3)
    assert "8-K Item 3.03/5.03 9/23" in " ".join(v["title_lines"])
    assert v["float_update"]["replaced_shares"] == 5527831 and v["flags"][0]["key"] == "float_updated"
    # refix 3: a dilution refusal's on-file % is on the REPLACED float, as on main (203,890 / 5,527,831)
    assert v["float_update"]["pct"] is None and v["float_pct_on_file"] == 3.69


def test_NXAT_count_fell_is_a_flag_never_a_refusal():
    rec = _rec("NXAT", short_interest=21473, float_shares=1353790, float_asof="2026-09-10",
               shares_outstanding=68476338, shares_asof="2026-09-10")
    doc = _doc("NXAT", splits=[], filings=[],
               covers=[{"as_of": "2025-12-31", "shares": 64221193, "form": "20-F", "filed": "2026-05-15"}],
               yahoo={"float_shares": 1353790, "shares_outstanding": 3236567, "as_of": "2026-11-20"})
    v = BM.verdict(rec, doc, TODAY)
    assert v["float_refused"] is None and v["status"] == "partial"
    assert [f["short"] for f in v["flags"]] == ["❔ shares fell 21×"]
    assert v["fell"]["ratio"] == pytest.approx(21.157, abs=1e-3)


def test_NXAT_shares_headed_fall_keeps_the_record_count():
    rec = _rec("NXAT", short_interest=21473, float_shares=None, shares_outstanding=68476338, shares_asof="2026-09-10")
    doc = _doc("NXAT", splits=[], filings=[], covers=[],
               yahoo={"float_shares": None, "shares_outstanding": 3236567, "as_of": "2026-11-20"})
    v = BM.verdict(rec, doc, TODAY)
    assert v["count"]["source"] == "record" and v["count"]["shares"] == 68476338 and v["count_changed"] is False
    assert "count_fell" in _keys(v)


def test_NEGATIVE_a_9pct_fall_and_a_fall_across_a_listed_split_are_not_flagged():
    rec = _rec("NXAT", short_interest=21473, float_shares=1353790, float_asof="2026-09-10",
               shares_outstanding=68476338, shares_asof="2026-09-10")
    nine = _doc("NXAT", splits=[], filings=[], covers=[],
                yahoo={"shares_outstanding": int(68476338 * 0.91), "as_of": "2026-11-20"})
    assert "count_fell" not in _keys(BM.verdict(rec, nine, TODAY))
    split = _doc("NXAT", splits=[_split("2026-10-01", 20, 1)], filings=[], covers=[],
                 yahoo={"shares_outstanding": 3236567, "as_of": "2026-11-20"})
    assert "count_fell" not in _keys(BM.verdict(rec, split, TODAY))


def test_WETO_shares_headed_count_up_14x():
    rec = _rec("WETO", short_interest=241900, float_shares=186729, float_asof="2026-11-02",
               shares_outstanding=1077801, shares_asof="2026-11-02")
    doc = _doc("WETO", splits=[], filings=[{"form": "6-K", "filed": "2026-11-19", "items": ""}],
               covers=[{"as_of": "2025-06-30", "shares": 22000000, "form": "20-F", "filed": "2025-10-30"},
                       {"as_of": "2026-06-30", "shares": 821300, "form": "20-F", "filed": "2026-11-05"}],
               yahoo={"float_shares": 14735015, "shares_outstanding": 14897999, "as_of": "2026-11-20"})
    v = BM.verdict(rec, doc, TODAY)
    # 2026-11-24 later: Yahoo's 11-20 float 14,735,015 (with 14,897,999 shares on the same row) is the one divided by;
    # the replaced 186,729 was suspect, so the growth check runs as before and the shares-up mark stays
    assert v["float_refused"] is None                          # float_suspect: shares-headed, never refused
    assert [f["short"] for f in v["flags"]] == ["⚠️ float updated", "⚠️ shares up 14×"]
    assert v["count"]["source"] == "yahoo" and v["pct_of_shares_out"] == 1.62
    assert v["growth"]["from_source"] == "record"              # the covers older than the anchor are never used
    assert v["float_update"]["suspect"] is None and v["float_update"]["pct"] == 1.64


def _jz(rtype):
    rec = _rec("JZ", short_interest=382451, float_shares=1403950, float_asof="2026-11-09",
               shares_outstanding=2377874, shares_asof="2026-11-09", days_to_cover=1.71)
    doc = _doc("JZ", rtype=rtype, splits=[_split("2026-12-24", 15, 1)],
               covers=[{"as_of": "2025-12-31", "shares": 517110000, "form": "20-F", "filed": "2026-04-13"},
                       {"as_of": "2026-11-15", "shares": 517110000, "form": "20-F", "filed": "2026-11-20"}],
               filings=[{"form": "424B5", "filed": "2026-08-14", "items": ""}],
               yahoo={"float_shares": 1403950, "shares_outstanding": 2377874, "as_of": "2026-11-24"})
    return rec, doc


def test_P1_ADR_cover_is_not_compared_and_the_check_says_why():
    v = BM.verdict(*_jz("ADRC"), TODAY)
    assert v["float_refused"] is None and v["sources"]["sec"] == "units"
    assert [f["short"] for f in v["flags"]] == ["✂️ split due 12/24"]
    assert "not compared — an ADR's SEC cover counts ordinary shares" in v["check_text"]


def test_P1_the_same_doc_typed_CS_is_refused():
    v = BM.verdict(*_jz("CS"), TODAY)
    assert v["float_refused"] == "diluted"


def test_CLRO_only_gains_the_filing_flag():
    rec, doc = _clro()
    v = BM.verdict(rec, doc, TODAY)
    assert v["float_refused"] is None and v["growth"] is None and v["fell"] is None
    assert [f["short"] for f in v["flags"]] == ["📄 S-1/A 11/24 +1"]
    # 2026-11-26 sitrack A1: the text counts the events ("2 dilution filings")
    assert v["flags"][0]["text"] == "📄 2 dilution filings since 11/10: S-1/A 11/24 · 8-K 3.02 11/17"


def _clro():
    """CLRO as captured 2026-11-24T19:05:50Z (scratchpad clro_inputs.json), filings after 08-01."""
    rec = _rec("CLRO", short_interest=391224, prev_short_interest=290226, si_change_pct=34.8,
               float_shares=888130, float_asof="2026-11-10", shares_outstanding=2675412, shares_asof="2026-11-10")
    covers = [{"as_of": "2026-08-14", "shares": 2675412, "form": "10-Q", "filed": "2026-08-14"},
              {"as_of": "2026-11-10", "shares": 2675412, "form": "10-Q", "filed": "2026-11-10"}]
    filings = [{"form": "S-1/A", "filed": "2026-11-24", "items": ""},
               {"form": "4", "filed": "2026-11-17", "items": ""},
               {"form": "SCHEDULE 13D/A", "filed": "2026-11-17", "items": ""},
               {"form": "8-K", "filed": "2026-11-17", "items": "1.01,3.02,7.01,9.01"},
               {"form": "10-Q", "filed": "2026-11-10", "items": ""},
               {"form": "8-K", "filed": "2026-10-15", "items": "1.01,2.03,9.01"},
               {"form": "S-1/A", "filed": "2026-09-04", "items": ""}]
    doc = _doc("CLRO", splits=[], covers=covers, filings=filings,
               yahoo={"float_shares": 888130, "shares_outstanding": 2675412, "as_of": "2026-11-17"})
    return rec, doc


def test_BENF_sec_none_gives_no_SEC_flag():
    rec = _rec("BENF", short_interest=359965, float_shares=3944455, float_asof="2026-11-10",
               shares_outstanding=15458833, shares_asof="2026-11-10")
    doc = _doc("BENF", splits=[], sec=_ok(status="none", covers=[], filings=[]),
               yahoo={"float_shares": 3944455, "shares_outstanding": 19146748, "as_of": "2026-11-24"})
    v = BM.verdict(rec, doc, TODAY)
    assert v["float_refused"] is None and v["flags"] == [] and v["sources"]["sec"] == "none"


XLAB_FILINGS = [{"form": "424B3", "filed": "2026-11-16", "items": ""},
                {"form": "10-Q", "filed": "2026-11-16", "items": ""},
                {"form": "424B3", "filed": "2026-11-09", "items": ""},
                {"form": "8-K", "filed": "2026-11-09", "items": "1.01,9.01"},
                {"form": "424B3", "filed": "2026-11-05", "items": ""},
                {"form": "S-1", "filed": "2026-10-30", "items": ""}]


def _xlab(sec_status):
    """XLAB as captured 2026-11-24 (scratchpad sec_inputs.json + basis_inputs.json): companyconcept 404 → no cover
    fact → sec status "none", but its submissions filings are stored. Shares-headed, anchor = shares_asof 11-05."""
    rec = _rec("XLAB", short_interest=708675, prev_short_interest=None, si_change_pct=None, prev_settlement_date=None,
               float_shares=None, float_asof=None, shares_outstanding=33689050, shares_asof="2026-11-05")
    doc = _doc("XLAB", splits=[], sec=_ok(status=sec_status, since="2026-08-01", covers=[], filings=XLAB_FILINGS),
               yahoo={"float_shares": None, "shares_outstanding": 33689050, "as_of": "2026-11-12"})
    return rec, doc


def test_XLAB_sec_none_still_flags_its_dilution_filings():
    rec, doc = _xlab("none")
    v = BM.verdict(rec, doc, TODAY)
    assert v["sources"]["sec"] == "none" and v["float_refused"] is None
    # 2026-11-26 sitrack A3: the 424B3 filed ON the anchor (11/05) now counts, labelled same day; the stored rows carry
    # no `doc`, so each 424B3 is one event and the text says they are not yet checked for copies (S-1 10/30: before)
    assert [f["short"] for f in v["flags"]] == ["📄 424B3 11/16 +2"]
    assert v["flags"][0]["text"] == ("📄 3 dilution filings since 11/5: 424B3 11/16 · 424B3 11/9 · 424B3 11/5"
                                     " — 424B3 11/5 filed the same day the share count was read; which came first is"
                                     " not known — 3 prospectus filings not yet checked for copies")


def test_XLAB_sec_none_chip_and_title_carry_the_filing():
    rec, doc = _xlab("none")
    b = SR.si_block(rec, TODAY, basis=doc)
    # 2026-11-26 sitrack A3 (+2: the 11/05 same-day 424B3) and A4 (the provider's 1.0 with no ADV is FINRA's floor)
    assert b["chip"] == "🩳 SI 2.1% shs out · ≤1d · 10/30 · 📄 424B3 11/16 +2"
    assert "424B3" in b["title"]
    assert [f["key"] for f in b["basis"]["flags"]] == ["filing"]


def test_XLAB_sec_none_flags_equal_sec_ok_flags():
    v_none = BM.verdict(*_xlab("none"), TODAY)
    v_ok = BM.verdict(*_xlab("ok"), TODAY)
    assert v_none["flags"] == v_ok["flags"] and v_none["filings"] == v_ok["filings"]


@pytest.mark.parametrize("status", ["failed", None, "", 7])
def test_XLAB_sec_never_read_uses_no_filings(status):
    rec, doc = _xlab("ok")
    doc["sec"]["status"] = status
    v = BM.verdict(rec, doc, TODAY)
    assert not any(f["key"] == "filing" for f in v["flags"])
    assert not v.get("filings")


def test_sec_none_filings_only_before_the_anchor_give_no_flag():
    rec, doc = _xlab("none")
    # 2026-11-26 sitrack A3: a filing ON the anchor counts now — strictly before it gives no flag
    doc["sec"]["filings"] = [f for f in XLAB_FILINGS if f["filed"] < "2026-11-05"]
    v = BM.verdict(rec, doc, TODAY)
    assert not any(f["key"] == "filing" for f in v["flags"])


def test_forward_split_between_float_and_count_is_refused():
    rec = _rec("FWD", short_interest=100000, float_shares=1000000, float_asof="2026-10-01",
               shares_outstanding=2000000, shares_asof="2026-10-01", prev_short_interest=None)
    v = BM.verdict(rec, _doc("FWD", splits=[_split("2026-10-15", 1, 2)], covers=[], filings=[], yahoo=None), TODAY)
    assert v["float_refused"] == "split" and "2-for-1 split" in v["float_line"]


def test_two_splits_chip_short_counts_the_second():
    rec = _rec("TWO", short_interest=100000, float_shares=1000000, float_asof="2026-09-01",
               shares_outstanding=2000000, shares_asof="2026-09-01", prev_short_interest=None)
    doc = _doc("TWO", splits=[_split("2026-09-15", 2, 1), _split("2026-10-15", 3, 1)], covers=[], filings=[],
               yahoo=None)
    v = BM.verdict(rec, doc, TODAY)
    assert [f["short"] for f in v["flags"] if f["key"] == "split"] == ["✂️ split 10/15 +1"]


def test_split_ON_the_settlement_day_and_ON_the_first_seen_day_is_never_rebased():
    rec = _rec("SAME", settlement_date="2026-10-30", short_interest=100000, float_shares=1000000,
               float_asof="2026-10-30", shares_outstanding=2000000, shares_asof="2026-10-30",
               prev_short_interest=None)
    doc = _doc("SAME", splits=[_split("2026-10-30", 10, 1)], filings=[],
               covers=[{"as_of": "2026-11-15", "shares": 200000, "form": "10-Q", "filed": "2026-11-16"}],
               yahoo={"shares_outstanding": 200000, "as_of": "2026-11-20"})
    v = BM.verdict(rec, doc, TODAY)
    assert v["float_refused"] == "split_same_day" and v["count"] is None and v["no_pct"] is True
    assert "that same day" in v["float_line"]


def test_NEGATIVE_upcoming_split_is_a_flag_only():
    v = BM.verdict(*_jz("ADRC"), TODAY)
    assert v["count"] is None and v["count_changed"] is False and v["no_pct"] is False and v["change"] is None


# ═════════════════════════════════════════════ [C1] the status rule
def test_C1_held_rows_with_an_error_still_refuse_and_say_last_check_failed():
    sp = _ok(since="2026-08-01", rows=SMTK_SPLITS, error="ReadTimeout", error_at="2026-11-24T19:10:00Z", strikes=1)
    v = BM.verdict(_rec(), _doc(sp=sp), TODAY)
    assert v["float_refused"] == "diluted" and v["flags"][-1]["short"] == "❔ last check failed"
    assert "the splits read last answered 11/24 13:05 ET and failed at 11/24 14:10 ET" in v["flags"][-1]["text"]
    assert v["status"] == "partial"


def test_C1_splits_never_read_refuses_nothing_and_says_unchecked():
    sp = {"status": "failed", "read_at": None, "error": "HTTPError", "error_at": "2026-11-24T19:10:00Z", "strikes": 1}
    v = BM.verdict(_rec(), _doc(sp=sp), TODAY)
    assert v["float_refused"] is None and v["count"] is None and v["change"] is None
    assert v["flags"][-1]["short"] == "❔ share count unchecked" and v["status"] == "partial"
    assert "the splits read did not answer (last try 11/24 14:10 ET)" in v["flags"][-1]["text"]


def test_C11_sec_blocked_is_unchecked():
    v = BM.verdict(_rec(), _doc(sec={"status": "blocked"}, yahoo=None), TODAY)
    assert v["float_refused"] is None and v["flags"][-1]["short"] == "❔ share count unchecked"
    assert v["sources"]["sec"] == "blocked"


def test_C1_a_seed_only_doc_carries_no_flag():
    doc = {"_id": "SMTK", "float_track": dict(SMTK_TRACK, origin="seed")}
    v = BM.verdict(_rec(), doc, TODAY)
    assert v["flags"] == [] and v["float_refused"] is None and v["status"] == "partial"


# ═════════════════════════════════════════════ [C11] None guards
def test_C11_a_cover_ON_a_split_day_is_dropped_never_raises():
    covers = SMTK_COVERS + [{"as_of": "2026-11-23", "shares": 971874, "form": "8-K", "filed": "2026-11-23"}]
    v = BM.verdict(_rec(), _doc(covers=covers), TODAY)
    assert v["growth"]["to_source"] == "yahoo"


_BAD = [float("nan"), float("inf"), -5, True, "x", None]


def _poison(o, bad):
    if isinstance(o, dict):
        return {k: (bad if isinstance(v, (int, float)) and not isinstance(v, bool) else _poison(v, bad))
                for k, v in o.items()}
    if isinstance(o, list):
        return [_poison(x, bad) for x in o]
    return o


@pytest.mark.parametrize("bad", _BAD)
def test_C11_bad_numbers_in_every_basis_leaf_are_missing(bad):
    doc = _poison(_doc(track=dict(SMTK_TRACK)), bad)
    v = BM.verdict(_rec(), doc, TODAY)
    assert v["float_refused"] is None
    json.dumps(v, allow_nan=False)


@pytest.mark.parametrize("bad", [None, "x", 5, [], {"splits": "x", "sec": [1], "ref": 3, "yahoo": "y",
                                                     "float_track": [1]}])
def test_NEGATIVE_junk_docs_never_raise(bad):
    v = BM.verdict(_rec(), bad, TODAY)
    assert v is not None and v["float_refused"] is None and v["flags"] == []
    json.dumps(v, allow_nan=False)


@pytest.mark.parametrize("over", [{"settlement_date": None}, {"short_interest": None}, {"short_interest": float("nan")}])
def test_NEGATIVE_no_record_is_None(over):
    assert BM.verdict(_rec(**over), _doc(), TODAY) is None
    assert BM.verdict(None, _doc(), TODAY) is None


def test_the_count_fell_cut_is_read_by_name_at_call_time(monkeypatch):
    rec = _rec("NXAT", short_interest=21473, float_shares=1353790, float_asof="2026-09-10",
               shares_outstanding=68476338, shares_asof="2026-09-10")
    doc = _doc("NXAT", splits=[], filings=[], covers=[],
               yahoo={"shares_outstanding": int(68476338 * 0.91), "as_of": "2026-11-20"})
    monkeypatch.setattr(SR, "SUSPECT_MAX_SHARES_OUT_FRACTION", 0.95)
    assert "count_fell" in _keys(BM.verdict(rec, doc, TODAY))


def test_rules_sentence_is_built_from_the_constants(mode):
    s = BM.rules_sentence()
    assert BM.FLOAT_STALE_MODE_WORDS[BM.FLOAT_STALE_WHEN] in s
    for w in (BM.SHORT_FLOAT_STALE, BM.SHORT_UNCHECKED, BM.EMOJI_FILING):
        assert w in s
    mode("tier_moves")
    assert BM.FLOAT_STALE_MODE_WORDS["tier_moves"] in BM.rules_sentence()
    assert set(BM.FLOAT_STALE_MODE_WORDS) == set(BM.FLOAT_STALE_MODES)
    assert BM.FLOAT_STALE_WHEN in BM.FLOAT_STALE_MODES
    assert not math.isnan(BM.CARRY_REL_TOL) and 1.8e-5 < BM.CARRY_REL_TOL < 3.0e-3
