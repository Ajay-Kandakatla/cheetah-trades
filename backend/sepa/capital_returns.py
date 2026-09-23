"""Return on capital — ROCE, ROIC, ROE, asset turnover, capex intensity.

Ajay 2026-09-22: *"Where we look at quality ... whcih manage quality like very
less capital and hi ROI."*

WHY THIS MODULE HAD TO EXIST AT ALL
───────────────────────────────────
"High ROI on low capital" is the whole ask, and before this file the app could
not compute ANY return on capital. Measured 2026-09-22 against the live growth
board: `ROCE`, `ROIC`, `ROE`, `capital employed`, `capex`, `total assets`,
`total equity`, `invested capital` and `operating income` appear NOWHERE in the
codebase. The quality read is not a ranking problem, it is a missing-data
problem, and this module is that gap closed.

NO SECOND PROVIDER, NO SECOND FETCH
───────────────────────────────────
Everything below is computed from the payload `sepa/board_metrics.py` ALREADY
pulls — one Massive `/vX/reference/financials` call per name, 12 quarters, made
once per board warm. This module is pure: it takes that `results` list and
returns numbers. It opens no socket. That keeps the house rule the boards are
built on — ONE snapshot per board, never a per-name fetch on a board request
(80 tiles x 1 call = 65 s, the measured reason `board_metrics` exists).

THE DERIVED-Q4 SPLIT — THE FINDING THIS MODULE TURNS ON
───────────────────────────────────────────────────────
`board_metrics` drops every quarter whose `filing_date is None` (a DERIVED Q4 —
annual minus the three reported quarters), because for an AVERAGE SHARE COUNT
that subtraction is arithmetic nonsense: NVDA's reads -28,000,000.

**That guard must NOT be inherited here, and the docstring next door says why:**
*"For a flow item that subtraction is fine; for an AVERAGE share count it is
meaningless."* Measured on the 21 live growth names 2026-09-22:

    4 consecutive REPORTED quarters (derived Q4 excluded)      1/21
    4 consecutive quarters INCLUDING derived Q4                21/21

A TTM window built from reported-only quarters is empty for 20 of 21 names,
because almost every company's Q4 is derived. Including derived Q4s for FLOW
items takes it to 21/21, and the reconstruction was verified against an
independent source rather than assumed:

    NVDA TTM revenue, summed from Massive quarters  302,969 M
    yfinance `.info.totalRevenue` (independent TTM)  302,970 M

To the dollar, and 13 of 21 names agree within 1%. The eight that do not are
dominated by mortgage REITs and financials (DX -50.8%, ARR -51.8%, NLY -58.0%),
where the two sources define "revenue" differently — which is exactly the
cohort `NON_OPERATING_SECTORS` already tells the boards not to rank.

BALANCE-SHEET VALUES IN A DERIVED Q4 ARE REAL, NOT SUBTRACTED
─────────────────────────────────────────────────────────────
Checked before relying on them, because a subtracted balance sheet would be
garbage. NVDA's derived Q4 2026 reports assets 206,803 M, sitting monotonically
between the reported Q3 2026 (161,148 M) and Q1 2027 (259,474 M). The provider
carries the point-in-time balance sheet through on derived rows; only the flow
lines are reconstructed. Same pattern on MU and SITM.

A derived row CAN still carry no flow data at all (NVDA Q4 2025 reports
`revenues: None`), so a TTM sum returns None the moment any quarter in the
window is missing its line. It never sums three quarters and calls it four.

WHAT IS MEASURED HERE AND WHAT IS NOT
─────────────────────────────────────
`MEASURED = False`. Every ratio below is an ACCOUNTING IDENTITY computed from
filed figures — arithmetic, not an edge. Nothing in this file has been shown to
predict a return, and no threshold in it has been fitted to an outcome. It is a
SCREEN. The app's own precedent is `sepa/longterm.py:105`, which ships
`SCORE_IS_MEASURED = False` for the same reason, and this module does not get to
borrow that score's credibility or lend it any.

NO INVENTED NUMBER — NOT EVEN THE SANITY BOUND
──────────────────────────────────────────────
Every cut in this file is definitional: a denominator must be positive, a tax
rate must lie in [0, 1], a window must have four quarters, an average needs the
quarter it averages against. The one constant that COULD have been a picked
number, `MIN_DENOMINATOR_ASSET_SHARE`, ships at **0.0 — off** — because review
measured that a blanked ratio is not a neutral act here: an UNKNOWN component
is excluded from `answered`, so suppressing a ratio can RAISE a capital
destroyer's grade. The constant and its guard remain, documented at their
definition, so setting a value is his call and one edit.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("sepa.capital_returns")

# This module is arithmetic on filed figures, not a measured edge. Any surface
# rendering these numbers must say so; see the module docstring.
MEASURED = False

# Quarters in a trailing-twelve-month window. Definitional, not a choice.
TTM_QUARTERS = 4

# Why a value is absent. A BLANK IS NEVER A ZERO — the house pattern, copied
# from `sepa/since_report.py:86`, so a board can explain an em-dash instead of
# leaving the reader to guess whether it means "nothing" or "none".
REASONS = (
    "no_quarters",                  # provider returned nothing usable
    "incomplete_ttm_window",        # fewer than 4 consecutive fiscal quarters
    "missing_input",                # a needed line item is absent in the window
    "negative_capital_employed",    # assets - current liabilities <= 0
    "negative_equity",              # equity <= 0
    "denominator_too_small",        # see MIN_DENOMINATOR_ASSET_SHARE
    "nonpositive_pretax_income",    # no honest effective tax rate
    "no_tax_expense",               # provider omits the tax line entirely
    "effective_tax_rate_out_of_range",   # tax benefit, or rate > 100%
    "non_operating_sector",         # a bank/REIT balance sheet is not this
    "no_capex",                     # provider has no capital-expenditure line
    "capex_period_mismatch",        # capex is from a different fiscal quarter
    "nonpositive_denominator",      # generic guard for a ratio's base
)

# THE SANITY BOUND — SHIPPED OFF, BECAUSE IT IS A NUMBER NOBODY MEASURED.
#
# A denominator that is positive but vanishingly small produces a ratio that is
# arithmetically true and economically meaningless: a company with $2 M of
# equity against $4 B of assets prints ROE 4,000% and would sort to the top of
# a "high return on capital" board. The guard below exists for that case, and
# it is expressed RELATIVE to the company's own total assets rather than as an
# absolute dollar floor, so it would scale from FF ($182 M capital employed) to
# NVDA ($206 B) without a per-size table.
#
# **IT SHIPS AT 0.0 — OFF — AND THAT IS THE POINT.** Any positive value here is
# a number somebody picked, and this package does not get to pick one. It was
# briefly set at 1%, and review measured what that cost: an UNKNOWN component
# is excluded from `answered`, so blanking a ratio does not merely hide a cell,
# it can UPGRADE the grade of a capital-DESTROYING name. A company earning
# -167% on a capital base of 0.75% of assets went from `positive_roce = FAIL`
# (grade "most", 3 of 4) to `positive_roce = UNKNOWN` (grade "all", 3 of 3).
# A screen that reads BETTER because a figure was suppressed is worse than no
# screen. At 0.0 the module is purely definitional: a denominator has to be
# positive, and nothing else.
#
# The constant, the guard and the `denominator_too_small` reason all stay, so
# this is HIS CALL and one edit: set it to 0.05 (say) and every ratio in the
# file is bounded again. The cost of that is the mirror case — a near-zero
# capital base then prints a huge POSITIVE ROCE and `positive_roce` PASSes
# instead of going UNKNOWN. Nobody has measured which error is dearer, so the
# package ships the setting that invents nothing.
MIN_DENOMINATOR_ASSET_SHARE = 0.0

# Two fiscal period-ends belong to the SAME quarter when they are nearer to each
# other than to the neighbouring quarter-end. A quarter is ~91 days, so the
# midpoint is ~45. This is NEAREST-QUARTER ROUNDING — definitional, not tuned.
# It exists because two providers stamp the same quarter days apart (MU: Massive
# 2026-05-28 vs yfinance 2026-05-31) while a genuinely stale source is a whole
# quarter off (NLY: Massive 2026-03-31 vs yfinance 2026-06-30, measured
# 2026-09-22).
SAME_QUARTER_DAYS = 45


def _f(v) -> Optional[float]:
    """A finite float, or None. NaN and inf never leave this function.

    The house `_scrub` rule stops NaN at the payload edge; this stops it at the
    source, so no NaN can reach an arithmetic step and silently poison a sum.
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (f != f or f in (float("inf"), float("-inf"))) else f


def _period_index(report: dict) -> Optional[int]:
    """A fiscal quarter as one comparable integer: year*4 + (quarter-1).

    Same construction as `sepa/qoq.py` and `board_metrics._period_index`, and
    for the same reason: it makes "exactly one quarter earlier" a subtraction
    instead of a date guess, so MU, NVDA and LPG — none of whose fiscal years
    match the calendar — are walked along their OWN quarters.

    Deliberately NOT imported from `board_metrics`: that module imports this
    one, and a cycle here would take both boards down on an import error.
    """
    try:
        fy = int(report.get("fiscal_year"))
    except (TypeError, ValueError):
        return None
    fp = str(report.get("fiscal_period") or "").upper().strip()
    if not fp.startswith("Q") or len(fp) < 2 or not fp[1].isdigit():
        return None
    q = int(fp[1])
    if not 1 <= q <= 4:
        return None
    return fy * 4 + (q - 1)


def _line(report: dict, statement: str, key: str) -> Optional[float]:
    """One line item out of one filing, or None."""
    fin = report.get("financials") or {}
    blob = fin.get(statement) or {}
    cell = blob.get(key)
    if not isinstance(cell, dict):
        return None
    return _f(cell.get("value"))


def _filed_key(item) -> str:
    """A filing date as a sortable string, `""` when absent (a derived row).

    ISO dates sort lexicographically, so this needs no date parse and cannot
    raise on a malformed stamp — an unreadable date sorts as an absent one,
    which is the safe side: it never lets a junk value outrank a real filing.
    """
    r = item[1] if isinstance(item, tuple) else item
    v = (r or {}).get("filing_date")
    return str(v) if isinstance(v, str) else ""


def ttm_window(results: list) -> Optional[list]:
    """The four most recent CONSECUTIVE fiscal quarters, newest first.

    Derived Q4s are KEPT — see the module docstring. That is the difference
    between a window for 1 of 21 names and a window for 21 of 21.

    Returns None when the four quarters are not consecutive. It never reaches
    further back to fill a hole: a window with a gap would silently compare a
    five-quarter span against a four-quarter one and report it as a year.

    A quarter that appears TWICE — an original filing and a restatement — is
    resolved by FILING DATE, never by the provider's list order. `_fetch_quarters`
    sends no `sort` parameter, so that order is the provider's default and not a
    guarantee; left to it, the same company would print two different ROCEs
    depending on which row happened to come first, and `positive_roce` is a
    GRADED chip. A filing date is a filed fact, not a chosen number.
    """
    rows = []
    for r in results or []:
        if not isinstance(r, dict):
            continue
        idx = _period_index(r)
        if idx is not None:
            rows.append((idx, r))
    if not rows:
        return None
    # Two stable sorts, newest filing first WITHIN a fiscal quarter, so the
    # `setdefault` below takes the restatement rather than the superseded row.
    # A derived Q4 carries no filing date and sorts behind a reported filing of
    # the same quarter, which is the right way round: reported beats derived.
    rows.sort(key=_filed_key, reverse=True)
    rows.sort(key=lambda t: -t[0])
    by = {}
    for idx, r in rows:
        by.setdefault(idx, r)          # newest FILING wins on a duplicate index
    newest = rows[0][0]
    win = [by.get(newest - k) for k in range(TTM_QUARTERS)]
    if any(w is None for w in win):
        return None
    return win


def ttm_sum(window: list, statement: str, key: str) -> Optional[float]:
    """Sum one FLOW line across the window, or None if any quarter lacks it.

    Never sums what it has and calls it a year — NVDA's derived Q4 2025 carries
    `revenues: None`, and three quarters presented as four would understate a
    denominator by ~25% and overstate every ratio built on it.
    """
    total = 0.0
    for w in window or []:
        v = _line(w, statement, key)
        if v is None:
            return None
        total += v
    return total


def _ratio(num: Optional[float], den: Optional[float],
           assets: Optional[float]) -> tuple:
    """`(value, reason)` — the one place a denominator is ever divided by.

    Every guard that protects this package lives here, so no caller can forget
    one. Order matters: a missing input is reported as missing, not as a bad
    denominator.
    """
    if num is None or den is None:
        return None, "missing_input"
    if den <= 0:
        return None, "nonpositive_denominator"
    if assets is not None and assets > 0 and MIN_DENOMINATOR_ASSET_SHARE > 0:
        if den < MIN_DENOMINATOR_ASSET_SHARE * assets:
            # See MIN_DENOMINATOR_ASSET_SHARE. A tiny-but-positive base is how
            # a 4,000% ROE gets onto a board looking like the best name on it.
            return None, "denominator_too_small"
    return num / den, None


def effective_tax_rate(window: list) -> tuple:
    """`(rate, reason)` from the window's own filings — never a statutory guess.

    A statutory rate would be an INVENTED NUMBER, and this package does not ship
    one. Where the filings cannot produce an honest rate the answer is None with
    a name, and ROIC goes blank for that company.

    Measured on the 21 live growth names 2026-09-22: 13 produce a rate, 5 have
    no tax line at all (LQDA, DX, INSW, ARR, LPG — shipping tonnage regimes and
    REITs, structurally untaxed rather than unfetched), 2 report a tax BENEFIT
    against positive pre-tax income (NLY -0.8%, ALAB -14.7%), and 1 is loss
    making (FF).
    """
    pre = ttm_sum(window, "income_statement",
                  "income_loss_from_continuing_operations_before_tax")
    tax = ttm_sum(window, "income_statement", "income_tax_expense_benefit")
    if pre is None:
        return None, "missing_input"
    if tax is None:
        return None, "no_tax_expense"
    if pre <= 0:
        # A negative pre-tax base makes the rate meaningless, and NOPAT built on
        # it would flip sign. FF is this case on the live board.
        return None, "nonpositive_pretax_income"
    rate = tax / pre
    if rate < 0.0 or rate > 1.0:
        # A tax benefit (rate < 0) would make NOPAT LARGER than EBIT and rank a
        # company higher for having lost money somewhere else.
        return None, "effective_tax_rate_out_of_range"
    return rate, None


def _days_apart(a: Optional[str], b: Optional[str]) -> Optional[int]:
    """Whole days between two ISO dates, or None if either will not parse."""
    from datetime import date
    def p(s):
        try:
            y, m, d = str(s).split("-")[:3]
            return date(int(y), int(m), int(d[:2]))
        except Exception:                                      # noqa: BLE001
            return None
    da, dbb = p(a), p(b)
    if da is None or dbb is None:
        return None
    return abs((da - dbb).days)


def periods_agree(end_a: Optional[str], end_b: Optional[str]) -> Optional[bool]:
    """Do two period-end stamps name the same fiscal quarter?

    None when either date is unusable — unknown is not agreement.
    """
    d = _days_apart(end_a, end_b)
    if d is None:
        return None
    return d <= SAME_QUARTER_DAYS


def compute(results: list, capex_ttm: Optional[float] = None,
            capex_period_end: Optional[str] = None,
            balance_meaningful: bool = True) -> dict:
    """Every return-on-capital figure for one name, from one filing set.

    `capex_ttm` and `capex_period_end` come from the ONLY source that carries a
    capital-expenditure line (see `board_metrics._capex_ttm`); the provider used
    for everything else reports no capex at all — measured 0/21 on the live
    growth board. They are optional: without them the capex-dependent ratios go
    blank with a reason and every other figure is unaffected.

    FORMULAS, each with the definition it follows:

      capital employed = total assets - current liabilities
          The classic ROCE denominator, identical to equity + non-current
          liabilities. Chosen over "total debt + equity - cash" because every
          input comes from the SAME filing, so the ratio cannot mix quarters;
          the cash-adjusted variant would need a cash figure this provider does
          not carry (see the his-call list).

      ROCE  = TTM EBIT / average capital employed
      NOPAT = TTM EBIT x (1 - effective tax rate)
      ROIC  = NOPAT / average capital employed
      ROE   = TTM net income / average equity, BOTH on the same basis
      asset turnover = TTM revenue / average total assets
      capex intensity = |TTM capex| / TTM revenue
      FCF conversion  = (TTM operating cash flow - |TTM capex|) / TTM net income

    ROE'S BASIS IS CHOSEN ONCE, FOR BOTH LEGS, and served as `roe_basis`. It is
    "parent" only when the filings carry BOTH the parent net-income line and
    the parent equity line; otherwise both legs are consolidated, and a missing
    consolidated line is a refusal. Letting them fall back independently is how
    a company with minority interests prints the MINORITY'S earnings over only
    the PARENT'S equity — measured at a 2.5x overstatement on a synthetic set.

    "Average" is the mean of the balance sheet at the END of the window and at
    the end of the quarter BEFORE it — the textbook pairing of a flow measured
    over a year against the stock it was earned on. Where that earlier quarter
    is absent the ending balance is used instead. `denominator_basis` reports
    that choice PER DENOMINATOR — `capital_employed`, `equity` and `assets`
    each fall back on their own — so the reader is never told an average was
    used on a figure that was not averaged.
    """
    out = {
        "measured": MEASURED,
        "period": None, "period_end": None, "filing_date": None,
        "period_is_derived": None,
        "capital_employed": None, "total_assets": None, "total_equity": None,
        "total_liabilities": None, "current_liabilities": None,
        "ttm_ebit": None, "ttm_net_income": None, "ttm_revenue": None,
        "ttm_operating_cash_flow": None, "ttm_capex": None, "ttm_fcf": None,
        "effective_tax_rate": None, "nopat": None,
        "denominator_basis": None, "roe_basis": None,
        "roce_pct": None, "roic_pct": None, "roe_pct": None,
        "asset_turnover": None, "capex_intensity_pct": None,
        "fcf_conversion_pct": None,
        "reasons": {},
    }

    def refuse(field: str, reason: str) -> None:
        out["reasons"][field] = reason if reason in REASONS else "missing_input"

    win = ttm_window(results)
    if win is None:
        for f in ("roce_pct", "roic_pct", "roe_pct", "asset_turnover",
                  "capex_intensity_pct", "fcf_conversion_pct"):
            refuse(f, "no_quarters" if not results else "incomplete_ttm_window")
        return out

    latest = win[0]
    out["period"] = "%s %s" % (latest.get("fiscal_period"),
                               latest.get("fiscal_year"))
    out["period_end"] = latest.get("end_date")
    out["filing_date"] = latest.get("filing_date")
    # A derived latest quarter is reported honestly rather than hidden: its
    # balance sheet is real (verified) but its flow lines are reconstructed.
    out["period_is_derived"] = not bool(latest.get("filing_date"))

    # ── balance sheet: ending, and one quarter before the window ────────────
    a0 = _line(latest, "balance_sheet", "assets")
    cl0 = _line(latest, "balance_sheet", "current_liabilities")
    # The two equity lines are kept APART rather than collapsed with `or`.
    # `or` is a truthiness test: a parent equity of exactly 0.0 — a company
    # whose book value the minority owns all of — would fall through to the
    # consolidated figure and print a comfortable ROE against a denominator
    # belonging to a different entity than the numerator. Which one is used is
    # decided ONCE, with the net-income leg, below.
    e0_parent = _line(latest, "balance_sheet", "equity_attributable_to_parent")
    e0_total = _line(latest, "balance_sheet", "equity")
    out["total_assets"] = a0
    out["current_liabilities"] = cl0
    out["total_liabilities"] = _line(latest, "balance_sheet", "liabilities")

    ce0 = (a0 - cl0) if (a0 is not None and cl0 is not None) else None
    out["capital_employed"] = ce0

    prior = None
    newest_idx = _period_index(latest)
    if newest_idx is not None:
        want = newest_idx - TTM_QUARTERS
        # Same rule as `ttm_window`: a restated quarter is resolved by FILING
        # DATE, not by which copy the provider listed first. `max` keeps the
        # first of equal keys, so with no duplicate this is the old behaviour.
        cands = [r for r in (results or [])
                 if isinstance(r, dict) and _period_index(r) == want]
        if cands:
            prior = max(cands, key=_filed_key)
    a1 = _line(prior, "balance_sheet", "assets") if prior else None
    cl1 = _line(prior, "balance_sheet", "current_liabilities") if prior else None
    # `is None`, never truthiness — a filed equity of exactly 0.0 is a ZERO the
    # company reported, not an absent line, and `or` would silently promote the
    # consolidated figure in its place.
    e1_parent = _line(prior, "balance_sheet",
                      "equity_attributable_to_parent") if prior else None
    e1_total = _line(prior, "balance_sheet", "equity") if prior else None
    ce1 = (a1 - cl1) if (a1 is not None and cl1 is not None) else None

    def avg(x, y):
        return (x + y) / 2.0 if (x is not None and y is not None) else x

    ce_avg, assets_avg = avg(ce0, ce1), avg(a0, a1)

    # ── TTM flows ───────────────────────────────────────────────────────────
    ebit = ttm_sum(win, "income_statement", "operating_income_loss")
    ni_parent = ttm_sum(win, "income_statement",
                        "net_income_loss_attributable_to_parent")
    ni_total = ttm_sum(win, "income_statement", "net_income_loss")
    ni = ni_parent if ni_parent is not None else ni_total
    rev = ttm_sum(win, "income_statement", "revenues")
    ocf = ttm_sum(win, "cash_flow_statement",
                  "net_cash_flow_from_operating_activities")
    out["ttm_ebit"], out["ttm_net_income"] = ebit, ni
    out["ttm_revenue"], out["ttm_operating_cash_flow"] = rev, ocf

    # ── ROE's basis: ONE choice for the numerator AND the denominator ───────
    # Falling back independently is how a company with minority interests
    # prints the minority's earnings over only the parent's equity. Parent
    # basis only when BOTH parent lines are filed; otherwise consolidated for
    # both, and a missing consolidated line is a refusal, not a mixed ratio.
    if ni_parent is not None and e0_parent is not None:
        roe_basis = "parent"
        roe_ni, e0, e1 = ni_parent, e0_parent, e1_parent
    else:
        roe_basis = "consolidated"
        roe_ni, e0, e1 = ni_total, e0_total, e1_total
    out["roe_basis"] = roe_basis
    out["total_equity"] = e0
    eq_avg = avg(e0, e1)

    # Per DENOMINATOR, never one word for three. Each of `ce_avg`, `eq_avg` and
    # `assets_avg` falls back to its own ending balance independently, so a
    # single flag taken off the capital-employed leg would tell the reader an
    # average was used on a ROE that was computed on the ending balance — and
    # this is the field a reader uses to decide whether two names' figures are
    # comparable at all.
    out["denominator_basis"] = {
        "capital_employed": "average" if ce1 is not None else "ending",
        "equity": "average" if e1 is not None else "ending",
        "assets": "average" if a1 is not None else "ending",
    }

    # A bank's deposits are liabilities and a mortgage REIT is levered by
    # design; "capital employed" does not mean there what it means elsewhere.
    # The raw figures above are kept so a drill-in can still show them, but
    # every RATIO is refused by name rather than rendered as if comparable.
    # Same cohort `board_metrics.NON_OPERATING_SECTORS` already flags.
    if not balance_meaningful:
        for f in ("roce_pct", "roic_pct", "roe_pct", "asset_turnover",
                  "capex_intensity_pct", "fcf_conversion_pct"):
            refuse(f, "non_operating_sector")
        return out

    # ── ROCE ────────────────────────────────────────────────────────────────
    val, why = _ratio(ebit, ce_avg, a0)
    if val is None:
        # Name the real condition rather than the generic one: a negative
        # capital base is a fact about the company, not a missing input.
        if why == "nonpositive_denominator":
            why = "negative_capital_employed"
        refuse("roce_pct", why)
    else:
        out["roce_pct"] = round(100.0 * val, 2)

    # ── ROIC ────────────────────────────────────────────────────────────────
    rate, tax_why = effective_tax_rate(win)
    out["effective_tax_rate"] = round(rate, 4) if rate is not None else None
    if rate is None:
        refuse("roic_pct", tax_why)
    else:
        nopat = ebit * (1.0 - rate) if ebit is not None else None
        out["nopat"] = nopat
        val, why = _ratio(nopat, ce_avg, a0)
        if val is None:
            if why == "nonpositive_denominator":
                why = "negative_capital_employed"
            refuse("roic_pct", why)
        else:
            out["roic_pct"] = round(100.0 * val, 2)

    # ── ROE ─────────────────────────────────────────────────────────────────
    # ROE is the ONE ratio whose denominator does not come from the assets
    # line, so it is the only one that can reach `_ratio` with no `assets`
    # figure to bound it against. ROCE and ROIC cannot: capital employed IS
    # assets minus current liabilities, so they are already None without it.
    # Asset turnover divides by assets itself. Left unguarded, a tiny equity
    # base on a filing with no assets line prints the 4,000% ROE this module
    # exists to refuse — measured at 40,000,000% on a 0.01 equity base.
    # So the missing input is refused as a missing input, exactly as ROCE and
    # ROIC already refuse it, rather than computing a number no bound could be
    # applied to. This invents nothing and holds whatever
    # MIN_DENOMINATOR_ASSET_SHARE is set to.
    if a0 is None or a0 <= 0:
        refuse("roe_pct", "missing_input")
    else:
        val, why = _ratio(roe_ni, eq_avg, a0)
        if val is None:
            if why == "nonpositive_denominator":
                # Negative book equity dividing a negative profit prints a
                # POSITIVE ROE and reads as the best name on the board.
                why = "negative_equity"
            refuse("roe_pct", why)
        else:
            out["roe_pct"] = round(100.0 * val, 2)

    # ── asset turnover ──────────────────────────────────────────────────────
    val, why = _ratio(rev, assets_avg, None)
    if val is None:
        refuse("asset_turnover", why)
    else:
        out["asset_turnover"] = round(val, 3)

    # ── capex-dependent ratios ──────────────────────────────────────────────
    # capex arrives from a DIFFERENT source than everything above, so its
    # quarter is checked before it is allowed to divide anything. NLY measured
    # a full quarter apart 2026-09-22; a mixed-quarter ratio is a real defect,
    # not a rounding nuisance.
    if capex_ttm is None:
        refuse("capex_intensity_pct", "no_capex")
        refuse("fcf_conversion_pct", "no_capex")
        return out
    agree = periods_agree(out["period_end"], capex_period_end)
    if agree is not True:
        refuse("capex_intensity_pct", "capex_period_mismatch")
        refuse("fcf_conversion_pct", "capex_period_mismatch")
        return out

    capex = abs(capex_ttm)          # reported negative by the source
    out["ttm_capex"] = capex
    if ocf is not None:
        out["ttm_fcf"] = ocf - capex

    val, why = _ratio(capex, rev, None)
    if val is None:
        refuse("capex_intensity_pct", why)
    else:
        out["capex_intensity_pct"] = round(100.0 * val, 2)

    val, why = _ratio(out["ttm_fcf"], ni, None)
    if val is None:
        # A loss-making company has no meaningful cash conversion OF EARNINGS;
        # dividing by a negative net income would flip the sign of a good
        # cash-generating quarter into a bad-looking number.
        refuse("fcf_conversion_pct", why)
    else:
        out["fcf_conversion_pct"] = round(100.0 * val, 2)

    return out
