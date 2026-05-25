"""Power Trend — Kell's stair-step continuation.

A Stage-2 leader is making higher highs with shallow pullbacks while
holding above the 21-day EMA. Each pullback to MA21 is a continuation
entry; the trend "powers" along the moving average like a staircase.

Detection rules (mechanical):
  1. Strict trend over last 50 sessions:
        closes[-50:] all above MA50         — never closes below the
                                              50-day average for 50 days.
  2. df[-1].close > MA21                    — currently above the 21-day.
  3. At least 2 distinct higher-highs in    — the stair-step structure.
       the last 30 days, separated by
       pullbacks of < 10%.
  4. Most recent pullback BOTTOMED at MA21  — the latest setup leg sits
       within the last 5 sessions.            on the moving-average rail.

Trigger / Stop / Target:
  - trigger = df[-1].close × 1.005   (continuation buy slightly above today)
  - stop    = MA21 × 0.98            (below MA21 with 2% buffer — if it
                                      closes meaningfully below MA21 the
                                      power trend is broken)
  - target  = trigger × 1.12         (next stair-step, ~12% leg)

Expires after 96h. Top 200 SEPA candidates scanned.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from setups import store, universe

log = logging.getLogger("kell.power_trend")


_TREND_WIN          = 50    # closes must stay above MA50 for this many bars
_HH_LOOKBACK        = 30    # window we look for higher-highs in
_HH_MIN_COUNT       = 2     # need >= 2 distinct higher-highs
_PULLBACK_MAX_PCT   = 10.0  # pullbacks between higher-highs < 10%
_MA21_TOUCH_LOOKBK  = 5     # last pullback bottomed at MA21 within N sessions
_MA21_TOUCH_PCT     = 2.5   # "touched" tolerance (low within X% of MA21)


def _detect(symbol: str) -> Optional[dict]:
    try:
        from sepa import prices
        df = prices.load_prices(symbol, period="6mo")
    except Exception as exc:
        log.debug("power_trend: price load failed for %s: %s", symbol, exc)
        return None
    if df is None or len(df) < _TREND_WIN + 5:
        return None

    closes = df["close"].values
    highs  = df["high"].values
    lows   = df["low"].values
    n = len(df)

    # 1) Strict trend: every close in the last 50 sessions must be at or
    # above its rolling 50-day average. We compute MA50 ending at each
    # bar and check the constraint at every step.
    for i in range(n - _TREND_WIN, n):
        ma50_at_i = float(closes[i - 49 : i + 1].mean()) if i >= 49 else None
        if ma50_at_i is None or closes[i] < ma50_at_i:
            return None

    # 2) df[-1].close > MA21.
    last_close = float(closes[-1])
    ma21 = float(closes[-21:].mean())
    if last_close <= ma21:
        return None

    # 3) Higher-highs in the last 30 sessions.
    # Find local peaks (high > both neighbors) within the window; require
    # at least 2 distinct peaks each higher than the prior, with pullback
    # between them < 10%.
    win_highs = highs[-_HH_LOOKBACK:]
    win_lows  = lows[-_HH_LOOKBACK:]
    peaks: list[tuple[int, float]] = []  # (idx_in_window, high)
    for j in range(1, len(win_highs) - 1):
        if win_highs[j] > win_highs[j - 1] and win_highs[j] > win_highs[j + 1]:
            peaks.append((j, float(win_highs[j])))
    # Also consider the most recent bar as a candidate "peak" if it's the
    # highest of the window — useful when the stair-step JUST printed a
    # new high and there's no neighbor on the right side yet.
    if len(win_highs) > 0:
        last_idx = len(win_highs) - 1
        if float(win_highs[last_idx]) >= float(max(win_highs)):
            if not peaks or peaks[-1][0] != last_idx:
                peaks.append((last_idx, float(win_highs[last_idx])))

    # Walk peaks left→right keeping only those strictly higher than the
    # last kept peak with a < 10% pullback intervening.
    kept: list[tuple[int, float]] = []
    for p_idx, p_high in peaks:
        if not kept:
            kept.append((p_idx, p_high))
            continue
        prev_idx, prev_high = kept[-1]
        if p_high <= prev_high:
            continue
        # Pullback between prev peak and this peak: min low in the gap.
        gap_lows = win_lows[prev_idx + 1 : p_idx + 1]
        if len(gap_lows) == 0:
            continue
        pullback_pct = (prev_high - float(min(gap_lows))) / prev_high * 100
        if pullback_pct > _PULLBACK_MAX_PCT:
            # Reset — too deep to be a power-trend stair step.
            kept = [(p_idx, p_high)]
            continue
        kept.append((p_idx, p_high))

    if len(kept) < _HH_MIN_COUNT:
        return None

    # 4) Latest pullback bottomed at MA21 within last 5 sessions.
    # Compute MA21 at each of the last 5 sessions and check whether the
    # session low came within tolerance of its MA21 value.
    tol = _MA21_TOUCH_PCT / 100.0
    touched_recent = False
    for k in range(_MA21_TOUCH_LOOKBK):
        idx = n - 1 - k
        if idx < 20:
            break
        ma21_at_idx = float(closes[idx - 20 : idx + 1].mean())
        if ma21_at_idx <= 0:
            continue
        if abs(float(lows[idx]) - ma21_at_idx) / ma21_at_idx <= tol:
            touched_recent = True
            break
    if not touched_recent:
        return None

    trigger = round(last_close * 1.005, 4)
    stop    = round(ma21 * 0.98, 4)
    target  = round(trigger * 1.12, 4)
    risk = trigger - stop
    if risk <= 0:
        return None

    return {
        "trigger": trigger,
        "stop": stop,
        "target": target,
        "meta": {
            "ma21":          round(ma21, 4),
            "close":         round(last_close, 4),
            "higher_highs":  len(kept),
            "last_pullback_to_ma21": True,
            "pct_above_ma21": round((last_close - ma21) / ma21 * 100, 2),
        },
    }


def scan(top_n: int = 200) -> list[dict]:
    if universe.is_bull_regime() is False:
        log.info("power_trend: bear regime — skipping scan")
        return []

    cands = universe.get_sepa_candidates(top_n=top_n)
    if not cands:
        log.info("power_trend: no SEPA candidates available")
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
            kind="power_trend",
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

    inserted = store.upsert_setups("power_trend", setups)
    log.info("power_trend: scanned %d candidates, %d setups inserted",
             len(cands), inserted)

    if setups:
        try:
            from sepa.notify import send_alert
            top = sorted(setups, key=lambda s: s["rr"], reverse=True)[:3]
            body = " · ".join(
                f"{s['symbol']} buy ≥ {s['trigger']:.2f} "
                f"(HHs {s['meta'].get('higher_highs')})"
                for s in top
            )
            send_alert(
                title=f"📈 {len(setups)} Kell Power Trend setups",
                body=body,
                kind="setup_power_trend",
                url="/kell?kind=power_trend",
            )
        except Exception as exc:
            log.warning("power_trend: push notify failed: %s", exc)

    return setups


if __name__ == "__main__":
    import json
    out = scan()
    print(json.dumps(
        [{"symbol": s["symbol"], "trigger": s["trigger"], "stop": s["stop"],
          "rr": s["rr"],
          "higher_highs": s["meta"].get("higher_highs"),
          "pct_above_ma21": s["meta"].get("pct_above_ma21")} for s in out],
        indent=2,
    ))
