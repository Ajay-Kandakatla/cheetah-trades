"""Ajay 2026-10-21 "Dated info." — the SEPA candidate page printed
"Data as of 11:03 AM" (the BROWSER's fetch time) and a typed "Re-rates after
3:00 PM CT (4:00 PM ET)" (the close, not the re-rate). The page now prints
served facts only:

  * `as_of_close` — the CLOSED session the SEPA read came from, stamped on
    every scan row by `scanner.as_of_close(df)` (None when the last bar was an
    in-progress one), carried top-level by GET /sepa/candidate/{symbol};
  * `rerate_text` — "re-rates after 4:30 PM ET", built from ONE constant
    `scanner.SEPA_RERATE_ET`, pinned here to the crontab fast-scan line.

Hermetic: the endpoint body is compiled out of main.py (the same way
test_scan_offloop / test_earnings_blackout do), every network call stubbed.
"""
from __future__ import annotations

import ast
import asyncio
import copy
import json
import logging
import math
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sepa import scanner as sc  # noqa: E402
from sepa import prices  # noqa: E402

MAIN_SRC = (BACKEND / "main.py").read_text()
SCANNER_SRC = (BACKEND / "sepa" / "scanner.py").read_text()
CRONTAB = (BACKEND / "crontab").read_text()


def _frame(*dates, tz=None):
    idx = pd.DatetimeIndex(pd.to_datetime(list(dates)))
    if tz:
        idx = idx.tz_localize(tz)
    return pd.DataFrame({"close": [1.0] * len(dates)}, index=idx)


# ---------------------------------------------------------------------------
# rerate_text — ONE constant, pinned to the crontab
# ---------------------------------------------------------------------------
def test_rerate_text_is_served_from_the_constant():
    assert sc.SEPA_RERATE_ET == "16:30"
    assert sc.rerate_text() == "re-rates after 4:30 PM ET"


def test_rerate_constant_matches_the_crontab_fast_scan_line():
    lines = [ln for ln in CRONTAB.splitlines()
             if not ln.lstrip().startswith("#") and "sepa.cli fast-scan --mode broad" in ln]
    assert len(lines) == 1, lines
    minute, hour = lines[0].split()[:2]
    assert f"{int(hour):02d}:{int(minute):02d}" == sc.SEPA_RERATE_ET
    assert "America/New_York" in CRONTAB, "the crontab times must be ET for the ET label"


@pytest.mark.parametrize("const,text", [
    ("09:05", "re-rates after 9:05 AM ET"),
    ("12:00", "re-rates after 12:00 PM ET"),
    ("00:15", "re-rates after 12:15 AM ET"),
    ("17:45", "re-rates after 5:45 PM ET"),
])
def test_NEG_rerate_text_follows_the_constant_never_a_typed_time(monkeypatch, const, text):
    monkeypatch.setattr(sc, "SEPA_RERATE_ET", const)
    assert sc.rerate_text() == text
    assert "4:30" not in sc.rerate_text()


def test_NEG_the_old_typed_ct_note_is_not_served():
    assert "CT" not in sc.rerate_text()
    assert "4:00 PM" not in sc.rerate_text()


# ---------------------------------------------------------------------------
# as_of_close — the CLOSED session the read came from, else None
# ---------------------------------------------------------------------------
RTH = pd.Timestamp("2026-10-21 12:03")          # Wed, regular session, ET wall clock
AFTER = pd.Timestamp("2026-10-21 16:31")
PRE = pd.Timestamp("2026-10-21 08:00")
LATE = pd.Timestamp("2026-10-21 21:00")


def test_last_bar_before_today_is_served_during_rth():
    df = _frame("2026-10-19", "2026-10-20")
    assert sc.as_of_close(df, now=RTH) == "2026-10-20"


def test_todays_bar_is_served_once_the_session_is_over():
    df = _frame("2026-10-20", "2026-10-21")
    assert sc.as_of_close(df, now=AFTER) == "2026-10-21"
    assert sc.as_of_close(df, now=LATE) == "2026-10-21"


def test_next_morning_serves_yesterdays_close():
    df = _frame("2026-10-20", "2026-10-21")
    assert sc.as_of_close(df, now=pd.Timestamp("2026-10-22 08:00")) == "2026-10-21"


@pytest.mark.parametrize("now", [RTH, PRE, pd.Timestamp("2026-10-21 15:59")])
def test_NEG_an_in_progress_bar_is_never_called_a_close(now):
    df = _frame("2026-10-20", "2026-10-21")
    assert sc.as_of_close(df, now=now) is None


# Critic fix (2) 2026-10-21: the 16:00 hourly vcp-watch run builds rows
# seconds after the bell — that is NOT the 16:30 re-rate, so a today-dated bar
# is a "close" only at/after SEPA_RERATE_ET (or when trade_session is 'closed').
def test_NEG_the_1600_hourly_run_is_not_the_rerate():
    df = _frame("2026-10-20", "2026-10-21")
    assert sc.as_of_close(df, now=pd.Timestamp("2026-10-21 16:00:30")) is None
    assert sc.as_of_close(df, now=pd.Timestamp("2026-10-21 16:29:59")) is None


def test_todays_bar_is_a_close_at_the_rerate_time():
    df = _frame("2026-10-20", "2026-10-21")
    assert sc.as_of_close(df, now=pd.Timestamp("2026-10-21 16:30:00")) == "2026-10-21"


def test_NEG_one_second_before_the_bell_is_not_a_close():
    df = _frame("2026-10-20", "2026-10-21")
    assert sc.as_of_close(df, now=pd.Timestamp("2026-10-21 15:59:59")) is None


def test_yesterdays_bar_at_1000_is_yesterdays_close():
    df = _frame("2026-10-19", "2026-10-20")
    assert sc.as_of_close(df, now=pd.Timestamp("2026-10-21 10:00")) == "2026-10-20"


def test_rerate_gate_follows_the_constant(monkeypatch):
    df = _frame("2026-10-20", "2026-10-21")
    monkeypatch.setattr(sc, "SEPA_RERATE_ET", "17:00")
    assert sc.as_of_close(df, now=pd.Timestamp("2026-10-21 16:45")) is None
    assert sc.as_of_close(df, now=pd.Timestamp("2026-10-21 17:00")) == "2026-10-21"


def test_todays_bar_on_a_closed_session_day_is_served():
    df = _frame("2026-10-23", "2026-10-24")                 # Sat bar, Sat clock
    assert sc.as_of_close(df, now=pd.Timestamp("2026-10-24 12:00")) == "2026-10-24"


def test_NEG_future_bar_empty_and_missing_frames_serve_nothing():
    assert sc.as_of_close(_frame("2026-10-22"), now=RTH) is None
    assert sc.as_of_close(None, now=RTH) is None
    assert sc.as_of_close(pd.DataFrame({"close": []}), now=RTH) is None


def test_NEG_garbage_index_serves_nothing():
    df = pd.DataFrame({"close": [1.0]}, index=["not-a-date"])
    assert sc.as_of_close(df, now=RTH) is None


def test_tz_aware_index_and_clock_read_in_et():
    df = _frame("2026-10-21 04:00", tz="UTC")              # Oct 21 00:00 ET
    utc_rth = pd.Timestamp("2026-10-21 16:03", tz="UTC")   # 12:03 ET
    assert sc.as_of_close(df, now=utc_rth) is None
    utc_after = pd.Timestamp("2026-10-21 20:31", tz="UTC")  # 16:31 ET
    assert sc.as_of_close(df, now=utc_after) == "2026-10-21"


def test_uses_the_shared_session_engine():
    fn = next(n for n in ast.parse(SCANNER_SRC).body
              if isinstance(n, ast.FunctionDef) and n.name == "as_of_close")
    src = ast.get_source_segment(SCANNER_SRC, fn)
    assert "prices.trade_session(" in src, "reuse the one session clock, never retype 16:00"
    assert "960" not in src and "16:00" not in src.split('"""')[-1]


# ---------------------------------------------------------------------------
# both scan row builders stamp the two fields
# ---------------------------------------------------------------------------
def test_both_scan_row_paths_stamp_the_fields():
    tree = ast.parse(SCANNER_SRC)
    fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name in ("_analyze_symbol", "_hot_recompute"):
        src = ast.get_source_segment(SCANNER_SRC, fns[name])
        assert '"as_of_close": as_of_close(df)' in src, name
        assert '"rerate_text": rerate_text()' in src, name


# ---------------------------------------------------------------------------
# GET /sepa/candidate/{symbol} — the page's payload carries both
# ---------------------------------------------------------------------------
def _compile(names, ns):
    tree = ast.parse(MAIN_SRC)
    body = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names:
            n.decorator_list = []
            body.append(n)
    assert {getattr(n, "name", "") for n in body} == set(names)
    exec(compile(ast.Module(body=body, type_ignores=[]), "main.py", "exec"), ns)
    return ns


@pytest.fixture
def candidate(monkeypatch):
    from starlette.responses import JSONResponse
    from sepa import catalyst as cat_mod, rs_rank

    state = {"latest": {}}

    async def _profile(sym):
        return {"name": sym}

    async def _smart(sym):
        return {}

    async def _cat(sym):
        return {"items": []}

    async def _ins(sym):
        return {}

    ns = {"asyncio": asyncio, "json": json, "copy": copy, "math": math, "JSONResponse": JSONResponse,
          "log": logging.getLogger("test"), "_company_profile": _profile,
          "sepa_smart_money": _smart, "sepa_catalyst_for": _cat, "sepa_insider": _ins,
          "sepa_ipo_age": lambda s: None,
          "sepa_scanner": type("S", (), {
              "load_latest_shared": staticmethod(lambda: state["latest"]),
              "load_latest": staticmethod(lambda: copy.deepcopy(state["latest"])),
              "LATEST_PATH": "/nonexistent/latest.json",
              "rerate_text": staticmethod(sc.rerate_text),
          })}
    _compile(["_clean_json_floats", "sepa_candidate_detail"], ns)
    monkeypatch.setattr(cat_mod, "summarize_catalyst", lambda c: None)
    monkeypatch.setattr(prices, "load_prices", lambda *a, **k: None)
    monkeypatch.setattr(prices, "is_stale", lambda df: False)
    monkeypatch.setattr(rs_rank, "rank_one", lambda *a, **k: None)
    monkeypatch.setattr(sc, "_earnings_map", lambda: {})
    monkeypatch.setattr(sc, "_analyze_symbol", lambda *a, **k: None)

    def _get(sym):
        resp = asyncio.run(ns["sepa_candidate_detail"](sym))
        return json.loads(resp.body)
    return state, _get


def test_candidate_payload_carries_the_served_close_and_rerate(candidate):
    state, get = candidate
    state["latest"] = {"all_results": [{"symbol": "POLA", "as_of_close": "2026-10-20",
                                        "rerate_text": sc.rerate_text()}]}
    out = get("pola")
    assert out["as_of_close"] == "2026-10-20"
    assert out["rerate_text"] == "re-rates after 4:30 PM ET"
    assert out["base"]["as_of_close"] == "2026-10-20"


def test_NEG_an_older_row_without_the_field_serves_no_close(candidate):
    state, get = candidate
    state["latest"] = {"all_results": [{"symbol": "POLA", "last_close": 0.75}]}
    out = get("POLA")
    assert out["as_of_close"] is None
    assert out["rerate_text"] == sc.rerate_text()


def test_NEG_an_in_progress_row_serves_no_close(candidate):
    state, get = candidate
    state["latest"] = {"all_results": [{"symbol": "POLA", "as_of_close": None}]}
    assert get("POLA")["as_of_close"] is None


def test_NEG_a_name_with_no_row_serves_no_close(candidate):
    state, get = candidate
    state["latest"] = {"all_results": []}
    out = get("ZZZZ")
    assert out["base"] is None
    assert out["as_of_close"] is None
    assert out["rerate_text"] == sc.rerate_text()


def test_NEG_the_route_never_types_a_rerate_time():
    fn = next(n for n in ast.parse(MAIN_SRC).body
              if isinstance(n, ast.AsyncFunctionDef) and n.name == "sepa_candidate_detail")
    src = ast.get_source_segment(MAIN_SRC, fn)
    assert '"rerate_text": sepa_scanner.rerate_text()' in src
    assert not re.search(r"re-rates after \d", src)
