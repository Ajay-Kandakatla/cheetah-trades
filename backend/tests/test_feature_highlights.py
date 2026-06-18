"""'What's new' feature highlights (Ajay 2026-06-18): highlight each shipped
feature until viewed, log the unviewed ones to analytics.

Locks: per-user seen set, first-view detection (idempotent), impression
logging, and the soft-fail (no Mongo → no crash).

  cd backend && .venv/bin/python -m pytest tests/test_feature_highlights.py -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analytics import store


class _Coll:
    def __init__(self):
        self.docs = []
        self._keys = set()

    def find(self, q, proj=None):
        em = q.get("user_email")
        return [d for d in self.docs if d.get("user_email") == em]

    def update_one(self, filt, update, upsert=False):
        key = (filt["user_email"], filt["feature"])

        class _R:
            upserted_id = None
        r = _R()
        if key in self._keys:
            return r                      # already seen → not newly inserted
        if upsert:
            self.docs.append({**filt, **update.get("$setOnInsert", {})})
            self._keys.add(key)
            r.upserted_id = "oid"
        return r

    def insert_one(self, doc):
        self.docs.append(doc)

    def insert_many(self, docs, ordered=True):
        self.docs.extend(docs)


class _DB:
    def __init__(self):
        self.feature_views = _Coll()
        self.feature_events = _Coll()


def test_first_view_then_idempotent(monkeypatch):
    db = _DB()
    monkeypatch.setattr(store, "_get_db", lambda: db)
    assert store.mark_feature_seen("a@b.com", "breakouts") is True    # first view
    assert store.mark_feature_seen("a@b.com", "breakouts") is False   # already seen
    assert store.feature_seen_set("a@b.com") == ["breakouts"]
    # the view was logged to analytics
    assert any(e.get("kind") == "viewed" for e in db.feature_events.docs)


def test_seen_is_per_user(monkeypatch):
    db = _DB()
    monkeypatch.setattr(store, "_get_db", lambda: db)
    store.mark_feature_seen("a@b.com", "x")
    store.mark_feature_seen("c@d.com", "y")
    assert store.feature_seen_set("a@b.com") == ["x"]
    assert store.feature_seen_set("c@d.com") == ["y"]


def test_impressions_logged_and_filtered(monkeypatch):
    db = _DB()
    monkeypatch.setattr(store, "_get_db", lambda: db)
    assert store.log_feature_impressions("a@b.com", ["x", "y", "  "]) == 2   # blank dropped
    assert all(e["kind"] == "impression" for e in db.feature_events.docs)


def test_soft_fail_without_mongo(monkeypatch):
    monkeypatch.setattr(store, "_get_db", lambda: None)
    assert store.mark_feature_seen("a@b.com", "x") is False
    assert store.feature_seen_set("a@b.com") == []
    assert store.log_feature_impressions("a@b.com", ["x"]) == 0
    assert store.mark_feature_seen("a@b.com", "") is False             # blank feature
