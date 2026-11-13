"""📅 Long Term — the weekly digest push: composed, HELD (spec §3.9, [C9], WP-RUN, 2026-11-12).

Ajay 2026-11-12, verbatim: "… if something gets dropped let me know when to like is Sales drop or Stage 2 to Stage 3
or stage 4 changes."

Today's path: DIGEST_PUSH_MODE "off" → "push off", nothing claimed, nothing sent. The live path (WP-PUSH, HIS CALL #1)
is exercised with the mode monkeypatched: owner only, one send per week, never `send_to_all`. NEGATIVES throughout.
"""
from __future__ import annotations

import inspect
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from long_term_list import constants as C
from long_term_list import push as PUSH
from long_term_list import words as W
from tests.test_long_term_list_store import FakeColl

ET = ZoneInfo("America/New_York")
FRI = datetime(2026, 11, 13, 16, 40, tzinfo=ET)
SAT = datetime(2026, 11, 14, 10, 0, tzinfo=ET)


def _db():
    return {C.RUNS_COLL: FakeColl(C.RUNS_COLL), C.FORWARD_COLL: FakeColl(C.FORWARD_COLL),
            C.CLAIMS_COLL: FakeColl(C.CLAIMS_COLL)}


def _doc(rings=True, n_lines=3):
    lines = [f"⚠️ SYM{i} Stage 2 → Stage 3 (Topping) — last read in Stage 2 on 2026-11-12" for i in range(n_lines)]
    return {"_id": "2026-W46", "iso_week": "2026-W46",
            "digest": {"title": W.digest_title("2026-11-13", 1, 0, 0), "lines": lines, "rings": rings,
                       "items": [{"symbol": f"SYM{i}", "kind": "stage_drop", "text": t} for i, t in enumerate(lines)]}}


class Sender:
    def __init__(self):
        self.calls = []

    def __call__(self, *, owner, payload):
        self.calls.append((owner, payload))
        return {"sent": 1, "failed": 0, "total_targets": 1}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.setenv("OWNER_EMAIL", "owner@example.com")
    from push import sender

    def _never(*a, **k):
        raise AssertionError("send_to_all reached")
    monkeypatch.setattr(sender, "send_to_all", _never)


@pytest.fixture()
def live(monkeypatch):
    from push import subs
    real = subs.default_prefs
    monkeypatch.setattr(C, "DIGEST_PUSH_MODE", "live")
    monkeypatch.setattr(subs, "default_prefs", lambda: {**real(), C.DIGEST_KIND: False})


# ── today's path ──────────────────────────────────────────────────────────────────────────────────────────────
def test_mode_is_off_today():
    assert C.DIGEST_PUSH_MODE == "off"


def test_push_off_sends_nothing_and_claims_nothing():
    db, s = _db(), Sender()
    out = PUSH.send_digest(_doc(), FRI, db=db, send=s)
    assert out["state"] == "skipped" and out["reason"] == PUSH.R_OFF == "push off"
    assert s.calls == []                                              # NEG
    assert db[C.CLAIMS_COLL].calls == [] and db[C.CLAIMS_COLL].docs == {}   # NEG


def test_push_off_never_reads_prefs(monkeypatch):
    from push import subs

    def _boom():
        raise AssertionError("prefs read with the push off")
    monkeypatch.setattr(subs, "default_prefs", _boom)
    assert PUSH.send_digest(_doc(), FRI, db=_db(), send=Sender())["reason"] == "push off"


# ── the held live path ────────────────────────────────────────────────────────────────────────────────────────
def test_live_sends_once_to_the_owner_only(live):
    from push import subs
    db, s = _db(), Sender()
    first = PUSH.send_digest(_doc(), FRI, db=db, send=s)
    second = PUSH.send_digest(_doc(), FRI, db=db, send=s)
    assert first["state"] == "pushed" and second["reason"] == PUSH.R_CLAIMED
    assert len(s.calls) == 1
    owner, payload = s.calls[0]
    assert owner == subs._owner_email() == "owner@example.com"
    assert payload["kind"] == C.DIGEST_KIND and payload["url"] == C.DIGEST_URL
    assert payload["tag"] == f"{C.DIGEST_KIND}:2026-W46"
    assert db[C.CLAIMS_COLL].docs["digest:2026-W46"]["state"] == "pushed"


def test_live_nothing_to_ring_sends_nothing(live):
    db, s = _db(), Sender()
    assert PUSH.send_digest(_doc(rings=False), FRI, db=db, send=s)["reason"] == "nothing to ring"
    assert s.calls == [] and db[C.CLAIMS_COLL].docs == {}


def test_live_kind_not_registered_is_skipped(monkeypatch):
    monkeypatch.setattr(C, "DIGEST_PUSH_MODE", "live")
    s = Sender()
    assert PUSH.send_digest(_doc(), FRI, db=_db(), send=s)["reason"] == PUSH.R_KIND
    assert s.calls == []


def test_live_override_never_pushes(live, monkeypatch):
    monkeypatch.setenv("CHEETAH_IGNORE_HOLIDAY", "1")
    s = Sender()
    assert PUSH.send_digest(_doc(), FRI, db=_db(), send=s)["reason"] == PUSH.R_OVERRIDE
    assert s.calls == []


def test_live_closed_day_never_pushes(live):
    s = Sender()
    assert PUSH.send_digest(_doc(), SAT, db=_db(), send=s)["reason"] == "weekend"
    assert s.calls == []


def test_live_without_the_hook_is_skipped_before_any_claim(live, monkeypatch):
    from push import hooks
    monkeypatch.delattr(hooks, "notify_long_term_digest", raising=False)
    db = _db()
    assert PUSH.send_digest(_doc(), FRI, db=db)["reason"] == PUSH.R_NO_HOOK
    assert db[C.CLAIMS_COLL].docs == {}


def test_a_raising_sender_is_failed_not_raised(live):
    def _raise(*, owner, payload):
        raise RuntimeError("fcm down")
    out = PUSH.send_digest(_doc(), FRI, db=_db(), send=_raise)
    assert out["state"] == "failed"


def test_compose_caps_the_body():
    p = PUSH.compose(_doc(n_lines=3)["digest"], "2026-W46")
    assert p["body"].count("\n") == 2 and p["title"].startswith(C.MARK)
    long = {"title": "t", "lines": [str(i) for i in range(C.DIGEST_BODY_LINES + 5)], "items": []}
    body = PUSH.compose(long, "2026-W46")["body"].split("\n")
    assert len(body) == C.DIGEST_BODY_LINES + 1 and body[-1] == W.more_text(5)


def test_source_never_calls_send_to_all():
    src = inspect.getsource(PUSH)
    assert "send_to_all(" not in src and "import send_to_all" not in src
    assert "sender.send_to_all" not in src
