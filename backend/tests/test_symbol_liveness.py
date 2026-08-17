"""The check that would have caught SQ nineteen months earlier.

Ajay 2026-08-16: the app said SATS was delisted while it traded at $91.89.
Fixing that one name turned up the real gap — Block renamed SQ to XYZ on
2025-01-21 and nothing noticed for **576 days**, because every existing check
asked how old the CACHE was and the cache was refreshing perfectly. It was just
storing the same dead bars each time.

These tests pin the third question: for each symbol we claim to cover, when did
its newest bar actually print?

All synthetic, loader injected. No network, no Mongo.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pd = pytest.importorskip("pandas")

from observability import symbol_liveness as SL  # noqa: E402

TODAY = date(2026, 8, 16)


def frame(last: str, n: int = 5):
    idx = pd.bdate_range(end=pd.Timestamp(last), periods=n)
    return pd.DataFrame({"open": [1.0] * n, "high": [1.0] * n, "low": [1.0] * n,
                         "close": [1.0] * n, "volume": [1.0] * n}, index=idx)


def loader_for(mapping):
    def _load(sym):
        val = mapping.get(sym, "__missing__")
        if val == "__missing__":
            raise KeyError(sym)
        return None if val is None else frame(val)
    return _load


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------
def test_a_current_symbol_is_fresh():
    assert SL.classify("2026-08-14", TODAY) == "fresh"


def test_the_sq_case_is_stopped():
    """576 calendar days of nothing. This is the whole reason the check exists."""
    assert SL.classify("2025-01-17", TODAY) == "stopped"


def test_a_symbol_with_no_bars_at_all_is_stopped():
    assert SL.classify(None, TODAY) == "stopped"


def test_there_is_a_band_between_fresh_and_stopped():
    """A week-long provider hiccup that heals itself should not land in a
    monthly report. Naming the band keeps the threshold honest as a choice."""
    assert SL.classify("2026-08-06", TODAY) == "quiet"


def test_a_long_weekend_never_reads_as_stopped():
    assert SL.classify("2026-08-13", TODAY) == "fresh"


# --- negatives ---
def test_a_future_bar_is_not_stale():
    assert SL.classify("2026-08-20", TODAY) == "fresh"


def test_the_threshold_is_a_parameter_not_a_constant():
    assert SL.classify("2026-08-06", TODAY, max_quiet=2) == "stopped"


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------
def test_a_healthy_universe_reports_ok():
    syms = ["AAPL", "NVDA", "MSFT"]
    got = SL.scan(syms, TODAY, loader=loader_for({s: "2026-08-14" for s in syms}))
    assert got["ok"] is True
    assert got["fresh"] == 3
    assert got["symbols"] == []


def test_one_dead_name_is_surfaced_with_its_last_bar():
    got = SL.scan(["AAPL", "SMAR"], TODAY,
                  loader=loader_for({"AAPL": "2026-08-14", "SMAR": "2025-01-21"}))
    assert got["ok"] is False
    assert [r["symbol"] for r in got["symbols"]] == ["SMAR"]
    assert got["symbols"][0]["last_bar"] == "2025-01-21"
    assert got["symbols"][0]["sessions_quiet"] > 400


def test_the_deadest_name_is_listed_first():
    """Sorted by how long it has been wrong, because that is how long we have
    been showing Ajay a dead chart."""
    got = SL.scan(["A", "B", "C"], TODAY,
                  loader=loader_for({"A": "2026-06-23", "B": "2025-01-21",
                                     "C": "2026-03-16"}))
    assert [r["symbol"] for r in got["symbols"]] == ["B", "C", "A"]


def test_it_never_pushes_and_stays_a_warning():
    """Ajay's phone keep-set is three kinds and this is not one of them."""
    got = SL.scan(["SMAR"], TODAY, loader=loader_for({"SMAR": "2025-01-21"}))
    assert got["severity"] == "WARN"


def test_a_symbol_already_in_RENAMES_is_flagged_as_a_regression():
    """SATS is in RENAMES and the fetch path splices it, so it must read fresh.
    If it ever shows up stale again, the splice broke — and that is a different
    and more urgent bug than an unknown dead ticker."""
    got = SL.scan(["SATS"], TODAY, loader=loader_for({"SATS": "2026-06-23"}))
    assert got["renames_regressed"] == ["SATS"]
    assert "REGRESSED" in got["detail"]


def test_a_working_rename_produces_no_regression():
    got = SL.scan(["SATS"], TODAY, loader=loader_for({"SATS": "2026-08-14"}))
    assert got["renames_regressed"] == []
    assert got["ok"] is True


# --- negatives: the failure modes that would bury the real finding ---
def test_a_universe_wide_outage_names_no_symbols():
    """If the provider or the warm cron dies, every symbol looks dead. Printing
    1,600 'dead tickers' would hide the one real rename, so the check says what
    actually happened instead."""
    syms = [f"S{i}" for i in range(50)]
    got = SL.scan(syms, TODAY, loader=loader_for({s: None for s in syms}))
    assert got["ok"] is False
    assert got["symbols"] == []
    assert "provider" in got["detail"]


def test_just_under_the_breadth_alarm_still_lists_symbols():
    syms = [f"S{i}" for i in range(100)]
    m = {s: "2026-08-14" for s in syms}
    for s in syms[:5]:                      # 5% — under the 10% alarm
        m[s] = "2025-01-21"
    got = SL.scan(syms, TODAY, loader=loader_for(m))
    assert len(got["symbols"]) == 5


def test_a_symbol_that_raises_is_counted_not_crashed():
    got = SL.scan(["AAPL", "BOOM"], TODAY, loader=loader_for({"AAPL": "2026-08-14"}))
    assert got["unreadable"] == 1
    assert got["fresh"] == 1


def test_an_empty_universe_does_not_divide_by_zero():
    got = SL.scan([], TODAY, loader=loader_for({}))
    assert got["total"] == 0
    assert got["ok"] is True


def test_the_symbol_list_is_capped_so_the_report_stays_readable():
    syms = [f"S{i}" for i in range(1000)]
    m = {s: "2026-08-14" for s in syms}
    for s in syms[:60]:
        m[s] = "2025-01-21"
    got = SL.scan(syms, TODAY, loader=loader_for(m))
    assert got["stopped"] == 60, "the COUNT must stay truthful"
    assert len(got["symbols"]) == 50, "only the listing is capped"
