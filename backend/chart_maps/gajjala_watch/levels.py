"""📐 Daily supply & demand zones on the 👀 Gajjala's Watch charts (2026-11-23, spec vwapzones §3.6, WP be-zones).

Ajay 2026-11-23, verbatim: "can you add vwap and supply demand zone in the daily time frame on the watch list please"
and "Add vwap and supply demand too".

ONE engine: `supply_demand.zone_store.build_doc` (= `price_zones.compute(f, max_zones=None, **demand_reentry.zone_geom())`,
the BOARD geometry every S&D board, alert and lane reads) on CLOSED daily bars, read FRESH through
`sepa.prices.closed_daily_frame(sym, now=…, period=C.ZONES_PERIOD, use_cache=False)` [C5] — a cached frame can hold an
unfinished intraday bar or a pre-split history. Nothing here computes a zone.

Storage: the name's Watch tile doc (`gajjala_watch_tiles`), key `levels` — ONE update_one per name read, never an
upsert, never another collection (the S&D store is read by the alert paths; the Watch never writes it):
  {"session", "state": "ok", "bands": [every band of build_doc], "prev_close", "through", "n_bars", "geom", "at"}
  {"session", "state": "none", "why": "short" | "none" | "error", "n_bars", "at"}        — LATCHED for the session
  {"session", "state": "retry", "why": "no_daily", "tries", "at"}                        — NOT latched [C5]
`warm` runs OFF the minute path (the loop child's daemon thread / the add-time build child), serially, at most
`C.ZONES_MAX_NEW` non-first reads per call. The card frames GET (`for_card`) never waits on a provider: a single-flight
queue + a per-process memo.

Served (`block`): the engine's own cut — `price_zones.nearest_first`, N per kind (`C.ZONES_PER_SIDE`, else
`price_zones.MAX_ZONES_PER_SIDE` by name) — as `ctx` bands of the two BOARD kinds (`C.ZONE_BAND_KIND`, a dashed outline),
EXACTLY six keys each; a `lo == hi` band (cent rounding under $1) is KEPT and printed as ONE price [C3]. One served
line names the zone the price is in / the next below / the next above. A high or low of the last
`zone_geom()["swing_window"]` closed sessions is never a zone — the words say so [C4].
Display only: nothing gates, sorts or rings on it. UNMEASURED.
"""
from __future__ import annotations

import logging
import math
import queue
import threading
from datetime import date, datetime, time, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import tab as GT
from supply_demand import price_zones as PZ
from supply_demand import zone_store as ZS
from supply_demand.demand_reentry import zone_geom

from . import colls as CO
from . import constants as C

log = logging.getLogger("chart_maps.gajjala_watch.levels")
_ET = ZoneInfo("America/New_York")

BAND_KEYS = ("kind", "lo", "hi", "label", "gutter", "ctx")             # the served band — EXACTLY these (never pad_lo)
BLOCK_KEYS = ("state", "as_of", "text", "title", "bands")
ROW_KEYS = ("state", "text", "title", "as_of")                          # the row's / card payload's `levels`

# ── words (every number a `{}` field filled from a constant BY NAME at format time) ────────────────────────────────
ZONE_KIND_WORDS = {"demand": "demand", "supply": "supply"}              # also the band's `gutter`
ZONE_LABEL_TEXT = "Daily {kind} {band}"
LEVELS_TEXT = "📐 Daily zones (bars through {through}): {parts}"
LEVELS_IN_TEXT = "inside {kind} {band}"
LEVELS_BELOW_TEXT = "next below {kind} {band} ({pct}% under)"
LEVELS_ABOVE_TEXT = "next above {kind} {band} ({pct}% over)"
LEVELS_NONE_BELOW, LEVELS_NONE_ABOVE = "none below", "none above"
LEVELS_PARTS_SEP = " · "
LEVELS_PENDING_TEXT = {True: "📐 Daily zones: not read yet — {cap} names are read every {min} minutes, {sym} is in line",
                       False: "📐 Daily zones: not read yet — read at the next session's first read ({open} ET)"}
LEVELS_WAITING_TEXT = "📐 Daily zones: read for today — they show at {sym}'s first print today"
LEVELS_CARD_PENDING_TEXT = "📐 Daily zones: reading now — they show at the next refresh"
LEVELS_RETRY_TEXT = ("📐 Daily zones: the daily read returned nothing for {sym} (tried {n}×, last {at} ET) — tried "
                     "again at the next read")
LEVELS_SHORT_TEXT = "📐 Daily zones: {n} daily bars for {sym}, the zone engine needs {min} — none drawn"
LEVELS_EMPTY_TEXT = "📐 Daily zones: the engine found none for {sym}"
LEVELS_ERROR_TEXT = "📐 Daily zones: the engine could not read {sym}'s daily bars — none drawn"
RULES_TEXT = ("📐 Daily zones on {label}: the Supply & Demand engine's daily supply and demand zones (closed daily bars, "
              "the board's geometry), the {n} nearest of each kind, drawn dashed where they cross the chart's price "
              "range; a zone never moves the price scale. A high or low made in the last {w} closed sessions is not a "
              "zone yet — the engine needs {w} later sessions to call it a swing, so yesterday's high is usually not "
              "drawn. A name with fewer than {min} daily bars gets none. Display only: nothing gates, sorts or rings on "
              "it. UNMEASURED.")
LEGEND = (("zone_demand", "Daily demand zone (dashed)"), ("zone_supply", "Daily supply zone (dashed)"))
NO_DASH = "—"

WHY_SHORT, WHY_NONE, WHY_ERROR, WHY_NO_DAILY = "short", "none", "error", "no_daily"
FIND_FIELDS = {"levels.session": 1, "levels.state": 1, "levels.tries": 1}


# ── small helpers ──────────────────────────────────────────────────────────────────────────────────────────────────
def _fin(x) -> Optional[float]:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    v = float(x)
    return v if math.isfinite(v) else None


def _day(session) -> date:
    if isinstance(session, datetime):
        return session.date()
    if isinstance(session, date):
        return session
    return date.fromisoformat(str(session)[:10])


def _iso(session) -> str:
    return _day(session).isoformat()


def _utc(now) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _loader_now(session) -> datetime:
    """The daily loader's `now`: the session date at 00:00, naive = ET → bars dated BEFORE the session only."""
    return datetime.combine(_day(session), time())


def _hhmm_et(at) -> str:
    t = CO.stamp_utc(at)
    return t.astimezone(_ET).strftime("%H:%M") if t is not None else NO_DASH


def _band_words(lo: float, hi: float) -> str:
    """ONE price when lo and hi print the same through the house formatter (`tab._px`), else "lo–hi" [C3]."""
    a, b = GT._px(lo), GT._px(hi)
    return a if a == b else f"{a}–{b}"


def _pct(v: float) -> str:
    """An unsigned % distance through the Watch's ONE % formatter (`runners.pct_show`, floored to PCT_SHOW_PLACES)."""
    from chart_maps.gajjala_watch import runners as RN               # lazy: runners imports replays lazily
    s = RN.pct_show(abs(v))
    return s.lstrip("+-").rstrip("%") if s else NO_DASH


def _per_side() -> int:
    n = C.ZONES_PER_SIDE
    return PZ.MAX_ZONES_PER_SIDE if n is None else int(n)


def _valid(bands) -> list:
    """Bands of a ZONE_KINDS kind with finite lo ≤ hi (as floats); junk / NaN / lo > hi dropped; lo == hi KEPT [C3]."""
    out = []
    for b in bands if isinstance(bands, list) else []:
        if not isinstance(b, dict) or b.get("kind") not in C.ZONE_KINDS:
            continue
        lo, hi = _fin(b.get("lo")), _fin(b.get("hi"))
        if lo is None or hi is None or lo > hi:
            continue
        out.append(dict(b, lo=lo, hi=hi))
    return out


# ── the daily read → the stored doc ────────────────────────────────────────────────────────────────────────────────
def default_loader(sym, *, now):
    """[C5] A FRESH closed-daily read: `closed_daily_frame(..., period=C.ZONES_PERIOD, use_cache=False)` — bars before
    `now`'s ET date, no cache read, no cache write, never raises (None on no bars AND on a provider failure)."""
    from sepa import prices
    return prices.closed_daily_frame(sym, now=now, period=C.ZONES_PERIOD, use_cache=False)


def _through(frame) -> Optional[str]:
    try:
        import pandas as pd
        idx = pd.DatetimeIndex(frame.index)
        if idx.tz is not None:
            idx = idx.tz_convert("America/New_York").tz_localize(None)
        return idx.max().date().isoformat()
    except Exception:                                          # noqa: BLE001
        return None


def levels_doc(sym, daily_df, session, now, *, tries: int = 0) -> dict:
    """The stored `levels` doc for one daily read. None / empty → `retry` (tries + 1, NOT latched). Else the engine:
    ≥ 1 band → `ok`; zero bands → `none / none`; build_doc None under `zone_store.MIN_BARS` → `none / short`; None
    otherwise → `none / error`."""
    day, at = _day(session), _utc(now)
    iso = day.isoformat()
    if daily_df is None or len(daily_df) == 0:
        return {"session": iso, "state": "retry", "why": WHY_NO_DAILY, "tries": int(tries or 0) + 1, "at": at}
    try:
        closed = ZS.drop_today(daily_df, day)
        n_bars = int(len(closed)) if closed is not None else 0
        doc = ZS.build_doc(sym, daily_df, day, now=at)
    except Exception as exc:                                   # noqa: BLE001 — the engine faulted on this frame
        log.warning("gajjala watch levels: %s engine fault: %s", sym, type(exc).__name__)
        return {"session": iso, "state": "none", "why": WHY_ERROR, "n_bars": 0, "at": at}
    if doc is None:
        why = WHY_SHORT if n_bars < ZS.MIN_BARS else WHY_ERROR
        return {"session": iso, "state": "none", "why": why, "n_bars": n_bars, "at": at}
    bands = list(doc.get("bands") or [])
    if not bands:
        return {"session": iso, "state": "none", "why": WHY_NONE, "n_bars": n_bars, "at": at}
    return {"session": iso, "state": "ok", "bands": bands, "prev_close": _fin(doc.get("prev_close")),
            "through": _through(closed), "n_bars": n_bars, "geom": ZS.GEOM_TAG, "at": at}


# ── the engine's own cut ───────────────────────────────────────────────────────────────────────────────────────────
def near(bands, price, n=None) -> list:
    """Per kind in C.ZONE_KINDS: `price_zones.nearest_first(kind bands, price)[:n]` (the engine's surfacing rule —
    the band price stands in first); n None → C.ZONES_PER_SIDE, else price_zones.MAX_ZONES_PER_SIDE. Sorted high → low."""
    k = _per_side() if n is None else int(n)
    out: list = []
    for kind in C.ZONE_KINDS:
        out += PZ.nearest_first([b for b in bands if b.get("kind") == kind], price)[:k]
    return sorted(out, key=lambda b: (-b["hi"], -b["lo"]))


# ── warm: the daily reads, off the minute path ─────────────────────────────────────────────────────────────────────
def _listed(cs, db, iso: str) -> list:
    """The owner list + the 🤖 auto names + (2026-11-24) the ✅ all-rules names of the session (fold-de-duplicated, his
    first, ✅ last) — the loop's own listing."""
    names = [s for s in CO.owner_symbols(db) if s]
    keys = {CO.fold(s) for s in names}
    try:
        from chart_maps.gajjala_watch import auto as AUTO           # lazy: a heavy import graph
        for s in AUTO.current_symbols(cs, iso):
            if CO.fold(s) not in keys:
                keys.add(CO.fold(s))
                names.append(s)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("gajjala watch levels: auto names unreadable: %s", type(exc).__name__)
    try:                                                       # ✅ 2026-11-24 (spec watchall §3.4) — the all-rules names, LAST
        from chart_maps.gajjala_watch import allrules as RULES      # lazy, like the auto engine
        for s in RULES.current_symbols(cs, iso):
            if CO.fold(s) not in keys:
                keys.add(CO.fold(s))
                names.append(s)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("gajjala watch levels: all-rules names unreadable: %s", type(exc).__name__)
    return names


def _lv(doc) -> dict:
    v = doc.get("levels") if isinstance(doc, dict) else None
    return v if isinstance(v, dict) else {}


def _tries(lv: dict) -> int:
    t = lv.get("tries")
    return t if isinstance(t, int) and not isinstance(t, bool) else 0


def warm(now=None, *, db=None, loader: Optional[Callable] = None, first=None, rest: bool = True, cap=None) -> dict:
    """Read and store the daily zones of the session. Order: (1) every `first` name with a tile doc — uncapped, each
    once; (2) when `rest`: listed names with a tile doc whose `levels.session` is not the session, list order; (3) then
    this session's `retry` docs, fewest tries first. (2) + (3) are cut to `cap` (None → C.ZONES_MAX_NEW). SERIAL reads;
    per name ONE update_one of `levels` on its existing tile doc. No store → no loader call."""
    if not C.ZONES_ON:
        return {"reason": "off", "read": []}
    cs = CO.colls(db)
    tiles = cs.get("tiles") if isinstance(cs, dict) else None
    if tiles is None:
        return {"reason": "no_store", "read": []}
    et = GT._et(now)
    session = GT.session_for(et)[0]
    iso = session.isoformat()
    loader = loader or default_loader
    firsts = list(dict.fromkeys(s for s in (first or []) if isinstance(s, str) and s))
    listed = _listed(cs, db, iso) if rest else []
    ids = list(dict.fromkeys(firsts + listed))
    try:
        docs = {d.get("_id"): d for d in tiles.find({"_id": {"$in": ids}}, FIND_FIELDS) if isinstance(d, dict)} \
            if ids else {}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("gajjala watch levels: tile read failed: %s", type(exc).__name__)
        return {"session": iso, "reason": "tile_read_failed", "read": []}
    order = [s for s in firsts if s in docs]
    if rest:
        fs = set(firsts)
        new = [s for s in listed if s in docs and s not in fs and _lv(docs[s]).get("session") != iso]
        again = [s for s in listed if s in docs and s not in fs and _lv(docs[s]).get("session") == iso
                 and _lv(docs[s]).get("state") == "retry"]
        again.sort(key=lambda s: _tries(_lv(docs[s])))           # stable: list order within a tries count
        k = C.ZONES_MAX_NEW if cap is None else cap
        order += (new + again)[:max(0, int(k))]
    out = {"session": iso, "read": [], "ok": 0, "none": 0, "retry": 0}
    day0 = _loader_now(session)
    for sym in order:
        lv = _lv(docs[sym])
        tries = _tries(lv) if lv.get("session") == iso and lv.get("state") == "retry" else 0
        try:
            df = loader(sym, now=day0)
        except Exception as exc:                               # noqa: BLE001 — a raising loader = nothing returned
            log.debug("gajjala watch levels: %s daily read raised: %s", sym, type(exc).__name__)
            df = None
        doc = levels_doc(sym, df, session, et, tries=tries)
        out["read"].append(sym)
        out[doc["state"]] = out.get(doc["state"], 0) + 1
        try:
            tiles.update_one({"_id": sym}, {"$set": {"levels": doc}})
        except Exception as exc:                               # noqa: BLE001
            log.warning("gajjala watch levels: %s write failed: %s", sym, type(exc).__name__)
    return out


def _warm_quiet(now) -> None:
    try:
        warm(now)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("gajjala watch levels: warm failed: %s", type(exc).__name__)


def spawn(now=None) -> Optional[threading.Thread]:
    """A daemon thread running `warm(now)` (it dies with the loop child; a read cut mid-flight writes nothing). Never
    raises: a fault → None + one log line."""
    try:
        t = threading.Thread(target=_warm_quiet, args=(now,), name="gajjala-watch-levels", daemon=True)
        t.start()
        return t
    except Exception as exc:                                   # noqa: BLE001
        log.warning("gajjala watch levels: spawn failed: %s", type(exc).__name__)
        return None


# ── served ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _served_band(b: dict) -> dict:
    kind = b["kind"]
    return {"kind": C.ZONE_BAND_KIND[kind], "lo": b["lo"], "hi": b["hi"],
            "label": ZONE_LABEL_TEXT.format(kind=ZONE_KIND_WORDS[kind], band=_band_words(b["lo"], b["hi"])),
            "gutter": ZONE_KIND_WORDS[kind], "ctx": True}


def _parts(valid: list, price: float) -> list:
    """The engine's own reading (price_zones: inside = lo ≤ P ≤ hi, below = hi < P, above = lo > P) over EVERY band."""
    inside = sorted((b for b in valid if b["lo"] <= price <= b["hi"]), key=lambda b: (-b["hi"], -b["lo"]))
    parts = [LEVELS_IN_TEXT.format(kind=ZONE_KIND_WORDS[b["kind"]], band=_band_words(b["lo"], b["hi"])) for b in inside]
    below = [b for b in valid if b["hi"] < price]
    above = [b for b in valid if b["lo"] > price]
    if below:
        b = max(below, key=lambda z: z["hi"])
        parts.append(LEVELS_BELOW_TEXT.format(kind=ZONE_KIND_WORDS[b["kind"]], band=_band_words(b["lo"], b["hi"]),
                                              pct=_pct((price - b["hi"]) / price * 100.0)))
    else:
        parts.append(LEVELS_NONE_BELOW)
    if above:
        b = min(above, key=lambda z: z["lo"])
        parts.append(LEVELS_ABOVE_TEXT.format(kind=ZONE_KIND_WORDS[b["kind"]], band=_band_words(b["lo"], b["hi"]),
                                              pct=_pct((b["lo"] - price) / price * 100.0)))
    else:
        parts.append(LEVELS_NONE_ABOVE)
    return parts


def _pending(sym: str, in_window: bool) -> dict:
    text = LEVELS_PENDING_TEXT[bool(in_window)].format(cap=C.ZONES_MAX_NEW, min=GC.PASS_CADENCE_SEC // 60, sym=sym,
                                                       open=GC.PASS_OPEN_ET)
    return {"state": "pending", "as_of": None, "text": text, "title": rules_line(), "bands": []}


def block(levels, tile_session, price, sym, *, in_window, now) -> dict:
    """One row's served block (pure). No `levels`, or `levels.session` ≠ `tile_session` → `pending`. P = `price`, else
    the stored `prev_close`."""
    lv = levels if isinstance(levels, dict) else None
    ts = _iso(tile_session) if tile_session is not None else None
    if lv is not None and ts is not None and isinstance(lv.get("session"), str) and lv.get("session") > ts \
            and lv.get("state") in ("ok", "none"):
        return {"state": "pending", "as_of": None, "text": LEVELS_WAITING_TEXT.format(sym=sym),
                "title": rules_line(), "bands": []}
    if lv is None or ts is None or lv.get("session") != ts:
        return _pending(sym, in_window)
    state = lv.get("state")
    title = rules_line()
    if state == "retry":
        n = _tries(lv)
        return {"state": "retry", "as_of": None, "title": title, "bands": [],
                "text": LEVELS_RETRY_TEXT.format(sym=sym, n=n, at=_hhmm_et(lv.get("at")))}
    if state == "none":
        why = lv.get("why")
        if why == WHY_SHORT:
            n_bars = lv.get("n_bars") if isinstance(lv.get("n_bars"), int) else 0
            text = LEVELS_SHORT_TEXT.format(n=n_bars, sym=sym, min=ZS.MIN_BARS)
        elif why == WHY_NONE:
            text = LEVELS_EMPTY_TEXT.format(sym=sym)
        else:
            text = LEVELS_ERROR_TEXT.format(sym=sym)
        return {"state": "none", "as_of": None, "text": text, "title": title, "bands": []}
    if state != "ok":
        return _pending(sym, in_window)
    P = _fin(price)
    if P is None or P <= 0:
        P = _fin(lv.get("prev_close"))
    valid = _valid(lv.get("bands"))
    through = lv.get("through") if isinstance(lv.get("through"), str) else None
    if P is None or P <= 0:
        return {"state": "ok", "as_of": through, "text": None, "title": title, "bands": []}
    bands = [_served_band(b) for b in near(valid, P)]
    text = LEVELS_TEXT.format(through=through or NO_DASH, parts=LEVELS_PARTS_SEP.join(_parts(valid, P)))
    return {"state": "ok", "as_of": through, "text": text, "title": title, "bands": bands}


def row_levels(blk) -> Optional[dict]:
    """The row's / card payload's `levels` = {state, text, title, as_of} of a block; None without one."""
    if not isinstance(blk, dict):
        return None
    return {k: blk.get(k) for k in ROW_KEYS}


def _last_close(tile: dict) -> Optional[float]:
    frames = tile.get("frames") if isinstance(tile.get("frames"), dict) else {}
    order = [C.AXIS_FRAME] + [tf for tf in frames if tf != C.AXIS_FRAME]
    for tf in order:
        f = frames.get(tf) if isinstance(frames.get(tf), dict) else {}
        bars = f.get("bars")
        if isinstance(bars, list) and bars and isinstance(bars[-1], dict):
            v = _fin(bars[-1].get("c"))
            if v is not None:
                return v
    return None


def blocks(names, tiles: dict, siso: str, now, in_window) -> dict:
    """STRICT core: {SYM: block} for every name. P = the last close of the stored C.AXIS_FRAME bars (else any stored
    frame's last close). `C.ZONES_ON` False → {}."""
    if not C.ZONES_ON:
        return {}
    out = {}
    tiles = tiles if isinstance(tiles, dict) else {}
    for sym in names or []:
        t = tiles.get(sym) if isinstance(tiles.get(sym), dict) else {}
        out[sym] = block(t.get("levels"), t.get("session"), _last_close(t), sym, in_window=bool(in_window), now=now)
    return out


def section(names, tiles: dict, siso: str, now, in_window) -> dict:
    """Fail-soft `blocks`: any fault → {} + ONE log line (the board still answers)."""
    try:
        return blocks(names, tiles, siso, now, in_window)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("gajjala watch levels: section failed: %s", type(exc).__name__)
        return {}


# ── the card frames GET: never waits on a provider (single-flight queue + memo) ───────────────────────────────────
_LOCK = threading.Lock()
_MEMO: dict = {}                     # (session iso, SYM) → {"doc": levels doc, "slot": the 5-minute slot it was read in}
_INFLIGHT: set = set()
_STATE = {"session": None, "worker": None}
_Q: "queue.Queue" = queue.Queue()


def _slot(now) -> str:
    from chart_maps.gajjala import run_1m as R1                     # lazy: the existing 5-minute grid
    return R1.slot_of(now)[0].isoformat()


def _reset_card_state() -> None:
    """Tests: forget the memo and the in-flight keys (the worker thread, if any, stays)."""
    with _LOCK:
        _MEMO.clear()
        _INFLIGHT.clear()
        _STATE["session"] = None


def _job(key, sym, session, now, loader, tries) -> Callable:
    def run_job():
        try:
            try:
                df = loader(sym, now=_loader_now(session))
            except Exception as exc:                           # noqa: BLE001 — a raising loader = nothing returned
                log.debug("gajjala watch levels: card read %s raised: %s", sym, type(exc).__name__)
                df = None
            doc = levels_doc(sym, df, session, now, tries=tries)
            with _LOCK:
                if _STATE["session"] == key[0]:
                    _MEMO[key] = {"doc": doc, "slot": _slot(now)}
        except Exception as exc:                               # noqa: BLE001
            log.warning("gajjala watch levels: card job %s failed: %s", sym, type(exc).__name__)
        finally:
            with _LOCK:
                _INFLIGHT.discard(key)
    return run_job


def _worker_loop() -> None:
    while True:
        job = _Q.get()
        try:
            job()
        except Exception as exc:                               # noqa: BLE001 — the worker never dies on a job
            log.warning("gajjala watch levels: worker job failed: %s", type(exc).__name__)


def _ensure_worker() -> None:
    w = _STATE["worker"]
    if w is not None and w.is_alive():
        return
    w = threading.Thread(target=_worker_loop, name="gajjala-watch-levels-card", daemon=True)
    w.start()
    _STATE["worker"] = w


def for_card(sym, session, now, *, price, levels=None, tile_session=None, loader=None, run=None) -> Optional[dict]:
    """The card frames GET's block — NEVER waits on a provider. (1) The Watch tile's stored `levels` of THIS session in
    state ok / none → `block`. (2) With a `loader`: the process memo — ok / none kept for the session, `retry` only for
    the 5-minute slot it was read in. (3) A miss with a `loader` → the key queued ONCE (one daemon worker, serial; `run`
    = tests' inline runner) and the `pending` block with LEVELS_CARD_PENDING_TEXT returned NOW. A miss with no
    `loader` → None (nothing queued, nothing served; a stores tuple without a daily loader never reads daily bars)."""
    if not C.ZONES_ON:
        return None
    iso = _iso(session)
    lv = levels if isinstance(levels, dict) else None
    if (lv is not None and lv.get("session") == iso and lv.get("state") in ("ok", "none")
            and (tile_session is None or _iso(tile_session) == iso)):
        return block(lv, iso, price, sym, in_window=True, now=now)
    if loader is None:
        return None
    key = (iso, sym)
    slot = _slot(now)
    with _LOCK:
        if _STATE["session"] != iso:
            _MEMO.clear()
            _INFLIGHT.clear()
            _STATE["session"] = iso
        hit = _MEMO.get(key)
        tries = 0
        if hit is not None:
            doc = hit["doc"]
            if doc.get("state") in ("ok", "none") or hit.get("slot") == slot:
                return block(doc, iso, price, sym, in_window=True, now=now)
            tries = _tries(doc)
        queue_it = key not in _INFLIGHT
        if queue_it:
            _INFLIGHT.add(key)
    if queue_it:
        job = _job(key, sym, iso, now, loader, tries)
        if run is not None:
            run(job)
        else:
            _ensure_worker()
            _Q.put(job)
    return {"state": "pending", "as_of": None, "text": LEVELS_CARD_PENDING_TEXT, "title": rules_line(), "bands": []}


# ── words for the legend / ℹ️ / the rules panel ────────────────────────────────────────────────────────────────────
def legend() -> list:
    """The two zone legend entries {tone, label, title}; [] when C.ZONES_ON is False."""
    if not C.ZONES_ON:
        return []
    title = rules_line()
    return [{"tone": tone, "label": label, "title": title} for tone, label in LEGEND]


def rules_line() -> str:
    """The ONE sentence (legend hover = ℹ️ = the rules panel). "" when C.ZONES_ON is False. Types no number."""
    if not C.ZONES_ON:
        return ""
    return RULES_TEXT.format(label=C.TAB_LABEL, n=_per_side(), w=zone_geom()["swing_window"], min=ZS.MIN_BARS)
