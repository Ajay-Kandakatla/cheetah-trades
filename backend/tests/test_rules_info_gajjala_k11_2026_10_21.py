"""ℹ️ rules panel — the 🚩 Gajjala section's K11 line (2026-10-21, BUILD_SPEC22 B3).

GG VR 0.4 "1M is a floor … it must SUSTAIN (one 1M bar then a fade = not interested)" — Ajay 2026-10-21 "keep what
ever Gajjala says for these" on "Whether an A+ should also require today's volume to clear GG's 1M floor (NIXX rang
on 288K shares)". The line is built from GC.K11_MIN_SESSION_VOLUME (= SCAN_MIN_VOLUME, one number) and the detectors'
served words (K11_WHY, K11_UNKNOWN, NOT_APLUS_REASON) — never retyped. UNMEASURED.
"""
from __future__ import annotations

import ast
import inspect
import re

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as GD
from supply_demand import rules_info as RI

HEAD = "Today's volume on the A+:"


def _k11_lines(sec: dict) -> list:
    return [s for s in sec["stops"] if s.startswith(HEAD)]


@pytest.fixture
def sec():
    return RI._gajjala_section()


def test_one_k11_line_in_the_stops_with_the_floor_from_the_constant(sec):
    lines = _k11_lines(sec)
    assert len(lines) == 1
    line = lines[0]
    assert "≥ {:,} shares".format(int(GC.K11_MIN_SESSION_VOLUME)) in line
    assert GC.K11_MIN_SESSION_VOLUME == GC.SCAN_MIN_VOLUME                 # ONE number (his scanner floor)
    assert len(sec["stops"]) <= 6 and len(sec["picks"]) == 8               # the section's shape pins still hold


def test_the_served_words_are_the_detectors_constants(sec):
    line = _k11_lines(sec)[0]
    for word in (GD.K11_WHY, GD.K11_UNKNOWN, GD.NOT_APLUS_REASON):
        assert word in line, word
    assert "never pushed" in line and "potentials are not judged" in line


def test_mutating_the_floor_moves_the_line(monkeypatch):
    monkeypatch.setattr(GC, "K11_MIN_SESSION_VOLUME", 2_500_000)
    line = _k11_lines(RI._gajjala_section())[0]
    assert "≥ 2,500,000 shares" in line
    assert "1,000,000" not in line                                          # NEGATIVE: never a retyped floor


def test_mutating_the_why_moves_the_line(monkeypatch):
    monkeypatch.setattr(GD, "K11_WHY", "GG: changed words")
    line = _k11_lines(RI._gajjala_section())[0]
    assert "GG: changed words" in line
    assert "fade = not interested" not in line                              # NEGATIVE: the why is not retyped


def test_NEGATIVE_no_k_number_token_and_no_second_number(sec):
    """The panel's number test allows constant values only: the line names no "K11" token, and the only numbers
    in it are the floor and the "1M" inside his quoted why."""
    line = _k11_lines(sec)[0]
    assert "K11" not in line
    rest = line.replace(GD.K11_WHY, "").replace("{:,}".format(int(GC.K11_MIN_SESSION_VOLUME)), "")
    assert re.findall(r"\d", rest) == []


def test_NEGATIVE_the_section_source_still_holds_no_numeric_literal():
    tree = ast.parse(inspect.getsource(RI._gajjala_section).lstrip())
    lits = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
            and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)]
    assert lits == []


def test_NEGATIVE_no_reversal_ban_word_and_no_other_method_named(sec):
    line = _k11_lines(sec)[0]
    assert not re.search("b" + "ounc", line, re.I)
    assert not re.search(r"\bSEPA\b|Minervini|Bonde|RVOL", line)
