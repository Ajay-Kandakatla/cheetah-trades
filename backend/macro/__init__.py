"""Macro-context module — Claude-generated per-ticker macro brief
(geopolitics, futures, bear cases, sector context) plus a few live
news headlines pulled from the existing news module.

The result is cached in Mongo for 6h per symbol so repeat clicks on
the chip don't ring up Claude calls. Cache TTL chosen so:
  - intraday users get fresh-ish context (≤6h old)
  - the same symbol viewed multiple times per session costs $0
  - overnight requests still get a re-pull next morning

See api.py for HTTP routes, store.py for cache + LLM call.
"""
from .api import router  # noqa: F401
