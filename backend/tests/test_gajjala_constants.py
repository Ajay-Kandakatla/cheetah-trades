"""chart_maps/gajjala/constants.py — every number by name, each with its provenance (spec §3.2, DECISIONS round A/B/C).

AST scans keep the file honest: no placeholder left None, every number carries a provenance comment, Ajay's own numbers
are labelled "Cheetah default" (not Gajjala's), and the file imports nothing from another board's engine.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from chart_maps import board
from chart_maps.gajjala import constants as GC

SRC_PATH = pathlib.Path(GC.__file__)
SRC = SRC_PATH.read_text()
TREE = ast.parse(SRC)
LINES = SRC.splitlines()


def _assigns():
    """[(name, value_node, lineno)] for every top-level `NAME = …`."""
    out = []
    for node in TREE.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            out.append((node.targets[0].id, node.value, node.lineno))
    return out


def _is_numeric(v) -> bool:
    if isinstance(v, ast.Constant):
        return isinstance(v.value, (int, float)) and not isinstance(v.value, bool)
    if isinstance(v, ast.Tuple):
        return bool(v.elts) and all(_is_numeric(e) for e in v.elts)
    return isinstance(v, (ast.BinOp, ast.Call))


def _comment(lineno: int) -> str:
    line = LINES[lineno - 1]
    return line.split("#", 1)[1].strip() if "#" in line else ""


def test_pins_against_the_house_engines():
    assert (GC.TILE_LIMIT_DEFAULT, GC.TILE_LIMIT_MAX) == (board.LIMIT_DEFAULT, board.LIMIT_MAX)
    assert (GC.EMA_FAST, GC.EMA_SLOW) == (9, 21)
    assert GC.STALE_AFTER_SEC == 900
    assert GC.LEASE_MIN_GAP_SEC == GC.PASS_BUDGET_SEC


def test_subs_and_setups():
    assert tuple(k for k, _e, _l in GC.SUBS) == GC.SETUPS + ("premarket", "postmarket", "playbook")
    assert GC.DEFAULT_SUB in GC.SETUPS
    assert set(GC.PLACEHOLDER_BY_SETUP) <= set(GC.SETUPS)
    assert {h for hs in GC.PLACEHOLDER_BY_SETUP.values() for h in hs} <= set(GC.PLACEHOLDERS)
    assert set(GC.K3_DEPTH_SETUPS) <= set(GC.SETUPS)


def test_no_placeholder_left_until_ajay_answers():
    """H1–H5 answered 2026-10-13 (DECISIONS round C): no placeholder constant is None."""
    for hid, names in GC.PLACEHOLDERS.items():
        for n in names:
            assert getattr(GC, n) is not None, f"{n} ({hid}) still unanswered"


def test_the_only_none_values_are_the_named_off_switches():
    nones = {n for n, v, _ in _assigns() if isinstance(v, ast.Constant) and v.value is None}
    assert nones == set(GC.OFF_BY_DEFAULT)
    placeholder_names = {n for names in GC.PLACEHOLDERS.values() for n in names}
    assert not (placeholder_names & nones)
    assert all(hasattr(GC, n) for n in placeholder_names)


def test_answered_placeholders_are_well_formed():
    assert GC.K8_FAIL_EVENT_RULE in GC.K8_FAIL_EVENT_RULES
    for n in ("K8_FAIL_NEAR_PCT", "K8_FAIL_DROP_PCT"):
        assert isinstance(getattr(GC, n), (int, float)) and getattr(GC, n) > 0
    for n in ("HF_LEG_MIN_BARS", "VCP_LEG_MIN_BARS", "RS_BASE_MIN_BARS", "VCP_PIVOT_WINDOW"):
        v = getattr(GC, n)
        assert isinstance(v, int) and not isinstance(v, bool) and v > 0


def test_decisions_round_a_b_c_values():
    """Ajay's binding answers, by value (DECISIONS.md 'ROUND A/B/C ANSWERS')."""
    assert GC.SCAN_MIN_PRICE == 0.10 and GC.SCAN_MAX_PRICE == 100.0
    assert GC.SCAN_INSTRUMENT_TYPES == frozenset({"CS", "ADRC"}) and GC.SCAN_INCLUDE_OTC is False
    assert GC.SCAN_UNKNOWN_TYPE_POLICY == "list" and GC.SCAN_UNKNOWN_TYPE_LABEL == "type unknown"
    assert GC.GAJJALA_PUSH_MODE == "shadow" and GC.GAJJALA_PUSH_MODE in GC.PUSH_MODES
    assert GC.PUSH_KIND == "gajjala_setup"
    assert (GC.K4_BF_PULL_MIN, GC.K4_BF_PULL_MAX, GC.K4_BF_LONG_FLAG_MAX) == (1, 3, 5)
    assert GC.K4_KF_PULL_MAX == 9 and GC.KF_HONOR_ALL_PULLBACK_CLOSES is True
    assert GC.KF_ALLOW_NO_TOUCH is True and GC.KF_NO_TOUCH_VARIANT == "near_kiss"
    assert (GC.K8_FAIL_NEAR_PCT, GC.K8_FAIL_DROP_PCT, GC.K8_FAIL_EVENT_RULE) == (2, 8, "distinct")
    assert (GC.HF_LEG_MIN_BARS, GC.VCP_LEG_MIN_BARS, GC.RS_BASE_MIN_BARS, GC.VCP_PIVOT_WINDOW) == (2, 1, 1, 2)
    assert GC.HF_TRIGGER == "base_high" and GC.HF_TRIGGER in GC.HF_TRIGGERS
    assert GC.VCP_B_READS is True and GC.VCP_B_GRADE == "B"
    assert GC.K3_DEPTH_SETUPS == ("bull_flag", "kiss_fly")
    assert GC.K2_CHECK_FIRST_BAR is False
    assert (GC.RED_CLOSES_WAIT, GC.RED_CLOSES_MODE, GC.RED_CLOSE_DEF) == (3, "chip", "close_below_open")
    assert GC.RED_CLOSES_MODE in GC.RED_CLOSES_MODES
    assert GC.STAY_LISTED_SESSIONS == 2 and GC.PSY_NEAR_PCT == 5.0
    assert (GC.STUDY_SESSIONS, GC.STUDY_TIME_EXIT_MIN, GC.STUDY_BE_AFTER_R) == (250, 60, 1.0)
    assert GC.FLOAT_SUSPECT_POLICY in GC.FLOAT_SUSPECT_POLICIES
    assert GC.SCAN_UNKNOWN_TYPE_POLICY in GC.SCAN_UNKNOWN_TYPE_POLICIES


def test_decisions_k_numbers():
    assert (GC.K1_BODY_GAIN_PCT, GC.K1_RANGE_MULT, GC.K1_RANGE_LOOKBACK) == (3.0, 1.5, 20)
    assert (GC.K2_MAX_VOL_STEP, GC.K3_DEPTH_FRAC, GC.K3_VOL_FRAC) == (5.0, 0.50, 0.50)
    assert (GC.K4_HF_BASE_MIN, GC.K4_HF_BASE_MAX, GC.K4_VCP_MIN_CYCLES) == (6, 24, 2)
    assert (GC.K5_KISS_TOL_PCT, GC.K5_SLOPE_BARS) == (0.5, 3)
    assert (GC.K6_MERGE_PCT, GC.K6_TIGHT_PCT, GC.K6_SELL_DECAY) == (0.5, 8.0, 0.70)
    assert (GC.K7_CONTRACTION, GC.K7_EMA21_TOL_PCT) == (0.75, 0.5)
    assert (GC.K8_MAX_FLOAT, GC.K8_DROP_PCT, GC.K8_RECOVER_PCT, GC.K8_RECOVER_BARS) == (10_000_000, 8.0, 2.0, 3)
    assert (GC.K8_HISTORY_SESSIONS, GC.K8_HISTORY_RANGE_PCT) == (30, 50.0)
    assert (GC.K9_PM_MIN_VOLUME, GC.K9_AH_CARRY_PCT) == (1_000_000, 10.0)
    assert (GC.K10_CLOSE_TOP_FRAC, GC.K10_AH_MIN_VOLUME, GC.K10_AH_MIN_GAIN_PCT) == (0.30, 250_000, 5.0)
    assert (GC.SA_BIG_RUNNER_PCT, GC.SA_RUNNER_PCT, GC.SA_QUIET_BEST_PCT) == (100.0, 80.0, 40.0)
    assert GC.PSY_LEVELS == (1.0, 5.0, 10.0) and GC.NO_TRADE_AFTER_OPEN_MIN == 15
    assert (GC.BF_LEG_MIN_BARS, GC.KF_LEG_MIN_BARS) == (2, 1)


def test_every_number_carries_a_provenance_comment():
    tags = ("GG ", "Ajay ", "Cheetah default", "TRANSPORT", "derived", "spec default")
    missing = []
    for name, v, ln in _assigns():
        if _is_numeric(v):
            c = _comment(ln)
            if not c.startswith(tags):
                missing.append((name, c))
    assert missing == []


def test_NEGATIVE_cheetah_defaults_are_labelled_ajays_not_ggs():
    """DECISIONS round A: the 2-session stay and the 5% psych band are Ajay's numbers — never filed as GG's."""
    lines = {n: ln for n, _v, ln in _assigns()}
    for n in GC.CHEETAH_DEFAULTS:
        c = _comment(lines[n])
        assert c.startswith("Cheetah default") and "not GG" in c, (n, c)


def test_NEGATIVE_source_guard_imports_nothing_from_other_engines():
    for node in ast.walk(TREE):
        if isinstance(node, ast.ImportFrom):
            assert node.module == "orderflow.signals", node.module
            assert {a.name for a in node.names} == {"EMA_FAST", "EMA_SLOW"}
        if isinstance(node, ast.Import):
            for a in node.names:
                assert not a.name.startswith(("sepa", "supply_demand")), a.name


def test_NEGATIVE_no_bounce_word_and_no_other_board_names():
    low = SRC.lower()
    assert "bounce" not in low
    assert "minervini" not in low and "bonde" not in low and "is_candidate" not in low


@pytest.mark.parametrize("name", ["K8_FAIL_NEAR_PCT", "HF_LEG_MIN_BARS", "VCP_PIVOT_WINDOW", "RS_BASE_MIN_BARS"])
def test_NEGATIVE_a_reverted_placeholder_would_fail_the_guard(monkeypatch, name):
    """The guard itself bites: put one answer back to None and it reports it."""
    monkeypatch.setattr(GC, name, None)
    with pytest.raises(AssertionError):
        test_no_placeholder_left_until_ajay_answers()
