"""Oliver Kell — Cycle of Price Action (CoPA) scanners.

Kell's framework (2021 U.S. Investing Championship winner +89% return)
treats price action as a *cycle* of recurring patterns rather than a
single setup. Each Stage-2 leader cycles through these phases:

    wedge_drop  →  reversal_extension  →  base_break  →  power_trend
                                                              ↓
                                                          climax_run
                                                              ↓
                                                          (top / pullback)

Patterns implemented (six modules, one file each):

  - wedge_drop            (SAFE-MOD)    — 3-7 day pullback wedge to MA21/MA50,
                                          bullish reversal candle on volume.
  - reversal_extension    (AGGRESSIVE)  — bottom-turn + extension above
                                          the prior 5-day high on volume.
  - volatility_compression (SAFE)       — ATR contraction (parallel to VCP
                                          but ATR-ratio based rather than
                                          base-structure based).
  - base_break            (MODERATE)    — classic 30-day high breakout on
                                          confirming volume.
  - power_trend           (AGGRESSIVE)  — Stage-2 stair-step continuation
                                          buy on MA21 hold.
  - climax_run            (DEFENSIVE)   — blow-off / exhaustion warning.
                                          SELL signal, not buy.

All scanners READ from `setups.universe.get_sepa_candidates()` — the
shared SEPA candidate list. They never modify SEPA scoring; the SEPA
core (scanner.py SCORE_WEIGHTS, trend_template.py, vcp.py, stage.py) is
locked behind the contracts regression test.

Output flows into the SAME Mongo `setups` collection used by the
`setups.*` modules, with `kind` discriminator values prefixed by the
Kell pattern name. The frontend /kell page tabs read /setups/{kind}
just like /sepa does.

Lazy module re-exports (PEP-562) — same pattern as setups/__init__.py
so `python -m kell.<name>` doesn't double-import its package.
"""

__all__ = [
    "wedge_drop",
    "reversal_extension",
    "volatility_compression",
    "base_break",
    "power_trend",
    "climax_run",
]


def __getattr__(name: str):
    """Lazy-load scanner submodules on attribute access (PEP 562)."""
    if name in {
        "wedge_drop", "reversal_extension", "volatility_compression",
        "base_break", "power_trend", "climax_run",
    }:
        import importlib
        mod = importlib.import_module(f".{name}", __name__)
        globals()[name] = mod
        return mod
    raise AttributeError(f"module 'kell' has no attribute {name!r}")
