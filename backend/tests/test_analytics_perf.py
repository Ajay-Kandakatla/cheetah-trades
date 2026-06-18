"""Web-vitals / page-load RUM (Ajay 2026-06-17): capture real page-load + paint
timings to OUR backend so we can see which pages are slow and how they fare on
low-bandwidth links.

Locks: the web-vitals rating thresholds, the percentile roll-up, the
slow-vs-fast-connection split, the ingest filtering (bad metric/value dropped),
and the soft-fail (no Mongo → empty, never a crash).

Run in the backend venv:
  cd backend && .venv/bin/python -m pytest tests/test_analytics_perf.py -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analytics import store


# ── rating thresholds (web.dev/vitals) ───────────────────────────────────────

def test_rating_thresholds():
    assert store._rating("LCP", 2000) == "good"
    assert store._rating("LCP", 3000) == "needs-improvement"
    assert store._rating("LCP", 5000) == "poor"
    assert store._rating("CLS", 0.05) == "good"
    assert store._rating("CLS", 0.3) == "poor"
    assert store._rating("TTFB", 500) == "good"
    assert store._rating("UNKNOWN", 1) == "unknown"


def test_module_of_route():
    assert store._module_of("/sepa/MU") == "sepa"
    assert store._module_of("/breakouts") == "breakouts"
    assert store._module_of("/") == "home"
    assert store._module_of("") == "home"


# ── percentile + roll-up (pure) ──────────────────────────────────────────────

def test_percentile_interpolates():
    s = [1000, 2000, 3000, 4000, 5000]
    assert store._percentile(s, 0.5) == 3000
    assert store._percentile(s, 0.75) == 4000
    assert round(store._percentile(s, 0.95), 1) == 4800.0
    assert store._percentile([], 0.5) is None
    assert store._percentile([42], 0.95) == 42


def test_summarize_groups_and_splits_by_connection():
    docs = []
    # sepa LCP on a FAST link, spread good→poor
    for v, conn in [(1000, "4g"), (2000, "4g"), (3000, "4g"), (4000, "4g"), (5000, "4g")]:
        docs.append({"metric": "LCP", "value": v, "module": "sepa", "conn": conn})
    # sepa LCP on a SLOW link — much worse
    for v in (6000, 8000):
        docs.append({"metric": "LCP", "value": v, "module": "sepa", "conn": "3g"})

    out = store._summarize(docs, days=14)
    assert out["available"] is True and out["n"] == 7

    lcp = next(m for m in out["metrics"] if m["metric"] == "LCP")
    assert lcp["n"] == 7
    # poor = value > 4000 → {5000, 6000, 8000} = 3 of 7
    assert lcp["poor_rate"] == round(3 / 7, 3)
    # the low-internet split is the whole point: slow link p50 is far worse
    assert lcp["slow_conn"]["n"] == 2 and lcp["fast_conn"]["n"] == 5
    assert lcp["slow_conn"]["p50"] > lcp["fast_conn"]["p50"]

    # per-(module, metric) row present
    sepa_lcp = next(r for r in out["routes"] if r["module"] == "sepa" and r["metric"] == "LCP")
    assert sepa_lcp["p50"] == 4000      # median of all 7 sepa LCP samples


def test_summarize_ignores_unknown_metrics_and_bad_values():
    docs = [
        {"metric": "LCP", "value": 1200, "module": "sepa", "conn": "4g"},
        {"metric": "NONSENSE", "value": 5, "module": "sepa", "conn": "4g"},
        {"metric": "LCP", "value": "oops", "module": "sepa", "conn": "4g"},
    ]
    out = store._summarize(docs, days=14)
    assert [m["metric"] for m in out["metrics"]] == ["LCP"]
    assert out["metrics"][0]["n"] == 1


# ── ingest filtering via record_perf (fake Mongo) ────────────────────────────

class _FakeColl:
    def __init__(self):
        self.docs = []

    def insert_many(self, docs, ordered=True):
        self.docs.extend(docs)


class _FakeDB:
    def __init__(self):
        self.perf_events = _FakeColl()


def test_record_perf_filters_and_tags(monkeypatch):
    fake = _FakeDB()
    monkeypatch.setattr(store, "_get_db", lambda: fake)
    n = store.record_perf([
        {"metric": "LCP", "value": 1200, "route": "/sepa/MU", "conn": "4g", "save_data": False},
        {"metric": "CLS", "value": 0.4, "route": "/breakouts", "conn": "3g"},
        {"metric": "BOGUS", "value": 1, "route": "/x"},          # bad metric → dropped
        {"metric": "LCP", "value": float("nan"), "route": "/x"},  # NaN → dropped
        {"metric": "LCP", "value": -5, "route": "/x"},            # negative → dropped
        "not-a-dict",                                             # junk → dropped
    ])
    assert n == 2
    stored = {(d["metric"], d["module"]): d for d in fake.perf_events.docs}
    assert stored[("LCP", "sepa")]["rating"] == "good"
    assert stored[("CLS", "breakouts")]["rating"] == "poor"      # 0.4 > 0.25
    assert stored[("CLS", "breakouts")]["conn"] == "3g"


def test_record_perf_soft_fails_without_mongo(monkeypatch):
    monkeypatch.setattr(store, "_get_db", lambda: None)
    assert store.record_perf([{"metric": "LCP", "value": 1}]) == 0   # no crash
    assert store.record_perf([]) == 0


def test_aggregate_perf_empty_without_mongo(monkeypatch):
    monkeypatch.setattr(store, "_get_db", lambda: None)
    out = store.aggregate_perf(14)
    assert out["available"] is False and out["routes"] == [] and out["n"] == 0
