"""👀 Gajjala's Watch — the four Mongo collections, the owner list reader and the on/off switch (spec §3.2, step 0).

  * `gajjala_watch_list`   — ONE doc `{_id: "owner", symbols: [...], added: {FOLD: UTC}, updated_at, by}`; `owner_doc`
    is the one read (`owner_symbols` = its `symbols`). `added` (2026-11-19) = when he last ➕'d each name, keyed by
    `fold` ONLY (no dot in a key — BRK.B would nest); written by store.add / store.remove only.
  * `gajjala_watch_tiles`  — one tile doc per name (written by the minute loop / the build child).
  * `gajjala_watch_alerts` — the `GGW:` cross-push claims (never `GG:` — the 🏁 reads those).
  * `gajjala_watch_state`  — the loop state docs and the lease doc.

Every call is fenced: Mongo down → None / [] plus a log line, never a raise into the caller (the `long_term_list.store`
pattern) — EXCEPT `owner_doc` / `owner_symbols(db, strict=True)`, the board's reader: an unreadable list raises so the GET serves
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
from datetime import datetime, timezone
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


def owner_doc(db=None, strict: bool = False):
    """The owner list doc as stored (None when missing). No database / a failing read → None + the 'gajjala_watch: owner
    list unreadable' line — unless `strict`: then it RAISES (the board's GET answers `error`, never an empty watch).
    ONE find_one({"_id": C.LIST_DOC_ID}) (2026-11-19: the board reads `symbols` AND `added` from this one read)."""
    try:
        c = colls(db)
        if c is None:
            raise RuntimeError("no database")
        return c["list"].find_one({"_id": C.LIST_DOC_ID})
    except Exception as exc:                                   # noqa: BLE001
        log.warning("gajjala_watch: owner list unreadable: %s", exc)
        if strict:
            raise
        return None


def owner_symbols(db=None, strict: bool = False) -> list:
    """The owner's watch list in his order: the `symbols` of the list doc, strings only, in the house spelling,
    de-duplicated by `fold` (first wins). A missing / malformed doc → []. Any failure → [] (never raises) — unless
    `strict`: then no database or a failing read RAISES (the board's GET answers `error`, never an empty watch)."""
    return symbols_of(owner_doc(db, strict))


def stamp_utc(v) -> Optional[datetime]:
    """A stored stamp as an aware UTC datetime (Mongo hands back naive UTC) — the `auto._utc` rule (a test pins them
    equal); anything that is not a datetime → None. Never raises."""
    if not isinstance(v, datetime):
        return None
    return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)


def added_of(doc) -> dict:
    """⬆️ 2026-11-19 — {fold(name): aware UTC} from the list doc's `added` map. A non-dict doc / map, a non-str or blank
    key, a value that is not a datetime → left out (that name is undated). Never raises."""
    raw = doc.get("added") if isinstance(doc, dict) else None
    out: dict = {}
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        if not isinstance(k, str) or not k.strip():
            continue
        t = stamp_utc(v)
        f = fold(k)
        if t is not None and f:
            out[f] = t
    return out


def newest_first(symbols: list, added: dict) -> list:
    """⬆️ 2026-11-19 — his names NEWEST ADDED FIRST: the dated names by their `added` time, newest first (a tie → the
    later list position first), then the undated names in his list order. `added` = `added_of(doc)`."""
    added = added if isinstance(added, dict) else {}
    dated, undated = [], []
    for i, s in enumerate(symbols):
        t = added.get(fold(s))
        (dated if t is not None else undated).append((t, i, s))
    dated.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [s for _t, _i, s in dated] + [s for _t, _i, s in undated]


def added_iso(v) -> Optional[str]:
    """A stored stamp as ISO UTC with milliseconds ("…+00:00"); anything that is not a datetime → None."""
    t = stamp_utc(v)
    return t.isoformat(timespec="milliseconds") if t is not None else None


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
