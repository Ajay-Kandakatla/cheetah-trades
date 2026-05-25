"""Climax Run — Kell's blow-off / exhaustion warning.

NOT an entry. This is the DEFENSIVE scanner: when a Stage-2 stock goes
parabolic and prints a wide-range distribution bar on huge volume,
Kell's playbook says SELL or TAKE PROFITS. The pattern flags positions
to lighten, not new positions to enter.

Detection rules (mechanical):
  1. 30-session return > 50%               — sharp run-up.
  2. df[-1] is a wide-range bar:
        (high - low) / close > 0.05        — at least 5% intraday range.
  3. df[-1].volume > 2.5 × avg_volume_50   — climactic volume.
  4. df[-1] looks distributive:
        close < open OR close in lower     — red candle OR weak close.
        third of the day's range
  5. Stretched above MA50:
        (close - MA50) / MA50 > 0.30       — price 30%+ above 50-day.

This is a SELL/take-profit signal — there is no trigger/stop/target.
We persist it with trigger = df[-1].low (the alert level), stop = 0,
target = 0, and meta.signal_type = "SELL_OR_TAKE_PROFITS" so the UI
can render the row distinctly (red border, no R:R math).

Expires after 48h. Top 200 SEPA candidates scanned.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from setups import store, universe

log = logging.getLogger("kell.climax_run")


_RUN_WIN              = 30
_MIN_RUN_PCT          = 50.0
_MIN_RANGE_RATIO      = 0.05
_MIN_VOL_MULT         = 2.5
_MIN_MA50_STRETCH     = 0.30   # price 30%+ above 50d MA
_LOWER_THIRD_RATIO    = 1.0 / 3.0
_AVG_VOL_WINDOW       = 50


def _detect(symbol: str) -> Optional[dict]:
    try:
        from sepa import prices
        df = prices.load_prices(symbol, period="6mo")
    except Exception as exc:
        log.debug("climax_run: price load failed for %s: %s", symbol, exc)
        return None
    if df is None or len(df) < _AVG_VOL_WINDOW + _RUN_WIN + 2:
        return None

    closes = df["close"].values
    opens  = df["open"].values
    highs  = df["high"].values
    lows   = df["low"].values
    vols   = df["volume"].values

    last_close = float(closes[-1])
    last_open  = float(opens[-1])
    last_high  = float(highs[-1])
    last_low   = float(lows[-1])
    if last_close <= 0:
        return None

    # 1) 30-session return > 50%.
    ref_close = float(closes[-_RUN_WIN - 1])
    if ref_close <= 0:
        return None
    run_pct = (last_close - ref_close) / ref_close * 100
    if run_pct <= _MIN_RUN_PCT:
        return None

    # 2) Wide-range bar.
    bar_range = last_high - last_low
    if bar_range <= 0:
        return None
    range_ratio = bar_range / last_close
    if range_ratio <= _MIN_RANGE_RATIO:
        return None

    # 3) Climactic volume.
    avg_vol = float(vols[-_AVG_VOL_WINDOW - 1 : -1].mean())
    if avg_vol <= 0:
        return None
    vol_mult = float(vols[-1]) / avg_vol
    if vol_mult <= _MIN_VOL_MULT:
        return None

    # 4) Distribution character: red candle OR close in lower third of range.
    lower_third_top = last_low + bar_range * _LOWER_THIRD_RATIO
    is_red = last_close < last_open
    is_weak_close = last_close <= lower_third_top
    if not (is_red or is_weak_close):
        return None

    # 5) Stretched above MA50.
    ma50 = float(closes[-50:].mean())
    if ma50 <= 0:
        return None
    stretch = (last_close - ma50) / ma50
    if stretch <= _MIN_MA50_STRETCH:
        return None

    # SELL/take-profits — no trigger/stop/target math. We persist
    # trigger = today's low (alert level), stop = 0, target = 0, and let
    # the UI render the row as a warning rather than an entry.
    return {
        "trigger": round(last_low, 4),
        "stop":    0.0,
        "target":  0.0,
        "meta": {
            "signal_type":    "SELL_OR_TAKE_PROFITS",
            "run_pct_30d":    round(run_pct, 2),
            "range_ratio":    round(range_ratio, 3),
            "vol_mult":       round(vol_mult, 2),
            "ma50_stretch":   round(stretch * 100, 2),  # percent
            "is_red_candle":  bool(is_red),
            "is_weak_close":  bool(is_weak_close),
            "close":          round(last_close, 4),
            "open":           round(last_open, 4),
            "high":           round(last_high, 4),
            "low":            round(last_low, 4),
            "ma50":           round(ma50, 4),
        },
    }


def scan(top_n: int = 200) -> list[dict]:
    """Climax-run scan — runs in any regime (warning signals are useful
    regardless of broader market health). The other scanners short-circuit
    in bear regimes, but a blow-off WARNING in a bear market is arguably
    even more valuable. Kept consistent with the spec which doesn't
    explicitly bear-gate this pattern."""
    cands = universe.get_sepa_candidates(top_n=top_n)
    if not cands:
        log.info("climax_run: no SEPA candidates available")
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
            kind="climax_run",
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

    inserted = store.upsert_setups("climax_run", setups)
    log.info("climax_run: scanned %d candidates, %d warnings inserted",
             len(cands), inserted)

    if setups:
        try:
            from sepa.notify import send_alert
            # Sort by 30-day run % desc — the most-stretched names first
            # so the warning push surfaces the riskiest holdings.
            top = sorted(
                setups,
                key=lambda s: s["meta"].get("run_pct_30d", 0),
                reverse=True,
            )[:3]
            body = " · ".join(
                f"{s['symbol']} +{s['meta'].get('run_pct_30d')}% in 30d "
                f"on {s['meta'].get('vol_mult')}x"
                for s in top
            )
            send_alert(
                title=f"⚠️ {len(setups)} Kell Climax-Run warnings (TAKE PROFITS)",
                body=body,
                kind="setup_climax_run",
                url="/kell?kind=climax_run",
            )
        except Exception as exc:
            log.warning("climax_run: push notify failed: %s", exc)

    return setups


if __name__ == "__main__":
    import json
    out = scan()
    print(json.dumps(
        [{"symbol": s["symbol"], "alert_low": s["trigger"],
          "run_pct_30d": s["meta"].get("run_pct_30d"),
          "vol_mult":    s["meta"].get("vol_mult"),
          "stretch_pct": s["meta"].get("ma50_stretch")} for s in out],
        indent=2,
    ))
