"""Base Break — classic 30-day high breakout on volume.

Kell's name for the cup-with-handle / VCP-completion entry — the
"textbook" breakout from a base. Stage 2 quality is already enforced
upstream by the SEPA universe filter; here we look for the moment
price clears resistance on confirming volume.

Detection rules (mechanical):
  1. pivot = df[-30:-1].high.max()       — resistance is the highest
                                            high of the last 30 sessions
                                            EXCLUDING today (today's high
                                            doesn't count as its own
                                            resistance).
  2. df[-1].close > pivot                — breakout closed today.
  3. df[-1].volume > 1.5 × avg_volume_50 — institutional confirmation.

Trigger / Stop / Target:
  - trigger = pivot + 1 cent             — entry on re-test / confirmation
                                            pullback above the pivot.
  - stop    = min(lows[-15:]) - 1 cent   — under the recent base low.
  - target  = trigger × 1.10             — Kell's typical 10% measured move.

Expires after 48h (short window because price has ALREADY broken out —
if it doesn't follow through within 2 days, the breakout is failing).
Top 200 SEPA candidates scanned.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from setups import store, universe

log = logging.getLogger("kell.base_break")


_PIVOT_LOOKBACK   = 30   # sessions for resistance (excluding today)
_STOP_LOOKBACK    = 15   # sessions for stop floor
_MIN_VOL_MULT     = 1.5
_AVG_VOL_WINDOW   = 50


def _detect(symbol: str) -> Optional[dict]:
    try:
        from sepa import prices
        df = prices.load_prices(symbol, period="6mo")
    except Exception as exc:
        log.debug("base_break: price load failed for %s: %s", symbol, exc)
        return None
    if df is None or len(df) < _AVG_VOL_WINDOW + _PIVOT_LOOKBACK + 2:
        return None

    closes = df["close"].values
    highs  = df["high"].values
    lows   = df["low"].values
    vols   = df["volume"].values

    # 1) Pivot = highest high in last 30 sessions excluding today.
    pivot = float(highs[-(_PIVOT_LOOKBACK + 1):-1].max())
    if pivot <= 0:
        return None

    # 2) Today's close above the pivot.
    last_close = float(closes[-1])
    if last_close <= pivot:
        return None

    # 3) Volume confirmation.
    avg_vol = float(vols[-_AVG_VOL_WINDOW - 1 : -1].mean())
    if avg_vol <= 0:
        return None
    vol_mult = float(vols[-1]) / avg_vol
    if vol_mult < _MIN_VOL_MULT:
        return None

    base_low = float(lows[-_STOP_LOOKBACK:].min())

    trigger = round(pivot + 0.01, 4)
    stop    = round(base_low - 0.01, 4)
    target  = round(trigger * 1.10, 4)
    risk = trigger - stop
    if risk <= 0:
        return None

    return {
        "trigger": trigger,
        "stop": stop,
        "target": target,
        "meta": {
            "pivot":          round(pivot, 4),
            "close":          round(last_close, 4),
            "vol_mult":       round(vol_mult, 2),
            "base_low":       round(base_low, 4),
            "breakout_pct":   round((last_close - pivot) / pivot * 100, 2),
            "base_depth_pct": round((pivot - base_low) / pivot * 100, 2),
        },
    }


def scan(top_n: int = 200) -> list[dict]:
    if universe.is_bull_regime() is False:
        log.info("base_break: bear regime — skipping scan")
        return []

    cands = universe.get_sepa_candidates(top_n=top_n)
    if not cands:
        log.info("base_break: no SEPA candidates available")
        return []

    setups: list[dict] = []

    def _process(c):
        sym = c.get("symbol")
        if not sym:
            return None
        result = _detect(sym)
        if result is None:
            return None
        meta = dict(result["meta"])
        meta["sepa_score"]  = c.get("score")
        meta["sepa_rating"] = c.get("rating")
        meta["rs_rank"]     = c.get("rs_rank")
        return store.make_setup(
            kind="base_break",
            symbol=sym,
            trigger=result["trigger"],
            stop=result["stop"],
            target=result["target"],
            expires_in_hours=48,
            meta=meta,
        )

    with ThreadPoolExecutor(max_workers=8) as ex:
        for setup in ex.map(_process, cands):
            if setup is not None:
                setups.append(setup)

    inserted = store.upsert_setups("base_break", setups)
    log.info("base_break: scanned %d candidates, %d setups inserted",
             len(cands), inserted)

    if setups:
        try:
            from sepa.notify import send_alert
            top = sorted(setups, key=lambda s: s["rr"], reverse=True)[:3]
            body = " · ".join(
                f"{s['symbol']} buy ≥ {s['trigger']:.2f} "
                f"(+{s['meta'].get('breakout_pct')}% on {s['meta'].get('vol_mult')}x)"
                for s in top
            )
            send_alert(
                title=f"💥 {len(setups)} Kell Base Break setups",
                body=body,
                kind="setup_base_break",
                url="/kell?kind=base_break",
            )
        except Exception as exc:
            log.warning("base_break: push notify failed: %s", exc)

    return setups


if __name__ == "__main__":
    import json
    out = scan()
    print(json.dumps(
        [{"symbol": s["symbol"], "trigger": s["trigger"], "stop": s["stop"],
          "rr": s["rr"],
          "breakout_pct": s["meta"].get("breakout_pct"),
          "vol_mult": s["meta"].get("vol_mult"),
          "base_depth_pct": s["meta"].get("base_depth_pct")} for s in out],
        indent=2,
    ))
