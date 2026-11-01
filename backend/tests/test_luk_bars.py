"""chart_maps/luk/bars.py — 🥇 Luk's frames (spec §3.5): 1m / 5m on every session's minutes, 60m on RTH only; the
lookbacks read THROUGH the judged bar (C7 rth_low, C8 hourly_ref). Synthetic minute days only (the suite refuses the
network); index = naive UTC minute STARTS, like the daytrading loader's."""
from __future__ import annotations

from datetime import date, datetime, time as dtime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala.context import history_window
from chart_maps.luk import bars as B
from chart_maps.luk import constants as LC

ET = ZoneInfo("America/New_York")
S = date(2026, 10, 13)
PRIOR = history_window(S, LC.LUK_HOURLY_SESSIONS)


def et(hh, mm, ss=0, d=S):
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=ET)


def _session_of(t):
    m = t.hour * 60 + t.minute
    return "premarket" if m < 570 else ("rth" if m < 960 else "afterhours")


def raw_day(d, start=(4, 0), end=(20, 0), base=10.0, lows=None):
    """A minute per minute [start, end) ET. `lows` = {(hh, mm): low} overrides a minute's low."""
    t0 = pd.Timestamp(datetime(d.year, d.month, d.day, *start), tz=ET)
    t1 = pd.Timestamp(datetime(d.year, d.month, d.day, *end), tz=ET)
    idx = pd.date_range(t0, t1, freq="1min", inclusive="left")
    rows = []
    for i, ts in enumerate(idx):
        p = base + 0.001 * i
        lo = (lows or {}).get((ts.hour, ts.minute), p - 0.001)
        rows.append({"open": p, "high": p + 0.002, "low": lo, "close": p + 0.001, "volume": 100.0,
                     "session": _session_of(ts)})
    return pd.DataFrame(rows, index=idx.tz_convert("UTC").tz_localize(None))


def prior_days():
    return [raw_day(d) for d in PRIOR]


def build(now, today=None, prior=True):
    return B.build("AAA", S, now, prior_days() if prior else [], today if today is not None else raw_day(S))


@pytest.fixture(scope="module")
def F():
    lows = {(8, 0): 1.0, (9, 40): 9.0, (10, 20): 8.0}
    return B.build("AAA", S, et(10, 31), prior_days(), raw_day(S, lows=lows))


def test_three_frames_in_variant_order(F):
    assert list(F.by) == ["1m", "5m", "60m"]
    assert F.primary == "5m" and F.slow == "60m"
    assert [F.by[k].frame for k in F.by] == ["1m", "5m", "60m"]


def test_1m_and_5m_carry_pre_rth_and_ah_bars_60m_rth_only(F):
    for tf in ("1m", "5m"):
        assert {"premarket", "rth", "afterhours"} <= set(F.by[tf].session), tf
    assert set(F.by["60m"].session) == {"rth"}, "NEGATIVE: no extended-hours minute reaches the hourly frame"


def test_60m_is_clock_anchored_first_rth_bar_is_a_half_hour(F):
    h = F.by["60m"]
    today = [h.t[i] for i in h.today]
    assert today == ["2026-10-13 10:00"], "only the 10:00 bar has closed at 10:31"
    assert h.v[h.today[0]] == 30 * 100.0, "09:30–09:59 = 30 minutes"
    prev_last = PRIOR[-1].isoformat() + " 16:00"
    assert prev_last in h.t


def test_rth_low_ignores_premarket(F):
    assert B.rth_low(F) == 8.0, "the 08:00 pre-market low of 1.0 is not his low of day"
    assert B.rth_low(F) != 1.0


def test_C7_rth_low_through_t_ignores_later_lows(F):
    at_0945 = B.rth_low(F, et(9, 45))
    assert at_0945 == 9.0
    assert B.rth_low(F, et(10, 0)) == 9.0, "the 10:20 low of 8.0 printed later — the read through 10:00 is unchanged"
    assert B.rth_low(F, "2026-10-13 10:21") == 8.0
    assert B.rth_low(F, et(9, 30)) is None, "no RTH bar closed by 09:30"


def test_rth_high_through_t(F):
    f1 = F.by["1m"]
    want = max(f1.h[i] for i in f1.today if f1.session[i] == "rth" and f1.t[i] <= "2026-10-13 09:45")
    assert B.rth_high(F, et(9, 45)) == want
    assert B.rth_high(F, et(9, 45)) < B.rth_high(F)


def test_C8_hourly_ref_before_ten_reads_yesterdays_last_bar(F):
    h = F.by["60m"]
    ref = B.hourly_ref(F, et(9, 55))
    assert ref["bar_t"] == PRIOR[-1].isoformat() + " 16:00"
    j = h.t.index(ref["bar_t"])
    assert ref["ema9"] == h.ema9[j] and ref["ema21"] == h.ema21[j]
    assert ref["ema21"] is not None, "10 prior sessions warm the 21 EMA"


def test_C8_hourly_ref_at_ten_reads_todays_ten_oclock_bar(F):
    assert B.hourly_ref(F, et(10, 0))["bar_t"] == "2026-10-13 10:00"
    assert B.hourly_ref(F, et(10, 30))["bar_t"] == "2026-10-13 10:00"


def test_NEGATIVE_hourly_ref_none_when_nothing_closed():
    fr = B.build("AAA", S, et(9, 50), [], raw_day(S))
    assert B.hourly_ref(fr, et(9, 45)) is None
    assert B.hourly_ref(None, et(9, 45)) is None


def test_latest_closed_t(F):
    assert B.latest_closed_t(F, "1m") == et(10, 30)
    assert B.latest_closed_t(F, "5m") == et(10, 30)
    assert B.latest_closed_t(F, "60m") == et(10, 0)
    assert B.latest_closed_t(F, "15m") is None


def test_NEGATIVE_latest_closed_t_none_without_a_bar_today():
    fr = B.build("AAA", S, et(4, 6), prior_days(), raw_day(S))
    assert fr is not None
    assert B.latest_closed_t(fr, "60m") is None, "no hourly bar today before the open"


def test_settle_rule_a_bar_counts_30s_after_its_close():
    early = build(et(10, 30, 29), prior=False)
    late = build(et(10, 30, 30), prior=False)
    assert B.latest_closed_t(early, "5m") == et(10, 25)
    assert B.latest_closed_t(late, "5m") == et(10, 30)


def test_NEGATIVE_build_none_without_a_5m_bar_today():
    assert build(et(4, 5, 10)) is None
    assert B.build("AAA", S, et(10, 0), prior_days(), None) is None
    assert B.build("AAA", S, et(10, 0), prior_days(), raw_day(S).iloc[0:0]) is None


@pytest.mark.parametrize("t,want", [
    (dtime(9, 30), None), (dtime(9, 31), "1m"), (dtime(9, 45), "1m"), (dtime(9, 46), "5m"), (dtime(9, 50), "5m"),
    (dtime(10, 30), "5m"), (dtime(10, 31), None), (dtime(10, 35), None), (dtime(8, 0), None)])
def test_frame_for_close_pullback(t, want):
    assert B.frame_for_close(t, switch_min=LC.LUK_ONE_MIN_UNTIL_MIN) == want


@pytest.mark.parametrize("t,want", [(dtime(9, 35), "1m"), (dtime(9, 36), "5m"), (dtime(9, 40), "5m"),
                                    (dtime(10, 30), "5m"), (dtime(10, 35), None)])
def test_frame_for_close_orh(t, want):
    assert B.frame_for_close(t, switch_min=LC.LUK_ORH_SWITCH_MIN) == want


def test_frame_for_close_takes_an_aware_datetime():
    assert B.frame_for_close(et(9, 45), switch_min=LC.LUK_ONE_MIN_UNTIL_MIN) == "1m"
    utc = et(9, 50).astimezone(ZoneInfo("UTC"))
    assert B.frame_for_close(utc, switch_min=LC.LUK_ONE_MIN_UNTIL_MIN) == "5m"


def _loader(log, *, today=None, failed_days=()):
    from daytrading import data as dt_data

    def load(sym, day, force=False, include_premarket=True, include_afterhours=False):
        log.append((sym, day, force, include_premarket, include_afterhours))
        if day in failed_days:
            return dt_data._provider_failed()
        if day == S:
            return today if today is not None else raw_day(S)
        return raw_day(day)
    return load


def test_load_days_prior_window_then_today_forced():
    log = []
    prior, today, failed = B.load_days("BRK-B", S, load_day=_loader(log))
    assert [x[1] for x in log] == PRIOR + [S] and len(prior) == LC.LUK_HOURLY_SESSIONS
    assert all(x[0] == "BRK.B" for x in log), "Massive's spelling"
    assert all(x[3] and x[4] for x in log), "pre-market and after-hours included"
    assert [x[2] for x in log] == [False] * len(PRIOR) + [True], "today force=True, prior from the cache"
    assert today is not None and failed is False


def test_frames_for_counts_loaded_failed_no_bars_and_over_budget():
    stats = {}
    out = B.frames_for(["AAA"], S, et(10, 31), load_day=_loader([]), budget_sec=60, stats=stats, workers=1)
    assert list(out) == ["AAA"] and stats == {"loaded": 1, "no_bars": 0, "failed": 0, "over_budget": 0}
    stats = {}
    out = B.frames_for(["AAA"], S, et(10, 31), load_day=_loader([], failed_days={S}), budget_sec=60, stats=stats)
    assert out == {} and stats["failed"] == 1, "NEGATIVE: a provider failure is never 'no bars today'"
    stats = {}
    out = B.frames_for(["AAA"], S, et(4, 5), load_day=_loader([]), budget_sec=60, stats=stats)
    assert out == {} and stats["no_bars"] == 1
    stats = {}
    out = B.frames_for(["AAA", "BBB"], S, et(10, 31), load_day=_loader([]), budget_sec=-1, stats=stats)
    assert out == {} and stats["over_budget"] == 2


# ── 2026-11-01 refix: the 60m frame goes through GG's build_frame on a 15-minute PROXY rule and is relabelled ────────
def _today_by_real_rule(fr, session_iso, rule):
    starts = ((fr.df.index - pd.Timedelta(rule)).tz_localize("UTC").tz_convert("America/New_York")
              .strftime("%Y-%m-%d").tolist())
    first = next((i for i, d in enumerate(starts) if d == session_iso), len(starts))
    return range(first, len(starts))


@pytest.mark.parametrize("now", [et(9, 55), et(10, 31), et(12, 1), et(16, 1), et(19, 59)])
def test_60m_today_under_the_proxy_equals_the_real_60min_rule(now):
    F = build(now)
    h = F.by["60m"]
    assert h.frame == "60m" and F.by["1m"].frame == "1m" and F.by["5m"].frame == "5m"
    assert h.today == _today_by_real_rule(h, S.isoformat(), "60min")


def test_60m_minutes_are_bucketed_by_the_real_hourly_rule():
    F = build(et(12, 1))
    h = F.by["60m"]
    assert [h.t[i] for i in h.today] == ["2026-10-13 10:00", "2026-10-13 11:00", "2026-10-13 12:00"]
    assert {k: len(v) for k, v in h.minutes.items()} == {"2026-10-13 10:00": 30, "2026-10-13 11:00": 60,
                                                         "2026-10-13 12:00": 60}


def test_NEGATIVE_a_15min_rule_would_have_split_the_hourly_minutes():
    from chart_maps.gajjala import bars as GB
    F = build(et(12, 1))
    h = F.by["60m"]
    wrong = GB._minutes_by_bucket(F.raw[F.raw["session"] == LC.LUK_HOURLY_SESSION], h, B._PROXY_RULE)
    assert wrong != h.minutes, "the proxy rule is for build_frame only; _minutes_by_bucket gets the real 60min"


def test_NEGATIVE_prior_days_hourly_bars_never_count_as_today():
    F = build(et(9, 55))
    h = F.by["60m"]
    assert not len(h.today), "no hourly bar of today has closed before 10:00"
    assert len(h.t) > 0 and all(not t.startswith(S.isoformat()) for t in h.t)
