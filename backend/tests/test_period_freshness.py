"""Quarterly-cadence freshness — is the 13F data reporting the CURRENT period?

Every date here is passed in, never read from the clock, so quarter-boundary
behaviour is testable today instead of once every three months.

The negatives matter most: an empty cache, payloads with no period block, a
provider that has rolled only partway, and the day-after-deadline case that
must NOT fire (funds file across the whole deadline week).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from observability import period_freshness as pf  # noqa: E402


# ---------------------------------------------------------------------------
# pure date logic
# ---------------------------------------------------------------------------
def test_filing_deadline_is_the_sec_45_day_rule():
    """SEC Rule 13f-1: 45 calendar days after quarter end."""
    assert pf.filing_due(date(2026, 6, 30)) == date(2026, 8, 14)
    assert pf.filing_due(date(2026, 3, 31)) == date(2026, 5, 15)
    assert pf.filing_due(date(2026, 9, 30)) == date(2026, 11, 14)
    assert pf.filing_due(date(2025, 12, 31)) == date(2026, 2, 14)


def test_labels_and_quarter_of():
    assert pf.label_for(date(2026, 6, 30)) == "Q2 2026"
    assert pf.label_for(date(2026, 12, 31)) == "Q4 2026"
    assert pf.quarter_of(date(2026, 8, 16)) == (2026, 3)
    assert pf.quarter_of(date(2026, 1, 1)) == (2026, 1)


def test_expected_quarter_two_days_after_the_deadline_is_still_q1():
    """THE CASE THAT STARTED THIS. On 2026-08-16 the Q2 deadline (Aug 14) had
    just passed, so Q1 data is not yet late — the modal reading "Q1 2026" was
    correct, not a bug. Flagging here would cry wolf every quarter."""
    assert pf.expected_13f_quarter(date(2026, 8, 16)) == date(2026, 3, 31)


def test_expected_quarter_rolls_once_the_grace_period_is_over():
    # Aug 14 deadline + 21 days grace = Sep 4.
    assert pf.expected_13f_quarter(date(2026, 9, 3)) == date(2026, 3, 31)
    assert pf.expected_13f_quarter(date(2026, 9, 5)) == date(2026, 6, 30)


def test_expected_quarter_crosses_the_year_boundary():
    """In January the answer is still a PRIOR-YEAR quarter: Q4's own deadline
    (Feb 14) has not arrived, so Q3 is the newest one that is properly due."""
    assert pf.expected_13f_quarter(date(2026, 1, 20)) == date(2025, 9, 30)
    # Q4 2025 due Feb 14 + 21 days grace = Mar 7, so by Mar 10 it has rolled.
    assert pf.expected_13f_quarter(date(2026, 3, 6)) == date(2025, 9, 30)
    assert pf.expected_13f_quarter(date(2026, 3, 10)) == date(2025, 12, 31)
    assert pf.expected_13f_quarter(date(2026, 6, 20)) == date(2026, 3, 31)


def test_expected_quarter_never_returns_the_future():
    for d in (date(2026, 1, 1), date(2026, 5, 16), date(2026, 8, 16),
              date(2026, 12, 31)):
        assert pf.expected_13f_quarter(d) < d


def test_grace_period_is_configurable():
    """With no grace, the quarter rolls the day after the deadline."""
    assert pf.expected_13f_quarter(date(2026, 8, 16), grace_days=0) == date(2026, 6, 30)


# ---------------------------------------------------------------------------
# the cache audit
# ---------------------------------------------------------------------------
class _Coll:
    """Minimal stand-in for the Mongo collection: find().limit()."""

    def __init__(self, docs):
        self._docs = docs

    def find(self, *a, **kw):
        return self

    def limit(self, n):
        return iter(self._docs[:n])


def _doc(ticker, dominant, earliest=None, latest=None):
    return {"ticker": ticker, "payload": {"period": {
        "dominant": dominant,
        "earliest": earliest or dominant,
        "latest": latest or dominant,
    }}}


def test_audit_is_ok_when_the_provider_has_rolled():
    docs = [_doc(f"T{i}", "2026-06-30") for i in range(10)]
    res = pf.audit_whales_cache(today=date(2026, 9, 20), coll=_Coll(docs))
    assert res["ok"] is True
    assert res["expected_quarter"] == "2026-06-30"
    assert res["rolled_pct"] == 100.0


def test_audit_flags_a_provider_stuck_a_quarter_behind():
    docs = [_doc(f"T{i}", "2026-03-31") for i in range(10)]
    res = pf.audit_whales_cache(today=date(2026, 9, 20), coll=_Coll(docs))
    assert res["ok"] is False
    assert res["newest_seen"] == "2026-03-31"
    assert "only 0.0%" in res["detail"]
    assert "2026-08-14" in res["detail"]        # names the deadline it missed


def test_audit_passes_on_a_partial_roll_above_the_floor():
    """Small caps keep a tail of funds that never file, so demanding 100%
    would sit red forever. Half is the bar."""
    docs = ([_doc(f"N{i}", "2026-06-30") for i in range(6)]
            + [_doc(f"O{i}", "2026-03-31") for i in range(4)])
    res = pf.audit_whales_cache(today=date(2026, 9, 20), coll=_Coll(docs))
    assert res["ok"] is True
    assert res["rolled_pct"] == 60.0


def test_audit_fails_just_below_the_floor():
    docs = ([_doc(f"N{i}", "2026-06-30") for i in range(4)]
            + [_doc(f"O{i}", "2026-03-31") for i in range(6)])
    res = pf.audit_whales_cache(today=date(2026, 9, 20), coll=_Coll(docs))
    assert res["ok"] is False
    assert res["rolled_pct"] == 40.0


def test_audit_counts_payloads_that_MIX_quarters():
    """Mixing is its own defect: the modal sums bought/sold dollars across
    funds, so adding one fund's Q1 delta to another's Q2 delta yields a net
    inflow that describes no single period. APGE had 6 funds on Mar 31 and 4 on
    Jun 30 in one payload."""
    docs = [_doc("APGE", "2026-03-31", earliest="2026-03-31", latest="2026-06-30"),
            _doc("CLEAN", "2026-03-31")]
    res = pf.audit_whales_cache(today=date(2026, 9, 20), coll=_Coll(docs))
    assert res["mixed_quarter_payloads"] == 1
    assert res["mixed_pct"] == 50.0


def test_audit_treats_a_newer_quarter_than_expected_as_rolled():
    """The provider running AHEAD is never a failure."""
    docs = [_doc(f"T{i}", "2026-09-30") for i in range(5)]
    res = pf.audit_whales_cache(today=date(2026, 9, 20), coll=_Coll(docs))
    assert res["ok"] is True


def test_audit_reports_cleanly_on_an_empty_cache():
    res = pf.audit_whales_cache(today=date(2026, 9, 20), coll=_Coll([]))
    assert res["ok"] is False
    assert "no cached payloads" in res["reason"]


def test_audit_skips_payloads_with_no_period_block():
    docs = [{"ticker": "X", "payload": {}},
            {"ticker": "Y", "payload": {"period": None}},
            _doc("Z", "2026-06-30")]
    res = pf.audit_whales_cache(today=date(2026, 9, 20), coll=_Coll(docs))
    assert res["sampled"] == 1
    assert res["ok"] is True


def test_audit_survives_a_broken_collection():
    class _Boom:
        def find(self, *a, **kw):
            raise RuntimeError("mongo down")

    res = pf.audit_whales_cache(today=date(2026, 9, 20), coll=_Boom())
    assert res["ok"] is False
    assert "cache read failed" in res["reason"]


def test_report_wraps_the_checks_with_an_all_ok_flag():
    docs = [_doc(f"T{i}", "2026-03-31") for i in range(5)]
    import unittest.mock as mock
    with mock.patch.object(pf, "audit_whales_cache",
                           return_value={"ok": False, "detail": "stuck"}):
        rep = pf.report(today=date(2026, 9, 20))
    assert rep["all_ok"] is False
    assert rep["checks"][0]["name"] == "13f_institutional_holders"
    assert "45 days" in rep["note"]


# ---------------------------------------------------------------------------
# the health-audit integration
# ---------------------------------------------------------------------------
def test_health_check_is_warn_never_critical(monkeypatch):
    """A provider lagging a quarter must never push the phone — Ajay's push
    keep-set is three kinds and this is not one of them. health_audit only
    alerts on CRITICAL, so the severity is the guard."""
    from observability import health_audit as ha

    monkeypatch.setattr(pf, "audit_whales_cache",
                        lambda *a, **kw: {"ok": False, "detail": "stuck on Q1",
                                          "rolled_pct": 0.0})
    res = ha.check_13f_quarter_current()
    assert res["ok"] is False
    assert res["severity"] == ha.WARN
    assert res["severity"] != ha.CRITICAL


def test_health_check_is_registered_in_the_battery():
    from observability import health_audit as ha
    assert ha.check_13f_quarter_current in ha.CHECKS


def test_health_check_degrades_to_warn_when_the_module_explodes(monkeypatch):
    from observability import health_audit as ha

    def _boom(*a, **kw):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(pf, "audit_whales_cache", _boom)
    res = ha.check_13f_quarter_current()
    assert res["ok"] is False and res["severity"] == ha.WARN


def test_monthly_cron_entry_exists():
    """The rule Ajay asked for is only real if it is scheduled."""
    crontab = (Path(__file__).resolve().parents[1] / "crontab").read_text()
    line = [ln for ln in crontab.splitlines()
            if "observability.period_freshness" in ln and not ln.startswith("#")]
    assert len(line) == 1, "expected exactly one scheduled period-freshness run"
    fields = line[0].split()
    assert fields[2] == "1", "should run on the 1st of the month"
    assert fields[3] == "*" and fields[4] == "*", "should run every month, any weekday"
