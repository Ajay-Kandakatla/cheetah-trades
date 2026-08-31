"""Smart Money Concepts: liquidity sweeps, BOS/CHoCH, order blocks, and the
five-step entry model that composes them.

Ajay 2026-08-29, quoting Brad Goh's mechanical SMC model: identify
liquidity → wait for the sweep → mark the order block → mark the fair
value gap → execute on mitigation (aggressive or conservative).

SOURCE STATUS — the same honesty as the rest of this app
────────────────────────────────────────────────────────
SMC is community-taught (ICT lineage, YouTube educators such as Brad Goh).
There is NO canonical text in Ajay's library the way Minervini's books back
the trend template, or Bulkowski backs the cup. Every definition below is
written out in full so the code is auditable without a source, and every
threshold is labelled CONVENTION. Records carry ``cited: False``.

That is not a reason to skip it — it is a reason to MEASURE it. Every setup
this module grades is written to `learning.observations` and resolved
against real forward prices, so within a few weeks the question "does the
sweep→BOS→OB sequence actually pay on my names" has a number instead of a
YouTube claim.

THE FOUR PRIMITIVES
───────────────────
**Liquidity** sits where stops sit: above a swing high (buy-side) and below
a swing low (sell-side). Those are the levels everyone can see, which is
exactly why they are the levels that get run.

**Liquidity sweep (the trap)** — price trades THROUGH a prior swing extreme
and then closes back on the original side. The wick took the stops; the
close says the move was not accepted. A close beyond the level is a
breakout, not a sweep, and the two mean opposite things — so the close is
the whole test.

**Displacement** — the impulsive move away from the sweep. Required, and
required to be big: `MIN_DISPLACEMENT_ATR` of range. Without it there is no
institutional footprint, just noise wobbling around a level.

**Break of Structure (BOS)** — a CLOSE beyond the most recent opposing
swing point, in the direction of the existing trend: continuation.
**Change of Character (CHoCH)** — the same break but AGAINST the prior
trend: the first evidence the trend has turned. After a sweep it is the
CHoCH that matters, because the sweep is a reversal premise.

**Order block** — the last opposing candle before the displacement: the
last down-candle before an up-move (bullish OB), the last up-candle before
a down-move (bearish OB). The reasoning is that institutional buying had
to be absorbed somewhere, and the last candle printed against the eventual
direction is the best visible proxy for where.

**Fair value gap** — the three-bar imbalance inside the displacement
(supply_demand.patterns). Used here to REFINE the entry inside the order
block, which is Brad Goh's step 4.

THE FIVE-STEP MODEL (`find_setups`)
────────────────────────────────────
  1. map swing structure → where liquidity rests
  2. a sweep of one of those levels, rejected by the close
  3. displacement away from it, confirmed by a BOS/CHoCH close
  4. the order block at the origin of that displacement, plus any FVG
     inside it for refinement
  5. entry when price MITIGATES the zone:
       aggressive    — at the order block's proximal edge
       conservative  — at the FVG inside it, which is deeper and needs
                       price to come further, so it fills less often
     Stop goes beyond the order block's far edge (or, per Brad Goh's
     refinement note, beyond the sweep extreme, which is tighter and is
     reported as `stop_tight`).

QUALITY OVER QUANTITY is the model's own rule, so `grade()` scores each
setup and `find_setups` sorts by it. A sweep with no displacement, no BOS,
or no order block is not a setup and is not returned.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("supply_demand.smc")

# All CONVENTION — no cited source exists for any of these.
SWING_WINDOW = 3             # bars each side for a structural pivot
MIN_DISPLACEMENT_ATR = 1.2   # the impulsive move must be this big vs ATR
SWEEP_LOOKBACK = 60          # bars scanned for sweeps
SWEEP_MAX_AGE = 30           # a sweep older than this is stale context
BOS_MAX_BARS = 12            # BOS must follow the sweep within this
OB_MAX_BARS = 6              # order block sits this close to the displacement
MITIGATION_NEAR_PCT = 1.0    # "price is at the zone" tolerance
STOP_BUFFER_ATR = 0.2
# A stop closer than this to the entry is inside the noise of the bar size
# and will be taken out by wiggle rather than by being wrong. Same lesson
# as the Desk's ASH row (2026-08-28): a tiny stop inflates R without
# improving the trade.
MIN_STOP_ATR = 0.5

CITED = False
SOURCE_NOTE = ("Smart Money Concepts — community-taught (ICT lineage; Ajay "
               "cited Brad Goh's mechanical model 2026-08-29). No canonical "
               "text in the library: every threshold here is this app's "
               "CONVENTION, and every setup is scored forward in the ledger "
               "so the edge is measured rather than assumed.")


def swing_points(df, window: int = SWING_WINDOW) -> tuple:
    """(lows, highs) as [(iloc, price)] — strict local extrema. This is
    where liquidity rests: stops sit under swing lows and over swing highs."""
    lows: list = []
    highs: list = []
    if df is None or len(df) < 2 * window + 1:
        return lows, highs
    try:
        lo = df["low"].to_numpy(dtype=float)
        hi = df["high"].to_numpy(dtype=float)
    except Exception:
        return lows, highs
    for i in range(window, len(df) - window):
        if lo[i] == min(lo[i - window:i + window + 1]):
            lows.append((i, float(lo[i])))
        if hi[i] == max(hi[i - window:i + window + 1]):
            highs.append((i, float(hi[i])))
    return lows, highs


def _atr(df, period: int = 14) -> Optional[float]:
    from supply_demand.patterns import atr
    return atr(df, period)


def liquidity_sweeps(df, *, window: int = SWING_WINDOW,
                     lookback: int = SWEEP_LOOKBACK) -> list:
    """Sweeps in the recent frame, newest first.

    A sweep is a wick THROUGH a prior swing extreme with a close back on
    the original side. A close beyond the level is a breakout and means the
    opposite thing, so the close is what separates them.
    """
    out: list = []
    if df is None or len(df) < 2 * window + 3:
        return out
    lows, highs = swing_points(df, window)
    try:
        hi = df["high"].to_numpy(dtype=float)
        lo = df["low"].to_numpy(dtype=float)
        cl = df["close"].to_numpy(dtype=float)
    except Exception:
        return out
    n = len(df)
    start = max(0, n - lookback)

    for i in range(start, n):
        # sell-side sweep: dips under a prior swing low, closes back above
        for (j, price) in lows:
            if j >= i or (i - j) > lookback:
                continue
            if lo[i] < price and cl[i] > price:
                out.append({"idx": i, "side": "sell_side", "level": price,
                            "level_idx": j, "wick": float(lo[i]),
                            "close": float(cl[i]),
                            "bars_ago": n - 1 - i,
                            "direction": "bullish"})
                break
        # buy-side sweep: pokes over a prior swing high, closes back below
        for (j, price) in highs:
            if j >= i or (i - j) > lookback:
                continue
            if hi[i] > price and cl[i] < price:
                out.append({"idx": i, "side": "buy_side", "level": price,
                            "level_idx": j, "wick": float(hi[i]),
                            "close": float(cl[i]),
                            "bars_ago": n - 1 - i,
                            "direction": "bearish"})
                break
    out.sort(key=lambda s: -s["idx"])
    return out


def structure_breaks(df, *, window: int = SWING_WINDOW) -> list:
    """BOS and CHoCH events, newest first.

    A CLOSE beyond the most recent opposing swing. Labelled BOS when it
    continues the prior leg and CHoCH when it reverses it — the sweep model
    wants the CHoCH, because a sweep is a reversal premise.
    """
    out: list = []
    if df is None or len(df) < 2 * window + 3:
        return out
    lows, highs = swing_points(df, window)
    if not lows or not highs:
        return out
    try:
        cl = df["close"].to_numpy(dtype=float)
    except Exception:
        return out
    n = len(df)
    trend = None
    for i in range(window, n):
        prior_high = [(j, p) for j, p in highs if j < i]
        prior_low = [(j, p) for j, p in lows if j < i]
        if not prior_high or not prior_low:
            continue
        hj, hp = prior_high[-1]
        lj, lp = prior_low[-1]
        if cl[i] > hp:
            kind = "BOS" if trend == "up" else "CHoCH"
            out.append({"idx": i, "kind": kind, "direction": "bullish",
                        "level": hp, "level_idx": hj,
                        "bars_ago": n - 1 - i})
            trend = "up"
        elif cl[i] < lp:
            kind = "BOS" if trend == "down" else "CHoCH"
            out.append({"idx": i, "kind": kind, "direction": "bearish",
                        "level": lp, "level_idx": lj,
                        "bars_ago": n - 1 - i})
            trend = "down"
    out.sort(key=lambda b: -b["idx"])
    return out


def order_blocks(df, *, direction: str = "bullish",
                 min_displacement_atr: float = MIN_DISPLACEMENT_ATR,
                 lookback: int = SWEEP_LOOKBACK) -> list:
    """Order blocks, newest first.

    The last opposing candle before a displacement move: the last down
    candle before an up-move (bullish), the last up candle before a
    down-move (bearish). The displacement is what makes it an order block
    rather than just a red candle — no impulse, no institutional footprint.
    """
    out: list = []
    if df is None or len(df) < 20:
        return out
    a = _atr(df)
    if not a:
        return out
    try:
        op = df["open"].to_numpy(dtype=float)
        hi = df["high"].to_numpy(dtype=float)
        lo = df["low"].to_numpy(dtype=float)
        cl = df["close"].to_numpy(dtype=float)
    except Exception:
        return out
    n = len(df)
    start = max(1, n - lookback)

    for i in range(start, n - 1):
        move = cl[i + 1] - op[i + 1]
        rng = hi[i + 1] - lo[i + 1]
        if rng < a * min_displacement_atr:
            continue
        if direction == "bullish" and move > 0 and cl[i] < op[i]:
            out.append({"idx": i, "kind": "bullish", "lo": float(lo[i]),
                        "hi": float(hi[i]), "open": float(op[i]),
                        "close": float(cl[i]),
                        "displacement_atr": round(rng / a, 2),
                        "bars_ago": n - 1 - i, "source": "order_block"})
        elif direction == "bearish" and move < 0 and cl[i] > op[i]:
            out.append({"idx": i, "kind": "bearish", "lo": float(lo[i]),
                        "hi": float(hi[i]), "open": float(op[i]),
                        "close": float(cl[i]),
                        "displacement_atr": round(rng / a, 2),
                        "bars_ago": n - 1 - i, "source": "order_block"})
    out.sort(key=lambda b: -b["idx"])
    return out


def grade(setup: dict) -> int:
    """0-100. The model's own rule is quality over quantity, so the score
    exists to make "not every sweep is worth trading" operational."""
    score = 40
    if setup.get("break", {}).get("kind") == "CHoCH":
        score += 15                       # a sweep is a reversal premise
    disp = (setup.get("order_block") or {}).get("displacement_atr") or 0
    score += 15 if disp >= 2.0 else (8 if disp >= 1.5 else 0)
    if setup.get("fvg"):
        score += 12                       # refined entry available
    age = (setup.get("sweep") or {}).get("bars_ago", 99)
    score += 10 if age <= 10 else (5 if age <= 20 else 0)
    if setup.get("mitigated"):
        score += 8
    return max(0, min(100, score))


def find_setups(df, *, last_price: Optional[float] = None,
                direction: str = "bullish", limit: int = 3) -> list:
    """The five-step model, composed. Best-graded first.

    Returns [] when any required step is absent — a sweep with no
    displacement, no structure break or no order block is not a setup.
    """
    out: list = []
    if df is None or len(df) < 40:
        return out
    from supply_demand.patterns import fair_value_gaps

    a = _atr(df)
    try:
        last = float(last_price if last_price is not None
                     else df["close"].iloc[-1])
    except (TypeError, ValueError, IndexError):
        return out
    if last <= 0:
        return out

    want = "bullish" if direction == "bullish" else "bearish"
    sweeps = [s for s in liquidity_sweeps(df) if s["direction"] == want
              and s["bars_ago"] <= SWEEP_MAX_AGE]
    if not sweeps:
        return out
    breaks = structure_breaks(df)
    obs = order_blocks(df, direction=want)
    gaps = [g for g in fair_value_gaps(df, last)
            if g["kind"] == ("demand" if want == "bullish" else "supply")]

    for sweep in sweeps:
        # step 3: a structure break in our direction, shortly AFTER the sweep
        brk = next((b for b in breaks
                    if b["direction"] == want
                    and 0 < (b["idx"] - sweep["idx"]) <= BOS_MAX_BARS), None)
        if not brk:
            continue
        # step 3b: the order block at the origin of that displacement
        ob = next((o for o in obs
                   if sweep["idx"] - 2 <= o["idx"] <= brk["idx"]
                   and (brk["idx"] - o["idx"]) <= OB_MAX_BARS), None)
        if not ob:
            continue
        # step 4: an FVG inside or adjacent to the block refines the entry
        fvg = next((g for g in gaps
                    if g["lo"] >= ob["lo"] * 0.98 and g["hi"] <= ob["hi"] * 1.02),
                   None) or next((g for g in gaps if g["bar_index"] >= ob["idx"]),
                                 None)

        if want == "bullish":
            aggressive = ob["hi"]
            stop_full = ob["lo"] - (a or 0) * STOP_BUFFER_ATR
            stop_tight = min(sweep["wick"], ob["lo"]) - (a or 0) * STOP_BUFFER_ATR
            conservative = fvg["lo"] if fvg else ob["lo"]
            mitigated = last <= ob["hi"] * (1 + MITIGATION_NEAR_PCT / 100.0)
        else:
            aggressive = ob["lo"]
            stop_full = ob["hi"] + (a or 0) * STOP_BUFFER_ATR
            stop_tight = max(sweep["wick"], ob["hi"]) + (a or 0) * STOP_BUFFER_ATR
            conservative = fvg["hi"] if fvg else ob["hi"]
            mitigated = last >= ob["lo"] * (1 - MITIGATION_NEAR_PCT / 100.0)

        risk = abs(aggressive - stop_full)
        if risk <= 0:
            continue
        target = (aggressive + risk * 2.0 if want == "bullish"
                  else aggressive - risk * 2.0)

        # Per-entry geometry. The conservative entry is deeper, so against
        # the SAME stop and target it carries a smaller risk and a bigger
        # R — which is the entire reason to wait for it, and the reason
        # Brad Goh's refinement note is about stop placement. Reporting one
        # blended number would hide the trade-off the choice exists for.
        def _leg(entry_price: float, stop_price: float) -> Optional[dict]:
            r = abs(entry_price - stop_price)
            if r <= 0:
                return None
            reward = abs(target - entry_price)
            leg = {"entry": round(entry_price, 4),
                   "stop": round(stop_price, 4),
                   "risk_pct": round(r / entry_price * 100.0, 2),
                   "rr": round(reward / r, 2)}
            # NOISE FLOOR. A deep entry against the same stop produces a
            # huge R arithmetically, but a stop closer than MIN_STOP_ATR of
            # ATR is inside the bar-to-bar noise of this timeframe: it will
            # be taken out by wiggle, not by the idea being wrong. The R is
            # still shown — hiding it would be its own dishonesty — but it
            # is flagged so a 20R never reads as a 20R.
            if a and r < a * MIN_STOP_ATR:
                leg["too_tight"] = True
                leg["warning"] = (
                    f"stop is {r / a:.2f} ATR from entry — inside this "
                    f"timeframe's noise; the R is arithmetic, not a plan")
            return leg

        legs = {
            "aggressive": _leg(aggressive, stop_full),
            "conservative": _leg(conservative, stop_full),
            "aggressive_tight": _leg(aggressive, stop_tight),
        }
        legs = {k: v for k, v in legs.items() if v}
        setup = {
            "direction": want,
            "sweep": sweep,
            "break": brk,
            "order_block": {k: v for k, v in ob.items() if k != "idx"} | {"idx": ob["idx"]},
            "fvg": fvg,
            "mitigated": bool(mitigated),
            "entries": {
                "aggressive": round(aggressive, 4),
                "conservative": round(conservative, 4),
            },
            "stop": round(stop_full, 4),
            "stop_tight": round(stop_tight, 4),
            "target": round(target, 4),
            "legs": legs,
            "risk_pct": round(risk / aggressive * 100.0, 2),
            "rr": 2.0,
            "distance_pct": round((aggressive - last) / last * 100.0, 2),
            "cited": CITED,
            "note": SOURCE_NOTE,
        }
        setup["score"] = grade(setup)
        setup["narrative"] = _narrative(setup)
        out.append(setup)
        if len(out) >= limit * 2:
            break

    out.sort(key=lambda s: -s["score"])
    return out[:limit]


def _narrative(s: dict) -> str:
    sw, br, ob = s["sweep"], s["break"], s["order_block"]
    side = "sell-side" if sw["side"] == "sell_side" else "buy-side"
    return (f"{side} liquidity at {sw['level']:.2f} was swept "
            f"{sw['bars_ago']} bars ago and rejected, then a {br['kind']} "
            f"closed {'above' if s['direction'] == 'bullish' else 'below'} "
            f"{br['level']:.2f}. The {ob['displacement_atr']}x-ATR "
            f"displacement leaves an order block at "
            f"{ob['lo']:.2f}-{ob['hi']:.2f}"
            + (f", refined by an FVG at {s['fvg']['lo']:.2f}-{s['fvg']['hi']:.2f}."
               if s.get("fvg") else "."))
