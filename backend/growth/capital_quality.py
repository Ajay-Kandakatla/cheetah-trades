"""💎 Capital quality — "very less capital and hi ROI", on the 🚀 Explosive Growth board.

Ajay, 2026-09-22:

    "Ok can you now with in the explosive growth can you add a new tab..
     Where we look at quality I need filter tab in explosive growth tab, whcih
     manage quality like very less capital and hi ROI.
     ...
     Filter and have alerts and new look out for such companies where whcih
     have very high quality. Let me know where you are creating it"

WHAT THIS MODULE IS
───────────────────
A READ over the rows the 🚀 board already built. It answers, per name, a list of
PLAIN QUESTIONS about the balance sheet — does it hold more cash than debt, does
it throw off cash, is the share count rising, does it earn a positive return on
the capital it employs, and does it earn MORE on LESS capital than the rest of
its own sector — and reports which of those questions it could answer, which it
could not, and how many came back yes.

It is computed ONCE per board request from data already in hand: the row fields
`sepa/board_metrics.attach` has just flattened, plus ONE extra projected Mongo
read for the sector peer medians. It fetches nothing per name and opens no
provider socket.

WHAT IT IS NOT
──────────────
**It is not a score, and it is not measured.** `MEASURED = False`. Every cut
below is either an ACCOUNTING FACT (cash exceeds debt — true or false, nothing
fitted) or a COMPARISON AGAINST THE COHORT IN HAND (above this sector's own
median — a rank, not a target). Nobody has measured whether any of it predicts a
return on his universe. `MEASURED_NOTE` is the sentence every surface must print,
and `tests/test_capital_quality.py` pins the flag so it cannot be flipped true
until a study script exists.

It does not borrow `sepa/longterm.py`'s Quality score's credibility either —
that score ships its own `SCORE_IS_MEASURED = False` for the same reason, and
neither one lends the other any weight.

HOW THIS DIFFERS FROM `eq_score`, WHICH IT MUST NEVER BE CONFLATED WITH
──────────────────────────────────────────────────────────────────────
`eq_score` (`sepa/scanner.py:384`, `_earnings_quality_adjustment`) is the
Minervini Ch.8 EARNINGS-quality read: are the reported earnings real — backed by
sales, margin-expanding, free of the Code 33 / double-trouble accounting red
flags. It is an INCOME-STATEMENT question, it is scored 0-100, and it FEEDS THE
SEPA SCORE through `SCORE_WEIGHTS["fundamentals"]`.

This module asks a different question of a different statement: given that the
earnings are what they are, HOW MUCH CAPITAL did the business need to tie up to
produce them, and what does it earn on that capital. It is a BALANCE-SHEET
question, it is not scored, and **it feeds nothing**. Same English word, two
unrelated reads; a surface that shows both must label them apart.

WHAT IT DOES NOT DO (Rule #10 — an executor changes no rule)
────────────────────────────────────────────────────────────
It changes NOTHING about what the 🚀 board selects. The 100/100 screen, its
ordering, its rosters, its cohorts, its alert gates and its warnings are all
untouched. This adds one nested key per row and one summary block. It sorts
nothing by default, gates nothing, and hides nothing on its own — the counts in
`summary["components"]` exist precisely so a chip can say how many rows it would
hide BEFORE he toggles it.

NOTHING IS EVER SILENTLY HIDDEN — THE LESSON THE FILE NEXT DOOR ALREADY LEARNED
──────────────────────────────────────────────────────────────────────────────
`frontend/src/components/ExplosiveGrowth.tsx:285` records that a literal
`debt === 0` filter returned ZERO of 29 rows, which is why `debtTier` ships
defaulted to the widest honestly debt-light tier instead of the strictest one.
The same arithmetic applies here and was measured on the live board 2026-09-22:
stacking every definitional cut as one AND-gate leaves **2 of 21 names** (NVDA,
TER). A gate that hides 19 of 21 is not a filter, it is a blindfold.

So this ships a GRADED read plus per-component counts, never a boolean. A name
that fails a component is still on the board, still ranked, and still says which
component it failed and why.

**UNKNOWN IS NOT FAILED.** A component whose input is missing returns
`"unknown"` with a named reason and is excluded from the counts entirely — it
never lands in `failed`, and it never drags a grade down. A name whose every
component is unknown grades `"unknown"` and is not ranked at all (`rank_key`
None) rather than being ranked last, because "we could not look" and "we looked
and it was bad" are different facts and a board that conflates them is lying.

THE "LOW CAPITAL" LEG NEEDS PEERS, AND THE PEERS ARE NOT THE BOARD
──────────────────────────────────────────────────────────────────
"Low capital" has no definitional form. There is no sign test for it: every
operating company has positive capex, so unlike "cash > debt" there is no
natural zero to cut at. Answering it requires either a THRESHOLD (which this
package refuses to invent) or a COMPARISON.

The comparison cannot be made against the 🚀 board itself. Measured 2026-09-22,
the board is 21 rows and its largest sector cohort is **Technology with 6
names**; a median over 6 — or over the 1 name in Industrials — is the "comparing
against 2 names" failure this read exists to avoid.

It is made instead against the `board_metrics` collection, which every board in
the app warms and which already carries a `sector` on each document. Measured in
the api container 2026-09-22: 485 documents, 413 fresh within `TTL_SEC`, **340
operating and sectored** — the cohort this module actually reduces over, read in
2.1 ms. Six sectors clear the peer floor: Industrials 87, Technology 85,
Healthcare 50, Energy 32, Consumer Cyclical 30, Basic Materials 29.
Communication Services (11), Consumer Defensive (10) and Utilities (6) do NOT,
and are refused by name rather than compared against a handful.

That cohort is a convenience sample — it is "every name this app has recently
pulled a balance sheet for", not a designed universe — so `summary["peers"]`
serves its size and its per-sector counts, and the reason string on a refused
component names the shortfall. The reader is never shown a median without being
told what it is a median of.

THE PEER FLOOR IS THE HOUSE FLOOR, NOT A NEW ONE
────────────────────────────────────────────────
`MIN_PEERS = 20`, which is `sepa/longterm.py`'s `MIN_SECTOR_N` — the app's
existing floor for exactly this operation, a within-sector percentile, where its
comment reads *"Below this, a within-sector percentile is noise."* It is pinned
equal to that constant by test so the two cannot drift. It is not invented here
and it is not tuned here.

RULE #7 — THE AS-OF PERIOD, NEVER THE CACHE AGE
───────────────────────────────────────────────
Every component that reads a return-on-capital figure carries the FISCAL QUARTER
that figure came from (`capital_period` / `capital_period_end`, set by
`board_metrics._attach_capital_returns`). A balance sheet fetched an hour ago
can still be a quarter old, and only the period says which.
"""
from __future__ import annotations

import logging
import math
from typing import Optional

log = logging.getLogger("growth.capital_quality")

# ─────────────────────────────────────────────────────────── the measured flag

# FLIP THIS ONLY WHEN `STUDY_SCRIPT` EXISTS AND HAS RUN.
# False = every surface must present this as a description of what the filings
# say, never as a forecast or an edge. Pinned by
# tests/test_capital_quality.py::test_measured_true_requires_the_study_script.
MEASURED = False

# Where the study would live if one is ever run. Named here so the test that
# guards `MEASURED` has one path to check, and so the docs have one path to
# point at. It deliberately does NOT exist yet.
STUDY_SCRIPT = "backend/scripts/capital_quality_study.py"

# The sentence a surface prints. Plain words, his register, no hedging clause
# that could be mistaken for a disclaimer about the DATA — the data is filed
# fact; it is the RANKING that is unmeasured.
MEASURED_NOTE = (
    "This orders names by balance-sheet quality — how much capital the business "
    "ties up and what it earns on it. Nobody has measured whether that predicts "
    "anything on your universe. It is a screen, not an edge."
)

# ─────────────────────────────────────────────────────────── the peer floor

# `sepa/longterm.py:MIN_SECTOR_N` — the app's existing floor for a within-sector
# comparison, whose own comment is "Below this, a within-sector percentile is
# noise." NOT a new number: pinned equal to that constant by test. Deliberately
# re-stated rather than imported, because `sepa.longterm` pulls the scoring
# stack in with it and this module must stay importable from a board request.
MIN_PEERS = 20

# ─────────────────────────────────────────────────────────── the components

# The three verdicts. `UNKNOWN` is a first-class answer, never a soft FAIL.
PASS, FAIL, UNKNOWN = "pass", "fail", "unknown"

# Two kinds of cut, and the distinction is the whole safety argument:
#   DEFINITIONAL — a sign test or an inequality between two filed figures. There
#                  is no number to pick: "cash exceeds debt" is true or false.
#   RELATIVE     — above/below the name's OWN SECTOR median, computed from the
#                  cohort in hand at read time. A rank, never a target.
# There is no third kind. No component anywhere in this file compares a figure
# to a constant that someone chose.
DEFINITIONAL, RELATIVE = "definitional", "relative"

COMPONENTS = (
    # key                   kind          the question, in his words
    ("net_cash",            DEFINITIONAL, "Holds more cash than debt"),
    ("positive_fcf",        DEFINITIONAL, "Throws off cash, does not burn it"),
    ("no_dilution",         DEFINITIONAL, "Share count is not rising"),
    ("positive_roce",       DEFINITIONAL, "Earns a positive return on capital"),
    ("roce_above_sector",   RELATIVE,     "Earns more on capital than its sector"),
    ("capex_below_sector",  RELATIVE,     "Ties up less capital than its sector"),
)

COMPONENT_KEYS = tuple(k for k, _kind, _label in COMPONENTS)

# The two fields a sector median is taken over, and the row field each reads.
# `capex_intensity_pct` is LOWER-IS-BETTER — the "less capital" half of the ask.
RELATIVE_FIELDS = {
    "roce_above_sector": ("roce_pct", "higher"),
    "capex_below_sector": ("capex_intensity_pct", "lower"),
}

# Why a component could not be answered. A blank is never a zero and never a
# failure; the house pattern from `sepa/since_report.py` and
# `sepa/capital_returns.REASONS`.
UNKNOWN_REASONS = (
    "missing_cash_or_debt",      # the balance sheet has no cash or no debt line
    "missing_fcf_yield",         # no free-cash-flow yield on the row
    "missing_shares_yoy",        # share count year-over-year not computable
    "missing_roce",              # return on capital employed refused upstream
    "missing_capex_intensity",   # capex intensity refused upstream
    "non_operating_sector",      # a bank / mortgage REIT balance sheet
    "no_sector",                 # the name carries no GICS sector
    "insufficient_peers",        # fewer than MIN_PEERS names with this figure
    "peers_unavailable",         # the peer pool could not be read at all
)

# The grades. Derived ENTIRELY from a COUNT of how many answered components came
# back yes — see `grade_for`. Not one of these boundaries is fitted to an
# outcome, because no outcome has been measured.
GRADES = ("all", "most", "some", "none", "unknown")


def _f(v) -> Optional[float]:
    """A finite float, or None. NaN and inf never leave this function.

    Stops a NaN at the source rather than at the payload edge, so it can never
    reach a comparison — `nan > 0` is False, which would render a NaN as a
    quiet FAIL instead of the UNKNOWN it actually is.
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (f != f or math.isinf(f)) else f


def _median(values) -> Optional[float]:
    """The median of the finite values, or None if there are none.

    Same construction as `growth/api.py:_median`, deliberately: the board's
    group medians and this module's sector medians must not use two different
    definitions of the word.
    """
    vals = sorted(v for v in (_f(x) for x in values or []) if v is not None)
    if not vals:
        return None
    n = len(vals)
    if n % 2:
        return vals[n // 2]
    return (vals[n // 2 - 1] + vals[n // 2]) / 2.0


# ─────────────────────────────────────────────────────────── the peer cohort

def peer_medians(db=None, max_age_sec: Optional[int] = None) -> dict:
    """Sector medians for the relative components. ONE projected Mongo read.

    Returns `{"sectors": {sector: {field: {"median": m, "n": k}}},
              "n_docs": int, "available": bool}`.

    The cohort is the `board_metrics` collection — every name any board in this
    app has recently warmed — filtered to documents that are FRESH by that
    module's own TTL and whose balance sheet is meaningful. A bank's deposits
    are liabilities and a mortgage REIT is levered by design; `board_metrics`
    already flags that cohort, and including it in a median of "capital
    employed" would move the number for every operating name in the sector.

    `n` is counted PER FIELD, not per document: a sector with 99 documents but
    only 3 usable ROCE figures has 3 peers for ROCE, and the floor must see the
    3. Counting documents instead is how a median over three names gets served
    looking like a median over ninety-nine.

    Never raises. On any failure it reports `available: False`, and every
    relative component then answers UNKNOWN with `peers_unavailable` — which is
    the correct answer, and is not a FAIL.
    """
    out = {"sectors": {}, "n_docs": 0, "available": False}
    try:
        from sepa import board_metrics as BM
    except Exception as exc:                                   # noqa: BLE001
        log.debug("capital_quality: board_metrics import failed: %s", exc)
        return out
    d = BM._db(db)
    if d is None:
        return out

    ttl = BM.TTL_SEC if max_age_sec is None else max_age_sec
    try:
        import time as _time
        cutoff = _time.time() - ttl
        docs = list(d[BM.COLL].find(
            {"fetched_at": {"$gte": cutoff}},
            {"sector": 1, "balance_meaningful": 1,
             "capital_returns.roce_pct": 1,
             "capital_returns.capex_intensity_pct": 1}))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("capital_quality: peer read failed: %s", exc)
        return out

    buckets: dict = {}
    for doc in docs:
        if doc.get("balance_meaningful") is False:
            continue
        sec = doc.get("sector")
        if not sec:
            continue
        cr = doc.get("capital_returns") or {}
        if not isinstance(cr, dict):
            continue
        b = buckets.setdefault(sec, {"roce_pct": [], "capex_intensity_pct": []})
        for field in ("roce_pct", "capex_intensity_pct"):
            v = _f(cr.get(field))
            if v is not None:
                b[field].append(v)

    sectors = {}
    for sec, b in buckets.items():
        sectors[sec] = {
            field: {"median": _median(vals), "n": len(vals)}
            for field, vals in b.items()
        }
    out["sectors"] = sectors
    out["n_docs"] = len(docs)
    out["available"] = True
    return out


# ─────────────────────────────────────────────────────────── one component

def _verdict(ok: Optional[bool], detail: Optional[str],
             unknown_reason: Optional[str]) -> dict:
    """One component's answer. Exactly one of pass / fail / unknown."""
    if ok is None:
        return {"verdict": UNKNOWN, "reason": unknown_reason, "detail": None}
    return {"verdict": PASS if ok else FAIL, "reason": None, "detail": detail}


def _definitional(row: dict) -> dict:
    """The four cuts that need no peer and no number.

    Each is a sign test or an inequality between two figures from the SAME
    filing. There is nothing here to tune: `cash > debt` is a fact about a
    balance sheet, not a threshold somebody picked.
    """
    out = {}

    cash, debt = _f(row.get("cash")), _f(row.get("debt"))
    out["net_cash"] = _verdict(
        None if (cash is None or debt is None) else (cash > debt),
        None if (cash is None or debt is None)
        else "cash %s debt" % (">" if cash > debt else "<="),
        "missing_cash_or_debt")

    fcf = _f(row.get("fcf_yield"))
    out["positive_fcf"] = _verdict(
        None if fcf is None else (fcf > 0),
        None if fcf is None else "FCF yield %.2f%%" % fcf,
        "missing_fcf_yield")

    # "not rising" — flat counts as a pass, because a company that issued no
    # stock has not diluted him. The cut is <= 0, not < 0, and that is
    # definitional rather than generous.
    dil = _f(row.get("shares_yoy_pct"))
    out["no_dilution"] = _verdict(
        None if dil is None else (dil <= 0),
        None if dil is None else "shares %+.2f%% YoY" % dil,
        "missing_shares_yoy")

    # The "return on it" half of the ask in its definitional form: is the return
    # on capital employed positive at all. Zero is the natural boundary — below
    # it the capital tied up in the business is destroying value — so this is a
    # sign test, not a target. Measured on the live board 2026-09-22 it is NOT a
    # no-op: it separates SITM (-1.03%) and FF (-17.03%) from the other 14
    # operating names.
    roce = _f(row.get("roce_pct"))
    if roce is None:
        reason = ("non_operating_sector"
                  if (row.get("capital_reasons") or {}).get("roce_pct")
                  == "non_operating_sector" else "missing_roce")
        out["positive_roce"] = _verdict(None, None, reason)
    else:
        out["positive_roce"] = _verdict(roce > 0, "ROCE %.2f%%" % roce, None)
    return out


def _relative(row: dict, peers: dict) -> dict:
    """The two cuts that answer "compared to what" — the sector, never a number.

    `roce_above_sector` is the "high return" leg and `capex_below_sector` is the
    "low capital" leg: together they are the ask. Both refuse rather than
    compare when the sector has fewer than `MIN_PEERS` names carrying that
    figure.
    """
    out = {}
    available = bool(peers.get("available"))
    sector = row.get("sector")
    by_sector = (peers.get("sectors") or {}).get(sector) or {}

    for key, (field, direction) in RELATIVE_FIELDS.items():
        if not available:
            out[key] = _verdict(None, None, "peers_unavailable")
            continue
        # A bank or mortgage REIT is refused by name, not compared. Its ratios
        # were already refused upstream for the same reason.
        if row.get("balance_meaningful") is False:
            out[key] = _verdict(None, None, "non_operating_sector")
            continue
        if not sector:
            out[key] = _verdict(None, None, "no_sector")
            continue
        val = _f(row.get(field))
        if val is None:
            out[key] = _verdict(
                None, None,
                "missing_roce" if field == "roce_pct"
                else "missing_capex_intensity")
            continue
        stat = by_sector.get(field) or {}
        n, med = int(stat.get("n") or 0), _f(stat.get("median"))
        if n < MIN_PEERS or med is None:
            out[key] = _verdict(None, None, "insufficient_peers")
            continue
        ok = (val > med) if direction == "higher" else (val < med)
        out[key] = _verdict(
            ok, "%.2f%% vs sector median %.2f%% (n=%d)" % (val, med, n), None)
        out[key]["peer_n"] = n
        out[key]["sector_median"] = round(med, 2)
    return out


# ─────────────────────────────────────────────────────────── the grade

def grade_for(passed: int, answered: int) -> str:
    """The grade, from a COUNT — and why that count is not a fitted number.

    A fitted threshold is one chosen because it separated an OUTCOME. Nothing
    here has an outcome: no study exists, `MEASURED` is False, and there is no
    forward return anywhere in this module to fit against.

    What is left is a count of yes-answers out of the questions that could be
    answered, and a count admits exactly three boundaries that refer to nothing
    but itself — all of them, none of them, and the line where yes outnumbers
    no. Those are the four grades. `most` and `some` are the two halves of "it
    depends", split at the majority line, which is a property of the count and
    not of any return.

    UNKNOWN components are excluded from `answered` entirely, so a name with
    thin data is graded on what IS known rather than punished for what is not.
    That is also why `answered` is served beside the grade: "all" over two
    questions and "all" over six are the same word and different facts.
    """
    if answered <= 0:
        return "unknown"
    if passed == answered:
        return "all"
    if passed == 0:
        return "none"
    return "most" if passed * 2 > answered else "some"


def for_row(row: dict, peers: Optional[dict] = None) -> dict:
    """The capital-quality read for ONE row. Pure: no I/O, never raises.

    `peers` is the cohort from `peer_medians()`, passed in so a board computes
    it once for every row. Omitted, the relative components answer UNKNOWN with
    `peers_unavailable` — which is honest, and is not a FAIL.
    """
    row = row if isinstance(row, dict) else {}
    peers = peers if isinstance(peers, dict) else {}
    comps = {}
    comps.update(_definitional(row))
    comps.update(_relative(row, peers))

    passed = sum(1 for k in COMPONENT_KEYS if comps[k]["verdict"] == PASS)
    failed = sum(1 for k in COMPONENT_KEYS if comps[k]["verdict"] == FAIL)
    unknown = sum(1 for k in COMPONENT_KEYS if comps[k]["verdict"] == UNKNOWN)
    answered = passed + failed
    grade = grade_for(passed, answered)

    return {
        "grade": grade,
        "passed": passed,
        "failed": failed,
        "unknown": unknown,
        "answered": answered,
        # A name nothing could be answered for is NOT ranked last — it is not
        # ranked. `answered` is the published tiebreak; a surface sorting on
        # `rank_key` alone would tie 3-of-3 with 3-of-6.
        "rank_key": passed if answered > 0 else None,
        "components": comps,
        # Rule #7: the fiscal quarter the capital figures came from, carried
        # through from `board_metrics._attach_capital_returns`. Never the cache
        # age — a balance sheet fetched an hour ago can still be a quarter old.
        "period": row.get("capital_period"),
        "period_end": row.get("capital_period_end"),
        # This read is arithmetic and comparison, not an edge. Carried on every
        # row so no surface can render the grade without it.
        "measured": MEASURED,
    }


# ─────────────────────────────────────────────────────────── the board

def attach(rows: list, db=None) -> dict:
    """Hang the read on every row and return the board summary. Never raises.

    ONE computation per board request: one peer read for the whole board, then
    pure arithmetic per row. No provider call, no per-name fetch — the measured
    reason `board_metrics` exists at all (80 tiles x 1 call = 65 s).

    The summary's per-component counts are what lets a chip say **how many rows
    it would hide, and why, BEFORE he toggles it** — the `ExplosiveGrowth.tsx`
    `debtTier` lesson, where a literal `debt === 0` filter silently returned
    zero of 29 rows.

    TWO survivor counts, because they answer two different questions and
    conflating them is how a board empties itself without warning:

      `no_fail_n`    — rows with ZERO failed components: what is still on screen
                       with every chip switched on. This is the number a warning
                       must use, because a chip hides FAILURES and an unknown
                       row was never judged (see `hides_n`).
      `all_pass_n`   — rows where every component came back PASS with nothing
                       unknown: the strictest possible read. This is the "2 of
                       21" the stacked AND-gate measured 2026-09-22, and it sits
                       at 0 until the peer cohort carries return-on-capital
                       figures, because the two relative components cannot pass
                       while they are unknown.
    """
    rows = rows if isinstance(rows, list) else []
    try:
        peers = peer_medians(db=db)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("capital_quality: peers failed: %s", exc)
        peers = {"sectors": {}, "n_docs": 0, "available": False}

    counts = {k: {"pass": 0, "fail": 0, "unknown": 0} for k in COMPONENT_KEYS}
    grades = {g: 0 for g in GRADES}
    all_pass = 0
    no_fail = 0
    graded = 0

    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            read = for_row(r, peers)
        except Exception as exc:                               # noqa: BLE001
            log.debug("capital_quality: row failed: %s", type(exc).__name__)
            continue
        r["capital_quality"] = read
        graded += 1
        grades[read["grade"]] = grades.get(read["grade"], 0) + 1
        for k in COMPONENT_KEYS:
            counts[k][read["components"][k]["verdict"]] += 1
        # What survives every chip switched on. A chip hides FAILURES, so a row
        # with unknowns but no failure is still on screen — this is the number a
        # "you are about to hide 19 of 21 rows" warning must be built from.
        if read["failed"] == 0:
            no_fail += 1
        # The strictest read: every component a PASS, nothing unknown.
        if read["passed"] == len(COMPONENT_KEYS):
            all_pass += 1

    return {
        "n": graded,
        "grades": grades,
        "components": [
            {"key": key, "kind": kind, "label": label,
             "pass_n": counts[key]["pass"],
             "fail_n": counts[key]["fail"],
             "unknown_n": counts[key]["unknown"],
             # What a chip toggling THIS component on would hide. Failures
             # only: an unknown row is not hidden, because it was never judged.
             "hides_n": counts[key]["fail"]}
            for key, kind, label in COMPONENTS
        ],
        "all_pass_n": all_pass,
        "no_fail_n": no_fail,
        "peers": {
            "available": bool(peers.get("available")),
            "n_docs": int(peers.get("n_docs") or 0),
            "min_peers": MIN_PEERS,
            "sectors": {
                sec: {f: int((stat or {}).get("n") or 0)
                      for f, stat in (fields or {}).items()}
                for sec, fields in (peers.get("sectors") or {}).items()
            },
        },
        "measured": MEASURED,
        "measured_note": MEASURED_NOTE,
        "study_script": STUDY_SCRIPT,
    }
