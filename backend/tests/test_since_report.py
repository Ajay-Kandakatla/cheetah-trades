"""📅 Since the report — pins for the FACT column (Ajay 2026-09-21, item #3).

Three jobs:

1. EVERY served number is read back out of
   ``backend/scripts/board_growth_measured.json``. Rule: "ship the backtest
   with the claim" — a re-run that moves a figure fails here instead of
   quietly rewriting the sentence under his board.
2. `read_one` is pinned branch by branch, with the NEGATIVES first: a blank
   must never be able to render as 0%, and `known: true` must never be able to
   coexist with a null or non-finite return.
3. The two wirings (growth `_payload`, `bonde_api._run`) add the key, keep the
   row order and survive the join failing.

Nothing here touches Mongo or the network.
"""

from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from sepa import since_report as SR
from sepa import earnings_watch as EW
from sepa import prices as P
from sepa.bonde_picks import SURPRISE_STALE_DAYS
from sepa.earnings_picks import reaction_read

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "backend" / "scripts" / "board_growth_measured.json"
LIB = ROOT / "frontend" / "src" / "lib" / "sinceReport.ts"
MODULE = ROOT / "backend" / "sepa" / "since_report.py"

ART = json.loads(ARTIFACT.read_text())


def frame(closes, start="2026-08-03", dates=None, vols=None):
    """A daily frame shaped like the price cache hands one over."""
    idx = pd.to_datetime(dates) if dates is not None else pd.bdate_range(
        start=start, periods=len(closes))
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {"open": c, "high": c, "low": c, "close": c,
         "volume": np.asarray(vols if vols is not None else [1000.0] * len(c),
                              dtype=float)},
        index=idx)


# ---------------------------------------------------------------- the pins

class RunMeasuredPins(unittest.TestCase):
    """RUN_MEASURED is the artifact, field for field. Nothing retyped."""

    def test_cohort_fields_equal_the_artifact(self):
        pairs = [("growth", "growth_21"), ("bonde", "bonde_visible_all"),
                 ("universe", "universe_all")]
        for key, cohort in pairs:
            coh = ART["cohorts"][cohort]
            m = SR.RUN_MEASURED[key]
            with self.subTest(cohort=cohort):
                self.assertEqual(m["n"], coh["n"])
                self.assertAlmostEqual(m["pre_median_pct"],
                                       coh["pre_filed_126_pct"]["median"], places=2)
                self.assertAlmostEqual(m["pre_share_pos"],
                                       coh["pre_filed_126_pct"]["share_pos"], places=1)
                self.assertAlmostEqual(m["since_median_pct"],
                                       coh["since_10q_filed_pct"]["median"], places=2)
                self.assertAlmostEqual(m["since_share_pos"],
                                       coh["since_10q_filed_pct"]["share_pos"], places=1)
                self.assertEqual(m["n_positive"], coh["n_since_10q_filed_positive"])
                self.assertEqual(m["n_known"], coh["n_since_10q_filed_known"])

    def test_run_level_fields_equal_the_artifact(self):
        self.assertEqual(SR.RUN_MEASURED["benchmark"], ART["run"]["benchmark"])
        self.assertEqual(SR.RUN_MEASURED["doc"], SR.DOC)

    def test_constants_are_imported_never_retyped(self):
        self.assertEqual(SR.CALENDAR_STALE_SEC, EW.REFETCH_AFTER_SEC)
        self.assertEqual(EW.REFETCH_AFTER_SEC, EW._REFETCH_AFTER_SEC)


class HonestyLine(unittest.TestCase):

    def test_growth_line_carries_every_measured_number(self):
        s = SR.honesty_line("growth")
        for token in ("+46.40%", "−2.21%", "8 of 20", "126 sessions",
                      "MEASURED 2026-09-21", SR.DOC, "REPORT date",
                      "SEC filing date", "before the board could see it"):
            self.assertIn(token, s)

    def test_bonde_line_carries_every_measured_number(self):
        s = SR.honesty_line("bonde")
        for token in ("+8.19%", "+8.14%", "−4.41%", "57 of 152",
                      "126 sessions", SR.DOC, "REPORT date",
                      "SEC filing date"):
            self.assertIn(token, s)

    def test_NEGATIVE_the_bonde_line_says_scan_universe_not_the_market(self):
        """C6 — +8.14% is the scan universe's OWN pre-filing median, not an
        RSP read. Calling it 'the market' would be a claim the artifact does
        not make."""
        s = SR.honesty_line("bonde")
        self.assertIn("scan universe", s)
        self.assertNotIn("than the market", s)
        self.assertNotIn("the market's", s)
        self.assertNotIn("the market", SR.honesty_line("growth"))

    def test_NEGATIVE_no_line_says_bounce(self):
        for board in ("growth", "bonde"):
            self.assertNotIn("bounce", SR.honesty_line(board).lower())

    def test_NEGATIVE_the_module_cites_the_doc_and_not_the_artifact(self):
        src = MODULE.read_text()
        self.assertIn(SR.DOC, src)
        self.assertNotIn("board_growth" + "_measured", src)

    def test_the_lines_claim_nothing_forward(self):
        for board in ("growth", "bonde"):
            s = SR.honesty_line(board)
            self.assertIn("changes no order, no filter and no gate", s)


# ------------------------------------------------------------- read_one

CAL = {"date": "2026-09-01", "when": "AMC", "fetched_at": None}
DATES = ["2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"]


class ReadOneAnchor(unittest.TestCase):

    def test_AMC_anchors_on_the_next_session(self):
        f = frame([10, 11, 12, 13, 15], dates=DATES)
        r = SR.read_one({"date": "2026-09-01", "when": "AMC"}, f,
                        "2026-09-21", None, "closed")
        self.assertTrue(r["known"])
        self.assertEqual(r["anchor_date"], "2026-09-02")
        self.assertEqual(r["anchor_close"], 12.0)
        self.assertEqual(r["last_close"], 15.0)
        self.assertEqual(r["as_of"], "2026-09-04")
        self.assertEqual(r["sessions"], 2)
        self.assertAlmostEqual(r["pct"], round((15 / 12 - 1) * 100, 2), places=2)

    def test_BMO_anchors_on_the_report_day(self):
        f = frame([10, 11, 12, 13, 15], dates=DATES)
        r = SR.read_one({"date": "2026-09-01", "when": "BMO"}, f,
                        "2026-09-21", None, "closed")
        self.assertEqual(r["anchor_date"], "2026-09-01")
        self.assertEqual(r["anchor_close"], 11.0)
        self.assertEqual(r["sessions"], 3)

    def test_C5_unknown_timing_anchors_on_the_report_day_like_BMO(self):
        """The tooltip says 'the first session the market could trade on'. For
        `when: None` that IS the report day — `reaction_read` shifts only for
        AMC — so the phrase has to be true on this branch too."""
        f = frame([10, 11, 12, 13, 15], dates=DATES)
        r = SR.read_one({"date": "2026-09-01", "when": None}, f,
                        "2026-09-21", None, "closed")
        self.assertEqual(r["anchor_date"], "2026-09-01")
        self.assertIsNone(r["when"])


class ReadOneNegatives(unittest.TestCase):
    F = None

    def setUp(self):
        self.F = frame([10, 11, 12, 13, 15], dates=DATES)

    def _blank(self, r, reason):
        self.assertFalse(r["known"])
        self.assertIsNone(r["pct"])
        self.assertEqual(r["reason"], reason)
        self.assertIn(reason, SR.REASONS)

    def test_NEGATIVE_no_report(self):
        self._blank(SR.read_one(None, self.F, "2026-09-21"), "no_report")
        self._blank(SR.read_one({}, self.F, "2026-09-21"), "no_report")
        self._blank(SR.read_one({"date": None}, self.F, "2026-09-21"), "no_report")

    def test_NEGATIVE_bad_date(self):
        self._blank(SR.read_one({"date": "not-a-date"}, self.F, "2026-09-21"),
                    "bad_date")

    def test_NEGATIVE_future_report_is_not_traded_yet(self):
        self._blank(SR.read_one({"date": "2026-12-01"}, self.F, "2026-09-21"),
                    "not_traded_yet")

    def test_NEGATIVE_report_predates_the_screened_quarter(self):
        """The live 2016-11-09 case on the growth board: the calendar's newest
        report is for an older quarter than the one the board screened on."""
        r = SR.read_one({"date": "2016-11-09"}, self.F, "2026-09-21",
                        "2026-06-30", "closed")
        self._blank(r, "report_predates_period")

    def test_period_end_None_skips_the_check(self):
        """Bonde rows carry no period_end — the check is skipped, not failed."""
        f = frame([10, 11, 12, 13, 15], dates=DATES)
        r = SR.read_one({"date": "2026-09-01", "when": "BMO"}, f,
                        "2026-09-21", None, "closed")
        self.assertTrue(r["known"])

    def test_NEGATIVE_no_bars(self):
        self._blank(SR.read_one(CAL, None, "2026-09-21"), "no_bars")
        self._blank(SR.read_one(CAL, frame([], dates=[]), "2026-09-21"), "no_bars")

    def test_NEGATIVE_report_before_the_first_bar(self):
        self._blank(SR.read_one({"date": "2020-01-02"}, self.F, "2026-09-21",
                                None, "closed"), "before_first_bar")

    def test_every_branch_returns_the_exact_fourteen_keys(self):
        cases = [
            SR.read_one(None, self.F, "2026-09-21"),
            SR.read_one({"date": "xx"}, self.F, "2026-09-21"),
            SR.read_one({"date": "2026-12-01"}, self.F, "2026-09-21"),
            SR.read_one({"date": "2016-11-09"}, self.F, "2026-09-21", "2026-06-30"),
            SR.read_one(CAL, None, "2026-09-21"),
            SR.read_one({"date": "2020-01-02"}, self.F, "2026-09-21", None, "closed"),
            SR.read_one(CAL, self.F, "2026-09-21", None, "closed"),
        ]
        want = set(SR._ROW_KEYS)
        self.assertEqual(len(want), 14)
        for r in cases:
            self.assertEqual(set(r), want)

    def test_NEGATIVE_a_blank_is_never_zero(self):
        for r in (SR.read_one(None, self.F, "2026-09-21"),
                  SR.read_one(CAL, None, "2026-09-21")):
            self.assertIsNone(r["pct"])
            self.assertNotEqual(r["pct"], 0.0)


class FreshnessLabels(unittest.TestCase):
    """Labels, never gates — the same reading the surprise leg applies to the
    very same calendar doc."""

    def test_stale_report_flips_at_the_imported_constant(self):
        import datetime as dt
        today = dt.date(2026, 9, 21)
        f = frame([10, 11, 12, 13, 15], dates=DATES)
        at_limit = (today - dt.timedelta(days=SURPRISE_STALE_DAYS)).isoformat()
        past = (today - dt.timedelta(days=SURPRISE_STALE_DAYS + 1)).isoformat()
        r1 = SR.read_one({"date": at_limit}, f, today.isoformat(), None, "closed")
        r2 = SR.read_one({"date": past}, f, today.isoformat(), None, "closed")
        self.assertEqual(r1["report_age_days"], SURPRISE_STALE_DAYS)
        self.assertFalse(r1["stale_report"])
        self.assertEqual(r2["report_age_days"], SURPRISE_STALE_DAYS + 1)
        self.assertTrue(r2["stale_report"])

    def test_calendar_stale_reads_the_docs_own_refetch_rule(self):
        import time
        f = frame([10, 11, 12, 13, 15], dates=DATES)
        fresh = {"date": "2026-09-01", "when": "AMC", "fetched_at": time.time()}
        old = {"date": "2026-09-01", "when": "AMC",
               "fetched_at": time.time() - EW.REFETCH_AFTER_SEC - 60}
        none = {"date": "2026-09-01", "when": "AMC"}
        self.assertFalse(SR.read_one(fresh, f, "2026-09-21", None, "closed")["calendar_stale"])
        self.assertTrue(SR.read_one(old, f, "2026-09-21", None, "closed")["calendar_stale"])
        self.assertIsNone(SR.read_one(none, f, "2026-09-21", None, "closed")["calendar_stale"])

    def test_NEGATIVE_an_unreadable_fetched_at_is_None_not_a_crash(self):
        f = frame([10, 11, 12, 13, 15], dates=DATES)
        r = SR.read_one({"date": "2026-09-01", "when": "AMC",
                         "fetched_at": "yesterday"}, f, "2026-09-21", None, "closed")
        self.assertIsNone(r["calendar_fetched_at"])
        self.assertIsNone(r["calendar_stale"])
        self.assertTrue(r["known"])


class InProgressBar(unittest.TestCase):
    """C1 — `crontab:407` patches today's partial bar into the cache hourly."""

    DATES = ["2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18",
             "2026-09-21"]
    CAL = {"date": "2026-09-15", "when": "BMO"}

    def _f(self):
        return frame([10, 11, 12, 13, 14, 99], dates=self.DATES)

    def test_the_today_bar_is_dropped_during_rth_and_premarket(self):
        for sess in ("rth", "premarket"):
            with self.subTest(session=sess):
                r = SR.read_one(self.CAL, self._f(), "2026-09-21", None, sess)
                self.assertEqual(r["as_of"], "2026-09-18")
                self.assertEqual(r["last_close"], 14.0)
                self.assertEqual(r["sessions"], 3)

    def test_NEGATIVE_the_today_bar_stays_after_hours_when_closed_and_unknown(self):
        for sess in ("afterhours", "closed", None):
            with self.subTest(session=sess):
                r = SR.read_one(self.CAL, self._f(), "2026-09-21", None, sess)
                self.assertEqual(r["as_of"], "2026-09-21")
                self.assertEqual(r["last_close"], 99.0)
                self.assertEqual(r["sessions"], 4)

    def test_a_frame_holding_only_todays_partial_reads_no_bars(self):
        f = frame([99], dates=["2026-09-21"])
        r = SR.read_one(self.CAL, f, "2026-09-21", None, "rth")
        self.assertFalse(r["known"])
        self.assertEqual(r["reason"], "no_bars")

    def test_NEGATIVE_a_zero_length_window_is_blank_never_plus_zero(self):
        """AMC on D with the frame ending D+1: the reaction bar IS the latest
        closed bar, so there is no 'since' yet. `+0.0%` would read as flat."""
        f = frame([10, 11, 12], dates=["2026-08-31", "2026-09-01", "2026-09-02"])
        r = SR.read_one({"date": "2026-09-01", "when": "AMC"}, f,
                        "2026-09-21", None, "closed")
        self.assertFalse(r["known"])
        self.assertIsNone(r["pct"])
        self.assertEqual(r["reason"], "not_traded_yet")

    def test_NEGATIVE_BMO_on_the_last_bar_is_also_blank(self):
        f = frame([10, 11, 12], dates=["2026-08-31", "2026-09-01", "2026-09-02"])
        r = SR.read_one({"date": "2026-09-02", "when": "BMO"}, f,
                        "2026-09-21", None, "closed")
        self.assertFalse(r["known"])
        self.assertEqual(r["reason"], "not_traded_yet")

    def test_POSITIVE_one_closed_bar_after_the_reaction_is_enough(self):
        f = frame([10, 11, 12, 13], dates=["2026-08-31", "2026-09-01",
                                           "2026-09-02", "2026-09-03"])
        r = SR.read_one({"date": "2026-09-01", "when": "AMC"}, f,
                        "2026-09-21", None, "closed")
        self.assertTrue(r["known"])
        self.assertGreaterEqual(r["sessions"], 1)

    def test_known_true_always_implies_at_least_one_session(self):
        f = frame([10, 11, 12, 13, 14, 99], dates=self.DATES)
        for sess in ("rth", "premarket", "afterhours", "closed", None):
            r = SR.read_one(self.CAL, f, "2026-09-21", None, sess)
            if r["known"]:
                self.assertGreaterEqual(r["sessions"], 1)

    def test_attach_reads_the_session_from_the_one_clock(self):
        """C1 — with no `session` given, `attach` asks
        `prices.trade_session(EW._today_et())`. No second clock."""
        import datetime as dt
        from zoneinfo import ZoneInfo
        rows_rth = [{"symbol": "AAA"}]
        rows_pm = [{"symbol": "AAA"}]
        frames = {"AAA": frame([10, 11, 12, 13, 14, 99], dates=self.DATES)}
        reports = {"AAA": dict(self.CAL)}
        orig = EW._today_et
        try:
            # a frozen Tuesday 11:00 ET -> rth -> the today-bar goes
            EW._today_et = lambda: dt.datetime(2026, 9, 21, 11, 0,
                                               tzinfo=ZoneInfo("America/New_York"))
            SR.attach(rows_rth, reports=reports, frames=frames, today="2026-09-21")
            # 17:00 ET -> afterhours -> the today-bar stays
            EW._today_et = lambda: dt.datetime(2026, 9, 21, 17, 0,
                                               tzinfo=ZoneInfo("America/New_York"))
            SR.attach(rows_pm, reports=reports, frames=frames, today="2026-09-21")
        finally:
            EW._today_et = orig
        self.assertEqual(rows_rth[0]["since_report"]["as_of"], "2026-09-18")
        self.assertEqual(rows_pm[0]["since_report"]["as_of"], "2026-09-21")


class StalePriceCacheReadsAsNotTradedYet(unittest.TestCase):
    """A KNOWN LIMITATION, pinned so it cannot change without this test.

    A report dated in the PAST (<= today) whose name's cached frame stopped
    updating BEFORE that date takes the `report_date >= last_bar` branch at
    `since_report.py:269-272` and blanks as `not_traded_yet`. The served
    sentence for that reason says "no session has closed AFTER the first one
    the market could trade on this report", which is false here: sessions did
    close, the `price_cache` doc simply went stale. And the blank carries
    `as_of: None`, so the reader cannot see where the bars stop.

    Not fixed in this package by design. The seven `REASONS` and the blank
    sentences are frozen by the spec (3.11 / 3.10); telling the stale-cache
    case apart needs either an eighth reason or `as_of` served on the blank,
    and both are HIS CALL (doc 11.10). These tests pin TODAY's behaviour."""

    CAL = {"date": "2026-09-10", "when": "BMO"}
    DATES = ["2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03",
             "2026-09-04"]

    def test_a_past_report_after_a_stale_frames_last_bar_blanks(self):
        f = frame([10, 11, 12, 13, 14], dates=self.DATES)
        r = SR.read_one(self.CAL, f, "2026-09-21", None, "closed")
        self.assertFalse(r["known"])
        self.assertIsNone(r["pct"])
        self.assertEqual(r["reason"], "not_traded_yet")

    def test_the_blank_cannot_say_where_the_bars_stop(self):
        """The reader-facing half of the limitation: `as_of` is null on the
        blank, so the surface cannot show the 2026-09-04 cut-off."""
        f = frame([10, 11, 12, 13, 14], dates=self.DATES)
        r = SR.read_one(self.CAL, f, "2026-09-21", None, "closed")
        self.assertIsNone(r["as_of"])
        self.assertIsNone(r["last_close"])
        self.assertIsNone(r["sessions"])

    def test_NEGATIVE_a_fresh_frame_over_the_same_report_is_known(self):
        """The same report against a frame that DID keep updating reads
        normally — the blank above is the cache's state, not the report's."""
        f = frame([10, 11, 12, 13, 14, 15, 16],
                  dates=self.DATES + ["2026-09-10", "2026-09-11"])
        r = SR.read_one(self.CAL, f, "2026-09-21", None, "closed")
        self.assertTrue(r["known"])
        self.assertEqual(r["anchor_date"], "2026-09-10")
        self.assertEqual(r["as_of"], "2026-09-11")

    def test_NEGATIVE_no_eighth_reason_was_added_for_it(self):
        """If a `stale_cache` reason ever lands, this fires and doc 11.10
        must be closed with it (the FE blank map is keyed on these seven)."""
        self.assertEqual(len(SR.REASONS), 7)
        self.assertNotIn("stale_cache", SR.REASONS)


class NonFiniteGuard(unittest.TestCase):
    """C4 — `_fetch_yfinance` does not filter close > 0, so a cached frame can
    hold a zero or NaN close. `known: true` with a non-finite return must be
    unreachable; the API scrub is a belt, not the guard."""

    CAL = {"date": "2026-09-01", "when": "BMO"}

    def test_a_zero_anchor_close_is_blank(self):
        f = frame([10, 0.0, 12, 13], dates=["2026-08-31", "2026-09-01",
                                            "2026-09-02", "2026-09-03"])
        r = SR.read_one(self.CAL, f, "2026-09-21", None, "closed")
        self.assertFalse(r["known"])
        self.assertIsNone(r["pct"])
        self.assertEqual(r["reason"], "insufficient_history")

    def test_a_NaN_last_close_is_blank(self):
        f = frame([10, 11, 12, float("nan")], dates=["2026-08-31", "2026-09-01",
                                                     "2026-09-02", "2026-09-03"])
        r = SR.read_one(self.CAL, f, "2026-09-21", None, "closed")
        self.assertFalse(r["known"])
        self.assertIsNone(r["pct"])

    def test_an_inf_anchor_close_is_blank(self):
        f = frame([10, float("inf"), 12, 13], dates=["2026-08-31", "2026-09-01",
                                                     "2026-09-02", "2026-09-03"])
        r = SR.read_one(self.CAL, f, "2026-09-21", None, "closed")
        self.assertFalse(r["known"])
        self.assertIsNone(r["pct"])

    def test_the_raw_cell_is_strict_json_before_any_scrub(self):
        f = frame([10, 11, 12, 13], dates=["2026-08-31", "2026-09-01",
                                           "2026-09-02", "2026-09-03"])
        for cal in (self.CAL, None, {"date": "bad"}):
            r = SR.read_one(cal, f, "2026-09-21", None, "closed")
            json.dumps(r, allow_nan=False)

    def test_NEGATIVE_known_true_never_carries_a_non_finite_pct(self):
        cases = [
            frame([10, 11, 12, 13], dates=["2026-08-31", "2026-09-01",
                                           "2026-09-02", "2026-09-03"]),
            frame([10, 0.0, 12, 13], dates=["2026-08-31", "2026-09-01",
                                            "2026-09-02", "2026-09-03"]),
            frame([10, 11, 12, float("nan")], dates=["2026-08-31", "2026-09-01",
                                                     "2026-09-02", "2026-09-03"]),
            frame([10, float("inf"), 12, 13], dates=["2026-08-31", "2026-09-01",
                                                     "2026-09-02", "2026-09-03"]),
        ]
        for f in cases:
            r = SR.read_one(self.CAL, f, "2026-09-21", None, "closed")
            if r["known"]:
                self.assertTrue(math.isfinite(r["pct"]))
                self.assertTrue(math.isfinite(r["anchor_close"]))
                self.assertTrue(math.isfinite(r["last_close"]))


class IntradayStampedIndex(unittest.TestCase):
    """CAUGHT IN THE CONTAINER 2026-09-21: a live `price_cache` frame is NOT
    stamped midnight — CRDO's older bars carry `04:00:00`. Anchoring by
    `index.get_loc(Timestamp(date))` raised KeyError on EVERY name and blanked
    both boards with `insufficient_history`. The lookup is by DATE."""

    def test_an_04_00_stamped_frame_still_anchors(self):
        idx = pd.to_datetime([d + " 04:00:00" for d in DATES])
        f = frame([10, 11, 12, 13, 15], dates=idx)
        r = SR.read_one({"date": "2026-09-01", "when": "AMC"}, f,
                        "2026-09-21", None, "closed")
        self.assertTrue(r["known"], r["reason"])
        self.assertEqual(r["anchor_date"], "2026-09-02")
        self.assertEqual(r["anchor_close"], 12.0)
        self.assertEqual(r["as_of"], "2026-09-04")
        self.assertEqual(r["sessions"], 2)

    def test_a_mixed_stamp_frame_still_anchors(self):
        idx = pd.to_datetime(["2026-08-31 04:00:00", "2026-09-01 04:00:00",
                              "2026-09-02 00:00:00", "2026-09-03 00:00:00",
                              "2026-09-04 00:00:00"])
        f = frame([10, 11, 12, 13, 15], dates=idx)
        r = SR.read_one({"date": "2026-09-01", "when": "BMO"}, f,
                        "2026-09-21", None, "closed")
        self.assertTrue(r["known"], r["reason"])
        self.assertEqual(r["anchor_date"], "2026-09-01")

    def test_the_in_progress_trim_reads_an_04_00_today_bar(self):
        idx = pd.to_datetime(["2026-09-15 04:00:00", "2026-09-16 04:00:00",
                              "2026-09-17 04:00:00", "2026-09-18 04:00:00",
                              "2026-09-21 04:00:00"])
        f = frame([10, 11, 12, 13, 99], dates=idx)
        rth = SR.read_one({"date": "2026-09-16", "when": "BMO"}, f,
                          "2026-09-21", None, "rth")
        closed = SR.read_one({"date": "2026-09-16", "when": "BMO"}, f,
                             "2026-09-21", None, "closed")
        self.assertEqual(rth["as_of"], "2026-09-18")
        self.assertEqual(closed["as_of"], "2026-09-21")


class Precision(unittest.TestCase):
    """C8 — both closes come off the FRAME at 4 dp. `reaction_read` rounds its
    own `last_close` to 2, which would print two different prices for one bar."""

    def test_sub_penny_closes_survive(self):
        f = frame([1.1111, 1.2345, 1.3456], dates=["2026-08-31", "2026-09-01",
                                                   "2026-09-02"])
        r = SR.read_one({"date": "2026-09-01", "when": "BMO"}, f,
                        "2026-09-21", None, "closed")
        self.assertTrue(r["known"])
        self.assertEqual(r["anchor_close"], 1.2345)
        self.assertEqual(r["last_close"], 1.3456)
        raw = reaction_read(f, "2026-09-01", "BMO", min_history=1)
        self.assertNotEqual(r["last_close"], raw["last_close"])


# --------------------------------------------------------------- attach

def _rows(*syms):
    return [{"symbol": s, "price": 1.0} for s in syms]


class Attach(unittest.TestCase):

    def setUp(self):
        self.frames = {s: frame([10, 11, 12, 13, 15], dates=DATES)
                       for s in ("AAA", "BBB", "CCC")}
        self.reports = {"AAA": {"date": "2026-09-01", "when": "AMC"},
                        "BBB": {"date": "2026-09-01", "when": "BMO"}}

    def test_ORDER_PIN_rows_are_untouched_except_for_the_added_key(self):
        rows = _rows("AAA", "BBB", "CCC")
        before = [dict(r) for r in rows]
        SR.attach(rows, reports=self.reports, frames=self.frames,
                  today="2026-09-21", session="closed")
        self.assertEqual([r["symbol"] for r in rows], ["AAA", "BBB", "CCC"])
        for r, b in zip(rows, before):
            self.assertEqual({k: v for k, v in r.items() if k != "since_report"}, b)
            self.assertIn("since_report", r)

    def test_the_summary_counts_add_up(self):
        rows = _rows("AAA", "BBB", "CCC")
        s = SR.attach(rows, reports=self.reports, frames=self.frames,
                      today="2026-09-21", session="closed")
        self.assertEqual(s["n"], 3)
        self.assertEqual(s["n_known"] + s["n_blank"], s["n"])
        self.assertEqual(sum(s["blank_reasons"].values()), s["n_blank"])
        self.assertEqual(s["n_known"], 2)
        self.assertEqual(s["blank_reasons"], {"no_report": 1})
        self.assertEqual(s["as_of"], "2026-09-04")
        self.assertEqual(s["date_basis"], SR.DATE_BASIS)
        self.assertEqual(s["honesty"], SR.honesty_line("growth"))

    def test_the_summary_key_set_is_frozen(self):
        s = SR.attach(_rows("AAA"), reports=self.reports, frames=self.frames,
                      today="2026-09-21", session="closed")
        self.assertEqual(set(s), {
            "n", "n_known", "n_positive", "n_blank", "blank_reasons",
            "n_stale_report", "n_calendar_stale", "as_of", "date_basis",
            "date_basis_note", "measured", "honesty", "source"})
        self.assertEqual(set(s["measured"]), {
            "run_date", "doc", "sessions_before", "benchmark", "board",
            "universe"})

    def test_NEGATIVE_a_raising_reports_lookup_still_serves_the_board(self):
        class Boom(dict):
            def get(self, *a, **k):
                raise RuntimeError("calendar is on fire")
        rows = _rows("AAA", "BBB")
        s = SR.attach(rows, reports=Boom(), frames=self.frames,
                      today="2026-09-21", session="closed")
        self.assertEqual(s["n"], 2)
        self.assertEqual(s["n_known"], 0)
        for r in rows:
            self.assertFalse(r["since_report"]["known"])
            self.assertIn("since_report", r)

    def test_NEGATIVE_a_raising_frames_lookup_still_serves_the_board(self):
        class Boom(dict):
            def get(self, *a, **k):
                raise RuntimeError("cache is on fire")
        rows = _rows("AAA")
        s = SR.attach(rows, reports=self.reports, frames=Boom(),
                      today="2026-09-21", session="closed")
        self.assertEqual(s["n_known"], 0)
        self.assertEqual(rows[0]["since_report"]["reason"], "no_bars")

    def test_a_NaN_close_leaves_the_payload_strict_json(self):
        frames = {"AAA": frame([10, 11, 12, float("nan"), 15], dates=DATES)}
        rows = _rows("AAA")
        s = SR.attach(rows, reports=self.reports, frames=frames,
                      today="2026-09-21", session="closed")
        json.dumps({"rows": rows, "since_report_summary": s}, allow_nan=False)

    def test_C7_a_row_shared_by_two_sections_is_visited_once(self):
        shared = {"symbol": "AAA"}
        rows = [shared, {"symbol": "BBB"}, shared]
        calls = []
        orig = SR.read_one
        try:
            def spy(*a, **k):
                calls.append(a[0])
                return orig(*a, **k)
            SR.read_one = spy
            s = SR.attach(rows, reports=self.reports, frames=self.frames,
                          today="2026-09-21", session="closed")
        finally:
            SR.read_one = orig
        self.assertEqual(len(calls), 2)
        self.assertEqual(s["n"], 2)
        self.assertIs(rows[0]["since_report"], rows[2]["since_report"])

    def test_NEGATIVE_dedupe_is_by_identity_not_by_symbol(self):
        """Two DIFFERENT dicts with the same symbol count twice — the board
        never does that today; the test documents the contract."""
        rows = [{"symbol": "AAA"}, {"symbol": "AAA"}]
        s = SR.attach(rows, reports=self.reports, frames=self.frames,
                      today="2026-09-21", session="closed")
        self.assertEqual(s["n"], 2)

    def test_attach_bonde_flattens_every_section_once(self):
        shared = {"symbol": "AAA"}
        payload = {"sections": {"pivot": [shared],
                                "explosive": [shared, {"symbol": "BBB"}],
                                "steady": []}}
        out = SR.attach_bonde(payload)
        self.assertIs(out, payload)
        self.assertEqual(out["since_report_summary"]["n"], 2)
        self.assertEqual(out["since_report_summary"]["honesty"],
                         SR.honesty_line("bonde"))
        for sec in payload["sections"].values():
            for r in sec:
                self.assertIn("since_report", r)

    def test_attach_bonde_survives_a_shapeless_payload(self):
        self.assertEqual(SR.attach_bonde(None), None)
        self.assertEqual(SR.attach_bonde({})["since_report_summary"]["n"], 0)


# --------------------------------------------------------- bulk_cached_frames

class FakeColl:
    def __init__(self, docs):
        self.docs = docs
        self.queries = []

    def find(self, q=None, proj=None):
        self.queries.append(q)
        want = set((q or {}).get("symbol", {}).get("$in") or [])
        return [d for d in self.docs if not want or d.get("symbol") in want]


class BulkCachedFrames(unittest.TestCase):

    def setUp(self):
        self.orig_mongo = P._get_mongo
        self.orig_fetches = {n: getattr(P, n) for n in
                             ("_fetch", "_fetch_massive", "_fetch_yfinance")
                             if hasattr(P, n)}

    def tearDown(self):
        P._get_mongo = self.orig_mongo
        for n, f in self.orig_fetches.items():
            setattr(P, n, f)

    def _docs(self):
        bars = [{"date": d, "open": 1.0, "high": 2.0, "low": 0.5,
                 "close": c, "volume": 100.0 + i}
                for i, (d, c) in enumerate(zip(DATES, [10, 11, 12, 13, 15]))]
        return [{"symbol": "AAA", "bars": bars, "cached_at": 0}]

    def test_one_find_and_the_same_reshaping_as_mongo_get(self):
        coll = FakeColl(self._docs())
        P._get_mongo = lambda: coll
        out = P.bulk_cached_frames(["AAA", "ZZZ"])
        self.assertEqual(len(coll.queries), 1)
        self.assertEqual(set(out), {"AAA"})
        f = out["AAA"]
        self.assertEqual(list(f.columns), ["open", "high", "low", "close", "volume"])
        self.assertEqual(f["close"].iloc[-1], 15.0)
        self.assertEqual(f.index[0].date().isoformat(), DATES[0])

    def test_NEGATIVE_it_never_fetches(self):
        coll = FakeColl([])
        P._get_mongo = lambda: coll

        def boom(*a, **k):
            raise AssertionError("bulk_cached_frames reached the network")
        for n in self.orig_fetches:
            setattr(P, n, boom)
        self.assertEqual(P.bulk_cached_frames(["AAA"]), {})

    def test_NEGATIVE_no_mongo_and_empty_input_are_empty_dicts(self):
        P._get_mongo = lambda: None
        self.assertEqual(P.bulk_cached_frames(["AAA"]), {})
        self.assertEqual(P.bulk_cached_frames([]), {})
        self.assertEqual(P.bulk_cached_frames(None), {})

    def test_NEGATIVE_a_bad_doc_is_skipped_not_fatal(self):
        docs = self._docs() + [{"symbol": "BAD", "bars": [{"nope": 1}]},
                               {"symbol": "EMPTY", "bars": []}]
        P._get_mongo = lambda: FakeColl(docs)
        out = P.bulk_cached_frames(["AAA", "BAD", "EMPTY"])
        self.assertEqual(set(out), {"AAA"})

    def test_NEGATIVE_a_raising_collection_returns_an_empty_dict(self):
        class Boom:
            def find(self, *a, **k):
                raise RuntimeError("mongo down")
        P._get_mongo = lambda: Boom()
        self.assertEqual(P.bulk_cached_frames(["AAA"]), {})


# ------------------------------------------------------- reaction_read kwarg

class ReactionReadMinHistory(unittest.TestCase):

    def test_the_default_is_unchanged_at_fifty(self):
        c = list(range(1, 60))
        f = frame(c)
        d49 = f.index[49].date().isoformat()
        d50 = f.index[50].date().isoformat()
        self.assertIsNone(reaction_read(f, d49, "BMO"))
        self.assertIsNotNone(reaction_read(f, d50, "BMO"))

    def test_min_history_one_anchors_at_k_equals_one(self):
        f = frame([10, 11, 12], dates=["2026-08-31", "2026-09-01", "2026-09-02"])
        r = reaction_read(f, "2026-09-01", "BMO", min_history=1)
        self.assertIsNotNone(r)
        self.assertEqual(r["reaction_date"], "2026-09-01")

    def test_NEGATIVE_min_history_one_still_refuses_k_zero(self):
        f = frame([10, 11, 12], dates=["2026-08-31", "2026-09-01", "2026-09-02"])
        self.assertIsNone(reaction_read(f, "2026-08-31", "BMO", min_history=1))

    def test_NEGATIVE_a_reaction_session_not_in_the_frame_is_still_None(self):
        f = frame([10, 11, 12], dates=["2026-08-31", "2026-09-01", "2026-09-02"])
        self.assertIsNone(reaction_read(f, "2026-09-02", "AMC", min_history=1))


# ---------------------------------------------------------- calendar accessor

class CalendarFetchedAt(unittest.TestCase):

    def test_last_report_map_carries_fetched_at_additively(self):
        docs = [{"_id": "AAA", "fetched_at": 1790027403,
                 "last_report": {"date": "2026-09-01", "when": "AMC",
                                 "eps_actual": 1.2, "eps_estimate": 1.17,
                                 "surprise_pct": 2.69}},
                {"_id": "BBB", "last_report": None}]

        class C:
            def find(self, q, proj=None):
                self.proj = proj
                return docs
        c = C()
        orig = EW._coll
        try:
            EW._coll = lambda: c
            out = EW.last_report_map(["AAA", "BBB"])
        finally:
            EW._coll = orig
        self.assertEqual(set(out), {"AAA"})
        self.assertEqual(out["AAA"]["fetched_at"], 1790027403)
        for k in ("date", "when", "eps_actual", "eps_estimate", "surprise_pct"):
            self.assertIn(k, out["AAA"])
        self.assertIn("fetched_at", c.proj)

    def test_NEGATIVE_a_doc_without_fetched_at_reads_None(self):
        docs = [{"_id": "AAA", "last_report": {"date": "2026-09-01"}}]

        class C:
            def find(self, q, proj=None):
                return docs
        orig = EW._coll
        try:
            EW._coll = lambda: C()
            out = EW.last_report_map(["AAA"])
        finally:
            EW._coll = orig
        self.assertIsNone(out["AAA"]["fetched_at"])


# ------------------------------------------------------------------ the FE lock

class FrontendLabelLock(unittest.TestCase):
    """The tooltip prints "157 days" and "3-day refresh window" in words. Those
    two literals are the BE constants' semantics — pin them so the label can
    never drift from the enforcing constant (Rule #1)."""

    def test_the_lib_labels_equal_the_backend_constants(self):
        src = LIB.read_text()
        import re
        m = re.search(r"SURPRISE_STALE_DAYS_LABEL\s*=\s*(\d+)", src)
        n = re.search(r"CALENDAR_STALE_DAYS_LABEL\s*=\s*(\d+)", src)
        self.assertIsNotNone(m, "sinceReport.ts must export SURPRISE_STALE_DAYS_LABEL")
        self.assertIsNotNone(n, "sinceReport.ts must export CALENDAR_STALE_DAYS_LABEL")
        self.assertEqual(int(m.group(1)), SURPRISE_STALE_DAYS)
        self.assertEqual(int(n.group(1)), EW.REFETCH_AFTER_SEC // 86400)

    def test_every_reason_has_a_sentence_in_the_lib(self):
        src = LIB.read_text()
        for reason in SR.REASONS:
            self.assertIn(reason, src)


# ------------------------------------------------------------------ the boards

class GrowthPayload(unittest.TestCase):

    def setUp(self):
        from growth import api as GA
        from growth import earnings_fresh as EF
        self.GA, self.EF = GA, EF
        self._coll = EF.EW._coll
        EF.EW._coll = lambda: None
        self._reports, self._frames = EW.last_report_map, P.bulk_cached_frames
        EW.last_report_map = lambda syms: {
            "AAA": {"date": "2026-09-01", "when": "AMC"}}
        P.bulk_cached_frames = lambda syms: {
            "AAA": frame([10, 11, 12, 13, 15], dates=DATES)}

    def tearDown(self):
        self.EF.EW._coll = self._coll
        EW.last_report_map, P.bulk_cached_frames = self._reports, self._frames

    def test_the_payload_carries_the_summary_and_every_row_carries_a_cell(self):
        out = self.GA._payload({"rows": [{"symbol": "AAA", "price": 1.0},
                                         {"symbol": "ZZZ", "price": 2.0}]})
        s = out["since_report_summary"]
        self.assertIsNotNone(s)
        self.assertEqual(s["n"], 2)
        self.assertEqual(s["n_known"], 1)
        for r in out["rows"]:
            self.assertIn("since_report", r)
        self.assertEqual([r["symbol"] for r in out["rows"]], ["AAA", "ZZZ"])

    def test_the_payload_is_strict_json(self):
        out = self.GA._payload({"rows": [{"symbol": "AAA", "price": 1.0}]})
        json.dumps(out, allow_nan=False, default=str)


class BondeApiWiring(unittest.TestCase):

    def setUp(self):
        from sepa import bonde_api as BA
        self.BA = BA
        self.shared = {"symbol": "AAA"}
        self.board = {"sections": {"pivot": [self.shared],
                                   "explosive": [self.shared, {"symbol": "BBB"}]},
                      "counts": {"pivot": 1, "explosive": 2}}
        self._board, self._live = BA.B.board, BA.BL.attach
        BA.B.board = lambda **k: self.board
        BA.BL.attach = lambda b: b
        self._reports, self._frames = EW.last_report_map, SR.frames_for
        EW.last_report_map = lambda syms: {
            "AAA": {"date": "2026-09-01", "when": "AMC"}}
        SR.frames_for = lambda syms: {
            "AAA": frame([10, 11, 12, 13, 15], dates=DATES)}

    def tearDown(self):
        self.BA.B.board, self.BA.BL.attach = self._board, self._live
        EW.last_report_map, SR.frames_for = self._reports, self._frames

    def _run(self):
        # `asyncio.run` CLOSES the loop and leaves the thread with none, and on
        # py3.9 the next module that builds an `asyncio.Lock()` at import time
        # (sepa/insider.py, imported by sepa/scanner.py) then blows up in
        # whatever test file happens to run after this one -- an order-dependent
        # red that only shows when this file sorts first. Own the loop and hand
        # a fresh one back. Same pattern as tests/test_bonde_live.py.
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(
                self.BA.bonde_board(new_days=7)).body
        finally:
            loop.close()
            asyncio.set_event_loop(asyncio.new_event_loop())

    def test_every_row_in_every_section_carries_a_cell(self):
        body = json.loads(self._run())
        self.assertIn("since_report_summary", body)
        self.assertEqual(body["since_report_summary"]["n"], 2)
        for sec in body["sections"].values():
            for r in sec:
                self.assertIn("since_report", r)

    def test_section_and_row_order_are_unchanged(self):
        body = json.loads(self._run())
        self.assertEqual(list(body["sections"]), ["pivot", "explosive"])
        self.assertEqual([r["symbol"] for r in body["sections"]["explosive"]],
                         ["AAA", "BBB"])

    def test_NEGATIVE_the_board_is_still_served_when_the_join_raises(self):
        orig = SR.attach_bonde
        try:
            def boom(_p):
                raise RuntimeError("join is on fire")
            SR.attach_bonde = boom
            body = json.loads(self._run())
        finally:
            SR.attach_bonde = orig
        self.assertIn("sections", body)
        self.assertNotIn("since_report_summary", body)

    def test_NEGATIVE_running_the_endpoint_leaves_a_usable_loop_behind(self):
        """Regression: `asyncio.run` here closed the thread's loop, so the next
        test file that imports a module building an `asyncio.Lock()` at import
        time died with `There is no current event loop in thread 'MainThread'`.
        Order-dependent red -- demo was
        `pytest tests/test_since_report.py tests/test_sepa_contracts.py`."""
        import asyncio
        self._run()
        loop = asyncio.get_event_loop()
        self.assertFalse(loop.is_closed())
        lock = asyncio.Lock()          # what blew up on py3.9
        self.assertIsNotNone(lock)


# ------------------------------------------------------------------ fixtures

FIXTURES = ROOT / "frontend" / "src" / "pages" / "__fixtures__"
SUMMARY_KEYS = {"n", "n_known", "n_positive", "n_blank", "blank_reasons",
                "n_stale_report", "n_calendar_stale", "as_of", "date_basis",
                "date_basis_note", "measured", "honesty", "source"}


class FixtureContract(unittest.TestCase):
    """The two saved payloads are the REAL served shape — the AMD fixture
    pattern. If the shape moves, the FE render tests stop proving anything."""

    def _load(self, name):
        p = FIXTURES / name
        self.assertTrue(p.exists(), f"missing fixture {p}")
        return json.loads(p.read_text())

    def test_fixtures_match_the_served_shape(self):
        for name, rows_of in (
                ("since_report_growth_2026_09_21.json",
                 lambda d: d["rows"]),
                ("since_report_bonde_2026_09_21.json",
                 lambda d: [r for s in d["sections"].values() for r in s])):
            with self.subTest(fixture=name):
                d = self._load(name)
                s = d["since_report_summary"]
                self.assertEqual(set(s), SUMMARY_KEYS)
                self.assertEqual(s["date_basis"], SR.DATE_BASIS)
                rows = rows_of(d)
                self.assertTrue(rows)
                for r in rows:
                    self.assertEqual(set(r["since_report"]), set(SR._ROW_KEYS))
                json.dumps(d, allow_nan=False)

    def test_bonde_fixture_measured_block_is_the_served_one(self):
        """The Bonde capture was taken from the container, which runs main —
        so it came back WITHOUT `measured.steady` (WP-2 is not deployed yet).
        The field was filled in from this branch's own `bonde.measured_verdict()`,
        the same pure call `bonde.board()` makes at `bonde.py:789`, so the
        fixture is the post-deploy payload rather than a hand-written string.
        This pin is what keeps that honest: every key of the fixture's
        `measured` — the eight captured AND the filled `steady` — must still
        equal what the served code returns today.
        """
        from sepa import bonde as B
        d = self._load("since_report_bonde_2026_09_21.json")
        served = B.measured_verdict()
        self.assertEqual(set(d["measured"]), set(served))
        for k, v in served.items():
            with self.subTest(key=k):
                self.assertEqual(d["measured"][k], v)
        self.assertEqual(d["measured"]["steady"], B.steady_verdict())

    def test_NEGATIVE_bonde_fixture_steady_is_not_a_synthetic_string(self):
        """NEGATIVE — the FE render test may not be proved by a placeholder:
        the fixture's steady line has to be the real paragraph (long, dated,
        and carrying the MEASUREMENT framing), not 'served steady sentence'."""
        d = self._load("since_report_bonde_2026_09_21.json")
        s = d["measured"]["steady"]
        self.assertIsInstance(s, str)
        self.assertGreater(len(s), 500)
        self.assertIn("MEASURED 2026-09-21", s)
        self.assertIn("MEASUREMENT", s)
        self.assertNotIn("bounce", s)

    def test_NEGATIVE_no_fixture_row_is_known_with_a_null_return(self):
        for name, rows_of in (
                ("since_report_growth_2026_09_21.json", lambda d: d["rows"]),
                ("since_report_bonde_2026_09_21.json",
                 lambda d: [r for s in d["sections"].values() for r in s])):
            d = self._load(name)
            for r in rows_of(d):
                sr = r["since_report"]
                if sr["known"]:
                    self.assertIsNotNone(sr["pct"])
                else:
                    self.assertIsNone(sr["pct"])
                    self.assertIn(sr["reason"], SR.REASONS)


class LiveUnsettledBar(unittest.TestCase):
    """C1 on REAL DATA — the spec's §5.3 RTH/post-16:30 probe pair, replayed.

    The wall clock could not be moved into market hours in the session that
    built this column (the probe ran at 23:10 ET), so the live evidence was
    taken instead: at 23:10 ET on 2026-09-21, **31 `price_cache` documents were
    still carrying a today-dated last bar whose `cached_at` stamp fell inside
    the session** — written by the hourly `crontab:407` patch and never
    re-settled. Those bars are genuine in-progress prints, not closes.

    The frame below is one of them, copied bar-for-bar out of the live cache
    (AOUT, doc written 11:42:40 ET; note the today-bar's volume is a fifth of
    the days around it — a part-day print). The calendar row is AOUT's real
    one. Both readings reproduce the probe's served numbers exactly:

        session=rth        as_of 2026-09-18  last_close 16.42    sessions  9  +13.40%
        session=afterhours as_of 2026-09-21  last_close 16.635   sessions 10  +14.88%

    A 1.48pp difference on one name from one unsettled bar; the probe measured
    a sign flip (FANG +0.29% vs −2.13%) and a 17.7pp swing (INV) on the same
    31. `attach` is called with NO `session` argument here, so the whole
    wall-clock path runs: `P.trade_session(EW._today_et())` → the trim.
    """

    # (date, close, volume) — LIVE `price_cache` bars, 2026-09-21 23:10 ET.
    BARS = [
        ("2026-08-31T04:00:00", 10.57, 57647.831),
        ("2026-09-01T04:00:00", 10.0, 32178.304),
        ("2026-09-02T04:00:00", 9.95, 35667.466),
        ("2026-09-03T04:00:00", 10.01, 314951.658),
        ("2026-09-04T04:00:00", 14.48, 4431456.962),
        ("2026-09-08T04:00:00", 14.77, 833713.236),
        ("2026-09-09T04:00:00", 15.0, 187603.786),
        ("2026-09-10T04:00:00", 15.03, 110973.571),
        ("2026-09-11T04:00:00", 15.68, 172718.819),
        ("2026-09-14T04:00:00", 15.23, 86299.114),
        ("2026-09-15T04:00:00", 15.305, 95268.165),
        ("2026-09-16T04:00:00", 15.44, 67889.262),
        ("2026-09-17T04:00:00", 15.925, 71822.834),
        ("2026-09-18T04:00:00", 16.42, 125918.698),
        ("2026-09-21T04:00:00", 16.635, 32664.198),   # the UNSETTLED 11:42 print
    ]
    CAL = {"AOUT": {"date": "2026-09-03", "when": "AMC", "eps_actual": 0.03,
                    "eps_estimate": -0.24, "surprise_pct": 112.5}}
    TODAY = "2026-09-21"

    def _frame(self):
        return frame([c for _d, c, _v in self.BARS],
                     dates=[d for d, _c, _v in self.BARS],
                     vols=[v for _d, _c, v in self.BARS])

    def _at(self, hour, minute=0):
        """`attach` with NO session argument, at a frozen ET wall clock."""
        import datetime as dt
        from zoneinfo import ZoneInfo
        rows = [{"symbol": "AOUT"}]
        orig = EW._today_et
        try:
            EW._today_et = lambda: dt.datetime(
                2026, 9, 21, hour, minute, tzinfo=ZoneInfo("America/New_York"))
            summary = SR.attach(rows, reports=self.CAL,
                                frames={"AOUT": self._frame()},
                                today=self.TODAY)
        finally:
            EW._today_et = orig
        return rows[0]["since_report"], summary

    def test_the_live_partial_is_dropped_on_the_rth_wall_clock(self):
        cell, _ = self._at(11, 0)
        self.assertEqual(cell["anchor_date"], "2026-09-04")
        self.assertEqual(cell["anchor_close"], 14.48)
        self.assertEqual(cell["as_of"], "2026-09-18")
        self.assertEqual(cell["last_close"], 16.42)
        self.assertEqual(cell["sessions"], 9)
        self.assertEqual(round(cell["pct"], 2), 13.40)

    def test_the_settled_bar_is_kept_on_the_after_hours_wall_clock(self):
        cell, _ = self._at(17, 0)
        self.assertEqual(cell["as_of"], "2026-09-21")
        self.assertEqual(cell["last_close"], 16.635)
        self.assertEqual(cell["sessions"], 10)
        self.assertEqual(round(cell["pct"], 2), 14.88)

    def test_the_premarket_wall_clock_reads_like_rth(self):
        cell, _ = self._at(6, 30)
        self.assertEqual(cell["as_of"], "2026-09-18")
        self.assertEqual(cell["sessions"], 9)

    def test_the_probe_hour_2310_keeps_the_bar(self):
        """The hour the live probe actually ran — `closed`, bar kept."""
        cell, _ = self._at(23, 10)
        self.assertEqual(cell["as_of"], "2026-09-21")
        self.assertEqual(cell["sessions"], 10)

    def test_the_two_readings_differ_by_the_unsettled_bar_alone(self):
        rth, _ = self._at(11, 0)
        ah, _ = self._at(17, 0)
        self.assertEqual(rth["anchor_date"], ah["anchor_date"])
        self.assertEqual(rth["anchor_close"], ah["anchor_close"])
        self.assertEqual(ah["sessions"] - rth["sessions"], 1)
        self.assertAlmostEqual(round(ah["pct"] - rth["pct"], 2), 1.48, places=2)

    def test_NEGATIVE_no_wall_clock_serves_known_with_a_zero_length_window(self):
        """§5.3's live assertion, as a pin: on no clock may a served row be
        `known` without at least one closed session behind it."""
        for hour, minute in ((4, 5), (6, 30), (9, 45), (11, 0), (13, 30),
                             (15, 59), (16, 5), (17, 0), (20, 30), (23, 10)):
            with self.subTest(hour=hour, minute=minute):
                cell, summary = self._at(hour, minute)
                if cell["known"]:
                    self.assertGreaterEqual(cell["sessions"], 1)
                    self.assertTrue(math.isfinite(cell["pct"]))
                else:
                    self.assertIsNone(cell["pct"])
                self.assertEqual(summary["n"], 1)

    def test_NEGATIVE_the_as_of_never_runs_ahead_of_the_frames_own_bars(self):
        """Never overlay the live print (memory `cheetah_live_bar_overlay`):
        the served as_of is always a date the frame actually carries."""
        have = {d[:10] for d, _c, _v in self.BARS}
        for hour in (6, 11, 17, 23):
            cell, _ = self._at(hour, 0)
            self.assertIn(cell["as_of"], have)

    def test_the_frame_really_is_the_live_shape(self):
        """Guards the fixture itself: 04:00-stamped index, and a today-bar
        whose volume is a fraction of the sessions around it."""
        f = self._frame()
        self.assertTrue(all(t.hour == 4 for t in f.index))
        self.assertEqual(f.index[-1].date().isoformat(), self.TODAY)
        self.assertLess(float(f["volume"].iloc[-1]),
                        0.5 * float(f["volume"].iloc[-6:-1].mean()))


if __name__ == "__main__":                                      # pragma: no cover
    unittest.main()
