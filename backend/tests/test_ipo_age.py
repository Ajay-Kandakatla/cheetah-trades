"""IPO-age data-trust tests (2026-08-31).

The bug: sepa/ipo_age.py read the first bar of the cached price frame as the
listing date. The price cache is keyed by symbol only and every fetch has a
hard lookback cap (prices.PERIOD_DAYS), so an old company whose frame was
filled by the scan's 2y fetch showed first_trade_date at the cap boundary and
is_recent_ipo=true. Live case: SAIC reported first_trade_date=2024-09-03 /
is_recent_ipo=true while the company listed 2013-09-16.

The contract now:
  - a first bar whose age coincides with any fetch cap (±guard) is NEVER
    read as a listing — the profile provider answers, or every field is None
  - bars alone never mint a recent-IPO claim without a profile confirm
    attempt; the profile wins whenever it knows a date
  - book thresholds are untouched: is_young ≤8y, is_recent_ipo ≤2y
    (TLSW Ch. 11 p. 260)
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta

import pandas as pd
import pytest

from sepa import ipo_age
from sepa.prices import PERIOD_DAYS


def _frame(span_days: int) -> pd.DataFrame:
    """Business-day OHLCV-ish frame whose first bar is ~span_days ago."""
    now = pd.Timestamp(datetime.utcnow().date())
    idx = pd.bdate_range(start=now - pd.Timedelta(days=span_days), end=now)
    return pd.DataFrame({"close": [100.0] * len(idx)}, index=idx)


@pytest.fixture
def no_profile(monkeypatch):
    """Profile provider knows nothing (and records that it was asked)."""
    calls = []

    def _none(symbol):
        calls.append(symbol)
        return None

    monkeypatch.setattr(ipo_age, "_profile_ipo_date", _none)
    return calls


# ---------------------------------------------------------------------------
# The SAIC case: frame truncated at the 2y fetch cap, no profile date
# ---------------------------------------------------------------------------

def test_truncated_frame_refuses_recent_ipo(monkeypatch, no_profile):
    monkeypatch.setattr(ipo_age, "load_prices", lambda s, period="max": _frame(729))
    out = ipo_age.age("SAIC")
    assert out is not None
    assert out["is_recent_ipo"] is None
    assert out["is_young"] is None
    assert out["first_trade_date"] is None
    assert out["years_since_ipo"] is None
    assert out["source"] is None
    assert no_profile == ["SAIC"]


def test_truncated_frame_uses_profile_when_available(monkeypatch):
    monkeypatch.setattr(ipo_age, "load_prices", lambda s, period="max": _frame(729))
    monkeypatch.setattr(ipo_age, "_profile_ipo_date", lambda s: "2013-09-16")
    out = ipo_age.age("SAIC")
    assert out["first_trade_date"] == "2013-09-16"
    assert out["source"] == "profile"
    assert out["is_recent_ipo"] is False
    assert out["is_young"] is False
    assert out["years_since_ipo"] > 10


@pytest.mark.parametrize("cap", sorted(PERIOD_DAYS.values()))
def test_every_fetch_cap_window_is_suspect(monkeypatch, no_profile, cap):
    monkeypatch.setattr(ipo_age, "load_prices", lambda s, period="max": _frame(cap))
    out = ipo_age.age("XXXX")
    assert out["is_recent_ipo"] is None, f"cap {cap} was trusted as a listing"
    assert out["source"] is None


# ---------------------------------------------------------------------------
# Genuine listings — first bar clear of every cap
# ---------------------------------------------------------------------------

def test_genuine_recent_ipo_inside_window(monkeypatch, no_profile):
    monkeypatch.setattr(ipo_age, "load_prices", lambda s, period="max": _frame(300))
    out = ipo_age.age("NEWCO")
    assert out["source"] == "history"
    assert out["is_recent_ipo"] is True
    assert out["is_young"] is True
    assert 0.7 < out["years_since_ipo"] < 0.9
    # the recent-IPO claim must have attempted a profile confirm
    assert no_profile == ["NEWCO"]


def test_profile_overrides_bars_that_merely_start_late(monkeypatch):
    # e.g. provider coverage gap / unstitched rename: bars begin 300d ago but
    # the profile knows the company listed in 2015 — no recent-IPO claim.
    monkeypatch.setattr(ipo_age, "load_prices", lambda s, period="max": _frame(300))
    monkeypatch.setattr(ipo_age, "_profile_ipo_date", lambda s: "2015-06-01")
    out = ipo_age.age("RENAMED")
    assert out["source"] == "profile"
    assert out["first_trade_date"] == "2015-06-01"
    assert out["is_recent_ipo"] is False
    assert out["is_young"] is False


def test_old_history_needs_no_profile_call(monkeypatch, no_profile):
    # 1200d sits clear of every cap window; >2y so no confirm needed either.
    monkeypatch.setattr(ipo_age, "load_prices", lambda s, period="max": _frame(1200))
    out = ipo_age.age("MIDCO")
    assert out["source"] == "history"
    assert out["is_recent_ipo"] is False
    assert out["is_young"] is True
    assert no_profile == []


# ---------------------------------------------------------------------------
# Negatives / edges
# ---------------------------------------------------------------------------

def test_no_prices_returns_none(monkeypatch):
    monkeypatch.setattr(ipo_age, "load_prices", lambda s, period="max": None)
    assert ipo_age.age("GONE") is None
    monkeypatch.setattr(ipo_age, "load_prices", lambda s, period="max": pd.DataFrame())
    assert ipo_age.age("EMPTY") is None


def test_future_profile_date_is_unknown(monkeypatch):
    monkeypatch.setattr(ipo_age, "load_prices", lambda s, period="max": _frame(730))
    future = (datetime.utcnow() + timedelta(days=40)).strftime("%Y-%m-%d")
    monkeypatch.setattr(ipo_age, "_profile_ipo_date", lambda s: future)
    out = ipo_age.age("WEIRD")
    assert out["is_recent_ipo"] is None
    assert out["source"] is None


def test_cap_guard_boundaries():
    assert ipo_age._at_fetch_cap(730)
    assert ipo_age._at_fetch_cap(730 - ipo_age._CAP_GUARD_DAYS)
    assert ipo_age._at_fetch_cap(730 + ipo_age._CAP_GUARD_DAYS)
    assert not ipo_age._at_fetch_cap(730 - ipo_age._CAP_GUARD_DAYS - 1)
    assert not ipo_age._at_fetch_cap(300)
    assert not ipo_age._at_fetch_cap(1200)


# ---------------------------------------------------------------------------
# Source guard — book thresholds stay locked (TLSW Ch. 11 p. 260)
# ---------------------------------------------------------------------------

def test_book_thresholds_unchanged():
    src = inspect.getsource(ipo_age)
    assert "years <= 8" in src, "is_young threshold drifted from TLSW's 8 years"
    assert "years <= 2" in src, "is_recent_ipo threshold drifted from 2 years"
