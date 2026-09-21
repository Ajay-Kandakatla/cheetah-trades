"""🗓️ "Coming up" drill-in — a FACT SHEET for one expected listing.

Ajay 2026-09-20: *"Can you gather similar info about these please like the
ticket and make them clicable the onesin IPO tab that are future"*.

A ticker page shows a company's story and its numbers. An expected listing has
no price history, so this shows what the ticker page would if it could: who
the company is (EDGAR's own company record), what it says it does (the
prospectus Overview paragraph, as printed), the deal terms as the cover prints
them, who is underwriting, the last revenue and net-loss lines AS PRINTED in
the registration filing, the link to that filing, and recent headlines.

WHAT THIS NEVER DOES
  * It never measures anything. There is no signal here, no chip, no verdict,
    no ranking and no score — `NOTE` says so on every payload.
  * It never parses a figure out of the filing. `revenue_line` and
    `net_loss_line` are SENTENCES the prospectus printed, carried verbatim
    with their own units and period headers beside them. A thousands-vs-
    millions mistake on a sheet he reads before a listing is exactly the
    invented number Rule #1 forbids, so no number ever leaves the filing.
  * It never runs from the board build. `chart_maps.ipo.build()` does not
    import this module; the drill-in is fetched on a click and nowhere else.
  * It never asks an LLM anything.

THE ONE ENGINES
  * EDGAR — every GET goes through `sepa.insider._edgar_get`, the single
    rate-paced chokepoint that ended the 2026-06-17 429 storm, with
    `sepa.insider.SEC_HEADERS` and `sepa.insider.EDGAR_FTS`. The names are
    bound bare at import so a test can patch `ipo_upcoming._edgar_get` and
    actually stop the network.
  * News — `news_search.core.search`. A `keyword` search is NOT relevance
    filtered by the engine (it only filters `ticker` searches), so this module
    applies `core.relevance_filter` itself.
  * HTML → text — BeautifulSoup with `html.parser` ONLY. lxml is installed in
    the api container but NOT in `backend/.venv`; measured on the 5.76 MB
    Amaero S-1/A the two parsers produce identical text (741,060 chars) and
    html.parser takes 0.44 s, so the stdlib parser is the one rule.

THE CACHE RULE (Mongo `ipo_upcoming_cache`, one doc per symbol)
  * The filing block is keyed by ACCESSION and kept while the accession is
    unchanged AND `parse_note is None` — a block that carries a parse note
    ("EDGAR answered 503", "larger than 15 MB") is a failure, not a fact, and
    is re-fetched on the next resolve.
  * A successful resolve and the headlines are fresh for `CACHE_TTL_SEC`.
  * **A FAILURE IS NEVER CACHED.** An unreachable EDGAR and a name EDGAR
    cannot confirm both leave `resolved_at` exactly where it was, so the next
    click asks again. Otherwise a 30-second blip serves `cached: true` for a
    day.
  * `cached: true` is served ONLY on the zero-network path.
  * Timestamps are epoch floats in Mongo and ISO-8601 UTC on the wire.

FAILURE IS A SENTENCE, NEVER AN EXCEPTION. `lookup` always answers: EDGAR
down, no hit, a filing that names a different symbol, a document over 15 MB
and Mongo down each come back as a payload with `error` set and the calendar
row still on it.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple
from urllib.parse import urlencode

from bs4 import BeautifulSoup

# The ONE EDGAR engine. Bound bare on purpose: `insider._edgar_get(...)` would
# silently defeat every test stub and send the recorder tests at live EDGAR.
from sepa.insider import _edgar_get, SEC_HEADERS, EDGAR_FTS
# The ONE news engine.
from news_search import core

from . import ipo

log = logging.getLogger("chart_maps.ipo_upcoming")

# ── constants ───────────────────────────────────────────────────────────────
# The registration forms a prospectus can arrive on. 424B4/424B1 is the priced
# prospectus, the amendments are the latest pre-pricing draft.
FTS_FORMS = "S-1,F-1,S-1/A,F-1/A,424B4,424B1"
FTS_LOOKBACK_DAYS = 365
PROSPECTUS_RANK = {"424B4": 3, "424B1": 3, "S-1/A": 2, "F-1/A": 2, "S-1": 1, "F-1": 1}
PROSPECTUS_MAX_BYTES = 15 * 1024 * 1024
PROSPECTUS_TIMEOUT_SEC = 30
# stdlib; lxml is NOT in backend/.venv (measured identical output).
HTML_PARSER = "html.parser"
# The underwriters / share count / price / symbol are printed on the cover.
COVER_CHARS = 30_000
SYMBOL_SCAN_CHARS = 100_000
OVERVIEW_MAX_CHARS = 700
LINE_MAX_CHARS = 240
# Units / period lines are read at most this far BEFORE each quote.
TABLE_HEADER_LOOKBACK_CHARS = 4_000
UNDERWRITER_SEGMENT_CHARS = 1_500
HEADLINES_WINDOW_HOURS = 24 * 7
HEADLINES_WINDOW_DAYS = 7
# Freshness for a SUCCESSFUL resolve and for the headlines. The filing block
# itself is keyed by accession and kept while it parsed cleanly.
CACHE_TTL_SEC = 24 * 3600
CACHE_COLL = "ipo_upcoming_cache"
AUDIT_TAG = "ipo_upcoming"

CORP_SUFFIXES = (
    "inc", "corp", "corporation", "co", "company", "ltd", "limited", "plc",
    "llc", "l.p.", "lp", "n.v.", "nv", "s.a.", "sa", "holdings", "holding",
    "group",
)

# Title-case, matched case-SENSITIVE. A cover's bank list is typeset in Title
# case; the running text's lowercase "…between us and the underwriters…" sits
# 2,000+ characters from the banks on Amaero's cover and must never open the
# segment.
UNDERWRITER_ANCHORS = (
    "Bookrunning Managers", "Bookrunning Manager", "Book-Running Managers",
    "Book-Running Manager", "Bookrunners", "Bookrunner", "Lead Managers",
    "Lead Manager", "Sole Manager", "Co-Managers", "Co-Manager",
    "Underwriters", "Underwriter", "Placement Agents", "Placement Agent",
)
UNDERWRITER_END_ANCHORS = (
    "Prospectus dated", "The date of this prospectus", "TABLE OF CONTENTS",
)
UNDERWRITER_NAMES = (
    "Goldman Sachs", "Morgan Stanley", "J.P. Morgan", "JPMorgan", "BofA Securities", "Bank of America",
    "Citigroup", "Citi", "Barclays", "Jefferies", "Evercore", "UBS", "Deutsche Bank", "Wells Fargo",
    "RBC Capital Markets", "RBC", "HSBC", "Mizuho", "Nomura", "SMBC Nikko", "Truist Securities", "KeyBanc",
    "Piper Sandler", "Stifel", "Baird", "William Blair", "Raymond James", "TD Cowen", "Cowen", "Canaccord Genuity",
    "Canaccord", "Lake Street", "Roth Capital", "Roth", "Craig-Hallum", "Needham", "Oppenheimer", "Guggenheim",
    "BTIG", "Leerink Partners", "Leerink", "Cantor Fitzgerald", "Cantor", "Maxim Group", "Maxim", "ThinkEquity",
    "EF Hutton", "Aegis Capital", "Boustead Securities", "Joseph Gunnar", "Kingswood", "The Benchmark Company",
    "Benchmark", "Ladenburg Thalmann", "B. Riley", "Northland", "Titan Partners", "Prime Number Capital",
    "Univest Securities", "Network 1", "WestPark Capital", "D. Boral Capital", "Revere Securities", "Bancroft Capital",
    "Dominari Securities", "Spartan Capital", "Loop Capital", "Siebert Williams Shank", "Academy Securities",
    "Keefe, Bruyette & Woods", "KBW", "Moelis", "Lazard", "Allen & Company", "Macquarie", "Berenberg", "Stephens",
    "Wedbush", "JonesTrading", "Lucid Capital Markets", "Rodman & Renshaw", "A.G.P.", "AGP", "H.C. Wainwright",
    "Alliance Global Partners", "Chardan", "Brookline Capital", "Laidlaw", "Freedom Capital Markets", "US Tiger Securities",
    "Cathay Securities", "Bancroft", "Pacific Century Securities", "R.F. Lafferty", "Craft Capital", "Eddid Securities",
)
# A name at or under this length is matched case-SENSITIVE, so "Citi" cannot
# come from "citizens" prose and "Roth" cannot come from a surname in a
# lowercase sentence.
_SHORT_NAME_CHARS = 6

NOTE = ("A fact sheet from the registration filing and the calendar. Nothing here is "
        "measured, nothing here is a signal, and an expected deal is a plan: dates move "
        "and deals are withdrawn.")

# Every key `extract` returns. The parse-failure filing block sets each of
# these to None (and `underwriters` to []) so the wire shape never changes.
EXTRACT_KEYS = (
    "overview", "proposed_symbol_line", "symbol_in_filing",
    "shares_offered_line", "price_line", "underwriters",
    "revenue_line", "revenue_units_line", "revenue_period_line",
    "net_loss_line", "net_loss_units_line", "net_loss_period_line",
    "extracted_at",
)

_EMPTY_SOURCES = {"edgar_search_url": None, "submissions_url": None, "filing_url": None}
_EMPTY_RESOLUTION = {"method": None, "query": None, "hits": 0, "reason": None}

NO_HIT_ERROR = ("no registration filing found for this name on EDGAR full-text "
                "search (S-1/F-1/424B4, last 365 days)")


# ── tiny helpers ────────────────────────────────────────────────────────────
def _norm(s) -> str:
    """lower-cased, alphanumerics only — the one comparison key for names."""
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def _iso(ts: Optional[float]) -> Optional[str]:
    """Epoch seconds → 'YYYY-MM-DDTHH:MM:SSZ'. None → None.

    Mongo keeps epoch floats; the wire only ever carries the ISO string.
    """
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _collapse(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").replace("\xa0", " ")).strip()


def _cap(s: str) -> Optional[str]:
    """Collapse and cap a printed line. Empty → None (a miss is never '')."""
    t = _collapse(s)
    if not t:
        return None
    if len(t) > LINE_MAX_CHARS:
        t = t[:LINE_MAX_CHARS - 1].rstrip() + "…"
    return t


def short_name(name: str) -> str:
    """ONE rule for the searchable company name.

    Split on whitespace; compare each trailing token with its trailing
    punctuation stripped; drop at most TWO trailing corporate-suffix tokens;
    never drop to zero tokens.

        "Bamboo Insurance Services, Inc." → "Bamboo Insurance Services"
        "Amaero Inc."                     → "Amaero"
        "Foo Holdings, Inc."              → "Foo"
        "Foo Holdings Inc"                → "Foo"
        "SIYATA PTT"                      → "SIYATA PTT"   (nothing to drop)
        "Holdings Inc"                    → "Holdings Inc" (never empty)
    """
    original = str(name or "").strip()
    toks = original.split()
    if not toks:
        return original
    kept = list(toks)
    for _ in range(2):
        if not kept:
            break
        last = kept[-1].strip(",.;").lower()
        if last not in CORP_SUFFIXES:
            break
        kept = kept[:-1]
        if not kept:
            return original
    if not kept:
        return original
    out = " ".join(kept).rstrip(",.;").strip()
    return out or original


# ── the Finnhub calendar row this drill-in is about ─────────────────────────
def calendar_row(symbol: str) -> Tuple[Optional[dict], bool, Optional[str]]:
    """The one `ipo.upcoming` row for `symbol`, or None.

    SYNC — `ipo.calendar` drives its own event loop, so this must be called
    through `asyncio.to_thread`, exactly as `board()` calls it.

    Returns ``(row | None, cal_ok, reason)``. `cal_ok` is Finnhub's own "every
    chunk arrived" flag: a False with no row means the calendar could not be
    read, which is a different answer from "this symbol is not expected".
    """
    sym = str(symbol or "").strip().upper()
    today = ipo._today()
    res = ipo.calendar(today.isoformat(),
                       (today + timedelta(days=ipo.FORWARD_DAYS)).isoformat())
    if not isinstance(res, dict):                              # pragma: no cover
        return None, False, "calendar unavailable"
    ok = bool(res.get("ok"))
    reason = res.get("reason")
    for row in ipo.upcoming(res.get("rows") or [], today):
        if str(row.get("symbol") or "").strip().upper() == sym:
            return row, ok, reason
    return None, ok, reason


# ── EDGAR full-text search ──────────────────────────────────────────────────
def display_name_parts(s: str) -> Tuple[str, Optional[str], Optional[str]]:
    """`'SIYATA PTT  (PTT)  (CIK 0002110025)'` → `('SIYATA PTT', 'PTT', '0002110025')`.

    A filer's display string carries an OPTIONAL ticker tag and the CIK. Older
    exhibits carry no tag at all, which is why a tag can only ever confirm and
    never exclude.
    """
    text = str(s or "")
    m_tag = re.search(r"\(([A-Z][A-Z0-9.\-]{0,5})\)\s*\(CIK", text)
    m_cik = re.search(r"\(CIK\s*(\d{10})\)", text)
    cut = len(text)
    if m_tag is not None:
        cut = min(cut, m_tag.start())
    if m_cik is not None:
        cut = min(cut, m_cik.start())
    name = text[:cut].strip()
    tag = m_tag.group(1) if m_tag is not None else None
    cik = m_cik.group(1) if m_cik is not None else None
    return name, tag, cik


def pick_hit(hits: list, *, symbol: str, name: str) -> Tuple[Optional[dict], Optional[str]]:
    """Which CIK in these full-text hits is the company on the calendar row.

    `_source.ciks` and `_source.display_names` are PARALLEL lists — a filing
    with a co-registrant carries both filers, so the pairs are zipped and
    grouped by CIK. A ticker tag confirms only the CIK it is printed on.

    Rules: a tag equal to the calendar symbol confirms (`ticker_tag`); else an
    exact name match, raw or short-name, confirms (`name`); `ticker_tag` beats
    `name`; a tie goes to the newest `file_date`. Nothing else is confirmed —
    the top hit is NEVER taken on faith.
    """
    sym = str(symbol or "").strip().upper()
    want_raw = _norm(name)
    want_short = _norm(short_name(name))
    best = None
    best_key = None
    for hit in hits or []:
        src = (hit or {}).get("_source") or {}
        ciks = src.get("ciks") or []
        displays = src.get("display_names") or []
        if not isinstance(ciks, list) or not isinstance(displays, list):
            continue
        if len(ciks) != len(displays):
            # Malformed: the pairing is the only thing that ties a tag to a
            # filer, so a mismatched pair is skipped, never guessed.
            continue
        form = src.get("form")
        filed = src.get("file_date")
        for cik, display in zip(ciks, displays):
            part, tag, _cik_in_display = display_name_parts(display)
            if tag and tag.upper() == sym and sym:
                method, rank = "ticker_tag", 2
            elif want_raw and (_norm(part) == want_raw
                               or (want_short and _norm(short_name(part)) == want_short)):
                method, rank = "name", 1
            else:
                continue
            key = (rank, str(filed or ""))
            if best_key is None or key > best_key:
                best_key = key
                best = {"cik": str(cik or "").zfill(10), "form": form,
                        "file_date": filed, "display_name": display,
                        "method": method}
    if best is None:
        return None, "no registration filing found for this name"
    return best, None


def _fts_url(params: dict) -> str:
    return f"{EDGAR_FTS}?{urlencode(params)}"


async def fts_search(name: str, *, today: date) -> Tuple[Optional[list], str]:
    """EDGAR full-text search for a quoted company name.

    Returns ``(hits, url_used)``. **`hits` is None when EDGAR could not be
    reached** and `[]` when EDGAR answered with nothing — the two are different
    facts and `lookup` says a different sentence for each. Never raises.

    Zero hits gets exactly ONE retry with the short name (a phrase carrying
    punctuation, e.g. `"Bamboo Insurance Services, Inc."`, can come back
    empty). Two queries, never a third.
    """
    start = (today - timedelta(days=FTS_LOOKBACK_DAYS)).isoformat()
    end = today.isoformat()
    queries = [f'"{str(name or "").strip()}"']
    short = short_name(name)
    if short and short.strip() and f'"{short}"' != queries[0]:
        queries.append(f'"{short}"')

    url = ""
    reached = False
    for q in queries:
        params = {"q": q, "forms": FTS_FORMS, "dateRange": "custom",
                  "startdt": start, "enddt": end}
        url = _fts_url(params)
        try:
            resp = await _edgar_get(EDGAR_FTS, params=params)
        except Exception as exc:                               # noqa: BLE001
            log.warning("ipo_upcoming: FTS %s errored: %s", q, exc)
            continue
        if resp is None or getattr(resp, "status_code", 0) != 200:
            continue
        try:
            data = resp.json()
        except Exception as exc:                               # noqa: BLE001
            log.warning("ipo_upcoming: FTS %s body unreadable: %s", q, exc)
            continue
        reached = True
        hits = ((data or {}).get("hits") or {}).get("hits") or []
        if hits:
            return list(hits), url
    return ([] if reached else None), url


# ── EDGAR submissions ───────────────────────────────────────────────────────
def _submissions_url(cik10: str) -> str:
    return f"https://data.sec.gov/submissions/CIK{cik10}.json"


async def submissions(cik10: str) -> Optional[dict]:
    """The filer's submissions record, or None if EDGAR could not be read."""
    try:
        resp = await _edgar_get(_submissions_url(str(cik10 or "").zfill(10)))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ipo_upcoming: submissions %s errored: %s", cik10, exc)
        return None
    if resp is None or getattr(resp, "status_code", 0) != 200:
        return None
    try:
        data = resp.json()
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ipo_upcoming: submissions %s body unreadable: %s", cik10, exc)
        return None
    return data if isinstance(data, dict) else None


def company_block(sub: dict) -> dict:
    """EDGAR's own company record, verbatim. Every value is a string or None.

    A pre-IPO filer has `tickers: []` and `exchanges: []` — EDGAR is the only
    fact source here, because Finnhub's profile2 is empty before the listing.
    """
    sub = sub if isinstance(sub, dict) else {}

    def _s(v):
        t = str(v).strip() if v is not None else ""
        return t or None

    cik = str(sub.get("cik") or "").strip()
    return {
        "name": _s(sub.get("name")),
        "cik": cik.zfill(10) if cik else None,
        "sic": _s(sub.get("sic")),
        "sic_description": _s(sub.get("sicDescription")),
        "state": _s(sub.get("stateOfIncorporation")),
        "fiscal_year_end": _s(sub.get("fiscalYearEnd")),
    }


def latest_prospectus(sub: dict) -> Optional[dict]:
    """The newest registration document on the filer's recent list.

    Ranked by FORM first (a priced 424B4 outranks an amendment, an amendment
    outranks the original), then by filing date — an original S-1 filed after
    its own amendment is still the older document.
    """
    sub = sub if isinstance(sub, dict) else {}
    recent = ((sub.get("filings") or {}).get("recent") or {})
    forms = recent.get("form") or []
    dates = recent.get("filingDate") or []
    accs = recent.get("accessionNumber") or []
    docs = recent.get("primaryDocument") or []
    sizes = recent.get("size") or []
    cik = str(sub.get("cik") or "").strip()
    if not cik:
        return None

    best = None
    best_key = None
    for i, form in enumerate(forms):
        rank = PROSPECTUS_RANK.get(str(form or "").strip())
        if rank is None:
            continue
        filed = str(dates[i]) if i < len(dates) else ""
        key = (rank, filed)
        if best_key is not None and key <= best_key:
            continue
        acc = str(accs[i]) if i < len(accs) else ""
        doc = str(docs[i]) if i < len(docs) else ""
        if not acc or not doc:
            continue
        best_key = key
        best = {
            "form": str(form).strip(),
            "filed": filed or None,
            "accession": acc,
            "primary_document": doc,
            "url": (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                    f"{acc.replace('-', '')}/{doc}"),
            "size": sizes[i] if i < len(sizes) else None,
        }
    return best


def _filing_head(lp: dict) -> dict:
    """The five link fields of a filing block. `size` is deliberately dropped:
    no number from the filing ever reaches the wire."""
    lp = lp if isinstance(lp, dict) else {}
    return {k: lp.get(k) for k in
            ("form", "filed", "accession", "primary_document", "url")}


async def fetch_prospectus_html(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Download one prospectus. Network only — the parse happens in a thread.

    Returns ``(html, None)`` or ``(None, reason)``; the reason becomes the
    filing block's `parse_note`, which is what makes the block re-fetch on the
    next resolve instead of being cached as a fact.
    """
    try:
        resp = await _edgar_get(url, timeout=PROSPECTUS_TIMEOUT_SEC)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ipo_upcoming: prospectus %s errored: %s", url, exc)
        return None, "EDGAR could not be reached"
    if resp is None:
        return None, "EDGAR could not be reached"
    try:
        size = len(resp.content)
    except Exception:                                          # noqa: BLE001
        size = 0
    if size > PROSPECTUS_MAX_BYTES:
        return None, "prospectus larger than 15 MB; not parsed"
    status = getattr(resp, "status_code", 0)
    if status != 200:
        return None, f"EDGAR answered {status}"
    return resp.text, None


# ── HTML → the printed text ─────────────────────────────────────────────────
def _html_to_text(html: str) -> str:
    """Strip one filing to text. CPU-bound — only ever called inside a thread.

    `html.parser` only: lxml is absent from `backend/.venv`, and naming that
    parser here would break the local suite with FeatureNotFound.
    """
    soup = BeautifulSoup(html or "", HTML_PARSER)
    for tag in soup(["script", "style"]):
        tag.decompose()
    return _collapse(soup.get_text(" "))


def parse_filing(html: str, *, symbol: str) -> dict:
    """strip + extract — the ONE callable `lookup` hands to `asyncio.to_thread`."""
    return extract(_html_to_text(html), symbol=symbol)


# ── the extractor ───────────────────────────────────────────────────────────
_RX_OVERVIEW = re.compile(
    r"\b(?:Company Overview|Business Overview|Our Company|Our Business|Overview)\s+(?=[A-Z])")
_RX_SYMBOL = re.compile(
    r"under the (?:trading )?symbol\s*[“\"']?\s*([A-Z][A-Z0-9.\-]{0,6})")
_RX_SHARES = re.compile(
    r"(?:We are (?:offering|selling)"
    r"|This is (?:an|the) initial public offering of"
    r"|(?:The )?selling (?:stockholders|shareholders) (?:are|is) offering)"
    r"[^.]{0,200}?\d{1,3}(?:,\d{3})+\s+"
    r"(?:shares|ordinary shares|American Depositary Shares|ADSs|units)")
_RX_SHARES_FALLBACK = re.compile(
    r"\d{1,3}(?:,\d{3})+\s+(?:shares|ordinary shares|ADSs|units)\b")
_RX_PRICE = (
    re.compile(r"between \$\s?\d[\d.,]*\s+and\s+\$\s?\d[\d.,]*\s+per\s+"
               r"(?:share|ADS|ordinary share|unit)"),
    re.compile(r"initial public offering price\s+(?:is|will be|of)\s+\$\s?\d[\d.,]*"
               r"\s+per\s+(?:share|ADS|ordinary share|unit)"),
    re.compile(r"(?:initial public offering|offering) price[^.]{0,200}?"
               r"(?:will be determined|is expected to be"
               r"|we (?:currently )?(?:estimate|anticipate|expect))"),
)
# A numeric run of up to six printed cells, e.g. "$ 6,305 $ 1,317 $ 4,988 379 %"
# or "$ (18,378 ) $ (12,725 )". At least one cell must carry a comma or three
# digits, so a lone footnote marker can never look like a figure.
_NUM_RUN = r"((?:\$?\s*\(?\s*\d[\d,]*(?:\.\d+)?\s*\)?\s*%?\s*[—\-]?\s*){1,6})"
_REVENUE_LABELS = (
    r"Total (?:net )?revenues?(?: from contracts with customers)?",
    r"Net revenues?",
    r"Revenues?, net",
    r"Total net sales",
    r"Net sales",
    r"Revenues?",
)
_NET_LOSS_LABELS = (
    r"Net loss(?: attributable to [^$(]{0,80}?)?",
    r"Net income \(loss\)(?: attributable to [^$(]{0,80}?)?",
    r"Net \(loss\) income",
    r"Net income",
)
_RX_BIG_CELL = re.compile(r"\d[\d,]*")
# Units: a parenthesised header ("(in thousands)") first, else the bare phrase
# with its "except …" tail ("in thousands, except share and per share data").
_RX_UNITS = re.compile(
    r"\((?:in|dollars in|amounts in|U\.S\. dollars in)\s+(?:thousands|millions)[^)]{0,80}\)"
    r"|\bin (?:thousands|millions)(?:,? except [^.)]{0,60})?")
# "ended" either case; the month keeps its capital.
_RX_PERIOD = re.compile(
    r"(?:Fiscal )?(?:Years?|Six Months|Nine Months|Three Months|Twelve Months)"
    r" [Ee]nded [A-Z][a-z]+ \d{1,2},?(?:\s+\d{4})?(?:\s*(?:,|and)\s*\d{4})*")


def _sentence_at(text: str, pos: int) -> Optional[str]:
    """The printed sentence around `pos`, collapsed and capped."""
    if pos < 0 or pos > len(text):
        return None
    win_start = max(0, pos - 400)
    back = text.rfind(". ", win_start, pos)
    start = back + 2 if back != -1 else win_start
    end = min(len(text), pos + 400)
    stop = end
    i = pos
    while i < end:
        j = text.find(".", i)
        if j == -1 or j >= end:
            break
        nxt = text[j + 1:j + 2]
        if nxt == "" or nxt.isspace() or nxt in "”’\"'":
            stop = j + 1
            # keep the closing quote with the sentence it closes
            if nxt in "”’\"'":
                stop = j + 2
            break
        i = j + 1
    return _cap(text[start:stop])


def _first_label_quote(text: str, labels) -> Tuple[Optional[str], int]:
    """The first of `labels` (in order) that is followed by a numeric run.

    Returns ``(line, pos)`` — the label plus its run, collapsed and capped,
    and the position the label was printed at. A label with no figures beside
    it is not a quote.
    """
    for label in labels:
        rx = re.compile(label + r"\s*(?:\(\d\))?\s*" + _NUM_RUN)
        for m in rx.finditer(text):
            run = m.group(m.lastindex or 1)
            if not any(("," in c) or len(c) >= 3 for c in _RX_BIG_CELL.findall(run)):
                continue
            return _cap(m.group(0)), m.start()
    return None, -1


def _table_header_lines(text: str, quote_pos: int) -> Tuple[Optional[str], Optional[str]]:
    """`(units_line, period_line)` for ONE quote — the NEAREST match of each
    printed BEFORE it, within `TABLE_HEADER_LOOKBACK_CHARS`.

    Read per quote on purpose: on Amaero the revenue line comes from the MD&A
    table and the net-loss line from the summary table, and the two tables
    print different units and different periods. One shared header line would
    put the wrong unit under one of them.
    """
    if quote_pos is None or quote_pos < 0:
        return None, None
    window = text[max(0, quote_pos - TABLE_HEADER_LOOKBACK_CHARS):quote_pos]

    def _last(rx):
        found = None
        for m in rx.finditer(window):
            found = m.group(0)
        return _cap(found) if found else None

    return _last(_RX_UNITS), _last(_RX_PERIOD)


def extract(text: str, *, symbol: str) -> dict:
    """Pull the printed lines off one prospectus. A miss is None, never '' or 0.

    `underwriters` is the one field whose miss is `[]`, because it is a list.
    Nothing here is converted to a number.
    """
    text = _collapse(text)
    sym = str(symbol or "").strip().upper()
    cover = text[:COVER_CHARS]
    out = {k: None for k in EXTRACT_KEYS}
    out["underwriters"] = []

    # overview ---------------------------------------------------------------
    for m in _RX_OVERVIEW.finditer(text):
        tail = text[m.end():m.end() + 12]
        if re.match(r"\s*\d{1,3}\b", tail):            # a table-of-contents row
            continue
        body = text[m.end():m.end() + OVERVIEW_MAX_CHARS]
        cut = body.rfind(". ")
        if cut != -1:
            body = body[:cut + 1]
        body = body.strip()
        if body:
            out["overview"] = body
        break

    # the proposed trading symbol -------------------------------------------
    picked = None
    first = None
    for m in _RX_SYMBOL.finditer(text[:SYMBOL_SCAN_CHARS]):
        # the sentence's own full stop sits INSIDE the closing quote: “AMRO.”
        cap = m.group(1).rstrip(".").upper()
        if first is None:
            first = (m.start(), cap)
        if sym and cap == sym:
            picked = (m.start(), cap)
            break
    if picked is None:
        picked = first
    if picked is not None:
        out["proposed_symbol_line"] = _sentence_at(text, picked[0])
        out["symbol_in_filing"] = picked[1]

    # shares offered (cover only) -------------------------------------------
    m = _RX_SHARES.search(cover) or _RX_SHARES_FALLBACK.search(cover)
    if m is not None:
        out["shares_offered_line"] = _sentence_at(cover, m.start())

    # the price sentence (cover only) ---------------------------------------
    for rx in _RX_PRICE:
        m = rx.search(cover)
        if m is not None:
            out["price_line"] = _sentence_at(cover, m.start())
            break

    out["underwriters"] = _underwriters(cover)

    rev_line, rev_pos = _first_label_quote(text, _REVENUE_LABELS)
    loss_line, loss_pos = _first_label_quote(text, _NET_LOSS_LABELS)
    out["revenue_line"] = rev_line
    out["net_loss_line"] = loss_line
    if rev_line is not None:
        out["revenue_units_line"], out["revenue_period_line"] = \
            _table_header_lines(text, rev_pos)
    if loss_line is not None:
        out["net_loss_units_line"], out["net_loss_period_line"] = \
            _table_header_lines(text, loss_pos)

    out["extracted_at"] = _iso(time.time())
    return out


def _underwriter_rx(name: str) -> re.Pattern:
    flags = 0 if len(name) <= _SHORT_NAME_CHARS else re.IGNORECASE
    # `\b` is wrong beside "A.G.P." and "B. Riley"; the explicit look-arounds
    # are the same boundary and survive the punctuation.
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])",
                      flags)


_UNDERWRITER_RX = tuple((n, _underwriter_rx(n)) for n in UNDERWRITER_NAMES)


def _underwriter_segment(cover: str) -> str:
    """The stretch of the cover that prints the bank list.

    Both ends are matched case-SENSITIVE: the list is typeset in Title case,
    and a lowercase "…between us and the underwriters…" in the running text is
    a sentence about them, not the list of them.
    """
    starts = [cover.find(a) for a in UNDERWRITER_ANCHORS]
    starts = [i for i in starts if i >= 0]
    if starts:
        start = min(starts)
        ends = [cover.find(a, start + 1) for a in UNDERWRITER_END_ANCHORS]
        ends = [i for i in ends if i >= 0]
        end = min(ends) if ends else -1
        if end != -1 and (end - start) <= UNDERWRITER_SEGMENT_CHARS:
            return cover[start:end]
    # No anchor, or the end anchor is beyond the cap: the banks are printed
    # immediately above "Prospectus dated".
    p = cover.find("Prospectus dated")
    if p >= 0:
        return cover[max(0, p - UNDERWRITER_SEGMENT_CHARS):p]
    return ""


def _underwriters(cover: str) -> List[str]:
    """The banks named in the cover's list, in the order they are printed.

    A longer name always wins over a shorter alias printed inside it
    ("Roth Capital" over "Roth", "RBC Capital Markets" over "RBC"), so one
    bank is listed once.
    """
    segment = _underwriter_segment(cover)
    if not segment:
        return []
    spans = []
    for name, rx in _UNDERWRITER_RX:
        for m in rx.finditer(segment):
            spans.append((m.start(), m.end(), name))
    out: List[str] = []
    for start, end, name in sorted(spans):
        if any(s <= start and end <= e and (e - s) > (end - start)
               for s, e, _n in spans):
            continue                                   # an alias inside a longer name
        if name not in out:
            out.append(name)
    return out


# ── headlines ───────────────────────────────────────────────────────────────
async def headlines(symbol: str, name: str, *, now=None) -> Tuple[list, dict]:
    """Recent headlines for the company name, through the ONE news engine.

    `core.search` only relevance-filters a `ticker` selector, so a `keyword`
    search comes back unfiltered and this caller applies
    `core.relevance_filter` itself. Never raises.
    """
    sym = str(symbol or "").strip().upper()
    short = short_name(name)
    meta: dict = {}
    try:
        res = await core.search(keyword=f'"{short}"',
                                window_hours=HEADLINES_WINDOW_HOURS,
                                now=now, limit=12, audit=AUDIT_TAG)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ipo_upcoming: headlines %s failed: %s", sym, exc)
        return [], meta
    if not isinstance(res, dict):                              # pragma: no cover
        return [], meta
    meta = {"query": res.get("query"), "counts": res.get("counts"),
            "window_hours": res.get("window_hours")}
    try:
        items = core.relevance_filter(res.get("items") or [],
                                      ticker=sym, company=short)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ipo_upcoming: relevance %s failed: %s", sym, exc)
        items = []
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        out.append({"title": it.get("title"), "url": it.get("url"),
                    "source": it.get("source"), "published": it.get("published")})
    return out, meta


# ── the cache ───────────────────────────────────────────────────────────────
def _coll():
    try:
        from sepa.prices import _get_mongo
        pc = _get_mongo()
        return None if pc is None else pc.database[CACHE_COLL]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ipo_upcoming: mongo unavailable: %s", exc)
        return None


def _serve(doc: dict, row: dict, cached: bool) -> dict:
    """The wire payload. Nothing from the filing is a number."""
    doc = doc if isinstance(doc, dict) else {}
    return {
        "ok": True,
        "symbol": doc.get("_id"),
        "calendar_row": row,
        "company": doc.get("company"),
        "filing": doc.get("filing"),
        "headlines": doc.get("headlines") or [],
        "headlines_window_days": HEADLINES_WINDOW_DAYS,
        "headlines_at": _iso(doc.get("headlines_at")),
        "resolution": doc.get("resolution") or dict(_EMPTY_RESOLUTION),
        "error": doc.get("error"),
        "cached": bool(cached),
        "resolved_at": _iso(doc.get("resolved_at")),
        "sources": doc.get("sources") or dict(_EMPTY_SOURCES),
        "note": NOTE,
    }


def _parse_failure_block(lp: dict, reason: str) -> dict:
    """A filing block that still links the document but carries no facts.

    `parse_note` is what makes the next resolve fetch it again: a failure is
    never kept as a fact.
    """
    block = _filing_head(lp)
    block.update({k: None for k in EXTRACT_KEYS})
    block["underwriters"] = []
    block["parse_note"] = reason
    return block


async def lookup(symbol: str, row: dict, *, now: Optional[float] = None) -> dict:
    """The fact sheet for ONE expected listing. Never raises.

    Cold: full-text search → confirm the CIK → submissions → the newest
    registration document → strip and read it in a thread → headlines. Warm:
    zero network.
    """
    sym = str(symbol or "").strip().upper()
    row = row if isinstance(row, dict) else {}
    now = time.time() if now is None else float(now)
    name = row.get("name") or ""

    coll = _coll()
    doc = None
    if coll is not None:
        try:
            found = coll.find_one({"_id": sym})
            doc = found if isinstance(found, dict) else None
        except Exception as exc:                               # noqa: BLE001
            log.warning("ipo_upcoming: cache read %s failed: %s", sym, exc)
            doc = None

    prev_resolved = (doc or {}).get("resolved_at")
    prev_headlines_at = (doc or {}).get("headlines_at")
    fresh_resolve = bool(
        doc is not None and prev_resolved is not None
        and doc.get("name") == row.get("name")
        and (now - float(prev_resolved)) < CACHE_TTL_SEC)
    fresh_headlines = bool(
        doc is not None and prev_headlines_at is not None
        and (now - float(prev_headlines_at)) < CACHE_TTL_SEC)

    if fresh_resolve and fresh_headlines:
        # The ONE zero-network path — the only one that may say `cached`.
        return _serve(doc, row, cached=True)

    new = dict(doc) if doc else {}
    new["_id"] = sym
    new["name"] = row.get("name")
    new.setdefault("headlines", [])
    new["resolved_at"] = prev_resolved
    new["headlines_at"] = prev_headlines_at

    if not fresh_resolve:
        await _resolve(new, doc, sym, name, now)

    if fresh_headlines:
        new["headlines"] = (doc or {}).get("headlines") or []
    else:
        items, _meta = await headlines(sym, name, now=now)
        new["headlines"] = items
        new["headlines_at"] = now

    # What is STORED can keep more than what is SERVED. A zero-hit answer from
    # EDGAR (or a filer with no registration form on record) serves
    # `filing: None` with its sentence — but it must not ERASE a block that
    # parsed cleanly on an earlier day: the next EDGAR-down call would then
    # have nothing to show, and the accession reuse would be lost with it.
    # (Verify miss, 2026-09-20.) A failure is never kept as a fact; a fact is
    # never thrown away by a failure.
    stored = dict(new)
    old_block = (doc or {}).get("filing")
    if (stored.get("filing") is None and isinstance(old_block, dict)
            and old_block.get("accession") and old_block.get("parse_note") is None):
        stored["filing"] = old_block

    if coll is not None:
        try:
            coll.replace_one({"_id": sym}, stored, upsert=True)
        except Exception as exc:                               # noqa: BLE001
            log.warning("ipo_upcoming: cache write %s failed: %s", sym, exc)

    return _serve(new, row, cached=False)


def _edgar_down(new: dict, doc: Optional[dict], what: str) -> None:
    """EDGAR did not answer. `resolved_at` is NOT advanced — a 30-second blip
    is a 30-second blip, never a day of `cached: true`."""
    stale = (doc or {}).get("filing")
    if isinstance(stale, dict) and stale.get("parse_note") is None:
        new["filing"] = stale
        new["company"] = (doc or {}).get("company")
        new["resolution"] = (doc or {}).get("resolution") or dict(_EMPTY_RESOLUTION)
        new["error"] = ("EDGAR could not be reached; showing the filing cached "
                        f"{_iso((doc or {}).get('resolved_at'))}")
    else:
        new["filing"] = None
        new["company"] = None
        new["error"] = f"EDGAR could not be reached: {what}"


async def _resolve(new: dict, doc: Optional[dict], sym: str, name: str,
                   now: float) -> None:
    """One resolve pass. Mutates `new`; every outcome is a sentence."""
    sources = dict(_EMPTY_SOURCES)
    resolution = dict(_EMPTY_RESOLUTION)
    new["sources"] = sources
    new["resolution"] = resolution
    new["error"] = None
    new["company"] = None
    new["filing"] = None

    hits, url = await fts_search(name, today=ipo._today())
    sources["edgar_search_url"] = url or None
    resolution["query"] = f'"{str(name or "").strip()}"'

    if hits is None:
        _edgar_down(new, doc, "the full-text search did not answer")
        return

    resolution["hits"] = len(hits)
    hit, reason = pick_hit(hits, symbol=sym, name=name)
    if hit is None:
        resolution["reason"] = reason
        new["error"] = NO_HIT_ERROR
        return                                     # NOT cached: no resolved_at

    resolution["method"] = hit.get("method")
    sub = await submissions(hit.get("cik") or "")
    if sub is None:
        _edgar_down(new, doc, "the submissions record did not answer")
        return

    sources["submissions_url"] = _submissions_url(str(hit.get("cik") or "").zfill(10))
    new["company"] = company_block(sub)

    lp = latest_prospectus(sub)
    if lp is None:
        resolution["reason"] = "the filer has no registration filing on record"
        new["company"] = None
        new["error"] = NO_HIT_ERROR
        return                                     # NOT cached: no resolved_at

    sources["filing_url"] = lp.get("url")
    old = (doc or {}).get("filing")
    if (isinstance(old, dict) and old.get("accession") == lp.get("accession")
            and old.get("parse_note") is None):
        filing = old                               # a clean block, kept
    else:
        html, why = await fetch_prospectus_html(lp.get("url") or "")
        if html is None:
            filing = _parse_failure_block(lp, why or "the document could not be read")
        else:
            extracted = await asyncio.to_thread(parse_filing, html, symbol=sym)
            filing = _filing_head(lp)
            filing.update(extracted)
            filing["parse_note"] = None

    # A name-only match whose filing names a DIFFERENT symbol is not this
    # company. Both sides are already normalised (the full stop inside the
    # closing quote is stripped at capture), so "AMRO." never reads as a
    # mismatch against AMRO.
    in_filing = filing.get("symbol_in_filing")
    if resolution.get("method") == "name" and in_filing and in_filing != sym:
        new["filing"] = None
        new["error"] = (f"the registration filing found for this name names the "
                        f"symbol {in_filing}, not {sym}; not shown")
    else:
        new["filing"] = filing

    # The resolve SUCCEEDED — this is the one path that advances the clock.
    # The mismatch above is a fact that was read, not a failure.
    new["resolved_at"] = now
