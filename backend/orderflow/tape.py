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

Trade eligibility (2026-09-27, docs/sepa/orderflow_methodology.md §"Trade
eligibility"): every print is classified by its Massive sale conditions and
correction indicator (`print_kind`) BEFORE any side is assigned. Busted and
summary re-reports are dropped everywhere; average-price / contingent /
derivatively-priced / out-of-sequence prints stay in volume but never in
sides, delta, bursts or big-print $; auction crosses stay in volume and are
LISTED in big prints with no side. The sets below are derived from Massive's
own `update_rules.consolidated` flags — a test pins them to a checked-in copy
of the reference so they cannot drift silently.
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


# ── Trade eligibility (Massive sale conditions + correction indicator) ────────
# Ajay 2026-09-27, on the ORCL Tape tab: "Can you add date stamps please to the
# tape?" then "this is for oracle hoping this info is accurate". It was not:
# ORCL 2026-09-25's one closing cross (1,671,248 @ $137.10, $229.1M) was listed
# FIVE times as a "buy" — the cross itself (cond 8) plus four NYSE "Official
# Close" re-sends (cond 15) at 16:04, 16:10, 18:30 and 19:00 — so Big buy $
# read $1,563.8M where the regular prints hold $110.7M. Each re-send has its
# own id and sequence number; only the CONDITION identifies it.
#
# Ids are Massive's (`GET /v3/reference/conditions?asset_class=stocks`).
# Correction indicator (Massive glossary): 1 original later corrected,
# 7 original marked erroneous, 8 original cancelled, 10 cancel record,
# 11 error record. 0 / null = regular, 12 = the corrected record (kept).
CORRECTION_DROP = frozenset({1, 7, 8, 10, 11})
# consolidated.updates_volume == false: the print duplicates an execution that
# is already on the tape. Dropped everywhere, including volume.
SUMMARY_CONDITIONS = frozenset({
    15,     # Market Center Official Close
    16,     # Market Center Official Open
    38,     # Corrected Consolidated Close (per listing market)
})
# consolidated.updates_high_low or updates_open_close == false (minus 12 and
# 37, below): real volume, but not a current arms-length price. Kept in volume
# and venue share; never in sides, delta, bursts or big-print $.
NON_FLOW_CONDITIONS = frozenset({
    2,      # Average Price Trade
    5,      # Bunched Sold Trade
    7,      # Cash Sale
    10,     # Derivatively Priced
    13,     # Extended Hours (Sold Out Of Sequence)
    20,     # Next Day
    21,     # Price Variation Trade
    22,     # Prior Reference Price
    29,     # Seller
    32,     # Sold (Out Of Sequence)
    33,     # Sold (Out of Sequence) and Stopped Stock
    52,     # Contingent Trade
    53,     # Qualified Contingent Trade
})
# Flagged false for SESSION (Form T = after hours) and SIZE (odd lots never set
# the last sale) reasons, not a stale price. Kept as regular flow — the status
# quo; dropping them is Ajay's call, not a default.
KEPT_DESPITE_FLAGS = frozenset({
    12,     # Form T/Extended Hours
    37,     # Odd Lot Trade
})
# Auction crosses. Real volume, but nobody aggressed: side = None, never in
# delta / bursts / big-print $, LISTED in big prints as an auction row.
# Condition-based, not clock-based: ORCL's NYSE crosses printed at 09:30:14
# and 16:04:14, which a "09:30:00 / 16:00:00" filter misses.
AUCTION_OPEN_CONDITIONS = frozenset({17, 25})     # Market Center Opening Trade, Opening Prints
AUCTION_CLOSE_CONDITIONS = frozenset({8, 19})     # Closing Prints, Market Center Closing Trade
AUCTION_REOPEN_CONDITIONS = frozenset({18, 28})   # Market Center Reopening Trade, Re-Opening Prints

# Ledger tag for the rule a verdict was computed under (orderflow/history.py).
ELIGIBILITY_METHOD = "eligibility_2026_09_27"
LEGACY_METHOD = "all_prints"

PRINT_KINDS = ("busted", "summary", "non_flow", "auction_open", "auction_close",
               "auction_reopen", "regular")
AUCTION_KINDS = frozenset({"auction_open", "auction_close", "auction_reopen"})
VOLUME_KINDS = frozenset({"non_flow", "regular"}) | AUCTION_KINDS   # busted + summary out


def print_kind(conditions, correction=None) -> str:
    """Classify ONE print. First match wins. PURE.

    busted → summary → non_flow → auction_open/close/reopen → regular.
    Missing / malformed conditions read as regular (the pre-2026-09-27
    behaviour), never as an exclusion.
    """
    try:
        if correction is not None and correction == correction \
                and int(correction) in CORRECTION_DROP:
            return "busted"
    except (TypeError, ValueError):
        pass
    conds = set()
    if isinstance(conditions, (list, tuple, set, frozenset)):
        for c in conditions:
            try:
                conds.add(int(c))
            except (TypeError, ValueError):
                continue
    elif hasattr(conditions, "tolist"):                    # numpy array
        return print_kind(conditions.tolist(), correction)
    if conds & SUMMARY_CONDITIONS:
        return "summary"
    if conds & NON_FLOW_CONDITIONS:
        return "non_flow"
    if conds & AUCTION_OPEN_CONDITIONS:
        return "auction_open"
    if conds & AUCTION_CLOSE_CONDITIONS:
        return "auction_close"
    if conds & AUCTION_REOPEN_CONDITIONS:
        return "auction_reopen"
    return "regular"


def label_kinds(df: pd.DataFrame) -> pd.DataFrame:
    """Add a `kind` column from raw Massive `conditions` / `correction`
    columns. Either column may be absent; a frame with neither is all
    'regular'. PURE (returns the same frame, mutated)."""
    conds = df["conditions"] if "conditions" in df.columns else [None] * len(df)
    corr = df["correction"] if "correction" in df.columns else [None] * len(df)
    df["kind"] = [print_kind(c, k) for c, k in zip(conds, corr)]
    return df


def _et_zone():
    from zoneinfo import ZoneInfo
    return ZoneInfo("America/New_York")


# ── Fetch ─────────────────────────────────────────────────────────────────────
def fetch_trades(symbol: str, day) -> Optional[pd.DataFrame]:
    """All prints for one ET calendar day (04:00-20:00 ET), ascending.

    Returns DataFrame [ts_utc index, price, size, exchange, kind, exec_utc]
    with attrs['truncated'] set when the page cap was hit, or None on no data
    / provider failure. ALL rows are returned (busted and summary included) —
    `kind` says what each one is; `analyze_tape` decides what counts where,
    and every other consumer keeps its pre-2026-09-27 frame plus two columns.
    `exec_utc` is Massive's `participant_timestamp` (when the trade executed);
    the index stays the SIP time, which the window, NBBO merge and resample
    all key on.
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
    # `kind` (2026-09-27) from the sale conditions + correction indicator —
    # see print_kind. Every consumer before this read every row as a trade.
    label_kinds(df)
    if "participant_timestamp" in df.columns:
        df["exec_utc"] = pd.to_datetime(df["participant_timestamp"], unit="ns", utc=True)
    keep = (["ts_utc", "price", "size"] + (["exchange"] if "exchange" in df.columns else [])
            + ["kind"] + (["exec_utc"] if "exec_utc" in df.columns else []))
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
    excluded from delta but counted in totals. `analyze_tape` hands it the
    REGULAR prints only (2026-09-27) — auctions, re-reports and non-flow
    prints never reach it. An empty tape is all zeros, never a crash.
    """
    if df is None or df.empty:
        return {"buy_volume": 0, "sell_volume": 0, "delta": 0,
                "delta_pct_of_volume": 0.0, "classified_pct": 0.0,
                "late_delta": 0, "late_window_min": LATE_WINDOW_MIN,
                "series": [], "per_minute": [], "n_trades": 0}
    signed = df["size"] * df["side"]
    buy_vol = int(df.loc[df["side"] > 0, "size"].sum())
    sell_vol = int(df.loc[df["side"] < 0, "size"].sum())
    total_vol = int(df["size"].sum())
    delta = buy_vol - sell_vol

    per_min = signed.resample("1min").sum()
    per_min = per_min[per_min.index >= df.index.min().floor("1min")]
    cum = per_min.cumsum()
    series = [[ts.isoformat(), int(v)] for ts, v in cum.items() if not math.isnan(v)]
    # The PRE-cumsum series — net buys minus sells inside each minute. This is
    # the "big delta per candle" read (Ajay 2026-08-24: "which side is actually
    # winning the battle ... inside a specific candle"); it was computed here
    # all along and discarded on the way to the cumulative line.
    per_minute = [[ts.isoformat(), int(v)] for ts, v in per_min.items()
                  if not math.isnan(v)]

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
        "per_minute": per_minute,
        "n_trades": int(len(df)),
    }


def stamp_et(ts) -> dict:
    """{date_et, time_et} for one UTC timestamp, in New York time. PURE.

    Ajay 2026-09-27: "Can you add date stamps please to the tape?" — the page
    serves the last session's snapshot on later days (Friday's prints on a
    Sunday), so a bare 16:04:14 does not say WHICH 16:04:14.
    """
    t = ts.tz_convert(_et_zone())
    return {"date_et": t.strftime("%Y-%m-%d"), "time_et": t.strftime("%H:%M:%S")}


def _exec_stamp(r) -> dict:
    """exec_date_et / exec_time_et from Massive's participant_timestamp (when
    the trade EXECUTED), when the frame carries it. The row's own date_et /
    time_et stay the SIP time — the time the tape shows it."""
    ex = r.get("exec_utc") if hasattr(r, "get") else None
    if ex is None or pd.isna(ex):
        return {}
    s = stamp_et(pd.Timestamp(ex))
    return {"exec_date_et": s["date_et"], "exec_time_et": s["time_et"]}


def _side_word(v) -> str:
    return "buy" if v > 0 else ("sell" if v < 0 else "unknown")


def find_big_prints(df: pd.DataFrame, auctions: Optional[pd.DataFrame] = None) -> dict:
    """Top prints by notional — >= max($100k, today's 99.9th pct notional).

    `df` is the REGULAR, sided tape: the threshold and the buy/sell $ come
    from it alone. `auctions` (optional, 2026-09-27) are the session's cross
    prints: listed when they clear the same threshold, with `side: None` and
    `kind: auction_open|auction_close|auction_reopen`, and NEVER added to buy
    or sell $ — nobody aggressed in an auction.
    """
    notional = df["price"] * df["size"]
    has_auctions = auctions is not None and len(auctions) > 0
    if not len(notional) and not has_auctions:
        return {"threshold_dollars": BIG_PRINT_FLOOR_DOLLARS, "prints": [],
                "buy_dollars": 0.0, "sell_dollars": 0.0}
    threshold = (max(BIG_PRINT_FLOOR_DOLLARS, float(notional.quantile(BIG_PRINT_TOP_QUANTILE)))
                 if len(notional) else BIG_PRINT_FLOOR_DOLLARS)
    big = df[notional >= threshold].copy()
    big["dollars"] = (big["price"] * big["size"]).round(0)
    buy_d = float(big.loc[big["side"] > 0, "dollars"].sum())
    sell_d = float(big.loc[big["side"] < 0, "dollars"].sum())
    rows = []
    for ts, r in big.iterrows():
        rows.append({
            **stamp_et(ts),
            "price": round(float(r["price"]), 2),
            "size": int(r["size"]),
            "dollars": float(r["dollars"]),
            "side": _side_word(r["side"]),
            "kind": "regular",
            **_exec_stamp(r),
        })
    if has_auctions:
        a = auctions[(auctions["price"] * auctions["size"]) >= threshold]
        for ts, r in a.iterrows():
            rows.append({
                **stamp_et(ts),
                "price": round(float(r["price"]), 2),
                "size": int(r["size"]),
                "dollars": float(round(r["price"] * r["size"], 0)),
                "side": None,
                "kind": str(r.get("kind") or "auction_open"),
                **_exec_stamp(r),
            })
    rows.sort(key=lambda p: -p["dollars"])
    return {"threshold_dollars": round(threshold, 0), "prints": rows[:BIG_PRINTS_MAX],
            "buy_dollars": buy_d, "sell_dollars": sell_d}


def find_bursts(df: pd.DataFrame) -> list:
    """Trade-flash bursts: 10s windows, >=$250k, >=75% one-sided, >=15 prints.

    Fed REGULAR prints only (tape.analyze_tape and trade_flash both filter on
    print_kind first) — an auction cross or a re-report is not urgency.
    """
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
    out = [{
        **stamp_et(ts),
        "side": "buy" if r["signed"] > 0 else "sell",
        "dollars": round(float(r["dollars"]), 0),
        "volume": int(r["volume"]),
        "n_trades": int(r["n"]),
        "price": round(float(r["px"]), 2),
    } for ts, r in g.iterrows()]
    return sorted(out, key=lambda b: (b["date_et"], b["time_et"]))


def split_by_kind(trades: pd.DataFrame) -> dict:
    """{all, volume, flow, auctions} views of one tape. PURE.

    volume   = everything except busted + summary (real shares that traded)
    flow     = regular prints only (sides, delta, bursts, big-print $)
    auctions = the cross prints (listed, never sided)
    A frame with no `kind` column (old caches, synthetic tapes) is all flow —
    the pre-2026-09-27 behaviour.
    """
    df = trades.copy()
    if "kind" not in df.columns:
        df["kind"] = "regular"
    vol = df[df["kind"].isin(VOLUME_KINDS)]
    return {"all": df, "volume": vol,
            "flow": vol[vol["kind"] == "regular"].copy(),
            "auctions": vol[vol["kind"].isin(AUCTION_KINDS)]}


def excluded_summary(trades: pd.DataFrame) -> Optional[dict]:
    """What was held out of buy/sell, and why — the Tape tab's one-line note.
    None when the tape carries no `kind` (nothing was classified). PURE."""
    if trades is None or "kind" not in trades.columns:
        return None
    k = trades["kind"]
    dollars = trades["price"] * trades["size"]

    def part(mask, with_dollars=False):
        out = {"n": int(mask.sum()), "shares": int(trades.loc[mask, "size"].sum())}
        if with_dollars:
            out["dollars"] = float(round(dollars[mask].sum(), 0))
        return out

    auc = k.isin(AUCTION_KINDS)
    out = {
        "busted": part(k == "busted"),
        "summary": part(k == "summary"),
        "non_flow": part(k == "non_flow", True),
        "auctions": {**part(auc, True),
                     "open": int((k == "auction_open").sum()),
                     "close": int((k == "auction_close").sum()),
                     "reopen": int((k == "auction_reopen").sum())},
    }
    out["note"] = excluded_note(out)
    return out


def _money(d: float) -> str:
    a = abs(d)
    if a >= 1e9:
        return f"${a / 1e9:.1f}B"
    if a >= 1e6:
        return f"${a / 1e6:.1f}M"
    if a >= 1e3:
        return f"${a / 1e3:.0f}K"
    return f"${a:.0f}"


def excluded_note(ex: dict) -> str:
    """The served sentence. Counts come from `excluded_summary`; nothing here
    is estimated. PURE."""
    parts = []
    a = ex.get("auctions") or {}
    if a.get("n"):
        legs = [f"{a[k]} {k}" for k in ("open", "close", "reopen") if a.get(k)]
        parts.append(f"{' + '.join(legs)} auction cross{'es' if a['n'] > 1 else ''} "
                     f"({_money(a.get('dollars') or 0)}, listed without a side)")
    s = ex.get("summary") or {}
    if s.get("n"):
        parts.append(f"{s['n']:,} official open/close re-report{'s' if s['n'] != 1 else ''} "
                     f"of a cross already on the tape")
    nf = ex.get("non_flow") or {}
    if nf.get("n"):
        parts.append(f"{nf['n']:,} average-price / contingent / derivatively-priced / "
                     f"out-of-sequence print{'s' if nf['n'] != 1 else ''} "
                     f"({_money(nf.get('dollars') or 0)})")
    b = ex.get("busted") or {}
    if b.get("n"):
        parts.append(f"{b['n']:,} cancelled or busted print{'s' if b['n'] != 1 else ''}")
    if not parts:
        return "Every print this session was a regular trade — nothing held out of buy/sell."
    return "Not counted as buying or selling: " + ", ".join(parts) + "."


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

    Trade eligibility (2026-09-27): sides, delta, bursts, retail and big-print
    $ read the REGULAR prints only; venues and dark blocks read every print
    that is real volume (busted + summary out); auction crosses are listed in
    big prints with no side. See `print_kind`.
    """
    from . import darkpool, quotes as quotes_mod, retail as retail_mod

    views = split_by_kind(trades)
    df = views["flow"]
    vol_df = views["volume"]
    # Sides over the flow prints ONLY, so an excluded print can never set the
    # reference tick for the regular print after it.
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

    venues = darkpool.split_venues(vol_df)
    blocks = darkpool.dark_blocks(vol_df)
    # Retail flow: sub-penny off-exchange prints, signed on the quote midpoint.
    # Needs the SAME quotes the classifier uses, so it costs nothing extra.
    # Retail prints + their sign from the REGULAR prints; the percent divides
    # by the session's real volume (busted + summary out), the same base as
    # the venue split — not by the regular prints alone.
    retail_read = retail_mod.identify(df, quotes,
                                      total_volume=int(vol_df["size"].sum()))
    # The last REGULAR print is the last trade; a summary or prior-reference
    # print can carry a stale price. Falls back when there is no flow at all.
    last_src = df if len(df) else (vol_df if len(vol_df) else trades)
    return {
        "delta": delta_summary(df),
        "big_prints": find_big_prints(df, auctions=views["auctions"]),
        "bursts": find_bursts(df),
        "classification": classification,
        "venues": {**venues, "read": darkpool.read(venues),
                   "blocks": blocks,
                   "disclaimer": darkpool.DISCLAIMER},
        "retail": {**retail_read,
                   "divergence": retail_mod.divergence(retail_read, blocks)},
        "excluded": excluded_summary(trades),
        "truncated": bool(trades.attrs.get("truncated", False)),
        "last_price": round(float(last_src["price"].iloc[-1]), 2),
    }


# ---------------------------------------------------------------------------
# Most recent session with prints
# ---------------------------------------------------------------------------
# Found 2026-08-17 (a Monday, pre-open) while adding dark-pool sorts to Chart
# Maps: every consumer walked back exactly ONE CALENDAR DAY when today was
# empty. On a Monday morning that lands on Sunday, and on Saturday it lands on
# Friday-the-week-before only by luck — so all weekend and every pre-open
# Monday, the Back in Demand board's off-exchange and retail columns came back
# empty and its dark-pool sorts silently ranked a column of nulls.
#
# Measured that morning: USB returned 0 rows for Aug 17 (Mon, pre-open), Aug 16
# (Sun) and Aug 15 (Sat), and 53,075 rows for Aug 14 (Fri) — dark 16.3% of
# 9.9M shares. The data was always there; nobody was asking for the right day.
#
# Walking back by TRADING days rather than calendar days also skips holidays
# for free, because a holiday simply returns no prints and the walk continues.

# How far back to look. 5 covers a long weekend plus a holiday either side.
MAX_TAPE_LOOKBACK_DAYS = 5


def last_session_trades(symbol: str, max_back: int = MAX_TAPE_LOOKBACK_DAYS):
    """Trades for the most recent day that actually printed, and which day.

    Returns ``(DataFrame, date)`` or ``(None, None)``. Weekends are skipped
    without a request; anything else is asked for, so a holiday costs one empty
    call and the walk continues.
    """
    from datetime import date as _date, timedelta as _td

    today = _date.today()
    for back in range(0, max_back + 1):
        day = today - _td(days=back)
        if day.weekday() >= 5:                    # Sat/Sun never print
            continue
        try:
            df = fetch_trades(symbol, day)
        except Exception as exc:
            log.debug("last_session_trades: %s %s failed: %s", symbol, day, exc)
            continue
        if df is not None and not df.empty:
            return df, day
    return None, None
