"""WHO this app tracks. One row per public trader.

Ajay 2026-09-12: *"Also track their mentions for me.. Martin Luk +969.8%
(stocks)"* — after the GnT tab, a second champion from the same competition.

Every claim here is CITED to where it was read, and read on 2026-09-12 — never
recalled. A contest return is not a transferable track record: those divisions
permit concentration and leverage this app's own risk rules forbid, and both of
these traders post ideas, not a portfolio.

HOW OFTEN THEY ACTUALLY POST is part of the record, because it decides what a
"daily" tracker can possibly find:

  GnT_Trades  posts most days; three fresh ideas landed on one Friday evening.
  martinlukkt posts RARELY — on 2026-09-12 his newest post was 57 days old.
              A daily check on him will usually find nothing, and that is the
              honest expectation, not a broken fetch.
"""
from __future__ import annotations

from typing import Optional

TRADERS: list[dict] = [
    {
        "key": "gnt",
        "handle": "GnT_Trades",
        "display": "Tito Adhikary",
        "usic": {
            "year": 2025,
            "division": "$20,000+ Enhanced Growth",
            "return_pct": 2115.1,
            "rank": 1,
            "source": "@USICOfficial, quoted in his pinned post 2026-01-29",
        },
        "style": ("Options and swing trades on breakouts; posts forward ideas "
                  "AND past-tense recaps of closed trades, several of them puts."),
    },
    {
        "key": "martinluk",
        "handle": "martinlukkt",
        "display": "Martin Luk",
        "usic": {
            "year": 2025,
            "division": "Stocks",
            "return_pct": 969.0,
            "rank": 1,
            "source": ("his own X bio, read 2026-09-12: \"Trader | +969% in US "
                       "Investing Championship 2025\"; corroborated by "
                       "@TraderLion and @USICOfficial coverage"),
        },
        # Ajay wrote "+969.8%"; his bio and TraderLion both say 969%. The
        # difference is not resolvable from a public source, so the figure
        # stored is the one his own bio states and the decimal is NOT invented.
        "style": ("Stage-2 pullback entries on leaders; posts charts and "
                  "observations rather than trade calls. Posts infrequently."),
    },
]

BY_KEY = {t["key"]: t for t in TRADERS}
BY_HANDLE = {t["handle"].lower(): t for t in TRADERS}
DEFAULT_KEY = "gnt"

# The shared caveat. Lives here so every surface prints the SAME sentence and
# none of them can quietly soften it.
DISCLAIMER = (
    "Their posts, NOT advice and NOT a portfolio. They post forward ideas AND "
    "past-tense recaps of closed trades, several of them PUTS — read the "
    "sentence, not the ticker. A championship return is not a transferable "
    "track record. Nothing here gates a scan, an alert or a lane."
)


def get(key: str) -> Optional[dict]:
    return BY_KEY.get((key or "").strip().lower())


def keys() -> list[str]:
    return [t["key"] for t in TRADERS]
