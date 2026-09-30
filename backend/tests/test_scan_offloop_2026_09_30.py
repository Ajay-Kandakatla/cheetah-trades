"""HTTP 524 incident 2026-09-30: latest.json is ~24 MB at the full universe and
was parsed (and for /sepa/scan scrubbed + encoded) ON THE EVENT LOOP by
/market/regime and /sepa/live-prices on every poll and by every full
/sepa/scan read — /health took 18 s and his boards timed out.

Fix under test: scanner.load_latest_shared() parses once per scan write
(keyed by mtime + size); /sepa/scan serves bytes built once per write in a
worker thread; the live-API contract tests are opt-in.

The endpoint bodies are compiled straight out of main.py (the local venv
cannot import main.py whole), the same way test_earnings_blackout does.
"""
from __future__ import annotations

import ast
import asyncio
import json
import math
import os
import sys
import threading
import types
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sepa import scanner as sc  # noqa: E402

MAIN_SRC = (BACKEND / "main.py").read_text()


@pytest.fixture
def latest(monkeypatch, tmp_path):
    p = tmp_path / "latest.json"
    monkeypatch.setattr(sc, "LATEST_PATH", p)
    monkeypatch.setitem(sc._SHARED, "key", None)
    monkeypatch.setitem(sc._SHARED, "value", None)
    parses = []
    real = sc.load_latest

    def _counting():
        parses.append(1)
        return real()
    monkeypatch.setattr(sc, "load_latest", _counting)
    return types.SimpleNamespace(path=p, parses=parses)


def _write(p: Path, payload: dict, bump: int = 0) -> None:
    p.write_text(json.dumps(payload))
    st = p.stat()
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + bump))


SCAN = {"generated_at": 1.0, "candidates": [],
        "all_results": [{"symbol": "AAA", "is_candidate": True, "rating": "BUY",
                         "trend": {"ma200": 10.0, "price": 12.0}},
                        {"symbol": "BBB", "is_candidate": False, "rating": "AVOID",
                         "score": float("nan")}]}


# ---------------------------------------------------------------------------
# load_latest_shared
# ---------------------------------------------------------------------------
def test_shared_load_parses_once_per_scan_write(latest):
    _write(latest.path, SCAN)
    a = sc.load_latest_shared()
    b = sc.load_latest_shared()
    assert a is b and len(latest.parses) == 1, "a poll must not re-parse an unchanged file"
    _write(latest.path, {**SCAN, "generated_at": 2.0}, bump=10**9)
    c = sc.load_latest_shared()
    assert c["generated_at"] == 2.0 and len(latest.parses) == 2, "a new scan write re-parses"


def test_NEG_no_scan_file_is_none_and_never_parses(latest):
    assert sc.load_latest_shared() is None and latest.parses == []


def test_NEG_a_half_written_file_is_not_cached(latest):
    latest.path.write_text('{"all_results": [')
    assert sc.load_latest_shared() is None
    assert sc._SHARED["key"] is None, "a failed parse must not be memoised"
    _write(latest.path, SCAN, bump=10**9)
    assert sc.load_latest_shared()["generated_at"] == 1.0


def test_NEG_the_key_changes_when_only_the_size_changes(latest):
    _write(latest.path, SCAN)
    k1 = sc.latest_key()
    st = latest.path.stat()
    latest.path.write_text(json.dumps({**SCAN, "pad": "x" * 10}))
    os.utime(latest.path, ns=(st.st_atime_ns, st.st_mtime_ns))
    assert sc.latest_key() != k1


# ---------------------------------------------------------------------------
# /sepa/scan — bytes built once per write, off the loop, identical output
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
def scan_endpoint(latest):
    from starlette.responses import JSONResponse, Response
    ns = {"asyncio": asyncio, "json": json, "_math": math, "threading": threading,
          "JSONResponse": JSONResponse, "Response": Response, "Optional": None,
          "Query": lambda d=None, **k: d, "sepa_scanner": sc,
          "_SCAN_BODY_LOCK": threading.Lock(), "_SCAN_BODY": {}}
    _compile(["_scrub_nan", "_sepa_scan_payload", "_sepa_scan_body", "sepa_scan_get"], ns)
    return types.SimpleNamespace(ns=ns, latest=latest)


def _get(ns, slim):
    resp = asyncio.run(ns["sepa_scan_get"](slim=slim))
    return resp, json.loads(resp.body)


def test_full_and_slim_payloads_match_the_old_handler(scan_endpoint):
    ns = scan_endpoint.ns
    _write(scan_endpoint.latest.path, SCAN)
    _, full = _get(ns, False)
    assert [r["symbol"] for r in full["all_results"]] == ["AAA", "BBB"]
    assert full["all_results"][1]["score"] is None, "NaN is still scrubbed to null"
    _, slim = _get(ns, True)
    assert "all_results" not in slim and slim["_slim"] is True and slim["_full_count"] == 2
    assert [c["symbol"] for c in slim["candidates"]] == ["AAA"]


def test_the_body_is_built_once_per_scan_write(scan_endpoint):
    ns = scan_endpoint.ns
    _write(scan_endpoint.latest.path, SCAN)
    _get(ns, False)
    _get(ns, False)
    _get(ns, True)
    _get(ns, True)
    assert len(scan_endpoint.latest.parses) == 2, "one parse per variant, not per request"
    _write(scan_endpoint.latest.path, {**SCAN, "generated_at": 9.0}, bump=10**9)
    _, full = _get(ns, False)
    assert full["generated_at"] == 9.0 and len(scan_endpoint.latest.parses) == 3


def test_NEG_no_scan_yet_keeps_the_old_message(scan_endpoint):
    resp, body = _get(scan_endpoint.ns, False)
    assert resp.status_code == 200 and body["message"].startswith("no scan yet")


def test_the_scan_body_is_built_in_a_worker_thread(scan_endpoint, monkeypatch):
    ns = scan_endpoint.ns
    _write(scan_endpoint.latest.path, SCAN)
    seen = []
    real = ns["_sepa_scan_body"]

    def _spy(slim):
        seen.append(threading.current_thread() is threading.main_thread())
        return real(slim)
    ns["_sepa_scan_body"] = _spy
    _get(ns, False)
    assert seen == [False], "the 24 MB parse/scrub/encode must never run on the event loop thread"


# ---------------------------------------------------------------------------
# source guards — the polled endpoints never parse latest.json on the loop
# ---------------------------------------------------------------------------
def _fn_src(name):
    tree = ast.parse(MAIN_SRC)
    fn = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
    return ast.get_source_segment(MAIN_SRC, fn)


@pytest.mark.parametrize("name", ["market_regime_get", "sepa_live_prices", "sepa_scan_get"])
def test_NEG_polled_endpoints_never_call_load_latest_on_the_loop(name):
    src = _fn_src(name)
    assert "load_latest()" not in src, f"{name} parses the 24 MB scan per request"
    assert "asyncio.to_thread" in src, f"{name} must do the heavy read in a worker thread"


def test_NEG_live_api_contract_tests_are_opt_in():
    src = (BACKEND / "tests" / "test_sepa_contracts.py").read_text()
    assert 'API_HOST = os.getenv("SEPA_TEST_API", "")' in src
    mk = (BACKEND.parent / "Makefile").read_text()
    assert "-e SEPA_TEST_API=http://localhost:8000 api python -m pytest tests/test_sepa_contracts.py" in mk, \
        "make contracts must still run the live shape checks inside the api container"
