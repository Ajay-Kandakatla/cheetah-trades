"""🧨 The weak lid on the room read (A7, spec sitrack §3.5, 2026-11-26).

Ajay 2026-11-26: "can we make sure in the future these # are accurate ?" —
WHLR's 🧨 chip read "room +6666279%": the room was measured to the first
TESTED band (28,395.04, 2 touches, 187 sessions old) past 13 untested bands,
the nearest +154% away. `room_read` now SERVES that untested band (additive);
the room number, the state and every sort / gate stay as they were.

The WHLR doc below is the stored `bounce_room_zones` doc WHLR:2026-11-25
(19 bands), copied from a read-only probe of the api container on 2026-11-26.

Host-runnable (py3.9):
    cd backend && .venv/bin/python -m pytest tests/test_bounce_room_weak_lid_2026_11_26.py -q
"""
import copy
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import alert_gates as AG          # noqa: E402
from supply_demand import bounce_room as BR          # noqa: E402
from supply_demand import explosive as EX            # noqa: E402

ET = ZoneInfo("America/New_York")
WHLR_PX = 0.425944
NEW_KEYS = {"weak", "skipped", "target_age", "weak_text", "weak_title"}
OLD_KEYS = {"state", "room_pct", "atr_days", "band", "at_highs"}

WHLR_DOC = json.loads(r'''{
 "_id": "WHLR:2026-11-25",
 "symbol": "WHLR",
 "date": "2026-11-25",
 "geom": "board",
 "bands": [
  {
   "kind": "demand",
   "lo": 60912.0,
   "hi": 61430.4,
   "touches": 2,
   "strength": 50.0,
   "oldest_touch_bars": 226,
   "bars_since_test": 214
  },
  {
   "kind": "demand",
   "lo": 19481.8,
   "hi": 20175.8,
   "touches": 1,
   "strength": 25.0,
   "oldest_touch_bars": 191,
   "bars_since_test": 191
  },
  {
   "kind": "demand",
   "lo": 6960.82,
   "hi": 7208.78,
   "touches": 1,
   "strength": 25.0,
   "oldest_touch_bars": 147,
   "bars_since_test": 147
  },
  {
   "kind": "demand",
   "lo": 4371.73,
   "hi": 4527.47,
   "touches": 1,
   "strength": 25.0,
   "oldest_touch_bars": 140,
   "bars_since_test": 140
  },
  {
   "kind": "demand",
   "lo": 3735.07,
   "hi": 3868.13,
   "touches": 1,
   "strength": 25.0,
   "oldest_touch_bars": 130,
   "bars_since_test": 130
  },
  {
   "kind": "demand",
   "lo": 78.61,
   "hi": 81.41,
   "touches": 1,
   "strength": 25.0,
   "oldest_touch_bars": 79,
   "bars_since_test": 79
  },
  {
   "kind": "demand",
   "lo": 9.73,
   "hi": 10.07,
   "touches": 1,
   "strength": 27.0,
   "oldest_touch_bars": 45,
   "bars_since_test": 45
  },
  {
   "kind": "demand",
   "lo": 0.3,
   "hi": 0.31,
   "touches": 1,
   "strength": 26.0,
   "oldest_touch_bars": 10,
   "bars_since_test": 10
  },
  {
   "kind": "supply",
   "lo": 261667.26,
   "hi": 270988.74,
   "touches": 1,
   "strength": 25.0,
   "oldest_touch_bars": 243,
   "bars_since_test": 243
  },
  {
   "kind": "supply",
   "lo": 85949.1,
   "hi": 89010.9,
   "touches": 1,
   "strength": 25.0,
   "oldest_touch_bars": 220,
   "bars_since_test": 220
  },
  {
   "kind": "supply",
   "lo": 81492.48,
   "hi": 84395.52,
   "touches": 1,
   "strength": 25.0,
   "oldest_touch_bars": 211,
   "bars_since_test": 211
  },
  {
   "kind": "supply",
   "lo": 28395.04,
   "hi": 29406.56,
   "touches": 2,
   "strength": 50.0,
   "oldest_touch_bars": 188,
   "bars_since_test": 187
  },
  {
   "kind": "supply",
   "lo": 11374.99,
   "hi": 11780.21,
   "touches": 1,
   "strength": 25.0,
   "oldest_touch_bars": 148,
   "bars_since_test": 148
  },
  {
   "kind": "supply",
   "lo": 6324.16,
   "hi": 6549.44,
   "touches": 1,
   "strength": 25.0,
   "oldest_touch_bars": 129,
   "bars_since_test": 129
  },
  {
   "kind": "supply",
   "lo": 4244.4,
   "hi": 4395.6,
   "touches": 1,
   "strength": 25.0,
   "oldest_touch_bars": 116,
   "bars_since_test": 116
  },
  {
   "kind": "supply",
   "lo": 87.14,
   "hi": 90.24,
   "touches": 1,
   "strength": 25.0,
   "oldest_touch_bars": 63,
   "bars_since_test": 63
  },
  {
   "kind": "supply",
   "lo": 51.35,
   "hi": 53.17,
   "touches": 1,
   "strength": 37.0,
   "oldest_touch_bars": 44,
   "bars_since_test": 44
  },
  {
   "kind": "supply",
   "lo": 3.35,
   "hi": 3.47,
   "touches": 1,
   "strength": 37.0,
   "oldest_touch_bars": 24,
   "bars_since_test": 24
  },
  {
   "kind": "supply",
   "lo": 1.08,
   "hi": 1.12,
   "touches": 1,
   "strength": 75.0,
   "oldest_touch_bars": 9,
   "bars_since_test": 9
  }
 ],
 "atr14": 0.1524142857142857,
 "prev_close": 0.3254,
 "high_252": 266328.0,
 "recent": [
  {
   "date": "2026-11-18",
   "low": 0.3928,
   "high": 0.4334,
   "close": 0.4189
  },
  {
   "date": "2026-11-19",
   "low": 0.3106,
   "high": 0.4185,
   "close": 0.3607
  },
  {
   "date": "2026-11-20",
   "low": 0.3102,
   "high": 0.3634,
   "close": 0.3184
  },
  {
   "date": "2026-11-23",
   "low": 0.3233,
   "high": 0.3508,
   "close": 0.3236
  },
  {
   "date": "2026-11-24",
   "low": 0.3155,
   "high": 0.3562,
   "close": 0.3254
  }
 ],
 "feat": {
  "rsi14": 43.09645108367153,
  "rvol20": 0.26818196308075326,
  "rvol50": 0.48647449340392085,
  "dvol50": 692858.0789791634,
  "atr_pct": 121.54450803731281,
  "cmf20": 0.11394551699730773,
  "dist_52wh_pct": null,
  "above_52wl_pct": null,
  "kc": {
   "pos": -0.246,
   "on": false,
   "coil": 0,
   "rise": false,
   "fired": false,
   "coiled": false,
   "breaking": false,
   "width_ratio": 1.3477994985083792
  },
  "tail": [
   {
    "date": "2026-11-02",
    "open": 0.9945,
    "high": 1.09,
    "low": 0.5801,
    "close": 0.611,
    "volume": 2578893.81191
   },
   {
    "date": "2026-11-03",
    "open": 0.5442,
    "high": 0.6898,
    "low": 0.5251,
    "close": 0.602,
    "volume": 1625313.4324
   },
   {
    "date": "2026-11-04",
    "open": 0.5777,
    "high": 0.6039,
    "low": 0.43,
    "close": 0.4853,
    "volume": 883014.812291
   },
   {
    "date": "2026-11-05",
    "open": 0.4702,
    "high": 0.5969,
    "low": 0.433,
    "close": 0.4582,
    "volume": 1536811.171354
   },
   {
    "date": "2026-11-06",
    "open": 0.4448,
    "high": 0.445,
    "low": 0.3401,
    "close": 0.385,
    "volume": 10347764.464976
   },
   {
    "date": "2026-11-09",
    "open": 0.3721,
    "high": 0.4234,
    "low": 0.364,
    "close": 0.41,
    "volume": 1176171.284558
   },
   {
    "date": "2026-11-10",
    "open": 0.4148,
    "high": 0.4148,
    "low": 0.30749,
    "close": 0.321,
    "volume": 1236431.735221
   },
   {
    "date": "2026-11-11",
    "open": 0.3133,
    "high": 1.1,
    "low": 0.3131,
    "close": 0.7491,
    "volume": 66958090.629777
   },
   {
    "date": "2026-11-12",
    "open": 0.5755,
    "high": 0.6,
    "low": 0.4136,
    "close": 0.5076,
    "volume": 3357427.856789
   },
   {
    "date": "2026-11-13",
    "open": 0.5015,
    "high": 0.5168,
    "low": 0.4504,
    "close": 0.4855,
    "volume": 847319.291473
   },
   {
    "date": "2026-11-16",
    "open": 0.4476,
    "high": 0.4476,
    "low": 0.4,
    "close": 0.401,
    "volume": 315818.180245
   },
   {
    "date": "2026-11-17",
    "open": 0.3985,
    "high": 0.46899,
    "low": 0.34,
    "close": 0.44,
    "volume": 20638651.24816
   },
   {
    "date": "2026-11-18",
    "open": 0.417,
    "high": 0.4334,
    "low": 0.3928,
    "close": 0.4189,
    "volume": 394221.092491
   },
   {
    "date": "2026-11-19",
    "open": 0.41,
    "high": 0.4185,
    "low": 0.3106,
    "close": 0.3607,
    "volume": 602111.581663
   },
   {
    "date": "2026-11-20",
    "open": 0.3589,
    "high": 0.3634,
    "low": 0.3102,
    "close": 0.3184,
    "volume": 430236.769581
   },
   {
    "date": "2026-11-23",
    "open": 0.3275,
    "high": 0.3508,
    "low": 0.3233,
    "close": 0.3236,
    "volume": 298192.282451
   },
   {
    "date": "2026-11-24",
    "open": 0.3273,
    "high": 0.3562,
    "low": 0.3155,
    "close": 0.3254,
    "volume": 1558559.20374
   }
  ]
 },
 "computed_at": "2026-11-25T10:21:02.607653-05:00",
 "origin": "ondemand"
}''')


def _whlr():
    return copy.deepcopy(WHLR_DOC)


def _doc(bands, *, prev_close=100.0, atr14=2.0, high_252=500.0):
    return {"_id": "XYZ:2026-11-25", "symbol": "XYZ", "date": "2026-11-25", "geom": "board",
            "bands": list(bands), "atr14": atr14, "prev_close": prev_close,
            "high_252": high_252, "recent": []}


def _strip(room):
    if not isinstance(room, dict):
        return room
    return {k: v for k, v in room.items() if k not in NEW_KEYS}


def _snap(px, *, now):
    import pandas as pd
    ts_ns = int((now - timedelta(seconds=30)).timestamp() * 1e9)
    return {"open": px, "high": px * 1.02, "low": px * 0.98, "close": px, "volume": 1e6,
            "date": pd.Timestamp("2026-11-25"), "change_pct": 1.0, "prev_day_close": 0.3254,
            "last_trade_price": px, "last_trade_ts_ms": ts_ns}


# ── WHLR — the case that started it ──────────────────────────────────────────
def test_whlr_room_number_is_unchanged_and_the_weak_lid_is_served():
    out = BR.room_read(WHLR_PX, _whlr())
    assert set(out) == OLD_KEYS | NEW_KEYS
    assert out["state"] == "ROOM"
    assert out["room_pct"] == 6666278.68, "the room number is NOT touched"
    assert out["atr_days"] == 186298.9
    assert out["band"] == {"kind": "supply", "lo": 28395.04, "hi": 29406.56, "touches": 2}
    assert out["at_highs"] is False
    w = out["weak"]
    assert (w["lo"], w["hi"], w["touches"], w["pct"]) == (1.08, 1.12, 1, 153.6), \
        "the served pct keeps the engine's one decimal"
    assert w == AG.first_weak_lid(WHLR_DOC["bands"], WHLR_PX, 28395.04), "the ONE engine"
    assert out["skipped"] == 13
    assert out["target_age"] == 187
    assert out["weak_text"] == "1× band +154% first"
    assert out["weak_title"] == (
        "The room is measured to the first band tested 2 times or more "
        "(28,395.04–29,406.56, 2 touches, last tested 187 sessions ago, "
        "186,298.9 average daily ranges away). 13 untested bands under it; the nearest is "
        "1.08–1.12, +154% (1 touch). The room gate reads the tested band.")


def test_whlr_two_prints_a_tick_apart_serve_the_same_weak_text():
    a = BR.room_read(0.425944, _whlr())
    b = BR.room_read(0.4260, _whlr())
    assert a["weak"]["pct"] == 153.6 and b["weak"]["pct"] == 153.5
    assert a["weak_text"] == b["weak_text"] == "1× band +154% first"
    assert a["weak_title"] == b["weak_title"]


def test_the_tested_count_in_the_title_is_lid_min_touches_by_name():
    out = BR.room_read(WHLR_PX, _whlr())
    assert ("tested %d times or more" % AG.LID_MIN_TOUCHES) in out["weak_title"]
    assert "%d times or more" in BR.WEAK_TITLE, "never a typed 2"


# ── the one number format ────────────────────────────────────────────────────
@pytest.mark.parametrize("v, words", [
    (153.6, "154"), (153.5, "154"), (12.5, "13"), (10, "10"), (9.96, "10.0"),
    (3.44, "3.4"), (0.44, "0.4"),
])
def test_room_pct_words_case_list(v, words):
    """The case list the main session mirrors against the FE `pct`
    (frontend/src/lib/bounceRoom.ts: |v| >= 10 → toFixed(0), else toFixed(1))."""
    assert BR._room_pct_words(v) == words


@pytest.mark.parametrize("v, words", [
    (6666278.68, "6666279"), (9.95, "9.9"), (0.45, "0.5"), (0.05, "0.1"), (-12.5, "-13"),
    (0, "0.0"), (10.0, "10"), (9.999, "10.0"),
])
def test_room_pct_words_matches_tofixed_on_the_binary_value(v, words):
    """9.95 is 9.9499… in binary → JS (9.95).toFixed(1) is "9.9"; 0.45 is
    0.4500…01 → "0.5". Not Python's banker's round (round(12.5) == 12)."""
    assert BR._room_pct_words(v) == words


@pytest.mark.parametrize("bad", [None, "x", float("nan"), float("inf"), [], {}])
def test_room_pct_words_garbage_is_none_never_raises(bad):
    assert BR._room_pct_words(bad) is None


# ── negatives: nothing moves where there is no untested band ────────────────
def test_no_untested_band_under_the_target_the_dict_equals_todays_exactly():
    """The JDZG shape: the tested band is the first band overhead."""
    doc = _doc([{"kind": "demand", "lo": 90.0, "hi": 92.0, "touches": 1},
                {"kind": "supply", "lo": 110.0, "hi": 112.0, "touches": 2, "bars_since_test": 5},
                {"kind": "supply", "lo": 130.0, "hi": 133.0, "touches": 1}])    # untested but ABOVE
    out = BR.room_read(99.0, doc)
    assert out == {"state": "ROOM", "room_pct": 11.11, "atr_days": 5.5,
                   "band": {"kind": "supply", "lo": 110.0, "hi": 112.0, "touches": 2},
                   "at_highs": False}


def test_an_untested_band_the_print_sits_inside_is_not_under_the_target():
    doc = _doc([{"kind": "supply", "lo": 98.0, "hi": 101.0, "touches": 1},
                {"kind": "supply", "lo": 110.0, "hi": 112.0, "touches": 2}])
    assert set(BR.room_read(99.0, doc)) == OLD_KEYS


def test_clear_in_band_and_garbage_prints_are_unchanged():
    only_weak = _doc([{"kind": "supply", "lo": 110.0, "hi": 112.0, "touches": 1}])
    assert BR.room_read(99.0, only_weak) == {"state": "CLEAR", "room_pct": None,
                                             "atr_days": None, "band": None, "at_highs": False}
    inb = BR.room_read(28400.0, _whlr())
    assert inb["state"] == "IN_BAND" and set(inb) == OLD_KEYS
    for bad in (None, 0, -1, "x", float("nan"), float("inf")):
        assert BR.room_read(bad, _whlr()) is None


def test_near_carries_the_weak_lid_too():
    doc = _doc([{"kind": "supply", "lo": 100.5, "hi": 100.8, "touches": 1},
                {"kind": "supply", "lo": 101.5, "hi": 102.0, "touches": 2}])
    out = BR.room_read(100.0, doc)
    assert out["state"] == "NEAR" and out["room_pct"] == 1.5
    assert out["weak_text"] == "1× band +0.5% first" and out["skipped"] == 1


def test_optional_title_parts_drop_when_unknown_and_one_band_is_singular():
    doc = _doc([{"kind": "supply", "lo": 105.0, "hi": 106.0, "touches": 1},
                {"kind": "supply", "lo": 120.0, "hi": 121.0, "touches": 3}], atr14=None)
    out = BR.room_read(100.0, doc)
    assert out["target_age"] is None and out["atr_days"] is None
    assert out["weak_title"] == (
        "The room is measured to the first band tested 2 times or more "
        "(120.00–121.00, 3 touches). 1 untested band under it; the nearest is "
        "105.00–106.00, +5.0% (1 touch). The room gate reads the tested band.")
    assert out["weak_text"] == "1× band +5.0% first"


def test_a_band_with_unknown_touches_is_proven_kept_and_never_skipped():
    weak = {"kind": "supply", "lo": 105.0, "hi": 106.0, "touches": 1}
    unknown = {"kind": "supply", "lo": 110.0, "hi": 111.0}                  # nobody counted
    zero = {"kind": "supply", "lo": 112.0, "hi": 113.0, "touches": 0}
    tested = {"kind": "supply", "lo": 120.0, "hi": 121.0, "touches": 2}
    out = BR.room_read(100.0, _doc([weak, unknown, zero, tested]))
    assert out["band"]["lo"] == 110.0, "the unknown-touches band IS the lid (proven)"
    assert out["skipped"] == 1 and out["weak"]["lo"] == 105.0
    out2 = BR.room_read(100.0, _doc([unknown, zero, tested]))
    assert set(out2) == OLD_KEYS, "unknown / zero touches are never counted as skipped"


def test_an_untested_demand_band_above_the_print_is_overhead_and_counts_as_skipped():
    dem = {"kind": "demand", "lo": 104.0, "hi": 105.0, "touches": 1}
    tested = {"kind": "supply", "lo": 120.0, "hi": 121.0, "touches": 2}
    out = BR.room_read(100.0, _doc([dem, tested]))
    assert out["skipped"] == 1 and out["weak"]["lo"] == 104.0
    assert out["weak_text"] == "1× band +4.0% first"


def test_skipped_counts_only_bands_between_the_print_and_the_target():
    bands = [{"kind": "demand", "lo": 90.0, "hi": 92.0, "touches": 1},     # under the print
             {"kind": "supply", "lo": 103.0, "hi": 104.0, "touches": 1},
             {"kind": "supply", "lo": 107.0, "hi": 108.0, "touches": 1},
             {"kind": "supply", "lo": 120.0, "hi": 121.0, "touches": 2},   # the target
             {"kind": "supply", "lo": 130.0, "hi": 131.0, "touches": 1},   # above it
             {"kind": "supply", "lo": "x", "hi": 140.0, "touches": 1},     # garbage
             {"kind": "supply", "lo": 150.0, "hi": 149.0, "touches": 1}]   # lo > hi
    out = BR.room_read(100.0, _doc(bands))
    assert out["skipped"] == 2 and out["weak"]["lo"] == 103.0
    assert "2 untested bands under it" in out["weak_title"]


def test_no_b_word_in_the_new_strings():
    out = BR.room_read(WHLR_PX, _whlr())
    for s in (BR.WEAK_TEXT, BR.WEAK_TITLE, BR.WEAK_TITLE_AGE, BR.WEAK_TITLE_ATR,
              out["weak_text"], out["weak_title"]):
        assert "bounce" not in s.lower()


def test_overhead_bands_on_whlr_is_the_two_tested_bands():
    out = BR.overhead_bands(WHLR_DOC["bands"], WHLR_PX, WHLR_DOC["prev_close"])
    assert out == [{"kind": "broken_support", "lo": 60912.0, "hi": 61430.4, "touches": 2},
                   {"kind": "supply", "lo": 28395.04, "hi": 29406.56, "touches": 2}]


def test_target_age_reads_the_band_first_overhead_picked():
    weak = {"kind": "supply", "lo": 105.0, "hi": 106.0, "touches": 1, "bars_since_test": 1}
    older = {"kind": "supply", "lo": 120.0, "hi": 125.0, "touches": 2, "bars_since_test": 40}
    same_lo = {"kind": "supply", "lo": 120.0, "hi": 121.0, "touches": 2, "bars_since_test": 9}
    twin = dict(same_lo, bars_since_test=77)                         # equal slim form, later
    broken = {"kind": "supply", "lo": 98.0, "hi": 99.0, "touches": 2, "bars_since_test": 3}
    out = BR.room_read(100.0, _doc([broken, weak, older, same_lo, twin]))
    assert out["band"] == {"kind": "supply", "lo": 120.0, "hi": 125.0, "touches": 2}
    assert out["target_age"] == 40, "first in doc order among equal lo — first_overhead's pick"
    out2 = BR.room_read(100.0, _doc([broken, weak, same_lo, twin, older]))
    assert out2["band"]["hi"] == 121.0 and out2["target_age"] == 9
    junk = dict(same_lo, bars_since_test="x")
    assert BR.room_read(100.0, _doc([weak, junk]))["target_age"] is None
    assert "sessions ago" not in BR.room_read(100.0, _doc([weak, junk]))["weak_title"]


# ── sorts, gates and the other reads read none of the new keys ──────────────
def test_room_ok_rank_into_supply_and_keys_are_the_same_with_and_without_the_new_keys():
    room = BR.room_read(WHLR_PX, _whlr())
    with_keys = {"symbol": "WHLR", "room": room, "bounce": None}
    without = {"symbol": "WHLR", "room": _strip(room), "bounce": None}
    assert set(room) - set(without["room"]) == NEW_KEYS
    for fn in (BR.room_ok, BR.room_rank, BR.into_supply, BR.room_group, BR.bounce_room_key):
        assert fn(with_keys) == fn(without), fn.__name__


def test_the_row_path_enterable_explosive_and_band_structure_are_identical(monkeypatch):
    now = datetime(2026, 11, 25, 11, 0, tzinfo=ET)
    snap = _snap(WHLR_PX, now=now)
    row = BR.read_symbol("WHLR", _whlr(), snap, now=now)
    assert row["room"]["weak_text"] == "1× band +154% first"
    real = BR.room_read
    monkeypatch.setattr(BR, "room_read", lambda px, doc, *a, **k: _strip(real(px, doc, *a, **k)))
    base = BR.read_symbol("WHLR", _whlr(), snap, now=now)
    assert set(base["room"]) == OLD_KEYS
    for k in ("enterable", "band_structure", "bounce", "demand", "print", "coverage"):
        assert json.dumps(row.get(k), sort_keys=True, default=str) == \
            json.dumps(base.get(k), sort_keys=True, default=str), k
    ex, ex0 = row["explosive"], base["explosive"]
    assert ex is not None and ex0 is not None and row["enterable"] and row["band_structure"]
    assert ex["room"]["weak_text"] == "1× band +154% first", "the chip's read carries it"
    assert _strip(ex["room"]) == ex0["room"]
    assert {k: v for k, v in ex.items() if k != "room"} == \
        {k: v for k, v in ex0.items() if k != "room"}
    assert EX.explosive_key(ex, "WHLR") == EX.explosive_key(ex0, "WHLR")
    assert BR.bounce_room_key(row) == BR.bounce_room_key(base)
    assert BR.room_ok(row) == BR.room_ok(base) and BR.into_supply(row) == BR.into_supply(base)
