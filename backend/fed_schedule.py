"""The Federal Reserve's own calendar — FOMC decisions, minutes, Beige Book and
the Fed Chair's remarks, read from federalreserve.gov (2026-10-07).

Ajay 2026-10-07: "First today there was an FOMC event why is it not in our new
tab in chart maps. I want us to pull dynamic dates". Today's event was the FOMC
MINUTES of the Sep 15-16 meeting (2:00 p.m. ET) — the app only knew decision
days, from a hand-typed list, so a minutes row could never exist.

Two official sources, both on federalreserve.gov (MEASURED 2026-10-07):
  * json/calendar.json — the current year only: FOMC meetings (decision day +
    time), press conferences, minutes, Beige Book, speeches and testimony.
  * monetarypolicy/fomccalendars.htm — decision days 2021..next year, the `*`
    SEP (dot-plot) marker and "(Released …)" minutes dates.

Each source's last-known-good parse lives in Mongo `macro_fed_calendar`.
`load()` reads LKG ∪ the built-in floor and NEVER fetches; `current()` is the
ONE fetching entry point (called only by `macro_calendar.compute()`). A year
neither source answered falls back to FLOOR_DECISION_DATES. Nothing is ever
derived: no minutes date, presser time or SEP flag is filled in by assumption.

NOT a signal. Nothing here gates, pushes, sizes or enters.
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
import threading
import time
from datetime import date, datetime, timezone
from typing import Callable, Optional

log = logging.getLogger("fed_schedule")

FED_CALENDAR_JSON_URL = "https://www.federalreserve.gov/json/calendar.json"
FED_FOMC_CALENDARS_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
FED_USER_AGENT = os.getenv("GOV_USER_AGENT", "CheetahMarketApp/1.0 (+https://pounce.ajaykandakatla.dev)")
FED_TIMEOUT = (5, 15)                 # connect, read — both pages answered in ~1 s (MEASURED 10-07)
FED_REFRESH_SEC = 6 * 3600            # one cadence with macro_calendar.TTL_SEC
FED_STALE_SEC = 24 * 3600             # display freshness only — not a trading threshold
FED_MIN_MEETINGS_PER_YEAR = 6         # the Fed schedules 8 (MEASURED 2021-2027); a year with fewer parsed is not trusted
FED_YEARS_BACK, FED_YEARS_AHEAD = 6, 2
COLLECTION = "macro_fed_calendar"
SRC_JSON, SRC_HTM = "calendar_json", "fomccalendars"
FLOOR_CHECKED_ON = "2026-10-07"       # floor last matched against fomccalendars.htm (MEASURED: identical 2024-09..2027-12)

# FLOOR ONLY — the Fed's own pages above are primary. Authoritative FOMC
# decision days. The rate decision + statement lands on the LAST day of each
# two-day meeting. SOURCE: Federal Reserve FOMC calendar
# (federalreserve.gov/monetarypolicy/fomccalendars.htm), fetched 2026-06-17;
# re-checked 2026-10-07 (FLOOR_CHECKED_ON). Moved verbatim from
# macro_calendar.py (where it is re-exported as FOMC_DECISION_DATES).
FLOOR_DECISION_DATES = (
    # 2024 — added 2026-09-30 for the 🛡️ Resiliency tab's event history (past_events):
    # meetings Sep 17-18, Nov 6-7, Dec 17-18 (federalreserve.gov fomccalendars.htm,
    # re-fetched 2026-09-30).
    "2024-09-18", "2024-11-07", "2024-12-18",
    # 2025
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    # 2026
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
    # 2027
    "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09",
    "2027-07-28", "2027-09-15", "2027-10-27", "2027-12-08",
)
SOURCE_LABEL = {
    SRC_JSON: "Federal Reserve calendar (federalreserve.gov)",
    SRC_HTM: "Federal Reserve FOMC calendar page (federalreserve.gov)",
    "floor": f"Federal Reserve FOMC calendar (built-in list, checked {FLOOR_CHECKED_ON})",
}
FED_NOTE_OK = "FOMC decisions, minutes and Fed Chair remarks: federalreserve.gov"
FED_NOTE_STALE = "Fed calendar not re-read since {as_of} — showing the last good copy"
FED_NOTE_FLOOR = ("Fed calendar unreachable — FOMC decision days from the built-in list "
                  f"(checked {FLOOR_CHECKED_ON}); minutes and Fed Chair remarks not shown")
# 2026-10-07 critic fix: the floor note must not blame the Fed when it is the
# last-good-copy store (Mongo) that failed — the Fed is never asked without it.
FED_NOTE_NO_STORE = ("Fed calendar store unavailable — FOMC decision days from the built-in list "
                     f"(checked {FLOOR_CHECKED_ON}); minutes and Fed Chair remarks not shown")
# The FOMC page answered but calendar.json never parsed: decisions are live,
# minutes and Chair remarks do not exist anywhere in the schedule.
FED_NOTE_NO_JSON = ("FOMC decision days: federalreserve.gov FOMC page; "
                    "minutes and Fed Chair remarks not shown (Fed calendar not read)")

_SCHEMA = 1
_JSON_TYPES = ("FOMC", "Beige", "Speeches", "Testimony")
# Only these types are weekday-bounded: FOMC meetings, pressers, minutes and the
# Beige Book are weekday releases. Remarks are NOT — the Fed lists Chair speeches
# on weekends (MEASURED: Powell 2026-03-21 Sat, 2025-05-25 Sun in calendar.json).
_WEEKDAY_TYPES = ("FOMC", "Beige")
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?$", re.I)
_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")
_REMARK_RE = re.compile(r"^\s*([A-Za-z][A-Za-z ]*?)\s*-{1,2}\s*(.+?)\s*$")
_CHAIR_RE = re.compile(r"^(Chair|Chairman|Chairwoman)\b")
_MEETING_RE = re.compile(
    r"(?:Meeting of|Two-day meeting,|One-day meeting,)\s*"
    r"([A-Z][a-z]+\s+\d{1,2}(?:\s*-\s*(?:[A-Z][a-z]+\s+)?\d{1,2})?)")
_PANEL_RE = re.compile(r'<h4>\s*<a[^>]*>\s*(\d{4}) FOMC Meetings\s*</a>\s*</h4>')
_ROW_RE = re.compile(
    r'fomc-meeting__month[^>]*>\s*<strong>([^<]+)</strong>\s*</div>\s*'
    r'<div class="[^"]*fomc-meeting__date[^"]*"[^>]*>([^<]+)</div>'
    r'(.*?)(?=fomc-meeting__month|panel-footer|<h4>|\Z)', re.S)
_DAYS_RE = re.compile(r"^(\d{1,2})-(\d{1,2})(\*?)$")
_RELEASED_RE = re.compile(r"\(Released ([A-Z][a-z]+ \d{1,2}, \d{4})\)")
_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}

_DEFAULT = object()
_COLL = None
_REFRESH_LOCK = threading.Lock()


def _today_et() -> date:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date()
    except Exception:                                          # noqa: BLE001
        return datetime.now(timezone.utc).date()


# ── pure parsers (never raise) ──────────────────────────────────────────────
def to_24h(s) -> Optional[str]:
    """'2:00 p.m.' → '14:00'; anything else → None."""
    if not isinstance(s, str):
        return None
    m = _TIME_RE.match(s.strip())
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3).lower()
    if not (1 <= h <= 12 and 0 <= mi <= 59):
        return None
    if ap == "a":
        h = 0 if h == 12 else h
    else:
        h = 12 if h == 12 else h + 12
    return f"{h:02d}:{mi:02d}"


def _clean(s) -> str:
    if not isinstance(s, str):
        return ""
    t = html.unescape(html.unescape(s))
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _in_bounds(d: date, today: date, weekday: bool = True) -> bool:
    return (today.year - FED_YEARS_BACK <= d.year <= today.year + FED_YEARS_AHEAD
            and (not weekday or d.weekday() < 5))


def _meeting_text(desc) -> Optional[str]:
    m = _MEETING_RE.search(_clean(desc))
    if not m:
        return None
    return re.sub(r"\s*-\s*", "-", m.group(1)).strip()


def _empty_cal(reason: str) -> dict:
    return {"ok": False, "reason": reason, "meetings": [], "pressers": [], "minutes": [],
            "beige": [], "remarks": [], "years": {}, "rejected": 0}


def parse_calendar_json(text: str, today: date) -> dict:
    """federalreserve.gov/json/calendar.json → meetings / pressers / minutes /
    Beige / remarks. ok = ≥ FED_MIN_MEETINGS_PER_YEAR meetings AND ≥ 1 minutes
    row in today.year."""
    try:
        if not isinstance(text, str):
            return _empty_cal("not text")
        body = json.loads(text.lstrip("﻿"))
    except Exception as exc:                                   # noqa: BLE001
        return _empty_cal(f"json {type(exc).__name__}")
    events = body.get("events") if isinstance(body, dict) else None
    if not isinstance(events, list):
        return _empty_cal("no events list")
    out = _empty_cal("")
    seen: set = set()
    for e in events:
        if not isinstance(e, dict) or e.get("type") not in _JSON_TYPES:
            continue
        mm = _MONTH_RE.match(str(e.get("month") or ""))
        if not mm:
            if str(e.get("month") or ""):
                out["rejected"] += 1
            continue
        yr, mo = int(mm.group(1)), int(mm.group(2))
        typ = e.get("type")
        dates = []
        for part in str(e.get("days") or "").split(","):
            part = part.strip()
            try:
                if not part.isdigit():
                    raise ValueError(part)
                d = date(yr, mo, int(part))
            except Exception:                                  # noqa: BLE001
                out["rejected"] += 1
                continue
            if not _in_bounds(d, today, weekday=typ in _WEEKDAY_TYPES):
                out["rejected"] += 1
                continue
            dates.append(d.isoformat())
        if not dates:
            continue
        t = to_24h(e.get("time"))
        title = str(e.get("title") or "")
        for d in dates:
            if typ == "FOMC":
                tl = title.strip().lower()
                if tl == "fomc meeting":
                    key, row = "meetings", {"date": d, "time_et": t,
                                            "meeting": _meeting_text(e.get("description"))}
                elif tl == "fomc press conference":
                    key, row = "pressers", {"date": d, "time_et": t}
                elif tl == "fomc minutes":
                    key, row = "minutes", {"date": d, "time_et": t,
                                           "meeting": _meeting_text(e.get("description"))}
                else:
                    continue
            elif typ == "Beige":
                key, row = "beige", {"date": d, "time_et": t}
            else:
                m = _REMARK_RE.match(title)
                if not m:
                    continue
                who = m.group(2).strip()
                key, row = "remarks", {"date": d, "time_et": t, "what": m.group(1).strip(),
                                       "who": who, "topic": _clean(e.get("description")),
                                       "chair": bool(_CHAIR_RE.match(who))}
            dk = (key, d) if key != "remarks" else (key, d, row["who"], row["time_et"])
            if dk in seen:
                continue
            seen.add(dk)
            out[key].append(row)
    for k in ("meetings", "pressers", "minutes", "beige", "remarks"):
        out[k].sort(key=lambda r: (r["date"], r.get("time_et") or "99:99"))
    years: dict = {}
    for r in out["meetings"]:
        years[r["date"][:4]] = years.get(r["date"][:4], 0) + 1
    out["years"] = years
    y = str(today.year)
    n_min = sum(1 for r in out["minutes"] if r["date"][:4] == y)
    if years.get(y, 0) < FED_MIN_MEETINGS_PER_YEAR:
        out["reason"] = f"{years.get(y, 0)} meetings in {y}"
    elif n_min < 1:
        out["reason"] = f"no minutes in {y}"
    else:
        out["ok"], out["reason"] = True, None
    return out


def _month_num(raw: str) -> Optional[int]:
    last = (raw or "").split("/")[-1].strip().lower()
    return _MONTHS.get(last[:3]) if len(last) >= 3 else None


def parse_fomccalendars_htm(text: str, today: date) -> dict:
    """monetarypolicy/fomccalendars.htm → decision days per year panel, SEP
    flag, minutes release date. Notation votes / unscheduled rows are skipped."""
    out = {"ok": False, "reason": None, "meetings": [], "years": {}, "skipped": [], "rejected": 0}
    if not isinstance(text, str):
        out["reason"] = "not text"
        return out
    try:
        parts = _PANEL_RE.split(text)
    except Exception as exc:                                   # noqa: BLE001
        out["reason"] = f"split {type(exc).__name__}"
        return out
    seen: set = set()
    for i in range(1, len(parts) - 1, 2):
        try:
            year = int(parts[i])
        except Exception:                                      # noqa: BLE001
            continue
        out["years"].setdefault(str(year), 0)
        for m in _ROW_RE.finditer(parts[i + 1]):
            mon_raw, days_raw, rest = m.group(1).strip(), m.group(2).strip(), m.group(3)
            dm = _DAYS_RE.match(days_raw)
            mo = _month_num(mon_raw)
            if not dm or mo is None:
                out["skipped"].append(f"{year} {mon_raw} {days_raw}")
                continue
            try:
                d = date(year, mo, int(dm.group(2)))
            except Exception:                                  # noqa: BLE001
                out["rejected"] += 1
                continue
            if not _in_bounds(d, today) or d.isoformat() in seen:
                out["rejected"] += 1
                continue
            seen.add(d.isoformat())
            rel = None
            rm = _RELEASED_RE.search(rest or "")
            if rm:
                try:
                    rel = datetime.strptime(rm.group(1), "%B %d, %Y").date().isoformat()
                except Exception:                              # noqa: BLE001
                    rel = None
            out["meetings"].append({"date": d.isoformat(), "sep": dm.group(3) == "*",
                                    "meeting": f"{mon_raw} {dm.group(1)}-{dm.group(2)}",
                                    "minutes_released": rel})
            out["years"][str(year)] += 1
    out["meetings"].sort(key=lambda r: r["date"])
    full = [y for y, n in out["years"].items() if n >= FED_MIN_MEETINGS_PER_YEAR]
    y = str(today.year)
    if len(full) < 2:
        out["reason"] = f"{len(full)} full year panels"
    elif out["years"].get(y, 0) < FED_MIN_MEETINGS_PER_YEAR:
        out["reason"] = f"{out['years'].get(y, 0)} meetings in {y}"
    else:
        out["ok"] = True
    return out


def merge(cal: Optional[dict], htm: Optional[dict], today: date,
          floor: tuple = FLOOR_DECISION_DATES) -> dict:
    """LKG parses ∪ floor → one schedule. PURE. Per year: calendar.json when it
    has ≥ MIN meetings AND at least as many as fomccalendars.htm lists for that
    year (a json row that failed to parse must never silently drop a decision
    the FOMC page has — critic fix 2026-10-07), else fomccalendars.htm, else
    the floor. Minutes, Beige and remarks come from calendar.json only — never
    derived."""
    cal = cal if isinstance(cal, dict) else {}
    htm = htm if isinstance(htm, dict) else {}
    cal_m = [r for r in cal.get("meetings") or [] if isinstance(r, dict) and r.get("date")]
    htm_m = [r for r in htm.get("meetings") or [] if isinstance(r, dict) and r.get("date")]
    floor_d = [d for d in floor or () if isinstance(d, str) and len(d) == 10]

    def _by_year(rows):
        by: dict = {}
        for r in rows:
            by.setdefault(int(r["date"][:4]), []).append(r)
        return by

    cal_y, htm_y = _by_year(cal_m), _by_year(htm_m)
    floor_y: dict = {}
    for d in floor_d:
        floor_y.setdefault(int(d[:4]), []).append(d)
    cal_by_date = {r["date"]: r for r in cal_m}
    htm_by_date = {r["date"]: r for r in htm_m}
    presser = {r["date"]: r.get("time_et") for r in cal.get("pressers") or []
               if isinstance(r, dict) and r.get("date")}
    decisions, jy, hy, fy = [], [], [], []
    for y in sorted(set(cal_y) | set(htm_y) | set(floor_y)):
        n_cal = len(cal_y.get(y, []))
        if n_cal >= FED_MIN_MEETINGS_PER_YEAR and n_cal >= len(htm_y.get(y, [])):
            dates, src = [r["date"] for r in cal_y[y]], SOURCE_LABEL[SRC_JSON]
            jy.append(y)
        elif len(htm_y.get(y, [])) >= FED_MIN_MEETINGS_PER_YEAR:
            dates, src = [r["date"] for r in htm_y[y]], SOURCE_LABEL[SRC_HTM]
            hy.append(y)
        elif floor_y.get(y):
            dates, src = list(floor_y[y]), SOURCE_LABEL["floor"]
            fy.append(y)
        else:
            continue
        for d in sorted(set(dates)):
            c, h = cal_by_date.get(d) or {}, htm_by_date.get(d) or {}
            sep = h.get("sep") if isinstance(h.get("sep"), bool) else None
            decisions.append({"date": d, "time_et": c.get("time_et"),
                              "presser_time_et": presser.get(d), "sep": sep,
                              "meeting": c.get("meeting") or h.get("meeting"),
                              "source": src})
    decisions.sort(key=lambda r: r["date"])

    def _src(rows):
        return [{**r, "source": SOURCE_LABEL[SRC_JSON]} for r in rows or [] if isinstance(r, dict)]

    return {"decisions": decisions, "minutes": _src(cal.get("minutes")),
            "beige": _src(cal.get("beige")), "remarks": _src(cal.get("remarks")),
            "floor_years": fy, "json_years": jy, "htm_years": hy}


# ── I/O (never raises; errors logged by class / HTTP code, never the text) ──
def _coll():
    global _COLL
    if _COLL is not None:
        return _COLL
    client = None
    try:
        import pymongo
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        client = pymongo.MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _COLL = client[os.getenv("MONGO_DB", "cheetah")][COLLECTION]
        return _COLL
    except Exception:                                          # noqa: BLE001
        if client is not None:                                 # never leak its monitor threads
            try:
                client.close()
            except Exception:                                  # noqa: BLE001
                pass
        return None


def _http_get(url: str, last_modified: Optional[str]) -> tuple:
    import requests
    headers = {"User-Agent": FED_USER_AGENT, **({"If-Modified-Since": last_modified} if last_modified else {})}
    r = requests.get(url, headers=headers, timeout=FED_TIMEOUT)
    return r.status_code, r.text, r.headers.get("Last-Modified")


def read_lkg(store) -> dict:
    out = {SRC_JSON: None, SRC_HTM: None}
    if store is None:
        return out
    for src in (SRC_JSON, SRC_HTM):
        try:
            doc = store.find_one({"_id": src})
            out[src] = doc if isinstance(doc, dict) else None
        except Exception as exc:                               # noqa: BLE001
            log.warning("fed_schedule: LKG read %s failed: %s", src, type(exc).__name__)
    return out


_SOURCES = ((SRC_JSON, FED_CALENDAR_JSON_URL, parse_calendar_json),
            (SRC_HTM, FED_FOMC_CALENDARS_URL, parse_fomccalendars_htm))


def _iso_utc(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def refresh_due(*, store=None, http: Optional[Callable] = None, now: Optional[float] = None,
                today: Optional[date] = None) -> dict:
    """Re-read each source whose LKG is missing or ≥ FED_REFRESH_SEC old. No
    store → no fetch. Returns the LKG dict after any refresh (the fresh doc is
    returned even when the write fails)."""
    if store is None:
        return {SRC_JSON: None, SRC_HTM: None}
    http = http or _http_get
    with _REFRESH_LOCK:
        now = time.time() if now is None else now
        today = today or _today_et()
        lkg = read_lkg(store)
        for src, url, parse in _SOURCES:
            doc = lkg.get(src)
            # A parse written by an older parser (schema ≠ _SCHEMA) is kept as the
            # LKG but treated as missing: no If-Modified-Since, so a 304 can never
            # pin the old parser's output (critic fix 2026-10-07).
            has = (isinstance(doc, dict) and isinstance(doc.get("parsed"), dict)
                   and doc.get("schema") == _SCHEMA)
            age = (now - float(doc.get("fetched_at") or 0)) if has else None
            if has and age < FED_REFRESH_SEC:
                continue
            upd: dict = {"last_attempt_at": now}
            try:
                status, body, lm = http(url, doc.get("last_modified") if has else None)
                if status == 304 and has:
                    upd.update(fetched_at=now, fetched_at_iso=_iso_utc(now), last_error=None)
                elif status == 200:
                    parsed = parse(body, today)
                    if parsed.get("ok"):
                        upd.update(parsed=parsed, fetched_at=now, fetched_at_iso=_iso_utc(now),
                                   last_modified=lm, last_error=None, schema=_SCHEMA)
                    else:
                        upd["last_error"] = f"parse: {parsed.get('reason')}"
                else:
                    upd["last_error"] = f"HTTP {status}"
            except Exception as exc:                           # noqa: BLE001
                upd["last_error"] = type(exc).__name__
            if upd.get("last_error"):
                log.warning("fed_schedule: %s refresh kept the last good copy: %s",
                            src, upd["last_error"])
            new = {**(doc or {}), "_id": src, **upd}
            lkg[src] = new
            try:
                store.update_one({"_id": src}, {"$set": upd}, upsert=True)
            except Exception as exc:                           # noqa: BLE001
                log.warning("fed_schedule: LKG write %s failed: %s", src, type(exc).__name__)
        return lkg


def _status(lkg: dict, store_ok: bool = True) -> dict:
    j, h = lkg.get(SRC_JSON) or {}, lkg.get(SRC_HTM) or {}
    jp = j.get("parsed") if isinstance(j.get("parsed"), dict) else None
    hp = h.get("parsed") if isinstance(h.get("parsed"), dict) else None
    as_of = j.get("fetched_at") if jp else (h.get("fetched_at") if hp else None)
    return {
        "as_of": as_of, "as_of_iso": _iso_utc(as_of) if isinstance(as_of, (int, float)) else None,
        "floor": jp is None and hp is None,
        "store_ok": store_ok is True,
        "sources": {
            SRC_JSON: {"ok": jp is not None, "fetched_at": j.get("fetched_at"),
                       "last_modified": j.get("last_modified"), "last_error": j.get("last_error"),
                       "n_meetings": len((jp or {}).get("meetings") or []),
                       "n_minutes": len((jp or {}).get("minutes") or [])},
            SRC_HTM: {"ok": hp is not None, "fetched_at": h.get("fetched_at"),
                      "last_modified": h.get("last_modified"), "last_error": h.get("last_error"),
                      "years": sorted(int(y) for y in ((hp or {}).get("years") or {}))},
        },
    }


def _sched(lkg: dict, today: date, store_ok: bool = True) -> dict:
    j, h = lkg.get(SRC_JSON) or {}, lkg.get(SRC_HTM) or {}
    out = merge(j.get("parsed"), h.get("parsed"), today)
    out["status"] = _status(lkg, store_ok)
    return out


def load(*, store=_DEFAULT, today=None) -> dict:
    """LKG ∪ floor. NEVER fetches."""
    store = _coll() if store is _DEFAULT else store
    return _sched(read_lkg(store), today or _today_et(), store is not None)


def current(*, store=_DEFAULT, http=None, now=None, today=None) -> dict:
    """refresh_due + merge. The ONE fetching entry point (macro_calendar.compute)."""
    store = _coll() if store is _DEFAULT else store
    today = today or _today_et()
    return _sched(refresh_due(store=store, http=http, now=now, today=today), today,
                  store is not None)


def status_view(status: Optional[dict], now: Optional[float] = None) -> Optional[dict]:
    if not isinstance(status, dict):
        return None
    now = time.time() if now is None else now
    as_of = status.get("as_of")
    age = int(now - as_of) if isinstance(as_of, (int, float)) else None
    floor = status.get("floor") is True
    stale = age is not None and age > FED_STALE_SEC
    json_ok = ((status.get("sources") or {}).get(SRC_JSON) or {}).get("ok")
    if floor:
        note = FED_NOTE_NO_STORE if status.get("store_ok") is False else FED_NOTE_FLOOR
    elif stale:
        note = FED_NOTE_STALE.format(as_of=status.get("as_of_iso"))
    elif json_ok is False:
        note = FED_NOTE_NO_JSON
    else:
        note = FED_NOTE_OK
    return {"note": note, "as_of_iso": status.get("as_of_iso"), "age_sec": age,
            "stale": stale, "floor": floor}
