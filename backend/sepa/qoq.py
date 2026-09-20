"""Sequential quarter-over-quarter income and growth.

Ajay 2026-09-12: *"May show any stage but prioritize income and growth only
quarter over quarter"*.

WHAT "QUARTER OVER QUARTER" MEANS HERE, AND WHY IT IS NOT WHAT THE BOARD HAD.
The breakout board already printed two quarterly numbers — `sales_yoy` and
`q_eps_yoy` — and both are the latest quarter against the SAME quarter a year
earlier (`canslim._compute_q_eps_growth`, Q0 vs Q4). That is the comparison
Minervini uses, and he uses it for a reason: it cancels seasonality. This module
adds the OTHER comparison, the literal one he asked for — Q0 against Q1, the
quarter that just ended against the one before it.

They are genuinely different orderings, not two names for one number. MEASURED
on his own board, 2026-09-12 (`scripts/qoq_vs_yoy.py`): Spearman 0.579 on
revenue and 0.367 on EPS. Two examples, and the pair is instructive because
they point OPPOSITE ways —

  NFE   revenue YoY +3.6%  ·  sequential +37.7%  ·  own-Q2 norm −3.1%
        Sequential is RIGHT. YoY says "flat" and is wrong; the adjusted
        surprise is +40.8%.

  JFB   revenue YoY +417.8%  ·  sequential −89.5%  ·  own-Q2 history −95.6%
        Sequential is the ARTIFACT. −89.5% is simply what JFB's Q2 does; the
        adjusted surprise is +6.2%. (Weak — only one prior observation.)

The JFB read is a correction to this module's own first draft, which used it
as the headline case for sequential catching a collapse. Measuring the name's
own seasonal history reversed it. That is the entire argument for the seasonal
reference below, made by the example that was supposed to argue against it.

Sequential also COVERS MORE NAMES, because it needs two quarters where YoY needs
five: 59/80 vs 57/80 on revenue, 66/80 vs 56/80 on net income. GOLD has a
sequential number and no YoY at all.

So neither is strictly better, and the board carries both — sequential leads,
because that is what he asked for, and YoY sits beside it as the check.

WHAT THIS MODULE WILL NOT DO. It will not turn a non-comparable number into a
rank. Two traps, both measured rather than imagined:

  • NON-POSITIVE BASE. 21 of the 80 sampled names had a NEGATIVE prior-quarter
    EPS. `(Q0 − Q1) / |Q1|` prints +90% for a name going −0.50 → −0.05 and
    +1600% for −0.02 → +0.30. Neither is comparable to a profitable grower's
    +12%, and sorted raw they would own the top of his board. A non-positive
    base therefore yields NO percentage at all; the name is marked and ranked on
    whether it actually turned, never on an inflated ratio.

  • OUTLIERS. One +5,000% EPS print must not own rank 1 on a board of 250. The
    blend ranks by PERCENTILE within the board, so a number that is merely the
    largest contributes exactly as much as being largest — no more.

Nothing here is a claim that quarter-over-quarter growth predicts the next move.
It is an ORDERING of what already broke out. No study in this app measures
sequential growth against forward return, and none is cited.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

log = logging.getLogger("sepa.qoq")

# Two quarters is the whole requirement — that is the point of the sequential
# read, and the reason it covers names a five-quarter YoY cannot answer for.
QUARTERS_NEEDED = 2

# MATERIALITY FLOOR — and it is the single most important constant here.
#
# A NEGATIVE base is the obvious trap. A TINY POSITIVE base is the bigger one,
# and it is invisible until measured. MEASURED on the live 250-row board
# 2026-09-12 (`scripts/qoq_negative_base.py`): 73 names had a negative prior-Q
# EPS, but ANOTHER 19 had 0 < Q1 EPS < $0.10 — 13 of them under $0.05 — and a
# "require a positive base" rule does not touch one of them.
#
# Ranked on the raw sequential percentage, ELEVEN of the top twenty were bought
# by a non-material base, and NINE of those eleven were tiny-POSITIVE:
#     CDNA +4,040%  $0.05 -> $2.07        SNPS +3,056%  $0.09 -> $2.84
#     DBRG +3,733%  $0.03 -> $1.15        TXNM +2,033%  $0.03 -> $0.64
#     MRVL   +725%  $0.04 -> $0.33        CNH  +1,000%  $0.01 -> $0.11
# None is a grower. SNPS's $0.09 was one amortisation quarter and its $2.84 is
# a return to its own normal — still well under the $7.14 it printed two years
# earlier. CNH's eight-quarter series falls $0.34 -> $0.11, a two-thirds
# DECLINE, and the sequential read called it the fifth-best name on the board.
# MRVL is an AI-sector name, so his standing "AI winners on top" tiebreak would
# have pushed that fake number to the very top.
#
# $0.10 is where those nine stop and the real ones (DVN $0.19, MPC $1.73,
# SMTC $0.27) continue.
MIN_EPS_BASE = 0.10          # dollars per share
MIN_REV_BASE = 1_000.0       # dollars of revenue in the prior quarter

# A same-sign move of at least this size at the SAME point in the calendar last
# year marks the row as a seasonal echo — "this is what it does every year".
# 10% is where the measured transition medians separate (+5.3% Q1->Q2 against
# -4.0% Q4->Q1); a smaller threshold would flag ordinary drift as seasonality.
SEASONAL_ECHO_PCT = 10.0

BASE_OK = "positive"
BASE_NON_POSITIVE = "non_positive"   # prior quarter lost money (or broke even)
BASE_TOO_SMALL = "too_small"         # positive, but too near zero to carry a ratio
BASE_UNKNOWN = "unknown"             # we do not have the two quarters
BASE_NOT_ADJACENT = "gap"            # the two newest filings skip a quarter


def _f(v) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        return f if f == f else None            # NaN out
    except (TypeError, ValueError):
        return None


def _pair(series: Optional[Iterable], i: int, j: int) -> tuple[Optional[float], Optional[float]]:
    """Two SLOTS of a newest-first series. A None inside is a hole, never a
    shift — see `_first_two`."""
    if not series:
        return None, None
    vals = list(series)
    a = _f(vals[i]) if len(vals) > i else None
    b = _f(vals[j]) if len(vals) > j else None
    return a, b


def _first_two(series: Optional[Iterable]) -> tuple[Optional[float], Optional[float]]:
    """The two most recent quarters, newest first — the order Massive returns.

    A None INSIDE the series is a hole, not a shift: skipping it would silently
    compare Q0 against Q2 and call the result quarter-over-quarter. So the two
    values must be the first two SLOTS, and a hole in either means unknown.
    """
    if not series:
        return None, None
    vals = list(series)
    cur = _f(vals[0]) if len(vals) > 0 else None
    prev = _f(vals[1]) if len(vals) > 1 else None
    return cur, prev


def _seq_pct(cur: Optional[float], prev: Optional[float],
             min_base: float) -> tuple[Optional[float], str]:
    """Sequential % change and the STATE of its base.

    Returns (pct, base_state). `pct` is None whenever the base cannot carry a
    ratio — unknown, zero, negative, or too small to mean anything — and the
    state says WHICH, because "we don't know" and "it lost money last quarter"
    are different facts and the board prints them differently.
    """
    if cur is None or prev is None:
        return None, BASE_UNKNOWN
    if prev <= 0:
        return None, BASE_NON_POSITIVE
    if prev < min_base:
        # POSITIVE but tiny. Distinct from a loss on purpose: the page says
        # "near zero" rather than implying the company lost money, and neither
        # state is ever rendered as a percentage.
        return None, BASE_TOO_SMALL
    return round((cur - prev) / prev * 100, 2), BASE_OK


# Slots of the SAME fiscal transition in prior years, newest-first: (Q4,Q5) is
# one year back, (Q8,Q9) two. The quarterly fetch carries 12 quarters (widened
# from 8 on 2026-09-12) so the norm can be an AVERAGE of two observations rather
# than a bet on one year not having been strange.
SEASONAL_SLOTS = ((4, 5), (8, 9))


def _seasonal_norm(series, min_base: float, periods=None) -> Optional[float]:
    """What this name usually does at THIS point in its calendar.

    The mean of the same fiscal transition in prior years. MEASURED on his
    board 2026-09-12 (`scripts/qoq_seasonality.py`), pooled over all history
    and after subtracting each name's own median so scale cannot masquerade as
    season:

        revenue sequential   Q1 −4.4 · Q2 +1.1 · Q3 0.0 · Q4 +1.4
                             spread 5.8pp, rotation placebo 1.2pp, p=0.0005
        EPS sequential       Q1 −12.7 · Q2 +5.6 · Q3 0.0 · Q4 0.0
                             spread 18.3pp, rotation placebo 3.0pp, p=0.0005
        revenue YoY (ctrl)   spread 0.3pp, p=0.119   — no effect, by design
        EPS YoY (ctrl)       spread 1.4pp, p=0.165   — no effect, by design

    Within a name's own series, fiscal quarter explains a median 30.5% of the
    variance of its sequential revenue (shift-null 21.9%; 29% of names beat
    their own 95th-percentile null against a 5% chance). For YoY the same
    figure is 3.5% against a 6.5% null — nothing.

    And it is a third of the ranking: of the variance in the raw sequential
    ordering, 32.9% is the names' seasonal norms.

    ZYME is the example to remember: +90.6% sequential, its own Q2 history
    +85.8%, so +4.8% of actual surprise — while YoY was −90.6%.
    """
    vals = []
    for i, j in SEASONAL_SLOTS:
        # The slot pair must itself be one quarter apart, AND must sit a whole
        # number of YEARS back from the current transition — otherwise it is
        # not the same fiscal quarter and the "seasonal norm" is some other
        # season's.
        if not _adjacent(periods, i, j):
            continue
        if not _adjacent(periods, 0, i, gap=i):
            continue
        cur, prev = _pair(series, i, j)
        pct, _ = _seq_pct(cur, prev, min_base)
        if pct is not None:
            vals.append(pct)
    if not vals:
        return None
    # MEDIAN, not mean. Measured 2026-09-12: one near-zero-revenue quarter gave
    # ATRC a "typical Q2" of +4,825% and destroyed the adjustment outright. The
    # base floors above already refuse that case, but the median costs nothing
    # and does not depend on them staying right.
    vals.sort()
    n = len(vals)
    mid = n // 2
    med = vals[mid] if n % 2 else (vals[mid - 1] + vals[mid]) / 2
    return round(med, 2)


def _adjacent(periods, i: int, j: int, gap: int = 1) -> bool:
    """Are slots i and j exactly `gap` fiscal quarters apart?

    THE SILENT MISLABELLING THIS STOPS. Massive OMITS a quarter it does not
    have rather than leaving a placeholder, so list POSITION is not quarter
    adjacency — ORCL is missing Q2 FY2025 and Q2 FY2026, NVDA is missing Q1
    FY2025. Measured over 200 of his board names: 3.2% of "sequential" pairs
    span two quarters, and 12.6% of the YEAR-over-year pairs the board has been
    printing for months are not four quarters apart (ASO's compares 2027Q2
    against 2025Q4). Without the period keys the board prints a two-quarter
    change and calls it quarter-over-quarter.

    No periods on file (an older cached document, or the yfinance path before
    it carried them) means we cannot check — and an unverifiable pair is
    ACCEPTED, not refused, because refusing every legacy row would blank the
    ranking rather than improve it. `periods_checked` on the result says which
    rows were actually verified.
    """
    if not periods:
        return True
    p = list(periods)
    a = p[i] if len(p) > i else None
    b = p[j] if len(p) > j else None
    if a is None or b is None:
        return True
    try:
        return int(a) - int(b) == gap
    except (TypeError, ValueError):
        return True


# ── the YoY PAIR GUARD, in exactly one place ────────────────────────────────
# The year-over-year legs every board prints (sales.growth_yoy_pct,
# canslim.q_eps_growth_pct, sales.prior_yoy_pct) are computed at list POSITIONS
# 0 vs 4 and 1 vs 5. Massive OMITS a quarter it does not have, so a position
# pair is not always a year apart — IOVA's keys are
# [8105,8104,8102,8101,8100,8098]: 8103 and 8099 (FY Q4 both years) are missing,
# so slot 4 is FY2025 Q1 measured against FY2026 Q2.
#
# growth/tracker.py has refused exactly those rows since 2026-09-14. These
# helpers are that rule, lifted out of the board so the 📈 Bonde board and the
# 🔥 Hottest row apply the IDENTICAL test — "explosive on one board, refused on
# the other off the same filed quarter" is a data-spine bug, not a screen
# difference. Nothing here recomputes a growth number and no threshold moves:
# sepa/sales.py and sepa/canslim.py are book-cited and untouched.
YOY_GAP = 4                 # fiscal quarters between a quarter and its year-ago self
HEADLINE_PAIR = (0, 4)      # latest quarter vs the same quarter a year earlier
PRIOR_PAIR = (1, 5)         # the quarter before vs ITS year-ago
YOY_PAIRS = (HEADLINE_PAIR, PRIOR_PAIR)


def period_ok(periods, pairs=YOY_PAIRS):
    """THE tri-state a surface serves: True / False / None.

    None means UNVERIFIABLE — no keys on file, an unkeyed slot 0, too few
    quarters to reach the headline pair at all, or a year-ago slot that is None
    with NO filed quarter beyond it (trailing blanks are missing data, not a
    missing quarter). Never "fine". True means the
    headline pair was checked and is four quarters apart. False means it was
    checked and is not, or its year-ago slot is a KNOWN HOLE.

    2026-09-20 — HEADLINE HOLE vs PRIOR HOLE, and why they are not the same
    answer. Once `align_reports` has densified the filings by fiscal period
    (below), a None in a YoY slot stops meaning "no key on file" and starts
    meaning "that quarter is absent from the filings". Those two holes have
    different consequences and this function refuses on ONE of them:

      * HEADLINE pair (0, 4) — a hole at slot 4 means the year-ago quarter of
        the latest filed quarter is simply not there, so `growth_yoy_pct` has
        no base. `sales.compute` already yields `score None` on it, so the row
        is PENDING and out of the Bonde board either way; the surfaces mark it.
        → **False**.
      * PRIOR pair (1, 5) — a hole there costs the ACCELERATION read and
        nothing else: `sales.compute` returns `prior_yoy_pct None` and
        `accelerating False` (sales.py:49-53, :69) without ever reading a
        neighbouring quarter. Refusing the whole row for it held out ~105
        names whose headline number is correct. → does NOT refuse.

    The first pair in `pairs` is the headline pair; the rest are prior pairs.
    Calls the module-global `_adjacent`, so a test that monkeypatches
    `sepa.qoq._adjacent` bites through here too (growth board E1 does).
    """
    pairs = tuple(pairs)
    if not periods or not pairs:
        return None
    p = list(periods)
    head_j = pairs[0][1]
    if len(p) <= head_j:
        return None                     # insufficient history — never "fine"
    try:
        int(p[0])
    except (TypeError, ValueError):
        return None                     # unkeyed row (legacy / yfinance)

    for n, (i, j) in enumerate(pairs):
        hole = len(p) <= j or p[i] is None or p[j] is None
        if n == 0:
            if hole:
                # A hole is KNOWN only when a filed quarter exists beyond it —
                # that is what densifying produces (the last slot is always
                # the oldest key). A run of trailing Nones with nothing after
                # is absence of data, not an absent quarter: the legacy shape
                # [8105, None, None, None, None, None] that the growth board
                # ACCEPTED on 2026-09-14 (E1) must stay unverifiable, never a
                # refusal. `_densify` can never emit that shape, so on every
                # aligned list this branch is unchanged (probed 2026-09-20).
                if any(x is not None for x in p[j + 1:]):
                    return False        # the year-ago quarter is ABSENT
                return None             # nothing filed beyond → unverifiable
            if not _adjacent(p, i, j, gap=YOY_GAP):
                return False
        else:
            if hole:
                continue                # prior hole → sales.py already blanks it
            if not _adjacent(p, i, j, gap=YOY_GAP):
                return False
    return True


def headline_hole(periods, pairs=YOY_PAIRS) -> bool:
    """Is the HEADLINE pair's year-ago quarter absent from the filings?

    Only meaningful once the list is densified — on a raw Massive list a
    missing quarter is a SHIFT, not a hole, and `period_ok` catches it as a
    wrong gap instead. False on an unverifiable row (nothing was checked).
    """
    pairs = tuple(pairs)
    if period_ok(periods, pairs) is None:
        return False
    p = list(periods)
    j = pairs[0][1]
    return len(p) <= j or p[pairs[0][0]] is None or p[j] is None


def prior_hole(periods, pairs=YOY_PAIRS) -> bool:
    """Is a PRIOR pair's slot absent? Costs the acceleration read, nothing
    more — `sales.compute` yields `prior_yoy_pct None`, `accelerating False`
    and `consecutive_growth_q 1` on it. Served so a surface can say WHY the
    character clause came up empty. False on an unverifiable row."""
    pairs = tuple(pairs)
    if period_ok(periods, pairs) is None:
        return False
    p = list(periods)
    for i, j in pairs[1:]:
        if len(p) <= j or p[i] is None or p[j] is None:
            return True
    return False


def yoy_pairs_ok(periods, pairs=YOY_PAIRS) -> bool:
    """Is the headline pair a year apart (and no checkable prior pair wrong)?

    ACCEPT-BY-DEFAULT is kept: an unverifiable row answers True, because
    refusing every legacy row would blank the board rather than improve it.
    That is why this is NOT the tri-state a surface should print — use
    `period_ok`.
    """
    return period_ok(periods, pairs) is not False


def yoy_pairs_verifiable(periods, pairs=YOY_PAIRS) -> bool:
    """Could the headline pair be CHECKED at all?

    352 of 2,078 live scan rows and 682 of 3,754 research documents carry no
    `q_period_series` at all (measured 2026-09-20), and on those rows
    `yoy_pairs_ok` is True because nothing could be checked, not because the
    quarters line up. A board that prints a tick for those is lying by omission.

    2026-09-20: a PRIOR-pair hole no longer makes a row unverifiable — the
    headline pair is still checkable, and `prior_hole` says the rest.
    """
    return period_ok(periods, pairs) is not None


def period_label(idx, source=None):
    """'FY2026 Q2' from a fiscal index. The yfinance path stores CALENDAR
    quarters (canslim._q_periods_yf), so those read 'Q2 2026'. None when the
    slot carries no key — never a guess.

    Moved here verbatim from growth/tracker.py (2026-09-20) so every board
    prints the same quarter the same way; the tracker re-exports it.
    """
    try:
        i = int(idx)
    except (TypeError, ValueError):
        return None
    y, q = i // 4, i % 4 + 1
    return f"Q{q} {y}" if source == "yfinance" else f"FY{y} Q{q}"


# ── DENSIFY BY FISCAL PERIOD — the repair, 2026-09-20 ───────────────────────
# Ajay 2026-09-20, on the 164 mismatched pairs the audit found: *"#2 Yes"* —
# repair them to the true year-ago quarter rather than keep holding the rows
# out.
#
# THE DEFECT. Massive OMITS a quarter it does not have rather than leaving a
# placeholder, so every consumer that reads "slot 4" gets whatever filing
# happens to sit fourth in the list. IOVA's keys are
# [8105,8104,8102,8101,8100,8098] — FY Q4 is absent in BOTH years, so slot 4
# is FY2025 Q1 standing in for the year-ago quarter of FY2026 Q2, and the
# board printed the resulting number as growth for months.
#
# THE REPAIR, at the ONE place Massive's rows become series: put one slot per
# fiscal index from the newest key down to the oldest, leave `None` where a
# quarter is missing, and let every positional reader downstream land on the
# right quarter. Nothing is recomputed and no threshold moves — `sepa/sales.py`
# keeps its 5 / 25 / 100 tiers and its arithmetic. A slot that is now None
# yields None, which sales.py, earnings_quality.py and this module already
# handle without ever reading a neighbour.
#
# MEASURED on the live cache 2026-09-20 before this shipped: 0 of the keyed
# documents carried a PARTIAL list (a key sequence with an internal gap AND
# fewer rows than its span) that densify could not place — every gap is a
# plain omission.
def _densify(keys):
    """(slot_periods, {period: source_index}, stats) from a list of raw keys.

    One slot per fiscal index from `max(int keys)` down to `min(int keys)`, so
    the returned list has a slot for every quarter in the span and `None` where
    the filing is absent.

    Walking the SOURCE order, the FIRST occurrence of a period wins and later
    duplicates are ignored. Massive lists filings newest-FILING-first, so the
    first row for a restated quarter is the restatement — NU files two rows for
    FY2024 Q2 (revenue 1,892,600,000 then 1,892,590,000) and the restated one
    is the one the board should read.

    A key that cannot be int-ed (None, a string) has no slot and its row is
    DROPPED; the caller counts those.
    """
    ints = []
    for k in list(keys or []):
        try:
            ints.append(None if k is None else int(k))
        except (TypeError, ValueError):
            ints.append(None)
    got = [v for v in ints if v is not None]
    stats = {"duplicate_periods": 0, "reordered": False}
    if not got:
        return [], {}, stats
    stats["reordered"] = bool(got != sorted(got, reverse=True))
    index_of: dict = {}
    for src, v in enumerate(ints):
        if v is None:
            continue
        if v in index_of:
            stats["duplicate_periods"] += 1      # a later row for the same Q
            continue
        index_of[v] = src
    slot_periods = [p if p in index_of else None
                    for p in range(max(got), min(got) - 1, -1)]
    return slot_periods, index_of, stats


def align_reports(reports, key_fn):
    """(aligned_reports, dropped_unlabelled, stats) — reports by fiscal period.

    `None` sits at every hole. A list with NO int-able key at all is returned
    UNCHANGED (the legacy / yfinance path stores calendar quarters positionally
    and must not be disturbed).
    """
    rows = list(reports or [])
    keys = []
    for r in rows:
        try:
            keys.append(key_fn(r))
        except Exception:                                   # noqa: BLE001
            keys.append(None)
    slot_periods, index_of, stats = _densify(keys)
    if not index_of:
        return rows, 0, {"duplicate_periods": 0, "reordered": False}
    dropped = sum(1 for k in keys if _int_or_none(k) is None)
    aligned = [rows[index_of[p]] if p is not None else None for p in slot_periods]
    return aligned, dropped, stats


def _int_or_none(v):
    try:
        return None if v is None else int(v)
    except (TypeError, ValueError):
        return None


def align_series(periods, **series):
    """Align the parallel period keys and value series onto dense slots.

    Returns `{"q_period_series": [...], "<name>": [...], "dropped_unlabelled",
    "duplicate_periods", "reordered"}`. With no int-able key the inputs come
    back UNCHANGED — a legacy document is never rearranged on a guess.
    """
    keys = list(periods or [])
    slot_periods, index_of, stats = _densify(keys)
    if not index_of:
        out = {"q_period_series": keys}
        out.update({k: list(v or []) for k, v in series.items()})
        out.update({"dropped_unlabelled": 0, "duplicate_periods": 0,
                    "reordered": False})
        return out
    out = {"q_period_series": list(slot_periods)}
    for name, vals in series.items():
        v = list(vals or [])
        out[name] = [(v[index_of[p]] if (p is not None and index_of[p] < len(v))
                      else None) for p in slot_periods]
    out["dropped_unlabelled"] = sum(1 for k in keys if _int_or_none(k) is None)
    out["duplicate_periods"] = stats["duplicate_periods"]
    out["reordered"] = stats["reordered"]
    return out


def yoy_pct(series, i: int = 0, gap: int = YOY_GAP):
    """THE year-over-year arithmetic, in one place: slot `i` vs slot `i+gap`.

    `(a − b) / |b| × 100`, 2 dp. None when either slot is absent or the base is
    zero. `|b|` (not `b`) matches what `canslim._compute_q_eps_growth` and
    `sales._yoy` have always done — a name going −0.50 → −0.05 must not print
    a confident sign flip.
    """
    s = list(series or [])
    j = i + gap
    if len(s) <= j or i < 0:
        return None
    a, b = s[i], s[j]
    if a is None or b is None:
        return None
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return None
    if b == 0:
        return None
    return round((a - b) / abs(b) * 100.0, 2)


def compute(rev_series=None, eps_series=None, ni_series=None,
            periods=None) -> dict:
    """Sequential growth (revenue) and income (EPS, net income) for one name.

    Every series is newest-first, as Massive's quarterly financials return them
    and as `canslim` already stores them. `periods` is the parallel list of
    `fiscal_year*4 + (quarter-1)` indices; when present, a pair that is not
    actually one quarter apart is refused rather than mislabelled.
    """
    rev_cur, rev_prev = _first_two(rev_series)
    # THE SAME FISCAL TRANSITION ONE YEAR EARLIER (slots 4 and 5). This is the
    # seasonality reference, and it is the answer to the one real objection to
    # a sequential read: a retailer's January quarter is smaller than its
    # December quarter EVERY year, and raw sequential calls that a collapse.
    #
    # MEASURED on his own board 2026-09-12: median sequential revenue by fiscal
    # transition runs +5.3% for Q1->Q2 (31% negative) against -4.0% for Q4->Q1
    # (63% negative) — a fiscal-Q1 reporter is docked ~9 points of "growth" for
    # no business reason at all. Sequential revenue against the SAME transition
    # a year earlier correlates 0.376 (n=148); against the ADJACENT transition,
    # 0.023. The seasonal component is real, large, and repeatable.
    rev_ly = _seasonal_norm(rev_series, MIN_REV_BASE, periods)
    eps_ly = _seasonal_norm(eps_series, MIN_EPS_BASE, periods)
    seq_ok = _adjacent(periods, 0, 1)
    eps_cur, eps_prev = _first_two(eps_series)
    ni_cur, ni_prev = _first_two(ni_series)

    growth_pct, growth_base = _seq_pct(rev_cur, rev_prev, MIN_REV_BASE)
    income_pct, income_base = _seq_pct(eps_cur, eps_prev, MIN_EPS_BASE)
    ni_pct, ni_base = _seq_pct(ni_cur, ni_prev, MIN_REV_BASE)
    if not seq_ok:
        # The two newest filings are not consecutive quarters. Printing their
        # difference as "quarter over quarter" would be a confident false
        # label — worse than an em-dash.
        growth_pct, growth_base = None, BASE_NOT_ADJACENT
        income_pct, income_base = None, BASE_NOT_ADJACENT
        ni_pct, ni_base = None, BASE_NOT_ADJACENT

    # A loss-maker that just printed its first profitable quarter is a real
    # event and he should see it — but it is NOT a growth percentage, and it
    # does not get to compete on one. It is recorded as a fact.
    turned = None
    if eps_prev is not None and eps_cur is not None:
        if eps_prev <= 0 and eps_cur > 0:
            turned = "to_profit"
        elif eps_prev <= 0 and eps_cur > eps_prev:
            turned = "narrowing"
        elif eps_prev > 0 and eps_cur <= 0:
            turned = "to_loss"

    # What the SAME transition did a year ago, and how far this year beats it.
    # Points, not a ratio of ratios: "+12pp better than its own seasonal norm"
    # is a sentence; "+0.4x" is not.
    growth_ly, income_ly = rev_ly, eps_ly
    growth_vs_seasonal = (None if growth_pct is None or growth_ly is None
                          else round(growth_pct - growth_ly, 2))
    income_vs_seasonal = (None if income_pct is None or income_ly is None
                          else round(income_pct - income_ly, 2))
    # A move this name makes every year at this point in its calendar. Flagged,
    # never silently removed — he asked for quarter over quarter and gets it.
    seasonal = bool(growth_ly is not None and growth_pct is not None
                    and abs(growth_ly) >= SEASONAL_ECHO_PCT
                    and (growth_ly > 0) == (growth_pct > 0))

    return {
        "growth_qoq_pct": growth_pct,
        "growth_base": growth_base,
        "growth_qoq_ly_pct": growth_ly,
        "income_qoq_ly_pct": income_ly,
        "growth_vs_seasonal_pp": growth_vs_seasonal,
        "income_vs_seasonal_pp": income_vs_seasonal,
        "seasonal_echo": seasonal,
        "income_qoq_pct": income_pct,
        "income_base": income_base,
        "ni_qoq_pct": ni_pct,
        "ni_base": ni_base,
        "income_turn": turned,
        "periods_checked": bool(periods),
        "eps_latest": eps_cur,
        "eps_prior": eps_prev,
        "rev_latest": rev_cur,
        "rev_prior": rev_prev,
    }


# --------------------------------------------------------------------------
# Ranking
# --------------------------------------------------------------------------
def _percentiles(values: list[Optional[float]]) -> list[Optional[float]]:
    """Rank-to-[0,1] within the board, unknowns left as None.

    PERCENTILE, not the raw number, is what gets blended. On a 250-name board a
    single +5,000% EPS print and a +40% print are one rank apart here; blended
    raw, the first would decide the whole order on its own. Ties share the
    average rank so a block of identical values cannot be ordered by accident.
    """
    known = sorted((v for v in values if v is not None))
    n = len(known)
    if n == 0:
        return [None] * len(values)
    if n == 1:
        return [1.0 if v is not None else None for v in values]

    # average rank of each distinct value (ties -> same percentile)
    pos: dict[float, float] = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and known[j + 1] == known[i]:
            j += 1
        pos[known[i]] = (i + j) / 2.0
        i = j + 1
    return [None if v is None else pos[v] / (n - 1) for v in values]


def rank_values(row: dict, *, seasonal: bool = True) -> tuple:
    """The two numbers a row is RANKED on, and which reading they are.

    Default is the SEASONALLY REFERENCED move — this quarter's sequential
    change minus what the same fiscal transition did a year earlier. It is
    still quarter over quarter; it is measured against the company's own
    calendar instead of against zero.

    WHY THAT IS THE DEFAULT, stated plainly because it departs from the literal
    words. MEASURED 2026-09-12 on his board (`scripts/qoq_negative_base.py`):
    rank names on last quarter's RAW sequential EPS and look at what they did
    the following quarter — median +0.4%, 50% still positive [25, 70]. The
    PLACEBO, every other name on the board: median +24.0%, 70% positive
    [61, 79]. The raw sequential leaderboard performed WORSE than the rest of
    the board. Part of that is mechanical — a high Q1 becomes next quarter's
    denominator — but the mechanism IS the finding: a big sequential number is
    a statement about one quarter's level, not a property of the business.

    A row with no prior-year transition on file falls back to the raw
    sequential number, and says so, rather than dropping out of the ranking.
    """
    if seasonal:
        gi = row.get("growth_vs_seasonal_pp")
        ii = row.get("income_vs_seasonal_pp")
        if gi is not None or ii is not None:
            return (ii if ii is not None else row.get("income_qoq_pct"),
                    gi if gi is not None else row.get("growth_qoq_pct"),
                    "seasonal" if (gi is not None or ii is not None) else "raw")
    return (row.get("income_qoq_pct"), row.get("growth_qoq_pct"), "raw")


def score_board(rows: list[dict], *,
                income_key: str = "income_qoq_pct",
                growth_key: str = "growth_qoq_pct",
                out_key: str = "qoq_score") -> None:
    """Attach a 0-100 income+growth percentile blend to every row, IN PLACE.

    "prioritize income and growth" — both legs, weighted equally. A name with
    only one leg is scored on that leg alone and says so in `qoq_legs`, rather
    than being handed the other leg's median (which would invent a number) or
    dropped (which would hide a real breakout for a filing gap).

    A row with NEITHER leg gets `None`, and the board's sort puts None LAST.
    An unknown never sorts as though it were good — the same discipline the
    recency sort and the demand sort already use.
    """
    inc = _percentiles([r.get(income_key) for r in rows])
    gro = _percentiles([r.get(growth_key) for r in rows])
    for r, i, g in zip(rows, inc, gro):
        legs = [p for p in (i, g) if p is not None]
        r["qoq_income_pctile"] = None if i is None else round(i * 100, 1)
        r["qoq_growth_pctile"] = None if g is None else round(g * 100, 1)
        r["qoq_legs"] = len(legs)
        r[out_key] = round(sum(legs) / len(legs) * 100, 1) if legs else None


# --------------------------------------------------------------------------
# Backfill
# --------------------------------------------------------------------------
# THE PROBLEM THIS SOLVES. The research cache is rebuilt by a SUNDAY cron and
# holds for 16 days (`research.CACHE_TTL_SEC`). Persisting the quarterly series
# in `canslim` only helps names refreshed AFTER that change — measured
# 2026-09-12, 0 of 250 board rows carried a series, so shipping the sequential
# read alone would have given him a blank column until the following Sunday and
# a half-filled one for two weeks after that.
#
# This fills the three series onto EXISTING cached documents without rebuilding
# research. It deliberately does NOT touch `cached_at`: bumping it would extend
# the life of stale fundamentals, which is the opposite of the point.
MAX_BACKFILL_WORKERS = 6


def _series_missing(doc: dict) -> bool:
    f = (doc or {}).get("fundamentals") or {}
    # A document with series but NO period keys is still "missing": it predates
    # the adjacency check and its pairs cannot be verified.
    if not (isinstance(f.get("q_period_series"), list) and f.get("q_period_series")):
        return True
    return not any(isinstance(f.get(k), list) and f.get(k)
                   for k in ("rev_q_series", "eps_q_series", "ni_q_series"))


def backfill(symbols: Optional[list] = None, *, limit: int = 0,
             only_missing: bool = True) -> dict:
    """Fetch and store the quarterly series for `symbols` (default: everything
    cached). Returns counts. Safe to re-run; safe to interrupt."""
    from concurrent.futures import ThreadPoolExecutor
    from sepa import canslim, research

    coll = research._get_cache()
    if coll is None:
        return {"ok": False, "reason": "no cache"}

    if symbols:
        want = [str(s).upper() for s in symbols]
        q = {"symbol": {"$in": want}}
    else:
        q = {}
    docs = list(coll.find(q, {"symbol": 1, "fundamentals.rev_q_series": 1,
                              "fundamentals.eps_q_series": 1,
                              "fundamentals.ni_q_series": 1}))
    todo = [d["symbol"] for d in docs if (_series_missing(d) or not only_missing)]
    if limit:
        todo = todo[:limit]

    filled = failed = 0

    def one(sym: str) -> bool:
        try:
            m = canslim._fetch_massive_financials(sym)
        except Exception as exc:                            # noqa: BLE001
            log.debug("qoq.backfill(%s) fetch failed: %s", sym, exc)
            return False
        if not m:
            return False
        sets = {f"fundamentals.{k}": m.get(k)
                for k in ("q_period_series", "rev_q_series", "eps_q_series",
                          "ni_q_series")
                if m.get(k)}
        if not sets:
            return False
        try:
            # `$set` of the three keys ONLY — `cached_at` is left alone so a
            # backfill can never make stale fundamentals look fresh.
            coll.update_one({"symbol": sym}, {"$set": sets})
            return True
        except Exception as exc:                            # noqa: BLE001
            log.debug("qoq.backfill(%s) write failed: %s", sym, exc)
            return False

    with ThreadPoolExecutor(max_workers=MAX_BACKFILL_WORKERS) as pool:
        for ok in pool.map(one, todo):
            if ok:
                filled += 1
            else:
                failed += 1

    return {"ok": True, "considered": len(docs), "attempted": len(todo),
            "filled": filled, "failed": failed}


# --------------------------------------------------------------------------
# Realign — the HEAL for documents cached before densify shipped
# --------------------------------------------------------------------------
# `align_reports` fixes every document written from now on. This walks the
# cache and fixes the ones already there, so the 164 mismatched rows land in
# the RIGHT place under today's rules instead of waiting for Sunday's refresh.
#
# WHAT IT WILL NOT DO. It never touches `cached_at` (bumping it would extend
# the life of stale fundamentals) and it never recomputes `earnings_quality`:
# that score needs the inventory and receivables series, and `inv_q_series` is
# not stored on the cache document at all (canslim.py copies only
# period/rev/eps/ni). The Sunday refresh realigns it through canslim.
#
# This PROMOTES NOTHING. A row whose year-ago quarter is genuinely absent
# becomes `headline_hole` → `sales.score None` → pending → still off the board.
def realign(symbols: Optional[list] = None, *, limit: int = 0,
            dry_run: bool = False) -> dict:
    """Re-align the stored quarterly series of every keyed cached document.

    `--dry-run` computes and reports the identical counts without a write —
    that dry run IS the re-tier measurement.
    """
    import time as _time

    from sepa import canslim, research, sales as _sales

    coll = research._get_cache()
    if coll is None:
        return {"ok": False, "reason": "no cache"}

    q = {}
    if symbols:
        q = {"symbol": {"$in": [str(s).upper() for s in symbols]}}
    proj = {"symbol": 1, "fundamentals.q_period_series": 1,
            "fundamentals.rev_q_series": 1, "fundamentals.eps_q_series": 1,
            "fundamentals.ni_q_series": 1, "fundamentals.sales": 1}
    docs = list(coll.find(q, proj))
    considered = len(docs)
    if limit:
        docs = docs[:limit]

    out = {"ok": True, "considered": considered, "keyed": 0, "realigned": 0,
           "unchanged": 0, "retier": {}, "headline_hole": 0, "prior_hole": 0,
           "duplicate_periods": 0, "reordered": 0, "dropped_unlabelled": 0,
           "dry_run": bool(dry_run)}

    for d in docs:
        f = (d.get("fundamentals") or {}) if isinstance(d, dict) else {}
        periods = f.get("q_period_series")
        if not (isinstance(periods, list) and any(
                _int_or_none(v) is not None for v in periods)):
            continue
        out["keyed"] += 1
        a = align_series(periods,
                         rev_q_series=f.get("rev_q_series"),
                         eps_q_series=f.get("eps_q_series"),
                         ni_q_series=f.get("ni_q_series"))
        if a["duplicate_periods"]:
            out["duplicate_periods"] += 1
        if a["reordered"]:
            out["reordered"] += 1
        if a["dropped_unlabelled"]:
            out["dropped_unlabelled"] += 1

        new_periods = a["q_period_series"]
        q_eps = yoy_pct(a["eps_q_series"])
        rev_g = yoy_pct(a["rev_q_series"])
        sales_new = _sales.compute(canslim._head8(a["rev_q_series"]), q_eps)
        hh = headline_hole(new_periods)
        ph = prior_hole(new_periods)
        out["headline_hole"] += 1 if hh else 0
        out["prior_hole"] += 1 if ph else 0

        old_tier = str(((f.get("sales") or {}) if isinstance(f.get("sales"), dict)
                        else {}).get("tier") or "unknown")
        new_tier = str(sales_new.get("tier") or "unknown")
        if new_periods == list(periods):
            out["unchanged"] += 1
            continue
        out["realigned"] += 1
        key = f"{old_tier}→{new_tier}"
        out["retier"][key] = out["retier"].get(key, 0) + 1
        if dry_run:
            continue
        sets = {
            "fundamentals.q_period_series": new_periods,
            "fundamentals.rev_q_series": a["rev_q_series"],
            "fundamentals.eps_q_series": a["eps_q_series"],
            "fundamentals.ni_q_series": a["ni_q_series"],
            "fundamentals.q_eps_growth_pct": q_eps,
            "fundamentals.rev_growth_q_pct": rev_g,
            "fundamentals.sales": sales_new,
            "fundamentals.headline_hole": hh,
            "fundamentals.prior_hole": ph,
            "fundamentals.realigned_at": _time.time(),
        }
        try:
            # `cached_at` is NOT in `sets` and never will be.
            coll.update_one({"symbol": d.get("symbol")}, {"$set": sets})
        except Exception as exc:                            # noqa: BLE001
            log.debug("qoq.realign(%s) write failed: %s", d.get("symbol"), exc)
            out["realigned"] -= 1
    return out


def snapshot(symbols: list) -> dict:
    """Sequential QoQ per symbol off the research cache — ONE projected read.

    Returns {} on failure and omits a symbol it cannot answer for; the board
    prints an em-dash for a miss and a miss never wins a sort.
    """
    try:
        from sepa import research
        snap = research.decision_snapshot(symbols) or {}
    except Exception as exc:                                # noqa: BLE001
        log.warning("qoq.snapshot failed: %s", exc)
        return {}
    out = {}
    for sym, f in snap.items():
        out[sym] = compute(f.get("rev_q_series"),
                           f.get("eps_q_series"),
                           f.get("ni_q_series"),
                           periods=f.get("q_period_series"))
    return out


# --------------------------------------------------------------------------
# CLI — `python -m sepa.qoq backfill [--limit N] [--all]`
# --------------------------------------------------------------------------
def _main(argv=None) -> int:
    import argparse
    import json as _json

    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd")

    b = sub.add_parser("backfill", help="fill the quarterly series on cached research")
    b.add_argument("--limit", type=int, default=0, help="cap the number of names")
    b.add_argument("--all", action="store_true",
                   help="re-fetch even names that already have a series")
    b.add_argument("--symbols", default="", help="comma-separated subset")

    c = sub.add_parser("coverage", help="how many cached names carry a series")

    r = sub.add_parser("realign",
                       help="densify the cached quarterly series by fiscal period")
    r.add_argument("--limit", type=int, default=0, help="cap the number of names")
    r.add_argument("--symbols", default="", help="comma-separated subset")
    r.add_argument("--dry-run", action="store_true",
                   help="compute and print the counts without writing")
    r.add_argument("--json", action="store_true", help="JSON only (default)")

    # A CLI process has no app startup, so the root redaction filter would not
    # be installed — and this command is the one that hammers a keyed endpoint.
    try:
        from observability.logsetup import install_redaction
        install_redaction()
    except Exception:                                       # noqa: BLE001
        pass

    a = ap.parse_args(argv)
    if a.cmd == "backfill":
        syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()] or None
        print(_json.dumps(backfill(syms, limit=a.limit, only_missing=not a.all)))
        return 0
    if a.cmd == "realign":
        syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()] or None
        print(_json.dumps(realign(syms, limit=a.limit, dry_run=a.dry_run)))
        return 0
    if a.cmd == "coverage":
        from sepa import research
        coll = research._get_cache()
        if coll is None:
            print('{"ok": false, "reason": "no cache"}')
            return 1
        total = coll.count_documents({})
        have = coll.count_documents({"fundamentals.rev_q_series": {"$type": "array"}})
        print(_json.dumps({"ok": True, "cached": total, "with_series": have,
                           "pct": round(have / total * 100, 1) if total else 0.0}))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":                                  # pragma: no cover
    raise SystemExit(_main())
