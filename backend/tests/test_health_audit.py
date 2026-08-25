"""Tests for the health-audit fail-safe observability battery.

Pure — swaps the CHECKS list / stubs the sinks so we assert aggregation,
severity rollup, and crash-resilience without Mongo / push / network.
"""
import time

import pytest

from observability import health_audit as ha


@pytest.fixture(autouse=True)
def _no_side_effects(monkeypatch):
    # Never touch disk / Mongo / network / push during tests.
    monkeypatch.setattr(ha, "_persist", lambda a: None)
    monkeypatch.setattr(ha, "_ping_healthchecks", lambda s: None)
    monkeypatch.setattr(ha, "_post_webhook", lambda a: None)
    monkeypatch.setattr(ha, "_push", lambda *a, **k: None)
    monkeypatch.setattr(ha, "install_file_handler", lambda *a, **k: None)


def test_age_hours():
    assert ha._age_hours(time.time() - 3600) == pytest.approx(1.0, abs=0.1)
    assert ha._age_hours(None) is None
    assert ha._age_hours("nope") is None


def test_status_ok_when_all_pass(monkeypatch):
    monkeypatch.setattr(ha, "CHECKS", [lambda: ha._ok("a", "x"), lambda: ha._ok("b", "x")])
    out = ha.run_audit(alert=False)
    assert out["status"] == "ok"
    assert out["n_critical"] == 0 and out["n_warn"] == 0
    assert out["n_checks"] == 2


def test_status_critical_dominates(monkeypatch):
    monkeypatch.setattr(ha, "CHECKS", [
        lambda: ha._fail("scan", "data", ha.CRITICAL, "stale"),
        lambda: ha._fail("macro", "data", ha.WARN, "slow"),
        lambda: ha._ok("disk", "infra"),
    ])
    out = ha.run_audit(alert=False)
    assert out["status"] == "critical"
    assert out["n_critical"] == 1 and out["n_warn"] == 1


def test_status_degraded_on_warn_only(monkeypatch):
    monkeypatch.setattr(ha, "CHECKS", [
        lambda: ha._fail("macro", "data", ha.WARN, "slow"),
        lambda: ha._ok("disk", "infra"),
    ])
    out = ha.run_audit(alert=False)
    assert out["status"] == "degraded"


def test_audit_survives_a_crashing_check(monkeypatch):
    def boom():
        raise ValueError("feed down")
    monkeypatch.setattr(ha, "CHECKS", [boom, lambda: ha._ok("b", "x")])
    out = ha.run_audit(alert=False)
    assert out["n_checks"] == 2                      # crash recorded as a check
    assert any(not c["ok"] for c in out["checks"])   # ...and marked failing
    assert out["status"] in ("degraded", "critical")


def test_alert_dedupes_per_day(monkeypatch):
    pushed = []
    monkeypatch.setattr(ha, "_push", lambda title, body: pushed.append(title))
    monkeypatch.setattr(ha, "_load_state", lambda: {})
    saved = {}
    monkeypatch.setattr(ha, "_save_state", lambda s: saved.update(s))
    crit = [ha._fail("scan", "data", ha.CRITICAL, "stale")]
    ha._maybe_alert({"status": "critical", "n_critical": 1, "n_warn": 0, "n_checks": 9}, crit, digest=False)
    assert len(pushed) == 1                          # fired once
    # second run same day, state already has today -> no push
    today = ha._now_et().strftime("%Y-%m-%d")
    monkeypatch.setattr(ha, "_load_state", lambda: {"scan": today})
    pushed.clear()
    ha._maybe_alert({"status": "critical", "n_critical": 1, "n_warn": 0, "n_checks": 9}, crit, digest=False)
    assert pushed == []                              # de-duped


def test_digest_pushes_even_when_green(monkeypatch):
    pushed = []
    monkeypatch.setattr(ha, "_push", lambda title, body: pushed.append((title, body)))
    monkeypatch.setattr(ha, "_load_state", lambda: {})
    ha._maybe_alert({"status": "ok", "n_critical": 0, "n_warn": 0, "n_checks": 9}, [], digest=True)
    assert len(pushed) == 1 and "digest" in pushed[0][0]


def test_check_helpers_shape():
    ok = ha._ok("n", "c", "d", 5)
    bad = ha._fail("n", "c", ha.CRITICAL, "d", 5)
    assert ok["ok"] is True and ok["severity"] is None
    assert bad["ok"] is False and bad["severity"] == ha.CRITICAL


# ── the four silent-scan checks (added 2026-08-25) ──────────────────────────
# Why: the pullback artifact sat 96h stale while the audit WARNed into a void;
# Ajay: "make sure there is a count indication ... some scans failed silently."
class _FakeColl:
    def __init__(self, docs=None):
        self.docs = docs or []

    def count_documents(self, q):
        return len(self.docs)

    def find_one(self, q, **kw):
        return self.docs[0] if self.docs else None


class _FakeDB:
    def __init__(self, **colls):
        self._colls = colls

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self._colls.get(name, _FakeColl())


def _weekday_noon(monkeypatch):
    import datetime as _dt
    class _ET(_dt.datetime):
        pass
    fake = _dt.datetime(2026, 8, 25, 12, 0)  # Tuesday, mid-session
    monkeypatch.setattr(ha, "_now_et", lambda: fake)
    return fake


def test_demand_scan_check_warns_when_no_runs_recorded(monkeypatch):
    _weekday_noon(monkeypatch)
    monkeypatch.setattr(ha, "_mongo_db", lambda: _FakeDB(demand_board_runs=_FakeColl([])))
    r = ha.check_demand_scan_fresh()
    assert r["ok"] is False and r["severity"] == ha.WARN
    assert "silently down" in r["detail"]


def test_demand_scan_check_ok_with_recent_run(monkeypatch):
    _weekday_noon(monkeypatch)
    monkeypatch.setattr(ha, "_mongo_db",
                        lambda: _FakeDB(demand_board_runs=_FakeColl([{"et_date": "2026-08-25"}])))
    assert ha.check_demand_scan_fresh()["ok"] is True


def test_trade_flash_check_passes_vacuously_when_market_closed(monkeypatch):
    import datetime as _dt
    monkeypatch.setattr(ha, "_now_et", lambda: _dt.datetime(2026, 8, 23, 12, 0))  # Sunday
    r = ha.check_trade_flash_heartbeat()
    assert r["ok"] is True and "market closed" in r["detail"]


def test_trade_flash_check_warns_on_stale_heartbeat_in_session(monkeypatch):
    _weekday_noon(monkeypatch)
    stale = {"name": "trade_flash", "ts": time.time() - 45 * 60}
    monkeypatch.setattr(ha, "_mongo_db",
                        lambda: _FakeDB(engine_heartbeat=_FakeColl([stale])))
    r = ha.check_trade_flash_heartbeat()
    assert r["ok"] is False and r["severity"] == ha.WARN


def test_trade_flash_check_ok_on_fresh_heartbeat(monkeypatch):
    _weekday_noon(monkeypatch)
    fresh = {"name": "trade_flash", "ts": time.time() - 3 * 60}
    monkeypatch.setattr(ha, "_mongo_db",
                        lambda: _FakeDB(engine_heartbeat=_FakeColl([fresh])))
    assert ha.check_trade_flash_heartbeat()["ok"] is True


def test_zero_dte_check_warns_when_todays_run_missing(monkeypatch):
    _weekday_noon(monkeypatch)
    monkeypatch.setattr(ha, "_mongo_db", lambda: _FakeDB(zero_dte_runs=_FakeColl([])))
    r = ha.check_zero_dte_ledger()
    assert r["ok"] is False and r["severity"] == ha.WARN


def test_zero_dte_check_quiet_before_the_morning_run(monkeypatch):
    import datetime as _dt
    monkeypatch.setattr(ha, "_now_et", lambda: _dt.datetime(2026, 8, 25, 9, 30))
    assert ha.check_zero_dte_ledger()["ok"] is True


def test_research_cache_check_warns_when_mostly_stale(monkeypatch):
    import sepa.research as research
    monkeypatch.setattr(research, "status",
                        lambda: {"available": True, "total": 1000, "fresh": 100})
    r = ha.check_research_cache_age()
    assert r["ok"] is False and r["severity"] == ha.WARN
    assert "research-refresh may be failing" in r["detail"]


def test_research_cache_check_ok_when_fresh(monkeypatch):
    import sepa.research as research
    monkeypatch.setattr(research, "status",
                        lambda: {"available": True, "total": 1000, "fresh": 950})
    assert ha.check_research_cache_age()["ok"] is True
