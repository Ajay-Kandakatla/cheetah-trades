"""Russell inclusion watch — the classification table and its percentile
yardstick, locked pure so the EMAT-shaped false positive stays VISIBLE
(a name added after the baseline files still classifies as a candidate;
the payload's baseline note is the honesty valve, not silent magic).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalysts.russell_watch import _pctl, classify  # noqa: E402

P25_R2000 = 250e6      # pretend p25 of current R2000 caps
P10_R1000 = 5_000e6    # pretend p10 of current R1000 caps (live run: ~$5.0B)


# ── classify ────────────────────────────────────────────────────────────────
def test_outsider_above_the_band_is_an_r2000_add_candidate():
    hit = classify("EMAT", 600e6, in_r1000=False, in_r3000=False,
                   r2000_p25=P25_R2000, r1000_p10=P10_R1000)
    assert hit == {"board": "add_r2000", "cap": 600e6}


def test_outsider_below_the_band_is_nothing():
    assert classify("TINY", 80e6, False, False, P25_R2000, P10_R1000) is None


def test_r2000_member_sized_for_r1000_is_a_promotion():
    hit = classify("GROWN", 6_000e6, in_r1000=False, in_r3000=True,
                   r2000_p25=P25_R2000, r1000_p10=P10_R1000)
    assert hit == {"board": "promote_r1000", "cap": 6_000e6}


def test_r2000_member_not_sized_up_is_nothing():
    assert classify("MID", 3_000e6, False, True, P25_R2000, P10_R1000) is None


def test_r1000_member_is_never_a_candidate_even_when_huge():
    assert classify("AAPL", 3_500_000e6, True, True, P25_R2000, P10_R1000) is None


def test_no_cap_data_is_nothing_not_a_guess():
    assert classify("X", None, False, False, P25_R2000, P10_R1000) is None
    assert classify("X", 0, False, False, P25_R2000, P10_R1000) is None


def test_missing_band_yardstick_refuses_rather_than_admits_everyone():
    # p25 unknown (empty member cap sample) -> no add candidates at all
    assert classify("Y", 600e6, False, False, None, P10_R1000) is None
    assert classify("Z", 9_999e6, False, True, P25_R2000, None) is None


def test_giant_outsider_is_rejected_as_almost_certainly_ineligible():
    # The first live run's "top adds" were ASML/BABA/RY — foreign names
    # Russell will never take. An outsider already sized for the R1000 is
    # a foreign/ineligible tell, not a missed add.
    assert classify("ASML", 651_000e6, False, False, P25_R2000, P10_R1000) is None


def test_emat_shaped_outsider_inside_the_window_is_an_add():
    # EMAT at ~$2.4B: above p25 of R2000, below p10 of R1000 — exactly the
    # window. (It is ALSO the known false-positive shape: already
    # preliminarily added effective 2026-09-21, baseline files older.)
    hit = classify("EMAT", 2_400e6, False, False, P25_R2000, P10_R1000)
    assert hit == {"board": "add_r2000", "cap": 2_400e6}


# ── _pctl ───────────────────────────────────────────────────────────────────
def test_pctl_nearest_rank_on_sorted_values():
    vals = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert _pctl(vals, 0) == 10.0
    assert _pctl(vals, 50) == 30.0
    assert _pctl(vals, 100) == 50.0
    assert _pctl(vals, 25) == 20.0


def test_pctl_empty_is_none():
    assert _pctl([], 25) is None
