"""Locks the gentle weekly connect nudge (todos/connect_nudge.py).

One suggestion at a time, rotating; links are https-only (no dead/fabricated
URLs). 2026-06-03 replacement for the over-aggressive setup.
"""
from todos.connect_nudge import SUGGESTIONS, pick_for_week


def test_rotation_cycles_through_list():
    assert pick_for_week(0) is SUGGESTIONS[0]
    assert pick_for_week(1) is SUGGESTIONS[1]
    assert pick_for_week(len(SUGGESTIONS)) is SUGGESTIONS[0]      # wraps


def test_one_at_a_time_and_safe_links():
    assert len(SUGGESTIONS) >= 6
    for s in SUGGESTIONS:
        assert s.get("text")
        u = s.get("url")
        assert u is None or u.startswith("https://")              # no http/dead schemes
