"""IPO-age filter — young companies preferred (TLSW Ch. 11).

"Eighty percent of the stock market winners that drove the tech boom during
the 1990s were IPOs within the prior eight years" (TLSW p. 260). The book
wants YOUTH with character.

Output:
  - first_trade_date: listing date, or None when we cannot know it
  - years_since_ipo:  float, or None
  - is_young:         ≤8 years, or None
  - is_recent_ipo:    ≤2 years (still in primary-base territory), or None
  - source:           "history" | "profile" | None

Data trust (2026-08-31): every price fetch has a hard lookback cap
(prices.PERIOD_DAYS — even "max" stops at 3650 days) and the price cache is
keyed by symbol only, so this module receives whatever window the last
caller fetched — in practice the scan's 2y frame, regardless of the period
we ask for here. A first bar sitting at the frame's own start is history
truncation, not a listing: SAIC reported first_trade_date=2024-09-03 /
is_recent_ipo=true while the company listed 2013-09-16. So the first bar is
only read as a listing date when its age lands clear of every known fetch
cap; at a cap boundary we ask the profile provider (Finnhub profile2 `ipo`,
cached in Mongo — listing dates are immutable) and return all-None when it
cannot say. A recent-IPO claim from bars alone is additionally confirmed
against the profile, so a frame that merely *starts* late (provider
coverage gap, unstitched rename) cannot mint one on its own.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional

import pandas as pd

from . import symbols
from .prices import PERIOD_DAYS, load_prices
from .providers import FINNHUB_API_KEY

log = logging.getLogger("cheetah.sepa.ipo_age")

# A first bar whose age is within this many calendar days of a fetch cap is
# indistinguishable from truncation (the cap's from-date can land on a
# weekend/holiday cluster, so the first BAR prints a few sessions late).
_CAP_GUARD_DAYS = 10

# A cached "profile has no listing date" answer is retried after a week.
_MISS_TTL_SEC = 7 * 24 * 3600

_UNKNOWN = {
    "first_trade_date": None,
    "years_since_ipo": None,
    "is_young": None,
    "is_recent_ipo": None,
    "source": None,
}


def _at_fetch_cap(span_days: float) -> bool:
    """True when a first-bar age coincides with any known fetch-window cap."""
    return any(
        cap - _CAP_GUARD_DAYS <= span_days <= cap + _CAP_GUARD_DAYS
        for cap in PERIOD_DAYS.values()
    )


def _ipo_coll():
    """Sibling Mongo collection to the price cache; None when Mongo is down."""
    try:
        from .prices import _get_mongo
        price_coll = _get_mongo()
        if price_coll is None:
            return None
        return price_coll.database["ipo_dates"]
    except Exception:
        return None


def _profile_ipo_date(symbol: str) -> Optional[str]:
    """Real listing date from the profile provider (Finnhub profile2 `ipo`).

    Successes cache in Mongo forever — listing dates are immutable. A clean
    200 with no date caches as a miss for a week. Transport errors and
    rate-limits cache nothing, so the next call simply retries.
    """
    sym = symbols.resolve((symbol or "").strip().upper())
    coll = _ipo_coll()
    if coll is not None:
        try:
            doc = coll.find_one({"_id": sym})
        except Exception:
            doc = None
        if doc:
            if doc.get("ipo"):
                return doc["ipo"]
            if time.time() - (doc.get("cached_at") or 0) < _MISS_TTL_SEC:
                return None

    if not FINNHUB_API_KEY:
        return None
    try:
        import requests
        r = requests.get(
            "https://finnhub.io/api/v1/stock/profile2",
            params={"symbol": sym, "token": FINNHUB_API_KEY},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        ipo = (r.json() or {}).get("ipo") or None
    except Exception as exc:
        log.debug("profile ipo fetch failed for %s: %s", sym, exc)
        return None

    if ipo:
        try:
            datetime.strptime(ipo, "%Y-%m-%d")
        except (ValueError, TypeError):
            ipo = None
    if coll is not None:
        try:
            coll.replace_one(
                {"_id": sym},
                {"_id": sym, "ipo": ipo, "cached_at": time.time()},
                upsert=True,
            )
        except Exception:
            pass
    return ipo


def _block(first_trade_date: str, years: float, source: str) -> dict:
    return {
        "first_trade_date": first_trade_date,
        "years_since_ipo": round(years, 2),
        "is_young": years <= 8,
        "is_recent_ipo": years <= 2,
        "source": source,
    }


def listing_dates_map(symbols) -> dict:
    """{SYM: "YYYY-MM-DD"} for a list of names — ONE cached Mongo read.

    The board path's reader. `listing_date()` can fall through to Finnhub on a
    miss and `age()` loads price history; neither may run per-symbol on a page
    render, so this reads `ipo_dates` and nothing else. Symbols are resolved
    through `symbols.resolve` exactly as `_profile_ipo_date` does, and the map
    is keyed by BOTH the caller's spelling and the resolved one so a renamed
    ticker answers either way. A doc with `ipo` None (a cached miss) is
    omitted — absent means unknown, never "not young".

    The dates are Finnhub PROFILE dates and are uncorroborated: 21.4% of them
    on this universe belong to a recycled ticker (see chart_maps/ipo.py:20-27),
    which reads as a RECENT date for an OLD company. Any caller rendering this
    must label it.
    """
    from . import symbols as S      # the module — `symbols` is the parameter
    wanted: dict = {}
    for s in symbols or []:
        s = str(s or "").strip().upper()
        if not s:
            continue
        wanted.setdefault(S.resolve(s), set()).add(s)
    coll = _ipo_coll()
    if coll is None or not wanted:
        return {}
    out: dict = {}
    try:
        for doc in coll.find({"_id": {"$in": sorted(wanted)},
                              "ipo": {"$ne": None}}):
            ipo = doc.get("ipo")
            if not ipo:
                continue
            rid = str(doc.get("_id") or "").upper()
            for alias in wanted.get(rid, set()) | {rid}:
                out[alias] = ipo
    except Exception as exc:
        log.debug("listing_dates_map read failed: %s", exc)
        return {}
    return out


def listing_date(symbol: str) -> Optional[str]:
    """The real listing date (YYYY-MM-DD) from the profile provider, or None —
    the cheap, cached half of `age()` for callers that only need the date
    (the Russell watch's IPO-window test) and must not load price history."""
    try:
        return _profile_ipo_date(symbol)
    except Exception:
        return None


def age(symbol: str) -> Optional[dict]:
    df = load_prices(symbol, period="max")
    if df is None or df.empty:
        return None
    first = df.index[0]
    # tz-naive comparison
    if hasattr(first, "tz_localize"):
        try:
            first = first.tz_localize(None)
        except Exception:
            pass
    now = datetime.utcnow()
    first_dt = pd.Timestamp(first).to_pydatetime().replace(tzinfo=None)
    span_days = (now - first_dt).days

    if not _at_fetch_cap(span_days):
        years = span_days / 365.25
        if years > 2:
            return _block(pd.Timestamp(first).strftime("%Y-%m-%d"), years, "history")
        # Bars alone don't get to claim a recent IPO — confirm with the
        # profile provider, which wins when it knows better (e.g. a frame
        # that starts late for reasons other than a listing).
        listed = _profile_ipo_date(symbol)
        if not listed:
            return _block(pd.Timestamp(first).strftime("%Y-%m-%d"), years, "history")
    else:
        listed = _profile_ipo_date(symbol)
        if not listed:
            return dict(_UNKNOWN)

    listed_dt = datetime.strptime(listed, "%Y-%m-%d")
    if listed_dt > now:
        return dict(_UNKNOWN)
    years = (now - listed_dt).days / 365.25
    return _block(listed, years, "profile")
