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
    assert [o["key"] for o in opts] == [TF.DAILY, TF.H1, TF.M15, TF.M15_OPEN]
    # the live chart frame is opt-in only (it must never feed the zone engine)
    assert [o["key"] for o in TF.tf_options(include_live=True)][-1] == TF.M5_LIVE
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


# ── market mood + buy signal (Ajay 2026-08-29) ─────────────────────────────
def _trending_frame(n=80, up=True, freq="15min"):
    rows = []
    for i in range(n):
        base = 100 + (i * 0.4 if up else -i * 0.4)
        rows.append((base, base + 0.6, base - 0.6, base + (0.3 if up else -0.3)))
    return _frame(rows, freq=freq)


def test_mood_reads_bullish_on_an_advance_and_bearish_on_a_decline():
    from supply_demand import mood as M
    up = M.mood(_trending_frame(up=True))
    down = M.mood(_trending_frame(up=False))
    assert up["score"] > 0 and "bull" in up["label"]
    assert down["score"] < 0 and "bear" in down["label"]
    assert set(up["components"]) == {"trend", "momentum", "pressure", "vwap",
                                     "location", "structure"}


def test_mood_drops_the_forming_bar_so_a_signal_never_repaints():
    """The one GainzAlgo claim worth copying is no-repainting, and it is a
    property, not a feature: the last bar is still being written."""
    from supply_demand import mood as M
    df = _trending_frame()
    assert M.mood(df)["bars"] == len(df) - 1
    assert M.mood(df, closed_only=False)["bars"] == len(df)


def test_a_missing_component_scores_zero_and_is_named_never_assumed_neutral():
    from supply_demand import mood as M
    m = M.mood(_trending_frame(freq="D"))          # daily frame → no VWAP
    assert m["components"]["vwap"] == 0.0
    assert any("vwap" in u for u in m["unavailable"])


def test_mood_degrades_on_junk_rather_than_guessing():
    from supply_demand import mood as M
    for bad in (None, _frame([(1, 1, 1, 1)] * 2)):
        out = M.mood(bad)
        assert out["label"] == "unavailable" and out["score"] == 0.0


def test_a_buy_needs_BOTH_a_mood_and_a_level():
    """Mood alone is a weather report: without a band there is no stop, and
    without a stop there is no position size."""
    from supply_demand import mood as M
    df = _trending_frame(up=True)
    last = float(df["close"].iloc[-2])
    band = {"kind": "demand", "lo": last * 0.99, "hi": last * 0.999,
            "source": "swing"}
    good = M.signal(df, [band], last_price=last, atr_value=1.0)
    assert good["action"] == "BUY"
    assert good["trade"]["stop"] < good["trade"]["entry"]
    assert good["no_repaint"] is True
    # same constructive mood, no band anywhere near → no trade
    far = M.signal(df, [{"kind": "demand", "lo": last * 0.5, "hi": last * 0.55}],
                   last_price=last, atr_value=1.0)
    assert far["action"] == "WAIT"
    assert any("demand band" in b for b in far["blockers"])
    # a band right there but a bearish mood → still no trade
    down = _trending_frame(up=False)
    dlast = float(down["close"].iloc[-2])
    bear = M.signal(down, [{"kind": "demand", "lo": dlast * 0.99,
                            "hi": dlast * 0.999}],
                    last_price=dlast, atr_value=1.0)
    assert bear["action"] != "BUY"
    # A decisively bearish mood resolves to SELL, and the reasons a BUY did
    # not fire move to buy_blockers (they would read as sell doubts here).
    reasons_not_to_buy = bear["blockers"] + bear.get("buy_blockers", [])
    assert any("mood" in b for b in reasons_not_to_buy)


def test_signal_never_fires_without_a_stop():
    from supply_demand import mood as M
    df = _trending_frame(up=True)
    last = float(df["close"].iloc[-2])
    broken = {"kind": "demand", "lo": last * 1.5, "hi": last * 0.5}  # inverted
    out = M.signal(df, [broken], last_price=last, atr_value=1.0)
    assert out["action"] != "BUY" or out["trade"] is not None


def test_watch_pushes_only_the_actionable_half_of_each_signal():
    """A BUY on something already held is not a decision; a SELL on
    something not held is noise."""
    from catalysts import signal_watch as SW
    assert SW.should_push("BUY", False) == (True, "")
    assert SW.should_push("BUY", True)[0] is False
    assert SW.should_push("SELL", True) == (True, "")
    assert SW.should_push("SELL", False)[0] is False
    assert SW.should_push("WAIT", False)[0] is False


def test_signal_watch_session_gate_and_push_kind():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from catalysts import signal_watch as SW
    et = ZoneInfo("America/New_York")
    assert SW.in_session(datetime(2026, 8, 29, 11, 0, tzinfo=et)) is False   # Sat
    assert SW.in_session(datetime(2026, 8, 28, 9, 20, tzinfo=et)) is False   # pre
    assert SW.in_session(datetime(2026, 8, 28, 10, 0, tzinfo=et)) is True
    # The gate is asserted against a STUBBED clock. Reading the real one made
    # this test pass only outside market hours: on 2026-08-31 at 09:31 ET it
    # went past the gate into the live path and died on an unrelated py3.9
    # pydantic annotation. A test whose result depends on when the suite runs
    # is not testing the thing it names.
    real = SW.in_session
    try:
        SW.in_session = lambda *a, **k: False
        out = SW.check_once()
    finally:
        SW.in_session = real
    assert out["ran"] is False and "RTH" in out["reason"]
    import inspect
    src = inspect.getsource(SW)
    assert 'kind="pivot_alert"' in src, "the keep-set gains no new kinds"
    assert "signal_alert" not in src


def test_every_signal_is_written_to_the_forward_ledger():
    """The honest answer to 'how does GainzAlgo figure it out': we cannot
    know, so we measure OURS against real forward prices."""
    import inspect

    from catalysts import signal_watch as SW
    from chart_maps import support as S
    assert "record_observation" in inspect.getsource(SW)
    assert "record_observation" in inspect.getsource(S._record_signal)


def test_vwap_scores_on_intraday_frames_where_the_index_is_naive_utc():
    """Regression: the intraday cache indexes bars in NAIVE UTC, and reading
    that as 'no timezone, no VWAP' silently zeroed a 15-point component on
    exactly the timeframes VWAP exists for."""
    import pandas as pd

    from supply_demand import mood as M
    idx = pd.date_range("2026-08-28 13:30", periods=60, freq="15min")  # naive
    df = pd.DataFrame({"open": range(60), "high": range(1, 61),
                       "low": range(-1, 59), "close": range(60),
                       "volume": [1000] * 60}, index=idx)
    assert M._vwap(df) is not None
    # A daily frame must still decline: a multi-year VWAP is not a level.
    daily = _frame([(10, 11, 9, 10)] * 60)
    assert M._vwap(daily) is None


def test_a_sell_does_not_carry_the_reasons_a_buy_did_not_fire():
    from supply_demand import mood as M
    down = _trending_frame(up=False)
    last = float(down["close"].iloc[-2])
    out = M.signal(down, [{"kind": "demand", "lo": last * 0.5, "hi": last * 0.55}],
                   last_price=last, atr_value=1.0)
    assert out["action"] == "SELL"
    assert out["blockers"] == [], "buy blockers must not read as sell doubts"
    assert out["buy_blockers"], "they are kept, just under their own key"


# ── Smart Money Concepts: sweep → BOS → order block → FVG ─────────────────
def _smc_frame():
    """40 flat bars (swing low ~99), a sweep candle that wicks to 96 and
    closes back down, then a 4-bar displacement up through structure."""
    rows = [(100, 101, 99, 100.2)] * 40
    rows += [(100, 100.5, 99.5, 100)] * 5
    rows += [(100.4, 100.5, 96.0, 99.2)]          # the sweep + order block
    rows += [(99.3, 106, 99.2, 105.5)] * 4        # displacement
    rows += [(105.5, 106, 104.5, 105)] * 6
    return _frame(rows, freq="15min")


def test_a_sweep_needs_the_close_back_inside_or_it_is_a_breakout():
    """The close is the whole test: through-and-close-beyond is a breakout,
    through-and-close-back is a trap. They mean opposite things."""
    from supply_demand import smc
    sweeps = smc.liquidity_sweeps(_smc_frame())
    assert sweeps and sweeps[0]["side"] == "sell_side"
    assert sweeps[0]["wick"] < sweeps[0]["level"] < sweeps[0]["close"]

    # same wick, but it CLOSES below the level → breakout, not a sweep
    rows = [(100, 101, 99, 100.2)] * 40 + [(100, 100.5, 99.5, 100)] * 5
    rows += [(100.4, 100.5, 96.0, 96.5)]
    rows += [(96.5, 97, 95, 95.5)] * 4
    broke = smc.liquidity_sweeps(_frame(rows, freq="15min"))
    assert not [s for s in broke if s["side"] == "sell_side"
                and s["level"] >= 99.0 and s["bars_ago"] <= 6]


def test_bos_and_choch_are_distinguished_by_the_prior_trend():
    from supply_demand import smc
    breaks = smc.structure_breaks(_smc_frame())
    assert breaks
    kinds = {b["kind"] for b in breaks}
    assert kinds <= {"BOS", "CHoCH"}
    bull = [b for b in breaks if b["direction"] == "bullish"]
    assert bull, "the displacement closes above prior structure"


def test_order_block_is_the_last_opposing_candle_before_displacement():
    from supply_demand import smc
    obs = smc.order_blocks(_smc_frame(), direction="bullish")
    assert obs
    ob = obs[0]
    assert ob["kind"] == "bullish"
    assert ob["close"] < ob["open"], "the block is a DOWN candle"
    assert ob["displacement_atr"] >= smc.MIN_DISPLACEMENT_ATR


def test_no_displacement_means_no_order_block():
    """Without an impulse it is just a red candle, not an institutional
    footprint."""
    from supply_demand import smc
    flat = _frame([(100, 100.4, 99.6, 100)] * 60, freq="15min")
    assert smc.order_blocks(flat, direction="bullish") == []


def test_the_five_step_model_requires_every_step():
    from supply_demand import smc
    full = smc.find_setups(_smc_frame())
    assert len(full) == 1
    s = full[0]
    assert s["sweep"] and s["break"] and s["order_block"]
    assert s["entries"]["aggressive"] and s["entries"]["conservative"]
    assert s["stop"] < s["entries"]["aggressive"]
    assert s["score"] > 0 and s["cited"] is False

    # a sweep with no following structure break is NOT a setup
    rows = [(100, 101, 99, 100.2)] * 40 + [(100, 100.5, 99.5, 100)] * 5
    rows += [(100.4, 100.5, 96.0, 99.2)] + [(99.2, 100, 99, 99.5)] * 8
    assert smc.find_setups(_frame(rows, freq="15min")) == []


def test_conservative_entry_is_deeper_and_therefore_a_better_R():
    """The whole reason to wait for the refined entry."""
    from supply_demand import smc
    s = smc.find_setups(_smc_frame())[0]
    legs = s["legs"]
    assert legs["conservative"]["entry"] < legs["aggressive"]["entry"]
    assert legs["conservative"]["rr"] > legs["aggressive"]["rr"]


def test_a_stop_inside_the_noise_is_flagged_not_sold_as_a_huge_R():
    """Same lesson as the Desk's ASH row: a tiny stop inflates R without
    improving the trade, and an unflagged 20R would be a lie by arithmetic."""
    from supply_demand import smc
    s = smc.find_setups(_smc_frame())[0]
    tight = [lg for lg in s["legs"].values() if lg.get("too_tight")]
    assert tight, "a sub-0.5-ATR stop must be flagged"
    assert all("noise" in lg["warning"] for lg in tight)
    assert all(lg["rr"] for lg in tight), "the number is still shown, not hidden"


def test_smc_never_claims_a_citation_it_does_not_have():
    from supply_demand import smc
    assert smc.CITED is False
    assert "no canonical text" in smc.SOURCE_NOTE.lower()
    for s in smc.find_setups(_smc_frame()):
        assert s["cited"] is False


def test_smc_degrades_on_junk_instead_of_raising():
    from supply_demand import smc
    for bad in (None, _frame([(1, 1, 1, 1)] * 3)):
        assert smc.liquidity_sweeps(bad) == []
        assert smc.structure_breaks(bad) == []
        assert smc.order_blocks(bad) == []
        assert smc.find_setups(bad) == []


# ── the chart must draw the bars the levels came from (Ajay's screenshot) ──
def test_intraday_bars_carry_a_time_or_a_session_collapses_to_one_candle():
    import pandas as pd

    from chart_maps import support as S
    idx = pd.date_range("2026-08-28 13:45", periods=4, freq="15min")
    df = pd.DataFrame({"open": [1, 2, 3, 4], "high": [2, 3, 4, 5],
                       "low": [0.5, 1.5, 2.5, 3.5], "close": [1.5, 2.5, 3.5, 4.5],
                       "volume": [10] * 4}, index=idx)
    bars = S._frame_bars(df)
    assert len(bars) == 4
    assert bars[0]["t"] == "2026-08-28 09:45"   # ET on the axis (13:45 UTC) since 2026-09-02
    assert len({b["t"] for b in bars}) == 4, \
        "date-only stamps would collapse a whole session into one candle"


def test_the_session_timeframe_keeps_only_one_day():
    from supply_demand import timeframes as TF
    spec = TF.tf_spec(TF.M15_OPEN)
    assert spec["days"] == 1 and spec["bars"] <= 27      # 6.5h / 15m = 26
    assert "09:30" in spec["span"]
    for alias in ("open", "session", "15m_open"):
        assert TF.parse_tf(alias) == TF.M15_OPEN, alias


def test_overlay_draws_the_smc_objects_and_reports_what_it_capped():
    """Ajay 2026-08-29: "do you actually draw these out on the map?" — they
    have to reach the tile's bands/lines, not just a table."""
    from chart_maps import support as S
    tile = {"bands": [{"kind": "demand", "lo": 90, "hi": 92}], "lines": []}
    gaps = [{"kind": "demand", "lo": 95, "hi": 96, "fill_pct": 0},
            {"kind": "demand", "lo": 80, "hi": 81, "fill_pct": 10},
            {"kind": "supply", "lo": 130, "hi": 131, "fill_pct": 0}]
    smc = {"order_blocks": [{"lo": 97, "hi": 98, "displacement_atr": 2.1}],
           "breaks": [{"kind": "CHoCH", "direction": "bullish", "level": 105}],
           "sweeps": [{"side": "sell_side", "level": 89}]}
    orb = {"lo": 99, "hi": 101, "minutes": 15, "session": "2026-08-28"}
    out = S._draw_overlay(tile, gaps, smc, orb, 100.0)

    kinds = [b["kind"] for b in tile["bands"]]
    assert "fvg_demand" in kinds and "order_block" in kinds
    assert "demand" in kinds, "the original swing bands survive"
    labels = [l["label"] for l in tile["lines"]]
    assert any("CHoCH" in l for l in labels)
    assert any("swept" in l for l in labels)
    assert any("ORB" in l for l in labels)
    # capped at the nearest two, and it SAYS three were found
    assert out["drawn"]["fvg"] == 2 and out["found"]["fvg"] == 3


def test_overlay_survives_missing_pieces():
    from chart_maps import support as S
    tile = {"bands": [], "lines": []}
    out = S._draw_overlay(tile, [], None, None, 100.0)
    assert out["drawn"] == {"fvg": 0, "order_block": 0, "bos": 0,
                            "sweep": 0, "orb": 0}
    assert tile["bands"] == [] and tile["lines"] == []


def test_trend_says_bullish_or_bearish_and_refuses_on_a_short_frame():
    from chart_maps import support as S
    up = _frame([(100 + i, 101 + i, 99 + i, 100.5 + i) for i in range(80)])
    down = _frame([(200 - i, 201 - i, 199 - i, 199.5 - i) for i in range(80)])
    assert S.trend_read(up, None)["direction"] == "bullish"
    assert S.trend_read(down, None)["direction"] == "bearish"
    short = S.trend_read(_frame([(1, 2, 0.5, 1)] * 20), None)
    assert short["direction"] == "unknown"
    assert "50 bars" in short["why"][0]
    # disagreement with mood is stated, not silently averaged away
    dis = S.trend_read(up, {"score": -40})
    assert dis["mood_agrees"] is False


# ── engine fixes 2026-09-05 (Ajay: "yes please fix the bugs") ─────────────────
def _minutes(start, n, tz="UTC"):
    idx = pd.date_range(start, periods=n, freq="1min", tz=tz)
    base = [100.0 + (i % 5) * 0.1 for i in range(n)]
    return pd.DataFrame({"open": base, "high": [b + 0.2 for b in base],
                         "low": [b - 0.2 for b in base], "close": base,
                         "volume": [100] * n}, index=idx)


def test_frame_for_as_of_is_the_last_minute_seen_never_a_future_label():
    """At 10:07 ET the 15m frame's last bucket is labelled 10:15 (its CLOSE);
    stamping the payload with that put the read 8 minutes in the future.
    as_of is the last raw minute that actually printed, and the bucket that
    has not reached its label is flagged partial."""
    raw = _minutes("2026-09-04 13:30", 38)                    # 13:30–14:07 UTC
    df, meta = TF.frame_for("ACME", TF.M15, raw=raw)
    assert meta["available"] is True
    assert str(df.index[-1]) == "2026-09-04 14:15:00+00:00", "label stays the close"
    assert meta["as_of"] == str(raw.index[-1])                # 14:07, not 14:15
    assert meta["partial"] is True


def test_frame_for_marks_a_bucket_that_saw_its_last_minute_as_complete():
    raw = _minutes("2026-09-04 13:30", 45)                    # 13:30–14:14 UTC
    df, meta = TF.frame_for("ACME", TF.M15, raw=raw)
    assert str(df.index[-1]) == "2026-09-04 14:15:00+00:00"
    assert meta["as_of"] == str(raw.index[-1])
    assert meta["partial"] is False


def test_hourly_buckets_are_clock_anchored_and_the_FIRST_is_the_half_hour():
    """The module docstring said the LAST hourly bar was the half hour. On
    09:30–16:00 ET the buckets are 30,60,60,60,60,60,60 minutes: the first
    (09:30–10:00) is the short one, and every label sits on the clock hour."""
    raw = _minutes("2026-09-04 13:30", 390)                   # full RTH session
    df, meta = TF.frame_for("ACME", TF.H1, raw=raw)
    assert list(df["volume"]) == [3000, 6000, 6000, 6000, 6000, 6000, 6000]
    assert all(t.minute == 0 for t in df.index)
    assert meta["partial"] is False
    doc = TF.__doc__
    assert "the last one is a half hour" not in doc
    assert "first" in doc.lower() and "half hour" in doc.lower()


def test_a_supply_band_containing_price_yields_no_long_plan():
    """Inside resistance the verdict says AT_SUPPLY / caution; the same payload
    printed a LONG at the band top with a stop under it. No plan while price
    is inside a supply band."""
    inside = P.trade_levels({"kind": "supply", "lo": 100.0, "hi": 104.0}, 102.0, 2.0)
    assert inside is None
    # a demand band containing price is still the long-from-support read
    dem = P.trade_levels({"kind": "demand", "lo": 100.0, "hi": 104.0}, 102.0, 2.0)
    assert dem and dem["side"] == "long"
    # a supply band entirely above / below price is unchanged
    above = P.trade_levels({"kind": "supply", "lo": 120.0, "hi": 125.0}, 110.0, 4.0)
    assert above and above["side"] == "short"
    below = P.trade_levels({"kind": "supply", "lo": 90.0, "hi": 95.0}, 110.0, 4.0)
    assert below and below["side"] == "long"                # broken supply = support
    # attach_levels carries the absence with a reason, never a fabricated plan
    rows = P.attach_levels([{"kind": "supply", "lo": 100.0, "hi": 104.0, "source": "swing"}],
                           102.0, 2.0)
    assert rows[0]["trade"] is None and "supply" in rows[0]["trade_reason"]


def test_atr_is_labelled_as_the_simple_mean_it_computes():
    """The docstring said Wilder-style; the math is a 14-bar simple mean of true
    range. The MATH stays (changing it moves every stop); the label is fixed."""
    n = 36
    tr = [1.0] * n
    tr[-6] = 10.0
    df = pd.DataFrame({"open": [100.0] * n, "high": [100.0 + t for t in tr],
                       "low": [100.0] * n, "close": [100.0] * n, "volume": [1] * n},
                      index=pd.date_range("2026-01-01", periods=n, freq="D"))
    assert P.atr(df) == pytest.approx((13 * 1.0 + 10.0) / 14)      # simple mean
    assert "Wilder" not in (P.atr.__doc__ or "")
    assert "simple" in P.atr.__doc__ and "mean" in P.atr.__doc__
