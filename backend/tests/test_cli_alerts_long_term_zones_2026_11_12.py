"""🔔 `sepa.cli alerts` carries the 📅 Long Term zone pass (pkzone spec §3.4, 2026-11-12).

Ajay 2026-11-12, verbatim: "add an alert list when stocks reach Pankaj's zones and also tell me if you finish the long
term tabs in general". ONE fenced call after pivot_alerts, before the heartbeat — no crontab edit. NEGATIVES: the 09-08
guard strings never return; a raising zone pass never blocks positions / price / pivot alerts or the heartbeat.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

CLI = Path(__file__).resolve().parents[1] / "sepa" / "cli.py"


def _alerts_branch() -> str:
    src = CLI.read_text(encoding="utf-8")
    i = src.index('if args.cmd == "alerts":')
    return src[i:src.index("return 0", i)]


def test_the_alerts_branch_calls_run_pass_inside_a_try():
    branch = _alerts_branch()
    assert "zone_watch.run_pass" in branch and "from long_term_list import zone_watch" in branch
    tree = ast.parse(CLI.read_text(encoding="utf-8"))
    tries = [n for n in ast.walk(tree) if isinstance(n, ast.Try)]
    assert any("zone_watch.run_pass" in ast.unparse(t) and t.handlers for t in tries)
    assert branch.index("pivot_alerts.check_pivot_alerts()") < branch.index("zone_watch.run_pass") \
        < branch.index('beat("alerts")')


def test_NEGATIVE_the_0908_guard_strings_never_return():
    src = CLI.read_text(encoding="utf-8")
    assert "pankaj_alerts" not in src and "check_pankaj_alerts" not in src
    assert not (CLI.parent / "pankaj_alerts.py").exists()
    assert "Remove all of" in _alerts_branch()                           # the 09-08 comment is kept


def test_NEGATIVE_a_raising_zone_pass_never_blocks_the_alerts_pass(monkeypatch):
    from market_hours import gate
    from observability import engine_heartbeat
    from sepa import alerts, cli, pivot_alerts, price_alerts
    from long_term_list import zone_watch
    calls = []
    monkeypatch.setattr(sys, "argv", ["sepa.cli", "alerts"])
    monkeypatch.setattr(gate, "closed_reason", lambda now=None: None)
    monkeypatch.setattr(alerts, "check_positions", lambda: calls.append("pos") or {"fired": [], "skipped": []})
    monkeypatch.setattr(price_alerts, "check_alerts", lambda: calls.append("price") or {"fired": 0, "checked": 0})
    monkeypatch.setattr(pivot_alerts, "check_pivot_alerts", lambda: calls.append("pivot") or {"fired": []})

    def _boom(*a, **k):
        calls.append("zones")
        raise RuntimeError("zone pass exploded")
    monkeypatch.setattr(zone_watch, "run_pass", _boom)
    monkeypatch.setattr(engine_heartbeat, "beat", lambda name="alerts": calls.append(f"beat:{name}"))
    assert cli.main() == 0
    assert calls == ["pos", "price", "pivot", "zones", "beat:alerts"]


def test_a_closed_day_skips_the_whole_branch(monkeypatch):
    from market_hours import gate
    from sepa import cli
    from long_term_list import zone_watch
    monkeypatch.setattr(sys, "argv", ["sepa.cli", "alerts"])
    monkeypatch.setattr(gate, "closed_reason", lambda now=None: "weekend")

    def _never(*a, **k):
        raise AssertionError("zone pass on a closed day")
    monkeypatch.setattr(zone_watch, "run_pass", _never)
    assert cli.main() == 0
