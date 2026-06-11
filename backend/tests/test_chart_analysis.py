"""Chart-analysis validation layer — the LLM's output must conform or be
rejected (never show the user a malformed/invented verdict). No network."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa.chart_analysis import _VERDICTS, _validate, own_record_summary, MIN_RECORD_N


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


class TestOwnRecordSummary(unittest.TestCase):
    def test_kim_case_flagged_insufficient(self):
        # The exact KIM record that the model wrongly called "catastrophic".
        rec = {"double_bottom": {"n": 1, "pct_positive_21d": 0.0},
               "triple_bottom": {"n": 2, "pct_positive_21d": 0.0},
               "cup_with_handle": {"n": 5, "pct_positive_21d": 0.0}}
        s = own_record_summary(rec)
        self.assertEqual(s["total_resolved_instances"], 8)
        self.assertFalse(s["statistically_sufficient"])
        self.assertIn("ANECDOTE", s["note"])

    def test_sufficient_when_a_pattern_clears_min_n(self):
        rec = {"cup_with_handle": {"n": MIN_RECORD_N + 3, "pct_positive_21d": 0.6}}
        self.assertTrue(own_record_summary(rec)["statistically_sufficient"])

    def test_empty_record_is_insufficient_not_crash(self):
        s = own_record_summary(None)
        self.assertFalse(s["statistically_sufficient"])
        self.assertEqual(s["total_resolved_instances"], 0)


if __name__ == "__main__":
    unittest.main()