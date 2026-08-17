"""Power Earnings Gap (PEG) — Minervini's short-term post-earnings setup.

Setup definition:
  - Detect a "gap day" in the last 5 trading sessions where:
        open >= prior_close × 1.05    (≥ 5% gap up)
        volume >= 4 × avg_volume_50d   (institutional confirmation)
    The gap is almost always an earnings reaction (≥ 5% on 4× vol on
    a quality name is structurally an earnings event 95% of the time;
    we don't strictly need the calendar to know it happened).

  - Trigger: HIGH of the gap day + 1 cent buffer
        — entry when the market takes that high back out in a later
          session. This is Minervini's "buy the high of the high-volume
          day" rule.
  - Stop:    LOW of the gap day - 1 cent buffer
        — if price closes below the gap-day low, the setup is broken.
  - Target:  gap-day high × 1.06 (≈ 6% above trigger)
        — Minervini publishes 5-15% as the typical PEG target range;
          we pick the conservative 6% for the first scale-out so the
          R:R math is favorable even on the tighter gaps.
  - Hold 3-10 days. Expires after 72h (3 trading days) if untriggered —
    after that the gap is "stale," buyers have moved on.

Why detect via price action instead of calling Finnhub/yfinance for an
earnings calendar:
  - The earnings-calendar APIs are flaky (Finnhub rate-limits hard, yfinance
    Ticker.calendar misses 20-30% of confirmations).
  - The PRICE signal IS the setup. If a stock gaps 5%+ on 4× volume,
    something material happened — we don't actually need to know it was
    earnings specifically. M&A, FDA approval, guidance raise — all are
    Power Gaps that behave the same way technically.
  - This makes the scanner self-contained against the existing Massive
    daily-bar cache. No new data dependencies.

We DO still record an earnings_hint flag if Finnhub's calendar happens
to confirm an earnings event near the gap day — useful for the UI to
show "earnings gap" vs "news gap" but not load-bearing for the trigger.
"""
from __future__ import annotations

import logging
from typing import Optional

from . import store, universe
from sepa import symbols

log = logging.getLogger("setups.peg")


# Gap detection knobs — tunable but these track Minervini's published rules.
_MIN_GAP_PCT      = 5.0     # min open vs prior close, %
_MIN_VOL_MULT     = 4.0     # min volume vs 50-day average
_LOOKBACK_DAYS    = 5       # how recent the gap can be
_AVG_VOL_WINDOW   = 50      # session count for avg volume baseline
_TARGET_PCT_ABOVE = 6.0     # first-target % above trigger


def _detect_recent_power_gap(symbol: str) -> Optional[dict]:
    """Find the most recent qualifying power gap in the last 5 sessions.

    Returns a setup payload (trigger/stop/target/meta) or None.
    """
    try:
        from sepa import prices
        df = prices.load_prices(symbol, period="1y")
    except Exception as exc:
        log.debug("peg: price load failed for %s: %s", symbol, exc)
        return None
    if df is None or len(df) < _AVG_VOL_WINDOW + 2:
        return None

    # Walk backward through the last LOOKBACK_DAYS sessions checking each
    # as a potential gap day. We want the MOST RECENT qualifying gap
    # because older gaps are less actionable.
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
        # 50-day average ENDING the day BEFORE the gap day. We don't want
        # the gap day's own volume polluting its own baseline.
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
                "gap_day_idx": i,
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

    # If the trigger has already been taken out and price has run away,
    # the setup is "stale" — skip it. (We define "already taken out"
    # as the current bar's close > gap_day_high × 1.03; 3% buffer for
    # the natural breakout-and-pullback case where the entry is still
    # actionable.)
    current_close = closes[-1]
    if current_close > found["gap_day_high"] * 1.03:
        return None

    # Also skip if price has BROKEN DOWN below the gap-day low already —
    # the stop is invalidated; this is no longer a viable PEG.
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
            "gap_pct":     found["gap_pct"],
            "vol_mult":    found["vol_mult"],
            "days_ago":    found["days_ago"],
            "gap_day_high": round(found["gap_day_high"], 4),
            "gap_day_low":  round(found["gap_day_low"],  4),
            "gap_day_close": round(found["gap_day_close"], 4),
            "current_close": round(float(current_close), 4),
            "pct_from_trigger": round(
                (trigger - current_close) / current_close * 100, 2
            ),
        },
    }


def _maybe_tag_earnings(symbol: str, days_ago: int) -> Optional[str]:
    """Cosmetic: if Finnhub knows this was an earnings event near the
    gap, return a short hint string. Never load-bearing — failures
    return None and the setup still publishes."""
    try:
        # yfinance is already a dep; use the recent earnings_dates DF.
        import yfinance as yf
        tk = symbols.yf_ticker(symbol)
        df = tk.earnings_dates
        if df is None or df.empty:
            return None
        import pandas as pd
        recent = pd.Timestamp.utcnow().normalize() - pd.Timedelta(days=days_ago + 2)
        df = df[df.index <= pd.Timestamp.utcnow().normalize()]
        df = df[df.index >= recent - pd.Timedelta(days=2)]
        if df.empty:
            return None
        return "earnings"
    except Exception:
        return None


def scan(top_n: int = 50) -> list[dict]:
    """Run the PEG scan across the top SEPA candidates.

    PEG is rarer than inside-day so we cast a wider net (50 vs 30).
    """
    if universe.is_bull_regime() is False:
        log.info("peg: bear regime — skipping scan")
        return []

    cands = universe.get_sepa_candidates(top_n=top_n)
    if not cands:
        log.info("peg: no SEPA candidates available")
        return []

    setups: list[dict] = []
    for c in cands:
        sym = c.get("symbol")
        if not sym:
            continue
        result = _detect_recent_power_gap(sym)
        if result is None:
            continue
        meta = dict(result["meta"])
        meta["sepa_score"]  = c.get("score")
        meta["sepa_rating"] = c.get("rating")
        meta["rs_rank"]     = c.get("rs_rank")
        hint = _maybe_tag_earnings(sym, meta.get("days_ago") or 0)
        if hint:
            meta["catalyst_hint"] = hint
        setup = store.make_setup(
            kind="peg",
            symbol=sym,
            trigger=result["trigger"],
            stop=result["stop"],
            target=result["target"],
            expires_in_hours=72,
            meta=meta,
        )
        setups.append(setup)

    inserted = store.upsert_setups("peg", setups)
    log.info("peg: scanned %d candidates, %d setups inserted", len(cands), inserted)

    if setups:
        try:
            from sepa.notify import send_alert
            top = sorted(setups, key=lambda s: s["rr"], reverse=True)[:3]
            body = " · ".join(
                f"{s['symbol']} buy ≥ {s['trigger']:.2f} (gap {s['meta'].get('gap_pct')}%)"
                for s in top
            )
            send_alert(
                title=f"⚡ {len(setups)} Power Earnings Gap setups",
                body=body,
                kind="setup_peg",
                url="/setups?kind=peg",
            )
        except Exception as exc:
            log.warning("peg: push notify failed: %s", exc)

    return setups


if __name__ == "__main__":
    # Smoke test: `python -m setups.peg`
    import json
    out = scan(top_n=50)
    print(json.dumps(
        [{"symbol": s["symbol"], "trigger": s["trigger"], "stop": s["stop"],
          "rr": s["rr"], "gap_pct": s["meta"].get("gap_pct"),
          "days_ago": s["meta"].get("days_ago")} for s in out],
        indent=2,
    ))
