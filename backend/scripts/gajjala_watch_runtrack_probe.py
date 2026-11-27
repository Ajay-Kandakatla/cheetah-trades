"""📅 Runners record — READ-ONLY probe (2026-11-26, spec watchrun rev 2 §3.4 / WP-2 step 4).

Answers three questions from the live store without writing anything: how far back the stored 5-minute reads go, how
many record docs tonight's nightly would open, and when the first run finishes its 10 sessions.

The container runs origin/main, where `chart_maps.gajjala_watch.runtrack` does not exist yet, so the small pieces are
re-implemented here (the window, the seat-run keys). `tests/test_gajjala_watch_runtrack_nightly_2026_11_26.py` pins
each one equal to the engine on fixtures, and pins the typed names below to the constants.

    docker exec -i -w /app cheetah-market-app-api-1 python - < backend/scripts/gajjala_watch_runtrack_probe.py

Reads: one `distinct("date")` on gajjala_reads, one find_one on the runners doc, one projected find on the record.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone

KEEP = 10                                            # == C.RUNNERS_KEEP_SESSIONS (pinned by a repo test)
READS_COLL = "gajjala_reads"                         # == chart_maps.gajjala.store.READS (pinned)
LIST_COLL = "gajjala_watch_list"                     # == C.COLL_LIST (pinned)
RUNNERS_ID = "runners"                               # == C.RUNNERS_DOC_ID (pinned)
RECORD_COLL = "gajjala_watch_runtrack"               # == C.COLL_RUNTRACK (pinned)
REASONS = ("aged", "dismissed", "blocked")           # == runtrack.SEAT_REASONS as a set (pinned)


def window_of(run_day, next_market_day=None) -> list:
    """The run day + the next KEEP − 1 market days, ISO, oldest first (== runtrack.window_of)."""
    if next_market_day is None:
        from catalysts.medical.reaction import next_market_day
    d = date.fromisoformat(str(run_day)[:10])
    out = [d]
    while len(out) < KEEP:
        out.append(next_market_day(out[-1]))
    return [x.isoformat() for x in out]


def _fold(sym) -> str:
    try:
        from chart_maps.gajjala.store import broker_fold
        return broker_fold(sym)
    except Exception:                                  # noqa: BLE001
        return str(sym or "").strip().upper()


def seat_keys(runners_doc, through: str) -> set:
    """{"<run day>|<SYM>"} of every run dated ≤ through: entries' runs ∪ removed entries' runs with a REASONS reason
    (== the keys of runtrack.seat_runs)."""
    out = set()
    doc = runners_doc if isinstance(runners_doc, dict) else {}
    ents = [e for e in doc.get("entries") or [] if isinstance(e, dict)]
    ents += [r.get("entry") for r in doc.get("removed") or []
             if isinstance(r, dict) and r.get("reason") in REASONS and isinstance(r.get("entry"), dict)]
    for e in ents:
        sym = _fold(e.get("symbol") or "").replace("-", ".")
        if not sym:
            continue
        for run in e.get("runs") or []:
            d = str((run or {}).get("date") or "")[:10] if isinstance(run, dict) else ""
            if d and d <= through:
                out.add(f"{d}|{sym}")
    return out


def main() -> int:
    from catalysts.medical.reaction import is_market_day, prev_market_day
    from sepa import prices
    pc = prices._get_mongo()
    if pc is None:
        print(json.dumps({"error": "no database"}))
        return 1
    db = pc.database
    et = datetime.now(timezone.utc).astimezone(__import__("zoneinfo").ZoneInfo("America/New_York")).date()
    through = (et if is_market_day(et) else prev_market_day(et)).isoformat()
    dates = sorted(d for d in db[READS_COLL].distinct("date") if isinstance(d, str))
    rdoc = db[LIST_COLL].find_one({"_id": RUNNERS_ID})
    on_file = {d["_id"]: d.get("state") for d in db[RECORD_COLL].find({}, {"_id": 1, "state": 1})}
    keys = seat_keys(rdoc, through)
    first = dates[0] if dates else None
    out = {"tonight": through, "reads_from": first, "reads_sessions": len(dates),
           "runners_doc": rdoc is not None, "runs_on_the_list": len(keys),
           "would_open_tonight": len(keys - set(on_file)),
           "record_docs": len(on_file), "record_open": sum(1 for s in on_file.values() if s == "open"),
           "first_run_closes": window_of(first)[-1] if first else None,
           "note": ("no runners doc yet — runseat is not deployed; every run it seats opens a record the next nightly"
                    if rdoc is None else None)}
    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
