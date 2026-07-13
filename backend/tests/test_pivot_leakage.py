"""sepa/pivot_leakage.py — the shared leaky-pivot read.

The pure pivot_leaky() cases live in tests/test_auto_entry.py (the engine
imports the same function). This file locks the SCANNER side: the
leakage_block() df adapter and its always-full JSON shape, so the SEPA
Global demotion + general-page chip can rely on the field.

Run: cd backend && .venv/bin/python -m pytest tests/test_pivot_leakage.py -q
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import pivot_leakage as PL


def _df(pivot=100.0, leak_days=(), n=12):
    """n completed bars, oldest->newest; leak_days are bars-ago (1 = last)."""
    rows = []
    for ago in range(n, 0, -1):
        if ago in leak_days:
            rows.append({"high": pivot + 1.0, "close": pivot - 1.0})
        else:
            rows.append({"high": pivot - 2.0, "close": pivot - 3.0})
    return pd.DataFrame(rows)


def test_leakage_block_flags_two_recent_leaks():
    blk = PL.leakage_block(_df(leak_days={2, 4}), 100.0)
    assert blk == {"leaky": True, "leaks": 2, "last_leak_bars_ago": 2}


def test_leakage_block_quiet_and_stale_pivots_read_clean():
    assert PL.leakage_block(_df(), 100.0)["leaky"] is False
    stale = PL.leakage_block(_df(leak_days={7, 9}), 100.0)
    assert stale["leaky"] is False and stale["leaks"] == 2


def test_leakage_block_lookback_window_bounds():
    # Leaks older than the 10-bar lookback are invisible.
    blk = PL.leakage_block(_df(leak_days={11, 12}, n=12), 100.0)
    assert blk["leaks"] == 0 and blk["leaky"] is False


def test_leakage_block_always_full_shape_on_garbage():
    for df, pivot in ((None, 100.0), (_df(), None), (_df(), 0),
                      (pd.DataFrame(), 100.0)):
        blk = PL.leakage_block(df, pivot)
        assert set(blk) == {"leaky", "leaks", "last_leak_bars_ago"}
        assert blk["leaky"] is False


def test_scanner_stamps_the_field_on_rows_with_a_setup():
    """Source-level wire check (a full scan needs network): both scan paths
    must stamp pivot_leakage next to entry_setup via the SHARED module."""
    path = os.path.join(os.path.dirname(__file__), "..", "sepa", "scanner.py")
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    assert src.count('"pivot_leakage": (pivot_leakage.leakage_block(') == 2, (
        "scanner must stamp pivot_leakage in BOTH scan paths (full + fast)")
