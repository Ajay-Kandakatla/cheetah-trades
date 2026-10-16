"""ℹ️ Rules panel — the 🕯️ Doji Sweep section (supply_demand/rules_info.py, BUILD_SPEC6 §3.8.4, WP-B; 2026-10-16).

Ajay 2026-10-16: "create me a new tab for Doji candle after a sweep. For any stocks after a down trend. May be from
all chart maps especially on the 60% 70% down stocks" — then "Within 5% either side counts as a test".

Built FROM chart_maps.doji_sweep_tab (DJ) and the modules it reuses, never retyped: the section source holds no
numeric literal but the `100` that turns a fraction into a percent, every order line / sort label / the study line
are the tab's own served words, and the sources are cited by name and year. UNMEASURED; pushes nothing.
"""
from __future__ import annotations

import ast
import inspect

import pytest

from chart_maps import doji_sweep_measured as DSM
from chart_maps import doji_sweep_tab as DJ
from chart_maps import fallen_tab as FAL
from chart_maps.high_beta_tab import FORBIDDEN_WORDS
from patterns import candles_daily as CD
from patterns import history as PH
from supply_demand import key_levels as KL
from supply_demand import rules_info as RI


_BW = "b" + "ounc"                                     # the b-word stem, never spelled in this file
# WP-R 2026-10-16: the primary's served verdict words (W31 "no_signal") and the strings the
# measured line must never carry.
PRIMARY_WORDS = "no difference this study can separate from zero"
STALE_STRINGS = ("UNMEASURED", "until the study lands", "until it lands", _BW)

def _text(sec: dict) -> str:
    return " ".join([sec["title"]] + sec["picks"] + sec["stops"] + sec["alerts"] + [sec["note"]])


@pytest.fixture()
def sec():
    return RI.sections()["doji_sweep"]


def test_doji_sweep_sits_right_before_high_beta_and_the_tail_pins_hold():
    keys = RI.SECTION_KEYS
    assert keys.count("doji_sweep") == 1
    assert keys.index("doji_sweep") == keys.index("high_beta") - 1
    assert keys.index("high_beta") == keys.index("gajjala") - 1            # test_rules_info_high_beta.py
    assert keys.index("gajjala") == keys.index("fallen") - 1
    assert keys[-3:] == ("fallen", "drop10", "short_interest")
    assert tuple(RI.sections()) == keys


def test_shape_matches_every_other_section(sec):
    assert sec["title"].startswith(DJ.TAB_LABEL) and sec["emoji"] == DJ.MARK
    for cat in ("picks", "stops", "alerts"):
        assert isinstance(sec[cat], list) and sec[cat] and all(isinstance(x, str) and x for x in sec[cat])
    assert len(sec["picks"]) <= 8 and len(sec["stops"]) <= 6
    assert sec["stops"][0].startswith("No stop, no target, no size")
    assert "doji_sweep" not in RI.PAD_LINE_SECTIONS
    assert f"prior {DJ.SWEEP_REF_SESSIONS}-session low" in sec["title"]


def test_every_served_order_line_sort_label_and_the_study_line_is_on_the_panel(sec):
    picks = " ".join(sec["picks"])
    served = DJ.served_sorts()
    assert len(served) == 3
    for s in served:
        assert s["label"] in picks and DJ.order_line(s["key"]) in picks, s
    assert sec["picks"][-1] == DJ.study_block()["text"]
    # WP-R 2026-10-16: the study ran (one outcome run, head 2845fe24) — the pin moved from the placeholder to the measured line
    assert DJ.study_block()["status"] == "measured"
    assert "MEASURED" in sec["picks"][-1] and "UNMEASURED" not in sec["picks"][-1]
    assert PRIMARY_WORDS in sec["picks"][-1]


def test_the_sources_and_his_words_are_named(sec):
    t = _text(sec)
    for need in ("Connors & Raschke", "1995", "Bulkowski", "Marshall", "Nison 1991", "PivotBoss",
                 "Bruce Fraser", "Within 5% either side counts as a test", CD.BULKOWSKI_CANDLE["doji"],
                 CD.CAVEAT, DJ.DRAGONFLY_CLAIM):
        assert need in t, need
    a = " ".join(sec["alerts"])
    assert PH.DOJI_SWEEP_KIND in a and "Pushes nothing" in a and "GET /patterns/accuracy" in a
    assert f"next {PH.CANDLE_HORIZON} sessions" in a
    assert "never join the 🗺️ Chart Maps tape-burst watch" in a                # AMENDMENTS6 B3


def test_the_picks_state_every_number_from_its_constant(sec):
    t = _text(sec)
    b5, b10 = DJ.BODY_STEPS
    assert f"after {KL.ROLL_AT.strftime('%H:%M')} ET" in t
    assert f"fewer than {DJ.YEAR_BARS} sessions" in t
    assert f"under {b5}% of the day's range" in t and f"bodies under {b10}%" in t
    assert f"at most {DJ.SMALL_WICK_PCT * 100:g}% of the range" in t
    assert f"prior {DJ.LONG_LEG_BARS} sessions'" in t
    assert f"lowest low of the {DJ.SWEEP_REF_SESSIONS} sessions before it" in t
    assert f"at least {DJ.SWEEP_REF_MIN_AGE} sessions old" in t
    assert f"{DJ.DOWN_PCT:g}% or more under the 52-week high (the {FAL.TAB_LABEL} tab's own read)" in t
    assert f"below both the {DJ.SMA_FAST}- and {DJ.SMA_SLOW}-day" in t
    for k in DJ.FILTER_KEYS:
        assert DJ.FILTER_LABELS[k] in t, k
    assert f"prior {DJ.VOL_AVG_BARS} sessions'" in t and f"{DJ.VOL_QUIET_X:g}×" in t and f"{DJ.VOL_HEAVY_X:g}×" in t
    assert f"{DJ.ATR_BARS}-day ATR" in t


MUTATIONS = [
    ("SWEEP_TEST_PCT", 7.0, "“Within 7% either side counts as a test”"),
    ("SWEEP_REF_SESSIONS", 30, "the 30 sessions before it"),
    ("SWEEP_REF_MIN_AGE", 6, "at least 6 sessions old"),
    ("DOWN_PCT", 65.0, "65% or more under the 52-week high"),
    ("SMA_FAST", 40, "below both the 40- and"),
    ("LONG_LEG_BARS", 12, "prior 12 sessions'"),
    ("VOL_QUIET_X", 0.8, "quiet at or under 0.8×"),
    ("YEAR_BARS", 250, "fewer than 250 sessions"),
    ("BODY_STEPS", (4, 12), "under 4% of the day's range"),
]


@pytest.mark.parametrize("name,val,want", MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_mutating_a_constant_moves_the_text(monkeypatch, name, val, want):
    assert want not in _text(RI._doji_sweep_section())
    monkeypatch.setattr(DJ, name, val)
    assert want in _text(RI._doji_sweep_section())


def test_mutating_the_roll_and_the_ledger_horizon_moves_the_text(monkeypatch):
    from datetime import time as dtime
    monkeypatch.setattr(KL, "ROLL_AT", dtime(19, 30))
    monkeypatch.setattr(PH, "CANDLE_HORIZON", 7)
    t = _text(RI._doji_sweep_section())
    assert "after 19:30 ET" in t and "next 7 sessions" in t


def test_NEG_no_numeric_literal_in_the_section_source_but_100():
    tree = ast.parse(inspect.getsource(RI._doji_sweep_section).lstrip())
    lits = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
            and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)]
    assert set(lits) <= {100}, lits
    assert lits.count(100) == 1


def test_NEG_the_literal_walk_bites():
    tree = ast.parse("def f():\n    return f'{x * 100:g} and {5}'\n")
    lits = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
            and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)]
    assert set(lits) - {100} == {5}


def test_NEG_no_b_word_and_no_forecast_word(sec):
    low = _text(sec).lower()
    assert _BW not in low
    for w in FORBIDDEN_WORDS:
        assert w not in low, w
    src = inspect.getsource(RI._doji_sweep_section).lower()
    assert _BW not in src


def test_the_note_is_the_disclaimer_once_measured(sec, monkeypatch):
    # WP-R 2026-10-16: the study ran (one outcome run, head 2845fe24) — the pin moved from the placeholder to the measured line
    assert DJ.is_measured() is True and sec["note"] == RI._DISCLAIMER
    monkeypatch.setattr(DJ, "is_measured", lambda: True)
    assert RI._doji_sweep_section()["note"] == RI._DISCLAIMER


def test_NEG_the_placeholder_path_still_says_unmeasured(monkeypatch):
    monkeypatch.setattr(DSM, "MEASURED", {"state": "unmeasured"})
    s = RI._doji_sweep_section()
    assert s["note"].startswith("UNMEASURED") and s["note"].endswith(RI._DISCLAIMER)
    assert s["picks"][-1] == DJ.NOTE_PENDING and "UNMEASURED" in s["picks"][-1]


def test_NEG_the_measured_panel_never_says_a_stale_string(sec):
    for line in (sec["picks"][-1], sec["note"]):
        low = line.lower()
        for w in STALE_STRINGS:
            assert w.lower() not in low, w


def test_NEG_a_broken_section_never_breaks_the_panel(monkeypatch):
    def boom():
        raise RuntimeError("tab module broke")
    monkeypatch.setattr(RI, "_doji_sweep_section", boom)
    secs = RI.sections()
    assert "doji_sweep" not in secs and "high_beta" in secs and "fallen" in secs
