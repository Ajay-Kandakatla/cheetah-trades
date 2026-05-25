"""Episodic Pivot scanner — catalyst-agnostic Power Gap detector.

The Episodic Pivot (Pradeep Bonde / "Stockbee") is a broader cousin of the
Power Earnings Gap (PEG): same price/volume math (a stock gapping hard on
huge volume), but we don't try to confirm an earnings event. Any catalyst
counts — earnings, M&A, FDA, contract win, news leak — they all show up
the same way in the tape.

We scan a wider universe than PEG (top 200 SEPA candidates vs PEG's 50)
but use stricter thresholds (≥ 8% gap on ≥ 5× volume vs PEG's 5% / 4×)
because we lose the earnings-calendar quality filter. The SEPA score is
the quality filter.

  Trigger: gap_day_high + 1 cent
  Stop:    gap_day_low  - 1 cent
  Target:  trigger × 1.06   (~6% — same as PEG)

Meta records `catalyst_type` ∈ {"earnings", "news", "unknown"}:
  - "earnings" if Finnhub / yfinance earnings calendar confirms a recent
    earnings event within ±2 days of the gap.
  - "news" only if we have explicit news data; today we default to
    "unknown" when no earnings match (so the field is honest).

Expires after 72h (same shelf life as PEG).
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from . import store, universe

log = logging.getLogger("setups.episodic_pivot")


# Stricter thresholds than PEG to compensate for the missing earnings filter.
_MIN_GAP_PCT      = 8.0
_MIN_VOL_MULT     = 5.0
_LOOKBACK_DAYS    = 5
_AVG_VOL_WINDOW   = 50
_TARGET_PCT_ABOVE = 6.0


def _detect_episodic_pivot(symbol: str) -> Optional[dict]:
    """Find the most recent qualifying episodic pivot. Returns payload or None."""
    try:
        from sepa import prices
        df = prices.load_prices(symbol, period="1y")
    except Exception as exc:
        log.debug("episodic_pivot: price load failed for %s: %s", symbol, exc)
        return None
    if df is None or len(df) < _AVG_VOL_WINDOW + 2:
        return None

    df = df.tail(_LOOKBACK_DAYS + _AVG_VOL_WINDOW + 5).copy()
    closes = df["close"].values
    opens  = df["open"].values
    highs  = df["high"].values
    lows   = df["low"].values
    vols   = df["volume"].values
    n = len(df)
    if n < _AVG_VOL_WINDOW + 2:
        return None

    found = None
    for i in range(n - 1, n - 1 - _LOOKBACK_DAYS, -1):
        if i < _AVG_VOL_WINDOW + 1:
            break
        avg_vol = vols[i - _AVG_VOL_WINDOW : i].mean()
        if avg_vol <= 0:
            continue
        prior_close = closes[i - 1]
        if prior_close <= 0:
            continue
        gap_pct = (opens[i] - prior_close) / prior_close * 100
        vol_mult = vols[i] / avg_vol
        if gap_pct >= _MIN_GAP_PCT and vol_mult >= _MIN_VOL_MULT:
            found = {
                "gap_day_idx":   i,
                "gap_day_open":  float(opens[i]),
                "gap_day_high":  float(highs[i]),
                "gap_day_low":   float(lows[i]),
                "gap_day_close": float(closes[i]),
                "gap_pct":       round(float(gap_pct), 2),
                "vol_mult":      round(float(vol_mult), 2),
                "days_ago":      n - 1 - i,
            }
            break

    if not found:
        return None

    current_close = closes[-1]
    # Same sanity filters as PEG — skip if price already ran away or broke down.
    if current_close > found["gap_day_high"] * 1.03:
        return None
    if current_close < found["gap_day_low"]:
        return None

    trigger = round(found["gap_day_high"] + 0.01, 4)
    stop    = round(found["gap_day_low"]  - 0.01, 4)
    target  = round(trigger * (1 + _TARGET_PCT_ABOVE / 100), 4)

    risk = trigger - stop
    if risk <= 0:
        return None

    return {
        "trigger": trigger,
        "stop": stop,
        "target": target,
        "meta": {
            "gap_pct":      found["gap_pct"],
            "vol_mult":     found["vol_mult"],
            "days_ago":     found["days_ago"],
            "gap_day_high": round(found["gap_day_high"], 4),
            "gap_day_low":  round(found["gap_day_low"],  4),
            "gap_day_close": round(found["gap_day_close"], 4),
            "current_close": round(float(current_close), 4),
            "pct_from_trigger": round(
                (trigger - current_close) / current_close * 100, 2
            ),
        },
    }


def _classify_catalyst(symbol: str, days_ago: int) -> str:
    """Return "earnings", "news", or "unknown" for the catalyst type.

    We currently only have an earnings-calendar signal via yfinance, so
    everything else falls back to "unknown" rather than asserting "news".
    """
    try:
        import yfinance as yf
        import pandas as pd
        tk = yf.Ticker(symbol)
        df = tk.earnings_dates
        if df is None or df.empty:
            return "unknown"
        recent = pd.Timestamp.utcnow().normalize() - pd.Timedelta(days=days_ago + 2)
        df = df[df.index <= pd.Timestamp.utcnow().normalize()]
        df = df[df.index >= recent - pd.Timedelta(days=2)]
        if df.empty:
            return "unknown"
        return "earnings"
    except Exception:
        return "unknown"


def scan(top_n: int = 200) -> list[dict]:
    """Run the Episodic Pivot scan across the top SEPA candidates."""
    if universe.is_bull_regime() is False:
        log.info("episodic_pivot: bear regime — skipping scan")
        return []

    cands = universe.get_sepa_candidates(top_n=top_n)
    if not cands:
        log.info("episodic_pivot: no SEPA candidates available")
        return []

    setups: list[dict] = []

    def _process(c):
        sym = c.get("symbol")
        if not sym:
            return None
        result = _detect_episodic_pivot(sym)
        if result is None:
            return None
        meta = dict(result["meta"])
        meta["sepa_score"]  = c.get("score")
        meta["sepa_rating"] = c.get("rating")
        meta["rs_rank"]     = c.get("rs_rank")
        meta["catalyst_type"] = _classify_catalyst(sym, meta.get("days_ago") or 0)
        return store.make_setup(
            kind="episodic_pivot",
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

    inserted = store.upsert_setups("episodic_pivot", setups)
    log.info("episodic_pivot: scanned %d candidates, %d setups inserted",
             len(cands), inserted)

    if setups:
        try:
            from sepa.notify import send_alert
            top = sorted(setups, key=lambda s: s["rr"], reverse=True)[:3]
            body = " · ".join(
                f"{s['symbol']} buy ≥ {s['trigger']:.2f} "
                f"(gap {s['meta'].get('gap_pct')}%)"
                for s in top
            )
            send_alert(
                title=f"⚡ {len(setups)} Episodic Pivot setups",
                body=body,
                kind="setup_episodic_pivot",
                url="/setups?kind=episodic_pivot",
            )
        except Exception as exc:
            log.warning("episodic_pivot: push notify failed: %s", exc)

    return setups


if __name__ == "__main__":
    import json
    out = scan()
    print(json.dumps(
        [{"symbol": s["symbol"], "trigger": s["trigger"], "stop": s["stop"],
          "rr": s["rr"], "gap_pct": s["meta"].get("gap_pct"),
          "vol_mult": s["meta"].get("vol_mult"),
          "catalyst": s["meta"].get("catalyst_type")} for s in out],
        indent=2,
    ))
