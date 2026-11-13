"""📅 Long Term — build the AT-SAVE baseline from the 2026-11-12 dumps (WP-DATA).

Ajay 2026-11-12 ~21:00 ET: "Save this entire list for me. In a New tab - Long
Term - Remember this analays criteria I am asking you to for this tab and keep
updating it from all the other tabs info.. Weekly and if something gets dropped
let me know when to like is Sales drop or Stage 2 to Stage 3 or stage 4 changes."

PURE JSON, host python, no Mongo, no network: every dump is a file the main
session wrote on 11-12 from the source tabs' own engines, and every dump row is
mapped through `long_term_list.facts`' OWN mappers, the legs through
`long_term_list.criteria`, the 🧭 zone read through `criteria.zone_read`
(-> `pankaj_picks.setup_status`) and the initial per-name flags through
`notices.initial_flags(notices.at_save(...))`.

    .venv/bin/python scripts/long_term_list_baseline_2026_11_12.py \
        --seed  <scratch>/longterm/saved_list_2026_11_12.json \
        --scan  <scratch>/sepa1112/full.json   --sweep <scratch>/sc1112/sweep.json \
        --snap  <scratch>/sc1112/snap.json     --lt    <scratch>/sc1112/lt_rows.json \
        --hot   <scratch>/hot1112/h.json       --fallen <scratch>/val1112/fallen2.json \
        --uvp   <scratch>/val1112/uvp.json     --acc   <scratch>/sc1112/acc_rows.json \
        --caps  <scratch>/sc1112/acc_caps.json --dec   <scratch>/longterm/dec1112.json \
        --out long_term_list/data/baseline_2026_11_12.json
    ... same args --check     -> prints the reproduction table, writes nothing

Dump -> source mapping (the shapes `sources.load_all` serves):
  scan    full.json `all_results` (+ `candidates`, is_candidate) — the 16:30 fast scan
  frames  sweep.json: stage.classify on the cached closed bars; px/last_date;
          off_hi/off_lo = the 252-bar close high/low (trend_template's own window);
          dv50_m = 50-bar mean close x volume (adr.liquidity_check's formula), $M at 0.1
  research snap.json `sales` blocks; the quarter end + read date [C11] from
          dec1112.json = `research.decision_snapshot(the 109 saved)` read-only in
          the api container 11-12 23:40 ET ({read_at, n_asked, rows: {SYM: {sales,
          q_end_series, cached_at}}}). A name's q_end_series / cached_at ride along
          ONLY when its decision_snapshot `sales` block equals the snap.json block
          (the dates then belong to the very read the baseline's sales came from);
          otherwise, or with no --dec, they stay None (missing, never invented)
  longterm lt_rows.json (the stored long-term rows)
  hottest h.json served Hottest payload (25 names per sector = HOT_PAGE, all served)
  fallen  fallen2.json served 📉 page (80 tiles = LIMIT_MAX, min_tier ok): the
          tile's `fallen` block; every tile is in the served pool and cleared the floor
  undervalue uvp.json served 🏷️ vs-peers tiles (24 of 37 passed, ratio order, ok floor):
          ratio = (Mkt cap ÷ TTM rev) ÷ Peer P/S recomputed from the printed stats
          (the "vs peers % below" text is whole-% and ties AVT/ARW at 94%); it keeps the
          served order through the first 20 tiles — AIR/HHH (21st/22nd) swap on the
          rounded peer P/S. TTM revenue / sales growth from the tile stats as printed
  caps    acc_caps.json market_caps_for(cap=0) over the 🔄 pre-candidates
  sector map (🔄 fallback) acc_rows.json `sec` (the 11-12 run's own read)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from long_term_list import constants as C          # noqa: E402
from long_term_list import criteria as CR          # noqa: E402
from long_term_list import facts as F              # noqa: E402
from long_term_list import notices as N            # noqa: E402
from long_term_list import seed as SEED            # noqa: E402

ARGS = ("seed", "scan", "sweep", "snap", "lt", "hot", "fallen", "uvp", "acc", "caps")
OPTIONAL_ARGS = ("dec",)


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _num(text):
    """'+48%' -> 48.0 · '$27.6B · FY2026 Q4' -> 2.76e10 · '94% below' -> 94.0."""
    if text is None:
        return None
    m = re.search(r"([+\-−]?)\$?([0-9]+(?:\.[0-9]+)?)\s*([KMBT]?)", str(text))
    if not m:
        return None
    v = float(m.group(2)) * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}[m.group(3)]
    return -v if m.group(1) in ("-", "−") else v


# ---------------------------------------------------------------------------
# dumps -> the `sources.load_all` shapes
# ---------------------------------------------------------------------------
def research_dates(snap: dict, dec) -> dict:
    """{SYM: {q_end_series, cached_at}} for the names whose decision_snapshot
    `sales` block equals the snap.json block (same read). Any other name -> absent."""
    rows = (dec or {}).get("rows") if isinstance(dec, dict) else None
    out = {}
    for s, v in (rows or {}).items():
        if not isinstance(v, dict):
            continue
        sales = (snap.get(s) or {}).get("sales")
        if sales is None or v.get("sales") != sales:
            continue
        out[s] = {"q_end_series": v.get("q_end_series"), "cached_at": v.get("cached_at")}
    return out


def sources_from_dumps(d: dict) -> dict:
    scan = d["scan"]
    rows = {}
    for r in scan.get("all_results") or []:
        rows[str(r["symbol"]).upper()] = r
    cands = []
    for r in scan.get("candidates") or []:
        s = str(r["symbol"]).upper()
        rows.setdefault(s, r)
        if r.get("is_candidate"):
            cands.append(s)

    reads = {}
    for w in d["sweep"]:
        if "stage" not in w:
            continue
        reads[w["sym"]] = {"close": w.get("px"), "close_date": w.get("last_date"),
                           "stage": w.get("stage"), "stage_label": w.get("label"),
                           "stage_bar_date": w.get("last_date"),
                           "pct_below_high": (-w["off_hi"] if w.get("off_hi") is not None else None),
                           "pct_above_low": w.get("off_lo"),
                           "dollar_vol_50": (w["dv50_m"] * 1e6 if w.get("dv50_m") is not None else None)}

    research = {s: {"sales": (v or {}).get("sales")} for s, v in d["snap"].items()}
    for s, v in research_dates(d["snap"], d.get("dec")).items():
        research.setdefault(s, {"sales": None}).update(v)

    hot_rows = {}
    for sec in d["hot"].get("sectors") or []:
        for i, n in enumerate(sec.get("names") or []):
            s = str(n["symbol"]).upper()
            if s in hot_rows:
                continue
            hot_rows[s] = {"symbol": s, "group": sec.get("group"), "sales_tier": n.get("sales_tier"),
                           "q_eps_yoy": n.get("q_eps_yoy"), "ret_21d": n.get("ret_21d"),
                           "rank_in_group": i + 1, "served": i < C.HOT_PAGE}

    fal_rows, pool = {}, []
    for t in d["fallen"].get("tiles") or []:
        s = str(t["symbol"]).upper()
        fb = t.get("fallen") or {}
        fal_rows[s] = {"symbol": s, "name": t.get("name"), "pct_below": fb.get("pct_below"),
                       "pct_above_low": fb.get("pct_above_low"), "close": fb.get("close"),
                       "close_date": fb.get("close_date"), "sector": fb.get("sector"),
                       "sales": fb.get("sales"), "in_served_pool": True, "floor_ok": True}
        pool.append(s)

    passed = []
    for t in d["uvp"].get("tiles") or []:
        s = str(t["symbol"]).upper()
        st = {x["k"]: x["v"] for x in t.get("stats") or []}
        cap, ttm, peer = _num(st.get("Mkt cap")), _num(st.get("TTM rev")), _num(st.get("Peer P/S"))
        ratio = (cap / ttm / peer) if cap and ttm and peer else None
        passed.append({"symbol": s, "sector": (rows.get(s) or {}).get("sector"),
                       "ratio": (None if ratio is None else round(ratio, 4)),
                       "ttm_revenue": _num(st.get("TTM rev")),
                       "q_yoy_pct": _num(st.get("Sales YoY Q")),
                       "ttm_growth_pct": _num(st.get("Sales TTM")), "floor_ok": True})

    sector_map = {r["sym"]: r.get("sec") for r in d["acc"] if r.get("sec")}
    gen = scan.get("generated_at")
    ok = lambda **kw: {"ok": True, "reason": None, **kw}             # noqa: E731
    return {
        "session": "2026-11-12",
        "scan": ok(as_of=gen, n=len(rows), rows=rows, candidates=cands),
        "undervalue": ok(as_of="2026-11-12", n=len(passed), passed=passed, snaps={}),
        "fallen": ok(as_of=d["fallen"].get("fallen_board", {}).get("as_of"), n=len(pool),
                     rows=fal_rows, pool=pool),
        "hottest": ok(as_of=d["hot"].get("as_of"), n=len(hot_rows), rows=hot_rows),
        "longterm": ok(as_of=None, n=len(d["lt"]), rows=d["lt"], sector_map=sector_map),
        "research": ok(as_of=None, n=len(research), rows=research),
        "frames": ok(as_of="2026-11-12", n=len(reads), reads=reads, frames={}),
        "caps": ok(as_of=None, n=len(d["caps"]), caps=d["caps"]),
        "growth_board": {"ok": False, "reason": "not in the 2026-11-12 dumps", "as_of": None, "n": 0},
    }


# ---------------------------------------------------------------------------
# the baseline + the reproduction table
# ---------------------------------------------------------------------------
def _leg_dicts(cat, values):
    return [lg.to_dict() for lg in CR.legs(cat, values)]


def build_baseline(seed: dict, srcs: dict, built_from: dict) -> dict:
    saved = SEED.unique_names(seed)
    chips = SEED.chips(seed)
    facts = F.build(srcs, saved, seed)
    order = SEED.zone_order(seed)
    names = {}
    for s in saved:
        n = facts["names"][s]
        names[s] = {"stage": n["stage"], "stage_label": n["stage_label"],
                    "stage_bar_date": n["stage_bar_date"], "close_at_save": n["close"],
                    "sales_tier": n["sales_tier"], "sales_yoy_pct": n["sales_yoy_pct"],
                    "sales_q_end": n["sales_q_end"], "sales_read_on": n["sales_read_on"],
                    "sector": n["sector"], "name": n["name"]}
    cats = {}
    for cat in C.CATEGORY_KEYS:
        look = facts["categories"][cat]["lookup"]
        cats[cat] = {}
        for s in saved:
            if cat not in chips[s] or s not in look:
                continue
            vals = look[s]["values"]
            if cat == C.PANKAJ_KEY:
                vals = dict(vals, zone_read=CR.zone_read(vals["zones"], vals["close"],
                                                         vals["close_date"], order))
            cats[cat][s] = {"values": vals, "legs": _leg_dicts(cat, vals)}
    pankaj = {s: {"zone_read": row["values"]["zone_read"]}
              for s, row in cats[C.PANKAJ_KEY].items()}
    out = {"saved_on": C.SAVED_ON, "built_from": built_from, "names": names,
           "categories": cats, "pankaj": pankaj}
    out["flags"] = {s: N.initial_flags(N.at_save(s, out)) for s in saved}
    return out


def reproduction(seed: dict, srcs: dict) -> list:
    """[(cat, seed names, pick_top, uncapped top, verdict)] for the eight screened lists."""
    saved = SEED.unique_names(seed)
    facts = F.build(srcs, saved, seed)
    rows = []
    for cat in C.SCREENED_KEYS:
        want = [SEED.name_symbol(e) for e in (SEED.category(seed, cat) or {}).get("names") or []]
        pop = facts["categories"][cat]["population"]
        got = CR.pick_top(cat, pop, saved=frozenset(saved))
        q = [c for c in pop if CR.in_population(cat, c["values"])
             and CR.qualifies(cat, c["values"]) is True]
        q.sort(key=lambda c: CR.rank_key(cat, c["values"], c["symbol"]))
        uncapped = [c["symbol"] for c in q][:C.PER_CATEGORY]
        if got == want:
            verdict = "EXACT"
        elif uncapped == want:
            verdict = "differs only by the sector cap"
        else:
            verdict = "DIFFERS"
        rows.append({"cat": cat, "seed": want, "pick_top": got, "uncapped": uncapped,
                     "n_qualify": len(q), "verdict": verdict})
    return rows


def check_table(rows: list) -> str:
    lines = ["| category | qualify | verdict | pick_top (capped) |", "|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['cat']} | {r['n_qualify']} | {r['verdict']} | {' '.join(r['pick_top'])} |")
        if r["verdict"] != "EXACT":
            lines.append(f"| ↳ seed | | | {' '.join(r['seed'])} |")
            lines.append(f"| ↳ uncapped | | | {' '.join(r['uncapped'])} |")
    lines.append(f"| {C.PANKAJ_KEY} | — | n/a (his sheet's first 40 rows, not a screen) | — |")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    for a in ARGS:
        ap.add_argument(f"--{a}", required=True)
    for a in OPTIONAL_ARGS:
        ap.add_argument(f"--{a}", default=None)
    ap.add_argument("--out", default=str(C.BASELINE_FILE))
    ap.add_argument("--check", action="store_true")
    ns = ap.parse_args(argv)
    seed = SEED.load(ns.seed)
    dumps = {a: _load(getattr(ns, a)) for a in ARGS if a != "seed"}
    for a in OPTIONAL_ARGS:
        if getattr(ns, a):
            dumps[a] = _load(getattr(ns, a))
    srcs = sources_from_dumps(dumps)
    if ns.check:
        print(check_table(reproduction(seed, srcs)))
        return 0
    built_from = {a: {"file": Path(getattr(ns, a)).name, "sha256": _sha(getattr(ns, a))}
                  for a in ARGS + OPTIONAL_ARGS if getattr(ns, a)}
    base = build_baseline(seed, srcs, built_from)
    text = json.dumps(base, indent=1, sort_keys=True, allow_nan=False, ensure_ascii=False)
    Path(ns.out).write_text(text + "\n", encoding="utf-8")
    n_q = sum(1 for v in base["names"].values() if v.get("sales_q_end"))
    n_r = sum(1 for v in base["names"].values() if v.get("sales_read_on"))
    print(f"wrote {ns.out}: {len(base['names'])} names · quarter end on {n_q} · read date on {n_r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
