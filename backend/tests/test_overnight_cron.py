"""🌙 The overnight crontab lines + `python -m overnight.scan` (BUILD_SPEC16 §3.5, WP-A).

Two scan lines that are NOT wrapped in market_hours.gate (the gate reads TODAY:
Sunday 20:00 is a weekend) — the module gates itself on the session's trade
date — and one gated 06:45 push line. NEGATIVE: no gate on the scan, no curl /
api call on any overnight line, a closed clock makes no HTTP."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

import pytest
import requests

from overnight import scan
from overnight import session as S

CRONTAB = Path(__file__).resolve().parents[1] / "crontab"


def _jobs():
    out = []
    for line in CRONTAB.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            out.append(line)
    return out


def _overnight_jobs():
    return [j for j in _jobs() if re.search(r"(?<![\w.])overnight\.(scan|push)\b", j)]


def test_exactly_the_two_scan_lines():
    scan_lines = [j.split(None, 5) for j in _jobs() if "-m overnight.scan" in j]
    assert scan_lines == [
        ["*/10", "20-23", "*", "*", "0-4", "/usr/local/bin/python -m overnight.scan"],
        ["*/10", "0-3", "*", "*", "1-5", "/usr/local/bin/python -m overnight.scan"],
    ]


def test_negative_neither_scan_line_goes_through_the_gate():
    for j in (j for j in _jobs() if "overnight.scan" in j):
        assert "market_hours.gate" not in j, j
        assert "CHEETAH_IGNORE_HOLIDAY" not in j, j


def test_negative_no_curl_or_api_call_on_any_overnight_line():
    jobs = _overnight_jobs()
    assert len(jobs) == 3
    for j in jobs:
        assert "curl" not in j and "api:8000" not in j and "127.0.0.1" not in j, j
        assert j.split(None, 5)[5].startswith("/usr/local/bin/python -m "), j


def test_exactly_one_gated_push_line():
    push = [j.split(None, 5) for j in _jobs() if "overnight.push" in j]
    assert push == [["45", "6", "*", "*", "1-5", "/usr/local/bin/python -m market_hours.gate overnight.push"]]


def test_minute_step_is_the_cadence_and_the_hours_are_the_session():
    for f in (j.split(None, 5) for j in _jobs() if "-m overnight.scan" in j):
        assert f[0] == f"*/{scan.CADENCE_SEC // 60}"
    hours = [j.split(None, 5)[1] for j in _jobs() if "-m overnight.scan" in j]
    assert hours[0] == f"{S.SESSION_OPEN_ET.hour}-23"
    assert hours[1] == f"0-{S.SESSION_CLOSE_ET.hour - 1}"


def test_the_module_is_runnable_with_dash_m():
    src = Path(scan.__file__).read_text(encoding="utf-8")
    assert 'if __name__ == "__main__":' in src and "sys.exit(main())" in src
    assert "market_hours.gate" not in re.sub(r'""".*?"""|#[^\n]*', "", src, flags=re.S)


def test_main_on_a_closed_clock_returns_0_with_one_log_line(monkeypatch, caplog):
    from market_hours import gate
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)

    def boom(*a, **k):
        raise AssertionError("no HTTP on a closed clock")
    monkeypatch.setattr(requests, "get", boom)
    sat = datetime(2026, 10, 24, 21, 0, tzinfo=S.ET)
    monkeypatch.setattr(S, "et_now", lambda now=None: sat)
    caplog.set_level(logging.INFO, logger="overnight.scan")
    assert scan.main([]) == 0
    recs = [r for r in caplog.records if r.name == "overnight.scan"]
    assert len(recs) == 1 and "not run" in recs[0].getMessage() and "weekend" in recs[0].getMessage()


def test_negative_main_scrubs_a_crash_and_exits_nonzero(monkeypatch, caplog):
    secret = "PKCRASHSECRET999"
    monkeypatch.setenv("ALPACA_KEY_ID", secret)

    def crash(**k):
        raise RuntimeError(f"boom {secret}")
    monkeypatch.setattr(scan, "read_once", crash)
    caplog.set_level(logging.INFO, logger="overnight.scan")
    assert scan.main([]) == 1
    assert secret not in caplog.text and "<redacted>" in caplog.text
