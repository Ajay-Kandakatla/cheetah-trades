"""🏁 🩳 SI track record — backfill every session that still has stored reads and is not recorded yet (2026-11-26, SPEC
sitrack §3.7, WP be-track).

    python -m scripts.gajjala_si_track_backfill [--dry] [--from YYYY-MM-DD] [--force]

Oldest first: `si_track.record_session(..., source="backfill")` (one MAX_LOADS budget per session), then
`si_track.fill_next`, then the stats once at the end. Prints one JSON line per session: rows, counted, no_pit_si,
⛔ known / unknown, loads, split calls. Stored reads live GC.READS_TTL_DAYS days, so the first run reaches back about
that far. ⛔ is read by the engine as of each session (unknown where the SSR record does not reach); 🔒 📄 ✂️ fields are
None on every backfilled day (the engines have no as-of read).

--dry      records nothing (computes and prints only).
--from     the first session to consider (default: every stored session).
--force    re-records a session already in the index — never one recorded by the nightly (its ex-ante fields are point
           in time; record_session refuses it from the session doc itself, even when the index lost it).
An index read fault prints {"error": "index_read"} and records nothing.
Run it outside 09:30–16:00 ET (detached in the container). Not advice.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timezone

log = logging.getLogger("scripts.gajjala_si_track_backfill")


def stored_sessions(st) -> list:
    """Every session (ISO, ascending) with at least one stored read doc — ONE distinct read; [] on a fault."""
    from chart_maps.gajjala import store as ST
    c = st.coll(ST.READS)
    if c is None:
        return []
    try:
        return sorted({d for d in c.distinct("date") if isinstance(d, str)})
    except Exception as exc:                                    # noqa: BLE001
        log.warning("si track backfill: stored sessions unread: %s", type(exc).__name__)
        return []


def run(st, now, *, dry: bool = False, start: str = None, force: bool = False, **seams) -> list:
    """-> one summary dict per session considered (oldest first). Never raises per session."""
    from chart_maps.gajjala import si_track as SIT
    out = []
    try:
        have = set(SIT.index_dates(st))
    except SIT.ReadFault:                                       # a faulted index is never "nothing recorded yet"
        print(json.dumps({"error": "index_read"}))
        return out
    for iso in stored_sessions(st):
        if start and iso < start:
            continue
        d = date.fromisoformat(iso)
        if not SIT._ended(d, now):
            continue
        if iso in have:
            if not force or SIT.session_doc(st, iso).get("source") == "nightly":
                continue
        line = {"session": iso}
        try:
            ctx = SIT.Ctx(st, now, load_1m=seams.get("load_1m"), split_lookup=seams.get("split_lookup"),
                          ssr_read=seams.get("ssr_read"), sho_read=seams.get("sho_read"),
                          si_read=seams.get("si_read"), budget=SIT.Budget(seams.get("max_loads", SIT.MAX_LOADS)))
            res = SIT.record_session(st, d, now, source="backfill", ctx=ctx, write=not dry)
            rows = res["doc"]["rows"]
            if not dry:
                SIT.fill_next(st, d, now, ctx=ctx)
            line.update(rows=len(rows), counted=len(SIT.counted(rows)),
                        no_pit_si=int((res["doc"].get("excluded") or {}).get("no_si") or 0),
                        ssr_known=sum(1 for r in rows for k in ("ssr_open", "ssr_trig_day") if r.get(k) is not None),
                        ssr_unknown=sum(1 for r in rows for k in ("ssr_open", "ssr_trig_day") if r.get(k) is None),
                        loads=res["loads"], split_calls=res["split_calls"], deferred_cap=res["deferred_cap"],
                        faults=res["faults"], dry=bool(dry))
        except SIT.OnFile:                                      # a nightly doc the index lost: put it back, keep it
            SIT._index_add(st, iso)
            line["error"] = "on_file"
        except Exception as exc:                                # noqa: BLE001
            line["error"] = type(exc).__name__
        out.append(line)
        print(json.dumps(line, default=str))
    if not dry:
        try:
            SIT.write_stats(st, now)
        except Exception as exc:                                # noqa: BLE001
            print(json.dumps({"stats_error": type(exc).__name__}))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="scripts.gajjala_si_track_backfill", description=__doc__.split("\n")[0])
    ap.add_argument("--dry", action="store_true", help="compute and print only — nothing written")
    ap.add_argument("--from", dest="start", help="YYYY-MM-DD — the first session to consider")
    ap.add_argument("--force", action="store_true", help="re-record a backfilled / late session (never a nightly one)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    from chart_maps.gajjala import store as ST
    st = ST.default()
    if st.coll(ST.STATE) is None:
        print(json.dumps({"error": "no_store"}))
        return 1
    run(st, datetime.now(timezone.utc), dry=args.dry, start=args.start, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
