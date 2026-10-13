"""NYSE 2025 closures — 2026-10-13.

market_hours.reminder carried 2026 + 2027 only, so is_market_day (and
catalysts.medical.reaction.is_market_day, which wraps it) read Thanksgiving
2025-11-27 and Christmas 2025-12-25 as sessions. The Gajjala 250-session study
walks that window, so a closed day would have been counted as a bar.
These tests pin the 2025 list, the two open days around it, and that no
half day in supply_demand.timeframes is also a full closure.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from market_hours import reminder
from market_hours.reminder import ALL_HOLIDAYS, HOLIDAYS_2025, is_market_day

NYSE_2025_CLOSURES = [
    "2025-01-01",  # New Year's Day
    "2025-01-09",  # National Day of Mourning (President Carter)
    "2025-01-20",  # MLK Jr Day
    "2025-02-17",  # Presidents Day
    "2025-04-18",  # Good Friday
    "2025-05-26",  # Memorial Day
    "2025-06-19",  # Juneteenth
    "2025-07-04",  # Independence Day
    "2025-09-01",  # Labor Day
    "2025-11-27",  # Thanksgiving
    "2025-12-25",  # Christmas
]


def _noon(ymd: str) -> datetime:
    return datetime.strptime(ymd, "%Y-%m-%d").replace(hour=12)


@pytest.mark.parametrize("ymd", NYSE_2025_CLOSURES)
def test_every_2025_closure_is_not_a_market_day(ymd):
    d = _noon(ymd)
    assert d.weekday() < 5, f"{ymd} is a weekend — the list should hold weekday closures only"
    assert is_market_day(d) is False


def test_2025_set_is_exactly_the_nyse_list_and_folded_into_all():
    assert HOLIDAYS_2025 == set(NYSE_2025_CLOSURES)
    assert HOLIDAYS_2025 <= ALL_HOLIDAYS
    assert ALL_HOLIDAYS == reminder.HOLIDAYS_2025 | reminder.HOLIDAYS_2026 | reminder.HOLIDAYS_2027


def test_existing_years_survive_the_fold():
    assert "2026-11-26" in ALL_HOLIDAYS
    assert "2027-12-24" in ALL_HOLIDAYS


# ---- NEGATIVE: open days near the closures stay open ----------------------

def test_columbus_day_2025_is_open():
    assert is_market_day(_noon("2025-10-13")) is True


def test_day_after_thanksgiving_2025_is_open_half_day():
    assert is_market_day(_noon("2025-11-28")) is True


def test_ordinary_2025_weekday_is_open_and_weekend_is_closed():
    assert is_market_day(_noon("2025-11-26")) is True
    assert is_market_day(_noon("2025-11-29")) is False  # Saturday


def test_2024_is_not_covered_by_the_2025_list():
    assert not any(h.startswith("2024-") for h in ALL_HOLIDAYS)


# ---- the wrapper the medical reaction study uses --------------------------

def test_medical_reaction_wrapper_reads_2025_thanksgiving_as_closed():
    from catalysts.medical.reaction import is_market_day as med_imd
    assert med_imd(date(2025, 11, 27)) is False
    assert med_imd(date(2025, 12, 25)) is False
    assert med_imd(date(2025, 11, 28)) is True
    assert med_imd(date(2025, 10, 13)) is True


def test_medical_next_market_day_skips_2025_thanksgiving():
    from catalysts.medical.reaction import next_market_day
    assert next_market_day(date(2025, 11, 26)) == date(2025, 11, 28)
    assert next_market_day(date(2025, 12, 24)) == date(2025, 12, 26)


# ---- half days are never full closures ------------------------------------

def test_no_half_day_is_also_a_holiday():
    from supply_demand.timeframes import HALF_DAYS
    assert {"2025-07-03", "2025-11-28", "2025-12-24"} <= HALF_DAYS
    assert HALF_DAYS.isdisjoint(ALL_HOLIDAYS)
    for ymd in HALF_DAYS:
        assert is_market_day(_noon(ymd)) is True, ymd
