"""chart_maps/luk/playbook.py — the 📓 Playbook and the ℹ️ panel lines (BUILD SPEC luk-tab §3.10 / §3.12, WP-A1).

Sections in the spec's order; every item {text, cite_text, url, kind ∈ his|mine|external|his_call|consideration};
his rule items carry his caption words verbatim (the registry's quotes); the 2% QQQ remark is kind "his" prose and no
*THRESHOLD* constant exists; every number the module FORMATS is a constant's value (monkeypatching a constant moves the
text); no b-word and no "edge" in anything served. NEGATIVES included.
"""
from __future__ import annotations

import json
import re

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.luk import constants as LC
from chart_maps.luk import playbook as PB

B_WORD = re.compile("b" + "ounc", re.I)
EDGE = re.compile(r"\bedge\b", re.I)
SECTION_KEYS = ["who", "scans", "tiers", "where", "trigger", "stop", "exits", "sizing", "market", "considerations",
                "formulas", "his_calls", "external", "stats"]
NUM = re.compile(r"\d+(?:\.\d+)?")


def _items(pb=None):
    return {it["id"]: it for it in PB.all_items(pb)}


def allowed_numbers() -> set:
    """Every value a formatted number may take: LC's numbers (tuple members too), scaled by the K / M / B units, the
    digits of LC's clock / date strings, GC's cadence in minutes and settle seconds."""
    vals = set()
    for name in dir(LC):
        v = getattr(LC, name)
        members = v if isinstance(v, tuple) else (v,)
        for m in members:
            if isinstance(m, (int, float)) and not isinstance(m, bool):
                for unit in (1, 1_000, 1_000_000, 1_000_000_000):
                    vals.add(round(m / unit, 9))
            elif isinstance(m, str) and re.fullmatch(r"[\d:\-]+", m):
                vals |= {float(x) for x in re.findall(r"\d+", m)}
    vals |= {GC.PASS_CADENCE_SEC / 60, float(GC.BAR_SETTLE_SEC)}
    return vals


def typed_numbers(lines) -> list:
    ok = allowed_numbers()
    return [(n, ln[:60]) for ln in lines for n in NUM.findall(ln) if round(float(n), 9) not in ok]


# ── the Playbook ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_sections_in_the_spec_order():
    pb = PB.playbook()
    assert pb["title"] == PB.TITLE
    assert [s["key"] for s in pb["sections"]] == SECTION_KEYS
    assert all(isinstance(s["title"], str) and s["title"] and s["items"] for s in pb["sections"])


def test_every_item_has_the_served_shape():
    for it in PB.all_items():
        assert set(it) >= {"id", "text", "cite_text", "url", "kind", "verbatim"}, it
        assert it["kind"] in PB.KINDS, it["id"]
        assert isinstance(it["text"], str) and it["text"].strip(), it["id"]
        assert isinstance(it["cite_text"], str) and it["cite_text"].strip(), it["id"]
        assert it["url"] is None or it["url"].startswith("https://"), it["id"]


def test_his_items_carry_his_caption_words_verbatim():
    by_id = PB.rules_by_id()
    n = 0
    for it in PB.all_items():
        r = by_id.get(it["id"])
        if not r or r["kind"] == "paraphrase" or not r["quotes"]:
            continue
        for q in r["quotes"]:
            assert "“%s”" % q in it["text"], (it["id"], q[:40])
            n += 1
        assert it["verbatim"] is True
    assert n >= 60


def test_the_kinds():
    items = _items()
    assert items["U7"]["kind"] == "consideration"
    assert [items["H%d" % i]["kind"] for i in range(1, 16)] == ["his_call"] * 15
    assert items["H7"]["cite_text"] == "SYNTHESIS §D #7 — not applied, his call"
    for k in ("R1", "EX1", "EX2"):
        assert items[k]["kind"] == "external" and items[k]["text"].endswith(PB.EXTERNAL_TAIL)
    assert all(it["kind"] == "mine" for it in PB.formula_items())
    for k in ("E1", "E2", "S4", "X2", "M1", "ST2", "R2"):
        assert items[k]["kind"] == "his", k


def test_the_cites():
    items = _items()
    assert items["E1"]["cite_text"] == "VKNEJA5r8zw 0:49:58"
    assert items["E1"]["url"] == "https://www.youtube.com/watch?v=VKNEJA5r8zw&t=2998s"
    assert items["U1"]["cite_text"] == PB.SUBSTACK_CITE
    assert items["U1"]["url"] == "https://tradingresourcehub.substack.com/p/martin-luk-283-usic-2024-key-lessons"
    assert items["S4"]["cite_text"] == "lS9zbnLi1Gg 0:38:02"
    assert items["EX2"]["url"] == "https://github.com/zongfan2/TradingAgents/pull/4"


def test_the_2pct_qqq_remark_is_his_prose_and_no_threshold_exists():
    m2 = _items()["M2"]
    assert m2["kind"] == "his" and "“Qs is almost 2% above the 9 EMA”" in m2["text"]
    assert "not a threshold" in m2["text"]
    assert not [n for n in dir(LC) if "THRESHOLD" in n] and not hasattr(LC, "LUK_QQQ_EXAMPLE_PCT")
    assert not [n for n in dir(PB) if "THRESHOLD" in n]


def test_the_m3_paraphrase_is_served_as_a_paraphrase():
    p = _items()["M3-paraphrase"]
    assert p["kind"] == "his" and p["verbatim"] is False
    assert "reversing into a declining 21 or 50 EMA" in p["text"] and "paraphrased" in p["text"]
    m3 = _items()["M3"]
    assert m3["text"].count("“") == 1 and "favorable time for doing a short”" in m3["text"]


def test_the_sizing_example_follows_the_constant(monkeypatch):
    ex = _items()["Z2-example"]
    assert ex["text"].startswith("Worked example, his: a $10,000 account risking 0.5% = $50 of risk; $50 ÷ a 2.5% stop "
                                 "= a $2,000 position (20% of the account)")
    assert ex["cite_text"] == "VKNEJA5r8zw 3:03:50" and ex["kind"] == "his"
    monkeypatch.setattr(LC, "LUK_SIZING_EXAMPLE", (20_000, 1.0, 200, 4.0, 5_000, 25))
    ex2 = _items()["Z2-example"]
    assert "$20,000 account risking 1% = $200" in ex2["text"] and "$5,000 position (25% of" in ex2["text"]


def test_the_formulas_follow_the_constants(monkeypatch):
    texts = [it["text"] for it in PB.formula_items()]
    assert "ADR = 20 sessions, the house ADR (his \"ADR\" names no period)" in texts
    assert "1-month % = the change over 21 sessions" in texts
    assert any("30 s after the 16:00 ET close" in t for t in texts)
    monkeypatch.setattr(LC, "LUK_ADR_SESSIONS", 14)
    assert "ADR = 14 sessions, the house ADR (his \"ADR\" names no period)" in [it["text"] for it in
                                                                               PB.formula_items()]


def test_negative_an_unreadable_registry_still_serves_the_sections(monkeypatch):
    monkeypatch.setattr(PB, "_rules_doc", lambda: None)
    pb = PB.playbook()
    assert [s["key"] for s in pb["sections"]] == SECTION_KEYS
    by_key = {s["key"]: s["items"] for s in pb["sections"]}
    assert [it["id"] for it in by_key["sizing"]] == ["Z2-example"]
    assert len(by_key["formulas"]) == len(PB.formula_items()) and by_key["who"] == []


def test_negative_a_missing_rule_is_skipped_never_invented():
    doc = json.loads(PB._RULES_FILE.read_text(encoding="utf-8"))
    for t in doc["topics"]:
        t["verified"] = [r for r in t["verified"] if r["id"] != "M2"]
    ids = [it["id"] for it in PB.all_items(PB.playbook(doc))]
    assert "M2" not in ids and "M1" in ids


# ── the ℹ️ panel lines ────────────────────────────────────────────────────────────────────────────────────────────
def test_rules_lines_are_served_sentences():
    lines = PB.rules_lines()
    assert isinstance(lines, list) and len(lines) >= 8
    assert all(isinstance(ln, str) and ln.strip() for ln in lines)
    blob = " ".join(lines)
    for w in ("shadow, never sent", "UNMEASURED", "Pullback reversal", "never a gate", "listed, not A+"):
        assert w in blob, w


def test_every_number_in_the_rules_lines_is_a_constant_value():
    assert typed_numbers(PB.rules_lines()) == []


def test_negative_a_typed_number_is_caught():
    assert typed_numbers(["more than 7% above the low of day"]) == [("7", "more than 7% above the low of day")]


def test_the_rules_lines_follow_the_constants(monkeypatch):
    monkeypatch.setattr(LC, "LUK_NO_CHASE_PCT", 4.25)
    monkeypatch.setattr(LC, "LUK_SCREEN_MIN_CAP_USD", 250_000_000)
    monkeypatch.setattr(LC, "LUK_SHORTLIST_MAX", 33)
    blob = " ".join(PB.rules_lines())
    assert "more than 4.25% above the low of day" in blob and "market cap > $250M" in blob
    assert "up to 33 screened names" in blob
    assert typed_numbers(PB.rules_lines()) == []


def test_negative_the_rules_lines_carry_the_shown_numbers():
    blob = " ".join(PB.rules_lines())
    assert "more than 3% above the low of day" in blob
    assert "1-minute bars for the first 15 minutes, 5-minute bars to 60 minutes" in blob
    assert "within 5% of the trigger and within 0.5 × the 20-day ADR" in blob
    assert "04:00–16:05 ET" in blob and "from 2026-11-01" in blob


# ── words ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _served_strings():
    out = [PB.TITLE] + PB.rules_lines()
    for s in PB.playbook()["sections"]:
        out.append(s["title"])
        for it in s["items"]:
            out += [it["text"], it["cite_text"]]
    return out


def test_no_b_word_and_no_edge_in_anything_served():
    for s in _served_strings():
        assert not B_WORD.search(s), s[:80]
        assert not EDGE.search(s), s[:80]


def test_reversal_is_the_word():
    assert "reversal" in " ".join(PB.rules_lines()).lower()
