"""Oliver Kell — Cycle of Price Action (CoPA) scanners.

Canonical source: "Victory in Stock Trading" (Kell, 2021), pp. 14-27.

Kell's framework (2021 U.S. Investing Championship winner, +941%)
treats price action as a *cycle* of recurring patterns rather than a
single setup. Each Stage-2 leader cycles through these six phases in
order, then the cycle repeats:

    Reversal Extension  →  Wedge Pop  →  EMA Crossback  →  Base n' Break
                                                                ↓
                                                  Exhaustion Extension
                                                                ↓
                                                          Wedge Drop
                                                                ↓
                                                  (cycle repeats from RE)

Canonical moving averages (pp. 12, 26-27):
  - 10 EMA (Daily) — short-term, primary trailing stop
  - 20 EMA (Daily) — medium-term, "10/20 EMA" tight cluster reference
  - 50 SMA (Daily) — support during corrections
  - 200 SMA (Daily) — long-term trend

Patterns implemented (six modules, one file each):

  - reversal_extension   (AGGRESSIVE)         — Phase 1: capitulation bottom.
                                                Bullish reversal bar after price
                                                extended below 10 EMA.
  - wedge_pop            (MODERATE)           — Phase 2: first reclaim of the
                                                10/20 EMA cluster after a
                                                downtrend.
  - ema_crossback        (SAFE-MOD)           — Phase 3: first pullback to the
                                                EMAs inside a confirmed uptrend.
                                                Kell's lowest-risk add point.
  - base_n_break         (SAFE)               — Phase 4: 5-15 day consolidation
                                                on the 10/20 EMA, then breakout
                                                on expanding volume.
  - exhaustion_extension (DEFENSIVE / WARN)   — Phase 5: 2nd-or-3rd extension
                                                from 10 EMA. SELL signal,
                                                NOT a buy.
  - wedge_drop           (DEFENSIVE / WARN)   — Phase 6: first close below the
                                                10/20 EMA after Exhaustion.
                                                SELL signal, cycle end.

All scanners READ from `setups.universe.get_sepa_candidates()` — the
shared SEPA candidate list. They never modify SEPA scoring; the SEPA
core (scanner.py SCORE_WEIGHTS, trend_template.py, vcp.py, stage.py) is
locked behind the contracts regression test.

Output flows into the SAME Mongo `setups` collection used by the
`setups.*` modules, with `kind` discriminator values matching the
pattern name. The frontend /kell page tabs read /setups/{kind}
just like /sepa does.

The 4 BULLISH scanners are bull-regime-gated (no-op in bear markets).
The 2 BEARISH scanners (exhaustion_extension, wedge_drop) are NOT
regime-gated — warnings are valuable in any regime.

Lazy module re-exports (PEP-562) — same pattern as setups/__init__.py
so `python -m kell.<name>` doesn't double-import its package.
"""

__all__ = [
    "reversal_extension",
    "wedge_pop",
    "ema_crossback",
    "base_n_break",
    "exhaustion_extension",
    "wedge_drop",
]


def __getattr__(name: str):
    """Lazy-load scanner submodules on attribute access (PEP 562)."""
    if name in set(__all__):
        import importlib
        mod = importlib.import_module(f".{name}", __name__)
        globals()[name] = mod
        return mod
    raise AttributeError(f"module 'kell' has no attribute {name!r}")
