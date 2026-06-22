"""Caution market -> difficult regime downshift (2026-06-22).

Minervini p.311: in a difficult / non-constructive tape, tighten stops
(7-8% -> 5-6%) and take smaller profits (15-20% -> 10-12%). Map BOTH 'risk_off'
AND 'caution' to the 'difficult' regime so a caution day auto-downshifts; only
'constructive' stays 'normal'. The 1-min engine tick means a later re-entry on a
constructive turn is never missed, so standing tighter on caution costs nothing.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trading import exit_engine, risk_rules


def _gauge(monkeypatch, state):
    import sepa.market_gauge as mg
    monkeypatch.setattr(mg, "get_gauge", lambda **kw: {"state": state, "score": 50})


# ── the mapping ───────────────────────────────────────────────────────────
def test_caution_maps_to_difficult(monkeypatch):
    _gauge(monkeypatch, "caution")
    assert exit_engine.regime() == "difficult"


def test_risk_off_still_difficult(monkeypatch):
    _gauge(monkeypatch, "risk_off")
    assert exit_engine.regime() == "difficult"


def test_constructive_is_normal(monkeypatch):
    _gauge(monkeypatch, "constructive")
    assert exit_engine.regime() == "normal"


def test_missing_gauge_defaults_normal(monkeypatch):
    import sepa.market_gauge as mg
    monkeypatch.setattr(mg, "get_gauge", lambda **kw: None)   # negative: never crash, default normal
    assert exit_engine.regime() == "normal"


# ── the downshift it produces (p.311) ─────────────────────────────────────
def test_difficult_tightens_stop_and_shrinks_target():
    normal = risk_rules.initial_stop(100.0, "normal")
    difficult = risk_rules.initial_stop(100.0, "difficult")
    # stop TIGHTENS on caution/difficult (7% -> 6% band), never widens (p.308-309)
    assert difficult.stop_pct < normal.stop_pct
    assert difficult.stop_pct <= 6.0 and normal.stop_pct >= 7.0
    # profit target SHRINKS (15-20% -> 10-12%)
    nt = risk_rules.profit_target(100.0, normal.stop_pct, "normal")
    dt = risk_rules.profit_target(100.0, difficult.stop_pct, "difficult")
    assert dt["target_pct"] <= 12.0 < nt["target_pct"]
