"""🏁 🩳 SI follow-up — fill the follow-up facts of the recorded sessions, plan a night, or pin a name (2026-11-26, SPEC
sishares rev 2 §3.5, WP be-track).

    python -m scripts.gajjala_si_follow_backfill --plan
    python -m scripts.gajjala_si_follow_backfill --night
    python -m scripts.gajjala_si_follow_backfill [--dry] [--from YYYY-MM-DD] [--to YYYY-MM-DD]
    python -m scripts.gajjala_si_follow_backfill --load --max-loads N [--dry] [--from …] [--to …]
    python -m scripts.gajjala_si_follow_backfill --pin SYM[,SYM] --since YYYY-MM-DD | --unpin SYM | --pins

--plan       prints si_follow.plan over the same sessions (--from / --to apply): per session the facts wanted / free
             from stored reads / needing minutes / units, and the total vs si_track.MAX_LOADS. No write, no outside
             call. This sums the whole range, so its over_cap is NOT a night's verdict — use --night for that.
--night      prints si_follow.plan(st, now): the units ONE 20:15 ET night asks (the ended look-back sessions only)
             vs si_track.MAX_LOADS — the night's own over_cap. No write, no outside call. Takes no --from / --to.
             Exits 1 when any read fault is named (an index read or a session's follow doc).
default      the facts of every recorded session (and the sessions after it, through tonight) from STORED read docs
             only — the 1-minute seam is never asked (status "deferred"); a split check may still be asked when a
             stored read is complete; only those split checks count against si_track.MAX_LOADS. --dry writes
             nothing. --from / --to bound the sessions.
--load       the one-off paced provider load (HIS CALL #12): --max-loads N is REQUIRED (never defaulted) and is the
             run's whole budget. Refuses to start between 09:30 and 16:00 ET.
--pin        his word only: follow SYM from --since on (shown apart, never counted). --unpin / --pins.
Prints one JSON line per session, then a total. Not advice.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timezone

log = logging.getLogger("scripts.gajjala_si_follow_backfill")


def in_rth(now) -> bool:
    """True when `now` is between the regular open and close, ET (daytrading.data ET_RTH_OPEN / ET_RTH_CLOSE)."""
    from zoneinfo import ZoneInfo
    from daytrading.data import ET_RTH_CLOSE, ET_RTH_OPEN
    t = now.astimezone(ZoneInfo("America/New_York")).time()
    return ET_RTH_OPEN <= t < ET_RTH_CLOSE


def sessions(st, now, *, start=None, end=None) -> list:
    """Every market session (ISO, ascending) from the first recorded listing day through FOLLOW_SESSIONS sessions after
    the last one, never past tonight, inside [start, end]. RAISES si_track.ReadFault on an index read fault."""
    from chart_maps.gajjala import si_follow as SF
    from chart_maps.gajjala import si_track as SIT
    out = SF.fact_days(SIT.index_dates(st), now)
    return [x for x in out if (not start or x >= start) and (not end or x <= end) and SIT._ended(date.fromisoformat(x),
                                                                                                     now)]


def splits_only_budget(cap: int):
    """The stored-reads-only run's budget: a 1-minute load there is si_follow.stored_only (never a provider), so it
    is free — not counted in `loads`, never spends the cap a split check of a complete stored read needs. Only the
    split checks count against `cap`."""
    from chart_maps.gajjala import si_track as SIT

    class SplitsOnly(SIT.Budget):
        def take(self, kind: str) -> bool:
            return True if kind == "load" else super().take(kind)
    return SplitsOnly(cap)


def run(st, now, *, dry: bool = False, start: str = None, end: str = None, load: bool = False,
        max_loads: int = None, load_1m=None, split_lookup=None) -> list:
    """-> one line per session considered (oldest first). Without `load` the 1-minute seam is si_follow.stored_only
    (never a provider). ONE budget for the run: SIT.MAX_LOADS counting split checks only (a stored-only load is free,
    `loads` stays 0), or `max_loads` with --load. Never raises per session."""
    from chart_maps.gajjala import si_follow as SF
    from chart_maps.gajjala import si_track as SIT
    out = []
    try:
        isos = sessions(st, now, start=start, end=end)
        have = SIT.index_dates(st)
    except SIT.ReadFault:
        print(json.dumps({"error": "index_read"}))
        return out
    status: dict = {}
    seam = (load_1m or SIT.default_load_1m) if load else SF.stored_only
    ctx = SF._ctx(st, now, load_1m=seam, split_lookup=split_lookup,
                  max_loads=max_loads if load else None, share=None, status=status)
    if not load:
        ctx.budget = splits_only_budget(SIT.MAX_LOADS)
    pin_list = SF.pins(st)
    cache: dict = {}
    stamp = SIT._stamp(now)
    for iso in isos:
        d = date.fromisoformat(iso)
        line = {"session": iso, "asked": 0, "terminal": 0, "retry": 0, "no_trade": 0, "dry": bool(dry)}
        try:
            sid = SF.STATE_FMT.format(date=iso)
            cur = SIT.state_read(st, sid)
            if cur is None:
                line["error"] = "read"
                out.append(line)
                print(json.dumps(line))
                continue
            facts = SF._facts_of(cur)
            rows = {}
            if iso in have:
                rows = {str(r.get("symbol") or "").upper(): r
                        for r in SIT.session_doc(st, d, strict=True).get("rows") or [] if isinstance(r, dict)}
            changed = False
            for sym in SF.tracked(st, d, index=have, pin_list=pin_list, cache=cache):
                old, row = facts.get(sym), rows.get(sym)
                if SF._terminal(old) and not (row is not None and "base_kind" not in old):
                    continue
                f = SF.day_fact(ctx, sym, d, status, row=row)
                f["symbol"] = sym
                line["asked"] += 1
                line["retry" if f.get("retry") else "terminal"] += 1
                line["no_trade"] += 1 if f.get("state") == SF.FACT_STATES[-1] else 0
                if SF._terminal(f) or not SF._terminal(old):
                    facts[sym] = f
                    changed = True
            if changed and not dry:
                st.set_state(sid, {"date": iso, "facts": [facts[s] for s in sorted(facts)], "version": SF.VERSION,
                                   "updated_at": stamp})
        except Exception as exc:                                # noqa: BLE001
            line["error"] = type(exc).__name__
        line.update(loads=ctx.budget.loads, split_calls=ctx.budget.split_calls, deferred_cap=ctx.budget.deferred)
        out.append(line)
        print(json.dumps(line, default=str))
    if not dry:
        try:
            SIT.write_stats(st, now)
        except Exception as exc:                                # noqa: BLE001
            print(json.dumps({"stats_error": type(exc).__name__}))
    print(json.dumps({"total": {"sessions": len(out), "asked": sum(x.get("asked", 0) for x in out),
                                "loads": ctx.budget.loads, "split_calls": ctx.budget.split_calls,
                                "deferred_cap": ctx.budget.deferred, "dry": bool(dry)}}))
    return out


def main(argv=None, *, store=None, now=None) -> int:
    ap = argparse.ArgumentParser(prog="scripts.gajjala_si_follow_backfill", description=__doc__.split("\n")[0])
    ap.add_argument("--plan", action="store_true", help="print the units the backfill range would ask — nothing written")
    ap.add_argument("--night", action="store_true",
                    help="print the units ONE night asks (the look-back only) vs the cap — nothing written")
    ap.add_argument("--dry", action="store_true", help="compute and print only — nothing written")
    ap.add_argument("--from", dest="start", help="YYYY-MM-DD — the first session")
    ap.add_argument("--to", dest="end", help="YYYY-MM-DD — the last session")
    ap.add_argument("--load", action="store_true", help="the one-off paced provider load (needs --max-loads)")
    ap.add_argument("--max-loads", dest="max_loads", type=int, help="the --load run's whole budget (required)")
    ap.add_argument("--pin", help="SYM[,SYM] — follow these names (his word only)")
    ap.add_argument("--since", help="YYYY-MM-DD — the pin's first session")
    ap.add_argument("--unpin", help="SYM — stop following it")
    ap.add_argument("--pins", action="store_true", help="print the pins")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    now = now or datetime.now(timezone.utc)
    if args.load and (args.max_loads is None or args.max_loads <= 0):
        print(json.dumps({"error": "max_loads_required"}))
        return 2
    if args.load and in_rth(now):
        print(json.dumps({"error": "regular_hours"}))
        return 3
    from chart_maps.gajjala import si_follow as SF
    from chart_maps.gajjala import store as ST
    st = store if store is not None else ST.default()
    if st.coll(ST.STATE) is None:
        print(json.dumps({"error": "no_store"}))
        return 1
    if args.pins:
        print(json.dumps({"pins": SF.pins(st)}))
        return 0
    if args.pin:
        if not args.since:
            print(json.dumps({"error": "since_required"}))
            return 2
        res = [SF.pin(st, s.strip(), args.since, now) for s in args.pin.split(",") if s.strip()]
        print(json.dumps({"pin": res}, default=str))
        return 0 if res and all(r["ok"] for r in res) else 2
    if args.unpin:
        res = SF.unpin(st, args.unpin)
        print(json.dumps({"unpin": res}, default=str))
        return 0 if res["ok"] else 2
    if args.night:
        if args.start or args.end:
            print(json.dumps({"error": "night_takes_no_range"}))
            return 2
        p = SF.plan(st, now)
        print(json.dumps(p, default=str))
        return 1 if p.get("faults") else 0
    if args.plan:
        from chart_maps.gajjala import si_track as SIT
        try:
            isos = sessions(st, now, start=args.start, end=args.end)
        except SIT.ReadFault:
            print(json.dumps({"error": "index_read"}))
            return 1
        print(json.dumps(SF.plan(st, now, sessions=isos), default=str))
        return 0
    run(st, now, dry=args.dry, start=args.start, end=args.end, load=args.load, max_loads=args.max_loads)
    return 0


if __name__ == "__main__":
    sys.exit(main())
