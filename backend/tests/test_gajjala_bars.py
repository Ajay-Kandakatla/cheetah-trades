"""chart_maps/gajjala/bars.py — closed 5/15-minute frames, EMAs, tile payload (spec §3.1.4, WP1).

Synthetic 1-minute days only (the suite refuses the network): index = naive UTC minute STARTS, like the
daytrading loader's. The resampler is the house one (left-closed, right-labelled).
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps import board
from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from orderflow.signals import ema

ET = ZoneInfo("America/New_York")
S = date(2026, 10, 13)
PREV = date(2026, 10, 12)


def et(hh, mm, ss=0, d=S):
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=ET)


def _session_of(t_et):
    m = t_et.hour * 60 + t_et.minute
    return "premarket" if m < 570 else ("rth" if m < 960 else "afterhours")


def raw_day(d, start=(4, 0), end=(20, 0), base=1.0):
    """One minute bar per minute [start, end) ET; volume = minute-of-day so every bucket sum is unique."""
    t0 = pd.Timestamp(datetime(d.year, d.month, d.day, *start), tz=ET)
    t1 = pd.Timestamp(datetime(d.year, d.month, d.day, *end), tz=ET)
    idx_et = pd.date_range(t0, t1, freq="1min", inclusive="left")
    rows = []
    for i, ts in enumerate(idx_et):
        p = base + 0.001 * i
        rows.append({"open": p, "high": p + 0.002, "low": p - 0.001, "close": p + 0.001,
                     "volume": float(ts.hour * 60 + ts.minute), "session": _session_of(ts)})
    idx = idx_et.tz_convert("UTC").tz_localize(None)
    return pd.DataFrame(rows, index=idx)


def frames(now, *, prev=True, today_end=(20, 0)):
    return B.build_frames("AAA", S, now, raw_day(PREV) if prev else None, raw_day(S, end=today_end))


def test_5min_right_labelled_bucket_1005_holds_1000_to_1004():
    fr = frames(et(10, 7))
    i = fr.f5.t.index("2026-10-13 10:05")
    assert fr.f5.v[i] == sum(float(600 + k) for k in range(5))
    m = fr.minutes5["2026-10-13 10:05"]
    assert len(m) == 5 and [x[4] for x in m] == [600.0, 601.0, 602.0, 603.0, 604.0]
    assert fr.f5.o[i] == m[0][0] and fr.f5.c[i] == m[-1][3]
    assert fr.f5.h[i] == max(x[1] for x in m) and fr.f5.l[i] == min(x[2] for x in m)


def test_15min_right_labelled_the_same():
    fr = frames(et(10, 20))
    i = fr.f15.t.index("2026-10-13 10:15")
    assert fr.f15.v[i] == sum(float(600 + k) for k in range(15))
    assert len(fr.minutes15["2026-10-13 10:15"]) == 15


def test_NEGATIVE_bucket_1010_dropped_at_1007():
    fr = frames(et(10, 7))
    assert fr.f5.t[-1] == "2026-10-13 10:05" and "2026-10-13 10:10" not in fr.f5.t
    assert "2026-10-13 10:10" not in fr.minutes5


@pytest.mark.parametrize("ss,has", [(GC.BAR_SETTLE_SEC - 10, False), (GC.BAR_SETTLE_SEC, True)])
def test_NEGATIVE_never_a_bar_after_now_minus_settle(ss, has):
    fr = frames(et(10, 5, ss))
    assert ("2026-10-13 10:05" in fr.f5.t) is has
    cutoff = B._utc_naive(et(10, 5, ss)) - pd.Timedelta(seconds=GC.BAR_SETTLE_SEC)
    assert (fr.df5.index <= cutoff).all() and (fr.df15.index <= cutoff).all()


def test_as_of_bar_t5_and_t15_differ_at_1006():
    fr = frames(et(10, 6))
    assert fr.as_of_bar_t5 == "2026-10-13 10:05" and fr.as_of_bar_t15 == "2026-10-13 10:00"
    assert fr.as_of_bar_t == {"5m": "2026-10-13 10:05", "15m": "2026-10-13 10:00"}


def test_ema_is_signals_ema_with_warm_up_none():
    fr = frames(et(12, 0))
    e9 = ema(fr.df5["close"].astype(float), GC.EMA_FAST).tolist()
    e21 = ema(fr.df5["close"].astype(float), GC.EMA_SLOW).tolist()
    assert fr.f5.ema9[:GC.EMA_FAST - 1] == [None] * (GC.EMA_FAST - 1)
    assert fr.f5.ema21[:GC.EMA_SLOW - 1] == [None] * (GC.EMA_SLOW - 1)
    for i in range(GC.EMA_SLOW, len(fr.f5)):
        assert fr.f5.ema9[i] == pytest.approx(e9[i], abs=1e-6) and fr.f5.ema21[i] == pytest.approx(e21[i], abs=1e-6)
    assert list(fr.df5["ema9"]) == fr.f5.ema9


def test_today_range_and_the_prior_session_only_warms():
    fr = frames(et(12, 0))
    first = fr.f5.today.start
    assert fr.f5.t[first] == "2026-10-13 04:05" and fr.f5.t[first - 1] == "2026-10-12 20:00"
    assert fr.today_idx5 == fr.f5.today and fr.f5.today.stop == len(fr.f5)
    assert fr.f5.ema9[first] is not None and fr.f5.ema21[first] is not None
    assert set(k[:10] for k in fr.minutes5) == {"2026-10-13"}


def test_tile_payload_today_only_s_flags_and_curves_by_stamp():
    fr = frames(et(17, 1))
    tp = B.tile_payload(fr, "5m")
    assert tp["bars"][0]["t"] == "2026-10-13 04:05" and tp["bars"][-1]["t"] == "2026-10-13 17:00"
    assert tp["bars"][0]["s"] == "pre" and "s" not in tp["bars"][80] and tp["bars"][-1]["s"] == "ah"
    assert [c["tone"] for c in tp["curves"]] == ["ema9", "ema21"]
    assert [c["label"] for c in tp["curves"]] == ["9 EMA", "21 EMA"]
    for c in tp["curves"]:
        assert len(c["values"]) == len(tp["bars"])
    assert tp["curves"][0]["values"][-1] == fr.f5.ema9[-1]


def test_tile_vol_avg_has_a_value_on_todays_0405_bar():
    fr = frames(et(10, 0))
    tp = B.tile_payload(fr, "5m")
    va = tp["vol_avg"]
    assert va["period"] == board.VOL_AVG_PERIOD == 50 and va["label"] == board.VOL_AVG_LABEL
    assert len(va["values"]) == len(tp["bars"]) and va["values"][0] is not None
    i = fr.f5.today.start
    want = sum(fr.f5.v[i - board.VOL_AVG_PERIOD + 1:i + 1]) / board.VOL_AVG_PERIOD
    assert va["values"][0] == pytest.approx(want)


def test_tile_15m_frame():
    tp = B.tile_payload(frames(et(10, 1)), "15m")
    assert tp["bars"][0]["t"] == "2026-10-13 04:15" and tp["bars"][-1]["t"] == "2026-10-13 10:00"


def test_NEGATIVE_first_print_name_no_prior_session():
    fr = frames(et(5, 1), prev=False)                            # 12 five-minute bars, nothing before today
    assert len(fr.f5) == 12 and fr.f5.today == range(0, 12)
    assert fr.f5.ema9[:8] == [None] * 8 and fr.f5.ema9[8] is not None
    assert fr.f5.ema21 == [None] * 12
    tp = B.tile_payload(fr, "5m")
    assert [c["tone"] for c in tp["curves"]] == ["ema9"]           # an all-None 21 EMA is omitted, not drawn as nulls
    assert tp["vol_avg"] is None


def test_NEGATIVE_no_bars_today_is_none():
    assert B.build_frames("AAA", S, et(10, 0), raw_day(PREV), None) is None
    assert B.build_frames("AAA", S, et(10, 0), raw_day(PREV), raw_day(S).iloc[:0]) is None
    assert B.build_frames("AAA", S, et(4, 0, 10), raw_day(PREV), raw_day(S, end=(4, 1))) is None   # nothing closed


def _loader(table, calls):
    def load(sym, day, force=False, include_premarket=True, include_afterhours=False):
        calls.append((sym, day, force, include_premarket, include_afterhours))
        v = table[sym]
        if isinstance(v, Exception):
            raise v
        return v.get(day)
    return load


def test_frames_for_loads_prev_cached_and_today_forced_and_counts():
    calls = []
    table = {"AAA": {PREV: raw_day(PREV), S: raw_day(S, end=(10, 10))},
             "BAD": RuntimeError("provider down"),
             "NONE": {PREV: raw_day(PREV), S: None}}
    stats = {}
    out = B.frames_for(["AAA", "BAD", "NONE", "AAA"], S, et(10, 6), load_day=_loader(table, calls), stats=stats)
    assert set(out) == {"AAA"} and out["AAA"].as_of_bar_t5 == "2026-10-13 10:05"
    assert stats == {"loaded": 1, "no_bars": 1, "failed": 1, "over_budget": 0}
    aaa = [c for c in calls if c[0] == "AAA"]
    assert aaa == [("AAA", PREV, False, True, True), ("AAA", S, True, True, True)]


def test_NEGATIVE_frames_for_over_budget_is_skipped_and_counted():
    stats = {}
    out = B.frames_for(["AAA"], S, et(10, 6), stats=stats, budget_sec=-1,
                       load_day=lambda *a, **k: pytest.fail("past the budget nothing loads"))
    assert out == {} and stats["over_budget"] == 1


def test_frames_for_holiday_prev_day():
    calls = []
    d = date(2026, 11, 27)
    table = {"AAA": {date(2026, 11, 25): raw_day(date(2026, 11, 25)), d: raw_day(d, end=(10, 0))}}
    B.frames_for(["AAA"], d, datetime(2026, 11, 27, 9, 0, tzinfo=ET), load_day=_loader(table, calls))
    assert calls[0][1] == date(2026, 11, 25)                      # Thanksgiving skipped


def test_closed_only_accepts_aware_and_naive_utc():
    df = B.closed_only(raw_day(S, end=(4, 10)), et(4, 5))
    assert len(df) == 5
    naive_utc = pd.Timestamp(et(4, 5)).tz_convert("UTC").tz_localize(None)
    assert len(B.closed_only(raw_day(S, end=(4, 10)), naive_utc)) == 5
    assert B.closed_only(None, et(4, 5)) is None


def test_frames_carry_the_detector_contract():
    """WP3's `Frame` reads o/h/l/c/v/t/session/ema9/ema21/today/df/minutes/frame — every one is on ours."""
    fr = frames(et(10, 7))
    df = fr.detector_frames()
    assert df["5m"] is fr.f5 and df["15m"] is fr.f15
    assert fr.f5.frame == "5m" and fr.f15.frame == "15m"
    assert fr.f5.minutes is fr.minutes5 and fr.f15.minutes is fr.minutes15
    for f in df.values():
        for attr in ("o", "h", "l", "c", "v", "t", "session", "ema9", "ema21", "today", "df", "minutes", "frame"):
            assert hasattr(f, attr), attr


def test_detectors_read_our_frames_without_raising():
    from chart_maps.gajjala import detectors
    fr = frames(et(12, 1))
    reads = detectors.read_all(fr.detector_frames(), {"symbol": "AAA", "float_read": None})
    assert set(reads) == set(GC.SETUPS)
    assert all(r.get("reason") != "detector error" for r in reads.values())
