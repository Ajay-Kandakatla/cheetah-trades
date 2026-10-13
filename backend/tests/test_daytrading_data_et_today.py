"""daytrading/data.py — two shared-module fixes (Ajay round C: "fix all four", R1-11; 2026-10-13, WP1).

T1: `load_intraday` decided "today" by `datetime.utcnow().date()`, so from 19:00 EST (00:00 UTC) the live session read
as a COMPLETED day and its partial bars were cached in `intraday_cache` forever. It now uses the ET date.
T2: `_fetch_massive_minute` retried HTTP 429 with a bare `continue` and no cap — a persistent 429 hung the thread. It
now gives up after `_CB_TRIP_AFTER` consecutive 429s (the existing breaker constant) and records one failure.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from daytrading import data as D


def _bars_payload():
    return {"results": [{"t": 1795350600000, "o": 1.0, "h": 1.2, "l": 0.9, "c": 1.1, "v": 1000.0}]}


class _R:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body or {}
        self.text = ""

    def json(self):
        return self._body


@pytest.fixture(autouse=True)
def _reset_breaker(monkeypatch):
    D._CB["fails"] = 0
    D._CB["open_until"] = 0.0
    monkeypatch.setattr(D, "stocks_key", lambda: "k")
    monkeypatch.setattr(D.time, "sleep", lambda s: None)
    yield
    D._CB["fails"] = 0
    D._CB["open_until"] = 0.0


def _clock(monkeypatch, utc: datetime):
    """Freeze the module's `datetime` at a UTC instant (now(tz) converts; utcnow is naive UTC)."""
    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return utc.astimezone(tz) if tz else utc.replace(tzinfo=None)

        @classmethod
        def utcnow(cls):
            return utc.replace(tzinfo=None)
    monkeypatch.setattr(D, "datetime", _Frozen)


def _spy_cache(monkeypatch):
    puts = []
    monkeypatch.setattr(D, "_mongo_put_day", lambda sym, day, df: puts.append((sym, day)))
    monkeypatch.setattr(D, "_mongo_get_day", lambda sym, day: None)
    return puts


def test_load_intraday_today_is_et_date(monkeypatch):
    """2026-11-20 19:30 EST = 2026-11-21 00:30 UTC: the 11-20 session is still TODAY -> fetched, NOT cached."""
    _clock(monkeypatch, datetime(2026, 11, 21, 0, 30, tzinfo=timezone.utc))
    assert D._today_et() == date(2026, 11, 20)
    puts = _spy_cache(monkeypatch)
    monkeypatch.setattr(D, "_fetch_massive_minute", lambda s, a, b: D.pd.DataFrame(
        {"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1.0], "session": ["afterhours"]},
        index=D.pd.DatetimeIndex(["2026-11-21 00:29"])))
    df = D.load_intraday("AAA", date(2026, 11, 20), include_afterhours=True)
    assert df is not None and len(df) == 1
    assert puts == []


def test_NEGATIVE_completed_day_still_cached(monkeypatch):
    _clock(monkeypatch, datetime(2026, 11, 21, 0, 30, tzinfo=timezone.utc))
    puts = _spy_cache(monkeypatch)
    monkeypatch.setattr(D, "_fetch_massive_minute", lambda s, a, b: D.pd.DataFrame(
        {"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1.0], "session": ["rth"]},
        index=D.pd.DatetimeIndex(["2026-11-19 15:00"])))
    D.load_intraday("AAA", date(2026, 11, 19))
    assert puts == [("AAA", date(2026, 11, 19))]


def test_NEGATIVE_utc_date_would_have_cached_the_live_session(monkeypatch):
    """The old rule, spelled out: at this instant the UTC date is the 21st — the bug's 'today'."""
    _clock(monkeypatch, datetime(2026, 11, 21, 0, 30, tzinfo=timezone.utc))
    assert D.datetime.utcnow().date() == date(2026, 11, 21) != D._today_et()


def test_NEGATIVE_persistent_429_returns_none_after_cb_trip_after(monkeypatch):
    import requests
    calls = []

    def _get(url, params=None, timeout=None):
        calls.append(url)
        return _R(429)
    monkeypatch.setattr(requests, "get", _get)
    out = D._fetch_massive_minute("AAA", date(2026, 10, 12), date(2026, 10, 12))
    assert out is None
    assert len(calls) == D._CB_TRIP_AFTER
    assert D._CB["fails"] == 1                                  # one provider failure recorded toward the breaker


def test_a_single_429_then_200_still_returns_the_bars(monkeypatch):
    import requests
    seq = [_R(429), _R(200, _bars_payload())]
    monkeypatch.setattr(requests, "get", lambda url, params=None, timeout=None: seq.pop(0))
    out = D._fetch_massive_minute("AAA", date(2026, 11, 20), date(2026, 11, 20))
    assert out is not None and len(out) == 1
    assert D._CB["fails"] == 0


def test_NEGATIVE_429s_on_different_pages_do_not_accumulate(monkeypatch):
    """The cap counts CONSECUTIVE 429s: two pages each answering 429 x (cap-1) then 200 still finish."""
    import requests
    page2 = dict(_bars_payload(), next_url=None)
    page1 = dict(_bars_payload(), next_url="https://api.massive.com/next")
    n = D._CB_TRIP_AFTER - 1
    seq = [_R(429)] * n + [_R(200, page1)] + [_R(429)] * n + [_R(200, page2)]
    monkeypatch.setattr(requests, "get", lambda url, params=None, timeout=None: seq.pop(0))
    out = D._fetch_massive_minute("AAA", date(2026, 11, 20), date(2026, 11, 20))
    assert out is not None and not seq
