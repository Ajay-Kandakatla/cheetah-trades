"""👀 Gajjala's Watch — the four Mongo collections, the owner list reader and the on/off switch (spec §3.2, step 0).

  * `gajjala_watch_list`   — ONE doc `{_id: "owner", symbols: [...], updated_at, by}`; `owner_symbols` is the one reader.
  * `gajjala_watch_tiles`  — one tile doc per name (written by the minute loop / the build child).
  * `gajjala_watch_alerts` — the `GGW:` cross-push claims (never `GG:` — the 🏁 reads those).
  * `gajjala_watch_state`  — the loop state docs and the lease doc.

Every call is fenced: Mongo down → None / [] plus a log line, never a raise into the caller (the `long_term_list.store`
pattern). `loop_reads_soon` is the ONE definition of "the minute loop will read a newly added name within about a
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


def owner_symbols(db=None) -> list:
    """The owner's watch list in his order: the `symbols` of the list doc, strings only, de-duplicated (first wins).
    Any failure → []; never raises."""
    try:
        c = colls(db)
        if c is None:
            return []
        doc = c["list"].find_one({"_id": C.LIST_DOC_ID})
        raw = (doc or {}).get("symbols") if isinstance(doc, dict) else None
        if not isinstance(raw, (list, tuple)):
            return []
        out: list = []
        for s in raw:
            if isinstance(s, str) and s and s not in out:
                out.append(s)
        return out
    except Exception as exc:                                   # noqa: BLE001
        log.warning("gajjala_watch: owner list unreadable: %s", exc)
        return []


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
