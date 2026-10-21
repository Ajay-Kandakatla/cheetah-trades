"""Reddit scraping helper — shared across forum_chatter + smart_money.

Anonymous path: old.reddit.com/.json. Reddit closed it (2026-10-21: www →
403 block page, old → 404), so when REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET
are both set the same searches go through Reddit's app key instead
(OAuth2 client_credentials → oauth.reddit.com). See _OAuth.

Public API:
    await search_subreddits(symbol, subs, ...) -> dict

Returns the same shape both lanes have always used:
    {
      "available":         bool,
      "reason":            str,           # served sentence; only when available=False
      "reason_code":       str,           # FAILURE_CODES; only when available=False
      "threads":           [{...}, ...],  # top-N by score, descending
      "mentions_7d":       int,           # 0 if return_mention_windows=False
      "mentions_prior_7d": int,           # 0 if return_mention_windows=False
    }

Each thread:
    {
      "subreddit":  str,
      "title":      str,
      "url":        "https://reddit.com/r/.../comments/.../...",
      "score":      int,
      "n_comments": int,
      "created":    int,    # unix-utc seconds
      "snippet":    str,    # first 240 chars of selftext
      "comments":   [{"score": int, "body": str}, ...],  # empty unless requested
    }
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time

import httpx

log = logging.getLogger("sepa.reddit_scrape")

_DEFAULT_USER_AGENT = (
    "cheetah-market-app/0.1 (+https://github.com/Ajay-Kandakatla/cheetah-trades)"
)
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", _DEFAULT_USER_AGENT)
REDDIT_BASE = "https://old.reddit.com"
REDDIT_TIMEOUT = 12

# 2026-10-21: Reddit closed anonymous JSON (www → 403 block page, old → 404).
# The only route left is Reddit's own app key (OAuth2 client_credentials).
# Dark until REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET are both set; read at
# CALL time. The secret is never logged, served or stored past the request.
REDDIT_OAUTH_BASE = "https://oauth.reddit.com"
REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
TOKEN_EARLY_EXPIRY_SEC = 60

# Test seam: a zero-arg callable returning an httpx transport. None = httpx's
# default network transport.
_transport_factory = None

# In-process bearer token: {"value", "expires_at", "client_id"}.
_token: dict = {"value": None, "expires_at": 0.0, "client_id": None}

# Per-sub failure codes; the order breaks ties when all subs failed.
FAILURE_CODES = ("rate_limited", "blocked", "gone", "unreachable",
                 "http_other", "bad_json", "auth_failed")

# Served sentences (the ticker page prints ``reason`` as is).
SENTENCE_KEY_NEEDED = ("Reddit closed anonymous access (http {code}) — a Reddit "
                       "app key is needed (REDDIT_CLIENT_ID and "
                       "REDDIT_CLIENT_SECRET in backend/.env)")
SENTENCE_KEY_REFUSED = "Reddit refused the app key (http {code})"
SENTENCE_RATE_LIMITED = "Reddit rate limit (http 429)"
SENTENCE_UNREACHABLE = "Reddit is not reachable"
SENTENCE_HTTP_OTHER = "Reddit answered http {code}"
SENTENCE_BAD_JSON = "Reddit answered something that is not JSON"


class _RedditFetchError(Exception):
    """Internal marker — raised when a Reddit HTTP call fails so the
    caller can distinguish "ticker has no chatter" from "Reddit blocked
    us." Used by _search_one_sub → search_subreddits to surface a
    failure rate up to forum_chatter.chatter_for so we don't poison
    the cache with empty results during a 429.

    ``code`` ∈ FAILURE_CODES; ``status`` is the HTTP status when there
    was one."""

    def __init__(self, msg: str, code: str = "http_other",
                 status: "int | None" = None):
        super().__init__(msg)
        self.code = code
        self.status = status


def _code_for_status(status: int) -> str:
    if status == 429:
        return "rate_limited"
    if status == 403:
        return "blocked"
    if status == 404:
        return "gone"
    return "http_other"


def _oauth_configured() -> bool:
    return bool((os.getenv("REDDIT_CLIENT_ID") or "").strip()
                and (os.getenv("REDDIT_CLIENT_SECRET") or "").strip())


def _oauth_user_agent() -> str:
    return (os.getenv("REDDIT_USER_AGENT") or "").strip() or _DEFAULT_USER_AGENT


def failure_sentence(code: str, status: "int | None", key_set: bool) -> str:
    """The served sentence for one failure code."""
    if code in ("blocked", "gone"):
        tmpl = SENTENCE_KEY_REFUSED if key_set else SENTENCE_KEY_NEEDED
        return tmpl.format(code=status)
    if code == "auth_failed":
        return SENTENCE_KEY_REFUSED.format(code=status)
    if code == "rate_limited":
        return SENTENCE_RATE_LIMITED
    if code == "unreachable":
        return SENTENCE_UNREACHABLE
    if code == "bad_json":
        return SENTENCE_BAD_JSON
    return SENTENCE_HTTP_OTHER.format(code=status)


def _make_client(headers: dict) -> httpx.AsyncClient:
    kw: dict = {"timeout": REDDIT_TIMEOUT, "follow_redirects": True,
                "headers": headers}
    if _transport_factory is not None:
        kw["transport"] = _transport_factory()
    return httpx.AsyncClient(**kw)


class _OAuth:
    """Bearer-token holder for ONE search_subreddits call. The token itself
    is cached in-process (``_token``) across calls until expires_in − 60 s;
    a 401 drops it and re-auths at most ONCE per call (a lock keeps the
    concurrent sub searches from each re-authing)."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.lock = asyncio.Lock()
        self.reauths = 0
        self.current: "str | None" = None  # the token this call runs on

    async def _exchange(self) -> str:
        cid = (os.getenv("REDDIT_CLIENT_ID") or "").strip()
        try:
            r = await self.client.post(
                REDDIT_TOKEN_URL,
                auth=(cid, (os.getenv("REDDIT_CLIENT_SECRET") or "").strip()),
                data={"grant_type": "client_credentials"},
                headers={"User-Agent": _oauth_user_agent()},
            )
        except Exception as exc:
            log.debug("reddit token exchange failed: %s", type(exc).__name__)
            raise _RedditFetchError("token exchange failed", "unreachable")
        if r.status_code != 200:
            log.warning("reddit token exchange answered http %d",
                        r.status_code)
            raise _RedditFetchError("token refused", "auth_failed",
                                    r.status_code)
        try:
            body = r.json()
        except Exception:
            raise _RedditFetchError("token not json", "bad_json", 200)
        tok = body.get("access_token") if isinstance(body, dict) else None
        if not tok:
            raise _RedditFetchError("no access_token", "auth_failed", 200)
        try:
            ttl = float(body.get("expires_in") or 0)
        except (TypeError, ValueError):
            ttl = 0.0
        _token["value"] = tok
        _token["expires_at"] = time.time() + ttl - TOKEN_EARLY_EXPIRY_SEC
        _token["client_id"] = cid
        self.current = tok
        return tok

    def _cached(self) -> "str | None":
        cid = (os.getenv("REDDIT_CLIENT_ID") or "").strip()
        if (_token["value"] and _token["client_id"] == cid
                and time.time() < _token["expires_at"]):
            return _token["value"]
        return None

    async def token(self) -> str:
        """One token per call: the in-process cache when still valid, else
        ONE exchange that every sub search of this call then shares."""
        if self.current:
            return self.current
        async with self.lock:
            if self.current:
                return self.current
            cached = self._cached()
            if cached:
                self.current = cached
                return cached
            if self.reauths >= 1:
                # The one re-auth of this call already ran and failed:
                # no further exchange (one per permalink otherwise).
                raise _RedditFetchError("re-auth spent", "auth_failed")
            return await self._exchange()

    async def refresh(self, rejected: str) -> "str | None":
        """A 401 came back for ``rejected``: drop it and re-auth once.
        None = this call already spent its one re-auth (no retry)."""
        async with self.lock:
            if self.current and self.current != rejected:
                return self.current  # another sub already re-authed
            if self.reauths >= 1:
                return None
            self.reauths += 1
            self.current = None
            _token["value"] = None
            _token["expires_at"] = 0.0
            return await self._exchange()


async def _reddit_get(client: httpx.AsyncClient, oauth: "_OAuth | None",
                      path: str, params: dict) -> httpx.Response:
    """GET ``path`` (``/r/x/search``, a permalink …) on the right base.
    Anonymous: old.reddit + ``.json``. OAuth: oauth.reddit.com, bearer,
    one 401 → one re-auth → one retry."""
    if oauth is None:
        return await client.get(f"{REDDIT_BASE}{path}.json", params=params,
                                headers=_headers())
    url = f"{REDDIT_OAUTH_BASE}{path}"
    tok = await oauth.token()
    r = await client.get(url, params=params,
                         headers={"Authorization": f"bearer {tok}"})
    if r.status_code == 401:
        fresh = await oauth.refresh(tok)
        if fresh is not None:
            r = await client.get(url, params=params,
                                 headers={"Authorization": f"bearer {fresh}"})
    log.debug("reddit oauth x-ratelimit-remaining=%s",
              r.headers.get("x-ratelimit-remaining"))
    return r


def _ticker_pattern(symbol: str) -> re.Pattern:
    sym = re.escape(symbol.upper())
    return re.compile(rf"(?:\${sym}\b|(?<![A-Za-z]){sym}(?![A-Za-z]))")


def _headers() -> dict:
    return {
        "User-Agent": REDDIT_USER_AGENT,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }


async def _fetch_top_comments(
    client: httpx.AsyncClient, permalink: str, n: int,
    oauth: "_OAuth | None" = None,
) -> list[dict]:
    if not permalink or n <= 0:
        return []
    try:
        r = await _reddit_get(
            client, oauth, permalink.rstrip('/'),
            {"limit": str(n + 5), "sort": "top"},
        )
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception as exc:
        log.debug("reddit comments fetch failed for %s: %s",
                  permalink, type(exc).__name__)
        return []

    if not isinstance(data, list) or len(data) < 2:
        return []
    children = (data[1].get("data") or {}).get("children") or []

    out: list[dict] = []
    for c in children:
        if c.get("kind") != "t1":
            continue
        cd = c.get("data") or {}
        body = (cd.get("body") or "").strip()
        if not body or body in ("[deleted]", "[removed]"):
            continue
        out.append({
            "score": int(cd.get("score", 0) or 0),
            "body":  body[:280],
        })
        if len(out) >= n:
            break
    return out


async def _search_one_sub(
    client: httpx.AsyncClient,
    symbol: str,
    sub_name: str,
    score_floor: int,
    pat: re.Pattern,
    cutoffs: tuple[float, float, float],  # (window_start, 7d_ago, 14d_ago)
    fetch_comments_per_thread: int,
    return_mention_windows: bool,
    oauth: "_OAuth | None" = None,
) -> tuple[list[dict], int, int]:
    """Search one subreddit. Returns (qualifying_threads, m_7d, m_prior_7d)."""
    cutoff_window, cutoff_7d, cutoff_14d = cutoffs
    params = {
        "q":           symbol,
        "restrict_sr": "1",
        "sort":        "top",
        "t":           "month",
        "limit":       "25",
    }
    try:
        r = await _reddit_get(client, oauth, f"/r/{sub_name}/search", params)
    except _RedditFetchError:
        raise
    except Exception as exc:
        log.debug("reddit search failed for %s in r/%s: %s",
                  symbol, sub_name, type(exc).__name__)
        raise _RedditFetchError(f"r/{sub_name} unreachable", "unreachable")
    if r.status_code != 200:
        # Rate-limiting (429) and blocks (403 / 404 since 2026-10) show up
        # here. Used to silently return 0 mentions — which the
        # downstream forum_chatter classifier then read as "this
        # ticker has no chatter," polluting the cache. Now we
        # surface the failure so the caller can preserve stale
        # data instead of overwriting with garbage.
        log.warning("reddit r/%s returned %d for %s — treating as failed fetch",
                    sub_name, r.status_code, symbol)
        raise _RedditFetchError(f"r/{sub_name} HTTP {r.status_code}",
                                _code_for_status(r.status_code), r.status_code)
    try:
        data = r.json()
        if not isinstance(data, dict):
            raise ValueError("not an object")
    except Exception:
        raise _RedditFetchError(f"r/{sub_name} not json", "bad_json", 200)

    children = (data.get("data") or {}).get("children") or []
    candidates: list[dict] = []
    m_7d = m_prior_7d = 0

    for c in children:
        post = c.get("data") or {}
        created = float(post.get("created_utc") or 0)
        if created < cutoff_window:
            continue
        title = post.get("title") or ""
        selftext = (post.get("selftext") or "")[:500]
        if not pat.search(title) and not pat.search(selftext):
            continue

        if return_mention_windows:
            if created >= cutoff_7d:
                m_7d += 1
            elif created >= cutoff_14d:
                m_prior_7d += 1

        score = int(post.get("score") or 0)
        if score < score_floor:
            continue

        candidates.append({
            "subreddit":  sub_name,
            "title":      title,
            "url":        f"https://reddit.com{post.get('permalink', '')}",
            "permalink":  post.get("permalink", ""),
            "score":      score,
            "n_comments": int(post.get("num_comments") or 0),
            "created":    int(created),
            "snippet":    selftext[:240],
        })

    candidates.sort(key=lambda t: t["score"], reverse=True)
    top = candidates[:5]  # cap comment fetches per sub
    if fetch_comments_per_thread > 0 and top:
        comment_results = await asyncio.gather(
            *(_fetch_top_comments(client, t["permalink"],
                                  fetch_comments_per_thread, oauth)
              for t in top),
            return_exceptions=True,
        )
        for t, cr in zip(top, comment_results):
            t["comments"] = cr if isinstance(cr, list) else []
    for t in candidates:
        t.setdefault("comments", [])
        t.pop("permalink", None)

    return candidates, m_7d, m_prior_7d


def _dominant_failure(failures: list) -> tuple:
    """Most common failure code; ties → the first in FAILURE_CODES. Returns
    (code, status of the first failure carrying that code)."""
    if not failures:
        return "unreachable", None
    counts = {c: 0 for c in FAILURE_CODES}
    for code, _ in failures:
        counts[code if code in counts else "http_other"] += 1
    best = max(FAILURE_CODES, key=lambda c: (counts[c], -FAILURE_CODES.index(c)))
    status = next((st for code, st in failures
                   if code == best and st is not None), None)
    return best, status


async def search_subreddits(
    symbol: str,
    subs: list[tuple[str, int]],
    *,
    days: int = 30,
    fetch_comments_per_thread: int = 0,
    return_mention_windows: bool = False,
    top_n: int = 10,
) -> dict:
    """Search a list of (sub_name, score_floor) tuples for posts mentioning symbol.

    Args:
        symbol: ticker, e.g. 'NVDA'
        subs: list of (sub_name, min_score) tuples
        days: window cutoff (drops posts older than this)
        fetch_comments_per_thread: 0 = skip comments; N = fetch top-N for the
            top-5 threads per sub (caps request volume)
        return_mention_windows: when True, populate mentions_7d /
            mentions_prior_7d counters (counts every ticker-mentioning post,
            not just score-floor passers)
        top_n: max threads to keep in the final list (overall, after merging
            all subs)
    """
    pat = _ticker_pattern(symbol)
    now = time.time()
    cutoffs = (
        now - days * 86400,
        now - 7 * 86400,
        now - 14 * 86400,
    )

    key_set = _oauth_configured()
    n_total = len(subs)
    if key_set:
        headers = {"User-Agent": _oauth_user_agent(),
                   "Accept": "application/json"}
    else:
        headers = _headers()

    def _all_failed(code: str, status: "int | None") -> dict:
        return {
            "available": False, "partial": False,
            "subs_total": n_total, "subs_failed": n_total,
            "reason": failure_sentence(code, status, key_set),
            "reason_code": code,
            "threads": [], "mentions_7d": 0, "mentions_prior_7d": 0,
        }

    try:
        async with _make_client(headers) as client:
            oauth = None
            if key_set:
                oauth = _OAuth(client)
                try:
                    await oauth.token()
                except _RedditFetchError as exc:
                    return _all_failed(exc.code, exc.status)
            results = await asyncio.gather(*(
                _search_one_sub(
                    client, symbol, sub_name, score_floor, pat, cutoffs,
                    fetch_comments_per_thread, return_mention_windows,
                    oauth,
                )
                for sub_name, score_floor in subs
            ), return_exceptions=True)
    except Exception as exc:
        log.debug("reddit client failed: %s", type(exc).__name__)
        return _all_failed("unreachable", None)

    threads: list[dict] = []
    m_7d = m_prior_7d = 0
    n_failed = 0
    failures: list[tuple[str, "int | None"]] = []
    for res in results:
        if isinstance(res, BaseException):
            log.debug("reddit sub failed: %s", res)
            n_failed += 1
            if isinstance(res, _RedditFetchError):
                failures.append((res.code, res.status))
            else:
                failures.append(("unreachable", None))
            continue
        sub_threads, m7, mp = res
        threads.extend(sub_threads)
        m_7d += m7
        m_prior_7d += mp

    threads.sort(key=lambda t: t["score"], reverse=True)
    # Lane availability decision:
    #   - ALL subs failed → available=False (full Reddit outage / rate-limited).
    #     Caller (forum_chatter) preserves stale data instead of writing
    #     "0 mentions" to the cache.
    #   - SOME subs failed → available=True with partial=True so the UI
    #     can show a "partial data" hint.
    #   - None failed → clean result.
    available = n_failed < n_total
    reason = reason_code = None
    if not available:
        reason_code, status = _dominant_failure(failures)
        reason = failure_sentence(reason_code, status, key_set)
    return {
        "available":         available,
        "partial":           n_failed > 0 and n_failed < n_total,
        "subs_total":        n_total,
        "subs_failed":       n_failed,
        "reason":            reason,
        "reason_code":       reason_code,
        "threads":           threads[:top_n],
        "mentions_7d":       m_7d,
        "mentions_prior_7d": m_prior_7d,
    }
