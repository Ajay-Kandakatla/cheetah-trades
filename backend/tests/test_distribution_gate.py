"""Distribution blocks the Enter/buy tier (Ajay 2026-06-21: "if big institutions
are selling … block this from coming up in the buy list").

When the tape shows institutions SELLING into a name's breakout/run — a churn
breakout (heavy volume, weak close in the lower third, TTLAC p.188) or a
climax-top distribution — the strict `is_buyable` (Enter) tier must drop it,
while it STAYS `setup_ready`/`is_candidate` (watchlist). Locks:
  * gate wiring — `distribution=True` blocks is_buyable, `False` does not;
  * `_distribution_context` flags a churn breakout + a climax, and (REGRESSION)
    does NOT flag a clean breakout that closed strong;
  * the gate threshold is stricter than the display "suspect" warning.

Run: cd backend && .venv/bin/python -m pytest tests/test_distribution_gate.py -q
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import scanner, volume
from sepa import climax_distribution as cd


# ── gate wiring ──────────────────────────────────────────────────────────────
def test_distribution_blocks_is_buyable_keeps_setup_ready():
    from types import SimpleNamespace
    tr = SimpleNamespace(pass_all=True)
    es = {"type": "VCP", "pivot": 100, "stop": 93}
    stg, liq, vol = {"stage": 2}, {"liquid": True}, {"high_vol_breakout": True}

    # Baseline — everything passes → buyable.
    assert scanner._is_buyable(tr, stg, None, liq, vol, es) is True
    # Institutions selling → buy tier blocked …
    assert scanner._is_buyable(tr, stg, None, liq, vol, es, distribution=True) is False
    # … but setup_ready (watchlist) is unaffected — the name still shows.
    assert scanner._is_setup_ready(tr, stg, None, liq, es) is True


# ── _distribution_context: churn breakout vs clean breakout ──────────────────
def _df(close, high, low, vol, openp):
    n = len(close)
    return pd.DataFrame({"open": openp, "high": high, "low": low, "close": close,
                         "volume": vol},
                        index=pd.date_range("2025-01-01", periods=n, freq="D"))


def _breakout_df(close_loc="high", n=130, bo=120):
    """A volume-confirmed breakout; vary only the close LOCATION in the bar."""
    close = np.full(n, 100.0); high = np.full(n, 100.5)
    low = np.full(n, 99.5); vol = np.full(n, 1_000_000.0); openp = np.full(n, 100.0)
    for k, p in enumerate(range(bo - 6, bo)):
        close[p] = 100.0 + (k + 1) * 0.4
        high[p] = close[p] + 0.3; low[p] = close[p] - 0.3
        openp[p] = close[p]; vol[p] = 1_300_000.0
    close[bo] = 112.0; vol[bo] = 3_000_000.0
    if close_loc == "high":
        high[bo] = 112.5; low[bo] = 105.0; openp[bo] = 106.0   # close near the high
    else:
        high[bo] = 118.0; low[bo] = 111.5; openp[bo] = 117.0   # close near the low (churn)
    return _df(close, high, low, vol, openp)


def test_churn_breakout_is_flagged_selling():
    selling, reason, _ = scanner._distribution_context(_breakout_df("low"), None)
    assert selling is True
    assert "churn" in reason


def test_clean_breakout_not_flagged_regression():
    """REGRESSION: a breakout that closed STRONG (near the high) is institutions
    BUYING — it must NOT be blocked from the buy tier."""
    selling, reason, _ = scanner._distribution_context(_breakout_df("high"), None)
    assert selling is False
    assert reason is None


def test_climax_distribution_is_flagged_selling():
    n = 130
    close = np.full(n, 100.0); high = np.full(n, 100.5)
    low = np.full(n, 99.5); vol = np.full(n, 1_000_000.0); openp = np.full(n, 100.0)
    step = (130.0 - 100.0) / 15
    for k, p in enumerate(range(n - 15, n)):
        px = 100.0 + step * (k + 1)
        close[p] = px; high[p] = px + 0.4; low[p] = px - 0.4
        openp[p] = px - step * 0.5; vol[p] = 1_200_000.0
    p = n - 4                                             # one heavy-volume down day
    close[p] = close[p - 1] - 1.5
    high[p] = close[p] + 2.0; low[p] = close[p] - 0.5; openp[p] = close[p] + 1.2
    vol[p] = 3_500_000.0
    df = _df(close, high, low, vol, openp)
    assert cd.detect(df).get("is_distribution") is True   # sanity
    selling, reason, climax = scanner._distribution_context(df, None)
    assert selling is True and climax.get("read") == "distribution_underway"


def test_gate_threshold_stricter_than_display_warning():
    """The buy-tier gate (lower THIRD) is stricter than the chart's "suspect"
    warning (lower half) — so ordinary intraday fades stay buyable."""
    assert volume.BREAKOUT_GATE_CHURN_LOC < volume.BREAKOUT_CHURN_LOC
    assert volume.BREAKOUT_GATE_CHURN_LOC <= -0.3
