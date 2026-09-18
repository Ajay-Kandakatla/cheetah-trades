"""Behavioural tests for the Support Levels tab (chart_maps/support.py).

The claim the tab makes is that the ZOOM changes the answer — that "support
over 1 month" and "support over 1 year" are different numbers and both are
true. So the fixture is built to have TWO floors at different depths, one
inside the last month and one only visible over half a year, and the tests
assert each window finds its own and not the other's.

Everything is synthetic and deterministic. `price_zones` is a configured
price-structure read, NOT a book method, so nothing here cites a page — and the
contract test at the bottom pins that this module never mutates its globals.
"""
from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest

from chart_maps import support as S
from supply_demand import price_zones as pz


# ── fixture: two floors at two depths ─────────────────────────────────────────
def _saw(low: float, high: float, leg: int, cycles: int) -> list[float]:
    seq: list[float] = []
    for _ in range(cycles):
        seq += list(np.linspace(low, high, leg, endpoint=False))
        seq += list(np.linspace(high, low, leg, endpoint=False))
    return seq


def _two_floor_frame() -> pd.DataFrame:
    """~150 bars: an OLD range that bottoms at 80, then a RECENT one at 100.

    A 1-month read can only see the 100 floor. A 6-month read sees both. That
    is the entire feature, expressed as data.
    """
    old = _saw(80.0, 92.0, 7, 8)            # 112 bars, floor 80
    recent = _saw(100.0, 108.0, 5, 4)       # 40 bars, floor 100
    c = pd.Series(old + recent, dtype=float)
    idx = pd.date_range("2026-01-02", periods=len(c), freq="B")
    return pd.DataFrame(
        {"open": c.values, "high": c.values, "low": c.values, "close": c.values,
         "volume": np.ones(len(c)) * 1_000_000},
        index=idx,
    )


FRAME = _two_floor_frame()


@pytest.fixture
def loaded(monkeypatch):
    """Point every price read at the synthetic frame."""
    from sepa import prices
    monkeypatch.setattr(prices, "load_prices",
                        lambda sym, *a, **k: FRAME.copy())
    return FRAME


# ── the dropdown ──────────────────────────────────────────────────────────────
def test_the_three_windows_Ajay_asked_for_are_all_offered():
    keys = S.window_keys()
    for asked in S.REQUESTED_WINDOWS:
        assert asked in keys, f"{asked} missing from the dropdown"


def test_windows_are_ordered_shortest_first_and_strictly_increasing():
    bars = [w["bars"] for w in S.SUPPORT_WINDOWS]
    assert bars == sorted(bars)
    assert len(set(bars)) == len(bars)


def test_the_default_window_is_one_of_the_offered_ones():
    assert S.DEFAULT_WINDOW in S.window_keys()


def test_an_unknown_window_falls_back_and_never_raises():
    for junk in ("", "  ", "10y", "monthly", None, 7, object()):
        assert S.parse_window(junk) == S.DEFAULT_WINDOW
    # "5y" graduated from junk to a real window on 2026-08-25 ("select
    # support level ... by up to 5 years") — it must parse, not fall back.
    assert S.parse_window("5y") == "5y"


def test_window_parsing_is_case_and_space_insensitive():
    assert S.parse_window("  6M ") == "6m"


def test_the_swing_window_scales_down_with_the_frame():
    """At the module default of 4 a swing must dominate 9 bars — 43% of a
    21-bar month. If someone flattens these back to a constant, the 1m option
    silently returns one band or none."""
    by_key = {w["key"]: w for w in S.SUPPORT_WINDOWS}
    assert by_key["1m"]["swing_window"] < by_key["6m"]["swing_window"]
    assert by_key["1m"]["swing_window"] >= 2      # w=1 makes every bar a swing


# ── the zoom actually changes the answer ──────────────────────────────────────
def test_a_one_month_read_finds_the_RECENT_floor_and_not_the_old_one(loaded):
    out = S.for_symbol("TEST", "1m")
    assert "error" not in out, out
    lows = [lv["lo"] for lv in out["supports"]] + \
           ([out["standing_in"]["lo"]] if out["standing_in"] else [])
    assert any(abs(x - 100.0) <= 3 for x in lows), lows
    assert not any(x < 92.0 for x in lows), f"1m reached back to the old floor: {lows}"


def test_a_six_month_read_reaches_the_DEEPER_floor(loaded):
    out = S.for_symbol("TEST", "6m")
    assert "error" not in out, out
    lows = [lv["lo"] for lv in out["supports"]]
    assert any(x < 92.0 for x in lows), \
        f"6m never reached the 80 floor that only it can see: {lows}"


def test_the_two_zooms_disagree_on_purpose(loaded):
    """The feature is worthless if every window returns the same list."""
    a = S.for_symbol("TEST", "1m")["supports"]
    b = S.for_symbol("TEST", "6m")["supports"]
    assert [x["lo"] for x in a] != [x["lo"] for x in b]


def test_the_window_that_was_asked_for_is_the_one_reported(loaded):
    out = S.for_symbol("TEST", "6m")
    assert out["window"] == "6m"
    assert out["params"]["lookback"] == 126


# ── levels: position, not origin, decides the column ──────────────────────────
def test_supports_are_below_price_and_overhead_is_above(loaded):
    out = S.for_symbol("TEST", "6m")
    px = out["last_price"]
    for lv in out["supports"]:
        assert lv["hi"] < px, lv
    for lv in out["overhead"]:
        assert lv["lo"] > px, lv


def test_supports_are_ordered_NEAREST_first(loaded):
    out = S.for_symbol("TEST", "6m")
    his = [lv["hi"] for lv in out["supports"]]
    assert his == sorted(his, reverse=True), his


def test_a_broken_supply_band_below_price_is_listed_as_SUPPORT():
    """Polarity. `price_zones` keeps the supply/demand label for colour only;
    a table that split by origin would drop the level price is standing on."""
    zones = {
        "demand_zones": [],
        "supply_zones": [{"kind": "supply", "lo": 90.0, "hi": 92.0, "mid": 91.0,
                          "touches": 3, "strength": 60, "bars_since_test": 5,
                          "oldest_touch_bars": 40}],
        "nearest_support": None, "nearest_resistance": None,
    }
    out = S.levels_from_zones(zones, 100.0)
    assert len(out["supports"]) == 1
    assert out["supports"][0]["origin"] == "supply"      # origin preserved…
    assert out["supports"][0]["distance_pct"] == 8.0     # …but listed below


def test_the_nearest_support_is_never_dropped_by_the_strength_cap():
    """`nearest_support` is computed over EVERY band while the returned lists
    keep only the strongest four per side. If the table were built from the
    lists alone its top row could disagree with the verdict's support_pct."""
    weak_but_nearest = {"kind": "demand", "lo": 98.0, "hi": 99.0, "mid": 98.5,
                        "touches": 1, "strength": 5, "bars_since_test": 2,
                        "oldest_touch_bars": 3}
    zones = {
        "demand_zones": [{"kind": "demand", "lo": 80.0, "hi": 82.0, "mid": 81.0,
                          "touches": 9, "strength": 99, "bars_since_test": 60,
                          "oldest_touch_bars": 200}],
        "supply_zones": [],
        "nearest_support": weak_but_nearest,
        "nearest_resistance": None,
    }
    out = S.levels_from_zones(zones, 100.0)
    assert out["supports"][0]["hi"] == 99.0


def test_the_same_band_arriving_twice_is_listed_once():
    z = {"kind": "demand", "lo": 98.0, "hi": 99.0, "mid": 98.5, "touches": 2,
         "strength": 50, "bars_since_test": 2, "oldest_touch_bars": 10}
    out = S.levels_from_zones(
        {"demand_zones": [z], "supply_zones": [],
         "nearest_support": dict(z), "nearest_resistance": None}, 100.0)
    assert len(out["supports"]) == 1


def test_a_band_price_is_INSIDE_is_neither_support_nor_overhead():
    z = {"kind": "demand", "lo": 99.0, "hi": 101.0, "mid": 100.0, "touches": 4,
         "strength": 70, "bars_since_test": 0, "oldest_touch_bars": 30}
    out = S.levels_from_zones(
        {"demand_zones": [z], "supply_zones": [],
         "nearest_support": None, "nearest_resistance": None}, 100.0)
    assert out["supports"] == [] and out["overhead"] == []
    assert out["standing_in"]["lo"] == 99.0


def test_distance_is_measured_to_the_EDGE_price_touches_not_the_midpoint():
    """To the band's top going down, to its low coming up. Measuring to the mid
    would flatter every level by half its width — and these are stop distances."""
    zones = {"demand_zones": [{"kind": "demand", "lo": 88.0, "hi": 90.0,
                               "mid": 89.0, "touches": 3, "strength": 50,
                               "bars_since_test": 4, "oldest_touch_bars": 20}],
             "supply_zones": [{"kind": "supply", "lo": 110.0, "hi": 112.0,
                               "mid": 111.0, "touches": 3, "strength": 50,
                               "bars_since_test": 9, "oldest_touch_bars": 30}],
             "nearest_support": None, "nearest_resistance": None}
    out = S.levels_from_zones(zones, 100.0)
    assert out["supports"][0]["distance_pct"] == 10.0     # (100-90)/100
    assert out["overhead"][0]["distance_pct"] == 10.0     # (110-100)/100


def test_a_zero_or_negative_price_does_not_divide_by_zero():
    zones = {"demand_zones": [{"kind": "demand", "lo": 1.0, "hi": 2.0, "mid": 1.5,
                               "touches": 1, "strength": 1, "bars_since_test": 1,
                               "oldest_touch_bars": 1}],
             "supply_zones": [], "nearest_support": None,
             "nearest_resistance": None}
    out = S.levels_from_zones(zones, 0.0)
    assert out["supports"] == [] or out["supports"][0]["distance_pct"] is None


# ── "recent support levels as well" ───────────────────────────────────────────
def test_a_level_tested_inside_the_last_month_is_flagged_recent():
    near = {"kind": "demand", "lo": 95.0, "hi": 96.0, "mid": 95.5, "touches": 3,
            "strength": 50, "bars_since_test": S.RECENT_BARS - 1,
            "oldest_touch_bars": 30}
    old = {"kind": "demand", "lo": 85.0, "hi": 86.0, "mid": 85.5, "touches": 6,
           "strength": 90, "bars_since_test": S.RECENT_BARS + 40,
           "oldest_touch_bars": 200}
    out = S.levels_from_zones(
        {"demand_zones": [near, old], "supply_zones": [],
         "nearest_support": None, "nearest_resistance": None}, 100.0)
    by_lo = {lv["lo"]: lv for lv in out["supports"]}
    assert by_lo[95.0]["recent"] is True
    assert by_lo[85.0]["recent"] is False


def test_the_recency_boundary_is_inclusive():
    z = {"kind": "demand", "lo": 95.0, "hi": 96.0, "mid": 95.5, "touches": 1,
         "strength": 1, "bars_since_test": S.RECENT_BARS, "oldest_touch_bars": 25}
    out = S.levels_from_zones(
        {"demand_zones": [z], "supply_zones": [], "nearest_support": None,
         "nearest_resistance": None}, 100.0)
    assert out["supports"][0]["recent"] is True


def test_a_missing_bars_since_test_is_NOT_claimed_recent():
    """Absent evidence is not evidence of a recent touch."""
    z = {"kind": "demand", "lo": 95.0, "hi": 96.0, "mid": 95.5, "touches": 1,
         "strength": 1, "bars_since_test": None, "oldest_touch_bars": None}
    out = S.levels_from_zones(
        {"demand_zones": [z], "supply_zones": [], "nearest_support": None,
         "nearest_resistance": None}, 100.0)
    assert out["supports"][0]["recent"] is False


def test_recency_is_a_FLAG_not_an_ordering(loaded):
    """Nearest-first is the ordering. If recency sorted the table, the level
    your stop actually sits under could be listed third."""
    src = inspect.getsource(S.levels_from_zones)
    assert "recent" not in src, "levels_from_zones sorts or filters on recency"


# ── the tile ──────────────────────────────────────────────────────────────────
def test_the_tile_charts_exactly_the_window_that_was_analysed(loaded):
    out = S.for_symbol("TEST", "3m")
    assert len(out["tile"]["bars"]) == 63


def test_only_the_two_decision_levels_get_a_written_label(loaded):
    """Ajay 2026-08-18 on the zone charts: "they are all clumsy and its hard to
    look at the bars". Eight labelled bands is that same chart again."""
    lines = S.for_symbol("TEST", "6m")["tile"]["lines"]
    # The rule is about WRITTEN labels. The 2026-08-29 SMC overlay adds lines
    # for the BOS, the swept level and the opening range, but they are marked
    # `quiet` and the renderer draws them without text — so the chart still
    # carries at most three pieces of writing, which is what the complaint
    # was about.
    labels = [ln["label"] for ln in lines if not ln.get("quiet")]
    assert len(labels) <= 3
    assert "now" in labels


def test_the_chart_never_draws_more_than_three_boxes_a_side(loaded):
    bands = S.for_symbol("TEST", "6m")["tile"]["bands"]
    assert sum(1 for b in bands if b["kind"] == "demand") <= 4   # +1 standing_in
    assert sum(1 for b in bands if b["kind"] == "supply") <= 3


def test_the_tile_uses_only_the_kinds_and_tones_the_renderer_knows(loaded):
    tile = S.for_symbol("TEST", "6m")["tile"]
    for b in tile["bands"]:
        assert b["kind"] in ("base", "demand", "supply",
                             # SMC overlay kinds (2026-08-29). Deliberately
                             # their own colours: an imbalance and a footprint
                             # are not the same evidence as a tested swing.
                             "fvg_demand", "fvg_supply", "order_block"), b
    for ln in tile["lines"]:
        assert ln["tone"] in ("buy", "stop", "target", "now", "neutral"), ln


def test_the_tile_carries_every_key_the_shared_contract_promises(loaded):
    tile = S.for_symbol("TEST", "6m")["tile"]
    for k in ("symbol", "name", "href", "bars", "bands", "lines", "markers",
              "stats", "why", "theme"):
        assert k in tile, f"tile is missing {k}"


# ── negatives: a miss still renders the controls ──────────────────────────────
def test_an_empty_symbol_answers_with_the_dropdown_still_populated():
    out = S.for_symbol("", "3m")
    assert "error" in out
    # The dropdown carries every real window PLUS the overlay pseudo-window
    # (added 2026-08-25) — a miss must still offer every way out.
    assert len(out["windows"]) == len(S.SUPPORT_WINDOWS) + 1
    assert out["windows"][-1]["key"] == S.OVERLAY_KEY


def test_a_non_string_symbol_does_not_raise():
    for junk in (None, 7, object(), ["NVDA"]):
        out = S.for_symbol(junk, "3m")
        assert "error" in out


def test_an_unknown_ticker_answers_an_error_not_an_exception(monkeypatch):
    from sepa import prices
    monkeypatch.setattr(prices, "load_prices", lambda *a, **k: None)
    out = S.for_symbol("NOPE", "3m")
    assert "NOPE" in out["error"]
    assert "tile" not in out


def test_a_price_load_that_RAISES_is_reported_not_propagated(monkeypatch):
    from sepa import prices

    def boom(*a, **k):
        raise RuntimeError("upstream down")
    monkeypatch.setattr(prices, "load_prices", boom)
    out = S.for_symbol("NVDA", "3m")
    assert "error" in out


def test_a_frame_shorter_than_the_window_is_ANSWERED_but_declared(monkeypatch):
    """REGRESSION. `.iloc[-126:]` on a 30-bar frame is 30 bars, so a recent IPO
    used to come back as a normal result labelled "6 months" on screen. A short
    frame is the ordinary case for a new listing — refusing it is worse than
    answering it, and answering it silently is worse than both."""
    from sepa import prices
    short = FRAME.iloc[-30:].copy()
    monkeypatch.setattr(prices, "load_prices", lambda *a, **k: short)
    out = S.for_symbol("TINY", "6m")
    assert "error" not in out, out
    assert out["bars_used"] == 30
    assert out["short_history"] == {"have": 30, "asked": 126}
    assert out["window_label"] == "6 months"       # what was asked stays visible


def test_a_frame_that_covers_the_window_declares_NO_truncation(loaded):
    out = S.for_symbol("TEST", "3m")
    assert out["short_history"] is None
    assert out["bars_used"] == 63


def test_the_chart_shows_the_bars_actually_read_not_the_bars_requested(monkeypatch):
    from sepa import prices
    short = FRAME.iloc[-30:].copy()
    monkeypatch.setattr(prices, "load_prices", lambda *a, **k: short)
    out = S.for_symbol("TINY", "6m")
    assert len(out["tile"]["bars"]) == out["bars_used"]


def test_too_little_history_for_ANY_read_says_so(monkeypatch):
    """Below the swing floor there is no answer at all, and the message must
    name history rather than blaming the window — the two misses have different
    fixes, so they must not share a sentence."""
    from sepa import prices
    tiny = FRAME.iloc[-6:].copy()
    monkeypatch.setattr(prices, "load_prices", lambda *a, **k: tiny)
    out = S.for_symbol("TINY", "6m")
    assert "bars of history" in out["error"]
    assert "try a longer window" not in out["error"]


def test_a_dead_flat_series_answers_STANDING_IN_rather_than_inventing_levels(monkeypatch):
    """Degenerate but not wrong: `_local_extrema` uses >= / <=, so every bar of
    a flat line is both a swing high and a swing low. They all cluster into the
    one band price is sitting in — and the honest output is that band, with
    nothing above and nothing below, not a fabricated support."""
    from sepa import prices
    n = 200
    idx = pd.date_range("2026-01-02", periods=n, freq="B")
    flat = pd.DataFrame({"open": [50.0] * n, "high": [50.0] * n,
                         "low": [50.0] * n, "close": [50.0] * n,
                         "volume": [1000] * n}, index=idx)
    monkeypatch.setattr(prices, "load_prices", lambda *a, **k: flat)
    out = S.for_symbol("FLAT", "6m")
    assert out["window"] == "6m"
    assert out["supports"] == [] and out["overhead"] == []
    assert out["standing_in"] is not None
    assert any(s["v"] == "none in this window"
               for s in out["tile"]["stats"] if s["k"] == "nearest support")


def test_the_shortest_window_is_actually_reachable(loaded):
    """REGRESSION. `price_zones` gated on a 60-bar frame, so before the
    `lookback_bars` knob existed a 21-bar month could only ever return None —
    the dropdown's first option would have been permanently broken."""
    out = S.for_symbol("TEST", "1m")
    assert "error" not in out, out
    assert out["supports"] or out["standing_in"]


# ── contract ──────────────────────────────────────────────────────────────────
def test_price_zones_globals_are_untouched_by_this_module(loaded):
    before = (pz.LOOKBACK_BARS, pz.SWING_WINDOW, pz.ZONE_MERGE_PCT,
              pz.ZONE_HALF_WIDTH_PCT, pz.MIN_BARS)
    for k in S.window_keys():
        S.for_symbol("TEST", k)
    assert (pz.LOOKBACK_BARS, pz.SWING_WINDOW, pz.ZONE_MERGE_PCT,
            pz.ZONE_HALF_WIDTH_PCT, pz.MIN_BARS) == before


def test_the_band_geometry_knobs_are_deliberately_NOT_varied_per_window():
    """One rule, four zooms. If merge_pct/half_width_pct also moved, the four
    views would differ for three reasons at once and 1M disagreeing with 6M
    would be unexplainable. Only `bars` and `swing_window` vary."""
    for w in S.SUPPORT_WINDOWS:
        assert set(w) == {"key", "label", "bars", "swing_window"}, w
    src = inspect.getsource(S.for_symbol)
    assert "merge_pct" not in src and "half_width_pct" not in src


def test_this_module_never_scans_a_universe():
    """Chart Maps' standing rule: a page load can never sit behind a universe
    pass. The 524 that took the demand board down on 2026-08-14 was exactly
    that mistake."""
    src = inspect.getsource(S)
    for forbidden in ("cached_or_warm", "load_latest", "scanner",
                      "analyze_symbol"):
        assert forbidden not in src, f"support.py reaches for {forbidden}"
    # 2026-09-14: the tab reads the demand BOARD's band through
    # `decide_from_frame` — PURE per frame (no network, no clock, no cache,
    # no universe). Nothing else from that module may be reached for.
    import re
    used = set(re.findall(r"\bDR\.(\w+)", src))
    assert used <= {"decide_from_frame", "zone_geom"}, used
    assert "decide_from_frame" in used


def test_it_reuses_the_boards_tile_helpers_rather_than_reimplementing_them():
    src = inspect.getsource(S)
    for shared in ("board_mod.bars_for", "board_mod._href", "board_mod._name_for"):
        assert shared in src, f"support.py reimplements {shared}"


def test_the_disclaimer_is_the_price_zones_one_not_a_new_claim():
    assert S.DISCLAIMER is pz.DISCLAIMER


# ── tested vs single-touch (2026-08-19, found in the live smoke test) ─────────
def test_a_single_touch_band_is_flagged_as_NOT_tested():
    """A one-touch "band" is one swing low with synthetic width painted round
    it. On a 21-bar frame that is also the COMMONEST band, so it wins the
    nearest-first sort — NVDA's nearest support at every zoom was one touch,
    0.03% below price. Shown, but never as a floor."""
    one = {"kind": "demand", "lo": 95.0, "hi": 96.0, "mid": 95.5, "touches": 1,
           "strength": 10, "bars_since_test": 3, "oldest_touch_bars": 3}
    many = {"kind": "demand", "lo": 85.0, "hi": 87.0, "mid": 86.0, "touches": 4,
            "strength": 80, "bars_since_test": 30, "oldest_touch_bars": 100}
    out = S.levels_from_zones(
        {"demand_zones": [one, many], "supply_zones": [],
         "nearest_support": None, "nearest_resistance": None}, 100.0)
    by_lo = {lv["lo"]: lv for lv in out["supports"]}
    assert by_lo[95.0]["tested"] is False
    assert by_lo[85.0]["tested"] is True


def test_the_tested_threshold_is_more_than_one_turn():
    assert S.MIN_TOUCHES_TESTED == 2


def test_a_single_touch_level_is_STILL_listed_not_filtered_away():
    """Hiding them would empty the short windows, and a recent swing low IS
    where the next bid sat. The fix is a label, not a filter."""
    one = {"kind": "demand", "lo": 95.0, "hi": 96.0, "mid": 95.5, "touches": 1,
           "strength": 10, "bars_since_test": 3, "oldest_touch_bars": 3}
    out = S.levels_from_zones(
        {"demand_zones": [one], "supply_zones": [], "nearest_support": None,
         "nearest_resistance": None}, 100.0)
    assert len(out["supports"]) == 1


def test_the_why_line_says_so_when_the_nearest_support_is_one_touch(loaded, monkeypatch):
    one = {"kind": "demand", "lo": 95.0, "hi": 96.0, "mid": 95.5, "touches": 1,
           "strength": 10, "bars_since_test": 3, "oldest_touch_bars": 3}
    levels = S.levels_from_zones(
        {"demand_zones": [one], "supply_zones": [], "nearest_support": None,
         "nearest_resistance": None}, 100.0)
    why = S._why(levels, {"verdict": {"label": "Mid-range."}},
                 S.window_spec("3m"))
    assert "not a tested floor" in why


def test_the_why_line_stays_quiet_when_the_level_IS_tested():
    many = {"kind": "demand", "lo": 85.0, "hi": 87.0, "mid": 86.0, "touches": 4,
            "strength": 80, "bars_since_test": 3, "oldest_touch_bars": 100}
    levels = S.levels_from_zones(
        {"demand_zones": [many], "supply_zones": [], "nearest_support": None,
         "nearest_resistance": None}, 100.0)
    why = S._why(levels, {"verdict": {"label": "Mid-range."}},
                 S.window_spec("3m"))
    assert "not a tested floor" not in why


def test_the_stats_separate_RECENCY_from_EVIDENCE(loaded):
    """Two different claims about a level and neither implies the other: a
    level touched yesterday once is recent and untested; one turned at four
    times last year is tested and stale."""
    stats = {s["k"]: s["v"] for s in S.for_symbol("TEST", "6m")["tile"]["stats"]}
    assert "touched in last month" in stats
    assert "turned at more than once" in stats


# ── the overlay window (Ajay 2026-08-25: "where can I see the overlapping
#    Demand zones?") ─────────────────────────────────────────────────────────
support = S


def test_cluster_bands_counts_DISTINCT_windows_not_bands():
    """Two bands from the SAME window are one voice, not two. Agreement means
    independent zooms seeing the same level."""
    tagged = [
        {"lo": 99.0, "hi": 101.0, "touches": 2, "window": "1y"},
        {"lo": 99.5, "hi": 100.5, "touches": 1, "window": "1y"},   # same window
        {"lo": 99.2, "hi": 100.8, "touches": 1, "window": "3m"},
    ]
    c = support.cluster_bands(tagged, 110.0)
    assert len(c) == 1
    assert c[0]["agree"] == 2                     # 1y + 3m, not 3
    assert c[0]["windows"] == ["3m", "1y"]        # short → long, dropdown order


def test_bands_further_apart_than_the_cluster_width_stay_separate():
    tagged = [{"lo": 100.0, "hi": 101.0, "touches": 2, "window": "1y"},
              {"lo": 106.0, "hi": 107.0, "touches": 2, "window": "3m"}]
    c = support.cluster_bands(tagged, 120.0)
    assert len(c) == 2
    assert all(x["agree"] == 1 for x in c)


def test_touches_keep_the_MAX_because_short_windows_truncate_the_count():
    """The 5x on CR's $173 floor only exists at the zooms long enough to see all
    five touches; a 3m window reporting 1 is truncation, not disagreement."""
    tagged = [{"lo": 173.6, "hi": 176.0, "touches": 5, "window": "1y"},
              {"lo": 174.2, "hi": 176.3, "touches": 1, "window": "6m"}]
    c = support.cluster_bands(tagged, 206.0)
    assert c[0]["touches"] == 5
    assert c[0]["tested"] is True


def test_strength_is_REFUSED_on_cluster_rows():
    """Strength is relative within its own window (CR's $223 band scored 58 at
    1y and 100 at 6m — same band). A cluster carrying either number would be
    lying; it carries none."""
    tagged = [{"lo": 99.0, "hi": 101.0, "touches": 2, "strength": 100.0,
               "window": "6m"},
              {"lo": 99.2, "hi": 100.8, "touches": 3, "strength": 58.0,
               "window": "1y"}]
    c = support.cluster_bands(tagged, 110.0)
    assert c[0]["strength"] is None


def test_clusters_rank_by_agreement_first_then_distance():
    tagged = [
        {"lo": 90.0, "hi": 91.0, "touches": 2, "window": "1y"},      # near, 1 win
        {"lo": 70.0, "hi": 71.0, "touches": 2, "window": "1y"},      # far, 3 wins
        {"lo": 70.2, "hi": 70.9, "touches": 1, "window": "6m"},
        {"lo": 70.1, "hi": 71.1, "touches": 1, "window": "3m"},
    ]
    c = support.cluster_bands(tagged, 100.0)
    assert c[0]["agree"] == 3                     # agreement outranks nearness
    assert c[0]["lo"] == 70.0


def test_sides_split_by_position_and_standing_in_is_detected():
    tagged = [{"lo": 95.0, "hi": 98.0, "touches": 2, "window": "1y"},
              {"lo": 99.0, "hi": 101.0, "touches": 2, "window": "1y"},
              {"lo": 104.0, "hi": 106.0, "touches": 2, "window": "1y"}]
    c = support.cluster_bands(tagged, 100.0)
    sides = {x["lo"]: x["side"] for x in c}
    assert sides[95.0] == "below" and sides[99.0] == "in" and sides[104.0] == "above"
    assert next(x for x in c if x["side"] == "in")["distance_pct"] == 0.0


def test_empty_and_garbage_band_lists_cluster_to_nothing():
    assert support.cluster_bands([], 100.0) == []
    assert support.cluster_bands([{"lo": None, "hi": 101.0, "window": "1y"}],
                                 100.0) == []


def test_the_dropdown_now_offers_the_overlay_and_parse_accepts_it():
    assert support.OVERLAY_KEY in support.window_keys()
    assert support.parse_window("all") == "all"
    assert support.parse_window("ALL ") == "all"
    # And unknown values still degrade to the default, never to the overlay.
    assert support.parse_window("everything") == support.DEFAULT_WINDOW


# ── the 5-year window's deep fetch (2026-08-25) ─────────────────────────────
def _bars_df(n):
    import pandas as pd
    idx = pd.bdate_range("2020-01-01", periods=n)
    close = [50 + 0.01 * i for i in range(n)]
    return pd.DataFrame({"open": close, "high": [c + 1 for c in close],
                         "low": [c - 1 for c in close], "close": close,
                         "volume": [1_000_000] * n}, index=idx)


def test_5y_window_reaches_past_the_2y_cache(monkeypatch):
    """The shared price cache returns its ~2y frame regardless of the period
    argument, so the 5y zoom must fetch deep — and must NOT write the deep
    frame back into the shared cache."""
    from sepa import prices as prices_mod
    calls = []
    monkeypatch.setattr(prices_mod, "load_prices",
                        lambda sym, period="2y", force=False: _bars_df(500))
    monkeypatch.setattr(prices_mod, "_fetch_massive",
                        lambda sym, period: calls.append((sym, period)) or _bars_df(1300))
    S._deep_cache.clear()

    df, have, _as_of = S._frame_for("CR", 1260)
    assert have == 1300 and calls == [("CR", "5y")]
    # Second call: served from the module's own cache, no refetch.
    S._frame_for("CR", 1260)
    assert len(calls) == 1


def test_5y_degrades_to_the_shared_frame_when_deep_fetch_fails(monkeypatch):
    """A failed deep fetch answers with the 2y frame — and the single-window
    path already reports bars_used/short so a 2-year chart is never silently
    labelled '5 years'."""
    from sepa import prices as prices_mod
    monkeypatch.setattr(prices_mod, "load_prices",
                        lambda sym, period="2y", force=False: _bars_df(500))
    def boom(sym, period):
        raise RuntimeError("provider down")
    monkeypatch.setattr(prices_mod, "_fetch_massive", boom)
    S._deep_cache.clear()

    df, have, _as_of = S._frame_for("CR", 1260)
    assert have == 500 and df is not None


def test_short_windows_never_trigger_a_deep_fetch(monkeypatch):
    from sepa import prices as prices_mod
    monkeypatch.setattr(prices_mod, "load_prices",
                        lambda sym, period="2y", force=False: _bars_df(500))
    def forbidden(sym, period):
        raise AssertionError("deep fetch fired for a short window")
    monkeypatch.setattr(prices_mod, "_fetch_massive", forbidden)
    S._deep_cache.clear()
    df, have, _as_of = S._frame_for("CR", 252)
    assert have == 500


# ---------------------------------------------------------------------------
# freshness stamp (Ajay 2026-08-26: INTU's frozen partial bar drew a candle
# below his stop while the live tape said $345 — the chart must SAY when its
# data left the provider)
# ---------------------------------------------------------------------------
def test_payload_carries_as_of_and_data_through(monkeypatch):
    from sepa import prices as prices_mod
    frame = _bars_df(300)
    monkeypatch.setattr(prices_mod, "load_prices",
                        lambda sym, period="2y", force=False: frame)
    monkeypatch.setattr(S, "_shared_frame_as_of", lambda sym: 1787760000.0)
    S._deep_cache.clear()

    out = S.for_symbol("CR", window="6m")
    assert out["as_of"] == 1787760000.0
    assert out["data_through"] == frame.index[-1].date().isoformat()


def test_a_missing_cache_mtime_stamps_nothing_never_now(monkeypatch):
    """NEGATIVE: no provable fetch time -> as_of None. Stamping now() would
    recreate the exact lie the stamp exists to prevent."""
    import time
    from sepa import prices as prices_mod
    frame = _bars_df(300)
    monkeypatch.setattr(prices_mod, "load_prices",
                        lambda sym, period="2y", force=False: frame)
    monkeypatch.setattr(S, "_shared_frame_as_of", lambda sym: None)
    S._deep_cache.clear()

    before = time.time()
    out = S.for_symbol("CR", window="6m")
    assert out["as_of"] is None
    assert not any(isinstance(v, float) and v >= before
                   for k, v in out.items() if k == "as_of")
    # data_through still answers — the bar date needs no fetch clock.
    assert out["data_through"] == frame.index[-1].date().isoformat()


def test_overlay_payload_is_stamped_too(monkeypatch):
    from sepa import prices as prices_mod
    frame = _bars_df(300)
    monkeypatch.setattr(prices_mod, "load_prices",
                        lambda sym, period="2y", force=False: frame)
    monkeypatch.setattr(S, "_shared_frame_as_of", lambda sym: 1787760000.0)
    monkeypatch.setattr(prices_mod, "_fetch_massive",
                        lambda sym, period: (_ for _ in ()).throw(RuntimeError("no")))
    S._deep_cache.clear()

    out = S.for_symbol("CR", window="all")
    assert out.get("error") is None or "as_of" in out
    if out.get("error") is None:
        assert out["as_of"] == 1787760000.0
        assert out["data_through"] == frame.index[-1].date().isoformat()


def test_as_of_prefers_the_mongo_cached_at_over_parquet_mtime(monkeypatch):
    """Measured 2026-08-26 on INTU: the parquet fallback file was 2.2 days
    old while the Mongo layer (the one load_prices actually serves, tail
    bumped by the intraday patcher) was minutes fresh — the parquet mtime
    would understate freshness by days."""
    from sepa import prices as prices_mod

    class _Coll:
        @staticmethod
        def find_one(q, proj=None):
            return {"cached_at": 1787770000}

    monkeypatch.setattr(prices_mod, "_get_mongo", lambda: _Coll())
    assert S._shared_frame_as_of("INTU") == 1787770000.0


def test_as_of_falls_back_to_parquet_then_none(monkeypatch, tmp_path):
    from sepa import prices as prices_mod
    monkeypatch.setattr(prices_mod, "_get_mongo", lambda: None)
    f = tmp_path / "INTU.parquet"
    f.write_bytes(b"x")
    monkeypatch.setattr(prices_mod, "_cache_path", lambda s: f)
    assert S._shared_frame_as_of("INTU") == f.stat().st_mtime
    monkeypatch.setattr(prices_mod, "_cache_path", lambda s: tmp_path / "nope.parquet")
    assert S._shared_frame_as_of("INTU") is None


# ── integrator fixes 2026-09-05: structure off the CLOSED frame ───────────────
def _closed_with_displacement(n=80, last="2026-09-02"):
    """Wavy closed daily frame whose LAST bar is a displacement bar (h105 / l100.5)
    — the same fixture tests/test_price_zones.py uses for for_symbol."""
    import math
    idx = pd.bdate_range(end=pd.Timestamp(last), periods=n) + pd.Timedelta(hours=4)
    c = [100.0 + math.sin(i / 3.0) * 0.8 for i in range(n)]
    h = [x + 0.5 for x in c]; l = [x - 0.5 for x in c]
    h[-1], l[-1], c[-1] = 105.0, 100.5, 104.8
    return pd.DataFrame({"open": c, "high": h, "low": l, "close": c,
                         "volume": [1e6] * n}, index=idx)


LIVE_SNAP = {"open": 105.6, "high": 106.0, "low": 105.5, "close": 105.8,
             "volume": 2.5e6, "date": "2026-09-03 00:00:00", "last_trade_ts_ms": 1788455521222}


def test_the_support_tab_reads_structure_off_the_closed_frame_not_the_live_bar(monkeypatch):
    """price_zones.for_symbol stopped reading FVGs / ATR / swings off today's
    partial bar on 2026-09-05; this tab computed the same things on the
    overlaid frame and still printed a demand FVG whose top was the live bar's
    low-so-far. The levels are still READ at the live print."""
    from sepa import prices as P
    from supply_demand import patterns as pat
    closed = _closed_with_displacement()
    monkeypatch.setattr(P, "load_prices", lambda sym, *a, **k: closed.copy())
    monkeypatch.setattr(P, "bulk_snapshot", lambda syms: {"ACME": LIVE_SNAP})
    monkeypatch.setattr(pat, "opening_range", lambda *a, **k: None)
    out = S.for_symbol("ACME", "1m")
    assert out.get("error") is None, out
    assert out["last_price"] == 105.8, "the levels are still read at the live print"
    assert not any(abs(g["hi"] - 105.5) < 1e-9 for g in out["fair_value_gaps"]), out["fair_value_gaps"]
    assert out["fair_value_gaps"] == pat.fair_value_gaps(closed, 105.8)
    assert out["atr"] == round(pat.atr(closed), 4)
    # a frame the overlay did NOT extend (after the close + fast-scan) is read whole, as before
    monkeypatch.setattr(P, "bulk_snapshot", lambda syms: {})
    same = S.for_symbol("ACME", "1m")
    assert same["fair_value_gaps"] == pat.fair_value_gaps(closed, float(closed["close"].iloc[-1]))


# ── 2 / 3-year zooms (Ajay 2026-09-06) ────────────────────────────────────────
def test_two_and_three_year_windows_sit_between_one_and_five_years():
    """Ajay 2026-09-06: "add 2 years to the time frame ... I do seem sometime
    we have bounces off the 2 years as well; also add 3 years and then keep 5
    years." Order is the zoom order; 5y stays the deepest."""
    assert S.window_keys() == ["1w", "2w", "1m", "3m", "6m", "1y", "2y", "3y",
                              "5y", S.OVERLAY_KEY]
    by_key = {w["key"]: w for w in S.SUPPORT_WINDOWS}
    assert by_key["2y"]["bars"] == 504 and by_key["3y"]["bars"] == 756 and by_key["5y"]["bars"] == 1260
    assert by_key["2y"]["swing_window"] == by_key["3y"]["swing_window"] == by_key["5y"]["swing_window"]
    assert by_key["2y"]["swing_window"] > by_key["1y"]["swing_window"]
    for k in ("2y", "3y", " 3Y "):
        assert S.parse_window(k) == k.strip().lower()
    assert S.window_spec("2y")["label"] == "2 years" and S.window_spec("3y")["label"] == "3 years"


def test_a_two_or_three_year_zoom_hands_price_zones_that_many_bars(loaded, monkeypatch):
    """The zoom IS the demand-zone lookback: 3y must hand price_zones 756
    bars (2y: 504), not the 1y default — else the dropdown is a label change."""
    seen = []
    real = pz.compute

    def spy(df, *a, **kw):
        seen.append(kw.get("lookback_bars"))
        return real(df, *a, **kw)
    monkeypatch.setattr(pz, "compute", spy)
    out = S.for_symbol("TEST", "3y")
    assert out["window"] == "3y" and out["window_label"] == "3 years" and 756 in seen
    seen.clear()
    out = S.for_symbol("TEST", "2y")
    assert out["window"] == "2y" and 504 in seen
    # The dropdown the response carries lists both, in zoom order.
    assert [w["key"] for w in out["windows"]] == ["1w", "2w", "1m", "3m", "6m",
                                                  "1y", "2y", "3y", "5y",
                                                  S.OVERLAY_KEY]


# ── default zoom = 1 year (Ajay 2026-09-06) ───────────────────────────────────
def test_the_default_zoom_is_one_year_on_every_surface(loaded):
    """Ajay 2026-09-06: "make support default to 1 year on all the tabs? I
    think its safer and more accurate." The API default, the fallback for
    junk and a call with no window all open on 1y — was 3m."""
    assert S.DEFAULT_WINDOW == "1y"
    assert S.parse_window("") == "1y" and S.parse_window("nope") == "1y" and S.parse_window(None) == "1y"
    out = S.for_symbol("TEST")
    assert out["window"] == "1y" and out["window_label"] == "1 year"
    # NEGATIVE: the old default still exists as a zoom, it is just not opened on.
    assert S.parse_window("3m") == "3m" and S.for_symbol("TEST", "3m")["window"] == "3m"


# ── 1-week / 2-week zooms (Ajay 2026-09-18) ──────────────────────────────────
# "Also a weekly chart for the past week and 2 week inthe charting time frames
# in all places". He chose SHORT WINDOWS, not weekly candles: the candles stay
# daily, the zoom shows the last 5 / 10 sessions, and because a frame that
# short is under price_zones.MIN_BARS_ABS (and under the len(df) > 5 the
# no-repaint drop in supply_demand/mood.py needs) EVERY read — levels, mood,
# signal, SMC, patterns, trend — is the 1-month read. These tests pin that the
# picture is the only thing that got shorter.
from chart_maps import board as B_                     # noqa: E402
from supply_demand import mood as mood_mod             # noqa: E402


def _ramp_frame(n: int, *, spike: bool = False) -> pd.DataFrame:
    """`n` bars with real swing structure (a 5-bar saw), optionally with the
    last bar spiked — the still-forming bar a no-repaint read must drop."""
    seq = _saw(100.0, 108.0, 5, (n // 10) + 2)[:n]
    c = pd.Series(seq, dtype=float)
    if spike and n:
        c.iloc[-1] = float(c.iloc[-1]) * 1.09
    idx = pd.date_range("2026-01-02", periods=len(c), freq="B")
    return pd.DataFrame(
        {"open": c.values, "high": c.values * 1.004, "low": c.values * 0.996,
         "close": c.values, "volume": np.ones(len(c)) * 1_000_000},
        index=idx,
    )


@pytest.fixture
def frame_of(monkeypatch):
    """Point every price read (shared AND deep) at a frame of exactly N bars."""
    from sepa import prices

    def _use(n: int, *, spike: bool = False):
        f = _ramp_frame(n, spike=spike)
        monkeypatch.setattr(prices, "load_prices", lambda s, *a, **k: f.copy())
        monkeypatch.setattr(prices, "_fetch_massive", lambda *a, **k: None,
                            raising=False)
        S._deep_cache.clear()
        return f
    yield _use
    S._deep_cache.clear()


def _spy_compute(monkeypatch):
    """Record every (lookback_bars, swing_window) price_zones.compute saw."""
    seen: list[tuple] = []
    real = pz.compute

    def spy(df, *a, **kw):
        seen.append((kw.get("lookback_bars"), kw.get("swing_window")))
        return real(df, *a, **kw)
    monkeypatch.setattr(pz, "compute", spy)
    return seen


# BE-1
def test_the_two_short_zooms_are_offered_first():
    assert S.window_keys() == ["1w", "2w", "1m", "3m", "6m", "1y", "2y", "3y",
                               "5y", S.OVERLAY_KEY]
    assert S.parse_window(" 1W ") == "1w" and S.parse_window("2w") == "2w"


# BE-2
def test_a_week_is_five_sessions_and_two_weeks_is_ten():
    """Bars are TRADING days on this list's own convention (21/mo = 4.2
    trading weeks) — 5 sessions to the week, never 7 or 14 calendar days."""
    by_key = {w["key"]: w for w in S.SUPPORT_WINDOWS}
    assert by_key["1w"]["bars"] == 5 and by_key["1w"]["label"] == "1 week"
    assert by_key["2w"]["bars"] == 10 and by_key["2w"]["label"] == "2 weeks"
    # NEGATIVE: nobody counted calendar days.
    assert not any(w["bars"] in (7, 14) for w in S.SUPPORT_WINDOWS)


# BE-3
def test_a_chart_only_zoom_reads_its_levels_from_the_one_month_window(
        loaded, monkeypatch):
    by_key = {w["key"]: w for w in S.SUPPORT_WINDOWS}
    for key in ("1w", "2w"):
        seen = _spy_compute(monkeypatch)
        out = S.for_symbol("TEST", key)
        assert "error" not in out, out
        assert seen and all(lb == by_key["1m"]["bars"] for lb, _ in seen), seen
        assert all(sw == by_key["1m"]["swing_window"] for _, sw in seen), seen
        # NEGATIVE: the chart budget never reaches price_zones.
        assert not any(lb in (5, 10) for lb, _ in seen), seen
        assert out["levels_window"] == "1m"
        assert out["levels_window_label"] == "1 month"


# BE-4
def test_a_chart_only_zoom_draws_only_its_own_sessions(loaded):
    for key, want in (("1w", 5), ("2w", 10)):
        out = S.for_symbol("TEST", key)
        assert "error" not in out, out
        assert len(out["tile"]["bars"]) == want
        # NEGATIVE: bars_for's 20-bar floor did not silently widen the picture.
        assert len(out["tile"]["bars"]) != B_.BARS_FLOOR


# BE-6 UNDERFLOW
def test_a_one_week_zoom_on_a_three_bar_symbol_says_so_and_draws_nothing(frame_of):
    frame_of(3)
    out = S.for_symbol("TEST", "1w")
    assert "only 3 bars of history" in out["error"], out["error"]
    assert "1 month" in out["error"], out["error"]
    assert out["bars_used"] == 3
    for k in ("supports", "verdict", "levels_capped", "tile"):
        assert k not in out, f"a 3-bar frame still shipped {k}"


# BE-7 BOUNDARY
def test_at_exactly_the_swing_floor_a_short_zoom_answers(frame_of):
    frame_of(pz.MIN_BARS_ABS)
    ok = S.for_symbol("TEST", "1w")
    assert "error" not in ok, ok
    assert ok["levels_window"] == "1m"
    frame_of(pz.MIN_BARS_ABS - 1)
    miss = S.for_symbol("TEST", "1w")
    assert f"only {pz.MIN_BARS_ABS - 1} bars of history" in miss["error"], miss


# BE-8 BOUNDARY
def test_a_five_bar_frame_reports_thin_history_not_missing_structure(frame_of):
    frame_of(5)
    out = S.for_symbol("TEST", "1w")
    assert out["error"] == ("TEST has only 5 bars of history — "
                            "too few to read a 1 month window.")
    # NEGATIVE: the "change the zoom" message would be useless here.
    assert "No swing structure" not in out["error"]


# BE-9
def test_the_overlay_skips_the_chart_only_zooms(loaded):
    out = S.for_symbol("TEST", S.OVERLAY_KEY)
    keys = [r["key"] for r in (out.get("per_window") or [])]
    assert "1w" not in keys and "2w" not in keys, keys
    assert keys == ["1m", "3m", "6m", "1y", "2y", "3y", "5y"], keys


# BE-10 DEFAULT UNMOVED
def test_adding_the_short_zooms_moved_no_default(loaded):
    assert S.DEFAULT_WINDOW == "1y"
    for junk in (None, "", "  ", "zzz", 7):
        assert S.parse_window(junk) == "1y"
    assert S.window_spec("zzz")["key"] == "1y"
    assert S.window_spec("zzz")["label"] == "1 year"
    assert S.for_symbol("TEST")["window"] == "1y"


# BE-11
def test_the_short_zooms_touch_no_price_zones_constant(loaded):
    before = (pz.MIN_BARS, pz.MIN_BARS_ABS, pz.ZONE_MERGE_PCT,
              pz.ZONE_HALF_WIDTH_PCT, pz.SWING_WINDOW)
    S.for_symbol("TEST", "1w")
    S.for_symbol("TEST", "2w")
    assert (pz.MIN_BARS, pz.MIN_BARS_ABS, pz.ZONE_MERGE_PCT,
            pz.ZONE_HALF_WIDTH_PCT, pz.SWING_WINDOW) == before


# BE-12
def test_the_long_zooms_are_byte_identical_after_the_change(loaded, monkeypatch):
    by_key = {w["key"]: w for w in S.SUPPORT_WINDOWS}
    for key in ("1m", "3m", "6m", "1y", "2y", "3y", "5y"):
        seen = _spy_compute(monkeypatch)
        out = S.for_symbol("TEST", key)
        assert seen, key
        assert all(lb == by_key[key]["bars"] for lb, _ in seen), (key, seen)
        assert all(sw == by_key[key]["swing_window"] for _, sw in seen), (key, seen)
        assert out.get("levels_window") is None, key
        assert out.get("levels_window_label") is None, key


# BE-13
def test_the_note_on_a_chart_only_zoom_names_the_floor_and_the_read_window(loaded):
    note = S.for_symbol("TEST", "1w")["note"]
    assert str(pz.MIN_BARS_ABS) in note, note
    assert "1 month" in note, note
    # NEGATIVE: the old sentence is FALSE here and must not be printed.
    assert "Levels are read from this window only." not in note
    assert "bounce" not in note.lower()


# BE-14
def test_a_chart_only_window_swing_value_is_never_used(loaded, monkeypatch):
    bumped = tuple({**w, "swing_window": 9} if w["key"] in ("1w", "2w") else w
                   for w in S.SUPPORT_WINDOWS)
    monkeypatch.setattr(S, "SUPPORT_WINDOWS", bumped)
    seen = _spy_compute(monkeypatch)
    S.for_symbol("TEST", "1w")
    assert seen and all(sw == 2 for _, sw in seen), seen


# BE-15
def test_chart_span_on_a_short_zoom_states_both_spans(loaded):
    span = S.for_symbol("TEST", "1w")["chart_span"]
    assert "last 5 sessions" in span, span
    assert "from 1 month of daily bars" in span, span
    assert S.for_symbol("TEST", "1y")["chart_span"] == "1 year"


# BE-15b NEGATIVE — the intraday collision, found by the critic before ship.
# `chart_only` keys off `not own_bars`, and an EXT-HOURS frame (5m_live) also
# has own_bars False, so the chart-only arm used to win and announce
# "last 300 sessions" over a 300-bar FIVE-MINUTE chart. `window` and `tf` are
# independent URL params and the API advertises 1w/2w, so it is reachable by
# bookmark even though the dropdown always writes the pair together.
@pytest.mark.parametrize("tf", ["5m_live", "60m", "15m"])
def test_a_short_zoom_on_an_INTRADAY_frame_never_claims_daily_sessions(
        loaded, monkeypatch, tf):
    # The intraday frame never loads in tests (no MASSIVE key, no mongo), so
    # stub the ONE call support.py makes for it and let everything else run for
    # real. 300 bars is what the live 5-min view actually serves.
    from supply_demand import timeframes as tf_mod
    intra = FRAME.tail(300).copy()
    monkeypatch.setattr(tf_mod, "frame_for",
                        lambda sym, key, **k: (intra, {"tf": key}))
    try:
        out = S.for_symbol("TEST", "1w", tf=tf)
    except TypeError:
        pytest.skip("for_symbol takes no tf in this build")
    if "chart_span" not in out:
        pytest.skip("intraday frame unavailable in this environment: %s"
                    % out.get("error"))
    span, note = out["chart_span"], out["note"]
    # UPDATED 2026-09-18 (second ship): a short window now TRIMS the intraday
    # chart, so naming sessions here is no longer a lie — it is the point. What
    # must still never happen is claiming a DAILY span, or claiming more
    # sessions than the drawn frame actually holds.
    assert "daily bars" not in span or "levels from" in span, span
    assert "the last 5 sessions" not in note, note
    held = out.get("chart_sessions")
    if "session" in span:
        assert held, "span names sessions but chart_sessions is %r" % held
        assert str(held) in span, (span, held)
        # never more than the frame contains
        dates = {str(b["t"])[:10] for b in (out["tile"]["bars"] or [])}
        assert held <= max(len(dates), 1), (held, len(dates))
    # UNTIL 2026-09-18 the daily zoom was inert on EVERY intraday frame. The
    # second ship makes a SHORT window reach the intraday chart — he asked for
    # "1 week of HOURLY bars" — so zoom_applies is now True exactly when the
    # slice actually trimmed something, and False when it could not.
    assert out["zoom_applies"] is (out.get("chart_sessions") is not None)
    if tf == "5m_live":
        # ext-hours: own_bars is False, so the window would have driven the
        # LEVELS — the redirect still applies and the span must name it.
        assert out["levels_window"] == "1m", out["levels_window"]
        assert "1 month" in span, span
    else:
        # 60m / 15m carry their OWN bars: the window never reached the levels,
        # so there is no redirect to report and none is claimed.
        assert out["levels_window"] is None, out["levels_window"]
        # an own-bars frame read no daily window, so it must not name one
        assert "levels from" not in span, span


def test_the_short_zoom_still_states_its_daily_span_on_a_DAILY_frame(loaded):
    out = S.for_symbol("TEST", "1w")
    assert "last 5 sessions" in out["chart_span"]
    assert "the last 5 sessions" in out["note"]


# BE-16 NEGATIVE — he declined weekly CANDLES
def test_no_bar_interval_was_introduced():
    src = inspect.getsource(S)
    assert "resample" not in src
    assert "closed=left" not in src


# BE-17 [C1] the equality that makes the note true
def test_every_read_on_a_short_zoom_equals_the_one_month_read(frame_of):
    df = frame_of(80, spike=True)
    one_m = S.for_symbol("TEST", "1m")
    assert "error" not in one_m, one_m
    for key in ("1w", "2w"):
        out = S.for_symbol("TEST", key)
        assert "error" not in out, out
        assert out["mood"] == one_m["mood"], key
        assert out["signal"]["action"] == one_m["signal"]["action"], key
        assert out["trend_read"] == one_m["trend_read"], key
        assert out["bullish_patterns"] == one_m["bullish_patterns"], key
        assert out["smc"] == one_m["smc"], key
        assert out["supports"] == one_m["supports"], key
        assert out["overhead"] == one_m["overhead"], key
        assert out["verdict"] == one_m["verdict"], key
    # NEGATIVE — the regression this pins: a mood read off the CHART budget is
    # a different number entirely (5 bars scores far under MOOD_BUY).
    short_mood = mood_mod.mood(df.tail(5))
    assert short_mood["score"] != one_m["mood"]["score"], short_mood


# BE-18 [C2] no_repaint must not sit over a repainting frame
def test_a_short_zoom_never_ships_a_repainting_no_repaint_flag(frame_of):
    df = frame_of(80, spike=True)
    out = S.for_symbol("TEST", "1w")
    assert out["mood"]["closed_only"] is True
    assert out["mood"]["bars"] == 20            # 21 asked, the forming bar dropped
    assert out["mood"]["bars"] != 5
    assert out["signal"]["no_repaint"] is True
    # The hole this change ROUTES AROUND rather than closing: mood.py drops the
    # still-forming bar only when len(df) > 5, strictly — so a caller handing
    # it exactly 5 bars gets a repainting read. Documented here, not "fixed":
    # that guard is the shared no-repaint rule for every timeframe. HIS CALL.
    assert mood_mod.mood(df.tail(5))["bars"] == 5


# BE-19 [C3] the evidence warning must not go quiet at the short zoom
def test_a_thin_symbol_still_warns_at_the_short_zoom(frame_of):
    frame_of(13)
    out = S.for_symbol("TEST", "1w")
    assert "error" not in out, out
    assert out["short_history"] == {"have": 13, "asked": 21}
    assert out["supports"] is not None
    assert S.for_symbol("TEST", "1m")["short_history"] == {"have": 13, "asked": 21}
    # NEGATIVE: a full frame says nothing.
    frame_of(300)
    assert S.for_symbol("TEST", "1w")["short_history"] is None


# BE-20 [C4] the miss payload must agree with its own sentence
def test_the_miss_payload_agrees_with_its_own_error_string(frame_of, monkeypatch):
    frame_of(11)
    out = S.for_symbol("TEST", "1w")
    assert out["bars_used"] == 11
    assert "only 11 bars" in out["error"], out["error"]
    # NEGATIVE, no regression into the no-structure branch: a 300-bar frame at
    # 1m that finds no structure still reports the 21 bars it READ, not 300.
    frame_of(300)
    monkeypatch.setattr(pz, "compute", lambda *a, **k: None)
    miss = S.for_symbol("TEST", "1m")
    assert miss["bars_used"] == 21
    assert "No swing structure" in miss["error"], miss["error"]
