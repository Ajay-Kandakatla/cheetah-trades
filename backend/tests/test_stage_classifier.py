"""Behavioral + regression tests for the Minervini/Weinstein stage classifier.

Source of truth: Mark Minervini, *Trade Like a Stock Market Wizard* (2013),
Chapter 5 "Trading with the Trend," pp. 65-77.

Companion to the source-guard in tests/test_sepa_contracts.py
(``test_stage_classifier_outputs_locked``, which locks the four labels). This
file exercises the *behaviour* on synthetic OHLC series — each archetype is a
deterministic piecewise-linear close path engineered to land in one stage's
MA geometry, so the test is reproducible (no randomness, no live data).

The 2026-06-09 book audit fixed a real DRIFT: the geometric Stage 3 branch used
to require a *rising* 200-day MA (`s200 > s200_prev`). Book p.74 says the
opposite — in a top the 200-day "will lose upside momentum, flatten out, and
then roll over into a downtrend," and price "may undercut its 200-day." So a
topping stock whose 200-day had flattened/rolled over fell through to Stage 1
"Basing", masking the top. ``test_stage3_flat_200_rollover_is_topping_not_basing``
is the regression lock for that fix.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from sepa import stage


def _series(segments):
    """Build a close Series from (n_bars, start, end) linear segments."""
    out = []
    for n, a, b in segments:
        out += list(np.linspace(a, b, n, endpoint=False))
    return pd.Series(out, dtype=float)


def _df(close: pd.Series) -> pd.DataFrame:
    """Wrap a close series as an OHLCV frame (classify only reads `close`)."""
    return pd.DataFrame(
        {
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": pd.Series(np.ones(len(close)) * 1_000_000),
        }
    )


# ── Archetypes ────────────────────────────────────────────────────────────────
# Strong rising stacked advance — Stage 2.
STAGE2 = _series([(120, 50, 150), (120, 150, 210)])
# Fully inverted, falling — Stage 4.
STAGE4 = _series([(120, 200, 150), (120, 150, 80)])
# Decline then a low, flat base (post-Stage-4 neglect) — Stage 1.
STAGE1_BASE = _series([(120, 180, 90), (140, 90, 98)])
# Post-advance top: long advance, long plateau (this flattens the 200-day),
# then a mild rollover that loses the 50- and 150-day but stays within 10% of
# the 200-day, with 150-day still > 200-day. Old code => Stage 1 (wrong);
# fixed code => Stage 3. (Construction verified to produce slope-down 200-day.)
STAGE3_FLAT_TOP = _series([(60, 60, 140), (180, 140, 150), (45, 150, 135)])


def test_stage2_clean_advance():
    s = stage.classify(_df(STAGE2))
    assert s is not None and s["stage"] == 2 and s["label"] == "Advancing"
    assert s["slope_up"] is True


def test_stage4_decline():
    s = stage.classify(_df(STAGE4))
    assert s is not None and s["stage"] == 4 and s["label"] == "Decline"


def test_stage1_base_after_decline_is_not_topping():
    """A base that forms after a Stage-4 decline (stack recovering from
    inversion, 150-day <= 200-day) must stay Stage 1 — the s150 > s200 guard
    is what keeps the fixed Stage-3 branch from grabbing post-decline bases."""
    s = stage.classify(_df(STAGE1_BASE))
    assert s is not None and s["stage"] == 1 and s["label"] == "Basing"


def test_stage3_flat_200_rollover_is_topping_not_basing():
    """REGRESSION (book p.74, 2026-06-09 audit): a post-advance top whose
    200-day has flattened / rolled over — price below the 50-day, within 10%
    of the 200-day, 150-day still > 200-day — is Stage 3 Topping, NOT Stage 1
    Basing. Before the fix the rising-200-day requirement sent it to Stage 1."""
    df = _df(STAGE3_FLAT_TOP)

    # Precondition: confirm this series really is the flat/rolling-over geometry
    # the book calls a top (otherwise the test would silently stop covering it).
    c = df["close"]
    s50 = float(c.rolling(50).mean().iloc[-1])
    s150 = float(c.rolling(150).mean().iloc[-1])
    s200 = float(c.rolling(200).mean().iloc[-1])
    s200_prev = float(c.rolling(200).mean().iloc[-22])
    p = float(c.iloc[-1])
    assert p < s50, "precondition: price should have lost the 50-day"
    assert p > s200 * 0.9, "precondition: price within 10% of the 200-day"
    assert s150 > s200, "precondition: prior Stage-2 stack intact (150 > 200)"
    assert s200 <= s200_prev, "precondition: 200-day flat/rolling over (NOT rising)"

    s = stage.classify(df)
    assert s is not None
    assert s["stage"] == 3, f"flat-200 rollover must be Stage 3 (Topping), got {s['stage']}"
    assert s["label"] == "Topping"


def test_stage3_branch_never_returns_stage2():
    """BUY-SIDE SAFETY: the fixed Stage-3 branch must never yield Stage 2 (which
    would manufacture a buy — is_buyable/ENTER require stage == 2). Sweep a grid
    of post-advance rollover depths; any classified result that is the Topping
    branch must be stage 3, and none of these (price < 50-day) may be stage 2."""
    for plateau in (120, 150, 180):
        for drop in (0.88, 0.90, 0.92, 0.94):
            s = stage.classify(_df(_series([(60, 60, 140), (plateau, 140, 150), (45, 150, 150 * drop)])))
            if s is None:
                continue
            assert s["stage"] != 2, f"price-below-50 rollover must never be Stage 2 (got {s})"
