"""Trading-engine liveness — the REAL order-management heartbeat, not the alert
cron (UX teardown #8: a green 'engine OK' light that watches the wrong thing is a
trust bug). `stale` must only trip when the engine SHOULD be ticking."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from trading import exit_engine as E


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def test_fresh_tick_is_not_stale():
    r = E._engine_liveness(_iso(time.time() - 30), market_open=True, armed=True)
    assert r["stale"] is False
    assert r["tick_age_sec"] is not None and r["tick_age_sec"] < E.ENGINE_STALE_SEC


def test_old_tick_is_stale_when_open_and_armed():
    assert E._engine_liveness(_iso(time.time() - 10 * 60),
                              market_open=True, armed=True)["stale"] is True


def test_not_stale_when_market_closed():
    assert E._engine_liveness(_iso(time.time() - 10 * 60),
                              market_open=False, armed=True)["stale"] is False


def test_not_stale_when_disarmed():
    assert E._engine_liveness(_iso(time.time() - 10 * 60),
                              market_open=True, armed=False)["stale"] is False


def test_never_ticked_is_stale_only_when_active():
    assert E._engine_liveness(None, market_open=True, armed=True)["stale"] is True
    assert E._engine_liveness(None, market_open=False, armed=True)["stale"] is False
