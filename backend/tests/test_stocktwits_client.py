"""StockTwits fetch — Cloudflare-challenge + pagination regression tests.

The bug (found 2026-09-01): GET /catalysts/{ticker} showed 0 StockTwits
messages for PETZ / LIDR / OLOX / NWGL while stocktwits.com showed active
streams (LIDR at "Extremely High" volume). Root cause was NOT a symbol
gap: Cloudflare fronted api.stocktwits.com with a bot challenge that 403s
every non-browser TLS fingerprint on EVERY symbol (AAPL included), and
both fetchers swallowed the 403 as "no stream for this ticker".

These tests pin the fix:
  1. profile rotation past the challenge (Safari passes, Chrome doesn't);
  2. a total block is a LOUD, machine-readable failure, not a silent 0;
  3. pagination via cursor.max so n_24h — and velocity_per_hour — can
     exceed the 30-msg single-page cap (velocity used to saturate at
     30/24 = 1.25/hr on frenzy names);
  4. pagination stops at the 24h cutoff (quiet tickers cost 1 request);
  5. created_at is parsed as UTC (time.mktime skewed it by the container's
     UTC offset).

All HTTP is faked at the stocktwits_client._http_get seam — no network.
"""
import asyncio
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import stocktwits_client as stc
from catalysts import chatter as cat_chatter
from sepa import forum_chatter


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeResp:
    def __init__(self, status_code=200, headers=None, body=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._body = body if body is not None else {}

    def json(self):
        return self._body


CHALLENGE = FakeResp(403, headers={"cf-mitigated": "challenge"})


def msg(mid, epoch, sentiment=None, body="to the moon"):
    created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))
    entities = {"sentiment": {"basic": sentiment} if sentiment else None}
    return {"id": mid, "body": body, "created_at": created,
            "entities": entities, "user": {"username": "u", "followers": 1}}


def page(msgs, more=False):
    body = {"messages": msgs}
    if msgs:
        body["cursor"] = {"more": more, "max": min(m["id"] for m in msgs),
                          "since": max(m["id"] for m in msgs)}
    else:
        body["cursor"] = {"more": False}
    return FakeResp(200, body=body)


@pytest.fixture(autouse=True)
def _reset_client_state(monkeypatch):
    """Fresh profile memory per test; force the curl_cffi code path so the
    rotation logic is exercised even on hosts without curl_cffi."""
    monkeypatch.setattr(stc, "_working_profile", None)
    monkeypatch.setattr(stc, "HAVE_CURL_CFFI", True)
    yield


# ---------------------------------------------------------------------------
# 1+2 — challenge rotation and loud failure
# ---------------------------------------------------------------------------

def test_challenge_rotates_to_next_profile(monkeypatch):
    calls = []

    def fake_get(url, profile, timeout):
        calls.append(profile)
        if profile == stc.IMPERSONATE_PROFILES[0]:
            return CHALLENGE
        return page([msg(10, time.time() - 60, "Bullish")])

    monkeypatch.setattr(stc, "_http_get", fake_get)
    res = stc.fetch_stream("LIDR")

    assert res["ok"] is True
    assert len(res["messages"]) == 1
    assert calls == list(stc.IMPERSONATE_PROFILES[:2])
    # The passing profile is remembered and tried first next time.
    assert stc._working_profile == stc.IMPERSONATE_PROFILES[1]
    stc.fetch_stream("PETZ")
    assert calls[2] == stc.IMPERSONATE_PROFILES[1]


def test_all_profiles_challenged_is_loud_not_silent_zero(monkeypatch):
    monkeypatch.setattr(stc, "_http_get", lambda u, p, t: CHALLENGE)
    res = stc.fetch_stream("PETZ")
    assert res["ok"] is False
    assert "cloudflare challenge" in (res["reason"] or "")
    assert res["messages"] == [] and res["pages"] == 0


def test_plain_404_does_not_burn_profiles(monkeypatch):
    calls = []

    def fake_get(url, profile, timeout):
        calls.append(profile)
        return FakeResp(404)

    monkeypatch.setattr(stc, "_http_get", fake_get)
    res = stc.fetch_stream("NOSUCH")
    assert res["ok"] is False and res["reason"] == "http 404"
    assert len(calls) == 1  # only a challenge rotates; a real 404 is final


# ---------------------------------------------------------------------------
# 3+4 — pagination
# ---------------------------------------------------------------------------

def test_pagination_follows_cursor_past_single_page_cap(monkeypatch):
    now = time.time()
    # 3 pages of recent messages: 30 + 30 + 10 = 70, all inside 24h.
    pages = {
        None: page([msg(1000 - i, now - i * 60) for i in range(30)], more=True),         # ids 1000..971
        971:  page([msg(970 - i, now - (30 + i) * 60) for i in range(30)], more=True),   # ids 970..941
        941:  page([msg(940 - i, now - (60 + i) * 60) for i in range(10)], more=False),  # ids 940..931
    }
    seen = []

    def fake_get(url, profile, timeout):
        key = int(url.split("max=")[1]) if "max=" in url else None
        seen.append(key)
        return pages[key]

    monkeypatch.setattr(stc, "_http_get", fake_get)
    res = stc.fetch_stream("LIDR", max_pages=4,
                           stop_before_epoch=now - 24 * 3600)
    assert res["ok"] is True
    assert res["pages"] == 3
    assert len(res["messages"]) == 70          # > the old 30-message cap
    assert seen == [None, 971, 941]


def test_pagination_stops_at_cutoff_for_quiet_tickers(monkeypatch):
    now = time.time()
    old = now - 3 * 86400  # stream tail is 3 days old
    calls = []

    def fake_get(url, profile, timeout):
        calls.append(url)
        return page([msg(50 - i, old - i * 60) for i in range(30)], more=True)

    monkeypatch.setattr(stc, "_http_get", fake_get)
    res = stc.fetch_stream("QUIET", max_pages=4,
                           stop_before_epoch=now - 24 * 3600)
    assert res["ok"] is True
    assert len(calls) == 1  # deeper pages are older still — don't spend them


# ---------------------------------------------------------------------------
# 5 — UTC parsing
# ---------------------------------------------------------------------------

def test_created_at_parsed_as_utc(monkeypatch):
    # 1970-01-02T00:00:00Z is exactly 86400 — in any host timezone.
    # time.mktime (the old code) returns 86400 only when TZ=UTC.
    if hasattr(time, "tzset"):
        monkeypatch.setenv("TZ", "America/New_York")
        time.tzset()
        try:
            assert stc.parse_created_at("1970-01-02T00:00:00Z") == 86400.0
        finally:
            monkeypatch.delenv("TZ")
            time.tzset()
    assert stc.parse_created_at("1970-01-02T00:00:00Z") == 86400.0
    assert stc.parse_created_at(None) is None
    assert stc.parse_created_at("garbage") is None


# ---------------------------------------------------------------------------
# catalysts.chatter wiring
# ---------------------------------------------------------------------------

def test_catalysts_n24h_and_velocity_exceed_old_saturation(monkeypatch):
    now = time.time()
    msgs = [msg(1000 - i, now - i * 600,
                "Bullish" if i % 3 == 0 else ("Bearish" if i % 3 == 1 else None))
            for i in range(96)]
    for m in msgs:
        m["_epoch"] = stc.parse_created_at(m["created_at"])
    monkeypatch.setattr(cat_chatter.stocktwits_client, "fetch_stream",
                        lambda *a, **k: {"ok": True, "reason": None,
                                         "messages": msgs, "pages": 4})
    st = cat_chatter._fetch_stocktwits("LIDR")
    assert st["n_messages"] == 96
    assert st["n_24h"] == 96                   # old code could never pass 30
    assert st["n_bullish"] == 32 and st["n_bearish"] == 32
    assert st["sentiment_pct_bullish"] == 50

    monkeypatch.setattr(cat_chatter, "_fetch_stocktwits", lambda t: st)
    monkeypatch.setattr(cat_chatter, "_fetch_reddit",
                        lambda t: {"n_posts_24h": 0, "n_posts_7d": 0,
                                   "top": None, "subreddits": []})
    out = cat_chatter.get_chatter("LIDR")
    assert out["velocity_per_hour"] == 4.0     # was hard-capped at 1.25


def test_catalysts_block_reports_unavailable_not_zero_chatter(monkeypatch):
    reason = "cloudflare challenge (http 403, profile safari184)"
    monkeypatch.setattr(cat_chatter.stocktwits_client, "fetch_stream",
                        lambda *a, **k: {"ok": False, "reason": reason,
                                         "messages": [], "pages": 0})
    st = cat_chatter._fetch_stocktwits("PETZ")
    assert st["n_messages"] == 0 and st["n_24h"] == 0
    assert st["unavailable_reason"] == reason


# ---------------------------------------------------------------------------
# sepa.forum_chatter wiring
# ---------------------------------------------------------------------------

def test_forum_chatter_lane_uses_shared_client(monkeypatch):
    now = time.time()
    msgs = [msg(3, now - 60, "Bullish"), msg(2, now - 120, "Bullish"),
            msg(1, now - 180, "Bearish")]
    for m in msgs:
        m["_epoch"] = stc.parse_created_at(m["created_at"])
    monkeypatch.setattr(forum_chatter.stocktwits_client, "fetch_stream",
                        lambda *a, **k: {"ok": True, "reason": None,
                                         "messages": msgs, "pages": 1})
    out = asyncio.run(forum_chatter._stocktwits("LIDR"))
    assert out["available"] is True
    assert out["bullish"] == 2 and out["bearish"] == 1
    assert len(out["messages"]) == 3


def test_forum_chatter_lane_surfaces_block_reason(monkeypatch):
    monkeypatch.setattr(forum_chatter.stocktwits_client, "fetch_stream",
                        lambda *a, **k: {"ok": False,
                                         "reason": "rate limited (http 429)",
                                         "messages": [], "pages": 0})
    out = asyncio.run(forum_chatter._stocktwits("LIDR"))
    assert out["available"] is False
    assert out["reason"] == "rate limited (http 429)"
