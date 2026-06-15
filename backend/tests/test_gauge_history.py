"""Market-gauge trend history — one point per ET day, idempotent, soft-fail.

(Ajay 2026-06-13: "trend graph storing previous reads". The old 'latest' doc was
overwritten each run, so no series existed.)
"""
from __future__ import annotations

from sepa import market_gauge as mg


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, key, direction=1):
        self.rows.sort(key=lambda r: r.get(key) or "", reverse=direction < 0)
        return self

    def __iter__(self):
        return iter(self.rows)


class FakeColl:
    def __init__(self):
        self.docs = {}

    def update_one(self, flt, update, upsert=False):
        _id = flt["_id"]
        self.docs.setdefault(_id, {"_id": _id}).update(update["$set"])

    def find(self, _q, _proj=None):
        return _Cursor([{k: v for k, v in d.items() if k != "_id"} for d in self.docs.values()])


def test_one_point_per_day_idempotent(monkeypatch):
    fake = FakeColl()
    monkeypatch.setattr(mg, "_hist_coll", lambda: fake)
    monkeypatch.setattr(mg, "_today_et", lambda: "2026-06-13")
    mg._record_history({"score": 56, "state": "caution", "source": "preopen"})
    mg._record_history({"score": 58, "state": "caution", "source": "live"})  # same day → overwrites
    out = mg.history(90)
    assert len(out["rows"]) == 1
    assert out["rows"][0]["score"] == 58
    assert out["rows"][0]["date_et"] == "2026-06-13"


def test_history_sorted_oldest_to_newest(monkeypatch):
    fake = FakeColl()
    monkeypatch.setattr(mg, "_hist_coll", lambda: fake)
    for day, score in [("2026-06-11", 50), ("2026-06-13", 56), ("2026-06-12", 53)]:
        monkeypatch.setattr(mg, "_today_et", lambda d=day: d)
        mg._record_history({"score": score, "state": "caution"})
    out = mg.history(90)
    assert [r["date_et"] for r in out["rows"]] == ["2026-06-11", "2026-06-12", "2026-06-13"]
    assert [r["score"] for r in out["rows"]] == [50, 53, 56]


def test_soft_fails_without_mongo(monkeypatch):
    monkeypatch.setattr(mg, "_hist_coll", lambda: None)
    mg._record_history({"score": 56})            # must not raise
    assert mg.history()["rows"] == []


def test_record_skips_missing_score(monkeypatch):
    fake = FakeColl()
    monkeypatch.setattr(mg, "_hist_coll", lambda: fake)
    monkeypatch.setattr(mg, "_today_et", lambda: "2026-06-13")
    mg._record_history({"state": "caution"})     # no score → no row
    assert mg.history()["rows"] == []
