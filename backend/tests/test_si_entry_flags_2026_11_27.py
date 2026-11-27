"""🩳 ON-ENTRY SOURCE CHECK — the pure flags and fixes (2026-11-27, spec sicheck rev 2 §3.4, work package `si-pure`).

Ajay 2026-11-27, verbatim: "Can you double check short interest for these two please?" · "Anytime something is in our
Gajjalas we need to initiate a flow checking these values" · "WHLR is too much".

What is pinned here (display only — no gate, sort, count, push trigger or lane reads any of it; UNMEASURED):
  A1 `⚠️ sources disagree` both ways at any tier = the spread above `SCK.min_rel()` AND the two % on different rungs of
     THE ladder (`SR.tier_of`) AND the second float passes THE house float check (`SR._float_suspect`), behind
     `SCK.RUNG_FLAG`; only in step 10's not-contested branch (step 10 and `SCK.STATES` are not touched). A second float
     that fails the check is named "not usable" and never flags. The rung sentence prints `SR._range` ranges.
  A2 `✂️ split filing M/D` from the K-1 `sec.fts_split` read — words only.
  A3 the `Dates` line, `⚠️ dates apart` only at the existing `stale_trigger` cut.
  B1 the days-to-cover split sentence only for `prevS < exec <= S`.
  B4 a lagged older count: the NEW count must sit inside the split-adjusted cover band too.
  B5 a split filing between the two float dates: always compared + a caveat; only the A1 flag is held back on a rebase.
  The entry line (`si_block(.., entry=)`, `si_map` through the lazy `_entry_words` seam).

INPUTS ARE REAL: tests/fixtures/si_entry_docs_2026_11_27.json — ONE read-only probe of the api container (WHLR, BDMD,
POM, NXAT, WETO: the short_interest_latest doc, the si_share_basis doc and the block main served), plus, clearly labelled,
hand-added frozen-shape copies carrying ONLY the K-1 `sec.fts_split` sub-doc (rows = spec §1.6). The frozen probe rows
(tests/fixtures/si_float_probe_rows_2026_11_26.json, 693 rows) give the pinned count. Synthetic shapes change one leaf
of a real doc each, by computation from it (never a typed share count).

The frontend fixture (frontend/src/components/__fixtures__/si_entry_check_2026_11_27.json) is GENERATED here:
    cd backend && .venv/bin/python -m tests.test_si_entry_flags_2026_11_27 --regen
"""
from __future__ import annotations

import copy
import json
import sys
import types
from datetime import date
from pathlib import Path

import pytest

from short_interest import basis_math as BM
from short_interest import client as SIC
from short_interest import read as SR
from short_interest import source_check as SCK
from tests.test_short_interest_read_2026_10_03 import FORBIDDEN, FakeColl, FakeDB

BACKEND = Path(__file__).resolve().parents[1]
FIX = json.loads((BACKEND / "tests" / "fixtures" / "si_entry_docs_2026_11_27.json").read_text(encoding="utf-8"))
PROBE = json.loads((BACKEND / "tests" / "fixtures" / "si_float_probe_rows_2026_11_26.json").read_text(encoding="utf-8"))
FE_FIX = BACKEND.parent / "frontend" / "src" / "components" / "__fixtures__" / "si_entry_check_2026_11_27.json"
DOC = BACKEND.parent / "docs" / "short_interest" / "entry_check_flags_2026_11_27.md"
TODAY = date(2026, 11, 27)
NAMES = ("BDMD", "NXAT", "POM", "WETO", "WHLR")
SPLIT_NAMES = ("BDMD", "NXAT", "POM")


# ═════════════════════════════════════════════ builders
def rec(sym, **over):
    r = copy.deepcopy(FIX["names"][sym]["si_record"])
    r.update(over)
    return r


def doc(sym, split=False):
    """The captured basis doc; `split=True` = the hand-added frozen-shape copy with `sec.fts_split` (K-1)."""
    src = FIX["with_fts_split"]["names"] if split else FIX["names"]
    return copy.deepcopy(src[sym] if split else src[sym]["basis_doc"])


def main_block(sym):
    return FIX["names"][sym]["block_main"]


def blk(sym, d="plain", r=None, **kw):
    dd = doc(sym) if d == "plain" else (doc(sym, split=True) if d == "split" else d)
    b = SR.si_block(r if r is not None else rec(sym), TODAY, basis=dd, **kw)
    json.dumps(b, allow_nan=False)
    return b


def sc(b):
    return b["basis"]["sources_compared"]


def keys(b):
    return [f.get("key") for f in (b.get("basis") or {}).get("flags") or []]


def row(b, k):
    got = [r["v"] for r in b["rows"] if r["k"] == k]
    return got[0] if got else None


def rows(b, k):
    return [r["v"] for r in b["rows"] if r["k"] == k]


def flag(b, key):
    return next((f for f in b["basis"]["flags"] if f["key"] == key), None)


def strings(b) -> list:
    out = [b.get("chip") or "", b.get("title") or ""] + [r["k"] + " " + r["v"] for r in b.get("rows") or []]
    e = b.get("extreme") or {}
    out += [e.get(k) or "" for k in ("text", "short", "title")]
    return out


@pytest.fixture
def setmode(monkeypatch):
    def _set(name, value, mod=SCK):
        monkeypatch.setattr(mod, name, value)
    return _set


# ═════════════════════════════════════════════ the fixture is the real capture
def test_fixture_is_the_real_capture_and_the_copies_add_only_fts_split():
    assert "REAL" in FIX["about"] and FIX["serve_day"] == TODAY.isoformat()
    assert sorted(FIX["names"]) == list(NAMES)
    assert FIX["with_fts_split"]["about"].startswith("HAND-ADDED FROZEN-SHAPE COPIES")
    assert sorted(FIX["with_fts_split"]["names"]) == list(SPLIT_NAMES)
    for s in NAMES:
        n = FIX["names"][s]
        assert set(n) == {"si_record", "basis_doc", "block_main"}
        assert n["si_record"]["symbol"] == s and n["basis_doc"]["_id"] == s
        assert BM.KEY_FTS_SPLIT not in n["basis_doc"]["sec"]
    for s in SPLIT_NAMES:
        c = doc(s, split=True)
        fs = c["sec"].pop(BM.KEY_FTS_SPLIT)
        assert c == doc(s)                                       # nothing else differs
        assert set(fs) == {"status", "since", "top_6k", "top_6k_filed", "rows", "read_at", "error", "error_at",
                           "strikes"} and fs["status"] == "ok"
        assert all(set(r) == {"form", "filed", "accn", "doc", "ex"} for r in fs["rows"])
    # the probe's served chips are the §1.4 table, as main served them at capture
    assert main_block("BDMD")["chip"] == "🩳 SI High 30.1% float · float unconfirmed · <0.1d · 11/13"
    assert main_block("WHLR")["chip"] == ("🩳 SI EXTREME 26.4% float · <0.1d · 11/13 · ⚠️ float updated · ✂️ split due "
                                          "11/30 · 📄 8-K 3.02 11/20 +4")
    assert main_block("NXAT")["chip"].endswith("· ❔ shares fell 21×")
    assert main_block("WETO")["chip"] == blk("WETO")["chip"]


# ═════════════════════════════════════════════ A1 — both ways, any tier [C2][C3]
def test_A1_BDMD_is_flagged_and_the_rung_sentence_prints_two_ranges():
    for d in ("plain", "split"):
        b = blk("BDMD", d)
        assert b["chip"].endswith(" · " + SCK.SHORT_SOURCES), d
        assert sc(b)["rung"] is True and "second" not in sc(b) and sc(b)["state"] == "compared"
        assert b["basis"]["extreme_contest"] is None and b["tier"] == SR.TIER_HIGH
        rung = SCK.TEXT_RUNG % ("Yahoo", SR._range(SR.TIER_EXTREME), "Massive", SR._range(SR.TIER_HIGH))
        assert rung == " Yahoo's float puts it at 20% or more of the float, Massive's at 10% to under 20%."
        t = sc(b)["text"]
        assert rung in t and t.startswith(SCK.SHORT_SOURCES + " — float: ") and t.endswith(SCK.TAIL_BOTH % ())
        assert "EXTREME" not in rung and "High" not in rung                     # ranges, never a tier word
        assert keys(b)[-1] == SCK.FLAG_SOURCES and flag(b, SCK.FLAG_SOURCES)["text"] == t
        assert row(b, SCK.ROW_FLOAT_SOURCES) == t
        assert SCK.title_sentences(b) == []                                    # the flag text rides the title


def _pre(sym, d):
    """The block si_block hands to compare: the same doc with no `mfloat` (tier built, no source keys yet)."""
    d0 = copy.deepcopy(d)
    d0.pop("mfloat", None)
    return SR.si_block(rec(sym), TODAY, basis=d0)


def test_A1_compare_answers_rung_flag_and_apply_appends_the_flag_last():
    pre = _pre("BDMD", doc("BDMD"))
    assert pre["chip"] == main_block("BDMD")["chip"]
    cmp = SCK.compare(pre, doc("BDMD"))
    assert cmp["rung_flag"] is True and cmp["contest"] is None and cmp["state"] == "compared"
    assert cmp["rung"] is True and cmp["text"] == cmp["row"] and "second" not in cmp
    SCK.apply(pre, cmp)
    assert keys(pre)[-1] == SCK.FLAG_SOURCES and pre["tier"] == SR.TIER_HIGH
    for sym in ("WHLR", "NXAT", "WETO"):
        c = SCK.compare(_pre(sym, doc(sym)), doc(sym))
        assert c["rung_flag"] is False and c["text"] is None, sym
    assert SCK.compare({}, {"mfloat": {"status": "none"}})["rung_flag"] is False
    nope = dict(cmp, rung_flag="yes")                                          # only a real True appends
    b = _pre("BDMD", doc("BDMD"))
    SCK.apply(b, nope)
    assert SCK.FLAG_SOURCES not in keys(b)


def test_NEGATIVE_A1_WHLR_second_float_smaller_than_the_short_is_not_usable_never_flagged():
    b = blk("WHLR")
    assert SCK.FLAG_SOURCES not in keys(b) and SCK.SHORT_SOURCES not in b["chip"]
    assert sc(b)["second"] == SR.SHORT_EXCEEDS_FLOAT and "rung" not in sc(b)
    t = sc(b)["text"]
    assert "= 1100.5% — smaller than the 439,892 shares sold short · 42× apart" in t
    assert t.endswith(SCK.TEXT_NOT_USABLE) and "float puts it at" not in t
    assert b["chip"] == main_block("WHLR")["chip"]                         # the chip tail is UNCHANGED


def _bdmd_second(shares):
    d = doc("BDMD")
    d["mfloat"] = dict(d["mfloat"], shares=shares)
    return d


def test_NEGATIVE_A1_second_float_above_shares_out_on_another_rung_is_not_usable():
    so = rec("BDMD")["shares_outstanding"]
    b = blk("BDMD", _bdmd_second(so * 2))
    assert SR.tier_of(sc(b) and b["basis"]["float_sources"][1]["pct"]) != SR.tier_of(b["pct_of_float"])
    assert sc(b)["second"] == SR.FLOAT_EXCEEDS_SHARES and "rung" not in sc(b)
    assert SCK.FLAG_SOURCES not in keys(b)
    t = sc(b)["text"]
    assert (SCK.TEXT_LARGER % format(so, ",")) in t and t.endswith(SCK.TEXT_NOT_USABLE)


def test_NEGATIVE_A1_same_rung_with_a_usable_second_float_has_none_of_the_new_keys():
    b = blk("NXAT")                                                          # 3.4% / 2.5%, both Low
    assert SR.tier_of(b["pct_of_float"]) == SR.tier_of(b["basis"]["float_sources"][1]["pct"]) == SR.TIER_LOW
    assert set(sc(b)) == {"state", "rel", "text"} and SCK.FLAG_SOURCES not in keys(b)
    # a synthetic 1.32% / 1.32% pair 0.24% apart (WETO's record and doc, the short count and the second float computed)
    r = rec("WETO")
    r["short_interest"] = int(round(r["float_shares"] * 0.0132))
    d = doc("WETO")
    d["mfloat"] = dict(d["mfloat"], shares=int(round(r["float_shares"] * 1.0024)))
    b2 = SR.si_block(r, TODAY, basis=d)
    assert b2["pct_of_float"] == 1.32 and b2["basis"]["float_sources"][1]["pct"] == 1.32
    assert 0.002 < sc(b2)["rel"] < 0.003 and set(sc(b2)) == {"state", "rel", "text"}
    assert SCK.FLAG_SOURCES not in keys(b2)


def test_NEGATIVE_A1_a_spread_at_or_under_min_rel_never_flags(setmode):
    b = blk("BDMD", _bdmd_second(rec("BDMD")["float_shares"]))              # the same count
    assert sc(b)["rel"] == 0 and set(sc(b)) == {"state", "rel", "text"} and SCK.FLAG_SOURCES not in keys(b)
    setmode("CONTEST_MIN_REL", 2.0)                                          # BDMD's 2.4× = rel 1.37 ≤ 2.0
    b = blk("BDMD")
    assert sc(b)["rel"] < SCK.min_rel() and SCK.FLAG_SOURCES not in keys(b) and "rung" not in sc(b)


@pytest.mark.parametrize("word", ["off", "junk", "", None, "ON"])
def test_NEGATIVE_A1_RUNG_FLAG_off_or_junk_no_chip_flag_the_sentence_still_prints(setmode, word):
    setmode("RUNG_FLAG", word)
    assert SCK.rung_on() is False
    b = blk("BDMD")
    assert SCK.FLAG_SOURCES not in keys(b) and SCK.SHORT_SOURCES not in b["chip"]
    assert sc(b)["rung"] is True and " Yahoo's float puts it at 20% or more of the float" in sc(b)["text"]
    assert not sc(b)["text"].startswith(SCK.SHORT_SOURCES)
    assert SCK.title_sentences(b) == [SCK.HOVER_HEAD + sc(b)["text"]]


def test_NEGATIVE_A1_EXTREME_CONTEST_off_no_chip_flag(setmode):
    setmode("EXTREME_CONTEST", "off")
    b = blk("BDMD")
    assert SCK.FLAG_SOURCES not in keys(b) and sc(b)["rung"] is True


def test_NEGATIVE_A1_not_older_with_an_older_second_float_is_not_flagged(setmode):
    setmode("EXTREME_CONTEST_BY", "not_older")
    b = blk("BDMD")                                       # Massive 11/10 is older than Yahoo's 11/20
    assert SCK.FLAG_SOURCES not in keys(b) and sc(b)["rung"] is True
    d = doc("BDMD")
    d["mfloat"] = dict(d["mfloat"], as_of=rec("BDMD")["float_asof"])         # same date → not older → flags
    assert SCK.FLAG_SOURCES in keys(blk("BDMD", d))


def test_NEGATIVE_A1_cuts_out_of_order_no_flag(monkeypatch):
    monkeypatch.setattr(SIC, "SI_MODERATE_PCT", SIC.SI_HIGH_PCT + 1)
    assert SR._ladder_ok() is False
    for s in NAMES:
        b = blk(s, "split" if s in SPLIT_NAMES else "plain")
        assert SCK.FLAG_SOURCES not in keys(b) and "rung" not in sc(b), s


def test_NEGATIVE_A1_tier_contest_pct_and_basis_are_as_main_served_on_every_name(setmode):
    for s in NAMES:
        m = main_block(s)
        for d in (("plain", "split") if s in SPLIT_NAMES else ("plain",)):
            for word in ("on", "off"):
                setmode("RUNG_FLAG", word)
                b = blk(s, d)
                for k in ("tier", "float_check", "pct_of_float", "headline_basis", "pct_of_shares_out",
                          "float_shares", "shares_outstanding"):
                    assert b[k] == m[k], (s, d, word, k)
                assert b["basis"]["extreme_contest"] == m["basis"]["extreme_contest"] is None, (s, d, word)


def _incidents():
    from tests import test_si_float_incidents_2026_11_26 as T
    return T


def test_step_10_is_untouched_the_contested_rows_are_todays():
    T = _incidents()
    for cid in T.CONTESTED:
        b = T.serve(T.CASES[cid])
        g = T.GOLD[cid]
        assert b["basis"]["extreme_contest"] == g["basis"]["extreme_contest"] is not None, cid
        assert b["basis"]["sources_compared"] == g["basis"]["sources_compared"], cid
        assert b["chip"] == g["chip"] and keys(b) == [f["key"] for f in g["basis"]["flags"]], cid
        t = b["basis"]["sources_compared"]["text"]
        assert SCK.TEXT_NOT_USABLE not in t and "float puts it at" not in t, cid
    # the CHWY shape sets `contest`
    assert T.serve(T.CASES["8_CHWY_11_26"])["basis"]["extreme_contest"]["from"] == SR.TIER_EXTREME


def test_NEGATIVE_a_contested_second_float_above_shares_out_keeps_todays_text():
    T = _incidents()
    hit = 0
    for cid in T.CONTESTED:
        b = T.serve(T.CASES[cid])
        so = b.get("shares_outstanding")
        t = b["basis"]["sources_compared"]["text"]
        if so and (SCK.TEXT_LARGER % format(so, ",")) in t:
            hit += 1
            assert SCK.TEXT_NOT_USABLE not in t and "second" not in b["basis"]["sources_compared"], cid
    assert hit >= 1


def _state_doc(kind):
    d = doc("BDMD")
    if kind == "units":
        d["ref"] = dict(d["ref"], type="ADRC")
    elif kind == "no_splits":
        d["splits"] = dict(d["splits"], status="failed")
    elif kind == "window":
        d["splits"] = dict(d["splits"], since=BM.day_after(d["mfloat"]["as_of"]))
    elif kind == "split_day":
        d["splits"] = dict(d["splits"], rows=[{"execution_date": d["mfloat"]["as_of"], "split_from": 2, "split_to": 1}])
    return d


@pytest.mark.parametrize("kind", ["units", "no_splits", "window", "split_day"])
def test_NEGATIVE_not_compared_states_never_flag(kind):
    b = blk("BDMD", _state_doc(kind))
    assert sc(b)["state"] == kind and SCK.FLAG_SOURCES not in keys(b) and set(sc(b)) == {"state", "rel", "text"}
    cmp = SCK.compare(b, _state_doc(kind))
    assert cmp["rung_flag"] is False


def test_STATES_and_the_cut_table_are_unchanged():
    assert SCK.STATES == ("no_float", "unread", "none", "units", "no_splits", "window", "split_day", "compared",
                          "contested")
    t = SCK.cut_table([{"symbol": r["s"], "state": "window" if r["md"] < r["since"] else "compared", "tier": r["t"],
                        "other": {"tier": r["tm"]}, "float_rel": r["rel"]} for r in PROBE["rows"]])
    assert [c["differ"] for c in t["cuts"]] == [564, 148, 58, 24]
    assert [c["contested"] for c in t["cuts"]] == [11, 8, 4, 2]


# ═════════════════════════════════════════════ the count the REAL engines give on the frozen probe rows
def _probe_block(r):
    so = int(round(r["si"] / r["ps"] * 100)) if r.get("ps") else None     # shares out from the rounded % (the probe)
    b = {"symbol": r["s"], "status": "ok", "headline_basis": "float", "float_shares": r["F"], "float_asof": r["Fa"],
         "pct_of_float": r["pf"], "si_shares": r["si"], "shares_outstanding": so, "pct_of_shares_out": r.get("ps"),
         "tier": r["t"], "float_check": r.get("fc")}
    d = {"mfloat": {"status": "ok", "shares": r["mr"], "as_of": r["md"]}, "ref": {"type": r["type"]},
         "splits": {"status": r["splits_status"], "since": r["since"], "rows": []}}
    return b, d, so


def probe_counts() -> dict:
    """compare() over the 693 frozen rows (the second float as the probe rebased it; the splits read as the probe saw
    it). `rule` = the A1 legs through THE engine helpers on every compared row, contested ones included."""
    out = {"compared": 0, "contested": 0, "rung_flag": 0, "rule": 0, "fails": 0, "rule_rows": []}
    for r in PROBE["rows"]:
        b, d, so = _probe_block(r)
        c = SCK.compare(b, d)
        if c["state"] not in ("compared", "contested"):
            continue
        out["compared"] += 1
        out["contested"] += c["state"] == "contested"
        out["rung_flag"] += c["rung_flag"] is True
        pm = c["sources"][1]["pct"]
        differs = c["rel"] > SCK.min_rel()
        sus = SR._float_suspect(r["si"], r["mr"], so)
        out["fails"] += bool(differs and sus)
        tu, to = SR.tier_of(r["pf"]), SR.tier_of(pm)
        if differs and tu and to and tu != to and sus is None:
            out["rule"] += 1
            out["rule_rows"].append(r)
    B = out.pop("rule_rows")
    out["within"] = [len([r for r in B if r["rel"] <= c]) for c in (0.10, 0.05, 0.02)]
    out["older"] = len([r for r in B if r["md"] < r["Fa"]])
    out["cuts"] = [len([r for r in B if r["rel"] > c]) for c in SCK.EXAMPLE_CUTS]
    out["chip"] = out["rung_flag"] + out["contested"]
    return out


PINNED = {"compared": 569, "contested": 11, "rung_flag": 43, "rule": 52, "fails": 22, "within": [13, 8, 2],
          "older": 27, "cuts": [39, 29, 16], "chip": 54}


def test_the_engines_count_on_the_frozen_probe_rows_is_pinned():
    assert probe_counts() == PINNED


def test_the_doc_prints_the_pinned_count():
    t = DOC.read_text(encoding="utf-8")
    for s in ("52 of 569", "43", "54", "13 / 8 / 2", "27", "39 / 29 / 16", "RUNG_FLAG", "min_rel()", "tier_of",
              "_float_suspect", "UNMEASURED"):
        assert s in t, s


def test_NEGATIVE_the_probe_count_follows_the_switch(setmode):
    setmode("RUNG_FLAG", "off")
    got = probe_counts()
    assert got["rung_flag"] == 0 and got["rule"] == PINNED["rule"] and got["contested"] == 11


# ═════════════════════════════════════════════ A2 — ✂️ split filing [C1]
def test_A2_BDMD_unlisted_filing_on_or_after_the_floor_flags_with_the_match_words():
    b = blk("BDMD", "split")
    assert b["chip"] == ("🩳 SI High 30.1% float · float unconfirmed · <0.1d · 11/13 · ✂️ split filing 11/16 · ⚠️ "
                         "sources disagree")
    f = flag(b, BM.FLAG_SPLIT_FILING)
    assert f["short"] == BM.SHORT_SPLIT_FILING % "11/16" and f["emoji"] == BM.EMOJI_SPLIT
    assert "a proposal, a vote notice and an executed split all match" in f["text"]
    assert f["text"].startswith("✂️ 6-K 11/16 matches split / share-consolidation words")
    assert row(b, "Split filing") == f["text"]
    assert b["basis"]["split_filings"] == [{"form": "6-K", "filed": "2026-11-16", "accn": "0001104659-26-128404",
                                            "on_chip": True}]


def test_A2_NXAT_two_unlisted_filings_and_NEGATIVE_the_two_under_the_8_3_split():
    b = blk("NXAT", "split")
    assert flag(b, BM.FLAG_SPLIT_FILING)["short"] == "✂️ split filing 11/23 +1"
    assert b["chip"] == "🩳 SI Low 3.4% float · 0.2d · 11/13 · ✂️ split filing 11/23 +1 · 📄 6-K 10/5 +1"
    got = {f["filed"] for f in BM.unlisted_split_filings(doc("NXAT", split=True))}
    assert got == {"2026-11-23", "2026-11-13"}                                # 07-10 / 05-27 sit under the 08-03 split
    assert {f["filed"] for f in BM.split_filings(doc("NXAT", split=True))} == got | {"2026-07-10", "2026-05-27"}


def test_NEGATIVE_A2_POM_filed_before_the_floor_no_chip_flag():
    b = blk("POM", "split")
    assert BM.FLAG_SPLIT_FILING not in keys(b) and "split filing" not in b["chip"]
    assert [f["on_chip"] for f in b["basis"]["split_filings"]] == [False, False, False]


@pytest.mark.parametrize("status", ["failed", "off", "blocked", "none_6k", None])
def test_NEGATIVE_A2_no_ok_read_is_byte_identical(status):
    for s in SPLIT_NAMES:
        d = doc(s, split=True)
        d["sec"][BM.KEY_FTS_SPLIT]["status"] = status
        assert blk(s, d) == blk(s), (s, status)
        assert BM.split_filings(d) == []


@pytest.mark.parametrize("junk", [None, "x", 3, [], {"rows": "x", "status": "ok"}, {"status": "ok", "rows": [None, 1,
                                  {"form": "10-K", "filed": "2026-11-20"}, {"form": "6-K", "filed": "nope"}]}])
def test_NEGATIVE_A2_junk_reads_add_nothing(junk):
    d = doc("BDMD")
    d["sec"][BM.KEY_FTS_SPLIT] = junk
    assert blk("BDMD", d) == blk("BDMD") and BM.split_filings(d) == []


def test_NEGATIVE_A2_splits_read_not_ok_lists_none():
    d = doc("BDMD", split=True)
    d["splits"] = dict(d["splits"], status="failed")
    assert BM.unlisted_split_filings(d) == [] and BM.FLAG_SPLIT_FILING not in keys(blk("BDMD", d))


def test_A2_a_6K_in_both_lists_is_listed_once_and_the_dilution_count_is_unchanged():
    b, b0 = blk("BDMD", "split"), blk("BDMD")
    assert rows(b0, BM.ROW_SHARE_ISSUANCE) and not rows(b, BM.ROW_SHARE_ISSUANCE)       # the 11/16 row moved
    assert row(b, "Split filing").endswith(BM.TEXT_SPLIT_FILING_ISSUANCE)
    assert b["basis"]["issuances"] == b0["basis"]["issuances"] and b["basis"]["filings"] == b0["basis"]["filings"]
    # NXAT: a split row carrying the 10/5 issuance 6-K's accession — the 📄 short and count do not move
    d = doc("NXAT", split=True)
    iss = next(i for i in d["sec"]["fts"]["issuance"] if i["filed"] == "2026-10-05")
    d["sec"][BM.KEY_FTS_SPLIT]["rows"].insert(2, {"form": "6-K", "filed": iss["filed"], "accn": iss["accn"],
                                                  "doc": None, "ex": []})
    b1, n0 = blk("NXAT", d), blk("NXAT")
    assert flag(b1, BM.FLAG_FILING) == flag(n0, BM.FLAG_FILING) and b1["basis"]["filings"] == n0["basis"]["filings"]
    assert len(rows(b1, BM.ROW_SHARE_ISSUANCE)) == len(rows(n0, BM.ROW_SHARE_ISSUANCE)) - 1
    assert flag(b1, BM.FLAG_SPLIT_FILING)["short"] == "✂️ split filing 11/23 +2"


# ═════════════════════════════════════════════ A3 — Dates / ⚠️ dates apart
def test_A3_WHLR_prints_the_dates_line_and_no_chip_flag():
    b = blk("WHLR")
    line = ("Dates: short interest counted 11/13; the float is read 11/25; shares outstanding 1,788,532 (SEC 10-Q "
            "cover, 11/3) → 2,220,906 (Yahoo, 11/25) in between.")
    assert line in rows(b, "Note") and line in b["title"]
    assert BM.SHORT_DATE_GAP not in b["chip"] and BM.FLAG_DATE_GAP not in keys(b)
    assert b["basis"]["date_gap"]["flag"] is False
    assert 2220906 - 1788532 <= b["float_shares"]                             # 432,374 added ≤ the float


def _whlr_grown():
    d = doc("WHLR")
    d["yahoo"] = dict(d["yahoo"], shares_outstanding=d["yahoo"]["shares_outstanding"] * 2)
    return d


def test_A3_added_above_the_float_adds_dates_apart():
    b = blk("WHLR", _whlr_grown())
    assert BM.SHORT_DATE_GAP in b["chip"] and b["basis"]["date_gap"]["flag"] is True
    f = flag(b, BM.FLAG_DATE_GAP)
    assert f["text"].startswith(BM.SHORT_DATE_GAP + " — short interest counted 11/13; the float is read 11/25")
    assert f["text"].endswith("in between; " + BM.DATE_GAP_MODE_WORDS[BM.FLOAT_STALE_WHEN])
    assert row(b, "Dates") == f["text"] and not [v for v in rows(b, "Note") if v.startswith("Dates:")]


def test_NEGATIVE_A3_the_cut_is_the_existing_mode(monkeypatch):
    monkeypatch.setattr(BM, "FLOAT_STALE_WHEN", "nonsense")
    b = blk("WHLR", _whlr_grown())
    assert BM.SHORT_DATE_GAP not in b["chip"] and b["basis"]["date_gap"]["flag"] is False


def test_NEGATIVE_A3_float_dated_on_or_before_the_settlement():
    d = doc("WHLR")
    d["yahoo"] = dict(d["yahoo"], as_of=rec("WHLR")["settlement_date"])
    b = blk("WHLR", d)
    assert "date_gap" not in b["basis"] and not [v for v in rows(b, "Note") if v.startswith("Dates:")]


def test_NEGATIVE_A3_a_split_between_the_dates():
    d = doc("WHLR")
    d["splits"] = dict(d["splits"], rows=d["splits"]["rows"] + [{"execution_date": "2026-11-20", "split_from": 1,
                                                                 "split_to": 2}])
    b = blk("WHLR", d)
    assert "date_gap" not in b["basis"] and BM.SHORT_DATE_GAP not in (b["chip"] or "")


def test_NEGATIVE_A3_POM_proof_filed_before_the_settlement_nothing():
    for d in ("plain", "split"):
        b = blk("POM", d)
        assert "date_gap" not in b["basis"] and not [v for v in rows(b, "Note") if v.startswith("Dates:")]
        assert BM.SHORT_DATE_GAP not in b["chip"]


# ⚠️ 2026-11-27 refix — the growth is BETWEEN the count and the float read: the flag and the rules sentence say so in
# their own words, never the float-stale words ("since the float was read").
def test_A3_dates_apart_words_cover_every_mode_and_differ_from_the_stale_words():
    assert set(BM.DATE_GAP_MODE_WORDS) == set(BM.FLOAT_STALE_MODES)
    for m in BM.FLOAT_STALE_MODES:
        w = BM.DATE_GAP_MODE_WORDS[m]
        assert "between the count and the float read" in w and w != BM.FLOAT_STALE_MODE_WORDS[m]
        assert "since the float was read" not in w


def test_A3_dates_apart_text_says_between_never_since():
    f = flag(blk("WHLR", _whlr_grown()), BM.FLAG_DATE_GAP)
    assert f["text"].endswith("in between; more shares added between the count and the float read than the float "
                              "holds")
    assert "since the float was read" not in f["text"]
    assert BM.FLOAT_STALE_MODE_WORDS[BM.FLOAT_STALE_WHEN] not in f["text"]


@pytest.mark.parametrize("mode", ["any_increase", "added_exceeds_float", "tier_moves"])
def test_A3_rules_sentence_uses_the_date_gap_words_per_mode(monkeypatch, mode):
    monkeypatch.setattr(BM, "FLOAT_STALE_WHEN", mode)
    s = BM._rules_2026_11_27()
    assert ("'%s' only when %s." % (BM.SHORT_DATE_GAP, BM.DATE_GAP_MODE_WORDS[mode])) in s
    assert BM.FLOAT_STALE_MODE_WORDS[mode] not in s and "since the float was read" not in s
    assert not FORBIDDEN.search(s)


def test_NEGATIVE_A3_rules_sentence_unknown_mode_says_never(monkeypatch):
    monkeypatch.setattr(BM, "FLOAT_STALE_WHEN", "nonsense")
    s = BM._rules_2026_11_27()
    assert "'%s' only never (the cut is switched off)" % BM.SHORT_DATE_GAP in s
    assert not any(w in s for w in BM.DATE_GAP_MODE_WORDS.values())


def test_NEGATIVE_A3_stale_rules_words_unchanged():
    s = BM.rules_sentence()
    assert ("stale (%s)" % BM.FLOAT_STALE_MODE_WORDS[BM.FLOAT_STALE_WHEN]) in s
    assert BM.FLOAT_STALE_MODE_WORDS["added_exceeds_float"] == ("more shares added since the float was read than the "
                                                                "float itself held")


# ═════════════════════════════════════════════ B1 — the days-to-cover split sentence
def _whlr_split_on(day):
    d = doc("WHLR")
    d["splits"] = dict(d["splits"], rows=[dict(r, execution_date=day) if r["execution_date"] == "2026-10-30" else r
                                          for r in d["splits"]["rows"]])
    return d


@pytest.mark.parametrize("day,note", [("2026-10-30", False), ("2026-11-13", True), ("2026-11-02", True)])
def test_B1_the_sentence_only_strictly_after_the_prior_settlement(day, note):
    d = _whlr_split_on(day)
    b = blk("WHLR", d)
    assert isinstance(b["basis"]["change"], dict)
    assert (SR.DTC_SPLIT_NOTE in row(b, "Days to cover")) is note
    assert (SR.DTC_SPLIT_NOTE in b["title"]) is note
    r = rec("WHLR")
    want = BM.change_across_split(r["short_interest"], r["settlement_date"], r["prev_short_interest"],
                                  r["prev_settlement_date"], BM._rows(d["splits"]["rows"]))
    assert b["basis"]["change"] == want                                        # the change % keeps its inclusive rule
    assert b["si_change_pct"] == (want["pct"] if want else None)


@pytest.mark.parametrize("change,prev,s", [(None, "2026-10-30", "2026-11-13"), ("x", "2026-10-30", "2026-11-13"),
                                           ({"splits": "x"}, "2026-10-30", "2026-11-13"),
                                           ({"splits": [None, {"execution_date": "junk"}]}, "2026-10-30", "2026-11-13"),
                                           ({"splits": [{"execution_date": "2026-11-02"}]}, None, "2026-11-13"),
                                           ({"splits": [{"execution_date": "2026-11-14"}]}, "2026-10-30",
                                            "2026-11-13")])
def test_NEGATIVE_B1_split_in_window_on_junk_is_false(change, prev, s):
    assert BM.split_in_window(change, prev, s) is False


# ═════════════════════════════════════════════ B4 — a lagged older count [C7]
def test_B4_NXAT_corroborated_is_a_note_not_a_fall():
    b = blk("NXAT")
    assert BM.FLAG_COUNT_FELL not in keys(b) and "shares fell" not in b["chip"]
    assert b["basis"]["fell"] is None and b["basis"]["status"] == "ok"
    note = ("Share counts: Yahoo's 68,476,338 (9/10) predates its own adjustment for the 1-for-30 reverse split on 8/3 "
            "(on file) — split-adjusted 2,282,545 vs 3,236,567.")
    assert note in rows(b, "Note") and note in b["title"]
    lg = b["basis"]["lagged"]
    assert lg["corroborated"] is True and lg["cover"]["shares"] == 64221193 and lg["adj"] == 2282545
    frac = SR.SUSPECT_MAX_SHARES_OUT_FRACTION
    rb = lg["cover"]["adjusted"]
    assert rb * frac < 3236567 and 3236567 * frac < rb                         # 1.07M < 3.24M < 4.28M


def _nxat(covers=None, track_shares=None, new=None, splits=None):
    r, d = rec("NXAT"), doc("NXAT")
    if covers is not None:
        d["sec"] = dict(d["sec"], covers=covers)
    if track_shares is not None:
        d["float_track"] = dict(d["float_track"], shares=track_shares)
    if new is not None:                                         # Yahoo's newer count only (the record's stands)
        d["yahoo"] = dict(d["yahoo"], shares_outstanding=new)
    if splits is not None:
        d["splits"] = dict(d["splits"], rows=splits)
    return r, d


def test_NEGATIVE_B4_dilute_then_reverse_split_keeps_the_fall():
    cov = doc("NXAT")["sec"]["covers"][0]
    ten = 10_000_000                                                            # the spec's own case (§4.1 B4)
    r, d = _nxat(covers=[dict(cov, shares=ten)], track_shares=ten, new=ten // 10)
    b = SR.si_block(r, TODAY, basis=d)
    f = flag(b, BM.FLAG_COUNT_FELL)
    assert f is not None and "lagged" not in b["basis"]
    assert "a 1-for-30 reverse split on 8/3 is on file: the older count may already be adjusted for it" in f["text"]
    assert "no split on file" not in f["text"]
    # the contrast: the same docs with the new count INSIDE the split-adjusted cover band → a lagged count, no flag
    r2, d2 = _nxat(covers=[dict(cov, shares=ten)], track_shares=ten, new=ten // 30)
    b2 = SR.si_block(r2, TODAY, basis=d2)
    assert BM.FLAG_COUNT_FELL not in keys(b2) and b2["basis"]["lagged"]["corroborated"] is True


def test_NEGATIVE_B4_uncorroborated_no_cover_keeps_the_flag_and_names_the_split():
    r, d = _nxat(covers=[])
    b = SR.si_block(r, TODAY, basis=d)
    f = flag(b, BM.FLAG_COUNT_FELL)
    assert f["short"] == "❔ shares fell 21×" and b["basis"]["status"] == "partial"
    assert f["text"].startswith("❔ share count fell 21×: 3,236,567 (Yahoo, 11/27) vs 68,476,338 (9/10) — a 1-for-30 "
                                "reverse split on 8/3 is on file")
    assert "no split on file" not in f["text"]


def test_NEGATIVE_B4_a_fall_with_no_on_file_split_is_todays_text_byte_for_byte():
    r, d = _nxat(splits=[])
    b = SR.si_block(r, TODAY, basis=d)
    want = next(x["v"] for x in main_block("NXAT")["rows"] if x["k"] == "Shares fell")
    assert row(b, "Shares fell") == want and want.startswith("❔ share count fell 21× with no split on file:")
    assert "lagged" not in b["basis"]


def test_NEGATIVE_B4_growth_and_refusal_are_as_main_served_on_every_name():
    for s in NAMES:
        for d in (("plain", "split") if s in SPLIT_NAMES else ("plain",)):
            b, m = blk(s, d), main_block(s)
            for k in ("growth", "float_refused", "refused_reasons", "float_pct_on_file", "splits", "filings",
                      "float_update", "change"):
                assert b["basis"].get(k) == m["basis"].get(k), (s, d, k)
            if s != "NXAT":
                assert b["basis"]["fell"] == m["basis"]["fell"], (s, d)


# ═════════════════════════════════════════════ B5 — a split filing between the two float dates [C1]
def test_B5_POM_compared_both_pcts_the_rebased_caveat_not_flagged():
    b = blk("POM", "split")
    t = sc(b)["text"]
    assert sc(b)["state"] == "compared" and sc(b)["split_filing"] == "2026-10-19"
    assert "= 5.0% · Massive 576,290 (as of 3/31; 10,373,225 as published, split-adjusted) = 13.5%" in t
    assert t.endswith(SCK.TEXT_SPLIT_FILING_REBASED % "10/19")
    assert SCK.FLAG_SOURCES not in keys(b) and "rung" not in sc(b) and "float puts it at" not in t


def test_B5_BDMD_nothing_rebased_caveat_and_flagged():
    b = blk("BDMD", "split")
    t = sc(b)["text"]
    assert (SCK.TEXT_SPLIT_FILING % "11/16") in t and SCK.TEXT_SPLIT_FILING_REBASED % "11/16" not in t
    assert SCK.FLAG_SOURCES in keys(b) and sc(b)["split_filing"] == "2026-11-16"


def test_B5_NXAT_stays_compared_and_the_caveat_names_11_13():
    b = blk("NXAT", "split")
    assert sc(b)["state"] == "compared" and sc(b)["split_filing"] == "2026-11-13"
    assert sc(b)["text"].endswith(SCK.TEXT_SPLIT_FILING_REBASED % "11/13")
    assert "not comparable" not in sc(b)["text"]


def test_NEGATIVE_B5_a_filing_outside_the_two_dates_is_todays_line():
    d = doc("BDMD", split=True)
    d["sec"][BM.KEY_FTS_SPLIT]["rows"][0]["filed"] = "2026-11-21"           # after Yahoo's 11/20 read
    b = blk("BDMD", d)
    assert sc(b)["text"] == sc(blk("BDMD"))["text"] and "split_filing" not in sc(b)


def test_NEGATIVE_B5_no_split_read_is_todays_line_and_POM_then_flags_R5():
    for s in SPLIT_NAMES:
        assert "split_filing" not in sc(blk(s))
    b = blk("POM")
    assert SCK.FLAG_SOURCES in keys(b) and b["chip"].endswith(" · " + SCK.SHORT_SOURCES)      # the known R5 case


# ═════════════════════════════════════════════ the entry line
ENTRY = "checked 11/27 09:41 ET when it listed on 🚩 — re-read now: the second float. Yahoo's float is not re-read."


def test_entry_adds_one_row_and_one_title_sentence():
    b0, b = blk("BDMD"), blk("BDMD", entry=ENTRY)
    assert b["rows"][:-1] == b0["rows"] and b["rows"][-1] == {"k": SR.ROW_ENTRY_CHECK, "v": ENTRY}
    assert b["title"] == b0["title"].replace(SR._NOT_A_FORECAST, "%s: %s %s" % (SR.ROW_ENTRY_CHECK, ENTRY,
                                                                                SR._NOT_A_FORECAST))
    assert b["chip"] == b0["chip"] and b["extreme"] == b0["extreme"] and b["basis"] == b0["basis"]


@pytest.mark.parametrize("e", [None, "", "   ", 3, ["x"]])
def test_NEGATIVE_entry_none_or_junk_is_byte_identical(e):
    assert blk("WHLR", entry=e) == blk("WHLR")


def _map_db():
    si = FakeColl([dict(rec(s), _id=s) for s in NAMES], name=SIC.SI_COLL)
    from short_interest import share_basis as SB
    sb = FakeColl([doc(s) for s in NAMES], name=SB.SB_COLL)
    return FakeDB({SIC.SI_COLL: si, SB.SB_COLL: sb})


def _fake_ec(load, words=lambda row: row.get("w")):
    m = types.ModuleType("short_interest.entry_check")
    m.load, m.words = load, words
    return m


def _set_ec(monkeypatch, mod):
    """Plant the seam where read.py's lazy `from short_interest import entry_check` looks: sys.modules AND the package
    attribute (once the real module was imported by another test file, the attribute wins). None = an ImportError."""
    import short_interest
    monkeypatch.setitem(sys.modules, "short_interest.entry_check", mod)
    if mod is None:
        monkeypatch.delattr(short_interest, "entry_check", raising=False)
    else:
        monkeypatch.setattr(short_interest, "entry_check", mod, raising=False)


def test_si_map_reads_the_entry_sentences_through_the_seam(monkeypatch):
    calls = []

    def load(syms, session, db=None):
        calls.append((list(syms), session))
        return {"BDMD": {"w": ENTRY}, "WHLR": {"w": None}}
    _set_ec(monkeypatch, _fake_ec(load))
    got = SR.si_map(list(NAMES), db=_map_db(), today=TODAY)
    assert calls == [(sorted(NAMES, key=list(NAMES).index), TODAY.isoformat())]
    assert got["BDMD"]["rows"][-1] == {"k": SR.ROW_ENTRY_CHECK, "v": ENTRY}
    assert got["WHLR"] == blk("WHLR")


@pytest.mark.parametrize("how", ["raise", "junk", "import"])
def test_NEGATIVE_a_failing_seam_leaves_si_map_identical(monkeypatch, how):
    _set_ec(monkeypatch, _fake_ec(lambda *a, **k: {}))
    want = SR.si_map(list(NAMES), db=_map_db(), today=TODAY)
    assert want == {s: blk(s) for s in NAMES}
    if how == "import":
        _set_ec(monkeypatch, None)                                                   # ImportError
    elif how == "raise":
        _set_ec(monkeypatch, _fake_ec(lambda *a, **k: 1 / 0))
    else:
        _set_ec(monkeypatch, _fake_ec(lambda *a, **k: ["x"]))
    assert SR.si_map(list(NAMES), db=_map_db(), today=TODAY) == want
    assert SR._entry_words(list(NAMES), TODAY, _map_db()) == {}


# ═════════════════════════════════════════════ every surface the tokens reach [C8]
def _surfaces(b):
    from chart_maps.gajjala import high_si as HS
    from chart_maps.gajjala import si_track as ST
    fr = {"shares": b.get("float_shares")}
    ff = ST.filing_facts(b, TODAY.isoformat())
    flags = HS.si_flags(b)
    return {"classify": HS.classify(b, fr), "facts": {k: ff[k] for k in ("dilution", "split", "dilution_before",
                                                                           "split_before")},
            "ladder": ST._ladder_tier(b), "flag_shorts": ff["flag_shorts"], "si_flags": flags,
            "tier_chip": HS.tier_chip({"pct_record": b.get("pct_of_float"), "float_check": b.get("float_check"),
                                       "si_flags": flags})}


def test_surfaces_gain_exactly_the_new_tokens_and_nothing_listing_reads_moves(setmode):
    new = {"BDMD": [BM.SHORT_SPLIT_FILING % "11/16", SCK.SHORT_SOURCES], "NXAT": [BM.SHORT_SPLIT_FILING % "11/23 +1"]}
    for s, tokens in new.items():
        b = blk(s, "split")
        setmode("RUNG_FLAG", "off")
        d = doc(s, split=True)
        d["sec"].pop(BM.KEY_FTS_SPLIT)
        b0 = blk(s, d)
        setmode("RUNG_FLAG", "on")
        g, g0 = _surfaces(b), _surfaces(b0)
        assert g["classify"] == g0["classify"] and g["facts"] == g0["facts"] and g["ladder"] == g0["ladder"], s
        assert [t for t in g["flag_shorts"] if t not in g0["flag_shorts"]] == tokens, s
        assert [t for t in g["si_flags"] if t not in g0["si_flags"]] == tokens, s
        tc = g["tier_chip"]
        for t in tokens:
            assert tc.count(" · " + t) == 1, (s, t)
            tc = tc.replace(" · " + t, "")
        assert tc == g0["tier_chip"], s                                   # exactly the new tokens, nothing else
        assert g["si_flags"] == g["flag_shorts"] == SR._flag_shorts(b), s
    # NXAT lost its ❔ shares fell (B4) — a flag token gone, the pattern values unchanged
    b, m = blk("NXAT"), main_block("NXAT")
    assert "❔ shares fell 21×" in _surfaces(m)["flag_shorts"] and "❔ shares fell 21×" not in _surfaces(b)["flag_shorts"]
    assert _surfaces(b)["facts"] == _surfaces(m)["facts"] and _surfaces(b)["classify"] == _surfaces(m)["classify"]


# ═════════════════════════════════════════════ the LIVE 🧠 potential push TITLE carries them (refix, HIS CALL #21)
# tier_chip → si_ssr_names.hsi_tags (:175-178) → tag_block "text" → potential.title_lead → compose lead_text → the 🧠
# title, sent under POTENTIAL_PUSH_KIND (live). Not only the cross-push body (mode off): this one RINGS. Pinned so the
# reach is stated, not hidden; whether to keep the tokens off the title is his call (#21) — nothing is filtered here.
BDMD_LEAD_MAIN = "🩳 30.1% short interest · High (float unconfirmed)"
BDMD_LEAD_BUILD = BDMD_LEAD_MAIN + " · ✂️ split filing 11/16 · ⚠️ sources disagree"
TITLE_TAIL = "🚩 Bull Flag — trigger armed · UNMEASURED"


def _hsi_lead(sym, b):
    from chart_maps.gajjala import potential as PT
    from chart_maps.gajjala import si_ssr_names as SSN
    tags = SSN.hsi_tags([sym], {sym: {"shares": b.get("float_shares")}}, si_read=lambda ss: {sym: b}, today=TODAY)
    return PT.title_lead(SSN.tag_block(sym, {}, tags.get(sym), add=False))


def _ring(sym, b):
    """One LIVE (not dry, not shadow) 🧠 pass for `sym` with its 🩳 tag built from block `b` by the real engines."""
    from chart_maps.gajjala import potential as PT
    from chart_maps.gajjala import si_ssr_names as SSN
    from tests.test_gajjala_potential import OK_SEND, Rec, at, bf_armed, ctx_for, frame_at, seed
    from tests.test_gajjala_store import fake_store
    tags = SSN.hsi_tags([sym], {sym: {"shares": b.get("float_shares")}}, si_read=lambda ss: {sym: b}, today=TODAY)
    tag = SSN.tag_block(sym, {}, tags.get(sym), add=False)
    st, send, now = fake_store(), Rec(OK_SEND), at(10, 6)
    seed(st)
    reads = {sym: {"bull_flag": bf_armed()}}
    out = PT.run_pass(reads, {sym: frame_at(now)}, now, now.astimezone(PT.ET).date(), store=st,
                      ctx={sym: dict(ctx_for(), **({"si_ssr": tag} if tag is not None else {}))},
                      rows={sym: {"volume": 2_000_000, "price": 11.2}}, send=send, owner="owner@example.com",
                      dry=False, tape="rth")
    return out, [p for (_o, p), _k in send.calls]


def test_the_live_potential_push_title_gains_exactly_the_new_tokens_on_bdmd(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    from chart_maps.gajjala import constants as GC
    from chart_maps.gajjala import potential as PT
    assert PT.KIND == GC.POTENTIAL_PUSH_KIND                                     # the live 🧠 kind
    assert _hsi_lead("BDMD", main_block("BDMD")) == BDMD_LEAD_MAIN
    assert _hsi_lead("BDMD", blk("BDMD", "split")) == BDMD_LEAD_BUILD
    o0, (p0,) = _ring("BDMD", main_block("BDMD"))
    o1, (p1,) = _ring("BDMD", blk("BDMD", "split"))
    assert p0["title"] == "🧠 BDMD · %s · %s" % (BDMD_LEAD_MAIN, TITLE_TAIL)
    assert p1["title"] == "🧠 BDMD · %s · %s" % (BDMD_LEAD_BUILD, TITLE_TAIL)      # it RINGS with the new words
    # nothing else on the push moves: the dedupe tag, the kind, the link, the body, the pass counts
    assert {k: v for k, v in p1.items() if k != "title"} == {k: v for k, v in p0.items() if k != "title"}
    assert p1["tag"] == "gg-pot-bull_flag-BDMD" and o1 == o0


@pytest.mark.parametrize("sym", ["WHLR", "POM", "WETO"])
def test_NEGATIVE_no_new_token_no_title_change(sym):
    d = "split" if sym in SPLIT_NAMES else "plain"
    b = blk(sym, d)
    assert SCK.SHORT_SOURCES not in (b.get("chip") or "") and "✂️ split filing" not in (b.get("chip") or "")
    lead, lead0 = _hsi_lead(sym, b), _hsi_lead(sym, main_block(sym))
    assert lead == lead0                                       # unlisted (None) or listed: byte-identical to main
    if sym == "WHLR":                                          # a LISTED name: its title lead is real, not None
        assert lead is not None and lead.startswith("🩳 26.4% short interest · EXTREME")


def test_NEGATIVE_switches_off_and_no_split_read_give_the_title_of_main(setmode):
    setmode("RUNG_FLAG", "off")
    assert _hsi_lead("BDMD", blk("BDMD")) == BDMD_LEAD_MAIN
    setmode("RUNG_FLAG", "on")
    d = doc("BDMD", split=True)
    d["sec"].pop(BM.KEY_FTS_SPLIT)
    assert _hsi_lead("BDMD", blk("BDMD", d)) == BDMD_LEAD_MAIN + " · " + SCK.SHORT_SOURCES


def test_every_new_string_passes_the_forecast_check():
    for s in NAMES:
        for d in (("plain", "split") if s in SPLIT_NAMES else ("plain",)):
            for t in strings(blk(s, d)) + strings(blk(s, d, entry=ENTRY)):
                assert not FORBIDDEN.search(t), (s, t)
    for t in (BM.rules_sentence(), SCK.rules_sentence()):
        assert not FORBIDDEN.search(t)
    assert "'%s'" % (BM.SHORT_SPLIT_FILING % "M/D") in BM.rules_sentence()
    assert "'%s'" % BM.SHORT_DATE_GAP in BM.rules_sentence()
    assert BM.rules_sentence().endswith(" " + SCK.rules_sentence())
    sec = SR.rules_section()
    assert len(sec["picks"]) == 8                                              # folded, never a ninth pick


def test_no_new_division_and_no_new_pct_of_call():
    from tests import test_si_one_division_guard_2026_11_26 as G
    assert G.inventory() == G.INVENTORY
    for rel, n in G.CALLS.items():
        assert len(G.pct_of_calls(G._src(rel))) == n, rel


# ═════════════════════════════════════════════ the frontend fixture (generated from the backend)
FE_CASES = (("BDMD_flagged", "BDMD", "split"), ("WHLR_not_flagged", "WHLR", "plain"))


def build_fe_fixture() -> dict:
    blocks = {cid: json.loads(json.dumps(blk(s, d), ensure_ascii=False, allow_nan=False)) for cid, s, d in FE_CASES}
    return {"about": ("GENERATED by backend/tests/test_si_entry_flags_2026_11_27.py from the REAL 2026-11-27 capture "
                      "(tests/fixtures/si_entry_docs_2026_11_27.json): BDMD with the frozen-shape `sec.fts_split` copy "
                      "(flagged), WHLR as captured (not flagged); `old_payload` = the BDMD block main served at "
                      "capture (no new keys)."),
            "flag_key": SCK.FLAG_SOURCES, "short_sources": SCK.SHORT_SOURCES,
            "short_split_filing": BM.SHORT_SPLIT_FILING % "11/16",
            "blocks": blocks, "old_payload": main_block("BDMD")}


def test_the_frontend_fixture_is_the_backend_output():
    assert FE_FIX.is_file(), "regen: python -m tests.test_si_entry_flags_2026_11_27 --regen"
    assert json.loads(FE_FIX.read_text(encoding="utf-8")) == build_fe_fixture()


def test_NEGATIVE_the_frontend_fixture_carries_one_flagged_and_one_unflagged_chip():
    fx = build_fe_fixture()
    assert fx["blocks"]["BDMD_flagged"]["chip"].endswith(" · " + SCK.SHORT_SOURCES)
    assert SCK.SHORT_SOURCES not in fx["blocks"]["WHLR_not_flagged"]["chip"]
    assert SCK.SHORT_SOURCES not in fx["old_payload"]["chip"] and "split_filings" not in fx["old_payload"]["basis"]


if __name__ == "__main__":                                       # pragma: no cover — the deliberate regen
    if "--regen" in sys.argv:
        FE_FIX.parent.mkdir(parents=True, exist_ok=True)
        FE_FIX.write_text(json.dumps(build_fe_fixture(), ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                          encoding="utf-8")
        print("wrote", FE_FIX)
