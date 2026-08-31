"""Multi-timeframe zones, Fair Value Gaps, ORB, dynamic entry/stop, and
bullish patterns off daily bars.

Ajay 2026-08-29: "ORB and Fair value gap ... in Daily, Market hourly, 15
mins ... Give me stop loss and Entry calculated dynamically" + "any other
bullish patterns on an hourly chart ... Cup handle or Inverse head and
shoulder or Flat top".

These lock the parts that put a real stop on a real chart. The negative
cases matter most (Rule #6): a fabricated stop sizes a live position, and
a daily-calibrated pattern gate silently reused on 15-minute bars would
wear a Bulkowski citation it has not earned.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from patterns import timeframe as PT  # noqa: E402
from supply_demand import patterns as P  # noqa: E402
from supply_demand import timeframes as TF  # noqa: E402


def _frame(rows, freq="D"):
    """rows = [(open, high, low, close)]"""
    return pd.DataFrame(
        {"open": [r[0] for r in rows], "high": [r[1] for r in rows],
         "low": [r[2] for r in rows], "close": [r[3] for r in rows],
         "volume": [1_000_000] * len(rows)},
        index=pd.date_range("2026-01-01", periods=len(rows), freq=freq))


# ── timeframe plumbing ──────────────────────────────────────────────────────
def test_parse_tf_accepts_what_a_human_types_and_falls_back_to_daily():
    for raw in ("60m", "1h", "hour", "HOURLY", " 60min "):
        assert TF.parse_tf(raw) == TF.H1, raw
    for raw in ("15m", "15", "m15", "15MIN"):
        assert TF.parse_tf(raw) == TF.M15, raw
    for raw in ("daily", "1d", "D", "day"):
        assert TF.parse_tf(raw) == TF.DAILY, raw
    # Junk must land on daily: every surface worked on daily before the
    # dropdown existed, so it is the one fallback that cannot surprise.
    for raw in (None, "", "weekly", "4h", 15, {"tf": "60m"}):
        assert TF.parse_tf(raw) == TF.DAILY, raw


def test_tf_options_carry_a_label_and_a_real_span():
    opts = TF.tf_options()
    assert [o["key"] for o in opts] == [TF.DAILY, TF.H1, TF.M15]
    for o in opts:
        assert o["label"] and o["span"] and o["bars"] > 0


def test_hourly_budget_can_hold_bulkowskis_minimum_cup():
    """7 weeks = 245 hourly bars. A budget under that makes the cup
    detector silently barren and look broken."""
    h1 = TF.tf_spec(TF.H1)
    assert h1["bars"] >= 35 * PT.BARS_PER_SESSION["60m"] + 5


def test_resample_is_right_closed_and_drops_empty_buckets():
    idx = pd.date_range("2026-01-02 14:30", periods=30, freq="1min", tz="UTC")
    raw = pd.DataFrame({"open": range(30), "high": range(1, 31),
                        "low": range(-1, 29), "close": range(30),
                        "volume": [100] * 30}, index=idx)
    out = TF.resample_ohlcv(raw, "15min")
    # Exactly two 15-minute bars — NOT three. A right-CLOSED interval would
    # orphan the session's opening minute into a bar of its own, and that
    # one-minute bar wearing a 15-minute label is a fake extreme the swing
    # and FVG detectors would read as structure.
    assert len(out) == 2, "no orphan bar at the session open"
    assert str(out.index[0].time()) == "14:45:00", "stamped when it closes"
    assert out["high"].iloc[0] == 15 and out["low"].iloc[0] == -1
    assert out["volume"].iloc[0] == 1500
    assert out["open"].iloc[0] == 0, "first bar opens on the session's first tick"
    assert TF.resample_ohlcv(None, "15min") is None
    assert TF.resample_ohlcv(raw.iloc[0:0], "15min") is None


def test_frame_for_answers_meta_even_on_a_miss():
    df, meta = TF.frame_for("", TF.H1)
    assert df is None and meta["available"] is False and meta["reason"]
    assert meta["tf"] == TF.H1 and meta["label"]


# ── Fair Value Gaps ─────────────────────────────────────────────────────────
def _bull_fvg_frame():
    """Bar 1 high 100, bar 2 rips, bar 3 low 106 → unfilled demand gap."""
    rows = [(95, 100, 94, 99)] * 20                    # base, builds ATR
    rows += [(99, 100, 98, 99.5),                      # bar 1 (high 100)
             (100, 112, 100, 111),                     # bar 2 displacement
             (110, 114, 106, 112)]                     # bar 3 (low 106)
    rows += [(112, 113, 111, 112)] * 3                 # never returns
    return _frame(rows)


def test_bullish_fvg_is_found_with_its_band_and_zero_fill():
    gaps = P.fair_value_gaps(_bull_fvg_frame())
    demand = [g for g in gaps if g["kind"] == "demand"]
    assert demand, "a clean three-bar imbalance must be found"
    g = demand[0]
    assert g["lo"] == pytest.approx(100.0) and g["hi"] == pytest.approx(106.0)
    assert g["fill_pct"] == 0.0
    assert g["source"] == "fvg" and g["displacement_atr"] > 1


def test_bearish_fvg_is_a_supply_band():
    rows = [(105, 106, 100, 101)] * 20
    rows += [(101, 102, 100, 101),                     # bar 1 (low 100)
             (100, 100.5, 88, 89),                     # bar 2 down displacement
             (89, 94, 88, 90)]                         # bar 3 (high 94)
    rows += [(90, 91, 89, 90)] * 3
    gaps = P.fair_value_gaps(_frame(rows))
    supply = [g for g in gaps if g["kind"] == "supply"]
    assert supply and supply[0]["lo"] == pytest.approx(94.0)
    assert supply[0]["hi"] == pytest.approx(100.0)


def test_a_filled_gap_is_dropped_because_the_fill_was_the_signal():
    rows = [(95, 100, 94, 99)] * 20
    rows += [(99, 100, 98, 99.5), (100, 112, 100, 111), (110, 114, 106, 112)]
    rows += [(112, 113, 99, 100)]                      # trades all the way back
    gaps = P.fair_value_gaps(_frame(rows))
    assert not [g for g in gaps
                if g["kind"] == "demand" and g["lo"] == pytest.approx(100.0)]


def test_a_sleepy_bar_leaves_no_gap_no_matter_the_arithmetic():
    """Displacement filter: without it, any non-overlap is a 'gap'."""
    rows = [(100, 100.4, 99.6, 100)] * 25
    rows += [(100, 100.2, 99.9, 100.1),
             (100.1, 100.5, 100.05, 100.4),
             (100.4, 100.8, 100.3, 100.6)]
    gaps = P.fair_value_gaps(_frame(rows))
    assert gaps == []


def test_fvg_never_raises_on_junk():
    assert P.fair_value_gaps(None) == []
    assert P.fair_value_gaps(_frame([(1, 1, 1, 1)])) == []
    assert P.fair_value_gaps(_bull_fvg_frame(), last_price=0) == []


# ── dynamic entry / stop ────────────────────────────────────────────────────
def test_demand_band_below_price_is_a_long_at_the_top_stop_under_the_bottom():
    t = P.trade_levels({"lo": 100.0, "hi": 104.0}, 110.0, atr_value=4.0)
    assert t["side"] == "long"
    assert t["entry"] == 104.0                       # proximal edge
    assert t["stop"] < 100.0                         # distal edge + buffer
    assert t["stop"] == pytest.approx(100.0 - 4.0 * P.STOP_BUFFER_ATR)
    assert t["rr"] == pytest.approx(P.DEFAULT_TARGET_R)
    assert t["risk_pct"] > 0 and t["distance_pct"] < 0


def test_supply_band_above_price_is_a_short_at_the_bottom():
    t = P.trade_levels({"lo": 120.0, "hi": 125.0}, 110.0, atr_value=4.0)
    assert t["side"] == "short"
    assert t["entry"] == 120.0 and t["stop"] > 125.0


def test_a_structural_target_beats_a_multiple_when_one_exists():
    opposing = {"lo": 130.0, "hi": 134.0}
    t = P.trade_levels({"lo": 100.0, "hi": 104.0}, 110.0, atr_value=4.0,
                       opposing=opposing)
    assert t["target1"] == 130.0
    assert t["target_basis"] == "next supply band"
    # A nonsense "opposing" band BELOW entry must not produce a target
    # under the entry — it falls back to the measured multiple.
    bad = P.trade_levels({"lo": 100.0, "hi": 104.0}, 110.0, atr_value=4.0,
                         opposing={"lo": 50.0, "hi": 55.0})
    assert bad["target1"] > bad["entry"]
    assert "measured" in bad["target_basis"]


def test_the_stop_buffer_has_a_floor_so_a_quiet_name_is_not_stopped_on_the_level():
    """A stop resting exactly ON the level is the liquidity that gets taken."""
    t = P.trade_levels({"lo": 100.0, "hi": 104.0}, 110.0, atr_value=0.0)
    assert t["stop"] < 100.0
    assert t["buffer_basis"] == "floor"
    loud = P.trade_levels({"lo": 100.0, "hi": 104.0}, 110.0, atr_value=8.0)
    assert loud["stop"] < t["stop"], "a volatile name gets a wider stop"
    assert loud["buffer_basis"] == "ATR"


def test_trade_levels_refuse_nonsense_rather_than_inventing_a_stop():
    assert P.trade_levels({"lo": 104.0, "hi": 100.0}, 110.0) is None
    assert P.trade_levels({"lo": 0, "hi": 10}, 110.0) is None
    assert P.trade_levels({"hi": 104.0}, 110.0) is None
    assert P.trade_levels({"lo": 100.0, "hi": 104.0}, None) is None
    assert P.trade_levels({"lo": 100.0, "hi": 104.0}, "x") is None


def test_attach_levels_pairs_each_band_with_the_nearest_opposing_structure():
    bands = [{"kind": "demand", "lo": 100.0, "hi": 104.0},
             {"kind": "supply", "lo": 120.0, "hi": 124.0},
             {"kind": "supply", "lo": 140.0, "hi": 144.0}]
    out = P.attach_levels(bands, 110.0, 4.0)
    assert len(out) == 3
    demand = next(o for o in out if o["kind"] == "demand")
    assert demand["trade"]["target1"] == 120.0, "nearest supply, not the far one"
    assert P.attach_levels([], 110.0, 4.0) == []


def test_atr_is_none_on_a_frame_too_short_to_measure_it():
    assert P.atr(_frame([(1, 2, 0.5, 1)] * 5)) is None
    assert P.atr(None) is None
    assert P.atr(_frame([(10, 11, 9, 10)] * 40)) > 0


# ── bullish patterns across timeframes ──────────────────────────────────────
def test_daily_uses_the_cited_gates_verbatim_and_intraday_scales_by_calendar():
    """Bulkowski cites cup duration in WEEKS. Copying the daily bar-count to
    an hourly chart would find a '7-week cup' inside two sessions and label
    it with a citation it does not have."""
    assert PT._scaled_kwargs("daily") == {}, "daily must use cited defaults"
    h = PT._scaled_kwargs("60m")
    assert h["cup_min_bars"] == 35 * 7        # 7 weeks of hourly bars
    assert h["handle_min_bars"] == 5 * 7
    m = PT._scaled_kwargs("15m")
    assert m["cup_min_bars"] == 35 * 26
    assert m["cup_min_bars"] > h["cup_min_bars"] > 35


def test_out_of_range_patterns_are_reported_not_silently_barren():
    reach = PT.reachable("15m", 260)
    assert reach["cup_with_handle"]["reachable"] is False
    assert reach["cup_with_handle"]["needs_bars"] > 260
    assert reach["flat_top"]["reachable"] is True
    daily = PT.reachable("daily", 252)
    assert all(v["reachable"] for v in daily.values())


def _triangle_frame():
    """Flat top ~100 with rising lows underneath, then a breakout close."""
    rows = []
    for low in (85, 88, 91, 93, 95, 96):
        for j in range(6):
            p = 100 - (100 - low) * (1 - abs(j - 2.5) / 2.5)
            rows.append((p, p * 1.004, p * 0.996, p))
    rows.append((101, 102, 100.5, 101.5))
    return _frame(rows)


def test_flat_top_finds_the_ascending_triangle_with_its_own_entry_and_stop():
    out = PT.flat_top(_triangle_frame(), swing_window=2)
    assert len(out["fresh"]) == 1
    f = out["fresh"][0]
    assert f["kind"] == "flat_top" and f["confirmed"] is True
    assert f["touches"] >= PT.MIN_TOUCHES
    assert f["rising_lows"] >= PT.MIN_RISING_LOWS
    assert f["stop"] < f["entry"] < f["target"]
    assert f["cited"] is False, "no source in the library — must say so"


def test_flat_top_rejects_a_descending_base_and_a_short_frame():
    falling = _frame([(100 - i, 100.4 - i, 99.6 - i, 100 - i) for i in range(40)])
    assert PT.flat_top(falling, swing_window=2)["fresh"] == []
    assert PT.flat_top(_frame([(1, 1, 1, 1)] * 5))["fresh"] == []
    assert PT.flat_top(None)["fresh"] == []


def test_scan_stamps_stats_transfer_false_off_daily():
    """Bulkowski's hit rates were measured on daily bars. An hourly cup is a
    SHAPE, and the report must never let it borrow the daily statistics."""
    df = _triangle_frame()
    daily = PT.scan("TEST", "daily", df=df)
    assert daily["stats_transfer"] is True and daily["note"] is None
    hourly = PT.scan("TEST", "60m", df=df)
    assert hourly["stats_transfer"] is False
    assert "daily" in hourly["note"].lower()
    for p in hourly["patterns"]:
        assert p["stats_transfer"] is False
        assert p["stats_caveat"]


def test_scan_answers_a_dict_with_a_reason_when_there_are_no_bars():
    out = PT.scan("TEST", "60m", df=_frame([(1, 1, 1, 1)]))
    assert out["patterns"] == [] and out["bars"] == 0 or out["bars"] == 1
    assert out["symbol"] == "TEST" and out["timeframe"] == "60m"


def test_uncited_patterns_never_claim_a_citation_on_any_timeframe():
    for tf in ("daily", "60m", "15m"):
        for p in PT.scan("TEST", tf, df=_triangle_frame())["patterns"]:
            if p["kind"] == "flat_top":
                assert p["cited"] is False
                assert p["stats_transfer"] is False



# ── the per-ticker zone drill-in (Ajay 2026-08-29: "not on scans, but on
# demand in the support levels to figure out entries") ─────────────────────
def test_the_scan_boards_do_not_take_a_timeframe():
    """Ajay 2026-08-29 course-correction. The board answers 'which names',
    which is a daily structural question; the timeframe belongs on the
    per-ticker surfaces where an entry is actually chosen. A dropdown on
    the scan tabs would also cost an intraday fetch per tile per refresh."""
    import inspect

    from chart_maps import board as B
    src_board = inspect.getsource(B.board)
    assert "tf" not in inspect.signature(B.board).parameters
    assert "_timeframe_decor" not in src_board


def test_zone_map_overlays_the_timeframe_without_touching_the_daily_read():
    """The individual ticker's supply/demand tab keeps its daily re-entry
    answer underneath; the chosen timeframe rides alongside it."""
    import inspect

    from supply_demand import api as sd_api
    src_api = inspect.getsource(sd_api.get_zone_map)
    assert "tf_bands" in src_api and "trade_levels" in src_api
    # The daily analyze_symbol result is still what the body is built from.
    assert "analyze_symbol" in src_api
