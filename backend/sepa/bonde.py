"""Bonde board — Pradeep Bonde's (Stockbee) own screen, as its own tab.

Ajay 2026-09-13: *"create me a Bonde tab. we already have his rules in the
analysis tab on individual ticker but I wanna see explicitly new ones getting
added in this tab … but I wanna see his stocks."*

NOTHING HERE RE-DERIVES BONDE. Every rule is called from the module that
already implements it and is already cited:

  `sepa/sales.py`              his 5% / 25% / 100% sales tiers
  `sepa/buyable_verdict.py`    `_bonde_pillar` — the PASS rule
  `setups/episodic_pivot.py`   the Episodic Pivot, his signature setup
  docs/sepa/sales_confidence_methodology.md — the sourcing, including which
  widely-attributed figures FAILED verification and are deliberately not used.

WHY THE BOARD IS THE INTERSECTION, AND NOT EITHER LEG
─────────────────────────────────────────────────────
Measured on the live scan 2026-09-13, which is what decided this board's shape:

  * His SALES gate alone passes **1,051 of 2,076 names (50.6%)**. Half the
    market is a description of the market, not a selection. Tiers underneath:
    explosive 72, strong 317, steady 691, weak 227, declining 265, unknown 504.
  * The EPISODIC PIVOT alone has 50 active setups. Of the 32 that are in the
    scan, **ELEVEN have DECLINING sales** — precisely what his own screen throws
    away. The EP is a tape pattern; on its own it is catalyst-agnostic and says
    nothing about the business.
  * **Together: 12 names.** That is a board.

So the sales screen is the UNIVERSE and the Episodic Pivot is the ENTRY, which
is how Bonde describes his own process — and either leg alone produces a list he
would not trade.

WHAT THE THRESHOLDS ARE AND ARE NOT
───────────────────────────────────
The sales numbers (5 / 25 / 100) are Bonde's own, documented in his writing and
cited in the methodology doc. The EP's numbers are NOT his: 8% gap on 5x volume
are this app's OWNER settings, chosen in `setups/episodic_pivot.py` to be
stricter than its PEG cousin because it has no earnings-calendar filter. The
board says so rather than implying he published them.

NOTHING HERE GATES, ALERTS OR BUYS.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

log = logging.getLogger("sepa.bonde")

# Arrivals ledger — his explicit ask, "I wanna see explicitly new ones getting
# added". Its own collection so the Bonde board's arrivals cannot be confused
# with the Explosive Growth board's.
SEEN_COLL = "bonde_seen"
NEW_DAYS = 30

SECTION_PIVOT = "pivot"
SECTION_EXPLOSIVE = "explosive"
SECTION_STRONG = "strong"
SECTION_STEADY = "steady"
SECTIONS = (SECTION_PIVOT, SECTION_EXPLOSIVE, SECTION_STRONG, SECTION_STEADY)

# `steady` is 691 names on the live scan. It is CAPPED rather than dropped,
# because his 5% floor is genuinely his floor and hiding the tier would
# misrepresent his screen — but a 691-row section is a scroll, not a read.
SECTION_CAP = {SECTION_PIVOT: 60, SECTION_EXPLOSIVE: 60,
               SECTION_STRONG: 60, SECTION_STEADY: 40}

# An EP older than this is history, not a setup. `setups/episodic_pivot.py`
# expires its own rows at 72h; this is the display bound for a row that is
# still technically alive.
MAX_PIVOT_AGE_H = 72


def _f(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (f != f or f in (float("inf"), float("-inf"))) else f


def regime_state() -> dict:
    """Why the ⚡ Pivots section may be empty — and it usually is right now.

    FOUND WHILE BUILDING THIS BOARD, 2026-09-13, and it is not a bug: EVERY
    setup kind in the app is stale. Newest episodic_pivot 413h old, peg 461h,
    bull_flag 413h, orb 326h — zero fresh rows across all 18 kinds.

    The cause is Ajay's own rule. `setups/universe.is_bull_regime()` gates every
    setup scanner, he explicitly chose to sit out bear markets, and the gate
    itself was BROKEN until 2026-08-31 — it imported a function that never
    existed, the bare except swallowed the ImportError, and it returned None
    ("cannot tell, go ahead") on every call. So the sit-out rule had never once
    fired until that fix, and the fleet went quiet almost immediately after.

    A board whose headline section is empty for a structural reason MUST say so.
    Rendering an empty ⚡ Pivots with no explanation would read as a broken tab,
    and the honest answer — "his entry setup is switched off because the market
    is in correction" — is itself the useful information.
    """
    out = {"is_bull": None, "label": None, "score": None, "scanners_paused": False}
    try:
        from setups import universe as SU
        out["is_bull"] = SU.is_bull_regime()
    except Exception as exc:                                   # noqa: BLE001
        log.debug("bonde: regime gate unavailable: %s", exc)
    try:
        from sepa.market_regime import regime
        r = regime() or {}
        out["label"] = r.get("label")
        out["score"] = _f(r.get("score"))
    except Exception as exc:                                   # noqa: BLE001
        log.debug("bonde: regime label unavailable: %s", exc)
    out["scanners_paused"] = out["is_bull"] is False
    return out


def _pivots() -> dict:
    """{SYM: freshest active Episodic Pivot} — DEDUPED.

    The stored setups are NOT unique per symbol: a live read on 2026-09-13
    returned MRNA five times, PAYS three times and ANF twice, because each
    scanner pass upserts a new row. Rendering that raw would put one name on
    the board five times and make a 12-name list look like 30.
    """
    try:
        from setups import store
        rows = store.get_setups(kind="episodic_pivot", limit=400,
                                only_pending=True) or []
    except Exception as exc:                                   # noqa: BLE001
        log.warning("bonde: episodic pivots unavailable: %s", exc)
        return {}
    now = time.time()
    best: dict = {}
    for r in rows:
        sym = str(r.get("symbol") or "").upper()
        if not sym:
            continue
        gen = _f(r.get("generated_at")) or 0.0
        if gen and (now - gen) > MAX_PIVOT_AGE_H * 3600:
            continue
        prev = best.get(sym)
        if prev is None or gen > (_f(prev.get("generated_at")) or 0.0):
            best[sym] = r
    return best


# Year-ago quarterly revenue below this is a base so small the percentage off it
# is a ratio artifact rather than a growth rate. Same constant `sepa/qoq.py`
# already uses for the identical job on the sequential board, imported rather
# than retyped so the two boards cannot drift.
#
# It is a DISPLAY FLAG, not a gate: a flagged name still shows, still carries its
# tier, and still prints its dollars. Hiding it would misrepresent his screen;
# ranking on it would put arithmetic at the top of his board.
# A company whose quarterly revenue was under this a year ago was, for practical
# purposes, pre-revenue — and a percentage measured off it is a ratio, not a
# growth rate. QUBT reads +9,000% off $61,000 and FCUV +1,811% off $35,330.
#
# THIS IS THIS APP'S OWNER SETTING, NOT A BONDE NUMBER, and it is stated on the
# board as such. `sepa/qoq.py` already solves the identical problem on the
# sequential board, but its MIN_REV_BASE of $1,000 is a divide-by-zero guard
# rather than a materiality test and would pass every name above.
#
# It is a RANKING boundary, never a filter: a name below it still appears in its
# tier, still prints its percentage and its actual dollars, and simply does not
# outrank a company with a real base. Hiding it would misrepresent his screen.
MIN_MATERIAL_BASE_REV = 1_000_000.0


def _rev_base(scan_row: dict) -> dict:
    """Latest and year-ago quarterly revenue, and whether a % off it means anything.

    THE DEFECT THIS EXISTS TO STOP, measured on the live board 2026-09-13.
    Ranked on the raw percentage, the top of the "explosive" tier was almost
    entirely arithmetic:

        DBRG  +15,961%   year-ago revenue was MINUS $3,207,000
        APLD     +877%   year-ago revenue was MINUS $33,300,000
        QUBT   +9,000%   year-ago revenue was $61,000
        FCUV   +1,811%   year-ago revenue was $35,330

    `sepa/sales.py::_yoy` divides by `abs(base)`, so a NEGATIVE base comes back
    as large POSITIVE growth — a sign flip, not a ramp. Meanwhile the genuinely
    explosive businesses underneath (PTGX $5.5M -> $213M, LQDA $8.8M -> $171M,
    ONDS $6.3M -> $83.8M) ranked BELOW the artifacts.

    `sales.py` itself is NOT changed: it is book-cited, locked by contract tests
    and read by the falling-knife gate on several other boards, so moving its
    arithmetic would move `sales.score` app-wide. The board handles its own
    ranking instead.
    """
    f = scan_row.get("fundamentals") or {}
    ser = (f.get("rev_q_series") or []) if isinstance(f, dict) else []
    latest = _f(ser[0]) if len(ser) > 0 else None
    base = _f(ser[4]) if len(ser) > 4 else None
    if base is None or latest is None:
        state = "unknown"
    elif base <= 0:
        state = "non_positive"      # arithmetic, not a threshold
    elif base < MIN_MATERIAL_BASE_REV:
        state = "too_small"
    else:
        state = "ok"
    return {"latest_rev": latest, "base_rev": base, "base_state": state,
            "rev_added": (latest - base) if (latest is not None and base is not None
                                             and base > 0) else None}


def _row(scan_row: dict, pillar: dict, pivot: Optional[dict]) -> dict:
    """One board row. Every number comes from a module that already owns it."""
    sym = str(scan_row.get("symbol") or "").upper()
    fundamentals = scan_row.get("fundamentals") or {}
    sales = (fundamentals.get("sales") or {}) if isinstance(fundamentals, dict) else {}
    out = {
        "symbol": sym,
        "name": scan_row.get("name"),
        "last_close": _f(scan_row.get("last_close")),
        # Bonde's sales read, straight from sepa/sales.py via the pillar.
        "tier": pillar.get("tier"),
        "sales_score": pillar.get("score"),
        "growth_yoy_pct": pillar.get("growth_yoy_pct"),
        "prior_yoy_pct": sales.get("prior_yoy_pct"),
        "accelerating": pillar.get("accelerating"),
        "consecutive_growth_q": pillar.get("consecutive_growth_q"),
        "sales_led": pillar.get("sales_led"),
        "bonde_reason": pillar.get("reason"),
        "pivot": None,
    }
    out.update(_rev_base(scan_row))
    if pivot:
        meta = pivot.get("meta") or {}
        gen = _f(pivot.get("generated_at"))
        out["pivot"] = {
            "gap_pct": _f(meta.get("gap_pct")),
            "vol_mult": _f(meta.get("vol_mult")),
            "catalyst_type": meta.get("catalyst_type"),
            "trigger": _f(pivot.get("trigger")),
            "stop": _f(pivot.get("stop")),
            "target": _f(pivot.get("target")),
            "rr": _f(pivot.get("rr")),
            "date_et": pivot.get("date_et"),
            "hours_ago": round((time.time() - gen) / 3600.0, 1) if gen else None,
        }
    return out


def _pivot_key(r: dict):
    """Freshest pivot first, then the bigger gap. An ORDER, not a ranking —
    nothing here has been measured against a placebo."""
    p = r.get("pivot") or {}
    return (p.get("hours_ago") if p.get("hours_ago") is not None else 1e6,
            -(p.get("gap_pct") or 0.0), r["symbol"])


def _sales_key(r: dict):
    """Order within a tier. NOT the raw percentage — see `_rev_base`.

    Every name in a tier has already cleared that tier's threshold, so the
    order inside it is this board's choice, and ranking on the raw YoY put
    DBRG's sign flip (+15,961% off a NEGATIVE base) and QUBT's $61,000 base
    above PTGX going $5.5M -> $213M.

    So: names whose base can carry a percentage come FIRST as a block, then
    `sales.compute`'s 0-100 score — which saturates at 100, so an artifact
    cannot dominate it — then the actual DOLLARS of revenue added, which no
    tiny base can inflate. The percentage is still printed on every row; it
    just no longer decides the order.
    """
    return (r.get("base_state") != "ok",
            -(r.get("growth_yoy_pct") or -1e18),
            -(r.get("rev_added") or -1e18),
            r["symbol"])


def board(db=None, new_days: int = NEW_DAYS) -> dict:
    """The Bonde board: his Episodic Pivots first, then his sales tiers.

    Reads the latest scan — never scans on the request path.
    """
    from sepa import scanner, buyable_verdict as BV
    from sepa import first_seen as FS

    scan = scanner.load_latest() or {}
    rows = scan.get("all_results") or []
    pivots = _pivots()

    sections: dict = {k: [] for k in SECTIONS}
    n_pass = 0
    for r in rows:
        sym = str(r.get("symbol") or "").upper()
        if not sym:
            continue
        pillar = BV._bonde_pillar(r)
        if pillar.get("passed") is not True:
            # Pending (not enriched) and explicit fails are both OUT. "We do not
            # know yet" must never render on a board that claims his screen.
            continue
        n_pass += 1
        row = _row(r, pillar, pivots.get(sym))
        if row["pivot"] is not None:
            sections[SECTION_PIVOT].append(row)
        tier = row.get("tier")
        if tier in (SECTION_EXPLOSIVE, SECTION_STRONG, SECTION_STEADY):
            sections[tier].append(row)

    sections[SECTION_PIVOT].sort(key=_pivot_key)
    for k in (SECTION_EXPLOSIVE, SECTION_STRONG, SECTION_STEADY):
        sections[k].sort(key=_sales_key)

    counts = {k: len(v) for k, v in sections.items()}
    for k in SECTIONS:
        sections[k] = sections[k][:SECTION_CAP[k]]

    # ── arrivals: his explicit ask ─────────────────────────────────────────
    # Recorded over every name that PASSES, not only the ones that survived the
    # per-section cap: a name that arrives into a capped tier has still arrived,
    # and recording only the visible ones would reset its "new" clock every time
    # the cap pushed it off and back on.
    shown = {r["symbol"] for v in sections.values() for r in v}
    try:
        all_pass = {str(r.get("symbol") or "").upper() for r in rows
                    if BV._bonde_pillar(r).get("passed") is True}
        FS.record(SEEN_COLL, all_pass, db=db)
        new = FS.newly_found(SEEN_COLL, days=new_days, db=db)
        seen_at = FS.first_seen_map(SEEN_COLL, sorted(shown), db=db)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("bonde: arrivals unavailable: %s", exc)
        new, seen_at = set(), {}

    for v in sections.values():
        for r in v:
            r["is_new"] = r["symbol"] in new
            r["first_seen"] = seen_at.get(r["symbol"])

    # The CPA columns, same cache the other two boards read. A cold entry
    # leaves the row untouched and the cell renders an em-dash.
    try:
        from sepa import board_metrics as BM
        BM.attach([r for v in sections.values() for r in v], db=db)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("bonde: board_metrics attach failed: %s", exc)

    reg = regime_state()
    return {
        "sections": sections,
        "counts": counts,
        "regime": reg,
        "caps": dict(SECTION_CAP),
        "n_pass": n_pass,
        "n_scanned": len(rows),
        "n_new": len(new),
        "new_days": new_days,
        "scan_ts": scan.get("finished_at") or scan.get("started_at"),
        "note": note(n_pass, len(rows), counts, reg),
    }


def note(n_pass: int, n_scanned: int, counts: dict,
         reg: Optional[dict] = None) -> str:
    """The sentence under the board.

    It leads with the fire rate because that is the fact that shaped the board:
    his sales gate alone describes half the market, and a reader who does not
    know that will read the tier sections as a selection.
    """
    pct = round(100.0 * n_pass / n_scanned, 1) if n_scanned else None
    return (
        "Pradeep Bonde's own screen, as he describes it: the SALES growth is the "
        "universe, the EPISODIC PIVOT is the entry. ⚡ Pivots are shown first "
        "because that intersection is the only part of this that is a selection "
        "— measured on this scan, his sales gate alone passes %s of %s names "
        "(%s%%), and the Episodic Pivot alone carries names with DECLINING "
        "sales, which is exactly what his screen throws away. Together they are "
        "%d. The sales tiers below are his documented 5%% floor / 25%% preferred "
        "/ 100%% explosive hierarchy and are a WATCHLIST, ordered by top-line "
        "growth — not a ranking anything measured. The 5/25/100 numbers are "
        "Bonde's own (see docs/sepa/sales_confidence_methodology.md, which also "
        "lists the figures widely attributed to him that failed verification and "
        "are deliberately not used here); the Pivot's 8%% gap on 5x volume are "
        "THIS APP'S owner settings, not numbers he published. Nothing on this "
        "tab gates a scan, fires an alert or buys in any lane."
        % (f"{n_pass:,}", f"{n_scanned:,}", pct, counts.get(SECTION_PIVOT, 0))
    ) + pivot_pause_note(reg)


def pivot_pause_note(reg: Optional[dict]) -> str:
    """The sentence that keeps an empty ⚡ Pivots section from reading broken."""
    if not reg or not reg.get("scanners_paused"):
        return ""
    label = str(reg.get("label") or "not bullish").replace("_", " ")
    return (
        " ⚡ PIVOTS ARE PAUSED RIGHT NOW, and that is your own rule rather than "
        "a fault: the regime gate reads \u201c%s\u201d, and you chose to sit "
        "out bear markets, so every setup scanner in the app short-circuits and "
        "writes nothing. It bites harder than it looks — EVERY setup kind is "
        "currently stale, not just this one, because that gate was itself broken "
        "until 2026-08-31 (it imported a function that never existed and always "
        "answered \u201ccannot tell, go ahead\u201d) and the fleet went quiet as "
        "soon as it started working. The sales tiers below are unaffected: they "
        "read the scan, not the setup scanners." % label
    )


def symbols(db=None) -> list:
    """Every symbol the board shows — what the metrics cron warms."""
    try:
        b = board(db=db)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("bonde: symbols unavailable: %s", exc)
        return []
    return sorted({r["symbol"] for v in (b.get("sections") or {}).values()
                   for r in v})


def _main(argv=None) -> int:
    """`python -m sepa.bonde show` — counts, from the container."""
    b = board()
    print("bonde: %s of %s pass (%s new in %dd)"
          % (b["n_pass"], b["n_scanned"], b["n_new"], b["new_days"]))
    print("counts:", b["counts"])
    for k in SECTIONS:
        rows = (b["sections"] or {}).get(k) or []
        if rows:
            print("  %-10s %s" % (k, ", ".join(
                "%s%s" % (r["symbol"], "✨" if r.get("is_new") else "")
                for r in rows[:12])))
    return 0


if __name__ == "__main__":                                  # pragma: no cover
    raise SystemExit(_main())
