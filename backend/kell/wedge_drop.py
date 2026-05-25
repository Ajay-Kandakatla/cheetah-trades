"""Wedge Drop — Oliver Kell's "shakeout that resolves to upside."

The pattern (from "Victory in Stock Trading", 2021):
  - A Stage-2 leader pulls back 3-7 days in a downsloping WEDGE
    (descending highs AND descending lows) that touches the 21-day EMA
    or 50-day SMA.
  - The shakeout flushes weak hands; institutions step in at the moving
    average and reverse the wedge with a bullish candle on confirming
    volume.
  - The reversal candle is the entry trigger — buy the high + 1 cent.

Detection rules (mechanical):
  1. df[-7:-1] forms a descending wedge — highs falling AND lows falling.
  2. df[-1].low touches MA21 or MA50 within 2% (the key support test).
  3. df[-1] is bullish: close > open AND close > df[-2].close.
  4. df[-1].volume > 0.7 × avg_volume_50 (volume confirms the reversal).

Trigger / Stop / Target:
  - trigger = df[-1].high + 1 cent
  - stop    = df[-1].low  - 1 cent
  - target  = trigger × 1.08  (Kell's typical 8% first scale)

Expires after 72h (3 trading days). Top 200 SEPA candidates scanned.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

# Reuse the existing setups infrastructure — store + universe helper.
# Kell scanners share the `setups` Mongo collection (one row per setup,
# `kind` field discriminates), so the frontend can read /setups/{kind}
# uniformly across Minervini + Kell patterns.
from setups import store, universe

log = logging.getLogger("kell.wedge_drop")


_WEDGE_MIN_LEN          = 3      # min wedge length, sessions
_WEDGE_MAX_LEN          = 7      # max wedge length
_MA_TOUCH_TOLERANCE_PCT = 2.0    # df[-1].low within X% of MA21/MA50
_MIN_VOL_RATIO          = 0.7    # df[-1].volume >= 0.7 × avg_vol_50
_AVG_VOL_WINDOW         = 50


def _detect(symbol: str) -> Optional[dict]:
    """Detect a wedge drop reversal. Returns payload or None."""
    try:
        from sepa import prices
        df = prices.load_prices(symbol, period="6mo")
    except Exception as exc:
        log.debug("wedge_drop: price load failed for %s: %s", symbol, exc)
        return None
    if df is None or len(df) < _AVG_VOL_WINDOW + _WEDGE_MAX_LEN + 2:
        return None

    closes = df["close"].values
    opens  = df["open"].values
    highs  = df["high"].values
    lows   = df["low"].values
    vols   = df["volume"].values
    n = len(df)

    # 1) Bullish reversal candle on df[-1].
    last_close = float(closes[-1])
    last_open  = float(opens[-1])
    last_high  = float(highs[-1])
    last_low   = float(lows[-1])
    prev_close = float(closes[-2])
    if last_close <= last_open:
        return None
    if last_close <= prev_close:
        return None

    # 2) Volume confirmation — at least 70% of the 50d avg.
    avg_vol = float(vols[-_AVG_VOL_WINDOW - 1 : -1].mean())
    if avg_vol <= 0:
        return None
    vol_ratio = float(vols[-1]) / avg_vol
    if vol_ratio < _MIN_VOL_RATIO:
        return None

    # 3) Moving-average proximity test — df[-1].low must touch MA21 or MA50
    # within tolerance. We compute both averages off the WHOLE series ending
    # at df[-1] (inclusive — Kell measures the close-of-day MA values).
    ma21 = float(closes[-21:].mean())
    ma50 = float(closes[-50:].mean())
    tol = _MA_TOUCH_TOLERANCE_PCT / 100.0
    touch_ma21 = abs(last_low - ma21) / ma21 <= tol if ma21 > 0 else False
    touch_ma50 = abs(last_low - ma50) / ma50 <= tol if ma50 > 0 else False
    if not (touch_ma21 or touch_ma50):
        return None

    # 4) Wedge structure on the 3-7 sessions BEFORE the reversal candle.
    # We try the longest wedge that satisfies "descending highs AND lows"
    # because the 7-day flush is more meaningful than the 3-day one.
    wedge_len = None
    for L in range(_WEDGE_MAX_LEN, _WEDGE_MIN_LEN - 1, -1):
        # Window: df[-(L+1):-1] — L sessions, ending the bar BEFORE today.
        seg_highs = highs[-(L + 1):-1]
        seg_lows  = lows[-(L + 1):-1]
        if len(seg_highs) < L:
            continue
        # Strictly descending highs AND lows. Allow equal as no-op (rare).
        highs_desc = all(seg_highs[i] >= seg_highs[i + 1] for i in range(L - 1))
        lows_desc  = all(seg_lows[i]  >= seg_lows[i + 1]  for i in range(L - 1))
        # Require at least one strict drop in each so we're not flat-lining.
        any_high_drop = any(seg_highs[i] > seg_highs[i + 1] for i in range(L - 1))
        any_low_drop  = any(seg_lows[i]  > seg_lows[i + 1]  for i in range(L - 1))
        if highs_desc and lows_desc and any_high_drop and any_low_drop:
            wedge_len = L
            break
    if wedge_len is None:
        return None

    trigger = round(last_high + 0.01, 4)
    stop    = round(last_low  - 0.01, 4)
    target  = round(trigger * 1.08, 4)
    risk = trigger - stop
    if risk <= 0:
        return None

    return {
        "trigger": trigger,
        "stop": stop,
        "target": target,
        "meta": {
            "wedge_len":      wedge_len,
            "ma21":           round(ma21, 4),
            "ma50":           round(ma50, 4),
            "ma_touched":     "ma21" if touch_ma21 else "ma50",
            "vol_ratio":      round(vol_ratio, 2),
            "reversal_close": round(last_close, 4),
            "reversal_open":  round(last_open, 4),
            "reversal_high":  round(last_high, 4),
            "reversal_low":   round(last_low, 4),
            "prev_close":     round(prev_close, 4),
        },
    }


def scan(top_n: int = 200) -> list[dict]:
    """Scan the top SEPA candidates for Kell wedge drops."""
    if universe.is_bull_regime() is False:
        log.info("wedge_drop: bear regime — skipping scan")
        return []

    cands = universe.get_sepa_candidates(top_n=top_n)
    if not cands:
        log.info("wedge_drop: no SEPA candidates available")
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
            kind="wedge_drop",
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

    inserted = store.upsert_setups("wedge_drop", setups)
    log.info("wedge_drop: scanned %d candidates, %d setups inserted",
             len(cands), inserted)

    if setups:
        try:
            from sepa.notify import send_alert
            top = sorted(setups, key=lambda s: s["rr"], reverse=True)[:3]
            body = " · ".join(
                f"{s['symbol']} buy ≥ {s['trigger']:.2f} "
                f"(wedge {s['meta'].get('wedge_len')}d "
                f"@ {s['meta'].get('ma_touched')})"
                for s in top
            )
            send_alert(
                title=f"🪃 {len(setups)} Kell Wedge Drop setups",
                body=body,
                kind="setup_wedge_drop",
                url="/kell?kind=wedge_drop",
            )
        except Exception as exc:
            log.warning("wedge_drop: push notify failed: %s", exc)

    return setups


if __name__ == "__main__":
    # Smoke test: `python -m kell.wedge_drop`
    import json
    out = scan()
    print(json.dumps(
        [{"symbol": s["symbol"], "trigger": s["trigger"], "stop": s["stop"],
          "rr": s["rr"],
          "wedge_len": s["meta"].get("wedge_len"),
          "ma_touched": s["meta"].get("ma_touched"),
          "vol_ratio": s["meta"].get("vol_ratio")} for s in out],
        indent=2,
    ))
