"""todos.reminder.fire_due gives up after MAX_NOTIFY_ATTEMPTS (2026-09-07).

Measured on Labor Day 2026: 34,441 push_history rows for todo_reminder in one
day, every one sent=0 — Vineetha's phone had dropped its push subscription, so
each due todo failed to deliver and was retried every minute forever
(4.42M silent rows in total). Three strikes, then the todo is marked notified.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from todos import reminder, store  # noqa: E402


def _todo(i="64f000000000000000000001", owner="gandurivineetha@gmail.com"):
    return {"_id": i, "user_email": owner, "text": "💧 Hydrate"}


def _wire(monkeypatch, *, delivered: bool, attempts_seq):
    from sepa import notify
    marked, bumped, sends = [], [], []
    seq = iter(attempts_seq)
    monkeypatch.setattr(store, "find_due_reminders", lambda limit=50: [_todo()])
    monkeypatch.setattr(store, "mark_notified", lambda tid: marked.append(tid))
    monkeypatch.setattr(store, "bump_notify_attempts", lambda tid: bumped.append(tid) or next(seq))
    monkeypatch.setattr(notify, "send_alert", lambda **kw: sends.append(kw) or delivered)
    return marked, bumped, sends


def test_delivered_reminder_is_marked_without_counting_an_attempt(monkeypatch):
    marked, bumped, sends = _wire(monkeypatch, delivered=True, attempts_seq=[1])
    out = reminder.fire_due()
    assert out == {"checked": 1, "fired": 1, "skipped_no_owner": 0, "gave_up": 0}
    assert marked == ["64f000000000000000000001"] and bumped == []
    assert sends[0]["user_email"] == "gandurivineetha@gmail.com" and sends[0]["kind"] == "todo_reminder"


def test_undeliverable_reminder_retries_twice_then_gives_up(monkeypatch):
    marked, bumped, sends = _wire(monkeypatch, delivered=False, attempts_seq=[1, 2, 3])
    assert reminder.fire_due()["gave_up"] == 0
    assert reminder.fire_due()["gave_up"] == 0
    assert marked == []                                   # still retrying
    out = reminder.fire_due()
    assert out["gave_up"] == 1 and out["fired"] == 0
    assert marked == ["64f000000000000000000001"]          # third strike
    assert len(bumped) == 3 and len(sends) == 3


def test_cap_is_three():
    assert reminder.MAX_NOTIFY_ATTEMPTS == 3


def test_missing_owner_is_still_marked_without_a_send(monkeypatch):
    from sepa import notify
    marked, sends = [], []
    monkeypatch.setattr(store, "find_due_reminders", lambda limit=50: [_todo(owner="")])
    monkeypatch.setattr(store, "mark_notified", lambda tid: marked.append(tid))
    monkeypatch.setattr(notify, "send_alert", lambda **kw: sends.append(kw) or True)
    out = reminder.fire_due()
    assert out["skipped_no_owner"] == 1 and sends == [] and marked == ["64f000000000000000000001"]
