"""🩳 newer Yahoo float — the verifier's second-round findings 1–5 (2026-11-24, later still).

Ajay 2026-11-24, verbatim: "Is GMEX float accurate?" (after "Make sure we are looking for Dilution.." and "Also split
related events and filing so we flag them in the right way").

1. A newer Yahoo float that fails its own suspect check never replaces a GOOD record float (case a: the record's
   EXTREME 30.0% float stands; case b: the split refusal on the record float stands at 50.0% shs out).
2. A good newer float divided by while the record's share count sits across a split from the settlement: the % of shares
   outstanding (and so the EXTREME float check) uses step 3's count choice, else the newer float's own Yahoo row —
   never the pre-split count (66.7% of float no longer reads "High · float unconfirmed" off a 5.0% pre-split count).
3. The "% of float: not shown — float stale" line names the REPLACED float (LABT 847,661 as of 11/9), not Yahoo's newer
   read; a split refusal under a newer float still names the newer float (it is the one across the split).
4. 🩳 High SI `floats_text` says the block's float is Yahoo's newer read when one replaced the record's.
5. The split wording under a newer float says "first seen" (its own date), never "carried across it".

NEGATIVES: a suspect newer float with a suspect record float is still served (with its suspect reason); the count on
the settlement's side of every split is left alone; no Yahoo row count → no % of shares outstanding; no float_update →
the record float is named; the old floats_text wording without an update.
"""
from __future__ import annotations

import copy
from datetime import date

from chart_maps.gajjala import high_si as HS
from short_interest import basis_math as BM
from short_interest import read as SR
from tests.test_gajjala_high_si_2026_11_23 import fr
from tests.test_si_basis_math_2026_11_24 import _doc, _keys, _rec, _split
from tests.test_si_float_newer_2026_11_24 import gmex_doc, gmex_rec

TODAY = date(2026, 11, 24)


def blk(rec, doc):
    return SR.si_block(copy.deepcopy(rec), TODAY, basis=copy.deepcopy(doc))


def _no_counts(b):
    """2026-11-26 sishares §3.4: the block without `basis.share_counts` (it lists the Yahoo row's float as read)."""
    b = copy.deepcopy(b)
    b["basis"].pop("share_counts", None)
    return b


def _yahoo_none(doc):
    d = copy.deepcopy(doc)
    d["yahoo"] = dict(d["yahoo"], float_shares=None)
    return d


# ═════════════════════════════════════════════ 1. a suspect newer float never replaces a good record float
def _case_a():
    """The verifier's mixed2.py: record float 1,000,000 on 2,000,000 shares; Yahoo 11/19 2,100,000 on 2,050,000."""
    rec = _rec("ZZA", settlement_date="2026-10-30", short_interest=300000, float_shares=1000000,
               float_asof="2026-09-01", shares_outstanding=2000000, shares_asof="2026-09-01",
               prev_settlement_date=None, prev_short_interest=None)
    doc = _doc("ZZA", covers=[], filings=[], splits=[],
               yahoo={"float_shares": 2100000, "shares_outstanding": 2050000, "as_of": "2026-11-19"})
    return rec, doc


def _case_b(yf, ys):
    """The verifier's mixed.py: 1-for-10 on 10/20; record float 1,000,000 and count 2,000,000 read 9/1 (pre-split)."""
    rec = _rec("ZZB", settlement_date="2026-10-30", short_interest=100000, float_shares=1000000,
               float_asof="2026-09-01", shares_outstanding=2000000, shares_asof="2026-09-01",
               prev_settlement_date="2026-10-15", prev_short_interest=90000)
    doc = _doc("ZZB", covers=[], filings=[], splits=[_split("2026-10-20", 10, 1)],
               yahoo={"float_shares": yf, "shares_outstanding": ys, "as_of": "2026-11-19"})
    return rec, doc


def test_case_a_suspect_newer_float_leaves_the_record_EXTREME_30pct():
    rec, doc = _case_a()
    v = BM.verdict(rec, doc, TODAY)
    assert v["float_update"] is None and "float_updated" not in _keys(v)
    b = blk(rec, doc)
    # 2026-11-26 sitrack A4: the provider's 1.0 with no ADV on the record is FINRA's floor → '≤1d'
    assert b["chip"] == "🩳 SI EXTREME 30.0% float · ≤1d · 10/30"
    assert (b["pct_of_float"], b["tier"], b["float_check"]) == (30.0, "extreme", "confirmed")
    assert (b["float_shares"], b["float_asof"], b["float_source"]) == (1000000, "2026-09-01", SR.FLOAT_SOURCE)
    assert b["float_suspect"] is None and "float_update" not in b["basis"]
    assert {"k": "% of float", "v": "not read — no float on file"} not in b["rows"]
    # 2026-11-26 sishares §3.4 / §5.5: basis.share_counts lists Yahoo's row (its float too) — dropped before comparing
    assert _no_counts(b) == _no_counts(blk(rec, _yahoo_none(doc)))      # exactly the record-float block


def test_case_b_suspect_newer_float_keeps_the_record_floats_split_refusal():
    rec, doc = _case_b(300000, 200000)                         # float > its own row's count → suspect
    v = BM.verdict(rec, doc, TODAY)
    assert v["float_update"] is None and v["float_refused"] == "split"
    b = blk(rec, doc)
    # 2026-11-26 sitrack A4: the provider's 1.0 with no ADV on the record is FINRA's floor → '≤1d'
    assert b["chip"] == "🩳 SI 50.0% shs out · ≤1d · 10/30 · ✂️ split 10/20"
    assert (b["pct_of_shares_out"], b["shares_outstanding"], b["tier"]) == (50.0, 200000, None)
    assert b["basis"]["float_refused"] == "split" and "float updated" not in b["chip"]
    assert _no_counts(b) == _no_counts(blk(rec, _yahoo_none(doc)))      # 2026-11-26 sishares §5.5 (share_counts)


def test_NEGATIVE_a_suspect_newer_float_over_a_suspect_record_float_is_still_served():
    doc = gmex_doc(yahoo={"float_shares": 800000, "shares_outstanding": 752439, "as_of": "2026-11-19"})
    rec = gmex_rec(float_shares=900000)                        # record float > its count → the record is suspect too
    v = BM.verdict(rec, doc, TODAY)
    assert v["float_update"]["shares"] == 800000 and v["float_update"]["suspect"] == SR.FLOAT_EXCEEDS_SHARES
    b = blk(rec, doc)
    assert b["float_suspect"] == SR.FLOAT_EXCEEDS_SHARES and b["headline_basis"] == "shares_out"


# ═════════════════════════════════════════════ 2. the count across a split under a good newer float
def test_newer_ok_float_reads_EXTREME_on_the_post_split_count():
    rec, doc = _case_b(150000, 200000)
    v = BM.verdict(rec, doc, TODAY)
    assert v["float_refused"] is None and v["float_update"]["pct"] == 66.67
    assert v["count"] == {"shares": 200000, "as_of": "2026-11-19", "source": "yahoo", "form": None}
    assert v["pct_of_shares_out"] == 50.0 and v["count_changed"] is True
    b = blk(rec, doc)
    # 2026-11-26 sitrack A4: the provider's 1.0 with no ADV on the record is FINRA's floor → '≤1d'
    assert b["chip"] == "🩳 SI EXTREME 66.7% float · ≤1d · 10/30 · ⚠️ float updated · ✂️ split 10/20"
    assert (b["tier"], b["float_check"]) == ("extreme", "confirmed")
    assert (b["shares_outstanding"], b["shares_asof"], b["shares_source"]) == \
        (200000, "2026-11-19", SR.YAHOO_LIVE_SHARES_SOURCE)
    assert "float unconfirmed" not in b["chip"]


def _fallback_case(ys, yf=1500000):
    """Split 11/5 AFTER the 10/30 settlement; record count read 11/10 (post-split), record float 10/1 (pre); Yahoo's
    newer float 10/31 sits on the settlement's side and its row predates the record count, so step 3 finds no count."""
    rec = _rec("ZZC", settlement_date="2026-10-30", short_interest=60000, float_shares=150000,
               float_asof="2026-10-01", shares_outstanding=200000, shares_asof="2026-11-10",
               prev_settlement_date=None, prev_short_interest=None)
    doc = _doc("ZZC", covers=[], filings=[], splits=[_split("2026-11-05", 10, 1)],
               yahoo={"float_shares": yf, "shares_outstanding": ys, "as_of": "2026-10-31"})
    return rec, doc


def test_no_step3_count_falls_back_to_the_newer_floats_own_row():
    rec, doc = _fallback_case(2000000)
    v = BM.verdict(rec, doc, TODAY)
    assert v["float_refused"] is None and v["float_update"]["pct"] == 4.0
    assert v["count"] == {"shares": 2000000, "as_of": "2026-10-31", "source": "yahoo", "form": None}
    assert v["pct_of_shares_out"] == 3.0                       # not 30.0 off the post-split 200,000


def test_NEGATIVE_no_count_on_the_yahoo_row_serves_no_pct_of_shares_out():
    rec, doc = _fallback_case(None, yf=160000)                 # no row count; 160,000 passes the check vs the record's
    v = BM.verdict(rec, doc, TODAY)
    assert v["float_update"]["pct"] == 37.5
    assert v["count"] is None and v["no_pct"] is True and v["pct_of_shares_out"] is None
    b = blk(rec, doc)
    assert b["pct_of_shares_out"] is None and b["float_check"] == SR.FLOAT_UNCHECKED


def test_NEGATIVE_a_count_on_the_settlements_side_is_left_alone():
    v = BM.verdict(gmex_rec(), gmex_doc(), TODAY)              # GMEX: 752,439 read 11/2, same side as 10/30
    assert v["float_update"]["pct"] == 3.52 and v["count"] is None and v["count_changed"] is False
    assert blk(gmex_rec(), gmex_doc())["pct_of_shares_out"] == 1.69


# ═════════════════════════════════════════════ 3. the refusal line names the replaced float
def _labt(yahoo_float=3201536):
    rec = _rec("LABT", short_interest=152917, prev_short_interest=90040, float_shares=847661, float_asof="2026-11-09",
               shares_outstanding=2369688, shares_asof="2026-11-09")
    doc = _doc("LABT", splits=[], filings=[],
               covers=[{"as_of": "2026-08-03", "shares": 2369688, "form": "10-Q", "filed": "2026-08-14"},
                       {"as_of": "2026-11-13", "shares": 8950088, "form": "10-Q", "filed": "2026-11-16"}],
               yahoo={"float_shares": yahoo_float, "shares_outstanding": 8950088, "as_of": "2026-11-18"})
    return rec, doc


def test_LABT_refusal_line_names_the_replaced_847661_float():
    rec, doc = _labt()
    b = blk(rec, doc)
    want = "the float on file (847,661, %s, as of 2026-11-09) would read 18.04%%" % SR.FLOAT_SOURCE
    assert want in b["title"]
    assert "3,201,536, %s" % SR.YAHOO_LIVE_FLOAT_SOURCE not in b["title"]
    assert any(want in r["v"] for r in b["rows"])


def test_NEGATIVE_LABT_without_a_newer_float_names_the_record_float_as_before():
    rec, doc = _labt(yahoo_float=None)
    b = blk(rec, doc)
    assert "float_update" not in b["basis"]
    assert "the float on file (847,661, %s, as of 2026-11-09) would read 18.04%%" % SR.FLOAT_SOURCE in b["title"]


def test_NEGATIVE_a_split_refusal_under_a_newer_float_names_the_newer_float():
    rec = _rec("PRE", settlement_date="2026-11-13", short_interest=50000, prev_settlement_date=None,
               prev_short_interest=None, float_shares=900000, float_asof="2026-11-01",
               shares_outstanding=2000000, shares_asof="2026-11-01")
    doc = _doc("PRE", covers=[], filings=[], splits=[_split("2026-11-10", 10, 1)],
               yahoo={"float_shares": 1000000, "shares_outstanding": 2000000, "as_of": "2026-11-05"})
    b = blk(rec, doc)
    assert b["basis"]["float_refused"] == "split"
    assert ("the float on file (1,000,000, %s, as of 2026-11-05) would read 5.00%%" % SR.YAHOO_LIVE_FLOAT_SOURCE
            in b["title"])


# ═════════════════════════════════════════════ 4. 🩳 High SI floats_text under a newer float
def test_floats_text_says_yahoos_newer_read_when_it_replaced_the_record():
    b = blk(gmex_rec(), gmex_doc())
    assert HS.floats_text(fr(361428, text="Float 361.4K"), b) == \
        "Float 361.4K on this card · 361.4K from Yahoo's newer read (11/19), replacing 20.2K on the short-interest record"


def test_NEGATIVE_floats_text_without_an_update_keeps_the_record_wording():
    b = blk(gmex_rec(), _yahoo_none(gmex_doc()))
    assert HS.floats_text(fr(361428, text="Float 361.4K"), b) == \
        "Float 361.4K on this card · 20.2K on the short-interest record"


# ═════════════════════════════════════════════ 5. the split wording under a newer float
def _smx(yahoo_float):
    held = {"value": 791704, "since": "2026-11-05", "shares": 892857, "shares_asof": "2026-11-05",
            "basis_asof": "2026-11-05", "origin": "si_doc", "carried": []}
    rec = _rec("SMX", short_interest=47715, float_shares=282748, float_asof="2026-11-12", shares_outstanding=897717,
               shares_asof="2026-11-12", prev_short_interest=None, prev_settlement_date=None)
    doc = _doc("SMX", splits=[_split("2026-11-09", 2.8, 1)], track=held, filings=[],
               covers=[{"as_of": "2025-12-31", "shares": 1795943, "form": "20-F", "filed": "2026-03-20"}],
               yahoo={"float_shares": yahoo_float, "shares_outstanding": 897717, "as_of": "2026-11-20"})
    return rec, doc


def test_split_wording_under_a_newer_float_is_first_seen_on_its_own_date():
    rec, doc = _smx(282000)
    v = BM.verdict(rec, doc, TODAY)
    assert v["float_update"]["shares"] == 282000 and v["float_refused"] == "split"
    assert v["track"]["origin"] == BM.ORIGIN_CARRIED                # the RECORD float was carried across 11/9
    assert "the float on file dates from after it (first seen, 11/20)" in v["float_line"]
    assert "carried across it" not in v["float_line"]


def test_NEGATIVE_the_carried_record_float_still_says_carried_across_it():
    rec, doc = _smx(None)
    v = BM.verdict(rec, doc, TODAY)
    assert v["float_update"] is None and v["float_refused"] == "split"
    assert "the float on file dates from after it (carried across it, 11/5)" in v["float_line"]
