"""Deterministic BUY / WAIT / AVOID checklist over the order-flow read.

Five core checks — every one a fixed rule, no discretion (the point of the
page: "more deterministic trading"):

  1. trend_daily    Daily uptrend — SEPA trend-template qualifier or Stage 2
                    from the latest scan; fallback: close > SMA50 AND close >
                    EMA21 AND EMA21 rising over 5 bars. THE GATE: fail -> the
                    verdict can never be BUY (don't fight the daily trend —
                    keeps this page consistent with the SEPA system).
  2. ema_intraday   5-min EMA9 > EMA21 AND last price >= EMA21 (intraday
                    trend up, not just a bounce).
  3. delta          Session cumulative delta > 0 AND the last-30-min delta
                    >= 0 (buyers in control, still in control).
  4. big_buyers     Big-print $ on the buy side >= 1.25x the sell side, with
                    at least one big buy print (institutions on the bid side).
  5. zone           supply_demand price-zone read: 'favorable' passes,
                    'neutral' neither, 'caution' (at/into overhead supply or
                    extended) blocks BUY.

Verdict table (documented verbatim in docs/sepa/orderflow_methodology.md):
  AVOID  if trend_daily fails, OR zone is caution AND delta fails.
  BUY    if trend_daily + ema_intraday + delta all pass AND (big_buyers or
         zone passes) AND zone is not caution.
  WAIT   otherwise.

GEX is CONTEXT ONLY (never counted): amplifying regime means a move has wind
behind it; pinning means expiration drag — shown next to the verdict.
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

log = logging.getLogger("orderflow.signals")

EMA_FAST = 9
EMA_SLOW = 21
DAILY_EMA_SPAN = 21
DAILY_SMA_SPAN = 50
DAILY_RISING_BARS = 5
BIG_BUYER_RATIO = 1.25


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


# ── Check 1: daily trend (the gate) ───────────────────────────────────────────
def daily_trend_read(symbol: str) -> dict:
    """SEPA-first daily uptrend read; falls back to a bare MA check."""
    sym = symbol.upper()
    try:
        from sepa import scanner as sepa_scanner
        latest = sepa_scanner.load_latest() or {}
        rec = next((c for c in (latest.get("all_results") or [])
                    if c.get("symbol") == sym), None)
        if rec:
            stage = rec.get("stage")
            if isinstance(stage, dict):
                stage = stage.get("stage")
            qualifier = bool(rec.get("is_candidate") or rec.get("qualifier"))
            stage2 = str(stage) == "2"
            ok = qualifier or stage2
            detail = (f"SEPA scan: {'trend-template qualifier' if qualifier else 'not a qualifier'}"
                      f", stage {stage if stage is not None else '?'}")
            return {"pass": ok, "detail": detail, "source": "sepa"}
    except Exception as exc:
        log.debug("daily_trend_read: SEPA lookup failed for %s: %s", sym, exc)

    try:
        from sepa import prices
        df = prices.load_prices(sym, period="1y")
        if df is not None and len(df) >= DAILY_SMA_SPAN + DAILY_RISING_BARS:
            close = df["close"].astype(float)
            sma50 = close.rolling(DAILY_SMA_SPAN).mean()
            ema21 = ema(close, DAILY_EMA_SPAN)
            last = float(close.iloc[-1])
            ok = (last > float(sma50.iloc[-1])
                  and last > float(ema21.iloc[-1])
                  and float(ema21.iloc[-1]) > float(ema21.iloc[-1 - DAILY_RISING_BARS]))
            return {"pass": ok,
                    "detail": f"MA check: close {'>' if ok else 'vs'} SMA50/EMA21, EMA21 "
                              f"{'rising' if ok else 'read'} over {DAILY_RISING_BARS} bars",
                    "source": "ma_fallback"}
    except Exception as exc:
        log.debug("daily_trend_read: MA fallback failed for %s: %s", sym, exc)
    return {"pass": False, "detail": "no daily data — treated as fail (safe default)",
            "source": "none"}


# ── Check 2: intraday EMAs ────────────────────────────────────────────────────
def intraday_ema_read(bars_1min: pd.DataFrame) -> dict:
    """EMA9 vs EMA21 on 5-min closes (RTH+premarket bars in, RTH preferred)."""
    if bars_1min is None or bars_1min.empty or "close" not in bars_1min:
        return {"pass": False, "detail": "no intraday bars", "ema9": None, "ema21": None}
    rth = bars_1min[bars_1min.get("session", "rth") == "rth"]
    src = rth if len(rth) >= EMA_SLOW * 5 else bars_1min
    closes5 = src["close"].resample("5min").last().dropna()
    if len(closes5) < EMA_SLOW:
        return {"pass": False, "detail": f"only {len(closes5)} 5-min bars — need {EMA_SLOW}",
                "ema9": None, "ema21": None}
    e9 = float(ema(closes5, EMA_FAST).iloc[-1])
    e21 = float(ema(closes5, EMA_SLOW).iloc[-1])
    last = float(closes5.iloc[-1])
    ok = e9 > e21 and last >= e21
    return {"pass": ok, "ema9": round(e9, 2), "ema21": round(e21, 2),
            "last": round(last, 2),
            "detail": f"5-min EMA9 {round(e9, 2)} {'>' if e9 > e21 else '<='} EMA21 {round(e21, 2)}"
                      f", price {'above' if last >= e21 else 'below'} EMA21"}


# ── Checks 3-4 from the tape read ────────────────────────────────────────────
def delta_check(delta: dict) -> dict:
    total = delta.get("delta", 0)
    late = delta.get("late_delta", 0)
    ok = total > 0 and late >= 0
    return {"pass": ok,
            "detail": f"session delta {total:+,} sh · last {delta.get('late_window_min', 30)}min {late:+,} sh"}


def big_buyers_check(big: dict) -> dict:
    buy_d = float(big.get("buy_dollars") or 0.0)
    sell_d = float(big.get("sell_dollars") or 0.0)
    ok = buy_d > 0 and buy_d >= BIG_BUYER_RATIO * sell_d
    ratio = (buy_d / sell_d) if sell_d > 0 else (float("inf") if buy_d > 0 else 0.0)
    ratio_s = "∞" if ratio == float("inf") else f"{ratio:.2f}"
    return {"pass": ok,
            "detail": f"big prints ${buy_d:,.0f} buy vs ${sell_d:,.0f} sell (ratio {ratio_s}, need ≥{BIG_BUYER_RATIO})"}


# ── Check 5: zones (reuse supply_demand) ─────────────────────────────────────
def zone_read(symbol: str, last_price: Optional[float]) -> dict:
    try:
        from supply_demand import price_zones
        z = price_zones.for_symbol(symbol, last_price=last_price)
        v = z.get("verdict") or {}
        entry_read = v.get("entry_read") or "neutral"
        return {"pass": entry_read == "favorable", "caution": entry_read == "caution",
                "state": v.get("state"), "detail": v.get("label") or "no zone read",
                "nearest_support": (z.get("nearest_support") or {}).get("hi"),
                "nearest_resistance": (z.get("nearest_resistance") or {}).get("lo"),
                # Which band RESOLUTION produced this read. The Tape tab uses
                # fine bands (intraday decisions); Back in Demand uses coarse
                # ones (multi-day holds), so the same stock can legitimately
                # show different band edges on the two surfaces. Saying which
                # is which stops that reading as a contradiction — Ajay spotted
                # it on DTE 2026-08-14.
                "resolution": z.get("resolution")}
    except Exception as exc:
        log.debug("zone_read failed for %s: %s", symbol, exc)
        return {"pass": False, "caution": False, "state": None,
                "detail": "zone read unavailable", "nearest_support": None,
                "nearest_resistance": None}


# ── Context: GEX (never counted in the verdict) ──────────────────────────────
def gex_context(symbol: str) -> Optional[dict]:
    try:
        from options import opex
        out = opex.compute_opex(symbol.upper())
        if not out or not out.get("gamma"):
            return None
        g = out["gamma"]
        mp = out.get("max_pain") or {}
        return {"regime": g.get("regime"), "net_gex_dollars": g.get("net_gex_dollars"),
                "reliability": out.get("gex_reliability"),
                "max_pain_strike": mp.get("max_pain_strike"),
                "expiration_date": out.get("expiration_date")}
    except Exception as exc:
        log.debug("gex_context failed for %s: %s", symbol, exc)
        return None


# ── The verdict (pure — unit-tested) ─────────────────────────────────────────
def composite_verdict(trend_daily: dict, ema_intraday: dict, delta: dict,
                      big_buyers: dict, zone: dict) -> dict:
    """The fixed table. See module docstring — no other rule may decide."""
    checks = [
        {"key": "trend_daily", "label": "Daily uptrend (SEPA gate)", **_pf(trend_daily)},
        {"key": "ema_intraday", "label": "Intraday EMAs aligned (9>21, price above)", **_pf(ema_intraday)},
        {"key": "delta", "label": "Buyers in control (cumulative delta)", **_pf(delta)},
        {"key": "big_buyers", "label": "Big prints lean buy-side", **_pf(big_buyers)},
        {"key": "zone", "label": "Price at demand / clear runway", **_pf(zone)},
    ]
    caution = bool(zone.get("caution"))
    if not trend_daily["pass"]:
        verdict, reason = "AVOID", "daily trend gate failed — never fight the daily trend"
    elif caution and not delta["pass"]:
        verdict, reason = "AVOID", "into overhead supply with sellers in control"
    elif (ema_intraday["pass"] and delta["pass"]
          and (big_buyers["pass"] or zone["pass"]) and not caution):
        verdict, reason = "BUY", "trend + intraday EMAs + delta aligned, with big buyers or a zone tailwind"
    else:
        verdict, reason = "WAIT", "daily trend OK but the tape hasn't confirmed — wait for alignment"
    n_pass = sum(1 for c in checks if c["pass"])
    return {"verdict": verdict, "reason": reason, "checks": checks,
            "checks_passed": n_pass, "checks_total": len(checks)}


def _pf(check: dict) -> dict:
    return {"pass": bool(check.get("pass")), "detail": check.get("detail") or ""}
