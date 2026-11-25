"""⛔🔒 What the SI / SSR / Reg SHO add source WOULD have added and read on one session — READ-ONLY, APPROXIMATE
(2026-11-24, SPEC sissr rev 2 §1.2 / §5.2, WP be-pass).

Ajay 2026-11-24 ~23:35 ET, verbatim: "Days past little bit like AKAN is what I am mainly looking for many were so
confident on SSR..".

COUNTS ONLY — NOT AN EDGE, not a win rate, not a forecast. Nothing here rings: under rev 2 an added name is SEATED, never
rung (C1, HIS CALL #6). For `--date D` (run it after 20:00 ET on D itself — the snapshot is today's):

  * the module's OWN path end to end — si_ssr_names.default_reader at 20:30 ET of D → source_tags → resolve (the ONE add
    check, trader_names.candidate_row, + ADD_MIN_VOLUME) against today's snapshot and the stored type map, with the
    session's listed set; every skip counted by reason;
  * the eligible adds in the module's order and the pass clock each would land on under ADD_MAX_NEW_PER_PASS from the
    first pass clock (`landing_clocks`);
  * for each eligible add, GG's five detectors on CLOSED 5m / 15m bars at every pass clock of D (bars.build_frames),
    the first 🧠 potential and the first trigger-armed read. A ⛔-today-only name is counted only after its trigger
    minute (ssr.new_triggers' `at_et`).

APPROXIMATIONS (C12) — never quote the result as measured:
  * the add check uses the 20:30 snapshot at EVERY pass clock (lookahead: a name may not have qualified at 10:00);
  * K11 reads the minute-volume sum through the pass clock, not the snapshot the pass read;
  * floats: cache + Massive shares-out only (no Yahoo refinement); fresh tape and the per-pass bound are not modelled
    in the detector replay (every eligible add is read at every clock).

READ-ONLY: Mongo reads, the minute fetch WITHOUT the cache write (run._dry_load_day), the float cache WITHOUT a fetch
(run._dry_status_lookup) — no write, no index build, no send.

    docker exec -i -w /app <throwaway container on the branch> python -m scripts.gajjala_si_ssr_replay \\
        --date 2026-11-24 --out /tmp/sissr_replay.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time as _time
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
READ_AT_ET = time(20, 30)                        # the read clock: after the 20:00 close, every list of D is on file


def pass_clocks(day: date) -> list:
    """Every 🚩 pass clock of D: PASS_OPEN_ET + PASS_MINUTE_OFFSET, every PASS_CADENCE_SEC, through PASS_CLOSE_ET
    (04:01 … 20:01 — the cron line's minutes)."""
    from chart_maps.gajjala import constants as GC
    t = datetime.combine(day, time.fromisoformat(GC.PASS_OPEN_ET), ET) + timedelta(minutes=GC.PASS_MINUTE_OFFSET)
    end = datetime.combine(day, time.fromisoformat(GC.PASS_CLOSE_ET), ET)
    out = []
    while t <= end:
        out.append(t)
        t += timedelta(seconds=GC.PASS_CADENCE_SEC)
    return out


def landing_clocks(eligible: list, clocks: list, per_pass: int) -> dict:
    """PURE. {SYM: "HH:MM"} — the pass each eligible add lands on when at most `per_pass` NEW names are added a pass,
    in `eligible`'s order from the first clock. Names past the last clock map to None."""
    out: dict = {}
    for i, sym in enumerate(eligible):
        k = i // per_pass if per_pass > 0 else len(clocks)
        out[sym] = clocks[k].strftime("%H:%M") if k < len(clocks) else None
    return out


def _first_reads(sym: str, day: date, prev: date, clocks: list, float_read, after_hhmm: Optional[str]) -> dict:
    from chart_maps.gajjala import bars as B
    from chart_maps.gajjala import constants as GC
    from chart_maps.gajjala import detectors as DT
    from chart_maps.gajjala import potential as PT
    from chart_maps.gajjala import run as RUN
    from sepa.symbols import for_massive
    rp = RUN._dry_load_day(for_massive(sym), prev, include_premarket=True, include_afterhours=True)
    rt = RUN._dry_load_day(for_massive(sym), day, include_premarket=True, include_afterhours=True)
    if rt is None or rt.empty:
        return {"err": "no_bars_today"}
    idx = rt.index.tz_localize("UTC") if rt.index.tz is None else rt.index.tz_convert("UTC")
    first = first_armed = None
    n_pot = 0
    for c in clocks:
        hm = c.strftime("%H:%M")
        if after_hhmm is not None and hm <= after_hhmm:
            continue
        cu = c.astimezone(timezone.utc)
        mask = idx < cu
        if not mask.any():
            continue
        cut = rt[mask]
        sv = float(cut["volume"].sum()) if "volume" in cut else None
        fr = B.build_frames(sym, day, cu, rp, cut)
        if fr is None:
            continue
        reads = DT.read_all(fr.detector_frames(), {"symbol": sym, "float_read": float_read, DT.K11_CTX_KEY: sv})
        for setup, rd in (reads or {}).items():
            k = PT.potential_kind(rd)
            if k is None:
                continue
            n_pot += 1
            if first is None:
                first = {"at_et": hm, "setup": setup, "kind": k}
            if k == GC.POTENTIAL_KINDS[0] and first_armed is None:
                first_armed = {"at_et": hm, "setup": setup}
    return {"first": first, "first_armed": first_armed, "n_potential_reads": n_pot}


def run(day: date, *, limit: Optional[int] = None) -> dict:
    from catalysts.medical.reaction import prev_market_day
    from chart_maps.gajjala import constants as GC
    from chart_maps.gajjala import context as CX
    from chart_maps.gajjala import run as RUN
    from chart_maps.gajjala import scanner as SC
    from chart_maps.gajjala import si_ssr_names as SSN
    from chart_maps.gajjala import store as ST
    from sepa import prices
    from short_interest import ssr as SSR
    t0 = _time.time()
    now = datetime.combine(day, READ_AT_ET, ET)
    st = ST.default()
    listed = set(SC.listed_symbols(st, day))
    read = SSN.default_reader(now, day)
    tags = SSN.source_tags(read)
    rows, meta = prices.market_snapshot_with_meta(include_otc=GC.SCAN_INCLUDE_OTC)
    tdoc = st.types_map() or {}
    types = {p[0]: p[1] for p in (tdoc.get("pairs") or []) if isinstance(p, (list, tuple)) and len(p) == 2}
    res = SSN.resolve(tags, rows or {}, day, types, [], listed, on_open=False)
    eligible = [r["symbol"] for r in res["added"]] + list(res["queued"])
    clocks = pass_clocks(day)
    try:
        trig = {r.get("symbol"): (r.get("at_et") or "")[:5] or None
                for r in (SSR.new_triggers(day, now=now).get("rows") or []) if isinstance(r, dict)}
    except Exception as exc:                                    # noqa: BLE001
        logging.warning("new_triggers unread: %s", type(exc).__name__)
        trig = {}
    names = eligible[:limit] if limit else eligible
    floats = CX.floats_for(names, now=now, status_lookup=RUN._dry_status_lookup, store=None, session=day,
                           refine=False)
    prev = prev_market_day(day)
    per: dict = {}
    for sym in names:
        keys = list((tags.get(sym) or {}).keys())
        today_only = keys == [SSN.SSR_KEYS[1]]
        try:
            per[sym] = dict(_first_reads(sym, day, prev, clocks, floats.get(sym), trig.get(sym) if today_only
                                         else None), keys=keys, trigger_at_et=trig.get(sym))
        except Exception as exc:                                # noqa: BLE001
            per[sym] = {"err": type(exc).__name__, "keys": keys}
    reached = sorted(s for s, v in per.items() if v.get("first"))
    armed = sorted(s for s, v in per.items() if v.get("first_armed"))
    listed_tagged = sorted(s for s in tags if s in listed)
    return {"date": day.isoformat(), "read_at_et": now.isoformat(), "snapshot": {"http": (meta or {}).get("http"),
            "n": (meta or {}).get("n")},
            "faults": read.get("faults"), "tagged_names": len(tags), "listed_tagged": listed_tagged,
            "skips": {k: len(v) for k, v in res["skips"].items()}, "eligible": eligible,
            "landing": landing_clocks(eligible, clocks, SSN.ADD_MAX_NEW_PER_PASS),
            "per_name": per, "reached_potential": reached, "armed": armed, "approximate": True,
            "wall_s": round(_time.time() - t0, 1)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="scripts.gajjala_si_ssr_replay", description=__doc__.split("\n")[0])
    ap.add_argument("--date", required=True, help="the session, YYYY-MM-DD (run after 20:00 ET on that day)")
    ap.add_argument("--out", required=True, help="the JSON file to write the result to")
    ap.add_argument("--limit", type=int, default=None, help="replay only the first N eligible adds (a smoke run)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    out = run(date.fromisoformat(args.date), limit=args.limit)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, default=str, indent=1)
    print(f"{out['date']} — APPROXIMATE (20:30 snapshot at every clock; no Yahoo float; fresh tape not modelled)")
    print(f"tagged names {out['tagged_names']} · listed + tagged {len(out['listed_tagged'])} · "
          f"eligible adds {len(out['eligible'])} · skips {out['skips']}")
    print(f"~{len(out['reached_potential'])} reach a 🧠 potential, ~{len(out['armed'])} arm "
          "(seated under rev 2, never rung)")
    for s in out["reached_potential"]:
        v = out["per_name"][s]
        print(f"  {s} {v['first']['at_et']} {v['first']['setup']} {v['first']['kind']} · lands "
              f"{out['landing'].get(s)} · {','.join(v.get('keys') or [])}")
    print(f"wrote {args.out} in {out['wall_s']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
