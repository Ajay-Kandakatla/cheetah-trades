"""Bull-flag continuation scanner — strong leg-up followed by a tight rest.

Setup definition (mechanical):
  1. Find the most recent strong leg-up: in the last 30 sessions, the
     highest rolling 5-day return must be at least 15%.
  2. From the peak of that leg, scan forward for a 5-15 session
     consolidation that:
       - never closes more than 15% below the peak (shallow pullback),
       - never makes a new high above peak × 1.02 (i.e. not yet a new leg),
       - started within the last 25 sessions and ends within the last 5.
  3. Average volume during the consolidation must be lower than during
     the leg-up (volume drying up = healthy digestion).

  Trigger: flag_high + 1 cent.
  Stop:    flag_low  - 1 cent.
  Target:  flag_high + (leg_up_size × 0.6)  — conservative measured-move.

We restrict the universe to Stage-2 SEPA candidates because bull flags
in Stage 1 / 4 are statistically just oversold bounces; the structural
trend has to be intact for a flag to mean what it says.

Expires after 96h (4 trading days). Top 80 SEPA candidates scanned.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from . import store, universe

log = logging.getLogger("setups.bull_flag")


_MIN_LEG_RETURN_PCT     = 15.0   # rolling 5-day return floor for "leg up"
_LEG_LOOKBACK_SESSIONS  = 30     # how far back to search for the leg
_FLAG_MIN_LEN           = 5      # min consolidation length, sessions
_FLAG_MAX_LEN           = 15     # max consolidation length
_FLAG_MAX_DEPTH_PCT     = 15.0   # max pullback from the leg-up peak
_NEW_HIGH_TOLERANCE_PCT = 2.0    # flag must not exceed peak × 1.02
_MAX_START_AGO          = 25     # flag must start within last N sessions
_MAX_END_AGO            = 5      # flag must end within last N sessions


def _detect_bull_flag(symbol: str) -> Optional[dict]:
    """Detect a bull-flag continuation. Returns trigger/stop/target/meta or None."""
    try:
        from sepa import prices
        df = prices.load_prices(symbol, period="6mo")
    except Exception as exc:
        log.debug("bull_flag: price load failed for %s: %s", symbol, exc)
        return None
    if df is None or len(df) < 40:
        return None

    closes = df["close"].values
    highs  = df["high"].values
    lows   = df["low"].values
    vols   = df["volume"].values
    n = len(df)

    # 1) Find the strongest 5-day return in the LEG_LOOKBACK window. The
    # leg-up is the run ending at the peak day; we measure the 5-day
    # return ending at each session and pick the best.
    best_leg_pct = 0.0
    leg_end_idx = None
    leg_start_idx = None
    start_scan = max(5, n - _LEG_LOOKBACK_SESSIONS)
    for i in range(start_scan, n):
        prior = closes[i - 5]
        if prior <= 0:
            continue
        pct = (closes[i] - prior) / prior * 100
        if pct > best_leg_pct:
            best_leg_pct = pct
            leg_end_idx = i
            leg_start_idx = i - 5

    if leg_end_idx is None or best_leg_pct < _MIN_LEG_RETURN_PCT:
        return None

    # The "peak" we measure the flag against is the highest CLOSE in the
    # leg window (more stable than the absolute intraday high).
    peak_idx = leg_start_idx + int(closes[leg_start_idx:leg_end_idx + 1].argmax())
    peak_close = float(closes[peak_idx])

    # 2) Scan forward from peak for a consolidation that satisfies the
    # depth + new-high constraints. We're looking for the LONGEST valid
    # flag ending close to today.
    best_flag = None
    for flag_len in range(_FLAG_MIN_LEN, _FLAG_MAX_LEN + 1):
        flag_start = peak_idx + 1
        flag_end   = flag_start + flag_len - 1
        if flag_end >= n:
            break
        # Bound checks: must START within MAX_START_AGO and END within MAX_END_AGO.
        if (n - 1) - flag_start > _MAX_START_AGO:
            continue
        if (n - 1) - flag_end > _MAX_END_AGO:
            continue

        flag_closes = closes[flag_start:flag_end + 1]
        flag_highs  = highs[flag_start:flag_end + 1]
        flag_lows   = lows[flag_start:flag_end + 1]

        depth_pct = (peak_close - flag_closes.min()) / peak_close * 100
        if depth_pct > _FLAG_MAX_DEPTH_PCT:
            continue
        # Must not have already broken out above the peak.
        if flag_closes.max() > peak_close * (1 + _NEW_HIGH_TOLERANCE_PCT / 100):
            continue

        flag_high = float(flag_highs.max())
        flag_low  = float(flag_lows.min())
        # Pick the LATEST-ending valid flag (the most actionable one).
        best_flag = {
            "start_idx": flag_start,
            "end_idx":   flag_end,
            "flag_high": flag_high,
            "flag_low":  flag_low,
            "depth_pct": depth_pct,
            "length":    flag_len,
        }

    if best_flag is None:
        return None

    # 3) Volume drying-up check: avg volume during the flag must be
    # strictly less than avg volume during the leg up.
    leg_avg_vol = float(vols[leg_start_idx:leg_end_idx + 1].mean())
    flag_avg_vol = float(vols[best_flag["start_idx"]:best_flag["end_idx"] + 1].mean())
    if leg_avg_vol <= 0 or flag_avg_vol >= leg_avg_vol:
        return None

    leg_up_size = peak_close - float(closes[leg_start_idx])
    if leg_up_size <= 0:
        return None

    flag_high = best_flag["flag_high"]
    flag_low  = best_flag["flag_low"]
    trigger = round(flag_high + 0.01, 4)
    stop    = round(flag_low  - 0.01, 4)
    target  = round(flag_high + leg_up_size * 0.6, 4)

    risk = trigger - stop
    if risk <= 0:
        return None

    return {
        "trigger": trigger,
        "stop": stop,
        "target": target,
        "meta": {
            "leg_return_pct":     round(best_leg_pct, 2),
            "leg_start_idx_ago":  int(n - 1 - leg_start_idx),
            "leg_end_idx_ago":    int(n - 1 - leg_end_idx),
            "peak_close":         round(peak_close, 4),
            "flag_length":        best_flag["length"],
            "flag_depth_pct":     round(best_flag["depth_pct"], 2),
            "flag_high":          round(flag_high, 4),
            "flag_low":           round(flag_low, 4),
            "flag_avg_vol":       int(flag_avg_vol),
            "leg_avg_vol":        int(leg_avg_vol),
            "vol_dryup_ratio":    round(flag_avg_vol / leg_avg_vol, 2),
            "leg_up_size":        round(leg_up_size, 4),
        },
    }


def scan(top_n: int = 80) -> list[dict]:
    """Find bull-flag setups across the top SEPA candidates (Stage 2 only)."""
    if universe.is_bull_regime() is False:
        log.info("bull_flag: bear regime — skipping scan")
        return []

    cands = universe.get_sepa_candidates(top_n=top_n)
    if not cands:
        log.info("bull_flag: no SEPA candidates available")
        return []

    # Only Stage-2 names. Flags require an established uptrend; flags in
    # Stage 1/3/4 are usually just consolidation noise.
    # Note: in candidates rows `stage` is a dict {"stage": N}; in all_results
    # rows it's a bare int. Handle both shapes.
    def _stage_num(c):
        s = c.get("stage")
        if isinstance(s, dict):
            return s.get("stage")
        return s
    cands = [c for c in cands if _stage_num(c) == 2]
    if not cands:
        log.info("bull_flag: no Stage-2 candidates")
        return []

    setups: list[dict] = []

    def _process(c):
        sym = c.get("symbol")
        if not sym:
            return None
        result = _detect_bull_flag(sym)
        if result is None:
            return None
        meta = dict(result["meta"])
        meta["sepa_score"]  = c.get("score")
        meta["sepa_rating"] = c.get("rating")
        meta["rs_rank"]     = c.get("rs_rank")
        return store.make_setup(
            kind="bull_flag",
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

    inserted = store.upsert_setups("bull_flag", setups)
    log.info("bull_flag: scanned %d Stage-2 candidates, %d setups inserted",
             len(cands), inserted)

    if setups:
        try:
            from sepa.notify import send_alert
            top = sorted(setups, key=lambda s: s["rr"], reverse=True)[:3]
            body = " · ".join(
                f"{s['symbol']} buy ≥ {s['trigger']:.2f} "
                f"(leg {s['meta'].get('leg_return_pct')}%)"
                for s in top
            )
            send_alert(
                title=f"🚩 {len(setups)} Bull Flag setups",
                body=body,
                kind="setup_bull_flag",
                url="/setups?kind=bull_flag",
            )
        except Exception as exc:
            log.warning("bull_flag: push notify failed: %s", exc)

    return setups


if __name__ == "__main__":
    # Smoke test: `python -m setups.bull_flag`
    import json
    out = scan()
    print(json.dumps(
        [{"symbol": s["symbol"], "trigger": s["trigger"], "stop": s["stop"],
          "rr": s["rr"],
          "leg_pct": s["meta"].get("leg_return_pct"),
          "flag_len": s["meta"].get("flag_length")} for s in out],
        indent=2,
    ))
