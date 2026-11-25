"""🔒 still on a Reg SHO list after its close-out day — `reg_sho.past_closeout_text` (sissr WP be-ssr-words, 2026-11-24).

Ajay 2026-11-24 ~23:35 ET: "Days past little bit like AKAN is what I am mainly looking for many were so confident on
SSR..". Spec: scratchpad sissr/spec.md §3.2. Every name is SYNTHETIC ("ZZ…").
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from datetime import date

import pytest

from short_interest import reg_sho as RS
from short_interest import reg_sho_runs as RUNS

RULE = RUNS.REG_SHO_CLOSEOUT_SETTLEMENT_DAYS


def _run_from_lists(on_days: int, window: int, *, ended: bool) -> dict:
    """A real `run_for` block: the name on the newest `on_days` lists; `ended` = the list before them is READ
    without it (else the window runs out with the name still on)."""
    days = RUNS.settlement_days_back(date(2026, 11, 25), window)
    mem = {}
    for i, d in enumerate(days):
        mem[d.isoformat()] = frozenset({"ZZPC"}) if i < on_days else frozenset({"ZZOTHER"})
    if not ended:
        mem = {k: frozenset({"ZZPC"}) for k in mem}
    return RUNS.run_for("ZZPC", days, mem)


# ═════════════════════════════════════════════ POSITIVE
def test_passed_19_is_day_6_past_close_out():
    assert RS.past_closeout_text({"state": "passed", "days": 19}) == "🔒 day 6 past close-out"


def test_passed_open_30_is_day_17_plus():
    assert RS.past_closeout_text({"state": "passed_open", "days": 30}) == "🔒 day 17+ past close-out"


def test_real_run_blocks_read_through_the_same_words():
    passed = _run_from_lists(19, 25, ended=True)
    assert passed["state"] == "passed" and passed["days"] == 19
    assert RS.past_closeout_text(passed) == "🔒 day 6 past close-out"
    open_ = _run_from_lists(30, 30, ended=False)
    assert open_["state"] == "passed_open" and open_["days"] == 30
    assert RS.past_closeout_text(open_) == "🔒 day 17+ past close-out"


def test_the_words_are_built_from_the_glyph_and_the_rule_word():
    assert RS.PAST_CLOSEOUT_TEXT == "%s day %d past %s"
    assert RS.PAST_CLOSEOUT_OPEN_TEXT == "%s day %d+ past %s"
    assert RS.past_closeout_text({"state": "passed", "days": RULE + 2}) == (
        RS.PAST_CLOSEOUT_TEXT % (RS.GLYPH, 2, RS.CLOSEOUT_WORD))


def test_the_constant_is_read_by_name_at_call_time(monkeypatch):
    monkeypatch.setattr(RUNS, "REG_SHO_CLOSEOUT_SETTLEMENT_DAYS", 12)
    assert RS.past_closeout_text({"state": "passed", "days": 19}) == "🔒 day 7 past close-out"
    assert RS.past_closeout_text({"state": "passed_open", "days": 30}) == "🔒 day 18+ past close-out"


# ═════════════════════════════════════════════ NEGATIVE
@pytest.mark.parametrize("state", ["counting", "reached", "unknown", "off", "", None, "PASSED", 3])
def test_NEGATIVE_every_other_state_is_none(state):
    assert RS.past_closeout_text({"state": state, "days": 19}) is None


def test_NEGATIVE_real_counting_reached_and_unknown_blocks_are_none():
    counting = _run_from_lists(4, 25, ended=True)
    reached = _run_from_lists(RULE, 25, ended=True)
    assert counting["state"] == "counting" and reached["state"] == "reached"
    for run in (counting, reached, RUNS.unknown_block()):
        assert RS.past_closeout_text(run) is None


@pytest.mark.parametrize("days", [None, "19", 19.0, float("nan"), float("inf"), True, False, [19], {"n": 19}])
def test_NEGATIVE_a_junk_day_count_is_none(days):
    assert RS.past_closeout_text({"state": "passed", "days": days}) is None
    assert RS.past_closeout_text({"state": "passed_open", "days": days}) is None


@pytest.mark.parametrize("days", [RULE, RULE - 1, 0, -5])
def test_NEGATIVE_no_day_past_the_close_out_is_none(days):
    assert RS.past_closeout_text({"state": "passed", "days": days}) is None
    assert RS.past_closeout_text({"state": "passed_open", "days": days}) is None


@pytest.mark.parametrize("run", [None, "passed", 19, [], ["passed", 19], {}, {"state": "passed"}, object()])
def test_NEGATIVE_a_junk_block_is_none_and_never_raises(run):
    assert RS.past_closeout_text(run) is None


def test_NEGATIVE_a_raising_block_is_none():
    class Boom(dict):
        def get(self, *a, **k):
            raise RuntimeError("synthetic")
    assert RS.past_closeout_text(Boom()) is None


def test_NEGATIVE_no_squeeze_no_earliest_no_bare_rule_number():
    src = inspect.getsource(RS.past_closeout_text)
    words = (RS.PAST_CLOSEOUT_TEXT + RS.PAST_CLOSEOUT_OPEN_TEXT + src).lower()
    for banned in ("squeeze", "earliest", "bounce", "predict"):
        assert banned not in words, banned
    tree = ast.parse(textwrap.dedent(src))
    nums = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
            and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)]
    assert RULE not in nums and all(v == 0 for v in nums), nums
    assert "13" not in RS.PAST_CLOSEOUT_TEXT and "13" not in RS.PAST_CLOSEOUT_OPEN_TEXT
