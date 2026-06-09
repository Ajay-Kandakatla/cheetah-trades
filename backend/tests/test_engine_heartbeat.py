"""Tests for the alert-engine staleness logic (observability/engine_heartbeat).

DISPLAY-only watchdog: tells the UI when the alert cron has stopped running
during market hours. We test the pure decision logic (market-hours window +
stale threshold) without touching Mongo.
"""
from __future__ import annotations

from datetime import datetime

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
