"""Wedge Pop — Oliver Kell, Cycle of Price Action.

Canonical source: "Victory in Stock Trading" (Kell, 2021), pp. 17, 23-24.

Phase 2 of the CoPA cycle — the FIRST RECLAIM of the 10/20 EMAs after a
Reversal Extension. Price has been below the moving averages for a while
and has been tightening into them in a small wedge. Today the stock
"pops" back through both EMAs, signaling the beginning of a potential
new uptrend (often catalyst-driven — Kell uses TSLA's S&P-500 inclusion
in his $TSLA Phase 3 walkthrough on p. 26 as the canonical example).

Detection (per pp. 17, 23-24):
  1. Recent downtrend: average of last 14 closes (before today) is
     below the average 20 EMA over the same window.
  2. The 10 EMA and 20 EMA are CLOSE TOGETHER (tight cluster — Kell's
     "10/20 EMA reference" on p. 12): |ema10 - ema20| / ema20 < 0.02.
  3. Tight wedge into the EMAs — last 5-10 sessions show progressively
     higher lows AND tighter ranges (volatility contracting).
  4. TODAY: df[-1].close > ema10 AND df[-1].close > ema20 — the first
     close above BOTH EMAs in the last 10 sessions.
  5. df[-1] is bullish: close > open.
  6. Volume confirms: df[-1].volume >= avg_volume_50.

Stops & targets:
  - trigger = df[-1].high + 0.01
  - stop    = min(lows[-7:]) (below the wedge floor — pp. 49 "Ignition Bar Low"
                              applied to the start of the new pattern)
  - target  = df[-1].close × 1.10 (typical first leg)

Tier: MODERATE — second-chance entry, much cleaner than catching the
reversal bar itself but still in early Stage 1→2 transition.
Expires 72h. Top 200 SEPA candidates.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from setups import store, universe

log = logging.getLogger("kell.wedge_pop")


# ── Locked thresholds — see docs/KELL_CONTRACTS.md §4.2
_DOWNTREND_WIN          = 14    # closes-below-20EMA window for "trend down"
_EMA_CLUSTER_MAX_PCT    = 0.02  # |ema10 - ema20| / ema20 < 2%
_WEDGE_MIN_LEN          = 5
_WEDGE_MAX_LEN          = 10
_FIRST_CLOSE_LOOKBACK   = 10    # first close above BOTH EMAs in N sessions
_AVG_VOL_WINDOW         = 50
_STOP_LOOKBACK          = 7     # min(lows[-7:]) for stop


def _ema(series, span: int):
    return series.ewm(span=span, adjust=False).mean()


def _detect(symbol: str) -> Optional[dict]:
    try:
        from sepa import prices
        df = prices.load_prices(symbol, period="6mo")
    except Exception as exc:
        log.debug("wedge_pop: price load failed for %s: %s", symbol, exc)
        return None
    if df is None or len(df) < _AVG_VOL_WINDOW + _DOWNTREND_WIN + 5:
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
    last_high  = float(highs[-1])
    last_ema10 = float(ema10[-1])
    last_ema20 = float(ema20[-1])
    if last_ema20 <= 0:
        return None

    # 1) Recent downtrend: mean(close[-15:-1]) < mean(ema20[-15:-1]).
    recent_close_mean = float(closes[-(_DOWNTREND_WIN + 1):-1].mean())
    recent_ema20_mean = float(ema20[-(_DOWNTREND_WIN + 1):-1].mean())
    if recent_close_mean >= recent_ema20_mean:
        return None

    # 2) 10 / 20 EMAs tight together.
    ema_gap_pct = abs(last_ema10 - last_ema20) / last_ema20
    if ema_gap_pct >= _EMA_CLUSTER_MAX_PCT:
        return None

    # 3) Tight wedge into the EMAs over 5-10 sessions BEFORE today.
    #    Look for the longest valid wedge (progressively higher lows AND
    #    contracting daily ranges) in [5..10].
    wedge_len = None
    for L in range(_WEDGE_MAX_LEN, _WEDGE_MIN_LEN - 1, -1):
        seg_lows  = lows[-(L + 1):-1]
        seg_highs = highs[-(L + 1):-1]
        if len(seg_lows) < L:
            continue
        # Higher lows: each low >= the prior low (not strictly higher,
        # because flat lows ARE wedging, but require at least one strict
        # higher low so we're not flat-lining).
        lows_rising = all(seg_lows[i] <= seg_lows[i + 1] for i in range(L - 1))
        any_strict_higher_low = any(
            seg_lows[i] < seg_lows[i + 1] for i in range(L - 1)
        )
        # Ranges contracting: last 3 daily ranges' mean < first 3 daily
        # ranges' mean (volatility contracting).
        if L >= 6:
            ranges = seg_highs - seg_lows
            first_third = ranges[:3].mean()
            last_third  = ranges[-3:].mean()
            ranges_tighter = last_third < first_third
        else:
            ranges_tighter = True
        if lows_rising and any_strict_higher_low and ranges_tighter:
            wedge_len = L
            break
    if wedge_len is None:
        return None

    # 4) FIRST close above BOTH EMAs in the last 10 sessions. Today
    #    must satisfy close > ema10 AND close > ema20; the prior
    #    9 sessions must NOT have closed above both.
    if not (last_close > last_ema10 and last_close > last_ema20):
        return None
    prior_above_both = False
    for k in range(1, _FIRST_CLOSE_LOOKBACK):
        idx = -1 - k
        if closes[idx] > ema10[idx] and closes[idx] > ema20[idx]:
            prior_above_both = True
            break
    if prior_above_both:
        return None

    # 5) Bullish today.
    if last_close <= last_open:
        return None

    # 6) Volume confirms.
    avg_vol = float(vols[-_AVG_VOL_WINDOW - 1:-1].mean())
    if avg_vol <= 0:
        return None
    vol_mult = float(vols[-1]) / avg_vol
    if vol_mult < 1.0:
        return None

    # 7) Trigger / stop / target.
    stop_floor = float(lows[-_STOP_LOOKBACK:].min())
    trigger = round(last_high + 0.01, 4)
    stop    = round(stop_floor, 4)
    target  = round(last_close * 1.10, 4)
    risk = trigger - stop
    if risk <= 0:
        return None

    return {
        "trigger": trigger,
        "stop":    stop,
        "target":  target,
        "meta": {
            "ema10":          round(last_ema10, 4),
            "ema20":          round(last_ema20, 4),
            "ema_gap_pct":    round(ema_gap_pct * 100, 3),
            "wedge_len":      int(wedge_len),
            "vol_mult":       round(vol_mult, 2),
            "close_above_ema10": round((last_close - last_ema10) / last_ema10 * 100, 2),
            "close_above_ema20": round((last_close - last_ema20) / last_ema20 * 100, 2),
            "wedge_floor":    round(stop_floor, 4),
        },
    }


def scan(top_n: int = 200) -> list[dict]:
    # Bull-regime gated — Wedge Pop is a BUY setup.
    if universe.is_bull_regime() is False:
        log.info("wedge_pop: bear regime — skipping scan")
        return []

    cands = universe.get_sepa_candidates(top_n=top_n)
    if not cands:
        log.info("wedge_pop: no SEPA candidates available")
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
            kind="wedge_pop",
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

    inserted = store.upsert_setups("wedge_pop", setups)
    log.info(
        "wedge_pop: scanned %d candidates, %d setups inserted",
        len(cands), inserted,
    )

    if setups:
        try:
            from sepa.notify import send_alert
            top = sorted(setups, key=lambda s: s["rr"], reverse=True)[:3]
            body = " · ".join(
                f"{s['symbol']} buy ≥ {s['trigger']:.2f} "
                f"(wedge {s['meta'].get('wedge_len')}d / {s['meta'].get('vol_mult')}x)"
                for s in top
            )
            send_alert(
                title=f"🎈 {len(setups)} Kell Wedge Pop setups",
                body=body,
                kind="setup_wedge_pop",
                url="/kell?kind=wedge_pop",
            )
        except Exception as exc:
            log.warning("wedge_pop: push notify failed: %s", exc)

    return setups


if __name__ == "__main__":
    import json
    out = scan()
    print(json.dumps(
        [{"symbol": s["symbol"], "trigger": s["trigger"], "stop": s["stop"],
          "target": s["target"], "rr": s["rr"],
          "wedge_len": s["meta"].get("wedge_len"),
          "vol_mult":  s["meta"].get("vol_mult")} for s in out],
        indent=2,
    ))
