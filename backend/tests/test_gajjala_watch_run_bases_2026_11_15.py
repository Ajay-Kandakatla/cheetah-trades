"""📶 GG's base count on the 👀 Gajjala's Watch 5-min chart (spec ggbase rev 2 WP-E, 2026-11-15).

Ajay, verbatim: "There is a concept of 3 bases and climax run can you bake that in to the app please" · "I need that
tracked in to Gajjala's". His answers the same day: the count starts at the 09:30 open, runs to the regular close, the
shortest base = K4_HF_BASE_MIN, a pause past K4_HF_BASE_MAX restarts it, "Just show it" (information only).

The watch's 5-min frame carries the SAME 📶 line the Gajjala cards print, from the ONE engine (`run_bases.count` →
`card_block` / `ellipses`), keys only when non-empty. NEGATIVES: the 1-min / 3-min frames never carry either key (built
or served); a flat day carries none; a blank stored line is not served; every other key of every frame is byte-equal to
the build without the count; the cross push / the held chip never read the count; no second base engine in the package.
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import run_bases as RB
from chart_maps.gajjala_watch import build as BLD
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from tests.test_gajjala_watch_api_2026_11_15 import _db, _doc

ET = ZoneInfo("America/New_York")
PREV = date(2026, 11, 12)
S = date(2026, 11, 13)
SESSION = S.isoformat()
PKG = Path(BLD.__file__).resolve().parent


def at(d, hh, mm, ss=0):
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=ET)


def stamp(hh, mm):
    return f"{SESSION} {hh:02d}:{mm:02d}"


def raw(d, end, price):
    """1-minute bars [04:00, end) ET (the minute loader's shape: UTC-naive index)."""
    t0 = pd.Timestamp(datetime(d.year, d.month, d.day, 4, 0), tz=ET)
    t1 = pd.Timestamp(datetime(d.year, d.month, d.day, *end), tz=ET)
    idx = pd.date_range(t0, t1, freq="1min", inclusive="left")
    rows = []
    for ts in idx:
        m = ts.hour * 60 + ts.minute
        p = price(ts)
        rows.append({"open": p - 0.01, "high": p + 0.03, "low": p - 0.04, "close": p, "volume": 1000.0,
                     "session": "premarket" if m < 570 else ("rth" if m < 960 else "afterhours")})
    return pd.DataFrame(rows, index=idx.tz_convert("UTC").tz_localize(None))


# 5-minute buckets from the 09:30 open: quiet, a 2-bar K1 run up, a 6-bar pause, a run up, a pause, a run up, a pause
STEPS = [("flat", 2, 10.0, 10.0),
         ("ramp", 1, 10.0, 10.8), ("ramp", 1, 10.8, 11.6), ("flat", 6, 11.4, 11.4),
         ("ramp", 1, 11.4, 12.3), ("ramp", 1, 12.3, 13.2), ("flat", 6, 13.0, 13.0),
         ("ramp", 1, 13.0, 14.0), ("ramp", 1, 14.0, 15.0), ("flat", 6, 14.8, 14.8)]
BUCKETS = []
for _kind, _n, _a, _z in STEPS:
    BUCKETS.extend([(_kind, _a, _z)] * _n)
END = (9 + (30 + 5 * len(BUCKETS)) // 60, (30 + 5 * len(BUCKETS)) % 60)       # the last bucket's close (11:40)
NOW = at(S, END[0], END[1], 30)


def three_bases_price(ts):
    m = ts.hour * 60 + ts.minute - (9 * 60 + 30)
    if m < 0:
        return 10.0
    k, j = divmod(m, 5)
    if k >= len(BUCKETS):
        return BUCKETS[-1][2]
    kind, a, z = BUCKETS[k]
    return round(a + (z - a) * (j + 1) / 5, 4) if kind == "ramp" else a


def watch_frames(price=three_bases_price):
    return B.build_frames("OMH", S, NOW, raw(PREV, (20, 0), lambda ts: 10.0), raw(S, END, price), rules=C.FRAMES)


def frames_of(fr) -> dict:
    return BLD.tile_update("OMH", fr, S, NOW, "loaded")[1]["$set"]["frames"]


# ── build ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_5m_frame_carries_the_engines_line_two_broke_and_the_3rd_forming_climax():
    fr = watch_frames()
    assert fr.frame("5m").t[-1] == stamp(*END)
    fs = frames_of(fr)
    five = fs[GC.RUN_BASE_FRAME]
    blk = RB.count(fr.frame(GC.RUN_BASE_FRAME))
    assert blk["n"] == 2 and blk["state"] == RB.FORMING
    assert five["run_bases"] == RB.card_block(blk)                               # the ONE engine, byte-equal
    assert five["run_bases"]["text"].startswith("📶 " + RB.BASE_WORDS[GC.RUN_BASE_CLIMAX_N - 1])
    assert five["run_bases"]["frame"] == GC.RUN_BASE_FRAME and five["run_bases"]["n"] == 2
    assert five["ellipses"] == RB.ellipses(blk, five["bars"], GC.RUN_BASE_FRAME)
    assert [e["n"] for e in five["ellipses"]] == [1, 2, 3]
    assert {e["kind"] for e in five["ellipses"]} == {RB.MARK_KIND}
    assert {e["tone"] for e in five["ellipses"]} == {RB.MARK_TONE}
    served = {b["t"] for b in five["bars"]}
    assert all(e["from_t"] in served and e["to_t"] in served for e in five["ellipses"])


def test_the_watch_line_equals_the_cards_line_for_the_same_frame():
    """The 🚩 card serves RB.card_block of the stored block; the watch serves RB.card_block of the same count."""
    fr = watch_frames()
    F = fr.frame(GC.RUN_BASE_FRAME)
    assert BLD.run_bases_keys(F, GC.RUN_BASE_FRAME, frames_of(fr)[GC.RUN_BASE_FRAME]["bars"])["run_bases"] == \
        RB.card_block(json.loads(json.dumps(RB.count(F))))


def test_NEGATIVE_the_1m_and_3m_frames_never_carry_either_key():
    fs = frames_of(watch_frames())
    for tf, _rule in C.FRAMES:
        if tf != GC.RUN_BASE_FRAME:
            assert "run_bases" not in fs[tf] and "ellipses" not in fs[tf], tf
    fr = watch_frames()
    assert BLD.run_bases_keys(fr.frame("1m"), "1m", []) == {}
    assert BLD.run_bases_keys(fr.frame("3m"), "3m", []) == {}
    assert BLD.run_bases_keys(None, GC.RUN_BASE_FRAME, []) == {}


def test_NEGATIVE_a_flat_day_has_no_line_and_no_mark():
    fs = frames_of(watch_frames(price=lambda ts: 10.0))
    for tf in fs:
        assert "run_bases" not in fs[tf] and "ellipses" not in fs[tf]


def test_NEGATIVE_every_other_key_is_byte_equal_to_the_build_without_the_count(monkeypatch):
    fr = watch_frames()
    with_count = frames_of(fr)
    monkeypatch.setattr(BLD, "run_bases_keys", lambda F, tf, bars: {})
    without = frames_of(fr)
    for tf in with_count:
        rest = {k: v for k, v in with_count[tf].items() if k not in ("run_bases", "ellipses")}
        assert json.dumps(rest, sort_keys=True, default=str) == json.dumps(without[tf], sort_keys=True, default=str)


def test_NEGATIVE_a_raising_engine_never_breaks_the_tile(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(RB, "_count", boom)
    fs = frames_of(watch_frames())
    assert "run_bases" not in fs[GC.RUN_BASE_FRAME] and "ellipses" not in fs[GC.RUN_BASE_FRAME]
    assert fs[GC.RUN_BASE_FRAME]["bars"]


def test_NEGATIVE_the_cross_push_and_the_loop_never_read_the_count():
    for name in ("cross_alerts.py", "loop.py", "store.py", "colls.py", "api.py", "constants.py"):
        src = (PKG / name).read_text(encoding="utf-8")
        assert "run_bases" not in src and "ellipses" not in src, name


def test_ONE_engine_no_second_base_count_in_the_package():
    for p in PKG.glob("*.py"):
        src = p.read_text(encoding="utf-8")
        for bad in ("find_legs", "is_demand", "k3_depth_ok", "BASE_WORDS", "K4_HF_BASE_MIN", "K4_HF_BASE_MAX"):
            assert bad not in src, (p.name, bad)


# ── payload ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _row_from_build(fr):
    doc = {"_id": "OMH", "symbol": "OMH", "at": NOW, "status": "loaded", "session": SESSION, "loaded_at": NOW,
           "frames": frames_of(fr)}
    return PL.row("OMH", doc, session=SESSION, is_today=True, in_window=True, now=NOW, claims=[])


def test_payload_serves_the_5m_line_and_marks_as_built():
    fr = watch_frames()
    built = frames_of(fr)[GC.RUN_BASE_FRAME]
    r = _row_from_build(fr)
    by = {f["tf"]: f for f in r["frames"]}
    assert by[GC.RUN_BASE_FRAME]["run_bases"] == built["run_bases"]
    assert by[GC.RUN_BASE_FRAME]["ellipses"] == built["ellipses"]
    for tf, _rule in C.FRAMES:
        if tf != GC.RUN_BASE_FRAME:
            assert "run_bases" not in by[tf] and "ellipses" not in by[tf]
    assert "ellipses" not in by[GC.RUN_BASE_FRAME]["tile"]                       # served beside the tile, not in it


def test_NEGATIVE_payload_drops_a_stray_key_on_another_frame_and_a_blank_line():
    t = {"run_bases": {"text": "📶 1st base · x", "title": "t"}, "ellipses": [{"kind": RB.MARK_KIND}]}
    for tf, _rule in C.FRAMES:
        if tf != GC.RUN_BASE_FRAME:
            f = PL.frame_block("OMH", tf, dict(t), None)
            assert "run_bases" not in f and "ellipses" not in f
    for bad in ({"text": "  "}, {"text": None}, {"title": "only"}, "📶 a string", None, 3):
        f = PL.frame_block("OMH", GC.RUN_BASE_FRAME, {"run_bases": bad, "ellipses": []}, None)
        assert "run_bases" not in f and "ellipses" not in f
    f = PL.frame_block("OMH", GC.RUN_BASE_FRAME, {"ellipses": ["junk", 3, None]}, None)
    assert "ellipses" not in f


def test_NEGATIVE_existing_docs_without_the_count_serve_the_exact_old_frame_keys():
    db = _db(["OMH"])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH", ups=(f"{SESSION} 09:35",))
    r = PL.build(at(S, 10, 30), db=db)["rows"][0]
    for f in r["frames"]:
        assert set(f) == {"tf", "label", "tile", "axis", "ema_cross", "uptrend", "held"}


def test_NEGATIVE_the_held_chip_is_unchanged_by_the_count():
    """The held chip of a frame reads ema_cross + held only — the same answer with or without a stored count."""
    up = f"{SESSION} 09:35"
    doc = _doc("OMH", ups=(up,), held={tf: {"bar_t": up, "reason": "off"} for tf, _r in C.FRAMES})
    plain = PL.row("OMH", doc, session=SESSION, is_today=True, in_window=True, now=at(S, 10, 30), claims=[])
    doc["frames"][GC.RUN_BASE_FRAME]["run_bases"] = {"text": "📶 1st base · broke out 09:50 ET · 5-min bars",
                                                    "title": "t", "n": 1, "state": RB.RUNNING, "frame": "5m"}
    withc = PL.row("OMH", doc, session=SESSION, is_today=True, in_window=True, now=at(S, 10, 30), claims=[])
    assert [f["held"] for f in plain["frames"]] == [f["held"] for f in withc["frames"]]
    assert [f["ema_cross"] for f in plain["frames"]] == [f["ema_cross"] for f in withc["frames"]]


def test_the_count_frame_is_one_of_the_watch_frames():
    assert GC.RUN_BASE_FRAME in dict(C.FRAMES)


def test_no_nan_in_the_served_marks():
    fr = watch_frames()
    for e in frames_of(fr)[GC.RUN_BASE_FRAME]["ellipses"]:
        assert math.isfinite(e["lo"]) and math.isfinite(e["hi"]) and e["lo"] <= e["hi"]
