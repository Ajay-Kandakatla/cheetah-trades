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

MEASURED 2026-09-13, AND THE BOARD'S OWN THESIS IS INVERTED
──────────────────────────────────────────────────────────
This board shipped on the reasoning that his SALES screen is the universe and
the EPISODIC PIVOT is the entry, so the intersection is the selection. That
reasoning was then measured twice — a first pass, then an independent audit
with its own code, its own fetch and roughly twice the panel — and the
intersection is the WORST cell either pass found.

  780 Episodic Pivots reconstructed bar by bar from CLOSED bars,
  2024-09-13 → 2026-09-11 (the rule validated 62/63 against the stored
  setup docs, and 0 of 780 events used a quarter filed after their bar):

    EP + his sales gate PASS   376 events   21d median −3.22%   win 39.8%
    date-matched non-EP names  1,376 draws  21d median −0.11%   win 49.6%
    ────────────────────────────────────────────────────────────────────
    lift                                    −3.11pp   95% CI −5.28 … −1.16
                                            (−5.19 … −1.13 date-clustered)

  His sales gate ON ITS OWN separated nothing at any horizon: −0.40pp,
  CI −1.40 … +0.61. It passes 48.2% of EP events and 46.0% of matched
  non-EP draws — it carries no information about the pivot.

The inversion holds under date clustering, under a ≥$1M liquidity cut, under
entry at the next open (worse: −4.76pp), and in all four point-in-time
fundamentals variants. It is NOT a licence to short: cell A's 21d MEAN is
−2.18% with a CI that includes zero. The finding is "these bleed at the median
and win less than half the time".

WHAT DID **NOT** REPRODUCE, AND IS THEREFORE NOT SAID ANYWHERE
──────────────────────────────────────────────────────────────
The first pass claimed EP+PASS also loses to EP+FAIL (−3.36pp). The audit puts
that at −2.42pp [−4.88, +0.30], spanning zero in every variant. STRUCK.
It also claimed both character clauses measure backwards; only the consistency
clause does. And its "coverage is 46%" limitation was its own no-retry fetcher
losing half its requests, not a data limit.

THE ONE THING THAT SURVIVED EVERY ATTACK, AND WHY THERE IS A 🔎 SECTION
──────────────────────────────────────────────────────────────────────
Among names that clear his 5% floor, the character clause — `accelerating` OR
≥2 consecutive growth quarters — is what turns a floor-clearer into a PASS.
Requiring it measures NEGATIVE: the floor-clearing names the gate REJECTS won
56.8% of the next 21 sessions against 51.2% for the names it accepts (PASS
minus REJECT −5.64pp, CI −7.52 … −3.91; −7.66pp at 63 days). Clause by clause
it is the CONSISTENCY half: ≥2 consecutive quarters costs 3.3pp of win rate at
21d (CI −4.7 … −1.8). `accelerating` is a NULL, not a negative.

So the gate is not edited — it is Bonde's, and this board exists to show HIS
screen — but the cohort it throws away is shown beside it, labelled, because a
board that hides its best-measured cell is not a study board.

Caveat that belongs next to that number: the rejected-cell result does not
survive date clustering at 21 days (it does at 63), and the variant that feeds
production's raw list position shrinks it to 1,030 bars with CIs spanning zero.

THE TIERS ARE A WATCHLIST, AND THE AUDIT IS STRICTER ABOUT THAT THAN THE FIRST
PASS WAS
────────────────────────────────────────────────────────────────────────────
Over 45,425 symbol-bars in 24 monthly cross-sections, the ≥100% and ≥25% tiers
beat the scored universe by a MEDIAN of +0.45pp and +0.37pp at 21 days — both
CIs include zero — with win rates level with the market (+0.96pp and +0.68pp,
CIs include zero). The mean lift that does appear is entirely the right tail:
strong's +5.27pp falls to +0.26pp when the top 5% of returns are dropped, and
every date-clustered interval spans zero. Names passing the full gate are
statistically indistinguishable from any stock (+0.48pp, CI −0.47 … +2.20).

Therefore: no tier number prints here without its MEDIAN, its WIN RATE and its
placebo beside the mean, and the board does NOT sort on `sales.compute`'s
0-100 score — whatever ranking value it has sits inside a tail the audit could
not separate from noise.

WHAT THE THRESHOLDS ARE AND ARE NOT
───────────────────────────────────
The sales numbers (5 / 25 / 100) are Bonde's own, documented in his writing and
cited in the methodology doc. The EP's numbers are NOT his: 8% gap on 5x volume
are this app's OWNER settings, chosen in `setups/episodic_pivot.py` to be
stricter than its PEG cousin because it has no earnings-calendar filter. The
board says so rather than implying he published them.

Scripts, re-runnable verbatim: `backend/scripts/bonde_audit/` (README.md there
carries the run recipe, the struck claims and the limits — survivorship,
24 cross-sections in ONE bull regime, and the derived-Q4 availability date).

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

# ── the measurement, in exactly one place ───────────────────────────────────
# Every surface that quotes a Bonde number reads it from here: the note under
# the board, the tab blurb contract test, and the doc. A number typed twice is
# a number that drifts, and this one is a negative result on a board he reads.
# Source: backend/scripts/bonde_audit/ (lane1.py, lane1b.py, lane2.py,
# attack.py, sens.py), run 2026-09-13 inside the api container.
MEASURED = {
    "run_date": "2026-09-13",
    "window": "2024-09-13 → 2026-09-11",
    "ep_events": 780,
    "cell_a_n": 376,
    "cell_a_med_21d": -3.22,
    "cell_a_win_21d": 39.8,
    "placebo_med_21d": -0.11,
    "placebo_win_21d": 49.6,
    "lift_21d": -3.11,
    "lift_ci": (-5.28, -1.16),
    "lift_ci_date": (-5.19, -1.13),
    "sales_alone_lift": -0.40,
    "sales_alone_ci": (-1.40, 0.61),
    "expectancy_pct": -0.92,
    "expectancy_ci": (-2.14, 0.27),
    # The cell the gate REJECTS — the one result that survived every attack.
    "reject_win_21d": 56.8,
    "pass_win_21d": 51.2,
    "reject_minus_pass_21d": 5.64,
    "reject_ci_21d": (3.91, 7.52),
    "consec_win_cost_21d": -3.31,
    "consec_ci_21d": (-4.68, -1.83),
    # The tiers, as MEDIAN lifts with their CIs — never the mean alone.
    "tier_explosive_med": 0.45,
    "tier_explosive_ci": (-0.31, 1.36),
    "tier_strong_med": 0.37,
    "tier_strong_ci": (-0.16, 0.78),
    "tier_strong_mean_trimmed": 0.26,
    "panel_bars": 45425,
    "panel_dates": 24,
    "scripts": "backend/scripts/bonde_audit/",
}

SECTION_PIVOT = "pivot"
SECTION_EXPLOSIVE = "explosive"
SECTION_STRONG = "strong"
SECTION_STEADY = "steady"
# Not on his screen — the cohort his character clause THROWS AWAY, which is the
# only cell in either measurement pass that beat the market on win rate. Shown
# last, labelled as excluded, never mixed into the tiers above it.
SECTION_REJECTED = "rejected"
SECTIONS = (SECTION_PIVOT, SECTION_EXPLOSIVE, SECTION_STRONG, SECTION_STEADY,
            SECTION_REJECTED)

# `steady` is 691 names on the live scan. It is CAPPED rather than dropped,
# because his 5% floor is genuinely his floor and hiding the tier would
# misrepresent his screen — but a 691-row section is a scroll, not a read.
SECTION_CAP = {SECTION_PIVOT: 60, SECTION_EXPLOSIVE: 60,
               SECTION_STRONG: 60, SECTION_STEADY: 40,
               SECTION_REJECTED: 40}

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


def _cleared_floor(pillar: dict) -> bool:
    """Did this name clear Bonde's 5% sales floor and fail only on character?

    Read off the pillar's own fields rather than re-deriving the comparison —
    `buyable_verdict._bonde_pillar` owns that rule and its rounding seam.
    """
    from sepa.sales import SALES_FLOOR_PCT
    g = _f(pillar.get("growth_yoy_pct"))
    return g is not None and round(g) >= SALES_FLOOR_PCT


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

    So: names whose base can carry a percentage come FIRST as a block — every
    sign flip and every $61,000 base lands below every real business — then the
    growth percentage within that block, then the actual DOLLARS of revenue
    added, which no tiny base can inflate.

    NOT `sales.compute`'s 0-100 score, deliberately. The audit measured ranking
    by that score and could not separate whatever value it has from the right
    tail of the return distribution (see MEASURED and
    backend/scripts/bonde_audit/attack.py), so it does not decide any order a
    reader might mistake for a ranking.
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
    n_rejected = 0
    for r in rows:
        sym = str(r.get("symbol") or "").upper()
        if not sym:
            continue
        pillar = BV._bonde_pillar(r)
        passed = pillar.get("passed")
        if passed is not True:
            # Pending (not enriched) is OUT — "we do not know yet" must never
            # render on a board that claims his screen.
            #
            # An explicit FAIL is out of his screen too, but one kind of fail
            # gets its own section rather than vanishing: a name that CLEARED
            # his 5% floor and was rejected only by the character clause. That
            # is the cohort the audit found beating the passers on win rate
            # (56.8% vs 51.2%), and it is the single result that survived date
            # clustering, the tail trim and all four fundamentals variants. It
            # is never mixed into the tiers, and the section says plainly that
            # these are NOT on his screen.
            if passed is False and _cleared_floor(pillar):
                n_rejected += 1
                sections[SECTION_REJECTED].append(
                    _row(r, pillar, pivots.get(sym)))
            continue
        n_pass += 1
        row = _row(r, pillar, pivots.get(sym))
        if row["pivot"] is not None:
            sections[SECTION_PIVOT].append(row)
        tier = row.get("tier")
        if tier in (SECTION_EXPLOSIVE, SECTION_STRONG, SECTION_STEADY):
            sections[tier].append(row)

    sections[SECTION_PIVOT].sort(key=_pivot_key)
    for k in (SECTION_EXPLOSIVE, SECTION_STRONG, SECTION_STEADY,
              SECTION_REJECTED):
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

    for k, v in sections.items():
        for r in v:
            r["is_new"] = (k != SECTION_REJECTED) and (r["symbol"] in new)
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
        "n_rejected": n_rejected,
        "n_scanned": len(rows),
        "n_new": len(new),
        "new_days": new_days,
        "scan_ts": scan.get("finished_at") or scan.get("started_at"),
        "note": note(n_pass, len(rows), counts, reg),
        # The verdict banner. Served, not retyped in the component: the numbers
        # have exactly one home (MEASURED) and the FE renders whatever it is
        # handed, so a re-run that moves a figure moves every surface at once.
        "measured": measured_verdict(),
    }


def _sgn(v, d: int = 2) -> str:
    """A signed number with a REAL minus sign (U+2212), for prose.

    Always signed, because every number that goes through here is a lift, a
    median or a confidence bound, and an unsigned "0.61" at the top of a CI
    reads as a magnitude rather than as the positive end of an interval that
    crosses zero — which is the whole point of printing it.

    Not a blanket `.replace("-", "−")` on the finished sentence — that eats the
    hyphen in "date-matched" and "non-EP" and produces a paragraph that looks
    like a typo in exactly the place a reader is checking a negative result.
    """
    return ("%s%%.%df" % ("+" if v >= 0 else "−", d)) % abs(v)


def measured_verdict() -> dict:
    """The verdict banner the tab leads with, built from MEASURED.

    Returned by the API so the component renders numbers it was handed rather
    than numbers someone typed into TSX. Keltner and AMD set this precedent on
    the same day for the same reason.
    """
    m = MEASURED
    return {
        "headline": "MEASURED %s AND THIS BOARD’S OWN THESIS IS INVERTED"
                    % m["run_date"],
        "body": (
            "This tab shipped on the idea that Bonde's sales screen is the "
            "universe and the Episodic Pivot is the entry, so the intersection "
            "is the selection. Measured on %d Episodic Pivots reconstructed "
            "from CLOSED bars %s, the %d that ALSO passed his sales gate "
            "returned a median %s%% over the next 21 sessions (win rate "
            "%.1f%%) against %s%% (%.1f%%) for date-matched non-EP names — a "
            "lift of %spp, 95%% CI %s to %s symbol-clustered and %s to "
            "%s date-clustered. His sales gate on its own separated nothing "
            "at any horizon (%spp, CI %s to %s). Expectancy on the "
            "setup's own bracket is %s%% (CI %s to %s), and the sales "
            "gate moves it by −0.06pp. THIS IS A STUDY BOARD, NOT A BUY LIST."
            % (m["ep_events"], m["window"], m["cell_a_n"],
               _sgn(m["cell_a_med_21d"]), m["cell_a_win_21d"],
               _sgn(m["placebo_med_21d"]), m["placebo_win_21d"],
               _sgn(m["lift_21d"]), _sgn(m["lift_ci"][0]),
               _sgn(m["lift_ci"][1]), _sgn(m["lift_ci_date"][0]),
               _sgn(m["lift_ci_date"][1]), _sgn(m["sales_alone_lift"]),
               _sgn(m["sales_alone_ci"][0]), _sgn(m["sales_alone_ci"][1]),
               _sgn(m["expectancy_pct"]), _sgn(m["expectancy_ci"][0]),
               _sgn(m["expectancy_ci"][1]))
        ),
        "not_a_short": (
            "It does not read the other way either: that cohort's 21-day MEAN "
            "is −2.18% with a CI that includes zero. The finding is “these "
            "bleed at the median and win less than half the time”, not “these "
            "reliably fall”."
        ),
        "tiers": (
            "The tiers below do not separate on the typical name. Over %s "
            "symbol-bars in %d monthly cross-sections, the ≥100%% and ≥25%% "
            "tiers beat the scored universe by a MEDIAN of +%.2fpp and "
            "+%.2fpp over 21 days — both CIs include zero — with win rates "
            "level with the market. The average lift that does show up is the "
            "right tail: it falls to +%.2fpp once the top 5%% of returns are "
            "dropped, and every date-clustered interval spans zero. Names "
            "passing the full gate are statistically indistinguishable from "
            "any stock (+0.48pp, CI −0.47 to +2.20)."
            % (f"{m['panel_bars']:,}", m["panel_dates"],
               m["tier_explosive_med"], m["tier_strong_med"],
               m["tier_strong_mean_trimmed"])
        ),
        "rejected": (
            "The one result that survived every attack is about the cohort his "
            "gate THROWS AWAY. Among names that clear his 5%% floor, requiring "
            "the character clause measures negative: the rejected names win "
            "%.1f%% of the next 21 sessions against %.1f%% for the ones the "
            "gate accepts (+%.2fpp, CI +%.2f to +%.2f). Clause by clause it is "
            "the CONSISTENCY half — ≥2 consecutive growth quarters costs "
            "%spp of win rate (CI %s to %s); `accelerating` is a null, "
            "not a negative. The gate is not edited, because it is his; the "
            "cohort is shown instead, in 🔎 below. Caveat: this one does not "
            "survive date clustering at 21 days (it does at 63), and the "
            "variant matching production's raw list position shrinks it to "
            "1,030 bars with CIs spanning zero."
            % (m["reject_win_21d"], m["pass_win_21d"],
               m["reject_minus_pass_21d"], m["reject_ci_21d"][0],
               m["reject_ci_21d"][1], "%.2f" % abs(m["consec_win_cost_21d"]),
               _sgn(m["consec_ci_21d"][0]), _sgn(m["consec_ci_21d"][1]))
        ),
        "struck": (
            "Struck on re-measurement and said nowhere: that EP+PASS also "
            "loses to EP+FAIL (−2.42pp, CI −4.88 to +0.30 — spans zero in all "
            "four variants), that BOTH character clauses are inverted (only "
            "the consistency one is), and the first pass's “coverage is 46%” "
            "limitation, which was its own no-retry fetcher losing half its "
            "requests."
        ),
        "limits": (
            "Limits: delisting survivorship is unmeasured (today's universe "
            "membership, so anything that went to zero is absent from every "
            "cell); the tier panel is 24 cross-sections inside ONE bull "
            "regime; 24.3% of quarterly rows carry no filing date and are "
            "assumed available at end-of-quarter + 90 days; 24.6% of pivots "
            "are unclassifiable and the dropout is structural (recent IPOs and "
            "de-SPACs); returns are gross of commissions, slippage and borrow, "
            "and real fills on 8% gaps would be worse for the pivot cohort "
            "than for the placebo."
        ),
        "scripts": m["scripts"],
    }


def note(n_pass: int, n_scanned: int, counts: dict,
         reg: Optional[dict] = None) -> str:
    """The sentence under the board.

    It leads with the measurement, not the rules. The fire rate is still here —
    his sales gate alone describes half the market — but it is now the second
    fact, because the first fact is that the intersection this board was built
    on measures the wrong way round.
    """
    m = MEASURED
    pct = round(100.0 * n_pass / n_scanned, 1) if n_scanned else None
    return (
        "MEASURED %s AND THE THESIS IS INVERTED. This board was built on the "
        "idea that Bonde's sales screen is the universe and the Episodic Pivot "
        "is the entry, so ⚡ the intersection is the selection. On %d Pivots "
        "reconstructed from closed bars (%s) the %d that also passed his sales "
        "gate ran a 21-day median %s%% (win %.1f%%) against %s%% (%.1f%%) "
        "for date-matched non-Pivot names — %spp, 95%% CI %s to %s. His "
        "sales gate alone separated nothing (%spp, CI %s to %s), and it "
        "passes %s of %s names on this scan (%s%%) — half the market is a "
        "description, not a selection. Everything here is a STUDY BOARD: ⚡ "
        "Pivots are shown because you asked to see his stocks, not because "
        "anything measured says to buy them, and the tiers are his documented "
        "5%% floor / 25%% preferred / 100%% explosive hierarchy ordered by "
        "top-line growth — never by the 0-100 score, which the audit could not "
        "separate from the return tail. 🔎 at the bottom is the cohort his "
        "character clause REJECTS, which is the only cell that beat the market "
        "on win rate (%.1f%% vs %.1f%%). The 5/25/100 numbers are Bonde's own "
        "(docs/sepa/sales_confidence_methodology.md, which also lists the "
        "figures widely attributed to him that failed verification); the "
        "Pivot's 8%% gap on 5x volume are THIS APP'S owner settings, not "
        "numbers he published. Scripts: %s. Nothing on this tab gates a scan, "
        "fires an alert or buys in any lane."
        % (m["run_date"], m["ep_events"], m["window"], m["cell_a_n"],
           _sgn(m["cell_a_med_21d"]), m["cell_a_win_21d"],
           _sgn(m["placebo_med_21d"]), m["placebo_win_21d"],
           _sgn(m["lift_21d"]), _sgn(m["lift_ci"][0]), _sgn(m["lift_ci"][1]),
           _sgn(m["sales_alone_lift"]), _sgn(m["sales_alone_ci"][0]),
           _sgn(m["sales_alone_ci"][1]), f"{n_pass:,}", f"{n_scanned:,}", pct,
           m["reject_win_21d"], m["pass_win_21d"], m["scripts"])
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
    print("bonde: %s of %s pass (%s new in %dd), %s floor-clearers REJECTED "
          "for character" % (b["n_pass"], b["n_scanned"], b["n_new"],
                             b["new_days"], b.get("n_rejected")))
    print("verdict:", (b.get("measured") or {}).get("headline"))
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
