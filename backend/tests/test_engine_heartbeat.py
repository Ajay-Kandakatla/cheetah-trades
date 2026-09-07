"""Tests for the alert-engine staleness logic (observability/engine_heartbeat).

DISPLAY-only watchdog: tells the UI when the alert cron has stopped running
during market hours. We test the pure decision logic (market-hours window +
stale threshold) without touching Mongo.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from observability import engine_heartbeat as hb


def _et(y, m, d, hh, mm):
    if hb._ET:
        return datetime(y, m, d, hh, mm, tzinfo=hb._ET)
    return datetime(y, m, d, hh, mm)


def test_market_open_window():
    # 2026-06-09 is a Tuesday.
    assert hb._market_open(_et(2026, 6, 9, 9, 30)) is True     # open bell
    assert hb._market_open(_et(2026, 6, 9, 12, 0)) is True
    assert hb._market_open(_et(2026, 6, 9, 16, 0)) is True     # close
    assert hb._market_open(_et(2026, 6, 9, 9, 29)) is False    # pre-open
    assert hb._market_open(_et(2026, 6, 9, 16, 1)) is False    # after close
    # 2026-06-13 is a Saturday.
    assert hb._market_open(_et(2026, 6, 13, 11, 0)) is False


def test_to_epoch_accepts_iso_and_number():
    assert hb._to_epoch(1_700_000_000) == 1_700_000_000.0
    iso = hb._to_epoch("2026-06-09T14:30:00+00:00")
    assert iso is not None and abs(iso - 1781015400.0) < 2
    assert hb._to_epoch(None) is None
    assert hb._to_epoch("not-a-date") is None


def test_threshold_is_two_missed_cycles():
    # alerts run every 5 min; the stale threshold should be > one cycle.
    assert hb.ALERTS_STALE_SEC >= 10 * 60


# 2026-09-07 (Labor Day): the gate skips the alerts cron on closed days, so the
# banner must read the SAME calendar or it tells him to restart cron on a holiday.
def test_market_open_is_false_on_a_weekday_holiday(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    assert hb._market_open(_et(2026, 9, 7, 10, 0)) is False    # Labor Day, Monday
    assert hb._market_open(_et(2026, 9, 8, 10, 0)) is True     # the next trading day
    assert hb._market_open(_et(2026, 11, 26, 10, 0)) is False  # Thanksgiving


def test_engine_status_is_not_stale_on_a_closed_day_even_with_an_old_beat(monkeypatch):
    monkeypatch.setattr(hb, "_market_open", lambda now=None: False)
    monkeypatch.setattr(hb, "_last_beat", lambda name="alerts": hb._now_epoch() - 6 * 3600)
    s = hb.engine_status()
    assert s["market_open"] is False and s["stale"] is False and s["stale_reason"] is None


def test_engine_status_still_flags_a_dead_engine_on_a_trading_day(monkeypatch):
    monkeypatch.setattr(hb, "_market_open", lambda now=None: True)
    monkeypatch.setattr(hb, "_last_beat", lambda name="alerts": hb._now_epoch() - 6 * 3600)
    s = hb.engine_status()
    assert s["stale"] is True and "last ran" in (s["stale_reason"] or "")
