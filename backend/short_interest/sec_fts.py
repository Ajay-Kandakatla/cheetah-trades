"""🩳 6-K issuance reader — SEC full-text search (2026-11-26, spec sishares §3.1 + §3.3, work package be-io).

Ajay 2026-11-26: "Fix the POM chip and the 6-K dilution check."

A foreign issuer reports a share issuance in a 6-K, which carries no item numbers, so the filing listing alone cannot
tell an issuance 6-K from a press release. The SEC document host (the EDGAR Archives) answers 403 to the house's
generic User-Agent, so the 6-K text is never read here. The SEC full-text search (efts.sec.gov) answers that User-Agent; it returns which DOCUMENTS of a
filer match a query, never their text. Two queries:

  * the issuance phrase family (FTS_ISSUANCE_PHRASES, OR) over the filer's 6-Ks in the fetch window;
  * the exact share count added (format(n, ",")), only when a share-count growth is on file;
  * ✂️ 2026-11-27 (spec sicheck §3.3): the split-word family (FTS_SPLIT_PHRASES, OR), a hit kept only on a document
    type of FTS_SPLIT_DOC_TYPES — stored as `sec.fts_split`, a sibling of `sec.fts`. It finds MENTIONS: a proposal, a
    vote notice and an executed split all match.

This module holds NO http client: every call goes through the getter it is handed (share_basis passes
`lambda url: share_basis._sec_get(url, http)` — ONE pacer, the generic headers, the `_http` seam the test session
refuses). It names one host, efts.sec.gov. basis_math is reached only lazily (`holds`, `default_growth_fn`).
"""
from __future__ import annotations

import re
import urllib.parse
from datetime import date, datetime, timezone
from typing import Callable, Optional

# ───────────────────────────────────────────── constants
FTS_URL = "https://efts.sec.gov/LATEST/search-index"
FTS_WHEN = "on"                     # HIS CALL #3 — one of FTS_MODES; "off" (or any other value) = no efts call
FTS_MODES = ("off", "on")
FTS_ISSUANCE = "issuance"           # the marker on a 6-K row found by the phrase query (== basis_math.FTS_ISSUANCE)
FTS_GOOD = ("ok", "none_6k")        # a good read (the status rule) (== basis_math.FTS_KNOWN_STATUSES)
# MINE — the 9 phrases probed on POM 2026-11-26: they hit only the 11-04 debt-conversion 6-K of nine POM 6-Ks, and only
# the 10-20 Item 3.02 8-K of five NCPL 8-Ks (tests/fixtures/sec_6k_text_pom_2026_11_26.json). HIS CALL #4.
FTS_ISSUANCE_PHRASES = ("agreed to issue", "issued an aggregate", "private placement", "registered direct",
                        "securities purchase agreement", "debt conversion", "at-the-market", "exercise of warrants",
                        "subscription agreement")
FTS_FORMS = ("6-K",)
# ✂️ 2026-11-27 (spec sicheck §3.3, C1) — the 6-K SPLIT-WORD read, stored as `sec.fts_split` (a SIBLING of `sec.fts`;
# `sec.fts`, FTS_ISSUANCE_PHRASES and read_issuance are not changed). HIS CALL #11 — "off" (or any other word) = no call.
FTS_SPLIT_WHEN = "on"
FTS_SPLIT_MODES = ("off", "on")
# MINE — the phrases the probe gate ADMITTED on 2026-11-27 (9 efts GETs: 3 candidates × BDMD / POM / NXAT, raw answers in
# tests/fixtures/sec_6k_split_probe_2026_11_27.json): "share consolidation" and "reverse stock split" hit none of the
# must-NOT filings once FTS_SPLIT_DOC_TYPES is applied; "reverse share split" is OUT (it hits NXAT 10-05's EX-99.2, a
# warrant exchange). Together they hit the three must-hits BDMD 11-16, POM 10-19, NXAT 11-13.
FTS_SPLIT_PHRASES = ("share consolidation", "reverse stock split")
# MINE — a hit counts only on the report itself or an EX-99 exhibit: a contract or instrument exhibit (EX-10, EX-4)
# carries adjustment boilerplate (BDMD 09-30 matches only in EX-10.1 / EX-10.2).
FTS_SPLIT_DOC_TYPES = ("6-K", "EX-99")
FTS_DESC_MAX = 120                 # MINE — chars of an exhibit description kept (display only)
FTS_TZ = "America/New_York"         # SEC filing dates are Eastern dates
ACCN_RE = re.compile(r"^\d{10}-\d{2}-\d{6}$")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ───────────────────────────────────────────── small helpers (never raise)
def fts_on(mode=None) -> bool:
    """True only for the exact word "on" — any other value behaves as "off" (no call)."""
    return (FTS_WHEN if mode is None else mode) == "on"


def _day(v) -> Optional[str]:
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if not isinstance(v, str):
        return None
    s = v.strip()[:10]
    if not DAY_RE.match(s):
        return None
    try:
        return date.fromisoformat(s).isoformat()
    except ValueError:
        return None


def _et():
    from zoneinfo import ZoneInfo                              # lazy
    return ZoneInfo(FTS_TZ)


def et_day(v) -> Optional[str]:
    """The Eastern calendar date of a timestamp (a tz-naive value is UTC, the house's stored stamp), else None."""
    if isinstance(v, str) and v.strip():
        try:
            v = datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(v, datetime):
        return None
    if v.tzinfo is None:
        v = v.replace(tzinfo=timezone.utc)
    try:
        return v.astimezone(_et()).date().isoformat()
    except (OverflowError, ValueError, OSError):
        return None


def _base(form) -> str:
    b = form.strip().upper() if isinstance(form, str) else ""
    return b[:-2].strip() if b.endswith("/A") else b


def is_6k(form) -> bool:
    """A 6-K or 6-K/A."""
    return _base(form) in FTS_FORMS


def _plain_file(v) -> Optional[str]:
    if not isinstance(v, str):
        return None
    s = v.strip()
    return s if s and "/" not in s and "\\" not in s and ".." not in s else None


def _int(v) -> Optional[int]:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _code(resp) -> int:
    try:
        return int(getattr(resp, "status_code", 0) or 0)
    except (TypeError, ValueError):
        return 0


# ───────────────────────────────────────────── queries
def phrase_query(phrases) -> str:
    """'"a" OR "b" …' — each phrase quoted (a phrase holding a double quote is dropped)."""
    ps = [p.strip() for p in phrases or () if isinstance(p, str) and p.strip() and '"' not in p]
    return " OR ".join('"%s"' % p for p in ps)


def number_query(n) -> str:
    """'"33,185,841"' — the count as a filing prints it."""
    return '"%s"' % format(n, ",")


def url_of(q: str, cik10: str, since: str, today: str) -> str:
    return FTS_URL + "?" + urllib.parse.urlencode({"q": q, "forms": ",".join(FTS_FORMS), "ciks": cik10,
                                                   "dateRange": "custom", "startdt": since, "enddt": today})


# ───────────────────────────────────────────── the answer
def parse_hits(body) -> dict:
    """{"rows": [{accn, file, filed, form, file_type, desc}], "total": int}; a junk hit is dropped. Raises ValueError
    when the answer has no `hits.total` / `hits.hits` of the documented shape."""
    if not isinstance(body, dict) or not isinstance(body.get("hits"), dict):
        raise ValueError("no hits")
    h = body["hits"]
    tot = h.get("total")
    total = _int(tot.get("value")) if isinstance(tot, dict) else _int(tot)
    arr = h.get("hits")
    if total is None or total < 0 or not isinstance(arr, list):
        raise ValueError("no hits")
    rows = []
    for x in arr:
        if not isinstance(x, dict):
            continue
        src = x.get("_source") if isinstance(x.get("_source"), dict) else {}
        hid = x.get("_id") if isinstance(x.get("_id"), str) else ""
        accn, _, file = hid.partition(":")
        adsh = src.get("adsh")
        accn = (adsh if isinstance(adsh, str) else accn).strip()
        filed = _day(src.get("file_date"))
        if not ACCN_RE.match(accn) or filed is None:
            continue
        form = src.get("form") if isinstance(src.get("form"), str) else None
        ft = src.get("file_type") if isinstance(src.get("file_type"), str) else None
        desc = src.get("file_description") if isinstance(src.get("file_description"), str) else None
        rows.append({"accn": accn, "file": _plain_file(file), "filed": filed, "form": form.strip() if form else None,
                     "file_type": ft.strip() if ft else None, "desc": desc.strip() if desc else None})
    return {"rows": rows, "total": total}


def by_accession(rows, reports) -> list:
    """One row per accession that IS a 6-K / 6-K/A of the filer's own listing (`reports`) — a hit on anything else is
    dropped. {"form", "filed" (both from the listing), "accn", "doc" (the listing's primary document, else the 6-K
    document hit), "ex": [{"type", "desc"}] (the other documents hit, in answer order)}; filed DESC."""
    rep: dict = {}
    for r in reports or []:
        if isinstance(r, dict) and isinstance(r.get("accn"), str) and is_6k(r.get("form")) and _day(r.get("filed")):
            rep.setdefault(r["accn"], r)
    groups: dict = {}
    for x in rows or []:
        if isinstance(x, dict) and x.get("accn") in rep:
            groups.setdefault(x["accn"], []).append(x)
    out = []
    for accn, xs in groups.items():
        r = rep[accn]
        primary = _plain_file(r.get("doc"))
        doc, ex, seen = primary, [], set()
        for x in xs:
            f = x.get("file")
            if (primary and f == primary) or is_6k(x.get("file_type")):
                doc = doc or f
                continue
            if f in seen:
                continue
            seen.add(f)
            ex.append({"type": x.get("file_type") or "", "desc": (x.get("desc") or "")[:FTS_DESC_MAX]})
        out.append({"form": r["form"].strip(), "filed": _day(r["filed"]), "accn": accn, "doc": doc, "ex": ex})
    out.sort(key=lambda z: z["filed"], reverse=True)
    return out


def _ask(q, cik10, since, today, get: Callable):
    """(parsed, None) | (None, failed dict). Never raises; an error is the HTTP code or the exception TYPE only."""
    try:
        r = get(url_of(q, cik10, since, today))
        code = _code(r)
        if code != 200:
            return None, {"status": "failed", "error": "http_%d" % code, "code": code}
        return parse_hits(r.json()), None
    except Exception as exc:                                   # noqa: BLE001
        return None, {"status": "failed", "error": type(exc).__name__, "code": None}


def read_issuance(cik10, since, today, reports, *, get: Callable) -> dict:
    """ONE phrase query → {"status": "ok", "issuance": [...][, "cap": rows returned when the total is larger]}
    | {"status": "failed", "error", "code"}."""
    p, bad = _ask(phrase_query(FTS_ISSUANCE_PHRASES), cik10, since, today, get)
    if bad:
        return bad
    out = {"status": "ok", "issuance": by_accession(p["rows"], reports)}
    if p["total"] > len(p["rows"]):
        out["cap"] = len(p["rows"])
    return out


def split_on(mode=None) -> bool:
    """✂️ The split-word switch: True only for the exact word "on" (FTS_SPLIT_WHEN read at call time)."""
    m = FTS_SPLIT_WHEN if mode is None else mode
    return m in FTS_SPLIT_MODES and m == FTS_SPLIT_MODES[1]


def split_doc_ok(file_type) -> bool:
    """✂️ A matching document of an allowed type: upper-cased, equal to or starting with one of FTS_SPLIT_DOC_TYPES
    ("6-K", "6-K/A", "EX-99.1" → True; "EX-10.1", "EX-4.1", None, "" → False)."""
    if not isinstance(file_type, str) or not file_type.strip():
        return False
    t = file_type.strip().upper()
    return any(t == k or t.startswith(k) for k in FTS_SPLIT_DOC_TYPES)


def read_split(cik10, since, today, reports, *, get: Callable) -> dict:
    """✂️ ONE phrase query (FTS_SPLIT_PHRASES, OR) → {"status": "ok", "rows": [by_accession rows][, "cap": raw rows
    returned when the total is larger]} | {"status": "failed", "error", "code"}. The raw hit rows are filtered by
    `split_doc_ok` BEFORE `by_accession`: a filing kept only by a contract exhibit is dropped."""
    p, bad = _ask(phrase_query(FTS_SPLIT_PHRASES), cik10, since, today, get)
    if bad:
        return bad
    kept = [r for r in p["rows"] if split_doc_ok(r.get("file_type"))]
    out = {"status": "ok", "rows": by_accession(kept, reports)}
    if p["total"] > len(p["rows"]):
        out["cap"] = len(p["rows"])
    return out


def read_number(cik10, n, since, today, reports, *, get: Callable) -> dict:
    """ONE exact-number query → {"status": "ok", "hits": [{accn, filed, form, doc}]} (6-Ks of the listing only)
    | {"status": "failed", "error", "code"}."""
    p, bad = _ask(number_query(n), cik10, since, today, get)
    if bad:
        return bad
    return {"status": "ok", "hits": [{"accn": r["accn"], "filed": r["filed"], "form": r["form"], "doc": r["doc"]}
                                     for r in by_accession(p["rows"], reports)]}


# ───────────────────────────────────────────── caching
def holds(top_filed, read_at, hit) -> bool:
    """[C8] A held answer stands when it HIT the newest 6-K (`hit is True`), or when it was read (Eastern date) after
    the day after that 6-K was filed (BM.day_after). A no-hit read made on the filing day or the day after is asked
    again — the index lag is unknown. Junk dates → not held."""
    d, r = _day(top_filed), et_day(read_at)
    if d is None or r is None:
        return False
    if hit is True:
        return True
    from short_interest import basis_math as BM                # lazy
    return r > BM.day_after(d)


def growth_numbers(growth) -> Optional[tuple]:
    """(n, from, to) — n = to_shares − from_shares, all whole share counts and n > 0 — else None."""
    if not isinstance(growth, dict):
        return None
    a, b = _int(growth.get("from_shares")), _int(growth.get("to_shares"))
    if a is None or b is None or a <= 0 or b - a <= 0:
        return None
    return b - a, a, b


def default_growth_fn():
    """fn(rec, doc, today) -> the verdict's share-count growth dict | None (lazy basis_math; keeps share_basis.py at
    exactly its two basis_math import lines)."""
    from short_interest import basis_math as BM                # lazy

    def growth(rec, doc, today):
        v = BM.verdict(rec, doc, today)
        g = v.get("growth") if isinstance(v, dict) else None
        return g if isinstance(g, dict) else None
    return growth


# ───────────────────────────────────────────── TEST-ONLY local matcher
def text_matches(text, phrases) -> list:
    """The phrases found in `text` — case-insensitive, whitespace collapsed, on word edges. Used only to check the
    phrase list on saved filing texts; never on a live path."""
    if not isinstance(text, str):
        return []
    t = re.sub(r"\s+", " ", text).lower()
    out = []
    for p in phrases or ():
        if not isinstance(p, str) or not p.strip():
            continue
        q = re.escape(re.sub(r"\s+", " ", p.strip().lower()))
        if re.search(r"(?<![a-z0-9])" + q + r"(?![a-z0-9])", t):
            out.append(p)
    return out
