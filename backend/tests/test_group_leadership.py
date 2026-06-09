"""Behavioral tests for sepa.group_leadership (Minervini Ch.6, p.95-116).

Group source is yfinance industry via companies.store; here we inject an
``industry_map`` so the test is deterministic and offline. The annotation is
DISPLAY-only — it must never touch score / is_candidate (asserted below).
"""
from __future__ import annotations

from sepa import group_leadership as gl


def _row(symbol, rs, score=50, is_candidate=True):
    return {"symbol": symbol, "rs_rank": rs, "score": score, "is_candidate": is_candidate}


def test_group_leader_and_laggard_within_group():
    rows = [
        _row("NVDA", 98), _row("AVGO", 95), _row("AMD", 90), _row("INTC", 60),  # Semis
        _row("LLY", 97), _row("NVO", 70),                                        # Pharma
    ]
    imap = {
        "NVDA": ("Semiconductors", "Technology"),
        "AVGO": ("Semiconductors", "Technology"),
        "AMD": ("Semiconductors", "Technology"),
        "INTC": ("Semiconductors", "Technology"),
        "LLY": ("Drug Manufacturers", "Healthcare"),
        "NVO": ("Drug Manufacturers", "Healthcare"),
    }
    gl.annotate(rows, industry_map=imap)
    by = {r["symbol"]: r for r in rows}

    # Semis: NVDA/AVGO/AMD are top-3 leaders; INTC (98-60=38 >= 20 gap) is a laggard.
    assert by["NVDA"]["group_leader"] is True and by["NVDA"]["group_rs_rank"] == 1
    assert by["AVGO"]["group_leader"] is True
    assert by["AMD"]["group_leader"] is True and by["AMD"]["group_rs_rank"] == 3
    assert by["INTC"]["group_leader"] is False and by["INTC"]["is_laggard"] is True
    assert by["INTC"]["group_leader_symbol"] == "NVDA"
    assert by["NVDA"]["group_size"] == 4

    # Pharma: LLY leads; NVO gap is 97-70=27 >= 20 -> laggard.
    assert by["LLY"]["group_leader"] is True
    assert by["NVO"]["is_laggard"] is True and by["NVO"]["group_leader_symbol"] == "LLY"


def test_close_rs_is_not_a_laggard():
    """A second-tier name within the laggard gap is NOT flagged a laggard."""
    rows = [_row("A", 90), _row("B", 80), _row("C", 75)]  # all within 20 of the top
    imap = {s: ("Software", "Technology") for s in ("A", "B", "C")}
    gl.annotate(rows, industry_map=imap)
    for r in rows:
        assert r["is_laggard"] is False
    # top 3 of a 3-member group are all leaders
    assert all(r["group_leader"] for r in rows)


def test_singleton_group_has_no_leader_or_laggard():
    rows = [_row("SOLO", 99), _row("X", 80), _row("Y", 50)]
    imap = {"SOLO": ("Uranium", "Energy"), "X": ("Software", "Technology"),
            "Y": ("Software", "Technology")}
    gl.annotate(rows, industry_map=imap)
    solo = next(r for r in rows if r["symbol"] == "SOLO")
    assert solo["group_size"] == 1
    assert solo["group_leader"] is False and solo["is_laggard"] is False
    assert solo["group_rs_rank"] is None


def test_missing_industry_degrades_gracefully():
    rows = [_row("AAA", 95), _row("BBB", 40)]
    gl.annotate(rows, industry_map={})  # no industry data at all
    for r in rows:
        assert r["industry"] is None
        assert r["group_leader"] is False and r["is_laggard"] is False
        assert r["group_rs_rank"] is None
        # all annotated keys present even when ungrouped (no KeyError downstream)
        for k in gl.ANNOTATED_KEYS:
            assert k in r


def test_none_rs_rank_is_skipped():
    rows = [_row("A", None), _row("B", 90), _row("C", 50)]
    imap = {s: ("Banks", "Financial Services") for s in ("A", "B", "C")}
    gl.annotate(rows, industry_map=imap)
    by = {r["symbol"]: r for r in rows}
    assert by["A"]["group_rs_rank"] is None  # no RS -> not ranked
    # B and C still form a 2-member group
    assert by["B"]["group_size"] == 2 and by["B"]["group_leader"] is True


def test_annotation_never_mutates_score_or_gate():
    """DISPLAY-only contract: score / is_candidate must be byte-identical after."""
    rows = [_row("NVDA", 98, score=88, is_candidate=True),
            _row("INTC", 55, score=41, is_candidate=False)]
    imap = {"NVDA": ("Semiconductors", "Technology"), "INTC": ("Semiconductors", "Technology")}
    before = [(r["score"], r["is_candidate"]) for r in rows]
    gl.annotate(rows, industry_map=imap)
    after = [(r["score"], r["is_candidate"]) for r in rows]
    assert before == after
