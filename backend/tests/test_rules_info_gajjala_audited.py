"""ℹ️ Rules panel — the 🧪 Gajjala · Audited clause in the 🚩 Gajjala's section note (BUILD_SPEC gg-audited §3.7 /
WP-D, 2026-11-01).

Ajay 2026-11-01, verbatim: "I would like you to create a new tab for Gajjals when you modifiy with audit of End of day..
Gajjals-Audited  So we can keep track of improvements on this tab".

The clause is built by chart_maps.gajjala.audited_rules.rules_clause() — every rule number formatted from that
registry's constants, never typed in rules_info. It rides the note right after the one-minute clause. NEGATIVES: a
raising import / a raising clause / an empty clause → "" and the panel still serves; the clause source holds no
numeric literal; the note never prints the b-word.
"""
from __future__ import annotations

import ast
import inspect
import re
import sys

import pytest

from supply_demand import rules_info as RI


def _note() -> str:
    return RI.sections()["gajjala"]["note"]


def test_the_note_carries_the_registry_clause_verbatim():
    from chart_maps.gajjala import audited_rules as AUD
    clause = AUD.rules_clause()
    assert isinstance(clause, str) and clause
    assert RI._gg_audited_clause() == " " + clause
    assert clause in _note()


def test_the_clause_sits_after_the_one_minute_clause_and_before_the_tail():
    note = _note()
    one_min, aud = RI._gg_one_minute_clause(), RI._gg_audited_clause()
    assert one_min and aud
    tail = " UNMEASURED — no study here says these setups win. Not advice."
    assert note.endswith(aud + tail)
    assert note.index(one_min) < note.index(aud)


def test_the_clause_moves_with_the_registry(monkeypatch):
    from chart_maps.gajjala import audited_rules as AUD
    monkeypatch.setattr(AUD, "rules_clause", lambda: "🧪 SENTINEL clause")
    assert RI._gg_audited_clause() == " 🧪 SENTINEL clause"
    assert " 🧪 SENTINEL clause UNMEASURED — no study here" in _note()


def test_NEGATIVE_no_numeric_literal_in_the_clause_source():
    tree = ast.parse(inspect.getsource(RI._gg_audited_clause).lstrip())
    lits = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
            and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)]
    assert lits == []
    assert RI._gg_audited_clause in [fn for name, fn in vars(RI).items()
                                     if name.startswith(("_gajjala", "_gg_")) and callable(fn)]   # the section guard walks it


def test_NEGATIVE_the_section_source_names_no_audit_number():
    """The section itself never retypes a registry number (G1 k, G2 max, G4 cap, the floor)."""
    src = inspect.getsource(RI._gajjala_section) + inspect.getsource(RI._gg_audited_clause)
    assert "audited_rules" in src
    for typed in ("G1_K", "G4_MAX_RISK_PCT", "MEASURE_FLOOR_WEEKS", "2.0", "10.0"):
        assert typed not in src, typed


def test_NEGATIVE_a_raising_import_empties_the_clause_and_the_panel_still_serves(monkeypatch):
    import chart_maps.gajjala as PKG
    monkeypatch.delattr(PKG, "audited_rules", raising=False)
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala.audited_rules", None)       # `import` now raises ImportError
    assert RI._gg_audited_clause() == ""
    secs = RI.sections()
    assert "gajjala" in secs and "fallen" in secs
    note = secs["gajjala"]["note"]
    assert note.endswith(RI._gg_one_minute_clause() + " UNMEASURED — no study here says these setups win. Not advice.")
    assert "None" not in note


@pytest.mark.parametrize("bad", [RuntimeError("boom"), KeyError("x")])
def test_NEGATIVE_a_raising_clause_is_empty(monkeypatch, bad):
    from chart_maps.gajjala import audited_rules as AUD

    def boom():
        raise bad
    monkeypatch.setattr(AUD, "rules_clause", boom)
    assert RI._gg_audited_clause() == ""
    assert "gajjala" in RI.sections()


@pytest.mark.parametrize("junk", ["", None, 7, ["x"]])
def test_NEGATIVE_an_empty_or_non_string_clause_adds_nothing(monkeypatch, junk):
    from chart_maps.gajjala import audited_rules as AUD
    monkeypatch.setattr(AUD, "rules_clause", lambda: junk)
    assert RI._gg_audited_clause() == ""


def test_NEGATIVE_no_reversal_ban_word_in_the_note():
    assert not re.search("b" + "ounc", _note(), re.I)
    assert not re.search("b" + "ounc", RI._gg_audited_clause(), re.I)
