"""Lock the day-trading strategies to LONG-ONLY (bull swing).

No short-only momentum_failure, and every advertised strategy is side=long.
Guards against a future edit re-introducing shorts.

Run:
  docker run --rm -e PYTHONPATH=/app -v "$PWD/backend:/app" -w /app \
      cheetah-api:latest python -m pytest tests/test_day_long_only.py -q
"""
from __future__ import annotations

from daytrading import backtest as bt
from daytrading import api as dt_api


def test_momentum_failure_removed_everywhere():
    assert "momentum_failure" not in bt.SIGNAL_REGISTRY
    assert "momentum_failure" not in dt_api._STRATEGIES
    assert "momentum_failure" not in dt_api.STRATEGY_INFO


def test_all_advertised_strategies_are_long():
    assert dt_api.STRATEGY_INFO, "no strategies registered"
    for key, info in dt_api.STRATEGY_INFO.items():
        assert info.get("side") == "long", f"{key} is not long-only (side={info.get('side')})"


def test_registry_and_info_agree():
    assert set(bt.SIGNAL_REGISTRY) == set(dt_api._STRATEGIES) == set(dt_api.STRATEGY_INFO)
