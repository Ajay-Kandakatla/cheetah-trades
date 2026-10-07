"""Macro calendar — tiered upcoming data releases for the REGIME check.

The framework is the ZONETRADER618 "Not All Data Is Equal" tiering:
  • TIER 1 — market movers : Jobs report (NFP/unemployment/wages), CPI, FOMC
             decision + dot plot + presser, Core PCE
  • TIER 2 — trend shapers : ISM mfg & services, retail sales, JOLTS, ADP,
             jobless claims, GDP, Fed-speaker remarks
             (FRED "shadow" releases — state/industry/research cuts of a print —
             excluded by name in _RELEASE_EXCLUDE; fixture
             tests/fixtures/fred_release_dates_2026_09_24.json)
  • TIER 3 — context       : consumer/business confidence, housing starts/permits,
             regional Fed indices, trade balance
Regime weighting (right now): inflation + labor-strength prints carry the most
weight — they drive the hike-vs-cut debate. In a growth scare, flip to ISM + claims.

Upcoming DATES are REAL. Data releases come from the St. Louis Fed FRED
`/releases/dates` endpoint (the same free FRED key the gauge uses), matched by
release name into the tiers above. FOMC decisions, FOMC minutes, the Beige Book
and the Fed Chair's remarks come from the Federal Reserve's own pages
(federalreserve.gov json/calendar.json + monetarypolicy/fomccalendars.htm, via
`fed_schedule`, 2026-10-07); FOMC_DECISION_DATES is only the floor for a year
neither page answered. FRED's "FOMC Press Release" is padding and is dropped.
Plus an earnings-ahead list for the names Ajay tracks (long-term roster +
leaderboard), so specific high-volatility days are flagged.

NOT advice — a heads-up on what data could move the regime, not a forecast.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import fed_schedule

log = logging.getLogger("macro_calendar")

TTL_SEC = 6 * 3600
DEFAULT_DAYS = 14

REGIME_WEIGHTING = ("Right now inflation + labor-strength prints carry the most weight — "
                    "they drive the hike-vs-cut debate. In a growth scare, flip and weight "
                    "ISM + jobless claims.")

TIER_LABELS = {1: "Market movers", 2: "Trend shapers", 3: "Context"}

# The slide's framework — shown as a reference so every tier-1/2/3 event type is
# visible even when FRED has no firm upcoming date for it. The Fed-calendar kinds
# (FED_KIND_TIERS, below _RELEASE_TIERS) are appended from their constants.
_BASE_TAXONOMY = {
    "1": ["Jobs report (NFP, unemployment, wages)", "CPI",
          "FOMC decision + dot plot + presser", "Core PCE"],
    "2": ["ISM mfg & services", "Retail sales", "JOLTS", "ADP",
          "Jobless claims", "GDP", "Fed-speaker remarks"],
    "3": ["Consumer & business confidence", "Housing starts / permits",
          "Regional Fed indices", "Trade balance"],
}

# FLOOR only — the Fed's own pages are primary (fed_schedule, 2026-10-07). No code
# in this module iterates this name; it is kept for callers and tests.
FOMC_DECISION_DATES = fed_schedule.FLOOR_DECISION_DATES

# FRED release names that CONTAIN a tier needle but are NOT the print. Checked BEFORE the needle
# table, so they never match any tier. Measured 2026-09-24 on FRED /releases/dates (30-day window),
# every name that double-matched a kind, with its FRED release_id:
#   469 "State Unemployment Insurance Weekly Claims Report"  Fridays — state detail of 180's Thursday print
#   345 "Research Consumer Price Index"                       shadow of 10 (CPI)
#   140 "Gross Domestic Product by State" · 331 "… by Industry" · 263 "Debt to Gross Domestic Product Ratios"  shadows of 53
#   391 "Personal Consumption Expenditures by State"          shadow of 54 (Core PCE)
#   436 "Monthly Retail Trade and Food Services" · 494 "Chicago Fed Advance Retail Trade Summary"  shadows of 9
# The (kind, date) dedupe hides a shadow only when it lands on the print's date; 469 (Fri) and 494
# (10-08) did not, so "Jobless claims" printed twice a week from 2026-06-17 and a phantom "Retail
# sales" shipped, until this. Fixture: tests/fixtures/fred_release_dates_2026_09_24.json.
_RELEASE_EXCLUDE = (
    "state unemployment insurance weekly claims",
    " by state", " by industry",
    "debt to gross domestic product",
    "research consumer price index",
    "monthly retail trade and food services",
    "chicago fed advance retail trade",
)

# Match FRED release names → (kind, tier, short label). First match wins; order
# matters (specific before generic). Case-insensitive substring match.
_RELEASE_TIERS = [
    ("employment situation",          ("jobs", 1, "Jobs report (NFP)")),
    ("consumer price index",          ("cpi", 1, "CPI")),
    ("fomc",                          ("fomc", 1, "FOMC decision")),
    ("federal open market",           ("fomc", 1, "FOMC decision")),
    ("personal income and outlays",   ("pce", 1, "Core PCE")),
    ("personal consumption expenditures", ("pce", 1, "Core PCE")),
    # Tier 2 — trend shapers
    ("ism ",                          ("ism", 2, "ISM")),
    ("manufacturing pmi",             ("ism", 2, "ISM / PMI")),
    ("services pmi",                  ("ism", 2, "ISM services")),
    ("advance monthly sales for retail", ("retail", 2, "Retail sales")),
    ("retail trade",                  ("retail", 2, "Retail sales")),
    ("job openings and labor turnover", ("jolts", 2, "JOLTS")),
    ("adp ",                          ("adp", 2, "ADP payrolls")),
    ("unemployment insurance weekly claims", ("claims", 2, "Jobless claims")),
    ("gross domestic product",        ("gdp", 2, "GDP")),
    ("producer price index",          ("ppi", 2, "PPI")),
    # Tier 3 — context
    ("consumer confidence",           ("confidence", 3, "Consumer confidence")),
    ("surveys of consumers",          ("confidence", 3, "UMich sentiment")),
    ("new residential construction",  ("housing", 3, "Housing starts/permits")),
    ("housing starts",                ("housing", 3, "Housing starts")),
    ("empire state",                  ("regional_fed", 3, "Empire State (NY Fed)")),
    ("philadelphia fed",              ("regional_fed", 3, "Philly Fed")),
    ("international trade",            ("trade", 3, "Trade balance")),
]

# Event kinds read from the Federal Reserve's own calendar (fed_schedule, 2026-10-07).
# HIS CALL (spec §7.1-7.3): minutes T2 (News, never "next market mover"), Beige Book T3
# (gauge page only), Fed Chair remarks T2 (Chair only, every topic).
FED_KIND_TIERS = {"fomc_minutes": 2, "beige_book": 3, "fed_chair": 2}
FED_KIND_LABELS = {"fomc_minutes": "FOMC minutes", "beige_book": "Beige Book",
                   "fed_chair": "Fed Chair remarks"}
PAST_WORD = {"fed_chair": "began"}                       # default "released"
# Kinds whose time of day the Fed publishes WITHOUT a stated time zone: neither
# json/calendar.json nor newsevents/calendar.htm names one (critic, 2026-10-07),
# and remarks given abroad are unverified — so their label carries no " ET".
# FOMC decisions / pressers / minutes are ET by publication and keep it.
TIME_ZONE_UNSTATED_KINDS = frozenset({"fed_chair"})
# The kinds past_events can produce (FRED kinds + FOMC decisions) — the 🛡️ Resiliency
# event set. Fed-calendar kinds are deliberately NOT in it.
HISTORY_KINDS = frozenset(k for _n, (k, _t, _l) in _RELEASE_TIERS)


def _build_taxonomy(base: dict, tiers: dict, labels: dict) -> dict:
    out = {k: list(v) for k, v in base.items()}
    for kind, tier in tiers.items():
        out.setdefault(str(tier), []).append(labels[kind])
    return out


TIER_TAXONOMY = _build_taxonomy(_BASE_TAXONOMY, FED_KIND_TIERS, FED_KIND_LABELS)


def _match_tier(release_name: str):
    nm = (release_name or "").lower()
    if any(x in nm for x in _RELEASE_EXCLUDE):
        return None
    for needle, meta in _RELEASE_TIERS:
        if needle in nm:
            return meta
    return None


def _fred_releases(days: int) -> list[dict]:
    """Upcoming FRED release dates, matched into our tiers. Real scheduled dates."""
    try:
        from sepa import fred
        key = fred.api_key()
    except Exception:
        key = os.getenv("FRED_API_KEY", "").strip()
    if not key:
        return []
    import requests
    today = _today_et()
    end = today + timedelta(days=days)
    params = {"api_key": key, "file_type": "json",
              "include_release_dates_with_no_data": "true",
              "realtime_start": str(today), "realtime_end": str(end),
              "sort_order": "asc", "limit": 1000}
    rows = None
    for attempt, tmo in enumerate((45, 60)):       # one retry — the endpoint is SLOW (often >25s)
        try:
            r = requests.get("https://api.stlouisfed.org/fred/releases/dates",
                             params=params, timeout=tmo)
            if r.status_code != 200:
                log.warning("FRED releases/dates HTTP %s", r.status_code)
                return []
            rows = (r.json() or {}).get("release_dates") or []
            break
        except Exception as exc:
            log.warning("FRED releases/dates attempt %d failed: %s", attempt + 1, _safe_reason(exc))
    if rows is None:
        return []

    out, seen = [], set()
    for x in rows:
        d, nm = x.get("date"), x.get("release_name")
        if not d or not nm or d < str(today) or d > str(end):
            continue
        meta = _match_tier(nm)
        if not meta:
            continue
        kind, tier, label = meta
        if kind == "fomc":
            # FOMC has no firm FRED date (padded onto every day) — sourced from
            # the authoritative Fed schedule in _fomc_events() instead.
            continue
        dedup = (kind, d)
        if dedup in seen:
            continue
        seen.add(dedup)
        out.append({"date": d, "kind": kind, "tier": tier, "label": label, "source": nm})

    # Drop "no-data padding": a continuously-pending release (e.g. FOMC Press
    # Release) shows a row on EVERY day in the window. A real scheduled print
    # lands on one day (claims: weekly → ≤3 at the default 14-day window). >3
    # distinct dates = padding noise. ⚠ At days >= 21 a weekly print has 4+ dates
    # and THIS FILTER DROPS IT — open, see docs/sepa/macro_event_overlay.md
    # 2026-09-24 (pinned by an xfail(strict=True) in
    # tests/test_macro_calendar_claims_2026_09_24.py). No threshold change here.
    from collections import Counter
    date_count = Counter(e["source"] for e in out)
    out = [e for e in out if date_count[e["source"]] <= 3]
    out.sort(key=lambda e: (e["date"], e["tier"]))
    return out


# ---------------------------------------------------------------------------
# PAST events — the dated history of T1/T2 prints (2026-09-30, the 🛡️ Resiliency
# tab). `_fred_releases` reads UPCOMING dates only and its >3-dates padding filter
# drops every claims week, so history is read PER RELEASE from FRED's
# `/fred/release/dates` (≈1.5 s an id, measured 2026-09-30).
# ---------------------------------------------------------------------------
# FRED releases whose PAST dates feed the event history. Ids measured 2026-09-24/-30
# (docs/sepa/macro_event_overlay.md table + the resiliency spec §1.1). Each id only
# SELECTS a fetch; the release NAME is classified by _match_tier (the one classifier).
#   50 Employment Situation · 10 CPI · 54 Personal Income and Outlays · 53 GDP ·
#   9 Advance Retail Sales · 192 JOLTS · 194 ADP · 180 UI Weekly Claims · 46 PPI
# FOMC (FRED 101, padded onto every day) is NEVER fetched — the Fed schedule
# (fed_schedule.load(): LKG of the Fed's own pages ∪ the floor) is the source.
HISTORY_RELEASE_IDS = (50, 10, 54, 53, 9, 192, 194, 180, 46)
HISTORY_UNSOURCED = ("ISM mfg & services", "Fed-speaker remarks")   # taxonomy kinds with no dated history
HISTORY_TTL_SEC = TTL_SEC
HISTORY_FOMC_SOURCE = "Federal Reserve FOMC calendar"
HISTORY_FOMC_LABEL = "FOMC decision"
FRED_BASE = "https://api.stlouisfed.org/fred/"

_HISTORY_CACHE: dict = {}              # (start_iso, end_iso, max_tier) -> {"at", "data"}
_HISTORY_LOCK = threading.Lock()


class FredHTTPError(Exception):
    """A non-200 FRED answer. Carries ONLY the status code — never the URL
    (the URL holds the api_key)."""

    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.code = code


def _fred_key() -> str:
    try:
        from sepa import fred
        return fred.api_key() or ""
    except Exception:
        return os.getenv("FRED_API_KEY", "").strip()


def _fred_get(path: str, params: dict) -> dict:
    """GET FRED `path` with the key. Raises FredHTTPError on a non-200."""
    key = _fred_key()
    if not key:
        raise LookupError("no FRED key")
    import requests
    r = requests.get(FRED_BASE + path, params={**params, "api_key": key, "file_type": "json"},
                     timeout=(15, 30))
    if r.status_code != 200:
        raise FredHTTPError(r.status_code)
    return r.json() or {}


def _safe_reason(exc: BaseException) -> str:
    """The error class or the HTTP code — NEVER str(exc): a requests error
    string carries the request URL, api_key included."""
    if isinstance(exc, FredHTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, LookupError) and str(exc) == "no FRED key":
        return "no FRED key"
    return type(exc).__name__


def _iso(d) -> str:
    return d.isoformat() if hasattr(d, "isoformat") else str(d)[:10]


def _compute_past_events(start, end, max_tier: int, fetch) -> dict:
    s_iso, e_iso = _iso(start)[:10], _iso(end)[:10]
    events: list = []
    errors: list = []
    answered = 0
    seen: set = set()
    for rid in HISTORY_RELEASE_IDS:
        try:
            rel = fetch("release", {"release_id": rid}) or {}
            name = ((rel.get("releases") or [{}])[0] or {}).get("name") or ""
            meta = _match_tier(name)
            if not meta or meta[0] == "fomc":
                answered += 1
                continue
            kind, tier, label = meta
            if tier > max_tier:
                answered += 1
                continue
            got = fetch("release/dates", {
                "release_id": rid, "realtime_start": s_iso, "realtime_end": "9999-12-31",
                "include_release_dates_with_no_data": "false", "sort_order": "asc",
                "limit": 10000}) or {}
            answered += 1
        except Exception as exc:                                # noqa: BLE001
            reason = _safe_reason(exc)
            log.warning("FRED release %s history failed: %s", rid, reason)
            errors.append({"release_id": rid, "reason": reason})
            continue
        for x in got.get("release_dates") or []:
            d = str((x or {}).get("date") or "")[:10]
            if len(d) != 10 or d < s_iso or d > e_iso or (kind, d) in seen:
                continue
            seen.add((kind, d))
            events.append({"date": d, "kind": kind, "tier": tier, "label": label,
                           "source": name, "release_id": rid})
    if max_tier >= 1:
        try:
            decision_days = [d["date"] for d in fed_schedule.load()["decisions"]]
        except Exception as exc:                                # noqa: BLE001
            log.warning("Fed schedule unavailable for history: %s", type(exc).__name__)
            decision_days = [d["date"] for d in fed_schedule.merge(None, None, _today_et())["decisions"]]
        for d in decision_days:
            if s_iso <= d <= e_iso and ("fomc", d) not in seen:
                seen.add(("fomc", d))
                events.append({"date": d, "kind": "fomc", "tier": 1,
                               "label": HISTORY_FOMC_LABEL, "source": HISTORY_FOMC_SOURCE,
                               "release_id": None})
    events.sort(key=lambda e: (e["date"], e["tier"], e["kind"]))
    return {"events": events, "errors": errors, "unsourced": list(HISTORY_UNSOURCED),
            "start": s_iso, "end": e_iso, "available": answered > 0}


def past_events(start, end, *, max_tier: int = 2, fetch=None, force: bool = False) -> dict:
    """The dated T1/T2 history between `start` and `end` (inclusive, ISO days).

    {"events": [{date, kind, tier, label, source, release_id}],
     "errors": [{release_id, reason}], "unsourced": list(HISTORY_UNSOURCED),
     "start": iso, "end": iso, "available": bool}

    Events sorted (date, tier), deduped on (kind, date), tier <= max_tier. FRED
    per-release dates for HISTORY_RELEASE_IDS, each release NAME classified by
    `_match_tier`; FOMC rows from the Fed schedule's decision days (release_id
    None) — decisions only, never minutes / Beige / remarks. A
    release whose name matches no tier, or kind == "fomc", contributes nothing.
    Soft-fails PER release (error row; reason = the exception class or
    "HTTP <code>", NEVER str(exc)). available = at least one FRED release
    answered. Cached in-process per (start, end, max_tier) for HISTORY_TTL_SEC
    behind its own lock (double-checked, like get_macro_calendar) — only a
    clean read (no error rows) is cached. `fetch(path, params) -> dict` is
    injectable (tests; an injected fetch bypasses the cache)."""
    if fetch is not None:
        return _compute_past_events(start, end, max_tier, fetch)
    key = (_iso(start)[:10], _iso(end)[:10], int(max_tier))

    def _fresh():
        hit = _HISTORY_CACHE.get(key)
        return (None if force or hit is None or (time.time() - hit["at"]) >= HISTORY_TTL_SEC
                else hit["data"])

    got = _fresh()
    if got is not None:
        return got
    with _HISTORY_LOCK:
        got = _fresh()
        if got is not None:
            return got
        data = _compute_past_events(start, end, max_tier, _fred_get)
        if data["available"] and not data["errors"]:
            _HISTORY_CACHE[key] = {"at": time.time(), "data": data}
        return data


def _sched_or_load(sched: Optional[dict]) -> dict:
    if isinstance(sched, dict):
        return sched
    try:
        return fed_schedule.load(today=_today_et())
    except Exception as exc:                                    # noqa: BLE001
        log.warning("Fed schedule load failed: %s", type(exc).__name__)
        return fed_schedule.merge(None, None, _today_et())


def time_label(hhmm, et: bool = True) -> Optional[str]:
    """'14:00' → '2:00 pm ET' ('2:00 pm' with et=False). Junk → None."""
    if not isinstance(hhmm, str) or len(hhmm) != 5 or hhmm[2] != ":":
        return None
    try:
        h, m = int(hhmm[:2]), int(hhmm[3:])
    except ValueError:
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    ap = "am" if h < 12 else "pm"
    return f"{(h % 12) or 12}:{m:02d} {ap}" + (" ET" if et else "")


def _decision_detail(d: dict) -> Optional[str]:
    bits = []
    if d.get("sep") is True:
        bits.append("dot plot (SEP)")
    pl = time_label(d.get("presser_time_et"))
    if pl:
        bits.append(f"press conference {pl}")
    return " · ".join(bits) or None


def _decision_row(d: dict) -> dict:
    return {"date": d["date"], "kind": "fomc", "tier": 1, "label": HISTORY_FOMC_LABEL,
            "source": d.get("source"), "time_et": d.get("time_et"),
            "detail": _decision_detail(d), "sep": d.get("sep")}


def _fomc_events(days: int, sched: Optional[dict] = None) -> list[dict]:
    """FOMC decision days inside the window, from the Fed's own schedule
    (fed_schedule: LKG of federalreserve.gov ∪ the floor) — NOT FRED's padded
    press-release rows. Always tier 1. The window 'today' is ET (matching
    imminent_events / _today_et) — otherwise the day-of FOMC drops off hours
    early once UTC rolls past midnight while it's still that day in ET."""
    today = _today_et()
    end = (today + timedelta(days=days)).isoformat()
    t_iso = today.isoformat()
    out = []
    for d in _sched_or_load(sched).get("decisions") or []:
        if isinstance(d, dict) and t_iso <= str(d.get("date") or "") <= end:
            out.append(_decision_row(d))
    return out


def _fed_events(days: int, sched: Optional[dict] = None) -> list[dict]:
    """FOMC minutes, Beige Book and Fed Chair remarks inside the window, from
    the Fed's calendar.json LKG only — never derived."""
    sched = _sched_or_load(sched)
    today = _today_et()
    t_iso, end = today.isoformat(), (today + timedelta(days=days)).isoformat()
    rows = []

    def _add(kind, r, detail):
        d = str(r.get("date") or "")
        if t_iso <= d <= end:
            rows.append({"date": d, "kind": kind, "tier": FED_KIND_TIERS[kind],
                         "label": FED_KIND_LABELS[kind], "source": r.get("source"),
                         "time_et": r.get("time_et"), "detail": detail})

    for r in sched.get("minutes") or []:
        if isinstance(r, dict):
            _add("fomc_minutes", r, f"Meeting of {r['meeting']}" if r.get("meeting") else None)
    for r in sched.get("beige") or []:
        if isinstance(r, dict):
            _add("beige_book", r, None)
    for r in sched.get("remarks") or []:
        if isinstance(r, dict) and r.get("chair") is True:
            _add("fed_chair", r, f"{r.get('what')} · {r.get('who')} — {r.get('topic')}"
                 if r.get("topic") else f"{r.get('what')} · {r.get('who')}")
    rows.sort(key=lambda e: (e["date"], e.get("time_et") or "99:99"))
    out, seen = [], set()
    for e in rows:
        if (e["kind"], e["date"]) in seen:
            continue
        seen.add((e["kind"], e["date"]))
        out.append(e)
    return out


def next_fomc(sched: Optional[dict] = None) -> Optional[dict]:
    """The first FOMC decision on or after today (ET). Not window-limited."""
    t_iso = _today_et().isoformat()
    for d in _sched_or_load(sched).get("decisions") or []:
        if isinstance(d, dict) and str(d.get("date") or "") >= t_iso:
            return _decision_row(d)
    return None


def _earnings_universe() -> list[str]:
    tk: set = set()
    try:
        from longterm import _TICKERS
        tk.update(_TICKERS)
    except Exception:
        pass
    try:
        from sepa import leaderboard
        for l in (leaderboard.leaderboard(n=25).get("leaders") or []):
            if l.get("symbol"):
                tk.add(l["symbol"])
    except Exception:
        pass
    try:
        from sepa.scanner import load_watchlist
        for w in (load_watchlist() or []):
            s = (w.get("symbol") or w.get("ticker")) if isinstance(w, dict) else w
            if isinstance(s, str):
                tk.add(s.upper())
    except Exception:
        pass
    return sorted(t for t in tk if isinstance(t, str) and t)


def _earnings_ahead(days: int) -> list[dict]:
    tickers = _earnings_universe()
    if not tickers:
        return []
    try:
        from catalysts.calendar import _next_earnings
        from concurrent.futures import ThreadPoolExecutor
    except Exception:
        return []
    today = _today_et()
    cutoff = today + timedelta(days=days)
    out = []
    try:
        with ThreadPoolExecutor(max_workers=12) as ex:
            for r in ex.map(_next_earnings, tickers):
                if not r or not r.get("date"):
                    continue
                try:
                    d = datetime.strptime(r["date"], "%Y-%m-%d").date()
                except Exception:
                    continue
                if today <= d <= cutoff:
                    out.append({"date": r["date"], "ticker": r["ticker"]})
    except Exception as exc:
        log.debug("earnings-ahead failed: %s", exc)
    out.sort(key=lambda e: (e["date"], e["ticker"]))
    return out


def _schedule_for_compute() -> dict:
    today = _today_et()
    try:
        return fed_schedule.current(today=today)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("Fed schedule refresh failed: %s", type(exc).__name__)
    try:
        return fed_schedule.load(today=today)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("Fed schedule load failed: %s", type(exc).__name__)
    out = fed_schedule.merge(None, None, today)
    out["status"] = None
    return out


def compute(days: int = DEFAULT_DAYS) -> dict:
    t0 = time.time()
    # FRED gives the broad release calendar (CPI/jobs/PCE/ISM/...); the Fed's own
    # calendar gives FOMC decisions, minutes, Beige Book and Chair remarks.
    sched = _schedule_for_compute()
    macro = _fred_releases(days) + _fomc_events(days, sched) + _fed_events(days, sched)
    macro.sort(key=lambda e: (e["date"], e["tier"], e.get("time_et") or "99:99"))
    earnings = _earnings_ahead(days)

    by_tier = {1: [], 2: [], 3: []}
    for e in macro:
        by_tier[e["tier"]].append(e)
    next_t1 = macro and next((e for e in macro if e["tier"] == 1), None)

    # group earnings by date for "that day" awareness
    edays: dict = {}
    for e in earnings:
        edays.setdefault(e["date"], []).append(e["ticker"])
    earnings_by_day = [{"date": d, "tickers": sorted(set(t)), "n": len(set(t))}
                       for d, t in sorted(edays.items())]

    return {
        "generated_at": int(time.time()),
        "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_sec": round(time.time() - t0, 2),
        "days": days,
        "tier_labels": TIER_LABELS,
        "tier_taxonomy": TIER_TAXONOMY,
        "regime_weighting": REGIME_WEIGHTING,
        "macro": macro,
        "macro_by_tier": {str(k): v for k, v in by_tier.items()},
        "next_tier1": next_t1 or None,
        "next_fomc": next_fomc(sched),
        "fed": sched.get("status"),
        "earnings": earnings,
        "earnings_by_day": earnings_by_day,
        "n_macro": len(macro), "n_earnings": len(earnings),
        "available": bool(macro or earnings),
        "disclaimer": ("A heads-up on what data could move the regime + which days carry "
                       "earnings risk — not a forecast or advice."),
    }


_CACHE: dict = {"at": 0.0, "data": None}
# One cold FRED fetch at a time; concurrent cold callers wait for it, never spawn their own.
_CACHE_LOCK = threading.Lock()


def get_macro_calendar(force: bool = False, days: int = DEFAULT_DAYS) -> dict:
    def _fresh() -> bool:
        return (not force and _CACHE["data"] is not None
                and (time.time() - _CACHE["at"]) < TTL_SEC
                and _CACHE["data"].get("days") == days)

    if _fresh():
        return _CACHE["data"]
    with _CACHE_LOCK:
        if _fresh():                    # double-check: the thread we waited on filled it
            return _CACHE["data"]
        data = compute(days)
        _CACHE.update(at=time.time(), data=data)
        return data


def _today_et():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date()
    except Exception:
        return datetime.now(timezone.utc).date()


def _now_et() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:                                           # noqa: BLE001
        return datetime.now(timezone.utc)


def when_fields(date_iso, time_et, kind, *, today=None, now=None) -> Optional[dict]:
    """The ONE read-time 'when' engine. when_label stays today / tomorrow /
    in N days; `past` is True only once a timed event's ET time has passed."""
    try:
        ed = datetime.strptime(str(date_iso)[:10], "%Y-%m-%d").date()
    except Exception:                                           # noqa: BLE001
        return None
    today = today or _today_et()
    du = (ed - today).days
    tl = time_label(time_et, et=kind not in TIME_ZONE_UNSTATED_KINDS)
    past = None
    if du > 0:
        past = False
    elif du == 0 and tl:
        n = now or _now_et()
        past = f"{n.hour:02d}:{n.minute:02d}" >= time_et
    elif du < 0:
        past = True
    return {"days_until": du,
            "when_label": ("today" if du == 0 else "tomorrow" if du == 1 else f"in {du} days"),
            "time_label": tl, "past": past,
            "past_label": f"{PAST_WORD.get(kind, 'released')} {tl}" if past is True and tl else None}


def imminent_events(within_days: int = 5, max_tier: int = 1) -> list:
    """High-impact macro events within the next ``within_days`` ET days
    (tier <= ``max_tier``). The SINGLE source for the holding-diagnosis
    heads-up + the market-gauge outlook allusion — reuses the cached macro
    calendar, so no extra FRED calls. Each row:

        {date, kind, tier, label, days_until, when_label,
         time_et, time_label, detail, past, past_label, source}

    Soft-fails to ``[]``. Days-until / 'tomorrow' is computed in ET because the
    events (FOMC 2pm, CPI 8:30am) are ET-scheduled.
    """
    try:
        events = get_macro_calendar().get("macro") or []
    except Exception:
        return []
    today = _today_et()
    now = None
    out: list = []
    for e in events:
        d = e.get("date")
        if not d or (e.get("tier") or 9) > max_tier:
            continue
        try:
            ed = datetime.strptime(d, "%Y-%m-%d").date()
        except Exception:
            continue
        du = (ed - today).days
        if 0 <= du <= within_days:
            if now is None:
                now = _now_et()
            w = when_fields(d, e.get("time_et"), e.get("kind"), today=today, now=now) or {}
            out.append({
                "date": d, "kind": e.get("kind"), "tier": e.get("tier"),
                "label": e.get("label"),
                "days_until": du,
                "when_label": ("today" if du == 0 else "tomorrow" if du == 1 else f"in {du} days"),
                "time_et": e.get("time_et"), "time_label": w.get("time_label"),
                "detail": e.get("detail"), "past": w.get("past"),
                "past_label": w.get("past_label"), "source": e.get("source"),
            })
    out.sort(key=lambda x: (x["days_until"], x["tier"], x.get("time_et") or "99:99"))
    return out
