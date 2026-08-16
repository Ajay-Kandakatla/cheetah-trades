"""Are our quarterly data sources still reporting the CURRENT period?

Ajay 2026-08-16, after opening the APGE institutional-flow modal and seeing
"As of Q1 2026 (Mar 31, 2026)" two days after the Q2 deadline: *"The
accumulations are dated now can you check… Make a rule to check for updated
date.. Monthly"*.

WHY A CADENCE CHECK IS DIFFERENT FROM A STALENESS CHECK
-------------------------------------------------------
Everything else in health_audit asks "how old is this file?". That question is
useless for 13F: the *cache* refreshes every 24h and is perfectly fresh while
the *content* inside it is a quarter behind. On 2026-08-16 the APGE payload had
been fetched minutes earlier and still said Q1. A freshness check on
`cached_at` would have called that green.

So this asks a different question: given today's date, which 13F quarter SHOULD
be public by now, and is that what the data actually contains?

THE 45-DAY RULE
---------------
SEC Rule 13f-1 gives institutions 45 calendar days after quarter end to file.
So Q2 (Jun 30) is due Aug 14, Q3 (Sep 30) due Nov 14, Q4 (Dec 31) due Feb 14,
Q1 (Mar 31) due May 15. We allow a GRACE period on top, because funds file
across the whole deadline week and the upstream provider then takes its own
time to ingest — flagging on day 46 would cry wolf every quarter.

WHAT IT DOES NOT DO
-------------------
It never pushes. Severity is WARN by design: a data provider lagging a quarter
is worth knowing on the monthly sweep, not worth a phone buzz — Ajay's push
keep-set is deliberately three kinds and this is not one of them.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

log = logging.getLogger("observability.period_freshness")

# SEC Rule 13f-1 filing deadline, in calendar days after the quarter end.
FILING_LAG_DAYS = 45

# Extra days before we call the data late. Funds file right up to the deadline
# and the provider ingests afterwards, so day 46 is normal, not broken.
GRACE_DAYS = 21

# Share of tickers that must have rolled to the expected quarter before we
# call the roll "done". Never 100%: small caps keep a tail of funds that file
# late or not at all, so a strict rule would sit red forever.
ROLLED_FRACTION_OK = 0.50

# Tickers sampled from the cache. The question is "did the provider roll?",
# which a sample answers as well as a full scan and far more cheaply.
SAMPLE_SIZE = 300


# ---------------------------------------------------------------------------
# pure date logic
# ---------------------------------------------------------------------------
def quarter_end(year: int, q: int) -> date:
    """Last calendar day of quarter `q`. PURE."""
    return {1: date(year, 3, 31), 2: date(year, 6, 30),
            3: date(year, 9, 30), 4: date(year, 12, 31)}[q]


def quarter_of(d: date) -> tuple:
    """(year, quarter) containing `d`. PURE."""
    return (d.year, (d.month - 1) // 3 + 1)


def label_for(d: date) -> str:
    """'Q2 2026' for a quarter-end date. PURE."""
    y, q = quarter_of(d)
    return f"Q{q} {y}"


def filing_due(qe: date) -> date:
    """When 13Fs for the quarter ending `qe` are due. PURE."""
    return qe + timedelta(days=FILING_LAG_DAYS)


def expected_13f_quarter(today: Optional[date] = None,
                         grace_days: int = GRACE_DAYS) -> date:
    """The most recent quarter end whose filing deadline (plus grace) has passed.

    This is the quarter the data SHOULD be showing. PURE — no I/O, so the
    quarter-boundary behaviour is testable without waiting for a quarter.
    """
    today = today or date.today()
    y, q = quarter_of(today)
    # Walk back from the current quarter until one is comfortably due.
    for _ in range(8):
        q -= 1
        if q == 0:
            q, y = 4, y - 1
        qe = quarter_end(y, q)
        if today >= filing_due(qe) + timedelta(days=grace_days):
            return qe
    return quarter_end(y, q)


# ---------------------------------------------------------------------------
# the audit
# ---------------------------------------------------------------------------
def audit_whales_cache(today: Optional[date] = None,
                       sample_size: int = SAMPLE_SIZE,
                       coll=None) -> dict:
    """What quarter does the institutional-holder cache actually contain?

    Reports BOTH the dominant quarter per ticker and how many payloads mix
    quarters, because mixing is its own problem: the modal sums bought/sold
    dollars across funds, and adding a fund's Q1 delta to another's Q2 delta
    produces a "net inflow" that describes no single period.
    """
    today = today or date.today()
    expected = expected_13f_quarter(today)
    expected_s = expected.isoformat()

    if coll is None:
        try:
            from supply_demand import whales
            coll = whales._cache_coll()
        except Exception as exc:
            return {"ok": False, "reason": f"cache unavailable: {exc}",
                    "expected_quarter": expected_s}
    if coll is None:
        return {"ok": False, "reason": "cache unavailable",
                "expected_quarter": expected_s}

    n = rolled = mixed = 0
    seen_dominants: dict = {}
    try:
        cursor = coll.find({}, {"ticker": 1, "payload.period": 1}).limit(int(sample_size))
        for doc in cursor:
            per = ((doc.get("payload") or {}).get("period")) or {}
            dom = per.get("dominant")
            if not dom:
                continue
            n += 1
            seen_dominants[dom] = seen_dominants.get(dom, 0) + 1
            if dom >= expected_s:
                rolled += 1
            if per.get("earliest") != per.get("latest"):
                mixed += 1
    except Exception as exc:
        return {"ok": False, "reason": f"cache read failed: {exc}",
                "expected_quarter": expected_s}

    if not n:
        return {"ok": False, "reason": "no cached payloads carry period info",
                "expected_quarter": expected_s}

    rolled_pct = round(100.0 * rolled / n, 1)
    ok = (rolled / n) >= ROLLED_FRACTION_OK
    newest = max(seen_dominants) if seen_dominants else None

    return {
        "ok": ok,
        "source": "whales_cache (institutional 13F holders)",
        "expected_quarter": expected_s,
        "expected_label": label_for(expected),
        "filing_due": filing_due(expected).isoformat(),
        "sampled": n,
        "rolled": rolled,
        "rolled_pct": rolled_pct,
        "newest_seen": newest,
        "newest_seen_label": label_for(date.fromisoformat(newest)) if newest else None,
        "mixed_quarter_payloads": mixed,
        "mixed_pct": round(100.0 * mixed / n, 1),
        "detail": (
            f"{rolled_pct}% of {n} sampled tickers report {label_for(expected)} "
            f"or newer" if ok else
            f"only {rolled_pct}% of {n} sampled tickers have rolled to "
            f"{label_for(expected)} (due {filing_due(expected).isoformat()}); "
            f"newest seen is {label_for(date.fromisoformat(newest)) if newest else 'none'}"
        ),
    }


def report(today: Optional[date] = None) -> dict:
    """Every quarterly-cadence source, in one payload. One entry today; the
    shape is a list so 13D/G and fund-flow sources can join without a new
    endpoint."""
    today = today or date.today()
    checks = [dict(audit_whales_cache(today), name="13f_institutional_holders")]
    return {
        "generated_on": today.isoformat(),
        "all_ok": all(c.get("ok") for c in checks),
        "checks": checks,
        "note": ("Quarterly sources lag by design — SEC Rule 13f-1 allows 45 days "
                 "after quarter end, and the data provider ingests after that. "
                 "This flags a source that has NOT rolled well past its deadline."),
    }


if __name__ == "__main__":                                   # pragma: no cover
    import json
    print(json.dumps(report(), indent=2))
