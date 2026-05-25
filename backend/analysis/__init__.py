"""Cross-cutting technical analysis module.

Houses analyst-grade level computations (entry/stop/target/support/resistance)
that multiple pages need: SEPA candidate detail, Options Pulse, Tiny Stocks.

The shape of a "trade plan" returned by this module is deliberately
opinionated — it answers the four questions a swing trader actually
needs at decision time:

  1. Where do I buy?       (entry levels, ranked)
  2. Where do I stop out?  (stops, ranked by tightness)
  3. Where do I take profit? (1R/2R/3R + nearest resistance)
  4. What's the risk?      (% from entry to stop, R-multiples)

Methodology references:
  • Mark Minervini, "Trade Like a Stock Market Wizard" (2013) —
    7-8% hard stop rule, 20-25% profit zone, 2-3R target.
  • William O'Neil, "How to Make Money in Stocks" (1988) —
    7-8% stop, pivot from cup base, RS Rank ≥ 80.
  • Welles Wilder, "New Concepts in Technical Trading Systems" (1978) —
    ATR / Wilder smoothing, used here for volatility-adjusted stops.
"""
