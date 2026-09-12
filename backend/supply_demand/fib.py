"""Fibonacci retracements and extensions, anchored to the last major swing.

Ajay 2026-09-12: *"Fibonacci so with a checkbox I may be like we already do to
toggle on and off"*, and, asked what to anchor to, he chose **the last major
swing** with retracements 0.382 / 0.5 / 0.618 / 0.786 **and** extensions
1.272 / 1.618, drawn on the expanded chart only.

SOURCE STATUS — the same honesty as the rest of this app
────────────────────────────────────────────────────────
Fibonacci levels are chart CONVENTION. There is no book in Ajay's library that
backs them the way Minervini backs the trend template, and **nothing here has
been measured forward**. They are drawn because he asked to see them, and they
gate nothing: no scan reads this module, no alert fires from it, no lane buys
on it. `CITED = False`, same as `supply_demand/smc.py`.

Two of the six numbers are not even Fibonacci. **0.5 is a half, not a ratio in
the sequence**, and 1.272 is the square root of 1.618. Both are conventional
and both are labelled as such rather than quietly presented as maths.

THE ANCHOR
──────────
The leg runs **origin A → end B**, taken from `smc.swing_points` — deliberately
the SAME pivot detector that produces the BOS / CHoCH reads, so a fib level can
never disagree with the structure line drawn beside it.

  * the most recent confirmed swing high and swing low are found;
  * whichever is LATER is the leg's end B, the other is its origin A;
  * so an up-leg (low → high) retraces downward from the high, and a down-leg
    (high → low) retraces upward from the low.

A leg must clear `MIN_LEG_ATR` of ATR-14 to anchor anything. Without that floor
a four-bar wiggle becomes the anchor and the levels move every session, which
is the single most common way this overlay turns into noise.

THE ARITHMETIC, written out so it is auditable without a platform
────────────────────────────────────────────────────────────────
  retracement r:  price = B - r * (B - A)     r = 0 is B, r = 1 is A
  extension   e:  price = A + e * (B - A)     e = 1 is B, e > 1 is beyond it

For an up-leg that puts the retracements between the high and the low, and the
extensions above the high — a target read that sits next to the supply bands.
For a down-leg both flip, with no special-casing: the signs take care of it.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("supply_demand.fib")

# CONVENTION, every one of them. 0.5 is a half, not a Fibonacci ratio; 1.272 is
# sqrt(1.618). Kept because they are what he reads on every other platform.
RETRACEMENTS = (0.382, 0.5, 0.618, 0.786)
EXTENSIONS = (1.272, 1.618)
# The golden pocket — 0.618 to 0.786 — is the zone most SMC material treats as
# the discount/premium region. Marked so the UI can shade it, not gated on.
POCKET = (0.618, 0.786)

SWING_WINDOW = 3          # same pivot width smc.py uses — shared on purpose
MIN_LEG_ATR = 2.0         # a leg under this is a wiggle, not a swing
MIN_LEG_PCT = 3.0         # ...and a floor for names whose ATR is unreadable

CITED = False
SOURCE_NOTE = ("Fibonacci retracement/extension — chart convention, no cited "
               "source, never measured forward. Display only: nothing in the "
               "app gates on these levels.")


def _f(v) -> Optional[float]:
    """float(v) or None — NaN and inf are None. A NaN anchor would propagate
    into every level and each one would then pass any <= comparison."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (f != f or f in (float("inf"), float("-inf"))) else f


def last_swing(df, window: int = SWING_WINDOW,
               min_leg_atr: float = MIN_LEG_ATR) -> Optional[dict]:
    """The leg to anchor on, or None when nothing qualifies.

    Returns {"a", "b", "a_idx", "b_idx", "direction", "range"} where `a` is the
    origin and `b` the end. `direction` is "up" when the leg ran low → high.
    None is a real answer — a chart with no qualifying swing draws no levels
    rather than anchoring on noise.
    """
    if df is None or len(df) < 2 * window + 2:
        return None
    try:
        from supply_demand.smc import swing_points
        lows, highs = swing_points(df, window)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("fib: swing detection failed: %s", exc)
        return None
    if not lows or not highs:
        return None

    li, lp = lows[-1]
    hi, hp = highs[-1]
    if li == hi:
        return None
    if hi > li:
        a_idx, a, b_idx, b, direction = li, lp, hi, hp, "up"
    else:
        a_idx, a, b_idx, b, direction = hi, hp, li, lp, "down"

    a, b = _f(a), _f(b)
    if a is None or b is None:
        return None
    rng = abs(b - a)
    if rng <= 0:
        return None

    # The size floor. ATR first; a percentage of price as the fallback so a
    # name with an unreadable ATR is still held to SOMETHING rather than
    # silently anchoring on a four-bar wiggle.
    atr = None
    try:
        from supply_demand.patterns import atr as _atr
        atr = _f(_atr(df, 14))
    except Exception:                                          # noqa: BLE001
        atr = None
    if atr and atr > 0:
        if rng < min_leg_atr * atr:
            return None
    else:
        ref = _f(b) or 0.0
        if not ref or (rng / abs(ref)) * 100.0 < MIN_LEG_PCT:
            return None

    return {"a": a, "b": b, "a_idx": int(a_idx), "b_idx": int(b_idx),
            "direction": direction, "range": rng,
            "bars_ago": int(len(df) - 1 - max(a_idx, b_idx))}


def levels(df, window: int = SWING_WINDOW,
           min_leg_atr: float = MIN_LEG_ATR) -> list:
    """[{ratio, price, label, kind, pocket}] for the last major swing, or [].

    `kind` is "retracement" or "extension"; `pocket` marks 0.618 and 0.786.
    Ordered high price first so the caller can draw top-down without sorting.
    """
    leg = last_swing(df, window, min_leg_atr)
    if not leg:
        return []
    a, b = leg["a"], leg["b"]
    out = []
    for r in RETRACEMENTS:
        out.append({"ratio": r, "price": round(b - r * (b - a), 4),
                    "label": "fib %.3f" % r, "kind": "retracement",
                    "pocket": r in POCKET})
    for e in EXTENSIONS:
        out.append({"ratio": e, "price": round(a + e * (b - a), 4),
                    "label": "fib %.3f" % e, "kind": "extension",
                    "pocket": False})
    out = [x for x in out if _f(x["price"]) is not None and x["price"] > 0]
    out.sort(key=lambda x: -x["price"])
    return out


def chart_lines(df, window: int = SWING_WINDOW,
                min_leg_atr: float = MIN_LEG_ATR) -> list:
    """The levels as chart-tile lines: {price, label, tone}.

    Tone is always "fib" so `chartOverlays` can route the whole family to one
    checkbox — never "target" or "buy", which would fold these into the Trade
    lines toggle and make them look like an instruction. They are not one."""
    return [{"price": x["price"], "label": x["label"], "tone": "fib",
             "ratio": x["ratio"], "fib_kind": x["kind"], "pocket": x["pocket"]}
            for x in levels(df, window, min_leg_atr)]
