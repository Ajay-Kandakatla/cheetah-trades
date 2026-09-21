"""Behavioral contracts for the Sales Confidence score (backend/sepa/sales.py).

Whose number is whose: the 5% floor is his (Stockbee 2007); 25% is THIS APP'S
mid-tier; 100% is the boundary of his 2010 "Sales 100% plus" category.
Figures that failed source verification and are not used: 30% and "MAGNA 53+".
His own 2025 two-quarter revenue figure is his and ships as a pick leg.
See docs/sepa/sales_confidence_methodology.md. Synthetic series; no network.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from sepa import sales


def _series(yoy_recent):
    """Newest-first quarterly revenue series whose YoY[i] == yoy_recent[i] %.
    Older 4 quarters are a flat base of 100; the recent 4 are base*(1+yoy)."""
    base = [100.0, 100.0, 100.0, 100.0]
    recent = [100.0 * (1 + p / 100.0) for p in yoy_recent]
    return recent + base   # Q0..Q3 (newest) then Q4..Q7 (a year ago)


def test_explosive_sales_scores_high():
    info = sales.compute(_series([120, 110, 100, 90]))   # ~120% YoY, accelerating
    assert info["tier"] == "explosive"
    assert info["growth_yoy_pct"] >= 100
    assert info["accelerating"] is True
    assert info["score"] >= 90


def test_strong_sales_25_to_100():
    info = sales.compute(_series([40, 38, 35, 30]))
    assert info["tier"] == "strong"
    assert 55 <= info["score"] <= 100


def test_below_floor_scores_weak():
    # Below Bonde's 5% floor — the accel/consistency bonuses must NOT lift it.
    info = sales.compute(_series([3, 2, 1, 1]))
    assert info["tier"] == "weak"
    assert info["score"] < 40


def test_declining_sales():
    info = sales.compute(_series([-10, -5, 0, 5]))
    assert info["tier"] == "declining"
    assert info["growth_yoy_pct"] < 0
    assert info["score"] < 25


def test_acceleration_flag():
    accel = sales.compute(_series([40, 20, 15, 10]))   # 40 now vs 20 prior
    decel = sales.compute(_series([20, 40, 35, 30]))   # 20 now vs 40 prior
    assert accel["accelerating"] is True
    assert decel["accelerating"] is False


def test_consistency_counts_consecutive_growth():
    assert sales.compute(_series([30, 25, 20, 15]))["consecutive_growth_q"] == 4
    assert sales.compute(_series([30, -5, 20, 15]))["consecutive_growth_q"] == 1


def test_sales_led_flag():
    led = sales.compute(_series([50, 40, 30, 20]), eps_growth_q=10)     # sales 50 > eps 10
    not_led = sales.compute(_series([50, 40, 30, 20]), eps_growth_q=80)
    assert led["sales_led"] is True
    assert not_led["sales_led"] is False


def test_insufficient_history_is_none():
    assert sales.compute([100, 101, 102])["score"] is None    # < 5 quarters
    assert sales.compute([])["score"] is None


def test_thresholds_locked():
    assert sales.SALES_FLOOR_PCT == 5.0
    assert sales.SALES_PREFERRED_PCT == 25.0
    assert sales.SALES_EXPLOSIVE_PCT == 100.0


# The frozen AST pin — recompute ONLY with Ajay's nod (see the guard docstring).
SALES_AST_SHA256 = "e923e1a753f912c8370a40430dfcd4f853deaf7bba68f8c78408abafcffe27d3"

SALES_PY = Path(__file__).resolve().parents[1] / "sepa" / "sales.py"


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    """Drop every module/class/function docstring node, in place."""
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            node.body = body[1:] or [ast.Pass()]
    return tree


def _ast_hash(source: str) -> str:
    tree = _strip_docstrings(ast.parse(source))
    dumped = ast.dump(tree, annotate_fields=True, include_attributes=False)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def test_SOURCE_GUARD_sales_arithmetic_frozen_hash():
    """sepa/sales.py's ARITHMETIC is frozen to a literal hash pinned here.

    Comments and docstrings may change freely — comments never enter the AST and
    every docstring is stripped before hashing, so a reword or a reflow that
    changes no node is free. Any change to a CONSTANT, a SIGNATURE or a BODY
    moves the hash: re-set the pin only in a commit whose message names the
    arithmetic change and Ajay's nod (Rule #10). A venv Python upgrade can also
    move `ast.dump` output — re-pin with that reason stated.

    This replaces a HEAD-byte comparison, which was vacuous the moment the
    change it guarded was committed. No git call, no skip: it bites every run.
    """
    assert _ast_hash(SALES_PY.read_text()) == SALES_AST_SHA256


def test_NEGATIVE_sales_frozen_hash_bites_on_a_constant_change():
    """Mutating a tier constant MUST move the hash — proves the pin is real."""
    mutated = SALES_PY.read_text().replace("SALES_PREFERRED_PCT = 25.0",
                                           "SALES_PREFERRED_PCT = 26.0", 1)
    assert "SALES_PREFERRED_PCT = 26.0" in mutated       # the mutation applied
    assert _ast_hash(mutated) != SALES_AST_SHA256


def test_NEGATIVE_sales_frozen_hash_ignores_docstrings():
    """Rewording the module docstring must NOT move the hash."""
    src = SALES_PY.read_text()
    head, sep, tail = src.partition('"""')
    body, sep2, rest = tail.partition('"""')
    mutated = head + sep + body + "\nA sentence added by the test.\n" + sep2 + rest
    assert mutated != src
    assert _ast_hash(mutated) == SALES_AST_SHA256
