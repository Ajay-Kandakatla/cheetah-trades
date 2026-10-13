"""catalysts/halts.py — "today" is the ET date (Ajay round C "fix all four", R1-11; 2026-10-13, Gajjala's tab WP2,
trap T3).

The feed stamps HaltDate on the ET clock, but `get_today_halts` filtered by the UTC date — so from 20:00 EDT / 19:00
EST every one of the session's halts vanished from the ⚡ frenzy radar, the catalysts page and (now) the ⏸ chip.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from catalysts import halts as H


def _item(sym, halt_date, reason="LUDP"):
    return (f"<item><ndaq:IssueSymbol>{sym}</ndaq:IssueSymbol><ndaq:IssueName>{sym} Inc</ndaq:IssueName>"
            f"<ndaq:ReasonCode>{reason}</ndaq:ReasonCode><ndaq:HaltDate>{halt_date}</ndaq:HaltDate>"
            f"<ndaq:HaltTime>15:01:02</ndaq:HaltTime><ndaq:ResumptionDate>{halt_date}</ndaq:ResumptionDate>"
            f"<ndaq:ResumptionTradeTime>15:06:02</ndaq:ResumptionTradeTime></item>")


class _R:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status


def _clock(monkeypatch, utc: datetime):
    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return utc.astimezone(tz) if tz else utc.replace(tzinfo=None)
    monkeypatch.setattr(H, "datetime", _Frozen)


@pytest.fixture(autouse=True)
def _fresh_cache():
    H._cache.update(data=None, ts=0.0)
    yield
    H._cache.update(data=None, ts=0.0)


def _feed(monkeypatch, body):
    monkeypatch.setattr(H.requests, "get", lambda *a, **k: _R(body))


def test_a_halt_dated_today_counts_at_1930_est(monkeypatch):
    """2026-11-20 19:30 EST = 2026-11-21 00:30 UTC: the 11/20 halts are still TODAY's."""
    _clock(monkeypatch, datetime(2026, 11, 21, 0, 30, tzinfo=timezone.utc))
    _feed(monkeypatch, "<rss>" + _item("AAA", "11/20/2026") + _item("AAA", "11/20/2026", "T1") + "</rss>")
    out = H.get_today_halts(force=True)
    assert out["session_date"] == "2026-11-20"
    assert out["by_ticker"]["AAA"]["n_halts"] == 2
    assert out["by_ticker"]["AAA"]["reasons"] == ["LUDP", "T1"]
    assert out["n_halts"] == 2


def test_NEGATIVE_a_halt_from_the_day_before_is_excluded(monkeypatch):
    _clock(monkeypatch, datetime(2026, 11, 21, 0, 30, tzinfo=timezone.utc))
    _feed(monkeypatch, "<rss>" + _item("OLD", "11/19/2026") + _item("NEW", "11/20/2026") + "</rss>")
    out = H.get_today_halts(force=True)
    assert set(out["by_ticker"]) == {"NEW"}


def test_NEGATIVE_the_utc_date_is_not_today_after_8pm_edt(monkeypatch):
    """2026-10-13 20:30 EDT = 10-14 00:30 UTC — the UTC date (10/14) has no halts yet; the ET date (10/13) does."""
    _clock(monkeypatch, datetime(2026, 10, 14, 0, 30, tzinfo=timezone.utc))
    _feed(monkeypatch, "<rss>" + _item("AAA", "10/13/2026") + _item("ZZZ", "10/14/2026") + "</rss>")
    out = H.get_today_halts(force=True)
    assert out["session_date"] == "2026-10-13" and set(out["by_ticker"]) == {"AAA"}


def test_midday_still_reads_the_same_day(monkeypatch):
    _clock(monkeypatch, datetime(2026, 10, 13, 15, 0, tzinfo=timezone.utc))   # 11:00 EDT
    _feed(monkeypatch, "<rss>" + _item("AAA", "10/13/2026") + "</rss>")
    assert set(H.get_today_halts(force=True)["by_ticker"]) == {"AAA"}
    assert H.get_ticker_halts("aaa")["n_halts"] == 1


def test_NEGATIVE_feed_failure_is_an_empty_day_not_a_raise(monkeypatch):
    _clock(monkeypatch, datetime(2026, 10, 13, 15, 0, tzinfo=timezone.utc))

    def boom(*a, **k):
        raise RuntimeError("network refused")
    monkeypatch.setattr(H.requests, "get", boom)
    out = H.get_today_halts(force=True)
    assert out["by_ticker"] == {} and out["n_total"] == 0
