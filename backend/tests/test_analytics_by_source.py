"""Auto-Pilot analytics by_source split (Ajay 2026-06-19: "track your accuracy
in parallel … continue your previous rodeo"). The combined batting/expectancy
stays the CONTINUOUS track record across the sim -> paper cutover; by_source
breaks it into sim vs live-paper so the dashboard can watch paper accuracy
accrue separately. Fills predating the cutover carry no `mode` and must bucket
as sim.

  cd backend && .venv/bin/python -m pytest tests/test_analytics_by_source.py -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _trade(sym, epoch, gain_pct, mode):
    entry = {"epoch": float(epoch), "price": 100.0, "qty": 1, "stop_pct": 7.0,
             "trigger": None}
    if mode is not None:
        entry["mode"] = mode
    return {"trade_id": "%s-%d" % (sym, epoch), "symbol": sym, "status": "closed",
            "entry": entry,
            "exit": {"epoch": float(epoch + 86400),
                     "price": 100.0 * (1 + gain_pct / 100.0), "leg": "stop"},
            "realized": {"gain_pct": gain_pct, "gain_dollars": round(gain_pct, 2),
                         "r_multiple": round(gain_pct / 7.0, 2),
                         "holding_days": 1.0, "exit_reason": "x"}}


def test_by_source_splits_sim_and_paper():
    from trading import analytics as an
    trades = [
        _trade("A", 1, 10.0, "sim"),
        _trade("B", 2, -5.0, "sim"),
        _trade("C", 3, 12.0, "paper"),
        _trade("D", 4, -4.0, "paper"),
    ]
    a = an.compute(trades)
    assert set(a["by_source"]) == {"sim", "paper"}
    assert a["by_source"]["sim"]["n"] == 2
    assert a["by_source"]["paper"]["n"] == 2
    # Combined stays the continuous record across both venues.
    assert a["n_closed"] == 4


def test_missing_mode_buckets_as_sim():
    from trading import analytics as an
    # Pre-cutover fills (mode=None) + one explicit paper fill.
    trades = [_trade("A", 1, 8.0, None), _trade("B", 2, -3.0, None),
              _trade("C", 3, 9.0, "paper")]
    a = an.compute(trades)
    assert a["by_source"]["sim"]["n"] == 2        # both None -> sim
    assert a["by_source"]["paper"]["n"] == 1


def test_empty_has_empty_by_source():
    from trading import analytics as an
    a = an.compute([])
    assert a["by_source"] == {}


def test_by_source_stats_are_per_bucket():
    from trading import analytics as an
    # paper: one +14 winner only -> batting 1.0; sim: one -7 loser -> batting 0.
    trades = [_trade("P", 1, 14.0, "paper"), _trade("S", 2, -7.0, "sim")]
    a = an.compute(trades)
    assert a["by_source"]["paper"]["batting_avg"] == 1.0
    assert a["by_source"]["sim"]["batting_avg"] == 0.0
