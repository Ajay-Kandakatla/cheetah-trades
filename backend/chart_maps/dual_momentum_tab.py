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

THE FILTERS (Ajay 2026-09-29, verbatim): "Can you add AMD raided and near
demand zone and near lower Key level filters to dual momentum please".
The three filters are VIEWS over existing reads — 🌀 the AMD Raided tab's own
stored sweep grade (`rotation.hottest_amd.attach`, MEASURED INVERTED on its
own claim), 📍 the 🎯 gate's own proximity read copied onto `dm_zone`, and 🔑
the Key Levels tab's own `build` / `rank` (UNMEASURED; the 1% cut is his
call). They narrow the leaders shown; they gate nothing, push nothing, sort
nothing and enter no lane.
"""
from __future__ import annotations

import copy
import inspect
import logging
import math
import threading
import time
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from supply_demand import alert_gates as AG
from supply_demand import turning_bullish as TB

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
# 💰 market cap order (Ajay 2026-09-29: "Also a sort by market cap please").
# Two tab-scoped keys so the direction lives in `?sort=` like the toggle:
# largest first is the first click, smallest first the second. Display only.
SORT_MARKET_CAP = "market_cap"
SORT_MARKET_CAP_ASC = "market_cap_asc"
CAP_SORTS = (SORT_MARKET_CAP, SORT_MARKET_CAP_ASC)
TAB_SORTS = (SORT_NEAREST_DEMAND,) + CAP_SORTS          # every key only this tab honours
MARKET_CAP_LABEL = "\U0001F4B0 Market cap \u2014 largest first"      # 💰
MARKET_CAP_ASC_LABEL = "\U0001F4B0 Market cap \u2014 smallest first"
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
# ONE newest 🔑 pool entry for the filter read: {"key": (session_iso,
# generation, syms, universe), "entry", "ts"} — see `_kl_pool_entry`.
_kl_memo: dict = {}


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


def market_cap_key(cap, rank, symbol, *, largest_first: bool = True) -> tuple:
    """💰 known caps first — largest (or smallest) first; a name with no
    cached cap (None / NaN / not positive) sorts LAST in BOTH directions;
    ties -> the page's rank, then the symbol."""
    r = int(rank) if _f(rank) is not None else 10 ** 6
    c = _f(cap)
    if c is None or c <= 0:
        return (1, 0.0, r, str(symbol or ""))
    return (0, -c if largest_first else c, r, str(symbol or ""))


def market_caps(syms, *, caps_fn=None) -> dict:
    """{SYM: cap or None} — the app's ONE cached cap: the weekly shares cache
    read through `catalysts.promo_circuit.market_caps_for` (the reader the
    demand / zone-edge cap gates and the 🪜 band note use; its stored
    `market_cap` is the field `trading.safety_floor` reads for the cap
    floor). `cap=0` cuts its provider tail — a render never becomes one
    network call per name. Fails open to every name None (sorted last)."""
    syms = [str(s) for s in (syms or [])]
    if caps_fn is None:
        from catalysts.promo_circuit import market_caps_for

        def caps_fn(names):
            return market_caps_for(names, {}, cap=0)
    try:
        got = caps_fn(list(syms)) or {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("dual momentum tab: market-cap read failed: %s", exc)
        got = {}
    got = got if isinstance(got, dict) else {}
    return {s: _f(got.get(s)) for s in syms}


def cap_block(caps: dict, syms, sort: str) -> Optional[dict]:
    """The served 💰 line when a cap order is on (None otherwise): which way,
    and how many of the ordered leaders had no cached cap (they sit last)."""
    if sort not in CAP_SORTS:
        return None
    syms = list(syms or [])
    c = caps if isinstance(caps, dict) else {}
    none = sum(1 for s in syms if (_f(c.get(s)) or 0.0) <= 0)
    largest = sort == SORT_MARKET_CAP
    line = (f"\U0001F4B0 Ordered by market cap, {'largest' if largest else 'smallest'} "
            f"first — the weekly shares-cache cap; display only, it gates nothing. "
            f"{_n(none)} of {_n(len(syms))} leaders have no cached market cap — they sit "
            "last, in rank order.")
    return {"sort": sort, "largest_first": largest, "ordered": len(syms),
            "with_cap": len(syms) - none, "no_cap": none, "line": line}


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
    if sort in CAP_SORTS:
        order = (" — reordered \U0001F4B0 by market cap, "
                 f"{'largest' if sort == SORT_MARKET_CAP else 'smallest'} first "
                 "(no cached cap last; rank breaks ties)")
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


def _block(state: str, *, entry: Optional[dict], counts, sort, header: str,
           filters: Optional[dict] = None, cap_sort: Optional[dict] = None) -> dict:
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
            "page_route": PAGE_ROUTE, "measured": MEASURED, "filters": filters,
            "cap_sort": cap_sort}


def ready_block(counts: dict, *, entry: dict, sort: str, themes_first: bool,
                filters: Optional[dict] = None, cap_sort: Optional[dict] = None) -> dict:
    return _block("ready", entry=entry, counts=counts, sort=sort,
                  header=header_text(counts, entry=entry, sort=sort,
                                     themes_first=themes_first), filters=filters,
                  cap_sort=cap_sort)


def warming_block() -> dict:
    return _block("warming", entry=None, counts=None, sort=None, header=WARMING_NOTE)


def no_scan_block() -> dict:
    return _block("no_scan", entry=None, counts=None, sort=None, header=NO_SCAN_NOTE)


def error_note(reason) -> str:
    return ERROR_NOTE_FMT.format(reason=str(reason or "unknown"),
                                 mins=int(FAIL_RETRY_SEC // 60))


def error_block(reason) -> dict:
    return _block("error", entry=None, counts=None, sort=None, header=error_note(reason))


# ---------------------------------------------------------------------------
# 🌀 / 📍 / 🔑 filters (Ajay 2026-09-29): views over existing reads, gate nothing
# ---------------------------------------------------------------------------
FILTER_PARAM = "dm"
FILTER_KEYS = ("amd", "zone", "level")             # canonical order; FE DM_FILTER_KEYS pinned equal
FILTER_LABELS = {"amd": "\U0001F300 AMD raided",
                 "zone": "\U0001F4CD Near demand zone",
                 "level": "\U0001F511 Near a lower key level"}
AMD_RAIDED = TB.AMD_TURNING                         # the AMD Raided tab's own state — never the literal
# HIS CALL (spec §7 #1): no existing "near a key level" constant (PIERCE_PCT is the
# break buffer, AT_LEVEL_PCT the "at the level" band). A display cut-off, NOT a rule.
KEY_LEVEL_NEAR_PCT = 1.0
LEVEL_STATUSES = ("ranked", "broken", "no_level", "stale", "no_print")   # ⊂ KLT.COUNT_KEYS (test-pinned)
LEVEL_UNREAD = "unread"
FILTERS_NOTE = ("Ticked boxes narrow the leaders — every ticked box must pass. They sort "
                "nothing, push nothing, gate nothing and enter no lane.")
FILTER_EMPTY_FMT = (MARK + " No leader in ranks 1–{pool} passes every ticked box ({labels}) — "
                    "untick one to see more; the line above says how many each box hid.")
# HOW the ticked boxes combine (Ajay 2026-09-29, after 🌀 5 · 📍 12 · 🔑 2 showed
# 0 names together: "How can I see all of these? at the same time? is there a
# check box selection?"). ANY (the default) = a leader passing ANY ticked box
# shows, with a served badge for each ticked box it passes; ALL = the "must
# match all" switch, every ticked box must pass. `?dm_mode=all`; absent or
# unknown = any. Not-read never passes a box in either mode.
FILTER_MODE_PARAM = "dm_mode"
MODE_ANY = "any"
MODE_ALL = "all"
FILTER_MODES = (MODE_ANY, MODE_ALL)
FILTER_MODE_DEFAULT = MODE_ANY
MODE_ALL_LABEL = "must match all"
FILTERS_NOTE_ANY = ("Ticked boxes narrow the leaders — a leader passing ANY ticked box shows, "
                    "with a badge for each ticked box it passes; tick \u201cmust match all\u201d "
                    "to need every one. They sort nothing, push nothing, gate nothing and "
                    "enter no lane.")
FILTER_EMPTY_ANY_FMT = (MARK + " No leader in ranks 1–{pool} passes any ticked box ({labels}) — "
                        "tick another box to see more; the line above says how many each "
                        "box passed.")


def near_demand_pct() -> float:
    """The 🎯 gate's own proximity bound: the default `demand_proximity_gate`
    binds (the 🎯 read calls it without overriding it), read off its signature
    — the `_engine_min_rs` pattern — so this module never spells or retypes
    the alert constant."""
    return float(inspect.signature(AG.demand_proximity_gate)
                 .parameters["max_above_pct"].default)


def parse_filters(spec) -> tuple:
    """`"level,AMD, foo"` -> ("amd", "level"). Unknown tokens are dropped (never
    an error); None / non-str / blank -> (). Canonical FILTER_KEYS order."""
    if not isinstance(spec, str) or not spec.strip():
        return ()
    toks = {t.strip().lower() for t in spec.replace("+", ",").split(",")}
    return tuple(k for k in FILTER_KEYS if k in toks)


def amd_reads(syms, *, doc=None, now=None) -> tuple:
    """({SYM: cell}, summary) — ONE `hottest_amd.attach` over a one-roster
    body (the AMD Raided tab's stored sweep, rename-aware, 5-min cached).
    `attach` never raises: store down -> every cell blank("store_unavailable")."""
    from rotation import hottest_amd as HA
    rows = [{"symbol": s} for s in syms]
    summary = HA.attach({"themes": [{"names": rows}]}, doc=doc, now=now)
    return {r["symbol"]: r.get(HA.ROW_KEY) for r in rows}, (summary or {})


def _kl_pool_entry(syms, *, now, universe, build_fn):
    """The Key Levels tab's own `build` over the pool, MEMOISED (critic fix 2,
    2026-09-29): the per-box counts are served on every ready request, ticked
    or not, and the build is a closed-bar read that cannot change inside one
    (session, scan generation, pool). Key = (session ISO, `scan_generation()`,
    tuple(syms)); freshness = the Key Levels tab's own `KLT.MEMO_TTL_SEC`
    (cache freshness, NOT a rule). ONE newest entry. A raising build is never
    memoised (the caller turns it into LEVEL_UNREAD). The live-print `rank`
    is NOT memoised — it runs on every request against this request's
    snapshot."""
    from chart_maps import key_levels_tab as KLT
    session = KLT.session_for(now)
    key = (session.isoformat(), scan_generation(), tuple(syms), str(universe))
    with _lock:
        held_key, held, ts = _kl_memo.get("key"), _kl_memo.get("entry"), _kl_memo.get("ts")
    if (held is not None and held_key == key
            and (time.time() - float(ts or 0)) < KLT.MEMO_TTL_SEC):
        return held
    entry = (build_fn or KLT.build)(universe, session, universe_fn=lambda _u: list(syms))
    with _lock:
        _kl_memo.clear()
        _kl_memo.update(key=key, entry=entry, ts=time.time())
    return entry


def key_level_reads(syms, raw, *, now, first_seen, universe="full", build_fn=None) -> tuple:
    """({SYM: {"status", "near"}}, error-or-None) — the Key Levels tab's own
    `build` over the pool (memoised, `_kl_pool_entry`) + its own per-name
    `rank` outcome. Never mutates the entry; a failed build -> every name
    LEVEL_UNREAD and the reason."""
    from chart_maps import key_levels_tab as KLT
    syms = [str(s) for s in (syms or [])]
    try:
        entry = _kl_pool_entry(syms, now=now, universe=universe, build_fn=build_fn)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("dual momentum tab: key-level read failed: %s", exc)
        return {s: {"status": LEVEL_UNREAD, "near": None} for s in syms}, (str(exc)[:200] or "unknown")
    out = {}
    for s in syms:
        ranked, counts = KLT.rank({**entry, "syms": [s]}, raw, now=now, first_seen=first_seen or {})
        st = next((k for k in LEVEL_STATUSES if counts.get(k)), LEVEL_UNREAD)
        # a COPY: the entry is memoised, the tile's block must never alias it
        out[s] = {"status": st, "near": copy.deepcopy(ranked[0]["near"]) if ranked else None}
    return out, None


def tile_filter(amd_cell, zone, level_read) -> dict:
    """One leader's three reads — PURE. True passes, False fails, None = not
    read (a ticked box hides a None; it never passes)."""
    cell = amd_cell if isinstance(amd_cell, dict) else None
    if cell is not None and cell.get("known") is True:
        amd = cell.get("grade") == AMD_RAIDED
        amd_grade, amd_reason = cell.get("grade"), None
    else:
        amd, amd_grade = None, None
        amd_reason = cell.get("reason") if cell is not None else None
    gate = (zone or {}).get("gate") if isinstance(zone, dict) else None
    prox = gate.get("prox_ok") if isinstance(gate, dict) else None
    if isinstance(zone, dict) and zone.get("reason") == "no_band":
        # A stored doc was read against a real print and no demand band sits
        # under it: that IS the read, and it is not near demand — a plain
        # FAIL, never "not read" (critic fix 3, 2026-09-29).
        zone_ok = False
    else:
        zone_ok = prox if isinstance(prox, bool) else None
    lr = level_read if isinstance(level_read, dict) else {}
    status = lr.get("status") if lr.get("status") in LEVEL_STATUSES else LEVEL_UNREAD
    near = lr.get("near") if isinstance(lr.get("near"), dict) else None
    level = None
    if status == "ranked":
        d = _f((near or {}).get("distance_pct"))
        level = None if d is None else abs(d) <= KEY_LEVEL_NEAR_PCT
    elif status in ("broken", "no_level"):
        level = False
    return {"amd": amd, "amd_grade": amd_grade, "amd_reason": amd_reason,
            "zone": zone_ok, "level": level, "level_status": status,
            "level_near": near if status == "ranked" else None}


def parse_mode(v) -> str:
    """`?dm_mode=` -> MODE_ALL only for "all" (any case / spacing); absent,
    blank, junk or a non-str -> MODE_ANY (the default)."""
    return MODE_ALL if isinstance(v, str) and v.strip().lower() == MODE_ALL else MODE_ANY


def passes(tf, active, mode=FILTER_MODE_DEFAULT) -> bool:
    """ANY (default): at least one ticked box is True. ALL: every ticked box is
    True. None (not read) never passes a box; no ticked box -> True."""
    tf = tf if isinstance(tf, dict) else {}
    act = tuple(active or ())
    if not act:
        return True
    hits = [tf.get(k) is True for k in act]
    return all(hits) if parse_mode(mode) == MODE_ALL else any(hits)


def filter_badges(tf, active) -> list:
    """The served badge for EACH TICKED box this leader passes (True only —
    never a fail, never a not-read), in FILTER_KEYS order; [] with nothing
    ticked. Text = the box's own label, so the card reads which box let the
    leader in. Built from the tile's `dm_filter` read — the page computes none."""
    tf = tf if isinstance(tf, dict) else {}
    act = set(active or ())
    return [{"text": FILTER_LABELS[k], "tone": "good", "dm_filter": k}
            for k in FILTER_KEYS if k in act and tf.get(k) is True]


def _measured_clause() -> str:
    from rotation import hottest_amd as HA
    M = HA.AMD_MEASURED
    return f"MEASURED INVERTED on its own claim ({M['date']}): {M['claim']} — a narrowing, not a pick."


def amd_note(summary) -> str:
    s = summary if isinstance(summary, dict) else {}
    if not s.get("available"):
        return ("\U0001F300 The nightly AMD sweep could not be read, so no leader has an AMD "
                "state right now — ticked, this box passes no leader. " + _measured_clause())
    stamp = str(s.get("built_at_et") or "")[:16].replace("T", " ") or "time unknown"
    txt = (f"\U0001F300 The AMD Raided tab's own state, from the nightly sweep ({stamp} ET). "
           + _measured_clause())
    if s.get("stale") and s.get("stale_note"):
        txt += " " + str(s["stale_note"])
    return txt


def zone_note() -> str:
    return (f"\U0001F4CD In the demand band or at most {near_demand_pct():g}% above its top — "
            "the \U0001F3AF gate's own proximity read, the same number the phone alerts use. "
            "UNMEASURED on these leaders.")


def level_note(error=None) -> str:
    from chart_maps import key_levels_tab as KLT
    txt = (f"\U0001F511 The Key Levels tab's nearest {KLT.LOWS} not yet broken, at most "
           f"{KEY_LEVEL_NEAR_PCT:g}% from the print — a display cut-off awaiting your call. "
           "UNMEASURED.")
    if error:
        txt += (f" The key-level read failed this time ({error}); ticked, this box passes "
                "no leader.")
    return txt


def filter_line(items, passed_all, pool, *, mode=MODE_ALL, shown=None) -> Optional[str]:
    """The served line for the ticked boxes. ALL: each box's pass / hidden
    (what that box hid) and how many pass every box. ANY: each box's pass
    count, then how many pass at least one and how many are hidden (they pass
    none — a not-read counts as not passing)."""
    on = [i for i in (items or []) if isinstance(i, dict) and i.get("on")]
    if not on:
        return None
    if parse_mode(mode) == MODE_ANY:
        bits = []
        for i in on:
            b = f"{i['label']}: {_n(i.get('pass'))} pass"
            if int(i.get("no_read") or 0) > 0:
                b += f" ({_n(i.get('no_read'))} not read)"
            bits.append(b)
        n_shown = int(shown or 0)
        n_pool = int(pool or 0)
        return (f"Filters on (any ticked box) — {'; '.join(bits)}. {_n(n_shown)} of {_n(n_pool)} "
                f"pass at least one ticked box, {_n(max(n_pool - n_shown, 0))} hidden (they pass "
                "none of them; a leader passing several shows once, with a badge for each).")
    bits = []
    for i in on:
        b = f"{i['label']}: {_n(i.get('pass'))} pass, {_n(i.get('hidden'))} hidden"
        if int(i.get("no_read") or 0) > 0:
            b += f" ({_n(i.get('no_read'))} not read)"
        bits.append(b)
    return (f"Filters on ({MODE_ALL_LABEL}) — {'; '.join(bits)}. {_n(passed_all)} of {_n(pool)} "
            f"pass every ticked box (each count is over all {_n(pool)} ranked leaders; a name "
            "can fail more than one).")


def filter_empty_note(active, pool, mode=FILTER_MODE_DEFAULT) -> str:
    labs = [FILTER_LABELS[k] for k in active if k in FILTER_LABELS]
    if parse_mode(mode) == MODE_ALL:
        return FILTER_EMPTY_FMT.format(pool=_n(pool), labels=" + ".join(labs))
    return FILTER_EMPTY_ANY_FMT.format(pool=_n(pool), labels=" or ".join(labs))


def filters_block(tfs, active, *, pool, amd_summary, level_error,
                  mode=FILTER_MODE_DEFAULT) -> dict:
    """Per-box counts over EVERY pool tile, each box independently (computed
    whether or not it is ticked), plus the served line when any is ticked.

    `mode` (ANY default / ALL) decides `shown` = how many leaders the ticked
    boxes let through (`passed_any` / `passed_all`) and `hidden` = pool - shown
    (in ANY: the leaders passing NONE of the ticked boxes). An item's own
    `hidden` stays what that box ON ITS OWN hides (fail + not read) — the ALL
    line's per-box number; the ANY line prints only each box's pass count."""
    tfs = [t if isinstance(t, dict) else {} for t in (tfs or [])]
    act = tuple(k for k in FILTER_KEYS if k in (active or ()))
    md = parse_mode(mode)
    notes = {"amd": amd_note(amd_summary), "zone": zone_note(),
             "level": level_note(level_error)}
    items = []
    for k in FILTER_KEYS:
        vals = [t.get(k) for t in tfs]
        n_pass = sum(1 for v in vals if v is True)
        n_fail = sum(1 for v in vals if v is False)
        n_none = len(vals) - n_pass - n_fail
        on = k in act
        items.append({"key": k, "label": FILTER_LABELS[k], "on": on, "pass": n_pass,
                      "fail": n_fail, "no_read": n_none,
                      "hidden": (n_fail + n_none) if on else 0, "note": notes[k]})
    passed_all = sum(1 for t in tfs if passes(t, act, MODE_ALL)) if act else None
    passed_any = sum(1 for t in tfs if passes(t, act, MODE_ANY)) if act else None
    shown = (passed_all if md == MODE_ALL else passed_any) if act else None
    return {"keys": list(FILTER_KEYS), "active": list(act), "pool": int(pool or 0),
            "mode": md, "mode_param": FILTER_MODE_PARAM, "mode_all_label": MODE_ALL_LABEL,
            "passed_all": passed_all, "passed_any": passed_any, "shown": shown,
            "hidden": (len(tfs) - shown) if act else 0, "items": items,
            "line": filter_line(items, passed_all, pool, mode=md, shown=shown) if act else None,
            "note": (FILTERS_NOTE if md == MODE_ALL else FILTERS_NOTE_ANY),
            "near_demand_pct": near_demand_pct(),
            "near_level_pct": KEY_LEVEL_NEAR_PCT, "measured": False}
