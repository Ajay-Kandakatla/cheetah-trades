"""Pluggable data-provider layer.

Today: free sources (yfinance, Google News RSS, SEC EDGAR). The Polygon layer
is stubbed — when POLYGON_API_KEY is set, we'll route catalyst/earnings/news
calls there for better quality + latency. For now everything works without a key.
"""
from __future__ import annotations

import os
from typing import Optional

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")


def has_polygon() -> bool:
    return bool(POLYGON_API_KEY)


# Finnhub (we already have a key in main.py env); useful for earnings calendar.
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")


def has_finnhub() -> bool:
    return bool(FINNHUB_API_KEY)
