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

from supply_demand import price_zones as pz

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
# returned lists at MAX_ZONES_PER_SIDE (4) per ORIGIN, so the practical ceiling
# below price is 8 (4 demand + 4 broken supply). Stated in the payload as
# `levels_capped` so a short list never reads as "that is all there is".
MAX_LEVELS = 6

DISCLAIMER = pz.DISCLAIMER


def window_keys() -> list[str]:
    return [w["key"] for w in SUPPORT_WINDOWS]


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


def for_symbol(symbol: str, window: str = DEFAULT_WINDOW) -> dict:
    """Support levels for one ticker at one zoom.

    Always answers a dict. A bad symbol, a thin frame or a structureless window
    come back as `{'error': …}` with the dropdown still populated, because the
    tab has to keep rendering its controls after a miss — the user's next move
    is to change the zoom or the ticker.
    """
    sym = (symbol if isinstance(symbol, str) else "").upper().strip()
    spec = window_spec(window)
    base = {
        "symbol": sym,
        "window": spec["key"],
        "window_label": spec["label"],
        "windows": [{"key": w["key"], "label": w["label"], "bars": w["bars"]}
                    for w in SUPPORT_WINDOWS],
        "recent_bars": RECENT_BARS,
        "disclaimer": DISCLAIMER,
    }
    if not sym:
        return {**base, "error": "Type a ticker to see its support levels."}

    try:
        from sepa import prices
        df = prices.load_prices(sym, period="2y")
    except Exception as exc:                                  # pragma: no cover
        log.debug("support: prices %s failed: %s", sym, exc)
        return {**base, "error": f"No price data for {sym}."}

    if df is None or not len(df):
        return {**base, "error": f"No price data for {sym}."}

    # A frame SHORTER than the window asked for still computes — `.iloc[-126:]`
    # on 30 bars is 30 bars — and would then be labelled "6 months" on screen.
    # A recent IPO is the ordinary case, and refusing it is worse than answering
    # it, so the truncation is reported rather than hidden or fatal.
    bars_used = min(len(df), spec["bars"])
    short = bars_used < spec["bars"]

    zones = pz.compute(df,
                       swing_window=spec["swing_window"],
                       lookback_bars=spec["bars"])
    if zones is None:
        # Two different misses with two different fixes, so two messages. The
        # fix for the second one is the dropdown sitting right there.
        if short:
            return {**base, "bars_used": bars_used,
                    "error": f"{sym} has only {bars_used} bars of history — "
                             f"too few to read a {spec['label']} window."}
        return {**base, "bars_used": bars_used,
                "error": f"No swing structure for {sym} over {spec['label']} "
                         f"— try a longer window."}

    last_price = float(zones["last_price"])
    levels = levels_from_zones(zones, last_price)

    tile = {
        "symbol": sym,
        "name": board_mod._name_for(sym),
        "href": board_mod._href(sym, "supply"),
        # The chart shows EXACTLY the analysed window. Drawing more would put
        # bars on screen that had no vote in the bands; drawing fewer would
        # hide a band's own defining touches, which is the failure
        # `oldest_touch_bars` was added to catch (price_zones, 2026-08-16).
        "bars": board_mod.bars_for(sym, days=bars_used),
        "bands": _bands(levels),
        "lines": _lines(levels, last_price),
        "markers": [],
        "stats": _stats(levels, zones, spec),
        "why": _why(levels, zones, spec),
        "theme": board_mod._theme(sym),
        "badges": [],
    }

    return {
        **base,
        "name": tile["name"],
        "last_price": last_price,
        "bars_used": bars_used,
        # Set when the frame could not cover the window. The label still says
        # what was ASKED for; this says what was actually read.
        "short_history": ({"have": bars_used, "asked": spec["bars"]}
                          if short else None),
        "tile": tile,
        **levels,
        "verdict": zones.get("verdict"),
        "params": zones.get("params"),
        "note": ("Levels are read from this window only. A wider zoom finds the "
                 "structural floor; a tighter one finds the level this week's "
                 "trade is standing on."),
    }
