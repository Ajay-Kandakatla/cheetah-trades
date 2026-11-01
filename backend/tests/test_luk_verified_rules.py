"""chart_maps/luk/verified_rules.json — the cited rule registry (BUILD SPEC luk-tab §3.2, WP-A1).

Every quote is found verbatim (whitespace folded) in its fixture at the cited line ±2; the M3 quote ENDS at "…doing a
short" (the next caption line carries the b-word) and its resistance clause is a separate `kind "paraphrase"` item the
quote test skips; every LUK-tagged constant is in exactly one `used_by`; the 15 HIS CALLs are SYNTHESIS §D verbatim;
the external numbers sit on their cited lines; no b-word and no "edge" anywhere in the file. NEGATIVES included.
"""
from __future__ import annotations

import copy
import json
import pathlib
import re

import pytest

from chart_maps.luk import constants as LC
from tests.test_luk_constants import FIXTURES, fixture_lines, fold, luk_tagged, phrase_at, window

RULES_PATH = pathlib.Path(LC.__file__).resolve().parent / "verified_rules.json"
RAW = RULES_PATH.read_text(encoding="utf-8")
DOC = json.loads(RAW)
B_WORD = re.compile("b" + "ounc", re.I)
EDGE = re.compile(r"\bedge\b", re.I)
TOPIC_IDS = {
    "universe": ["U%d" % i for i in range(1, 9)],
    "entry": ["E%d" % i for i in range(1, 9)],
    "stop": ["S%d" % i for i in range(1, 5)],
    "exits": ["X%d" % i for i in range(1, 7)],
    "sizing": ["Z%d" % i for i in range(1, 5)],
    "market": ["M1", "M2", "M3", "M3-paraphrase"],
    "his_calls": ["H%d" % i for i in range(1, 16)],
    "record": ["R1", "R2"],
    "stats": ["ST1", "ST2", "ST3"],
    "external": ["EX1", "EX2"],
}
SOURCE_KEYS = ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "X1", "X2", "X3"]


def rules(doc=None):
    return [r for t in (doc or DOC)["topics"] for r in t["verified"]]


def by_id(doc=None):
    return {r["id"]: r for r in rules(doc)}


def quote_errors(doc) -> list:
    """Every quote that is not at its cited fixture line (±2). `kind "paraphrase"` items carry no quote — skipped."""
    errs = []
    for r in rules(doc):
        if r.get("kind") == "paraphrase" or not r["quotes"]:
            continue
        if len(r["quotes"]) != len(r["quote_src"]):
            errs.append((r["id"], "quotes / quote_src lengths differ"))
            continue
        for q, s in zip(r["quotes"], r["quote_src"]):
            f = s.get("file")
            if not f or not (FIXTURES / f).exists():
                errs.append((r["id"], "no fixture for the quote"))
            elif not phrase_at(q, f, s.get("line")):
                errs.append((r["id"], q[:40]))
    return errs


def test_the_shape():
    assert DOC["schema"] == "luk.verified_rules/1" and DOC["as_of"] == "2026-11-01"
    assert "SYNTHESIS.md §D" in DOC["built_from"]
    assert {"confirmed_first_hand", "confirmed_multi_source", "single_source", "contradicted",
            "unsupported"} <= set(DOC["status_labels"])
    assert [s["key"] for s in DOC["sources"]] == SOURCE_KEYS
    assert [t["key"] for t in DOC["topics"]] == list(TOPIC_IDS)
    for t in DOC["topics"]:
        assert [r["id"] for r in t["verified"]] == TOPIC_IDS[t["key"]], t["key"]


def test_every_rule_carries_the_fields():
    for r in rules():
        for k in ("id", "kind", "rule", "numbers", "status", "his_call", "applied", "sources", "quotes", "quote_src",
                  "used_by"):
            assert k in r, (r["id"], k)
        assert r["status"] in DOC["status_labels"], r["id"]
        assert r["applied"] in (True, False, "listed"), r["id"]
        assert isinstance(r["rule"], str) and r["rule"].strip(), r["id"]
        assert r["kind"] in ("rule", "paraphrase"), r["id"]
        for s in r["sources"]:
            assert {"key", "url", "first_hand", "ts", "line"} <= set(s), r["id"]
            assert s["url"].startswith("https://"), r["id"]


def test_first_hand_sources_and_the_fan_site():
    src = {s["key"]: s for s in DOC["sources"]}
    assert all(src[k]["first_hand"] is True for k in ("L1", "L2", "L3", "L4", "L5", "L6", "L7"))
    assert all(src[k]["first_hand"] is False for k in ("L8", "X1", "X2", "X3"))
    assert src["L7"]["url"] == "https://tradingresourcehub.substack.com/p/martin-luk-283-usic-2024-key-lessons"
    assert src["X1"]["url"] == "https://github.com/rootchunhe/martin-luk-backtesting"
    assert src["X2"]["url"] == "https://github.com/zongfan2/TradingAgents/pull/4"
    for s in DOC["sources"]:
        assert (FIXTURES / s["fixture"]).exists(), s["key"]


def test_his_rules_are_confirmed_first_hand():
    for r in rules():
        if re.match(r"^[UESXZM]\d$", r["id"]):
            assert r["status"] == "confirmed_first_hand", r["id"]
            assert any(s["first_hand"] for s in r["sources"]), r["id"]


def test_every_quote_is_at_its_cited_line():
    assert quote_errors(DOC) == []
    assert sum(len(r["quotes"]) for r in rules()) >= 60


def test_negative_a_quote_moved_off_its_line_fails():
    doc = copy.deepcopy(DOC)
    r = by_id(doc)["E4"]
    r["quote_src"][0]["line"] = "1546-1548"
    assert ("E4", r["quotes"][0][:40]) in quote_errors(doc)


def test_negative_a_quote_he_never_said_fails():
    doc = copy.deepcopy(DOC)
    r = by_id(doc)["S2"]
    r["quotes"][0] = r["quotes"][0].replace("maximum will be 5%", "maximum will be 6%")
    assert ("S2", r["quotes"][0][:40]) in quote_errors(doc)


def test_negative_a_paraphrase_is_never_matched_but_a_rule_kind_is():
    doc = copy.deepcopy(DOC)
    p = by_id(doc)["M3-paraphrase"]
    p["kind"] = "rule"
    p["quotes"], p["quote_src"] = [p["rule"]], [{"key": "L2", "file": "lS9zbnLi1Gg.txt", "line": "2466-2467"}]
    assert any(e[0] == "M3-paraphrase" for e in quote_errors(doc))


def test_m3_quote_ends_at_doing_a_short_and_the_clause_is_a_paraphrase():
    m3 = by_id()["M3"]
    assert m3["sources"][0]["line"] == "2458-2465" and m3["quote_src"][0]["line"] == "2458-2465"
    assert len(m3["quotes"]) == 1 and m3["quotes"][0].endswith("favorable time for doing a short")
    assert "caption drops" in m3["note"]
    para = by_id()["M3-paraphrase"]
    assert para["kind"] == "paraphrase" and para["quotes"] == [] and para["applied"] is False
    assert "reversing into a declining 21 or 50 EMA" in para["rule"]
    assert para["quote_src"] == "paraphrase of lS9zbnLi1Gg 1:58:04 — his caption says it another way"
    # the caption line right after the quote carries the b-word — the quote must not reach it
    assert B_WORD.search(window("lS9zbnLi1Gg.txt", "2467", pad=0))
    assert not B_WORD.search(window("lS9zbnLi1Gg.txt", "2458-2465", pad=0))
    assert not B_WORD.search(m3["quotes"][0])


def test_every_luk_tagged_constant_is_in_exactly_one_used_by():
    seen = {}
    for r in rules():
        for name in r["used_by"]:
            seen.setdefault(name, []).append(r["id"])
    tagged = luk_tagged()
    assert set(seen) == tagged
    assert {n: ids for n, ids in seen.items() if len(ids) != 1} == {}
    for name in seen:
        assert hasattr(LC, name), name


def test_negative_a_mine_constant_in_used_by_is_caught():
    doc = copy.deepcopy(DOC)
    by_id(doc)["U4"]["used_by"].append("LUK_SHORTLIST_MAX")
    names = {n for r in rules(doc) for n in r["used_by"]}
    assert names != luk_tagged()


def test_the_his_calls_are_synthesis_d_verbatim():
    lines = fixture_lines("SYNTHESIS.md")
    hs = [r for r in rules() if r["id"].startswith("H")]
    assert len(hs) == 15
    for i, r in enumerate(hs, start=1):
        src = r["quote_src"][0]
        raw = lines[int(src["line"]) - 1]
        assert raw.startswith("%d. " % i)
        assert r["rule"] == re.sub(r"^\d+\. ", "", raw.replace("**", "")).strip(), r["id"]
        assert (r["status"], r["his_call"], r["applied"]) == ("his_call", True, False)


def _norm(s: str) -> str:
    return s.replace("−", "-").replace("**", "")


@pytest.mark.parametrize("rid", ["R1", "EX1", "EX2"])
def test_external_numbers_sit_on_their_cited_lines(rid):
    r = by_id()[rid]
    text = " ".join(_norm(window(s["file"], s["line"], pad=0)) for s in r["quote_src"])
    nums = re.findall(r"[+-]?\d+(?:\.\d+)?%?R?", _norm(r["rule"]))
    nums = [n for n in nums if any(c in n for c in ".%")]
    assert nums
    for n in nums:
        assert n.rstrip("R") in text, (rid, n)
    assert r["status"] == "external" and r["applied"] is False


def test_negative_an_external_number_off_its_line_fails():
    text = _norm(window("luk_bt_readme.md", "122", pad=0))
    assert "12.1%" in text and "13.1%" not in text


def test_his_considerations_are_listed_not_applied():
    u7 = by_id()["U7"]
    assert u7["applied"] is False and u7["his_call"] is True
    assert set(u7["used_by"]) == {"LUK_CONSIDERED_PX_VOL_USD", "LUK_CONSIDERED_EXCLUDES"}
    assert by_id()["U1"]["applied"] == "listed"           # >5% ADR — a chip, never a gate


def test_no_b_word_and_no_edge_anywhere_in_the_file():
    assert not B_WORD.search(RAW)
    assert not EDGE.search(RAW)


def test_negative_the_guards_see_a_planted_word():
    assert B_WORD.search(RAW.replace("reversing into", "b" + "ouncing into"))
    assert EDGE.search(RAW + " an edge ")
    assert not EDGE.search("knowledge hedge ledger")


def test_the_substack_quotes_are_byte_equal_to_one_fixture_line():
    lines = fixture_lines("substack_2025_02_01_quotes.md")
    subs = [q for r in rules() for q, s in zip(r["quotes"], r["quote_src"]) if isinstance(s, dict) and s["key"] == "L7"]
    assert len(subs) >= 15
    for q in subs:
        assert any(q in ln for ln in lines), q             # byte-equal to (a part of) ONE published sentence line


def test_the_fixture_reader_folds_caption_wraps():
    assert fold("a\n  b") == "a b"
    assert phrase_at("at most it is 280% long", "VKNEJA5r8zw.txt", "910-911")


def test_every_caption_quote_sits_on_exactly_its_cited_lines():
    """Stricter than the ±2 rule: the quote_src line range itself holds the quote (pad 0)."""
    off = [(r["id"], s["line"]) for r in rules() if r["kind"] == "rule"
           for q, s in zip(r["quotes"], r["quote_src"]) if s.get("line") and not phrase_at(q, s["file"], s["line"], 0)]
    assert off == []
