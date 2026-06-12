"""Racing-to-R1/R2 board — behavioral tests on synthetic data (host .venv,
no network, no pandas). Locks the leg boundaries, the R-ladder math, the
buy-range inclusivity at exactly +3.0%, NaN safety, sort order, and the 60s
in-process cache. The R convention and the 3.0 constant are additionally
cross-locked against position_lens / scanner in test_sepa_contracts.py."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import racing


def _setup_row(sym, pivot, stop, score=80.0, is_buyable=False,
               qualifier=True, setup_type="VCP"):
    return {
        "symbol": sym, "score": score, "qualifier": qualifier,
        "is_candidate": qualifier, "is_buyable": is_buyable,
        "entry_setup": {"type": setup_type, "pivot": pivot, "stop": stop},
    }


class FakeBackend:
    """Stands in for scanner.load_latest + prices.bulk_live_prices +
    live_gate.live_gate, with call counters for the cache test."""

    def __init__(self, rows, quotes, relvols=None):
        self.rows, self.quotes = rows, quotes
        self.relvols = relvols or {}
        self.load_calls = 0
        self.bulk_calls = 0
        self.gate_calls = 0

    def load_latest(self):
        self.load_calls += 1
        return {"generated_at": 1765500000, "all_results": self.rows}

    def bulk_live_prices(self, symbols):
        self.bulk_calls += 1
        return {s: self.quotes[s] for s in symbols if s in self.quotes}

    def live_gate(self, sym):
        self.gate_calls += 1
        if isinstance(self.relvols.get(sym), Exception):
            raise self.relvols[sym]
        return {"volume_live": {"projected_relvol": self.relvols.get(sym)}}


class RacingTest(unittest.TestCase):
    def setUp(self):
        # reset the module cache between tests
        racing._CACHE["ts"], racing._CACHE["payload"] = 0.0, None

    def _patch(self, fake):
        """Patch the lazy `from . import scanner, prices` / live_gate targets."""
        import sepa.scanner as scanner
        import sepa.prices as prices
        import sepa.live_gate as live_gate
        self._saved = (scanner.load_latest, prices.bulk_live_prices,
                       live_gate.live_gate)
        scanner.load_latest = fake.load_latest
        prices.bulk_live_prices = fake.bulk_live_prices
        live_gate.live_gate = fake.live_gate
        self.addCleanup(self._unpatch)

    def _unpatch(self):
        import sepa.scanner as scanner
        import sepa.prices as prices
        import sepa.live_gate as live_gate
        scanner.load_latest, prices.bulk_live_prices, live_gate.live_gate = self._saved

    # ---- R-ladder math + leg boundaries ------------------------------------

    def test_r_ladder_math_pivot_100_stop_93(self):
        fake = FakeBackend([_setup_row("AAA", 100.0, 93.0)],
                           {"AAA": {"price": 101.0, "prev_day_close": 99.0}})
        self._patch(fake)
        rows = racing.get_board()["rows"]
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r["risk"], 7.0)
        self.assertEqual(r["r1"], 107.0)   # pivot + 1*risk
        self.assertEqual(r["r2"], 114.0)   # pivot + 2*risk

    def test_leg_boundaries(self):
        rows = [_setup_row(s, 100.0, 93.0) for s in
                ("JUSTUP", "ATR1", "ATR2", "ATPIVOT", "BELOW")]
        quotes = {
            "JUSTUP":  {"price": 100.01},   # just above pivot -> to_r1
            "ATR1":    {"price": 107.0},    # live == r1 -> to_r2
            "ATR2":    {"price": 114.0},    # live >= r2 -> excluded
            "ATPIVOT": {"price": 100.0},    # live <= pivot -> excluded
            "BELOW":   {"price": 95.0},     # below pivot -> excluded
        }
        fake = FakeBackend(rows, quotes)
        self._patch(fake)
        board = {r["symbol"]: r for r in racing.get_board()["rows"]}
        self.assertEqual(set(board), {"JUSTUP", "ATR1"})
        self.assertEqual(board["JUSTUP"]["leg"], "to_r1")
        self.assertEqual(board["ATR1"]["leg"], "to_r2")

    # ---- buy-range cap: inclusive at exactly +3.0%, out at 3.01 ------------

    def test_in_buy_range_inclusive_at_exactly_3_pct(self):
        rows = [_setup_row("IN", 100.0, 93.0), _setup_row("OUT", 100.0, 93.0)]
        quotes = {"IN": {"price": 103.0}, "OUT": {"price": 103.01}}
        fake = FakeBackend(rows, quotes)
        self._patch(fake)
        board = {r["symbol"]: r for r in racing.get_board()["rows"]}
        self.assertTrue(board["IN"]["in_buy_range"])     # +3.00% inclusive
        self.assertFalse(board["OUT"]["in_buy_range"])   # +3.01% out

    def test_progress_clamped_0_to_1(self):
        fake = FakeBackend([_setup_row("AAA", 100.0, 93.0)],
                           {"AAA": {"price": 113.99}})   # deep in to_r2 leg
        self._patch(fake)
        r = racing.get_board()["rows"][0]
        self.assertGreaterEqual(r["progress"], 0.0)
        self.assertLessEqual(r["progress"], 1.0)
        self.assertEqual(r["leg"], "to_r2")

    # ---- NaN / None safety --------------------------------------------------

    def test_day_pct_none_when_prev_close_missing(self):
        fake = FakeBackend([_setup_row("AAA", 100.0, 93.0)],
                           {"AAA": {"price": 102.0, "prev_day_close": None}})
        self._patch(fake)
        r = racing.get_board()["rows"][0]
        self.assertIsNone(r["day_pct"])

    def test_nan_quote_skips_row_not_crash(self):
        rows = [_setup_row("NANQ", 100.0, 93.0), _setup_row("GOOD", 100.0, 93.0)]
        quotes = {"NANQ": {"price": float("nan")}, "GOOD": {"price": 102.0}}
        fake = FakeBackend(rows, quotes)
        self._patch(fake)
        board = racing.get_board()["rows"]
        self.assertEqual([r["symbol"] for r in board], ["GOOD"])
        for r in board:                       # nothing non-finite leaks to JSON
            for v in r.values():
                if isinstance(v, float):
                    self.assertTrue(math.isfinite(v))

    def test_bad_setup_rows_filtered(self):
        rows = [
            _setup_row("NOQUAL", 100.0, 93.0, qualifier=False),  # not a qualifier
            _setup_row("INVSTOP", 100.0, 104.0),                 # stop >= pivot
            _setup_row("ZERO", 0.0, 0.0),                        # no levels
            {"symbol": "NOSETUP", "qualifier": True},            # no entry_setup
        ]
        fake = FakeBackend(rows, {s: {"price": 101.0} for s in
                                  ("NOQUAL", "INVSTOP", "ZERO", "NOSETUP")})
        self._patch(fake)
        self.assertEqual(racing.get_board()["rows"], [])

    def test_empty_scan_empty_board(self):
        fake = FakeBackend([], {})
        self._patch(fake)
        board = racing.get_board()
        self.assertEqual(board["rows"], [])
        self.assertIn("as_of", board)

    # ---- sort + relvol ------------------------------------------------------

    def test_sort_order_buyrange_then_leg_then_progress(self):
        rows = [_setup_row(s, 100.0, 93.0) for s in
                ("CHASE_R2", "BUYRANGE", "CHASE_R1_HI", "CHASE_R1_LO")]
        quotes = {
            "BUYRANGE":    {"price": 102.0},   # in buy range -> first
            "CHASE_R1_HI": {"price": 106.0},   # to_r1, progress 6/7
            "CHASE_R1_LO": {"price": 104.0},   # to_r1, progress 4/7
            "CHASE_R2":    {"price": 110.0},   # to_r2 -> last
        }
        fake = FakeBackend(rows, quotes)
        self._patch(fake)
        order = [r["symbol"] for r in racing.get_board()["rows"]]
        self.assertEqual(order, ["BUYRANGE", "CHASE_R1_HI", "CHASE_R1_LO", "CHASE_R2"])

    def test_relvol_populated_and_one_failure_does_not_kill_board(self):
        rows = [_setup_row("OK", 100.0, 93.0), _setup_row("BOOM", 100.0, 93.0)]
        quotes = {"OK": {"price": 101.0}, "BOOM": {"price": 102.0}}
        fake = FakeBackend(rows, quotes,
                           relvols={"OK": 2.3, "BOOM": RuntimeError("provider down")})
        self._patch(fake)
        board = {r["symbol"]: r for r in racing.get_board()["rows"]}
        self.assertEqual(board["OK"]["relvol"], 2.3)
        self.assertIsNone(board["BOOM"]["relvol"])   # failed quietly, row kept

    def test_max_rows_cap(self):
        rows = [_setup_row(f"S{i:02d}", 100.0, 93.0) for i in range(10)]
        quotes = {f"S{i:02d}": {"price": 101.0 + i * 0.1} for i in range(10)}
        fake = FakeBackend(rows, quotes)
        self._patch(fake)
        self.assertEqual(len(racing.get_board(max_rows=5)["rows"]), 5)

    # ---- cache TTL ----------------------------------------------------------

    def test_cache_ttl_second_call_skips_recompute(self):
        fake = FakeBackend([_setup_row("AAA", 100.0, 93.0)],
                           {"AAA": {"price": 101.0}})
        self._patch(fake)
        first = racing.get_board()
        self.assertEqual(fake.load_calls, 1)
        second = racing.get_board()
        self.assertIs(second, first)              # same object back
        self.assertEqual(fake.load_calls, 1)      # load_latest NOT re-called
        self.assertEqual(fake.bulk_calls, 1)
        # expire the cache -> recompute
        racing._CACHE["ts"] -= (racing.CACHE_TTL_S + 1)
        racing.get_board()
        self.assertEqual(fake.load_calls, 2)


if __name__ == "__main__":
    unittest.main()
