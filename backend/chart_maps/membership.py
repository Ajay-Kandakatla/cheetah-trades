"""Chart Maps tab membership snapshot (Ajay 2026-10-12, his-call #8: "Link each
new name to the other Chart Maps tabs it's on? That needs a stored per-tab
snapshot first." → "yes").

ONE Mongo collection, `chart_maps_membership`, ONE doc per tab:
    {_id: tab, tab, symbols[], n, built_at, source_as_of, ttl_sec, ttl_name,
     params_note, limit}

WRITERS
  * `board.board()` — ONE hook after `out["tab"] = t`, which upserts only when
    the request is the DEFAULT page request (`is_default_request`): `limit ==
    LIMIT_MAX` (the page's BOARD_LIMIT), `days == BARS_DEFAULT`, `studies is
    False`, `min_room` None or `room_floor.MIN_ROOM_DEFAULT` (board.py treats
    the two identically and the page sends 5 explicitly on the room tabs), and
    every other argument at its `board()` SIGNATURE default. A warming payload
    or an empty tile list never overwrites the last real list.
    `supply_demand.session_board.board_symbols()` reaches that same default
    request for zones / deep_demand on its own cadence, so it writes too.
  * `sepa.bonde_api.bonde_board` — `record_bonde` over the placed sections.

READER
  * `attach_also_on(arrivals)` — ONE projected `find({})` (≤ 23 tiny docs),
    then per arrival the list of other tabs whose latest snapshot holds it,
    each with its own as-of and a `stale` read judged against THAT tab's own
    cache TTL constant (by name; never a new threshold — a tab with no TTL is
    `stale: None`, as-of shown, staleness not judged).

Membership means "in the served top `limit`" (80 on a page load), not the
whole tab. It snapshots nothing about users. It changes no board, no sort, no
filter, no gate and no push: every function here swallows its own errors.
"""
from __future__ import annotations

import inspect
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

log = logging.getLogger("chart_maps.membership")

COLL = "chart_maps_membership"
# `supply` is the hidden alias of `ict` on the page (`parseTab`); `growth` is
# the arrivals board itself (it links OUT, never to itself).
SKIP_TABS = ("supply",)
SELF_TAB = "growth"
# Where `board()` nests each memo tab's block — the block's own `built_at` is
# the memo's build stamp, which can be up to one TTL old when served
# (stale-while-revalidate). The snapshot's write time is NOT the data's as-of.
MEMO_BLOCK_KEY = {
    "key_levels": "key_levels_board",
    "dual_momentum": "dual_momentum_board",
    "ath": "ath_board",
    "resiliency": "resiliency_board",
    "fallen": "fallen_board",
    "drop10": "drop10_board",
}
# Memo tabs whose TTL is ONE module constant, read by name at call time.
_MEMO_TTL_MODULE = {
    "key_levels": "key_levels_tab",
    "dual_momentum": "dual_momentum_tab",
    "ath": "ath_tab",
    "resiliency": "resiliency_tab",
    "fallen": "fallen_tab",
}
BONDE_TAB = "bonde"
PROJECTION = {"_id": 1, "symbols": 1, "built_at": 1, "source_as_of": 1,
              "ttl_sec": 1, "ttl_name": 1, "limit": 1}


def _db(db=None):
    """The `chart_maps/earnings_alerts.py` pattern: `portfolio.store._get_db`."""
    if db is not None:
        return db
    try:
        from portfolio.store import _get_db
        return _get_db()
    except Exception as exc:                                   # noqa: BLE001
        log.debug("membership: no mongo: %s", exc)
        return None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _iso(v) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, str):
        s = v.strip()
        return s if s and s.lower() != "none" else None
    return None


# ---------------------------------------------------------------------------
# the writer rule
# ---------------------------------------------------------------------------
def is_default_request(**request) -> bool:
    """True iff `request` is the page's default board request.

    Defaults are read from `board.board`'s own SIGNATURE (never a typed list),
    with four named overrides. An unknown key → one warning and False (never a
    TypeError); a signature parameter missing from the request → False."""
    from chart_maps import board as B
    from supply_demand import room_floor as RF

    defaults = {name: p.default
                for name, p in inspect.signature(B.board).parameters.items()}
    for k in request:
        if k not in defaults:
            log.warning("membership: unknown board() arg %s — treating as "
                        "non-default", k)
            return False
    for k in defaults:
        if k not in request:
            return False
    for k, v in request.items():
        if k == "tab":
            continue
        if k == "limit":
            if v != B.LIMIT_MAX:
                return False
        elif k == "days":
            if v != B.BARS_DEFAULT:
                return False
        elif k == "studies":
            if v is not False:
                return False
        elif k == "min_room":
            if v is None:
                continue
            if isinstance(v, bool):
                return False
            try:
                if float(v) != float(RF.MIN_ROOM_DEFAULT):
                    return False
            except (TypeError, ValueError):
                return False
        else:
            try:
                if not (v == defaults[k]):
                    return False
            except Exception:                                  # noqa: BLE001
                return False
    return True


# ---------------------------------------------------------------------------
# as-of and staleness, by the tab's own constants
# ---------------------------------------------------------------------------
def ttl_for_tab(tab: str, out: dict) -> Tuple[Optional[int], Optional[str]]:
    """(seconds, "module.CONSTANT") for a memo tab, (None, None) otherwise.
    Never invents a number."""
    try:
        if tab in _MEMO_TTL_MODULE:
            import importlib
            mod_name = _MEMO_TTL_MODULE[tab]
            mod = importlib.import_module("chart_maps." + mod_name)
            return (int(mod.MEMO_TTL_SEC),
                    "chart_maps.%s.MEMO_TTL_SEC" % mod_name)
        if tab == "drop10":
            from chart_maps import drop10_tab as D10
            mode = ((out or {}).get(MEMO_BLOCK_KEY["drop10"]) or {}).get("mode")
            if not mode:
                return (None, None)
            name = ("LIVE_TTL_SEC" if mode == D10.MODE_LIVE else "CLOSED_TTL_SEC")
            return (int(D10.ttl_for(mode)), "chart_maps.drop10_tab.%s" % name)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("membership: ttl for %s unavailable: %s", tab, exc)
    return (None, None)


def source_as_of_for(tab: str, out: dict) -> Optional[str]:
    """The DATA's as-of: a memo tab's own block `built_at`; for every other
    tab the first present of `built_at` / `as_of` / `generated_at`."""
    out = out or {}
    if tab in MEMO_BLOCK_KEY:
        block = out.get(MEMO_BLOCK_KEY[tab]) or {}
        return _iso(block.get("built_at")) if isinstance(block, dict) else None
    for k in ("built_at", "as_of", "generated_at"):
        s = _iso(out.get(k))
        if s:
            return s
    return None


def _parse(stamp) -> Optional[datetime]:
    if not isinstance(stamp, str) or not stamp:
        return None
    try:
        dt = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def is_stale(doc: dict, now: datetime) -> Optional[bool]:
    """None when the tab has no TTL constant (as-of shown, not judged);
    otherwise older than that TTL, judged from `source_as_of` first."""
    try:
        ttl = (doc or {}).get("ttl_sec")
        if ttl is None:
            return None
        dt = _parse(doc.get("source_as_of")) or _parse(doc.get("built_at"))
        if dt is None:
            return None
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return (now - dt).total_seconds() > float(ttl)
    except Exception:                                          # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# writers
# ---------------------------------------------------------------------------
def record(tab: str, symbols: list, *, built_at: Optional[str] = None,
           source_as_of: Optional[str] = None, ttl_sec: Optional[int] = None,
           ttl_name: Optional[str] = None, params_note: str = "",
           limit: Optional[int] = None, db=None) -> bool:
    """ONE upsert for one tab. Never raises. An empty list never overwrites
    the last real one (the as-of then stays at the last non-empty build)."""
    try:
        if tab in SKIP_TABS or tab == SELF_TAB:
            return False
        seen, syms = set(), []
        for s in symbols or []:
            u = str(s or "").strip().upper()
            if u and u not in seen:
                seen.add(u)
                syms.append(u)
        if not syms:
            return False
        d = _db(db)
        if d is None:
            return False
        doc = {"_id": tab, "tab": tab, "symbols": syms, "n": len(syms),
               "built_at": built_at or _utc_now_iso(),
               "source_as_of": source_as_of, "ttl_sec": ttl_sec,
               "ttl_name": ttl_name, "params_note": params_note,
               "limit": limit}
        t0 = time.perf_counter()
        d[COLL].replace_one({"_id": tab}, doc, upsert=True)
        log.debug("membership: wrote %s n=%d in %.1f ms", tab, len(syms),
                  (time.perf_counter() - t0) * 1000.0)
        return True
    except Exception as exc:                                   # noqa: BLE001
        log.warning("membership: write for %s failed: %s", tab, exc)
        return False


def record_board(tab: str, out: dict, *, request: dict, db=None) -> bool:
    """The `board()` hook: the default page request only, never warming."""
    try:
        if not isinstance(out, dict) or out.get("warming"):
            return False
        if not is_default_request(**request):
            return False
        syms = [t["symbol"] for t in (out.get("tiles") or [])
                if isinstance(t, dict) and t.get("symbol")]
        ttl_sec, ttl_name = ttl_for_tab(tab, out)
        note = ("default page request: limit=%s days=%s min_tier=%s sort=%s "
                "universe=%s min_room=%s" % (
                    request.get("limit"), request.get("days"),
                    request.get("min_tier"), request.get("sort"),
                    request.get("universe"), request.get("min_room")))
        return record(tab, syms, source_as_of=source_as_of_for(tab, out),
                      ttl_sec=ttl_sec, ttl_name=ttl_name, params_note=note,
                      limit=request.get("limit"), db=db)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("membership: board hook for %s failed: %s", tab, exc)
        return False


def _bonde_as_of(payload: dict) -> Optional[str]:
    """The Bonde board carries the scan stamp as `scan_ts` (epoch seconds from
    the scan file, or an ISO string)."""
    v = (payload or {}).get("scan_ts")
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        try:
            return datetime.fromtimestamp(float(v), tz=timezone.utc).isoformat(
                timespec="seconds")
        except (OverflowError, OSError, ValueError):
            return None
    return _iso(v)


def record_bonde(payload: dict, *, db=None) -> bool:
    """The placed sections in `bonde.SECTIONS` order, first placement wins,
    `rejected` never walked (the `board_arrival.bonde_rows` walk without its
    is_new cut). No TTL: the scan cadence has no cache constant here."""
    try:
        from sepa import bonde as BD
        sections = (payload or {}).get("sections") or {}
        syms = []
        for k in BD.SECTIONS:
            if k == BD.SECTION_REJECTED:
                continue
            for r in sections.get(k) or []:
                if isinstance(r, dict) and r.get("symbol"):
                    syms.append(r["symbol"])
        return record(BONDE_TAB, syms, source_as_of=_bonde_as_of(payload),
                      params_note="placed sections (rejected never walked)",
                      db=db)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("membership: bonde hook failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# reader
# ---------------------------------------------------------------------------
def attach_also_on(arrivals: list, *, now: Optional[datetime] = None,
                   db=None) -> None:
    """ONE projected find; sets `a["also_on"]` on each arrival in place.
    Never raises; on any failure the arrivals are left untouched."""
    try:
        t0 = time.perf_counter()
        if not arrivals:
            return
        d = _db(db)
        docs = {}
        if d is not None:
            for doc in d[COLL].find({}, PROJECTION) or []:
                tab = doc.get("_id")
                if not tab or tab == SELF_TAB or tab in SKIP_TABS:
                    continue
                docs[str(tab)] = doc
        now = now or datetime.now(timezone.utc)
        sets = {tab: {str(s).upper() for s in (doc.get("symbols") or [])}
                for tab, doc in docs.items()}
        order = sorted(docs)
        per_tab = {tab: {"tab": tab, "built_at": docs[tab].get("built_at"),
                         "source_as_of": docs[tab].get("source_as_of"),
                         "ttl_name": docs[tab].get("ttl_name"),
                         "limit": docs[tab].get("limit"),
                         "stale": is_stale(docs[tab], now)}
                   for tab in order}
        # Computed for every arrival FIRST, assigned after: a failure part-way
        # leaves the arrivals exactly as they came in.
        planned = []
        for a in arrivals:
            if not isinstance(a, dict):
                continue
            sym = str(a.get("symbol") or "").upper()
            planned.append((a, [dict(per_tab[tab]) for tab in order
                                if sym and sym in sets[tab]]))
        for a, also in planned:
            a["also_on"] = also
        log.debug("membership: attach over %d tabs in %.1f ms", len(docs),
                  (time.perf_counter() - t0) * 1000.0)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("membership: attach failed: %s", exc)
