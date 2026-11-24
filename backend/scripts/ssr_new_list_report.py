"""⛔ SSR "new today" list on the 🩳 High SI sub — the re-runnable report behind every number its docs quote. READ-ONLY.

Ajay 2026-11-24, in order: "What are the SSR stocks today" · "Can you add it to short interest tab" · "The new ones".
SPEC ssrlist §4 main-session. It calls the REAL engine (`short_interest.ssr.new_triggers`) and the REAL served block
(`chart_maps.gajjala.high_si.ssr_new_block`) for the session the board shows now, and prints:

  * the engine status, rows, official / computed, "triggered again", withheld names by reason, faults
  * the four folds and, per fold, the names that could not be tiered; the rows with a 🩳 text
  * the served block's bytes (raw and gzip) and the time of the engine read and of the whole block
  * with --clocks: the SAME day read at D 19:59, D 20:01, the next market day 00:30 and 04:05 — the
    "triggered again" count must not move with the clock [C1]

Mongo reads only (the engine's own `find`s + the 🩳 SI read + GG's 🚩 list read): no write, no list refresh, no outside
call. Nothing here is a signal; the list is UNMEASURED.

Run it in the api container:

    docker exec -i -w /app cheetah-market-app-api-1 python scripts/ssr_new_list_report.py --clocks
    docker exec -i -w /app cheetah-market-app-api-1 python scripts/ssr_new_list_report.py --json
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _modules(ssr=None, hs=None, lists=None):
    """The engine, the block and the list module — the house ones unless handed in (a probe of a branch passes its own
    copies; `lists` None = the engine resolves its own)."""
    if ssr is None:
        from short_interest import ssr as ssr
    if hs is None:
        from chart_maps.gajjala import high_si as hs
    return ssr, hs, lists


def _size(obj) -> tuple:
    raw = json.dumps(obj, ensure_ascii=False, allow_nan=False).encode("utf-8")
    return len(raw), len(gzip.compress(raw))


def build(now=None, *, ssr=None, hs=None, lists=None) -> dict:
    """{now, session, engine, block, ms_engine, ms_block, listed_n, listed_ok} for the board's session at `now`."""
    from chart_maps.gajjala import scanner as SC
    from chart_maps.gajjala import tab as GT
    from chart_maps.gajjala import variant as V
    from short_interest import reg_sho as RS
    ssr, hs, lists = _modules(ssr, hs, lists)
    now_et = RS._to_et(now)
    session, _is_today, _in_window = GT.session_for(now_et)
    listed_ok = True
    try:
        listed = SC.listed_symbols(GT._store(None), session)
    except Exception as exc:                                        # noqa: BLE001 — the board serves {} then too
        print("his list unread: %s" % type(exc).__name__, file=sys.stderr)
        listed, listed_ok = {}, False
    seen = {}

    def read(s, n):
        t0 = time.perf_counter()
        ans = ssr.new_triggers(s, now=n, lists=lists) if lists is not None else ssr.new_triggers(s, now=n)
        seen["ms"] = (time.perf_counter() - t0) * 1000.0
        seen["ans"] = ans
        return ans
    t0 = time.perf_counter()
    blk = hs.ssr_new_block(listed, session=session, now=now_et, tf=V.of(None).primary, v=None, ssr_read=read)
    ms_block = (time.perf_counter() - t0) * 1000.0
    return {"now": now_et, "session": session, "engine": seen.get("ans"), "block": blk, "ms_engine": seen.get("ms"),
            "ms_block": ms_block, "listed_n": len(listed) if isinstance(listed, dict) else None,
            "listed_ok": listed_ok}


def summary(res: dict) -> dict:
    """The JSON summary: every count the docs quote, from the served engine answer and the served block."""
    eng = res.get("engine") if isinstance(res.get("engine"), dict) else {}
    blk = res.get("block") if isinstance(res.get("block"), dict) else {}
    groups = [g for g in (blk.get("groups") or []) if isinstance(g, dict)]
    fold = {g.get("key"): g for g in groups}
    raw, gz = _size(blk)
    rows = [r for g in groups for r in (g.get("rows") or [])]
    lh = (fold.get("list_high") or {}).get("rows") or []
    withheld = eng.get("withheld") if isinstance(eng.get("withheld"), dict) else {}
    return {
        "now_et": res["now"].strftime("%Y-%m-%d %H:%M:%S"),
        "session": res["session"].isoformat(),
        "status": eng.get("status"),
        "n_rows": eng.get("n"),
        "n_official": eng.get("n_official"),
        "n_computed": eng.get("n_computed"),
        "n_retriggered": eng.get("n_retriggered"),
        "withheld": {k: len(v) for k, v in withheld.items() if isinstance(v, list)},
        "withheld_names": {k: list(v) for k, v in withheld.items() if isinstance(v, list)},
        "faults": len(eng.get("faults") or []),
        "corp_checked": eng.get("corp_checked"),
        "listed_n": res.get("listed_n"),
        "listed_ok": res.get("listed_ok"),
        "folds": {g.get("key"): g.get("count") for g in groups},
        "fold_summaries": {g.get("key"): g.get("summary") for g in groups},
        "n_untiered": blk.get("n_untiered"),
        "n_tiered": (blk["n"] - blk["n_untiered"]) if isinstance(blk.get("n"), int)
                    and isinstance(blk.get("n_untiered"), int) else None,
        "rows_with_si_text": sum(1 for r in rows if r.get("si_text")),
        "list_high_first_six": lh[:6],
        "counts_text": blk.get("counts_text"),
        "tier_note": blk.get("tier_note"),
        "asof_text": blk.get("asof_text"),
        "partial_text": blk.get("partial_text"),
        "status_text": blk.get("status_text"),
        "fault_text": blk.get("fault_text"),
        "empty_text": blk.get("empty_text"),
        "block_bytes_raw": raw,
        "block_bytes_gzip": gz,
        "ms_engine": round(res["ms_engine"], 1) if isinstance(res.get("ms_engine"), float) else None,
        "ms_block": round(res["ms_block"], 1),
    }


def clocks(session, *, ssr=None, lists=None) -> list:
    """The same trigger day read at the clocks where the rev 1 rule broke [C1]. Engine only (no SI / list read)."""
    from catalysts.medical.reaction import next_market_day
    ssr, _hs, lists = _modules(ssr, True, lists)
    D, N = session, next_market_day(session)
    out = []
    for label, d, h, m in (("D 15:00", D, 15, 0), ("D 19:59", D, 19, 59), ("D 20:01", D, 20, 1),
                           ("next market day 00:30", N, 0, 30), ("next market day 04:05", N, 4, 5)):
        clock = datetime(d.year, d.month, d.day, h, m, tzinfo=ssr._ET)
        ans = ssr.new_triggers(D, now=clock, lists=lists) if lists is not None else ssr.new_triggers(D, now=clock)
        out.append({"clock": label, "at": clock.strftime("%Y-%m-%d %H:%M"), "status": ans.get("status"),
                    "n_rows": ans.get("n"), "n_retriggered": ans.get("n_retriggered")})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="print the summary as one JSON object")
    ap.add_argument("--clocks", action="store_true", help="also read the same day at the later clocks [C1]")
    a = ap.parse_args(argv)
    res = build()
    s = summary(res)
    if a.clocks:
        s["clock_table"] = clocks(res["session"])
    if a.json:
        print(json.dumps(s, ensure_ascii=False, indent=1))
        return 0
    print("now %s ET · session %s · status %s" % (s["now_et"], s["session"], s["status"]))
    print("rows %s · official %s · computed %s · triggered again %s · faults %s · corp checked %s"
          % (s["n_rows"], s["n_official"], s["n_computed"], s["n_retriggered"], s["faults"], s["corp_checked"]))
    print("withheld %s %s" % (s["withheld"], s["withheld_names"]))
    print("his list %s names (read %s)" % (s["listed_n"], s["listed_ok"]))
    print("folds %s · tiered %s / not tiered %s · rows with a 🩳 text %s"
          % (s["folds"], s["n_tiered"], s["n_untiered"], s["rows_with_si_text"]))
    for k, v in s["fold_summaries"].items():
        print("  %s: %s" % (k, v))
    for k in ("counts_text", "tier_note", "asof_text", "partial_text", "status_text", "fault_text", "empty_text"):
        if s[k]:
            print("%s: %s" % (k, s[k]))
    print("block bytes raw %d · gzip %d · engine %s ms · block %s ms"
          % (s["block_bytes_raw"], s["block_bytes_gzip"], s["ms_engine"], s["ms_block"]))
    for r in s.get("clock_table") or []:
        print("clock %-22s %s · status %s · rows %s · triggered again %s"
              % (r["clock"], r["at"], r["status"], r["n_rows"], r["n_retriggered"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
