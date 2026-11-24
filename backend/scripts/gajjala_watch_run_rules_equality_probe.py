"""▶ run Gajjala's rules — the EQUALITY probe, read-only (2026-11-24, spec ggrun rev 2 §4 be-run, critique C6).

Ajay 2026-11-24, verbatim: "On the Watch list I need a run button to run against Gajjalas rules of a stock to see for
patterns of 5 patterns he has especially reversal squeeze.."

The critic's 11-24 probe made durable. For every Watch name (his + that session's 🤖 names) that has a stored 🚩 read
doc for the session: frames built with `run_rules.load_day` (no cache write) at the stored read's own clock
(`updated_at`), graded with `run_rules.grade` and the stored read's own float (`tab._float_read`) and the run's K11
volume (`bars.session_volume`), then compared with the stored read: per setup the state, the 🚩 state label and every
rule row (label / ok / value / need). Prints each row difference, the totals, and the K11 direction — the run's minute
sum ÷ the stored scan row's volume (`gajjala_scan` `last.volume`), with n, min, median, max.

The probe writes nothing. One Massive minute call per name (the session) + the prior day on a cache miss. A row
difference is reported, never "fixed": Massive's bars for a closed minute can change after the pass read them.

  python -m scripts.gajjala_watch_run_rules_equality_probe [--date 2026-11-23]
  docker exec -i -w /app cheetah-market-app-api-1 python - --date 2026-11-23 < backend/scripts/gajjala_watch_run_rules_equality_probe.py

Display only, UNMEASURED.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from datetime import date, datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

BACKEND = (str(Path(__file__).resolve().parents[1])
           if str(globals().get("__file__") or "").endswith(".py") else None)
if BACKEND and BACKEND not in sys.path and not __package__:
    sys.path.insert(0, BACKEND)

ET = ZoneInfo("America/New_York")
ROW_FIELDS = ("label", "ok", "value", "need")


def _rows(read) -> dict:
    out = {}
    for c in (read or {}).get("criteria") or []:
        if isinstance(c, dict) and c.get("key") is not None:
            out[c["key"]] = {k: c.get(k) for k in ROW_FIELDS}
    return out


def compare(read: dict, stored: dict) -> dict:
    """{state_diff, label_diff, rows}: `rows` = exactly the rule rows whose label / ok / value / need differ (or that
    exist on one side only), as [{key, run, stored}] in key order. Pure — no I/O."""
    from chart_maps.gajjala import tab as GT
    read, stored = read or {}, stored or {}
    a, b = _rows(read), _rows(stored)
    rows = [{"key": k, "run": a.get(k), "stored": b.get(k)} for k in sorted(set(a) | set(b), key=str)
            if a.get(k) != b.get(k)]
    return {"state_diff": read.get("state") != stored.get("state"),
            "label_diff": GT.state_label(read) != GT.state_label(stored), "rows": rows}


def k11_ratios(pairs) -> dict:
    """{n, min, median, max} of minute sum ÷ scan volume over the (sum, scan) pairs where both are positive numbers."""
    xs = [s / v for s, v in pairs if isinstance(s, (int, float)) and isinstance(v, (int, float)) and s > 0 and v > 0]
    if not xs:
        return {"n": 0, "min": None, "median": None, "max": None}
    return {"n": len(xs), "min": round(min(xs), 4), "median": round(statistics.median(xs), 4),
            "max": round(max(xs), 4)}


def late_clock(session: date) -> datetime:
    """The session's last pass clock (GC.PASS_CLOSE_ET, read by name)."""
    from chart_maps.gajjala import constants as GC
    return datetime.combine(session, dtime.fromisoformat(GC.PASS_CLOSE_ET), tzinfo=ET)


def _clock_of(doc, session: date) -> datetime:
    """The stored read's own clock (`updated_at`, ET); none → late_clock(session)."""
    from chart_maps.gajjala_watch import payload as PL
    et = PL._to_et((doc or {}).get("updated_at"))
    return et if et is not None else late_clock(session)


def main(argv=None) -> int:
    from chart_maps.gajjala import bars as B
    from chart_maps.gajjala import detectors as D
    from chart_maps.gajjala import store as GST
    from chart_maps.gajjala import tab as GT
    from chart_maps.gajjala_watch import constants as C
    from chart_maps.gajjala_watch import run_rules as RR
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", default=None, help="YYYY-MM-DD; default = the board's session (tab.session_for)")
    a = ap.parse_args(argv)
    session = date.fromisoformat(a.date) if a.date else GT.session_for(datetime.now(ET))[0]
    st = GST.default()
    names = RR.watch_names(None, late_clock(session))
    scan_vol = {d.get("symbol"): (d.get("last") or {}).get("volume") for d in st.scan_docs([session])}
    tot = {"names": 0, "setups": 0, "state_diff": 0, "label_diff": 0, "setups_with_row_diff": 0, "asof_equal": 0}
    pairs = []
    for s in names:
        doc = st.get_read(session, s)
        if not isinstance(doc, dict):
            continue
        now = _clock_of(doc, session)
        pn: dict = {}
        frames = B.frames_for([s], session, now, load_day=RR.load_day, budget_sec=C.RUN_BUDGET_SEC, stats={},
                              per_name=pn)
        fr = frames.get(s)
        if fr is None:
            print(f"{s}: no frames ({pn.get(s)})")
            continue
        sv = B.session_volume(fr)
        pairs.append((sv, scan_vol.get(str(s).upper())))
        reads = RR.grade(fr, {"symbol": s, "float_read": GT._float_read(doc, None), D.K11_CTX_KEY: sv})
        tot["names"] += 1
        tot["asof_equal"] += int(fr.as_of_bar_t5 == doc.get("as_of_bar_t5"))
        for k in RR.setup_order():
            cmp = compare(reads.get(k), (doc.get("setups") or {}).get(k))
            tot["setups"] += 1
            tot["state_diff"] += int(cmp["state_diff"])
            tot["label_diff"] += int(cmp["label_diff"])
            tot["setups_with_row_diff"] += int(bool(cmp["rows"]))
            for r in cmp["rows"]:
                print(f"{s} {k} {r['key']}: run {r['run']} | stored {r['stored']}")
    print(session.isoformat(), tot)
    print("K11 minute sum ÷ scan volume:", k11_ratios(pairs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
