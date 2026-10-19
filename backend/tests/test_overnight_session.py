"""🌙 overnight.session — the Blue Ocean session clock (BUILD_SPEC16 §3.1, WP-A).

20:00–04:00 ET, the evening before each trade date; the ONE market calendar
(`market_hours.gate.closed_reason`) decides whether the trade date trades.
NEGATIVE cases: weekends, Thanksgiving eve, Labor Day eve, the hole between
sessions."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from overnight import session as S

ET = S.ET


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    from market_hours import gate
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)


def at(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=ET)


def test_sunday_2000_opens_the_monday_session_on_the_friday_base():
    s = S.session_for(at(2026, 10, 18, 20, 0))
    assert s["open"] is True and s["reason"] is None
    assert s["trade_date"] == date(2026, 10, 19)
    assert s["base_date"] == date(2026, 10, 16)
    assert s["opens_at"] == at(2026, 10, 18, 20, 0)
    assert s["closes_at"] == at(2026, 10, 19, 4, 0)
    assert s["next_open"] == at(2026, 10, 19, 20, 0)


def test_monday_0103_is_inside_the_session():
    s = S.session_for(at(2026, 10, 19, 1, 3))
    assert s["open"] is True
    assert s["trade_date"] == date(2026, 10, 19)
    assert s["base_date"] == date(2026, 10, 16)


def test_monday_0400_is_closed_and_the_next_opens_monday_2000():
    s = S.session_for(at(2026, 10, 19, 4, 0))
    assert s["open"] is False
    assert s["reason"] == "between sessions"
    assert s["trade_date"] is None and s["opens_at"] is None and s["closes_at"] is None
    assert s["next_open"] == at(2026, 10, 19, 20, 0)


def test_monday_0359_is_still_open():
    assert S.session_for(at(2026, 10, 19, 3, 59))["open"] is True


def test_friday_0359_is_open():
    s = S.session_for(at(2026, 10, 23, 3, 59))
    assert s["open"] is True and s["trade_date"] == date(2026, 10, 23)
    assert s["base_date"] == date(2026, 10, 22)


def test_friday_2000_is_closed_and_the_next_opens_sunday_2000():
    s = S.session_for(at(2026, 10, 23, 20, 0))
    assert s["open"] is False
    assert s["reason"] == "no session — weekend 2026-10-24"
    assert s["next_open"] == at(2026, 10, 25, 20, 0)


def test_negative_saturday_night_is_closed():
    s = S.session_for(at(2026, 10, 24, 21, 0))
    assert s["open"] is False
    assert "weekend" in s["reason"]
    assert s["next_open"] == at(2026, 10, 25, 20, 0)


def test_negative_sunday_0300_is_closed():
    s = S.session_for(at(2026, 10, 25, 3, 0))
    assert s["open"] is False
    assert s["next_open"] == at(2026, 10, 25, 20, 0)


def test_negative_thanksgiving_eve_has_no_session_and_the_next_opens_thursday_2000():
    s = S.session_for(at(2026, 11, 25, 20, 0))
    assert s["open"] is False
    # CHANGED 2026-10-19 (coordinator): the date is named ONCE (was "holiday 2026-11-26 2026-11-26").
    # market_hours exposes no holiday names, so the generic word is served.
    assert s["reason"] == "no session — holiday 2026-11-26"
    assert s["reason"].count("2026-11-26") == 1
    assert s["next_open"] == at(2026, 11, 26, 20, 0)


def test_thanksgiving_night_opens_the_friday_session_on_the_wednesday_base():
    s = S.session_for(at(2026, 11, 26, 20, 0))
    assert s["open"] is True
    assert s["trade_date"] == date(2026, 11, 27)
    assert s["base_date"] == date(2026, 11, 25)


def test_negative_labor_day_eve_is_closed():
    s = S.session_for(at(2026, 9, 6, 20, 0))
    assert s["open"] is False
    # CHANGED 2026-10-19 (coordinator): the date once.
    assert s["reason"] == "no session — holiday 2026-09-07"
    assert s["next_open"] == at(2026, 9, 7, 20, 0)


def test_labor_day_night_opens_the_tuesday_session_on_the_friday_base():
    s = S.session_for(at(2026, 9, 7, 20, 0))
    assert s["open"] is True
    assert s["trade_date"] == date(2026, 9, 8)
    assert s["base_date"] == date(2026, 9, 4)


def test_dst_end_sunday_opens_at_minus_five():
    s = S.session_for(at(2026, 11, 1, 20, 0))
    assert s["open"] is True
    assert s["opens_at"].utcoffset() == timedelta(hours=-5)
    assert s["opens_at"].isoformat().endswith("-05:00")


def test_naive_now_is_the_et_wall_clock():
    naive = S.session_for(datetime(2026, 10, 19, 1, 3))
    aware = S.session_for(at(2026, 10, 19, 1, 3))
    assert naive == aware
    assert S.et_now(datetime(2026, 10, 19, 1, 3)) == at(2026, 10, 19, 1, 3)


def test_an_aware_utc_instant_is_converted_to_et():
    # 2026-10-19 00:30 UTC = Sun 20:30 ET → inside the Monday session.
    s = S.session_for(datetime(2026, 10, 19, 0, 30, tzinfo=timezone.utc))
    assert s["open"] is True and s["trade_date"] == date(2026, 10, 19)
    # NEGATIVE: 2026-10-19 08:30 UTC = Mon 04:30 ET → closed (read as an ET wall
    # clock, 08:30 would also be closed, so pin 07:30 UTC = 03:30 ET → open instead).
    assert S.session_for(datetime(2026, 10, 19, 8, 30, tzinfo=timezone.utc))["open"] is False
    assert S.session_for(datetime(2026, 10, 19, 7, 30, tzinfo=timezone.utc))["open"] is True
    assert S.session_for(datetime(2026, 10, 19, 7, 30))["open"] is False   # naive 07:30 ET


def test_override_env_opens_a_holiday_night(monkeypatch):
    """Documents the ONE calendar's manual override: CHEETAH_IGNORE_HOLIDAY=1
    lifts the holiday (manual runs only — the crontab never sets it)."""
    from market_hours import gate
    monkeypatch.setenv(gate.OVERRIDE_ENV, "1")
    s = S.session_for(at(2026, 11, 25, 20, 0))
    assert s["open"] is True and s["trade_date"] == date(2026, 11, 26)


def test_et_is_the_one_eastern_zone():
    from supply_demand import zone_edge
    assert str(S.ET) == str(zone_edge.ET)


def test_session_hours_are_the_alpaca_doc_window():
    assert (S.SESSION_OPEN_ET.hour, S.SESSION_OPEN_ET.minute) == (20, 0)
    assert (S.SESSION_CLOSE_ET.hour, S.SESSION_CLOSE_ET.minute) == (4, 0)


def test_next_open_is_always_later_than_now_and_open_brackets_now():
    """Every 30 minutes across six weeks (Labor Day, the DST end, Thanksgiving)."""
    t = at(2026, 8, 30, 0, 0)
    end = at(2026, 12, 1, 0, 0)
    n_open = 0
    while t < end:
        s = S.session_for(t)
        assert s["next_open"] > t, t
        if s["open"]:
            n_open += 1
            assert s["opens_at"] <= t < s["closes_at"], t
            assert s["base_date"] < s["trade_date"]
        t += timedelta(minutes=30)
    assert n_open > 0
