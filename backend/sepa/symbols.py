"""Symbol identity — renames, former names, and per-provider spelling.

Ajay 2026-08-16, looking at EchoStar: *"look at this issue with SATS stocks"*.
The page said **"SATS looks delisted or acquired."** SATS was trading at $91.89
that morning. Two separate defects were producing that one wrong sentence, and
both of them make a live company look dead:

**1. Ticker renames.** EchoStar renamed SATS → ECHO effective 2026-06-24. Our
price frame for SATS ends 2026-06-23 and never resumes, so ``is_stale`` fires
and the UI asserts the company was acquired. Block did the same thing in January
2025 (SQ → XYZ) and **that one has been silently wrong for 576 days** — the app
has been showing a dead SQ this whole time.

**2. Provider spelling for class shares.** Massive serves ``BRK.B``; our universe
spells it ``BRK-B`` (the S&P/Wikipedia convention). Massive returns *nothing* for
the dash form, so ``BRK-B``, ``BF-B`` and ``MOG-A`` have all been quietly served
by the **yfinance fallback** — different provider, different adjustment
convention, same scan. ``CWEN-A`` fails on both spellings at both providers, so
it vanished from the universe entirely.

WHY THE RENAME MAP IS CURATED, NOT INFERRED
-------------------------------------------
It is tempting to detect a rename automatically: data stops, so go look for a
symbol that started trading the same week at a similar price. **Do not.** A wrong
guess splices another company's price history into a chart Ajay sizes real
positions against, and it would do so silently. Every entry here is hand-checked
against both providers and carries the evidence. A missing entry costs one stale
name that the staleness monitor will flag; a wrong entry costs a fabricated
chart. Those are not symmetric.

Nothing in Minervini covers this. It is data plumbing.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("sepa.symbols")

# ---------------------------------------------------------------------------
# Ticker renames
# ---------------------------------------------------------------------------
# {OLD: (NEW, first_session_under_the_new_symbol, evidence)}
#
# `effective` is the first session that PRINTS under the new symbol, so the old
# series is kept strictly before it. Verified 2026-08-16 by fetching both symbols
# from Massive and checking the boundary bars are consecutive sessions with a
# continuous price.
RENAMES: dict[str, tuple[str, str, str]] = {
    "SATS": ("ECHO", "2026-06-24",
             "EchoStar Corp. SATS last bar 2026-06-23 close 103.915; ECHO first "
             "bar 2026-06-24 open 101.16. Consecutive sessions, -2.6% overnight, "
             "no split."),
    "SQ": ("XYZ", "2025-01-21",
           "Block, Inc. SQ last bar 2025-01-17 close 86.96; XYZ first bar "
           "2025-01-21 open 88.06 (2025-01-20 was MLK Day). Consecutive "
           "sessions, no split."),
    "DOOO": ("DOO", "2025-12-08",
             "BRP Inc. DOOO last bar 2025-12-05 close 76.66; DOO first bar "
             "2025-12-08 open 81.67. Consecutive sessions (Fri->Mon), +6.5% "
             "overnight, no split. Massive reference 2026-08-25: DOO active "
             "on XNAS as 'BRP Inc. Common Subordinate Voting Shares'; DOOO "
             "NOT_FOUND."),
    "IAC": ("PPLI", "2026-06-04",
            "IAC renamed to People Inc. IAC last bar 2026-06-03 close 42.24; "
            "PPLI first bar 2026-06-04 open 42.72. Consecutive sessions, "
            "+1.1% overnight, no split. Massive reference 2026-08-25: PPLI "
            "active on XNAS as 'People Incorporated Common Stock'; IAC "
            "NOT_FOUND."),
}

# Reverse index, built once. A current symbol can have more than one former name
# over a long enough history, so the value is a list, oldest first.
_FORMER: dict[str, list[str]] = {}
for _old, (_new, _eff, _why) in RENAMES.items():
    _FORMER.setdefault(_new.upper(), []).append(_old.upper())


def resolve(symbol: str) -> str:
    """The symbol that trades TODAY. ``SATS`` → ``ECHO``. PURE.

    Idempotent, and safe on a symbol that was never renamed. Chains are not
    followed on purpose: a two-step rename should be written as a direct entry so
    the evidence stays readable.
    """
    if not symbol:
        return symbol
    s = symbol.strip().upper()
    entry = RENAMES.get(s)
    return entry[0] if entry else s


def former_names(symbol: str) -> list[str]:
    """Symbols this one used to trade under, oldest first. PURE."""
    if not symbol:
        return []
    return list(_FORMER.get(symbol.strip().upper(), []))


def rename_of(symbol: str) -> Optional[dict]:
    """Rename record for an OLD symbol, or None. PURE.

    The UI reads this to say "SATS now trades as ECHO" instead of claiming the
    company was acquired.
    """
    entry = RENAMES.get((symbol or "").strip().upper())
    if not entry:
        return None
    new, eff, why = entry
    return {"from": symbol.strip().upper(), "to": new, "effective": eff,
            "evidence": why}


# ---------------------------------------------------------------------------
# Delistings — names that no longer trade ANYWHERE, under ANY spelling
# ---------------------------------------------------------------------------
# {SYMBOL: evidence}. Curated for the same reason RENAMES is: a wrong removal
# hides a live company, so every entry carries what was checked and when. A
# delisting is NOT a rename — there is no successor series to splice, so the
# symbol simply leaves the universe. If a successor is later discovered, move
# the entry to RENAMES with boundary-bar evidence.
#
# All verified 2026-08-25 against Massive: reference lookup NOT_FOUND (both
# spellings for class shares), zero daily aggs 2026-08-08..2026-08-25, and an
# active-listings name search that found no successor. Most carry the classic
# deal-close signature: price pinned at the deal level for days, then a final
# session on a multiple of average volume.
DELISTED: dict[str, str] = {
    "SMAR": "Smartsheet. Last bar 2025-01-21, pinned $56.4x for days, final "
            "session 6x volume — take-private close. Sat dead in the universe "
            "for 19 months (the SQ lesson, again).",
    "CFLT": "Confluent. Last bar 2026-03-16, pinned ~$30.7, final session "
            "~4x volume — acquisition close.",
    "CWEN-A": "Clearway Energy Class A. Last bar 2026-04-30. NOT_FOUND as "
              "CWEN-A and CWEN.A; CWEN (Class C) remains active on XNYS — "
              "the A class was retired, not renamed.",
    "MASI": "Masimo. Last bar 2026-06-09, pinned $179.9x, final session 3x "
            "volume — acquisition close.",
    "BLD": "TopBuild. Last bar 2026-06-30 after a two-day -15% slide; no "
           "successor listing found by name search.",
    "JHG": "Janus Henderson Group. Last bar 2026-06-30, pinned $51.9x, final "
           "session 3x volume — acquisition close (only ETF products carry "
           "the Janus Henderson name now).",
    "NSA": "National Storage Affiliates. Last bar 2026-07-21, final session "
           "13x volume — acquisition close.",
    "EA": "Electronic Arts. Last bar 2026-08-04, pinned $209.9x, final "
          "session 10x volume — take-private close.",
    "AVB": "AvalonBay Communities. Last bar 2026-08-14; reference NOT_FOUND, "
           "no successor by name search. No deal-close pin — likely a "
           "stock-for-stock merger; revisit if a successor surfaces.",
    "GFRR": "Never in the universe — a ghost in Massive's movers snapshot "
            "that erred the catalysts cron every 5 minutes. Reference "
            "NOT_FOUND, zero aggs, Yahoo 404s the quote.",
}


def is_delisted(symbol: str) -> bool:
    """True when the symbol is a verified dead listing. PURE.

    Checks the symbol AS GIVEN (canonicalized), not resolve()d: a renamed
    symbol (IAC) is not delisted — it trades on as PPLI.
    """
    return (symbol or "").strip().upper() in DELISTED


# ---------------------------------------------------------------------------
# Per-provider spelling
# ---------------------------------------------------------------------------
# Our canonical spelling is the S&P / Wikipedia one: a dash before the share
# class (BRK-B). Providers disagree, and the disagreement is silent — a wrong
# spelling returns "no data", which is indistinguishable from "delisted".
def for_massive(symbol: str) -> str:
    """Massive spells class shares with a DOT: ``BRK-B`` → ``BRK.B``. PURE.

    Measured 2026-08-16 — Massive returns nothing at all for the dash form:

        BRK-B → None      BRK.B → 250 bars
        BF-B  → None      BF.B  → 250 bars
        MOG-A → None      MOG.A → 250 bars
        CWEN-A→ None      CWEN.A→ 177 bars

    Without this, every class share silently falls through to yfinance, mixing
    two providers' adjustment conventions inside one scan.
    """
    return _reclass(symbol, ".")


def for_yahoo(symbol: str) -> str:
    """Yahoo spells class shares with a DASH: ``BRK.B`` → ``BRK-B``. PURE."""
    return _reclass(symbol, "-")


# A class suffix is a single letter after the separator, at the very end. Only
# that shape is rewritten, so a symbol that legitimately contains a dot or dash
# elsewhere is left alone.
def _reclass(symbol: str, sep: str) -> str:
    if not symbol:
        return symbol
    s = symbol.strip().upper()
    for other in (".", "-"):
        if other == sep:
            continue
        head, found, tail = s.rpartition(other)
        if found and head and len(tail) == 1 and tail.isalpha():
            return f"{head}{sep}{tail}"
    return s


def yf_ticker(symbol: str):
    """``yfinance.Ticker`` for the symbol that trades TODAY, spelled Yahoo's way.

    Ajay 2026-08-16, from the deploy log right after the rename fix shipped::

        ERROR HTTP Error 404: No fundamentals data found for symbol: SQ

    The price path resolves renames; thirty-odd other call sites were still
    handing Yahoo the retired ticker, so a renamed company kept its chart and
    lost its profile, fundamentals, catalysts, earnings date and analyst
    ratings. Every one of those reads as "this company has no data", which is
    the same wrong story the delisted banner was telling.

    Use this instead of ``yf.Ticker`` anywhere the symbol came from a user, a
    watchlist or a scan. ``sepa.prices`` deliberately does NOT: its splice has
    to fetch the OLD symbol on purpose.

    Index symbols (``^VIX``) and anything not in ``RENAMES`` pass through
    untouched, so this is safe to apply blanket.
    """
    import yfinance as yf
    return yf.Ticker(for_yahoo(resolve(symbol)))


__all__ = ["RENAMES", "DELISTED", "resolve", "former_names", "rename_of",
           "is_delisted", "for_massive", "for_yahoo", "yf_ticker"]
