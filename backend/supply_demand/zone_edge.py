"""Zone edge — $1B+ names within 1% of BREAKING their last supply band toward
new highs, and names within 1% ABOVE a demand level. Every minute in RTH,
tracked minute by minute, pushed once per band per day.

Ajay 2026-09-03 (~5pm ET, verbatim): "1. Oh I need stocks that are <1% away
from breaking supply zones which are going for new highs... 2. and stocks
that are just <1% away from Demand zones. I need you to give me an alert and
also to track these min on min. Actually can you add #1 stocks in to Demand
zone too ones breaking resistance and also in to deep demand zones. I wanna
keep track of these."

Two reads per name, both against the LIVE print and the bands zone_store
drew BEFORE today (board geometry, every band, both kinds):

Side A — "breaking" (resistance)  ``read_breaking``
-----------------------------------------------------
  resistance  the supply band with the SMALLEST top at or above the print
  near        0 <= (hi - px) / px <= EDGE_PCT           within 1% under it
  broke       no near band, and some supply band has
              hi < px <= hi * (1 + BROKE_MAX_PCT%)  AND  prev_close <= hi
              — it broke TODAY (yesterday still closed at/under the ceiling)
              and is at most 3% through; the HIGHEST such band. dist_pct is
              NEGATIVE (= above the ceiling).
  new_highs   no supply band sits above the band (nothing overhead), OR the
              band's top is at/above 98% of the 252-bar high (the last shelf
              IS the 52-week high area).
  overhead    count of supply bands with lo > band.hi (told on the board).

Side B — "near_demand"  ``read_near_demand``
---------------------------------------------
  support     demand bands, plus supply bands yesterday CLOSED above (hi <
              prev_close — zone_bounce_alerts.is_eligible, the house
              definition of broken supply = support, role 'broken supply' —
              the NTAP shelf of 09-03). A shelf broken TODAY is Side A's fact
              and never support here: counting it made one breakout two
              pushes (🚀 broke + 🧲 "above demand", same band, same minute).
  in          a demand band with lo <= px <= hi (dist 0).
  near        else the support band with the GREATEST top <= px, when
              (px - hi) / px <= EDGE_PCT.
  arrival     demand_alerts.read(px, band, change_pct, prev_close) is not
              None — the IDENTICAL rule the 5-min demand_alerts pass uses:
              yesterday closed outside the 1% ring or under the floor.
              Unknown prev close = resident (never pushed), counted.

Board vs phone
--------------
The board (Mongo ``zone_edge_latest`` → GET /supply-demand/zone-edge) lists
EVERY near/broke/in name with a KNOWN cap, each band with its touch count,
arrivals and residents tagged. The phone gets a strict subset:

  breaking    new_highs AND band.touches >= MIN_TOUCHES_PUSH AND cap >= $1B
              kind ``supply_break_alert`` (NEW), state ``supply_break_state``,
              once per (symbol, band, day, tier).
  near demand arrivals only, touches >= MIN_TOUCHES_PUSH, cap >= $1B — kind
              ``demand_alert`` REUSED with demand_alerts.state_key(...,'at')
              in demand_alerts.STATE_COLL, so the 5-min module and this one
              can never double-fire the same band on the same day.

Per side: strongest MAX_SINGLES_PER_PASS get their own push, the rest ONE
digest (trade_flash discipline). Digest names are recorded too — nothing
repeats. State is written only on a terminal send (delivered, or nobody
targeted); a transport failure retries next minute.

Tracking ("min on min")
-----------------------
Every pass upserts ``zone_edge_latest`` (_id 'latest' = the API payload
without the track) and appends one ``zone_edge_track`` row per listed row
{symbol, date, ts, side, tier, px, dist_pct, band}. Rows older than
TRACK_KEEP_DAYS are purged each pass. first_seen per (symbol, side, band,
date) = the first minute that key was listed today (== the earliest track
row for it, since every listing writes a row), kept as ONE per-day map doc
(_id 'first_seen' in zone_edge_latest) so no pass re-reads the day's rows.
The API attaches the last TRACK_POINTS minutes per "side:SYM" up to as_of —
a window, so the read is bounded by TRACK_POINTS rows per key instead of the
whole day (hundreds of rows a minute pile up to ~100k by mid-afternoon).

Cost: one zone_store read, one bulk_snapshot (~5 chunked HTTP calls for
~1,124 names), one caps read, ONE names read, ONE $in read per state coll,
one first_seen doc read/write, one insert_many, one delete_many. NO
per-symbol network call and NO per-symbol Mongo round trip anywhere —
this runs every minute and must stay well under 60 s. Print freshness:
STALE_PRINT_SEC = 180 (a 3-minute-old trade is not "now" on a one-minute
cadence).

Configured price-structure heuristic, S/D scope, NOT a book method, no
Minervini cites. Decision support, not a buy signal, not advice.
"""
from __future__ import annotations

import logging
import math
import time
from datetime import datetime, time as dtime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from . import demand_alerts as DA
from .zone_bounce_alerts import print_from_snapshot

log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")

EDGE_PCT = 1.0                     # "<1% away" — within this of the level
BROKE_MAX_PCT = 3.0                # broke today, at most this far through the ceiling
MIN_CAP_USD = 1_000_000_000.0      # "billion or at least bigger than a billion"
MIN_TOUCHES_PUSH = 2               # pushes only; the board lists every band + its touches
MAX_SINGLES_PER_PASS = 3           # strongest first; the rest ride ONE digest
DIGEST_MAX = 6                     # names spelled out in one digest body
STALE_PRINT_SEC = 180              # one-minute cadence: a 3-min-old print is not "now"
SESSION_OPEN = dtime(9, 31)        # first pass after the open + first prints
SESSION_CLOSE = dtime(16, 0)
TRACK_KEEP_DAYS = 2                # track rows older than this are purged every pass
TRACK_POINTS = 30                  # points per "side:SYM" the API hands the sparkline
KIND_BREAK = "supply_break_alert"
STATE_COLL_BREAK = "supply_break_state"
LATEST_COLL = "zone_edge_latest"
TRACK_COLL = "zone_edge_track"
NEW_HIGH_TOL = 0.98                # band top >= 98% of the 252-bar high = "at the 52w high"

DISCLAIMER = ("Configured price-structure heuristic (supply/demand bands from zone_store), "
              "not a book method. Decision support, not a buy signal, not advice.")


def _now_et() -> datetime:
    return datetime.now(ET)


def in_session(now: Optional[datetime] = None) -> bool:
    """RTH weekdays 9:31-16:00 ET."""
    now = now or _now_et()
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
    return v if v == v and not math.isinf(v) else None      # NaN / inf guard


def _valid_band(band: dict) -> bool:
    lo, hi = _f(band.get("lo")), _f(band.get("hi"))
    return lo is not None and hi is not None and 0 < lo <= hi


def _kind(band: dict) -> str:
    return str(band.get("kind") or "demand").lower()


def _slim_band(band: dict) -> dict:
    return {"kind": _kind(band), "lo": float(band["lo"]), "hi": float(band["hi"]),
            "touches": int(_f(band.get("touches")) or 0),
            "strength": float(_f(band.get("strength")) or 0.0)}


def _clean(obj):
    """JSON-safe: plain float/int/str/bool/None, recursively. numpy scalars
    become Python numbers; NaN/inf become None."""
    if obj is None or isinstance(obj, (bool, str)):
        return obj
    if isinstance(obj, int):
        return int(obj)
    if isinstance(obj, float):
        return float(obj) if (obj == obj and not math.isinf(obj)) else None
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if hasattr(obj, "item"):                                  # numpy scalar
        try:
            return _clean(obj.item())
        except Exception:
            return None
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    try:
        return _clean(float(obj))
    except (TypeError, ValueError):
        return str(obj)


# --------------------------------------------------------------------------
# Pure reads
# --------------------------------------------------------------------------
def read_breaking(px, bands: list, prev_close=None, high_252=None,
                  edge_pct: float = EDGE_PCT, broke_max_pct: float = BROKE_MAX_PCT) -> Optional[dict]:
    """Side A. None = not within 1% under its resistance and did not break a
    ceiling today.

    {"tier": "near"|"broke", "band", "dist_pct", "new_highs", "overhead_bands",
     "high_252", "pct_to_52w"}   dist_pct < 0 = above the ceiling (broke).
    """
    px = _f(px)
    if px is None or px <= 0:
        return None
    supply = [b for b in bands or [] if _kind(b) == "supply" and _valid_band(b)]
    if not supply:
        return None
    tier, band, dist = None, None, None
    above = [b for b in supply if float(b["hi"]) >= px]
    if above:
        res = min(above, key=lambda b: float(b["hi"]))
        d = (float(res["hi"]) - px) / px * 100.0
        if 0.0 <= d <= edge_pct:
            tier, band, dist = "near", res, d
    if tier is None:
        pc = _f(prev_close)
        if pc is None or pc <= 0:
            return None                                   # cannot tell "broke today"
        broke = [b for b in supply
                 if float(b["hi"]) < px <= float(b["hi"]) * (1.0 + broke_max_pct / 100.0)
                 and pc <= float(b["hi"])]
        if not broke:
            return None
        band = max(broke, key=lambda b: float(b["hi"]))
        tier, dist = "broke", -(px - float(band["hi"])) / px * 100.0
    hi = float(band["hi"])
    overhead = sum(1 for b in supply if float(b["lo"]) > hi)
    h252 = _f(high_252)
    if h252 is not None and h252 <= 0:
        h252 = None
    at_52w = h252 is not None and hi >= NEW_HIGH_TOL * h252
    pct_to_52w = round((h252 - px) / px * 100.0, 2) if h252 is not None else None
    return {"tier": tier, "band": _slim_band(band), "dist_pct": round(dist, 2),
            "new_highs": bool(overhead == 0 or at_52w), "overhead_bands": int(overhead),
            "high_252": h252, "pct_to_52w": pct_to_52w}


def read_near_demand(px, bands: list, change_pct=None, prev_close=None,
                     edge_pct: float = EDGE_PCT) -> Optional[dict]:
    """Side B. None = not inside a demand band and not within 1% above the
    nearest support (demand, or broken supply).

    Broken supply = a supply band yesterday CLOSED above (hi < prev_close):
    zone_bounce_alerts.is_eligible, the house rule. A shelf broken TODAY is
    Side A's "broke" fact, not support — with hi < px alone the same band
    fired 🚀 broke and 🧲 "above demand" in the same minute. Unknown prev
    close: supply bands are never support (as in zone_bounce); demand bands
    still list, as residents.

    {"tier": "in"|"near", "band", "role": "demand"|"broken supply", "dist_pct",
     "arrival", "hit"}   hit = demand_alerts.read(...) (None for a resident /
     unknown prev close); arrival = hit is not None.
    """
    px = _f(px)
    if px is None or px <= 0:
        return None
    pc = _f(prev_close)
    if pc is not None and pc <= 0:
        pc = None
    demand = [b for b in bands or [] if _kind(b) == "demand" and _valid_band(b)]
    broken = [b for b in bands or [] if _kind(b) == "supply" and _valid_band(b)
              and float(b["hi"]) < px and pc is not None and float(b["hi"]) < pc]
    tier, band, dist = None, None, None
    inside = [b for b in demand if float(b["lo"]) <= px <= float(b["hi"])]
    if inside:
        tier, band, dist = "in", max(inside, key=lambda b: float(b["hi"])), 0.0
    else:
        support = [b for b in demand if float(b["hi"]) <= px] + broken
        if not support:
            return None
        band = max(support, key=lambda b: float(b["hi"]))
        d = (px - float(band["hi"])) / px * 100.0
        if d > edge_pct:
            return None
        tier, dist = "near", d
    hit = DA.read(px, band, change_pct, pc) if pc is not None else None
    return {"tier": tier, "band": _slim_band(band),
            "role": "broken supply" if _kind(band) == "supply" else "demand",
            "dist_pct": round(dist, 2), "arrival": hit is not None, "hit": hit}


# --------------------------------------------------------------------------
# Keys + messages
# --------------------------------------------------------------------------
def break_state_key(symbol: str, band: dict, day: str, tier: str) -> str:
    return f"{symbol}:{float(band['lo']):g}-{float(band['hi']):g}:{day}:{tier}"


def _band_txt(band: dict) -> str:
    return f"${float(band['lo']):g}–{float(band['hi']):g}"


def _url(sym: str) -> str:
    return f"/sepa/{sym}?tab=supply"


def break_single_message(item: dict) -> dict:
    """near  -> '🚀 SYM 0.4% under resistance $100–102 → new highs'
       broke -> '🚀 SYM broke resistance $100–102 (+1.2%) → new highs'"""
    sym, band, px = item["symbol"], item["band"], float(item["last"])
    dist = float(item["dist_pct"])
    if item["tier"] == "broke":
        title = f"🚀 {sym} broke resistance {_band_txt(band)} (+{abs(dist):.1f}%) → new highs"
    else:
        title = f"🚀 {sym} {dist:g}% under resistance {_band_txt(band)} → new highs"
    parts = [f"${px:g}", f"tested {int(band.get('touches') or 0)}x"]
    if item.get("high_252") is not None and item.get("pct_to_52w") is not None:
        parts.append(f"52w high ${float(item['high_252']):g} ({float(item['pct_to_52w']):+.1f}%)")
    parts.append(DA.fmt_cap(item.get("cap")))
    if item.get("name"):
        parts.append(str(item["name"]))
    url = _url(sym)
    return {"title": title, "body": " · ".join(parts), "url": url, "data": {"url": url},
            "kind": KIND_BREAK}


def _break_rank(item: dict) -> tuple:
    """Broke rows first (furthest through first), then the nearest to the ceiling."""
    return (0 if item["tier"] == "broke" else 1, float(item["dist_pct"]))


def break_digest_message(items: list) -> Optional[dict]:
    """'🚀 Breaking resistance — SYM 0.4% +4 more', one line per name."""
    if not items:
        return None
    items = sorted(items, key=_break_rank)
    lead = items[0]
    ld = float(lead["dist_pct"])
    lead_txt = (f"{lead['symbol']} broke +{abs(ld):.1f}%" if lead["tier"] == "broke"
                else f"{lead['symbol']} {ld:g}%")
    title = f"🚀 Breaking resistance — {lead_txt}"
    if len(items) > 1:
        title += f" +{len(items) - 1} more"
    lines = []
    for it in items[:DIGEST_MAX]:
        d, band = float(it["dist_pct"]), it["band"]
        where = (f"broke {_band_txt(band)} (+{abs(d):.1f}%)" if it["tier"] == "broke"
                 else f"{d:g}% under {_band_txt(band)}")
        lines.append(f"{it['symbol']} ${float(it['last']):g} · {where} · "
                     f"tested {int(band.get('touches') or 0)}x · {DA.fmt_cap(it.get('cap'))}")
    if len(items) > DIGEST_MAX:
        lines.append(f"+{len(items) - DIGEST_MAX} more")
    url = "/chart-maps?tab=deep_demand"
    return {"title": title, "body": "\n".join(lines), "url": url, "data": {"url": url},
            "kind": KIND_BREAK}


# --------------------------------------------------------------------------
# Mongo wiring
# --------------------------------------------------------------------------
def _coll(name: str):
    try:
        from portfolio.store import _get_db
        db = _get_db()
        return db[name] if db is not None else None
    except Exception as exc:
        log.warning("zone_edge: no mongo for %s: %s", name, exc)
        return None


def _existing_keys(coll, keys: list) -> set:
    """The subset of `keys` already recorded in `coll` — ONE $in read per
    pass, never a find_one per candidate (this runs every minute against
    hundreds of listed rows). A read failure returns the empty set: push
    again rather than never, the same choice demand_alerts._already makes."""
    if coll is None or not keys:
        return set()
    try:
        return {str(d["_id"]) for d in coll.find({"_id": {"$in": sorted(set(keys))}}, {"_id": 1})}
    except Exception as exc:
        log.warning("zone_edge: dedupe read failed: %s", exc)
        return set()


def _names_for(symbols: list) -> dict:
    """{SYM: name} for the listed rows in ONE read of the company-name cache.
    sepa.company_names.name_for memoises per process, and this process is
    fresh every minute — per row it is one Mongo round trip per listed name."""
    out: dict = {}
    if not symbols:
        return out
    try:
        from sepa import company_names
        coll = company_names._get_mongo()
        if coll is None:
            return out
        for d in coll.find({"symbol": {"$in": sorted(set(symbols))}}, {"symbol": 1, "name": 1}):
            if d.get("symbol"):
                out[str(d["symbol"])] = d.get("name")
    except Exception as exc:
        log.warning("zone_edge: names read failed: %s", exc)
    return out


def _record_break(coll, item: dict, now: datetime) -> None:
    if coll is None:
        return
    try:
        coll.update_one({"_id": item["key"]}, {"$set": {
            "symbol": item["symbol"], "tier": item["tier"],
            "band": {"lo": item["band"]["lo"], "hi": item["band"]["hi"]},
            "last": item["last"], "dist_pct": item["dist_pct"], "new_highs": item["new_highs"],
            "cap": item.get("cap"), "sent_at": now.isoformat()}}, upsert=True)
    except Exception as exc:
        log.warning("zone_edge: dedupe write failed: %s", exc)


def _terminal(res: Optional[dict]) -> bool:
    """Delivered, or nobody targeted (muted pref / no device) — both mean
    'do not retry today'. A transport failure is retried next pass."""
    res = res or {}
    return (res.get("sent") or 0) > 0 or (res.get("total_targets") or 0) == 0


def _hhmm(ts) -> Optional[str]:
    try:
        if isinstance(ts, datetime):
            t = ts
        else:
            t = datetime.fromisoformat(str(ts))
        if t.tzinfo is not None:
            t = t.astimezone(ET)
        return t.strftime("%H:%M")
    except Exception:
        return None


def write_track(track_coll, rows: list, now: datetime, day: str) -> int:
    """One track row per listed board row. Returns the count written."""
    if track_coll is None or not rows:
        return 0
    docs = [{"symbol": r["symbol"], "date": day, "ts": now.isoformat(), "side": r["side"],
             "tier": r["tier"], "px": r["last"], "dist_pct": r["dist_pct"],
             "band": {"lo": r["band"]["lo"], "hi": r["band"]["hi"]}} for r in rows]
    try:
        track_coll.insert_many(docs)
        return len(docs)
    except Exception as exc:
        log.warning("zone_edge: track write failed: %s", exc)
        return 0


def purge_track(track_coll, day, keep_days: int = TRACK_KEEP_DAYS) -> int:
    """Delete track rows dated before day - keep_days. Returns the count."""
    if track_coll is None:
        return 0
    cutoff = (day - timedelta(days=keep_days)).isoformat()
    try:
        res = track_coll.delete_many({"date": {"$lt": cutoff}})
        return int(getattr(res, "deleted_count", 0) or 0)
    except Exception as exc:
        log.warning("zone_edge: track purge failed: %s", exc)
        return 0


TRACK_INDEX = [("date", 1), ("symbol", 1), ("ts", 1)]


def ensure_track_index(track_coll) -> bool:
    """(date, symbol, ts) on the track coll so read_track / purge_track stay
    index-bound as the day's rows pile up. Idempotent (a no-op round trip
    once it exists); a fake without create_index is fine."""
    if track_coll is None:
        return False
    try:
        track_coll.create_index(TRACK_INDEX, name="date_symbol_ts")
        return True
    except Exception as exc:
        log.debug("zone_edge: track index: %s", exc)
        return False


def read_track(track_coll, day: str, symbols: list, points: int = TRACK_POINTS,
               as_of: Optional[datetime] = None) -> dict:
    """{"supply:SYM": [["HH:MM", dist_pct], ...]} for `day`, restricted to
    `symbols`, chronological, at most `points` per key.

    With `as_of` (the pass clock) only rows stamped within the last `points`
    minutes are read — rows are one per minute per key, so that is the same
    last `points` points for a continuously listed name and a bounded read
    (<= points rows per key) instead of the whole day. ts is stored as an ET
    ISO string with a fixed offset inside a session, so a string $gte is
    chronological. No `as_of` = the whole day, trimmed.
    """
    series: dict = {}
    if track_coll is None or not symbols:
        return series
    q: dict = {"date": day, "symbol": {"$in": sorted(set(symbols))}}
    if as_of is not None:
        try:
            q["ts"] = {"$gte": (as_of - timedelta(minutes=int(points))).isoformat(),
                       "$lte": as_of.isoformat()}
        except Exception:
            pass
    try:
        cur = track_coll.find(q, {"_id": 0, "symbol": 1, "side": 1, "ts": 1, "dist_pct": 1})
        rows = sorted(cur, key=lambda d: str(d.get("ts") or ""))
    except Exception as exc:
        log.warning("zone_edge: track read failed: %s", exc)
        return series
    for d in rows:
        hhmm = _hhmm(d.get("ts"))
        if hhmm is None:
            continue
        side, sym = str(d.get("side") or ""), str(d.get("symbol") or "")
        series.setdefault(f"{side}:{sym}", []).append([hhmm, _f(d.get("dist_pct"))])
    for k in list(series):
        series[k] = series[k][-points:]
    return series


FIRST_SEEN_ID = "first_seen"


def first_seen_key(symbol: str, side: str, band: dict) -> str:
    return f"{symbol}:{side}:{float(band['lo']):g}-{float(band['hi']):g}"


def read_first_seen(latest_coll, day: str) -> dict:
    """{first_seen_key: "HH:MM"} — the first minute each (symbol, side, band)
    was listed on `day`. One find_one on the per-day map doc; a doc from any
    other day is an empty map (the clocks reset daily). Because every listing
    writes a track row, this equals the earliest track row per key without
    re-reading the day's rows every minute."""
    if latest_coll is None:
        return {}
    try:
        doc = latest_coll.find_one({"_id": FIRST_SEEN_ID})
    except Exception as exc:
        log.warning("zone_edge: first_seen read failed: %s", exc)
        return {}
    if not doc or str(doc.get("date") or "") != day:
        return {}
    out: dict = {}
    for e in doc.get("rows") or []:
        try:
            out[str(e[0])] = str(e[1])
        except Exception:
            continue
    return out


def write_first_seen(latest_coll, day: str, first: dict) -> None:
    if latest_coll is None:
        return
    try:
        latest_coll.replace_one({"_id": FIRST_SEEN_ID},
                                {"_id": FIRST_SEEN_ID, "date": day,
                                 "rows": [[k, v] for k, v in sorted(first.items())]},
                                upsert=True)
    except Exception as exc:
        log.warning("zone_edge: first_seen write failed: %s", exc)


# --------------------------------------------------------------------------
# Rows + payload
# --------------------------------------------------------------------------
def _row(sym: str, px: float, side: str, role: str, r: dict, cap, name) -> dict:
    return {"symbol": sym, "name": name, "last": float(px), "dist_pct": float(r["dist_pct"]),
            "tier": r["tier"], "side": side, "role": role, "band": dict(r["band"]),
            "cap": _f(cap), "new_highs": r.get("new_highs"), "high_252": r.get("high_252"),
            "pct_to_52w": r.get("pct_to_52w"), "overhead_bands": r.get("overhead_bands"),
            "arrival": r.get("arrival"), "first_seen": None, "url": _url(sym)}


def _break_row_key(r: dict) -> tuple:
    return (0 if r["tier"] == "broke" else 1, 0 if r.get("new_highs") else 1, float(r["dist_pct"]))


def _demand_row_key(r: dict) -> tuple:
    return (0 if r.get("arrival") else 1, float(r["dist_pct"]))


def sort_rows(breaking: list, near_demand: list) -> tuple:
    """breaking: broke first, then near; within each new_highs first, then
    dist ascending. near_demand: arrivals first, then dist ascending."""
    return sorted(breaking, key=_break_row_key), sorted(near_demand, key=_demand_row_key)


def build_payload(breaking: list, near_demand: list, *, now: datetime, day: str,
                  pass_sec: float, counts: dict) -> dict:
    """The API payload WITHOUT the track (that is attached at read time)."""
    breaking, near_demand = sort_rows(breaking, near_demand)
    counts = dict(counts or {})
    counts["breaking"], counts["near_demand"] = len(breaking), len(near_demand)
    return _clean({
        "as_of": now.astimezone(ET).isoformat(), "date": day, "in_session": in_session(now),
        "pass_sec": round(float(pass_sec), 2),
        "params": {"edge_pct": EDGE_PCT, "broke_max_pct": BROKE_MAX_PCT,
                   "min_cap_usd": MIN_CAP_USD, "min_touches_push": MIN_TOUCHES_PUSH},
        "counts": counts, "breaking": breaking, "near_demand": near_demand,
        "disclaimer": DISCLAIMER})


def empty_payload(reason: str = "no pass yet") -> dict:
    return {"as_of": None, "date": None, "in_session": False, "pass_sec": None,
            "params": {"edge_pct": EDGE_PCT, "broke_max_pct": BROKE_MAX_PCT,
                       "min_cap_usd": MIN_CAP_USD, "min_touches_push": MIN_TOUCHES_PUSH},
            "counts": {"breaking": 0, "near_demand": 0, "candidates": 0, "priced": 0,
                       "stale_print": 0},
            "breaking": [], "near_demand": [], "track": {}, "reason": reason,
            "disclaimer": DISCLAIMER}


def api_payload(*, latest_coll=None, track_coll=None, now: Optional[datetime] = None) -> dict:
    """GET /supply-demand/zone-edge: the last pass + the day's track. in_session
    is evaluated NOW (the stored flag is the pass's own clock)."""
    now = now or _now_et()
    latest_coll = latest_coll if latest_coll is not None else _coll(LATEST_COLL)
    doc = None
    if latest_coll is not None:
        try:
            doc = latest_coll.find_one({"_id": "latest"})
        except Exception as exc:
            log.warning("zone_edge: latest read failed: %s", exc)
    if not doc:
        return empty_payload()
    payload = {k: v for k, v in doc.items() if k != "_id"}
    payload["in_session"] = in_session(now)
    track_coll = track_coll if track_coll is not None else _coll(TRACK_COLL)
    syms = [r["symbol"] for r in (payload.get("breaking") or []) + (payload.get("near_demand") or [])]
    as_of = None
    try:
        as_of = datetime.fromisoformat(str(payload["as_of"])) if payload.get("as_of") else None
    except Exception:
        as_of = None
    payload["track"] = read_track(track_coll, str(payload.get("date") or ""), syms, as_of=as_of)
    return _clean(payload)


# --------------------------------------------------------------------------
# The pass
# --------------------------------------------------------------------------
def check_once(*, push: bool = True, force: bool = False, track: bool = True,
               store: Optional[dict] = None, snapshot: Optional[dict] = None,
               caps: Optional[dict] = None, names: Optional[dict] = None,
               coll_break=None, coll_demand=None, latest_coll=None, track_coll=None,
               owner: Optional[str] = None, now: Optional[datetime] = None) -> dict:
    """One 1-min pass. Every input is injectable for tests; the cron passes
    none. `force` skips the session gate for in-container smoke tests only;
    `track=False` (dry runs) reads the board without writing latest/track."""
    t0 = time.time()
    now = now or _now_et()
    if not force and not in_session(now):
        return {"ran": False, "reason": "outside RTH"}
    day = now.astimezone(ET).date()
    day_iso = day.isoformat()
    if store is None:
        from supply_demand import zone_store
        store = zone_store.load(None, day)
    if not store:
        return {"ran": True, "reason": "zone store empty for today", "candidates": 0,
                "priced": 0, "stale_print": 0, "breaking": [], "near_demand": [],
                "pushed": 0, "seconds": round(time.time() - t0, 2)}
    syms = sorted(store)
    if snapshot is None:
        try:
            from sepa import prices
            snapshot = prices.bulk_snapshot(syms) or {}
        except Exception as exc:
            log.warning("zone_edge: snapshot failed: %s", exc)
            return {"ran": False, "reason": f"snapshot failed: {exc}"}
    if not snapshot:
        log.warning("zone_edge: snapshot returned nothing for %d stored names — a quiet "
                    "pass, not a quiet day", len(syms))
    now_ts = now.timestamp()
    prints: dict = {}
    stale_print = 0
    for s in syms:
        snap = snapshot.get(s)
        if not snap:
            continue
        px, stale = print_from_snapshot(snap, now_ts, STALE_PRINT_SEC)
        if stale:
            stale_print += 1
            continue
        prints[s] = px
    if caps is None:
        try:
            from catalysts.promo_circuit import market_caps_for
            caps = market_caps_for(list(prints), prints) or {}
        except Exception as exc:
            log.warning("zone_edge: market caps failed: %s", exc)
            caps = {}
    if coll_break is None:
        coll_break = _coll(STATE_COLL_BREAK)
    if coll_demand is None:
        coll_demand = _coll(DA.STATE_COLL)
    if latest_coll is None:
        latest_coll = _coll(LATEST_COLL)
    if track_coll is None:
        track_coll = _coll(TRACK_COLL)

    # The loop is pure: reads, no I/O. Names and dedupe state come after it in
    # ONE read each — a find_one per row here is a Mongo round trip per listed
    # name, every minute.
    breaking, near_demand = [], []
    break_cands, demand_cands = [], []
    unknown_cap = skipped_cap = unknown_prev = 0
    for sym in syms:
        px = prints.get(sym)
        if px is None:
            continue
        doc, snap = store[sym], snapshot.get(sym) or {}
        bands = doc.get("bands") or []
        prev = _f(snap.get("prev_day_close")) or _f(doc.get("prev_close"))
        chg = snap.get("change_pct")
        rb = read_breaking(px, bands, prev, doc.get("high_252"))
        rd = read_near_demand(px, bands, chg, prev)
        if rb is None and rd is None:
            continue
        cap = caps.get(sym)
        if _f(cap) is None:
            unknown_cap += 1
            continue                                          # unknown cap: not a known-big name
        if rd is not None and not prev:
            unknown_prev += 1
        cap_ok = DA.passes_cap(cap, MIN_CAP_USD)
        if not cap_ok:
            skipped_cap += 1
        if rb is not None:
            row = _row(sym, px, "supply", "resistance", rb, cap, None)
            breaking.append(row)
            if (cap_ok and rb["new_highs"] and rb["band"]["touches"] >= MIN_TOUCHES_PUSH):
                break_cands.append(dict(row, key=break_state_key(sym, rb["band"], day_iso, rb["tier"])))
        if rd is not None:
            row = _row(sym, px, "demand", rd["role"], rd, cap, None)
            near_demand.append(row)
            if (cap_ok and rd["arrival"] and rd["band"]["touches"] >= MIN_TOUCHES_PUSH):
                demand_cands.append({"symbol": sym, "hit": rd["hit"], "band": rd["band"],
                                     "last": float(px), "cap": _f(cap), "name": None,
                                     "key": DA.state_key(sym, rd["band"], day_iso, "at"),
                                     "tier": rd["tier"], "dist_pct": rd["dist_pct"]})

    # ── names + dedupe: one read each, never per symbol ──────────────────────
    if names is None:
        names = _names_for([r["symbol"] for r in breaking + near_demand])
    for r in breaking + near_demand:
        r["name"] = names.get(r["symbol"])
    seen_break = _existing_keys(coll_break, [it["key"] for it in break_cands])
    seen_demand = _existing_keys(coll_demand, [it["key"] for it in demand_cands])
    break_items = [it for it in break_cands if it["key"] not in seen_break]
    demand_items = [it for it in demand_cands if it["key"] not in seen_demand]
    for it in break_items + demand_items:
        it["name"] = names.get(it["symbol"])

    # ── pushes ──────────────────────────────────────────────────────────────
    break_items.sort(key=_break_rank)
    b_singles, b_digest = break_items[:MAX_SINGLES_PER_PASS], break_items[MAX_SINGLES_PER_PASS:]
    demand_items.sort(key=lambda it: float(it["hit"]["dist_pct"]))
    d_singles, d_digest = demand_items[:MAX_SINGLES_PER_PASS], demand_items[MAX_SINGLES_PER_PASS:]
    pushed = 0
    if push and (break_items or demand_items):
        from push import sender
        if owner is None:
            from portfolio.alerts import _resolve_owner
            owner = _resolve_owner()
        for it in b_singles:
            try:
                res = sender.send_to_user(owner, break_single_message(it), kind=KIND_BREAK)
            except Exception as exc:
                log.warning("zone_edge: break push for %s failed: %s", it["symbol"], exc)
                continue
            if _terminal(res):
                _record_break(coll_break, it, now)
                pushed += 1
        if b_digest:
            try:
                res = sender.send_to_user(owner, break_digest_message(b_digest), kind=KIND_BREAK)
            except Exception as exc:
                log.warning("zone_edge: break digest push failed: %s", exc)
                res = None
            if _terminal(res):
                for it in b_digest:
                    _record_break(coll_break, it, now)
                pushed += 1
        for it in d_singles:
            try:
                res = sender.send_to_user(owner, DA.at_message(it), kind=DA.KIND)
            except Exception as exc:
                log.warning("zone_edge: demand push for %s failed: %s", it["symbol"], exc)
                continue
            if _terminal(res):
                DA._record(coll_demand, it["key"], it, now)
                pushed += 1
        if d_digest:
            try:
                res = sender.send_to_user(owner, DA.digest_message(d_digest), kind=DA.KIND)
            except Exception as exc:
                log.warning("zone_edge: demand digest push failed: %s", exc)
                res = None
            if _terminal(res):
                for it in d_digest:
                    DA._record(coll_demand, it["key"], it, now)
                pushed += 1

    # ── tracking (min on min) ───────────────────────────────────────────────
    breaking, near_demand = sort_rows(breaking, near_demand)
    tracked = purged = 0
    if track:
        ensure_track_index(track_coll)
        tracked = write_track(track_coll, breaking + near_demand, now, day_iso)
        purged = purge_track(track_coll, day)
    # first_seen: the per-day map (one doc), never the day's rows. A dry run
    # (track=False) reads the clocks it finds and starts none.
    first_seen = read_first_seen(latest_coll, day_iso)
    now_hhmm = now.astimezone(ET).strftime("%H:%M")
    for r in breaking + near_demand:
        k = first_seen_key(r["symbol"], r["side"], r["band"])
        if track and k not in first_seen:
            first_seen[k] = now_hhmm
        r["first_seen"] = first_seen.get(k)
    if track:
        write_first_seen(latest_coll, day_iso, first_seen)
    counts = {"candidates": len(syms), "priced": len(prints), "stale_print": stale_print}
    payload = build_payload(breaking, near_demand, now=now, day=day_iso,
                            pass_sec=time.time() - t0, counts=counts)
    if track and latest_coll is not None:
        try:
            latest_coll.replace_one({"_id": "latest"}, dict(payload, _id="latest"), upsert=True)
        except Exception as exc:
            log.warning("zone_edge: latest write failed: %s", exc)
    return {"ran": True, "date": day_iso, "as_of": payload["as_of"], "candidates": len(syms),
            "priced": len(prints), "stale_print": stale_print,
            "breaking": payload["breaking"], "near_demand": payload["near_demand"],
            "singles_break": len(b_singles), "digest_break": len(b_digest),
            "singles_demand": len(d_singles), "digest_demand": len(d_digest),
            "pushed": pushed, "tracked": tracked, "purged": purged,
            "skipped_cap": skipped_cap, "unknown_cap": unknown_cap,
            "unknown_prev": unknown_prev, "seconds": round(time.time() - t0, 2),
            "payload": payload}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    t0 = time.time()
    out = check_once()
    log.info("ZONE-EDGE: ran=%s candidates=%s priced=%s stale_print=%s breaking=%s "
             "near_demand=%s pushed=%s seconds=%.1f", out.get("ran"), out.get("candidates"),
             out.get("priced"), out.get("stale_print"), len(out.get("breaking") or []),
             len(out.get("near_demand") or []), out.get("pushed"), time.time() - t0)
