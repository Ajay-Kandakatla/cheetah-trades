"""🚀 Explosive Growth — the "just reported" read (Ajay 2026-09-17).

A CALENDAR FACT, pinned as one. The suite exists to hold four lines that are
easy to cross:

  * the window is the repo's own `sepa.earnings_picks.REPORT_WINDOW_DAYS`,
    never a number anyone here picked;
  * `last_report: None` is UNKNOWN, never "did not report" — 16 of the 21 live
    rows are in that state (measured 2026-09-18);
  * a `next_date` in the PAST is a stale estimate, never a report, even though
    `chart_maps.earnings.phase_for` calls that bar REACTED;
  * the read never adds, drops, reorders or re-keys a row, and sends nothing.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from growth import earnings_fresh as EF
from growth import api as GA
from sepa import earnings_picks as EP
from chart_maps.earnings import REACTED, phase_for

TODAY = "2026-09-18"

# CRDO's real live calendar doc, read out of the container 2026-09-18.
CRDO = {"_id": "CRDO", "next_date": None, "when": None, "eps_estimate": None,
        "last_report": {"date": "2026-09-01", "when": "AMC", "eps_actual": 0.41,
                        "eps_estimate": 0.386, "surprise_pct": 6.1}}
# The all-None fingerprint 16 of the 21 board rows carry (NVDA / MU / TER / …).
BLANK = {"_id": "NVDA", "next_date": None, "when": None,
         "eps_estimate": None, "last_report": None}
# IPI: a forward estimate and nothing else. The C4 trap.
IPI = {"_id": "IPI", "next_date": "2026-11-04", "when": None,
       "eps_estimate": None, "last_report": None}


class FakeColl:
    def __init__(self, docs):
        self.docs = list(docs)
        self.queries = []

    def find(self, q=None, *a, **k):
        self.queries.append(q)
        ids = ((q or {}).get("_id") or {}).get("$in")
        for d in self.docs:
            if ids is not None and d.get("_id") not in ids:
                continue
            yield dict(d)


class DeadColl:
    def find(self, *a, **k):
        raise RuntimeError("mongo is down")


def _src():
    import inspect
    return inspect.getsource(EF)


# --------------------------------------------------------------- the window

class WindowTest(unittest.TestCase):
    def test_window_is_the_repo_constant_never_a_local_number(self):
        self.assertIs(EF.WINDOW_DAYS, EP.REPORT_WINDOW_DAYS)
        self.assertIs(EF.read_one(CRDO, TODAY)["window_days"],
                      EP.REPORT_WINDOW_DAYS)
        import re
        for line in _src().splitlines():
            if line.lstrip().startswith(("#", "*")):
                continue
            self.assertIsNone(
                re.match(r"\s*\w*(WINDOW|DAYS)\w*\s*=\s*\d", line),
                "earnings_fresh defines its own window number: %r" % line)


# ------------------------------------------------------------- read_one core

class ReadOneTest(unittest.TestCase):
    def test_bmo_report_today_is_fresh(self):
        cal = {"next_date": TODAY, "when": "BMO", "last_report": None}
        r = EF.read_one(cal, TODAY)
        self.assertTrue(r["known"] and r["fresh"])
        self.assertEqual(r["days_ago"], 0)
        self.assertEqual(r["reported_on"], TODAY)
        self.assertEqual(phase_for(cal, TODAY, TODAY), REACTED)

    def test_amc_report_today_is_NOT_fresh_yet(self):
        """NEGATIVE — the numbers are not out until the close."""
        cal = {"next_date": TODAY, "when": "AMC", "last_report": None}
        r = EF.read_one(cal, TODAY)
        self.assertFalse(r["known"])
        self.assertFalse(r["fresh"])
        self.assertIsNone(r["reported_on"])

    def test_a_past_next_date_is_a_stale_estimate_not_a_report(self):
        """NEGATIVE — THE C4 PIN. IPI's real shape, read the day after its
        estimate ages. phase_for says REACTED; this module must not."""
        r = EF.read_one(IPI, "2026-11-05")
        self.assertIs(r["known"], False)
        self.assertIsNone(r["reported_on"])
        self.assertIs(r["fresh"], False)
        self.assertEqual(
            phase_for({"next_date": "2026-11-04", "when": None},
                      "2026-11-05", "2026-11-05"), REACTED)

    def test_a_friday_amc_reporter_is_visible_on_monday(self):
        """NEGATIVE — THE C3 PIN. The most common slot. At a 2-day window it
        would be invisible on every market day, which is why 2 is not shipped."""
        fri = {"next_date": "2026-09-18", "when": "AMC", "last_report": None}
        self.assertFalse(EF.read_one(fri, "2026-09-18")["fresh"])
        mon = {"next_date": None, "when": None,
               "last_report": {"date": "2026-09-18", "when": "AMC"}}
        r = EF.read_one(mon, "2026-09-21")
        self.assertEqual(r["days_ago"], 3)
        self.assertIs(r["fresh"], True)
        self.assertGreater(r["days_ago"], 2)          # invisible at LOOKBACK_DAYS=2
        from chart_maps import earnings as CME
        self.assertEqual(CME.LOOKBACK_DAYS, 2)

    def test_report_at_the_window_edge_is_fresh(self):
        from datetime import date, timedelta
        d = (date.fromisoformat(TODAY) - timedelta(days=EF.WINDOW_DAYS)).isoformat()
        r = EF.read_one({"last_report": {"date": d, "when": "BMO"}}, TODAY)
        self.assertEqual(r["days_ago"], EF.WINDOW_DAYS)
        self.assertTrue(r["fresh"])

    def test_report_one_day_past_the_window_is_NOT_fresh(self):
        """NEGATIVE."""
        from datetime import date, timedelta
        d = (date.fromisoformat(TODAY)
             - timedelta(days=EF.WINDOW_DAYS + 1)).isoformat()
        r = EF.read_one({"last_report": {"date": d}}, TODAY)
        self.assertIs(r["known"], True)
        self.assertIs(r["fresh"], False)

    def test_stale_2026_09_01_report_is_not_fresh(self):
        """NEGATIVE — CRDO on the day this shipped: 17 days, known, not fresh."""
        r = EF.read_one(CRDO, TODAY)
        self.assertIs(r["known"], True)
        self.assertIs(r["fresh"], False)
        self.assertEqual(r["days_ago"], 17)
        self.assertEqual(r["when"], "AMC")
        self.assertEqual(r["surprise_pct"], 6.1)

    def test_no_calendar_doc_is_unknown_not_stale_and_does_not_crash(self):
        """NEGATIVE."""
        r = EF.read_one(None, TODAY)
        self.assertIs(r["known"], False)
        self.assertIs(r["fresh"], False)
        self.assertIsNone(r["reported_on"])

    def test_last_report_None_reads_UNKNOWN_not_did_not_report(self):
        """NEGATIVE — the live NVDA / MU / TER shape. Risk 3."""
        r = EF.read_one(BLANK, TODAY)
        self.assertIs(r["known"], False)
        self.assertIsNone(r["reported_on"])
        self.assertIs(r["fresh"], False)

    def test_garbage_calendar_shapes_never_raise(self):
        """NEGATIVE."""
        for cal in ("CRDO", ["CRDO"], 7, {"last_report": "2026-09-16"},
                    {"next_date": 12345}, {"last_report": {"date": "not-a-date"}},
                    {"last_report": {"date": None}}, {},
                    {"next_date": None, "when": "BMO"}):
            r = EF.read_one(cal, TODAY)
            self.assertIs(r["known"], False, cal)
            self.assertIs(r["fresh"], False, cal)
        self.assertIs(EF.read_one(CRDO, None)["known"], False)
        self.assertIs(EF.read_one(CRDO, "garbage")["known"], False)

    def test_future_report_date_is_never_fresh(self):
        """NEGATIVE — clock skew."""
        r = EF.read_one({"last_report": {"date": "2026-09-30"}}, TODAY)
        self.assertIs(r["fresh"], False)

    def test_surprise_only_rides_a_last_report_date(self):
        r = EF.read_one({"next_date": TODAY, "when": "BMO",
                         "last_report": None}, TODAY)
        self.assertEqual(r["reported_on"], TODAY)
        self.assertIsNone(r["surprise_pct"])


# ----------------------------------------------------------------- attach

def _rows():
    return [{"symbol": "PTGX", "sales_growth_pct": 900.0, "warnings": ["⛔ x"],
             "zone": {"intact": True}},
            {"symbol": "CRDO", "sales_growth_pct": 300.0, "warnings": []},
            {"symbol": "NVDA", "sales_growth_pct": 100.0, "warnings": []}]


class AttachTest(unittest.TestCase):
    def test_attach_never_reorders_adds_or_drops_a_row(self):
        """NEGATIVE — the screen's own ordering key is (-sales_growth_pct, symbol)."""
        rows = _rows()
        before = [r["symbol"] for r in rows]
        EF.attach(rows, db=FakeColl([CRDO, BLANK]), today=TODAY)
        after = [r["symbol"] for r in rows]
        self.assertEqual(before, after)
        self.assertEqual(len(rows), 3)
        self.assertEqual(
            after, [r["symbol"] for r in
                    sorted(rows, key=lambda r: (-r["sales_growth_pct"], r["symbol"]))])

    def test_attach_does_not_touch_warnings_zone_or_any_other_row_key(self):
        """NEGATIVE."""
        import copy
        rows = _rows()
        snap = copy.deepcopy(rows)
        EF.attach(rows, db=FakeColl([CRDO, BLANK]), today=TODAY)
        for r, s in zip(rows, snap):
            self.assertEqual({k: v for k, v in r.items() if k != "earnings_fresh"}, s)

    def test_attach_survives_a_dead_mongo(self):
        """NEGATIVE."""
        rows = _rows()
        out = EF.attach(rows, db=DeadColl(), today=TODAY)
        self.assertEqual(out["n"], 3)
        self.assertEqual(out["n_unknown"], 3)
        for r in rows:
            self.assertIs(r["earnings_fresh"]["known"], False)

    def test_attach_joins_on_the_id_field_not_a_symbol_field(self):
        """Risk 2 pinned: `_id` IS the symbol in earnings_calendar."""
        wrong = FakeColl([{"symbol": "CRDO", **{k: v for k, v in CRDO.items()
                                                if k != "_id"}}])
        rows = _rows()
        out = EF.attach(rows, db=wrong, today=TODAY)
        self.assertEqual(out["n_known"], 0)
        self.assertEqual(wrong.queries[0], {"_id": {"$in": ["PTGX", "CRDO", "NVDA"]}})

    def test_summary_counts_and_most_recent(self):
        """The live board, 2026-09-18: 21 rows, 0 fresh, 5 known, 16 unknown,
        most recent CRDO 2026-09-01."""
        known = ["CRDO", "ALAB", "BE", "ARR", "FF"]
        blanks = ["PTGX", "LQDA", "IPI", "MU", "HHH", "DX", "SM", "INSW", "SITM",
                  "EVC", "LPG", "STAA", "NVDA", "NLY", "RKT", "TER"]
        docs = [dict(CRDO),
                {"_id": "ALAB", "last_report": {"date": "2026-08-04"}},
                {"_id": "BE", "last_report": {"date": "2026-07-28"}},
                {"_id": "ARR", "last_report": {"date": "2026-07-22"}},
                {"_id": "FF", "last_report": {"date": "2016-11-09"}}]
        docs += [{"_id": s, "next_date": None, "when": None,
                  "last_report": None} for s in blanks]
        docs[docs.index(next(d for d in docs if d["_id"] == "IPI"))] = dict(IPI)
        rows = [{"symbol": s} for s in known + blanks]
        out = EF.attach(rows, db=FakeColl(docs), today=TODAY)
        self.assertEqual(out["n"], 21)
        self.assertEqual(out["n_fresh"], 0)
        self.assertEqual(out["n_known"], 5)
        self.assertEqual(out["n_unknown"], 16)
        self.assertEqual(out["most_recent"],
                         {"symbol": "CRDO", "reported_on": "2026-09-01",
                          "days_ago": 17})
        self.assertEqual(out["as_of"], TODAY)
        self.assertIs(out["window_days"], EP.REPORT_WINDOW_DAYS)
        self.assertIn("EarningsWhispers", out["source"])


# ----------------------------------------------------------------- payload

class PayloadTest(unittest.TestCase):
    def setUp(self):
        self._coll = EF.EW._coll
        EF.EW._coll = lambda: FakeColl([CRDO, BLANK])

    def tearDown(self):
        EF.EW._coll = self._coll

    def test_payload_carries_earnings_fresh_summary(self):
        out = GA._payload({"rows": _rows()})
        self.assertIsNotNone(out["earnings_fresh_summary"])
        self.assertEqual(out["earnings_fresh_summary"]["n"], 3)
        for r in out["rows"]:
            self.assertIn("earnings_fresh", r)

    def test_payload_key_set_is_otherwise_unchanged(self):
        """NEGATIVE — exactly the old eight keys plus two read-time joins
        (`earnings_fresh_summary` 2026-09-17, `since_report_summary`
        2026-09-21). Nothing else may creep into this payload."""
        out = GA._payload({"rows": _rows()})
        self.assertEqual(
            set(out),
            {"rows", "n", "max_rows", "capped", "groups", "built_at", "screen",
             "disclaimer", "earnings_fresh_summary", "since_report_summary"})


# ------------------------------------------------------- refresh_board_calendar

class RefreshTest(unittest.TestCase):
    def setUp(self):
        from growth import tracker as T
        self._board, self._refresh = T.board, EF.EW.refresh
        self.T = T

    def tearDown(self):
        self.T.board, EF.EW.refresh = self._board, self._refresh

    def _capture(self, rows):
        self.T.board = lambda: {"rows": rows}
        seen = {}

        def fake(**kw):
            seen.update(kw)
            return {"ok": True, "universe": len(kw.get("symbols") or []),
                    "refreshed": 1}
        EF.EW.refresh = fake
        return seen

    def test_refresh_board_calendar_sends_nothing(self):
        """NEGATIVE — no send path exists in this module at all."""
        src = _src()
        for word in ("push", "notify", "send_to_", "growth.alerts"):
            self.assertNotIn(word, src, word)
        seen = self._capture([{"symbol": "CRDO"}])
        EF.refresh_board_calendar()
        self.assertEqual(seen["symbols"], ["CRDO"])

    def test_refresh_board_calendar_passes_force_true_AND_merge_true_and_the_board_symbols(self):
        seen = self._capture([{"symbol": "CRDO"}, {"symbol": "NVDA"}])
        out = EF.refresh_board_calendar()
        self.assertIs(seen["force"], True)
        self.assertIs(seen["merge"], True)
        self.assertEqual(seen["symbols"], ["CRDO", "NVDA"])
        self.assertEqual(out["symbols"], 2)
        from growth import tracker as T
        self.assertLessEqual(len(seen["symbols"]), T.MAX_ROWS)

    def test_refresh_board_calendar_on_an_empty_board_is_a_no_op(self):
        """NEGATIVE."""
        self.T.board = lambda: {"rows": []}
        boom = lambda **kw: (_ for _ in ()).throw(AssertionError("refresh called"))
        EF.EW.refresh = boom
        self.assertEqual(EF.refresh_board_calendar(),
                         {"ok": True, "symbols": 0, "refreshed": 0,
                          "reason": "empty board"})

    def test_refresh_board_calendar_never_calls_refresh_without_merge(self):
        """NEGATIVE."""
        self.T.board = lambda: {"rows": [{"symbol": "CRDO"}]}

        def strict(**kw):
            if not kw.get("merge") or not kw.get("force"):
                raise AssertionError("refresh without merge/force")
            return {"ok": True, "refreshed": 1}
        EF.EW.refresh = strict
        self.assertTrue(EF.refresh_board_calendar()["ok"])


if __name__ == "__main__":
    unittest.main()
