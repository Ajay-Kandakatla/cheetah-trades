"""👀 Gajjala's Watch — the owner's ticker list (spec §3.3, WP-A, 2026-11-15).

Ajay 2026-11-15, verbatim: "I need dashboard to add tickers to Gajjalas watch dashboard. I wanna be able to remove and
add remove tickers from the dashboard."

The list is ONE doc `{_id: "owner", symbols: [...], updated_at, by}` in `gajjala_watch_list`; the routes gate every
write to the primary owner (api.py). `colls.owner_symbols` stays the ONE reader for everyone else — add / remove read
the doc themselves so a failed read is an `error`, never an empty list written back over his names.

  * `normalize(raw)` — `strip().upper()` then `accumulation_changes._TICKER_SHAPE` (imported, never retyped), then
    the house spelling `colls.house`.
  * `add` → `added` (appended at the END, his order) | `already` | `full` (REFUSED at C.MAX_SYMBOLS — Signal Lab's
    silent drop of the oldest is NOT copied) | `bad_symbol` | `error`.
    🔁 SUPERSEDED 2026-11-18 (below): at the cap an add now REPLACES — `full` is the all-🎯 A+ refusal only.
  * `remove` → `removed` | `absent` (also a string that is not a ticker — it cannot be on the list) | `error`.

Never raises. A removed name's tile doc and claims stay (audit); the payload shows listed names only. Every served
word is a constant in payload.py.

Fixes 2026-11-15:
  * ONE spelling per stock — `normalize` returns `colls.house` (BRK-B → BRK.B) and every compare is on `colls.fold`
    (the house `broker_fold`), so BRK-B and BRK.B are one name: stored once, rung once; a remove drops either spelling.
  * No lost write — the write is a compare-and-set: it lands ONLY IF the stored `symbols` are still exactly what was
    read (a missing doc: only if it is still missing). Another add / remove in between → re-read and decide again
    (up to `_CAS_TRIES` reads), so two adds at once keep both names; the cap refusal and the append-at-the-end order
    are decided on the fresh read.

🔁 Replace the oldest at the cap (2026-11-18 — Ajay, verbatim: "For watch list when I add new ones remove the ones that are
not active in the watch list"; asked what "not active" means he picked "Oldest added" — "Remove the one you added longest
ago, whatever it is doing."; told "A+ names are never removed, and you'll see a line saying which one went."):
  * at C.MAX_SYMBOLS `add` drops the OLDEST name on his list (list order = add order; `add` appends at the END) that is
    NOT 🎯 A+ this session, appends the new one, and answers `replaced` with `replaced: <SYM>` (one compare-and-set —
    the drop and the append land together or not at all; a racing write → re-read and decide again).
  * 🎯 A+ = THE Watch tag's own read (`payload.aplus_blocks` over his names, the session `payload.session_iso`) — an A+
    name (A+, A+ triggered, A+ then stopped) never makes room. Every name A+ → `full` (FULL_TEXT, list unchanged).
    The A+ read faults → `full` too (unknown is never "not A+"; nothing is removed on a guess).
  * the replaced name is NOT blocked: he can ➕ it back at once (`add` keeps no block list). Nothing is written to the 🤖
    auto doc — only his × (api DELETE → auto.dismiss) blocks an auto re-add today, so the 🤖 engine may seat a replaced
    name by its own rules. The served `replaced` sentence names it; the "🤖 removed today" strip lists auto removals only.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from . import colls as CO
from . import constants as C

log = logging.getLogger("chart_maps.gajjala_watch.store")

STATES_ADD = ("added", "already", "full", "bad_symbol", "error",
              "replaced")                                       # 🔁 2026-11-18 — appended LAST
STATES_REMOVE = ("removed", "absent", "error")

_CAS_TRIES = 3          # reads per add / remove when another write lands between the read and the compare-and-set


def normalize(raw) -> Optional[str]:
    """A listed US ticker in the house spelling (`_TICKER_SHAPE`, upper case, class separator a dot), else None.
    Never raises."""
    if not isinstance(raw, str):
        return None
    from supply_demand.accumulation_changes import _TICKER_SHAPE
    s = raw.strip().upper()
    return CO.house(s) if _TICKER_SHAPE.match(s) else None


def _symbols_of(doc) -> list:
    """The `symbols` of a list doc — the `colls.symbols_of` rule (house spelling, de-duplicated by fold)."""
    return CO.symbols_of(doc)


def _answer(state: str, symbols: list, symbol: Optional[str], *, replaced: Optional[str] = None,
            past_aplus: bool = False) -> dict:
    from . import payload as PL
    out = {"state": state, "symbols": list(symbols), "symbol": symbol,
           "text": PL.store_text(state, symbol, old=replaced, past_aplus=past_aplus)}
    if state == "replaced":
        out["replaced"] = replaced
    return out


def aplus_names(names: list) -> set:
    """🔁 The names of `names` that carry the Watch's 🎯 A+ tag this session — THE tag's read (`payload.aplus_blocks`).
    RAISES on a fault (the caller refuses; unknown is never "not A+"). Tests replace this function."""
    from . import payload as PL
    return set(PL.aplus_blocks(list(names), PL.session_iso()))


def _oldest_not_aplus(cur: list) -> tuple:
    """(the oldest name of `cur` that is not 🎯 A+ | None, an older A+ name was passed over). RAISES on an A+ fault."""
    aps = aplus_names(cur)
    for i, s in enumerate(cur):
        if s not in aps:
            return s, i > 0
    return None, False


def _read_doc(coll):
    """The stored list doc — RAISES on a read failure (the caller answers `error`, never writes over his names)."""
    return coll.find_one({"_id": C.LIST_DOC_ID})


def _cas(coll, doc, symbols: list, by) -> bool:
    """Write `symbols` ONLY IF the stored list is still `doc`'s (compare-and-set, one atomic update). False = another
    write landed in between (the caller re-reads). A failing write RAISES."""
    fields = {"symbols": list(symbols), "updated_at": datetime.now(timezone.utc),
              "by": by if isinstance(by, str) else None}
    if isinstance(doc, dict):
        flt = {"_id": C.LIST_DOC_ID, "symbols": doc["symbols"]} if "symbols" in doc else \
              {"_id": C.LIST_DOC_ID, "symbols": {"$exists": False}}
        res = coll.update_one(flt, {"$set": fields}, upsert=False)
        return bool(getattr(res, "matched_count", 0))
    from pymongo.errors import DuplicateKeyError
    try:                                                       # no doc read → create it, unless one appeared meanwhile
        res = coll.update_one({"_id": C.LIST_DOC_ID, "symbols": {"$exists": False}}, {"$set": fields}, upsert=True)
    except DuplicateKeyError:
        return False
    return bool(getattr(res, "matched_count", 0)) or getattr(res, "upserted_id", None) is not None


def _has(cur: list, sym: str) -> bool:
    k = CO.fold(sym)
    return any(CO.fold(s) == k for s in cur)


def add(symbol, *, by, db=None) -> dict:
    """Append `symbol` at the END of the list. -> {state, symbols, symbol, text}. Never raises."""
    sym = normalize(symbol)
    if sym is None:
        return _answer("bad_symbol", CO.owner_symbols(db), None)
    try:
        cs = CO.colls(db)
        if cs is None:
            return _answer("error", [], sym)
        for _ in range(_CAS_TRIES):
            doc = _read_doc(cs["list"])
            cur = _symbols_of(doc)
            if _has(cur, sym):
                return _answer("already", cur, sym)
            if len(cur) >= C.MAX_SYMBOLS:
                try:
                    old, past = _oldest_not_aplus(cur)
                except Exception as exc:                       # noqa: BLE001 — unknown A+ → remove nothing
                    log.warning("gajjala_watch: add %s at the cap — A+ read failed: %s", sym, type(exc).__name__)
                    return _answer("full", cur, sym)
                if old is None:                                # every name is 🎯 A+ → nothing makes room
                    return _answer("full", cur, sym)
                new = [s for s in cur if s != old] + [sym]
                if _cas(cs["list"], doc, new, by):
                    return _answer("replaced", new, sym, replaced=old, past_aplus=past)
                continue
            new = cur + [sym]
            if _cas(cs["list"], doc, new, by):
                return _answer("added", new, sym)
        log.warning("gajjala_watch: add %s lost the compare-and-set %d times", sym, _CAS_TRIES)
        return _answer("error", [], sym)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("gajjala_watch: add %s failed: %s", sym, exc)
        return _answer("error", [], sym)


def remove(symbol, *, by, db=None) -> dict:
    """Drop `symbol` (either spelling) from the list (its tile doc and claims stay). -> {state, symbols, symbol, text}.
    Never raises."""
    sym = normalize(symbol)
    if sym is None:
        return _answer("absent", CO.owner_symbols(db), None)
    try:
        cs = CO.colls(db)
        if cs is None:
            return _answer("error", [], sym)
        for _ in range(_CAS_TRIES):
            doc = _read_doc(cs["list"])
            cur = _symbols_of(doc)
            if not _has(cur, sym):
                return _answer("absent", cur, sym)
            k = CO.fold(sym)
            new = [s for s in cur if CO.fold(s) != k]
            if _cas(cs["list"], doc, new, by):
                return _answer("removed", new, sym)
        log.warning("gajjala_watch: remove %s lost the compare-and-set %d times", sym, _CAS_TRIES)
        return _answer("error", [], sym)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("gajjala_watch: remove %s failed: %s", sym, exc)
        return _answer("error", [], sym)
