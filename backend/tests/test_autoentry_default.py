"""Auto-entry DEFAULT is mode-aware: ON in paper/sim, OFF in live — and a
stored explicit value always wins. The master `armed` switch stays default-off
in every mode (so a default-on auto-entry still places no order until armed)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.exit_engine as EE


class _FakeColl:
    def __init__(self, doc):
        self._doc = doc

    def find_one(self, *a, **k):
        return self._doc


class _FakeDB:
    def __init__(self, doc):
        self.trading_config = _FakeColl(doc)


def test_default_on_in_paper_and_sim(monkeypatch):
    monkeypatch.setattr(EE, "_db", lambda: None)        # no stored doc → default path
    for mode in ("paper", "sim"):
        monkeypatch.setattr(EE, "_broker_mode", lambda m=mode: m)
        assert EE._auto_entry_default() is True
        assert EE.get_config()["auto_entry"] is True


def test_default_off_in_live(monkeypatch):
    monkeypatch.setattr(EE, "_db", lambda: None)
    monkeypatch.setattr(EE, "_broker_mode", lambda: "live")
    assert EE._auto_entry_default() is False
    assert EE.get_config()["auto_entry"] is False       # live never auto-buys by default


def test_explicit_stored_value_wins_over_mode_default(monkeypatch):
    monkeypatch.setattr(EE, "_broker_mode", lambda: "paper")
    # explicitly OFF in paper → respected (not overridden to default-on)
    monkeypatch.setattr(EE, "_db", lambda: _FakeDB({"auto_entry": False}))
    assert EE.get_config()["auto_entry"] is False
    # explicitly ON in live → respected (user opted in)
    monkeypatch.setattr(EE, "_broker_mode", lambda: "live")
    monkeypatch.setattr(EE, "_db", lambda: _FakeDB({"auto_entry": True}))
    assert EE.get_config()["auto_entry"] is True


def test_armed_stays_default_off_regardless_of_mode(monkeypatch):
    monkeypatch.setattr(EE, "_db", lambda: None)
    monkeypatch.setattr(EE, "_broker_mode", lambda: "paper")
    cfg = EE.get_config()
    assert cfg["armed"] is False        # master gate is still off until the user arms
    assert cfg["auto_entry"] is True    # but the preference defaults on in paper


def test_broker_mode_failure_fails_safe_off(monkeypatch):
    def _boom():
        raise RuntimeError("broker down")
    monkeypatch.setattr(EE, "_broker_mode", _boom)
    assert EE._auto_entry_default() is False
