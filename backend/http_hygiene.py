"""Connection hygiene for long-lived HTTP clients (2026-10-06).

THE RULE: a long-lived HTTP client must never hold an idle socket the provider
can close first.

WHY: Docker Desktop's gvisor network forwarder never retires a flow that the
REMOTE side closes first. The api kept idle keep-alive sockets until Finnhub,
Yahoo or Massive timed them out, and every such flow became a permanent
forwarder entry: ~1,400 a day, ~14,750 after 10.5 days (2026-10-05 incident; a
fresh VM holds 39-64). The fix is that WE send the FIN first.

THE THREE TOOLS:
  1. ``NO_KEEPALIVE`` (this module): httpx ``Limits`` that close every
     connection as soon as its response finishes. Used by the finnhub per-loop
     client and main.py's four ``httpx.AsyncClient`` sites.
  2. ``install_yfinance_no_reuse()`` (this module): yfinance's process-wide
     curl_cffi session with ``FORBID_REUSE=1``, so libcurl closes each
     connection after its transfer.
  3. ``sepa.prices._http()``: a recycled per-thread ``requests.Session`` whose
     idle sessions are closed by us after 20 s (and busy ones every 10 min),
     keeping the measured keep-alive gain for the 15 s pollers.
"""
from __future__ import annotations

import logging

import httpx

log = logging.getLogger("http_hygiene")

# httpx closes the connection as soon as each response finishes, so we send the FIN.
# max_connections=100 is httpx's own default: Limits(max_keepalive_connections=0) alone
# would make it unbounded.
NO_KEEPALIVE: httpx.Limits = httpx.Limits(max_connections=100, max_keepalive_connections=0)

_YF_INSTALLED = False


def install_yfinance_no_reuse() -> bool:
    """Swap yfinance's process-wide curl_cffi session for one with FORBID_REUSE=1
    (libcurl closes each connection after its transfer: no idle fc.yahoo.com /
    query*.finance.yahoo.com sockets). Idempotent. Never raises; False when yfinance or
    curl_cffi cannot be imported or the swap fails (logged at WARNING)."""
    global _YF_INSTALLED
    if _YF_INSTALLED:
        return True
    try:
        from yfinance import data as yfd
        from curl_cffi import requests as cr, CurlOpt

        yfd.YfData(session=cr.Session(impersonate="chrome",
                                      curl_options={CurlOpt.FORBID_REUSE: 1}))
    except Exception as exc:
        log.warning("http_hygiene: yfinance no-reuse session not installed: %s", exc)
        return False
    _YF_INSTALLED = True
    return True
