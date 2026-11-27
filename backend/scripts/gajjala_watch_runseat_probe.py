"""📅 Runners kept two weeks — READ-ONLY probe (spec watchrun rev 2 §4 WP-1 step 4, 2026-11-26).

Prints every name that would seat at the NEXT first minute step, under EACH of the three readings, with its rule, run
day and day N; every name that ran but is not seated with its reason (HZN, ANT, SRTM by name); the pending items; and
BGLC / POM / NCPL by name or why not.

The container runs origin/main, where `chart_maps.gajjala_watch.runseat` does not exist yet: this script RE-IMPLEMENTS
the small judging piece from the house engines that are on main (runners.ran_of, ledger.rows_for / session_bounds /
fill_window / SETTLE / _default_split_lookup, runchart.cached_at, the 1-minute day cache) and a repo test
(tests/test_gajjala_watch_runseat_probe_2026_11_26.py) pins it equal to the engine on fixtures.

Read-only: sub-second finds, one session at a time with a pause between, NO provider read by default — a ring or a
day whose split check is not on file prints "split check not asked" (pending). `--splits` (OFF HOURS ONLY) asks each
through the house lookup, one reference read per item, a pause between. Nothing is written, nothing rings.

    docker exec -i -w /app cheetah-market-app-api-1 python - < backend/scripts/gajjala_watch_runseat_probe.py
    docker exec -i -w /app cheetah-market-app-api-1 python - --splits < backend/scripts/gajjala_watch_runseat_probe.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

if "/app" not in sys.path and os.path.isdir("/app"):
    sys.path.insert(0, "/app")

from chart_maps.gajjala import ledger as L                       # noqa: E402
from chart_maps.gajjala_watch import constants as C              # noqa: E402
from chart_maps.gajjala_watch import runners as RN               # noqa: E402

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
# the engine's numbers BY NAME when this branch is deployed; on origin/main the copies below (a repo test pins them)
READINGS = tuple(getattr(C, "RUNNERS_SEAT_READINGS", ("after_aplus", "seat_cut", "either")))
DAY_PCT = float(getattr(C, "RUNNERS_SEAT_DAY_PCT", C.RAN_MIN_PCT))
APLUS_PCT = getattr(C, "RUNNERS_SEAT_APLUS_PCT", 30)
KEEP = int(getattr(C, "RUNNERS_KEEP_SESSIONS", 10))
PAGES = tuple(getattr(C, "RUNNERS_SEAT_PAGES", ("gajjala", "gajjala_1m")))
PAUSE_SEC = 0.25                                                   # between sessions / provider asks — transport only
WATCH = ("BGLC", "POM", "NCPL", "HZN", "ANT", "SRTM")


# ── the judging piece (== runseat._judge, pinned by a repo test) ───────────────────────────────────────────────────
def _fin(x):
    return RN._fin(x)


def play_day(ring_date: date, at: datetime) -> date:
    return L.session_bounds(ring_date, at)["same_date"]


def measure(bars, day: date, at: datetime, trigger, pct=APLUS_PCT) -> dict:
    """The run from the A+ trigger — runseat.from_trigger re-implemented (replay_win30.measure's window)."""
    from daytrading.data import ET_AFTERHOURS_CLOSE
    t = _fin(trigger)
    if t is None or t <= 0:
        return {"why": "aplus_no_trigger"}
    if not isinstance(at, datetime):
        return {"why": "aplus_no_time"}
    opens = datetime.combine(day, L.fill_window(day)[0], tzinfo=ET).astimezone(UTC)
    start = max(at.astimezone(UTC) + L.SETTLE, opens)
    end = datetime.combine(day, ET_AFTERHOURS_CLOSE, tzinfo=ET).astimezone(UTC)
    best = None
    for b in bars or []:
        ts, hi = b[0], _fin(b[2])
        if hi is not None and start <= ts < end and (best is None or hi > best[0]):
            best = (hi, ts)
    if best is None:
        return {"why": "aplus_no_bars"}
    hp = best[0]
    passed = Decimal(repr(float(hp))) * 100 >= Decimal(repr(float(t))) * (100 + Decimal(str(pct)))
    return {"why": "", "passed": passed, "run_pct": round((hp / t - 1) * 100, 1), "raw_pct": (hp / t - 1) * 100,
            "high": hp, "high_et": best[1].astimezone(ET).strftime("%H:%M")}


def judge(S: date, *, reading: str, scan_by: dict, reads_by: dict, rings: list, checks_of, daily_ok_of, stamp_of,
          bars_of, look, now: datetime, ask: bool, day_of=None) -> dict:
    """One completed session under one reading → {"seats": {SYM: rule}, "not_seated": {(SYM, why)},
    "pending": {(SYM, why)}}. `look(sym, after, through)` → True | iso | False | None; `ask` False = only the scanner's
    stored record answers a split (the probe's default — no provider read). `day_of(iso)` → (scan_by, reads_by) of the
    ring's own day (an after-close ring that ran on its ring day)."""
    iso = S.isoformat()
    aplus_on = reading in (READINGS[0], READINGS[2])
    skip_rel = reading == READINGS[0]
    cut = float(APLUS_PCT) if reading == READINGS[1] else DAY_PCT
    related = {r["symbol"] for r in rings if r["date"] == iso or r["play_day"] == iso}
    seats, not_seated, pending = {}, set(), set()
    ran = {s: RN.ran_of(d, reads_by.get(s), S) for s, d in scan_by.items()}

    def split(sym, after, through):
        if through <= after:
            return False
        one = L._next_market_day(after) == through and (checks_of(through) or {}).get(sym) in ("ok", "held")
        if not one and not ask:
            return None
        try:
            return look(sym, after, through)
        except Exception:                                            # noqa: BLE001
            return None

    best, under = {}, {}
    if aplus_on:
        for r in rings:
            if r["play_day"] != iso:
                continue
            sym = r["symbol"]
            if _fin(r.get("trigger")) is None or _fin(r.get("trigger")) <= 0:
                not_seated.add((sym, "aplus_no_trigger"))
                continue
            if not isinstance(r.get("at_utc"), datetime):
                not_seated.add((sym, "aplus_no_time"))
                continue
            stamp = stamp_of(sym, iso)
            fetched = stamp.astimezone(ET).date() if stamp is not None else now.astimezone(ET).date()
            v = split(sym, date.fromisoformat(r["date"]), fetched)
            if v is None:
                pending.add((sym, "aplus_split_unchecked" if ask else "aplus_pending"))
                continue
            if v is not False:
                not_seated.add((sym, "aplus_split"))
                continue
            bars = bars_of(sym, iso)
            if bars is None:
                pending.add((sym, "aplus_pending"))
                continue
            m = measure(bars, S, r["at_utc"], r["trigger"])
            if m["why"]:
                not_seated.add((sym, m["why"]))
            elif m["passed"]:
                best[sym] = "aplus"
            else:
                under[sym] = r["date"]
    day = {}
    for sym in scan_by:
        if skip_rel and sym in related:
            continue
        r = ran[sym]
        if r is None or r["premarket_peak"] or r["run_pct"] < cut:
            continue
        if (checks_of(S) or {}).get(sym) != "ok":
            v = split(sym, L._prev_market_day(S), S)
            if v is None:
                pending.add((sym, "split_unchecked"))
                continue
            if v is not False:
                not_seated.add((sym, "split_day"))
                continue
        ok = daily_ok_of(sym, iso)
        if ok is not True:
            not_seated.add((sym, "prior_unknown" if ok is None else "no_prior_bar"))
            continue
        day[sym] = "day"
    seats.update(day)
    seats.update(best)
    for sym, rdate in under.items():
        if sym in seats:
            continue
        r = ran.get(sym)
        counted = r is not None and r["counts"]
        if not counted and rdate != iso and day_of is not None:
            sb, rb = day_of(rdate)
            r0 = RN.ran_of(sb[sym], rb.get(sym), date.fromisoformat(rdate)) if sym in sb else None
            counted = r0 is not None and r0["counts"]
        if counted:
            not_seated.add((sym, "aplus_under"))
    return {"seats": seats, "not_seated": not_seated, "pending": pending}


# ── the live reads (read-only) ───────────────────────────────────────────────────────────────────────────────────
def _next_step_session(now: datetime) -> date:
    from catalysts.medical.reaction import next_market_day
    from chart_maps.gajjala import run as RUN
    d = now.astimezone(ET).date()
    if RUN.in_window(now) or (now.astimezone(ET).hour < 4 and next_market_day(d - timedelta(days=1)) == d):
        return d
    return next_market_day(d)


def _window(session: date) -> list:
    from catalysts.medical.reaction import next_market_day
    from chart_maps.gajjala import context as CX
    return list(CX.history_window(next_market_day(session), KEEP))


def _rings(dates, stores) -> list:
    from chart_maps.gajjala import variant as V
    vs = {v.key: v for v in V.VARIANTS}
    out = []
    for page in PAGES:
        for r in L.rows_for(list(dates), stores[page], variant=vs[page]):
            if r.get("kind") != L.KINDS[1] or r.get("line") not in L.LINES[:2]:
                continue
            at = r.get("at_utc") if isinstance(r.get("at_utc"), datetime) else None
            d = date.fromisoformat(r["date"])
            out.append({"id": r["id"], "page": page, "date": r["date"], "symbol": str(r["symbol"]).upper(),
                        "at_utc": at, "at_et": r.get("at_et"), "trigger": r.get("trigger"),
                        "play_day": (play_day(d, at) if at else d).isoformat()})
    return out


def _cached_bars(sym, iso):
    """The cached 1-minute day ONLY (daytrading.data._mongo_get_day) — never a provider read; None when not cached."""
    from daytrading import data as dt_data
    from sepa.symbols import for_massive
    df = dt_data._mongo_get_day(for_massive(sym), date.fromisoformat(iso))
    if df is None or df.empty:
        return None
    return L.bars_from_frame(dt_data._filter_sessions(df, True, True))


def _sidecars(root: Path) -> dict:
    out = {}
    if not root.is_dir():
        return out
    for p in root.glob("*/*.json"):
        try:
            j = json.loads(p.read_text())
        except Exception:                                            # noqa: BLE001
            continue
        if isinstance(j, dict) and j.get("ring_id") and isinstance(j.get("win30"), dict):
            out[j["ring_id"]] = j["win30"]
    return out


def _his_x() -> set:
    """{(SYM, ISO)} — his × pairs as the engine reads them (the ✅ doc's `dismissed` pairs ∪ the 🤖 doc's `dismissed` of
    its session; on this branch the runners doc's own too). Two find_one reads; a fault → empty (printed)."""
    from chart_maps.gajjala_watch import colls as CO
    out = set()
    try:
        cs = CO.colls()
        for _id in ("rules", "runners"):
            d = cs["list"].find_one({"_id": _id}) or {}
            for r in d.get("dismissed") or []:
                if isinstance(r, dict) and isinstance(r.get("symbol"), str):
                    for k in ("session", "run_day"):
                        if isinstance(r.get(k), str):
                            out.add((CO.fold(r["symbol"]), r[k]))
        a = cs["list"].find_one({"_id": "auto"}) or {}
        for s in a.get("dismissed") or []:
            if isinstance(s, str) and isinstance(a.get("session"), str):
                out.add((CO.fold(s), a["session"]))
    except Exception as exc:                                          # noqa: BLE001
        print(f"his × record unreadable ({type(exc).__name__}) — nothing marked blocked")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--splits", action="store_true", help="ask split checks through the house lookup (OFF HOURS)")
    ap.add_argument("--session", help="the next step's session YYYY-MM-DD (default: computed)")
    ap.add_argument("--sidecars", default="/Users/ajay/clinet-test/eod-audits/replays/videos")
    a = ap.parse_args(argv)
    from chart_maps.gajjala import store as GST
    from chart_maps.gajjala import variant as V
    from chart_maps.gajjala_watch import runchart as RC
    now = datetime.now(UTC)
    if a.splits:
        h = now.astimezone(ET)
        if h.weekday() < 5 and (9, 30) <= (h.hour, h.minute) < (16, 0):
            print("--splits refused during 09:30–16:00 ET")
            return 2
    session = date.fromisoformat(a.session) if a.session else _next_step_session(now)
    win = _window(session)
    todo = [d for d in win if d < session]
    st = GST.default()
    stores = {V.GG5.key: st, V.GG1.key: GST.for_variant(V.GG1)}
    look = L._default_split_lookup(st)
    rings = _rings(sorted(set(todo) | {L._prev_market_day(d) for d in todo}), stores)
    side = _sidecars(Path(a.sidecars))
    print(f"📅 runseat probe — next step session {session} · window {win[0]} → {win[-1]} · {len(rings)} A+ rings · "
          f"splits {'ASKED' if a.splits else 'stored only'}")
    checks: dict = {}

    def checks_of(d):
        iso = d.isoformat()
        if iso not in checks:
            checks[iso] = st.split_checks(d) or {}
        return checks[iso]

    def daily_ok_of(sym, iso):
        doc = st.get_daily(date.fromisoformat(iso), sym)
        sh = doc.get("squeeze_history") if isinstance(doc, dict) else None
        return None if not isinstance(sh, dict) else (sh.get("daily_ok") is True)

    asked: dict = {}

    def asked_look(sym, after, through):
        k = (sym, after, through)
        if k not in asked:                                            # ONE reference read per item, all readings
            time.sleep(PAUSE_SEC)
            asked[k] = look(sym, after, through)
        return asked[k]

    blocked = _his_x()

    stamps: dict = {}

    def stamp_of(sym, iso):
        if (sym, iso) not in stamps:
            stamps[(sym, iso)] = RC.cached_at(sym, [iso]).get(iso)
        return stamps[(sym, iso)]

    days = {}
    for d in todo:
        days[d.isoformat()] = RN.read_day(st, d.isoformat())
        time.sleep(PAUSE_SEC)
    totals = {}
    for rd in READINGS:
        seats, ns, pend = {}, [], []
        for d in todo:
            scan_by, reads_by = days[d.isoformat()]
            j = judge(d, reading=rd, scan_by=scan_by, reads_by=reads_by, rings=rings, checks_of=checks_of,
                      daily_ok_of=daily_ok_of, stamp_of=stamp_of, bars_of=_cached_bars,
                      look=asked_look if a.splits else look, now=now, ask=a.splits,
                      day_of=lambda iso: days.get(iso) or RN.read_day(st, iso))
            for sym, rule in j["seats"].items():
                if (sym.replace(".", "-"), d.isoformat()) in blocked or (sym, d.isoformat()) in blocked:
                    ns.append((d, sym, f"blocked by your × ({rule} rule) — written to removed"))
                    continue
                seats.setdefault(sym, []).append((d, rule))
            ns += [(d, s, w) for s, w in sorted(j["not_seated"])]
            pend += [(d, s, w) for s, w in sorted(j["pending"])]
        run_days = sum(len(v) for v in seats.values())
        totals[rd] = (run_days, len(seats))
        print(f"\n── reading {rd!r}: {run_days} run-days · {len(seats)} names ──")
        for sym in sorted(seats, key=lambda s: (-seats[s][-1][0].toordinal(), s)):
            d, rule = seats[sym][-1]
            n = len(win) - win.index(d)
            print(f"  {sym:<6} {rule:<5} run day {d} · day {n} of {KEEP}" + (f" · {len(seats[sym])} runs"
                                                                           if len(seats[sym]) > 1 else ""))
        for d, s, w in ns:
            print(f"  not seated  {s:<6} {d} {w}")
        for d, s, w in pend:
            print(f"  pending     {s:<6} {d} {w}" + ("" if a.splits else " (split check not asked)"
                                                   if "split" in w or w == "aplus_pending" else ""))
        for sym in WATCH:
            hit = seats.get(sym)
            why = [f"{d} {w}" for d, s, w in ns + pend if s == sym]
            print(f"  · {sym}: " + (f"seated {hit[-1][1]} {hit[-1][0]}" if hit else ("; ".join(why) or "not a runner")))
    for r in rings:
        w30 = side.get(r["id"])
        if w30:
            print(f"  🎬 {r['id']}: sidecar win30 run_pct {w30.get('run_pct')} label {w30.get('label')}")
    print("\ntotals: " + " · ".join(f"{k} {v[0]} run-days / {v[1]} names" for k, v in totals.items()))
    print("READ-ONLY — nothing written, nothing rang. UNMEASURED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
