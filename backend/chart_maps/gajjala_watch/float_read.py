"""🔢 the float on EVERY 👀 Gajjala's Watch row (2026-11-21, spec watchfloat §3.2, WP be-float).

Ajay 2026-11-21, verbatim: "can you add the current float value also to the tickers on the watch list."

Every Watch row (his names, 🤖 names, 🎯 A+ names) serves the name's float as a plain fact, read in this order:
  1. PASS  — a name carded on today's 🚩 board: the tags block's own chip (`tags.float`, the pass's read), no cache
     read; a SUSPECT chip alone takes ONE cache read for its numbered words (the words the 🚩 card prints);
  2. CACHE — the 7-day `shares_cache` row through the ONE engine (`sepa.volume_movers.shares_status`, cache only, on
     the store's long-lived handle) and `context._yf_read`;
  3. MEMO  — the 🚩 pass's own `gajjala_daily` memo of the board session (ONE projected `_id $in` find): the Yahoo
     refine `float`, else the Massive shares-out answer `float_massive` (dated when Massive was asked). A memo fault
     keeps steps 1-2 and logs ONE line;
  4. nothing on file → the name is not a key (the row serves None — never invented).

Never a network call, never a clock (the payload's `now` is handed in), never a write, never a new Mongo client (the
cache read goes through `st.coll(VM.SHARES_COLL)`, the process-wide handle). A float is not realtime: Yahoo's figure
is kept up to the cache's TTL, Massive's shares out is asked once a session — every numeric chip serves a `title`
saying so with its read time. Display only. UNMEASURED, not a signal.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from chart_maps.gajjala import context as CX
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab
from sepa import volume_movers as VM

log = logging.getLogger("chart_maps.gajjala_watch.float_read")

FLOAT_KEYS = ("shares", "src", "text", "as_of", "suspect", "suspect_text", "title", "read_from")
READ_FROM = ("pass", "cache", "memo")
DAILY_FIELDS = {"symbol": 1, "float": 1, "float_massive": 1}           # never the whole daily doc
FLOAT_TITLE_TEXT = "{text} — not realtime: {source}, read {as_of}"
FLOAT_TITLE_NO_ASOF_TEXT = "{text} — not realtime: {source}"
AS_OF_ET_TEXT = "{clock} ET"
FLOAT_SOURCE_WORDS = {                                                 # keys == the srcs context.py serves
    "float": "Yahoo's float figure, kept up to {days} days",
    "shares_out_yf": "Yahoo's shares outstanding, kept up to {days} days",
    "shares_out_massive": "Massive's shares outstanding, asked once a session",
}
FLOAT_STALE_SOURCE_WORDS = {                                           # [C6] a Yahoo read whose own as_of ≥ the TTL
    "float": "Yahoo's float figure, older than {days} days",
    "shares_out_yf": "Yahoo's shares outstanding, older than {days} days",
}
_CHIP_KEYS = ("shares", "src", "text", "as_of", "suspect")             # tab._float_chip's own keys


def _pl():
    from chart_maps.gajjala_watch import payload as PL                 # lazy — payload imports this module lazily too
    return PL


def _store():
    """The 🚩 five-minute tab's store (tests swap this function — the tags._store pattern)."""
    return ST.default()


def _status_lookup():
    """The ONE cache engine (tests swap this function)."""
    return VM.shares_status


# ── words ────────────────────────────────────────────────────────────────────────────────────────────────────────
def ttl_days() -> int:
    return timedelta(seconds=VM._SHARES_TTL_SEC).days


def as_of_words(as_of, now) -> Optional[str]:
    """A date-only stamp as itself; else "{clock} ET" (payload._clock); unreadable → None."""
    if isinstance(as_of, str) and len(as_of) == len("YYYY-MM-DD"):
        return as_of
    clock = _pl()._clock(as_of, now)
    return AS_OF_ET_TEXT.format(clock=clock) if clock else None


def is_stale(chip, now) -> bool:
    """[C6] A Yahoo read whose own as_of is at least the cache TTL old — the exact complement of shares_status's fresh
    rule. A Massive read is never stale-worded."""
    if not isinstance(chip, dict) or chip.get("src") not in FLOAT_STALE_SOURCE_WORDS:
        return False
    et = _pl()._to_et(chip.get("as_of"))
    return et is not None and (now - et).total_seconds() >= VM._SHARES_TTL_SEC


def title(chip, now) -> Optional[str]:
    if not isinstance(chip, dict):
        return None
    text = tab._text(chip.get("text"))
    src = chip.get("src")
    if not text or chip.get("shares") is None or src not in FLOAT_SOURCE_WORDS:
        return None
    words = FLOAT_STALE_SOURCE_WORDS if is_stale(chip, now) else FLOAT_SOURCE_WORDS
    source = words[src].format(days=ttl_days())
    at = as_of_words(chip.get("as_of"), now)
    if at is None:
        return FLOAT_TITLE_NO_ASOF_TEXT.format(text=text, source=source)
    return FLOAT_TITLE_TEXT.format(text=text, source=source, as_of=at)


def served(chip: dict, read_from: str, now, *, suspect_text: Optional[str] = None) -> dict:
    """The served row block: tab._float_chip's five keys as served (`shares` stays its float), + suspect_text, title,
    read_from. Key set == FLOAT_KEYS."""
    out = {k: chip.get(k) for k in _CHIP_KEYS}
    out["suspect"] = bool(out["suspect"])
    if suspect_text is None and out["suspect"]:
        suspect_text = tab._float_suspect_text({}, chip)
    out["suspect_text"] = suspect_text
    out["title"] = title(out, now)
    out["read_from"] = read_from
    return out


# ── reads ────────────────────────────────────────────────────────────────────────────────────────────────────────
def cache_read(sym: str, now, lookup, coll) -> Optional[dict]:
    """The `shares_cache` row through the engine, cache only, on the given handle. A raise propagates."""
    vals, st = lookup(sym, fetch=False, coll=coll)
    return CX._yf_read(vals, st, now) if st in CX._USABLE else None


def _siso(session) -> str:
    return session.isoformat()[:10] if hasattr(session, "isoformat") else str(session)[:10]


def _find_daily(st, session, names) -> dict:
    """{SYM: memo doc} — ONE projected `_id $in` find on gajjala_daily. RAISES on no handle / a fault."""
    c = st.coll(ST.DAILY) if st is not None else None
    if c is None:
        raise LookupError("no daily handle")
    ids = {ST.key(_siso(session), s): s for s in names}
    out: dict = {}
    for d in c.find({"_id": {"$in": list(ids)}}, DAILY_FIELDS):
        if isinstance(d, dict) and d.get("_id") in ids:
            out[ids[d["_id"]]] = d
    return out


def memo_read(doc, now) -> Optional[dict]:
    """A float read from the 🚩 pass's daily memo: the Yahoo refine `float`, else the Massive answer (dated when
    Massive was asked — never serve time); else None."""
    if not isinstance(doc, dict):
        return None
    fl = doc.get("float")
    if isinstance(fl, dict):
        shares = tab._f(fl.get("shares"))
        if shares is not None and shares > 0:
            return {"shares": fl.get("shares"), "src": fl.get("src"), "as_of": fl.get("as_of"), "suspect": None}
    m = doc.get("float_massive")
    if isinstance(m, dict) and "shares" in m and "failed_at" not in m:
        fr = CX._massive_read(m.get("shares"), now)
        at = m.get("at")
        fr["as_of"] = at if isinstance(at, str) and at else None
        return fr
    return None


def _pass_chip(tags_by, sym) -> Optional[dict]:
    t = (tags_by or {}).get(sym)
    fl = t.get("float") if isinstance(t, dict) else None
    return fl if isinstance(fl, dict) and tab._text(fl.get("text")) else None


def blocks(names, session, now, tags_by=None, *, st, lookup) -> dict:
    """STRICT core: {SYM: float block} for the names with a read on file (a name with none is not a key)."""
    names = list(names or [])
    if not names:
        return {}
    if now is None:
        raise LookupError("no clock handed in")
    now = _pl()._now(now)
    h = st.coll(VM.SHARES_COLL) if st is not None else None
    if h is None:
        raise LookupError("no shares handle")                          # never None into the engine (its own client)
    out: dict = {}
    rest = []
    for s in names:                                                    # 1. PASS
        chip = _pass_chip(tags_by, s)
        if chip is None:
            rest.append(s)
            continue
        words = None
        if chip.get("suspect"):                                        # [C5] ONE cache read for the numbered words
            fr = cache_read(s, now, lookup, h)
            words = tab._float_suspect_text({}, fr if (fr and fr.get("suspect")) else chip)
        out[s] = served(chip, "pass", now, suspect_text=words)
    misses = []
    for s in rest:                                                     # 2. CACHE
        fr = cache_read(s, now, lookup, h)
        if fr is None:
            misses.append(s)
            continue
        out[s] = served(tab._float_chip(fr), "cache", now, suspect_text=tab._float_suspect_text({}, fr))
    if misses:                                                         # 3. MEMO — fail-soft on its own [C10]
        try:
            docs = _find_daily(st, session, misses)
            for s in misses:
                fr = memo_read(docs.get(s), now)
                if fr is not None:
                    out[s] = served(tab._float_chip(fr), "memo", now)
        except Exception as exc:                                       # noqa: BLE001
            log.warning("gajjala_watch: float memo unavailable: %s", type(exc).__name__)
    return out


def section(names, session, now, tags_by=None) -> dict:
    """Fail-soft `blocks`: any fault → {} (every row serves None; the board answers) and ONE log line."""
    try:
        return blocks(names, session, now, tags_by, st=_store(), lookup=_status_lookup())
    except Exception as exc:                                           # noqa: BLE001
        log.warning("gajjala_watch: float unavailable: %s", type(exc).__name__)
        return {}
