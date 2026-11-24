"""🩳🔀 How often the 🩳 High SI 9 / 21 EMA cross push WOULD ring — READ-ONLY, frequency only (2026-11-23, spec highsi §3.7).

Ajay, verbatim (2026-11-23, voice-typed — "talks" = stocks): "And also add alerts for these talks when they are crossing
EMA, 9 EMA over 21 EMA."

FREQUENCY ONLY — NOT AN EDGE, not a win rate, not a forecast. Per stored session (the newest `--sessions N` dates of
gajjala_reads, all inside READS_TTL_DAYS):

  * members under the BUILT rule (high_si.classify — the ONE membership function the board and the push use, never a
    copy) and under his answer #1 read literally (house tier High / EXTREME + the card's float at or under the cap),
    and every not-listed reason;
  * the up crosses per frame of the members' STORED 5-min / 15-min tiles (tab.ema_cross_block — the ONE engine over
    the stored curves; the first drawn bar is never a cross, the push's watch_crosses rule);
  * the rings under BOTH latches (one per cross = BUILT, one per name / frame / session), each with and without GG's
    session floor, under the gates of high_si_cross.run_step exactly:
      - the first-15 MUTE by the candle's START (alerts.window_reason == "suppressed_first15"; "suppressed_window" =
        outside the hours; pre-market is not held),
      - the HOURS on the pass clock (potential.window_reason at the bar's close + GC.BAR_SETTLE_SEC == "outside_hours"),
      - the name was already listed at the cross (its scan doc's `first_qualified_at`, or the session start for a name
        carried from an earlier window day),
      - TODAY's cumulative volume through the cross bar (the stored 5-minute tile, today's bars only) at or over
        GC.K11_MIN_SESSION_VOLUME.

`--pushes` adds that day's delivered pushes per kind (ONE push_history find, `sent > 0`). Mongo reads only: no fetch,
no write, no index build. Membership uses TODAY's short-interest read for every session (the newest FINRA settlement
on file). It assumes every pass ran (an upper bound).

    docker exec -i -w /app <scratch container on the branch> python -m scripts.gajjala_high_si_cross_count \\
        --sessions 5 --pushes --json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
HONESTY = ("frequency only — not an edge", "membership uses today's short-interest read", "assumes every pass ran")
LATCH_WORDS = {"cross": "one per name, chart and cross (BUILT)", "session": "one per name, chart and session"}


def _et(x) -> Optional[datetime]:
    if not isinstance(x, datetime):
        return None
    return (x.replace(tzinfo=timezone.utc) if x.tzinfo is None else x).astimezone(ET)


def literal_member(blk, fr) -> bool:
    """His answer #1 read word for word: house tier High / EXTREME + the CARD's float at or under the cap."""
    from chart_maps.gajjala import constants as GC
    from chart_maps.gajjala import high_si as HS
    tier = blk.get("tier") if isinstance(blk, dict) else None
    cf = HS.float_shares(fr)
    return tier in HS.TIERS and cf is not None and cf <= GC.HIGH_SI_MAX_FLOAT


def listed_since(sym: str, day: str, scan_today: dict, earlier: set) -> Optional[datetime]:
    """When the name joined the list this session: None = listed all session (carried from an earlier window day, or
    no stamp on file); else the scan doc's `first_qualified_at` in ET (only when it is on that day)."""
    if sym in earlier or sym not in scan_today:
        return None
    fq = _et((scan_today.get(sym) or {}).get("first_qualified_at"))
    return fq if fq is not None and fq.date().isoformat() == day else None


def cross_rings(doc: dict, session: date, *, since: Optional[datetime] = None) -> dict:
    """{tf: {"up": n, "gated": [ok_floor bool per gated cross]}} for one read doc's stored tiles — the run_step gates."""
    from chart_maps.gajjala import alerts as AL
    from chart_maps.gajjala import constants as GC
    from chart_maps.gajjala import potential as PT
    from chart_maps.gajjala import tab as GT
    from chart_maps.gajjala import variant as V
    day = session.isoformat()
    f5 = GT._tile_frame(doc, "5m", V.GG5)
    today5 = [b for b in f5.get("bars") or [] if isinstance(b, dict) and str(b.get("t") or "")[:10] == day]
    out = {}
    for tf in GC.HIGH_SI_CROSS_FRAMES:
        fr = f5 if tf == "5m" else GT._tile_frame(doc, tf, V.GG5)
        ups = [x for x in ((GT.ema_cross_block(fr) or {}).get("crosses") or [])
               if x.get("dir") == "up" and str(x.get("t") or "")[:10] == day]
        gated = []
        for x in ups:
            w = AL.window_reason(x["t"], session, tf)
            if w in ("suppressed_first15", "suppressed_window"):
                continue
            label = AL.bar_close_et(x["t"])
            pass_at = label + timedelta(seconds=GC.BAR_SETTLE_SEC)
            if PT.window_reason(pass_at, session) == "outside_hours":
                continue
            if since is not None and pass_at < since:
                continue
            vol = 0.0
            for b in today5:
                if str(b["t"]) <= x["t"]:
                    try:
                        vol += float(b.get("v") or 0)
                    except (TypeError, ValueError):
                        pass
            gated.append(vol >= GC.K11_MIN_SESSION_VOLUME)
        out[tf] = {"up": len(ups), "gated": gated}
    return out


def count_session(st, session: date, blocks: dict) -> dict:
    """One session's frequency table (reads only)."""
    from chart_maps.gajjala import high_si as HS
    from chart_maps.gajjala import scanner as SC
    from chart_maps.gajjala import tab as GT
    day = session.isoformat()
    listed = SC.listed_symbols(st, session)
    win = [w.isoformat() for w in SC._window(session)]
    scan_today, earlier = {}, set()
    for d in st.scan_docs(SC._window(session)):
        s = str(d.get("symbol") or "").upper()
        if d.get("date") == day:
            scan_today[s] = d
        elif d.get("date") in win:
            earlier.add(s)
    reads = {str(d["symbol"]).upper(): d for d in (st.reads(session) or [])
             if isinstance(d, dict) and d.get("symbol") and str(d["symbol"]).upper() in {k.upper() for k in listed}}
    reasons, members, literal = Counter(), [], []
    for s, d in sorted(reads.items()):
        fr = GT._float_read(d, None)
        cl = HS.classify((blocks or {}).get(s), fr)
        if literal_member((blocks or {}).get(s), fr):
            literal.append(s)
        if cl.get("listed"):
            members.append(s)
        else:
            reasons[cl.get("reason")] += 1
    up = Counter()
    rings = {lt: {"floor": Counter(), "no_floor": Counter()} for lt in LATCH_WORDS}
    for s in members:
        res = cross_rings(reads[s], session, since=listed_since(s, day, scan_today, earlier))
        for tf, r in res.items():
            up[tf] += r["up"]
            ok = [g for g in r["gated"] if g]
            rings["cross"]["floor"][tf] += len(ok)
            rings["cross"]["no_floor"][tf] += len(r["gated"])
            rings["session"]["floor"][tf] += 1 if ok else 0
            rings["session"]["no_floor"][tf] += 1 if r["gated"] else 0
    return {"session": day, "reads": len(reads), "members": members, "n_members": len(members),
            "literal": literal, "n_literal": len(literal), "reasons": dict(reasons), "up_crosses": dict(up),
            "rings": {lt: {k: dict(v, total=sum(v.values())) for k, v in r.items()} for lt, r in rings.items()}}


def _pushes(day: str, db=None) -> dict:
    """{kind: n delivered (sent > 0)} of that ET day — ONE push_history find. Never writes, never builds an index."""
    d = date.fromisoformat(day)
    a = int(datetime(d.year, d.month, d.day, tzinfo=ET).timestamp())
    b = a + 86400
    if db is None:
        from short_interest import read as SR
        db = SR.SIC._get_db()
    if db is None:
        return {}
    c = Counter()
    for r in db["push_history"].find({"ts": {"$gte": a, "$lt": b}, "sent": {"$gt": 0}}, {"kind": 1}):
        c[str(r.get("kind"))] += 1
    return dict(c)


def run(n: int, *, store=None, si_read: Optional[Callable] = None, pushes: bool = False,
        pushes_read: Optional[Callable] = None, today: Optional[date] = None) -> dict:
    from chart_maps.gajjala import constants as GC
    from chart_maps.gajjala import high_si as HS
    from chart_maps.gajjala import store as ST
    st = store if store is not None else ST.default()
    days = sorted(d for d in (st.coll(ST.READS).distinct("date") or []) if isinstance(d, str))[-max(1, int(n)):]
    today = today or datetime.now(ET).date()
    out = {"honesty": list(HONESTY), "latches": LATCH_WORDS, "built_latch": GC.HIGH_SI_CROSS_LATCH,
           "floor": GC.K11_MIN_SESSION_VOLUME, "cap": GC.HIGH_SI_MAX_FLOAT, "si_as_of": today.isoformat(),
           "sessions": []}
    for day in days:
        session = date.fromisoformat(day)
        syms = sorted({str(d.get("symbol") or "").upper() for d in (st.reads(session) or []) if isinstance(d, dict)}
                      - {""})
        blocks = (si_read or (lambda s: HS.si_blocks(s, today=today)))(syms)
        if blocks is None:
            out["sessions"].append({"session": day, "error": "short interest unread"})
            continue
        row = count_session(st, session, blocks)
        if pushes:
            row["pushes"] = (pushes_read or _pushes)(day)
        out["sessions"].append(row)
    return out


def _print(res: dict) -> None:
    for h in res["honesty"]:
        print(h)
    for r in res["sessions"]:
        if r.get("error"):
            print("==", r["session"], r["error"])
            continue
        c, s = r["rings"]["cross"], r["rings"]["session"]
        print("== %s reads %d | members %d (literal %d) | up crosses %s" % (r["session"], r["reads"], r["n_members"],
                                                                          r["n_literal"], r["up_crosses"]))
        print("   not listed", r["reasons"])
        print("   rings one per cross: %d (no floor %d) | one per session: %d (no floor %d)"
              % (c["floor"]["total"], c["no_floor"]["total"], s["floor"]["total"], s["no_floor"]["total"]))
        if "pushes" in r:
            print("   delivered pushes that day", sum(r["pushes"].values()), r["pushes"])
        print("   members", r["members"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="scripts.gajjala_high_si_cross_count", description=__doc__.split("\n")[0])
    ap.add_argument("--sessions", type=int, default=5, help="the newest N stored sessions")
    ap.add_argument("--pushes", action="store_true", help="add that day's delivered pushes per kind")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    res = run(a.sessions, pushes=a.pushes)
    if a.json:
        print(json.dumps(res, indent=1, default=str))
    else:
        _print(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
