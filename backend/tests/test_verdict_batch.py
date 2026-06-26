"""verdict_batch pure-helper tests — no scan, no network."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa.verdict_batch import parse_symbols, slim_verdict


def test_parse_symbols_uppercases_dedupes_and_caps():
    assert parse_symbols("aapl, nvda ,AAPL,, msft") == ["AAPL", "NVDA", "MSFT"]
    assert parse_symbols("") == []
    assert parse_symbols(None) == []
    assert parse_symbols(",".join(f"S{i}" for i in range(100)), cap=5) == ["S0", "S1", "S2", "S3", "S4"]


_VERDICT = {
    "status": "pass", "label": "PASS — Minervini + sales", "icon": "🟢", "tone": "#10b981",
    "both_pass": True, "buyable_now": True, "sales_pending": False,
    "minervini": {"passed": True, "stage": 2, "reason": "qualifier", "cite": "p.79"},
    "bonde": {"passed": True, "pending": False, "tier": "strong", "reason": "35% YoY", "cite": "Bonde"},
}


def test_slim_verdict_extracts_chip_fields():
    row = {"symbol": "NVDA", "buy_verdict": _VERDICT, "rs_rank": 95,
           "stage": {"stage": 2}, "score": 88.0, "is_etf": False}
    v = slim_verdict(row)
    assert v["symbol"] == "NVDA"
    assert v["status"] == "pass" and v["icon"] == "🟢"
    assert v["both_pass"] is True and v["buyable_now"] is True
    assert v["rs"] == 95 and v["stage"] == 2 and v["score"] == 88.0
    assert v["minervini"]["passed"] is True
    assert v["bonde"]["tier"] == "strong"


def test_slim_verdict_handles_int_stage_and_rs_fallback():
    row = {"symbol": "ARM", "buy_verdict": _VERDICT, "rs": 87, "stage": 2}
    v = slim_verdict(row)
    assert v["rs"] == 87 and v["stage"] == 2


def test_slim_verdict_none_and_empty_return_none():
    assert slim_verdict(None) is None
    assert slim_verdict({}) is None            # falsy row → None


def test_slim_verdict_computes_fallback_for_unannotated_row():
    # a row with no precomputed buy_verdict (e.g. on-demand analyze) still gets
    # an honest verdict computed inline rather than rendering chipless.
    v = slim_verdict({"symbol": "X", "is_candidate": False, "qualifier": False})
    assert v is not None and v["status"] in ("pass", "partial", "fail")
    assert v["symbol"] == "X"


def test_slim_verdict_marks_etf():
    row = {"symbol": "SOXL", "buy_verdict": _VERDICT, "is_etf": True}
    assert slim_verdict(row)["is_etf"] is True
