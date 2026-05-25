"""Watchlist — user-curated ticker shelf with auto-research.

When a ticker is added (manually, or from any other page like SEPA/Catalyst/
Track), the system:

1. Inserts it as ``status="queued"``
2. Spawns a background task (FastAPI BackgroundTasks — same-process, no
   external worker required) to:
   - Fetch yfinance info: sector, industry, last_price, market cap, name
   - Look up the most recent SEPA score from candidate_snapshots if one exists
   - Find 3-5 industry peers from candidate_snapshots, add them as
     ``primary_ticker={original}, added_via="competitor_of:{original}"``
   - Mark the entry as ``status="ready"`` once research completes
3. Hooks the ticker into supply_demand if its sector exists there.

Competitors are not recursive — we add peers of the user-added ticker, but
not peers-of-peers.

Module layout
-------------
store.py    Mongo CRUD
research.py Background research worker
"""

from watchlist import store, research  # noqa: F401
