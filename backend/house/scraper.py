"""Best-effort scrape of Redfin / Zillow / Realtor.com listing pages.

These are *unofficial* — Redfin has no public API for view/save counts;
the numbers are extracted from the embedded JSON in the page HTML. They
break when the platforms redesign. Treat as flaky bonus data; the user
can always enter numbers manually via /house/snapshot.

Usage:
  metrics = scrape_all(
      redfin_url="https://www.redfin.com/TX/...",
      zillow_url="https://www.zillow.com/homedetails/...",
      realtor_url="https://www.realtor.com/...",
  )

Returns dict with whichever fields each scraper could extract; missing
fields stay absent so the upsert merge works correctly.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

log = logging.getLogger("house.scraper")

# Platform-realistic UA so we don't get blocked by basic bot filters.
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
TIMEOUT = 12


def _fetch(url: str) -> Optional[str]:
    if not url:
        return None
    try:
        import requests
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            log.warning("scraper: %s returned %d", url[:80], r.status_code)
            return None
        return r.text
    except Exception as exc:
        log.warning("scraper: fetch failed %s: %s", url[:80], exc)
        return None


# ---------------------------------------------------------------------------
# Redfin — view count + save count + tour requests
# ---------------------------------------------------------------------------
def scrape_redfin(url: Optional[str]) -> dict:
    """Pull view/save/tour counts from a Redfin listing page.

    Redfin embeds a JSON blob in <script id="__NEXT_DATA__"> with
    `pageViewCount`, `favoritesCount`, and tour info. Field names
    drift across page redesigns so we look for several patterns.

    The current "Powered by Rocket" Redfin layout uses a different
    `__INITIAL_STATE__` blob with keys like `viewCount`, `dailyViewCount`,
    `propertyHistoryStats.viewCount`, `activityInfo.recentViewCount`.
    """
    out: dict = {}
    html = _fetch(url) if url else None
    if not html:
        return out

    # Bot-wall detection — if Redfin served a CAPTCHA, no point parsing.
    low = html.lower()
    if "press & hold" in low or "perimeterx" in low or "px-captcha" in low:
        out["_blocked"] = "redfin (bot wall)"
        return out

    # Pattern 1: __NEXT_DATA__ blob OR __INITIAL_STATE__ (post-Rocket rebrand)
    blobs = re.findall(
        r'<script[^>]+id="(?:__NEXT_DATA__|__INITIAL_STATE__)"[^>]*>(.*?)</script>',
        html, re.S,
    )
    for blob in blobs:
        try:
            data = json.loads(blob)
            views = _deep_find(data, (
                "pageViewCount", "viewCount", "views",
                "dailyViewCount", "recentViewCount", "totalViewCount",
            ))
            saves = _deep_find(data, (
                "favoritesCount", "favoriteCount", "saves",
                "favoriters", "savedCount",
            ))
            tours = _deep_find(data, (
                "tourCount", "scheduledTourCount", "tourRequestCount",
                "recentTourCount", "tours",
            ))
            if views is not None and "redfin_views" not in out:
                try: out["redfin_views"] = int(views)
                except Exception: pass
            if saves is not None and "redfin_saves" not in out:
                try: out["redfin_saves"] = int(saves)
                except Exception: pass
            if tours is not None and "redfin_tours" not in out:
                try: out["redfin_tours"] = int(tours)
                except Exception: pass
        except Exception as exc:
            log.debug("redfin blob parse failed: %s", exc)

    # Pattern 2 (fallback): inline strings the page renders even when JSON
    # field names change. Cover several phrasings Redfin has used.
    if "redfin_views" not in out:
        for pat in (
            r'(\d[\d,]*)\s*(?:people\s+)?(?:have\s+)?viewed',
            r'(\d[\d,]*)\s*views?\s+(?:in\s+)?(?:the\s+)?(?:last|past)',
            r'"viewCount"\s*:\s*(\d+)',
            r'"dailyViews?"\s*:\s*(\d+)',
        ):
            m = re.search(pat, html, re.I)
            if m:
                try: out["redfin_views"] = int(m.group(1).replace(",", "")); break
                except Exception: pass
    if "redfin_saves" not in out:
        for pat in (
            r'(\d[\d,]*)\s*(?:saves?|favorites?)\b',
            r'"favoritesCount"\s*:\s*(\d+)',
            r'"savedCount"\s*:\s*(\d+)',
        ):
            m = re.search(pat, html, re.I)
            if m:
                try: out["redfin_saves"] = int(m.group(1).replace(",", "")); break
                except Exception: pass
    if "redfin_tours" not in out:
        for pat in (
            r'(\d[\d,]*)\s*(?:tours?|tour\s+requests?)\b',
            r'"tourCount"\s*:\s*(\d+)',
        ):
            m = re.search(pat, html, re.I)
            if m:
                try: out["redfin_tours"] = int(m.group(1).replace(",", "")); break
                except Exception: pass

    # Redfin Estimate (informational — useful comp number)
    m = re.search(r'"redfinEstimate"\s*:\s*\{[^}]*"value"\s*:\s*(\d+)', html)
    if m:
        try: out["redfin_estimate"] = int(m.group(1))
        except Exception: pass

    return out


# ---------------------------------------------------------------------------
# Zillow — view count + save count
# ---------------------------------------------------------------------------
def scrape_zillow(url: Optional[str]) -> dict:
    """Pull view/save counts + Zestimate from a Zillow homedetails page.

    Zillow embeds data in __NEXT_DATA__ similar to Redfin, plus an
    apolloState cache. View/save counts are public on most listings.

    Note: Zillow aggressively blocks `python-requests` with a
    Press-and-Hold CAPTCHA / akamai bot wall. When that happens we
    return ``{"_blocked": "zillow"}`` so the caller can prompt for
    manual entry instead of pretending the page loaded clean.
    """
    out: dict = {}
    html = _fetch(url) if url else None
    if not html:
        return out

    low = html.lower()
    if "press & hold" in low or "perimeterx" in low or "captcha-delivery" in low \
            or len(html) < 4000:  # akamai stub pages are tiny
        out["_blocked"] = "zillow (bot wall)"
        return out

    # Apollo cache — Zillow's preferred shape
    m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
            views = _deep_find(data, ("pageViewCount", "views", "viewCount"))
            saves = _deep_find(data, ("favoriteCount", "saves", "savedCount"))
            zest  = _deep_find(data, ("zestimate", "zestimateAmount"))
            if views is not None: out["zillow_views"] = int(views)
            if saves is not None: out["zillow_saves"] = int(saves)
            if zest  is not None:
                try: out["zestimate"] = int(zest)
                except Exception: pass
        except Exception as exc:
            log.debug("zillow __NEXT_DATA__ parse failed: %s", exc)

    # Fallback regex
    if "zillow_views" not in out:
        m = re.search(r'(\d[\d,]*)\s*views?', html, re.I)
        if m:
            try: out["zillow_views"] = int(m.group(1).replace(",", ""))
            except Exception: pass
    if "zillow_saves" not in out:
        m = re.search(r'(\d[\d,]*)\s*saves?', html, re.I)
        if m:
            try: out["zillow_saves"] = int(m.group(1).replace(",", ""))
            except Exception: pass

    return out


# ---------------------------------------------------------------------------
# Realtor.com — saved-by-X-users count
# ---------------------------------------------------------------------------
def scrape_realtor(url: Optional[str]) -> dict:
    """Realtor.com publishes a 'Saved' count on most active listings."""
    out: dict = {}
    html = _fetch(url) if url else None
    if not html:
        return out

    m = re.search(r'(\d[\d,]*)\s*(?:saves?|saved)', html, re.I)
    if m:
        try:
            out["realtor_saves"] = int(m.group(1).replace(",", ""))
        except Exception:
            pass

    return out


# ---------------------------------------------------------------------------
# Aggregate — call all three, merge, return a single metrics dict
# ---------------------------------------------------------------------------
def scrape_all(*, redfin_url: Optional[str] = None,
               zillow_url: Optional[str] = None,
               realtor_url: Optional[str] = None) -> dict:
    """Run all three scrapers. Each is best-effort and never raises.

    `_blocked_<source>` keys carry bot-wall diagnostics for the UI; they
    are stripped before persisting to Mongo.
    """
    out: dict = {"source": "scraper"}
    for label, fn, url in (
        ("redfin",  scrape_redfin,  redfin_url),
        ("zillow",  scrape_zillow,  zillow_url),
        ("realtor", scrape_realtor, realtor_url),
    ):
        try:
            r = fn(url)
            if "_blocked" in r:
                out[f"_blocked_{label}"] = r.pop("_blocked")
            out.update(r)
        except Exception as exc:
            log.warning("%s scrape failed: %s", label, exc)
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _deep_find(obj, keys: tuple, max_depth: int = 8):
    """Walk a nested dict/list structure looking for the first occurrence
    of any of `keys`. Returns the value or None."""
    if max_depth <= 0:
        return None
    if isinstance(obj, dict):
        for k in keys:
            if k in obj and obj[k] not in (None, "", [], {}):
                return obj[k]
        for v in obj.values():
            r = _deep_find(v, keys, max_depth - 1)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _deep_find(v, keys, max_depth - 1)
            if r is not None:
                return r
    return None
