"""Chart Maps lane snapshot — the slim long candidates each generic Auto-Pilot
lane reads (spec 2026-09-27 §3.7, WP-SNAP).

Ajay 2026-09-27: "stop minerviews use all strategies from Most used from Chart
maps. All of them and journal the," — every Chart Maps tab becomes a PAPER lane.

WHAT THIS DOES. Once every 5 minutes in RTH (cron → `GET /chart-maps/lane-
snapshot?record=true`, in the api process) it calls each enabled tab's OWN
builder — the same board he opens — and stores, per strategy, the tiles/rows
that are a 🎯 READY long on that board, plus the board's OWN build stamp. The
per-minute engine tick never builds a board: it reads this doc and re-confirms
the one chosen candidate on the live print (`trading/chart_maps_lanes.py`).

WHAT THIS IS NOT. It places nothing, gates nothing on its own, and invents no
stop: a PLAN tab keeps its SERVED stop, a LIST tab's stop is the READY read's
demand band floor less `zone_edge_entry.STOP_BUFFER_PCT`, and a name with
neither is rejected. For the LIST tabs this is a READY demand reversal on a
name from the tab's list, NOT the tab's own setup. UNMEASURED forward paper
measurement — the priors on these tabs are null, inverted or unmeasured.

SOURCE TIME (critic 11). `source_as_of` is the board's own build stamp,
normalised to an epoch — never this job's write time. A board that serves no
stamp stores None, and the lane then fails closed ("build time unknown").
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, time as dtime, timezone
from typing import Callable, Iterable, Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("chart_maps.lane_snapshot")

ET = ZoneInfo("America/New_York")

# A bare-date stamp ("2026-09-25") means that session's close.
BARE_DATE_CLOSE_ET = dtime(16, 0)

# Spec §3.7: the stored `why` is at most 280 characters.
WHY_MAX_CHARS = 280

_RUN_LOCK = threading.Lock()


# ═════════════════════════════════════════════════════════════════════════════
# SHARED NAMES — imported, never retyped
# ═════════════════════════════════════════════════════════════════════════════
def _board():
    from chart_maps import board as board_mod                   # noqa: PLC0415
    return board_mod


def _max_candidates() -> int:
    """At most `board.LIMIT_MAX` per sid — the page's own BOARD_LIMIT (80)."""
    return int(_board().LIMIT_MAX)


def _ready() -> str:
    from supply_demand import enterable                         # noqa: PLC0415
    return enterable.READY


def _stop_buffer_pct() -> Optional[float]:
    """`zone_edge_entry.STOP_BUFFER_PCT` — the one band-floor stop buffer. None
    when it cannot be read: the LIST stop is then left None, never typed."""
    try:
        from trading import zone_edge_entry as ZEE              # noqa: PLC0415
        return float(ZEE.STOP_BUFFER_PCT)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("lane_snapshot: STOP_BUFFER_PCT unavailable: %s", exc)
        return None


def _lanes_consts() -> tuple:
    """(SNAPSHOT_COLL, ADAPTER_VERSION) from `trading.chart_maps_lanes`, the
    module that reads the doc. Imported lazily (it pulls the engine in)."""
    from trading import chart_maps_lanes as CML                 # noqa: PLC0415
    return CML.SNAPSHOT_COLL, CML.ADAPTER_VERSION


def _roster_entry(sid: str) -> Optional[dict]:
    try:
        from trading import strategy_tags as ST                 # noqa: PLC0415
        for r in ST.ROSTER:
            if r.get("sid") == sid:
                return r
    except Exception as exc:                                    # noqa: BLE001
        log.debug("lane_snapshot: roster unavailable: %s", exc)
    return None


def _now_et() -> datetime:
    return datetime.now(timezone.utc).astimezone(ET)


def _f(x) -> Optional[float]:
    if isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


# ═════════════════════════════════════════════════════════════════════════════
# SOURCE TIME
# ═════════════════════════════════════════════════════════════════════════════
def parse_source_as_of(v) -> Optional[float]:
    """A board's build stamp → epoch seconds, or None.

    * a number → epoch seconds (ms / µs / ns stamps are scaled down);
      0 or negative is "no stamp" (patterns.latest serves 0 before its first scan);
    * a datetime → itself (naive = UTC, the pymongo convention);
    * a bare "YYYY-MM-DD" (or a `date`) → that date at 16:00 ET, the close;
    * an ISO string → parsed; "Z" accepted; naive = UTC (Mongo `built_at`
      stamps come back naive UTC — the amd/keltner 21:20 build is 17:20 ET).
    Anything else — None, "", junk — is None. Never the write time."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        x = _f(v)
        if x is None or x <= 0:
            return None
        for scale in (1e18, 1e15, 1e12):       # ns, µs, ms → s
            if x >= scale:
                return x / (scale / 1e9)
        return x
    if isinstance(v, datetime):
        dt = v if v.tzinfo is not None else v.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    if isinstance(v, date):
        return datetime.combine(v, BARE_DATE_CLOSE_ET, tzinfo=ET).timestamp()
    if not isinstance(v, str):
        return None
    s = v.strip()
    if not s:
        return None
    if len(s) == 10:
        try:
            d = date.fromisoformat(s)
        except ValueError:
            return None
        return datetime.combine(d, BARE_DATE_CLOSE_ET, tzinfo=ET).timestamp()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parse_source_as_of(dt)


def _stamp(payload, *keys) -> tuple:
    """(epoch, key) — the first of `keys` in `payload` that parses."""
    if not isinstance(payload, dict):
        return None, None
    for k in keys:
        ts = parse_source_as_of(payload.get(k))
        if ts is not None:
            return ts, k
    return None, None


# ═════════════════════════════════════════════════════════════════════════════
# THE SLIM CANDIDATE
# ═════════════════════════════════════════════════════════════════════════════
def _slim_enterable(e: Optional[dict]) -> Optional[dict]:
    if not isinstance(e, dict):
        return None
    room = e.get("room") if isinstance(e.get("room"), dict) else None
    return {"verdict": e.get("verdict"),
            "reasons": list(e.get("reasons") or []),
            "reason_short": list(e.get("reason_short") or []),
            "gates": dict(e.get("gates") or {}),
            "band": dict(e["band"]) if isinstance(e.get("band"), dict) else None,
            "room": ({"state": room.get("state"), "room_pct": _f(room.get("room_pct")),
                      "target": _f(room.get("target"))} if room else None)}


def _slim_bs(bs: Optional[dict]) -> dict:
    bs = bs if isinstance(bs, dict) else {}
    return {"ceiling_pct": _f((bs.get("ceiling") or {}).get("distance_pct")),
            "floor_pct": _f((bs.get("floor") or {}).get("distance_pct"))}


def _band_floor_stop(e: Optional[dict]) -> Optional[float]:
    lo = _f(((e or {}).get("band") or {}).get("lo"))
    buf = _stop_buffer_pct()
    if lo is None or lo <= 0 or buf is None:
        return None
    return round(lo * (1.0 - buf / 100.0), 4)


def _candidate(sym: str, rank: int, *, enterable: Optional[dict], px, px_source,
               plan: dict, band_structure=None, badges=None, stats=None, why=None,
               served: Optional[dict] = None) -> dict:
    """The stored tile snapshot. A whitelist: bars, curves, markers and the
    rest of the tile never ride along."""
    return {
        "symbol": str(sym).upper(),
        "board_rank": int(rank),
        "plan": {"buy": _f(plan.get("buy")), "stop": _f(plan.get("stop")),
                 "target": _f(plan.get("target")), "source": plan.get("source")},
        "enterable": _slim_enterable(enterable),
        "band_structure": _slim_bs(band_structure),
        "badges": [str(b.get("text")) for b in (badges or [])
                   if isinstance(b, dict) and b.get("text")],
        "stats": [[s.get("k"), s.get("v")] for s in (stats or []) if isinstance(s, dict)],
        "why": str(why or "")[:WHY_MAX_CHARS],
        "print": {"px": _f(px), "source": px_source},
        "served": {k: v for k, v in (served or {}).items()
                   if v is None or isinstance(v, (str, int, float, bool))},
    }


def _read_reason(e: Optional[dict]) -> Optional[str]:
    """None when the read is READY, else the rejection key: the verdict plus
    its first reason code ("blocked: floor_swept", "watch: reclaim")."""
    if not isinstance(e, dict) or not e.get("verdict"):
        return "no_read"
    if e.get("verdict") == _ready():
        return None
    codes = list(e.get("reasons") or [])
    return f"{str(e.get('verdict')).lower()}: {codes[0] if codes else '?'}"


class _Out:
    """Accumulates one sid's result."""

    def __init__(self):
        self.candidates: list = []
        self.rejected: dict = {}
        self.rejected_syms: dict = {}
        self.universe_n = 0

    def reject(self, reason: str, sym=None):
        self.rejected[reason] = self.rejected.get(reason, 0) + 1
        if sym:
            lst = self.rejected_syms.setdefault(reason, [])
            if len(lst) < 10:
                lst.append(str(sym).upper())

    def keep(self, cand: dict):
        if len(self.candidates) < _max_candidates():
            self.candidates.append(cand)
        else:
            self.reject("over_limit", cand.get("symbol"))

    def result(self, source_as_of, source_key) -> dict:
        return {"candidates": self.candidates, "universe_n": self.universe_n,
                "rejected": self.rejected, "rejected_syms": self.rejected_syms,
                "source_as_of": source_as_of, "source_key": source_key}


# ═════════════════════════════════════════════════════════════════════════════
# THE READ FOR SYMBOL LISTS (row boards and the n/a tile tabs)
# ═════════════════════════════════════════════════════════════════════════════
def _bounce_rows(symbols: list) -> dict:
    from supply_demand import bounce_room                       # noqa: PLC0415
    if not symbols:
        return {}
    return (bounce_room.api_payload(symbols) or {}).get("rows") or {}


def _keep_ready_rows(out: _Out, items: list) -> None:
    """`items` = [(board_rank, sym, served_scalars, badges, stats, why)] in
    board order, already past the tab's own filter. One bounce-room read for
    all of them; READY rows become band-floor candidates."""
    syms = []
    for it in items:
        s = str(it[1] or "").upper()
        if s and s not in syms:
            syms.append(s)
    syms = syms[:_max_candidates()]
    rows = _bounce_rows(syms)
    seen = set()
    for it in items:
        rank = it[0]
        sym = str(it[1] or "").upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        if sym not in syms:
            out.reject("over_limit", sym)
            continue
        row = rows.get(sym) or {}
        cov = row.get("coverage")
        if cov not in ("store", "ondemand"):
            out.reject(str(cov or "pending"), sym)
            continue
        e = row.get("enterable")
        why_not = _read_reason(e)
        if why_not:
            out.reject(why_not, sym)
            continue
        stop = _band_floor_stop(e)
        if stop is None:
            out.reject("no_stop", sym)
            continue
        px = _f(row.get("print")) or _f(((e or {}).get("print") or {}).get("px"))
        if px is None or stop >= px:
            out.reject("stop_not_below_print", sym)
            continue
        out.keep(_candidate(sym, rank, enterable=e, px=px,
                            px_source=((e or {}).get("print") or {}).get("source"),
                            plan={"buy": None, "stop": stop, "target": None,
                                  "source": "band_floor"},
                            band_structure=row.get("band_structure"),
                            badges=it[3], stats=it[4], why=it[5], served=it[2]))


# ═════════════════════════════════════════════════════════════════════════════
# TILE ADAPTERS — board_mod.board(tab, limit=LIMIT_MAX, universe="full")
# ═════════════════════════════════════════════════════════════════════════════
def _tiles(tab: str) -> dict:
    bm = _board()
    return bm.board(tab=tab, limit=bm.LIMIT_MAX, universe="full") or {}


def _line(tile: dict, label: str) -> Optional[float]:
    for ln in tile.get("lines") or []:
        if isinstance(ln, dict) and str(ln.get("label") or "").strip().upper() == label:
            return _f(ln.get("price"))
    return None


def _tile_px(tile: dict) -> tuple:
    e = tile.get("enterable") or {}
    p = e.get("print") or {}
    px = _f(p.get("px"))
    if px is None:
        px = _f(tile.get("live_price"))
    return px, p.get("source")


def _tile_served(tile: dict) -> dict:
    amd = tile.get("amd_read") or {}
    ver = tile.get("verdict") if isinstance(tile.get("verdict"), dict) else {}
    return {"amd_grade": amd.get("grade"), "amd_phase": amd.get("phase"),
            "verdict_grade": ver.get("grade"), "levels_broken": tile.get("levels_broken"),
            "bias": tile.get("bias"), "state": tile.get("state"),
            "phase": tile.get("phase") if isinstance(tile.get("phase"), str) else None}


def _adapt_plan_tiles(tiles: list, out: _Out) -> None:
    """deep_demand: READY, with a served BUY and STOP line, STOP < print."""
    for rank, t in enumerate(tiles, start=1):
        sym = t.get("symbol")
        why_not = _read_reason(t.get("enterable"))
        if why_not:
            out.reject(why_not, sym)
            continue
        buy, stop = _line(t, "BUY"), _line(t, "STOP")
        if buy is None or stop is None:
            out.reject("no_stop", sym)
            continue
        px, src = _tile_px(t)
        if px is None or stop >= px:
            out.reject("stop_not_below_print", sym)
            continue
        out.keep(_candidate(sym, rank, enterable=t.get("enterable"), px=px, px_source=src,
                            plan={"buy": buy, "stop": stop, "target": _line(t, "TARGET"),
                                  "source": "served"},
                            band_structure=t.get("band_structure"), badges=t.get("badges"),
                            stats=t.get("stats"), why=t.get("why"), served=_tile_served(t)))


def _adapt_ict_tiles(tiles: list, out: _Out) -> None:
    """ict: plan.entry + plan.stop, bias bullish, state entry, stop < print, READY."""
    for rank, t in enumerate(tiles, start=1):
        sym = t.get("symbol")
        if t.get("bias") != "bullish":
            out.reject("not_bullish", sym)
            continue
        if t.get("state") != "entry":
            out.reject("not_entry_state", sym)
            continue
        plan = t.get("plan") if isinstance(t.get("plan"), dict) else {}
        entry, stop = _f(plan.get("entry")), _f(plan.get("stop"))
        if entry is None or stop is None:
            out.reject("no_stop", sym)
            continue
        px, src = _tile_px(t)
        if px is None or stop >= px:
            out.reject("stop_not_below_print", sym)
            continue
        why_not = _read_reason(t.get("enterable"))
        if why_not:
            out.reject(why_not, sym)
            continue
        out.keep(_candidate(sym, rank, enterable=t.get("enterable"), px=px, px_source=src,
                            plan={"buy": entry, "stop": stop, "target": plan.get("target"),
                                  "source": "served"},
                            band_structure=t.get("band_structure"), badges=t.get("badges"),
                            stats=t.get("stats"), why=t.get("why"), served=_tile_served(t)))


def _adapt_list_tiles(tiles: list, out: _Out) -> None:
    """amd / keltner / gabbar: READY on the served tile read; band-floor stop."""
    for rank, t in enumerate(tiles, start=1):
        sym = t.get("symbol")
        e = t.get("enterable")
        why_not = _read_reason(e)
        if why_not:
            out.reject(why_not, sym)
            continue
        stop = _band_floor_stop(e)
        px, src = _tile_px(t)
        if stop is None:
            out.reject("no_stop", sym)
            continue
        if px is None or stop >= px:
            out.reject("stop_not_below_print", sym)
            continue
        out.keep(_candidate(sym, rank, enterable=e, px=px, px_source=src,
                            plan={"buy": None, "stop": stop, "target": None,
                                  "source": "band_floor"},
                            band_structure=t.get("band_structure"), badges=t.get("badges"),
                            stats=t.get("stats"), why=t.get("why"), served=_tile_served(t)))


def _tile_board(tab: str, stamp_keys: tuple, fn: Callable) -> Callable:
    def adapter() -> dict:
        payload = _tiles(tab)
        tiles = [t for t in (payload.get("tiles") or []) if isinstance(t, dict)]
        out = _Out()
        out.universe_n = len(tiles)
        fn(tiles, out)
        ts, key = _stamp(payload, *stamp_keys)
        return out.result(ts, key)
    return adapter


def _na_tile_board(tab: str, stamp_keys: tuple, keep_tile: Callable = None) -> Callable:
    """undervalue / ipo / earnings: the tab kind is n/a, so the tile carries
    no demand read — collect the symbols, read them, keep READY rows."""
    def adapter() -> dict:
        payload = _tiles(tab)
        tiles = [t for t in (payload.get("tiles") or []) if isinstance(t, dict)]
        out = _Out()
        out.universe_n = len(tiles)
        items = []
        for rank, t in enumerate(tiles, start=1):
            why_not = keep_tile(t) if keep_tile else None
            if why_not:
                out.reject(why_not, t.get("symbol"))
                continue
            items.append((rank, t.get("symbol"), _tile_served(t), t.get("badges"),
                          t.get("stats"), t.get("why")))
        _keep_ready_rows(out, items)
        ts, key = _stamp(payload, *stamp_keys)
        return out.result(ts, key)
    return adapter


def _earnings_keep(tile: dict) -> Optional[str]:
    """REACTED only; an UPCOMING row is never a candidate."""
    from chart_maps import earnings as E                        # noqa: PLC0415
    return None if tile.get("phase") == E.REACTED else "upcoming"


# ═════════════════════════════════════════════════════════════════════════════
# ROW ADAPTERS — the tab's own builder
# ═════════════════════════════════════════════════════════════════════════════
def _adapt_bonde() -> dict:
    from sepa import bonde                                      # noqa: PLC0415
    b = bonde.board(new_days=bonde.NEW_DAYS) or {}
    out = _Out()
    items = []
    for section in ("explosive", "strong", "steady"):
        for r in ((b.get("sections") or {}).get(section) or []):
            out.universe_n += 1
            if r.get("is_new") is not True:
                out.reject("not_arrival", r.get("symbol"))
                continue
            items.append((out.universe_n, r.get("symbol"),
                          {"is_new": True, "tier": r.get("tier")},
                          None, None, r.get("bonde_reason")))
    _keep_ready_rows(out, items)
    ts, key = _stamp(b, "scan_ts")
    if ts is None:
        # The board reads the SEPA scan; its own stamp is the scan's generated_at.
        try:
            from sepa import scanner                            # noqa: PLC0415
            ts, key = _stamp(scanner.load_latest() or {}, "generated_at")
            key = f"sepa_scan.{key}" if key else None
        except Exception as exc:                                # noqa: BLE001
            log.warning("lane_snapshot: bonde scan stamp unavailable: %s", exc)
    return out.result(ts, key)


def _adapt_growth() -> dict:
    from growth import tracker                                  # noqa: PLC0415
    g = tracker.board() or {}
    out = _Out()
    items = []
    for r in g.get("rows") or []:
        out.universe_n += 1
        items.append((out.universe_n, r.get("symbol"), {"sales_tier": r.get("sales_tier")},
                      None, None, None))
    _keep_ready_rows(out, items)
    ts, key = _stamp(g, "built_at")
    return out.result(ts, key)


def _adapt_patterns() -> dict:
    from patterns import scan                                   # noqa: PLC0415
    p = scan.latest() or {}
    out = _Out()
    items = []
    for r in p.get("results") or []:
        out.universe_n += 1
        if r.get("status") != "confirmed":
            out.reject("not_confirmed", r.get("symbol"))
            continue
        items.append((out.universe_n, r.get("symbol"),
                      {"pattern": r.get("pattern"), "status": "confirmed"}, None, None, None))
    _keep_ready_rows(out, items)
    ts, key = _stamp(p, "generated_at")
    return out.result(ts, key)


def _gnt_fetch_stamp() -> tuple:
    """The newest stored post's `first_seen` — when the cron fetch saw it."""
    try:
        from traders import feed                                # noqa: PLC0415
        posts = feed.stored(limit=1, trader="gnt") or []
        if posts:
            ts, _ = _stamp(posts[0], "first_seen")
            if ts is not None:
                return ts, "newest_post.first_seen"
    except Exception as exc:                                    # noqa: BLE001
        log.warning("lane_snapshot: gnt fetch stamp unavailable: %s", exc)
    return None, None


def _adapt_gnt() -> dict:
    from traders import feed                                    # noqa: PLC0415
    g = feed.board(limit=400, trader="gnt") or {}
    out = _Out()
    items = []
    for r in g.get("tickers") or []:
        out.universe_n += 1
        if r.get("fresh") is not True:
            out.reject("not_fresh", r.get("symbol"))
            continue
        items.append((out.universe_n, r.get("symbol"), {"fresh": True}, None, None, None))
    _keep_ready_rows(out, items)
    ts, key = _gnt_fetch_stamp()
    if ts is None:
        ts, key = _stamp(g, "newest_post_at")
    return out.result(ts, key)


def _adapt_potus() -> dict:
    from political import api as political_api                 # noqa: PLC0415
    p = political_api._board(_max_candidates()) or {}
    out = _Out()
    items = []
    for r in p.get("entries") or []:
        out.universe_n += 1
        if r.get("is_new") is not True:
            out.reject("not_arrival", r.get("ticker"))
            continue
        items.append((out.universe_n, r.get("ticker"), {"is_new": True}, None, None,
                      r.get("notes")))
    _keep_ready_rows(out, items)
    ts, key = _stamp(p, "as_of")
    return out.result(ts, key)


def _adapt_overnight() -> dict:
    from daytrading import premarket                            # noqa: PLC0415
    g = premarket.gappers("aggressive", False) or {}
    out = _Out()
    items = []
    for r in g.get("gappers") or []:
        out.universe_n += 1
        if r.get("direction") != "up":
            out.reject("not_up", r.get("symbol"))
            continue
        items.append((out.universe_n, r.get("symbol"),
                      {"direction": "up", "gap_pct": r.get("gap_pct")}, None, None, None))
    _keep_ready_rows(out, items)
    ts, key = _stamp(g, "as_of")
    return out.result(ts, key)


def _adapt_session() -> dict:
    """session: `row.signal.trade` only (never the SMC fallback); the served
    STOP is the stop, READY on the live read, stop < print."""
    from supply_demand import session_board                     # noqa: PLC0415
    s = session_board.cached_or_warm() or {}
    out = _Out()
    rows = [r for r in (s.get("rows") or []) if isinstance(r, dict)]
    out.universe_n = len(rows)
    trades = []
    for rank, r in enumerate(rows, start=1):
        trade = (r.get("signal") or {}).get("trade") or {}
        entry, stop = _f(trade.get("entry")), _f(trade.get("stop"))
        if entry is None or stop is None:
            out.reject("no_stop", r.get("symbol"))
            continue
        if stop >= entry:
            out.reject("not_long", r.get("symbol"))
            continue
        trades.append((rank, r, entry, stop, _f(trade.get("target1"))))
    reads = _bounce_rows([str(t[1].get("symbol") or "").upper()
                          for t in trades][:_max_candidates()])
    for rank, r, entry, stop, tgt in trades:
        sym = str(r.get("symbol") or "").upper()
        row = reads.get(sym) or {}
        cov = row.get("coverage")
        if cov not in ("store", "ondemand"):
            out.reject(str(cov or "pending"), sym)
            continue
        e = row.get("enterable")
        why_not = _read_reason(e)
        if why_not:
            out.reject(why_not, sym)
            continue
        px = _f(row.get("print"))
        if px is None or stop >= px:
            out.reject("stop_not_below_print", sym)
            continue
        out.keep(_candidate(sym, rank, enterable=e, px=px,
                            px_source=((e or {}).get("print") or {}).get("source"),
                            plan={"buy": entry, "stop": stop, "target": tgt, "source": "served"},
                            band_structure=row.get("band_structure"),
                            served={"action": (r.get("signal") or {}).get("action")}))
    ts, key = _stamp(s, "as_of")
    return out.result(ts, key)


def _adapt_hot_sectors() -> dict:
    """The 🔥 Hottest board's name rows, in served sector order."""
    from rotation import api as RA                              # noqa: PLC0415
    from rotation import hottest as H                           # noqa: PLC0415
    table, _meta = RA._members_table()
    out = _Out()
    if table is None:
        return out.result(None, None)
    payload = dict(RA._members_payload() or {})
    payload[RA.T.MEMBERS_KEY] = table
    body = H.build_live(payload) or {}
    items = []
    for grp in body.get("sectors") or []:
        for n in (grp or {}).get("names") or []:
            out.universe_n += 1
            items.append((out.universe_n, n.get("symbol"), {"sector": grp.get("group")},
                          None, None, None))
    _keep_ready_rows(out, items)
    ts, key = _stamp(body, "built_at")
    return out.result(ts, key)


# ═════════════════════════════════════════════════════════════════════════════
# THE ADAPTER TABLE — generic sids only. vcp (OFF with Minervini), topping
# (bearish), and every not-a-lane tab are deliberately ABSENT.
# ═════════════════════════════════════════════════════════════════════════════
ADAPTERS: dict = {
    "deep_demand": _tile_board("deep_demand", ("generated_at",), _adapt_plan_tiles),
    "ict": _tile_board("ict", ("generated_at", "as_of"), _adapt_ict_tiles),
    "amd": _tile_board("amd", ("built_at",), _adapt_list_tiles),
    "keltner": _tile_board("keltner", ("built_at",), _adapt_list_tiles),
    # gabbar / undervalue serve no build stamp (generated_at None) → the lane
    # fails closed as "build time unknown" (spec §3.7).
    "gabbar": _tile_board("gabbar", ("generated_at",), _adapt_list_tiles),
    "undervalue": _na_tile_board("undervalue", ("generated_at",)),
    "ipo": _na_tile_board("ipo", ("as_of",)),
    "earnings": _na_tile_board("earnings", ("as_of",), keep_tile=_earnings_keep),
    "bonde": _adapt_bonde,
    "growth": _adapt_growth,
    "patterns": _adapt_patterns,
    "gnt": _adapt_gnt,
    "potus": _adapt_potus,
    "overnight": _adapt_overnight,
    "session": _adapt_session,
    "hot_sectors": _adapt_hot_sectors,
}


# ═════════════════════════════════════════════════════════════════════════════
# THE JOB
# ═════════════════════════════════════════════════════════════════════════════
def _default_sids() -> list:
    """Generic roster lanes that are ON right now (program + per-strategy switch)."""
    from trading import exit_engine as EE                       # noqa: PLC0415
    from trading import program_caps as PC                      # noqa: PLC0415
    from trading import strategy_tags as ST                     # noqa: PLC0415
    cfg = EE.get_config()
    mode = EE._broker_mode()
    out = []
    for sid in ST.lane_sids():
        r = _roster_entry(sid) or {}
        if r.get("lane") == "generic" and sid in ADAPTERS and PC.strategy_on(sid, cfg, mode):
            out.append(sid)
    return out


def _snapshot_coll():
    coll_name, _ = _lanes_consts()
    try:
        from portfolio.store import _get_db                     # noqa: PLC0415
        db = _get_db()
        return db[coll_name] if db is not None else None
    except Exception as exc:                                    # noqa: BLE001
        log.warning("lane_snapshot: no mongo: %s", exc)
        return None


def _build_one(sid: str, now: datetime) -> dict:
    t0 = time.monotonic()
    err = None
    try:
        res = ADAPTERS[sid]() or {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("lane_snapshot: %s builder failed: %s", sid, exc)
        err = f"{type(exc).__name__}: {exc}"[:300]
        res = {}
    built_ms = int(round((time.monotonic() - t0) * 1000))
    r = _roster_entry(sid) or {}
    try:
        _, version = _lanes_consts()
    except Exception as exc:                                    # noqa: BLE001
        log.debug("lane_snapshot: adapter version unavailable: %s", exc)
        version = None
    tabs = r.get("tabs") or [sid]
    return {"_id": sid, "sid": sid, "tab": (tabs[0] if tabs else sid),
            "adapter": r.get("adapter"), "adapter_version": version,
            "day": now.astimezone(ET).date().isoformat(),
            "as_of": now.astimezone(ET).isoformat(),
            "source_as_of": res.get("source_as_of"), "source_key": res.get("source_key"),
            "built_ms": built_ms, "universe_n": int(res.get("universe_n") or 0),
            "candidates": list(res.get("candidates") or [])[:_max_candidates()],
            "rejected": dict(res.get("rejected") or {}),
            "rejected_syms": dict(res.get("rejected_syms") or {}),
            "error": err}


def run(sids: Optional[Iterable] = None, record: bool = True,
        now: Optional[datetime] = None) -> dict:
    """Build (and, with `record`, store) one snapshot doc per sid.

    Closed day → {"skipped": reason} and nothing is built or written. Each sid
    is fenced: a builder that raises stores its `error` with no candidates (the
    lane then has nothing to buy) and the other sids still build."""
    from market_hours import gate                               # noqa: PLC0415
    now = now or _now_et()
    closed = gate.closed_reason(now)
    if closed:
        return {"skipped": closed}
    if not _RUN_LOCK.acquire(blocking=False):
        return {"skipped": "a snapshot pass is already running"}
    try:
        if sids is None:
            try:
                todo = _default_sids()
            except Exception as exc:                            # noqa: BLE001
                log.warning("lane_snapshot: roster unavailable: %s", exc)
                return {"skipped": f"roster unavailable: {type(exc).__name__}"}
        else:
            todo = [str(s).strip() for s in sids if str(s).strip()]
        coll = None
        if record:
            try:
                coll = _snapshot_coll()
            except Exception as exc:                            # noqa: BLE001
                log.warning("lane_snapshot: snapshot collection unavailable: %s", exc)
        out: dict = {}
        for sid in todo:
            if sid not in ADAPTERS:
                out[sid] = {"skipped": "not a snapshot lane"}
                continue
            doc = _build_one(sid, now)
            written = False
            if record and coll is not None:
                try:
                    coll.replace_one({"_id": sid}, doc, upsert=True)
                    written = True
                except Exception as exc:                        # noqa: BLE001
                    log.warning("lane_snapshot: write failed for %s: %s", sid, exc)
            out[sid] = {"n": len(doc["candidates"]), "built_ms": doc["built_ms"],
                        "source_as_of": doc["source_as_of"], "source_key": doc["source_key"],
                        "universe_n": doc["universe_n"], "rejected": doc["rejected"],
                        "rejected_syms": doc["rejected_syms"], "error": doc["error"],
                        "written": written}
        return out
    finally:
        _RUN_LOCK.release()
