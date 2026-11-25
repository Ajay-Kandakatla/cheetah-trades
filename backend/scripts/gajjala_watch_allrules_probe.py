"""✅ All rules met → 👀 Watch — the CONTAINER probe, read-only (2026-11-24, spec watchall rev 2 §5.2).

Ajay 2026-11-24, verbatim: "Anytime stocks qualify all his rules should be auto added to the Watch list so I can keep
tracking them later"

The container runs origin/main, where `gajjala_watch/allrules.py` does not exist yet. This script re-implements the
✅ seating rule from the pieces main already has, so the count the first step will seat can be read BEFORE deploy:

  armed   a 🧠 tracker doc of the session whose `state_path` carries a turn into (GC.POTENTIAL_STATE,
          GC.POTENTIAL_KINDS[0]) with a readable `at` — "trigger armed": every rule met, only the break missing
  K11     that session's volume (`auto.volume_of`: the scan row, else GG5's tracker) ≥ GC.K11_MIN_SESSION_VOLUME;
          unknown → `volume_unknown`, under → `under_floor` (armed reads only; a 🎯 A+ has no floor)
  🎯 A+   every 🤖 entry of THAT session with `why == C.AUTO_APLUS_WHY` (+ `aplus`, the live step's names, when given)
  then    his names → `yours` · his × that session (the 🤖 doc's `dismissed`) → `dismissed` · 🚫 → `not_eligible`
  seated  the rest

tests/test_gajjala_watch_allrules_probe_2026_11_24.py pins `expected` == `allrules.step(dry=True)` on the same fixture
(same session, empty ✅ doc, the 🤖 doc of that session = `auto_prior`) — the probe rule IS the engine's rule.

The probe writes nothing (find / find_one only). Expected on 11-24 (spec §5.2): ≈ 14 = 22 − his 6 − ×'d BAK, GLXG; his
list at the 04:00 step decides the 6.

  python -m scripts.gajjala_watch_allrules_probe [--date 2026-11-24]
  docker exec -i -w /app cheetah-market-app-api-1 python - --date 2026-11-24 < backend/scripts/gajjala_watch_allrules_probe.py

Display / tracking only. UNMEASURED.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

BACKEND = (str(Path(__file__).resolve().parents[1])
           if str(globals().get("__file__") or "").endswith(".py") else None)
if BACKEND and BACKEND not in sys.path and not __package__:
    sys.path.insert(0, BACKEND)

# The tracker projection the ✅ engine reads (C.RULES_TRACKER_FIELDS on the branch; main has no such constant — the
# repo test pins this copy equal to it).
TRACKER_FIELDS = {"symbol": 1, "setup": 1, "date": 1, "first_seen": 1, "state_path": 1, "last.at": 1,
                  "last.session_volume": 1}
OUT_KEYS = ("seated", "armed", "aplus", "under_floor", "volume_unknown", "yours", "dismissed", "not_eligible")


def _at(x) -> Optional[datetime]:
    if isinstance(x, datetime):
        return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    if isinstance(x, str) and x:
        try:
            t = datetime.fromisoformat(x)
        except ValueError:
            return None
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    return None


def armed_turn(doc) -> bool:
    """True when the doc's state_path holds a (forming, armed) turn with a readable `at`."""
    from chart_maps.gajjala import constants as GC
    path = doc.get("state_path") if isinstance(doc, dict) else None
    if not isinstance(path, list):
        return False
    want = (GC.POTENTIAL_STATE, GC.POTENTIAL_KINDS[0])
    return any(isinstance(e, dict) and (e.get("state"), e.get("kind")) == want and _at(e.get("at")) is not None
               for e in path)


def floor() -> float:
    from chart_maps.gajjala import constants as GC
    return GC.K11_MIN_SESSION_VOLUME


def expected(iso: str, *, tdocs_by_source: dict, shared: dict, manual, broker, auto_doc, aplus=()) -> dict:
    """{key: sorted house symbols} for OUT_KEYS. Pure over its inputs (no I/O). `broker` = folded 🚫 symbols."""
    from chart_maps.gajjala import potential as PT
    from chart_maps.gajjala_watch import auto as AUTO
    from chart_maps.gajjala_watch import colls as CO
    from chart_maps.gajjala_watch import constants as C
    out = {k: set() for k in OUT_KEYS}
    cand: dict = {}                                              # fold → house symbol of every qualifier
    scan_by = shared.get("scan_by") or {}
    trackers = shared.get("trackers")
    for key in AUTO.read_sources():
        for d in tdocs_by_source.get(key) or []:
            sym = AUTO._up(d.get("symbol")) if isinstance(d, dict) else ""
            if not sym or not armed_turn(d):
                continue
            out["armed"].add(CO.house(sym))
            vol, _src = AUTO.volume_of(sym, (scan_by.get(sym) or {}).get("last"), trackers)
            v = PT._num(vol)
            if v is None:
                out["volume_unknown"].add(CO.house(sym))
                continue
            if v < floor():
                out["under_floor"].add(CO.house(sym))
                continue
            cand.setdefault(CO.fold(sym), CO.house(sym))
    aps = [e["symbol"] for e in AUTO.entries_of(auto_doc, iso) if e.get("why") == C.AUTO_APLUS_WHY]
    for sym in aps + [s for s in aplus or [] if isinstance(s, str) and s.strip()]:
        out["aplus"].add(CO.house(sym))
        cand.setdefault(CO.fold(sym), CO.house(sym))
    # an armed read under the floor is still seated when the same name is an A+ — the engine's rule too
    for k in ("under_floor", "volume_unknown"):
        out[k] = {s for s in out[k] if CO.fold(s) not in cand}
    mk = {CO.fold(m) for m in manual or [] if isinstance(m, str)}
    xk = set()
    if isinstance(auto_doc, dict) and auto_doc.get("session") == iso:
        xk = {CO.fold(s) for s in auto_doc.get("dismissed") or [] if isinstance(s, str) and s.strip()}
    bk = {CO.fold(s) for s in broker or []}
    for k, sym in cand.items():
        if k in mk:
            out["yours"].add(sym)
        elif k in xk:
            out["dismissed"].add(sym)
        elif k in bk:
            out["not_eligible"].add(sym)
        else:
            out["seated"].add(sym)
    return {k: sorted(v) for k, v in out.items()}


def read(iso: str, *, db=None, stores=None) -> dict:
    """Every input of `expected` from the live stores — find / find_one only. Raises on a read fault (a probe, not a
    loop: an unknown is reported, never guessed)."""
    from chart_maps.gajjala import store as ST
    from chart_maps.gajjala import variant as V
    from chart_maps.gajjala_watch import auto as AUTO
    from chart_maps.gajjala_watch import colls as CO
    stores = stores if stores is not None else AUTO._default_stores()
    tdocs = {}
    for key in AUTO.read_sources():
        c = stores[key].coll(ST.POTENTIALS)
        tdocs[key] = list(c.find({"date": iso}, TRACKER_FIELDS))
    shared = AUTO.shared_sets(date.fromisoformat(iso), store=stores.get(V.GG5.key),
                              tracker_docs=tdocs.get(V.GG5.key))
    bk, bfault = AUTO.broker_gate(stores)
    if bfault:
        raise RuntimeError("🚫 broker list unreadable")
    cs = CO.colls(db)
    auto_doc = AUTO.read_doc(cs)
    if auto_doc is None:
        raise RuntimeError("🤖 auto doc unreadable")
    return {"tdocs_by_source": tdocs, "shared": shared, "manual": CO.owner_symbols(db, strict=True),
            "broker": sorted(bk), "auto_doc": auto_doc}


def run(iso: str, *, db=None, stores=None) -> dict:
    inp = read(iso, db=db, stores=stores)
    ex = expected(iso, **inp)
    ad = inp["auto_doc"]
    return {"session": iso, "auto_doc_session": ad.get("session"), "floor": floor(),
            "his_names": len(inp["manual"]), "counts": {k: len(v) for k, v in ex.items()}, **ex}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="session ISO (default: the 🤖 doc's session)")
    a = ap.parse_args(argv)
    iso = a.date
    if not iso:
        from chart_maps.gajjala_watch import auto as AUTO
        from chart_maps.gajjala_watch import colls as CO
        iso = (AUTO.read_doc(CO.colls()) or {}).get("session")
    print(json.dumps(run(iso), indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
