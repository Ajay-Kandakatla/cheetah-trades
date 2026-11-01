"""ℹ️ Rules panel — the 🥇 Luk's section (BUILD SPEC luk-tab §3.12 / WP-D, 2026-11-01).

Ajay 2026-11-01, verbatim: "look at other winners of US stocks champion ship and pic the next best one like Gajjala.
Implement their strategy please if they have online resources."

The section is luk.playbook.rules_lines() split into the house shape the panel draws (picks / stops / alerts + note),
by the words each line already serves — never by position and never retyped: the shadow line → alerts; the stop line
(S2–S4) and the 🏁 exit line → "Stops & targets"; the rest → picks. Key "luk" sits right BEFORE "doji_sweep" so the
doji_sweep → high_beta → gajjala → fallen chain and the tail pins hold. NEGATIVES: a raising import / a raising
rules_lines() drops only this section and the panel still serves; no numeric literal in the section source; not a pad
section; no b-word, no "edge".
"""
from __future__ import annotations

import ast
import inspect
import re
import sys

import pytest

from chart_maps.luk import constants as LC
from chart_maps.luk import playbook as LPB
from supply_demand import rules_info as RI

_BW = "b" + "ounc"                                     # the b-word stem, never spelled in this file


def _text(sec: dict) -> str:
    return " ".join([sec["title"]] + sec["picks"] + sec["stops"] + sec["alerts"] + [sec["note"]])


@pytest.fixture()
def sec():
    return RI.sections()["luk"]


def test_luk_sits_right_before_doji_sweep_and_the_chain_pins_hold():
    keys = RI.SECTION_KEYS
    assert keys.count("luk") == 1
    assert keys.index("luk") == keys.index("doji_sweep") - 1
    assert keys.index("doji_sweep") == keys.index("high_beta") - 1      # test_rules_info_doji_sweep.py
    assert keys.index("high_beta") == keys.index("gajjala") - 1         # test_rules_info_high_beta.py
    assert keys.index("gajjala") == keys.index("fallen") - 1            # test_rules_info_gajjala.py
    assert keys[-3:] == ("fallen", "drop10", "short_interest")          # test_fallen_tab.py:879
    assert tuple(RI.sections()) == keys                                 # test_rules_info.py:30


def test_shape_matches_every_other_section(sec):
    assert sec["emoji"] == "🥇" and sec["title"] == "Luk's"
    assert " ".join([sec["emoji"], sec["title"]]) == LC.LUK_TAB_LABEL   # the panel heading == the tab label
    for cat in ("picks", "stops", "alerts"):
        assert isinstance(sec[cat], list) and sec[cat] and all(isinstance(x, str) and x for x in sec[cat]), cat
    assert len(sec["picks"]) <= 8 and len(sec["stops"]) <= 6            # test_rules_info.py:37
    assert sec["note"] == LPB.TITLE and "UNMEASURED" in sec["note"]


def test_every_served_line_lands_exactly_once_in_served_order(sec):
    lines = LPB.rules_lines()
    got = sec["picks"] + sec["stops"] + sec["alerts"]
    assert sorted(got) == sorted(lines) and len(got) == len(lines)
    for cat in ("picks", "stops", "alerts"):
        idx = [lines.index(x) for x in sec[cat]]
        assert idx == sorted(idx), cat


def test_the_buckets_carry_the_right_rules(sec):
    assert all("recorded in shadow, never sent" in a for a in sec["alerts"])
    assert any("Not advice" in a and "UNMEASURED" in a for a in sec["alerts"])
    stop = [s for s in sec["stops"] if s.startswith("Stop:")]
    assert len(stop) == 1 and "low of day" in stop[0]
    assert ("%g%%" % LC.LUK_LOD_SWITCH_PCT) in stop[0] and ("%g%%" % LC.LUK_STOP_MAX_PCT) in stop[0]   # S4 / S2-S3
    assert any(s.startswith("🏁") and LC.LUK_RECORD_FROM in s for s in sec["stops"])
    p = " ".join(sec["picks"])
    for word in ("Pre-market screen", "Pullback reversal", "Opening range", "Inside day", "Listed, never A+", "A+ ="):
        assert word in p, word
    assert not any("recorded in shadow" in x for x in sec["picks"] + sec["stops"])


def test_numbers_move_with_the_constants(monkeypatch):
    monkeypatch.setattr(LC, "LUK_STOP_MAX_PCT", 7.25)
    monkeypatch.setattr(LC, "LUK_SCREEN_TOP_N", 37)
    sec = RI.sections()["luk"]
    assert "within 7.25% of the trigger" in " ".join(sec["stops"])
    assert "Top 37 per screen" in " ".join(sec["picks"])


def test_the_split_reads_words_never_positions(monkeypatch):
    synthetic = ["x recorded in shadow, never sent y", "a pick", "Stop: here", "🏁 graded", "mid Stop: is a pick"]
    monkeypatch.setattr(LPB, "rules_lines", lambda: list(synthetic))
    sec = RI._luk_section()
    assert sec["alerts"] == ["x recorded in shadow, never sent y"]
    assert sec["stops"] == ["Stop: here", "🏁 graded"]
    assert sec["picks"] == ["a pick", "mid Stop: is a pick"]


def test_NEGATIVE_no_numeric_literal_in_the_section_source():
    src = inspect.getsource(RI._luk_section).lstrip()
    tree = ast.parse(src)
    lits = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
            and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)]
    assert lits == []
    assert isinstance(RI._LUK_ALERT_MARK, str) and all(isinstance(h, str) for h in RI._LUK_STOP_HEADS)
    for typed in ("LUK_STOP_MAX_PCT", "LUK_LOD_SWITCH_PCT", "LUK_NO_CHASE_PCT", "%"):
        assert typed not in src, typed


def test_NEGATIVE_a_raising_import_drops_only_the_section(monkeypatch):
    import chart_maps.luk as PKG
    monkeypatch.delattr(PKG, "playbook", raising=False)
    monkeypatch.setitem(sys.modules, "chart_maps.luk.playbook", None)            # `import` now raises ImportError
    secs = RI.sections()
    assert "luk" not in secs
    assert "doji_sweep" in secs and "gajjala" in secs and "short_interest" in secs
    assert RI.payload()["keys"] == list(RI.SECTION_KEYS)


@pytest.mark.parametrize("bad", [RuntimeError("boom"), KeyError("x"), ValueError("v")])
def test_NEGATIVE_a_raising_rules_lines_drops_only_the_section(monkeypatch, bad):
    def boom():
        raise bad
    monkeypatch.setattr(LPB, "rules_lines", boom)
    secs = RI.sections()
    assert "luk" not in secs and "doji_sweep" in secs and "in_demand" in secs
    assert RI.payload("luk")["sections"] == {}


def test_payload_serves_the_section_alone():
    body = RI.payload("luk")
    assert list(body["sections"]) == ["luk"] and "luk" in body["keys"]


def test_NEGATIVE_not_a_pad_section_and_no_pad_line(sec):
    assert "luk" not in RI.PAD_LINE_SECTIONS
    assert not any("🧱 Pad" in line for line in sec["stops"])


def test_NEGATIVE_no_ban_word_and_no_edge_claim(sec):
    text = _text(sec)
    assert not re.search(_BW, text, re.I)
    assert not re.search(r"\bedge\b", text, re.I)
    assert "None" not in text
