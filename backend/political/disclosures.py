"""The curated political-disclosure list — load, validate, look up.

The rows live in ``disclosures.json`` beside this file. That file is the ONE
source: ``backend/scripts/gen_political_ts.py`` regenerates
``frontend/src/lib/politicalDisclosures.ts`` from it, so a row added here shows
up on every surface without a second edit.

INFORMATIONAL, never a buy or sell signal — the header of the generated TS says
the same thing and says why.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger("political.disclosures")

JSON_PATH = Path(__file__).with_name("disclosures.json")

#: The only categories a row may carry. Mirrors ``DisclosureCategory`` in the
#: generated TypeScript — the generator writes that union from this tuple.
CATEGORIES: tuple[str, ...] = ("potus_family", "govt_investment",
                               "govt_contractor", "inferred")

#: How long a row keeps its 🆕 highlight after ``addedOn``. Same constant the
#: frontend uses (the generator writes it into the TS from here).
NEW_DISCLOSURE_DAYS = 14

#: Every key a row carries, in the order the generator writes them.
ROW_KEYS: tuple[str, ...] = ("ticker", "company", "sector", "categories",
                             "disclosureBand", "govtStake", "notes",
                             "asOf", "addedOn")

#: Tokens that count as a NAMED agency inside ``govtStake``. The 2026-09-19
#: rule (commit 585be0c, written into the TS doc-comment): "A row without a
#: NAMED agency and a STATED percentage leaves this null and does not get to
#: imply one. 'The administration is weighing a stake' is not a stake."
AGENCY_TOKENS: tuple[str, ...] = ("DoD", "DOD", "Commerce", "DOE", "Energy",
                                  "Treasury", "Federal", "Pentagon", "Army",
                                  "Navy", "Air Force")

_cache: Optional[list[dict]] = None


def _load_raw() -> list[dict]:
    with JSON_PATH.open(encoding="utf-8") as fh:
        rows = json.load(fh)
    if not isinstance(rows, list):
        raise ValueError("disclosures.json must hold a list of rows")
    return rows


def _iso_ok(value) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def validate(rows) -> list[str]:
    """Every problem with ``rows``, as readable sentences. Empty list = clean.

    PURE — takes the rows, returns errors, touches no file. The callers are
    ``entries()`` (which logs) and the test suite (which asserts)."""
    errors: list[str] = []
    seen: set[str] = set()
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"row {i}: not an object")
            continue
        ticker = row.get("ticker")
        where = ticker or f"row {i}"
        if not ticker or not isinstance(ticker, str):
            errors.append(f"row {i}: missing ticker")
        else:
            up = ticker.upper()
            if up in seen:
                errors.append(f"{up}: duplicate ticker")
            seen.add(up)
        cats = row.get("categories")
        if not isinstance(cats, list) or not cats:
            errors.append(f"{where}: categories must be a non-empty list")
            cats = []
        for c in cats:
            if c not in CATEGORIES:
                errors.append(f"{where}: unknown category {c!r}")
        stake = row.get("govtStake")
        if stake is not None:
            if "govt_investment" not in cats:
                errors.append(
                    f"{where}: govtStake on a row that is not govt_investment "
                    f"— a contract or a headline is not an equity stake")
            if not isinstance(stake, str):
                errors.append(f"{where}: govtStake must be a string")
            else:
                if not any(tok in stake for tok in AGENCY_TOKENS):
                    errors.append(
                        f"{where}: govtStake {stake!r} names no agency — "
                        f"a stake with no holder does not get to imply one")
                if "%" not in stake:
                    errors.append(
                        f"{where}: govtStake {stake!r} states no percentage — "
                        f"'weighing a stake' is not a stake")
        for key in ("asOf", "addedOn"):
            if not _iso_ok(row.get(key)):
                errors.append(f"{where}: {key}={row.get(key)!r} is not YYYY-MM-DD")
        for key in ("company", "sector"):
            if not row.get(key) or not isinstance(row.get(key), str):
                errors.append(f"{where}: missing {key}")
    return errors


def entries() -> list[dict]:
    """The list, loaded once and validated. Rows are copies — a caller that
    mutates one does not corrupt the next reader."""
    global _cache
    if _cache is None:
        rows = _load_raw()
        errs = validate(rows)
        if errs:
            # Loud, but never fatal: the board is informational and a bad row
            # must not take the API down. The test suite holds the real gate.
            log.error("political.disclosures: %d validation error(s): %s",
                      len(errs), "; ".join(errs[:5]))
        _cache = [{k: row.get(k) for k in ROW_KEYS} for row in rows]
    return [dict(r) for r in _cache]


def by_ticker() -> dict[str, dict]:
    """{TICKER: row} — uppercase keys, the shape the watch drops against."""
    return {(r["ticker"] or "").upper(): r for r in entries()}


def is_new(row: dict, today: Optional[date] = None) -> bool:
    """True when ``addedOn`` is within NEW_DISCLOSURE_DAYS of ``today``.

    The same rule as ``isNewDisclosure`` in the generated TS: no date → never
    new; an unparseable date → never new; a FUTURE date → never new (a typo
    must not mint a highlight)."""
    added = (row or {}).get("addedOn")
    if not added:
        return False
    try:
        d = datetime.strptime(added, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return False
    t = today or date.today()
    age = (t - d).days
    if age < 0:
        return False
    return age <= NEW_DISCLOSURE_DAYS
