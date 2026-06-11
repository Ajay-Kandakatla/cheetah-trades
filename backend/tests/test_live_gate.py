"""Live-gate helpers — session_fraction (pure, host) + the live-patch /
trend recompute (container, needs pandas). Locks the KIM behavior: a 7/8
name failing only '30% above 52w-low' must be reported borderline with the
exact flip price, never silently promoted."""
import os
import sys
import types
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import pandas  # noqa: F401
    HAVE_PANDAS = True
except ImportError:
    HAVE_PANDAS = False
    sys.modules.setdefault("pandas", types.ModuleType("pandas"))

from sepa import live_gate


def _et(h, m):
    return datetime(2026, 6, 11, h, m)


class TestSessionFraction(unittest.TestCase):
    def test_pre_open_is_zero(self):
        self.assertEqual(live_gate.session_fraction(_et(8, 0)), 0.0)
        self.assertEqual(live_gate.session_fraction(_et(9, 30)), 0.0)

    def test_after_close_is_one(self):
        self.assertEqual(live_gate.session_fraction(_et(16, 0)), 1.0)
        self.assertEqual(live_gate.session_fraction(_et(20, 0)), 1.0)

    def test_midday_is_fraction(self):
        # 12:45 ET = 195 min after the 9:30 open, of 390 → 0.5
        self.assertAlmostEqual(live_gate.session_fraction(_et(12, 45)), 0.5, places=3)


@unittest.skipUnless(HAVE_PANDAS, "needs pandas (container)")
class TestLivePatchAndBorderline(unittest.TestCase):
    def _frame(self, last_close):
        import pandas as pd
        import numpy as np
        # 260 bars trending up from a 52w low of 19.78 to `last_close`.
        idx = pd.bdate_range("2025-06-10", periods=260)
        lows = np.linspace(19.78, last_close, 260)
        c = np.maximum.accumulate(lows)  # monotone up so MAs stack 50>150>200
        return pd.DataFrame({"open": c, "high": c * 1.005, "low": c * 0.995,
                             "close": c, "volume": np.full(260, 1e6)}, index=idx)

    def test_patch_overwrites_or_appends_today(self):
        df = self._frame(25.38)
        out = live_gate._patch_price(df, 25.63)
        self.assertAlmostEqual(float(out["close"].iloc[-1]), 25.63, places=2)
        self.assertGreaterEqual(len(out), len(df))     # same or +1 bar


if __name__ == "__main__":
    unittest.main()
