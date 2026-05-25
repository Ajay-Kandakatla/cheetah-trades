"""Cheat entry scanner — Minervini's three earlier-entry pivots inside a VCP base.

The "Cheat" is buying EARLIER than the textbook pivot — at the low, middle,
or upper portion of the handle (the final contraction of a VCP base). The
trade-off: tighter stop, more risk of failure, but a much better cost basis
when the breakout finally hits.

The three variants — Low Cheat, Mid Cheat, and High Cheat — each emit their
own setup kind so the UI can render them separately and the user can opt
into the aggression level that matches their conviction on a given name.

Algorithm:
  1. Call sepa.vcp.detect(df). If has_base is False, no Cheat — skip.
  2. The "handle range" = [suggested_stop, pivot_buy_price].
  3. Subdivide handle into thirds:
       low_third  = [handle_low, handle_low + range × 0.33]
       mid_third  = [handle_low + range × 0.33, handle_low + range × 0.67]
       high_third = [handle_low + range × 0.67, pivot_buy_price]
  4. Classify by where the current close sits:
       close ≤ low_third_upper  → Low Cheat candidate
       close ≤ mid_third_upper  → Mid Cheat
       close <  pivot           → High Cheat
       close ≥ pivot            → already broke out, no Cheat (use VCP entry)
  5. Compute trigger/stop/target per variant — see _build_*_cheat below.

Expires after 120h (5 trading days). Cheats live longer than gap setups
because the underlying VCP base is stable on a multi-day timescale.

Three public callables:
  - scan_low()  → kind="low_cheat"
  - scan_mid()  → kind="mid_cheat"
  - scan_high() → kind="high_cheat"

CLI `python -m setups.cheat` runs all three with a consolidated push alert.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from . import store, universe

log = logging.getLogger("setups.cheat")


_EXPIRES_HOURS = 120   # 5 trading days
_DEFAULT_TOP_N = 80    # broader net than inside-day; Cheats are rarer


def _detect_cheat_variant(symbol: str, which: str) -> Optional[dict]:
    """Detect whether `symbol` currently sits in the requested Cheat zone.

    `which` ∈ {"low", "mid", "high"}. Returns trigger/stop/target/meta dict
    or None if the stock isn't in that zone (or has no base at all).
    """
    try:
        from sepa import prices, vcp
        df = prices.load_prices(symbol, period="2y")
    except Exception as exc:
        log.debug("cheat: price load failed for %s: %s", symbol, exc)
        return None
    if df is None or len(df) < 30:
        return None

    base = vcp.detect(df)
    if not base or not base.get("has_base"):
        return None

    pivot = base.get("pivot_buy_price")
    handle_low = base.get("suggested_stop")
    if pivot is None or handle_low is None:
        return None
    if pivot <= handle_low:
        return None

    handle_range = pivot - handle_low
    if handle_range <= 0:
        return None

    low_upper  = handle_low + handle_range * 0.33
    mid_upper  = handle_low + handle_range * 0.67

    current_close = float(df["close"].iloc[-1])

    # If current close has already cleared the pivot, no Cheat — the
    # textbook breakout entry is in play instead.
    if current_close >= pivot:
        return None
    # If current close is below the handle low, the base is broken.
    if current_close < handle_low:
        return None

    # Classify which zone we're in.
    if current_close <= low_upper:
        zone = "low"
    elif current_close <= mid_upper:
        zone = "mid"
    else:
        zone = "high"

    if zone != which:
        return None

    # Build trigger / stop / target per variant.
    if which == "low":
        # Low Cheat: pay a 0.5% premium over current close to enter on a
        # nibble of strength. Tight stop just under the handle low.
        trigger = round(current_close * 1.005, 4)
        stop    = round(handle_low - 0.01, 4)
        target  = round(pivot, 4)
    elif which == "mid":
        # Mid Cheat: trigger sits at the midpoint of the handle. We're
        # paying up for confirmation that the handle is digesting properly.
        trigger = round(handle_low + handle_range * 0.5, 4)
        stop    = round(handle_low - 0.01, 4)
        target  = round(pivot * 1.03, 4)
    else:  # high
        # High Cheat: trigger sits just under the pivot — we're trying to
        # front-run the official breakout by 1%. Wider target since most
        # of the move is already in the bag once price hits the pivot.
        trigger = round(pivot * 0.99, 4)
        stop    = round(handle_low - 0.01, 4)
        target  = round(pivot * 1.05, 4)

    risk = trigger - stop
    if risk <= 0:
        return None

    return {
        "trigger": trigger,
        "stop": stop,
        "target": target,
        "meta": {
            "cheat_zone": which,
            "pivot_buy_price": round(float(pivot), 4),
            "handle_low":      round(float(handle_low), 4),
            "handle_range_pct": round(handle_range / current_close * 100, 2),
            "current_close":   round(float(current_close), 4),
            "n_contractions":  base.get("n_contractions"),
            "final_contraction_pct": base.get("final_contraction_pct"),
            "base_depth_pct":  base.get("base_depth_pct"),
            "tight_right_side": base.get("tight_right_side"),
            "volume_drying":   base.get("volume_drying"),
        },
    }


def _scan_variant(which: str, top_n: int) -> list[dict]:
    """Shared driver — run a Cheat scan for one variant and persist results."""
    if universe.is_bull_regime() is False:
        log.info("cheat[%s]: bear regime — skipping scan", which)
        return []

    cands = universe.get_sepa_candidates(top_n=top_n)
    if not cands:
        log.info("cheat[%s]: no SEPA candidates available", which)
        return []

    kind = f"{which}_cheat"
    setups: list[dict] = []

    def _process(c):
        sym = c.get("symbol")
        if not sym:
            return None
        result = _detect_cheat_variant(sym, which)
        if result is None:
            return None
        meta = dict(result["meta"])
        meta["sepa_score"]  = c.get("score")
        meta["sepa_rating"] = c.get("rating")
        meta["rs_rank"]     = c.get("rs_rank")
        return store.make_setup(
            kind=kind,
            symbol=sym,
            trigger=result["trigger"],
            stop=result["stop"],
            target=result["target"],
            expires_in_hours=_EXPIRES_HOURS,
            meta=meta,
        )

    with ThreadPoolExecutor(max_workers=8) as ex:
        for setup in ex.map(_process, cands):
            if setup is not None:
                setups.append(setup)

    inserted = store.upsert_setups(kind, setups)
    log.info("cheat[%s]: scanned %d candidates, %d setups inserted",
             which, len(cands), inserted)
    return setups


def scan_low(top_n: int = _DEFAULT_TOP_N) -> list[dict]:
    """Detect Low Cheat candidates — stocks in the lower third of their VCP handle."""
    return _scan_variant("low", top_n)


def scan_mid(top_n: int = _DEFAULT_TOP_N) -> list[dict]:
    """Detect Mid Cheat candidates — stocks in the middle third of their VCP handle."""
    return _scan_variant("mid", top_n)


def scan_high(top_n: int = _DEFAULT_TOP_N) -> list[dict]:
    """Detect High Cheat candidates — stocks in the upper third of their VCP handle."""
    return _scan_variant("high", top_n)


def scan_all(top_n: int = _DEFAULT_TOP_N) -> dict:
    """Run all three variants and fire one consolidated push notification.

    Returns a dict of {variant: [setups]}.
    """
    low_setups  = scan_low(top_n=top_n)
    mid_setups  = scan_mid(top_n=top_n)
    high_setups = scan_high(top_n=top_n)

    total = len(low_setups) + len(mid_setups) + len(high_setups)
    if total > 0:
        try:
            from sepa.notify import send_alert
            # Top 3 across all variants by R:R for the body line.
            combined = low_setups + mid_setups + high_setups
            top = sorted(combined, key=lambda s: s["rr"], reverse=True)[:3]
            body = " · ".join(
                f"{s['symbol']} ({s['meta'].get('cheat_zone')}) "
                f"buy ≥ {s['trigger']:.2f}"
                for s in top
            )
            send_alert(
                title=(
                    f"🎯 {total} Cheat setups "
                    f"({len(low_setups)} low, {len(mid_setups)} mid, "
                    f"{len(high_setups)} high)"
                ),
                body=body,
                kind="setup_cheat",
                url="/setups?kind=low_cheat",
            )
        except Exception as exc:
            log.warning("cheat: push notify failed: %s", exc)

    return {"low": low_setups, "mid": mid_setups, "high": high_setups}


if __name__ == "__main__":
    # Smoke test: `python -m setups.cheat`
    import json
    out = scan_all()
    summary = {
        variant: [
            {"symbol": s["symbol"], "trigger": s["trigger"],
             "stop": s["stop"], "target": s["target"], "rr": s["rr"]}
            for s in setups
        ]
        for variant, setups in out.items()
    }
    print(json.dumps(summary, indent=2))
