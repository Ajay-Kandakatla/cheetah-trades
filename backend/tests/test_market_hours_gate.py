"""Closed-day gate — Ajay 2026-09-07 (Labor Day): "TOday is holiday so turn of alerts scans."

Sixteen pivot alerts had pushed at 09:00 ET on a closed market, computed from
Friday's closes, because the crontab's Mon–Fri field cannot see a weekday
holiday. These tests pin ONE calendar feeding THREE chokepoints:
  1. market_hours.gate.closed_reason — weekend / holiday / open / override
  2. push.sender — market kinds dropped on a closed day before any device or
     push_history row; personal kinds still deliver
  3. jobs — sepa.cli MARKET_DAY_CMDS, the `python -m market_hours.gate` runner,
     and the crontab: every weekday price-reading module is wrapped
"""
from __future__ import annotations

import re
import sys
import types
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_hours import gate  # noqa: E402

LABOR_DAY = datetime(2026, 9, 7, 10, 0, tzinfo=gate._ET)     # Monday, NYSE closed
TUESDAY = datetime(2026, 9, 8, 10, 0, tzinfo=gate._ET)
SATURDAY = datetime(2026, 9, 5, 10, 0, tzinfo=gate._ET)


@pytest.fixture
def no_override(monkeypatch):
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)


@pytest.fixture
def labor_day(monkeypatch, no_override):
    monkeypatch.setattr(gate, "_now_et", lambda: LABOR_DAY)


@pytest.fixture
def tuesday(monkeypatch, no_override):
    monkeypatch.setattr(gate, "_now_et", lambda: TUESDAY)


# ── 1. calendar ───────────────────────────────────────────────────────────────
def test_labor_day_2026_is_closed(no_override):
    assert gate.closed_reason(LABOR_DAY) == "holiday 2026-09-07"


def test_the_next_trading_day_is_open(no_override):
    assert gate.closed_reason(TUESDAY) is None


def test_weekend_is_closed_even_when_not_a_holiday(no_override):
    assert gate.closed_reason(SATURDAY) == "weekend"


def test_override_env_lifts_the_gate_for_a_manual_run(monkeypatch):
    monkeypatch.setenv(gate.OVERRIDE_ENV, "1")
    assert gate.closed_reason(LABOR_DAY) is None
    assert gate.should_drop_kind("pivot_alert", LABOR_DAY) is None


def test_override_env_must_be_truthy(monkeypatch):
    monkeypatch.setenv(gate.OVERRIDE_ENV, "0")
    assert gate.closed_reason(LABOR_DAY) == "holiday 2026-09-07"


def test_clock_defaults_to_now_et(labor_day):
    assert gate.closed_reason() == "holiday 2026-09-07"


# ── kinds ─────────────────────────────────────────────────────────────────────
def test_market_kinds_drop_and_personal_kinds_pass_on_a_closed_day(no_override):
    for k in gate.MARKET_ALERT_KINDS:
        assert gate.should_drop_kind(k, LABOR_DAY) == "holiday 2026-09-07", k
    for k in gate.PERSONAL_KINDS:
        assert gate.should_drop_kind(k, LABOR_DAY) is None, k
    assert gate.should_drop_kind(None, LABOR_DAY) is None          # untyped broadcast


def test_unknown_kind_is_treated_as_market_driven(no_override):
    """Default DROP: a new setup_* / pattern kind must not slip through on a holiday."""
    assert gate.should_drop_kind("setup_bull_flag", LABOR_DAY) == "holiday 2026-09-07"
    assert gate.should_drop_kind("setup_bull_flag", TUESDAY) is None


def test_personal_and_market_sets_are_disjoint_and_cover_default_prefs():
    from push import subs
    assert not (gate.PERSONAL_KINDS & gate.MARKET_ALERT_KINDS)
    kinds = {k for k in subs.default_prefs() if not k.startswith("quiet_hours")}   # prefs, not kinds
    unclassified = kinds - gate.PERSONAL_KINDS - gate.MARKET_ALERT_KINDS
    assert not unclassified, f"classify these in market_hours.gate: {sorted(unclassified)}"


def test_the_three_phone_kinds_are_market_kinds():
    assert {"pivot_alert", "position_alert", "todo_reminder"} & (
        gate.MARKET_ALERT_KINDS | gate.PERSONAL_KINDS) == {"pivot_alert", "position_alert", "todo_reminder"}
    assert "todo_reminder" in gate.PERSONAL_KINDS
    assert {"pivot_alert", "position_alert"} <= gate.MARKET_ALERT_KINDS


# ── 2. push chokepoint ────────────────────────────────────────────────────────
@pytest.fixture
def push_stack(monkeypatch):
    from push import sender, subs, history
    sent, recorded = [], []
    monkeypatch.setattr(subs, "list_subscriptions",
                        lambda *a, **k: [{"endpoint": "e1", "keys": {}}])
    monkeypatch.setattr(sender, "_send_one", lambda sub, payload: sent.append(payload) or True)
    monkeypatch.setattr(history, "record", lambda payload, **k: recorded.append(payload))
    return sender, sent, recorded


def test_sender_drops_a_market_kind_on_labor_day_before_device_and_history(labor_day, push_stack):
    sender, sent, recorded = push_stack
    out = sender.send_to_all({"title": "🟢 At the pivot: OGN"}, kind="pivot_alert")
    assert out == {"sent": 0, "failed": 0, "total_targets": 0, "skipped": "holiday 2026-09-07"}
    assert sent == [] and recorded == []


def test_send_to_user_drops_a_market_kind_too(labor_day, push_stack):
    sender, sent, recorded = push_stack
    out = sender.send_to_user("ajaykandakatla@gmail.com", {"title": "stop hit"}, kind="position_alert")
    assert out["skipped"] == "holiday 2026-09-07" and sent == [] and recorded == []


def test_sender_still_delivers_a_todo_reminder_on_labor_day(labor_day, push_stack):
    sender, sent, recorded = push_stack
    out = sender.send_to_user("gandurivineetha@gmail.com", {"title": "💧 Hydrate"}, kind="todo_reminder")
    assert out["sent"] == 1 and len(sent) == 1 and len(recorded) == 1


def test_sender_delivers_the_market_kind_on_a_trading_day(tuesday, push_stack):
    sender, sent, recorded = push_stack
    out = sender.send_to_all({"title": "🟢 At the pivot: OGN"}, kind="pivot_alert")
    assert out["sent"] == 1 and len(sent) == 1 and len(recorded) == 1


# ── 3. jobs ───────────────────────────────────────────────────────────────────
def test_cli_market_commands_are_gated_at_dispatch():
    from sepa import cli
    src = (ROOT / "sepa" / "cli.py").read_text()
    for cmd in ("alerts", "fast-scan", "scan", "brief", "trade-flash-watch",
                "scalping-watch", "pullback-scan", "breakout-audit", "zero-dte-record"):
        assert cmd in cli.MARKET_DAY_CMDS, cmd
    for cmd in ("research-refresh", "fear-greed-refresh", "macro-indicators-refresh", "scan-context"):
        assert cmd not in cli.MARKET_DAY_CMDS, cmd            # not price reads
    i_parse = src.index("args = p.parse_args()")
    i_gate = src.index("gate.closed_reason()")
    i_first = src.index('if args.cmd == "breakout-audit"')
    assert i_parse < i_gate < i_first, "the gate must sit between parse_args and the first dispatch"


def test_cli_alerts_returns_without_running_on_labor_day(labor_day, monkeypatch):
    from sepa import cli
    fake = types.ModuleType("sepa.alerts")

    def boom():
        raise AssertionError("alerts ran on a holiday")
    fake.check_positions = boom
    monkeypatch.setitem(sys.modules, "sepa.alerts", fake)
    monkeypatch.setattr(sys, "argv", ["cli", "alerts"])
    assert cli.main() == 0


def test_runner_skips_the_module_on_labor_day_and_runs_it_on_tuesday(monkeypatch, tmp_path, no_override):
    mod = tmp_path / "gate_probe_mod.py"
    mod.write_text("import sys, pathlib\n"
                   "pathlib.Path(sys.argv[0]).with_suffix('.ran').write_text(' '.join(sys.argv[1:]))\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    marker = tmp_path / "gate_probe_mod.ran"
    monkeypatch.setattr(gate, "_now_et", lambda: LABOR_DAY)
    assert gate.main(["gate_probe_mod", "--warm"]) == 0
    assert not marker.exists()
    monkeypatch.setattr(gate, "_now_et", lambda: TUESDAY)
    assert gate.main(["gate_probe_mod", "--warm"]) == 0
    assert marker.exists() and marker.read_text() == "--warm"


def test_runner_call_form(monkeypatch, tmp_path, no_override):
    mod = tmp_path / "gate_probe_call.py"
    mod.write_text("HITS = []\ndef go():\n    HITS.append(1)\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(gate, "_now_et", lambda: LABOR_DAY)
    assert gate.main(["--call", "gate_probe_call:go"]) == 0
    import importlib
    probe = importlib.import_module("gate_probe_call")
    assert probe.HITS == []
    monkeypatch.setattr(gate, "_now_et", lambda: TUESDAY)
    assert gate.main(["--call", "gate_probe_call:go"]) == 0
    assert probe.HITS == [1]


def test_runner_usage_errors_do_not_exit_zero(tuesday):
    assert gate.main([]) == 2
    assert gate.main(["--call", "no_colon"]) == 2


WRAPPED = ("trading.autopsy", "trading.catalyst_entry", "supply_demand.zone_store",
           "ict.engine", "options.scanner", "options.gex_history",
           "catalysts.gabbar_watch", "supply_demand.demand_alerts")
NOT_WRAPPED = ("sepa.cli",)                    # gates itself via MARKET_DAY_CMDS


def _weekday_jobs():
    for line in (ROOT / "crontab").read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.split(None, 5)
        if len(fields) == 6 and fields[4] == "1-5":
            yield fields[5]


def test_every_weekday_price_reading_cron_job_runs_through_the_gate():
    jobs = list(_weekday_jobs())
    assert len(jobs) >= 30
    for m in WRAPPED:
        hits = [j for j in jobs if re.search(r"(?<![\w.])" + re.escape(m) + r"\b", j)]
        assert hits, m
        for j in hits:
            assert f"-m market_hours.gate {m}" in j, j
    for m in NOT_WRAPPED:
        for j in (j for j in jobs if f"-m {m}" in j):
            assert "market_hours.gate" not in j, j
    drop = [j for j in jobs if "run_drop_attribution_default" in j]
    assert drop and all("market_hours.gate --call portfolio.alerts:run_drop_attribution_default" in j
                        for j in drop)
    assert not any('-c "from portfolio.alerts' in j for j in jobs)


def test_crontab_never_sets_the_override():
    jobs = [l for l in (ROOT / "crontab").read_text().splitlines()
            if l.strip() and not l.lstrip().startswith("#")]
    assert not any(gate.OVERRIDE_ENV in l for l in jobs)      # comments may mention it


def test_rules_panel_prints_the_closed_day_line(labor_day):
    from supply_demand import rules_info
    picks = rules_info.sections()["alerts"]["picks"]
    line = [p for p in picks if p.startswith("Closed days")]
    assert len(line) == 1 and "2026-09-07" in line[0] and "still deliver" in line[0]
