"""🩳 share basis — the I/O half of the % of float check (2026-11-24, spec sidilute §3.1 + §3.2).

Ajay 2026-11-24: "Make sure we are looking for Dilution.." · "Also split related events and filing so we flag them in
the right way".

One record per name in `si_share_basis` (SB_COLL), FROZEN shape (spec §3.1): the SEC cover-page share counts and the
dilution / charter filings (data.sec.gov), the Massive ticker reference (CIK + type) and splits, the live Yahoo row of
`shares_cache`, and a TRACK of the float value (when it was first seen, which splits it was carried across).

I/O ONLY: no words, no verdict. The verdict and the split math live in `short_interest.basis_math`, reached here only
through the `track_fn` / `kind_fn` seams (lazy default). The read path (`read.si_map`) only ever calls `load`; the
fetching runs in ONE background thread started by `kick` (the `borrow.kick_refresh` shape).

Status rule [C1][C11]: a sub-doc's `status` describes the DATA HELD, never the last attempt. A failed attempt over a held
good read leaves status, data and `read_at` untouched and sets `error` (the exception TYPE, never its text — a URL
can carry the key) + `error_at` + `strikes`. `failed` = no good read ever stored; `blocked` (sec only) = never read
because the SEC stop was on.

Outside calls: data.sec.gov with a generic User-Agent (no project name, no contact), paced through ONE pacer
(`_sec_wait`, SB_SEC_MIN_INTERVAL_SEC apart); the Massive host through `ssr_corp._getter / _key / _safe`.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional

from short_interest import ssr_corp as SC

log = logging.getLogger("short_interest.share_basis")

# ───────────────────────────────────────────── constants (engineering — MINE, his call to change; none is a trading threshold)
SB_COLL = "si_share_basis"
SB_VERSION = 1
SB_STATE_SEC_ID = "state|sec"                 # {"_id", "blocked_until", "reason"}: a 403 / 429 stops ALL SEC calls until then
SB_HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; share-count-reader)", "Accept": "application/json"}
SEC_CONCEPT_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK%s/dei/EntityCommonStockSharesOutstanding.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK%s.json"
MASSIVE_REF_PATH = "/v3/reference/tickers/%s"
SB_HTTP_TIMEOUT_SEC = 15
SB_SEC_MIN_INTERVAL_SEC = 0.5                 # [C12] 2 req/s beside the house Form-4 reader's 7 (sepa/insider.py EDGAR_MAX_RPS) = 9, under 10
SB_REFRESH_MIN = 60
SB_ERROR_RETRY_MIN = 5
SB_ERROR_STRIKES = 2
SB_SEC_BLOCK_MIN = 15
SB_REF_REFRESH_DAYS = 7
SB_COVERS_KEPT = 8
SB_FILINGS_KEPT = 40
SB_QUEUE_MAX = 400
SB_RETRY_AFTER_SEC = 20
SB_THREAD_NAME = "si-share-basis"
SEC_PERIODIC_PREFIXES = ("10-Q", "10-K", "20-F", "40-F")     # the forms whose accession moves `top_accn`
# 📄 2026-11-26 (spec sitrack §3.1, A1) — the CURRENT report forms (domestic, foreign). A filing row's `with` names the
# report the same issuer filed the SAME day (a base in SB_REPORT_FORMS or one of SEC_PERIODIC_PREFIXES), so the pure
# half can tell a report re-filed as a prospectus under several registrations from a new offering. MINE.
SB_REPORT_FORMS = ("8-K", "6-K")
SEC_BLOCK_HTTP = (403, 429)
SEEN_KEYS = ("settlement_date", "float_shares", "float_asof", "shares_outstanding", "shares_asof")
GOOD_STATUSES = ("ok", "none", "no_cik", "absent")             # a good read (status rule)
ERR_NO_KEY = "no_key"
ERR_NO_REF = "no_ref"                                          # the ticker reference never answered: no CIK to ask with
ERR_MALFORMED = "malformed"

_http = None                  # the ONE SEC outside-call seam; None → requests.get (lazy import) — the reg_sho._http shape


# ───────────────────────────────────────────── small helpers
def _SR():
    from short_interest import read as SR                      # lazy: read joins this module lazily too
    return SR


def _SIC():
    from short_interest import client as SIC                   # lazy
    return SIC


def _default_db():
    try:
        return _SIC()._get_db()
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: no database: %s", type(exc).__name__)
        return None


def _now(now=None) -> datetime:
    if isinstance(now, datetime):
        return now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(v) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v if v.tzinfo is not None else v.replace(tzinfo=timezone.utc)
    if not isinstance(v, str) or not v.strip():
        return None
    try:
        d = datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo is not None else d.replace(tzinfo=timezone.utc)


def _day(v) -> Optional[str]:
    return _SR()._iso_date(v)


def _pos_int(v) -> Optional[int]:
    if isinstance(v, bool):
        return None
    return _SR()._pos_int(v)


def _num(v) -> Optional[float]:
    return _SR()._num(v)


def _plain(f: float):
    return int(f) if float(f).is_integer() else f


def _err(exc: BaseException) -> str:
    return _safe(type(exc).__name__)


def _safe(text: str) -> str:
    return SC._safe(str(text))


def _status(resp) -> int:
    try:
        return int(getattr(resp, "status_code", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _clean(symbols) -> list:
    out: list = []
    for s in symbols or []:
        if not isinstance(s, str):
            continue
        s = s.strip().upper()
        if s and s not in out and s != SB_STATE_SEC_ID.upper():
            out.append(s)
    return out


def _find_one(coll, sym: str) -> Optional[dict]:
    for doc in coll.find({"_id": {"$in": [sym]}}):
        if isinstance(doc, dict):
            return dict(doc)
    return None


def _find_map(coll, syms: list) -> dict:
    out: dict = {}
    for doc in coll.find({"_id": {"$in": list(syms)}}):
        if isinstance(doc, dict) and isinstance(doc.get("_id"), str):
            out[doc["_id"].upper()] = dict(doc)
    return out


def _strikes(sub) -> int:
    n = sub.get("strikes") if isinstance(sub, dict) else None
    return n if isinstance(n, int) and not isinstance(n, bool) and n > 0 else 0


def _good(sub) -> bool:
    return isinstance(sub, dict) and sub.get("status") in GOOD_STATUSES


def _ok_sub(fields: dict, now_iso: str) -> dict:
    out = dict(fields)
    out.update({"read_at": now_iso, "error": None, "error_at": None, "strikes": 0})
    return out


def _failed_sub(held, error: str, now_iso: str, empty: dict) -> dict:
    """The status rule for a failed attempt: a held good read stands (status, data, read_at untouched) + error;
    nothing good held → `failed`."""
    if _good(held):
        out = dict(held)
        out.update({"error": error, "error_at": now_iso, "strikes": _strikes(held) + 1})
        return out
    out = {"status": "failed"}
    out.update(empty)
    out.update({"read_at": None, "error": error, "error_at": now_iso, "strikes": _strikes(held) + 1})
    return out


# ───────────────────────────────────────────── the SEC pacer + GET (ONE path for every SEC call)
_sec_lock = threading.Lock()
_sec_last = {"t": None}
_sec_stop = {"until": None}                                    # the in-process copy of state|sec.blocked_until


def _sec_wait(clock: Optional[Callable] = None, sleep: Optional[Callable] = None) -> None:
    """Two SEC GETs never start closer than SB_SEC_MIN_INTERVAL_SEC (monotonic, module lock) [C12]."""
    clock = clock or time.monotonic
    sleep = sleep or time.sleep
    with _sec_lock:
        t = clock()
        last = _sec_last["t"]
        if last is not None:
            gap = SB_SEC_MIN_INTERVAL_SEC - (t - last)
            if gap > 0:
                sleep(gap)
                t = clock()
        _sec_last["t"] = t


def _resolve_http(http):
    if http is not None:
        return http
    if _http is not None:
        return _http
    import requests                                            # lazy: the read never needs it
    return requests.get


def _sec_get(url: str, http):
    _sec_wait()
    call = _resolve_http(http)
    return call(url, headers=dict(SB_HTTP_HEADERS), timeout=SB_HTTP_TIMEOUT_SEC)


def _sec_blocked(db, now: datetime) -> bool:
    until = _sec_stop["until"]
    if isinstance(until, datetime) and until > now:
        return True
    try:
        doc = _find_one(db[SB_COLL], SB_STATE_SEC_ID) if db is not None else None
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: sec state read failed: %s", type(exc).__name__)
        doc = None
    u = _parse_ts((doc or {}).get("blocked_until"))
    return bool(u is not None and u > now)


def _block_sec(db, now: datetime, reason: str, store: bool) -> None:
    until = now + timedelta(minutes=SB_SEC_BLOCK_MIN)
    _sec_stop["until"] = until
    log.warning("share_basis: SEC answered %s — every SEC call stops until %s", reason, _ts(until))
    if not store or db is None:
        return
    try:
        db[SB_COLL].replace_one({"_id": SB_STATE_SEC_ID},
                                {"_id": SB_STATE_SEC_ID, "blocked_until": _ts(until), "reason": reason}, upsert=True)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: sec state write failed: %s", type(exc).__name__)


# ───────────────────────────────────────────── the four reads (never raise)
def _cik10(v) -> Optional[str]:
    if isinstance(v, bool) or v is None:
        return None
    s = str(v).strip()
    if isinstance(v, int):
        s = str(v)
    if not s.isdigit() or len(s) > 10 or int(s) == 0:
        return None
    return s.zfill(10)


def fetch_ref(sym: str, *, http=None) -> dict:
    """The Massive ticker reference: {"status": "ok", "cik", "type"} | {"status": "absent"} (404)
    | {"status": "failed", "error"}. ONE GET."""
    try:
        key = SC._key()
        if not key:
            return {"status": "failed", "error": ERR_NO_KEY}
        from sepa import symbols                               # lazy
        t = symbols.for_massive(symbols.resolve(str(sym).strip().upper()))
        get = SC._getter(http)
        r = get(SC.BASE_URL + MASSIVE_REF_PATH % urllib.parse.quote(t, safe=".-"),
                params={"apiKey": key}, timeout=SB_HTTP_TIMEOUT_SEC)
        code = _status(r)
        if code == 404:
            return {"status": "absent"}
        if code != 200:
            return {"status": "failed", "error": "http_%d" % code}
        body = r.json()
        res = body.get("results") if isinstance(body, dict) else None
        if not isinstance(res, dict):
            return {"status": "failed", "error": ERR_MALFORMED}
        typ = res.get("type")
        return {"status": "ok", "cik": _cik10(res.get("cik")),
                "type": typ.strip().upper() if isinstance(typ, str) and typ.strip() else None}
    except Exception as exc:                                   # noqa: BLE001
        return {"status": "failed", "error": _err(exc)}


def _default_kind_fn():
    from short_interest import basis_math as BM                # lazy: the pure half (be-read)
    return BM.filing_kind


def _default_track_fn():
    from short_interest import basis_math as BM                # lazy
    return BM.track_update


def _str_at(arr, i) -> Optional[str]:
    """`arr[i]` when it is a non-empty string, else None (a missing / ragged / junk array never raises)."""
    if not isinstance(arr, list) or i >= len(arr) or not isinstance(arr[i], str):
        return None
    v = arr[i].strip()
    return v or None


def _is_report(form: str) -> bool:
    """A current or periodic report: the base (after `/A`) in SB_REPORT_FORMS, or a SEC_PERIODIC_PREFIXES form."""
    base = form.strip().upper()
    if base.endswith("/A"):
        base = base[:-2].strip()
    return base in SB_REPORT_FORMS or base.startswith(SEC_PERIODIC_PREFIXES)


def fetch_filings(cik10: str, since_iso: Optional[str], *, http=None, kind_fn=None) -> dict:
    """{"status": "ok", "filings": [{"form", "filed", "items", "doc", "file", "accn", "with"}] (newest first,
    filed >= since, only kinds `kind_fn(form, items)` names, at most SB_FILINGS_KEPT), "top_accn"[, "cap"]}
    | {"status": "failed", "error", "blocked": bool}.

    📄 2026-11-26 (spec sitrack §3.1, A1): `doc` = primaryDocument, `file` = fileNumber, `accn` = accessionNumber
    (each a non-empty string or None — a missing or ragged array leaves them None and the row counts as before);
    `with` = the form of the first report (`_is_report`) in listing order the issuer filed the SAME day, read over the
    WHOLE listing before the kind filter (an 8-K 8.01 that is not kept still marks its day), else None. `cap` =
    SB_FILINGS_KEPT, present only when the kind-filtered list was longer than it."""
    try:
        kf = kind_fn or _default_kind_fn()
        r = _sec_get(SEC_SUBMISSIONS_URL % cik10, http)
        code = _status(r)
        if code in SEC_BLOCK_HTTP:
            return {"status": "failed", "error": "http_%d" % code, "blocked": True}
        if code != 200:
            return {"status": "failed", "error": "http_%d" % code, "blocked": False}
        body = r.json()
        rec = ((body.get("filings") if isinstance(body, dict) else None) or {}).get("recent")
        if not isinstance(rec, dict):
            return {"status": "failed", "error": ERR_MALFORMED, "blocked": False}
        forms, dates = rec.get("form"), rec.get("filingDate")
        items, accns = rec.get("items"), rec.get("accessionNumber")
        docs, files = rec.get("primaryDocument"), rec.get("fileNumber")
        if not isinstance(forms, list) or not isinstance(dates, list):
            return {"status": "failed", "error": ERR_MALFORMED, "blocked": False}
        items = items if isinstance(items, list) else []
        accns = accns if isinstance(accns, list) else []
        since = _day(since_iso)
        n = min(len(forms), len(dates))
        report_on: dict = {}                                   # filed day → the first report's form, listing order
        for i in range(n):
            form = forms[i].strip() if isinstance(forms[i], str) else ""
            filed = _day(dates[i])
            if form and filed and filed not in report_on and _is_report(form):
                report_on[filed] = form
        rows, top = [], None
        for i in range(n):
            form = forms[i].strip() if isinstance(forms[i], str) else ""
            filed = _day(dates[i])
            if not form or not filed:
                continue
            it = items[i] if i < len(items) and isinstance(items[i], str) else ""
            accn = accns[i] if i < len(accns) and isinstance(accns[i], str) and accns[i].strip() else None
            if accn and form.upper().startswith(SEC_PERIODIC_PREFIXES) and (top is None or filed > top[0]):
                top = (filed, accn.strip())
            if since and filed < since:
                continue
            if kf(form, it) is None:
                continue
            rows.append({"form": form, "filed": filed, "items": it, "doc": _str_at(docs, i),
                         "file": _str_at(files, i), "accn": accn.strip() if accn else None,
                         "with": report_on.get(filed)})
        rows.sort(key=lambda x: x["filed"], reverse=True)
        out = {"status": "ok", "filings": rows[:SB_FILINGS_KEPT], "top_accn": top[1] if top else None}
        if len(rows) > SB_FILINGS_KEPT:
            out["cap"] = SB_FILINGS_KEPT
        return out
    except Exception as exc:                                   # noqa: BLE001
        return {"status": "failed", "error": _err(exc), "blocked": False}


def fetch_covers(cik10: str, *, http=None) -> dict:
    """{"status": "ok", "covers": [{"as_of", "shares", "form", "filed"}]} (ascending by as_of, deduped by as_of —
    the latest filed wins — the last SB_COVERS_KEPT) | {"status": "none"} (404, no such fact — a valid answer)
    | {"status": "failed", "error", "blocked": bool}."""
    try:
        r = _sec_get(SEC_CONCEPT_URL % cik10, http)
        code = _status(r)
        if code == 404:
            return {"status": "none"}
        if code in SEC_BLOCK_HTTP:
            return {"status": "failed", "error": "http_%d" % code, "blocked": True}
        if code != 200:
            return {"status": "failed", "error": "http_%d" % code, "blocked": False}
        body = r.json()
        units = body.get("units") if isinstance(body, dict) else None
        rows = units.get("shares") if isinstance(units, dict) else None
        if not isinstance(rows, list):
            return {"status": "none"}
        by: dict = {}
        for x in rows:
            if not isinstance(x, dict) or isinstance(x.get("val"), bool):
                continue
            as_of = _day(x.get("end"))
            f = _num(x.get("val"))
            if as_of is None or f is None or f <= 0:
                continue
            filed = _day(x.get("filed"))
            form = x.get("form").strip() if isinstance(x.get("form"), str) else None
            row = {"as_of": as_of, "shares": int(round(f)), "form": form, "filed": filed}
            held = by.get(as_of)
            if held is None or (filed or "") >= (held["filed"] or ""):
                by[as_of] = row
        covers = [by[k] for k in sorted(by)][-SB_COVERS_KEPT:]
        if not covers:
            return {"status": "none"}
        return {"status": "ok", "covers": covers}
    except Exception as exc:                                   # noqa: BLE001
        return {"status": "failed", "error": _err(exc), "blocked": False}


def fetch_splits(sym: str, since_iso: Optional[str], *, fetch=None) -> dict:
    """{"status": "ok", "rows": [{"execution_date", "split_from", "split_to"}]} (ascending; from > 0, to > 0,
    from != to; future dates kept) | {"status": "failed", "error"} — wraps `drop10_tab.fetch_splits_strict`;
    only the exception TYPE is kept (its text can carry the key)."""
    try:
        f = fetch
        if f is None:
            from chart_maps import drop10_tab as D             # lazy
            f = D.fetch_splits_strict
        raw = f(sym, since_iso)
        if not isinstance(raw, list):
            return {"status": "failed", "error": ERR_MALFORMED}
        rows, seen = [], set()
        for x in raw:
            if not isinstance(x, dict):
                continue
            e = _day(x.get("execution_date"))
            fr = None if isinstance(x.get("split_from"), bool) else _num(x.get("split_from"))
            to = None if isinstance(x.get("split_to"), bool) else _num(x.get("split_to"))
            if e is None or fr is None or to is None or fr <= 0 or to <= 0 or fr == to:
                continue
            k = (e, fr, to)
            if k in seen:
                continue
            seen.add(k)
            rows.append({"execution_date": e, "split_from": _plain(fr), "split_to": _plain(to)})
        rows.sort(key=lambda x: x["execution_date"])
        return {"status": "ok", "rows": rows}
    except Exception as exc:                                   # noqa: BLE001
        return {"status": "failed", "error": _err(exc)}


# ───────────────────────────────────────────── the SI record
def _usable(rec) -> bool:
    """A usable settlement + count (the si_block rule): a `no_record` name is never checked [C5]."""
    if not isinstance(rec, dict):
        return False
    SR = _SR()
    return SR._as_date(rec.get("settlement_date")) is not None and SR._nonneg_int(rec.get("short_interest")) is not None


def _seen_of(rec: dict) -> dict:
    return {"settlement_date": _day(rec.get("settlement_date")),
            "float_shares": _pos_int(rec.get("float_shares")),
            "float_asof": _day(rec.get("float_asof")),
            "shares_outstanding": _pos_int(rec.get("shares_outstanding")),
            "shares_asof": _day(rec.get("shares_asof"))}


def _yahoo_row(db, sym: str) -> Optional[dict]:
    try:
        from sepa.volume_movers import SHARES_COLL             # lazy
        row = _find_one(db[SHARES_COLL], sym)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: shares_cache read failed: %s", type(exc).__name__)
        return None
    if not isinstance(row, dict):
        return None
    fl, so = _pos_int(row.get("float_shares")), _pos_int(row.get("shares_outstanding"))
    if fl is None and so is None:
        return None
    a = row.get("as_of")
    asof = None
    f = None if isinstance(a, (bool, str, datetime, date)) else _num(a)
    if f is not None and f > 0:
        try:
            asof = datetime.fromtimestamp(f, tz=timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError):
            asof = None
    elif isinstance(a, (str, datetime, date)):
        asof = _day(a)
    return {"float_shares": fl, "shares_outstanding": so, "as_of": asof}


def _ref_fresh(href, now: datetime) -> bool:
    if not isinstance(href, dict) or href.get("status") != "ok":
        return False
    r = _parse_ts(href.get("read_at"))
    return r is not None and timedelta(0) <= now - r < timedelta(days=SB_REF_REFRESH_DAYS)


# ───────────────────────────────────────────── one name
def _sec_step(db, cik, ref, held, since, now, now_iso, http, kind_fn, store) -> dict:
    empty = {"since": since, "top_accn": None, "covers": [], "filings": []}
    if not cik:
        if isinstance(ref, dict) and ref.get("status") in ("ok", "absent"):
            return _ok_sub(dict({"status": "no_cik"}, **empty), now_iso)
        if _good(held):
            return dict(held)                                  # SEC was not asked: what is held stands, unmarked
        return _failed_sub(held, ERR_NO_REF, now_iso, empty)
    if _sec_blocked(db, now):
        if _good(held):
            return dict(held)                                  # [C11] no call; the held answer stays as it is
        out = dict({"status": "blocked"}, **empty)
        out.update({"read_at": None, "error": None, "error_at": now_iso, "strikes": _strikes(held)})
        return out
    got = fetch_filings(cik, since, http=http, kind_fn=kind_fn)
    if got.get("status") != "ok":
        if got.get("blocked"):
            _block_sec(db, now, got.get("error") or "blocked", store)
        return _failed_sub(held, got.get("error") or "error", now_iso, empty)
    hcov = held.get("covers") if _good(held) and isinstance(held.get("covers"), list) else []
    hsince = _day(held.get("since")) if isinstance(held, dict) else None
    need = (not hcov) or got.get("top_accn") != held.get("top_accn") or (hsince is not None and hsince > since)
    if need:
        c = fetch_covers(cik, http=http)
        if c.get("status") == "failed":
            if c.get("blocked"):
                _block_sec(db, now, c.get("error") or "blocked", store)
            return _failed_sub(held, c.get("error") or "error", now_iso, empty)
        status, covers = c["status"], (c.get("covers") or [])
    else:
        status, covers = "ok", hcov
    out = {"status": status, "since": since, "top_accn": got.get("top_accn"),
           "covers": covers, "filings": got.get("filings") or []}
    if got.get("cap"):                                         # 📄 2026-11-26 — the kept-row cap cut the list
        out["filings_cap"] = got["cap"]
    return _ok_sub(out, now_iso)


def refresh_symbol(sym: str, db=None, now=None, *, http=None, splits_fetch=None, track_fn=None, kind_fn=None,
                   store: bool = True) -> dict:
    """Re-read one name's share basis (spec §3.2 steps 1–9) and return the §3.1 doc; `store=False` writes nothing."""
    sym = str(sym or "").strip().upper()
    now = _now(now)
    now_iso = _ts(now)
    d = db if db is not None else _default_db()
    if d is None or not sym:
        return {"skipped": "no_db" if d is None else "no_symbol"}
    rec = _find_one(d[_SIC().SI_COLL], sym)
    if not _usable(rec):
        return {"skipped": "no_record"}                        # 1. nothing written
    try:
        held = _find_one(d[SB_COLL], sym) or {}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: %s basis read failed: %s", sym, type(exc).__name__)
        held = {}
    # 2. the ticker reference
    href = held.get("ref")
    if _ref_fresh(href, now):
        ref = dict(href)
    else:
        got = fetch_ref(sym, http=http)
        if got.get("status") in ("ok", "absent"):
            ref = _ok_sub({"status": got["status"], "cik": got.get("cik"), "type": got.get("type")}, now_iso)
        else:
            ref = _failed_sub(href, got.get("error") or "error", now_iso, {"cik": None, "type": None})
    cik = ref.get("cik") if ref.get("status") == "ok" else None
    # 3. Yahoo's live row
    yahoo = _yahoo_row(d, sym)
    # 4. the window
    track_held = held.get("float_track") if isinstance(held.get("float_track"), dict) else None
    dates = [_day(rec.get(k)) for k in ("settlement_date", "prev_settlement_date", "float_asof", "shares_asof")]
    dates.append(_day((track_held or {}).get("since")))
    since = min(x for x in dates if x)
    # 5. SEC
    sec = _sec_step(d, cik, ref, held.get("sec"), since, now, now_iso, http, kind_fn, store)
    # 6. reach back to the cover in force when the float was first seen
    tsince = _day((track_held or {}).get("since")) or _day(rec.get("float_asof"))
    since2 = since
    if tsince:
        before = [c.get("as_of") for c in (sec.get("covers") or [])
                  if isinstance(c, dict) and _day(c.get("as_of")) and c["as_of"] <= tsince]
        if before and max(before) < since2:
            since2 = max(before)
    # 7. splits
    hsp = held.get("splits")
    got = fetch_splits(sym, since2, fetch=splits_fetch)
    if got.get("status") == "ok":
        splits = _ok_sub({"status": "ok", "since": since2, "rows": got.get("rows") or []}, now_iso)
    else:
        splits = _failed_sub(hsp, got.get("error") or "error", now_iso, {"since": since2, "rows": []})
    # 8. the float track (held rows count even when the last try failed [C1])
    rows = splits.get("rows") if splits.get("status") == "ok" else None
    try:
        track = (track_fn or _default_track_fn())(track_held, dict(rec), rows)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: %s track update failed: %s", sym, type(exc).__name__)
        track = track_held
    doc = {"_id": sym, "v": SB_VERSION, "checked_at": now_iso, "seen": _seen_of(rec),
           "ref": ref, "sec": sec, "splits": splits, "yahoo": yahoo, "float_track": track}
    # 9. store
    if store:
        try:
            d[SB_COLL].replace_one({"_id": sym}, doc, upsert=True)
        except Exception as exc:                               # noqa: BLE001
            log.warning("share_basis: %s write failed: %s", sym, type(exc).__name__)
    return doc


# ───────────────────────────────────────────── due rule
def is_due(basis_doc, si_record, now=None) -> bool:
    """[C5] False for a `no_record` name. True: no doc · a seed-only doc (no `checked_at`) · `seen` differs from the
    record · a source with an error / failed / blocked whose last try is SB_ERROR_RETRY_MIN old (SB_REFRESH_MIN from
    SB_ERROR_STRIKES strikes) · `checked_at` SB_REFRESH_MIN old."""
    if not _usable(si_record):
        return False
    if not isinstance(basis_doc, dict):
        return True
    now = _now(now)
    chk = _parse_ts(basis_doc.get("checked_at"))
    if chk is None:
        return True
    if basis_doc.get("seen") != _seen_of(si_record):
        return True
    for k in ("ref", "sec", "splits"):
        sub = basis_doc.get(k)
        if not isinstance(sub, dict):
            return True
        if sub.get("error") or sub.get("status") in ("failed", "blocked"):
            last = _parse_ts(sub.get("error_at")) or _parse_ts(sub.get("read_at")) or chk
            wait = SB_ERROR_RETRY_MIN if _strikes(sub) < SB_ERROR_STRIKES else SB_REFRESH_MIN
            if now - last >= timedelta(minutes=wait):
                return True
    return now - chk >= timedelta(minutes=SB_REFRESH_MIN)


# ───────────────────────────────────────────── the read (never fetches)
def load(symbols, db=None) -> dict:
    """{SYM: basis doc} — ONE `$in` find. `{}` on any failure or no handle. Never fetches."""
    try:
        syms = _clean(symbols)
        if not syms:
            return {}
        d = db if db is not None else _default_db()
        if d is None:
            return {}
        return {s: doc for s, doc in _find_map(d[SB_COLL], syms).items() if s in syms}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: load failed: %s", type(exc).__name__)
        return {}


# ───────────────────────────────────────────── the queue + ONE worker thread
_q_lock = threading.Lock()
_queue: list = []                                              # newest request first
_inflight: set = set()
_bg = {"running": False, "thread": None}


def _thread_spawn(fn: Callable) -> None:
    t = threading.Thread(target=fn, daemon=True, name=SB_THREAD_NAME)
    t.start()
    _bg["thread"] = t


def _worker(db) -> None:
    while True:
        with _q_lock:
            if not _queue:
                _bg["running"] = False
                return
            sym = _queue.pop(0)
            _inflight.add(sym)
        try:
            rec = _find_one(db[_SIC().SI_COLL], sym)
            try:
                doc = _find_one(db[SB_COLL], sym)
            except Exception:                                  # noqa: BLE001
                doc = None
            if is_due(doc, rec):
                refresh_symbol(sym, db)
        except Exception as exc:                               # noqa: BLE001
            log.warning("share_basis: worker %s failed: %s", sym, type(exc).__name__)
        finally:
            with _q_lock:
                _inflight.discard(sym)


def kick(symbols, db=None, now=None, *, spawn: Optional[Callable] = None) -> dict:
    """Queue the DUE asked names at the FRONT (newest request first; a queued name moves to the front), drop the
    oldest past SB_QUEUE_MAX, start ONE daemon thread when none runs. -> {"queued": names added or moved,
    "pending": every ASKED name queued or in flight after this call} [C5]. Never raises. With no injected `spawn`, a
    pytest run starts nothing, reads nothing and returns empty lists (the bar_close.spawn_child guard)."""
    empty = {"queued": [], "pending": []}
    try:
        if spawn is None and os.environ.get("PYTEST_CURRENT_TEST"):
            return empty
        syms = _clean(symbols)
        if not syms:
            return empty
        d = db if db is not None else _default_db()
        if d is None:
            return empty
        now = _now(now)
        recs = _find_map(d[_SIC().SI_COLL], syms)
        try:
            docs = _find_map(d[SB_COLL], syms)
        except Exception as exc:                               # noqa: BLE001
            log.warning("share_basis: kick basis read failed: %s", type(exc).__name__)
            docs = {}
        due = [s for s in syms if is_due(docs.get(s), recs.get(s), now)]
        start = False
        with _q_lock:
            moved = [s for s in due if s not in _inflight]
            rest = [s for s in _queue if s not in moved]
            _queue[:] = (moved + rest)[:SB_QUEUE_MAX]
            queued = [s for s in moved if s in _queue]
            pending = [s for s in syms if s in _queue or s in _inflight]
            if _queue and not _bg["running"]:
                _bg["running"] = True
                start = True
        if start:
            try:
                (spawn or _thread_spawn)(lambda: _worker(d))
            except Exception as exc:                           # noqa: BLE001
                log.warning("share_basis: worker could not start: %s", type(exc).__name__)
                with _q_lock:
                    _bg["running"] = False
        return {"queued": queued, "pending": pending}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: kick failed: %s", type(exc).__name__)
        return empty


# ───────────────────────────────────────────── seed (the 11-24 float pairings, a one-time load)
def seed(rows, db=None) -> dict:
    """Write ONLY `float_track` (origin "seed", no `checked_at`) for each row whose float equals the live SI record's
    AND (no track is held, or the held track has the same value and a LATER since). Returns counts."""
    counts = {"rows": 0, "written": 0, "no_record": 0, "float_differs": 0, "held_kept": 0, "bad_row": 0,
              "write_failed": 0}
    if not isinstance(rows, dict):
        return counts
    d = db if db is not None else _default_db()
    if d is None:
        return counts
    syms = _clean(list(rows.keys()))
    recs = _find_map(d[_SIC().SI_COLL], syms)
    held = _find_map(d[SB_COLL], syms)
    for raw_sym, row in rows.items():
        counts["rows"] += 1
        sym = raw_sym.strip().upper() if isinstance(raw_sym, str) else ""
        if not sym or not isinstance(row, dict):
            counts["bad_row"] += 1
            continue
        fl, fa = _pos_int(row.get("float_shares")), _day(row.get("float_asof"))
        if fl is None or fa is None:
            counts["bad_row"] += 1
            continue
        rec = recs.get(sym)
        if not isinstance(rec, dict):
            counts["no_record"] += 1
            continue
        if _pos_int(rec.get("float_shares")) != fl:
            counts["float_differs"] += 1
            continue
        ht = (held.get(sym) or {}).get("float_track")
        if isinstance(ht, dict) and ht.get("value") is not None:
            hs = _day(ht.get("since"))
            if not (_pos_int(ht.get("value")) == fl and hs is not None and hs > fa):
                counts["held_kept"] += 1
                continue
        so = _pos_int(row.get("shares_outstanding"))
        track = {"value": fl, "since": fa, "shares": so, "shares_asof": _day(row.get("shares_asof")) if so else None,
                 "basis_asof": fa, "origin": "seed", "carried": []}
        try:
            d[SB_COLL].update_one({"_id": sym}, {"$set": {"float_track": track}}, upsert=True)
            counts["written"] += 1
        except Exception as exc:                               # noqa: BLE001
            log.warning("share_basis: seed %s write failed: %s", sym, type(exc).__name__)
            counts["write_failed"] += 1
    return counts


# ───────────────────────────────────────────── CLI
def _summary(sym: str, doc: dict) -> str:
    if not isinstance(doc, dict) or "skipped" in doc:
        return "%s skipped %s" % (sym, (doc or {}).get("skipped"))
    st = lambda k: "%s%s" % ((doc.get(k) or {}).get("status"),
                             (" (last try %s)" % doc[k]["error"]) if (doc.get(k) or {}).get("error") else "")
    tr = doc.get("float_track") or {}
    return "%s | ref %s | sec %s, %d covers, %d filings | splits %s, %d rows | track %s" % (
        sym, st("ref"), st("sec"), len((doc.get("sec") or {}).get("covers") or []),
        len((doc.get("sec") or {}).get("filings") or []), st("splits"),
        len((doc.get("splits") or {}).get("rows") or []), tr.get("origin"))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m short_interest.share_basis")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("refresh")
    r.add_argument("--symbols", required=True)
    s = sub.add_parser("seed")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--stdin", action="store_true")
    g.add_argument("--file")
    sh = sub.add_parser("show")
    sh.add_argument("--symbols", required=True)
    a = p.parse_args(argv)
    d = _default_db()
    if d is None:
        print("no database")
        return 2
    if a.cmd == "seed":
        try:
            if a.stdin:
                body = json.load(sys.stdin)
            else:
                with open(a.file) as fh:
                    body = json.load(fh)
        except (OSError, ValueError) as exc:
            print("seed input unreadable: %s" % type(exc).__name__)
            return 2
        print(json.dumps(seed(body.get("rows") if isinstance(body, dict) else None, d), sort_keys=True))
        return 0
    syms = _clean(a.symbols.split(","))
    if a.cmd == "show":
        print(json.dumps(load(syms, d), default=str, indent=1, sort_keys=True))
        return 0
    for sym in syms:
        try:
            print(_summary(sym, refresh_symbol(sym, d)))
        except Exception as exc:                               # noqa: BLE001
            print("%s failed: %s" % (sym, type(exc).__name__))
    return 0


if __name__ == "__main__":                                     # pragma: no cover
    sys.exit(main())
