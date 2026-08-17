"""Which symbols in the universe have stopped printing bars?

Ajay 2026-08-16, on the EchoStar detail page: *"look at this issue with SATS
stocks"*. The app said SATS was delisted or acquired. It was trading at $91.89 —
EchoStar had renamed to ECHO on 2026-06-24 and our series simply stopped there.

The rename itself is fixed in ``sepa/symbols.py``. This exists because of the
OTHER thing that scan turned up: Block renamed SQ to XYZ on **2025-01-21**, and
the app had been showing a dead SQ for **576 days** without anything noticing.
One wrong name is a bug; a wrong name nobody notices for nineteen months is a
missing check.

WHAT THIS ASKS THAT NOTHING ELSE DOES
-------------------------------------
``health_audit`` asks how old a cache FILE is. ``period_freshness`` asks whether
quarterly CONTENT has rolled. Both would have called SQ green every single day:
its price document refreshed on schedule and its bars parsed cleanly. They were
just the same bars every time.

So this asks a third question — for each symbol we claim to cover, **when did
its newest bar print?** A symbol whose data stops while the market keeps trading
has been renamed, delisted, halted, or dropped by the provider. All four need a
human; none of them announce themselves.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
* **It does not guess the new ticker.** Inferring a rename from "data stopped
  here and this other symbol started there" would eventually splice a different
  company's history into a chart Ajay sizes positions against. It reports the
  stop; a person adds the entry to ``RENAMES`` with evidence.
* **It does not push.** The keep-set on his phone is three kinds and this is not
  one of them. WARN only, visible on /health.
* **It does not fetch.** Cache reads only, so the monthly sweep costs nothing
  and can never itself be the thing that hammers the provider.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

log = logging.getLogger("observability.symbol_liveness")

# Trading sessions a symbol may miss before it is called stopped. Deliberately
# looser than the scan's own 6-session gate (sepa.prices.STALE_MAX_TRADING_DAYS):
# this check exists to catch a permanent stop, and a two-week provider hiccup
# that heals itself is not worth a monthly report entry.
MAX_QUIET_SESSIONS = 10

# Above this share of the universe, the finding is not about the symbols — the
# provider, the warm cron, or Mongo is down. Reporting 1,600 dead tickers would
# bury the one real rename, so the check says so instead and names no symbols.
BREADTH_ALARM_FRACTION = 0.10
# ...but a fraction alone misfires on any small list: scanning three symbols and
# finding one dead is 33%, which is a dead ticker, not an outage. An outage has
# to be broad in absolute terms as well as proportionally.
BREADTH_ALARM_MIN = 25

# The universe to sweep. sp1500_plus is everything the scanner can surface.
UNIVERSE = "sp1500_plus"


def _sessions_between(a, b) -> int:
    """Market sessions from `a` to `b`, Mon-Fri. Holidays over-count harmlessly
    — the threshold has a fortnight of headroom. PURE."""
    import pandas as pd
    return max(0, len(pd.bdate_range(pd.Timestamp(a).normalize(),
                                     pd.Timestamp(b).normalize())) - 1)


def classify(last_bar, today, max_quiet: int = MAX_QUIET_SESSIONS) -> str:
    """``"fresh"``, ``"quiet"`` or ``"stopped"`` for one symbol. PURE.

    ``"quiet"`` is the band between normal and alarming: the symbol is behind
    but not yet worth a person's time. Naming it keeps the report honest about
    the fact that the boundary is a choice, not a fact.
    """
    if last_bar is None:
        return "stopped"
    gap = _sessions_between(last_bar, today)
    if gap <= max_quiet // 2:
        return "fresh"
    return "quiet" if gap <= max_quiet else "stopped"


def scan(symbols_list: Optional[list] = None, today: Optional[date] = None,
         max_quiet: int = MAX_QUIET_SESSIONS, loader=None) -> dict:
    """Last-bar age for every symbol in the universe. Cache reads only.

    ``loader`` is injected so the whole sweep is testable without Mongo or a
    provider; it defaults to ``sepa.prices.load_prices``.
    """
    import pandas as pd

    today = today or date.today()
    if loader is None:
        from sepa import prices
        loader = prices.load_prices
    if symbols_list is None:
        from sepa import universe
        symbols_list = sorted(set(universe.load_universe(UNIVERSE)))

    from sepa import symbols as S

    stopped, quiet, fresh, unreadable = [], [], 0, []
    for sym in symbols_list:
        try:
            df = loader(sym)
        except Exception as exc:
            log.debug("symbol_liveness: %s failed to load: %s", sym, exc)
            unreadable.append(sym)
            continue
        last = None
        if df is not None and len(df):
            last = str(pd.Timestamp(df.index[-1]).date())
        state = classify(last, today, max_quiet)
        row = {"symbol": sym, "last_bar": last,
               "sessions_quiet": (_sessions_between(last, today) if last else None),
               "known_rename": S.rename_of(sym) is not None}
        if state == "stopped":
            stopped.append(row)
        elif state == "quiet":
            quiet.append(row)
        else:
            fresh += 1

    stopped.sort(key=lambda r: -(r["sessions_quiet"] or 10**6))
    total = len(symbols_list)
    broad = (len(stopped) >= BREADTH_ALARM_MIN and bool(total)
             and (len(stopped) / total) > BREADTH_ALARM_FRACTION)

    if broad:
        return {
            "name": "symbol_liveness", "ok": False, "severity": "WARN",
            "generated_on": today.isoformat(), "universe": UNIVERSE,
            "total": total, "fresh": fresh, "stopped": len(stopped),
            "quiet": len(quiet), "unreadable": len(unreadable),
            "symbols": [],
            "detail": (f"{len(stopped)} of {total} symbols have stopped printing "
                       "bars. That is too many to be corporate actions — check "
                       "the provider, the price-warm cron and Mongo before "
                       "reading this as a list of dead tickers."),
        }

    # Anything already in RENAMES is expected to read fresh (the fetch path
    # splices it). One appearing here means the map entry stopped working.
    regressed = [r["symbol"] for r in stopped if r["known_rename"]]

    return {
        "name": "symbol_liveness",
        "ok": not stopped,
        "severity": "WARN",
        "generated_on": today.isoformat(),
        "universe": UNIVERSE,
        "total": total,
        "fresh": fresh,
        "quiet": len(quiet),
        "stopped": len(stopped),
        "unreadable": len(unreadable),
        "symbols": stopped[:50],
        "renames_regressed": regressed,
        "detail": (
            "Symbols whose newest bar is more than "
            f"{max_quiet} sessions old. Each one is a rename, a delisting, a "
            "halt or a provider drop — check the ticker, then either add it to "
            "sepa.symbols.RENAMES with evidence or drop it from the universe. "
            "SQ sat here unnoticed for 576 days."
            + (f" REGRESSED: {', '.join(regressed)} is in RENAMES and still "
               "stale — the splice is broken." if regressed else "")
        ),
    }


def report(today: Optional[date] = None) -> dict:
    today = today or date.today()
    return {"generated_on": today.isoformat(), "checks": [scan(today=today)]}


if __name__ == "__main__":                                   # pragma: no cover
    import json
    print(json.dumps(report(), indent=2))
