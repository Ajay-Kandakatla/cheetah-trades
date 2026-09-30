"""vX financials snapshot crawler (Ajay 2026-09-30: "yes please" to saving
Massive's deprecated feed before its 2026-10-09 sunset).

No network: a scripted fake session. The NEGATIVES carry the weight — a
brownout must never skip a page, the key must never reach disk, a bad key or
a self-pointing cursor must stop the crawl with the resume point intact.
"""
from __future__ import annotations

import gzip
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import vx_financials_snapshot as S  # noqa: E402

KEY = "SECRETKEY123"


class _Resp:
    def __init__(self, status, body=None, bad_json=False):
        self.status_code = status
        self._body = body
        self._bad = bad_json

    def json(self):
        if self._bad:
            raise ValueError("not json")
        return self._body


class _Session:
    """Answers each GET from a script keyed by the key-less URL."""

    def __init__(self, script):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append(url)
        assert "apiKey=" + KEY in url, "every request carries the key"
        return self.script[S.strip_key(url)].pop(0)


def _row(cik, fy, fp="Q1", tf="quarterly", fd="2020-01-02", end="2019-12-31"):
    return {"cik": cik, "fiscal_year": fy, "fiscal_period": fp, "timeframe": tf,
            "start_date": "2019-10-01", "end_date": end, "filing_date": fd,
            "tickers": ["X"], "financials": {"income_statement": {}}}


def _page(results, nxt=None):
    b = {"status": "OK", "request_id": "r", "results": results}
    if nxt:
        b["next_url"] = nxt + "&apiKey=" + KEY
    return b


U0 = S.first_url()
U1 = S.BASE + "?cursor=AAA"
U2 = S.BASE + "?cursor=BBB"


def _run(out, script, **kw):
    sleeps = []
    sess = _Session(script)
    st = S.crawl(str(out), sess, KEY, sleep=sleeps.append, log=lambda m: None, **kw)
    return st, sess, sleeps


def _all_rows(out):
    return [r for _, rec in S.iter_pages(str(out)) for r in rec["results"]]


# ---------------------------------------------------------------------------
# positives
# ---------------------------------------------------------------------------
def test_crawls_every_page_in_order_and_marks_done(tmp_path):
    script = {U0: [_Resp(200, _page([_row("1", "2019", fd=None)], U1))],
              U1: [_Resp(200, _page([_row("2", "2020")], U2))],
              U2: [_Resp(200, _page([_row("3", "2021", fd="2021-05-01")]))]}
    st, sess, sleeps = _run(tmp_path, script)
    assert st["done"] and st["pages"] == 3 and st["rows"] == 3
    assert st["null_filing_date_rows"] == 1, "null filing_date rows are KEPT and counted"
    assert st["first_filing_date"] == "2020-01-02" and st["last_filing_date"] == "2021-05-01"
    assert [r["cik"] for r in _all_rows(tmp_path)] == ["1", "2", "3"]
    assert sleeps == []
    m = S.verify(str(tmp_path))
    assert m["ok"] and m["rows"] == 3 and m["unique_rows"] == 3 and m["gap_count"] == 0
    assert m["null_filing_date_rows"] == 1 and m["by_timeframe"] == {"quarterly": 3}


def test_the_first_request_is_the_unfiltered_filing_date_crawl():
    q = dict(S.parse_qsl(S.urlsplit(S.first_url()).query))
    assert q == {"sort": "filing_date", "order": "asc", "limit": "100"}, \
        "no date/ticker/timeframe filter — nothing may fall between partitions"


def test_resume_continues_from_state_without_refetching(tmp_path):
    script = {U0: [_Resp(200, _page([_row("1", "2019")], U1))],
              U1: [_Resp(200, _page([_row("2", "2020")]))]}
    st, sess, _ = _run(tmp_path, script, max_pages=1)
    assert not st["done"] and st["pages"] == 1 and st["next_url"] == U1
    st, sess2, _ = _run(tmp_path, {U1: script[U1]})
    assert [S.strip_key(u) for u in sess2.calls] == [U1], "page 0 is never fetched again"
    assert st["done"] and st["pages"] == 2 and st["rows"] == 2
    assert S.verify(str(tmp_path))["ok"]


def test_strip_key_keeps_the_cursor_and_drops_only_the_key():
    u = S.BASE + "?cursor=YXA9MDAw&apiKey=" + KEY + "&limit=100"
    assert S.strip_key(u) == S.BASE + "?cursor=YXA9MDAw&limit=100"
    assert S.with_key(S.strip_key(u), KEY).count("apiKey=") == 1


# ---------------------------------------------------------------------------
# negatives
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad", [_Resp(410, {"status": "ERROR"}), _Resp(429), _Resp(503),
                                 _Resp(200, bad_json=True),
                                 _Resp(200, {"status": "ERROR", "error": "x"})])
def test_NEG_a_brownout_or_bad_body_retries_the_same_cursor_never_skips(tmp_path, bad):
    script = {U0: [_Resp(200, _page([_row("1", "2019")], U1))],
              U1: [bad, bad, _Resp(200, _page([_row("2", "2020")]))]}
    st, sess, sleeps = _run(tmp_path, script)
    assert [S.strip_key(u) for u in sess.calls] == [U0, U1, U1, U1]
    assert sleeps == [S.backoff(0), S.backoff(1)]
    assert st["done"] and st["rows"] == 2 and st["retries"] == 2


def test_NEG_a_network_error_is_retried_not_fatal(tmp_path):
    class _Boom(_Session):
        n = 0

        def get(self, url, timeout=None):
            self.n += 1
            if self.n == 1:
                raise ConnectionError("reset")
            return super().get(url, timeout)
    sess = _Boom({U0: [_Resp(200, _page([_row("1", "2019")]))]})
    st = S.crawl(str(tmp_path), sess, KEY, sleep=lambda s: None, log=lambda m: None)
    assert st["done"] and st["rows"] == 1


def test_backoff_is_capped():
    assert S.backoff(0) == 15.0 and S.backoff(1) == 30.0
    assert S.backoff(40) == S.BACKOFF_CAP_SEC


@pytest.mark.parametrize("status", [401, 403])
def test_NEG_a_key_problem_stops_the_crawl_with_the_resume_point_intact(tmp_path, status):
    script = {U0: [_Resp(200, _page([_row("1", "2019")], U1))],
              U1: [_Resp(status, {"status": "ERROR"})]}
    with pytest.raises(S.Fatal):
        _run(tmp_path, script)
    st = S.load_state(str(tmp_path))
    assert st["pages"] == 1 and st["next_url"] == U1 and not st["done"]


def test_NEG_a_cursor_pointing_at_itself_stops_instead_of_looping(tmp_path):
    script = {U0: [_Resp(200, _page([_row("1", "2019")], U0))]}
    with pytest.raises(S.Fatal, match="points at itself"):
        _run(tmp_path, script)
    assert S.load_state(str(tmp_path))["pages"] == 0


def test_NEG_past_the_deadline_stops_with_state_saved(tmp_path):
    script = {U0: [_Resp(200, _page([_row("1", "2019")], U1))],
              U1: [_Resp(410)] * 5}
    clock = iter([0, 0, 0, 10, 10**12, 10**12])
    with pytest.raises(S.DeadlineReached):
        _run(tmp_path, script, now=lambda: next(clock), deadline=100)
    st = S.load_state(str(tmp_path))
    assert st["pages"] == 1 and st["next_url"] == U1


def test_NEG_the_key_never_reaches_disk(tmp_path):
    script = {U0: [_Resp(200, _page([_row("1", "2019")], U1))],
              U1: [_Resp(200, _page([_row("2", "2020")]))]}
    _run(tmp_path, script)
    S.verify(str(tmp_path))
    for p in tmp_path.rglob("*"):
        if p.is_file():
            raw = p.read_bytes()
            if p.suffix == ".gz":
                raw = gzip.decompress(raw)
            assert KEY.encode() not in raw, f"key leaked into {p.name}"


def test_NEG_a_missing_key_refuses_to_start(tmp_path):
    with pytest.raises(S.Fatal, match=S.KEY_ENV):
        S.crawl(str(tmp_path), _Session({}), "", sleep=lambda s: None, log=lambda m: None)


def test_NEG_verify_fails_on_a_missing_page(tmp_path):
    script = {U0: [_Resp(200, _page([_row("1", "2019")], U1))],
              U1: [_Resp(200, _page([_row("2", "2020")], U2))],
              U2: [_Resp(200, _page([_row("3", "2021")]))]}
    _run(tmp_path, script)
    os.remove(S.page_path(str(tmp_path), 1))
    m = S.verify(str(tmp_path))
    assert not m["ok"] and m["gaps"] == [1] and m["rows"] == 2


def test_NEG_verify_fails_while_the_crawl_is_unfinished(tmp_path):
    script = {U0: [_Resp(200, _page([_row("1", "2019")], U1))]}
    _run(tmp_path, script, max_pages=1)
    assert not S.verify(str(tmp_path))["ok"]


def test_NEG_verify_counts_duplicate_rows(tmp_path):
    script = {U0: [_Resp(200, _page([_row("1", "2019")], U1))],
              U1: [_Resp(200, _page([_row("1", "2019")]))]}
    _run(tmp_path, script)
    m = S.verify(str(tmp_path))
    assert m["rows"] == 2 and m["unique_rows"] == 1 and m["duplicate_rows"] == 1
    assert json.loads((tmp_path / "manifest.json").read_text())["duplicate_rows"] == 1


def test_NEG_crosscheck_names_rows_the_snapshot_lacks(tmp_path):
    script = {U0: [_Resp(200, _page([_row("1", "2019")]))]}
    _run(tmp_path, script)
    t_url = S.BASE + "?ticker=AAA&limit=100"
    sess = _Session({t_url: [_Resp(200, _page([_row("1", "2019"), _row("1", "2020")]))]})
    rep = S.crosscheck(str(tmp_path), sess, KEY, ["AAA"], sleep=lambda s: None,
                       log=lambda m: None)
    assert rep["AAA"]["fresh_rows"] == 2 and rep["AAA"]["missing"] == 1
