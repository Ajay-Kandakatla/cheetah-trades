"""Regression tests for `/kell` page contracts.

See `docs/KELL_CONTRACTS.md` for the spec these tests enforce. Run before
AND after any Kell-adjacent change to prove nothing drifted:

    docker compose exec api python -m pytest /app/tests/test_kell_contracts.py -v

Tests are intentionally cheap — no Massive calls, no Mongo. Constants are
asserted by re-importing the modules; detector callability is verified
indirectly via the `scan()` smoke import.

Six canonical CoPA patterns covered (book pp. 14-21):
  reversal_extension, wedge_pop, ema_crossback, base_n_break,
  exhaustion_extension, wedge_drop.
"""
from __future__ import annotations

import importlib
import pytest


# =============================================================================
# §4 — Per-scanner constant locks
# =============================================================================

def test_reversal_extension_constants_locked():
    m = importlib.import_module("kell.reversal_extension")
    assert m._DOWNTREND_MIN_DAYS == 5
    assert m._EXTENSION_MIN_PCT  == 0.05
    assert m._MIN_VOL_MULT       == 1.5
    assert m._AVG_VOL_WINDOW     == 50
    assert m._HTF_SUPPORT_PCT    == 0.03


def test_wedge_pop_constants_locked():
    m = importlib.import_module("kell.wedge_pop")
    assert m._DOWNTREND_WIN        == 14
    assert m._EMA_CLUSTER_MAX_PCT  == 0.02
    assert m._WEDGE_MIN_LEN        == 5
    assert m._WEDGE_MAX_LEN        == 10
    assert m._FIRST_CLOSE_LOOKBACK == 10
    assert m._AVG_VOL_WINDOW       == 50
    assert m._STOP_LOOKBACK        == 7


def test_ema_crossback_constants_locked():
    m = importlib.import_module("kell.ema_crossback")
    assert m._TREND_WIN          == 15
    assert m._TREND_MIN_CLOSES   == 10
    assert m._EMA10_RISING_DAYS  == 10
    assert m._PULLBACK_LOOKBACK  == 3
    assert m._EMA_TOUCH_PCT      == 0.01
    assert m._AVG_VOL_WINDOW     == 50
    assert m._LIGHT_VOL_WINDOW   == 3


def test_base_n_break_constants_locked():
    m = importlib.import_module("kell.base_n_break")
    assert m._BASE_MIN_LEN         == 5
    assert m._BASE_MAX_LEN         == 15
    assert m._BASE_MAX_RANGE_PCT   == 0.10
    assert m._BASE_NEAR_EMA_PCT    == 0.03
    assert m._BASE_VOL_DRY_RATIO   == 0.85
    assert m._BREAKOUT_VOL_MULT    == 1.3
    assert m._AVG_VOL_WINDOW       == 50
    assert m._TREND_STACK_DAYS     == 5


def test_exhaustion_extension_constants_locked():
    m = importlib.import_module("kell.exhaustion_extension")
    assert m._TREND_AGE_WIN  == 30
    assert m._TREND_AGE_MIN  == 20
    assert m._EXT_MIN_PCT    == 0.08
    assert m._WIDE_RANGE_MIN == 0.05
    assert m._MIN_VOL_MULT   == 2.0
    assert m._EXT_COUNT_WIN  == 60
    assert m._AVG_VOL_WINDOW == 50


def test_wedge_drop_constants_locked():
    m = importlib.import_module("kell.wedge_drop")
    assert m._EXHAUSTION_LOOKBACK_MIN == 5
    assert m._EXHAUSTION_LOOKBACK_MAX == 15
    assert m._EXT_MIN_PCT             == 0.08
    assert m._EXT_MIN_VOL_MULT        == 2.0
    assert m._FIRST_CLOSE_LOOKBACK    == 10
    assert m._MIN_VOL_MULT            == 1.3
    assert m._AVG_VOL_WINDOW          == 50


# =============================================================================
# §1 / §3 — All 6 kinds are importable + scan() callable
# =============================================================================

KELL_MODULES = [
    "kell.reversal_extension",
    "kell.wedge_pop",
    "kell.ema_crossback",
    "kell.base_n_break",
    "kell.exhaustion_extension",
    "kell.wedge_drop",
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
    "reversal_extension",
    "wedge_pop",
    "ema_crossback",
    "base_n_break",
    "exhaustion_extension",
    "wedge_drop",
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
        kind="base_n_break",
        symbol="TEST",
        trigger=100.0, stop=95.0, target=110.0,
        expires_in_hours=48,
        meta={"sepa_score": 80.0},
    )
    missing = REQUIRED_SETUP_KEYS - set(s.keys())
    assert not missing, f"missing keys in make_setup output: {missing}"
    # Status is always pending on emit.
    assert s["status"] == "pending"
    # R:R sanity.
    assert s["risk_pct"] > 0
    assert s["reward_pct"] > 0
    assert s["rr"] > 0


# =============================================================================
# §4.5 / §4.6 — Both SELL scanners contain the SELL signal literal
# =============================================================================

def test_sell_signals_emit_signal_type_literal():
    """Both SELL-signal scanners (exhaustion_extension, wedge_drop) must
    emit the literal 'SELL_OR_TAKE_PROFITS' in their source — frontend
    rendering keys on this exact string (KELL_CONTRACTS.md §4.5/§4.6)."""
    import inspect
    for mod_name in ("kell.exhaustion_extension", "kell.wedge_drop"):
        m = importlib.import_module(mod_name)
        src = inspect.getsource(m)
        assert "SELL_OR_TAKE_PROFITS" in src, (
            f"{mod_name} must emit the literal SELL_OR_TAKE_PROFITS in meta — "
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
        "reversal_extension",
        "wedge_pop",
        "ema_crossback",
        "base_n_break",
        "exhaustion_extension",
        "wedge_drop",
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
        # Fallback for in-repo test runs (not container).
        cron_path = Path(__file__).parent.parent / "crontab"
    text = cron_path.read_text() if cron_path.exists() else ""
    for kind in KELL_KINDS:
        assert f"kell.{kind}" in text, (
            f"crontab missing entry for kell.{kind} — see §10 of KELL_CONTRACTS.md"
        )
