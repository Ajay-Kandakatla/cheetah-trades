"""3-C cheat detector (sepa/cheat.py) — TTLAC §7.

A qualifier is tagged a cheat only when it is a continuation after a >=25%
advance (p.133), sitting in a 10-40% base off its high (p.119), with volume
drying up (p.226) and a tight VCP coil (p.132/134), and NOT yet a volume-
confirmed breakout (p.132 — the cheat is the entry BEFORE the pivot clears).

Host-runnable (py3.9, stdlib only):
    cd backend && python3 -m pytest tests/test_cheat.py -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import cheat


def _row(**over):
    """A canonical 3-C cheat qualifier; override one field to break a pillar."""
    row = {
        "is_candidate": True,
        "is_buyable": False,
        "trend": {"pct_above_low": 60.0, "pct_below_high": 18.0},
        "volume": {"vol_dryup": 0.7},
        "vcp": {"has_base": True, "good_contraction_count": 2},
    }
    # shallow-merge overrides, supporting nested dotted keys like "trend"
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(row.get(k), dict):
            row[k] = {**row[k], **v}
        else:
            row[k] = v
    return row


# ── the positive case ───────────────────────────────────────────────────────

def test_canonical_cheat_is_detected():
    out = cheat.detect(_row())
    assert out["is_cheat"] is True
    assert out["off_high_pct"] == 18.0
    assert out["cite"].startswith("TTLAC §7")
    assert out["reasons"]                       # a human-readable why


def test_shakeout_is_a_bonus_detail_not_a_requirement():
    plain = cheat.detect(_row())
    assert plain["is_cheat"] is True and plain["shakeout"] is False
    shook = cheat.detect(_row(vcp={"has_base": True, "good_contraction_count": 2,
                                   "undercut_low": True}))
    assert shook["is_cheat"] is True and shook["shakeout"] is True
    assert any("shakeout" in r for r in shook["reasons"])


# ── negatives: each pillar, removed ─────────────────────────────────────────

def test_non_qualifier_is_never_a_cheat():
    assert cheat.detect(_row(is_candidate=False))["is_cheat"] is False


def test_already_buyable_breakout_is_not_a_cheat():
    """The cheat is the entry BEFORE the breakout (p.132) — a volume-confirmed
    buyable name has graduated past it."""
    assert cheat.detect(_row(is_buyable=True))["is_cheat"] is False


def test_at_new_highs_is_a_breakout_not_a_cheat():
    # < 10% off the high → not in a base (p.119)
    assert cheat.detect(_row(trend={"pct_below_high": 4.0}))["is_cheat"] is False


def test_too_deep_a_correction_is_failure_prone_not_a_cheat():
    # > 40% off the high → failure-prone (p.133)
    assert cheat.detect(_row(trend={"pct_below_high": 55.0}))["is_cheat"] is False


def test_no_prior_advance_is_not_a_continuation():
    # < 25% above the 52w low → not the continuation the 3-C requires (p.133)
    assert cheat.detect(_row(trend={"pct_above_low": 12.0}))["is_cheat"] is False


def test_volume_not_drying_up_fails():
    # 10d avg >= 50d avg → no volume contraction (p.226)
    assert cheat.detect(_row(volume={"vol_dryup": 1.1}))["is_cheat"] is False


def test_no_tight_coil_fails():
    assert cheat.detect(_row(vcp={"has_base": True,
                                  "good_contraction_count": 0}))["is_cheat"] is False
    assert cheat.detect(_row(vcp={"has_base": False,
                                  "good_contraction_count": 3}))["is_cheat"] is False


# ── robustness ──────────────────────────────────────────────────────────────

def test_missing_fields_never_crash_and_return_full_schema():
    out = cheat.detect({})
    assert out["is_cheat"] is False
    for key in ("is_cheat", "off_high_pct", "pct_above_low", "vol_dryup",
                "good_contractions", "shakeout", "reasons", "cite"):
        assert key in out


def test_garbage_field_types_are_tolerated():
    out = cheat.detect(_row(trend={"pct_above_low": "n/a", "pct_below_high": None},
                            volume={"vol_dryup": "x"}))
    assert out["is_cheat"] is False
