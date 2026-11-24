"""⛔ SSR — SEC Rule 201 short-sale restriction tag (2026-11-23).

THE ASK (Ajay 2026-11-23, verbatim)
  "No shorting at the bid (SEC short-sale restriction)

   Can we check or this for other stocks too?"

What this module is: the cited rule, the COMPUTED read and the ONE served read
behind the ⛔ tag. The official exchange lists live in `short_interest.ssr_lists`
(Nasdaq + NYSE Group) and the session's dividends and splits in
`short_interest.ssr_corp`; both are read here through the `lists=` / `corp=`
seams only (FROZEN interfaces, spec §3.3 / §3.4a). Every word the front end
prints is built here; it types none.

  * `record_pass` — the ONE writer. Rides the Gajjala 5-minute pass (`Deps.ssr`)
    with ZERO outside calls: for the names on his cards the 1-minute bars decide;
    for every other US stock the whole-market snapshot the pass already loads
    gives a REGULAR-HOURS trigger. The first pass at/after the close-confirm
    clock writes `judged|<date>` once (the names proven OFF + the unjudged).
  * `payload` — `GET /short-interest/ssr?symbols=A,B,C`. Mongo reads only.
    Official wins. A computed tag says "computed", shows only until both
    exchange lists are complete, and is withheld on a dividend or split day.
    Anything unproven reads `unknown`, never `off`.

DISPLAY ONLY. Nothing here gates, sorts, sizes, pushes or enters a lane.
UNMEASURED. Docs: docs/short_interest/ssr_rule_201_2026_11_24.md.

Python 3.9-safe (the host venv): no `X | None` at runtime, no `match`.
"""
from __future__ import annotations

import logging
import math
import re
import threading
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from short_interest import borrow as BR
from short_interest import client as SIC
from short_interest import read as SR
from short_interest import reg_sho as RS

log = logging.getLogger("short_interest.ssr")

# ───────────────────────────────────────────── constants (spec §3.1)
GLYPH = "⛔"                                   # MINE (HIS CALL 1)
TAG = "SSR"
TAG_WORDS = "no shorting at the bid"           # HIS words, 2026-11-23
KIND = "ssr_rule_201"                          # payload discriminator
API_PATH = "/short-interest/ssr"
SSR_RULE = "SEC Rule 201 of Regulation SHO (17 CFR 242.201)"
SSR_FAQ_URL = "https://www.sec.gov/divisions/marketreg/rule201faq.htm"
SSR_TRIGGER_DROP_PCT = 10          # 242.201(b)(1)(i): "decreased by 10% or more from the covered security's closing price … as of the end of regular trading hours on the prior day"
SSR_FOLLOWING_TRADING_DAYS = 1     # 242.201(b)(1)(ii): "for the remainder of the day and the following day"; FAQ 2.1: "the next trading day"
SSR_REGULAR_HOURS_ONLY = True      # FAQ 1.1 + 2.1: only trades in regular trading hours trigger it
# engineering — MINE, none is a trading threshold (HIS CALL 13)
SSR_STALE_PASSES = 3               # × GC.PASS_CADENCE_SEC: how old a followed name's last read (`names.<SYM>.at`) may be in RTH before "off" reads "unknown"
SSR_KEEP_SEC = 300                 # served keep_sec (one pass cadence)
SSR_FORMS = ("label", "chip", "short")
SSR_UNKNOWN_FORMS = ("label",)     # HIS CALL 5 — where an UNKNOWN name prints
SSR_QUIET_WHYS = ("awaiting_first_scan", "computed_only")   # unknown, but nothing is drawn
SSR_COMPUTED_UNTIL_LISTS_COMPLETE = True   # HIS CALL 4 — the ONE switch: a computed tag comes off once both exchange lists are complete without the name [C1a]
MAP_MAX_SYMBOLS = SR.MAP_MAX_SYMBOLS
_PRICE_DP = 6                      # float-noise rounding of the edge compare, not a rule

_ET = ZoneInfo("America/New_York")
_DEFAULT = object()                # "resolve the house Mongo handle"; None means ONLY "Mongo is down"

# ───────────────────────────────────────────── words (spec §3.7; served — the FE types none)
CHIP_TEXT = "%s %s · %s · thru %s"            # ⛔ SSR · no shorting at the bid · thru Tue 11/24      — 🚩 / 🧪 cards
SHORT_TEXT = "%s %s thru %s"                   # ⛔ SSR thru 11/24                                     — 👀 tile head (M/D only)
LABEL_TEXT = "%s %s on · %s · through %s · %s" # ⛔ SSR on · no shorting at the bid · through Tue 11/24 · Nasdaq list   — 🎾 card
COMPUTED_TAIL = " · computed"                   # appended to chip and short when source == "computed"
LABEL_SRC_OFFICIAL = "%s list"                  # Nasdaq list / NYSE list / NYSE American list / NYSE Arca list
LABEL_SRC_COMPUTED = "computed from the house's bars"
UNKNOWN_LABEL = "%s %s not read"                # ⛔ SSR not read
TITLE_ON = ("%s %s — %s is under the SEC short-sale restriction: a short sale must be priced above the best bid "
            "(no shorting at the bid). Holders can still sell at the bid. %s In force through %s, after-hours "
            "included; off from %s.%s %s%s %s")
TRIG_OFFICIAL = "Triggered %s at %s ET%s — %s short sale circuit breaker list, file stamped %s."
DROP_CLAUSE = " at %s vs the prior close %s"                                   # −12.4% vs 4.23 ; omitted without a computed number
TRIG_MINUTE = ("Triggered %s in the %s ET minute at %s vs the prior close %s — computed here from the house's "
               "1-minute bars; %s.")
TRIG_SEEN = ("Triggered %s (first seen by the 5-minute scan at %s ET; day low %s vs the prior close %s) — computed "
             "here from the snapshot's day low; %s.")
NOT_ON_LIST_YET = "the exchange lists are not complete for that day yet — this tag comes off if they do not carry it"
NOT_ON_ANY_LIST = "it is on neither the Nasdaq nor the NYSE Group list read"   # an ITEM word only when SSR_COMPUTED_UNTIL_LISTS_COMPLETE is False
RETRIGGER_TEXT = " Also triggered %s — the newer trigger extends it."
HALF_DAY_TEXT = " %s is a half day (regular close %s ET)."
CONFLICT_OFFICIAL_WINS = " The house's bars did not show a %d%% drop (day low %s vs the prior close %s) — the exchange's list decides."
CONFLICT_OFFICIAL_WINS_BARE = " The house's bars did not show a %d%% drop — the exchange's list decides."   # no house numbers on file (a name the scan judged off without following it)
RULE_TEXT = ("The rule (%s): a drop of %d%% or more from the prior day's close during regular hours starts it for "
             "the rest of that day and the next trading day; a new %d%% drop on that next day extends it. ")
PRIOR_CLOSE_NOTE = ("The prior close is the data provider's daily close, which is not always the listing exchange's "
                    "official close. ")                                      # computed sources only
UNKNOWN_TITLE = "%s %s could not be checked for %s: %s. A missing tag does not mean the restriction is off. %s"
WHY_WORDS = {"no_prior_close": "no prior close on file", "no_day_bar": "no regular-session bar today yet",
             "price_suspect": "the price data looks split-adjusted or shifted",
             "not_followed": "the 5-minute scan does not follow this name",
             "scan_stale": "the 5-minute scan has not read the market since %s ET", "no_final_read": "no complete read of %s",
             "awaiting_first_scan": "waiting for the first scan after the open", "unread": "the store could not be read",
             "corp_action": "a dividend or a split took effect on %s, so the prior close on file is not the exchange's",
             "bars_disagree": "the day low and the 1-minute bars disagree at the %d%% line",
             "late_print": ("the day low reached the %d%% line only after the last regular-hours scan — a late trigger "
                            "or an after-hours print"),
             "computed_only": "the house's bars show a %d%% drop but neither exchange list carries it"}
CORP_UNREAD_NOTE = ("That day's dividends and splits could not be checked, so the prior close may be unadjusted. ")   # computed sources only, when corp_checked is false; printed right after PRIOR_CLOSE_NOTE
HONESTY_NOTE = "The listing exchange decides; a tag marked computed is this app's own read of the %d%% line."
FAULT_TEXT = "%s %s tags may be missing: %s."                               # sources' texts joined "; "
FAULT_UNREADABLE = "%s %s tags could not be read — a missing tag does not mean the restriction is off."
# the served `computed` row's text (MINE — the spec freezes the key, not the words)
COMPUTED_TEXT_FINAL = "computed read for %s · complete (last 5-minute scan %s ET)"
COMPUTED_TEXT_LIVE = "computed read for %s · last 5-minute scan %s ET"
COMPUTED_TEXT_STALE = "computed read for %s · the 5-minute scan has not read the market since %s ET"
COMPUTED_TEXT_NONE = "computed read for %s not run yet"

# ───────────────────────────────────────────── the names NEW on one trigger day (2026-11-24 ssrlist §3.2)
# Ajay 2026-11-24: "What are the SSR stocks today" · "Can you add it to short interest tab" · "The new ones".
# Keys FROZEN (the 🩳 High SI block reads them); the words are MINE (HIS CALL 11).
NEW_KIND = "ssr_new_triggers"
NEW_STATUSES = ("ok", "not_read", "pre_open", "not_latest", "out_of_play", "failed")
NEW_KEYS = ("kind", "status", "day", "day_words", "prior_day", "is_today", "market_day_today", "title", "rows", "n",
            "n_official", "n_computed", "n_retriggered", "sources_text", "retriggered_text", "withheld",
            "withheld_text", "faults", "faults_text", "through", "off_from", "half_day", "window_text", "computed",
            "sources", "corp_checked", "asof_text", "status_text", "partial_text", "empty_text", "fault_text",
            "note_text", "rule_text")                       # rev 2: + prior_day [C1], + corp_checked [C4]
NEW_ROW_KEYS = ("symbol", "source", "exchange", "time_basis", "at_et", "at_text", "drop_pct", "drop_text",
                "source_text", "retriggered", "mark_text")
NEW_WITHHELD = ("corp_action", "computed_only", "bars_disagree")   # computed_only: DEFENSIVE, cannot occur in production (§6.17)
NEW_TITLE_TODAY = "%s %s — new today (%s)"                    # GLYPH, TAG, _day_words(D)
NEW_TITLE_SESSION = "%s %s — new on %s, the last session"
NEW_TITLE_BARE = "%s %s — new names"                          # the day could not be read
NEW_CLOSED_TODAY = " · the market is closed today"
NEW_DAY_UNREAD = "that day"                                   # the day words when the asked day could not be read (the `_why_text` fallback word)
NEW_WINDOW_TEXT = "Each is in force through %s, after-hours included; off from %s."   # + HALF_DAY_TEXT when half_day
NEW_AT_PLAIN = "%s ET"                                        # minute_bar "09:42" · exchange "09:45:36"
NEW_AT_SEEN = "by %s ET"                                      # first_seen — the 5-minute scan's first sight
NEW_SRC_COMPUTED = "computed"                                 # a test pins COMPUTED_TAIL.endswith(NEW_SRC_COMPUTED)
NEW_RETRIGGER_MARK = "also triggered %s"                      # _day_words(prev_market_day(D)) — ALWAYS the prior market day [C1]
NEW_SOURCES_TEXT = "%d on an exchange list · %d computed here"
NEW_RETRIGGERED_TEXT = "%d were already restricted and triggered again"
NEW_FAULTS_TEXT = "%d name(s) could not be read this time — the rest of the list stands"
NEW_PRE_OPEN_TEXT = "No name can be new on %s yet — only regular-hours trades start it, and regular hours open at %s ET."
NEW_NOT_LATEST_TEXT = "This list covers the newest trigger day only (%s)."
NEW_OUT_OF_PLAY_TEXT = "What started on %s has run out — nothing from that day is in force."
NEW_EMPTY_TEXT = "No name has newly triggered it on %s (%s)."                 # day words, computed text
NEW_PARTIAL_TEXT = "This list may be missing names: %s."                       # computed text
NEW_CORP_UNREAD_TEXT = "%s A name whose only drop is a dividend or a split may be listed by mistake."   # CORP_UNREAD_NOTE.strip() [C4]
NEW_NOT_READ_TEXT = "%s %s — the names new on %s are not read yet: %s. A missing list does not mean no name triggered."
NEW_FAULT_TEXT = "%s %s — the names new on %s could not be read. A missing list does not mean no name triggered."
NEW_WITHHELD_TEXT = "Left off this list: %s."                                  # parts joined "; "
NEW_WITHHELD_PART = "%s — %s"                                                  # names joined ", " · _why_text(why, ev)
NEW_NOTE_TEXT = ("A plain time is the first regular-hours minute at or under the %d%% line (a name on the Gajjala "
                 "cards) or the exchange's own time; “by” is the 5-minute scan that first saw the drop. The %% is "
                 "the low at that read against the prior close — not the drop now. “%s” = this app's own read of "
                 "that line, with no exchange list read here carrying the name yet. The exchanges publish a day's "
                 "names after the close, some only the next morning, so most names stay “%s”, and a name is not "
                 "taken off this list for being missing from an exchange list. “also triggered” = already under "
                 "it from the trading day before; the new drop extends it a day.")     # rev 2 [C3b]: no "comes off" promise
# the closing sentence of every title is RS.NOT_A_SIGNAL, by name

_SPACES = re.compile(r" {2,}")
_STAMP14 = re.compile(r"^\d{14}$")


# ───────────────────────────────────────────── small helpers
def _pos(x) -> Optional[float]:
    """A finite positive float, else None."""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f) or f <= 0:
        return None
    return f


def _as_date(d) -> Optional[date]:
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    return RS._as_date(d)


def _drop_pct(low: float, prev: float) -> float:
    return round((low / prev - 1.0) * 100.0, 1)


def _day_words(d) -> str:
    """"Tue 11/24" — `%a` + SR._md."""
    dd = _as_date(d)
    if dd is None:
        return str(d)
    return "%s %s" % (dd.strftime("%a"), SR._md(dd.isoformat()))


def _px(x) -> str:
    """A price as printed: up to 4 decimals, at least 2."""
    f = _pos(x)
    if f is None:
        return str(x)
    s = "%.4f" % f
    while s.endswith("0") and len(s.split(".")[1]) > 2:
        s = s[:-1]
    return s


def _pct_words(p) -> str:
    try:
        return "%.1f%%" % float(p)
    except (TypeError, ValueError):
        return str(p)


def _hm_et(iso) -> Optional[str]:
    d = RS._parse_iso(iso)
    return d.astimezone(_ET).strftime("%H:%M") if d is not None else None


def _rth_open_dt(session: date) -> datetime:
    from daytrading.data import ET_RTH_OPEN
    return datetime.combine(session, ET_RTH_OPEN, tzinfo=_ET)


def _stale_sec() -> int:
    from chart_maps.gajjala import constants as GC
    return int(SSR_STALE_PASSES * GC.PASS_CADENCE_SEC)


def _spellings(sym) -> list:
    """The asked spelling, its norm and alias keys — de-duplicated, in that order."""
    out = []
    s = str(sym or "").strip().upper()
    norm = RS.norm_symbol(s)
    for k in (s, norm) + (RS.alias_keys(norm) if norm else ()):
        if k and k not in out:
            out.append(k)
    return out


def _field_key(sym: str) -> Optional[str]:
    """A `names.<SYM>` field key: the dash spelling, no dots, never a leading $."""
    k = str(sym or "").strip().upper().replace(".", "-")
    if not k or k.startswith("$"):
        return None
    return k


def _resolve_lists(lists):
    if lists is not None:
        return lists
    from short_interest import ssr_lists                      # lazy: the frozen W2 interface
    return ssr_lists


SSR_COLL_FALLBACK = "ssr_rule_201"   # = ssr_lists.SSR_COLL (a test pins them equal); used only when ssr_lists cannot import


def _coll_name() -> str:
    """The collection the computed half writes. A broken `ssr_lists` must not stop the computed half (§6.15
    severability), so the name falls back to the literal rather than raising."""
    try:
        return _resolve_lists(None).SSR_COLL
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ssr: exchange lists not wired, computed half writes on: %s", type(exc).__name__)
        return SSR_COLL_FALLBACK


def _resolve_corp(corp):
    """The corp seam; a missing or broken `ssr_corp` reads as "not read" (None)."""
    if corp is not None:
        return corp
    try:
        from short_interest import ssr_corp                   # lazy: the frozen W5 interface
        return ssr_corp
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ssr: corporate actions not wired: %s", type(exc).__name__)
        return None


# ───────────────────────────────────────────── pure rule functions (spec §3.2)
def trigger_line(prev_close) -> Optional[float]:
    """The price at/under which the rule starts: prev × (1 − SSR_TRIGGER_DROP_PCT / 100)."""
    p = _pos(prev_close)
    if p is None:
        return None
    return round(p * (1.0 - SSR_TRIGGER_DROP_PCT / 100.0), _PRICE_DP)


def is_trigger(low, prev_close) -> Optional[bool]:
    """None when either price is missing / ≤ 0; exactly the line is ON."""
    lo = _pos(low)
    line = trigger_line(prev_close)
    if lo is None or line is None:
        return None
    return round(lo, _PRICE_DP) <= line


def window(T) -> dict:
    """The rule's window for a trigger on market day T: the rest of T + SSR_FOLLOWING_TRADING_DAYS trading days,
    after-hours included (FAQ 2.1). Expires at the session's extended close (`alerts._closes`)."""
    from catalysts.medical.reaction import next_market_day, rth_close_time
    from chart_maps.gajjala.alerts import _closes
    from supply_demand.timeframes import HALF_DAYS
    t = _as_date(T)
    through = t
    for _ in range(SSR_FOLLOWING_TRADING_DAYS):
        through = next_market_day(through)
    off_from = next_market_day(through)
    return {"triggered_on": t, "through": through, "off_from": off_from,
            "expires_at": datetime.combine(through, _closes(through)[1], tzinfo=_ET),
            "half_day": through.isoformat() in HALF_DAYS, "rth_close": rth_close_time(through)}


def in_play(now_et) -> list:
    """The trigger days whose window is open at `now_et`, newest first."""
    from catalysts.medical.reaction import is_market_day, prev_market_day
    now_et = RS._to_et(now_et)
    today = now_et.date()
    L = today if is_market_day(today) else prev_market_day(today)
    out = []
    for T in (L, prev_market_day(L)):
        if now_et >= window(T)["expires_at"]:
            continue
        if T == today and now_et < _rth_open_dt(T):
            continue
        out.append(T)
    return out


def _rth_lows(raw, session: date) -> list:
    """[(ET minute start, low)] of the minutes whose ET START is on `session` in [ET_RTH_OPEN, rth_close_time) —
    judged by the stamp, never by a `session` column. Minutes without a finite positive low are left out."""
    if raw is None:
        return []
    try:
        if len(raw) == 0 or "low" not in raw.columns:
            return []
    except (TypeError, AttributeError):
        return []
    import pandas as pd
    from catalysts.medical.reaction import rth_close_time
    idx = pd.DatetimeIndex(raw.index)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    et = idx.tz_convert(_ET)
    start = _rth_open_dt(session)
    end = datetime.combine(session, rth_close_time(session), tzinfo=_ET)
    mask = (et >= start) & (et < end)
    lows = pd.to_numeric(raw["low"], errors="coerce").to_numpy()
    out = []
    for t, lo in zip(et[mask], lows[mask]):
        f = _pos(lo)
        if f is not None:
            out.append((t.to_pydatetime(), f))
    out.sort(key=lambda x: x[0])
    return out


def first_trigger_minute(raw, session, prev_close) -> Optional[dict]:
    """The FIRST regular-hours minute at/under the line → {"at": "HH:MM", "low", "drop_pct"}; None = no such minute."""
    s = _as_date(session)
    prev = _pos(prev_close)
    if s is None or prev is None:
        return None
    for t, lo in _rth_lows(raw, s):
        if is_trigger(lo, prev):
            return {"at": t.strftime("%H:%M"), "low": lo, "drop_pct": _drop_pct(lo, prev)}
    return None


def rth_minutes(raw, session) -> dict:
    """{"n": regular-hours minutes of `session`, "low": their lowest low or None} — stamp-judged like
    `first_trigger_minute`."""
    s = _as_date(session)
    lows = _rth_lows(raw, s) if s is not None else []
    return {"n": len(lows), "low": min(lo for _t, lo in lows) if lows else None}


def eval_row(row, session) -> dict:
    """The SNAPSHOT read of one row (spec §3.2, in order): no prior close → no day bar → the RTH-open stamp guard
    [C3] → the scale-glitch guard → on / off."""
    from chart_maps import drop10_tab
    from sepa import prices
    s = _as_date(session)
    raw = row if isinstance(row, dict) else {}
    prev = _pos(raw.get("prev_day_close"))
    if prev is None:
        return {"s": "unknown", "why": "no_prior_close"}
    d = drop10_tab.day_from_snapshot(raw, s) if s is not None else None
    if d is None:
        return {"s": "unknown", "why": "no_day_bar"}
    ep = prices._trade_epoch(raw.get("min_t_ms"))
    if ep is None:                                             # the order day_from_snapshot itself uses
        ep = prices._trade_epoch(raw.get("last_trade_ts_ms"))
    if ep is None or datetime.fromtimestamp(ep, tz=_ET) < _rth_open_dt(s):
        return {"s": "unknown", "why": "no_day_bar", "stale": True}
    if prices._is_scale_glitch(d["low"], d["prev_close"]):
        return {"s": "unknown", "why": "price_suspect"}
    lo, pc = d["low"], d["prev_close"]
    return {"s": "on" if is_trigger(lo, pc) else "off", "pc": pc, "lo": lo, "drop_pct": _drop_pct(lo, pc)}


def _judge(row, raw, session) -> tuple:
    """(judgement, snapshot eval, rth minutes) — `judge_followed`'s table, spec §3.2 [C2]."""
    e = eval_row(row, session)
    if e.get("why") in ("no_prior_close", "price_suspect"):
        return dict(e, by="snapshot"), e, {"n": 0, "low": None}
    m = rth_minutes(raw, session)
    if m["n"] == 0:
        return dict(e, by="snapshot"), e, m
    prev = _pos((row or {}).get("prev_day_close"))
    hit = first_trigger_minute(raw, session, prev)
    if hit is not None:
        return ({"s": "on", "by": "minute", "at": hit["at"], "pc": prev, "lo": hit["low"], "mlo": m["low"],
                 "drop_pct": hit["drop_pct"]}, e, m)
    if e["s"] == "on":
        return ({"s": "unknown", "why": "bars_disagree", "by": "minute", "pc": prev, "lo": e.get("lo"),
                 "mlo": m["low"], "drop_pct": e.get("drop_pct")}, e, m)
    return ({"s": "off", "by": "minute", "pc": prev, "lo": m["low"], "mlo": m["low"],
             "drop_pct": _drop_pct(m["low"], prev)}, e, m)


def judge_followed(row, raw, session) -> dict:
    """The read of ONE followed name — the minute bars decide [C2]."""
    return _judge(row, raw, session)[0]


# ───────────────────────────────────────────── the ONE writer (spec §3.5)
_index_done = {"ok": False}


def _ensure_index(coll) -> None:
    if _index_done["ok"]:
        return
    try:
        coll.create_index([("kind", 1), ("date", -1)])
        _index_done["ok"] = True
    except Exception:                                          # noqa: BLE001
        pass


def _names_entry(j: dict, at_iso: str) -> dict:
    return {"s": j.get("s"), "why": j.get("why"), "by": j.get("by"), "pc": j.get("pc"), "lo": j.get("lo"),
            "mlo": j.get("mlo"), "drop_pct": j.get("drop_pct"), "at": at_iso}


def record_pass(rows, frames, now, session, *, followed=(), good=True, db=_DEFAULT) -> dict:
    """The computed read of one Gajjala pass. Never raises (→ {"error": <ExceptionName>}), never an outside call,
    no `out` key, no gate, never reads `ssr_corp` (the corporate-action rule is applied at READ time)."""
    try:
        return _record_pass(rows, frames, now, session, followed=followed, good=good, db=db)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ssr: the pass read failed: %s", type(exc).__name__)
        return {"error": type(exc).__name__}


def _record_pass(rows, frames, now, session, *, followed, good, db) -> dict:
    from chart_maps import drop10_tab
    from supply_demand.key_levels import close_confirm_at
    sess_d = _as_date(session)
    now_et = RS._to_et(now)
    mode, sess, _tape, _half = drop10_tab.mode_for(now_et)
    if mode not in (drop10_tab.MODE_LIVE, drop10_tab.MODE_AFTER) or sess != sess_d:
        return {"skipped": "closed"}
    if not good or not rows:
        return {"skipped": "snapshot"}
    if db is _DEFAULT:
        db = SIC._get_db()
    if db is None:
        return {"error": "no_db"}
    coll = db[_coll_name()]
    _ensure_index(coll)
    iso = sess_d.isoformat()
    now_iso = RS._utc_iso(now_et)
    hm = now_et.strftime("%H:%M")
    rows = rows if isinstance(rows, dict) else {}
    frames = frames if isinstance(frames, dict) else {}

    # 2. every row, the stamp guard inside [C3]
    evals = {}
    stale_bar = 0
    for sym, row in rows.items():
        e = eval_row(row, sess_d)
        evals[sym] = e
        if e.get("stale"):
            stale_bar += 1
    usable = sum(1 for e in evals.values() if e["s"] in ("on", "off"))

    existing = {}
    for d in coll.find({"kind": "trig", "date": iso}):
        if d.get("symbol"):
            existing[d["symbol"]] = d

    # 3. followed names — the minute bars decide [C2]
    fol = [s for s in dict.fromkeys(followed or ()) if s]
    judged = {}
    by_minute = set()
    new = upgraded = voided = lo_under = 0
    disagree = []
    for s in fol:
        fr = frames.get(s)
        j, e, m = _judge(rows.get(s), getattr(fr, "raw", None) if fr is not None else None, sess_d)
        judged[s] = j
        if j.get("by") == "minute":
            by_minute.add(s)
        if e.get("lo") is not None and m.get("low") is not None and \
                round(e["lo"], _PRICE_DP) < round(m["low"], _PRICE_DP):
            lo_under += 1
        tid = "trig|%s|%s" % (iso, s)
        old = existing.get(s)
        if j["s"] == "on" and j["by"] == "minute":
            if old is not None and old.get("basis") == "minute_bar" and not old.get("void"):
                continue                                       # already a minute doc: the first minute stands
            doc = {"kind": "trig", "date": iso, "symbol": s, "basis": "minute_bar", "at": j["at"], "low": j["lo"],
                   "drop_pct": j["drop_pct"], "prev_close": j["pc"]}
            coll.update_one({"_id": tid}, {"$set": doc, "$unset": {"void": ""},
                                           "$setOnInsert": {"created_at": now_iso}}, upsert=True)
            if old is None:
                new += 1
                existing[s] = dict(doc, _id=tid, created_at=now_iso)
            else:
                upgraded += 1
                merged = dict(old)
                merged.update(doc)
                merged.pop("void", None)
                existing[s] = merged
        elif j["s"] == "unknown" and j.get("why") == "bars_disagree":
            disagree.append(s)
            if old is not None and old.get("basis") == "snapshot" and not old.get("void"):
                coll.update_one({"_id": tid}, {"$set": {"void": "bars_disagree"}})
                old = dict(old, void="bars_disagree")
                existing[s] = old
                voided += 1

    # 4. whole market — snapshot triggers, regular-hours passes ONLY [C2]
    if mode == drop10_tab.MODE_LIVE:
        docs = []
        for sym, e in evals.items():
            if e["s"] != "on" or sym in by_minute or sym in existing:
                continue
            docs.append({"_id": "trig|%s|%s" % (iso, sym), "kind": "trig", "date": iso, "symbol": sym,
                         "basis": "snapshot", "at": None, "seen_at": hm, "prev_close": e["pc"], "low": e["lo"],
                         "drop_pct": e["drop_pct"], "created_at": now_iso})
        if docs:
            try:
                coll.insert_many(docs, ordered=False)
                new += len(docs)
            except Exception as exc:                           # noqa: BLE001 — a duplicate from a twin pass
                n_ins = 0
                try:
                    n_ins = int((getattr(exc, "details", None) or {}).get("nInserted") or 0)
                except Exception:                              # noqa: BLE001
                    n_ins = 0
                new += n_ins
                log.warning("ssr: snapshot trig insert partly failed: %s", type(exc).__name__)
            for d in docs:
                existing.setdefault(d["symbol"], d)

    live = {s for s, d in existing.items() if not d.get("void")}
    void = {s for s, d in existing.items() if d.get("void")}

    # 6 (decided before 5 so the day doc carries `final` in the same write). The close pass [C5].
    is_close = now_et.time() >= close_confirm_at(sess_d)
    final_written = False
    if is_close:
        jid = "judged|%s" % iso
        if coll.find_one({"_id": jid}) is None:
            off = set()
            unjudged = {}
            universe = list(dict.fromkeys(list(rows.keys()) + fol))
            for sym in universe:
                if sym in live:
                    continue
                stv = judged.get(sym) if sym in judged else evals.get(sym, {"s": "unknown", "why": "no_prior_close"})
                if stv["s"] == "off":
                    off.add(sym)
                    continue
                uk = _field_key(sym)                           # a Mongo field key: "FCRS.WS" → "FCRS-WS", never "$…"
                if uk is None:
                    continue
                if sym in void:
                    unjudged[uk] = "bars_disagree"
                elif stv["s"] == "on":
                    unjudged[uk] = "late_print"
                else:
                    unjudged[uk] = stv.get("why") or "no_day_bar"
            coll.update_one({"_id": jid}, {"$setOnInsert": {
                "kind": "judged", "date": iso, "at": now_iso, "off": " ".join(sorted(off)),
                "unjudged": unjudged, "n_off": len(off), "n_unjudged": len(unjudged)}}, upsert=True)
        final_written = True

    # 5. the day doc — a MERGE, never a replace
    st = {"kind": "day", "date": iso, "last_ok_at": now_iso, "n_rows": len(rows), "n_usable": usable,
          "n_trig": len(live)}
    for s in fol:
        k = _field_key(s)
        if k is not None:
            st["names.%s" % k] = _names_entry(judged[s], now_iso)
    if final_written:
        st["final"] = True                                     # never unset
    coll.update_one({"_id": "day|%s" % iso}, {"$set": st}, upsert=True)

    return {"rows": len(rows), "usable": usable, "new": new, "upgraded": upgraded, "voided": voided,
            "followed": len(fol), "final": final_written, "stale_bar": stale_bar, "lo_under_minutes": lo_under,
            "disagree": len(disagree)}


# ───────────────────────────────────────────── the resolution (spec §3.6)
_jcache_lock = threading.Lock()
_jcache = {}                      # judged _id -> (at, off set, unjudged dict) — decoded once per doc


def _reset_cache() -> None:
    with _jcache_lock:
        _jcache.clear()


def _judged_sets(coll, iso: str) -> Optional[tuple]:
    jid = "judged|%s" % iso
    doc = coll.find_one({"_id": jid})
    if not doc:
        return None
    at = doc.get("at")
    with _jcache_lock:
        hit = _jcache.get(jid)
        if hit is not None and hit[0] == at:
            return hit[1], hit[2]
    off = set(str(doc.get("off") or "").split())
    unjudged = dict(doc.get("unjudged") or {})
    with _jcache_lock:
        _jcache[jid] = (at, off, unjudged)
    return off, unjudged


def _first(mapping, keys):
    if not mapping:
        return None
    for k in keys:
        if k in mapping:
            return mapping[k]
    return None


class _Ctx:
    """Everything one read loaded (Mongo only)."""

    def __init__(self, lists, loaded, corp, corp_loaded, coll, days, now_et):
        self.lists = lists
        self.loaded = loaded
        self.corp = corp
        self.corp_loaded = corp_loaded
        self.days = days
        self.now_et = now_et
        self.today = now_et.date()
        self.stale_sec = _stale_sec()
        self.day_docs = {}
        self.judged = {}
        self.actions = {}
        self.complete = {}
        for T in days:
            iso = T.isoformat()
            self.day_docs[iso] = coll.find_one({"_id": "day|%s" % iso})
            dd = self.day_docs[iso] or {}
            self.judged[iso] = _judged_sets(coll, iso) if dd.get("final") else None
            self.actions[iso] = self._actions(T)
            self.complete[iso] = bool(lists.complete_for(loaded, T))

    def _actions(self, T):
        if self.corp is None or self.corp_loaded is None:
            return None
        try:
            return self.corp.actions(self.corp_loaded, T)
        except Exception as exc:                               # noqa: BLE001
            log.warning("ssr: corporate actions unread: %s", type(exc).__name__)
            return None

    def age_sec(self, iso_ts) -> Optional[float]:
        d = RS._parse_iso(iso_ts)
        return None if d is None else (self.now_et - d).total_seconds()


def _official_rows(ctx, sym) -> list:
    try:
        return list(ctx.lists.rows_for(ctx.loaded, sym) or [])
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ssr: list rows unread: %s", type(exc).__name__)
        return []


def _trig_docs(coll, days, syms) -> dict:
    """{(date iso, spelling): trig doc} for every asked spelling — ONE read."""
    keys = []
    for s in syms:
        for k in _spellings(s):
            if k not in keys:
                keys.append(k)
    if not keys or not days:
        return {}
    out = {}
    for d in coll.find({"kind": "trig", "date": {"$in": [T.isoformat() for T in days]}, "symbol": {"$in": keys}}):
        out[(d.get("date"), d.get("symbol"))] = d
    return out


def _day_eval(ctx, sym, T, trigs) -> dict:
    """One trigger day's evidence for one asked symbol (spec §3.6 table)."""
    iso = T.isoformat()
    sp = _spellings(sym)
    rows = [r for r in _official_rows(ctx, sym) if str(r.get("trigger_date")) == iso]
    ca = ctx.actions.get(iso)
    ca_kind = _first(ca, sp) if ca is not None else None
    trig = None
    for k in sp:
        trig = trigs.get((iso, k))
        if trig is not None:
            break
    live_trig = trig if trig is not None and not trig.get("void") else None
    corp_void = live_trig is not None and ca_kind is not None
    comp_on = live_trig is not None and not corp_void
    complete = ctx.complete.get(iso, False)
    overruled = comp_on and not rows and complete and SSR_COMPUTED_UNTIL_LISTS_COMPLETE
    on = bool(rows) or (comp_on and not overruled)

    dd = ctx.day_docs.get(iso) or {}
    final = bool(dd.get("final"))
    js = ctx.judged.get(iso)
    in_off = js is not None and final and any(k in js[0] for k in sp)
    names = dd.get("names") or {}
    entry = _first(names, sp)
    entry_age = ctx.age_sec(entry.get("at")) if entry else None
    entry_fresh = entry is not None and entry_age is not None and entry_age <= ctx.stale_sec
    entry_off = entry is not None and entry.get("s") == "off"
    split = ca_kind == "split"

    # coverage — POSITIVE evidence only [C5]
    cov2_raw = final and in_off
    cov3_raw = T == ctx.today and not final and entry_off and entry_fresh
    covered = False
    if not on:
        if complete and not overruled:
            covered = True
        elif (cov2_raw or cov3_raw) and not split:
            covered = True

    why = None
    if not on and not covered:
        if ca_kind is not None and (corp_void or cov2_raw or cov3_raw):
            why = "corp_action"
        elif overruled:
            why = "computed_only"
        elif final:
            uks = [k for k in dict.fromkeys(_field_key(s) for s in sp) if k is not None]
            why = (_first(js[1], uks) if js is not None else None) or "no_final_read"
        elif T == ctx.today:
            if entry is not None:
                if not entry_fresh:
                    why = "scan_stale"
                elif entry.get("s") == "on":
                    why = "late_print"
                else:
                    why = entry.get("why") or "scan_stale"
            else:
                day_age = ctx.age_sec(dd.get("last_ok_at")) if dd else None
                since_open = (ctx.now_et - _rth_open_dt(T)).total_seconds()
                if dd and day_age is not None and day_age <= ctx.stale_sec:
                    why = "not_followed"
                elif not dd and 0 <= since_open <= ctx.stale_sec:
                    why = "awaiting_first_scan"
                else:
                    why = "scan_stale"
        else:
            why = "no_final_read"
    return {"T": T, "iso": iso, "rows": rows, "trig": live_trig if comp_on else None, "on": on,
            "official": bool(rows), "covered": covered, "why": why, "overruled": overruled, "complete": complete,
            "corp_checked": ca is not None, "entry": entry, "dd": dd, "in_off": in_off}


def _why_text(why: str, ev: Optional[dict]) -> str:
    w = WHY_WORDS.get(why, why)
    if "%" not in w:
        return w
    if why in ("bars_disagree", "late_print", "computed_only"):
        return w % SSR_TRIGGER_DROP_PCT
    if why in ("no_final_read", "corp_action"):
        return w % (_day_words(ev["T"]) if ev else "that day")
    if why == "scan_stale":
        at = None
        if ev:
            at = _hm_et((ev.get("entry") or {}).get("at")) or _hm_et((ev.get("dd") or {}).get("last_ok_at"))
            if at is None:
                at = _rth_open_dt(ev["T"]).strftime("%H:%M")
        return w % (at or "the open")
    return w


def _unknown_block(sym: str, why: str, ev: Optional[dict]) -> Optional[dict]:
    forms = tuple(f for f in SSR_FORMS if f in tuple(SSR_UNKNOWN_FORMS or ()))
    if not forms or why in SSR_QUIET_WHYS:
        return None
    word = UNKNOWN_LABEL % (GLYPH, TAG)
    title = UNKNOWN_TITLE % (GLYPH, TAG, sym, _why_text(why, ev), RS.NOT_A_SIGNAL)
    return {"state": "unknown", "symbol": sym, "why": why,
            "chip": word if "chip" in forms else None, "short": word if "short" in forms else None,
            "label": word if "label" in forms else None, "title": title}


def _stamp_words(row: dict) -> str:
    st = str(row.get("stamp") or "")
    if _STAMP14.match(st):
        try:
            dt = datetime.strptime(st, "%Y%m%d%H%M%S")
            return "%s %s ET" % (SR._md(dt.date().isoformat()), dt.strftime("%H:%M:%S"))
        except ValueError:
            pass
    return SR._md(str(row.get("file_date") or row.get("trigger_date") or ""))


def _list_name(lists, row: dict) -> str:
    for src in getattr(lists, "SOURCES", ()) or ():
        if src.get("key") == row.get("source"):
            return src.get("exchange") or str(row.get("source"))
    return str(row.get("exchange") or row.get("source") or "")


def _on_block(sym: str, evs: list, ctx) -> dict:
    on_days = [ev for ev in evs if ev["on"]]
    gov = max(on_days, key=lambda ev: ev["T"])
    T = gov["T"]
    w = window(T)
    official = gov["official"]
    trig = gov["trig"]                                         # facts merged: the day's live, not corp-void computed doc
    if official:
        row = sorted(gov["rows"], key=lambda r: str(r.get("trigger_time") or ""))[0]
        exch = row.get("exchange") or _list_name(ctx.lists, row)
        at = str(row.get("trigger_time") or "")
        basis = "exchange"
        drop = DROP_CLAUSE % (_pct_words(trig["drop_pct"]), _px(trig["prev_close"])) if trig else ""
        trig_s = TRIG_OFFICIAL % (_day_words(T), at, drop, _list_name(ctx.lists, row), _stamp_words(row))
        source = "official"
    else:
        exch = None
        tail = NOT_ON_ANY_LIST if gov["complete"] else NOT_ON_LIST_YET
        if trig.get("basis") == "minute_bar":
            at, basis = trig.get("at"), "minute_bar"
            trig_s = TRIG_MINUTE % (_day_words(T), at, _px(trig.get("low")), _px(trig.get("prev_close")), tail)
        else:
            at, basis = trig.get("seen_at"), "first_seen"
            trig_s = TRIG_SEEN % (_day_words(T), at, _px(trig.get("low")), _px(trig.get("prev_close")), tail)
        source = "computed"

    conflict = None
    extras = ""
    older = [ev for ev in on_days if ev is not gov]
    if older:
        extras += RETRIGGER_TEXT % _day_words(older[0]["T"])
    if w["half_day"]:
        extras += HALF_DAY_TEXT % (_day_words(w["through"]), w["rth_close"].strftime("%H:%M"))
    if official:
        entry = gov["entry"]
        if entry is not None and entry.get("s") == "off":
            conflict = "official_on_computed_off"
            if entry.get("lo") is not None and entry.get("pc") is not None:
                extras += CONFLICT_OFFICIAL_WINS % (SSR_TRIGGER_DROP_PCT, _px(entry["lo"]), _px(entry["pc"]))
            else:
                extras += CONFLICT_OFFICIAL_WINS_BARE % SSR_TRIGGER_DROP_PCT
        elif gov["in_off"]:
            conflict = "official_on_computed_off"
            extras += CONFLICT_OFFICIAL_WINS_BARE % SSR_TRIGGER_DROP_PCT
    elif gov["complete"]:                                       # only reachable with the switch off (HIS CALL 4)
        conflict = "computed_only"

    notes = ""
    if source == "computed":
        notes = PRIOR_CLOSE_NOTE + ("" if gov["corp_checked"] else CORP_UNREAD_NOTE)
    title = TITLE_ON % (GLYPH, TAG, sym, trig_s, _day_words(w["through"]), _day_words(w["off_from"]), extras,
                        RULE_TEXT % (SSR_RULE, SSR_TRIGGER_DROP_PCT, SSR_TRIGGER_DROP_PCT), notes,
                        (HONESTY_NOTE % SSR_TRIGGER_DROP_PCT) + " " + RS.NOT_A_SIGNAL)
    title = _SPACES.sub(" ", title)
    ctail = COMPUTED_TAIL if source == "computed" else ""
    src_words = LABEL_SRC_OFFICIAL % exch if official else LABEL_SRC_COMPUTED
    thru = _day_words(w["through"])
    return {"state": "on", "symbol": sym, "source": source, "exchange": exch,
            "triggered_on": T.isoformat(), "triggered_at_et": at, "time_basis": basis,
            "through": w["through"].isoformat(), "off_from": w["off_from"].isoformat(), "half_day": bool(w["half_day"]),
            "drop_pct": trig.get("drop_pct") if trig else None,
            "prior_close": trig.get("prev_close") if trig else None,
            "retriggered": len(on_days) == 2, "conflict": conflict, "corp_checked": bool(gov["corp_checked"]),
            "chip": (CHIP_TEXT % (GLYPH, TAG, TAG_WORDS, thru)) + ctail,
            "short": (SHORT_TEXT % (GLYPH, TAG, SR._md(w["through"].isoformat()))) + ctail,
            "label": LABEL_TEXT % (GLYPH, TAG, TAG_WORDS, thru, src_words),
            "title": title}


def resolve(sym, ctx, trigs) -> tuple:
    """(state, why, item-or-None) for one asked symbol."""
    evs = []
    for T in ctx.days:
        evs.append(_day_eval(ctx, sym, T, trigs))
    if any(ev["on"] for ev in evs):
        return "on", None, _on_block(sym, evs, ctx)
    unc = [ev for ev in evs if not ev["covered"]]
    if not unc:
        return "off", None, None
    newest = max(unc, key=lambda ev: ev["T"])
    return "unknown", newest["why"], _unknown_block(sym, newest["why"], newest)


# ───────────────────────────────────────────── the served read (spec §3.8)
def _envelope(status, items, states, whys, syms, now_et, days, sources, computed, fault_text, refreshing,
              retry_after_sec) -> dict:
    return {"kind": KIND, "status": status, "items": items, "states": states, "whys": whys,
            "asked": len(syms), "n": len(items), "max_symbols": MAP_MAX_SYMBOLS,
            "session": {"now_et": now_et.strftime("%Y-%m-%d %H:%M"), "in_play": [T.isoformat() for T in days]},
            "sources": sources, "computed": computed, "note": HONESTY_NOTE % SSR_TRIGGER_DROP_PCT,
            "fault_text": fault_text, "refreshing": bool(refreshing), "retry_after_sec": retry_after_sec,
            "keep_sec": SSR_KEEP_SEC}


def _failed(syms, now_et) -> dict:
    items, states, whys = {}, {}, {}
    for s in syms:
        states[s] = "unknown"
        whys[s] = "unread"
        blk = _unknown_block(s, "unread", None)
        if blk is not None:
            items[s] = blk
    try:
        days = in_play(now_et)
    except Exception:                                          # noqa: BLE001
        days = []
    computed = {"ok": False, "last_pass_et": None, "final": False, "text": None}
    return _envelope("failed", items, states, whys, syms, now_et, days, [], computed,
                     FAULT_UNREADABLE % (GLYPH, TAG), False, None)


def _computed_view(ctx) -> dict:
    if not ctx.days:
        return {"ok": False, "last_pass_et": None, "final": False, "text": None}
    L = ctx.days[0]
    dd = ctx.day_docs.get(L.isoformat())
    if not dd:
        return {"ok": False, "last_pass_et": None, "final": False, "text": COMPUTED_TEXT_NONE % _day_words(L)}
    last = _hm_et(dd.get("last_ok_at"))
    final = bool(dd.get("final"))
    age = ctx.age_sec(dd.get("last_ok_at"))
    if final:
        return {"ok": True, "last_pass_et": last, "final": True, "text": COMPUTED_TEXT_FINAL % (_day_words(L), last)}
    if age is not None and age <= ctx.stale_sec:
        return {"ok": True, "last_pass_et": last, "final": False, "text": COMPUTED_TEXT_LIVE % (_day_words(L), last)}
    return {"ok": False, "last_pass_et": last, "final": False, "text": COMPUTED_TEXT_STALE % (_day_words(L), last)}


def payload(symbols, db=_DEFAULT, now=None, *, kick: bool = True, http=None, lists=None, corp=None) -> dict:
    """THE served read — Mongo reads only, never an outside call. A due list OR a due corporate-action day kicks
    the ONE worker through `lists.kick_refresh` (never inline)."""
    now_et = RS._to_et(now)
    syms = BR.clean_symbols(symbols)
    try:
        lists = _resolve_lists(lists)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ssr: exchange lists not wired: %s", type(exc).__name__)
        return _failed(syms, now_et)
    corp = _resolve_corp(corp)
    if db is _DEFAULT:
        db = SIC._get_db()
    if db is None:
        return _failed(syms, now_et)
    try:
        return _payload(syms, db, now, now_et, kick=kick, http=http, lists=lists, corp=corp)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ssr: the read failed: %s", type(exc).__name__)
        return _failed(syms, now_et)


def _payload(syms, db, now, now_et, *, kick, http, lists, corp) -> dict:
    coll = db[lists.SSR_COLL]
    loaded = lists.load(coll, now_et)
    days = in_play(now_et)
    corp_loaded = None
    if corp is not None:
        try:
            corp_loaded = corp.load(coll, days)
        except Exception as exc:                               # noqa: BLE001
            log.warning("ssr: corporate actions unread: %s", type(exc).__name__)
            corp_loaded = None

    refreshing = False
    started = False
    if kick:
        due = bool(lists.any_due(loaded, now_et))
        if not due and corp is not None and corp_loaded is not None:
            try:
                due = bool(corp.any_due(corp_loaded, days, now_et))
            except Exception as exc:                           # noqa: BLE001
                log.warning("ssr: corporate-action due check failed: %s", type(exc).__name__)
        if due:
            started = bool(lists.kick_refresh(coll, now_et if now is not None else None, http=http))
    refreshing = bool(started or lists.worker_running())

    ctx = _Ctx(lists, loaded, corp, corp_loaded, coll, days, now_et)
    trigs = _trig_docs(coll, days, syms)
    items, states, whys = {}, {}, {}
    for s in syms:
        state, why, blk = resolve(s, ctx, trigs)
        states[s] = state
        if why is not None:
            whys[s] = why
        if blk is not None:
            items[s] = blk

    sources = list(lists.source_views(loaded, now_et) or [])
    if corp is not None and corp_loaded is not None:
        try:
            sources.append(corp.source_view(corp_loaded, days, now_et))
        except Exception as exc:                               # noqa: BLE001
            log.warning("ssr: corporate-action source row failed: %s", type(exc).__name__)
    computed = _computed_view(ctx)
    official = [x for x in sources if x.get("key") != "corp_actions"]
    fault = None
    if not any(x.get("ok") for x in official) and not computed["ok"]:
        texts = [x.get("text") for x in official if x.get("text")] + ([computed["text"]] if computed["text"] else [])
        fault = FAULT_TEXT % (GLYPH, TAG, "; ".join(texts))
    return _envelope("ok", items, states, whys, syms, now_et, days, sources, computed, fault, refreshing,
                     getattr(lists, "RETRY_AFTER_SEC", None) if refreshing else None)


def fault_payload(symbols=None) -> dict:
    """The served body when the read itself raised — the SAME shape as "Mongo down". Reads nothing."""
    now_et = RS._to_et(None)
    try:
        syms = BR.clean_symbols(symbols)
    except Exception:                                          # noqa: BLE001
        syms = []
    try:
        return _failed(syms, now_et)
    except Exception:                                          # noqa: BLE001
        computed = {"ok": False, "last_pass_et": None, "final": False, "text": None}
        return _envelope("failed", {}, {}, {}, [], now_et, [], [], computed, FAULT_UNREADABLE % (GLYPH, TAG),
                         False, None)


# ───────────────────────────────────────────── the names NEW on one trigger day (2026-11-24 ssrlist §3.2)
def _new_note() -> str:
    return (NEW_NOTE_TEXT % (SSR_TRIGGER_DROP_PCT, NEW_SRC_COMPUTED, NEW_SRC_COMPUTED) + " "
            + HONESTY_NOTE % SSR_TRIGGER_DROP_PCT + " " + RS.NOT_A_SIGNAL)


def _new_rule() -> str:
    return (RULE_TEXT % (SSR_RULE, SSR_TRIGGER_DROP_PCT, SSR_TRIGGER_DROP_PCT)).strip()


def _new_title(D, now_et, market_day_today) -> str:
    if D is None:
        return NEW_TITLE_BARE % (GLYPH, TAG)
    if D == now_et.date():
        return NEW_TITLE_TODAY % (GLYPH, TAG, _day_words(D))
    return NEW_TITLE_SESSION % (GLYPH, TAG, _day_words(D)) + ("" if market_day_today else NEW_CLOSED_TODAY)


def _new_base(D, now_et) -> dict:
    """Every NEW_KEYS key with its not-evaluated value (None / [] / the unread computed row)."""
    out = {k: None for k in NEW_KEYS}
    out.update({"kind": NEW_KIND, "day": D.isoformat() if D is not None else None,
                "day_words": _day_words(D) if D is not None else None, "rows": [],
                "computed": {"ok": False, "last_pass_et": None, "final": False, "text": None}, "sources": [],
                "note_text": _new_note(), "rule_text": _new_rule(), "title": NEW_TITLE_BARE % (GLYPH, TAG)})
    try:
        from catalysts.medical.reaction import is_market_day
        mkt = bool(is_market_day(now_et.date()))
        out["market_day_today"] = mkt
        out["is_today"] = (D == now_et.date()) if D is not None else None
        out["title"] = _new_title(D, now_et, mkt)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ssr: new-names title unread: %s", type(exc).__name__)
    return out


def _new_failed(D, now_et) -> dict:
    """The `failed` shape — never raises."""
    try:
        now_et = now_et if isinstance(now_et, datetime) else RS._to_et(None)
        out = _new_base(D, now_et)
    except Exception:                                          # noqa: BLE001
        out = {k: None for k in NEW_KEYS}
        out.update({"kind": NEW_KIND, "rows": [], "sources": [], "title": NEW_TITLE_BARE % (GLYPH, TAG),
                    "computed": {"ok": False, "last_pass_et": None, "final": False, "text": None}})
    out["status"] = "failed"
    out["rows"] = []
    out["empty_text"] = None
    out["fault_text"] = NEW_FAULT_TEXT % (GLYPH, TAG, out.get("day_words") or NEW_DAY_UNREAD)
    return out


def _finite(x) -> Optional[float]:
    """A finite float, else None (never NaN / inf / a bool / a string)."""
    if isinstance(x, bool):
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _new_row(sym: str, it: dict, P: date) -> dict:
    basis = it.get("time_basis")
    at = it.get("triggered_at_et")
    at = at if isinstance(at, str) and at else None
    at_text = None
    if at is not None:
        at_text = (NEW_AT_SEEN % at) if basis == "first_seen" else (NEW_AT_PLAIN % at)
    pct = _finite(it.get("drop_pct"))
    official = it.get("source") == "official"
    retrig = bool(it.get("retriggered"))
    return {"symbol": sym, "source": it.get("source"), "exchange": it.get("exchange"), "time_basis": basis,
            "at_et": at, "at_text": at_text, "drop_pct": pct, "drop_text": _pct_words(pct) if pct is not None else None,
            "source_text": (LABEL_SRC_OFFICIAL % it.get("exchange")) if official else NEW_SRC_COMPUTED,
            "retriggered": retrig, "mark_text": (NEW_RETRIGGER_MARK % _day_words(P)) if retrig else None}


def new_triggers(day, db=_DEFAULT, now=None, *, lists=None, corp=None) -> dict:
    """The names whose restriction STARTED on `day`, resolved by the rules `payload` uses (`_day_eval` + `_on_block`,
    no second computation of the line). Mongo reads only, never kicks, never writes, never raises (→ the `failed`
    shape). `in_play(now)` decides the STATUS only; the evidence is read over [day, prev_market_day(day)] with the
    lists as of the day's own files, so a row and its mark never change with the clock [C1]."""
    D = None
    now_et = None
    try:
        now_et = RS._to_et(now)
        D = _as_date(day)
        if D is None:
            return _new_failed(None, now_et)
        lists = _resolve_lists(lists)
        corp = _resolve_corp(corp)
        if db is _DEFAULT:
            db = SIC._get_db()
        if db is None:
            return _new_failed(D, now_et)
        return _new_triggers(D, db, now_et, lists, corp)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ssr: the new-names read failed: %s", type(exc).__name__)
        return _new_failed(D, now_et)


def _new_triggers(D, db, now_et, lists, corp) -> dict:
    from catalysts.medical.reaction import prev_market_day
    out = _new_base(D, now_et)
    out["status"] = "ok"

    # 2. STATUS ONLY — `days` is used for nothing else
    days = in_play(now_et)
    if D not in days:
        if D >= now_et.date() and now_et < _rth_open_dt(D):
            out["status"] = "pre_open"
            out["status_text"] = NEW_PRE_OPEN_TEXT % (_day_words(D), _rth_open_dt(D).strftime("%H:%M"))
        else:
            out["status"] = "out_of_play"
            out["status_text"] = NEW_OUT_OF_PLAY_TEXT % _day_words(D)
        return out
    if D != days[0]:
        out["status"] = "not_latest"
        out["status_text"] = NEW_NOT_LATEST_TEXT % _day_words(days[0])
        return out

    # 3. [C1] the prior market day, explicitly; the lists as of the list day's OWN files
    P = prev_market_day(D)
    iso, piso = D.isoformat(), P.isoformat()
    eval_days = [D, P]                                         # D first — `_computed_view` reads ctx.days[0]
    list_now = now_et if now_et.date() <= D else datetime.combine(D, datetime.max.time(), tzinfo=_ET)
    coll = db[lists.SSR_COLL]
    loaded = lists.load(coll, list_now)
    corp_loaded = None
    if corp is not None:
        try:
            corp_loaded = corp.load(coll, eval_days)
        except Exception as exc:                               # noqa: BLE001
            log.warning("ssr: corporate actions unread: %s", type(exc).__name__)
            corp_loaded = None
    ctx = _Ctx(lists, loaded, corp, corp_loaded, coll, eval_days, now_et)

    # 4. ONE find — the `_trig_docs` map shape; str symbols only
    trigs = {}
    for d in coll.find({"kind": "trig", "date": {"$in": [iso, piso]}}):
        s = d.get("symbol") if isinstance(d, dict) else None
        if isinstance(s, str) and s:
            trigs[(d.get("date"), s)] = d

    # 5. candidates — one name, one row
    seen, cands = set(), []

    def add(s):
        sp = _spellings(s)
        if not sp or any(k in seen for k in sp):
            return
        seen.update(sp)
        cands.append(s)

    for dt, s in sorted(trigs):
        if dt == iso:
            add(s)
    for s in lists.symbols_on(loaded, D) or []:
        if isinstance(s, str) and s:
            add(s)

    # 6–7. each name in its OWN try
    rows, faults = [], []
    withheld = {r: [] for r in NEW_WITHHELD}
    for s in cands:
        try:
            ev = _day_eval(ctx, s, D, trigs)
            if ev["on"]:
                it = _on_block(s, [ev, _day_eval(ctx, s, P, trigs)], ctx)
                if it.get("triggered_on") != iso:
                    faults.append(s)
                    continue
                rows.append(_new_row(s, it, P))
                continue
            doc = next((trigs[(iso, k)] for k in _spellings(s) if (iso, k) in trigs), None)
            if doc is None:                                    # a list name its own rows do not carry: unread, never "none"
                faults.append(s)
                continue
            why = "bars_disagree" if doc.get("void") else ("computed_only" if ev["overruled"] else "corp_action")
            withheld[why].append(s)
        except Exception as exc:                               # noqa: BLE001
            log.warning("ssr: one new name unread: %s", type(exc).__name__)
            faults.append(s)

    # 8. rows, the computed row, the sources, the as-of line
    rows.sort(key=lambda r: r["symbol"])
    computed = _computed_view(ctx)
    sources = list(lists.source_views(loaded, list_now) or [])
    if corp is not None and corp_loaded is not None:
        try:
            sources.append(corp.source_view(corp_loaded, [D], now_et))
        except Exception as exc:                               # noqa: BLE001
            log.warning("ssr: corporate-action source row failed: %s", type(exc).__name__)
    sources = [x for x in sources if isinstance(x, dict)]
    corp_checked = ctx.actions.get(iso) is not None            # [C4]
    texts = ([computed.get("text")] + [x.get("text") for x in sources if x.get("key") != "corp_actions"]
             + [x.get("text") for x in sources if x.get("key") == "corp_actions"])
    asof = "; ".join(t for t in texts if isinstance(t, str) and t)

    n_off = sum(1 for r in rows if r["source"] == "official")
    n_comp = sum(1 for r in rows if r["source"] == "computed")
    n_re = sum(1 for r in rows if r["retriggered"])
    dw = _day_words(D)
    w = window(D)
    wt = NEW_WINDOW_TEXT % (_day_words(w["through"]), _day_words(w["off_from"]))
    if w["half_day"]:
        wt += HALF_DAY_TEXT % (_day_words(w["through"]), w["rth_close"].strftime("%H:%M"))
    wparts = [NEW_WITHHELD_PART % (", ".join(withheld[r]), _why_text(r, {"T": D})) for r in NEW_WITHHELD
              if withheld[r]]
    out.update({"prior_day": piso, "corp_checked": corp_checked, "rows": rows, "n": len(rows), "n_official": n_off,
                "n_computed": n_comp, "n_retriggered": n_re,
                "sources_text": (NEW_SOURCES_TEXT % (n_off, n_comp)) if rows else None,
                "retriggered_text": (NEW_RETRIGGERED_TEXT % n_re) if n_re else None,
                "withheld": withheld, "withheld_text": (NEW_WITHHELD_TEXT % "; ".join(wparts)) if wparts else None,
                "faults": faults, "faults_text": (NEW_FAULTS_TEXT % len(faults)) if faults else None,
                "through": w["through"].isoformat(), "off_from": w["off_from"].isoformat(),
                "half_day": bool(w["half_day"]), "window_text": wt, "computed": computed, "sources": sources,
                "asof_text": asof or None})

    # 9. the honesty table, then the dividend / split sentence [C4]
    if not rows and not computed["ok"]:
        out["status"] = "not_read"
        out["fault_text"] = NEW_NOT_READ_TEXT % (GLYPH, TAG, dw, asof)
    elif not rows and not faults:                              # a faulted name is never "no name"
        out["empty_text"] = NEW_EMPTY_TEXT % (dw, computed["text"])
    parts = []
    if rows and not computed["ok"]:
        parts.append(NEW_PARTIAL_TEXT % computed["text"])
    if n_comp > 0 and not corp_checked:
        parts.append(NEW_CORP_UNREAD_TEXT % CORP_UNREAD_NOTE.strip())
    out["partial_text"] = " ".join(parts) or None
    return out


def _and_list(names: list) -> str:
    return RS._and_list(names) if names else ""


def rules_line() -> str:
    """The ℹ️ 🩳 section's `alerts` line — numbers from the constants, exchange names from `ssr_lists.SOURCES`."""
    lists = _resolve_lists(None)
    names = [src.get("exchange") for src in lists.SOURCES if src.get("exchange")]
    pct = SSR_TRIGGER_DROP_PCT
    return ("%s %s (%s) = the SEC short-sale restriction, %s: once a stock trades %d%% or more under the prior day's "
            "close during regular hours, a short sale must be priced above the best bid for the rest of that day "
            "and the next trading day, after-hours included; a new %d%% drop on that next day extends it, and a "
            "drop outside regular hours never starts it. Official = the %s short sale circuit breaker lists; "
            "computed = this app's own read of the %d%% line from its 1-minute bars (names on the Gajjala cards) or "
            "the 5-minute scan's day low (every other stock), marked 'computed'. A computed tag comes off once both "
            "exchange lists are complete without the name; no computed tag on a dividend or split day. A tag only: "
            "it pushes nothing, gates nothing, sorts nothing and enters no lane. UNMEASURED."
            % (GLYPH, TAG, TAG_WORDS, SSR_RULE, pct, pct, _and_list(names), pct))
