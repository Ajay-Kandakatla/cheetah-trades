"""📅 Long Term (2026-11-12 refix) — a fundamental ⚠️ survives an unread week.

pass → unknown (one missing read) → fail must raise exactly one 'fundamental'
event: when last week's verdict is not pass/fail the last known verdict
(flags["leg_last_known"], else the at-save verdict) stands in for it."""
from __future__ import annotations

from long_term_list import notices as N
from tests.test_long_term_list_notices import _now, _save, _session, kinds, run_weeks, all_kinds

CQ = ["capital_quality"]


def _roe(v):
    return _now(CQ, 2, over={"capital_quality": {"roe_pct": v}})


def test_pass_unknown_fail_is_one_fundamental_event():
    w, flags = run_weeks("MA", CQ, _save(CQ, 2), [_roe(25.0), _roe(None), _roe(18.0), _roe(18.0)])
    assert [kinds(e) for e in w] == [[], [], ["fundamental"], []]
    assert w[2][0]["rings"] is False and "ROE 18.0%" in w[2][0]["text"]
    assert flags["fundamental_failing"] == ["capital_quality"]
    assert N.section_for(flags, _roe(18.0), _session(3)) == "changed"


def test_save_pass_then_unknown_then_fail_uses_the_save_verdict():
    w, flags = run_weeks("MA", CQ, _save(CQ, 2), [_roe(None), _roe(18.0)])
    assert [kinds(e) for e in w] == [[], ["fundamental"]]
    assert flags["fundamental_failing"] == ["capital_quality"]


def test_pass_two_unknown_weeks_then_fail_still_fires_once():
    w, _ = run_weeks("MA", CQ, _save(CQ, 2), [_roe(None), _roe(None), _roe(18.0), _roe(None), _roe(18.0)])
    assert all_kinds(w) == ["fundamental"] and kinds(w[2]) == ["fundamental"]


def test_negative_fail_unknown_fail_never_a_second_event():
    w, flags = run_weeks("MA", CQ, _save(CQ, 2), [_roe(18.0), _roe(None), _roe(18.0)])
    assert [kinds(e) for e in w] == [["fundamental"], [], []]
    assert flags["fundamental_failing"] == ["capital_quality"]


def test_negative_saved_fail_unknown_fail_never_fires():
    save = _save(CQ, 2, over={"capital_quality": {"roe_pct": 18.0}})
    w, flags = run_weeks("MA", CQ, save, [_roe(None), _roe(18.0)])
    assert all_kinds(w) == [] and flags["fundamental_failing"] == []


def test_negative_saved_fail_then_pass_unknown_fail_fires_on_last_known_not_save():
    save = _save(CQ, 2, over={"capital_quality": {"roe_pct": 18.0}})
    w, _ = run_weeks("MA", CQ, save, [_roe(25.0), _roe(None), _roe(18.0)])
    assert [kinds(e) for e in w] == [[], [], ["fundamental"]]


def test_negative_pass_unknown_pass_no_event_and_holding():
    w, flags = run_weeks("MA", CQ, _save(CQ, 2), [_roe(None), _roe(25.0)])
    assert all_kinds(w) == [] and flags["fundamental_failing"] == []
    assert N.section_for(flags, _roe(25.0), _session(1)) == "holding"


def test_negative_unknown_is_never_fail_and_never_overwrites_last_known():
    w, flags = run_weeks("MA", CQ, _save(CQ, 2), [_roe(25.0), _roe(None)])
    assert all_kinds(w) == [] and flags["fundamental_failing"] == []
    assert flags["leg_last_known"]["capital_quality"]["roe"] == "pass"


def test_initial_flags_carry_no_last_known_key():
    assert "leg_last_known" not in N.initial_flags({"stage": 2})
