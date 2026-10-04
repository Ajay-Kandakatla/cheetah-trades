"""🩳 Short interest — live check of the bulk warm and the served read (READ-ONLY).

THE ASK (Ajay 2026-10-03, verbatim)
  "I would like to see a new field for sotcks about short interest I heard EOSE
   has about 40% short interest is Short Interest always accurate about a stocks
   down fall?
   can you add this field to all our chart maps scan. also the individual
   tickers please"

What it does (≤ 3 provider calls, ZERO writes):
  1. `block_writes()` FIRST — every pymongo write method becomes a recorded
     no-op in this process (`ATTEMPTED` lists any that were tried).
  2. `warm_short_interest_bulk(scope=<full universe>, dry_run=True, force=True)`
     — the cron's own warm, writing nothing, returning the v2 docs it would
     write.
  3. `read.si_block` over those dry-run docs, and `read.si_map` over the LIVE
     cache, for the named symbols below.
  4. Coverage counts: universe names with a block, by headline basis, by status.

Outputs (in the working directory, /out in the throwaway container):
  si_live_check.json   — counts, the named blocks (dry-run and live), calls
  si_live_blocks.json  — the shared-fixture shape ({today, cases[name, doc,
                         block]}) from LIVE data, for the FE payload test:
                         SI_LIVE_PAYLOAD=<path> npx vitest run
                         src/components/ShortInterest.payload.test.tsx

Run only in a throwaway container (never the live api/cron containers):
  docker run --rm --cpus 2 --memory 3g --network cheetah-market-app_default \\
    -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York \\
    -e SEPA_UNIVERSE_MODE=full -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 \\
    --env-file <600-mode key file> -v <tree>/backend:/app:ro \\
    -v cheetah-market-app_cheetah-scans:/root/.cheetah:ro -v <outdir>:/out -w /out \\
    cheetah-api:latest python -u /app/scripts/short_interest_live_check.py

Never prints the key or a request URL; every output is scrubbed of `apiKey=`.
Display data only — this script measures nothing about returns.
"""
from __future__ import annotations

import collections
import json
import re
import sys
from datetime import date
from pathlib import Path

from scripts.resiliency_study import ATTEMPTED, block_writes

NAMED = ("EOSE", "BYND", "GME", "NVDA", "AAPL", "UHAL", "IIIV", "CACC", "FCG")
_SCRUB = re.compile(r"apiKey=[^&\s\"']+")


def _scrub(text: str, key: str = "") -> str:
    if key:
        text = text.replace(key, "***")
    return _SCRUB.sub("apiKey=***", text)


def main(argv=None) -> int:
    block_writes()                                   # FIRST: no write can land

    import requests
    from massive_keys import stocks_key
    from sepa import universe
    from short_interest import client as C
    from short_interest import read as SR

    key = stocks_key() or ""
    calls: list = []
    real_get = requests.get

    def counted_get(url, *a, **k):
        try:
            r = real_get(url, *a, **k)
            calls.append({"path": str(url).split("?")[0].replace("https://api.massive.com", ""),
                          "status": r.status_code})
            return r
        except Exception as exc:                               # noqa: BLE001
            calls.append({"path": str(url).split("?")[0].replace("https://api.massive.com", ""),
                          "status": "EXC " + type(exc).__name__})
            raise

    requests.get = counted_get

    today = date.today()
    try:
        scope = list(universe.load_universe("full") or [])
    except Exception as exc:                                   # noqa: BLE001
        print("universe unavailable: %s" % type(exc).__name__, file=sys.stderr)
        scope = []

    res = C.warm_short_interest_bulk(scope=scope, dry_run=True, force=True)
    docs = {d["_id"]: d for d in res.pop("docs", []) or []}

    blocks = {s: SR.si_block(docs[s], today) for s in scope if s in docs}
    covered = [s for s, b in blocks.items() if b and b["status"] != "no_record"]
    by_basis = collections.Counter(str(b["headline_basis"]) for b in blocks.values() if b)
    by_status = collections.Counter(b["status"] for b in blocks.values() if b)

    live = SR.si_map(list(NAMED), today=today)
    live_docs = C.short_interest_map(list(NAMED))

    out = {
        "run_date": today.isoformat(),
        "universe_n": len(scope),
        "universe_with_a_block": len(blocks),
        "universe_covered_with_a_number": len(covered),
        "coverage_pct": round(100.0 * len(covered) / len(scope), 2) if scope else None,
        "by_headline_basis": dict(by_basis),
        "by_status": dict(by_status),
        "warm": res,
        "provider_calls_counted": len(calls),
        "provider_call_statuses": dict(collections.Counter(
            "%s %s" % (c["path"], c["status"]) for c in calls)),
        "attempted_writes": len(ATTEMPTED),
        "attempted_write_methods": dict(collections.Counter(ATTEMPTED)),
        "named_dry_run": {s: blocks.get(s) or (SR.si_block(docs[s], today) if s in docs else None)
                          for s in NAMED},
        "named_live_cache": {s: live.get(s) for s in NAMED},
    }

    cases = []
    for s in NAMED:
        if s in docs:
            cases.append({"name": "%s_dry_run_v2" % s.lower(), "doc": docs[s],
                          "block": SR.si_block(docs[s], today)})
        if s in live_docs:
            d = dict(live_docs[s])
            d.pop("age_days", None)
            d.pop("stale", None)
            d.setdefault("_id", s)
            cases.append({"name": "%s_live_cache" % s.lower(), "doc": d,
                          "block": SR.si_block(d, today)})
    payload = {"today": today.isoformat(), "cases": cases}

    Path("si_live_check.json").write_text(
        _scrub(json.dumps(out, indent=1, ensure_ascii=False, default=str), key), encoding="utf-8")
    Path("si_live_blocks.json").write_text(
        _scrub(json.dumps(payload, indent=1, ensure_ascii=False, default=str), key),
        encoding="utf-8")

    eose = out["named_dry_run"].get("EOSE") or {}
    print(_scrub("universe %d, covered %d (%s%%), calls %d, attempted writes %d, "
                 "latest %s, error %s" % (
                     out["universe_n"], out["universe_covered_with_a_number"],
                     out["coverage_pct"], out["provider_calls_counted"],
                     out["attempted_writes"], res.get("latest"), res.get("error")), key))
    print(_scrub("EOSE dry-run chip: %s" % eose.get("chip"), key))
    print(_scrub("EOSE live chip:    %s" % (live.get("EOSE") or {}).get("chip"), key))
    return 0 if not res.get("error") else 1


if __name__ == "__main__":                                  # pragma: no cover
    raise SystemExit(main())
