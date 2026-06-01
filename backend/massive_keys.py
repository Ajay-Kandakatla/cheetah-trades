"""
Massive (Polygon-shape) API key resolution — single source of truth.

Ajay runs SEPARATE Massive subscriptions per product, each with its OWN key,
stored in ``backend/.env`` under product-specific names:

    MASSIVE_API_KEY_STOCKS    Stocks Advanced — real-time stock aggregates,
                              snapshots, and the WebSocket feed. Used by every
                              stock path (sepa, supply_demand, catalysts,
                              daytrading, overnight, short_interest, portfolio,
                              setups).
    MASSIVE_API_KEY_OPTIONS   Options Advanced — options chains / snapshots.
                              Used by the options-sentiment modules (SOIR).
    MASSIVE_API_KEY_CRYPTO    (optional) crypto data.

These are DISTINCT entitlements: a stocks key returns HTTP 403
("not entitled to this data") on the options endpoints and vice-versa. So each
module MUST read the RIGHT key — that routing lives here and nowhere else.

Legacy fallback
---------------
Older code (and the long-running prod container) used a single
``MASSIVE_API_KEY``. We fall back to it when a product-specific key is unset so
a half-migrated ``.env`` — or an old container env — keeps working instead of
silently dropping to the yfinance path. New deployments should set the
product-specific names; the bare name is deprecated.

Added 2026-06-01 to fix a var-name mismatch: the .env had been migrated to
``MASSIVE_API_KEY_STOCKS`` / ``_OPTIONS`` while the code still read the bare
``MASSIVE_API_KEY``. A restart would have resolved every stock call to None.
"""
from __future__ import annotations

import os


def _first(*names: str) -> str:
    """First non-empty env var among ``names`` (stripped), else ""."""
    for n in names:
        v = os.getenv(n)
        if v and v.strip():
            return v.strip()
    return ""


def stocks_key() -> str:
    """Key for real-time STOCK data (aggregates, snapshots, WebSocket)."""
    return _first("MASSIVE_API_KEY_STOCKS", "MASSIVE_API_KEY")


def options_key() -> str:
    """Key for OPTIONS chains / snapshots (SOIR sentiment).

    Distinct entitlement from stocks — falls back only to the legacy bare key,
    NOT to the stocks key (a stocks key 403s on options, so falling back to it
    would just produce confusing 403s instead of a clean "no key" signal).
    """
    return _first("MASSIVE_API_KEY_OPTIONS", "MASSIVE_API_KEY")


def crypto_key() -> str:
    """Key for CRYPTO data (optional)."""
    return _first("MASSIVE_API_KEY_CRYPTO", "MASSIVE_API_KEY")
