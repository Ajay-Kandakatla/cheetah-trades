"""Macro calendar — tiered upcoming data releases for the REGIME check.

The framework is the ZONETRADER618 "Not All Data Is Equal" tiering:
  • TIER 1 — market movers : Jobs report (NFP/unemployment/wages), CPI, FOMC
             decision + dot plot + presser, Core PCE
  • TIER 2 — trend shapers : ISM mfg & services, retail sales, JOLTS, ADP,
             jobless claims, GDP, Fed-speaker remarks
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
    # lands on one (claims: weekly → ≤2) day. >3 distinct dates = padding noise.
    from collections import Counter
    date_count = Counter(e["source"] for e in out)
    out = [e for e in out if date_count[e["source"]] <= 3]
    out.sort(key=lambda e: (e["date"], e["tier"]))
    return out


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


def get_macro_calendar(force: bool = False, days: int = DEFAULT_DAYS) -> dict:
    now = time.time()
    if not force and _CACHE["data"] is not None and (now - _CACHE["at"]) < TTL_SEC \
            and _CACHE["data"].get("days") == days:
        return _CACHE["data"]
    data = compute(days)
    _CACHE.update(at=now, data=data)
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
