"""Chart Maps dwell tag — "in demand zone for 3 days" (2026-09-09).

Ajay: "I wanna have dates on the chart map stocks it has to tell if they are
there form yesterday or todays scan" then "May be tag them to say they are in
demand zone for 3 days or so... Cuz I have seen some stocks sitting there".

The count is `demand_episodes.appearances` — BOARD DAYS in one continuous
episode, not calendar days. What these pin:
  1. the wording, because he reads it as a fact about how long a name has sat;
  2. that day one says NEW rather than "1 board days";
  3. that the tone is never good/warn — nothing has measured whether a long sit
     helps or hurts, and a colour would be an unearned verdict;
  4. that garbage never reaches the screen;
  5. that a name with no episode is left completely alone.
"""
import importlib

import pytest

B = importlib.import_module("chart_maps.board")


def test_day_one_says_new_not_one_board_days():
    assert B.dwell_text(1, "2026-09-09") == B.DWELL_NEW_TEXT
    assert "1 board days" not in (B.dwell_text(1, "2026-09-09") or "")


def test_the_sitting_case_he_described_names_the_count_and_the_date():
    txt = B.dwell_text(3, "2026-09-05")
    assert txt == "📌 3 board days · since Sep 5"
    assert B.dwell_text(13, "2026-08-26") == "📌 13 board days · since Aug 26"


def test_the_date_is_sliced_never_parsed():
    """A datetime round-trip would shift an ET stamp by a day."""
    assert B._dwell_month("2026-01-01") == "Jan 1"
    assert B._dwell_month("2026-12-31") == "Dec 31"
    assert B._dwell_month("2026-09-05T23:59:00-04:00") == "Sep 5"
    assert B._dwell_month("nonsense") == "nonsense"


@pytest.mark.parametrize("n", [0, -3, None, "", "abc", float("nan")])
def test_garbage_counts_never_reach_the_screen(n):
    assert B.dwell_text(n, "2026-09-05") is None


def test_a_missing_first_seen_still_gives_the_count():
    assert B.dwell_text(4, None) == "📌 4 board days"
    assert B.dwell_text(4, "") == "📌 4 board days"


class _Coll:
    def __init__(self, docs):
        self.docs = docs

    def find(self, q, proj=None):
        syms = set((q.get("symbol") or {}).get("$in") or [])
        return [d for d in self.docs if d["symbol"] in syms]


class _DB:
    def __init__(self, docs):
        self._c = _Coll(docs)

    def __getitem__(self, name):
        return self._c


def test_the_decorator_tags_only_names_with_an_episode(monkeypatch):
    from supply_demand import demand_history as DH
    docs = [
        {"symbol": "AIG", "appearances": 13, "first_seen": "2026-08-26", "last_seen": "2026-09-09"},
        {"symbol": "NEW", "appearances": 1, "first_seen": "2026-09-09", "last_seen": "2026-09-09"},
    ]
    monkeypatch.setattr(DH, "_db", lambda: _DB(docs))
    tiles = [{"symbol": "AIG"}, {"symbol": "NEW"}, {"symbol": "NOEP"}]
    assert B._dwell_decor(tiles) == 2

    aig = tiles[0]
    assert aig["badges"][0]["text"] == "📌 13 board days · since Aug 26"
    assert aig["stats"][0] == {"k": B.DWELL_STAT_KEY, "v": "13d"}
    assert tiles[1]["badges"][0]["text"] == B.DWELL_NEW_TEXT
    # the untagged name is left completely alone — no empty badge list either
    assert "badges" not in tiles[2] and "stats" not in tiles[2]


def test_the_tag_never_carries_a_verdict_colour(monkeypatch):
    """A long sit is not measured good or bad. Colouring it would say it is."""
    from supply_demand import demand_history as DH
    docs = [{"symbol": s, "appearances": n, "first_seen": "2026-08-26",
             "last_seen": "2026-09-09"}
            for s, n in (("A", 1), ("B", 3), ("C", 30))]
    monkeypatch.setattr(DH, "_db", lambda: _DB(docs))
    tiles = [{"symbol": "A"}, {"symbol": "B"}, {"symbol": "C"}]
    B._dwell_decor(tiles)
    tones = {t["badges"][0]["tone"] for t in tiles}
    assert tones == {"muted"}, "no good/warn tone until a study says which it is"


def test_the_newest_episode_wins_when_a_name_left_and_came_back(monkeypatch):
    from supply_demand import demand_history as DH
    docs = [
        {"symbol": "X", "appearances": 9, "first_seen": "2026-07-01", "last_seen": "2026-07-20"},
        {"symbol": "X", "appearances": 2, "first_seen": "2026-09-08", "last_seen": "2026-09-09"},
    ]
    monkeypatch.setattr(DH, "_db", lambda: _DB(docs))
    tiles = [{"symbol": "X"}]
    B._dwell_decor(tiles)
    assert tiles[0]["badges"][0]["text"] == "📌 2 board days · since Sep 8"


def test_no_mongo_is_a_no_op_not_a_crash(monkeypatch):
    from supply_demand import demand_history as DH
    monkeypatch.setattr(DH, "_db", lambda: None)
    tiles = [{"symbol": "AIG"}]
    assert B._dwell_decor(tiles) == 0
    assert "badges" not in tiles[0]
    assert B._dwell_decor([]) == 0


def test_a_raising_mongo_is_swallowed(monkeypatch):
    """The tag is decoration. It must never take the board down with it."""
    from supply_demand import demand_history as DH

    def boom():
        raise RuntimeError("mongo down")

    monkeypatch.setattr(DH, "_db", boom)
    tiles = [{"symbol": "AIG"}]
    assert B._dwell_decor(tiles) == 0
    assert "badges" not in tiles[0]


def test_both_demand_tabs_tag_and_the_others_do_not():
    """Source guard: `demand_episodes` is written from the Back in Demand board,
    so the count is meaningless on a VCP or topping tile."""
    import inspect
    src = inspect.getsource(B)
    assert src.count("_dwell_decor(out)") == 2, "exactly zones + deep_demand"
    for fn in (B.zone_tiles, B.deep_demand_tiles):
        assert "_dwell_decor(out)" in inspect.getsource(fn), fn.__name__
    for fn in (B.vcp_tiles, B.topping_tiles, B.undervalue_tiles, B.gabbar_tiles):
        assert "_dwell_decor" not in inspect.getsource(fn), fn.__name__
