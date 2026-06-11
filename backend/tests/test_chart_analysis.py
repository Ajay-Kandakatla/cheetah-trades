"""Chart-analysis validation layer — the LLM's output must conform or be
rejected (never show the user a malformed/invented verdict). No network."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa.chart_analysis import _VERDICTS, _validate


class TestValidate(unittest.TestCase):
    def test_good_verdict_passes(self):
        out = _validate({"verdict": "BUY_ON_CLOSE_CONFIRM", "confidence": "medium",
                         "entry": 48.81, "stop": 45.39, "risk_pct": 7.0,
                         "thesis": ["cup confirmed intraday", "needs the close"],
                         "risks": ["own record n=1 negative"],
                         "what_would_change_it": "close below 48.81"})
        self.assertIsNotNone(out)
        self.assertEqual(out["verdict"], "BUY_ON_CLOSE_CONFIRM")
        self.assertEqual(out["entry"], 48.81)

    def test_unknown_verdict_rejected(self):
        self.assertIsNone(_validate({"verdict": "YOLO", "thesis": []}))
        self.assertIsNone(_validate({"thesis": ["no verdict at all"]}))
        self.assertIsNone(_validate("not a dict"))

    def test_bad_confidence_degrades_to_low(self):
        out = _validate({"verdict": "WAIT", "confidence": "certain!!"})
        self.assertEqual(out["confidence"], "low")

    def test_lists_capped(self):
        out = _validate({"verdict": "PASS",
                         "thesis": [str(i) for i in range(10)],
                         "risks": [str(i) for i in range(10)]})
        self.assertEqual(len(out["thesis"]), 5)
        self.assertEqual(len(out["risks"]), 4)

    def test_verdict_whitelist_locked(self):
        self.assertEqual(_VERDICTS,
                         ("BUY_NOW", "BUY_ON_CLOSE_CONFIRM", "WAIT", "PASS"))


if __name__ == "__main__":
    unittest.main()
