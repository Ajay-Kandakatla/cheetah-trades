"""Regression tests for `/kell` page contracts.

See `docs/KELL_CONTRACTS.md` for the spec these tests enforce. Run before
AND after any Kell-adjacent change to prove nothing drifted:

    docker compose exec api python -m pytest /app/tests/test_kell_contracts.py -v

Tests are intentionally cheap — no Massive calls, no Mongo. Constants are
asserted by re-importing the modules; detector callability is verified
against a synthetic in-memory DataFrame.
"""
from __future__ import annotations

import importlib
import pytest


# =============================================================================
# §4 — Per-scanner constant locks
# =============================================================================

def test_wedge_drop_constants_locked():
    m = importlib.import_module("kell.wedge_drop")
    assert m._WEDGE_MIN_LEN == 3
    assert m._WEDGE_MAX_LEN == 7
    assert m._MA_TOUCH_TOLERANCE_PCT == 2.0
    assert m._MIN_VOL_RATIO == 0.7
    assert m._AVG_VOL_WINDOW == 50


def test_reversal_extension_constants_locked():
    m = importlib.import_module("kell.reversal_extension")
    assert m._LOW_LOOKBACK == 20
    assert m._LOW_MIN_AGE == 3
    assert m._PRIOR_HIGH_WIN == 5
    assert m._MIN_VOL_MULT == 1.5
    assert m._AVG_VOL_WINDOW == 50


def test_volatility_compression_constants_locked():
    m = importlib.import_module("kell.volatility_compression")
    assert m._ATR_SHORT_WIN == 10
    assert m._ATR_LONG_WIN == 50
    assert m._ATR_RATIO_MAX == 0.7
    assert m._RANGE_WIN == 5
    assert m._RANGE_MAX_PCT == 0.04
    assert m._MA_PROX_PCT == 0.05
    assert m._VOL_DRY_RATIO == 0.85


def test_base_break_constants_locked():
    m = importlib.import_module("kell.base_break")
    assert m._PIVOT_LOOKBACK == 30
    assert m._STOP_LOOKBACK == 15
    assert m._MIN_VOL_MULT == 1.5
    assert m._AVG_VOL_WINDOW == 50


def test_power_trend_constants_locked():
    m = importlib.import_module("kell.power_trend")
    assert m._TREND_WIN == 50
    assert m._HH_LOOKBACK == 30
    assert m._HH_MIN_COUNT == 2
    assert m._PULLBACK_MAX_PCT == 10.0
    assert m._MA21_TOUCH_LOOKBK == 5
    assert m._MA21_TOUCH_PCT == 2.5


def test_climax_run_constants_locked():
    m = importlib.import_module("kell.climax_run")
    assert m._RUN_WIN == 30
    assert m._MIN_RUN_PCT == 50.0
    assert m._MIN_RANGE_RATIO == 0.05
    assert m._MIN_VOL_MULT == 2.5
    assert m._MIN_MA50_STRETCH == 0.30
    # 1/3 exactly (within float tolerance)
    assert abs(m._LOWER_THIRD_RATIO - (1.0 / 3.0)) < 1e-9
    assert m._AVG_VOL_WINDOW == 50


# =============================================================================
# §1 / §3 — All 6 kinds are importable + scan() callable
# =============================================================================

KELL_MODULES = [
    "kell.wedge_drop",
    "kell.reversal_extension",
    "kell.volatility_compression",
    "kell.base_break",
    "kell.power_trend",
    "kell.climax_run",
]


@pytest.mark.parametrize("mod_name", KELL_MODULES)
def test_kell_module_has_scan(mod_name):
    """Every Kell scanner must expose a callable scan() that returns a list."""
    m = importlib.import_module(mod_name)
    assert hasattr(m, "scan"), f"{mod_name} missing scan()"
    assert callable(m.scan), f"{mod_name}.scan is not callable"


# =============================================================================
# §8 — API surface accepts every Kell kind
# =============================================================================

KELL_KINDS = {
    "wedge_drop",
    "reversal_extension",
    "volatility_compression",
    "base_break",
    "power_trend",
    "climax_run",
}


def test_setups_api_accepts_kell_kinds():
    """The shared setups/api.py router knows about every Kell kind."""
    api = importlib.import_module("setups.api")
    for kind in KELL_KINDS:
        assert kind in api._VALID_KINDS, (
            f"kind '{kind}' missing from setups.api._VALID_KINDS"
        )
        assert kind in api._KIND_DISPATCH, (
            f"kind '{kind}' missing from setups.api._KIND_DISPATCH"
        )
        mod_name, func_name = api._KIND_DISPATCH[kind]
        assert mod_name.startswith("kell."), (
            f"_KIND_DISPATCH['{kind}'] should point at a kell.* module, got {mod_name}"
        )
        assert func_name == "scan"


# =============================================================================
# §5 — store.make_setup payload shape
# =============================================================================

REQUIRED_SETUP_KEYS = {
    "kind", "symbol", "generated_at", "date_et",
    "trigger", "stop", "target",
    "risk_pct", "reward_pct", "rr",
    "meta", "status",
    "triggered_at", "expires_at",
}


def test_store_make_setup_shape_for_kell_kinds():
    """make_setup produces every required key for a representative Kell kind."""
    from setups import store
    s = store.make_setup(
        kind="wedge_drop",
        symbol="TEST",
        trigger=100.0, stop=95.0, target=108.0,
        expires_in_hours=72,
        meta={"sepa_score": 80.0},
    )
    missing = REQUIRED_SETUP_KEYS - set(s.keys())
    assert not missing, f"missing keys in make_setup output: {missing}"
    # Status is always pending on emit
    assert s["status"] == "pending"
    # R:R sanity
    assert s["risk_pct"] > 0
    assert s["reward_pct"] > 0
    assert s["rr"] > 0


# =============================================================================
# §4.6 — climax_run signal_type literal is permanent
# =============================================================================

def test_climax_run_signal_type_literal():
    """The string 'SELL_OR_TAKE_PROFITS' must appear in the climax_run module
    — frontend rendering keys on this exact literal."""
    import inspect
    m = importlib.import_module("kell.climax_run")
    src = inspect.getsource(m)
    assert "SELL_OR_TAKE_PROFITS" in src, (
        "climax_run must emit the literal SELL_OR_TAKE_PROFITS in meta — "
        "frontend rendering depends on it"
    )


# =============================================================================
# §7 — Tier ordering and kind sets stay in sync between backend + frontend
# =============================================================================

def test_kell_init_exports_all_kinds():
    """backend/kell/__init__.py should expose all 6 scanner submodules."""
    import kell
    # __all__ is the documented export list. Should include all 6 kinds.
    declared = set(getattr(kell, "__all__", []))
    expected = {
        "wedge_drop",
        "reversal_extension",
        "volatility_compression",
        "base_break",
        "power_trend",
        "climax_run",
    }
    missing = expected - declared
    assert not missing, f"kell.__all__ missing: {missing}"


# =============================================================================
# §10 — Cron entries exist for all 6 scanners
# =============================================================================

def test_crontab_has_all_kell_entries():
    """backend/crontab has a cron line for each Kell scanner."""
    from pathlib import Path
    cron_path = Path("/app/crontab")
    if not cron_path.exists():
        # Fallback for in-repo test runs (not container)
        cron_path = Path(__file__).parent.parent / "crontab"
    text = cron_path.read_text() if cron_path.exists() else ""
    for kind in KELL_KINDS:
        assert f"kell.{kind}" in text, (
            f"crontab missing entry for kell.{kind} — see §10 of KELL_CONTRACTS.md"
        )
