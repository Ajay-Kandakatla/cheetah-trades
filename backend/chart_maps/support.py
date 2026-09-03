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
    {"key": "1m", "label": "1 month",  "bars": 21,  "swing_window": 2},
    {"key": "3m", "label": "3 months", "bars": 63,  "swing_window": 3},
    {"key": "6m", "label": "6 months", "bars": 126, "swing_window": 4},
    {"key": "1y", "label": "1 year",   "bars": 252, "swing_window": 4},
    # Ajay 2026-08-25: "select support level ... by up to 5 years". Wider
    # swing window on purpose — at this zoom only structural pivots matter;
    # a 2-bar swing five years ago is noise, not a level.
    {"key": "5y", "label": "5 years",  "bars": 1260, "swing_window": 5},
)

# 3 months is the middle of what was asked for and the horizon a swing stop
# actually lives on. Not 1y: that is what every other surface already answers,
# so opening on it would make the tab look like a duplicate of /zones.
DEFAULT_WINDOW = "3m"

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


def _overlay_today(prices_mod, df, sym: str):
    """(frame, as_of_epoch | None) via prices.with_today_bar — tolerant of
    stubs without it and of any failure; the closed frame always stands."""
    fn = getattr(prices_mod, "with_today_bar", None)
    if fn is None or df is None:
        return df, None
    try:
        out, info = fn(df, sym)
    except Exception as exc:                                   # pragma: no cover
        log.debug("support: today-bar overlay failed for %s: %s", sym, exc)
        return df, None
    return out, ((info or {}).get("as_of_epoch") if (info or {}).get("appended") else None)


def _frame_for(sym: str, need_bars: int):
    """(df, bars_available, as_of_epoch) — the shared 2y frame, or a deep 5y
    fetch when the window needs more than the shared frame holds. Degrades to
    the shared frame on a failed deep fetch — the caller reports the
    shortfall rather than silently drawing a 2-year chart under a 5-year
    label. `as_of_epoch` is when the data left the PROVIDER (shared frame:
    parquet mtime; deep frame: its fetch time), or None — never now()."""
    import time as _t
    from sepa import prices

    try:
        df = prices.load_prices(sym, period="2y")
    except Exception:                                          # pragma: no cover
        df = None
    # Today's live bar on top of the closed frame (Ajay 2026-09-03, CHPT: the
    # tab said "1.4% below support" off yesterday's 5.19 while the tape was
    # 9.14). as_of becomes the snapshot's last-trade time when it appended.
    df, live_as_of = _overlay_today(prices, df, sym)
    have = len(df) if df is not None else 0
    if need_bars <= have:
        return df, have, (live_as_of or _shared_frame_as_of(sym))

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
        if deep is not None and len(deep):
            deep_as_of = _t.time()
            _deep_cache[key] = (deep_as_of, deep)
    if deep is not None and len(deep) > have:
        deep, deep_live_as_of = _overlay_today(prices, deep, sym)
        return deep, len(deep), (deep_live_as_of or deep_as_of)
    return df, have, _shared_frame_as_of(sym)


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
    return SUPPORT_WINDOWS[1]                       # unreachable; keeps mypy calm


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

    df, have, as_of = _frame_for(sym, max(w["bars"] for w in SUPPORT_WINDOWS))
    if df is None or not len(df):
        return {**base, "error": f"No price data for {sym}."}
    base = {**base, "as_of": as_of, "data_through": _last_bar_date(df)}

    tagged: list[dict] = []
    per_window: list[dict] = []
    last_price = None
    for w in SUPPORT_WINDOWS:
        z = pz.compute(df, swing_window=w["swing_window"], lookback_bars=w["bars"],
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


def _bands(levels: dict) -> list[dict]:
    """Chart boxes for the tile. Supports drawn as demand, overhead as supply —
    the tile contract's existing two colours, so `PatternChart` needs no new
    case. Capped at three a side: a chart with eight boxes is a solid block."""
    out: list[dict] = []
    inside = levels.get("standing_in")
    if inside:
        out.append({"kind": "demand", "lo": inside["lo"], "hi": inside["hi"],
                    "label": "here"})
    for lv in (levels.get("supports") or [])[:3]:
        out.append({"kind": "demand", "lo": lv["lo"], "hi": lv["hi"]})
    for lv in (levels.get("overhead") or [])[:3]:
        out.append({"kind": "supply", "lo": lv["lo"], "hi": lv["hi"]})
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


def _why(levels: dict, zones: dict, spec: dict) -> str:
    verdict = (zones.get("verdict") or {})
    sup = (levels.get("supports") or [None])[0]
    head = verdict.get("label") or ""
    if sup and sup["distance_pct"] is not None:
        when = ("tested in the last month" if sup["recent"]
                else f"last tested {sup['bars_since_test']} bars ago")
        weak = ("" if sup["tested"] else
                " Single swing low, not a tested floor.")
        return (f"{head} Nearest support over {spec['label']}: "
                f"${sup['lo']}–${sup['hi']}, {sup['distance_pct']}% below, "
                f"{sup['touches']}× touched, {when}.{weak}")
    return head or f"No band below price in the last {spec['label']}."


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
                "t": _et(ts).strftime("%Y-%m-%d %H:%M"),
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
        "timeframes": tf_mod.tf_options(include_live=True),
        "disclaimer": DISCLAIMER,
    }
    if not sym:
        return {**base, "error": "Type a ticker to see its support levels."}
    if overlay:
        return overlay_for_symbol(sym, base)

    tf_key = tf_mod.parse_tf(tf)
    intraday = tf_key != tf_mod.DAILY
    live_raw = None
    try:
        if intraday:
            # allow_ext: this tab draws the pre/post-market bars but reads
            # its LEVELS from the daily window below — the only place the
            # extended frame is legitimate.
            live_raw = (tf_mod.intraday_raw(sym, tf_key)
                        if tf_mod.tf_spec(tf_key).get("ext_hours") else None)
            df, tf_meta = tf_mod.frame_for(sym, tf_key, allow_ext=True,
                                           raw=live_raw)
            as_of = tf_meta.get("as_of")
            base = {**base, "timeframe_meta": tf_meta}
            if df is None:
                return {**base, "error": (
                    f"No {tf_meta['label']} bars for {sym} — "
                    f"{tf_meta.get('reason') or 'intraday data unavailable'}.")}
        else:
            df, _have, as_of = _frame_for(sym, spec["bars"])
    except Exception as exc:                                  # pragma: no cover
        log.debug("support: prices %s failed: %s", sym, exc)
        return {**base, "error": f"No price data for {sym}."}

    if df is None or not len(df):
        return {**base, "error": f"No price data for {sym}."}
    base = {**base, "as_of": as_of,
            "data_through": _last_bar_date(df, intraday=intraday)}

    # Live / extended-hours frame (Ajay 2026-09-02: "I wanna see where things
    # bounced over night"). The CHART draws every 5-minute bar incl. pre/post
    # market; the LEVELS come from the DAILY frame at the selected window —
    # the same numbers the daily views print — so an overnight touch is
    # measured against the zones he already knows, not against 2.5 sessions
    # of intraday swings (which, after a gap, may hold no level at all).
    # `chart_df` is what is drawn; `df` from here on is what is analysed.
    chart_df = df
    ext_frame = bool(intraday and tf_mod.tf_spec(tf_key).get("ext_hours"))
    if ext_frame:
        try:
            daily_df, _have_d, levels_as_of = _frame_for(sym, spec["bars"])
        except Exception as exc:                              # pragma: no cover
            log.debug("support: daily frame for live %s failed: %s", sym, exc)
            daily_df, levels_as_of = None, None
        if daily_df is None or not len(daily_df):
            return {**base, "error": f"No daily price data for {sym} to read levels from."}
        df = daily_df
        base = {**base, "levels_as_of": levels_as_of}

    # A frame SHORTER than the window asked for still computes — `.iloc[-126:]`
    # on 30 bars is 30 bars — and would then be labelled "6 months" on screen.
    # A recent IPO is the ordinary case, and refusing it is worse than answering
    # it, so the truncation is reported rather than hidden or fatal.
    tf_spec_ = tf_mod.tf_spec(tf_key)
    # The live frame analyses DAILY bars at the window, so it budgets like
    # the daily views; the other intraday frames budget from their own spec.
    own_bars = intraday and not ext_frame
    budget = tf_spec_["bars"] if own_bars else spec["bars"]
    swing = tf_spec_["swing_window"] if own_bars else spec["swing_window"]
    bars_used = min(len(df), budget)
    short = bars_used < budget

    zones = pz.compute(df, swing_window=swing, lookback_bars=budget, max_zones=None)
    if zones is None:
        # Two different misses with two different fixes, so two messages. The
        # fix for the second one is the dropdown sitting right there.
        scope = tf_spec_["label"] if own_bars else spec["label"]
        if short:
            return {**base, "bars_used": bars_used,
                    "error": f"{sym} has only {bars_used} bars of history — "
                             f"too few to read a {scope} window."}
        return {**base, "bars_used": bars_used,
                "error": f"No swing structure for {sym} over {scope} "
                         f"— try a longer window."}

    last_price = float(zones["last_price"])
    levels = levels_from_zones(zones, last_price)

    # Fair Value Gaps, the opening range, and the entry/stop each band
    # implies (Ajay 2026-08-29). Every one of these degrades to empty
    # rather than raising: a level surface must keep answering.
    atr_value = pat_mod.atr(df)
    gaps = pat_mod.fair_value_gaps(df, last_price)
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
        mood_read = mood_mod.mood(df.tail(budget))
        sig = mood_mod.signal(df.tail(budget), zone_bands + gaps, mood_read,
                              last_price=last_price, atr_value=atr_value)
        # The live frame's signal IS the daily signal — recording it again
        # under a second key would double-count the ledger.
        if sig.get("action") in ("BUY", "SELL") and not ext_frame:
            _record_signal(sym, tf_key, sig, last_price)
    except Exception as exc:                                # pragma: no cover
        log.warning("support: mood/signal for %s failed: %s", sym, exc)
        mood_read, sig = None, None

    # Smart Money Concepts: sweep -> BOS/CHoCH -> order block -> FVG, and
    # the mitigation entry (Ajay 2026-08-29, Brad Goh's five-step model).
    try:
        from supply_demand import smc as smc_mod
        smc_setups = smc_mod.find_setups(df.tail(budget), last_price=last_price)
        smc_read = {
            "setups": smc_setups,
            "sweeps": smc_mod.liquidity_sweeps(df.tail(budget))[:4],
            "breaks": smc_mod.structure_breaks(df.tail(budget))[:4],
            "order_blocks": smc_mod.order_blocks(df.tail(budget))[:4],
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
        bullish = pat_tf.scan(sym, "daily" if ext_frame else tf_key,
                              df=df.tail(budget))
    except Exception as exc:                                # pragma: no cover
        log.warning("support: pattern scan for %s failed: %s", sym, exc)
        bullish = None

    tile = {
        "symbol": sym,
        "name": board_mod._name_for(sym),
        "href": board_mod._href(sym, "supply"),
        # The chart draws the SAME bars the levels were read from. Ajay
        # 2026-08-29 ("why is one hour showing Monthly?"): board_mod.bars_for
        # ALWAYS loads DAILY candles, so an intraday timeframe computed its
        # levels on 15m/60m bars and then painted them over a year of daily
        # ones — the picture and the numbers were two different charts.
        "bars": (_frame_bars(chart_df.tail(tf_spec_["bars"]) if ext_frame
                             else df.tail(bars_used)) if intraday
                 else board_mod.bars_for(sym, days=bars_used)),
        "bands": _bands(levels),
        "lines": _lines(levels, last_price),
        "markers": [],
        "stats": _stats(levels, zones, spec),
        "why": _why(levels, zones, spec),
        "theme": board_mod._theme(sym),
        "badges": [],
    }
    overlay = _draw_overlay(tile, gaps, smc_read, orb, last_price)
    trend = trend_read(df.tail(budget), mood_read)
    # On an intraday timeframe the Zoom dropdown's DAILY bar-counts do not
    # apply, and leaving "1 month" sitting over a 15-minute chart is what
    # made the tab look wrong. State the real span instead.
    chart_span = (f"{len(tile['bars'])} x 5-min bars incl. pre/post market · "
                  f"levels from {spec['label']} of daily bars"
                  if ext_frame else
                  f"{len(tile['bars'])} x {tf_spec_['label']} bars"
                  if intraday else spec["label"])

    return {
        **base,
        "name": tile["name"],
        "last_price": last_price,
        "bars_used": bars_used,
        "short_history": ({"have": bars_used, "asked": budget}
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
        "chart_span": chart_span,
        "zoom_applies": not intraday,
        # Live chart (Ajay 2026-09-02): poll cadence + the overnight read.
        # Both None off the live frame so nothing else on the tab changes.
        "live": tf_mod.live_state() if ext_frame else None,
        "overnight": (overnight_read(chart_df, levels.get("supports") or [],
                                     levels.get("overhead") or [])
                      if ext_frame else None),
        "note": ("Levels are read from this window only. A wider zoom finds the "
                 "structural floor; a tighter one finds the level this week's "
                 "trade is standing on."),
    }
