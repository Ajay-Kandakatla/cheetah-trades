"""The one reusable news routine — see `news_search.core`."""

from .core import (                                            # noqa: F401
    AUDIT_COLL,
    DEFAULT_LIMIT,
    DEFAULT_WINDOW_HOURS,
    SELECTORS,
    build_query,
    dedupe,
    fresh,
    normalise,
    relevance_filter,
    search,
    search_sync,
)

__all__ = [
    "search", "search_sync", "DEFAULT_WINDOW_HOURS", "DEFAULT_LIMIT",
    "SELECTORS", "AUDIT_COLL", "normalise", "fresh", "dedupe",
    "relevance_filter", "build_query",
]
