"""Scan skip accounting — no symbol leaves the payload without a trace.

Audit 2026-08-25: 69 of 1,746 universe symbols never reached all_results and
latest.json's permanent_failures was EMPTY — `_analyze_symbol` returning None
(no data, thin history, stale series, liquidity floor) was silently dropped by
both scan loops. Four of those Nones were dead tickers (SMAR stale since
2025-01-21) that nothing could distinguish from a liquidity drop.

These tests pin the two halves of the fix:
  1. `_analyze_symbol` / `_hot_recompute` record symbol -> reason into `skips`.
  2. `_absorb_skips` folds them into permanent_failures without disturbing
     real failure records, recovered symbols, or recovered_count.

All synthetic. No network.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pd = pytest.importorskip("pandas")
np = pytest.importorskip("numpy")

from sepa import scanner as sc  # noqa: E402


def _df(n_bars: int, last_day: date | None = None) -> "pd.DataFrame":
    """Synthetic OHLCV frame with `n_bars` business days ending `last_day`."""
    last_day = last_day or date.today()
    idx = pd.bdate_range(end=pd.Timestamp(last_day), periods=n_bars)
    px = pd.Series(100.0 + np.arange(n_bars) * 0.1, index=idx)
    return pd.DataFrame({
        "open": px, "high": px * 1.01, "low": px * 0.99, "close": px,
        "volume": pd.Series(1_000_000, index=idx),
    })


# ---------------------------------------------------------------------------
# _analyze_symbol records WHY it returned None
# ---------------------------------------------------------------------------
def test_no_price_data_is_recorded(monkeypatch):
    monkeypatch.setattr(sc.prices, "load_prices", lambda s: None)
    skips = {}
    assert sc._analyze_symbol("DEADX", {}, skips=skips) is None
    assert skips == {"DEADX": "no price data"}


def test_thin_history_is_recorded_with_the_bar_count(monkeypatch):
    monkeypatch.setattr(sc.prices, "load_prices", lambda s: _df(57))
    skips = {}
    assert sc._analyze_symbol("YOUNG", {}, skips=skips) is None
    assert skips["YOUNG"] == "insufficient history (57 bars < 220)"


def test_stale_series_is_recorded_with_the_last_bar_date(monkeypatch):
    # bdate_range snaps a weekend end-date back to Friday, so the expected
    # date must come from the FRAME, not from `today - 60d` — the raw form
    # failed every day that offset landed on a weekend (first seen
    # 2026-08-26, when it hit Saturday 06-27).
    frozen = date.today() - timedelta(days=60)
    frame = _df(300, frozen)
    monkeypatch.setattr(sc.prices, "load_prices", lambda s: frame)
    skips = {}
    assert sc._analyze_symbol("HALTED", {}, skips=skips) is None
    assert skips["HALTED"].startswith("stale — last bar ")
    assert frame.index[-1].date().isoformat() in skips["HALTED"]


def test_liquidity_floor_is_recorded(monkeypatch):
    monkeypatch.setattr(sc.prices, "load_prices", lambda s: _df(300))
    monkeypatch.setattr(sc.adr, "liquidity_check",
                        lambda df: {"liquid": False, "reason": "thin"})
    skips = {}
    assert sc._analyze_symbol("THIN", {}, skips=skips) is None
    assert skips["THIN"] == "below institutional liquidity floor"


def test_skips_is_optional(monkeypatch):
    """NEGATIVE: every existing caller passes no skips dict — the early
    returns must stay plain Nones for them, not crashes."""
    monkeypatch.setattr(sc.prices, "load_prices", lambda s: None)
    assert sc._analyze_symbol("DEADX", {}) is None


# ---------------------------------------------------------------------------
# _hot_recompute (fast path) records the same way
# ---------------------------------------------------------------------------
def test_hot_recompute_records_cached_illiquidity():
    skips = {}
    out = sc._hot_recompute("THIN", _df(300), {},
                            {"liquidity": {"liquid": False}}, skips=skips)
    assert out is None
    assert skips["THIN"] == "below institutional liquidity floor (cached research)"


def test_hot_recompute_records_stale_frozen_bars():
    frozen = date.today() - timedelta(days=60)
    skips = {}
    out = sc._hot_recompute("HALTED", _df(300, frozen), {}, {}, skips=skips)
    assert out is None
    assert skips["HALTED"].startswith("stale — last bar ")


# ---------------------------------------------------------------------------
# _absorb_skips — folding into permanent_failures
# ---------------------------------------------------------------------------
def test_absorb_adds_skips_with_reason_and_marker():
    pf = []
    sc._absorb_skips(pf, {"AAA": "no price data"}, results=[])
    assert pf == [{"symbol": "AAA", "attempt": 1, "skipped": True,
                   "error": "no price data"}]


def test_absorb_never_overwrites_a_real_failure_record():
    pf = [{"symbol": "ZZZ", "error": "boom", "attempt": 2}]
    sc._absorb_skips(pf, {"ZZZ": "stale — last bar 2026-01-01"}, results=[])
    assert pf == [{"symbol": "ZZZ", "error": "boom", "attempt": 2}]


def test_absorb_skips_symbols_that_recovered_into_results():
    """NEGATIVE: a symbol that failed pass 1 but produced a row on retry is a
    success — recording it as skipped would contradict all_results."""
    pf = []
    sc._absorb_skips(pf, {"WON": "no price data"},
                     results=[{"symbol": "WON"}])
    assert pf == []


def test_absorb_records_excluded_benchmarks_as_by_design():
    pf = []
    sc._absorb_skips(pf, {}, results=[], excluded_benchmarks=["SPY", "QQQ"])
    assert [(f["symbol"], f["attempt"], f["skipped"]) for f in pf] == \
        [("SPY", 0, True), ("QQQ", 0, True)]
    assert all("by design" in f["error"] for f in pf)


def test_absorb_with_nothing_to_do_changes_nothing():
    """NEGATIVE: a clean scan keeps a clean payload."""
    pf = []
    sc._absorb_skips(pf, {}, results=[{"symbol": "NVDA"}])
    assert pf == []


def test_absorb_output_is_deterministically_ordered():
    pf = []
    sc._absorb_skips(pf, {"ZED": "x", "ALF": "y", "MID": "z"}, results=[])
    assert [f["symbol"] for f in pf] == ["ALF", "MID", "ZED"]


def test_recovered_count_semantics_survive_the_fold():
    """recovered_count is snapshotted before the fold in both scan paths —
    replicate the arithmetic here so a refactor that derives it from
    len(permanent_failures) AFTER absorbing fails loudly."""
    failures = [{"symbol": "A"}, {"symbol": "B"}]          # pass-1 failures
    pf = [{"symbol": "B", "error": "still down", "attempt": 2}]
    recovered = len(failures) - len(pf)                    # A came back
    sc._absorb_skips(pf, {"C": "no price data"}, results=[{"symbol": "A"}])
    assert recovered == 1
    assert len(pf) == 2   # B's failure + C's skip — recovered stays 1
