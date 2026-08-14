"""Raw tape → order-flow analytics (pure math + the Massive trades fetch).

Classification is the TICK RULE (uptick = buyer-aggressive, downtick =
seller-aggressive, zero-tick carries the last direction). The proper quote
rule needs the full NBBO stream — 5-10x the trade count, too heavy to pull
per page view — and academic checks put the tick rule at ~75-80% agreement
with it. Stated on the page and in the methodology doc; every consumer of
`side` inherits that error bar.

Configured house values (NOT a book method):
  BIG_PRINT_FLOOR_DOLLARS  100k — a "big print" is >= this AND in the top
                           0.1% of today's notionals (adaptive so $40 small
                           caps and NVDA both surface sensible tapes)
  BURST_WINDOW_SEC         10s rolling windows for trade-flash detection
  BURST_MIN_DOLLARS        250k traded inside the window
  BURST_ONE_SIDED          75% of window volume on one side
  BURST_MIN_TRADES         15 prints in the window (a real burst, not one block)
  VALUE_AREA_PCT           70% — standard volume-profile value area
"""
from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

log = logging.getLogger("orderflow.tape")

BASE_URL = "https://api.massive.com"

BIG_PRINT_FLOOR_DOLLARS = 100_000.0
BIG_PRINT_TOP_QUANTILE = 0.999
BIG_PRINTS_MAX = 20
BURST_WINDOW_SEC = 10
BURST_MIN_DOLLARS = 250_000.0
BURST_ONE_SIDED = 0.75
BURST_MIN_TRADES = 15
BURSTS_MAX = 10
VALUE_AREA_PCT = 0.70
PROFILE_BUCKETS = 40
MAX_TRADE_PAGES = 24            # 24 x 50k = 1.2M prints — flags `truncated` past that
FETCH_TIMEOUT_SEC = 10
LATE_WINDOW_MIN = 30            # "who's in control NOW" — the last 30 min of tape


def _et_zone():
    from zoneinfo import ZoneInfo
    return ZoneInfo("America/New_York")


# ── Fetch ─────────────────────────────────────────────────────────────────────
def fetch_trades(symbol: str, day) -> Optional[pd.DataFrame]:
    """All prints for one ET calendar day (04:00-20:00 ET), ascending.

    Returns DataFrame [ts_utc index, price, size] with attrs['truncated'] set
    when the page cap was hit, or None on no data / provider failure.
    """
    import requests
    from massive_keys import stocks_key

    key = stocks_key()
    if not key:
        log.error("MASSIVE_API_KEY_STOCKS missing — cannot fetch tape")
        return None

    et = _et_zone()
    start = datetime(day.year, day.month, day.day, 4, 0, tzinfo=et)
    end = datetime(day.year, day.month, day.day, 20, 0, tzinfo=et)
    gte_ns = int(start.timestamp() * 1_000_000_000)
    lt_ns = int(end.timestamp() * 1_000_000_000)

    url = f"{BASE_URL}/v3/trades/{symbol.upper()}"
    params = {"timestamp.gte": gte_ns, "timestamp.lt": lt_ns,
              "order": "asc", "sort": "timestamp", "limit": 50000, "apiKey": key}
    rows: list = []
    truncated = False
    page = 0
    next_url = url
    while next_url:
        try:
            r = requests.get(next_url, params=params, timeout=FETCH_TIMEOUT_SEC)
        except Exception as exc:
            try:
                from sepa.prices import _scrub_key
                log.warning("tape fetch failed for %s: %s", symbol, _scrub_key(exc))
            except Exception:
                log.warning("tape fetch failed for %s (page %d)", symbol, page)
            return None
        if r.status_code == 429:
            time.sleep(2)
            continue
        if r.status_code != 200:
            log.warning("tape %s -> HTTP %s: %s", symbol, r.status_code, r.text[:200])
            return None
        body = r.json() or {}
        rows.extend(body.get("results") or [])
        nxt = body.get("next_url")
        if nxt:
            page += 1
            if page >= MAX_TRADE_PAGES:
                truncated = True
                break
            next_url = nxt
            params = {"apiKey": key}      # next_url carries its own cursor params
        else:
            next_url = None

    if not rows:
        return None
    df = pd.DataFrame(rows)
    ts_col = "sip_timestamp" if "sip_timestamp" in df.columns else "participant_timestamp"
    df["ts_utc"] = pd.to_datetime(df[ts_col], unit="ns", utc=True)
    # `exchange` is kept (2026-08-13) so orderflow.darkpool can split lit vs
    # FINRA-TRF (off-exchange) volume. Purely additive — every existing
    # consumer selects the columns it needs.
    keep = ["ts_utc", "price", "size"] + (["exchange"] if "exchange" in df.columns else [])
    df = df[keep].dropna(subset=["ts_utc", "price", "size"]).sort_values("ts_utc").set_index("ts_utc")
    df = df[(df["price"] > 0) & (df["size"] > 0)]
    df.attrs["truncated"] = truncated
    return df if len(df) else None


# ── Pure math (unit-tested on synthetic tapes) ───────────────────────────────
def tick_rule_sides(prices) -> list:
    """+1 buyer-aggressive / -1 seller-aggressive / 0 unknown, zero-tick carry.

    First print (and any prefix of equal prices) has no reference tick -> 0.
    """
    sides = []
    last_dir = 0
    prev = None
    for p in prices:
        if prev is None or p == prev:
            sides.append(last_dir)
        elif p > prev:
            last_dir = 1
            sides.append(1)
        else:
            last_dir = -1
            sides.append(-1)
        prev = p
    return sides


def delta_summary(df: pd.DataFrame) -> dict:
    """Cumulative volume delta + per-minute series from a sided tape.

    Expects columns price, size, side (+1/-1/0). Unknown-side volume is
    excluded from delta but counted in totals.
    """
    signed = df["size"] * df["side"]
    buy_vol = int(df.loc[df["side"] > 0, "size"].sum())
    sell_vol = int(df.loc[df["side"] < 0, "size"].sum())
    total_vol = int(df["size"].sum())
    delta = buy_vol - sell_vol

    per_min = signed.resample("1min").sum()
    per_min = per_min[per_min.index >= df.index.min().floor("1min")]
    cum = per_min.cumsum()
    series = [[ts.isoformat(), int(v)] for ts, v in cum.items() if not math.isnan(v)]

    cutoff = df.index.max() - timedelta(minutes=LATE_WINDOW_MIN)
    late = df[df.index >= cutoff]
    late_delta = int((late["size"] * late["side"]).sum())

    classified = buy_vol + sell_vol
    return {
        "buy_volume": buy_vol,
        "sell_volume": sell_vol,
        "delta": int(delta),
        "delta_pct_of_volume": round(delta / total_vol * 100, 1) if total_vol else 0.0,
        "classified_pct": round(classified / total_vol * 100, 1) if total_vol else 0.0,
        "late_delta": late_delta,
        "late_window_min": LATE_WINDOW_MIN,
        "series": series,
        "n_trades": int(len(df)),
    }


def find_big_prints(df: pd.DataFrame) -> dict:
    """Top prints by notional — >= max($100k, today's 99.9th pct notional)."""
    notional = df["price"] * df["size"]
    if not len(notional):
        return {"threshold_dollars": BIG_PRINT_FLOOR_DOLLARS, "prints": [],
                "buy_dollars": 0.0, "sell_dollars": 0.0}
    threshold = max(BIG_PRINT_FLOOR_DOLLARS, float(notional.quantile(BIG_PRINT_TOP_QUANTILE)))
    big = df[notional >= threshold].copy()
    big["dollars"] = (big["price"] * big["size"]).round(0)
    buy_d = float(big.loc[big["side"] > 0, "dollars"].sum())
    sell_d = float(big.loc[big["side"] < 0, "dollars"].sum())
    big = big.sort_values("dollars", ascending=False).head(BIG_PRINTS_MAX)
    et = _et_zone()
    prints = [{
        "time_et": ts.tz_convert(et).strftime("%H:%M:%S"),
        "price": round(float(r["price"]), 2),
        "size": int(r["size"]),
        "dollars": float(r["dollars"]),
        "side": "buy" if r["side"] > 0 else ("sell" if r["side"] < 0 else "unknown"),
    } for ts, r in big.iterrows()]
    return {"threshold_dollars": round(threshold, 0), "prints": prints,
            "buy_dollars": buy_d, "sell_dollars": sell_d}


def find_bursts(df: pd.DataFrame) -> list:
    """Trade-flash bursts: 10s windows, >=$250k, >=75% one-sided, >=15 prints."""
    if df.empty:
        return []
    w = df.copy()
    w["dollars"] = w["price"] * w["size"]
    w["signed_vol"] = w["size"] * w["side"]
    g = w.resample(f"{BURST_WINDOW_SEC}s").agg(
        dollars=("dollars", "sum"), volume=("size", "sum"),
        signed=("signed_vol", "sum"), n=("size", "count"),
        px=("price", "last"))
    g = g[(g["dollars"] >= BURST_MIN_DOLLARS) & (g["n"] >= BURST_MIN_TRADES) & (g["volume"] > 0)]
    if g.empty:
        return []
    one_sided = (g["signed"].abs() / g["volume"])
    g = g[one_sided >= BURST_ONE_SIDED]
    g = g.sort_values("dollars", ascending=False).head(BURSTS_MAX)
    et = _et_zone()
    out = [{
        "time_et": ts.tz_convert(et).strftime("%H:%M:%S"),
        "side": "buy" if r["signed"] > 0 else "sell",
        "dollars": round(float(r["dollars"]), 0),
        "volume": int(r["volume"]),
        "n_trades": int(r["n"]),
        "price": round(float(r["px"]), 2),
    } for ts, r in g.iterrows()]
    return sorted(out, key=lambda b: b["time_et"])


def volume_profile(bars_1min: pd.DataFrame) -> Optional[dict]:
    """POC + 70% value area from 1-min bars (volume at traded price).

    The honest bookmap substitute: where volume ACTUALLY traded (can't be
    spoofed), not resting orders (which we have no Level-2 feed for).
    """
    if bars_1min is None or bars_1min.empty or "volume" not in bars_1min:
        return None
    px = bars_1min["vwap_bar"] if "vwap_bar" in bars_1min else bars_1min["close"]
    vol = bars_1min["volume"]
    lo, hi = float(px.min()), float(px.max())
    if not (hi > lo > 0):
        return None
    step = (hi - lo) / PROFILE_BUCKETS
    idx = ((px - lo) / step).clip(0, PROFILE_BUCKETS - 1).astype(int)
    buckets = vol.groupby(idx).sum()
    total = float(buckets.sum())
    if total <= 0:
        return None
    poc_i = int(buckets.idxmax())
    covered = float(buckets[poc_i])
    lo_i = hi_i = poc_i
    while covered / total < VALUE_AREA_PCT and (lo_i > buckets.index.min() or hi_i < buckets.index.max()):
        below = float(buckets.get(lo_i - 1, 0.0))
        above = float(buckets.get(hi_i + 1, 0.0))
        if above >= below and hi_i < buckets.index.max():
            hi_i += 1
            covered += above
        elif lo_i > buckets.index.min():
            lo_i -= 1
            covered += below
        else:
            hi_i += 1
            covered += above
    mid = lambda i: round(lo + (i + 0.5) * step, 2)  # noqa: E731
    return {"poc": mid(poc_i), "value_area_low": mid(lo_i), "value_area_high": mid(hi_i),
            "session_low": round(lo, 2), "session_high": round(hi, 2),
            "value_area_pct": int(VALUE_AREA_PCT * 100)}


def analyze_tape(trades: pd.DataFrame, quotes: Optional[pd.DataFrame] = None) -> dict:
    """Sided tape → the full order-flow read (delta + prints + bursts).

    `quotes` (NBBO, from orderflow.quotes.fetch_quotes) upgrades classification
    from the tick rule to the quote rule (Lee-Ready). Omitted or too sparse →
    the tick rule stands and `classification` says so. The tick-rule sides are
    always computed: they are the documented fallback for prints that land at
    the midpoint or outside the quote window, and they give us the agreement
    figure that quantifies the upgrade.
    """
    from . import darkpool, quotes as quotes_mod

    df = trades.copy()
    tick_sides = tick_rule_sides(df["price"].tolist())

    qr = quotes_mod.quote_rule_sides(df, quotes, fallback_sides=tick_sides)
    df["side"] = qr["sides"] if qr["method"] != "none" else tick_sides

    classification = {
        "method": qr["method"],                    # quote | mixed | tick | none
        "coverage_pct": qr["coverage_pct"],
        "trustworthy": qr["trustworthy"],
        "n_quote_classified": qr["n_quote_classified"],
        "n_at_mid": qr["n_at_mid"],
        "n_fallback": qr["n_fallback"],
        "tick_agreement_pct": quotes_mod.agreement(tick_sides, qr["sides"]),
    }

    venues = darkpool.split_venues(df)
    return {
        "delta": delta_summary(df),
        "big_prints": find_big_prints(df),
        "bursts": find_bursts(df),
        "classification": classification,
        "venues": {**venues, "read": darkpool.read(venues),
                   "blocks": darkpool.dark_blocks(df),
                   "disclaimer": darkpool.DISCLAIMER},
        "truncated": bool(trades.attrs.get("truncated", False)),
        "last_price": round(float(df["price"].iloc[-1]), 2),
    }
