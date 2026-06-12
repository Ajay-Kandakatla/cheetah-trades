"""Broker factory — the ONE seam where the engine picks its execution venue.

get_broker() selection:
  1. env TRADING_BROKER=sim|alpaca — an explicit choice always wins;
  2. otherwise Alpaca when ALPACA_KEY_ID / ALPACA_SECRET_KEY are set;
  3. otherwise the built-in simulated broker (trading/broker_sim) that fills
     against the app's own real-time Massive quotes — paper trading with no
     external account. Switching later = env change + restart, no code.

Both modules expose the SAME duck-typed surface (configured/account/clock/
positions/open_orders/closed_orders_since/submit_bracket/submit_stop/
replace_order/cancel_order/close_position/latest_trade/make_client_order_id)
returning Alpaca-shaped dicts, so exit_engine / entries / auto_entry never
know which one they hold. The sim additionally exposes process_fills() —
its matching engine — which exit_engine.tick() duck-calls when present.

BrokerError and OPEN_STATUSES are re-exported here so the engine modules
import NOTHING from a broker implementation directly (locked by the factory
invariant in tests/test_trading_contracts.py).
"""
from __future__ import annotations

import os

from trading.broker_alpaca import (  # noqa: F401 — re-exports for the engine
    OPEN_STATUSES,
    BrokerError,
)


def get_broker():
    """The active broker MODULE (duck-typed; see module docstring)."""
    sel = (os.getenv("TRADING_BROKER") or "").strip().lower()
    if sel == "sim":
        from trading import broker_sim
        return broker_sim
    if sel == "alpaca":
        from trading import broker_alpaca
        return broker_alpaca
    from trading import broker_alpaca
    if broker_alpaca.configured():
        return broker_alpaca
    from trading import broker_sim
    return broker_sim


def mode() -> str:
    """"sim" | "paper" | "live" for the ACTIVE broker (sim reports itself;
    Alpaca reports paper/live from ALPACA_PAPER)."""
    active = get_broker()
    m = getattr(active, "mode", None)
    if callable(m):
        return str(m())
    return "live" if (os.getenv("ALPACA_PAPER", "1") or "1").strip() == "0" else "paper"
