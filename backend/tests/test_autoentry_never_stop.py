"""Paper/sim never auto-stops auto-entry — the daily cap is lifted and a
risk-off gauge no longer halts entries; live keeps BOTH guardrails. The
per-order safety gates (MAX_POSITIONS, stops, no-average-up, earnings) are NOT
touched by this — they still apply in every mode."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.auto_entry as AE


def test_entry_cap_unlimited_in_paper_book_cap_in_live():
    assert AE.entry_cap(True) == math.inf                       # paper/sim
    assert AE.entry_cap(False) == float(AE.MAX_AUTO_ENTRIES_PER_DAY)  # live


def test_gauge_allows_bypasses_risk_off_only_when_never_stop():
    # paper/sim: risk-off does NOT stop entries
    assert AE.gauge_allows(True, "risk_off") is True
    assert AE.gauge_allows(True, "constructive") is True
    # live: risk-off halts; other states pass
    assert AE.gauge_allows(False, "risk_off") is False
    assert AE.gauge_allows(False, "caution") is True
    assert AE.gauge_allows(False, "constructive") is True


def test_never_auto_stop_is_paper_sim_true_live_false(monkeypatch):
    for mode in ("paper", "sim"):
        monkeypatch.setattr(AE, "_broker_mode", lambda m=mode: m)
        assert AE._never_auto_stop() is True
    monkeypatch.setattr(AE, "_broker_mode", lambda: "live")
    assert AE._never_auto_stop() is False


def test_never_auto_stop_fails_safe_to_capped(monkeypatch):
    def _boom():
        raise RuntimeError("broker down")
    monkeypatch.setattr(AE, "_broker_mode", _boom)
    assert AE._never_auto_stop() is False        # fail safe → keep the live cap


def test_daily_cap_actually_lifts_in_paper():
    # with the cap lifted, an entries_today well past the book cap still passes
    entries_today = AE.MAX_AUTO_ENTRIES_PER_DAY + 50
    assert (entries_today < AE.entry_cap(True)) is True      # paper: keeps going
    assert (entries_today < AE.entry_cap(False)) is False    # live: stopped
