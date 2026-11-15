"""📶 The ℹ️ panel's base-count clause — supply_demand/rules_info._gg_run_bases_clause over run_bases.rules_line() (spec
ggbase §3.1 / WP-A step 8, 2026-11-15).

Ajay, verbatim: "There is a concept of 3 bases and climax run can you bake that in to the app please". Every number in
the sentence is a constant read at call time; the panel never breaks on the clause.
"""
from __future__ import annotations

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import run_bases as RB
from supply_demand import rules_info as RI


def _note() -> str:
    return RI._gajjala_section()["note"]


def test_the_clause_rides_the_note_right_after_the_fade_cross():
    note, line = _note(), RB.rules_line()
    assert line in note and RI._gg_run_bases_clause() == " " + line
    fade = RI._gg_fade_cross_clause()
    if fade:
        assert note.index(fade) < note.index(line)
    assert note.index(line) < note.index("UNMEASURED — no study here says these setups win")


def test_the_sentence_at_his_defaults():
    line = RB.rules_line()
    assert line.startswith("📶 Base count (GG, verified rule E6 — single source, his example(s)): on 5-min bars from "
                           "the 09:30 ET open to the 16:00 (13:00 on a half day) ET close, a run starts at 2 big green bars in a row; a "
                           "base "
                           "is a pause of 6–24 printed bars of any depth after such a run")
    assert "a pause longer than 24 bars ends the run and the next run counts from 1" in line
    assert "“3rd base — climax run, GG peels early”" in line and "“4th base — GG came out of everything”" in line
    assert "quoted, not computed" in line and "UNMEASURED" in line and "mine, not his" in line
    assert RB.FLAG_WORDS not in line


def test_the_numbers_move_with_the_constants(monkeypatch):
    monkeypatch.setattr(GC, "RUN_BASE_MIN_BARS", GC.K4_BF_PULL_MIN)
    monkeypatch.setattr(GC, "RUN_BASE_MAX_BARS", 30)
    monkeypatch.setattr(GC, "RUN_BASE_LEG_MIN_BARS", GC.KF_LEG_MIN_BARS)
    monkeypatch.setattr(GC, "RUN_BASE_FROM", "session")
    monkeypatch.setattr(GC, "RUN_BASE_UNTIL", "session")
    monkeypatch.setattr(GC, "RUN_BASE_RESTART", False)
    monkeypatch.setattr(GC, "RUN_BASE_DEPTH_FLOOR", True)
    line = RB.rules_line()
    assert "a pause of 1–30 printed bars" in line and RB.FLAG_WORDS in line
    assert "a run starts at 1 big green bars" in line
    assert "from the premarket through after hours" in line and "; the count runs the whole window" in line
    assert "holding the upper half of the run up's last big green bar" in line
    assert line in _note()


def test_NEGATIVE_a_raising_line_drops_the_clause_and_the_panel_stands(monkeypatch):
    monkeypatch.setattr(RB, "rules_line", lambda: 1 / 0)
    assert RI._gg_run_bases_clause() == ""
    note = _note()
    assert "📶 Base count" not in note and "UNMEASURED — no study here says these setups win" in note


def test_NEGATIVE_an_empty_line_adds_nothing(monkeypatch):
    monkeypatch.setattr(RB, "rules_line", lambda: "")
    assert RI._gg_run_bases_clause() == ""


def test_NEGATIVE_the_clause_never_says_the_b_word_or_advises():
    low = RB.rules_line().lower()
    for w in ("b" + "ounce", "sell", "buy", "exit"):
        assert w not in low, w
