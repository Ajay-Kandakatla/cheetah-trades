"""🩳 % of float — dilution, splits, filings (2026-11-24): the served block, the map join and the route.

Ajay 2026-11-24, verbatim, in order: "Yeah please" · "Make sure we are looking for Dilution.." ·
"Also split related events and filing so we flag them in the right way"

Spec: scratchpad sidilute/spec.md REV 2 §3.4 (read.si_block(basis=), the flags in chip / title / rows / EXTREME note,
the rebased change phrase, a raising verdict) and §3.5 (api: kick ok / stale items, overlay basis.pending). Hermetic:
share-basis docs built by hand (tests/test_si_basis_math_2026_11_24.py builders), Mongo is the 10-03 fake, the seams
SR._basis_docs / api._kick_basis are patched. NEGATIVES: basis=None is byte-identical for every shared-fixture case
and carries no `basis` key; a raising verdict never costs the chip; junk leaves never reach the JSON.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import date
from pathlib import Path

import pytest

from short_interest import api as SAPI
from short_interest import basis_math as BM
from short_interest import client as SIC
from short_interest import read as SR
from short_interest import share_basis as SB
from tests.test_short_interest_read_2026_10_03 import FORBIDDEN, FakeColl, FakeDB, _run
from tests.test_si_basis_math_2026_11_24 import (
    SMTK_TRACK, TODAY, FWD, _clro, _doc, _jz, _ok, _poison, _rec, _rec_C, _smx_doc, _smx_rec, _split)

BACKEND = Path(__file__).resolve().parents[1]
FIXTURE = BACKEND / "tests" / "fixtures" / "short_interest_blocks_2026_10_03.json"
FIX = json.loads(FIXTURE.read_text(encoding="utf-8"))
FIX_TODAY = date.fromisoformat(FIX["today"])
CASES = {c["name"]: c for c in FIX["cases"]}
# 2026-11-26 sitrack A4: the provider's 1.0 with no ADV on the record is FINRA's floor → '≤1d'
SMTK_CHIP = "🩳 SI 8.9% shs out · ≤1d · 10/30 · ⚠️ float stale · ✂️ split 11/23 · 📄 S-4 11/13"


def _blk(rec, doc, today=TODAY):
    b = SR.si_block(rec, today, basis=doc)
    json.dumps(b, allow_nan=False)
    return b


def _texts(b):
    return [b["chip"] or "", b["title"]] + [r["k"] + " " + r["v"] for r in b["rows"]]


# ═════════════════════════════════════════════ NEGATIVE: no basis → byte-identical, no key
@pytest.mark.parametrize("name", sorted(CASES))
def test_NEGATIVE_basis_None_is_byte_identical_to_the_shared_fixture(name):
    c = CASES[name]
    b = SR.si_block(c["doc"], FIX_TODAY, basis=None)
    assert b == c["block"] and "basis" not in b
    assert json.dumps(b, ensure_ascii=False, sort_keys=True) == json.dumps(c["block"], ensure_ascii=False,
                                                                          sort_keys=True)
    assert list(b) == list(SR._BLOCK_KEYS)


@pytest.mark.parametrize("bad", ["x", 5, [], None])
def test_NEGATIVE_a_non_dict_basis_is_no_basis(bad):
    c = CASES["eose_v2_float"]
    assert SR.si_block(c["doc"], FIX_TODAY, basis=bad) == c["block"]


def test_NEGATIVE_a_no_record_block_is_untouched_by_a_basis_doc():
    rec = _rec(short_interest=None)
    assert SR.si_block(rec, TODAY, basis=_doc()) == SR.si_block(rec, TODAY)
    assert "basis" not in SR.si_block(rec, TODAY, basis=_doc())


# ═════════════════════════════════════════════ SMTK, captured (today 11-24)
def test_SMTK_block():
    b = _blk(_rec(), _doc())
    assert b["chip"] == SMTK_CHIP
    assert b["pct_of_float"] is None and b["pct_of_shares_out"] == 8.9 and b["tier"] is None
    assert b["float_check"] is None and b["extreme"] is None and b["headline_basis"] == "shares_out"
    assert b["shares_outstanding"] == 4859369 and b["shares_asof"] == "2026-11-11"
    assert b["shares_source"] == SR.SEC_SHARES_SOURCE % "10-Q"
    assert b["float_shares"] == 546875 and b["si_change_pct"] == 334.6 and b["prev_si_shares"] == 99473
    assert b["basis"]["float_refused"] == "diluted" and b["basis"]["float_pct_on_file"] == 79.05
    assert [f["key"] for f in b["basis"]["flags"]] == ["float_stale", "split", "filing"]
    assert set(b["basis"]) == set(SR.BASIS_KEYS) - {"float_update"}       # 2026-11-24 later: served only when used
    assert list(b)[:len(SR._BLOCK_KEYS)] == list(SR._BLOCK_KEYS) and list(b)[-1] == "basis"
    for needle in ("4.7×", "8.6×", "86,463 of today's shares", "Tier: not tiered — float stale.",
                   "% of float: not shown — float stale — 4.7× more shares than when the float was read",
                   "the float on file (546,875, yfinance floatShares (shares_cache), as of 2026-11-02) would read "
                   "79.05%", "8-K Item 5.03 11/23", "Share-count check: SEC cover count: read 11/24 13:05 ET"):
        assert needle in b["title"], needle
    rows = {r["k"]: r["v"] for r in b["rows"]}
    assert rows["% of float"].startswith("not shown — float stale — 4.7×")
    assert rows["Tier"].startswith(SR.TIER_FLOAT_STALE_TEXT)
    assert rows["Float stale"].startswith("⚠️ float stale — 4.7×") and "Share-count check" in rows
    assert not [t for t in _texts(b) if FORBIDDEN.search(t)]


def test_SMTK_tier_sentence_reads_the_served_block():
    b = _blk(_rec(), _doc())
    assert SR._tier_sentence(b) == SR.TIER_FLOAT_STALE_TEXT
    c = _blk(_rec_C(), _doc(track=dict(SMTK_TRACK), yahoo=None), FWD)
    assert SR._tier_sentence(c) == SR.TIER_SPLIT_TEXT
    assert SR.chip_text(b) == b["chip"]                       # a served block re-chips to the same string


# ═════════════════════════════════════════════ SMTK forward (today 12-10)
def test_forward_B_C_D_E_blocks():
    b = _blk(_rec(settlement_date="2026-11-13", short_interest=440000, float_asof="2026-11-18",
                  shares_outstanding=4859369, shares_asof="2026-11-18"), _doc(track=dict(SMTK_TRACK)), FWD)
    assert b["basis"]["float_refused"] == "diluted" and b["pct_of_shares_out"] == 9.05
    c = _blk(_rec_C(), _doc(track=dict(SMTK_TRACK), yahoo=None), FWD)
    assert c["basis"]["float_refused"] == "split" and c["basis"]["refused_reasons"] == ["split", "diluted"]
    assert c["shares_outstanding"] == 971874 and c["pct_of_shares_out"] == 9.05
    assert {"float_stale", "split"} <= {f["key"] for f in c["basis"]["flags"]}
    assert "% of float: not shown — 1-for-5 reverse split 11/23 — the float on file dates from before it" in c["title"]
    d = _blk(_rec_C(float_shares=109375), _doc(track=dict(SMTK_TRACK)), FWD)
    assert d["basis"]["float_refused"] == "diluted" and d["basis"]["growth"]["from_asof"] == "2026-08-12"
    assert "8.6×" in d["title"]
    e = _blk(_rec_C(float_shares=700000, float_asof="2026-12-09", shares_asof="2026-12-09"),
             _doc(track=dict(SMTK_TRACK), yahoo=None), FWD)
    assert e["basis"]["float_refused"] is None and "12.6% float" in e["chip"] and e["tier"] == "high"


# ═════════════════════════════════════════════ [C1]
def test_C1_held_rows_with_an_error_still_refuse_chip_ends_last_check_failed():
    sp = _ok(since="2026-08-01", rows=[_split("2026-08-21", 50, 1), _split("2026-11-23", 5, 1)],
             error="ReadTimeout", error_at="2026-11-24T19:10:00Z", strikes=1)
    b = _blk(_rec(), _doc(sp=sp))
    assert b["basis"]["float_refused"] == "diluted" and b["chip"].endswith(" · ❔ last check failed")
    assert b["basis"]["status"] == "partial"


def test_C1_splits_never_read_nothing_refused_chip_says_unchecked():
    sp = {"status": "failed", "read_at": None, "error": "HTTPError", "error_at": "2026-11-24T19:10:00Z", "strikes": 1}
    b = _blk(_rec(), _doc(sp=sp))
    assert b["pct_of_float"] == 79.05 and b["tier"] == "extreme"
    # 2026-11-26 sitrack A4: the provider's 1.0 with no ADV on the record is FINRA's floor → '≤1d'
    assert b["chip"] == "🩳 SI EXTREME 79.0% float · ≤1d · 10/30 · 📄 S-4 11/13 · ❔ share count unchecked"


def test_C1_sec_failed_no_covers_keeps_the_pct_and_the_title_says_not_checked():
    sec = {"status": "failed", "read_at": None, "error": "ConnectTimeout", "error_at": "2026-11-24T19:10:00Z",
           "strikes": 1}
    b = _blk(_rec(), _doc(sec=sec, yahoo=None))
    plain = SR.si_block(_rec(), TODAY)
    assert b["pct_of_float"] == plain["pct_of_float"] and b["tier"] == plain["tier"]
    assert b["chip"] == plain["chip"] + " · ✂️ split 11/23 · ❔ share count unchecked"
    assert "share count not checked — the SEC did not answer (last try 11/24 14:10 ET)" in b["title"]


def test_C1_a_seed_only_doc_adds_no_flag():
    b = _blk(_rec(), {"_id": "SMTK", "float_track": dict(SMTK_TRACK, origin="seed")})
    plain = SR.si_block(_rec(), TODAY)
    assert b["chip"] == plain["chip"] and b["basis"]["flags"] == [] and b["extreme"] == plain["extreme"]


# ═════════════════════════════════════════════ [C2] the change across a split
def _omex(**over):
    d = dict(short_interest=195353, prev_short_interest=4766804, si_change_pct=-95.9, float_shares=None,
             float_asof=None, shares_outstanding=None, shares_asof=None, days_to_cover=None)
    d.update(over)
    return _rec("OMEX", **d)


def test_C2_OMEX_rebased_change_title_and_rows():
    b = _blk(_omex(), _doc("OMEX", splits=[_split("2026-10-29", 25, 1)], covers=[], filings=[], yahoo=None))
    assert b["si_change_pct"] == 2.5 and b["prev_si_shares"] == 4766804
    words = ("+2.5% vs 2026-10-15, split-adjusted — the 1-for-25 reverse split 10/29 turns the 4,766,804 counted "
             "then into 190,672 of today's shares")
    assert "195,353 shares short (%s)." % words in b["title"]
    assert {r["k"]: r["v"] for r in b["rows"]}["Shares short"] == "195,353 · " + words
    assert b["basis"]["change"]["prev_adj"] == 190672


def test_C2_KNDI_rebased_and_its_pre_split_float_refused():
    rec = _rec("KNDI", short_interest=127620, prev_short_interest=1198836, si_change_pct=-89.4,
               float_shares=67911029, float_asof="2026-09-29", shares_outstanding=100415365, shares_asof="2026-09-29")
    b = _blk(rec, _doc("KNDI", splits=[_split("2026-10-16", 10, 1)], covers=[], filings=[], yahoo=None))
    assert b["si_change_pct"] == 6.5 and b["basis"]["change"]["prev_adj"] == 119884
    assert b["basis"]["float_refused"] == "split" and b["pct_of_float"] is None
    assert b["pct_of_shares_out"] is None and b["chip"].startswith("🩳 SI 127.6K sh")


@pytest.mark.parametrize("e", ["2026-10-30", "2026-10-15"])
def test_C2_a_split_ON_a_settlement_day_gives_no_pct_and_says_why(e):
    b = _blk(_omex(short_interest=1000, prev_short_interest=25000),
             _doc("RUBI", splits=[_split(e, 25, 1)], covers=[], filings=[], yahoo=None))
    assert b["si_change_pct"] is None
    tail = ("the 1-for-25 reverse split executed %s, a settlement day, and which side of it that count is on is not "
            "known" % ("10/30" if e == "2026-10-30" else "10/15"))
    assert "1,000 shares short (no % vs 2026-10-15 — " + tail + ")." in b["title"]
    assert {r["k"]: r["v"] for r in b["rows"]}["Shares short"] == \
        "1,000 · no % vs 2026-10-15 (25,000 then) — " + tail


def test_NEGATIVE_C2_no_split_between_keeps_the_change_phrase_byte_identical():
    plain = SR.si_block(_rec(), TODAY)
    b = _blk(_rec(), _doc())
    head = "432,313 shares short (+334.6% vs 2026-10-15)."
    assert head in plain["title"] and head in b["title"]
    assert {r["k"]: r["v"] for r in b["rows"]}["Shares short"] == {r["k"]: r["v"] for r in plain["rows"]}["Shares short"]


def test_NEGATIVE_C2_splits_never_read_the_raw_pct_stands():
    sp = {"status": "failed", "error": "HTTPError", "error_at": "2026-11-24T19:10:00Z"}
    b = _blk(_omex(), _doc("OMEX", sp=sp, covers=[], filings=[], yahoo=None))
    assert b["si_change_pct"] == -95.9 and b["basis"]["change"] is None


@pytest.mark.parametrize("prev", [0, None])
def test_NEGATIVE_C2_no_prior_count_no_change_key(prev):
    b = _blk(_omex(prev_short_interest=prev), _doc("OMEX", splits=[_split("2026-10-29", 25, 1)], covers=[],
                                                   filings=[], yahoo=None))
    assert b["basis"]["change"] is None and "split-adjusted" not in b["title"]


# ═════════════════════════════════════════════ [C6] EXTREME note
def test_C6_EXTREME_with_an_upcoming_split():
    b = _blk(*_jz("ADRC"))
    assert b["tier"] == "extreme" and set(b["extreme"]) == {"text", "short", "title", "basis"}
    assert b["extreme"]["short"] == "🩳 SI EXTREME 27.2% float · ✂️ split due 12/24"
    assert "✂️ 1-for-15 reverse split due 12/24" in b["extreme"]["title"]
    t = b["extreme"]["title"]
    assert t.index("✂️ 1-for-15") < t.index(SR.EXTREME_STUDY_NOTE)
    assert b["extreme"]["text"] == b["chip"] and b["chip"].endswith(" · ✂️ split due 12/24")
    assert "not compared — an ADR's SEC cover counts ordinary shares" in {r["k"]: r["v"] for r in b["rows"]}[
        "Share-count check"]


def test_NEGATIVE_C6_no_flags_leaves_extreme_byte_identical():
    rec, doc = _jz("ADRC")
    doc["splits"]["rows"] = []
    b, plain = _blk(rec, doc), SR.si_block(rec, TODAY)
    assert b["extreme"] == plain["extreme"] and b["chip"] == plain["chip"]


def test_P1_the_JZ_doc_typed_CS_is_refused():
    b = _blk(*_jz("CS"))
    assert b["basis"]["float_refused"] == "diluted" and b["tier"] is None and b["extreme"] is None


# ═════════════════════════════════════════════ named names
def test_CLRO_EXTREME_unchanged_gains_only_the_filing_flag():
    rec, doc = _clro()
    b, plain = _blk(rec, doc), SR.si_block(rec, TODAY)
    assert b["tier"] == plain["tier"] == "extreme" and b["pct_of_float"] == plain["pct_of_float"] == 44.05
    assert b["chip"] == plain["chip"] + " · 📄 S-1/A 11/24 +1"
    assert b["chip"].startswith("🩳 SI EXTREME 44.0% float")
    assert b["extreme"]["short"] == plain["extreme"]["short"] + " · 📄 S-1/A 11/24 +1"
    assert b["extreme"]["basis"] == plain["extreme"]["basis"] and set(b["extreme"]) == set(plain["extreme"])


def test_JELD_x1_0001_nothing_refused_no_chip_flag():
    from tests.test_si_basis_math_2026_11_24 import _jeld
    rec, doc = _jeld()
    b, plain = _blk(rec, doc), SR.si_block(rec, TODAY)
    # 2026-11-24 later: the newer Yahoo float (11-23) reads 10.03% vs 10.00% — the same printed 10.0%; the only mark is
    # ⚠️ float updated
    assert b["chip"] == plain["chip"] + " · ⚠️ float updated" and b["basis"]["float_refused"] is None
    assert [f["key"] for f in b["basis"]["flags"]] == ["float_updated"]
    assert (plain["pct_of_float"], b["pct_of_float"]) == (10.0, 10.03)


def test_WETO_shares_up_14x_on_the_newer_count():
    rec = _rec("WETO", short_interest=241900, float_shares=186729, float_asof="2026-11-02",
               shares_outstanding=1077801, shares_asof="2026-11-02")
    doc = _doc("WETO", splits=[], filings=[], covers=[
        {"as_of": "2026-06-30", "shares": 821300, "form": "20-F", "filed": "2026-11-05"}],
        yahoo={"float_shares": 14735015, "shares_outstanding": 14897999, "as_of": "2026-11-20"})
    b = _blk(rec, doc)
    # 2026-11-24 later: Yahoo's newer float (11-20) is the one divided by; the shares-up mark (growth since the
    # replaced float's date) stays
    # 2026-11-26 sitrack A4: the provider's 1.0 with no ADV on the record is FINRA's floor → '≤1d'
    assert b["chip"] == "🩳 SI Low 1.6% float · ≤1d · 10/30 · ⚠️ float updated · ⚠️ shares up 14×"
    assert b["float_source"] == SR.YAHOO_LIVE_FLOAT_SOURCE and b["float_asof"] == "2026-11-20"
    assert b["float_suspect"] is None and b["headline_basis"] == "float"
    assert b["shares_source"] == SR.YAHOO_LIVE_SHARES_SOURCE and b["shares_asof"] == "2026-11-20"


def test_NXAT_shares_fell_flag_head_unchanged():
    rec = _rec("NXAT", short_interest=21473, float_shares=1353790, float_asof="2026-09-10",
               shares_outstanding=68476338, shares_asof="2026-09-10")
    doc = _doc("NXAT", splits=[], filings=[], covers=[],
               yahoo={"float_shares": 1353790, "shares_outstanding": 3236567, "as_of": "2026-11-20"})
    b, plain = _blk(rec, doc), SR.si_block(rec, TODAY)
    assert b["chip"] == plain["chip"] + " · ❔ shares fell 21×" and "1.6% float" in b["chip"]
    assert b["basis"]["status"] == "partial" and b["pct_of_float"] == plain["pct_of_float"]


def test_carried_SMX_split_refused_then_6pct_float_next_settlement():
    b = _blk(_smx_rec(), _smx_doc())
    assert b["basis"]["float_refused"] == "split" and "float_stale" not in [f["key"] for f in b["basis"]["flags"]]
    assert b["pct_of_shares_out"] is None and b["chip"].startswith("🩳 SI 47.7K sh")
    n = _blk(_smx_rec(settlement_date="2026-11-13", short_interest=16965), _smx_doc())
    assert "6.0% float" in n["chip"] and n["basis"]["float_refused"] is None


# ═════════════════════════════════════════════ [C11] a raising verdict, junk leaves
def test_C11_a_raising_verdict_serves_the_block_as_today_plus_failed(monkeypatch):
    def boom(*a, **k):
        raise ZeroDivisionError("x")
    monkeypatch.setattr(BM, "verdict", boom)
    plain = SR.si_block(_rec(), TODAY)
    b = _blk(_rec(), _doc())
    assert b["basis"]["status"] == "failed" and b["basis"]["flags"][0]["short"] == "❔ share count unchecked"
    assert b["chip"] == plain["chip"] + " · ❔ share count unchecked"
    assert "❔ share count check failed — the % shown uses the counts on the short-interest record." in b["title"]
    for k in SR._BLOCK_KEYS:
        if k not in ("chip", "title", "rows", "extreme"):
            assert b[k] == plain[k], k
    assert b["extreme"]["short"].endswith("❔ share count unchecked")


def test_C11_a_verdict_raising_after_a_partial_apply_restores_the_numbers(monkeypatch):
    def half(b, v):
        b["pct_of_float"] = None
        b["shares_outstanding"] = 1
        raise KeyError("x")
    monkeypatch.setattr(SR, "_apply_verdict", half)
    plain = SR.si_block(_rec(), TODAY)
    b = _blk(_rec(), _doc())
    assert b["pct_of_float"] == plain["pct_of_float"] and b["shares_outstanding"] == plain["shares_outstanding"]
    assert b["basis"]["status"] == "failed" and b["tier"] == plain["tier"]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -5, True])
def test_C11_bad_basis_leaves_never_reach_the_json(bad):
    b = _blk(_rec(), _poison(_doc(track=dict(SMTK_TRACK)), bad))
    json.dumps(b, allow_nan=False)
    assert b["pct_of_float"] == 79.05


# ═════════════════════════════════════════════ the map join
def test_si_map_joins_the_basis_through_the_seam(monkeypatch):
    seen = []

    def fake(syms, db=None):
        seen.append(list(syms))
        return {"SMTK": _doc()}
    monkeypatch.setattr(SR, "_basis_docs", fake)
    db = FakeDB({SIC.SI_COLL: FakeColl([_rec(), _rec("EOSE")], name=SIC.SI_COLL)})
    m = SR.si_map(["SMTK", "EOSE", "NOPE"], db=db, today=TODAY)
    assert seen == [["SMTK", "EOSE"]]
    assert m["SMTK"]["chip"] == SMTK_CHIP and "basis" not in m["EOSE"]
    assert len(db.colls[SIC.SI_COLL].finds) == 1


def test_si_map_reads_the_real_share_basis_collection():
    doc = _doc()
    db = FakeDB({SIC.SI_COLL: FakeColl([_rec()], name=SIC.SI_COLL),
                 SB.SB_COLL: FakeColl([doc], name=SB.SB_COLL)})
    m = SR.si_map(["SMTK"], db=db, today=TODAY)
    assert m["SMTK"]["chip"] == SMTK_CHIP
    assert len(db.colls[SB.SB_COLL].finds) == 1


def test_NEGATIVE_si_map_with_a_raising_basis_load_serves_the_plain_blocks(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("mongo down")
    monkeypatch.setattr(SB, "load", boom)
    db = FakeDB({SIC.SI_COLL: FakeColl([_rec()], name=SIC.SI_COLL)})
    assert SR.si_map(["SMTK"], db=db, today=TODAY)["SMTK"] == SR.si_block(_rec(), TODAY)
    assert SR._basis_docs(["SMTK"], db) == {} and SR._basis_docs([], db) == {}


def test_NEGATIVE_si_map_with_no_si_docs_never_reads_the_basis(monkeypatch):
    monkeypatch.setattr(SR, "_basis_docs", lambda *a, **k: pytest.fail("basis read with no SI docs"))
    db = FakeDB({SIC.SI_COLL: FakeColl([], name=SIC.SI_COLL)})
    assert SR.si_map(["SMTK"], db=db, today=TODAY) == {}


# ═════════════════════════════════════════════ ℹ️ rules — folded, still 8 picks
def test_rules_pick_1_carries_the_basis_sentence_and_the_cap_holds():
    sec = SR.rules_section()
    assert len(sec["picks"]) == 8 and sec["picks"][1].startswith("% of float = ")
    assert sec["picks"][1].endswith(BM.rules_sentence())
    assert not [p for p in sec["picks"] if FORBIDDEN.search(p)]


def test_NEGATIVE_rules_survives_a_raising_sentence(monkeypatch):
    monkeypatch.setattr(BM, "rules_sentence", lambda: 1 / 0)
    sec = SR.rules_section()
    assert sec["picks"][1].startswith("% of float = ") and len(sec["picks"]) == 8


# ═════════════════════════════════════════════ the route [C5]
def _route(monkeypatch, recs, basis=None, pend=None):
    db = FakeDB({SIC.SI_COLL: FakeColl(recs, name=SIC.SI_COLL)})
    monkeypatch.setattr(SIC, "_get_db", lambda: db)
    monkeypatch.setattr(SR, "_basis_docs", lambda syms, db=None: dict(basis or {}))
    kicked = []

    def kick(syms):
        kicked.append(list(syms))
        return list(pend or [])
    monkeypatch.setattr(SAPI, "_kick_basis", kick)
    return kicked


def test_route_overlays_pending_and_keeps_three_keys(monkeypatch):
    seed = {"_id": "SMTK", "float_track": dict(SMTK_TRACK, origin="seed")}
    kicked = _route(monkeypatch, [_rec(), _rec("EOSE"), _rec("GONE", short_interest=None)],
                    basis={"SMTK": seed}, pend=["SMTK", "EOSE"])
    out = _run(SAPI.short_interest_read_map(symbols="smtk,EOSE,GONE"))
    assert set(out) == {"items", "n", "max_symbols"} and out["n"] == 3
    assert kicked == [["SMTK", "EOSE"]]                         # the no_record item is never kicked
    s, e = out["items"]["SMTK"]["basis"], out["items"]["EOSE"]["basis"]
    assert s["pending"] is True and s["retry_after_sec"] == SB.SB_RETRY_AFTER_SEC
    assert s["status"] == "partial" and s["flags"] == [] and "float_refused" in s      # its own basis kept
    assert e == {"status": "pending", "pending": True, "retry_after_sec": SB.SB_RETRY_AFTER_SEC}
    assert "basis" not in out["items"]["GONE"]
    json.dumps(out, allow_nan=False)


def test_NEGATIVE_route_with_nothing_pending_is_unchanged(monkeypatch):
    _route(monkeypatch, [_rec("EOSE")], pend=[])
    out = _run(SAPI.short_interest_read_map(symbols="EOSE"))
    assert "basis" not in out["items"]["EOSE"]


def test_NEGATIVE_route_no_kick_on_an_empty_list(monkeypatch):
    kicked = _route(monkeypatch, [_rec("GONE", short_interest=None)], pend=["GONE"])
    out = _run(SAPI.short_interest_read_map(symbols="GONE,NOPE"))
    assert kicked == [] and "basis" not in out["items"]["GONE"]
    kicked = _route(monkeypatch, [], pend=["X"])
    _run(SAPI.short_interest_read_map(symbols=""))
    assert kicked == []


def test_NEGATIVE_kick_basis_never_raises(monkeypatch):
    monkeypatch.setattr(SB, "kick", lambda *a, **k: 1 / 0)
    assert SAPI._kick_basis(["SMTK"]) == []
    monkeypatch.setattr(SB, "kick", lambda *a, **k: "junk")
    assert SAPI._kick_basis(["SMTK"]) == []
    monkeypatch.setattr(SB, "kick", lambda *a, **k: {"queued": [], "pending": ["smtk", 5, None, ""]})
    assert SAPI._kick_basis(["SMTK"]) == ["SMTK"]
    assert SAPI._kick_basis([]) == []


def test_kick_basis_under_pytest_queues_nothing():
    assert SAPI._kick_basis(["SMTK", "EOSE"]) == []
    assert SAPI._retry_after_sec() == SB.SB_RETRY_AFTER_SEC


def test_route_source_reads_the_constants_by_name():
    import inspect
    src = inspect.getsource(SAPI)
    assert "SB.SB_RETRY_AFTER_SEC" in src and "SB.kick(" in src
    assert '("ok", "stale")' in inspect.getsource(SAPI.short_interest_read_map)
    assert not re.search(r"retry_after_sec\"?:\s*\d", src)
