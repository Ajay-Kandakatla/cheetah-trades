"""One reusable news routine — ticker, sector, or keyword.

Ajay 2026-09-20, verbatim: "A reusable backend routine".

WHY THIS EXISTS
---------------
Before this module there were five separate news legs in the backend, each
with its own idea of what "recent" means and its own idea of what an UNDATED
headline is worth:

  * `rotation/sector_news_tags._fresh`      36h window, undated DROPPED
  * `sepa/catalyst._fetch_google_news`      no window at all, `pub` carried raw
  * `catalysts/news_read`                   no window (Google), 7d Massive leg
  * `catalysts/evidence._fetch_massive_news`  cutoff, undated KEPT
  * `catalysts/product_launches._fetch_news`  cutoff, undated DROPPED
  * `supply_demand/news.fetch_edge_news`    no window — 30 ARTICLES, not days

This module is the ONE place a new surface asks for news. It does not rewrite
the five above; reconciling them is HIS CALL (docs/news/news_search.md, and
spec §7 item 9 for the evidence-vs-product_launches pair). What it does give
every NEW caller is a single window, a single undated policy, a single dedupe
and a single relevance rule — all lifted verbatim from code that already
shipped, never re-derived:

  * the window and the undated/ms/future guards are `sector_news_tags._fresh`
  * the dedupe title key is `news.fetch_news`'s (`\\W`-stripped lower, 80 chars)
  * the relevance rule is `sepa.catalyst._fetch_google_news`'s post-filter
    (company name | its first word | $TICKER | bare ticker only at len >= 4)

NOT A SIGNAL, NOT A GATE
------------------------
Nothing here is measured. A headline count is not evidence and a "fresh"
stamp is not a catalyst. The window below is a SCOPE knob — it bounds what a
caller reads, it does not decide anything — in the same sense as the knobs at
the top of `rotation/sector_news_tags`.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("cheetah.news_search")

ET = ZoneInfo("America/New_York")

# ── SCOPE KNOBS, NOT SIGNAL THRESHOLDS ─────────────────────────────────────
# DEFAULT_WINDOW_HOURS is `sector_news_tags.NEWS_WINDOW_HOURS`'s value, moved
# here so there is ONE window in the app rather than a copy per caller. 36 not
# 24 so a Monday run still sees Friday's close-of-day story and a weekend run
# sees Friday. SNT re-binds its own name to this constant.
DEFAULT_WINDOW_HOURS = 36
DEFAULT_LIMIT = 12
AUDIT_COLL = "news_search_audit"
SELECTORS = ("ticker", "sector", "keyword")

_FUTURE_SLACK_SEC = 3600      # clock skew allowance, from SNT._fresh
_MS_STAMP_FLOOR = 1e12        # a 13-digit stamp is milliseconds, not year 45000
_TITLE_KEY_CHARS = 80         # news.fetch_news's dedupe key length


# ---------------------------------------------------------------------------
# Normalise
# ---------------------------------------------------------------------------
def _iso_to_epoch(raw) -> Optional[int]:
    """ISO-8601 (Massive `published_utc`) -> epoch seconds, or None."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        dt = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except Exception:                                          # noqa: BLE001
        return None
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:                                          # noqa: BLE001
        return None


def normalise(item: dict, provider: Optional[str] = None) -> dict:
    """One item shape across every provider in the app.

    Accepts the three shapes that already exist:
      * `news.py`                     {source,title,url,summary,published,provider}
      * `sepa.catalyst`               {title,link,pub,score}
      * Massive (evidence/launches)   {title,url,publisher,published_utc,description}
    """
    item = item or {}
    published = item.get("published")
    if not isinstance(published, (int, float)) or published != published:
        published = None
    if published is None:
        published = _iso_to_epoch(item.get("published_utc"))
    if published is None and item.get("pub"):
        from news import _parse_rss_date              # RFC-2822, unknown -> None
        published = _parse_rss_date(item.get("pub"))
    return {
        "title": (item.get("title") or "").strip(),
        "url": (item.get("url") or item.get("link") or "").strip(),
        "source": (item.get("source") or item.get("publisher") or "") or None,
        "summary": (item.get("summary") or item.get("description") or "").strip(),
        "published": published,
        "provider": item.get("provider") or provider,
    }


# ---------------------------------------------------------------------------
# Fresh — `sector_news_tags._fresh` semantics, verbatim
# ---------------------------------------------------------------------------
def fresh(items, *, window_hours: float = DEFAULT_WINDOW_HOURS,
          now: Optional[float] = None) -> list:
    """Headlines inside `window_hours`, newest first.

    An item with no timestamp is DROPPED rather than assumed fresh. That drop
    is load-bearing: `news._parse_rss_date` used to stamp every unparseable
    Google date with the CURRENT TIME, which made every window in the app
    inert (measured 2026-09-19 — 12 of 12 NVDA Google items reported an age of
    0.00 hours, one of them twenty-four days old). Undated now means undated.
    """
    now = time.time() if now is None else now
    floor = now - window_hours * 3600
    out = []
    for it in items or []:
        ts = (it or {}).get("published")
        if not isinstance(ts, (int, float)) or ts != ts:
            continue
        # Feeds have shipped milliseconds before.
        if ts > _MS_STAMP_FLOOR:
            ts = ts / 1000.0
        if ts < floor or ts > now + _FUTURE_SLACK_SEC:
            continue
        out.append({**it, "published": ts})
    out.sort(key=lambda x: x["published"], reverse=True)
    return out


# ---------------------------------------------------------------------------
# Dedupe — `news.fetch_news`'s title key, plus the url
# ---------------------------------------------------------------------------
def _title_key(title: str) -> str:
    return re.sub(r"\W+", "", (title or "").lower())[:_TITLE_KEY_CHARS]


def dedupe(items) -> list:
    """Drop repeats of the same story: same title key OR same url.

    Two legs syndicating one wire story share a title; one leg serving the
    same url twice under a rewritten headline does not. Both are one story.
    """
    seen_titles: set = set()
    seen_urls: set = set()
    out = []
    for it in items or []:
        key = _title_key((it or {}).get("title"))
        url = ((it or {}).get("url") or "").strip()
        if not key:
            continue
        if key in seen_titles:
            continue
        if url and url in seen_urls:
            continue
        seen_titles.add(key)
        if url:
            seen_urls.add(url)
        out.append(it)
    return out


# ---------------------------------------------------------------------------
# Relevance — `sepa.catalyst._fetch_google_news`'s post-filter, verbatim rule
# ---------------------------------------------------------------------------
def relevance_filter(items, *, ticker: str, company: Optional[str]) -> list:
    """Keep only headlines that actually name this company.

    The USD-as-currency / ETH-as-Ethereum trap: a bare three-letter ticker
    matches prose about the dollar. So a cashtag-less ticker is only accepted
    at 4+ characters, exactly as the catalyst tab has always done.
    """
    sym = (ticker or "").upper()
    if not sym:
        return list(items or [])
    name = (company or "").strip()
    name_first = name.split()[0] if name else ""

    terms = []
    if name:
        terms.append(re.escape(name))
    if name_first and name_first.lower() != name.lower():
        terms.append(re.escape(name_first))
    terms.append(re.escape(f"${sym}"))
    if len(sym) >= 4:
        terms.append(rf"\b{re.escape(sym)}\b")
    rx = re.compile("|".join(terms), re.IGNORECASE)

    return [it for it in (items or []) if rx.search(((it or {}).get("title") or ""))]


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------
def build_query(*, sector: Optional[str] = None, keyword: Optional[str] = None) -> str:
    """The Google-News query string for a sector or a keyword selector.

    The sector form quotes the phrase and anchors it to equities, the same way
    `sepa.catalyst` quotes a company name — an unquoted multi-word sector
    returns the union of its words.
    """
    if sector is not None:
        s = (sector or "").strip()
        if not s:
            raise ValueError("sector must not be empty")
        return f'"{s}" sector stocks'
    k = (keyword or "").strip()
    if not k:
        raise ValueError("keyword must not be empty")
    return k


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
def _selector(ticker, sector, keyword) -> tuple:
    chosen = [(k, v) for k, v in
              (("ticker", ticker), ("sector", sector), ("keyword", keyword))
              if v is not None and str(v).strip()]
    if len(chosen) != 1:
        raise ValueError("exactly one of ticker/sector/keyword")
    return chosen[0]


async def search(*, ticker: Optional[str] = None, sector: Optional[str] = None,
                 keyword: Optional[str] = None,
                 window_hours: float = DEFAULT_WINDOW_HOURS,
                 now: Optional[float] = None,
                 relevance: str = "company",
                 limit: int = DEFAULT_LIMIT,
                 audit: Optional[str] = None) -> dict:
    """Recent headlines for ONE selector.

    Never raises past the selector check — a provider that is down comes back
    as `items: []` with `counts.raw == 0`, because every caller of this is a
    board that must still render.
    """
    kind, value = _selector(ticker, sector, keyword)

    import news as _news

    raw: list = []
    query = ""
    if kind == "ticker":
        value = str(value).upper()
        query = value
        try:
            raw = await _news.fetch_news(value) or []
        except Exception as exc:                               # noqa: BLE001
            log.warning("news_search: ticker %s failed: %s", value, exc)
            raw = []
    else:
        value = str(value).strip()
        query = build_query(**{kind: value})
        try:
            raw = await _news.google_search(query) or []
        except Exception as exc:                               # noqa: BLE001
            log.warning("news_search: %s %r failed: %s", kind, value, exc)
            raw = []

    normed = [normalise(it, provider=(it or {}).get("provider")) for it in raw]
    undated_dropped = sum(1 for n in normed if n["published"] is None)
    kept = fresh(normed, window_hours=window_hours, now=now)
    stale_dropped = len(normed) - undated_dropped - len(kept)

    irrelevant_dropped = 0
    if kind == "ticker" and relevance == "company":
        from sepa import company_names
        try:
            company = company_names.name_for(value)
        except Exception as exc:                               # noqa: BLE001
            log.debug("news_search: name lookup %s failed: %s", value, exc)
            company = None
        before = len(kept)
        kept = relevance_filter(kept, ticker=value, company=company)
        irrelevant_dropped = before - len(kept)

    before = len(kept)
    kept = dedupe(kept)
    deduped = before - len(kept)

    out = {
        "items": kept[:limit],
        "selector": {"kind": kind, "value": value},
        "query": query,
        "window_hours": window_hours,
        "fetched_at": time.time() if now is None else now,
        "counts": {
            "raw": len(raw),
            "undated_dropped": undated_dropped,
            "stale_dropped": stale_dropped,
            "irrelevant_dropped": irrelevant_dropped,
            "deduped": deduped,
        },
    }
    if audit:
        _write_audit(audit, out)
    return out


def search_sync(**kw) -> dict:
    """`search` from sync code — the cron path and a request thread both work.

    Same shape as `sector_news_tags.build`: `asyncio.run`, and when a loop is
    already running, hand it to a worker thread.
    """
    try:
        return asyncio.run(search(**kw))
    except RuntimeError:
        import concurrent.futures as _f
        with _f.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(lambda: asyncio.run(search(**kw))).result()


# ---------------------------------------------------------------------------
# Audit — what a surface was shown, by ET day
# ---------------------------------------------------------------------------
def _coll():
    try:
        from sepa.prices import _get_mongo
        pc = _get_mongo()
        return None if pc is None else pc.database[AUDIT_COLL]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("news_search: mongo unavailable: %s", exc)
        return None


def _write_audit(caller: str, result: dict) -> None:
    coll = _coll()
    if coll is None:
        return
    sel = result.get("selector") or {}
    day = datetime.now(ET).strftime("%Y-%m-%d")
    _id = f"{caller}|{sel.get('kind')}|{sel.get('value')}|{day}"
    try:
        coll.update_one({"_id": _id},
                        {"$set": {"_id": _id, "caller": caller, **result}},
                        upsert=True)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("news_search: audit write failed for %s: %s", _id, exc)
