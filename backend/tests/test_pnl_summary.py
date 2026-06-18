"""Auto-Pilot account P&L summary (Ajay 2026-06-18: "I can't tell if we made
money … how much did we enter with"). exit_engine.pnl_summary is a pure roll-up:
started-with vs equity now, split into invested / unrealized / realized.

Loaded standalone (importlib) so the test doesn't drag in the broker/Mongo stack
on py3.9.

  cd backend && .venv/bin/python -m pytest tests/test_pnl_summary.py -q
"""
import importlib.util
import os

_PATH = os.path.join(os.path.dirname(__file__), "..", "trading", "exit_engine.py")


def _load():
    # exit_engine imports the broker package at module load; if that stack isn't
    # importable here, fall back to executing just the pnl_summary source.
    try:
        spec = importlib.util.spec_from_file_location("exit_engine_mod", _PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.pnl_summary
    except Exception:
        ns = {}
        src = open(_PATH).read()
        start = src.index("def pnl_summary(")
        end = src.index("\n\n", src.index("return {", start))
        exec("from typing import Optional\n" + src[start:end + 1], ns)
        return ns["pnl_summary"]


pnl_summary = _load()


def test_open_position_up_is_all_unrealized():
    acct = {"starting_cash": 10000, "equity": 10500, "cash": 2000}
    s = pnl_summary(acct, [{"qty": 100, "avg_entry": 80.0, "last": 85.0}])
    assert s["starting_cash"] == 10000
    assert s["invested"] == 8000 and s["market_value"] == 8500
    assert s["unrealized_dollars"] == 500
    assert s["total_pnl_dollars"] == 500 and s["total_pnl_pct"] == 5.0
    assert s["realized_dollars"] == 0          # nothing closed yet


def test_booked_gain_shows_as_realized():
    # +$300 realized (reflected in cash/equity), one open position sitting flat
    acct = {"starting_cash": 10000, "equity": 10300, "cash": 2300}
    s = pnl_summary(acct, [{"qty": 100, "avg_entry": 80.0, "last": 80.0}])
    assert s["unrealized_dollars"] == 0
    assert s["total_pnl_dollars"] == 300 and s["realized_dollars"] == 300


def test_all_cash_no_positions():
    s = pnl_summary({"starting_cash": 10000, "equity": 10200, "cash": 10200}, [])
    assert s["invested"] == 0 and s["market_value"] == 0 and s["position_count"] == 0
    assert s["total_pnl_dollars"] == 200 and s["realized_dollars"] == 200


def test_loss_is_negative():
    s = pnl_summary({"starting_cash": 10000, "equity": 9400, "cash": 1000},
                    [{"qty": 100, "avg_entry": 90.0, "last": 84.0}])
    assert s["total_pnl_dollars"] == -600 and s["total_pnl_pct"] == -6.0
    assert s["unrealized_dollars"] == -600    # market 8400 vs cost 9000


def test_missing_starting_cash_is_none_not_crash():
    s = pnl_summary({"equity": 100, "cash": 100}, [])
    assert s["starting_cash"] == 0
    assert s["total_pnl_dollars"] is None and s["total_pnl_pct"] is None
