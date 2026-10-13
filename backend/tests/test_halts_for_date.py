"""catalysts/halts.get_halts_for_date — one PAST session from Nasdaq Trader's dated list (2026-10-13, Gajjala's tab WP2).

The fixture is the real feed body for `&haltdate=10092026`, saved 2026-10-13 ~09:12 EDT (spec §1.6; re-read it with
scripts/gajjala_halts_history_probe.py): 72 items, every HaltDate 10/09/2026. The 🎾 squeeze-history chip's halt leg
is backfilled for 30 sessions with this call (chart_maps/gajjala/nightly.py).
"""
from __future__ import annotations

import os
from datetime import date

from catalysts import halts as H

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "gajjala", "halts_10092026.xml")
D = date(2026, 10, 9)


class _R:
    def __init__(self, text="", status=200):
        self.text, self.status_code = text, status


def _body():
    with open(FIXTURE, encoding="utf-8-sig") as fh:
        return fh.read()


def test_fixture_date_gives_72_halts_every_one_dated_that_day(monkeypatch):
    seen = {}

    def get(url, **k):
        seen["url"] = url
        return _R(_body())
    monkeypatch.setattr(H.requests, "get", get)
    out = H.get_halts_for_date(D)
    assert seen["url"].endswith("feed=tradehalts&haltdate=10092026")
    assert out["session_date"] == "2026-10-09"
    assert out["n_halts"] == 72
    assert sum(v["n_halts"] for v in out["by_ticker"].values()) == 72
    assert out["by_ticker"]["VIVK"]["reasons"] == ["LUDP"]


def test_NEGATIVE_another_dates_body_is_a_failed_read(monkeypatch):
    """The same body asked as 10/08 — no item is dated 10/08. Pin changed 2026-10-13 (review): this used to come back
    as "no halts on 10/08" (by_ticker {}) and the nightly marked the session read for good; a feed that ignores
    `&haltdate` would have blanked 29 of 30 sessions. It is now {} — a failed read, retried next night."""
    monkeypatch.setattr(H.requests, "get", lambda url, **k: _R(_body()))
    assert H.get_halts_for_date(date(2026, 10, 8)) == {}


def test_NEGATIVE_one_item_of_another_date_fails_the_whole_read(monkeypatch):
    body = _body()
    stray = ("<item><ndaq:IssueSymbol>STRY</ndaq:IssueSymbol><ndaq:HaltDate>10/08/2026</ndaq:HaltDate>"
             "<ndaq:ReasonCode>LUDP</ndaq:ReasonCode></item>")
    i = body.index("<item>")
    monkeypatch.setattr(H.requests, "get", lambda url, **k: _R(body[:i] + stray + body[i:]))
    assert H.get_halts_for_date(D) == {}


def test_NEGATIVE_empty_or_truncated_200_body_is_a_failed_read(monkeypatch):
    monkeypatch.setattr(H.requests, "get", lambda url, **k: _R("<rss><channel></channel></rss>"))
    assert H.get_halts_for_date(D) == {}
    monkeypatch.setattr(H.requests, "get", lambda url, **k: _R(""))
    assert H.get_halts_for_date(D) == {}


def test_NEGATIVE_non_200_is_empty_dict_not_raise(monkeypatch):
    monkeypatch.setattr(H.requests, "get", lambda url, **k: _R("", 503))
    assert H.get_halts_for_date(D) == {}


def test_NEGATIVE_transport_error_is_empty_dict_not_raise(monkeypatch):
    def boom(url, **k):
        raise RuntimeError("network refused")
    monkeypatch.setattr(H.requests, "get", boom)
    assert H.get_halts_for_date(D) == {}


def test_NEGATIVE_dated_read_never_touches_the_today_cache(monkeypatch):
    H._cache.update(data=None, ts=0.0)
    monkeypatch.setattr(H.requests, "get", lambda url, **k: _R(_body()))
    H.get_halts_for_date(D)
    assert H._cache["data"] is None
