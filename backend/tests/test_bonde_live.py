"""📈 Bonde — the live Today leg (`sepa/bonde_live.py`), Ajay 2026-09-20:
*"make his page more live"*.

The negatives carry this file. The failure that matters is not "no live price"
— it is a board that shows THIS session for some rows and the LAST one for the
rest under a single header. Four tests below exist only to prove that cannot
happen: a shut calendar, a missing benchmark, a raising fetch and an empty
snapshot all have to blank EVERY row, not the unlucky ones.

The cost sentence the tab prints ("2 Massive snapshot calls") is pinned here by
COUNTING the chunks a real `bulk_snapshot` would send, using `prices._SNAP_CHUNK`
— never by typing 2 in a test and 2 in the TSX and hoping they stay equal.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from rotation import hottest as H
from sepa import bonde as BD
from sepa import bonde_live as BL

ET = ZoneInfo("America/New_York")


# ───────────────────────────────────────────────────────────── fixtures
def row(symbol: str, **kw) -> dict:
    return {"symbol": symbol, "name": f"{symbol} Inc", "tier": "explosive",
            "growth_yoy_pct": 120.0, "pivot": None, **kw}


def board(**kw) -> dict:
    return {"sections": {"pivot": [], "explosive": [row("PTGX"), row("IOVA")],
                         "strong": [row("TWLO")], "steady": [],
                         "rejected": [row("HPQ")]},
            "counts": {}, "n_pass": 4, "n_scanned": 2076,
            "scan_ts": "2026-09-19T21:04:11+00:00", **kw}


def snap(px: float = 10.0, chg: float = 1.5) -> dict:
    return {"price": px, "change_pct": chg}


def fetch_all(moves: dict):
    """An injected snapshot fetcher: one call, every asked symbol answered."""
    def _f(syms):
        return {s: snap(chg=moves.get(s, 0.5)) for s in syms if s in moves}
    return _f


@pytest.fixture(autouse=True)
def _open_tape(monkeypatch):
    """Default every test to an OPEN calendar inside RTH, so a test that wants
    a closed one says so. The calendar and the clock are the engine's, not this
    module's — they are stubbed where the engine reads them."""
    monkeypatch.setattr(H, "_closed_reason", lambda: None)
    monkeypatch.setattr(H, "_in_session", lambda: True)
    monkeypatch.setattr(H, "_session_window", lambda: "9:30-16:00 ET")


# ───────────────────────────────────────────────────────────── the live case
def test_live_snapshot_fills_today_on_every_listed_row():
    moves = {"RSP": 0.4, "PTGX": 3.2, "IOVA": -1.1, "TWLO": 0.0, "HPQ": 2.5}
    b = BL.attach(board(), fetch=fetch_all(moves))
    assert b["d1"]["basis"] == H.D1_LIVE
    assert b["d1"]["live"] is True
    # `live_names` counts the BOARD names that printed, not RSP-plus-them.
    assert b["d1"]["live_names"] == 4
    assert b["d1"]["symbols"] == 4
    for sec in b["sections"].values():
        for r in sec:
            assert r["today_pct"] == moves[r["symbol"]]
            assert r["today_basis"] == H.D1_LIVE
    # A 0.0% move is a real print, not a missing one.
    assert b["sections"]["strong"][0]["today_pct"] == 0.0


def test_the_rejected_section_gets_the_live_column_too():
    """🔎 rows are not on his screen, but they are on the PAGE — a column that
    silently stops at the last section reads as "no move today"."""
    b = BL.attach(board(), fetch=fetch_all({"RSP": 0.4, "HPQ": 2.5}))
    assert b["sections"]["rejected"][0]["today_pct"] == 2.5


def test_d1_keys_are_exactly_the_pinned_set():
    b = BL.attach(board(), fetch=fetch_all({"RSP": 0.4, "PTGX": 1.0}))
    assert set(b["d1"]) == set(BL.D1_KEYS)


def test_as_of_is_stamped_on_live_and_absent_on_close():
    live = BL.attach(board(), fetch=fetch_all({"RSP": 0.4, "PTGX": 1.0}))
    assert isinstance(live["d1"]["as_of"], str) and live["d1"]["as_of"]
    closed = BL.attach(board(), fetch=lambda syms: {})
    assert closed["d1"]["as_of"] is None


# ──────────────────────────────────────── NEGATIVES — never half live
def test_NEGATIVE_closed_calendar_blanks_every_row(monkeypatch):
    """The provider still answers on a weekend — with the LAST session. Serving
    that as "today" would relabel the same number."""
    monkeypatch.setattr(H, "_closed_reason", lambda: "weekend")
    b = BL.attach(board(), fetch=fetch_all({"RSP": 0.4, "PTGX": 3.2, "IOVA": -1.1,
                                            "TWLO": 0.0, "HPQ": 2.5}))
    assert b["d1"]["basis"] == H.D1_CLOSE
    assert b["d1"]["live"] is False
    assert b["d1"]["market_closed"] == "weekend"
    assert "weekend" in (b["d1"]["reason"] or "")
    assert b["d1"]["live_names"] == 0
    for sec in b["sections"].values():
        for r in sec:
            assert r["today_pct"] is None
            assert r["today_basis"] == H.D1_CLOSE


def test_NEGATIVE_missing_benchmark_puts_ALL_rows_on_the_close():
    """The one that would have shipped a mixed table: four names printed live,
    RSP did not. Every row goes back to the close, not just RSP's."""
    b = BL.attach(board(), fetch=fetch_all({"PTGX": 3.2, "IOVA": -1.1,
                                            "TWLO": 0.0, "HPQ": 2.5}))
    assert b["d1"]["basis"] == H.D1_CLOSE
    assert "RSP" in (b["d1"]["reason"] or "")
    assert all(r["today_pct"] is None
               for sec in b["sections"].values() for r in sec)


def test_NEGATIVE_partial_snapshot_keeps_the_basis_live_and_blanks_only_the_missing():
    """The other half of the rule: with a live benchmark the basis IS live, and
    a name with no print carries None while its neighbours carry numbers. The
    basis label is what must never be mixed — a per-row gap is honest."""
    b = BL.attach(board(), fetch=fetch_all({"RSP": 0.4, "PTGX": 3.2}))
    assert b["d1"]["basis"] == H.D1_LIVE
    assert b["sections"]["explosive"][0]["today_pct"] == 3.2
    assert b["sections"]["explosive"][1]["today_pct"] is None
    assert b["d1"]["live_names"] == 1


def test_NEGATIVE_empty_snapshot_is_the_close_basis_not_a_live_board_of_blanks():
    b = BL.attach(board(), fetch=lambda syms: {})
    assert b["d1"]["basis"] == H.D1_CLOSE
    assert b["d1"]["live"] is False
    assert b["d1"]["reason"]


def test_NEGATIVE_attach_never_raises_when_the_fetch_raises():
    def boom(syms):
        raise RuntimeError("provider down")
    b = BL.attach(board(), fetch=boom)
    assert b["d1"]["basis"] == H.D1_CLOSE
    assert "RuntimeError" in (b["d1"]["reason"] or "")
    assert all(r["today_pct"] is None
               for sec in b["sections"].values() for r in sec)


def test_NEGATIVE_a_board_with_no_rows_does_not_raise_and_says_why():
    b = BL.attach({"sections": {"pivot": [], "explosive": []}, "scan_ts": None},
                  fetch=fetch_all({"RSP": 0.4}))
    assert b["d1"]["basis"] == H.D1_CLOSE
    assert b["d1"]["symbols"] == 0
    assert b["d1"]["close_as_of"] is None


def test_NEGATIVE_a_non_dict_payload_is_returned_untouched():
    assert BL.attach(None) is None            # type: ignore[arg-type]
    assert BL.attach([]) == []                # type: ignore[arg-type]


# ───────────────────────────────────────────────────── labels the FE prints
def test_tape_session_is_the_one_tagger_and_never_called_session():
    b = BL.attach(board(), fetch=fetch_all({"RSP": 0.4}),
                  now=datetime(2026, 9, 18, 10, 15, tzinfo=ET))
    assert b["d1"]["tape_session"] in {"premarket", "rth", "afterhours", "closed"}
    assert "session" not in set(b["d1"]) - {"tape_session", "in_session",
                                            "session_window"}


@pytest.mark.parametrize("when,expect", [
    (datetime(2026, 9, 18, 7, 40, tzinfo=ET), "premarket"),
    (datetime(2026, 9, 18, 10, 15, tzinfo=ET), "rth"),
    (datetime(2026, 9, 18, 17, 30, tzinfo=ET), "afterhours"),
    (datetime(2026, 9, 19, 23, 30, tzinfo=ET), "closed"),
])
def test_tape_session_tags_each_window(when, expect):
    b = BL.attach(board(), fetch=fetch_all({"RSP": 0.4}), now=when)
    assert b["d1"]["tape_session"] == expect


def test_the_note_says_which_basis_and_names_the_scan_date():
    live = BL.attach(board(), fetch=fetch_all({"RSP": 0.4, "PTGX": 1.0}))
    assert "so far in this session" in live["d1"]["note"]
    assert "2026-09-19" in live["d1"]["note"]
    closed = BL.attach(board(), fetch=lambda syms: {})
    assert "last finished session" in closed["d1"]["note"]
    assert "2026-09-19" in closed["d1"]["note"]


def test_NEGATIVE_the_note_is_bondes_own_sentence_not_hottests():
    """Copying Hottest's sentence would put "every sector, industry and roster
    row" on a board that has none of those."""
    b = BL.attach(board(), fetch=fetch_all({"RSP": 0.4, "PTGX": 1.0}))
    assert "sector" not in b["d1"]["note"]
    assert "roster" not in b["d1"]["note"]
    assert "Episodic" in b["d1"]["note"]


def test_the_word_bounce_never_reaches_a_served_string():
    b = BL.attach(board(), fetch=fetch_all({"RSP": 0.4, "PTGX": 1.0}))
    blob = " ".join(str(v) for v in b["d1"].values())
    assert "bounce" not in blob.lower()


@pytest.mark.parametrize("ts,expect", [
    ("2026-09-19T21:04:11+00:00", "2026-09-19"),
    ("2026-09-19", "2026-09-19"),
    (None, None),
    ("", None),
])
def test_close_as_of_is_a_date_or_nothing(ts, expect):
    b = BL.attach(board(scan_ts=ts), fetch=fetch_all({"RSP": 0.4}))
    assert b["d1"]["close_as_of"] == expect


def test_NEGATIVE_an_epoch_scan_ts_prints_a_date_not_ten_digits():
    """`str(epoch)[:10]` would have rendered "1758322" in the basis line."""
    epoch = datetime(2026, 9, 19, 16, 30, tzinfo=ET).timestamp()
    b = BL.attach(board(scan_ts=epoch), fetch=fetch_all({"RSP": 0.4}))
    assert b["d1"]["close_as_of"] == "2026-09-19"


# ─────────────────────────────── the cost sentence, counted not typed
def test_the_full_board_costs_exactly_two_snapshot_calls():
    """THE PIN BEHIND `BONDE_LIVE_COST_SENTENCE`.

    `SECTION_CAP` is 60/60/60/40/40 = 260 names at most, plus RSP = 261, and
    `prices.bulk_snapshot` sends `_SNAP_CHUNK` (250) tickers per call. Both
    numbers are READ here, never retyped, so a cap change or a provider limit
    change fails this test instead of quietly making the tab's sentence wrong.
    """
    from sepa.prices import _SNAP_CHUNK

    cap_total = sum(BD.SECTION_CAP.values())
    assert cap_total == 260

    calls: list = []

    def chunking_fetch(syms):
        """Stands in for `bulk_live_prices` → `bulk_snapshot`: same chunking,
        counted."""
        wire = sorted(set(syms))
        out = {}
        for i in range(0, len(wire), _SNAP_CHUNK):
            chunk = wire[i:i + _SNAP_CHUNK]
            calls.append(len(chunk))
            out.update({s: snap(chg=1.0) for s in chunk})
        return out

    syms = [f"SYM{i:04d}" for i in range(cap_total)]
    full = {"sections": {"explosive": [row(s) for s in syms]},
            "scan_ts": "2026-09-19"}
    b = BL.attach(full, fetch=chunking_fetch)
    assert b["d1"]["symbols"] == cap_total
    assert len(calls) == 2, (
        "the tab prints '2 Massive snapshot calls' — this is that number")
    assert sum(calls) == cap_total + 1        # the board's names plus RSP


def test_NEGATIVE_one_name_over_the_cap_would_cost_a_third_call():
    """Proves the 2 above is a real boundary and not an artefact: the sentence
    would be wrong the moment the caps grew past 2 x 250 - 1."""
    from sepa.prices import _SNAP_CHUNK

    calls: list = []

    def chunking_fetch(syms):
        wire = sorted(set(syms))
        for i in range(0, len(wire), _SNAP_CHUNK):
            calls.append(1)
        return {s: snap() for s in wire}

    syms = [f"SYM{i:04d}" for i in range(2 * _SNAP_CHUNK)]
    BL.attach({"sections": {"explosive": [row(s) for s in syms]}},
              fetch=chunking_fetch)
    assert len(calls) == 3


def test_the_board_prices_only_what_it_SHOWS():
    """The capped sections are the page. Pricing the 1,051 passers would spend
    provider reads on rows nobody can see."""
    b = board()
    syms = BL._symbols(b)
    assert syms == ["PTGX", "IOVA", "TWLO", "HPQ"]
    asked: list = []

    def spy(s):
        asked.extend(s)
        return {x: snap() for x in s}
    BL.attach(b, fetch=spy)
    assert set(asked) == set(syms) | {BL.BENCH}


def test_the_benchmark_is_the_apps_own_constant():
    assert BL.BENCH == "RSP"


# ─────────────────────────────────────────────────────── the API wiring
def test_the_endpoint_wraps_the_board_with_attach(monkeypatch):
    """`/bonde/board` must serve the live leg — the whole point of 4a."""
    import asyncio
    from sepa import bonde_api as API

    monkeypatch.setattr(API.B, "board", lambda new_days=30: board())
    seen: dict = {}

    def fake_attach(b, **kw):
        seen["called"] = True
        b["d1"] = {"basis": "close"}
        return b
    monkeypatch.setattr(API.BL, "attach", fake_attach)

    # `asyncio.run` CLOSES the loop and leaves the thread with none, and on
    # py3.9 the next module that builds an `asyncio.Lock()` at import time
    # (sepa/insider.py, imported by sepa/scanner.py) then blows up in whatever
    # test happens to run after this one. Own the loop and hand a fresh one
    # back.
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        resp = loop.run_until_complete(API.bonde_board(new_days=30))
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())

    assert seen.get("called") is True
    import json
    assert json.loads(resp.body)["d1"]["basis"] == "close"
