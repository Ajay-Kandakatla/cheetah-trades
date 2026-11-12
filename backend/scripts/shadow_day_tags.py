"""Shadow day tags (rec157 WP-2, 2026-11-11) — the host CLI. RECORD ONLY: one record per closed session appended to
an append-only JSONL store outside the repo; nothing served reads it, no gate, no push, no page word.

  python3 backend/scripts/shadow_day_tags.py [--session D] [--out DIR] [--from-json FILE] [--recompute A..B]
                                             [--container NAME] [--dry-run]
  python  backend/scripts/shadow_day_tags.py --build-fixture STUDY_DIR OUT     (api image only; lazy pandas)

It runs the read-only probe itself (ONE `docker exec -i -w /app <container> python - < probe`), or reads `--from-json`.
Prints ONE JSON summary line {"session", "appended", "gap_sessions", "missing_retry", "orphan_inputs", "exit", …}.
Exit 0 ok · 2 refused (a corrupt store, an unclosed session, a probe failure) — the scheduled task must surface a 2.
Stdlib only, Python 3.9-safe. Store format + rules: docs/gajjala/shadow_day_tags_2026_11_11.md."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

try:
    from scripts import shadow_day_tags_lib as LIB
except ImportError:                                             # run as a file: backend/scripts is sys.path[0]
    import shadow_day_tags_lib as LIB

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE = os.path.join(HERE, "shadow_day_tags_probe.py")
DEFAULT_OUT = "/Users/ajay/clinet-test/eod-audits/shadow-day-tags"
DEFAULT_CONTAINER = "cheetah-market-app-api-1"
EXIT_OK, EXIT_REFUSED = 0, 2


def run_probe(container: str) -> dict:
    with open(PROBE, "rb") as fh:
        p = subprocess.run(["docker", "exec", "-i", "-w", "/app", container, "python", "-"], stdin=fh,
                           capture_output=True, timeout=900)
    if p.returncode != 0:
        raise RuntimeError("probe exit %d: %s" % (p.returncode, p.stderr.decode("utf-8", "replace")[-600:]))
    return json.loads(p.stdout.decode("utf-8"))


def _summary(session, exit_code, **kw) -> dict:
    out = {"session": session, "appended": [], "gap_sessions": [], "missing_retry": [], "orphan_inputs": [],
           "exit": exit_code}
    out.update(kw)
    return out


def _range(text: str, sessions: list) -> list:
    a, b = text.split("..")
    return [d for d in sessions if a <= d <= b], b


def run(args) -> dict:
    out_dir = args.out
    store_path = os.path.join(out_dir, LIB.STORE_NAME)
    try:
        records = LIB.load_store(store_path)
    except LIB.StoreCorrupt as exc:
        return _summary(args.session, EXIT_REFUSED, why="store corrupt: %s" % exc)
    orphans = LIB.orphan_inputs(out_dir, records)
    try:
        if args.from_json:
            with open(args.from_json) as fh:
                inputs = json.load(fh)
        else:
            inputs = run_probe(args.container)
    except Exception as exc:                                    # noqa: BLE001 — surfaced as a refusal
        return _summary(args.session, EXIT_REFUSED, orphan_inputs=orphans, why="no inputs: %s" % exc)
    sessions = list(inputs.get("sessions") or [])
    closed = inputs.get("last_closed_session")
    target = args.session or closed
    if not target or not closed or target > closed:
        return _summary(target, EXIT_REFUSED, orphan_inputs=orphans,
                        why="session %s is not closed (last closed %s)" % (target, closed))
    if target not in sessions:
        return _summary(target, EXIT_REFUSED, orphan_inputs=orphans, why="%s is not a market day" % target)

    if args.recompute:
        todo, last = _range(args.recompute, sessions)
        if last > closed:
            return _summary(target, EXIT_REFUSED, orphan_inputs=orphans,
                            why="--recompute reaches %s, past the last closed session %s" % (last, closed))
        plan = {"target": target, "gaps": [], "missing_retry": []}
        jobs = [(d, "recompute") for d in todo]
    else:
        plan = LIB.sessions_to_compute(records, inputs, target)
        jobs = [(d, "plain") for d in plan["gaps"]] + [(d, "retry") for d in plan["missing_retry"]]
        jobs.append((target, "plain"))
        jobs.sort(key=lambda j: j[0])

    tags = LIB.compute_all(inputs, sorted({d for d, _ in jobs}))
    blob = LIB.inputs_blob(inputs)
    inputs_rel = LIB.next_inputs_name(out_dir, str(inputs.get("today_et") or target))
    now = datetime.now(timezone.utc).isoformat()
    constants = dict(inputs.get("constants") or {})
    constants.update({"STALE_MIN": LIB.STALE_MIN, "WEEK": LIB.WEEK, "TWO_WEEKS": LIB.TWO_WEEKS,
                      "PILLAR_WEAK_MIN": LIB.PILLAR_WEAK_MIN, "GD6_MIN_HIST": LIB.GD6_MIN_HIST,
                      "GD3W_SHARE": LIB.GD3W_SHARE, "LD9_MIN_PILLARS": LIB.LD9_MIN_PILLARS,
                      "PRE_CUT": LIB.hm_text(LIB.PRE_CUT), "GD4_PRE_CUT": LIB.hm_text(LIB.GD4_PRE_CUT),
                      "PILLARS": list(LIB.PILLARS), "FORWARD_FROM": LIB.FORWARD_FROM})
    lines, work = [], list(records)
    for d, mode in jobs:
        meta = {"recorded_at_utc": now, "late": d < target, "constants": constants, "source_tags": LIB.SOURCE_TAGS,
                "inputs_sha256": LIB.sha256_hex(blob), "inputs_file": inputs_rel,
                "probe_generated_utc": inputs.get("generated_utc")}
        rec = LIB.plan_append(work, d, tags[d], meta, mode=mode)
        if rec is not None:
            lines.append(rec)
            work.append(rec)
    res = _summary(target, EXIT_OK, gap_sessions=plan["gaps"], missing_retry=plan["missing_retry"],
                   orphan_inputs=orphans,
                   appended=[{"session": r["session"], "rev": r["rev"], "late": r["late"], "changed": r["changed"]}
                             for r in lines])
    if args.dry_run:
        res["dry_run"] = True
        return res
    if lines:
        LIB.write_run(out_dir, inputs_rel, blob, lines)
        res["inputs_file"] = inputs_rel
    return res


# ── the fixture (api image only — pandas + the house EMA; never on the daily path) ───────────────────────────────
def build_fixture(study_dir: str, out_path: str) -> dict:
    """Reduce STUDY/rows.json, STUDY/gg5_strip_snapshot_2026-11-11.json and STUDY/day_probe.json to the probe's
    `inputs` shape (EMAs by orderflow.signals.ema, as the study) and record their sha256 in the fixture."""
    import pandas as pd                                         # lazy: api image only
    from orderflow.signals import ema
    from chart_maps.gajjala import audited_rules as AR, constants as GC
    try:
        from scripts import shadow_day_tags_probe as PR         # the ONE ast reader (the probe's)
    except ImportError:
        import shadow_day_tags_probe as PR

    names = ("rows.json", "gg5_strip_snapshot_2026-11-11.json", "day_probe.json")
    src = {}
    for n in names:
        with open(os.path.join(study_dir, n), "rb") as fh:
            raw = fh.read()
        src[n] = (json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest())
    rows_doc, strip_doc, probe = src["rows.json"][0], src[names[1]][0], src["day_probe.json"][0]
    sessions = list(probe["gg_sessions"])
    t1030 = AR.T2_FIRST_HOUR_END_ET.strftime("%H:%M")
    v = next(x for x in rows_doc["variants"] if x["variant"] == "gajjala")
    row_keys = ("id", "date", "symbol", "setup", "kind", "line", "at_utc", "trigger", "stop", "thin", "plan")
    cell_keys = ("fill_t", "exit_t", "end_t", "outcome", "fill_px", "close_pct")
    gg5 = []
    for r in v["rows"]:
        x = {k: r.get(k) for k in row_keys}
        for h in ("same", "next"):
            x[h] = {k: r[h].get(k) for k in cell_keys} if isinstance(r.get(h), dict) else None
        x.update({k: r.get(k) for k in ("state_same", "state_next", "bucket", "dup_of")})
        gg5.append(x)
    n_all = len(gg5)
    gg5 = [x for x in gg5 if x["line"] == "live" and LIB.trade_of(x) and x["bucket"] in ("win", "loss", "open", "flat")]
    by = {}
    for p in strip_doc["rows"]:
        hm = p["id"].split("|")[1][:5]
        by.setdefault(p["date"], []).append((hm, str(p.get("at")), p["id"], p))
    passes, last_id, last_at = {}, None, None
    for d in sessions:
        ps = sorted(by.get(d, []), key=lambda x: (x[0], x[1], x[2]))
        passes[d] = {}
        for cut in (LIB.hm_text(LIB.PRE_CUT), t1030):
            c = [x[3] for x in ps if x[0] <= cut]
            p = c[-1] if c else None
            s = (p or {}).get("strip")
            passes[d][cut] = None if p is None else {
                "id": p["id"], "date": p["date"], "at": p.get("at"),
                "strip": {"n_population": s.get("n_population")} if isinstance(s, dict) else None}
        for x in ps:
            if last_at is None or x[1] > last_at:
                last_at, last_id = x[1], x[2]
    intra = {}
    for key, bs in probe["index_intraday"].items():
        if bs is None:
            intra[key] = None
            continue
        d = key.split("|")[1]
        cut = LIB.at_cut(d, LIB.hm_of(t1030))
        keep = []
        for b in bs:
            t = LIB.et_of(b[0])
            if b[6] == "rth" and t is not None and t + timedelta(minutes=1) <= cut:
                keep.append(b)
        intra[key] = keep
    iwm = probe["index_daily"]["IWM"]
    df = pd.DataFrame(iwm["bars"], columns=["date", "open", "high", "low", "close", "volume"]).set_index("date")
    c = df["close"].astype(float)
    e9, e21 = ema(c, 9), ema(c, 21)
    iwm_rows = [[d, float(c.iloc[k]), float(e9.iloc[k]), float(e21.iloc[k])] for k, d in enumerate(df.index)]
    pillars = {s: rows for s, rows in probe["pillars"].items()}
    ge_path = os.path.join(HERE, "..", "trading", "gajjala_entry.py")
    dd_path = os.path.join(HERE, "..", "daytrading", "data.py")
    inputs = {
        "generated_utc": probe["generated_utc"], "today_et": probe["today_et"], "sessions": sessions,
        "last_closed_session": sessions[-1],
        "constants": {"T2_FIRST_HOUR_END_ET": t1030, "LEDGER_MIN_R_PCT": GC.LEDGER_MIN_R_PCT,
                      "GG_LOSS_RISK_CUT": PR.ast_constant(ge_path, "GG_LOSS_RISK_CUT"),
                      "ET_RTH_OPEN": PR.ast_constant(dd_path, "ET_RTH_OPEN"),
                      "MEASURE_FLOOR_WEEKS": AR.MEASURE_FLOOR_WEEKS},
        "gg5_rows": gg5, "gg5_rows_error": None, "passes": passes, "index_intraday": intra,
        "iwm_daily": {"rows": iwm_rows[-60:], "cached_at": iwm.get("cached_at")}, "pillars": pillars,
        "asof": {"gg5_last_graded_at": None, "passes_last_id": last_id,
                 "qqq_last_date": max((k.split("|")[1] for k, b in intra.items() if k.startswith("QQQ|") and b),
                                      default=None),
                 "iwm_last_date": max((k.split("|")[1] for k, b in intra.items() if k.startswith("IWM|") and b),
                                      default=None),
                 "iwm_daily_last_date": iwm_rows[-1][0], "iwm_daily_cached_at": iwm.get("cached_at"),
                 "pillars_last_date": {s: (r[-1][0] if r else None) for s, r in sorted(pillars.items())},
                 "pillars_cached_at": {}},
        "fixture_sources": {n: src[n][1] for n in names},
        "fixture_reduction": "gg5_rows: only the live rows trade_of counts as FILLED (the only rows the eight formulas "
                             "read; %d of %d kept); every other block is the probe's shape, whole" % (len(gg5), n_all),
    }
    with open(out_path, "w") as fh:
        json.dump(inputs, fh, sort_keys=True, allow_nan=False, separators=(",", ":"))
        fh.write("\n")
    return {"out": out_path, "bytes": os.path.getsize(out_path), "sources": inputs["fixture_sources"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--session")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--from-json", dest="from_json")
    ap.add_argument("--recompute")
    ap.add_argument("--container", default=DEFAULT_CONTAINER)
    ap.add_argument("--dry-run", dest="dry_run", action="store_true")
    ap.add_argument("--build-fixture", dest="build_fixture", nargs=2, metavar=("STUDY_DIR", "OUT"))
    args = ap.parse_args(argv)
    if args.build_fixture:
        print(json.dumps(build_fixture(*args.build_fixture), sort_keys=True))
        return EXIT_OK
    res = run(args)
    print(json.dumps(res, sort_keys=True))
    return res["exit"]


if __name__ == "__main__":
    sys.exit(main())
