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
