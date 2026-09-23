"""🔥 Hottest — the sector / industry / roster rows go live with the names.

Ajay, 2026-09-23, on a rotating Wednesday morning:

    "I think the sector rotation is wrong.. Can you show me till or current
     market instead of last close. Its actualy rotating this morning I wanna
     see live rotattion"

He was right and the board was internally inconsistent. Measured on the live
board at 10:44 ET that morning: the NAME rows were live (1,751 of 1,753 priced
against RSP's own live move) while every group row sat on the 2026-09-22 close,
and **19 of the 29 roster rows carried the OPPOSITE SIGN to their own members'
live median** — `semi_materials` printed +3.94 over a cohort trading at −1.53.

WHAT THESE TESTS EXIST TO PROTECT
─────────────────────────────────
1. NEVER HALF-LIVE. A member with no live print is LEFT OUT of the live median,
   never folded in at its last-close move. That was the original objection to
   a live group row and it stays enforced — the fix is a stated cohort, not a
   blend.
2. THE COHORT IS STATED AND COUNTED. `d1_live_n` / `d1_live_of` ride on the
   row, and the cell prints them when they differ.
3. `rel_1d_close` IS NOT TOUCHED. A SECTOR row's close median is over the
   rotation grid's own SAMPLE (n=40 of 308 for Technology); the live median is
   over the full membership. They are NOT a before/after pair, so
   `d1_live_close` carries the same-cohort close beside them and nothing here
   ever differences the other two.
4. THE MEDIANS USE THE FULL MEMBER LIST, never the served `names` array — that
   array is truncated to `names_per_group` AFTER the sort, so it is the top of
   the board, not a sample of it.
5. NO LIVE READ → BYTE-IDENTICAL to what this board served before. Same for a
   row where not one member printed: it falls back to the close whole and is
   marked, rather than wearing a live header over a close number.
6. `group_basis` STAYS A TOKEN. The FE's `HsD1Source` union switches on it; a
   sentence in that field is how a board starts string-matching prose.
"""
from __future__ import annotations

import math

from rotation import hottest as H
from rotation import tracker as T


# ── fixture ─────────────────────────────────────────────────────────────────
# Four members of one roster. The close leg and the live leg disagree in SIGN,
# which is the whole point: on the close this roster is hot, on the tape it is
# not. DARK has no live print and its close move is enormous — if it ever leaks
# into the live median the assertions below move loudly.
BY_SYMBOL = {
    "AAA": {"sector": "Technology", "industry": "Semis", "name": "Aaa Inc",
            "last_close": 10.0, "ret_1d": 3.0, "ret_5d": 2.0, "ret_21d": 5.0},
    "BBB": {"sector": "Technology", "industry": "Semis", "name": "Bbb Inc",
            "last_close": 20.0, "ret_1d": 4.0, "ret_5d": 3.0, "ret_21d": 6.0},
    "CCC": {"sector": "Technology", "industry": "Semis", "name": "Ccc Inc",
            "last_close": 30.0, "ret_1d": 5.0, "ret_5d": 4.0, "ret_21d": 7.0},
    "DARK": {"sector": "Technology", "industry": "Semis", "name": "Dark Inc",
             "last_close": 40.0, "ret_1d": 90.0, "ret_5d": 5.0, "ret_21d": 8.0},
}
BENCH = {"ret_1d": 1.0, "ret_5d": 1.0, "ret_21d": 1.0}


def _payload():
    syms = list(BY_SYMBOL)
    return {
        "as_of": "2026-09-22", "benchmark": "RSP",
        "sectors": [{"group": "Technology", "n": 40, "dropped": 0,
                     "rel_1d": 2.55, "rel_5d": 1.0, "rel_21d": 3.0,
                     "pct_positive_1d": 80.0}],
        "industries": [],
        "themes": [],
        "sampled": {"Technology": {"of": 308, "used": 40}},
        T.MEMBERS_KEY: {
            "by_symbol": BY_SYMBOL,
            "groups": {"sector": {"Technology": {"symbols": syms, "median_21d": 6.0}},
                       "industry": {}, "cohort": {},
                       "theme": {"ai_semis": {"symbols": syms, "median_21d": 6.0}}},
            "benchmark": BENCH,
        },
    }


def _live(moves: dict, bench_move: float = 0.0, ok: bool = True) -> dict:
    return {"basis": H.D1_LIVE if ok else H.D1_CLOSE, "live": ok,
            "benchmark": "RSP", "benchmark_move": bench_move,
            "symbols": len(BY_SYMBOL), "live_names": len(moves),
            "moves": dict(moves), "as_of": "2026-09-23T14:44:30+00:00",
            "reason": None, "market_closed": None, "in_session": True,
            "session_window": "9:30-16:00 ET"}


# Three names print red, DARK stays dark. Relative = move − bench(0.0).
LIVE_3 = {"AAA": -3.0, "BBB": -2.0, "CCC": -1.0}


def _build(live=None, **kw):
    return H._build(_payload(), sort=H.DEFAULT_SORT, names_per_group=25,
                    decisions={}, earnings={}, live=live, **kw)


def _theme(b, group="ai_semis"):
    return {t["group"]: t for t in b["themes"]}[group]


def _sector(b, group="Technology"):
    return {s["group"]: s for s in b["sectors"]}[group]


# ── 1. the fix itself ───────────────────────────────────────────────────────
def test_a_roster_row_goes_live_with_the_names_under_it():
    """His ask. On the close this roster is +5.0; on the tape it is −2.0."""
    closed = _theme(_build())
    # median(2, 3, 4, 89) over the members' own close moves against the bench
    assert closed["rel_1d"] == 3.5 and closed["d1_source"] == H.D1_CLOSE

    live = _theme(_build(_live(LIVE_3)))
    assert live["d1_source"] == H.D1_LIVE
    assert live["rel_1d"] == -2.0           # median(-3, -2, -1)
    # the sign really does flip — the condition he was reading through
    assert (closed["rel_1d"] > 0) is not (live["rel_1d"] > 0)


def test_the_sector_row_goes_live_too():
    """Not just the curated rosters: the provider's own sectors, which is what
    the word 'rotation' means on this board."""
    s = _sector(_build(_live(LIVE_3)))
    assert s["d1_source"] == H.D1_LIVE and s["rel_1d"] == -2.0


def test_the_industry_row_goes_live_too():
    s = _sector(_build(_live(LIVE_3)))
    semis = {i["group"]: i for i in s["industries"]}["Semis"]
    assert semis["d1_source"] == H.D1_LIVE and semis["rel_1d"] == -2.0


def test_the_live_median_is_relative_to_the_live_benchmark():
    """`rel_1d` has always been the name's move MINUS the benchmark's. A live
    median of RAW moves under a relative header is a different measurement."""
    live = _theme(_build(_live(LIVE_3, bench_move=-4.0)))
    # each name is now +1 / +2 / +3 against a benchmark down 4.0
    assert live["rel_1d"] == 2.0


# ── 2. NEGATIVE: never half-live ────────────────────────────────────────────
def test_a_member_with_no_live_print_is_excluded_not_folded_in_at_its_close():
    """DARK closed +89.0 relative. If it were counted at its close move the
    median would be +1.0 rather than −2.0 — the exact blend this board has
    always refused."""
    live = _theme(_build(_live(LIVE_3)))
    assert live["rel_1d"] == -2.0
    assert live["d1_live_n"] == 3 and live["d1_live_of"] == 4
    # and the name row itself is honest about why it is not in there
    dark = {n["symbol"]: n for n in live["names"]}["DARK"]
    assert dark["d1_source"] == H.D1_CLOSE


def test_a_row_whose_members_are_all_dark_falls_back_to_the_close_whole():
    """The board is LIVE and this one row has nothing live in it. A live header
    over a close number is the bug this whole change replaces, so the row goes
    back to the close entirely — and `d1_source` says so, which is what makes
    the FE print "last close" beside it."""
    p2 = _payload()
    p2[T.MEMBERS_KEY]["groups"]["theme"]["alldark"] = {"symbols": ["DARK"],
                                                       "median_21d": 8.0}
    b = H._build(p2, sort=H.DEFAULT_SORT, names_per_group=25,
                 decisions={}, earnings={}, live=_live(LIVE_3))
    assert b["d1"]["live"] is True                  # the BOARD is live
    row = _theme(b, "alldark")
    assert row["d1_source"] == H.D1_CLOSE           # ...this ROW is not
    assert row["rel_1d"] == 89.0 == row["rel_1d_close"]
    assert row["d1_live_n"] == 0 and row["d1_live_of"] == 1
    assert row["d1_live_close"] is None
    # and the live row beside it is unaffected
    assert _theme(b)["d1_source"] == H.D1_LIVE


def test_an_empty_live_block_is_not_live_at_all():
    """`live=True` with no benchmark move and no moves is not a live board —
    `_build` re-checks the fetcher's optimism."""
    for blk in (_live({}, ok=True),
                {"live": True, "benchmark_move": None, "moves": LIVE_3},
                {"live": False, "benchmark_move": 0.0, "moves": LIVE_3}):
        b = _build(blk)
        assert b["d1"]["live"] is False
        assert b["d1"]["group_basis"] == H.D1_GROUP_BASIS


# ── 3. NEGATIVE: the close leg is not touched, and never differenced ────────
def test_rel_1d_close_keeps_the_shipped_grid_sample_median():
    """A SECTOR's close leg is over the rotation grid's n=40 sample. The live
    leg is over the full membership. Overwriting one with the other is how a
    board starts quoting a number no cohort produced."""
    s = _sector(_build(_live(LIVE_3)))
    assert s["rel_1d_close"] == 2.55         # the shipped grid-sample figure
    assert s["n_measured"] == 40 and s["sampled_of"] == 308
    assert s["rel_1d"] == -2.0               # full-membership live median
    # the two cohorts are different sizes: they are NOT a before/after pair
    assert s["d1_live_of"] == 4 != s["n_measured"]


def test_d1_live_close_is_the_same_cohort_close_and_differs_from_rel_1d_close():
    """The one comparable pair. AAA/BBB/CCC closed +2/+3/+4 relative →
    median 3.0, which is NOT the shipped 2.55."""
    s = _sector(_build(_live(LIVE_3)))
    assert s["d1_live_close"] == 3.0
    assert s["d1_live_close"] != s["rel_1d_close"]


def test_the_close_row_carries_no_live_keys_at_all():
    """Byte-identical to what this board served before 2026-09-23."""
    closed = _theme(_build())
    for k in ("d1_live_n", "d1_live_of", "d1_live_close"):
        assert k not in closed, k
    assert closed["rel_1d"] == closed["rel_1d_close"] == 3.5
    assert closed["d1_source"] == H.D1_CLOSE


# ── 4. NEGATIVE: the medians use the FULL member list, not the served slice ─
def test_the_median_is_over_the_full_membership_not_the_truncated_names_array():
    """`names` is cut to `names_per_group` AFTER the sort, so it is the TOP of
    the board. A median over it would be biased upward by construction."""
    b = H._build(_payload(), sort=H.DEFAULT_SORT, names_per_group=1,
                 decisions={}, earnings={}, live=_live(LIVE_3))
    t = _theme(b)
    assert len(t["names"]) == 1              # only the top name is SERVED
    # ...and on the board's default sort (rel_5d) that one name is DARK — the
    # single member with NO live print at all. A median over what gets served
    # would have had nothing to work with.
    assert t["names"][0]["symbol"] == "DARK"
    assert t["names"][0]["d1_source"] == H.D1_CLOSE
    assert t["d1_live_n"] == 3               # the median counted all three
    assert t["rel_1d"] == -2.0


# ── 5. the served d1 block ──────────────────────────────────────────────────
def test_group_basis_is_a_token_never_prose():
    """The FE's `HsD1Source` union is exactly these two values."""
    assert H.D1_GROUP_BASIS == H.D1_CLOSE
    assert H.D1_LIVE_GROUP_BASIS == H.D1_LIVE
    for blk, want in ((None, H.D1_CLOSE), (_live(LIVE_3), H.D1_LIVE)):
        d1 = _build(blk)["d1"]
        assert d1["group_basis"] == want
        assert d1["group_basis"] in (H.D1_CLOSE, H.D1_LIVE)
        assert " " not in d1["group_basis"]


def test_the_basis_sentence_is_served_beside_the_token_and_matches_it():
    for blk, want in ((None, H.D1_CLOSE), (_live(LIVE_3), H.D1_LIVE)):
        d1 = _build(blk)["d1"]
        assert d1["group_basis_note"] == H.D1_GROUP_BASIS_NOTE[want]
        assert d1["group_basis_note"]


def test_the_live_note_stops_claiming_the_group_rows_are_from_the_close():
    """The exact sentence he was reading while the rows disagreed with it."""
    note = _build(_live(LIVE_3))["d1"]["note"]
    assert "5 days, 21 days and Sales YoY" in note
    assert "roster rows" not in note.split("Everything else")[-1]
    closed = _build()["d1"]["note"]
    assert "last finished session" in closed


def test_the_group_basis_and_the_rows_can_never_disagree():
    """One flag drives both, so a `live` basis with close rows is impossible."""
    for blk in (None, _live(LIVE_3), _live({}, ok=True)):
        b = _build(blk)
        live_board = b["d1"]["group_basis"] == H.D1_LIVE
        for row in b["themes"] + b["sectors"]:
            if not live_board:
                assert row["d1_source"] == H.D1_CLOSE
            else:
                # live board: a row is live unless NOT ONE member printed
                assert (row["d1_source"] == H.D1_LIVE) == (row.get("d1_live_n", 0) > 0)


# ── 6. ranking + hygiene ────────────────────────────────────────────────────
def test_the_board_re_ranks_on_the_live_group_number():
    """'I wanna see live rotation' — a live number that does not move the
    ranking is a decoration."""
    p = _payload()
    p[T.MEMBERS_KEY]["groups"]["theme"]["laggard"] = {"symbols": ["DARK"],
                                                      "median_21d": 8.0}
    def order(live):
        b = H._build(p, sort="rel_1d", names_per_group=25,
                     decisions={}, earnings={}, live=live)
        return [t["group"] for t in b["themes"]]
    # on the close DARK's roster is +89.0 and leads
    assert order(None)[0] == "laggard"
    # live, DARK never printed → its row stays on the close and still leads;
    # give it a live print that is worse and the order flips
    assert order(_live({**LIVE_3, "DARK": -9.0}))[0] == "ai_semis"


def test_no_nan_reaches_the_payload_from_the_live_medians():
    """A NaN survives every arithmetic step and passes every <= comparison,
    so one bad print would silently reorder the board."""
    b = _build(_live({**LIVE_3, "DARK": float("nan")}))
    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, float):
            assert not math.isnan(o)
    walk(b)


def test_nothing_else_on_the_row_moved():
    """5d / 21d / pct_positive / counts are the snapshot's, live or not."""
    closed, live = _theme(_build()), _theme(_build(_live(LIVE_3)))
    for k in ("rel_5d", "rel_21d", "n_full", "names_total", "basis", "thin"):
        assert closed[k] == live[k], k
