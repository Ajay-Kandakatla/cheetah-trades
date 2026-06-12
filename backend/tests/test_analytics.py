"""Trade ANALYTICS — pure compute over closed journal docs, no I/O.

Locks trading/analytics.py (docs/sepa/journal_analytics_methodology.md):
every metric is Minervini's own (TLSW Ch.13, page-cited in the module):
  batting average (p.298), avg gain / avg loss (p.299), win/loss ratio +
  2:1/3:1 targets (p.301), expectancy % and $ (p.298), realized R, equity
  curve, by-trigger breakdown, half-average-gain stop (p.299), the CARDINAL
  SIN flag (p.299, avg_loss > avg_gain), and the provisional small-sample
  label (< MIN_RECORD_N closed trades).

The closed set under test (matches test_journal.py's seeded round-trips):
  AAA +15.02% (stop 7%),  BBB -7.0% (stop 7%),  DDD +4.4% (stop 7%).
  winners [15.02, 4.4] -> avg_gain 9.71; losers [-7.0] -> avg_loss 7.0;
  batting 2/3; win/loss 9.71/7.0 = 1.39 (< 2:1 floor -> p.301 flag).

Host-runnable (py3.9, no pandas/numpy):
    cd backend && .venv/bin/python -m pytest tests/test_analytics.py -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trading import analytics as AN


def _trade(symbol, epoch, gain_pct, stop_pct, qty, entry_price, exit_price,
           holding_days, trigger_path=None):
    """A closed journal doc shaped like journal.reconcile() emits."""
    gain_dollars = round(qty * (exit_price - entry_price), 2)
    r_multiple = round(gain_pct / stop_pct, 2) if stop_pct else None
    trig = ({"path": trigger_path, "pivot": entry_price - 1, "relvol": 1.6,
             "score": 80, "cleared_at_frac": 0.2}
            if trigger_path else None)
    return {
        "trade_id": "%s-%d" % (symbol, epoch),
        "symbol": symbol, "status": "closed",
        "entry": {"epoch": float(epoch), "price": entry_price, "qty": qty,
                  "stop_pct": stop_pct, "trigger": trig},
        "exit": {"epoch": float(epoch + holding_days * 86400),
                 "price": exit_price, "leg": "take_profit"},
        "realized": {"gain_pct": gain_pct, "gain_dollars": gain_dollars,
                     "r_multiple": r_multiple, "holding_days": holding_days,
                     "exit_reason": "take-profit"},
    }


@pytest.fixture
def closed_set():
    return [
        _trade("AAA", 1000, 15.02, 7.0, 12, 182.40, 209.80, 4.0,
               trigger_path="intraday"),
        _trade("BBB", 2000, -7.0, 7.0, 10, 50.0, 46.50, 2.0),     # manual
        _trade("DDD", 3000, 4.4, 7.0, 8, 75.0, 78.30, 1.0),       # manual
    ]


# ── Core ratios ──────────────────────────────────────────────────────────────

def test_batting_avg_gain_loss_win_loss(closed_set):
    a = AN.compute(closed_set)
    assert a["n_closed"] == 3
    assert a["batting_avg"] == pytest.approx(2 / 3, abs=1e-3)
    assert a["avg_gain_pct"] == pytest.approx(9.71, abs=0.01)     # (15.02+4.4)/2
    assert a["avg_loss_pct"] == pytest.approx(7.0, abs=0.01)
    assert a["win_loss_ratio"] == pytest.approx(1.39, abs=0.01)   # 9.71/7.0


def test_expectancy_pct_matches_book_formula(closed_set):
    a = AN.compute(closed_set)
    batting = 2 / 3
    expected = batting * 9.71 - (1 - batting) * 7.0               # p.298
    assert a["expectancy_pct"] == pytest.approx(round(expected, 2), abs=0.02)


def test_expectancy_dollars_is_mean_realized_pnl(closed_set):
    a = AN.compute(closed_set)
    pnl = [12 * (209.80 - 182.40), 10 * (46.50 - 50.0), 8 * (78.30 - 75.0)]
    assert a["total_pnl_dollars"] == pytest.approx(round(sum(pnl), 2), abs=0.02)
    assert a["expectancy_dollars"] == pytest.approx(
        round(sum(pnl) / 3, 2), abs=0.02)


def test_avg_r_multiple(closed_set):
    a = AN.compute(closed_set)
    rs = [round(15.02 / 7, 2), round(-7.0 / 7, 2), round(4.4 / 7, 2)]
    assert a["avg_r"] == pytest.approx(round(sum(rs) / 3, 2), abs=0.02)
    assert a["total_pnl_pct_on_risk"] == pytest.approx(round(sum(rs), 2),
                                                       abs=0.02)


def test_best_and_worst(closed_set):
    a = AN.compute(closed_set)
    assert a["best"]["symbol"] == "AAA" and a["best"]["gain_pct"] == 15.02
    assert a["worst"]["symbol"] == "BBB" and a["worst"]["gain_pct"] == -7.0


def test_avg_holding_days(closed_set):
    a = AN.compute(closed_set)
    assert a["avg_holding_days"] == pytest.approx((4 + 2 + 1) / 3, abs=0.01)


# ── Equity curve ─────────────────────────────────────────────────────────────

def test_equity_curve_is_cumulative_in_time_order(closed_set):
    a = AN.compute(closed_set)
    curve = a["equity_curve"]
    assert len(curve) == 3
    # Ordered by EXIT epoch (entry epoch + holding_days*86400):
    #   DDD exit 3000+1d, BBB exit 2000+2d, AAA exit 1000+4d -> DDD, BBB, AAA.
    pnl = [round(8 * (78.30 - 75.0), 2),    # DDD  +26.40
           round(10 * (46.50 - 50.0), 2),   # BBB  -35.00
           round(12 * (209.80 - 182.40), 2)]  # AAA +328.80
    cum = []
    run = 0.0
    for p in pnl:
        run += p
        cum.append(round(run, 2))
    assert [pt["cum_pnl_dollars"] for pt in curve] == cum
    # epochs strictly increasing (exit-time ordered).
    epochs = [pt["epoch"] for pt in curve]
    assert epochs == sorted(epochs)
    # final cumulative == total realized P&L.
    assert curve[-1]["cum_pnl_dollars"] == pytest.approx(
        a["total_pnl_dollars"], abs=0.01)


# ── By trigger ───────────────────────────────────────────────────────────────

def test_by_trigger_splits_intraday_and_manual(closed_set):
    a = AN.compute(closed_set)
    bt = a["by_trigger"]
    assert "intraday" in bt and "manual" in bt
    assert bt["intraday"]["n"] == 1                 # AAA only
    assert bt["manual"]["n"] == 2                   # BBB + DDD
    assert bt["intraday"]["avg_gain_pct"] == pytest.approx(15.02, abs=0.01)


# ── vs_book: targets + half-avg-gain stop + the p.301 floor flag ─────────────

def test_vs_book_targets_and_half_avg_gain_stop(closed_set):
    a = AN.compute(closed_set)
    vb = a["vs_book"]
    assert vb["target_ratio"] == 2.0 and vb["stretch_ratio"] == 3.0
    assert vb["batting_ref"] == 0.5
    assert vb["your_ratio"] == pytest.approx(1.39, abs=0.01)
    # half of avg_gain 9.71 = 4.855 -> 4.86, under the 10% cap (p.299).
    assert vb["half_avg_gain_stop_pct"] == pytest.approx(4.86, abs=0.02)


def test_win_loss_below_2to1_raises_p301_flag(closed_set):
    a = AN.compute(closed_set)
    flags = " ".join(a["vs_book"]["flags"])
    assert "2:1 floor" in flags and "p.301" in flags


def test_half_avg_gain_stop_capped_at_10pct():
    """p.299: even a huge average gain cannot push the suggested stop past
    the absolute 10% line."""
    big = [_trade("X%d" % i, 1000 + i, 60.0, 7.0, 1, 100.0, 160.0, 3.0)
           for i in range(3)]
    a = AN.compute(big)
    assert a["vs_book"]["half_avg_gain_stop_pct"] == 10.0    # min(30, 10)


# ── The cardinal sin flag (p.299) ────────────────────────────────────────────

def test_cardinal_sin_flag_when_avg_loss_exceeds_avg_gain():
    """p.299: avg loss > avg gain -> the trader's cardinal sin, flagged with
    the page cite. Set: one +5% winner, two -9% losers -> avg_gain 5,
    avg_loss 9."""
    trades = [
        _trade("W", 1000, 5.0, 7.0, 10, 100.0, 105.0, 2.0),
        _trade("L1", 2000, -9.0, 7.0, 10, 100.0, 91.0, 1.0),
        _trade("L2", 3000, -9.0, 7.0, 10, 100.0, 91.0, 1.0),
    ]
    a = AN.compute(trades)
    assert a["avg_loss_pct"] > a["avg_gain_pct"]
    flags = " ".join(a["vs_book"]["flags"])
    assert "cardinal sin" in flags and "p.299" in flags


# ── Provisional small-sample label ───────────────────────────────────────────

def test_provisional_true_under_min_record_n(closed_set):
    a = AN.compute(closed_set)
    assert a["n_closed"] < AN.MIN_RECORD_N
    assert a["provisional"] is True


def test_provisional_false_at_or_above_min_record_n():
    trades = [_trade("S%d" % i, 1000 + i, 10.0, 7.0, 1, 100.0, 110.0, 2.0)
              for i in range(AN.MIN_RECORD_N)]
    a = AN.compute(trades)
    assert a["n_closed"] == AN.MIN_RECORD_N
    assert a["provisional"] is False


# ── Open marks -> open_risk_dollars ──────────────────────────────────────────

def test_open_risk_dollars_sums_qty_times_last_minus_stop(closed_set):
    marks = [
        {"qty": 10, "last": 105.0, "stop": 100.0},   # 10 * 5 = 50 at risk
        {"qty": 5, "last": 90.0, "stop": 93.0},      # last < stop -> 0 (ratcheted)
        {"qty": 8, "last": 50.0, "stop": 46.50},     # 8 * 3.50 = 28
    ]
    a = AN.compute(closed_set, open_marks=marks)
    assert a["n_open"] == 3
    assert a["open_risk_dollars"] == pytest.approx(50.0 + 28.0, abs=0.01)


# ── Empty input -> zeroed shape, no exception ────────────────────────────────

def test_empty_input_returns_zeroed_provisional_shape():
    a = AN.compute([])
    assert a["n_closed"] == 0 and a["provisional"] is True
    assert a["batting_avg"] == 0.0 and a["win_loss_ratio"] == 0.0
    assert a["expectancy_pct"] == 0.0 and a["avg_r"] == 0.0
    assert a["best"] is None and a["worst"] is None
    assert a["equity_curve"] == [] and a["by_trigger"] == {}
    assert a["vs_book"]["flags"] == []
    assert a["vs_book"]["target_ratio"] == 2.0
    assert a["vs_book"]["stretch_ratio"] == 3.0


def test_empty_closed_but_open_marks_still_compute_open_risk():
    a = AN.compute([], open_marks=[{"qty": 4, "last": 50.0, "stop": 45.0}])
    assert a["n_closed"] == 0 and a["n_open"] == 1
    assert a["open_risk_dollars"] == pytest.approx(20.0, abs=0.01)
