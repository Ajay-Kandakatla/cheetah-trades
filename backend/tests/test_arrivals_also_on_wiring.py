"""Wiring pin (Ajay 2026-10-12, his-call #8): the growth board AND the tags
endpoint attach `also_on` from the per-tab membership snapshot, each inside its
own guard, and the tab-membership hook in `chart_maps/board.py` sits right after
`out["tab"] = t` so it sees the SERVED block. A source grep, not behaviour —
`tests/test_chart_maps_membership.py` owns the behaviour."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_growth_api_attaches_also_on_in_both_sync_bodies():
    api = _src("growth/api.py")
    assert api.count("_mem.attach_also_on(arr)") == 2
    # Each call is guarded: a cold collection never takes the tab down.
    for m in re.finditer(r"_mem\.attach_also_on\(arr\)", api):
        before = api[max(0, m.start() - 200):m.start()]
        after = api[m.end():m.end() + 160]
        assert "try:" in before and "except Exception" in after


def test_board_hook_sits_after_the_served_tab_stamp():
    bp = _src("chart_maps/board.py")
    i = bp.index('out["tab"] = t\n')
    window = bp[i:i + 1400]        # the request dict names every board() parameter
    assert "_MB.record_board(t, out, request={" in window
    assert "try:" in window and "except Exception" in window


def test_NEGATIVE_the_hook_never_runs_before_the_tab_is_stamped():
    bp = _src("chart_maps/board.py")
    first_hook = bp.index("_MB.record_board(")
    stamp = bp.index('out["tab"] = t\n')
    assert stamp < first_hook


def test_the_30_day_window_is_kept():
    assert re.search(r"^NEW_GROWTH_DAYS\s*=\s*30\b", _src("growth/tracker.py"), re.M)
