"""🩺 ops_alert — the push kind + POST /admin/ops/alert behind the Mac's Docker
watchdog (ops/docker_watchdog.py, 2026-10-06; Ajay approved the watchdog push).

Pinned: the kind is registered (default_prefs, OWNER_KEEP_SET, PERSONAL_KINDS),
hooks.notify_ops only ever targets push.hooks.ADMIN_EMAIL with a closed condition
set, and the route is a strict-admin 404 stealth gate with a closed body, fixed
limits and a 6/h/condition cap. No Mongo, no device: list_subscriptions and
send_to_user are stubbed.
"""
from __future__ import annotations

import inspect
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI                      # noqa: E402
from fastapi.testclient import TestClient        # noqa: E402

from market_hours import gate                    # noqa: E402
from push import hooks, ops_api, sender, subs    # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BANNED = ("boun" + "ce", "fa" + "ke")
LABOR_DAY = datetime(2026, 9, 7, 10, 0, tzinfo=gate._ET)
SATURDAY = datetime(2026, 9, 5, 10, 0, tzinfo=gate._ET)
EIGHT = {"forwarder_high", "forwarder_growth", "docker_down", "docker_restored",
         "backend_restarted", "battery_low", "watchdog_error", "test"}
GOOD = {"condition": "docker_down", "title": "🛑 Docker is down", "body": "Docker's backend is not running."}


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def env(monkeypatch):
    sends = []
    state = {"targets": [{"endpoint": "e1"}], "held": [{"endpoint": "e1"}]}

    def fake_list(filter_kind=None, user_email=None, *, honor_quiet_hours=True):
        state.setdefault("list_calls", []).append((filter_kind, user_email, honor_quiet_hours))
        return list(state["targets"] if honor_quiet_hours else state["held"])

    def fake_send(user_email, payload, kind=None):
        sends.append((user_email, payload, kind))
        return {"sent": 1, "failed": 0, "total_targets": 1}

    monkeypatch.setattr(subs, "list_subscriptions", fake_list)
    monkeypatch.setattr(sender, "send_to_user", fake_send)
    clock = Clock()
    monkeypatch.setattr(ops_api, "_now", clock)
    monkeypatch.setattr(ops_api, "_SENT", {})
    app = FastAPI()
    app.include_router(ops_api.router)
    return {"client": TestClient(app), "sends": sends, "state": state, "clock": clock}


def post(env, body, email=None):
    headers = {} if email is False else {"X-User-Email": email or hooks.ADMIN_EMAIL}
    return env["client"].post("/admin/ops/alert", json=body, headers=headers)


# --------------------------------------------------------------------------- kind wiring
def test_O1_default_prefs_ship_it_on():
    assert subs.default_prefs()["ops_alert"] is True


def test_O2_owner_keep_set_keeps_it():
    assert "ops_alert" in subs.OWNER_KEEP_SET
    assert subs.owner_prefs()["ops_alert"] is True


def test_O3_personal_kind_rings_on_closed_days():
    assert "ops_alert" in gate.PERSONAL_KINDS
    assert "ops_alert" not in gate.MARKET_ALERT_KINDS
    assert gate.should_drop_kind("ops_alert", SATURDAY) is None
    assert gate.should_drop_kind("ops_alert", LABOR_DAY) is None
    assert gate.should_drop_kind("pivot_alert", SATURDAY) == "weekend", "the gate itself still works"


def test_O4_NEGATIVE_not_a_disabled_kind():
    assert "ops_alert" not in subs.DISABLED_ALERT_KINDS


def test_O5_closed_condition_set():
    assert hooks.OPS_CONDITIONS == frozenset(EIGHT)


# --------------------------------------------------------------------------- notify_ops
def test_O6_one_send_to_the_admin(env):
    r = hooks.notify_ops("docker_down", "t", "b")
    assert r["sent"] == 1
    assert len(env["sends"]) == 1
    email, payload, kind = env["sends"][0]
    assert email == hooks.ADMIN_EMAIL and kind == "ops_alert"
    assert payload["tag"] == "ops-docker_down" and payload["url"] == "/alerts"
    assert payload["kind"] == "ops_alert" and payload["condition"] == "docker_down"
    assert all(c[1] == hooks.ADMIN_EMAIL and c[0] == "ops_alert" for c in env["state"]["list_calls"])


def test_O7_NEGATIVE_no_target_and_quiet_hours_write_nothing(env):
    env["state"]["targets"], env["state"]["held"] = [], []
    r = hooks.notify_ops("docker_down", "t", "b")
    assert r == {"sent": 0, "failed": 0, "total_targets": 0, "skipped": "no_target"}
    env["state"]["held"] = [{"endpoint": "e1"}]
    r = hooks.notify_ops("docker_down", "t", "b")
    assert r["skipped"] == "quiet_hours" and r["sent"] == 0
    assert env["sends"] == []


def test_O8_NEGATIVE_unknown_condition_raises(env):
    with pytest.raises(ValueError):
        hooks.notify_ops("pivot_alert", "t", "b")
    assert env["sends"] == []


# --------------------------------------------------------------------------- endpoint
def test_O9_admin_valid_body_delivers(env):
    r = post(env, GOOD)
    assert r.status_code == 200
    js = r.json()
    assert js["ok"] is True and js["delivered"] is True
    assert (js["sent"], js["failed"], js["total_targets"], js["skipped"]) == (1, 0, 1, None)
    assert env["sends"][0][0] == hooks.ADMIN_EMAIL


def test_O10_admin_header_mixed_case(env):
    r = post(env, GOOD, email=hooks.ADMIN_EMAIL.upper())
    assert r.status_code == 200


def test_O11_NEGATIVE_non_admin_is_404(env):
    r = post(env, GOOD, email="someone@example.com")
    assert r.status_code == 404
    assert env["sends"] == []


def test_O12_NEGATIVE_non_admin_garbage_is_404_not_422(env):
    r = post(env, {"garbage": 1, "kind": "x"}, email="someone@example.com")
    assert r.status_code == 404
    assert env["sends"] == []


def test_O13_NEGATIVE_no_auth_is_401(env):
    r = post(env, GOOD, email=False)
    assert r.status_code == 401
    assert env["sends"] == []


def test_O14_NEGATIVE_unknown_condition_is_422(env):
    r = post(env, dict(GOOD, condition="pivot_alert"))
    assert r.status_code == 422
    assert env["sends"] == []


def test_O15_NEGATIVE_caller_cannot_pick_kind_or_recipient(env):
    for extra in ({"kind": "pivot_alert"}, {"user_email": "x@y.z"}):
        r = post(env, dict(GOOD, **extra))
        assert r.status_code == 422, extra
    assert env["sends"] == []


def test_O16_NEGATIVE_limits_are_rejected_not_truncated(env):
    for bad in (dict(GOOD, title="x" * 81), dict(GOOD, body="y" * 281), dict(GOOD, title=""),
                {"condition": "test", "title": "t"}):
        assert post(env, bad).status_code == 422, bad
    assert env["sends"] == []
    assert post(env, dict(GOOD, title="x" * 80, body="y" * 280)).status_code == 200


def test_O17_rate_cap_per_condition_per_hour(env):
    for _ in range(ops_api.OPS_RATE_MAX_PER_HOUR):
        assert post(env, GOOD).status_code == 200
    r = post(env, GOOD)
    assert r.status_code == 429
    js = r.json()
    assert js["ok"] is False and js["error"] == "rate_limited" and js["retry_after_sec"] >= 1
    assert len(env["sends"]) == 6
    assert post(env, dict(GOOD, condition="battery_low")).status_code == 200
    env["clock"].t += 3601
    assert post(env, GOOD).status_code == 200
    assert ops_api.OPS_RATE_MAX_PER_HOUR == 6


def test_O18_no_targets_is_200_not_delivered(env):
    env["state"]["targets"], env["state"]["held"] = [], []
    r = post(env, GOOD)
    assert r.status_code == 200
    js = r.json()
    assert js["delivered"] is False and js["skipped"] == "no_target"
    assert set(js) == {"ok", "delivered", "sent", "failed", "total_targets", "skipped"}


def test_O18b_NEGATIVE_send_failure_is_500_without_detail(env, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("SECRET_VALUE_FROM_ENV")
    monkeypatch.setattr(hooks, "notify_ops", boom)
    r = post(env, GOOD)
    assert r.status_code == 500
    assert r.json() == {"ok": False, "error": "send_failed"}
    assert "SECRET" not in r.text


def test_O19_route_is_mounted_on_push_recent_router():
    from push import recent
    assert "/admin/ops/alert" in {getattr(r, "path", None) for r in recent.router.routes}


def test_O20_one_admin():
    from ollama_chat import api as ollama_api
    assert hooks.ADMIN_EMAIL == ollama_api.PRIMARY_ADMIN_EMAIL


def test_O21_NEGATIVE_no_banned_words():
    texts = [inspect.getsource(hooks.notify_ops), inspect.getsource(ops_api)]
    kinds = (ROOT / "frontend" / "src" / "lib" / "alertKinds.ts").read_text()
    line = [ln for ln in kinds.splitlines() if ln.strip().startswith("ops_alert:")]
    assert line, "alertKinds.ts must register ops_alert"
    texts += line
    for t in texts:
        for w in BANNED:
            assert w not in t.lower(), w


def test_O22_NEG_an_all_spaces_title_or_body_is_rejected_before_sending(env):
    for body in ({**GOOD, "title": "   "}, {**GOOD, "body": " \t "}):
        r = post(env, body)
        assert r.status_code == 422, body
    assert env["sends"] == []
    r = post(env, {**GOOD, "title": "  🛑 Docker is down  "})
    assert r.status_code == 200 and env["sends"], "a padded title still sends, stripped"

