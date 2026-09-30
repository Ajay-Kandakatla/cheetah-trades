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

Upcoming DATES are REAL — pulled from the St. Louis Fed FRED `/releases/dates`
endpoint (the same free FRED key the gauge uses) and matched by release name into
the tiers above. FOMC announcements come through FRED's "FOMC Press Release"
release. Plus an earnings-ahead list for the names Ajay tracks (long-term roster +
leaderboard), so specific high-volatility days are flagged.

NOT advice — a heads-up on what data could move the regime, not a forecast.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

log = logging.getLogger("macro_calendar")

TTL_SEC = 6 * 3600
DEFAULT_DAYS = 14

REGIME_WEIGHTING = ("Right now inflation + labor-strength prints carry the most weight — "
                    "they drive the hike-vs-cut debate. In a growth scare, flip and weight "
                    "ISM + jobless claims.")

TIER_LABELS = {1: "Market movers", 2: "Trend shapers", 3: "Context"}

# The slide's framework — shown as a reference so every tier-1/2/3 event type is
# visible even when FRED has no firm upcoming date for it (e.g. FOMC).
TIER_TAXONOMY = {
    "1": ["Jobs report (NFP, unemployment, wages)", "CPI",
          "FOMC decision + dot plot + presser", "Core PCE"],
    "2": ["ISM mfg & services", "Retail sales", "JOLTS", "ADP",
          "Jobless claims", "GDP", "Fed-speaker remarks"],
    "3": ["Consumer & business confidence", "Housing starts / permits",
          "Regional Fed indices", "Trade balance"],
}

# Authoritative FOMC decision days. The rate decision + statement lands on the
# LAST day of each two-day meeting. SOURCE: Federal Reserve FOMC calendar
# (federalreserve.gov/monetarypolicy/fomccalendars.htm), fetched 2026-06-17.
#
# Why hardcoded and not from FRED: FRED's "FOMC Press Release" release has NO
# firm scheduled date — it pads a row onto EVERY day of the realtime window, so
# (a) it can't tell us the real meeting day and (b) the no-data-padding filter in
# _fred_releases drops it entirely. The Fed's published schedule is the only
# reliable source for the actual decision day, so we source it here.
# ⚠ VERIFY ANNUALLY: extend this list each year when the Fed publishes the next
# year's calendar (they release it ~1.5 years ahead).
FOMC_DECISION_DATES = (
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
    today = datetime.now(timezone.utc).date()
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
            log.warning("FRED releases/dates attempt %d failed: %s", attempt + 1, exc)
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
# FOMC (FRED 101, padded onto every day) is NEVER fetched — FOMC_DECISION_DATES is the source.
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
        for d in FOMC_DECISION_DATES:
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
    `_match_tier`; FOMC rows from FOMC_DECISION_DATES (release_id None). A
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


def _fomc_events(days: int) -> list[dict]:
    """FOMC decision days inside the window, from the authoritative Fed schedule
    (FOMC_DECISION_DATES) — NOT FRED's padded press-release rows. Always tier 1.
    FOMC is an ET-scheduled 2pm event, so the window 'today' is ET (matching
    imminent_events / _today_et) — otherwise the day-of FOMC drops off hours
    early once UTC rolls past midnight while it's still that day in ET."""
    today = _today_et()
    end = today + timedelta(days=days)
    out = []
    for d in FOMC_DECISION_DATES:
        try:
            dd = datetime.strptime(d, "%Y-%m-%d").date()
        except Exception:
            continue
        if today <= dd <= end:
            out.append({"date": d, "kind": "fomc", "tier": 1,
                        "label": "FOMC decision",
                        "source": "Federal Reserve FOMC calendar"})
    return out


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
    today = datetime.now(timezone.utc).date()
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


def compute(days: int = DEFAULT_DAYS) -> dict:
    t0 = time.time()
    # FRED gives the broad release calendar (CPI/jobs/PCE/ISM/...); the Fed's
    # published schedule gives the one event FRED can't pin — FOMC. Merge + sort.
    macro = _fred_releases(days) + _fomc_events(days)
    macro.sort(key=lambda e: (e["date"], e["tier"]))
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


def imminent_events(within_days: int = 5, max_tier: int = 1) -> list:
    """High-impact macro events within the next ``within_days`` ET days
    (tier <= ``max_tier``). The SINGLE source for the holding-diagnosis
    heads-up + the market-gauge outlook allusion — reuses the cached macro
    calendar, so no extra FRED calls. Each row:

        {date, kind, tier, label, days_until, when_label}

    Soft-fails to ``[]``. Days-until / 'tomorrow' is computed in ET because the
    events (FOMC 2pm, CPI 8:30am) are ET-scheduled.
    """
    try:
        events = get_macro_calendar().get("macro") or []
    except Exception:
        return []
    today = _today_et()
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
            out.append({
                "date": d, "kind": e.get("kind"), "tier": e.get("tier"),
                "label": e.get("label"),
                "days_until": du,
                "when_label": ("today" if du == 0 else "tomorrow" if du == 1 else f"in {du} days"),
            })
    out.sort(key=lambda x: (x["days_until"], x["tier"]))
    return out
