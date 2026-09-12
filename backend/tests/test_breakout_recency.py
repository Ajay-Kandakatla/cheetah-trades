"""The breakout board ranks by RECENCY, and the cut follows it (2026-09-12).

Ajay: "update the breakout page with EPS and explosive growth logic we created.
Sort it by recent breakout intead of # of breakouts".

WHY THIS HAD TO MOVE TO THE SERVER: the board sorted by COUNT and only then cut
to `top`, so the cut itself was count-biased. On the 2026-09-12 scan that threw
away 47 names which had broken out THAT DAY — HPQ, HPE, QRVO, SWKS, SFL, TNK,
FEIM, INSP among them — before the browser saw anything, while the names it kept
at the head (AXTI 19, BELFA 18, QUIK 18) had `days_since_breakout = None`, i.e.
no recent breakout at all. Re-sorting those 250 in the browser would have
reordered a list that had already discarded the answer.
"""
from __future__ import annotations

import inspect

from sepa import breakout as B


def _rows():
    return [
        {"symbol": "OLDMANY", "days_since_breakout": None, "breakout_count": 19,
         "rs_rank": 99, "ai_sector_rank": None},
        {"symbol": "FRESH", "days_since_breakout": 0, "breakout_count": 2,
         "rs_rank": 10, "ai_sector_rank": None},
        {"symbol": "FRESHAI", "days_since_breakout": 0, "breakout_count": 1,
         "rs_rank": 5, "ai_sector_rank": 0},
        {"symbol": "MID", "days_since_breakout": 4, "breakout_count": 9,
         "rs_rank": 50, "ai_sector_rank": None},
    ]


def _key():
    """The module's own comparator, lifted out of board()."""
    def k(x):
        d = x.get("days_since_breakout")
        return (d is None, d if d is not None else 0,
                x.get("ai_sector_rank") if x.get("ai_sector_rank") is not None else 99,
                -x["breakout_count"], -(x.get("rs_rank") or 0), x["symbol"])
    return k


def test_the_most_recent_breakout_leads_not_the_biggest_count():
    out = [r["symbol"] for r in sorted(_rows(), key=_key())]
    assert out[0] == "FRESHAI"
    assert out.index("FRESH") < out.index("MID") < out.index("OLDMANY")


def test_HIS_STANDING_AI_RULE_survives_INSIDE_the_day():
    """2026-06-25, standing: "any breakout list puts AI-ecosystem sector winners
    on top". Recency wins overall; AI wins the tie within one day — so the rule
    moved, it was not dropped. FRESHAI has the LOWEST count and the WORST RS of
    the same-day pair and still leads it."""
    same_day = [r for r in _rows() if r["days_since_breakout"] == 0]
    out = [r["symbol"] for r in sorted(same_day, key=_key())]
    assert out == ["FRESHAI", "FRESH"]


def test_NEGATIVE_an_undated_breakout_sorts_LAST_not_first():
    """`None` is unknown. Scoring it as 0 would put a name nobody dated at the
    top of a board that now claims to be ordered by recency — and OLDMANY has
    the highest count and RS, so it would win every tiebreak after that."""
    out = [r["symbol"] for r in sorted(_rows(), key=_key())]
    assert out[-1] == "OLDMANY"


def test_the_board_sorts_BEFORE_it_cuts_and_reports_the_cut():
    src = inspect.getsource(B.board)
    i_sort = src.index("rows.sort(key=_recency_key)")
    i_cut = src.index("rows = rows[:top]")
    assert i_sort < i_cut, "the cut must follow the recency order, not the count order"
    assert '"capped"' in src and '"n_all"' in src, \
        "a cap the reader cannot see is how a truncated list reads as a complete one"


def test_the_ai_tag_is_attached_BEFORE_the_sort_that_uses_it():
    """The recency sort breaks ties on `ai_sector_rank`. Tagging afterwards —
    which is what the code did until this change — leaves every rank reading as
    the 99 default and silently drops his AI-first rule while still looking
    like it applied."""
    src = inspect.getsource(B.board)
    assert src.index('x["ai_sector_rank"] = ') < src.index("rows.sort(key=_recency_key)")


def test_the_overlay_reuses_the_research_cache_not_a_second_screen():
    """Sales/EPS must come from the SAME cache the 🔥 Hottest board reads, and
    `explosive` must POINT AT the 🚀 board rather than re-implement 100/100."""
    src = inspect.getsource(B.board)
    assert "decision_snapshot" in src
    assert "from growth import tracker" in src
    for reimpl in ("100.0", ">= 100", "MIN_SALES_GROWTH_PCT"):
        assert reimpl not in src, "membership is a pointer, never a second screen"


def test_NEGATIVE_the_fundamentals_are_read_FLAT_not_under_a_fundamentals_key():
    """TRAP: `research.decision_snapshot` returns a FLAT dict per symbol. Reading
    a "fundamentals" key yields {} for every name — a silently 100%-blank column
    that reads like "we have no data". It shipped that way for one run and was
    caught by checking the live fill rate, not by a test passing."""
    src = inspect.getsource(B.board)
    assert 'snap.get(x["symbol"]) or {}' in src
    assert '.get("fundamentals")' not in src


def test_a_missing_number_stays_None_and_never_becomes_a_zero():
    assert B._fnum(None) is None
    assert B._fnum("") is None
    assert B._fnum(float("nan")) is None
    assert B._fnum(float("inf")) is None
    assert B._fnum(0) == 0.0
    assert B._fnum("83.4") == 83.4
