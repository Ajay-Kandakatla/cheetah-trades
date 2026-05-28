"""Personal portfolio holdings — what the user actually owns.

Two paths into this package coexist:

  * Manual entry  — the original ``store.py`` (user-typed ticker /
    shares / cost basis). Surfaced at the top of the morning brief.
  * Plaid Investments — ``plaid_client.py`` + ``plaid_store.py`` add
    a hosted-login flow against Fidelity (or any Plaid-supported
    broker) so positions auto-import without storing broker
    credentials anywhere in this app.

Distinct from `watchlist` (interests) and `daytrading/paper_trading`
(simulated). This is real money, surfaced at the top of the morning
brief so it stays in the user's face when planning the day.

The package uses PEP-562 lazy attribute resolution to keep
``python -m portfolio.<submodule>`` invocations clean (the eager-import
pattern produced "found in sys.modules after import of package"
warnings when both ``__init__`` and an ``-m`` entry-point loaded the
same module).
"""
from .api import router

__all__ = [
    "router",
    "quotes", "store", "seed",
    "plaid_client", "plaid_store",
]


def __getattr__(name: str):
    """Lazy-load submodules on attribute access (PEP 562).

    Importing ``plaid_client`` at package-load time would pull the
    plaid-python SDK in for every backend startup — including the
    cron container that doesn't need it. Lazy resolution keeps the
    Plaid dependency truly optional until something actually touches
    a Plaid path.
    """
    if name in {"quotes", "store", "seed", "plaid_client", "plaid_store", "csv_import", "alerts", "corporate_actions"}:
        import importlib
        mod = importlib.import_module(f".{name}", __name__)
        globals()[name] = mod
        return mod
    raise AttributeError(f"module 'portfolio' has no attribute {name!r}")
