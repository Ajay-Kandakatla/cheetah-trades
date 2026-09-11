"""Sector rotation API — one read-only endpoint.

Read-only by construction: nothing here starts a scan. The tracker reads the
latest SEPA scan for its sector membership and pulls cached price frames, so a
cold call is seconds, not minutes.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from . import backtest as B
from . import hottest as H
from . import tracker as T

log = logging.getLogger("rotation.api")
router = APIRouter(tags=["rotation"])

# Default window start. Ajay 2026-08-16: "From June this happened."
DEFAULT_START = "2026-06-01"

_CACHE_TTL_SEC = 30 * 60
_cache: dict = {}
_DEFAULT_KEY = (DEFAULT_START, 20_000_000.0, 10.0)


def warm_cache(start: str, data: dict, *, source: str = "live",
               built_at_iso: Optional[str] = None) -> None:
    """Seed the in-process cache for the default key (the scans call this
    after persisting their build, so a smoke run in the API process is warm)."""
    if start == DEFAULT_START and isinstance(data, dict):
        _cache[_DEFAULT_KEY] = {"ts": time.time(), "data": data, "source": source,
                                "built_at_iso": built_at_iso}


def _persisted_hit(key) -> Optional[dict]:
    """2026-09-06 (Ajay: "make ... Hot sectors part of the scans"): the last
    scan's build, when it is fresh enough, replaces a cold on-demand build
    (89 s measured that day). Default key only — the scans build exactly
    that; a custom start still computes on request."""
    if key != _DEFAULT_KEY:
        return None
    try:
        from sepa import context_refresh as MC
        doc = MC.load_doc(MC.ROTATION_ID, max_age_sec=MC.PERSIST_FRESH_SEC)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("rotation: persisted read failed: %s", exc)
        return None
    if not doc:
        return None
    hit = {"ts": time.time(), "data": doc["payload"], "source": "scan",
           "built_at_iso": doc.get("built_at_iso")}
    _cache[key] = hit
    return hit


def _coerce_str(v, fallback: str) -> str:
    """FastAPI resolves Query(...) defaults at REQUEST time, so a direct call
    from a container smoke test receives the Query OBJECT — truthy, with no
    string methods. That bug shipped twice on the demand board; coerce here."""
    return v if isinstance(v, str) and v.strip() else fallback


def _coerce_float(v, fallback: float) -> float:
    return float(v) if isinstance(v, (int, float)) else fallback


def _coerce_int(v, fallback: int) -> int:
    return int(v) if isinstance(v, int) and not isinstance(v, bool) else fallback


def _public(data: dict) -> dict:
    """The /rotation payload WITHOUT the per-member table.

    That table is ~350 KB of per-name rows (2026-09-10) and the rotation page
    reads none of it — it is served one group at a time by /rotation/members.
    Shipping it on every /rotation call would be seven times the payload for a
    popover nobody has opened yet. The index says it exists and where to get
    it; nothing already on the page changes.
    """
    out = {k: v for k, v in (data or {}).items() if k != T.MEMBERS_KEY}
    table = (data or {}).get(T.MEMBERS_KEY) or {}
    out["members_index"] = {
        "available": bool(table.get("by_symbol")),
        "symbols": len(table.get("by_symbol") or {}),
        "grains": [g for g in T.MEMBER_GRAINS if (table.get("groups") or {}).get(g)],
        "endpoint": "/rotation/members?grain=<grain>&group=<name>",
    }
    return out


@router.get("/rotation")
async def rotation(
    start: str = Query(DEFAULT_START, description="ISO date the window opens on"),
    min_dollar_vol: float = Query(20_000_000.0, ge=0,
                                  description="liquidity floor for sector members"),
    min_price: float = Query(10.0, ge=0, description="price floor for sector members"),
    refresh: bool = Query(False, description="bypass the 30-minute cache"),
):
    """Where money left and where it went, relative to equal-weight.

    Returns sectors, Ajay's build-out themes, and safe-haven proxies, each with
    the window return, 21-day and 63-day, all restated relative to RSP.
    """
    s = _coerce_str(start, DEFAULT_START)
    dv = _coerce_float(min_dollar_vol, 20_000_000.0)
    px = _coerce_float(min_price, 10.0)
    key = (s, dv, px)

    if not (refresh is True):
        hit = _cache.get(key)
        if hit and (time.time() - hit["ts"]) < _CACHE_TTL_SEC:
            return JSONResponse({**_public(hit["data"]), "cached": True,
                                 "source": hit.get("source", "live"),
                                 "built_at_iso": hit.get("built_at_iso")})
        hit = _persisted_hit(key)
        if hit:
            return JSONResponse({**_public(hit["data"]), "cached": True, "source": "scan",
                                 "built_at_iso": hit.get("built_at_iso")})

    try:
        data = T.build(start=s, min_dollar_vol=dv, min_price=px)
    except Exception as exc:
        log.warning("rotation: build failed: %s", exc)
        return JSONResponse(
            {"error": f"{type(exc).__name__}: {exc}"[:200], "sectors": [],
             "themes": [], "havens": [], "start": s},
            status_code=503)

    _cache[key] = {"ts": time.time(), "data": data, "source": "live", "built_at_iso": None}
    return JSONResponse({**_public(data), "cached": False, "source": "live",
                         "built_at_iso": None})


@router.get("/rotation/hot")
async def rotation_hot(refresh: bool = Query(False)):
    """The hot ends only — for the strip on Chart Maps and the Market Gauge.

    Ajay 2026-08-31: "make sure this scan you did today to be on top of the
    chart maps or some section where it says Hot sectors" + "I need this
    component market guage tab too". Same 30-minute cache as /rotation (same
    key), a fraction of the payload: the two pages poll this on every visit,
    and shipping them the full member tables would be weight without signal.
    """
    key = _DEFAULT_KEY
    hit = _cache.get(key)
    if not (refresh is True) and (not hit or (time.time() - hit["ts"]) >= _CACHE_TTL_SEC):
        hit = _persisted_hit(key) or hit      # the last scan's build, if fresh enough
    if (refresh is True) or not hit or (time.time() - hit["ts"]) >= _CACHE_TTL_SEC:
        try:
            data = T.build(start=DEFAULT_START)
        except Exception as exc:
            log.warning("rotation: hot build failed: %s", exc)
            return JSONResponse({"error": f"{type(exc).__name__}: {exc}"[:200]},
                                status_code=503)
        _cache[key] = {"ts": time.time(), "data": data, "source": "live", "built_at_iso": None}
        hit = _cache[key]

    d = hit["data"]

    # Each chip carries the GRAIN its member table lives under (2026-09-10), so
    # the popover asks /rotation/members with a key the backend handed it
    # instead of inferring one from which list the chip came out of. The strip's
    # money-in/out chips are cap-tier cohorts, not bare sectors — an inferred
    # mapping would have got exactly that wrong.
    # The SHORT legs ride on every chip (Ajay 2026-09-10: "what ever today is
    # what I wanna see in green but keep the other days too ... May be just
    # keep 5days and today"). Adding keys only — the 21d/63d/window legs stay
    # exactly where the strip already reads them, they just stop being the
    # only thing it can colour on.
    _SHORT = ("rel_1d", "rel_5d", "pct_positive_1d")

    def _slim(r):
        return dict({k: r.get(k) for k in
                     ("group", "sector", "tier", "index", "n", "rel_21d",
                      "rel_window", "rel_63d", "pct_positive") + _SHORT},
                    grain="cohort")

    def _slim_thm(r):
        return dict({k: r.get(k) for k in
                     ("group", "n", "rel_21d", "rel_window", "rel_63d",
                      "pct_positive", "thin") + _SHORT}, grain="theme")

    def _slim_ind(r):
        return dict({k: r.get(k) for k in
                     ("group", "sector", "industry", "n", "rel_21d", "rel_window",
                      "rel_63d", "pct_positive") + _SHORT}, grain="industry")

    hot = d.get("hot") or {}
    return JSONResponse({
        "as_of": d.get("as_of"),
        "start": d.get("start"),
        "benchmark": (d.get("benchmark") or {}).get("symbol"),
        "in": [_slim(r) for r in (hot.get("in") or [])],
        "out": [_slim(r) for r in (hot.get("out") or [])],
        "ranked_by": hot.get("ranked_by"),
        # One grain finer (Ajay 2026-09-09: "increase our sectors ... money got
        # moved in to technology too from Semis"). A semis rotation is invisible
        # in the Technology row and obvious here — 2026-09-09: Semiconductors
        # rel_63d -13.3 against Software-Infrastructure +19.1, inside one sector.
        "industries_in": [_slim_ind(r) for r in ((d.get("hot_industries") or {}).get("in") or [])],
        "industries_out": [_slim_ind(r) for r in ((d.get("hot_industries") or {}).get("out") or [])],
        # His own build-out rosters — robotics, energy, optical, nuclear,
        # rare_earth, datacenter_build and the AI complex. Computed since the
        # tracker was written and never once shown, which is why he asked for
        # things the app was already tracking (2026-09-09).
        "themes_in": [_slim_thm(r) for r in ((d.get("hot_themes") or {}).get("in") or [])],
        "themes_out": [_slim_thm(r) for r in ((d.get("hot_themes") or {}).get("out") or [])],
        "stance": d.get("stance"),
        "note": d.get("note"),
        # Ajay 2026-09-10: "when there are none hot that day it helps to know
        # overall market it red." The whole-tape read the build already
        # computes, served HERE so the strip prints it without a second round
        # trip — on a day when 9 of 11 sectors are red, "nothing is hot" and
        # "everything is red" are different sentences and he wants the second
        # one. None when the persisted build predates the key: the strip must
        # show no market line rather than a made-up one.
        "market": d.get("market"),
        # Whether the persisted build carries a member table at all — a doc
        # written before 2026-09-10 does not, and the popover must know that
        # before it offers a click that can only answer "nothing here".
        "members_available": bool(((d.get(T.MEMBERS_KEY) or {}).get("by_symbol"))),
        "cached": bool(time.time() - hit["ts"] > 1) or hit.get("source") == "scan",
        # 2026-09-06: "scan" = the last scan's persisted build (stamped), "live"
        # = built on request; the strip prints the scan clock.
        "source": hit.get("source", "live"),
        "built_at_iso": hit.get("built_at_iso"),
    })


# ── The popover's member table ───────────────────────────────────────────────
# Ajay 2026-09-10: "I would like to click on the sector category and see the
# related stocks list in a pop over to see which ones are gaining traction."
#
# READ-ONLY, and that is the entire design constraint. A cold T.build() measured
# 41 s on 2026-09-10 BEFORE this table existed; hanging a popover click on that
# is not a slow page, it is a broken one. Nothing below can start a build.
_MEMBERS_TTL_SEC = 5 * 60
_members_cache: dict = {}


def _members_payload() -> dict:
    """The whole persisted rotation payload, not just its member table.

    The Hottest board needs the SHIPPED group rows (`sectors`, `industries`,
    `sampled`, `market`) so it reuses the strip's numbers verbatim instead of
    computing a second definition of how hot a sector is. Same doc and same
    never-build rule as `_members_table`; returns {} rather than raising, so a
    Mongo blip costs the group legs, never the board.
    """
    try:
        from sepa import context_refresh as MC
        return (MC.load_doc(MC.ROTATION_ID) or {}).get("payload") or {}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("rotation: payload read failed: %s", exc)
        return {}


def _scrub(o):
    """NaN / inf -> None, recursively. FastAPI serialises NaN as a bare `NaN`
    token, which is not JSON: the frontend's JSON.parse throws and the board
    renders as a spinner that never resolves (the stuck-Scanning bug, 2026-05-29).
    """
    if isinstance(o, float):
        return None if (o != o or o in (float("inf"), float("-inf"))) else o
    if isinstance(o, dict):
        return {k: _scrub(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_scrub(v) for v in o]
    return o


def _members_table() -> tuple:
    """(table, meta), or (None, meta carrying `reason`). NEVER builds.

    Reads, in order:

      1. this worker's `_cache` — warm only when the process already served
         /rotation, or when a scan in this process called `warm_cache`;
      2. the PERSISTED scan doc (`scan_context` `_id: rotation`), held for
         `_MEMBERS_TTL_SEC` in a cache of its own.

    Step 2 is the one that carries the feature. `_cache` is per uvicorn worker,
    so the worker answering the click is usually not the worker that built
    anything — everything this endpoint needs has to come off the Mongo doc.

    That doc is read with NO freshness cut and deliberately NOT written into
    `_cache`: /rotation and /rotation/hot keep their own 20-hour rule, and a
    read for the popover must never widen it for them. A day-old member table
    is worth showing WITH its age, so `age_sec` / `built_at_iso` / `stale` ride
    in the payload and the popover can print it.
    """
    hit = _cache.get(_DEFAULT_KEY) or {}
    table = (hit.get("data") or {}).get(T.MEMBERS_KEY)
    if isinstance(table, dict) and table.get("by_symbol"):
        return table, {"source": hit.get("source", "live"),
                       "built_at_iso": hit.get("built_at_iso"),
                       "age_sec": round(time.time() - float(hit.get("ts") or 0), 1),
                       "stale": False}

    entry = _members_cache.get("v")
    if not entry or (time.time() - entry["ts"]) >= _MEMBERS_TTL_SEC:
        try:
            from sepa import context_refresh as MC
            doc = MC.load_doc(MC.ROTATION_ID) or {}
            entry = {"ts": time.time(), "table": (doc.get("payload") or {}).get(T.MEMBERS_KEY),
                     "built_at": float(doc.get("built_at") or 0.0),
                     "built_at_iso": doc.get("built_at_iso"),
                     "fresh_sec": float(MC.PERSIST_FRESH_SEC)}
        except Exception as exc:                               # noqa: BLE001
            log.warning("rotation: member table read failed: %s", exc)
            return None, {"reason": "persisted rotation build unreadable: %s"
                                    % type(exc).__name__}
        # A MISS is never cached: a Mongo blip must not blank the popover for
        # the next five minutes when the doc is sitting right there.
        if entry.get("table"):
            _members_cache["v"] = entry

    table = entry.get("table")
    if not entry.get("built_at"):
        return None, {"reason": "no persisted rotation build yet — the member "
                                "table is written by the scan's context refresh"}
    if not isinstance(table, dict) or not table.get("by_symbol"):
        return None, {"reason": "the persisted rotation build predates the "
                                "member table; it appears after the next scan"}
    age = time.time() - entry["built_at"]
    return table, {"source": "scan", "built_at_iso": entry.get("built_at_iso"),
                   "age_sec": round(age, 1), "stale": age > entry["fresh_sec"]}


@router.get("/rotation/members")
async def rotation_members(
    grain: str = Query("", description="sector | cohort | industry | theme"),
    kind: str = Query("", description="alias for `grain` — the spelling the popover sends"),
    group: str = Query("", description="group label, exactly as the strip prints it"),
    sector: str = Query("", description="optional cross-check: the sector the clicked chip carried"),
    tier: str = Query("", description="optional cross-check: the cap tier the clicked chip carried"),
    limit: int = Query(0, ge=0, le=2000, description="0 = every member"),
):
    """The names inside one hot group, ranked by who is gaining traction.

    `traction` is the tracker's, not the page's — the formula, its two
    thresholds and the sort order ship in every response (`traction`), so the
    popover renders a number the backend owns instead of inventing a second
    definition of "gaining".

    The rows are the FULL liquidity-filtered membership. The median printed
    above them on the strip is measured on the rotation grid's fixed sample of
    the same group, so `median_note` says that in one line and
    `median_21d_full` gives this table's own. Two populations, side by side.

    A group nobody could price still answers with its counts (`priced`,
    `unpriced`, `unpriced_symbols`) rather than an empty list that reads like
    an empty sector. A missing build answers 200 with `reason`.

    `kind` is accepted as an alias for `grain` because that is the spelling the
    popover sends. FastAPI IGNORES an unknown query key, so a mismatch would
    NOT error — it would silently answer about the DEFAULT grain, i.e. a
    different group that happens to share a label. Reading both spellings is
    four characters; the failure it prevents is a wrong table under a right
    heading.
    """
    g = (_coerce_str(grain, "") or _coerce_str(kind, "") or "sector").strip()
    name = _coerce_str(group, "").strip()
    cap = _coerce_int(limit, 0)

    def _empty(reason: str, status: int = 200, meta: Optional[dict] = None, **extra):
        body = {k: v for k, v in (meta or {}).items() if k != "reason"}
        body.update({"grain": g, "group": name, "rows": [], "n": 0, "shown": 0,
                     "gaining": 0, "reason": reason,
                     "traction": T.TRACTION_SPEC, "note": T.MEMBER_NOTE})
        body.update(extra)
        return JSONResponse(body, status_code=status)

    if g not in T.MEMBER_GRAINS:
        return _empty("unknown grain", status=400, grains=list(T.MEMBER_GRAINS))
    if not name:
        return _empty("no group asked for", status=400, grains=list(T.MEMBER_GRAINS))

    table, meta = _members_table()
    if table is None:
        return _empty(meta.get("reason") or "member table unavailable", meta=meta)

    grp = ((table.get("groups") or {}).get(g) or {}).get(name)
    if grp is None:
        known = sorted((table.get("groups") or {}).get(g) or {})
        return _empty("this build has no member table for that %s" % g, meta=meta,
                      known_groups=known[:40], known_count=len(known))

    by_symbol = table.get("by_symbol") or {}
    bench = table.get("benchmark") or {}
    median = grp.get("median_21d")
    rows = [T.traction_row(s, by_symbol.get(s), median, bench)
            for s in (grp.get("symbols") or [])]
    rows.sort(key=T.traction_sort_key)
    shown = rows[:cap] if cap else rows

    # `sector` / `tier` ride along from the clicked chip so a cohort resolves
    # without re-parsing " · large caps" out of a display label. They are
    # REDUNDANT — the label already encodes both — so they are spent as a
    # guard: a disagreement means the strip and this build are describing
    # different groups under one name. Answered anyway (the label is the key),
    # said out loud rather than swallowed.
    mismatch = {k: {"asked": want, "build": got} for k, want, got in
                (("sector", _coerce_str(sector, "").strip(), grp.get("sector")),
                 ("tier", _coerce_str(tier, "").strip(), grp.get("tier")))
                if want and got and want != got}
    if mismatch:
        log.warning("rotation/members: %s %r cross-check mismatch %s", g, name, mismatch)

    n_measured, n_full = grp.get("n_measured"), grp.get("n_full")
    # Was a STRIDE actually applied? Compare the published row's population
    # (priced + dropped) with the full membership -- not its survivor count,
    # which drops on a dead series and would fake a sample. Themes are built
    # from the whole roster and must therefore never say "sample".
    n_pop = grp.get("n_population")
    sampled = bool(n_pop and n_full and n_pop < n_full)
    # The one short line the popover prints under the group median. It says the
    # two numbers come from two populations; it does NOT reconcile them.
    median_note = (
        "Median above = the rotation grid's %s-name sample · this table = all "
        "%s members (its own 21d median %s%%)"
        % (n_pop, n_full, grp.get("median_21d_full"))
        if sampled else
        "Median above and this table are the same %s members" % n_full)

    body = {
        "grain": g, "group": name,
        "sector": grp.get("sector"), "tier": grp.get("tier"),
        "industry": grp.get("industry"),
        "as_of": table.get("as_of"), "windows": table.get("windows"),
        # rel_* on every row is rebased against this (decision 1) — the same
        # benchmark the chip above the popover is quoted against.
        "benchmark": bench.get("symbol"), "benchmark_returns": bench,
        "source": meta.get("source"), "built_at_iso": meta.get("built_at_iso"),
        "age_sec": meta.get("age_sec"), "stale": meta.get("stale"),
        "traction": table.get("traction") or T.TRACTION_SPEC,
        "median_21d": median, "median_21d_full": grp.get("median_21d_full"),
        # SAME DAY (Ajay 2026-09-10). The group's median move TODAY over the
        # same full membership as the rows, and how many of them are green.
        # A read, never a gate -- one session does not feed `traction`.
        "median_1d_full": grp.get("median_1d_full"),
        "up_today": grp.get("up_today"),
        "n_measured": n_measured, "n_full": n_full, "sampled": sampled,
        "n_population": n_pop,
        "median_note": median_note,
        # Fail closed and COUNT what was dropped — a group whose names could not
        # be priced must never look like a group with no names.
        "priced": grp.get("priced"), "unpriced": grp.get("unpriced"),
        "unpriced_symbols": grp.get("unpriced_symbols"),
        # Demand-zone context, not a gate: `zone_unmarked` is how many of these
        # names the zone store simply has no doc for.
        "at_demand": grp.get("at_demand"), "zone_unmarked": grp.get("zone_unmarked"),
        "zone": table.get("zone"),
        "gaining": sum(1 for r in rows if r.get("gaining")),
        "n": len(rows), "shown": len(shown), "rows": shown,
        "note": table.get("note") or T.MEMBER_NOTE,
    }
    if mismatch:
        body["cross_check_mismatch"] = mismatch
    if not rows:
        body["reason"] = ("none of the %s members could be priced (%s dropped "
                          "as dead or unpriceable)" % (n_full, grp.get("unpriced")))
    return JSONResponse(body)


# The backtest is a ~5s full-history refetch, so it is cached hard. The answer
# moves on the scale of months, not minutes.
_BT_TTL_SEC = 12 * 60 * 60
_bt_cache: dict = {}


@router.get("/rotation/hottest")
async def rotation_hottest(
    sort: str = Query(H.DEFAULT_SORT, description="rel_1d | rel_5d | rel_21d | traction"),
    names: int = Query(H.NAMES_PER_GROUP, ge=1, le=200,
                       description="names returned per sector/industry"),
):
    """The 🔥 Hottest tab: every sector ranked, each opening into its
    industries and then its names, with the sales block on every row.

    ALL ELEVEN sectors answer, not just the hot end — deliberately. His own
    example is a strong name in a COLD sector (ANDE is 2nd of Consumer
    Defensive's 76 on 21 days while the sector itself is 8th of 11), so a
    board that lists only hot sectors structurally cannot find it.

    Group heat is the SHIPPED sampled median, reused verbatim so this can never
    disagree with the Hot-sectors strip. Name rows are the FULL membership.
    Both bases ride in the payload (`basis`) rather than being blended.
    """
    table, meta = _members_table()
    if table is None:
        return JSONResponse({"sectors": [], "reason": meta.get("reason") or "member table unavailable",
                             "sorted_by": sort, **meta}, status_code=200)
    payload = dict(_members_payload() or {})
    payload[T.MEMBERS_KEY] = table
    body = H.build_live(payload, sort=_coerce_str(sort, H.DEFAULT_SORT),
                        names_per_group=_coerce_int(names, H.NAMES_PER_GROUP))
    body.update({k: v for k, v in meta.items() if k in ("source", "built_at_iso", "age_sec", "stale")})
    return JSONResponse(_scrub(body))


@router.get("/rotation/backtest")
async def rotation_backtest(refresh: bool = Query(False)):
    """Does rotating into the leading sectors actually pay?

    Measured 2026-08-16 over 116 monthly rebalances back to 2016: top-3 rotation
    158.22%, RSP 155.42%, holding all 11 sectors 163.23%. Mean excess -0.013%
    per period with a 95% interval of [-0.549, +0.522].

    Served next to the tracker on purpose. The tracker describes what already
    moved; this is the evidence that acting on that description does not beat
    owning the market, so the page can say so rather than implying a signal it
    does not have.
    """
    hit = _bt_cache.get("v")
    if hit and not (refresh is True) and (time.time() - hit["ts"]) < _BT_TTL_SEC:
        return JSONResponse({**hit["data"], "cached": True})
    try:
        data = B.run()
        # Per-period rows are debugging detail and dominate the payload; the
        # page reads the summary and the year table.
        data.pop("periods", None)
    except Exception as exc:
        log.warning("rotation: backtest failed: %s", exc)
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"[:200]},
                            status_code=503)
    _bt_cache["v"] = {"ts": time.time(), "data": data}
    return JSONResponse({**data, "cached": False})
