"""🔢 Watch float probe (2026-11-21, spec watchfloat §4 step 5) — READ-ONLY.

Ajay 2026-11-21, verbatim: "can you add the current float value also to the tickers on the watch list."

Runs the branch's `float_read.section` against live data from a THROWAWAY container (the worktree mounted read-only,
PYTHONPATH=/repo/backend) and re-implements the chain with the SAME engine calls to pin equality. Never fetches, never
writes, never touches the live api process. Prints:
  * n, cache ms, daily ms, hits by read_from, the miss list, each name's text and title, EQUAL / DIFF;
  * [C2] the per-name cache age table (age days, days left before the TTL cliff, status) from ONE `$in` find;
  * [C3] new threads + ResourceWarnings around 3× section (expected 0 / 0) vs ONE 36-call default-path loop;
  * --build: PL.build(db=db) 3× with floats and 3× with FLOAT_MODULE pointed at a missing module; medians + delta.

Usage: python scripts/watch_float_probe.py [--build]
"""
from __future__ import annotations

import gc
import os
import statistics
import sys
import threading
import time
import warnings

from pymongo import MongoClient

from chart_maps.gajjala import context as CX
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import float_read as FR
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import tags as TG
from sepa import volume_movers as VM


def _ms(t0):
    return round((time.perf_counter() - t0) * 1000, 1)


def _names(db, now):
    session, is_today, _w = PL._session_of(now)
    siso = session.isoformat()[:10]
    cs = CO.colls(db)
    ldoc = CO.owner_doc(db, strict=True)
    his = CO.newest_first(CO.symbols_of(ldoc), CO.added_of(ldoc))
    _state, entries, _removed = PL.auto_read(cs, his, siso)
    auto = [e["symbol"] for e in entries]
    return session, is_today, his, auto


def _reimpl(db, names, session, now, tags_by):
    """The chain with the SAME engine calls: pass → shares_status(cache only, the handle) + _yf_read → ONE $in memo."""
    h = db[VM.SHARES_COLL]
    out, misses, status = {}, [], {}
    t0 = time.perf_counter()
    for s in names:
        chip = (tags_by.get(s) or {}).get("float") if isinstance(tags_by.get(s), dict) else None
        if isinstance(chip, dict) and chip.get("text"):
            out[s] = (chip["text"], "pass")
            continue
        vals, st = VM.shares_status(s, fetch=False, coll=h)
        status[s] = st
        fr = CX._yf_read(vals, st, now) if st in CX._USABLE else None
        if fr is None:
            misses.append(s)
        else:
            out[s] = (tab._float_chip(fr)["text"], "cache")
    cache_ms = _ms(t0)
    t0 = time.perf_counter()
    docs = {}
    if misses:
        ids = {ST.key(session.isoformat()[:10], s): s for s in misses}
        for d in db[ST.DAILY].find({"_id": {"$in": list(ids)}}, FR.DAILY_FIELDS):
            docs[ids[d["_id"]]] = d
    daily_ms = _ms(t0)
    for s in misses:
        fr = FR.memo_read(docs.get(s), now)
        if fr is not None:
            out[s] = (tab._float_chip(fr)["text"], "memo")
    return out, status, cache_ms, daily_ms


def _age_table(db, names, now_ts, status):
    rows = {d["_id"]: d for d in db[VM.SHARES_COLL].find({"_id": {"$in": list(names)}},
                                                          {"as_of": 1, "rl_until": 1})}
    print("\n[C2] cache age table (days; left = ttl_days - age)")
    print(f"{'SYM':<8}{'age':>7}{'left':>7}  status")
    for s in sorted(names, key=lambda n: -(now_ts - float((rows.get(n) or {}).get("as_of") or 0))):
        d = rows.get(s)
        if not d or not d.get("as_of"):
            print(f"{s:<8}{'—':>7}{'—':>7}  {status.get(s, 'missing')} (no row)")
            continue
        age = (now_ts - float(d["as_of"])) / 86400
        print(f"{s:<8}{age:>7.1f}{FR.ttl_days() - age:>7.1f}  {status.get(s)}")


def _threads_warnings(fn):
    gc.collect()
    before = threading.active_count()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fn()
    n_warn = sum(1 for w in caught if issubclass(w.category, ResourceWarning))
    return threading.active_count() - before, n_warn


def main(argv):
    db = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"), serverSelectionTimeoutMS=4000)[
        os.getenv("MONGO_DB", "cheetah")]
    import portfolio.store as PS
    PS._db = db                                                         # _get_db never runs its create_index here
    st = ST.GajjalaStore({ST.DAILY: db[ST.DAILY], VM.SHARES_COLL: db[VM.SHARES_COLL]})
    FR._store = lambda: st
    now = PL._now(None)
    session, is_today, his, auto = _names(db, now)
    names = his + [a for a in auto if a not in his]
    print(f"session {session} · his {len(his)} · auto {len(auto)} · n {len(names)}")
    tags_by = TG.section(names, session, is_today)

    t0 = time.perf_counter()
    got = FR.section(names, session, now, tags_by)
    section_ms = _ms(t0)
    want, status, cache_ms, daily_ms = _reimpl(db, names, session, now, tags_by)
    by = {}
    for s in names:
        f = got.get(s)
        by[f["read_from"] if f else "none"] = by.get(f["read_from"] if f else "none", 0) + 1
    print(f"section {section_ms} ms · re-impl cache {cache_ms} ms ({round(cache_ms / max(len(names), 1), 2)} ms/name)"
          f" · daily {daily_ms} ms")
    print("hits by read_from:", by)
    print("misses:", [s for s in names if s not in got])
    equal = True
    for s in names:
        f = got.get(s)
        mine = (f["text"], f["read_from"]) if f else None
        ok = mine == want.get(s)
        equal = equal and ok
        print(f"  {s:<7} {'EQUAL' if ok else 'DIFF '} {mine} | title: {f['title'] if f else None}")
    print("RE-IMPL vs FR.section:", "EQUAL" if equal else "DIFF")
    _age_table(db, names, now.timestamp(), status)

    dt, dw = _threads_warnings(lambda: [FR.section(names, session, now, tags_by) for _ in range(3)])
    print(f"\n[C3] 3x FR.section: new threads {dt}, ResourceWarnings {dw}")
    loop = [names[i % len(names)] for i in range(36)] if names else []
    dt2, dw2 = _threads_warnings(lambda: [VM.shares_status(s, fetch=False) for s in loop])
    print(f"[C3] 36x default-path shares_status (no handle): new threads {dt2}, ResourceWarnings {dw2}")

    if "--build" in argv:
        def run(n=3):
            ms = []
            for _ in range(n):
                t0 = time.perf_counter()
                out = PL.build(now, db=db)
                ms.append(_ms(t0))
            return statistics.median(ms), out
        with_f, out = run()
        real = PL.FLOAT_MODULE
        PL.FLOAT_MODULE = "chart_maps.gajjala_watch._no_float_module_probe"
        without, _o = run()
        PL.FLOAT_MODULE = real
        n_float = sum(1 for r in out.get("rows") or [] if r.get("float"))
        print(f"\n--build: with floats {with_f} ms · without {without} ms · delta {round(with_f - without, 1)} ms · "
              f"rows {len(out.get('rows') or [])} · rows with float {n_float} · state {out.get('state')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
