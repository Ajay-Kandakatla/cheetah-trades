"""Behavioral + regression tests for the Minervini-buyable + Bonde-sales verdict
(sepa/buyable_verdict.py).

This is the combined PASS / PARTIAL / FAIL badge shown on every stock (Ajay
2026-06-16). It only *combines* two already-tested frameworks — Minervini's
qualifier/buyable gate (p.79 / pp.198-203) and Bonde's sales score (sepa/sales.py,
5/25/100) — so the tests below lock the COMBINATION logic and the additive,
display-only contract. See docs/sepa/buyable_verdict_methodology.md.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sepa import buyable_verdict as bv  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────────────
def _row(*, qualifier=False, buyable=False, stage=2, sales=None):
    r = {"is_candidate": qualifier, "is_buyable": buyable, "stage": {"stage": stage}}
    if sales is not None:
        r["fundamentals"] = {"sales": sales}
    return r


def _sales(score, g, accel, consec, tier="strong", led=True):
    return {"score": score, "growth_yoy_pct": g, "accelerating": accel,
            "consecutive_growth_q": consec, "tier": tier, "sales_led": led}


# ── Behavioral: each status path ─────────────────────────────────────────────
def test_both_pass_is_green_pass():
    """Minervini qualifier + Bonde sales both green → status pass, both_pass."""
    v = bv.compute(_row(qualifier=True, buyable=True,
                        sales=_sales(80, 32.0, True, 4)))
    assert v["status"] == "pass"
    assert v["both_pass"] is True
    assert v["buyable_now"] is True
    assert v["minervini"]["passed"] is True
    assert v["bonde"]["passed"] is True
    assert "BUY" in v["label"]            # buyable_now + both pass → BUY label


def test_qualifier_with_failing_sales_is_partial():
    """Price side green but sales below Bonde's 5% floor → PARTIAL, not PASS."""
    v = bv.compute(_row(qualifier=True, buyable=False,
                        sales=_sales(30, 2.0, False, 1, tier="weak")))
    assert v["status"] == "partial"
    assert v["both_pass"] is False
    assert v["minervini"]["passed"] is True
    assert v["bonde"]["passed"] is False
    assert "Minervini ✓" in v["label"]


def test_strong_sales_without_minervini_setup_is_partial():
    """Bonde sales accelerating but NOT a Minervini qualifier → PARTIAL."""
    v = bv.compute(_row(qualifier=False, buyable=False, stage=1,
                        sales=_sales(85, 40.0, True, 3)))
    assert v["status"] == "partial"
    assert v["minervini"]["passed"] is False
    assert v["bonde"]["passed"] is True
    assert "sales ✓" in v["label"]


def test_qualifier_with_sales_pending_is_pass_pending():
    """A qualifier with no enriched sales → PASS (Minervini carries) but flagged
    sales_pending so the badge stays honest rather than faking a sales verdict."""
    v = bv.compute(_row(qualifier=True, buyable=False, sales=None))
    assert v["status"] == "pass"
    assert v["sales_pending"] is True
    assert v["both_pass"] is False
    assert v["bonde"]["passed"] is None
    assert "sales n/a" in v["label"]


def test_neither_side_is_fail():
    v = bv.compute(_row(qualifier=False, buyable=False, stage=4,
                        sales=_sales(10, -5.0, False, 0, tier="declining")))
    assert v["status"] == "fail"
    assert v["minervini"]["passed"] is False
    assert v["bonde"]["passed"] is False


def test_growing_but_no_character_fails_bonde():
    """Bonde needs his CHARACTER (acceleration OR >=2 consecutive growth q): a
    name growing +12% but decelerating with only 1 consecutive q does NOT pass."""
    v = bv.compute(_row(qualifier=True,
                        sales=_sales(45, 12.0, False, 1, tier="steady")))
    assert v["bonde"]["passed"] is False
    assert v["status"] == "partial"


def test_consistency_alone_can_pass_bonde():
    """No acceleration but >=2 consecutive growth quarters above the floor passes
    (Bonde's consistency catalyst), even without acceleration."""
    v = bv.compute(_row(qualifier=True,
                        sales=_sales(55, 14.0, False, 3, tier="steady")))
    assert v["bonde"]["passed"] is True
    assert v["status"] == "pass"


# ── Negative / robustness ────────────────────────────────────────────────────
def test_handles_missing_fields_without_crashing():
    """Empty / malformed rows must degrade to fail, never raise (Rule: an
    additive display annotation can never break a scan)."""
    for bad in [{}, {"stage": None}, {"fundamentals": None},
                {"fundamentals": {"sales": None}}, {"is_candidate": None}]:
        v = bv.compute(bad)
        assert v["status"] in {"pass", "partial", "fail"}
        assert v["minervini"]["passed"] is False  # no qualifier flag → fails


def test_sales_below_floor_never_passes_even_if_accelerating():
    """Regression: acceleration must NOT rescue a name below Bonde's 5% floor —
    a tiny +3% that's 'accelerating' from +1% is still a Bonde fail."""
    v = bv.compute(_row(qualifier=True, sales=_sales(34, 3.0, True, 2, tier="weak")))
    assert v["bonde"]["passed"] is False


# ── Contract: additive / display-only (mirrors group_leadership) ─────────────
def test_annotate_is_additive_and_never_mutates_gates():
    rows = [
        {"symbol": "A", "score": 80, "is_candidate": True, "is_buyable": True},
        {"symbol": "B", "score": 30, "is_candidate": False, "is_buyable": False},
    ]
    snapshot = [(r["score"], r["is_candidate"], r["is_buyable"]) for r in rows]
    bv.annotate(rows)
    for r, snap in zip(rows, snapshot):
        assert (r["score"], r["is_candidate"], r["is_buyable"]) == snap
        assert r["buy_verdict"]["status"] in {"pass", "partial", "fail"}


def test_compute_does_not_mutate_input_row():
    row = _row(qualifier=True, sales=_sales(80, 30.0, True, 4))
    before = dict(row)
    bv.compute(row)
    assert row == before  # compute returns a new dict, never edits the row
    assert "buy_verdict" not in row
