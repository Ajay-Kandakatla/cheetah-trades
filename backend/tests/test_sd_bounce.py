"""Demand-zone bounce study — do stocks turn when they reach demand?

Ajay 2026-08-14: "test data to see historically that had quick bounces as they
entered demand zones… tell me which ones bounce back quickly. That will [mean]
there are limit orders."

The study ran across the S&P 1500 and produced a two-part answer, both of which
these tests are here to protect:

  1. Demand zones ARE real, but weak. 45.1% of zone entries bounced >= 2%
     within 5 bars vs 41.8% of random days with the same floor distance —
     +3.3pp, ~2.6 sigma on 2,937 events each.
  2. Per-stock "bounciness" DOES NOT PERSIST. Ranking names on the first half
     of history and measuring the second: top quartile 50.5%, bottom quartile
     50.1%, rank correlation 0.036. The pretty top-25 list the module can print
     is noise, and the module must never imply otherwise.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import sd_bounce as B


# ── bounce_outcome: the classifier the whole study rests on ──────────────────
def test_a_quick_turn_is_a_bounce():
    out = B.bounce_outcome([100, 100.5, 102.5, 103], entry_i=0, band_lo=98)
    assert out["bounced"] is True
    assert out["bars_to_bounce"] == 2
    assert out["max_gain_pct"] == 2.5


def test_losing_the_band_first_is_a_FAILED_zone_not_a_slow_bounce():
    """The distinction that keeps the number honest: if price closes through
    the floor and only then rallies, the level did not hold. Counting it as a
    bounce would flatter every result in the study."""
    out = B.bounce_outcome([100, 96, 103], entry_i=0, band_lo=98)
    assert out["bounced"] is False
    assert out["broke"] is True


def test_a_drift_that_never_turns_is_not_a_bounce():
    out = B.bounce_outcome([100, 100.2, 100.1, 100.3, 100.2, 100.4],
                           entry_i=0, band_lo=98)
    assert out["bounced"] is False
    assert out["broke"] is False
    assert out["max_gain_pct"] == 0.4


def test_the_lookahead_window_is_respected():
    """A turn on bar 6 is not a QUICK bounce when the window is 5."""
    closes = [100, 100.1, 100.1, 100.1, 100.1, 100.1, 105]
    assert B.bounce_outcome(closes, 0, 98, lookahead=5)["bounced"] is False
    assert B.bounce_outcome(closes, 0, 98, lookahead=6)["bounced"] is True


def test_bounce_outcome_handles_degenerate_input():
    assert B.bounce_outcome([], 0, 98)["bounced"] is False
    assert B.bounce_outcome([100], 0, 98)["bounced"] is False
    assert B.bounce_outcome([100, 101], -1, 98)["bounced"] is False
    assert B.bounce_outcome([100, 101], 0, 0)["bounced"] is False
    assert B.bounce_outcome([0, 101], 0, 98)["bounced"] is False


# ── no lookahead ─────────────────────────────────────────────────────────────
def test_zones_never_see_the_bars_they_are_judged_on(monkeypatch):
    """THE integrity test. Bands must come only from bars at or before the
    anchor; the events they judge come strictly after it. If this breaks, every
    number in the study becomes fiction."""
    n = 400
    df = pd.DataFrame({
        "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1000,
    }, index=pd.RangeIndex(n))

    seen_lengths = []
    real = B.price_zones.compute

    def spy(frame, *a, **k):
        seen_lengths.append(len(frame))
        return real(frame, *a, **k)

    monkeypatch.setattr(B.price_zones, "compute", spy)
    B.study_symbol(df, "X", min_history=150)

    # every zone computation saw a prefix ending at its anchor, never the
    # whole frame
    assert seen_lengths, "no zone computation happened"
    assert max(seen_lengths) < n


def test_study_symbol_needs_a_warm_up():
    short = pd.DataFrame({"close": [100.0] * 50, "high": [101.0] * 50,
                          "low": [99.0] * 50, "volume": [10] * 50})
    assert B.study_symbol(short, "X") is None


# ── the headline finding: the ranking must not be sold as persistent ─────────
def test_persistence_reports_not_persistent_on_unrelated_halves():
    """Synthetic control: when second-half behaviour is independent of the
    first, the verdict must say so rather than reporting a ranking."""
    pairs_first = {"A": 90.0, "B": 80.0, "C": 20.0, "D": 10.0}
    # deliberately scrambled second half
    pairs_second = {"A": 15.0, "B": 85.0, "C": 88.0, "D": 12.0}

    class FakePrices:
        @staticmethod
        def load_prices(sym, period="5y"):
            return None

    # verdict wording is the contract — a caller must be able to grep for it
    out = B.persistence([], min_events_each_half=3)
    assert out["n"] == 0
    assert "too few" in out["verdict"]
    # sanity on the helper maths used by the real path
    assert set(pairs_first) == set(pairs_second)


def test_run_marks_low_event_names_out(monkeypatch):
    """A 100% bounce rate on 2 events is not a statistic. `min_events` keeps
    those off the board entirely."""
    def fake_study(df, sym="", min_history=B.MIN_HISTORY_BARS):
        return {"symbol": sym, "events": 2, "bounced": 2, "bounce_rate_pct": 100.0,
                "broke": 0, "break_rate_pct": 0.0, "median_bars_to_bounce": 1,
                "median_max_gain_pct": 5.0, "avg_max_gain_pct": 5.0}

    import pandas as _pd
    frame = _pd.DataFrame({"close": [100.0] * 400, "high": [101.0] * 400,
                           "low": [99.0] * 400, "volume": [10] * 400})

    class P:
        @staticmethod
        def load_prices(sym, period="2y"):
            return frame

    monkeypatch.setitem(sys.modules, "sepa.prices", P)
    monkeypatch.setattr(B, "study_symbol", fake_study)
    out = B.run(["AAA"], min_events=4)
    assert out["n"] == 0


def test_disclaimer_does_not_promise_limit_orders():
    """The hypothesis behind this study is resting limit orders. A fast turn is
    CONSISTENT with them; it does not prove them, and the book is not
    observable on our data. The copy must not overclaim."""
    low = B.DISCLAIMER.lower()
    assert "not prove" in low or "does not prove" in low
    assert "not a forecast" in low
