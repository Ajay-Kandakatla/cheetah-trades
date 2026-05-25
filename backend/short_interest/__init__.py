"""Short volume + short interest module.

Shared foundation for three downstream features:

  1. **SEPA score component** (`sepa/scanner.py`) — high short% on a Stage-2
     advancing name = squeeze fuel. Adds a new dimension to the composite
     score; see `docs/rfcs/001-sepa-short-interest.md`.

  2. **Whale chip enrichment** (`supply_demand/whales.py`) — weekly delta
     short-interest is a real-time proxy for institutional positioning that
     dodges the 45-day 13F lag.

  3. **Accumulation/Distribution classifier** (`sepa/volume.py`) — short
     volume splits "selling" from "shorting" on down days. A down-day on
     heavy short volume is bearish *positioning*; a down-day on heavy long
     selling is bearish *conviction*. Different signals.

Data source: Massive (Polygon) `/stocks/v1/short-volume` — FINRA daily
short volume aggregated across NYSE / NASDAQ Carteret / NASDAQ Chicago /
ADF reporting venues. Free-tier-safe under the Options Advanced plan
(confirmed via probe 2026-05-24).

Caches in Mongo `short_volume_cache` (1-day TTL) and `short_interest_cache`
(14-day TTL — FINRA publishes bi-monthly). Both upsert-only; no row ever
gets deleted so we accumulate a time-series for trend analysis.

Why not yfinance: yfinance's short_ratio is the legacy "days-to-cover"
which is bi-monthly and lags by 14+ days. Massive gives us daily granularity
with a 1-day publication lag — much more actionable.
"""
from short_interest.client import (
    short_volume_for,
    short_volume_history,
    latest_short_pct,
)

__all__ = ["short_volume_for", "short_volume_history", "latest_short_pct"]
