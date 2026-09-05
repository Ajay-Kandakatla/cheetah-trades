"""Behavioral tests for the on-demand price-structure zones (price_zones.py).

Configured price-structure method (NOT a book method) — these lock the geometry
+ the entry-read decision logic on a deterministic synthetic series. A clean
sawtooth between a support level (~100) and a resistance level (~120) gives a
known demand band ~100 and supply band ~120; we then probe the verdict at several
price positions via the `last_price` override.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from supply_demand import price_zones as pz


def _sawtooth(low=100.0, high=120.0, leg=12, cycles=7):
    """Repeating low→high→low ramp so swing highs cluster at `high`, lows at `low`."""
    seq = []
    for _ in range(cycles):
        seq += list(np.linspace(low, high, leg, endpoint=False))
        seq += list(np.linspace(high, low, leg, endpoint=False))
    c = pd.Series(seq, dtype=float)
    return pd.DataFrame({"open": c, "high": c, "low": c, "close": c,
                         "volume": pd.Series(np.ones(len(c)) * 1_000_000)})


SAW = _sawtooth()


def test_zones_are_found_at_the_swing_levels():
    out = pz.compute(SAW, last_price=110.0)
    assert out is not None
    # A supply band near 120 and a demand band near 100 must exist.
    assert any(abs(z["mid"] - 120) <= 2 for z in out["supply_zones"]), out["supply_zones"]
    assert any(abs(z["mid"] - 100) <= 2 for z in out["demand_zones"]), out["demand_zones"]


def test_into_supply_when_resistance_just_above():
    out = pz.compute(SAW, last_price=118.0)          # ~1.7% below the 120 band
    assert out["verdict"]["state"] == "INTO_SUPPLY"
    assert out["verdict"]["entry_read"] == "caution"


def test_clear_runway_with_support_below():
    out = pz.compute(SAW, last_price=101.0)          # just above the 100 support, runway up
    assert out["verdict"]["state"] in ("CLEAR_RUNWAY", "AT_DEMAND")
    assert out["verdict"]["entry_read"] == "favorable"


def test_mid_range_between_bands():
    out = pz.compute(SAW, last_price=110.0)          # dead center, ~9% from each band
    assert out["verdict"]["state"] == "MID_RANGE"
    assert out["verdict"]["entry_read"] == "neutral"


def test_extended_no_support_above_all_bands():
    # Price well above every band → no overhead, no nearby support → extended.
    out = pz.compute(SAW, last_price=140.0)
    assert out["verdict"]["state"] == "EXTENDED_NO_SUPPORT"
    assert out["verdict"]["entry_read"] == "caution"
    assert out["nearest_resistance"] is None


def test_disclaimer_and_params_present():
    out = pz.compute(SAW, last_price=110.0)
    assert "not advice" in out["disclaimer"].lower()
    assert out["params"]["near_pct"] == pz.NEAR_PCT


def test_too_little_history_returns_none():
    short = _sawtooth(cycles=1).iloc[:30]
    assert pz.compute(short) is None


def test_resolution_is_reported_so_two_surfaces_cannot_look_contradictory():
    """Ajay 2026-08-14 spotted DTE showing different demand bands on the Tape
    tab (fine geometry) and Back in Demand (coarse). They are the same
    structure at two zoom levels, but nothing on screen said so."""
    import pandas as pd
    n = 260
    base = [100 + (i % 7) for i in range(n)]
    df = pd.DataFrame({
        "open": base, "close": base,
        "high": [b + 1.5 for b in base], "low": [b - 1.5 for b in base],
        "volume": [10_000] * n,
    })
    fine = pz.compute(df)
    coarse = pz.compute(df, merge_pct=4.0, half_width_pct=1.75, swing_window=5)
    assert fine["resolution"] == "fine"
    assert coarse["resolution"] == "swing"
    assert fine["params"]["merge_pct"] < coarse["params"]["merge_pct"]


# ── the lookback knob (2026-08-19, Support Levels tab) ────────────────────────
def test_the_default_lookback_is_unchanged_and_still_gated_at_60_bars():
    """Every pre-existing caller passes no window. If this floor moves, the
    /zones page, orderflow.signals and both backtests change silently."""
    assert pz.LOOKBACK_BARS == 252
    assert pz.MIN_BARS == 60
    assert pz.compute(SAW.iloc[:59]) is None
    assert pz.compute(SAW.iloc[:60]) is not None


def test_a_short_window_is_reachable_only_when_it_is_ASKED_for():
    """21 bars cannot clear the 60-bar default gate — that is the point of the
    gate. Passing `lookback_bars` is the explicit request that relaxes it."""
    frame = SAW.iloc[:40]
    assert pz.compute(frame.iloc[:21]) is None                   # default floor
    out = pz.compute(SAW, lookback_bars=21, swing_window=2)      # asked for
    assert out is not None
    assert out["params"]["lookback"] == 21


def test_a_frame_below_the_absolute_floor_returns_None_at_any_window():
    assert pz.compute(SAW.iloc[:8], lookback_bars=21, swing_window=2) is None


def _vees(low, high, leg, cycles):
    """A V-repeating series whose local minima land at `low`. Unlike SAW this is
    built per-test so the exact bar count is known, which is what the floor
    tests need."""
    seq = []
    for _ in range(cycles):
        seq += list(np.linspace(high, low, leg, endpoint=False))
        seq += list(np.linspace(low, high, leg, endpoint=False))
    c = pd.Series(seq, dtype=float)
    return pd.DataFrame({"open": c, "high": c, "low": c, "close": c,
                         "volume": pd.Series(np.ones(len(c)) * 1_000_000)})


def test_the_floor_scales_with_the_swing_window():
    """`_local_extrema` scans range(w, n-w) and compares w bars either side, so
    a frame of 2w+2 has nowhere to put a swing at all. A fixed floor would let a
    wide swing window through to return an empty band list instead of None."""
    frame = _vees(100.0, 110.0, 4, 20)                 # a swing every 4 bars
    assert pz.compute(frame, lookback_bars=12, swing_window=5) is None   # 2*5+3=13
    assert pz.compute(frame, lookback_bars=13, swing_window=5) is not None


def test_the_window_actually_narrows_what_is_seen():
    """The whole feature: a short read must not report structure that only
    exists further back than it looked."""
    old = list(np.linspace(90.0, 80.0, 10)) + list(np.linspace(80.0, 90.0, 10))
    recent = ([100.0, 104.0] * 5) + list(np.linspace(104.0, 100.0, 5)) \
        + list(np.linspace(100.0, 106.0, 10))
    c = pd.Series(([95.0] * 40) + (old * 4) + recent, dtype=float)
    df = pd.DataFrame({"open": c, "high": c, "low": c, "close": c,
                       "volume": pd.Series(np.ones(len(c)) * 1_000_000)})

    wide = pz.compute(df, lookback_bars=252, swing_window=2)
    narrow = pz.compute(df, lookback_bars=21, swing_window=2)
    assert wide["params"]["lookback"] == 252
    assert narrow["params"]["lookback"] == 21

    # The 80 floor is 80+ bars back. The wide read must find it; the narrow one
    # must not be able to see it at all.
    assert any(z["mid"] < 85 for z in wide["demand_zones"]), wide["demand_zones"]
    assert not any(z["mid"] < 85 for z in narrow["demand_zones"]), \
        f"a 21-bar read reported a band from 80+ bars back: {narrow['demand_zones']}"


def test_the_lookback_is_a_per_call_argument_and_never_a_global_mutation():
    before = (pz.LOOKBACK_BARS, pz.SWING_WINDOW, pz.MIN_BARS, pz.MIN_BARS_ABS)
    pz.compute(SAW, lookback_bars=21, swing_window=2)
    assert (pz.LOOKBACK_BARS, pz.SWING_WINDOW, pz.MIN_BARS,
            pz.MIN_BARS_ABS) == before


def test_params_report_the_EFFECTIVE_window_not_the_module_default():
    """The payload is what the Support tab labels its chart with. Reporting 252
    while reading 63 would put the wrong zoom on screen."""
    for lb in (21, 63, 126, 252):
        out = pz.compute(SAW, lookback_bars=lb, swing_window=2)
        assert out["params"]["lookback"] == lb


def _staircase(n_peaks=8, base=100.0, step=1.05, leg=12):
    """n distinct swing highs at rising levels (each >3% apart so they never
    merge), price finishing back at the base: every peak is overhead."""
    closes = []
    for k in range(n_peaks):
        peak = base * (step ** k)
        closes += list(np.linspace(base, peak, leg, endpoint=False))
        closes += list(np.linspace(peak, base, leg, endpoint=False))
    closes = np.array(closes + [base])
    idx = pd.bdate_range("2025-01-02", periods=len(closes))
    return pd.DataFrame({"open": closes, "high": closes * 1.002, "low": closes * 0.998,
                         "close": closes, "volume": np.full(len(closes), 1e6)}, index=idx)


def test_surfaced_bands_are_the_nearest_not_the_strongest():
    """2026-09-02: every consumer asks 'what is nearest / what am I in', so the
    N surfaced bands per side are cut by distance from price. The first band
    overhead and the band price stands in can never be dropped again."""
    df = _staircase()
    live = 100.0
    out = pz.compute(df, last_price=live)
    every = pz.compute(df, last_price=live, max_zones=None)
    assert out and every
    sup, all_sup = out["supply_zones"], every["supply_zones"]
    assert len(sup) <= pz.MAX_ZONES_PER_SIDE < len(all_sup)
    nearest_all = min((z for z in all_sup if z["hi"] >= live), key=lambda z: z["lo"])
    assert any(abs(z["lo"] - nearest_all["lo"]) < 1e-9 for z in sup)          # first band overhead is surfaced
    dists = sorted(pz.band_distance(z, live) for z in all_sup)[:len(sup)]
    assert sorted(pz.band_distance(z, live) for z in sup) == dists           # exactly the N nearest
    assert [z["mid"] for z in sup] == sorted((z["mid"] for z in sup), reverse=True)   # still high -> low
    # a band price is standing in is always kept, whatever its strength
    inside_px = (all_sup[-1]["lo"] + all_sup[-1]["hi"]) / 2
    kept = pz.compute(df, last_price=inside_px)["supply_zones"]
    assert any(z["lo"] <= inside_px <= z["hi"] for z in kept)
    # the engine's own nearest_resistance agrees with the surfaced list
    nr = pz.compute(df, last_price=live)["nearest_resistance"]
    assert nr and any(abs(z["lo"] - nr["lo"]) < 1e-9 for z in sup)


def test_band_distance_and_nearest_first():
    z_in, z_up, z_dn = {"lo": 99, "hi": 101, "strength": 1}, {"lo": 110, "hi": 112, "strength": 90}, {"lo": 90, "hi": 92, "strength": 5}
    assert pz.band_distance(z_in, 100) == 0.0
    assert pz.band_distance(z_up, 100) == 10 and pz.band_distance(z_dn, 100) == 8
    assert [z["lo"] for z in pz.nearest_first([z_up, z_dn, z_in], 100)] == [99, 90, 110]
    tie_a, tie_b = {"lo": 110, "hi": 112, "strength": 10}, {"lo": 110, "hi": 112, "strength": 80}
    assert pz.nearest_first([tie_a, tie_b], 100)[0] is tie_b                  # ties -> stronger first


# ── engine fixes 2026-09-05 (Ajay: "yes please fix the bugs") ─────────────────
def _two_level_frame(hi_a=110.0, hi_b=130.0, lo_a=80.0, lo_b=70.0, n=80):
    """80 bars of a 90–100 range with two isolated swing highs (bars 20/40) and
    two isolated swing lows (bars 20/40): four single-swing bands, so nearest
    support/resistance and the containing band are all different objects."""
    h = np.full(n, 100.0); l = np.full(n, 90.0)
    h[20], h[40] = hi_a, hi_b
    l[20], l[40] = lo_a, lo_b
    c = (h + l) / 2
    return pd.DataFrame({"open": c, "high": h, "low": l, "close": c,
                         "volume": np.full(n, 1e6)})


def _dist_pct(px, band, side):
    if band is None:
        return None
    return (round((band["lo"] - px) / px * 100, 1) if side == "res"
            else round((px - band["hi"]) / px * 100, 1))


def test_at_demand_support_pct_is_the_distance_to_nearest_support_not_zero():
    """The /zones page prints `nearest_support lo–hi (−support_pct%)` as ONE
    statement, so the pair must describe the same band. AT_DEMAND used to
    force 0.0 next to the NEXT band below (12% away)."""
    out = pz.compute(_two_level_frame(), last_price=80.0)
    v, ns = out["verdict"], out["nearest_support"]
    assert v["state"] == "AT_DEMAND"
    assert ns is not None and ns["hi"] < 80.0, "nearest_support is the band BELOW price"
    assert v["support_pct"] == _dist_pct(80.0, ns, "sup")
    assert v["support_pct"] > 0
    # the AT_SUPPLY side was already honest; it stays that way
    out2 = pz.compute(_two_level_frame(), last_price=110.0)
    v2, nr = out2["verdict"], out2["nearest_resistance"]
    assert v2["state"] == "AT_SUPPLY"
    assert v2["resistance_pct"] == _dist_pct(110.0, nr, "res") and v2["resistance_pct"] > 0


def test_support_and_resistance_pct_describe_the_nearest_band_in_every_state():
    """Both sides symmetric: pct == distance to the band the payload names;
    0.0 only if that band contained the price (it never does — nearest_*
    are strictly outside the price by construction)."""
    frame = _two_level_frame()
    seen = set()
    for px in (60.0, 70.0, 75.0, 80.0, 85.0, 95.0, 101.0, 108.0, 110.0, 120.0, 128.0,
               130.0, 150.0):
        out = pz.compute(frame, last_price=px)
        v, ns, nr = out["verdict"], out["nearest_support"], out["nearest_resistance"]
        seen.add(v["state"])
        assert v["support_pct"] == _dist_pct(px, ns, "sup"), (px, v, ns)
        assert v["resistance_pct"] == _dist_pct(px, nr, "res"), (px, v, nr)
        for band, pct in ((ns, v["support_pct"]), (nr, v["resistance_pct"])):
            if band is not None:
                assert (pct == 0.0) == (band["lo"] <= px <= band["hi"])
    assert {"AT_DEMAND", "AT_SUPPLY", "INTO_SUPPLY", "MID_RANGE",
            "EXTENDED_NO_SUPPORT"} <= seen, seen


def test_a_degenerate_multi_touch_cluster_gets_the_single_swing_width():
    """Two swing highs a fraction of a cent apart used to make a 2-touch band of
    ZERO width after 2dp rounding (1.2001/1.2004 -> 1.20–1.20), which killed
    its trade_levels. The single-swing half-width applies whenever the span
    rounds below one tick."""
    df = _two_level_frame()
    z = pz._make_zone(df, [(100.001, 20), (100.004, 30)], "supply")
    hw = round(100.0025 * pz.ZONE_HALF_WIDTH_PCT / 100.0, 2)
    assert z["touches"] == 2
    assert z["hi"] - z["lo"] >= 2 * hw - 0.02, z
    assert z["lo"] < 100.001 and z["hi"] > 100.004
    # end to end: the sub-$2 repro from the review
    h = df["high"].values.copy(); h[:] = 1.0; h[20], h[30] = 1.2001, 1.2004
    small = df.assign(high=h, low=0.9, close=0.95, open=0.95)
    out = pz.compute(small, last_price=0.95)
    band = next(b for b in out["supply_zones"] if b["touches"] == 2)
    assert band["hi"] > band["lo"]
    from supply_demand import patterns as pat
    assert pat.trade_levels(band, 0.95, 0.02) is not None


def test_a_real_span_multi_touch_cluster_is_NOT_widened():
    """Only the degenerate case is fixed. Widening every multi-touch band would
    reshape every board and needs a re-measure first."""
    df = _two_level_frame()
    z = pz._make_zone(df, [(100.0, 20), (101.5, 30)], "supply")
    assert (z["lo"], z["hi"], z["touches"]) == (100.0, 101.5, 2)
    one_tick = pz._make_zone(df, [(110.0, 20), (110.01, 30)], "supply")
    assert (one_tick["lo"], one_tick["hi"]) == (110.0, 110.01), "a one-tick span is a real span"


def _closed_with_displacement(n=80, last="2026-09-02"):
    """Wavy closed frame whose LAST bar is a displacement bar (h105 / l100.5)."""
    import math
    idx = pd.bdate_range(end=pd.Timestamp(last), periods=n) + pd.Timedelta(hours=4)
    c = [100.0 + math.sin(i / 3.0) * 0.8 for i in range(n)]
    h = [x + 0.5 for x in c]; l = [x - 0.5 for x in c]
    h[-1], l[-1], c[-1] = 105.0, 100.5, 104.8
    return pd.DataFrame({"open": c, "high": h, "low": l, "close": c,
                         "volume": [1e6] * n}, index=idx)


LIVE_SNAP = {"open": 105.6, "high": 106.0, "low": 105.5, "close": 105.8,
             "volume": 2.5e6, "date": "2026-09-03 00:00:00",
             "last_trade_ts_ms": 1788455521222}


def test_for_symbol_daily_structure_comes_from_the_closed_frame_only(monkeypatch):
    """A displacement bar + a LIVE bar used to print a demand FVG whose top was
    the live bar's low-so-far — a three-bar imbalance whose third bar had not
    closed. Structure (swings, gaps, ATR, trade levels) now reads the CLOSED
    frame; the live bar supplies only the price the verdict is read at."""
    from sepa import prices as P
    from supply_demand import patterns as pat
    closed = _closed_with_displacement()
    monkeypatch.setattr(P, "load_prices", lambda sym, *a, **k: closed.copy())
    monkeypatch.setattr(P, "bulk_snapshot", lambda syms: {"ACME": LIVE_SNAP})
    monkeypatch.setattr(pat, "opening_range", lambda *a, **k: None)
    out = pz.for_symbol("ACME")
    assert out.get("error") is None, out
    assert out["live_bar"]["appended"] is True
    assert out["last_price"] == 105.8, "the verdict still reads the live price"
    assert not any(abs(g["hi"] - 105.5) < 1e-9 for g in out["fair_value_gaps"]), \
        out["fair_value_gaps"]
    assert out["fair_value_gaps"] == pat.fair_value_gaps(closed, 105.8)
    assert out["atr"] == round(pat.atr(closed), 4)
    # bars_since_test counts CLOSED bars: the live bar is not a session
    ref = pz.compute(closed, last_price=105.8)
    assert out["supply_zones"] == ref["supply_zones"]
    assert out["demand_zones"] == ref["demand_zones"]
    assert out["verdict"] == ref["verdict"]


def test_for_symbol_intraday_excludes_the_partial_last_bucket(monkeypatch):
    """Same rule on the intraday path: `frame_for` flags an in-progress last
    bucket and for_symbol keeps it out of the structure."""
    import math
    from supply_demand import patterns as pat
    from supply_demand import timeframes as TF
    n = 60
    idx = pd.date_range("2026-09-03 13:45", periods=n, freq="15min", tz="UTC")
    c = [50.0 + math.sin(i / 3.0) * 0.4 for i in range(n)]
    h = [x + 0.25 for x in c]; l = [x - 0.25 for x in c]
    h[-2], l[-2], c[-2] = 52.5, 50.3, 52.4          # displacement bar (closed)
    h[-1], l[-1], c[-1] = 52.9, 52.7, 52.8          # in-progress bucket
    df = pd.DataFrame({"open": c, "high": h, "low": l, "close": c,
                       "volume": [1e5] * n}, index=idx)
    meta = {"tf": TF.M15, "label": "15 min", "span": "x", "bars": n, "available": True,
            "source": "test", "as_of": "2026-09-04 04:37:00+00:00", "swing_window": 2,
            "reason": None, "partial": True}
    monkeypatch.setattr(TF, "frame_for", lambda *a, **k: (df.copy(), meta))
    monkeypatch.setattr(pat, "opening_range", lambda *a, **k: None)
    out = pz.for_symbol("ACME", tf="15m")
    assert out.get("error") is None, out
    assert out["last_price"] == 52.8
    assert out["timeframe_meta"]["partial"] is True
    assert not any(abs(g["hi"] - 52.7) < 1e-9 for g in out["fair_value_gaps"]), \
        out["fair_value_gaps"]
    closed = df.iloc[:-1]
    assert out["fair_value_gaps"] == pat.fair_value_gaps(closed, 52.8)
    assert out["atr"] == round(pat.atr(closed), 4)
    assert out["params"]["lookback"] == n - 1
    # a frame whose last bucket is CLOSED is read whole
    monkeypatch.setattr(TF, "frame_for", lambda *a, **k: (df.copy(), {**meta, "partial": False}))
    whole = pz.for_symbol("ACME", tf="15m")
    assert whole["params"]["lookback"] == n
