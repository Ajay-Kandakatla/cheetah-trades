"""🏛️ POTUS / federal-stake headline watch — a REGEX, not a signal.

Ajay 2026-09-20: *"Anytime POTUS does new investments show me those"*.

WHAT THIS IS. Once a day the cron runs a handful of keyword searches through
``news_search`` and classifies the TITLES. A headline that names a federal
agency AND a stated size AND resolves to a ticker that is not already on the
curated list becomes a CANDIDATE. Candidates are shown on the 🏛️ POTUS tab.
Only the tightest class — an equity stake, named agency, stated size, resolved
ticker — is allowed to page the phone.

WHAT THIS IS NOT. It is not measured, it is not backtested, and it is not a
buy. A title-matching regex has no record and this module never claims one.
Nothing here edits ``disclosures.json``: promoting a candidate onto the curated
list is a human edit plus a re-run of ``scripts.gen_political_ts``.

RESOLUTION. 1.1% of the titles these queries return carry a cashtag or an
exchange tag (measured on 377 titles, 2026-09-20), so a tag-only extractor
would answer his ask with nothing. The fallback is a reverse index built from
``sepa.company_names.all_names()`` intersected with the ``full`` universe:
longest name first, whole-phrase, suffixes stripped. One-word names are kept
only at ≥ 6 characters, so "Apple", "Target" and "Visa" never fire off a common
English word. That is a PARSER rule, not a threshold on a signal. A classified
headline whose company is outside the index is STILL stored — with
``ticker: None`` and ``resolution: "unnamed"`` — because "we saw this and could
not name it" is the honest row, and a wrong ticker is the alternative.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import string
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("political.watch")

KIND = "potus_investment"
COLL = "political_candidates"
WINDOW_HOURS = 24

#: The searches. Keyword queries, not tickers — the government names the
#: company, not the ticker. Confirm the wording with Ajay before changing it
#: (§7.4 of the 2026-09-20 spec: the wording is HIS call).
WATCH_QUERIES: tuple[str, ...] = (
    '"equity stake" government company',
    '"Department of Commerce" stake',
    '"Department of Defense" OR Pentagon equity stake',
    '"Department of Energy" OR DOE stake company',
    'Treasury "equity stake"',
    '"golden share"',
    'Trump family stock stake disclosure',
)

AGENCY_RE = r"\b(Commerce|Department of Commerce|DoD|Department of Defense|Pentagon|DOE|Department of Energy|Energy Department|Treasury)\b"
SIZE_RE = r"(\$\s?\d[\d,.]*\s?(million|billion|bn|m)\b|\b\d{1,2}(\.\d+)?\s?%)"

PATTERNS: dict[str, str] = {
    "equity_stake": r"\b(equity stake|stake in|takes? (a )?\d+(\.\d+)?% stake|acquires? \d+(\.\d+)?%|golden share|government (will )?(own|owns|take)|warrants?)\b",
    "federal_award": r"\b(award(ed)?|contract|grant|loan)\b",
    "potus_family": r"\b(Trump|Kushner|Vance)\b.*\b(disclos|stake|bought|purchas|holding)",
}

#: Evaluated in THIS order, first match wins. "Trump administration takes 10%
#: stake in Intel" is an equity_stake — the administration acting IS the
#: government investing, and filing it under potus_family would hide the exact
#: event he asked to be told about.
PATTERN_ORDER: tuple[str, ...] = ("equity_stake", "federal_award", "potus_family")

TICKER_RE = r"\$([A-Z]{1,5})\b|\((?:NASDAQ|NYSE|NYSE American|AMEX):\s*([A-Z]{1,5})\)"

#: Trailing corporate suffixes stripped before matching, so "MP Materials Inc"
#: in the cache matches "MP Materials" in a headline.
_NAME_SUFFIXES: tuple[str, ...] = ("inc", "corp", "corporation", "co", "ltd", "plc",
                                   "holdings", "group", "company", "technologies",
                                   "nv", "sa")

#: A one-word company name shorter than this is NOT indexed. "Apple", "Target",
#: "Visa" and "Block" are ordinary English before they are tickers.
MIN_ONE_WORD_NAME = 6

_AGENCY = re.compile(AGENCY_RE, re.I)
_SIZE = re.compile(SIZE_RE, re.I)
_TICKER = re.compile(TICKER_RE)
_COMPILED = {k: re.compile(v, re.I) for k, v in PATTERNS.items()}

NOTE = ("Headline classifier — a regex over titles, NOT a measured signal. "
        "A push needs a named agency AND a stated size in the same headline.")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime] = None) -> str:
    return (dt or _now_utc()).replace(microsecond=0).isoformat()


def _owner() -> str:
    """The one address these pushes go to. Imported, never retyped."""
    from growth.alerts import OWNER
    return OWNER


# ── classification ──────────────────────────────────────────────────────────

def classify(title: str) -> Optional[dict]:
    """``{"pattern", "agency", "size"}`` for a title that matches one of the
    PATTERNS, else None. PURE.

    Precedence is PATTERN_ORDER, not dict order: a headline that is both an
    equity stake and a Trump mention is an equity stake."""
    if not title:
        return None
    for name in PATTERN_ORDER:
        rx = _COMPILED.get(name)
        if rx is None or not rx.search(title):
            continue
        agency = _AGENCY.search(title)
        size = _SIZE.search(title)
        return {"pattern": name,
                "agency": agency.group(0) if agency else None,
                "size": size.group(0).strip() if size else None}
    return None


def is_pushable(c: Optional[dict]) -> bool:
    """The phone gate, and NOTHING looser: an EQUITY STAKE, a NAMED agency, a
    STATED size, and a ticker we actually resolved. A federal award is not a
    stake; "weighing a stake" is not a stake; an unnamed company is not a
    position he can act on."""
    if not isinstance(c, dict):
        return False
    return bool(c.get("pattern") == "equity_stake"
                and c.get("agency") and c.get("size") and c.get("ticker"))


# ── the reverse company-name index ──────────────────────────────────────────

_PUNCT = str.maketrans({ch: " " for ch in string.punctuation})


def _strip_name(name: str) -> str:
    """Lower-cased, punctuation removed, trailing corporate suffixes dropped."""
    words = (name or "").lower().translate(_PUNCT).split()
    while words and words[-1] in _NAME_SUFFIXES:
        words.pop()
    return " ".join(words)


def _name_index(names: Optional[dict] = None) -> list[tuple[str, str]]:
    """``[(stripped_name, TICKER)]`` sorted LONGEST FIRST.

    ``names`` defaults to ``company_names.all_names()`` intersected with the
    ``full`` universe. ``all_names()`` is CACHE-ONLY — ``bulk_warm`` is never
    called on this path — so a cold cache simply shrinks the index and more
    headlines land as ``unnamed``. That is the intended failure direction."""
    if names is None:
        from sepa import company_names, universe
        try:
            allowed = {s.upper() for s in universe.load_universe("full")}
        except Exception as exc:          # a universe read must not kill the run
            log.warning("political.watch: universe load failed (%s)", exc)
            allowed = set()
        cached = company_names.all_names() or {}
        names = {s.upper(): n for s, n in cached.items()
                 if not allowed or s.upper() in allowed}
    out: list[tuple[str, str]] = []
    for sym, name in (names or {}).items():
        key = _strip_name(name)
        if not key:
            continue
        if len(key.split()) == 1 and len(key) < MIN_ONE_WORD_NAME:
            continue
        out.append((key, sym.upper()))
    out.sort(key=lambda kv: (-len(kv[0]), kv[0]))
    return out


def tickers_in(title: str, index: Optional[list] = None) -> dict:
    """``{"by_tag": [...], "by_name": [...]}`` — tags first, then whole-phrase
    company names longest-first. A ticker appears at most once, and never in
    both lists."""
    by_tag: list[str] = []
    for m in _TICKER.finditer(title or ""):
        sym = (m.group(1) or m.group(2) or "").upper()
        if sym and sym not in by_tag:
            by_tag.append(sym)
    by_name: list[str] = []
    hay = " " + _strip_name(title or "") + " "
    for key, sym in (index or []):
        if sym in by_tag or sym in by_name:
            continue
        if f" {key} " in hay:
            by_name.append(sym)
    return {"by_tag": by_tag, "by_name": by_name}


# ── storage ─────────────────────────────────────────────────────────────────

def _coll(coll=None):
    if coll is not None:
        return coll
    try:
        from sepa.prices import _get_mongo
        price_cache = _get_mongo()
        if price_cache is None:
            return None
        return price_cache.database[COLL]
    except Exception as exc:
        log.warning("political.watch: Mongo unavailable (%s)", exc)
        return None


def _resolvable(symbol: str, resolve=None) -> bool:
    """A ticker we can actually show. The stub ``companies.store.get`` returns
    for an unknown symbol carries ``refreshed_at: None`` — that is a REJECT,
    not a name. A rate-limited day therefore rejects rather than inventing a
    company; the same headline is only re-evaluated when a NEW url names it
    (dedupe is on (ticker, url))."""
    if resolve is not None:
        return bool(resolve(symbol))
    try:
        from companies import store
        doc = store.get(symbol) or {}
    except Exception as exc:
        log.warning("political.watch: company lookup failed for %s (%s)", symbol, exc)
        return False
    return doc.get("refreshed_at") is not None


def candidates(coll=None, limit: int = 200) -> list[dict]:
    """Stored candidates, newest first — what the board renders."""
    c = _coll(coll)
    if c is None:
        return []
    try:
        rows = list(c.find({}, {"_id": 0}).sort("first_seen", -1).limit(limit))
    except Exception as exc:
        log.warning("political.watch: candidate read failed (%s)", exc)
        return []
    return rows


def last_run(coll=None) -> Optional[str]:
    c = _coll(coll)
    if c is None:
        return None
    try:
        row = c.find_one({"_id": "__last_run__"})
    except Exception:
        return None
    return (row or {}).get("at")


# ── the pass ────────────────────────────────────────────────────────────────

def run(*, dry_run: bool = False, now=None, search=None, resolve=None,
        names=None, coll=None, push=None) -> dict:
    """One pass over WATCH_QUERIES. Every dependency is injectable; the cron
    passes none.

    Returns counts: ``{queries, headlines, candidates_new, unnamed, pushed,
    rejected_unresolved}``."""
    if search is None:
        from news_search import search_sync as search      # lazy: P1's routine
    if push is None:
        from push.sender import send_to_user as push
    on_list = set()
    try:
        from political.disclosures import by_ticker
        on_list = set(by_ticker().keys())
    except Exception as exc:
        log.error("political.watch: could not read the curated list (%s) — "
                  "refusing to run rather than re-propose every row", exc)
        return {"queries": 0, "headlines": 0, "candidates_new": 0, "unnamed": 0,
                "pushed": 0, "rejected_unresolved": 0, "error": str(exc)}

    index = _name_index(names)
    c = _coll(coll)
    stamp = _iso(now)
    counts = {"queries": 0, "headlines": 0, "candidates_new": 0, "unnamed": 0,
              "pushed": 0, "rejected_unresolved": 0}
    seen_urls: set[str] = set()

    for query in WATCH_QUERIES:
        counts["queries"] += 1
        try:
            res = search(keyword=query, window_hours=WINDOW_HOURS,
                         relevance="none", audit="potus_watch") or {}
        except Exception as exc:
            log.warning("political.watch: query %r failed (%s)", query, exc)
            continue
        for item in (res.get("items") or []):
            title = (item.get("title") or "").strip()
            url = (item.get("url") or "").strip()
            if not title or not url:
                continue
            counts["headlines"] += 1
            hit = classify(title)
            if not hit:
                continue
            found = tickers_in(title, index)
            resolution = "tag" if found["by_tag"] else ("name" if found["by_name"] else "unnamed")
            syms = found["by_tag"] or found["by_name"]
            headline = {"title": title, "url": url,
                        "source": item.get("source"),
                        "published": item.get("published")}

            if not syms:
                key = f"|{url}"
                if key in seen_urls:
                    continue
                seen_urls.add(key)
                counts["unnamed"] += 1
                _upsert(c, key, {"ticker": None, "resolution": "unnamed",
                                 "company": None, "headline": headline,
                                 "pattern": hit["pattern"], "agency": hit["agency"],
                                 "size": hit["size"], "query": query,
                                 "heuristic": True}, stamp, dry_run)
                continue

            for sym_raw in syms:
                from sepa.symbols import resolve as resolve_symbol
                sym = resolve_symbol(sym_raw)
                if sym in on_list:
                    continue
                key = f"{sym}|{url}"
                if key in seen_urls:
                    continue
                seen_urls.add(key)
                if not _resolvable(sym, resolve):
                    counts["rejected_unresolved"] += 1
                    continue
                doc = {"ticker": sym, "resolution": resolution,
                       "company": _company_for(sym, index),
                       "headline": headline, "pattern": hit["pattern"],
                       "agency": hit["agency"], "size": hit["size"],
                       "query": query, "heuristic": True}
                inserted = _upsert(c, key, doc, stamp, dry_run)
                if inserted:
                    counts["candidates_new"] += 1
                gate = dict(hit)
                gate["ticker"] = sym
                if is_pushable(gate) and not dry_run and not _already_pushed(c, key):
                    body = (f"{title} — heuristic headline match, not a signal")
                    res_push = push(_owner(),
                                    {"title": f"🏛️ {sym}: federal stake reported",
                                     "body": body,
                                     "url": "/chart-maps?tab=potus"},
                                    kind=KIND)
                    if _terminal(res_push):
                        counts["pushed"] += 1
                        _mark_pushed(c, key)

    if not dry_run and c is not None:
        try:
            c.update_one({"_id": "__last_run__"}, {"$set": {"at": stamp}}, upsert=True)
        except Exception as exc:
            log.warning("political.watch: last_run stamp failed (%s)", exc)
    return counts


def _company_for(symbol: str, index) -> Optional[str]:
    try:
        from sepa.company_names import name_for
        return name_for(symbol)
    except Exception:
        return None


def _terminal(res) -> bool:
    """Delivered, or nobody targeted — both mean 'do not retry'. Reused from
    ``supply_demand.demand_alerts`` so there is one definition."""
    from supply_demand.demand_alerts import _terminal as t
    return t(res)


def _upsert(coll, key: str, doc: dict, stamp: str, dry_run: bool) -> bool:
    """True when the row is NEW. A dry run reports the row as new without
    writing (nothing to dedupe against)."""
    if coll is None or dry_run:
        return True
    try:
        res = coll.update_one({"_id": key},
                              {"$set": doc,
                               "$setOnInsert": {"first_seen": stamp, "pushed": False}},
                              upsert=True)
        return bool(getattr(res, "upserted_id", None))
    except Exception as exc:
        log.warning("political.watch: upsert %s failed (%s)", key, exc)
        return False


def _already_pushed(coll, key: str) -> bool:
    if coll is None:
        return False
    try:
        row = coll.find_one({"_id": key}, {"pushed": 1})
    except Exception:
        return False
    return bool((row or {}).get("pushed"))


def _mark_pushed(coll, key: str) -> None:
    if coll is None:
        return
    try:
        coll.update_one({"_id": key}, {"$set": {"pushed": True}})
    except Exception as exc:
        log.warning("political.watch: pushed flag failed (%s)", exc)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="🏛️ POTUS / federal-stake headline watch")
    ap.add_argument("--dry-run", action="store_true",
                    help="classify and print, write nothing, push nothing")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    counts = run(dry_run=args.dry_run)
    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
