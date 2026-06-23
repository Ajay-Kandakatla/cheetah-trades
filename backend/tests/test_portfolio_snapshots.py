"""Portfolio "today's change" baseline (portfolio/snapshots.day_change_from_baseline).

The bug (Ajay 2026-06-23): today's change was `shares × (last − prev_close)` —
the market's close-to-close move. A position BOUGHT TODAY, below yesterday's
close, never experienced that close, so the move overstated its loss (MUU read
−20% when the real position was −1.5%).

Fix: baseline = yesterday's snapshot value if held, else COST basis.

The `portfolio` package pulls pydantic models that use 3.10 `str | None` syntax
(unevaluable on this 3.9 venv), so we load snapshots.py STANDALONE via importlib
— the project's standard portfolio-test pattern.

Host-runnable: cd backend && python3 -m pytest tests/test_portfolio_snapshots.py -q
"""
import importlib.util
import os

_PATH = os.path.join(os.path.dirname(__file__), "..", "portfolio", "snapshots.py")
_spec = importlib.util.spec_from_file_location("_pf_snapshots", _PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
dcb = _mod.day_change_from_baseline


def test_opened_today_measures_from_cost_not_market_close():
    """MUU regression: bought today at ~$980 (cost 19,999), now worth 19,349.
    No prior snapshot -> today = current − cost = −650 (−3.3%), NOT the market's
    −20% close-to-close."""
    d, pct = dcb(cur_value=19_349.0, cost_basis=19_999.0, prior_value=None)
    assert round(d, 0) == -650
    assert -4.0 < pct < -3.0


def test_opened_today_can_be_GREEN_even_if_the_security_fell():
    """WDCX: the ETF fell close-to-close, but he bought today below that close
    and it's up vs his cost -> today is POSITIVE (+2%), not the market's −16%."""
    d, pct = dcb(cur_value=9_285.0, cost_basis=9_100.0, prior_value=None)
    assert d > 0 and pct > 0


def test_held_position_uses_yesterdays_snapshot_value():
    """A position we held at yesterday's close -> today = current − prior
    snapshot (the real close-to-close), independent of cost."""
    d, pct = dcb(cur_value=9_309.0, cost_basis=11_187.0, prior_value=10_180.0)
    assert round(d, 0) == -871
    assert -9.0 < pct < -8.0


def test_negatives_are_safe():
    assert dcb(None, 1000.0, None) == (None, None)        # no live value
    assert dcb(1000.0, 0.0, None) == (None, None)         # no cost, no prior
    assert dcb(1000.0, None, 0.0) == (None, None)         # zero prior, no cost
