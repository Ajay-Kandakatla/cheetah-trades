"""Bull-regime intraday + short-swing setups.

Long-only, single-pass scanners that read the latest SEPA candidate
list and produce concrete trigger / stop / target rows in Mongo.

Original three (Phase 0):
  - PEG (Power Earnings Gap)  — 5% gap on 4× volume; buy take-out of
        the gap-day high. Hold 3-10 days, target 3-8%.
  - ORB (Opening Range Breakout) — 9:30-9:45 range; intraday alert on
        a volume break. ~1-2% target, same-day.
  - Inside-Day                — compression bar; buy a break of
        yesterday's high. Hold 1-3 days.

Phase 1 additions (Minervini moderate-aggressive setups):
  - Cheat (low / mid / high variants) — earlier entries inside a VCP
        handle. Three kinds in one module: low_cheat, mid_cheat, high_cheat.
  - Bull Flag — strong leg-up followed by a tight low-volume rest;
        measured-move target.
  - Episodic Pivot — catalyst-agnostic version of PEG (8% gap, 5× vol).
  - High Tight Flag — 90%+ run in 4-8 weeks then a 15-25% tight rest.
  - Post-Earnings Drift — joining the trend that follows a power gap.

All scanners feed off the existing SEPA candidate list (universe is
already quality-filtered) and reuse the existing price-cache plumbing.
No new data subscriptions needed.

Output flows into one Mongo collection (``setups``) with a `kind` field
so the frontend can render them as tabs against a single API surface.

This module is BULL-REGIME ONLY. The user explicitly chose to sit out
bear markets in cash (the disciplined Minervini answer). When the market
regime turns bearish, the scanners still run but produce no setups —
that's by design, NOT a bug. See sepa/market_regime.py for the regime
classifier these modules respect.
"""
from .api import router

# Lazy re-export: importing the scanner modules eagerly at package import
# time produced "found in sys.modules after import of package" warnings
# whenever a `python -m setups.<name>` invocation also triggered the
# package __init__. Using a __getattr__ hook delays the import until a
# caller actually does `from setups import bull_flag`, which:
#   - keeps `python -m setups.bull_flag` clean (no double-import warning),
#   - still lets `from setups import bull_flag` work for in-process callers,
#   - keeps the package's __all__ documenting what's available.
__all__ = [
    "router",
    "peg", "inside_day", "orb",
    "cheat", "bull_flag", "episodic_pivot",
    "high_tight_flag", "post_earnings_drift",
]


def __getattr__(name: str):
    """Lazy-load scanner submodules on attribute access (PEP 562)."""
    if name in {
        "peg", "inside_day", "orb",
        "cheat", "bull_flag", "episodic_pivot",
        "high_tight_flag", "post_earnings_drift",
    }:
        import importlib
        mod = importlib.import_module(f".{name}", __name__)
        globals()[name] = mod
        return mod
    raise AttributeError(f"module 'setups' has no attribute {name!r}")
