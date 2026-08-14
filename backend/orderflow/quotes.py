"""NBBO quotes → quote-rule (Lee-Ready) trade classification.

Ajay 2026-08-13: "I wanna make sure I invest based on orders too that way its
more deterministic."

WHY THIS EXISTS
---------------
`tape.py` classifies every print with the TICK RULE (uptick = buyer-aggressive)
because "the proper quote rule needs the full NBBO stream — 5-10x the trade
count". We measured the subscription on 2026-08-13: `/v3/quotes` IS available
on the stocks key (and the options key), so the stream we said was out of reach
is in fact ours. The tick rule agrees with the quote rule only ~75-80% of the
time, and that error lands directly on cumulative delta — the number the Tape
tab's BUY/WAIT/AVOID verdict leans on.

THE RULE (Lee & Ready 1991, the standard microstructure classifier — an
academic method, NOT a trading-book method):

    price >= ask          -> +1  buyer-aggressive  (lifted the offer)
    price <= bid          -> -1  seller-aggressive (hit the bid)
    price >  midpoint     -> +1
    price <  midpoint     -> -1
    price == midpoint     ->  0  undecidable on quote alone; the caller may
                               fall back to the tick rule for these

We deliberately do NOT apply Lee-Ready's 5-second quote lag: that adjustment
corrects for 1990s reporting latency and is counterproductive on modern
nanosecond SIP timestamps.

HONESTY ABOUT COVERAGE
----------------------
The NBBO for a liquid name runs to millions of rows a day. We cap the pull and
report `coverage_pct` — the share of trades that landed inside a window we
actually hold quotes for. A partial pull degrades to the tick rule for the
uncovered prints and SAYS SO; it never silently reports a quote-rule delta
computed off half the tape.

NOT a book method and NOT advice.
Spec: docs/orderflow/quote_rule_methodology.md
"""
from __future__ import annotations

import logging
import math
import time
from datetime import datetime
from typing import Optional

import pandas as pd

log = logging.getLogger("orderflow.quotes")

BASE_URL = "https://api.massive.com"
FETCH_TIMEOUT_SEC = 15
QUOTE_PAGE_LIMIT = 50_000
MAX_QUOTE_PAGES = 40             # 40 x 50k = 2M quotes; past that we go partial

# Regular session only. Pre/post NBBO is wide, thin and frequently crossed,
# which classifies badly; those prints keep the tick rule.
SESSION_START = (9, 30)
SESSION_END = (16, 0)

# Below this coverage the quote-rule delta is not trustworthy as a headline
# number and the UI should keep presenting the tick-rule figure.
MIN_USEFUL_COVERAGE_PCT = 60.0

# Tolerance for "this print is exactly at the midpoint". Guards binary-float
# error in (bid+ask)/2; orders of magnitude below any real sub-penny increment.
MID_EPSILON = 1e-9


def _et_zone():
    from zoneinfo import ZoneInfo
    return ZoneInfo("America/New_York")


def fetch_quotes(symbol: str, day, max_pages: int = MAX_QUOTE_PAGES) -> Optional[pd.DataFrame]:
    """Regular-session NBBO for one ET day, ascending.

    Returns [ts_utc index, bid, ask] with attrs['truncated'], or None.
    """
    import requests
    from massive_keys import stocks_key

    key = stocks_key()
    if not key:
        log.error("MASSIVE_API_KEY_STOCKS missing — cannot fetch NBBO")
        return None

    et = _et_zone()
    start = datetime(day.year, day.month, day.day, *SESSION_START, tzinfo=et)
    end = datetime(day.year, day.month, day.day, *SESSION_END, tzinfo=et)

    url = f"{BASE_URL}/v3/quotes/{symbol.upper()}"
    params = {
        "timestamp.gte": int(start.timestamp() * 1_000_000_000),
        "timestamp.lt": int(end.timestamp() * 1_000_000_000),
        "order": "asc", "sort": "timestamp",
        "limit": QUOTE_PAGE_LIMIT, "apiKey": key,
    }
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
                log.warning("nbbo fetch failed for %s: %s", symbol, _scrub_key(exc))
            except Exception:
                log.warning("nbbo fetch failed for %s (page %d)", symbol, page)
            break                       # keep what we have; caller sees coverage
        if r.status_code == 429:
            time.sleep(2)
            continue
        if r.status_code != 200:
            log.warning("nbbo %s -> HTTP %s: %s", symbol, r.status_code, r.text[:160])
            break
        body = r.json() or {}
        rows.extend(body.get("results") or [])
        nxt = body.get("next_url")
        if nxt:
            page += 1
            if page >= max_pages:
                truncated = True
                break
            next_url = nxt
            params = {"apiKey": key}
        else:
            next_url = None

    if not rows:
        return None
    df = pd.DataFrame(rows)
    ts_col = "sip_timestamp" if "sip_timestamp" in df.columns else "participant_timestamp"
    if ts_col not in df.columns:
        return None
    df["ts_utc"] = pd.to_datetime(df[ts_col], unit="ns", utc=True)
    df = df.rename(columns={"bid_price": "bid", "ask_price": "ask"})
    if "bid" not in df.columns or "ask" not in df.columns:
        return None
    df = df[["ts_utc", "bid", "ask"]].dropna().sort_values("ts_utc").set_index("ts_utc")
    # Drop crossed/locked and zero quotes — they classify everything wrongly.
    df = df[(df["bid"] > 0) & (df["ask"] > 0) & (df["ask"] > df["bid"])]
    df.attrs["truncated"] = truncated
    return df if len(df) else None


# ── Pure math (unit-tested on synthetic tapes) ───────────────────────────────
def classify_against_quote(price: float, bid: float, ask: float) -> int:
    """Lee-Ready side for ONE print against its prevailing quote. PURE.

    +1 buyer-aggressive, -1 seller-aggressive, 0 undecidable (exactly at mid,
    or the quote is missing/degenerate)."""
    if not bid or not ask or not price:
        return 0
    if ask <= bid:                       # crossed/locked — no information
        return 0
    if price >= ask:
        return 1
    if price <= bid:
        return -1
    mid = (bid + ask) / 2.0
    # Float tolerance is NOT cosmetic here: (10.00 + 10.06)/2 == 10.030000000000001,
    # so a print exactly at the midpoint compared as BELOW mid and was classified
    # a sell. On a penny-spread tape that silently biases cumulative delta
    # bearish. MID_EPSILON is far below any real sub-penny increment (1e-4).
    if math.isclose(price, mid, rel_tol=0.0, abs_tol=MID_EPSILON):
        return 0
    return 1 if price > mid else -1


def quote_rule_sides(trades: pd.DataFrame, quotes: Optional[pd.DataFrame],
                     fallback_sides: Optional[list] = None) -> dict:
    """Classify a whole tape against the prevailing NBBO.

    Each trade is matched to the LAST quote at or before its timestamp
    (`merge_asof`, direction='backward'). Trades with no prior quote — the
    pre-market prefix, or anything past a truncated pull — fall back to
    `fallback_sides` (the tick rule) when supplied, else 0.

    Returns {sides, coverage_pct, n_quote_classified, n_fallback, n_at_mid,
             method, trustworthy}.
    """
    n = len(trades)
    fb = list(fallback_sides) if fallback_sides is not None else [0] * n
    if n == 0:
        return {"sides": [], "coverage_pct": 0.0, "n_quote_classified": 0,
                "n_fallback": 0, "n_at_mid": 0, "method": "none",
                "trustworthy": False}
    if quotes is None or quotes.empty:
        return {"sides": fb, "coverage_pct": 0.0, "n_quote_classified": 0,
                "n_fallback": n, "n_at_mid": 0, "method": "tick",
                "trustworthy": False}

    left = trades.reset_index()[["ts_utc", "price"]]
    right = quotes.reset_index()[["ts_utc", "bid", "ask"]]
    merged = pd.merge_asof(
        left.sort_values("ts_utc"), right.sort_values("ts_utc"),
        on="ts_utc", direction="backward",
    )

    sides, n_quote, n_mid, n_fb = [], 0, 0, 0
    for i, row in enumerate(merged.itertuples(index=False)):
        bid, ask = row.bid, row.ask
        if pd.isna(bid) or pd.isna(ask):
            sides.append(fb[i] if i < len(fb) else 0)
            n_fb += 1
            continue
        s = classify_against_quote(row.price, float(bid), float(ask))
        if s == 0:                        # exactly at mid → tick rule decides
            n_mid += 1
            sides.append(fb[i] if i < len(fb) else 0)
            n_fb += 1
        else:
            n_quote += 1
            sides.append(s)

    coverage = round(100.0 * n_quote / n, 1) if n else 0.0
    return {
        "sides": sides,
        "coverage_pct": coverage,
        "n_quote_classified": n_quote,
        "n_fallback": n_fb,
        "n_at_mid": n_mid,
        "method": "quote" if coverage >= MIN_USEFUL_COVERAGE_PCT else "mixed",
        "trustworthy": coverage >= MIN_USEFUL_COVERAGE_PCT,
    }


def agreement(tick_sides, quote_sides) -> Optional[float]:
    """% of prints where the tick rule and the quote rule agree. Diagnostic —
    this is the number that tells us how wrong the old delta was."""
    pairs = [(t, q) for t, q in zip(tick_sides, quote_sides) if q != 0 and t != 0]
    if not pairs:
        return None
    return round(100.0 * sum(1 for t, q in pairs if t == q) / len(pairs), 1)
