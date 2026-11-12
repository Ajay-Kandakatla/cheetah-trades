"""🥇 Luk's 🏁 — the R of a stop BEFORE (the served −1.0) and AFTER (measured from the actual fill), read-only
(spec rec157 WP-1, 2026-11-11). Ajay 2026-11-11 (relayed by the main session): "Do your receommendations".

The decided rule (chart_maps/luk/ledger.py `stop_r`, 2026-11-11): a stopped row's r = (stop − fill) / (trigger − stop),
the same arithmetic as walk()'s r_of at the stop; exit_px stays the alert's stop (no slippage model).

READ-ONLY. It runs INSIDE the api container, which runs origin/main — so it never imports `stop_r` (the branch's
helper); `probe_stop_r` below re-implements it with plain floats + decimal and tests/test_luk_stop_r_from_fill_2026_11_11
pins the two equal. It reads the UNCAPPED pipeline (record_sessions → rows_for → ledger_docs → track_row → mark_dups →
counts_of), never the served block's day list (capped at LUK_LEDGER_ROWS_MAX), and asserts its counts equal the served
block's counts (a mismatch → exit 1, both printed). Every store handle is the dry recording store: any write is
refused and named (exit 1).

Run (after the close, once):
    docker exec -i -w /app cheetah-market-app-api-1 python - < backend/scripts/luk_stop_r_before_after.py > out.json
Markdown table from the JSON (host, stdlib only):
    python3 backend/scripts/luk_stop_r_before_after.py --md out.json > out.md

The fill-distance decomposition is a READING, not a rule (HIS CALL #2): the bands use LC.LUK_NO_CHASE_PCT by name (his
"more than 3% from the low of day" measures the trigger vs the low of the day — LISTED, not A+ — never the fill), the
thin split uses GC.LEDGER_MIN_R_PCT by name (Luk has no thin rule — HIS CALL #1), and `fill_risk_mean_r` (R taken as
fill − stop) is a display of another convention, NOT the page's R.
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from typing import Optional

STOP, EMA9 = "stopped", "ema9_close"
FILL_RISK_LABEL = "R taken as fill − stop (every stop −1.0R) — a display of another convention, not the page's R"


# ── pure units (tested) ──────────────────────────────────────────────────────────────────────────────────────────
def _num(x) -> Optional[float]:
    if isinstance(x, bool) or x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def _D(x) -> Decimal:
    return Decimal(repr(float(x)))


def probe_stop_r(trigger, stop, fill_px) -> Optional[float]:
    """(stop − fill) / (trigger − stop), 4 dp — None when the plan is not ok (trigger / stop missing, trigger ≤ 0,
    stop < 0, trigger ≤ stop), the fill is not a finite number, or the fill is at or under the stop."""
    t, s, f = _num(trigger), _num(stop), _num(fill_px)
    if t is None or s is None or t <= 0 or s < 0:
        return None
    dt, ds = _D(t), _D(s)
    if dt <= ds or f is None or f <= s:
        return None
    risk = _D(float(dt - ds))
    return round(float((ds - _D(f)) / risk), 4)


def fill_over_trigger_pct(trigger, fill_px) -> Optional[float]:
    """(fill / trigger − 1) × 100, 4 dp; None on a missing / non-finite / bool input or a trigger ≤ 0."""
    t, f = _num(trigger), _num(fill_px)
    if t is None or f is None or t <= 0:
        return None
    return round(float((_D(f) / _D(t) - 1) * 100), 4)


def fill_risk_r(state, exit_px, fill_px, stop) -> Optional[float]:
    """The OTHER convention (display only): a stop = −1.0; a 9 EMA exit = (exit − fill) / (fill − stop)."""
    if state == STOP:
        return -1.0
    x, f, s = _num(exit_px), _num(fill_px), _num(stop)
    if state != EMA9 or x is None or f is None or s is None or f <= s:
        return None
    return round(float((_D(x) - _D(f)) / (_D(f) - _D(s))), 4)


def _stats(rs: list) -> dict:
    rs = [float(r) for r in rs]
    n = len(rs)
    return {"n": n, "sum_r": round(sum(rs), 4), "mean_r": round(sum(rs) / n, 4) if n else None}


def _median(rs: list) -> Optional[float]:
    s = sorted(float(r) for r in rs)
    n = len(s)
    if not n:
        return None
    return round(s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2, 4)


def quartiles(rows: list) -> list:
    """Rows with a pct, sorted by (pct, id); group k = rows[k*n//4 : (k+1)*n//4], k = 0..3 →
    [{lo_pct, hi_pct, n, sum_r, mean_r}]."""
    xs = sorted([x for x in rows if x.get("pct") is not None], key=lambda x: (x["pct"], str(x.get("id"))))
    n = len(xs)
    out = []
    for k in range(4):
        g = xs[k * n // 4:(k + 1) * n // 4]
        out.append(dict(_stats([x["r"] for x in g]), lo_pct=g[0]["pct"] if g else None,
                        hi_pct=g[-1]["pct"] if g else None))
    return out


def decompose(rows: list, no_chase_pct: float, thin_cut: float) -> dict:
    """rows = [{"id", "r" (R from the fill), "pct" (fill over trigger %), "r_pct" (the plan's R % of the trigger),
    "fill_risk_r"}]; a row with r None is out of every sum (as counts_of). Bands by `no_chase_pct`: on the trigger
    (pct == 0), above it by at most no_chase_pct, above it by more — they partition the rows with a pct. Thin = r_pct
    STRICTLY under `thin_cut`."""
    rows = [x for x in rows if x.get("r") is not None]
    rs = [x["r"] for x in rows]
    total = sum(rs)
    low2 = sorted(rs)[:2]
    fr = [x["fill_risk_r"] for x in rows if x.get("fill_risk_r") is not None]
    thin = [x for x in rows if x.get("r_pct") is not None and x["r_pct"] < thin_cut]
    return {
        "all": _stats(rs),
        "thin_cut": thin_cut,
        "thin": sorted(str(x.get("id")) for x in thin),
        "without_thin": _stats([x["r"] for x in rows if id(x) not in {id(t) for t in thin}]),
        "quartiles": quartiles(rows),
        "no_chase_pct": no_chase_pct,
        "on_trigger": _stats([x["r"] for x in rows if x.get("pct") is not None and x["pct"] == 0]),
        "at_most_no_chase": _stats([x["r"] for x in rows if x.get("pct") is not None and 0 < x["pct"] <= no_chase_pct]),
        "over_no_chase": _stats([x["r"] for x in rows if x.get("pct") is not None and x["pct"] > no_chase_pct]),
        "pct_missing": sum(1 for x in rows if x.get("pct") is None),
        "top2_share_pct": round(sum(low2) / total * 100, 2) if total else None,
        "fill_risk_mean_r": round(sum(fr) / len(fr), 4) if fr else None,
        "fill_risk_sum_r": round(sum(fr), 4),
        "fill_risk_label": FILL_RISK_LABEL,
    }


def summary(closed: list, key: str) -> dict:
    """{n_closed, wins, losses, mean_r, median_r, sum_r, per_session} over `closed` rows' `key` R (None = out)."""
    rs = [(x["date"], x[key]) for x in closed if x.get(key) is not None]
    vals = [r for _d, r in rs]
    per: dict = {}
    for d, r in rs:
        p = per.setdefault(d, {"n": 0, "sum_r": 0.0})
        p["n"] += 1
        p["sum_r"] = round(p["sum_r"] + r, 4)
    st = _stats(vals)
    return {"n_closed": st["n"], "wins": sum(1 for r in vals if r > 0), "losses": sum(1 for r in vals if r < 0),
            "mean_r": st["mean_r"], "median_r": _median(vals), "sum_r": st["sum_r"],
            "per_session": dict(sorted(per.items()))}


def md_table(out: dict) -> str:
    """The markdown tables of one run's JSON (host-side, stdlib only)."""
    b, a, dc = out["before"], out["after"], out["decomposition"]

    def f(v, nd=2):
        return "—" if v is None else f"{v:+.{nd}f}"

    def band(name, s):
        return f"| {name} | {s['n']} | {f(s['sum_r'])} | {f(s['mean_r'], 3)} |"

    lines = [f"Generated {out['generated_utc']} · record {out['record'][0]} → {out['record'][-1]} "
             f"(read-only, the uncapped pipeline; served-block counts assert: "
             f"{'held' if out['served_counts_equal'] else 'FAILED'})", "",
             "| | served (before) | from the fill (after) |", "|---|---|---|",
             f"| closed n | {b['n_closed']} | {a['n_closed']} |",
             f"| wins / losses | {b['wins']} / {b['losses']} | {a['wins']} / {a['losses']} |",
             f"| sum R (derived from rows) | {f(b['sum_r'])} | {f(a['sum_r'])} |",
             f"| mean R | {f(b['mean_r'], 3)} | {f(a['mean_r'], 3)} |",
             f"| median R | {f(b['median_r'], 3)} | {f(a['median_r'], 3)} |", "",
             f"Stops {out['stops']} · exactly −1.0 from the fill {out['stops_exactly_minus_one']} · "
             f"buckets changed {out['buckets_changed']} · served equals fill-based: {out['served_equals_fill_based']}",
             "", "| session | n | served sum R | from-the-fill sum R |", "|---|---|---|---|"]
    for d in sorted(set(b["per_session"]) | set(a["per_session"])):
        pb, pa = b["per_session"].get(d, {}), a["per_session"].get(d, {})
        lines.append(f"| {d} | {pa.get('n', pb.get('n', 0))} | {f(pb.get('sum_r'))} | {f(pa.get('sum_r'))} |")
    lines += ["", "| worst stops from the fill | trigger | stop | fill | fill over trigger % | R % | after R |",
              "|---|---|---|---|---|---|---|"]
    for w in out["worst"]:
        lines.append(f"| {w['id']} | {w['trigger']} | {w['stop']} | {w['fill_px']} | {f(w['pct'])} | "
                     f"{w['r_pct']} | {f(w['after'])} |")
    q = dc["quartiles"]
    lines += ["", "| the counted closed rows, R from the fill | n | sum R | mean R |", "|---|---|---|---|",
              band("all", dc["all"]),
              band(f"without the rows under GC.LEDGER_MIN_R_PCT ({dc['thin_cut']}) %: {', '.join(dc['thin']) or '—'}",
                   dc["without_thin"])]
    for k, s in enumerate(q):
        lines.append(band(f"fill-over-trigger quartile {k + 1} ({f(s['lo_pct'])} to {f(s['hi_pct'])} %)", s))
    lines += [band("fill exactly on the trigger", dc["on_trigger"]),
              band(f"fill above the trigger by at most LC.LUK_NO_CHASE_PCT ({dc['no_chase_pct']}) %",
                   dc["at_most_no_chase"]),
              band("fill above the trigger by more than LC.LUK_NO_CHASE_PCT %", dc["over_no_chase"]),
              f"| {dc['fill_risk_label']} | {dc['all']['n']} | {f(dc['fill_risk_sum_r'])} | "
              f"{f(dc['fill_risk_mean_r'], 3)} |", "",
              f"The two worst rows carry {dc['top2_share_pct']} % of the sum. A reading, not a rule — HIS CALL."]
    return "\n".join(lines) + "\n"


# ── the container run (origin/main engines only; read-only) ─────────────────────────────────────────────────────
def main() -> int:
    from datetime import datetime, timezone

    from chart_maps.gajjala import constants as GC
    from chart_maps.luk import constants as LC
    from chart_maps.luk import ledger as LL
    from chart_maps.luk import store as LS

    now = datetime.now(timezone.utc)
    today = now.astimezone(LL.ET).date()
    store = LS.dry_store()                                     # reads through; any write is recorded, never sent
    record = LL.record_sessions(today)
    rows = LL.rows_for(record, store)
    docs_l = store.ledger_docs(record) if record else []
    if docs_l is None:
        sys.stderr.write("luk_ledger could not be read\n")
        return 1
    docs = {d.get("_id"): d for d in docs_l if isinstance(d, dict)}
    rows_by_id = {r["id"]: r for r in rows}
    served = [LL.track_row(r, docs.get(r["id"])) for r in rows]          # the uncapped pipeline (F17)
    weeks = LL.entry_weeks(served)
    LL.mark_dups(served, docs, rows_by_id)
    counts, _text = LL.counts_of(served, weeks)
    blk = LL.served_block(store, today, now, span="all")
    served_equal = blk.get("counts") == counts

    closed, stops, exact, changed, served_fill = [], 0, 0, 0, True
    for c in served:
        if c.get("dup_of") or c["state"] not in (STOP, EMA9) or c.get("r") is None:
            continue
        row = rows_by_id[c["id"]]
        doc = docs.get(c["id"]) or {}
        f = doc.get("fill") if isinstance(doc.get("fill"), dict) else {}
        w = doc.get("walk") if isinstance(doc.get("walk"), dict) else {}
        fpx = f.get("fill_px")
        before = float(c["r"])
        if c["state"] == STOP:
            stops += 1
            after = probe_stop_r(row.get("trigger"), row.get("stop"), fpx)
            exact += 1 if after == -1.0 else 0
            served_fill = served_fill and after is not None and before == after
        else:
            after = before
        if LL.bucket_of(c["state"], before) != LL.bucket_of(c["state"], after):
            changed += 1
        closed.append({"id": c["id"], "date": c["date"], "state": c["state"], "before": before, "after": after,
                       "trigger": row.get("trigger"), "stop": row.get("stop"), "fill_px": fpx,
                       "pct": fill_over_trigger_pct(row.get("trigger"), fpx), "r_pct": row.get("r_pct"),
                       "fill_risk_r": fill_risk_r(c["state"], w.get("exit_px"), fpx, row.get("stop"))})
    worst = sorted([x for x in closed if x["state"] == STOP and x["after"] is not None], key=lambda x: x["after"])[:6]
    dec_rows = [{"id": x["id"], "r": x["after"], "pct": x["pct"], "r_pct": x["r_pct"],
                 "fill_risk_r": x["fill_risk_r"]} for x in closed]
    out = {"generated_utc": now.isoformat(), "record": [d.isoformat() for d in record],
           "served_counts_equal": served_equal, "served_counts": blk.get("counts"), "pipeline_counts": counts,
           "before": summary(closed, "before"), "after": summary(closed, "after"), "stops": stops,
           "stops_exactly_minus_one": exact, "buckets_changed": changed, "served_equals_fill_based": served_fill,
           "worst": [{k: x[k] for k in ("id", "trigger", "stop", "fill_px", "pct", "r_pct", "before", "after")}
                     for x in worst],
           "decomposition": decompose(dec_rows, LC.LUK_NO_CHASE_PCT, GC.LEDGER_MIN_R_PCT),
           "writes": list(getattr(store, "writes", []) or [])}
    sys.stdout.write(json.dumps(out, default=str, allow_nan=False) + "\n")
    if not served_equal:
        sys.stderr.write("served_block counts != the uncapped pipeline's counts_of\n")
        return 1
    if out["writes"]:
        sys.stderr.write("a write was attempted — refused\n")
        return 1
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--md":
        with open(sys.argv[2], encoding="utf-8") as fh:
            sys.stdout.write(md_table(json.load(fh)))
        sys.exit(0)
    sys.exit(main())
