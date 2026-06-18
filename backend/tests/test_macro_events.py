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


# ── FOMC from the authoritative Fed schedule (NOT FRED's padded rows) ─────────
# FRED's "FOMC Press Release" has no firm date — it pads a row onto every day of
# the window, so it (a) can't pin the real meeting day and (b) gets dropped by
# the no-data-padding filter. We source the real decision day from the Fed's
# published calendar (FOMC_DECISION_DATES, federalreserve.gov). These lock that.

def test_fomc_decision_dates_are_sane_and_sourced():
    # The constant must exist, be ISO dates, ascending, and cover the live year.
    dates = mc.FOMC_DECISION_DATES
    assert len(dates) >= 16                                  # ≥2 years × 8 meetings
    parsed = [datetime.datetime.strptime(d, "%Y-%m-%d").date() for d in dates]
    assert parsed == sorted(parsed)                          # chronological
    assert any(d.year == 2026 for d in parsed)               # current year present
    assert "2026-06-17" in dates                             # the June-2026 decision day


def test_fomc_event_in_window_is_tier1_today(monkeypatch):
    # ET window 'today' = a real decision day → one tier-1 FOMC event for that day.
    monkeypatch.setattr(mc, "_today_et", lambda: datetime.date(2026, 6, 17))
    ev = mc._fomc_events(14)
    assert [e["date"] for e in ev] == ["2026-06-17"]
    assert ev[0]["kind"] == "fomc" and ev[0]["tier"] == 1
    assert ev[0]["label"] == "FOMC decision"
    assert "Federal Reserve" in ev[0]["source"]              # sourced, not invented


def test_fomc_event_out_of_window_is_empty(monkeypatch):
    # No FOMC in the next 5 days (next is weeks out) → empty, never a crash (negative).
    monkeypatch.setattr(mc, "_today_et", lambda: datetime.date(2026, 6, 20))
    assert mc._fomc_events(5) == []


def test_fomc_window_is_ET_not_UTC(monkeypatch):
    # Boundary: evening of the decision day, UTC has rolled to the next date but
    # ET is still the decision day — the event must still show as 'today'.
    monkeypatch.setattr(mc, "_today_et", lambda: datetime.date(2026, 6, 17))
    out = mc._fomc_events(14)
    assert out and out[0]["date"] == "2026-06-17"


def test_fred_fomc_padding_rows_are_skipped(monkeypatch):
    # FRED returns FOMC Press Release padded onto every day + a real CPI row.
    # The CPI is kept; the FOMC padding is skipped (sourced from the schedule).
    import sepa.fred
    monkeypatch.setattr(sepa.fred, "api_key", lambda: "testkey")
    today = mc.datetime.now(mc.timezone.utc).date()
    rows = [{"date": str(today), "release_name": "Consumer Price Index"}]
    for i in range(6):                                       # 6 days of FOMC padding
        rows.append({"date": str(today + mc.timedelta(days=i)),
                     "release_name": "FOMC Press Release"})

    class _Resp:
        status_code = 200
        def json(self):
            return {"release_dates": rows}

    monkeypatch.setattr("requests.get", lambda *a, **k: _Resp())
    out = mc._fred_releases(14)
    kinds = [e["kind"] for e in out]
    assert "cpi" in kinds                                    # real release kept
    assert "fomc" not in kinds                               # FRED padding dropped


def test_compute_merges_fomc_with_fred(monkeypatch):
    # The merged calendar carries BOTH the FRED releases and the schedule FOMC,
    # date-sorted, with FOMC as the nearest tier-1 mover.
    monkeypatch.setattr(mc, "_today_et", lambda: datetime.date(2026, 6, 16))
    monkeypatch.setattr(mc, "_fred_releases", lambda days: [
        {"date": "2026-06-18", "kind": "cpi", "tier": 1, "label": "CPI", "source": "FRED"}])
    monkeypatch.setattr(mc, "_earnings_ahead", lambda days: [])
    mc._CACHE["data"] = None
    d = mc.compute(14)
    pairs = [(e["date"], e["kind"]) for e in d["macro"]]
    assert ("2026-06-17", "fomc") in pairs                   # FOMC injected
    assert ("2026-06-18", "cpi") in pairs                    # FRED kept
    assert pairs == sorted(pairs)                            # date-sorted
    assert d["next_tier1"]["kind"] == "fomc"                 # 6/17 before 6/18
