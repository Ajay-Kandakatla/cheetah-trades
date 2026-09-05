"""push/history.list_recent — the additive filters behind the /alerts page.

Ajay 2026-09-05: "can I go to a dedicated page to see the list of alerts? May be
add it to recent alerts or something?" The page reads push_history through
/notifications/recent filtered to the three S/D kinds, a day, a ticker. With no
filter given the Mongo query must be byte-for-byte what it was.

Pure: a fake collection records the query / sort / limit it was asked for.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from push import history as H  # noqa: E402


class _Cursor:
    def __init__(self, coll, q):
        self.coll, self.q = coll, q

    def sort(self, key, direction):
        self.coll.sorted = (key, direction)
        return self

    def limit(self, n):
        self.coll.limited = n
        return self

    def __iter__(self):
        return iter([dict(d) for d in self.coll.rows])


class FakeColl:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.queries = []
        self.sorted = self.limited = None

    def find(self, q):
        self.queries.append(q)
        return _Cursor(self, q)


@pytest.fixture
def coll(monkeypatch):
    c = FakeColl([{"_id": 1, "ts": 10, "ts_iso": datetime(2026, 9, 5, 14, 0, tzinfo=timezone.utc),
                   "kind": "demand_alert", "ticker": "NTAP", "user_email": "a@x"}])
    monkeypatch.setattr(H, "_coll", c)
    monkeypatch.setattr(H, "_disabled", False)
    return c


_VIS = {"$or": [{"user_email": "a@x"}, {"user_email": None}]}


def test_default_query_is_unchanged_visibility_only_sorted_ts_desc(coll):
    rows = H.list_recent("A@x", 25)
    assert coll.queries == [{"$and": [_VIS]}], "no filter given -> the pre-2026-09-05 query"
    assert coll.sorted == ("ts", -1) and coll.limited == 25
    assert rows[0]["_id"] == "1" and rows[0]["ts_iso"] == "2026-09-05T14:00:00+00:00"
    H.list_recent(None, 5)
    assert coll.queries[-1] == {}, "admin path: everything"
    H.list_recent("a@x", 5, kind="todo_reminder")
    assert coll.queries[-1] == {"$and": [_VIS, {"kind": "todo_reminder"}]}, "/push/history kind filter intact"


def test_kinds_list_becomes_an_in_clause_and_an_empty_list_is_no_filter(coll):
    H.list_recent("a@x", 25, kinds=["demand_alert", "zone_bounce_alert", "supply_break_alert"])
    assert coll.queries[-1] == {"$and": [_VIS, {"kind": {"$in": ["demand_alert", "zone_bounce_alert",
                                                                 "supply_break_alert"]}}]}
    H.list_recent("a@x", 25, kinds=[])
    assert coll.queries[-1] == {"$and": [_VIS]}
    H.list_recent("a@x", 25, kinds=[" ", ""])
    assert coll.queries[-1] == {"$and": [_VIS]}, "blank kinds are dropped, not matched"
    H.list_recent("a@x", 25, kinds=[" demand_alert "])
    assert coll.queries[-1] == {"$and": [_VIS, {"kind": {"$in": ["demand_alert"]}}]}


def test_since_is_ts_gte_as_an_int(coll):
    H.list_recent("a@x", 25, since_ts=1_757_000_000)
    assert coll.queries[-1] == {"$and": [_VIS, {"ts": {"$gte": 1_757_000_000}}]}
    H.list_recent("a@x", 25, since_ts=1_757_000_000.7)
    assert coll.queries[-1]["$and"][1] == {"ts": {"$gte": 1_757_000_000}}
    H.list_recent("a@x", 25, since_ts=0)
    assert coll.queries[-1]["$and"][1] == {"ts": {"$gte": 0}}, "0 is a value, not 'absent'"


def test_ticker_is_upper_cased_and_blank_is_ignored(coll):
    H.list_recent("a@x", 25, ticker="ntap")
    assert coll.queries[-1] == {"$and": [_VIS, {"ticker": "NTAP"}]}
    H.list_recent("a@x", 25, ticker=" ")
    assert coll.queries[-1] == {"$and": [_VIS]}
    H.list_recent("a@x", 25, ticker=None)
    assert coll.queries[-1] == {"$and": [_VIS]}


def test_all_filters_compose_in_a_fixed_order(coll):
    H.list_recent("a@x", 40, kinds=["demand_alert"], since_ts=5, ticker="aapl")
    assert coll.queries[-1] == {"$and": [_VIS, {"kind": {"$in": ["demand_alert"]}},
                                         {"ts": {"$gte": 5}}, {"ticker": "AAPL"}]}
    assert coll.limited == 40


def test_limit_is_capped_at_500_and_floored_at_1(coll):
    H.list_recent("a@x", 5000)
    assert coll.limited == 500 == H.MAX_LIMIT
    H.list_recent("a@x", 0)
    assert coll.limited == 1
    H.list_recent("a@x", -3)
    assert coll.limited == 1


def test_no_collection_is_an_empty_list_never_an_error(monkeypatch):
    monkeypatch.setattr(H, "_coll", None)
    monkeypatch.setattr(H, "_disabled", True)
    assert H.list_recent("a@x", 25, kinds=["demand_alert"], since_ts=1, ticker="X") == []
