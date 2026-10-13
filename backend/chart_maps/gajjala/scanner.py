"""Gajjala's scanner over ONE whole-market snapshot (spec §3.1.1–3.1.3).

His three numbers, verbatim (GG S8 19:12–19:51): price in the band, at least 1 million shares today, up at least 25%
on the prior regular close — plus Ajay's round-A instrument rule (common stock + ADRs; a symbol the reference map does
not know yet is listed as "type unknown"). Long only; nothing here ranks, gates on, or imports any other board.

`scan_rows` is PURE (rows in, a dict out). The I/O around it is spelled out beside it: the split hold-out
(`record_scan`), the after-hours carry commit (`commit_ah_carry`), the listed set (`listed_symbols`,
`graveyard_today`) and the once-a-day instrument-type map (`ensure_type_map`). Every comparison on a knob edge is
written as the multiplication the tests build their fixtures with (`price >= prev * (1 + pct / 100)`), so a
boundary row can never flip on the last bit of a division.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from sepa import prices, symbols

from . import constants as GC

log = logging.getLogger("chart_maps.gajjala.scanner")

ET = ZoneInfo("America/New_York")
_REF_TICKERS_URL = "https://api.massive.com/v3/reference/tickers"


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None                                # NaN -> None


def _et(now) -> datetime:
    if now is None:
        return datetime.now(ET)
    if now.tzinfo is None:
        return now.replace(tzinfo=ET)                           # a naive clock is read as ET
    return now.astimezone(ET)


def _iso(d) -> str:
    return d.isoformat() if isinstance(d, (date, datetime)) else str(d)


def pass_tape_session(now) -> str:
    """The tape session a pass belongs to. `prices.trade_session` calls 20:00–20:05 "closed", but the 20:01 pass
    closes the 19:55–20:00 bar and is the LAST after-hours pass (it decides tomorrow's carry) — so the minutes up
    to PASS_CLOSE_ET still count as after-hours."""
    et = _et(now)
    s = prices.trade_session(et)
    if s == "closed" and et.weekday() < 5:
        hh, mm = (int(x) for x in GC.PASS_CLOSE_ET.split(":"))
        if 20 * 60 <= et.hour * 60 + et.minute <= hh * 60 + mm:
            return "afterhours"
    return s


def _volume(row: dict, session_iso: str, tape_session: Optional[str] = None) -> tuple:
    """(shares today, source). Massive's `min.av` — the day's accumulated shares including pre-market (the `day`
    bar is all zeros before the open) — when its minute is dated the session; else `day.v` (HIS CALL 1 default).
    A PRE-MARKET print never falls back to `day.v`: before the open the day aggregate can be a phantom copy of the
    prior session (board.py's phantom-day trap), so a stale `min` reads volume 0, source "none"."""
    av = _f(row.get("min_av"))
    ep = prices._trade_epoch(row.get("min_t_ms"))
    if av is not None and ep is not None:
        try:
            if datetime.fromtimestamp(ep, tz=ET).date().isoformat() == session_iso:
                return av, "min_av"
        except (OverflowError, OSError, ValueError):
            pass
    if tape_session == "premarket":
        return 0.0, "none"
    return (_f(row.get("volume")) or 0.0), "day_v"


def _at_least(x: float, base: float, pct: float) -> bool:
    """x is at least `pct`% above `base` — written as the multiplication (edge-exact)."""
    return x >= base * (1 + pct / 100)


def row_type(sym: str, types: Optional[dict]) -> Optional[str]:
    """The instrument type the reference map gives `sym`; SCAN_UNKNOWN_TYPE when the map has no entry."""
    t = (types or {}).get(sym)
    return t if t else GC.SCAN_UNKNOWN_TYPE


def scan_rows(rows: dict, now, session, *, types: Optional[dict] = None) -> dict:
    """His scanner over every snapshot row. PURE.

    -> {session, tape_session, qualifiers: [Row], strip, counts, ah_carry: [Row] | None, k10_candidates: [Row]}
    Row = {symbol, type, price, prev_close, change_pct, volume, vol_src, day_o, day_h, day_l, day_c,
           last_trade_et, tape_session, ah_move_pct?}
    A row counts only when its last print is dated the session (an overnight row carries the LAST session stamped
    as today — trap T6) and its prior regular close is > 0. The strip population is his scanner minus the change
    floor (price band + 1M shares) inside the same instrument set; `quiet` is None when that population is empty
    (04:00 with nothing traded yet is not a quiet market, it is no market)."""
    session_iso = _iso(session)
    tape = pass_tape_session(now)
    in_ah = tape == "afterhours"
    types_on = GC.SCAN_INSTRUMENT_TYPES is not None
    counts = {"rows": 0, "dated_session": 0, "type_ok": 0, "type_out": 0, "type_unknown": 0, "band_ok": 0,
              "vol_ok": 0, "change_ok": 0, "qualifiers": 0, "held_split": 0, "split_failed": 0,
              "ah_rows": 0, "ah_close_eq_last": 0}
    qualifiers: list = []
    population: list = []                       # (symbol, change_pct, price, prev) — the strip's universe
    carry: list = []
    k10: list = []
    for sym, row in (rows or {}).items():
        counts["rows"] += 1
        if not isinstance(row, dict):
            continue
        ep = prices.extended_print(row)
        if not ep or ep["date"] != session_iso:
            continue
        prev = _f(row.get("prev_day_close"))
        if not prev or prev <= 0:
            continue
        counts["dated_session"] += 1
        typ = None
        if types_on:
            typ = row_type(sym, types)
            if typ == GC.SCAN_UNKNOWN_TYPE:
                if GC.SCAN_UNKNOWN_TYPE_POLICY == "drop":
                    counts["type_out"] += 1
                    continue
                counts["type_unknown"] += 1
            elif typ not in GC.SCAN_INSTRUMENT_TYPES:
                counts["type_out"] += 1
                continue
        counts["type_ok"] += 1
        price = float(ep["price"])
        vol, vol_src = _volume(row, session_iso, ep["session"])
        r = {"symbol": sym, "type": typ, "price": price, "prev_close": prev,
             "change_pct": round((price / prev - 1) * 100, 4), "volume": vol, "vol_src": vol_src,
             "day_o": _f(row.get("open")), "day_h": _f(row.get("high")), "day_l": _f(row.get("low")),
             "day_c": _f(row.get("close")),
             "last_trade_et": datetime.fromtimestamp(ep["epoch"], tz=ET).strftime("%Y-%m-%d %H:%M:%S"),
             "tape_session": ep["session"]}
        band = GC.SCAN_MIN_PRICE <= price <= GC.SCAN_MAX_PRICE
        if band:
            counts["band_ok"] += 1
            if vol >= GC.SCAN_MIN_VOLUME:
                counts["vol_ok"] += 1
                population.append((sym, r["change_pct"], price, prev))
                if _at_least(price, prev, GC.SCAN_MIN_CHANGE_PCT):
                    counts["change_ok"] += 1
                    qualifiers.append(r)
        if in_ah and band:
            # K9 carry + K10 prefilter: EVERY row of the snapshot, not only qualifiers (spec C4)
            # reg_close = `day.c`, read as the 16:00 close. UNVERIFIED in after-hours (step 0's AH probe not yet
            # run): if Massive's day.c follows the after-hours prints, every move reads ~0 and both lists stay empty
            # silently — `ah_close_eq_last` / `ah_rows` makes that visible in the funnel.
            reg_close = r["day_c"]
            if reg_close and reg_close > 0:
                counts["ah_rows"] += 1
                if reg_close == price:
                    counts["ah_close_eq_last"] += 1
                r["ah_move_pct"] = round((price / reg_close - 1) * 100, 4)
                if _at_least(price, reg_close, GC.K9_AH_CARRY_PCT):
                    carry.append(r)
                if _at_least(price, reg_close, GC.K10_AH_MIN_GAIN_PCT):
                    k10.append(r)
    counts["qualifiers"] = len(qualifiers)
    best = max(population, key=lambda p: (p[1], p[0]), default=None)
    strip = {
        "n_population": len(population),
        "best_change_pct": best[1] if best else None,
        "best_symbol": best[0] if best else None,
        "runners_100": sum(1 for _s, _c, px, pv in population if _at_least(px, pv, GC.SA_BIG_RUNNER_PCT)),
        "runners_80": sum(1 for _s, _c, px, pv in population if _at_least(px, pv, GC.SA_RUNNER_PCT)),
        "quiet": (None if not population
                  else not any(_at_least(px, pv, GC.SA_QUIET_BEST_PCT) for _s, _c, px, pv in population)),
    }
    qualifiers.sort(key=lambda q: (-q["change_pct"], q["symbol"]))
    return {"session": session_iso, "tape_session": tape, "qualifiers": qualifiers, "strip": strip,
            "counts": counts, "ah_carry": carry if in_ah else None, "k10_candidates": k10 if in_ah else []}


# ── split hold-out (new qualifiers only, once per symbol per session — HIS CALL 17) ─────────────────────────────
def hold_out_splits(result: dict, session, *, known: Optional[dict] = None,
                    fetch: Optional[Callable] = None) -> dict:
    """Drop every qualifier whose split executed TODAY (a reverse split reads as a +900% "runner"), in place.
    `known` = {SYM: check} decided earlier this session (never re-fetched). A raised fetch keeps the name, marked
    `split_check: "failed"` and counted. -> {SYM: check} newly decided this call."""
    from chart_maps.drop10_tab import fetch_splits_strict, split_on
    fetch = fetch or fetch_splits_strict
    session_iso = _iso(session)
    known = dict(known or {})
    decided: dict = {}
    kept: list = []
    for q in result.get("qualifiers") or []:
        sym = q["symbol"]
        check = known.get(sym)
        if check is None:
            try:
                check = "held" if split_on(fetch(sym, session_iso), session_iso) else "ok"
            except Exception as exc:                            # noqa: BLE001 — the URL carries the key; never logged
                log.debug("gajjala split check %s failed: %s", sym, type(exc).__name__)
                check = "failed"
            decided[sym] = check
        q["split_check"] = check
        if check == "held":
            result["counts"]["held_split"] += 1
            continue
        if check == "failed":
            result["counts"]["split_failed"] += 1
        kept.append(q)
    result["qualifiers"] = kept
    result["counts"]["qualifiers"] = len(kept)
    return decided


def record_scan(store, session, now, result: dict, *, fetch_splits: Optional[Callable] = None) -> dict:
    """The scan's writes for one pass: split hold-out on the names new this session, then today's qualifiers into
    `gajjala_scan` (held names are written as held so no pass re-fetches them). -> the newly decided checks."""
    decided = hold_out_splits(result, session, known=store.split_checks(session), fetch=fetch_splits)
    store.record_qualifiers(session, now, result["qualifiers"], result.get("tape_session") or "")
    for sym, check in decided.items():
        store.set_split_check(session, sym, check, now=now, held=(check == "held"))
    return decided


def commit_ah_carry(store, session, pass_at, result: dict, meta: Optional[dict]) -> str:
    """Write this pass's after-hours carry set. -> "replaced" | "failed" | "skipped" (not an after-hours pass).
    A failed or empty snapshot NEVER replaces the set: the last after-hours pass that actually read the market
    decides tomorrow's ☀️ carry (20:01 normally; an earlier one when the host slept through it)."""
    if result.get("ah_carry") is None:
        return "skipped"
    meta = meta or {}
    if meta.get("http") != 200 or not meta.get("n"):
        return "failed"
    store.replace_ah_carry(session, pass_at, result["ah_carry"])
    return "replaced"


# ── the listed set (spec §3.1.3) ────────────────────────────────────────────────────────────────────────────────
def _window(session) -> list:
    """[S, prev(S), …] — STAY_LISTED_SESSIONS + 1 market days, newest first (the house trading calendar)."""
    from catalysts.medical.reaction import prev_market_day
    d = session if isinstance(session, date) else date.fromisoformat(str(session))
    out = [d]
    for _ in range(GC.STAY_LISTED_SESSIONS):
        out.append(prev_market_day(out[-1]))
    return out


def listed_symbols(store, session) -> dict:
    """{SYM: {since, last_qualified, day_n, of}} — qualified on S or on one of the STAY_LISTED_SESSIONS market days
    before it. `day_n` = 1 on a day it qualified, rising each session it has not (day `of` = the last day listed)."""
    win = _window(session)
    pos = {w.isoformat(): i for i, w in enumerate(win)}
    seen: dict = {}
    for doc in store.scan_docs(win):
        d = doc.get("date")
        sym = doc.get("symbol")
        if d in pos and sym:
            seen.setdefault(sym, set()).add(d)
    out = {}
    for sym, days in seen.items():
        last = max(days)
        out[sym] = {"since": min(days), "last_qualified": last, "day_n": pos[last] + 1, "of": len(win)}
    return out


def graveyard_today(store, session) -> list:
    """Names that dropped off the list TODAY: last qualified exactly one market day before the window (HIS CALL 23)."""
    from catalysts.medical.reaction import prev_market_day
    win = _window(session)
    gone_day = prev_market_day(win[-1])
    still = {doc.get("symbol") for doc in store.scan_docs(win)}
    return sorted({doc.get("symbol") for doc in store.scan_docs([gone_day])
                   if doc.get("symbol") and doc.get("symbol") not in still})


# ── instrument-type reference map (Ajay round A: CS + ADRC) ─────────────────────────────────────────────────────
def fetch_type_map(*, http=None, key: Optional[str] = None,
                   max_pages: int = GC.TYPES_MAX_PAGES) -> tuple:
    """-> (types {SYM: type}, complete, calls). Massive `/v3/reference/tickers?market=stocks&active=true`, every
    type, paginated by `next_url`, at most `max_pages` calls; a page cut short leaves `complete` False (the names it
    missed then read "type unknown"). Never raises; the key never reaches a log line."""
    from massive_keys import stocks_key
    key = key if key is not None else stocks_key()
    if not key:
        return {}, False, 0
    http = http or prices._http()
    types: dict = {}
    url: Optional[str] = _REF_TICKERS_URL
    params: dict = {"market": "stocks", "active": "true", "limit": GC.TYPES_PAGE_LIMIT, "apiKey": key}
    calls = 0
    while url and calls < max_pages:
        calls += 1
        try:
            r = http.get(url, params=params, timeout=30)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala type map: %s", prices._scrub_key(exc))
            return types, False, calls
        if r.status_code != 200:
            log.warning("gajjala type map: HTTP %s", r.status_code)
            return types, False, calls
        body = r.json() or {}
        for it in body.get("results") or []:
            sym = symbols.for_yahoo(str((it or {}).get("ticker") or "").strip().upper())
            if sym and it.get("type"):
                types[sym] = str(it["type"])
        url = body.get("next_url")
        params = {"apiKey": key}                                # next_url carries its own cursor
    return types, url is None, calls


def ensure_type_map(store, session, *, fetch: Optional[Callable] = None, now=None) -> dict:
    """{SYM: type} for the session — ONE complete fetch per trading day (the first pass that gets one); every later
    pass reads Mongo. Only a COMPLETE fetch replaces the map and stamps `as_of` today. A failed or PARTIAL fetch (a
    mid-pagination error, or the TYPES_MAX_PAGES cap) never drops a known type: what it did read is merged over the
    previous map, `as_of` stays old, and the next pass retries (at most one fetch per pass). Replacing the map with a
    partial read would turn every name after the cut into "type unknown" — LISTED under the "list" policy, so ETFs,
    warrants and units would leak onto the board for the whole session."""
    session_iso = _iso(session)
    doc = store.types_map() or {}
    have = {p[0]: p[1] for p in doc.get("pairs") or [] if isinstance(p, (list, tuple)) and len(p) == 2}
    if doc.get("as_of") == session_iso:
        return have
    fetch = fetch or fetch_type_map
    try:
        types, complete, calls = fetch()
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala type map fetch raised: %s", prices._scrub_key(exc))
        types, complete, calls = {}, False, 0
    stamp = (now or datetime.now(timezone.utc))
    if complete and types:
        store.set_types_map({"as_of": session_iso, "attempted_on": session_iso, "complete": True,
                             "calls": calls, "n": len(types), "fetched_at": stamp,
                             "pairs": sorted([s, t] for s, t in types.items())})
        return dict(types)
    merged = dict(have, **(types or {}))
    log.warning("gajjala type map INCOMPLETE for %s: %d names in %d calls (cap %d) — kept the %s map, retrying "
                "next pass", session_iso, len(types or {}), calls, GC.TYPES_MAX_PAGES, doc.get("as_of") or "empty")
    keep = {k: v for k, v in doc.items() if k != "_id"}
    keep.update({"complete": False, "n": len(merged), "pairs": sorted([s, t] for s, t in merged.items()),
                 "last_error_at": stamp, "last_partial": {"session": session_iso, "n": len(types or {}),
                                                          "calls": calls}})
    store.set_types_map(keep)
    return merged


def k10_names(result: dict) -> list:
    """The 🌙 prefilter symbols of an after-hours pass (confirmed with 1-minute bars by context.py)."""
    return [r["symbol"] for r in result.get("k10_candidates") or []]


__all__ = ["pass_tape_session", "scan_rows", "hold_out_splits", "record_scan", "commit_ah_carry",
           "listed_symbols", "graveyard_today", "fetch_type_map", "ensure_type_map", "row_type", "k10_names"]
