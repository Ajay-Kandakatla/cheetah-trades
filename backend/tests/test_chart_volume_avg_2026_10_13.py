"""📊 The served 50-bar volume average (Ajay 2026-10-13).

The volume pane shipped averaging in the browser over the bars a tile SHOWS,
so a 120-bar tile spent 49 bars warming up. The backend now serves the true
average over the FULL frame, joined to the tile's bars by stamp — the
`_ma_series` / `_ma_curves` rule — and the frontend draws it when present.

Pinned here: the 50-bar mean itself, the full-frame rule (and its negative:
a tailed frame would be all warm-up), the by-stamp join (a live bar the frame
lacks is a gap, never a shifted value), the intraday key, the omissions, the
NaN guard, the soft-fail inside `_ma_curves`, idempotency, and the weekly /
monthly tile.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_maps import board as B          # noqa: E402
from chart_maps import ema_frames as EF    # noqa: E402
from chart_maps import support as S        # noqa: E402


def _daily(vols, start: str = "2024-01-02"):
    v = [float(x) for x in vols]
    idx = pd.bdate_range(start, periods=len(v))
    c = [10.0 + i * 0.01 for i in range(len(v))]
    return pd.DataFrame({"open": c, "high": [x + 0.5 for x in c],
                         "low": [x - 0.5 for x in c], "close": c,
                         "volume": v}, index=idx)


def _ramp(n: int):
    return [1_000.0 + 37.0 * i for i in range(n)]


def _tile(df):
    return {"symbol": "VOLT", "bars": B._frame_to_bars(df)}


# ── 1. the number ───────────────────────────────────────────────────────────
def test_period_is_his_fifty():
    assert B.VOL_AVG_PERIOD == 50
    assert B.VOL_AVG_LABEL == "50-bar avg volume"


def test_sixty_bars_warm_up_then_the_simple_mean():
    v = _ramp(60)
    ser = B._vol_avg_series(_daily(v))
    vals = ser["values"]
    assert len(vals) == 60 and len(ser["dates"]) == 60
    assert all(x is None for x in vals[:49])
    assert vals[48] is None
    assert vals[49] == pytest.approx(sum(v[0:50]) / 50)
    assert vals[50] == pytest.approx(sum(v[1:51]) / 50)
    assert vals[59] == pytest.approx(sum(v[10:60]) / 50)


def test_zero_volume_counts_as_zero():
    v = [0.0] * 10 + [100.0] * 50
    vals = B._vol_avg_series(_daily(v))["values"]
    assert vals[49] == pytest.approx(4_000.0 / 50)


# ── 2. the full-frame rule ──────────────────────────────────────────────────
def test_a_20_bar_window_of_a_200_bar_frame_has_a_value_on_every_bar():
    df = _daily(_ramp(200))
    tile = _tile(df.tail(20))
    B._vol_avg(tile, df)
    va = tile["vol_avg"]
    assert va["period"] == 50 and va["label"] == B.VOL_AVG_LABEL
    assert len(va["values"]) == 20
    assert all(x is not None for x in va["values"])
    full = B._vol_avg_series(df)["values"]
    assert va["values"] == full[-20:]


def test_NEGATIVE_the_tailed_frame_would_be_all_warm_up():
    """What the rule protects against: averaging the 20 SHOWN bars gives 20
    Nones, so the tile carries no `vol_avg` at all."""
    df = _daily(_ramp(200))
    tail = df.tail(20)
    assert all(x is None for x in B._vol_avg_series(tail)["values"])
    tile = _tile(tail)
    B._vol_avg(tile, tail)
    assert "vol_avg" not in tile


def test_the_board_attach_hands_the_UNTAILED_frame(monkeypatch):
    from sepa import prices
    df = _daily(_ramp(400))
    monkeypatch.setattr(prices, "load_prices", lambda s, *a, **k: df)
    monkeypatch.setattr(prices, "with_today_bar",
                        lambda d, s, **k: (d, None), raising=False)
    monkeypatch.setattr(prices, "bulk_snapshot", lambda syms: {}, raising=False)
    seen: list = []
    real = B._vol_avg_series

    def spy(frame, **kw):
        seen.append(len(frame))
        return real(frame, **kw)

    monkeypatch.setattr(B, "_vol_avg_series", spy)
    tiles = [{"symbol": "AAA"}]
    B._attach_bars(tiles, days=20)
    t = tiles[0]
    assert len(t["bars"]) == 20
    assert seen == [400]                                  # the WHOLE frame
    assert len(t["vol_avg"]["values"]) == 20
    assert all(x is not None for x in t["vol_avg"]["values"])


# ── 3. by stamp, not by position ────────────────────────────────────────────
def test_a_live_bar_the_frame_lacks_is_a_gap_not_a_shifted_value():
    df = _daily(_ramp(120))
    bars = B._frame_to_bars(df.tail(30))
    bars.append({"t": "2099-01-01", "o": 1, "h": 1, "l": 1, "c": 1, "v": 5e6})
    tile = {"bars": bars}
    B._vol_avg(tile, df)
    vals = tile["vol_avg"]["values"]
    assert len(vals) == 31
    assert vals[-1] is None
    full = B._vol_avg_series(df)["values"]
    assert vals[:-1] == full[-30:]                         # no shift left


def test_intraday_stamps_match_support_frame_bars():
    idx = pd.date_range("2026-10-12 13:30", periods=120, freq="5min", tz="UTC")
    v = _ramp(120)
    df = pd.DataFrame({"open": 10.0, "high": 11.0, "low": 9.0, "close": 10.0,
                       "volume": v}, index=idx)
    bars = S._frame_bars(df.tail(40))
    ser = B._vol_avg_series(df, stamp=S._intraday_stamp)
    assert set(b["t"] for b in bars) <= set(ser["dates"])
    tile = {"bars": bars}
    S._attach_ma(tile, df, intraday=True)
    assert all(x is not None for x in tile["vol_avg"]["values"])
    assert tile["vol_avg"]["values"][-1] == pytest.approx(sum(v[70:120]) / 50)


def test_NEGATIVE_intraday_bars_with_the_daily_key_match_nothing():
    idx = pd.date_range("2026-10-12 13:30", periods=120, freq="5min", tz="UTC")
    df = pd.DataFrame({"open": 10.0, "high": 11.0, "low": 9.0, "close": 10.0,
                       "volume": 1e5}, index=idx)
    tile = {"bars": S._frame_bars(df.tail(40))}
    B._vol_avg(tile, df)                                   # date-only key
    assert "vol_avg" not in tile


# ── 4. omissions + guards ───────────────────────────────────────────────────
def test_NEGATIVE_a_frame_shorter_than_fifty_omits_vol_avg():
    df = _daily(_ramp(49))
    tile = _tile(df)
    B._vol_avg(tile, df)
    assert "vol_avg" not in tile
    assert B._vol_avg_series(df)["values"] == [None] * 49


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -5.0])
def test_NEGATIVE_a_bad_volume_blanks_every_window_holding_it(bad):
    v = _ramp(120)
    v[60] = bad
    df = _daily(v)
    vals = B._vol_avg_series(df)["values"]
    for i in range(60, 110):                               # windows holding bar 60
        assert vals[i] is None, i
    assert vals[59] == pytest.approx(sum(v[10:60]) / 50)
    assert vals[110] == pytest.approx(sum(v[61:111]) / 50)
    tile = _tile(df)
    B._vol_avg(tile, df)
    text = json.dumps(tile["vol_avg"], allow_nan=False)    # raises on NaN/inf
    assert "NaN" not in text and "Infinity" not in text


@pytest.mark.parametrize("df", [None, pd.DataFrame(),
                                pd.DataFrame({"close": [1.0] * 60},
                                             index=pd.bdate_range("2024-01-02", periods=60))])
def test_NEGATIVE_no_frame_or_no_volume_column_is_None(df):
    assert B._vol_avg_series(df) is None
    tile = {"bars": [{"t": "2024-01-02", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]}
    B._vol_avg(tile, df)
    assert "vol_avg" not in tile


def test_NEGATIVE_a_tile_with_no_bars_gets_nothing():
    tile = {"bars": []}
    B._vol_avg(tile, _daily(_ramp(80)))
    assert "vol_avg" not in tile


def test_NEGATIVE_a_raising_vol_avg_leaves_bars_and_curves_intact(monkeypatch):
    df = _daily(_ramp(300))
    tile = _tile(df.tail(120))
    bars_before = json.dumps(tile["bars"])

    def boom(*a, **k):
        raise RuntimeError("volume read blew up")

    monkeypatch.setattr(B, "_vol_avg", boom)
    B._ma_curves(tile, df)
    assert json.dumps(tile["bars"]) == bars_before
    assert {c["tone"] for c in tile["curves"]} == {"ema9", "sma20", "sma200"}
    assert "vol_avg" not in tile


def test_NEGATIVE_a_raising_series_soft_fails_inside_vol_avg(monkeypatch):
    df = _daily(_ramp(80))
    tile = _tile(df)
    monkeypatch.setattr(B, "_vol_avg_series",
                        lambda *a, **k: (_ for _ in ()).throw(ValueError("x")))
    B._vol_avg(tile, df)
    assert "vol_avg" not in tile and len(tile["bars"]) == 80


def test_NEGATIVE_mas_already_on_the_tile_still_get_vol_avg():
    df = _daily(_ramp(300))
    tile = _tile(df.tail(120))
    tile["curves"] = [{"tone": "ema9", "label": "9 EMA", "values": [1.0] * 120}]
    B._ma_curves(tile, df)
    assert [c["tone"] for c in tile["curves"]] == ["ema9"]   # MA early return
    assert len(tile["vol_avg"]["values"]) == 120


def test_idempotent_served_once_and_a_stale_None_is_overwritten():
    df = _daily(_ramp(200))
    tile = _tile(df.tail(60))
    tile["vol_avg"] = None
    B._vol_avg(tile, df)
    first = tile["vol_avg"]
    assert first and len(first["values"]) == 60
    B._vol_avg(tile, _daily([9e9] * 200))                  # a second pass
    assert tile["vol_avg"] is first


def test_the_pure_series_does_not_touch_the_frame():
    df = _daily(_ramp(80))
    before = df.copy()
    B._vol_avg_series(df)
    pd.testing.assert_frame_equal(df, before)


# ── 5. the 〰️ 9 EMA · W/M tile ──────────────────────────────────────────────
def test_weekly_tile_carries_a_fifty_week_average():
    df = _daily(np.full(1_300, 1_000.0))                   # ~5 years of sessions
    out = EF.build("VOLT", "weekly", df=df)
    tile = out["tile"]
    va = tile["vol_avg"]
    assert va["period"] == 50
    assert len(va["values"]) == len(tile["bars"])
    rs = EF.resample_ohlcv(df, "weekly")
    weekly = rs["volume"].tolist()
    assert va["values"][-1] == pytest.approx(sum(weekly[-50:]) / 50)
    assert all(x is None for x in va["values"][:49])


def test_NEGATIVE_monthly_tile_under_fifty_months_has_no_vol_avg():
    df = _daily(np.full(500, 1_000.0))                     # ~24 months
    out = EF.build("VOLT", "monthly", df=df)
    assert out["tile"] is not None
    assert "vol_avg" not in out["tile"]


def test_NEGATIVE_ema_frames_survives_a_raising_vol_avg(monkeypatch):
    monkeypatch.setattr(B, "_vol_avg",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    out = EF.build("VOLT", "weekly", df=_daily(np.full(1_300, 1_000.0)))
    assert out["tile"] and out["tile"]["bars"] and out["error"] is None
    assert "vol_avg" not in out["tile"]


def test_every_served_value_is_finite_or_None():
    df = _daily(_ramp(300))
    tile = _tile(df.tail(150))
    B._ma_curves(tile, df)
    for x in tile["vol_avg"]["values"]:
        assert x is None or (isinstance(x, float) and math.isfinite(x))
