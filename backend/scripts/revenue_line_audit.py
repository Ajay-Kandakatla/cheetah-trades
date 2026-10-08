"""Revenue-line audit — the durability tripwire for semantic change 7 (2026-10-08).

WHAT IT CHECKS. `massive_fundamentals.revenue_line` picks each quarter's revenue
line by v1's statement template (banks: revenue − cost_of_revenue + other
income). This script reads the research docs that line produced and checks the
latest quarter and its year-ago quarter against SEC companyfacts XBRL — the
10-Q's own tags, the year-ago value from the SAME accession (the comparative
column), never a separately filed number. It prints a table and SUGGESTED
ledger edits; it never edits code and never writes Mongo (`block_writes()`
first). 0 Massive calls.

    python scripts/revenue_line_audit.py --held --financial [--out /out/audit.json]
    python scripts/revenue_line_audit.py --symbols BAC,JPM,C

VERDICTS. match = some audited tag reproduces the stored % within
`AUDIT_PCT_TOL` pp OR both quarter levels within `AUDIT_LEVEL_TOL` — the
2026-10-07 measurement's REPRESENTATION tolerances, not rules. mismatch = SEC
has the pair and no tag reproduces it. unchecked = SEC has no pair at that
quarter (companyfacts lags: C sat at 2025-09-30 on 2026-10-07) — NEVER a
mismatch.

THE R-FILE FACE IS THE ARBITER. Where a companyfacts tag is not the 10-Q's
face line (MTB, CPT, RSG, HAS measured 2026-10-07) this may say "mismatch"
where the face says match; re-check the face (the R2/R4 page of the filing)
before editing `REVENUE_LINE_PICKS` / `REVENUE_LINE_HOLD`. See
docs/sepa/revenue_lines_2026_10_08.md.

SEC fair access: User-Agent from `SEC_USER_AGENT` (giants.edgar), ≤ 5 req/s
(`giants.edgar._get` sleeps 0.15 s, plus `AUDIT_EXTRA_SLEEP`).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path
from typing import Optional

AUDIT_TAGS = ("RevenuesNetOfInterestExpense", "Revenues",
              "RevenueFromContractWithCustomerExcludingAssessedTax",
              "RegulatedAndUnregulatedOperatingRevenue", "RegulatedOperatingRevenue")
SUM_TAG = "NII+NonII"
SUM_ADDENDS = ("InterestIncomeExpenseNet", "NoninterestIncome")
AUDIT_PCT_TOL = 0.10        # pp — the 2026-10-07 measurement's representation tolerance, NOT a rule
AUDIT_LEVEL_TOL = 0.002     # 0.2 % of the SEC level — same measurement, NOT a rule
AUDIT_EXTRA_SLEEP = 0.06    # s, on top of giants.edgar's 0.15 s → ≤ 5 req/s
DAYS_PER_MONTH = 30.44      # definitional: a "3-month" fact is one whose span rounds to 3 months
CF_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
DOC_FIELDS = ("rev_q_series", "q_end_series", "rev_growth_q_pct", "rev_line", "rev_line_note")


def _day(v) -> Optional[date]:
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def _three_month(f: dict) -> bool:
    s, e = _day(f.get("start")), _day(f.get("end"))
    if s is None or e is None:
        return False
    return round(((e - s).days + 1) / DAYS_PER_MONTH) == 3


def _facts_usd(facts: dict, tag: str) -> list:
    g = ((facts or {}).get("facts") or {}).get("us-gaap") or {}
    return [f for f in (((g.get(tag) or {}).get("units") or {}).get("USD") or [])
            if isinstance(f, dict)]


def _tag_pair(facts: dict, tag: str, end: str, year_ago_end: str) -> Optional[tuple]:
    """(cur, ya, accn) — the 3-month value ending `end` and the 3-month value
    ending `year_ago_end` from the SAME accession; the earliest-filed such
    accession (the quarter's own 10-Q). None when SEC has no such pair."""
    rows = [f for f in _facts_usd(facts, tag) if _three_month(f)]
    cur = {}
    ya = {}
    for f in rows:
        if str(f.get("end")) == end:
            cur.setdefault(f.get("accn"), f)
        elif str(f.get("end")) == year_ago_end:
            ya.setdefault(f.get("accn"), f)
    both = [a for a in cur if a in ya]
    if not both:
        return None
    a = min(both, key=lambda x: str(cur[x].get("filed") or ""))
    try:
        return float(cur[a]["val"]), float(ya[a]["val"]), a
    except (KeyError, TypeError, ValueError):
        return None


def sec_quarter_pair(facts: dict, end: str, year_ago_end: str) -> dict:
    """{tag: (cur, ya, accn)} for every audited tag SEC carries at that pair,
    plus `NII+NonII` (InterestIncomeExpenseNet + NoninterestIncome, both from
    one accession). PURE."""
    out = {}
    if not end or not year_ago_end:
        return out
    for t in AUDIT_TAGS:
        p = _tag_pair(facts, t, end, year_ago_end)
        if p is not None:
            out[t] = p
    a, b = (_tag_pair(facts, t, end, year_ago_end) for t in SUM_ADDENDS)
    if a is not None and b is not None and a[2] == b[2]:
        out[SUM_TAG] = (a[0] + b[0], a[1] + b[1], a[2])
    return out


def _pct(cur, ya) -> Optional[float]:
    try:
        cur, ya = float(cur), float(ya)
    except (TypeError, ValueError):
        return None
    return None if ya == 0 else round((cur - ya) / abs(ya) * 100.0, 2)


def _near(a, b) -> bool:
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return False
    return b != 0 and abs(a - b) <= AUDIT_LEVEL_TOL * abs(b)


def verdict(cur, ya, pct, pairs: dict) -> dict:
    """{"verdict": "match" | "mismatch" | "unchecked", "tag", "sec_pct"}. PURE.
    No SEC pair (or no stored figure) → "unchecked", never "mismatch"."""
    pairs = pairs if isinstance(pairs, dict) else {}
    order = [t for t in AUDIT_TAGS + (SUM_TAG,) if t in pairs]
    if not order or (pct is None and (cur is None or ya is None)):
        return {"verdict": "unchecked", "tag": None, "sec_pct": None}
    for t in order:
        c, y, _a = pairs[t]
        sp = _pct(c, y)
        by_pct = pct is not None and sp is not None and abs(float(pct) - sp) <= AUDIT_PCT_TOL
        by_level = _near(cur, c) and _near(ya, y)
        if by_pct or by_level:
            return {"verdict": "match", "tag": t, "sec_pct": sp}
    t = order[0]
    return {"verdict": "mismatch", "tag": t, "sec_pct": _pct(*pairs[t][:2])}


def _ledger_ciks() -> dict:
    from sepa import massive_fundamentals as MF
    return {v[0]: k for k, v in {**MF.REVENUE_LINE_PICKS, **MF.REVENUE_LINE_HOLD}.items()}


def _select(coll, *, symbols, held, financial) -> list:
    want = set(s.upper() for s in (symbols or []))
    if held:
        want |= set(_ledger_ciks())
    if financial:
        from sepa import massive_fundamentals as MF
        for d in coll.find({"fundamentals.rev_line": MF.LINE_NET_OF_INTEREST}, {"symbol": 1}):
            if d.get("symbol"):
                want.add(str(d["symbol"]).upper())
    return sorted(want)


def _fetch_facts(cik: str) -> Optional[dict]:
    from giants import edgar
    try:
        time.sleep(AUDIT_EXTRA_SLEEP)
        return edgar._get(CF_URL.format(cik=str(cik).zfill(10))).json()
    except Exception as exc:                                # noqa: BLE001
        print(f"  companyfacts CIK{cik}: {type(exc).__name__}", file=sys.stderr)
        return None


def audit(symbols: list, *, coll, cik_of, fetch=_fetch_facts) -> list:
    proj = {"symbol": 1, **{f"fundamentals.{k}": 1 for k in DOC_FIELDS}}
    docs = {d["symbol"]: (d.get("fundamentals") or {})
            for d in coll.find({"symbol": {"$in": list(symbols)}}, proj) if d.get("symbol")}
    rows = []
    for s in symbols:
        f = docs.get(s) or {}
        rev, ends = f.get("rev_q_series") or [], f.get("q_end_series") or []
        cur = rev[0] if len(rev) > 4 else None
        ya = rev[4] if len(rev) > 4 else None
        end = ends[0] if len(ends) > 4 else None
        ya_end = ends[4] if len(ends) > 4 else None
        cik = cik_of(s)
        facts = fetch(cik) if (cik and end and ya_end) else None
        pairs = sec_quarter_pair(facts or {}, end, ya_end) if facts else {}
        v = verdict(cur, ya, f.get("rev_growth_q_pct"), pairs)
        rows.append({"symbol": s, "cik": cik, "rev_line": f.get("rev_line"),
                     "rev_line_note": f.get("rev_line_note"), "end": end, "year_ago_end": ya_end,
                     "cur": cur, "year_ago": ya, "pct": f.get("rev_growth_q_pct"),
                     "doc": bool(f), **v,
                     "pairs": {t: list(p) for t, p in pairs.items()}})
    return rows


def suggestions(rows: list) -> list:
    """Suggested ledger edits — text only, never applied."""
    out = []
    for r in rows:
        held = bool(r.get("rev_line_note"))
        if r["verdict"] == "mismatch" and not held:
            out.append(f"{r['symbol']} (CIK {r['cik']}): ranked line {r['rev_line']} does not "
                       f"reproduce SEC {r['tag']} {r['sec_pct']} vs stored {r['pct']} — check the "
                       "R-file face; if it agrees, add a REVENUE_LINE_HOLD entry")
        elif r["verdict"] == "match" and held:
            out.append(f"{r['symbol']}: held line reproduces SEC {r['tag']} — a candidate to "
                       "leave the hold ledger (HIS CALL)")
    return out


def main(argv=None) -> int:
    from scripts.resiliency_study import block_writes
    block_writes()
    ap = argparse.ArgumentParser(description="Revenue-line audit vs SEC companyfacts (read-only).")
    ap.add_argument("--symbols", default="")
    ap.add_argument("--held", action="store_true", help="every ticker in the picks + hold ledger")
    ap.add_argument("--financial", action="store_true",
                    help="every doc whose rev_line is net_of_interest")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    from sepa import research
    coll = research._get_cache()
    if coll is None:
        print("no research cache", file=sys.stderr)
        return 1
    syms = _select(coll, symbols=[s.strip() for s in a.symbols.split(",") if s.strip()],
                   held=a.held, financial=a.financial)
    led = _ledger_ciks()

    def cik_of(s):
        if s in led:
            return led[s]
        from supply_demand import whales_13d
        return whales_13d._ticker_to_cik(s)
    rows = audit(syms, coll=coll, cik_of=cik_of)
    counts: dict = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        print(f"{r['symbol']:6} {str(r['rev_line']):16} {r['verdict']:9} stored "
              f"{r['pct']} sec {r['sec_pct']} ({r['tag']})")
    sugg = suggestions(rows)
    print(json.dumps({"n": len(rows), "verdicts": counts}))
    for line in sugg:
        print("SUGGESTED:", line)
    if a.out:
        Path(a.out).write_text(json.dumps({"rows": rows, "verdicts": counts,
                                           "suggested": sugg}, indent=1, default=str))
    return 0


if __name__ == "__main__":                                  # pragma: no cover
    raise SystemExit(main())
