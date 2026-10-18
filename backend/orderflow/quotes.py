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
report `coverage_pct` — the share of prints WITH a prevailing quote we hold
(2026-10-18, DECISIONS14 D10: 100 × (n − n_uncovered) / n). A print with no
held quote — before the first quote, outside the spans the pull actually
holds, or (on a hand-built frame only) against a zero / locked / crossed quote
— degrades to the tick rule and SAYS SO; we never silently report a
quote-rule delta computed off half the tape. A print exactly at the midpoint
has a quote (it is covered); only its side comes from the tick rule.

Since 2026-10-18 (DECISIONS14 D1/D4/D5) the session is pulled as 11 parallel
ET windows with a per-window page cap, and `attrs["covered"]` names the spans
actually held; a print outside them keeps the tick rule (`covered_mask`).

NOT a book method and NOT advice.
Spec: docs/orderflow/quote_rule_methodology.md
"""
from __future__ import annotations

import logging
import math
from datetime import date as _date
from typing import Optional

import numpy as np
import pandas as pd

from .massive_pages import fetch_windowed, windows_for

log = logging.getLogger("orderflow.quotes")

BASE_URL = "https://api.massive.com"
FETCH_TIMEOUT_SEC = 15
QUOTE_PAGE_LIMIT = 50_000

# Regular session only. Pre/post NBBO is wide, thin and frequently crossed,
# which classifies badly; those prints keep the tick rule.
SESSION_START = (9, 30)
SESSION_END = (16, 0)

# 2026-10-18 (DECISIONS14 D1/D4): the session is pulled as parallel ET windows
# (orderflow/massive_pages.py) and the page cap is per WINDOW.
QUOTE_PAGES_PER_WINDOW = 8  # MINE (DECISIONS14 D12) — 400k NBBO rows per window; IREN-class days fit whole, a megacap's open window is capped and coverage_pct says so
N_SESSION_WINDOWS = len(windows_for(_date(2026, 10, 16), SESSION_START, SESSION_END))   # MINE (DECISIONS14 D2) — 11: the 12 edges inside 09:30–16:00 bound 11 windows
MAX_QUOTE_PAGES = QUOTE_PAGES_PER_WINDOW * N_SESSION_WINDOWS   # MINE (DECISIONS14 D12) — 88 = 8 x 11, derived; was 40 (prefix cap)
QUOTE_PAGE_COLUMNS = ("sip_timestamp", "participant_timestamp", "bid_price", "ask_price")   # D11 page compaction

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

    Returns [ts_utc index, bid, ask] with attrs['truncated'] and
    attrs['covered'], or None.

    2026-10-18 (DECISIONS14 D1/D4/D5/D7/D11/D12): the session is pulled as 11
    parallel ET windows, each page compacted to its four columns as it arrives
    (D11). `max_pages` is the TOTAL page budget (default MAX_QUOTE_PAGES 88), spread as
    max(1, ceil(max_pages / n_windows)) pages per window. `truncated` = any
    window hit its cap. A window that fails mid-way keeps what it got; the
    other windows stand. attrs['covered'] = [(start_utc, end_utc_exclusive)]
    per window actually held: ending at the window end when the window
    completed (rows or not — zero updates means the prior quote stayed
    prevailing), at last_quote + 1 ns when it stopped early, nothing when it
    did not complete and held no rows; starting at the window start for the
    first window or when the previous span reached its window end, otherwise
    at its own first quote (a completed window with no rows after a gap adds
    nothing). Zero / locked / crossed quotes are dropped PER PAGE (D13), so
    every span edge comes from a valid quote, and a print during a locked
    market is classified against the prior VALID quote (standard Lee-Ready
    practice, what the serial code always did). — quote_rule_sides / retail.identify classify only inside it.
    """
    from massive_keys import stocks_key

    key = stocks_key()
    if not key:
        log.error("MASSIVE_API_KEY_STOCKS missing — cannot fetch NBBO")
        return None

    windows = windows_for(day, SESSION_START, SESSION_END)
    if not windows:
        return None
    pages_per_window = max(1, math.ceil(max_pages / len(windows)))

    url = f"{BASE_URL}/v3/quotes/{symbol.upper()}"
    def compact(results):              # D11: each page → its four columns, the raw list dropped
        df = pd.DataFrame(results)
        df = df[[c for c in QUOTE_PAGE_COLUMNS if c in df.columns]]
        if "bid_price" in df.columns and "ask_price" in df.columns:
            # D13: zero / locked / crossed quotes go PER PAGE, so every span edge
            # (first_ts_ns / last_ts_ns) comes from a valid quote.
            df = df[(df["bid_price"] > 0) & (df["ask_price"] > 0) & (df["ask_price"] > df["bid_price"])]
        return df

    result = fetch_windowed(url, key, windows=windows, limit=QUOTE_PAGE_LIMIT,
                            timeout=FETCH_TIMEOUT_SEC, pages_per_window=pages_per_window,
                            compact=compact, max_429=None, label=f"nbbo {symbol}", log=log)
    if result.failed:
        log.warning("nbbo %s -> %d of %d windows failed: kept what they held",
                    symbol, result.failed, len(result.windows))
    if not result.frames:
        return None
    df = pd.concat(result.frames, ignore_index=True)
    ts_col = "sip_timestamp" if "sip_timestamp" in df.columns else "participant_timestamp"
    if ts_col not in df.columns:
        return None
    df["ts_utc"] = pd.to_datetime(df[ts_col], unit="ns", utc=True)
    df = df.rename(columns={"bid_price": "bid", "ask_price": "ask"})
    if "bid" not in df.columns or "ask" not in df.columns:
        return None
    df = df[["ts_utc", "bid", "ask"]].dropna().sort_values("ts_utc").set_index("ts_utc")
    # Drop crossed/locked and zero quotes — they classify everything wrongly.
    # Since 2026-10-18 (D13) `compact` drops them per page; this stays as a no-op guard.
    df = df[(df["bid"] > 0) & (df["ask"] > 0) & (df["ask"] > df["bid"])]
    df.attrs["truncated"] = result.truncated
    df.attrs["covered"] = [(pd.Timestamp(g, unit="ns", tz="UTC"), pd.Timestamp(e, unit="ns", tz="UTC"))
                           for g, e in result.covered]
    return df if len(df) else None


def _ns_values(ts) -> np.ndarray:
    idx = pd.DatetimeIndex(ts)
    return idx.as_unit("ns").asi8


def _ts_ns(t) -> int:
    return int(pd.Timestamp(t).as_unit("ns").value)


def covered_mask(ts, quotes: pd.DataFrame) -> np.ndarray:
    """True where a timestamp lies inside a span we actually hold quotes for. PURE.

    The spans are `quotes.attrs["covered"]` ([start, end) pairs, set by
    fetch_quotes on every frame it returns). When the attr is MISSING (or not
    a list) — a frame without provenance, e.g. hand-built — there is no
    restriction: all True, and merge_asof(backward) alone decides, as before
    2026-10-18. An EMPTY list means the pull held nothing: all False.
    Vectorised: one np.searchsorted over the sorted span starts.
    (2026-10-18, DECISIONS14 D5 as amended.)"""
    t = _ns_values(ts)
    if quotes is None:
        return np.zeros(len(t), dtype=bool)
    spans = quotes.attrs.get("covered")
    if not isinstance(spans, list):          # no provenance → legacy, unrestricted
        return np.ones(len(t), dtype=bool)
    pairs = sorted((_ts_ns(a), _ts_ns(b)) for a, b in spans)
    merged: list = []                       # loop over SPANS (≤ a dozen), never over prints
    for a, b in pairs:
        if b <= a:
            continue
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    if not merged or len(t) == 0:
        return np.zeros(len(t), dtype=bool)
    starts = np.array([a for a, _ in merged], dtype=np.int64)
    ends = np.array([b for _, b in merged], dtype=np.int64)
    i = np.searchsorted(starts, t, side="right") - 1
    ok = i >= 0
    out = np.zeros(len(t), dtype=bool)
    out[ok] = t[ok] < ends[i[ok]]
    return out


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
    (`merge_asof`, direction='backward'). A trade with no prevailing quote we
    hold gets `fallback_sides` (the tick rule) when supplied, else 0. "No
    prevailing quote we hold" means either (a) the backward merge found no
    quote — the pre-market prefix, before the first quote — or (b) the frame
    carries `attrs["covered"]` (fetch_quotes always sets it) and the trade lies
    outside every covered span, so the quote the merge found is stale
    (`covered_mask`; DECISIONS14 D5), or (c) the prevailing quote is
    degenerate — a zero side, locked or crossed (`not bid or not ask or
    ask <= bid`): that is not a quote we hold (critic MED on D10). (c) can
    only fire on a frame that did NOT come from fetch_quotes (hand-built /
    legacy): fetch_quotes drops degenerate quotes per page (D13), so on live
    data a print during a locked market is matched to the prior VALID quote. (b) closes two holes this module's
    coverage promise already claimed were closed: after-hours prints
    (16:00-20:00 ET) were classified against the 15:59:59 quote, and prints
    past a truncated / failed window against the last quote held. A frame
    WITHOUT the `covered` attr (not from fetch_quotes) keeps the legacy
    behaviour: only (a) and (c) apply.

    Coverage (2026-10-18, DECISIONS14 D10): `coverage_pct` is the share of
    prints WITH a prevailing quote we hold —
    100 × (n − n_uncovered) / n. A print exactly at the midpoint of a REAL
    two-sided quote (0 < bid < ask) HAS a quote: it counts as covered, and only
    its side comes from the tick rule.
    `method` is "quote" and `trustworthy` is True when coverage_pct ≥
    MIN_USEFUL_COVERAGE_PCT, else "mixed" / False.

    Returns {sides, coverage_pct, n_quote_classified, n_fallback, n_at_mid,
             n_uncovered, method, trustworthy}, all counts of prints:
      n_quote_classified  held quote, off the midpoint → ±1 from the quote
      n_at_mid            held real two-sided quote (0 < bid < ask), print
                          exactly at its midpoint → tick side
      n_uncovered         no prevailing quote we hold → tick side
      n_fallback          n_at_mid + n_uncovered (every tick-sided print)
    Sides are unchanged by D10; only the headline number and the label moved.
    """
    n = len(trades)
    fb = list(fallback_sides) if fallback_sides is not None else [0] * n
    if n == 0:
        return {"sides": [], "coverage_pct": 0.0, "n_quote_classified": 0,
                "n_fallback": 0, "n_at_mid": 0, "n_uncovered": 0, "method": "none",
                "trustworthy": False}
    if quotes is None or quotes.empty:
        return {"sides": fb, "coverage_pct": 0.0, "n_quote_classified": 0,
                "n_fallback": n, "n_at_mid": 0, "n_uncovered": n, "method": "tick",
                "trustworthy": False}

    left = trades.reset_index()[["ts_utc", "price"]]
    right = quotes.reset_index()[["ts_utc", "bid", "ask"]]
    merged = pd.merge_asof(
        left.sort_values("ts_utc"), right.sort_values("ts_utc"),
        on="ts_utc", direction="backward",
    )

    inside = covered_mask(merged["ts_utc"], quotes)

    sides, n_quote, n_mid, n_fb, n_unc = [], 0, 0, 0, 0
    for i, row in enumerate(merged.itertuples(index=False)):
        bid, ask = row.bid, row.ask
        if not inside[i]:                 # no quote held for this moment → tick rule (D5)
            sides.append(fb[i] if i < len(fb) else 0)
            n_fb += 1
            n_unc += 1
            continue
        if pd.isna(bid) or pd.isna(ask):  # no quote before this print → uncovered (D10)
            sides.append(fb[i] if i < len(fb) else 0)
            n_fb += 1
            n_unc += 1
            continue
        b_, a_ = float(bid), float(ask)
        if not b_ or not a_ or a_ <= b_:  # zero / locked / crossed: not a quote we hold (critic MED)
            sides.append(fb[i] if i < len(fb) else 0)
            n_fb += 1
            n_unc += 1
            continue
        s = classify_against_quote(row.price, b_, a_)
        if s == 0:                        # exactly at mid of a real quote → tick rule decides
            n_mid += 1
            sides.append(fb[i] if i < len(fb) else 0)
            n_fb += 1
        else:
            n_quote += 1
            sides.append(s)

    coverage = round(100.0 * (n - n_unc) / n, 1) if n else 0.0   # MINE (DECISIONS14 D10) — share of prints with a held quote
    return {
        "sides": sides,
        "coverage_pct": coverage,
        "n_quote_classified": n_quote,
        "n_fallback": n_fb,
        "n_at_mid": n_mid,
        "n_uncovered": n_unc,
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
