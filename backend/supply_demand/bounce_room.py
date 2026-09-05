"""Bounce + room — is a name bouncing off a demand level, and how much room
does it have before the next supply band? One read, three surfaces.

Ajay 2026-09-05 (verbatim): "Can you help add a new filter to SEPA and In
demand and also catalyst ... The Filter need to check. #1 for Sepa stocks
that is bouncing off of Demand zone. #2 for in demand Make sure you sort
stocks by bouncing off of demand zone and have big gap in to supply. #3 for
catalyst same deal make sure you sort stocks by bigger gaps in to supply
like EOSE stock and CLYM as an example they have bigger gap and room to
grow."

Why one module
--------------
Three pages (SEPA scanner filter, Back-in-Demand sort, Catalysts sort) ask
the same two questions of the same bands. If each page computed its own
version, "bouncing" would mean three things within a week. So: pure reads
here, ONE route (POST /supply-demand/bounce-room), and an ordering key the
frontend mirrors 1:1 (docs/supply_demand/bounce_room.md).

The bands are the zone_store's (board geometry, every band, both kinds,
drawn BEFORE the store day) — the same bands the phone's zone_bounce_alert
and zone_edge passes read. Nothing here draws a new band.

The two reads (pure)
--------------------
BOUNCE  ``touch_hits`` + ``bounce_read``
  eligible  demand bands, plus supply bands with hi < prev_close (broken
            supply = support) — zone_bounce_alerts.is_eligible, imported.
  TOUCH     a session LOW with  low <= hi*(1+TOUCH_TOL_PCT%)  AND
            low >= lo*(1-WICK_PCT%)  — the alert's constants, imported.
  sessions  the doc's `recent` closed sessions (sessions_ago 1..
            LOOKBACK_SESSIONS; recent[-1] is the bar BEFORE the store day,
            drop_today) plus the snapshot's day bar as sessions_ago 0 ONLY
            when it IS the store day's own session — decided by DATA, not
            by the snapshot's date: sepa.prices.bulk_snapshot dates a bar
            TODAY when Massive omits day.t, so Saturday's snapshot of
            Friday's bar is dated Saturday. is_store_session_bar:
            (a) a bar whose low / high / close equal recent[-1]'s IS that
                closed bar and is never counted again (weekday holiday:
                the 9:20 warm keeps Friday in `recent` and the snapshot
                still shows Friday's OHLC);
            (b) otherwise it is the store-day session when its date == the
                store day, or when its date is LATER and its prevDay close
                == the doc's prev_close (the bar before the store day).
            A Monday snapshot over a Friday store (warm failed) matches
            neither -> Monday's low is NOT seen; never a false read.
  BOUNCE    print > band.hi  AND  print >= touch_low*(1 + max(BOUNCE_MIN_PCT,
            100*atr14/touch_low)/100).  NO arrival gate: that is the phone
            kind's anti-noise rule (zone_bounce_alerts ARRIVAL_PCT); a
            FILTER must also show a name that lived near the band and
            lifted off it.
  pick      several bands/touches qualify -> freshest touch first (smallest
            sessions_ago), then the biggest bounce_pct.
  fields    bounce_pct = (print/touch_low-1)*100 · floor_pct · strong =
            bounce_pct >= max(STRONG_PCT, 2*atr_pct) · atr_x = (print -
            touch_low)/atr14 · role demand | broken_supply.

ROOM    ``room_read``
  overhead  supply bands with hi >= print, plus demand bands with lo > print
            (broken support = resistance; the SAME rule as
            portfolio.supply_watch.overhead_bands — re-stated here because
            the portfolio package cannot be imported on the py3.9 host, and
            pinned by a behavioural test that loads that file standalone).
  first     the overhead band containing the print, else the lowest lo.
  state     CLEAR    nothing overhead in the 1y frame  (room_pct null)
            IN_BAND  first contains the print          (room_pct 0.0)
            NEAR     room_pct <= NEAR_PCT
            ROOM     otherwise.       room_pct = (lo/print-1)*100,
            atr_days = (lo-print)/atr14.
  at_highs  high_252 known and print >= NEW_HIGH_TOL*high_252 (zone_edge's
            constant, imported).

Ordering (pure, mirrored in frontend/src/lib/bounceRoom.ts)
-----------------------------------------------------------
  room_rank(row)        (0)       CLEAR first
                        (1, -room_pct)  ROOM / NEAR / IN_BAND, biggest room first
                        (2)       no room read (pending / unavailable) last
  bounce_room_key(row)  (0 if bouncing else 1, *room_rank, -bounce_pct, symbol)

Why CLEAR sorts FIRST: no supply band overhead in the 1y frame means the
name is at/near its highs — its room is unbounded, not zero. Ajay treats
names clearing their last supply as the ones "likely to go much higher"
(EOSE / CLYM in the ask were exactly that shape). A page may still show
CLEAR as "at highs" rather than a %, the order is the same.

Constants (every one an owner setting; none is a book value)
-----------------------------------------------------------
  TOUCH_TOL_PCT   1.0   zone_bounce_alerts (imported, never redefined)
  WICK_PCT        1.5   zone_bounce_alerts (imported)
  BOUNCE_MIN_PCT  3.0   zone_bounce_alerts (imported)
  STRONG_PCT      5.0   zone_bounce_alerts (imported)
  NEW_HIGH_TOL    0.98  zone_edge (imported)
  LOOKBACK_SESSIONS 5   = zone_store.RECENT_SESSIONS (one truth)
  NEAR_PCT        2.0   supply_watch's NEAR line, re-stated (see ROOM)
  STALE_PRINT_SEC 180   a last trade older than 3 min is shown with
                        fresh=false — NEVER dropped (a filter shows the
                        last known price; the phone alert is the one that
                        must not act on an old print)
  RESPONSE_TTL_SEC 30   whole-response cache per sorted symbol set so a
                        polling page never fans out snapshot calls
  ONDEMAND_MAX_QUEUE 400 / ONDEMAND_BUDGET_SEC 240   one background batch
  ENGINE_RETRY_SEC 600  an on-demand build that RAISED (provider / Mongo
                        hiccup, pandas error) is marked in memory only and
                        retried after this; never a day-long tombstone

Coverage story
--------------
`store`    the symbol has a zone_store doc for the LATEST stored day <=
           today (zone_store.latest_store_day) — weekends and evenings
           answer with Friday's bands, never "empty because today has no
           doc". The $1B+ warm covers ~1,124 names.
`ondemand` not in the store (small caps, foreign, the Catalysts board):
           ONE daemon worker builds the same doc shape with
           zone_store.build_doc(sym, prices.load_prices(sym, "2y"), day)
           and caches it in Mongo `bounce_room_zones` (_id "SYM:date") —
           pattern: catalysts/promo_live.zones_for/_bg_compute. The
           request that discovers the miss returns immediately with those
           rows as `pending`; the next poll finds them.
`pending`  queued, no doc yet. The page says "pending", never CLEAR.
`unavailable`  a Mongo tombstone {"error": NO_DATA_ERROR} for the day when
           the frame cannot support a doc (missing / < 120 bars) so nothing
           retry-storms; an in-memory {"error": ENGINE_ERROR} marker for
           ENGINE_RETRY_SEC when the build raised (a transient failure must
           not tombstone 400 names for the day, and the exception text
           never reaches the browser); or no snapshot print for the name.
           The on-demand collection is purged past zone_store.KEEP_DAYS on
           every batch, like the store.

Never a network call per symbol on the request path: one zone_store read,
one cache read, one chunked bulk_snapshot for the covered names. Only
sepa.prices is imported from outside supply_demand, lazily.

S/D scope: a CONFIGURED price-structure heuristic, NOT a book method, no
Minervini cites, no SEPA gates. Decision support, never a buy signal, not
advice.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, time as dtime, timedelta
from typing import Callable, Iterable, Optional
from zoneinfo import ZoneInfo

from . import zone_store
from .zone_bounce_alerts import (BOUNCE_MIN_PCT, STRONG_PCT, TOUCH_TOL_PCT, WICK_PCT,
                                 is_eligible, print_from_snapshot)
from .zone_edge import NEW_HIGH_TOL, _clean as _json_clean
from .zone_store import RECENT_SESSIONS

log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")

LOOKBACK_SESSIONS = RECENT_SESSIONS   # 5 — a touch older than the doc's `recent` cannot be seen
NEAR_PCT = 2.0                        # <= this under the first overhead band -> NEAR
STALE_PRINT_SEC = 180                 # fresh flag only; the print is never dropped
RESPONSE_TTL_SEC = 30                 # per sorted symbol set
ONDEMAND_MAX_QUEUE = 400              # misses handed to ONE worker per request
ONDEMAND_BUDGET_SEC = 240             # the worker stops after this; the rest stay pending
ONDEMAND_COLL = "bounce_room_zones"
MAX_SYMBOLS = 2500                    # the route's cap (full SEPA universe is ~1,750)
ENGINE_RETRY_SEC = 600                # a build that raised is retried after this (memory marker)
SESSION_OPEN = dtime(9, 30)
SESSION_CLOSE = dtime(16, 0)
NO_DATA_ERROR = "no / insufficient price data"
ENGINE_ERROR = "engine error"         # the fixed text a raised build shows; never str(exc)
PX_REL_TOL = 1e-6                     # "the same price" when comparing a snapshot bar to a stored bar

PARAMS = {"touch_tol_pct": TOUCH_TOL_PCT, "wick_pct": WICK_PCT, "bounce_min_pct": BOUNCE_MIN_PCT,
          "strong_pct": STRONG_PCT, "lookback_sessions": LOOKBACK_SESSIONS, "near_pct": NEAR_PCT,
          "stale_print_sec": STALE_PRINT_SEC, "new_high_tol": NEW_HIGH_TOL}

DISCLAIMER = ("Configured price-structure heuristic (supply/demand bands from zone_store; "
              "touch / bounce / room thresholds are owner settings), not a book method. "
              "Coverage is partial (pending / unavailable rows are not CLEAR). "
              "Decision support, not a buy signal, not advice.")

ROOM_STATES = ("CLEAR", "IN_BAND", "NEAR", "ROOM")


def _now_et() -> datetime:
    return datetime.now(ET)


def in_session(now: Optional[datetime] = None) -> bool:
    """RTH weekdays 9:30-16:00 ET, evaluated at request time."""
    now = (now or _now_et()).astimezone(ET)
    if now.weekday() >= 5:
        return False
    return SESSION_OPEN <= now.time() <= SESSION_CLOSE


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------
def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def _kind(band: dict) -> str:
    return str(band.get("kind") or "demand").lower()


def _valid_band(band: dict) -> bool:
    lo, hi = _f(band.get("lo")), _f(band.get("hi"))
    return lo is not None and hi is not None and 0 < lo <= hi


def _slim_band(band: dict, with_strength: bool = True) -> dict:
    out = {"kind": _kind(band), "lo": float(band["lo"]), "hi": float(band["hi"]),
           "touches": int(_f(band.get("touches")) or 0)}
    if with_strength:
        out["strength"] = float(_f(band.get("strength")) or 0.0)
    return out


def _iso_day(x) -> Optional[str]:
    """'YYYY-MM-DD' from a str / date / datetime / pandas Timestamp; None
    when it cannot be read. The snapshot's `date` is a pandas Timestamp."""
    if x is None:
        return None
    if isinstance(x, str):
        return x[:10] if len(x) >= 10 else None
    try:
        if hasattr(x, "date") and callable(x.date):
            return x.date().isoformat()
        if hasattr(x, "isoformat"):
            return x.isoformat()[:10]
    except Exception:
        return None
    return None


def is_touch(low, band: dict, touch_tol_pct: float = TOUCH_TOL_PCT,
             wick_pct: float = WICK_PCT) -> bool:
    """The alert's TOUCH test on one session low: stopped within
    TOUCH_TOL_PCT above the top, or undercut the floor by at most WICK_PCT."""
    lo_px = _f(low)
    if lo_px is None or lo_px <= 0 or not _valid_band(band):
        return False
    lo, hi = float(band["lo"]), float(band["hi"])
    return lo_px <= hi * (1 + touch_tol_pct / 100.0) and lo_px >= lo * (1 - wick_pct / 100.0)


def _same_px(a, b, rel: float = PX_REL_TOL) -> bool:
    x, y = _f(a), _f(b)
    if x is None or y is None:
        return False
    return abs(x - y) <= rel * max(abs(x), abs(y), 1e-9)


def is_store_session_bar(doc: dict, snapshot_low, snapshot_date, store_date,
                         snapshot: Optional[dict] = None) -> bool:
    """Is the snapshot's day bar the STORE DAY's own session (-> sessions_ago
    0)? Decided by data, not by the snapshot's date: bulk_snapshot dates a
    bar TODAY when Massive omits day.t (its own comment, sepa/prices.py), so
    on a Saturday Friday's bar arrives dated Saturday, and on a weekday
    holiday Friday's bar arrives dated Monday while the 9:20 warm already
    put Friday in `recent`.

    (a) low / high / close equal to recent[-1]'s -> it IS that closed bar,
        already counted as sessions_ago 1 -> False.
    (b) else True when the bar's date == the store day, or when the date is
        later and the snapshot's prevDay close == the doc's prev_close (the
        bar before the store day: the day bar can only be the store-day
        session). A Monday bar over a Friday store (warm failed) has
        Friday's close as prevDay -> False: that low is NOT seen, which is
        an honest miss, never a false touch."""
    low0 = _f(snapshot_low)
    if low0 is None or low0 <= 0:
        return False
    snap = snapshot or {}
    recent = [r for r in ((doc or {}).get("recent") or []) if isinstance(r, dict)]
    if recent:
        last = recent[-1]
        if (_same_px(low0, last.get("low")) and _same_px(snap.get("close"), last.get("close"))
                and (snap.get("high") is None or last.get("high") is None
                     or _same_px(snap.get("high"), last.get("high")))):
            return False
    snap_day, store_day = _iso_day(snapshot_date), _iso_day(store_date)
    if snap_day is None or store_day is None:
        return False
    if snap_day == store_day:
        return True
    return snap_day > store_day and _same_px(snap.get("prev_day_close"), (doc or {}).get("prev_close"))


def touch_hits(doc: dict, snapshot_low, snapshot_date, store_date,
               lookback: int = LOOKBACK_SESSIONS, *, snapshot: Optional[dict] = None) -> list:
    """Every (band, touch_low, touch_date, sessions_ago) where a session low
    touched an ELIGIBLE band. sessions_ago 0 = the snapshot's day bar, counted
    only when is_store_session_bar says it IS the store day's session (its
    touch_date is then the store day, whatever the snapshot's date fallback
    says); 1..lookback = the doc's `recent` closed sessions, newest = 1.
    `snapshot` (the bulk_snapshot row: high / close / prev_day_close) feeds
    that identity check. Freshest first. [] when nothing touched or the doc
    has no usable bands."""
    if not doc:
        return []
    prev_close = _f(doc.get("prev_close"))          # None -> supply bands never eligible
    bands = [b for b in doc.get("bands") or [] if _valid_band(b) and is_eligible(b, prev_close)]
    if not bands:
        return []
    candidates: list = []
    store_day = _iso_day(store_date)
    low0 = _f(snapshot_low)
    if is_store_session_bar(doc, low0, snapshot_date, store_date, snapshot):
        candidates.append((low0, store_day, 0))
    recent = [r for r in (doc.get("recent") or []) if isinstance(r, dict)]
    n = len(recent)
    for i, r in enumerate(recent):
        ago = n - i
        if ago > lookback:
            continue
        low = _f(r.get("low"))
        if low is None or low <= 0:
            continue
        candidates.append((low, _iso_day(r.get("date")), ago))
    hits = []
    for low, day, ago in candidates:
        for b in bands:
            if is_touch(low, b):
                hits.append((b, low, day, ago))
    hits.sort(key=lambda h: (h[3], -float(h[0]["hi"])))     # freshest, then the higher shelf
    return hits


def bounce_read(print_px, doc: dict, touches: list,
                bounce_min_pct: float = BOUNCE_MIN_PCT,
                strong_pct: float = STRONG_PCT) -> Optional[dict]:
    """The best qualifying bounce among `touches` (from touch_hits), or None.
    print > band.hi AND print >= touch_low * (1 + max(bounce_min_pct,
    atr_pct)/100). No arrival gate (see module docstring). Freshest touch
    wins, then the bigger bounce."""
    px = _f(print_px)
    if px is None or px <= 0 or not touches:
        return None
    atr = _f((doc or {}).get("atr14")) or 0.0
    if atr < 0:
        atr = 0.0
    best = None
    for band, touch_low, touch_date, ago in touches:
        low = _f(touch_low)
        if low is None or low <= 0 or not _valid_band(band):
            continue
        hi = float(band["hi"])
        if px <= hi:
            continue                                      # still in / under the band
        atr_pct = 100.0 * atr / low
        floor = max(bounce_min_pct, atr_pct)
        bounce_pct = (px / low - 1.0) * 100.0
        if bounce_pct < floor:
            continue
        cand = {"band": _slim_band(band),
                "role": "broken_supply" if _kind(band) == "supply" else "demand",
                "touch_low": round(low, 4), "touch_date": touch_date, "sessions_ago": int(ago),
                "bounce_pct": round(bounce_pct, 2), "floor_pct": round(floor, 2),
                "strong": bool(bounce_pct >= max(strong_pct, 2.0 * atr_pct)),
                "atr_x": round((px - low) / atr, 1) if atr > 0 else None}
        key = (cand["sessions_ago"], -cand["bounce_pct"])
        if best is None or key < best[0]:
            best = (key, cand)
    return best[1] if best else None


def overhead_bands(bands: list, live: float) -> list:
    """Everything price meets going UP: supply bands at/above the print plus
    demand bands strictly above it (broken support = resistance). A demand
    band that CONTAINS price is support, never overhead. Same rule as
    portfolio.supply_watch.overhead_bands — kept in step by
    tests/test_bounce_room.py, which loads that file standalone."""
    out = []
    for b in bands or []:
        if not _valid_band(b):
            continue
        lo, hi = float(b["lo"]), float(b["hi"])
        if _kind(b) == "supply" and hi >= live:
            out.append(dict(_slim_band(b, with_strength=False), kind="supply"))
        elif _kind(b) == "demand" and lo > live:
            out.append(dict(_slim_band(b, with_strength=False), kind="broken_support"))
    return out


def first_overhead(overhead: list, live: float) -> Optional[dict]:
    """The band price meets FIRST going up: the one containing `live` (lowest
    lo when nested), else the lowest lo above it. None = clear."""
    if not overhead:
        return None
    inside = [b for b in overhead if b["lo"] <= live <= b["hi"]]
    if inside:
        return min(inside, key=lambda b: b["lo"])
    return min(overhead, key=lambda b: b["lo"])


def room_read(print_px, doc: dict, near_pct: float = NEAR_PCT) -> Optional[dict]:
    """{"state", "room_pct", "atr_days", "band", "at_highs"} for a valid
    print; None when the print is unusable."""
    px = _f(print_px)
    if px is None or px <= 0:
        return None
    doc = doc or {}
    h252 = _f(doc.get("high_252"))
    at_highs = bool(h252 is not None and h252 > 0 and px >= NEW_HIGH_TOL * h252)
    first = first_overhead(overhead_bands(doc.get("bands") or [], px), px)
    if first is None:
        return {"state": "CLEAR", "room_pct": None, "atr_days": None, "band": None,
                "at_highs": at_highs}
    band = {"kind": first["kind"], "lo": first["lo"], "hi": first["hi"],
            "touches": int(first.get("touches") or 0)}
    if first["lo"] <= px <= first["hi"]:
        return {"state": "IN_BAND", "room_pct": 0.0, "atr_days": 0.0, "band": band,
                "at_highs": at_highs}
    atr = _f(doc.get("atr14")) or 0.0
    room_pct = (first["lo"] / px - 1.0) * 100.0
    return {"state": "NEAR" if room_pct <= near_pct else "ROOM",
            "room_pct": round(room_pct, 2),
            "atr_days": round((first["lo"] - px) / atr, 1) if atr > 0 else None,
            "band": band, "at_highs": at_highs}


def room_rank(row: dict) -> tuple:
    """(group, -room_pct): CLEAR first (group 0), then ROOM/NEAR/IN_BAND by
    room_pct DESC (group 1), then anything without a room read (pending /
    unavailable / None) last (group 2)."""
    room = (row or {}).get("room") or {}
    state = room.get("state")
    if state == "CLEAR":
        return (0, 0.0)
    if state in ("ROOM", "NEAR", "IN_BAND"):
        pct = _f(room.get("room_pct"))
        if pct is not None:
            return (1, -pct)
    return (2, 0.0)


def bounce_room_key(row: dict) -> tuple:
    """Sort key shared by all three surfaces: bouncing names first, then
    room_rank, then the bigger bounce, then the symbol (stable)."""
    bounce = (row or {}).get("bounce") or None
    bouncing = 0 if bounce else 1
    bounce_pct = _f((bounce or {}).get("bounce_pct")) or 0.0
    return (bouncing,) + tuple(room_rank(row)) + (-bounce_pct, str((row or {}).get("symbol") or ""))


def print_of(snap: Optional[dict], now_ts: float,
             stale_sec: float = STALE_PRINT_SEC) -> tuple[Optional[float], bool]:
    """(print, fresh). The last trade (fresh when its stamp is within
    `stale_sec` of now — print_from_snapshot's normalisation of ns/ms/s
    stamps), else the last trade anyway with fresh=False, else the day close
    with fresh=False. (None, False) when the snapshot carries no price. A
    filter shows the last known price; only the phone alert drops stale."""
    if not snap:
        return None, False
    px, stale = print_from_snapshot(snap, now_ts, stale_sec)
    if px is not None and not stale:
        return float(px), True
    last = _f(snap.get("last_trade_price"))
    if last is not None and last > 0:
        return last, False
    close = _f(snap.get("close"))
    if close is not None and close > 0:
        return close, False
    return None, False


def _coverage_of(doc: dict) -> str:
    return "ondemand" if (doc or {}).get("origin") == "ondemand" else "store"


def read_symbol(sym: str, doc: Optional[dict], snap: Optional[dict],
                now: Optional[datetime] = None) -> dict:
    """One contract row. A tombstone doc ({"error": ...}) or a missing print
    -> coverage 'unavailable'; no doc -> 'pending'."""
    sym = str(sym).upper()
    if not doc:
        return {"symbol": sym, "coverage": "pending"}
    if doc.get("error"):
        return {"symbol": sym, "coverage": "unavailable", "error": str(doc["error"])}
    now = now or _now_et()
    px, fresh = print_of(snap, now.timestamp())
    if px is None:
        return {"symbol": sym, "coverage": "unavailable", "error": "no print in snapshot"}
    snap = snap or {}
    touches = touch_hits(doc, snap.get("low"), snap.get("date"), doc.get("date"), snapshot=snap)
    return {"symbol": sym, "print": round(px, 4), "fresh": bool(fresh),
            "coverage": _coverage_of(doc),
            "bounce": bounce_read(px, doc, touches),
            "room": room_read(px, doc)}


# --------------------------------------------------------------------------
# I/O layer
# --------------------------------------------------------------------------
def _coll(name: str):
    try:
        from portfolio.store import _get_db
        db = _get_db()
        return db[name] if db is not None else None
    except Exception as exc:
        log.warning("bounce_room: no mongo for %s: %s", name, exc)
        return None


def _today_et(now: Optional[datetime] = None) -> date:
    return (now or _now_et()).astimezone(ET).date()


def last_weekday(d: date) -> date:
    """`d` itself Mon-Fri, else the Friday before it. The cold-store fallback
    day: an on-demand doc dated Saturday would keep Friday's bar in `recent`
    AND see it again in the snapshot (dated Saturday by bulk_snapshot's
    fallback) — the store never has weekend days, so neither does this."""
    while d.weekday() >= 5:
        d = d - timedelta(days=1)
    return d


def normalize_symbols(symbols: Iterable, cap: int = MAX_SYMBOLS) -> list:
    """Upper-cased, stripped, de-duplicated (first occurrence wins), capped."""
    out, seen = [], set()
    for s in symbols or []:
        t = str(s or "").strip().upper()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= cap:
            break
    return out


# In-process copy of the on-demand docs so a container without Mongo (or a
# write that failed) still serves what the worker computed. Keyed by
# "SYM:date"; entries for other days are dropped on every read.
_mem: dict = {}
_mem_lock = threading.Lock()


def _ondemand_id(sym: str, day) -> str:
    return f"{sym}:{_iso_day(day)}"


def load_docs(symbols: list, day, store_coll=None, ondemand_coll=None,
              now_ts: Optional[float] = None) -> tuple[dict, list]:
    """({SYMBOL: doc}, missing). Store docs first (zone_store.load for `day`),
    then the on-demand cache (Mongo `bounce_room_zones`, then memory) —
    tombstones come back as docs carrying "error" so the row reads
    'unavailable'. An in-memory ENGINE_ERROR marker whose `retry_after` has
    passed (clock = `now_ts`) is dropped so the name is re-queued. `missing`
    = no doc anywhere, in request order."""
    symbols = [str(s).upper() for s in symbols]
    now_ts = time.time() if now_ts is None else float(now_ts)
    docs = dict(zone_store.load(symbols, day, coll=store_coll) or {}) if symbols else {}
    missing = [s for s in symbols if s not in docs]
    if not missing:
        return docs, []
    day_iso = _iso_day(day)
    ids = [_ondemand_id(s, day_iso) for s in missing]
    coll = ondemand_coll if ondemand_coll is not None else _coll(ONDEMAND_COLL)
    if coll is not None:
        try:
            for d in coll.find({"_id": {"$in": ids}}):
                sym = str(d.get("symbol") or str(d.get("_id", "")).split(":")[0]).upper()
                if sym:
                    docs[sym] = d
        except Exception as exc:
            log.warning("bounce_room: on-demand cache read failed: %s", exc)
    with _mem_lock:
        for k in [k for k in _mem if not k.endswith(f":{day_iso}")]:
            _mem.pop(k, None)
        for k in [k for k, d in _mem.items()
                  if d.get("retry_after") is not None and float(d["retry_after"]) <= now_ts]:
            _mem.pop(k, None)
        for s in missing:
            if s not in docs and _ondemand_id(s, day_iso) in _mem:
                docs[s] = _mem[_ondemand_id(s, day_iso)]
    return docs, [s for s in missing if s not in docs]


def default_builder(sym: str, day) -> Optional[dict]:
    """zone_store.build_doc on the shared price cache — the ONLY provider
    path here, and only ever on the worker thread."""
    from sepa import prices
    df = prices.load_prices(sym, period="2y")
    return zone_store.build_doc(sym, df, day)


def compute_batch(syms: list, day, coll=None, *, builder: Optional[Callable] = None,
                  budget_sec: float = ONDEMAND_BUDGET_SEC, now_ts: Optional[float] = None) -> dict:
    """The worker body (synchronous; the daemon thread calls it). Builds the
    same doc shape as the store for each symbol, tags origin='ondemand',
    writes a {"error": NO_DATA_ERROR} tombstone for the day when the frame
    cannot support a doc (builder -> None), and stops at the budget — the
    rest stay pending for a later request.

    A builder that RAISES (a transient Mongo / provider hiccup inside
    load_prices, a pandas error) is NOT tombstoned: one bad minute would
    otherwise mark up to 400 names 'unavailable' until the next 9:20 warm,
    with a stack-trace fragment as the row's error. It gets an in-memory
    marker {"error": ENGINE_ERROR, "retry_after": now + ENGINE_RETRY_SEC}
    that load_docs drops once due, so the name is re-queued; the single
    worker and the 30 s response cache bound the retry rate.

    Old on-demand docs (< day - zone_store.KEEP_DAYS) are purged at the end
    of every batch — the collection has no other reader or TTL."""
    t0 = time.time()
    retry_at = (time.time() if now_ts is None else float(now_ts)) + ENGINE_RETRY_SEC
    builder = builder or default_builder
    done = failed = errored = 0
    timed_out = False
    day_obj = day if isinstance(day, date) else date.fromisoformat(_iso_day(day))
    for sym in syms:
        if time.time() - t0 > budget_sec:
            timed_out = True
            break
        _id = _ondemand_id(sym, day_obj)
        try:
            doc = builder(sym, day_obj)
        except Exception as exc:
            log.warning("bounce_room: on-demand build raised for %s: %s", sym, exc)
            errored += 1
            with _mem_lock:
                _mem[_id] = {"_id": _id, "symbol": sym, "date": day_obj.isoformat(),
                             "origin": "ondemand", "error": ENGINE_ERROR,
                             "retry_after": retry_at}
            continue
        if doc is None:
            doc = {"_id": _id, "symbol": sym, "date": day_obj.isoformat(), "origin": "ondemand",
                   "error": NO_DATA_ERROR, "computed_at": _now_et().isoformat()}
            failed += 1
        else:
            doc = dict(doc, _id=_id, origin="ondemand")
            done += 1
        with _mem_lock:
            _mem[_id] = doc
        if coll is not None:
            try:
                coll.replace_one({"_id": _id}, doc, upsert=True)
            except Exception as exc:
                log.warning("bounce_room: on-demand cache write failed for %s: %s", sym, exc)
    purged = purge_ondemand(coll, day_obj)
    out = {"asked": len(syms), "built": done, "tombstoned": failed, "errored": errored,
           "purged": purged, "timed_out": timed_out, "seconds": round(time.time() - t0, 1)}
    log.info("bounce_room: on-demand batch %s", out)
    return out


def purge_ondemand(coll, day: date, keep_days: int = zone_store.KEEP_DAYS) -> int:
    """Drop on-demand docs dated before `day - keep_days` (zone_store.purge's
    rule, same window). 0 when there is no collection or the delete fails —
    housekeeping never fails a batch."""
    if coll is None:
        return 0
    cutoff = (day - timedelta(days=keep_days)).isoformat()
    try:
        res = coll.delete_many({"date": {"$lt": cutoff}})
        return int(getattr(res, "deleted_count", 0) or 0)
    except Exception as exc:
        log.warning("bounce_room: on-demand purge failed: %s", exc)
        return 0


# One background worker at a time (promo_live pattern): a request never waits
# on the zone engine; it reports the misses as pending and the next poll finds
# them. A second request while the worker runs is not queued — its misses are
# re-discovered on the poll after the worker releases itself.
_bg_lock = threading.Lock()
_bg = {"running": False}


def queue_ondemand(missing: list, day, coll=None, *, builder: Optional[Callable] = None,
                   max_queue: int = ONDEMAND_MAX_QUEUE, now_ts: Optional[float] = None) -> int:
    """Hand up to `max_queue` misses to the single daemon worker. Returns how
    many were handed over (0 when a worker is already running)."""
    syms = list(missing or [])[:max_queue]
    if not syms:
        return 0
    with _bg_lock:
        kick = not _bg["running"]
        if kick:
            _bg["running"] = True
    if not kick:
        return 0

    def run():
        try:
            compute_batch(syms, day, coll, builder=builder, now_ts=now_ts)
        except Exception as exc:                                # pragma: no cover
            log.warning("bounce_room: on-demand worker failed: %s", exc)
        finally:
            with _bg_lock:
                _bg["running"] = False

    try:
        threading.Thread(target=run, daemon=True, name="bounce-room-zones").start()
    except Exception as exc:
        # RuntimeError("can't start new thread") under resource pressure: the
        # flag must not stay True or no on-demand doc is ever built again
        # until the container restarts — the misses just stay pending.
        with _bg_lock:
            _bg["running"] = False
        log.warning("bounce_room: on-demand worker could not start: %s", exc)
        return 0
    return len(syms)


def build_payload(symbols: list, *, docs: dict, snapshot: Optional[dict], now: datetime,
                  store_date, pending: Optional[list] = None,
                  unavailable: Optional[dict] = None) -> dict:
    """The response contract from already-loaded inputs (pure given them).
    `snapshot` None = no snapshot was read (nothing covered) -> as_of null.
    `pending` is informational (a symbol without a doc is pending either
    way); `unavailable` = {sym: reason} for names that can never be covered
    (rejected upstream) and have no tombstone doc."""
    snap_read = snapshot is not None
    snapshot = snapshot or {}
    unavailable = unavailable or {}
    rows: dict = {}
    for sym in symbols:
        doc = docs.get(sym)
        if doc is not None:
            rows[sym] = read_symbol(sym, doc, snapshot.get(sym), now)
        elif sym in unavailable:
            rows[sym] = {"symbol": sym, "coverage": "unavailable", "error": str(unavailable[sym])}
        else:
            rows[sym] = {"symbol": sym, "coverage": "pending"}
    covered = sum(1 for r in rows.values() if r["coverage"] in ("store", "ondemand"))
    n_pending = sum(1 for r in rows.values() if r["coverage"] == "pending")
    n_unavail = sum(1 for r in rows.values() if r["coverage"] == "unavailable")
    return _json_clean({
        "as_of": now.astimezone(ET).isoformat() if snap_read else None,
        "in_session": in_session(now),
        "store_date": _iso_day(store_date),
        "params": dict(PARAMS),
        "rows": rows,
        "requested": len(symbols), "covered": covered, "pending": n_pending,
        "unavailable": n_unavail,
        "disclaimer": DISCLAIMER,
    })


_resp_cache: dict = {}
_resp_lock = threading.Lock()


def _cache_get(key: tuple, now_ts: float) -> Optional[dict]:
    with _resp_lock:
        hit = _resp_cache.get(key)
    if hit and now_ts - hit[0] <= RESPONSE_TTL_SEC and now_ts >= hit[0]:
        return hit[1]
    return None


def _cache_put(key: tuple, now_ts: float, payload: dict) -> None:
    with _resp_lock:
        if len(_resp_cache) > 64:                  # a handful of pages poll; never grows unbounded
            _resp_cache.clear()
        _resp_cache[key] = (now_ts, payload)


def api_payload(symbols: Iterable, *, now: Optional[datetime] = None, store_coll=None,
                ondemand_coll=None, snapshot_fn: Optional[Callable] = None,
                builder: Optional[Callable] = None, background: bool = True) -> dict:
    """POST/GET /supply-demand/bounce-room. One store read, one cache read,
    one chunked snapshot for the covered names; misses go to the worker and
    come back as pending. Whole response cached RESPONSE_TTL_SEC per sorted
    symbol set (clock = `now`, so tests are deterministic)."""
    now = now or _now_et()
    syms = normalize_symbols(symbols)
    key = tuple(sorted(syms))
    now_ts = now.timestamp()
    cached = _cache_get(key, now_ts)
    if cached is not None:
        return cached
    today = _today_et(now)
    day = zone_store.latest_store_day(coll=store_coll, today=today)
    if day is None:
        day = last_weekday(today)                   # store cold: on-demand docs for the last session day
    docs, missing = load_docs(syms, day, store_coll=store_coll, ondemand_coll=ondemand_coll,
                              now_ts=now_ts)
    if missing and background:
        coll = ondemand_coll if ondemand_coll is not None else _coll(ONDEMAND_COLL)
        queue_ondemand(missing, day, coll, builder=builder, now_ts=now_ts)
    priced = [s for s in syms if s in docs and not docs[s].get("error")]
    snapshot: Optional[dict] = None
    if priced:
        if snapshot_fn is None:
            def snapshot_fn(names):
                from sepa import prices
                return prices.bulk_snapshot(names)
        try:
            snapshot = snapshot_fn(priced) or {}
        except Exception as exc:
            log.warning("bounce_room: snapshot failed: %s", exc)
            snapshot = {}
    payload = build_payload(syms, docs=docs, snapshot=snapshot, now=now, store_date=day,
                            pending=missing)
    _cache_put(key, now_ts, payload)
    return payload


if __name__ == "__main__":
    import json
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    argv = [a for a in sys.argv[1:] if a]
    if not argv:
        print("usage: python -m supply_demand.bounce_room SYM [SYM ...]")
        sys.exit(2)
    out = api_payload(argv)
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))
    for sym in sorted(out["rows"].values(), key=bounce_room_key):
        print(json.dumps(sym))
