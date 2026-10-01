"""🔑 Key Levels tab on Chart Maps (Ajay 2026-09-28).

The ask, verbatim: "Also create me tab for keylevel main. Sort them by stocks
that are near lower keylevels".

Every name in the full scan universe whose print sits above — or within the
`PIERCE_PCT` break buffer of — a LOWER key level not yet broken (the prior-week
low, prior-month low or 52-week low the daily cards already draw), ordered by
the % from the print down to the NEAREST such level, closest first. A tie goes
to the longer period, then the symbol.

ONE ENGINE. Every level, side, state, anchor and distance comes from
`supply_demand.key_levels` (the frozen half of `tile_block`, the member state,
the anchor, the break buffer); the 50-bar turnover from the house
`avg_dollar_vol` (the boards' liquidity-floor input). This module only
memoises the frozen half and counts.

THE MEMO. Levels are frozen per session (they roll at 20:00), so the closed-bar
half is built ONCE per `levels_session` in a background thread (the
demand_reentry `cached_or_warm` pattern) and every request ranks it against ONE
universe `bulk_snapshot`. `MEMO_TTL_SEC` is cache freshness only — it heals a
daily bar patched after the memo was built — never a rule.

WRITES NOTHING: no Mongo, no file. UNMEASURED: no study in this app says a
stock near a key low holds or turns there; the order is a distance, not a
ranking of setups, and nothing gates, pushes, sizes or enters on it.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime
from typing import Optional

from supply_demand import key_levels as KL

log = logging.getLogger("chart_maps.key_levels_tab")

MEMO_TTL_SEC = 60 * 60          # cache freshness, NOT a rule
DRAW_PER_SIDE = KL.SUPPORT_PER_SIDE
DEFAULT_SORT_LABEL = "🔑 Closest to a key low first"

_memo: dict = {}                # (session_iso, ukey) -> entry
_warming: set = set()
_lock = threading.Lock()

_LOW_LABELS = [KL.LABELS[(p, k)] for p in KL.BOARD_PERIODS for k in KL.BOARD_KINDS]
LOWS = " / ".join(_LOW_LABELS)


def _join_or(items: list) -> str:
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " or " + items[-1]


NAMES = _join_or([KL.NAMES[lab] for lab in _LOW_LABELS])
BUF = f"{KL.PIERCE_PCT:g}%"


def buf_text() -> str:
    """The break buffer in words (🧱 2026-09-30): with the pad on a support LOW
    breaks only PIERCE_PCT beyond its level_pad pad, so the header says both —
    built from level_pad (through key_levels) and PIERCE_PCT, never typed."""
    p = KL.LP.pad_pct()
    if p <= 0:
        return f"the {BUF} break buffer"
    return f"the {p:g}% pad plus the {BUF} break buffer"

NOTE = (f"{KL.MARK} UNMEASURED — no study in this app says a stock near its {NAMES} "
        "holds there or turns there. The order is a distance, not a ranking of setups; "
        "nothing here gates a scan, pushes a phone, sizes a position or enters a lane.")
WARMING_NOTE = (f"{KL.MARK} Reading every name's {NAMES} from the cached daily bars — "
                "the charts appear here as soon as it lands; you don't need to refresh.")
EMPTY_NOTE = (f"{KL.MARK} No name sits above a {LOWS} not yet broken right now — "
              "the line above says where they went.")

_BASIS = {None: "last close", "pre": "pre-market print", "rth": "live print",
          "close": "after-hours print"}

COUNT_KEYS = ("scanned", "ranked", "broken", "no_level", "stale", "no_print",
              "set_last_session")


def session_for(now: datetime) -> date:
    """`key_levels.levels_session` — re-exported so a script reaches it
    without importing the engine (the display-only import guard)."""
    return KL.levels_session(now)


def _ukey(universe) -> str:
    try:
        from supply_demand import demand_reentry as D
        return D._universe_key(universe)
    except Exception:                                           # noqa: BLE001
        return "full"


# ---------------------------------------------------------------------------
# build — the frozen, closed-bar half, once per session
# ---------------------------------------------------------------------------
def build(universe: str, session: date, *, universe_fn=None, frames_fn=None) -> dict:
    """entry = {syms, levels: {SYM: {levels, ref_close, last_date, stale_note,
    avg_dollar_vol_50, last_bar: {member_id: read}}}, built_ts, built_at,
    session, ukey}. ONE cached-frames read; ONE closed-frame cut per name
    (levels, turnover and the last-bar read on CLOSED bars only)."""
    from supply_demand import quick_bounce as QB
    ukey = _ukey(universe)
    if universe_fn is None:
        from supply_demand import demand_reentry as D
        syms_raw = D._resolve_universe(ukey)[0]
    else:
        syms_raw = universe_fn(ukey)
    syms: list = []
    seen: set = set()
    for s in syms_raw or []:
        s = str(s or "").strip().upper()
        if s and s not in seen:
            seen.add(s)
            syms.append(s)
    if frames_fn is None:
        from sepa import prices
        frames_fn = prices.bulk_cached_frames
    frames = frames_fn(syms) or {}
    if syms and not frames:
        # `bulk_cached_frames` answers {} when Mongo is down or the read throws.
        # Memoising that would serve "every name has daily bars behind" for
        # MEMO_TTL_SEC; raising lets `_warm` log it and the next poll retry.
        raise RuntimeError(f"key levels tab: the price-cache read returned no frames for "
                           f"{len(syms):,} names — not memoising an empty read")
    levels: dict = {}
    for sym in syms:
        df = frames.get(sym)
        if df is None:
            levels[sym] = {**KL.closed_levels(sym, None, frame="daily", session=session),
                           "avg_dollar_vol_50": None, "last_bar": {}}
            continue
        try:
            closed = KL.closed_frame(df, session)
            cl = KL.closed_levels(sym, df, frame="daily", session=session, closed=closed)
            has_bars = closed is not None and len(closed) > 0
            adv = QB.avg_dollar_vol(closed) if has_bars else None
            last_bar = {}
            for m in cl["levels"]:
                if m.get("kind") in KL.BOARD_KINDS:
                    r = KL.last_bar_read(m, closed)
                    if r is not None:
                        last_bar[m["id"]] = r
            levels[sym] = {**cl, "avg_dollar_vol_50": adv, "last_bar": last_bar}
        except Exception as exc:                                # noqa: BLE001
            log.debug("key levels tab: %s build failed: %s", sym, exc)
    now_ts = time.time()
    return {"syms": syms, "levels": levels, "built_ts": now_ts,
            "built_at": datetime.fromtimestamp(now_ts, tz=KL.ET).isoformat(timespec="seconds"),
            "session": session.isoformat(), "ukey": ukey}


def _spawn(target, name: str) -> None:
    threading.Thread(target=target, name=name, daemon=True).start()


def _warm(key: tuple, universe: str, session: date) -> None:
    def _work():
        try:
            entry = build(universe, session)
            with _lock:
                newest = max((k[0] for k in _memo), default=key[0])
                if key[0] < newest:
                    # a late rebuild of a session that has already rolled: never
                    # store it, never let its cleanup evict the newer entry
                    log.info("key levels tab: dropped a late %s build (memo holds %s)",
                             key[0], newest)
                    return
                for k in [k for k in _memo if k[0] < key[0]]:
                    _memo.pop(k, None)                          # an OLDER session's entry
                _memo[key] = entry
        except Exception as exc:                                # noqa: BLE001
            log.warning("key levels tab: build failed for %s: %s", key, exc)
        finally:
            with _lock:
                _warming.discard(key)

    with _lock:
        if key in _warming:
            return
        _warming.add(key)
    _spawn(_work, f"key-levels-tab-{key[0]}-{key[1]}")


def cached_or_warm(universe, *, now: datetime, sync: bool = False) -> dict:
    """{"state": "ready"|"warming", "entry"}. Key = (levels_session(now), ukey).
    Fresh -> ready. Older than MEMO_TTL_SEC -> ready with the OLD entry and ONE
    background rebuild. None for this session -> ONE background build, warming.
    `sync=True` builds inline (tests)."""
    session = KL.levels_session(now)
    ukey = _ukey(universe)
    key = (session.isoformat(), ukey)
    with _lock:
        entry = _memo.get(key)
    fresh = entry is not None and (time.time() - float(entry.get("built_ts") or 0)) < MEMO_TTL_SEC
    if fresh:
        return {"state": "ready", "entry": entry}
    if sync:
        entry = build(ukey, session)
        with _lock:
            _memo[key] = entry
        return {"state": "ready", "entry": entry}
    _warm(key, ukey, session)
    if entry is not None:
        return {"state": "ready", "entry": entry}
    return {"state": "warming", "entry": None}


# ---------------------------------------------------------------------------
# rank — per request, against ONE snapshot map
# ---------------------------------------------------------------------------
def rank_key(r) -> tuple:
    return (abs(r["near"]["distance_pct"]), -KL.PERIOD_RANK[r["near"]["period"]], r["symbol"])


def rank(entry: dict, raw_snaps: dict, *, now: datetime, first_seen: dict) -> tuple:
    """(ranked rows, counts). PURE given its inputs. First match wins, in
    EVERY phase: no levels / stale by date / no ref_close -> stale; no
    snapshot row -> no_print; verify mismatch -> stale; unverifiable row ->
    no_print; no anchor -> no_print; then the nearest lower level: broken /
    no_level / ranked. scanned == ranked + broken + no_level + stale + no_print."""
    now_et = KL._et(now)
    session = date.fromisoformat(str(entry["session"]))
    ph = KL.phase(now_et, session)
    raw_snaps = raw_snaps if isinstance(raw_snaps, dict) else {}
    counts = {k: 0 for k in COUNT_KEYS}
    ranked: list = []
    for sym in entry.get("syms") or []:
        counts["scanned"] += 1
        lv = (entry.get("levels") or {}).get(sym)
        if not lv or lv.get("stale_note") or lv.get("ref_close") is None:
            counts["stale"] += 1
            continue
        row = KL.row_or_none(raw_snaps.get(sym))
        if row is None:
            counts["no_print"] += 1
            continue
        ref_close = lv["ref_close"]
        sentence, verified = KL.verify_last(ref_close, lv.get("last_date"), row)
        if sentence:
            counts["stale"] += 1
            continue
        if not verified:
            counts["no_print"] += 1
            continue
        px, basis, tape = KL.anchor_read(row, now_et, session, ref_close)
        if px is None:
            counts["no_print"] += 1
            continue
        lows = [m for m in lv.get("levels") or []
                if m.get("kind") in KL.BOARD_KINDS and m.get("period") in KL.BOARD_PERIODS]
        read = KL.read_levels(lows, symbol=sym, ref_close=ref_close, row=row, now=now_et,
                              session=session, first_seen=first_seen)
        nl = KL.nearest_lower(read, px)
        if nl["status"] == "broken":
            counts["broken"] += 1
            continue
        if nl["status"] != "ranked":
            counts["no_level"] += 1
            continue
        near = KL.near_block(nl, px=px, basis=basis, tape=tape, ph=ph,
                             last_date=lv.get("last_date"),
                             last_bar=(lv.get("last_bar") or {}).get(nl["nearest"]["id"]))
        counts["ranked"] += 1
        counts["set_last_session"] += int(bool(near["set_last_session"]))
        ranked.append({"symbol": sym, "ref_close": ref_close,
                       "avg_dollar_vol_50": lv.get("avg_dollar_vol_50"), "near": near})
    ranked.sort(key=rank_key)
    return ranked, counts


# ---------------------------------------------------------------------------
# words — every name and number from the engine's constants
# ---------------------------------------------------------------------------
def _n(x) -> str:
    return f"{int(x or 0):,}"


def header_text(counts: dict, *, ph, sort_label=None, themes_first: bool = False) -> str:
    c = counts or {}
    basis = _BASIS.get(ph, _BASIS[None])
    order = ("closest first" if not sort_label
             else f"ordered by {sort_label} (your pick), closest first breaks ties")
    lead = " — theme names lead (themes box)" if themes_first else ""
    return (f"{KL.MARK} {_n(c.get('ranked'))} names sit above, or within {buf_text()} "
            f"of, a {LOWS} not yet broken — {order}, by % from the {basis} down to "
            f"the nearest one{lead}. {_n(c.get('set_last_session'))} of them sit on a low made "
            f"in the last session (flagged on the card). Not listed: {_n(c.get('broken'))} "
            f"through every low below them, {_n(c.get('no_level'))} with no low below the "
            f"price, {_n(c.get('stale'))} with daily bars behind, {_n(c.get('no_print'))} with "
            f"no snapshot print to check their bars against. {_n(c.get('dropped_thin'))} under "
            f"the liquidity floor, {_n(c.get('no_turnover'))} with no turnover to check; "
            f"showing {_n(c.get('shown'))}.")


def ready_block(counts: dict, *, now: datetime, session: date, ph, sort_label,
                themes_first: bool, built_at) -> dict:
    return {"state": "ready", "session": session.isoformat(), "phase": ph,
            "periods": list(_LOW_LABELS), "counts": dict(counts),
            "header": header_text(counts, ph=ph, sort_label=sort_label,
                                  themes_first=themes_first),
            "note": NOTE, "built_at": None if built_at is None else str(built_at),
            "measured": KL.MEASURED}


def warming_block(*, now: datetime) -> dict:
    session = session_for(now)
    return {"state": "warming", "session": session.isoformat(),
            "phase": KL.phase(now, session), "periods": list(_LOW_LABELS),
            "counts": None, "header": WARMING_NOTE, "note": NOTE, "built_at": None,
            "measured": KL.MEASURED}
