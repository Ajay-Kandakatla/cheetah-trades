"""The phantom bar that made every pre-market surface read FLAT (2026-09-14).

Ajay, looking at Hot Sectors at 09:22 ET: *"This can't be true all of them have
0.1%?"* — every member of every group showed +0.1%, on the morning AI names
were down 7% in the pre-market.

WHAT HAPPENED. A pre-session snapshot echoes the PRIOR session's completed
aggregate into a bar stamped with TODAY's date. `_drop_phantom_tail` exists to
strip exactly that, and it required close AND volume to be byte-identical. Both
legs of that test failed in the wild:

  AMKR  Fri 51.73 / 3,064,207.847861   ->  today 51.73 / 3,064,208.0
  NVDA  Fri 218.29 / 89,060,140.139811 ->  today 218.29 / 89,058,725.0

AMKR differed by a float round-trip through the cache (0.15 shares); NVDA by a
1,415-share late restatement of Friday's aggregate. Neither is `==`, so the
placeholder survived, and every `trailing_return(bars, 1)` came back exactly
0.00 — which is why every row rendered the same number.

It also MASKED the live overlay: `with_today_bar` was correct all along and
would have appended the real pre-market print, but it no-ops when the frame
already holds today's date. Fixing the guard fixed the whole chain in one move.
"""
from __future__ import annotations

import pandas as pd
import pytest

from sepa import prices


def _frame(rows):
    idx = [pd.Timestamp(d) for d, *_ in rows]
    return pd.DataFrame(
        [{"open": o, "high": h, "low": l, "close": c, "volume": v}
         for _, o, h, l, c, v in rows], index=idx)


def test_the_AMKR_shape_a_rounded_volume_echo():
    """The float round-trip. 0.15 shares out of 3 million is not a session."""
    df = _frame([("2026-09-10", 49.0, 50.0, 48.5, 49.53, 3168967.083387),
                 ("2026-09-11", 50.0, 52.0, 49.8, 51.73, 3064207.847861),
                 ("2026-09-14", 51.73, 51.73, 51.73, 51.73, 3064208.0)])
    out = prices._drop_phantom_tail(df)
    assert len(out) == 2
    assert str(out.index[-1].date()) == "2026-09-11"


def test_the_NVDA_shape_a_late_restatement_1415_shares_apart():
    """The one a 'rounding tolerance' would still miss — which is why the CLOSE
    carries the test and the volume only has to be close."""
    df = _frame([("2026-09-10", 218.0, 219.0, 217.0, 218.36, 105768001.014511),
                 ("2026-09-11", 218.3, 219.5, 217.8, 218.29, 89060140.139811),
                 ("2026-09-14", 218.29, 218.29, 218.29, 218.29, 89058725.0)])
    out = prices._drop_phantom_tail(df)
    assert len(out) == 2, "a 1,415-share restatement is still the same session"


def test_NEGATIVE_a_real_session_that_closes_flat_is_KEPT():
    """The guard must not eat a genuine unchanged close. A real session brings
    its own volume; here it is 30% different, which no echo ever is."""
    df = _frame([("2026-09-10", 49.0, 50.0, 48.5, 51.73, 3168967.0),
                 ("2026-09-11", 50.0, 52.0, 49.8, 51.73, 4300000.0)])
    assert len(prices._drop_phantom_tail(df)) == 2


def test_NEGATIVE_a_different_close_is_always_kept():
    """One cent of difference is a session. The close is the binding leg."""
    df = _frame([("2026-09-11", 50.0, 52.0, 49.8, 51.73, 3064207.847861),
                 ("2026-09-14", 51.73, 51.74, 51.72, 51.74, 3064208.0)])
    assert len(prices._drop_phantom_tail(df)) == 2


def test_it_drops_at_most_ONE_bar_and_survives_a_short_frame():
    """Conservative, as it always was: never a cascade, never a crash."""
    df = _frame([("2026-09-10", 1, 1, 1, 51.73, 3064207.0),
                 ("2026-09-11", 1, 1, 1, 51.73, 3064207.5),
                 ("2026-09-14", 1, 1, 1, 51.73, 3064208.0)])
    assert len(prices._drop_phantom_tail(df)) == 2      # one bar, not two
    assert prices._drop_phantom_tail(None) is None
    assert len(prices._drop_phantom_tail(_frame([("2026-09-11", 1, 1, 1, 2.0, 5.0)]))) == 1


def test_the_tolerance_is_stated_in_the_source_not_guessed():
    """SOURCE GUARD. The 0.5% volume band is a deliberate call — two real
    sessions sharing a byte-identical close AND a volume within 0.5% does not
    happen — and the reasoning must ride with it."""
    import inspect
    src = inspect.getsource(prices._drop_phantom_tail)
    assert "5e-3" in src
    assert "1,415" in src or "restatement" in src
