"""⛔ SSR tag — the session's dividends and splits (2026-11-23).

THE ASK (Ajay 2026-11-23, verbatim)
  "No shorting at the bid (SEC short-sale restriction)

   Can we check or this for other stocks too?"

What this module is: the corporate-action half of the ⛔ SSR read
(spec rev 2 §3.4a, critique C1(b) + C6). The computed Rule 201 read compares a
day low to the snapshot's prior close, and that prior close is NOT adjusted on
an ex-dividend or split day (PXED, ex-dividend $2.36 on 2026-11-23, read as a
false computed tag). The SEC FAQ leaves the prior close to the listing market
(Q1.3, Q3.1) and says nothing about corporate actions, so a name with a
dividend ex-date or a split executed on trigger day T gets NO computed answer
for T. This module only says WHICH names those are. It never computes an
adjusted close.

Two Massive reference reads per day D, BY DATE (no ticker), through the house
client `sepa.prices._http()` with `massive_keys.stocks_key()` — the endpoint,
client and strictness of `chart_maps.drop10_tab.fetch_splits_strict`:
  GET https://api.massive.com/v3/reference/dividends?ex_dividend_date=D&limit=1000
  GET https://api.massive.com/v3/reference/splits?execution_date=D&limit=1000
A failure is an ERROR, never an empty day: a non-200, a body without a list
`results`, no key, a transport error, or more pages than CA_MAX_PAGES.

The read side never calls out: `refresh_due` runs inside the ⛔ list worker
(ssr_lists), ≤ 2 good reads × 2 GETs per day, 0 calls once every day handed in
was read at/after its regular-session open. The key is never logged or stored
(errors carry the exception class name only, through `prices._scrub_key`).

Imports neither `short_interest.ssr` nor `short_interest.ssr_lists`.
DISPLAY ONLY — nothing here gates, sorts, pushes or trades.
"""
from __future__ import annotations

import logging
import threading
import urllib.parse
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from short_interest import read as SR
from short_interest import reg_sho as RS

log = logging.getLogger("short_interest.ssr_corp")

SOURCE_KEY = "corp_actions"
BASE_URL = "https://api.massive.com"
DIVIDENDS_PATH = "/v3/reference/dividends"
SPLITS_PATH = "/v3/reference/splits"
READS = (                                  # (name, path, the BY-DATE filter field)
    ("dividends", DIVIDENDS_PATH, "ex_dividend_date"),
    ("splits", SPLITS_PATH, "execution_date"),
)

# engineering — MINE (HIS CALL 13)
CA_HTTP_TIMEOUT_SEC = 15           # the house value for this endpoint (drop10_tab.py:350)
CA_PAGE_LIMIT = 1000
CA_MAX_PAGES = 5
CA_RETRY_MIN = 30
CA_ERROR_RETRY_MIN = 5
CA_ERROR_STRIKES = 2

# served texts (M/D via SR._md)
SRC_OK = "dividends and splits of %s read · %s names"
SRC_PENDING = "dividends and splits of %s not read yet"
SRC_FAILED = "dividends and splits of %s could not be read"

_ET = ZoneInfo("America/New_York")


class _ReadError(Exception):
    """One reference read could not be trusted (never read as an empty day)."""


# ───────────────────────────────────────────── seams
def _getter(http):
    """The GET callable: the house session's `.get` (default), a session-like `http`, or a requests.get-like callable."""
    if http is None:
        from sepa import prices                                # lazy
        http = prices._http()
    g = getattr(http, "get", None)
    return g if callable(g) else http


def _key() -> str:
    from massive_keys import stocks_key                        # lazy
    return stocks_key() or ""


def _scrub(text: str) -> str:
    from sepa import prices                                    # lazy
    return prices._scrub_key(text)


def _for_snapshot(ticker: str) -> str:
    from sepa import symbols                                   # lazy
    return symbols.for_yahoo(ticker.strip().upper())


def _rth_open(d: date) -> datetime:
    from daytrading.data import ET_RTH_OPEN                    # lazy
    return datetime.combine(d, ET_RTH_OPEN).replace(tzinfo=_ET)


def _iso(d) -> Optional[str]:
    if isinstance(d, datetime):
        d = d.date()
    if isinstance(d, date):
        return d.isoformat()
    x = RS._as_date(d)
    return x.isoformat() if x else None


def _days(days) -> list:
    out = []
    for d in days or ():
        iso = _iso(d)
        if iso and iso not in out:
            out.append(iso)
    return out


def _num(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


# ───────────────────────────────────────────── the two reads
def _strip_key(url: str) -> str:
    """A next_url without any apiKey param (ours is re-attached through `params`)."""
    p = urllib.parse.urlsplit(url)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True) if k != "apiKey"]
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(q), p.fragment))


def _read_all(get, name: str, path: str, field: str, iso: str, key: str) -> list:
    """Every `results` row of one by-date read, paging through `next_url` up to CA_MAX_PAGES. Raises _ReadError."""
    url = BASE_URL + path
    params = {field: iso, "limit": CA_PAGE_LIMIT, "apiKey": key}
    rows = []
    for page in range(1, CA_MAX_PAGES + 1):
        r = get(url, params=params, timeout=CA_HTTP_TIMEOUT_SEC)
        if getattr(r, "status_code", None) != 200:
            raise _ReadError("%s HTTP %s" % (name, getattr(r, "status_code", "?")))
        try:
            body = r.json()
        except Exception:                                      # noqa: BLE001
            raise _ReadError("%s malformed" % name)
        res = body.get("results") if isinstance(body, dict) else None
        if not isinstance(res, list):
            raise _ReadError("%s malformed" % name)
        rows.extend(res)
        nxt = body.get("next_url")
        if not nxt:
            return rows
        if not isinstance(nxt, str) or not nxt.startswith(BASE_URL + "/"):
            raise _ReadError("%s bad_next_url" % name)         # the key is never sent to another host
        if page == CA_MAX_PAGES:
            break
        url, params = _strip_key(nxt), {"apiKey": key}
    raise _ReadError("%s truncated" % name)                    # a partial day is never read as complete


def _dividend_rows(res: list) -> list:
    out = []
    for x in res:
        if not isinstance(x, dict):
            continue
        t = x.get("ticker")
        if not isinstance(t, str) or not t.strip():
            continue
        cur = x.get("currency")
        out.append([_for_snapshot(t), _num(x.get("cash_amount")), cur if isinstance(cur, str) else None])
    return out


def _split_rows(res: list) -> list:
    out = []
    for x in res:
        if not isinstance(x, dict):
            continue
        t = x.get("ticker")
        if not isinstance(t, str) or not t.strip():
            continue
        out.append([_for_snapshot(t), _num(x.get("split_from")), _num(x.get("split_to"))])
    return out


def fetch_day(d, *, http=None) -> dict:
    """Day D's dividends (ex-date) and splits (execution date). Never raises.
    {"result": "found", "dividends": [[SYM, cash_amount, currency]], "splits": [[SYM, split_from, split_to]]}
    | {"result": "error", "error": text}. BOTH reads must answer."""
    iso = _iso(d)
    if not iso:
        return {"result": "error", "error": "bad_date"}
    which = "setup"
    try:
        key = _key()
        if not key:
            return {"result": "error", "error": "no_key"}
        get = _getter(http)
        got = {}
        for name, path, field in READS:
            which = name
            got[name] = _read_all(get, name, path, field, iso, key)
        return {"result": "found", "dividends": _dividend_rows(got["dividends"]),
                "splits": _split_rows(got["splits"])}
    except _ReadError as exc:
        return {"result": "error", "error": _safe(str(exc))}
    except Exception as exc:                                   # noqa: BLE001
        return {"result": "error", "error": _safe("%s %s" % (which, type(exc).__name__))}


def _safe(text: str) -> str:
    try:
        return _scrub(text)
    except Exception:                                          # noqa: BLE001
        return "error"


# ───────────────────────────────────────────── due rule
def _due(iso: str, corp: Optional[dict], state: Optional[dict], now_et: datetime) -> bool:
    d = RS._as_date(iso)
    if d is None:
        return False
    if corp:
        if corp.get("after_open") or now_et < _rth_open(d):
            return False                                       # read after its open, or the open not reached yet
    if state:
        if state.get("result") == "error" and int(state.get("errors") or 0) < CA_ERROR_STRIKES:
            wait = CA_ERROR_RETRY_MIN
        else:
            wait = CA_RETRY_MIN
        age = RS._age_min(state.get("attempt_at"), now_et)
        if age is not None and age < wait:
            return False
    return True


def _read_day(coll, iso: str):
    return (coll.find_one({"_id": "corp|%s" % iso}), coll.find_one({"_id": "corpstate|%s" % iso}))


def refresh_due(coll, days, now_et, *, http=None) -> dict:
    """Read every due day of `days`. Never raises. ≤ 1 fetch_day per due day; the state doc is written BEFORE
    the first outside call. {"ran": [iso], "results": {iso: result}, "calls": GETs}."""
    out = {"ran": [], "results": {}, "calls": 0}
    try:
        now_et = RS._to_et(now_et)
        isos = _days(days)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ssr_corp: bad refresh arguments: %s", type(exc).__name__)
        return out
    if coll is None:
        return out
    calls = {"n": 0}

    class _Counted:
        def get(self, url, **kw):
            calls["n"] += 1
            return _getter(http)(url, **kw)

    for iso in isos:
        try:
            corp, prev = _read_day(coll, iso)
            if not _due(iso, corp, prev, now_et):
                continue
        except Exception as exc:                               # noqa: BLE001
            log.warning("ssr_corp: %s read failed: %s", iso, type(exc).__name__)
            continue
        errors = int((prev or {}).get("errors") or 0)
        now_iso = RS._utc_iso(now_et)
        sid = "corpstate|%s" % iso
        state = {"_id": sid, "kind": "corpstate", "date": iso, "attempt_at": now_iso,
                 "result": "running", "error": None, "errors": errors}
        try:
            coll.replace_one({"_id": sid}, dict(state), upsert=True)   # BEFORE the outside call
        except Exception as exc:                               # noqa: BLE001
            log.warning("ssr_corp: %s state write failed, day skipped: %s", iso, type(exc).__name__)
            continue
        out["ran"].append(iso)
        result, err = "error", None
        try:
            got = fetch_day(iso, http=_Counted())
            if got.get("result") == "found":
                dv, sp = got["dividends"], got["splits"]
                doc = {"_id": "corp|%s" % iso, "kind": "corp", "date": iso, "dividends": dv, "splits": sp,
                       "n_div": len(dv), "n_split": len(sp), "read_at": now_iso,
                       "after_open": now_et >= _rth_open(RS._as_date(iso)),
                       "rev": "%s|%d|%d" % (now_iso, len(dv), len(sp))}
                coll.replace_one({"_id": doc["_id"]}, doc, upsert=True)
                result = "found"
            else:
                err = got.get("error") or "error"
                log.warning("ssr_corp: %s not read: %s", iso, err)
        except Exception as exc:                               # noqa: BLE001
            err = "store %s" % type(exc).__name__
            log.warning("ssr_corp: %s store failed: %s", iso, type(exc).__name__)
        finally:
            state["result"] = result
            state["error"] = err if result == "error" else None
            state["errors"] = errors + 1 if result == "error" else 0
            out["results"][iso] = result
            try:
                coll.replace_one({"_id": sid}, dict(state), upsert=True)
            except Exception as exc:                           # noqa: BLE001
                log.warning("ssr_corp: %s final state write failed: %s", iso, type(exc).__name__)
    out["calls"] = calls["n"]
    return out


# ───────────────────────────────────────────── the read side (Mongo only)
_dec_lock = threading.Lock()
_decoded = {}                      # iso -> (rev, {SYM: "split" | "dividend"})


def _reset_cache() -> None:
    with _dec_lock:
        _decoded.clear()


def _decode(doc: dict) -> dict:
    iso, rev = doc.get("date"), doc.get("rev")
    with _dec_lock:
        hit = _decoded.get(iso)
        if hit is not None and rev is not None and hit[0] == rev:
            return hit[1]
    acts = {}
    for row in doc.get("dividends") or ():
        if isinstance(row, (list, tuple)) and row and isinstance(row[0], str) and row[0]:
            acts[row[0]] = "dividend"
    for row in doc.get("splits") or ():
        if isinstance(row, (list, tuple)) and row and isinstance(row[0], str) and row[0]:
            acts[row[0]] = "split"                             # split wins over a dividend
    with _dec_lock:
        _decoded[iso] = (rev, acts)
    return acts


def load(coll, days) -> dict:
    """Mongo reads only, never raises. {"days": {iso: {"corp", "state"}}, "actions": {iso: {...}}, "unread": [iso]}."""
    out = {"days": {}, "actions": {}, "unread": []}
    for iso in _days(days):
        if coll is None:
            out["unread"].append(iso)
            continue
        try:
            corp, state = _read_day(coll, iso)
        except Exception as exc:                               # noqa: BLE001
            log.warning("ssr_corp: %s load failed: %s", iso, type(exc).__name__)
            out["unread"].append(iso)
            continue
        out["days"][iso] = {"corp": corp, "state": state}
        if corp:
            try:
                out["actions"][iso] = _decode(corp)
            except Exception as exc:                           # noqa: BLE001
                log.warning("ssr_corp: %s doc undecodable: %s", iso, type(exc).__name__)
    return out


def actions(loaded, T) -> Optional[dict]:
    """{SYM: "split" | "dividend"} for day T; None = day T not read (never {} for an unread day)."""
    iso = _iso(T)
    if not iso or not isinstance(loaded, dict):
        return None
    acts = (loaded.get("actions") or {}).get(iso)
    return dict(acts) if acts is not None else None


def any_due(loaded, days, now_et) -> bool:
    try:
        now_et = RS._to_et(now_et)
        held = (loaded or {}).get("days") or {}
        unread = set((loaded or {}).get("unread") or ())
        for iso in _days(days):
            if iso in unread:
                continue                                       # Mongo unreadable: nothing to kick for
            e = held.get(iso) or {}
            if _due(iso, e.get("corp"), e.get("state"), now_et):
                return True
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ssr_corp: any_due failed: %s", type(exc).__name__)
    return False


def _day_status(iso: str, loaded: dict) -> str:
    if iso in set(loaded.get("unread") or ()):
        return "failed"
    e = (loaded.get("days") or {}).get(iso) or {}
    if e.get("corp"):
        return "ok"
    st = e.get("state") or {}
    if st.get("result") == "error" and int(st.get("errors") or 0) >= CA_ERROR_STRIKES:
        return "failed"
    return "pending"


def source_view(loaded, days, now_et) -> dict:
    """ONE served `sources` row. Worst day wins: failed > pending > ok; the text names the days in that status."""
    loaded = loaded if isinstance(loaded, dict) else {"unread": _days(days)}
    isos = sorted(_days(days))
    per = {iso: _day_status(iso, loaded) for iso in isos}
    held = [((loaded.get("days") or {}).get(iso) or {}).get("corp") for iso in isos]
    held = [c for c in held if c]
    names = set()
    for c in held:
        names.update(_decode(c))
    as_of = max((str(c.get("read_at")) for c in held if c.get("read_at")), default=None)
    status = "failed" if "failed" in per.values() else ("pending" if "pending" in per.values() or not isos else "ok")
    which = [iso for iso in isos if per[iso] == status] if isos else []
    dates = ", ".join(SR._md(iso) for iso in which) or "—"
    if status == "ok":
        text = SRC_OK % (dates, len(names))
    elif status == "failed":
        text = SRC_FAILED % dates
    else:
        text = SRC_PENDING % dates
    error = None
    for iso in which:
        st = ((loaded.get("days") or {}).get(iso) or {}).get("state") or {}
        if st.get("error"):
            error = str(st["error"])
            break
    if status == "failed" and error is None and any(iso in set(loaded.get("unread") or ()) for iso in which):
        error = "unread"
    return {"key": SOURCE_KEY, "exchange": None, "ok": status == "ok", "status": status, "as_of": as_of,
            "n": len(names), "error": error, "text": text}
