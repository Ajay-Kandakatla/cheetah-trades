"""🔒 HARD TO BORROW — the Reg SHO threshold-security read (2026-11-22).

THE ASK (Ajay 2026-11-22, verbatim)
  "Can you do something for me for reversal squeezes can you also tell me if
   something is under when it's on our list.. i want to check if people are
   finding it hard to get stocks like AkAN now has that issue.. add a tag to
   stocks tickers like short interest, name the tag " hard to borrow"
   threshold security"

What this module is: the ONE engine behind the 🔒 tag. It reads the exchanges'
daily Reg SHO threshold lists (Nasdaq, NYSE, NYSE American, NYSE Arca, Cboe
BZX — three keyless public hosts), keeps one Mongo doc per market per trade
date (NEVER purged: `fetched_at` is the point-in-time record a later study
would need) and serves ONE whole-list read, `GET /short-interest/reg-sho`.
Every word the front end prints is built here; it types none.

DISPLAY ONLY. Nothing here gates, sorts, sizes, pushes or enters a lane.
UNMEASURED on this app's universe. The threshold list measures persistent
fails to deliver (SEC Regulation SHO Rule 203(c)(6)), not a broker's borrow
rate — a broker's own hard-to-borrow list can differ.

The read never makes an outside call: a due list is refreshed by ONE
single-flight daemon worker kicked from the read (the
`supply_demand.bounce_room.queue_ondemand` shape), throttled and calendar
aware — 0 outside calls when no newer list can exist.

TRAPS (measured 2026-11-22, see docs/gajjala/hard_to_borrow_reg_sho_2026_11_22.md):
  * Nasdaq "no file" is HTTP 302 to /Trader.aspx?id=http404 — never a 404, so
    requests always pass allow_redirects=False.
  * NYSE answers 200 with a header, a synthetic trailer and ZERO rows for a
    weekend, a future date, a bank holiday AND a bogus or lower-cased market
    name — the market value is case-sensitive. "No list" = all three markets
    empty; a zero-row market inside a published group is believed only after
    a second read RS_RETRY_MIN later agrees.
  * Cboe "no file" is HTTP 403 with <Code>AccessDenied</Code>.
  * A plain 404 / NoSuchKey was NEVER seen: it is an error (unseen_404), never
    "no list".
  * Line endings: Nasdaq / Cboe CRLF; NYSE rows LF with a CRLF trailer —
    splitlines() + strip reads all three.
"""
from __future__ import annotations

import logging
import re
import threading
import time
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from short_interest import client as SIC
from short_interest import read as SR

log = logging.getLogger("short_interest.reg_sho")

GLYPH = "🔒"                                  # MINE (HIS CALL #1)
TAG_WORDS = "Hard to borrow"                  # HIS name, verbatim
KIND = "reg_sho_threshold"                    # payload discriminator
RS_COLL = "reg_sho_threshold"                 # Mongo collection
API_PATH = "/short-interest/reg-sho"

# SEC Regulation SHO Rule 203(c)(6) — the SEC's numbers, enforced by the exchanges, DESCRIBED here, never compared
REG_SHO_RULE = "SEC Regulation SHO Rule 203(c)(6)"
REG_SHO_MIN_FTD_SHARES = 10_000
REG_SHO_MIN_PCT_SHARES_OUT = 0.5
REG_SHO_CONSEC_SETTLEMENT_DAYS = 5

# [C2] the NYSE query value IS the exchange name, EXACT CASE — measured: "nyse american" answers 200 with zero rows
NYSE_MARKETS = (("nyse", "NYSE"), ("nyse_american", "NYSE American"), ("nyse_arca", "NYSE Arca"))
# [C3] which NYSE markets may raise the fault line (NYSE Arca = a fund list)
NYSE_FAULTS = {"nyse": True, "nyse_american": True, "nyse_arca": False}

# engineering constants — MINE, none is a trading threshold (HIS CALL #5)
RS_HTTP_TIMEOUT_SEC = 6          # hard timeout per outside call
RS_REFRESH_BUDGET_SEC = 45       # wall budget of one refresh round
RS_RETRY_MIN = 30                # minutes between attempts for one source; also the wait before a zero-row list is re-read [C2]
RS_ERROR_RETRY_MIN = 5           # [C8] the first retry after an error
RS_ERROR_STRIKES = 2             # [C8] errors in a row for one trade date before a held list reads failed
RS_KICK_MIN_SEC = 60             # [C7] in-process floor between two worker starts
RS_WALKBACK_BDAYS = 5            # business days walked back for the newest existing list
RS_BEHIND_GRACE_BDAYS = 2        # a list may be this many business days behind before it reads stale / failed
RS_RETRY_AFTER_SEC = 20          # served to the FE while a refresh runs
RS_CHECK_MAX = 50                # ?check= cap
RS_MAX_BYTES = 2_000_000
RS_MAX_ROWS = 5000
RS_MAX_SKIPPED_ROWS = 10         # [C4] more unreadable symbol cells than this = a malformed file
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; reg-sho-reader)"}   # no project name, no email
_ET = ZoneInfo("America/New_York")
_DEFAULT = object()              # [C6] "resolve the house Mongo handle"; None now means ONLY "Mongo is down"
_http = None                     # [C6] the ONE outside-call seam; None → requests.get (lazy import)

NASDAQ_HEADER = "Symbol|Security Name|Market Category|Reg SHO Threshold Flag|Rule 3210|Filler"
NYSE_HEADER = "Symbol|Security Name|Market Category|Reg SHO Threshold Flag|Filler|Filler"
CBOE_HEADER = "Symbol|CompanyName"

# the MEASURED "no list" answers [C10]
NO_LIST_NASDAQ_302 = "nasdaq_302_http404"
NO_LIST_NYSE_EMPTY = "nyse_all_markets_empty"
NO_LIST_CBOE_403 = "cboe_403_access_denied"

SOURCES = (
    {"key": "nasdaq",
     "markets": (("nasdaq", "Nasdaq", True),),
     "url": "https://www.nasdaqtrader.com/dynamic/symdir/regsho/nasdaqth%Y%m%d.txt",
     "header": NASDAQ_HEADER, "flag_col": 3, "market_col": False,
     "no_list": NO_LIST_NASDAQ_302, "publish_hm": (23, 15), "publish_next_bday": False},
    {"key": "nyse",
     "markets": None,                                          # from NYSE_MARKETS at call time
     "url": "https://www.nyse.com/api/regulatory/threshold-securities/download?selectedDate=%Y-%m-%d&market=",
     "header": NYSE_HEADER, "flag_col": 3, "market_col": True,
     "no_list": NO_LIST_NYSE_EMPTY, "publish_hm": (23, 15), "publish_next_bday": False},
    {"key": "cboe_bzx",
     "markets": (("cboe_bzx", "Cboe BZX", False),),
     "url": ("https://cdn.cboe.com/resources/us/equities/market-statistics/reg-sho-threshold/"
             "bzx_equities_reg_sho_threshold_%Y%m%d.txt"),
     "header": CBOE_HEADER, "flag_col": None, "market_col": False,
     "no_list": NO_LIST_CBOE_403, "publish_hm": (3, 30), "publish_next_bday": True},
)

# ───────────────────────────────────────────── words (served; the FE types none)
CHIP_TEXT = "%s %s · threshold security · %s"                       # GLYPH, TAG_WORDS, M/D — cards
SHORT_TEXT = "%s %s · %s"                                            # [C12] GLYPH, TAG_WORDS, M/D — 📋 cell, 👀 tile head
LABEL_TEXT = "%s %s · Reg SHO threshold security · %s list for %s"   # GLYPH, TAG_WORDS, exchange, M/D — the 🎾 card
STALE_WORD = " · stale"                                              # appended to chip, short and label
TITLE_TEXT = ("%s %s — %s is a Reg SHO threshold security on the %s list for %s: fails to deliver of at least %s "
              "shares and at least %g%% of shares outstanding for %d straight settlement days (%s). %s %s")
HONESTY_NOTE = ("The threshold list measures persistent fails to deliver, not a broker's borrow rate — a broker's "
                "own hard-to-borrow list can differ.")
NOT_A_SIGNAL = "A data label, not a signal. UNMEASURED."
STALE_TITLE = " This list could not be refreshed (last good list %s) — the name may have left it."
SRC_OK = "%s threshold list for %s · %d names"
SRC_SKIPPED = " · %d not read"                                       # [C4] appended when skipped > 0
SRC_BEHIND = "%s threshold list for %s · %d names (none published for %s)"
SRC_UNCONFIRMED = "%s threshold list for %s · 0 names (re-reading to confirm)"   # [C2]
SRC_FAILED_HELD = "%s threshold list could not be read — last good list %s"
SRC_FAILED = "%s threshold list could not be read"
SRC_PENDING = "%s threshold list not read yet"
FAULT_TEXT = "%s %s tags may be missing or out of date: %s."          # GLYPH, TAG_WORDS, faulting markets' texts "; "
FAULT_UNREADABLE = "%s %s tags could not be read — a missing tag does not mean the name is off the list."   # [C1]

_SYMBOL_CELL = re.compile(r"^[A-Z0-9][A-Z0-9 ./\-+$^=#]{0,14}$")
_TRAILER = re.compile(r"^\d{14}$")
_SEP_RUN = re.compile(r"[ ./\-]+")


class Malformed(ValueError):
    """A file that cannot be trusted as a list (never read as an empty one)."""


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


def _to_et(now) -> datetime:
    if now is None:
        return datetime.now(_ET)
    if now.tzinfo is None:
        return now.replace(tzinfo=_ET)
    return now.astimezone(_ET)


def _utc_iso(now_et: datetime) -> str:
    return now_et.astimezone(timezone.utc).isoformat(timespec="seconds")


def _parse_iso(s) -> Optional[datetime]:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo is not None else d.replace(tzinfo=timezone.utc)


def _age_min(s, now_et: datetime) -> Optional[float]:
    d = _parse_iso(s)
    if d is None:
        return None
    return (now_et - d).total_seconds() / 60.0


def _as_date(s) -> Optional[date]:
    try:
        return date.fromisoformat(str(s)[:10]) if s else None
    except ValueError:
        return None


# ───────────────────────────────────────────── symbols
def norm_symbol(sym) -> str:
    """upper, strip, every run of [space . / -] → "." — "brk-b" / "BRK B" / "BRK/B" → "BRK.B"."""
    return _SEP_RUN.sub(".", str(sym or "").strip().upper()).strip(".")


def alias_keys(norm: str) -> tuple:
    """The house spellings a list name is served under: ("AKAN",) ; ("BRK.B", "BRK-B")."""
    if "." in norm:
        return (norm, norm.replace(".", "-"))
    return (norm,)


# ───────────────────────────────────────────── registry helpers
def source_markets(src: dict) -> tuple:
    """((market key, exchange name, faults), …) for one source, read at call time."""
    if src.get("markets") is None:
        return tuple((k, name, bool(NYSE_FAULTS.get(k, False))) for k, name in NYSE_MARKETS)
    return tuple(src["markets"])


def all_markets() -> list:
    """[(src, market key, exchange, faults)] in registry order — five rows."""
    return [(src, k, ex, f) for src in SOURCES for (k, ex, f) in source_markets(src)]


def _exchange(src: dict, mkt: str) -> str:
    for k, ex, _f in source_markets(src):
        if k == mkt:
            return ex
    raise KeyError(mkt)


def source_url(src: dict, mkt: str, d: date) -> str:
    """[C2] the ONE url builder."""
    base = d.strftime(src["url"])
    if src.get("markets") is None:
        return base + urllib.parse.quote(dict(NYSE_MARKETS)[mkt])
    return base


# ───────────────────────────────────────────── parse
def parse_list(text: str, *, header: str, flag_col: Optional[int], want: date,
               market_name: Optional[str] = None) -> tuple:
    """(sorted unique norm symbols, skipped_rows) — raises Malformed(reason)."""
    if not isinstance(text, str):
        raise Malformed("not text")
    if len(text.encode("utf-8", "replace")) > RS_MAX_BYTES:
        raise Malformed("oversize")
    lines = [ln.strip() for ln in text.lstrip("﻿").splitlines()]
    lines = [ln for ln in lines if ln]
    if len(lines) < 2:
        raise Malformed("too short")
    want_cells = [c.strip().lower() for c in header.split("|")]
    if [c.strip().lower() for c in lines[0].split("|")] != want_cells:
        raise Malformed("header")
    trailer = lines[-1]
    if not _TRAILER.match(trailer) or trailer[:8] != want.strftime("%Y%m%d"):
        raise Malformed("trailer")
    rows = lines[1:-1]
    if len(rows) > RS_MAX_ROWS:
        raise Malformed("too many rows")
    out = set()
    skipped = 0
    for row in rows:
        cells = [c.strip() for c in row.split("|")]
        flag = None
        if flag_col is not None:
            flag = cells[flag_col] if len(cells) > flag_col else None
            if flag not in ("Y", "N"):
                raise Malformed("flag")
        if market_name is not None:
            if len(cells) < 3 or cells[2].lower() != market_name.lower():
                raise Malformed("market")
        if flag == "N":
            continue
        if not _SYMBOL_CELL.match(cells[0]):
            skipped += 1                                       # [C4] skipped and counted, never rewritten
            continue
        out.add(norm_symbol(cells[0]))
    if skipped > RS_MAX_SKIPPED_ROWS:
        raise Malformed("too many unreadable symbols")
    return sorted(out), skipped


def _trailer_of(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


# ───────────────────────────────────────────── calendar (the ONE house calendar)
def publish_dt(src: dict, d: date) -> datetime:
    day = SR.add_business_days(d, 1) if src.get("publish_next_bday") else d
    hh, mm = src["publish_hm"]
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=_ET)


def expected_trade_date(src: dict, now_et: datetime) -> date:
    """The latest business day whose list should be out by now."""
    now_et = _to_et(now_et)
    d = SR.prev_business_day(now_et.date())
    while now_et < publish_dt(src, d):
        d = SR.prev_business_day(d - timedelta(days=1))
    return d


def bdays_between(a: date, b: date) -> int:
    """Business days in (a, b]."""
    n = 0
    d = a
    while d < b:
        d += timedelta(days=1)
        if SR.is_business_day(d):
            n += 1
    return n


# ───────────────────────────────────────────── fetch (never raises)
def fetch_market(src: dict, mkt: str, d: date, *, http=None) -> dict:
    url = source_url(src, mkt, d)
    try:
        call = _resolve_http(http)
        resp = call(url, headers=dict(HTTP_HEADERS), timeout=RS_HTTP_TIMEOUT_SEC, allow_redirects=False)
        status = int(getattr(resp, "status_code", 0) or 0)
        text = getattr(resp, "text", "") or ""
        headers = getattr(resp, "headers", None) or {}
    except Exception as exc:                                   # noqa: BLE001
        name = type(exc).__name__
        log.warning("reg_sho: %s %s fetch failed: %s", src["key"], mkt, name)
        return {"result": "error", "error": "timeout" if "timeout" in name.lower() else "exception"}
    try:
        if status == 200:
            name = _exchange(src, mkt) if src.get("market_col") else None
            syms, skipped = parse_list(text, header=src["header"], flag_col=src["flag_col"], want=d,
                                       market_name=name)
            return {"result": "found", "symbols": syms, "skipped": skipped, "stamp": _trailer_of(text), "url": url}
        if status == 302:
            loc = str(headers.get("Location") or headers.get("location") or "")
            if src["no_list"] == NO_LIST_NASDAQ_302 and "id=http404" in loc:
                return {"result": "missing"}
            return {"result": "error", "error": "redirect"}
        if status == 403:
            if src["no_list"] == NO_LIST_CBOE_403 and "<Code>AccessDenied</Code>" in text:
                return {"result": "missing"}
            return {"result": "error", "error": "http_403"}
        if status == 404:
            return {"result": "error", "error": "unseen_404"}
        return {"result": "error", "error": "http_%d" % status}
    except Malformed as exc:
        log.warning("reg_sho: %s %s %s malformed: %s", src["key"], mkt, d, exc)
        return {"result": "error", "error": "malformed"}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("reg_sho: %s %s read failed: %s", src["key"], mkt, type(exc).__name__)
        return {"result": "error", "error": "exception"}


def fetch_source(src: dict, d: date, *, http=None) -> dict:
    """The source's answer for date d; applies the NYSE group rule."""
    try:
        markets = source_markets(src)
        res = {}
        for mkt, _ex, _f in markets:
            r = fetch_market(src, mkt, d, http=http)
            if r["result"] == "error":
                return {"result": "error", "error": r.get("error") or "error"}
            res[mkt] = r
        if src["no_list"] == NO_LIST_NYSE_EMPTY:
            if all(r["result"] == "found" and not r["symbols"] for r in res.values()):
                return {"result": "missing"}
            return {"result": "found", "markets": res}
        (only,) = res.values()
        if only["result"] == "missing":
            return {"result": "missing"}
        return {"result": "found", "markets": res}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("reg_sho: %s fetch failed: %s", src.get("key"), type(exc).__name__)
        return {"result": "error", "error": "exception"}


# ───────────────────────────────────────────── Mongo (find_one+sort, find states, replace_one upsert, create_index)
_SORT = [("trade_date", -1)]


def _newest_list(coll, mkt: str) -> Optional[dict]:
    return coll.find_one({"kind": "list", "market": mkt}, sort=_SORT)


def _states(coll) -> dict:
    return {d.get("source"): d for d in coll.find({"kind": "state"})}


def load(coll) -> dict:
    """[C9] {"lists": {mkt: newest list doc}, "states": {src: state doc}} — six small reads."""
    lists = {}
    for _src, mkt, _ex, _f in all_markets():
        doc = _newest_list(coll, mkt)
        if doc:
            lists[mkt] = doc
    return {"lists": lists, "states": _states(coll)}


def _held_date(src: dict, lists: dict) -> Optional[date]:
    ds = [_as_date(lists[m].get("trade_date")) for m, _e, _f in source_markets(src) if lists.get(m)]
    ds = [d for d in ds if d]
    return max(ds) if ds else None


def _believed(doc: dict) -> bool:
    return int(doc.get("n") or 0) > 0 or bool(doc.get("confirmed_at"))


# ───────────────────────────────────────────── refresh
def refresh_source(src: dict, coll, now_et: datetime, *, http=None, deadline: Optional[float] = None) -> dict:
    """One source's refresh round. Returns the state doc it wrote (None when abandoned)."""
    now_et = _to_et(now_et)
    now_iso = _utc_iso(now_et)
    key = src["key"]
    E = expected_trade_date(src, now_et)
    sid = "state|%s" % key
    try:
        prev = _states(coll).get(key)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("reg_sho: %s state read failed: %s", key, type(exc).__name__)
        return None
    errors = int(prev.get("errors") or 0) if prev and prev.get("attempt_for") == E.isoformat() else 0
    state = {"_id": sid, "kind": "state", "source": key, "attempt_at": now_iso, "attempt_for": E.isoformat(),
             "result": "running", "error": None, "errors": errors,
             "good_date": (prev or {}).get("good_date"), "checked_at": (prev or {}).get("checked_at")}
    try:
        coll.replace_one({"_id": sid}, dict(state), upsert=True)     # [C7] BEFORE the first outside call
    except Exception as exc:                                   # noqa: BLE001
        log.warning("reg_sho: %s state write failed, source abandoned: %s", key, type(exc).__name__)
        return None

    result, err = "error", None
    try:
        lists = {m: _newest_list(coll, m) for m, _e, _f in source_markets(src)}
        lists = {m: d for m, d in lists.items() if d}
        held = _held_date(src, lists)
        answered = True
        d = E
        for _step in range(RS_WALKBACK_BDAYS + 1):
            if held is not None and d <= held:
                break
            if deadline is not None and _mono() > deadline:
                answered, err = False, "budget"
                break
            got = fetch_source(src, d, http=http)
            if got["result"] == "found":
                for mkt, r in got["markets"].items():
                    n = len(r["symbols"])
                    coll.replace_one({"_id": "list|%s|%s" % (mkt, d.isoformat())}, {
                        "_id": "list|%s|%s" % (mkt, d.isoformat()), "kind": "list", "source": key,
                        "market": mkt, "exchange": _exchange(src, mkt), "trade_date": d.isoformat(),
                        "symbols": list(r["symbols"]), "n": n, "skipped": int(r["skipped"]),
                        "file_stamp": r["stamp"], "url": r["url"], "fetched_at": now_iso,
                        "confirmed_at": now_iso if n > 0 else None, "revised_at": None}, upsert=True)
                held = d
                break
            if got["result"] == "missing":
                d = SR.prev_business_day(d - timedelta(days=1))
                continue
            answered, err = False, got.get("error") or "error"
            break
        else:
            if held is None or held < d:
                answered, err = False, err or "no_list_in_window"

        # [C2] confirm pass: a zero-row list is believed only after a second read
        for mkt, _ex, _f in source_markets(src):
            doc = _newest_list(coll, mkt)
            if not doc or int(doc.get("n") or 0) > 0 or doc.get("confirmed_at"):
                continue
            age = _age_min(doc.get("fetched_at"), now_et)
            if age is None or age < RS_RETRY_MIN:
                continue
            if deadline is not None and _mono() > deadline:
                break
            td = _as_date(doc.get("trade_date"))
            r = fetch_market(src, mkt, td, http=http)
            if r["result"] != "found":
                continue
            new = dict(doc)
            new["confirmed_at"] = now_iso
            if r["symbols"]:
                new.update({"symbols": list(r["symbols"]), "n": len(r["symbols"]), "skipped": int(r["skipped"]),
                            "file_stamp": r["stamp"], "revised_at": now_iso})
            coll.replace_one({"_id": new["_id"]}, new, upsert=True)

        newest = _held_date(src, {m: x for m, x in
                                  ((m, _newest_list(coll, m)) for m, _e, _f in source_markets(src)) if x})
        if newest is not None and newest >= E:
            result, err = "found", None
        elif answered and newest is not None:
            result, err = "missing_walked", None
        else:
            result, err = "error", err or "no_list_in_window"
        state["good_date"] = newest.isoformat() if newest else state.get("good_date")
    except Exception as exc:                                   # noqa: BLE001
        log.warning("reg_sho: %s refresh failed: %s", key, type(exc).__name__)
        result, err = "error", "exception"
    finally:
        state["result"] = result
        state["error"] = err if result == "error" else None
        state["errors"] = errors + 1 if result == "error" else 0
        if result in ("found", "missing_walked"):
            state["checked_at"] = now_iso
        try:
            coll.replace_one({"_id": sid}, dict(state), upsert=True)
        except Exception as exc:                               # noqa: BLE001
            log.warning("reg_sho: %s final state write failed: %s", key, type(exc).__name__)
    return state


def is_due(src: dict, loaded: dict, now_et: datetime) -> bool:
    now_et = _to_et(now_et)
    E = expected_trade_date(src, now_et)
    lists = loaded.get("lists") or {}
    state = (loaded.get("states") or {}).get(src["key"])
    held = _held_date(src, lists)
    if held is None or held < E:
        if not state or state.get("attempt_for") != E.isoformat():
            return True
        if state.get("result") == "error" and int(state.get("errors") or 0) < RS_ERROR_STRIKES:
            wait = RS_ERROR_RETRY_MIN
        else:
            wait = RS_RETRY_MIN
        age = _age_min(state.get("attempt_at"), now_et)
        if age is None or age >= wait:
            return True
    st_age = _age_min(state.get("attempt_at"), now_et) if state else None
    for mkt, _ex, _f in source_markets(src):
        doc = lists.get(mkt)
        if not doc or _believed(doc):
            continue
        age = _age_min(doc.get("fetched_at"), now_et)
        if age is not None and age >= RS_RETRY_MIN and (st_age is None or st_age >= RS_RETRY_MIN):
            return True
    return False


def refresh_due(coll, now_et: Optional[datetime] = None, *, http=None) -> dict:
    """Refresh every due source. {"ran": [keys], "calls": n, "seconds": s}."""
    t0 = _mono()
    now_et = _to_et(now_et)
    calls = {"n": 0}
    out = {"ran": [], "calls": 0, "seconds": 0.0}
    try:
        base = _resolve_http(http)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("reg_sho: no http client: %s", type(exc).__name__)
        return out

    def counted(url, **kw):
        calls["n"] += 1
        return base(url, **kw)

    try:
        try:
            coll.create_index([("kind", 1), ("market", 1), ("trade_date", -1)])
        except Exception:                                      # noqa: BLE001
            pass
        loaded = load(coll)
        deadline = t0 + RS_REFRESH_BUDGET_SEC
        for src in SOURCES:
            if not is_due(src, loaded, now_et):
                continue
            if _mono() > deadline:
                break
            refresh_source(src, coll, now_et, http=counted, deadline=deadline)
            out["ran"].append(src["key"])
    except Exception as exc:                                   # noqa: BLE001
        log.warning("reg_sho: refresh round failed: %s", type(exc).__name__)
    out["calls"] = calls["n"]
    out["seconds"] = round(_mono() - t0, 3)
    return out


# One worker at a time (bounce_room.queue_ondemand shape) + a floor between starts [C7].
_bg_lock = threading.Lock()
_bg = {"running": False, "last_start": None, "thread": None}


def _worker_running() -> bool:
    with _bg_lock:
        return bool(_bg["running"])


def kick_refresh(coll, now_et: Optional[datetime] = None, *, http=None) -> bool:
    """True = a worker was started."""
    with _bg_lock:
        if _bg["running"]:
            return False
        last = _bg["last_start"]
        if last is not None and _mono() - last < RS_KICK_MIN_SEC:
            return False
        _bg["running"] = True
        _bg["last_start"] = _mono()

    def run():
        try:
            refresh_due(coll, now_et, http=http)
        except Exception as exc:                               # pragma: no cover
            log.warning("reg_sho: worker failed: %s", type(exc).__name__)
        finally:
            with _bg_lock:
                _bg["running"] = False

    try:
        t = threading.Thread(target=run, daemon=True, name="reg-sho-refresh")
        t.start()
    except Exception as exc:                                   # noqa: BLE001
        with _bg_lock:
            _bg["running"] = False
            _bg["last_start"] = last
        log.warning("reg_sho: worker could not start: %s", type(exc).__name__)
        return False
    _bg["thread"] = t
    return True


# ───────────────────────────────────────────── the served read
def market_view(src: dict, mkt: str, loaded: dict, now_et: datetime) -> dict:
    now_et = _to_et(now_et)
    E = expected_trade_date(src, now_et)
    held = (loaded.get("lists") or {}).get(mkt)
    state = (loaded.get("states") or {}).get(src["key"])
    st = state if state and state.get("attempt_for") == E.isoformat() else None
    finished = st is not None and st.get("result") != "running"
    faults = next(f for k, _e, f in source_markets(src) if k == mkt)
    hd = _as_date(held.get("trade_date")) if held else None
    if held and hd is None:
        held = None
    gap = bdays_between(hd, E) if hd else 0
    if not held:
        status = "failed" if finished else "pending"
    elif not _believed(held):
        status = "pending"
    elif hd >= E:
        status = "ok"
    elif gap > RS_BEHIND_GRACE_BDAYS:
        status = "failed" if finished else "pending"
    elif st is not None and st.get("result") in ("found", "missing_walked"):
        status = "ok"
    elif st is not None and st.get("result") == "error":
        status = "pending" if int(st.get("errors") or 0) < RS_ERROR_STRIKES else "failed"
    else:
        status = "pending"
    return {
        "status": status,
        "as_of": hd.isoformat() if hd else None,
        "n": int(held.get("n") or 0) if held else 0,
        "skipped": int(held.get("skipped") or 0) if held else 0,
        "behind": bool(held) and gap > 0,
        "stale": bool(held) and (status == "failed" or gap > RS_BEHIND_GRACE_BDAYS),
        "error": (st.get("error") or None) if st is not None and st.get("result") == "error" else None,
        "faults": bool(faults),
        "_expected": E.isoformat(),
        "_believed": bool(held) and _believed(held),
    }


def state_for(sym, views: dict, loaded: dict) -> str:
    """"on" | "off" | "unknown" — a missing, unreadable or unconfirmed list is never "off"."""
    norm = norm_symbol(sym)
    if not norm:
        return "unknown"
    for doc in (loaded.get("lists") or {}).values():
        if doc and norm in (doc.get("symbols") or []):
            return "on"
    if len(views) == len(all_markets()) and all(v["status"] == "ok" for v in views.values()):
        return "off"
    return "unknown"


def tag_block(sym: str, mkt: str, exchange: str, as_of: str, stale: bool) -> dict:
    md = SR._md(as_of)
    tail = STALE_WORD if stale else ""
    title = TITLE_TEXT % (GLYPH, TAG_WORDS, sym, exchange, as_of, "{:,}".format(REG_SHO_MIN_FTD_SHARES),
                          REG_SHO_MIN_PCT_SHARES_OUT, REG_SHO_CONSEC_SETTLEMENT_DAYS, REG_SHO_RULE,
                          HONESTY_NOTE, NOT_A_SIGNAL)
    if stale:
        title += STALE_TITLE % md
    return {"state": "on", "symbol": sym, "market": mkt, "exchange": exchange, "as_of": as_of, "stale": bool(stale),
            "chip": (CHIP_TEXT % (GLYPH, TAG_WORDS, md)) + tail,
            "short": (SHORT_TEXT % (GLYPH, TAG_WORDS, md)) + tail,
            "label": (LABEL_TEXT % (GLYPH, TAG_WORDS, exchange, md)) + tail,
            "title": title}


def _source_text(exchange: str, v: dict) -> str:
    skipped = SRC_SKIPPED % v["skipped"] if v["skipped"] > 0 else ""
    if v["as_of"] is None:
        return (SRC_FAILED if v["status"] == "failed" else SRC_PENDING) % exchange
    md = SR._md(v["as_of"])
    if not v["_believed"]:
        return SRC_UNCONFIRMED % (exchange, md)
    if v["status"] == "failed":
        return SRC_FAILED_HELD % (exchange, md)
    if v["status"] == "ok" and v["behind"]:
        return (SRC_BEHIND % (exchange, md, v["n"], SR._md(v["_expected"]))) + skipped
    return (SRC_OK % (exchange, md, v["n"])) + skipped


def _source_entry(mkt: str, exchange: str, v: dict) -> dict:
    return {"market": mkt, "exchange": exchange, "faults": v["faults"], "ok": v["status"] == "ok",
            "status": v["status"], "as_of": v["as_of"], "n": v["n"], "skipped": v["skipped"],
            "behind": v["behind"], "stale": v["stale"], "error": v["error"], "text": _source_text(exchange, v)}


def payload(db=_DEFAULT, now: Optional[datetime] = None, *, check=None, kick: bool = True, http=None) -> dict:
    """THE served read — Mongo reads only, never an outside call."""
    now_et = _to_et(now)
    if db is _DEFAULT:
        db = SIC._get_db()
    coll = db[RS_COLL] if db is not None else None
    loaded = load(coll) if coll is not None else {"lists": {}, "states": {}}

    refreshing = False
    if coll is not None:
        started = False
        if kick and any(is_due(src, loaded, now_et) for src in SOURCES):
            started = kick_refresh(coll, now_et if now is not None else None, http=http)
        refreshing = bool(started or _worker_running())

    views = {}
    sources = []
    items = {}
    seen = set()
    for src, mkt, exchange, _f in all_markets():
        v = market_view(src, mkt, loaded, now_et)
        views[mkt] = v
        sources.append(_source_entry(mkt, exchange, v))
        held = loaded["lists"].get(mkt)
        if not held or v["as_of"] is None:
            continue
        for sym in held.get("symbols") or []:
            norm = norm_symbol(sym)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            blk = tag_block(norm, mkt, exchange, v["as_of"], v["stale"])
            for k in alias_keys(norm):
                items.setdefault(k, blk)

    faulting = [s["text"] for s in sources
                if s["faults"] and (s["status"] == "failed"
                                    or (s["status"] == "pending" and s["as_of"] is None and not refreshing))]
    as_ofs = [s["as_of"] for s in sources if s["as_of"]]
    out = {
        "kind": KIND,
        "as_of": max(as_ofs) if as_ofs else None,
        "complete": all(s["ok"] for s in sources),
        "n": len(seen),
        "items": items,
        "sources": sources,
        "note": HONESTY_NOTE,
        "fault_text": (FAULT_TEXT % (GLYPH, TAG_WORDS, "; ".join(faulting))) if faulting else None,
        "refreshing": refreshing,
        "retry_after_sec": RS_RETRY_AFTER_SEC if refreshing else None,
    }
    if check is not None:
        res = {}
        for s in list(check):
            k = str(s or "").strip().upper()
            if not k or k in res:
                continue
            if len(res) >= RS_CHECK_MAX:
                break
            res[k] = state_for(k, views, loaded)
        out["check"] = res
    return out


def fault_payload(now: Optional[datetime] = None) -> dict:
    """[C1] the served body when the read itself raised. Reads nothing."""
    sources = []
    for src in SOURCES:
        for mkt, exchange, faults in source_markets(src):
            sources.append({"market": mkt, "exchange": exchange, "faults": bool(faults), "ok": False,
                            "status": "pending", "as_of": None, "n": 0, "skipped": 0, "behind": False,
                            "stale": False, "error": None, "text": SRC_PENDING % exchange})
    return {"kind": KIND, "as_of": None, "complete": False, "n": 0, "items": {}, "sources": sources,
            "note": HONESTY_NOTE, "fault_text": FAULT_UNREADABLE % (GLYPH, TAG_WORDS),
            "refreshing": False, "retry_after_sec": None}


def _and_list(names: list) -> str:
    return names[0] if len(names) == 1 else "%s and %s" % (", ".join(names[:-1]), names[-1])


def rules_pick() -> str:
    """The ℹ️ 🩳 pick — numbers and exchange names from the constants and the registry."""
    names = [ex for _s, _m, ex, _f in all_markets()]
    stock = [ex for _s, _m, ex, f in all_markets() if f]
    return ("%s %s (the tag's name) = the name is on an exchange's Reg SHO threshold list: fails to deliver of at "
            "least %s shares and at least %g%% of shares outstanding for %d straight settlement days (%s). Read "
            "from the %s daily files; the tag carries the list's trade date and says 'stale' when its list could "
            "not be refreshed. When a stock list (%s) could not be read, a line above the cards says so — a "
            "missing tag then does not mean 'not listed'. %s Tags Gajjala cards, 👀 Watch tiles and the 📋 All "
            "strategies table only; it gates, sorts and pushes nothing. UNMEASURED."
            % (GLYPH, TAG_WORDS, "{:,}".format(REG_SHO_MIN_FTD_SHARES), REG_SHO_MIN_PCT_SHARES_OUT,
               REG_SHO_CONSEC_SETTLEMENT_DAYS, REG_SHO_RULE, _and_list(names), ", ".join(stock), HONESTY_NOTE))
