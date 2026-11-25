"""🥇 Luk's alerts OFF again — the shipped LC.LUK_PUSH_MODE is "shadow" (2026-11-25).

Ajay 2026-11-25, verbatim: "Kill the alerts on 1 min time frame they are not reliable"

The only 1-minute-frame alerts still reaching his phone were 🥇 Luk's (`luk_setup`). The one source change is
chart_maps/luk/constants.py `LUK_PUSH_MODE = "shadow"` (was "live" since LC.LUK_LIVE_SINCE, his 11-01 words
LC.LUK_LIVE_WORDS kept on file). Every test here runs with the SHIPPED constant — no LC.LUK_PUSH_MODE patch — and pins:
the constant and his dated words; the gate (luk.alerts.run_pass) and the full pass (luk.run.run_pass) reach no sender,
look up no device, fan out to nothing and write no push_history row; the claim is still RECORDED (the shadow row with
its would-push payload) and is still a 🏁 ledger row (graded like any other); the served words are the shadow ones.
NEGATIVES throughout. The live send chain stays covered by tests/test_luk_live_pushes_2026_11_01.py and
tests/test_luk_alerts.py (both patch "live").
"""
from __future__ import annotations

import pathlib

import pytest

from chart_maps.gajjala import alerts as GA
from chart_maps.gajjala import store as GS
from chart_maps.luk import alerts as AL
from chart_maps.luk import constants as LC
from chart_maps.luk import ledger as LL
from chart_maps.luk import playbook as PB
from chart_maps.luk import run as LR
from chart_maps.luk import store as ST
from chart_maps.luk import tab as T
from chart_maps.luk import variant as VL
from chart_maps.luk.variant import LUK
from market_hours import gate
from push import history, hooks, sender, subs
from tests.test_gajjala_store import FakeColl
from tests.test_luk_live_pushes_2026_11_01 import DAY, OWNER, _resolve_owner_env, aplus, at
from tests import test_luk_run as TR

KILL_WORDS = "Kill the alerts on 1 min time frame they are not reliable"
SRC = pathlib.Path(LC.__file__).read_text(encoding="utf-8")


@pytest.fixture
def chain(monkeypatch):
    """The real chain down to the transport, every hop recorded: hooks.notify_luk_setup (wrapped, the real one still
    called), subs.list_subscriptions, sender._fan_out, history.record. The owner's device has luk_setup ON."""
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.setenv("PORTFOLIO_ALERT_OWNER", OWNER)
    monkeypatch.setattr(gate, "closed_reason", lambda now=None: None)
    seen = {"hook": [], "list": [], "fan": [], "history": []}
    real_hook = hooks.notify_luk_setup

    def _hook(**k):
        seen["hook"].append(k)
        return real_hook(**k)

    def _list(filter_kind=None, user_email=None):
        seen["list"].append((filter_kind, user_email))
        return [{"user_email": OWNER, "endpoint": "e-owner", "prefs": subs.owner_prefs()}]

    def _fan(targets, payload, **_kw):
        seen["fan"].append((list(targets), payload))
        return {"sent": len(targets), "failed": 0, "total_targets": len(targets)}, "pid", []

    monkeypatch.setattr(hooks, "notify_luk_setup", _hook)
    monkeypatch.setattr(subs, "list_subscriptions", _list)
    monkeypatch.setattr(sender, "_fan_out", _fan)
    monkeypatch.setattr(history, "record", lambda *a, **k: seen["history"].append((a, k)))
    monkeypatch.setattr(GA, "_owner", _resolve_owner_env)
    return seen


def _store():
    coll = FakeColl()
    return ST.LukStore(colls={GS.ALERTS: coll}), coll


def _quiet(seen: dict) -> bool:
    return seen["hook"] == [] and seen["list"] == [] and seen["fan"] == [] and seen["history"] == []


# ── the shipped constant and his words ───────────────────────────────────────────────────────────────────────────
def test_the_shipped_mode_is_shadow_by_his_11_25_word():
    assert LC.LUK_PUSH_MODE == "shadow" and VL.push_mode() == "shadow"
    line = next(ln for ln in SRC.splitlines() if ln.startswith("LUK_PUSH_MODE = "))
    comment = line.split("#", 1)[1].strip()
    assert comment.startswith('Ajay 2026-11-25: "' + KILL_WORDS + '"')


def test_the_11_01_words_stay_on_file():
    assert LC.LUK_LIVE_SINCE == "2026-11-01" and LC.LUK_LIVE_WORDS == "Lets make it live. also alerts too."
    line = next(ln for ln in SRC.splitlines() if ln.startswith("LUK_PUSH_MODE = "))
    assert LC.LUK_LIVE_WORDS in line                                    # the history is quoted on the line too


def test_NEGATIVE_the_live_line_is_not_shipped():
    assert 'LUK_PUSH_MODE = "live"' not in SRC
    assert sum(ln.startswith("LUK_PUSH_MODE = ") for ln in SRC.splitlines()) == 1


# ── the gate: recorded, never sent ───────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_the_gate_reaches_no_sender_and_writes_no_push_history(chain):
    st, coll = _store()
    c = AL.run_pass({"ABC": {"opening_range_high": aplus()}}, {}, at("09:36"), DAY, store=st)
    assert c["aplus"] == 1 and c["shadow"] == 1 and c["shadow_mode"] == 1
    assert c["pushed"] == 0 and c["failed"] == 0 and c["no_target"] == 0
    assert _quiet(chain)                                                # no hook, no device, no fan-out, no history
    assert GA.claim_key(DAY, "ABC", "opening_range_high", LUK) not in coll.docs   # NEGATIVE: no live claim


def test_the_claim_is_still_recorded_with_its_would_push_payload(chain):
    st, coll = _store()
    AL.run_pass({"ABC": {"opening_range_high": aplus()}}, {}, at("09:36"), DAY, store=st)
    sk = GA.shadow_key(DAY, "ABC", "opening_range_high", LUK)
    assert list(coll.docs) == [sk]
    doc = coll.docs[sk]
    assert doc["state"] == "shadow" and doc["mode"] == "shadow" and doc["note"] == AL.SHADOW_NOTE
    assert doc["kind"] == LUK.push_kind_setup == "luk_setup"
    assert doc["would_push"]["kind"] == "luk_setup" and doc["would_push"]["title"].startswith("🥇 ABC")


def test_the_shadow_claim_is_a_ledger_row_so_it_is_still_graded(chain):
    st, coll = _store()
    AL.run_pass({"ABC": {"opening_range_high": aplus()}}, {}, at("09:36"), DAY, store=st)
    row = LL.row_of(coll.docs[GA.shadow_key(DAY, "ABC", "opening_range_high", LUK)])
    assert row is not None and row["line"] == "shadow" and row["symbol"] == "ABC"
    assert LL.rang_text(row).startswith("recorded") and "never sent" in LL.rang_text(row)


def test_NEGATIVE_a_second_pass_still_sends_nothing(chain):
    st, coll = _store()
    reads = {"ABC": {"opening_range_high": aplus()}}
    AL.run_pass(reads, {}, at("09:36"), DAY, store=st)
    c = AL.run_pass(reads, {}, at("09:41"), DAY, store=st)
    assert c["pushed"] == 0 and c["shadow"] == 0 and c["claimed_before"] == 1
    assert _quiet(chain) and len(coll.docs) == 1


def test_NEGATIVE_an_explicit_live_mode_still_rings_so_the_off_is_the_constant(chain):
    """Control: the kill is the constant, not a broken chain — an explicit mode="live" reaches the sender."""
    st, _coll = _store()
    c = AL.run_pass({"ABC": {"opening_range_high": aplus()}}, {}, at("09:36"), DAY, store=st, mode="live")
    assert c["pushed"] == 1 and len(chain["hook"]) == 1 and len(chain["fan"]) == 1


# ── the full pass ────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_the_full_pass_records_and_sends_nothing(monkeypatch):
    def _boom(*_a, **_k):
        raise AssertionError("the sender was called")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.setattr(hooks, "notify_luk_setup", _boom, raising=False)
    monkeypatch.setattr(GA, "_owner", lambda: TR.OWNER)
    recorded: list = []
    monkeypatch.setattr(history, "record", lambda *a, **k: recorded.append((a, k)))
    spies = TR.fake_steps(monkeypatch, t1=TR.at("09:35"), t5=TR.at("09:35"), read=TR._aplus())
    st, colls = TR.mk_store()
    out = LR.run_pass(TR.at("09:36", 7), store=st, deps=TR.fake_deps())
    assert out["status"] == "ok" and out["errors"] == []
    assert out["alerts"]["pushed"] == 0 and out["alerts"]["shadow"] == 2 and out["alerts"]["shadow_mode"] == 1
    assert {d["state"] for d in colls[GS.ALERTS].docs.values()} == {"shadow"}
    assert all(k.startswith("SHADOW:") for k in colls[GS.ALERTS].docs)
    assert recorded == []                                               # no push_history row
    assert len(spies["grade"]) == 1                                     # the 🏁 grade step still runs


# ── the served words follow the mode ─────────────────────────────────────────────────────────────────────────────
def test_the_served_mode_words_are_the_shadow_ones():
    assert PB.alert_clause() == PB.ALERT_CLAUSE_SHADOW
    assert T.push_text() == T.PUSH_TEXT_SHADOW
    assert LL.honesty() is LL.HONESTY_SHADOW and LL.empty_text() is LL.EMPTY_TEXT_SHADOW
    assert T.variant_block()["push_mode"] == "shadow"


def test_NEGATIVE_no_mode_sentence_claims_it_rings_or_quotes_the_live_words():
    for txt in (PB.alert_clause(), T.push_text()):
        assert "rings your phone" not in txt and LC.LUK_LIVE_WORDS not in txt
    assert T.PUSH_REREAD_TAIL not in T.push_text()
