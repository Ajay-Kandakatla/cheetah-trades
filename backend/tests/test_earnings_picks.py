"""Earnings-picks reaction math + gates — synthetic daily frames, no network.
Locks the ATEX-bull-side semantics: AMC report → reaction is the NEXT
session; the tape (reaction + volume + still-holding) is the gate; the EPS
beat only boosts rank."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import pandas as pd
    import numpy as np
    HAVE_PANDAS = True
except ImportError:          # py3.9 host — container CI runs the full math
    HAVE_PANDAS = False
    sys.modules.setdefault("pandas", types.ModuleType("pandas"))

from sepa.earnings_picks import (MIN_REACTION_PCT, MIN_VOL_RATIO,
                                 passes_gates, rank_score)
if HAVE_PANDAS:
    from sepa.earnings_picks import reaction_read


def _frame(closes, vols, start="2026-03-02"):
    idx = pd.bdate_range(start, periods=len(closes))
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99,
                         "close": c, "volume": np.asarray(vols, dtype=float)},
                        index=idx)


@unittest.skipUnless(HAVE_PANDAS, "needs pandas (container)")
class TestReactionRead(unittest.TestCase):
    def _gap_frame(self):
        # 69 quiet days at 100 on 1M shares, then the reaction day: +8% on 4M,
        # then drift to 110.
        closes = [100.0] * 69 + [108.0, 109.0, 110.0]
        vols = [1e6] * 69 + [4e6, 1.5e6, 1.2e6]
        return _frame(closes, vols)

    def test_bmo_reaction_is_report_day(self):
        df = self._gap_frame()
        report_day = df.index[69].date().isoformat()
        r = reaction_read(df, report_day, "BMO")
        self.assertAlmostEqual(r["reaction_pct"], 8.0, places=1)
        self.assertGreaterEqual(r["vol_ratio"], 3.9)
        self.assertTrue(r["still_above_pre"])
        self.assertAlmostEqual(r["drift_since_pct"], 1.85, places=1)
        self.assertTrue(passes_gates(r))

    def test_amc_reaction_is_next_session(self):
        df = self._gap_frame()
        amc_report_day = df.index[68].date().isoformat()  # reports after close
        r = reaction_read(df, amc_report_day, "AMC")
        self.assertEqual(r["reaction_date"], df.index[69].date().isoformat())
        self.assertAlmostEqual(r["reaction_pct"], 8.0, places=1)

    def test_reaction_session_not_traded_yet_is_none(self):
        df = self._gap_frame()
        last_day = df.index[-1].date().isoformat()
        self.assertIsNone(reaction_read(df, last_day, "AMC"))

    def test_faded_reaction_fails_gate(self):
        # +8% pop then full round-trip below the pre-report close
        closes = [100.0] * 69 + [108.0, 101.0, 98.0]
        vols = [1e6] * 69 + [4e6, 2e6, 2e6]
        df = _frame(closes, vols)
        r = reaction_read(df, df.index[69].date().isoformat(), "BMO")
        self.assertFalse(r["still_above_pre"])
        self.assertFalse(passes_gates(r))

    def test_thin_volume_fails_gate(self):
        closes = [100.0] * 69 + [105.0, 106.0, 107.0]
        vols = [1e6] * 69 + [1.1e6, 1e6, 1e6]   # +5% but no participation
        df = _frame(closes, vols)
        r = reaction_read(df, df.index[69].date().isoformat(), "BMO")
        self.assertFalse(passes_gates(r))


class TestGatesAndRank(unittest.TestCase):
    def test_constants_locked(self):
        self.assertEqual(MIN_REACTION_PCT, 3.0)
        self.assertEqual(MIN_VOL_RATIO, 1.5)

    def test_beat_boosts_but_is_not_required(self):
        read = {"reaction_pct": 6.0, "vol_ratio": 3.0, "still_above_pre": True}
        self.assertTrue(passes_gates(read))            # no surprise needed
        base = rank_score(read, None, None)
        with_beat = rank_score(read, 25.0, None)
        self.assertGreater(with_beat, base)

    def test_none_read_fails(self):
        self.assertFalse(passes_gates(None))

    def test_provisional_skips_volume_gate_only(self):
        # ATEX case: +19.5% at 11 AM on PARTIAL volume (1.31x) — must pass
        # provisionally on price; the nightly re-grade applies full volume.
        partial = {"reaction_pct": 19.5, "vol_ratio": 1.31, "still_above_pre": True}
        self.assertFalse(passes_gates(partial))               # final grade: no
        self.assertTrue(passes_gates(partial, provisional=True))
        weak = {"reaction_pct": 1.0, "vol_ratio": 1.31, "still_above_pre": True}
        self.assertFalse(passes_gates(weak, provisional=True))  # price gate stays


if __name__ == "__main__":
    unittest.main()
