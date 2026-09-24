"""Support Levels — one ticker, on demand, at a chosen zoom.

Ajay 2026-08-19:

> *"Can you help me with a new feature where I can look at support levels on
> demand may be a new tab in the chart maps. Where I can toggle a drop down to
> check montly vs 3 months vs 6 months demand zones please. I should be able to
> a search of all the Ticker I do today and then drop down or something to
> check supports... I want look at recent support levels as well."*

HOW THIS DIFFERS FROM THE OTHER THREE TABS
------------------------------------------
Every other Chart Maps tab is a BOARD: a scan hands it a list, the module turns
each row into a tile. This one has no list. You type a ticker, it computes.
Same tile contract, one tile, plus a levels table underneath — because a
support read is a set of NUMBERS you place a stop against, and a chart alone
cannot be read to the cent.

THE ZOOM IS THE WHOLE POINT
---------------------------
`price_zones` has always answered at one fixed zoom: 252 bars. That is the
right lookback for "where is the structural floor", and the wrong one for
"where is support for a trade I am in this week" — a level tested four times in
the last three weeks does not survive a year-long clustering pass, it gets
merged into whatever larger band contains it.

So the dropdown drives `price_zones.compute(lookback_bars=…)` and nothing else
about the rule changes. Two knobs move, and only two:

    bars          how far back structure is read from — the question asked
    swing_window  how many bars either side define a swing

`swing_window` HAS to move with the frame. At the module default of 4, a swing
low must be the lowest of nine consecutive bars; over a 21-bar month that is
43% of the entire window, and the shortest option would return one band or
none. Scaling it keeps roughly the same swing DENSITY at every zoom, which is
what makes the four views comparable.

`merge_pct` and `half_width_pct` are deliberately LEFT ALONE. Widening bands at
short zooms was the obvious next move and it is wrong: then the four views
would differ for three reasons at once and no one could say why 1M disagreed
with 6M. One rule, four zooms, one explanation.

WHAT IT IS NOT
--------------
`price_zones` is explicitly a configured, pragmatic price-structure read — NOT
a book method (see that module's header). No Minervini page backs these
thresholds and none is cited. Decision support, not a buy signal.
"""
from __future__ import annotations

import logging
from typing import Optional

from supply_demand import patterns as pat_mod
from supply_demand import price_zones as pz
from supply_demand import timeframes as tf_mod

from . import board as board_mod

log = logging.getLogger("chart_maps.support")

# ── the dropdown ──────────────────────────────────────────────────────────────
# `bars` are TRADING days: 21/mo. `swing_window` scales to hold swing density
# roughly constant — see the module header for why it is not left at 4.
SUPPORT_WINDOWS: tuple[dict, ...] = (
    # Ajay 2026-09-18: "Also a weekly chart for the past week and 2 week inthe
    # charting time frames in all places". He chose SHORT WINDOWS, not weekly
    # candles: "Add '1 week' and '2 weeks' to the zoom list ... Same
    # daily/intraday candles you have now, just zoomed into the last 5 or 10
    # sessions." Bars are TRADING days on this list's own convention (21/mo =
    # 4.2 trading weeks), so a week is 5 sessions and two weeks is 10 — never
    # 7 or 14. PREPENDED: `overlay_for_symbol` and the deep fetch both read
    # max(bars) / SUPPORT_WINDOWS[-1], which must stay 5y / 1260.
    {"key": "1w", "label": "1 week",   "bars": 5,   "swing_window": 2},
    {"key": "2w", "label": "2 weeks",  "bars": 10,  "swing_window": 2},
    {"key": "1m", "label": "1 month",  "bars": 21,  "swing_window": 2},
    {"key": "3m", "label": "3 months", "bars": 63,  "swing_window": 3},
    {"key": "6m", "label": "6 months", "bars": 126, "swing_window": 4},
    {"key": "1y", "label": "1 year",   "bars": 252, "swing_window": 4},
    # Ajay 2026-09-06: "add 2 years to the time frame ... I do seem sometime
    # we have bounces off the 2 years as well; also add 3 years and then keep
    # 5 years." Same swing window as 5y: past a year only structural pivots
    # are levels. The zoom IS the demand-zone lookback (lookback_bars below).
    {"key": "2y", "label": "2 years",  "bars": 504, "swing_window": 5},
    {"key": "3y", "label": "3 years",  "bars": 756, "swing_window": 5},
    # Ajay 2026-08-25: "select support level ... by up to 5 years". Wider
    # swing window on purpose — at this zoom only structural pivots matter;
    # a 2-bar swing five years ago is noise, not a level.
    {"key": "5y", "label": "5 years",  "bars": 1260, "swing_window": 5},
)

# Ajay 2026-09-18: "Also a weekly chart for the past week and 2 week inthe
# charting time frames in all places" — the SHORT-WINDOW option he chose, not
# weekly candles (declined). These two zooms are CHART-ONLY. Two floors make a
# 5/10-bar frame unreadable, not merely thin: price_zones.compute refuses any
# custom frame under price_zones.MIN_BARS_ABS (a swing needs 2*w+3 bars), and
# mood() only drops the still-forming bar when len(df) > 5
# (supply_demand/mood.py:136) — so a 5-bar mood would repaint while signal()
# still stamps no_repaint=True. The candles are the last 5 / 10 sessions;
# EVERY READ (levels, mood, signal, SMC, patterns, trend) is the 1-month read
# — the same chart-at-one-scale / levels-from-another split the 5-minute live
# views already use — and the payload says which window the numbers came from.
# A shorter zoom is a VIEW. Nothing about it is measured.
CHART_ONLY_LEVELS_FROM: dict[str, str] = {"1w": "1m", "2w": "1m"}

# 1 year since 2026-09-06 (Ajay: "make support default to 1 year on all the
# tabs? I think its safer and more accurate"). Until then 3 months — the middle
# of the 2026-08-19 ask and the horizon a swing stop lives on; 1y was avoided
# because /zones already answered it. He would rather open on the structural
# floor and zoom IN than start on a week's shelf. One default on every surface
# (Chart Maps tab, ticker page) — the frontend mirrors it.
DEFAULT_WINDOW = "1y"

# 1Y is not in the request. It is here because `/supply-demand/price-zones` and
# the /zones page both read 252 bars, and a tab that could not reproduce their
# answer would look like it disagreed with them rather than zoomed differently.
REQUESTED_WINDOWS = ("1m", "3m", "6m")

# "Recently tested" — a level price has actually visited inside the last month.
# Ajay: "I want look at recent support levels as well". Untested-for-a-year
# structure and last-week's floor are both support and are not the same claim,
# so the flag is carried per level rather than folded into the ordering.
RECENT_BARS = 21

# A band is a TESTED level once price has turned at it more than once. Below
# that it is one swing low with `half_width_pct` of synthetic width painted
# around it — which is the weakest evidence the clustering pass can emit, and on
# a short zoom it is also the COMMONEST: a 21-bar frame rarely contains two
# turns at the same price, so single-touch bands win the nearest-first sort
# almost every time (measured 2026-08-19: NVDA's nearest support at every zoom
# was one touch, 0.03% below price).
#
# They are still shown — a recent swing low IS where the next bid sat, and
# hiding it would empty the short windows. They are LABELLED, because the whole
# point of the table is that a stop goes under it.
MIN_TOUCHES_TESTED = 2

# How many levels the table shows per side. `price_zones` already caps its own
# returned lists at MAX_ZONES_PER_SIDE (4) per ORIGIN — the 4 STRONGEST, not the
# nearest, which on a 6-month CRWD dropped the 216–219 and 227 swing highs the
# SMC ledger was sweeping (2026-09-02). We now ask for EVERY cluster
# (max_zones=None) and cap by distance ourselves, so the practical ceiling
# below price is 8 (4 demand + 4 broken supply). Stated in the payload as
# `levels_capped` so a short list never reads as "that is all there is".
MAX_LEVELS = 6

DISCLAIMER = pz.DISCLAIMER


# The overlay pseudo-window (Ajay 2026-08-25: "where can I see the overlapping
# Demand zones?" after the CR study). Not a zoom — ALL zooms at once, clustered.
TF_DEFAULT = tf_mod.DEFAULT_TF

OVERLAY_KEY = "all"

# Bands whose midpoints sit within this % of each other are the same level seen
# through different windows. The same 2% the CR overlay study used; tighter
# than price_zones.ZONE_MERGE_PCT-at-4% territory would double-merge, looser
# would split genuine agreement.
CLUSTER_PCT = 2.0


# ── deep history (the 5y window) ─────────────────────────────────────────────
# prices.load_prices returns the CACHED ~2y frame regardless of the period
# argument on a cache hit, so the 5y zoom fetches its own frame straight from
# the provider and keeps it in a small module cache. Never written back into
# the shared price cache: everything downstream of it is sized for ~2y frames.
_DEEP_TTL_SEC = 6 * 3600
_deep_cache: dict = {}


def _shared_frame_as_of(sym: str) -> Optional[float]:
    """Epoch when the shared price cache last pulled `sym` from the provider,
    or None. Primary source is the Mongo price_cache doc's `cached_at` —
    the intraday patcher bumps it every time it refreshes the tail, so it
    tracks the layer load_prices actually serves. The parquet file's mtime
    is the fallback layer only: it understates freshness by days when Mongo
    is doing the work (measured on INTU 2026-08-26: parquet 2.2d old under
    a minutes-fresh Mongo tail). None means "don't stamp" — a fabricated
    stamp is the exact lie this exists to prevent."""
    import os
    from sepa import prices
    try:
        coll = prices._get_mongo()
        if coll is not None:
            doc = coll.find_one({"symbol": sym.upper()},
                                {"cached_at": 1, "_id": 0})
            ts = (doc or {}).get("cached_at")
            if ts:
                return float(ts)
    except Exception:                                          # pragma: no cover
        pass
    try:
        path = str(prices._cache_path(sym))
        return os.path.getmtime(path) if os.path.exists(path) else None
    except Exception:                                          # pragma: no cover
        return None


def _overlay_today(prices_mod, df, sym: str, snap: Optional[dict] = None):
    """(frame, as_of_epoch or None, live) via prices.with_today_bar —
    tolerant of stubs without it and of any failure; the closed frame always
    stands. `live` says whether the last row carries today's live print:
    appended (the day bar / a pre-market print) or, since 2026-09-08,
    ADJUSTED — an after-hours print carried into the last bar the frame
    already holds. Either way the caller keeps the frame it passed in as the
    closed one.

    `snap` (2026-09-21) is a raw `bulk_snapshot` row the caller already
    fetched: `None` means "fetch it yourself" (the legacy per-call shape, and
    what the 2-arg `with_today_bar` stubs expect), `{}` means "fetched, and
    this symbol was absent" — no fetch, no overlay."""
    fn = getattr(prices_mod, "with_today_bar", None)
    if fn is None or df is None:
        return df, None, False, False
    try:
        out, info = fn(df, sym) if snap is None else fn(df, sym, snap=snap)
    except Exception as exc:                                   # pragma: no cover
        log.debug("support: today-bar overlay failed for %s: %s", sym, exc)
        return df, None, False, False
    info = info or {}
    live = bool(info.get("appended") or info.get("adjusted"))
    # `partial` (2026-09-14): the returned frame's LAST ROW is a session in
    # progress. Until today `appended` alone decided what was closed, and
    # from ~10:00 ET the hourly cache patch had already put today's partial
    # bar in the frame, so nothing was appended and the partial bar was read
    # as closed structure — with the verdict priced off a print up to an
    # hour stale while the `now` line moved to the live tape.
    return out, (info.get("as_of_epoch") if live else None), live, bool(info.get("partial"))


def _closed_of(df, partial: bool):
    """The structure frame: everything but an in-progress last row."""
    if df is None or not partial or len(df) < 2:
        return df
    return df.iloc[:-1]


def _frame_for(sym: str, need_bars: int, *, with_closed: bool = False,
               snap: Optional[dict] = None):
    """(df, bars_available, as_of_epoch[, closed]) — the shared 2y frame, or a
    deep 5y fetch when the window needs more than the shared frame holds.
    Degrades to the shared frame on a failed deep fetch — the caller reports
    the shortfall rather than silently drawing a 2-year chart under a 5-year
    label. `as_of_epoch` is when the data left the PROVIDER (shared frame:
    parquet mtime; deep frame: its fetch time), or None — never now().

    `with_closed=True` (integrator 2026-09-05) also returns the frame WITHOUT
    today's live bar (== df when nothing was appended): structure — swings,
    gaps, ATR — is read off closed bars only and the live bar prices the read,
    the rule price_zones.for_symbol adopted the same day.

    `snap` (2026-09-21): a prefetched `bulk_snapshot` row handed to BOTH
    overlays (shared frame and deep frame) so a deep-window tile costs zero
    HTTPS calls instead of three. Same `None` / `{}` rule as `_overlay_today`."""
    import time as _t
    from sepa import prices

    def _ret(frame, have, as_of, closed_frame):
        return (frame, have, as_of, closed_frame) if with_closed else (frame, have, as_of)

    try:
        closed = prices.load_prices(sym, period="2y")
    except Exception:                                          # pragma: no cover
        closed = None
    # Today's live bar on top of the closed frame (Ajay 2026-09-03, CHPT: the
    # tab said "1.4% below support" off yesterday's 5.19 while the tape was
    # 9.14). as_of becomes the snapshot's last-trade time when it appended.
    # NEVER add `snap=` to a call nobody prefetched for: `_overlay_today` is
    # itself stubbed 3-positional in places (test_zone_consistency:155).
    df, live_as_of, _live, partial = (
        _overlay_today(prices, closed, sym) if snap is None
        else _overlay_today(prices, closed, sym, snap=snap))
    closed = _closed_of(df, partial)
    have = len(df) if df is not None else 0
    if need_bars <= have:
        return _ret(df, have, (live_as_of or _shared_frame_as_of(sym)), closed)

    key = sym.upper()
    deep_as_of = None
    hit = _deep_cache.get(key)
    if hit and (_t.time() - hit[0]) < _DEEP_TTL_SEC:
        deep_as_of, deep = hit
    else:
        try:
            deep = prices._fetch_massive(key, "5y")
        except Exception:
            deep = None
        # The deep frame bypasses load_prices, so the pre-session phantom echo
        # scrub that every other frame gets never ran on it (2026-09-14).
        scrub = getattr(prices, "_drop_phantom_tail", None)
        if deep is not None and len(deep) and scrub is not None:
            try:
                healed = scrub(deep)
                deep = healed if healed is not None else deep
            except Exception as exc:                            # pragma: no cover
                log.debug("support: phantom scrub on deep %s failed: %s", sym, exc)
        if deep is not None and len(deep):
            deep_as_of = _t.time()
            _deep_cache[key] = (deep_as_of, deep)
    if deep is not None and len(deep) > have:
        deep, deep_live_as_of, _dl, deep_partial = (
            _overlay_today(prices, deep, sym) if snap is None
            else _overlay_today(prices, deep, sym, snap=snap))
        deep_closed = _closed_of(deep, deep_partial)
        return _ret(deep, len(deep), (deep_live_as_of or deep_as_of), deep_closed)
    return _ret(df, have, _shared_frame_as_of(sym), closed)


def window_keys() -> list[str]:
    return [w["key"] for w in SUPPORT_WINDOWS] + [OVERLAY_KEY]


def parse_window(raw) -> str:
    """Coerce a `?window=` value. Unknown → the default, never an error: a
    mistyped deep link should still answer with a chart."""
    v = (raw if isinstance(raw, str) else "").strip().lower()
    return v if v in window_keys() else DEFAULT_WINDOW


def window_spec(key: str) -> dict:
    k = parse_window(key)
    for w in SUPPORT_WINDOWS:
        if w["key"] == k:
            return w
    # Unreachable (parse_window already coerced); keeps mypy calm. By KEY, not
    # by index — index 1 is "2w" since 2026-09-18, and the fallback must be the
    # default window, never whatever happens to sit second in the tuple.
    return next(w for w in SUPPORT_WINDOWS if w["key"] == DEFAULT_WINDOW)


def _last_bar_date(df, intraday: bool = False) -> Optional[str]:
    """ISO date of the frame's newest bar, or None. The other half of the
    stamp: a fetch five minutes ago over week-old bars is still stale."""
    try:
        # INTRADAY only: ET, not UTC — the right-labelled 19:55-20:00 ET
        # after-hours bar is stamped 00:00 UTC the NEXT day, so the live
        # frame read "bars through <tomorrow>" every evening (review
        # 2026-09-02). Daily bars are DATES at midnight; converting those
        # would move every one of them back a day.
        ts = _et(df.index[-1]) if intraday else df.index[-1]
        return ts.date().isoformat()
    except Exception:                                          # pragma: no cover
        return None


def _pct_below(last_price: float, level_hi: float) -> Optional[float]:
    """How far BELOW the current price a level's top edge sits, in %.

    Measured to the band's TOP edge, which is the first price that touches it on
    the way down — the same edge `price_zones._verdict` measures `support_pct`
    to. Measuring to the midpoint would flatter every level by half its width.
    """
    if not last_price or last_price <= 0:
        return None
    return round((last_price - level_hi) / last_price * 100.0, 2)


def _pct_above(last_price: float, level_lo: float) -> Optional[float]:
    if not last_price or last_price <= 0:
        return None
    return round((level_lo - last_price) / last_price * 100.0, 2)


def _level(z: dict, last_price: float, *, above: bool) -> dict:
    """One row of the levels table, from a `price_zones` band."""
    bars_since = z.get("bars_since_test")
    return {
        "lo": z.get("lo"),
        "hi": z.get("hi"),
        "mid": z.get("mid"),
        # The band's ORIGIN, kept for colour and for honesty: a level that used
        # to be overhead supply and now sits below price is support-by-polarity,
        # which is a weaker claim than a floor that was bought four times.
        "origin": z.get("kind"),
        "touches": z.get("touches"),
        "strength": z.get("strength"),
        "bars_since_test": bars_since,
        "oldest_touch_bars": z.get("oldest_touch_bars"),
        "recent": bool(bars_since is not None and bars_since <= RECENT_BARS),
        # Price turned here more than once vs. a single swing low. See
        # MIN_TOUCHES_TESTED — this is the difference between a floor and a bar.
        "tested": bool((z.get("touches") or 0) >= MIN_TOUCHES_TESTED),
        # The bars that MADE the band (2026-09-14) — drawn as touch markers
        # so the box carries its reasons.
        "touch_dates": z.get("touch_dates"),
        "distance_pct": (_pct_above(last_price, float(z["lo"])) if above
                         else _pct_below(last_price, float(z["hi"]))),
    }


def _dedupe(zones: list[dict]) -> list[dict]:
    """Collapse bands that are the same band. `nearest_support` is computed over
    EVERY band while the returned lists are capped at the strongest four per
    side, so merging the two sources can hand back the same object twice."""
    out: list[dict] = []
    seen: set = set()
    for z in zones:
        if not z:
            continue
        key = (z.get("lo"), z.get("hi"), z.get("kind"))
        if key in seen:
            continue
        seen.add(key)
        out.append(z)
    return out


def cluster_bands(tagged: list[dict], last_price: float) -> list[dict]:
    """Cluster bands from DIFFERENT windows into agreed levels. PURE.

    `tagged` rows are price_zones bands with a `window` key added. Bands whose
    midpoints land within CLUSTER_PCT of each other are one level seen through
    different zooms — and the count of DISTINCT windows agreeing is the signal.
    Measured on CR (2026-08-24): the two four-window clusters were the level
    price stood on and the ceiling above it; every single-window band was an
    artifact of that window.

    What is deliberately NOT merged across windows:
      * `strength` — relative within its own window, meaningless across zooms
        (the same CR band scored 58 at 1y and 100 at 6m). The cluster carries
        no strength at all rather than a lying one.
      * touches — the MAX is kept, because the longest window sees the full
        count and the short window's smaller number is truncation, not
        disagreement.
    """
    order = {w["key"]: i for i, w in enumerate(SUPPORT_WINDOWS)}
    rows = sorted((b for b in tagged
                   if b.get("lo") is not None and b.get("hi") is not None),
                  key=lambda b: (float(b["lo"]) + float(b["hi"])) / 2.0)
    clusters: list[dict] = []
    for b in rows:
        mid = (float(b["lo"]) + float(b["hi"])) / 2.0
        if clusters and mid <= clusters[-1]["_last_mid"] * (1 + CLUSTER_PCT / 100.0):
            c = clusters[-1]
            c["members"].append(b)
            c["_last_mid"] = mid
        else:
            clusters.append({"_last_mid": mid, "members": [b]})

    out = []
    for c in clusters:
        m = c["members"]
        lo = min(float(x["lo"]) for x in m)
        hi = max(float(x["hi"]) for x in m)
        wins = sorted({x["window"] for x in m}, key=lambda k: order.get(k, 99))
        touches = max(int(x.get("touches") or 0) for x in m)
        bars_since = [x.get("bars_since_test") for x in m
                      if x.get("bars_since_test") is not None]
        side = ("in" if lo <= last_price <= hi
                else "below" if hi < last_price else "above")
        out.append({
            "lo": round(lo, 2), "hi": round(hi, 2),
            "mid": round((lo + hi) / 2.0, 2),
            "windows": wins,
            "agree": len(wins),
            "touches": touches,
            "tested": touches >= MIN_TOUCHES_TESTED,
            "bars_since_test": min(bars_since) if bars_since else None,
            "recent": bool(bars_since and min(bars_since) <= RECENT_BARS),
            "side": side,
            "distance_pct": (0.0 if side == "in"
                             else _pct_below(last_price, hi) if side == "below"
                             else _pct_above(last_price, lo)),
            # Kept for the FE type; an overlay row has no single origin.
            "origin": "demand" if side != "above" else "supply",
            "strength": None,
            "oldest_touch_bars": None,
        })
    # Strongest agreement first, then nearest — the reading order of the table.
    out.sort(key=lambda c: (-c["agree"], abs(c["distance_pct"] or 0.0)))
    return out


def overlay_for_symbol(sym: str, base: dict) -> dict:
    """All zooms at once: each window's bands computed independently, then
    clustered by agreement. The chart draws only clusters TWO OR MORE windows
    agree on — drawing all ~20 raw bands is the solid-block chart the label
    cap already exists to prevent, and agreement is the point of the view."""
    from sepa import prices

    df, have, as_of, closed = _frame_for(sym, max(w["bars"] for w in SUPPORT_WINDOWS),
                                         with_closed=True)
    if df is None or not len(df):
        return {**base, "error": f"No price data for {sym}."}
    base = {**base, "as_of": as_of, "data_through": _last_bar_date(df)}
    # Structure off CLOSED bars, priced at the live print — the same rule the
    # single-window path adopted 2026-09-05. This path read the live-overlaid
    # frame, so an unclosed bar could confirm or veto the newest pivot and
    # the overlay tab disagreed with the 1y tab about the same swing
    # (2026-09-14: band sets differed on 76 of 108 names).
    try:
        live_px = float(df["close"].iloc[-1])
    except Exception:                                          # pragma: no cover
        live_px = None
    struct = closed if closed is not None and len(closed) else df

    tagged: list[dict] = []
    per_window: list[dict] = []
    last_price = None
    for w in SUPPORT_WINDOWS:
        # The chart-only zooms (1w/2w) have no bands of their own — their
        # numbers ARE the 1m numbers — so a row here would duplicate 1m and
        # inflate the "N windows agree" denominator this view is built on.
        if w["key"] in CHART_ONLY_LEVELS_FROM:
            continue
        z = pz.compute(struct, last_price=live_px, swing_window=w["swing_window"],
                       lookback_bars=w["bars"],
                       max_zones=None)   # every cluster: this tab caps by NEAREST below
        if z is None:
            per_window.append({"key": w["key"], "bands": 0})
            continue
        last_price = float(z["last_price"])
        pool = _dedupe(list(z.get("demand_zones") or [])
                       + list(z.get("supply_zones") or [])
                       + [z.get("nearest_support"), z.get("nearest_resistance")])
        for b in pool:
            tagged.append({**b, "window": w["key"]})
        per_window.append({"key": w["key"], "bands": len(pool)})
    if last_price is None or not tagged:
        return {**base, "error": f"No swing structure for {sym} in any window."}

    clusters = cluster_bands(tagged, last_price)
    agreed = [c for c in clusters if c["agree"] >= 2]
    supports = [c for c in clusters if c["side"] == "below"][:MAX_LEVELS]
    overhead = [c for c in clusters if c["side"] == "above"][:MAX_LEVELS]
    inside = next((c for c in clusters if c["side"] == "in"), None)

    bands = []
    if inside and inside["agree"] >= 2:
        bands.append({"kind": "demand", "lo": inside["lo"], "hi": inside["hi"],
                      "label": f"here · {inside['agree']} windows"})
    for c in agreed:
        if c["side"] == "below":
            bands.append({"kind": "demand", "lo": c["lo"], "hi": c["hi"],
                          "label": f"{c['agree']}w"})
        elif c["side"] == "above":
            bands.append({"kind": "supply", "lo": c["lo"], "hi": c["hi"],
                          "label": f"{c['agree']}w"})
    bands = bands[:7]

    lines = [{"price": round(last_price, 2), "label": "now", "tone": "now"}]
    if supports:
        lines.append({"price": supports[0]["hi"],
                      "label": f"support {supports[0]['hi']}", "tone": "buy"})
    if overhead:
        lines.append({"price": overhead[0]["lo"],
                      "label": f"overhead {overhead[0]['lo']}", "tone": "target"})

    bars_used = min(len(df), SUPPORT_WINDOWS[-1]["bars"])
    best = clusters[0] if clusters else None
    tile = {
        "symbol": sym,
        "name": board_mod._name_for(sym),
        "href": board_mod._href(sym, "supply"),
        "bars": board_mod.bars_for(sym, days=bars_used),
        "bands": bands,
        "lines": lines,
        "markers": [],
        "stats": [
            {"k": "zoom", "v": "all windows"},
            {"k": "levels", "v": str(len(clusters))},
            {"k": "agreed 2+", "v": str(len(agreed))},
            {"k": "best agreement", "v": (f"{best['agree']} windows"
                                          if best else "—")},
        ],
        "why": (f"{len(agreed)} levels confirmed by 2+ windows out of "
                f"{len(clusters)} found — agreement is the signal; a level "
                f"only one zoom can see is usually an artifact of that zoom"),
        "theme": board_mod._theme(sym),
        "badges": [],
    }

    return {
        **base,
        "name": tile["name"],
        "last_price": last_price,
        "bars_used": bars_used,
        "short_history": None,
        "tile": tile,
        "supports": supports,
        "overhead": overhead,
        "standing_in": inside,
        "levels_capped": len(clusters) > len(supports) + len(overhead) + (1 if inside else 0),
        "per_window": per_window,
        "verdict": None,
        "params": {"cluster_pct": CLUSTER_PCT},
        "note": ("Every zoom computed independently, then clustered: bands "
                 "within 2% of each other are one level seen through different "
                 "windows. The chart draws only levels TWO OR MORE windows "
                 "agree on. Strength is not shown here — it is relative within "
                 "a single window and does not compare across zooms."),
    }


def levels_from_zones(zones: dict, last_price: float) -> dict:
    """Split every band into supports (below price) and overhead (above). PURE.

    Band ORIGIN is not the split — position is. `price_zones` keeps the
    supply/demand label for colour, but broken support trades as resistance and
    reclaimed resistance trades as support, and a table that sorted by origin
    would put a level price is standing on into the "overhead" column.
    """
    pool = _dedupe(
        list(zones.get("demand_zones") or [])
        + list(zones.get("supply_zones") or [])
        + [zones.get("nearest_support"), zones.get("nearest_resistance")]
    )
    below = [z for z in pool if z.get("hi") is not None and float(z["hi"]) < last_price]
    above = [z for z in pool if z.get("lo") is not None and float(z["lo"]) > last_price]
    inside = [z for z in pool
              if z.get("lo") is not None and z.get("hi") is not None
              and float(z["lo"]) <= last_price <= float(z["hi"])]

    # Nearest first on both sides — the level you hit next is the one you are
    # trading against, regardless of which is strongest.
    below.sort(key=lambda z: -float(z["hi"]))
    above.sort(key=lambda z: float(z["lo"]))

    supports = [_level(z, last_price, above=False) for z in below[:MAX_LEVELS]]
    overhead = [_level(z, last_price, above=True) for z in above[:MAX_LEVELS]]
    return {
        "supports": supports,
        "overhead": overhead,
        "standing_in": (_level(inside[0], last_price, above=False)
                        if inside else None),
        "levels_capped": len(below) > MAX_LEVELS or len(above) > MAX_LEVELS,
    }


def _holds_a_level(zones: Optional[dict]) -> bool:
    """Did this frame hold ANY band — below price, above it, or AROUND it?

    The gate on the named intraday fallback (2026-09-22), and `standing_in`
    is the reason it is not simply `supports or overhead`. Measured that
    evening on today's 5-minute frame: PTGX at 145.07 was standing INSIDE a
    $144.50–$145.96 band tested 13 times, so `supports` was empty and
    `overhead` held one band — yet the most useful number on the screen was
    the one under the cursor. `_bands` draws it labelled "here" and the
    verdict names it. A fallback that fired on an empty `supports` would
    have thrown that away and served him the 6-month daily band instead,
    which is the exact defect this change exists to fix.
    """
    if zones is None:
        return False
    try:
        lv = levels_from_zones(zones, float(zones["last_price"]))
    except Exception:                                          # pragma: no cover
        return False
    return bool((lv.get("supports") or []) or (lv.get("overhead") or [])
                or lv.get("standing_in"))


def _bands(levels: dict) -> list[dict]:
    """Chart boxes for the tile. Supports drawn as demand, overhead as supply —
    the tile contract's existing two colours, so `PatternChart` needs no new
    case. Capped at three a side: a chart with eight boxes is a solid block."""
    out: list[dict] = []
    inside = levels.get("standing_in")
    if inside:
        t = _touch_label(inside)
        # The box price stands IN takes its colour from its ORIGIN
        # (2026-09-14). It was always green: AAPL sat in a 2-touch
        # overhead-supply cluster, the verdict said "resistance right here",
        # and the chart drew a green support box under the cursor — 63 of 388
        # ticker-windows read that way.
        in_supply = (inside.get("origin") == "supply")
        out.append({"kind": "supply" if in_supply else "demand",
                    "lo": inside["lo"], "hi": inside["hi"],
                    "label": ("here · in supply" if in_supply else "here")
                             + (f" · {t}" if t else "")})
    for lv in (levels.get("supports") or [])[:3]:
        out.append({"kind": "demand", "lo": lv["lo"], "hi": lv["hi"],
                    **({"label": _touch_label(lv)} if _touch_label(lv) else {})})
    for lv in (levels.get("overhead") or [])[:3]:
        out.append({"kind": "supply", "lo": lv["lo"], "hi": lv["hi"],
                    **({"label": _touch_label(lv)} if _touch_label(lv) else {})})
    return out


def _touch_label(lv: dict) -> Optional[str]:
    """"3× tested" on a band price turned at more than once; nothing on a
    single swing, whose box already says what it is. The count is the one
    number that separates a floor from a bar (MIN_TOUCHES_TESTED)."""
    t = lv.get("touches")
    if isinstance(t, int) and t >= MIN_TOUCHES_TESTED:
        return f"{t}× tested"
    return None


# Marker kinds for the swings that make a band: a swing LOW (`touch_d`, drawn
# under the bar) or a swing HIGH (`touch_s`, drawn over it). Chosen by the
# band's ORIGIN, not the side it is drawn on — a broken lid now acting as
# support was made by swing highs, and the glyph has to sit where they are.
TOUCH_LOW_KIND = "touch_d"
TOUCH_HIGH_KIND = "touch_s"
MAX_TOUCH_MARKERS = 40


def _touch_markers(levels: dict) -> list[dict]:
    """Dated markers for every touch of every band the tile draws (2026-09-14).

    Ajay studies these charts to learn the pattern, and a band whose defining
    swings are not marked is a box with no visible cause. The tile only draws
    a marker whose date is inside its bar window, so a touch from a wider
    lookback than the zoom simply does not render.
    """
    inside = levels.get("standing_in")
    drawn = ([inside] if inside else []) \
        + list((levels.get("supports") or [])[:3]) \
        + list((levels.get("overhead") or [])[:3])
    out, seen = [], set()
    for lv in drawn:
        kind = (TOUCH_HIGH_KIND if (lv or {}).get("origin") == "supply"
                else TOUCH_LOW_KIND)
        for d in (lv or {}).get("touch_dates") or []:
            key = (str(d), kind)
            if key in seen:
                continue
            seen.add(key)
            out.append({"date": str(d), "kind": kind})
            if len(out) >= MAX_TOUCH_MARKERS:
                return out
    return out


def _lines(levels: dict, last_price: float) -> list[dict]:
    """Only the two levels a decision is actually made against get a label —
    the nearest support (where the stop goes) and the nearest overhead (what
    the trade has to clear). Labelling all eight is what made the zone charts
    unreadable (Ajay, 2026-08-18: "they are all clumsy")."""
    out = [{"price": round(float(last_price), 2), "label": "now", "tone": "now"}]
    sup = (levels.get("supports") or [None])[0]
    ovh = (levels.get("overhead") or [None])[0]
    if sup:
        out.append({"price": sup["hi"], "label": f"support {sup['hi']}",
                    "tone": "buy"})
    if ovh:
        out.append({"price": ovh["lo"], "label": f"overhead {ovh['lo']}",
                    "tone": "target"})
    return out


# ── The BOARD's band on the per-ticker views (2026-09-14) ─────────────────────
# Ajay: "make sure the overhead supply and demand zone logic is accurate across
# board." Measured that evening on 46 live board tickers: every board, alert
# gate and paper lane shares ONE engine at ONE geometry (demand_reentry.
# zone_geom — swing 5, merge 4%, 252 bars) and they agree with each other;
# this tab and the holdings tab read the same engine at the FINER geometry
# the zoom table documents (merge 1.75%) and agreed with the boards on the
# nearest demand band 6 times in 46 and on the nearest overhead 9 in 46. The
# doc's own promise — "a tab that could not reproduce their answer would look
# like it disagreed with them" — no longer held. So every daily view now ALSO
# carries the board's band, computed by the board's own decision function on
# the same closed frame, drawn dashed and labelled. The finer levels stay.
BOARD_NOTE = ("The dashed band is the demand BOARD's band — what Back in Demand, "
              "Deep Demand, the alert gate and the paper lanes use (swing 5 · "
              "merge 4% · 252 bars). The solid bands are this tab's finer levels "
              "at the chosen zoom.")


def board_read(closed, sym: str, last_price: float) -> Optional[dict]:
    """The demand board's read of THIS closed frame, priced off `last_price`.

    `decide_from_frame` is the one rule every S/D board, the alert gate and
    the lanes run, so its entry band (else its nearest support, which may be
    a lid turned floor) and the alert gate's first overhead ARE the bands an
    alert would name. None when the frame is too short or the rule declines.
    """
    try:
        from supply_demand import demand_reentry as DR
        from supply_demand import alert_gates as _gates
        from supply_demand.room_floor import plan_bands
    except Exception:                                          # pragma: no cover
        return None
    try:
        rec = DR.decide_from_frame(closed, sym, last_price=last_price)
    except Exception as exc:                                   # pragma: no cover
        log.debug("support: board read for %s failed: %s", sym, exc)
        return None
    if not rec:
        return None
    px = float(last_price)

    def _dist(lo, hi):
        if lo <= px <= hi:
            return 0.0
        return (round((lo - px) / px * 100.0, 2) if lo > px
                else round((px - hi) / px * 100.0, 2))

    entry = rec.get("entry_zone")
    dem = entry or rec.get("nearest_support")
    cands = ([rec.get("nearest_resistance")] + list(rec.get("supply_zones") or [])
             + list(rec.get("demand_zones") or []))
    try:
        first = _gates.first_overhead(plan_bands(cands, entry), px, rec.get("prev_close"))
    except Exception:                                          # pragma: no cover
        first = None
    verdict = rec.get("verdict")
    out = {"demand": None, "supply": None,
           "in_demand_band": bool(rec.get("in_demand_band")),
           "verdict": (verdict.get("label") if isinstance(verdict, dict) else verdict),
           "geom": DR.zone_geom(), "lookback_bars": pz.LOOKBACK_BARS,
           "structure_through": rec.get("structure_through")}
    if dem and dem.get("lo") is not None and dem.get("hi") is not None:
        lo, hi = float(dem["lo"]), float(dem["hi"])
        out["demand"] = {"lo": round(lo, 2), "hi": round(hi, 2),
                         "touches": dem.get("touches"),
                         "origin": dem.get("kind") or "demand",
                         "is_entry_band": entry is not None and dem is entry,
                         "distance_pct": _dist(lo, hi)}
    if first and first.get("lo") is not None and first.get("hi") is not None:
        lo, hi = float(first["lo"]), float(first["hi"])
        out["supply"] = {"lo": round(lo, 2), "hi": round(hi, 2),
                         "touches": first.get("touches"),
                         "distance_pct": _dist(lo, hi)}
    return out


def _board_bands(board: Optional[dict]) -> list[dict]:
    out: list[dict] = []
    if not board:
        return out
    d, s = board.get("demand"), board.get("supply")
    if d:
        t = f" · {d['touches']}× tested" if d.get("touches") else ""
        out.append({"kind": "board_demand", "lo": d["lo"], "hi": d["hi"],
                    "label": f"board demand{t}"})
    if s:
        out.append({"kind": "board_supply", "lo": s["lo"], "hi": s["hi"],
                    "label": "board overhead"})
    return out


def _board_pos(b: dict, *, above: bool) -> str:
    if b["distance_pct"] == 0.0:
        return "price inside"
    return f"+{b['distance_pct']}%" if above else f"{b['distance_pct']}% below"


def _board_stats(board: Optional[dict]) -> list[dict]:
    if not board:
        return []
    d, s = board.get("demand"), board.get("supply")
    return [
        {"k": "board demand band",
         "v": (f"${d['lo']}–${d['hi']}  ({_board_pos(d, above=False)})" if d
               else "none — the board would not list it")},
        {"k": "board overhead",
         "v": (f"${s['lo']}–${s['hi']}  ({_board_pos(s, above=True)})" if s
               else "clear — no band above the print")},
    ]


def _board_why(board: Optional[dict]) -> str:
    if not board:
        return ""
    d, s = board.get("demand"), board.get("supply")
    dem = (f"demand ${d['lo']}–${d['hi']} ({_board_pos(d, above=False)})" if d
           else "no demand band")
    sup = (f"overhead ${s['lo']}–${s['hi']} ({_board_pos(s, above=True)})" if s
           else "overhead clear")
    return f"BOARD (what alerts and lanes use): {dem} · {sup}. "


def _stats(levels: dict, zones: dict, spec: dict) -> list[dict]:
    sup = (levels.get("supports") or [None])[0]
    ovh = (levels.get("overhead") or [None])[0]
    out = [{"k": "zoom", "v": spec["label"]}]
    if sup:
        out.append({"k": "nearest support",
                    "v": f"${sup['lo']}–${sup['hi']}  ({sup['distance_pct']}% below)"})
    else:
        out.append({"k": "nearest support", "v": "none in this window"})
    if ovh:
        out.append({"k": "nearest overhead",
                    "v": f"${ovh['lo']}–${ovh['hi']}  (+{ovh['distance_pct']}%)"})
    sups = levels.get("supports") or []
    n_recent = sum(1 for lv in sups if lv["recent"])
    n_tested = sum(1 for lv in sups if lv["tested"])
    out.append({"k": "touched in last month", "v": f"{n_recent} of {len(sups)}"})
    out.append({"k": "turned at more than once", "v": f"{n_tested} of {len(sups)}"})
    return out


#: The two `price_zones._verdict` states that assert price is INSIDE a band.
#: They are the only ones whose numbers can contradict the chart, because the
#: verdict reads pz.compute's RAW pool while the chart draws the DE-DUPED,
#: merged pool from `levels_from_zones` (2026-09-23).
IN_ZONE_STATES = ("AT_DEMAND", "AT_SUPPLY")


def _in_zone_head(inside: dict) -> str:
    """`price_zones._verdict`'s OWN two in-zone sentences, on the DRAWN band.

    Measured 2026-09-22 on the branch, NVDA `5m_today`: the chart drew a
    demand band at $225.56–$229.44 ("here · 29x tested") while the verdict
    beside it read "In an overhead-supply band ($226.40–$229.98)" — neither
    the numbers nor the SIDE matched, and $226.40–$229.98 was drawn nowhere.
    The split is pre-existing in the engine (it shows on 15m too), but the
    5-minute frames used to read the DAILY frame for both, so the two agreed
    there until 2026-09-22.

    No new rule and no new maths: the mapping below is `_verdict`'s, verbatim
    (kind demand -> "support is right here", kind supply -> "resistance right
    here"), applied to the band the tile actually paints. The engine's own
    `verdict` object is served untouched at the payload's top level.
    """
    lo, hi = inside.get("lo"), inside.get("hi")
    if inside.get("origin") == "supply":
        return (f"In an overhead-supply band (${lo}–${hi}) — resistance right "
                f"here; it needs to clear this before it runs.")
    return (f"In a demand zone (${lo}–${hi}, {inside.get('touches')}x tested) "
            f"— support is right here.")


def _why(levels: dict, zones: dict, spec: dict) -> str:
    verdict = (zones.get("verdict") or {})
    sup = (levels.get("supports") or [None])[0]
    head = verdict.get("label") or ""
    if verdict.get("state") in IN_ZONE_STATES:
        inside = levels.get("standing_in")
        # No drawn containing band at all: the verdict is naming a raw band
        # this chart does not paint, so it says nothing here rather than
        # pointing at numbers a reader cannot find.
        head = _in_zone_head(inside) if inside else ""
    if sup and sup["distance_pct"] is not None:
        when = ("tested in the last month" if sup["recent"]
                else f"last tested {sup['bars_since_test']} bars ago")
        weak = ("" if sup["tested"] else
                " Single swing low, not a tested floor.")
        return (f"{head} Nearest support over {spec['label']}: "
                f"${sup['lo']}–${sup['hi']}, {sup['distance_pct']}% below, "
                f"{sup['touches']}× touched, {when}.{weak}")
    return head or f"No band below price in the last {spec['label']}."


def _last_sessions(df, n: int):
    """The bars of `df` belonging to its last `n` ET SESSION dates.

    Ajay 2026-09-18: "Can you increase the bars on the weekly chart please? I am
    trying to read more on the weekly chart" — on a 1W zoom serving its honest 5
    daily bars. Asked, he chose "1 week of HOURLY bars": keep the span, raise the
    resolution. So a short window now trims the intraday CHART instead of being
    inert on it.

    BY SESSION DATE, NEVER BY BAR COUNT. A count (5 x 6.5) would need a
    bars-per-session number this repo does not have, and it bleeds into the prior
    session on a half-day and clips on a full one. Counting dates needs neither.

    THE INDEX IS UTC AND NAIVE. Verified on the live frame 2026-09-18 12:23 ET /
    16:23 UTC: MU's last 60m bar stamps 16:30 and 2026-09-17 runs 17:00 -> 20:00,
    i.e. 13:00 -> 16:00 ET, the RTH afternoon into the close. So `.date()` taken
    raw is a UTC date. For an RTH frame that happens to agree with the ET
    session, but the extended session runs to 20:00 ET = 00:00 UTC THE NEXT DAY —
    so on `5m_live` a raw date would file the last after-hours hour under
    tomorrow and drop it from today. Convert first. This is the container-UTC vs
    provider-ET trap the repo already carries elsewhere.

    Returns (frame, n_sessions_present). Fewer sessions than asked is NOT an
    error — it is what a shallow intraday cache looks like, and the caller says
    so rather than claiming a span the frame does not hold.
    """
    if df is None or not len(df) or n <= 0:
        return df, 0
    idx = df.index
    try:
        et = (idx.tz_localize("UTC") if getattr(idx, "tz", None) is None
              else idx).tz_convert("America/New_York")
    except Exception as exc:                                   # noqa: BLE001
        log.debug("support: session slice could not localise the index: %s", exc)
        return df, 0
    dates = et.normalize()
    uniq = sorted(set(dates))
    if not uniq:
        return df, 0
    keep = set(uniq[-n:])
    mask = dates.isin(keep)
    out = df[mask]
    return (out if len(out) else df), len(keep)


def _attach_ma(tile: dict, frame, *, intraday: bool) -> None:
    """〰️ The three moving averages on a Support tile, in place.

    Ajay 2026-09-24, on a screenshot of this tab's LEDGER row: *"I would need
    9EMA and 20 SMA here too as check boxes"*. Same three families, the same
    shared checkboxes, the same `board._ma_curves` engine — the only thing this
    wrapper owns is WHICH FRAME and WHICH KEY.

    THE FRAME. Daily gets the UNTAILED frame out of `bars_for(frame_out=...)`,
    so a 200 SMA under a 1-year chart is a true 200-bar average and does not
    move when he changes the Zoom. Intraday gets `chart_df`, the widest frame
    that timeframe has, and its averages are therefore in ITS bars: a 20 SMA on
    the 15-minute chart is twenty 15-minute bars. That is the rule this tab's
    levels have followed since 2026-09-23 and the averages must not differ from
    it — a 20-DAY average drawn over a 15-minute chart is the "why is one hour
    showing Monthly?" bug wearing a new label.

    THE KEY. `_intraday_stamp` on an intraday frame, because those bars carry
    HH:MM in ET; the board default (date-only) on a daily one. Get this wrong
    and nothing raises — the join simply matches nothing, every curve is
    dropped as all-warm-up, and the lines silently never appear.

    Soft-fails to no curves. A drawing must never be able to empty a tile.
    """
    if frame is None:
        return
    try:
        board_mod._ma_curves(tile, frame,
                             stamp=_intraday_stamp if intraday else None)
    except Exception as exc:                                    # noqa: BLE001
        log.debug("support: moving averages failed: %s", exc)


def _intraday_stamp(ts) -> str:
    """The SAME key `_frame_bars` writes into a bar's `t`.

    〰️ The moving averages (2026-09-24) join to the drawn bars by string, and
    on an intraday frame that string carries HH:MM in ET. `board._row_date`,
    the default, is date-only — it would match NOTHING here, every value would
    come back None, every curve would be dropped as all-warm-up, and the
    averages would silently never appear on a 5-minute chart. Defined beside
    `_frame_bars` and used by both so the format has one definition.
    """
    return _et(ts).strftime("%Y-%m-%d %H:%M")


def _frame_bars(df) -> list:
    """Candles straight from the analysed intraday frame.

    Timestamps carry HH:MM, unlike the daily helper's date-only stamps —
    without the time, every bar in a session would share one label and the
    chart's own axis would collapse them into one candle.
    """
    bars = []
    try:
        for ts, row in df.iterrows():
            bars.append({
                # ET on the axis. The minute loader indexes in UTC, and a
                # 13:30 stamp over the opening bar read as a lunch print
                # (found 2026-09-02 building the live frame).
                "t": _intraday_stamp(ts),
                "o": round(float(row["open"]), 4),
                "h": round(float(row["high"]), 4),
                "l": round(float(row["low"]), 4),
                "c": round(float(row["close"]), 4),
                "v": float(row.get("volume") or 0.0),
                # 'pre' / 'ah' on extended-hours bars so the chart can shade
                # them; absent on RTH bars (and on every non-live frame).
                **({"s": _SESSION_FLAG[row["session"]]}
                   if "session" in df.columns and row.get("session") in _SESSION_FLAG
                   else {}),
            })
    except Exception as exc:                                # pragma: no cover
        log.warning("support: intraday bars failed: %s", exc)
    return bars


_SESSION_FLAG = {"premarket": "pre", "afterhours": "ah"}


def _et(ts):
    """UTC (naive or aware) timestamp → America/New_York."""
    import pandas as pd
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.tz_convert("America/New_York")


def _et_str(ts) -> str:
    return _et(ts).strftime("%Y-%m-%d %H:%M ET")


def overnight_read(df, supports: list, overhead: list) -> Optional[dict]:
    """Where price went since the last regular close, against the levels.

    Ajay 2026-09-02: "I wanna see where things bounced over night." Pure
    over the extended-hours bars printed AFTER the most recent RTH bar:
    the overnight low/high, and every band the overnight tape ENTERED — a
    bar whose low reached into a support band (or high into an overhead
    band) — with whether the last overnight close is back outside it
    ("held") or inside/through it. Thin-tape caveat is stated, never
    hidden: an overnight touch is a print, not a defended level.

    None when the frame carries no session tags or nothing has printed
    since the close.
    """
    try:
        if df is None or "session" not in df.columns or not len(df):
            return None
        sess = list(df["session"])
        n = len(sess)
        # Anchor on the close BEFORE the most recent extended-hours run, not
        # on the last RTH bar in the frame — otherwise, one minute after
        # today's open the read discards the whole overnight and claims
        # "nothing printed" for the rest of the session (review 2026-09-02).
        i = n - 1
        while i >= 0 and sess[i] == "rth":      # skip today's RTH run
            i -= 1
        end = i + 1                              # first bar of today's RTH run
        while i >= 0 and sess[i] in ("afterhours", "premarket"):
            i -= 1                               # walk back over the ext run
        if i < 0:
            return None                          # no prior close in the frame
        after = df.iloc[i + 1:end]
        after = after[after["session"].isin(("afterhours", "premarket"))]
        if not len(after):
            return {"bars": 0, "since": _et_str(df.index[i]),
                    "note": "Nothing has printed since the last regular close."}
        lo_i = after["low"].idxmin()
        hi_i = after["high"].idxmax()
        last_close = float(after["close"].iloc[-1])
        rth_close = float(df["close"].iloc[i])
        touches = []
        for band, side in ([(b, "support") for b in supports]
                           + [(b, "overhead") for b in overhead]):
            b_lo, b_hi = band.get("lo"), band.get("hi")
            if not b_lo or not b_hi or b_hi < b_lo:
                continue
            # OVERLAP, not "an extreme landed inside": a bar that gapped
            # clean through the band is the event this feature exists for,
            # and an extreme-only test reported "No level touched" while
            # price sat 7% under support (review 2026-09-02).
            hit = after[(after["low"] <= b_hi) & (after["high"] >= b_lo)]
            # CROSSED: price was on one side of the band at the close and the
            # overnight tape traded clean past it without ever printing
            # inside — a gap through, which is the event, not a non-event.
            if side == "support":
                crossed = rth_close > b_hi and float(after["low"].min()) < b_lo
            else:
                crossed = rth_close < b_lo and float(after["high"].max()) > b_hi
            if not len(hit) and not crossed:
                continue
            if len(hit):
                first = hit.index[0]
            elif side == "support":
                first = after["low"].idxmin()
            else:
                first = after["high"].idxmax()
            rec = {"side": side, "lo": b_lo, "hi": b_hi, "at": _et_str(first),
                   "gapped": not len(hit)}
            if side == "support":
                rec.update({"low": round(float(after["low"].min()), 4),
                            "held": last_close > b_hi, "broke": last_close < b_lo})
            else:
                rec.update({"high": round(float(after["high"].max()), 4),
                            "held": last_close < b_lo, "broke": last_close > b_hi})
            touches.append(rec)
        return {
            "bars": int(len(after)),
            "since": _et_str(df.index[i]),
            "rth_close": round(rth_close, 4),
            "low": round(float(after["low"].min()), 4), "low_at": _et_str(lo_i),
            "high": round(float(after["high"].max()), 4), "high_at": _et_str(hi_i),
            "last": round(last_close, 4),
            "change_pct": round((last_close / rth_close - 1) * 100, 2) if rth_close else None,
            "touches": touches,
            "note": ("Extended-hours prints are thin — a touch here is a print, "
                     "not a defended level. Structure is read from regular "
                     "hours only."),
        }
    except Exception as exc:                                # pragma: no cover
        log.warning("support: overnight read failed: %s", exc)
        return None


def trend_read(df, mood_read: Optional[dict]) -> dict:
    """Bullish / bearish on THIS timeframe, said in one word.

    Ajay 2026-08-29: "also trend if its bullish or bearish from the trend".
    The mood score already contains a trend component, but a number between
    -100 and 100 does not answer "is this thing going up" — so the direction
    is stated on its own, from the three facts that decide it.
    """
    out = {"direction": "unknown", "label": "unknown", "why": [],
           "ema20": None, "ema50": None}
    try:
        closes = df["close"].astype(float)
        if len(closes) < 50:
            out["why"].append("needs 50 bars to read a trend")
            return out
        e20 = float(closes.ewm(span=20, adjust=False).mean().iloc[-1])
        e50 = float(closes.ewm(span=50, adjust=False).mean().iloc[-1])
        last = float(closes.iloc[-1])
    except Exception:
        return out

    out["ema20"], out["ema50"] = round(e20, 2), round(e50, 2)
    above20, above50, stacked = last > e20, last > e50, e20 > e50
    votes = sum((above20, above50, stacked))
    out["direction"] = "bullish" if votes >= 2 else "bearish"
    out["label"] = {3: "bullish", 2: "leaning bullish",
                    1: "leaning bearish", 0: "bearish"}[votes]
    out["why"] = [
        f"price {'above' if above20 else 'below'} EMA20 ({e20:.2f})",
        f"price {'above' if above50 else 'below'} EMA50 ({e50:.2f})",
        f"EMA20 {'above' if stacked else 'below'} EMA50",
    ]
    if mood_read and mood_read.get("score") is not None:
        out["mood_agrees"] = (
            (out["direction"] == "bullish" and mood_read["score"] > 0)
            or (out["direction"] == "bearish" and mood_read["score"] < 0))
    return out


def _draw_overlay(tile: dict, gaps: list, smc_read: Optional[dict],
                  orb: Optional[dict], last_price: float) -> dict:
    """Put the FVGs, order blocks, BOS and swept levels ON THE CHART.

    Ajay 2026-08-29: "do you actually draw these out on the map?" — they
    were tables only, which meant reading a level in one place and hunting
    for it in another.

    Deliberately capped. Every band is ink, and a chart carrying nine
    overlapping boxes answers nothing; the nearest two of each kind are the
    ones a decision touches. Counts of drawn-vs-found ride back so the tab
    can say "2 of 5" rather than quietly hiding three.
    """
    bands = list(tile.get("bands") or [])
    lines = list(tile.get("lines") or [])
    drawn = {"fvg": 0, "order_block": 0, "bos": 0, "sweep": 0, "orb": 0}

    def _near(z):
        try:
            return abs((float(z["hi"]) + float(z["lo"])) / 2 - last_price)
        except (KeyError, TypeError, ValueError):
            return float("inf")

    for g in sorted(gaps or [], key=_near)[:2]:
        bands.append({"kind": "fvg_demand" if g.get("kind") == "demand"
                              else "fvg_supply",
                      "lo": g["lo"], "hi": g["hi"],
                      "label": f"FVG {g.get('fill_pct', 0):g}% filled"})
        drawn["fvg"] += 1

    obs = ((smc_read or {}).get("order_blocks") or [])
    for o in sorted(obs, key=_near)[:2]:
        bands.append({"kind": "order_block", "lo": o["lo"], "hi": o["hi"],
                      "label": f"Order block {o.get('displacement_atr')}x ATR"})
        drawn["order_block"] += 1

    brks = ((smc_read or {}).get("breaks") or [])
    if brks:
        b = brks[0]
        lines.append({"price": b["level"],
                      "label": f"{b['kind']} {b['level']:.2f}", "quiet": True,
                      "tone": "target" if b["direction"] == "bullish" else "stop"})
        drawn["bos"] += 1
    sweeps = ((smc_read or {}).get("sweeps") or [])
    if sweeps:
        s = sweeps[0]
        lines.append({"price": s["level"], "quiet": True,
                      "label": f"swept {s['level']:.2f}", "tone": "neutral"})
        drawn["sweep"] += 1
    if orb:
        lines.append({"price": orb["hi"], "label": f"ORB hi {orb['hi']:.2f}",
                      "tone": "neutral", "quiet": True})
        lines.append({"price": orb["lo"], "label": f"ORB lo {orb['lo']:.2f}",
                      "tone": "neutral", "quiet": True})
        drawn["orb"] = 2

    tile["bands"] = bands
    tile["lines"] = lines
    return {"drawn": drawn,
            "found": {"fvg": len(gaps or []), "order_block": len(obs),
                      "bos": len(brks), "sweep": len(sweeps)}}


def _record_signal(sym: str, tf_key: str, sig: dict,
                   last_price: Optional[float]) -> None:
    """Log every BUY/SELL to the forward-measurement ledger.

    This is the honest answer to "how does GainzAlgo figure it out": its
    source is protected and its accuracy is a marketing number, so rather
    than guess at their formula we measure OURS. `learning.observations`
    resolves each row against real forward prices, which turns a signal
    into something with a hit rate he owns.

    Deduped per (symbol, timeframe, bar) — the tab refetches on every
    keystroke and a ledger full of the same call would corrupt the rate.
    """
    try:
        import time

        from learning import observations as obs
        horizon = {"15m": 6, "60m": 24}.get(tf_key, 72)
        obs.record_observation(
            source=f"mood_signal:{tf_key}",
            ticker=sym,
            ts=int(time.time()),
            direction="up" if sig.get("action") == "BUY" else "down",
            baseline_price=last_price,
            horizon_hours=horizon,
            predicted_pct=float((sig.get("trade") or {}).get("rr") or 0) or 0.0,
            prediction_id=f"{sym}:{tf_key}:{sig.get('action')}:"
                          f"{(sig.get('level') or {}).get('lo')}",
        )
    except Exception as exc:                                # pragma: no cover
        log.debug("support: signal ledger write failed: %s", exc)


def for_symbol(symbol: str, window: str = DEFAULT_WINDOW,
               tf: str = TF_DEFAULT) -> dict:
    """Support levels for one ticker at one zoom, on one timeframe.

    `tf` (Ajay 2026-08-29) selects the BARS the structure is read from —
    daily, hourly or 15-minute. The zoom (`window`) and the timeframe are
    independent questions: the window says how far back to look, the
    timeframe says how finely. On an intraday timeframe the window's daily
    bar budget is meaningless, so the timeframe's own budget is used and
    the label says which span was actually read.

    Always answers a dict. A bad symbol, a thin frame or a structureless window
    come back as `{'error': …}` with the dropdown still populated, because the
    tab has to keep rendering its controls after a miss — the user's next move
    is to change the zoom or the ticker.
    """
    sym = (symbol if isinstance(symbol, str) else "").upper().strip()
    spec = window_spec(window)
    overlay = parse_window(window) == OVERLAY_KEY
    base = {
        "symbol": sym,
        "window": OVERLAY_KEY if overlay else spec["key"],
        "window_label": "All windows · overlay" if overlay else spec["label"],
        "windows": ([{"key": w["key"], "label": w["label"], "bars": w["bars"]}
                     for w in SUPPORT_WINDOWS]
                    + [{"key": OVERLAY_KEY, "label": "All windows · overlay",
                        "bars": 0}]),
        "recent_bars": RECENT_BARS,
        # Ajay 2026-08-29: the second dropdown. Present on every response,
        # errors included — the tab must keep rendering its controls so the
        # next move (change the timeframe) is available after a miss.
        "timeframe": tf_mod.parse_tf(tf),
        "timeframe_label": tf_mod.tf_spec(tf)["label"],
        # The bar size, beside the job name. `studies_note` and the level
        # tables need a noun ("5-minute"), never "Today, for an entry"
        # (2026-09-23).
        "timeframe_bar_label": tf_mod.tf_spec(tf)["bar_label"],
        "timeframes": tf_mod.tf_options(include_live=True),
        "disclaimer": DISCLAIMER,
    }
    if not sym:
        return {**base, "error": "Type a ticker to see its support levels."}
    if overlay:
        return overlay_for_symbol(sym, base)

    tf_key = tf_mod.parse_tf(tf)
    intraday = tf_key != tf_mod.DAILY
    # Empty on the daily branch, which never calls `frame_for`. It is read
    # below for the frame's OWN window label, which `frame_for` may narrow
    # once it has seen the bars (the `24h` one-session case, 2026-09-23).
    tf_meta: dict = {}
    live_raw = None
    # `closed` = the frame WITHOUT today's live bar / the in-progress bucket
    # (integrator 2026-09-05). Structure (swings, gaps, ATR) reads it; the
    # live print still prices the levels — price_zones.for_symbol's rule.
    closed = None
    try:
        if intraday:
            # allow_ext: this tab is the one caller allowed to hold an
            # extended-hours frame. Until 2026-09-22 that was justified by
            # "it draws these bars but reads its levels from daily"; now it
            # reads its levels from them too, and the justification is the
            # narrower one the guard was always really making — the SUPPORT
            # TAB is a chart a human reads, not a universe pass that mints
            # alerts off a 07:12 print. Nothing downstream of here reaches the gate
            # or the lanes: `_record_signal` is off on these frames and the
            # `board` block stays daily.
            live_raw = (tf_mod.intraday_raw(sym, tf_key)
                        if tf_mod.tf_spec(tf_key).get("ext_hours") else None)
            df, tf_meta = tf_mod.frame_for(sym, tf_key, allow_ext=True,
                                           raw=live_raw)
            as_of = tf_meta.get("as_of")
            base = {**base, "timeframe_meta": tf_meta}
            if df is None:
                # The frame's BAR SIZE, never its job name: since 2026-09-22
                # `label` is "Today, for an entry", and "No Today, for an entry
                # bars for THIN" is not a sentence. Same rule as the
                # no-structure branch below (2026-09-23).
                return {**base, "error": (
                    f"No {tf_meta['bar_label']} bars for {sym} — "
                    f"{tf_meta.get('reason') or 'intraday data unavailable'}.")}
            if tf_meta.get("partial") and len(df) > 1:
                closed = df.iloc[:-1]
        else:
            df, _have, as_of, closed = _frame_for(sym, spec["bars"], with_closed=True)
    except Exception as exc:                                  # pragma: no cover
        log.debug("support: prices %s failed: %s", sym, exc)
        return {**base, "error": f"No price data for {sym}."}

    if df is None or not len(df):
        return {**base, "error": f"No price data for {sym}."}
    base = {**base, "as_of": as_of,
            "data_through": _last_bar_date(df, intraday=intraday)}

    # AN INTRADAY FRAME READS ITS OWN LEVELS (Ajay 2026-09-22).
    #
    # > "I wanna use this for entries during the day and it been useless for
    # >  that ... at any giving point This has been useless"
    #
    # Until today the two 5-minute frames — the only ones carrying
    # `ext_hours` — swapped the DAILY frame in before any level was read, so
    # the frames he picks FOR AN ENTRY were the only ones handing him coarse
    # 6-month daily bands. Measured 2026-09-22, PTGX at 145.07: both
    # 5-minute frames said 142.43-144.15 (the 6-month daily band, 0.6%
    # under the print and untouched for months) while PTGX's OWN 5-minute
    # tape that day put price INSIDE a 144.50-145.96 band tested 14 times.
    # The number he needed was computable and was being discarded. `15m`
    # and `60m` already read their own bars; the 5-minute frames now go
    # through THAT SAME PATH. No new level maths: `own_bars` simply becomes
    # true for them.
    #
    # THE ORIGINAL REASON IS NOT THROWN AWAY. The 2026-09-02 comment was
    # right that an intraday window "after a gap, may hold no level at all".
    # That case is now a NAMED fallback a few lines below — the daily read,
    # announced in `levels_fallback` and in the first sentence of `note` —
    # rather than the unconditional default it had become.
    #
    # `chart_df` is what is drawn; `df` from here on is what is analysed.
    chart_df = df
    ext_frame = bool(intraday and tf_mod.tf_spec(tf_key).get("ext_hours"))
    # The DAILY frame is still read on every intraday frame, for two things
    # that must not follow the chart: the BOARD block (what the alerts and
    # lanes use — see `board_read`) and the named level fallback.
    daily_df = daily_closed = daily_as_of = None
    if intraday:
        try:
            daily_df, _have_d, daily_as_of, daily_closed = _frame_for(
                sym, spec["bars"], with_closed=True)
        except Exception as exc:                              # pragma: no cover
            log.debug("support: daily frame for %s failed: %s", sym, exc)
            daily_df = daily_closed = daily_as_of = None
        if daily_df is not None and not len(daily_df):
            daily_df = None
        if ext_frame and daily_df is None:
            # The extended frames are the ones the board block rides on, and
            # they are the ones whose fallback is being promised. Without a
            # daily frame neither promise can be kept, so say so rather than
            # serve half an answer.
            return {**base,
                    "error": f"No daily price data for {sym} to read the "
                             f"board's band from."}

    # A frame SHORTER than the window asked for still computes — `.iloc[-126:]`
    # on 30 bars is 30 bars — and would then be labelled "6 months" on screen.
    # A recent IPO is the ordinary case, and refusing it is worse than answering
    # it, so the truncation is reported rather than hidden or fatal.
    tf_spec_ = tf_mod.tf_spec(tf_key)
    # THE SPAN THE FRAME ACTUALLY HOLDS, not the one its spec advertises
    # (2026-09-23). `frame_for` narrows this for `24h` when the 24-hour slice
    # turned out to hold a single session — every evening, every weekend and
    # every pre-market, where `24h` and `5m_today` draw the same chart. Every
    # sentence on this tab that names the span reads THIS, so there is one
    # place the two can never disagree.
    tf_window_label = tf_meta.get("window_label") or tf_spec_["window_label"]
    # EVERY intraday frame budgets from its own spec now, the 5-minute ones
    # included. This one assignment is the whole behavioural change.
    own_bars = intraday
    # The chart-only zooms (Ajay 2026-09-18). `budget` is the CHART bar count —
    # the 5 or 10 sessions his label promises. `read_budget` is what every
    # ANALYTIC read runs on, and at 1w/2w that is the 1-month window's 21 bars:
    # price_zones.compute refuses a frame under MIN_BARS_ABS outright, and a
    # 5-bar mood scores 10 where the 1-month read scores 49.6 against
    # MOOD_BUY = 25.0 — i.e. WAIT vs BUY on identical bands. For every other
    # window and every intraday view level_spec is spec and read_budget ==
    # budget, so nothing else changes by a byte.
    chart_only = (not own_bars) and spec["key"] in CHART_ONLY_LEVELS_FROM
    level_spec = (window_spec(CHART_ONLY_LEVELS_FROM[spec["key"]])
                  if chart_only else spec)
    budget = tf_spec_["bars"] if own_bars else spec["bars"]
    read_budget = tf_spec_["bars"] if own_bars else level_spec["bars"]
    swing = tf_spec_["swing_window"] if own_bars else level_spec["swing_window"]
    bars_used = min(len(df), budget)
    # A SHORT WINDOW NOW REACHES THE INTRADAY CHART (Ajay 2026-09-18).
    # 1W/2W used to be inert on every intraday frame — `zoom_applies: false` —
    # so 1w+60m drew the frame's whole 330-bar budget, ~47 sessions, under a
    # label that said one week. It now draws that window's OWN sessions at the
    # timeframe's resolution: ~33 hourly bars for a week instead of 5 daily ones.
    #
    # ONLY the chart is trimmed. `df` — what every level, mood, trend and pattern
    # read runs on — is untouched, so the numbers beside the chart are exactly
    # the ones the un-trimmed frame produced. That separation already existed
    # (chart_df vs df above); this leans on it rather than widening it.
    short_intraday, short_sessions = None, 0
    if intraday and spec["key"] in CHART_ONLY_LEVELS_FROM:
        short_intraday, short_sessions = _last_sessions(chart_df, spec["bars"])
        if short_sessions == 0:                    # could not read a session date
            short_intraday = None
    # Three different things: `short` is CHART truncation (fewer bars than the
    # picture asked for), `level_short` is an EVIDENCE shortfall behind the
    # reads (fewer bars than the 21 the numbers ask for), `chart_only` is which
    # window asked. A 13-bar symbol at 1w met the 5-bar chart budget and is not
    # `short`, but its levels still came off 13 bars against a 21-bar ask.
    short = bars_used < budget
    level_short = len(df) < read_budget
    if closed is None or not len(closed):
        closed = df                                   # nothing live on top: read whole
    try:
        live_last = float(df["close"].iloc[-1])
    except Exception:                                 # pragma: no cover
        live_last = None
    if live_last is not None and not live_last > 0:
        live_last = None

    zones = pz.compute(closed, last_price=live_last, swing_window=swing,
                       lookback_bars=read_budget, max_zones=None)

    # THE NAMED FALLBACK. An intraday window that holds no cluster — the gap
    # case the 2026-09-02 comment warned about — falls back to the DAILY
    # read rather than erroring, and SAYS SO. A silent fallback would
    # recreate the exact confusion this change removes: he would be looking
    # at 5-minute candles under daily bands with nothing on screen to tell
    # him which is which.
    levels_fallback = None
    if (not _holds_a_level(zones)) and intraday and daily_df is not None:
        # Everything the daily read would overwrite, kept so the fallback can
        # be ABANDONED. If the daily window holds no level either, the
        # intraday read — empty lists and all — is still the honest answer to
        # what was asked, and turning that into an error would be a fresh
        # regression on 15m/60m, which render an empty read today.
        keep = (own_bars, chart_only, level_spec, df, closed, budget,
                read_budget, swing, bars_used, short, level_short, zones)
        own_bars = False
        chart_only = spec["key"] in CHART_ONLY_LEVELS_FROM
        level_spec = (window_spec(CHART_ONLY_LEVELS_FROM[spec["key"]])
                      if chart_only else spec)
        df, closed = daily_df, daily_closed
        if closed is None or not len(closed):
            closed = df
        budget = spec["bars"]
        read_budget = level_spec["bars"]
        swing = level_spec["swing_window"]
        bars_used = min(len(df), budget)
        short = bars_used < budget
        level_short = len(df) < read_budget
        try:
            daily_last = float(df["close"].iloc[-1])
        except Exception:                             # pragma: no cover
            daily_last = None
        if daily_last is not None and not daily_last > 0:
            daily_last = None
        zones = pz.compute(closed, last_price=daily_last, swing_window=swing,
                           lookback_bars=read_budget, max_zones=None)
        if _holds_a_level(zones):
            live_last = daily_last
            levels_fallback = {
                "from": tf_spec_["label"],
                "from_bars": tf_spec_["bar_label"],
                "to": level_spec["label"],
                "note": (f"The {tf_spec_['bar_label']} window held no level, "
                         f"so these levels are the {level_spec['label']} "
                         f"daily read — not this chart's own."),
            }
            base = {**base, "levels_as_of": daily_as_of}
        else:
            (own_bars, chart_only, level_spec, df, closed, budget,
             read_budget, swing, bars_used, short, level_short, zones) = keep

    # What the stats row and the why-sentence call the window. On an intraday
    # timeframe the structure came from the timeframe's OWN bars, and the
    # daily zoom label ("6 months" under an hourly chart) was a lie the header
    # chip stopped telling on 2026-08-29 but the tile kept (2026-09-14).
    # `bar_label`, never `label`: since 2026-09-22 `label` names the JOB
    # ("Today, for an entry"), which would read as nonsense in "N x … bars".
    scope_spec = (level_spec if not own_bars
                  else {**spec,
                        "label": f"{bars_used} x {tf_spec_['bar_label']} bars"})

    if zones is None:
        # Two different misses with two different fixes, so two messages. The
        # fix for the second one is the dropdown sitting right there.
        # The frame's BAR SIZE, not its job name: "too few to read a Today,
        # for an entry window" is not a sentence (2026-09-22).
        scope = (f"{tf_spec_['bar_label']} ({tf_window_label})"
                 if own_bars else level_spec["label"])
        # `len(df)`, not `bars_used`: on this branch they are the same number
        # for every non-chart-only window (short ⟺ len(df) < budget ⟺
        # bars_used == len(df)), and on a chart-only zoom bars_used is the
        # 5-bar CHART budget while the sentence is about the history the READ
        # did not have. The no-structure branch below keeps bars_used — a
        # 300-bar frame at 1m must report 21 there, not 300.
        if short or level_short:
            return {**base, "bars_used": len(df),
                    "error": f"{sym} has only {len(df)} bars of history — "
                             f"too few to read a {scope} window."}
        return {**base, "bars_used": bars_used,
                "error": f"No swing structure for {sym} over {scope} "
                         f"— try a longer window."}

    last_price = float(zones["last_price"])
    levels = levels_from_zones(zones, last_price)

    # Fair Value Gaps, the opening range, and the entry/stop each band
    # implies (Ajay 2026-08-29). Every one of these degrades to empty
    # rather than raising: a level surface must keep answering.
    atr_value = pat_mod.atr(closed)
    gaps = pat_mod.fair_value_gaps(closed, last_price)
    # The live frame already holds the minute bars; fetching them again for
    # the opening range doubled provider load on a 30s poll (review
    # 2026-09-02 — the same double-fetch intraday_raw's docstring warns of).
    if ext_frame and live_raw is not None:
        try:
            rth_raw = live_raw[live_raw["session"] == "rth"] if "session" in live_raw.columns else live_raw
            orb = pat_mod.opening_range_from_bars(rth_raw, tf_spec_["orb_minutes"])
        except Exception as exc:                            # pragma: no cover
            log.warning("support: orb from bars failed: %s", exc)
            orb = None
    else:
        orb = pat_mod.opening_range(sym, tf_spec_["orb_minutes"])
    # POSITION is the side, not origin — the same rule levels_from_zones
    # uses: a level below price is bought, one above is sold into,
    # whatever the band used to be.
    zone_bands = (
        [{"kind": "demand", "lo": z.get("lo"), "hi": z.get("hi"),
          "source": "swing", "origin": z.get("origin"),
          "touches": z.get("touches"), "tested": z.get("tested")}
         for z in (levels.get("supports") or [])
         if z.get("lo") and z.get("hi")]
        + [{"kind": "supply", "lo": z.get("lo"), "hi": z.get("hi"),
            "source": "swing", "origin": z.get("origin"),
            "touches": z.get("touches"), "tested": z.get("tested")}
           for z in (levels.get("overhead") or [])
           if z.get("lo") and z.get("hi")])
    traded = pat_mod.attach_levels(zone_bands + gaps, last_price, atr_value)

    # Bullish chart patterns on THIS timeframe (Ajay 2026-08-29: "any other
    # bullish patterns on an hourly chart ... Cup handle or Inverse head and
    # shoulder or Flat top"). Cited shapes keep their citation; every
    # non-daily record is stamped stats_transfer=False.
    # Market mood + buy/sell signal on THIS timeframe (Ajay 2026-08-29:
    # "market sentiment ... to figure out market mood and sentiments for
    # entries. Also give me a buy signal"). Computed on CLOSED bars only —
    # a signal that can change after he acts on it is worse than none.
    try:
        from supply_demand import mood as mood_mod
        # read_budget, never budget: a 5-bar mood would print WAIT where the
        # 1-month read prints BUY, and _record_signal below would then race the
        # per-(symbol, timeframe, bar) dedupe with a contradicting action.
        mood_read = mood_mod.mood(df.tail(read_budget))
        sig = mood_mod.signal(df.tail(read_budget), zone_bands + gaps, mood_read,
                              last_price=last_price, atr_value=atr_value)
        # NOT recorded off a 5-minute frame (`ext_frame`). Before
        # 2026-09-22 the reason was that its signal WAS the daily signal, so
        # recording it would double-count; now it is its own signal and the
        # reason is different but no weaker — `_record_signal`'s horizon
        # table knows 15m and 60m and defaults everything else to 72 hours,
        # which would file a five-minute call under a three-day outcome and
        # quietly corrupt the accuracy ledger. Giving it a horizon is a
        # measured question, not a view change.
        if sig.get("action") in ("BUY", "SELL") and not ext_frame:
            _record_signal(sym, tf_key, sig, last_price)
        # SAID OUT LOUD (2026-09-23). The tab printed "Every BUY/SELL is
        # written to the forward ledger and scored against real prices"
        # unconditionally. On the two 5-minute frames it is not — and until
        # 2026-09-22 that sentence was still true there, because the signal
        # WAS the daily frame's signal. Now it is the frame's own, so the
        # claim has to carry the exception with it.
        sig["recorded"] = not ext_frame
        if ext_frame:
            sig["recorded_note"] = (
                "This chart's BUY/SELL is NOT written to the forward ledger: "
                "the ledger scores an outcome over a per-timeframe horizon and "
                "the 5-minute frames have none, so no hit rate is claimed for "
                "it. The daily, 15-minute and 1-hour charts are recorded.")
    except Exception as exc:                                # pragma: no cover
        log.warning("support: mood/signal for %s failed: %s", sym, exc)
        mood_read, sig = None, None

    # Smart Money Concepts: sweep -> BOS/CHoCH -> order block -> FVG, and
    # the mitigation entry (Ajay 2026-08-29, Brad Goh's five-step model).
    try:
        from supply_demand import smc as smc_mod
        # CLOSED bars (2026-09-14). These read the live-overlaid frame while
        # the zones/ATR/gaps read `closed`, so an unclosed bar's high or low
        # could mint a BOS, a sweep or an order block that vanished at the
        # close — ESI drew "BOS 33.49" that only existed with the live bar.
        smc_setups = smc_mod.find_setups(closed.tail(read_budget), last_price=last_price)
        smc_read = {
            "setups": smc_setups,
            "sweeps": smc_mod.liquidity_sweeps(closed.tail(read_budget))[:4],
            "breaks": smc_mod.structure_breaks(closed.tail(read_budget))[:4],
            "order_blocks": smc_mod.order_blocks(closed.tail(read_budget))[:4],
            "cited": smc_mod.CITED,
            "note": smc_mod.SOURCE_NOTE,
        }
    except Exception as exc:                                # pragma: no cover
        log.warning("support: smc for %s failed: %s", sym, exc)
        smc_read = None

    try:
        from patterns import timeframe as pat_tf
        # Same window the bands were read from — a pattern found in bars the
        # zoom excludes would contradict the levels drawn beside it.
        #
        # THE 5-MINUTE FRAMES STAY ON DAILY BARS HERE (2026-09-22), even
        # though their LEVELS no longer do. `patterns.timeframe` converts
        # Bulkowski's cited calendar durations into bars through
        # BARS_PER_SESSION, and that table knows daily, 60m and 15m only —
        # an unknown key falls through to the DAILY gates, which would find
        # a "7-week cup" inside one session and stamp it with a citation it
        # does not have. Adding a 5-minute row is a cited-duration question,
        # not a view change, so the scan keeps reading the daily frame it
        # read before this change and returns byte-identical records.
        pat_key = tf_key if tf_key in pat_tf.BARS_PER_SESSION else "daily"
        pat_df = (daily_closed if (pat_key == "daily" and intraday
                                   and daily_closed is not None)
                  else closed)
        bullish = pat_tf.scan(sym, pat_key, df=pat_df.tail(read_budget))
    except Exception as exc:                                # pragma: no cover
        log.warning("support: pattern scan for %s failed: %s", sym, exc)
        bullish = None

    # THE BOARD'S BAND, ON EVERY FRAME (2026-09-22). This block is what the
    # alerts, the gate and the paper lanes use, and it is DAILY-derived by
    # construction — `decide_from_frame` at the board's own geometry on the
    # daily closed frame, priced off the daily frame's own last close. It
    # does not follow the chart and never has: before today it appeared on
    # the daily views and on the two 5-minute frames and was simply ABSENT
    # from 15m/60m. Now that every intraday frame reads its own levels, the
    # board reading is the thing that keeps them honest — two readings, each
    # labelled ("BOARD (what alerts and lanes use)" vs this tab's finer
    # bands), never conflated — so it is served on all five.
    board_closed = daily_closed if intraday else closed
    board_px = last_price
    if intraday and daily_df is not None:
        try:
            board_px = float(daily_df["close"].iloc[-1])
        except Exception:                                   # pragma: no cover
            board_px = last_price
    board = (board_read(board_closed, sym, board_px)
             if board_closed is not None and len(board_closed) else None)

    # 〰️ The moving averages need the FULL frame, not the drawn window (Ajay
    # 2026-09-24: "I would need 9EMA and 20 SMA here too as check boxes").
    # On the daily path `bars_for` fills this out-list with the UNTAILED frame,
    # so a 200 SMA under a 1-year chart is still a true 200-bar average and
    # does not move when he changes the Zoom. On an intraday path the widest
    # frame this timeframe has IS `chart_df`, which `frame_for` already sized.
    _ma_frame: list = []
    tile = {
        "symbol": sym,
        "name": board_mod._name_for(sym),
        "href": board_mod._href(sym, "supply"),
        # The chart draws the SAME bars the levels were read from. Ajay
        # 2026-08-29 ("why is one hour showing Monthly?"): board_mod.bars_for
        # ALWAYS loads DAILY candles, so an intraday timeframe computed its
        # levels on 15m/60m bars and then painted them over a year of daily
        # ones — the picture and the numbers were two different charts.
        # A chart-only zoom opts out of bars_for's 20-bar floor by name — it
        # draws exactly the 5 or 10 sessions its label promises. Every other
        # caller keeps BARS_FLOOR.
        # `chart_df`, never `df`: on the named fallback `df` has become the
        # DAILY frame and drawing it here would paint daily candles under a
        # 5-minute label (2026-09-22). `chart_df` is always the frame the
        # timeframe asked for, already tailed to its own budget by
        # `frame_for`, so the tail is a no-op on every non-fallback read.
        "bars": (_frame_bars(short_intraday if short_intraday is not None
                             else chart_df.tail(tf_spec_["bars"])) if intraday
                 else board_mod.bars_for(
                     sym, days=bars_used,
                     min_bars=(bars_used if chart_only
                               else board_mod.BARS_FLOOR),
                     frame_out=_ma_frame)),
        "bands": _bands(levels) + _board_bands(board),
        "lines": _lines(levels, last_price),
        "markers": _touch_markers(levels),
        "stats": _stats(levels, zones, scope_spec) + _board_stats(board),
        "why": _board_why(board) + _why(levels, zones, scope_spec),
        "theme": board_mod._theme(sym),
        "badges": [],
    }
    overlay = _draw_overlay(tile, gaps, smc_read, orb, last_price)
    # 〰️ 9 EMA / 20 SMA / 200 SMA, the same three checkboxes the Chart Maps
    # tiles carry — computed on THIS frame's own bars, so a 20 SMA on the
    # 15-minute chart is twenty 15-minute bars, never twenty days painted over
    # it. The same rule the levels themselves follow on this tab since
    # 2026-09-23. Soft-fails to no lines; it can never empty a tile.
    _attach_ma(tile,
               (chart_df if intraday else
                (_ma_frame[0] if _ma_frame else None)),
               intraday=intraday)
    trend = trend_read(df.tail(read_budget), mood_read)
    # On an intraday timeframe the Zoom dropdown's DAILY bar-counts do not
    # apply, and leaving "1 month" sitting over a 15-minute chart is what
    # made the tab look wrong. State the real span instead.
    # THE INTRADAY ARM GOES FIRST (fixed before ship, 2026-09-18, and it
    # still matters). Both params are independent in the URL and the API
    # advertises 1w/2w, so `?window=1w&tf=24h` is reachable by bookmark even
    # though the dropdown always writes the pair; with the chart-only arm
    # first it announced "last 300 sessions" over a FIVE-MINUTE chart.
    #
    # ONE SENTENCE, TWO CLAUSES, ON EVERY FRAME (2026-09-22). Ajay: "why do
    # I need the look at the drop down" — the header has to answer what is
    # DRAWN and where the LEVELS came from without him opening anything, and
    # the two are no longer the same thing on any frame by accident. The old
    # shape had four arms and said nothing about provenance on 15m/60m.
    chart_part = (
        f"{len(tile['bars'])} x {tf_spec_['bar_label']} bars over "
        f"{short_sessions} session{'' if short_sessions == 1 else 's'}"
        if short_intraday is not None else
        f"{len(tile['bars'])} x {tf_spec_['bar_label']} bars · "
        f"{tf_window_label}"
        if intraday else
        f"last {len(tile['bars'])} sessions"
        if chart_only else spec["label"])
    # Three cases, and the middle one is why this is not a one-liner: the
    # levels came from the frame being drawn (any intraday frame now, and a
    # daily frame at its own zoom), or from a DIFFERENT daily window — a
    # chart-only zoom, or the named fallback. Only the third names a window;
    # the first two say "these bars", because naming "1 year of daily bars"
    # under a 1-year daily chart is noise, and naming any daily window under
    # an intraday chart would be a lie.
    redirected = bool(chart_only or levels_fallback)
    levels_part = (f"{level_spec['label']} of daily bars" if redirected else
                   f"these {tf_spec_['bar_label']} bars")
    chart_span = f"{chart_part} · levels from {levels_part}"
    if levels_fallback:
        chart_span += (f" (the {tf_spec_['bar_label']} window held no level)")

    return {
        **base,
        "name": tile["name"],
        "last_price": last_price,
        "bars_used": bars_used,
        # The chart-only arm FIRST: both can be true on a 3-bar symbol, and
        # the shortfall behind the NUMBERS is the larger claim. Without it a
        # 13-bar symbol warned at window=1m and went silent at window=1w,
        # which is backwards.
        "short_history": ({"have": len(df), "asked": read_budget}
                          if (chart_only and level_short)
                          else {"have": bars_used, "asked": budget}
                          if short else None),
        "tile": tile,
        **levels,
        "verdict": zones.get("verdict"),
        "params": zones.get("params"),
        "atr": round(atr_value, 4) if atr_value else None,
        "fair_value_gaps": gaps,
        "opening_range": orb,
        "trade_levels": traded,
        "bullish_patterns": bullish,
        "mood": mood_read,
        "signal": sig,
        "smc": smc_read,
        "trend_read": trend,
        "overlay": overlay,
        "board": board,
        "chart_span": chart_span,
        # WHERE THE NUMBERS CAME FROM, as a noun phrase (2026-09-23). The
        # empty level tables used to name `window_label` — the pinned DAILY
        # zoom — so an entry frame with no support below price asserted "No
        # band below price in the last 6 months" while the same page printed
        # the board's 6-month demand band a few lines above it. This is the
        # SAME string `_stats`/`_why` already label the read with, so the
        # table and the stats row cannot drift apart.
        "levels_scope": scope_spec["label"],
        # The BAR SIZE the level read ran on — "5-minute" on an own-bars
        # intraday frame, "daily" on the daily frame AND on the named
        # fallback (where `own_bars` is False again by then). The recency
        # column counts BARS, so without this the tab printed one 5-minute
        # bar as "tested yesterday".
        "levels_bar_label": (tf_spec_["bar_label"] if own_bars
                             else tf_mod.tf_spec(tf_mod.DAILY)["bar_label"]),
        # Which window the NUMBERS came from. None on every ordinary window,
        # so an FE that predates 2026-09-18 simply ignores both keys.
        # Set whenever the DRAWN frame and the READ frame are not the same
        # thing, so the tab can say so out loud. That was only ever the daily
        # chart-only zooms; 1W/2W on an intraday frame is the same divergence
        # (34 bars drawn, 330 read) and went SILENT on it — the one view where
        # naming the provenance matters most. Points at the TIMEFRAME here, not
        # at a daily window: these levels were never redirected to 1 month.
        # `levels_window` keeps its ORIGINAL narrow meaning — which DAILY
        # window the levels were REDIRECTED to — and stays None on an own-bars
        # frame, where no redirect happened. Overloading it with a timeframe
        # key would break every reader that treats it as a window key.
        "levels_window": level_spec["key"] if chart_only else None,
        # The LABEL is wider on purpose: it answers "where did these numbers
        # come from", which the tab prints verbatim, and that question has an
        # answer on an own-bars short zoom too (34 bars drawn, 330 read). It
        # names the TIMEFRAME there, never a daily window — these levels were
        # not redirected to 1 month and must not claim to be. The asymmetry is
        # deliberate: the FE gates the sentence on the label, not the key.
        "levels_window_label": (
            level_spec["label"] if chart_only or levels_fallback else
            f"{tf_spec_['label']} · {tf_spec_['span']}"
            if (own_bars and short_intraday is not None) else None),
        # THE NAMED FALLBACK (2026-09-22), or null. `{from, from_bars, to,
        # note}` — the one case where an intraday frame is NOT showing its
        # own levels. `note` below carries the same sentence first so the
        # surface says it whether or not the FE knows this key.
        "levels_fallback": levels_fallback,
        # True when the daily zoom actually reached the chart. Since
        # 2026-09-18 that includes an intraday frame trimmed by a short window;
        # since 2026-09-22 it also includes the fallback, where the daily
        # window really is what produced the numbers.
        "zoom_applies": ((not intraday) or short_intraday is not None
                         or bool(levels_fallback)),
        # How many ET sessions the drawn intraday frame actually holds — null
        # when the window did not trim it. Never more than the frame contains.
        "chart_sessions": short_sessions or None,
        # Live chart (Ajay 2026-09-02): poll cadence + the overnight read.
        # Both None off the live frame so nothing else on the tab changes.
        "live": tf_mod.live_state() if ext_frame else None,
        "overnight": (overnight_read(chart_df, levels.get("supports") or [],
                                     levels.get("overhead") or [])
                      if ext_frame else None),
        # Same fix: the sentence describes a DAILY frame of spec['bars']
        # sessions, which an intraday frame is not.
        "note": (
                 # THE FALLBACK SENTENCE GOES FIRST (2026-09-22) and is not
                 # optional. An intraday frame that could not find a level in
                 # its own window is showing DAILY bands over 5-minute
                 # candles, which is precisely the state that made this tab
                 # "useless at any given point" — the difference is that now
                 # it is announced in the first clause a reader meets.
                 ((levels_fallback["note"] + " ") if levels_fallback else "")
                 # THE OWN-BARS SHORT ZOOM (Ajay 2026-09-18, second ship).
                 # 1W/2W on an intraday frame takes NEITHER of the two arms
                 # below: own_bars makes chart_only False, so the generic arm
                 # fired and said "Levels are read from this window only" under
                 # a chart labelled one week. That was false in the direction
                 # that matters — the levels are the timeframe's own ~47-session
                 # budget (measured: 1w+60m and 6m+60m return identical
                 # supports, overhead and verdict at bars_used 330), not a week
                 # of anything. It must not borrow the daily arm's wording
                 # either: nothing here is redirected to a 1-month daily read.
                 + (f"The chart is the last {short_sessions} "
                 f"session{'' if short_sessions == 1 else 's'} of "
                 f"{tf_spec_['bar_label']} bars. Every number beside it — "
                 f"levels, mood, signal, trend, patterns — is the "
                 f"{tf_spec_['bar_label']} frame's own {read_budget}-bar "
                 f"read, the same numbers every other {tf_spec_['bar_label']} "
                 f"zoom shows. "
                 if (own_bars and short_intraday is not None) else
                 f"This zoom sets the CHART only — the last {spec['bars']} "
                  f"sessions. A frame that short is under the "
                  f"{pz.MIN_BARS_ABS}-bar floor a swing needs, so every number "
                  f"here — levels, mood, signal, trend, patterns — is the "
                  f"{level_spec['label']} read, the same numbers the "
                  f"{level_spec['label']} zoom shows. "
                  if (chart_only and not intraday) else
                  f"The chart is the {tf_spec_['bar_label']} frame; the short "
                  f"zoom sets no daily span here. Every number is the "
                  f"{level_spec['label']} read. "
                  if chart_only else
                  # AN INTRADAY FRAME READS ITS OWN LEVELS (2026-09-22). The
                  # generic arm used to say "this window", which on a daily
                  # view means the Zoom and on an intraday view means the
                  # frame — two different things wearing one sentence.
                  f"Levels are read from this chart's own "
                  f"{tf_spec_['bar_label']} bars — {tf_window_label}. "
                  f"The Zoom dropdown does not move them. "
                  if own_bars else
                  "Levels are read from this window only. A wider zoom finds the "
                  "structural floor; a tighter one finds the level this week's "
                  "trade is standing on. ") + (BOARD_NOTE if board else "")).strip(),
    }
