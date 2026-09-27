"""Which names Chart Maps served — the 17:50 ET GEX sweep's coverage list.

Ajay 2026-09-27: "Only Chart Maps names nightly". Every `board()` call records
the symbols it served into Mongo `chart_maps_seen`, one doc per (ET date, tab):
`_id="2026-09-28:zones"`, `{date_et, tab, symbols: [...], updated_at}`.
The five chart-card tabs that board() does not serve (CARD_TABS: holdings,
POTUS, Signals, Session, 9 EMA W/M) are recorded by POST /chart-maps/gex-live
instead, under the same key shape. `symbols` is ordered by LAST SEEN, oldest first: each record moves the names it
served to the end (one atomic pipeline update, no duplicates), so the per-tab
cap in `recent_symbols` keeps the names on screen latest — the ones showing at
the close — not the day's first 80 (critic 2026-09-27). The
nightly sweep (`options.gex_history.run`) unions `recent_symbols()` into its
universe so every Chart Maps tile has a post-close dealer-gamma row.

Display coverage only: nothing here gates, sizes, alerts or orders anything.
Never raises — a failed record means some names miss tonight's sweep; the
board itself is unaffected. No pruning (at most one doc per tab per day).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("chart_maps.gex_seen")

COLL = "chart_maps_seen"
ET = ZoneInfo("America/New_York")

# The five Chart Maps tabs that draw the same chart card but are NOT served by
# board.board() (Ajay 2026-09-27: "Got on add it to all tabs now please" /
# "In chartmaps"). board() records its own tabs; these are recorded by
# POST /chart-maps/gex-live when the tab asks for its live read, under the same
# per-tab cap and the same last-seen order. Keys = the frontend CM_TABS keys.
CARD_TABS = ("holdings", "potus", "signals", "session", "ema_frames")


def seen_tabs() -> tuple:
    """Every tab whose served names the nightly sweep covers: board.TABS
    first (their order unchanged), then CARD_TABS."""
    from chart_maps import board as B
    return tuple(B.TABS) + tuple(t for t in CARD_TABS if t not in B.TABS)


def _coll(coll=None):
    if coll is not None:
        return coll
    try:
        from portfolio.store import _get_db
        db = _get_db()
        return db[COLL] if db is not None else None
    except Exception as exc:                                    # noqa: BLE001
        log.debug("gex_seen: no mongo: %s", exc)
        return None


def _et_today(now: Optional[datetime] = None):
    n = now if now is not None else datetime.now(ET)
    if n.tzinfo is not None:
        n = n.astimezone(ET)
    return n.date()


def _syms(symbols) -> list:
    out = []
    for s in symbols or []:
        t = str(s or "").strip().upper()
        if t and t not in out:
            out.append(t)
    return out


def _move_to_end(syms: list, day: str, tab: str) -> list:
    """The update pipeline: symbols = (stored minus syms) + syms."""
    lit = {"$literal": list(syms)}
    kept = {"$filter": {"input": {"$ifNull": ["$symbols", []]}, "as": "s",
                        "cond": {"$not": [{"$in": ["$$s", lit]}]}}}
    return [{"$set": {"symbols": {"$concatArrays": [kept, lit]},
                      "date_et": {"$literal": day}, "tab": {"$literal": tab},
                      "updated_at": {"$literal": int(time.time())}}}]


def record(tab: str, symbols, now: Optional[datetime] = None, coll=None) -> int:
    """Move the served symbols to the END of today's (date, tab) doc's
    `symbols` (drop them where they were, append them in served order) — one
    aggregation-pipeline update, atomic per doc, upserting. Returns how many
    symbols were offered; 0 on empty input or any failure."""
    try:
        syms = _syms(symbols)
        if not syms or not tab:
            return 0
        c = _coll(coll)
        if c is None:
            return 0
        day = _et_today(now).isoformat()
        c.update_one({"_id": f"{day}:{tab}"}, _move_to_end(syms, day, tab),
                     upsert=True)
        return len(syms)
    except Exception as exc:                                    # noqa: BLE001
        log.debug("gex_seen: record %s failed: %s", tab, exc)
        return 0


def recent_symbols(days: Optional[int] = None, per_tab: Optional[int] = None,
                   now: Optional[datetime] = None, coll=None) -> list:
    """Names served in the last `days` ET days (default
    gex_history.NIGHTLY_MAX_AGE_DAYS). PER TAB: newest date first, and inside
    a day most recently seen first (the stored list read back to front),
    deduped, at most `per_tab` (default board.LIMIT_MAX); then the
    union across tabs in seen_tabs() order (board.TABS, then CARD_TABS),
    deduped. No global cut, so no tab is ever cut for its name's place in the
    alphabet. A doc under any other tab key is ignored. [] on failure."""
    try:
        from options import gex_history as GH
        from chart_maps import board as B
        d = GH.NIGHTLY_MAX_AGE_DAYS if days is None else int(days)
        cap = B.LIMIT_MAX if per_tab is None else int(per_tab)
        c = _coll(coll)
        if c is None:
            return []
        floor = (_et_today(now) - timedelta(days=d)).isoformat()
        docs = list(c.find({"date_et": {"$gte": floor}}))
        by_tab: dict = {}
        for doc in docs:
            tab = doc.get("tab")
            if tab:
                by_tab.setdefault(tab, []).append(doc)
        out, seen = [], set()
        for tab in seen_tabs():
            kept = []
            for doc in sorted(by_tab.get(tab) or [],
                              key=lambda x: str(x.get("date_et") or ""),
                              reverse=True):
                stored = doc.get("symbols")
                stored = list(stored) if isinstance(stored, list) else []
                for s in _syms(reversed(stored)):
                    if len(kept) >= cap:
                        break
                    if s not in kept:
                        kept.append(s)
            for s in kept:
                if s not in seen:
                    seen.add(s)
                    out.append(s)
        return out
    except Exception as exc:                                    # noqa: BLE001
        log.debug("gex_seen: recent_symbols failed: %s", exc)
        return []
