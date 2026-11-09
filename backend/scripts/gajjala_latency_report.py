"""⏱ Speed — the 🚩 A+ latency ledger, printed (GG LIVE P4, 2026-11-09). Supersedes the session probe probe_latency.py.

Prints `chart_maps.gajjala.latency.payload(span)` — the SAME function GET /trading/gajjala/latency serves (a test pins
the JSON equal), so the numbers on the 🏁 and here never differ. READ ONLY: Mongo finds on gajjala_alerts, gajjala_lane,
gajjala_lane_stream and gajjala_bar_final; no write, no broker, no HTTP.

RUN (read-only, inside the api container):
  docker exec -i -w /app cheetah-market-app-api-1 python -m scripts.gajjala_latency_report --span all
  docker exec -i -w /app cheetah-market-app-api-1 python -m scripts.gajjala_latency_report --span 10d --json

`--span` takes the 🏁's span keys (chart_maps/gajjala/constants.LEDGER_SPANS); `--span all` over the records since
2026-10-01 reproduces the 2026-11-09 baseline (docs/gajjala/latency_ledger_2026_11_09.md).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_maps.gajjala import constants as GC  # noqa: E402
from chart_maps.gajjala import latency as LT  # noqa: E402


def render_text(p: dict) -> str:
    """The served block as plain lines: the same served words and cells the frontend prints."""
    out = [p["title"], f"span: {p['span']} · alerts: {p['n_alerts']}"]
    if p.get("empty_text"):
        out.append(p["empty_text"])
    for s in p.get("summary") or []:
        out.append(f"[{s['label']}] n {s['n']}")
        for k in LT.STEPS:
            st = s["steps"][k]
            out.append(f"  {k:<12} n {st['n']:>3}  p50 {LT._num(st['p50']):>9}  p90 {LT._num(st['p90']):>9}  "
                       f"min {LT._num(st['min']):>9}  max {LT._num(st['max']):>9}")
    for c in p.get("ci") or []:
        out.append(c["text"])
    chk = p.get("check")
    if chk:
        out.append(chk["title"])
        out.extend("  " + x["text"] for x in chk["pairs"])
        out.append("  " + chk["entry_delta_r"]["text"])
        out.append("  " + chk["odd_lot_only"]["text"])
    fin = p.get("finality")
    if fin:
        out.append(fin["text"])
        out.extend("  " + x["text"] for x in fin["parts"])
    out.append(p["footnote"])
    out.append(p["placebo_text"])
    return "\n".join(out)


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="⏱ the 🚩 A+ latency ledger (read only)")
    ap.add_argument("--span", default=GC.LEDGER_SPAN_DEFAULT, choices=list(GC.LEDGER_SPANS))
    ap.add_argument("--json", action="store_true", help="print the served payload as JSON")
    args = ap.parse_args(argv)
    p = LT.payload(args.span)
    print(json.dumps(p, indent=1, ensure_ascii=False, sort_keys=True) if args.json else render_text(p))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
