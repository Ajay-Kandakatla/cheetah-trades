"""Order-flow ("Tape") analytics — per-ticker, on-demand.

Reads the day's raw trade prints from Massive (`/v3/trades/{symbol}`, Stocks
Advanced) and derives: buy/sell classification (tick rule), cumulative volume
delta, big prints, trade-flash bursts, a session volume profile (the honest
substitute for a bookmap — traded volume, not resting orders), intraday EMAs,
and a deterministic BUY / WAIT / AVOID checklist that reuses the existing
supply/demand zones and the OpEx dealer-gamma read.

METHOD NOTE (Ajay 2026-07-06): industry-standard order-flow techniques, NOT a
book methodology — every threshold is a CONFIGURED house value, cited in
docs/sepa/orderflow_methodology.md. The signal is decision-support with a
forward accuracy ledger (orderflow/history.py) so its hit rate is measured,
not assumed ("saw 70% in a WhatsApp group" → we grade our own record).
"""
