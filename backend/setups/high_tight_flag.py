"""High Tight Flag scanner — Minervini's most aggressive momentum setup.

The High Tight Flag (HTF) is rare. It needs:
  1. A run-up of ≥ 90% in 4-8 weeks (20-40 sessions). This is the
     "high" part — the stock has already gone parabolic.
  2. A subsequent 3-5 week (15-25 session) consolidation that pulls
     back between 15% and 25% from the run's peak. This is the
     "tight" part — most parabolic moves give back 40%+; the ones
     that DON'T are the rare keepers that go again.
  3. Volume must be drying up during the flag relative to the run.
  4. The flag must INCLUDE the most recent session — we want HTFs we
     can act on now, not historical ones.

Trigger: flag_high + 1 cent.
Stop:    flag_low  - 1 cent.   (Wide stops are intentional — HTFs go far.)
Target:  flag_high × 1.30.    (Targets 30% from breakout; these run hard.)

Expires after 96h. Most days return zero HTFs — that's expected. When one
appears, we fire a single-name notification (vs the consolidated alerts
the other scanners use) because it's high-conviction enough to warrant
a focused ping.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from . import store, universe

log = logging.getLogger("setups.high_tight_flag")


_MIN_RUN_RETURN_PCT  = 90.0
_RUN_MIN_LEN         = 20   # 4 weeks
_RUN_MAX_LEN         = 40   # 8 weeks
_FLAG_MIN_LEN        = 15   # 3 weeks
_FLAG_MAX_LEN        = 25   # 5 weeks
_FLAG_MIN_DEPTH_PCT  = 15.0
_FLAG_MAX_DEPTH_PCT  = 25.0
_LOOKBACK_SESSIONS   = 120  # roughly 6 months


def _detect_htf(symbol: str) -> Optional[dict]:
    """Return HTF setup dict or None."""
    try:
        from sepa import prices
        df = prices.load_prices(symbol, period="6mo")
    except Exception as exc:
        log.debug("high_tight_flag: price load failed for %s: %s", symbol, exc)
        return None
    if df is None or len(df) < (_RUN_MIN_LEN + _FLAG_MIN_LEN + 5):
        return None

    df = df.tail(_LOOKBACK_SESSIONS).copy().reset_index(drop=True)
    closes = df["close"].values
    highs  = df["high"].values
    lows   = df["low"].values
    vols   = df["volume"].values
    n = len(df)

    # We're searching for: a run of length R that ends at run_end_idx,
    # followed by a flag of length F that ends at exactly n-1 (today).
    best_match = None

    for flag_len in range(_FLAG_MIN_LEN, _FLAG_MAX_LEN + 1):
        flag_start = n - flag_len
        flag_end   = n - 1
        if flag_start < _RUN_MIN_LEN:
            continue

        flag_closes = closes[flag_start:flag_end + 1]
        flag_highs  = highs[flag_start:flag_end + 1]
        flag_lows   = lows[flag_start:flag_end + 1]

        # The "post-run peak" is the close at the start of the flag — i.e.
        # the last close before the consolidation began. (Using flag_start
        # rather than searching gives a clean boundary between run and flag.)
        peak_close = float(closes[flag_start - 1])
        if peak_close <= 0:
            continue

        depth_pct = (peak_close - float(flag_lows.min())) / peak_close * 100
        if not (_FLAG_MIN_DEPTH_PCT <= depth_pct <= _FLAG_MAX_DEPTH_PCT):
            continue
        # Flag must not have already broken out (made a new high above peak).
        if float(flag_highs.max()) > peak_close * 1.02:
            continue

        # Find a run ending exactly at flag_start - 1 of length ∈ [RUN_MIN_LEN, RUN_MAX_LEN]
        # whose total return ≥ MIN_RUN_RETURN_PCT.
        for run_len in range(_RUN_MIN_LEN, _RUN_MAX_LEN + 1):
            run_start = flag_start - 1 - run_len + 1
            if run_start < 0:
                continue
            run_start_close = float(closes[run_start])
            if run_start_close <= 0:
                continue
            run_pct = (peak_close - run_start_close) / run_start_close * 100
            if run_pct < _MIN_RUN_RETURN_PCT:
                continue

            # Volume drying-up check
            run_avg_vol  = float(vols[run_start:flag_start].mean())
            flag_avg_vol = float(vols[flag_start:flag_end + 1].mean())
            if run_avg_vol <= 0 or flag_avg_vol >= run_avg_vol:
                continue

            candidate = {
                "run_start":   run_start,
                "run_end":     flag_start - 1,
                "run_len":     run_len,
                "run_pct":     run_pct,
                "flag_start":  flag_start,
                "flag_end":    flag_end,
                "flag_len":    flag_len,
                "flag_high":   float(flag_highs.max()),
                "flag_low":    float(flag_lows.min()),
                "depth_pct":   depth_pct,
                "peak_close":  peak_close,
                "run_avg_vol": run_avg_vol,
                "flag_avg_vol": flag_avg_vol,
            }
            # Prefer the highest run% match (strongest move into the flag).
            if best_match is None or candidate["run_pct"] > best_match["run_pct"]:
                best_match = candidate

    if best_match is None:
        return None

    flag_high = best_match["flag_high"]
    flag_low  = best_match["flag_low"]
    trigger = round(flag_high + 0.01, 4)
    stop    = round(flag_low  - 0.01, 4)
    target  = round(flag_high * 1.30, 4)

    risk = trigger - stop
    if risk <= 0:
        return None

    return {
        "trigger": trigger,
        "stop": stop,
        "target": target,
        "meta": {
            "run_return_pct":  round(best_match["run_pct"], 2),
            "run_length":      best_match["run_len"],
            "flag_length":     best_match["flag_len"],
            "flag_depth_pct":  round(best_match["depth_pct"], 2),
            "flag_high":       round(flag_high, 4),
            "flag_low":        round(flag_low, 4),
            "peak_close":      round(best_match["peak_close"], 4),
            "run_avg_vol":     int(best_match["run_avg_vol"]),
            "flag_avg_vol":    int(best_match["flag_avg_vol"]),
            "vol_dryup_ratio": round(
                best_match["flag_avg_vol"] / best_match["run_avg_vol"], 2
            ),
        },
    }


def scan(top_n: int = 200) -> list[dict]:
    """Find High Tight Flag setups across the top SEPA candidates.

    HTFs are rare — most days this returns 0. Top 200 cast to maximize
    coverage; the SEPA quality filter keeps noise low.
    """
    if universe.is_bull_regime() is False:
        log.info("high_tight_flag: bear regime — skipping scan")
        return []

    cands = universe.get_sepa_candidates(top_n=top_n)
    if not cands:
        log.info("high_tight_flag: no SEPA candidates available")
        return []

    setups: list[dict] = []

    def _process(c):
        sym = c.get("symbol")
        if not sym:
            return None
        result = _detect_htf(sym)
        if result is None:
            return None
        meta = dict(result["meta"])
        meta["sepa_score"]  = c.get("score")
        meta["sepa_rating"] = c.get("rating")
        meta["rs_rank"]     = c.get("rs_rank")
        return store.make_setup(
            kind="high_tight_flag",
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

    inserted = store.upsert_setups("high_tight_flag", setups)
    log.info("high_tight_flag: scanned %d candidates, %d setups inserted",
             len(cands), inserted)

    if setups:
        # One push per HTF — these are rare, single-name highlights warranted.
        try:
            from sepa.notify import send_alert
            for s in setups[:3]:  # cap at 3 to avoid spam in the freak case
                sym = s["symbol"]
                send_alert(
                    title=f"🚀 HIGH-TIGHT FLAG detected on {sym}",
                    body=(
                        f"buy ≥ {s['trigger']:.2f} stop {s['stop']:.2f} "
                        f"target {s['target']:.2f} · run "
                        f"{s['meta'].get('run_return_pct')}% in "
                        f"{s['meta'].get('run_length')} sessions"
                    ),
                    kind="setup_high_tight_flag",
                    url=f"/setups?kind=high_tight_flag&symbol={sym}",
                )
        except Exception as exc:
            log.warning("high_tight_flag: push notify failed: %s", exc)

    return setups


if __name__ == "__main__":
    import json
    out = scan()
    print(json.dumps(
        [{"symbol": s["symbol"], "trigger": s["trigger"], "stop": s["stop"],
          "target": s["target"], "rr": s["rr"],
          "run_pct": s["meta"].get("run_return_pct"),
          "flag_depth_pct": s["meta"].get("flag_depth_pct")} for s in out],
        indent=2,
    ))
