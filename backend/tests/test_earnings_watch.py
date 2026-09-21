"""Earnings-watch cache/date logic — no network, fake Mongo. The ATEX
lesson encoded: a name reporting tonight must show days_to=0 and be
flagged inside the warn window."""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import earnings_watch as ew


class FakeColl:
    def __init__(self, docs=None):
        self.docs = {d["_id"]: d for d in (docs or [])}

    def find(self, q=None, *a, **k):
        q = q or {}
        for d in self.docs.values():
            if "_id" in q and isinstance(q["_id"], dict):
                if d["_id"] not in q["_id"].get("$in", []):
                    continue
            if "next_date" in q and isinstance(q["next_date"], dict):
                if q["next_date"].get("$ne") == None and d.get("next_date") is None:  # noqa: E711
                    continue
            yield dict(d)

    def find_one(self, q):
        d = self.docs.get(q.get("_id"))
        return dict(d) if d else None

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["_id"]] = dict(doc)


def _patch(coll, today_iso):
    ew._coll = lambda: coll
    from datetime import datetime
    class FakeNow:
        @staticmethod
        def date():
            from datetime import date
            return date.fromisoformat(today_iso)
    ew._today_et = lambda: FakeNow()


class TestEarningsWatch(unittest.TestCase):
    def setUp(self):
        self._orig = (ew._coll, ew._today_et)

    def tearDown(self):
        ew._coll, ew._today_et = self._orig

    def test_days_to_and_today_counts_as_zero(self):
        # ATEX case: report is TODAY (AMC) — days_to must be 0, not hidden.
        coll = FakeColl([{"_id": "ATEX", "next_date": "2026-06-10",
                          "when": "AMC", "fetched_at": int(time.time())}])
        _patch(coll, "2026-06-10")
        self.assertEqual(ew.days_to("ATEX"), 0)
        ev = ew.next_event("ATEX")
        self.assertEqual(ev["days_to"], 0)
        self.assertEqual(ev["when"], "AMC")
        self.assertLessEqual(ev["days_to"], ew.WARN_WINDOW_DAYS)

    def test_past_date_is_none(self):
        coll = FakeColl([{"_id": "ATEX", "next_date": "2026-06-10",
                          "when": "AMC", "fetched_at": int(time.time())}])
        _patch(coll, "2026-06-12")
        self.assertIsNone(ew.days_to("ATEX"))
        self.assertIsNone(ew.next_event("ATEX"))

    def test_bulk_map_filters_past_and_far(self):
        coll = FakeColl([
            {"_id": "SOON", "next_date": "2026-06-15", "when": "BMO", "fetched_at": 1},
            {"_id": "FAR", "next_date": "2026-08-11", "when": None, "fetched_at": 1},
            {"_id": "PAST", "next_date": "2026-06-01", "when": None, "fetched_at": 1},
            {"_id": "NONE", "next_date": None, "when": None, "fetched_at": 1},
        ])
        _patch(coll, "2026-06-11")
        out = ew.bulk_map()
        self.assertTrue(out["ok"])
        self.assertIn("SOON", out["map"])
        self.assertEqual(out["map"]["SOON"]["days_to"], 4)
        self.assertNotIn("FAR", out["map"])     # > 30d horizon
        self.assertNotIn("PAST", out["map"])
        self.assertNotIn("NONE", out["map"])
        self.assertEqual(out["warn_window_days"], 7)

    def test_unknown_symbol_is_none_not_zero(self):
        # Fail open with honesty: unknown must read as "no data", never as
        # "no earnings risk = 0 days" or a false warning.
        _patch(FakeColl(), "2026-06-11")
        self.assertIsNone(ew.days_to("ZZZZ"))

    def test_upcoming_groups_sorted_filtered_labeled(self):
        coll = FakeColl([
            {"_id": "AAA", "next_date": "2026-06-11", "when": "AMC", "fetched_at": 1},
            {"_id": "BBB", "next_date": "2026-06-12", "when": "BMO", "fetched_at": 1},
            {"_id": "CCC", "next_date": "2026-06-12", "when": "AMC", "fetched_at": 1},
            {"_id": "FAR", "next_date": "2026-07-30", "when": None, "fetched_at": 1},  # beyond 14d
            {"_id": "PAST", "next_date": "2026-06-01", "when": None, "fetched_at": 1},
            {"_id": "NONE", "next_date": None, "when": None, "fetched_at": 1},
        ])
        _patch(coll, "2026-06-11")
        out = ew.upcoming(14)
        self.assertTrue(out["ok"])
        labels = [g["label"] for g in out["groups"]]
        self.assertEqual(labels[0], "Today")
        self.assertEqual(labels[1], "Tomorrow")
        self.assertEqual(out["n"], 3)                       # AAA, BBB, CCC
        # within a date, BMO sorts before AMC
        jun12 = [g for g in out["groups"] if g["date"] == "2026-06-12"][0]
        self.assertEqual([n["symbol"] for n in jun12["names"]], ["BBB", "CCC"])
        self.assertNotIn("2026-07-30", [g["date"] for g in out["groups"]])


if __name__ == "__main__":
    unittest.main()


class LastReportMapTests(unittest.TestCase):
    """The BOARD reader (2026-09-20) — ONE cached read, raw stored fields.

    THE UNIT TRAP pinned here: `earnings_calendar.last_report.surprise_pct` is
    a PERCENT (AAL 2026-07-23 reads 227.58 for a $0.15 print against a $0.05
    estimate). `sepa/catalyst.py` carried a FRACTION on a different path until
    2026-09-20; a reader that "normalised" one to the other would render a
    +12% beat as +1,200% or +0.12%.
    """

    def _coll(self, docs):
        c = FakeColl(docs)
        ew._coll = lambda: c
        return c

    def test_the_percent_is_returned_EXACTLY_as_stored(self):
        self._coll([{"_id": "AAL", "last_report": {
            "date": "2026-07-23", "when": "BMO", "eps_actual": 0.15,
            "eps_estimate": 0.05, "surprise_pct": 227.58}}])
        m = ew.last_report_map(["aal"])
        self.assertEqual(m["AAL"]["surprise_pct"], 227.58)
        self.assertEqual(m["AAL"]["eps_actual"], 0.15)
        self.assertEqual(m["AAL"]["when"], "BMO")
        self.assertEqual(m["AAL"]["date"], "2026-07-23")

    def test_NEGATIVE_a_None_last_report_is_OMITTED_not_a_blank_block(self):
        """A nulled `last_report` is the 2026-09-18 merge scar, not a report
        with no surprise. It must read as unknown, never as a zero beat."""
        self._coll([{"_id": "AAA", "last_report": None},
                    {"_id": "BBB", "last_report": {"date": "2026-08-01",
                                                   "surprise_pct": 12.0}}])
        m = ew.last_report_map(["AAA", "BBB"])
        self.assertNotIn("AAA", m)
        self.assertEqual(m["BBB"]["surprise_pct"], 12.0)

    def test_NEGATIVE_a_report_with_no_surprise_keeps_the_key_as_None(self):
        """The caller distinguishes "no report" from "a report Yahoo gave no
        surprise for" — so the key must exist and be None, not be missing."""
        self._coll([{"_id": "AAA", "last_report": {"date": "2026-08-01",
                                                   "eps_actual": 0.30}}])
        m = ew.last_report_map(["AAA"])
        self.assertIn("surprise_pct", m["AAA"])
        self.assertIsNone(m["AAA"]["surprise_pct"])
        self.assertIsNone(m["AAA"]["eps_estimate"])

    def test_an_unknown_symbol_is_absent(self):
        self._coll([])
        self.assertEqual(ew.last_report_map(["AAA"]), {})

    def test_no_mongo_and_no_symbols_are_empty_maps(self):
        ew._coll = lambda: None
        self.assertEqual(ew.last_report_map(["AAA"]), {})
        self._coll([{"_id": "AAA", "last_report": {"date": "2026-08-01"}}])
        self.assertEqual(ew.last_report_map([]), {})

    def test_NEGATIVE_a_read_failure_is_an_empty_map_not_an_exception(self):
        class Boom:
            def find(self, *a, **k):
                raise RuntimeError("mongo down")

        ew._coll = lambda: Boom()
        self.assertEqual(ew.last_report_map(["AAA"]), {})
