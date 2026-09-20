"""📣 earnings_reaction replay — a phone-load COUNT, not an edge claim.

What this answers, and only this: how many pushes the `earnings_reaction` kind
(chart_maps/earnings_alerts.py) would have sent per session over the last N
sessions, how many would have ridden a digest, and what a surprise floor would
do to those counts. It says NOTHING about whether the pushed names went up —
the prior on this signal is null (the institutional read is an owner setting
calibrated on two names on the 2026-08-19 tape), the 8-K event study measured
no chase edge after a day-0 pop, and the entry-trigger study measured
confirmation entries as cushion, not edge.

BOTH ANCHORINGS (critique F6, 2026-09-20). The reaction bar is located from a
report date plus a BMO/AMC stamp, and the tree has two sources for that stamp:
`last_report.when` (the confirmed timestamp yfinance returns with the reported
EPS) and the calendar doc's top-level `when` (an estimate, and None for most
near reporters — 1,646 of 2,071 docs after the 2026-09-18 refresh). The live
pass anchors on the FRESH fetch's `last_report.when` and skips a name whose
fresh stamp is None. So this script computes both and reports both; the JSON's
`live_anchoring` names the one the cron actually uses, and a count taken off
the other anchoring is not a description of the cron.

Every threshold comes from `chart_maps.earnings` by import. Nothing here
retypes a gate, and the test pins that the source carries no gate literal.

Run OUTSIDE RTH — `sepa.prices.load_prices` serves the cache, and between
10:00 and 16:30 ET its last row is today's PARTIAL bar (vcp-watch patches it
hourly), which would score a half-session as a reaction.

    docker exec -i -w /app cheetah-market-app-api-1 \
        python - --out /tmp/earnings_reaction_measured.json \
        < backend/scripts/earnings_reaction_replay.py
    docker cp cheetah-market-app-api-1:/tmp/earnings_reaction_measured.json <scratch>/
    # then copy into backend/scripts/earnings_reaction_measured.json
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chart_maps.earnings import bar_metrics, is_institutional_buy   # noqa: E402
from growth.alerts import MAX_INDIVIDUAL                            # noqa: E402

log = logging.getLogger("earnings_reaction_replay")

# Candidate surprise floors for §7.2. REPORT ONLY — none is chosen here, and
# choosing one is a new numeric threshold, which is his call (Rule #1).
FLOORS = (0, 2, 5, 10, 20, 50)

# How far back the calendar is read. The collection holds only the LAST report
# per name, so a wider window buys nothing but slower queries.
WINDOW_DAYS = 100

WOULD_PUSH = "institutional_and_beat"
LABELS = (WOULD_PUSH, "institutional_and_miss", "institutional_null_surprise",
          "beat_not_institutional", "neither")

CAVEATS = [
    "A phone-load COUNT, not an edge claim: nothing here measures what the pushed names did next.",
    "A census over the calendar's decision universe (the same collection the Earnings Flow tab "
    "reads), not a sample — there is no CI because there is no estimate of a population quantity.",
    "The calendar holds only the LAST report per name, so a name contributes at most one event in "
    "the window, and a doc refreshed after a newer report shows only that one.",
    "Docs whose last_report was nulled by the 2026-09-18 fetch-pool fallback undercount the total.",
    "A report whose `when` is None is anchored like BMO in the doc-anchoring pass; the LIVE pass "
    "skips such a name (skipped_timing_unknown) instead of guessing.",
    "The >= 5% room gate cannot be replayed — zone_store keeps only the latest bands — so "
    "would_skip_room comes from live passes only.",
    "The institutional read is an owner setting calibrated on two names (TGT, BULL) on the "
    "2026-08-19 tape. NOT MEASURED.",
]


def classify(m: Optional[dict], surprise_pct) -> str:
    """One event's cell. PURE. `m` is a `bar_metrics` dict for the reaction bar.

    The gate the push applies is institutional buying AND a beat above zero, so
    the four other cells exist to say what the gate refused and why.
    """
    inst = is_institutional_buy(m or {})
    try:
        s = float(surprise_pct)
        s = s if s == s else None
    except (TypeError, ValueError):
        s = None
    if inst and s is None:
        return "institutional_null_surprise"
    if inst and s > 0:
        return WOULD_PUSH
    if inst:
        return "institutional_and_miss"
    if s is not None and s > 0:
        return "beat_not_institutional"
    return "neither"


def per_session(events: list, sessions: list) -> dict:
    """{session: {pushes, names, singles, digest}} over the would-push events.

    `singles` / `digest` split at `growth.alerts.MAX_INDIVIDUAL` — the same
    constant the pass splits at, imported rather than retyped.
    """
    out = {d: {"pushes": 0, "names": [], "singles": 0, "digest": 0} for d in sessions}
    for e in events:
        if e.get("cell") != WOULD_PUSH:
            continue
        d = e.get("reaction_date")
        if d not in out:
            continue
        out[d]["pushes"] += 1
        out[d]["names"].append(e["symbol"])
    for d, row in out.items():
        n = row["pushes"]
        row["singles"] = min(n, MAX_INDIVIDUAL)
        row["digest"] = max(0, n - MAX_INDIVIDUAL)
    return out


def _stats(values: list) -> dict:
    vals = sorted(values)
    n = len(vals)
    if not n:
        return {"total": 0, "sessions_with_any": 0, "median": 0, "p90": 0, "max": 0}
    med = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
    p90 = vals[min(n - 1, int(round(0.9 * (n - 1))))]
    return {"total": sum(vals), "sessions_with_any": sum(1 for v in vals if v > 0),
            "median": med, "p90": p90, "max": vals[-1]}


def summarize(ps: dict) -> dict:
    s = _stats([r["pushes"] for r in ps.values()])
    busiest = max(ps.items(), key=lambda kv: kv[1]["pushes"], default=(None, {"pushes": 0, "names": []}))
    s["busiest"] = {"date": busiest[0], "n": busiest[1]["pushes"], "names": busiest[1]["names"]}
    return s


def floors_table(events: list, sessions: list, floors=FLOORS) -> dict:
    """Counts at each candidate surprise floor. REPORT ONLY — no floor ships.

    Monotone non-increasing in the floor by construction: a higher floor can
    only drop events.
    """
    out = {}
    for f in floors:
        kept = [e for e in events
                if e.get("cell") == WOULD_PUSH and (e.get("surprise_pct") or 0) > f]
        ps = per_session(kept, sessions)
        st = _stats([r["pushes"] for r in ps.values()])
        b = max(ps.items(), key=lambda kv: kv[1]["pushes"], default=(None, {"pushes": 0}))
        out[str(f)] = {"total": st["total"], "median": st["median"], "max": st["max"],
                       "busiest_n": b[1]["pushes"]}
    return out


# ── the impure half: Mongo + the price cache ────────────────────────────────
def _calendar_docs(window_days: int = WINDOW_DAYS) -> list:
    from datetime import timedelta
    from sepa import earnings_watch as EW
    coll = EW._coll()
    if coll is None:
        return []
    lo = (EW._today_et().date() - timedelta(days=window_days)).isoformat()
    return list(coll.find({"last_report.date": {"$gte": lo}}))


def _sessions(n: int) -> list:
    from sepa import prices
    df = prices.load_prices("SPY")
    if df is None or not len(df):
        return []
    return [str(d)[:10] for d in df.index[-n:]]


def build_events(docs: list, sessions: list, anchor: str, load=None) -> tuple:
    """(events, coverage) for one anchoring.

    `anchor` is "last_report" (the live pass's source — the confirmed stamp on
    the report itself) or "doc" (the calendar's top-level estimate).
    """
    from sepa import earnings_picks as EP
    if load is None:
        from sepa import prices
        load = prices.load_prices
    import pandas as pd
    cov = {"calendar_docs": len(docs), "with_last_report_in_window": 0,
           "no_reaction_bar": 0, "short_frame": 0, "when_none": 0, "off_window": 0}
    events = []
    lo = sessions[0] if sessions else ""
    for doc in docs:
        lr = doc.get("last_report") or {}
        date = str(lr.get("date") or "")[:10]
        if not date:
            continue
        cov["with_last_report_in_window"] += 1
        when = lr.get("when") if anchor == "last_report" else doc.get("when")
        if when is None:
            cov["when_none"] += 1
        sym = str(doc.get("_id") or "").upper()
        try:
            df = load(sym)
        except Exception:
            df = None
        if df is None or not len(df):
            cov["short_frame"] += 1
            continue
        rr = EP.reaction_read(df, date, when)
        if not rr:
            cov["no_reaction_bar"] += 1
            continue
        rdate = str(rr.get("reaction_date") or "")[:10]
        if rdate < lo:
            cov["off_window"] += 1
            continue
        try:
            k = int(df.index.searchsorted(pd.Timestamp(rdate), side="left"))
        except Exception:
            cov["no_reaction_bar"] += 1
            continue
        m = bar_metrics(df, k)
        if not m or m["date"] != rdate:
            cov["short_frame"] += 1
            continue
        s = lr.get("surprise_pct")
        events.append({"symbol": sym, "report_date": date, "when": when,
                       "reaction_date": rdate, "surprise_pct": s,
                       "dollar_vol": m.get("dollar_vol"), "change_pct": m.get("change_pct"),
                       "vol_ratio": m.get("vol_ratio"), "close_loc": m.get("close_loc"),
                       "cell": classify(m, s)})
    return events, cov


def cells(events: list) -> dict:
    out = {k: 0 for k in LABELS}
    out["reacted_total"] = len(events)
    for e in events:
        out[e["cell"]] = out.get(e["cell"], 0) + 1
    return out


def replay(sessions_n: int = 60, docs: Optional[list] = None,
           sessions: Optional[list] = None, load=None) -> dict:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    docs = _calendar_docs() if docs is None else docs
    sessions = _sessions(sessions_n) if sessions is None else sessions
    out = {"as_of": datetime.now(ZoneInfo("America/New_York")).isoformat(),
           "sessions": sessions,
           "live_anchoring": "last_report",
           "anchorings": {}, "caveats": list(CAVEATS)}
    for anchor in ("last_report", "doc"):
        ev, cov = build_events(docs, sessions, anchor, load=load)
        ps = per_session(ev, sessions)
        misses = [e for e in ev if e["cell"] == "institutional_and_miss"]
        out["anchorings"][anchor] = {
            "cells": cells(ev),
            "per_session": ps,
            "summary": summarize(ps),
            "floors": floors_table(ev, sessions),
            "institutional_misses": _stats([sum(1 for e in misses if e["reaction_date"] == d)
                                            for d in sessions]),
            "coverage": cov,
        }
    live = out["anchorings"]["last_report"]
    out.update(per_session=live["per_session"], summary=live["summary"],
               floors=live["floors"], institutional_misses=live["institutional_misses"],
               coverage=live["coverage"])
    return out


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--sessions", type=int, default=60)
    p.add_argument("--out", default="")
    a = p.parse_args(argv)
    res = replay(a.sessions)
    blob = json.dumps(res, indent=2, default=str)
    if a.out:
        with open(a.out, "w") as fh:
            fh.write(blob + "\n")
        print("wrote %s (%d sessions, %d would-push)"
              % (a.out, len(res["sessions"]), res["summary"]["total"]))
    else:
        print(blob)
    return 0


if __name__ == "__main__":                                   # pragma: no cover
    raise SystemExit(main())
