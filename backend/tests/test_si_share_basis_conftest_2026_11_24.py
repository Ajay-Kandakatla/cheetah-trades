"""🩳 2026-11-24 — the test session refuses the share-basis SEC seam (spec sidilute §4 main-session).

`tests/conftest.py` ASSIGNS `short_interest.share_basis._http` to a refuser for the whole session (the reg_sho
pattern): a refresh / fetch with no `http=` must never reach data.sec.gov. A test's own `http=` still wins.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import short_interest.share_basis as SB

BACKEND = Path(__file__).resolve().parents[1]
CIK = "0001817760"


class Resp:
    def __init__(self, code, body):
        self.status_code = code
        self._body = body

    def json(self):
        return self._body


@pytest.fixture(autouse=True)
def _no_pace(monkeypatch):
    monkeypatch.setattr(SB, "_sec_wait", lambda *a, **k: None)
    monkeypatch.setattr(SB, "_sec_last", {"t": None})


def test_the_session_seam_is_the_conftest_refuser():
    assert SB._http is not None
    with pytest.raises(RuntimeError, match="share_basis SEC calls are disabled during tests"):
        SB._http("https://data.sec.gov/submissions/CIK%s.json" % CIK)


def test_conftest_installs_and_restores_the_refuser():
    src = (BACKEND / "tests" / "conftest.py").read_text()
    assert "import short_interest.share_basis as SBAS" in src
    assert "SBAS._http = _refuse_sec" in src and "SBAS._http = prior_sb_http" in src
    assert src.index("SBAS._http = _refuse_sec") < src.index("yield") < src.index("SBAS._http = prior_sb_http")


def test_NEGATIVE_sec_get_with_no_http_reaches_only_the_refuser():
    with pytest.raises(RuntimeError, match="disabled during tests"):
        SB._sec_get(SB.SEC_CONCEPT_URL % CIK, None)


def test_NEGATIVE_fetch_covers_with_no_http_fails_by_type_and_never_blocks():
    got = SB.fetch_covers(CIK)
    assert got == {"status": "failed", "error": "RuntimeError", "blocked": False}


def test_NEGATIVE_fetch_filings_with_no_http_fails_and_stores_no_text():
    got = SB.fetch_filings(CIK, "2026-08-01", kind_fn=lambda form, items: None)
    assert got["status"] == "failed"
    assert got["error"] == "RuntimeError"
    assert "disabled" not in repr(got)


def test_a_tests_own_http_wins_over_the_refuser():
    calls = []

    def fake(url, **kw):
        calls.append(url)
        return Resp(404, {})
    assert SB.fetch_covers(CIK, http=fake) == {"status": "none"}
    assert calls == [SB.SEC_CONCEPT_URL % CIK]


def test_monkeypatching_the_seam_is_scoped_to_the_test(monkeypatch):
    monkeypatch.setattr(SB, "_http", lambda url, **kw: Resp(404, {}))
    assert SB.fetch_covers(CIK) == {"status": "none"}


def test_NEGATIVE_the_refuser_is_back_after_a_monkeypatched_test():
    with pytest.raises(RuntimeError, match="disabled during tests"):
        SB._http("https://data.sec.gov/x")
