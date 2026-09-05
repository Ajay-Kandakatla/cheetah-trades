"""GET /notifications/recent (push/recent.py) through FastAPI's TestClient.

Ajay 2026-09-05: "can I go to a dedicated page to see the list of alerts? May be
add it to recent alerts or something?" — the /alerts page reads this feed with
kinds / since / ticker. Absent params must produce the pre-2026-09-05 read:
list_recent(email, limit) positionally, sepa_breakouts.find({}), 200-row cap,
merge ts desc, cap at limit.

Pure: push.history.list_recent and sepa.breakouts._get_db are injected via the
module's own hooks; the auth dependency is overridden.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from push import recent as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


class _Cursor:
    def __init__(self, rows, log):
        self.rows, self.log = rows, log

    def sort(self, key, direction):
        self.log["sort"] = (key, direction)
        return self

    def limit(self, n):
        self.log["limit"] = n
        return self

    def __iter__(self):
        return iter(self.rows)


class _Breakouts:
    def __init__(self, rows, log):
        self.rows, self.log = rows, log

    def find(self, q):
        self.log["queries"].append(q)
        return _Cursor(self.rows, self.log)


class _Db:
    def __init__(self, rows, log):
        self.sepa_breakouts = _Breakouts(rows, log)


def _harness(monkeypatch, pushes=None, breakouts=None, db_none=False):
    """Patch the two data hooks in place (gather resolves them lazily) and
    return (client, calls) — calls records list_recent args and the breakout
    queries so a test can prove the default read is unchanged."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from auth import current_user_email
    from push import history as H
    from sepa import breakouts as bk
    calls = {"list_recent": [], "queries": [], "sort": None, "limit": None}

    def fake_list_recent(email, limit, **kw):
        calls["list_recent"].append((email, limit, kw))
        return [dict(p) for p in (pushes or [])]
    monkeypatch.setattr(H, "list_recent", fake_list_recent)
    monkeypatch.setattr(bk, "_get_db", lambda: None if db_none else _Db(breakouts or [], calls))
    app = FastAPI()
    app.include_router(R.router)
    app.dependency_overrides[current_user_email] = lambda: "a@x"
    return TestClient(app), calls


PUSH = {"_id": "p1", "ts": 1_788_616_000, "ts_iso": "2026-09-05T13:46:40+00:00",
        "title": "🧲 NTAP at demand $161.78–167.54", "body": "$171.2 · tested 1x", "kind": "demand_alert",
        "ticker": "NTAP", "url": "/sepa/NTAP?tab=supply", "user_email": "a@x", "sent": 1, "failed": 0, "total": 1}
BK = {"_id": "b1", "ts": 1_788_617_000, "ticker": "AAPL", "kind": "volume_breakout", "reason": "vol 3.1x",
      "context": {"last_close": 231.5, "day_change_pct": 4.25}, "dismissed_at": None}


# ── the default read is the old read ─────────────────────────────────────────
def test_default_read_is_unchanged_positional_list_recent_and_unfiltered_breakouts(monkeypatch):
    c, calls = _harness(monkeypatch, pushes=[PUSH], breakouts=[BK])
    r = c.get("/notifications/recent")
    assert r.status_code == 200
    assert calls["list_recent"] == [("a@x", 25, {})], "no kwargs when no filter was asked for"
    assert calls["queries"] == [{}] and calls["sort"] == ("ts", -1) and calls["limit"] == 200
    body = r.json()
    assert body["count"] == 2 and [x["_id"] for x in body["rows"]] == ["b1", "p1"], "ts desc merge"
    push_row, bk_row = body["rows"][1], body["rows"][0]
    assert push_row["source"] == "push" and push_row["kind"] == "demand_alert" and "dismissed" not in push_row
    assert bk_row == {"_id": "b1", "ts": 1_788_617_000, "ts_iso": "2026-09-05T14:03:20+00:00",
                      "title": "🚀 Volume breakout · AAPL", "body": "$231.50  ·  +4.2%\nvol 3.1x",
                      "kind": "volume_breakout", "ticker": "AAPL", "url": "/sepa/AAPL?from=alert",
                      "user_email": None, "sent": 0, "failed": 0, "total": 0, "source": "breakout",
                      "dismissed": False}


def test_limit_caps_the_merge_and_accepts_up_to_500(monkeypatch):
    pushes = [dict(PUSH, _id=f"p{i}", ts=100 + i) for i in range(5)]
    c, calls = _harness(monkeypatch, pushes=pushes, breakouts=[dict(BK, ts=103)])
    r = c.get("/notifications/recent", params={"limit": 3})
    assert [x["ts"] for x in r.json()["rows"]] == [104, 103, 103] and r.json()["count"] == 3
    assert calls["list_recent"][-1] == ("a@x", 3, {})
    assert c.get("/notifications/recent", params={"limit": 500}).status_code == 200
    assert calls["list_recent"][-1][1] == 500
    assert c.get("/notifications/recent", params={"limit": 501}).status_code == 422
    assert c.get("/notifications/recent", params={"limit": 0}).status_code == 422


def test_db_down_or_find_raising_still_returns_the_pushes(monkeypatch):
    c, _ = _harness(monkeypatch, pushes=[PUSH], db_none=True)
    assert [x["_id"] for x in c.get("/notifications/recent").json()["rows"]] == ["p1"]

    class Boom(_Breakouts):
        def find(self, q):
            raise RuntimeError("mongo")
    c2, calls = _harness(monkeypatch, pushes=[PUSH])
    from sepa import breakouts as bk
    db = _Db([], calls)
    db.sepa_breakouts = Boom([], calls)
    monkeypatch.setattr(bk, "_get_db", lambda: db)
    assert [x["_id"] for x in c2.get("/notifications/recent").json()["rows"]] == ["p1"]


# ── the /alerts page filters ─────────────────────────────────────────────────
def test_sd_kinds_filter_the_pushes_and_exclude_the_breakout_source(monkeypatch):
    c, calls = _harness(monkeypatch, pushes=[PUSH], breakouts=[BK])
    r = c.get("/notifications/recent", params={"kinds": "demand_alert,zone_bounce_alert, supply_break_alert,,",
                                               "limit": 200})
    assert r.status_code == 200
    assert calls["list_recent"] == [("a@x", 200, {"kinds": ["demand_alert", "zone_bounce_alert",
                                                            "supply_break_alert"]})]
    assert calls["queries"] == [], "no breakout kind named -> sepa_breakouts is never read"
    assert [x["_id"] for x in r.json()["rows"]] == ["p1"]


def test_naming_a_breakout_kind_reads_breakouts_filtered_to_those_kinds(monkeypatch):
    c, calls = _harness(monkeypatch, pushes=[PUSH], breakouts=[BK])
    r = c.get("/notifications/recent", params={"kinds": "demand_alert,volume_breakout,stage_breakdown_2_4"})
    assert calls["list_recent"][-1][2] == {"kinds": ["demand_alert", "volume_breakout", "stage_breakdown_2_4"]}
    assert calls["queries"] == [{"kind": {"$in": ["volume_breakout", "stage_breakdown_2_4"]}}]
    assert [x["_id"] for x in r.json()["rows"]] == ["b1", "p1"]
    c.get("/notifications/recent", params={"kinds": "rising_momentum"})
    assert calls["queries"][-1] == {"kind": {"$in": ["rising_momentum"]}}


def test_since_and_ticker_reach_both_sources_ticker_upper_cased(monkeypatch):
    c, calls = _harness(monkeypatch, pushes=[PUSH], breakouts=[BK])
    r = c.get("/notifications/recent", params={"since": 1_757_000_000, "ticker": "aapl"})
    assert r.status_code == 200
    assert calls["list_recent"][-1] == ("a@x", 25, {"since_ts": 1_757_000_000, "ticker": "AAPL"})
    assert calls["queries"] == [{"ts": {"$gte": 1_757_000_000}, "ticker": "AAPL"}]
    c.get("/notifications/recent", params={"ticker": "  "})
    assert calls["list_recent"][-1] == ("a@x", 25, {}) and calls["queries"][-1] == {}, "blank ticker = absent"
    assert c.get("/notifications/recent", params={"since": -1}).status_code == 422
    assert c.get("/notifications/recent", params={"since": "yesterday"}).status_code == 422


def test_blank_kinds_is_no_filter(monkeypatch):
    c, calls = _harness(monkeypatch, pushes=[PUSH], breakouts=[BK])
    c.get("/notifications/recent", params={"kinds": " , "})
    assert calls["list_recent"][-1] == ("a@x", 25, {}) and calls["queries"] == [{}]


# ── the pure helpers ─────────────────────────────────────────────────────────
def test_parse_kinds_and_breakout_kinds():
    assert R.parse_kinds(None) is None and R.parse_kinds("") is None and R.parse_kinds(",, ,") is None
    assert R.parse_kinds("a, b,a,,c ") == ["a", "b", "c"]
    assert R.breakout_kinds(None) is None
    assert R.breakout_kinds(["demand_alert"]) == []
    assert R.breakout_kinds(["demand_alert", "volume_breakout", "stage_breakdown_3_4", "rising_momentum"]) == \
        ["volume_breakout", "stage_breakdown_3_4", "rising_momentum"]
    assert R.breakout_query(None, None, None) == {}
    assert R.breakout_query(["demand_alert"], None, None) is None
    assert R.breakout_query(["volume_breakout"], 5, "X") == {"kind": {"$in": ["volume_breakout"]},
                                                               "ts": {"$gte": 5}, "ticker": "X"}


def test_normalize_breakout_defaults_and_unknown_kind():
    row = R.normalize_breakout({"_id": 7, "ticker": "", "kind": "something_new", "ts": None})
    assert row["title"] == "📣 something_new · " and row["url"] is None and row["ts"] == 0
    assert row["ts_iso"] is None and row["body"] == "" and row["dismissed"] is False
    assert R.normalize_breakout({"_id": 8, "ticker": "T", "reason": "r", "ts": 1})["kind"] == "volume_breakout"


def test_main_includes_the_router_and_the_inline_route_is_gone():
    src = (ROOT / "backend/main.py").read_text()
    assert "from push.recent import router as notifications_recent_router" in src
    assert "app.include_router(notifications_recent_router)" in src
    assert '@app.get("/notifications/recent")' not in src, "two handlers for one path"
    assert src.count("/notifications/recent") >= 1
