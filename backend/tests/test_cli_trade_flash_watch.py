"""🎚️ `sepa.cli trade-flash-watch` — the tape_control hook (AMENDMENTS7 A1 / A5, 2026-10-16).

Ajay 2026-10-16: "I wwant you to alert me when the Buyers are winning in tape for IREN today."

The hook runs in the cli AFTER trade_flash.run_watch and its heartbeat loop
(trade_flash + each burst kind that ran), in its own try; it beats
`tape_control` only when run_pass says `ran: True`. Hermetic: run_watch and
run_pass are doubles unless a test says otherwise. NEGATIVES marked.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from orderflow import tape_control as TC
from orderflow import trade_flash as TF

ET = ZoneInfo("America/New_York")
NOW = datetime(2026, 10, 16, 10, 2, tzinfo=ET)
KINDS_RAN = {"tape_burst_highbeta": {"ran": True}, "tape_burst_chartmaps": {"ran": True}}
THREE_BEATS = ["trade_flash", "tape_burst_highbeta", "tape_burst_chartmaps"]
REAL_RUN_PASS = TC.run_pass


@pytest.fixture
def env(monkeypatch):
    from market_hours import gate
    from observability import engine_heartbeat
    from sepa import cli

    class E:
        log = []
        beats = []
        rp_calls = []
        watch_result = {"ok": True, "new": 0, "kinds": dict(KINDS_RAN)}
        rp_result = {"ran": True, "pins": 1, "active": 1, "read": 1}
        rp_raise = None

    e = E()

    def stub_watch(**kw):
        e.log.append("run_watch")
        return json.loads(json.dumps(e.watch_result))

    def stub_beat(name="alerts"):
        e.log.append("beat:" + name)
        e.beats.append(name)

    def stub_run_pass(**kw):
        e.log.append("run_pass")
        e.rp_calls.append(kw)
        if e.rp_raise is not None:
            raise e.rp_raise
        return dict(e.rp_result)

    monkeypatch.setattr(gate, "closed_reason", lambda *a, **k: None)
    monkeypatch.setattr(engine_heartbeat, "beat", stub_beat)
    monkeypatch.setattr(TF, "_now_et", lambda: NOW)
    monkeypatch.setattr(TF, "run_watch", stub_watch)
    monkeypatch.setattr(TC, "run_pass", stub_run_pass)
    e.cli = cli
    return e


def _run(e, monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["sepa.cli", "trade-flash-watch", *args])
    return e.cli.main()


def test_run_pass_is_called_after_the_beats_and_beats_its_own_name(env, monkeypatch):
    assert _run(env, monkeypatch) == 0
    assert env.log == ["run_watch"] + ["beat:" + b for b in THREE_BEATS] + ["run_pass", "beat:tape_control"]
    kw = env.rp_calls[0]
    assert kw["now"] == NOW and kw["dry_run"] is False
    assert isinstance(kw["poll_ts"], int) and isinstance(kw["started"], float)


def test_it_still_runs_when_the_burst_kinds_failed_to_prepare(env, monkeypatch):
    env.watch_result = {"ok": True, "new": 0, "kinds_error": "prepare failed"}
    assert _run(env, monkeypatch) == 0
    assert env.log == ["run_watch", "beat:trade_flash", "run_pass", "beat:tape_control"]


def test_NEGATIVE_a_raising_run_pass_leaves_the_three_beats_and_the_exit_code(env, monkeypatch):
    env.rp_raise = RuntimeError("tape_control blew up")
    assert _run(env, monkeypatch) == 0
    assert env.beats == THREE_BEATS, "the three beats are written; tape_control's is not"
    assert env.log.index("run_pass") > env.log.index("beat:tape_burst_chartmaps")


def test_NEGATIVE_a_pass_that_did_not_run_beats_nothing(env, monkeypatch):
    env.rp_result = {"ran": False, "pins": 1, "active": 1, "read": 0, "faults": 1,
                     "reason": TC.FAULT_WORDS["no_prints"]}
    assert _run(env, monkeypatch) == 0
    assert env.beats == THREE_BEATS and "tape_control" not in env.beats


def test_NEGATIVE_a_truthy_non_True_ran_beats_nothing(env, monkeypatch):
    env.rp_result = {"ran": "yes"}
    assert _run(env, monkeypatch) == 0
    assert "tape_control" not in env.beats


def test_NEGATIVE_a_broken_import_never_touches_the_beats(env, monkeypatch):
    monkeypatch.setitem(sys.modules, "orderflow.tape_control", None)
    import orderflow
    monkeypatch.delattr(orderflow, "tape_control", raising=False)
    assert _run(env, monkeypatch) == 0
    assert env.beats == THREE_BEATS and env.rp_calls == []


def test_NEGATIVE_kinds_highbeta_alone_skips_it(env, monkeypatch):
    assert _run(env, monkeypatch, "--kinds", "tape_burst_highbeta") == 0
    assert env.rp_calls == [] and "tape_control" not in env.beats


@pytest.mark.parametrize("kinds", ["tape_control", "tape_burst_highbeta,tape_control", "all"])
def test_kinds_naming_it_runs_it(env, monkeypatch, kinds):
    assert _run(env, monkeypatch, "--kinds", kinds) == 0
    assert len(env.rp_calls) == 1 and env.beats[-1] == "tape_control"


def test_dry_run_reaches_it_as_dry_run_true_and_beats_nothing(env, monkeypatch, capsys):
    env.rp_result = {"ran": True, "dry_run": True, "would_push": 0, "reads": []}
    assert _run(env, monkeypatch, "--dry-run") == 0
    assert len(env.rp_calls) == 1 and env.rp_calls[0]["dry_run"] is True
    assert env.beats == [], "NEGATIVE: a dry run beats nothing"
    out = json.loads(capsys.readouterr().out)
    assert out["tape_control"]["dry_run"] is True


def test_NEGATIVE_a_closed_day_never_reaches_it(env, monkeypatch):
    from market_hours import gate
    monkeypatch.setattr(gate, "closed_reason", lambda *a, **k: "holiday 2026-11-26")
    assert _run(env, monkeypatch) == 0
    assert env.log == [] and env.rp_calls == []


@pytest.mark.parametrize("now", [
    datetime(2026, 10, 16, 9, 31, tzinfo=ET),
    datetime(2026, 10, 16, 16, 0, tzinfo=ET),
    datetime(2026, 10, 17, 11, 0, tzinfo=ET),      # Saturday
])
def test_NEGATIVE_outside_the_window_the_real_pass_never_reads(env, monkeypatch, now):
    """The REAL run_pass behind the cli: outside 09:32–16:00 ET it reads no
    tape, opens no state store, and beats nothing."""
    real = TC
    monkeypatch.setattr(TC, "run_pass", REAL_RUN_PASS)
    monkeypatch.setattr(TF, "_now_et", lambda: now)
    monkeypatch.setattr(real, "WATCH", {"IREN": None})
    touched = []
    monkeypatch.setattr(real, "read_tape", lambda *a, **k: touched.append("read") or (None, "error"))
    monkeypatch.setattr(TF, "_db", lambda: touched.append("db"))
    env.watch_result = {"ok": True, "skipped": "market closed"}
    assert _run(env, monkeypatch) == 0
    assert touched == [] and "tape_control" not in env.beats


def test_inside_the_window_the_real_pass_reads_once(env, monkeypatch):
    real = TC
    monkeypatch.setattr(TC, "run_pass", REAL_RUN_PASS)
    monkeypatch.setattr(TF, "_now_et", lambda: datetime(2026, 10, 16, 9, 32, tzinfo=ET))
    monkeypatch.setattr(real, "WATCH", {"IREN": None})
    touched = []

    class Coll:
        def find_one(self, q):
            return None

    class DB:
        def __getitem__(self, name):
            return Coll()
    monkeypatch.setattr(real, "read_tape", lambda *a, **k: touched.append("read") or (None, "error"))
    monkeypatch.setattr(TF, "_db", lambda: DB())
    monkeypatch.setattr(real, "_claim", lambda *a, **k: (True, 1, None))
    from supply_demand import alert_status as AS
    monkeypatch.setattr(AS, "record_pass", lambda *a, **k: True)
    assert _run(env, monkeypatch) == 0
    assert touched == ["read"]
    assert "tape_control" not in env.beats, "NEGATIVE: an all-fault poll beats nothing (A5)"
