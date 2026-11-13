"""📅 Long Term — the weekly digest push is LIVE (pkzone spec §3.5, [C6], 2026-11-12).

Ajay 2026-11-12, verbatim: "Weekly and if something gets dropped let me know when to like is Sales drop or Stage 2 to
Stage 3 or stage 4 changes." ONE kind `long_term`, hook `notify_long_term`, ring set unchanged, body cap unchanged,
one push per ISO week. The push-hours window reads the WALL clock at send time (`clock=` / `push._wall_et`, never the
real clock in a test), not the weekly run's start clock. NEGATIVES throughout.
"""
from __future__ import annotations

import inspect
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from long_term_list import constants as C
from long_term_list import notices as N
from long_term_list import push as PUSH
from long_term_list import words as W
from tests.test_long_term_list_store import FakeColl

ET = ZoneInfo("America/New_York")


def fri(hh, mm):
    return datetime(2026, 11, 13, hh, mm, tzinfo=ET)


SAT = datetime(2026, 11, 14, 10, 0, tzinfo=ET)


def _db():
    return {C.RUNS_COLL: FakeColl(C.RUNS_COLL), C.FORWARD_COLL: FakeColl(C.FORWARD_COLL),
            C.CLAIMS_COLL: FakeColl(C.CLAIMS_COLL)}


def _doc(rings=True, n_lines=9):
    lines = [f"⚠️ SYM{i} Stage 2 → Stage 3 (Topping)" for i in range(n_lines)]
    return {"_id": "2026-W46", "iso_week": "2026-W46",
            "digest": {"title": W.digest_title("2026-11-13", n_lines, 0, 0), "lines": lines, "rings": rings,
                       "items": [{"symbol": f"SYM{i}", "kind": "stage_drop", "text": t} for i, t in enumerate(lines)]}}


class Sender:
    def __init__(self):
        self.calls = []

    def __call__(self, *, owner, payload):
        self.calls.append((owner, payload))
        return {"sent": 1, "failed": 0, "total_targets": 1}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    from push import sender, subs
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.setattr(subs, "_owner_email", lambda: "owner@example.com")
    real = subs.default_prefs
    monkeypatch.setattr(subs, "default_prefs", lambda: {**real(), C.KIND: False})

    def _never(*a, **k):
        raise AssertionError("send_to_all reached")
    monkeypatch.setattr(sender, "send_to_all", _never)
    monkeypatch.setattr(PUSH, "_wall_et", lambda: fri(17, 0))


def test_mode_is_live_with_his_sentence_on_the_line():
    assert C.DIGEST_PUSH_MODE == "live"
    src = inspect.getsource(C)
    line = next(ln for ln in src.splitlines() if ln.startswith("DIGEST_PUSH_MODE = "))
    assert line.split("#", 1)[1].strip().startswith(
        'Ajay 2026-11-12: "Weekly and if something gets dropped let me know when to like is Sales drop or Stage 2 '
        'to Stage 3 or stage 4 changes."')
    zline = next(ln for ln in src.splitlines() if ln.startswith("ZONE_PUSH_MODE = "))
    assert 'Ajay 2026-11-12: "add an alert list when stocks reach Pankaj\'s zones' in zline


def test_rings_one_send_capped_body_no_items():
    db, s = _db(), Sender()
    out = PUSH.send_digest(_doc(), fri(16, 40), db=db, send=s)
    assert out["state"] == "pushed" and len(s.calls) == 1
    owner, p = s.calls[0]
    assert owner == "owner@example.com" and p["kind"] == "long_term" and p["tag"] == "long_term:2026-W46"
    body = p["body"].split("\n")
    assert len(body) == C.DIGEST_BODY_LINES + 1 and body[-1] == W.more_text(9 - C.DIGEST_BODY_LINES)
    assert "items" not in p


def test_NEGATIVE_quiet_week_second_call_and_saturday():
    db, s = _db(), Sender()
    assert PUSH.send_digest(_doc(rings=False), fri(16, 40), db=db, send=s)["reason"] == "nothing to ring"
    assert s.calls == []
    PUSH.send_digest(_doc(), fri(16, 40), db=db, send=s)
    assert PUSH.send_digest(_doc(), fri(16, 50), db=db, send=s)["reason"] == "already pushed this week"
    assert len(s.calls) == 1
    assert PUSH.send_digest(_doc(), SAT, db=_db(), send=s)["reason"] == "weekend" and len(s.calls) == 1


def test_hook_resolves_notify_long_term_only(monkeypatch):
    from push import hooks
    marker = object()
    monkeypatch.setattr(hooks, "notify_long_term", marker, raising=False)
    monkeypatch.setattr(hooks, "notify_long_term_digest", object(), raising=False)
    assert PUSH._hook() is marker                                         # NEG: never the old digest name
    monkeypatch.delattr(hooks, "notify_long_term")
    assert PUSH._hook() is None


def test_ring_set_unchanged_and_a_zone_event_alone_never_rings():
    assert C.RING_KINDS == ("stage_drop", "sales_drop", "started_moving")
    zone_only = [{"kind": "zone", "symbol": "TSM", "text": W.zone_event_text("TSM", "Agg", 400, 410, "2026-11-13"),
                  "rings": False}]
    d = N.digest(zone_only, {}, "2026-11-13")
    assert d["rings"] is False
    db, s = _db(), Sender()
    assert PUSH.send_digest({"_id": "2026-W46", "iso_week": "2026-W46", "digest": d}, fri(16, 40), db=db,
                            send=s)["reason"] == "nothing to ring" and s.calls == []


# ── [C6] the window reads the wall clock at send time ───────────────────────────────────────────────────────────
def test_c6_run_clock_inside_wall_clock_after_hours_is_refused_before_the_claim():
    db, s = _db(), Sender()
    out = PUSH.send_digest(_doc(), fri(19, 55), db=db, send=s, clock=lambda: fri(20, 1))
    assert out["reason"] == PUSH.R_WINDOW == "outside the app's push hours"
    assert s.calls == [] and db[C.CLAIMS_COLL].docs == {}                  # NEG: no claim written


@pytest.mark.parametrize("now", [fri(19, 55), fri(20, 30)])
def test_NEGATIVE_c6_the_window_never_reads_the_run_clock(now):
    s = Sender()
    out = PUSH.send_digest(_doc(), now, db=_db(), send=s, clock=lambda: fri(19, 58))
    assert out["state"] == "pushed" and len(s.calls) == 1


def test_c6_default_clock_is_push_wall_et(monkeypatch):
    s = Sender()
    monkeypatch.setattr(PUSH, "_wall_et", lambda: fri(20, 1))
    assert PUSH.send_digest(_doc(), fri(16, 40), db=_db(), send=s)["reason"] == PUSH.R_WINDOW and s.calls == []
    monkeypatch.setattr(PUSH, "_wall_et", lambda: fri(17, 0))
    assert PUSH.send_digest(_doc(), fri(16, 40), db=_db(), send=s)["state"] == "pushed" and len(s.calls) == 1


def test_pushed_text_follows_the_week():
    assert W.pushed_text(rings=True) == "This week's digest rang — one push to your phone when allowed."
    assert W.pushed_text(rings=False) == "Nothing dropped or started moving this week — no push."
    assert W.pushed_text().startswith("One phone push per week")


def test_NEGATIVE_pushed_text_off(monkeypatch):
    monkeypatch.setattr(C, "DIGEST_PUSH_MODE", "off")
    assert W.pushed_text(rings=True) == "Phone push is off — this digest shows here only."


# ── REFIX 2026-11-13: the served digest line never claims delivery ─────────────────────────────────────────────
# The GET builds pushed_text from the run doc only; send_digest's result lives on the claim doc. A refused week
# (outside push hours, no phone, failed send, kind not registered) keeps digest.rings True on the run doc.
def _refused(monkeypatch, case):
    from push import subs
    s = Sender()
    if case == "window":
        res = PUSH.send_digest(_doc(), fri(16, 40), db=_db(), send=s, clock=lambda: fri(20, 1))
    elif case == "no_target":
        res = PUSH.send_digest(_doc(), fri(16, 40), db=_db(), clock=lambda: fri(17, 0),
                               send=lambda **k: {"sent": 0, "failed": 0, "total_targets": 0})
    elif case == "failed":
        def boom(**k):
            raise RuntimeError("x")
        res = PUSH.send_digest(_doc(), fri(16, 40), db=_db(), send=boom, clock=lambda: fri(17, 0))
    else:
        monkeypatch.setattr(subs, "default_prefs", lambda: {})
        res = PUSH.send_digest(_doc(), fri(16, 40), db=_db(), send=s, clock=lambda: fri(17, 0))
    return res, s


@pytest.mark.parametrize("case,want", [("window", ("skipped", PUSH.R_WINDOW)), ("no_target", ("no_target", None)),
                                       ("failed", ("failed", "send failed")), ("kind", ("skipped", PUSH.R_KIND))])
def test_NEGATIVE_refused_week_line_never_says_sent(monkeypatch, case, want):
    res, _ = _refused(monkeypatch, case)
    assert (res["state"], res["reason"]) == want and res["sent"] == 0
    line = W.pushed_text(rings=_doc()["digest"]["rings"])
    assert line == "This week's digest rang — one push to your phone when allowed."
    assert "sent" not in line.lower() and "rang your phone" not in line


def test_NEGATIVE_no_live_digest_line_claims_delivery():
    for rings in (True, False, None):
        line = W.pushed_text(rings=rings).lower()
        assert "sent" not in line and "rang your phone" not in line and "delivered" not in line
