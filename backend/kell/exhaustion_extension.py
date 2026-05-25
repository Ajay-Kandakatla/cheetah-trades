"""Exhaustion Extension — Oliver Kell, Cycle of Price Action.

Canonical source: "Victory in Stock Trading" (Kell, 2021), pp. 19, 25, 40.

Phase 5 of the CoPA cycle — the TOPPING WARNING. NOT a buy setup. Quoting
Kell p. 19 (cycle overview) and pp. 40 [G/H]:

  "(G) Exhaustion Extension — As we extend from the moving averages
   price is likely to snap back or rest/base to let the moving averages
   catch up."
  "(H1/H2) Exhaustion Extension / Bearish Engulfing / Shooting Star —
   The second extension is often a time to take profits as we are
   usually also extended from the 10 week EMA."

Kell explicitly says (p. 19):
  "(S) Blowoff Exhaustion — Price extends from the 10 EMA on the daily
   chart ... this is the second or third extension from the daily
   10 EMA since the traditional Flat Base breakout. Shorter to
   intermediate term traders may take profits as a longer basing
   period may be in store."

The 2nd-or-3rd-extension count is structurally important: the FIRST
extension can be held through; the SECOND is where you start to lighten;
the THIRD is the canonical "lock in gains" moment.

Detection (per pp. 19, 25, 40):
  1. Established uptrend for 30+ sessions: closes above 10 EMA for
     at least 20 of last 30 sessions.
  2. Price extended ABOVE the 10 EMA today:
       (df[-1].close - ema10) / ema10 >= 0.08  (8%+ above).
  3. df[-1] is wide-range OR a bearish reversal candle:
       a. Wide range: (high - low) / close > 0.05, AND
       b. EITHER heavy-volume close in UPPER half (climax — selling
          will start soon) OR bearish reversal close (close < open,
          shooting star / bearish engulfing).
  4. Volume: df[-1].volume > 2.0 × avg_volume_50.
  5. Count of prior extensions in last 60 sessions where
     extension_pct ≥ 0.08. If count ≥ 2, this is the 2nd or 3rd
     extension and is MORE actionable.

Signal: SELL_OR_TAKE_PROFITS — no trigger/stop/target for entry.
Tier: DEFENSIVE / WARN.
Expires 48h. Top 200 SEPA candidates.
Bear-regime gate: intentionally NOT applied. Warnings are valuable in
any regime (see §11 of KELL_CONTRACTS.md).
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from setups import store, universe

log = logging.getLogger("kell.exhaustion_extension")


# ── Locked thresholds — see docs/KELL_CONTRACTS.md §4.5
_TREND_AGE_WIN          = 30    # uptrend search window
_TREND_AGE_MIN          = 20    # closes above 10 EMA for >= 20 of last 30
_EXT_MIN_PCT            = 0.08  # close >= 8% above 10 EMA
_WIDE_RANGE_MIN         = 0.05  # (high - low) / close > 5%
_MIN_VOL_MULT           = 2.0   # df[-1].volume > 2.0 × avg_vol_50
_EXT_COUNT_WIN          = 60    # count prior extensions in last N sessions
_AVG_VOL_WINDOW         = 50


def _ema(series, span: int):
    return series.ewm(span=span, adjust=False).mean()


def _detect(symbol: str) -> Optional[dict]:
    try:
        from sepa import prices
        df = prices.load_prices(symbol, period="6mo")
    except Exception as exc:
        log.debug("exhaustion_extension: price load failed for %s: %s", symbol, exc)
        return None
    if df is None or len(df) < _AVG_VOL_WINDOW + _EXT_COUNT_WIN + 5:
        return None

    closes_s = df["close"]
    opens  = df["open"].values
    highs  = df["high"].values
    lows   = df["low"].values
    vols   = df["volume"].values

    ema10 = _ema(closes_s, 10).values
    closes = closes_s.values

    last_close = float(closes[-1])
    last_open  = float(opens[-1])
    last_high  = float(highs[-1])
    last_low   = float(lows[-1])
    last_ema10 = float(ema10[-1])
    if last_ema10 <= 0:
        return None

    # 1) Established uptrend: closes above 10 EMA for at least 20 of
    #    the last 30 sessions (looking at the bars BEFORE today —
    #    today is the extension itself).
    trend_closes = closes[-(_TREND_AGE_WIN + 1):-1]
    trend_ema10  = ema10[-(_TREND_AGE_WIN + 1):-1]
    above_count = sum(1 for i in range(_TREND_AGE_WIN) if trend_closes[i] > trend_ema10[i])
    if above_count < _TREND_AGE_MIN:
        return None

    # 2) Today's close extended ≥8% above 10 EMA.
    extension_pct = (last_close - last_ema10) / last_ema10
    if extension_pct < _EXT_MIN_PCT:
        return None

    # 3) Wide-range AND (heavy-vol upper-half OR bearish reversal close).
    bar_range = last_high - last_low
    if bar_range <= 0:
        return None
    range_ratio = bar_range / last_close
    if range_ratio <= _WIDE_RANGE_MIN:
        return None

    # Volume confirmation.
    avg_vol = float(vols[-_AVG_VOL_WINDOW - 1:-1].mean())
    if avg_vol <= 0:
        return None
    vol_mult = float(vols[-1]) / avg_vol
    if vol_mult <= _MIN_VOL_MULT:
        return None

    midpoint = last_low + bar_range / 2.0
    upper_half_close = last_close > midpoint
    bearish_close = last_close < last_open
    if not (upper_half_close or bearish_close):
        return None

    # 4) Count prior extensions in last 60 sessions where ext_pct ≥ 8%
    #    (closes against the 10 EMA at THAT bar). We only count distinct
    #    extensions — consecutive bars above 8% count as one event.
    win_closes = closes[-(_EXT_COUNT_WIN + 1):-1]
    win_ema10  = ema10[-(_EXT_COUNT_WIN + 1):-1]
    extension_count = 0
    in_extension = False
    for i in range(_EXT_COUNT_WIN):
        if win_ema10[i] <= 0:
            in_extension = False
            continue
        ext = (win_closes[i] - win_ema10[i]) / win_ema10[i]
        if ext >= _EXT_MIN_PCT:
            if not in_extension:
                extension_count += 1
                in_extension = True
        else:
            in_extension = False
    # Today is itself an extension — count it.
    extension_count += 1

    # SELL / take-profits — no entry math. We persist trigger = today's
    # low (alert level), stop = 0, target = 0; UI renders distinctly.
    return {
        "trigger": round(last_low, 4),
        "stop":    0.0,
        "target":  0.0,
        "meta": {
            "signal_type":      "SELL_OR_TAKE_PROFITS",
            "extension_pct":    round(extension_pct * 100, 2),
            "extension_count":  int(extension_count),
            "vol_mult":         round(vol_mult, 2),
            "range_ratio":      round(range_ratio, 3),
            "trend_age_days":   int(above_count),
            "upper_half_close": bool(upper_half_close),
            "bearish_close":    bool(bearish_close),
            "ema10":            round(last_ema10, 4),
            "close":            round(last_close, 4),
            "high":             round(last_high, 4),
            "low":              round(last_low, 4),
            "open":             round(last_open, 4),
        },
    }


def scan(top_n: int = 200) -> list[dict]:
    # Bear-regime gate NOT applied — warnings matter in any regime.
    cands = universe.get_sepa_candidates(top_n=top_n)
    if not cands:
        log.info("exhaustion_extension: no SEPA candidates available")
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
            kind="exhaustion_extension",
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

    inserted = store.upsert_setups("exhaustion_extension", setups)
    log.info(
        "exhaustion_extension: scanned %d candidates, %d warnings inserted",
        len(cands), inserted,
    )

    if setups:
        try:
            from sepa.notify import send_alert
            top = sorted(
                setups,
                key=lambda s: s["meta"].get("extension_pct", 0),
                reverse=True,
            )[:3]
            body = " · ".join(
                f"{s['symbol']} +{s['meta'].get('extension_pct')}% over 10EMA "
                f"({s['meta'].get('extension_count')}{_ordinal(s['meta'].get('extension_count', 1))} "
                f"ext, {s['meta'].get('vol_mult')}x vol)"
                for s in top
            )
            send_alert(
                title=f"⚠️ {len(setups)} Kell Exhaustion Extension warnings (TAKE PROFITS)",
                body=body,
                kind="setup_exhaustion_extension",
                url="/kell?kind=exhaustion_extension",
            )
        except Exception as exc:
            log.warning("exhaustion_extension: push notify failed: %s", exc)

    return setups


def _ordinal(n: int) -> str:
    if 10 <= (n % 100) <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


if __name__ == "__main__":
    import json
    out = scan()
    print(json.dumps(
        [{"symbol": s["symbol"], "alert_low": s["trigger"],
          "extension_pct":   s["meta"].get("extension_pct"),
          "extension_count": s["meta"].get("extension_count"),
          "vol_mult":        s["meta"].get("vol_mult")} for s in out],
        indent=2,
    ))
