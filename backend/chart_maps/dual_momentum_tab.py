"""🏎️ Dual Momentum tab on Chart Maps (Ajay 2026-09-29).

The asks, verbatim:
  "Can you pull these in to chart maps and add the demand zones logic to
   these? https://pounce.ajaykandakatla.dev/dual-momentum"
  "I want a toggle and also the check boxes we have like AMD and supple and
   demand zones computing and also key levels"

THE POPULATION is the Dual Momentum page's own engine,
`sepa.dual_momentum.compute`, with the engine's own defaults (the page's
defaults) — the same picks in the same rank. Nothing here re-ranks, re-weights
or re-gates them; the SPY-12m hurdle is his pending call and is untouched.

ONE ZONE ENGINE. The band is `bounce_room.demand_read` over the stored
board-geometry docs (`zone_store`), the room is `room_floor.room_block /
room_stat` (the demand boards' tile wording), and the gate read is the 🎯
`enterable` read — `alert_gates.room_gate` + `demand_proximity_gate` + the
floor read — copied off the tile, never recomputed here and never loosened.

THE MEMO. `compute()` costs ~4-6 s (one price read per scanned name), so the
result is memoised per scan generation (the `latest.json` mtime) and ET date,
built in a daemon thread (the key_levels_tab pattern) and served
stale-while-revalidate. `MEMO_TTL_SEC` is cache freshness only, never a rule.

WRITES: this module writes nothing — no Mongo, no file. The engine's own
`prices.load_prices` may fetch and cache a cold symbol, exactly as the Dual
Momentum page does today on every request.

UNMEASURED: no study in this app says a dual-momentum leader sitting near a
demand band does better than one that is not. Nothing here gates a scan,
pushes a phone, sizes a position or enters a lane.
"""
from __future__ import annotations

import inspect
import logging
import math
import threading
import time
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from supply_demand import alert_gates as AG

log = logging.getLogger("chart_maps.dual_momentum_tab")

ET = ZoneInfo("America/New_York")

MARK = "\U0001F3CE️"                    # 🏎️ (VS16 included — FE literal must match)
MEASURED = False
MEMO_TTL_SEC = 30 * 60                        # cache freshness, NOT a rule
# After a FAILED build the tab serves the failure (state "error" / "no_scan")
# and retries at most once per FAIL_RETRY_SEC, instead of "warming" forever
# with a fresh full compute() on every 10-s poll. Retry cadence, NOT a rule.
FAIL_RETRY_SEC = 5 * 60
SORT_NEAREST_DEMAND = "nearest_demand"
DEFAULT_SORT_LABEL = f"{MARK} Dual-momentum rank"
NEAREST_SORT_LABEL = "\U0001F4CD Nearest demand first"   # 📍
RANK_CHIP_FMT = MARK + " #{rank} dual momentum"          # IDENT rung (FE prefix "🏎️ #")
NO_BAND_TEXT = "→ no demand band under the price"
NO_DOC_TEXT = "→ no demand band — no stored bands for this name"
NO_PRINT_TEXT = "→ no print to read the bands against"
PAGE_ROUTE = "/dual-momentum"
COUNT_KEYS = ("pool", "with_band", "no_band", "no_doc", "no_print",
              "held", "swept", "broken", "floor_unknown", "dropped_thin", "shown")
FLOOR_UNKNOWN = "unknown"
# The floor-state vocabulary is sd_liquidity.find_sweep's (sd_liquidity.py:91
# intact, :144 swept, :159 broken) plus alert_gates.sweep_read's "broken"
# (alert_gates.py:762). Held = AG.FLOOR_HELD_STATES. A test pins these
# literals against that source.
FLOOR_ORDER = {"swept": 2, "broken": 3}       # held -> 0, unknown -> 1, any other state -> 3

NOTE = (f"{MARK} UNMEASURED — no study in this app says a dual-momentum leader "
        "sitting near a demand band does better than one that is not. The zone read, "
        "the \U0001F3AF gate read and the \U0001F4CD order are the same ones the demand "
        "boards use; nothing here gates a scan, pushes a phone, sizes a position or "
        "enters a lane.")
WARMING_NOTE = (f"{MARK} Ranking every name the way the Dual Momentum page does — "
                "the charts appear here as soon as it lands; you don't need to refresh.")
NO_SCAN_NOTE = "no SEPA scan on disk yet — run a scan first"
ERROR_NOTE_FMT = (f"{MARK} The Dual Momentum ranking could not be built ({{reason}}). "
                  "It is retried every {mins} minutes — this is not a warming state.")
EMPTY_NOTE = f"{MARK} No name passes absolute momentum right now."
NEAREST_SORT_UNAVAILABLE = ("No demand band under any of these leaders — the board "
                            "is showing the dual-momentum rank.")
SPY_MISSING = "—"
DISCLAIMER = ("Leaders ranked by the Dual Momentum page's own engine; bands from the "
              "demand engine (board geometry). UNMEASURED together. Not advice.")

_NO_TEXT = {"no_band": NO_BAND_TEXT, "no_doc": NO_DOC_TEXT, "no_print": NO_PRINT_TEXT}

# ONE newest entry: {"key": (generation, et_date_iso, pool_n), "entry": {...}}
_memo: dict = {}
_warming: set = set()
# ONE newest failure: {"key": (generation, et_date_iso, pool_n), "ts", "reason", "no_scan"}
_failed: dict = {}
_lock = threading.Lock()


def _f(v) -> Optional[float]:
    """A finite float or None (NaN never reaches JSON)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _et(now: Optional[datetime]) -> datetime:
    now = now or datetime.now(ET)
    if now.tzinfo is None:
        now = now.replace(tzinfo=ET)
    return now.astimezone(ET)


# ---------------------------------------------------------------------------
# the memo
# ---------------------------------------------------------------------------
def scan_generation() -> Optional[int]:
    """The scan file's mtime (seconds), or None when no scan is on disk."""
    try:
        from sepa import scanner
        return int(scanner.LATEST_PATH.stat().st_mtime)
    except (FileNotFoundError, OSError):
        return None
    except Exception as exc:                                    # noqa: BLE001
        log.debug("dual momentum tab: scan generation unreadable: %s", exc)
        return None


def _engine_min_rs(fn) -> float:
    """The engine's OWN default RS floor (the page's default) — read off its
    signature, never retyped here."""
    try:
        d = inspect.signature(fn).parameters["min_rs_rank"].default
        return float(d) if d is not inspect.Parameter.empty else 0.0
    except (KeyError, TypeError, ValueError):
        return 0.0


class EngineNoScan(RuntimeError):
    """The engine answered `error: "no_scan"` (a scan file with no rows)."""


def build(pool_n: int, *, compute_fn=None, scan_fn=None) -> dict:
    """ONE engine call with the page's defaults (only `top_n` differs; the
    rank does not depend on it) + ONE scan read for the pool's rows.

    Raises RuntimeError on an engine error or an empty engine answer (no rows
    or no picks list), so a failed build is never memoised. An engine answer
    with rows but no pick is a real answer (EMPTY_NOTE), not an error."""
    min_rs_fn = None
    if compute_fn is None:
        from sepa import dual_momentum as DM
        compute_fn = DM.compute
        min_rs_fn = DM.compute
    res = compute_fn(top_n=int(pool_n))
    if isinstance(res, dict) and res.get("error") == "no_scan":
        raise EngineNoScan("dual momentum tab: the engine answered 'no_scan' — not memoising")
    if not isinstance(res, dict) or res.get("error"):
        raise RuntimeError("dual momentum tab: the engine answered %r — not memoising"
                           % ((res or {}).get("error") if isinstance(res, dict) else res))
    rows = res.get("rows")
    picks = res.get("picks")
    if not isinstance(rows, list) or not rows or not isinstance(picks, list):
        raise RuntimeError("dual momentum tab: the engine returned no rows — not memoising")
    if scan_fn is None:
        from sepa import scanner
        scan_fn = scanner.load_latest
    want = {str(p.get("symbol") or "").upper() for p in picks if isinstance(p, dict)}
    scan_rows: dict = {}
    try:
        latest = scan_fn() or {}
        for r in latest.get("all_results") or []:
            sym = str((r or {}).get("symbol") or "").upper() if isinstance(r, dict) else ""
            if sym and sym in want:
                scan_rows[sym] = r
    except Exception as exc:                                    # noqa: BLE001
        log.warning("dual momentum tab: scan rows unavailable: %s", exc)
    min_rs = _engine_min_rs(min_rs_fn or compute_fn)
    eligible = sum(1 for r in rows if isinstance(r, dict) and r.get("abs_mom_pass")
                   and (_f(r.get("rs_rank")) or 0.0) >= min_rs)
    now_ts = time.time()
    return {"key": None, "built_ts": now_ts,
            "built_at": datetime.fromtimestamp(now_ts, tz=ET).isoformat(timespec="seconds"),
            "generated_at": res.get("generated_at"),
            "generated_at_iso": res.get("generated_at_iso"),
            "scan_generated_at": res.get("scan_generated_at"),
            "regime": res.get("regime"),
            "gate_lookback_days": res.get("gate_lookback_days"),
            "universe_size": res.get("universe_size"),
            "eligible": eligible,
            "picks": [p for p in picks if isinstance(p, dict)],
            "scan_rows": scan_rows}


def _spawn(target, name: str) -> None:
    threading.Thread(target=target, name=name, daemon=True).start()


def _newer(a: tuple, b: tuple) -> bool:
    """Is key `a` a NEWER scan generation / date than key `b`?"""
    return (a[0], a[1]) > (b[0], b[1])


def _store(key: tuple, entry: dict) -> bool:
    """Store unless the memo already holds a NEWER key (a late build for an
    older generation never overwrites a newer one). Call under `_lock`."""
    held = _memo.get("key")
    if held is not None and _newer(held, key):
        log.info("dual momentum tab: dropped a late %s build (memo holds %s)", key, held)
        return False
    entry["key"] = list(key)
    _memo.clear()
    _memo.update(key=key, entry=entry)
    return True


def _record_failure(key: tuple, exc: BaseException) -> None:
    """Remember the newest failure (call under `_lock`)."""
    _failed.clear()
    _failed.update(key=key, ts=time.time(), reason=str(exc)[:200],
                   no_scan=isinstance(exc, EngineNoScan))


def _clear_failure(key: tuple) -> None:
    """A successful build for `key` forgets its failure (call under `_lock`)."""
    if _failed.get("key") == key:
        _failed.clear()


def _failure(key: tuple) -> Optional[dict]:
    """The recorded failure for `key`, or None (call under `_lock`)."""
    return dict(_failed) if _failed.get("key") == key else None


def _warm(key: tuple) -> None:
    def _work():
        try:
            entry = build(key[2])
            with _lock:
                _store(key, entry)
                _clear_failure(key)
        except Exception as exc:                                # noqa: BLE001
            log.warning("dual momentum tab: build failed for %s: %s", key, exc)
            with _lock:
                _record_failure(key, exc)
        finally:
            with _lock:
                _warming.discard(key)

    with _lock:
        if key in _warming:
            return
        _warming.add(key)
    _spawn(_work, f"dual-momentum-tab-{key[0]}-{key[1]}")


def cached_or_warm(*, now: datetime, pool_n: int, sync: bool = False) -> dict:
    """{"state": "ready"|"warming"|"no_scan"|"error", "entry"[, "reason"]}.
    Key = (scan generation, ET date, pool_n). No scan on disk -> no_scan (the
    engine is never called). Held + same key + fresh -> ready. Held but
    another key or older than MEMO_TTL_SEC -> ready with the HELD entry and
    ONE background rebuild. Nothing held -> ONE background build, warming.

    A FAILED build for this key is served as the failure — "no_scan" when the
    engine answered `no_scan`, else "error" with the reason — never as
    "warming"; it is retried at most once per FAIL_RETRY_SEC (a held entry
    keeps being served meanwhile). `sync=True` builds inline (tests) and
    re-raises a failure after recording it."""
    gen = scan_generation()
    if gen is None:
        return {"state": "no_scan", "entry": None}
    key = (gen, _et(now).date().isoformat(), int(pool_n))
    with _lock:
        held_key, entry = _memo.get("key"), _memo.get("entry")
    fresh = (entry is not None and held_key == key
             and (time.time() - float(entry.get("built_ts") or 0)) < MEMO_TTL_SEC)
    if fresh:
        return {"state": "ready", "entry": entry}
    if sync:
        try:
            built = build(key[2])
        except Exception as exc:
            with _lock:
                _record_failure(key, exc)
            raise
        with _lock:
            _store(key, built)
            _clear_failure(key)
        return {"state": "ready", "entry": built}
    with _lock:
        failed = _failure(key)
    backing_off = (failed is not None
                   and (time.time() - float(failed.get("ts") or 0)) < FAIL_RETRY_SEC)
    if not backing_off:
        _warm(key)
    if entry is not None:
        return {"state": "ready", "entry": entry}
    if failed is not None:
        if failed.get("no_scan"):
            return {"state": "no_scan", "entry": None}
        return {"state": "error", "entry": None, "reason": failed.get("reason") or "unknown"}
    return {"state": "warming", "entry": None}


# ---------------------------------------------------------------------------
# the zone read — PURE, from the ONE engine's outputs
# ---------------------------------------------------------------------------
def floor_state_word(floor_state) -> str:
    """The raw floor state, stripped and lowercased. None / blank ->
    FLOOR_UNKNOWN. Never collapses one state into another."""
    if floor_state is None:
        return FLOOR_UNKNOWN
    s = str(floor_state).strip().lower()
    return s or FLOOR_UNKNOWN


def floor_rank(word) -> int:
    """held 0 · unknown 1 · swept 2 · broken 3 · any other state 3."""
    if word in AG.FLOOR_HELD_STATES:
        return 0
    if word == FLOOR_UNKNOWN:
        return 1
    return FLOOR_ORDER.get(word, 3)


def _band_txt(demand: dict) -> str:
    return f"{float(demand['lo']):.2f}–{float(demand['hi']):.2f}"


def zone_read(px, doc, enterable, *, prev_close=None) -> dict:
    """The `dm_zone` block. The print is the 🎯 read's own (one print for both
    reads); `doc` is the SAME dict the builder handed `attach_enterable`, so
    `demand` lo/hi equal `enterable.band` by construction. The gate fields are
    COPIED from the 🎯 read, never recomputed."""
    from supply_demand import bounce_room, room_floor

    en = enterable if isinstance(enterable, dict) else {}
    pr = en.get("print") if isinstance(en.get("print"), dict) else {}
    p = _f(pr.get("px"))
    src = pr.get("source")
    if p is None:
        p, src = _f(px), "scan"
    src = src or "scan"
    gates = en.get("gates") if isinstance(en.get("gates"), dict) else {}
    raw_floor = gates.get("floor_state")
    gate = ({"verdict": en.get("verdict"), "room_ok": gates.get("room_ok"),
             "prox_ok": gates.get("prox_ok")} if en else None)
    d = doc if isinstance(doc, dict) else {}
    base = {"demand": None, "room": None, "room_stat": room_floor.room_stat(None),
            "floor": floor_state_word(raw_floor), "floor_state": raw_floor,
            "floor_held": floor_state_word(raw_floor) in AG.FLOOR_HELD_STATES,
            "gate": gate, "print": {"px": None if p is None or p <= 0 else p, "source": src}}
    if not d.get("bands"):
        reason = "no_doc"
    elif p is None or p <= 0:
        reason = "no_print"
    else:
        demand = bounce_room.demand_read(p, d)
        if demand is None:
            reason = "no_band"
        else:
            basis = "live" if src == "live" else "scan"
            room = room_floor.room_block(p, d.get("bands") or [], demand, prev_close, basis)
            z = {**base, "reason": "ok", "demand": demand, "room": room,
                 "room_stat": room_floor.room_stat(room)}
            z["text"] = zone_text(z)
            return z
    z = {**base, "reason": reason}
    z["text"] = zone_text(z)
    return z


def zone_text(zone: dict) -> str:
    """The zone half of the tile sentence."""
    dem = (zone or {}).get("demand")
    if (zone or {}).get("reason") != "ok" or not isinstance(dem, dict):
        return _NO_TEXT.get((zone or {}).get("reason"), NO_BAND_TEXT)[2:]
    if dem.get("in_band"):
        where = f"in its demand band {_band_txt(dem)}"
    else:
        where = f"{float(dem['distance_pct']):.2f}% above its demand band {_band_txt(dem)}"
    from supply_demand import room_floor
    room = zone.get("room_stat") or room_floor.room_stat(None)
    return f"{where} · room {room} · floor {zone.get('floor') or FLOOR_UNKNOWN}"


def nearest_demand_key(zone, rank, symbol) -> tuple:
    """📍 intact -> unknown -> swept -> broken -> no band; closest first
    inside a group; then the page's rank; then the symbol."""
    r = int(rank) if _f(rank) is not None else 10 ** 6
    dem = (zone or {}).get("demand")
    if not isinstance(dem, dict) or _f(dem.get("distance_pct")) is None:
        return (4, 0.0, r, str(symbol or ""))
    return (floor_rank((zone or {}).get("floor") or FLOOR_UNKNOWN),
            float(dem["distance_pct"]), r, str(symbol or ""))


def rank_key(rank, symbol) -> tuple:
    r = int(rank) if _f(rank) is not None else 10 ** 6
    return (r, str(symbol or ""))


def _pct(v) -> str:
    f = _f(v)
    return "—" if f is None else f"{f:+.1f}%"


def dm_stats(pick: dict) -> list:
    p = pick or {}
    rs = _f(p.get("rs_rank"))
    return [{"k": "12m", "v": _pct(p.get("return_12m"))},
            {"k": "6m", "v": _pct(p.get("return_6m"))},
            {"k": "3m", "v": _pct(p.get("return_3m"))},
            {"k": "1m", "v": _pct(p.get("return_1m"))},
            {"k": "RS", "v": "—" if rs is None else f"{rs:.0f}"}]


def zone_stats(zone: dict) -> list:
    """`Room` (plan) and `Band` (the floor fold). No `To band`: the distance
    lives once, on the PRICE-rung badge."""
    ok = (zone or {}).get("reason") == "ok"
    return [{"k": "Room", "v": (zone.get("room_stat") or "—") if ok else "—"},
            {"k": "Band", "v": f"floor {zone.get('floor') or FLOOR_UNKNOWN}" if ok else "—"}]


def zone_badge(zone: dict, dist_badge=None) -> dict:
    """With a band: the board's `_dist_badge` (passed in by the builder).
    Without: the honest NO_* text, muted."""
    z = zone or {}
    dem = z.get("demand")
    if z.get("reason") == "ok" and isinstance(dem, dict) and callable(dist_badge):
        return dist_badge(dem.get("distance_pct"), "the demand band")
    return {"text": _NO_TEXT.get(z.get("reason"), NO_BAND_TEXT), "tone": "muted"}


def why_text(pick: dict, zone: dict) -> str:
    p = pick or {}
    return (f"{RANK_CHIP_FMT.format(rank=p.get('rank'))} · 12m "
            f"{_pct(p.get('return_12m'))} · {zone_text(zone)}")


def regime_line(regime) -> str:
    if not isinstance(regime, dict):
        return f"{MARK} regime unavailable"
    spy = _f(regime.get("spy_return_12m"))
    spy_txt = SPY_MISSING if spy is None else f"{spy:+.2f}%"
    return f"{MARK} {regime.get('label') or ''} · SPY 12m {spy_txt} (the page's hurdle)"


def _n(x) -> str:
    try:
        return f"{int(x or 0):,}"
    except (TypeError, ValueError):
        return "0"


def _min_cap_txt() -> str:
    try:
        from supply_demand import zone_store
        return f"${float(zone_store.MIN_CAP_USD) / 1e6:,.0f}M"
    except Exception:                                           # noqa: BLE001
        return "the store's"


def header_text(counts: dict, *, entry: dict, sort: str, themes_first: bool) -> str:
    c = counts or {}
    e = entry or {}
    built = e.get("built_at") or "\u2014"
    order = ("" if sort != SORT_NEAREST_DEMAND else
             " — reordered \U0001F4CD nearest demand first (floor intact, then unknown, "
             "then swept, then broken; closest first; rank breaks ties)")
    if themes_first:
        order += " — theme names lead (themes box)"
    return (f"{MARK} Ranks 1–{_n(c.get('pool'))} of the {_n(e.get('eligible'))} names "
            f"with a positive 12-month return, in the Dual Momentum page's own order{order}. "
            f"{_n(c.get('with_band'))} sit above a demand band ({_n(c.get('held'))} with the "
            f"floor intact, {_n(c.get('swept'))} swept, {_n(c.get('broken'))} broken, "
            f"{_n(c.get('floor_unknown'))} unknown), {_n(c.get('no_band'))} have no demand band "
            f"under the price, {_n(c.get('no_doc'))} have no stored bands (the store covers "
            f"names at or above {_min_cap_txt()} cap), {_n(c.get('no_print'))} had no print. "
            f"{_n(c.get('dropped_thin'))} under the liquidity floor; showing "
            f"{_n(c.get('shown'))}. Ranked {built} from the "
            f"{_scan_txt(e.get('scan_generated_at'))} scan.")


def _scan_txt(v) -> str:
    f = _f(v)
    if f is not None and f > 1e9:
        return datetime.fromtimestamp(f, tz=ET).isoformat(timespec="minutes")
    return str(v) if v not in (None, "") else "—"


def _block(state: str, *, entry: Optional[dict], counts, sort, header: str) -> dict:
    e = entry or {}
    return {"state": state, "regime": e.get("regime"),
            "regime_line": regime_line(e.get("regime")) if entry else None,
            "gate_lookback_days": e.get("gate_lookback_days"),
            "pool": len(e.get("picks") or []) if entry else None,
            "eligible": e.get("eligible"), "universe": e.get("universe_size"),
            "counts": dict(counts) if counts is not None else None,
            "sort": sort, "header": header, "note": NOTE,
            "built_at": e.get("built_at"),
            "scan_generated_at": e.get("scan_generated_at"),
            "page_route": PAGE_ROUTE, "measured": MEASURED}


def ready_block(counts: dict, *, entry: dict, sort: str, themes_first: bool) -> dict:
    return _block("ready", entry=entry, counts=counts, sort=sort,
                  header=header_text(counts, entry=entry, sort=sort,
                                     themes_first=themes_first))


def warming_block() -> dict:
    return _block("warming", entry=None, counts=None, sort=None, header=WARMING_NOTE)


def no_scan_block() -> dict:
    return _block("no_scan", entry=None, counts=None, sort=None, header=NO_SCAN_NOTE)


def error_note(reason) -> str:
    return ERROR_NOTE_FMT.format(reason=str(reason or "unknown"),
                                 mins=int(FAIL_RETRY_SEC // 60))


def error_block(reason) -> dict:
    return _block("error", entry=None, counts=None, sort=None, header=error_note(reason))
