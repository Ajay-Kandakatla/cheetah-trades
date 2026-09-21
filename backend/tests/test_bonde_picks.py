"""📋 The Bonde PICK LINE (`sepa/bonde_picks.py`), Ajay 2026-09-20.

The negatives carry this file, and they carry it for one reason: every leg here
is a claim about a company, made in HIS words, on a board he reads. The three
ways to get that wrong are all pinned below.

  1. An UNKNOWN rendered as a FAIL. A cold cache, a fiscal pair that is not a
     year apart and a year-ago loss are all "we cannot say". A ✗ beside his
     sentence says the company failed his criterion.
  2. A confident number off arithmetic. `qoq.yoy_pct` divides by |base|, so
     −0.20 → +0.30 is +250% — a sign flip printed as a doubling. Every y/y EPS
     leg refuses a non-positive base.
  3. A `why` code with no sentence beside it. ONE vocabulary (`WHY_CODES`); the
     frontend's WHY_TEXT keys are pinned equal to it by the contract sweep, and
     a board walked end to end here must never serve a code outside it.

Plus the cost pin: `bonde.board()` reaches no network at all — `requests.get`
is monkeypatched to raise and a full stubbed board is built through it.
"""
from __future__ import annotations

import importlib
import json
import os
import re

import pytest

from sepa import bonde as BD
from sepa import bonde_picks as BP
from sepa import first_seen as FS
from sepa import qoq as Q


# ─────────────────────────────────────────────────────────── fixtures
def scan_row(symbol, **kw):
    f = {"eps_q_series": kw.get("eps"),
         "rev_q_series": kw.get("rev", [200_000_000, 0, 0, 0, 100_000_000]),
         "q_period_series": kw.get("periods"),
         "inst_ownership_pct": kw.get("inst"),
         "sales": kw.get("sales") or {}}
    if "inst" not in kw:
        f.pop("inst_ownership_pct")
    return {"symbol": symbol, "name": kw.get("name"), "sector": kw.get("sector"),
            "last_close": 10.0, "fundamentals": f}


def pillar(growth=100.0, **kw):
    return {"passed": kw.get("passed", True), "growth_yoy_pct": growth,
            "tier": kw.get("tier", "strong"), "score": 80,
            "accelerating": kw.get("accelerating", True),
            "consecutive_growth_q": kw.get("consec", 4),
            "sales_led": None, "reason": ""}


def legs(symbol="AAA", *, row=None, cleared=True, **kw):
    sr = scan_row(symbol, **kw)
    p = pillar(kw.get("growth", 100.0))
    r = {"growth_yoy_pct": kw.get("growth", 100.0),
         "prior_yoy_pct": kw.get("prior", 50.0),
         "period_ok": kw.get("period_ok", True),
         "prior_hole": kw.get("prior_hole", False)}
    r.update(row or {})
    return BP.legs_from_scan_row(sr, p, r, cleared)


# ══════════════════════════════════════════ the contract: keys, quotes, cites
def test_the_served_leg_keys_are_exactly_the_CRITERIA_computed_keys():
    got = set(legs(eps=[0.30, 0.10, 0.09, 0.08, 0.10, 0.05],
                   periods=[8105, 8104, 8103, 8102, 8101, 8100],
                   sector="Technology", inst=30.0))
    assert got == set(BP.SCAN_KEYS)
    assert set(BP.SCAN_KEYS) | set(BP.CACHE_KEYS) == set(BP.COMPUTED_KEYS)
    assert len(BP.COMPUTED_KEYS) == 18
    assert len(BP.LEGEND_ONLY_KEYS) == 9
    assert len(BP.CRITERIA) == 27


def test_every_criterion_carries_a_VERBATIM_sentence_and_one_of_his_links():
    """A criterion without his sentence is this app's opinion in his voice."""
    for c in BP.CRITERIA:
        assert c["quote"] and c["quote"].strip(), c["key"]
        assert ("stockbee.blogspot.com" in c["url"]
                or "x.com/PradeepBonde" in c["url"]
                or c["url"].startswith(BP.TAPE_URL + "&t=")), c["key"]
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", c["date"]), c["key"]
        assert c["source"] in ("stockbee", "x", "tape"), c["key"]
        assert c["data"], c["key"]
        assert isinstance(c["cites"], list), c["key"]
        assert isinstance(c["fact"], bool), c["key"]
        if not c["computed"]:
            assert c["not_computed_why"], c["key"]


def test_a_TAPE_primary_criterion_carries_its_second_and_its_recording_date():
    """Two dates on every tape entry: `date` is when the episode was published
    and `recorded` is when he spoke. One semantic per key across the app."""
    tape = [c for c in BP.CRITERIA if c["source"] == "tape"]
    assert len(tape) == 6, [c["key"] for c in tape]
    for c in tape:
        assert c["ts"], c["key"]
        assert c["recorded"] == BP.TAPE_RECORDED, c["key"]
        assert c["date"] == BP.TAPE_DATE, c["key"]
        assert c["url"] == "%s&t=%ds" % (BP.TAPE_URL, BP._ts_seconds(c["ts"])), c["key"]
    # and a criterion that is NOT on tape carries neither
    crit = {c["key"]: c for c in BP.CRITERIA}
    assert "ts" not in crit["eps_5c"] and "recorded" not in crit["eps_5c"]


def test_every_CITE_is_a_tape_dict_built_by_the_one_builder():
    n = 0
    for c in BP.CRITERIA:
        for cite in c["cites"]:
            n += 1
            assert set(cite) == {"quote", "url", "date", "recorded", "source",
                                 "ts", "note"}, (c["key"], cite)
            assert cite["source"] == BP.TAPE_SOURCE
            assert cite["date"] == BP.TAPE_DATE
            assert cite["recorded"] == BP.TAPE_RECORDED
            assert cite["url"] == "%s&t=%ds" % (BP.TAPE_URL,
                                                BP._ts_seconds(cite["ts"]))
    assert n == 13, n          # ten criteria, three of the cites on sector_3


def test_only_the_NAMED_criteria_gained_a_second_cite_on_tape():
    cited = {c["key"] for c in BP.CRITERIA if c["cites"]}
    assert cited == {"sector_3", "story_ep", "top_sector", "pead", "surprise",
                     "run_up_65d", "eps_yoy_100", "eps_seq_100", "rev_39_x2",
                     "theme"}


def test_the_PRIMARY_cite_of_every_pre_existing_criterion_is_BYTE_IDENTICAL():
    """"Add, never replace." The interview is a SECOND cite on his criteria; if
    a tape sentence ever became the primary quote of one of the twenty, the
    board would be quoting a podcast where it used to quote a post he wrote."""
    frozen = {
        "eps_5c": (BP.S2007_EARNINGS, BP.URL_2007, BP.DATE_2007, "stockbee"),
        "eps_yoy_100": (BP.S2010_YOY, BP.URL_2010, BP.DATE_2010, "stockbee"),
        "eps_seq_100": (BP.S2007_EARNINGS, BP.URL_2007, BP.DATE_2007, "stockbee"),
        "eps_accel": (BP.S2007_ACCEL + " · " + BP.S2010_YOY, BP.URL_2007,
                      BP.DATE_2007, "stockbee"),
        "sales_5": (BP.S2007_SALES, BP.URL_2007, BP.DATE_2007, "stockbee"),
        "surprise": (BP.S2010_BEATS + " · " + BP.S2007_SURPRISE, BP.URL_2010,
                     BP.DATE_2010, "stockbee"),
        "float_25m": (BP.S2010_FLOAT + " · " + BP.X2024_FLOAT, BP.URL_2010,
                      BP.DATE_2010, "stockbee"),
        "short_dtc_5": (BP.X2024_FLOAT, BP.X_2024_06_13, "2024-06-13", "x"),
        "neglect_analysts": (BP.S2007_NEGLECT + " · " + BP.S2010_NEGLECT,
                             BP.URL_2007, BP.DATE_2007, "stockbee"),
        "fund_holding": (BP.S2014_MARKETSMITH + " · " + BP.S2025_LOW_FUND,
                         BP.URL_2014, BP.DATE_2014, "stockbee"),
        "ipo_10y": (BP.S2025_YOUNG, BP.URL_2025, BP.DATE_2025, "stockbee"),
        "cap_10b": (BP.S2025_YOUNG + " · " + BP.S2025_SCAN, BP.URL_2025,
                    BP.DATE_2025, "stockbee"),
        "rev_39_x2": (BP.S2025_SCAN, BP.URL_2025, BP.DATE_2025, "stockbee"),
        "sector_3": (BP.X2023_SECTORS, BP.X_2023_01_25, "2023-01-25", "x"),
        "run_up_65d": (BP.S2007_RUNUP, BP.URL_2007, BP.DATE_2007, "stockbee"),
        "story_ep": (BP.X2023_STORY, BP.X_2023_11_12, "2023-11-12", "x"),
        "pead": (BP.S2007_PEAD + " · " + BP.X2023_PEAD, BP.URL_2007,
                 BP.DATE_2007, "stockbee"),
        "reactor_watchlist": (BP.X2021_REACTOR, BP.X_2021_08_13, "2021-08-13", "x"),
        "top_sector": (BP.S2010_TOP_SECTOR_CAT + " · " + BP.S2010_TOP_SECTOR,
                       BP.URL_2010, BP.DATE_2010, "stockbee"),
        "earnings_40": (BP.S2010_EARNINGS_40, BP.URL_2010, BP.DATE_2010, "stockbee"),
    }
    assert len(frozen) == 20
    crit = {c["key"]: c for c in BP.CRITERIA}
    for key, want in frozen.items():
        got = crit[key]
        assert (got["quote"], got["url"], got["date"], got["source"]) == want, key


# The frozen set: every sentence this module is allowed to put in his mouth.
# A paraphrase — even a tidier one — fails here.
ALLOWED_QUOTES = frozenset({
    "I only track companies whose earnings are up 100% or more quarter over "
    "quarter and the earnings should be at least 5 cents.",
    "Sales/revenue should be up 5% or more.",
    "Now what one is looking for is earnings acceleration.",
    "Even better is stock which has no analyst coverage and is neglected.",
    "Besides that I look for price action on that stock by looking at how much "
    "they are up in last 65 days or so. I am looking for stocks which have not "
    "rallied in anticipation of earnings.",
    "An earnings surprise on stock which has not rallied significantly will "
    "lead to breakout next day.",
    "PEAD or post earnings announcement drift is a well studied and proven "
    "market anomaly.",
    "On such stocks a significant earnings acceleration compared to last year "
    "same quarter as well as quarter over quarter is what to look for. I like "
    "to look for companies which had earnings acceleration of 100% plus in "
    "such cases.",
    "Stock with no analyst coverage",
    "Float below 25 million is ideal for this. The best moves happen on float "
    "below 10 million. Earnings breakouts on companies with 100 million plus "
    "float tend to have pullbacks.",
    "Beats analyst estimate",
    "In top 10 sector",
    "Top Sector",
    "Earnings 40% plus",
    "Marketsmith to find earnings and earnings trends, float, fund holding",
    "The most explosive Episodic Pivots occur in stocks that have Gone Public "
    "in the last 10 years and have a capitalization of less than $ 10 billion "
    "once they enter their growth phase.",
    "They will have very low capitalization, low fund ownership, and low "
    "interest from analysts and general investors.",
    "This scan finds stocks incorporated or IPOed in last 10 years that have a "
    "market capitalization below 11 billion and have two quarters of revenue "
    "growth of 39% plus.",
    "Stocks with lower floats (under 25M shares) tend to see the biggest "
    "episodic pivot moves … This coupled with high short interest ( 5 plus "
    "days to cover) can result in explosive moves",
    "If you want to make money from Earnings Episodic Pivots, focus on three "
    "sectors: technology, healthcare, and consumer discretionary.",
    "there is 100 times more money on story stocks EP … Understanding what "
    "theme is working and finding story EP in them is now my major focus",
    "Post earnings announcements drift is well known markrt anomaly and EP is "
    "based on that.",
    "Keep a watchlist of stocks that reacted positively to earnings (earnings "
    "Episodic Pivots) , they always offer another lower risk entry opportunity "
    "after few weeks or months.",
})


def test_SOURCE_GUARD_every_quote_is_one_of_his_frozen_sentences():
    """Blog and X quotes come out of the frozen set above; TAPE quotes come out
    of the caption fixture, checked line by line by `_in_fixture`."""
    for c in BP.CRITERIA:
        if c["source"] == BP.TAPE_SOURCE:
            assert _in_fixture(c["ts"], c["quote"]), c["key"]
            continue
        for part in c["quote"].split(" · "):
            assert part in ALLOWED_QUOTES, (c["key"], part)


def test_NEGATIVE_a_paraphrase_of_one_of_his_sentences_is_not_allowed():
    """The guard has to bite, or it is decoration."""
    assert "Sales should be up 5% or more." not in ALLOWED_QUOTES
    assert "Sales/revenue should be up 5% or more." in ALLOWED_QUOTES


# ══════════════════════════════════════════════ the tape, sentence by sentence
# The caption track is 697 lines and is NOT committed. The 33 lines the module
# quotes from are, and every tape sentence must be found in them, starting on
# the line its timestamp names — a quote that drifts a line is a quote from a
# different sentence, and on a caption track with no speaker labels it can be
# the HOST's.
_FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures",
                             "bonde_video_captions_2026_09_20.json")
with open(_FIXTURE_PATH, encoding="utf-8") as _fh:
    CAPTIONS = json.load(_fh)


def _norm(s) -> str:
    """TRAP: the caption track carries U+00A0 at every wrap and line end, so a
    byte-compare against a typed quote fails. Both sides normalise the same."""
    return re.sub(r"\s+", " ", (s or "").replace("\u00a0", " ")).strip()


def _run_from(ts: str):
    """The fixture entry at `ts` (exactly one) and the consecutive caption
    lines that follow it."""
    idx = [i for i, e in enumerate(CAPTIONS) if e["ts"] == ts]
    if len(idx) != 1:
        return None
    i = idx[0]
    run = [CAPTIONS[i]]
    j = i + 1
    while j < len(CAPTIONS) and CAPTIONS[j]["line"] == CAPTIONS[j - 1]["line"] + 1:
        run.append(CAPTIONS[j])
        j += 1
    return run


def _in_fixture(ts: str, quote: str) -> bool:
    """Is `quote` really what he says starting at `ts`?

    Every segment (split on the one permitted elision, " … ") must appear in
    order in the joined run of caption lines, and the FIRST segment must start
    on the cited line — otherwise the deep link opens a second before or after
    the words it claims to carry.
    """
    run = _run_from(ts)
    if not run:
        return False
    joined = _norm(" ".join(e["text"] for e in run))
    first_len = len(_norm(run[0]["text"]))
    pos = 0
    for n, seg in enumerate(_norm(quote).split(" … ")):
        seg = _norm(seg)
        if not seg:
            return False
        k = joined.find(seg, pos)
        if k < 0:
            return False
        if n == 0 and k >= first_len:
            return False
        pos = k + len(seg)
    return True


def test_every_TAPE_sentence_the_module_holds_is_in_the_caption_fixture():
    assert len(BP.TAPE_SENTENCES) == 17
    for ts, quote in BP.TAPE_SENTENCES:
        assert _in_fixture(ts, quote), ts


def test_every_tape_PRIMARY_and_every_CITE_quote_is_in_the_caption_fixture():
    for c in BP.CRITERIA:
        if c["source"] == BP.TAPE_SOURCE:
            assert _in_fixture(c["ts"], c["quote"]), c["key"]
        for cite in c["cites"]:
            assert _in_fixture(cite["ts"], cite["quote"]), (c["key"], cite["ts"])
    assert _in_fixture(*BP.T_CHART_NOT_SETUP)
    assert _in_fixture(BP.legend()["tape_header"]["ts"],
                       BP.legend()["tape_header"]["quote"])


def test_the_RECORDING_estimate_is_his_own_sentence_and_the_dated_cite_says_so():
    """`recorded` is an estimate off one line of tape. The cite that carries a
    dated claim ([1:06:50], what was in play) says so in its own note."""
    assert _in_fixture("1:05:11", "the last month is over May")
    assert BP.T_LAST_MONTH == ("1:05:11", "the last month is over May")
    crit = {c["key"]: c for c in BP.CRITERIA}
    note = next(c["note"] for c in crit["story_ep"]["cites"] if c["ts"] == "1:06:50")
    for token in ("the last month is over May", "June 2025", "never a standing rule"):
        assert token in note, token


def test_NEGATIVE_a_PARAPHRASE_of_a_tape_sentence_is_not_in_the_fixture():
    """The rule has to bite. These are the three ways a tape cite goes wrong:
    tidied words, the right words at the wrong second, and a second segment
    that is simply not there."""
    assert _in_fixture("1:07:04", BP.T_SECTORS[1]) is True
    assert _in_fixture("1:07:04", "Technology is where the money is") is False
    assert _in_fixture("1:07:17", BP.T_SECTORS[1]) is False
    assert _in_fixture("0:14:17",
                       "a good chart itself is not a setup … and that is why I "
                       "use the 9 million volume") is False
    assert _in_fixture("9:99:99", "anything at all") is False


def test_the_caption_fixture_is_the_33_lines_quoted_and_NOT_the_whole_track():
    """Committing the track would be publishing someone else's captions. Only
    the lines the module actually quotes from are in the repo."""
    assert len(CAPTIONS) == 33
    assert len(CAPTIONS) <= 40
    assert len({e["line"] for e in CAPTIONS}) == len(CAPTIONS)
    for e in CAPTIONS:
        assert re.match(r"^\d+:\d\d:\d\d$", e["ts"]), e
        assert e["text"] == _norm(e["text"]) and e["text"]
        assert "\u00a0" not in e["text"]


def test_FIXTURE_INTEGRITY_every_caption_line_matches_the_real_transcript():
    """Skipped where the track is absent (it is scratchpad, never committed).
    Where it IS present, every committed line must still be the caption at that
    line number — a fixture that drifted from the source is a forged quote."""
    src = os.environ.get("BONDE_TRANSCRIPT") or (
        "/private/tmp/claude-501/-Users-ajay-clinet-test/"
        "2ced0bf8-920d-4009-be24-082dc21c5651/scratchpad/bonde-video/transcript.txt")
    if not os.path.exists(src):
        pytest.skip("caption track not on this machine")
    with open(src, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    for e in CAPTIONS:
        raw = lines[e["line"] - 1]
        assert raw.startswith("[%s]" % e["ts"]), (e["line"], raw[:24])
        assert _norm(raw.split("]", 1)[1]) == e["text"], e["line"]


# ══════════════════════════════════════════════════ the deep link, second by second
def test_the_timestamp_to_SECONDS_conversion_is_exact():
    assert BP._ts_seconds("1:07:04") == 4024
    assert BP._ts_seconds("0:11:22") == 682
    assert BP._ts_seconds("0:00:00") == 0
    assert BP._ts_seconds("2:05") == 125


def test_NEGATIVE_a_timestamp_that_is_not_one_raises_rather_than_linking_wrong():
    for bad in ("x", "", "1:2:3:4", "1;07;04", "1:07:60", "1:99:04", None):
        with pytest.raises(ValueError):
            BP._ts_seconds(bad)


def test_the_tape_url_lands_on_the_second_the_sentence_starts():
    got = BP._tape("1:07:04", "q")
    assert got["url"].endswith("&t=4024s")
    assert got["url"] != BP.TAPE_URL + "&t=4023s"
    assert got["url"] == BP.TAPE_URL + "&t=4024s"
    assert got["ts"] == "1:07:04" and got["note"] is None
    assert got["date"] == BP.TAPE_DATE and got["recorded"] == BP.TAPE_RECORDED
    assert BP._tape("1:07:04", "q", "n")["note"] == "n"


def test_SOURCE_GUARD_the_deep_link_is_built_in_exactly_ONE_place():
    """A hand-typed `&t=` is a quote attributed to the wrong sentence, and on a
    track with no speaker labels it can be attributed to the wrong person."""
    src = open(BP.__file__).read()
    assert src.count("&t=") == 1
    assert 'TAPE_URL = "https://www.youtube.com/watch?v=fjox2hapu98"' in src


def test_the_two_EARNINGS_legs_cite_the_post_that_carries_THAT_leg():
    """He names BOTH bases and they are in different posts: the y/y leg is the
    2010 sentence ('compared to last year same quarter'), the sequential leg is
    the 2007 sentence ('up 100% or more quarter over quarter')."""
    crit = {c["key"]: c for c in BP.CRITERIA}
    assert crit["eps_yoy_100"]["url"] == BP.URL_2010
    assert "last year same quarter" in crit["eps_yoy_100"]["quote"]
    assert crit["eps_seq_100"]["url"] == BP.URL_2007
    assert "quarter over quarter" in crit["eps_seq_100"]["quote"]


def test_NEGATIVE_no_key_or_label_carries_a_MOMENTUM_word():
    """His correction: *"momentum does not need to be a criteria for his pics
    … I am looking fro static info"*. A dynamic leg sneaking onto this line is
    the one thing the ask ruled out by name."""
    banned = ("momentum", "rs_", "persistence", "return", "today", "rel_")
    for c in BP.CRITERIA:
        blob = (c["key"] + " " + c["label"]).lower()
        for word in banned:
            assert word not in blob, (c["key"], word)
    for k in BP.COMPUTED_KEYS:
        for word in banned:
            assert word not in k.lower(), (k, word)


def test_NEGATIVE_no_quote_or_label_says_bounce():
    """STANDING: 'reversal', never 'bounce', on any surface he reads."""
    blob = " ".join(c["quote"] + c["label"] + c["data"] for c in BP.CRITERIA)
    assert "bounce" not in blob.lower()


# ══════════════════════════════════════════════════ the ONE why vocabulary
def test_INCOME_BASE_TO_WHY_covers_every_qoq_base_state_except_OK():
    """Read off `qoq`'s own names, never retyped: a rename there must be an
    ImportError here, not a silently missing sentence on his board."""
    base_names = {getattr(Q, n) for n in dir(Q) if n.startswith("BASE_")}
    assert set(BP.INCOME_BASE_TO_WHY) == base_names - {Q.BASE_OK}
    assert set(BP.INCOME_BASE_TO_WHY.values()) <= BP.WHY_CODES


def test_WHY_CODES_has_the_twenty_five_codes_the_frontend_is_pinned_to():
    assert len(BP.WHY_CODES) == 25
    assert BP.legend()["why_codes"] == sorted(BP.WHY_CODES)


def test_NEGATIVE_a_leg_built_with_an_unknown_why_code_raises():
    with pytest.raises(ValueError):
        BP._leg(why="bogus")
    assert BP._leg(why=None)["why"] is None
    assert BP._leg(why="no_sector")["why"] == "no_sector"


def test_every_leg_always_carries_all_three_keys():
    for leg in legs(eps=[0.30, 0.10], sector="Energy").values():
        assert set(leg) >= {"ok", "value", "why"}


# ══════════════════════════════════════════════ the scan legs, branch by branch
def test_NO_eps_series_leaves_all_four_earnings_legs_UNKNOWN_never_FALSE():
    """THE DEFECT THIS EXISTS TO STOP. A missing series is not a company that
    earns nothing — a ✗ beside his sentence is a claim, and this one would be
    made about every name the provider has no filings for."""
    got = legs(eps=None)
    for k in ("eps_5c", "eps_yoy_100", "eps_seq_100", "eps_accel"):
        assert got[k]["ok"] is None, k
        assert got[k]["why"] == "no_eps_series", k


def test_a_YEAR_AGO_LOSS_is_UNKNOWN_not_a_250_percent_tick():
    """`qoq.yoy_pct` divides by |b|: −0.20 → +0.30 comes back +250%. That is a
    sign flip rendered as a doubling, and it would tick his 100% criterion."""
    got = legs(eps=[0.30, 0.10, 0.09, 0.08, -0.20, 0.05])
    assert got["eps_yoy_100"]["ok"] is None
    assert got["eps_yoy_100"]["why"] == "year_ago_loss"
    assert got["eps_yoy_100"]["value"] is None


def test_the_five_cent_level_sits_exactly_on_his_number():
    assert legs(eps=[0.04, 0.01])["eps_5c"]["ok"] is False
    assert legs(eps=[0.05, 0.01])["eps_5c"]["ok"] is True
    assert legs(eps=[0.05, 0.01])["eps_5c"]["value"] == 0.05
    assert BP.EPS_MIN_USD == 0.05


def test_the_doubling_legs_sit_exactly_on_his_hundred_percent():
    eps = [0.20, 0.10, 0.09, 0.08, 0.10, 0.05]
    p = [8105, 8104, 8103, 8102, 8101, 8100]
    g = legs(eps=eps, periods=p)
    assert g["eps_yoy_100"]["value"] == 100.0 and g["eps_yoy_100"]["ok"] is True
    assert g["eps_seq_100"]["value"] == 100.0 and g["eps_seq_100"]["ok"] is True
    assert legs(eps=[0.19, 0.10, 0.09, 0.08, 0.10, 0.05],
                periods=p)["eps_yoy_100"]["ok"] is False


def test_a_pair_that_is_NOT_a_year_apart_makes_every_y_slash_y_leg_unknown():
    """`period_ok False` means the pair was CHECKED and is wrong. The row may
    still carry a growth number (it does on 🔎 and pivot rows) — the leg must
    refuse it anyway, so the order of the board's own blanking cannot matter."""
    got = legs(eps=[0.30, 0.10, 0.09, 0.08, 0.10, 0.05],
               growth=200.0, prior=150.0, period_ok=False)
    for k in ("eps_yoy_100", "eps_accel", "sales_5", "rev_39_x2"):
        assert got[k]["ok"] is None, k
        assert got[k]["why"] == "pair_not_a_year_apart", k
    # the SEQUENTIAL leg is a different pair and is not refused by it
    assert got["eps_seq_100"]["why"] != "pair_not_a_year_apart"


def test_an_UNVERIFIABLE_pair_still_computes_and_says_so():
    """`period_ok None` = no keys on file, so nothing could be checked. The
    tiers already print the number with the word 'unverified'; the leg does the
    same rather than pretending to a check it never made."""
    got = legs(eps=[0.30, 0.10, 0.09, 0.08, 0.10, 0.05], period_ok=None)
    assert got["eps_yoy_100"]["ok"] is True
    assert got["eps_yoy_100"]["why"] == "no_period_keys"
    assert got["sales_5"]["why"] == "no_period_keys"


def test_non_adjacent_filings_refuse_the_SEQUENTIAL_leg_by_qoqs_own_state():
    got = legs(eps=[0.30, 0.10, 0.09], periods=[8105, 8103, 8102])
    assert got["eps_seq_100"]["ok"] is None
    assert got["eps_seq_100"]["why"] == "seq_not_adjacent"
    assert got["eps_seq_100"]["why"] == BP.INCOME_BASE_TO_WHY[Q.BASE_NOT_ADJACENT]


def test_a_LOSS_MAKING_prior_quarter_refuses_the_sequential_leg_and_keeps_the_turn():
    got = legs(eps=[0.30, -0.10, 0.09], periods=[8105, 8104, 8103])
    assert got["eps_seq_100"]["ok"] is None
    assert got["eps_seq_100"]["why"] == "seq_base_non_positive"
    assert got["eps_seq_100"]["value_note"] == "to_profit"


def test_a_PRIOR_HOLE_costs_the_acceleration_and_the_two_quarter_read():
    got = legs(eps=[0.30, 0.10, 0.09, 0.08, 0.10, 0.05], prior_hole=True)
    assert got["eps_accel"]["why"] == "prior_hole"
    assert got["rev_39_x2"]["why"] == "prior_hole"
    assert got["eps_accel"]["ok"] is None and got["rev_39_x2"]["ok"] is None


def test_earnings_acceleration_is_this_quarters_y_slash_y_against_last_quarters():
    eps = [0.30, 0.12, 0.09, 0.08, 0.10, 0.10]     # +200% now, +20% prior
    got = legs(eps=eps, periods=[8105, 8104, 8103, 8102, 8101, 8100])
    assert got["eps_accel"]["ok"] is True
    assert got["eps_accel"]["value"] == {"now": 200.0, "prior": 20.0}
    slow = [0.11, 0.30, 0.09, 0.08, 0.10, 0.10]    # +10% now, +200% prior
    assert legs(eps=slow)["eps_accel"]["ok"] is False


def test_the_sales_leg_reads_the_PILLARS_rounded_seam_not_its_own_comparison():
    assert legs(cleared=True, growth=4.6)["sales_5"]["ok"] is True
    assert legs(cleared=False, growth=4.4)["sales_5"]["ok"] is False
    assert BP.SALES_FLOOR_PCT == 5.0


def test_NEGATIVE_no_sales_read_is_UNKNOWN_not_a_failed_floor():
    assert legs(cleared=None)["sales_5"]["why"] == "no_sales_read"
    assert legs(cleared=None)["sales_5"]["ok"] is None
    assert legs(cleared=True, row={"growth_yoy_pct": None})["sales_5"]["ok"] is None


def test_his_two_quarter_revenue_leg_needs_BOTH_quarters_over_his_number():
    assert legs(growth=45.0, prior=52.0)["rev_39_x2"]["ok"] is True
    assert legs(growth=45.0, prior=20.0)["rev_39_x2"]["ok"] is False
    assert legs(growth=39.0, prior=39.0)["rev_39_x2"]["ok"] is True
    assert BP.REV_TWO_Q_PCT == 39.0
    note = legs(growth=45.0, prior=52.0)["rev_39_x2"]["value_note"]
    assert "his post does not say which base" in note


def test_FUND_HOLDING_never_passes_or_fails_because_he_publishes_no_number():
    """Rule #1: reuse his number or say there isn't one. Inventing a fund-
    ownership threshold and ticking it in his voice is the whole trap."""
    assert legs(inst=60.0)["fund_holding"]["ok"] is None
    assert legs(inst=1.0)["fund_holding"]["ok"] is None
    assert legs(inst=60.0)["fund_holding"]["why"] == "no_threshold_in_his_writing"
    assert legs(inst=60.0)["fund_holding"]["value"] == 60.0
    assert "never a flow" in legs(inst=60.0)["fund_holding"]["source"]
    assert legs()["fund_holding"]["why"] == "no_inst_read"


def test_his_three_sectors_read_in_the_SCANS_vocabulary():
    """He wrote 'consumer discretionary'; the scan rows say 'Consumer
    Cyclical'. Matching his words literally would fail every name in it."""
    assert legs(sector="Consumer Cyclical")["sector_3"]["ok"] is True
    assert legs(sector="Technology")["sector_3"]["ok"] is True
    assert legs(sector="Energy")["sector_3"]["ok"] is False
    assert legs(sector=None)["sector_3"]["ok"] is None
    assert legs(sector=None)["sector_3"]["why"] == "no_sector"


# ══════════════════════════════════════════ the FACT legs: a value and a dash
# He names the thing and publishes no level for it. A tick beside one of these
# would be this app's own threshold wearing his voice — the exact defect Rule
# #1 exists to stop — so `ok` is not even a parameter of `_fact`.
def test_FACT_KEYS_are_exactly_the_five_criteria_flagged_fact():
    flagged = {c["key"] for c in BP.CRITERIA if c["fact"]}
    assert flagged == set(BP.FACT_KEYS)
    assert len(BP.FACT_KEYS) == 5
    assert set(BP.FACT_KEYS) <= set(BP.COMPUTED_KEYS)
    assert BP.legend()["fact_keys"] == list(BP.FACT_KEYS)


def test_NEGATIVE_a_FACT_leg_cannot_be_handed_a_pass_state():
    with pytest.raises(ValueError):
        BP._fact(1, ok=True)
    with pytest.raises(ValueError):
        BP._fact(1, ok=False)
    assert BP._fact(1)["ok"] is None
    assert BP._fact(1)["why"] == "no_threshold_in_his_writing"


@pytest.mark.parametrize("kw", [
    dict(inst=0.0), dict(inst=60.0), dict(inst=100.0),
    dict(eps=[0.30, 0.10, 0.09, 0.08, -0.20, 0.05]),      # to_profit
    dict(eps=[-0.30, 0.10, 0.09, 0.08, 0.20, 0.05]),      # to_loss
    dict(eps=[-0.30, 0.10, 0.09, 0.08, -0.20, 0.05]),     # loss_both
    dict(eps=[0.30, 0.10, 0.09, 0.08, 0.20, 0.05]),       # profit_both
    dict(sales={"growth_yoy_pct": 60.0, "consecutive_growth_q": 0}),
    dict(sales={"growth_yoy_pct": 60.0, "consecutive_growth_q": 4}),
    dict(symbol="TER"), dict(symbol="ZZZZ"),
])
def test_NO_INPUT_gives_a_FACT_leg_a_tick_or_a_cross(kw):
    sym = kw.pop("symbol", "AAA")
    got = BP.legs_from_scan_row(scan_row(sym, **kw), pillar(),
                                {"period_ok": True, "growth_yoy_pct": 100.0,
                                 "prior_yoy_pct": 50.0, "prior_hole": False}, True)
    for k in BP.FACT_KEYS:
        if k not in got:
            continue
        assert got[k]["ok"] is None, k
        assert got[k]["why"] in ("no_threshold_in_his_writing", "no_inst_read",
                                 "no_sales_read", "no_eps_series",
                                 "pair_not_a_year_apart", "no_symbol"), (k, got[k])


def test_SOURCE_GUARD_every_FACT_leg_is_built_by_fact_or_is_an_unknown():
    """The guard that stops the next edit, not this one: a fact leg assembled
    by hand can acquire an `ok` the day someone adds a threshold."""
    src = open(BP.__file__).read()
    seen = set()
    for m in re.finditer(r'legs\["([a-z_]+)"\]\s*=\s*(.+)', src):
        key, rhs = m.group(1), m.group(2).strip()
        if key not in BP.FACT_KEYS:
            continue
        seen.add(key)
        assert (rhs.startswith("_fact(") or rhs.startswith("_leg(why=")
                or rhs.startswith("_report_age_leg(")), (key, rhs[:50])
    assert seen == set(BP.FACT_KEYS), seen
    body = src.split("def _report_age_leg(", 1)[1].split("\ndef ", 1)[0]
    returns = re.findall(r"return\s+(.+)", body)
    assert returns and all(r.startswith(("_fact(", "_leg(why=")) for r in returns)


def test_the_FUND_HOLDING_leg_is_BYTE_IDENTICAL_after_the_fact_helper_rewrite():
    """The rewrite routes an existing leg through `_fact`. If one key moved,
    the frontend's hover for that leg changed on a board he reads."""
    assert legs(inst=60.0)["fund_holding"] == {
        "ok": None, "value": 60.0, "why": "no_threshold_in_his_writing",
        "source": "13F level via yfinance (never a flow)"}


# ── turnaround: the YEAR-AGO pair, never qoq's sequential flip ────────────
def test_the_turnaround_fact_is_the_YEAR_AGO_pair_and_carries_the_sequential_one():
    got = legs(eps=[0.30, 0.10, 0.09, 0.08, -0.20, 0.05])["turnaround"]
    assert got["value"] == "to_profit"
    assert got["year_ago"] == -0.20 and got["latest"] == 0.30
    assert got["ok"] is None and got["why"] == "no_threshold_in_his_writing"
    assert got["seq_turn"] == Q.compute(
        eps_series=[0.30, 0.10, 0.09, 0.08, -0.20, 0.05])["income_turn"]
    assert "slot %d" % Q.YOY_GAP in got["source"]


@pytest.mark.parametrize("eps,token", [
    ([0.30, 0.10, 0.09, 0.08, -0.20, 0.05], "to_profit"),
    ([-0.10, 0.10, 0.09, 0.08, -0.20, 0.05], "loss_both"),
    ([-0.10, 0.10, 0.09, 0.08, 0.20, 0.05], "to_loss"),
    ([0.30, 0.10, 0.09, 0.08, 0.20, 0.05], "profit_both"),
    ([0.0, 0.10, 0.09, 0.08, 0.20, 0.05], "to_loss"),      # zero is not a profit
])
def test_the_four_turnaround_states_are_the_four_tokens(eps, token):
    got = legs(eps=eps)["turnaround"]
    assert got["value"] == token
    assert got["value"] in BP.TURN_TOKENS


def test_NEGATIVE_the_turnaround_fact_refuses_a_series_it_cannot_read():
    assert legs(eps=None)["turnaround"]["why"] == "no_eps_series"
    assert legs(eps=None)["turnaround"]["value"] is None
    assert legs(eps=[0.30, 0.10])["turnaround"]["why"] == "no_eps_series"
    assert legs(eps=[0.30, 0.10, 0.09, 0.08, None, 0.05])["turnaround"]["why"] \
        == "no_eps_series"
    refused = legs(eps=[0.30, 0.10, 0.09, 0.08, -0.20, 0.05], period_ok=False)
    assert refused["turnaround"]["why"] == "pair_not_a_year_apart"
    assert refused["turnaround"]["ok"] is None


def test_an_UNVERIFIABLE_pair_still_names_the_turnaround_and_says_unverified():
    got = legs(eps=[0.30, 0.10, 0.09, 0.08, -0.20, 0.05], period_ok=None)
    assert got["turnaround"]["value"] == "to_profit"
    assert "unverified" in got["turnaround"]["value_note"]


# ── growth_streak: sales.compute's own count, never the pillar's `or 0` ───
def _nine_q():
    return [190.0, 180.0, 170.0, 160.0, 100.0, 95.0, 90.0, 85.0, 50.0]


def test_the_streak_fact_is_sales_computes_count_and_says_what_it_hides():
    got = legs(sales={"growth_yoy_pct": 60.0, "consecutive_growth_q": 3},
               rev=_nine_q())["growth_streak"]
    assert got["value"] == 3 and got["ok"] is None
    assert got["capped"] is False and got["history_ended"] is False
    assert got["n_pairs_available"] == 5
    for token in ("trailing", "forward", "not period-checked"):
        assert token in got["value_note"], token
    assert "counts up to %d quarters" % BP.STREAK_CAP in got["source"]


def test_a_streak_AT_the_counters_cap_says_so_rather_than_reading_as_exactly_four():
    got = legs(sales={"growth_yoy_pct": 60.0, "consecutive_growth_q": 4},
               rev=_nine_q())["growth_streak"]
    assert got["value"] == 4 and got["capped"] is True
    assert legs(sales={"growth_yoy_pct": 60.0, "consecutive_growth_q": 3},
                rev=_nine_q())["growth_streak"]["capped"] is False


def test_STREAK_CAP_is_pinned_equal_to_sales_computes_own_loop_bound():
    """`sales.py` is book-cited and guarded, so the bound is NAMED here and
    pinned to the engine's behaviour: an all-growth series twelve quarters long
    still stops at the cap. If that loop ever moves, this pin moves with it."""
    from sepa import sales as SA
    ever_growing = [100.0, 90.0, 80.0, 70.0, 60.0, 50.0, 40.0, 30.0,
                    20.0, 10.0, 5.0, 4.0]
    assert SA.compute(ever_growing)["consecutive_growth_q"] == BP.STREAK_CAP
    assert BP.STREAK_CAP == 4


def test_a_streak_that_ran_out_of_HISTORY_says_so_instead_of_reading_as_a_stall():
    """A count of two off six quarters of revenue is not "growth stopped" — it
    is "the series stopped". Reading the first as the second understates every
    young name on a board built out of young names."""
    got = legs(sales={"growth_yoy_pct": 60.0, "consecutive_growth_q": 2},
               rev=[190.0, 180.0, 170.0, 160.0, 100.0, 95.0])["growth_streak"]
    assert got["history_ended"] is True and got["n_pairs_available"] == 2
    assert "history ends" in got["value_note"]
    long_ = legs(sales={"growth_yoy_pct": 60.0, "consecutive_growth_q": 2},
                 rev=_nine_q())["growth_streak"]
    assert long_["history_ended"] is False


def test_an_UNVERIFIABLE_pair_outranks_the_history_note_on_the_streak():
    got = legs(sales={"growth_yoy_pct": 60.0, "consecutive_growth_q": 2},
               rev=[190.0, 180.0, 170.0, 160.0, 100.0, 95.0],
               period_ok=None)["growth_streak"]
    assert "unverified" in got["value_note"]


@pytest.mark.parametrize("sales", [
    None, {}, {"growth_yoy_pct": None, "consecutive_growth_q": 3},
    {"growth_yoy_pct": 60.0, "consecutive_growth_q": None},
    {"growth_yoy_pct": 60.0, "consecutive_growth_q": "abc"},
    {"growth_yoy_pct": 60.0, "consecutive_growth_q": float("nan")},
    {"growth_yoy_pct": 60.0, "consecutive_growth_q": {"bad": 1}},
])
def test_NEGATIVE_an_unreadable_sales_doc_is_UNKNOWN_and_never_an_exception(sales):
    """`legs_from_scan_row` runs OUTSIDE any try in `bonde.py::_row`: a bare
    int() on a Mongo value here is not a bad leg, it is the tab going down."""
    got = legs(sales=sales, rev=_nine_q())["growth_streak"]
    assert got["ok"] is None and got["why"] == "no_sales_read"
    assert got["value"] is None


def test_a_streak_STORED_AS_A_STRING_still_reads_as_a_number():
    got = legs(sales={"growth_yoy_pct": 60.0, "consecutive_growth_q": "3"},
               rev=_nine_q())["growth_streak"]
    assert got["value"] == 3


def test_NEGATIVE_the_streak_is_NOT_read_off_the_pillars_or_zero_copy():
    """`_bonde_pillar` coerces the count `or 0`, which turns "no read" into a
    zero streak. The leg reads `fundamentals.sales` and nothing else."""
    got = legs(sales={"growth_yoy_pct": 60.0, "consecutive_growth_q": 3},
               rev=_nine_q(), row={"consecutive_growth_q": 9})["growth_streak"]
    assert got["value"] == 3
    src = open(BP.__file__).read()
    streak_block = src.split("# Revenue growth streak", 1)[1].split("# Theme", 1)[0]
    assert 'row.get("consecutive_growth_q")' not in streak_block
    assert 'pillar.get("consecutive_growth_q")' not in streak_block


def test_a_refused_fiscal_pair_costs_the_streak_too():
    assert legs(sales={"growth_yoy_pct": 60.0, "consecutive_growth_q": 3},
                rev=_nine_q(), period_ok=False)["growth_streak"]["why"] \
        == "pair_not_a_year_apart"


# ── theme: the APP'S map, and a miss is a fact about the map ─────────────
def test_the_theme_fact_reads_the_apps_own_map_and_names_every_membership():
    from supply_demand.sectors import SECTOR_BY_ID
    got = legs("TER", sector="Technology")["theme"]
    assert got["ok"] is None and got["mapped"] is True
    assert "semi_materials" in got["ids"]
    assert SECTOR_BY_ID["semi_materials"]["label"] in got["value"]


def test_a_name_that_is_NOT_on_the_map_reads_UNMAPPED_never_themeless():
    """The map is an S&P-heavy roster and most of this board's small caps miss
    it. "none" would be a claim about the COMPANY off an absent roster row —
    module Rule 2. The miss is a fact about the MAP."""
    got = legs("ZZZZ", sector="Technology")["theme"]
    assert got["value"] == BP.THEME_UNMAPPED == "not on the app's map"
    assert got["mapped"] is False and got["ids"] == []
    assert got["ok"] is None
    assert "unmapped, not themeless" in got["source"]
    assert str(len(BP.THEME_MAP_TICKERS)) in got["source"]


def test_NEGATIVE_no_input_ever_makes_the_theme_leg_read_the_word_none():
    for sym in ("ZZZZ", "TER", "aapl", "0", "-"):
        assert legs(sym)["theme"]["value"] != "none"
        assert legs(sym)["theme"]["value"] != "None"


def test_NEGATIVE_a_row_with_no_symbol_cannot_be_looked_up_at_all():
    got = BP.legs_from_scan_row(scan_row("", sector="Technology"), pillar(),
                                {"period_ok": True}, True)
    assert got["theme"]["why"] == "no_symbol"
    assert got["theme"]["ok"] is None and got["theme"]["value"] is None
    assert "no_symbol" in BP.WHY_CODES


def test_THEME_MAP_TICKERS_is_DERIVED_from_the_roster_and_never_retyped():
    from supply_demand.sectors import SECTORS
    assert BP.THEME_MAP_TICKERS == {t for s in SECTORS for t in s["sp_tickers"]}
    assert len(BP.SECTORS) == len(SECTORS)
    crit = {c["key"]: c for c in BP.CRITERIA}
    assert "unmapped" in crit["theme"]["data"].lower()
    assert str(len(BP.THEME_MAP_TICKERS)) in crit["theme"]["data"]
    assert str(len(SECTORS)) in crit["theme"]["data"]


def test_SOURCE_GUARD_the_theme_map_module_reaches_no_reader_at_all():
    """It is imported at module scope and runs per row inside `board()`. A
    network or Mongo call in there is a provider read per name."""
    import supply_demand.sectors as S
    src = open(S.__file__).read()
    for token in ("requests", "pymongo", "httpx", "urllib"):
        assert token not in src, token


# ══════════════════════════════════════════════════ the cache legs, via attach
class _Readers:
    """The five bulk readers, monkeypatched by NAME so this file works whether
    or not they have landed yet — `attach` answers {} for a reader that is not
    there, which is the same answer as a cold cache."""

    PATHS = (("sepa.board_metrics", "snapshot"),
             ("sepa.earnings_watch", "last_report_map"),
             ("short_interest.client", "short_interest_map"),
             ("sepa.analyst_pulse", "coverage_map"),
             ("sepa.ipo_age", "listing_dates_map"))


def set_readers(monkeypatch, metrics=None, reports=None, si=None,
                analysts=None, listings=None, raise_all=False):
    maps = [metrics, reports, si, analysts, listings]
    for (path, name), payload in zip(_Readers.PATHS, maps):
        mod = importlib.import_module(path)

        if raise_all:
            def fn(*a, **k):
                raise RuntimeError("reader down")
        else:
            def fn(*a, _p=payload, **k):
                return dict(_p or {})
        monkeypatch.setattr(mod, name, fn, raising=False)


def attach_one(monkeypatch, **kw):
    rows = [{"symbol": "AAA", "pick": {"legs": {}}}]
    set_readers(monkeypatch, **kw)
    BP.attach(rows)
    return rows[0]["pick"]["legs"], rows[0]["pick"]


def test_EVERY_cold_cache_reads_UNKNOWN_with_the_reason_named(monkeypatch):
    got, _ = attach_one(monkeypatch)
    expect = {"surprise": "not_on_calendar", "float_25m": "no_metrics_doc",
              "cap_10b": "no_metrics_doc", "short_dtc_5": "not_warmed",
              "neglect_analysts": "no_analyst_doc", "ipo_10y": "no_listing_date"}
    for k, why in expect.items():
        assert got[k]["ok"] is None, k
        assert got[k]["why"] == why, k


def test_NEGATIVE_a_reader_that_RAISES_leaves_unknowns_and_never_the_board(monkeypatch):
    """`board()` runs inside crons. A reader that throws must cost six legs,
    not the tab."""
    got, _ = attach_one(monkeypatch, raise_all=True)
    assert all(leg["ok"] is None for leg in got.values())
    assert got["short_dtc_5"]["why"] == "not_warmed"


def test_attach_on_rows_with_no_symbol_does_not_raise():
    rows = [{"name": "nothing"}]
    BP.attach(rows)
    assert rows[0]["pick"]["n_unknown"] == 18


# ── surprise ──────────────────────────────────────────────────────────────
def _days_ago(n):
    from datetime import timedelta
    return (BP._today() - timedelta(days=n)).isoformat()


def test_a_STALE_surprise_is_LABELLED_and_still_counts_as_his_beat(monkeypatch):
    """Rule #7 is about the reported PERIOD, and a beat two quarters ago is
    still the last thing he had to react to. The label never flips the leg."""
    got, _ = attach_one(monkeypatch, reports={
        "AAA": {"date": _days_ago(200), "surprise_pct": 12.0}})
    leg = got["surprise"]
    assert leg["ok"] is True and leg["value"] == 12.0
    assert leg["stale"] is True and leg["age_days"] == 200


def test_a_FRESH_surprise_is_not_labelled_stale(monkeypatch):
    got, _ = attach_one(monkeypatch, reports={
        "AAA": {"date": _days_ago(30), "surprise_pct": 12.0}})
    assert got["surprise"]["stale"] is False and got["surprise"]["age_days"] == 30


def test_a_MISS_is_a_fail_and_a_report_without_a_surprise_is_unknown(monkeypatch):
    got, _ = attach_one(monkeypatch, reports={
        "AAA": {"date": _days_ago(10), "surprise_pct": -8.0}})
    assert got["surprise"]["ok"] is False
    got, _ = attach_one(monkeypatch, reports={"AAA": {"date": _days_ago(10)}})
    assert got["surprise"]["ok"] is None
    assert got["surprise"]["why"] == "no_surprise_in_report"


def test_the_SURPRISE_leg_is_byte_identical_but_for_the_served_stale_bound(
        monkeypatch):
    """The hover used to print the ROW'S OWN AGE as the bound ("older than 200
    days"). The bound is the app's constant, so it is served; every other key
    on a leg he already reads is unchanged."""
    got, _ = attach_one(monkeypatch, reports={
        "AAA": {"date": _days_ago(200), "surprise_pct": 12.0}})
    assert got["surprise"] == {
        "ok": True, "value": 12.0, "why": None, "as_of": _days_ago(200),
        "age_days": 200, "stale": True, "stale_after": BP.SURPRISE_STALE_DAYS,
        "source": "earnings_calendar (sepa/earnings_watch)"}
    assert BP.SURPRISE_STALE_DAYS == 157


# ── report age ────────────────────────────────────────────────────────────
def test_the_report_age_fact_is_the_SAME_doc_the_surprise_leg_reads(monkeypatch):
    got, _ = attach_one(monkeypatch, reports={
        "AAA": {"date": _days_ago(10), "surprise_pct": 12.0}})
    leg = got["report_age"]
    assert leg["ok"] is None and leg["value"] == 10
    assert leg["as_of"] == _days_ago(10)
    assert leg["stale"] is False
    assert leg["stale_after"] == BP.SURPRISE_STALE_DAYS
    assert leg["age_days"] == got["surprise"]["age_days"]
    assert "the same doc as the surprise leg" in leg["source"]


def test_a_report_older_than_the_apps_label_is_labelled_and_still_a_fact(monkeypatch):
    got, _ = attach_one(monkeypatch, reports={
        "AAA": {"date": _days_ago(200), "surprise_pct": 12.0}})
    assert got["report_age"]["stale"] is True
    assert got["report_age"]["ok"] is None          # the label never makes a verdict


def test_NEGATIVE_a_calendar_row_with_no_readable_PAST_date_is_unknown(monkeypatch):
    """A future date would render as the freshest report on the board, and a
    zero-day report age reads as "reported today" on a name that never did."""
    from datetime import timedelta
    got, _ = attach_one(monkeypatch)
    assert got["report_age"]["why"] == "not_on_calendar"
    got, _ = attach_one(monkeypatch, reports={"AAA": {"date": "nope",
                                                      "surprise_pct": 1.0}})
    assert got["report_age"]["ok"] is None
    assert got["report_age"]["why"] == "not_on_calendar"
    assert "no readable past date" in got["report_age"]["value_note"]
    future = (BP._today() + timedelta(days=30)).isoformat()
    got, _ = attach_one(monkeypatch, reports={"AAA": {"date": future,
                                                      "surprise_pct": 1.0}})
    assert got["report_age"]["why"] == "not_on_calendar"


def test_the_report_age_leg_costs_NO_extra_bulk_read():
    """Five readers, and the age comes off the surprise leg's own doc."""
    assert len(_Readers.PATHS) == 5
    src = open(BP.__file__).read()
    body = src.split("def attach(", 1)[1].split("\ndef _count", 1)[0]
    assert body.count("_read(") == 5


def test_the_stale_bound_is_BUILT_from_the_named_freshness_constants():
    """Rule #7's constants by name, never a number typed twice."""
    from observability.period_freshness import FILING_LAG_DAYS, GRACE_DAYS
    assert BP.SURPRISE_STALE_DAYS == BP.QUARTER_DAYS + FILING_LAG_DAYS + GRACE_DAYS
    assert BP.SURPRISE_STALE_DAYS == 157


# ── float / cap ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("shares,ok,tier", [
    (9_900_000, True, "best"),
    (24_900_000, True, "ideal"),
    (40_000_000, False, None),
    (100_000_000, False, "pullback_prone"),
])
def test_the_float_leg_carries_BOTH_of_his_bands_and_his_pullback_warning(
        monkeypatch, shares, ok, tier):
    got, _ = attach_one(monkeypatch, metrics={"AAA": {"float_shares": shares}})
    assert got["float_25m"]["ok"] is ok
    assert got["float_25m"]["tier"] == tier


def test_a_metrics_doc_WITHOUT_the_float_key_is_not_the_same_as_no_doc(monkeypatch):
    """Docs cached before 2026-09-20 have no float at all. Reading that as 'no
    doc' would tell him to run a warm that has already run."""
    got, _ = attach_one(monkeypatch, metrics={"AAA": {"market_cap": 1e9}})
    assert got["float_25m"]["why"] == "no_float_in_doc"
    assert got["cap_10b"]["ok"] is True


def test_the_cap_leg_passes_at_his_PROSE_bound(monkeypatch):
    got, _ = attach_one(monkeypatch, metrics={"AAA": {"market_cap": 9.9e9}})
    assert got["cap_10b"]["ok"] is True
    got, _ = attach_one(monkeypatch, metrics={"AAA": {"market_cap": 1.05e10}})
    assert got["cap_10b"]["ok"] is False        # his scan line says 11B — §7.7
    got, _ = attach_one(monkeypatch, metrics={"AAA": {"float_shares": 1e6}})
    assert got["cap_10b"]["why"] == "no_cap_in_doc"


# ── short interest ────────────────────────────────────────────────────────
def test_a_REMEMBERED_MISS_is_not_the_same_answer_as_NEVER_WARMED(monkeypatch):
    got, _ = attach_one(monkeypatch, si={"AAA": {"settlement_date": None}})
    assert got["short_dtc_5"]["why"] == "no_si_record"
    got, _ = attach_one(monkeypatch)
    assert got["short_dtc_5"]["why"] == "not_warmed"


def test_the_days_to_cover_leg_sits_on_his_five_and_keeps_ok_when_stale(monkeypatch):
    got, _ = attach_one(monkeypatch, si={"AAA": {
        "settlement_date": "2026-08-31", "days_to_cover": 6.1,
        "pct_of_shares": 19.46, "stale": True, "age_days": 60}})
    leg = got["short_dtc_5"]
    assert leg["ok"] is True and leg["stale"] is True
    assert leg["as_of"] == "2026-08-31" and leg["pct_of_shares"] == 19.46
    got, _ = attach_one(monkeypatch, si={"AAA": {
        "settlement_date": "2026-08-31", "days_to_cover": 4.9}})
    assert got["short_dtc_5"]["ok"] is False
    assert BP.SHORT_DTC_MIN == 5.0


# ── analysts ──────────────────────────────────────────────────────────────
def test_NO_COVERAGE_is_his_criterion_and_the_reading_is_labelled(monkeypatch):
    """Yahoo never prints a zero — an EMPTY estimate frame is the only evidence
    of no coverage there is, so the ✓ says out loud where it came from and that
    the reading is pending his nod."""
    got, _ = attach_one(monkeypatch, analysts={"AAA": {"n_analysts": 0}})
    leg = got["neglect_analysts"]
    assert leg["ok"] is True
    assert leg["source"] == "Yahoo carries no estimate rows"
    assert leg["his_call"] and len(leg["his_call"]) > 20


def test_a_COVERED_name_fails_the_leg_and_says_by_how_many(monkeypatch):
    got, _ = attach_one(monkeypatch, analysts={"AAA": {"n_analysts": 3}})
    assert got["neglect_analysts"]["ok"] is False
    assert got["neglect_analysts"]["value_note"] == "covered by 3"


def test_NEGATIVE_an_unread_estimate_frame_is_unknown_never_no_coverage(monkeypatch):
    """A doc that predates the count, or a property that raised, is silence.
    Reading silence as 'no analyst coverage' ticks his criterion on a name the
    whole street follows."""
    got, _ = attach_one(monkeypatch, analysts={"AAA": {"n_analysts": None}})
    assert got["neglect_analysts"]["ok"] is None
    assert got["neglect_analysts"]["why"] == "no_estimate_read"
    got, _ = attach_one(monkeypatch)
    assert got["neglect_analysts"]["why"] == "no_analyst_doc"


# ── listing date ──────────────────────────────────────────────────────────
def test_the_ipo_leg_is_years_since_listing_and_names_its_own_weakness(monkeypatch):
    got, _ = attach_one(monkeypatch, listings={"AAA": "2019-01-01"})
    leg = got["ipo_10y"]
    assert leg["ok"] is True and leg["as_of"] == "2019-01-01"
    assert isinstance(leg["value"], float) and leg["value"] > 5
    assert "uncorroborated" in leg["source"]
    got, _ = attach_one(monkeypatch, listings={"AAA": "1995-01-01"})
    assert got["ipo_10y"]["ok"] is False


def test_NEGATIVE_a_listing_date_in_the_FUTURE_is_unknown_not_a_zero_year_old(
        monkeypatch):
    """A recycled ticker's profile date is the classic corruption here, and a
    future one would render as the youngest name on the board."""
    from datetime import timedelta
    future = (BP._today() + timedelta(days=30)).isoformat()
    got, _ = attach_one(monkeypatch, listings={"AAA": future})
    assert got["ipo_10y"]["ok"] is None
    assert got["ipo_10y"]["why"] == "future_listing_date"
    got, _ = attach_one(monkeypatch, listings={"AAA": "not-a-date"})
    assert got["ipo_10y"]["why"] == "no_listing_date"


# ══════════════════════════════════════════════════════ counts and coverage
def test_the_counts_always_add_up_to_his_eighteen_computed_criteria(monkeypatch):
    _, pick = attach_one(monkeypatch, metrics={"AAA": {"market_cap": 1e9,
                                                       "float_shares": 5e6}})
    assert pick["n_pass"] + pick["n_fail"] + pick["n_unknown"] == 18


def test_coverage_says_what_is_KNOWN_per_leg_over_the_rows(monkeypatch):
    rows = [{"symbol": "AAA", "pick": {"legs": {}}},
            {"symbol": "BBB", "pick": {"legs": {}}}]
    set_readers(monkeypatch, metrics={"AAA": {"market_cap": 1e9}})
    BP.attach(rows)
    cov = BP.coverage(rows)
    assert cov["cap_10b"] == {"known": 1, "rows": 2}
    assert cov["short_dtc_5"] == {"known": 0, "rows": 2}
    assert set(cov) == set(BP.COMPUTED_KEYS)


def test_the_legend_is_SERVED_whole_and_says_the_entries_are_his():
    lg = BP.legend()
    assert lg["header"] == BP.PICK_HEADER
    assert "entries are yours" in lg["header"]
    assert "nothing on it is measured" in lg["header"]
    assert lg["criteria"] is BP.CRITERIA
    assert lg["computed_keys"] == BP.COMPUTED_KEYS
    assert "YouTube" in lg["not_a_source"]
    assert "warm-si" in lg["warm_note"]


def test_a_FACT_leg_counts_as_KNOWN_when_it_carries_a_VALUE(monkeypatch):
    """A fact leg has no `ok` by construction, so the old rule read
    `fund_holding` as 0 of N on a board where it is filled nearly everywhere."""
    rows = [{"symbol": "AAA", "pick": {"legs": {
                "fund_holding": BP._fact(60.0), "theme": BP._fact("x")}}},
            {"symbol": "BBB", "pick": {"legs": {
                "fund_holding": BP._leg(why="no_inst_read")}}}]
    set_readers(monkeypatch)
    BP.attach(rows)
    cov = BP.coverage(rows)
    assert set(cov) == set(BP.COMPUTED_KEYS) and len(cov) == 18
    assert cov["fund_holding"] == {"known": 1, "rows": 2}
    assert cov["theme"] == {"known": 1, "rows": 2}
    assert cov["report_age"] == {"known": 0, "rows": 2}   # cold calendar


def test_the_legend_carries_the_TAPE_as_a_source_and_names_the_fact_legs():
    lg = BP.legend()
    assert lg["tape_header"]["ts"] == "0:14:17"
    assert lg["tape_header"]["url"].endswith("&t=857s")
    assert lg["tape"]["published"] == "2026-02-18" == BP.TAPE_DATE
    assert lg["tape"]["recorded"] == "~June 2025" == BP.TAPE_RECORDED
    assert lg["tape"]["received"] == "2026-09-20"
    assert lg["tape"]["url"] == BP.TAPE_URL
    assert lg["tape"]["show"] == BP.TAPE_SHOW and lg["tape"]["title"] == BP.TAPE_TITLE
    assert lg["tape"]["recorded_cite"]["ts"] == "1:05:11"
    assert lg["fact_keys"] == list(BP.FACT_KEYS)


def test_NOT_A_SOURCE_now_says_the_SUMMARY_was_never_one_and_the_TAPE_is():
    src = BP.NOT_A_SOURCE
    for token in ("YouTube", "SUMMARY", "timestamp", "received 2026-09-20"):
        assert token in src, token
    assert "never received" not in src


# ══════════════════════════════════════════ the board, end to end, offline
def _stub_board(monkeypatch, rows, **readers):
    from sepa import scanner, board_metrics as BM, buyable_verdict as BV
    monkeypatch.setattr(scanner, "load_latest", lambda *a, **k: {"all_results": rows})
    monkeypatch.setattr(BD, "_pivots", lambda *a, **k: {})
    monkeypatch.setattr(BD, "regime_state", lambda *a, **k: {"scanners_paused": False})
    monkeypatch.setattr(BM, "attach", lambda *a, **k: None)
    monkeypatch.setattr(FS, "record", lambda *a, **k: 0)
    monkeypatch.setattr(FS, "newly_found", lambda *a, **k: set())
    monkeypatch.setattr(FS, "first_seen_map", lambda *a, **k: {})
    assert hasattr(BV, "_bonde_pillar")
    set_readers(monkeypatch, **readers)
    return BD.board()


def _branchy_rows():
    """One row per branch this module has: a clean name, no series, a negative
    year-ago base, a non-adjacent pair, a refused pair, no period keys, and a
    row with no sector at all."""
    ok_p = [8105, 8104, 8103, 8102, 8101, 8100]
    s = {"score": 80, "tier": "strong", "growth_yoy_pct": 60.0,
         "prior_yoy_pct": 55.0, "accelerating": True, "consecutive_growth_q": 4}
    return [
        scan_row("CLEAN", eps=[0.30, 0.10, 0.09, 0.08, 0.10, 0.05],
                 periods=ok_p, sector="Technology", inst=30.0, sales=dict(s)),
        scan_row("NOEPS", periods=ok_p, sector="Healthcare", sales=dict(s)),
        scan_row("LOSSY", eps=[0.30, 0.10, 0.09, 0.08, -0.20, 0.05],
                 periods=ok_p, sector="Energy", sales=dict(s)),
        scan_row("GAPPY", eps=[0.30, 0.10, 0.09], periods=[8105, 8103, 8102],
                 sector="Technology", sales=dict(s)),
        scan_row("BADPAIR", eps=[0.30, 0.10, 0.09, 0.08, 0.10, 0.05],
                 periods=[8105, 8104, 8103, 8102, 8098, 8097],
                 sector="Technology", sales=dict(s)),
        scan_row("NOKEYS", eps=[0.30, 0.10, 0.09, 0.08, 0.10, 0.05],
                 sector="Technology", sales=dict(s)),
        scan_row("NOSECT", eps=[0.30, 0.10, 0.09, 0.08, 0.10, 0.05],
                 periods=ok_p, sales=dict(s)),
    ]


def test_EVERY_why_served_by_a_real_board_is_in_the_ONE_vocabulary(monkeypatch):
    """THE PIN BEHIND THE FRONTEND'S WHY_TEXT. Every branch of every leg is
    walked through the real `board()`, and a code with no sentence beside it
    would reach the page as a raw token."""
    b = _stub_board(monkeypatch, _branchy_rows(),
                    metrics={"CLEAN": {"market_cap": 1e9, "float_shares": 5e6}},
                    reports={"CLEAN": {"date": _days_ago(10), "surprise_pct": 5.0}},
                    si={"CLEAN": {"settlement_date": None}},
                    analysts={"CLEAN": {"n_analysts": 0},
                              "LOSSY": {"n_analysts": None}},
                    listings={"CLEAN": "2019-01-01"})
    seen = set()
    n_rows = 0
    for sec in b["sections"].values():
        for r in sec:
            n_rows += 1
            legs_ = r["pick"]["legs"]
            assert set(legs_) == set(BP.COMPUTED_KEYS), r["symbol"]
            for k, leg in legs_.items():
                assert leg["why"] is None or leg["why"] in BP.WHY_CODES, (k, leg)
                seen.add(leg["why"])
            assert (r["pick"]["n_pass"] + r["pick"]["n_fail"]
                    + r["pick"]["n_unknown"]) == 18, r["symbol"]
    assert n_rows >= 6
    # the branches really were exercised, not merely tolerated
    for why in ("no_eps_series", "year_ago_loss", "seq_not_adjacent",
                "no_sector", "not_on_calendar", "no_si_record"):
        assert why in seen, why
    assert b["pick_legend"]["why_codes"] == sorted(BP.WHY_CODES)
    assert set(b["pick_coverage"]) == set(BP.COMPUTED_KEYS)


def test_NO_ROW_of_a_REAL_board_ever_ticks_or_crosses_a_FACT_leg(monkeypatch):
    """The end-to-end pin behind the frontend's fact guard: a served `ok True`
    on one of these five is a threshold this app invented, in his voice."""
    b = _stub_board(monkeypatch, _branchy_rows(),
                    reports={"CLEAN": {"date": _days_ago(10), "surprise_pct": 5.0}})
    n = 0
    values = set()
    for sec in b["sections"].values():
        for r in sec:
            n += 1
            for k in BP.FACT_KEYS:
                leg = r["pick"]["legs"][k]
                assert leg["ok"] is None, (r["symbol"], k)
                if k == "theme":
                    values.add(leg["value"])
    assert n >= 6
    # every branchy row is a made-up ticker, so they all miss the map — and a
    # miss reads as a fact about the MAP, never as the word "none"
    assert values == {BP.THEME_UNMAPPED}
    assert "none" not in values


def test_NEGATIVE_the_whole_board_makes_ZERO_network_calls(monkeypatch):
    """The cost rule: five bulk Mongo reads and nothing else. A provider read
    per row is how a tab stops being served."""
    import requests

    def boom(*a, **k):
        raise AssertionError("the board path reached the network")

    for name in ("get", "post", "request"):
        monkeypatch.setattr(requests, name, boom)
    b = _stub_board(monkeypatch, _branchy_rows())
    assert b["sections"]["strong"]
    assert all(r["pick"]["legs"]["short_dtc_5"]["ok"] is None
               for v in b["sections"].values() for r in v)


def test_a_pivot_mismatch_row_carries_UNKNOWN_y_slash_y_legs(monkeypatch):
    """Those rows have their growth numbers BLANKED after `_row` builds them.
    The legs must not depend on which happened first."""
    rows = _branchy_rows()
    b = _stub_board(monkeypatch, rows)
    by_sym = {r["symbol"]: r for v in b["sections"].values() for r in v}
    bad = by_sym.get("BADPAIR")
    if bad is not None:
        for k in ("eps_yoy_100", "sales_5", "rev_39_x2", "eps_accel"):
            assert bad["pick"]["legs"][k]["ok"] is None, k
            assert bad["pick"]["legs"][k]["why"] == "pair_not_a_year_apart", k


def test_the_board_serves_the_legend_ONCE_and_never_a_count_to_render(monkeypatch):
    b = _stub_board(monkeypatch, _branchy_rows())
    assert b["pick_legend"]["header"] == BP.PICK_HEADER
    assert len(b["pick_legend"]["criteria"]) == 27
    # served for the doc and coverage, and rendered nowhere — the FE contract
    # sweep pins that the components never read these three.
    row = next(r for v in b["sections"].values() for r in v)
    assert {"n_pass", "n_fail", "n_unknown"} <= set(row["pick"])


# ══════════════════════════════════════════════════════════ import hygiene
def test_SOURCE_GUARD_the_five_readers_are_imported_INSIDE_attach():
    """`short_interest.client._main` imports `sepa.bonde`, which imports this
    module. A top-level import in either direction closes the cycle."""
    src = open(BP.__file__).read()
    head = src.split("def attach(", 1)[0]
    imports = [ln.strip() for ln in head.splitlines()
               if ln.startswith(("import ", "from "))]      # top level only
    for token in ("short_interest", "board_metrics", "analyst_pulse",
                  "ipo_age", "earnings_watch"):
        assert not any(token in ln for ln in imports), token
    # and what it DOES import at module level: the constants it must not retype
    assert any("from sepa.sales import SALES_FLOOR_PCT" in ln for ln in imports)
    assert any("period_freshness" in ln for ln in imports)


def test_SOURCE_GUARD_bonde_picks_never_imports_the_board_it_feeds():
    src = open(BP.__file__).read()
    assert "import bonde" not in src
    assert "from sepa.bonde" not in src


def test_SOURCE_GUARD_the_module_says_nothing_here_is_measured():
    src = open(BP.__file__).read()
    assert "NOTHING HERE IS MEASURED" in src
    assert "YouTube summary is NOT a source" in src or "YouTube" in BP.NOT_A_SOURCE


def test_SOURCE_GUARD_the_leg_docstrings_count_the_legs_they_actually_fill():
    """A docstring that names a count is a claim; it moves when the tuple does."""
    words = {8: "eight", 7: "seven", 11: "eleven", 6: "six"}
    scan_doc = BP.legs_from_scan_row.__doc__ or ""
    cache_doc = BP.attach.__doc__ or ""
    assert f"{words[len(BP.SCAN_KEYS)]} legs" in scan_doc
    assert f"{words[len(BP.CACHE_KEYS)]} cache legs" in cache_doc
    # NEGATIVE: the pre-refix counts must be gone from both docstrings
    assert "eight legs" not in scan_doc
    assert "six cache legs" not in cache_doc
    assert len(BP.SCAN_KEYS) == 11 and len(BP.CACHE_KEYS) == 7
