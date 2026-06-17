"""Minervini + Bonde buy verdict — a single PASS / PARTIAL / FAIL read that
folds the app's two independent "should I buy this?" frameworks into one badge
shown on every stock.

Two sources of truth, both already cited and tested elsewhere in the codebase —
this module only *combines* them, it invents no new thresholds:

  1. **Minervini — "is this a buyable stock?"** (Mark Minervini, *Trade Like a
     Stock Market Wizard*, 2013).
       - **Qualifier** (p.79): *"The Trend Template is a qualifier. If a stock
         doesn't meet the Trend Template criteria, I don't consider it."* This is
         the screening verdict — the row's ``is_candidate`` / ``qualifier`` flag
         (Stage-2 leader, RS ≥ 70, 8/8 trend, liquid). It answers *"is this even a
         Minervini-grade stock?"*
       - **Buyable now** (pp.198-203): the timed buy trigger — ``is_buyable`` —
         a volume-confirmed breakout near the pivot. This is *"buy it TODAY,"* a
         sub-state of a qualifier, not a separate pass gate (a great stock spends
         most days set up but not triggered).
     So the Minervini pillar **passes on the qualifier** (p.79) and separately
     reports ``buyable_now`` (pp.198-203). See ``scanner._is_buyable`` /
     ``scanner.scan_universe`` for the gate definitions this reads.

  2. **Bonde — "is the sales growth there?"** (Pradeep Bonde / Stockbee,
     sales-driven). Reads the already-computed ``fundamentals.sales`` block
     (``sepa/sales.py``): his documented 5% floor / 25% preferred / 100%
     "explosive" tiers, plus his two NAMED catalysts — acceleration and
     consecutive-quarter consistency. Full sourcing + the QoQ-vs-YoY caveat live
     in ``docs/sepa/sales_confidence_methodology.md``.
     The Bonde pillar **passes** when growth clears his 5% floor AND shows his
     character (accelerating OR ≥ 2 consecutive growth quarters). Sales data only
     exists on the enriched (top-N) set, so for un-enriched rows the pillar is
     ``None`` ("pending"), never a silent fail.

COMBINED status (the green/amber/red the user asked for):
  - 🟢 ``pass``    — Minervini qualifier passes (it IS a buyable-grade stock).
                     ``both_pass`` is set when Bonde ALSO passes (sales-confirmed).
                     When sales aren't enriched yet, status is still ``pass`` with
                     ``sales_pending=True`` so the badge is honest, not faked.
  - 🟡 ``partial`` — exactly ONE pillar passes (price-side good but sales fail, or
                     sales good but not a Minervini setup). Both per-pillar badges
                     show so the user sees which side disagrees.
  - 🔴 ``fail``    — neither passes.

This is **DISPLAY-only and additive** — exactly like ``group_leadership``. It
reads existing row fields and never alters ``score`` / ``is_candidate`` /
``is_buyable`` / ``SCORE_WEIGHTS``, so the SEPA_CONTRACTS §4 sum-to-100 invariant
is untouched. Constants below are LOCKED in tests/test_sepa_contracts.py.
"""
from __future__ import annotations

from typing import Optional

# Bonde's documented sales floor / preferred level — re-exported from sales.py so
# the verdict can't drift from the score it reads. (LOCKED in test_sepa_contracts.)
from sepa.sales import SALES_FLOOR_PCT, SALES_PREFERRED_PCT

# Bonde "character" gate: a name clears his floor AND shows acceleration OR at
# least this many consecutive positive-YoY quarters (his named consistency
# catalyst). 2 = a back-to-back growth trend, the minimum that reads as a trend
# rather than a one-quarter blip. Configured here (Bonde names the catalysts but
# publishes no consecutive-quarter count); chosen, not a Bonde number.
BONDE_MIN_CONSEC_Q = 2

# Field this module writes onto each row (additive; the v1 formula ignores it).
VERDICT_KEY = "buy_verdict"


def _minervini_pillar(row: dict) -> dict:
    """Minervini buyable-stock pillar (p.79 qualifier; pp.198-203 buy point)."""
    qualifier = bool(row.get("is_candidate") or row.get("qualifier"))
    buyable_now = bool(row.get("is_buyable"))
    stage = row.get("stage") or {}
    stage_num = stage.get("stage") if isinstance(stage, dict) else None

    if not qualifier:
        reason = "fails the Trend Template — not a Stage-2 leader (p.79)"
    elif buyable_now:
        reason = "qualifier AND a volume-confirmed breakout at the pivot — buyable now (pp.198-203)"
    else:
        reason = "qualifier (Stage-2 leader, p.79) — watch for the breakout trigger (pp.198-203)"

    return {
        "passed": qualifier,
        "buyable_now": buyable_now,
        "stage": stage_num,
        "reason": reason,
        "cite": "Minervini, Trade Like a Stock Market Wizard, p.79 (qualifier); pp.198-203 (buy point)",
    }


def _bonde_pillar(row: dict) -> dict:
    """Bonde sales pillar — reads fundamentals.sales (sepa/sales.py)."""
    fundamentals = row.get("fundamentals") or {}
    sales = fundamentals.get("sales") if isinstance(fundamentals, dict) else None
    sales = sales or {}
    score = sales.get("score")

    # No sales score → not enriched (or < 5 quarters of history). Pending, NOT a
    # fail — we simply don't know yet. Rule #1: never fake a verdict from no data.
    if score is None:
        return {
            "passed": None,
            "pending": True,
            "tier": sales.get("tier", "unknown"),
            "score": None,
            "growth_yoy_pct": sales.get("growth_yoy_pct"),
            "reason": "sales not enriched yet (top-N only, or < 5 quarters of revenue history)",
            "cite": "Pradeep Bonde / Stockbee — see docs/sepa/sales_confidence_methodology.md",
        }

    g = sales.get("growth_yoy_pct")
    accel = bool(sales.get("accelerating"))
    consec = int(sales.get("consecutive_growth_q") or 0)
    tier = sales.get("tier", "unknown")

    cleared_floor = bool(g is not None and g >= SALES_FLOOR_PCT)
    has_character = accel or consec >= BONDE_MIN_CONSEC_Q
    passed = bool(cleared_floor and has_character)
    strong = bool(g is not None and g >= SALES_PREFERRED_PCT)  # his "preferred" 25%+

    if not cleared_floor:
        reason = f"sales below Bonde's {SALES_FLOOR_PCT:.0f}% floor ({_pct(g)} YoY)"
    elif not has_character:
        reason = (f"growing ({_pct(g)} YoY) but not accelerating and < "
                  f"{BONDE_MIN_CONSEC_Q} consecutive growth quarters")
    elif strong:
        reason = f"sales {_pct(g)} YoY ≥ Bonde's 25% preferred, with {'acceleration' if accel else f'{consec}q consistency'}"
    else:
        reason = f"sales {_pct(g)} YoY clears the 5% floor, with {'acceleration' if accel else f'{consec}q consistency'}"

    return {
        "passed": passed,
        "pending": False,
        "strong": strong,
        "tier": tier,
        "score": score,
        "growth_yoy_pct": g,
        "accelerating": accel,
        "consecutive_growth_q": consec,
        "sales_led": sales.get("sales_led"),
        "reason": reason,
        "cite": "Pradeep Bonde / Stockbee — 5% floor / 25% preferred / 100% explosive (docs/sepa/sales_confidence_methodology.md)",
    }


def _pct(v: Optional[float]) -> str:
    if v is None:
        return "—"
    return f"{'+' if v > 0 else ''}{v}%"


def compute(row: dict) -> dict:
    """Combine the two pillars into one PASS / PARTIAL / FAIL verdict.

    Pure read over existing row fields — returns a dict, never mutates ``row``.
    """
    m = _minervini_pillar(row)
    b = _bonde_pillar(row)

    m_pass = m["passed"]
    b_pass = b["passed"]  # True / False / None(pending)

    both_pass = bool(m_pass and b_pass is True)
    sales_pending = b_pass is None

    if m_pass and (b_pass is True or b_pass is None):
        # Minervini carries the price-side verdict; Bonde confirms or is pending.
        status = "pass"
    elif m_pass or b_pass is True:
        # Exactly one side green — the pillars disagree.
        status = "partial"
    else:
        status = "fail"

    tone = {"pass": "#10b981", "partial": "#eab308", "fail": "#f87171"}[status]
    icon = {"pass": "🟢", "partial": "🟡", "fail": "🔴"}[status]

    if status == "pass":
        if both_pass and m["buyable_now"]:
            label = "BUY — Minervini + sales, breakout live"
        elif both_pass:
            label = "PASS — Minervini + sales confirm"
        elif sales_pending:
            label = "PASS — Minervini (sales n/a)"
        else:
            label = "PASS — Minervini setup"
    elif status == "partial":
        if m_pass:
            label = "PARTIAL — Minervini ✓ · sales ✗"
        else:
            label = "PARTIAL — sales ✓ · Minervini ✗"
    else:
        label = "FAIL — neither side confirms"

    return {
        "status": status,           # pass / partial / fail
        "label": label,
        "icon": icon,
        "tone": tone,
        "both_pass": both_pass,     # the strongest green: both frameworks agree
        "buyable_now": m["buyable_now"],
        "sales_pending": sales_pending,
        "minervini": m,
        "bonde": b,
    }


def annotate(rows: list[dict]) -> list[dict]:
    """Mutate each scan row IN PLACE with ``row['buy_verdict'] = compute(row)``.

    Mirrors ``group_leadership.annotate`` — additive, DISPLAY-only, safe on the
    daily hot path. Call it AFTER enrichment so the top-N rows carry
    ``fundamentals.sales`` (Bonde pillar); un-enriched rows get a Minervini-only
    verdict with the sales pillar pending. Returns the same list for convenience.
    """
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            r[VERDICT_KEY] = compute(r)
        except Exception:
            # Never let a display annotation break a scan (Rule: additive only).
            r[VERDICT_KEY] = None
    return rows
