"""Volatility Compression — Kell's ATR-based contraction.

Parallel to Minervini's VCP but uses ATR ratios + price-range
compression rather than base-structure shape. The thesis: volatility
contracts before expansion, regardless of whether the visible structure
forms a textbook three-touch base.

Detection rules (mechanical):
  1. ATR_10 < 0.7 × ATR_50               — recent volatility is 30%+
                                            below the long-term average.
  2. Last-week range:                     — 5-day high-low range under
       df[-5:].high.max() - df[-5:].low.min() < 0.8 × df[-1].close × 0.05
                                            ~= < 4% of price.
  3. Price within 5% of MA20 OR MA50     — coiled near a key MA.
  4. df[-10:].volume.mean() < 0.85 ×     — volume drying up.
       df[-50:].volume.mean()

Trigger / Stop / Target:
  - trigger = df[-5:].high.max() × 1.005  (top of the 5-day coil + buffer)
  - stop    = df[-5:].low.min()  - 1 cent (below the coil floor)
  - target  = trigger × 1.10  (Kell's typical 10% first leg on a
                               volatility-expansion break)

Expires after 120h (5 trading days — these can sit longer than other
breakouts because the compression itself signals patience). Top 150
SEPA candidates scanned.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from setups import store, universe

log = logging.getLogger("kell.volatility_compression")


_ATR_SHORT_WIN     = 10
_ATR_LONG_WIN      = 50
_ATR_RATIO_MAX     = 0.7
_RANGE_WIN         = 5
_RANGE_MAX_PCT     = 0.04          # 4% of price
_MA_PROX_PCT       = 0.05          # within 5% of MA20 or MA50
_VOL_DRY_RATIO     = 0.85          # 10d mean < 0.85 × 50d mean


def _atr(highs, lows, closes, window: int) -> float:
    """Wilder-style ATR over `window` sessions (using simple mean for
    smoothing — fine for ratio comparisons, faster than EMA, matches
    Kell's casual ATR usage in the book)."""
    if len(closes) < window + 1:
        return 0.0
    trs = []
    for i in range(1, window + 1):
        h, l, pc = float(highs[-i]), float(lows[-i]), float(closes[-i - 1])
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    return sum(trs) / len(trs)


def _detect(symbol: str) -> Optional[dict]:
    try:
        from sepa import prices
        df = prices.load_prices(symbol, period="6mo")
    except Exception as exc:
        log.debug("volatility_compression: price load failed for %s: %s", symbol, exc)
        return None
    if df is None or len(df) < _ATR_LONG_WIN + 5:
        return None

    closes = df["close"].values
    highs  = df["high"].values
    lows   = df["low"].values
    vols   = df["volume"].values

    last_close = float(closes[-1])
    if last_close <= 0:
        return None

    # 1) ATR ratio.
    atr_short = _atr(highs, lows, closes, _ATR_SHORT_WIN)
    atr_long  = _atr(highs, lows, closes, _ATR_LONG_WIN)
    if atr_long <= 0:
        return None
    atr_ratio = atr_short / atr_long
    if atr_ratio >= _ATR_RATIO_MAX:
        return None

    # 2) Last-week range under 4% of price. Spec form:
    #      range < 0.8 × close × 0.05   (i.e. < 4% of price).
    win_high = float(highs[-_RANGE_WIN:].max())
    win_low  = float(lows[-_RANGE_WIN:].min())
    range_pct = (win_high - win_low) / last_close
    if (win_high - win_low) >= 0.8 * last_close * 0.05:
        return None

    # 3) Within 5% of MA20 or MA50.
    ma20 = float(closes[-20:].mean())
    ma50 = float(closes[-50:].mean())
    near_ma20 = abs(last_close - ma20) / ma20 <= _MA_PROX_PCT if ma20 > 0 else False
    near_ma50 = abs(last_close - ma50) / ma50 <= _MA_PROX_PCT if ma50 > 0 else False
    if not (near_ma20 or near_ma50):
        return None

    # 4) Volume drying up.
    vol_10 = float(vols[-10:].mean())
    vol_50 = float(vols[-50:].mean())
    if vol_50 <= 0:
        return None
    vol_dry_ratio = vol_10 / vol_50
    if vol_dry_ratio >= _VOL_DRY_RATIO:
        return None

    trigger = round(win_high * 1.005, 4)
    stop    = round(win_low  - 0.01, 4)
    target  = round(trigger * 1.10, 4)
    risk = trigger - stop
    if risk <= 0:
        return None

    return {
        "trigger": trigger,
        "stop": stop,
        "target": target,
        "meta": {
            "atr_short":     round(atr_short, 4),
            "atr_long":      round(atr_long, 4),
            "atr_ratio":     round(atr_ratio, 3),
            "range_pct":     round(range_pct * 100, 2),
            "ma20":          round(ma20, 4),
            "ma50":          round(ma50, 4),
            "ma_anchor":     "ma20" if near_ma20 else "ma50",
            "vol_dry_ratio": round(vol_dry_ratio, 2),
            "coil_high":     round(win_high, 4),
            "coil_low":      round(win_low, 4),
            "close":         round(last_close, 4),
        },
    }


def scan(top_n: int = 150) -> list[dict]:
    if universe.is_bull_regime() is False:
        log.info("volatility_compression: bear regime — skipping scan")
        return []

    cands = universe.get_sepa_candidates(top_n=top_n)
    if not cands:
        log.info("volatility_compression: no SEPA candidates available")
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
            kind="volatility_compression",
            symbol=sym,
            trigger=result["trigger"],
            stop=result["stop"],
            target=result["target"],
            expires_in_hours=120,
            meta=meta,
        )

    with ThreadPoolExecutor(max_workers=8) as ex:
        for setup in ex.map(_process, cands):
            if setup is not None:
                setups.append(setup)

    inserted = store.upsert_setups("volatility_compression", setups)
    log.info("volatility_compression: scanned %d candidates, %d setups inserted",
             len(cands), inserted)

    if setups:
        try:
            from sepa.notify import send_alert
            top = sorted(setups, key=lambda s: s["rr"], reverse=True)[:3]
            body = " · ".join(
                f"{s['symbol']} buy ≥ {s['trigger']:.2f} "
                f"(ATR ratio {s['meta'].get('atr_ratio')})"
                for s in top
            )
            send_alert(
                title=f"🌀 {len(setups)} Kell Volatility Compression setups",
                body=body,
                kind="setup_volatility_compression",
                url="/kell?kind=volatility_compression",
            )
        except Exception as exc:
            log.warning("volatility_compression: push notify failed: %s", exc)

    return setups


if __name__ == "__main__":
    import json
    out = scan()
    print(json.dumps(
        [{"symbol": s["symbol"], "trigger": s["trigger"], "stop": s["stop"],
          "rr": s["rr"],
          "atr_ratio": s["meta"].get("atr_ratio"),
          "range_pct": s["meta"].get("range_pct"),
          "vol_dry_ratio": s["meta"].get("vol_dry_ratio")} for s in out],
        indent=2,
    ))
