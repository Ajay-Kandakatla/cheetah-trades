"""Sector rotation tracker.

Ajay 2026-08-16: "I want you to have sector rotation tracker what I feel now is
money is rotating out of that themes I gave you."

Every test below pins one of the four decisions that decide whether the numbers
are honest. Each of them flipped a real conclusion during the measurement that
produced this module, so none is an implementation detail:

  1. benchmark is RSP (equal-weight), not SPY
  2. anchor is the last close STRICTLY BEFORE the window start
  3. rank on the median MEMBER, not the sector ETF
  4. dead tickers are dropped, not counted as a flat 0%

All synthetic — no network, no scan on disk.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rotation import tracker as T  # noqa: E402


def bars(pairs):
    """[(date, close)] -> bar dicts, the shape chart_maps.board.bars_for emits."""
    return [{"t": d, "o": c, "h": c, "l": c, "c": c, "v": 1_000_000} for d, c in pairs]


FRESH = "2026-08-14"


# --------------------------------------------------------------------------
# Decision 2 — the anchor
# --------------------------------------------------------------------------
def test_anchor_is_the_last_close_strictly_before_the_start():
    b = bars([("2026-05-29", 100.0), ("2026-06-01", 110.0), ("2026-08-14", 120.0)])
    # 2026-06-01 IS a bar here. Strictly-before must pick 05-29, not 06-01.
    assert T.anchor_close(b, "2026-06-01") == 100.0


def test_anchor_when_the_start_is_not_a_trading_day():
    """June 1 2026 falls on a Monday; the tracker must behave identically when
    the window opens on a weekend or a holiday."""
    b = bars([("2026-05-29", 100.0), ("2026-06-02", 110.0)])
    assert T.anchor_close(b, "2026-06-01") == 100.0


def test_window_return_uses_that_anchor():
    b = bars([("2026-05-29", 100.0), ("2026-06-01", 110.0), ("2026-08-14", 150.0)])
    assert T.window_return(b, "2026-06-01") == pytest.approx(50.0)


# --- negatives ---

def test_no_bar_before_the_start_yields_no_return():
    """A name that IPO'd mid-window has no anchor. It must return None, not a
    number computed off its first available bar — that is the survivorship bug."""
    b = bars([("2026-07-01", 100.0), ("2026-08-14", 150.0)])
    assert T.anchor_close(b, "2026-06-01") is None
    assert T.window_return(b, "2026-06-01") is None


def test_zero_and_missing_closes_are_ignored():
    b = [{"t": "2026-05-28", "c": 0}, {"t": "2026-05-29", "c": None},
         {"t": "2026-05-30", "c": 100.0}, {"t": "2026-08-14", "c": 120.0}]
    assert T.anchor_close(b, "2026-06-01") == 100.0
    assert T.window_return(b, "2026-06-01") == pytest.approx(20.0)


def test_empty_bars_never_raise():
    assert T.anchor_close([], "2026-06-01") is None
    assert T.window_return([], "2026-06-01") is None
    assert T.window_return(None, "2026-06-01") is None
    assert T.trailing_return([], 21) is None


def test_trailing_return_needs_enough_bars():
    b = bars([(f"2026-08-{i:02d}", 100.0 + i) for i in range(1, 11)])
    assert T.trailing_return(b, 21) is None          # only 10 bars
    assert T.trailing_return(b, 5) is not None


# --------------------------------------------------------------------------
# Decision 4 — dead tickers
# --------------------------------------------------------------------------
def test_a_delisted_ticker_is_stale():
    """MRO's real last bar is 2024-11-21 (acquired by COP). Its anchor falls
    after its final bar, so a naive return is exactly 0.0% — which would drag
    the Energy median toward zero."""
    dead = bars([("2024-11-20", 28.0), ("2024-11-21", 28.55)])
    assert T.is_stale(dead, FRESH) is True


def test_a_live_ticker_is_not_stale_across_a_long_weekend():
    live = bars([("2026-08-07", 100.0), ("2026-08-11", 101.0)])
    assert T.is_stale(live, FRESH) is False


def test_stale_names_are_dropped_from_the_group_and_counted():
    frames = {
        "LIVE1": bars([("2026-05-29", 100.0), (FRESH, 120.0)]),
        "LIVE2": bars([("2026-05-29", 100.0), (FRESH, 110.0)]),
        "DEAD":  bars([("2024-11-20", 28.0), ("2024-11-21", 28.55)]),
    }
    row = T.group_row("Energy", ["LIVE1", "LIVE2", "DEAD"], frames,
                      "2026-06-01", FRESH)
    assert row["n"] == 2
    assert row["dropped"] == 1
    assert "DEAD" in row["dropped_symbols"]
    # Median of +20 and +10, NOT of +20/+10/0.
    assert row["median_window"] == pytest.approx(15.0)


def test_a_group_of_only_dead_names_reports_nothing_rather_than_zero():
    frames = {"DEAD": bars([("2024-11-21", 28.55)])}
    row = T.group_row("Ghost", ["DEAD"], frames, "2026-06-01", FRESH)
    assert row["n"] == 0 and row["dropped"] == 1
    assert row["median_window"] is None


def test_stale_check_is_defensive_about_junk_dates():
    assert T.is_stale(bars([("not-a-date", 10.0)]), FRESH) is True
    assert T.is_stale([], FRESH) is True
    assert T.is_stale(bars([(FRESH, 10.0)]), "") is True


# --------------------------------------------------------------------------
# Decision 3 — median member, not the ETF
# --------------------------------------------------------------------------
def test_the_etf_and_the_median_member_are_both_reported():
    """SOXX read -3.28% while the median liquid semi was -11.67%. The gap is
    the finding — it measures mega-cap concentration — so it must be visible."""
    frames = {
        "MEGA": bars([("2026-05-29", 100.0), (FRESH, 100.0)]),
        "A":    bars([("2026-05-29", 100.0), (FRESH, 88.0)]),
        "B":    bars([("2026-05-29", 100.0), (FRESH, 88.0)]),
        "XLX":  bars([("2026-05-29", 100.0), (FRESH, 97.0)]),
    }
    row = T.group_row("Technology", ["MEGA", "A", "B"], frames,
                      "2026-06-01", FRESH, etf="XLX")
    assert row["median_window"] == pytest.approx(-12.0)
    assert row["etf_window"] == pytest.approx(-3.0)
    assert row["etf_vs_median"] == pytest.approx(9.0)


def test_median_not_mean_so_one_outlier_cannot_carry_a_sector():
    frames = {s: bars([("2026-05-29", 100.0), (FRESH, c)]) for s, c in
              (("A", 99.0), ("B", 100.0), ("C", 101.0), ("D", 1000.0))}
    row = T.group_row("X", ["A", "B", "C", "D"], frames, "2026-06-01", FRESH)
    assert row["median_window"] == pytest.approx(0.5)   # mean would be ~225


def test_pct_positive_counts_breadth():
    frames = {s: bars([("2026-05-29", 100.0), (FRESH, c)]) for s, c in
              (("A", 110.0), ("B", 105.0), ("C", 95.0), ("D", 90.0))}
    row = T.group_row("X", ["A", "B", "C", "D"], frames, "2026-06-01", FRESH)
    assert row["pct_positive"] == pytest.approx(50.0)


# --------------------------------------------------------------------------
# Decision 1 — the benchmark
# --------------------------------------------------------------------------
def test_the_benchmark_is_equal_weight():
    """RSP +6.68% vs SPY +2.63% over the measured window — 4.05pp of pure
    cap-weight drag that would read as rotation against SPY."""
    assert T.BENCHMARK == "RSP"
    assert T.BENCHMARK_FALLBACK == "SPY"


def test_relative_restates_every_window_against_the_benchmark():
    rows = [{"group": "X", "median_window": 10.0, "median_21d": 3.0,
             "median_63d": None}]
    out = T._relativize(rows, {"window": 6.68, "d21": 3.58, "d63": 9.38})
    assert out[0]["rel_window"] == pytest.approx(3.32)
    assert out[0]["rel_21d"] == pytest.approx(-0.58)
    assert out[0]["rel_63d"] is None


def test_relative_is_none_when_the_benchmark_is_missing():
    out = T._relativize([{"group": "X", "median_window": 10.0}],
                        {"window": None, "d21": None, "d63": None})
    assert out[0]["rel_window"] is None


# --------------------------------------------------------------------------
# Safe havens vs the rest — Ajay's "safe haves vs in general"
# --------------------------------------------------------------------------
def test_every_sector_has_a_stance():
    """A sector with no stance silently vanishes from the defensive/cyclical
    read, which is the whole point of the grouping."""
    for sector in T.SECTOR_ETF:
        assert sector in T.STANCE, f"{sector} has no defensive/cyclical stance"


def test_stances_partition_cleanly():
    assert not (set(T.DEFENSIVE) & set(T.CYCLICAL))
    assert not (set(T.DEFENSIVE) & set(T.COMMODITY))
    assert not (set(T.CYCLICAL) & set(T.COMMODITY))


def test_haven_proxies_cover_the_classic_destinations():
    """Gold, treasuries and low-vol are where Wall Street historically hides."""
    syms = set(T.HAVEN_PROXY.values())
    assert {"GLD", "TLT", "USMV"} <= syms
    assert "RSP" in syms, "the benchmark itself must appear, as the 0.0 line"


def test_group_row_carries_the_stance_through():
    frames = {"A": bars([("2026-05-29", 100.0), (FRESH, 110.0)])}
    assert T.group_row("Utilities", ["A"], frames, "2026-06-01",
                       FRESH)["stance"] == "defensive"
    assert T.group_row("Technology", ["A"], frames, "2026-06-01",
                       FRESH)["stance"] == "cyclical"


def test_a_theme_row_has_no_stance():
    """Themes are not sectors; forcing one into defensive/cyclical would be a
    claim we have not measured."""
    frames = {"A": bars([("2026-05-29", 100.0), (FRESH, 110.0)])}
    assert T.group_row("space", ["A"], frames, "2026-06-01", FRESH)["stance"] is None
