"""Web Push Urgency for the kinds he keeps on his phone (2026-11-24).

Ajay: "also i am not getting the alerts on phone". push_history 11-23: every 🚩 push was accepted for all 4
devices, his iPhone's receipts came back 10-33 min late in batches and whole stretches never arrived. The
sender set no Urgency header. Now push/subs.OWNER_KEEP_SET kinds go "high"; everything else is unchanged.
"""
from __future__ import annotations

import sys
import types

import pytest

from push import sender as S
from push import subs


def test_urgent_kinds_are_the_keep_set_itself_never_retyped():
    assert S.URGENT_KINDS is subs.OWNER_KEEP_SET


@pytest.mark.parametrize("kind", sorted(subs.OWNER_KEEP_SET))
def test_every_kept_kind_goes_high(kind):
    assert S.urgency_for(kind) == "high"


@pytest.mark.parametrize("kind", [None, "", "tape_burst_chartmaps", "trade_flash", "pivot_alert", "todo_reminder",
                                  "GAJJALA_SETUP", "gajjala_setup "])
def test_negative_other_kinds_get_no_header(kind):
    assert S.urgency_for(kind) is None


def _fake_webpush(monkeypatch):
    calls = []
    mod = types.ModuleType("pywebpush")
    mod.webpush = lambda **kw: calls.append(kw)
    monkeypatch.setitem(sys.modules, "pywebpush", mod)
    monkeypatch.setattr(S, "_vapid_obj", lambda: object())
    return calls


SUB = {"endpoint": "https://web.push.apple.com/x", "keys": {"p256dh": "a", "auth": "b"}}


def test_send_one_puts_the_urgency_header_on_the_request(monkeypatch):
    calls = _fake_webpush(monkeypatch)
    assert S._send_one(SUB, {"title": "t"}, urgency="high") is True
    assert calls[0]["headers"] == {"Urgency": "high"}
    assert calls[0]["ttl"] == 3600


def test_negative_a_normal_push_sends_no_header_exactly_as_before(monkeypatch):
    calls = _fake_webpush(monkeypatch)
    assert S._send_one(SUB, {"title": "t"}) is True
    assert calls[0]["headers"] is None


def _capture_fan_out(monkeypatch):
    seen = []

    def fan(targets, payload, **kw):
        seen.append(kw)
        return {"sent": 0, "failed": 0, "total_targets": 0}, "pid", []

    monkeypatch.setattr(S, "_fan_out", fan)
    monkeypatch.setattr(subs, "list_subscriptions", lambda **kw: [])
    from market_hours import gate
    monkeypatch.setattr(gate, "should_drop_kind", lambda kind: None)
    from push import history
    monkeypatch.setattr(history, "record", lambda *a, **k: None)
    return seen


def test_send_to_user_and_all_pass_high_for_a_kept_kind(monkeypatch):
    seen = _capture_fan_out(monkeypatch)
    S.send_to_user("o@x", {"title": "🚩"}, kind="gajjala_setup")
    S.send_to_all({"title": "🧠"}, kind="gajjala_potential")
    assert seen == [{"urgency": "high"}, {"urgency": "high"}]


def test_negative_send_paths_pass_no_kwarg_for_other_kinds(monkeypatch):
    seen = _capture_fan_out(monkeypatch)
    S.send_to_user("o@x", {"title": "x"}, kind="tape_burst_chartmaps")
    S.send_to_all({"title": "x"}, kind=None)
    assert seen == [{}, {}]


def test_negative_the_device_payload_never_carries_an_urgency_key(monkeypatch):
    got = []
    monkeypatch.setattr(S, "_send_one", lambda sub, payload, **kw: got.append((payload, kw)) or True)
    caller = {"title": "🚩", "items": [1, 2]}
    S._fan_out([SUB], caller, urgency="high")
    payload, kw = got[0]
    assert kw == {"urgency": "high"}
    assert "urgency" not in {k.lower() for k in payload}
    assert "items" not in payload and caller == {"title": "🚩", "items": [1, 2]}
