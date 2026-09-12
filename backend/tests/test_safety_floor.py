"""Manipulation-safety floors — behavioral, negative, regression, source guard.

Ajay 2026-09-11: "I wanna be able to find stocks that have explosive sale with
safe entry where there wouldn't be easy manipulation.. By whales.. So make sure
to give me not penny stocks and other safety gates or warn me.. I dont want 10
Million Market Cap stocks too."

The 2026-09-11 audit found trading/entries.py::_evaluate — the ONE function
every stock lane funnels through on its way to the broker — enforced no price
floor, no cap floor, no dollar-volume floor: only `price > 0`. It had already
filled SABR at $2.24. These tests pin the fix.
"""
from __future__ import annotations

import ast
import importlib
import io
import os

import pytest

from trading import safety_floor as SF

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------- behavioral
def test_price_floor_blocks_under_two_dollars():
    assert SF.MIN_SHARE_PRICE == 2.00
    assert SF.price_block(1.99) is not None
    assert SF.price_block(0.74) is not None          # ARAI-class
    assert SF.price_block(2.00) is None              # the floor itself passes
    assert SF.price_block(2.17) is None              # SABR today
    assert SF.price_block(64.77) is None             # AXTI


def test_cap_floor_blocks_a_known_small_cap_and_passes_a_real_one():
    assert SF.cap_block(10_000_000) is not None      # his "10 Million" example
    assert SF.cap_block(SF.MIN_CAP_USD - 1) is not None
    assert SF.cap_block(SF.MIN_CAP_USD) is None
    assert SF.cap_block(3.95e9) is None              # AXTI


def test_unknown_cap_warns_and_never_blocks():
    """DELIBERATE asymmetry with the S/D boards, which fail CLOSED on an
    unknown cap. A board is a discovery surface: hiding an unverifiable name
    costs nothing. The entry path is where a name was already chosen by a lane
    or typed by hand, and a silent refusal there reads as a broken button. He
    asked for "other safety gates or warn me" — this is the warn half."""
    assert SF.cap_block(None) is None
    assert SF.cap_warning(None) is not None
    assert SF.cap_warning(3.95e9) is None


def test_thin_tape_warns_at_two_tiers():
    assert "thin tape" in (SF.liquidity_warning(148_074) or "")   # ARAI
    assert SF.liquidity_warning(9_000_000) is not None            # under $20M
    assert SF.liquidity_warning(30_000_000) is None
    assert SF.liquidity_warning(None) is None


# ------------------------------------------------------------------ negative
def test_nan_and_junk_never_pass_a_gate_by_accident():
    """NaN passes every `<=` and `>=` comparison in Python. A NaN price must
    not slip through the floor as 'not less than $2'."""
    for junk in (float("nan"), float("inf"), float("-inf"), "cheap", None, True):
        assert SF._f(junk) is None, junk
    # NaN cap: unknown, so it warns instead of blocking — but it must never
    # read as a known-big cap.
    assert SF.cap_block(float("nan")) is None
    assert SF.cap_warning(float("nan")) is not None


def test_check_reports_both_halves_without_a_lookup():
    out = SF.check("ARAI", price=0.74, cap=40e6, dollar_vol=148_074,
                   lookup_cap=False)
    assert len(out["blocked"]) == 2                  # price AND cap
    assert out["warnings"]                           # thin tape
    out = SF.check("AXTI", price=64.77, cap=3.95e9, dollar_vol=30e6,
                   lookup_cap=False)
    assert out["blocked"] == [] and out["warnings"] == []


def test_market_cap_lookup_failure_returns_none_not_an_exception():
    """A dead Mongo must warn, never block every entry in the app."""
    from sepa import volume_movers as vm

    orig = vm._shares_coll
    vm._shares_coll = lambda: (_ for _ in ()).throw(RuntimeError("mongo down"))
    try:
        assert SF.market_cap("AXTI") is None
    finally:
        vm._shares_coll = orig
    assert SF.market_cap("") is None


# ---------------------------------------------------------------- regression
def test_evaluate_blocks_a_sub_two_dollar_fill():
    """REGRESSION for the real 2026-09-09 order: SABR filled at $2.24 for
    11,043 shares and stopped out -4.46% / -0.74R. The same lane at $1.90 must
    now be refused BY PRICE, with the reason naming the floor."""
    from trading import entries as EN

    orig_price, orig_cap = EN._live_price, SF.market_cap
    EN._live_price = lambda s: (1.90, "test")
    SF.market_cap = lambda s: 3_000_000_000.0        # cap is fine; price is not
    try:
        blocked, ctx = EN._evaluate("SABR")
        assert any("penny floor" in b for b in blocked), blocked
        assert ctx["market_cap"] == 3_000_000_000.0
    finally:
        EN._live_price, SF.market_cap = orig_price, orig_cap


def test_evaluate_blocks_a_ten_million_dollar_cap():
    from trading import entries as EN

    orig_price, orig_cap = EN._live_price, SF.market_cap
    EN._live_price = lambda s: (14.00, "test")
    SF.market_cap = lambda s: 10_000_000.0
    try:
        blocked, ctx = EN._evaluate("TINY")
        assert any("market cap" in b for b in blocked), blocked
    finally:
        EN._live_price, SF.market_cap = orig_price, orig_cap


def test_evaluate_lets_a_real_name_through_the_floors():
    """NEGATIVE of the two above: AXTI-class inputs add NO floor reason. Other
    checks (disarmed, broker) may still block — this asserts only that none of
    the blocks came from safety_floor."""
    from trading import entries as EN

    orig_price, orig_cap = EN._live_price, SF.market_cap
    EN._live_price = lambda s: (64.77, "test")
    SF.market_cap = lambda s: 3.95e9
    try:
        blocked, ctx = EN._evaluate("AXTI")
        assert not any("penny floor" in b or "market cap" in b for b in blocked)
        assert ctx["warnings"] == []
    finally:
        EN._live_price, SF.market_cap = orig_price, orig_cap


def test_adr_liquidity_no_longer_rescues_a_thin_name_on_share_count():
    """REGRESSION for the OR leg. 200,000 shares of a $0.74 stock is $148k/day
    and used to read liquid=True. Deleting the leg must not also break the
    high-priced low-share names (NVR-class) — those clear on $-volume."""
    import pandas as pd
    from sepa import adr

    def frame(close, volume, n=60):
        return pd.DataFrame({"high": [close * 1.01] * n, "low": [close * 0.99] * n,
                             "close": [close] * n, "volume": [volume] * n})

    thin = adr.liquidity_check(frame(0.74, 200_000))
    assert thin["liquid"] is False, thin
    assert thin["avg_shares"] >= 200_000             # still reported, just inert

    nvr = adr.liquidity_check(frame(6_160.0, 32_000))       # ~$197M/day
    assert nvr["liquid"] is True, nvr

    borderline = adr.liquidity_check(frame(50.0, 400_000))  # exactly $20M/day
    assert borderline["liquid"] is True


# ------------------------------------------------------------- source guards
# These parse the AST rather than grepping text: the first version of this file
# matched its OWN docstring, which explains the deleted code, and reported the
# defect as still present. A guard that can be fooled by prose is not a guard.
def _module_ast(*parts):
    path = os.path.join(HERE, *parts)
    return ast.parse(io.open(path, encoding="utf-8").read(), filename=path), path


def test_entries_calls_the_floors_and_feeds_them_into_blocked():
    """SOURCE GUARD. The floors only work because _evaluate consults them AND
    routes the result into the blocked list. Calling and discarding would pass
    a text grep and change nothing."""
    tree, _ = _module_ast("trading", "entries.py")
    ev = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_evaluate")
    calls = [n for n in ast.walk(ev)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "check"
             and getattr(n.func.value, "id", None) == "safety_floor"]
    assert calls, "_evaluate no longer calls safety_floor.check()"

    extends = [n for n in ast.walk(ev)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
               and n.func.attr == "extend"
               and getattr(n.func.value, "id", None) == "blocked"]
    assert extends, "safety_floor's reasons are computed but never block anything"


@pytest.mark.parametrize("lane", ["auto_entry", "zone_edge_entry",
                                  "catalyst_entry", "hot_pullback_entry"])
def test_every_lane_buys_through_entries_never_the_broker(lane):
    """SOURCE GUARD. _evaluate is the chokepoint only while every lane goes
    through it. A lane that called broker submit_bracket directly would size,
    stop and BUY without ever seeing a floor. Alias-aware: hot_pullback_entry
    imports `entries as TE`, which a literal grep for 'entries.enter(' missed."""
    tree, path = _module_ast("trading", "%s.py" % lane)

    aliases = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and (n.module or "").startswith("trading"):
            for a in n.names:
                if a.name == "entries":
                    aliases.add(a.asname or a.name)
        elif isinstance(n, ast.Import):
            for a in n.names:
                if a.name == "trading.entries":
                    aliases.add(a.asname or "trading")
    assert aliases, "%s does not import trading.entries at all" % lane

    enters = [n for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr == "enter"
              and getattr(n.func.value, "id", None) in aliases]
    assert enters, "%s must buy through entries.enter() or it bypasses the floors" % lane

    direct = [n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr in ("submit_bracket", "submit_stop")]
    assert not direct, ("%s submits %s straight to the broker, skipping every "
                        "safety floor" % (lane, direct))


def test_adr_liquidity_has_no_or_leg():
    """SOURCE GUARD for the deleted share-count escape hatch, by SHAPE: the
    `liquid` assignment must be a single comparison, not a BoolOp."""
    tree, _ = _module_ast("sepa", "adr.py")
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "liquidity_check")
    assigns = [n for n in ast.walk(fn) if isinstance(n, ast.Assign)
               and any(getattr(t, "id", None) == "liquid" for t in n.targets)]
    assert len(assigns) == 1, "liquidity_check assigns `liquid` %d times" % len(assigns)
    value = assigns[0].value
    assert not isinstance(value, ast.BoolOp), (
        "the OR/AND leg is back in liquidity_check — the $-volume floor is "
        "decorative again")
    assert isinstance(value, ast.Compare)
    assert getattr(value.left, "id", None) == "avg_dollar_vol"


def test_cap_floor_agrees_with_the_sd_boards():
    """The entry-path cap floor and the S/D board floors are ONE number."""
    for name in ("supply_demand.zone_store", "supply_demand.demand_alerts",
                 "trading.zone_edge_entry"):
        mod = importlib.import_module(name)
        assert float(mod.MIN_CAP_USD) == float(SF.MIN_CAP_USD), name
