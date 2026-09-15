"""Chart Maps study verification, 2026-09-14.

Ajay: "I would [like] the AMD, KC logic and also supply demand logic on all
charts of Chart Maps to be verified. Also make it a lil more sophisticated."

Reproduced on his OWN holdings before any of this was written:

  CRDO  raided its base low on 08-20 (226.58 under 229.18, closed 231.35),
        closed UNDER the base on 08-24 (222.61), and on 09-14 — price 150,
        −35% — the chart still drew the base at 229–286 and the raid line as
        a live "manipulation" read. GLW (raid 08-21, broke 08-24) and ALAB
        (raid 08-19, broke 08-21) read the same way. `find_cycle` only looked
        for a close ABOVE the top after a raid; a close BELOW the raided edge
        was invisible, so a base that failed the day after its raid stayed
        "raided · 1d ago" on the Raided board.
  CRDO  Keltner position −0.242 — below the lower band, a computed bearish
        read — rendered "KC no read", the same badge as a halted name.
  CRDO  "AMD no cycle · 16d ago": grade `none` for a stale raid, with the
        raid's age appended.
  CRDO  Support tile with the Keltner box ticked carried BOTH the channel
        curves and three flat KC lines with duplicate right-edge labels.

The negatives here are the point: every fix is a way the chart could have
kept saying something false.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from supply_demand import amd as A
from supply_demand import keltner as K
from supply_demand import turning_bullish as TB
from supply_demand import price_zones as PZ


def dated(n: int, start: str = "2026-01-05"):
    return pd.bdate_range(start, periods=n)


def frame(close, hi=None, lo=None, vol=None, index=None):
    c = list(close)
    d = {"open": c,
         "high": hi or [x * 1.005 for x in c],
         "low": lo or [x * 0.995 for x in c],
         "close": c}
    if vol is not None:
        d["volume"] = list(vol)
    return pd.DataFrame(d, index=index)


def base_and_raid(after: list, *, raid_vol: float = 3.0, index=True):
    """20 tight bars, a raid that closes back inside, then `after` closes."""
    c = [100 + (i % 3) * 0.4 for i in range(20)] + [100.1] + list(after)
    hi = [x + 0.5 for x in c]
    lo = [x - 0.5 for x in c]
    lo[20] = 96.0                        # the wick takes the stops
    hi[20] = 100.6
    vol = [1_000.0] * len(c)
    vol[20] = 1_000.0 * raid_vol
    return frame(c, hi, lo, vol, index=dated(len(c)) if index else None)


# ---------------------------------------------------------------- AMD failed
def test_a_close_THROUGH_the_raided_edge_after_the_raid_is_a_FAILED_cycle():
    """CRDO, GLW and ALAB on 2026-09-14. The stops were taken, price closed
    back inside — and then it closed under the base. That is the base
    breaking, not a manipulation waiting for its markup."""
    df = base_and_raid([100.2, 98.0, 97.0, 96.5])
    cyc = A.find_cycle(df)
    assert cyc["phase"] == "failed"
    assert cyc["manipulation"] is not None
    assert cyc["distribution"] is None
    assert cyc["failure"]["close"] == 98.0
    assert cyc["failure"]["bars_ago"] == 2
    assert cyc["failure"]["level"] == cyc["accumulation"]["lo"]


def test_NEGATIVE_a_collapse_AFTER_the_markup_does_not_undo_a_completed_cycle():
    """The cycle completed. What happens next is the next story."""
    df = base_and_raid([101.8, 103, 106, 109, 95.0, 94.0])
    cyc = A.find_cycle(df)
    assert cyc["phase"] == "distribution"
    assert cyc["failure"] is None


def test_NEGATIVE_a_wick_under_the_edge_that_CLOSES_inside_is_not_a_failure():
    """A second raid is still a raid. Only a CLOSE beyond the edge fails it."""
    df = base_and_raid([100.3, 100.2])
    lo = df["low"].to_numpy(dtype=float).copy()
    lo[-1] = 95.5                      # another wick, closes at 100.2
    df["low"] = lo
    cyc = A.find_cycle(df)
    assert cyc["phase"] == "manipulation"
    assert cyc["failure"] is None


def test_a_failure_has_NO_bar_limit_because_a_dead_base_is_never_a_live_read():
    """MAX_MARKUP_BARS bounds the markup. It must not bound the failure: a
    base that broke 40 bars after its raid is still broken today."""
    flat = [100.2] * (A.MAX_MARKUP_BARS + 10)
    df = base_and_raid(flat + [97.0, 96.0])
    cyc = A.find_cycle(df)
    assert cyc["phase"] == "failed"


def test_the_failed_grade_reaches_the_verdict_and_reads_as_a_WARNING():
    df = base_and_raid([100.2, 98.0, 97.0])
    v = TB.amd_verdict(df)
    assert v["grade"] == "failed" and v["turning"] is False
    assert v["failed_bars_ago"] == 1 and v["failed_close"] == 98.0
    text, tone = TB.verdict_text("amd", v)
    assert text == "AMD base failed · 1d ago"
    assert tone == "warn"


def test_NEGATIVE_a_base_that_fails_the_day_after_its_raid_is_NOT_raided():
    """The Raided board's exact failure mode: GLW raided 08-21, closed under
    the base 08-24, and `raid_bars_ago == 1` kept it on the board."""
    df = base_and_raid([98.0])
    v = TB.amd_verdict(df)
    assert v["raid_bars_ago"] == 1 <= TB.MAX_RAID_BARS_AGO
    assert v["grade"] == "failed" and v["turning"] is False


def test_the_chart_overlay_says_FAILED_on_the_band_and_marks_the_bar():
    df = base_and_raid([100.2, 98.0, 97.0])
    o = A.chart_overlay(df)
    assert o["phase"] == "failed"
    assert "FAILED" in o["bands"][0]["label"]
    kinds = {m["kind"]: m for m in o["markers"]}
    assert set(kinds) == {"amd_a", "amd_m", "amd_x"}
    assert kinds["amd_x"]["date"] == df.index[22].strftime("%Y-%m-%d")
    assert kinds["amd_m"]["date"] == df.index[20].strftime("%Y-%m-%d")
    assert kinds["amd_a"]["date"] == df.index[0].strftime("%Y-%m-%d")


# ----------------------------------------------------------- AMD sophistication
def test_the_raid_carries_its_depth_and_its_volume_as_DATA():
    df = base_and_raid([100.2], raid_vol=2.5)
    r = A.find_cycle(df)["manipulation"]
    edge = r["level"]
    assert r["depth_pct"] == pytest.approx((edge - 96.0) / edge * 100.0, abs=0.01)
    assert r["vol_ratio"] == pytest.approx(2.5, abs=0.01)
    assert "−" in A.raid_label(r) and "2.5× vol" in A.raid_label(r)


def test_NEGATIVE_no_volume_column_means_no_ratio_and_a_shorter_label():
    df = base_and_raid([100.2])
    df = df.drop(columns=["volume"])
    r = A.find_cycle(df)["manipulation"]
    assert r["vol_ratio"] is None
    assert "vol" not in A.raid_label(r)


def test_NEGATIVE_depth_and_volume_are_never_thresholds():
    """A one-cent wick on flat volume is still a raid. Sophistication here is
    description, not a new gate — the read measured INVERTED and nothing may
    quietly make it stricter and call that accuracy."""
    df = base_and_raid([100.2], raid_vol=1.0)
    lo = df["low"].to_numpy(dtype=float).copy()
    lo[20] = A.find_cycle(base_and_raid([100.2]))["accumulation"]["lo"] - 0.01
    df["low"] = lo
    cyc = A.find_cycle(df)
    assert cyc["phase"] == "manipulation"


def test_the_markup_bar_is_marked_and_a_frame_without_dates_marks_NOTHING():
    df = base_and_raid([101.8, 103, 106, 109])
    o = A.chart_overlay(df)
    assert {m["kind"] for m in o["markers"]} == {"amd_a", "amd_m", "amd_d"}
    bare = A.chart_overlay(base_and_raid([101.8, 103, 106, 109], index=False))
    assert bare["phase"] == "distribution"
    assert bare["markers"] == []          # no dates → no invented positions


def test_the_verdict_carries_the_dates_so_a_stored_row_can_mark_the_bars():
    df = base_and_raid([101.8, 103, 106, 109])
    v = TB.amd_verdict(df)
    assert v["base_date"] == df.index[0].strftime("%Y-%m-%d")
    assert v["raid_date"] == df.index[20].strftime("%Y-%m-%d")
    assert v["markup_date"] == df.index[21].strftime("%Y-%m-%d")
    assert v["failed_date"] is None


def test_NEGATIVE_no_cycle_and_a_bare_base_carry_NO_age_in_the_badge():
    """"AMD no cycle · 16d ago" was a sentence at war with itself."""
    assert TB.verdict_text("amd", {"grade": "none", "bars_ago": 16}) == ("AMD no cycle", "muted")
    assert TB.verdict_text("amd", {"grade": "basing", "bars_ago": 4}) == ("AMD basing", "muted")


def test_the_grade_tables_cover_every_grade():
    assert set(TB.AMD_GRADES) == set(TB.AMD_TEXT)
    assert set(TB.KELTNER_GRADES) == set(TB.KELTNER_TEXT)
    assert "failed" in A.PHASES


# ------------------------------------------------------------------- Keltner
def wild_then_coiled(n_coil: int = 12):
    """A volatile run, then a tight drift so the Bollinger band sits inside
    the channel for the last `n_coil` bars."""
    rng = np.random.default_rng(7)
    c = list(100 + np.cumsum(rng.normal(0, 3.0, 60)))
    last = c[-1]
    c += [last + 0.02 * i for i in range(n_coil)]
    hi = [x + 1.5 for x in c[:60]] + [x + 0.05 for x in c[60:]]
    lo = [x - 1.5 for x in c[:60]] + [x - 0.05 for x in c[60:]]
    return frame(c, hi, lo, index=dated(len(c)))


def test_below_the_band_is_a_NAMED_bearish_read_not_a_no_read():
    """CRDO at position −0.24. A computed read must never share a badge with
    'cannot compute'."""
    rng = np.random.default_rng(3)
    c = list(100 + np.cumsum(rng.normal(0, 1.0, 60))) + [60.0, 55.0, 50.0]
    df = frame(c, index=dated(len(c)))
    v = TB.keltner_verdict(df)
    assert v["position"] < 0
    assert v["grade"] == "below_band"
    assert TB.verdict_text("keltner", v) == ("KC below the band", "warn")


def test_the_lower_half_is_named_too_and_none_means_only_no_channel():
    rng = np.random.default_rng(5)
    c = list(100 + np.cumsum(rng.normal(0, 1.0, 80)))
    df = frame(c, index=dated(len(c)))
    v = TB.keltner_verdict(df)
    assert v["grade"] in TB.KELTNER_GRADES
    if 0 <= v["position"] < TB.COILED_MIN_POSITION:
        assert v["grade"] == "lower_half"
        assert TB.verdict_text("keltner", v) == ("KC lower half", "muted")
    flat = frame([100.0] * 60, [100.0] * 60, [100.0] * 60, index=dated(60))
    assert TB.keltner_verdict(flat) is None or TB.keltner_verdict(flat)["grade"] == "none"


def test_squeeze_series_agrees_with_the_scalar_and_is_keyed_by_date():
    df = wild_then_coiled()
    ser = K.squeeze_series(df)
    sq = K.squeeze(df)
    assert ser["dates"][-1] == df.index[-1].strftime("%Y-%m-%d")
    assert len(ser["on"]) == len(ser["dates"]) == len(ser["ratio"]) == len(df)
    assert ser["on"][-1] == sq["on"]
    # `bars` counts the trailing run of the series — same arithmetic.
    run = 0
    for v in reversed(ser["on"]):
        if not v:
            break
        run += 1
    assert run == sq["bars"]
    assert sq["ratio"] == ser["ratio"][-1]


def test_the_squeeze_ratio_is_under_one_inside_and_reaches_the_badge():
    df = wild_then_coiled()
    r = K.reading(df)
    if r["squeeze"]:
        assert r["squeeze_ratio"] < 1.0
        v = TB.keltner_verdict(df)
        text, _ = TB.verdict_text("keltner", v)
        assert "× wide" in text and "squeeze" in text
    else:                                # a wild seed — the contract still holds
        assert r["squeeze_ratio"] is None or r["squeeze_ratio"] >= 1.0


def test_NEGATIVE_squeeze_series_on_a_short_frame_is_None():
    assert K.squeeze_series(frame([100 + i for i in range(20)])) is None


def test_NEGATIVE_the_ratio_is_None_in_the_warm_up_not_a_guess():
    df = wild_then_coiled()
    ser = K.squeeze_series(df)
    assert ser["ratio"][0] is None
    assert not ser["on"][0]


# ------------------------------------------------------- board wiring (tiles)
def test_flat_KC_lines_are_DROPPED_once_the_channel_is_a_curve():
    """CRDO Support tile, studies on: curves AND three flat lines, two 'KC
    upper 223.51' labels. The 2026-09-13 curve fix left the lines behind."""
    from chart_maps import board as B
    df = wild_then_coiled()
    with_lines = B._study_overlays(df, 60)
    without = B._study_overlays(df, 60, keltner_lines=False)
    assert any(l["tone"] == "keltner" for l in with_lines["lines"])
    assert not any(l["tone"] == "keltner" for l in without["lines"])
    # AMD/fib/meanrev are untouched by the flag.
    assert [l for l in with_lines["lines"] if l["tone"] != "keltner"] == \
           [l for l in without["lines"] if l["tone"] != "keltner"]


def test_attach_studies_sends_the_curve_and_NOT_the_flat_lines(monkeypatch):
    from chart_maps import board as B
    from sepa import prices
    df = wild_then_coiled()
    monkeypatch.setattr(prices, "load_prices", lambda *a, **k: df)
    bars = B._frame_to_bars(df.tail(40))
    out = {"tiles": [{"symbol": "XYZ", "bars": bars, "bands": [], "lines": []}]}
    B._attach_studies(out, 40)
    t = out["tiles"][0]
    assert any(c["tone"] == "keltner" for c in t["curves"])
    assert not any(l.get("tone") == "keltner" for l in t["lines"]), \
        "the flat lines duplicate the curve and its label"
    assert isinstance(t.get("markers"), list)


def test_squeeze_dots_ride_with_the_curve_aligned_by_date():
    from chart_maps import board as B
    df = wild_then_coiled()
    bars = B._frame_to_bars(df.tail(30))
    tile = {"symbol": "XYZ", "bars": bars}
    B._keltner_curves(tile, df)
    dots = [m for m in tile.get("markers") or [] if m["kind"] == B.SQUEEZE_MARKER_KIND]
    ser = K.squeeze_series(df)
    on = {d for d, v in zip(ser["dates"], ser["on"]) if v}
    drawn = {b["t"] for b in bars}
    assert {m["date"] for m in dots} == (on & drawn)


def test_NEGATIVE_a_tile_with_no_bars_gets_no_dots_and_no_crash():
    from chart_maps import board as B
    tile = {"symbol": "XYZ", "bars": []}
    B._keltner_curves(tile, wild_then_coiled())
    assert "markers" not in tile


def test_the_AMD_board_marks_the_bars_from_the_STORED_dates(monkeypatch):
    """No second frame read on the request path: the nightly row carries the
    dates, and the tile marks A / M from them."""
    from chart_maps import board as B
    from supply_demand import turning_bullish as TBm
    df = base_and_raid([100.2])
    v = TBm.amd_verdict(df)
    row = {"symbol": "XYZ", "last_close": 100.2, "amd": v, "amd_grade": v["grade"]}
    monkeypatch.setattr(TBm, "board", lambda kind, limit=120, db=None: {
        "kind": "amd", "rows": [row], "n": 1, "n_all": 1, "capped": False,
        "n_scanned": 1, "n_rows": 1, "counts": {}, "built_at": None, "params": {}})
    monkeypatch.setattr(B, "bars_for", lambda sym, days=130, **k: B._frame_to_bars(df))
    out = B.turning_bullish_tiles("amd", limit=5)
    t = out["tiles"][0]
    kinds = {m["kind"]: m["date"] for m in t["markers"]}
    assert kinds["amd_a"] == v["base_date"] and kinds["amd_m"] == v["raid_date"]
    assert "amd_x" not in kinds
    assert any("× vol" in l["label"] for l in t["lines"])


# ------------------------------------------------------- zones: touch dates
def zone_frame():
    rng = np.random.default_rng(11)
    c = list(100 + np.cumsum(rng.normal(0, 1.2, 120)))
    return frame(c, index=dated(len(c)))


def test_every_band_carries_the_DATES_of_the_swings_that_made_it():
    df = zone_frame()
    z = PZ.compute(df)
    for band in z["supply_zones"] + z["demand_zones"]:
        assert len(band["touch_dates"]) == band["touches"]
        for d in band["touch_dates"]:
            assert d in {ts.strftime("%Y-%m-%d") for ts in df.index}


def test_NEGATIVE_a_frame_without_dates_reports_None_never_an_invented_date():
    df = zone_frame().reset_index(drop=True)
    z = PZ.compute(df)
    assert all(b["touch_dates"] is None for b in z["supply_zones"] + z["demand_zones"])


def test_touch_dates_respect_the_zoom_because_they_come_from_the_sliced_frame():
    df = zone_frame()
    z = PZ.compute(df, lookback_bars=40)
    cut = {ts.strftime("%Y-%m-%d") for ts in df.index[-40:]}
    for band in z["supply_zones"] + z["demand_zones"]:
        assert set(band["touch_dates"]) <= cut


def test_the_support_tile_marks_the_touches_and_labels_tested_bands():
    from chart_maps import support as S
    lv_sup = {"lo": 90.0, "hi": 91.0, "origin": "demand", "touches": 3,
              "tested": True, "touch_dates": ["2026-02-02", "2026-03-03", "2026-04-04"]}
    lv_lid = {"lo": 110.0, "hi": 111.0, "origin": "supply", "touches": 1,
              "tested": False, "touch_dates": ["2026-05-05"]}
    lv_flip = {"lo": 95.0, "hi": 96.0, "origin": "supply", "touches": 2,
               "tested": True, "touch_dates": ["2026-01-06", "2026-02-02"]}
    levels = {"standing_in": None, "supports": [lv_sup, lv_flip], "overhead": [lv_lid]}
    bands = S._bands(levels)
    assert bands[0]["label"] == "3× tested"
    assert "label" not in bands[2]                  # a single swing keeps its box name
    mk = S._touch_markers(levels)
    assert {(m["date"], m["kind"]) for m in mk} == {
        ("2026-02-02", "touch_d"), ("2026-03-03", "touch_d"), ("2026-04-04", "touch_d"),
        ("2026-01-06", "touch_s"), ("2026-02-02", "touch_s"),   # a broken lid: swing HIGHS
        ("2026-05-05", "touch_s")}


def test_NEGATIVE_touch_markers_are_bounded_and_survive_missing_dates():
    from chart_maps import support as S
    many = {"lo": 1, "hi": 2, "origin": "demand", "touches": 99, "tested": True,
            "touch_dates": ["2026-01-%02d" % (i % 28 + 1) + str(i) for i in range(200)]}
    assert len(S._touch_markers({"supports": [many]})) == S.MAX_TOUCH_MARKERS
    assert S._touch_markers({"supports": [{"lo": 1, "hi": 2, "touches": 2}]}) == []
    assert S._touch_markers({}) == []


# ------------------------------------------------ the partial bar (S1/S6/S7)
def _snap(date, o, h, l, c, v, trade_ts_ms=None):
    s = {"date": date, "open": o, "high": h, "low": l, "close": c, "volume": v}
    if trade_ts_ms is not None:
        s["last_trade_ts_ms"] = trade_ts_ms
        s["last_trade_price"] = c
    return s


def _ms(date, hhmm):
    import pandas as pd
    return int(pd.Timestamp(f"{date} {hhmm}", tz="America/New_York").timestamp() * 1000)


def _frame_through(dates, closes):
    import pandas as pd
    idx = pd.DatetimeIndex([pd.Timestamp(f"{d} 04:00:00") for d in dates])
    return pd.DataFrame({"open": closes, "high": [c + 1 for c in closes],
                         "low": [c - 1 for c in closes], "close": closes,
                         "volume": [1_000_000.0] * len(closes)}, index=idx)


def test_an_RTH_print_on_a_day_the_cache_already_holds_is_PARTIAL_and_refreshed():
    """The hourly cache patch puts today's in-progress bar in the frame from
    ~10:00 ET. `snap_date <= last_date` then returned the frame untouched:
    the partial bar read as closed structure and the verdict was priced off
    a bar up to an hour stale (NVDA: 'into supply +1.4%' at 210.96 while the
    tape was 216.50 inside the band)."""
    from sepa import prices
    days = ["2026-09-10", "2026-09-11", "2026-09-14"]
    df = _frame_through(days, [100.0, 101.0, 101.5])        # 09-14 = 10:00 patch
    snap = _snap("2026-09-14", 101.0, 104.0, 100.5, 103.7, 2_000_000.0,
                 trade_ts_ms=_ms("2026-09-14", "13:00"))
    out, info = prices.with_today_bar(df, "NVDA", snap=snap)
    assert info["partial"] is True and info["adjusted"] is True
    assert info["session"] == "rth" and info["source"] == "rth_refresh"
    assert info["last_price"] == 103.7
    assert float(out["close"].iloc[-1]) == 103.7 and float(out["high"].iloc[-1]) == 104.0
    assert float(df["close"].iloc[-1]) == 101.5, "the cache's own frame is untouched"


def test_NEGATIVE_an_after_hours_print_on_a_held_day_is_NOT_partial():
    """After the close the day bar is complete; the AH print widens the
    returned copy (2026-09-08 rule) and structure may read the whole frame."""
    from sepa import prices
    days = ["2026-09-10", "2026-09-11", "2026-09-14"]
    df = _frame_through(days, [100.0, 101.0, 101.5])
    snap = _snap("2026-09-14", 101.0, 102.0, 100.5, 101.5, 2_000_000.0,
                 trade_ts_ms=_ms("2026-09-14", "17:30"))
    snap["last_trade_price"] = 102.4
    out, info = prices.with_today_bar(df, "NVDA", snap=snap)
    assert info["adjusted"] is True and info["partial"] is False
    assert info["session"] == "afterhours"


def test_an_APPENDED_rth_bar_is_partial_and_an_appended_afterhours_bar_is_not():
    from sepa import prices
    days = ["2026-09-10", "2026-09-11"]
    df = _frame_through(days, [100.0, 101.0])
    rth = _snap("2026-09-14", 101.0, 104.0, 100.5, 103.7, 2_000_000.0,
                trade_ts_ms=_ms("2026-09-14", "11:00"))
    out, info = prices.with_today_bar(df, "NVDA", snap=rth)
    assert info["appended"] is True and info["partial"] is True
    ah = _snap("2026-09-14", 101.0, 104.0, 100.5, 103.7, 2_000_000.0,
               trade_ts_ms=_ms("2026-09-14", "16:45"))
    ah["last_trade_price"] = 103.9
    out, info = prices.with_today_bar(df, "NVDA", snap=ah)
    assert info["appended"] is True and info["partial"] is False


def test_support_reads_structure_WITHOUT_the_partial_row(monkeypatch):
    from chart_maps import support as S
    from sepa import prices
    df = _frame_through(["2026-09-10", "2026-09-11", "2026-09-14"], [100.0, 101.0, 101.5])
    refreshed = df.copy()
    refreshed.iloc[-1, refreshed.columns.get_loc("close")] = 103.7
    monkeypatch.setattr(prices, "load_prices", lambda *a, **k: df)
    monkeypatch.setattr(prices, "with_today_bar",
                        lambda frame, sym, snap=None: (refreshed, {
                            "appended": False, "adjusted": True, "partial": True,
                            "as_of_epoch": 1.0, "source": "rth_refresh", "session": "rth"}))
    got, have, as_of, closed = S._frame_for("NVDA", 3, with_closed=True)
    assert have == 3 and float(got["close"].iloc[-1]) == 103.7
    assert len(closed) == 2 and str(closed.index[-1])[:10] == "2026-09-11"


def test_NEGATIVE_support_keeps_the_whole_frame_when_nothing_is_partial(monkeypatch):
    from chart_maps import support as S
    from sepa import prices
    df = _frame_through(["2026-09-10", "2026-09-11", "2026-09-14"], [100.0, 101.0, 101.5])
    monkeypatch.setattr(prices, "load_prices", lambda *a, **k: df)
    monkeypatch.setattr(prices, "with_today_bar",
                        lambda frame, sym, snap=None: (frame, {"appended": False, "adjusted": False,
                                                              "partial": False}))
    got, have, as_of, closed = S._frame_for("NVDA", 3, with_closed=True)
    assert len(closed) == 3


def test_price_zones_drops_the_partial_row_from_structure(monkeypatch):
    from supply_demand import price_zones as PZm
    from sepa import prices
    rng = np.random.default_rng(2)
    c = list(100 + np.cumsum(rng.normal(0, 1.0, 80)))
    idx = pd.bdate_range("2026-05-01", periods=80)
    df = pd.DataFrame({"open": c, "high": [x + 1 for x in c], "low": [x - 1 for x in c],
                       "close": c, "volume": [1e6] * 80}, index=idx)
    seen = {}
    real_compute = PZm.compute

    def spy(frame, *a, **k):
        seen["n"] = len(frame)
        return real_compute(frame, *a, **k)
    monkeypatch.setattr(PZm, "compute", spy)
    monkeypatch.setattr(prices, "load_prices", lambda *a, **k: df)
    monkeypatch.setattr(prices, "with_today_bar",
                        lambda frame, sym, snap=None: (frame, {
                            "appended": False, "adjusted": True, "partial": True,
                            "last_price": float(frame["close"].iloc[-1]) + 3.0}))
    out = PZm.for_symbol("XYZ")
    assert seen["n"] == 79, "the in-progress last row is not structure"
    assert out["last_price"] == pytest.approx(float(df["close"].iloc[-1]) + 3.0, abs=0.01)


def test_the_standing_in_box_is_SUPPLY_when_its_origin_is_supply():
    from chart_maps import support as S
    lv = {"lo": 330.81, "hi": 334.99, "origin": "supply", "touches": 2, "tested": True}
    b = S._bands({"standing_in": lv, "supports": [], "overhead": []})
    assert b[0]["kind"] == "supply" and "in supply" in b[0]["label"]
    lv["origin"] = "demand"
    b = S._bands({"standing_in": lv, "supports": [], "overhead": []})
    assert b[0]["kind"] == "demand" and b[0]["label"].startswith("here")


def test_SMC_and_the_pattern_scan_read_CLOSED_bars_in_the_support_source():
    import inspect
    from chart_maps import support as S
    src = inspect.getsource(S.for_symbol)
    for call in ("find_setups(", "liquidity_sweeps(", "structure_breaks(", "order_blocks("):
        i = src.index(call)
        assert src[i:i + 60].split(call)[1].startswith("closed.tail"), call
    i = src.index("pat_tf.scan(")
    assert "df=closed.tail" in src[i:i + 120]
    assert "with_closed=True" in inspect.getsource(S.overlay_for_symbol)


def test_the_support_endpoint_passes_the_bars_it_actually_used():
    """`bars`/`days` do not exist on the payload; `bars_used` does. With 0
    the zoom cut never ran and the 'mean of the visible window' was a
    2-year fit drawn over a 1-month chart, identical at every zoom."""
    import inspect
    from chart_maps import api as A
    src = inspect.getsource(A.chart_maps_support)
    assert "bars_used" in src
    assert 'res.get("timeframe") not in (None, "daily")' in src


# ------------------------------------------------ AMD failed: the age-out
# 2026-09-14, second pass. Adding the failed phase with no bar limit made a
# base that died months ago keep winning over a fresher base that had not
# raided yet: 699 of 2,673 names read "base failed · Nd ago" over a live
# base (330 of them 31-90 sessions old). A base that forms ENTIRELY after
# the failure bar is the live read; the dead one is history.

def _tight(level: float, n: int):
    return [level + (i % 3) * 0.2 for i in range(n)]


def test_a_base_that_forms_AFTER_the_failure_is_the_live_read():
    """Raid, failure, then a gap down and ten tight bars well below the dead
    base. The verdict must read the NEW base as basing, not the old one as
    failed."""
    df = base_and_raid([100.2, 98.0] + _tight(93.0, 10))
    cyc = A.find_cycle(df)
    assert cyc["phase"] == "accumulation"
    assert cyc["manipulation"] is None and cyc["failure"] is None
    assert cyc["accumulation"]["start"] > 22        # 22 = the failure bar
    assert cyc["accumulation"]["lo"] < 95            # the new base, not 99.5
    v = TB.amd_verdict(df)
    assert v["grade"] == "basing" and v["turning"] is False


def test_NEGATIVE_a_base_that_SPANS_the_breakdown_does_not_bury_the_failure():
    """The tight bars sit right under the failure close, so the widest tight
    window ending today starts ON the failure bar. That is not a base that
    formed after the failure — the failure stays the read."""
    df = base_and_raid([100.2, 98.0] + _tight(97.4, 9))
    cyc = A.find_cycle(df)
    assert cyc["phase"] == "failed"
    assert cyc["failure"]["close"] == 98.0


def test_NEGATIVE_a_COMPLETED_cycle_still_wins_over_a_bare_base():
    """Unchanged from 2026-09-13: a markup followed by a fresh base on top is
    still the completed cycle. Only a FAILED cycle yields."""
    df = base_and_raid([101.8, 103.0, 106.0, 109.0] + _tight(112.0, 10))
    cyc = A.find_cycle(df)
    assert cyc["phase"] == "distribution"


def test_NEGATIVE_a_fresh_failure_with_no_base_after_it_is_still_failed():
    df = base_and_raid([100.2, 98.0, 97.0, 96.5])
    assert A.find_cycle(df)["phase"] == "failed"


# ------------------------------------------------ the studies' contracts
# Parsed as TEXT, never imported: the Keltner script runs its whole study at
# import (it is written to be piped into `python -`), and the AMD one puts
# /app on sys.path. A test that imports either walks 3,700 names.
def _study_src(name: str) -> str:
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return open(os.path.join(here, "scripts", name)).read()


def _top_level_literal(src: str, name: str):
    import ast
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("no top-level %s" % name)


def test_the_AMD_study_codes_EVERY_phase_the_detector_can_return():
    """A phase the walk's table does not know would fold into 'no cycle' and
    put its bars into every placebo — which is exactly how the 2026-09-13
    numbers would have gone stale silently once `failed` existed."""
    codes = _top_level_literal(_study_src("turning_bullish_amd_study.py"), "PHASE_CODE")
    assert set(codes) == set(A.PHASES)
    assert len(set(codes.values())) == len(A.PHASES)
    assert -1 not in codes.values()                   # -1 is 'no cycle'


def test_BOTH_studies_walk_the_SAME_universe_and_it_is_the_wide_one():
    """Ajay 2026-09-14: 'there should be more names, about 4k is what we
    discussed' — the scan's `full` alias unioned with the cron's `broad`."""
    for name in ("turning_bullish_amd_study.py", "turning_bullish_keltner_study.py"):
        src = _study_src(name)
        assert _top_level_literal(src, "UNIVERSE_MODES") == ("full", "broad"), name
        assert "def study_universe" in src, name
        assert "syms = study_universe()" in src, name
        assert 'load_universe("full")' not in src and "load_universe()" not in src, name
