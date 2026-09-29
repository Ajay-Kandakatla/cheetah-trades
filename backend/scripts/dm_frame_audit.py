#!/usr/bin/env python
"""Find the next reused-ticker / reorg frame before it tops a board — READ-ONLY.

Why it exists (2026-09-29, the Dual Momentum data audit): Ajay's /dual-momentum
page ranked WOLF +2,248.76%, BNY +1,435% and SPCX +474.95% for 12 months. Each
cached frame began with ANOTHER security's bars (Wolfspeed's cancelled
pre-Chapter-11 equity, the BlackRock NY Muni fund, the SPAC ETF), so the
"return" was the ratio of two companies' prices. The fix is curated
(`sepa.symbols.FIRST_SESSION` / `RENAMES`, applied by
`sepa.prices._cut_foreign_head`); this script is the tool that finds the next
candidate for a human to check against the provider's reference data.

What it does: ONE `find` over `price_cache`. For every frame it looks at the
last 12-month window the Dual Momentum engine reads
(`sepa.dual_momentum.LOOKBACKS["return_12m"]` + 1 bars) and reports it when the
window holds

  * a close-to-close jump the price layer already calls impossible for one
    session (`sepa.prices._is_scale_glitch`, i.e. `_SCALE_GLITCH_RATIO`), or
  * a calendar hole longer than HOLE_REPORT_DAYS.

Each hit prints the first bar, the hole, the jump, and whether the curated cut
heals it (the check re-run on `_cut_foreign_head(frame, symbol)`).

A HIT IS NOT A VERDICT. Real moves can reach the ratio (none did on
2026-09-29: the largest real day was CAPR 4.71x). Every hit is checked against
Massive's reference (FIGI, list_date, ticker events, splits) before anyone adds
a curated entry — see docs/sepa/dual_momentum_data_audit_2026_09_29.md.

It writes nothing: no Mongo write of any kind, no provider fetch, no file.
The Mongo handle is opened directly, not through the price layer's own
connector (that one also ensures an index, which is a command, not a read).

    host:       backend/.venv/bin/python backend/scripts/dm_frame_audit.py
    container:  docker exec -i -w /app cheetah-market-app-api-1 \\
                    sh -c 'PYTHONPATH=/app python -u scripts/dm_frame_audit.py'
    options:    --symbols WOLF,BNY   --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable, Optional

_ROOT = str(Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path[:0] = [_ROOT]

import pandas as pd  # noqa: E402

from sepa import prices as P  # noqa: E402
from sepa import symbols as SY  # noqa: E402
from sepa.dual_momentum import LOOKBACKS  # noqa: E402

# A REPORT threshold, not a rule: a hole this long inside a 12m window is worth
# a human look. It gates nothing and no board reads it.
HOLE_REPORT_DAYS = 20
WINDOW_BARS = LOOKBACKS["return_12m"] + 1
PROJECTION = {"_id": 0, "symbol": 1, "bars": 1}


def frame_from_doc(doc: dict) -> Optional[pd.DataFrame]:
    """The `_mongo_get` reshaping of one cache doc, with NO cut applied."""
    bars = (doc or {}).get("bars") or []
    if not bars:
        return None
    df = pd.DataFrame(bars)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")[["open", "high", "low", "close", "volume"]].sort_index()


def window_read(df: Optional[pd.DataFrame]) -> dict:
    """Largest jump and longest hole inside the last WINDOW_BARS bars. PURE."""
    out = {"bars": 0, "window_start": None, "ratio": None, "ratio_date": None,
           "jump": False, "hole_days": 0, "hole_end": None, "hit": False}
    if df is None or len(df) == 0:
        return out
    w = df.iloc[-WINDOW_BARS:]
    out["bars"] = int(len(df))
    out["window_start"] = str(pd.Timestamp(w.index[0]).date())
    closes = [float(c) for c in w["close"]]
    days = P._day_index(w)
    for i in range(1, len(w)):
        prev, cur = closes[i - 1], closes[i]
        if prev > 0 and cur > 0:
            r = max(cur / prev, prev / cur)
            if out["ratio"] is None or r > out["ratio"]:
                out["ratio"] = round(r, 2)
                out["ratio_date"] = str(days[i].date())
            if P._is_scale_glitch(cur, prev):
                out["jump"] = True
        gap = int((days[i] - days[i - 1]).days)
        if gap > out["hole_days"]:
            out["hole_days"] = gap
            out["hole_end"] = str(days[i].date())
    out["hit"] = bool(out["jump"] or out["hole_days"] > HOLE_REPORT_DAYS)
    return out


def heal_source(symbol: str) -> Optional[str]:
    """Which curated map covers the symbol, if any. PURE."""
    if SY.first_session(symbol):
        return "FIRST_SESSION"
    if SY.rename_effective(symbol):
        return "RENAMES"
    return None


def audit_frame(symbol: str, df: Optional[pd.DataFrame]) -> Optional[dict]:
    """A report row when the raw frame's 12m window is suspect, else None."""
    raw = window_read(df)
    if not raw["hit"]:
        return None
    cut = window_read(P._cut_foreign_head(df, symbol))
    return {
        "symbol": symbol,
        "first_bar": str(pd.Timestamp(df.index[0]).date()),
        "bars": raw["bars"],
        "window_start": raw["window_start"],
        "max_ratio": raw["ratio"], "ratio_date": raw["ratio_date"],
        "hole_days": raw["hole_days"], "hole_end": raw["hole_end"],
        "curated": heal_source(symbol),
        "healed": not cut["hit"],
        "bars_after_cut": cut["bars"],
    }


def audit(coll, symbols: Optional[Iterable[str]] = None) -> list:
    """ONE `find` over the collection; the rows `audit_frame` reports."""
    query = {}
    if symbols:
        query = {"symbol": {"$in": [str(s).strip().upper() for s in symbols if s]}}
    rows = []
    for doc in coll.find(query, PROJECTION):
        sym = str((doc or {}).get("symbol") or "").upper()
        if not sym:
            continue
        try:
            row = audit_frame(sym, frame_from_doc(doc))
        except (KeyError, ValueError, TypeError) as exc:
            print(f"skip {sym}: {exc}", file=sys.stderr)
            continue
        if row:
            rows.append(row)
    rows.sort(key=lambda r: (r["healed"], -(r["max_ratio"] or 0), r["symbol"]))
    return rows


def _read_only_collection():
    from pymongo import MongoClient
    url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB", "cheetah")
    client = MongoClient(url, serverSelectionTimeoutMS=5000)
    return client[db_name].price_cache


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--symbols", default="", help="comma list; default = every cached frame")
    ap.add_argument("--json", action="store_true", help="print JSON rows")
    args = ap.parse_args(argv)
    syms = [s for s in args.symbols.split(",") if s.strip()] or None
    rows = audit(_read_only_collection(), syms)
    if args.json:
        print(json.dumps(rows, indent=1))
        return 0
    print(f"window {WINDOW_BARS} bars · jump = prices._is_scale_glitch "
          f"({P._SCALE_GLITCH_RATIO}x) · hole > {HOLE_REPORT_DAYS} days")
    print(f"{'sym':<7} {'first bar':<11} {'bars':>5} {'max x':>7} {'on':<11} "
          f"{'hole d':>6} {'hole end':<11} {'curated':<14} healed")
    for r in rows:
        print(f"{r['symbol']:<7} {r['first_bar']:<11} {r['bars']:>5} "
              f"{(r['max_ratio'] or 0):>7.2f} {str(r['ratio_date']):<11} "
              f"{r['hole_days']:>6} {str(r['hole_end']):<11} "
              f"{str(r['curated'] or '-'):<14} {'yes' if r['healed'] else 'NO'}")
    open_n = sum(1 for r in rows if not r["healed"])
    print(f"{len(rows)} suspect frames; {open_n} not healed by a curated entry "
          "(check each against the provider reference before adding one)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
