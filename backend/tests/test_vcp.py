"""Behavioral contracts for the VCP detector (backend/sepa/vcp.py).

Synthetic price series — no network, no Mongo. These lock the 2026-06-01
base-window rewrite: base depth + contractions are measured on the RECENT
contracting consolidation (book pp.197-205: "the contractions will be smaller
from left to right as supply is absorbed", p.205), NOT high-to-low across the
whole 325-bar window.

`test_measures_recent_base_not_full_window` is the headline regression — it is
the test that would have caught the original bug where every momentum leader
read as a 60-94% "base" and produced ZERO VCP setups.
"""
from __future__ import annotations

import pandas as pd

from sepa import vcp


def _df(prior_low, base_levels, advance_bars=320, leg_bars=10, vol=1000, vol_final=None):
    """Build a close+volume series: a prior advance from ``prior_low`` up to the
    base's left-side high, then legs through ``base_levels`` (alternating
    high / low / high / low ...). Sized to clear detect()'s 335-bar minimum.
    """
    seq = [prior_low + (base_levels[0] - prior_low) * k / (advance_bars - 1) for k in range(advance_bars)]
    for i in range(len(base_levels) - 1):
        a, b = base_levels[i], base_levels[i + 1]
        seq += [a + (b - a) * k / leg_bars for k in range(1, leg_bars + 1)]
    vols = [vol] * len(seq)
    if vol_final is not None:
        for j in range(len(seq) - leg_bars, len(seq)):
            vols[j] = vol_final
    return pd.DataFrame({"close": seq, "volume": vols})


def test_detects_clean_vcp():
    # Book pp.198-199 worked example: 25% -> 15% -> 8% contractions.
    info = vcp.detect(_df(50, [100, 75, 95, 80.75, 92, 84.6, 91]))
    assert info["has_base"] is True
    assert info["n_contractions"] == 3
    assert 20 <= info["base_depth_pct"] <= 30        # ~25% (first/deepest contraction)
    assert info["tight_right_side"] is True


def test_measures_recent_base_not_full_window():
    """REGRESSION (the 2026-06-01 bug): a leader up ~900% over the year with a
    tight recent base must read the BASE depth (~20%), not the 16-month range
    (~90%). The old code flagged it too_deep and returned has_base=False."""
    info = vcp.detect(_df(10, [100, 80, 95, 88, 93]))   # +900% advance, then 20%/7% base
    assert info["has_base"] is True
    assert info["base_depth_pct"] < 40                  # NOT ~90%
    assert info["too_deep"] is False


def test_rejects_deep_base():
    info = vcp.detect(_df(50, [100, 50, 90, 80, 88]))   # first contraction 50%
    assert info["has_base"] is False
    assert info["too_deep"] is True
    assert info["base_depth_pct"] >= 40


def test_rejects_non_tightening():
    # Volatility EXPANDING (8% then 18%) is not a contraction pattern.
    info = vcp.detect(_df(50, [100, 92, 98, 80, 95]))
    assert info["has_base"] is False


def test_rejects_flat_line():
    # <5% total range = a flat drift / low-vol name, not a real contraction.
    info = vcp.detect(_df(50, [100, 97, 99.5, 98, 99]))
    assert info["has_base"] is False
    assert info["base_depth_pct"] < 5


def test_requires_minimum_history():
    # detect() needs >=335 bars (65-week max base + buffer, book p.212).
    short = pd.DataFrame({"close": list(range(100)), "volume": [1] * 100})
    assert vcp.detect(short) is None


def test_requires_prior_advance():
    # A base must form AFTER an advance (book p.197). With ~1% prior advance the
    # pivot-quality gate fails, so it isn't a buyable base.
    info = vcp.detect(_df(99, [100, 80, 95, 88, 93]))
    assert info["pivot_quality_ok"] is False
    assert info["has_base"] is False


def test_volume_drying_flag():
    # Lighter volume in the final contraction -> volume_drying True (book p.205:
    # volume contracts as supply is absorbed).
    base = [100, 75, 95, 80.75, 92, 84.6, 91]
    dry = vcp.detect(_df(50, base, vol=1000, vol_final=300))
    wet = vcp.detect(_df(50, base, vol=1000, vol_final=1000))
    assert dry["volume_drying"] is True
    assert wet["volume_drying"] is False


def test_tightness_score_bands():
    # Textbook tight VCP: 24% -> 12% -> 5%, volume drying, price at the pivot.
    base = [{"depth_pct": 24}, {"depth_pct": 12}, {"depth_pct": 5}]
    s, band, drivers = vcp._tightness_score(base, 5.0, 24.0, True, 3, 100.0, 99.0)
    assert s >= 70 and band == "tight"
    assert any("tighten" in d for d in drivers)

    # Loose: barely tightens (20->18), no volume dry-up, far below the pivot.
    s2, band2, _ = vcp._tightness_score(
        [{"depth_pct": 20}, {"depth_pct": 18}], 18.0, 20.0, False, 2, 100.0, 60.0)
    assert s2 < s and band2 in ("early", "developing")

    # No gradable sequence (<2 contractions) -> None.
    assert vcp._tightness_score([{"depth_pct": 10}], 10.0, 10.0, False, 1, None, None) == (None, None, [])


def test_tightness_attached_to_detect_output():
    base = [100, 75, 95, 80.75, 92, 84.6, 91]          # deep->shallow clean VCP
    out = vcp.detect(_df(50, base, vol=1000, vol_final=300))
    assert out["tightness"] is not None and 0 <= out["tightness"] <= 100
    assert out["tightness_band"] in ("tight", "developing", "early")
