"""Shared StockTwits stream client — the only code that talks to
api.stocktwits.com.

Why this exists (2026-09-02): Cloudflare fronted api.stocktwits.com with a
managed bot challenge. Every request from python-requests / httpx / plain
curl gets HTTP 403 with ``cf-mitigated: challenge`` — for EVERY symbol,
active stream or not. Both chatter fetchers (catalysts.chatter and
sepa.forum_chatter) treated non-200 as "no stream for this ticker" and
silently reported 0 messages, which read as a fake symbol-coverage gap
(PETZ/LIDR/OLOX/NWGL showing 0 in the app while stocktwits.com showed
LIDR at "Extremely High" message volume).

The block is TLS-fingerprint based: curl_cffi's Chrome profiles ALSO get
the 403, but Safari and Firefox impersonation passes (verified 2026-09-02
against PETZ/LIDR/OLOX/NWGL/AAPL — all 200 with a full page of messages).
So we pin a Safari profile and keep a small fallback chain for the day
Cloudflare's rules move again. If every profile is challenged, the failure
is LOUD (log.warning + a machine-readable reason) instead of a silent 0.

Pagination: the API caps every page at 30 messages regardless of ?limit=
(verified: limit=100 still returns 30). Older history is fetched by
following cursor.max (``?max=<oldest-id>``). fetch_stream() walks up to
``max_pages`` pages and stops early once a page crosses
``stop_before_epoch`` — quiet tickers cost 1 request, only frenzy names
spend the extra budget. Unauthenticated rate limit is ~200 req/hr/IP, so
keep max_pages small on batch paths.
"""
from __future__ import annotations

import calendar
import logging
import time
from typing import Optional

log = logging.getLogger("stocktwits_client")

try:
    from curl_cffi import requests as _http
    HAVE_CURL_CFFI = True
except Exception:  # pragma: no cover — dep is in requirements.txt
    import requests as _http  # type: ignore[no-redef]
    HAVE_CURL_CFFI = False

try:
    from curl_cffi.requests.exceptions import Timeout as _CurlTimeout
except Exception:  # pragma: no cover — dep is in requirements.txt
    _CurlTimeout = None  # type: ignore[assignment,misc]

BASE_URL = "https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
PAGE_SIZE = 30  # server-side cap per page; ?limit= above this is ignored

# Profiles that pass the Cloudflare TLS check, best first. Chrome profiles
# are exactly the ones being blocked — don't add one back without re-testing.
IMPERSONATE_PROFILES = ("safari184", "safari180", "firefox135")

_HEADERS = {"Accept": "application/json"}

_working_profile: Optional[str] = None  # last profile that returned 200


def parse_created_at(created: Optional[str]) -> Optional[float]:
    """StockTwits ``created_at`` ("2026-09-01T12:34:56Z") → epoch seconds.

    The timestamp is UTC, so ``calendar.timegm`` — NOT ``time.mktime``,
    which reads the struct as LOCAL time and skewed every message by the
    container's UTC offset (the pre-2026-09 catalysts.chatter bug).
    """
    if not created:
        return None
    try:
        return float(calendar.timegm(
            time.strptime(created.split("Z")[0], "%Y-%m-%dT%H:%M:%S")))
    except Exception:
        return None


def _http_get(url: str, profile: Optional[str], timeout: float):
    """One HTTP GET. Separated out as the test seam."""
    if HAVE_CURL_CFFI and profile:
        return _http.get(url, impersonate=profile, headers=_HEADERS,
                         timeout=timeout)
    return _http.get(url, headers=_HEADERS, timeout=timeout)


def _is_challenge(resp) -> bool:
    try:
        return (resp.headers or {}).get("cf-mitigated") == "challenge"
    except Exception:
        return False


# 2026-10-21 outage words. ``reason`` is SERVED (the ticker page prints it):
# a plain sentence, never a URL, "curl", a libcurl error code or an
# exception repr. ``reason_code`` is the machine-readable twin.
REASON_CODES = ("timeout", "unreachable", "http_5xx", "rate_limited",
                "challenge", "http_other", "ok")
SENTENCE_TIMEOUT = "StockTwits is not answering (timed out after {secs:.0f}s)"
SENTENCE_UNREACHABLE = "StockTwits is not reachable"
SENTENCE_DOWN = "StockTwits is down (http {code})"
SENTENCE_RATE_LIMITED = "StockTwits rate limit (http 429)"
SENTENCE_CHALLENGE = "StockTwits is challenging this client (http 403)"
SENTENCE_HTTP_OTHER = "StockTwits answered http {code}"
SENTENCE_NOT_JSON = "StockTwits answered something that is not JSON"


def _is_timeout(exc: BaseException) -> bool:
    """curl_cffi raises ``requests.exceptions.Timeout`` for curl error 28;
    the plain-``requests`` fallback raises ``Timeout``/``ReadTimeout``."""
    if HAVE_CURL_CFFI and _CurlTimeout is not None:
        return isinstance(exc, _CurlTimeout)
    return "Timeout" in type(exc).__name__


def _http_failure(code: int):
    """(sentence, reason_code) for a non-200, non-challenge answer."""
    if code == 429:
        return SENTENCE_RATE_LIMITED, "rate_limited"
    if 500 <= code <= 599:
        return SENTENCE_DOWN.format(code=code), "http_5xx"
    return SENTENCE_HTTP_OTHER.format(code=code), "http_other"


def _get_page(url: str, timeout: float):
    """GET one stream page, rotating impersonation profiles past the
    Cloudflare challenge. Returns (response, None, "ok") or
    (None, sentence, reason_code)."""
    global _working_profile
    profiles = list(IMPERSONATE_PROFILES) if HAVE_CURL_CFFI else [None]
    if _working_profile in profiles:
        profiles.remove(_working_profile)
        profiles.insert(0, _working_profile)
    reason, code = SENTENCE_UNREACHABLE, "unreachable"
    for prof in profiles:
        try:
            r = _http_get(url, prof, timeout)
        except Exception as exc:
            # The exception text (URL, "curl: (28)", libcurl docs link)
            # goes to the debug log only — never into the served reason.
            log.debug("stocktwits GET failed (profile %s): %s",
                      prof or "default", type(exc).__name__)
            if _is_timeout(exc):
                reason = SENTENCE_TIMEOUT.format(secs=float(timeout))
                code = "timeout"
            else:
                reason, code = SENTENCE_UNREACHABLE, "unreachable"
            continue
        if r.status_code == 200:
            _working_profile = prof
            return r, None, "ok"
        if r.status_code == 403 and _is_challenge(r):
            # This TLS profile is burned — the next one may still pass.
            log.debug("stocktwits cloudflare challenge on profile %s",
                      prof or "default")
            reason, code = SENTENCE_CHALLENGE, "challenge"
            continue
        reason, code = _http_failure(r.status_code)
        return None, reason, code
    return None, reason, code


def fetch_stream(symbol: str, *, max_pages: int = 1,
                 stop_before_epoch: Optional[float] = None,
                 timeout: float = 8.0) -> dict:
    """Fetch up to ``max_pages`` × 30 messages for ``symbol``.

    Returns ``{ok, reason, reason_code, messages, pages}`` where ``messages`` runs
    newest→oldest across pages and each message carries ``_epoch`` (parsed
    UTC ``created_at``). ``ok`` is False only when the FIRST page failed;
    a later page failing keeps what was already fetched. When
    ``stop_before_epoch`` is set, pagination stops once a page contains a
    message older than it — deeper pages are entirely older still.
    """
    sym = symbol.upper()
    messages: list[dict] = []
    next_max = None
    pages = 0
    for _ in range(max(1, max_pages)):
        url = BASE_URL.format(symbol=sym)
        if next_max:
            url += f"?max={next_max}"
        r, reason, reason_code = _get_page(url, timeout)
        if r is None:
            if pages == 0:
                log.warning("stocktwits stream unavailable for %s: %s",
                            sym, reason)
                return {"ok": False, "reason": reason,
                        "reason_code": reason_code, "messages": [],
                        "pages": 0}
            log.warning("stocktwits page %d failed for %s: %s "
                        "(keeping %d messages)",
                        pages + 1, sym, reason, len(messages))
            break
        try:
            body = r.json() or {}
        except Exception:
            if pages == 0:
                return {"ok": False, "reason": SENTENCE_NOT_JSON,
                        "reason_code": "http_other",
                        "messages": [], "pages": 0}
            break
        page_msgs = body.get("messages") or []
        for m in page_msgs:
            m["_epoch"] = parse_created_at(m.get("created_at"))
        messages.extend(page_msgs)
        pages += 1
        cursor = body.get("cursor") or {}
        if not page_msgs or not cursor.get("more") or not cursor.get("max"):
            break
        oldest = min((m["_epoch"] for m in page_msgs if m["_epoch"]),
                     default=None)
        if (stop_before_epoch is not None and oldest is not None
                and oldest < stop_before_epoch):
            break
        next_max = cursor["max"]
    return {"ok": True, "reason": None, "reason_code": "ok",
            "messages": messages, "pages": pages}


__all__ = ["fetch_stream", "parse_created_at", "PAGE_SIZE",
           "IMPERSONATE_PROFILES", "HAVE_CURL_CFFI", "REASON_CODES"]
