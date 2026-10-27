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
  algo888     (StockTwits, added 2026-10-27) posted 30 messages between
              08:14 and 09:56 ET on 2026-10-27 — the stream page the cron
              reads holds about an hour and a half of him.
"""
from __future__ import annotations

from typing import Optional

TRADERS: list[dict] = [
    {
        "key": "gnt",
        "handle": "GnT_Trades",
        "display": "Tito Adhikary",
        "source": "x",
        "gajjala": False,
        "curate": True,
        "profile_url": "https://x.com/GnT_Trades",
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
        "source": "x",
        "gajjala": False,
        "curate": True,
        "profile_url": "https://x.com/martinlukkt",
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
    # 2026-10-27 — Ajay: "Can you track this guy please? and his tickers"
    # (https://stocktwits.com/algo888), then "Add them to Gajjals, they are
    # pretty good". Read off his own StockTwits stream on 2026-10-27; no
    # championship claim anywhere in it, so `usic` is None (never GnT's).
    {
        "key": "algo888", "handle": "algo888", "display": "algo888", "source": "stocktwits",
        "profile_url": "https://stocktwits.com/algo888", "usic": None,
        "gajjala": True,      # Ajay 2026-10-27 "Add them to Gajjals, they are pretty good"
        # 2026-10-27: his ask was "Add them to Gajjals" — Gajjala's scan only; the SEPA / S&D universe (full) is HIS CALL
        "curate": False,
        "profile": {"user_id": 2124563, "followers": 3846, "following": 0, "joined": "2019-06-06",
                    "ideas": 114049,
                    "bio": ("Been Trading the markets since 1999 Equities momentum Swing and Day "
                            "Trader with strong emphasis on Technical Harmonic Buy and Sell Signal "
                            "patterns; pure technical trading: DO NOT FOLLOW ME as I move in & out "
                            "of da markets killing it like a sniper"),
                    "read": "2026-10-27 from his StockTwits stream page"},
        "style": ("In his own words on StockTwits, 2026-10-27 (ET): “$GPUS 75,000 purchase @ .1856 pre=loading for the run up "
                  "to .50 - .70 range then back to 1.00 - 1.25 push” (08:28, message 667426628); “I used to pump  stockd with "
                  "regulatity” (08:52, message 667428643); “@WC25 That;s how I pump.... LOL” (08:55, message 667428905); "
                  "“$GPUS my 100,000 position is up huge!!!” (09:41, message 667434074). His bio: “DO NOT FOLLOW ME as I "
                  "move in & out of da markets killing it like a sniper”."),
    },
]

BY_KEY = {t["key"]: t for t in TRADERS}
BY_HANDLE = {t["handle"].lower(): t for t in TRADERS}
DEFAULT_KEY = "gnt"

# The shared caveat. Lives here so every surface prints the SAME sentence and
# none of them can quietly soften it.
# 2026-10-27: the last sentence gained a dated exception — Ajay: "Add them to
# Gajjals, they are pretty good" (algo888). It used to end "Nothing here gates a
# scan, an alert or a lane." and now names the one scan it feeds.
DISCLAIMER = (
    "Their posts, NOT advice and NOT a portfolio. They post forward ideas AND "
    "past-tense recaps of closed trades, several of them PUTS — read the "
    "sentence, not the ticker. A championship return is not a transferable "
    "track record. Nothing here gates a scan, an alert or a lane — except that, "
    "by Ajay's 2026-10-27 call, an account flagged for Gajjala's tab has its "
    "fresh names ADDED to that scan's candidate list, tagged 📌; GG's own rules "
    "still decide every read and every A+."
)


def get(key: str) -> Optional[dict]:
    return BY_KEY.get((key or "").strip().lower())


def keys() -> list[str]:
    return [t["key"] for t in TRADERS]
