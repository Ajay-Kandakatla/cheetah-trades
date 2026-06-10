"""Score floor on buy-side breakout alerts (Ajay 2026-06-10: "Don't show me
alerts that do not have a score of at least 70. Even they broke out on
volume").

Locks three behaviors:
  - the floor itself (≥70, None fails closed)
  - read-time filtering in list_active for volume_breakout/rising_momentum,
    so pre-floor records (the SFNC score-44 popup) stop showing immediately
  - stage-breakdown (sell-side) alerts are EXEMPT — a breaking-down stock
    has a low score by definition; flooring those would hide the warnings
    that protect held positions.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import breakouts


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def sort(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def __iter__(self):
        return iter(self._rows)


class FakeColl:
    def __init__(self, rows):
        self.rows = rows

    def find(self, *_a, **_k):
        return FakeCursor([dict(r) for r in self.rows])


class FakeDB:
    def __init__(self, rows):
        self.sepa_breakouts = FakeColl(rows)


def _row(ticker, kind, score, _id="x"):
    return {"_id": _id, "ticker": ticker, "kind": kind, "score": score,
            "ts": 10_000, "dismissed_at": None, "reason": "r", "context": {}}


class TestScoreFloor(unittest.TestCase):
    def test_floor_constant_is_70(self):
        self.assertEqual(breakouts.MIN_ALERT_SCORE, 70.0)

    def test_passes(self):
        self.assertTrue(breakouts._passes_score_floor(70))
        self.assertTrue(breakouts._passes_score_floor(88.5))

    def test_fails_below_and_closed_on_missing(self):
        self.assertFalse(breakouts._passes_score_floor(44))      # the SFNC case
        self.assertFalse(breakouts._passes_score_floor(69.9))
        self.assertFalse(breakouts._passes_score_floor(None))
        self.assertFalse(breakouts._passes_score_floor("n/a"))


class TestListActiveReadFilter(unittest.TestCase):
    def setUp(self):
        self._db, self._dis = breakouts._db, breakouts._disabled

    def tearDown(self):
        breakouts._db, breakouts._disabled = self._db, self._dis

    def _run(self, rows):
        breakouts._db = FakeDB(rows)
        breakouts._disabled = False
        return breakouts.list_active()

    def test_low_score_volume_breakout_hidden(self):
        out = self._run([_row("SFNC", "volume_breakout", 44),
                         _row("NVDA", "volume_breakout", 82)])
        self.assertEqual([r["ticker"] for r in out], ["NVDA"])

    def test_low_score_rising_momentum_hidden(self):
        out = self._run([_row("ABC", "rising_momentum", 61)])
        self.assertEqual(out, [])

    def test_other_kinds_not_floored(self):
        # custom-level / catalyst style kinds carry no scan score — the floor
        # must not eat them.
        out = self._run([_row("ZION", "custom_level", None)])
        self.assertEqual([r["ticker"] for r in out], ["ZION"])


if __name__ == "__main__":
    unittest.main()
