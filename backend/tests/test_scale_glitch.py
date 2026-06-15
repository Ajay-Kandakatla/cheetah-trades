"""Behavioral contract for the decimal-shift / scale-glitch guard
(backend/sepa/prices.py :: ``_is_scale_glitch`` + the patch_latest_closes guard).

REGRESSION for the 2026-06-15 bug: the latest SEPA scan (generated 2026-06-12)
showed KLAC with day_change_pct = -89.45% and dist_200_pct = -81.83%. The cause
was a stored price_cache history left at ~10x decimal scale by an earlier bad
full-history fetch; patch_latest_closes then appended a CORRECT-scale snapshot
bar (254.54) on top of a wrong-scale prior session (~2413), so
``day_change_pct = 254.54 / 2413 - 1`` collapsed to -89.45% and the 200-day MA
inflated to ~$1400 (flipping dist_200_pct from +80% to -81.83%).

The guard refuses to stack a correct bar onto a wrong-scale series: it expires
``cached_at`` so the next read does a full clean refetch (which rewrites the
whole array and heals dist_200 / stage / RS too). ``test_klac_signature_is_a_glitch``
is the headline test that would have caught the bug.

Pure pandas / pure function — no network, no Mongo (same shape as
test_phantom_bar.py).
"""
from __future__ import annotations

import pytest

from sepa import prices


# --- the exact production failure ------------------------------------------

def test_klac_signature_is_a_glitch():
    """HEADLINE: a correct 254.54 close sitting on a ~10x stored prior bar is
    flagged — this is the -89.45% day_change_pct that reached the scan."""
    assert prices._is_scale_glitch(254.54, 2413.6) is True   # correct-on-wrong-scale
    assert prices._is_scale_glitch(2413.6, 254.54) is True   # wrong-on-correct (symmetric)


# --- real moves must NOT trip the guard (negative cases) -------------------

def test_real_daily_move_is_not_a_glitch():
    # KLAC's actual +5.55% session (241.16 -> 254.54): a normal day.
    assert prices._is_scale_glitch(254.54, 241.164) is False


def test_violent_but_real_microcap_move_is_kept():
    # A 4x microcap squeeze ($1.00 -> $4.00) is below the 5x decimal-shift floor.
    # Real moves are preserved; only ~10x scale discontinuities are healed.
    assert prices._is_scale_glitch(4.00, 1.00) is False
    assert prices._is_scale_glitch(1.00, 4.00) is False


def test_flat_and_down_sessions_are_not_glitches():
    assert prices._is_scale_glitch(100.0, 100.0) is False
    assert prices._is_scale_glitch(92.0, 100.0) is False     # -8% red day


# --- boundary at exactly _SCALE_GLITCH_RATIO -------------------------------

def test_boundary_at_threshold():
    r = prices._SCALE_GLITCH_RATIO
    assert prices._is_scale_glitch(r * 10.0, 10.0) is True          # exactly 5x  -> glitch
    assert prices._is_scale_glitch(10.0, r * 10.0) is True          # exactly 1/5x -> glitch
    assert prices._is_scale_glitch(4.99, 1.0) is False              # just under 5x -> kept
    assert prices._is_scale_glitch(1.0, 4.99) is False              # just over 1/5x -> kept


def test_threshold_is_conservative():
    # Well clear of any real daily move, well below a 10x decimal shift.
    assert 3.0 <= prices._SCALE_GLITCH_RATIO <= 9.0


# --- robustness: bad inputs never trip the guard ---------------------------

@pytest.mark.parametrize(
    "a,b",
    [(None, 100.0), (100.0, None), (0.0, 100.0), (100.0, 0.0),
     (-5.0, 100.0), (100.0, -5.0), ("x", 100.0), (100.0, "x")],
)
def test_bad_inputs_are_not_glitches(a, b):
    assert prices._is_scale_glitch(a, b) is False
