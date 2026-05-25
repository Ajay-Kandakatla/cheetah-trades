"""Inside-Day breakout scanner.

Setup definition (mechanical, no judgment):
  - Look at the most recent two daily bars: today (T) and yesterday (T-1).
  - "Inside day" = T.high < T-1.high AND T.low > T-1.low.
    The whole T bar is engulfed by T-1's range — a compression bar.
  - Trigger: buy a break of T.high  + 1 cent buffer
  - Stop:    T.low                   - 1 cent buffer
  - Target:  T.high + 1.5 × (T.high - T.low)   (1.5× the inside range)
  - Reward:risk must be ≥ 1.2 — otherwise reject (not enough room).
  - Hold 1-3 days; expires after 48h regardless.

Why this works in bull markets:
  Compression bars before a continuation move are well-documented (search:
  "NR7 setup", "Toby Crabel's narrow-range patterns"). On a quality SEPA
  name in a bull regime, a break of the inside-day high typically
  produces a 1-3% move within 1-3 days. The math is forced — the stop
  is tight by construction (inside the inside day) and the target is
  computed off the same range, so the R:R is mechanically derived.

This scanner runs nightly. The user places a buy-stop + sell-stop pair
at Fidelity before bed and walks away.
"""
from __future__ import annotations

import logging
from typing import Optional

from . import store, universe

log = logging.getLogger("setups.inside_day")


def _detect_inside_day(symbol: str) -> Optional[dict]:
    """Return a setup dict if `symbol` is an inside-day candidate, else None.

    Returns the trigger/stop/target/meta payload that the caller wraps
    into a full setup row.
    """
    try:
        from sepa import prices
        df = prices.load_prices(symbol, period="1y")
    except Exception as exc:
        log.debug("inside_day: price load failed for %s: %s", symbol, exc)
        return None
    if df is None or len(df) < 3:
        return None

    today = df.iloc[-1]
    yday = df.iloc[-2]

    # Inside-day test
    if not (today["high"] < yday["high"] and today["low"] > yday["low"]):
        return None

    # Quality gates: don't trigger on a doji or a tiny range. The setup
    # needs room to move — if today's range is < 1% of close we'd be
    # trading on noise.
    today_range = today["high"] - today["low"]
    if today["close"] <= 0:
        return None
    if today_range / today["close"] < 0.005:  # <0.5% range
        return None

    # Sanity: today's close should be in the upper half of today's range
    # for a bullish bias. Inside-day shorts exist too, but we only build
    # bull setups (per user's direction).
    if today["close"] < (today["high"] + today["low"]) / 2:
        return None

    trigger = round(today["high"] + 0.01, 4)
    stop    = round(today["low"]  - 0.01, 4)
    target  = round(today["high"] + 1.5 * today_range, 4)

    risk    = trigger - stop
    reward  = target - trigger
    if risk <= 0:
        return None
    rr = reward / risk
    if rr < 1.2:
        # Too thin a payoff for a 48h hold — pass.
        return None

    return {
        "trigger": trigger,
        "stop": stop,
        "target": target,
        "meta": {
            "today_high":  round(float(today["high"]), 4),
            "today_low":   round(float(today["low"]),  4),
            "today_close": round(float(today["close"]), 4),
            "today_range_pct": round(today_range / today["close"] * 100, 2),
            "rr": round(rr, 2),
            "yesterday_high": round(float(yday["high"]), 4),
            "yesterday_low":  round(float(yday["low"]),  4),
        },
    }


def scan(top_n: int = 30) -> list[dict]:
    """Find inside-day setups across the top SEPA candidates.

    Returns the list of persisted setup dicts (for logging / push).
    """
    if universe.is_bull_regime() is False:
        log.info("inside_day: bear regime — skipping scan")
        return []

    cands = universe.get_sepa_candidates(top_n=top_n)
    if not cands:
        log.info("inside_day: no SEPA candidates available")
        return []

    setups: list[dict] = []
    for c in cands:
        sym = c.get("symbol")
        if not sym:
            continue
        result = _detect_inside_day(sym)
        if result is None:
            continue
        meta = dict(result["meta"])
        meta["sepa_score"]  = c.get("score")
        meta["sepa_rating"] = c.get("rating")
        meta["rs_rank"]     = c.get("rs_rank")
        setup = store.make_setup(
            kind="inside_day",
            symbol=sym,
            trigger=result["trigger"],
            stop=result["stop"],
            target=result["target"],
            expires_in_hours=48,
            meta=meta,
        )
        setups.append(setup)

    inserted = store.upsert_setups("inside_day", setups)
    log.info("inside_day: scanned %d candidates, %d setups inserted", len(cands), inserted)

    # Optional push notification with top 3 by R:R.
    if setups:
        try:
            from sepa.notify import send_alert
            top = sorted(setups, key=lambda s: s["rr"], reverse=True)[:3]
            body = " · ".join(
                f"{s['symbol']} buy ≥ {s['trigger']:.2f} stop {s['stop']:.2f}"
                for s in top
            )
            send_alert(
                title=f"📦 {len(setups)} inside-day setups for tomorrow",
                body=body,
                kind="setup_inside_day",
                url="/setups?kind=inside_day",
            )
        except Exception as exc:
            log.warning("inside_day: push notify failed: %s", exc)

    return setups


if __name__ == "__main__":
    # Smoke test: `python -m setups.inside_day`
    import json
    out = scan(top_n=30)
    print(json.dumps([{"symbol": s["symbol"], "trigger": s["trigger"],
                       "stop": s["stop"], "rr": s["rr"]} for s in out],
                     indent=2))
