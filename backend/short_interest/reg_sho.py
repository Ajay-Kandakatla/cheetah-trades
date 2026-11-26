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

THE CLOSE-OUT DAY (2026-11-24, Ajay: "I need to know when it would like to Potentially squeeze.." · "Add a tag with
date in it.."; see docs/gajjala/reg_sho_closeout_day_2026_11_24.md). The tag now also counts the name's current run of
straight SETTLEMENT days on its list and prints the Rule 203(b)(3) close-out day of that run (`reg_sho_runs`, the pure
math). The per-date history is READ now:
  * the same single worker, right AFTER `refresh_due` (never inside it), backfills RS_HIST_SETTLEMENT_DAYS settlement
    days of lists per market through the same fetch path (`backfill_history`), paced and bounded;
  * a date with no file, or one that errored, gets a hole doc (`kind: "nolist"`, op fetch or confirm, `tries`,
    `asked_at`); ONE retry rule (`_hole_due`): errors are re-asked, never final; a source with a fresh error sits
    out RS_RETRY_MIN; one failing item per source per round; a Mongo write that raises trips an in-process breaker;
  * a backfilled list doc carries `backfilled: true` — its `fetched_at` is the BACKFILL time, days after the trade
    date, so it is NOT a point-in-time record;
  * the read adds exactly two `find` filters, both bounded by the window:
    {"kind": "list", "trade_date": {"$gte": …}} and {"kind": "nolist", "trade_date": {"$gte": …}};
  * any failure in the history path serves `day count unknown` on the tag — never the fault payload.
A rule date, not a price read. DISPLAY ONLY. UNMEASURED.

THE RUN'S FIRST DAY (2026-11-26, spec sitrack §3.4 A5; Ajay: "can we make sure in the future these # are accurate ?").
A name on every list of the window read `day 30+` — its first day was knowable, the app did not read far enough back.
  * only names a caller ASKED about through `payload(check=…)` are walked (`_note_asks`, in-process, newest
    RS_CHECK_MAX kept, never stored); a name is never walked because it merely sits on a list;
  * the same worker, right AFTER `backfill_history`, walks older lists for them (`extend_runs`) inside ONE call budget
    (RS_HIST_MAX_GETS a round), Nasdaq first; a market stops the moment its asked names are resolved or blocked;
  * one doc per walked name (`kind: "runstart"`); `ext_due` is the ONE definition of done; the read adds a third
    bounded `find` {"kind": "runstart", "on_through": {"$gte": …}} and `reg_sho_runs.extend_run` reads it.

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
from short_interest import reg_sho_runs as RUNS

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
# the close-out day's history (2026-11-24) — engineering constants, MINE, none is a trading threshold
RS_HIST_SETTLEMENT_DAYS = 30     # settlement days of lists read behind (and including) the newest one, per market
RS_HIST_MAX_GETS = 40            # outside calls after which a backfill round starts no further item
RS_HIST_BUDGET_SEC = 45          # wall budget of one backfill round
RS_HIST_PAUSE_SEC = 0.25         # pause between two backfill items
RS_HIST_MAX_TRIES = 3            # asks of one hole at the short spacing; then an error goes daily, a missing is final
RS_HIST_REASK_MIN = 1440         # minutes between two asks of a missing hole, and of an error hole past the tries
RS_HIST_NOT_READ_MAX = 10        # unread dates listed per market in closeout.history.not_read
HOLE_KIND = "nolist"             # doc kind of a recorded hole
# the run's first day, read past the window (2026-11-26, spec sitrack §3.4 A5) — engineering constants, MINE
RS_RUN_START_MAX_SETTLEMENT_DAYS = 250   # walk-back bound per asked name (about one year of settlement days)
RUNSTART_KIND = "runstart"               # doc kind of a name's walked-back run start
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

# the close-out day (2026-11-24) — every number comes from a reg_sho_runs constant or the run block, never typed here
CLOSEOUT_WORD = "close-out"                             # the rule's own word — HIS CALL #6
RUN_DAY = "day %d of %d"                                # n, rule days
RUN_DAY_PAST = "day %d"
RUN_DAY_OPEN = "day %d+"
IF_STAYS = "if it stays on"                             # on the chip AND the label: the phone has no hover
RUN_TAIL = " · %s · %s day %s %s"                       # chip + label, counting: RUN_DAY, CLOSEOUT_WORD, date, IF_STAYS
RUN_TAIL_REACHED = " · %s · %s day %s"                  # chip + label, reached: the date is this list's own date
CHIP_RUN_PAST = " · %s · %s day passed %s · still on"   # RUN_DAY_PAST, CLOSEOUT_WORD, date
CHIP_RUN_OPEN = " · %s · %s day passed · still on"      # RUN_DAY_OPEN, CLOSEOUT_WORD
LABEL_RUN_PAST = " · %s · %s day passed %s · still on the list"
LABEL_RUN_OPEN = " · %s · %s day passed · still on the list"
RUN_UNKNOWN = " · day count unknown"                    # chip and label
SHORT_RUN = "%s %s %s · %s"                             # GLYPH, CLOSEOUT_WORD, date, RUN_DAY — DATE FIRST (ellipsis-safe)
SHORT_RUN_PAST = "%s %s passed %s · %s"                 # GLYPH, CLOSEOUT_WORD, date, RUN_DAY_PAST
SHORT_RUN_OPEN = "%s %s passed · %s"                    # GLYPH, CLOSEOUT_WORD, RUN_DAY_OPEN
LATE_ALT = " (%s if counted from each list's next open)"
# the 🔒 source tag of a name STILL on its list after its close-out day (2026-11-24 sissr §3.2) — Ajay 2026-11-24:
# "Days past little bit like AKAN is what I am mainly looking for". Day N is a backstop, a rule date only.
PAST_CLOSEOUT_TEXT = "%s day %d past %s"                # GLYPH, days past day N, CLOSEOUT_WORD → 🔒 day 6 past close-out
PAST_CLOSEOUT_OPEN_TEXT = "%s day %d+ past %s"          # the run's first day not known → 🔒 day 17+ past close-out
RULE_SENTENCE = ("After day %d, %s makes a clearing firm buy shares to close out a fail to deliver it carried on every "
                 "one of those days")
BUY_WINDOW = "; the buying may come from day %d (%s) and must start by the next open (%s)"
RULE_204_SENTENCE = ("%s already requires a fail in any stock to be closed out %d to %d settlement days after "
                     "settlement, so fails generally do not last %d (SEC staff); for a %s sale the count is %d, not %d.")
TITLE_RUN = " On the list %d straight settlement %s since %s. Day %d = %s %s%s. %s%s."
TITLE_RUN_REACHED = " On the list %d straight settlement days since %s. Day %d = %s, this list's date%s. %s%s."
TITLE_RUN_PAST = (" On the list %d straight settlement days since %s. Day %d was %s%s; it is still on the list %d "
                  "settlement %s later. %s. Staying listed means the total of fails is still over the level, not that "
                  "any one fail is that old — a name leaves a list only after %d straight settlement days back under it.")
TITLE_RUN_OPEN_WINDOW = (" On every list read for the last %d settlement days (back to %s), so day %d has passed; this "
                         "app has read only those %d days, so the date is not known to it. %s.")
# 2026-11-26 (sitrack §3.4): a `passed_open` run walked back past the window by the worker (an asked name only)
TITLE_RUN_OPEN_READ = (" On every list read back to %s (%d settlement days), so day %d has passed. The lists before %s "
                       "%s, so the first day is not known to this app. %s.")
OPEN_READ_NOT_YET = "have not been read yet"            # blocked None — the walk has not finished
OPEN_READ_FAILED = "could not be read"                  # blocked "missing" / "error"
OPEN_READ_CAP = "are past the %d settlement days this app reads back"   # blocked "cap" — RS_RUN_START_MAX_SETTLEMENT_DAYS
TITLE_RUN_OPEN_HOLE = (" On the list at least %d straight settlement days, so day %d has passed; its date is not known "
                       "— the %s list for %s has not been read. %s.")
TITLE_RUN_UNKNOWN = " Days on the list: not known — the %s list for %s has not been read."
TITLE_RUN_UNKNOWN_BARE = " Days on the list: not known."
FTD_ONLY = "Fails to deliver only, not every short position."
NOT_A_PRICE_READ = "A rule date — it says nothing about price."
NOT_ADVICE = "Not advice."
PICK_RUN_TAIL = (" The tag also counts the straight settlement days a name has been on its list and dates day %d: "
                 "after it, %s %s makes a clearing firm buy shares to close out a fail to deliver it carried on every "
                 "one of those days (the buying may come from day %d). %s Bank holidays (%s) are not settlement days "
                 "(%s). A list takes effect at the next open, so the date can be one settlement day later. %s")
_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")   # never strftime("%a") (locale)

_SYMBOL_CELL = re.compile(r"^[A-Z0-9][A-Z0-9 ./\-+$^=#]{0,14}$")
_TRAILER = re.compile(r"^\d{14}$")
_SEP_RUN = re.compile(r"[ ./\-]+")


class Malformed(ValueError):
    """A file that cannot be trusted as a list (never read as an empty one)."""


# ───────────────────────────────────────────── seams
def _mono() -> float:
    return time.monotonic()


def _pause(sec: float) -> None:
    """The ONE pause seam of the backfill — called only BETWEEN two items."""
    time.sleep(sec)


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


def _write_found(coll, src: dict, d: date, got: dict, now_iso: str, *, backfilled: bool = False,
                 skip=frozenset()) -> int:
    """Write one list doc per market of a `found` answer for date d (a raising write propagates). Markets in `skip` —
    those that already hold a doc for d — are not written, so their `fetched_at` stays the first write. Returns the
    number of docs written."""
    key = src["key"]
    wrote = 0
    for mkt, r in got["markets"].items():
        if mkt in skip:
            continue
        n = len(r["symbols"])
        doc = {"_id": "list|%s|%s" % (mkt, d.isoformat()), "kind": "list", "source": key,
               "market": mkt, "exchange": _exchange(src, mkt), "trade_date": d.isoformat(),
               "symbols": list(r["symbols"]), "n": n, "skipped": int(r["skipped"]),
               "file_stamp": r["stamp"], "url": r["url"], "fetched_at": now_iso,
               "confirmed_at": now_iso if n > 0 else None, "revised_at": None}
        if backfilled:
            doc["backfilled"] = True
        coll.replace_one({"_id": doc["_id"]}, doc, upsert=True)
        wrote += 1
    return wrote


def _confirm_zero_row(coll, src: dict, mkt: str, doc: dict, now_iso: str, *, http=None) -> str:
    """[C2] The second read of a zero-row list. Returns "found" after it wrote the confirmation, else the fetch's error
    (or result) word, having written nothing. A raising write propagates."""
    td = _as_date(doc.get("trade_date"))
    r = fetch_market(src, mkt, td, http=http)
    if r["result"] != "found":
        return r.get("error") or r["result"]
    new = dict(doc)
    new["confirmed_at"] = now_iso
    if r["symbols"]:
        new.update({"symbols": list(r["symbols"]), "n": len(r["symbols"]), "skipped": int(r["skipped"]),
                    "file_stamp": r["stamp"], "revised_at": now_iso})
    coll.replace_one({"_id": new["_id"]}, new, upsert=True)
    return "found"


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
                _write_found(coll, src, d, got, now_iso)
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
            _confirm_zero_row(coll, src, mkt, doc, now_iso, http=http)    # a failed re-read writes nothing

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


# ───────────────────────────────────────────── the close-out day's history (2026-11-24)
# In-process write-failure breaker [C2]: a Mongo write that raises stops the history for RS_RETRY_MIN.
_hist = {"blocked_until": None}

_OP_RANK = {"fetch": 0, "confirm": 1}


def _hist_blocked() -> bool:
    until = _hist.get("blocked_until")
    return until is not None and _mono() < until


def _empty_history() -> dict:
    return {"days": {}, "members": {}, "docs": {}, "holes": {}, "ext": {}}


def _members_of(doc) -> Optional[frozenset]:
    """A READ list's names, or None (unconfirmed zero-row, unreadable symbols, anything odd) [C4]."""
    try:
        if not isinstance(doc, dict) or not _believed(doc) or not isinstance(doc.get("symbols"), list):
            return None
        return frozenset(norm_symbol(s) for s in doc["symbols"])
    except Exception:                                          # noqa: BLE001
        return None


def load_history(coll, loaded: dict) -> dict:
    """The window of per-date list docs and hole docs behind each market's newest held list — two `find`s, NO read at
    all when no market holds a list. members[mkt][iso] = the names of a READ list, else None (= not read)."""
    out = _empty_history()
    if coll is None:
        return out
    for _src, mkt, _ex, _f in all_markets():
        held = (loaded.get("lists") or {}).get(mkt)
        as_of = _as_date(held.get("trade_date")) if isinstance(held, dict) else None
        if as_of is None:
            continue
        out["days"][mkt] = RUNS.settlement_days_back(as_of, RS_HIST_SETTLEMENT_DAYS)
    if not out["days"]:
        return out
    since = min(ds[-1] for ds in out["days"].values()).isoformat()
    for doc in coll.find({"kind": "list", "trade_date": {"$gte": since}}):
        if isinstance(doc, dict) and doc.get("market") and doc.get("trade_date"):
            out["docs"][(str(doc["market"]), str(doc["trade_date"]))] = doc
    for doc in coll.find({"kind": HOLE_KIND, "trade_date": {"$gte": since}}):
        if not isinstance(doc, dict) or not doc.get("trade_date"):
            continue
        iso = str(doc["trade_date"])
        if doc.get("op") == "confirm" and doc.get("market"):
            out["holes"][("confirm", str(doc["market"]), iso)] = doc
        elif doc.get("op") == "fetch" and doc.get("source"):
            out["holes"][("fetch", str(doc["source"]), iso)] = doc
    for mkt, days in out["days"].items():
        out["members"][mkt] = {d.isoformat(): _members_of(out["docs"].get((mkt, d.isoformat()))) for d in days}
    # 2026-11-26 (sitrack §3.4): the walked-back run starts still contiguous with the window — ONE bounded find
    for doc in coll.find({"kind": RUNSTART_KIND, "on_through": {"$gte": since}}):
        if isinstance(doc, dict) and doc.get("market") and doc.get("symbol"):
            out["ext"][(str(doc["market"]), str(doc["symbol"]))] = doc
    return out


def _hole_tries(hole) -> int:
    t = hole.get("tries") if isinstance(hole, dict) else None
    return t if isinstance(t, int) and not isinstance(t, bool) else 0


def _hole_due(hole, now_et: datetime) -> bool:
    """The ONE retry rule, fetch and confirm [C2, C3]. An `error` is never final: RS_HIST_MAX_TRIES asks RS_RETRY_MIN
    apart, then one ask every RS_HIST_REASK_MIN. A `missing` is asked RS_HIST_REASK_MIN apart, then final."""
    if not hole:
        return True
    age = _age_min(hole.get("asked_at"), _to_et(now_et))
    if age is None:
        return True
    tries = _hole_tries(hole)
    if hole.get("result") == "missing":
        return tries < RS_HIST_MAX_TRIES and age >= RS_HIST_REASK_MIN
    if tries < RS_HIST_MAX_TRIES:
        return age >= RS_RETRY_MIN
    return age >= RS_HIST_REASK_MIN


def _hole_source(key: tuple) -> Optional[str]:
    if key[0] == "fetch":
        return key[1]
    for src, mkt, _e, _f in all_markets():
        if mkt == key[1]:
            return src["key"]
    return None


def history_todo(loaded: dict, hist: dict, now_et: datetime) -> list:
    """Pure. ("fetch", src, d) and ("confirm", src, mkt, d) items — never-asked before any re-ask, every fetch before
    every confirm, newest date first, registry order inside a date. A source with a fresh `error` hole (fetch or
    confirm, asked under RS_RETRY_MIN ago) contributes nothing."""
    now_et = _to_et(now_et)
    days = hist.get("days") or {}
    docs = hist.get("docs") or {}
    holes = hist.get("holes") or {}
    lists = loaded.get("lists") or {}
    cooling = set()
    for key, hole in holes.items():
        if not isinstance(hole, dict) or hole.get("result") == "missing":
            continue
        age = _age_min(hole.get("asked_at"), now_et)
        if age is not None and age < RS_RETRY_MIN:
            cooling.add(_hole_source(key))
    ranked = []
    for si, src in enumerate(SOURCES):
        key = src["key"]
        if key in cooling:
            continue
        mkts = [m for m, _e, _f in source_markets(src)]
        union = sorted({d for m in mkts for d in days.get(m) or []}, reverse=True)
        for d in union:
            iso = d.isoformat()
            if all((m, iso) in docs for m in mkts):
                continue
            hole = holes.get(("fetch", key, iso))
            if _hole_due(hole, now_et):
                ranked.append(((1 if hole else 0, _OP_RANK["fetch"], -d.toordinal(), si, 0), ("fetch", src, d)))
        for mi, mkt in enumerate(mkts):
            newest = (lists.get(mkt) or {}).get("trade_date")
            for d in days.get(mkt) or []:
                iso = d.isoformat()
                doc = docs.get((mkt, iso))
                if not doc or iso == newest or doc.get("confirmed_at"):
                    continue
                try:
                    if int(doc.get("n") or 0) != 0:
                        continue
                except (TypeError, ValueError):
                    continue
                age = _age_min(doc.get("fetched_at"), now_et)
                if age is None or age < RS_RETRY_MIN:
                    continue
                hole = holes.get(("confirm", mkt, iso))
                if _hole_due(hole, now_et):
                    ranked.append(((1 if hole else 0, _OP_RANK["confirm"], -d.toordinal(), si, mi),
                                   ("confirm", src, mkt, d)))
    ranked.sort(key=lambda kv: kv[0])
    return [item for _k, item in ranked]


def _write_hole(coll, op: str, src: dict, mkt: Optional[str], d: date, result: str, error, prev,
                now_iso: str) -> None:
    iso = d.isoformat()
    hid = ("%s|%s|%s" % (HOLE_KIND, src["key"], iso) if op == "fetch"
           else "%s|confirm|%s|%s" % (HOLE_KIND, mkt, iso))
    coll.replace_one({"_id": hid}, {
        "_id": hid, "kind": HOLE_KIND, "op": op, "source": src["key"], "market": mkt, "trade_date": iso,
        "result": result, "error": error, "tries": _hole_tries(prev) + 1, "asked_at": now_iso}, upsert=True)


def _trip_breaker(exc) -> None:
    _hist["blocked_until"] = _mono() + RS_RETRY_MIN * 60
    log.warning("reg_sho: history write failed, history paused %d min: %s", RS_RETRY_MIN, type(exc).__name__)


def backfill_history(coll, now_et: Optional[datetime] = None, *, http=None) -> dict:
    """One backfill round of the per-date history. {"calls", "found", "confirmed", "holes", "seconds"}. Never raises.
    At most ONE failing item per source per round; stops starting items at RS_HIST_MAX_GETS calls or the
    RS_HIST_BUDGET_SEC deadline; a raising Mongo write ends the round and trips the breaker."""
    t0 = _mono()
    out = {"calls": 0, "found": 0, "confirmed": 0, "holes": 0, "seconds": 0.0}
    if coll is None or _hist_blocked():
        return out
    now_et = _to_et(now_et)
    now_iso = _utc_iso(now_et)
    calls = {"n": 0}
    try:
        base = _resolve_http(http)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("reg_sho: history has no http client: %s", type(exc).__name__)
        return out

    def counted(url, **kw):
        calls["n"] += 1
        return base(url, **kw)

    try:
        loaded = load(coll)
        hist = load_history(coll, loaded)
        todo = history_todo(loaded, hist, now_et)
        deadline = t0 + RS_HIST_BUDGET_SEC
        skip = set()
        started = False
        for item in todo:
            op, src = item[0], item[1]
            key = src["key"]
            if key in skip:
                continue
            if calls["n"] >= RS_HIST_MAX_GETS or _mono() > deadline:
                break
            if started:
                _pause(RS_HIST_PAUSE_SEC)
            started = True
            if op == "fetch":
                d = item[2]
                iso = d.isoformat()
                got = fetch_source(src, d, http=counted)
                prev = hist["holes"].get(("fetch", key, iso))
                try:
                    if got["result"] == "found":
                        held = frozenset(m for m, _e, _f in source_markets(src) if (m, iso) in hist["docs"])
                        _write_found(coll, src, d, got, now_iso, backfilled=True, skip=held)
                        out["found"] += 1
                    else:
                        res = "missing" if got["result"] == "missing" else "error"
                        _write_hole(coll, "fetch", src, None, d, res,
                                    None if res == "missing" else (got.get("error") or "error"), prev, now_iso)
                        out["holes"] += 1
                        if res == "error":
                            skip.add(key)
                except Exception as exc:                       # noqa: BLE001
                    _trip_breaker(exc)
                    break
            else:
                mkt, d = item[2], item[3]
                iso = d.isoformat()
                prev = hist["holes"].get(("confirm", mkt, iso))
                try:
                    word = _confirm_zero_row(coll, src, mkt, hist["docs"][(mkt, iso)], now_iso, http=counted)
                    if word == "found":
                        out["confirmed"] += 1
                    else:
                        _write_hole(coll, "confirm", src, mkt, d, "error", word, prev, now_iso)
                        out["holes"] += 1
                        skip.add(key)
                except Exception as exc:                       # noqa: BLE001
                    _trip_breaker(exc)
                    break
    except Exception as exc:                                   # noqa: BLE001
        log.warning("reg_sho: history round failed: %s", type(exc).__name__)
    out["calls"] = calls["n"]
    out["seconds"] = round(_mono() - t0, 3)
    return out


def _history_view(coll, loaded: dict, now_et: datetime) -> tuple:
    """(hist, todo, ok) for the read — ONE guard [C4]: any exception → the empty history, no todo, ok False."""
    if coll is None:
        return _empty_history(), [], True
    try:
        hist = load_history(coll, loaded)
        todo = [] if _hist_blocked() else history_todo(loaded, hist, now_et)
        return hist, todo, True
    except Exception as exc:                                   # noqa: BLE001
        log.warning("reg_sho: history read failed, day counts unknown: %s", type(exc).__name__)
        return _empty_history(), [], False


def _window_run(norm: str, mkt: str, hist: dict) -> dict:
    """The run read from the window's lists alone (`reg_sho_runs.run_for`)."""
    try:
        days = (hist.get("days") or {}).get(mkt)
        if not days:
            return RUNS.unknown_block()
        return RUNS.run_for(norm, days, (hist.get("members") or {}).get(mkt) or {})
    except Exception as exc:                                   # noqa: BLE001
        log.warning("reg_sho: run for %s failed: %s", norm, type(exc).__name__)
        return RUNS.unknown_block()


def _ext_of(hist: dict, mkt: str, norm: str) -> Optional[dict]:
    ext = (hist.get("ext") or {}).get((mkt, norm))
    return ext if isinstance(ext, dict) else None


def _run_block(norm: str, mkt: str, hist: dict) -> dict:
    """The served run: the window's run, read past the window by a usable runstart doc (2026-11-26)."""
    run = _window_run(norm, mkt, hist)
    try:
        return RUNS.extend_run(run, _ext_of(hist, mkt, norm))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("reg_sho: run extension for %s failed: %s", norm, type(exc).__name__)
        return run


def _closeout_block(hist: dict, todo: list, ok: bool) -> dict:
    out = {"rule": RUNS.REG_SHO_NAME + " " + RUNS.REG_SHO_CLOSEOUT_RULE,
           "rule_days": RUNS.REG_SHO_CLOSEOUT_SETTLEMENT_DAYS, "first_buy_day": RUNS.first_buy_day(),
           "ok": bool(ok), "history": None}
    if not ok:
        return out
    try:
        read, not_read = {}, {}
        for mkt, days in (hist.get("days") or {}).items():
            mem = (hist.get("members") or {}).get(mkt) or {}
            isos = [d.isoformat() for d in days]
            read[mkt] = sum(1 for i in isos if mem.get(i) is not None)
            not_read[mkt] = [i for i in isos if mem.get(i) is None][:RS_HIST_NOT_READ_MAX]
        out["history"] = {"window_days": RS_HIST_SETTLEMENT_DAYS, "read": read, "not_read": not_read,
                          "pending": bool(todo)}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("reg_sho: closeout block failed: %s", type(exc).__name__)
        out["ok"] = False
    return out


# ───────────────────────────────────────────── the run's first day, read past the window (2026-11-26, sitrack §3.4)
# Only names a caller ASKED about through payload(check=…) are walked. The asks live in this process (never in Mongo):
# payload stays "Mongo reads only". An API restart empties them; the next card read refills them.
_asks_lock = threading.Lock()
_asks = {"seq": 0, "items": {}}                  # {(mkt, norm): (monotonic seconds, seq)}


def _note_asks(pairs) -> None:
    """Remember asked (mkt, norm) pairs, newest last; only the newest RS_CHECK_MAX are kept. Never stored."""
    with _asks_lock:
        items = _asks["items"]
        for p in pairs or ():
            try:
                mkt, norm = str(p[0]), str(p[1])
            except Exception:                                  # noqa: BLE001
                continue
            if not mkt or not norm:
                continue
            _asks["seq"] += 1
            items.pop((mkt, norm), None)
            items[(mkt, norm)] = (_mono(), _asks["seq"])
        if len(items) > RS_CHECK_MAX:
            keep = sorted(items.items(), key=lambda kv: kv[1], reverse=True)[:RS_CHECK_MAX]
            _asks["items"] = dict(keep)


def _asked() -> list:
    """[(mkt, norm)], newest ask first."""
    with _asks_lock:
        return [k for k, _v in sorted(_asks["items"].items(), key=lambda kv: kv[1], reverse=True)]


def ext_due(run: dict, ext, now_et) -> bool:
    """Is there still work for this name? The ONE definition of done (spec sitrack §3.4):
    no usable ext → due · `start` set → resolved · blocked "cap" → done for good · blocked "missing" / "error" → the
    hole rule as it stands (`_hole_due`) · neither (a round ran out of budget) → due."""
    if not RUNS.ext_usable(run, ext):
        return True
    if ext.get("start"):
        return False
    blocked = ext.get("blocked")
    if blocked == "cap":
        return False
    if blocked in ("missing", "error"):
        return _hole_due({"result": blocked, "tries": ext.get("tries"), "asked_at": ext.get("asked_at")}, now_et)
    return True


def _runstart_id(mkt: str, norm: str) -> str:
    return "%s|%s|%s" % (RUNSTART_KIND, mkt, norm)


def _list_on(coll, mkt: str, d: date) -> Optional[dict]:
    return coll.find_one({"kind": "list", "market": mkt, "trade_date": d.isoformat()}, sort=_SORT)


def _write_runstart(coll, nm: dict, now_iso: str) -> None:
    prev = nm["prev"] or {}
    blocked = nm["blocked"]
    tries = 0
    if blocked in ("missing", "error"):
        same = prev.get("blocked") == blocked and prev.get("blocked_on") == _iso_or_none(nm["blocked_on"])
        tries = (_hole_tries(prev) if same else 0) + 1
    doc = {"_id": _runstart_id(nm["mkt"], nm["norm"]), "kind": RUNSTART_KIND, "market": nm["mkt"],
           "symbol": nm["norm"], "start": _iso_or_none(nm["start"]), "on_from": nm["on_from"].isoformat(),
           "on_through": nm["through"].isoformat(), "blocked": blocked, "blocked_on": _iso_or_none(nm["blocked_on"]),
           "tries": tries, "asked_at": now_iso}
    coll.replace_one({"_id": doc["_id"]}, doc, upsert=True)


def _iso_or_none(d) -> Optional[str]:
    return d.isoformat() if d else None


def extend_runs(coll, now_et: Optional[datetime] = None, *, http=None, calls_left: Optional[int] = None) -> dict:
    """One round of the run-start walk for the ASKED names whose window run is `passed_open` (no hole) and
    `ext_due`. {"calls", "names", "resolved", "blocked", "seconds"}. Never raises.
    Markets in registry order (Nasdaq first). Per market the walk reads one settlement day at a time, older than the
    oldest day each open name was verified on, WHILE an asked name of that market is still open: the stored list doc
    when held, else ONE fetch (`fetch_source` + `_write_found(..., backfilled=True)`). A READ list lacking a name
    resolves it; a `missing` / `error` answer blocks every still-open name of the market at that date;
    RS_RUN_START_MAX_SETTLEMENT_DAYS days verified → blocked "cap". A market stops the moment its asked names are all
    resolved or blocked; a market with no open asked name makes no call. `calls_left` (default RS_HIST_MAX_GETS) bounds
    the outside calls; a raising Mongo write trips the history breaker and ends the round."""
    t0 = _mono()
    out = {"calls": 0, "names": 0, "resolved": 0, "blocked": 0, "seconds": 0.0}
    if coll is None or _hist_blocked():
        return out
    asked = _asked()
    if not asked:
        return out
    now_et = _to_et(now_et)
    now_iso = _utc_iso(now_et)
    left = RS_HIST_MAX_GETS if calls_left is None else max(0, int(calls_left))
    calls = {"n": 0}
    try:
        base = _resolve_http(http)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("reg_sho: run-start walk has no http client: %s", type(exc).__name__)
        return out

    def counted(url, **kw):
        calls["n"] += 1
        return base(url, **kw)

    try:
        loaded = load(coll)
        hist = load_history(coll, loaded)
        by_mkt = {}
        for mkt, norm in asked:
            run = _window_run(norm, mkt, hist)
            if run.get("state") != "passed_open" or run.get("missing") is not None:
                continue
            ext = _ext_of(hist, mkt, norm)
            usable = RUNS.ext_usable(run, ext)
            if not ext_due(run, ext, now_et):
                if usable and str(ext.get("on_through")) < str(run["through"]):
                    moved = dict(ext)
                    moved["on_through"] = run["through"]           # contiguous again: one write, no call
                    try:
                        coll.replace_one({"_id": _runstart_id(mkt, norm)}, moved, upsert=True)
                    except Exception as exc:                   # noqa: BLE001
                        _trip_breaker(exc)
                        return out
                continue
            by_mkt.setdefault(mkt, []).append({
                "mkt": mkt, "norm": norm, "prev": ext if usable else None,
                "on_from": _as_date(ext.get("on_from") if usable else run["window_from"]),
                "through": _as_date(run["through"]), "start": None, "blocked": None, "blocked_on": None})
        deadline = t0 + RS_HIST_BUDGET_SEC
        started = False
        stop = False
        for src, mkt, _ex, _f in all_markets():
            names = by_mkt.get(mkt)
            if stop or not names:
                continue
            out["names"] += len(names)
            open_ = list(names)
            while open_:
                for nm in list(open_):
                    if RUNS.settlement_days_between(nm["on_from"], nm["through"]) >= RS_RUN_START_MAX_SETTLEMENT_DAYS:
                        nm["blocked"] = "cap"
                        open_.remove(nm)
                if not open_:
                    break
                nxt = {id(nm): RUNS.prev_settlement_day(nm["on_from"] - timedelta(days=1)) for nm in open_}
                d = max(nxt.values())
                engaged = [nm for nm in open_ if nxt[id(nm)] == d]
                held = _list_on(coll, mkt, d)
                members = _members_of(held)
                word = None
                if members is None:
                    if calls["n"] + len(source_markets(src)) > left or _mono() > deadline:
                        stop = True
                        break
                    if started:
                        _pause(RS_HIST_PAUSE_SEC)
                    started = True
                    if held is not None:
                        age = _age_min(held.get("fetched_at"), now_et)
                        if age is not None and age >= RS_RETRY_MIN:
                            got = _confirm_zero_row(coll, src, mkt, held, now_iso, http=counted)
                            members = _members_of(_list_on(coll, mkt, d)) if got == "found" else None
                        word = None if members is not None else "error"
                    else:
                        got = fetch_source(src, d, http=counted)
                        if got["result"] == "found":
                            skip = frozenset(m for m, _e, _f in source_markets(src)
                                             if m != mkt and _list_on(coll, m, d) is not None)
                            _write_found(coll, src, d, got, now_iso, backfilled=True, skip=skip)
                            members = _members_of(_list_on(coll, mkt, d))
                            word = None if members is not None else "error"   # an unconfirmed zero-row list
                        else:
                            word = "missing" if got["result"] == "missing" else "error"
                if word is not None:
                    for nm in open_:                                    # every still-open name of the market
                        nm["blocked"], nm["blocked_on"] = word, d
                    open_ = []
                    break
                for nm in engaged:
                    if nm["norm"] in members:
                        nm["on_from"] = d
                    else:
                        nm["start"] = nm["on_from"]                     # the READ list before it lacks the name
                        open_.remove(nm)
            for nm in names:
                _write_runstart(coll, nm, now_iso)
                if nm["start"] is not None:
                    out["resolved"] += 1
                elif nm["blocked"] is not None:
                    out["blocked"] += 1
    except Exception as exc:                                   # noqa: BLE001
        _trip_breaker(exc)
    out["calls"] = calls["n"]
    out["seconds"] = round(_mono() - t0, 3)
    return out


# One worker at a time (bounce_room.queue_ondemand shape) + a floor between starts [C7].
_bg_lock = threading.Lock()
_bg = {"running": False, "last_start": None, "thread": None}


def _worker_running() -> bool:
    with _bg_lock:
        return bool(_bg["running"])


def _floor_waiting() -> bool:
    """A worker was started less than RS_KICK_MIN_SEC ago (the next kick will be refused until then)."""
    with _bg_lock:
        last = _bg["last_start"]
    return last is not None and _mono() - last < RS_KICK_MIN_SEC


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
            try:
                refresh_due(coll, now_et, http=http)
            except Exception as exc:                           # noqa: BLE001
                log.warning("reg_sho: worker failed: %s", type(exc).__name__)
            used = 0
            try:                                               # AFTER refresh_due, never inside it
                used = int((backfill_history(coll, now_et, http=http) or {}).get("calls") or 0)
            except Exception as exc:                           # noqa: BLE001
                log.warning("reg_sho: history worker failed: %s", type(exc).__name__)
            try:                                               # AFTER backfill_history: ONE call budget a round
                extend_runs(coll, now_et, http=http, calls_left=max(0, RS_HIST_MAX_GETS - used))
            except Exception as exc:                           # noqa: BLE001
                log.warning("reg_sho: run-start worker failed: %s", type(exc).__name__)
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


def _dow_md(iso: str) -> str:
    """"Fri 11/27" — weekday from a fixed tuple, never strftime("%a") (locale)."""
    d = _as_date(iso)
    return "%s %s" % (_DOW[d.weekday()], SR._md(iso))


def _days_word(n: int) -> str:
    return "day" if n == 1 else "days"


def _rule_sentence() -> str:
    return RULE_SENTENCE % (RUNS.REG_SHO_CLOSEOUT_SETTLEMENT_DAYS, RUNS.REG_SHO_CLOSEOUT_RULE)


def _rule_204_sentence() -> str:
    rule = RUNS.REG_SHO_CLOSEOUT_SETTLEMENT_DAYS
    return RULE_204_SENTENCE % (RUNS.REG_SHO_204_RULE, RUNS.REG_SHO_204_SETTLEMENT_DAYS,
                                RUNS.REG_SHO_204_LONG_MM_SETTLEMENT_DAYS, rule, RUNS.REG_SHO_144_RULE,
                                RUNS.REG_SHO_144_SETTLEMENT_DAYS, rule)


def _run_words(exchange: str, run: dict) -> tuple:
    """(chip tail, short or None, label tail, title tail) for one run block — raises on a malformed block."""
    rule = RUNS.REG_SHO_CLOSEOUT_SETTLEMENT_DAYS
    st = run["state"]
    n = int(run["days"])
    tails = " " + _rule_204_sentence() + " " + FTD_ONLY + " " + NOT_A_PRICE_READ + " " + NOT_ADVICE
    if st in ("counting", "reached"):
        rd = RUN_DAY % (n, rule)
        d13 = _dow_md(run["day13"])
        late = LATE_ALT % _dow_md(run["day13_late"])
        bw = BUY_WINDOW % (RUNS.first_buy_day(), _dow_md(run["day11"]), RUNS.REG_SHO_STAFF_FAQ)
        short = SHORT_RUN % (GLYPH, CLOSEOUT_WORD, d13, rd)
        if st == "counting":
            tail = RUN_TAIL % (rd, CLOSEOUT_WORD, d13, IF_STAYS)
            title = TITLE_RUN % (n, _days_word(n), SR._md(run["start"]), rule, d13, IF_STAYS, late,
                                 _rule_sentence(), bw)
        else:
            tail = RUN_TAIL_REACHED % (rd, CLOSEOUT_WORD, d13)
            title = TITLE_RUN_REACHED % (n, SR._md(run["start"]), rule, d13, late, _rule_sentence(), bw)
        return tail, short, tail, title + tails
    if st == "passed":
        rd = RUN_DAY_PAST % n
        d13 = _dow_md(run["day13"])
        late = LATE_ALT % _dow_md(run["day13_late"])
        over = n - rule
        title = TITLE_RUN_PAST % (n, SR._md(run["start"]), rule, d13, late, over, _days_word(over),
                                  _rule_sentence(), REG_SHO_CONSEC_SETTLEMENT_DAYS)
        return (CHIP_RUN_PAST % (rd, CLOSEOUT_WORD, d13), SHORT_RUN_PAST % (GLYPH, CLOSEOUT_WORD, d13, rd),
                LABEL_RUN_PAST % (rd, CLOSEOUT_WORD, d13), title + tails)
    if st == "passed_open":
        rd = RUN_DAY_OPEN % n
        if run.get("missing") is None and run.get("read_back_to"):
            blocked = run.get("blocked")
            if blocked is None:
                mid = OPEN_READ_NOT_YET
            elif blocked in ("missing", "error"):
                mid = OPEN_READ_FAILED
            elif blocked == "cap":
                mid = OPEN_READ_CAP % RS_RUN_START_MAX_SETTLEMENT_DAYS
            else:
                raise ValueError("blocked %r" % (blocked,))
            back = SR._md(run["read_back_to"])
            title = TITLE_RUN_OPEN_READ % (back, n, rule, back, mid, _rule_sentence())
        elif run.get("missing") is None:
            title = TITLE_RUN_OPEN_WINDOW % (n, SR._md(run["window_from"]), rule, n, _rule_sentence())
        else:
            title = TITLE_RUN_OPEN_HOLE % (n, rule, exchange, SR._md(run["missing"]), _rule_sentence())
        return (CHIP_RUN_OPEN % (rd, CLOSEOUT_WORD), SHORT_RUN_OPEN % (GLYPH, CLOSEOUT_WORD, rd),
                LABEL_RUN_OPEN % (rd, CLOSEOUT_WORD), title + tails)
    if st != "unknown":
        raise ValueError("run state %r" % (st,))
    title = (TITLE_RUN_UNKNOWN % (exchange, SR._md(run["missing"])) if run.get("missing")
             else TITLE_RUN_UNKNOWN_BARE)
    return RUN_UNKNOWN, None, RUN_UNKNOWN, title + " " + NOT_ADVICE


def past_closeout_text(run) -> Optional[str]:
    """"🔒 day 6 past close-out" for a run block (`reg_sho_runs.run_for`) still on its list past its close-out day:
    the settlement days on the list beyond `RUNS.REG_SHO_CLOSEOUT_SETTLEMENT_DAYS` (read at call time, by name).
    `passed` → the exact form; `passed_open` (the run's first day not known) → the "+" form; anything else
    (counting, reached, unknown, junk, no day past) → None. Never raises."""
    try:
        if not isinstance(run, dict):
            return None
        n = run.get("days")
        if isinstance(n, bool) or not isinstance(n, int):
            return None
        over = n - RUNS.REG_SHO_CLOSEOUT_SETTLEMENT_DAYS
        if over <= 0:
            return None
        st = run.get("state")
        if st == "passed":
            return PAST_CLOSEOUT_TEXT % (GLYPH, over, CLOSEOUT_WORD)
        if st == "passed_open":
            return PAST_CLOSEOUT_OPEN_TEXT % (GLYPH, over, CLOSEOUT_WORD)
        return None
    except Exception as exc:                                   # noqa: BLE001
        log.warning("reg_sho: past close-out words failed: %s", type(exc).__name__)
        return None


def tag_block(sym: str, mkt: str, exchange: str, as_of: str, stale: bool, run: Optional[dict] = None) -> dict:
    """The four served strings. `run=None` ≡ RUNS.unknown_block(); a run block whose words cannot be built reads
    unknown [C4]. The stale tails stay LAST."""
    md = SR._md(as_of)
    tail = STALE_WORD if stale else ""
    try:
        words = _run_words(exchange, run if run is not None else RUNS.unknown_block())
    except Exception as exc:                                   # noqa: BLE001
        log.warning("reg_sho: run words for %s failed: %s", sym, type(exc).__name__)
        words = _run_words(exchange, RUNS.unknown_block())
    chip_tail, short, label_tail, title_tail = words
    title = TITLE_TEXT % (GLYPH, TAG_WORDS, sym, exchange, as_of, "{:,}".format(REG_SHO_MIN_FTD_SHARES),
                          REG_SHO_MIN_PCT_SHARES_OUT, REG_SHO_CONSEC_SETTLEMENT_DAYS, REG_SHO_RULE,
                          HONESTY_NOTE, NOT_A_SIGNAL) + title_tail
    if stale:
        title += STALE_TITLE % md
    return {"state": "on", "symbol": sym, "market": mkt, "exchange": exchange, "as_of": as_of, "stale": bool(stale),
            "chip": (CHIP_TEXT % (GLYPH, TAG_WORDS, md)) + chip_tail + tail,
            "short": (short if short is not None else SHORT_TEXT % (GLYPH, TAG_WORDS, md)) + tail,
            "label": (LABEL_TEXT % (GLYPH, TAG_WORDS, exchange, md)) + label_tail + tail,
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


def _due_asks(check, items: dict, hist: dict, now_et: datetime) -> tuple:
    """(noted, due) over the `check` names (first RS_CHECK_MAX) whose WINDOW run (`_window_run`, the one
    `extend_runs` reads — a resolved name's served run reads `passed`) is `passed_open` with no window hole.
    `noted` = every such name, the not-due ones first so the due ones are the newest asks (the set keeps the newest
    RS_CHECK_MAX); `due` = the `ext_due` subset, the only names that may start a worker. A resolved name is noted too
    (refix 2026-11-26): after an API restart empties the ask set, the worker's round can still move its `on_through`
    up (one write, no call) — else the doc falls behind the window and the tag drops back to `day 30+`.
    Pure over the read's own blocks; nothing while the history breaker is open. Never raises."""
    rest, due = [], []
    try:
        if _hist_blocked():
            return [], []
        seen = set()
        for s in list(check):
            k = str(s or "").strip().upper()
            if not k or k in seen:
                continue
            if len(seen) >= RS_CHECK_MAX:
                break
            seen.add(k)
            blk = items.get(norm_symbol(k))
            if not isinstance(blk, dict):
                continue
            pair = (blk["market"], blk["symbol"])
            run = _window_run(pair[1], pair[0], hist)          # the window's run, as `extend_runs` reads it
            if not isinstance(run, dict) or run.get("state") != "passed_open" or run.get("missing") is not None:
                continue
            if pair in rest or pair in due:
                continue
            (due if ext_due(run, _ext_of(hist, pair[0], pair[1]), now_et) else rest).append(pair)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("reg_sho: asked names could not be read: %s", type(exc).__name__)
        return [], []
    return rest + due, due


def payload(db=_DEFAULT, now: Optional[datetime] = None, *, check=None, kick: bool = True, http=None) -> dict:
    """THE served read — Mongo reads only, never an outside call."""
    now_et = _to_et(now)
    if db is _DEFAULT:
        db = SIC._get_db()
    coll = db[RS_COLL] if db is not None else None
    loaded = load(coll) if coll is not None else {"lists": {}, "states": {}}
    hist, todo, hist_ok = _history_view(coll, loaded, now_et)

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
            run = _run_block(norm, mkt, hist)
            blk = tag_block(norm, mkt, exchange, v["as_of"], v["stale"], run=run)
            blk["run"] = run
            for k in alias_keys(norm):
                items.setdefault(k, blk)

    # 2026-11-26 (sitrack §3.4): the asked names — noted in-process only
    # every checked passed_open name is noted (a resolved one still needs its on_through moved up); only a DUE one kicks
    noted, asks = (_due_asks(check, items, hist, now_et) if (kick and check is not None and coll is not None and hist_ok)
                   else ([], []))

    refreshing = False                                         # the latest lists — the fault line reads this one
    hist_refreshing = False
    if coll is not None:
        started = False
        tried = False
        if kick and (any(is_due(src, loaded, now_et) for src in SOURCES) or todo):
            tried = True
            started = kick_refresh(coll, now_et if now is not None else None, http=http)
        if noted:
            _note_asks(noted)
        if asks:
            if not tried:                                      # ONE more attempt; the running flag and floor decide
                started = kick_refresh(coll, now_et if now is not None else None, http=http)
        refreshing = bool(started or _worker_running())
        # [C2] only while a worker can make progress: running, just started, or the floor will let the next one start
        hist_refreshing = bool(kick and (todo or asks) and (started or _worker_running() or _floor_waiting()))

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
        "refreshing": bool(refreshing or hist_refreshing),
        "retry_after_sec": (RS_RETRY_AFTER_SEC if refreshing else (RS_KICK_MIN_SEC if hist_refreshing else None)),
        "closeout": _closeout_block(hist, todo, hist_ok),
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
            "refreshing": False, "retry_after_sec": None, "closeout": None}


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
               REG_SHO_CONSEC_SETTLEMENT_DAYS, REG_SHO_RULE, _and_list(names), ", ".join(stock), HONESTY_NOTE)
            + PICK_RUN_TAIL % (RUNS.REG_SHO_CLOSEOUT_SETTLEMENT_DAYS, RUNS.REG_SHO_NAME, RUNS.REG_SHO_CLOSEOUT_RULE,
                               RUNS.first_buy_day(), _rule_204_sentence(), " and ".join(RUNS.BANK_HOLIDAYS_OPEN_MARKET),
                               RUNS.REG_SHO_SETTLEMENT_DAY_RULE, NOT_A_PRICE_READ))
