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

🩳 2026-11-26 (spec sishares §3.1 + §3.3): the 6-K issuance reads go to the SEC full-text search through `sec_fts`,
which holds the one URL and no http client — every GET it makes is `_sec_get` here (the same pacer, headers and
`_http` seam). Its stop is persisted as `state|fts` and never stops data.sec.gov. The Massive ticker reference also
keeps its two share counts (`ref.share_class_shares`, `ref.weighted_shares`, dated by the read only).

🧮 2026-11-26 (spec floatguard §3.2 + §3.3): a second DATED float, Massive's free float (`MASSIVE_FLOAT_PATH`), is kept
as the `mfloat` sub-doc, behind `SB_MFLOAT_WHEN`. It is read in bulk by the nightly (`fetch_mfloats` +
`store_mfloats`) and by ONE worker step (`mfloat_step`) — never by `refresh_symbol`, which makes no new outside call:
it only carries a held `mfloat` and reaches its splits window (`since2`, never the SEC `since`) back to its date.
`widen_splits` does the same with one splits read. A doc with no `mfloat` key is built exactly as before.

✂️ 2026-11-27 (spec sicheck §3.3, K-1): the 6-K SPLIT-WORD read (`sec_fts.read_split`) is stored as `sec.fts_split`, a
SIBLING of `sec.fts` (whose shape is untouched). Its window starts at min(sec.since, the held ok second float's date);
the 6-K listing for it comes from the SAME submissions answer (`fetch_filings(wide_since=)`, no extra SEC call). ONE
extra efts GET per refresh, only when the held answer does not hold (top 6-K + window + `sec_fts.holds`); the efts stop
`state|fts` is honoured. `fts_split_step` is the same read for one name outside a refresh (the entry check's phase C).
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

from short_interest import sec_fts as SF
from short_interest import ssr_corp as SC

log = logging.getLogger("short_interest.share_basis")

# ───────────────────────────────────────────── constants (engineering — MINE, his call to change; none is a trading threshold)
SB_COLL = "si_share_basis"
SB_VERSION = 1
SB_STATE_SEC_ID = "state|sec"                 # {"_id", "blocked_until", "reason"}: a 403 / 429 stops ALL SEC calls until then
# 🩳 2026-11-26 (spec sishares §3.1, C12) — the same shape for the SEC full-text search: a 403 / 429 from efts stops ONLY
# the full-text reads (`sec_fts`) until then, never data.sec.gov.
SB_STATE_FTS_ID = "state|fts"
# ⏱ 2026-11-27 (critic finding, MEDIUM) — the SEC pace shared by EVERY process on this host (the api's on-view worker,
# the cron entry-check child, the nightly): {"_id", "next_at"} = the wall-clock epoch second of the next free slot.
SB_STATE_SEC_PACE_ID = "state|sec_pace"
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
# 🧮 2026-11-26 (spec floatguard §3.2 + §3.3) — the second DATED float: Massive's free float (`/stocks/vX/float`), the
# same host and key as the ticker reference. Read by the nightly (in bulk) and by ONE worker step (`mfloat_step`) for a
# name first seen between nights — never inside `refresh_symbol`, which only carries a held `mfloat`.
MASSIVE_FLOAT_PATH = "/stocks/vX/float"
SB_MFLOAT_WHEN = "on"                         # HIS CALL #7 — "off" (or any other word) ends every second-float call
SB_MFLOAT_MODES = ("off", "on")
SB_MFLOAT_CHUNK = 100                         # MINE (engineering) — tickers per GET = the endpoint's default page size
MFLOAT_GOOD = ("ok", "none")                  # a good second-float read (status rule)
ERR_PARTIAL = "partial"                       # a 200 answer that names a next page: its unanswered names are not "none"
ERR_TEST = "test"                             # pytest with nothing injected: no outside call

_http = None                 # the ONE SEC outside-call seam; None → requests.get (lazy import) — the reg_sho._http shape


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
        if s and s not in out and s not in (SB_STATE_SEC_ID.upper(), SB_STATE_FTS_ID.upper(),
                                            SB_STATE_SEC_PACE_ID.upper()):
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
_pace_coll = None            # seam: the collection holding state|sec_pace; None → _default_db()[SB_COLL]


def _pace_collection():
    if _pace_coll is not None:
        return _pace_coll
    d = _default_db()
    return d[SB_COLL] if d is not None else None


def _claim_shared_slot(coll, wall: Callable, sleep: Callable) -> bool:
    """ONE atomic `find_one_and_update` on state|sec_pace: next_at = max(now, next_at) + SB_SEC_MIN_INTERVAL_SEC; this
    call's slot = the new next_at − SB_SEC_MIN_INTERVAL_SEC, slept until. Two claims from any processes are therefore
    never closer than the spacing. A missing / non-number next_at counts as now. Never raises: any fault → False (the
    caller paces in-process only). A slot further ahead than SB_HTTP_TIMEOUT_SEC (the most one SEC call may already
    block) is a broken doc, not a queue: it is reset (compare-and-set on the value read) and False is returned, so a
    bad doc never blocks a call longer than that."""
    if coll is None:
        return False
    try:
        now = float(wall())
        nxt = {"$cond": [{"$isNumber": "$next_at"}, "$next_at", now]}
        doc = coll.find_one_and_update(
            {"_id": SB_STATE_SEC_PACE_ID},
            [{"$set": {"next_at": {"$add": [{"$max": [now, nxt]}, SB_SEC_MIN_INTERVAL_SEC]}}}],
            upsert=True, return_document=True)                 # True = pymongo ReturnDocument.AFTER
        got = doc.get("next_at") if isinstance(doc, dict) else None
        if isinstance(got, bool) or not isinstance(got, (int, float)):
            return False
        delay = (got - SB_SEC_MIN_INTERVAL_SEC) - float(wall())
        if delay > SB_HTTP_TIMEOUT_SEC:
            log.warning("share_basis: shared SEC pace slot %.1f s ahead — reset, in-process pace only", delay)
            coll.update_one({"_id": SB_STATE_SEC_PACE_ID, "next_at": got},
                            {"$set": {"next_at": float(wall()) + SB_SEC_MIN_INTERVAL_SEC}})
            return False
        if delay > 0:
            sleep(delay)
        return True
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: shared SEC pace failed, in-process pace only: %s", type(exc).__name__)
        return False


def _sec_wait(clock: Optional[Callable] = None, sleep: Optional[Callable] = None,
              coll=None, wall: Optional[Callable] = None) -> None:
    """Two SEC GETs never start closer than SB_SEC_MIN_INTERVAL_SEC [C12]: across PROCESSES through the state|sec_pace
    slot (`_claim_shared_slot`, wall clock), and always in-process (monotonic, module lock) — the only pace left
    when Mongo is down or faults."""
    clock = clock or time.monotonic
    sleep = sleep or time.sleep
    wall = wall or time.time
    with _sec_lock:
        try:
            c = coll if coll is not None else _pace_collection()
        except Exception:                                      # noqa: BLE001
            c = None
        _claim_shared_slot(c, wall, sleep)
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


_fts_stop = {"until": None}                                    # the in-process copy of state|fts.blocked_until


def _fts_blocked(db, now: datetime) -> bool:
    """The `_sec_blocked` shape for the full-text search stop (state|fts) [C12]."""
    until = _fts_stop["until"]
    if isinstance(until, datetime) and until > now:
        return True
    try:
        doc = _find_one(db[SB_COLL], SB_STATE_FTS_ID) if db is not None else None
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: fts state read failed: %s", type(exc).__name__)
        doc = None
    u = _parse_ts((doc or {}).get("blocked_until"))
    return bool(u is not None and u > now)


def _block_fts(db, now: datetime, reason: str, store: bool) -> None:
    """The `_block_sec` shape: SB_SEC_BLOCK_MIN, in-process + the stored doc; `store=False` writes nothing."""
    until = now + timedelta(minutes=SB_SEC_BLOCK_MIN)
    _fts_stop["until"] = until
    log.warning("share_basis: SEC full-text search answered %s — full-text reads stop until %s", reason, _ts(until))
    if not store or db is None:
        return
    try:
        db[SB_COLL].replace_one({"_id": SB_STATE_FTS_ID},
                                {"_id": SB_STATE_FTS_ID, "blocked_until": _ts(until), "reason": reason}, upsert=True)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: fts state write failed: %s", type(exc).__name__)


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


def _count(v) -> Optional[int]:
    """A provider share count: a finite number > 0 (bool / NaN / ≤ 0 / string / anything else → None)."""
    if isinstance(v, (bool, str)) or not isinstance(v, (int, float)):
        return None
    return _pos_int(v)


def fetch_ref(sym: str, *, http=None) -> dict:
    """The Massive ticker reference: {"status": "ok", "cik", "type", "share_class_shares", "weighted_shares"}
    | {"status": "absent"} (404) | {"status": "failed", "error"}. ONE GET.

    🩳 2026-11-26 (spec sishares §3.1, WP-3): the same answer's `share_class_shares_outstanding` and
    `weighted_shares_outstanding` are kept (`_count`; None when the provider gives none). The provider gives NO as-of
    date for either: they are dated by the read only."""
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
                "type": typ.strip().upper() if isinstance(typ, str) and typ.strip() else None,
                "share_class_shares": _count(res.get("share_class_shares_outstanding")),
                "weighted_shares": _count(res.get("weighted_shares_outstanding"))}
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


def _is_6k(form: str) -> bool:
    base = form.strip().upper()
    if base.endswith("/A"):
        base = base[:-2].strip()
    return base == SB_REPORT_FORMS[1]


def fetch_filings(cik10: str, since_iso: Optional[str], *, http=None, kind_fn=None,
                  wide_since: Optional[str] = None) -> dict:
    """{"status": "ok", "filings": [{"form", "filed", "items", "doc", "file", "accn", "with"}] (newest first,
    filed >= since, only kinds `kind_fn(form, items)` names, at most SB_FILINGS_KEPT), "top_accn"[, "cap"]}
    | {"status": "failed", "error", "blocked": bool}.

    📄 2026-11-26 (spec sitrack §3.1, A1): `doc` = primaryDocument, `file` = fileNumber, `accn` = accessionNumber
    (each a non-empty string or None — a missing or ragged array leaves them None and the row counts as before);
    `with` = the form of the first report (`_is_report`) in listing order the issuer filed the SAME day, read over the
    WHOLE listing before the kind filter (an 8-K 8.01 that is not kept still marks its day), else None. `cap` =
    SB_FILINGS_KEPT, present only when the kind-filtered list was longer than it.

    🩳 2026-11-26 (spec sishares §3.3): `reports` = the 6-K / 6-K/A rows (base SB_REPORT_FORMS[1]) filed >= since,
    [{"form", "filed", "accn", "doc"}] newest first, listing order on a tie — whatever `kind_fn` says (a 6-K is never
    in `filings` by itself; the full-text step marks the issuance ones).

    ✂️ 2026-11-27 (spec sicheck §3.3): `wide_since` given → also `reports_wide` = the same 6-K rows filed >= wide_since
    (the split-word window, from the SAME answer — no extra call); not given → the answer is exactly as before."""
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
        wide = _day(wide_since) if wide_since is not None else None
        wide_rows: list = []
        n = min(len(forms), len(dates))
        report_on: dict = {}                                   # filed day → the first report's form, listing order
        for i in range(n):
            form = forms[i].strip() if isinstance(forms[i], str) else ""
            filed = _day(dates[i])
            if form and filed and filed not in report_on and _is_report(form):
                report_on[filed] = form
        rows, top, reports = [], None, []
        for i in range(n):
            form = forms[i].strip() if isinstance(forms[i], str) else ""
            filed = _day(dates[i])
            if not form or not filed:
                continue
            it = items[i] if i < len(items) and isinstance(items[i], str) else ""
            accn = accns[i] if i < len(accns) and isinstance(accns[i], str) and accns[i].strip() else None
            if accn and form.upper().startswith(SEC_PERIODIC_PREFIXES) and (top is None or filed > top[0]):
                top = (filed, accn.strip())
            if wide and accn and _is_6k(form) and filed >= wide:
                wide_rows.append({"form": form, "filed": filed, "accn": accn.strip(), "doc": _str_at(docs, i)})
            if since and filed < since:
                continue
            if accn and _is_6k(form):
                reports.append({"form": form, "filed": filed, "accn": accn.strip(), "doc": _str_at(docs, i)})
            if kf(form, it) is None:
                continue
            rows.append({"form": form, "filed": filed, "items": it, "doc": _str_at(docs, i),
                         "file": _str_at(files, i), "accn": accn.strip() if accn else None,
                         "with": report_on.get(filed)})
        rows.sort(key=lambda x: x["filed"], reverse=True)
        reports.sort(key=lambda x: x["filed"], reverse=True)
        out = {"status": "ok", "filings": rows[:SB_FILINGS_KEPT], "top_accn": top[1] if top else None,
               "reports": reports}
        if len(rows) > SB_FILINGS_KEPT:
            out["cap"] = SB_FILINGS_KEPT
        if wide_since is not None:
            wide_rows.sort(key=lambda x: x["filed"], reverse=True)
            out["reports_wide"] = wide_rows
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


# ───────────────────────────────────────────── 🧮 the second dated float (spec floatguard §3.2 + §3.3)
def mfloat_on(mode=None) -> bool:
    """The switch: True only for the word "on" (SB_MFLOAT_WHEN read at call time; any other word = off)."""
    m = SB_MFLOAT_WHEN if mode is None else mode
    return m in SB_MFLOAT_MODES and m == SB_MFLOAT_MODES[1]


def _under_test(seam) -> bool:
    """The `kick` guard shape: nothing injected inside a pytest run -> no outside call."""
    return seam is None and bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _mfloat_row(x) -> Optional[dict]:
    """One usable float row: `free_float` passes `_count`, `effective_date` passes `_day`; the % only when
    0 < pct <= 100 (else None)."""
    if not isinstance(x, dict):
        return None
    shares, as_of = _count(x.get("free_float")), _day(x.get("effective_date"))
    if shares is None or as_of is None:
        return None
    return {"status": "ok", "shares": shares, "pct": _mfloat_pct(x.get("free_float_percent")), "as_of": as_of}


def _mfloat_pct(p) -> Optional[float]:
    """`free_float_percent` as a float when 0 < pct <= 100 (bool / string / NaN / out of range -> None)."""
    f = None if isinstance(p, (bool, str)) else _num(p)
    return float(f) if f is not None and 0 < f <= 100 else None


def _mfloat_chunk(get, key: str, chunk: list, out: dict) -> None:
    """ONE GET for `chunk` = [(SYM, massive ticker)]; fills `out[SYM]`. A non-200 / malformed / raising answer, or a
    200 that names a `next_url`, leaves every name it does not answer `failed` — never `none`."""
    names = [s for s, _ in chunk]
    try:
        tick = []
        for _, t in chunk:
            if t not in tick:
                tick.append(t)
        r = get(SC.BASE_URL + MASSIVE_FLOAT_PATH,
                params={"ticker.any_of": ",".join(tick), "limit": SB_MFLOAT_CHUNK, "apiKey": key},
                timeout=SB_HTTP_TIMEOUT_SEC)
        code = _status(r)
        if code != 200:
            raise _ChunkFail("http_%d" % code)
        try:
            body = r.json()
        except Exception:                                      # noqa: BLE001 — a non-JSON 200
            raise _ChunkFail(ERR_MALFORMED)
        res = body.get("results") if isinstance(body, dict) else None
        if not isinstance(res, list):
            raise _ChunkFail(ERR_MALFORMED)
        best: dict = {}                                        # massive ticker -> the newest usable row
        for x in res:
            t = x.get("ticker") if isinstance(x, dict) else None
            row = _mfloat_row(x)
            if not isinstance(t, str) or row is None:
                continue
            t = t.strip().upper()
            if t not in best or row["as_of"] > best[t]["as_of"]:
                best[t] = row
        partial = bool(body.get("next_url"))
        for s, t in chunk:
            if t in best:
                out[s] = dict(best[t])
            elif partial:
                out[s] = {"status": "failed", "error": ERR_PARTIAL}
            else:
                out[s] = {"status": "none"}
    except _ChunkFail as cf:
        for s in names:
            out[s] = {"status": "failed", "error": cf.code}
    except Exception as exc:                                   # noqa: BLE001
        e = _err(exc)
        for s in names:
            out[s] = {"status": "failed", "error": e}


class _ChunkFail(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def fetch_mfloats(symbols, *, http=None) -> dict:
    """{SYM: {"status": "ok", "shares", "pct", "as_of"} | {"status": "none"} | {"status": "failed", "error"}}.

    ONE GET per SB_MFLOAT_CHUNK names (`ticker.any_of`, `limit`, the key in params only). `http` None under pytest ->
    every name failed ERR_TEST, no GET. No key -> every name failed ERR_NO_KEY, no GET. Tickers are spelled
    `symbols.for_massive(symbols.resolve(s))` and mapped back. `none` ONLY for a name absent from an HTTP 200 answer
    with no `next_url`. Never raises; only the exception TYPE is kept."""
    syms = _clean(symbols)
    if not syms:
        return {}
    if _under_test(http):
        return {s: {"status": "failed", "error": ERR_TEST} for s in syms}
    out: dict = {}
    try:
        key = SC._key()
        if not key:
            return {s: {"status": "failed", "error": ERR_NO_KEY} for s in syms}
        from sepa import symbols as SYM                        # lazy
        pairs = []
        for s in syms:
            try:
                t = SYM.for_massive(SYM.resolve(s))
            except Exception:                                  # noqa: BLE001
                t = s
            pairs.append((s, (t if isinstance(t, str) and t.strip() else s).strip().upper()))
        get = SC._getter(http)
        for i in range(0, len(pairs), SB_MFLOAT_CHUNK):
            _mfloat_chunk(get, key, pairs[i:i + SB_MFLOAT_CHUNK], out)
    except Exception as exc:                                   # noqa: BLE001
        e = _err(exc)
        for s in syms:
            out.setdefault(s, {"status": "failed", "error": e})
    for s in syms:
        out.setdefault(s, {"status": "failed", "error": ERR_MALFORMED})
    return out


MFLOAT_EMPTY = {"shares": None, "pct": None, "as_of": None}


def _mfloat_good(sub) -> bool:
    return isinstance(sub, dict) and sub.get("status") in MFLOAT_GOOD


def mfloat_sub(held, got, now_iso) -> dict:
    """PURE: the stored §3.2 sub-doc for ONE fetched answer, against the held one (the house status rule:
    `_ok_sub` on a good answer; `_failed_sub` keeps a held good read + error). `now_iso` = a timestamp string (a
    datetime is accepted and written in the house format)."""
    ts = now_iso if isinstance(now_iso, str) else _ts(_now(now_iso))
    g = got if isinstance(got, dict) else {}
    if g.get("status") == "ok" and _count(g.get("shares")) is not None and _day(g.get("as_of")):
        return _ok_sub({"status": "ok", "shares": _count(g.get("shares")), "pct": _mfloat_pct(g.get("pct")),
                        "as_of": _day(g.get("as_of"))}, ts)
    if g.get("status") == "none":
        return _ok_sub(dict({"status": "none"}, **MFLOAT_EMPTY), ts)
    err = g.get("error") if isinstance(g.get("error"), str) and g.get("error") else ERR_MALFORMED
    h = held if isinstance(held, dict) else None
    if _mfloat_good(h):
        return _failed_sub(h, err, ts, dict(MFLOAT_EMPTY))     # the held read stands: data + read_at, + error
    return _failed_sub({"strikes": _strikes(h)} if h else None, err, ts, dict(MFLOAT_EMPTY))


def store_mfloats(db, got: dict, now=None) -> dict:
    """Write each fetched answer as the `mfloat` sub-doc of a CHECKED basis doc: `update_one({"_id": sym,
    "checked_at": {"$exists": True}}, {"$set": {"mfloat": sub}})` — never an upsert, never a state doc, never a
    seed-only doc. -> {"written": docs set, "no_doc": names with no checked doc, "failed": writes that raised}."""
    counts = {"written": 0, "no_doc": 0, "failed": 0}
    try:
        if db is None or not isinstance(got, dict):
            return counts
        ans = {}
        for k, v in got.items():
            c = _clean([k])
            if c:
                ans[c[0]] = v
        if not ans:
            return counts
        ts = _ts(_now(now))
        coll = db[SB_COLL]
        held = _find_map(coll, list(ans))
        for sym, g in ans.items():
            doc = held.get(sym)
            if not isinstance(doc, dict) or doc.get("checked_at") is None:
                counts["no_doc"] += 1
                continue
            sub = mfloat_sub(doc.get("mfloat"), g, ts)
            try:
                coll.update_one({"_id": sym, "checked_at": {"$exists": True}}, {"$set": {"mfloat": sub}})
                counts["written"] += 1
            except Exception as exc:                           # noqa: BLE001
                log.warning("share_basis: %s mfloat write failed: %s", sym, type(exc).__name__)
                counts["failed"] += 1
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: mfloat store failed: %s", type(exc).__name__)
    return counts


def _mfloat_fresh(held, now) -> bool:
    """A held good second-float read (`ok` / `none`), no error, read inside SB_REF_REFRESH_DAYS."""
    if not _mfloat_good(held) or held.get("error"):
        return False
    r = _parse_ts(held.get("read_at"))
    return r is not None and timedelta(0) <= _now(now) - r < timedelta(days=SB_REF_REFRESH_DAYS)


def mfloat_step(sym, db=None, now=None, *, http=None) -> str:
    """THE per-name second-float read the worker makes after its refresh. First match: "off" (the switch) · "test"
    (`http` None under pytest — before any read) · "no_doc" (no doc, or no `checked_at`) · "fresh" · "stored" (a
    good answer written) · "failed". Never raises."""
    try:
        if not mfloat_on():
            return "off"
        if _under_test(http):
            return "test"
        c = _clean([sym])
        d = db if db is not None else _default_db()
        if not c or d is None:
            return "no_doc"
        s = c[0]
        doc = _find_one(d[SB_COLL], s)
        if not isinstance(doc, dict) or doc.get("checked_at") is None:
            return "no_doc"
        now = _now(now)
        if _mfloat_fresh(doc.get("mfloat"), now):
            return "fresh"
        got = fetch_mfloats([s], http=http).get(s) or {"status": "failed", "error": ERR_MALFORMED}
        w = store_mfloats(d, {s: got}, now)
        return "stored" if got.get("status") in MFLOAT_GOOD and w.get("written") == 1 else "failed"
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: mfloat step failed: %s", type(exc).__name__)
        return "failed"


def checked_symbols(db=None) -> list:
    """Every `_id` of SB_COLL that holds `checked_at` and survives `_clean` (never SB_STATE_SEC_ID /
    SB_STATE_FTS_ID, never a seed-only doc), sorted. [] on any failure or no handle."""
    try:
        d = db if db is not None else _default_db()
        if d is None:
            return []
        ids = []
        for doc in d[SB_COLL].find({"checked_at": {"$exists": True}}, {"_id": 1, "checked_at": 1}):
            if isinstance(doc, dict) and isinstance(doc.get("_id"), str) and doc.get("checked_at") is not None:
                c = _clean([doc["_id"]])
                if c and c[0] == doc["_id"]:
                    ids.append(c[0])
        return sorted(set(ids))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: checked symbols read failed: %s", type(exc).__name__)
        return []


def _mfloat_asof(doc) -> Optional[str]:
    """The date of a held `ok` second float, else None."""
    mf = doc.get("mfloat") if isinstance(doc, dict) else None
    if not isinstance(mf, dict) or mf.get("status") != "ok":
        return None
    return _day(mf.get("as_of"))


def needs_window(doc) -> bool:
    """A held `ok` second float with a dated `as_of`, and (no dated `splits.since`, or `as_of` < `splits.since`): the
    splits on file do not reach back to its date."""
    a = _mfloat_asof(doc)
    if a is None:
        return False
    sp = doc.get("splits") if isinstance(doc.get("splits"), dict) else {}
    since = _day(sp.get("since"))
    return since is None or a < since


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


REF_COUNT_KEYS = ("share_class_shares", "weighted_shares")


def _ref_fresh(href, now: datetime) -> bool:
    """A held ok ref read inside SB_REF_REFRESH_DAYS — and [C16] holding BOTH count keys (a ref read before 2026-11-26
    has neither and is read once more)."""
    if not isinstance(href, dict) or href.get("status") != "ok":
        return False
    if any(k not in href for k in REF_COUNT_KEYS):
        return False
    r = _parse_ts(href.get("read_at"))
    return r is not None and timedelta(0) <= now - r < timedelta(days=SB_REF_REFRESH_DAYS)


# ───────────────────────────────────────────── the 6-K full-text step (spec sishares §3.3)
def _fts_empty(since) -> dict:
    return {"since": since, "top_6k": None, "top_6k_filed": None, "issuance": [], "number": None}


def _fts_good(sub) -> bool:
    return isinstance(sub, dict) and sub.get("status") in SF.FTS_GOOD


def _failed_fts(held, error: str, now_iso: str, since) -> dict:
    """The status rule on the full-text sub-doc: a held good read stands + error; nothing good held → `failed`."""
    if _fts_good(held):
        out = dict(held)
        out.update({"error": error, "error_at": now_iso, "strikes": _strikes(held) + 1})
        return out
    out = dict({"status": "failed"}, **_fts_empty(since))
    out.update({"read_at": None, "error": error, "error_at": now_iso, "strikes": _strikes(held) + 1})
    return out


def _fts_get(http):
    return lambda url: _sec_get(url, http)                     # the ONE pacer, the generic headers, the `_http` seam


def _accns(rows) -> list:
    return [r.get("accn") for r in rows or [] if isinstance(r, dict)]


def _fts_reask(held: dict, top: dict, since) -> bool:
    """A held good answer is asked again when the newest 6-K moved, the window moved, the last try failed (`error`
    set — re-asked on the name's next pass, which `is_due` schedules at SB_REFRESH_MIN: `sec.fts` does not take the
    SB_ERROR_RETRY_MIN retry of ref / sec / splits), or [C8] `holds` says a no-hit read was made too soon after the
    newest 6-K was filed."""
    if held.get("top_6k") != top["accn"] or _day(held.get("since")) != since or held.get("error"):
        return True
    return not SF.holds(held.get("top_6k_filed"), held.get("read_at"), top["accn"] in _accns(held.get("issuance")))


def _fts_step(db, cik, held, reports, since, now, now_iso, http, store, sink=None) -> dict:
    """sec.fts (spec §3.1): FTS_WHEN off → "off", no call · no 6-K in the window → "none_6k", no call · else the
    phrase query (re-asked per `_fts_reask`; the stop and the status rule as on every SEC sub-doc). The held
    `number` rides along; step 8b of `refresh_symbol` owns it."""
    held = held if isinstance(held, dict) else None
    if not SF.fts_on():
        out = dict({"status": "off"}, **_fts_empty(since))
        out.update({"read_at": None, "error": None, "error_at": None, "strikes": 0})
        return out
    if not reports:
        return _ok_sub(dict({"status": "none_6k"}, **_fts_empty(since)), now_iso)
    top = reports[0]
    good = _fts_good(held)
    if good and held.get("status") == "ok" and not _fts_reask(held, top, since):
        return dict(held)
    if _fts_blocked(db, now):
        if good:
            out = dict(held)                                   # no call; the held answer stays as it is …
            if held.get("status") == "none_6k" or held.get("top_6k") != top["accn"] \
                    or _day(held.get("since")) != since:
                out.update({"error": "blocked", "error_at": now_iso})   # … [C1] flagged when it no longer covers
            return out
        out = dict({"status": "blocked"}, **_fts_empty(since))
        out.update({"read_at": None, "error": None, "error_at": now_iso, "strikes": _strikes(held)})
        return out
    got = SF.read_issuance(cik, since, SF.et_day(now), reports, get=_fts_get(http))
    if got.get("status") != "ok":
        if isinstance(sink, dict):
            sink["fts_failed"] = True                          # step 8b asks nothing on a pass whose phrase read failed
        if got.get("code") in SEC_BLOCK_HTTP:
            _block_fts(db, now, got.get("error") or "blocked", store)
        return _failed_fts(held, got.get("error") or "error", now_iso, since)
    hn = held.get("number") if held and isinstance(held.get("number"), dict) else None
    out = {"status": "ok", "since": since, "top_6k": top["accn"], "top_6k_filed": top["filed"],
           "issuance": got.get("issuance") or [], "number": hn}
    if got.get("cap"):
        out["cap"] = got["cap"]
    return _ok_sub(out, now_iso)


def _marked(fts, since) -> list:
    """The issuance 6-Ks of a good full-text answer as `sec.filings` rows (spec §3.1), filed >= since."""
    if not isinstance(fts, dict) or fts.get("status") != "ok":
        return []
    out = []
    for r in fts.get("issuance") or []:
        if not isinstance(r, dict) or not isinstance(r.get("accn"), str) or not _day(r.get("filed")):
            continue
        if since and r["filed"] < since:
            continue
        out.append({"form": r.get("form") or SB_REPORT_FORMS[1], "filed": r["filed"], "items": "",
                    "doc": r.get("doc"), "file": None, "accn": r["accn"], "with": None, "fts": SF.FTS_ISSUANCE})
    return out


def _with_marked(filings: list, marked: list) -> tuple:
    """(rows filed DESC, capped at SB_FILINGS_KEPT, cut: bool). A marked accession already listed is marked in place."""
    rows = [dict(f) for f in filings]
    have = {f.get("accn"): f for f in rows if f.get("accn")}
    for m in marked:
        if m["accn"] in have:
            have[m["accn"]]["fts"] = SF.FTS_ISSUANCE
        else:
            rows.append(m)
    rows.sort(key=lambda x: x.get("filed") or "", reverse=True)
    return rows[:SB_FILINGS_KEPT], len(rows) > SB_FILINGS_KEPT


def _number_step(db, rec, doc, held_fts, reports, cik, now, now_iso, http, growth_fn, store, fts_failed=False) -> None:
    """Step 8b (spec §3.3): the exact-number query, IN PLACE on doc.sec.fts.number. Asked only when the full-text
    answer is ok, 6-Ks exist in the window, the verdict's growth gives n = to − from > 0, and (n, from, to, since,
    top_6k) moved or [C8] the held answer does not `holds`. A failed try keeps the held number and sets `error`."""
    sec = doc.get("sec") if isinstance(doc.get("sec"), dict) else {}
    fts = sec.get("fts")
    if fts_failed or not SF.fts_on() or not reports or not cik or not isinstance(fts, dict) \
            or fts.get("status") != "ok":
        return
    today = SF.et_day(now)
    try:
        g = (growth_fn or SF.default_growth_fn())(dict(rec), doc, today)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: %s growth read failed: %s", doc.get("_id"), type(exc).__name__)
        return
    nums = SF.growth_numbers(g)
    if nums is None:
        return
    n, a, b = nums
    since, top = sec.get("since"), reports[0]
    hn = fts.get("number") if isinstance(fts.get("number"), dict) else None
    hf = held_fts if isinstance(held_fts, dict) else {}
    same = bool(hn and hn.get("n") == n and hn.get("from") == a and hn.get("to") == b
                and _day(hf.get("since")) == _day(since) and hf.get("top_6k") == top["accn"])
    if same and SF.holds(top["filed"], hn.get("read_at"), bool(hn.get("hits"))):
        return
    if _fts_blocked(db, now):
        return
    got = SF.read_number(cik, n, since, today, reports, get=_fts_get(http))
    if got.get("status") == "ok":
        fts["number"] = {"n": n, "from": a, "to": b, "read_at": now_iso, "hits": got.get("hits") or []}
        return
    if got.get("code") in SEC_BLOCK_HTTP:
        _block_fts(db, now, got.get("error") or "blocked", store)
    fts.update({"error": got.get("error") or "error", "error_at": now_iso, "strikes": _strikes(fts) + 1})


# ───────────────────────────────────────────── ✂️ the 6-K split-word step (spec sicheck §3.3, K-1)
def _split_empty(since) -> dict:
    return {"since": since, "top_6k": None, "top_6k_filed": None, "rows": []}


def _split_good(sub) -> bool:
    return isinstance(sub, dict) and sub.get("status") in SF.FTS_GOOD


def _failed_split(held, error: str, now_iso: str, since) -> dict:
    """The status rule on `sec.fts_split`: a held good read stands + error; nothing good held → `failed`."""
    if _split_good(held):
        out = dict(held)
        out.update({"error": error, "error_at": now_iso, "strikes": _strikes(held) + 1})
        return out
    out = dict({"status": "failed"}, **_split_empty(since))
    out.update({"read_at": None, "error": error, "error_at": now_iso, "strikes": _strikes(held) + 1})
    return out


def _split_reask(held: dict, top: dict, since) -> bool:
    """The `_fts_reask` rule on the split-word answer: asked again when the newest 6-K moved, the window moved, the
    last try failed, or `sec_fts.holds` says a no-hit read was made too soon after the newest 6-K was filed."""
    if held.get("top_6k") != top["accn"] or _day(held.get("since")) != since or held.get("error"):
        return True
    return not SF.holds(held.get("top_6k_filed"), held.get("read_at"), top["accn"] in _accns(held.get("rows")))


def _fts_split_step(db, cik, held, reports, since, now, now_iso, http, store) -> dict:
    """`sec.fts_split` (K-1): FTS_SPLIT_WHEN off → "off", no call · no 6-K in the window → "none_6k", no call · a held
    `ok` answer that still holds → kept as is, no call · the efts stop on → the held answer stands (flagged `blocked`
    when it no longer covers) or status `blocked` · else ONE split-word query (`sec_fts.read_split`); a 403 / 429
    sets the efts stop (`state|fts`, never data.sec.gov's)."""
    held = held if isinstance(held, dict) else None
    if not SF.split_on():
        out = dict({"status": "off"}, **_split_empty(since))
        out.update({"read_at": None, "error": None, "error_at": None, "strikes": 0})
        return out
    if not reports:
        return _ok_sub(dict({"status": "none_6k"}, **_split_empty(since)), now_iso)
    top = reports[0]
    good = _split_good(held)
    if good and held.get("status") == "ok" and not _split_reask(held, top, since):
        return dict(held)
    if _fts_blocked(db, now):
        if good:
            out = dict(held)
            if held.get("status") == "none_6k" or held.get("top_6k") != top["accn"] \
                    or _day(held.get("since")) != since:
                out.update({"error": "blocked", "error_at": now_iso})
            return out
        out = dict({"status": "blocked"}, **_split_empty(since))
        out.update({"read_at": None, "error": None, "error_at": now_iso, "strikes": _strikes(held)})
        return out
    got = SF.read_split(cik, since, SF.et_day(now), reports, get=_fts_get(http))
    if got.get("status") != "ok":
        if got.get("code") in SEC_BLOCK_HTTP:
            _block_fts(db, now, got.get("error") or "blocked", store)
        return _failed_split(held, got.get("error") or "error", now_iso, since)
    out = {"status": "ok", "since": since, "top_6k": top["accn"], "top_6k_filed": top["filed"],
           "rows": got.get("rows") or []}
    if got.get("cap"):
        out["cap"] = got["cap"]
    return _ok_sub(out, now_iso)


def split_since(doc) -> Optional[str]:
    """K-1 `since`: min(sec.since, the held ok second float's date), else whichever is dated, else None."""
    if not isinstance(doc, dict):
        return None
    sec = doc.get("sec") if isinstance(doc.get("sec"), dict) else {}
    ds = [x for x in (_day(sec.get("since")), _mfloat_asof(doc)) if x]
    return min(ds) if ds else None


def _split_still(held, sec, wide) -> bool:
    """A held split-word answer needs no new listing read: good, no error, the same window, read no earlier than the
    6-K listing on file (`sec.read_at`), and (none_6k, or `sec_fts.holds`)."""
    if not _split_good(held) or held.get("error") or _day(held.get("since")) != wide:
        return False
    hr = _parse_ts(held.get("read_at"))
    sr = _parse_ts(sec.get("read_at")) if isinstance(sec, dict) else None
    if hr is None or sr is None or hr < sr:
        return False
    if held.get("status") == "none_6k":
        return True
    return SF.holds(held.get("top_6k_filed"), held.get("read_at"), held.get("top_6k") in _accns(held.get("rows")))


def _no_kind(form, items):
    return None


def fts_split_step(sym, db=None, now=None, *, http=None) -> str:
    """✂️ THE split-word read for one name outside a refresh (the entry check's phase C; the `mfloat_step` shape).
    First match: "off" (FTS_SPLIT_WHEN) · "test" (`http` None under pytest — before any read) · "no_doc" (no checked
    doc, no `sec`, no CIK, no window) · "held" (the held answer still holds — no call) · "failed" (the SEC stop, the
    listing read or the write failed, or the efts read failed: the held answer stands) · "stored". A needed read is
    ONE data.sec.gov listing GET (`fetch_filings`, the 6-K rows of its window) + at most ONE efts GET; the write is
    `update_one({"_id", "checked_at": {"$exists": True}}, {"$set": {"sec.fts_split": sub}})`, never an upsert.
    Never raises."""
    try:
        if not SF.split_on():
            return "off"
        if _under_test(http):
            return "test"
        c = _clean([sym])
        d = db if db is not None else _default_db()
        if not c or d is None:
            return "no_doc"
        s = c[0]
        doc = _find_one(d[SB_COLL], s)
        if not isinstance(doc, dict) or doc.get("checked_at") is None or not isinstance(doc.get("sec"), dict):
            return "no_doc"
        ref = doc.get("ref") if isinstance(doc.get("ref"), dict) else {}
        cik = ref.get("cik") if ref.get("status") == "ok" else None
        wide = split_since(doc)
        if not cik or wide is None:
            return "no_doc"
        sec = doc["sec"]
        held = sec.get("fts_split") if isinstance(sec.get("fts_split"), dict) else None
        if _split_still(held, sec, wide):
            return "held"
        now = _now(now)
        now_iso = _ts(now)
        if _sec_blocked(d, now):
            return "failed"
        got = fetch_filings(cik, wide, http=http, kind_fn=_no_kind)
        if got.get("status") != "ok":
            if got.get("blocked"):
                _block_sec(d, now, got.get("error") or "blocked", True)
            return "failed"
        sub = _fts_split_step(d, cik, held, got.get("reports") or [], wide, now, now_iso, http, True)
        if held is not None and sub == held:
            return "held"
        try:
            d[SB_COLL].update_one({"_id": s, "checked_at": {"$exists": True}}, {"$set": {"sec.fts_split": sub}})
        except Exception as exc:                               # noqa: BLE001
            log.warning("share_basis: %s split-word write failed: %s", s, type(exc).__name__)
            return "failed"
        return "stored" if _split_good(sub) and not sub.get("error") else "failed"
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: split-word step failed: %s", type(exc).__name__)
        return "failed"


# ───────────────────────────────────────────── one name
def _splits_sub(sym, held_splits, since_iso, now_iso, splits_fetch=None) -> dict:
    """Step 7 of `refresh_symbol` (moved verbatim, spec floatguard §3.3): ONE splits read from `since_iso` -> the
    `splits` sub-doc (`_ok_sub`), or the status rule over the held one (`_failed_sub`). `widen_splits` shares it."""
    got = fetch_splits(sym, since_iso, fetch=splits_fetch)
    if got.get("status") == "ok":
        return _ok_sub({"status": "ok", "since": since_iso, "rows": got.get("rows") or []}, now_iso)
    return _failed_sub(held_splits, got.get("error") or "error", now_iso, {"since": since_iso, "rows": []})


def widen_splits(sym, db=None, now=None, *, splits_fetch=None, store=True) -> dict:
    """Reach the splits window back to a held second float's date with ONE splits read (spec floatguard §3.3).
    -> {"status": "widened" | "not_needed" | "no_doc" | "failed" | "test", "splits": sub | None}. "test" =
    `splits_fetch` None under pytest (no read at all). `store` -> `update_one({"_id": sym, "checked_at": {"$exists":
    True}}, {"$set": {"splits": sub}})` (never an upsert); `store=False` writes nothing and still returns the sub. A
    failed read keeps the held rows and `since` and sets `error` (the status rule). Never raises."""
    try:
        if _under_test(splits_fetch):
            return {"status": "test", "splits": None}
        c = _clean([sym])
        d = db if db is not None else _default_db()
        if not c or d is None:
            return {"status": "no_doc", "splits": None}
        s = c[0]
        doc = _find_one(d[SB_COLL], s)
        if not isinstance(doc, dict) or doc.get("checked_at") is None:
            return {"status": "no_doc", "splits": None}
        if not needs_window(doc):
            return {"status": "not_needed", "splits": None}
        sub = _splits_sub(s, doc.get("splits"), _mfloat_asof(doc), _ts(_now(now)), splits_fetch)
        if store:
            try:
                d[SB_COLL].update_one({"_id": s, "checked_at": {"$exists": True}}, {"$set": {"splits": sub}})
            except Exception as exc:                           # noqa: BLE001
                log.warning("share_basis: %s splits write failed: %s", s, type(exc).__name__)
                return {"status": "failed", "splits": sub}
        return {"status": "widened" if sub.get("status") == "ok" and not sub.get("error") else "failed",
                "splits": sub}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: widen splits failed: %s", type(exc).__name__)
        return {"status": "failed", "splits": None}


def _sec_step(db, cik, ref, held, since, now, now_iso, http, kind_fn, store, sink=None, wide=None) -> dict:
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
    if wide is not None:                                       # ✂️ the split-word window rides the SAME answer
        got = fetch_filings(cik, since, http=http, kind_fn=kind_fn, wide_since=wide)
    else:
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
    # 🩳 2026-11-26 (spec sishares §3.3) — the 6-K full-text step, then its issuance rows join `filings`
    reports = got.get("reports") or []
    if isinstance(sink, dict):
        sink["reports"] = reports
        if wide is not None:
            sink["reports_split"] = got.get("reports_wide") or []
    fts = _fts_step(db, cik, held.get("fts") if isinstance(held, dict) else None, reports, since, now, now_iso,
                    http, store, sink)
    filings, cut = _with_marked(got.get("filings") or [], _marked(fts, since))
    out = {"status": status, "since": since, "top_accn": got.get("top_accn"),
           "covers": covers, "filings": filings, "fts": fts}
    if got.get("cap"):                                         # 📄 2026-11-26 — the kept-row cap cut the list
        out["filings_cap"] = got["cap"]
    elif cut:
        out["filings_cap"] = SB_FILINGS_KEPT
    return _ok_sub(out, now_iso)


def refresh_symbol(sym: str, db=None, now=None, *, http=None, splits_fetch=None, track_fn=None, kind_fn=None,
                   growth_fn=None, store: bool = True) -> dict:
    """Re-read one name's share basis (spec §3.2 steps 1–9) and return the §3.1 doc; `store=False` writes nothing.
    🩳 2026-11-26: `growth_fn(rec, doc, today)` is the step-8b seam (default `sec_fts.default_growth_fn()`)."""
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
            ref = _ok_sub({"status": got["status"], "cik": got.get("cik"), "type": got.get("type"),
                           "share_class_shares": got.get("share_class_shares"),
                           "weighted_shares": got.get("weighted_shares")}, now_iso)       # both keys always [C16]
        else:
            ref = _failed_sub(href, got.get("error") or "error", now_iso,
                              {"cik": None, "type": None, "share_class_shares": None, "weighted_shares": None})
    cik = ref.get("cik") if ref.get("status") == "ok" else None
    # 2b. 🧮 2026-11-26 (spec floatguard §3.3) — a held second float is CARRIED, never read here (no call, whatever
    # the switch says): its date only widens the splits window (step 7)
    mf = held.get("mfloat") if isinstance(held.get("mfloat"), dict) else None
    # 3. Yahoo's live row
    yahoo = _yahoo_row(d, sym)
    # 4. the window
    track_held = held.get("float_track") if isinstance(held.get("float_track"), dict) else None
    dates = [_day(rec.get(k)) for k in ("settlement_date", "prev_settlement_date", "float_asof", "shares_asof")]
    dates.append(_day((track_held or {}).get("since")))
    since = min(x for x in dates if x)
    # 5. SEC (+ the 6-K full-text step)
    held_sec = held.get("sec") if isinstance(held.get("sec"), dict) else None
    held_fts = held_sec.get("fts") if held_sec and isinstance(held_sec.get("fts"), dict) else None
    sink: dict = {}
    mf_day = _day(mf.get("as_of")) if mf is not None and mf.get("status") == "ok" else None
    wide = min(since, mf_day) if mf_day else since             # ✂️ K-1 `since`
    sec = _sec_step(d, cik, ref, held.get("sec"), since, now, now_iso, http, kind_fn, store, sink=sink, wide=wide)
    # 5b. ✂️ 2026-11-27 (spec sicheck §3.3) — the split-word read, a SIBLING of sec.fts; no listing read → carried
    held_split = held_sec.get("fts_split") if held_sec and isinstance(held_sec.get("fts_split"), dict) else None
    if "reports_split" in sink:
        sec["fts_split"] = _fts_split_step(d, cik, held_split, sink["reports_split"], wide, now, now_iso, http, store)
    elif held_split is not None and isinstance(sec, dict) and "fts_split" not in sec:
        sec["fts_split"] = dict(held_split)
    # 6. reach back to the cover in force when the float was first seen
    tsince = _day((track_held or {}).get("since")) or _day(rec.get("float_asof"))
    since2 = since
    if tsince:
        before = [c.get("as_of") for c in (sec.get("covers") or [])
                  if isinstance(c, dict) and _day(c.get("as_of")) and c["as_of"] <= tsince]
        if before and max(before) < since2:
            since2 = max(before)
    # 🧮 the splits window reaches back to a held ok second float's date — `since2` ONLY (the SEC window `since` and
    # the 📄 flags never move)
    mf_asof = _day(mf.get("as_of")) if mf is not None and mf.get("status") == "ok" else None
    if mf_asof and mf_asof < since2:
        since2 = mf_asof
    # 7. splits
    hsp = held.get("splits")
    splits = _splits_sub(sym, hsp, since2, now_iso, splits_fetch)
    # 8. the float track (held rows count even when the last try failed [C1])
    rows = splits.get("rows") if splits.get("status") == "ok" else None
    try:
        track = (track_fn or _default_track_fn())(track_held, dict(rec), rows)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: %s track update failed: %s", sym, type(exc).__name__)
        track = track_held
    doc = {"_id": sym, "v": SB_VERSION, "checked_at": now_iso, "seen": _seen_of(rec),
           "ref": ref, "sec": sec, "splits": splits, "yahoo": yahoo, "float_track": track}
    if mf is not None:
        doc["mfloat"] = mf                                     # 🧮 carried as held, byte for byte
    # 8b. 🩳 2026-11-26 — the exact share count added, read through the SEC full-text search (in place on sec.fts)
    try:
        _number_step(d, rec, doc, held_fts, sink.get("reports") or [], cik, now, now_iso, http, growth_fn, store,
                     fts_failed=bool(sink.get("fts_failed")))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("share_basis: %s number step failed: %s", sym, type(exc).__name__)
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
    SB_ERROR_STRIKES strikes) · `checked_at` SB_REFRESH_MIN old. 🩳 2026-11-26: `sec.fts` is NOT read here — a
    failed / blocked full-text read (or a number-read `error`) waits for the SB_REFRESH_MIN pass (or a `seen` change)
    and is re-asked then by `_fts_reask`; its efts stop is never a reason to re-read the whole basis sooner."""
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
            if mfloat_step(sym, db) == "stored":               # 🧮 the second float, then (if older) the window
                widen_splits(sym, db)
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
    fts = (doc.get("sec") or {}).get("fts") if isinstance((doc.get("sec") or {}).get("fts"), dict) else None
    tail = ""
    if fts is not None:                                        # 🩳 2026-11-26 — the 6-K full-text read
        num = fts.get("number") if isinstance(fts.get("number"), dict) else None
        tail = " | fts %s%s, %d issuance 6-K, number %s" % (
            fts.get("status"), (" (last try %s)" % fts["error"]) if fts.get("error") else "",
            len(fts.get("issuance") or []), ("%d hit" % len(num.get("hits") or [])) if num else "not asked")
    spl = (doc.get("sec") or {}).get("fts_split") if isinstance((doc.get("sec") or {}).get("fts_split"), dict) else None
    if spl is not None:                                        # ✂️ 2026-11-27 — the 6-K split-word read
        tail += " | split words %s%s, %d 6-K" % (spl.get("status"), (" (last try %s)" % spl["error"])
                                                 if spl.get("error") else "", len(spl.get("rows") or []))
    if isinstance(doc.get("mfloat"), dict):                    # 🧮 2026-11-26 — the second dated float
        tail += " | mfloat %s" % doc["mfloat"].get("status")
    return "%s | ref %s | sec %s, %d covers, %d filings | splits %s, %d rows | track %s%s" % (
        sym, st("ref"), st("sec"), len((doc.get("sec") or {}).get("covers") or []),
        len((doc.get("sec") or {}).get("filings") or []), st("splits"),
        len((doc.get("splits") or {}).get("rows") or []), tr.get("origin"), tail)


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
    mfp = sub.add_parser("mfloat")                             # 🧮 prints the second-float answer, writes nothing
    mfp.add_argument("--symbols", required=True)
    a = p.parse_args(argv)
    if a.cmd == "mfloat":
        print(json.dumps(fetch_mfloats(_clean(a.symbols.split(","))), sort_keys=True))
        return 0
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
