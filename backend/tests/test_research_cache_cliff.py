"""The 2026-09-01 research-cache cliff — one missed Sunday refresh emptied
every Bonde-gated board (Deep Demand / Gabbar / Under Value) overnight:
3,642 fresh Monday evening, 21 by Tuesday 6am, because the whole cache was
ONE batch and the TTL was only one day longer than the refresh cadence.

Locks: the TTL margin, the predictive needs_refresh decision, the
predictive health warning, and the crontab catch-up line itself.
"""
import sys
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sepa import research  # noqa: E402


def test_ttl_leaves_a_full_missed_sunday_of_margin():
    # Weekly cadence + 8-day TTL was a one-miss cliff. The TTL must cover
    # at least TWO refresh intervals (14 days) with margin.
    assert research.CACHE_TTL_SEC >= 15 * 24 * 3600


# ── needs_refresh (pure over status()) ──────────────────────────────────────
def _with_status(st):
    return mock.patch.object(research, "status", return_value=st)


def test_healthy_cache_skips_the_catchup():
    with _with_status({"available": True, "total": 3600, "fresh": 3500,
                       "expiring_48h": 100}):
        run, why = research.needs_refresh()
    assert run is False
    assert "healthy" in why


def test_the_cliff_shape_fires_the_catchup_BEFORE_expiry():
    # Monday after a missed Sunday: everything still FRESH, but the whole
    # batch crosses the TTL within 48h. The old reactive read said "ok"
    # here — this is the exact state that must fire.
    with _with_status({"available": True, "total": 3600, "fresh": 3600,
                       "expiring_48h": 3600}):
        run, why = research.needs_refresh()
    assert run is True
    assert "survive" in why


def test_already_dead_cache_fires():
    with _with_status({"available": True, "total": 3667, "fresh": 21,
                       "expiring_48h": 0}):
        run, _ = research.needs_refresh()
    assert run is True


def test_empty_and_unavailable_fire():
    with _with_status({"available": False, "reason": "Mongo down"}):
        assert research.needs_refresh()[0] is True
    with _with_status({"available": True, "total": 0, "fresh": 0}):
        assert research.needs_refresh()[0] is True


def test_threshold_boundary_is_surviving_fraction_not_fresh_fraction():
    # 80% fresh but half of that dies within 48h -> 40% surviving -> fire.
    with _with_status({"available": True, "total": 1000, "fresh": 800,
                       "expiring_48h": 400}):
        assert research.needs_refresh()[0] is True
    # Same fresh count, nothing expiring -> 80% surviving -> skip.
    with _with_status({"available": True, "total": 1000, "fresh": 800,
                       "expiring_48h": 0}):
        assert research.needs_refresh()[0] is False


# ── the predictive health warning ───────────────────────────────────────────
def test_health_check_warns_on_the_expiring_cliff():
    from observability import health_audit as ha
    st = {"available": True, "total": 3600, "fresh": 3600,
          "expiring_48h": 3400}
    with mock.patch.object(research, "status", return_value=st):
        res = ha.check_research_cache_age()
    assert res["ok"] is False and res["severity"] == ha.WARN
    assert "expire within 48h" in res["detail"]


def test_health_check_still_ok_when_genuinely_healthy():
    from observability import health_audit as ha
    st = {"available": True, "total": 3600, "fresh": 3400,
          "expiring_48h": 200}
    with mock.patch.object(research, "status", return_value=st):
        res = ha.check_research_cache_age()
    assert res["ok"] is True


# ── source guards: the crontab line and the CLI flag must exist ────────────
def test_crontab_has_the_nightly_catchup_guard():
    crontab = (Path(__file__).resolve().parents[1] / "crontab").read_text()
    assert "research-refresh --mode broad --only-if-stale" in crontab
    line = next(l for l in crontab.splitlines()
                if "--only-if-stale" in l and not l.startswith("#"))
    assert "1-6" in line, "catch-up must run Mon-Sat (Sunday has the full run)"


def test_cli_wires_the_flag_to_the_decision():
    src = (Path(__file__).resolve().parents[1] / "sepa" / "cli.py").read_text()
    assert "--only-if-stale" in src
    assert "research.needs_refresh()" in src
