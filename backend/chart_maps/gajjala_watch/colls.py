"""👀 Gajjala's Watch — the four Mongo collections, the owner list reader and the on/off switch (spec §3.2, step 0).

  * `gajjala_watch_list`   — ONE doc `{_id: "owner", symbols: [...], updated_at, by}`; `owner_symbols` is the one reader.
  * `gajjala_watch_tiles`  — one tile doc per name (written by the minute loop / the build child).
  * `gajjala_watch_alerts` — the `GGW:` cross-push claims (never `GG:` — the 🏁 reads those).
  * `gajjala_watch_state`  — the loop state docs and the lease doc.

Every call is fenced: Mongo down → None / [] plus a log line, never a raise into the caller (the `long_term_list.store`
pattern) — EXCEPT `owner_symbols(db, strict=True)`, the board's reader: an unreadable list raises so the GET serves
`error` with a reason, never "Your watch is empty" over his names (fix 2026-11-15). The loop / build child keep the
fail-soft [].

ONE spelling per stock (fix 2026-11-15): `fold` = the house fold `chart_maps.gajjala.store.broker_fold` ("." and "-"
are one ticker) is the equality key; `house` = the stored / fetched spelling, the class separator as a dot (BRK.B — the
Massive minute feed's spelling; `intraday_cache` holds only dotted class shares). BRK-B and BRK.B are one name. `loop_reads_soon` is the ONE definition of "the minute loop will read a newly added name within about a
minute" — the API's build-child guard and the loop tests both use it.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from . import constants as C

log = logging.getLogger("chart_maps.gajjala_watch.colls")


def _db():
    """The app database (prices._get_mongo().database), or None when Mongo is unreachable."""
    try:
        from sepa import prices
        coll = prices._get_mongo()
        return coll.database if coll is not None else None
    except Exception as exc:                                   # noqa: BLE001
        log.warning("gajjala_watch: mongo unavailable: %s", exc)
        return None


def colls(db=None) -> Optional[dict]:
    """{"list", "tiles", "alerts", "state"} collections, or None when there is no database."""
    d = db if db is not None else _db()
    if d is None:
        return None
    try:
        return {"list": d[C.COLL_LIST], "tiles": d[C.COLL_TILES], "alerts": d[C.COLL_ALERTS],
                "state": d[C.COLL_STATE]}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("gajjala_watch: collections unavailable: %s", exc)
        return None


def fold(sym) -> str:
    """The house equality key — `chart_maps.gajjala.store.broker_fold` (imported, never retyped): BRK.B == BRK-B."""
    from chart_maps.gajjala.store import broker_fold
    return broker_fold(sym)


def house(sym) -> str:
    """The ONE stored spelling of a ticker: upper case, the class separator a dot (BRK-B → BRK.B). "" for a non-str."""
    return fold(sym).replace("-", ".")


def owner_symbols(db=None, strict: bool = False) -> list:
    """The owner's watch list in his order: the `symbols` of the list doc, strings only, in the house spelling,
    de-duplicated by `fold` (first wins). A missing / malformed doc → []. Any failure → [] (never raises) — unless
    `strict`: then no database or a failing read RAISES (the board's GET answers `error`, never an empty watch)."""
    try:
        c = colls(db)
        if c is None:
            raise RuntimeError("no database")
        doc = c["list"].find_one({"_id": C.LIST_DOC_ID})
    except Exception as exc:                                   # noqa: BLE001
        log.warning("gajjala_watch: owner list unreadable: %s", exc)
        if strict:
            raise
        return []
    return symbols_of(doc)


def symbols_of(doc) -> list:
    """The `symbols` of a list doc — strings only, house spelling, de-duplicated by `fold` in order. Never raises."""
    raw = doc.get("symbols") if isinstance(doc, dict) else None
    out: list = []
    keys: set = set()
    for s in raw if isinstance(raw, (list, tuple)) else ():
        if isinstance(s, str) and s.strip():
            k = fold(s)
            if k not in keys:
                keys.add(k)
                out.append(house(s))
    return out


def enabled() -> bool:
    """C.ENABLED and the env switch is not "0" — read at call time."""
    return bool(C.ENABLED) and os.environ.get(C.ENV_ENABLED, "1") != "0"


def loop_reads_soon(now) -> bool:
    """[C2.5] True when the minute loop will read a newly added name within about a minute: the watch is on, `now` is
    inside the 🚩 pass window on a market day, and the loop's next start is not past the extended close."""
    if not enabled():
        return False
    from chart_maps.gajjala import run as RUN
    from chart_maps.gajjala import run_1m as R1
    return bool(RUN.in_window(now)) and not R1._after_extended_close(R1.next_start(now))
