"""👀 Gajjala's Watch — the owner's ticker list (spec §3.3, WP-A, 2026-11-15).

Ajay 2026-11-15, verbatim: "I need dashboard to add tickers to Gajjalas watch dashboard. I wanna be able to remove and
add remove tickers from the dashboard."

The list is ONE doc `{_id: "owner", symbols: [...], updated_at, by}` in `gajjala_watch_list`; the routes gate every
write to the primary owner (api.py). `colls.owner_symbols` stays the ONE reader for everyone else — add / remove read
the doc themselves so a failed read is an `error`, never an empty list written back over his names.

  * `normalize(raw)` — `strip().upper()` then `accumulation_changes._TICKER_SHAPE` (imported, never retyped).
  * `add` → `added` (appended at the END, his order) | `already` | `full` (REFUSED at C.MAX_SYMBOLS — Signal Lab's
    silent drop of the oldest is NOT copied) | `bad_symbol` | `error`.
  * `remove` → `removed` | `absent` (also a string that is not a ticker — it cannot be on the list) | `error`.

Never raises. A removed name's tile doc and claims stay (audit); the payload shows listed names only. Every served
word is a constant in payload.py.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from . import colls as CO
from . import constants as C

log = logging.getLogger("chart_maps.gajjala_watch.store")

STATES_ADD = ("added", "already", "full", "bad_symbol", "error")
STATES_REMOVE = ("removed", "absent", "error")


def normalize(raw) -> Optional[str]:
    """A listed US ticker in upper case (the house `_TICKER_SHAPE`), else None. Never raises."""
    if not isinstance(raw, str):
        return None
    from supply_demand.accumulation_changes import _TICKER_SHAPE
    s = raw.strip().upper()
    return s if _TICKER_SHAPE.match(s) else None


def _symbols_of(doc) -> list:
    """The `symbols` of a list doc — strings only, de-duplicated in order (the `colls.owner_symbols` rule)."""
    raw = doc.get("symbols") if isinstance(doc, dict) else None
    out: list = []
    for s in raw if isinstance(raw, (list, tuple)) else []:
        if isinstance(s, str) and s and s not in out:
            out.append(s)
    return out


def _answer(state: str, symbols: list, symbol: Optional[str]) -> dict:
    from . import payload as PL
    return {"state": state, "symbols": list(symbols), "symbol": symbol, "text": PL.store_text(state, symbol)}


def _read(coll) -> list:
    """The stored list — RAISES on a read failure (the caller answers `error`, never writes over his names)."""
    return _symbols_of(coll.find_one({"_id": C.LIST_DOC_ID}))


def _write(coll, symbols: list, by) -> None:
    coll.update_one({"_id": C.LIST_DOC_ID},
                    {"$set": {"symbols": list(symbols), "updated_at": datetime.now(timezone.utc),
                              "by": by if isinstance(by, str) else None}},
                    upsert=True)


def add(symbol, *, by, db=None) -> dict:
    """Append `symbol` at the END of the list. -> {state, symbols, symbol, text}. Never raises."""
    sym = normalize(symbol)
    if sym is None:
        return _answer("bad_symbol", CO.owner_symbols(db), None)
    try:
        cs = CO.colls(db)
        if cs is None:
            return _answer("error", [], sym)
        cur = _read(cs["list"])
        if sym in cur:
            return _answer("already", cur, sym)
        if len(cur) >= C.MAX_SYMBOLS:
            return _answer("full", cur, sym)
        new = cur + [sym]
        _write(cs["list"], new, by)
        return _answer("added", new, sym)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("gajjala_watch: add %s failed: %s", sym, exc)
        return _answer("error", [], sym)


def remove(symbol, *, by, db=None) -> dict:
    """Drop `symbol` from the list (its tile doc and claims stay). -> {state, symbols, symbol, text}. Never raises."""
    sym = normalize(symbol)
    if sym is None:
        return _answer("absent", CO.owner_symbols(db), None)
    try:
        cs = CO.colls(db)
        if cs is None:
            return _answer("error", [], sym)
        cur = _read(cs["list"])
        if sym not in cur:
            return _answer("absent", cur, sym)
        new = [s for s in cur if s != sym]
        _write(cs["list"], new, by)
        return _answer("removed", new, sym)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("gajjala_watch: remove %s failed: %s", sym, exc)
        return _answer("error", [], sym)
