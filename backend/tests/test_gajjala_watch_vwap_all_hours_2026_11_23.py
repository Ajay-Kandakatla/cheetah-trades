"""📈 Gajjala's Watch — VWAP over ALL hours (2026-11-23 evening, HIS CALL #1 answered).

Ajay, verbatim (2026-11-23 ~21:30 ET): "Why is VWAP not showing up in AH?" · then, told it was regular-hours only and
offered the full day: "Please extend them to all hours..".

Pins: `C.VWAP_SESSIONS` = `vwap.SESSION_SETS[2]` (premarket + rth + after-hours) and the served words follow; every
frame draws from the first premarket bar (04:00) through the last after-hours bar (20:00); a premarket bar counts from
04:00; an after-hours print moves the line; the half day keeps working (13:00–17:00 counted as after-hours).
NEGATIVES: yesterday's bars — its after-hours included — never reach today's line; a "closed" row (before 04:00 / from
20:00) never counts; under the rth set the same heavy prints change nothing; a junk constant still draws nothing and
never raises.
"""
from __future__ import annotations

import logging
import sys
import types
from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import vwap as VW
from daytrading import data as DD
from tests.test_gajjala_watch_build_2026_11_15 import PREV, S, at, raw_day
from tests.test_gajjala_watch_vwap_2026_11_23 import (HALF, HALF_PREV, LATE, SESSION, _db_with, _et_minutes,
                                                      close_cut, frames, stored, utc)

ALL = VW.SESSION_SETS[2]
RTH = VW.SESSION_SETS[0]
OPEN_HHMM = DD.ET_PREMARKET_OPEN.strftime("%H:%M")


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.setattr(VW, "_WARNED", set())
    monkeypatch.setitem(sys.modules, C.LEVELS_MODULE, types.SimpleNamespace(
        section=lambda *a, **k: {}, legend=lambda: [], rules_line=lambda: ""))


def _hm(t):
    return (t.hour, t.minute)


def _heavy(raw, d, hh, mm, price=30.0, mult=1000.0):
    """`raw` with ONE heavy print at hh:mm ET (price far from the day, volume × mult)."""
    out = raw.copy()
    ts = utc(d, hh, mm)
    out.loc[ts, ["open", "high", "low", "close"]] = [price, price + 0.03, price - 0.04, price]
    out.loc[ts, "volume"] = float(out.loc[ts, "volume"]) * mult
    return out


def _vals(fs, tf):
    return {t.strftime("%H:%M"): v for t, v in _et_minutes(fs, tf)}


# ── the constant + the served words ──────────────────────────────────────────────────────────────────────────────
def test_the_default_is_the_whole_extended_set_and_the_words_follow():
    assert C.VWAP_SESSIONS == ("premarket", "rth", "afterhours") == ALL
    assert VW.sessions() == ALL
    assert VW.legend_label() == f"VWAP (from {OPEN_HHMM} ET)" == "VWAP (from 04:00 ET)"
    line = VW.rules_line()
    assert VW.SPAN_WORDS[ALL] in line and "the whole extended session, premarket and after-hours included" in line
    assert VW.STOP_WORDS[True] in line and VW.STOP_WORDS[False] not in line
    assert "regular session" not in line and "premarket not counted" not in line
    assert f"from {OPEN_HHMM} ET" in line and "bounce" not in line
    assert PL.info()["vwap_text"] == line
    assert PL.legend()[2] == {"tone": C.VWAP_TONE, "label": VW.legend_label(), "title": line}


# ── 04:00 → 20:00, today only ────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("tf", [tf for tf, _r in C.FRAMES])
def test_every_frame_draws_from_the_first_premarket_bar_through_the_last_after_hours_bar(tf):
    fs = stored(frames())
    rows = _et_minutes(fs, tf)
    for t, v in rows:
        inside = (4, 0) < _hm(t) <= (20, 0)
        assert (v is not None) is inside, (tf, t)
    labels = [t for t, v in rows if v is not None]
    assert labels[-1] == rows[-1][0] and _hm(labels[-1]) >= (19, 45)            # through the last CLOSED bar (19:59:50)
    assert any(_hm(t) > (16, 0) for t in labels)                                 # after-hours bars carry a value


def test_the_minute_line_is_the_hand_sum_of_every_row_from_0400_to_2000():
    raw = raw_day(S, seed=3.0)
    got = VW.minute_vwap(raw, SESSION, sessions=C.VWAP_SESSIONS, rth_close=close_cut(S))
    typ = (raw["high"] + raw["low"] + raw["close"]) / 3
    hand = (typ * raw["volume"]).cumsum() / raw["volume"].cumsum()
    assert got.dropna().index[0] == utc(S, 4, 0) and got.dropna().index[-1] == utc(S, 19, 59)
    assert int(got.notna().sum()) == 960
    assert np.allclose(got.dropna().to_numpy(), hand.to_numpy(), rtol=0, atol=1e-12)


def test_a_premarket_bar_counts_from_0400():
    base = raw_day(S, seed=3.0)
    heavy = _heavy(base, S, 4, 0)
    a, b = _vals(stored(frames(today=base)), "1m"), _vals(stored(frames(today=heavy)), "1m")
    row = heavy.loc[utc(S, 4, 0)]
    assert b["04:01"] == round((row["high"] + row["low"] + row["close"]) / 3, C.VWAP_DP)   # the first counted bar
    for k in ("04:01", "09:31", "12:00", "16:00", "19:59"):
        assert b[k] != a[k], k                                                   # its weight rides all day


def test_NEGATIVE_under_the_rth_set_the_same_premarket_print_changes_nothing(monkeypatch):
    monkeypatch.setattr(C, "VWAP_SESSIONS", RTH)
    base = raw_day(S, seed=3.0)
    a, b = stored(frames(today=base)), stored(frames(today=_heavy(base, S, 4, 0)))
    for tf, _r in C.FRAMES:
        assert a[tf]["vwap"] == b[tf]["vwap"], tf


@pytest.mark.parametrize("tf", [tf for tf, _r in C.FRAMES])
def test_a_heavy_after_hours_print_moves_the_vwap(tf):
    base = raw_day(S, seed=3.0)
    a, b = _vals(stored(frames(today=base)), tf), _vals(stored(frames(today=_heavy(base, S, 17, 0))), tf)
    assert a.keys() == b.keys()
    before = [k for k in a if k <= "17:00"]
    after = [k for k in a if k > "17:00"]
    assert before and after
    assert all(a[k] == b[k] for k in before), tf                                # nothing before the print moves
    assert all(b[k] is not None and b[k] > a[k] for k in after), tf            # every later bar is pulled up


def test_NEGATIVE_under_the_rth_set_the_same_after_hours_print_changes_nothing(monkeypatch):
    monkeypatch.setattr(C, "VWAP_SESSIONS", RTH)
    base = raw_day(S, seed=3.0)
    a, b = stored(frames(today=base)), stored(frames(today=_heavy(base, S, 17, 0)))
    for tf, _r in C.FRAMES:
        assert a[tf]["vwap"] == b[tf]["vwap"], tf
        assert all(v is None for k, v in _vals(b, tf).items() if k > "16:00"), tf


def test_NEGATIVE_yesterdays_bars_after_hours_included_never_reach_todays_line():
    prev = raw_day(PREV)
    loud = prev.copy()
    loud["volume"] = loud["volume"] * 1000
    loud["close"] = loud["close"] + 20
    loud["high"] = loud["high"] + 20
    a, b = stored(frames(prev_raw=prev)), stored(frames(prev_raw=loud))
    for tf, _r in C.FRAMES:
        assert a[tf]["vwap"] == b[tf]["vwap"], tf
    today = raw_day(S, seed=3.0)
    both = VW.minute_vwap(pd.concat([loud, today]), SESSION, sessions=ALL, rth_close=close_cut(S))
    alone = VW.minute_vwap(today, SESSION, sessions=ALL, rth_close=close_cut(S))
    assert both.dropna().equals(alone.dropna())
    first = both.dropna().index[0]
    assert first == utc(S, 4, 0)
    row = today.loc[first]
    assert both.dropna().iloc[0] == pytest.approx((row["high"] + row["low"] + row["close"]) / 3)
    assert VW.minute_vwap(loud, SESSION, sessions=ALL, rth_close=close_cut(S)) is None       # yesterday only → nothing


def test_NEGATIVE_a_closed_row_before_0400_or_from_2000_never_counts():
    raw = raw_day(S, start=(3, 0), end=(21, 0), seed=3.0)
    raw["session"] = [DD._classify_session(ts) for ts in raw.index]           # the house tagger: "closed" outside
    closed = raw["session"] == "closed"
    assert int(closed.sum()) == 120
    raw.loc[closed, "volume"] = raw.loc[closed, "volume"] * 1000
    got = VW.minute_vwap(raw, SESSION, sessions=ALL, rth_close=close_cut(S))
    inside = VW.minute_vwap(raw[~closed], SESSION, sessions=ALL, rth_close=close_cut(S))
    assert got[closed].isna().all()
    assert got.dropna().equals(inside.dropna())
    assert got.dropna().index[0] == utc(S, 4, 0) and got.dropna().index[-1] == utc(S, 19, 59)


# ── the half day ─────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("tf", [tf for tf, _r in C.FRAMES])
def test_the_half_day_runs_past_the_1300_close_to_the_1700_label(tf):
    assert AL._closes(HALF) == (datetime(2000, 1, 1, 13).time(), datetime(2000, 1, 1, 17).time())
    now = at(HALF, 16, 59, 50)
    fs = stored(frames(d=HALF, prev=HALF_PREV, now=now, end=(17, 0)), d=HALF, now=now)
    vals = _vals(fs, tf)
    last = max(vals)
    assert vals["13:00"] is not None and last > "16:00" and vals[last] is not None      # 13:00–17:00 = after-hours
    assert all(v is not None for k, v in vals.items() if k > "04:00"), tf


def test_the_half_day_cut_only_retags_under_the_whole_set_nothing_is_dropped():
    raw = raw_day(HALF, end=(17, 0), seed=3.0)
    cut = VW.minute_vwap(raw, HALF.isoformat(), sessions=ALL, rth_close=close_cut(HALF))
    nocut = VW.minute_vwap(raw, HALF.isoformat(), sessions=ALL, rth_close=None)
    assert cut.equals(nocut) and int(cut.notna().sum()) == 780                  # 04:00–16:59, every row counted
    rth = VW.minute_vwap(raw, HALF.isoformat(), sessions=RTH, rth_close=close_cut(HALF))
    assert int(rth.notna().sum()) == 210                                        # the rth set still stops at 13:00


# ── junk under the new default ───────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("junk", [("premarket", "afterhours", "rth"), ("afterhours",), ("premarket", "afterhours"),
                                  "premarket rth afterhours", ("closed",)])
def test_NEGATIVE_a_junk_constant_still_draws_nothing_and_never_raises(monkeypatch, caplog, junk):
    good = stored(frames())                                                     # written under the all-hours default
    monkeypatch.setattr(C, "VWAP_SESSIONS", junk)
    with caplog.at_level(logging.WARNING, logger="chart_maps.gajjala_watch.vwap"):
        assert VW.sessions() is None and VW.rules_line() == "" and VW.legend_label() == ""
        fs = stored(frames())
        assert all("vwap" not in fs[tf] for tf in fs)
        out = PL.build(at(S, 19, 59, 55), db=_db_with(good))
    assert out["state"] == "ok" and out["info"]["vwap_text"] is None
    assert all(len(f["tile"]["curves"]) == 2 for f in out["rows"][0]["frames"])
    assert sum(r.name == "chart_maps.gajjala_watch.vwap" for r in caplog.records) == 1


def test_the_served_curve_runs_into_after_hours():
    fs = stored(frames())
    out = PL.build(at(S, 19, 59, 55), db=_db_with(fs))
    f = out["rows"][0]["frames"][0]
    vw = f["tile"]["curves"][2]
    assert vw["tone"] == C.VWAP_TONE
    by = dict(zip([b["t"] for b in f["tile"]["bars"]], vw["values"]))
    assert by[f"{S.isoformat()} 19:00"] is not None and by[f"{S.isoformat()} 04:01"] is not None
    assert LATE.hour == 19
