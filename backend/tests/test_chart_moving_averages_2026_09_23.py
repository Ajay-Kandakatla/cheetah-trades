"""9 EMA / 20 SMA / 200 SMA on the Chart Maps tiles — 2026-09-23.

Ajay: "I need 9 EMA and 20 SMA on our charts and also 200 MA on our charts as
check boxes.." The 200 is SIMPLE by his own answer, because Minervini's trend
template and this app's SEPA gate both read the 200-day simple average — a
chart line that disagreed with the gate beside it would be worse than no line.

The negatives are the point. Every one of these is a way the chart could have
drawn a number that is not the number it claims:

  * a "200 SMA" that is really a 120-bar average, because it was computed
    after `.tail(days)` and therefore changed every time he moved the zoom;
  * a "200 SMA" on a frame that has 150 closes — a straight line of nulls that
    says the average exists;
  * an average shifted one bar left on any tile carrying today's live
    extended-hours bar, because it was aligned by position instead of by date;
  * a 9 EMA seeded on four closes and labelled the same as a real one;
  * a NaN in the payload, which breaks the frontend's JSON.parse and passes
    every `<=` on the way there.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from chart_maps import board as B


def dated(n: int, start: str = "2024-01-02"):
    return pd.bdate_range(start, periods=n)


def frame(close, index=None):
    c = [float(x) for x in close]
    return pd.DataFrame(
        {"open": c,
         "high": [x * 1.01 for x in c],
         "low": [x * 0.99 for x in c],
         "close": c,
         "volume": [1_000.0] * len(c)},
        index=index if index is not None else dated(len(c)))


def step_frame(n: int = 400, tail_high: int = 160):
    """A frame that sits at 50 and steps to 150 exactly `tail_high` bars from
    the end.

    The step lands INSIDE the 200-bar window and OUTSIDE the 120-bar one on
    purpose: the 200-bar average of the last bar is then 130.0 and the 120-bar
    average is 150.0. Not a rounding difference — a different line. That gap is
    the whole point of computing before the tail.
    """
    return frame([50.0] * (n - tail_high) + [150.0] * tail_high)


# --------------------------------------------------------------- the periods
def test_exactly_his_three_periods_and_the_200_is_SIMPLE():
    """Rule #1: 9, 20 and 200 are his. Nothing else may appear."""
    assert [(tone, label, period, kind) for tone, label, period, kind in B.MA_SPECS] == [
        ("ema9", "9 EMA", 9, "ema"),
        ("sma20", "20 SMA", 20, "sma"),
        ("sma200", "200 SMA", 200, "sma"),
    ]


def test_the_ema_uses_adjust_False_like_every_other_EMA_in_this_codebase():
    df = frame(list(100 + np.cumsum(np.random.default_rng(3).normal(0, 1, 60))))
    ser = B._ma_series(df)
    want = df["close"].ewm(span=9, adjust=False).mean().tolist()
    got = ser["ema9"]
    # warm-up masked, the rest identical
    assert got[:8] == [None] * 8
    for i in range(8, len(want)):
        assert got[i] == pytest.approx(want[i])


def test_the_20_is_a_PLAIN_rolling_mean_not_an_ema():
    df = frame(list(100 + np.cumsum(np.random.default_rng(5).normal(0, 1, 60))))
    ser = B._ma_series(df)
    want = df["close"].rolling(20).mean().tolist()
    for i in range(19, len(want)):
        assert ser["sma20"][i] == pytest.approx(want[i])
    # and it is NOT the exponential one
    ema = df["close"].ewm(span=20, adjust=False).mean().tolist()
    assert ser["sma20"][-1] != pytest.approx(ema[-1])


# ------------------------------------------- the full frame, before the tail
def test_the_200_SMA_on_a_120_BAR_VIEW_is_the_TRUE_200_bar_average():
    """THE POINT OF THE WHOLE PACKAGE.

    The tile shows 120 bars; the average must still be over 200 closes. On the
    step frame those two numbers are 100.0 and 150.0 — not a rounding
    difference, a different line.
    """
    df = step_frame(400)
    bars = B._frame_to_bars(df.tail(120))
    tile = {"symbol": "XYZ", "bars": bars}
    B._ma_curves(tile, df)                      # the FULL frame, untailed
    sma200 = next(c for c in tile["curves"] if c["tone"] == "sma200")
    true200 = float(df["close"].tail(200).mean())
    only120 = float(df["close"].tail(120).mean())
    assert true200 != pytest.approx(only120)    # the frame really does separate them
    assert sma200["values"][-1] == pytest.approx(true200)
    assert sma200["values"][-1] != pytest.approx(only120)


def test_NEGATIVE_computing_on_the_TAILED_frame_would_have_been_wrong():
    """The bug this design exists to prevent, written down as a test."""
    df = step_frame(400)
    bars = B._frame_to_bars(df.tail(120))
    tile = {"symbol": "XYZ", "bars": bars}
    B._ma_curves(tile, df.tail(120))            # the mistake
    assert not any(c["tone"] == "sma200" for c in tile.get("curves") or [])


def test_the_curve_does_not_move_when_he_changes_the_zoom():
    df = step_frame(400)
    last = {}
    for days in (60, 120, 250):
        tile = {"symbol": "XYZ", "bars": B._frame_to_bars(df.tail(days))}
        B._ma_curves(tile, df)
        c = next(x for x in tile["curves"] if x["tone"] == "sma200")
        last[days] = c["values"][-1]
    assert last[60] == pytest.approx(last[120]) == pytest.approx(last[250])


# ----------------------------------------------------- warm-up is a GAP
def test_the_warm_up_is_None_and_the_curve_still_ships():
    df = frame(list(100 + np.cumsum(np.random.default_rng(7).normal(0, 1, 260))))
    tile = {"symbol": "XYZ", "bars": B._frame_to_bars(df)}
    B._ma_curves(tile, df)
    sma200 = next(c for c in tile["curves"] if c["tone"] == "sma200")
    assert sma200["values"][:199] == [None] * 199
    assert sma200["values"][199] is not None
    assert sma200["values"][-1] is not None


def test_NEGATIVE_a_150_close_frame_serves_NO_200_SMA_curve_at_all():
    """Not a line of nulls. A 200 SMA cannot exist on 150 closes and the chart
    must not imply that it does."""
    df = frame(list(100 + np.cumsum(np.random.default_rng(9).normal(0, 1, 150))))
    tile = {"symbol": "XYZ", "bars": B._frame_to_bars(df)}
    B._ma_curves(tile, df)
    tones = {c["tone"] for c in tile["curves"]}
    assert "sma200" not in tones
    assert tones == {"ema9", "sma20"}           # the two that CAN exist still ship


def test_NEGATIVE_a_79_bar_intraday_frame_serves_no_200_SMA():
    df = frame(list(100 + np.cumsum(np.random.default_rng(11).normal(0, 0.2, 79))))
    tile = {"symbol": "XYZ", "bars": B._frame_to_bars(df)}
    B._ma_curves(tile, df)
    assert {c["tone"] for c in tile["curves"]} == {"ema9", "sma20"}


def test_NEGATIVE_a_4_bar_frame_serves_NO_9_EMA_seeded_on_four_closes():
    """`ewm(adjust=False)` happily returns a value from bar one. A "9 EMA" of
    four closes is a guess wearing a label, so the warm-up mask applies to the
    EMA exactly as `rolling` applies it to the SMA."""
    df = frame([10.0, 11.0, 12.0, 13.0])
    tile = {"symbol": "XYZ", "bars": B._frame_to_bars(df)}
    B._ma_curves(tile, df)
    assert tile.get("curves") in (None, [])
    assert B._ma_series(df)["ema9"] == [None] * 4


def test_the_9_EMA_appears_on_its_ninth_bar_and_not_before():
    df = frame([10.0 + i for i in range(12)])
    ser = B._ma_series(df)
    assert ser["ema9"][:8] == [None] * 8
    assert ser["ema9"][8] is not None


# ------------------------------------------------------- by-date alignment
def test_a_LIVE_bar_the_frame_lacks_becomes_a_GAP_and_nothing_shifts():
    """The `prices.with_today_bar` case. A positional tail would move every
    average one bar left across the whole tile."""
    df = frame(list(100 + np.cumsum(np.random.default_rng(13).normal(0, 1, 300))))
    bars = B._frame_to_bars(df.tail(60))
    live_date = (pd.Timestamp(bars[-1]["t"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    bars.append({"t": live_date, "o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0, "v": 0.0})
    tile = {"symbol": "XYZ", "bars": bars}
    B._ma_curves(tile, df)
    ser = B._ma_series(df)
    by_date = dict(zip(ser["dates"], ser["sma20"]))
    sma20 = next(c for c in tile["curves"] if c["tone"] == "sma20")
    assert len(sma20["values"]) == len(bars)
    assert sma20["values"][-1] is None                      # the live bar is a gap
    for b, v in zip(bars[:-1], sma20["values"][:-1]):
        assert v == pytest.approx(by_date[b["t"]])          # every other value on ITS date


def test_a_hole_in_the_middle_of_the_tiles_bars_is_a_gap_not_a_shift():
    df = frame(list(100 + np.cumsum(np.random.default_rng(17).normal(0, 1, 300))))
    bars = B._frame_to_bars(df.tail(50))
    bars.insert(25, {"t": "1999-01-04", "o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0, "v": 0.0})
    tile = {"symbol": "XYZ", "bars": bars}
    B._ma_curves(tile, df)
    sma20 = next(c for c in tile["curves"] if c["tone"] == "sma20")
    ser = B._ma_series(df)
    by_date = dict(zip(ser["dates"], ser["sma20"]))
    assert sma20["values"][25] is None
    assert sma20["values"][26] == pytest.approx(by_date[bars[26]["t"]])


# ------------------------------------------------------------------- NaN
def test_no_NaN_anywhere_in_the_served_curves():
    df = frame(list(100 + np.cumsum(np.random.default_rng(19).normal(0, 1, 260))))
    df.loc[df.index[5], "close"] = np.nan           # a hole in the source
    tile = {"symbol": "XYZ", "bars": B._frame_to_bars(df)}
    B._ma_curves(tile, df)
    # allow_nan=False is the actual wire condition: a NaN here is what breaks
    # the frontend's JSON.parse.
    json.dumps(tile["curves"], allow_nan=False)
    for c in tile["curves"]:
        for v in c["values"]:
            assert v is None or (isinstance(v, float) and v == v)


def test_NEGATIVE_an_all_NaN_close_column_serves_nothing_and_does_not_crash():
    df = frame([100.0] * 260)
    df["close"] = np.nan
    tile = {"symbol": "XYZ", "bars": B._frame_to_bars(df)}
    B._ma_curves(tile, df)
    assert tile.get("curves") in (None, [])


# --------------------------------------------------------------- soft fails
def test_NEGATIVE_a_tile_with_no_bars_gets_no_curves_and_no_crash():
    tile = {"symbol": "XYZ", "bars": []}
    B._ma_curves(tile, step_frame(400))
    assert "curves" not in tile


def test_NEGATIVE_a_None_or_empty_frame_leaves_the_tile_alone():
    for bad in (None, pd.DataFrame(), pd.DataFrame({"foo": [1, 2, 3]})):
        tile = {"symbol": "XYZ", "bars": B._frame_to_bars(step_frame(300).tail(30))}
        B._ma_curves(tile, bad)
        assert tile.get("curves") in (None, [])


def test_NEGATIVE_a_frame_that_raises_leaves_the_tile_alone():
    class Boom:
        empty = False
        columns = ["close"]

        def __getitem__(self, k):
            raise RuntimeError("frame exploded")

    tile = {"symbol": "XYZ", "bars": B._frame_to_bars(step_frame(300).tail(30))}
    B._ma_curves(tile, Boom())
    assert tile.get("curves") in (None, [])


def test_the_curves_are_NOT_added_twice():
    df = step_frame(400)
    tile = {"symbol": "XYZ", "bars": B._frame_to_bars(df.tail(120))}
    B._ma_curves(tile, df)
    once = len(tile["curves"])
    B._ma_curves(tile, df)
    assert len(tile["curves"]) == once == 3


def test_it_rides_ALONGSIDE_the_keltner_channel_without_eating_it():
    df = frame(list(100 + np.cumsum(np.random.default_rng(23).normal(0, 1, 300))))
    tile = {"symbol": "XYZ", "bars": B._frame_to_bars(df.tail(120)),
            "curves": [{"tone": "keltner", "label": "KC mid",
                        "values": [None] * 120}]}
    B._ma_curves(tile, df)
    tones = [c["tone"] for c in tile["curves"]]
    assert tones[0] == "keltner"
    assert set(tones[1:]) == {"ema9", "sma20", "sma200"}


# ------------------------------------------------- nothing is gated or sorted
def test_bars_for_hands_back_the_UNTAILED_frame(monkeypatch):
    from sepa import prices
    df = step_frame(400)
    monkeypatch.setattr(prices, "load_prices", lambda s, *a, **k: df)
    monkeypatch.setattr(prices, "with_today_bar",
                        lambda d, s, **k: (d, None), raising=False)
    out: list = []
    bars = B.bars_for("XYZ", days=120, snap={}, frame_out=out)
    assert len(bars) == 120
    assert len(out) == 1 and len(out[0]) == 400        # the WHOLE frame came back


def test_the_tile_ORDER_and_every_other_key_are_byte_identical(monkeypatch):
    """Rule #10. An MA is a drawing: it may add `curves` and change nothing
    else — not the order, not a band, not a stat, not a metric."""
    import copy
    from sepa import prices
    df = step_frame(400)
    monkeypatch.setattr(prices, "load_prices", lambda s, *a, **k: df)
    monkeypatch.setattr(prices, "with_today_bar",
                        lambda d, s, **k: (d, None), raising=False)
    monkeypatch.setattr(prices, "bulk_snapshot", lambda syms: {}, raising=False)

    syms = ["AAA", "BBB", "CCC", "DDD"]
    tiles = [{"symbol": s, "bands": [], "lines": [], "markers": [],
              "_m": {"avg_turnover": 1e7}} for s in syms]
    B._attach_bars(tiles, days=120)
    assert [t["symbol"] for t in tiles] == syms

    with_ma = copy.deepcopy(tiles)
    for t in tiles:
        t.pop("curves", None)
    for a, b in zip(tiles, with_ma):
        assert set(b) - set(a) == {"curves"}
        for k in a:
            assert json.dumps(a[k], sort_keys=True) == json.dumps(b[k], sort_keys=True)


def test_every_tile_of_a_bar_attach_carries_all_three(monkeypatch):
    from sepa import prices
    df = step_frame(400)
    monkeypatch.setattr(prices, "load_prices", lambda s, *a, **k: df)
    monkeypatch.setattr(prices, "with_today_bar",
                        lambda d, s, **k: (d, None), raising=False)
    monkeypatch.setattr(prices, "bulk_snapshot", lambda syms: {}, raising=False)
    tiles = [{"symbol": s} for s in ("AAA", "BBB")]
    B._attach_bars(tiles, days=120)
    for t in tiles:
        assert {c["tone"] for c in t["curves"]} == {"ema9", "sma20", "sma200"}
        assert all(len(c["values"]) == len(t["bars"]) for c in t["curves"])


def test_NEGATIVE_a_symbol_whose_frame_will_not_load_keeps_a_tile_with_no_curves(monkeypatch):
    from sepa import prices
    monkeypatch.setattr(prices, "load_prices", lambda s, *a, **k: None)
    monkeypatch.setattr(prices, "bulk_snapshot", lambda syms: {}, raising=False)
    tiles = [{"symbol": "GONE"}]
    B._attach_bars(tiles, days=120)
    assert tiles[0]["bars"] == []
    assert tiles[0].get("curves") in (None, [])
