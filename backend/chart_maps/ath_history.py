"""The long-history summary behind the 🏔️ ATH tab (Ajay 2026-09-29).

The ask, verbatim: "Can you give me a new tab - for all the stocks that are
reaching all time highs? call it ATH. Once some of them are going below their
ATH or 52 Week Highs.."

WHY A SEPARATE STORE. The shared daily price cache holds 2 years — an
all-time high cannot be read from it. Asking the shared loader for a longer
period with a forced refetch would OVERWRITE that shared doc app-wide (every
scan, zone and chart would then read a 10-year frame) and is still only 10
years. So this module keeps ONE small summary doc per symbol in its own
collection `ath_history`, built from ONE Massive MONTHLY aggregates call per
name (probed 2026-09-29: p50 0.30 s, ~30 KB; the provider's floor is 2003-09
on our plan). It never touches the shared cache and never calls the shared
loader (a source-grep test pins it).

TWO CUTS before a bar may count (the ticker-recycling audit, 2026-09-29):
  1. `prices._cut_foreign_head` — the curated FIRST_SESSION / rename cut the
     whole app already applies.
  2. `last_hole_cut` — a calendar month with no print between two prints means
     the ticker went dark; the bars before it belong to an earlier listing
     (DJT, PCOR, RKT, OGN, HCA, PFGC probed) and are cut. HIS CALL #7.
A recycled ticker with neither a curated cut nor a gap is NOT cut; the tab
then only refuses to call it all-time when its bars reach back before the
listing date (`ath_tab.completeness`).

This is the ONLY module of the tab that writes, and it writes only
`ath_history` (or an in-process dict when `ATH_HISTORY_STORE=memory`, the
branch-verification mode: no prod writes).
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime, timedelta
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from sepa import ipo_age, prices, symbols

log = logging.getLogger("chart_maps.ath_history")

ET = ZoneInfo("America/New_York")

COLL = "ath_history"                  # sibling of the shared price cache, like ipo_dates (ipo_age._ipo_coll)
SOURCE = "massive_1month"
FROM_DATE = "1970-01-01"              # ask from the epoch; the provider answers from its own floor
FILL_PAUSE_SEC = 0.2                  # pacing between calls (not a rule)
FILL_REBUILD_EVERY = 500              # the tab rebuilds its memo every N filled names (progress)
MISS_TTL_SEC = ipo_age._MISS_TTL_SEC  # an 'empty' answer is retried after a week (imported)
REFETCH_MIN_AGE_SEC = prices.CACHE_TTL_SEC  # a split mismatch refetches no sooner than the frame heals
STORE_ENV = "ATH_HISTORY_STORE"       # "mongo" (default) | "memory" (branch verification: no prod writes)

_MEM: dict = {}                       # the memory store: {SYM: doc}


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _sym(s) -> str:
    return str(s or "").strip().upper()


def _memory_mode() -> bool:
    return str(os.environ.get(STORE_ENV, "mongo") or "mongo").strip().lower() == "memory"


def _coll():
    """The `ath_history` collection, None when Mongo is down. NEVER reached in
    memory mode."""
    try:
        price_coll = prices._get_mongo()
        if price_coll is None:
            return None
        return price_coll.database[COLL]
    except Exception:                                           # noqa: BLE001
        return None


def month_end_before(now: datetime) -> date:
    """The last day of the calendar month before `now` (ET). Only COMPLETE
    months are stored; the cached daily frame covers the current month."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=ET)
    d = now.astimezone(ET).date()
    return d.replace(day=1) - timedelta(days=1)


def curation_key(sym: str) -> str:
    """The curated inputs the cuts depend on. A curation edit (a new
    FIRST_SESSION, a new RENAMES entry) changes this and invalidates the doc."""
    s = _sym(sym)
    return repr((symbols.first_session(s), symbols.rename_effective(s),
                 tuple(symbols.former_names(s))))


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------
def _fetch_raw(symbol: str, *, end: date, fetch_fn=None) -> Optional[pd.DataFrame]:
    """The ONE Massive aggregates fetcher, asked for monthly bars from the
    epoch. None = transport error / 429 twice / non-200 / no results; an
    empty frame = a 200 whose bars were all zero-priced."""
    fn = fetch_fn or prices._fetch_massive
    return fn(symbols.resolve(_sym(symbol)), "max", timespan="month",
              start=FROM_DATE, end=end.isoformat())


def fetch_monthly(symbol: str, *, end: date, fetch_fn=None) -> Optional[pd.DataFrame]:
    """Monthly bars for `symbol` up to `end`. None on a transport error or a
    non-200 — and on an empty frame too (`fill` tells the two apart)."""
    df = _fetch_raw(symbol, end=end, fetch_fn=fetch_fn)
    if df is None or len(df) == 0:
        return None
    return df


# ---------------------------------------------------------------------------
# pure summary
# ---------------------------------------------------------------------------
def last_hole_cut(df: Optional[pd.DataFrame]) -> tuple:
    """(rows at or after the row following the LAST hole, ISO date of that row
    | None). PURE.

    A HOLE is two consecutive rows whose calendar months differ by more than
    one: a calendar month with no print between two prints = the ticker went
    dark; bars before it belong to an earlier listing (DJT, PCOR, RKT, OGN,
    HCA, PFGC probed 2026-09-29) and are cut. A month whose only bars
    `_fetch_massive` dropped as zero-priced IS a hole (no trades that month).
    """
    if df is None or len(df) < 2:
        return df, None
    months = prices._day_index(df).to_period("M")
    ords = [int(p.ordinal) for p in months]
    last = None
    for i in range(1, len(ords)):
        if ords[i] - ords[i - 1] > 1:
            last = i
    if last is None:
        return df, None
    cut_from = prices._day_index(df)[last].date().isoformat()
    return df.iloc[last:], cut_from


def summarize(sym: str, df: Optional[pd.DataFrame], *, now: datetime) -> dict:
    """The stored doc for one name. PURE. `_cut_foreign_head` first, then
    `last_hole_cut`; the high of what survives."""
    s = _sym(sym)
    fetched_at = float(now.timestamp()) if isinstance(now, datetime) else float(time.time())
    base = {"_id": s, "symbol": s, "curation": curation_key(s), "source": SOURCE,
            "fetched_at": fetched_at}
    cut = prices._cut_foreign_head(df, s) if df is not None else None
    cut, cut_from = last_hole_cut(cut)
    if cut is None or len(cut) == 0:
        return {**base, "status": "empty"}
    highs = cut["high"].astype(float)
    if not highs.notna().any():
        return {**base, "status": "empty"}
    days = prices._day_index(cut)
    i_hi = int(np.nanargmax(highs.to_numpy(dtype=float)))      # the first month that printed it
    return {**base, "status": "ok",
            "first_bar": days[0].date().isoformat(),
            "hi": float(highs.iloc[i_hi]),
            "hi_month": days[i_hi].strftime("%Y-%m"),
            "check_month": days[-1].strftime("%Y-%m"),
            "check_high": float(highs.iloc[-1]),
            "cut_from": cut_from,
            "n_months": int(len(cut))}


# ---------------------------------------------------------------------------
# store
# ---------------------------------------------------------------------------
def read_many(syms) -> dict:
    """{SYM: doc} — ONE find (or the memory dict). {} when Mongo is down; the
    callers then read frame-only."""
    want = sorted({_sym(s) for s in (syms or []) if _sym(s)})
    if not want:
        return {}
    if _memory_mode():
        return {s: dict(_MEM[s]) for s in want if s in _MEM}
    coll = _coll()
    if coll is None:
        return {}
    try:
        return {str(d.get("_id")): d for d in coll.find({"_id": {"$in": want}})}
    except Exception as exc:                                    # noqa: BLE001
        log.debug("ath_history read failed: %s", exc)
        return {}


def upsert(doc: dict) -> None:
    """ONE replace by `_id` (memory mode: a dict set). Never the shared cache."""
    if not isinstance(doc, dict) or not doc.get("_id"):
        return
    if _memory_mode():
        _MEM[str(doc["_id"])] = dict(doc)
        return
    coll = _coll()
    if coll is None:
        return
    try:
        coll.replace_one({"_id": doc["_id"]}, doc, upsert=True)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("ath_history write failed for %s: %s", doc.get("_id"), exc)


def no_overlap(doc: Optional[dict], frame_first: Optional[str]) -> bool:
    """True when a doc's check month is OLDER than the month of the rolling
    daily frame's first bar (or it has none): its split check cannot run."""
    if not isinstance(doc, dict) or not frame_first:
        return False
    cm = str(doc.get("check_month") or "")
    return (not cm) or cm < str(frame_first)[:7]


def needs_fetch(doc: Optional[dict], sym: str, *, now,
                frame_first: Optional[str] = None) -> Optional[str]:
    """The reason this name needs a (re)fetch, or None. The split mismatch is
    decided by the tab (`ath_tab.closed_read`), which reads the daily frame.

    `frame_first` = the ISO date of the rolling daily frame's first bar. A good
    doc whose `check_month` is OLDER than that month is refetched
    ("check_stale"): the split check compares the doc's last month with the
    frame, and on an empty overlap it could never fail (critic 2026-09-29).
    Like a split, no sooner than REFETCH_MIN_AGE_SEC after the last fetch: a
    fresh doc that still ends before the frame (measured 2026-09-29: 1 of
    2,709 right after a full fill) would otherwise refetch on every rebuild.
    The tab never trusts such a doc either way (`no_overlap`)."""
    if not isinstance(doc, dict):
        return "missing"
    if doc.get("curation") != curation_key(sym):
        return "curation"
    if doc.get("status") == "ok" and no_overlap(doc, frame_first):
        now_ts = now.timestamp() if isinstance(now, datetime) else float(now or time.time())
        if now_ts - float(doc.get("fetched_at") or 0.0) >= REFETCH_MIN_AGE_SEC:
            return "check_stale"
    if doc.get("status") == "empty":
        now_ts = now.timestamp() if isinstance(now, datetime) else float(now or time.time())
        if now_ts - float(doc.get("fetched_at") or 0.0) >= MISS_TTL_SEC:
            return "retry_empty"
    return None


# ---------------------------------------------------------------------------
# fill — sequential, paced, never raises
# ---------------------------------------------------------------------------
def fill(syms, *, now: datetime, pause: float = FILL_PAUSE_SEC, fetch_fn=None,
         on_progress: Optional[Callable[[int], None]] = None) -> dict:
    """fetch -> summarize -> upsert, one name at a time. `None` from the fetch
    (transport / 429 twice / non-200) writes NO doc and is retried next pass;
    an empty-but-200 answer writes the `empty` doc. Counts {asked, ok, empty,
    error} (+ `error_symbols`). One name's exception is logged and counted."""
    names = []
    for s in syms or []:
        s = _sym(s)
        if s and s not in names:
            names.append(s)
    end = month_end_before(now)
    counts = {"asked": len(names), "ok": 0, "empty": 0, "error": 0, "error_symbols": []}
    for i, s in enumerate(names):
        try:
            raw = _fetch_raw(s, end=end, fetch_fn=fetch_fn)
            if raw is None:
                counts["error"] += 1
                counts["error_symbols"].append(s)
            else:
                doc = summarize(s, raw, now=datetime.now(ET))
                upsert(doc)
                counts["ok" if doc.get("status") == "ok" else "empty"] += 1
        except Exception as exc:                                # noqa: BLE001
            log.warning("ath_history fill: %s failed: %s", s, prices._scrub_key(exc))
            counts["error"] += 1
            counts["error_symbols"].append(s)
        done = i + 1
        if on_progress is not None and done % FILL_REBUILD_EVERY == 0 and done < len(names):
            _safe_progress(on_progress, done)
        if pause and done < len(names):
            time.sleep(pause)
    if on_progress is not None:
        _safe_progress(on_progress, len(names))
    return counts


def _safe_progress(fn, n: int) -> None:
    try:
        fn(n)
    except Exception as exc:                                    # noqa: BLE001
        log.debug("ath_history fill: progress callback failed: %s", exc)


def main(argv=None) -> dict:
    import argparse
    import json
    ap = argparse.ArgumentParser(prog="python -m chart_maps.ath_history")
    ap.add_argument("--fill", action="store_true", help="fetch every name that needs it")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)
    if not args.fill:
        ap.print_help()
        return {}
    from supply_demand import demand_reentry as D
    syms = [_sym(s) for s in (D._resolve_universe("full")[0] or []) if _sym(s)]
    now = datetime.now(ET)
    have = read_many(syms)
    todo = [s for s in syms if needs_fetch(have.get(s), s, now=now)]
    if args.limit is not None:
        todo = todo[:max(0, int(args.limit))]
    counts = fill(todo, now=now)
    counts = {**counts, "error_symbols": counts["error_symbols"][:50],
              "store": "memory" if _memory_mode() else COLL}
    print(json.dumps(counts))
    return counts


if __name__ == "__main__":
    main()
