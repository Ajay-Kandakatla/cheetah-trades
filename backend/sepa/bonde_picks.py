"""📋 The Bonde PICK LINE — his STATIC criteria, each one a sentence he published.

Ajay 2026-09-20: *"I need bonde for stock picks rather than deciding to enter.
I decide based on supply and demand and also based on Momentum, but show me
other things like EPS, Sales and other things"* … and the correction that set
the scope: *"momentum does not need to be a criteria for his pics … i look at
momentum and others as dynamic info. I am looking fro static info"*.

So this module computes NOTHING dynamic. There is no return, no relative
strength, no persistence, no today's move — those are his entry inputs and they
stay on the boards that own them. What is here is the set of STATIC facts he
has written down about what he puts on a list, each carried with the verbatim
sentence, the URL and the date it was published.

THREE RULES THIS MODULE IS BUILT ON
───────────────────────────────────
1. A criterion exists here only if he wrote the sentence. His numbers are the
   module constants below and every one of them carries its cite on the same
   line. The app's own freshness labels are named as the app's (§7.15 of the
   spec) and never flip a verdict.
2. Every leg is TRI-STATE: True / False / None. `None` is UNKNOWN and is never
   a fail — a missing cache, an unverifiable fiscal pair and a year-ago loss
   are all "we cannot say", and a surface that renders them as ✗ is making a
   claim about a company off an absent row.
3. NOTHING HERE IS MEASURED. No leg is a signal, none of them gates, sorts or
   filters anything, and no count, ratio or score over the legs is rendered.
   The board's own thesis measured INVERTED (see `sepa/bonde.py::MEASURED`);
   this line is newer than that and has not been measured at all.

COST: the board path makes ZERO network calls. `legs_from_scan_row` is pure and
reads the scan row it is handed; `attach` makes five bulk Mongo reads over the
distinct symbols of the board and nothing else. It never raises — a reader that
is missing, empty or throwing leaves its legs UNKNOWN and the board is served.

The YouTube summary Ajay shared is NOT a source and nothing here is cited to
it. Full sourcing, per leg: docs/sepa/bonde_pick_list_2026_09_20.md.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from sepa.sales import SALES_FLOOR_PCT   # 2007 "Sales/revenue should be up 5% or more"
from sepa import qoq as Q                # period guard + yoy_pct + compute (MIN_EPS_BASE) + BASE_* names
from observability.period_freshness import FILING_LAG_DAYS, GRACE_DAYS   # Rule #7 constants by name

log = logging.getLogger("sepa.bonde_picks")

# ── his sources ────────────────────────────────────────────────────────────
URL_2007 = "https://stockbee.blogspot.com/2007/03/how-to-trade-earnings.html"
URL_2010 = "https://stockbee.blogspot.com/2010/02/what-are-episodic-pivots-and-how-to.html"
URL_2014 = "https://stockbee.blogspot.com/2014/07/my-process-flow-for-episodic-pivots-ep.html"
URL_2025 = "https://stockbee.blogspot.com/2025/09/find-young-episodic-pivots.html"
X_2024_06_13 = "https://x.com/PradeepBonde/status/1801220695197614404"
X_2023_01_25 = "https://x.com/PradeepBonde/status/1618245698008551424"
X_2023_11_12 = "https://x.com/PradeepBonde/status/1723676670924558778"
X_2023_12_04 = "https://x.com/PradeepBonde/status/1731652094283661602"
X_2021_08_13 = "https://x.com/PradeepBonde/status/1426157185168510979"

DATE_2007 = "2007-03-30"
DATE_2010 = "2010-02-12"
DATE_2014 = "2014-07-30"
DATE_2025 = "2025-09-01"

# ── HIS numbers, each with its cite on the same line ───────────────────────
EPS_MIN_USD = 0.05            # 2007 "the earnings should be at least 5 cents"
EPS_DOUBLING_PCT = 100.0      # 2007 "earnings are up 100% or more quarter over quarter"; 2010 "earnings acceleration of 100% plus"
FLOAT_IDEAL_MAX = 25_000_000  # 2010 "Float below 25 million is ideal"; X 2024-06-13 "under 25M shares"
FLOAT_BEST_MAX = 10_000_000   # 2010 "The best moves happen on float below 10 million"
FLOAT_PULLBACK_MIN = 100_000_000  # 2010 "100 million plus float tend to have pullbacks"
SHORT_DTC_MIN = 5.0           # X 2024-06-13 "high short interest ( 5 plus days to cover)"
IPO_MAX_YEARS = 10.0          # 2025 "Gone Public in the last 10 years"
CAP_MAX_USD = 10_000_000_000  # 2025 prose "less than $ 10 billion"; his scan line says "below 11 billion" — legend states both
REV_TWO_Q_PCT = 39.0          # 2025 "two quarters of revenue growth of 39% plus"
EP_SECTORS = ("Technology", "Healthcare", "Consumer Cyclical")  # X 2023-01-25; yfinance names consumer discretionary "Consumer Cyclical" (scan vocabulary, probed 2026-09-20)

# ── THIS APP'S freshness labels — never his, and they never flip `ok` ──────
QUARTER_DAYS = 91             # one fiscal quarter — THIS APP'S freshness label, not his
SURPRISE_STALE_DAYS = QUARTER_DAYS + FILING_LAG_DAYS + GRACE_DAYS   # = 157

PICK_HEADER = ("A pick list of his STATIC criteria — entries are yours (S&D, momentum). "
               "Each chip is one sentence he published, with its link. Nothing on the pick line "
               "is a signal, nothing on it is measured, and it gates, sorts and filters nothing.")

NOT_A_SOURCE = (
    "The YouTube summary is NOT a source: no criterion on this list is cited to "
    "it. Every quote here is from a post on stockbee.blogspot.com or from his own "
    "X account, with the date it was published."
)

WARM_NOTE = (
    "Short interest reads unknown on every row until "
    "`python -m short_interest.client warm-si` has run in the api container; "
    "a crontab line does not ship with a deploy."
)

# ── the ONE vocabulary of reasons a leg is UNKNOWN ────────────────────────
# Every served `why` is a member of this set; the frontend's WHY_TEXT keys are
# pinned equal to it by the contract sweep, so a code with no sentence beside
# it cannot reach the page.
WHY_CODES = frozenset({
    # scan-derived legs
    "no_eps_series", "year_ago_loss", "pair_not_a_year_apart", "no_period_keys", "prior_hole",
    "no_sales_read", "no_inst_read", "no_sector", "no_threshold_in_his_writing",
    # sequential base states, mapped from qoq BY NAME (never retyped)
    "seq_base_non_positive", "seq_base_too_small", "seq_base_unknown", "seq_not_adjacent",
    # cache-derived legs
    "not_on_calendar", "no_surprise_in_report",
    "no_metrics_doc", "no_float_in_doc", "no_cap_in_doc",
    "not_warmed", "no_si_record",
    "no_analyst_doc", "no_estimate_read",
    "no_listing_date", "future_listing_date",
})

# `sepa/qoq.py` owns the base states. They are mapped BY NAME here so a rename
# there is an ImportError, not a silently wrong sentence on his board.
INCOME_BASE_TO_WHY = {
    Q.BASE_NON_POSITIVE: "seq_base_non_positive",
    Q.BASE_TOO_SMALL:    "seq_base_too_small",
    Q.BASE_UNKNOWN:      "seq_base_unknown",
    Q.BASE_NOT_ADJACENT: "seq_not_adjacent",
}

# ── his sentences, verbatim, in one place ─────────────────────────────────
# Composed into CRITERIA below. A paraphrase anywhere fails the frozen quote
# test in backend/tests/test_bonde_picks.py.
S2007_EARNINGS = ("I only track companies whose earnings are up 100% or more quarter "
                  "over quarter and the earnings should be at least 5 cents.")
S2007_SALES = "Sales/revenue should be up 5% or more."
S2007_ACCEL = "Now what one is looking for is earnings acceleration."
S2007_NEGLECT = ("Even better is stock which has no analyst coverage and is "
                 "neglected.")
S2007_RUNUP = ("Besides that I look for price action on that stock by looking at "
               "how much they are up in last 65 days or so. I am looking for stocks "
               "which have not rallied in anticipation of earnings.")
S2007_SURPRISE = ("An earnings surprise on stock which has not rallied significantly "
                  "will lead to breakout next day.")
S2007_PEAD = ("PEAD or post earnings announcement drift is a well studied and proven "
              "market anomaly.")
S2010_YOY = ("On such stocks a significant earnings acceleration compared to last year "
             "same quarter as well as quarter over quarter is what to look for. I like "
             "to look for companies which had earnings acceleration of 100% plus in "
             "such cases.")
S2010_NEGLECT = "Stock with no analyst coverage"
S2010_FLOAT = ("Float below 25 million is ideal for this. The best moves happen on "
               "float below 10 million. Earnings breakouts on companies with 100 "
               "million plus float tend to have pullbacks.")
S2010_BEATS = "Beats analyst estimate"
S2010_TOP_SECTOR = "In top 10 sector"
S2010_TOP_SECTOR_CAT = "Top Sector"
S2010_EARNINGS_40 = "Earnings 40% plus"
S2014_MARKETSMITH = "Marketsmith to find earnings and earnings trends, float, fund holding"
S2025_YOUNG = ("The most explosive Episodic Pivots occur in stocks that have Gone "
               "Public in the last 10 years and have a capitalization of less than "
               "$ 10 billion once they enter their growth phase.")
S2025_LOW_FUND = ("They will have very low capitalization, low fund ownership, and low "
                  "interest from analysts and general investors.")
S2025_SCAN = ("This scan finds stocks incorporated or IPOed in last 10 years that have "
              "a market capitalization below 11 billion and have two quarters of "
              "revenue growth of 39% plus.")
X2024_FLOAT = ("Stocks with lower floats (under 25M shares) tend to see the biggest "
               "episodic pivot moves … This coupled with high short interest ( 5 plus "
               "days to cover) can result in explosive moves")
X2023_SECTORS = ("If you want to make money from Earnings Episodic Pivots, focus on "
                 "three sectors: technology, healthcare, and consumer discretionary.")
X2023_STORY = ("there is 100 times more money on story stocks EP … Understanding what "
               "theme is working and finding story EP in them is now my major focus")
X2023_PEAD = ("Post earnings announcements drift is well known markrt anomaly and EP is "
              "based on that.")
X2021_REACTOR = ("Keep a watchlist of stocks that reacted positively to earnings "
                 "(earnings Episodic Pivots) , they always offer another lower risk "
                 "entry opportunity after few weeks or months.")

_JOIN = " · "


def _q(*sentences) -> str:
    """One quote field, built only from the verbatim sentences above."""
    return _JOIN.join(sentences)


# ── the criteria, one entry per line on his list ──────────────────────────
# `computed` False means the criterion is his but this board does not compute
# it; `not_computed_why` says why, and the legend prints it rather than
# pretending the list is shorter than his.
CRITERIA = [
    {"key": "eps_5c", "label": "EPS ≥ 5¢",
     "quote": S2007_EARNINGS, "url": URL_2007, "date": DATE_2007, "source": "stockbee",
     "data": "Latest quarterly EPS off the scan row's filings (sepa/qoq.compute).",
     "computed": True, "not_computed_why": None, "his_call": None},
    {"key": "eps_yoy_100", "label": "EPS ≥ +100% y/y",
     "quote": S2010_YOY, "url": URL_2010, "date": DATE_2010, "source": "stockbee",
     "data": "Latest quarter against the SAME quarter a year earlier (sepa/qoq.yoy_pct), "
             "only when the year-ago quarter made money.",
     "computed": True, "not_computed_why": None, "his_call": None},
    {"key": "eps_seq_100", "label": "EPS ≥ +100% q/q",
     "quote": S2007_EARNINGS, "url": URL_2007, "date": DATE_2007, "source": "stockbee",
     "data": "Latest quarter against the quarter before it (sepa/qoq.compute), refused "
             "when the two filings are not consecutive quarters.",
     "computed": True, "not_computed_why": None, "his_call": None},
    {"key": "eps_accel", "label": "Earnings accelerating",
     "quote": _q(S2007_ACCEL, S2010_YOY), "url": URL_2007, "date": DATE_2007,
     "source": "stockbee",
     "data": "This quarter's y/y EPS growth against the previous quarter's y/y EPS "
             "growth. EARNINGS acceleration — the sales flags on this board are the "
             "app's own read.",
     "computed": True, "not_computed_why": None, "his_call": None},
    {"key": "sales_5", "label": "Sales ≥ 5% y/y",
     "quote": S2007_SALES, "url": URL_2007, "date": DATE_2007, "source": "stockbee",
     "data": "The pillar's own rounded seam against SALES_FLOOR_PCT "
             "(sepa/buyable_verdict._bonde_pillar). ✓ on every row the board draws, by "
             "construction.",
     "computed": True, "not_computed_why": None, "his_call": None},
    {"key": "surprise", "label": "Earnings surprise",
     "quote": _q(S2010_BEATS, S2007_SURPRISE), "url": URL_2010, "date": DATE_2010,
     "source": "stockbee",
     "data": "The most recent reported quarter in the `earnings_calendar` cache "
             "(sepa/earnings_watch), as a percent. Labelled stale past "
             "%d days; the label never changes the verdict." % SURPRISE_STALE_DAYS,
     "computed": True, "not_computed_why": None,
     "his_call": "A beat is any surprise above zero here. \"Earnings Beats by wide "
                 "margin\" carries no number, so whether a magnitude floor should "
                 "apply is Ajay's call."},
    {"key": "float_25m", "label": "Float < 25M",
     "quote": _q(S2010_FLOAT, X2024_FLOAT), "url": URL_2010, "date": DATE_2010,
     "source": "stockbee",
     "data": "yfinance `floatShares`, cached in `board_metrics`. Unknown until "
             "`python -m sepa.board_metrics warm --all` has refreshed the doc.",
     "computed": True, "not_computed_why": None, "his_call": None},
    {"key": "short_dtc_5", "label": "Days to cover ≥ 5",
     "quote": X2024_FLOAT, "url": X_2024_06_13, "date": "2024-06-13", "source": "x",
     "data": "FINRA short interest via Massive, cached in `short_interest_latest`. "
             "Unknown on every row until the warm has run.",
     "computed": True, "not_computed_why": None,
     "his_call": "The warm cadence and its crontab line are Ajay's call; the crontab "
                 "is host-mounted and a deploy does not ship it."},
    {"key": "neglect_analysts", "label": "No analyst coverage",
     "quote": _q(S2007_NEGLECT, S2010_NEGLECT), "url": URL_2007, "date": DATE_2007,
     "source": "stockbee",
     "data": "The count of analysts on Yahoo's current-quarter estimate row, cached in "
             "`analyst_pulse`. Yahoo never prints a zero — an EMPTY estimate frame is "
             "the only evidence of no coverage.",
     "computed": True, "not_computed_why": None,
     "his_call": "Reading an empty Yahoo estimate frame as his \"no analyst coverage\" "
                 "is a reading pending Ajay's nod, and whether a small count (say ≤2) "
                 "should also read as neglected is his call — his words give no number."},
    {"key": "fund_holding", "label": "Fund holding",
     "quote": _q(S2014_MARKETSMITH, S2025_LOW_FUND), "url": URL_2014, "date": DATE_2014,
     "source": "stockbee",
     "data": "Institutional ownership from the scan row (yfinance "
             "`heldPercentInstitutions`) — a 13F LEVEL, never a flow.",
     "computed": True,
     "not_computed_why": None,
     "his_call": "He names fund holding as something he looks at and gives no number, "
                 "so this leg is always shown as a fact and never as a pass or a fail."},
    {"key": "ipo_10y", "label": "IPO ≤ 10y",
     "quote": S2025_YOUNG, "url": URL_2025, "date": DATE_2025, "source": "stockbee",
     "data": "Listing date from the `ipo_dates` cache (Finnhub profile), uncorroborated.",
     "computed": True, "not_computed_why": None,
     "his_call": "It is the least-corroborated leg — 21.4% of profile dates on this "
                 "universe are recycled tickers, which reads as a falsely young ✓. "
                 "Whether it stays among the chips is Ajay's call."},
    {"key": "cap_10b", "label": "Cap < $10B",
     "quote": _q(S2025_YOUNG, S2025_SCAN), "url": URL_2025, "date": DATE_2025,
     "source": "stockbee",
     "data": "yfinance `marketCap`, cached in `board_metrics`.",
     "computed": True, "not_computed_why": None,
     "his_call": "His prose says less than $10 billion and his scan line in the same "
                 "post says below 11 billion. This leg passes at the prose bound; "
                 "which one to use is Ajay's call."},
    {"key": "rev_39_x2", "label": "Revenue ≥ 39% ×2",
     "quote": S2025_SCAN, "url": URL_2025, "date": DATE_2025, "source": "stockbee",
     "data": "This quarter's and the previous quarter's revenue growth, read here as "
             "year over year — his post does not say which base.",
     "computed": True, "not_computed_why": None,
     "his_call": "This figure is his. Whether it joins or replaces a sales TIER on this "
                 "board is Ajay's call; nothing about the tiers moved."},
    {"key": "sector_3", "label": "His three EP sectors",
     "quote": X2023_SECTORS, "url": X_2023_01_25, "date": "2023-01-25", "source": "x",
     "data": "The scan row's sector, in yfinance vocabulary — consumer discretionary is "
             "named \"Consumer Cyclical\" there. A FACT about the name, not a gate.",
     "computed": True, "not_computed_why": None, "his_call": None},

    # ── his, and NOT computed here ────────────────────────────────────────
    {"key": "run_up_65d", "label": "Has not rallied into earnings",
     "quote": S2007_RUNUP, "url": URL_2007, "date": DATE_2007, "source": "stockbee",
     "data": "Not computed here.",
     "computed": False,
     "not_computed_why": "It is a PRICE read over 65 days, and the correction that "
                         "shaped this line asked for static information only.",
     "his_call": "Whether a 65-day run-up number belongs on the row is Ajay's call."},
    {"key": "story_ep", "label": "Story / theme EP",
     "quote": X2023_STORY, "url": X_2023_11_12, "date": "2023-11-12", "source": "x",
     "data": "Not computed here.",
     "computed": False,
     "not_computed_why": "There is no feed that decides whether a name is a story "
                         "stock, and inventing one would be this app's judgement "
                         "wearing his words.",
     "his_call": None},
    {"key": "pead", "label": "Post-earnings drift",
     "quote": _q(S2007_PEAD, X2023_PEAD), "url": URL_2007, "date": DATE_2007,
     "source": "stockbee",
     "data": "Not computed here.",
     "computed": False,
     "not_computed_why": "It is the anomaly his whole method rests on, not a per-name "
                         "screen: there is nothing to tick on a row.",
     "his_call": None},
    {"key": "reactor_watchlist", "label": "Reacted well to earnings",
     "quote": X2021_REACTOR, "url": X_2021_08_13, "date": "2021-08-13", "source": "x",
     "data": "Not computed here.",
     "computed": False,
     "not_computed_why": "It is a watchlist he keeps over weeks and months, and the "
                         "reaction is a price read — dynamic, so out of scope for this "
                         "line.",
     "his_call": None},
    {"key": "top_sector", "label": "Top sector",
     "quote": _q(S2010_TOP_SECTOR_CAT, S2010_TOP_SECTOR), "url": URL_2010,
     "date": DATE_2010, "source": "stockbee",
     "data": "Not computed here.",
     "computed": False,
     "not_computed_why": "No sector RANK feed reaches this board, and the app's own "
                         "rotation read is a different concept with its own page.",
     "his_call": None},
    {"key": "earnings_40", "label": "Earnings 40% plus",
     "quote": S2010_EARNINGS_40, "url": URL_2010, "date": DATE_2010, "source": "stockbee",
     "data": "Not computed here.",
     "computed": False,
     "not_computed_why": "It is one entry in his catalogue of EP catalyst CATEGORIES, "
                         "not a screen number he says he runs: he writes that he only "
                         "focuses on the 100%-plus names.",
     "his_call": None},
]

COMPUTED_KEYS = [c["key"] for c in CRITERIA if c["computed"]]
LEGEND_ONLY_KEYS = [c["key"] for c in CRITERIA if not c["computed"]]
# The eight legs that come off the scan row, and the six that come off a cache.
SCAN_KEYS = ("eps_5c", "eps_yoy_100", "eps_seq_100", "eps_accel", "sales_5",
             "rev_39_x2", "fund_holding", "sector_3")
CACHE_KEYS = ("surprise", "float_25m", "cap_10b", "short_dtc_5",
              "neglect_analysts", "ipo_10y")

_CRIT_BY_KEY = {c["key"]: c for c in CRITERIA}
# The y/y legs: a fiscal pair that is NOT a year apart makes every one of them
# unknown, whatever number the row still carries.
_YOY_KEYS = ("eps_yoy_100", "eps_accel", "sales_5", "rev_39_x2")


# ── helpers ───────────────────────────────────────────────────────────────
def _f(v) -> Optional[float]:
    """A JSON-clean float or None — NaN and infinities never reach a payload."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (f != f or f in (float("inf"), float("-inf"))) else f


def _leg(ok=None, value=None, why=None, **extra) -> dict:
    """One leg, always with all three keys.

    `why` is checked against `WHY_CODES` here rather than at the edge, so a code
    invented in a hurry fails in this module's own tests instead of arriving on
    the page as an untranslated token.
    """
    if why is not None and why not in WHY_CODES:
        raise ValueError("unknown why code: %r" % (why,))
    leg = {"ok": ok, "value": value, "why": why}
    leg.update(extra)
    return leg


def _today() -> date:
    return date.today()


def _parse_date(v) -> Optional[date]:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v or "")[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _series(fundamentals: dict, key: str) -> list:
    s = fundamentals.get(key) if isinstance(fundamentals, dict) else None
    return list(s) if isinstance(s, list) else []


def _positive_base_yoy(eps: list, i: int):
    """(value, why) for a y/y EPS leg at slot `i`.

    `qoq.yoy_pct` divides by |base|, so −0.20 → +0.30 comes back as +250% — a
    sign flip rendered as a ramp. A y/y EPS leg therefore REQUIRES a positive
    year-ago base; a loss is UNKNOWN, never a tick. The loss-to-profit fact
    still travels, on the sequential leg, as `income_turn`.
    """
    j = i + Q.YOY_GAP
    if len(eps) <= j:
        return None, "no_eps_series"
    base = _f(eps[j])
    cur = _f(eps[i])
    if base is None or cur is None:
        return None, "no_eps_series"
    if base <= 0:
        return None, "year_ago_loss"
    return Q.yoy_pct(eps, i), None


# ── the scan-derived legs ─────────────────────────────────────────────────
def legs_from_scan_row(scan_row: dict, pillar: dict, row: dict,
                       cleared_floor: Optional[bool]) -> dict:
    """The eight legs that need nothing but the scan row. PURE.

    `cleared_floor` is passed IN rather than imported, because `sepa/bonde.py`
    owns the rounded seam `_bonde_pillar` uses and this module must never import
    the board (that would be the cycle bonde → bonde_picks → bonde).
    """
    fundamentals = scan_row.get("fundamentals") or {}
    eps = _series(fundamentals, "eps_q_series")
    periods = fundamentals.get("q_period_series") if isinstance(fundamentals, dict) else None
    periods = periods if isinstance(periods, list) else None
    pillar = pillar or {}
    row = row or {}

    period_ok = row.get("period_ok")
    # `period_ok False` = the pair was CHECKED and is not four quarters apart.
    # `period_ok None` = it could not be checked at all — the number is still
    # computed and the surface says `unverified` beside it.
    pair_refused = period_ok is False
    unverified = "no_period_keys" if period_ok is None else None
    prior_hole = bool(row.get("prior_hole"))

    q = Q.compute(eps_series=eps, periods=periods)
    has_eps = any(x is not None for x in eps)

    legs: dict = {}

    # EPS ≥ 5¢ — sequential in his sentence, but it is a LEVEL, so the fiscal
    # pair has nothing to do with it.
    eps_latest = _f(q.get("eps_latest"))
    if not has_eps or eps_latest is None:
        legs["eps_5c"] = _leg(why="no_eps_series")
    else:
        legs["eps_5c"] = _leg(ok=eps_latest >= EPS_MIN_USD, value=eps_latest)

    # EPS ≥ +100% y/y — his 2010 leg ("compared to last year same quarter").
    if not has_eps:
        legs["eps_yoy_100"] = _leg(why="no_eps_series")
    elif pair_refused:
        legs["eps_yoy_100"] = _leg(why="pair_not_a_year_apart")
    else:
        v, why = _positive_base_yoy(eps, 0)
        if why or v is None:
            legs["eps_yoy_100"] = _leg(why=why or "no_eps_series")
        else:
            legs["eps_yoy_100"] = _leg(ok=v >= EPS_DOUBLING_PCT, value=v,
                                       why=unverified)

    # EPS ≥ +100% q/q — his 2007 leg ("quarter over quarter"). Sequential, so
    # the YoY pair guard does not apply; `qoq` refuses a non-adjacent pair.
    income_base = q.get("income_base")
    if not has_eps:
        legs["eps_seq_100"] = _leg(why="no_eps_series")
    elif income_base != Q.BASE_OK:
        legs["eps_seq_100"] = _leg(why=INCOME_BASE_TO_WHY.get(income_base,
                                                              "seq_base_unknown"),
                                   value_note=q.get("income_turn"))
    else:
        v = _f(q.get("income_qoq_pct"))
        if v is None:
            legs["eps_seq_100"] = _leg(why="seq_base_unknown")
        else:
            legs["eps_seq_100"] = _leg(ok=v >= EPS_DOUBLING_PCT, value=v,
                                       value_note=q.get("income_turn"))

    # Earnings acceleration — HIS acceleration is the earnings one.
    if not has_eps:
        legs["eps_accel"] = _leg(why="no_eps_series")
    elif pair_refused:
        legs["eps_accel"] = _leg(why="pair_not_a_year_apart")
    elif prior_hole:
        legs["eps_accel"] = _leg(why="prior_hole")
    else:
        now, why_now = _positive_base_yoy(eps, 0)
        prior, why_prior = _positive_base_yoy(eps, 1)
        why = why_now or why_prior
        if why or now is None or prior is None:
            legs["eps_accel"] = _leg(why=why or "no_eps_series")
        else:
            legs["eps_accel"] = _leg(ok=now > prior,
                                     value={"now": now, "prior": prior},
                                     why=unverified)

    # Sales ≥ 5% — read off the pillar's own rounded seam, never re-derived.
    # The row is the authority: `bonde.board` BLANKS `growth_yoy_pct` on a row
    # whose fiscal pair it refused, and an explicit None there must stay None.
    # The pillar is only the fallback for a caller that handed no such key.
    growth = (_f(row.get("growth_yoy_pct")) if "growth_yoy_pct" in row
              else _f(pillar.get("growth_yoy_pct")))
    if pair_refused:
        legs["sales_5"] = _leg(why="pair_not_a_year_apart")
    elif cleared_floor is None or growth is None:
        legs["sales_5"] = _leg(why="no_sales_read", value=growth)
    else:
        legs["sales_5"] = _leg(ok=bool(cleared_floor), value=growth,
                               why=unverified,
                               value_note="against his %g%% floor" % SALES_FLOOR_PCT)

    # Revenue ≥ 39% twice — his 2025 scan line.
    prior_growth = _f(row.get("prior_yoy_pct"))
    if pair_refused:
        legs["rev_39_x2"] = _leg(why="pair_not_a_year_apart")
    elif growth is None:
        legs["rev_39_x2"] = _leg(why="no_sales_read")
    elif prior_hole or prior_growth is None:
        legs["rev_39_x2"] = _leg(why="prior_hole",
                                 value={"now": growth, "prior": None})
    else:
        legs["rev_39_x2"] = _leg(
            ok=(growth >= REV_TWO_Q_PCT and prior_growth >= REV_TWO_Q_PCT),
            value={"now": growth, "prior": prior_growth}, why=unverified,
            value_note="read here as y/y — his post does not say which base")

    # Fund holding — a FACT he looks at. He publishes no number, so this leg
    # has no pass state at all and says so rather than inventing one.
    inst = _f(fundamentals.get("inst_ownership_pct")
              if isinstance(fundamentals, dict) else None)
    if inst is None:
        legs["fund_holding"] = _leg(why="no_inst_read")
    else:
        legs["fund_holding"] = _leg(ok=None, value=inst,
                                    why="no_threshold_in_his_writing",
                                    source="13F level via yfinance (never a flow)")

    # His three earnings-EP sectors.
    sector = scan_row.get("sector")
    sector = str(sector).strip() if sector else None
    if not sector:
        legs["sector_3"] = _leg(why="no_sector")
    else:
        legs["sector_3"] = _leg(ok=sector in EP_SECTORS, value=sector,
                                value_note="a fact about the name, not a gate")

    return legs


# ── the cache-derived legs ────────────────────────────────────────────────
def _read(module_path: str, func: str, *args, **kw):
    """Call one bulk reader, lazily imported, and answer {} for any failure.

    The imports live here and not at module scope on purpose: `short_interest.
    client._main` imports `sepa.bonde`, which imports this module, so a
    top-level import in either direction closes a cycle.
    """
    try:
        mod = __import__(module_path, fromlist=["*"])
        fn = getattr(mod, func, None)
        if fn is None:
            log.debug("bonde_picks: %s.%s not available yet", module_path, func)
            return {}
        out = fn(*args, **kw)
        return out if isinstance(out, dict) else {}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("bonde_picks: %s.%s failed: %s", module_path, func, exc)
        return {}


def attach(rows: list, db=None) -> list:
    """Fill the six cache legs on every row, in place. NEVER raises.

    Five bulk Mongo reads over the DISTINCT symbols and no network at all: this
    runs inside `bonde.board()`, which crons call, and a board that costs a
    provider read per row is a board that stops being served.
    """
    rows = rows or []
    syms = sorted({str(r.get("symbol") or "").upper()
                   for r in rows if r.get("symbol")})
    if not syms:
        for r in rows:
            _count(r)
        return rows

    metrics = _read("sepa.board_metrics", "snapshot", syms, db=db)
    reports = _read("sepa.earnings_watch", "last_report_map", syms)
    si = _read("short_interest.client", "short_interest_map", syms, db=db)
    analysts = _read("sepa.analyst_pulse", "coverage_map", syms)
    listings = _read("sepa.ipo_age", "listing_dates_map", syms)
    today = _today()

    for r in rows:
        sym = str(r.get("symbol") or "").upper()
        pick = r.get("pick")
        if not isinstance(pick, dict):
            pick = {"legs": {}}
            r["pick"] = pick
        legs = pick.setdefault("legs", {})
        try:
            legs["surprise"] = _surprise_leg(reports.get(sym), today)
            legs["float_25m"] = _float_leg(metrics.get(sym))
            legs["cap_10b"] = _cap_leg(metrics.get(sym))
            legs["short_dtc_5"] = _si_leg(si.get(sym))
            legs["neglect_analysts"] = _analyst_leg(analysts.get(sym))
            legs["ipo_10y"] = _ipo_leg(listings.get(sym), today)
        except Exception as exc:                               # noqa: BLE001
            log.warning("bonde_picks: %s legs failed: %s", sym, exc)
        _count(r)
    return rows


def _count(row: dict) -> None:
    """n_pass / n_fail / n_unknown over all 14 computed legs.

    SERVED for the doc and `coverage()` and rendered NOWHERE: a count over legs
    that were never measured together is a synthesized rank, and the pick line
    is a list of cited facts, not a score.
    """
    legs = ((row.get("pick") or {}).get("legs") or {}) if isinstance(row, dict) else {}
    n_pass = n_fail = n_unknown = 0
    for k in COMPUTED_KEYS:
        ok = (legs.get(k) or {}).get("ok")
        if ok is True:
            n_pass += 1
        elif ok is False:
            n_fail += 1
        else:
            n_unknown += 1
    pick = row.setdefault("pick", {"legs": legs})
    pick["n_pass"], pick["n_fail"], pick["n_unknown"] = n_pass, n_fail, n_unknown


def _surprise_leg(rep: Optional[dict], today: date) -> dict:
    if not rep:
        return _leg(why="not_on_calendar")
    sp = _f(rep.get("surprise_pct"))
    if sp is None:
        return _leg(why="no_surprise_in_report", as_of=rep.get("date"))
    d = _parse_date(rep.get("date"))
    age = (today - d).days if d else None
    # A LABEL, never a verdict: Rule #7 is about the reported PERIOD, and a
    # beat two quarters ago is still the last thing he had to react to.
    stale = (age > SURPRISE_STALE_DAYS) if age is not None else None
    return _leg(ok=sp > 0, value=sp, as_of=(d.isoformat() if d else None),
                age_days=age, stale=stale,
                source="earnings_calendar (sepa/earnings_watch)")


def _float_leg(m: Optional[dict]) -> dict:
    if not m:
        return _leg(why="no_metrics_doc")
    fs = _f(m.get("float_shares"))
    if fs is None:
        return _leg(why="no_float_in_doc")
    if fs < FLOAT_BEST_MAX:
        tier = "best"
    elif fs < FLOAT_IDEAL_MAX:
        tier = "ideal"
    elif fs >= FLOAT_PULLBACK_MIN:
        tier = "pullback_prone"
    else:
        tier = None
    return _leg(ok=fs < FLOAT_IDEAL_MAX, value=fs, tier=tier,
                source="yfinance floatShares")


def _cap_leg(m: Optional[dict]) -> dict:
    if not m:
        return _leg(why="no_metrics_doc")
    mc = _f(m.get("market_cap"))
    if mc is None:
        return _leg(why="no_cap_in_doc")
    return _leg(ok=mc < CAP_MAX_USD, value=mc, source="yfinance marketCap")


def _si_leg(d: Optional[dict]) -> dict:
    if not d:
        return _leg(why="not_warmed")
    settle = d.get("settlement_date")
    dtc = _f(d.get("days_to_cover"))
    if settle is None or dtc is None:
        # A doc with no settlement date is a REMEMBERED miss — the warm ran and
        # the provider had nothing. Not the same answer as "never warmed".
        return _leg(why="no_si_record")
    return _leg(ok=dtc >= SHORT_DTC_MIN, value=dtc,
                as_of=str(settle)[:10],
                stale=d.get("stale"), age_days=d.get("age_days"),
                pct_of_shares=_f(d.get("pct_of_shares")),
                source="FINRA short interest via Massive")


def _analyst_leg(a: Optional[dict]) -> dict:
    if not a:
        return _leg(why="no_analyst_doc")
    n = a.get("n_analysts")
    try:
        n = int(n) if n is not None else None
    except (TypeError, ValueError):
        n = None
    if n is None:
        return _leg(why="no_estimate_read")
    if n == 0:
        # Yahoo never prints a zero. An EMPTY estimate frame is the only
        # evidence of no coverage there is, and reading it as his "no analyst
        # coverage" is a reading, labelled as one.
        return _leg(ok=True, value=0, source="Yahoo carries no estimate rows",
                    his_call=_CRIT_BY_KEY["neglect_analysts"]["his_call"])
    return _leg(ok=False, value=n, value_note="covered by %d" % n,
                source="Yahoo estimate row (analyst_pulse)")


def _ipo_leg(listing, today: date) -> dict:
    d = _parse_date(listing)
    if d is None:
        return _leg(why="no_listing_date")
    if d > today:
        return _leg(why="future_listing_date", as_of=d.isoformat())
    years = round((today - d).days / 365.25, 1)
    return _leg(ok=years <= IPO_MAX_YEARS, value=years, as_of=d.isoformat(),
                source="Finnhub profile date, uncorroborated (21.4% of profile "
                       "dates on this universe are recycled tickers)")


# ── what the page is handed ───────────────────────────────────────────────
def legend() -> dict:
    """The legend, served once. The component renders what it is handed — no
    sentence of his is ever typed into TSX."""
    return {
        "header": PICK_HEADER,
        "criteria": CRITERIA,
        "computed_keys": list(COMPUTED_KEYS),
        "why_codes": sorted(WHY_CODES),
        "not_a_source": NOT_A_SOURCE,
        "warm_note": WARM_NOTE,
    }


def coverage(rows: list) -> dict:
    """{leg_key: {known, rows}} — the one sentence that says what is UNKNOWN.

    A board of em-dashes with no explanation reads as broken; a board that says
    "float known on 169 of 199" reads as honest.
    """
    rows = rows or []
    out = {k: {"known": 0, "rows": 0} for k in COMPUTED_KEYS}
    for r in rows:
        legs = ((r.get("pick") or {}).get("legs") or {})
        for k in COMPUTED_KEYS:
            out[k]["rows"] += 1
            if (legs.get(k) or {}).get("ok") is not None:
                out[k]["known"] += 1
    return out
