"""🔑 Key levels engine (2026-09-25) — `supply_demand/key_levels.py`.

Pins the spec v2 §3.1–§3.4 semantics on synthetic frames: which period a
level comes from (the last COMPLETE week / the prior calendar month / the last
YEAR_BARS closed bars), the 20:00 roll, the state window, the pre-market
filter, the fresh-print engines, the per-member break states before and after
the close-confirm minute, merge-for-drawing, the cap, the guards, the payload
and the constant pins + import guard. Positive AND negative cases. Stubs only
— the conftest refuses Mongo.
"""
from __future__ import annotations

import json
import math
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from supply_demand import key_levels as KL

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------
def _market_days(end: str, n: int) -> list[pd.Timestamp]:
    from market_hours.reminder import ALL_HOLIDAYS
    out = []
    d = pd.Timestamp(end)
    while len(out) < n:
        if d.weekday() < 5 and d.strftime("%Y-%m-%d") not in ALL_HOLIDAYS:
            out.append(d)
        d -= pd.Timedelta(days=1)
    return sorted(out)


def _frame(end: str, n: int = 60, *, close=100.0, high=101.0, low=99.0, sets=None) -> pd.DataFrame:
    idx = pd.DatetimeIndex(_market_days(end, n))
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close,
                       "volume": 1_000_000.0}, index=idx)
    for day, vals in (sets or {}).items():
        for k, v in vals.items():
            df.loc[pd.Timestamp(day), k] = v
    return df


def _at(y, mo, d, h=12, mi=0, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=ET)


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _ns(dt: datetime) -> int:
    return int(dt.timestamp() * 1e9)


def _row(*, px=None, ts=None, open_=None, high=None, low=None, close=None, pdc=None) -> dict:
    return {"open": open_, "high": high, "low": low, "close": close,
            "last_trade_price": px, "last_trade_ts_ms": ts, "prev_day_close": pdc}


def _lvl(period="week", kind="low", price=100.0, as_of="2026-09-18"):
    m = KL._member(period, kind, price, as_of)
    assert m is not None
    return m


def _state(level, *, ref, row, now, first=None, sym="AAA"):
    return KL.member_state(level, ref_close=ref, row=row, now=now,
                           session=now.date(), first=first, symbol=sym)


def _by_id(levels, prefix):
    return [lv for lv in levels if lv["id"].startswith(prefix)]


# --------------------------------------------------------------------------
# periods
# --------------------------------------------------------------------------
def test_week_is_the_last_COMPLETE_week_on_a_monday_and_a_wednesday():
    df = _frame("2026-09-22", sets={"2026-09-16": {"high": 110.0},
                                    "2026-09-22": {"high": 120.0}})
    mon = date(2026, 9, 21)
    lv = KL.period_levels(KL.closed_frame(df, mon), mon, ("week",))
    wh = _by_id(lv, "week_high")[0]
    assert wh["price"] == 110.0 and wh["as_of"] == "2026-09-18"
    wed = date(2026, 9, 23)
    lv = KL.period_levels(KL.closed_frame(df, wed), wed, ("week",))
    wh = _by_id(lv, "week_high")[0]
    # NEGATIVE: the running week's 120 (Tue 09-22) is never the prior-week high.
    assert wh["price"] == 110.0 and wh["as_of"] == "2026-09-18"
    assert wh["id"] == "week_high_11000" and wh["label"] == "PWH"
    assert wh["name"] == "prior-week high"


def test_first_session_of_a_month_reads_the_whole_prior_month():
    df = _frame("2026-09-30", n=80, sets={"2026-08-14": {"high": 130.0},
                                          "2026-09-10": {"high": 115.0},
                                          "2026-09-02": {"low": 80.0}})
    oct1 = date(2026, 10, 1)
    lv = KL.period_levels(KL.closed_frame(df, oct1), oct1, ("month",))
    mh, ml = _by_id(lv, "month_high")[0], _by_id(lv, "month_low")[0]
    assert (mh["price"], ml["price"], mh["as_of"]) == (115.0, 80.0, "2026-09-30")
    # NEGATIVE: on the LAST session of September the prior month is August.
    sep30 = date(2026, 9, 30)
    lv = KL.period_levels(KL.closed_frame(df, sep30), sep30, ("month",))
    assert _by_id(lv, "month_high")[0]["price"] == 130.0
    assert _by_id(lv, "month_high")[0]["as_of"] == "2026-08-31"


def test_holiday_shortened_week_uses_its_four_sessions():
    df = _frame("2026-09-11", sets={"2026-09-04": {"low": 90.0},
                                    "2026-09-09": {"low": 95.0}})
    s = date(2026, 9, 14)
    lv = KL.period_levels(KL.closed_frame(df, s), s, ("week",))
    wl = _by_id(lv, "week_low")[0]
    assert wl["price"] == 95.0 and wl["as_of"] == "2026-09-11"      # 09-04 (prior week) excluded
    assert pd.Timestamp("2026-09-07") not in df.index                 # Labor Day is not a bar


def test_251_bars_NO_year_levels_252_bars_year_levels_pinned_to_zone_store():
    from supply_demand import zone_store
    s = date(2026, 9, 25)
    rng = np.random.default_rng(3)
    df = _frame("2026-09-24", n=300)
    df["high"] = 100 + rng.random(len(df)) * 20
    df["low"] = 80 + rng.random(len(df)) * 10
    short = df.tail(251)
    assert _by_id(KL.period_levels(KL.closed_frame(short, s), s, ("year",)), "year") == []
    full = df.tail(252)
    lv = KL.period_levels(KL.closed_frame(full, s), s, ("year",))
    yh, yl = _by_id(lv, "year_high")[0], _by_id(lv, "year_low")[0]
    doc = zone_store.build_doc("AAA", df, s, compute=lambda f: {}, atr=lambda f: None)
    assert yh["price"] == pytest.approx(doc["high_252"], abs=1e-4)
    closed = KL.closed_frame(df, s)
    assert yl["price"] == pytest.approx(float(closed["low"].tail(252).min()), abs=1e-4)
    assert yh["set_on"] == closed["high"].tail(252).idxmax().date().isoformat()
    assert yh["as_of"] == "2026-09-24" and yh["label"] == "52wH"
    assert yh["last_close_cross"] is None


def test_NEGATIVE_todays_partial_row_with_a_spike_never_becomes_a_level_tz_aware_too():
    s = date(2026, 9, 23)
    df = _frame("2026-09-23", sets={"2026-09-23": {"high": 999.0, "low": 1.0}})
    naive = KL.period_levels(KL.closed_frame(df, s), s, ("day", "week", "month"))
    assert all(lv["price"] not in (999.0, 1.0) for lv in naive)
    assert _by_id(naive, "day_high")[0]["as_of"] == "2026-09-22"
    tz = df.copy()
    tz.index = tz.index.tz_localize("America/New_York").tz_convert("UTC")
    aware = KL.period_levels(KL.closed_frame(tz, s), s, ("day", "week", "month"))
    assert [(lv["id"], lv["as_of"]) for lv in aware] == [(lv["id"], lv["as_of"]) for lv in naive]


def test_last_close_cross_is_the_latest_close_through_after_the_period():
    df = _frame("2026-09-24", sets={"2026-09-15": {"low": 95.0},
                                    "2026-09-22": {"close": 94.0},
                                    "2026-09-23": {"close": 96.0}})
    s = date(2026, 9, 25)
    wl = _by_id(KL.period_levels(KL.closed_frame(df, s), s, ("week",)), "week_low")[0]
    assert wl["price"] == 95.0
    assert wl["last_close_cross"] == {"date": "2026-09-23", "direction": "up"}
    # NEGATIVE: a level no close ever crossed carries none.
    wh = _by_id(KL.period_levels(KL.closed_frame(df, s), s, ("week",)), "week_high")[0]
    assert wh["last_close_cross"] is None


# --------------------------------------------------------------------------
# cadence
# --------------------------------------------------------------------------
@pytest.mark.parametrize("now,expected", [
    (_at(2026, 9, 24, 19, 59), date(2026, 9, 24)),
    (_at(2026, 9, 24, 20, 0), date(2026, 9, 25)),
    (_at(2026, 9, 26, 10, 0), date(2026, 9, 28)),     # Saturday -> Monday
    (_at(2026, 11, 25, 20, 0), date(2026, 11, 27)),   # before Thanksgiving -> the day after
    (_at(2026, 9, 4, 20, 0), date(2026, 9, 8)),       # Friday before Labor Day
    (_at(2026, 9, 7, 10, 0), date(2026, 9, 8)),       # ON the holiday
    (_at(2026, 9, 24, 3, 0), date(2026, 9, 24)),
])
def test_levels_session_rolls_at_2000_and_skips_closed_days(now, expected):
    assert KL.levels_session(now) == expected


def test_prev_market_day_skips_weekends_and_holidays():
    assert KL.prev_market_day(date(2026, 9, 8)) == date(2026, 9, 4)
    assert KL.prev_market_day(date(2026, 9, 28)) == date(2026, 9, 25)
    assert KL.prev_market_day(date(2026, 11, 27)) == date(2026, 11, 25)


@pytest.mark.parametrize("hm,expected", [
    ((3, 59), None), ((4, 0), "pre"), ((9, 29), "pre"), ((9, 30), "rth"),
    ((16, 4), "rth"), ((16, 5), "close"), ((19, 59), "close"), ((20, 0), None),
])
def test_phase_window(hm, expected):
    now = _at(2026, 9, 24, *hm)
    assert KL.phase(now, date(2026, 9, 24)) == expected


def test_phase_half_day_and_closed_days():
    assert KL.phase(_at(2026, 11, 27, 13, 5), date(2026, 11, 27)) == "close"
    assert KL.phase(_at(2026, 11, 27, 12, 59), date(2026, 11, 27)) == "rth"
    assert KL.close_confirm_at(date(2026, 11, 27)) == KL.CLOSE_CONFIRM_AT_HALF
    assert KL.close_confirm_at(date(2026, 9, 24)) == KL.CLOSE_CONFIRM_AT
    # NEGATIVE: Saturday, a holiday, and a session that is not today.
    assert KL.phase(_at(2026, 9, 26, 12, 0), date(2026, 9, 26)) is None
    assert KL.phase(_at(2026, 9, 7, 12, 0), date(2026, 9, 7)) is None
    assert KL.phase(_at(2026, 9, 24, 21, 0), date(2026, 9, 25)) is None


# --------------------------------------------------------------------------
# pre-market
# --------------------------------------------------------------------------
PRE_BARS = [
    {"t": "2026-09-24 08:00", "s": "pre", "h": 50.0, "l": 5.0},     # yesterday's pre (24h frame)
    {"t": "2026-09-24 17:00", "s": "ah", "h": 45.0, "l": 6.0},
    {"t": "2026-09-25 04:05", "s": "pre", "h": 20.5, "l": 19.8},
    {"t": "2026-09-25 09:30", "s": "pre", "h": 21.2, "l": 19.5},    # the 09:25-09:29 bar, stamped 09:30
    {"t": "2026-09-25 09:35", "h": 30.0, "l": 10.0},                 # RTH
]


def test_premarket_includes_the_0930_stamped_pre_bar_and_excludes_rth_and_yesterday():
    lv = KL.premarket_levels(PRE_BARS, date(2026, 9, 25), _at(2026, 9, 25, 10, 0))
    got = {m["id"].rsplit("_", 1)[0]: m["price"] for m in lv}
    assert got == {"pre_high": 21.2, "pre_low": 19.5}
    assert {m["label"] for m in lv} == {"pre-mkt H", "pre-mkt L"}


def test_NEGATIVE_premarket_is_empty_before_0930_and_without_pre_bars():
    assert KL.premarket_levels(PRE_BARS, date(2026, 9, 25), _at(2026, 9, 25, 9, 29)) == []
    rth_only = [b for b in PRE_BARS if b.get("s") != "pre"]
    assert KL.premarket_levels(rth_only, date(2026, 9, 25), _at(2026, 9, 25, 10, 0)) == []
    assert KL.premarket_levels(None, date(2026, 9, 25), _at(2026, 9, 25, 10, 0)) == []


# --------------------------------------------------------------------------
# fresh print
# --------------------------------------------------------------------------
def test_NEGATIVE_last_evenings_print_at_0400_is_not_fresh_and_the_state_is_unknown():
    now = _at(2026, 9, 25, 4, 0)
    row = _row(px=90.0, ts=_ms(_at(2026, 9, 24, 19, 59)))
    assert KL.fresh_print(row, now, now.date()) is None
    st = _state(_lvl(price=100.0), ref=101.0, row=row, now=now)
    assert st["state"] == "unknown"


def test_a_0402_print_beyond_is_broken_and_the_chip_says_pre_mkt():
    now = _at(2026, 9, 25, 4, 2, 30)
    row = _row(px=99.0, ts=_ms(_at(2026, 9, 25, 4, 2)))
    lv = KL.read_levels([_lvl(price=100.0)], symbol="AAA", ref_close=101.0, row=row,
                        now=now, session=now.date(), first_seen={})
    assert lv[0]["state"] == "broken"
    c = KL.chip(lv, "pre")
    assert c["text"].endswith(" · pre-mkt") and c["tone"] == "warn"
    assert c["text"].startswith("🔑 broke PWL 100.00 ↓")


def test_NEGATIVE_a_print_181_s_old_is_not_fresh_179_is():
    now = _at(2026, 9, 25, 11, 0, 0)
    old = _row(px=99.0, ts=_ms(_at(2026, 9, 25, 10, 56, 59)))
    new = _row(px=99.0, ts=_ms(_at(2026, 9, 25, 10, 57, 1)))
    assert KL.fresh_print(old, now, now.date()) is None
    assert KL.fresh_print(new, now, now.date()) == 99.0


def test_ns_and_ms_stamps_both_work():
    now = _at(2026, 9, 25, 11, 0)
    t = _at(2026, 9, 25, 10, 59)
    assert KL.fresh_print(_row(px=98.5, ts=_ms(t)), now, now.date()) == 98.5
    assert KL.fresh_print(_row(px=98.5, ts=_ns(t)), now, now.date()) == 98.5
    # NEGATIVE: a fresh stamp but the wrong session date.
    assert KL.fresh_print(_row(px=98.5, ts=_ms(t)), now, date(2026, 9, 28)) is None


# --------------------------------------------------------------------------
# live states (pre / rth)
# --------------------------------------------------------------------------
NOW_RTH = _at(2026, 9, 25, 11, 0)
TS_RTH = _ms(_at(2026, 9, 25, 10, 59))


@pytest.mark.parametrize("kind,ref,px_014,px_015", [
    ("low", 101.0, 99.86, 99.85),
    ("high", 99.0, 100.14, 100.15),
])
def test_014_pct_beyond_is_NOT_broken_015_is(kind, ref, px_014, px_015):
    lvl = _lvl(kind=kind, price=100.0)
    near = _state(lvl, ref=ref, row=_row(px=px_014, ts=TS_RTH), now=NOW_RTH)
    assert near["state"] != "broken"
    far = _state(lvl, ref=ref, row=_row(px=px_015, ts=TS_RTH), now=NOW_RTH)
    assert far["state"] == "broken"
    assert far["direction"] == ("down" if kind == "low" else "up")


def test_pierced_then_print_inside_the_buffer_is_pierced_no_chip():
    row = _row(px=99.95, ts=TS_RTH, low=99.50, high=101.0, open_=100.5, close=99.95)
    lv = KL.read_levels([_lvl(price=100.0)], symbol="AAA", ref_close=101.0, row=row,
                        now=NOW_RTH, session=NOW_RTH.date(), first_seen={})
    assert lv[0]["state"] == "pierced"
    assert KL.chip(lv, "rth") is None


def test_pierced_then_print_back_inside_is_a_reversal_no_chip():
    row = _row(px=100.30, ts=TS_RTH, low=99.50, high=101.0, open_=100.5, close=100.30)
    first = {KL.first_seen_key("AAA", "week_low_10000", "down", "reversal"): "10:40"}
    lv = KL.read_levels([_lvl(price=100.0)], symbol="AAA", ref_close=101.0, row=row,
                        now=NOW_RTH, session=NOW_RTH.date(), first_seen=first)
    assert lv[0]["state"] == "reversal" and lv[0]["reversal_at"] == "10:40"
    assert KL.chip(lv, "rth") is None
    assert "reversal 10:40" in KL.fold_text(lv, frame="daily", stale_note=None)


def test_a_through_stamp_counts_as_pierced_even_without_the_day_low():
    first = {KL.first_seen_key("AAA", "week_low_10000", "down", "through"): "04:12"}
    st = _state(_lvl(price=100.0), ref=101.0, row=_row(px=100.05, ts=TS_RTH),
                now=NOW_RTH, first=first)
    assert st["state"] == "pierced" and st["first_through"] == "04:12"


def test_gap_on_an_open_beyond_changes_the_chip_wording():
    row = _row(px=99.2, ts=TS_RTH, open_=99.0, low=98.8, high=99.5, close=99.2)
    lv = KL.read_levels([_lvl(price=100.0)], symbol="AAA", ref_close=101.0, row=row,
                        now=NOW_RTH, session=NOW_RTH.date(), first_seen={})
    assert lv[0]["state"] == "broken" and lv[0]["gap"] is True
    assert KL.chip(lv, "rth")["text"] == "🔑 gapped through PWL 100.00 ↓"
    # NEGATIVE: an open inside the level is no gap.
    row["open"] = 100.5
    lv = KL.read_levels([_lvl(price=100.0)], symbol="AAA", ref_close=101.0, row=row,
                        now=NOW_RTH, session=NOW_RTH.date(), first_seen={})
    assert lv[0]["gap"] is False


def test_broke_chip_carries_the_first_through_time_only_when_known():
    row = _row(px=99.0, ts=TS_RTH, low=98.9, high=101.0, open_=100.5, close=99.0)
    first = {KL.first_seen_key("AAA", "week_low_10000", "down", "through"): "10:42"}
    lv = KL.read_levels([_lvl(price=100.0)], symbol="AAA", ref_close=101.0, row=row,
                        now=NOW_RTH, session=NOW_RTH.date(), first_seen=first)
    assert KL.chip(lv, "rth")["text"] == "🔑 broke PWL 100.00 ↓ 10:42"
    lv = KL.read_levels([_lvl(price=100.0)], symbol="AAA", ref_close=101.0, row=row,
                        now=NOW_RTH, session=NOW_RTH.date(), first_seen={})
    assert KL.chip(lv, "rth")["text"] == "🔑 broke PWL 100.00 ↓"


def test_a_pwh_cleared_earlier_this_week_reads_as_support_down():
    st = _state(_lvl(kind="high", price=100.0), ref=102.0,
                row=_row(px=101.5, ts=TS_RTH, low=101.0, high=102.5), now=NOW_RTH)
    assert (st["side"], st["direction"]) == ("support", "down")
    assert st["state"] == "intact"


def test_chip_precedence_highest_rank_then_the_count():
    row = _row(px=90.0, ts=TS_RTH, low=89.0, high=101.0, open_=100.5, close=90.0)
    lvls = [_lvl("week", "low", 100.0), _lvl("month", "low", 95.0)]
    lv = KL.read_levels(lvls, symbol="AAA", ref_close=101.0, row=row,
                        now=NOW_RTH, session=NOW_RTH.date(), first_seen={})
    assert KL.chip(lv, "rth")["text"] == "🔑 broke PML 95.00 ↓ +1"


# --------------------------------------------------------------------------
# close phase
# --------------------------------------------------------------------------
NOW_CLOSE = _at(2026, 9, 25, 16, 10)


def _close_read(close, *, low=99.50, px=None, ts=None, now=NOW_CLOSE):
    row = _row(px=px, ts=ts, low=low, high=101.0, open_=100.5, close=close)
    return KL.read_levels([_lvl(price=100.0)], symbol="AAA", ref_close=101.0, row=row,
                          now=now, session=now.date(), first_seen={})


def test_close_inside_the_buffer_after_a_pierce_is_TESTED_never_broke():
    lv = _close_read(100.10)
    assert lv[0]["state"] == "tested" and lv[0]["closed_beyond"] is False
    assert KL.chip(lv, "close") is None
    assert "broke" not in (KL.fold_text(lv, frame="daily", stale_note=None) or "")


def test_close_back_inside_after_a_pierce_is_a_reversal():
    lv = _close_read(100.20)
    assert lv[0]["state"] == "reversal" and KL.chip(lv, "close") is None


def test_close_through_is_closed_beyond_and_the_chip_says_closed_under():
    lv = _close_read(99.80)
    assert lv[0]["state"] == "closed_beyond" and lv[0]["closed_beyond"] is True
    assert KL.chip(lv, "close")["text"] == "🔑 closed under PWL 100.00"


def test_closed_back_over_wording_for_a_low_crossed_upward():
    row = _row(low=99.0, high=100.5, open_=99.2, close=100.4)
    lv = KL.read_levels([_lvl(price=100.0)], symbol="AAA", ref_close=99.0, row=row,
                        now=NOW_CLOSE, session=NOW_CLOSE.date(), first_seen={})
    assert KL.chip(lv, "close")["text"] == "🔑 closed back over PWL 100.00"


def test_after_hours_print_through_with_a_close_inside_is_ah_through():
    now = _at(2026, 9, 25, 17, 0)
    lv = _close_read(100.20, px=99.70, ts=_ms(_at(2026, 9, 25, 16, 59)), now=now)
    assert lv[0]["state"] == "reversal" and lv[0]["ah_through"] is True
    assert KL.chip(lv, "close")["text"] == "🔑 after-hrs under PWL 100.00"
    # NEGATIVE: an RTH-stamped print is not an after-hours print.
    lv = _close_read(100.20, px=99.70, ts=_ms(_at(2026, 9, 25, 15, 59, 30)),
                     now=_at(2026, 9, 25, 16, 1))
    assert lv[0]["ah_through"] is False


def test_NEGATIVE_closed_beyond_is_null_before_the_close_confirm_minute():
    now = _at(2026, 9, 25, 16, 4)
    lv = _close_read(99.80, now=now)
    assert lv[0]["closed_beyond"] is None and lv[0]["state"] != "closed_beyond"


# --------------------------------------------------------------------------
# merge for drawing
# --------------------------------------------------------------------------
def test_same_side_members_merge_but_state_stays_per_member():
    lvls = [_lvl("week", "low", 99.75), _lvl("day", "low", 100.00)]
    row = _row(px=99.80, ts=TS_RTH, low=99.80, high=101.0, open_=100.5, close=99.80)
    lv = KL.read_levels(lvls, symbol="AAA", ref_close=101.0, row=row,
                        now=NOW_RTH, session=NOW_RTH.date(), first_seen={})
    st = {m["id"]: m["state"] for m in lv}
    assert st["day_low_10000"] == "broken"
    # The spec's prose says "intact"; the §3.3 table it points to makes a low
    # 0.05% above PWL "tested" (within AT_LEVEL_PCT, never beyond). Either
    # way the member is NOT broken and NOT pierced — that is what is pinned.
    assert st["week_low_9975"] == "tested"
    cl = KL.merge_for_draw(lv, 101.0)
    assert len(cl) == 1
    assert cl[0]["tone"] == KL.TONE_BROKEN
    assert cl[0]["price"] == 99.75 and cl[0]["label"] == "PWL = PDL"
    assert cl[0]["ids"] == ["week_low_9975", "day_low_10000"]


def test_NEGATIVE_members_on_opposite_sides_of_the_close_never_merge():
    lvls = [_lvl("day", "low", 50.00), _lvl("week", "high", 50.12)]
    row = _row(px=49.90, ts=TS_RTH, low=49.90, high=50.10, open_=50.05, close=49.90)
    lv = KL.read_levels(lvls, symbol="AAA", ref_close=50.05, row=row,
                        now=NOW_RTH, session=NOW_RTH.date(), first_seen={})
    cl = KL.merge_for_draw(lv, 50.05)
    assert len(cl) == 2
    st = {m["id"]: m["state"] for m in lv}
    assert st["day_low_5000"] == "broken" and st["week_high_5012"] != "broken"
    tones = {c["label"]: c["tone"] for c in cl}
    assert tones == {"PDL": KL.TONE_BROKEN, "PWH": KL.TONE}


def test_merge_tolerance_029_merges_031_does_not():
    a = _lvl("week", "low", 100.0)
    assert len(KL.merge_for_draw([a, _lvl("day", "low", 100.29)], 105.0)) == 1
    assert len(KL.merge_for_draw([a, _lvl("day", "low", 100.31)], 105.0)) == 2


# --------------------------------------------------------------------------
# cap
# --------------------------------------------------------------------------
def _cl(price, ids):
    return {"price": price, "label": "x", "ids": ids, "tone": KL.TONE}


def test_cap_keeps_the_nearest_per_side_and_ties_go_to_the_higher_rank():
    cls = [_cl(105, ["week_high_10500"]), _cl(110, ["month_high_11000"]),
           _cl(120, ["year_high_12000"]), _cl(95, ["week_low_9500"]),
           _cl(90, ["month_low_9000"]), _cl(80, ["year_low_8000"])]
    one = KL.rank_for_chart(cls, 100.0, KL.GRID_PER_SIDE)
    assert sorted(c["price"] for c in one) == [95, 105]
    two = KL.rank_for_chart(cls, 100.0, KL.SUPPORT_PER_SIDE)
    assert sorted(c["price"] for c in two) == [90, 95, 105, 110]
    tie = KL.rank_for_chart([_cl(105, ["day_high_10500"]), _cl(105, ["month_high_10500"])],
                            100.0, 1)
    assert tie[0]["ids"] == ["month_high_10500"]
    # NEGATIVE: a zero cap draws nothing.
    assert KL.rank_for_chart(cls, 100.0, 0) == []


def _tile_now(close=100.0):
    return _row(px=close, ts=TS_RTH, low=close - 0.5, high=close + 0.5, open_=close,
                close=close, pdc=100.0)


def test_undrawn_members_stay_in_the_block_and_the_fold():
    df = _frame("2026-09-24", n=300, sets={"2026-09-16": {"high": 104.0, "low": 97.0},
                                           "2026-08-12": {"high": 108.0, "low": 94.0},
                                           "2026-03-04": {"high": 131.2, "low": 70.0}})
    block, lines = KL.tile_block("AAA", df, frame="daily", row=_tile_now(),
                                 now=NOW_RTH, per_side=KL.GRID_PER_SIDE)
    assert len(lines) == 2
    assert len(block["levels"]) == 6
    undrawn = [lv for lv in block["levels"] if not lv["drawn"]]
    assert len(undrawn) == 4
    for lv in undrawn:
        assert f"{lv['label']} {lv['price']:.2f}" in block["fold"]
    assert "(set 03-04)" in block["fold"]
    assert block["fold"].startswith("🔑 RTH levels · ")
    block2, lines2 = KL.tile_block("AAA", df, frame="daily", row=_tile_now(),
                                   now=NOW_RTH, per_side=KL.SUPPORT_PER_SIDE)
    assert len(lines2) == 4


# --------------------------------------------------------------------------
# guards
# --------------------------------------------------------------------------
def test_NEGATIVE_a_frame_ending_three_sessions_early_is_stale_no_lines_no_chip():
    df = _frame("2026-09-21", n=60)
    row = _row(px=80.0, ts=TS_RTH, low=79.0, high=101.0, open_=100.0, close=80.0, pdc=100.0)
    block, lines = KL.tile_block("AAA", df, frame="daily", row=row, now=NOW_RTH, per_side=2)
    assert lines == [] and block["chip"] is None and block["drawn"] == []
    assert block["stale_note"] == ("key levels need bars through 2026-09-24; "
                                   "cached bars end 2026-09-21")
    assert block["levels"] and all(lv["state"] is None for lv in block["levels"])
    assert block["fold"].endswith(block["stale_note"])


def test_NEGATIVE_last_row_close_not_the_official_close_is_stale():
    df = _frame("2026-09-24", n=60, close=15.10, high=15.5, low=14.9)
    row = _row(px=15.2, ts=TS_RTH, low=15.0, high=15.3, open_=15.1, close=15.2, pdc=15.45)
    block, lines = KL.tile_block("WULX", df, frame="daily", row=row, now=NOW_RTH, per_side=2)
    assert block["stale_note"] == ("the 2026-09-24 bar in our cache is not the final "
                                   "close yet (15.10 vs 15.45)")
    assert lines == [] and block["chip"] is None and block["verified"] is False


def test_last_row_equal_to_prev_day_close_OR_the_snapshot_close_is_verified():
    df = _frame("2026-09-24", n=60, close=15.10, high=15.5, low=14.9)
    closed = KL.closed_frame(df, date(2026, 9, 25))
    assert KL.verify_last_row(closed, _row(pdc=15.10, close=15.3)) == (None, True)
    assert KL.verify_last_row(closed, _row(pdc=15.45, close=15.104)) == (None, True)
    assert KL.verify_last_row(closed, _row(pdc=15.45, close=15.106))[1] is False


def test_no_snapshot_row_draws_the_lines_unverified():
    df = _frame("2026-09-24", n=60, sets={"2026-09-16": {"high": 104.0, "low": 97.0}})
    block, lines = KL.tile_block("AAA", df, frame="daily", row=None, now=NOW_RTH, per_side=2)
    assert block["verified"] is False and block["stale_note"] is None
    assert lines


def test_NEGATIVE_no_cached_frame_says_so():
    block, lines = KL.tile_block("zzz", None, frame="daily", row=None, now=NOW_RTH, per_side=2)
    assert block["stale_note"] == "no cached daily bars for ZZZ" and lines == []
    assert block["levels"] == [] and block["fold"] == "🔑 RTH levels · no cached daily bars for ZZZ"


# --------------------------------------------------------------------------
# payload
# --------------------------------------------------------------------------
def test_every_float_is_finite_and_a_nan_level_is_dropped():
    df = _frame("2026-09-24", n=60)
    for d in _market_days("2026-09-18", 5):
        df.loc[d, "high"] = np.nan
    s = date(2026, 9, 25)
    lv = KL.period_levels(KL.closed_frame(df, s), s, ("week",))
    assert _by_id(lv, "week_high") == [] and _by_id(lv, "week_low")
    block, lines = KL.tile_block("AAA", df, frame="daily", row=_tile_now(),
                                 now=NOW_RTH, per_side=2)
    json.dumps({"b": block, "l": lines}, allow_nan=False)
    for lv in block["levels"]:
        for k in ("price", "dist_pct", "beyond_pct"):
            assert lv[k] is None or math.isfinite(lv[k])


def _scenario_payloads():
    df = _frame("2026-09-24", n=300, sets={"2026-09-16": {"high": 104.0, "low": 97.0}})
    outs = []
    for now, row in (
        (_at(2026, 9, 25, 4, 5), _row(px=96.0, ts=_ms(_at(2026, 9, 25, 4, 4)), pdc=100.0)),
        (NOW_RTH, _row(px=96.5, ts=TS_RTH, low=96.0, high=100.5, open_=99.0, close=96.5, pdc=100.0)),
        (NOW_RTH, _row(px=100.2, ts=TS_RTH, low=96.5, high=100.5, open_=99.0, close=100.2, pdc=100.0)),
        (NOW_CLOSE, _row(low=96.0, high=100.5, open_=99.0, close=96.5, pdc=100.0)),
        (_at(2026, 9, 25, 17, 0), _row(px=96.0, ts=_ms(_at(2026, 9, 25, 16, 59)), low=96.9,
                                       high=100.5, open_=99.0, close=97.2, pdc=100.0)),
    ):
        for frame in KL.FRAME_PERIODS:
            outs.append((frame, KL.tile_block("AAA", df, frame=frame, row=row, now=now,
                                              per_side=2, bars=PRE_BARS)))
    return outs


def test_served_strings_labels_and_chips():
    seen_chip = 0
    for frame, (block, lines) in _scenario_payloads():
        blob = json.dumps({"b": block, "l": lines}, allow_nan=False, ensure_ascii=False)
        assert "bounce" not in blob.lower()
        c = block["chip"]
        if c:
            seen_chip += 1
            assert c["text"] and c["text"][0] not in "↑↓" and c["text"].startswith("🔑 ")
        for ln in lines:
            assert ln["label"].startswith("🔑 ")
            assert ln["tone"] in (KL.TONE, KL.TONE_BROKEN)
            if frame in KL.EXT_FRAMES and "pre-mkt" not in ln["label"]:
                assert " RTH " in ln["label"]
            if frame not in KL.EXT_FRAMES:
                assert " RTH " not in ln["label"]
        assert block["measured"] is False and block["rule"] == KL.rule_text()
    assert seen_chip >= 3


def test_NEGATIVE_state_is_null_on_saturday_and_after_2000():
    df = _frame("2026-09-25", n=60, sets={"2026-09-16": {"high": 104.0, "low": 97.0}})
    # A Friday snapshot read on Saturday against Monday's levels: low 97.1 sits
    # 0.1% over PWL 97 — it must NOT read as "tested".
    fri = _row(px=97.1, ts=_ms(_at(2026, 9, 25, 15, 59)), low=97.1, high=99.0,
               open_=98.0, close=97.1, pdc=100.0)
    for now in (_at(2026, 9, 26, 11, 0), _at(2026, 9, 25, 20, 30)):
        block, _ = KL.tile_block("AAA", df, frame="daily", row=fri, now=now, per_side=2)
        assert block["phase"] is None and block["session"] == "2026-09-28"
        assert all(lv["state"] is None for lv in block["levels"])
        assert block["chip"] is None
        assert "tested" not in (block["fold"] or "")


def test_ext_frame_labels_and_pre_levels_only_from_0930():
    df = _frame("2026-09-24", n=60)
    row = _tile_now(20.5)
    early, _ = KL.tile_block("AAA", df, frame="5m_today", row=row,
                             now=_at(2026, 9, 25, 9, 29), per_side=2, bars=PRE_BARS)
    assert not [lv for lv in early["levels"] if lv["period"] == "pre"]
    late, lines = KL.tile_block("AAA", df, frame="5m_today", row=row,
                                now=_at(2026, 9, 25, 9, 31), per_side=2, bars=PRE_BARS)
    assert {lv["label"] for lv in late["levels"] if lv["period"] == "pre"} == {"pre-mkt H",
                                                                             "pre-mkt L"}
    # NEGATIVE: the daily frame never carries pre-market or prior-day levels.
    daily, _ = KL.tile_block("AAA", df, frame="daily", row=row,
                             now=_at(2026, 9, 25, 9, 31), per_side=2, bars=PRE_BARS)
    assert {lv["period"] for lv in daily["levels"]} <= {"week", "month", "year"}


def test_row_from_live_and_snapshot_shapes_non_positive_is_none():
    live = {"price": 0, "high": 0, "low": None, "open": -1, "last_trade_price": 12.5,
            "last_trade_ts_ms": 1, "prev_day_close": 12.0}
    r = KL.row_from_live(live)
    assert set(r) == set(KL._ROW_KEYS)
    assert r["close"] is None and r["high"] is None and r["low"] is None and r["open"] is None
    assert r["last_trade_price"] == 12.5 and r["prev_day_close"] == 12.0
    s = KL.row_from_snapshot({"close": 11.0, "high": 11.5, "low": 0, "open": 10.9})
    assert s["close"] == 11.0 and s["high"] == 11.5 and s["low"] is None
    assert KL.row_from_live(None) == {k: None for k in KL._ROW_KEYS}


def test_read_first_seen_is_one_find_one_and_empty_on_failure():
    class C:
        calls = 0

        def find_one(self, q):
            C.calls += 1
            assert q == {"_id": "2026-09-25"}
            return {"_id": "2026-09-25", "first": {"AAA|week_low_10000|down|through": "10:42"}}

    assert KL.read_first_seen("2026-09-25", coll=C()) == {
        "AAA|week_low_10000|down|through": "10:42"}
    assert C.calls == 1

    class Boom:
        def find_one(self, q):
            raise RuntimeError("down")
    assert KL.read_first_seen("2026-09-25", coll=Boom()) == {}
    assert KL.read_first_seen("2026-09-25") == {}        # conftest: no Mongo
    assert KL.first_seen_key("aaa", "week_low_10000", "down", "through") == \
        "AAA|week_low_10000|down|through"


# --------------------------------------------------------------------------
# pins + import guard
# --------------------------------------------------------------------------
def test_constants_are_the_house_constants():
    from scalping import candles
    from supply_demand import sd_liquidity
    from supply_demand import timeframes as TF
    from supply_demand import zone_edge as ZE
    assert KL.PIERCE_PCT is sd_liquidity.SWEEP_MIN_PIERCE_PCT
    assert KL.AT_LEVEL_PCT is candles.LEVEL_TOL_PCT
    assert KL.ROLL_AT == ZE.SESSION_CLOSE
    assert KL.SESSION_START == ZE.SESSION_OPEN
    assert KL.STALE_PRINT_SEC == ZE.STALE_PRINT_SEC
    assert set(KL.FRAME_PERIODS) == {TF.DAILY, TF.H1, TF.M15, TF.M5_TODAY, TF.H24}
    assert KL.PUSH_PERIODS == KL.FRAME_PERIODS[TF.DAILY]
    assert set(KL.EXT_FRAMES) == {TF.M5_TODAY, TF.H24}
    assert KL.MEASURED is False
    assert set(KL.NAMES) == set(KL.LABELS.values())


def test_rule_text_is_built_from_the_constants_and_says_unmeasured():
    txt = KL.rule_text()
    assert "UNMEASURED" in txt and "bounce" not in txt.lower()
    assert f"{KL.PIERCE_PCT:g}%" in txt and f"{KL.YEAR_BARS} sessions" in txt
    assert "16:05" in txt and "13:05" in txt and "20:00" in txt


_IMPORT_RE = re.compile(
    r"^\s*(from\s+supply_demand\s+import\s+[^\n]*\bkey_levels\b"
    r"|from\s+supply_demand\.key_levels\s+import"
    r"|import\s+supply_demand\.key_levels"
    r"|from\s+\.\s+import\s+[^\n]*\bkey_levels\b"
    r"|from\s+\.key_levels\s+import)", re.M)
ALLOWED = {"chart_maps/board.py", "chart_maps/api.py", "supply_demand/key_level_alerts.py",
           "supply_demand/rules_info.py", "supply_demand/key_levels.py"}


def test_import_guard_display_only():
    hits = set()
    for p in BACKEND.rglob("*.py"):
        rel = p.relative_to(BACKEND).as_posix()
        if rel.startswith((".venv/", "tests/")) or "/site-packages/" in rel:
            continue
        try:
            src = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if _IMPORT_RE.search(src):
            hits.add(rel)
    assert hits <= ALLOWED, sorted(hits - ALLOWED)
    assert "chart_maps/board.py" in hits and "chart_maps/api.py" in hits
    ze = (BACKEND / "supply_demand" / "zone_edge.py").read_text(encoding="utf-8")
    assert not _IMPORT_RE.search(ze)
    # zone_edge reaches key levels only through key_level_alerts, lazily.
    assert not re.search(r"^(from|import)\s[^\n]*key_level_alerts", ze, re.M)


def test_import_guard_catches_a_forbidden_import():
    assert _IMPORT_RE.search("    from supply_demand import key_levels as KL\n")
    assert _IMPORT_RE.search("from supply_demand.key_levels import chip\n")
    assert not _IMPORT_RE.search("x = 'key_levels'\n")


# --------------------------------------------------------------------------
# repair round 2026-09-25: pre-market sided by kind, the tie rule, half-day
# after-hours, the stale-note comparator, the set year, reclaim wording
# --------------------------------------------------------------------------
def _pre_bars(hi, lo, day="2026-09-25"):
    return [{"t": f"{day} 08:00", "s": "pre", "h": hi, "l": lo},
            {"t": f"{day} 09:35", "h": hi + 50, "l": lo - 50}]


def _pre_block(px, *, ref=100.0, hi=106.0, lo=104.0, now=None):
    now = now or _at(2026, 9, 25, 10, 0)
    df = _frame("2026-09-24", n=60, close=ref, high=ref + 0.5, low=ref - 0.5)
    row = _row(px=px, ts=_ms(now) - 30_000, open_=(hi + lo) / 2, high=px + 0.05, low=px - 0.05,
               close=px, pdc=ref)
    return KL.tile_block("AAA", df, frame="5m_today", row=row, now=now, per_side=2,
                         bars=_pre_bars(hi, lo))


def test_pre_levels_are_sided_by_KIND_a_gap_up_inside_the_range_is_not_broken():
    block, lines = _pre_block(105.0)
    pre = {lv["kind"]: lv for lv in block["levels"] if lv["period"] == "pre"}
    assert (pre["high"]["side"], pre["high"]["direction"]) == ("resistance", "up")
    assert (pre["low"]["side"], pre["low"]["direction"]) == ("support", "down")
    # NEGATIVE (the probe): yesterday closed at 100, the pre range is 104-106,
    # the price is 105 — the pre-mkt L 104 is NOT broken, no dashed pre line,
    # and no chip names it.
    assert pre["low"]["state"] != "broken" and pre["high"]["state"] != "broken"
    assert not [ln for ln in lines if "pre-mkt" in ln["label"] and ln["tone"] == KL.TONE_BROKEN]
    assert "pre-mkt" not in ((block["chip"] or {}).get("text") or "")
    assert "pre-mkt L 104.00" in block["fold"] and "broke" not in block["fold"].split("pre-mkt L 104.00")[1].split(" · ")[0]


def test_pre_low_lost_on_a_gap_down_day_reads_broken_down():
    """WULX live 12:30: 14.39 printed 8.4% under pre-mkt L 15.71 while the fold
    said 'tested' — sided by yesterday's close it was resistance."""
    block, _ = _pre_block(14.39, ref=14.0, hi=16.2, lo=15.71)
    pre_l = [lv for lv in block["levels"] if lv["id"].startswith("pre_low_")][0]
    assert (pre_l["side"], pre_l["direction"], pre_l["state"]) == ("support", "down", "broken")
    assert "pre-mkt L 15.71" in block["fold"]
    assert "tested" not in block["fold"].split("pre-mkt L 15.71")[1].split(" · ")[0]
    # the pre-mkt H above the price on a pre low break is plain resistance
    pre_h = [lv for lv in block["levels"] if lv["id"].startswith("pre_high_")][0]
    assert (pre_h["side"], pre_h["state"]) == ("resistance", "intact")


def test_NEGATIVE_pre_high_taken_out_upward_on_a_gap_down_day_reads_broken_up():
    block, _ = _pre_block(92.5, ref=100.0, hi=92.0, lo=90.0)
    pre_h = [lv for lv in block["levels"] if lv["id"].startswith("pre_high_")][0]
    assert (pre_h["side"], pre_h["direction"], pre_h["state"]) == ("resistance", "up", "broken")
    pre = [lv for lv in block["levels"] if lv["period"] == "pre"]
    assert KL.chip(pre, "rth")["text"] == "🔑 broke pre-mkt H 92.00 ↑"


def test_pre_members_on_their_own_sides_never_merge():
    lv = [KL._member("pre", "high", 100.2, "2026-09-25"), KL._member("pre", "low", 100.0, "2026-09-25")]
    cl = KL.merge_for_draw(lv, ref_close=90.0)
    assert len(cl) == 2


@pytest.mark.parametrize("period", ["week", "year"])
def test_a_close_exactly_AT_a_high_keeps_it_resistance_up(period):
    """Probe B: yesterday closed at its high = 52wH 101; today dips 0.2%.
    The level stays resistance — never '🔑 broke 52wH 101.00 ↓'."""
    lvl = _lvl(period, "high", 101.0)
    st = _state(lvl, ref=101.0, row=_row(px=100.8, ts=TS_RTH, low=100.7, high=101.0), now=NOW_RTH)
    assert (st["side"], st["direction"]) == ("resistance", "up")
    assert st["state"] != "broken"
    lv = KL.read_levels([lvl], symbol="AAA", ref_close=101.0,
                        row=_row(px=100.8, ts=TS_RTH, low=100.7, high=101.0),
                        now=NOW_RTH, session=NOW_RTH.date(), first_seen={})
    assert KL.chip(lv, "rth") is None
    # NEGATIVE: the close does not say "closed back under" either.
    lv = KL.read_levels([lvl], symbol="AAA", ref_close=101.0,
                        row=_row(low=100.7, high=101.0, open_=101.0, close=100.75),
                        now=NOW_CLOSE, session=NOW_CLOSE.date(), first_seen={})
    assert lv[0]["state"] != "closed_beyond" and KL.chip(lv, "close") is None


def test_a_close_exactly_AT_a_low_keeps_it_support_down_and_off_the_tie_by_position():
    st = _state(_lvl("week", "low", 100.0), ref=100.0, row=_row(px=99.8, ts=TS_RTH), now=NOW_RTH)
    assert (st["side"], st["direction"], st["state"]) == ("support", "down", "broken")
    # NEGATIVE: one cent off the tie is decided by position, not by kind.
    assert KL._side(101.0, 101.01, "high") == ("support", "down")
    assert KL._side(100.0, 99.99, "low") == ("resistance", "up")
    assert KL._side(101.0, 101.0, "high") == ("resistance", "up")
    assert KL._side(100.0, 100.0, "low") == ("support", "down")


HALF = date(2026, 11, 27)


def test_half_day_after_hours_print_from_1305_is_ah_through():
    now = datetime(2026, 11, 27, 13, 30, tzinfo=ET)
    row = _row(px=99.70, ts=_ms(datetime(2026, 11, 27, 13, 29, tzinfo=ET)),
               low=99.50, high=101.0, open_=100.5, close=100.20)
    lv = KL.read_levels([_lvl(price=100.0)], symbol="AAA", ref_close=101.0, row=row,
                        now=now, session=HALF, first_seen={})
    assert lv[0]["state"] == "reversal" and lv[0]["ah_through"] is True
    assert KL.chip(lv, "close")["text"] == "🔑 after-hrs under PWL 100.00"


def test_NEGATIVE_half_day_print_stamped_before_1305_is_not_after_hours():
    now = datetime(2026, 11, 27, 13, 5, 30, tzinfo=ET)
    row = _row(px=99.70, ts=_ms(datetime(2026, 11, 27, 13, 4, tzinfo=ET)),
               low=99.50, high=101.0, open_=100.5, close=100.20)
    lv = KL.read_levels([_lvl(price=100.0)], symbol="AAA", ref_close=101.0, row=row,
                        now=now, session=HALF, first_seen={})
    assert lv[0]["ah_through"] is False
    # NEGATIVE: on a FULL day a 13:29 print is RTH, never after-hours.
    assert KL._is_after_hours_print(
        _row(px=99.7, ts=_ms(_at(2026, 9, 25, 13, 29))), date(2026, 9, 25)) is False


def test_stale_note_quotes_the_snapshot_close_when_the_snapshot_is_that_bars_day():
    """Friday 20:05 before Massive rolls: prev_day_close is THURSDAY's close;
    the comparator for the 09-25 bar is the snapshot's own close."""
    df = _frame("2026-09-25", n=60, close=139.01, high=140.0, low=138.0)
    now = _at(2026, 9, 25, 20, 5)
    row = _row(px=139.2, ts=_ms(_at(2026, 9, 25, 19, 59)), open_=139.5, high=140.2,
               low=138.6, close=139.30, pdc=139.54)
    block, lines = KL.tile_block("AAA", df, frame="daily", row=row, now=now, per_side=2)
    assert block["stale_note"] == ("the 2026-09-25 bar in our cache is not the final "
                                   "close yet (139.01 vs 139.30)")
    assert "139.54" not in block["stale_note"] and lines == []


def test_NEGATIVE_stale_note_quotes_prev_day_close_after_the_roll():
    df = _frame("2026-09-25", n=60, close=139.01, high=140.0, low=138.0)
    closed = KL.closed_frame(df, date(2026, 9, 28))
    rolled = _row(px=140.0, ts=_ms(_at(2026, 9, 28, 8, 0)), close=140.0, pdc=139.30)
    note, ok = KL.verify_last_row(closed, rolled)
    assert ok is False and note.endswith("(139.01 vs 139.30)")
    # no trade stamp at all -> prev_day_close, as before
    note, _ = KL.verify_last_row(closed, _row(close=140.0, pdc=139.30))
    assert note.endswith("(139.01 vs 139.30)")


def test_set_on_carries_the_year_when_it_is_not_the_sessions_year():
    assert KL._day_mmdd("2025-09-25", ref_year=2026) == "2025-09-25"
    assert KL._day_mmdd("2025-09-25", weekday=True, ref_year=2026) == "Thu 2025-09-25"
    # NEGATIVE: same year stays MM-DD; no ref year keeps the old shape.
    assert KL._day_mmdd("2026-03-04", ref_year=2026) == "03-04"
    assert KL._day_mmdd("2025-09-25") == "09-25"
    df = _frame("2026-09-24", n=300, sets={"2025-10-01": {"low": 60.0},
                                           "2026-03-04": {"high": 131.2}})
    block, _ = KL.tile_block("AAA", df, frame="daily", row=_tile_now(), now=NOW_RTH,
                             per_side=KL.GRID_PER_SIDE)
    assert "52wL 60.00 (set 2025-10-01)" in block["fold"]
    assert "(set 10-01)" not in block["fold"] and "52wH 131.20 (set 03-04)" in block["fold"]


def test_a_low_reclaimed_upward_reads_back_over_never_broke():
    row = _row(px=100.5, ts=TS_RTH, low=99.2, high=100.6, open_=99.3, close=100.5)
    lv = KL.read_levels([_lvl(price=100.0)], symbol="AAA", ref_close=99.0, row=row,
                        now=NOW_RTH, session=NOW_RTH.date(), first_seen={})
    assert lv[0]["state"] == "broken" and lv[0]["direction"] == "up"
    c = KL.chip(lv, "rth")["text"]
    assert c == "🔑 back over PWL 100.00 ↑" and "broke" not in c
    fold = KL.fold_text(lv, frame="daily", stale_note=None)
    assert "back over" in fold and "broke" not in fold
    gap_row = {**row, "open": 100.5}
    lv = KL.read_levels([_lvl(price=100.0)], symbol="AAA", ref_close=99.0, row=gap_row,
                        now=NOW_RTH, session=NOW_RTH.date(), first_seen={})
    assert KL.chip(lv, "rth")["text"] == "🔑 gapped back over PWL 100.00 ↑"


def test_a_high_lost_downward_reads_back_under_and_natural_breaks_still_say_broke():
    row = _row(px=99.5, ts=TS_RTH, low=99.4, high=101.2, open_=101.0, close=99.5)
    lv = KL.read_levels([_lvl(kind="high", price=100.0)], symbol="AAA", ref_close=101.0,
                        row=row, now=NOW_RTH, session=NOW_RTH.date(), first_seen={})
    assert KL.chip(lv, "rth")["text"] == "🔑 back under PWH 100.00 ↓"
    # NEGATIVE: the level's own direction keeps the spec's "broke" / "gapped through".
    row = _row(px=100.5, ts=TS_RTH, low=99.9, high=100.6, open_=100.0, close=100.5)
    lv = KL.read_levels([_lvl(kind="high", price=100.0)], symbol="AAA", ref_close=99.0,
                        row=row, now=NOW_RTH, session=NOW_RTH.date(), first_seen={})
    assert KL.chip(lv, "rth")["text"] == "🔑 broke PWH 100.00 ↑"
    lv = KL.read_levels([_lvl(kind="high", price=100.0)], symbol="AAA", ref_close=99.0,
                        row={**row, "open": 100.4}, now=NOW_RTH, session=NOW_RTH.date(),
                        first_seen={})
    assert KL.chip(lv, "rth")["text"] == "🔑 gapped through PWH 100.00 ↑"
