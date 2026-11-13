"""📅 Long Term — the after-scan hook, eligibility and the detached spawn (spec §3.9, WP-RUN, 2026-11-12).

Ajay 2026-11-12, verbatim: "… keep updating it from all the other tabs info.. Weekly …"

`context_refresh.after_scan` returns exactly what it returned before; the hook is fenced; a pytest run never starts a
process; the eligibility read never touches Mongo. NEGATIVES throughout.
"""
from __future__ import annotations

import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from long_term_list import constants as C
from long_term_list import weekly as WK
from sepa import context_refresh as MC

ET = ZoneInfo("America/New_York")
SUMMARY = {"parts": {"vix": {"ok": True, "sec": 1.0}}, "ok": True}


def _at(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=ET)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(C.ENV_SWITCH, raising=False)
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


@pytest.fixture()
def no_mongo(monkeypatch):
    from sepa import prices

    def _boom(*a, **k):
        raise AssertionError("the hook touched Mongo")
    monkeypatch.setattr(prices, "_get_mongo", _boom)
    monkeypatch.setattr(WK.ST, "_db", _boom)
    monkeypatch.setattr(WK.ST, "colls", _boom)


# ── eligibility ───────────────────────────────────────────────────────────────────────────────────────────────
def test_friday_before_and_after_the_rerate():
    assert WK.eligible(_at(2026, 11, 13, 16, 29)).startswith("before 4:30 PM ET")
    assert WK.eligible(_at(2026, 11, 13, 16, 30)) is None


def test_a_normal_thursday_is_not_the_last_day():
    assert WK.eligible(_at(2026, 11, 12, 17, 0)) == WK.R_NOT_LAST


def test_the_thursday_before_good_friday_is_the_last_day():
    assert WK.is_last_trading_day("2027-03-25") is True
    assert WK.eligible(_at(2027, 3, 25, 16, 45)) is None
    assert WK.eligible(_at(2027, 3, 26, 16, 45)).startswith("holiday")


def test_saturday_and_holiday_are_closed():
    assert WK.eligible(_at(2026, 11, 14, 17, 0)) == "weekend"
    assert WK.eligible(_at(2026, 11, 26, 17, 0)).startswith("holiday")
    assert WK.is_last_trading_day("2026-11-27") is True             # Thanksgiving week: the Friday after


def test_env_off(monkeypatch):
    monkeypatch.setenv(C.ENV_SWITCH, "0")
    assert WK.eligible(_at(2026, 11, 13, 16, 30)) == WK.R_OFF
    assert WK.eligible(_at(2026, 11, 13, 16, 30), force=True) == WK.R_OFF


def test_override_on_saturday_without_force_is_refused(monkeypatch):
    monkeypatch.setenv("CHEETAH_IGNORE_HOLIDAY", "1")
    assert WK.eligible(_at(2026, 11, 14, 17, 0)) == WK.R_OVERRIDE   # NEG
    assert WK.eligible(_at(2026, 11, 14, 17, 0), force=True) is None


def test_session_for():
    assert WK.session_for(_at(2026, 11, 13, 16, 31)) == "2026-11-13"
    assert WK.session_for(_at(2026, 11, 13, 16, 29)) == "2026-11-12"
    assert WK.session_for(_at(2026, 11, 14, 10, 0)) == "2026-11-13"
    assert WK.session_for(_at(2026, 11, 27, 9, 0)) == "2026-11-25"   # Thanksgiving skipped


# ── the spawn ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_injected_spawn_gets_the_child_argv(monkeypatch, no_mongo):
    monkeypatch.setattr(WK, "_now", lambda: _at(2026, 11, 13, 16, 35))
    got = []
    assert WK.spawn_after_scan("fast-scan", spawn=lambda argv, name: got.append((argv, name))) is True
    assert got == [([sys.executable, "-m", "long_term_list.weekly", "--after-scan", "fast-scan"], C.CHILD_NAME)]
    assert C.CHILD_ARGV_MODULE == "long_term_list.weekly"


def test_not_eligible_day_never_calls_spawn(monkeypatch, no_mongo):
    monkeypatch.setattr(WK, "_now", lambda: _at(2026, 11, 12, 16, 35))
    got = []
    assert WK.spawn_after_scan("fast-scan", spawn=lambda argv, name: got.append(argv)) is False
    assert got == []


def test_pytest_without_injected_spawn_starts_no_process(monkeypatch, no_mongo):
    monkeypatch.setattr(WK, "_now", lambda: _at(2026, 11, 13, 16, 35))
    import subprocess

    def _no(*a, **k):
        raise AssertionError("a real process was started")
    monkeypatch.setattr(subprocess, "Popen", _no)
    assert WK.spawn_after_scan("fast-scan") is False


def test_a_raising_spawn_is_false(monkeypatch, no_mongo):
    monkeypatch.setattr(WK, "_now", lambda: _at(2026, 11, 13, 16, 35))

    def _raise(argv, name):
        raise OSError("fork failed")
    assert WK.spawn_after_scan("scan", spawn=_raise) is False


# ── the hook inside after_scan ────────────────────────────────────────────────────────────────────────────────
def test_after_scan_return_value_is_unchanged(monkeypatch, no_mongo):
    monkeypatch.setattr(MC, "refresh_all", lambda **kw: SUMMARY)
    seen = []
    monkeypatch.setattr(WK, "spawn_after_scan", lambda kind, spawn=None: seen.append(kind) or True)
    assert MC.after_scan("fast-scan") is SUMMARY
    assert seen == ["fast-scan"]


def test_a_raising_hook_is_swallowed(monkeypatch):
    monkeypatch.setattr(MC, "refresh_all", lambda **kw: SUMMARY)

    def _boom(kind, spawn=None):
        raise RuntimeError("hook exploded")
    monkeypatch.setattr(WK, "spawn_after_scan", _boom)
    assert MC.after_scan("scan") is SUMMARY


def test_after_scan_on_an_ineligible_day_spawns_nothing(monkeypatch, no_mongo):
    monkeypatch.setattr(MC, "refresh_all", lambda **kw: SUMMARY)
    monkeypatch.setattr(WK, "_now", lambda: _at(2026, 11, 11, 16, 35))
    import subprocess

    def _no(*a, **k):
        raise AssertionError("spawned")
    monkeypatch.setattr(subprocess, "Popen", _no)
    assert MC.after_scan("fast-scan") is SUMMARY


def test_hook_source_sits_after_the_log_line_before_return():
    import inspect
    src = inspect.getsource(MC.after_scan)
    assert src.index("SCAN CONTEXT after") < src.index("_long_term_hook(kind)") < src.index("return s")
