"""📐 Gajjala's Watch daily zones — the coverage table of the spec's section 1 (read-only, 2026-11-23, WP be-zones).

For docs/gajjala/watch_daily_zones_2026_11_23.md [C3][C4]: per stored Watch tile, the BOARD zones the 📐 overlay would
serve (`zone_store.build_doc` on the closed daily bars, the engine's own N-nearest-per-kind cut) against that tile's
1-min candle range. Prints one table:

  names read · under $1 · names carrying a zero-width served band (+ examples) · widest served sub-$1 band, % of its own mid ·
  names drawing NO zone inside the chart range · names under `zone_store.MIN_BARS` · names losing an in-range band to the
  N-nearest cut · names drawing ≥ 5 bands · prior-day high inside the chart range · … and in NO band · build_doc ms/name.

READ-ONLY and NO FETCH: ONE Mongo find over the Watch tiles + `sepa.prices.bulk_cached_frames` (the cached daily frames —
NOT the fresh loader the overlay uses, so the table is PROVISIONAL; a name without a cached frame is counted, never
fetched). Nothing is written anywhere. Imports ONLY modules that exist on origin/main (the container runs main), so the
served cut is re-implemented inline as `near` — tests/test_gajjala_watch_levels_2026_11_23.py pins it equal to
`chart_maps.gajjala_watch.levels.near`. Descriptive counts, not an edge — UNMEASURED.

  docker exec -i -w /app cheetah-market-app-api-1 python -m scripts.gajjala_watch_levels_coverage [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from typing import Optional

ZONE_KINDS = ("demand", "supply")                 # == gajjala_watch.constants.ZONE_KINDS (pinned by the repo test)
MANY_DRAWN = 5                                    # the "names drawing 5–7 bands" row of the spec table (a count bucket)
EXAMPLES = 5


def near(bands, price, n) -> list:
    """INLINE copy of `levels.near` (the engine's surfacing rule): per kind, `price_zones.nearest_first(kind bands,
    price)[:n]`, sorted high → low. A repo test pins it equal to the real one."""
    from supply_demand import price_zones
    out: list = []
    for kind in ZONE_KINDS:
        out += price_zones.nearest_first([b for b in bands if b.get("kind") == kind], price)[:n]
    return sorted(out, key=lambda b: (-b["hi"], -b["lo"]))


def _meets(b: dict, lo: float, hi: float) -> bool:
    """A band meets the candle range [lo, hi] (inclusive — a zero-width band at the range edge is drawn)."""
    return b["hi"] >= lo and b["lo"] <= hi


def widest_sub1_pct(served: list) -> Optional[float]:
    """Widest served band whose OWN mid is under $1, as % of that mid: 100 · (hi − lo) / ((hi + lo) / 2), one
    decimal. Width over the band's own price — never over the name's last price, which inflates a far-away band of an
    old history (47,573.7 % on 2026-11-23). None when no served band has 0 < mid < 1."""
    best: Optional[float] = None
    for b in served:
        mid = (b["hi"] + b["lo"]) / 2.0
        if not 0 < mid < 1:
            continue
        pct = round(100.0 * (b["hi"] - b["lo"]) / mid, 1)
        if best is None or pct > best:
            best = pct
    return best


def _bars(doc: dict) -> list:
    fr = (doc.get("frames") or {}).get("1m") if isinstance(doc.get("frames"), dict) else None
    bars = fr.get("bars") if isinstance(fr, dict) else None
    return [b for b in (bars or []) if isinstance(b, dict)
            and all(isinstance(b.get(k), (int, float)) for k in ("h", "l", "c"))]


def summarize(docs: list, cached: dict, *, n: Optional[int] = None) -> dict:
    """The table's counts for `docs` (stored Watch tiles: _id, session, frames.1m.bars h/l/c) against `cached`
    ({SYM: daily frame}). Pure apart from the engine calls."""
    from supply_demand import price_zones, zone_store
    k = price_zones.MAX_ZONES_PER_SIDE if n is None else int(n)
    t = {"names": 0, "no_bars": 0, "not_cached": 0, "short": 0, "ok": 0, "under_1": 0, "zero_width_names": 0,
         "widest_sub1_pct": None, "no_zone_in_range": 0, "cut_in_range": 0, "drawn_ge_many": 0,
         "pdh_in_range": 0, "pdh_in_range_no_band": 0, "build_ms_per_name": None, "zero_width_examples": []}
    ms: list = []
    for d in docs:
        t["names"] += 1
        sym, ses = d.get("_id"), d.get("session")
        bars = _bars(d)
        if not bars or not isinstance(ses, str):
            t["no_bars"] += 1
            continue
        lo, hi, P = min(b["l"] for b in bars), max(b["h"] for b in bars), float(bars[-1]["c"])
        if P < 1:
            t["under_1"] += 1
        df = cached.get(sym)
        if df is None:
            t["not_cached"] += 1
            continue
        day = date.fromisoformat(ses[:10])
        t0 = time.perf_counter()
        doc = zone_store.build_doc(sym, df, day)
        ms.append((time.perf_counter() - t0) * 1000.0)
        if doc is None:
            t["short"] += 1
            continue
        t["ok"] += 1
        bands = [b for b in doc.get("bands") or [] if b.get("kind") in ZONE_KINDS]
        served = near(bands, P, k)
        drawn = [b for b in served if _meets(b, lo, hi)]
        allin = [b for b in bands if _meets(b, lo, hi)]
        zero = [b for b in served if b["hi"] <= b["lo"]]
        if zero:
            t["zero_width_names"] += 1
            if len(t["zero_width_examples"]) < EXAMPLES:
                t["zero_width_examples"].append(f"{sym} {zero[0]['lo']}–{zero[0]['hi']}")
        pct = widest_sub1_pct(served)
        if pct is not None and (t["widest_sub1_pct"] is None or pct > t["widest_sub1_pct"]):
            t["widest_sub1_pct"] = pct
        if not drawn:
            t["no_zone_in_range"] += 1
        if len(allin) > len(drawn):
            t["cut_in_range"] += 1
        if len(drawn) >= MANY_DRAWN:
            t["drawn_ge_many"] += 1
        closed = zone_store.drop_today(df, day)
        try:
            pdh = float(closed["high"].iloc[-1])
        except Exception:                                      # noqa: BLE001
            pdh = None
        if pdh is not None and lo <= pdh <= hi:
            t["pdh_in_range"] += 1
            if not any(b["lo"] <= pdh <= b["hi"] for b in bands):
                t["pdh_in_range_no_band"] += 1
    if ms:
        t["build_ms_per_name"] = round(sorted(ms)[len(ms) // 2], 1)
    return t


def table(t: dict) -> str:
    rows = [
        ("Watch tiles read", t["names"]),
        ("… with no 1-min bars", t["no_bars"]),
        ("… with no cached daily frame (never fetched)", t["not_cached"]),
        ("Watch names under $1", t["under_1"]),
        ("names carrying a zero-width served band", t["zero_width_names"]),
        ("… examples", ", ".join(t["zero_width_examples"]) or "—"),
        ("widest served sub-$1 band, % of its own mid", "—" if t["widest_sub1_pct"] is None else f"{t['widest_sub1_pct']} %"),
        ("names drawing NO zone inside the chart range", f"{t['no_zone_in_range']} of {t['ok']}"),
        ("names under zone_store.MIN_BARS", t["short"]),
        ("names losing an in-range band to the nearest-N cut", t["cut_in_range"]),
        (f"names drawing {MANY_DRAWN}+ bands on one chart", t["drawn_ge_many"]),
        ("prior-day high inside the chart range", f"{t['pdh_in_range']} of {t['ok']}"),
        ("… and in NO band", f"{t['pdh_in_range_no_band']} of {t['ok']}"),
        ("build_doc cost (median ms / name)", "—" if t["build_ms_per_name"] is None else t["build_ms_per_name"]),
    ]
    out = ["| Read | Count |", "|---|---|"]
    out += [f"| {a} | {b} |" for a, b in rows]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="scripts.gajjala_watch_levels_coverage", description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true", help="print the counts as JSON too")
    args = ap.parse_args(argv)
    from chart_maps.gajjala_watch import colls as CO
    from sepa import prices
    cs = CO.colls(None)
    if not cs:
        print("no database", file=sys.stderr)
        return 1
    docs = list(cs["tiles"].find({}, {"session": 1, "frames.1m.bars.h": 1, "frames.1m.bars.l": 1,
                                      "frames.1m.bars.c": 1}))
    cached = prices.bulk_cached_frames([d["_id"] for d in docs])
    t = summarize(docs, cached)
    print("PROVISIONAL — cached daily frames, not the overlay's fresh read; nothing fetched, nothing written.")
    print(table(t))
    if args.json:
        print(json.dumps(t, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
