"""Giants 13F hygiene fixes, 2026-10-06 (docs/giants_13f_dedupe_units_2026_10_06.md).

Synthetic filings only — no network, no Mongo (a fake collection stands in).
Four defects, each pinned with the case that broke live and the negatives:

  1. one canonical portfolio per (cik, period): RESTATEMENT replaces, NEW
     HOLDINGS merges, unknown / orphan amendments never become a portfolio
  2. VALUE reported in thousands (T. Rowe) is detected and scaled; dollar,
     thin and ambiguous filings are never scaled
  3. quarter P = the dominant latest period; stale funds are named, not mixed
  4. FTD retired-CUSIP placeholders (HONZZZZ) never reach a board as a ticker
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from giants import cusips, edgar, flows  # noqa: E402

Q2, Q1, Q4, Q3 = "2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30"


def doc(cik, period, holdings, form="13F-HR", filed=None, atype=None,
        acc=None):
    hs = [{"cusip": c, "name": n, "value": v, "shares": s}
          for c, n, v, s in holdings]
    d = {"_id": "%s:%s" % (cik, acc or (period + form)), "cik": cik,
         "period": period, "form": form, "filed": filed or period,
         "accession": acc or (period + form), "holdings": hs,
         "n_positions": len(hs), "n_option_rows_excluded": 0,
         "total_value": sum(h["value"] for h in hs)}
    if form.endswith("/A") and atype is not None:
        d["amendment_type"] = atype
    return d


class FakeColl:
    def __init__(self, docs):
        self.docs = list(docs)
        self.updates = []

    def find(self, q):
        return [d for d in self.docs if d["cik"] == q.get("cik")]

    def find_one(self, q, *a, **k):
        for d in self.docs:
            if d["_id"] == q.get("_id"):
                return dict(d)
        return None

    def update_one(self, q, u):
        self.updates.append((q, u))

    def replace_one(self, *a, **k):
        pass

    def create_index(self, *a, **k):
        pass


# --- 1. canonical filing per period -----------------------------------------

class TestCanonicalFiling(unittest.TestCase):
    def test_restatement_replaces_original(self):
        orig = doc(1, Q2, [("A", "AAA", 100, 10), ("B", "BBB", 50, 5)],
                   filed="2026-08-14")
        rest = doc(1, Q2, [("A", "AAA", 100, 10)], form="13F-HR/A",
                   filed="2026-09-02", atype=edgar.AMEND_RESTATEMENT)
        out = edgar.canonical_filings([orig, rest])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["form"], "13F-HR/A")
        self.assertEqual([h["cusip"] for h in out[0]["holdings"]], ["A"])

    def test_citadel_cache_never_diffs_q2_against_q2(self):
        # NEGATIVE: the live defect — orig + restatement for Q2, then Q1.
        docs = [doc(1423053, Q2, [("V", "VISTRA", 794_630 * 160, 794_630)],
                    filed="2026-08-14"),
                doc(1423053, Q2, [("V", "VISTRA", 794_630 * 160, 794_630)],
                    form="13F-HR/A", filed="2026-09-02",
                    atype=edgar.AMEND_RESTATEMENT, acc="rest"),
                doc(1423053, Q1, [("V", "VISTRA", 1_610_000 * 160, 1_610_000)])]
        with mock.patch.object(edgar, "_coll", return_value=FakeColl(docs)):
            got = edgar.cached_filings(1423053)
            raw = edgar.cached_filings(1423053, raw=True)
        self.assertEqual([d["period"] for d in got], [Q2, Q1])
        self.assertEqual(len(raw), 3)  # raw=True still shows what is stored
        rows = flows.fund_diff(got[0], got[1])
        self.assertEqual(len(rows), 1)
        self.assertLess(rows[0]["delta_shares"], 0)

    def test_new_holdings_amendment_is_merged_not_the_whole_book(self):
        orig = doc(1998597, Q1, [("C%d" % i, "N%d" % i, 1000, 10)
                                 for i in range(10)], filed="2026-05-15")
        extra = doc(1998597, Q1, [("X", "XTRA", 61_537_156, 100)],
                    form="13F-HR/A", filed="2026-06-30",
                    atype=edgar.AMEND_NEW_HOLDINGS, acc="nh")
        c = edgar.canonical_filings([extra, orig])[0]
        self.assertEqual(c["n_positions"], 11)
        self.assertEqual(c["total_value"], 10 * 1000 + 61_537_156)
        self.assertEqual(c["amendments_applied"], ["nh"])
        # NEGATIVE: diffing Q2 (same 10 names) against it must not show the
        # 10 original positions as exits/new.
        q2 = doc(1998597, Q2, [("C%d" % i, "N%d" % i, 1000, 10)
                               for i in range(10)] + [("X", "XTRA", 1, 100)])
        self.assertEqual(flows.fund_diff(q2, c), [])

    def test_new_holdings_same_cusip_sums(self):
        orig = doc(1, Q1, [("A", "AAA", 100, 10)])
        extra = doc(1, Q1, [("A", "AAA", 50, 5)], form="13F-HR/A",
                    filed="2026-06-30", atype=edgar.AMEND_NEW_HOLDINGS)
        h = edgar.canonical_filings([orig, extra])[0]["holdings"]
        self.assertEqual((h[0]["value"], h[0]["shares"]), (150, 15))

    def test_orphan_new_holdings_amendment_is_no_portfolio(self):
        # NEGATIVE: Berkshire's Q1-2025 cache held ONLY its 4-position /A.
        extra = doc(1, Q1, [("X", "XTRA", 10, 1)], form="13F-HR/A",
                    atype=edgar.AMEND_NEW_HOLDINGS)
        self.assertIsNone(edgar.canonical_period([extra]))
        self.assertEqual(edgar.canonical_filings([extra]), [])

    def test_unknown_amendment_type_keeps_original(self):
        # NEGATIVE: an /A whose cover page was never read neither replaces
        # nor merges into the complete original.
        orig = doc(1, Q2, [("A", "AAA", 100, 10)], filed="2026-08-14")
        unk = doc(1, Q2, [("Z", "ZZZ", 5, 1)], form="13F-HR/A",
                  filed="2026-09-02", acc="unk")
        c = edgar.canonical_filings([orig, unk])[0]
        self.assertEqual([h["cusip"] for h in c["holdings"]], ["A"])
        self.assertEqual(c["amendments_unresolved"], ["unk"])
        self.assertEqual(c["form"], "13F-HR")
        # ...and alone it is not a portfolio
        self.assertIsNone(edgar.canonical_period([unk]))

    def test_parse_cover(self):
        ns = '<edgarSubmission xmlns="http://www.sec.gov/edgar/thirteenffiler">'
        self.assertEqual(edgar._parse_cover(
            ns + "<coverPage><isAmendment>true</isAmendment><amendmentInfo>"
            "<amendmentType>RESTATEMENT</amendmentType></amendmentInfo>"),
            edgar.AMEND_RESTATEMENT)
        self.assertEqual(edgar._parse_cover(
            "<ns1:amendmentType> NEW HOLDINGS </ns1:amendmentType>"),
            edgar.AMEND_NEW_HOLDINGS)
        self.assertIsNone(edgar._parse_cover(ns + "<isAmendment>false</isAmendment>"))
        self.assertIsNone(edgar._parse_cover("<amendmentType>OTHER</amendmentType>"))
        self.assertIsNone(edgar._parse_cover(""))

    def test_filing_index_keeps_every_filing_and_newer_notices(self):
        sub = {"filings": {"recent": {
            "form": ["13F-NT", "13F-HR/A", "13F-HR", "13F-HR", "13F-NT", "4"],
            "filingDate": ["2026-08-14", "2026-06-30", "2026-05-15",
                           "2026-02-17", "2025-11-14", "2026-01-01"],
            "accessionNumber": ["nt", "a1", "o1", "o4", "ntold", "x"],
            "reportDate": [Q2, Q1, Q1, Q4, Q3, Q4],
        }}}
        resp = mock.Mock()
        resp.json.return_value = sub
        with mock.patch.object(edgar, "_get", return_value=resp):
            idx = edgar.filing_index(1, max_n=6)
        # BOTH the original and its amendment survive (old code kept only
        # the last-filed one per period)
        self.assertEqual([f["accession"] for f in idx["filings"]],
                         ["o1", "a1", "o4"])
        # only the notice NEWER than the last holdings filing is reported
        self.assertEqual(idx["notice_periods"], [Q2])

    def test_cached_amendment_without_type_is_backfilled(self):
        cached = doc(1, Q2, [("A", "AAA", 1, 1)], form="13F-HR/A", acc="a1")
        coll = FakeColl([cached])
        with mock.patch.object(edgar, "_coll", return_value=coll), \
                mock.patch.object(edgar, "_fetch_amendment_type",
                                  return_value=edgar.AMEND_RESTATEMENT) as f:
            got = edgar.fetch_holdings(1, {"accession": "a1", "period": Q2,
                                           "filed": Q2, "form": "13F-HR/A"})
        self.assertEqual(got["amendment_type"], edgar.AMEND_RESTATEMENT)
        f.assert_called_once()
        self.assertEqual(coll.updates[0][1],
                         {"$set": {"amendment_type": edgar.AMEND_RESTATEMENT}})

    def test_cached_original_never_reads_cover(self):
        # NEGATIVE: originals need no cover-page fetch.
        coll = FakeColl([doc(1, Q2, [("A", "AAA", 1, 1)], acc="o1")])
        with mock.patch.object(edgar, "_coll", return_value=coll), \
                mock.patch.object(edgar, "_fetch_amendment_type") as f:
            edgar.fetch_holdings(1, {"accession": "o1", "period": Q2,
                                     "filed": Q2, "form": "13F-HR"})
        f.assert_not_called()
        self.assertEqual(coll.updates, [])

    def test_network_path_canonicalizes(self):
        idx = {"filings": [{"accession": "o", "period": Q1, "filed": "a",
                            "form": "13F-HR"},
                           {"accession": "nh", "period": Q1, "filed": "b",
                            "form": "13F-HR/A"}],
               "notice_periods": [Q2]}
        docs = {"o": doc(1, Q1, [("A", "AAA", 10, 1)], acc="o"),
                "nh": doc(1, Q1, [("B", "BBB", 20, 2)], form="13F-HR/A",
                          atype=edgar.AMEND_NEW_HOLDINGS, acc="nh")}
        with mock.patch.object(edgar, "filing_index", return_value=idx), \
                mock.patch.object(edgar, "fetch_holdings",
                                  side_effect=lambda c, f: docs[f["accession"]]):
            out, notice = flows._fund_filings(1, 5, network=True)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["n_positions"], 2)
        self.assertEqual(notice, [Q2])


# --- 2. VALUE units ------------------------------------------------------------

FILLER = [("F%02d" % i, "FILL%d" % i, 10.0 + i) for i in range(12)]


def priced(cik, period, extra=(), scale=1.0, n=len(FILLER)):
    rows = [(c, nm, int(px * 1000 * scale), 1000) for c, nm, px in FILLER[:n]]
    return doc(cik, period, rows + list(extra))


class TestValueUnits(unittest.TestCase):
    def test_thousands_filer_detected_and_scaled(self):
        trow = priced(80255, Q2, scale=0.001)
        out = flows.normalize_value_units(
            [priced(1, Q2), priced(2, Q2), priced(3, Q2), trow])
        t = out[-1]
        self.assertEqual(t["value_units"], flows.UNITS_THOUSANDS)
        self.assertEqual(t["holdings"][0]["value"], trow["holdings"][0]["value"] * 1000)
        self.assertEqual(t["total_value"], trow["total_value"] * 1000)
        # NEGATIVE: the input doc (the cache's) is not mutated
        self.assertEqual(trow["holdings"][0]["value"], 10)

    def test_trow_vst_add_clears_rotation_floor_after_scaling(self):
        # 2,643,274 → 2,851,055 sh at ~$158.6: filed in thousands it read ~$33k
        vst = lambda sh: ("VST", "VISTRA", int(sh * 158.6 / 1000), sh)  # noqa: E731
        cur = priced(80255, Q2, [vst(2_851_055)], scale=0.001)
        prev = priced(80255, Q1, [vst(2_643_274)], scale=0.001)
        raw_move = flows.fund_diff(cur, prev)[0]["delta_usd"]
        self.assertLess(abs(raw_move), flows._MIN_ROTATION_MOVE_USD)
        c = flows.normalize_value_units([priced(1, Q2), priced(2, Q2), cur])[-1]
        p = flows.normalize_value_units([priced(1, Q1), priced(2, Q1), prev])[-1]
        move = [r for r in flows.fund_diff(c, p) if r["cusip"] == "VST"][0]
        self.assertGreaterEqual(move["delta_usd"], flows._MIN_ROTATION_MOVE_USD)
        self.assertAlmostEqual(move["delta_usd"] / 33e6, 1, delta=0.02)

    def test_dollar_filer_untouched(self):
        # NEGATIVE
        d = priced(1, Q2)
        out = flows.normalize_value_units([d, priced(2, Q2), priced(80255, Q2, scale=0.001)])
        self.assertEqual(out[0]["value_units"], flows.UNITS_DOLLARS)
        self.assertEqual(out[0]["holdings"], d["holdings"])
        self.assertEqual(out[1]["value_units"], flows.UNITS_DOLLARS)

    def test_too_few_shared_positions_is_undetermined_and_unscaled(self):
        # NEGATIVE: never guess — Trian-like 7-position book
        thin = priced(9, Q2, n=7, scale=0.001)
        out = flows.normalize_value_units([priced(1, Q2), priced(2, Q2), thin])
        self.assertEqual(out[-1]["value_units"], flows.UNITS_UNDETERMINED)
        self.assertEqual(out[-1]["holdings"], thin["holdings"])

    def test_ambiguous_ratio_is_undetermined_and_unscaled(self):
        # NEGATIVE: 1/30 is neither dollars nor thousands
        odd = priced(9, Q2, scale=1 / 30)
        out = flows.normalize_value_units([priced(1, Q2), priced(2, Q2), odd])
        self.assertEqual(out[-1]["value_units"], flows.UNITS_UNDETERMINED)
        self.assertEqual(out[-1]["total_value"], odd["total_value"])

    def test_bond_book_compares_same_cusip_not_share_price(self):
        # PRN rows: value / principal ≈ 1. A dollar bond book must not read
        # as thousands, a thousands bond book must.
        bonds = [("B%02d" % i, "BOND%d" % i) for i in range(12)]
        mk = lambda cik, scale: doc(cik, Q2, [  # noqa: E731
            (c, n, int(1_000_000 * 0.98 * scale), 1_000_000) for c, n in bonds])
        out = flows.normalize_value_units([mk(1, 1), mk(2, 1), mk(3, 0.001)])
        self.assertEqual([d["value_units"] for d in out],
                         [flows.UNITS_DOLLARS, flows.UNITS_DOLLARS,
                          flows.UNITS_THOUSANDS])

    def test_alone_in_a_period_is_undetermined(self):
        # NEGATIVE: Greenlight's 2023 filings have no peers in the cache
        out = flows.normalize_value_units([priced(1079114, "2023-12-31")])
        self.assertEqual(out[0]["value_units"], flows.UNITS_UNDETERMINED)


# --- 3. dominant quarter + stale funds ------------------------------------------

FUNDS = [
    {"cik": 1, "name": "Fund One", "short": "One", "tier": "S", "style": "picker"},
    {"cik": 1423053, "name": "Citadel", "short": "Citadel", "tier": "S", "style": "quant"},
    {"cik": 80255, "name": "T Rowe", "short": "T. Rowe Price", "tier": "A", "style": "picker"},
    {"cik": 1079114, "name": "Greenlight", "short": "Greenlight", "tier": "S", "style": "picker"},
    {"cik": 1336528, "name": "Pershing", "short": "Pershing Sq", "tier": "S", "style": "activist"},
    {"cik": 7, "name": "Gappy", "short": "Gappy", "tier": "A", "style": "picker"},
]


def vst(sh, px=160.0, scale=1.0):
    return ("VST", "VISTRA", int(sh * px * scale), sh)


def world():
    """The live shapes, in miniature."""
    return [
        priced(1, Q2, [vst(1000)]), priced(1, Q1, [vst(500)]),
        # Citadel: original + RESTATEMENT for Q2, cut VST -50.7%
        priced(1423053, Q2, [vst(391_939)]),
        dict(priced(1423053, Q2, [vst(391_939)]), form="13F-HR/A",
             _id="1423053:rest", accession="rest", filed="2026-09-02",
             amendment_type=edgar.AMEND_RESTATEMENT),
        priced(1423053, Q1, [vst(794_630)]),
        # T. Rowe in thousands, +7.9%
        priced(80255, Q2, [vst(2_851_055, scale=0.001)], scale=0.001),
        priced(80255, Q1, [vst(2_643_274, scale=0.001)], scale=0.001),
        # Greenlight: last filed 2023, sold all its VST then
        doc(1079114, "2023-12-31", []),
        doc(1079114, "2023-09-30", [vst(9_000_000, px=10)]),
        # Pershing: latest is Q1 (13F-NT for Q2)
        priced(1336528, Q1, [vst(100)]), priced(1336528, Q4, [vst(900_000)]),
        # Gappy: Q2 and Q4 but no Q1 — a gap is not one quarter's move
        priced(7, Q2, [vst(10)]), priced(7, Q4, [vst(5_000_000)]),
    ]


class TestDominantQuarter(unittest.TestCase):
    def test_mode_wins_and_ties_go_newer(self):
        self.assertEqual(flows.dominant_period([Q2, Q2, Q1, "2023-12-31"]), Q2)
        self.assertEqual(flows.dominant_period([Q2, Q1]), Q2)
        self.assertIsNone(flows.dominant_period([]))

    def test_lone_early_filer_and_old_filer_never_set_the_quarter(self):
        # NEGATIVE: one fund on Q3, one on 2023 — the board stays on Q2
        self.assertEqual(flows.dominant_period(
            ["2026-09-30", Q2, Q2, Q2, "2023-12-31"]), Q2)
        # and Q4 2023 never outranks Q2 2026 as a STRING ('Q4 …' > 'Q2 …')
        self.assertEqual(flows.dominant_period(["2023-12-31", Q2]), Q2)


class _Patched(unittest.TestCase):
    def setUp(self):
        coll = FakeColl(world())
        maps = ({"VST": "VST"}, {})
        self._p = [mock.patch.object(edgar, "_coll", return_value=coll),
                   mock.patch.object(flows, "_coll", return_value=None),
                   mock.patch.object(flows.cusips, "get_maps", return_value=maps),
                   mock.patch.object(flows.registry, "all_funds",
                                     return_value=[dict(f) for f in FUNDS])]
        for p in self._p:
            p.start()

    def tearDown(self):
        for p in self._p:
            p.stop()


class TestSymbolRotation(_Patched):
    def test_vst_rotation_live_shape(self):
        r = flows.symbol_rotation("vst")
        self.assertEqual(r["quarter"], "Q2 2026")
        sellers = {e["fund"]: e for e in r["sellers"]}
        buyers = {e["fund"]: e for e in r["buyers"]}
        # Citadel's cut is present (not erased by a Q2-vs-Q2 diff)
        self.assertIn("Citadel", sellers)
        self.assertEqual(sellers["Citadel"]["pct_change_shares"], -50.7)
        # T. Rowe's add is present, valued in dollars
        self.assertIn("T. Rowe Price", buyers)
        self.assertEqual(buyers["T. Rowe Price"]["value_units"], "thousands")
        self.assertGreater(buyers["T. Rowe Price"]["delta_usd"], 30_000_000)
        # NEGATIVE: Fund One's +500 sh ($80k) stays under the unchanged floor
        self.assertNotIn("One", buyers)

    def test_stale_funds_named_not_mixed_in(self):
        r = flows.symbol_rotation("VST")
        movers = {e["fund"] for e in r["sellers"] + r["buyers"]}
        # NEGATIVE: Greenlight's 2023 sale, Pershing's Q1 cut and Gappy's
        # Q4→Q2 gap are not this quarter's moves
        for f in ("Greenlight", "Pershing Sq", "Gappy"):
            self.assertNotIn(f, movers)
        stale = {s["fund"]: s for s in r["stale_funds"]}
        self.assertEqual(set(stale), {"Greenlight", "Pershing Sq", "Gappy"})
        self.assertEqual(stale["Greenlight"]["latest_quarter"], "Q4 2023")
        self.assertIn("not filed for Q2 2026", stale["Greenlight"]["reason"])
        self.assertIn("no Q1 2026 filing", stale["Gappy"]["reason"])
        self.assertEqual(r["n_funds_current"], 3)
        for e in r["sellers"] + r["buyers"]:
            self.assertEqual(e["quarter"], "Q2 2026")

    def test_notice_reason(self):
        with mock.patch.object(flows, "_notice_periods_by_cik",
                               return_value={1336528: [Q2]}):
            r = flows.symbol_rotation("VST")
        s = [x for x in r["stale_funds"] if x["fund"] == "Pershing Sq"][0]
        self.assertIn("13F-NT", s["reason"])


class TestRebuildCacheOnly(_Patched):
    def test_rebuild_quarter_window_and_stale(self):
        d = flows.rebuild(network=False)
        self.assertEqual(d["latest_quarter"], "Q2 2026")
        # NEGATIVE: no 2023 buckets, no gap-diff bucket
        self.assertNotIn("Q4 2023", d["quarters"])
        self.assertNotIn("Q3 2023", d["quarters"])
        self.assertEqual({s["fund"] for s in d["stale_funds"]},
                         {"Greenlight", "Pershing Sq", "Gappy"})
        self.assertEqual(d["n_funds_current"], 3)
        vst_row = [r for r in d["rows_in"] + d["rows_out"] if r["ticker"] == "VST"][0]
        sellers = {s["fund"] for s in vst_row["sellers"]}
        buyers = {s["fund"] for s in vst_row["buyers"]}
        self.assertIn("Citadel", sellers)
        self.assertIn("T. Rowe Price", buyers)
        self.assertNotIn("Gappy", sellers | buyers)
        self.assertNotIn("Greenlight", sellers | buyers)
        # n_selling still counted per ticker; top-rows cap untouched
        self.assertEqual(vst_row["n_selling"], 1)
        self.assertEqual(flows._TOP_ROWS, 40)
        # Pershing's Q1 move still counts for Q1 (it filed Q1 and Q4)
        q1 = [b for b in d["by_quarter"] if b["q"] == "Q1 2026"][0]
        self.assertTrue(q1["top_out"] or q1["top_in"])
        fr = {f["fund"]: f for f in d["funds"]}
        self.assertFalse(fr["Greenlight"]["current"])
        self.assertEqual(fr["Greenlight"]["top_adds"] + fr["Greenlight"]["top_trims"], [])
        self.assertTrue(fr["Citadel"]["current"])


# --- 4. FTD retired-CUSIP placeholders ---------------------------------------------

class TestRetiredCusipSymbol(unittest.TestCase):
    CUS = {"438516106": "HONZZZZ", "438516205": "HON",
           "265342105": "ORPHZZZZ"}

    def test_placeholder_maps_to_live_base(self):
        self.assertEqual(cusips.resolve("438516106", "HONEYWELL INTL INC",
                                        self.CUS, {}), "HON")

    def test_placeholder_without_live_base_is_never_a_ticker(self):
        # NEGATIVE
        self.assertIsNone(cusips.resolve("265342105", "ORPHAN CO", self.CUS, {}))
        # ...but the issuer-name fallback still applies
        self.assertEqual(cusips.resolve("265342105", "ORPHAN CO", self.CUS,
                                        {"ORPHAN": "ORPH"}), "ORPH")

    def test_ordinary_symbols_untouched(self):
        # NEGATIVE
        cus = dict(self.CUS, **{"595112103": "MU", "X1": "BACPRB"})
        self.assertEqual(cusips.resolve("595112103", "", cus, {}), "MU")
        self.assertEqual(cusips.resolve("X1", "", cus, {}), "BACPRB")

    def test_old_and_new_honeywell_lines_net_to_one_row(self):
        cur = doc(1, Q2, [("438516205", "HONEYWELL INTL INC", 1_308_875_964, 5_845_806)])
        prev = doc(1, Q1, [("438516106", "HONEYWELL INTL INC", 3_760_080_475, 16_635_316)])
        raw = flows.fund_diff(cur, prev)
        flows._attach_tickers(raw, self.CUS, {})
        rows = flows._net_by_ticker(raw)
        self.assertEqual([r["ticker"] for r in rows], ["HON"])
        self.assertNotIn("HONZZZZ", [r["ticker"] for r in raw])


if __name__ == "__main__":
    unittest.main()
