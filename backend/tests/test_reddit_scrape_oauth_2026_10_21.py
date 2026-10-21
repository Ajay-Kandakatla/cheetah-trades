"""reddit_scrape — served failure words + the Reddit app-key path (2026-10-21).

Reddit closed anonymous JSON (www → 403 block page, old.reddit → 404). The
lane printed "all subs returned errors (rate-limit?)". Pins:
  * per-sub failure codes and the served sentence by the dominant code;
  * the OAuth2 client_credentials path, dark until BOTH env vars are set:
    token exchange shape (basic auth, form body, UA), bearer on search +
    comments via oauth.reddit.com, the token reused across calls,
    401 → one re-auth → success (never a second re-auth per call);
  * env unset → today's old.reddit path and no token call;
  * NEGATIVE: the secret never appears in any returned dict, reason or log
    record; the MockTransport is the only transport (a real one raises).
"""
import asyncio
import base64
import json
import logging
import os
import sys
import time
from urllib.parse import parse_qs

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import reddit_scrape as rs

SECRET = "fake-secret-XYZ"
CLIENT_ID = "fake-client-id"
UA = "cheetah-test/1.0 (by u/test)"
SUBS = [("stocks", 0), ("investing", 0)]


def post(i, title="POM to the moon", score=50):
    return {"data": {"title": title, "selftext": "", "score": score,
                     "num_comments": 3, "created_utc": time.time() - 3600,
                     "permalink": f"/r/stocks/comments/p{i}/x/"}}


def listing(posts):
    return {"data": {"children": posts}}


COMMENTS = [listing([]), listing([{"kind": "t1",
                                    "data": {"body": "nice", "score": 5}}])]


class Recorder:
    """MockTransport handler + call log. ``routes`` maps a predicate to a
    response factory; the first match wins."""

    def __init__(self, routes):
        self.routes = routes
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        for pred, make in self.routes:
            if pred(request):
                return make(request)
        return httpx.Response(599, text="unrouted")

    def token_calls(self):
        return [r for r in self.requests if r.url.path == "/api/v1/access_token"]

    def get_calls(self):
        return [r for r in self.requests if r.method == "GET"]


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    """Fresh token cache; any real httpx transport raises."""
    monkeypatch.setattr(rs, "_token",
                        {"value": None, "expires_at": 0.0, "client_id": None})

    async def _no_network(self, request):
        raise AssertionError(f"real network transport used: {request.url}")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request",
                        _no_network)
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("REDDIT_USER_AGENT", UA)
    yield


def install(monkeypatch, recorder):
    built = []

    def factory():
        t = httpx.MockTransport(recorder)
        built.append(t)
        return t

    monkeypatch.setattr(rs, "_transport_factory", factory)
    return built


def key_on(monkeypatch):
    monkeypatch.setenv("REDDIT_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", SECRET)


def is_token(r):
    return r.url.host == "www.reddit.com" and r.url.path == "/api/v1/access_token"


def is_search(r):
    return r.method == "GET" and r.url.path.endswith(("/search", "/search.json"))


def is_comments(r):
    return r.method == "GET" and "/comments/" in r.url.path


def token_resp(tok="tok-1", expires_in=3600):
    return lambda r: httpx.Response(
        200, json={"access_token": tok, "token_type": "bearer",
                   "expires_in": expires_in, "scope": "*"})


def search(**kw):
    return asyncio.run(rs.search_subreddits(
        "POM", SUBS, return_mention_windows=True, **kw))


def assert_no_secret(out, caplog):
    blob = json.dumps(out, default=str)
    b64 = base64.b64encode(f"{CLIENT_ID}:{SECRET}".encode()).decode()
    assert SECRET not in blob and b64 not in blob
    assert SECRET not in (out.get("reason") or "")
    assert SECRET not in caplog.text and b64 not in caplog.text
    for rec in caplog.records:
        assert SECRET not in rec.getMessage()


# ---------------------------------------------------------------------------
# OAuth path
# ---------------------------------------------------------------------------

def test_token_exchange_shape_and_bearer_on_search_and_comments(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    key_on(monkeypatch)
    rec = Recorder([
        (is_token, token_resp("tok-1")),
        (is_search, lambda r: httpx.Response(
            200, json=listing([post(1)]),
            headers={"x-ratelimit-remaining": "99"})),
        (is_comments, lambda r: httpx.Response(200, json=COMMENTS)),
    ])
    built = install(monkeypatch, rec)
    out = search(fetch_comments_per_thread=1)

    assert built, "the client was not built with the MockTransport"
    assert out["available"] is True and out["reason"] is None
    toks = rec.token_calls()
    assert len(toks) == 1
    t = toks[0]
    assert t.method == "POST"
    expected = base64.b64encode(f"{CLIENT_ID}:{SECRET}".encode()).decode()
    assert t.headers["authorization"] == f"Basic {expected}"
    assert parse_qs(t.content.decode()) == {"grant_type": ["client_credentials"]}
    assert t.headers["user-agent"] == UA

    searches = [r for r in rec.requests if is_search(r)]
    assert len(searches) == 2
    for r in searches:
        assert r.url.host == "oauth.reddit.com"
        assert not r.url.path.endswith(".json")
        assert r.headers["authorization"] == "bearer tok-1"
        assert r.url.params["q"] == "POM" and r.url.params["restrict_sr"] == "1"
    comments = [r for r in rec.requests if is_comments(r)]
    assert comments
    for r in comments:
        assert r.url.host == "oauth.reddit.com"
        assert not r.url.path.endswith(".json")
        assert r.headers["authorization"] == "bearer tok-1"
    assert out["threads"][0]["comments"] == [{"score": 5, "body": "nice"}]
    assert_no_secret(out, caplog)


def test_token_reused_across_calls(monkeypatch):
    key_on(monkeypatch)
    rec = Recorder([
        (is_token, token_resp("tok-1")),
        (is_search, lambda r: httpx.Response(200, json=listing([]))),
    ])
    install(monkeypatch, rec)
    search()
    search()
    assert len(rec.token_calls()) == 1


def test_expired_token_is_exchanged_again(monkeypatch):
    key_on(monkeypatch)
    # expires_in 30 s < the 60 s early-expiry margin → already expired
    rec = Recorder([
        (is_token, token_resp("tok-1", expires_in=30)),
        (is_search, lambda r: httpx.Response(200, json=listing([]))),
    ])
    install(monkeypatch, rec)
    search()
    search()
    assert len(rec.token_calls()) == 2


def test_401_reauths_once_then_succeeds(monkeypatch):
    key_on(monkeypatch)
    issued = iter(["tok-old", "tok-new"])

    def search_resp(r):
        if r.headers["authorization"] == "bearer tok-old":
            return httpx.Response(401, json={"error": 401})
        return httpx.Response(200, json=listing([post(1)]))

    rec = Recorder([
        (is_token, lambda r: token_resp(next(issued))(r)),
        (is_search, search_resp),
    ])
    install(monkeypatch, rec)
    out = search()
    assert out["available"] is True and out["subs_failed"] == 0
    assert len(rec.token_calls()) == 2      # initial + ONE re-auth
    assert rs._token["value"] == "tok-new"


def test_401_forever_never_reauths_twice(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    key_on(monkeypatch)
    n = iter(range(100))
    rec = Recorder([
        (is_token, lambda r: token_resp(f"tok-{next(n)}")(r)),
        (is_search, lambda r: httpx.Response(401, json={"error": 401})),
    ])
    install(monkeypatch, rec)
    out = search()
    assert len(rec.token_calls()) == 2      # initial + at most one re-auth
    assert out["available"] is False
    assert out["reason"] == "Reddit answered http 401"
    assert_no_secret(out, caplog)


def test_failed_token_exchange_is_auth_failed(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    key_on(monkeypatch)
    rec = Recorder([(is_token, lambda r: httpx.Response(401, json={"error": "invalid_grant"}))])
    install(monkeypatch, rec)
    out = search()
    assert out["available"] is False
    assert out["reason_code"] == "auth_failed"
    assert out["reason"] == "Reddit refused the app key (http 401)"
    assert rec.get_calls() == []            # no search without a token
    assert_no_secret(out, caplog)


def test_token_exchange_unreachable(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    key_on(monkeypatch)

    def boom(r):
        raise httpx.ConnectTimeout(f"timed out {SECRET}", request=r)

    install(monkeypatch, Recorder([(is_token, boom)]))
    out = search()
    assert out["reason_code"] == "unreachable"
    assert out["reason"] == "Reddit is not reachable"
    assert_no_secret(out, caplog)


@pytest.mark.parametrize("status", [403, 404])
def test_block_with_key_set_reads_refused_the_app_key(monkeypatch, status):
    key_on(monkeypatch)
    rec = Recorder([
        (is_token, token_resp()),
        (is_search, lambda r: httpx.Response(status, text="no")),
    ])
    install(monkeypatch, rec)
    out = search()
    assert out["available"] is False
    assert out["reason"] == f"Reddit refused the app key (http {status})"
    assert "app key is needed" not in out["reason"]


def test_only_one_env_var_set_stays_anonymous(monkeypatch):
    monkeypatch.setenv("REDDIT_CLIENT_ID", CLIENT_ID)   # secret missing
    rec = Recorder([(is_search, lambda r: httpx.Response(200, json=listing([])))])
    install(monkeypatch, rec)
    search()
    assert rec.token_calls() == []
    assert all(r.url.host == "old.reddit.com" for r in rec.requests)


# ---------------------------------------------------------------------------
# Anonymous path (env unset) — unchanged base + served sentences
# ---------------------------------------------------------------------------

def test_env_unset_uses_old_reddit_and_no_token_call(monkeypatch):
    rec = Recorder([
        (is_search, lambda r: httpx.Response(200, json=listing([post(1)]))),
        (is_comments, lambda r: httpx.Response(200, json=COMMENTS)),
    ])
    built = install(monkeypatch, rec)
    out = search(fetch_comments_per_thread=1)
    assert built
    assert out["available"] is True
    assert rec.token_calls() == []
    for r in rec.requests:
        assert r.url.host == "old.reddit.com"
        assert r.url.path.endswith(".json")
        assert "authorization" not in r.headers
    assert any(r.url.path == "/r/stocks/search.json" for r in rec.requests)


@pytest.mark.parametrize("status", [403, 404])
def test_block_without_key_reads_app_key_is_needed(monkeypatch, status):
    install(monkeypatch, Recorder([(is_search, lambda r: httpx.Response(status, text="Not Found"))]))
    out = search()
    assert out["available"] is False
    assert out["reason_code"] == ("blocked" if status == 403 else "gone")
    assert out["reason"] == (
        f"Reddit closed anonymous access (http {status}) — a Reddit app key is "
        "needed (REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in backend/.env)")
    assert "rate-limit?" not in out["reason"]


def test_429_rate_limit_sentence(monkeypatch):
    install(monkeypatch, Recorder([(is_search, lambda r: httpx.Response(429))]))
    out = search()
    assert out["reason"] == "Reddit rate limit (http 429)"
    assert out["reason_code"] == "rate_limited"


def test_unreachable_sentence_never_carries_exception_text(monkeypatch):
    def boom(r):
        raise httpx.ConnectError("[Errno 111] https://old.reddit.com refused",
                                 request=r)
    install(monkeypatch, Recorder([(is_search, boom)]))
    out = search()
    assert out["reason"] == "Reddit is not reachable"
    assert out["reason_code"] == "unreachable"
    assert "http" not in out["reason"].lower().replace("reddit", "")


def test_bad_json_and_other_http(monkeypatch):
    install(monkeypatch, Recorder([(is_search, lambda r: httpx.Response(
        200, text="<html>block</html>", headers={"content-type": "text/html"}))]))
    out = search()
    assert out["reason"] == "Reddit answered something that is not JSON"
    assert out["reason_code"] == "bad_json"

    install(monkeypatch, Recorder([(is_search, lambda r: httpx.Response(502))]))
    out = search()
    assert out["reason"] == "Reddit answered http 502"
    assert out["reason_code"] == "http_other"


def test_dominant_code_and_tie_order(monkeypatch):
    # one 429 vs one 404 → tie → rate_limited (first in FAILURE_CODES)
    def tie(r):
        return httpx.Response(429 if "/r/stocks/" in r.url.path else 404)
    install(monkeypatch, Recorder([(is_search, tie)]))
    out = search()
    assert out["reason_code"] == "rate_limited"

    # three subs: two 404, one 429 → gone dominates
    def dom(r):
        return httpx.Response(429 if "/r/a/" in r.url.path else 404)
    install(monkeypatch, Recorder([(is_search, dom)]))
    out = asyncio.run(rs.search_subreddits("POM", [("a", 0), ("b", 0), ("c", 0)]))
    assert out["reason_code"] == "gone"
    assert "(http 404)" in out["reason"]


def test_partial_failure_keeps_partial_semantics(monkeypatch):
    def half(r):
        if "/r/stocks/" in r.url.path:
            return httpx.Response(200, json=listing([post(1)]))
        return httpx.Response(429)
    install(monkeypatch, Recorder([(is_search, half)]))
    out = search()
    assert out["available"] is True and out["partial"] is True
    assert out["subs_failed"] == 1
    assert out["reason"] is None and out["reason_code"] is None


def test_typed_rate_limit_guess_is_gone_from_source():
    src = open(rs.__file__).read()
    assert "(rate-limit?)" not in src
    assert "oauth.reddit.com" in src and "api/v1/access_token" in src


def test_failed_reauth_then_comments_never_exchange_again(monkeypatch, caplog):
    # Critic 23 MED: the one re-auth fails, then the comment fetches of the
    # sub that got 200 must not each run another token exchange.
    caplog.set_level(logging.DEBUG)
    key_on(monkeypatch)
    state = {"tok": 0}

    def tok(r):
        state["tok"] += 1
        if state["tok"] == 1:
            return httpx.Response(200, json={"access_token": "t1",
                                             "expires_in": 3600})
        return httpx.Response(500, text="no")

    def srch(r):
        if "/r/stocks/" in r.url.path:
            return httpx.Response(200, json=listing([post(i) for i in range(5)]))
        return httpx.Response(401, text="x")

    rec = Recorder([(is_token, tok), (is_search, srch),
                    (is_comments, lambda r: httpx.Response(401, text="x"))])
    install(monkeypatch, rec)
    out = asyncio.run(rs.search_subreddits(
        "POM", SUBS, fetch_comments_per_thread=2))
    assert len(rec.token_calls()) == 2      # initial + the ONE re-auth
    assert out["available"] is True and out["partial"] is True
    assert_no_secret(out, caplog)


def test_spent_reauth_never_serves_http_none(monkeypatch):
    # Both subs fail auth: the sentence carries the real status, never "None".
    key_on(monkeypatch)
    state = {"tok": 0}

    def tok(r):
        state["tok"] += 1
        if state["tok"] == 1:
            return httpx.Response(200, json={"access_token": "t1",
                                             "expires_in": 3600})
        return httpx.Response(500, text="no")

    rec = Recorder([(is_token, tok),
                    (is_search, lambda r: httpx.Response(401, text="x"))])
    install(monkeypatch, rec)
    out = search()
    assert len(rec.token_calls()) == 2
    assert out["available"] is False
    assert "None" not in out["reason"]
