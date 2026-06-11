"""Monthly pattern-accuracy rollup (patterns/history §4) — grouping math,
perpetual upsert-only persistence (no deletes, ever), and the series read.
Fake Mongo, no network.
"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# The rollup functions under test never touch pandas/detector, but the module
# imports them at top level — stub ONLY when missing (host py3.9), so the
# container run still uses the real ones.
try:
    import pandas  # noqa: F401
except ImportError:
    sys.modules["pandas"] = types.ModuleType("pandas")
try:
    from patterns import detector  # noqa: F401
except ImportError:
    stub = types.ModuleType("patterns.detector")
    stub.VALIDATION_HORIZON = 21
    sys.modules["patterns.detector"] = stub

from patterns import history


class FakeObsColl:
    def __init__(self, docs):
        self.docs = docs

    def find(self, q=None):
        q = q or {}
        for d in self.docs:
            if "resolved" in q and d.get("resolved") != q["resolved"]:
                continue
            yield dict(d)


class FakeMonthlyColl:
    """Upsert-supporting fake. Records every operation so the no-delete
    contract is checkable."""
    def __init__(self):
        self.docs = {}
        self.deletes = 0

    def update_one(self, q, u, upsert=False):
        _id = q["_id"]
        if _id not in self.docs and upsert:
            self.docs[_id] = {"_id": _id}
        if _id in self.docs and "$set" in u:
            self.docs[_id].update(u["$set"])

    def find(self, q=None):
        return [dict(d) for d in self.docs.values()]

    def delete_one(self, *a, **k):       # nothing in the module should call these
        self.deletes += 1

    def delete_many(self, *a, **k):
        self.deletes += 1


def obs(month_day, pattern=None, status=None, outcome=None, kind="pattern",
        formation=None, fwd21=None, buyable=False, resolved=True):
    return {"et_date": month_day, "kind": kind, "pattern": pattern,
            "status": status, "outcome": outcome, "formation": formation,
            "fwd_21_pct": fwd21, "is_buyable": buyable, "resolved": resolved,
            "symbol": "X"}


LEDGER = [
    # June 2026 — cup: 2 wins 1 stop; double bottom forming: 1 confirm
    obs("2026-06-03", "cup_with_handle", "confirmed", "target_first", fwd21=8.0, buyable=True),
    obs("2026-06-10", "cup_with_handle", "confirmed", "target_first", fwd21=5.0),
    obs("2026-06-17", "cup_with_handle", "confirmed", "stop_first", fwd21=-4.0),
    obs("2026-06-20", "double_bottom", "forming", "confirmed"),
    obs("2026-06-21", kind="candle", formation="hammer", outcome="hit"),
    obs("2026-06-22", kind="candle", formation="hammer", outcome="miss"),
    # July 2026 — cup: 1 stop
    obs("2026-07-08", "cup_with_handle", "confirmed", "stop_first", fwd21=-2.0),
    # unresolved → ignored by the rollup
    obs("2026-07-09", "double_bottom", "confirmed", resolved=False),
]


class TestComputeMonthly(unittest.TestCase):
    def setUp(self):
        self._orig = history._coll
        history._coll = lambda: FakeObsColl(LEDGER)

    def tearDown(self):
        history._coll = self._orig

    def test_groups_and_rates(self):
        rows = history.compute_monthly()
        self.assertEqual([r["month"] for r in rows], ["2026-06", "2026-07"])
        jun = rows[0]
        cup = jun["patterns"]["cup_with_handle"]
        self.assertEqual(cup["confirmed_n"], 3)
        self.assertEqual(cup["win_pct"], 66.7)
        self.assertEqual(cup["buyable_n"], 1)
        self.assertEqual(cup["buyable_win_pct"], 100.0)
        self.assertEqual(jun["patterns"]["double_bottom"]["forming_confirm_pct"], 100.0)
        self.assertEqual(jun["candles"]["hammer"]["direction_hit_pct"], 50.0)
        self.assertEqual(jun["confirmed_n"], 3)
        self.assertEqual(jun["overall_win_pct"], 66.7)
        jul = rows[1]
        self.assertEqual(jul["overall_win_pct"], 0.0)
        self.assertEqual(jul["n_observations"], 1)   # unresolved one not counted

    def test_median_fwd(self):
        rows = history.compute_monthly()
        self.assertEqual(rows[0]["patterns"]["cup_with_handle"]["median_fwd_21d_pct"], 5.0)


class TestSnapshotPerpetual(unittest.TestCase):
    def setUp(self):
        self._orig = (history._coll, history._monthly_coll)
        history._coll = lambda: FakeObsColl(LEDGER)
        self.monthly = FakeMonthlyColl()
        history._monthly_coll = lambda: self.monthly

    def tearDown(self):
        history._coll, history._monthly_coll = self._orig

    def test_upsert_only_and_idempotent(self):
        r1 = history.snapshot_monthly()
        self.assertTrue(r1["ok"])
        self.assertEqual(set(self.monthly.docs), {"2026-06", "2026-07"})
        history.snapshot_monthly()                    # re-run: updates, never deletes
        self.assertEqual(set(self.monthly.docs), {"2026-06", "2026-07"})
        self.assertEqual(self.monthly.deletes, 0)

    def test_series_reads_persisted_and_sorts(self):
        history.snapshot_monthly()
        out = history.monthly_series()
        self.assertTrue(out["ok"])
        self.assertEqual([m["month"] for m in out["months"]],
                         ["2026-06", "2026-07"])
        self.assertIn("never pruned", out["retention"])


if __name__ == "__main__":
    unittest.main()
