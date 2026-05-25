"""Post-Earnings Drift tracker — ride the trend, don't catch a breakout.

This is structurally different from the other setups in this module.
Where PEG / Episodic Pivot trade the BREAKOUT above the gap-day high,
Post-Earnings Drift trades the slow grind that follows after the gap
has already been digested. Empirically, names that gap ≥ 6% on ≥ 4×
volume tend to drift another 10-20% over the following 1-30 sessions
("post-earnings announcement drift" — PEAD — well-documented in the
academic literature).

Detection criteria:
  1. Find the most recent qualifying power gap in the last 30 sessions
     (gap ≥ 6%, vol ≥ 4× — slightly looser than PEG because we're not
     trading the breakout itself).
  2. Current close > gap-day high (drift is intact, not failed).
  3. Current close within 15% of gap-day high (not yet over-extended;
     beyond +15% the easy money has been made).
  4. A 1-5 day micro-pullback to the gap-day's 5-day moving average
     from where we are now (we're entering on a small reset, not a peak).

Trigger: today's close × 1.005   (continuation buy — wait for the move
                                  to continue, don't predict it)
Stop:    gap_day_low - 1 cent    (the original gap remains the line in
                                  the sand; if that breaks, the whole
                                  premise of the post-earnings drift fails)
Target:  gap_day_high × 1.15     (~15% extension — typical drift run)

Expires after 240h (10 trading days — drifts take time to play out).
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from . import store, universe

log = logging.getLogger("setups.post_earnings_drift")


_MIN_GAP_PCT       = 6.0
_MIN_VOL_MULT      = 4.0
_LOOKBACK_DAYS     = 30
_AVG_VOL_WINDOW    = 50
_MAX_EXTENSION_PCT = 15.0   # close must be within 15% above gap_day_high
_MA_WINDOW         = 5      # 5-day MA used as the micro-pullback target
_PULLBACK_LOOKBACK = 5      # last N sessions to scan for a recent MA touch
_PULLBACK_TOL_PCT  = 2.0    # within 2% of the 5-day MA counts as a touch


def _detect_drift(symbol: str) -> Optional[dict]:
    """Detect a stock currently riding a post-earnings drift. Returns payload or None."""
    try:
        from sepa import prices
        df = prices.load_prices(symbol, period="1y")
    except Exception as exc:
        log.debug("post_earnings_drift: price load failed for %s: %s", symbol, exc)
        return None
    if df is None or len(df) < _AVG_VOL_WINDOW + _LOOKBACK_DAYS + 5:
        return None

    df = df.tail(_LOOKBACK_DAYS + _AVG_VOL_WINDOW + 10).copy().reset_index(drop=True)
    closes = df["close"].values
    opens  = df["open"].values
    highs  = df["high"].values
    lows   = df["low"].values
    vols   = df["volume"].values
    n = len(df)
    if n < _AVG_VOL_WINDOW + 2:
        return None

    # Find the most recent power gap in the last LOOKBACK_DAYS sessions.
    found = None
    for i in range(n - 1, n - 1 - _LOOKBACK_DAYS, -1):
        if i < _AVG_VOL_WINDOW + 1:
            break
        avg_vol = vols[i - _AVG_VOL_WINDOW : i].mean()
        if avg_vol <= 0:
            continue
        prior_close = closes[i - 1]
        if prior_close <= 0:
            continue
        gap_pct = (opens[i] - prior_close) / prior_close * 100
        vol_mult = vols[i] / avg_vol
        if gap_pct >= _MIN_GAP_PCT and vol_mult >= _MIN_VOL_MULT:
            found = {
                "gap_day_idx":   i,
                "gap_day_high":  float(highs[i]),
                "gap_day_low":   float(lows[i]),
                "gap_day_close": float(closes[i]),
                "gap_pct":       round(float(gap_pct), 2),
                "vol_mult":      round(float(vol_mult), 2),
                "days_ago":      n - 1 - i,
            }
            break

    if not found:
        return None

    current_close = float(closes[-1])

    # Drift must be intact — current close above gap-day high.
    if current_close <= found["gap_day_high"]:
        return None

    # Not yet over-extended.
    extension_pct = (current_close - found["gap_day_high"]) / found["gap_day_high"] * 100
    if extension_pct > _MAX_EXTENSION_PCT:
        return None

    # Look for a recent micro-pullback to the 5-day MA within the last
    # PULLBACK_LOOKBACK sessions. We compute the 5-day MA on the last
    # PULLBACK_LOOKBACK + MA_WINDOW closes.
    if n < _MA_WINDOW + _PULLBACK_LOOKBACK:
        return None
    ma_touched = False
    ma_touch_idx = None
    for j in range(n - _PULLBACK_LOOKBACK, n):
        if j < _MA_WINDOW:
            continue
        ma5 = float(closes[j - _MA_WINDOW + 1 : j + 1].mean())
        if ma5 <= 0:
            continue
        # "Touch" = low of the day came within tolerance of (or under) the MA.
        if lows[j] <= ma5 * (1 + _PULLBACK_TOL_PCT / 100):
            ma_touched = True
            ma_touch_idx = j
            break

    if not ma_touched:
        return None

    trigger = round(current_close * 1.005, 4)
    stop    = round(found["gap_day_low"] - 0.01, 4)
    target  = round(found["gap_day_high"] * 1.15, 4)

    risk = trigger - stop
    if risk <= 0:
        return None

    return {
        "trigger": trigger,
        "stop": stop,
        "target": target,
        "meta": {
            "gap_pct":         found["gap_pct"],
            "vol_mult":        found["vol_mult"],
            "days_since_gap":  found["days_ago"],
            "gap_day_high":    round(found["gap_day_high"], 4),
            "gap_day_low":     round(found["gap_day_low"],  4),
            "gap_day_close":   round(found["gap_day_close"], 4),
            "current_close":   round(current_close, 4),
            "extension_pct":   round(extension_pct, 2),
            "ma5_touch_days_ago": int(n - 1 - ma_touch_idx)
            if ma_touch_idx is not None else None,
        },
    }


def scan(top_n: int = 100) -> list[dict]:
    """Find post-earnings drift names worth joining."""
    if universe.is_bull_regime() is False:
        log.info("post_earnings_drift: bear regime — skipping scan")
        return []

    cands = universe.get_sepa_candidates(top_n=top_n)
    if not cands:
        log.info("post_earnings_drift: no SEPA candidates available")
        return []

    setups: list[dict] = []

    def _process(c):
        sym = c.get("symbol")
        if not sym:
            return None
        result = _detect_drift(sym)
        if result is None:
            return None
        meta = dict(result["meta"])
        meta["sepa_score"]  = c.get("score")
        meta["sepa_rating"] = c.get("rating")
        meta["rs_rank"]     = c.get("rs_rank")
        return store.make_setup(
            kind="post_earnings_drift",
            symbol=sym,
            trigger=result["trigger"],
            stop=result["stop"],
            target=result["target"],
            expires_in_hours=240,
            meta=meta,
        )

    with ThreadPoolExecutor(max_workers=8) as ex:
        for setup in ex.map(_process, cands):
            if setup is not None:
                setups.append(setup)

    inserted = store.upsert_setups("post_earnings_drift", setups)
    log.info("post_earnings_drift: scanned %d candidates, %d setups inserted",
             len(cands), inserted)

    if setups:
        try:
            from sepa.notify import send_alert
            top = sorted(setups, key=lambda s: s["rr"], reverse=True)[:3]
            body = " · ".join(
                f"{s['symbol']} buy ≥ {s['trigger']:.2f} "
                f"(gap {s['meta'].get('gap_pct')}% "
                f"{s['meta'].get('days_since_gap')}d ago)"
                for s in top
            )
            send_alert(
                title=f"📈 {len(setups)} Post-Earnings Drift names still riding",
                body=body,
                kind="setup_post_earnings_drift",
                url="/setups?kind=post_earnings_drift",
            )
        except Exception as exc:
            log.warning("post_earnings_drift: push notify failed: %s", exc)

    return setups


if __name__ == "__main__":
    import json
    out = scan()
    print(json.dumps(
        [{"symbol": s["symbol"], "trigger": s["trigger"], "stop": s["stop"],
          "rr": s["rr"], "gap_pct": s["meta"].get("gap_pct"),
          "days_since_gap": s["meta"].get("days_since_gap"),
          "extension_pct": s["meta"].get("extension_pct")} for s in out],
        indent=2,
    ))
