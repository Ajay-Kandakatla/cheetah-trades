"""📈 Gajjala's Watch — VWAP on the 1 / 5 / 15-minute charts (spec vwapzones rev 2 §3.2–§3.4, be-watch).

Ajay, verbatim (2026-11-23): "can you add vwap and supply demand zone in the daily time frame on the watch list please" ·
"Add vwap and supply demand too".

Pins: THE engine (`daytrading.indicators.vwap_session`) — the wrapper only chooses the rows; the three anchors of ONE
constant (HIS CALL #1); the half-day cut at the regular close [C2]; a frame value = the minute VWAP after the last
1-minute bar of its bucket; never NaN. NEGATIVES: a junk `C.VWAP_SESSIONS` draws nothing and never raises; VWAP off
computes nothing; premarket / after-hours bars carry None under the rth set (the default until 2026-11-23 pm, when he
said "Please extend them to all hours.." — tests/test_gajjala_watch_vwap_all_hours_2026_11_23.py); yesterday never
reaches the engine.
"""
from __future__ import annotations

import ast
import json
import logging
import math
import sys
import types
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala_watch import build as BLD
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import vwap as VW
from daytrading import data as DD
from daytrading.indicators import vwap_session
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_build_2026_11_15 import PREV, S, at, raw_day, stamp

ET = ZoneInfo("America/New_York")
SESSION = S.isoformat()
HALF, HALF_PREV = date(2026, 11, 27), date(2026, 11, 25)       # the half day after Thanksgiving (13:00 / 17:00)
FULL, FULL_PREV = date(2026, 11, 20), date(2026, 11, 19)
PKG = Path(VW.__file__).resolve().parent
LATE = at(S, 19, 59, 50)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.setattr(VW, "_WARNED", set())
    monkeypatch.setitem(sys.modules, C.LEVELS_MODULE, types.SimpleNamespace(
        section=lambda *a, **k: {}, legend=lambda: [], rules_line=lambda: ""))


def frames(d=S, prev=PREV, now=LATE, end=(20, 0), today=None, prev_raw=None):
    return B.build_frames("OMH", d, now, prev_raw if prev_raw is not None else raw_day(prev),
                          today if today is not None else raw_day(d, end=end, seed=3.0), rules=C.FRAMES)


def stored(fr, d=S, now=LATE):
    return BLD.tile_update("OMH", fr, d, now, "loaded")[1]["$set"]["frames"]


def utc(d, hh, mm):
    return pd.Timestamp(datetime(d.year, d.month, d.day, hh, mm), tz=ET).tz_convert("UTC").tz_localize(None)


def close_cut(d):
    return utc(d, AL._closes(d)[0].hour, AL._closes(d)[0].minute)


def _et_minutes(fs, tf):
    return [(datetime.strptime(b["t"], "%Y-%m-%d %H:%M").replace(tzinfo=ET), v)
            for b, v in zip(fs[tf]["bars"], fs[tf]["vwap"]["values"])]


# ── THE engine ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_rth_on_a_full_day_is_the_engine_on_the_same_raw():
    raw = raw_day(S, seed=3.0)
    got = VW.minute_vwap(raw, SESSION, sessions=("rth",), rth_close=close_cut(S))
    eng = vwap_session(raw, "rth")
    assert got.index.equals(raw.index)
    assert np.array_equal(got.isna().to_numpy(), eng.isna().to_numpy())
    assert np.allclose(got.dropna().to_numpy(), eng.dropna().to_numpy(), rtol=0, atol=1e-12)
    assert int(got.notna().sum()) == 390


def test_the_wrapper_holds_no_formula_and_calls_the_engine():
    src = (PKG / "vwap.py").read_text(encoding="utf-8")
    assert "vwap_session(rows.assign(session=_TAG), session=_TAG)" in src
    for bad in ("cumsum", ".ewm(", '["high"]', "typical =", "* rows"):
        assert bad not in src, bad


def test_the_first_rth_value_is_that_minutes_typical_price():
    raw = raw_day(S, seed=3.0)
    got = VW.minute_vwap(raw, SESSION).dropna()
    first = got.index[0]
    assert first == utc(S, 9, 30)
    row = raw.loc[first]
    assert got.iloc[0] == pytest.approx((row["high"] + row["low"] + row["close"]) / 3)


def test_a_doubled_prior_session_leaves_today_unchanged():
    prev = raw_day(PREV)
    big = prev.copy()
    big["volume"] = big["volume"] * 2
    big["close"] = big["close"] + 5
    a = stored(frames(prev_raw=prev))
    b = stored(frames(prev_raw=big))
    for tf, _r in C.FRAMES:
        assert a[tf]["vwap"] == b[tf]["vwap"]
    two = pd.concat([prev, raw_day(S, seed=3.0)])
    assert VW.minute_vwap(two, SESSION).dropna().equals(VW.minute_vwap(raw_day(S, seed=3.0), SESSION).dropna())


# ── frame values ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_frame_value_is_the_minute_vwap_after_the_last_minute_of_its_bucket():
    raw = raw_day(S, seed=3.0)
    fr = frames(today=raw)
    fs = stored(fr)
    mv = VW.minute_vwap(raw, SESSION, sessions=C.VWAP_SESSIONS, rth_close=close_cut(S))   # 2026-11-23 pm: the default
    for tf, rule in C.FRAMES:
        assert len(fs[tf]["vwap"]["values"]) == len(fs[tf]["bars"])
        step = pd.Timedelta(rule)
        for b, v in zip(fs[tf]["bars"], fs[tf]["vwap"]["values"]):
            lab = pd.Timestamp(datetime.strptime(b["t"], "%Y-%m-%d %H:%M"), tz=ET).tz_convert("UTC").tz_localize(None)
            m = mv.get(lab - pd.Timedelta("1min"))
            want = None if m is None or m != m else round(float(m), C.VWAP_DP)
            assert v == want, (tf, b["t"])
    v15 = dict(zip([b["t"] for b in fs["15m"]["bars"]], fs["15m"]["vwap"]["values"]))
    assert v15[stamp(S, 10, 0)] == round(float(mv[utc(S, 9, 59)]), C.VWAP_DP)


@pytest.mark.parametrize("tf", [tf for tf, _r in C.FRAMES])
def test_NEGATIVE_premarket_and_after_hours_bars_carry_none_under_the_rth_set(tf, monkeypatch):
    monkeypatch.setattr(C, "VWAP_SESSIONS", VW.SESSION_SETS[0])        # 2026-11-23 pm: no longer the default (all hours)
    fs = stored(frames())
    for t, v in _et_minutes(fs, tf):
        rth = (t.hour, t.minute) > (9, 30) and (t.hour, t.minute) <= (16, 0)
        assert (v is not None) is rth, (tf, t)


def test_frame_values_never_nan_and_none_without_input():
    labels = pd.DatetimeIndex([utc(S, 9, 31), utc(S, 9, 32)])
    assert VW.frame_values(None, labels, "1min") == [None, None]
    nan = pd.Series([float("nan"), float("inf")], index=[utc(S, 9, 30), utc(S, 9, 31)])
    assert VW.frame_values(nan, labels, "1min") == [None, None]


@pytest.mark.parametrize("drop", ["volume", "session"])
def test_NEGATIVE_no_volume_or_session_column_no_vwap_key(drop):
    raw = raw_day(S, end=(11, 0), seed=3.0).drop(columns=[drop])
    assert VW.minute_vwap(raw, SESSION) is None
    if drop == "session":
        fs = stored(frames(today=raw, now=at(S, 11, 0, 30)), now=at(S, 11, 0, 30))
        assert all("vwap" not in fs[tf] for tf in fs)


def test_NEGATIVE_no_bars_or_all_zero_volume_or_another_day_no_vwap(monkeypatch):
    assert VW.minute_vwap(None, SESSION) is None
    assert VW.minute_vwap(raw_day(S).iloc[:0], SESSION) is None
    assert VW.minute_vwap(raw_day(PREV), SESSION) is None                       # yesterday's rows only
    z = raw_day(S, end=(11, 0))
    z["volume"] = 0.0
    assert VW.minute_vwap(z, SESSION) is None
    pre = raw_day(S, end=(9, 0))                                                 # premarket only, the rth set
    assert VW.minute_vwap(pre, SESSION) is None
    monkeypatch.setattr(C, "VWAP_SESSIONS", VW.SESSION_SETS[0])                 # 2026-11-23 pm: no longer the default
    fs = stored(frames(today=pre, now=at(S, 9, 0, 30)), now=at(S, 9, 0, 30))
    assert all("vwap" not in fs[tf] for tf in fs)


def test_vwap_is_computed_once_per_name_per_build(monkeypatch):
    calls = []
    real = VW.minute_vwap
    monkeypatch.setattr(VW, "minute_vwap", lambda *a, **k: calls.append(1) or real(*a, **k))
    stored(frames())
    assert calls == [1]


def test_NEGATIVE_vwap_off_computes_nothing_and_serves_no_curve(monkeypatch):
    fr = frames()
    with_vw = stored(fr)
    monkeypatch.setattr(C, "VWAP_ON", False)
    monkeypatch.setattr(VW, "minute_vwap", lambda *a, **k: pytest.fail("off → nothing computed"))
    off = stored(fr)
    assert all("vwap" not in off[tf] for tf in off)
    for tf in off:
        assert {k: v for k, v in with_vw[tf].items() if k != "vwap"} == off[tf]   # byte-equal otherwise
    blk = PL.frame_block("OMH", "1m", with_vw["1m"], None)
    assert [c["tone"] for c in blk["tile"]["curves"]] == ["ema9", "ema21"]
    assert VW.rules_line() == "" and PL.info()["vwap_text"] is None
    assert [e["tone"] for e in PL.legend()] == ["ema9", "ema21"]


def test_a_tile_without_vw_is_byte_identical_to_before():
    fr = frames()
    end = BLD.axis_end(S, [fr.frame("1m").t[i] for i in fr.frame("1m").today])
    for tf, _r in C.FRAMES:
        assert "vwap" not in BLD.tile(fr, tf, end)
        assert BLD.tile(fr, tf, end, vw=None) == BLD.tile(fr, tf, end)


def test_a_raising_wrapper_is_fenced_the_tile_still_writes(monkeypatch):
    monkeypatch.setattr(VW, "minute_vwap", lambda *a, **k: 1 / 0)
    fs = stored(frames())
    assert list(fs) == [tf for tf, _r in C.FRAMES] and all("vwap" not in fs[tf] for tf in fs)
    monkeypatch.setattr(VW, "frame_values", lambda *a, **k: 1 / 0)
    assert BLD.vwap_keys(frames().frame("1m"), "1m", pd.Series([1.0])) == {}


# ── serve ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _db_with(doc_frames):
    db = {C.COLL_LIST: FakeColl([{"_id": C.LIST_DOC_ID, "symbols": ["OMH"]}]), C.COLL_TILES: FakeColl(),
          C.COLL_ALERTS: FakeColl(), C.COLL_STATE: FakeColl()}
    db[C.COLL_TILES].docs["OMH"] = {"_id": "OMH", "symbol": "OMH", "status": "loaded", "session": SESSION,
                                    "at": datetime(2026, 11, 14, 0, 59), "loaded_at": datetime(2026, 11, 14, 0, 59),
                                    "frames": doc_frames}
    return db


def test_the_served_curve_is_the_third_and_never_nan():
    fs = stored(frames())
    fs["1m"]["vwap"]["values"][400] = float("nan")                              # a NaN injected into the stored doc
    out = PL.build(at(S, 19, 59, 55), db=_db_with(fs))
    r = out["rows"][0]
    for f in r["frames"]:
        tones = [c["tone"] for c in f["tile"]["curves"]]
        assert tones == ["ema9", "ema21", C.VWAP_TONE]
        vw = f["tile"]["curves"][2]
        assert vw["label"] == C.VWAP_LABEL and len(vw["values"]) == len(f["tile"]["bars"])
    assert r["frames"][0]["tile"]["curves"][2]["values"][400] is None
    json.dumps(out, default=str, allow_nan=False)


@pytest.mark.parametrize("bad", ["ragged", "all_none", "junk", "missing"])
def test_NEGATIVE_an_unusable_stored_vwap_serves_no_curve(bad):
    fs = stored(frames())
    if bad == "ragged":
        fs["5m"]["vwap"]["values"] = fs["5m"]["vwap"]["values"][:-1]
    elif bad == "all_none":
        fs["5m"]["vwap"]["values"] = [None] * len(fs["5m"]["bars"])
    elif bad == "junk":
        fs["5m"]["vwap"] = "junk"
    else:
        del fs["5m"]["vwap"]
    blk = PL.frame_block("OMH", "5m", fs["5m"], None)
    assert [c["tone"] for c in blk["tile"]["curves"]] == ["ema9", "ema21"]


def test_curve_by_stamp_and_align():
    fr = {"bars": [{"t": "a"}, {"t": "b"}, {"t": "c"}], "vwap": {"values": [1.0, None, float("nan")]}}
    assert VW.curve_values(fr, 3) == [1.0, None, None] and VW.curve_values(fr, 2) is None
    assert VW.by_stamp(fr) == {"a": 1.0}
    assert VW.align({"a": 1.0}, [{"t": "z"}, {"t": "a"}]) == [None, 1.0]
    assert VW.align({"a": 1.0}, [{"t": "z"}]) is None and VW.align({}, [{"t": "a"}]) is None
    assert VW.by_stamp({"bars": [{"t": "a"}], "vwap": {"values": [1.0, 2.0]}}) == {}       # ragged → nothing
    assert VW.curve_values({"vwap": {"values": [True]}}, 1) is None                         # a bool is not a price


def test_legend_two_emas_byte_equal_then_vwap_with_its_sentence():
    lg = PL.legend()
    assert lg[:2] == [{"tone": "ema9", "label": f"{GC.EMA_FAST} EMA"}, {"tone": "ema21", "label": f"{GC.EMA_SLOW} EMA"}]
    assert lg[2] == {"tone": C.VWAP_TONE, "label": "VWAP (from 04:00 ET)", "title": VW.rules_line()}   # all hours (11-23 pm)
    assert lg[2]["label"] == VW.legend_label()
    assert PL.info()["vwap_text"] == VW.rules_line()


# ── [C2] the half day ────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("tf", [tf for tf, _r in C.FRAMES])
def test_C2_on_the_half_day_every_frame_stops_at_the_1300_close_under_the_rth_set(tf, monkeypatch):
    monkeypatch.setattr(C, "VWAP_SESSIONS", VW.SESSION_SETS[0])        # 2026-11-23 pm: no longer the default (all hours)
    assert AL._closes(HALF) == (datetime(2000, 1, 1, 13).time(), datetime(2000, 1, 1, 17).time())
    now = at(HALF, 16, 59, 50)
    fs = stored(frames(d=HALF, prev=HALF_PREV, now=now, end=(17, 0)), d=HALF, now=now)
    vals = dict((t.strftime("%H:%M"), v) for t, v in _et_minutes(fs, tf))
    assert vals["13:00"] is not None
    late = [k for k, v in vals.items() if k > "13:00" and v is not None]
    assert late == []
    assert any(k > "13:00" for k in vals)                                       # bars after the close exist


@pytest.mark.parametrize("tf", [tf for tf, _r in C.FRAMES])
def test_C2_the_same_raw_on_a_full_day_runs_to_the_1600_label_under_the_rth_set(tf, monkeypatch):
    monkeypatch.setattr(C, "VWAP_SESSIONS", VW.SESSION_SETS[0])        # 2026-11-23 pm: no longer the default (all hours)
    fs = stored(frames(d=FULL, prev=FULL_PREV, now=at(FULL, 19, 59, 50)), d=FULL, now=at(FULL, 19, 59, 50))
    vals = dict((t.strftime("%H:%M"), v) for t, v in _et_minutes(fs, tf))
    assert vals["16:00"] is not None and vals["13:15"] is not None
    assert all(v is None for k, v in vals.items() if k > "16:00")


def test_C2_NEGATIVE_without_the_cut_the_engine_runs_past_1300_the_cut_is_the_wrappers():
    raw = raw_day(HALF, seed=3.0)
    cut = VW.minute_vwap(raw, HALF.isoformat(), rth_close=close_cut(HALF))
    nocut = VW.minute_vwap(raw, HALF.isoformat(), rth_close=None)
    after = utc(HALF, 13, 0)
    assert nocut[nocut.index >= after].notna().sum() == 180                     # 13:00–15:59 still tagged rth
    assert cut[cut.index >= after].notna().sum() == 0 and int(cut.notna().sum()) == 210
    both = cut.dropna().index
    assert np.allclose(cut[both].to_numpy(), nocut[both].to_numpy())
    assert "runs through after-hours" in VW.rules_line()                       # 2026-11-23 pm: the all-hours default
    aware = VW.minute_vwap(raw, HALF.isoformat(), rth_close=pd.Timestamp(datetime(2026, 11, 27, 13, 0), tz=ET))
    assert aware.equals(cut)                                                    # an aware close is converted


def test_C2_build_hands_the_wrapper_the_session_regular_close(monkeypatch):
    got = []
    real = VW.minute_vwap
    monkeypatch.setattr(VW, "minute_vwap", lambda *a, **k: got.append(k) or real(*a, **k))
    now = at(HALF, 16, 59, 50)
    stored(frames(d=HALF, prev=HALF_PREV, now=now, end=(17, 0)), d=HALF, now=now)
    assert got[0]["rth_close"] == utc(HALF, 13, 0)
    assert got[0]["sessions"] == C.VWAP_SESSIONS == VW.SESSION_SETS[2]          # 2026-11-23 pm: all hours


# ── [O1] the three anchors of ONE constant ───────────────────────────────────────────────────────────────────────
def test_O1_the_session_sets_and_the_default_is_the_engines_own_default():
    import inspect
    assert VW.SESSION_SETS == (("rth",), ("premarket", "rth"), ("premarket", "rth", "afterhours"))
    # 2026-11-23 pm — HIS CALL #1 answered, Ajay verbatim: "Please extend them to all hours..". Was ("rth",) = the
    # engine's own default argument; that identity is no longer the intent — the whole extended set is.
    assert C.VWAP_SESSIONS == ("premarket", "rth", "afterhours") == VW.SESSION_SETS[2]
    assert VW.sessions() == VW.SESSION_SETS[2]
    assert (inspect.signature(vwap_session).parameters["session"].default,) == VW.SESSION_SETS[0]   # the engine untouched


def test_O1_premarket_and_rth_is_the_hand_sum_from_the_first_premarket_row_and_stops_at_the_close():
    raw = raw_day(S, seed=3.0)
    got = VW.minute_vwap(raw, SESSION, sessions=VW.SESSION_SETS[1], rth_close=close_cut(S))
    m = raw.index < close_cut(S)
    typ = (raw["high"] + raw["low"] + raw["close"]) / 3
    hand = (typ[m] * raw["volume"][m]).cumsum() / raw["volume"][m].cumsum()
    assert got.dropna().index[0] == utc(S, 4, 0) and got.dropna().index[-1] == utc(S, 15, 59)
    assert np.allclose(got.dropna().to_numpy(), hand.to_numpy())
    assert int(got.notna().sum()) == 720


def test_O1_the_whole_day_set_reaches_the_last_after_hours_row():
    raw = raw_day(S, seed=3.0)
    got = VW.minute_vwap(raw, SESSION, sessions=VW.SESSION_SETS[2], rth_close=close_cut(S))
    assert got.dropna().index[-1] == utc(S, 19, 59) and int(got.notna().sum()) == 960


@pytest.mark.parametrize("sets,open_t,stop", [(("rth",), DD.ET_RTH_OPEN, "stops at the regular close"),
                                              (("premarket", "rth"), DD.ET_PREMARKET_OPEN, "stops at the regular close"),
                                              (("premarket", "rth", "afterhours"), DD.ET_PREMARKET_OPEN,
                                               "runs through after-hours")])
def test_O1_each_anchor_draws_from_its_open_and_the_words_follow(monkeypatch, sets, open_t, stop):
    monkeypatch.setattr(C, "VWAP_SESSIONS", sets)
    hhmm = open_t.strftime("%H:%M")
    assert VW.legend_label() == f"VWAP (from {hhmm} ET)"
    line = VW.rules_line()
    assert f"from {hhmm} ET" in line and stop in line and VW.SPAN_WORDS[sets] in line
    assert C.TAB_LABEL in line and "closed 1-min bars" in line and "UNMEASURED" in line and "bounce" not in line
    fs = stored(frames())
    first = next(t for t, v in _et_minutes(fs, "1m") if v is not None)
    assert first.strftime("%H:%M") == (datetime.combine(S, open_t) + pd.Timedelta("1min")).strftime("%H:%M")


def test_O1_source_guard_no_digit_typed_in_the_vwap_words():
    tree = ast.parse((PKG / "vwap.py").read_text(encoding="utf-8"))
    fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name in ("rules_line", "legend_label", "_open_words"):
        for node in ast.walk(fns[name]):
            if isinstance(node, ast.Constant):
                assert not any(ch.isdigit() for ch in str(node.value)), (name, node.value)
    words = [VW.LEGEND_TEXT, VW.RULES_TEXT, *VW.SPAN_WORDS.values(), *VW.STOP_WORDS.values()]
    assert not any(ch.isdigit() for w in words for ch in w)
    for name in ("FRAME_PENDING_TEXT", "FRAME_NO_BARS_TEXT"):
        v = getattr(PL, name)
        for w in (v.values() if isinstance(v, dict) else [v]):
            assert not any(ch.isdigit() for ch in w.replace("{minutes}", "")), w


@pytest.mark.parametrize("junk", [("closed",), (), "rth", None, ("rth", "premarket"), 7])
def test_O1_NEGATIVE_a_junk_session_constant_draws_nothing_warns_once_never_raises(monkeypatch, caplog, junk):
    monkeypatch.setattr(C, "VWAP_SESSIONS", junk)
    with caplog.at_level(logging.WARNING, logger="chart_maps.gajjala_watch.vwap"):
        assert VW.sessions() is None and VW.rules_line() == "" and VW.legend_label() == ""
        fs = stored(frames())
        assert all("vwap" not in fs[tf] for tf in fs)
        good = stored(frames())
        out = PL.build(at(S, 19, 59, 55), db=_db_with(good))
    assert out["state"] == "ok"
    assert [e["tone"] for e in out["legend"]] == ["ema9", "ema21"]
    assert out["info"]["vwap_text"] is None
    assert all(len(f["tile"]["curves"]) == 2 for f in out["rows"][0]["frames"])
    assert sum(r.name == "chart_maps.gajjala_watch.vwap" for r in caplog.records) == 1


def test_NEGATIVE_junk_constant_with_a_stored_vwap_serves_no_curve(monkeypatch):
    fs = stored(frames())                                       # written while the constant was good
    monkeypatch.setattr(C, "VWAP_SESSIONS", ("closed",))
    out = PL.build(at(S, 19, 59, 55), db=_db_with(fs))
    assert all([c["tone"] for c in f["tile"]["curves"]] == ["ema9", "ema21"] for f in out["rows"][0]["frames"])
