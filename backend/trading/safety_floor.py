"""Manipulation-safety floors — the ONE place every "is this name safe to
buy" number lives.

Ajay 2026-09-11: "I wanna be able to find stocks that have explosive sale
with safe entry where there wouldn't be easy manipulation.. By whales.. So
make sure to give me not penny stocks and other safety gates or warn me..
I dont want 10 Million Market Cap stocks too.. I want real growing stocks
like AXTI and SABR with genuine sales".

Three floors, deliberately different in KIND:

  MIN_SHARE_PRICE  — HARD block, every lane, no exceptions. A sub-$2 quote
      is where the spread, the promo circuit and the tape games live. The
      2026-09-11 audit found trading/entries.py::_evaluate — the single
      chokepoint every stock lane funnels through — enforced only
      `price > 0`, and it had already filled SABR at $2.24 (11,043 shares,
      stopped out -4.46% / -0.74R). $2 not $5: he named SABR as a name he
      WANTS, and SABR trades at $2.17 today. This floor is a backstop
      against the tail, not a valuation opinion.

  MIN_CAP_USD      — HARD block when the cap is KNOWN and below it; a
      WARNING (never a block) when the cap is unknown. Blocking on unknown
      would silently delete every name whose shares row has not been
      warmed, which is the opposite of safety — it would hide the gap
      instead of showing it. Kept equal to the S/D floor
      (supply_demand/zone_store.MIN_CAP_USD) by
      tests/test_safety_floor.py::test_cap_floor_agrees_with_sd.

  MIN_DOLLAR_VOL   — WARNING only here. It is a hard gate inside
      sepa/adr.liquidity_check (the SEPA qualifier path); on the entry path
      a thin name that already cleared its lane's own rules gets flagged,
      not refused, because the lanes disagree about how thin is too thin
      and a silent block on an entry he asked for is worse than a label.

KNOWN LIMIT — the cap floor is circular: market_cap is shares x last price,
so a pump lifts a name over the floor by pumping it. Measured 2026-09-11:
5 names crossed $700M inside 21 sessions purely on price. The price floor
does not share that defect, which is why it is the hard one.
"""
from __future__ import annotations

import logging
import math
from typing import Optional

log = logging.getLogger("trading.safety_floor")

MIN_SHARE_PRICE = 2.00           # HARD: no lane may buy under this
MIN_CAP_USD = 700_000_000.0      # HARD when known, WARN when unknown
MIN_DOLLAR_VOL = 20_000_000.0    # WARN on the entry path (hard in sepa/adr)
THIN_DOLLAR_VOL = 5_000_000.0    # WARN loudly: whale-movable on one order


def _f(v) -> Optional[float]:
    """float(v) or None — NaN and inf are None (a NaN passes every <=)."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (f != f or math.isinf(f)) else f


def price_block(price) -> Optional[str]:
    """Reason string when the quote is under MIN_SHARE_PRICE, else None.

    An unreadable price is NOT this gate's business — the caller already
    blocks on "no price available"; returning a reason here too would
    double-report the same failure."""
    p = _f(price)
    if p is None:
        return None
    if p < MIN_SHARE_PRICE:
        return ("share price $%.2f is under the $%.2f penny floor — thin "
                "quotes are where the tape games live"
                % (p, MIN_SHARE_PRICE))
    return None


def cap_block(market_cap) -> Optional[str]:
    """Reason string when a KNOWN cap is under MIN_CAP_USD, else None.
    An unknown cap returns None here and a string from cap_warning()."""
    c = _f(market_cap)
    if c is None:
        return None
    if c < MIN_CAP_USD:
        return ("market cap $%.0fM is under the $%.0fM floor — too small to "
                "absorb an institution, too easy for one to move"
                % (c / 1e6, MIN_CAP_USD / 1e6))
    return None


def cap_warning(market_cap) -> Optional[str]:
    """Reason string when the cap is UNKNOWN. Never blocks — see module
    docstring on why unknown must not be fatal."""
    return None if _f(market_cap) is not None else \
        "market cap unknown — the size floor could not be checked"


def liquidity_warning(dollar_vol) -> Optional[str]:
    """Reason string when 50-day average $-volume is thin, else None."""
    d = _f(dollar_vol)
    if d is None:
        return None
    if d < THIN_DOLLAR_VOL:
        return ("thin tape: $%.2fM/day average — one whale order moves this"
                % (d / 1e6))
    if d < MIN_DOLLAR_VOL:
        return ("below the $%.0fM/day institutional floor ($%.2fM/day)"
                % (MIN_DOLLAR_VOL / 1e6, d / 1e6))
    return None


def market_cap(symbol: str) -> Optional[float]:
    """Cap for one symbol from the weekly shares cache — never the provider.
    None on any failure: an unreadable cache must warn, never block."""
    sym = (symbol or "").strip().upper()
    if not sym:
        return None
    try:
        from sepa import volume_movers as vm
        coll = vm._shares_coll()
        if coll is None:
            return None
        doc = coll.find_one({"_id": sym}, {"market_cap": 1}) or {}
        return _f(doc.get("market_cap"))
    except Exception as exc:                       # noqa: BLE001
        log.debug("safety_floor: shares cache read failed for %s: %s", sym, exc)
        return None


def check(symbol: str, price=None, cap=None, dollar_vol=None,
          lookup_cap: bool = True) -> dict:
    """Every floor at once.

    Returns {"blocked": [reason, ...], "warnings": [reason, ...],
             "market_cap": float|None}.
    `cap=None` with lookup_cap=True reads the shares cache; pass the cap
    directly (or lookup_cap=False) when the caller already has it."""
    c = _f(cap)
    if c is None and lookup_cap:
        c = market_cap(symbol)
    blocked = [r for r in (price_block(price), cap_block(c)) if r]
    warnings = [r for r in (cap_warning(c), liquidity_warning(dollar_vol)) if r]
    return {"blocked": blocked, "warnings": warnings, "market_cap": c}
