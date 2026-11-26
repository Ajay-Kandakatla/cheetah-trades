"""📅 Runners on one continuous chart — the engine `chart_maps.gajjala_watch.runchart` (spec runcharts rev 2 §3.2-§3.4,
§4.1 tests 1-22, 2026-11-26).

Ajay 2026-11-26, verbatim: "I want you to have continous charts for previous day runners … I wanna able to horizontal
scroll tp check continuity like he does".

Every test injects `load_day`, `splits_fn`, `cached_at_fn`, `ran_fn`, `clock` (and `wait_sec` where a gate is in play) —
never the network, never the default `cached_at` (it would wait on Mongo's server selection). NEGATIVES throughout.

The golden fixture `frontend/src/lib/__fixtures__/ggRunChart.golden.json` is WRITTEN by test 22's recipe, never by hand:

    cd backend && GGRC_WRITE_GOLDEN=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
        tests/test_gajjala_watch_runchart_2026_11_26.py -k golden
"""
from __future__ import annotations

import json
import math
import os
import re
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import runchart as RC
from chart_maps.support import _frame_bars
from daytrading import data as dt_data
from growth.api import _scrub
from orderflow import signals as SG
from tests.test_gajjala_watch_build_2026_11_15 import HALF, HALF_PREV, raw_day

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "frontend" / "src" / "lib" / "__fixtures__" / "ggRunChart.golden.json"
RECIPE = ("cd backend && GGRC_WRITE_GOLDEN=1 .venv/bin/python -m pytest -q -p no:cacheprovider "
          "tests/test_gajjala_watch_runchart_2026_11_26.py -k golden")
SRC = Path(RC.__file__).read_text(encoding="utf-8")

NOW_CLOSED = datetime(2026, 11, 26, 12, 0, tzinfo=ET)          # Thanksgiving — closed; newest session Wed 11-25
NOW_LIVE = datetime(2026, 11, 25, 10, 0, tzinfo=ET)            # Wed, in the pass window
D = {k: date(2026, 11, k) for k in (18, 19, 20, 23, 24, 25)}
CLOSED_DAYS = [D[18], D[19], D[20], D[23], D[24], D[25]]
DRAWN = ["2026-11-19", "2026-11-20", "2026-11-23", "2026-11-24", "2026-11-25"]
SPLIT = [{"execution_date": "2026-11-24", "split_from": 10.0, "split_to": 1.0}]


class Clock:
    def __init__(self, t=1000.0):
        self.t = float(t)

    def __call__(self):
        return self.t


class Loader:
    """A fake minute loader with a call log. `days` = {date: DataFrame | None | "fail" | "raise"}; a missing day →
    raw_day(d, seed=d.day). `tick` advances the injected clock on each call."""

    def __init__(self, days=None, clock=None, tick=0.0, live_end=None, hook=None):
        self.days = dict(days or {})
        self.calls = []
        self.clock = clock
        self.tick = tick
        self.live_end = live_end
        self.hook = hook

    def __call__(self, sym, d, force=False, include_premarket=True, include_afterhours=False, **kw):
        self.calls.append({"sym": sym, "day": d, "force": force, "pre": include_premarket, "ah": include_afterhours,
                           "kw": dict(kw)})
        if self.hook is not None:
            self.hook()
        if self.clock is not None and self.tick:
            self.clock.t += self.tick
        v = self.days.get(d, "default")
        if isinstance(v, str) and v == "fail":
            return dt_data._provider_failed()
        if isinstance(v, str) and v == "raise":
            raise RuntimeError("boom")
        if isinstance(v, str) and v == "default":
            if self.live_end is not None and d == self.live_end[0]:
                return raw_day(d, end=self.live_end[1], seed=d.day)
            return raw_day(d, seed=d.day)
        return v

    def days_asked(self):
        return [c["day"] for c in self.calls]


@pytest.fixture(autouse=True)
def _reset():
    RC.reset()
    yield
    RC.reset()


def kw(loader=None, clock=None, **over):
    clock = clock or Clock()
    out = dict(load_day=loader or Loader(), splits_fn=lambda s, i: [], cached_at_fn=lambda s, i: {},
               ran_fn=lambda n, d: {}, clock=clock, wait_sec=0.05)
    out.update(over)
    return out


def full_frame(days_raw, tf="5m", read_at=None):
    raw, _ = RC.clean({d.isoformat(): df for d, df in days_raw.items() if df is not None})
    return RC.frame_of(raw, tf, read_at or NOW_CLOSED)


def curve(p, tone):
    return next((c["values"] for c in p["curves"] if c["tone"] == tone), None)


# ── 1. tf_of / no session-count argument ─────────────────────────────────────────────────────────────────────────
def test_01_tf_of_every_frame_key_and_NEGATIVES_fall_back_to_the_default():
    from fastapi import Query
    for k, _rule in C.RUNCHART_FRAMES:
        assert RC.tf_of(k) == k
    for bad in ("3m", "", None, 5, Query(None), "5M", " 5m"):
        assert RC.tf_of(bad) == C.RUNCHART_DEFAULT_TF == GC.RUN_BASE_FRAME == "5m"


def test_01_NEGATIVE_no_sessions_reader_and_build_takes_no_sessions_argument():
    assert not hasattr(RC, "sessions_of")
    assert not hasattr(C, "RUNCHART_SESSIONS_MAX")
    with pytest.raises(TypeError):
        RC.build("X", sessions=3)


# ── 2. days_for ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_02_days_for_walks_the_house_calendar_and_NEGATIVE_never_a_holiday_or_weekend():
    days, session, is_today, in_window = RC.days_for(datetime(2026, 11, 27, 10, 0, tzinfo=ET), 6)
    assert [d.isoformat() for d in days] == ["2026-11-19", "2026-11-20", "2026-11-23", "2026-11-24", "2026-11-25",
                                             "2026-11-27"]
    assert session == date(2026, 11, 27) and is_today is True and in_window is True
    assert date(2026, 11, 26) not in days and not any(d.weekday() >= 5 for d in days)
    L = Loader()
    p = RC.build("BGLC", datetime(2026, 11, 27, 10, 0, tzinfo=ET), **kw(L))
    assert p["state"] == "ok"
    asked = L.days_asked()
    assert date(2026, 11, 26) not in asked and not any(d.weekday() >= 5 for d in asked)
    assert sorted(asked) == days


def test_02_days_for_closed_day_sunday_and_before_four():
    days, session, is_today, _w = RC.days_for(datetime(2026, 11, 26, 12, 0, tzinfo=ET), 6)
    assert days[-1] == date(2026, 11, 25) and session == date(2026, 11, 25) and is_today is False
    assert RC.days_for(datetime(2026, 11, 22, 12, 0, tzinfo=ET), 1)[0] == [date(2026, 11, 20)]      # Sunday → Friday
    assert RC.days_for(datetime(2026, 11, 24, 3, 59, tzinfo=ET), 1)[0] == [date(2026, 11, 23)]      # before 04:00


# ── 3. load_days + the chart's own breaker ───────────────────────────────────────────────────────────────────────
def test_03_load_days_newest_first_force_only_on_force_day_and_both_extended_sessions():
    L = Loader({D[23]: None, D[20]: "fail", D[19]: "raise"})
    parts, status = RC.load_days("BRK-B", CLOSED_DAYS, force_day=D[25], load_day=L, clock=Clock())
    assert L.days_asked() == sorted(CLOSED_DAYS, reverse=True)
    assert [c["force"] for c in L.calls] == [True, False, False, False, False, False]
    assert all(c["pre"] is True and c["ah"] is True for c in L.calls)
    assert {c["sym"] for c in L.calls} == {"BRK.B"}
    assert all("cb" not in c["kw"] for c in L.calls)                    # an injected loader is called WITHOUT cb
    assert status == {"2026-11-25": "loaded", "2026-11-24": "loaded", "2026-11-23": "no_bars",
                      "2026-11-20": "failed", "2026-11-19": "failed", "2026-11-18": "loaded"}
    assert set(parts) == {"2026-11-25", "2026-11-24", "2026-11-18"}


def test_03_NEGATIVE_past_the_budget_is_over_budget_and_the_loader_is_not_called_again():
    clk = Clock(0.0)
    L = Loader(clock=clk, tick=7.0)
    parts, status = RC.load_days("AAA", CLOSED_DAYS, load_day=L, budget_sec=12, clock=clk)
    assert L.days_asked() == [D[25], D[24]]
    assert status["2026-11-23"] == status["2026-11-20"] == status["2026-11-19"] == status["2026-11-18"] == "over_budget"
    assert set(parts) == {"2026-11-25", "2026-11-24"}


def test_03_the_default_loader_hands_the_charts_own_breaker_and_NEGATIVES(monkeypatch):
    seen = []

    def fake_load(sym, day, force=False, include_premarket=True, include_afterhours=False, cb=None):
        seen.append(cb)
        return raw_day(day)
    monkeypatch.setattr(dt_data, "load_intraday", fake_load)
    RC.load_days("AAA", CLOSED_DAYS[:3], clock=Clock())
    RC.load_days("BBB", CLOSED_DAYS[3:], clock=Clock())
    b = RC.breaker()
    assert len(seen) == 6 and all(x is b for x in seen)
    assert b is not dt_data._CB
    from chart_maps.gajjala_watch import rest
    assert b is not rest.breaker()
    assert set(b) == set(dt_data.new_breaker())
    RC.reset()
    assert RC.breaker() is not b


# ── 5 (function). cached_at ──────────────────────────────────────────────────────────────────────────────────────
class _Coll:
    def __init__(self, docs, fail=False):
        self.docs, self.fail, self.queries = docs, fail, []

    def find(self, q, proj=None):
        self.queries.append((q, proj))
        if self.fail:
            raise RuntimeError("mongo down")
        return [d for d in self.docs if d.get("symbol") == q["symbol"] and d.get("date") in q["date"]["$in"]]


def test_cached_at_reads_one_projected_find_naive_stamp_is_utc_and_NEGATIVES():
    naive = datetime(2026, 11, 25, 14, 0)
    coll = _Coll([{"symbol": "BRK.B", "date": "2026-11-24", "cached_at": naive},
                  {"symbol": "BRK.B", "date": "2026-11-23", "cached_at": "2026-11-23T10:00"},     # not a datetime
                  {"symbol": "BRK.B", "date": "2026-11-20"}])                                     # no stamp
    out = RC.cached_at("BRK-B", ["2026-11-24", "2026-11-23", "2026-11-20"], coll=coll)
    assert out == {"2026-11-24": naive.replace(tzinfo=timezone.utc)}
    assert coll.queries == [({"symbol": "BRK.B", "date": {"$in": ["2026-11-24", "2026-11-23", "2026-11-20"]}},
                             {"_id": 0, "date": 1, "cached_at": 1})]
    empty = _Coll([])
    assert RC.cached_at("AAA", [], coll=empty) == {} and empty.queries == []
    assert RC.cached_at("AAA", ["2026-11-24"], coll=_Coll([], fail=True)) == {}


def test_cached_at_NEGATIVE_no_collection_is_empty(monkeypatch):
    monkeypatch.setattr(dt_data, "_get_mongo_coll", lambda: None)
    assert RC.cached_at("AAA", ["2026-11-24"]) == {}


# ── 4. clean ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_04_clean_duplicate_minute_keeps_the_last_and_NEGATIVE_bad_bars_dropped_and_counted():
    a = raw_day(D[24], start=(9, 30), end=(9, 40))
    b = a.iloc[[3]].copy()
    b["close"] = 99.0
    bad = a.copy()
    bad.index = bad.index + pd.Timedelta(minutes=30)
    bad.iloc[0, bad.columns.get_loc("close")] = float("nan")
    bad.iloc[1, bad.columns.get_loc("high")] = float("inf")
    bad.iloc[2, bad.columns.get_loc("low")] = 0.0
    bad.iloc[3, bad.columns.get_loc("open")] = -1.0
    bad.iloc[4, bad.columns.get_loc("volume")] = float("nan")
    bad.iloc[5, bad.columns.get_loc("volume")] = -5.0
    raw, dropped = RC.clean({"x": a, "y": b, "z": bad})
    assert dropped == 4
    assert raw.loc[a.index[3], "close"] == 99.0
    assert not raw.index.duplicated().any() and raw.index.is_monotonic_increasing
    assert raw.loc[bad.index[4], "volume"] == 0.0 and raw.loc[bad.index[5], "volume"] == 0.0
    assert len(raw) == 10 + 6
    allbad = a.iloc[:2].copy()
    allbad["close"] = float("nan")
    assert RC.clean({"x": allbad}) == (None, 2)
    assert RC.clean({}) == (None, 0) and RC.clean({"x": None}) == (None, 0)


# ── 5. session tags ──────────────────────────────────────────────────────────────────────────────────────────────
def test_05_session_tags_equal_the_loaders_on_a_normal_day():
    from supply_demand.timeframes import resample_ohlcv
    res = resample_ohlcv(raw_day(D[24]), "5min")
    tags = RC.session_tags(RC._starts(res.index, "5min"))
    assert tags == res["session"].tolist()
    assert set(tags) == {"premarket", "rth", "afterhours"}


def test_05_half_day_one_pm_is_after_hours_NEGATIVE_not_regular():
    assert HALF.isoformat() in AL.HALF_DAYS
    st = [pd.Timestamp(datetime(2026, 11, 27, h, m), tz=ET) for h, m in ((12, 55), (13, 0), (16, 55), (9, 25))]
    assert RC.session_tags(st) == ["rth", "afterhours", "afterhours", "premarket"]
    normal = [pd.Timestamp(datetime(2026, 11, 25, h, m), tz=ET) for h, m in ((13, 0), (15, 55), (16, 0))]
    assert RC.session_tags(normal) == ["rth", "rth", "afterhours"]


# ── 6. EMA continuity ────────────────────────────────────────────────────────────────────────────────────────────
def _ema_all(F, span):
    return [round(float(x), 6) for x in SG.ema(F.df["close"].astype(float), span).tolist()]


def test_06_the_drawn_emas_equal_the_one_engine_over_every_loaded_close():
    p = RC.build("BGLC", NOW_CLOSED, tf="5m", **kw())
    F = full_frame({d: raw_day(d, seed=d.day) for d in CLOSED_DAYS})
    n = len(p["bars"])
    assert p["seed"] == {"sessions": 1, "bars": len(F) - n} and p["seed"]["bars"] == 192
    for tone, span in (("ema9", GC.EMA_FAST), ("ema21", GC.EMA_SLOW)):
        assert curve(p, tone) == _ema_all(F, span)[-n:]
    assert curve(p, "ema21")[0] is not None                              # a full seed session → a number at once


def test_06_NEGATIVE_a_level_shift_is_carried_never_restarted_at_a_session_or_at_0930():
    level = {d: 5.0 + 3.0 * i for i, d in enumerate(CLOSED_DAYS)}
    days = {d: raw_day(d, price=lambda ts, d=d: round(level[d] + 0.05 * math.sin(ts.minute / 7.0), 4))
            for d in CLOSED_DAYS}
    p = RC.build("SHFT", NOW_CLOSED, tf="5m", **kw(Loader(days)))
    s2 = p["sessions"][1]
    assert s2["date"] == "2026-11-20"
    e21 = curve(p, "ema21")
    closes = [b["c"] for b in p["bars"]]
    restart_session = [round(float(x), 6) for x in SG.ema(pd.Series(closes[s2["from"]:s2["to"] + 1]), 21)]
    assert e21[s2["from"]] != restart_session[0]
    i930 = next(i for i in range(s2["from"], s2["to"] + 1) if p["bars"][i].get("s") is None)
    restart_930 = round(float(SG.ema(pd.Series(closes[i930:s2["to"] + 1]), 21).iloc[0]), 6)
    assert e21[i930] != restart_930
    assert abs(e21[s2["from"]] - level[D[19]]) < abs(e21[s2["from"]] - level[D[20]])   # still carrying the 11-19 level


def test_06_NEGATIVE_one_session_only_the_first_slow_minus_one_values_are_a_gap():
    only = {d: None for d in CLOSED_DAYS[:-1]}
    p = RC.build("ONE", NOW_CLOSED, tf="5m", **kw(Loader(only)))
    e21, e9 = curve(p, "ema21"), curve(p, "ema9")
    assert len(p["sessions"]) == 1 and p["seed"] == {"sessions": 0, "bars": 0}
    assert e21[:GC.EMA_SLOW - 1] == [None] * (GC.EMA_SLOW - 1) and e21[GC.EMA_SLOW - 1] is not None
    assert e9[:GC.EMA_FAST - 1] == [None] * (GC.EMA_FAST - 1) and e9[GC.EMA_FAST - 1] is not None


# ── 7. chart_x ───────────────────────────────────────────────────────────────────────────────────────────────────
def _hm(x):
    return datetime.fromtimestamp(x, timezone.utc).strftime("%Y-%m-%d %H:%M")


def test_07_chart_x_is_the_et_wall_clock_in_summer_and_winter():
    xs = RC.chart_x([pd.Timestamp(datetime(2026, 7, 15, 9, 30), tz=ET), pd.Timestamp(datetime(2026, 11, 25, 9, 30),
                                                                                         tz=ET)])
    assert [_hm(x) for x in xs] == ["2026-07-15 09:30", "2026-11-25 09:30"]


def test_07_chart_x_strictly_ascending_across_the_clock_change_and_the_2000_bar_starts_at_1955():
    days = {d: None for d in (date(2026, 10, 26), date(2026, 10, 27), date(2026, 10, 28), date(2026, 10, 29))}
    p = RC.build("DST", datetime(2026, 11, 3, 3, 0, tzinfo=ET), tf="5m", **kw(Loader(days)))
    assert [s["date"] for s in p["sessions"]] == ["2026-10-30", "2026-11-02"]
    xs = [b["x"] for b in p["bars"]]
    assert all(b > a for a, b in zip(xs, xs[1:]))
    for s in p["sessions"]:
        first_reg = next(b for b in p["bars"][s["from"]:s["to"] + 1] if b.get("s") is None)
        assert _hm(first_reg["x"]) == s["date"] + " 09:30" and first_reg["t"] == s["date"] + " 09:35"
    last = next(b for b in p["bars"] if b["t"] == "2026-11-02 20:00")
    assert _hm(last["x"]) == "2026-11-02 19:55"


# ── 8. the ok payload ────────────────────────────────────────────────────────────────────────────────────────────
KEYS = {"state", "symbol", "tf", "frame_min", "frames", "title", "text", "notes", "as_of_text", "as_of_bar_t", "live",
        "refresh_sec", "hint", "words", "ran", "sessions", "bars", "curves", "vol_avg", "shade", "view", "seed",
        "dropped"}


def test_08_ok_payload_keys_partition_shade_lengths_and_strict_json():
    p = RC.build("BGLC", NOW_CLOSED, tf="5m", **kw())
    assert set(p) == KEYS and p["state"] == "ok" and p["text"] is None
    assert p["tf"] == "5m" and p["frame_min"] == 5
    assert p["frames"] == [{"key": "1m", "label": "1-min"}, {"key": "5m", "label": "5-min"},
                           {"key": "15m", "label": "15-min"}]
    assert [s["date"] for s in p["sessions"]] == DRAWN and p["sessions"][-1]["label"] == "Wed 11-25"
    nxt = 0
    for s in p["sessions"]:
        assert s["from"] == nxt and s["to"] >= s["from"] and s["half_day"] is False and s["ran"] is False
        nxt = s["to"] + 1
    assert nxt == len(p["bars"])
    covered = set()
    for sh in p["shade"]:
        sess = [s for s in p["sessions"] if s["from"] <= sh["from"] <= s["to"]]
        assert len(sess) == 1 and sh["to"] <= sess[0]["to"]
        assert all(p["bars"][i].get("s") == sh["kind"] for i in range(sh["from"], sh["to"] + 1))
        covered |= set(range(sh["from"], sh["to"] + 1))
    assert covered == {i for i, b in enumerate(p["bars"]) if b.get("s")}
    for c in p["curves"]:
        assert len(c["values"]) == len(p["bars"])
    assert len(p["vol_avg"]["values"]) == len(p["bars"]) and p["vol_avg"]["period"] == 50
    F = full_frame({d: raw_day(d, seed=d.day) for d in CLOSED_DAYS})
    assert [{k: v for k, v in b.items() if k != "x"} for b in p["bars"]] == _frame_bars(F.df.iloc[192:])
    json.dumps(_scrub(p), allow_nan=False)
    assert p["view"] == {"sessions": C.RUNCHART_VIEW_SESSIONS, "sessions_phone": C.RUNCHART_VIEW_SESSIONS_PHONE,
                         "right_gap_bars": C.RUNCHART_RIGHT_GAP_BARS}
    assert p["words"] == C.RUNCHART_WORDS and p["notes"] == [] and p["dropped"] == 0
    assert p["as_of_bar_t"] == "2026-11-25 20:00"


def test_08_words_and_numbers_move_with_their_constants_nothing_typed(monkeypatch):
    monkeypatch.setattr(C, "RUNCHART_TITLE", "T|{sym}|{frame}|{first}|{last}")
    monkeypatch.setattr(C, "RUNCHART_ASOF_TEXT", "A|{bar}|{at}")
    monkeypatch.setattr(C, "RUNCHART_HINT", "H|{frame}|{n}|{open}|{end}|{seed}|{slow}|{vol}|{memo}")
    monkeypatch.setattr(C, "RUNCHART_MEMO_SEC", 90)
    p = RC.build("BGLC", NOW_LIVE, tf="15m", **kw())
    assert p["title"] == "T|BGLC|15-min|Thu 11-19|Wed 11-25"
    assert p["as_of_text"].startswith("A|Wed 11-25 ") and p["as_of_text"].endswith("|10:00")
    assert p["hint"] == "H|15-min|5|04:00|20:00|1|21|50|90"
    assert p["live"] is True and p["refresh_sec"] == 90


# ── 9. empty ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_09_NEGATIVE_no_bars_is_empty_with_the_sentence_never_an_empty_ok():
    p = RC.build("NONE", NOW_CLOSED, **kw(Loader({d: None for d in CLOSED_DAYS})))
    assert p["state"] == "empty" and p["state"] != "ok"
    assert p["text"] == C.RUNCHART_EMPTY_TEXT.format(sym="NONE", n=C.RUNCHART_SESSIONS, first="Thu 11-19",
                                                     last="Wed 11-25")
    assert p["bars"] == [] and p["sessions"] == [] and p["curves"] == [] and p["shade"] == []
    assert p["symbol"] == "NONE" and p["tf"] == "5m" and p["title"] and p["frames"]


# ── 10. splits ───────────────────────────────────────────────────────────────────────────────────────────────────
def _stamps(by_iso):
    return lambda s, isos: {i: by_iso[i] for i in isos if i in by_iso}


AFTER = datetime(2026, 11, 25, 15, 0, tzinfo=timezone.utc)


def test_10_every_earlier_day_read_after_the_split_draws_every_session_and_says_so():
    p = RC.build("SPL", NOW_CLOSED, **kw(splits_fn=lambda s, i: SPLIT,
                                       cached_at_fn=_stamps({d.isoformat(): AFTER for d in CLOSED_DAYS})))
    assert [s["date"] for s in p["sessions"]] == DRAWN
    assert [n["kind"] for n in p["notes"]] == ["split_adjusted"]
    assert "1-for-10" in p["notes"][0]["text"] and "Tue 11-24" in p["notes"][0]["text"]
    F = full_frame({d: raw_day(d, seed=d.day) for d in CLOSED_DAYS})
    assert curve(p, "ema21") == _ema_all(F, GC.EMA_SLOW)[-len(p["bars"]):]


def test_10_NEGATIVE_a_day_saved_before_the_split_is_not_drawn_and_named():
    st = {d.isoformat(): AFTER for d in CLOSED_DAYS}
    st["2026-11-20"] = datetime(2026, 11, 21, 15, 0, tzinfo=timezone.utc)
    p = RC.build("SPL", NOW_CLOSED, **kw(splits_fn=lambda s, i: SPLIT, cached_at_fn=_stamps(st)))
    assert [s["date"] for s in p["sessions"]] == ["2026-11-23", "2026-11-24", "2026-11-25"]
    assert all(b["t"] >= "2026-11-23" for b in p["bars"])
    kinds = [n["kind"] for n in p["notes"]]
    assert kinds == ["split"] and "split_adjusted" not in kinds
    text = p["notes"][0]["text"]
    assert "may be" in text and "Wed 11-18, Thu 11-19, Fri 11-20 were saved" in text and "Mon 11-23" not in text


def test_10_NEGATIVE_a_day_saved_on_the_split_day_is_not_proven_unless_his_call(monkeypatch):
    st = {d.isoformat(): AFTER for d in CLOSED_DAYS}
    st["2026-11-23"] = datetime(2026, 11, 24, 15, 0, tzinfo=timezone.utc)
    args = dict(splits_fn=lambda s, i: SPLIT, cached_at_fn=_stamps(st))
    p = RC.build("SPL", NOW_CLOSED, **kw(**args))
    assert [s["date"] for s in p["sessions"]] == ["2026-11-24", "2026-11-25"]
    RC.reset()
    monkeypatch.setattr(C, "RUNCHART_SPLIT_SAME_DAY_OK", True)
    p = RC.build("SPL", NOW_CLOSED, **kw(**args))
    assert [s["date"] for s in p["sessions"]] == DRAWN and [n["kind"] for n in p["notes"]] == ["split_adjusted"]


def test_10_NEGATIVE_no_stamp_at_all_starts_at_the_split_day():
    p = RC.build("SPL", NOW_CLOSED, **kw(splits_fn=lambda s, i: SPLIT, cached_at_fn=lambda s, i: {}))
    assert [s["date"] for s in p["sessions"]] == ["2026-11-24", "2026-11-25"]
    assert p["seed"]["sessions"] == 0


def test_10_the_stamp_is_judged_by_its_et_date_not_the_utc_one():
    late = datetime(2026, 11, 25, 3, 30, tzinfo=timezone.utc)            # = Tue 11-24 22:30 ET → ON the split day
    stamps = {d.isoformat(): AFTER for d in CLOSED_DAYS}
    stamps["2026-11-23"] = late
    loaded = [d.isoformat() for d in CLOSED_DAYS]
    cut = RC.split_cut(CLOSED_DAYS, loaded, stamps, SPLIT)
    assert cut["cut_iso"] == "2026-11-24" and cut["adjusted"] is False
    stamps["2026-11-23"] = datetime(2026, 11, 25, 5, 30, tzinfo=timezone.utc)   # = Wed 11-25 00:30 ET → after
    assert RC.split_cut(CLOSED_DAYS, loaded, stamps, SPLIT)["adjusted"] is True


def test_10_two_splits_the_latest_decides_and_a_split_on_the_oldest_day_says_nothing():
    loaded = [d.isoformat() for d in CLOSED_DAYS]
    mid = datetime(2026, 11, 22, 15, 0, tzinfo=timezone.utc)
    stamps = {i: mid for i in loaded}
    early = [{"execution_date": "2026-11-20", "split_from": 1.0, "split_to": 2.0}]
    assert RC.split_cut(CLOSED_DAYS, loaded, stamps, early)["adjusted"] is True
    both = early + SPLIT
    cut = RC.split_cut(CLOSED_DAYS, loaded, stamps, both)
    assert cut["split"]["execution_date"] == "2026-11-24" and cut["cut_iso"] == "2026-11-24"
    on_oldest = [{"execution_date": "2026-11-18", "split_from": 10.0, "split_to": 1.0}]
    assert RC.split_cut(CLOSED_DAYS, loaded, {}, on_oldest) == {"split": None, "cut_iso": None, "not_drawn": [],
                                                                  "adjusted": False}
    on_first_loaded = [{"execution_date": "2026-11-23", "split_from": 10.0, "split_to": 1.0}]
    assert RC.split_cut(CLOSED_DAYS, loaded[3:], {}, on_first_loaded)["cut_iso"] is None
    for none in (None, []):
        assert RC.split_cut(CLOSED_DAYS, loaded, {}, none)["cut_iso"] is None


def test_10_a_raising_split_check_draws_all_with_a_note_and_nobody_asks_inside_the_retry():
    clk = Clock(0.0)
    asked = []

    def bad(sym, since):
        asked.append(sym)
        raise RuntimeError("down")
    p = RC.build("AAA", NOW_CLOSED, **kw(clock=clk, splits_fn=bad))
    assert [s["date"] for s in p["sessions"]] == DRAWN and [n["kind"] for n in p["notes"]] == ["split_unchecked"]
    assert asked == ["AAA"]
    clk.t = C.RUNCHART_SPLIT_RETRY_SEC - 1
    RC.build("AAA", NOW_CLOSED, **kw(clock=clk, splits_fn=bad, tf="15m"))
    RC.build("BBB", NOW_CLOSED, **kw(clock=clk, splits_fn=bad))
    assert asked == ["AAA"]
    clk.t = C.RUNCHART_SPLIT_RETRY_SEC + 1
    RC.build("CCC", NOW_CLOSED, **kw(clock=clk, splits_fn=bad))
    assert asked == ["AAA", "CCC"]


def test_10_an_answered_split_check_is_asked_once_per_window():
    asked = []
    fn = lambda s, i: asked.append((s, i)) or []                         # noqa: E731
    for tf in ("5m", "15m", "1m"):
        RC.build("AAA", NOW_CLOSED, **kw(splits_fn=fn, tf=tf))
    assert asked == [("AAA", "2026-11-18")]


def test_10_NEGATIVE_the_newest_day_failed_never_calls_the_split_check():
    asked = []
    p = RC.build("AAA", NOW_CLOSED, **kw(Loader({D[25]: "fail"}), splits_fn=lambda s, i: asked.append(s) or []))
    assert asked == [] and p["state"] == "ok"
    assert {n["kind"] for n in p["notes"]} == {"split_unchecked", "failed"}


def test_10_NEGATIVE_an_unchecked_split_payload_is_never_held_and_the_same_name_asks_again_past_the_retry(monkeypatch):
    real = RC.payload
    built = []
    monkeypatch.setattr(RC, "payload", lambda *a, **k: built.append(1) or real(*a, **k))
    clk = Clock(0.0)
    asked = []

    def flaky(sym, since):
        asked.append(sym)
        if len(asked) == 1:
            raise RuntimeError("down")
        return SPLIT
    L = Loader()
    args = kw(L, clock=clk, splits_fn=flaky, cached_at_fn=lambda s, i: {})
    p1 = RC.build("AAA", NOW_CLOSED, **args)                                 # closed day, the split check raises once
    assert [s["date"] for s in p1["sessions"]] == DRAWN and [n["kind"] for n in p1["notes"]] == ["split_unchecked"]
    assert ("AAA", "5m") not in RC._BUILT and asked == ["AAA"] and len(L.calls) == 6
    clk.t = C.RUNCHART_SPLIT_RETRY_SEC - 1                                   # inside the retry: rebuilt, nobody asks
    p2 = RC.build("AAA", NOW_CLOSED, **args)
    assert p2 is not p1 and len(built) == 2 and asked == ["AAA"] and len(L.calls) == 6
    assert ("AAA", "5m") not in RC._BUILT
    clk.t = C.RUNCHART_SPLIT_RETRY_SEC + 1                                   # past it: the SAME name and frame ask again
    p3 = RC.build("AAA", NOW_CLOSED, **args)
    assert asked == ["AAA", "AAA"] and len(L.calls) == 6
    assert [s["date"] for s in p3["sessions"]] == ["2026-11-24", "2026-11-25"]
    assert "split_unchecked" not in [n["kind"] for n in p3["notes"]]
    for t in (3600.0, 6 * 3600.0):                                           # answered → held, served as is
        clk.t = t
        assert RC.build("AAA", NOW_CLOSED, **args) is p3
    assert asked == ["AAA", "AAA"] and len(built) == 3


def test_10_the_newest_day_failing_keeps_the_held_split_answer_and_NEGATIVE_never_reads_or_unchecks():
    clk = Clock(0.0)
    asked = []
    fn = lambda s, i: asked.append((s, i)) or SPLIT                      # noqa: E731
    before = datetime(2026, 11, 21, 15, 0, tzinfo=timezone.utc)
    st = {d.isoformat(): before for d in (D[18], D[19], D[20], D[23])}
    st["2026-11-24"] = AFTER
    L = Loader(live_end=(D[25], (10, 0)))
    args = dict(splits_fn=fn, cached_at_fn=_stamps(st))
    p1 = RC.build("SPL", NOW_LIVE, **kw(L, clock=clk, **args))
    assert [s["date"] for s in p1["sessions"]] == ["2026-11-24", "2026-11-25"]
    assert [n["kind"] for n in p1["notes"]] == ["split"] and asked == [("SPL", "2026-11-18")]
    clk.t = max(61.0, float(C.RUNCHART_MEMO_SEC) + 1)
    L.days[D[25]] = "fail"
    p2 = RC.build("SPL", NOW_LIVE, **kw(L, clock=clk, **args))
    assert L.calls[-1]["day"] == D[25] and len(L.calls) == 7
    assert asked == [("SPL", "2026-11-18")]                              # held answer, no second read
    kinds = [n["kind"] for n in p2["notes"]]
    assert "split" in kinds and "failed" in kinds and "split_unchecked" not in kinds
    assert [s["date"] for s in p2["sessions"]] == ["2026-11-24"]
    assert all(b["t"] >= "2026-11-24" for b in p2["bars"])               # never old and new share count together
    assert RC._SPLIT_DOWN["until"] <= clk.t


def test_10_NEGATIVE_a_failed_newest_day_never_borrows_another_names_or_windows_answer():
    asked = []
    fn = lambda s, i: asked.append(s) or SPLIT                           # noqa: E731
    RC.build("AAA", NOW_CLOSED, **kw(splits_fn=fn))
    assert asked == ["AAA"]
    p = RC.build("BBB", NOW_CLOSED, **kw(Loader({D[25]: "fail"}), splits_fn=fn))
    assert asked == ["AAA"] and {n["kind"] for n in p["notes"]} == {"split_unchecked", "failed"}
    assert RC.splits_in("AAA", CLOSED_DAYS, splits_fn=fn, fetch=False) == RC._in_window(SPLIT, "2026-11-18",
                                                                                         "2026-11-25")
    assert RC.splits_in("AAA", CLOSED_DAYS[1:], splits_fn=fn, fetch=False) is None
    assert asked == ["AAA"]


def test_10_split_cut_is_pure():
    loaded = [d.isoformat() for d in CLOSED_DAYS]
    stamps = {"2026-11-20": datetime(2026, 11, 21, 15, 0, tzinfo=timezone.utc)}
    a = RC.split_cut(CLOSED_DAYS, loaded, dict(stamps), [dict(SPLIT[0])])
    b = RC.split_cut(CLOSED_DAYS, loaded, dict(stamps), [dict(SPLIT[0])])
    assert a == b and a["cut_iso"] == "2026-11-24"
    assert a["not_drawn"] == ["2026-11-18", "2026-11-19", "2026-11-20", "2026-11-23"]
    body = SRC[SRC.index("def split_cut("):SRC.index("# ── 9-12.")]
    for bad in ("clock", "time.", "_LOCK", ".find(", "fetch_splits", "datetime.now"):
        assert bad not in body, bad


# ── 11. failed / over budget ─────────────────────────────────────────────────────────────────────────────────────
def test_11_a_failed_day_is_named_then_asked_again_alone_and_NEGATIVE_never_served_from_the_memo(monkeypatch):
    real = RC.payload
    built = []
    monkeypatch.setattr(RC, "payload", lambda *a, **k: built.append(1) or real(*a, **k))
    L = Loader({D[23]: "fail"})
    args = kw(L)
    p = RC.build("AAA", NOW_CLOSED, **args)
    assert p["state"] == "ok" and [n["kind"] for n in p["notes"]] == ["failed"]
    assert "Mon 11-23" in p["notes"][0]["text"] and "2026-11-23" not in [s["date"] for s in p["sessions"]]
    RC.build("AAA", NOW_CLOSED, **args)                                  # still failing → payload built again
    assert len(built) == 2 and L.days_asked()[6:] == [D[23]]
    L.days[D[23]] = "default"
    p = RC.build("AAA", NOW_CLOSED, **args)
    assert L.days_asked()[7:] == [D[23]] and p["notes"] == [] and [s["date"] for s in p["sessions"]] == DRAWN
    assert len(built) == 3
    RC.build("AAA", NOW_CLOSED, **args)
    assert len(built) == 3 and len(L.calls) == 8                         # now served from the memo


def test_11_over_budget_says_reopen_and_the_reopen_loads():
    clk = Clock(0.0)
    L = Loader(clock=clk, tick=5.0)
    p = RC.build("AAA", NOW_CLOSED, **kw(L, clock=clk))
    assert [n["kind"] for n in p["notes"]] == ["budget"]
    assert "Wed 11-18, Thu 11-19, Fri 11-20" in p["notes"][0]["text"]
    p = RC.build("AAA", NOW_CLOSED, **kw(L, clock=clk))
    assert L.days_asked()[3:] == [D[20], D[19], D[18]]
    assert p["notes"] == [] and [s["date"] for s in p["sessions"]] == DRAWN


def test_11_NEGATIVE_error_when_nothing_drawn_and_the_feed_failed_vs_fault_two_sentences(monkeypatch):
    p = RC.build("AAA", NOW_CLOSED, **kw(Loader({d: "fail" for d in CLOSED_DAYS})))
    assert p["state"] == "error" and p["text"] == C.RUNCHART_ERROR_TEXT.format(sym="AAA") and p["bars"] == []
    RC.reset()
    monkeypatch.setattr(RC, "payload", lambda *a, **k: 1 / 0)
    q = RC.build("AAA", NOW_CLOSED, **kw())
    assert q["state"] == "error" and q["text"] == C.RUNCHART_FAULT_TEXT.format(sym="AAA")
    assert p["text"] != q["text"]


# ── 12. day memo ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_12_completed_days_are_asked_once_only_the_live_day_again():
    clk = Clock(0.0)
    L = Loader({D[24]: None}, live_end=(D[25], (10, 0)))
    RC.build("AAA", NOW_LIVE, **kw(L, clock=clk))
    assert len(L.calls) == 6
    for k in (1, 2):
        clk.t += 56
        RC.build("AAA", NOW_LIVE, **kw(L, clock=clk))
        assert len(L.calls) == 6 + k and L.calls[-1]["day"] == D[25] and L.calls[-1]["force"] is True
    assert not any(k[1] == "2026-11-25" for k in RC._DAYS)
    assert ("AAA", "2026-11-24") in RC._DAYS and RC._DAYS[("AAA", "2026-11-24")][1] is None


def test_12_NEGATIVE_a_new_session_asks_again_eviction_and_reset(monkeypatch):
    L = Loader()
    RC.build("AAA", NOW_CLOSED, **kw(L))
    RC.build("AAA", datetime(2026, 11, 27, 10, 0, tzinfo=ET), **kw(L, clock=Clock(5000.0)))
    assert len(L.calls) == 12
    RC.reset()
    monkeypatch.setattr(C, "RUNCHART_MEMO_MAX", 2)
    clk = Clock(0.0)
    L = Loader()
    for i, s in enumerate(("AAA", "BBB", "CCC")):
        clk.t = float(i)
        RC.build(s, NOW_CLOSED, **kw(L, clock=clk))
    assert not any(k[0] == "AAA" for k in RC._DAYS) and ("AAA", "5m") not in RC._BUILT
    assert set(RC._SEEN) == {"BBB", "CCC"}
    n = len(L.calls)
    clk.t = 10.0
    RC.build("AAA", NOW_CLOSED, **kw(L, clock=clk))
    assert len(L.calls) == n + 6
    RC.reset()
    assert not (RC._DAYS or RC._TODAY or RC._BUILT or RC._SPLITS or RC._SEEN or RC._GATES)
    assert RC._SPLIT_DOWN["until"] == 0.0 and RC._BREAKER is None


# ── 13. built memo ───────────────────────────────────────────────────────────────────────────────────────────────
def test_13_closed_day_second_build_is_the_same_object_with_zero_reads(monkeypatch):
    real = RC.payload
    built = []
    monkeypatch.setattr(RC, "payload", lambda *a, **k: built.append(a[2]) or real(*a, **k))
    L, sp, ca = Loader(), [], []
    args = kw(L, splits_fn=lambda s, i: sp.append(1) or [], cached_at_fn=lambda s, i: ca.append(1) or {})
    p1 = RC.build("AAA", NOW_CLOSED, **args)
    n = (len(L.calls), len(sp), len(ca), len(built))
    p2 = RC.build("AAA", NOW_CLOSED, **args)
    assert p2 is p1 and (len(L.calls), len(sp), len(ca), len(built)) == n
    p3 = RC.build("AAA", NOW_CLOSED, **dict(args, tf="1m"))
    assert len(L.calls) == n[0] and built[-1] == "1m" and len(built) == n[3] + 1 and p3["tf"] == "1m"
    assert RC.build("AAA", NOW_CLOSED, **dict(args, tf="1m")) is p3 and len(built) == n[3] + 1


def test_13_live_day_memo_follows_the_reads_age():
    clk = Clock(0.0)
    L = Loader(live_end=(D[25], (10, 0)))
    p1 = RC.build("AAA", NOW_LIVE, **kw(L, clock=clk))
    clk.t = 54
    assert RC.build("AAA", NOW_LIVE, **kw(L, clock=clk)) is p1 and len(L.calls) == 6
    clk.t = 56
    p3 = RC.build("AAA", NOW_LIVE, **kw(L, clock=clk))
    assert p3 is not p1 and len(L.calls) == 7 and L.calls[-1]["day"] == D[25]


def test_13_NEGATIVE_a_payload_from_an_old_read_ages_with_the_read_not_the_build():
    clk = Clock(0.0)
    L = Loader(live_end=(D[25], (10, 0)))
    RC.build("AAA", NOW_LIVE, **kw(L, clock=clk))
    clk.t = 50
    p = RC.build("AAA", NOW_LIVE, **kw(L, clock=clk, tf="15m"))
    assert len(L.calls) == 6
    clk.t = 60
    q = RC.build("AAA", NOW_LIVE, **kw(L, clock=clk, tf="15m"))
    assert q is not p and len(L.calls) == 7


def test_13_the_built_memo_is_bounded(monkeypatch):
    L = Loader()
    for s in ("AAA", "BBB", "CCC", "DDD"):
        for tf in ("1m", "5m", "15m"):
            RC.build(s, NOW_CLOSED, **kw(L, tf=tf))
            assert len(RC._BUILT) <= C.RUNCHART_BUILT_MAX
    assert len(RC._BUILT) == C.RUNCHART_BUILT_MAX


# ── 14. gate ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_14_a_held_gate_answers_busy_and_NEGATIVE_another_name_is_not_blocked():
    g = RC._gate("AAA")
    assert g.acquire()
    try:
        L = Loader()
        p = RC.build("AAA", NOW_CLOSED, **kw(L, wait_sec=0.05))
        assert p == {"state": "busy", "symbol": "AAA",
                     "text": C.RUNCHART_BUSY_TEXT.format(sym="AAA", sec=C.RUNCHART_BUSY_RETRY_SEC),
                     "retry_sec": C.RUNCHART_BUSY_RETRY_SEC}
        assert L.calls == [] and p["text"] != C.RUNCHART_ERROR_TEXT.format(sym="AAA")
        assert RC.build("BBB", NOW_CLOSED, **kw(L))["state"] == "ok"
    finally:
        g.release()


def test_14_NEGATIVE_the_module_lock_is_never_held_inside_a_read_or_a_build(monkeypatch):
    seen = []
    real = RC.payload
    monkeypatch.setattr(RC, "payload", lambda *a, **k: seen.append(("payload", RC._LOCK.locked())) or real(*a, **k))
    L = Loader(hook=lambda: seen.append(("load", RC._LOCK.locked())))
    RC.build("AAA", NOW_CLOSED, **kw(L, splits_fn=lambda s, i: seen.append(("splits", RC._LOCK.locked())) or [],
                                     cached_at_fn=lambda s, i: seen.append(("cached", RC._LOCK.locked())) or {}))
    assert {k for k, _ in seen} == {"payload", "load", "splits", "cached"}
    assert not any(v for _, v in seen)


def test_14_NEGATIVE_the_gate_is_free_after_a_raising_loader_or_a_raising_build(monkeypatch):
    p = RC.build("AAA", NOW_CLOSED, **kw(Loader({d: "raise" for d in CLOSED_DAYS})))
    assert p["state"] == "error"
    assert not RC._gate("AAA").locked()
    monkeypatch.setattr(RC, "payload", lambda *a, **k: 1 / 0)
    assert RC.build("AAA", NOW_CLOSED, **kw())["state"] == "error"
    assert not RC._gate("AAA").locked()
    monkeypatch.undo()
    assert RC.build("AAA", NOW_CLOSED, **kw())["state"] == "ok"


def test_14_two_threads_on_the_same_name_make_one_set_of_reads():
    go = threading.Event()
    started = threading.Event()

    def hook():
        started.set()
        go.wait(5)
    L = Loader(hook=hook)
    out = {}

    def run(k):
        out[k] = RC.build("AAA", NOW_CLOSED, **kw(L, wait_sec=5))
    t1 = threading.Thread(target=run, args=(1,))
    t1.start()
    assert started.wait(5)
    t2 = threading.Thread(target=run, args=(2,))
    t2.start()
    go.set()
    t1.join(10)
    t2.join(10)
    assert len(L.calls) == 6 and out[1]["state"] == "ok" and out[2] is out[1]


# ── 15. closed as of the READ ────────────────────────────────────────────────────────────────────────────────────
def test_15_a_reused_read_never_serves_a_bar_that_was_still_printing_when_read():
    clk = Clock(0.0)
    L = Loader(live_end=(D[25], (10, 5)))
    RC.build("AAA", datetime(2026, 11, 25, 10, 4, 50, tzinfo=ET), **kw(L, clock=clk, tf="1m"))
    clk.t = 45
    p = RC.build("AAA", datetime(2026, 11, 25, 10, 5, 35, tzinfo=ET), **kw(L, clock=clk, tf="5m"))
    assert len(L.calls) == 6
    assert p["bars"][-1]["t"] == "2026-11-25 10:00" and "2026-11-25 10:05" not in [b["t"] for b in p["bars"]]
    assert "read 10:04 ET" in p["as_of_text"]
    clk.t = 56
    L.live_end = (D[25], (10, 6))
    p = RC.build("AAA", datetime(2026, 11, 25, 10, 6, 0, tzinfo=ET), **kw(L, clock=clk, tf="5m"))
    assert len(L.calls) == 7 and p["bars"][-1]["t"] == "2026-11-25 10:05"


def test_15_NEGATIVE_on_completed_days_every_bar_is_served():
    p = RC.build("AAA", NOW_CLOSED, **kw(tf="5m"))
    assert len(p["bars"]) == 5 * 192 and p["bars"][-1]["t"] == "2026-11-25 20:00"


# ── 16. bar cap ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_16_the_bar_cap_drops_the_oldest_whole_sessions(monkeypatch):
    monkeypatch.setattr(C, "RUNCHART_MAX_BARS", 150)
    p = RC.build("AAA", NOW_CLOSED, **kw(tf="15m"))
    assert [s["date"] for s in p["sessions"]] == ["2026-11-24", "2026-11-25"]
    assert all(s["to"] - s["from"] + 1 == 64 for s in p["sessions"]) and len(p["bars"]) == 128
    assert p["notes"] == [{"kind": "bar_cap", "text": C.RUNCHART_BAR_CAP_TEXT.format(frame="15-min", k=2, n=5,
                                                                                     cap=150)}]


def test_16_NEGATIVE_never_a_cut_inside_a_single_session(monkeypatch):
    monkeypatch.setattr(C, "RUNCHART_MAX_BARS", 10)
    p = RC.build("ONE", NOW_CLOSED, **kw(Loader({d: None for d in CLOSED_DAYS[:-1]}), tf="15m"))
    assert len(p["sessions"]) == 1 and len(p["bars"]) == 64


# ── 17. VWAP ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_17_vwap_off_is_exactly_the_two_emas():
    p = RC.build("AAA", NOW_CLOSED, **kw(tf="1m"))
    assert [c["tone"] for c in p["curves"]] == ["ema9", "ema21"]


def test_17_vwap_on_restarts_every_session(monkeypatch):
    from chart_maps.gajjala_watch import vwap as VW
    monkeypatch.setattr(C, "RUNCHART_VWAP_ON", True)
    p = RC.build("AAA", NOW_CLOSED, **kw(tf="1m"))
    assert [c["tone"] for c in p["curves"]] == ["ema9", "ema21", C.VWAP_TONE]
    vals = p["curves"][2]["values"]
    assert len(vals) == len(p["bars"])
    for s in p["sessions"]:
        d = date.fromisoformat(s["date"])
        alone = VW.minute_vwap(raw_day(d, seed=d.day), s["date"], sessions=VW.sessions())
        assert vals[s["from"]] == round(float(alone.iloc[0]), C.VWAP_DP)


# ── 18. off / bad symbols ────────────────────────────────────────────────────────────────────────────────────────
def test_18_off_and_NEGATIVE_bad_symbols_read_nothing(monkeypatch):
    L = Loader()
    for bad in ("", "1ABC", "../x", None, 12):
        p = RC.build(bad, NOW_CLOSED, **kw(L))
        assert p == {"state": "bad_symbol", "symbol": None, "text": C.RUNCHART_BAD_SYMBOL_TEXT}
    monkeypatch.setattr(C, "RUNCHART_ON", False)
    assert RC.build("AAA", NOW_CLOSED, **kw(L)) == {"state": "off"}
    assert L.calls == []


# ── 19. ran ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_19_a_counted_run_is_served_and_marks_its_session():
    asked = []
    ran = {"BGLC": {"counts": True, "date": "2026-11-25", "text": "📅 ran Wed +176%", "title": "T", "run_pct": 176.0}}
    p = RC.build("BGLC", NOW_CLOSED, **kw(ran_fn=lambda n, d: asked.append((n, d)) or ran))
    assert asked == [(["BGLC"], date(2026, 11, 25))]
    assert p["ran"] == {"date": "2026-11-25", "text": "📅 ran Wed +176%", "title": "T"}
    assert [s["ran"] for s in p["sessions"]] == [False, False, False, False, True]


@pytest.mark.parametrize("fn", [lambda n, d: {"BGLC": {"counts": False, "date": "2026-11-25"}}, lambda n, d: 1 / 0,
                                lambda n, d: None])
def test_19_NEGATIVE_uncounted_or_raising_is_null_and_still_ok(fn):
    p = RC.build("BGLC", NOW_CLOSED, **kw(ran_fn=fn))
    assert p["state"] == "ok" and p["ran"] is None and not any(s["ran"] for s in p["sessions"])


# ── 20. refresh + words ──────────────────────────────────────────────────────────────────────────────────────────
def test_20_refresh_is_the_memo_on_every_frame_while_live_and_zero_otherwise():
    for tf in ("1m", "5m", "15m"):
        RC.reset()
        p = RC.build("AAA", NOW_LIVE, **kw(Loader(live_end=(D[25], (10, 0))), tf=tf))
        assert p["live"] is True and p["refresh_sec"] == C.RUNCHART_MEMO_SEC
        q = RC.build("AAA", NOW_CLOSED, **kw(tf=tf))
        assert q["live"] is False and q["refresh_sec"] == 0
        assert q["as_of_text"].startswith("last bar closed") and "START" in q["hint"] and "CLOSES" in q["hint"]


# ── 21. source guards ────────────────────────────────────────────────────────────────────────────────────────────
def _lock_blocks(src):
    lines = src.splitlines()
    out = []
    for i, ln in enumerate(lines):
        if ln.strip().startswith("with _LOCK"):
            ind = len(ln) - len(ln.lstrip())
            body = []
            for nx in lines[i + 1:]:
                if nx.strip() and len(nx) - len(nx.lstrip()) <= ind:
                    break
                body.append(nx)
            out.append("\n".join(body))
    return out


def test_21_source_guards():
    for bad in (".ewm(", "signals.ema(", "_masked_ema(", "find_one_and_update", "find_legs", "is_demand",
                "k3_depth_ok", "BASE_WORDS", "K4_HF_BASE_MIN", "K4_HF_BASE_MAX", "update_one", "insert_",
                "requests.", "_fetch_massive_minute", "load_intraday_range", "@"):
        assert bad not in SRC, bad
    assert "bounce" not in SRC.lower()
    for good in ("build_frame", "tile_payload", "closed_only", "resample_ohlcv", "load_intraday", "new_breaker",
                 "prev_market_day", "_get_mongo_coll", "_closes"):
        assert good in SRC, good
    blocks = _lock_blocks(SRC)
    assert len(blocks) >= 5
    for b in blocks:
        for bad in ("load_days(", "splits_in(", "payload(", ".find("):
            assert bad not in b, (bad, b)


def test_21_the_two_package_guards_still_pass_with_the_new_module():
    from tests.test_gajjala_watch_build_2026_11_15 import \
        test_ONE_engine_guard_no_second_ema_cross_or_lease_engine_in_the_package as g1
    from tests.test_gajjala_watch_run_bases_2026_11_15 import test_ONE_engine_no_second_base_count_in_the_package as g2
    g1()
    g2()


def test_21_NEGATIVE_no_comparison_names_the_ema_columns():
    import ast
    for node in ast.walk(ast.parse(SRC)):
        if isinstance(node, ast.Compare):
            assert not re.search(r"\bema_?(9|21)\b", ast.unparse(node)), ast.unparse(node)


# ── 22. golden ───────────────────────────────────────────────────────────────────────────────────────────────────
def golden_payload():
    days = {d: None for d in CLOSED_DAYS[:3]}
    days.update({D[23]: raw_day(D[23], seed=23.0), D[24]: raw_day(D[24], seed=24.0), D[25]: raw_day(D[25], seed=25.0)})
    RC.reset()
    p = RC.build("BGLC", datetime(2026, 11, 25, 20, 30, tzinfo=ET), tf="15m",
                 **kw(Loader(days), splits_fn=lambda s, i: [], cached_at_fn=lambda s, i: {}, ran_fn=lambda n, d: None))
    return json.loads(json.dumps(_scrub(p), allow_nan=False))


def test_22_golden_fixture_equals_the_engine():
    p = golden_payload()
    assert p["state"] == "ok" and [s["date"] for s in p["sessions"]] == ["2026-11-23", "2026-11-24", "2026-11-25"]
    if os.environ.get("GGRC_WRITE_GOLDEN") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(p, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    assert GOLDEN.exists(), f"no golden fixture — run: {RECIPE}"
    assert json.loads(GOLDEN.read_text(encoding="utf-8")) == p, f"the golden fixture drifted — run: {RECIPE}"


def test_22_half_day_prev_fixture_dates_are_market_days():
    from catalysts.medical.reaction import prev_market_day
    assert prev_market_day(HALF) == HALF_PREV
