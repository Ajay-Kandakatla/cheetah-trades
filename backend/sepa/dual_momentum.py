"""Dual Momentum — Gary Antonacci's two-gate ranking.

Antonacci's "Dual Momentum Investing" (2014) combines two ideas:

  1. Absolute momentum (the "trend filter")
       The asset's own 12-month total return must beat the risk-free rate
       (T-bills). If not, you're in a defensive regime — go to bonds/cash.
       We approximate the risk-free hurdle with SPY's 12-month return: when
       SPY 12m return is negative, the regime is "defensive" and the screen
       returns no risk-on picks.

  2. Relative momentum (the "winner filter")
       Among assets that pass absolute momentum, rank by 12-month return
       and own the top performers.

Why this complements SEPA:
  - SEPA = pattern-based entry signal (tight base + pivot)
  - Dual Momentum = systematic top-down ranking that ignores chart shape
  - Together: SEPA tells you WHEN to buy a leader, Dual Momentum tells you
    WHICH leaders the market is already rewarding.

Reuses existing scan data:
  - The latest persisted scan (`scanner.load_latest()`) supplies the universe,
    company names, RS rank, and stage info — no second universe.
  - Returns are computed from the same Mongo-cached daily bars (`prices.load_prices`)
    so we don't re-hit any provider.

Output rows:
  {
    symbol, name, return_12m, return_6m, return_3m, return_1m,
    abs_mom_pass (12m > 0), beats_spy (12m > SPY 12m),
    rs_rank, stage, score (composite for ranking)
  }

The page also returns regime info: SPY 12m return + a "risk_on" flag.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from . import prices, company_names
from . import scanner as sepa_scanner

log = logging.getLogger("sepa.dual_momentum")


def _return_pct(df, lookback_days: int) -> Optional[float]:
    """Return percentage change over the given lookback in trading days."""
    if df is None or len(df) < lookback_days + 1:
        return None
    start = float(df["close"].iloc[-lookback_days - 1])
    end = float(df["close"].iloc[-1])
    if start == 0:
        return None
    return round((end / start - 1.0) * 100.0, 2)


# Lookback bucket mapping — Antonacci uses 12m as the gate, but exposing
# 1/3/6/12 lets the UI show a momentum waterfall per name.
LOOKBACKS = {
    "return_1m": 21,    # ~1 month
    "return_3m": 63,    # ~3 months
    "return_6m": 126,   # ~6 months
    "return_12m": 252,  # ~12 months
}


def _benchmark_return(symbol: str = "SPY", lookback_days: int = 252) -> Optional[float]:
    df = prices.load_prices(symbol)
    return _return_pct(df, lookback_days)


def compute(top_n: int = 15, gate_lookback_days: int = 252,
            min_rs_rank: int = 0) -> dict:
    """Run dual momentum ranking against the latest scan universe.

    Pulls every symbol from the latest persisted scan (so universe + names + RS
    are reused for free), recomputes 1/3/6/12-month returns from cached prices,
    applies absolute momentum vs SPY, and returns ranked picks.

    Args:
        top_n: number of risk-on names to return.
        gate_lookback_days: trading days for the absolute momentum gate (default 252 = 12m).
        min_rs_rank: optional RS floor; 0 disables.

    Returns:
        {
          generated_at, generated_at_iso,
          regime: { spy_return_12m, risk_on, label },
          gate_lookback_days,
          rows: [...all symbols with returns + flags...],
          picks: [...top N risk-on picks...],
          universe_size,
        }
    """
    t0 = time.time()
    latest = sepa_scanner.load_latest() or {}
    universe_results = latest.get("all_results") or []
    if not universe_results:
        log.warning("dual_momentum: no scan data found — run /sepa/scan first")
        return {
            "generated_at": int(t0),
            "regime": {"spy_return_12m": None, "risk_on": False,
                       "label": "no scan data — run /sepa/scan first"},
            "gate_lookback_days": gate_lookback_days,
            "rows": [],
            "picks": [],
            "universe_size": 0,
            "error": "no_scan",
        }

    spy_12m = _benchmark_return("SPY", gate_lookback_days)
    risk_on = (spy_12m is not None and spy_12m > 0)

    rows: list[dict] = []
    for rec in universe_results:
        sym = rec["symbol"]
        df = prices.load_prices(sym)
        if df is None or len(df) < 30:
            continue
        returns = {key: _return_pct(df, days) for key, days in LOOKBACKS.items()}
        ret_gate = returns.get("return_12m") if gate_lookback_days == 252 else _return_pct(df, gate_lookback_days)

        abs_mom_pass = (ret_gate is not None and ret_gate > 0)
        beats_spy = (
            ret_gate is not None and spy_12m is not None and ret_gate > spy_12m
        )

        # Composite score for ranking (the page sorts by this when picks tie)
        # Weight: 50% 12m + 25% 6m + 15% 3m + 10% 1m → favors longer trends.
        weights = [
            (returns.get("return_12m"), 0.50),
            (returns.get("return_6m"),  0.25),
            (returns.get("return_3m"),  0.15),
            (returns.get("return_1m"),  0.10),
        ]
        score = None
        if all(r is not None for r, _ in weights):
            score = round(sum(r * w for r, w in weights), 2)

        rows.append({
            "symbol": sym,
            "name": rec.get("name") or company_names.name_for(sym),
            **returns,
            "return_gate": ret_gate,
            "abs_mom_pass": abs_mom_pass,
            "beats_spy": beats_spy,
            "rs_rank": rec.get("rs_rank"),
            "stage": (rec.get("stage") or {}).get("stage"),
            "score": score,
            "is_sepa_candidate": bool(rec.get("is_candidate")),
            "entry_setup": rec.get("entry_setup"),
        })

    # Sort universe table by gate return (descending) so the UI's "all symbols"
    # view is naturally ranked.
    rows.sort(key=lambda r: (r["return_gate"] is None, -(r["return_gate"] or 0)))

    # Build the top-N picks
    eligible = [r for r in rows if r["abs_mom_pass"] and (r["rs_rank"] or 0) >= min_rs_rank]
    eligible.sort(key=lambda r: -(r["score"] or r["return_gate"] or 0))
    picks = eligible[:top_n]
    for i, p in enumerate(picks, start=1):
        p["rank"] = i

    label = (
        "RISK-ON — SPY 12m return positive, take leaders"
        if risk_on else
        "DEFENSIVE — SPY 12m return ≤ 0, classic Antonacci says cash/bonds"
    )

    return {
        "generated_at": int(time.time()),
        "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_sec": round(time.time() - t0, 2),
        "regime": {
            "spy_return_12m": spy_12m,
            "risk_on": risk_on,
            "label": label,
        },
        "gate_lookback_days": gate_lookback_days,
        "rows": rows,
        "picks": picks,
        "universe_size": len(rows),
        "scan_generated_at": latest.get("generated_at"),
    }
