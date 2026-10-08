"""Build the FE fixture for the 🛡️ 🚀 revenue-line words (2026-10-08).

Every string comes from the REAL builders (`resiliency_tab.growth_read`,
`growth_coverage`, `growth_line`, `growth_gaps_block`, `tile_badges`,
`tile_stats`) over research-doc shapes the heal writes: BAC on the net line
(Q2-2026 10-Q: 31,558 / 27,443 M), SOFI held (NOTE_NO_NII), CVX his call, one
undetermined bank quarter, plus a legacy doc. Hermetic, no network, no Mongo.

    cd backend && PYTHONPATH=. python scripts/resiliency_revenue_line_fixture.py \
        > ../frontend/src/components/__fixtures__/resiliency_revenue_line_2026_10_08.json
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone

from chart_maps import resiliency_tab as R
from sepa import massive_fundamentals as MF

TODAY = date(2026, 10, 7)
CACHED = 1790700000.0
NOW = datetime(2026, 10, 8, 0, 30, tzinfo=timezone.utc)      # 20:30 ET 10-07, after the close
PER = [8105, 8104, 8103, 8102, 8101, 8100]


def _fund(*, rev_pct=None, eps_pct=None, rev=None, eps=None, **line):
    f = {"sales": {}, "rev_growth_q_pct": rev_pct, "q_eps_growth_pct": eps_pct,
         "q_period_series": list(PER), "rev_q_series": rev, "eps_q_series": eps,
         "ni_q_series": None, "_source": "hybrid", "cached_at": CACHED}
    f.update(line)
    return f


DOCS = {
    "BAC": (_fund(rev_pct=14.99, eps_pct=10.0, rev=[31558e6, 1, 1, 1, 27443e6, 1],
                  eps=[1.1, 1, 1, 1, 1.0, 1], rev_line=MF.LINE_NET_OF_INTEREST,
                  rev_line_note=None, rev_line_mixed=0), 9e9),
    "SOFI": (_fund(rev_pct=27.35, rev=[429298000.0, 1, 1, 1, 337107000.0, 1],
                   rev_line=MF.LINE_REVENUE, rev_line_note=MF.NOTE_NO_NII, rev_line_mixed=0), 5e9),
    "CVX": (_fund(rev_pct=51.43, rev=[67199e6, 1, 1, 1, 44375e6, 1],
                  rev_line=MF.LINE_REVENUE, rev_line_note=MF.NOTE_SUBLINE_CALL,
                  rev_line_mixed=0), 7e9),
    "UND": (_fund(rev=[None, 1, 1, 1, 3.0e9, 1], rev_line=MF.LINE_UNDETERMINED,
                  rev_line_note=None, rev_line_mixed=0), 1e9),
    "VST": (_fund(rev_pct=-5.48, eps_pct=-6.17, rev=[4.0e9, 4.1e9, 4.1e9, 4.1e9, 4.232e9, 4.0e9],
                  eps=[0.76, 1.0, 1.0, 1.0, 0.81, 1.0]), 3e9),
}


def build() -> dict:
    reads = {s: {"growth": R.growth_read(f, today=TODAY), "adv50": adv, "bars": 400}
             for s, (f, adv) in DOCS.items()}
    R.score_growth([r["growth"] for r in reads.values()])
    cov = R.growth_coverage(reads, min_bars=100, ttl_days=16)
    tiles = []
    for s, rd in reads.items():
        row = {"symbol": s, "resiliency": {"growth": rd["growth"]}}
        tiles.append({"symbol": s, "badges": R.tile_badges(row), "stats": R.tile_stats(row),
                      "growth": rd["growth"]})
    return {"_about": "built by backend/scripts/resiliency_revenue_line_fixture.py (2026-10-08)",
            # the real served block (`_block`); the header is incidental, not under test
            "resiliency_board": R._block("ready", now=NOW, sort=R.SORT_GROWTH,
                                         header="fixture header (not under test)",
                                         entry={"growth_coverage": cov, "session": TODAY.isoformat(),
                                                "built_at": NOW.isoformat()}),
            "tiles": tiles}


if __name__ == "__main__":                                  # pragma: no cover
    json.dump(build(), sys.stdout, indent=1, ensure_ascii=False, default=str)
    sys.stdout.write("\n")
