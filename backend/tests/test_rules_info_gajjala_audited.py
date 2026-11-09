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


def test_the_clause_names_all_twelve_entries_and_the_exit_grades():
    """2026-11-01 (SPEC gg-audited-mods §3.1, Ajay "Yes make the changes in audited please"): the clause follows the
    twelve-entry registry — the nine filters before "Exit grades", T3 / T5 after it, G3 as the lane-only gate."""
    from chart_maps.gajjala import audited_rules as AUD
    clause = RI._gg_audited_clause()
    assert len(AUD.REGISTRY) == 13                                                   # 2026-11-09: + K3S (an ADMIT)
    for r in AUD.REGISTRY:
        assert f"{r.id} {r.name}" in clause, r.id
    ex = clause.index("Exit grades on its 🏁 beside GG's math:")
    for r in AUD.filter_rules():
        assert clause.index(f"{r.id} {r.name}") < ex, r.id
    for r in AUD.exit_rules():
        assert clause.index(f"{r.id} {r.name}") > ex, r.id
    assert [r.id for r in AUD.exit_rules()] == ["T3", "T5"]
    assert "None" not in clause and not re.search(r"\bedge\b", clause, re.I)


def test_NEGATIVE_an_off_rule_leaves_the_clause(monkeypatch):
    import dataclasses
    from chart_maps.gajjala import audited_rules as AUD
    off = dataclasses.replace(AUD.T4, status=AUD.STATUS_OFF)
    monkeypatch.setattr(AUD, "REGISTRY", tuple(off if r.id == "T4" else r for r in AUD.REGISTRY))
    clause = RI._gg_audited_clause()
    assert "T4 regime gate" not in clause and "T2 first-hour block" in clause


def test_the_clause_carries_the_k3s_admit_after_the_exit_grades():
    """2026-11-09 (SPEC gg-k3s §3.2, Ajay "yes change the audit as per you like that is yours"): the ADMIT sentence
    names K3S and sits after the exit grades, before the lane-only gate."""
    from chart_maps.gajjala import audited_rules as AUD
    clause = RI._gg_audited_clause()
    ex = clause.index("Exit grades on its 🏁 beside GG's math:")
    ad = clause.index("Admits on the A+ read — a 🧪 A+ 🚩 never rings, with 🚩's own plan:")
    assert ex < ad < clause.index("K3S K3 volume-dry not binding on the 🎾 base") < clause.index("G3 ring age")
    assert [r.id for r in AUD.admit_rules()] == ["K3S"]
    assert not re.search("b" + "ounc", clause, re.I) and not re.search(r"\bedge\b", clause, re.I)


def test_NEGATIVE_k3s_off_drops_the_admit_sentence(monkeypatch):
    import dataclasses
    from chart_maps.gajjala import audited_rules as AUD
    off = dataclasses.replace(AUD.K3S, status=AUD.STATUS_OFF)
    monkeypatch.setattr(AUD, "REGISTRY", tuple(off if r.id == "K3S" else r for r in AUD.REGISTRY))
    clause = RI._gg_audited_clause()
    assert "Admits on the A+ read" not in clause and "K3S" not in clause
    assert "Exit grades on its 🏁 beside GG's math:" in clause
