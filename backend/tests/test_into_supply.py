"""Behavioural tests for the Into Supply board (supply_demand/into_supply.py).

The module claims to be the exact MIRROR of `reentry_read`, riding the demand
scan rather than running its own. Both claims are load-bearing and both are
pinned here: the mirror by running the same fixtures upside-down, the ride by
contract tests that fail if a second scan, a second cache or a second set of
thresholds appears.

Synthetic and deterministic. `price_zones` is a configured price-structure read,
NOT a book method, so nothing here cites a page.
"""
from __future__ import annotations

import inspect
import re

import numpy as np
import pandas as pd
import pytest

from supply_demand import demand_reentry as dr
from supply_demand import into_supply as S


_TRIPLE_D = '"' * 3
_TRIPLE_S = "'" * 3


def _code(obj) -> str:
    """Source with docstrings and comments stripped.

    A contract test must check what the code DOES, not what its prose mentions.
    Four of these failed on their first run for exactly that reason: the module
    docstring explains that it never calls scan(), and a naive substring search
    found the word inside the sentence saying so.
    """
    src = obj if isinstance(obj, str) else inspect.getsource(obj)
    src = re.sub(_TRIPLE_D + r"(?:.|\n)*?" + _TRIPLE_D, "", src)
    src = re.sub(_TRIPLE_S + r"(?:.|\n)*?" + _TRIPLE_S, "", src)
    return "\n".join(line.split("#", 1)[0] for line in src.splitlines())


# ── fixtures ─────────────────────────────────────────────────────────────────
BAND_LO, BAND_HI = 100.0, 104.0


def _closes(*legs) -> list:
    out: list = []
    for start, end, n in legs:
        out += list(np.linspace(start, end, n, endpoint=False))
    return [float(x) for x in out]


def _rally_into_band(last: float) -> list:
    """Down to 88 (12% under the band floor), then up to `last`."""
    return _closes((95.0, 88.0, 10), (88.0, last, 20)) + [last]


# ── the core mirror ──────────────────────────────────────────────────────────
def test_a_rally_up_into_the_band_is_into_supply():
    c = _rally_into_band(102.0)
    out = S.supply_read(c, BAND_LO, BAND_HI, 102.0)
    assert out["in_band"] is True
    assert out["state"] == S.STATE_AT
    assert out["into_supply"] is True
    assert out["run_up_pct"] >= S.MIN_RUN_UP_PCT


def test_price_just_UNDER_the_band_is_about_to_be_in_it():
    """"in OR about to be in" — the second half of what was asked for."""
    c = _rally_into_band(98.5)                       # 1.5% under the floor
    out = S.supply_read(c, BAND_LO, BAND_HI, 98.5)
    assert out["in_band"] is False
    assert out["near_band"] is True
    assert out["state"] == S.STATE_NEAR
    assert out["into_supply"] is True


def test_a_name_far_below_the_band_is_neither():
    c = _rally_into_band(90.0)
    out = S.supply_read(c, BAND_LO, BAND_HI, 90.0)
    assert out["state"] is None
    assert out["into_supply"] is False


def test_a_name_ABOVE_the_band_is_not_under_a_lid():
    """It cleared it. That is a breakout, and the band is now support."""
    c = _closes((95.0, 88.0, 10), (88.0, 112.0, 25)) + [112.0]
    out = S.supply_read(c, BAND_LO, BAND_HI, 112.0)
    assert out["state"] is None
    assert out["into_supply"] is False


def test_a_band_price_has_CLOSED_above_is_no_longer_a_ceiling():
    """The mirror of the broken-band guard. `reentry_read` refuses a floor the
    market has closed beneath; a lid the market has closed above is a breakout
    that came back, not a lid — and calling it one would flag every successful
    breakout retest as a warning."""
    c = _closes((95.0, 88.0, 8), (88.0, 108.0, 12)) + [106.0, 102.0]
    out = S.supply_read(c, BAND_LO, BAND_HI, 102.0)
    assert out["broke_above"] is True
    assert out["highest_close_pct_above"] > 0
    assert out["into_supply"] is False


def test_a_band_price_only_HOVERED_around_is_not_an_approach():
    """Mirror of MIN_RISE_ABOVE_PCT: chop around a level is not arriving at it."""
    c = [99.0, 100.5, 99.5, 101.0, 99.8, 100.2] * 5 + [102.0]
    out = S.supply_read(c, BAND_LO, BAND_HI, 102.0)
    assert out["run_up_pct"] < S.MIN_RUN_UP_PCT
    assert out["into_supply"] is False


def test_only_CLOSES_count_so_an_intraday_wick_does_not_disqualify():
    """Symmetric with the demand side: a wick through overhead supply is how a
    ceiling gets tested. Only closes are passed in, so a high above the band
    cannot appear here at all — this pins that the function reads the list it
    is given and nothing else."""
    src = _code(S.supply_read)
    # It is handed a list of closes and touches no price frame at all.
    for forbidden in ("df[", '["high"]', "['high']", ".high"):
        assert forbidden not in src, f"supply_read reaches for {forbidden}"


# ── the mirror is EXACT ──────────────────────────────────────────────────────
def test_the_two_reads_are_mirrors_on_the_same_geometry():
    """Flip a demand fixture upside-down about the band and the supply read
    must answer the same way the demand read did. If one side grows a rule the
    other lacks, this diverges."""
    demand = _closes((100.0, 118.0, 12), (118.0, 102.0, 18)) + [102.0]
    d = dr.reentry_read(demand, zone_hi=104.0, zone_lo=100.0, last_price=102.0)

    mirrored = [204.0 - c for c in demand]           # reflect about 102
    s = S.supply_read(mirrored, band_lo=100.0, band_hi=104.0, last_price=102.0)

    assert d["is_reentry"] == s["into_supply"]
    assert d["in_band"] == s["in_band"]

    # The VERDICTS mirror exactly. The PERCENTAGES cannot, and asserting they
    # did was wrong arithmetic on my part: `fell_from_pct` is measured against
    # the band HIGH and `run_up_pct` against the band LOW, so one 14-dollar
    # excursion reads 13.5% from 104 and 14.0% from 100. What reflects is the
    # distance in dollars, so that is what gets asserted.
    peak = max(demand[-dr.REENTRY_LOOKBACK_BARS:])
    trough = min(mirrored[-S.LOOKBACK_BARS:])
    assert (peak - 104.0) == pytest.approx(100.0 - trough, abs=1e-9)


def test_the_two_boards_share_ONE_scale():
    """Every threshold is borrowed. If someone forks them the boards start
    disagreeing about what "tested" means, silently."""
    assert S.MIN_RUN_UP_PCT is dr.MIN_RISE_ABOVE_PCT
    assert S.LOOKBACK_BARS is dr.REENTRY_LOOKBACK_BARS
    src = inspect.getsource(S)
    # No re-declared numbers for the quality bar.
    assert "MIN_TOUCHES =" not in src
    assert "MIN_ZONE_STRENGTH =" not in src


def test_near_uses_the_same_3pct_the_per_ticker_read_calls_INTO_SUPPLY():
    from supply_demand import price_zones as pz
    assert S.NEAR_CEILING_PCT is pz.NEAR_PCT


# ── picking the lid ──────────────────────────────────────────────────────────
def _z(lo, hi, kind="supply", touches=3, strength=60, bars=5):
    return {"kind": kind, "lo": lo, "hi": hi, "mid": (lo + hi) / 2,
            "touches": touches, "strength": strength, "bars_since_test": bars,
            "oldest_touch_bars": 60}


def test_the_ceiling_is_the_band_price_is_inside():
    rec = {"nearest_resistance": _z(120, 124), "supply_zones": [_z(101, 105)],
           "demand_zones": []}
    assert S.pick_ceiling(102.0, rec)["lo"] == 101


def test_otherwise_it_is_the_NEAREST_band_above():
    rec = {"nearest_resistance": _z(110, 112), "supply_zones": [_z(130, 134)],
           "demand_zones": []}
    assert S.pick_ceiling(100.0, rec)["lo"] == 110


def test_a_broken_SUPPORT_band_above_price_counts_as_a_ceiling():
    """Polarity, same as everywhere else: price_zones keeps the origin for
    colour. A demand band price has fallen under is overhead now."""
    rec = {"nearest_resistance": None, "supply_zones": [],
           "demand_zones": [_z(110, 112, kind="demand")]}
    assert S.pick_ceiling(100.0, rec)["lo"] == 110


def test_nearest_resistance_leads_because_the_lists_are_TRUNCATED():
    """price_zones caps supply_zones at the strongest four but computes
    nearest_resistance over every band — the same reason trade_plan reaches for
    it first, and the same KLAC bug if it does not."""
    rec = {"nearest_resistance": _z(106, 108), "supply_zones": [_z(140, 145)],
           "demand_zones": []}
    assert S.pick_ceiling(100.0, rec)["lo"] == 106


def test_no_band_above_means_no_ceiling_rather_than_a_guess():
    rec = {"nearest_resistance": None, "supply_zones": [], "demand_zones": []}
    assert S.pick_ceiling(100.0, rec) is None


def test_pick_ceiling_survives_junk_bands():
    rec = {"nearest_resistance": {"lo": None, "hi": 5},
           "supply_zones": [{}, None, {"lo": "x", "hi": "y"}],
           "demand_zones": []}
    assert S.pick_ceiling(100.0, rec) is None
    assert S.pick_ceiling(100.0, None) is None
    assert S.pick_ceiling("junk", rec) is None


# ── quality gate ─────────────────────────────────────────────────────────────
def test_an_untested_band_is_not_published_as_a_ceiling():
    """One touch is a bar, not a lid — the same distinction the Support Levels
    tab draws, and the same MIN_TOUCHES the demand board applies to a floor."""
    df = _frame(_rally_into_band(102.0))
    rec = {"last_price": 102.0, "nearest_resistance": _z(100, 104, touches=1),
           "supply_zones": [], "demand_zones": [], "nearest_support": None}
    out = S.read_from_frame(df, rec)
    assert out["quality_ok"] is False
    assert out["is_into_supply"] is False
    # …but the geometry is still reported, so the row is auditable.
    assert out["into_supply"] is True


def test_a_weak_band_is_refused_on_strength_too():
    df = _frame(_rally_into_band(102.0))
    rec = {"last_price": 102.0,
           "nearest_resistance": _z(100, 104, touches=5, strength=10),
           "supply_zones": [], "demand_zones": [], "nearest_support": None}
    assert S.read_from_frame(df, rec)["is_into_supply"] is False


# ── the asymmetry number ─────────────────────────────────────────────────────
def _frame(closes: list) -> pd.DataFrame:
    n = len(closes)
    idx = pd.date_range("2026-01-02", periods=n, freq="B")
    c = pd.Series(closes, dtype=float)
    return pd.DataFrame({"open": c.values, "high": c.values, "low": c.values,
                         "close": c.values, "volume": np.ones(n) * 1e6}, index=idx)


def test_room_ratio_is_room_up_over_room_down():
    """The DHI shape: a lid at price and a floor well below is a terrible place
    to buy, and the ratio is the one number that says so."""
    df = _frame(_rally_into_band(99.0))
    rec = {"last_price": 99.0, "nearest_resistance": _z(100, 104),
           "supply_zones": [], "demand_zones": [],
           "nearest_support": _z(89, 90, kind="demand")}
    out = S.read_from_frame(df, rec)
    # 1.01% up to the lid, 10% down to the floor.
    assert out["distance_pct"] == pytest.approx(1.01, abs=0.02)
    assert out["downside_pct"] == pytest.approx(10.0, abs=0.05)
    assert out["room_ratio"] == pytest.approx(0.10, abs=0.01)


def test_a_name_INSIDE_its_ceiling_has_zero_room_up():
    df = _frame(_rally_into_band(102.0))
    rec = {"last_price": 102.0, "nearest_resistance": _z(100, 104),
           "supply_zones": [], "demand_zones": [],
           "nearest_support": _z(90, 92, kind="demand")}
    out = S.read_from_frame(df, rec)
    assert out["distance_pct"] == 0.0
    assert out["room_ratio"] == 0.0


def test_to_clear_is_reported_separately_because_distance_goes_to_zero_inside():
    df = _frame(_rally_into_band(102.0))
    rec = {"last_price": 102.0, "nearest_resistance": _z(100, 104),
           "supply_zones": [], "demand_zones": [], "nearest_support": None}
    out = S.read_from_frame(df, rec)
    assert out["to_clear_pct"] == pytest.approx(1.96, abs=0.02)


def test_no_support_below_means_no_ratio_rather_than_a_fake_one():
    df = _frame(_rally_into_band(99.0))
    rec = {"last_price": 99.0, "nearest_resistance": _z(100, 104),
           "supply_zones": [], "demand_zones": [], "nearest_support": None}
    out = S.read_from_frame(df, rec)
    assert out["downside_pct"] is None
    assert out["room_ratio"] is None
    assert out["is_into_supply"] is True          # still a real ceiling


# ── negatives ────────────────────────────────────────────────────────────────
def test_supply_read_never_raises_on_junk():
    for args in (
        ([], 100, 104, 102), (None, 100, 104, 102),
        ([1, 2, 3], 0, 104, 102), ([1, 2, 3], 104, 100, 102),
        ([1, 2, 3], 100, 104, 0), ([1, 2, 3], 100, 104, -5),
        ([1, 2, 3], "a", "b", 102), ([1, 2, 3], 100, 104, None),
    ):
        out = S.supply_read(*args)
        assert out["into_supply"] is False
        assert out["state"] is None


def test_read_from_frame_answers_None_rather_than_raising():
    df = _frame(_rally_into_band(102.0))
    assert S.read_from_frame(None, {"last_price": 1}) is None
    assert S.read_from_frame(df, None) is None
    assert S.read_from_frame(df, {}) is None
    assert S.read_from_frame(df, {"last_price": "x"}) is None


def test_a_name_in_clear_air_returns_None_which_is_the_ordinary_case():
    df = _frame(_rally_into_band(90.0))
    rec = {"last_price": 90.0, "nearest_resistance": _z(130, 134),
           "supply_zones": [], "demand_zones": [], "nearest_support": None}
    assert S.read_from_frame(df, rec) is None


def test_qualifies_reads_the_attached_block_and_never_recomputes():
    assert S.qualifies({"supply": {"is_into_supply": True}}) is True
    assert S.qualifies({"supply": {"is_into_supply": False}}) is False
    assert S.qualifies({"supply": None}) is False
    assert S.qualifies({}) is False
    assert S.qualifies(None) is False


def _row(sym, state=S.STATE_AT, dist=0.0, down=1.0, touches=3):
    return {"symbol": sym, "supply": {"state": state, "distance_pct": dist,
                                      "downside_pct": down,
                                      "ceiling_touches": touches}}


def test_inside_the_band_ranks_above_merely_approaching_it():
    rows = [_row("NEAR", S.STATE_NEAR, dist=1.0), _row("AT")]
    assert [r["symbol"] for r in sorted(rows, key=S.sort_key)] == ["AT", "NEAR"]


def test_REGRESSION_a_board_of_AT_rows_is_not_sorted_alphabetically():
    """The defect the live S&P 500 board exposed. `distance_pct` and
    `room_ratio` are BOTH 0.0 for every name already inside its ceiling, so the
    first ordering degenerated completely and the tie-break fell through to the
    symbol — the board opened ABBV / ACN / AJG / AON. An alphabetical caution
    list is worse than none, because it looks ranked."""
    rows = [_row("AAA", down=0.4), _row("ZZZ", down=6.1), _row("MMM", down=2.9)]
    assert [r["symbol"] for r in sorted(rows, key=S.sort_key)] == \
        ["ZZZ", "MMM", "AAA"]


def test_most_air_beneath_ranks_first():
    """If it fails here, how far to the next floor? That is the risk."""
    rows = [_row("SHALLOW", down=0.4), _row("DEEP", down=6.1)]
    assert [r["symbol"] for r in sorted(rows, key=S.sort_key)] == ["DEEP", "SHALLOW"]


def test_a_harder_lid_breaks_a_tie_on_air_beneath():
    rows = [_row("SOFT", down=3.0, touches=2), _row("HARD", down=3.0, touches=6)]
    assert [r["symbol"] for r in sorted(rows, key=S.sort_key)] == ["HARD", "SOFT"]


def test_among_approaching_names_the_nearest_lid_leads():
    rows = [_row("FAR", S.STATE_NEAR, dist=2.8), _row("CLOSE", S.STATE_NEAR, dist=0.4)]
    assert [r["symbol"] for r in sorted(rows, key=S.sort_key)] == ["CLOSE", "FAR"]


def test_a_row_with_no_supply_block_sorts_LAST_not_first():
    """Missing data must never masquerade as the most urgent warning."""
    rows = [{"symbol": "NONE", "supply": {}}, _row("REAL", down=0.1)]
    assert [r["symbol"] for r in sorted(rows, key=S.sort_key)] == ["REAL", "NONE"]


def test_the_board_score_reproduces_the_sort_key_by_POSITION():
    """One definition of the ordering. A weighted score squashing four keys
    into one number would be a second, silently different one."""
    from chart_maps import board
    src = _code(board.supply_tiles)
    assert '"_score": float(len(rows) - rank)' in src


# ── contract: it RIDES the demand pass ───────────────────────────────────────
def test_this_module_never_loads_a_price_or_runs_a_scan():
    """The whole design. A second universe pass would double a 3-minute job and
    create two sources of truth for one name's bands."""
    src = _code(S)
    for forbidden in ("load_prices", "cached_or_warm", "scan(", "_cache",
                      "requests", "time.time", "datetime.now"):
        assert forbidden not in src, f"into_supply reaches for {forbidden}"


def test_the_supply_read_is_attached_inside_decide_from_frame():
    """So the walk-forward and the live board see the same record, and so the
    board never needs a second pass to build itself."""
    src = _code(dr.decide_from_frame)
    assert "into_supply" in src
    assert 'rec["supply"]' in src


def test_decide_from_frame_stays_pure_after_the_addition():
    """Duplicated from the contracts file on purpose — this change edits that
    function, and the property it must not break is exactly this one."""
    src = inspect.getsource(dr.decide_from_frame)
    for forbidden in ("load_prices", "datetime.now", "time.time", "_cache",
                      "cached_or_warm", "fetch_trades"):
        assert forbidden not in src, f"decide_from_frame reaches for {forbidden}"


def test_the_supply_read_can_never_break_the_demand_board():
    """It is the newer, secondary read; the demand board is what he trades."""
    src = _code(dr.decide_from_frame)
    lines = [ln for ln in src.splitlines() if ln.strip()]
    i = next(n for n, ln in enumerate(lines) if "into_supply" in ln)
    # The two statements immediately above the import are the guard itself.
    assert any(ln.strip() == "try:" for ln in lines[max(0, i - 2):i]), \
        "the attach is not inside a try block"
    assert 'rec["supply"] = None' in src, "no fallback on failure"
    assert "except Exception" in src


def test_the_scan_collects_both_boards_in_ONE_loop():
    src = _code(dr.scan)
    assert "supply_rows" in src
    # One analyze_symbol call, not two.
    assert src.count("analyze_symbol(") == 1


def test_the_scan_publishes_supply_rows_under_their_own_key():
    """`rows` and every consumer of it — the page, the R:R floor, the limit,
    the history ledger — must be untouched by construction."""
    src = inspect.getsource(dr.scan)
    assert '"supply_rows": supply_rows' in src
    assert '"rows": rows' in src


def test_the_rr_floor_and_limit_do_not_touch_the_supply_rows():
    """They filter a demand PLAN. There is no plan on this board."""
    data = {"rows": [{"plan": {"rr": 0.1}}],
            "supply_rows": [{"symbol": "AAA"}, {"symbol": "BBB"}]}
    floored = dr._apply_rr_floor(data, 1.0)
    assert len(floored["rows"]) == 0
    assert len(floored["supply_rows"]) == 2
    limited = dr._apply_limit(floored, 1)
    assert len(limited["supply_rows"]) == 2


def test_the_warming_payload_carries_the_key_so_the_page_never_reads_undefined():
    src = _code(dr.cached_or_warm)
    assert '"supply_rows": []' in src


# ── the board tab ────────────────────────────────────────────────────────────
def test_the_tab_is_registered():
    from chart_maps import board
    assert "supply" in board.TABS


def test_the_board_reads_the_shared_cache_and_never_starts_its_own_scan():
    from chart_maps import board
    src = _code(board.supply_tiles)
    assert "cached_or_warm" in src
    assert "supply_rows" in src
    assert "scan(" not in src


def test_the_tiles_draw_NO_plan_lines():
    """There is no trade here. BUY / STOP / TARGET would invent one."""
    from chart_maps import board
    src = _code(board.supply_tiles)
    for forbidden in ('"BUY"', '"STOP"', '"TARGET"', '"buy"', '"stop"'):
        assert forbidden not in src, f"supply_tiles draws {forbidden}"


def test_the_tab_keeps_its_OWN_disclaimer():
    """The generic study-board line would have overwritten the sentence that
    says this is not a short signal."""
    from chart_maps import board
    src = _code(board.board)
    assert 'out.get("disclaimer") or DISCLAIMER' in src
    assert "not a short signal" in board._supply_disclaimer()
