"""🧘 GG-like census (2026-11-27) — COUNTS of the 🧘 check over our own stored end-of-day carded reads. READ-ONLY.

NOT A MEASURED CLAIM: no outcome, no edge, no rate of anything but the check itself. It answers "how many of our cards
would read GG-like today" so the served sentence (gg_like.CENSUS / census_line) carries a dated, re-runnable number.

Carded = gajjala_watch.tags.carded_setups(doc) — the 🚩 board's own rule. One block per carded setup through
gg_like.doc_blocks (the engine's own bytes). Find-only on gajjala_reads: no write, no provider call, no file written.

Run after the deploy (backend/scripts has no __init__.py — never -m):
    docker exec -w /app -e PYTHONPATH=/app cheetah-market-app-api-1 python scripts/gg_like_census.py
Run BEFORE it, with the branch engine's bytes piped first (the container runs main, which has no gg_like module):
    cat backend/chart_maps/gajjala/gg_like.py backend/scripts/gg_like_census.py | docker exec -i -w /app cheetah-market-app-api-1 python -
What-if (a report for his pick, written nowhere; repeatable; a value "GC.NAME" reads that constant):
    ... python scripts/gg_like_census.py --set TENNIS_MIN_DROP_PCT=GC.K8_DROP_PCT --set MAX_UNDER_HIGH_PCT=20
"""
import json
import sys

try:
    from chart_maps.gajjala import gg_like as GL
except ImportError:                                  # piped after the engine's bytes: the engine IS __main__
    GL = sys.modules["__main__"]

CENSUS_TILE_KEYS = ("tile.bars5", "tile.curves5", "tile.bars15", "tile.curves15")
CENSUS_BATCH = 50


def _census_day(doc) -> str:
    d = doc.get("date")
    return d if isinstance(d, str) and d else str(doc.get("_id") or "").split("|")[0]


def tally(docs, gl) -> dict:
    """PURE. The census of read docs (each with `setups` + the `tile` frames) under `gl`'s CURRENT bounds."""
    from chart_maps.gajjala import constants as GCC
    from chart_maps.gajjala import tab as TT
    from chart_maps.gajjala_watch.tags import carded_setups
    out = {"carded": 0, "gg_like": 0, "not": 0, "unknown": 0}
    per_day, by_setup, rang = {}, {s: [0, 0] for s in GCC.SETUPS}, [0, 0]
    checks = {s: {} for s in GCC.SETUPS}
    only_fail = {s: {} for s in GCC.SETUPS}
    for doc in docs or []:
        if not isinstance(doc, dict):
            continue
        carded = carded_setups(doc)
        if not carded:
            continue
        day = _census_day(doc)
        per_day.setdefault(day, 0)
        blocks = gl.doc_blocks(doc)
        for s in carded:
            blk = blocks.get(s)
            if blk is None:
                continue
            v = blk["verdict"]
            out["carded"] += 1
            out[v] += 1
            by_setup[s][1] += 1
            if v == "gg_like":
                by_setup[s][0] += 1
                per_day[day] += 1
            if doc["setups"][s].get("state") in TT.MARKED_STATES:
                rang[1] += 1
                rang[0] += 1 if v == "gg_like" else 0
            for ch in blk["checks"]:
                if ch["key"] in gl.INFO_KEYS:
                    continue
                cell = checks[s].setdefault(ch["key"], {"ok": 0, "fail": 0, "na": 0})
                cell["ok" if ch["ok"] is True else "fail" if ch["ok"] is False else "na"] += 1
            if len(blk["failed"]) == 1:
                k = blk["failed"][0]
                only_fail[s][k] = only_fail[s].get(k, 0) + 1
    days = sorted(per_day)
    return dict(out, **{"from": days[0] if days else None, "to": days[-1] if days else None, "sessions": len(days),
                        "per_day": {d: per_day[d] for d in days}, "by_setup": by_setup, "rang": rang,
                        "checks": checks, "only_fail": only_fail, "bounds": gl.bounds_signature()})


def _census_value(raw: str):
    from chart_maps.gajjala import constants as GCC
    if raw.startswith("GC."):
        return getattr(GCC, raw[3:])
    return json.loads(raw)


def _census_load():
    from chart_maps.gajjala import constants as GCC
    from chart_maps.gajjala import store as ST
    from chart_maps.gajjala import tab as TT
    c = ST.default().coll(ST.READS)
    ids = []
    for d in c.find({}, {"symbol": 1, "date": 1, "setups": 1}):
        setups = d.get("setups") if isinstance(d.get("setups"), dict) else {}
        if any(isinstance(setups.get(s), dict) and setups[s].get("state") in TT.TILE_STATES for s in GCC.SETUPS):
            ids.append(d["_id"])
    proj = dict({"symbol": 1, "date": 1, "setups": 1}, **{k: 1 for k in CENSUS_TILE_KEYS})
    docs = []
    for i in range(0, len(ids), CENSUS_BATCH):
        docs.extend(c.find({"_id": {"$in": ids[i:i + CENSUS_BATCH]}}, proj))
    return docs


def main(argv=None) -> int:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    argv = list(sys.argv[1:] if argv is None else argv)
    sets = []
    while argv:
        a = argv.pop(0)
        if a == "--set" and argv:
            name, _eq, raw = argv.pop(0).partition("=")
            sets.append((name, _census_value(raw)))
        elif a.startswith("--set="):
            name, _eq, raw = a[len("--set="):].partition("=")
            sets.append((name, _census_value(raw)))
    docs = _census_load()
    res = dict({"at": datetime.now(ZoneInfo("America/New_York")).date().isoformat()}, **tally(docs, GL))
    if sets:
        saved = {name: getattr(GL, name) for name, _v in sets}
        try:
            for name, val in sets:
                setattr(GL, name, val)
            res["what_if"] = dict({"set": {name: val for name, val in sets}}, **tally(docs, GL))
        finally:
            for name, val in saved.items():
                setattr(GL, name, val)
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
