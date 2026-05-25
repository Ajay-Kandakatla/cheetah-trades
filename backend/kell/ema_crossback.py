"""EMA Crossback — Oliver Kell, Cycle of Price Action.

Canonical source: "Victory in Stock Trading" (Kell, 2021), pp. 18, 23, 27.

Phase 3 of the CoPA cycle — the FIRST PULLBACK to the moving averages
inside a confirmed new uptrend. Quoting Kell p. 27:

  "[Q] EMA Crossback / Pullback — Price pulls back into the moving
   averages and provides a low risk-spot to add to the position or
   raise stops and continue to hold the position."

This is one of the safest entries in the whole cycle because:
  1. The trend is already up (ema10 > ema20 > sma50),
  2. The pullback tags the EMAs lightly (low-risk, tight stop),
  3. Volume is LIGHTER on the pullback (constructive — no urgency to sell).

Detection (per pp. 18, 23, 27):
  1. Confirmed uptrend stack: ema10 > ema20 > sma50, AND closes above
     the 10 EMA for ≥ 10 of the last 15 sessions.
  2. The ema10 has been RISING for the last 10+ sessions (proxy for
     "established Stage 2 trend after a Wedge Pop").
  3. Pullback to EMAs in last 1-3 sessions: at least one of
     df[-3:].low touched within 1% of either ema10 or ema20.
  4. df[-1] is BULLISH and recovers from the EMA touch by close:
       close > open AND close > ema10.
  5. Pullback on LIGHT volume:
       mean(volume[-3:]) < avg_volume_50 (constructive pullback).

Stops & targets:
  - trigger = df[-1].high + 0.01
  - stop    = min(ema20, df[-3:].low.min()) - 0.01
              (per pp. 49 — "Reconfirming Price Strength Confirmation":
              stops below the new pivot low; 20 EMA is the trailing
              stop floor per pp. 49 "10/20 EMA Trailing Stop")
  - target  = df[-1].close × 1.08 (typical pullback continuation move)

Tier: SAFE-MOD — the cleanest, lowest-risk entry in the cycle.
Expires 72h. Top 200 SEPA candidates.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from setups import store, universe

log = logging.getLogger("kell.ema_crossback")


# ── Locked thresholds — see docs/KELL_CONTRACTS.md §4.3
_TREND_WIN              = 15    # closes above 10 EMA window
_TREND_MIN_CLOSES       = 10    # ≥ 10 of last 15 closes above 10 EMA
_EMA10_RISING_DAYS      = 10    # ema10 rising for last N sessions
_PULLBACK_LOOKBACK      = 3     # last N sessions can include the EMA touch
_EMA_TOUCH_PCT          = 0.01  # low within 1% of ema10 or ema20
_AVG_VOL_WINDOW         = 50
_LIGHT_VOL_WINDOW       = 3     # mean(volume[-3:]) < avg_volume_50


def _ema(series, span: int):
    return series.ewm(span=span, adjust=False).mean()


def _detect(symbol: str) -> Optional[dict]:
    try:
        from sepa import prices
        df = prices.load_prices(symbol, period="6mo")
    except Exception as exc:
        log.debug("ema_crossback: price load failed for %s: %s", symbol, exc)
        return None
    if df is None or len(df) < _AVG_VOL_WINDOW + _TREND_WIN + 5:
        return None

    closes_s = df["close"]
    opens  = df["open"].values
    highs  = df["high"].values
    lows   = df["low"].values
    vols   = df["volume"].values

    ema10 = _ema(closes_s, 10).values
    ema20 = _ema(closes_s, 20).values
    sma50 = closes_s.rolling(50).mean().values
    closes = closes_s.values

    last_close = float(closes[-1])
    last_open  = float(opens[-1])
    last_high  = float(highs[-1])
    last_ema10 = float(ema10[-1])
    last_ema20 = float(ema20[-1])
    last_sma50 = float(sma50[-1]) if sma50[-1] == sma50[-1] else 0.0
    if last_sma50 <= 0:
        return None

    # 1) Uptrend stack ema10 > ema20 > sma50.
    if not (last_ema10 > last_ema20 > last_sma50):
        return None
    # Closes above 10 EMA for ≥ 10 of last 15 sessions.
    win_closes = closes[-_TREND_WIN:]
    win_ema10  = ema10[-_TREND_WIN:]
    above_count = sum(1 for i in range(_TREND_WIN) if win_closes[i] > win_ema10[i])
    if above_count < _TREND_MIN_CLOSES:
        return None

    # 2) 10 EMA rising for last 10 sessions.
    ema10_seg = ema10[-(_EMA10_RISING_DAYS + 1):]
    if not all(ema10_seg[i] <= ema10_seg[i + 1] for i in range(_EMA10_RISING_DAYS)):
        return None
    # Require at least one strict rise (not flat-line).
    if not any(ema10_seg[i] < ema10_seg[i + 1] for i in range(_EMA10_RISING_DAYS)):
        return None

    # 3) Pullback to EMAs in last 1-3 sessions.
    touched = False
    touch_ma = None
    for k in range(_PULLBACK_LOOKBACK):
        idx = -1 - k
        lo = float(lows[idx])
        e10 = float(ema10[idx])
        e20 = float(ema20[idx])
        if e10 > 0 and lo <= e10 * (1 + _EMA_TOUCH_PCT):
            touched = True; touch_ma = "ema10"; break
        if e20 > 0 and lo <= e20 * (1 + _EMA_TOUCH_PCT):
            touched = True; touch_ma = "ema20"; break
    if not touched:
        return None

    # 4) df[-1] bullish AND closes above 10 EMA.
    if last_close <= last_open:
        return None
    if last_close <= last_ema10:
        return None

    # 5) Light volume on pullback.
    avg_vol = float(vols[-_AVG_VOL_WINDOW - 1:-1].mean())
    if avg_vol <= 0:
        return None
    light_vol_mean = float(vols[-_LIGHT_VOL_WINDOW:].mean())
    if light_vol_mean >= avg_vol:
        return None

    # 6) Trigger / stop / target.
    last3_low = float(lows[-_PULLBACK_LOOKBACK:].min())
    stop_floor = min(last_ema20, last3_low) - 0.01
    trigger = round(last_high + 0.01, 4)
    stop    = round(stop_floor, 4)
    target  = round(last_close * 1.08, 4)
    risk = trigger - stop
    if risk <= 0:
        return None

    return {
        "trigger": trigger,
        "stop":    stop,
        "target":  target,
        "meta": {
            "ema10":           round(last_ema10, 4),
            "ema20":           round(last_ema20, 4),
            "sma50":           round(last_sma50, 4),
            "touch_ma":        touch_ma,
            "closes_above_10ema_15d": int(above_count),
            "pullback_vol_ratio":     round(light_vol_mean / avg_vol, 2),
            "close":           round(last_close, 4),
            "pullback_low":    round(last3_low, 4),
        },
    }


def scan(top_n: int = 200) -> list[dict]:
    # Bull-regime gated — EMA Crossback is a BUY setup.
    if universe.is_bull_regime() is False:
        log.info("ema_crossback: bear regime — skipping scan")
        return []

    cands = universe.get_sepa_candidates(top_n=top_n)
    if not cands:
        log.info("ema_crossback: no SEPA candidates available")
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
            kind="ema_crossback",
            symbol=sym,
            trigger=result["trigger"],
            stop=result["stop"],
            target=result["target"],
            expires_in_hours=72,
            meta=meta,
        )

    with ThreadPoolExecutor(max_workers=8) as ex:
        for setup in ex.map(_process, cands):
            if setup is not None:
                setups.append(setup)

    inserted = store.upsert_setups("ema_crossback", setups)
    log.info(
        "ema_crossback: scanned %d candidates, %d setups inserted",
        len(cands), inserted,
    )

    if setups:
        try:
            from sepa.notify import send_alert
            top = sorted(setups, key=lambda s: s["rr"], reverse=True)[:3]
            body = " · ".join(
                f"{s['symbol']} buy ≥ {s['trigger']:.2f} "
                f"({s['meta'].get('touch_ma')} tag, "
                f"{s['meta'].get('pullback_vol_ratio')}x vol)"
                for s in top
            )
            send_alert(
                title=f"🎯 {len(setups)} Kell EMA Crossback setups",
                body=body,
                kind="setup_ema_crossback",
                url="/kell?kind=ema_crossback",
            )
        except Exception as exc:
            log.warning("ema_crossback: push notify failed: %s", exc)

    return setups


if __name__ == "__main__":
    import json
    out = scan()
    print(json.dumps(
        [{"symbol": s["symbol"], "trigger": s["trigger"], "stop": s["stop"],
          "target": s["target"], "rr": s["rr"],
          "touch_ma":          s["meta"].get("touch_ma"),
          "pullback_vol_ratio": s["meta"].get("pullback_vol_ratio")} for s in out],
        indent=2,
    ))
