"""🆕 IPOs ≤2y — the recent-listing population, corroborated before it is shown.

Ajay 2026-09-20: *"Can you build be an IPO tab of the hot sectors please?"* ·
*"IPO of hot sector theme of stocks and then add them as a tab in Chart maps"* ·
*"Also potential future IPOs coming up if stocktwitz has"*.

WHAT THIS IS
------------
A LIST, not a signal. The only thing cited here is the recency bound: TLSW
Ch. 11 ("Eighty percent of the stock market winners that drove the tech boom
during the 1990s were IPOs within the prior eight years", p. 260), which this
app already encodes as `sepa.ipo_age` — `is_recent_ipo = years <= 2`. This
module REUSES that bound by importing it; `RECENT_YEARS` below is pinned equal
to it by a test that reads the bound out of a real `ipo_age._block()` call, so
the number can never drift here without the suite saying so.

Nothing on this board is measured. No ordering, gate or entry is derived from
it, and the served note says so on every request.

WHY CORROBORATION EXISTS
------------------------
The listing dates come from Finnhub's `profile2.ipo`, cached in Mongo
`ipo_dates` by `sepa.ipo_age`. On this universe that field is ~21.4% corrupt:
a ticker that was RECYCLED — retired by one company and re-issued to a new
listing — carries the NEW listing's date while the price history belongs to
the OLD company, and a tile built on that pair prints a "day-1 pop" taken from
a bar that has nothing to do with the IPO.

So every claimed date is checked against TWO independent things:

1. Finnhub `/calendar/ipo` — a priced deal for that symbol within
   ±`NEAR_DAYS` of the claimed date.
2. The price frame's FIRST BAR. A frame that starts on/after the claimed date
   (within `BAR_SLACK_DAYS`) agrees with it. A frame that starts well BEFORE
   it means bars exist from before the listing — the recycled-ticker
   signature.

The four outcomes:

======================  ===========================================  ==========
status                  meaning                                      shown?
======================  ===========================================  ==========
``confirmed``           calendar agrees; bars agree or cannot say     yes
``recycled``            calendar agrees but bars pre-date the         yes, flagged,
                        listing — the ticker carries another          with every
                        company's history (conclusive even when       price stat blanked
                        the frame is truncated at its fetch cap)
``uncorroborated``      calendar is silent; bars agree or cannot say  NO — dropped,
                                                                     counted; the
                                                                     calendar-outage
                                                                     build still
                                                                     shows it flagged
``bogus``               calendar is silent AND bars pre-date the      NO — dropped
                        claimed listing (conclusive even at the cap)
======================  ===========================================  ==========

`uncorroborated` USED to be shown with a warning badge rather than dropped,
because Finnhub's calendar does not reach back over the whole trailing window
for every venue and silently hiding a real listing is the worse error. Ajay
answered that owner's-call on 2026-09-20 — *"Yes for #1 and #2 and #3 and #4
and #5"*, #3 being "DROP the IPO tab's uncorroborated rows". They are now
dropped and COUNTED in ``counts.dropped_uncorroborated``, which the strip's
basis line prints, so the drop is never silent. The live board on 2026-09-20
held 22 of them and they were mostly spin-offs and re-listings (HONA, FDXF,
VSNT, GLIBA/GLIBK, RAL, MRP, ECG, CURB, AMTM, Q, PSKY, SNDK, BULL, CEP …).

The CALENDAR-OUTAGE build is the exception and stays as it was: with no
calendar to be silent, "uncorroborated" says nothing about the listing, so
every candidate is still SHOWN flagged and nothing is dropped.

BARS THAT CANNOT SAY
--------------------
`sepa.prices` frames are capped (`prices.PERIOD_DAYS`) and the cache is keyed
by symbol only, so a first bar sitting AT a cap is history truncation, not a
listing (SAIC, 2026-08-31). That guard is `ipo_age._at_fetch_cap` and it is
imported, never re-derived — a first bar at the cap makes the bar evidence
INCONCLUSIVE, and the calendar alone then decides confirmed vs uncorroborated.

That guard covers ONE direction only (corrected 2026-09-20). A first bar at
the cap cannot prove the claimed date is the listing day; it can still
DISPROVE a claim that sits well after it, because bars between the cap and
the claim are real sessions of this symbol. XOM's profile claimed a
2026-07-02 listing over a frame that starts at the 2024-09-19 cap; the first
cut read "at cap → inconclusive → uncorroborated" and put XOM at the top of
the tab as an 80-day-old IPO. Bars before the claim are conclusive at the cap
or off it: recycled when the calendar prices a deal, bogus when it is silent.

CALENDAR OUTAGE
---------------
If Finnhub cannot be reached the board still builds, from `ipo_age` alone:
every tile becomes `uncorroborated`, `corroboration.available` is False and
carries the reason. A board that quietly turns into a different board is the
failure mode this avoids.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Optional

log = logging.getLogger("chart_maps.ipo")

# ---------------------------------------------------------------------------
# constants — every one of them named, none of them a threshold on a decision
# ---------------------------------------------------------------------------

# The book's recency bound, identical to `sepa.ipo_age._block`'s
# `is_recent_ipo = years <= 2` (TLSW p. 260). Pinned equal by
# tests/test_ipo_tab.py, which reads the bound out of a real `_block()` call
# rather than retyping it.
RECENT_YEARS = 2

# The trailing window the population is drawn from, in days — the same two
# years, expressed in the unit the Mongo query and the calendar chunker use.
TRAILING_DAYS = 730

# How far ahead "potential future IPOs coming up" looks. One month of the
# forward calendar: Finnhub prices deals a few days out, so a longer horizon
# is mostly `filed` rows with no date he can act on.
FORWARD_DAYS = 30

# Finnhub serves `/calendar/ipo` per window; the trailing window is chunked
# into quarters so one 5xx costs a quarter, not the whole history.
CAL_CHUNK_DAYS = 90

# A calendar deal within this many days of the claimed profile date is the
# same event. Finnhub's calendar date is the PRICING date and profile2's is
# the first trade date; they routinely differ by a few days, and a whole
# month is comfortably inside "the same deal" while staying far short of the
# next quarter's crop.
NEAR_DAYS = 30

# The first daily bar may print a few sessions after the listing date (a
# listing on a half-day, a provider that starts the frame on the first FULL
# session). Inside this slack the bars AGREE with the claimed date; before it
# they contradict it.
BAR_SLACK_DAYS = 7

CONFIRMED, RECYCLED, UNCORROBORATED, BOGUS = (
    "confirmed", "recycled", "uncorroborated", "bogus")

# The one Finnhub calendar status that means the deal actually happened.
PRICED = "priced"
# The one that means it is still ahead of us.
EXPECTED = "expected"

# Served on every payload. It names the cite, the source, the known corruption
# rate and — first — that nothing here is measured.
NOTE = (
    "Recency is TLSW Ch.11 (≤2 years, sepa/ipo_age). Nothing here is "
    "measured or claims an edge. Listing dates come from Finnhub profile2 "
    "(21.4% corrupt on this universe) corroborated against Finnhub "
    "/calendar/ipo. Listings the calendar does not carry are dropped "
    "(2026-09-20)."
)


# ---------------------------------------------------------------------------
# small date helpers — every one returns None rather than guessing
# ---------------------------------------------------------------------------
def _as_date(v) -> Optional[date]:
    """YYYY-MM-DD (or a date/datetime) → date, else None. Never raises."""
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if not isinstance(v, str):
        return None
    try:
        return datetime.strptime(v.strip()[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _today() -> date:
    return datetime.utcnow().date()


# ---------------------------------------------------------------------------
# the Finnhub calendar
# ---------------------------------------------------------------------------
def _row_symbol(row) -> str:
    """The row's ticker, upper-cased. Empty for a withdrawn filing, which
    Finnhub serves with a blank `symbol` — those rows are kept in `rows` (the
    caller may want to count them) but can never match a candidate."""
    if not isinstance(row, dict):
        return ""
    return str(row.get("symbol") or "").strip().upper()


def _row_status(row) -> str:
    if not isinstance(row, dict):
        return ""
    return str(row.get("status") or "").strip().lower()


def _is_priced(row) -> bool:
    """Did this deal actually price?

    `status == "priced"` is the answer Finnhub gives. Historical rows
    occasionally arrive with the status field missing altogether while still
    carrying a price — treated as priced, because an empty status on a row
    that has a price is a gap in the feed, not a withdrawal. A row whose
    status says anything else (`filed`, `withdrawn`, `expected`) is NOT
    priced, whatever else it carries.
    """
    st = _row_status(row)
    if st == PRICED:
        return True
    if st:
        return False
    return bool(isinstance(row, dict) and (row.get("price") or "")) and bool(_row_symbol(row))


async def _fetch_windows(FH, windows) -> list:
    """Await every chunk on ONE loop, sequentially.

    Sequential on purpose: the client's token bucket is 25 req/min and these
    chunks are the cheapest possible way to spend it. `FH.ipo_calendar` is
    resolved off the module on each call so a test can monkeypatch it.
    """
    out = []
    for frm, to in windows:
        try:
            got = await FH.ipo_calendar(frm, to)
        except Exception as exc:
            out.append((frm, to, None, exc))
        else:
            out.append((frm, to, got, None))
    return out


def _run(coro):
    """Run one coroutine from a SYNC caller without disturbing the thread.

    `asyncio.run()` sets the thread's current event loop to None when it is
    done, which poisons anything in the same thread that later calls
    `get_event_loop()` — on Python 3.9 that is a hard RuntimeError. The board
    runs inside `asyncio.to_thread`, so it must hand the thread back exactly
    as it found it. One loop for the whole call, then the previous loop is
    restored.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:                                                      # pragma: no cover
        raise RuntimeError(
            "chart_maps.ipo.calendar() is a sync call and cannot run inside a "
            "running event loop — call it through asyncio.to_thread()")

    try:
        prev = asyncio.get_event_loop()
    except Exception:                                          # pragma: no cover
        prev = None
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.close()
        finally:
            try:
                asyncio.set_event_loop(prev)
            except Exception:                                  # pragma: no cover
                pass


def calendar(from_d: str, to_d: str) -> dict:
    """Finnhub `/calendar/ipo` over [from_d, to_d], chunked.

    Returns ``{"ok": bool, "rows": list, "reason": str | None}``.

    `ok` is False if ANY chunk failed — a partially fetched calendar would
    corroborate some names and silently fail to corroborate others, which is
    exactly the asymmetry that makes a flag meaningless. The rows that DID
    arrive are still returned, so `upcoming` can show what it has while every
    tile is honestly marked uncorroborated.
    """
    start, end = _as_date(from_d), _as_date(to_d)
    if start is None or end is None or start > end:
        return {"ok": False, "rows": [], "reason": "bad date window"}

    try:
        from finnhub_client import client as FH
    except Exception as exc:                                   # pragma: no cover
        return {"ok": False, "rows": [], "reason": f"finnhub client unavailable: {exc}"}

    windows = []
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=CAL_CHUNK_DAYS - 1), end)
        windows.append((cur.isoformat(), chunk_end.isoformat()))
        cur = chunk_end + timedelta(days=1)

    try:
        results = _run(_fetch_windows(FH, windows))
    except Exception as exc:                                   # pragma: no cover
        log.warning("chart-maps ipo: calendar run failed: %s", exc)
        return {"ok": False, "rows": [],
                "reason": f"Finnhub /calendar/ipo could not be called: {exc}"}

    rows: list[dict] = []
    ok = True
    reason: Optional[str] = None
    for frm, to, got, exc in results:
        if exc is not None:
            log.warning("chart-maps ipo: calendar %s..%s failed: %s", frm, to, exc)
            ok = False
            reason = reason or f"Finnhub /calendar/ipo failed: {exc}"
            continue
        if got is None:
            ok = False
            reason = reason or (
                "Finnhub /calendar/ipo returned nothing for "
                f"{frm}..{to} (no key, rate limit, or outage)")
            continue
        rows.extend(r for r in got if isinstance(r, dict))

    return {"ok": ok, "rows": rows, "reason": reason}


def _priced_index(cal_rows) -> dict[str, list[date]]:
    """{SYMBOL: [priced dates]} — the corroboration lookup, built once."""
    out: dict[str, list[date]] = {}
    for r in cal_rows or []:
        if not isinstance(r, dict):
            continue
        sym = _row_symbol(r)
        d = _as_date(r.get("date"))
        if not sym or d is None or not _is_priced(r):
            continue
        out.setdefault(sym, []).append(d)
    return out


# ---------------------------------------------------------------------------
# the population
# ---------------------------------------------------------------------------
def candidates(universe: str = "full", cal_rows=None) -> list[dict]:
    """Every in-universe name claiming a listing inside the trailing window.

    Two sources, merged on the symbol:

    - Mongo `ipo_dates` (written by `sepa.ipo_age`, from Finnhub profile2):
      docs whose `ipo` is on or after ``today - TRAILING_DAYS``.
    - `cal_rows`, when given: priced calendar deals in the same window. A
      brand-new listing has no profile row until something asks `ipo_age` for
      it, so the calendar is what puts this week's IPO on the board at all.

    The profile date WINS when both exist — it is the first-trade date, which
    is what `ipo_age` and every other surface in this app measure age from.

    Returns ``[{"symbol", "claimed", "claimed_source"}]``, newest claimed date
    first. Never raises: a dead Mongo returns the calendar half alone.
    """
    cutoff = _today() - timedelta(days=TRAILING_DAYS)

    try:
        from sepa import universe as U
        in_universe = {s.upper() for s in (U.load_universe(universe) or [])}
    except Exception as exc:
        log.warning("chart-maps ipo: universe load failed: %s", exc)
        in_universe = set()

    found: dict[str, dict] = {}

    for r in cal_rows or []:
        if not isinstance(r, dict):
            continue
        sym = _row_symbol(r)
        d = _as_date(r.get("date"))
        if not sym or d is None or not _is_priced(r):
            continue
        if d < cutoff or d > _today():
            continue
        if in_universe and sym not in in_universe:
            continue
        prior = found.get(sym)
        if prior is None or d > _as_date(prior["claimed"]):
            found[sym] = {"symbol": sym, "claimed": d.isoformat(),
                          "claimed_source": "calendar"}

    try:
        from sepa.ipo_age import _ipo_coll
        coll = _ipo_coll()
    except Exception:                                          # pragma: no cover
        coll = None
    if coll is not None:
        try:
            for doc in coll.find({"ipo": {"$gte": cutoff.isoformat()}},
                                 {"_id": 1, "ipo": 1}):
                sym = str(doc.get("_id") or "").strip().upper()
                d = _as_date(doc.get("ipo"))
                if not sym or d is None or d < cutoff:
                    continue
                # A claimed date in the FUTURE is what `ipo_age.age()` already
                # refuses (it returns all-None). Refused here too, for the same
                # reason: a company that has not listed has no age.
                if d > _today():
                    continue
                if in_universe and sym not in in_universe:
                    continue
                found[sym] = {"symbol": sym, "claimed": d.isoformat(),
                              "claimed_source": "profile"}
        except Exception as exc:
            log.warning("chart-maps ipo: ipo_dates read failed: %s", exc)

    out = list(found.values())
    out.sort(key=lambda r: (r["claimed"], r["symbol"]), reverse=True)
    return out


# ---------------------------------------------------------------------------
# corroboration
# ---------------------------------------------------------------------------
def corroborate(sym: str, claimed: str, cal_rows, first_bar: Optional[str],
                at_cap: bool) -> dict:
    """One claimed listing date against the calendar and the first bar.

    ``cal_rows`` may be the raw calendar list or the ``{SYMBOL: [dates]}``
    index from `_priced_index` (the board builds it once for hundreds of
    names).

    Returns ``{"status", "in_calendar", "bars": "agree"|"before"|"inconclusive",
    "why"}``. `why` is a sentence the tile prints — a flag nobody can explain
    is a flag nobody trusts.
    """
    sym = (sym or "").strip().upper()
    claimed_d = _as_date(claimed)
    index = cal_rows if isinstance(cal_rows, dict) else _priced_index(cal_rows)
    dates = index.get(sym) or []
    in_cal = claimed_d is not None and any(
        abs((d - claimed_d).days) <= NEAR_DAYS for d in dates)

    first_d = _as_date(first_bar)
    if first_d is None or claimed_d is None:
        bars = "inconclusive"
    elif first_d < claimed_d - timedelta(days=BAR_SLACK_DAYS):
        # Bars exist BEFORE the claimed listing. That is conclusive whether or
        # not the frame is truncated at a fetch cap: truncation removes OLD
        # bars, it never invents bars between the cap and the claim. XOM,
        # 2026-09-20 — profile said "listed 2026-07-02", the 2y frame started
        # at the cap (2024-09-19) with ~450 sessions before the claim, and the
        # old rule filed it "inconclusive" → uncorroborated → shown as an
        # 80-day-old IPO at the top of the tab. Same for MKSI, RNA, VNOM, TEM.
        bars = "before"
    elif at_cap:
        # The first bar sits at the cap and is NOT before the claim: the claim
        # is at or near the cap, so a truncated frame cannot say whether that
        # first bar is the listing day or just the oldest bar it kept (SAIC,
        # 2026-08-31). The calendar alone decides.
        bars = "inconclusive"
    else:
        bars = "agree"

    if bars == "before":
        status = RECYCLED if in_cal else BOGUS
    else:
        status = CONFIRMED if in_cal else UNCORROBORATED

    if status == CONFIRMED:
        why = ("Finnhub's IPO calendar carries a priced deal for this symbol "
               "within a month of the listing date"
               + (", and the price history starts with it"
                  if bars == "agree" else
                  ", and the price frame is truncated at its fetch cap so the "
                  "bars cannot say either way"))
    elif status == RECYCLED:
        why = (f"the calendar prices this deal near {claimed}, but bars exist "
               f"from {first_bar} — before the listing. This ticker was "
               "recycled: the price history belongs to a different company, so "
               "every price-derived figure on this tile is blanked")
    elif status == UNCORROBORATED:
        why = ("Finnhub's IPO calendar has no priced deal for this symbol near "
               "the claimed date, so the listing date is the profile's word "
               "alone"
               + (" (the bars agree with it)" if bars == "agree" else
                  " (the price frame is truncated at its fetch cap, so the bars "
                  "cannot say either way)"))
    else:
        why = (f"the calendar has no deal near {claimed} and bars exist from "
               f"{first_bar}, before it — the claimed listing date is not "
               "supported by anything, so this name is dropped")

    return {"status": status, "in_calendar": in_cal, "bars": bars, "why": why}


# ---------------------------------------------------------------------------
# the two price stats
# ---------------------------------------------------------------------------
def first_moves(df, claimed) -> dict:
    """``{"day1_pct", "week1_pct", "day1_date"}`` off the listing's own bars.

    - ``day1_pct``  — the first bar on/after the claimed date, OPEN to CLOSE.
      This is the first SESSION's move, NOT the pop off the offer price: this
      app does not hold offer prices, and the stat labels on the tile say so
      in words.
    - ``week1_pct`` — the close of the 5th session against day 1's OPEN.

    Both are None when the frame does not actually start at the listing (no
    bar within ``BAR_SLACK_DAYS`` of the claimed date), and ``week1_pct`` is
    None when the fifth session has not happened yet.
    """
    out = {"day1_pct": None, "week1_pct": None, "day1_date": None}
    claimed_d = _as_date(claimed)
    if df is None or claimed_d is None:
        return out
    try:
        if getattr(df, "empty", True):
            return out
    except Exception:                                          # pragma: no cover
        return out

    import pandas as pd

    idx = 0
    first_d = None
    for i, ts in enumerate(df.index):
        try:
            d = pd.Timestamp(ts).to_pydatetime().replace(tzinfo=None).date()
        except Exception:                                      # pragma: no cover
            continue
        if d >= claimed_d:
            idx, first_d = i, d
            break
    if first_d is None:
        return out
    # A frame that only picks up WEEKS after the listing is not this listing's
    # first session — better silent than wrong.
    if (first_d - claimed_d).days > BAR_SLACK_DAYS:
        return out

    def _f(v):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return f if f == f and f not in (float("inf"), float("-inf")) else None

    try:
        o = _f(df["Open"].iloc[idx])
        c = _f(df["Close"].iloc[idx])
    except Exception:                                          # pragma: no cover
        return out
    out["day1_date"] = first_d.isoformat()
    if o and o > 0 and c is not None:
        out["day1_pct"] = round((c - o) / o * 100.0, 2)
        # Bar 5 counting day 1 as bar 1.
        j = idx + 4
        if j < len(df.index):
            c5 = _f(df["Close"].iloc[j])
            if c5 is not None:
                out["week1_pct"] = round((c5 - o) / o * 100.0, 2)
    return out


# ---------------------------------------------------------------------------
# "potential future IPOs coming up"
# ---------------------------------------------------------------------------
def upcoming(cal_rows, today=None) -> list[dict]:
    """Forward deals inside ``FORWARD_DAYS``, carried VERBATIM.

    Only ``status == "expected"`` — a `filed` row has no date he can act on
    and a `withdrawn` one is not coming. Every field is passed through exactly
    as Finnhub serves it: `price` is a string like "18.00-20.00" and
    `numberOfShares` can be a string too, and parsing either into a number
    here would invent precision the feed did not give.

    Sorted by date, earliest first. Rows with no parseable date are dropped —
    an undated "upcoming" row is not upcoming.
    """
    t = _as_date(today) or _today()
    horizon = t + timedelta(days=FORWARD_DAYS)
    out = []
    # (symbol, date) deduped: the window is fetched in chunks and a retried or
    # overlapping chunk must not print the same deal twice, nor count it twice.
    seen: set[tuple[str, str]] = set()
    for r in cal_rows or []:
        if not isinstance(r, dict):
            continue
        if _row_status(r) != EXPECTED:
            continue
        d = _as_date(r.get("date"))
        if d is None or d < t or d > horizon:
            continue
        key = (_row_symbol(r), d.isoformat())
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "symbol": _row_symbol(r),
            "name": r.get("name"),
            "date": r.get("date"),
            "exchange": r.get("exchange"),
            "price": r.get("price"),
            "numberOfShares": r.get("numberOfShares"),
            "totalSharesValue": r.get("totalSharesValue"),
            "status": r.get("status"),
        })
    out.sort(key=lambda r: (str(_as_date(r["date"])), r["symbol"]))
    return out


# ---------------------------------------------------------------------------
# the board's data
# ---------------------------------------------------------------------------
def _evaluate(row: dict, index: dict, cal_ok: bool = True,
              cal_reason: Optional[str] = None) -> tuple[Optional[dict], Optional[str]]:
    """One candidate → ``(row, dropped_as)``.

    ``dropped_as`` is None when the row is kept, and otherwise names WHY it was
    dropped — `BOGUS` or `UNCORROBORATED`. The caller counts the tuples; it
    never subtracts ``len(rows)`` from ``len(cands)``, because two different
    drops now share that difference and a count that cannot say which is which
    is a count he cannot read.

    With the calendar up, a listing it does not carry is dropped
    (2026-09-20, Ajay: *"Yes … #3"*).

    ``cal_ok=False`` is the calendar-outage path and is UNCHANGED: NOTHING can
    be corroborated, so every row comes back `uncorroborated`, is SHOWN
    flagged, and nothing is dropped — a board that silently became a different
    board (one that had quietly deleted the names the calendar would have
    confirmed) is the failure this avoids. The bar evidence is still read,
    because `recycled` blanks the price stats and another company's day-1 move
    must never print whatever the calendar says.
    """
    from sepa import ipo_age as IA
    from sepa.prices import load_prices

    sym, claimed = row["symbol"], row["claimed"]
    first_bar, at_cap, df = None, False, None
    try:
        df = load_prices(sym, period="max")
    except Exception as exc:
        log.debug("chart-maps ipo: prices %s failed: %s", sym, exc)
        df = None
    if df is not None and not getattr(df, "empty", True):
        try:
            import pandas as pd
            first_ts = pd.Timestamp(df.index[0]).to_pydatetime().replace(tzinfo=None)
            first_bar = first_ts.date().isoformat()
            # The truncation guard is `ipo_age`'s, imported — never re-derived.
            at_cap = IA._at_fetch_cap((datetime.utcnow() - first_ts).days)
        except Exception:                                      # pragma: no cover
            first_bar, at_cap = None, False

    corr = corroborate(sym, claimed, index, first_bar, at_cap)
    status, why = corr["status"], corr["why"]
    if not cal_ok:
        status = UNCORROBORATED
        why = ("Finnhub's IPO calendar could not be read on this build"
               + (f" ({cal_reason})" if cal_reason else "")
               + ", so nothing on this board is corroborated: the listing date "
                 "is the profile's word alone"
               + (f", and bars exist from {first_bar} — before it, so this "
                  "ticker looks recycled and every price-derived figure is "
                  "blanked" if corr["bars"] == "before" else ""))
    elif status == BOGUS:
        return None, BOGUS
    elif status == UNCORROBORATED:
        # The calendar WAS read and is silent on this symbol: dropped, and
        # counted by the caller so the strip can say how many went.
        return None, UNCORROBORATED

    claimed_d = _as_date(claimed)
    days_since = (_today() - claimed_d).days if claimed_d else None
    # A recycled ticker's bars belong to another company: NO price-derived
    # figure may be computed off them, let alone printed. Keyed on the BAR
    # evidence, not on the status, so the outage path blanks them too.
    recycled = corr["bars"] == "before"
    moves = ({"day1_pct": None, "week1_pct": None, "day1_date": None}
             if recycled else first_moves(df, claimed))

    return {
        "symbol": sym,
        "claimed": claimed,
        "claimed_source": row.get("claimed_source"),
        "status": status,
        "in_calendar": corr["in_calendar"],
        "bars": corr["bars"],
        "why": why,
        "first_bar": first_bar,
        "days_since": days_since,
        "recycled": recycled,
        "day1_pct": moves["day1_pct"],
        "week1_pct": moves["week1_pct"],
        "day1_date": moves["day1_date"],
    }, None


def build(limit: int = 24, days: int = 130, universe: str = "full") -> dict:
    """The whole IPO read: rows + upcoming + counts + corroboration state.

    `days` is the caller's chart window and is untouched here — the board
    attaches bars. `limit` caps how many rows come back, newest listing first.
    """
    today = _today()
    trailing_from = today - timedelta(days=TRAILING_DAYS)
    forward_to = today + timedelta(days=FORWARD_DAYS)

    cal = calendar(trailing_from.isoformat(), forward_to.isoformat())
    cal_rows = cal.get("rows") or []
    index = _priced_index(cal_rows)

    cands = candidates(universe, cal_rows=cal_rows)

    cal_ok = bool(cal.get("ok"))
    cal_reason = cal.get("reason")
    rows: list[dict] = []
    n_dropped = {BOGUS: 0, UNCORROBORATED: 0}
    if cands:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as pool:
            for r, dropped_as in pool.map(
                    lambda c: _evaluate(c, index, cal_ok, cal_reason), cands):
                if r is not None:
                    rows.append(r)
                elif dropped_as in n_dropped:
                    n_dropped[dropped_as] += 1
    rows.sort(key=lambda r: (r["claimed"], r["symbol"]), reverse=True)

    ups = upcoming(cal_rows, today)
    counts = {
        "candidates": len(cands),
        "confirmed": sum(1 for r in rows if r["status"] == CONFIRMED),
        "recycled": sum(1 for r in rows if r["status"] == RECYCLED),
        # Zero while the calendar is up — an uncorroborated row is dropped
        # now. On the outage path every SHOWN row is uncorroborated, and this
        # is that count.
        "uncorroborated": sum(1 for r in rows if r["status"] == UNCORROBORATED),
        "dropped_bogus": n_dropped[BOGUS],
        "dropped_uncorroborated": n_dropped[UNCORROBORATED],
        "upcoming": len(ups),
    }
    return {
        "rows": rows[:max(1, int(limit or 24))],
        "upcoming": ups,
        "counts": counts,
        "corroboration": {
            "available": cal_ok,
            "reason": cal_reason,
            "trailing_from": trailing_from.isoformat(),
            "forward_to": forward_to.isoformat(),
        },
        "as_of": today.isoformat(),
        "note": NOTE,
    }
