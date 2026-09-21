"""Analyst Pulse book verdict — PURE tests on read(), no network, no Mongo.

Rule #4 behavioral kit for backend/sepa/analyst_pulse.py (TLSW p.124-125
estimate revisions, p.89 brokerage-opinion trap, Ch.4 p.41/p.44 target
framing). The WDC fixture uses the REAL yfinance numbers observed live on
2026-06-12 (targets mean 542.30 / high 685 / median 545; 0y EPS 9.94013 vs
9.92107 (30d) vs 8.85861 (90d); +1y 17.92181 vs 17.41786 vs 13.57733;
Mizuho 2026-06-08 PT 550 -> 645) so the signed-percent math is anchored to
data the module actually ingests.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import analyst_pulse as ap


def trend_block(cur, d30, d90):
    """Build an eps_trend period entry the way fetch_one stores it."""
    return {"current": cur, "d30": d30, "d90": d90,
            "rev_pct_30d": ap.rev_pct(cur, d30),
            "rev_pct_90d": ap.rev_pct(cur, d90)}


def wdc_doc():
    """Realistic fixture — live yfinance numbers for WDC, 2026-06-12."""
    return {
        "symbol": "WDC", "fetched_at": 1,
        "targets": {"mean": 542.30, "median": 545.0, "high": 685.0,
                    "low": None, "current": None},
        "eps_trend": {
            "0q": trend_block(2.5, 2.45, 2.2),
            "0y": trend_block(9.94013, 9.92107, 8.85861),
            "+1y": trend_block(17.92181, 17.41786, 13.57733),
        },
        "rev_counts": {"0y": {"up30": 3, "down30": 0}},
        "actions": [{"date": "2026-06-08", "firm": "Mizuho",
                     "action": "main", "from_grade": "Outperform",
                     "to_grade": "Outperform",
                     "prior_pt": 550.0, "new_pt": 645.0}],
        "error": None,
    }


class TestRevPct(unittest.TestCase):
    def test_signed_negative_eps_is_upward(self):
        # -1.00 -> -0.50 is an UPWARD revision: +50%, NOT -50%.
        self.assertAlmostEqual(ap.rev_pct(-0.5, -1.0), 50.0, places=6)

    def test_signed_negative_eps_downward(self):
        # -0.50 -> -1.00 estimate move is a DOWNWARD revision: -100% of |base|.
        self.assertAlmostEqual(ap.rev_pct(-1.0, -0.5), -100.0, places=6)

    def test_cross_zero(self):
        # Loss -> profit flip stays positive: (0.5 - -0.5)/0.5 = +200%.
        self.assertAlmostEqual(ap.rev_pct(0.5, -0.5), 200.0, places=6)

    def test_zero_or_missing_base_is_none(self):
        self.assertIsNone(ap.rev_pct(1.0, 0.0))
        self.assertIsNone(ap.rev_pct(1.0, None))
        self.assertIsNone(ap.rev_pct(None, 1.0))
        self.assertIsNone(ap.rev_pct(float("nan"), 1.0))


class TestWdcFixture(unittest.TestCase):
    def test_90d_windows_match_live_numbers(self):
        r = ap.read(wdc_doc(), live_price=500.0, in_uptrend=True)
        self.assertAlmostEqual(r["fy_rev_90d"], 12.2, delta=0.2)
        self.assertAlmostEqual(r["next_fy_rev_90d"], 32.0, delta=0.2)

    def test_30d_small_positive_trending_both(self):
        r = ap.read(wdc_doc(), live_price=500.0, in_uptrend=True)
        self.assertGreater(r["fy_rev_30d"], 0)
        self.assertLess(r["fy_rev_30d"], ap.REVISION_BIG_PCT)
        self.assertGreater(r["next_fy_rev_30d"], 0)
        self.assertEqual(r["trending_higher"], "both")

    def test_big_up_keyed_off_30d_not_90d(self):
        # The book never states the 5% study's window; the badge is keyed
        # off 30d (the p.125 window) — 90d ships separately as context.
        r = ap.read(wdc_doc(), live_price=500.0, in_uptrend=True)
        self.assertFalse(r["big_up"])
        self.assertTrue(r["big_up_90d"])
        self.assertFalse(r["red_flag"])
        self.assertEqual(r["verdict"], "trending_higher")

    def test_target_raise_counted_upgrade_not(self):
        # Mizuho 550 -> 645 is a target RAISE; Action 'main' is no up/down.
        r = ap.read(wdc_doc(), live_price=500.0, in_uptrend=True)
        self.assertEqual(r["target_raises_90d"], 1)
        self.assertEqual(r["target_cuts_90d"], 0)
        self.assertEqual(r["upgrades_90d"], 0)
        self.assertEqual(r["downgrades_90d"], 0)

    def test_implied_upside_is_mean_vs_live(self):
        r = ap.read(wdc_doc(), live_price=500.0, in_uptrend=True)
        self.assertAlmostEqual(r["implied_upside_pct"], 8.46, delta=0.01)


class TestThresholdBoundaries(unittest.TestCase):
    def test_plus_five_exactly_is_big_up(self):
        doc = {"eps_trend": {"0y": trend_block(105.0, 100.0, None)}}
        r = ap.read(doc, None, True)
        self.assertEqual(r["fy_rev_30d"], 5.0)
        self.assertTrue(r["big_up"])
        self.assertEqual(r["verdict"], "revisions_up_big")

    def test_minus_five_exactly_is_red_flag(self):
        doc = {"eps_trend": {"0y": trend_block(95.0, 100.0, None)}}
        r = ap.read(doc, None, True)
        self.assertEqual(r["fy_rev_30d"], -5.0)
        self.assertTrue(r["red_flag"])
        self.assertEqual(r["verdict"], "red_flag")

    def test_just_inside_thresholds_neither(self):
        doc = {"eps_trend": {"0y": trend_block(104.9, 100.0, None),
                             "+1y": trend_block(95.1, 100.0, None)}}
        r = ap.read(doc, None, True)
        self.assertFalse(r["big_up"])
        self.assertFalse(r["red_flag"])

    def test_next_fy_window_also_triggers(self):
        # "either FY window" — +1y alone can fire big_up / red_flag.
        up = {"eps_trend": {"+1y": trend_block(106.0, 100.0, None)}}
        self.assertTrue(ap.read(up, None, True)["big_up"])
        down = {"eps_trend": {"+1y": trend_block(94.0, 100.0, None)}}
        self.assertTrue(ap.read(down, None, True)["red_flag"])


class TestNegativeEpsRead(unittest.TestCase):
    def test_loss_narrowing_reads_as_upward_revision(self):
        # -1.00 -> -0.50: read() must see +50% (big_up), never -50% (red_flag).
        doc = {"eps_trend": {"0y": trend_block(-0.5, -1.0, None)}}
        r = ap.read(doc, None, True)
        self.assertAlmostEqual(r["fy_rev_30d"], 50.0, places=6)
        self.assertTrue(r["big_up"])
        self.assertFalse(r["red_flag"])


class TestP89Trap(unittest.TestCase):
    def doc_with_upgrade(self):
        return {"actions": [{"date": "2026-06-01", "firm": "Citi",
                             "action": "up", "from_grade": "Neutral",
                             "to_grade": "Buy",
                             "prior_pt": None, "new_pt": None}]}

    def test_upgrade_on_broken_name_is_trap(self):
        r = ap.read(self.doc_with_upgrade(), None, in_uptrend=False)
        self.assertTrue(r["p89_trap"])
        self.assertEqual(r["context"], "broken")
        self.assertEqual(r["verdict"], "p89_trap")

    def test_same_upgrade_in_uptrend_is_not_trap(self):
        r = ap.read(self.doc_with_upgrade(), None, in_uptrend=True)
        self.assertFalse(r["p89_trap"])
        self.assertEqual(r["context"], "uptrend")
        self.assertNotEqual(r["verdict"], "p89_trap")

    def test_unknown_context_never_calls_trap(self):
        r = ap.read(self.doc_with_upgrade(), None, in_uptrend=None)
        self.assertFalse(r["p89_trap"])
        self.assertEqual(r["context"], "unknown")

    def test_target_raise_alone_triggers_trap_on_broken(self):
        doc = {"actions": [{"date": "2026-06-01", "firm": "GS",
                            "action": "main", "from_grade": None,
                            "to_grade": None,
                            "prior_pt": 100.0, "new_pt": 120.0}]}
        r = ap.read(doc, None, in_uptrend=False)
        self.assertTrue(r["p89_trap"])

    def test_broken_with_no_actions_is_not_trap(self):
        r = ap.read({"actions": []}, None, in_uptrend=False)
        self.assertFalse(r["p89_trap"])
        self.assertEqual(r["context"], "broken")


class TestBrokenNeverBullish(unittest.TestCase):
    """p.86: 'trust what you see, not what you hear. Tune out the analyst.'
    Bullish VERDICTS never fire on a broken (non-Stage-2) name — even when
    the estimate data alone is bullish and no broker action tripped the
    p.89 trap. The raw fields still ship as data; the call is gated."""

    def test_big_up_on_broken_with_no_actions_is_not_bullish(self):
        doc = {"eps_trend": {"0y": trend_block(110.0, 100.0, None)},
               "actions": []}
        r = ap.read(doc, None, in_uptrend=False)
        self.assertTrue(r["big_up"])                  # data still ships
        self.assertFalse(r["p89_trap"])               # no actions -> no trap
        self.assertEqual(r["verdict"], "neutral")     # but never bullish

    def test_trending_higher_on_broken_is_not_bullish(self):
        doc = {"eps_trend": {"0y": trend_block(102.0, 100.0, None)}}
        r = ap.read(doc, None, in_uptrend=False)
        self.assertEqual(r["trending_higher"], "fy")  # data still ships
        self.assertEqual(r["verdict"], "neutral")

    def test_unknown_context_keeps_the_bullish_read(self):
        # Not in the scan (e.g. a portfolio holding) -> no trend context;
        # the revision read itself still applies (only 'broken' gates it).
        doc = {"eps_trend": {"0y": trend_block(110.0, 100.0, None)}}
        r = ap.read(doc, None, in_uptrend=None)
        self.assertEqual(r["verdict"], "revisions_up_big")

    def test_red_flag_still_fires_on_broken(self):
        doc = {"eps_trend": {"0y": trend_block(90.0, 100.0, None)}}
        r = ap.read(doc, None, in_uptrend=False)
        self.assertEqual(r["verdict"], "red_flag")


class TestVerdictPrecedence(unittest.TestCase):
    def test_red_flag_beats_p89_trap(self):
        doc = {"eps_trend": {"0y": trend_block(90.0, 100.0, None)},
               "actions": [{"date": "2026-06-01", "firm": "Citi",
                            "action": "up", "from_grade": "Neutral",
                            "to_grade": "Buy",
                            "prior_pt": None, "new_pt": None}]}
        r = ap.read(doc, None, in_uptrend=False)
        self.assertTrue(r["red_flag"])
        self.assertTrue(r["p89_trap"])
        self.assertEqual(r["verdict"], "red_flag")

    def test_red_flag_beats_bullish_reads(self):
        # FY down big + next-FY up big -> red flag dominates (p.125:
        # "large downward estimate revisions are definitely a red flag").
        doc = {"eps_trend": {"0y": trend_block(90.0, 100.0, None),
                             "+1y": trend_block(110.0, 100.0, None)}}
        r = ap.read(doc, None, in_uptrend=True)
        self.assertTrue(r["big_up"])
        self.assertEqual(r["verdict"], "red_flag")

    def test_trap_beats_bullish_reads(self):
        doc = {"eps_trend": {"0y": trend_block(110.0, 100.0, None)},
               "actions": [{"date": "2026-06-01", "firm": "Citi",
                            "action": "up", "from_grade": None,
                            "to_grade": None,
                            "prior_pt": None, "new_pt": None}]}
        r = ap.read(doc, None, in_uptrend=False)
        self.assertEqual(r["verdict"], "p89_trap")

    def test_empty_doc_is_neutral(self):
        r = ap.read(None, None, None)
        self.assertEqual(r["verdict"], "neutral")
        self.assertIsNone(r["trending_higher"])
        self.assertIsNone(r["fy_rev_30d"])


class TestImpliedUpsideNoneSafety(unittest.TestCase):
    def test_no_live_price_is_none(self):
        r = ap.read(wdc_doc(), live_price=None, in_uptrend=True)
        self.assertIsNone(r["implied_upside_pct"])

    def test_zero_live_price_is_none(self):
        r = ap.read(wdc_doc(), live_price=0.0, in_uptrend=True)
        self.assertIsNone(r["implied_upside_pct"])

    def test_no_mean_target_is_none(self):
        doc = wdc_doc()
        doc["targets"] = {"mean": None, "median": 545.0, "high": 685.0,
                          "low": None, "current": None}
        r = ap.read(doc, live_price=500.0, in_uptrend=True)
        self.assertIsNone(r["implied_upside_pct"])

    def test_no_targets_block_is_none(self):
        doc = wdc_doc()
        doc["targets"] = None
        r = ap.read(doc, live_price=500.0, in_uptrend=True)
        self.assertIsNone(r["implied_upside_pct"])


# ─────────────────────────────────────────────────────────────────────────────
# Analyst COUNT (2026-09-20) — the Bonde "no analyst coverage" leg.
#
# PROBED live (yfinance 1.2.0): AAPL `earnings_estimate.numberOfAnalysts`
# [27,21,39,40]; SLNH [1,1,1,1]; BTCS (no coverage) → an EMPTY frame, no
# column, no exception. Yahoo NEVER prints 0. So an empty frame is the only
# evidence of no coverage, and it is labelled `empty_frame` rather than stored
# as a bare 0 that a reader would mistake for a measurement.
# ─────────────────────────────────────────────────────────────────────────────
import pandas as pd


class FakeTicker:
    """yfinance double — `earnings_estimate` only; every other property this
    path reads throws, exactly as a thin-coverage name does."""

    def __init__(self, estimate=None, raises=False):
        self._estimate = estimate
        self._raises = raises

    @property
    def earnings_estimate(self):
        if self._raises:
            raise RuntimeError("no data")
        return self._estimate

    def _boom(self):
        raise RuntimeError("no data")

    analyst_price_targets = property(_boom)
    eps_trend = property(_boom)
    eps_revisions = property(_boom)
    upgrades_downgrades = property(_boom)


def _fetch(ticker):
    from sepa import symbols as S
    old = S.yf_ticker
    S.yf_ticker = lambda sym: ticker
    try:
        return ap.fetch_one("FOO")
    finally:
        S.yf_ticker = old


class AnalystCountTests(unittest.TestCase):

    def test_a_0q_row_reads_the_count(self):
        df = pd.DataFrame({"numberOfAnalysts": [7, 8]}, index=["0q", "+1q"])
        doc = _fetch(FakeTicker(df))
        self.assertEqual(doc["n_analysts"], 7)
        self.assertEqual(doc["n_analysts_source"], "0q_row")

    def test_an_EMPTY_frame_is_the_only_no_coverage_evidence(self):
        doc = _fetch(FakeTicker(pd.DataFrame()))
        self.assertEqual(doc["n_analysts"], 0)
        self.assertEqual(doc["n_analysts_source"], "empty_frame")

    def test_NEGATIVE_a_frame_with_rows_but_no_count_column_is_UNKNOWN_not_zero(self):
        """A schema change at Yahoo must read as "we do not know", never as
        "nobody covers it" — the leg's PASS answer is no-coverage."""
        df = pd.DataFrame({"avg": [1.0]}, index=["0q"])
        doc = _fetch(FakeTicker(df))
        self.assertIsNone(doc["n_analysts"])
        self.assertIsNone(doc["n_analysts_source"])

    def test_NEGATIVE_a_frame_with_no_0q_row_is_UNKNOWN_not_zero(self):
        df = pd.DataFrame({"numberOfAnalysts": [9]}, index=["+1y"])
        doc = _fetch(FakeTicker(df))
        self.assertIsNone(doc["n_analysts"])
        self.assertIsNone(doc["n_analysts_source"])

    def test_NEGATIVE_a_None_frame_is_UNKNOWN(self):
        doc = _fetch(FakeTicker(None))
        self.assertIsNone(doc["n_analysts"])
        self.assertIsNone(doc["n_analysts_source"])

    def test_NEGATIVE_a_RAISING_property_leaves_the_doc_shipping(self):
        """Thin names throw per property. The refresh must never crash and the
        other fields must still be written."""
        doc = _fetch(FakeTicker(raises=True))
        self.assertIsNone(doc["n_analysts"])
        self.assertIsNone(doc["n_analysts_source"])
        self.assertEqual(doc["symbol"], "FOO")
        self.assertIn("n_analysts", doc)


class CoverageMapTests(unittest.TestCase):
    """The BOARD reader. `get_map()` makes a bulk LIVE price call; the Bonde
    board renders off the last scan and must make no network call at all."""

    class FakeColl:
        def __init__(self, docs):
            self.docs = docs

        def find(self, q, proj=None):
            ids = (q.get("_id") or {}).get("$in", [])
            for d in self.docs:
                if d["_id"] in ids:
                    yield dict(d)

    def _patch(self, docs):
        ap._coll = lambda: CoverageMapTests.FakeColl(docs)

    def test_coverage_map_never_calls_bulk_live(self):
        def boom(_syms):
            raise AssertionError("the board path made a live price call")

        old_coll, old_live = ap._coll, ap._bulk_live
        ap._bulk_live = boom
        try:
            self._patch([{"_id": "FOO", "n_analysts": 0,
                          "n_analysts_source": "empty_frame", "fetched_at": 42}])
            m = ap.coverage_map(["foo"])
        finally:
            ap._coll, ap._bulk_live = old_coll, old_live
        self.assertEqual(m["FOO"]["n_analysts"], 0)
        self.assertEqual(m["FOO"]["n_analysts_source"], "empty_frame")
        self.assertEqual(m["FOO"]["fetched_at"], 42)

    def test_NEGATIVE_a_PRE_2026_09_20_doc_reads_None_not_zero(self):
        """1,365 docs predate the field. Absent must read as unknown — a 0
        there would mint a false "no analyst coverage ✓" on every one."""
        old = ap._coll
        try:
            self._patch([{"_id": "FOO", "fetched_at": 1}])
            m = ap.coverage_map(["FOO"])
        finally:
            ap._coll = old
        self.assertIsNone(m["FOO"]["n_analysts"])
        self.assertIsNone(m["FOO"]["n_analysts_source"])

    def test_NEGATIVE_an_unknown_symbol_is_ABSENT_not_a_zero_entry(self):
        old = ap._coll
        try:
            self._patch([])
            m = ap.coverage_map(["FOO"])
        finally:
            ap._coll = old
        self.assertEqual(m, {})

    def test_no_mongo_returns_an_empty_map(self):
        old = ap._coll
        try:
            ap._coll = lambda: None
            self.assertEqual(ap.coverage_map(["FOO"]), {})
        finally:
            ap._coll = old


if __name__ == "__main__":
    unittest.main()
