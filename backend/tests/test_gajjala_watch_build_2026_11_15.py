"""👀 Gajjala's Watch — the engine edits (bars.py: 3m rule, `rules`, `per_name`), the tiles (04:00 axis, cross marks, K5)
and the tile writes (spec 2026-11-15 §3.5.1 / §3.5.2, WP-B).

Ajay, verbatim (2026-11-15): "When I add a ticker I need 1 min 3 min and 5 min charts... Not the SEPA and I need clear
distinction or may be a brighter and thicker 21 EMA and 9 EMA" · "Any chart I view make sure you are showing me from 4 AM
for historical behaviour and also the right side with gaps to see where it might go".

GG outputs are pinned BYTE-EQUAL to the pre-edit engine (sha256 digests computed on this fixture BEFORE bars.py was
edited). NEGATIVES: the still-printing bucket, a straddling bucket, a failed read wiping the last good charts, a raising
write, a second EMA / cross / lease engine inside the package.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import bars as B
from chart_maps.gajjala import break_watch as BW
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as DT
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import build as BLD
from chart_maps.gajjala_watch import constants as C
from tests.test_gajjala_store import FakeColl

ET = ZoneInfo("America/New_York")
PREV = date(2026, 11, 12)                                       # Thursday
S = date(2026, 11, 13)                                          # Friday, NYSE open
HALF = date(2026, 11, 27)                                       # the half day after Thanksgiving
HALF_PREV = date(2026, 11, 25)
PKG = Path(BLD.__file__).resolve().parent

# the pre-edit engine's output on `raw_day` (computed 2026-11-15 before bars.py was touched)
DIGEST_GG5 = "97dd37e0bc93d0b046073ea44b4c382c0ca6e4ba8572348d0e1924900fc02c1d"
DIGEST_GG1 = "44338a3753e9bcf3c24f5306051f7d021a36be1ad4416d3dd91535f7a4a16787"


def at(d, hh, mm, ss=0):
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=ET)


def stamp(d, hh, mm):
    return f"{d.isoformat()} {hh:02d}:{mm:02d}"


def raw_day(d, start=(4, 0), end=(20, 0), seed=0.0, price=None, volume=None):
    """Deterministic 1-minute bars [start, end) ET, UTC-naive index (the minute loader's shape)."""
    t0 = pd.Timestamp(datetime(d.year, d.month, d.day, *start), tz=ET)
    t1 = pd.Timestamp(datetime(d.year, d.month, d.day, *end), tz=ET)
    idx = pd.date_range(t0, t1, freq="1min", inclusive="left")
    rows = []
    for i, ts in enumerate(idx):
        m = ts.hour * 60 + ts.minute
        p = (price(ts) if price is not None else
             round(10.0 + 0.8 * math.sin((i + seed) / 37.0) + 0.3 * math.sin((i + seed) / 7.0), 4))
        rows.append({"open": p - 0.01, "high": p + 0.03, "low": p - 0.04, "close": p,
                     "volume": float(volume if volume is not None else 1000 + (i * 37) % 900),
                     "session": "premarket" if m < 570 else ("rth" if m < 960 else "afterhours")})
    return pd.DataFrame(rows, index=idx.tz_convert("UTC").tz_localize(None))


def digest(fr) -> str:
    if fr is None:
        return "none"
    out = {"keys": list(fr.by), "primary": fr.primary, "slow": fr.slow, "session": fr.session}
    for tf, f in fr.by.items():
        out[tf] = {"o": f.o, "h": f.h, "l": f.l, "c": f.c, "v": f.v, "t": f.t, "s": f.session, "e9": f.ema9,
                   "e21": f.ema21, "today": [f.today.start, f.today.stop], "frame": f.frame,
                   "minutes": {k: [list(x) for x in v] for k, v in sorted(f.minutes.items())}}
    return hashlib.sha256(json.dumps(out, sort_keys=True, default=str).encode()).hexdigest()


NOW = at(S, 10, 40, 10)


def fixture_raws():
    return raw_day(PREV), raw_day(S, end=(10, 41), seed=3.0)


def loader(today=None, prev=None, fail_today=False):
    def load(sym, day, force=False, include_premarket=True, include_afterhours=False):
        if sym == "NONE":
            return None
        if sym == "NOTODAY":
            return None if day == S else raw_day(PREV)
        if day == S:
            if fail_today:
                raise RuntimeError("boom")
            return today if today is not None else raw_day(S, end=(10, 41), seed=3.0)
        return prev if prev is not None else raw_day(PREV)
    return load


def watch_frames(now=NOW, prev=None, today=None, d=S):
    p, t = fixture_raws()
    return B.build_frames("OMH", d, now, prev if prev is not None else p, today if today is not None else t,
                          rules=C.FRAMES)


# ── engine (bars.py) ─────────────────────────────────────────────────────────────────────────────────────────────
def test_rule_of_gains_3m_and_nothing_else_moves():
    assert B.RULE_OF == {"1m": "1min", "5m": "5min", "15m": "15min", "3m": "3min"}
    assert B.RULES == {"5m": "5min", "15m": "15min"}
    for v in V.VARIANTS:
        assert "3m" not in dict(v.rules)


def test_build_frames_without_rules_is_byte_equal_to_before_for_gg5_and_gg1():
    p, t = fixture_raws()
    assert digest(B.build_frames("OMH", S, NOW, p, t)) == DIGEST_GG5
    assert digest(B.build_frames("OMH", S, NOW, p, t, rules=None)) == DIGEST_GG5
    assert digest(B.build_frames("OMH", S, NOW, p, t, variant=V.GG1)) == DIGEST_GG1
    assert digest(B.build_frames("OMH", S, NOW, p, t, variant=V.GG1, rules=None)) == DIGEST_GG1


@pytest.mark.parametrize("variant,want", [(None, DIGEST_GG5), (V.GG1, DIGEST_GG1)])
def test_frames_for_without_the_new_keywords_is_byte_equal_and_stats_unchanged(variant, want):
    st0, st1, per = {}, {}, {}
    a = B.frames_for(["OMH", "NONE"], S, NOW, load_day=loader(), workers=1, stats=st0, variant=variant)
    b = B.frames_for(["OMH", "NONE"], S, NOW, load_day=loader(), workers=1, stats=st1, variant=variant,
                     per_name=per)
    assert digest(a["OMH"]) == digest(b["OMH"]) == want
    assert st0 == st1 == {"loaded": 1, "no_bars": 1, "failed": 0, "over_budget": 0}
    assert sorted(a) == sorted(b) == ["OMH"]


# RE-PINNED 2026-11-23 (Ajay: "Can you remove 3 mins just add 15 mins instead.. So 1 min, 5 and 15 accross board"): the
# watch's frames are 1m / 5m / 15m — primary 1m, slow 15m; the 3m pins below now pin the 15m frame.
def test_rules_build_the_three_watch_frames_primary_1m_slow_15m():
    fr = watch_frames()
    assert list(fr.by) == ["1m", "5m", "15m"] and fr.primary == "1m" and fr.slow == "15m"
    assert [fr.frame(tf).frame for tf in ("1m", "5m", "15m")] == ["1m", "5m", "15m"]
    st = {}
    out = B.frames_for(["OMH"], S, NOW, load_day=loader(), workers=1, stats=st, rules=C.FRAMES)
    assert list(out["OMH"].by) == ["1m", "5m", "15m"] and st["loaded"] == 1


def test_15m_ohlcv_is_the_hand_aggregation_of_its_minutes():
    p, t = fixture_raws()
    F = watch_frames().frame("15m")
    et = t.copy()
    et.index = et.index.tz_localize("UTC").tz_convert(ET)
    for hh, mm in ((9, 45), (10, 0), (10, 15)):
        lab = pd.Timestamp(datetime(S.year, S.month, S.day, hh, mm), tz=ET)
        mins = et[(et.index >= lab - pd.Timedelta("15min")) & (et.index < lab)]
        assert len(mins) == 15
        k = F.t.index(stamp(S, hh, mm))
        assert F.o[k] == pytest.approx(float(mins["open"].iloc[0]))
        assert F.h[k] == pytest.approx(float(mins["high"].max()))
        assert F.l[k] == pytest.approx(float(mins["low"].min()))
        assert F.c[k] == pytest.approx(float(mins["close"].iloc[-1]))
        assert F.v[k] == pytest.approx(float(mins["volume"].sum()))


def test_NEGATIVE_the_still_printing_15m_bucket_is_absent():
    F = watch_frames(now=at(S, 9, 40, 10)).frame("15m")
    assert F.frame == "15m" and stamp(S, 9, 30) in F.t and F.t[-1] == stamp(S, 9, 30)
    assert stamp(S, 9, 45) not in F.t


@pytest.mark.parametrize("d,prev", [(S, PREV), (date(2026, 7, 14), date(2026, 7, 13))])   # EST and EDT
def test_NEGATIVE_no_15m_bucket_straddles_0930_or_the_close(d, prev):
    fr = B.build_frames("OMH", d, at(d, 19, 0), raw_day(prev), raw_day(d, end=(18, 0)), rules=C.FRAMES)
    F = fr.frame("15m")
    assert F.frame == "15m"
    for i in F.today:
        lab = datetime.strptime(F.t[i], "%Y-%m-%d %H:%M").replace(tzinfo=ET)
        start = lab - pd.Timedelta("15min")
        for edge in (at(d, 9, 30), at(d, 16, 0)):
            assert not (start < edge < lab), F.t[i]
    assert stamp(d, 9, 30) in F.t and stamp(d, 9, 45) in F.t and stamp(d, 16, 0) in F.t


def test_per_name_reports_no_prints_vs_no_bars_and_loaded():
    per = {}
    B.frames_for(["OMH", "NOTODAY", "NONE"], S, NOW, load_day=loader(), workers=1, per_name=per, rules=C.FRAMES)
    assert per == {"OMH": {"status": "loaded", "prev": True}, "NOTODAY": {"status": "no_bars", "prev": True},
                   "NONE": {"status": "no_bars", "prev": False}}
    per = {}
    B.frames_for(["OMH"], S, NOW, load_day=loader(fail_today=True), workers=1, per_name=per)
    assert per == {"OMH": {"status": "failed", "prev": True}}
    per = {}
    B.frames_for(["OMH"], S, NOW, load_day=loader(), workers=1, per_name=per, budget_sec=-1)
    assert per == {"OMH": {"status": "over_budget", "prev": False}}


def test_NEGATIVE_per_name_never_changes_stats_and_none_records_nothing():
    st0, st1 = {}, {}
    B.frames_for(["OMH", "NOTODAY", "NONE"], S, NOW, load_day=loader(), workers=1, stats=st0)
    B.frames_for(["OMH", "NOTODAY", "NONE"], S, NOW, load_day=loader(), workers=1, stats=st1, per_name={})
    assert st0 == st1 and set(st0) == {"loaded", "no_bars", "failed", "over_budget"}
    junk = []
    B.frames_for(["OMH"], S, NOW, load_day=loader(), workers=1, per_name=junk)   # not a dict → nothing recorded
    assert junk == []


def test_NEGATIVE_3m_never_becomes_a_push_frame():
    assert "3m" not in AL.FRAME_MINUTES
    assert BW._frame({"frame": "3m"}) is None


# ── status_of ────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("entry,want", [
    ({"status": "loaded", "prev": True}, "loaded"),
    ({"status": "no_bars", "prev": True}, "no_prints"),
    ({"status": "no_bars", "prev": False}, "no_bars"),
    ({"status": "failed", "prev": True}, "failed"),
    ({"status": "over_budget", "prev": False}, "over_budget"),
    ({}, "failed"), (None, "failed"), ({"status": "junk"}, "failed"),
])
def test_status_of(entry, want):
    assert BLD.status_of(entry) == want


# ── tiles ────────────────────────────────────────────────────────────────────────────────────────────────────────
def frames_of(upd) -> dict:
    return upd[1]["$set"]["frames"]


def test_tile_bars_start_at_04_and_the_axis_maps_the_close_stamp():
    fr = watch_frames()
    fs = frames_of(BLD.tile_update("OMH", fr, S, NOW, "loaded"))
    assert list(fs) == ["1m", "5m", "15m"]                                       # RE-PINNED 2026-11-23
    assert [fs[tf]["bars"][0]["t"] for tf in fs] == [stamp(S, 4, 1), stamp(S, 4, 5), stamp(S, 4, 15)]
    one = fs["1m"]
    k = [b["t"] for b in one["bars"]].index(stamp(S, 9, 31))
    assert one["axis"]["x"][k] == 330 and one["axis"]["x"][0] == 0
    assert one["axis"]["from_et"] == "04:00" and one["axis"]["to_et"] == "16:00"
    assert one["axis"]["slots"] == 720 and fs["5m"]["axis"]["slots"] == 144 and fs["15m"]["axis"]["slots"] == 48
    assert one["axis"]["shade"] == [{"from_slot": 0, "to_slot": 330, "kind": "pre"}]
    assert fs["5m"]["axis"]["shade"][0]["to_slot"] == 66 and fs["15m"]["axis"]["shade"][0]["to_slot"] == 22
    assert one["axis"]["ticks"][0] == {"slot": 0, "label": "04:00"} and one["axis"]["ticks"][-1]["label"] == "16:00"
    assert len(one["axis"]["x"]) == len(one["bars"]) and one["axis"]["x"][-1] < one["axis"]["slots"]   # space to the close
    assert one["label"] == "1-min" and one["as_of_bar_t"] == stamp(S, 10, 39)


def test_axis_ends_at_the_half_day_close_and_the_extended_close_once_a_bar_prints_after_it():
    fr = B.build_frames("OMH", HALF, at(HALF, 12, 0), raw_day(HALF_PREV), raw_day(HALF, end=(12, 0)),
                        rules=C.FRAMES)
    fs = frames_of(BLD.tile_update("OMH", fr, HALF, at(HALF, 12, 0), "loaded"))
    assert {fs[tf]["axis"]["to_et"] for tf in fs} == {"13:00"}
    fr = B.build_frames("OMH", HALF, at(HALF, 14, 0), raw_day(HALF_PREV), raw_day(HALF, end=(13, 30)),
                        rules=C.FRAMES)
    fs = frames_of(BLD.tile_update("OMH", fr, HALF, at(HALF, 14, 0), "loaded"))
    assert {fs[tf]["axis"]["to_et"] for tf in fs} == {"17:00"}


def test_C1_7_one_axis_end_per_tile_from_the_1m_frame():
    now = at(S, 16, 1, 45)                                      # 1m 16:01 closed; no 5m / 15m bar past 16:00 yet
    fr = B.build_frames("OMH", S, now, raw_day(PREV), raw_day(S, end=(16, 2)), rules=C.FRAMES)
    assert fr.frame("1m").t[-1] == stamp(S, 16, 1)
    assert fr.frame("15m").t[-1] <= stamp(S, 16, 0) and fr.frame("5m").t[-1] <= stamp(S, 16, 0)
    fs = frames_of(BLD.tile_update("OMH", fr, S, now, "loaded"))
    assert [fs[tf]["axis"]["to_et"] for tf in fs] == ["20:00", "20:00", "20:00"]
    sh = fs["1m"]["axis"]["shade"]
    assert sh[1] == {"from_slot": 720, "to_slot": 960, "kind": "ah"}


def test_NEGATIVE_axis_end_regular_close_when_the_last_bar_closes_at_it():
    assert BLD.axis_end(S, [{"t": stamp(S, 16, 0)}]) == AL._closes(S)[0]
    assert BLD.axis_end(S, [{"t": stamp(S, 16, 1)}]) == AL._closes(S)[1]
    assert BLD.axis_end(S, []) == AL._closes(S)[0]


def cross_frames():
    """Down all morning, then the 10:05 minute jumps: the 1m 9 EMA crosses above the 21 EMA on the bar stamped 10:06."""
    def price(ts):
        m = ts.hour * 60 + ts.minute
        return 14.0 if m >= 10 * 60 + 5 else 10.0 - 0.002 * (m - 4 * 60)
    return B.build_frames("OMH", S, at(S, 10, 6, 30), raw_day(PREV, price=lambda ts: 10.0),
                          raw_day(S, end=(10, 7), price=price), rules=C.FRAMES)


def test_markers_are_the_cards_cross_marks_on_served_bars_only():
    fr = cross_frames()
    fs = frames_of(BLD.tile_update("OMH", fr, S, at(S, 10, 6, 30), "loaded"))
    one = fs["1m"]
    stamps = {b["t"] for b in one["bars"]}
    assert one["markers"] and {m["kind"] for m in one["markers"]} <= {"ema_cross_up", "ema_cross_dn"}
    assert all(m["date"] in stamps for m in one["markers"])
    assert one["markers"][-1]["date"] == stamp(S, 10, 6) and one["markers"][-1]["kind"] == "ema_cross_up"
    assert one["ema_cross"]["dir"] == "up" and "_marks" not in one["ema_cross"]
    assert [c["t"] for c in one["ema_cross"]["crosses"]] == [m["date"] for m in one["markers"]]


def test_NEGATIVE_no_cross_no_block_and_no_marker():
    flat = B.build_frames("OMH", S, NOW, raw_day(PREV, price=lambda ts: 10.0),
                          raw_day(S, end=(10, 41), price=lambda ts: 10.0), rules=C.FRAMES)
    fs = frames_of(BLD.tile_update("OMH", flat, S, NOW, "loaded"))
    for tf in fs:
        assert fs[tf]["ema_cross"] is None and fs[tf]["markers"] == []


def test_uptrend_is_k5_at_the_latest_bar_and_the_short_words():
    fr = watch_frames()
    fs = frames_of(BLD.tile_update("OMH", fr, S, NOW, "loaded"))
    for tf in fs:
        F = fr.frame(tf)
        ok = DT.uptrend(F, len(F) - 1)
        assert fs[tf]["uptrend"] == {"ok": ok, "short": BLD.UPTREND_SHORT[ok]}
    assert BLD.UPTREND_SHORT == {True: "K5 ✓", False: "K5 ✗", None: "K5 —"}
    assert BLD.k5(fr.frame("1m"), -1) is None and BLD.k5(None, 3) is None and BLD.k5(fr.frame("1m"), 10 ** 6) is None


def test_uptrend_rule_is_byte_equal_to_the_k5_criterion():
    src = Path(DT.__file__).read_text(encoding="utf-8")
    need = None
    for n in ast.walk(ast.parse(src)):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "criterion" and n.args
                and isinstance(n.args[0], ast.Constant) and n.args[0].value == "k5_uptrend"):
            need = eval(compile(ast.Expression(n.args[4]), "k5", "eval"), {"GC": GC})   # noqa: S307
    assert need == f"9 EMA above the 21 EMA and both higher than {GC.K5_SLOPE_BARS} bars ago"
    assert BLD.uptrend_rule() == "K5 uptrend: " + need


def test_uptrend_rule_reads_the_constants_at_call_time(monkeypatch):
    monkeypatch.setattr(GC, "K5_SLOPE_BARS", 7)
    assert BLD.uptrend_rule().endswith("both higher than 7 bars ago")


# ── tile writes [C1.2] ───────────────────────────────────────────────────────────────────────────────────────────
def test_loaded_sets_frames_session_loaded_at_and_seen_bar_t():
    fr = watch_frames()
    flt, upd = BLD.tile_update("OMH", fr, S, NOW, "loaded", {"1m": {"bar_t": stamp(S, 10, 38), "reason": "pushed"}})
    s = upd["$set"]
    assert flt == {"_id": "OMH"}
    assert set(s) == {"symbol", "session", "at", "loaded_at", "status", "frames", "seen_bar_t", "held.1m"}
    assert s["session"] == S.isoformat() and s["loaded_at"] == s["at"] and s["status"] == "loaded"
    assert s["seen_bar_t"] == stamp(S, 10, 39) and list(s["frames"]) == [tf for tf, _r in C.FRAMES]
    assert s["held.1m"] == {"bar_t": stamp(S, 10, 38), "reason": "pushed"}


@pytest.mark.parametrize("status", ["failed", "over_budget", "no_prints", "no_bars"])
def test_NEGATIVE_a_bad_read_sets_only_symbol_at_status_and_the_last_good_charts_survive(status):
    coll = FakeColl()
    fr = watch_frames()
    BLD.write(coll, [BLD.tile_update("OMH", fr, S, NOW, "loaded")])
    before = coll.docs["OMH"]
    flt, upd = BLD.tile_update("OMH", None, S, at(S, 10, 41, 30), status)
    assert set(upd["$set"]) == {"symbol", "at", "status"}
    flt, upd2 = BLD.tile_update("OMH", None, S, at(S, 10, 41, 30), status,
                                {"1m": {"bar_t": stamp(S, 10, 40), "reason": "missed_fetch"}})
    assert set(upd2["$set"]) == {"symbol", "at", "status", "held.1m"}
    BLD.write(coll, [(flt, upd2)])
    after = coll.docs["OMH"]
    assert after["status"] == status and after["frames"] == before["frames"]
    assert after["loaded_at"] == before["loaded_at"] and after["seen_bar_t"] == before["seen_bar_t"]
    assert after["session"] == before["session"] and after["held"]["1m"]["reason"] == "missed_fetch"


def test_NEGATIVE_loaded_without_frames_is_written_as_failed():
    _f, upd = BLD.tile_update("OMH", None, S, NOW, "loaded")
    assert upd["$set"]["status"] == "failed" and "frames" not in upd["$set"]


def test_NEGATIVE_a_raising_write_never_raises_and_none_is_a_no_op():
    upd = BLD.tile_update("OMH", None, S, NOW, "failed")
    assert BLD.write(FakeColl(fail=True), [upd, upd]) == 0
    assert BLD.write(None, [upd]) == 0


def test_seen_is_one_read_and_a_failure_is_empty():
    coll = FakeColl([{"_id": "OMH", "seen_bar_t": stamp(S, 10, 39)}, {"_id": "AMD", "seen_bar_t": None},
                     {"_id": "ZZZ", "seen_bar_t": stamp(S, 10, 0)}])
    assert BLD.seen(coll, ["OMH", "AMD"]) == {"OMH": stamp(S, 10, 39)}
    assert BLD.seen(FakeColl(fail=True), ["OMH"]) == {} and BLD.seen(None, ["OMH"]) == {} and BLD.seen(coll, []) == {}


def test_session_of_is_the_tabs_session_clock():
    assert BLD.session_of(at(S, 10, 0)) == (S, True, True)
    assert BLD.session_of(at(date(2026, 11, 15), 12, 0))[0] == S                # Sunday → the last market session
    assert BLD.session_of(at(S, 3, 0))[0] == PREV                              # before 04:00 → the session before


# ── ONE engine ───────────────────────────────────────────────────────────────────────────────────────────────────
def _pkg_sources():
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(PKG.glob("*.py"))}


def test_ONE_engine_guard_no_second_ema_cross_or_lease_engine_in_the_package():
    srcs = _pkg_sources()
    assert {"build.py", "cross_alerts.py", "loop.py", "constants.py", "colls.py"} <= set(srcs)
    for name, src in srcs.items():
        for bad in (".ewm(", "signals.ema(", "_masked_ema(", "find_one_and_update"):
            assert bad not in src, (name, bad)
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Compare):
                text = ast.unparse(node) if hasattr(ast, "unparse") else ""
                assert not re.search(r"\bema_?(9|21)\b", text), (name, text)
    assert "ema_cross" in srcs["cross_alerts.py"] and "ema_cross_block" in srcs["build.py"]
