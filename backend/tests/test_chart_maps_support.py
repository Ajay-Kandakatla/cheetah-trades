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
    labels = [ln["label"] for ln in S.for_symbol("TEST", "6m")["tile"]["lines"]]
    assert len(labels) <= 3
    assert "now" in labels


def test_the_chart_never_draws_more_than_three_boxes_a_side(loaded):
    bands = S.for_symbol("TEST", "6m")["tile"]["bands"]
    assert sum(1 for b in bands if b["kind"] == "demand") <= 4   # +1 standing_in
    assert sum(1 for b in bands if b["kind"] == "supply") <= 3


def test_the_tile_uses_only_the_kinds_and_tones_the_renderer_knows(loaded):
    tile = S.for_symbol("TEST", "6m")["tile"]
    for b in tile["bands"]:
        assert b["kind"] in ("base", "demand", "supply"), b
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
    for forbidden in ("cached_or_warm", "load_latest", "demand_reentry",
                      "scanner"):
        assert forbidden not in src, f"support.py reaches for {forbidden}"


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
