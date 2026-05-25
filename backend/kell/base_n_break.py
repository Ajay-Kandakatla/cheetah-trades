"""Base n' Break — Oliver Kell, Cycle of Price Action.

Canonical source: "Victory in Stock Trading" (Kell, 2021), pp. 18-19, 24, 39.

Phase 4 of the CoPA cycle — the LONGER consolidation breakout. Quoting
Kell p. 39 on the $TWLO Daily example:

  "(D) Base n' Break — This basing pattern represents the first
   consolidation into the 10/20 EMA after the higher time frame base
   breakout and is a lower risk area to buy against the moving
   averages and add on the breakout."

The pattern: stock holds above the 10/20 EMA cluster for 5-15 days in a
tight range with volume drying, THEN today's bar breaks out of that
range on expanding volume.

Detection (per pp. 18-19, 24, 39):
  1. Confirmed uptrend stack: ema10 > ema20 > sma50 for at least the
     last 5 sessions.
  2. Longer base — pick best window length N ∈ [5, 15] satisfying:
       a. (highs[-N:].max() - lows[-N:].min()) / df[-N].close ≤ 0.10
          (range ≤ 10% of price).
       b. All N closes within 3% of either ema10 or ema20:
          min(|close-ema10|/ema10, |close-ema20|/ema20) ≤ 0.03.
       c. Volume drying: mean(volume[-N:]) < 0.85 × avg_volume_50.
  3. TODAY: df[-1].close > max(highs[-N-1:-1])  (breakout TODAY above
     base resistance, computed over the bars BEFORE today).
  4. Volume expands: df[-1].volume > 1.3 × avg_volume_50.

Stops & targets (per pp. 48-49):
  - trigger = max(highs[-N-1:-1]) + 0.01  (the breakout pivot)
  - stop    = min(ema20, min(lows[-N-1:-1])) - 0.01
              (per "Breakout Day / Reason For Buying Low" — pp. 48,
              and the 20 EMA as a structural floor)
  - target  = trigger × 1.10

Tier: SAFE — Kell calls this "lower risk area to buy against the moving
averages." Already broken out so the window is short (48h).
Top 200 SEPA candidates.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from setups import store, universe

log = logging.getLogger("kell.base_n_break")


# ── Locked thresholds — see docs/KELL_CONTRACTS.md §4.4
_BASE_MIN_LEN          = 5
_BASE_MAX_LEN          = 15
_BASE_MAX_RANGE_PCT    = 0.10   # range ≤ 10% of price
_BASE_NEAR_EMA_PCT     = 0.03   # within 3% of ema10 or ema20
_BASE_VOL_DRY_RATIO    = 0.85   # mean(vol[-N:]) < 0.85 × avg_vol_50
_BREAKOUT_VOL_MULT     = 1.3    # today's vol > 1.3 × avg_vol_50
_AVG_VOL_WINDOW        = 50
_TREND_STACK_DAYS      = 5      # ema10>ema20>sma50 for this many sessions


def _ema(series, span: int):
    return series.ewm(span=span, adjust=False).mean()


def _detect(symbol: str) -> Optional[dict]:
    try:
        from sepa import prices
        df = prices.load_prices(symbol, period="6mo")
    except Exception as exc:
        log.debug("base_n_break: price load failed for %s: %s", symbol, exc)
        return None
    if df is None or len(df) < _AVG_VOL_WINDOW + _BASE_MAX_LEN + 10:
        return None

    closes_s = df["close"]
    highs  = df["high"].values
    lows   = df["low"].values
    vols   = df["volume"].values

    ema10 = _ema(closes_s, 10).values
    ema20 = _ema(closes_s, 20).values
    sma50 = closes_s.rolling(50).mean().values
    closes = closes_s.values

    # 1) Uptrend stack ema10 > ema20 > sma50 for the last 5 sessions.
    for k in range(_TREND_STACK_DAYS):
        idx = -1 - k
        e10 = ema10[idx]; e20 = ema20[idx]; s50 = sma50[idx]
        if not (s50 == s50):  # NaN
            return None
        if not (e10 > e20 > s50):
            return None

    avg_vol = float(vols[-_AVG_VOL_WINDOW - 1:-1].mean())
    if avg_vol <= 0:
        return None

    last_close = float(closes[-1])
    last_vol   = float(vols[-1])

    # 2) Search for the LONGEST valid base in [5..15] BEFORE today.
    best_N = None
    best_pivot = None
    best_base_low = None
    best_range_pct = None
    best_vol_dry = None
    best_anchor_pct = None
    for N in range(_BASE_MAX_LEN, _BASE_MIN_LEN - 1, -1):
        # Window is the N bars ENDING the day before today (today is the
        # breakout, the base must be in the PRIOR consolidation).
        end = -1
        start = end - N
        if -start > len(df):
            continue
        base_highs  = highs[start:end]
        base_lows   = lows[start:end]
        base_closes = closes[start:end]
        base_ema10  = ema10[start:end]
        base_ema20  = ema20[start:end]
        base_vols   = vols[start:end]
        if len(base_highs) < N:
            continue
        ref_close = float(base_closes[0])
        if ref_close <= 0:
            continue
        # a) Range constraint.
        rng = float(base_highs.max()) - float(base_lows.min())
        range_pct = rng / ref_close
        if range_pct > _BASE_MAX_RANGE_PCT:
            continue
        # b) Every close within 3% of either 10 EMA or 20 EMA.
        ok = True
        max_anchor_pct = 0.0
        for j in range(N):
            c = float(base_closes[j])
            e1 = float(base_ema10[j])
            e2 = float(base_ema20[j])
            dist1 = abs(c - e1) / e1 if e1 > 0 else 1e9
            dist2 = abs(c - e2) / e2 if e2 > 0 else 1e9
            anchor = min(dist1, dist2)
            if anchor > _BASE_NEAR_EMA_PCT:
                ok = False
                break
            if anchor > max_anchor_pct:
                max_anchor_pct = anchor
        if not ok:
            continue
        # c) Volume drying.
        vol_dry = float(base_vols.mean()) / avg_vol
        if vol_dry >= _BASE_VOL_DRY_RATIO:
            continue

        pivot = float(base_highs.max())
        # 3) Today's close MUST be above the base's highest high.
        if last_close <= pivot:
            continue
        # Capture LONGEST base — break out of outer loop once found.
        best_N = N
        best_pivot = pivot
        best_base_low = float(base_lows.min())
        best_range_pct = range_pct
        best_vol_dry = vol_dry
        best_anchor_pct = max_anchor_pct
        break

    if best_N is None:
        return None

    # 4) Volume expansion on the breakout bar.
    vol_mult = last_vol / avg_vol
    if vol_mult <= _BREAKOUT_VOL_MULT:
        return None

    # 5) Trigger / stop / target.
    last_ema20 = float(ema20[-1])
    trigger = round(best_pivot + 0.01, 4)
    stop    = round(min(last_ema20, best_base_low) - 0.01, 4)
    target  = round(trigger * 1.10, 4)
    risk = trigger - stop
    if risk <= 0:
        return None

    return {
        "trigger": trigger,
        "stop":    stop,
        "target":  target,
        "meta": {
            "base_len":         int(best_N),
            "pivot":            round(best_pivot, 4),
            "base_low":         round(best_base_low, 4),
            "range_pct":        round(best_range_pct * 100, 2),
            "ema_anchor_pct":   round(best_anchor_pct * 100, 2),
            "vol_dry_ratio":    round(best_vol_dry, 2),
            "breakout_vol_mult": round(vol_mult, 2),
            "ema20":            round(last_ema20, 4),
            "close":            round(last_close, 4),
        },
    }


def scan(top_n: int = 200) -> list[dict]:
    # Bull-regime gated — Base n' Break is a BUY setup.
    if universe.is_bull_regime() is False:
        log.info("base_n_break: bear regime — skipping scan")
        return []

    cands = universe.get_sepa_candidates(top_n=top_n)
    if not cands:
        log.info("base_n_break: no SEPA candidates available")
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
            kind="base_n_break",
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

    inserted = store.upsert_setups("base_n_break", setups)
    log.info(
        "base_n_break: scanned %d candidates, %d setups inserted",
        len(cands), inserted,
    )

    if setups:
        try:
            from sepa.notify import send_alert
            top = sorted(setups, key=lambda s: s["rr"], reverse=True)[:3]
            body = " · ".join(
                f"{s['symbol']} buy ≥ {s['trigger']:.2f} "
                f"({s['meta'].get('base_len')}d base / "
                f"{s['meta'].get('breakout_vol_mult')}x vol)"
                for s in top
            )
            send_alert(
                title=f"💥 {len(setups)} Kell Base n' Break setups",
                body=body,
                kind="setup_base_n_break",
                url="/kell?kind=base_n_break",
            )
        except Exception as exc:
            log.warning("base_n_break: push notify failed: %s", exc)

    return setups


if __name__ == "__main__":
    import json
    out = scan()
    print(json.dumps(
        [{"symbol": s["symbol"], "trigger": s["trigger"], "stop": s["stop"],
          "target": s["target"], "rr": s["rr"],
          "base_len":          s["meta"].get("base_len"),
          "breakout_vol_mult": s["meta"].get("breakout_vol_mult")} for s in out],
        indent=2,
    ))
