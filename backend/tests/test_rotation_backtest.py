"""Does rotating into the leading sectors pay?

Ajay 2026-08-16: "Yes also back test and add the rotation tracker".

Measured over 116 monthly rebalances, 2016-11 to 2026-07: top-3 rotation
returned 158.22%, RSP 155.42%, and simply holding all 11 sectors 163.23%. Mean
excess per period -0.013% with a 95% interval of [-0.549, +0.522], beating the
benchmark in 51.7% of months.

So the ranking adds nothing, and the do-nothing alternative wins. That is a fine
outcome for the tracker — it was built to DESCRIBE what moved, not to predict —
but only if the tests stop someone later turning it into a signal.

All synthetic. No network.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pd = pytest.importorskip("pandas")

from rotation import backtest as RB  # noqa: E402


def frame(closes, opens=None):
    idx = pd.bdate_range("2020-01-01", periods=len(closes))
    opens = opens or closes
    return pd.DataFrame({"open": opens, "high": closes, "low": closes,
                         "close": closes, "volume": [1_000] * len(closes)},
                        index=idx)


def ramp(n, start=100.0, step=1.0):
    return [start + i * step for i in range(n)]


# --------------------------------------------------------------------------
# Ranking
# --------------------------------------------------------------------------
def test_ranking_is_relative_to_the_benchmark_not_absolute():
    """In a falling market every sector is negative. An absolute rank buys the
    least-bad three, which is a different and worse strategy than owning the
    leaders."""
    n = 80
    bench = frame(ramp(n, 100, -1.0))          # benchmark falling
    strong = frame(ramp(n, 100, -0.5))         # falls less
    weak = frame(ramp(n, 100, -2.0))           # falls more
    ranked = RB.rank_at({"S": strong, "W": weak}, ["S", "W"], 70, bench)
    assert [s for s, _ in ranked] == ["S", "W"]
    assert ranked[0][1] > 0, "beating a falling benchmark must score positive"
    assert ranked[1][1] < 0


def test_ranking_orders_by_relative_strength():
    n = 80
    bench = frame(ramp(n, 100, 0.5))
    a, b, c = frame(ramp(n, 100, 2.0)), frame(ramp(n, 100, 1.0)), frame(ramp(n, 100, 0.1))
    ranked = RB.rank_at({"A": a, "B": b, "C": c}, ["A", "B", "C"], 70, bench)
    assert [s for s, _ in ranked] == ["A", "B", "C"]


def test_a_symbol_with_no_history_is_skipped_not_ranked_last():
    n = 80
    bench = frame(ramp(n))
    ranked = RB.rank_at({"A": frame(ramp(n, 100, 2.0)), "GONE": None},
                        ["A", "GONE"], 70, bench)
    assert [s for s, _ in ranked] == ["A"]


def test_ranking_uses_only_bars_up_to_the_rebalance():
    """The lookahead firewall. A spike AFTER the rebalance bar must not change
    the ranking made on it."""
    n = 100
    bench = frame(ramp(n, 100, 0.0))
    quiet = ramp(n, 100, 0.1)
    spiked = list(quiet)
    spiked[85:] = [500.0] * (n - 85)           # moonshot after bar 80
    before = RB.rank_at({"X": frame(quiet)}, ["X"], 80, bench)
    after = RB.rank_at({"X": frame(spiked)}, ["X"], 80, bench)
    assert before == after


# --------------------------------------------------------------------------
# Returns and costs
# --------------------------------------------------------------------------
def test_sleeves_are_equal_weighted():
    a, b = frame([100.0, 110.0]), frame([100.0, 90.0])
    got = RB._sleeve_return({"A": a, "B": b}, ["A", "B"], 0, 1)
    assert got == pytest.approx(0.0)           # +10% and -10%


def test_sleeve_return_is_open_to_open():
    """Entry is the next session's OPEN. Using closes would let the rule rank on
    a close and trade the same one."""
    df = frame(closes=[100.0, 999.0], opens=[100.0, 120.0])
    assert RB._sleeve_return({"A": df}, ["A"], 0, 1) == pytest.approx(0.2)


def test_turnover_is_the_fraction_of_the_book_replaced():
    assert RB._turnover([], ["A", "B", "C"]) == 1.0
    assert RB._turnover(["A", "B", "C"], ["A", "B", "C"]) == 0.0
    assert RB._turnover(["A", "B", "C"], ["A", "B", "D"]) == pytest.approx(1 / 3)


def test_turnover_of_nothing_is_zero_not_one():
    assert RB._turnover(["A"], []) == 0.0


# --------------------------------------------------------------------------
# The summary — where an edge would be over-read
# --------------------------------------------------------------------------
def _periods(strategy, rsp, allw=None):
    return [{"date": f"2020-0{i%9+1}-01", "held": ["A"], "strategy_pct": s,
             "rsp_pct": r, "spy_pct": r,
             "all_sectors_pct": (allw[i] if allw else r), "turnover": 0.3}
            for i, (s, r) in enumerate(zip(strategy, rsp))]


def test_compounding_is_not_summation():
    got = RB.summarize(_periods([10.0, 10.0], [0.0, 0.0]))
    assert got["strategy_total_pct"] == pytest.approx(21.0)   # not 20


def test_the_interval_straddling_zero_is_reported():
    """The real result: +158% compounded while the per-period interval spans
    zero. The compounded number alone reads as an edge; the interval says it is
    a sample."""
    got = RB.summarize(_periods([2.0, -2.0, 3.0, -3.0, 1.0, -1.0],
                                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]))
    lo, hi = got["excess_ci95"]
    assert lo < 0 < hi, "an interval spanning zero must be visible"


def test_beat_rate_counts_periods_not_magnitude():
    got = RB.summarize(_periods([1.0, 1.0, -10.0], [0.0, 0.0, 0.0]))
    assert got["beat_rsp_pct"] == pytest.approx(66.7, abs=0.1)


def test_the_do_nothing_alternative_is_always_reported():
    """Holding all 11 sectors beat the top-3 rule (163.23% vs 158.22%). If that
    line is ever dropped, the rule looks better than it is."""
    got = RB.summarize(_periods([1.0, 1.0], [0.5, 0.5], allw=[2.0, 2.0]))
    assert got["all_sectors_total_pct"] is not None
    assert got["all_sectors_total_pct"] > got["strategy_total_pct"]


def test_the_summary_points_at_the_interval():
    got = RB.summarize(_periods([1.0, 1.0], [0.0, 0.0]))
    assert "excess_ci95" in got["note"]


def test_summarize_on_nothing_is_empty_not_zero():
    assert RB.summarize([])["n"] == 0


# --------------------------------------------------------------------------
# Regime breakdown
# --------------------------------------------------------------------------
def test_by_year_splits_so_one_regime_cannot_carry_the_result():
    """The real run swung from +11.38pp (2023) to -9.47pp (2025). A single
    total would hide that entirely."""
    periods = [
        {"date": "2022-03-01", "strategy_pct": 5.0, "rsp_pct": -1.0,
         "all_sectors_pct": 0.0, "spy_pct": -1.0, "held": ["A"], "turnover": 0.3},
        {"date": "2023-03-01", "strategy_pct": 2.0, "rsp_pct": 1.0,
         "all_sectors_pct": 0.0, "spy_pct": 1.0, "held": ["A"], "turnover": 0.3},
    ]
    got = RB.by_year(periods)
    assert [y["year"] for y in got] == ["2022", "2023"]
    assert got[0]["excess_pct"] == pytest.approx(6.0)
    assert got[1]["excess_pct"] == pytest.approx(1.0)


# --------------------------------------------------------------------------
# The history the test actually runs on
# --------------------------------------------------------------------------
def test_the_backtest_forces_a_full_refetch():
    """prices.load_prices serves a 500-bar cache and its `period` argument is a
    no-op — that is what silently limited the zone backtest to 13 bull-market
    months. force=True returns ~2,510 bars. If this ever reverts, the rule is
    being measured in one regime again."""
    import inspect
    src = inspect.getsource(RB.run)
    assert "force=True" in src


def test_the_benchmark_is_equal_weight():
    """A 3-of-11 equal-weight sleeve strategy is closer to RSP than to SPY.
    Benchmarking it against SPY would credit it with equal-weight's spread."""
    assert RB.BENCHMARK == "RSP"
    assert RB.BENCHMARK_ALT == "SPY"
