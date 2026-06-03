"""Locks the Massive-REST circuit-breaker in daytrading/data.py.

After a Massive REST outage froze the API event loop (2026-06-03), the breaker
trips after N consecutive failures and short-circuits fetches for a cooldown so a
dead provider returns instantly instead of stalling every caller.
"""
from daytrading import data as d


def _reset():
    d._CB["fails"] = 0
    d._CB["open_until"] = 0.0


def test_breaker_trips_after_threshold_then_cools_down():
    _reset()
    now = 1000.0
    for _ in range(d._CB_TRIP_AFTER - 1):
        d._cb_record(False, now)
    assert not d._cb_is_open(now)                              # not yet tripped
    d._cb_record(False, now)                                   # threshold hit
    assert d._cb_is_open(now)                                  # open now
    assert d._cb_is_open(now + d._CB_COOLDOWN_SEC - 1)         # still open during cooldown
    assert not d._cb_is_open(now + d._CB_COOLDOWN_SEC + 1)     # closed after cooldown


def test_success_resets_breaker():
    _reset()
    now = 2000.0
    for _ in range(d._CB_TRIP_AFTER):
        d._cb_record(False, now)
    assert d._cb_is_open(now)
    d._cb_record(True, now)                                    # a healthy response
    assert not d._cb_is_open(now)
    assert d._CB["fails"] == 0


def test_intermittent_failures_dont_trip():
    _reset()
    now = 3000.0
    d._cb_record(False, now)
    d._cb_record(True, now)        # success resets the counter
    d._cb_record(False, now)
    d._cb_record(False, now)
    assert not d._cb_is_open(now)  # only 2 in a row since the reset
