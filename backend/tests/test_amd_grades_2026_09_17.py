"""AMD: see every grade, filterable, with the numbers he trades on.

Ajay 2026-09-17: *"I think the AMD is my priority honestly. I wanna see all AMD
and also filterable AMD, I think, I wanna know any new stocks are are are
getting manipulated and about to be Distrubuted too ... I am rely on
manipulation.. I wanna use that as an entry the bottom of manipulation.. Feel
free to bring stocks that are getting distributed too but I need to see it as a
filter, Ignore the room thing.. Lot of time it will push though it."*

The sweep already stored every name at every grade — 2,678 rows on 2026-09-17,
of which the board served the 391 `raided` ones and dropped the other 2,287.
Nothing new is measured here; the filter stops throwing the document away and
the tile carries the cycle's own stored levels.

THE MEASUREMENT IS UNCHANGED AND STILL INVERTED (2026-09-14, 3,712 names):
the raid's own claim ran -4.2pp against a like-for-like placebo. Showing more
grades does not make the read better, and nothing here gates, alerts or enters.
"""
from __future__ import annotations

import pytest

from supply_demand import turning_bullish as TB
from chart_maps import board as B


# ── parse_grades: fails OPEN, never 422s a stale bookmark ───────────────────
@pytest.mark.parametrize("spec,expect", [
    (None, None),
    ("", None),
    ("JUNK", None),
    (123, None),
    ("raided", {"raided"}),
    ("raided,marked_up", {"raided", "marked_up"}),
    ("raided+failed", {"raided", "failed"}),
    ("  RAIDED , Basing ", {"raided", "basing"}),
    (["basing"], {"basing"}),
])
def test_parse_grades(spec, expect):
    got = TB.parse_grades(spec, "amd")
    assert (set(got) if got else None) == expect


def test_all_means_every_grade_the_sweep_stores():
    got = TB.parse_grades("all", "amd")
    assert set(got) == {g for g in TB.AMD_GRADES if g != "none"}
    # and "none" is never a choice — it is the absence of a read
    assert "none" not in got


def test_NEGATIVE_a_grade_from_the_other_kind_is_not_honoured():
    """keltner grades must not select AMD rows — they would match nothing and
    hand him an empty board that looks like 'no names qualify'."""
    assert TB.parse_grades("coiled_up", "amd") is None
    assert TB.parse_grades("raided", "keltner") is None


# ── the read on the tile ────────────────────────────────────────────────────
_V = {"grade": "raided", "phase": "manipulation", "raid_price": 902.60,
      "raid_level": 918.8801, "raid_depth_pct": 1.77, "raid_vol_ratio": 1.04,
      "raid_bars_ago": 3, "raid_date": "2026-09-14",
      "base_lo": 918.8801, "base_hi": 1042.4, "base_bars": 8}


def test_the_two_bottoms_are_kept_apart():
    """raid_low is the LOW that printed; raid_level is the edge that was swept.
    They differ by 1.8% on this real row, and collapsing them would put his
    entry 1.8% from where he meant it."""
    r = B._amd_read(_V, 950.0)
    assert r["raid_low"] == 902.60
    assert r["raid_level"] == 918.8801
    assert r["raid_low"] != r["raid_level"]


def test_distance_to_the_manipulation_bottom_and_to_distribution():
    r = B._amd_read(_V, 950.0)
    # price is above the bottom
    assert r["above_raid_low_pct"] == pytest.approx((950.0 - 902.60) / 902.60 * 100, abs=0.01)
    assert r["above_raid_low_pct"] > 0
    # distribution is still overhead
    assert r["to_distribution_pct"] == pytest.approx((1042.4 - 950.0) / 950.0 * 100, abs=0.01)
    assert r["to_distribution_pct"] > 0


def test_a_resolved_cycle_reads_distribution_as_already_through():
    """marked_up: price has closed above the base top, so the distance is
    NEGATIVE rather than absent — 'already through it', not 'unknown'."""
    r = B._amd_read({**_V, "grade": "marked_up", "phase": "distribution"}, 1100.0)
    assert r["to_distribution_pct"] < 0


def test_NEGATIVE_a_basing_row_has_no_raid_and_says_so():
    """Accumulation has not been raided. Those fields must be None, never 0 —
    a 0 would read as 'the bottom is at zero' and sort to the top."""
    r = B._amd_read({"grade": "basing", "phase": "accumulation",
                     "base_lo": 10.0, "base_hi": 12.0, "base_bars": 20}, 11.0)
    assert r["raid_low"] is None and r["raid_level"] is None
    assert r["above_raid_low_pct"] is None
    assert r["raid_bars_ago"] is None
    # but the distribution level IS known from the base top
    assert r["distribution_level"] == 12.0
    assert r["to_distribution_pct"] == pytest.approx((12.0 - 11.0) / 11.0 * 100, abs=0.01)


@pytest.mark.parametrize("bad", [None, {}, "nope", 7])
def test_NEGATIVE_a_junk_verdict_never_raises(bad):
    out = B._amd_read(bad, 100.0)
    assert out is None or out.get("raid_low") is None


def test_NEGATIVE_no_price_leaves_every_distance_unknown():
    r = B._amd_read(_V, None)
    assert r["above_raid_low_pct"] is None
    assert r["to_distribution_pct"] is None
    # the stored levels still ride, because they do not depend on the print
    assert r["raid_low"] == 902.60 and r["distribution_level"] == 1042.4


def test_NEGATIVE_a_zero_price_is_not_divided_by():
    r = B._amd_read(_V, 0)
    assert r["to_distribution_pct"] is None


# ── the board keeps its old default ─────────────────────────────────────────
def test_the_default_board_is_unchanged_turning_only():
    """No grades asked for = exactly what this tab has always served. A filter
    that silently widened the default would change a board he reads daily."""
    import inspect
    src = inspect.getsource(TB.board)
    assert "keep = parse_grades(grades, k)" in src
    assert "else [r for r in rows if r.get(key) == want]" in src


# ── the cycle IN FLIGHT (2026-09-17) ────────────────────────────────────────
#
# Ajay: "Today its not granular we do not show potentially or in the flight
# mani pulation i wanna see those". The stored detector only fires on a
# COMPLETE raid — swept AND closed back inside — so a sweep happening now is
# invisible until tonight. Measured on the live stack that afternoon: of 1,228
# names with a live base, 156 had already swept and reclaimed with the bar
# open, and 172 were below the edge unresolved. APH read `basing` while its day
# low (77.08) sat under its base floor (77.70) and price was back at 78.01.
_BASE = {"base_lo": 100.0, "base_hi": 120.0, "grade": "basing"}


def _snap(price, low):
    return {"last_trade_price": price, "price": price, "low": low}


def test_sweeping_is_below_the_edge_right_now():
    f = B._amd_flight(_BASE, _snap(97.0, 96.0))
    assert f["state"] == "sweeping"
    assert f["to_edge_pct"] < 0
    assert f["swept_today"] is True
    assert f["pierce_pct"] == pytest.approx((100.0 - 96.0) / 100.0 * 100, abs=0.01)


def test_reclaimed_is_swept_today_and_back_inside():
    """APH's shape: the day low pierced the floor, price is back above it, the
    bar has not closed. This is the raid FORMING."""
    f = B._amd_flight(_BASE, _snap(101.0, 98.0))
    assert f["state"] == "reclaimed"
    assert f["swept_today"] is True
    assert f["to_edge_pct"] > 0


def test_holding_never_reached_the_edge_today():
    f = B._amd_flight(_BASE, _snap(110.0, 105.0))
    assert f["state"] == "holding"
    assert f["swept_today"] is False
    assert f["pierce_pct"] is None


def test_NOTHING_in_flight_is_ever_reported_as_confirmed():
    """The bar has not closed. A reclaimed name is a raid forming, not a raid —
    if this ever serves True, the board is calling an unclosed bar a fact."""
    for snap in (_snap(97.0, 96.0), _snap(101.0, 98.0), _snap(110.0, 105.0)):
        assert B._amd_flight(_BASE, snap)["confirmed"] is False


def test_the_distance_to_the_edge_is_a_NUMBER_not_a_bucket():
    """No threshold is picked for "close to the edge" — he sorts the number
    himself. A bucketed field here would be a distance nobody gave."""
    import inspect
    src = inspect.getsource(B._amd_flight)
    for invented in ("0.5", "1.0", "2.0", "3.0", "5.0"):
        assert invented not in src, invented
    f = B._amd_flight(_BASE, _snap(100.5, 100.2))
    assert isinstance(f["to_edge_pct"], float)


@pytest.mark.parametrize("v,snap", [
    ({}, _snap(100.0, 99.0)),                       # no base
    (_BASE, {}),                                    # no live row
    (_BASE, {"last_trade_price": None, "low": 99}),  # no print
    (_BASE, {"last_trade_price": 100.0}),           # no day low
    ({"base_lo": 0}, _snap(100.0, 99.0)),           # zero edge
    (_BASE, _snap(0, 0)),                           # zero price
    (None, None),
])
def test_NEGATIVE_a_missing_input_is_UNKNOWN_never_a_state(v, snap):
    assert B._amd_flight(v, snap) is None


@pytest.mark.parametrize("spec,expect", [
    (None, None), ("", None), ("junk", None), (7, None), ("all", None),
    ("sweeping", {"sweeping"}),
    ("sweeping,reclaimed", {"sweeping", "reclaimed"}),
    ("SWEEPING + holding", {"sweeping", "holding"}),
])
def test_parse_flight_fails_open(spec, expect):
    got = B.parse_flight(spec)
    assert (set(got) if got else None) == expect


def test_the_flight_states_are_the_enforcing_tuple():
    assert set(B.AMD_FLIGHT_STATES) == {"sweeping", "reclaimed", "holding"}
    for st in B.AMD_FLIGHT_STATES:
        assert B.parse_flight(st) == frozenset({st})
