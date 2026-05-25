"""Wedge Drop — Oliver Kell, Cycle of Price Action.

Canonical source: "Victory in Stock Trading" (Kell, 2021), pp. 18, 20, 24, 41.

Phase 6 of the CoPA cycle — the END of the uptrend. NOT a buy setup;
this is the CONFIRMATION that the prior Exhaustion Extension was the
real top. Quoting Kell p. 27:

  "[U] Wedge Drop — Price gaps down on earnings and loses the 20 EMA,
   confirming the reversal exhaustion, and officially ending the
   uptrend cycle."

And p. 41:
  "(J) Wedge Drop — After 'Wedging' higher in a tight little channel
   without showing the ability to re-base in a proper fashion, the
   stock 'Drops' back down through the 10/20 EMA confirming an end to
   the intermediate term trend and marks a true end to an advance in
   the stock."

Detection (per pp. 18, 20, 24, 41):
  1. There was an Exhaustion Extension in the last 5-15 sessions —
     a wide-range bar with vol > 2.0× avg where close was > 8% above
     10 EMA at that time.
  2. Since that extension, price has tried to wedge higher in a tight
     range (informational — captured in meta).
  3. TODAY: df[-1].close < ema10 AND df[-1].close < ema20 — the FIRST
     close BELOW both EMAs in the last 10 sessions.
  4. df[-1] is bearish: close < open AND close < df[-2].close.
  5. Volume confirms breakdown: df[-1].volume > 1.3 × avg_volume_50.

Signal: SELL_OR_TAKE_PROFITS — no trigger/stop/target for entry.
Tier: DEFENSIVE / WARN.
Expires 72h. Top 200 SEPA candidates.
Bear-regime gate: intentionally NOT applied — see §11 of KELL_CONTRACTS.md.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from setups import store, universe

log = logging.getLogger("kell.wedge_drop")


# ── Locked thresholds — see docs/KELL_CONTRACTS.md §4.6
_EXHAUSTION_LOOKBACK_MIN = 5     # extension must be at least 5 sessions ago
_EXHAUSTION_LOOKBACK_MAX = 15    # ... and at most 15 sessions ago
_EXT_MIN_PCT             = 0.08  # historical extension threshold
_EXT_MIN_VOL_MULT        = 2.0   # historical extension volume threshold
_FIRST_CLOSE_LOOKBACK    = 10    # first close BELOW both EMAs in N sessions
_MIN_VOL_MULT            = 1.3   # df[-1].volume > 1.3 × avg_volume_50
_AVG_VOL_WINDOW          = 50


def _ema(series, span: int):
    return series.ewm(span=span, adjust=False).mean()


def _detect(symbol: str) -> Optional[dict]:
    try:
        from sepa import prices
        df = prices.load_prices(symbol, period="6mo")
    except Exception as exc:
        log.debug("wedge_drop: price load failed for %s: %s", symbol, exc)
        return None
    if df is None or len(df) < _AVG_VOL_WINDOW + _EXHAUSTION_LOOKBACK_MAX + 5:
        return None

    closes_s = df["close"]
    opens  = df["open"].values
    highs  = df["high"].values
    lows   = df["low"].values
    vols   = df["volume"].values

    ema10 = _ema(closes_s, 10).values
    ema20 = _ema(closes_s, 20).values
    closes = closes_s.values

    last_close = float(closes[-1])
    last_open  = float(opens[-1])
    prev_close = float(closes[-2])
    last_ema10 = float(ema10[-1])
    last_ema20 = float(ema20[-1])

    avg_vol = float(vols[-_AVG_VOL_WINDOW - 1:-1].mean())
    if avg_vol <= 0:
        return None

    # 1) An Exhaustion Extension exists in last 5-15 sessions: a bar
    #    with vol > 2.0× avg AND (high-low)/close > 0.05 AND
    #    (close - ema10) / ema10 > 8% at THAT bar.
    exhaustion_days_ago = None
    exhaustion_ext_pct = None
    for k in range(_EXHAUSTION_LOOKBACK_MIN, _EXHAUSTION_LOOKBACK_MAX + 1):
        idx = -1 - k
        if -idx > len(df):
            continue
        e10 = float(ema10[idx])
        if e10 <= 0:
            continue
        c = float(closes[idx])
        ext = (c - e10) / e10
        if ext < _EXT_MIN_PCT:
            continue
        h = float(highs[idx]); lo = float(lows[idx])
        if c <= 0 or (h - lo) / c <= 0.05:
            continue
        vol_at = float(vols[idx]) / avg_vol
        if vol_at <= _EXT_MIN_VOL_MULT:
            continue
        exhaustion_days_ago = k
        exhaustion_ext_pct = ext
        break
    if exhaustion_days_ago is None:
        return None

    # 2) TODAY: first close BELOW both EMAs in last 10 sessions.
    if not (last_close < last_ema10 and last_close < last_ema20):
        return None
    prior_below_both = False
    for k in range(1, _FIRST_CLOSE_LOOKBACK):
        idx = -1 - k
        if closes[idx] < ema10[idx] and closes[idx] < ema20[idx]:
            prior_below_both = True
            break
    if prior_below_both:
        return None

    # 3) Bearish today.
    if last_close >= last_open:
        return None
    if last_close >= prev_close:
        return None

    # 4) Volume confirms breakdown.
    vol_mult = float(vols[-1]) / avg_vol
    if vol_mult <= _MIN_VOL_MULT:
        return None

    # 5) Drop % — how far below the EMAs we closed (avg of the two).
    avg_ema = (last_ema10 + last_ema20) / 2.0
    if avg_ema <= 0:
        return None
    drop_pct = (avg_ema - last_close) / avg_ema

    return {
        "trigger": round(float(lows[-1]), 4),
        "stop":    0.0,
        "target":  0.0,
        "meta": {
            "signal_type":         "SELL_OR_TAKE_PROFITS",
            "exhaustion_days_ago": int(exhaustion_days_ago),
            "exhaustion_ext_pct":  round((exhaustion_ext_pct or 0) * 100, 2),
            "drop_pct":            round(drop_pct * 100, 2),
            "vol_mult":            round(vol_mult, 2),
            "ema10":               round(last_ema10, 4),
            "ema20":               round(last_ema20, 4),
            "close":               round(last_close, 4),
            "open":                round(last_open, 4),
            "prev_close":          round(prev_close, 4),
        },
    }


def scan(top_n: int = 200) -> list[dict]:
    # Bear-regime gate NOT applied — warnings matter in any regime.
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
    log.info(
        "wedge_drop: scanned %d candidates, %d warnings inserted",
        len(cands), inserted,
    )

    if setups:
        try:
            from sepa.notify import send_alert
            top = sorted(
                setups,
                key=lambda s: s["meta"].get("drop_pct", 0),
                reverse=True,
            )[:3]
            body = " · ".join(
                f"{s['symbol']} lost EMAs ({s['meta'].get('drop_pct')}% under, "
                f"{s['meta'].get('vol_mult')}x vol)"
                for s in top
            )
            send_alert(
                title=f"🔻 {len(setups)} Kell Wedge Drop warnings (CYCLE END)",
                body=body,
                kind="setup_wedge_drop",
                url="/kell?kind=wedge_drop",
            )
        except Exception as exc:
            log.warning("wedge_drop: push notify failed: %s", exc)

    return setups


if __name__ == "__main__":
    import json
    out = scan()
    print(json.dumps(
        [{"symbol": s["symbol"], "alert_low": s["trigger"],
          "drop_pct":            s["meta"].get("drop_pct"),
          "exhaustion_days_ago": s["meta"].get("exhaustion_days_ago"),
          "vol_mult":            s["meta"].get("vol_mult")} for s in out],
        indent=2,
    ))
