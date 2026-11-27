"""🧘 2026-11-27 — the ℹ️ panel's ONE clause on the GG-like calm check (spec gglike rev 2 §4 main-session).

Ajay 2026-11-27 ~00:15 ET, verbatim: "Yes please, I think we are in bear market and looking at bad setups and make them
work, forcing them to work honestly... Can you update them please.. find calmer and better setups.. Continue to track
the runners we might evolve and find patterns in the current runners too but I want to make sure we are finding similar
setups to Gajjala"

supply_demand.rules_info._gg_like_clause() == " " + chart_maps.gajjala.gg_like.rules_line(), inside the 🚩 section note,
built from the constants (a moved bound moves the panel), and "" when the module raises (the panel never breaks).
"""
from __future__ import annotations

import ast
import inspect
import re

from chart_maps.gajjala import gg_like as GL
from supply_demand import rules_info as RI


def test_the_clause_is_the_engines_line_inside_the_gajjala_note():
    line = GL.rules_line()
    assert isinstance(line, str) and line
    assert RI._gg_like_clause() == " " + line
    note = RI._gajjala_section()["note"]
    assert note.count(line) == 1
    assert GL.CHIP_OK in note and "display only" in note


def test_the_clause_sits_in_the_note_once_and_the_helper_types_no_digit():
    src = inspect.getsource(RI._gajjala_section)
    assert src.count("_gg_like_clause()") == 1
    tree = ast.parse(inspect.getsource(RI._gg_like_clause))
    words = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert [w for w in words if re.search(r"[0-9]", w) and "2026" not in w] == []


def test_the_panel_moves_with_a_moved_bound(monkeypatch):
    before = RI._gajjala_section()["note"]
    assert "within 15% of the day's high" in before
    monkeypatch.setattr(GL, "MAX_UNDER_HIGH_PCT", 12.5)
    after = RI._gajjala_section()["note"]
    assert "within 12.5% of the day's high" in after and "within 15% of the day's high" not in after


def test_the_panel_names_every_base_minimum_and_the_tennis_bound_from_the_constants(monkeypatch):
    monkeypatch.setattr(GL, "BASE_MIN_BARS", {**GL.BASE_MIN_BARS, "intraday_vcp": 7})
    monkeypatch.setattr(GL, "TENNIS_MIN_DROP_PCT", 18.0)
    clause = RI._gg_like_clause()
    assert "7 " in clause and "tennis ball 18% or more" in clause
    assert "6 " + GL._setup_emoji("intraday_vcp") not in clause


def test_NEGATIVE_a_raising_engine_drops_the_clause_never_the_panel(monkeypatch):
    monkeypatch.setattr(GL, "rules_line", lambda: 1 / 0)
    assert RI._gg_like_clause() == ""
    note = RI._gajjala_section()["note"]
    assert isinstance(note, str) and note
    assert GL.CHIP_OK + " (display only" not in note


def test_NEGATIVE_an_empty_or_non_string_line_adds_nothing(monkeypatch):
    for bad in ("", None, 3):
        monkeypatch.setattr(GL, "rules_line", lambda bad=bad: bad)
        assert RI._gg_like_clause() == ""
