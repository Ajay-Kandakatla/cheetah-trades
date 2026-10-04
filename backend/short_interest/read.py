"""🩳 SHORT INTEREST — the ONE served read (2026-10-03).

THE ASK (Ajay 2026-10-03, verbatim)
  "I would like to see a new field for sotcks about short interest I heard EOSE
   has about 40% short interest is Short Interest always accurate about a stocks
   down fall?
   can you add this field to all our chart maps scan. also the individual
   tickers please"

What this module is: every word, number and freshness label the app serves for
short interest is built HERE, from the `short_interest_latest` cache, and the
front end prints `chip` / `title` / `rows` verbatim. It never fetches: a name
with no cached doc is ABSENT from the map (never a zero), and a remembered miss
reads "not read".

DISPLAY ONLY. Nothing here gates, sorts, sizes, pushes or enters a lane — and
no served word says short interest forecasts a fall. UNMEASURED on this app's
universe.

FRESHNESS — FINRA's calendar, not a cache age:
  * settlements: the 15th (or the business day before) and the last business
    day of each month;
  * publication: the FINRA_PUBLICATION_BDAYS-th NYSE business day after the
    settlement (reproduces the six published 2026 pairs: 08-14→08-25,
    08-31→09-10, 09-15→09-24, 09-30→10-09, 10-15→10-26, 10-30→11-10);
  * STALE once the NEXT settlement's publication day plus
    SI_INGEST_GRACE_BDAYS business days has passed and the cache still holds
    the older one. A label, never a gate.

No top-level import of `sepa` or `market_hours`: the holiday list is loaded
lazily (market_hours.reminder pulls the push stack, as gate.py notes).
"""
from __future__ import annotations

import calendar
import logging
import math
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Optional

from short_interest import client as SIC

log = logging.getLogger("short_interest.read")

# FINRA: short interest is published on the 7th business day after the
# settlement date (FINRA schedule; six 2026 pairs reproduced exactly).
FINRA_PUBLICATION_BDAYS = 7
# HIS CALL #3 — a LABEL only: business days after FINRA's publication day
# before a cache still holding the older settlement reads STALE.
SI_INGEST_GRACE_BDAYS = 2
# One request reads at most this many names (the FE batcher's chunk equals it).
MAP_MAX_SYMBOLS = 200
GLYPH = "🩳"

SOURCE_SI = "FINRA short interest (Rule 4560) via Massive /stocks/v1/short-interest"
FLOAT_SOURCE = "yfinance floatShares (shares_cache)"
SHARES_SOURCE = "yfinance sharesOutstanding (shares_cache)"
LEGACY_SHARES_SOURCE = "Massive reference shares outstanding (legacy per-name warm)"

SOURCES = [
    {"label": "FINRA Rule 4560 (short-interest reporting)",
     "url": "https://www.finra.org/rules-guidance/rulebooks/finra-rules/4560"},
    {"label": "FINRA short-interest reporting schedule",
     "url": "https://www.finra.org/filing-reporting/regulatory-filing-systems/short-interest"},
    {"label": "Massive short-interest endpoint",
     "url": "https://massive.com/docs/rest/stocks/fundamentals/short-interest"},
]

_NOT_A_FORECAST = "A count of open short positions — not a forecast."


# ───────────────────────────────────────────── calendar (pure)
@lru_cache(maxsize=1)
def _holidays() -> frozenset:
    """NYSE full closures, loaded lazily from the ONE list the app keeps."""
    try:
        from market_hours.reminder import ALL_HOLIDAYS   # lazy: pulls the push stack
        return frozenset(str(d) for d in ALL_HOLIDAYS)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("short_interest.read: holiday list unavailable: %s",
                    type(exc).__name__)
        return frozenset()


def is_business_day(d: date) -> bool:
    return d.weekday() < 5 and d.isoformat() not in _holidays()


def prev_business_day(d: date) -> date:
    """`d` itself when it is a business day, else the business day before it
    (FINRA's "the 15th, or the business day before")."""
    while not is_business_day(d):
        d -= timedelta(days=1)
    return d


def add_business_days(d: date, n: int) -> date:
    """The n-th business day AFTER `d` (d itself never counts)."""
    out = d
    left = int(n)
    while left > 0:
        out += timedelta(days=1)
        if is_business_day(out):
            left -= 1
    return out


def settlements_in_month(y: int, m: int) -> list:
    last = calendar.monthrange(y, m)[1]
    return [prev_business_day(date(y, m, 15)), prev_business_day(date(y, m, last))]


def next_settlement_after(d: date) -> date:
    y, m = d.year, d.month
    for _ in range(3):
        for s in settlements_in_month(y, m):
            if s > d:
                return s
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    raise ValueError("no settlement found after %s" % d)      # pragma: no cover


def publication_date(settlement: date) -> date:
    return add_business_days(settlement, FINRA_PUBLICATION_BDAYS)


def due_date(settlement: date) -> date:
    return add_business_days(publication_date(settlement), SI_INGEST_GRACE_BDAYS)


def _as_date(v) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _iso_date(v) -> Optional[str]:
    d = _as_date(v)
    return d.isoformat() if d is not None else None


def _today(today) -> date:
    t = _as_date(today)
    # ONE CLOCK: the local date, like client._age_days and the Bonde legs.
    return t if t is not None else date.today()


def newer_settlement_can_exist(held, today=None) -> bool:
    """True when FINRA could have published a settlement newer than `held`."""
    h = _as_date(held)
    if h is None:
        return True
    return _today(today) >= publication_date(next_settlement_after(h))


def freshness(settlement_date, today=None) -> dict:
    s = _as_date(settlement_date)
    out = {"stale": None, "stale_reason": None, "published_on": None,
           "next_settlement_date": None, "next_due_on": None}
    if s is None:
        return out
    t = _today(today)
    nxt = next_settlement_after(s)
    due = due_date(nxt)
    stale = t > due
    out.update({
        "stale": bool(stale),
        "stale_reason": ("a newer FINRA settlement (%s) was due by %s; this app still holds %s"
                         % (nxt.isoformat(), due.isoformat(), s.isoformat())) if stale else None,
        "published_on": publication_date(s).isoformat(),
        "next_settlement_date": nxt.isoformat(),
        "next_due_on": due.isoformat(),
    })
    return out


# ───────────────────────────────────────────── number helpers
def _num(v) -> Optional[float]:
    """Finite float or None (never NaN/inf — Starlette serves allow_nan=False)."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _nonneg(v) -> Optional[float]:
    f = _num(v)
    return f if (f is not None and f >= 0) else None


def _pos_int(v) -> Optional[int]:
    """A share count: finite and > 0, else None (0 / negative = not on file)."""
    f = _num(v)
    return int(round(f)) if (f is not None and f > 0) else None


def _nonneg_int(v) -> Optional[int]:
    f = _nonneg(v)
    return int(round(f)) if f is not None else None


def _human_shares(n) -> str:
    f = _num(n)
    if f is None:
        return "—"
    a = abs(f)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= div:
            return "%.1f%s" % (f / div, suf)
    return "%d" % int(round(f))


def _pct1(p: float) -> str:
    return "<0.1%" if 0 < p < 0.05 else "%.1f%%" % p


def _dtc1(d: float) -> str:
    return "<0.1" if 0 < d < 0.05 else "%.1f" % d


def _md(iso: str) -> str:
    d = _as_date(iso)
    return "%d/%d" % (d.month, d.day) if d else str(iso)


def _iso_utc(epoch) -> Optional[str]:
    f = _num(epoch)
    if f is None or f <= 0:
        return None
    try:
        return datetime.fromtimestamp(f, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (OverflowError, OSError, ValueError):
        return None


def _ordinal(n: int) -> str:
    n = int(n)
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return "%d%s" % (n, suf)


# ───────────────────────────────────────────── the block
_BLOCK_KEYS = (
    "symbol", "status", "settlement_date", "published_on", "prev_settlement_date",
    "si_shares", "prev_si_shares", "si_change_pct", "avg_daily_volume", "days_to_cover",
    "float_shares", "float_asof", "float_source", "pct_of_float",
    "shares_outstanding", "shares_asof", "shares_source", "pct_of_shares_out",
    "headline_basis", "stale", "stale_reason", "next_settlement_date", "next_due_on",
    "source", "fetched_at", "chip", "title", "rows",
)


def _empty_block(sym: str) -> dict:
    b = {k: None for k in _BLOCK_KEYS}
    b["symbol"] = sym
    return b


def _no_record_block(sym: str, doc: dict) -> dict:
    b = _empty_block(sym)
    b.update({
        "status": "no_record",
        "source": SOURCE_SI,
        "fetched_at": _iso_utc(doc.get("fetched_at")),
        "chip": None,
        "title": ("Short interest: no FINRA record on file for %s at the last warm "
                  "— not read." % sym),
        "rows": [{"k": "Short interest",
                  "v": "not read — no FINRA record at the last warm"}],
    })
    return b


def si_block(doc: Optional[dict], today: Optional[date] = None) -> Optional[dict]:
    """The served block for one cached doc. PURE — no I/O, never fetches."""
    if not isinstance(doc, dict):
        return None
    sym = str(doc.get("symbol") or doc.get("_id") or "").strip().upper()
    si = _nonneg_int(doc.get("short_interest"))
    s = _as_date(doc.get("settlement_date"))
    if s is None or si is None:
        # A remembered miss, or a settlement with no readable date or count:
        # a number without its as-of is not shown.
        return _no_record_block(sym, doc)

    legacy = doc.get("v") != 2
    fl = None if legacy else _pos_int(doc.get("float_shares"))
    so = _pos_int(doc.get("shares_outstanding"))
    pf = round(si / fl * 100.0, 2) if fl else None
    ps = round(si / so * 100.0, 2) if so else None

    if legacy:
        shares_source = LEGACY_SHARES_SOURCE if so else None
        # The legacy per-name warm read the Massive count when it fetched.
        shares_asof = ((_iso_utc(doc.get("fetched_at")) or "")[:10] or None) if so else None
        float_asof = float_source = None
    else:
        shares_source = (str(doc.get("shares_source") or SHARES_SOURCE)) if so else None
        shares_asof = _iso_date(doc.get("shares_asof")) if so else None
        float_source = (str(doc.get("float_source") or FLOAT_SOURCE)) if fl else None
        float_asof = _iso_date(doc.get("float_asof")) if fl else None

    prev = _as_date(doc.get("prev_settlement_date"))
    prev_si = _nonneg_int(doc.get("prev_short_interest")) if prev else None
    chg = _num(doc.get("si_change_pct")) if prev else None
    if chg is not None:
        chg = round(chg, 1)
    adv = _nonneg_int(doc.get("avg_daily_volume"))
    dtc = _nonneg(doc.get("days_to_cover"))

    fr = freshness(s, today)
    basis = "float" if pf is not None else ("shares_out" if ps is not None else None)

    b = _empty_block(sym)
    b.update({
        "status": "stale" if fr["stale"] else "ok",
        "settlement_date": s.isoformat(),
        "published_on": fr["published_on"],
        "prev_settlement_date": prev.isoformat() if prev else None,
        "si_shares": si,
        "prev_si_shares": prev_si,
        "si_change_pct": chg,
        "avg_daily_volume": adv,
        "days_to_cover": dtc,
        "float_shares": fl,
        "float_asof": float_asof,
        "float_source": float_source,
        "pct_of_float": pf,
        "shares_outstanding": so,
        "shares_asof": shares_asof,
        "shares_source": shares_source,
        "pct_of_shares_out": ps,
        "headline_basis": basis,
        "stale": fr["stale"],
        "stale_reason": fr["stale_reason"],
        "next_settlement_date": fr["next_settlement_date"],
        "next_due_on": fr["next_due_on"],
        "source": str(doc.get("source") or SOURCE_SI),
        "fetched_at": _iso_utc(doc.get("fetched_at")),
    })
    b["chip"] = chip_text(b)
    b["title"] = title_text(b)
    b["rows"] = rows_for(b)
    return b


def _conflict(b: dict) -> bool:
    fl, so = b.get("float_shares"), b.get("shares_outstanding")
    return bool(fl and so and fl > so)


def _conflict_sentence(b: dict) -> str:
    return ("⚠ The float on file (%s) is larger than shares outstanding (%s) — the two "
            "counts disagree; read both with care."
            % (_human_shares(b["float_shares"]), _human_shares(b["shares_outstanding"])))


def chip_text(b: Optional[dict]) -> Optional[str]:
    if not b or b.get("status") == "no_record" or b.get("si_shares") is None:
        return None
    basis = b.get("headline_basis")
    if basis == "float":
        head = "%s float" % _pct1(b["pct_of_float"])
    elif basis == "shares_out":
        head = "%s shs out" % _pct1(b["pct_of_shares_out"])
    else:
        head = "%s sh" % _human_shares(b["si_shares"])
    parts = ["%s SI %s" % (GLYPH, head)]
    # A provider 0 next to a positive short count is not a readable figure:
    # drop the segment (the chip never shows "0.0d"); the hover keeps it.
    if b.get("days_to_cover") is not None and b["days_to_cover"] > 0:
        parts.append("%sd" % _dtc1(b["days_to_cover"]))
    parts.append(_md(b["settlement_date"]))
    if b.get("stale"):
        parts.append("stale")
    return " · ".join(parts)


def _change_phrase(b: dict, *, with_prev_count: bool) -> str:
    prev = b.get("prev_settlement_date")
    if not prev:
        return "no prior settlement on file"
    chg = b.get("si_change_pct")
    head = ("%+.1f%% vs %s" % (chg, prev)) if chg is not None else ("prior settlement %s" % prev)
    if with_prev_count and b.get("prev_si_shares") is not None:
        head += " (%s)" % format(b["prev_si_shares"], ",")
    return head


def title_text(b: dict) -> str:
    if not b or b.get("status") == "no_record" or b.get("si_shares") is None:
        return (b or {}).get("title") or "Short interest: not read."
    seg = ["%s Short interest — FINRA settlement %s (published ~%s)."
           % (GLYPH, b["settlement_date"], b["published_on"])]
    seg.append("%s shares short (%s)." % (format(b["si_shares"], ","),
                                          _change_phrase(b, with_prev_count=False)))
    if b.get("pct_of_float") is not None:
        s = "%s of float — float %s, %s" % (_pct1(b["pct_of_float"]),
                                           _human_shares(b["float_shares"]), b["float_source"])
        if b.get("float_asof"):
            s += ", as of %s" % b["float_asof"]
        seg.append(s + ".")
    else:
        seg.append("% of float: not read (no float on file).")
    if b.get("pct_of_shares_out") is not None:
        s = "%s of shares outstanding — %s, %s" % (
            _pct1(b["pct_of_shares_out"]), _human_shares(b["shares_outstanding"]),
            b["shares_source"])
        if b.get("shares_asof"):
            s += ", as of %s" % b["shares_asof"]
        seg.append(s + ".")
    else:
        seg.append("% of shares outstanding: not read.")
    if b.get("days_to_cover") is not None:
        if b.get("avg_daily_volume"):
            seg.append("%s days to cover (shares short ÷ %s average daily volume, the "
                       "provider's window)." % (_dtc1(b["days_to_cover"]),
                                                _human_shares(b["avg_daily_volume"])))
        else:
            seg.append("%s days to cover (the provider's figure)." % _dtc1(b["days_to_cover"]))
    else:
        seg.append("Days to cover: not read.")
    if b.get("stale"):
        seg.append("STALE — %s." % b["stale_reason"])
    if _conflict(b):
        seg.append(_conflict_sentence(b))
    seg.append(_NOT_A_FORECAST)
    seg.append("Source: %s. Not advice." % b["source"])
    return " ".join(seg)


def rows_for(b: dict) -> list:
    if not b or b.get("status") == "no_record" or b.get("si_shares") is None:
        return list((b or {}).get("rows") or [])
    rows = [{"k": "Settlement", "v": "%s (FINRA; published ~%s)"
             % (b["settlement_date"], b["published_on"])}]
    rows.append({"k": "Shares short", "v": "%s · %s" % (
        format(b["si_shares"], ","), _change_phrase(b, with_prev_count=True))})
    if b.get("pct_of_float") is not None:
        v = "%s — float %s (%s" % (_pct1(b["pct_of_float"]), format(b["float_shares"], ","),
                                   b["float_source"])
        v += (", as of %s)" % b["float_asof"]) if b.get("float_asof") else ")"
    else:
        v = "not read — no float on file"
    rows.append({"k": "% of float", "v": v})
    if b.get("pct_of_shares_out") is not None:
        v = "%s — shares outstanding %s (%s" % (
            _pct1(b["pct_of_shares_out"]), format(b["shares_outstanding"], ","),
            b["shares_source"])
        v += (", as of %s)" % b["shares_asof"]) if b.get("shares_asof") else ")"
    else:
        v = "not read — no shares outstanding on file"
    rows.append({"k": "% of shares outstanding", "v": v})
    dtc = b.get("days_to_cover")
    if dtc is None:
        v = "not read"
    elif b.get("avg_daily_volume"):
        v = "%.2f — shares short ÷ %s average daily volume (the provider's window)" % (
            dtc, format(b["avg_daily_volume"], ","))
    else:
        v = "%.2f — the provider's figure" % dtc
    rows.append({"k": "Days to cover", "v": v})
    if b.get("stale") is True:
        v = "STALE — %s" % b["stale_reason"]
    elif b.get("stale") is False:
        v = "current — next settlement %s, due ~%s" % (b["next_settlement_date"],
                                                        b["next_due_on"])
    else:
        v = "not read — the settlement date could not be read"
    rows.append({"k": "Freshness", "v": v})
    rows.append({"k": "Source", "v": b["source"]})
    if _conflict(b):
        rows.append({"k": "⚠ Counts disagree", "v": _conflict_sentence(b)})
    return rows


# ───────────────────────────────────────────── the map (ONE read)
def si_map(symbols, db=None, today=None) -> dict:
    """{SYM: block} for up to MAP_MAX_SYMBOLS names — ONE `$in` read of the
    short-INTEREST cache through `client.short_interest_map`. Never fetches; a
    name with no doc is absent, never zero-filled."""
    syms: list = []
    for s in symbols or []:
        s = str(s or "").strip().upper()
        if s and s not in syms:
            syms.append(s)
    syms = syms[:MAP_MAX_SYMBOLS]
    if not syms:
        return {}
    docs = SIC.short_interest_map(syms, db=db) or {}
    out: dict = {}
    for sym in syms:
        doc = docs.get(sym)
        if doc is None:
            continue
        d = dict(doc)
        d.setdefault("symbol", sym)
        try:
            blk = si_block(d, today)
        except Exception as exc:                               # noqa: BLE001
            log.warning("short_interest.read: block %s failed: %s", sym, type(exc).__name__)
            blk = None
        if blk is not None:
            out[sym] = blk
    return out


# ───────────────────────────────────────────── ℹ️ rules section
def rules_section() -> dict:
    return {
        "title": "Short interest — FINRA's count of open short positions (display only)",
        "emoji": GLYPH,
        "picks": [
            "What it is: shares sold short and not yet bought back, reported by FINRA member "
            "firms for two settlement dates a month — the 15th (or the business day before) "
            "and the last business day — and published on the %s business day after (FINRA "
            "Rule 4560). This app reads it from Massive, which aggregates the FINRA reports."
            % _ordinal(FINRA_PUBLICATION_BDAYS),
            "% of float = shares short ÷ float; % of shares outstanding = shares short ÷ "
            "shares outstanding. Both counts are yfinance's (floatShares / sharesOutstanding, "
            "cached in shares_cache) and carry their own date; older per-name records use "
            "Massive's shares outstanding — the hover names which. The chip leads with % of float "
            "when a float is on file, otherwise % of shares outstanding, and says which. Sites "
            "define float differently, so the same count can read several points apart from "
            "one site to the next.",
            "Days to cover = shares short ÷ average daily volume, as the provider computes it; "
            "the volume window differs between sites.",
            "Every number carries its settlement date. It reads STALE once a newer "
            "settlement's publication day plus %d business days has passed and this app "
            "still holds the older one. No record shows nothing on a card and 'not read' on "
            "the ticker page — never 0." % SI_INGEST_GRACE_BDAYS,
            "Not a forecast. Published studies find at most a small average effect across "
            "many stocks — one that shrank after it was published — and nothing about what "
            "one stock will do; part of any name's short interest is hedging (convertible "
            "bonds, options). UNMEASURED on this app's universe.",
            "Short VOLUME — the daily share of trades marked short — is a different series "
            "and is not this number.",
        ],
        "stops": ["No stop, no target, no size: a number and its date."],
        "alerts": ["Pushes nothing, gates nothing, sorts nothing and enters no lane."],
        "note": "A data label, not a rule or a signal. Not financial advice.",
    }
