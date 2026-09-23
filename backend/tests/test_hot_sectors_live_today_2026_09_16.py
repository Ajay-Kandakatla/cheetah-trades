"""🔥 Hottest — the "Today" column had to mean today (Ajay 2026-09-16).

He sent two screenshots taken the same minute, market open, ~11:00 ET:

  * the Hottest Sectors board:  TENB  **+8.3%**  under a column headed *Today*
  * his own TENB ticker page:   **$36.68, −3.70%, Today · Live**

Both numbers were right. The rotation snapshot behind the board is built AFTER
the close (the 2026-09-15 build stamped 19:14 ET; the refreshing scans run
16:30+), so the column was printing the PREVIOUS session under today's word.
TENB really did close +7.98% raw / +8.26% against RSP on 2026-09-15.

WHAT IS PINNED HERE
-------------------
1. `rel_1d` is RELATIVE, and stays relative. A name row's day leg has always
   been `ret_1d − benchmark.ret_1d` (tracker.traction_row). The live overlay
   therefore subtracts the LIVE benchmark move from the LIVE name move, out of
   the same fan-out. A raw move served into that column would be a different
   measurement wearing the same header, so there is a test that fails on it.
2. The snapshot value survives under `rel_1d_close` / `ret_1d_close`.
3. Every failure path degrades to the close WITH a reason — never blank, never
   a crash, never a silent stale number.
4. A group median is never half live and half close.

The snapshot's build cadence is deliberately NOT touched: a cold rotation build
is ~30 s and no board may wait on one.
"""
from __future__ import annotations

import pytest

from rotation import hottest as H


# ── Fixture: TENB's real 2026-09-15 close row, plus one quiet peer ───────────
BENCH = {"symbol": "RSP", "ret_1d": -0.28, "ret_5d": -1.08,
         "ret_21d": -3.76, "ret_63d": 0.71}


def _payload() -> dict:
    return {
        "as_of": "2026-09-15",
        "sectors": [{"group": "Technology", "n": 40, "rel_1d": -0.59,
                     "rel_5d": 2.0, "rel_21d": -4.27, "pct_positive_1d": 30}],
        "industries": [], "themes": [], "sampled": {},
        H.T.MEMBERS_KEY: {
            "benchmark": dict(BENCH),
            "by_symbol": {
                "TENB": {"last_close": 37.88, "ret_1d": 7.98, "ret_5d": 12.4,
                         "ret_21d": -1.18, "ret_63d": 36.65,
                         "sector": "Technology",
                         "industry": "Software - Infrastructure"},
                "QLYS": {"last_close": 100.0, "ret_1d": 1.0, "ret_5d": 2.0,
                         "ret_21d": 3.0, "ret_63d": 4.0,
                         "sector": "Technology",
                         "industry": "Software - Infrastructure"},
            },
            "groups": {"sector": {"Technology": {
                "median_21d": -4.27, "symbols": ["TENB", "QLYS"]}}},
        },
    }


def _names(board: dict) -> dict:
    return {n["symbol"]: n for n in board["sectors"][0]["names"]}


def _open_market(monkeypatch):
    """The calendar says trading, so the test does not change answer on a
    Saturday. The gate itself is market_hours.gate — never a second calendar."""
    monkeypatch.setattr(H, "_closed_reason", lambda: None)


def _build_with(live: dict, sort: str = "rel_5d") -> dict:
    return H._build(_payload(), sort=sort, names_per_group=25,
                    decisions={}, earnings={}, live=live)


# ── 1. The live read reaches the row, and says so ───────────────────────────
def test_a_name_with_a_live_read_shows_TODAY_and_is_marked_live(monkeypatch):
    _open_market(monkeypatch)
    live = H.live_day_moves(
        ["TENB", "QLYS"], "RSP",
        fetch=lambda syms: {"RSP": {"price": 190.0, "change_pct": -0.50},
                            "TENB": {"price": 36.68, "change_pct": -3.70},
                            "QLYS": {"price": 99.0, "change_pct": -2.79}})
    rows = _names(_build_with(live))

    tenb = rows["TENB"]
    assert tenb["d1_source"] == "live"
    # RELATIVE, exactly as the column has always been: −3.70 − (−0.50).
    assert tenb["rel_1d"] == pytest.approx(-3.20)
    assert tenb["ret_1d"] == pytest.approx(-3.70)
    # …and the snapshot value is still carried, so nothing reading the old
    # field loses its number.
    assert tenb["rel_1d_close"] == pytest.approx(8.26)
    assert tenb["ret_1d_close"] == pytest.approx(7.98)
    assert rows["QLYS"]["d1_source"] == "live"


def test_the_column_is_RELATIVE_not_raw(monkeypatch):
    """The test that fails if someone serves a raw move into a relative column.

    With the benchmark itself down 0.50 the two are 0.50 apart by construction,
    so a raw overlay cannot pass this by accident.
    """
    _open_market(monkeypatch)
    live = H.live_day_moves(
        ["TENB"], "RSP",
        fetch=lambda syms: {"RSP": {"price": 190.0, "change_pct": -0.50},
                            "TENB": {"price": 36.68, "change_pct": -3.70}})
    tenb = _names(_build_with(live))["TENB"]
    assert tenb["rel_1d"] != pytest.approx(tenb["ret_1d"]), \
        "rel_1d must be the name's move MINUS the benchmark's, never the raw move"
    assert tenb["rel_1d"] == pytest.approx(tenb["ret_1d"] - live["benchmark_move"])


# ── 2. NEGATIVE: a name with no live read ───────────────────────────────────
def test_NEGATIVE_a_name_with_no_live_read_shows_the_close_and_says_so(monkeypatch):
    _open_market(monkeypatch)
    live = H.live_day_moves(
        ["TENB", "QLYS"], "RSP",
        fetch=lambda syms: {"RSP": {"price": 190.0, "change_pct": -0.50},
                            "TENB": {"price": 36.68, "change_pct": -3.70}})
    rows = _names(_build_with(live))
    qlys = rows["QLYS"]
    assert qlys["d1_source"] == "close", "an unpriced name must never read as live"
    assert qlys["rel_1d"] == qlys["rel_1d_close"] == pytest.approx(1.28)
    # the board is live, so the FE has something to mark this row WITH
    assert _build_with(live)[H.D1_KEY]["live"] is True


def test_NEGATIVE_a_zero_day_bar_is_missing_not_flat(monkeypatch):
    """Pre-open the day aggregate is 0. Serving its change_pct would print a
    flat '+0.0%' for every name — a measurement nobody made."""
    _open_market(monkeypatch)
    live = H.live_day_moves(
        ["TENB"], "RSP",
        fetch=lambda syms: {"RSP": {"price": 190.0, "change_pct": -0.50},
                            "TENB": {"price": 0, "change_pct": 0.0}})
    assert _names(_build_with(live))["TENB"]["d1_source"] == "close"


# ── 3. NEGATIVE: the fan-out fails ──────────────────────────────────────────
def _boom(syms):
    raise RuntimeError("massive is down")


@pytest.mark.parametrize("fetch,expect_in_reason", [
    (_boom, "RuntimeError"),
    # an empty answer stops at the BENCHMARK check — the relative column has
    # nothing to rebase against, which is the same honest fallback
    (lambda syms: {}, "no live price"),
    (lambda syms: None, "no live price"),
])
def test_NEGATIVE_a_failed_live_read_leaves_every_row_on_the_close(
        monkeypatch, fetch, expect_in_reason):
    _open_market(monkeypatch)
    live = H.live_day_moves(["TENB", "QLYS"], "RSP", fetch=fetch)
    assert live["live"] is False and expect_in_reason in (live["reason"] or "")

    board = _build_with(live)
    rows = _names(board)
    # never blank: every row still renders, on the snapshot's numbers
    assert set(rows) == {"TENB", "QLYS"}
    assert rows["TENB"]["rel_1d"] == pytest.approx(8.26)
    assert all(r["d1_source"] == "close" for r in rows.values())
    d1 = board[H.D1_KEY]
    assert d1["basis"] == "close" and d1["live"] is False
    assert d1["reason"], "a board that fell back must say why, in words"
    assert "close" in d1["note"]


def test_NEGATIVE_no_live_benchmark_means_no_live_overlay_at_all(monkeypatch):
    """Without a live benchmark print there is no RELATIVE number to serve.
    Half the column changing meaning is worse than all of it being yesterday's.
    """
    _open_market(monkeypatch)
    live = H.live_day_moves(
        ["TENB"], "RSP",
        fetch=lambda syms: {"TENB": {"price": 36.68, "change_pct": -3.70}})
    assert live["live"] is False and "RSP" in (live["reason"] or "")
    rows = _names(_build_with(live))
    assert rows["TENB"]["d1_source"] == "close"
    assert rows["TENB"]["rel_1d"] == pytest.approx(8.26)


def test_NEGATIVE_a_closed_market_never_fans_out_at_all(monkeypatch):
    """Weekend / NYSE holiday: the provider snapshot still answers, with the
    session the board already has. Relabelling it "live" would be the same bug
    with a nicer word. ONE calendar — market_hours.gate."""
    monkeypatch.setattr(H, "_closed_reason", lambda: "holiday 2026-11-26")
    calls = []
    live = H.live_day_moves(["TENB"], "RSP",
                            fetch=lambda syms: calls.append(syms) or {})
    assert calls == [], "a closed tape must not spend a provider call"
    assert live["live"] is False and "holiday 2026-11-26" in live["reason"]


def test_NEGATIVE_the_pure_build_makes_no_live_read_and_says_so():
    board = H.build(_payload())
    d1 = board[H.D1_KEY]
    assert d1["basis"] == "close" and d1["live"] is False and d1["reason"]
    assert all(n["d1_source"] == "close" for n in board["sectors"][0]["names"])


# ── 4. NEGATIVE: group medians are never a live/close mix ───────────────────
def test_NEGATIVE_a_group_median_is_never_a_mix_of_live_and_close_members(monkeypatch):
    """TENB live −3.20, QLYS on its close +1.28.

    THE INVARIANT IS UNCHANGED AND IS THE POINT OF THIS TEST: a median of one
    live and one last-close value is true of neither session, and nothing may
    ever produce one.

    WHAT CHANGED 2026-09-23 (Ajay: "Its actualy rotating this morning I wanna
    see live rotattion") is which of the two honest answers the row gives. It
    used to median BOTH closes; it now medians the LIVE members only and says
    how many that was. The forbidden middle — one of each — is pinned below
    exactly as it always was.
    """
    _open_market(monkeypatch)
    live = H.live_day_moves(
        ["TENB", "QLYS"], "RSP",
        fetch=lambda syms: {"RSP": {"price": 190.0, "change_pct": -0.50},
                            "TENB": {"price": 36.68, "change_pct": -3.70}})
    board = _build_with(live)
    sector = board["sectors"][0]
    ind = sector["industries"][0]

    # the live cohort is TENB alone, and the row says so
    assert ind["d1_source"] == "live"
    assert ind["rel_1d"] == pytest.approx(-3.20)
    assert ind["d1_live_n"] == 1 and ind["d1_live_of"] == 2

    # THE FORBIDDEN NUMBER: (−3.20 + 1.28) / 2 = −0.96, one live and one close
    assert ind["rel_1d"] != pytest.approx(-0.96)
    # and the both-closes median (8.26 + 1.28) / 2 = 4.77 is not served as the
    # live figure either — it is kept, under its own key
    closes = [8.26, 1.28]
    assert ind["rel_1d"] != pytest.approx(sum(closes) / 2)
    assert ind["rel_1d_close"] == pytest.approx(sum(closes) / 2)
    # the same-cohort close is TENB's own: comparable, unlike the two above
    assert ind["d1_live_close"] == pytest.approx(8.26)

    # the shipped SECTOR row keeps the rotation grid's sampled close under its
    # own key while its day cell rides the live cohort
    assert sector["rel_1d_close"] == pytest.approx(-0.59)
    assert sector["d1_source"] == "live" and sector["rel_1d"] == pytest.approx(-3.20)
    assert board[H.D1_KEY]["group_basis"] == H.D1_LIVE


# ── 5. The as-of block says which columns are live ─────────────────────────
def test_the_d1_block_states_which_columns_are_live(monkeypatch):
    _open_market(monkeypatch)
    live = H.live_day_moves(
        ["TENB", "QLYS"], "RSP",
        fetch=lambda syms: {"RSP": {"price": 190.0, "change_pct": -0.50},
                            "TENB": {"price": 36.68, "change_pct": -3.70},
                            "QLYS": {"price": 99.0, "change_pct": -2.79}})
    d1 = _build_with(live)[H.D1_KEY]
    assert d1["live"] is True and d1["basis"] == "live"
    assert d1["benchmark"] == "RSP" and d1["benchmark_move"] == pytest.approx(-0.50)
    assert d1["close_as_of"] == "2026-09-15"
    assert d1["live_names"] == 2
    note = d1["note"]
    for phrase in ("5 days", "21 days", "Sales YoY", "2026-09-15"):
        assert phrase in note, f"the note must name what is NOT live: {phrase}"
    # the payload never carries the per-symbol map — one float per priced name
    assert "moves" not in d1


def test_the_close_note_names_the_session_it_is_showing():
    d1 = H.build(_payload())[H.D1_KEY]
    assert "2026-09-15 close" in d1["note"]
    assert "not the current one" in d1["note"]


# ── 6. ONE fan-out for the whole board ─────────────────────────────────────
def test_one_bulk_live_prices_fanout_per_board_and_it_carries_the_benchmark(monkeypatch):
    _open_market(monkeypatch)
    seen = []

    def _fetch(syms):
        seen.append(list(syms))
        return {s: {"price": 10.0, "change_pct": 1.0} for s in syms}

    H.live_day_moves(["TENB", "QLYS"], "RSP", fetch=_fetch)
    assert len(seen) == 1, "one fan-out for the board, never one per row"
    assert "RSP" in seen[0], "the benchmark must ride in the SAME call or the " \
                             "column stops being relative to the same session"


def test_the_live_read_covers_every_priced_name_not_just_the_printed_ones(monkeypatch):
    """The day column is sortable. Ranking on yesterday and THEN truncating to
    25 would hide today's movers behind yesterday's, so the fan-out is over the
    whole member table."""
    _open_market(monkeypatch)
    seen = []
    monkeypatch.setattr(H, "_bulk_live", lambda syms: seen.append(list(syms)) or {})
    monkeypatch.setattr(H, "_decision_map", lambda syms: {})
    monkeypatch.setattr(H, "_earnings_map", lambda syms: {})
    H.build_live(_payload(), names_per_group=1)
    assert seen and set(seen[0]) >= {"TENB", "QLYS", "RSP"}


def test_the_day_column_sorts_on_the_LIVE_number(monkeypatch):
    """TENB leads on the close (+8.26) and trails live (−3.20). Sorted on the
    day leg, the live order is the one that must survive the truncation."""
    _open_market(monkeypatch)
    live = H.live_day_moves(
        ["TENB", "QLYS"], "RSP",
        fetch=lambda syms: {"RSP": {"price": 190.0, "change_pct": -0.50},
                            "TENB": {"price": 36.68, "change_pct": -3.70},
                            "QLYS": {"price": 99.0, "change_pct": -2.79}})
    order = [n["symbol"] for n in
             _build_with(live, sort="rel_1d")["sectors"][0]["names"]]
    assert order == ["QLYS", "TENB"]
