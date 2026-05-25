"""Reversal Extension — Oliver Kell, Cycle of Price Action.

Canonical source: "Victory in Stock Trading" (Kell, 2021), pp. 16, 22-23.

Phase 1 of the CoPA cycle — the capitulation bottom. After a downtrend
that has stretched price WELL BELOW the 10 EMA, a single high-volume
bullish reversal bar prints. This is the moment supply gets exhausted
and the first buyers step back in. The TURN is risky to catch but the
risk/reward is asymmetric because the next phase (Wedge Pop) gives a
much cleaner second-chance entry.

Detection (per pp. 16, 22-23):
  1. Recent downtrend: closes were below the 10 EMA for at least the
     last 5 sessions.
  2. Price is EXTENDED below the 10 EMA — today's low is ≥5% below the
     10 EMA: `(ema10 - df[-1].low) / ema10 >= 0.05`.
  3. df[-1] is a BULLISH REVERSAL BAR:
       - close > open (green candle), AND
       - close > df[-2].high (engulfs prior bar's high) OR
         close > (high + low) / 2 (closes in upper half of range).
  4. Heavy volume capitulation: df[-1].volume > 1.5 × avg_volume_50.
  5. (Soft confluence) Near 50 SMA or 200 SMA as higher-TF support
     (within 3%) — captured in meta but not required.

Stops & targets (per pp. 47-51 — Stop Loss Placement):
  - trigger = df[-1].high + 0.01    (above the reversal bar)
  - stop    = df[-1].low  - 0.01    (below the reversal bar; the
                                     "breakout day low" rule from
                                     pp. 48 — if the reversal bar's
                                     low is taken out, sellers
                                     overwhelmed the heavy volume).
  - target  = 20 EMA (Kell's first profit target: "20 EMA on the
                      trading timeframe" — pp. 26-27).

Tier: AGGRESSIVE — bottom-fishing is the riskiest phase.
Expires 96h. Top 200 SEPA candidates.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from setups import store, universe

log = logging.getLogger("kell.reversal_extension")


# ── Locked thresholds — see docs/KELL_CONTRACTS.md §4.1
_DOWNTREND_MIN_DAYS    = 5      # closes below 10 EMA for last N sessions
_EXTENSION_MIN_PCT     = 0.05   # low ≥5% below 10 EMA
_MIN_VOL_MULT          = 1.5    # df[-1].volume vs 50d avg
_AVG_VOL_WINDOW        = 50
_HTF_SUPPORT_PCT       = 0.03   # within 3% of 50 SMA or 200 SMA (informational)


def _ema(series, span: int):
    """Exponential moving average. Matches pandas
    `series.ewm(span=span, adjust=False).mean()`."""
    return series.ewm(span=span, adjust=False).mean()


def _detect(symbol: str) -> Optional[dict]:
    try:
        from sepa import prices
        df = prices.load_prices(symbol, period="1y")
    except Exception as exc:
        log.debug("reversal_extension: price load failed for %s: %s", symbol, exc)
        return None
    # Need 200 SMA → require at least 200 + a few bars.
    if df is None or len(df) < 205:
        return None

    closes = df["close"]
    opens  = df["open"].values
    highs  = df["high"].values
    lows   = df["low"].values
    vols   = df["volume"].values

    ema10  = _ema(closes, 10).values
    sma50  = closes.rolling(50).mean().values
    sma200 = closes.rolling(200).mean().values
    closes = closes.values

    last_close = float(closes[-1])
    last_open  = float(opens[-1])
    last_high  = float(highs[-1])
    last_low   = float(lows[-1])
    prev_high  = float(highs[-2])

    last_ema10 = float(ema10[-1])
    last_sma50 = float(sma50[-1]) if sma50[-1] == sma50[-1] else 0.0  # NaN guard
    last_sma200 = float(sma200[-1]) if sma200[-1] == sma200[-1] else 0.0

    # 1) Recent downtrend — closes < 10 EMA for at least last 5 sessions
    # BEFORE today (we look at df[-(N+1):-1] so today's bar doesn't have
    # to satisfy the downtrend rule — today IS the reversal).
    recent_closes = closes[-(_DOWNTREND_MIN_DAYS + 1):-1]
    recent_ema10  = ema10[-(_DOWNTREND_MIN_DAYS + 1):-1]
    if not all(recent_closes[i] < recent_ema10[i] for i in range(_DOWNTREND_MIN_DAYS)):
        return None

    # 2) Extended below 10 EMA — today's LOW is ≥5% below the EMA.
    if last_ema10 <= 0:
        return None
    extension_pct = (last_ema10 - last_low) / last_ema10
    if extension_pct < _EXTENSION_MIN_PCT:
        return None

    # 3) Bullish reversal bar.
    if last_close <= last_open:
        return None
    bar_range = last_high - last_low
    if bar_range <= 0:
        return None
    midpoint = last_low + bar_range / 2.0
    engulfs_prior = last_close > prev_high
    closes_upper_half = last_close > midpoint
    if not (engulfs_prior or closes_upper_half):
        return None

    # 4) Heavy capitulation volume.
    avg_vol = float(vols[-_AVG_VOL_WINDOW - 1:-1].mean())
    if avg_vol <= 0:
        return None
    vol_mult = float(vols[-1]) / avg_vol
    if vol_mult <= _MIN_VOL_MULT:
        return None

    # 5) HTF support confluence (informational only).
    near_50  = (last_sma50  > 0 and abs(last_close - last_sma50)  / last_sma50  <= _HTF_SUPPORT_PCT)
    near_200 = (last_sma200 > 0 and abs(last_close - last_sma200) / last_sma200 <= _HTF_SUPPORT_PCT)

    # 6) Trigger / stop / target.
    # Target = current 20 EMA (Kell's first take-profit per pp. 26-27).
    ema20 = float(_ema(df["close"], 20).values[-1])
    trigger = round(last_high + 0.01, 4)
    stop    = round(last_low - 0.01, 4)
    target  = round(ema20, 4)

    risk = trigger - stop
    if risk <= 0:
        return None
    # If target <= trigger (we already closed at/above 20 EMA — too late
    # to enter, the reversal has already run too far), skip.
    if target <= trigger:
        return None

    return {
        "trigger": trigger,
        "stop":    stop,
        "target":  target,
        "meta": {
            "ema10":            round(last_ema10, 4),
            "ema20":            round(ema20, 4),
            "sma50":            round(last_sma50, 4),
            "sma200":           round(last_sma200, 4),
            "extension_pct":    round(extension_pct * 100, 2),
            "vol_mult":         round(vol_mult, 2),
            "engulfs_prior":    bool(engulfs_prior),
            "closes_upper_half": bool(closes_upper_half),
            "near_50_sma":      bool(near_50),
            "near_200_sma":     bool(near_200),
            "reversal_close":   round(last_close, 4),
            "reversal_high":    round(last_high, 4),
            "reversal_low":     round(last_low, 4),
        },
    }


def scan(top_n: int = 200) -> list[dict]:
    # Bull-regime gated — Reversal Extension is a BUY setup.
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
    log.info(
        "reversal_extension: scanned %d candidates, %d setups inserted",
        len(cands), inserted,
    )

    if setups:
        try:
            from sepa.notify import send_alert
            top = sorted(setups, key=lambda s: s["rr"], reverse=True)[:3]
            body = " · ".join(
                f"{s['symbol']} buy ≥ {s['trigger']:.2f} "
                f"(ext {s['meta'].get('extension_pct')}% / "
                f"{s['meta'].get('vol_mult')}x vol)"
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
          "target": s["target"], "rr": s["rr"],
          "extension_pct": s["meta"].get("extension_pct"),
          "vol_mult":      s["meta"].get("vol_mult")} for s in out],
        indent=2,
    ))
