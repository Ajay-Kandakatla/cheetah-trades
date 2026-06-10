"""Behavioral tests for the giants 13F flow engine — synthetic filings only,
no network, no Mongo. Locks the dollar conventions stated in giants/flows.py:

  - delta_usd = delta_shares x period-end price of the LATER quarter
  - full exits valued at the PRIOR quarter's period-end price
  - price drift with zero share change is NOT a flow
  - option rows (putCall) never reach holdings
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from giants import registry
from giants.cusips import normalize_issuer, resolve
from giants.edgar import _parse_info_table
from giants.flows import _net_by_ticker, _shape_doc, fund_diff, quarter_label


def filing(period, holdings):
    return {"period": period,
            "holdings": [{"cusip": c, "name": n, "value": v, "shares": s}
                         for c, n, v, s in holdings]}


class TestFundDiff(unittest.TestCase):
    def test_add_valued_at_current_price(self):
        # 100 → 150 shares, now worth $300 total → price $2 → +50sh = +$100
        cur = filing("2026-03-31", [("C1", "ACME", 300, 150)])
        prev = filing("2025-12-31", [("C1", "ACME", 100, 100)])
        rows = fund_diff(cur, prev)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["action"], "add")
        self.assertEqual(rows[0]["delta_usd"], 100)
        self.assertEqual(rows[0]["pct_change_shares"], 50.0)

    def test_trim_is_negative(self):
        cur = filing("2026-03-31", [("C1", "ACME", 100, 50)])   # price $2
        prev = filing("2025-12-31", [("C1", "ACME", 100, 100)])
        rows = fund_diff(cur, prev)
        self.assertEqual(rows[0]["action"], "trim")
        self.assertEqual(rows[0]["delta_usd"], -100)  # -50sh x $2

    def test_new_position_is_full_current_value(self):
        cur = filing("2026-03-31", [("C1", "ACME", 500, 10)])
        prev = filing("2025-12-31", [])
        rows = fund_diff(cur, prev)
        self.assertEqual(rows[0]["action"], "new")
        self.assertEqual(rows[0]["delta_usd"], 500)
        self.assertIsNone(rows[0]["pct_change_shares"])

    def test_exit_valued_at_prior_price(self):
        cur = filing("2026-03-31", [])
        prev = filing("2025-12-31", [("C1", "ACME", 400, 100)])
        rows = fund_diff(cur, prev)
        self.assertEqual(rows[0]["action"], "exit")
        self.assertEqual(rows[0]["delta_usd"], -400)

    def test_price_drift_alone_is_not_a_flow(self):
        # Same 100 shares, value doubled — a market move, not a decision.
        cur = filing("2026-03-31", [("C1", "ACME", 200, 100)])
        prev = filing("2025-12-31", [("C1", "ACME", 100, 100)])
        self.assertEqual(fund_diff(cur, prev), [])

    def test_sorted_by_magnitude(self):
        cur = filing("2026-03-31", [("C1", "SMALL", 10, 10),
                                    ("C2", "BIG", 9000, 900)])
        prev = filing("2025-12-31", [("C1", "SMALL", 5, 5),
                                     ("C2", "BIG", 100, 10)])
        rows = fund_diff(cur, prev)
        self.assertEqual(rows[0]["name"], "BIG")


class TestNetByTicker(unittest.TestCase):
    def test_share_classes_net_to_one_row(self):
        # ADR +3.6B and ordinary shares -3.4B, both map to AZN → one +0.2B row
        cur = filing("2026-03-31", [("ADR000000", "ASTRAZENECA ADR", 3_600, 36),
                                    ("ORD000000", "ASTRAZENECA ORD", 100, 1)])
        prev = filing("2025-12-31", [("ORD000000", "ASTRAZENECA ORD", 3_500, 35)])
        rows = fund_diff(cur, prev)
        for r in rows:
            r["ticker"] = "AZN"
        net = _net_by_ticker(rows)
        self.assertEqual(len(net), 1)
        self.assertEqual(net[0]["delta_usd"], 3_600 - 3_400)

    def test_unmapped_rows_stay_separate_by_name(self):
        cur = filing("2026-03-31", [("C1", "BOND A", 200, 2),
                                    ("C2", "BOND B", 300, 3)])
        prev = filing("2025-12-31", [])
        rows = fund_diff(cur, prev)
        for r in rows:
            r["ticker"] = None
        self.assertEqual(len(_net_by_ticker(rows)), 2)


class TestInfoTableParse(unittest.TestCase):
    NS = "http://www.sec.gov/edgar/document/thirteenf/informationtable"

    def _xml(self, entries):
        rows = "".join(
            "<infoTable><nameOfIssuer>%s</nameOfIssuer><cusip>%s</cusip>"
            "<value>%d</value><shrsOrPrnAmt><sshPrnamt>%d</sshPrnamt>"
            "<sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>%s</infoTable>"
            % (n, c, v, s, ("<putCall>%s</putCall>" % pc) if pc else "")
            for n, c, v, s, pc in entries)
        return ('<informationTable xmlns="%s">%s</informationTable>'
                % (self.NS, rows))

    def test_basic_parse_and_option_exclusion(self):
        out = _parse_info_table(self._xml([
            ("MICRON TECHNOLOGY INC", "595112103", 1000, 10, ""),
            ("MICRON TECHNOLOGY INC", "595112103", 500, 5, ""),   # second manager row
            ("NVIDIA CORP", "67066G104", 9999, 1, "Call"),        # option → excluded
        ]))
        self.assertEqual(out["n_positions"], 1)
        self.assertEqual(out["n_option_rows_excluded"], 1)
        h = out["holdings"][0]
        self.assertEqual(h["cusip"], "595112103")
        self.assertEqual(h["value"], 1500)   # rows summed
        self.assertEqual(h["shares"], 15)
        self.assertEqual(out["total_value"], 1500)


class TestCusipResolve(unittest.TestCase):
    def test_normalize_peels_stacked_suffixes(self):
        self.assertEqual(normalize_issuer("Micron Technology, Inc."),
                         "MICRON TECHNOLOGY")
        self.assertEqual(normalize_issuer("TJX COS INC NEW"), "TJX COS")
        self.assertEqual(normalize_issuer("ALPHABET INC CL C"), "ALPHABET")

    def test_cusip_wins_over_name(self):
        cus = {"595112103": "MU"}
        names = {"MICRON TECHNOLOGY": "WRONG"}
        self.assertEqual(resolve("595112103", "MICRON TECHNOLOGY INC",
                                 cus, names), "MU")

    def test_name_fallback_then_none(self):
        names = {"MICRON TECHNOLOGY": "MU"}
        self.assertEqual(resolve("XXXXXXXXX", "MICRON TECHNOLOGY INC",
                                 {}, names), "MU")
        self.assertIsNone(resolve("XXXXXXXXX", "SOME OBSCURE BOND", {}, {}))


class TestAggregateShape(unittest.TestCase):
    def test_shape_doc_ranks_and_timelines(self):
        agg = {
            "Q4 2025": {"MU": {"ticker": "MU", "name": "MICRON", "net_usd": 50.0,
                               "buy_usd": 50.0, "sell_usd": 0.0, "n_buying": 1,
                               "n_selling": 0, "buyers": [], "sellers": []}},
            "Q1 2026": {
                "MU": {"ticker": "MU", "name": "MICRON", "net_usd": -200.0,
                       "buy_usd": 0.0, "sell_usd": 200.0, "n_buying": 0,
                       "n_selling": 2,
                       "buyers": [],
                       "sellers": [{"fund": "Capital World", "tier": "A",
                                    "style": "picker", "usd": -150.0,
                                    "action": "trim",
                                    "pct_change_shares": -27.8}]},
                "AVGO": {"ticker": "AVGO", "name": "BROADCOM", "net_usd": 300.0,
                         "buy_usd": 300.0, "sell_usd": 0.0, "n_buying": 2,
                         "n_selling": 0, "buyers": [], "sellers": []},
            },
        }
        doc = _shape_doc(agg, {}, [])
        self.assertEqual(doc["quarters"], ["Q4 2025", "Q1 2026"])  # oldest first
        self.assertEqual(doc["latest_quarter"], "Q1 2026")
        self.assertEqual([r["ticker"] for r in doc["rows_in"]], ["AVGO"])
        self.assertEqual([r["ticker"] for r in doc["rows_out"]], ["MU"])
        mu = doc["rows_out"][0]
        # timeline spans BOTH quarters, oldest first, zero-filled when absent
        self.assertEqual([t["net_usd"] for t in mu["timeline"]], [50, -200])
        avgo = doc["rows_in"][0]
        self.assertEqual([t["net_usd"] for t in avgo["timeline"]], [0, 300])
        # per-quarter top movers strip
        q1 = [b for b in doc["by_quarter"] if b["q"] == "Q1 2026"][0]
        self.assertEqual(q1["top_in"][0]["ticker"], "AVGO")
        self.assertEqual(q1["top_out"][0]["ticker"], "MU")

    def test_quarter_label(self):
        self.assertEqual(quarter_label("2026-03-31"), "Q1 2026")
        self.assertEqual(quarter_label("2025-12-31"), "Q4 2025")
        self.assertEqual(quarter_label("2025-06-30"), "Q2 2025")


class TestRegistry(unittest.TestCase):
    def test_ciks_unique_and_tiers_valid(self):
        funds = registry.all_funds()
        ciks = [f["cik"] for f in funds]
        self.assertEqual(len(ciks), len(set(ciks)), "duplicate CIK in registry")
        for f in funds:
            self.assertIn(f["tier"], ("S", "A"))
            self.assertIn(f["style"], ("picker", "quant", "activist"))
            self.assertTrue(f["short"])

    def test_no_index_giants(self):
        # The whole point: mandate-driven index flow stays out of the signal.
        names = " ".join(f["name"].lower() for f in registry.all_funds())
        for banned in ("vanguard", "blackrock", "state street", "geode"):
            self.assertNotIn(banned, names)


if __name__ == "__main__":
    unittest.main()
