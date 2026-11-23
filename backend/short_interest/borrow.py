from __future__ import annotations

__doc__ = """💸 BORROW — Interactive Brokers' public shortable-shares file (2026-11-22).

THE ASK (Ajay 2026-11-22, verbatim)
  "What is short borrow fee? Is that a real time value I saw AKAN has a high
   short borrow fee" — offered a borrow fee + shares-available line next to
  the 🔒, he answered: "yes i need that please".

What this module is: the ONE engine behind the 💸 line. It reads IBKR's
anonymous FTP file (`ftp2.interactivebrokers.com`, user `shortstock`, empty
password, `usa.txt` + `usa.txt.md5`), keeps one compressed snapshot per
changed file (NEVER purged — `fetched_at` is the point-in-time record), the
company names in one content-addressed doc, and one state doc. It serves ONE
batched read, `GET /short-interest/borrow?symbols=A,B,C`. Every word the front
end prints is built here; it types none.

DISPLAY ONLY. Nothing here gates, sorts, sizes, pushes or enters a lane.
UNMEASURED. IBKR calls its rates "indicative": one broker's file, not the fee
another broker charges.

The read never makes an outside call: a due file is fetched by ONE
single-flight daemon worker kicked from the read (the `reg_sho.kick_refresh`
shape), at most once per BR_REFRESH_MIN.

TRAPS (measured 2026-11-22 Sunday night, see docs/gajjala/borrow_fee_ibkr_2026_11_22.md):
  * `usa.txt.md5` is the md5 of the file with CRLF → LF, never of the bytes as
    downloaded. It is read BEFORE and AFTER the file inside the one session.
  * The parser splits the BYTES on b"\\n" — never Python's str line splitter,
    which also splits on \\x0b \\x0c \\x1c-\\x1e and would reject a whole good
    file over one odd byte in a NAME cell.
  * AVAILABLE 0 is a LISTED row with 0 shares; a name with no row is "absent",
    never zero. `>10000000` is a lower bound.
  * NAME is HTML-escaped (`&amp;`) and up to 60 characters.
  * The `#BOF` stamp names no zone: printed verbatim, no arithmetic on it.

Python 3.9-safe (the host venv): no `X | None` at runtime, no `match`.
"""

import hashlib
import html
import logging
import math
import re
import threading
import time
import zlib
from datetime import datetime
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from short_interest import client as SIC
from short_interest import read as SR
from short_interest import reg_sho as RS

log = logging.getLogger("short_interest.borrow")

GLYPH = "💸"
WORD = "Borrow"
SOURCE_NAME = "Interactive Brokers"
SOURCE_SHORT = "IBKR"
KIND = "ibkr_borrow"                         # payload discriminator
BR_COLL = "ibkr_borrow"                      # Mongo collection
API_PATH = "/short-interest/borrow"

BR_FTP_HOST = "ftp2.interactivebrokers.com"   # the ONLY host — no fallback list
BR_FTP_PORT = 21
BR_FTP_USER = "shortstock"
BR_FTP_PASSWORD = ""
BR_FILE = "usa.txt"
BR_MD5_FILE = "usa.txt.md5"
BR_FETCH_NAMES = (BR_MD5_FILE, BR_FILE, BR_MD5_FILE)   # md5 BEFORE and AFTER the file, one session
BR_HEADER = "#SYM|CUR|NAME|CON|ISIN|REBATERATE|FEERATE|AVAILABLE|FIGI|"
BR_CURRENCY = "USD"

# engineering constants — MINE, none is a trading threshold (HIS CALL #8)
BR_REFRESH_MIN = 15          # at most one fetch per this many minutes
BR_ERROR_RETRY_MIN = 5       # the first retries after an error
BR_ERROR_STRIKES = 2         # errors in a row before the wait goes back to BR_REFRESH_MIN
BR_KICK_MIN_SEC = 60         # in-process floor between two worker starts
BR_FTP_TIMEOUT_SEC = 25
BR_FETCH_BUDGET_SEC = 60
BR_STALE_MIN = 60            # the held file reads stale past this
BR_RETRY_AFTER_SEC = 20      # served to the FE while a refresh runs
BR_MAX_BYTES = 8_000_000
BR_MAX_ROWS = 60_000
BR_MIN_ROWS = 5_000
BR_MAX_SKIPPED_ROWS = 200
BR_NAME_MAX = 60             # IBKR's NAME cell, measured max 60
BR_FEE_WHOLE_FROM = 10.0     # display format break only
BR_DAYS_PER_YEAR = 365       # plain arithmetic, printed in the words (HIS CALL #7)
BR_FORMS = ("label", "chip", "short")
BR_ABSENT_FORMS = ("label",)   # HIS CALL #1 — the forms an ABSENT name is served in
BR_FORM_SURFACE = {"label": "🎾 cards", "chip": "the other Gajjala cards", "short": "the 📋 table"}
BR_SURFACES_TEXT = "Gajjala cards and the 📋 All strategies table"     # no Watch (HIS CALL #2)
MAP_MAX_SYMBOLS = SR.MAP_MAX_SYMBOLS
_ftp = None                  # the ONE outside-call seam; None → _ftp_fetch
_DEFAULT = object()          # "resolve the house Mongo handle"; None means ONLY "Mongo is down"
_ET = ZoneInfo("America/New_York")

# ───────────────────────────────────────────── words (served; the FE types none)
CHIP_TEXT = "%s %s %s · %s avail"                    # 💸 Borrow 196% · 100K avail
CHIP_NO_FEE_TEXT = "%s %s fee n/a · %s avail"        # 💸 Borrow fee n/a · 90 avail
SHORT_TEXT = "%s %s"                                 # 💸 196%          (no fee → short is None)
LABEL_TEXT = "%s %s %s a year · %s shares available · %s file %s"
LABEL_NO_FEE_TEXT = "%s %s fee n/a · %s shares available · %s file %s"
ABSENT_LABEL = "%s not in %s's borrow file"          # 💸 not in IBKR's borrow file
ABSENT_CHIP = "%s not in %s's file"                  # 💸 not in IBKR's file     ("chip" in BR_ABSENT_FORMS)
ABSENT_SHORT = "%s not in file"                      # 💸 not in file            ("short" in BR_ABSENT_FORMS)
UNREAD_LABEL = "%s %s's borrow file could not be read"
STALE_TEXT = " · file %s old"                        # appended to chip, short, label (listed AND absent)
NAME_TEXT = " (%s's row: %s)"                        # "" with no name
TITLE_TEXT = "%s borrow fee for %s%s: %s a year%s, %s shares available to borrow, %s file stamped %s, read %s. %s %s"
PER_DAY_TEXT = " (≈ %s a day, the yearly rate ÷ %d)"  # omitted when it would print 0.00%
TITLE_NO_FEE_TEXT = ("%s lists %s%s with %s shares available to borrow and no fee rate (the file says NA), "
                     "%s file stamped %s, read %s. %s %s")
ABSENT_TITLE = ("%s is not in %s's borrow file stamped %s (read %s, %s US names). Not in the file is not a number — "
                "no count is shown. %s %s")
UNREAD_TITLE = "%s's borrow file could not be read — no fee and no share count is shown for %s. %s %s"
STALE_TITLE = " This is the file first read %s (%s old) — a newer one could not be read or has not been published."
HONESTY_NOTE = "One broker's indicative rate — your broker sets its own fee when you borrow."
ONE_BROKER_NOTE = "One broker's file — your own broker keeps its own list."
FILE_TEXT = "%s borrow file stamped %s · read %s · %s US names"
RULES_ABSENT_TEXT = "A name that is not in the file reads '%s' on %s%s — never a zero."
RULES_ABSENT_NONE = "A name that is not in the file shows nothing — never a zero."
# the closing sentence is RS.NOT_A_SIGNAL, by name

_BOF = re.compile(r"^#BOF\|(\d{4}\.\d{2}\.\d{2})\|(\d{2}:\d{2}:\d{2})$")
_EOF = re.compile(r"^#EOF\|(\d+)$")
_RATE = re.compile(r"^-?\d+(\.\d+)?$")
_AVAIL = re.compile(r"^\d+$")
_AVAIL_FLOOR = re.compile(r"^>(\d+)$")
_MD5 = re.compile(r"^[0-9a-f]{32}$")
_PLAIN = re.compile(r"^[A-Z0-9]{1,9}$")
_NOT_PRINTABLE = re.compile(r"[^\x20-\x7e]|\|")
_WS_RUN = re.compile(r"\s+")
_TRIM_ZERO = re.compile(r"\.0(?=[KMB]$)")


# ───────────────────────────────────────────── seams
def _mono() -> float:
    return time.monotonic()


def _resolve_ftp(ftp):
    if ftp is not None:
        return ftp
    if _ftp is not None:
        return _ftp
    return _ftp_fetch


# ───────────────────────────────────────────── parse
def clean_name(cell) -> str:
    """IBKR's NAME cell → printable text: unescaped, controls and `|` → space, one space per run, ≤ BR_NAME_MAX."""
    s = html.unescape(str(cell or ""))
    s = _NOT_PRINTABLE.sub(" ", s)
    return _WS_RUN.sub(" ", s).strip()[:BR_NAME_MAX].strip()


def _rate(cell: str) -> Tuple[bool, Optional[float]]:
    """(ok, value) — `NA` → (True, None); a malformed cell → (False, None)."""
    if cell == "NA":
        return True, None
    if not _RATE.match(cell):
        return False, None
    f = float(cell)
    if not math.isfinite(f):
        return False, None
    return True, f


def parse_file(body: bytes) -> dict:
    """IBKR's usa.txt → rows keyed by RS.norm_symbol — raises RS.Malformed(reason)."""
    if not isinstance(body, (bytes, bytearray)):
        raise RS.Malformed("not bytes")
    if len(body) > BR_MAX_BYTES:
        raise RS.Malformed("oversize")
    lines = []
    for raw in bytes(body).split(b"\n"):                       # BYTES on \n — never the str line splitter
        ln = raw.rstrip(b"\r").decode("ascii", "replace").strip()
        if ln:
            lines.append(ln)
    if not lines:
        raise RS.Malformed("bof")
    m = _BOF.match(lines[0])
    if not m:
        raise RS.Malformed("bof")
    stamp = "%s %s" % (m.group(1), m.group(2))
    want_cells = [c.strip().upper() for c in BR_HEADER.split("|")]
    if len(lines) < 2 or [c.strip().upper() for c in lines[1].split("|")] != want_cells:
        raise RS.Malformed("header")
    e = _EOF.match(lines[-1]) if len(lines) >= 3 else None
    if not e:
        raise RS.Malformed("eof")
    eof_n = int(e.group(1))
    data = lines[2:-1]
    if len(data) != eof_n:
        raise RS.Malformed("count")
    if len(data) > BR_MAX_ROWS:
        raise RS.Malformed("too many rows")

    ncells = len(want_cells)
    rows: dict = {}
    names: dict = {}
    skipped = non_usd = na = floor = zero = dups = kept = 0
    for row in data:
        cells = [c.strip() for c in row.split("|")]
        if len(cells) != ncells:
            skipped += 1
            continue
        sym, cur, name, _con, _isin, rebate_c, fee_c, avail_c = cells[:8]
        if cur != BR_CURRENCY:
            non_usd += 1
            continue
        if not RS._SYMBOL_CELL.match(sym):
            skipped += 1
            continue
        ok_fee, fee = _rate(fee_c)
        ok_reb, rebate = _rate(rebate_c)
        if not ok_fee or not ok_reb or (fee is not None and fee < 0):
            skipped += 1
            continue
        a = _AVAIL.match(avail_c)
        if a:
            avail, is_floor = int(avail_c), False
        else:
            f = _AVAIL_FLOOR.match(avail_c)
            if not f:
                skipped += 1
                continue
            avail, is_floor = int(f.group(1)), True
        kept += 1
        if fee is None:
            na += 1
        if is_floor:
            floor += 1
        elif avail == 0:
            zero += 1
        key = RS.norm_symbol(sym)
        if key in rows:
            rows[key] = None                                   # ambiguous → "unknown"
            names.pop(key, None)
            dups += 1
            continue
        rows[key] = (fee, rebate, avail, is_floor)
        nm = clean_name(name)
        if nm:
            names[key] = nm
    if skipped > BR_MAX_SKIPPED_ROWS:
        raise RS.Malformed("too many unreadable rows")
    if kept < BR_MIN_ROWS:
        raise RS.Malformed("too few rows")
    return {"stamp": stamp, "eof_n": eof_n, "rows": rows, "names": names, "n": len(rows), "skipped": skipped,
            "non_usd": non_usd, "na": na, "floor": floor, "zero": zero, "dups": dups}


def md5_ok(body: bytes, texts) -> Optional[bool]:
    """True = a valid md5 answer equals the md5 of the LF form; None = no valid md5 answer was read."""
    valid = []
    for t in list(texts or ()):
        if isinstance(t, (bytes, bytearray)):
            t = bytes(t).decode("ascii", "replace")
        if not isinstance(t, str):
            continue
        t = t.strip().lower()
        if _MD5.match(t):
            valid.append(t)
    if not valid:
        return None
    want = hashlib.md5(bytes(body).replace(b"\r\n", b"\n")).hexdigest()
    return want in valid


# ───────────────────────────────────────────── storage (canonical text → sha1 + zlib)
def _num4(v) -> str:
    return "NA" if v is None else "%.4f" % v


def encode_rows(rows) -> Tuple[bytes, str]:
    """SYM|FEE|REBATE|AVAIL per key, sorted; a dup → SYM|DUP||. NAME / CON / ISIN / FIGI never stored here."""
    out = []
    for k in sorted(rows):
        r = rows[k]
        if r is None:
            out.append("%s|DUP||" % k)
            continue
        fee, rebate, avail, is_floor = r
        out.append("%s|%s|%s|%s%d" % (k, _num4(fee), _num4(rebate), ">" if is_floor else "", int(avail)))
    text = "\n".join(out).encode("utf-8")
    return zlib.compress(text, 6), hashlib.sha1(text).hexdigest()


def _un4(cell: str) -> Optional[float]:
    return None if cell == "NA" else float(cell)


def decode_rows(blob) -> dict:
    text = zlib.decompress(bytes(blob)).decode("utf-8")
    rows: dict = {}
    for ln in text.split("\n"):
        if not ln:
            continue
        k, fee, rebate, avail = ln.split("|")
        if fee == "DUP":
            rows[k] = None
            continue
        is_floor = avail.startswith(">")
        rows[k] = (_un4(fee), _un4(rebate), int(avail[1:] if is_floor else avail), is_floor)
    return rows


def encode_names(names) -> Tuple[bytes, str]:
    """SYM|NAME per key, sorted. CON / ISIN / FIGI are never stored anywhere."""
    text = "\n".join("%s|%s" % (k, names[k]) for k in sorted(names)).encode("utf-8")
    return zlib.compress(text, 6), hashlib.sha1(text).hexdigest()


def decode_names(blob) -> dict:
    text = zlib.decompress(bytes(blob)).decode("utf-8")
    out: dict = {}
    for ln in text.split("\n"):
        if not ln:
            continue
        k, nm = ln.split("|", 1)
        out[k] = nm
    return out


# ───────────────────────────────────────────── fetch (the real fetcher + the never-raising wrapper)
class _Oversize(Exception):
    """A RETR past max_bytes."""


def _ftp_fetch(*, host, port, user, password, names, timeout, max_bytes, budget_sec) -> list:
    """ONE FTP session: RETR each entry of `names` in order. [bytes | None] aligned with `names`."""
    import ftplib                                              # lazy: the read never needs it
    t0 = _mono()
    out = []
    ftp = ftplib.FTP()
    try:
        ftp.connect(host, port, timeout=timeout)
        ftp.login(user, password)
        for name in names:
            buf = bytearray()

            def cb(chunk, buf=buf):
                buf.extend(chunk)
                if len(buf) > max_bytes:
                    raise _Oversize(name)
                if _mono() - t0 > budget_sec:
                    raise TimeoutError("fetch budget")
            try:
                ftp.retrbinary("RETR " + name, cb)
            except ftplib.error_perm:
                if name == BR_MD5_FILE:
                    out.append(None)
                    continue
                raise
            out.append(bytes(buf))
    finally:
        try:
            ftp.close()
        except Exception:                                      # noqa: BLE001
            pass
    return out


def fetch(ftp=None) -> dict:
    """Never raises. ONE seam call: entries 0 and 2 = the md5 answers, entry 1 = the file."""
    try:
        call = _resolve_ftp(ftp)
        got = call(host=BR_FTP_HOST, port=BR_FTP_PORT, user=BR_FTP_USER, password=BR_FTP_PASSWORD,
                   names=BR_FETCH_NAMES, timeout=BR_FTP_TIMEOUT_SEC, max_bytes=BR_MAX_BYTES,
                   budget_sec=BR_FETCH_BUDGET_SEC)
    except Exception as exc:                                   # noqa: BLE001
        name = type(exc).__name__
        log.warning("borrow: fetch failed: %s", name)
        return {"result": "error", "error": "timeout" if "timeout" in name.lower() else "exception", "detail": name}
    try:
        got = list(got or [])
        body = got[1] if len(got) > 1 else None
        if not body:
            return {"result": "error", "error": "empty", "detail": None}
        texts = [got[0] if len(got) > 0 else None, got[2] if len(got) > 2 else None]
        ok = md5_ok(body, texts)
        if ok is False:
            log.warning("borrow: md5 mismatch")
            return {"result": "error", "error": "md5", "detail": None}
        parsed = parse_file(body)
        return {"result": "found", "parsed": parsed, "md5_ok": ok}
    except RS.Malformed as exc:
        log.warning("borrow: malformed file: %s", exc)
        return {"result": "error", "error": "malformed", "detail": type(exc).__name__}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("borrow: read failed: %s", type(exc).__name__)
        return {"result": "error", "error": "exception", "detail": type(exc).__name__}


# ───────────────────────────────────────────── refresh
def is_due(state, now_et) -> bool:
    if not state:
        return True
    now_et = RS._to_et(now_et)
    if state.get("result") == "error" and int(state.get("errors") or 0) < BR_ERROR_STRIKES:
        wait = BR_ERROR_RETRY_MIN
    else:
        wait = BR_REFRESH_MIN
    age = RS._age_min(state.get("attempt_at"), now_et)
    return age is None or age >= wait


def _snap_loads(coll, sid) -> bool:
    if not sid:
        return False
    try:
        doc = coll.find_one({"_id": sid})
        if not doc:
            return False
        decode_rows(doc["blob"])
        return True
    except Exception:                                          # noqa: BLE001
        return False


def refresh(coll, now_et=None, *, ftp=None) -> Optional[dict]:
    """One refresh round. Returns the state doc it wrote (None when abandoned before the seam)."""
    now = RS._to_et(now_et)
    iso = RS._utc_iso(now)
    try:
        prev = coll.find_one({"_id": "state"})
    except Exception as exc:                                   # noqa: BLE001
        log.warning("borrow: state read failed: %s", type(exc).__name__)
        return None
    pre = dict(prev or {})
    pre.update({"_id": "state", "kind": "state", "attempt_at": iso, "result": "running", "error": None})
    try:
        coll.replace_one({"_id": "state"}, dict(pre), upsert=True)     # BEFORE the outside call, held keys CARRIED
    except Exception as exc:                                   # noqa: BLE001
        log.warning("borrow: state pre-write failed, round abandoned: %s", type(exc).__name__)
        return None
    try:
        coll.create_index([("kind", 1), ("fetched_at", -1)])
    except Exception:                                          # noqa: BLE001
        pass

    state = dict(pre)
    result, err = "error", "exception"
    upd: dict = {}
    try:
        got = fetch(ftp)
        if got["result"] != "found":
            result, err = "error", got.get("error") or "exception"
        else:
            parsed = got["parsed"]
            blob, digest = encode_rows(parsed["rows"])
            nblob, ndigest = encode_names(parsed["names"])
            names_id = "names|" + ndigest[:16]
            if names_id != pre.get("names_id"):
                try:
                    coll.replace_one({"_id": names_id}, {
                        "_id": names_id, "kind": "names", "digest": ndigest, "n": len(parsed["names"]),
                        "first_seen_at": iso, "blob": nblob}, upsert=True)
                except Exception as exc:                       # noqa: BLE001
                    log.warning("borrow: names write failed: %s", type(exc).__name__)
                    names_id = pre.get("names_id")
            result, err = "unchanged", None
            if digest != pre.get("good_digest") or not _snap_loads(coll, pre.get("good_id")):
                sid = "snap|%s|%s" % (iso, digest[:12])
                try:
                    coll.replace_one({"_id": sid}, {
                        "_id": sid, "kind": "snap", "fetched_at": iso, "stamp": parsed["stamp"],
                        "eof_n": parsed["eof_n"], "n": parsed["n"], "skipped": parsed["skipped"],
                        "non_usd": parsed["non_usd"], "na": parsed["na"], "floor": parsed["floor"],
                        "zero": parsed["zero"], "dups": parsed["dups"], "digest": digest,
                        "md5_ok": got.get("md5_ok"), "names_id": names_id, "blob": blob}, upsert=True)
                    upd.update({"good_id": sid, "good_digest": digest, "n": parsed["n"],
                                "skipped": parsed["skipped"]})
                    result = "found"
                except Exception as exc:                       # noqa: BLE001
                    log.warning("borrow: snapshot write failed: %s", type(exc).__name__)
                    result, err = "error", "store"
            if result != "error":
                upd.update({"checked_at": iso, "errors": 0, "names_id": names_id})
                if parsed["stamp"] != pre.get("stamp"):
                    upd.update({"stamp": parsed["stamp"], "stamp_seen_at": iso})
    except Exception as exc:                                   # noqa: BLE001
        log.warning("borrow: refresh failed: %s", type(exc).__name__)
        result, err, upd = "error", "exception", {}
    finally:
        if result == "error":
            state["errors"] = int(pre.get("errors") or 0) + 1
        else:
            state.update(upd)
        state["result"] = result
        state["error"] = err if result == "error" else None
        try:
            coll.replace_one({"_id": "state"}, dict(state), upsert=True)
        except Exception as exc:                               # noqa: BLE001
            log.warning("borrow: final state write failed: %s", type(exc).__name__)
    return state


# One worker at a time (the reg_sho.kick_refresh shape) + a floor between starts.
_bg_lock = threading.Lock()
_bg = {"running": False, "last_start": None, "thread": None}


def _worker_running() -> bool:
    with _bg_lock:
        return bool(_bg["running"])


def kick_refresh(coll, now_et=None, *, ftp=None) -> bool:
    """True = a worker was started."""
    with _bg_lock:
        if _bg["running"]:
            return False
        last = _bg["last_start"]
        if last is not None and _mono() - last < BR_KICK_MIN_SEC:
            return False
        _bg["running"] = True
        _bg["last_start"] = _mono()

    def run():
        try:
            refresh(coll, now_et, ftp=ftp)
        except Exception as exc:                               # pragma: no cover
            log.warning("borrow: worker failed: %s", type(exc).__name__)
        finally:
            with _bg_lock:
                _bg["running"] = False

    try:
        t = threading.Thread(target=run, daemon=True, name="ibkr-borrow-refresh")
        t.start()
    except Exception as exc:                                   # noqa: BLE001
        with _bg_lock:
            _bg["running"] = False
            _bg["last_start"] = last
        log.warning("borrow: worker could not start: %s", type(exc).__name__)
        return False
    _bg["thread"] = t
    return True


# ───────────────────────────────────────────── symbols
def clean_symbols(symbols) -> list:
    """THE one cleaner: strings only, upper, blanks / unreadable dropped, de-duplicated, first MAP_MAX_SYMBOLS."""
    out: list = []
    try:
        if not isinstance(symbols, (list, tuple)):
            return []
        for s in symbols:
            if not isinstance(s, str):
                continue
            s = s.strip().upper()
            if not s or not RS._SYMBOL_CELL.match(s) or s in out:
                continue
            out.append(s)
            if len(out) >= MAP_MAX_SYMBOLS:
                break
    except Exception:                                          # noqa: BLE001
        return out[:MAP_MAX_SYMBOLS]
    return out


def lookup(sym, rows) -> Tuple[str, Optional[tuple]]:
    """("listed", row) | ("absent", None) | ("unknown", None) — exact match only."""
    norm = RS.norm_symbol(sym)
    if norm and norm in rows:
        row = rows[norm]
        return ("listed", row) if row is not None else ("unknown", None)
    if _PLAIN.match(norm):
        return "absent", None
    return "unknown", None


# ───────────────────────────────────────────── formatters
def _fee_words(f: float) -> str:
    if f < BR_FEE_WHOLE_FROM:
        s = ("%.2f" % f).rstrip("0").rstrip(".")
        if float(s) < BR_FEE_WHOLE_FROM:
            return s + "%"
    return "{:,.0f}%".format(f)


def _per_day(f: float) -> str:
    d = "%.2f" % (f / BR_DAYS_PER_YEAR)
    return "" if d == "0.00" else PER_DAY_TEXT % (d + "%", BR_DAYS_PER_YEAR)


def _avail_words(n: int, is_floor: bool) -> str:
    return (">" if is_floor else "") + _TRIM_ZERO.sub("", SR._human_shares(n))


def _avail_long(n: int, is_floor: bool) -> str:
    return ("more than " if is_floor else "") + "{:,}".format(int(n))


def _age_words(minutes) -> str:
    m = int(minutes)
    if m < 60:
        return "%d min" % m
    if m < 2880:
        return "%dh" % (m // 60)
    return "%dd" % (m // 1440)


def _read_words(iso) -> str:
    d = RS._parse_iso(iso)
    if d is None:
        return str(iso or "")
    et = d.astimezone(_ET)
    return SR._md(et.date().isoformat()) + et.strftime(" %H:%M ET")


def _stale_tails(file: dict, stale_min) -> Tuple[str, str]:
    if stale_min is None:
        return "", ""
    age = _age_words(stale_min)
    return STALE_TEXT % age, STALE_TITLE % (_read_words(file.get("first_read_at")), age)


def _tail(s: Optional[str], tail: str) -> Optional[str]:
    return None if s is None else s + tail


def _absent_forms() -> tuple:
    try:
        chosen = tuple(BR_ABSENT_FORMS or ())
    except TypeError:
        chosen = ()
    return tuple(f for f in BR_FORMS if f in chosen)


# ───────────────────────────────────────────── the three word builders (pure)
def listed_block(sym, row, name, file, stale_min) -> dict:
    fee, rebate, avail, is_floor = row
    tail, ttail = _stale_tails(file, stale_min)
    stamp = file.get("stamp")
    read = _read_words(file.get("read_at"))
    nm = name or None
    nclause = NAME_TEXT % (SOURCE_SHORT, nm) if nm else ""
    aw = _avail_words(avail, is_floor)
    if fee is None:
        chip = CHIP_NO_FEE_TEXT % (GLYPH, WORD, aw)
        short = None
        label = LABEL_NO_FEE_TEXT % (GLYPH, WORD, aw, SOURCE_SHORT, stamp)
        title = TITLE_NO_FEE_TEXT % (SOURCE_NAME, sym, nclause, _avail_long(avail, is_floor), SOURCE_SHORT, stamp,
                                     read, HONESTY_NOTE, RS.NOT_A_SIGNAL)
    else:
        fw = _fee_words(fee)
        chip = CHIP_TEXT % (GLYPH, WORD, fw, aw)
        short = SHORT_TEXT % (GLYPH, fw)
        label = LABEL_TEXT % (GLYPH, WORD, fw, aw, SOURCE_SHORT, stamp)
        title = TITLE_TEXT % (SOURCE_NAME, sym, nclause, "{:,.2f}%".format(fee), _per_day(fee),
                              _avail_long(avail, is_floor), SOURCE_SHORT, stamp, read, HONESTY_NOTE, RS.NOT_A_SIGNAL)
    return {"state": "listed", "symbol": sym, "name": nm,
            "chip": _tail(chip, tail), "short": _tail(short, tail), "label": _tail(label, tail),
            "title": title + ttail, "stale": stale_min is not None,
            "fee_pct": fee, "rebate_pct": rebate, "available": int(avail), "available_floor": bool(is_floor)}


def absent_block(sym, file, stale_min) -> Optional[dict]:
    forms = _absent_forms()
    if not forms:
        return None
    tail, ttail = _stale_tails(file, stale_min)
    title = ABSENT_TITLE % (sym, SOURCE_SHORT, file.get("stamp"), _read_words(file.get("read_at")),
                            "{:,}".format(int(file.get("names") or 0)), ONE_BROKER_NOTE, RS.NOT_A_SIGNAL)
    return {"state": "absent", "symbol": sym, "name": None,
            "chip": (ABSENT_CHIP % (GLYPH, SOURCE_SHORT)) + tail if "chip" in forms else None,
            "short": (ABSENT_SHORT % GLYPH) + tail if "short" in forms else None,
            "label": (ABSENT_LABEL % (GLYPH, SOURCE_SHORT)) + tail if "label" in forms else None,
            "title": title + ttail, "stale": stale_min is not None,
            "fee_pct": None, "rebate_pct": None, "available": None, "available_floor": False}


def unread_block(sym) -> dict:
    return {"state": "unread", "symbol": sym, "name": None, "chip": None, "short": None,
            "label": UNREAD_LABEL % (GLYPH, SOURCE_SHORT),
            "title": UNREAD_TITLE % (SOURCE_SHORT, sym, ONE_BROKER_NOTE, RS.NOT_A_SIGNAL), "stale": False,
            "fee_pct": None, "rebate_pct": None, "available": None, "available_floor": False}


# ───────────────────────────────────────────── the served read
_dec_lock = threading.Lock()
_decoded = {"rows_id": None, "rows": None, "names_id": None, "names": None}


def _reset_cache() -> None:
    with _dec_lock:
        _decoded.update({"rows_id": None, "rows": None, "names_id": None, "names": None})


def _held_rows(coll, sid) -> Optional[dict]:
    if not sid:
        return None
    with _dec_lock:
        if _decoded["rows_id"] == sid and _decoded["rows"] is not None:
            return _decoded["rows"]
    doc = coll.find_one({"_id": sid})
    if not doc:
        return None
    try:
        rows = decode_rows(doc["blob"])
    except Exception as exc:                                   # noqa: BLE001
        log.warning("borrow: held snapshot does not unpack: %s", type(exc).__name__)
        return None
    with _dec_lock:
        _decoded["rows_id"], _decoded["rows"] = sid, rows
    return rows


def _held_names(coll, nid) -> Optional[dict]:
    """The names doc, or None (no name clause). A miss is never cached — the next read looks again."""
    if not nid:
        return None
    with _dec_lock:
        if _decoded["names_id"] == nid and _decoded["names"] is not None:
            return _decoded["names"]
    try:
        doc = coll.find_one({"_id": nid})
        if not doc:
            return None
        names = decode_names(doc["blob"])
    except Exception as exc:                                   # noqa: BLE001
        log.warning("borrow: names doc unread: %s", type(exc).__name__)
        return None
    with _dec_lock:
        _decoded["names_id"], _decoded["names"] = nid, names
    return names


def _envelope(status: str, items: dict, syms: list, file, keep_sec, refreshing: bool, retry_after_sec) -> dict:
    return {"kind": KIND, "status": status, "stale": status == "stale", "items": items,
            "asked": len(syms), "n": len(items), "max_symbols": MAP_MAX_SYMBOLS, "file": file,
            "note": HONESTY_NOTE, "refreshing": bool(refreshing), "retry_after_sec": retry_after_sec,
            "keep_sec": keep_sec}


def _unread_retry(refreshing: bool) -> int:
    return BR_RETRY_AFTER_SEC if refreshing else BR_ERROR_RETRY_MIN * 60


def payload(symbols, db=_DEFAULT, now=None, *, kick: bool = True, ftp=None) -> dict:
    """THE served read — Mongo reads only, never an outside call."""
    now_et = RS._to_et(now)
    syms = clean_symbols(symbols)
    if db is _DEFAULT:
        db = SIC._get_db()
    coll = db[BR_COLL] if db is not None else None
    if coll is None:                                           # Mongo down = the fault shape
        return _envelope("failed", {s: unread_block(s) for s in syms}, syms, None, None, False, _unread_retry(False))

    state = coll.find_one({"_id": "state"})
    started = False
    if kick and is_due(state, now_et):
        started = kick_refresh(coll, now_et if now is not None else None, ftp=ftp)
    refreshing = bool(started or _worker_running())

    st = state or {}
    seen_at = RS._parse_iso(st.get("stamp_seen_at"))
    rows = _held_rows(coll, st.get("good_id")) if seen_at is not None else None
    if rows is None:                                           # nothing held — never reads state.result while held
        if st.get("result") == "error":
            return _envelope("failed", {s: unread_block(s) for s in syms}, syms, None, None, refreshing,
                             _unread_retry(refreshing))
        return _envelope("pending", {}, syms, None, None, refreshing, _unread_retry(refreshing))

    names = _held_names(coll, st.get("names_id")) or {}
    age_sec = max(0.0, (now_et - seen_at).total_seconds())
    limit = BR_STALE_MIN * 60
    if age_sec <= limit:
        status, stale_min, keep_sec = "ok", None, max(1, limit - int(age_sec))
    else:
        status, stale_min, keep_sec = "stale", int(age_sec // 60), limit
    n_names = int(st.get("n") or 0)
    read_at = st.get("checked_at") or st.get("stamp_seen_at")
    file = {"stamp": st.get("stamp"), "first_read_at": st.get("stamp_seen_at"), "read_at": read_at,
            "age_min": int(age_sec // 60), "names": n_names, "skipped": int(st.get("skipped") or 0),
            "text": FILE_TEXT % (SOURCE_NAME, st.get("stamp"), _read_words(read_at), "{:,}".format(n_names))}
    items: dict = {}
    for sym in syms:
        state_word, row = lookup(sym, rows)
        if state_word == "listed":
            items[sym] = listed_block(sym, row, names.get(RS.norm_symbol(sym)), file, stale_min)
        elif state_word == "absent":
            blk = absent_block(sym, file, stale_min)
            if blk is not None:
                items[sym] = blk
    return _envelope(status, items, syms, file, keep_sec, refreshing,
                     BR_RETRY_AFTER_SEC if refreshing else None)


def fault_payload(symbols=None) -> dict:
    """The served body when the read itself raised — the SAME shape as "Mongo down". Reads nothing."""
    try:
        syms = clean_symbols(symbols)
        items = {s: unread_block(s) for s in syms}
    except Exception:                                          # noqa: BLE001
        syms, items = [], {}
    return _envelope("failed", items, syms, None, None, False, _unread_retry(False))


def rules_pick() -> str:
    """The ℹ️ sentence folded into the 🩳 short-volume pick — numbers and surfaces from the constants."""
    forms = _absent_forms()
    if not forms:
        absent = RULES_ABSENT_NONE
    else:
        word = {"label": ABSENT_LABEL % (GLYPH, SOURCE_SHORT), "chip": ABSENT_CHIP % (GLYPH, SOURCE_SHORT),
                "short": ABSENT_SHORT % GLYPH}[forms[0]]
        absent = RULES_ABSENT_TEXT % (word, RS._and_list([BR_FORM_SURFACE[f] for f in forms]),
                                      " only" if len(forms) == 1 else "")
    return ("%s %s = %s' public shortable-shares file: the yearly borrow fee rate and the shares it shows available "
            "to lend, per US ticker. Re-read at most once every %d minutes while a Gajjala page is open; the hover "
            "carries %s's file stamp, the time it was read and the company name on %s's row, and the chip says how "
            "old the file is once it is more than %d minutes old. %s %s Tags %s only; it gates, sorts and pushes "
            "nothing. UNMEASURED."
            % (GLYPH, WORD, SOURCE_NAME, BR_REFRESH_MIN, SOURCE_SHORT, SOURCE_SHORT, BR_STALE_MIN, absent,
               HONESTY_NOTE, BR_SURFACES_TEXT))
