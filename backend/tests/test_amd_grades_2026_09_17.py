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
