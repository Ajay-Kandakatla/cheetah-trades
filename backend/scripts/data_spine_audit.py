"""The 📈 Bonde ↔ 🚀 Explosive Growth DATA SPINE audit — re-runnable.

Ajay 2026-09-20: *"Especially this in Bondes. I think bondes and explosive
growth are hand in hand."*

THE QUESTION THIS ANSWERS. Both boards read the SAME quarterly series out of
the SAME research cache, so a name must never read "explosive" on one and
"declining"/"refused" on the other off the same filed quarter. This script
measures whether they agree and, where they do not, says exactly why.

Run it in the api container (it needs Mongo and the latest scan file):

    docker exec -i -w /app cheetah-market-app-api-1 \\
        python -m scripts.data_spine_audit

JSON to stdout. Every counting function below is PURE over injected documents
so the repo tests pin the arithmetic without a database
(`backend/tests/test_data_spine_2026_09_20.py`).

2026-09-20, after his *"#2"*: `repair_outcome` reports where every row LANDS
once the series are densified by fiscal period (`sepa.qoq.align_series` +
`python -m sepa.qoq realign`) — re-tiered through the real `sales.compute` and
placed through the real `buyable_verdict._bonde_pillar`, with the headline and
prior holes counted apart. It is emitted under `"repair"`.

NOTHING HERE GATES, ALERTS OR BUYS, and nothing it reports is a measured
signal — it is a data-quality reconciliation, not a study.
"""
from __future__ import annotations

import json
import sys
from collections import Counter

from sepa import qoq as Q

TIERS = ("explosive", "strong", "steady", "weak", "declining", "unknown")


# ---------------------------------------------------------------------------
# pure counters — tested without Mongo
# ---------------------------------------------------------------------------
def _periods(doc: dict):
    f = (doc.get("fundamentals") or {}) if isinstance(doc, dict) else {}
    p = f.get("q_period_series") if isinstance(f, dict) else None
    return p if isinstance(p, list) else None


def _tier(doc: dict):
    f = (doc.get("fundamentals") or {}) if isinstance(doc, dict) else {}
    s = (f.get("sales") or {}) if isinstance(f, dict) else {}
    return s.get("tier")


def mismatch_by_tier(docs) -> dict:
    """{tier: count} and the symbols, for rows whose YoY pairs are NOT a year
    apart. `yoy_pairs_ok` ACCEPTS an unverifiable row, so a row with no period
    keys is never counted here — `unverifiable_count` reports those."""
    by_tier: Counter = Counter()
    syms: dict[str, list] = {}
    for d in docs:
        if Q.yoy_pairs_ok(_periods(d)):
            continue
        t = str(_tier(d) or "unknown")
        by_tier[t] += 1
        syms.setdefault(t, []).append(str(d.get("symbol") or "").upper())
    return {"by_tier": dict(by_tier), "total": sum(by_tier.values()),
            "symbols": {k: sorted(v) for k, v in syms.items()}}


def unverifiable_count(docs) -> int:
    """Rows with no checkable period keys — the residual the guard cannot see."""
    return sum(1 for d in docs if not Q.yoy_pairs_verifiable(_periods(d)))


def q4_shaped_share(docs) -> dict:
    """Of the mismatched rows, how many are missing a FY Q4?

    A fiscal index is `year*4 + (quarter-1)`, so FY Q4 is `idx % 4 == 3`. If
    the gap in the key sequence swallows an index congruent to 3, the shape is
    the Q4 hole the Bonde docstring already names (Massive's quarterly rows
    often lack Q4) rather than a random omission.
    """
    n = q4 = 0
    for d in docs:
        p = _periods(d)
        if Q.yoy_pairs_ok(p):
            continue
        n += 1
        ints = []
        for v in (p or []):
            try:
                ints.append(int(v))
            except (TypeError, ValueError):
                ints.append(None)
        got = {v for v in ints if v is not None}
        if not got:
            continue
        missing = {i for i in range(min(got), max(got) + 1)} - got
        if any(i % 4 == 3 for i in missing):
            q4 += 1
    return {"mismatched": n, "q4_shaped": q4,
            "pct": round(100.0 * q4 / n, 1) if n else None}


def character_pairs_mismatch(docs) -> int:
    """How many MORE rows the guard would hold out if it also checked the
    character clause's pairs (2,6) and (3,7) — `consecutive_growth_q` reaches
    that far back. Reported, NOT applied: the shipped guard checks exactly the
    two pairs the 🚀 growth board checks, so the boards agree by construction.
    HIS CALL (spec §7.2)."""
    extra = ((2, 6), (3, 7))
    n = 0
    for d in docs:
        p = _periods(d)
        if not Q.yoy_pairs_ok(p):
            continue                       # already held out on the two pairs
        if not Q.yoy_pairs_ok(p, pairs=extra):
            n += 1
    return n


def _series(doc: dict, key: str):
    f = (doc.get("fundamentals") or {}) if isinstance(doc, dict) else {}
    v = f.get(key) if isinstance(f, dict) else None
    return v if isinstance(v, list) else None


def repair_outcome(docs) -> dict:
    """WHERE EVERY MISMATCHED ROW LANDS AFTER THE 2026-09-20 REPAIR.

    Ajay 2026-09-20: *"#2 Yes"* — repair the pairs rather than keep holding
    the rows out. This counts the outcome of that repair on injected documents,
    with no database and no write: it densifies each row's series by fiscal
    period (`qoq.align_series`), recomputes the sales read through the REAL
    modules (`sepa.sales.compute` on `qoq.yoy_pct`), and places the row through
    the REAL clause (`buyable_verdict._bonde_pillar`) — never through a
    re-derived copy of either.

    `headline_hole` and `prior_hole` are reported SEPARATELY on purpose: the
    first has no growth base and is pending (off the board either way), the
    second keeps a correct headline number and is judged by the character
    clause. Collapsing them into one "year-ago hole" number would hide which
    ~105 names the repair actually releases.
    """
    from sepa import buyable_verdict as BV
    from sepa import canslim as CS
    from sepa import sales as SL
    from sepa.bonde import _cleared_floor

    out = {"mismatched_before": 0, "retier_after": {}, "headline_hole": 0,
           "prior_hole": 0,
           "placement_after": {"tiered": 0, "rejected_character": 0,
                               "out_pending": 0, "out_floor": 0},
           "still_held_out": 0, "unverifiable": 0, "duplicate_periods": 0,
           "reordered": 0, "symbols_headline_hole": [],
           "symbols_prior_hole": []}

    for d in docs:
        sym = str(d.get("symbol") or "").upper()
        raw = _periods(d)
        if not Q.yoy_pairs_verifiable(raw):
            out["unverifiable"] += 1
            continue
        if not Q.yoy_pairs_ok(raw):
            out["mismatched_before"] += 1

        a = Q.align_series(raw,
                           rev_q_series=_series(d, "rev_q_series"),
                           eps_q_series=_series(d, "eps_q_series"))
        if a["duplicate_periods"]:
            out["duplicate_periods"] += 1
        if a["reordered"]:
            out["reordered"] += 1
        periods = a["q_period_series"]

        if Q.headline_hole(periods):
            out["headline_hole"] += 1
            out["symbols_headline_hole"].append(sym)
        if Q.prior_hole(periods):
            out["prior_hole"] += 1
            out["symbols_prior_hole"].append(sym)

        q_eps = Q.yoy_pct(a["eps_q_series"])
        sales_new = SL.compute(CS._head8(a["rev_q_series"]), q_eps)
        tier = str(sales_new.get("tier") or "unknown")
        out["retier_after"][tier] = out["retier_after"].get(tier, 0) + 1

        pillar = BV._bonde_pillar({"fundamentals": {"sales": sales_new}})
        if pillar.get("pending"):
            out["placement_after"]["out_pending"] += 1
        elif pillar.get("passed"):
            out["placement_after"]["tiered"] += 1
        elif _cleared_floor(pillar):
            out["placement_after"]["rejected_character"] += 1
        else:
            out["placement_after"]["out_floor"] += 1

        # A row that is STILL refused after the repair and is not pending —
        # expected 0: a headline hole is pending, not held out.
        if Q.period_ok(periods) is False and not pillar.get("pending"):
            out["still_held_out"] += 1

    out["symbols_headline_hole"] = sorted(out["symbols_headline_hole"])
    out["symbols_prior_hole"] = sorted(out["symbols_prior_hole"])
    return out


def cross_source_asymmetry(scan_docs, research_docs) -> dict:
    """THE RESIDUAL WAY THE TWO BOARDS CAN STILL DISAGREE.

    Both boards now apply the identical guard, but they apply it to DIFFERENT
    COPIES of the series: 📈 Bonde reads the latest scan row, 🚀 growth reads
    the research cache. A symbol keyed in one copy and unkeyed in the other is
    checked on one board and accept-by-defaulted on the other — so it can be
    tiered here and refused there off what is nominally the same quarter.

    Counted both directions, by the tier the row would carry, symbols listed.
    """
    s_keyed = {}
    for d in scan_docs:
        sym = str(d.get("symbol") or "").upper()
        if sym:
            s_keyed[sym] = (Q.yoy_pairs_verifiable(_periods(d)), _tier(d))
    r_keyed = {}
    for d in research_docs:
        sym = str(d.get("symbol") or "").upper()
        if sym:
            r_keyed[sym] = (Q.yoy_pairs_verifiable(_periods(d)), _tier(d))

    out = {"research_only_keyed": {"total": 0, "by_tier": {}, "symbols": []},
           "scan_only_keyed": {"total": 0, "by_tier": {}, "symbols": []},
           "overlap": 0}
    for sym, (s_ok, s_tier) in s_keyed.items():
        if sym not in r_keyed:
            continue
        out["overlap"] += 1
        r_ok, r_tier = r_keyed[sym]
        if r_ok and not s_ok:
            b = out["research_only_keyed"]
        elif s_ok and not r_ok:
            b = out["scan_only_keyed"]
        else:
            continue
        t = str(s_tier or r_tier or "unknown")
        b["total"] += 1
        b["by_tier"][t] = b["by_tier"].get(t, 0) + 1
        b["symbols"].append(sym)
    for k in ("research_only_keyed", "scan_only_keyed"):
        out[k]["symbols"] = sorted(out[k]["symbols"])
    return out


def overlap_diffs(scan_docs, research_docs) -> dict:
    """Do the two copies disagree about the latest quarter, the growth number
    or the tier? (Measured 2026-09-20: 0 / 0 / 2, both 'pending vs computed'.)"""
    r = {str(d.get("symbol") or "").upper(): d for d in research_docs}
    n = per = yoy = tier = 0
    tier_syms = []
    for d in scan_docs:
        sym = str(d.get("symbol") or "").upper()
        if sym not in r:
            continue
        n += 1
        a, b = d, r[sym]
        pa, pb = _periods(a) or [], _periods(b) or []
        if (pa[:1] or [None]) != (pb[:1] or [None]):
            per += 1
        fa = (a.get("fundamentals") or {}).get("sales") or {}
        fb = (b.get("fundamentals") or {}).get("sales") or {}
        if fa.get("growth_yoy_pct") != fb.get("growth_yoy_pct"):
            yoy += 1
        if fa.get("tier") != fb.get("tier"):
            tier += 1
            tier_syms.append(sym)
    return {"overlap": n, "period_differs": per, "growth_differs": yoy,
            "tier_differs": tier, "tier_diff_symbols": sorted(tier_syms)[:40]}


# ---------------------------------------------------------------------------
# the live read
# ---------------------------------------------------------------------------
def _scan_docs():
    from sepa import scanner
    scan = scanner.load_latest() or {}
    return scan.get("all_results") or []


def _research_docs():
    from sepa import research
    coll = research._get_cache()
    if coll is None:
        return []
    # rev/eps series are needed by `repair_outcome` — it re-tiers each row
    # through the real `sales.compute` rather than trusting the stored tier.
    proj = {"symbol": 1, "fundamentals.sales": 1,
            "fundamentals.q_period_series": 1, "fundamentals._source": 1,
            "fundamentals.rev_q_series": 1, "fundamentals.eps_q_series": 1}
    return list(coll.find({}, proj))


def _bonde_passers(scan_docs):
    from sepa import buyable_verdict as BV
    return [d for d in scan_docs if BV._bonde_pillar(d).get("passed") is True]


def _surprise_units(symbols=("NVDA", "IOVA", "DELL")) -> dict:
    """Both yfinance paths on the same names — the 100x defect and its fix.

    Reads live; returns the error rather than failing the audit when yfinance
    is unreachable from the container.
    """
    out = {}
    for sym in symbols:
        row = {"catalyst_path": None, "earnings_watch_path": None}
        try:
            from sepa import catalyst as C
            row["catalyst_path"] = (C._fetch_yfinance_extras(sym) or {}).get(
                "last_surprise_pct")
        except Exception as exc:                               # noqa: BLE001
            row["catalyst_path"] = f"error: {exc}"
        try:
            from sepa import earnings_watch as EW
            nxt = EW._fetch_next(sym) or {}
            last = (nxt.get("last_report") or {})
            row["earnings_watch_path"] = last.get("surprise_pct")
        except Exception as exc:                               # noqa: BLE001
            row["earnings_watch_path"] = f"error: {exc}"
        out[sym] = row
    return out


def _ipo_recent_count() -> dict:
    try:
        from portfolio.store import _get_db
        db = _get_db()
        if db is None:
            return {"error": "no mongo"}
        import time as _t
        cut = _t.time() - 2 * 365 * 86400
        n = db["ipo_dates"].count_documents({})
        recent = 0
        for d in db["ipo_dates"].find({}, {"ipo": 1}):
            v = d.get("ipo")
            try:
                import datetime as _dt
                ts = _dt.datetime.fromisoformat(str(v)).timestamp()
            except Exception:                                  # noqa: BLE001
                continue
            if ts >= cut:
                recent += 1
        return {"docs": n, "claim_le_2y": recent}
    except Exception as exc:                                   # noqa: BLE001
        return {"error": str(exc)}


def audit() -> dict:
    scan = _scan_docs()
    research = _research_docs()
    passers = _bonde_passers(scan)
    mism = mismatch_by_tier(passers)

    growth_expl = set()
    bonde_expl = set()
    try:
        from growth import tracker as T
        for row in (T.board() or {}).get("rows", []) or []:
            growth_expl.add(str(row.get("symbol") or "").upper())
    except Exception as exc:                                   # noqa: BLE001
        growth_expl = {f"error: {exc}"}
    for d in passers:
        if _tier(d) == "explosive":
            bonde_expl.add(str(d.get("symbol") or "").upper())

    return {
        "scan_rows": len(scan),
        "research_docs": len(research),
        "bonde_passers": len(passers),
        "pair_mismatch": mism,
        "mismatch_pct": round(100.0 * mism["total"] / len(passers), 1) if passers else None,
        "q4_shaped": q4_shaped_share(passers),
        "repair": repair_outcome(research),
        "character_pairs_extra": character_pairs_mismatch(passers),
        "unverifiable": {"scan": unverifiable_count(scan),
                         "research": unverifiable_count(research)},
        "cross_source_asymmetry": cross_source_asymmetry(scan, research),
        "overlap": overlap_diffs(scan, research),
        "bonde_explosive": len(bonde_expl),
        "growth_board": len(growth_expl) if isinstance(growth_expl, set) else None,
        "shared_explosive": sorted(bonde_expl & growth_expl) if isinstance(growth_expl, set) else None,
        "surprise_units": _surprise_units(),
        "ipo_dates": _ipo_recent_count(),
    }


def _main(argv=None) -> int:
    print(json.dumps(audit(), indent=2, default=str))
    return 0


if __name__ == "__main__":                                  # pragma: no cover
    sys.exit(_main())
