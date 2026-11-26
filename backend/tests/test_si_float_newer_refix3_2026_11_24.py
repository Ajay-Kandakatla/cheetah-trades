"""🩳 newer Yahoo float — the verifier's third-round findings (2026-11-24, refix 3).

Ajay 2026-11-24, verbatim: "Is GMEX float accurate?" (after "Make sure we are looking for Dilution.." and "Also split
related events and filing so we flag them in the right way").

1. MEDIUM: on a DILUTED refusal under a newer float, `float_pct_on_file` is on the REPLACED float (as on main), so the
   "% of float: not shown" line and the 🩳 High SI panel's basis_text agree — LABT 18.04% (High) on 847,661, listed in
   basis_text, not 4.78% (Low) on Yahoo's 3,201,536.
2. LOW: the refusal line says no "would read X%" when an executed split sits between the replaced float's date and the
   settlement (KITT: a 9/3 float vs a short count after the 9/25 1-for-6).
3. LOW: both floats suspect, Yahoo read after a split (the verifier's dfl.py) — not refused; the newer float is not
   divided by, so the split-side check does not run on it.

NEGATIVES: a split refusal under a newer float keeps the % on the newer float; a dilution refusal with no newer float is
on the record float; no split, or a split before / after both dates, keeps "would read"; the dfl shape with a good newer
float IS judged across the split.
"""
from __future__ import annotations

import copy
from datetime import date

from chart_maps.gajjala import high_si as HS
from short_interest import basis_math as BM
from short_interest import read as SR
from tests.test_gajjala_high_si_basis_2026_11_24 import _ev
from tests.test_gajjala_high_si_2026_11_23 import fr
from tests.test_si_basis_math_2026_11_24 import _doc, _rec, _split
from tests.test_si_float_newer_fixes_2026_11_24 import _labt

TODAY = date(2026, 11, 24)
HI = SR.TIER_WORDS[SR.TIER_HIGH]


def blk(rec, doc):
    return SR.si_block(copy.deepcopy(rec), TODAY, basis=copy.deepcopy(doc))


def _pof_row(b):
    return next(r["v"] for r in b["rows"] if r["k"] == "% of float")


# ═════════════════════════════════════════════ 1. a dilution refusal's on-file % is on the replaced float
def test_LABT_float_pct_on_file_is_on_the_replaced_847661_float():
    rec, doc = _labt()
    v = BM.verdict(rec, doc, TODAY)
    assert v["float_refused"] == "diluted" and v["float_update"]["replaced_shares"] == 847661
    assert v["float_pct_on_file"] == 18.04 == round(152917 / 847661 * 100.0, 2)
    assert SR.tier_of(v["float_pct_on_file"]) == SR.TIER_HIGH


def test_LABT_refusal_line_and_float_pct_on_file_agree():
    rec, doc = _labt()
    b = blk(rec, doc)
    assert b["basis"]["float_pct_on_file"] == 18.04
    assert _pof_row(b).endswith("would read %.2f%%" % b["basis"]["float_pct_on_file"])


def test_LABT_is_named_in_the_high_si_basis_text_as_on_main():
    rec, doc = _labt()
    b = blk(rec, doc)
    ev = _ev({"LABT": (b, fr(3201536))})
    assert ev["rows"] == [] and ev["refused"] == 1
    assert ev["basis"] == [{"symbol": "LABT", "chip": b["chip"], "tier_word": HI}]
    assert "LABT" in HS.basis_text(ev)
    old = _ev({"LABT": (blk(rec, dict(copy.deepcopy(doc), yahoo=dict(doc["yahoo"], float_shares=None))),
                        fr(3201536))})
    assert [r["symbol"] for r in old["basis"]] == ["LABT"]                  # the same listing without a newer float


def test_NEGATIVE_LABT_without_a_newer_float_is_unchanged():
    rec, doc = _labt(yahoo_float=None)
    v = BM.verdict(rec, doc, TODAY)
    assert v["float_update"] is None and v["float_pct_on_file"] == 18.04


def test_NEGATIVE_a_split_refusal_under_a_newer_float_keeps_the_newer_floats_pct():
    rec = _rec("PRE", settlement_date="2026-11-13", short_interest=50000, prev_settlement_date=None,
               prev_short_interest=None, float_shares=900000, float_asof="2026-11-01",
               shares_outstanding=2000000, shares_asof="2026-11-01")
    doc = _doc("PRE", covers=[], filings=[], splits=[_split("2026-11-10", 10, 1)],
               yahoo={"float_shares": 1000000, "shares_outstanding": 2000000, "as_of": "2026-11-05"})
    v = BM.verdict(rec, doc, TODAY)
    assert v["float_refused"] == "split" and v["float_update"]["shares"] == 1000000
    assert v["float_pct_on_file"] == 5.0                                    # 50,000 / 1,000,000, not / 900,000


def test_NEGATIVE_no_refusal_has_no_float_pct_on_file():
    from tests.test_si_float_newer_2026_11_24 import gmex_doc, gmex_rec
    v = BM.verdict(gmex_rec(), gmex_doc(), TODAY)
    assert v["float_refused"] is None and v["float_pct_on_file"] is None and v["float_update"]["pct"] == 3.52


# ═════════════════════════════════════════════ 2. no "would read" across an executed split
def _kitt(splits=None):
    rec = _rec("KITT", short_interest=203890, float_shares=5527831, float_asof="2026-09-03",
               shares_outstanding=7471960, shares_asof="2026-09-03", days_to_cover=3.58)
    doc = _doc("KITT", splits=[_split("2026-09-25", 6, 1)] if splits is None else splits,
               covers=[{"as_of": "2026-08-12", "shares": 7471960, "form": "10-Q", "filed": "2026-08-12"},
                       {"as_of": "2026-11-16", "shares": 2643176, "form": "10-Q", "filed": "2026-11-16"}],
               filings=[{"form": "10-Q", "filed": "2026-11-16", "items": ""},
                        {"form": "S-1", "filed": "2026-11-12", "items": ""},
                        {"form": "8-K", "filed": "2026-09-23", "items": "3.03,5.03,8.01,9.01"}],
               yahoo={"float_shares": 1612787, "shares_outstanding": 2643176, "as_of": "2026-11-23"})
    return rec, doc


def test_KITT_refusal_line_says_no_would_read_across_the_9_25_split():
    rec, doc = _kitt()
    b = blk(rec, doc)
    assert b["basis"]["refused_reasons"] == ["diluted"] and b["basis"]["float_update"]["replaced_asof"] == "2026-09-03"
    row = _pof_row(b)
    assert row.endswith("the float on file (5,527,831, %s, as of 2026-09-03)" % SR.FLOAT_SOURCE)
    assert "would read" not in row and "3.69%" not in b["title"]


def test_NEGATIVE_LABT_with_no_split_keeps_would_read():
    rec, doc = _labt()
    assert _pof_row(blk(rec, doc)).endswith("as of 2026-11-09) would read 18.04%")


def test_NEGATIVE_a_split_after_both_dates_keeps_would_read():
    rec, doc = _labt()
    doc["splits"]["rows"] = [_split("2026-11-20", 10, 1)]                  # after S 10/30 and the float's 11/9
    b = blk(rec, doc)
    assert b["basis"]["float_refused"] == "diluted"
    assert [s["execution_date"] for s in b["basis"]["splits"]] == ["2026-11-20"]
    assert _pof_row(b).endswith("as of 2026-11-09) would read 18.04%")


def test_NEGATIVE_a_split_before_both_dates_keeps_would_read():
    rec, doc = _labt()
    doc["splits"]["rows"] = [_split("2026-06-01", 10, 1)]                  # before every count and float in play
    b = blk(rec, doc)
    assert b["basis"]["float_refused"] == "diluted"
    assert _pof_row(b).endswith("as of 2026-11-09) would read 18.04%")


# ═════════════════════════════════════════════ 3. both floats suspect, Yahoo read after a split (dfl.py)
def _dfl(yahoo_float):
    rec = _rec("ZZD", settlement_date="2026-10-30", short_interest=100000, prev_settlement_date=None,
               prev_short_interest=None, float_shares=3000000, float_asof="2026-09-01",
               shares_outstanding=2000000, shares_asof="2026-09-01")
    doc = _doc("ZZD", covers=[], filings=[], splits=[_split("2026-11-10", 10, 1)],
               yahoo={"float_shares": yahoo_float, "shares_outstanding": 200000, "as_of": "2026-11-19"})
    return rec, doc


def test_dfl_both_floats_suspect_not_refused_for_the_split():
    rec, doc = _dfl(400000)                                                 # 3.0M > 2.0M and 400K > 200K: both suspect
    v = BM.verdict(rec, doc, TODAY)
    assert v["float_update"]["suspect"] == SR.FLOAT_EXCEEDS_SHARES and v["float_update"]["pct"] is None
    assert v["refused_reasons"] == [] and v["float_refused"] is None and v["float_pct_on_file"] is None
    b = blk(rec, doc)
    assert b["pct_of_float"] is None and b["pct_of_shares_out"] == 5.0
    # 2026-11-26 sitrack A4: the provider's 1.0 with no ADV on the record is FINRA's floor → '≤1d'
    assert b["chip"] == "🩳 SI 5.0% shs out · ≤1d · 10/30 · ⚠️ float updated · ✂️ split 11/10"


def test_NEGATIVE_dfl_with_a_good_newer_float_is_judged_across_the_split():
    rec, doc = _dfl(150000)                                                 # 150K ≤ 200K: the newer float is good
    v = BM.verdict(rec, doc, TODAY)
    assert v["float_update"]["suspect"] is None
    assert v["refused_reasons"] == ["split"]                                # 11/19 float vs the 10/30 count
