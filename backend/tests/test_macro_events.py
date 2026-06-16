"""Macro-event overlay — imminent FOMC/CPI/jobs/PCE in the holding advice + gauge.

Ajay 2026-06-16: "consider macro news that would impact the stock in the advice…
if tomorrow is FOMC readout consider it… allude to it in the Market Gauge hold vs
sell." Like the earnings-quality overlay, this is INFORMATIONAL — a binary-event
heads-up that does NOT change the price-based verdict. These lock the window /
tier filtering, the 'today/tomorrow' labels, the heads-up strings, and the
soft-fail.

Run in the backend venv (py3.9):
  cd backend && .venv/bin/python -m pytest tests/test_macro_events.py -q
"""
import datetime
import importlib.util
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import macro_calendar as mc

# diagnosis.py STANDALONE — the `portfolio` package trips a py3.9 annotation-eval
# quirk (same reason test_diagnosis_brain.py / test_portfolio_diagnosis.py do this).
_PATH = os.path.join(os.path.dirname(__file__), "..", "portfolio", "diagnosis.py")
_spec = importlib.util.spec_from_file_location("diagnosis_macro_mod", _PATH)
D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(D)


def _cal(events):
    return {"macro": events}


# ── imminent_events: window + tier + day labels ──────────────────────────────

def test_imminent_filters_window_tier_and_labels(monkeypatch):
    monkeypatch.setattr(mc, "_today_et", lambda: datetime.date(2026, 6, 16))
    events = [
        {"date": "2026-06-16", "kind": "cpi", "tier": 1, "label": "CPI"},            # today
        {"date": "2026-06-17", "kind": "fomc", "tier": 1, "label": "FOMC decision"}, # tomorrow
        {"date": "2026-06-19", "kind": "jobs", "tier": 1, "label": "Jobs report"},   # in 3 days
        {"date": "2026-06-30", "kind": "pce", "tier": 1, "label": "Core PCE"},        # outside 5d
        {"date": "2026-06-17", "kind": "ism", "tier": 2, "label": "ISM"},             # tier 2
    ]
    monkeypatch.setattr(mc, "get_macro_calendar", lambda *a, **k: _cal(events))
    out = mc.imminent_events(within_days=5, max_tier=1)
    assert [e["kind"] for e in out] == ["cpi", "fomc", "jobs"]   # window + tier + sorted
    assert out[0]["when_label"] == "today" and out[0]["days_until"] == 0
    assert out[1]["when_label"] == "tomorrow"
    assert out[2]["when_label"] == "in 3 days"


def test_imminent_soft_fails_on_calendar_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("FRED down")
    monkeypatch.setattr(mc, "get_macro_calendar", boom)
    assert mc.imminent_events() == []          # must not raise


# ── the heads-up strings (informational, mirrors eq_sell_risk) ───────────────

def test_heads_up_strings_and_sector_sensitivity():
    events = [{"date": "2026-06-17", "kind": "fomc", "tier": 1,
               "label": "FOMC decision", "when_label": "tomorrow", "days_until": 1}]
    out = D._macro_events_heads_up(events, "semis_ai")
    assert any("FOMC decision tomorrow" in s for s in out)
    assert any("binary macro event" in s for s in out)
    assert any("rate/inflation-sensitive" in s for s in out)   # semis_ai + fomc


def test_heads_up_no_sector_line_for_insensitive_sector():
    events = [{"date": "2026-06-17", "kind": "fomc", "tier": 1,
               "label": "FOMC decision", "when_label": "tomorrow"}]
    assert not any("rate/inflation-sensitive" in s
                   for s in D._macro_events_heads_up(events, "energy"))


def test_heads_up_empty_when_no_events():
    assert D._macro_events_heads_up([], "semis_ai") == []


# ── gauge outlook surfaces the event in its hold-vs-add watch list ───────────

def test_gauge_outlook_surfaces_imminent_event(monkeypatch):
    from sepa import market_gauge as mg
    monkeypatch.setattr(mc, "imminent_events",
                        lambda within_days=5, max_tier=1: [
                            {"label": "FOMC decision", "when_label": "tomorrow",
                             "date": "2026-06-17", "kind": "fomc", "tier": 1, "days_until": 1}])
    out = mg._outlook(70, "constructive", [], None, None)
    assert any("📅" in w and "FOMC" in w for w in out.get("watch", []))


def test_gauge_outlook_clean_when_no_events(monkeypatch):
    from sepa import market_gauge as mg
    monkeypatch.setattr(mc, "imminent_events", lambda within_days=5, max_tier=1: [])
    out = mg._outlook(70, "constructive", [], None, None)
    assert not any("📅" in w for w in out.get("watch", []))
