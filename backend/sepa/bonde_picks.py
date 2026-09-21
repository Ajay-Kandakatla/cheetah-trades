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

The third-party YouTube summary was never a source. The interview itself
(received 2026-09-20) IS one: tape quotes are cited by timestamp from the
caption track, and their frozen set is
backend/tests/fixtures/bonde_video_captions_2026_09_20.json. Full sourcing, per
leg: docs/sepa/bonde_pick_list_2026_09_20.md.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from sepa.sales import SALES_FLOOR_PCT   # 2007 "Sales/revenue should be up 5% or more"
from sepa import qoq as Q                # period guard + yoy_pct + compute (MIN_EPS_BASE) + BASE_* names
from observability.period_freshness import FILING_LAG_DAYS, GRACE_DAYS   # Rule #7 constants by name
from supply_demand.sectors import SECTORS, sectors_for_ticker   # the app's own theme map — typing-only module, no I/O

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

# ── the interview, received 2026-09-20 ─────────────────────────────────────
# His own voice on a caption track, cited by the second it starts. The host's
# turns are never quoted here; the frozen caption set lives in
# backend/tests/fixtures/bonde_video_captions_2026_09_20.json.
TAPE_URL = "https://www.youtube.com/watch?v=fjox2hapu98"
TAPE_TITLE = "Trading Legend: His Strategy Has Made the MOST Millionaire Traders - StockBee"
TAPE_SHOW = "Words of Rizdom"
TAPE_DATE = "2026-02-18"        # published (Apple Podcasts episode page, read 2026-09-20)
TAPE_RECORDED = "~June 2025"    # his words at [1:05:11]: "the last month is over May"
TAPE_RECEIVED = "2026-09-20"
TAPE_SOURCE = "tape"

# `sepa/sales.py` counts the revenue-growth streak with a literal loop bound of
# four quarters. That file is book-cited and guarded, so the bound is NAMED
# here and pinned equal to `sales.compute`'s own behaviour by a test — it is
# never used to compute anything, only to SAY that four means "four or more".
STREAK_CAP = 4

# The app's theme map, derived at import from `supply_demand.sectors.SECTORS`
# so the size printed on his board can never drift from the roster itself.
THEME_MAP_TICKERS = frozenset(t for s in SECTORS for t in (s.get("sp_tickers") or []))
THEME_UNMAPPED = "not on the app's map"

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
    "The third-party YouTube SUMMARY was never a source and nothing from it is "
    "cited. The INTERVIEW itself (Words of Rizdom, published 2026-02-18, "
    "recorded ~June 2025, received 2026-09-20) is cited by timestamp: every tape "
    "quote is his own words from the caption track, linked at the second it "
    "starts. Everything else is a post on stockbee.blogspot.com or his own X "
    "account, with its date."
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
    # the theme map needs a symbol to look up
    "no_symbol",
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


# ── his sentences on tape, verbatim ───────────────────────────────────────
# Straight apostrophes exactly as captioned; "written down" is the caption's
# hearing of "beaten down" and stays. The " … " in T_CHART_NOT_SETUP is the one
# permitted elision (the same convention as X2024_FLOAT). Every one of these is
# checked against the frozen caption fixture by the test module.
T_TURNAROUND = ("0:11:22",
                "I have a specific setup of turnaround stocks where I know based on "
                "their history that it can be held for a little longer than the growth "
                "stock")
T_VALUATION = ("0:12:54",
               "But if I have to do longerterm trading, I will base lot of my "
               "longerterm trading on a setup which is very very analysis based, which "
               "is based on valuation, which is based on projecting how many quarters "
               "in a row that stock is likely to have a growth.")
T_STREAK = ("0:13:00",
            "which is based on projecting how many quarters in a row that stock is "
            "likely to have a growth")
T_CHART_NOT_SETUP = ("0:14:17",
                     "a good chart itself is not a setup … they don't go up just "
                     "because there is a pretty good chart or support or resistance")
T_REASON = ("0:14:33",
            "that reason must be might be theme That might be sector that might be "
            "whatever earnings catalyst story but the that particular stock should "
            "have a reason to go up")
T_BEATEN_DOWN = ("0:27:04",
                 "Now I tended to believe this when I was new in the market right till "
                 "I actually checked it out and when I checked it out I found that "
                 "actually the stock which make the biggest move are the one which were "
                 "written down the most right")
T_ORIGIN_300 = ("0:48:59",
                "the earnings is like phenomenally good 300 400 500%. Then those stocks "
                "can double or triple.")
T_NEWSPAPER = ("0:49:23",
               "And I opened the newspaper. It used to have the list of stocks which "
               "are released earnings last night.")
T_USLB = ("0:49:28",
          "And there was this small stock called USLB. At that time it was called US "
          "laboratories. And that had come out with earnings and the sales growth was "
          "some 900% and the profit was 2,600%.")
T_EP_BORN = ("0:49:55",
             "And that changed how that became the EP kind of an idea then.")
T_MARKET_LIKES = ("1:04:32",
                  "So take the first point right and which is you have to trade what is "
                  "in the market likes right")
T_LAST_MONTH = ("1:05:11", "the last month is over May")
T_VOLUME_9M = ("1:05:52",
               "that is why I use the 9 million volume because I know volume is a "
               "object effective way to find where the crowd is")
T_IN_PLAY = ("1:06:50",
             "today if you have to make money what is in play AI uh robotics humanoid "
             "robotics or like crypto wallets or things like that")
T_SECTORS = ("1:07:04",
             "I have seen that over any time period of last 24 years 25 years right "
             "there are three sectors where the biggest money is in the market. "
             "Technology, biotechnology or healthcare related stock and third is "
             "consumer discretionary.")
T_SECTORS_EXCL = ("1:07:17",
                  "You can get rid of everything else if you really want to make money.")
T_SECTORS_RANK = ("1:07:22",
                  "once in a while you'll have gold stocks making money. once in a "
                  "while you're a uranium stock making money but just trading technology "
                  "stock is where the money is.")

TAPE_SENTENCES = (T_TURNAROUND, T_VALUATION, T_STREAK, T_CHART_NOT_SETUP, T_REASON,
                  T_BEATEN_DOWN, T_ORIGIN_300, T_NEWSPAPER, T_USLB, T_EP_BORN,
                  T_MARKET_LIKES, T_LAST_MONTH, T_VOLUME_9M, T_IN_PLAY, T_SECTORS,
                  T_SECTORS_EXCL, T_SECTORS_RANK)


def _ts_seconds(ts: str) -> int:
    """"h:mm:ss" (or "m:ss") -> seconds. Anything else is a ValueError.

    A hand-typed deep link that lands a minute off quotes him from the wrong
    sentence, so the seconds are never written by hand anywhere in this module.
    """
    parts = str(ts).split(":")
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        raise ValueError("not a timestamp: %r" % (ts,))
    nums = [int(p) for p in parts]
    if len(nums) == 2:
        nums = [0] + nums
    h, m, s = nums
    if m > 59 or s > 59:
        raise ValueError("not a timestamp: %r" % (ts,))
    return h * 3600 + m * 60 + s


def _tape(ts: str, quote: str, note: Optional[str] = None) -> dict:
    """One cite on the interview. The ONLY place a deep link is built.

    Two dates ride on every tape dict: `date` is when the episode was PUBLISHED
    (the same semantic every other cite's `date` carries) and `recorded` is when
    he spoke, by his own words at [1:05:11].
    """
    return {"quote": quote,
            "url": "%s&t=%ds" % (TAPE_URL, _ts_seconds(ts)),
            "date": TAPE_DATE,
            "recorded": TAPE_RECORDED,
            "source": TAPE_SOURCE,
            "ts": ts,
            "note": note}


# Cite notes — what the extra sentence does and does NOT do to the leg it sits
# beside. Every one of them is this app's own prose, never his.
_EXCL_NOTE = ("the exclusion half — the X post says focus on; whether it is a filter "
              "is Ajay's call, the leg's pass line does not change")
_RANK_NOTE = ("technology ranked first; gold and uranium named as once in a while — "
              "a rank on the row is Ajay's call")
_IN_PLAY_NOTE = ("DATED — what was in play when this was recorded, ~June 2025 (at "
                 "[1:05:11] he says 'the last month is over May'); printed with its "
                 "date, never a standing rule")
_BEATEN_NOTE = ("agrees in direction only; 'written down' is the caption's hearing of "
                "beaten down; a different mechanism and still a price read — legend "
                "only")
_USLB_NOTE = ("a worked example — direction only, sales named first; it carries no "
              "threshold and changes no number")


# ── the criteria, one entry per line on his list ──────────────────────────
# `computed` False means the criterion is his but this board does not compute
# it; `not_computed_why` says why, and the legend prints it rather than
# pretending the list is shorter than his.
CRITERIA = [
    {"key": "eps_5c", "label": "EPS ≥ 5¢",
     "quote": S2007_EARNINGS, "url": URL_2007, "date": DATE_2007, "source": "stockbee",
     "data": "Latest quarterly EPS off the scan row's filings (sepa/qoq.compute).",
     "computed": True, "not_computed_why": None, "his_call": None,
     "cites": [],
     "fact": False},
    {"key": "eps_yoy_100", "label": "EPS ≥ +100% y/y",
     "quote": S2010_YOY, "url": URL_2010, "date": DATE_2010, "source": "stockbee",
     "data": "Latest quarter against the SAME quarter a year earlier (sepa/qoq.yoy_pct), "
             "only when the year-ago quarter made money.",
     "computed": True, "not_computed_why": None, "his_call": None,
     "cites": [_tape(*T_USLB, note=_USLB_NOTE)],
     "fact": False},
    {"key": "eps_seq_100", "label": "EPS ≥ +100% q/q",
     "quote": S2007_EARNINGS, "url": URL_2007, "date": DATE_2007, "source": "stockbee",
     "data": "Latest quarter against the quarter before it (sepa/qoq.compute), refused "
             "when the two filings are not consecutive quarters.",
     "computed": True, "not_computed_why": None, "his_call": None,
     "cites": [_tape(*T_USLB, note=_USLB_NOTE)],
     "fact": False},
    {"key": "eps_accel", "label": "Earnings accelerating",
     "quote": _q(S2007_ACCEL, S2010_YOY), "url": URL_2007, "date": DATE_2007,
     "source": "stockbee",
     "data": "This quarter's y/y EPS growth against the previous quarter's y/y EPS "
             "growth. EARNINGS acceleration — the sales flags on this board are the "
             "app's own read.",
     "computed": True, "not_computed_why": None, "his_call": None,
     "cites": [],
     "fact": False},
    {"key": "sales_5", "label": "Sales ≥ 5% y/y",
     "quote": S2007_SALES, "url": URL_2007, "date": DATE_2007, "source": "stockbee",
     "data": "The pillar's own rounded seam against SALES_FLOOR_PCT "
             "(sepa/buyable_verdict._bonde_pillar). ✓ on every row the board draws, by "
             "construction.",
     "computed": True, "not_computed_why": None, "his_call": None,
     "cites": [],
     "fact": False},
    {"key": "surprise", "label": "Earnings surprise",
     "quote": _q(S2010_BEATS, S2007_SURPRISE), "url": URL_2010, "date": DATE_2010,
     "source": "stockbee",
     "data": "The most recent reported quarter in the `earnings_calendar` cache "
             "(sepa/earnings_watch), as a percent. Labelled stale past "
             "%d days; the label never changes the verdict." % SURPRISE_STALE_DAYS,
     "computed": True, "not_computed_why": None,
     "his_call": "A beat is any surprise above zero here. \"Earnings Beats by wide "
                 "margin\" carries no number, so whether a magnitude floor should "
                 "apply is Ajay's call.",
     "cites": [_tape(*T_NEWSPAPER, note="his origin universe was last night's reporters")],
     "fact": False},
    {"key": "float_25m", "label": "Float < 25M",
     "quote": _q(S2010_FLOAT, X2024_FLOAT), "url": URL_2010, "date": DATE_2010,
     "source": "stockbee",
     "data": "yfinance `floatShares`, cached in `board_metrics`. Unknown until "
             "`python -m sepa.board_metrics warm --all` has refreshed the doc.",
     "computed": True, "not_computed_why": None, "his_call": None,
     "cites": [],
     "fact": False},
    {"key": "short_dtc_5", "label": "Days to cover ≥ 5",
     "quote": X2024_FLOAT, "url": X_2024_06_13, "date": "2024-06-13", "source": "x",
     "data": "FINRA short interest via Massive, cached in `short_interest_latest`. "
             "Unknown on every row until the warm has run.",
     "computed": True, "not_computed_why": None,
     "his_call": "The warm cadence and its crontab line are Ajay's call; the crontab "
                 "is host-mounted and a deploy does not ship it.",
     "cites": [],
     "fact": False},
    {"key": "neglect_analysts", "label": "No analyst coverage",
     "quote": _q(S2007_NEGLECT, S2010_NEGLECT), "url": URL_2007, "date": DATE_2007,
     "source": "stockbee",
     "data": "The count of analysts on Yahoo's current-quarter estimate row, cached in "
             "`analyst_pulse`. Yahoo never prints a zero — an EMPTY estimate frame is "
             "the only evidence of no coverage.",
     "computed": True, "not_computed_why": None,
     "his_call": "Reading an empty Yahoo estimate frame as his \"no analyst coverage\" "
                 "is a reading pending Ajay's nod, and whether a small count (say ≤2) "
                 "should also read as neglected is his call — his words give no number.",
     "cites": [],
     "fact": False},
    {"key": "fund_holding", "label": "Fund holding",
     "quote": _q(S2014_MARKETSMITH, S2025_LOW_FUND), "url": URL_2014, "date": DATE_2014,
     "source": "stockbee",
     "data": "Institutional ownership from the scan row (yfinance "
             "`heldPercentInstitutions`) — a 13F LEVEL, never a flow.",
     "computed": True,
     "not_computed_why": None,
     "his_call": "He names fund holding as something he looks at and gives no number, "
                 "so this leg is always shown as a fact and never as a pass or a fail.",
     "cites": [],
     "fact": True},
    {"key": "ipo_10y", "label": "IPO ≤ 10y",
     "quote": S2025_YOUNG, "url": URL_2025, "date": DATE_2025, "source": "stockbee",
     "data": "Listing date from the `ipo_dates` cache (Finnhub profile), uncorroborated.",
     "computed": True, "not_computed_why": None,
     "his_call": "It is the least-corroborated leg — 21.4% of profile dates on this "
                 "universe are recycled tickers, which reads as a falsely young ✓. "
                 "Whether it stays among the chips is Ajay's call.",
     "cites": [],
     "fact": False},
    {"key": "cap_10b", "label": "Cap < $10B",
     "quote": _q(S2025_YOUNG, S2025_SCAN), "url": URL_2025, "date": DATE_2025,
     "source": "stockbee",
     "data": "yfinance `marketCap`, cached in `board_metrics`.",
     "computed": True, "not_computed_why": None,
     "his_call": "His prose says less than $10 billion and his scan line in the same "
                 "post says below 11 billion. This leg passes at the prose bound; "
                 "which one to use is Ajay's call.",
     "cites": [],
     "fact": False},
    {"key": "rev_39_x2", "label": "Revenue ≥ 39% ×2",
     "quote": S2025_SCAN, "url": URL_2025, "date": DATE_2025, "source": "stockbee",
     "data": "This quarter's and the previous quarter's revenue growth, read here as "
             "year over year — his post does not say which base.",
     "computed": True, "not_computed_why": None,
     "his_call": "This figure is his. Whether it joins or replaces a sales TIER on this "
                 "board is Ajay's call; nothing about the tiers moved.",
     "cites": [_tape(*T_USLB, note=_USLB_NOTE)],
     "fact": False},
    {"key": "sector_3", "label": "His three EP sectors",
     "quote": X2023_SECTORS, "url": X_2023_01_25, "date": "2023-01-25", "source": "x",
     "data": "The scan row's sector, in yfinance vocabulary — consumer discretionary is "
             "named \"Consumer Cyclical\" there. A FACT about the name, not a gate.",
     "computed": True, "not_computed_why": None, "his_call": None,
     "cites": [_tape(*T_SECTORS),
               _tape(*T_SECTORS_EXCL, note=_EXCL_NOTE),
               _tape(*T_SECTORS_RANK, note=_RANK_NOTE)],
     "fact": False},

    # ── the FACT legs: his sentence names the thing and no level for it ───
    # Every one of these is `ok = None` by construction (`_fact`). A value and
    # a dash, never a tick and never a cross: he publishes no line for any of
    # them, and drawing one would be this app's judgement in his voice.
    {"key": "report_age", "label": "Days since last report",
     "quote": T_NEWSPAPER[1], "url": _tape(*T_NEWSPAPER)["url"], "date": TAPE_DATE,
     "source": TAPE_SOURCE, "ts": T_NEWSPAPER[0], "recorded": TAPE_RECORDED,
     "data": "Days from today to the `date` of the last reported quarter in the "
             "`earnings_calendar` cache — the SAME doc the surprise leg reads, so it "
             "costs no extra read. A FACT: his words name no window; the stale label "
             "past %d days is this app's." % SURPRISE_STALE_DAYS,
     "computed": True, "not_computed_why": None,
     "his_call": "What recency reads as in play is Ajay's call; the %d-day label never "
                 "flips anything." % SURPRISE_STALE_DAYS,
     "cites": [], "fact": True},
    {"key": "turnaround", "label": "Turnaround (loss → profit y/y)",
     "quote": T_TURNAROUND[1], "url": _tape(*T_TURNAROUND)["url"], "date": TAPE_DATE,
     "source": TAPE_SOURCE, "ts": T_TURNAROUND[0], "recorded": TAPE_RECORDED,
     "data": "Year-ago quarter EPS ≤ 0 and latest quarter EPS > 0, on the same "
             "fiscal-pair guard the y/y legs use (sepa/qoq). This is the cohort the "
             "y/y EPS legs mark year_ago_loss; the sequential flip (qoq income_turn) "
             "rides beside it.",
     "computed": True, "not_computed_why": None,
     "his_call": "Whether a turnaround reads as a pass or stays a fact is Ajay's call "
                 "— his words give no rule.",
     "cites": [], "fact": True},
    {"key": "growth_streak", "label": "Revenue growth streak (trailing)",
     "quote": T_STREAK[1], "url": _tape(*T_STREAK)["url"], "date": TAPE_DATE,
     "source": TAPE_SOURCE, "ts": T_STREAK[0], "recorded": TAPE_RECORDED,
     "data": "Trailing count of consecutive quarters of positive y/y revenue growth — "
             "sales.compute's own consecutive_growth_q, never recomputed here; it "
             "counts up to %d, so %d reads as %d or more, and it stops where the "
             "revenue history stops, which the leg says when it happens. Only the "
             "latest two year-ago pairs are period-checked. His sentence is a FORWARD "
             "projection this app does not make." % (STREAK_CAP, STREAK_CAP, STREAK_CAP),
     "computed": True, "not_computed_why": None,
     "his_call": "What count reads as a pass is Ajay's call; his words give none.",
     "cites": [], "fact": True},
    {"key": "theme", "label": "Theme (the app's map)",
     "quote": X2023_STORY, "url": X_2023_11_12, "date": "2023-11-12", "source": "x",
     "data": "The app's own theme map (supply_demand/sectors.sectors_for_ticker), in "
             "memory, no network — his word is theme, the map is ours. The map names "
             "%d tickers across %d themes and is S&P-heavy: a miss reads %s — "
             "UNMAPPED, never themeless — and most of this board's small caps miss it."
             % (len(THEME_MAP_TICKERS), len(SECTORS), THEME_UNMAPPED),
     "computed": True, "not_computed_why": None,
     "his_call": "Whether the app's map is the right reading of his word theme, and "
                 "whether a miss should read unknown instead of a fact about the map, "
                 "is Ajay's call.",
     "cites": [_tape(*T_REASON)], "fact": True},

    # ── his, and NOT computed here ────────────────────────────────────────
    {"key": "run_up_65d", "label": "Has not rallied into earnings",
     "quote": S2007_RUNUP, "url": URL_2007, "date": DATE_2007, "source": "stockbee",
     "data": "Not computed here.",
     "computed": False,
     "not_computed_why": "It is a PRICE read over 65 days, and the correction that "
                         "shaped this line asked for static information only.",
     "his_call": "Whether a 65-day run-up number belongs on the row is Ajay's call.",
     "cites": [_tape(*T_BEATEN_DOWN, note=_BEATEN_NOTE)],
     "fact": False},
    {"key": "story_ep", "label": "Story / theme EP",
     "quote": X2023_STORY, "url": X_2023_11_12, "date": "2023-11-12", "source": "x",
     "data": "Not computed here.",
     "computed": False,
     "not_computed_why": "There is no feed that decides whether a name is a story "
                         "stock, and inventing one would be this app's judgement "
                         "wearing his words.",
     "his_call": None,
     "cites": [_tape(*T_REASON), _tape(*T_IN_PLAY, note=_IN_PLAY_NOTE)],
     "fact": False},
    {"key": "pead", "label": "Post-earnings drift",
     "quote": _q(S2007_PEAD, X2023_PEAD), "url": URL_2007, "date": DATE_2007,
     "source": "stockbee",
     "data": "Not computed here.",
     "computed": False,
     "not_computed_why": "It is the anomaly his whole method rests on, not a per-name "
                         "screen: there is nothing to tick on a row.",
     "his_call": None,
     "cites": [_tape(*T_EP_BORN, note="the origin: he systematised the search after one trade")],
     "fact": False},
    {"key": "reactor_watchlist", "label": "Reacted well to earnings",
     "quote": X2021_REACTOR, "url": X_2021_08_13, "date": "2021-08-13", "source": "x",
     "data": "Not computed here.",
     "computed": False,
     "not_computed_why": "It is a watchlist he keeps over weeks and months, and the "
                         "reaction is a price read — dynamic, so out of scope for this "
                         "line.",
     "his_call": None,
     "cites": [],
     "fact": False},
    {"key": "top_sector", "label": "Top sector",
     "quote": _q(S2010_TOP_SECTOR_CAT, S2010_TOP_SECTOR), "url": URL_2010,
     "date": DATE_2010, "source": "stockbee",
     "data": "Not computed here.",
     "computed": False,
     "not_computed_why": "No sector RANK feed reaches this board, and the app's own "
                         "rotation read is a different concept with its own page.",
     "his_call": None,
     "cites": [_tape(*T_MARKET_LIKES)],
     "fact": False},
    {"key": "earnings_40", "label": "Earnings 40% plus",
     "quote": S2010_EARNINGS_40, "url": URL_2010, "date": DATE_2010, "source": "stockbee",
     "data": "Not computed here.",
     "computed": False,
     "not_computed_why": "It is one entry in his catalogue of EP catalyst CATEGORIES, "
                         "not a screen number he says he runs: he writes that he only "
                         "focuses on the 100%-plus names.",
     "his_call": None,
     "cites": [],
     "fact": False},

    # ── on tape, and NOT computed here ────────────────────────────────────
    {"key": "ep_origin_300", "label": "The paragraph that started EP (300–500%)",
     "quote": T_ORIGIN_300[1], "url": _tape(*T_ORIGIN_300)["url"], "date": TAPE_DATE,
     "source": TAPE_SOURCE, "ts": T_ORIGIN_300[0], "recorded": TAPE_RECORDED,
     "data": "Not computed here.",
     "computed": False,
     "not_computed_why": "The book paragraph that started EP, quoted by him — NOT his "
                         "screen; his published screen is 100% (2007, 2010). Nothing "
                         "here moves off his published number.",
     "his_call": "A second, higher tier chip at the origin figure, or legend only — "
                 "default legend only.",
     "cites": [], "fact": False},
    {"key": "valuation", "label": "Valuation",
     "quote": T_VALUATION[1], "url": _tape(*T_VALUATION)["url"], "date": TAPE_DATE,
     "source": TAPE_SOURCE, "ts": T_VALUATION[0], "recorded": TAPE_RECORDED,
     "data": "Not computed here.",
     "computed": False,
     "not_computed_why": "He names valuation and no metric and no number; a chip would "
                         "be this app choosing a ratio and wearing his word for it. "
                         "The quarters-in-a-row half is the growth_streak fact.",
     "his_call": "Which metric, if any — his words give none.",
     "cites": [], "fact": False},
    {"key": "volume_9m", "label": "9 million volume",
     "quote": T_VOLUME_9M[1], "url": _tape(*T_VOLUME_9M)["url"], "date": TAPE_DATE,
     "source": TAPE_SOURCE, "ts": T_VOLUME_9M[0], "recorded": TAPE_RECORDED,
     "data": "Not computed here.",
     "computed": False,
     "not_computed_why": "Unit and window are unstated, and volume is dynamic — the "
                         "class his correction removed from this line. His 2010 post's "
                         "construct is RELATIVE (ten times average volume), not an "
                         "absolute floor.",
     "his_call": "Shares or dollars, which window, and whether a dynamic liquidity "
                 "floor belongs on a static line at all.",
     "cites": [], "fact": False},
]

COMPUTED_KEYS = [c["key"] for c in CRITERIA if c["computed"]]
LEGEND_ONLY_KEYS = [c["key"] for c in CRITERIA if not c["computed"]]
# The eleven legs that come off the scan row, and the seven that come off a cache.
SCAN_KEYS = ("eps_5c", "eps_yoy_100", "eps_seq_100", "eps_accel", "sales_5",
             "rev_39_x2", "fund_holding", "sector_3",
             "turnaround", "growth_streak", "theme")
CACHE_KEYS = ("surprise", "float_25m", "cap_10b", "short_dtc_5",
              "neglect_analysts", "ipo_10y", "report_age")
# The legs that have NO pass state at all: he names the thing and publishes no
# level for it, so they carry a value and never an `ok`.
FACT_KEYS = ("fund_holding", "report_age", "turnaround", "growth_streak", "theme")
# The four states of the year-ago EPS pair the turnaround fact can be in.
TURN_TOKENS = ("to_profit", "to_loss", "loss_both", "profit_both")

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


def _fact(value=None, why="no_threshold_in_his_writing", **extra) -> dict:
    """A leg that has NO pass state, built so it cannot acquire one.

    He names the thing and publishes no level for it. `ok` is not a parameter
    here on purpose: a fact leg that could be handed `ok=True` is one edit away
    from ticking a threshold this app invented and wearing his voice for it.
    """
    if "ok" in extra:
        raise ValueError("a FACT leg has no pass state: `ok` cannot be set")
    return _leg(ok=None, value=value, why=why, **extra)


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
    """The eleven legs that need nothing but the scan row. PURE.

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
        legs["fund_holding"] = _fact(inst,
                                     source="13F level via yfinance (never a flow)")

    # His three earnings-EP sectors.
    sector = scan_row.get("sector")
    sector = str(sector).strip() if sector else None
    if not sector:
        legs["sector_3"] = _leg(why="no_sector")
    else:
        legs["sector_3"] = _leg(ok=sector in EP_SECTORS, value=sector,
                                value_note="a fact about the name, not a gate")

    # Turnaround — the YEAR-AGO pair, on the same guard the y/y legs use. This
    # is NOT `qoq.income_turn`: that one is the SEQUENTIAL flip (slot 0 vs 1).
    # It rides along as `seq_turn` and is never redefined here.
    if not has_eps:
        legs["turnaround"] = _leg(why="no_eps_series")
    elif pair_refused:
        legs["turnaround"] = _leg(why="pair_not_a_year_apart")
    else:
        j = Q.YOY_GAP
        base = _f(eps[j]) if len(eps) > j else None
        cur = _f(eps[0]) if eps else None
        if base is None or cur is None:
            legs["turnaround"] = _leg(why="no_eps_series")
        else:
            token = ("to_profit" if base <= 0 < cur else
                     "to_loss" if base > 0 >= cur else
                     "loss_both" if base <= 0 else "profit_both")
            legs["turnaround"] = _fact(
                token, latest=cur, year_ago=base, seq_turn=q.get("income_turn"),
                value_note=("unverified pair — no fiscal-period keys on file"
                            if unverified else
                            "year-ago quarter vs the latest; his words give no rule"),
                source="scan row EPS series (sepa/qoq slot 0 vs slot %d)" % Q.YOY_GAP)

    # Revenue growth streak — `sales.compute`'s OWN count, read off
    # `fundamentals.sales`. Never off the pillar/row copy: `_bonde_pillar`
    # coerces it `or 0`, which turns "no read" into a zero streak on his board.
    sales = fundamentals.get("sales") if isinstance(fundamentals, dict) else None
    # `legs_from_scan_row` runs OUTSIDE any try in `bonde.py::_row`, so every
    # Mongo value goes through `_f` — a bare int() here is a board outage.
    streak = _f(sales.get("consecutive_growth_q")) if isinstance(sales, dict) else None
    if pair_refused:
        legs["growth_streak"] = _leg(why="pair_not_a_year_apart")
    elif (not isinstance(sales, dict) or sales.get("growth_yoy_pct") is None
            or streak is None):
        legs["growth_streak"] = _leg(why="no_sales_read")
    else:
        n = int(streak)
        # a LENGTH, never a growth number — sales.py owns the arithmetic
        n_pairs = max(0, len(_series(fundamentals, "rev_q_series")) - Q.YOY_GAP)
        capped = n >= STREAK_CAP
        history_ended = (n < STREAK_CAP and n_pairs <= n)
        note = ("unverified pair — no fiscal-period keys on file" if unverified else
                "trailing — the count ended where the revenue history ends, not where "
                "growth did" if history_ended else
                "trailing — his sentence projects forward; this app does not; pairs "
                "beyond the prior are not period-checked")
        legs["growth_streak"] = _fact(
            n, capped=capped, history_ended=history_ended, n_pairs_available=n_pairs,
            value_note=note,
            source="sepa/sales.compute consecutive_growth_q (counts up to %d quarters)"
                   % STREAK_CAP)

    # Theme — the APP'S map, in memory, no network. A miss is a fact about the
    # MAP, never about the company: the roster is S&P-heavy and most of this
    # board's small caps are simply not on it.
    sym = str(scan_row.get("symbol") or "").strip().upper()
    if not sym:
        legs["theme"] = _leg(why="no_symbol")
    else:
        secs = sectors_for_ticker(sym)
        legs["theme"] = _fact(
            " · ".join(s["label"] for s in secs) if secs else THEME_UNMAPPED,
            mapped=bool(secs), ids=[s["id"] for s in secs],
            source="the app's theme map (supply_demand/sectors.py, %d tickers across "
                   "%d themes) — his word is theme, the map is ours; a miss is "
                   "unmapped, not themeless" % (len(THEME_MAP_TICKERS), len(SECTORS)))

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
    """Fill the seven cache legs on every row, in place. NEVER raises.

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
            legs["report_age"] = _report_age_leg(reports.get(sym), today)
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
    """n_pass / n_fail / n_unknown over all 18 computed legs; the five FACT legs
    always land in n_unknown.

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


def _report_age(rep: Optional[dict], today: date):
    """(report date, age in days) off ONE calendar row.

    The arithmetic both age-bearing legs share, in one place, so the surprise
    chip's age and the report_age fact can never drift apart.
    """
    d = _parse_date((rep or {}).get("date"))
    age = (today - d).days if d else None
    return d, age


def _surprise_leg(rep: Optional[dict], today: date) -> dict:
    if not rep:
        return _leg(why="not_on_calendar")
    sp = _f(rep.get("surprise_pct"))
    if sp is None:
        return _leg(why="no_surprise_in_report", as_of=rep.get("date"))
    d, age = _report_age(rep, today)
    # A LABEL, never a verdict: Rule #7 is about the reported PERIOD, and a
    # beat two quarters ago is still the last thing he had to react to. The
    # BOUND is served beside the age so a hover prints the app's constant
    # rather than the row's own age.
    stale = (age > SURPRISE_STALE_DAYS) if age is not None else None
    return _leg(ok=sp > 0, value=sp, as_of=(d.isoformat() if d else None),
                age_days=age, stale=stale, stale_after=SURPRISE_STALE_DAYS,
                source="earnings_calendar (sepa/earnings_watch)")


def _report_age_leg(rep: Optional[dict], today: date) -> dict:
    """How long ago the last quarter was reported. A FACT — his words name no
    window, and the stale label (`SURPRISE_STALE_DAYS`) is this app's own."""
    if not rep:
        return _leg(why="not_on_calendar")
    d, age = _report_age(rep, today)
    if d is None or age is None or age < 0:
        return _leg(why="not_on_calendar",
                    value_note="calendar row carries no readable past date")
    return _fact(age, as_of=d.isoformat(), age_days=age,
                 stale=(age > SURPRISE_STALE_DAYS),
                 stale_after=SURPRISE_STALE_DAYS,
                 source="earnings_calendar (sepa/earnings_watch) — the same doc as "
                        "the surprise leg")


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
        # the second header line, in his own voice, on tape
        "tape_header": _tape(*T_CHART_NOT_SETUP),
        "tape": {"url": TAPE_URL, "title": TAPE_TITLE, "show": TAPE_SHOW,
                 "published": TAPE_DATE, "recorded": TAPE_RECORDED,
                 "recorded_cite": _tape(*T_LAST_MONTH), "received": TAPE_RECEIVED},
        "fact_keys": list(FACT_KEYS),
    }


def coverage(rows: list) -> dict:
    """{leg_key: {known, rows}} — the one sentence that says what is UNKNOWN.

    A board of em-dashes with no explanation reads as broken; a board that says
    "float known on 169 of 199" reads as honest.

    A FACT leg has no `ok` by construction, so for those five keys KNOWN means
    a value was read (§7.10). Without that rule `fund_holding` would report 0
    of N on a board where it is filled on nearly every row.
    """
    rows = rows or []
    out = {k: {"known": 0, "rows": 0} for k in COMPUTED_KEYS}
    for r in rows:
        legs = ((r.get("pick") or {}).get("legs") or {})
        for k in COMPUTED_KEYS:
            out[k]["rows"] += 1
            leg = legs.get(k) or {}
            if leg.get("ok") is not None or (k in FACT_KEYS
                                             and leg.get("value") is not None):
                out[k]["known"] += 1
    return out
