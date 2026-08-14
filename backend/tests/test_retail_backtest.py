"""Is retail imbalance predictive? — harness integrity tests.

Ajay 2026-08-14, after SWKS fell on a buy-side tape: "lets [test] it before you
lean on this at all." These tests protect the harness that answers that, since
a subtly wrong backtest is far more dangerous than no backtest.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orderflow import retail_backtest as BT


def test_forward_returns_measure_from_the_decision_day_close():
    """Entry is the CLOSE of the day whose tape produced the signal. The tape
    is complete at that close, so nothing unknowable is used."""
    closes = [100, 101, 103, 102, 105, 107]
    dates = ["d0", "d1", "d2", "d3", "d4", "d5"]
    out = BT._forward_returns(closes, dates, "d0")
    assert out["fwd_1d"] == 1.0        # 101/100
    assert out["fwd_3d"] == 2.0        # 102/100
    assert out["fwd_5d"] == 7.0        # 107/100


def test_forward_returns_are_none_past_the_end_not_clipped():
    """Silently clipping to the last available bar would quietly turn a 5-day
    horizon into a 1-day one and flatter the result."""
    closes = [100, 101, 103, 102, 105, 107]
    dates = ["d0", "d1", "d2", "d3", "d4", "d5"]
    out = BT._forward_returns(closes, dates, "d4")
    assert out["fwd_1d"] is not None
    assert out["fwd_3d"] is None and out["fwd_5d"] is None


def test_forward_returns_reject_unknown_or_degenerate_days():
    assert BT._forward_returns([100, 101], ["d0", "d1"], "nope") == {}
    assert BT._forward_returns([0, 101], ["d0", "d1"], "d0") == {}


def test_summarize_refuses_to_score_a_tiny_sample():
    obs = [{"imbalance": i, "fwd_1d": 1.0, "fwd_3d": 1.0, "fwd_5d": 1.0} for i in range(10)]
    assert "too few" in BT.summarize(obs)["verdict"]


def test_summarize_detects_a_planted_positive_relationship():
    """Control: if retail buying really did predict gains, the harness must
    say so. A test that can only ever print 'no signal' proves nothing."""
    obs = [{"imbalance": i - 50, "fwd_1d": (i - 50) / 10.0,
            "fwd_3d": (i - 50) / 10.0, "fwd_5d": (i - 50) / 10.0}
           for i in range(100)]
    s = BT.summarize(obs)
    for h in s["horizons"].values():
        assert h["spread_pct"] > 0
        assert h["rank_correlation"] > 0.9
    assert "predictive" in s["verdict"]


def test_summarize_calls_noise_noise():
    """Alternating returns uncorrelated with imbalance must NOT read as a
    signal — the failure mode that would cost real money."""
    obs = [{"imbalance": i - 50,
            "fwd_1d": 0.2 if i % 2 else -0.2,
            "fwd_3d": -0.2 if i % 2 else 0.2,
            "fwd_5d": 0.1 if i % 3 else -0.1}
           for i in range(100)]
    s = BT.summarize(obs)
    assert "no usable signal" in s["verdict"]


def test_summarize_requires_a_CONSISTENT_sign_across_horizons():
    """A spread that flips direction between 1d and 5d is noise dressed as
    signal; the verdict must not reward it."""
    obs = []
    for i in range(100):
        imb = i - 50
        obs.append({"imbalance": imb,
                    "fwd_1d": imb / 10.0,       # positive relationship
                    "fwd_3d": -imb / 10.0,      # negative — flips
                    "fwd_5d": imb / 10.0})
    assert "no usable signal" in BT.summarize(obs)["verdict"]
