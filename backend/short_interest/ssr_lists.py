"""⛔ SSR — the exchanges' official short sale circuit breaker lists (SEC Rule 201) (2026-11-23).

THE ASK (Ajay 2026-11-23, verbatim)
  "No shorting at the bid (SEC short-sale restriction)

   Can we check or this for other stocks too?"

What this module is: the OFFICIAL half of the ⛔ SSR tag. It reads the two exchange groups' daily Rule 201 lists —
Nasdaq (`shorthalts%Y%m%d.txt`, CSV) and NYSE Group (`NYSEGroupSSRCircuitBreakers%Y%m%d.xls`, BIFF8 through the house
reader `biff_rows`) — keeps one Mongo doc per source per FILE date (never purged) and answers `ssr.py` through the
FROZEN interface below. It types no served tag word except the source rows' texts; `ssr.py` builds the tag.

The read never makes an outside call: the ONE single-flight daemon worker (`kick_refresh`, the `reg_sho` shape) is
kicked from `ssr.payload`, throttled, calendar aware — 0 outside list calls once both files of both sources are
final. Its LAST job is the corporate-action read (`ssr_corp.refresh_due`), in its own fenced try: a missing or raising
`ssr_corp` never stops or fails the list refresh [C1b].

DISPLAY ONLY. Nothing here gates, sorts, sizes, pushes or enters a lane. UNMEASURED.

FACTS (measured 2026-11-23 21:08–22:20 ET, docs/short_interest/ssr_official_lists_2026_11_24.md):
  * Nasdaq file(D) holds the rows triggered on prev trading day AND D; editions seen 04:15 ET (only the carried
    prior-day rows) and 16:30 ET (+ today's). The 16:30 edition and the next morning's file differ by a few rows both
    ways → Nasdaq's record of trigger day T is complete ONLY with file(next_market_day(T)) [C4]; `final` only stops
    the re-fetch of a file, it never completes a day.
  * Nasdaq TRAP: at 22:10 ET the URL still served the 04:15 edition while Nasdaq's page listed a 16:30 file → the
    edition is read from the 14-digit TRAILER, never from the clock.
  * Nasdaq "no file" = HTTP 302 to /Trader.aspx?id=http404 (the reg_sho answer); NYSE "no file" = HTTP 404.
  * NYSE file(D) holds only D's triggers, published ≈ 20:06–21:18 ET; Anticipated Deactivation Date = the 2nd trading
    day after the trigger (the exchange's own "rest of the day + the next trading day").
"""
from __future__ import annotations

import csv
import importlib
import io
import logging
import re
import threading
import time
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from zoneinfo import ZoneInfo

from short_interest import biff_rows as BIFF
from short_interest import read as SR
from short_interest import reg_sho as RS

log = logging.getLogger("short_interest.ssr_lists")

SSR_COLL = "ssr_rule_201"                      # ONE collection; kinds: list, state (this module) · corp, corpstate (ssr_corp.py) · trig, day, judged (ssr.py)
NO_LIST_NYSE_404 = "nyse_404"
SOURCES = (
    {"key": "nasdaq", "exchange": "Nasdaq", "format": "nasdaq_csv",
     "url": "https://www.nasdaqtrader.com/dynamic/symdir/shorthalts/shorthalts%Y%m%d.txt",
     "no_list": RS.NO_LIST_NASDAQ_302, "first_hm": (4, 20), "carries_prior_day": True, "editions": True},
    {"key": "nyse", "exchange": "NYSE Group", "format": "nyse_xls",
     "url": ("https://ftp.nyse.com/NYSEGroupSSRCircuitBreakers/NYSEGroupSSRCircuitBreakers_%Y/"
             "NYSEGroupSSRCircuitBreakers_%Y%m/NYSEGroupSSRCircuitBreakers%Y%m%d.xls"),
     "no_list": NO_LIST_NYSE_404, "first_hm": (20, 10), "carries_prior_day": False, "editions": False},
)
NASDAQ_HEADER = "Symbol,Security Name,Market Category,Trigger Time"
NYSE_HEADER = ("Trigger Date", "Issue Symbol", "Issue Name", "Primary Exchange", "SSR State", "Trigger Time",
               "Anticipated Deactivation Date")
NYSE_EXCHANGES = {"NYSE": "NYSE", "MKT": "NYSE American", "P": "NYSE Arca"}   # an unseen code prints as itself
NYSE_ACTIVE_STATE = "A"                        # the only SSR State seen (11/20, 11/23); any other is skipped and counted

# engineering — MINE (HIS CALL 13); none is a trading threshold
SL_HTTP_TIMEOUT_SEC = 6          # hard timeout per outside call
SL_REFRESH_BUDGET_SEC = 45       # wall budget of one refresh round
SL_RETRY_MIN = 30                # minutes between attempts for one (source, file date)
SL_ERROR_RETRY_MIN = 5           # the first retries after an error
SL_ERROR_STRIKES = 2             # errors in a row before the long wait (and before a source reads failed)
SL_KICK_MIN_SEC = 60             # in-process floor between two worker starts
SL_RETRY_AFTER_SEC = 20          # served to the FE while a refresh runs
SL_MAX_BYTES = 2_000_000
SL_MAX_ROWS = 20_000
SL_MAX_SKIPPED_ROWS = 10         # more skipped rows than this = a malformed file
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ssr-reader)"}        # no project name, no email
RETRY_AFTER_SEC = SL_RETRY_AFTER_SEC           # the FROZEN name ssr.py reads

# served source texts (M/D via SR._md)
SRC_OK = "%s short sale list for %s · edition %s ET · %s rows"
SRC_PRE_CLOSE = " (today's triggers not in it yet)"
SRC_NOT_PUBLISHED = "%s short sale list for %s not published yet (after %s ET)"
SRC_FAILED_HELD = "%s short sale list could not be read — last good list %s"
SRC_PENDING = "%s short sale list not read yet"

_ET = ZoneInfo("America/New_York")
_http = None                     # the ONE outside-call seam; None → requests.get (lazy import)
_TRAILER = re.compile(r"^\d{14}$")
_NASDAQ_TIME = "%m/%d/%Y %I:%M:%S %p"
_NYSE_DATE = "%m/%d/%Y"
_HMS = re.compile(r"^\d{2}:\d{2}:\d{2}$")


Malformed = RS.Malformed                       # the reg_sho class: an untrustworthy file is never read as an empty list


# ───────────────────────────────────────────── seams
def _mono() -> float:
    return time.monotonic()


def _resolve_http(http):
    if http is not None:
        return http
    if _http is not None:
        return _http
    import requests                                            # lazy: the read never needs it
    return requests.get


def _cal():
    """The ONE house calendar (catalysts.medical.reaction), imported lazily."""
    from catalysts.medical import reaction as R
    return R


def source(key: str) -> dict:
    for s in SOURCES:
        if s["key"] == key:
            return s
    raise KeyError(key)


def source_url(src: dict, d: date) -> str:
    return d.strftime(src["url"])


def _first_dt(src: dict, d: date) -> datetime:
    hh, mm = src["first_hm"]
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=_ET)


def _hm(hh: int, mm: int) -> str:
    return "%02d:%02d" % (hh, mm)


# ───────────────────────────────────────────── calendar
def file_dates(now_et) -> list:
    """[prev_market_day(L), L] — L = today when a market day, else the market day before. The days kept fresh."""
    R = _cal()
    today = RS._to_et(now_et).date()
    L = today if R.is_market_day(today) else R.prev_market_day(today)
    return [R.prev_market_day(L), L]


def _stamp_dt(stamp) -> Optional[datetime]:
    s = str(stamp or "")
    if not _TRAILER.match(s):
        return None
    try:
        return datetime.strptime(s, "%Y%m%d%H%M%S").replace(tzinfo=_ET)
    except ValueError:
        return None


def is_final(src: dict, doc: Optional[dict]) -> bool:
    """nasdaq: the stamp is dated the file date at/after its regular close; nyse: the file exists. Stops the
    re-fetch of THAT file only — never completes a trigger day [C4]."""
    if not doc:
        return False
    if not src.get("editions"):
        return True
    st = _stamp_dt(doc.get("stamp"))
    fd = RS._as_date(doc.get("file_date"))
    if st is None or fd is None or st.date() != fd:
        return False
    return st.time() >= _cal().rth_close_time(fd)


# ───────────────────────────────────────────── parse
def parse_nasdaq(text: str, want: date) -> tuple:
    """(rows, stamp, skipped) — row = (norm symbol, "YYYY-MM-DD", "HH:MM:SS", market category). Raises Malformed."""
    if not isinstance(text, str):
        raise Malformed("not text")
    if len(text.encode("utf-8", "replace")) > SL_MAX_BYTES:
        raise Malformed("oversize")
    try:
        lines = [r for r in csv.reader(io.StringIO(text.lstrip("﻿")))]
    except csv.Error:
        raise Malformed("csv")
    lines = [r for r in lines if any(c.strip() for c in r)]
    if len(lines) < 2:
        raise Malformed("too short")
    want_cells = [c.strip().lower() for c in NASDAQ_HEADER.split(",")]
    if [c.strip().lower() for c in lines[0]] != want_cells:
        raise Malformed("header")
    trailer = lines[-1]
    stamp = trailer[0].strip() if len(trailer) == 1 else ""
    if not _TRAILER.match(stamp) or stamp[:8] != want.strftime("%Y%m%d"):
        raise Malformed("trailer")
    body = lines[1:-1]
    if len(body) > SL_MAX_ROWS:
        raise Malformed("too many rows")
    prev = _cal().prev_market_day(want)
    ok_dates = {want, prev}
    rows = []
    skipped = 0
    for cells in body:
        if len(cells) != 4:
            skipped += 1
            continue
        sym = RS.norm_symbol(cells[0])
        try:
            t = datetime.strptime(cells[3].strip(), _NASDAQ_TIME)
        except ValueError:
            skipped += 1
            continue
        if not sym or t.date() not in ok_dates:
            skipped += 1
            continue
        rows.append((sym, t.date().isoformat(), t.strftime("%H:%M:%S"), cells[2].strip()))
    if skipped > SL_MAX_SKIPPED_ROWS:
        raise Malformed("too many skipped rows")
    if body and not rows:
        raise Malformed("every row skipped")
    return rows, stamp, skipped


def parse_nyse(data: bytes, want: date) -> tuple:
    """(rows, skipped) — row = (norm symbol, "YYYY-MM-DD", "HH:MM:SS", exchange name, deactivation "YYYY-MM-DD").
    Raises Malformed; any reader error is Malformed (an unreadable file is an ERROR, never an empty list)."""
    if not isinstance(data, (bytes, bytearray)):
        raise Malformed("not bytes")
    if len(data) > SL_MAX_BYTES:
        raise Malformed("oversize")
    try:
        grid = BIFF.read_rows(bytes(data))
    except Exception as exc:                                   # noqa: BLE001
        raise Malformed("reader: %s" % exc)

    def cells_of(row) -> tuple:
        out = [("" if c is None else str(c).strip()) for c in row]
        while out and not out[-1]:
            out.pop()
        return tuple(out)

    grid = [cells_of(r) for r in grid]
    grid = [r for r in grid if r]
    if not grid:
        raise Malformed("empty sheet")
    if grid[0] != NYSE_HEADER:
        raise Malformed("header")
    body = grid[1:]
    if len(body) > SL_MAX_ROWS:
        raise Malformed("too many rows")
    rows = []
    skipped = 0
    for cells in body:
        if len(cells) != len(NYSE_HEADER):
            skipped += 1
            continue
        tdate, sym, _name, code, state, ttime, deact = cells
        try:
            td = datetime.strptime(tdate, _NYSE_DATE).date()
            dd = datetime.strptime(deact, _NYSE_DATE).date()
        except ValueError:
            skipped += 1
            continue
        norm = RS.norm_symbol(sym)
        if not norm or not _HMS.match(ttime) or state != NYSE_ACTIVE_STATE or td != want:
            skipped += 1
            continue
        rows.append((norm, td.isoformat(), ttime, NYSE_EXCHANGES.get(code, code), dd.isoformat()))
    if skipped > SL_MAX_SKIPPED_ROWS:
        raise Malformed("too many skipped rows")
    if body and not rows:
        raise Malformed("every row skipped")
    return rows, skipped


def _nyse_stamp(headers) -> Optional[str]:
    """NYSE has no trailer: its edition = the file's Last-Modified, in ET, as the 14-digit stamp."""
    lm = headers.get("Last-Modified") or headers.get("last-modified")
    if not lm:
        return None
    try:
        dt = parsedate_to_datetime(str(lm))
    except (TypeError, ValueError, IndexError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_ET).strftime("%Y%m%d%H%M%S")


# ───────────────────────────────────────────── fetch (never raises)
def fetch(src: dict, d: date, *, http=None, etag=None) -> dict:
    """found (rows, stamp, etag, skipped, url) · unchanged (304) · missing (the measured "no file") · error."""
    url = source_url(src, d)
    headers = dict(HTTP_HEADERS)
    if etag:
        headers["If-None-Match"] = str(etag)
    try:
        call = _resolve_http(http)
        resp = call(url, headers=headers, timeout=SL_HTTP_TIMEOUT_SEC, allow_redirects=False)
        status = int(getattr(resp, "status_code", 0) or 0)
        rh = getattr(resp, "headers", None) or {}
    except Exception as exc:                                   # noqa: BLE001
        name = type(exc).__name__
        log.warning("ssr_lists: %s %s fetch failed: %s", src["key"], d, name)
        return {"result": "error", "error": "timeout" if "timeout" in name.lower() else "exception"}
    try:
        if status == 200:
            body = getattr(resp, "content", None)
            if body is None:
                body = (getattr(resp, "text", "") or "").encode("utf-8")
            if len(body) > SL_MAX_BYTES:
                raise Malformed("oversize")
            new_etag = rh.get("ETag") or rh.get("etag") or None
            if src["format"] == "nasdaq_csv":
                rows, stamp, skipped = parse_nasdaq(bytes(body).decode("utf-8", "replace"), d)
            else:
                rows, skipped = parse_nyse(bytes(body), d)
                stamp = _nyse_stamp(rh)
            return {"result": "found", "rows": rows, "stamp": stamp, "etag": new_etag, "skipped": skipped,
                    "url": url}
        if status == 304:
            return {"result": "unchanged", "url": url}
        if status == 302:
            loc = str(rh.get("Location") or rh.get("location") or "")
            if src["no_list"] == RS.NO_LIST_NASDAQ_302 and "id=http404" in loc:
                return {"result": "missing"}
            return {"result": "error", "error": "redirect"}
        if status == 404:
            if src["no_list"] == NO_LIST_NYSE_404:
                return {"result": "missing"}
            return {"result": "error", "error": "unseen_404"}
        return {"result": "error", "error": "http_%d" % status}
    except Malformed as exc:
        log.warning("ssr_lists: %s %s malformed: %s", src["key"], d, exc)
        return {"result": "error", "error": "malformed"}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ssr_lists: %s %s read failed: %s", src["key"], d, type(exc).__name__)
        return {"result": "error", "error": "exception"}


# ───────────────────────────────────────────── Mongo (find with projection, find_one by _id, replace_one, create_index)
def _list_id(key: str, d) -> str:
    return "list|%s|%s" % (key, d.isoformat() if isinstance(d, date) else d)


def _state_id(key: str, d) -> str:
    return "state|%s|%s" % (key, d.isoformat() if isinstance(d, date) else d)


_dec_lock = threading.Lock()
_decoded: dict = {}                              # list _id → (rev, [row dicts]) — decoded once per rev


def _reset_cache() -> None:
    with _dec_lock:
        _decoded.clear()


def _decode(doc: dict) -> list:
    src = source(doc["source"])
    out = []
    for r in doc.get("rows") or []:
        if not isinstance(r, (list, tuple)) or len(r) < 4:
            continue
        exch = src["exchange"] if src["key"] == "nasdaq" else str(r[3])
        out.append({"_sym": RS.norm_symbol(r[0]), "source": src["key"], "exchange": exch,
                    "trigger_date": str(r[1]), "trigger_time": str(r[2]),
                    "file_date": str(doc.get("file_date")), "stamp": doc.get("stamp")})
    return out


def _rows_of(coll, lid: str, rev) -> list:
    with _dec_lock:
        hit = _decoded.get(lid)
        if hit is not None and hit[0] == rev:
            return hit[1]
    full = coll.find_one({"_id": lid})
    if not full:
        return []
    rows = _decode(full)
    with _dec_lock:
        _decoded[lid] = (full.get("rev"), rows)
    return rows


def load(coll, now_et) -> dict:
    """Mongo reads only — {"days": [file dates], "lists": {(src, iso): doc w/o rows}, "states": {(src, iso): doc},
    "index": {norm symbol: [row dicts]}, "read": bool}. coll None → an empty, unread load; a raising coll raises."""
    days = file_dates(now_et)
    out = {"days": [d.isoformat() for d in days], "lists": {}, "states": {}, "index": {}, "read": False}
    if coll is None:
        return out
    ids = [f(s["key"], d) for s in SOURCES for d in days for f in (_list_id, _state_id)]
    docs = list(coll.find({"_id": {"$in": ids}}, {"rows": 0}))
    index: dict = {}
    keep = set()
    for doc in docs:
        k = (doc.get("source"), doc.get("file_date"))
        if doc.get("kind") == "state":
            out["states"][k] = doc
            continue
        if doc.get("kind") != "list":
            continue
        out["lists"][k] = doc
        keep.add(doc["_id"])
        for row in _rows_of(coll, doc["_id"], doc.get("rev")):
            index.setdefault(row["_sym"], []).append(row)
    with _dec_lock:
        for lid in [x for x in _decoded if x not in keep]:
            _decoded.pop(lid, None)
    out["index"] = index
    out["read"] = True
    return out


def rows_for(loaded: dict, sym) -> list:
    """Every stored row of the symbol (norm + alias keys), newest trigger first, one per (source, trigger date,
    trigger time) — the union of file(T) and file(next T); the newest file's copy is kept."""
    norm = RS.norm_symbol(sym)
    if not norm:
        return []
    index = loaded.get("index") or {}
    seen = {}
    for k in {RS.norm_symbol(a) for a in RS.alias_keys(norm)}:
        for row in index.get(k) or []:
            key = (row["source"], row["trigger_date"], row["trigger_time"])
            have = seen.get(key)
            if have is None or str(row["file_date"]) > str(have["file_date"]):
                seen[key] = row
    out = [{k: v for k, v in r.items() if k != "_sym"} for r in seen.values()]
    out.sort(key=lambda r: (r["trigger_date"], r["trigger_time"], r["file_date"], r["source"]), reverse=True)
    return out


def symbols_on(loaded: dict, T) -> list:
    """Every stored list symbol (norm spelling) with a row whose trigger date is T, sorted — the ONE enumerator by
    trigger date (`rows_for` looks up by symbol; 2026-11-24 ssrlist §3.1). Reads `loaded["index"]` only: no Mongo, no
    outside call. An unread / empty load, or an unreadable T → []."""
    if isinstance(T, datetime):
        T = T.date()
    iso = T.isoformat() if isinstance(T, date) else ""
    if not iso or not isinstance(loaded, dict):
        return []
    index = loaded.get("index") or {}
    if not isinstance(index, dict):
        return []
    out = set()
    for sym, rows in index.items():
        if not isinstance(sym, str) or not sym:
            continue
        for r in rows or ():
            if isinstance(r, dict) and str(r.get("trigger_date")) == iso:
                out.add(sym)
                break
    return sorted(out)


def complete_for(loaded: dict, T: date) -> bool:
    """EVERY source holds a complete record of trigger day T: nasdaq ONLY via file(next_market_day(T)) (any
    edition) — file(T)'s 16:30 edition never completes T [C4]; nyse via file(T)."""
    lists = loaded.get("lists") or {}
    nxt = _cal().next_market_day(T)
    for src in SOURCES:
        fd = nxt if src.get("carries_prior_day") else T
        if (src["key"], fd.isoformat()) not in lists:
            return False
    return True


def is_due(src: dict, d: date, loaded: dict, now_et) -> bool:
    now_et = RS._to_et(now_et)
    doc = (loaded.get("lists") or {}).get((src["key"], d.isoformat()))
    if is_final(src, doc):
        return False
    if now_et < _first_dt(src, d):
        return False
    state = (loaded.get("states") or {}).get((src["key"], d.isoformat()))
    if not state:
        return True
    if state.get("result") == "error" and int(state.get("errors") or 0) < SL_ERROR_STRIKES:
        wait = SL_ERROR_RETRY_MIN
    else:
        wait = SL_RETRY_MIN
    age = RS._age_min(state.get("attempt_at"), now_et)
    return age is None or age >= wait


def any_due(loaded: dict, now_et) -> bool:
    return any(is_due(src, d, loaded, now_et) for src in SOURCES for d in file_dates(now_et))


# ───────────────────────────────────────────── refresh
def refresh_one(src: dict, d: date, coll, now_et, *, http=None) -> Optional[dict]:
    """One (source, file date) attempt. Returns the state doc it wrote (None when abandoned)."""
    now_et = RS._to_et(now_et)
    now_iso = RS._utc_iso(now_et)
    key = src["key"]
    sid = _state_id(key, d)
    lid = _list_id(key, d)
    try:
        prev = coll.find_one({"_id": sid})
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ssr_lists: %s %s state read failed: %s", key, d, type(exc).__name__)
        return None
    errors = int((prev or {}).get("errors") or 0)
    state = {"_id": sid, "kind": "state", "source": key, "file_date": d.isoformat(), "attempt_at": now_iso,
             "result": "running", "error": None, "errors": errors}
    try:
        coll.replace_one({"_id": sid}, dict(state), upsert=True)     # BEFORE the first outside call (reg_sho.py:430)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ssr_lists: %s %s state write failed, abandoned: %s", key, d, type(exc).__name__)
        return None

    result, err = "error", None
    try:
        held = coll.find_one({"_id": lid})
        got = fetch(src, d, http=http, etag=(held or {}).get("etag"))
        result = got["result"]
        if result == "found":
            stamp = got.get("stamp") or now_et.strftime("%Y%m%d%H%M%S")
            held_stamp = str((held or {}).get("stamp") or "")
            if held and held_stamp and stamp < held_stamp:
                result = "older_edition"                       # the stale-edition trap: never replace a newer one
            else:
                rows = [list(r) for r in got["rows"]]
                editions = list((held or {}).get("editions") or [])
                if stamp not in editions:
                    editions.append(stamp)
                doc = {"_id": lid, "kind": "list", "source": key, "file_date": d.isoformat(), "stamp": stamp,
                       "final": False, "etag": got.get("etag"), "url": got.get("url"),
                       "rows": rows, "n": len(rows), "skipped": int(got.get("skipped") or 0),
                       "fetched_at": now_iso, "first_fetched_at": (held or {}).get("first_fetched_at") or now_iso,
                       "editions": editions, "rev": "%s|%d" % (stamp, len(rows))}
                doc["final"] = is_final(src, doc)
                coll.replace_one({"_id": lid}, doc, upsert=True)
        elif result == "unchanged" and not held:
            result, err = "error", "unexpected_304"
        elif result == "error":
            err = got.get("error") or "error"
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ssr_lists: %s %s refresh failed: %s", key, d, type(exc).__name__)
        result, err = "error", "exception"
    finally:
        state["result"] = result
        state["error"] = err if result == "error" else None
        state["errors"] = errors + 1 if result == "error" else 0
        try:
            coll.replace_one({"_id": sid}, dict(state), upsert=True)
        except Exception as exc:                               # noqa: BLE001
            log.warning("ssr_lists: %s %s final state write failed: %s", key, d, type(exc).__name__)
    return state


def refresh_due(coll, now_et=None, *, http=None, corp=None) -> dict:
    """Refresh every due (source, file date), then — its OWN fenced try — the corporate-action read
    `ssr_corp.refresh_due(coll, file_dates(now_et), now_et, http=http)` [C1b]. `corp=None` = the real module (a lazy
    import); a missing or raising one never fails the list refresh. Never raises.
    {"ran": ["nasdaq|2026-11-23", …], "calls": n, "seconds": s, "corp": <its answer or None>}."""
    t0 = _mono()
    now_et = RS._to_et(now_et)
    calls = {"n": 0}
    out = {"ran": [], "calls": 0, "seconds": 0.0, "corp": None}
    base = None
    try:
        base = _resolve_http(http)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ssr_lists: no http client: %s", type(exc).__name__)

    def counted(url, **kw):
        calls["n"] += 1
        return base(url, **kw)

    if base is not None:
        try:
            try:
                coll.create_index([("kind", 1), ("source", 1), ("file_date", -1)])
            except Exception:                                  # noqa: BLE001
                pass
            loaded = load(coll, now_et)
            deadline = t0 + SL_REFRESH_BUDGET_SEC
            for src in SOURCES:
                for d in file_dates(now_et):
                    if not is_due(src, d, loaded, now_et):
                        continue
                    if _mono() > deadline:
                        break
                    refresh_one(src, d, coll, now_et, http=counted)
                    out["ran"].append("%s|%s" % (src["key"], d.isoformat()))
        except Exception as exc:                               # noqa: BLE001
            log.warning("ssr_lists: refresh round failed: %s", type(exc).__name__)
    out["calls"] = calls["n"]

    try:                                                       # [C1b] the worker's LAST job, its OWN try
        mod = corp if corp is not None else importlib.import_module("short_interest.ssr_corp")
        out["corp"] = mod.refresh_due(coll, file_dates(now_et), now_et, http=http)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ssr_lists: the corporate-action read did not run: %s", type(exc).__name__)
    out["seconds"] = round(_mono() - t0, 3)
    return out


# One worker at a time (the reg_sho.kick_refresh shape) + a floor between starts.
_bg_lock = threading.Lock()
_bg = {"running": False, "last_start": None, "thread": None}


def worker_running() -> bool:
    with _bg_lock:
        return bool(_bg["running"])


def kick_refresh(coll, now_et=None, *, http=None) -> bool:
    """True = a worker was started."""
    with _bg_lock:
        if _bg["running"]:
            return False
        last = _bg["last_start"]
        if last is not None and _mono() - last < SL_KICK_MIN_SEC:
            return False
        _bg["running"] = True
        _bg["last_start"] = _mono()

    def run():
        try:
            refresh_due(coll, now_et, http=http)
        except Exception as exc:                               # pragma: no cover
            log.warning("ssr_lists: worker failed: %s", type(exc).__name__)
        finally:
            with _bg_lock:
                _bg["running"] = False

    try:
        t = threading.Thread(target=run, daemon=True, name="ssr-lists-refresh")
        t.start()
    except Exception as exc:                                   # noqa: BLE001
        with _bg_lock:
            _bg["running"] = False
            _bg["last_start"] = last
        log.warning("ssr_lists: worker could not start: %s", type(exc).__name__)
        return False
    _bg["thread"] = t
    return True


# ───────────────────────────────────────────── served source rows
def _edition(stamp) -> Optional[str]:
    st = _stamp_dt(stamp)
    return st.strftime("%H:%M") if st else None


def source_views(loaded: dict, now_et) -> list:
    """One served row per source: {key, exchange, ok, status: ok|pending|failed, as_of, edition_et, final, n, error,
    text}. Describes the newest file date L; when L is not held, the file before it."""
    now_et = RS._to_et(now_et)
    lists = loaded.get("lists") or {}
    states = loaded.get("states") or {}
    prev_d, L = file_dates(now_et)
    out = []
    for src in SOURCES:
        key, ex = src["key"], src["exchange"]
        cur = lists.get((key, L.isoformat()))
        older = lists.get((key, prev_d.isoformat()))
        st = states.get((key, L.isoformat()))
        st_err = st is not None and st.get("result") == "error"
        error = (st.get("error") or None) if st_err else None
        doc = cur or older
        if cur:
            status = "ok"
            text = SRC_OK % (ex, SR._md(L.isoformat()), _edition(cur.get("stamp")) or "?", int(cur.get("n") or 0))
            if src.get("editions") and not is_final(src, cur):
                text += SRC_PRE_CLOSE
        elif st_err and int(st.get("errors") or 0) >= SL_ERROR_STRIKES:
            status = "failed"
            text = (SRC_FAILED_HELD % (ex, SR._md(prev_d.isoformat()))) if older else (SRC_PENDING % ex)
        elif now_et < _first_dt(src, L) or (st is not None and st.get("result") == "missing"):
            status = "ok" if older else "pending"
            text = SRC_NOT_PUBLISHED % (ex, SR._md(L.isoformat()), _hm(*src["first_hm"]))
        else:
            status = "pending"
            text = SRC_PENDING % ex
        out.append({"key": key, "exchange": ex, "ok": status == "ok", "status": status,
                    "as_of": doc.get("file_date") if doc else None,
                    "edition_et": _edition(doc.get("stamp")) if doc else None,
                    "final": is_final(src, doc) if doc else False,
                    "n": int(doc.get("n") or 0) if doc else 0,
                    "error": error, "text": text})
    return out
