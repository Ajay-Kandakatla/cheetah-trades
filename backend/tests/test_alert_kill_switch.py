"""Retired-alert kill-switch — DISABLED_ALERT_KINDS hard-stops delivery.

Ajay 2026-06-13 pared notifications to: Minervini learning, buyable/Enter-zone,
portfolio, market open/close, and household. The retired market-scan kinds must
never be delivered, regardless of any per-device pref still set True. The guard
lives in push/subs.py so BOTH the Web Push path (sender) and the Mac SSE path
(mac_stream) are covered.
"""
from __future__ import annotations

from push import subs


def test_retired_kinds_short_circuit_before_db(monkeypatch):
    # For a disabled kind, delivery returns empty WITHOUT ever opening Mongo —
    # so it can't fire even for a device whose stored pref is still True.
    def boom():
        raise AssertionError("_get_db must not be reached for a disabled kind")
    monkeypatch.setattr(subs, "_get_db", boom)
    assert subs.list_subscriptions(filter_kind="volume_breakout") == []
    assert subs.list_subscriptions(filter_kind="price_alert") == []
    assert subs.list_mac_device_ids("a@b.com", filter_kind="scalp_tape") == set()


def test_kept_kinds_are_not_disabled():
    # The surviving surfaces (+ household) must NOT be in the denylist.
    # minervini_flashcards and the three vb_* kinds LEFT this list on
    # 2026-09-20 — see test_retired_kinds_2026_09_20.py.
    for k in (
        "pivot_alert", "position_alert",
        "market_hours_reminder",
        "todo_reminder", "todo_daily_digest", "house_daily",
    ):
        assert k not in subs.DISABLED_ALERT_KINDS, k


def test_retired_kinds_are_disabled():
    for k in (
        "sepa_new_candidate", "volume_breakout", "rising_momentum",
        "watchlist_breakout", "juggernaut_watchlist", "stage_breakdown",
        "watchlist_stage_breakdown", "morning_brief", "product_launch",
        "scalp_tape", "price_alert",
        # Ajay 2026-09-20: "Remove volleyball and learning of stocks I do dont
        # wanna see them they are spamming too much."
        "minervini_flashcards", "vb_workout", "vb_supplement", "vb_education",
    ):
        assert k in subs.DISABLED_ALERT_KINDS, k
