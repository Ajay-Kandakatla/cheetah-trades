"""Tests for the pivot-alert fixes (backend/sepa/pivot_alerts.py), 2026-06-09:

  1. AT_PIVOT fires ONLY for names in the buyable set (`is_buyable`); a name at
     its pivot but not buyable (e.g. +4% past pivot) is suppressed — "don't
     report it if it's not buyable."
  2. Dedup is recorded on ATTEMPT, not on delivery success — so a transient
     push miss (0 devices reached) can't make the next tick re-fire the same
     name. Once per symbol/kind/ET-day.
  3. APPROACHING (pre-breakout buy-stop) still fires without a buyable gate.
  4. ETFs are skipped.

All synthetic / monkeypatched — no network, no Mongo (in-proc _mem dedup).
"""
import pytest

from sepa import pivot_alerts as pa
from sepa import at_pivot, scanner, notify


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    pa._mem.clear()
    monkeypatch.setattr(pa, "_coll", lambda: None)      # use in-proc _mem dedup
    yield
    pa._mem.clear()


AT_PIVOT_BUYABLE = {"symbol": "AAA", "is_etf": False, "bucket": "at_pivot",
                    "decision": "ENTER", "pivot": 50.0, "live_price": 50.4,
                    "rs_rank": 95, "dist_pct": 0.8}
AT_PIVOT_NOT_BUYABLE = {"symbol": "BBB", "is_etf": False, "bucket": "at_pivot",
                        "decision": "ENTER", "pivot": 60.0, "live_price": 62.4,
                        "rs_rank": 97, "dist_pct": 4.0}        # +4% → not buyable
APPROACHING = {"symbol": "CCC", "is_etf": False, "bucket": "approaching",
               "decision": "WAIT", "pivot": 70.0, "live_price": 69.0,
               "rs_rank": 90, "dist_pct": -1.4}


def _latest(buyable_syms):
    return {"all_results": [{"symbol": s, "is_buyable": True} for s in buyable_syms]}


def _patch(monkeypatch, ap_rows, buyable_syms, send_ret=True, sink=None):
    monkeypatch.setattr(at_pivot, "get_at_pivot", lambda force=False: {"rows": ap_rows})
    monkeypatch.setattr(scanner, "load_latest", lambda: _latest(buyable_syms))

    def _send(**k):
        if sink is not None:
            sink.append(k.get("ticker"))
        return send_ret() if callable(send_ret) else send_ret
    monkeypatch.setattr(notify, "send_alert", _send)


def test_at_pivot_fires_only_for_buyable(monkeypatch):
    sent = []
    _patch(monkeypatch, [AT_PIVOT_BUYABLE, AT_PIVOT_NOT_BUYABLE], ["AAA"], sink=sent)
    out = pa.check_pivot_alerts()
    assert sent == ["AAA"]                                # BBB (not buyable) suppressed
    assert "BBB" in out["suppressed_not_buyable"]
    assert any(k.startswith("AAA:AT_PIVOT") for k in out["fired"])


def test_dedup_marks_on_attempt_even_when_delivery_fails(monkeypatch):
    attempts = {"n": 0}

    def _fail():
        attempts["n"] += 1
        return False                                     # 0 devices reached
    _patch(monkeypatch, [AT_PIVOT_BUYABLE], ["AAA"], send_ret=_fail)
    out1 = pa.check_pivot_alerts()
    out2 = pa.check_pivot_alerts()
    assert attempts["n"] == 1                            # attempted ONCE across two runs
    assert out1["delivery_failed"] and not out1["fired"]
    assert any(k.startswith("AAA:AT_PIVOT") for k in out2["skipped"])  # deduped 2nd run


def test_approaching_fires_without_buyable_gate(monkeypatch):
    sent = []
    _patch(monkeypatch, [APPROACHING], [], sink=sent)    # nothing buyable
    pa.check_pivot_alerts()
    assert sent == ["CCC"]                               # pre-breakout buy-stop still fires


def test_etf_at_pivot_is_skipped(monkeypatch):
    etf = {**AT_PIVOT_BUYABLE, "symbol": "SPY", "is_etf": True}
    sent = []
    _patch(monkeypatch, [etf], ["SPY"], sink=sent)
    pa.check_pivot_alerts()
    assert sent == []


def test_dry_run_reports_without_sending(monkeypatch):
    sent = []
    _patch(monkeypatch, [AT_PIVOT_BUYABLE], ["AAA"], sink=sent)
    out = pa.check_pivot_alerts(dry_run=True)
    assert sent == []                                    # nothing sent
    assert "AT_PIVOT:AAA" in out["would_fire"]
    assert pa._mem == {}                                 # dry-run doesn't mark dedup
