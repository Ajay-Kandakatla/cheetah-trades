"""SPY implied-volatility term structure from the option chain we already
pay for (Massive `/v3/snapshot/options/SPY`) — 9d / 30d / 90d ATM IV for the
nav IV badge (Ajay 2026-09-06: "Yes please add it", after the CBOE ^VIX9D /
^VIX3M history went stale at the source on 2026-07-17).

Method (house, no book):
  * spot = SPY price from the chain's `underlying_asset.price` (fallback:
    sepa.prices.bulk_snapshot).
  * per target tenor T in TENORS_DAYS the chain is queried for expiries in
    [T - w, T + w] days and strikes within STRIKE_BAND_PCT of spot (a few
    hundred contracts, not the whole board).
  * per expiry, ATM IV = mean of the call and put `implied_volatility` at
    the strike nearest spot (one side when the other is missing).
  * the tenor IV is interpolated between the two expiries that bracket T
    linearly in TOTAL VARIANCE (sigma^2 x t, t in calendar years) — the
    standard way to read a curve between listed dates; a single side uses
    the nearest expiry.
  * ratios 9d/30d and 30d/90d, shape from 30d/90d (contango under 1,
    backwardation over 1, sepa.iv_read.term_shape's flat band).
Every failure returns None: the badge then falls back to the CBOE tenors
(marked stale) — nothing here is fabricated. Data is DELAYED on this plan
(15 min); the payload says so. Not advice.
"""
from __future__ import annotations

import logging
import math
import os
import time
from datetime import date, datetime, timedelta
from typing import Callable, Optional

log = logging.getLogger("sepa.iv_term")

TENORS_DAYS = (9, 30, 90)
WINDOW_DAYS = {9: 5, 30: 10, 90: 25}
STRIKE_BAND_PCT = 1.0
MIN_DTE = 2                       # skip same/next-day expiries (pin noise)
PAGE_LIMIT = 250
MAX_PAGES = 4
TIMEOUT_SEC = 12
SOURCE = "spy_chain"
SOURCE_LABEL = "SPY option chain (Massive, delayed)"


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) and v > 0 else None


# ── fetch ────────────────────────────────────────────────────────────────────

def _spot_from_snapshot() -> Optional[float]:
    try:
        from sepa.prices import bulk_snapshot
        snap = (bulk_snapshot(["SPY"]) or {}).get("SPY") or {}
        return _f(snap.get("last_trade_price")) or _f(snap.get("close")) or _f(snap.get("last"))
    except Exception as exc:                       # noqa: BLE001
        log.debug("iv_term: spot snapshot unavailable: %s", exc)
        return None


def fetch_window(exp_lo: str, exp_hi: str, strike_lo: float, strike_hi: float,
                 session=None) -> list:
    """Raw contracts for one expiry window / strike band (paginated)."""
    from massive_keys import options_key
    key = options_key()
    if not key:
        return []
    import requests
    sess = session or requests.Session()
    url = "https://api.massive.com/v3/snapshot/options/SPY"
    params = {"apiKey": key, "limit": PAGE_LIMIT,
              "expiration_date.gte": exp_lo, "expiration_date.lte": exp_hi,
              "strike_price.gte": round(strike_lo, 2), "strike_price.lte": round(strike_hi, 2)}
    out, pages = [], 0
    while url and pages < MAX_PAGES:
        r = sess.get(url, params=params if pages == 0 else {"apiKey": key}, timeout=TIMEOUT_SEC)
        if r.status_code != 200:
            log.warning("iv_term: Massive HTTP %s for %s..%s", r.status_code, exp_lo, exp_hi)
            return out
        body = r.json() or {}
        out.extend(c for c in (body.get("results") or []) if isinstance(c, dict))
        url = body.get("next_url")
        pages += 1
    return out


def fetch_chain(today: date, spot: Optional[float] = None) -> tuple:
    """(spot, contracts) across the three tenor windows. Spot comes from the
    stock snapshot, else from the first contract's underlying_asset.price
    (a first narrow probe finds it when the snapshot is silent)."""
    import requests
    sess = requests.Session()
    spot = spot or _spot_from_snapshot()
    if spot is None:
        probe = fetch_window((today + timedelta(days=MIN_DTE)).isoformat(),
                             (today + timedelta(days=14)).isoformat(), 1.0, 1e6, sess)[:1]
        for c in probe:
            spot = _f((c.get("underlying_asset") or {}).get("price"))
        if spot is None:
            return None, []
    lo, hi = spot * (1 - STRIKE_BAND_PCT / 100.0), spot * (1 + STRIKE_BAND_PCT / 100.0)
    contracts, seen = [], set()
    for t in TENORS_DAYS:
        w = WINDOW_DAYS[t]
        exp_lo = max(today + timedelta(days=t - w), today + timedelta(days=MIN_DTE))
        exp_hi = today + timedelta(days=t + w)
        for c in fetch_window(exp_lo.isoformat(), exp_hi.isoformat(), lo, hi, sess):
            tk = (c.get("details") or {}).get("ticker")
            if tk and tk not in seen:
                seen.add(tk)
                contracts.append(c)
    return spot, contracts


# ── pure maths ───────────────────────────────────────────────────────────────

def atm_iv_by_expiry(contracts: list, spot: float) -> dict:
    """{expiry_iso: {"iv": float, "strike": float}} — mean of the call and put
    IV at the strike nearest spot; one side when the other has no IV."""
    by_exp = {}
    for c in contracts or []:
        d = c.get("details") or {}
        exp = d.get("expiration_date")
        k = _f(d.get("strike_price"))
        iv = _f(c.get("implied_volatility"))
        if not exp or k is None or iv is None:
            continue
        side = d.get("contract_type")
        if side not in ("call", "put"):
            continue
        by_exp.setdefault(exp, {}).setdefault(k, {})[side] = iv
    out = {}
    for exp, strikes in by_exp.items():
        k = min(strikes, key=lambda s: abs(s - spot))
        legs = strikes[k]
        ivs = [v for v in (legs.get("call"), legs.get("put")) if v is not None]
        if ivs:
            out[exp] = {"iv": sum(ivs) / len(ivs), "strike": k, "legs": len(ivs)}
    return out


def _dte(exp: str, today: date) -> Optional[int]:
    try:
        return (date.fromisoformat(exp[:10]) - today).days
    except (TypeError, ValueError):
        return None


def tenor_iv(points: dict, target_days: int, today: date) -> Optional[dict]:
    """Interpolate the ATM IV at `target_days` from {expiry: {iv, strike}}
    linearly in total variance between the bracketing expiries; nearest
    expiry when only one side exists. None when nothing usable."""
    rows = []
    for exp, p in (points or {}).items():
        dte = _dte(exp, today)
        if dte is None or dte < MIN_DTE or p.get("iv") is None:
            continue
        rows.append((dte, float(p["iv"]), exp))
    if not rows:
        return None
    rows.sort()
    below = [r for r in rows if r[0] <= target_days]
    above = [r for r in rows if r[0] >= target_days]
    if below and above and below[-1][0] == above[0][0]:
        d, iv, exp = below[-1]
        return {"iv": iv, "dte": d, "expiries": [exp], "method": "exact"}
    if below and above:
        (d1, iv1, e1), (d2, iv2, e2) = below[-1], above[0]
        t1, t2, t = d1 / 365.0, d2 / 365.0, target_days / 365.0
        var1, var2 = iv1 * iv1 * t1, iv2 * iv2 * t2
        var = var1 + (var2 - var1) * (t - t1) / (t2 - t1)
        iv = math.sqrt(max(var, 0.0) / t) if t > 0 else iv1
        return {"iv": iv, "dte": target_days, "expiries": [e1, e2], "method": "variance_interp"}
    d, iv, exp = min(rows, key=lambda r: abs(r[0] - target_days))
    return {"iv": iv, "dte": d, "expiries": [exp], "method": "nearest"}


def curve(contracts: list, spot: float, today: date, fetched_at: Optional[float] = None) -> Optional[dict]:
    """The badge's term block from raw contracts. None without a 30d point."""
    from sepa.iv_read import term_shape
    points = atm_iv_by_expiry(contracts, spot)
    t9, t30, t90 = (tenor_iv(points, t, today) for t in TENORS_DAYS)
    if t30 is None:
        return None

    def pct(x):
        return round(x["iv"] * 100.0, 2) if x else None

    r9 = round(t9["iv"] / t30["iv"], 3) if t9 else None
    r90 = round(t30["iv"] / t90["iv"], 3) if t90 else None
    return {"source": SOURCE, "source_label": SOURCE_LABEL, "underlying": round(spot, 2),
            "iv9d": pct(t9), "iv30d": pct(t30), "iv90d": pct(t90),
            "ratio_9d_30d": r9, "ratio_30d_90d": r90,
            # Legacy keys the badge already reads: 30D/3M ~ 30d/90d.
            "ratio_30d_3m": r90, "vix9d": None, "vix3m": None,
            "shape": term_shape(r90 if r90 is not None else r9),
            "as_of": today.isoformat(), "stale": False,
            "fetched_at": fetched_at or time.time(),
            "points": [{"tenor_days": t, "iv": pct(x), "dte": x["dte"] if x else None,
                        "expiries": x["expiries"] if x else [], "method": x["method"] if x else None}
                       for t, x in zip(TENORS_DAYS, (t9, t30, t90))],
            "expiries_seen": sorted(points.keys())}


def spy_curve(today: Optional[date] = None,
              fetch: Optional[Callable[[date], tuple]] = None) -> Optional[dict]:
    """Live SPY curve or None (fenced). `fetch(today) -> (spot, contracts)`
    is injectable for tests."""
    today = today or datetime.now().date()
    try:
        spot, contracts = (fetch or fetch_chain)(today)
    except Exception as exc:                       # noqa: BLE001
        log.warning("iv_term: SPY chain unavailable: %s", exc)
        return None
    if spot is None or not contracts:
        return None
    try:
        return curve(contracts, spot, today)
    except Exception as exc:                       # noqa: BLE001
        log.warning("iv_term: curve failed: %s", exc)
        return None
