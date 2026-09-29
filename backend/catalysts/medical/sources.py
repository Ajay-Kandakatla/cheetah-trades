"""🧬 Medical catalysts — news sources -> normalised articles (spec §3.5).

Four legs, every one async and injectable (`get` / `fetch`), so the routine
can bound each network await with `asyncio.wait_for` and the tests never
touch the network:

  finnhub   per-ticker trigger (roster)       finnhub_client.client.company_news (house token bucket + cache)
  sec       market-wide 8-K EX-99.1           sepa.insider._edgar_get (the ONE paced EDGAR chokepoint)
  massive   market-wide news, 1 call/run      v2/reference/news, key via massive_keys.stocks_key()
  fda_rss   FDA press releases                browser UA — the python-requests UA gets a 404 (measured)

Article shape:
  {key, provider, source, title, url, published (epoch s UTC), ticker, tickers_tagged,
   context (<= EXHIBIT_LEAD_CHARS), text_basis, sic, cik}

Traps (docs/catalysts/medical_catalysts.md):
  * Finnhub `related` is the ASKED ticker even on other companies' stories —
    relevance is checked on the title (news_search.relevance_filter or the
    classifier's name forms).
  * Massive `tickers[]` carries partners (Elevar's approval is tagged RLAY):
    the issuer is the tagged ticker NAMED in the title, else unresolved.
  * EDGAR full-text hits boilerplate ("clinical hold" inside a credit
    agreement): only the EX-99.1 lead is ever classified; no exhibit -> skip.
  * Keys ride in request URLs (`token=`, `apiKey=`): every exception text is
    passed through observability.logsetup.redact before it is logged or stored.
"""
from __future__ import annotations

import html as _html
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Optional
from xml.etree import ElementTree as _ET

log = logging.getLogger("catalysts.medical.sources")

FINNHUB_PER_MIN = 20                 # prober default; the key's 60/min is shared with the live app
FINNHUB_DAYS_BACK = 4
FTS_QUERIES = ('"primary endpoint"', '"topline"', '"FDA approval"', '"complete response letter"',
               '"breakthrough therapy designation"', '"clinical hold"')
HEALTHCARE_SICS = frozenset({"2834", "2835", "2836", "3841", "3845", "8731"})
EXHIBIT_LEAD_CHARS = 1500            # headline + bullets; excludes safe-harbor boilerplate
FTS_MAX_HITS_PER_QUERY = 10
FDA_PRESS_RSS = "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml"
FDA_RSS_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")   # python-requests UA → 404 (measured)
MASSIVE_NEWS_URL = "https://api.massive.com/v2/reference/news"
FDA_PAGES_PER_RUN = 3
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{adsh}/"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
_TITLE_MAX = 300

_EX991 = re.compile(r"ex-?99[._-]?1|ex991", re.I)
_BOILER = re.compile(r"forward[- ]looking statements?|safe harbor|cautionary (?:note|statement)", re.I)
_DISPLAY_TICKERS = re.compile(r"\(([A-Z0-9.\-]+(?:,\s*[A-Z0-9.\-]+)*)\)\s*\(CIK")
_FDA_COMPANY = re.compile(r"(?:granted|approved|awarded)\s+to\s+([A-Z][\w&.,\- ]{2,60}?)(?:[.,]| for)")
_SUFFIX = re.compile(r"(?:,?\s+(?:inc\.?|incorporated|corp\.?|corporation|company|co\.?|ltd\.?|limited|plc|ag|"
                     r"s\.?a\.?|n\.?v\.?|ab|asa|a/?s|se|holdings?|group|llc|l\.?p\.?)|\s*&|\s+and)\s*$", re.I)


def redact_exc(exc) -> str:
    from observability.logsetup import redact
    return redact(f"{type(exc).__name__}: {exc}")


def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def norm_company(name: Optional[str]) -> str:
    """Drop parentheticals, collapse spaces, strip trailing Inc/Corp/Ltd/… repeatedly."""
    n = re.sub(r"\([^)]*\)", " ", name or "")
    n = re.sub(r"\s+", " ", n).strip()
    prev = None
    while prev != n:
        prev = n
        n = _SUFFIX.sub("", n).strip(" ,")
    return n


# ---------------------------------------------------------------------------
# article keys
# ---------------------------------------------------------------------------
def article_key(item: dict) -> str:
    """Natural id per provider; fallback `t:{title_key}:{YYYYmmddHHMM}`."""
    prov = item.get("provider")
    nid = item.get("id") or item.get("_nid")
    if prov == "finnhub" and nid:
        return f"fh:{nid}"
    if prov == "sec" and item.get("adsh"):
        return f"sec:{item['adsh']}"
    if prov == "massive" and nid:
        return f"mv:{nid}"
    if prov == "fda_rss" and (item.get("guid") or item.get("url")):
        return f"fda:{item.get('guid') or item.get('url')}"
    from news_search.core import _title_key
    ts = item.get("published")
    stamp = (datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y%m%d%H%M")
             if isinstance(ts, (int, float)) else "undated")
    return f"t:{_title_key(item.get('title') or '')}:{stamp}"


def _article(*, provider, source, title, url, published, nid=None, ticker=None, tickers=None,
             context="", basis="headline", sic=None, cik=None, adsh=None, guid=None) -> dict:
    a = {"provider": provider, "source": source or None, "title": (title or "").strip(),
         "url": (url or "").strip(), "published": published, "ticker": ticker,
         "tickers_tagged": list(tickers or []), "context": (context or "")[:EXHIBIT_LEAD_CHARS],
         "text_basis": basis, "sic": sic, "cik": cik}
    a["key"] = article_key({"provider": provider, "id": nid, "adsh": adsh, "guid": guid,
                            "url": url, "title": title, "published": published})
    return a


# ---------------------------------------------------------------------------
# relevance (Finnhub `related` = the asked ticker even on others' stories)
# ---------------------------------------------------------------------------
def relevant(title: str, *, ticker: str, company: Optional[str], forms: tuple = ()) -> bool:
    """The house rule (news_search.relevance_filter: name | first word |
    $TICKER | bare ticker >= 4 chars) OR the classifier's name forms (which
    add the distinctive word — "Lilly" for "Eli Lilly and Company")."""
    from news_search.core import relevance_filter
    # suffix-stripped first: "Moderna, Inc." would make the house rule's first
    # word "Moderna," (comma included) and miss "Moderna Announces …"
    if relevance_filter([{"title": title}], ticker=ticker, company=norm_company(company) or company):
        return True
    if forms:
        try:
            from catalysts.medical.classify import attribute
            return bool(attribute(title, ticker=ticker, forms=forms, cue_span=None))
        except Exception as exc:                                # noqa: BLE001
            log.debug("medical.sources: attribute failed: %s", exc)
    return False


# ---------------------------------------------------------------------------
# Finnhub
# ---------------------------------------------------------------------------
async def _default_finnhub(symbol: str, days_back: int):
    from finnhub_client.client import company_news
    return await company_news(symbol, days_back=days_back)


async def finnhub_articles(symbol: str, *, company: Optional[str], days_back: int = FINNHUB_DAYS_BACK,
                           fetch: Optional[Callable] = None, forms: tuple = (),
                           counts: Optional[dict] = None) -> list:
    """Company news for one roster name -> relevant, dated articles."""
    counts = counts if counts is not None else {}
    fetch = fetch or _default_finnhub
    try:
        rows = await fetch(symbol, days_back)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.sources: finnhub %s failed: %s", symbol, redact_exc(exc))
        counts["errors"] = counts.get("errors", 0) + 1
        return []
    out = []
    for r in rows or []:
        title = (r.get("headline") or "").strip()
        ts = r.get("datetime")
        if not isinstance(ts, (int, float)) or ts != ts or ts <= 0:
            counts["undated_dropped"] = counts.get("undated_dropped", 0) + 1
            continue
        if not title:
            continue
        if not relevant(title, ticker=symbol, company=company, forms=forms):
            counts["irrelevant_dropped"] = counts.get("irrelevant_dropped", 0) + 1
            continue
        related = [s.strip().upper() for s in str(r.get("related") or "").split(",") if s.strip()]
        out.append(_article(provider="finnhub", source=r.get("source"), title=title, url=r.get("url"),
                            published=float(ts), nid=r.get("id"), ticker=symbol.upper(),
                            tickers=related or [symbol.upper()], context=r.get("summary") or ""))
    return out


# ---------------------------------------------------------------------------
# EDGAR
# ---------------------------------------------------------------------------
async def _default_edgar_get(url, params=None, headers=None):
    from sepa.insider import _edgar_get
    return await _edgar_get(url, params=params)


def ticker_from_display(name: str) -> Optional[str]:
    """'Calidi Biotherapeutics, Inc.  (CLDI, CLDWW)  (CIK 0001855485)' -> 'CLDI'."""
    m = _DISPLAY_TICKERS.search(name or "")
    if not m:
        return None
    return m.group(1).split(",")[0].strip().upper() or None


def company_from_display(name: str) -> str:
    return re.sub(r"\s*\(.*$", "", name or "").strip()


async def edgar_8k_hits(day_from: str, day_to: str, *, get: Optional[Callable] = None,
                        queries: tuple = FTS_QUERIES, counts: Optional[dict] = None) -> list:
    """EDGAR full-text search, forms=8-K, one GET per query; healthcare SICs
    only; one hit per accession (adsh). A failed query (None) skips it."""
    counts = counts if counts is not None else {}
    get = get or _default_edgar_get
    from sepa.insider import EDGAR_FTS
    seen, out = set(), []
    for q in queries:
        params = {"q": q, "forms": "8-K", "dateRange": "custom", "startdt": day_from, "enddt": day_to}
        try:
            resp = await get(EDGAR_FTS, params=params)
        except Exception as exc:                                # noqa: BLE001
            log.warning("medical.sources: EDGAR FTS failed: %s", redact_exc(exc))
            counts["errors"] = counts.get("errors", 0) + 1
            continue
        if resp is None or getattr(resp, "status_code", 0) != 200:
            continue
        try:
            hits = ((resp.json() or {}).get("hits") or {}).get("hits") or []
        except Exception:                                       # noqa: BLE001
            continue
        for h in hits[:FTS_MAX_HITS_PER_QUERY]:
            src = h.get("_source") or {}
            adsh = src.get("adsh") or (h.get("_id") or "").split(":")[0]
            sics = [str(s) for s in (src.get("sics") or [])]
            if not adsh or adsh in seen:
                continue
            if not any(s in HEALTHCARE_SICS for s in sics):
                counts["non_healthcare_sic"] = counts.get("non_healthcare_sic", 0) + 1
                continue
            seen.add(adsh)
            dn = (src.get("display_names") or [""])[0]
            out.append({"adsh": adsh, "cik": (src.get("ciks") or [None])[0], "display_name": dn,
                        "ticker": ticker_from_display(dn), "company": company_from_display(dn),
                        "sic": next((s for s in sics if s in HEALTHCARE_SICS), None),
                        "items": src.get("items") or [], "file_date": src.get("file_date"),
                        "query": q})
    counts["edgar_hits"] = counts.get("edgar_hits", 0) + len(out)
    return out


def _strip_html(raw: str) -> str:
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw or "")
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = _html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def exhibit_lead(text: str) -> str:
    """Plain exhibit text -> the lead: 'Exhibit 99.1' label dropped, cut at the
    first forward-looking / safe-harbor marker, then EXHIBIT_LEAD_CHARS."""
    t = re.sub(r"\s+", " ", text or "").strip()
    t = re.sub(r"^.*?\bExhibit\s+99\.1\b\s*", "", t, count=1, flags=re.I) if re.search(
        r"\bExhibit\s+99\.1\b", t[:300], re.I) else t
    m = _BOILER.search(t)
    if m:
        t = t[:m.start()]
    return t[:EXHIBIT_LEAD_CHARS].strip()


def split_headline(lead: str) -> tuple:
    """(headline, rest). The PR headline ends at the first bullet, else at the
    dateline ('CITY, Calif., September 28, 2026 /PRNewswire/'), capped."""
    s = lead or ""
    cut = len(s)
    b = re.search(r"[••●▪]", s)
    if b:
        cut = min(cut, b.start())
    d = re.search(r"[A-Z][A-Za-z .]+,\s+[A-Z][A-Za-z.]*\.?,?\s+[A-Z][a-z]+\s+\d{1,2},\s+\d{4}", s)
    if d and d.start() > 20:
        cut = min(cut, d.start())
    head = s[:cut].strip(" .—-")
    if len(head) > _TITLE_MAX:
        head = head[:_TITLE_MAX].rsplit(" ", 1)[0]
    return head, s[cut:].strip()


async def edgar_exhibit_lead(cik, adsh: str, *, get: Optional[Callable] = None) -> Optional[str]:
    """index.json -> the EX-99.1 .htm -> stripped, unescaped lead. "" when the
    filing carries no EX-99.1 (the credit-agreement boilerplate case — skip it
    for good); None when a fetch failed (retry next pass)."""
    get = get or _default_edgar_get
    base = SEC_ARCHIVE.format(cik=int(str(cik).lstrip("0") or 0), adsh=adsh.replace("-", ""))
    try:
        resp = await get(base + "index.json")
        if resp is None or resp.status_code != 200:
            return None
        items = ((resp.json() or {}).get("directory") or {}).get("item") or []
        names = [str(i.get("name") or "") for i in items]
        ex = [n for n in names if _EX991.search(n) and n.lower().endswith((".htm", ".html", ".txt"))]
        if not ex:
            return ""
        r2 = await get(base + ex[0])
        if r2 is None or r2.status_code != 200:
            return None
        return exhibit_lead(_strip_html(r2.text))
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.sources: EX-99.1 %s failed: %s", adsh, redact_exc(exc))
        return None


def acceptance_from_submissions(data: dict, adsh: str) -> Optional[datetime]:
    rec = ((data or {}).get("filings") or {}).get("recent") or {}
    accs = rec.get("accessionNumber") or []
    acc = rec.get("acceptanceDateTime") or []
    for i, a in enumerate(accs):
        if a == adsh and i < len(acc):
            try:
                return datetime.fromisoformat(str(acc[i]).replace("Z", "+00:00")).astimezone(timezone.utc)
            except ValueError:
                return None
    return None


async def edgar_acceptance(cik, adsh: str, *, get: Optional[Callable] = None) -> Optional[datetime]:
    """data.sec.gov submissions acceptanceDateTime (UTC) for one accession."""
    get = get or _default_edgar_get
    try:
        resp = await get(SEC_SUBMISSIONS.format(cik=str(int(str(cik).lstrip("0") or 0)).zfill(10)))
        if resp is None or resp.status_code != 200:
            return None
        return acceptance_from_submissions(resp.json(), adsh)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.sources: acceptance %s failed: %s", adsh, redact_exc(exc))
        return None


def edgar_article(hit: dict, lead: str, accepted: Optional[datetime]) -> Optional[dict]:
    """One EDGAR hit + its EX-99.1 lead -> an article (None when undated)."""
    if not lead:
        return None
    head, rest = split_headline(lead)
    if not head or accepted is None:
        return None
    adsh = hit["adsh"]
    cik = str(int(str(hit.get("cik") or "0").lstrip("0") or 0))
    url = SEC_ARCHIVE.format(cik=cik, adsh=adsh.replace("-", "")) + f"{adsh}-index.htm"
    return _article(provider="sec", source="SEC 8-K EX-99.1", title=head, url=url,
                    published=accepted.timestamp(), ticker=hit.get("ticker"),
                    tickers=[hit["ticker"]] if hit.get("ticker") else [], context=rest,
                    basis="exhibit_99_1", sic=hit.get("sic"), cik=hit.get("cik"), adsh=adsh)


async def sec_company_titles(*, get: Optional[Callable] = None) -> dict:
    """{TICKER: title} from SEC company_tickers.json (the routine caches it per ET day)."""
    get = get or _default_edgar_get
    try:
        resp = await get(SEC_TICKERS_URL)
        if resp is None or resp.status_code != 200:
            return {}
        data = resp.json() or {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.sources: SEC tickers failed: %s", redact_exc(exc))
        return {}
    rows = data.values() if isinstance(data, dict) else data
    out = {}
    for r in rows:
        t = str((r or {}).get("ticker") or "").upper()
        if t and t not in out:
            out[t] = (r or {}).get("title") or ""
    return out


# ---------------------------------------------------------------------------
# Massive (market-wide)
# ---------------------------------------------------------------------------
async def _default_http_get(url, params=None, headers=None):
    import httpx
    async with httpx.AsyncClient(timeout=15) as client:
        return await client.get(url, params=params, headers=headers)


def _mention_pos(title: str, forms) -> Optional[int]:
    """Earliest match of any name form (regex strings from classify.name_forms;
    a plain string is escaped) — used only to ORDER candidate issuers."""
    best = None
    for f in forms or ():
        try:
            rx = re.compile(r"(?<![\w$])(?:" + str(f) + r")(?![\w])", re.I)
        except re.error:
            rx = re.compile(r"(?<![\w$])" + re.escape(str(f)) + r"(?![\w])", re.I)
        m = rx.search(title or "")
        if m and (best is None or m.start() < best):
            best = m.start()
    return best


def resolve_issuer_massive(title: str, tickers, forms_for: Callable) -> Optional[str]:
    """§3.4.3 rule 4: the tagged ticker whose name forms are attributed in the
    title; several -> the earliest mention; none -> None (never the single
    tag — "Live Oak Acquisition Corp VI … IPO" is tagged SAN)."""
    from catalysts.medical.classify import attribute
    cands = []
    for t in tickers or []:
        t = str(t or "").upper()
        if not t:
            continue
        forms = forms_for(t) or ()
        try:
            ok = attribute(title, ticker=t, forms=forms, cue_span=None)
        except Exception:                                       # noqa: BLE001
            ok = False
        if ok:
            pos = _mention_pos(title, forms)
            cands.append((pos if pos is not None else 10 ** 6, t))
    if not cands:
        return None
    return sorted(cands)[0][1]


async def massive_marketwide(since_utc: datetime, *, get: Optional[Callable] = None,
                             key: Optional[str] = None, counts: Optional[dict] = None) -> list:
    """One page (limit 1000, newest first) of market-wide news since `since_utc`."""
    counts = counts if counts is not None else {}
    get = get or _default_http_get
    if key is None:
        from massive_keys import stocks_key
        key = stocks_key()
    if not key:
        return []
    params = {"published_utc.gte": since_utc.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "order": "desc", "sort": "published_utc", "limit": 1000, "apiKey": key}
    try:
        resp = await get(MASSIVE_NEWS_URL, params=params)
        if resp is None or resp.status_code != 200:
            return []
        rows = (resp.json() or {}).get("results") or []
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.sources: massive failed: %s", redact_exc(exc))
        counts["errors"] = counts.get("errors", 0) + 1
        return []
    from news_search.core import _iso_to_epoch
    out = []
    for r in rows:
        ts = _iso_to_epoch(r.get("published_utc"))
        if ts is None:
            counts["undated_dropped"] = counts.get("undated_dropped", 0) + 1
            continue
        out.append(_article(provider="massive", source=(r.get("publisher") or {}).get("name"),
                            title=r.get("title"), url=r.get("article_url"), published=float(ts),
                            nid=r.get("id"), tickers=[str(t).upper() for t in (r.get("tickers") or [])],
                            context=r.get("description") or ""))
    counts["massive_items"] = counts.get("massive_items", 0) + len(out)
    return out


# ---------------------------------------------------------------------------
# FDA press releases
# ---------------------------------------------------------------------------
def parse_rss(xml_text: str) -> list:
    try:
        root = _ET.fromstring(xml_text)
    except _ET.ParseError:
        return []
    out = []
    for it in root.iter("item"):
        def tx(tag):
            el = it.find(tag)
            return (el.text or "").strip() if el is not None and el.text else ""
        pub = None
        raw = tx("pubDate")
        if raw:
            try:
                pub = parsedate_to_datetime(raw).astimezone(timezone.utc).timestamp()
            except (TypeError, ValueError):
                pub = None
        out.append({"title": tx("title"), "url": tx("link"), "guid": tx("guid") or tx("link"),
                    "published": pub, "description": _strip_html(tx("description"))})
    return out


def fda_company_from_page(page_html: str) -> Optional[str]:
    """v1 page rule: '(granted|approved|awarded) to <Company>(.|,| for)'."""
    m = _FDA_COMPANY.search(_strip_html(page_html or ""))
    return norm_company(m.group(1)) if m else None


async def fda_press_releases(*, get: Optional[Callable] = None, want_page: Optional[Callable] = None,
                             max_pages: int = FDA_PAGES_PER_RUN, counts: Optional[dict] = None) -> list:
    """The FDA press RSS (browser UA) -> articles; for at most `max_pages`
    items `want_page(item)` selects, the release page names the company."""
    counts = counts if counts is not None else {}
    get = get or _default_http_get
    hdr = {"User-Agent": FDA_RSS_UA}
    try:
        resp = await get(FDA_PRESS_RSS, headers=hdr)
        if resp is None or resp.status_code != 200:
            return []
        items = parse_rss(resp.text)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.sources: FDA RSS failed: %s", redact_exc(exc))
        counts["errors"] = counts.get("errors", 0) + 1
        return []
    out, pages = [], 0
    for it in items:
        if it["published"] is None:
            counts["undated_dropped"] = counts.get("undated_dropped", 0) + 1
            continue
        company = None
        if want_page is not None and pages < max_pages and it.get("url") and want_page(it):
            pages += 1
            try:
                r = await get(it["url"], headers=hdr)
                if r is not None and r.status_code == 200:
                    company = fda_company_from_page(r.text)
            except Exception as exc:                            # noqa: BLE001
                log.warning("medical.sources: FDA page failed: %s", redact_exc(exc))
        a = _article(provider="fda_rss", source="FDA press release", title=it["title"], url=it["url"],
                     published=it["published"], guid=it["guid"], context=it["description"])
        a["company"] = company
        out.append(a)
    counts["fda_items"] = counts.get("fda_items", 0) + len(out)
    return out


def match_company_title(company: Optional[str], sec_titles: dict) -> Optional[str]:
    """A page company name -> its ticker through the SEC titles (suffix-stripped,
    case-insensitive exact match); no match -> None."""
    c = norm_company(company).lower()
    if not c:
        return None
    for t, title in (sec_titles or {}).items():
        if norm_company(title).lower() == c:
            return t
    return None


__all__ = ["FINNHUB_PER_MIN", "FINNHUB_DAYS_BACK", "FTS_QUERIES", "HEALTHCARE_SICS", "EXHIBIT_LEAD_CHARS",
           "FTS_MAX_HITS_PER_QUERY", "FDA_PRESS_RSS", "FDA_RSS_UA", "MASSIVE_NEWS_URL",
           "finnhub_articles", "edgar_8k_hits", "edgar_exhibit_lead", "edgar_acceptance", "edgar_article",
           "massive_marketwide", "fda_press_releases", "resolve_issuer_massive", "fda_company_from_page",
           "article_key", "sec_company_titles", "relevant", "redact_exc", "norm_company",
           "match_company_title", "ticker_from_display", "exhibit_lead", "split_headline"]
