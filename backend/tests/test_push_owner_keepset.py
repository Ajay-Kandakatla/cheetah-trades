"""The owner's phone carries five kinds and nothing else (Ajay 2026-09-08).

"Also kill the tape burst and pankaj and also few others miscellaneous
notifications... I need just supply demand and also Sell signals and buy
signals accurately."

A NEW device registration used to inherit default_prefs() — every kind ON —
which is how his second phone ended up with 335 promo movers, 183 pivot alerts
and 105 flash cards in a week while the first phone was already tight. The
owner now starts from the keep-set; everyone else is untouched.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from push import subs   # noqa: E402


def test_keep_set_is_the_2026_09_09_four():
    """REPLACED 2026-09-09. Ajay: "Can you give me hot pull back alerts and
    chart pattern Alerts and also Sameday deman alerts please... Kill all
    other.. I just wanna these alerts.. Default turn these on from tomorrow."

    Asked whether the stop alerts on stocks he OWNS counted as "other", he kept
    those and dropped the todo reminders. What left: zone_bounce_alert,
    supply_break_alert, todo_reminder."""
    assert subs.OWNER_KEEP_SET == frozenset({
        "hot_pullback_alert", "pattern_alert", "demand_alert", "position_alert"})
    for gone in ("zone_bounce_alert", "supply_break_alert", "todo_reminder"):
        assert gone not in subs.OWNER_KEEP_SET, gone
    # every kept kind must exist in default_prefs or it sends to ZERO devices
    assert set(subs.OWNER_KEEP_SET) <= set(subs.default_prefs())

def test_owner_prefs_mute_everything_outside_the_keep_set():
    p = subs.owner_prefs()
    d = subs.default_prefs()
    assert set(p) == set(d), "same keys — a kind missing from prefs silently drops"
    on = {k for k, v in p.items() if v is True}
    assert on == set(subs.OWNER_KEEP_SET)
    # non-boolean settings ride through untouched (quiet-hours window)
    assert p["quiet_hours_start"] == d["quiet_hours_start"]
    assert p["quiet_hours_enabled"] is False
    # every kind that fired at him last week and is not S/D is off
    for k in ("promo_alert", "pivot_alert", "minervini_flashcards", "trade_flash",
              "market_hours_reminder", "vb_education", "house_scrape_failed"):
        assert p[k] is False, k


def test_a_new_owner_device_starts_tight_and_everyone_else_does_not(monkeypatch):
    monkeypatch.setenv("OWNER_EMAIL", "ajaykandakatla@gmail.com")
    owner = subs.prefs_for("AjayKandakatla@Gmail.com")          # case-insensitive
    assert {k for k, v in owner.items() if v is True} == set(subs.OWNER_KEEP_SET)
    other = subs.prefs_for("someone@else.com")
    assert other == subs.default_prefs()
    assert other["promo_alert"] is True, "other users keep the old defaults"
    assert subs.prefs_for(None) == subs.default_prefs()


def test_registration_paths_use_prefs_for_not_default_prefs():
    import inspect
    for fn in (subs.add_subscription, subs.add_mac_subscription):
        src = inspect.getsource(fn)
        assert "prefs or prefs_for(user_email)" in src, fn.__name__
        assert "prefs or default_prefs()" not in src, fn.__name__
