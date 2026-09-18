"""`sepa.earnings_watch.refresh(merge=True)` — a PAST fact is never erased by a
fetch that did not see it; a FORWARD estimate is.

Measured 2026-09-18 on the live `earnings_calendar`: 16 of the 21 names on the
🚀 Explosive Growth board carry `last_report: None`, and CRDO — the one name
with a real report on file — loses it the moment one fetch misses, because the
write at `earnings_watch.refresh` is a full `replace_one`. A nulled
`last_report` silently drops a name from `sepa.earnings_picks`, which is read on
Portfolio / SEPA / Leaderboard / Scalping.

`merge=False` stays the DEFAULT: the shared 17:45 nightly sweep over ~2,078
symbols must behave exactly as it does today. That is pinned here too, so
flipping the default later is a real, reversible choice and not a silent drift.
"""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import earnings_watch as ew

# CRDO's real live doc shape, read out of the container 2026-09-18.
CRDO_LAST = {"date": "2026-09-01", "when": "AMC", "eps_actual": 0.41,
             "eps_estimate": 0.386, "surprise_pct": 6.1}

# The `Ticker.calendar` fallback shape — `_fetch_next` returns this literally
# (earnings_watch._fetch_next), and it carries last_report: None by construction.
FALLBACK = {"next_date": "2026-11-04", "when": None,
            "eps_estimate": None, "last_report": None}


class FakeColl:
    """House pattern (tests/test_earnings_watch.py)."""

    def __init__(self, docs=None):
        self.docs = {d["_id"]: d for d in (docs or [])}

    def find(self, q=None, *a, **k):
        q = q or {}
        for d in self.docs.values():
            if "_id" in q and isinstance(q["_id"], dict):
                if d["_id"] not in q["_id"].get("$in", []):
                    continue
            yield dict(d)

    def find_one(self, q):
        d = self.docs.get(q.get("_id"))
        return dict(d) if d else None

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["_id"]] = dict(doc)


class MergeTest(unittest.TestCase):
    def setUp(self):
        self._orig = (ew._coll, ew._today_et, ew._fetch_next, ew._universe)

    def tearDown(self):
        ew._coll, ew._today_et, ew._fetch_next, ew._universe = self._orig

    def _wire(self, docs, fetch):
        coll = FakeColl(docs)
        ew._coll = lambda: coll
        ew._fetch_next = lambda sym: fetch(sym) if callable(fetch) else fetch
        return coll

    # ---------------------------------------------------------------- merge=True

    def test_a_failed_fetch_never_nulls_an_existing_last_report(self):
        """THE PIN. `_fetch_next -> None` on CRDO's real doc, merge=True."""
        coll = self._wire([{"_id": "CRDO", "fetched_at": 1,
                            "next_date": None, "when": None,
                            "eps_estimate": None,
                            "last_report": dict(CRDO_LAST)}],
                          lambda s: None)
        out = ew.refresh(symbols=["CRDO"], max_workers=1, force=True, merge=True)
        self.assertTrue(out["ok"])
        self.assertEqual(out["refreshed"], 1)
        self.assertEqual(coll.docs["CRDO"]["last_report"], CRDO_LAST)

    def test_the_calendar_fallback_shape_never_nulls_last_report(self):
        coll = self._wire([{"_id": "CRDO", "fetched_at": 1,
                            "last_report": dict(CRDO_LAST)}],
                          lambda s: dict(FALLBACK))
        ew.refresh(symbols=["CRDO"], max_workers=1, force=True, merge=True)
        self.assertEqual(coll.docs["CRDO"]["last_report"], CRDO_LAST)
        # the forward estimate DID land
        self.assertEqual(coll.docs["CRDO"]["next_date"], "2026-11-04")

    def test_a_newer_last_report_always_wins(self):
        newer = {"date": "2026-09-16", "when": "BMO", "eps_actual": 1.0,
                 "eps_estimate": 0.9, "surprise_pct": 11.1}
        coll = self._wire([{"_id": "CRDO", "fetched_at": 1,
                            "last_report": dict(CRDO_LAST)}],
                          lambda s: {"next_date": None, "when": None,
                                     "eps_estimate": None,
                                     "last_report": dict(newer)})
        ew.refresh(symbols=["CRDO"], max_workers=1, force=True, merge=True)
        self.assertEqual(coll.docs["CRDO"]["last_report"], newer)

    def test_merge_does_not_preserve_a_stale_forward_estimate(self):
        """NEGATIVE — a PAST fact is kept, a FORWARD estimate is not."""
        coll = self._wire([{"_id": "CRDO", "fetched_at": 1,
                            "next_date": "2026-09-01", "when": "AMC",
                            "eps_estimate": 0.386,
                            "last_report": dict(CRDO_LAST)}],
                          lambda s: None)
        ew.refresh(symbols=["CRDO"], max_workers=1, force=True, merge=True)
        d = coll.docs["CRDO"]
        self.assertEqual(d["last_report"], CRDO_LAST)
        self.assertIsNone(d["next_date"])
        self.assertIsNone(d["when"])
        self.assertIsNone(d["eps_estimate"])

    def test_merge_on_a_doc_that_never_existed_upserts_the_all_none_shape(self):
        coll = self._wire([], lambda s: None)
        ew.refresh(symbols=["ZZZZ"], max_workers=1, force=True, merge=True)
        d = coll.docs["ZZZZ"]
        self.assertIsNone(d["last_report"])
        self.assertIsNone(d["next_date"])
        self.assertEqual(d["_id"], "ZZZZ")

    def test_fetched_at_advances_on_a_miss(self):
        coll = self._wire([{"_id": "CRDO", "fetched_at": 1,
                            "last_report": dict(CRDO_LAST)}],
                          lambda s: None)
        ew.refresh(symbols=["CRDO"], max_workers=1, force=True, merge=True)
        self.assertGreater(coll.docs["CRDO"]["fetched_at"], int(time.time()) - 60)

    # --------------------------------------------------------------- merge=False

    def test_merge_false_still_replaces(self):
        """NEGATIVE — the destructive path still exists and is still reachable,
        EXPLICITLY. merge=True became the default 2026-09-18 on Ajay's call; a
        caller that asks for the old whole-document replace must still get it,
        or there is no way to reproduce the bug this fixed."""
        for fetch in (lambda s: None, lambda s: dict(FALLBACK)):
            coll = self._wire([{"_id": "CRDO", "fetched_at": 1,
                                "last_report": dict(CRDO_LAST)}], fetch)
            ew.refresh(symbols=["CRDO"], max_workers=1, force=True, merge=False)
            self.assertIsNone(coll.docs["CRDO"]["last_report"])

    def test_THE_DEFAULT_now_protects_a_past_report(self):
        """The flip itself. A no-merge-kwarg call — which is what the shared
        17:45 nightly sweep makes — must KEEP a report a failed fetch did not
        see. This is the 16-of-21 scar on the growth board."""
        for fetch in (lambda s: None, lambda s: dict(FALLBACK)):
            coll = self._wire([{"_id": "CRDO", "fetched_at": 1,
                                "last_report": dict(CRDO_LAST)}], fetch)
            ew.refresh(symbols=["CRDO"], max_workers=1, force=True)
            self.assertEqual(coll.docs["CRDO"]["last_report"], dict(CRDO_LAST))

    def test_refresh_signature_is_backwards_compatible(self):
        import inspect
        sig = inspect.signature(ew.refresh)
        # merge defaults TRUE as of 2026-09-18 (his call); force stays False.
        self.assertTrue(sig.parameters["merge"].default)
        self.assertFalse(sig.parameters["force"].default)
        coll = self._wire([], lambda s: None)
        # no-arg (falls through to _universe, stubbed empty)
        ew._universe = lambda: []
        self.assertTrue(ew.refresh()["ok"])
        self.assertTrue(ew.refresh(symbols=["AAA"])["ok"])
        self.assertTrue(ew.refresh(symbols=["AAA"], force=True)["ok"])
        self.assertTrue(ew.refresh(["AAA"], 1, True)["ok"])
        self.assertIn("AAA", coll.docs)


if __name__ == "__main__":
    unittest.main()
