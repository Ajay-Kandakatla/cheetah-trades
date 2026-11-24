"""🩳 % of float — a NEWER dated Yahoo float replaces the record's (2026-11-24 later).

Ajay 2026-11-24, verbatim: "Is GMEX float accurate?" (after "Make sure we are looking for Dilution.." and "Also split
related events and filing so we flag them in the right way").

GMEX's short-interest record divided FINRA's 12,722 (10-30) by Yahoo's float of 20,235 read 11-02 → "High 62.9% float ·
float unconfirmed". Its own share-basis doc held a NEWER Yahoo read (11-19): float 361,428 on the SAME 752,439 shares
outstanding → 3.52% of float — on Yahoo's newer read, not confirmed by a filing. `basis_math.newer_float` lets the
newer dated float be the one divided by, with "⚠️ float updated — NEW (Yahoo M/D) replaced OLD (M/D)", and the split-side
check judges it. FIX (verifier, same day): the newer float is used ONLY for the division and the split-side check — the
dilution-filing window, the share-growth check and the stored float track keep the REPLACED float's own date and count
(SRTM's +421-share Yahoo drift had wiped ⚠️ float stale and 📄; AAOI / ALTG / ALXO / DCGO / SOAR lost 📄; LABT lost ⚠️).
No size cut: any difference, any later date.

NEGATIVES: an equal newer read, a missing / undated / NaN / zero / negative / bool / inf Yahoo float, an OLDER or
same-day read, no held splits read [C1], a legacy record, a raising fold; the record-float results of KITT / JELD / WETO
are pinned with the Yahoo float removed; every dilution flag main serves survives a newer float (SRTM / AAOI / ALTG /
ALXO / DCGO / SOAR / LABT on their live 11-24 numbers).
"""
from __future__ import annotations

import copy
import json
from datetime import date

import pytest

from short_interest import basis_math as BM
from short_interest import read as SR
from short_interest import share_basis as SB
from tests.test_si_basis_math_2026_11_24 import _doc, _jeld, _keys, _ok, _rec, _split

TODAY = date(2026, 11, 24)

GMEX_SPLITS = [_split("2026-01-08", 8, 1), _split("2026-05-01", 7, 1), _split("2026-07-02", 9, 1),
               _split("2026-09-28", 9, 1), _split("2026-11-27", 19, 1)]
GMEX_COVERS = [{"as_of": "2023-06-30", "shares": 8120000, "form": "20-F", "filed": "2023-10-30"},
               {"as_of": "2024-06-30", "shares": 20123386, "form": "20-F", "filed": "2024-11-15"},
               {"as_of": "2025-06-30", "shares": 21020597, "form": "20-F", "filed": "2025-11-14"}]
GMEX_YAHOO = {"float_shares": 361428, "shares_outstanding": 752439, "as_of": "2026-11-19"}
GMEX_TRACK = {"value": 20235, "since": "2026-11-02", "shares": 752439, "shares_asof": "2026-11-02",
              "basis_asof": "2026-11-02", "origin": "si_doc", "carried": []}
GMEX_TEXT = "⚠️ float updated — 361,428 (Yahoo 11/19) replaced 20,235 (11/2)"


def gmex_rec(**over):
    """The live record read 11-24 (Mongo short_interest_latest)."""
    d = dict(settlement_date="2026-10-30", short_interest=12722, prev_settlement_date="2026-10-15",
             prev_short_interest=55579, si_change_pct=-77.1, days_to_cover=1.0, avg_daily_volume=1235611,
             float_shares=20235, float_asof="2026-11-02", float_source="yfinance floatShares (shares_cache)",
             shares_outstanding=752439, shares_asof="2026-11-02",
             shares_source="yfinance sharesOutstanding (shares_cache)")
    d.update(over)
    return _rec("GMEX", **d)


def gmex_doc(yahoo="default", track=None, **kw):
    """The live basis doc read 11-24 (si_share_basis): CS, 20-F covers only, no filings, five reverse splits."""
    return _doc("GMEX", covers=GMEX_COVERS, filings=[], splits=GMEX_SPLITS, track=track or dict(GMEX_TRACK),
                yahoo=dict(GMEX_YAHOO) if yahoo == "default" else yahoo, **kw)


def blk(rec, doc):
    return SR.si_block(copy.deepcopy(rec), TODAY, basis=copy.deepcopy(doc))


# ═════════════════════════════════════════════ GMEX — the asked name
def test_GMEX_newer_yahoo_float_heads_with_the_flag():
    v = BM.verdict(gmex_rec(), gmex_doc(), TODAY)
    fu = v["float_update"]
    assert (fu["shares"], fu["as_of"], fu["source"]) == (361428, "2026-11-19", "yahoo")
    assert (fu["replaced_shares"], fu["replaced_asof"], fu["paired_shares"]) == (20235, "2026-11-02", 752439)
    assert fu["pct"] == round(12722 / 361428 * 100, 2) == 3.52 and fu["suspect"] is None
    assert v["flags"][0] == {"key": "float_updated", "emoji": "⚠️", "short": "⚠️ float updated", "text": GMEX_TEXT}
    assert v["float_refused"] is None and v["refused_reasons"] == []
    assert _keys(v) == ["float_updated", "split"] and v["flags"][1]["short"] == "✂️ split due 11/27"
    # the track (filing window + growth baseline) keeps the REPLACED float's first-seen date and count
    assert (v["track"]["value"], v["track"]["since"], v["track"]["shares"]) == (20235, "2026-11-02", 752439)
    json.dumps(v, allow_nan=False)


def test_GMEX_served_block_low_3_5pct_of_float():
    plain = SR.si_block(gmex_rec(), TODAY)
    assert plain["chip"] == "🩳 SI High 62.9% float · float unconfirmed · 1.0d · 10/30"        # what was served
    b = blk(gmex_rec(), gmex_doc())
    assert b["chip"] == "🩳 SI Low 3.5% float · 1.0d · 10/30 · ⚠️ float updated · ✂️ split due 11/27"
    assert (b["pct_of_float"], b["tier"], b["float_check"]) == (3.52, "low", None)
    assert (b["float_shares"], b["float_asof"], b["float_source"]) == (361428, "2026-11-19", SR.YAHOO_LIVE_FLOAT_SOURCE)
    assert b["pct_of_shares_out"] == 1.69 and b["shares_outstanding"] == 752439 and b["headline_basis"] == "float"
    assert b["basis"]["float_update"]["replaced_shares"] == 20235 and set(b["basis"]) == set(SR.BASIS_KEYS)
    assert GMEX_TEXT + "." in b["title"] and "3.5% of float — float 361.4K, " + SR.YAHOO_LIVE_FLOAT_SOURCE in b["title"]
    assert {"k": "Float updated", "v": GMEX_TEXT} in b["rows"]
    assert b["extreme"] is None
    json.dumps(b, allow_nan=False)


# ═════════════════════════════════════════════ negatives — the record's float stands
def test_NEGATIVE_an_equal_newer_read_has_no_flag():
    v = BM.verdict(gmex_rec(), gmex_doc(yahoo=dict(GMEX_YAHOO, float_shares=20235)), TODAY)
    assert v["float_update"] is None and "float_updated" not in _keys(v)
    b = blk(gmex_rec(), gmex_doc(yahoo=dict(GMEX_YAHOO, float_shares=20235)))
    assert b["pct_of_float"] == 62.87 and "float updated" not in b["chip"]


@pytest.mark.parametrize("bad", [None, 0, -361428, float("nan"), float("inf"), True, "x", "361428x"])
def test_NEGATIVE_a_missing_or_bad_newer_float_keeps_the_record(bad):
    doc = gmex_doc(yahoo=dict(GMEX_YAHOO, float_shares=bad))
    assert BM.newer_float(gmex_rec(), doc) is None
    b = blk(gmex_rec(), doc)
    assert (b["float_shares"], b["pct_of_float"], b["float_source"]) == (20235, 62.87, SR.FLOAT_SOURCE)
    assert "float updated" not in b["chip"] and "float_update" not in b["basis"]


@pytest.mark.parametrize("yahoo", [None, "x", [], {}, {"float_shares": 361428}])
def test_NEGATIVE_no_yahoo_read_keeps_the_record(yahoo):
    assert BM.newer_float(gmex_rec(), gmex_doc(yahoo=yahoo)) is None
    assert blk(gmex_rec(), gmex_doc(yahoo=yahoo))["pct_of_float"] == 62.87


@pytest.mark.parametrize("asof", [None, "", "garbage", True, 5])
def test_NEGATIVE_an_undated_newer_read_keeps_the_record(asof):
    doc = gmex_doc(yahoo=dict(GMEX_YAHOO, as_of=asof))
    assert BM.newer_float(gmex_rec(), doc) is None
    assert blk(gmex_rec(), doc)["pct_of_float"] == 62.87


@pytest.mark.parametrize("asof", ["2026-10-01", "2026-11-01", "2026-11-02"])
def test_NEGATIVE_an_older_or_same_day_read_never_wins(asof):
    doc = gmex_doc(yahoo=dict(GMEX_YAHOO, as_of=asof))
    assert BM.newer_float(gmex_rec(), doc) is None
    b = blk(gmex_rec(), doc)
    assert b["float_shares"] == 20235 and b["float_asof"] == "2026-11-02" and "float updated" not in b["chip"]


def test_the_older_read_never_wins_when_the_RECORD_is_the_newer_one():
    rec = gmex_rec(float_shares=361428, float_asof="2026-11-24")
    doc = gmex_doc(yahoo=dict(GMEX_YAHOO, float_shares=20235, as_of="2026-11-19"))
    assert BM.newer_float(rec, doc) is None
    assert blk(rec, doc)["float_shares"] == 361428


@pytest.mark.parametrize("sp", [{"status": "failed", "error": "Timeout", "rows": []}, {}, {"status": None},
                                {"status": "not_read"}])
def test_NEGATIVE_no_held_splits_read_replaces_nothing_C1(sp):
    doc = gmex_doc(sp=sp)
    assert BM.newer_float(gmex_rec(), doc) is None
    b = blk(gmex_rec(), doc)
    assert b["pct_of_float"] == 62.87 and "float updated" not in b["chip"]


def test_held_splits_after_a_failed_retry_still_count_C1():
    doc = gmex_doc(sp=_ok(since="2025-06-30", rows=GMEX_SPLITS, error="Timeout", error_at="2026-11-24T19:00:00Z"))
    assert BM.newer_float(gmex_rec(), doc)["shares"] == 361428


def test_NEGATIVE_a_legacy_record_has_no_float_to_replace():
    rec = gmex_rec(v=1, fetched_at=1794354002.5)
    assert BM.newer_float(rec, gmex_doc()) is None
    assert blk(rec, gmex_doc())["float_shares"] is None


@pytest.mark.parametrize("rec,doc", [(None, None), ("x", {}), ({}, {"yahoo": GMEX_YAHOO}), ({"v": 2}, [])])
def test_NEGATIVE_junk_inputs(rec, doc):
    assert BM.newer_float(rec, doc) is None


# ═════════════════════════════════════════════ the split rules judge the newer float
def _pre_split_case(**yahoo_over):
    """SI counted 11-13 AFTER a 1-for-10 split on 11-10; the record float read 11-01; Yahoo's newer read 11-05 —
    the newer read itself predates the split after it."""
    rec = _rec("PRE", settlement_date="2026-11-13", short_interest=50000, prev_settlement_date=None,
               prev_short_interest=None, float_shares=900000, float_asof="2026-11-01",
               shares_outstanding=2000000, shares_asof="2026-11-01")
    y = {"float_shares": 1000000, "shares_outstanding": 2000000, "as_of": "2026-11-05"}
    y.update(yahoo_over)
    doc = _doc("PRE", covers=[], filings=[], splits=[_split("2026-11-10", 10, 1)], yahoo=y)
    return rec, doc


def test_a_newer_read_before_a_later_split_is_refused_by_the_split_rules():
    rec, doc = _pre_split_case()
    v = BM.verdict(rec, doc, TODAY)
    assert v["float_update"]["shares"] == 1000000 and v["float_update"]["pct"] is None
    assert v["float_refused"] == "split" and _keys(v)[:2] == ["float_updated", "split"]
    assert "the float on file dates from before it (first seen, 11/5)" in v["float_line"]
    b = blk(rec, doc)
    assert b["pct_of_float"] is None and b["tier"] is None
    assert b["pct_of_shares_out"] is None and b["basis"]["float_refused"] == "split"   # no count on the count's side
    assert b["float_shares"] == 1000000 and "1,000,000, " + SR.YAHOO_LIVE_FLOAT_SOURCE in b["title"]
    assert b["basis"]["float_pct_on_file"] == 5.0                    # 50,000 / 1,000,000 — the float it refused


def test_a_newer_read_AFTER_the_split_on_the_counts_side_is_read():
    rec, doc = _pre_split_case(float_shares=100000, shares_outstanding=200000, as_of="2026-11-20")
    v = BM.verdict(rec, doc, TODAY)
    assert v["float_refused"] is None and v["float_update"]["pct"] == 50.0
    assert BM.verdict(rec, _pre_split_case()[1], TODAY)["float_refused"] == "split"      # the same name, pre-split read


def test_a_newer_read_ON_the_split_day_is_split_same_day():
    rec, doc = _pre_split_case(as_of="2026-11-10")
    assert BM.verdict(rec, doc, TODAY)["float_refused"] == "split_same_day"


# ═════════════════════════════════════════════ the suspect rule pairs the newer float with ITS row
def test_a_newer_float_above_its_own_rows_count_never_replaces_a_good_record_float():
    # 2026-11-24 verifier finding 1: a suspect newer float leaves GMEX's good record float standing (was: replaced and
    # shares-headed). The suspect-and-served path (record float suspect too) is pinned in
    # test_si_float_newer_fixes_2026_11_24.py.
    doc = gmex_doc(yahoo=dict(GMEX_YAHOO, float_shares=800000))                  # > 752,439 on the same row
    v = BM.verdict(gmex_rec(), doc, TODAY)
    assert v["float_update"] is None and "float_updated" not in _keys(v)
    b = blk(gmex_rec(), doc)
    assert b["float_suspect"] is None and b["pct_of_float"] == 62.87 and b["float_shares"] == 20235
    assert b["headline_basis"] == "float" and "float updated" not in b["chip"]


def test_with_no_count_on_the_yahoo_row_the_record_count_pairs():
    doc = gmex_doc(yahoo={"float_shares": 361428, "shares_outstanding": None, "as_of": "2026-11-19"})
    v = BM.verdict(gmex_rec(), doc, TODAY)
    assert v["float_update"]["paired_shares"] is None and v["float_update"]["pct"] == 3.52
    assert v["track"]["shares"] == 752439 and v["track"]["since"] == "2026-11-02"   # the record's pair stands


# ═════════════════════════════════════════════ the names pinned on the record float before (Yahoo float removed)
def _no_yfloat(doc):
    d = copy.deepcopy(doc)
    d["yahoo"] = dict(d["yahoo"], float_shares=None)
    return d


def test_KITT_record_float_result_unchanged_without_the_newer_float():
    rec = _rec("KITT", short_interest=203890, float_shares=5527831, float_asof="2026-09-03",
               shares_outstanding=7471960, shares_asof="2026-09-03", days_to_cover=3.58)
    doc = _doc("KITT", splits=[_split("2026-09-25", 6, 1)],
               covers=[{"as_of": "2026-08-12", "shares": 7471960, "form": "10-Q", "filed": "2026-08-12"},
                       {"as_of": "2026-11-16", "shares": 2643176, "form": "10-Q", "filed": "2026-11-16"}],
               filings=[{"form": "10-Q", "filed": "2026-11-16", "items": ""},
                        {"form": "S-1", "filed": "2026-11-12", "items": ""},
                        {"form": "8-K", "filed": "2026-09-23", "items": "3.03,5.03,8.01,9.01"}],
               yahoo={"float_shares": 1612787, "shares_outstanding": 2643176, "as_of": "2026-11-23"})
    old = BM.verdict(rec, _no_yfloat(doc), TODAY)
    assert old["refused_reasons"] == ["split", "diluted"] and old["pct_of_shares_out"] == 7.71
    assert old["growth"]["ratio"] == pytest.approx(2.122, abs=1e-3) and old["float_update"] is None
    new = blk(rec, doc)                                  # the newer float clears the split side, not the dilution
    assert new["basis"]["refused_reasons"] == ["diluted"] and new["pct_of_float"] is None and new["tier"] is None
    # refix 3: a dilution refusal's on-file % is on the REPLACED float, as on main (203,890 / 5,527,831)
    assert new["basis"]["float_pct_on_file"] == 3.69 and "float_stale" in [f["key"] for f in new["basis"]["flags"]]


@pytest.mark.parametrize("m,refused", [("any_increase", True), ("tier_moves", False), ("added_exceeds_float", False)])
def test_JELD_record_float_modes_unchanged_without_the_newer_float(monkeypatch, m, refused):
    monkeypatch.setattr(BM, "FLOAT_STALE_WHEN", m)
    rec, doc = _jeld()
    assert (BM.verdict(rec, _no_yfloat(doc), TODAY)["float_refused"] == "diluted") is refused
    assert (BM.verdict(rec, doc, TODAY)["float_refused"] == "diluted") is refused     # growth is judged as before


def test_WETO_record_float_result_unchanged_without_the_newer_float():
    rec = _rec("WETO", short_interest=241900, float_shares=186729, float_asof="2026-11-02",
               shares_outstanding=1077801, shares_asof="2026-11-02")
    doc = _doc("WETO", splits=[], filings=[{"form": "6-K", "filed": "2026-11-19", "items": ""}],
               covers=[{"as_of": "2025-06-30", "shares": 22000000, "form": "20-F", "filed": "2025-10-30"},
                       {"as_of": "2026-06-30", "shares": 821300, "form": "20-F", "filed": "2026-11-05"}],
               yahoo={"float_shares": 14735015, "shares_outstanding": 14897999, "as_of": "2026-11-20"})
    old = blk(rec, _no_yfloat(doc))
    assert old["chip"] == "🩳 SI 1.6% shs out · 1.0d · 10/30 · ⚠️ shares up 14×"
    assert old["float_suspect"] == SR.SHORT_EXCEEDS_FLOAT and "float_update" not in old["basis"]
    new = blk(rec, doc)
    assert new["chip"] == "🩳 SI Low 1.6% float · 1.0d · 10/30 · ⚠️ float updated · ⚠️ shares up 14×"


# ═════════════════════════════════════════════ the track keeps the REPLACED float's first-seen date
def test_NEGATIVE_no_track_helper_lays_the_newer_float_over_the_record():
    assert not hasattr(SB, "_track_record") and not hasattr(BM, "float_record")    # the stored track follows the record


def test_a_stored_track_keeps_the_record_floats_first_seen_date_under_a_newer_read():
    for asof in ("2026-11-19", "2026-11-24"):
        doc = gmex_doc(yahoo=dict(GMEX_YAHOO, as_of=asof))
        v = BM.verdict(gmex_rec(), doc, TODAY)
        assert v["track"]["since"] == "2026-11-02" and v["float_update"]["as_of"] == asof


# ═════════════════════════════════════════════ FIX: dilution keeps the REPLACED float's date and count
# Live 11-24 numbers (Mongo short_interest_latest + si_share_basis). Before the fix a newer Yahoo float moved the
# filing window and the growth baseline to the Yahoo read date and the flags below vanished.
SRTM_SPLITS = [_split("2026-11-23", 9, 1)]
SRTM_COVERS = [{"as_of": "2026-06-04", "shares": 1616081, "form": "10-K", "filed": "2026-06-04"},
               {"as_of": "2026-07-31", "shares": 2108277, "form": "10-Q", "filed": "2026-07-31"},
               {"as_of": "2026-08-20", "shares": 3317834, "form": "10-Q", "filed": "2026-08-21"}]
SRTM_FILINGS = [{"form": "424B3", "filed": "2026-11-06", "items": ""}, {"form": "S-1/A", "filed": "2026-10-30", "items": ""},
                {"form": "S-1", "filed": "2026-10-29", "items": ""},
                {"form": "8-K", "filed": "2026-10-26", "items": "3.02,9.01"}]


def srtm():
    rec = _rec("SRTM", short_interest=40070, prev_settlement_date=None, prev_short_interest=None, si_change_pct=None,
               float_shares=552120, float_asof="2026-10-26", shares_outstanding=569639, shares_asof="2026-10-26")
    doc = _doc("SRTM", covers=SRTM_COVERS, filings=SRTM_FILINGS, splits=SRTM_SPLITS,
               yahoo={"float_shares": 552541, "shares_outstanding": 4539240, "as_of": "2026-11-20"},
               track={"value": 552120, "since": "2026-10-26", "shares": 569639, "shares_asof": "2026-10-26",
                      "basis_asof": "2026-10-26", "origin": "si_doc", "carried": []})
    return rec, doc


def _same_dilution(rec, doc):
    """The newer float changes NOTHING on the dilution side: same filings, growth, refusal-for-dilution, track and
    every flag the record-float read raised (the newer float only adds ⚠️ float updated)."""
    old, new = BM.verdict(rec, _no_yfloat(doc), TODAY), BM.verdict(rec, doc, TODAY)
    assert old["float_update"] is None and new["float_update"] is not None
    assert new["filings"] == old["filings"] and new["growth"] == old["growth"] and new["track"] == old["track"]
    assert ("diluted" in new["refused_reasons"]) == ("diluted" in old["refused_reasons"])
    assert set(_keys(old)) <= set(_keys(new)) and _keys(new)[0] == "float_updated"
    return old, new


def test_SRTM_a_421_share_newer_float_is_still_refused_as_stale_with_its_filings():
    rec, doc = srtm()
    old, new = _same_dilution(rec, doc)
    assert new["float_update"]["replaced_shares"] == 552120 and new["float_update"]["shares"] == 552541
    assert new["float_refused"] == "diluted" and new["float_update"]["pct"] is None
    assert new["growth"]["to_shares"] == 4539240 and new["growth"]["from_shares"] == 569639
    assert [f["form"] for f in new["filings"]] == ["424B3", "S-1/A", "S-1"]       # 8-K 10/26 = the float's own day
    b = blk(rec, doc)
    assert b["chip"] == ("🩳 SI 0.9% shs out · 1.0d · 10/30 · ⚠️ float updated · ⚠️ float stale · ✂️ split 11/23 · "
                         "📄 424B3 11/6 +2")
    assert b["pct_of_float"] is None and b["tier"] is None
    assert blk(rec, _no_yfloat(doc))["chip"] == ("🩳 SI 0.9% shs out · 1.0d · 10/30 · ⚠️ float stale · ✂️ split 11/23"
                                                 " · 📄 424B3 11/6 +2")                    # what main serves


def test_AAOI_a_424B5_filed_between_the_two_float_dates_is_still_flagged():
    rec = _rec("AAOI", short_interest=18036843, prev_short_interest=16296183, si_change_pct=10.7, days_to_cover=1.62,
               float_shares=80855802, float_asof="2026-10-20", shares_outstanding=84906289, shares_asof="2026-10-20")
    doc = _doc("AAOI", splits=[], filings=[{"form": "424B5", "filed": "2026-11-17", "items": ""}],
               covers=[{"as_of": "2026-08-03", "shares": 84569237, "form": "10-Q", "filed": "2026-08-06"},
                       {"as_of": "2026-11-02", "shares": 90770732, "form": "10-Q", "filed": "2026-11-05"}],
               yahoo={"float_shares": 86771374, "shares_outstanding": 90771506, "as_of": "2026-11-23"})
    _old, new = _same_dilution(rec, doc)
    assert "2026-10-20" < "2026-11-17" < "2026-11-23" and [f["form"] for f in new["filings"]] == ["424B5"]
    b = blk(rec, doc)
    assert "📄 424B5 11/17" in b["chip"] and b["pct_of_float"] == round(18036843 / 86771374 * 100, 2)


@pytest.mark.parametrize("sym,si,F,Fa,P,yf,ys,ya,filed,items", [
    ("ALTG", 677987, 17980826, "2026-09-12", 32666872, 17900024, 32833236, "2026-11-24", "2026-11-23",
     "1.01,3.02,5.02,7.01,8.01,9.01"),
    ("DCGO", 2133153, 96121771, "2026-09-12", 98928369, 96185914, 98992347, "2026-11-23", "2026-10-05",
     "1.01,1.02,2.03,3.02,8.01"),
    ("SOAR", 2565811, 38416423, "2026-09-03", 53633248, 38406233, 56607771, "2026-11-23", "2026-10-09",
     "1.01,3.02,3.03,5.03,9.01"),
    ("ALXO", 6166023, 94708681, "2026-10-14", 138276997, 65918395, 129274568, "2026-11-24", "2026-10-15",
     "1.01,3.02,9.01"),
])
def test_an_8K_item_3_02_since_the_replaced_float_is_still_flagged(sym, si, F, Fa, P, yf, ys, ya, filed, items):
    rec = _rec(sym, short_interest=si, float_shares=F, float_asof=Fa, shares_outstanding=P, shares_asof=Fa)
    doc = _doc(sym, splits=[], covers=[], filings=[{"form": "8-K", "filed": filed, "items": items}],
               yahoo={"float_shares": yf, "shares_outstanding": ys, "as_of": ya})
    _old, new = _same_dilution(rec, doc)
    assert [f["kind"] for f in new["filings"]] == [BM.KIND_UNREGISTERED]
    assert "📄 8-K 3.02 %s" % BM._md(filed) in blk(rec, doc)["chip"]


def test_LABT_keeps_float_stale_under_its_newer_float():
    rec = _rec("LABT", short_interest=152917, prev_short_interest=90040, float_shares=847661, float_asof="2026-11-09",
               shares_outstanding=2369688, shares_asof="2026-11-09")
    doc = _doc("LABT", splits=[], filings=[],
               covers=[{"as_of": "2026-08-03", "shares": 2369688, "form": "10-Q", "filed": "2026-08-14"},
                       {"as_of": "2026-11-13", "shares": 8950088, "form": "10-Q", "filed": "2026-11-16"}],
               yahoo={"float_shares": 3201536, "shares_outstanding": 8950088, "as_of": "2026-11-18"})
    _old, new = _same_dilution(rec, doc)
    assert new["float_refused"] == "diluted" and "float_stale" in _keys(new)
    b = blk(rec, doc)
    assert b["chip"] == "🩳 SI 1.7% shs out · 1.0d · 10/30 · ⚠️ float updated · ⚠️ float stale"
    assert b["tier"] is None and b["pct_of_float"] is None


def test_GMEX_still_low_3_5pct_and_its_dilution_side_is_the_record_floats():
    _old, new = _same_dilution(gmex_rec(), gmex_doc())
    assert new["float_update"]["pct"] == 3.52 and new["float_refused"] is None


def test_NEGATIVE_a_filing_on_or_before_the_replaced_floats_date_is_not_flagged():
    rec, doc = srtm()
    doc["sec"]["filings"] = [{"form": "8-K", "filed": "2026-10-26", "items": "3.02,9.01"},
                             {"form": "S-1", "filed": "2026-10-01", "items": ""}]
    assert BM.verdict(rec, doc, TODAY)["filings"] == [] and "📄" not in blk(rec, doc)["chip"]


def test_NEGATIVE_no_newer_float_serves_no_float_update_key():
    rec, doc = srtm()
    b = blk(rec, _no_yfloat(doc))
    assert "float_update" not in b["basis"] and set(b["basis"]) == set(SR.BASIS_KEYS) - {"float_update"}
    assert "float_update" in blk(rec, doc)["basis"]


# ═════════════════════════════════════════════ read-side folds
def test_a_raising_fold_serves_the_record_float(monkeypatch):
    real = SR._apply_verdict

    def half(b, v):
        real(b, v)
        raise RuntimeError("boom")

    monkeypatch.setattr(SR, "_apply_verdict", half)
    b = blk(gmex_rec(), gmex_doc())
    assert (b["float_shares"], b["float_asof"], b["float_source"], b["pct_of_float"]) == \
        (20235, "2026-11-02", SR.FLOAT_SOURCE, 62.87)
    assert b["basis"]["status"] == "failed"


def _extreme_case(**yahoo_over):
    rec = _rec("XTR", short_interest=500000, prev_settlement_date=None, prev_short_interest=None,
               float_shares=2000000, float_asof="2026-11-02", shares_outstanding=2500000, shares_asof="2026-11-02")
    y = {"float_shares": 1000000, "shares_outstanding": 2500000, "as_of": "2026-11-20"}
    y.update(yahoo_over)
    return rec, _doc("XTR", covers=[], filings=[], splits=[], yahoo=y)


def test_the_EXTREME_note_names_the_newer_float():
    rec, doc = _extreme_case()
    b = blk(rec, doc)
    assert b["tier"] == "extreme" and b["pct_of_float"] == 50.0
    t = b["extreme"]["title"]
    assert (SR.EXTREME_FLOAT_UPDATED_NOTE % ("1,000,000", SR.YAHOO_LIVE_FLOAT_SOURCE, "2026-11-20")) in t
    assert "the float stored with this short-interest record at the last warm" not in t
    assert b["extreme"]["short"].endswith(" · ⚠️ float updated")


def test_NEGATIVE_the_EXTREME_note_without_an_update_is_unchanged():
    rec, doc = _extreme_case(float_shares=2000000)                         # equal → no update; 25% EXTREME
    b = blk(rec, doc)
    assert b["tier"] == "extreme" and "float_update" not in b["basis"]
    assert (SR.EXTREME_FLOAT_BASIS_NOTE % ("2,000,000", SR.FLOAT_SOURCE, "2026-11-02")) in b["extreme"]["title"]


def test_no_basis_doc_is_byte_identical():
    assert SR.si_block(gmex_rec(), TODAY) == SR.si_block(gmex_rec(), TODAY, basis=None)
    assert "basis" not in SR.si_block(gmex_rec(), TODAY)


def test_rules_sentence_names_the_flag():
    assert BM.SHORT_FLOAT_UPDATED in BM.rules_sentence()
    assert BM.FLAG_ROW_LABEL[BM.FLAG_FLOAT_UPDATED] == "Float updated"
