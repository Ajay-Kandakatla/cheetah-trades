"""Reversal Extension — Oliver Kell's "buy the bottom turn."

The pattern (from "Victory in Stock Trading", 2021):
  - A stock made a recent swing low within the last 20 sessions.
  - It now extends above the prior 5-day high on a strong bullish close
    with confirming volume.
  - Translation: the turn is real — buyers have absorbed the supply and
    pushed price decisively out of the post-low range.

Detection rules (mechanical):
  1. Find idx_low = argmin of df[-20:].low. The low must be at least
     3 sessions ago (not today — we want CONFIRMATION of the turn,
     not the bottom candle itself).
  2. df[-1].close > max(highs[-6:-1])   — extension above the prior
     5-day high.
  3. df[-1].close > df[-1].open         — bullish today.
  4. df[-1].volume > 1.5 × avg_volume_50 — institutional confirmation.

Trigger / Stop / Target:
  - trigger = df[-1].close × 1.005   (small buffer above the breakout)
  - stop    = df[idx_low].low - 1 cent  (below the swing low)
  - target  = trigger × 1.15  (Kell's typical 15% turn target)

Expires after 96h. Top 200 SEPA candidates scanned.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from setups import store, universe

log = logging.getLogger("kell.reversal_extension")


_LOW_LOOKBACK     = 20    # idx_low must lie within last 20 sessions
_LOW_MIN_AGE      = 3     # at least 3 sessions ago (not the current bar)
_PRIOR_HIGH_WIN   = 5     # 5-day prior high to clear
_MIN_VOL_MULT     = 1.5   # df[-1].volume vs 50d avg
_AVG_VOL_WINDOW   = 50


def _detect(symbol: str) -> Optional[dict]:
    try:
        from sepa import prices
        df = prices.load_prices(symbol, period="6mo")
    except Exception as exc:
        log.debug("reversal_extension: price load failed for %s: %s", symbol, exc)
        return None
    if df is None or len(df) < _AVG_VOL_WINDOW + _LOW_LOOKBACK + 2:
        return None

    closes = df["close"].values
    opens  = df["open"].values
    highs  = df["high"].values
    lows   = df["low"].values
    vols   = df["volume"].values
    n = len(df)

    # 1) Recent swing low — argmin in last 20 sessions, age >= 3.
    last_20_lows = lows[-_LOW_LOOKBACK:]
    rel_min_idx = int(last_20_lows.argmin())          # 0..19
    age = (_LOW_LOOKBACK - 1) - rel_min_idx           # sessions ago, 0 = today
    if age < _LOW_MIN_AGE:
        return None
    idx_low = n - _LOW_LOOKBACK + rel_min_idx          # absolute index
    swing_low = float(lows[idx_low])

    # 2) Extension above prior 5-day high (excluding today).
    prior_5_high = float(highs[-(_PRIOR_HIGH_WIN + 1):-1].max())
    last_close = float(closes[-1])
    if last_close <= prior_5_high:
        return None

    # 3) Bullish close today.
    if last_close <= float(opens[-1]):
        return None

    # 4) Volume confirmation.
    avg_vol = float(vols[-_AVG_VOL_WINDOW - 1 : -1].mean())
    if avg_vol <= 0:
        return None
    vol_mult = float(vols[-1]) / avg_vol
    if vol_mult < _MIN_VOL_MULT:
        return None

    trigger = round(last_close * 1.005, 4)
    stop    = round(swing_low - 0.01, 4)
    target  = round(trigger * 1.15, 4)
    risk = trigger - stop
    if risk <= 0:
        return None

    return {
        "trigger": trigger,
        "stop": stop,
        "target": target,
        "meta": {
            "swing_low":     round(swing_low, 4),
            "swing_low_age": age,
            "prior_5_high":  round(prior_5_high, 4),
            "close":         round(last_close, 4),
            "vol_mult":      round(vol_mult, 2),
            "extension_pct": round((last_close - prior_5_high) / prior_5_high * 100, 2),
            "off_low_pct":   round((last_close - swing_low) / swing_low * 100, 2),
        },
    }


def scan(top_n: int = 200) -> list[dict]:
    if universe.is_bull_regime() is False:
        log.info("reversal_extension: bear regime — skipping scan")
        return []

    cands = universe.get_sepa_candidates(top_n=top_n)
    if not cands:
        log.info("reversal_extension: no SEPA candidates available")
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
            kind="reversal_extension",
            symbol=sym,
            trigger=result["trigger"],
            stop=result["stop"],
            target=result["target"],
            expires_in_hours=96,
            meta=meta,
        )

    with ThreadPoolExecutor(max_workers=8) as ex:
        for setup in ex.map(_process, cands):
            if setup is not None:
                setups.append(setup)

    inserted = store.upsert_setups("reversal_extension", setups)
    log.info("reversal_extension: scanned %d candidates, %d setups inserted",
             len(cands), inserted)

    if setups:
        try:
            from sepa.notify import send_alert
            top = sorted(setups, key=lambda s: s["rr"], reverse=True)[:3]
            body = " · ".join(
                f"{s['symbol']} buy ≥ {s['trigger']:.2f} "
                f"(off low {s['meta'].get('off_low_pct')}% on {s['meta'].get('vol_mult')}x)"
                for s in top
            )
            send_alert(
                title=f"↗️ {len(setups)} Kell Reversal Extension setups",
                body=body,
                kind="setup_reversal_extension",
                url="/kell?kind=reversal_extension",
            )
        except Exception as exc:
            log.warning("reversal_extension: push notify failed: %s", exc)

    return setups


if __name__ == "__main__":
    import json
    out = scan()
    print(json.dumps(
        [{"symbol": s["symbol"], "trigger": s["trigger"], "stop": s["stop"],
          "rr": s["rr"],
          "off_low_pct": s["meta"].get("off_low_pct"),
          "vol_mult": s["meta"].get("vol_mult"),
          "swing_low_age": s["meta"].get("swing_low_age")} for s in out],
        indent=2,
    ))
