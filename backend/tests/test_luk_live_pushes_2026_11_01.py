"""🥇 Luk's alerts go LIVE — the cross-package integration pins (luk-live spec main-session, 2026-11-01).

Ajay 2026-11-01, verbatim: "Lets make it live. also alerts too."

The unit pins live with each package (tests/test_luk_push_kind_2026_11_01.py = the push stack, tests/test_luk_alerts.py
= the gate). This file pins the SEAMS between them with the shipped values (no LC.LUK_PUSH_MODE patch in the live
tests): luk/alerts.run_pass's DEFAULT sender → gajjala.alerts._default_send(…, LUK) → push.hooks.notify_luk_setup →
push.sender.send_to_user(owner, payload, kind="luk_setup") → the per-device pref filter under that kind; the owner
resolved from env (the detached child's path); the keep-set seven ↔ owner_prefs_apply.on_kinds() ↔ default_prefs; the
closed-day drop at the sender. NEGATIVES: 🧪 GGA still refuses (audited_rules.NEVER_SENDS) and its kind is in no
registry; the shadow fallback reaches no sender; no luk potential kind anywhere. Only the transport (`_fan_out`,
`history.record`, `subs.list_subscriptions`) is faked — every Cheetah function between the pass and it is the real one.
UNMEASURED: his setup, not a buy signal.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import alerts as GA
from chart_maps.gajjala import audited_rules as AR
from chart_maps.gajjala import store as GS
from chart_maps.gajjala import variant as V
from chart_maps.luk import alerts as AL
from chart_maps.luk import constants as LC
from chart_maps.luk import store as ST
from chart_maps.luk import variant as VL
from chart_maps.luk.variant import LUK
from market_hours import gate
from push import history, hooks, recent, sender, subs
from scripts import owner_prefs_apply as S
from tests.test_gajjala_store import FakeColl

ET = ZoneInfo("America/New_York")
DAY = "2026-11-03"                                   # a Tuesday, a market day
QUOTE = "Lets make it live. also alerts too."
SEVEN = frozenset({"gajjala_setup", "gajjala_potential", "gajjala_1m_setup", "gajjala_1m_potential",
                   "luk_setup", "position_alert", "ops_alert"})
OWNER = "owner-local-part" + chr(64) + "example.com"
OTHER = "someone-else" + chr(64) + "example.com"


def at(hhmm: str) -> datetime:
    return datetime.fromisoformat(f"{DAY}T{hhmm}:00").replace(tzinfo=ET)


def aplus(bar: str = "09:32", setup: str = "opening_range_high") -> dict:
    return {"setup": setup, "state": "aplus", "frame": "1m", "entry_bar_t": f"{DAY} {bar}", "trigger": 10.0,
            "stop": 9.7, "risk_pct": 3.0, "r_usd": 0.3, "stop_src": "lod",
            "facts": {"frame_text": "1-minute candle"}}


@pytest.fixture
def wire(monkeypatch):
    """The real chain with a fake transport. Devices: one of the owner's with luk_setup ON (what owner_prefs_apply
    writes), one of another user's with the default_prefs() value. `subs.list_subscriptions` filters by the kind's pref
    exactly as the store does (a device whose pref for the kind is not True is not a target)."""
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.setenv("PORTFOLIO_ALERT_OWNER", OWNER)
    monkeypatch.setattr(gate, "closed_reason", lambda now=None: None)
    devices = [
        {"user_email": OWNER, "endpoint": "e-owner", "prefs": subs.owner_prefs()},
        {"user_email": OTHER, "endpoint": "e-other", "prefs": subs.default_prefs()},
    ]
    seen = {"list": [], "fan": []}

    def _list(filter_kind=None, user_email=None):
        seen["list"].append((filter_kind, user_email))
        return [d for d in devices if d["user_email"] == user_email and d["prefs"].get(filter_kind) is True]

    def _fan(targets, payload):
        seen["fan"].append((list(targets), payload))
        return {"sent": len(targets), "failed": 0, "total_targets": len(targets)}, "pid", []

    monkeypatch.setattr(subs, "list_subscriptions", _list)
    monkeypatch.setattr(sender, "_fan_out", _fan)
    monkeypatch.setattr(history, "record", lambda *a, **k: None)
    # The detached child never passes owner= → GA._owner() → portfolio.alerts._resolve_owner() (env). On the HOST 3.9
    # venv `import portfolio` dies at portfolio/api.py:184 (`str | None`, commit da54f678 — pre-existing, not this
    # build), so the chain tests resolve the owner through _resolve_owner_env below (the same env order, read by NAME
    # from the real function when it imports); test_the_default_owner_is_the_env_owner pins the real one where it can.
    monkeypatch.setattr(GA, "_owner", _resolve_owner_env)
    return seen


def _resolve_owner_env() -> str:
    try:
        from portfolio.alerts import _resolve_owner
    except TypeError:                                               # host 3.9 only (see the fixture)
        import os
        return (os.getenv("PORTFOLIO_ALERT_OWNER") or os.getenv("HOUSE_OWNER_EMAIL") or "").lower()
    return _resolve_owner()


def _store():
    coll = FakeColl()
    return ST.LukStore(colls={GS.ALERTS: coll}), coll


# ── the shipped values ───────────────────────────────────────────────────────────────────────────────────────────
def test_the_shipped_mode_is_live_and_the_one_reader_says_so():
    assert LC.LUK_PUSH_MODE == "live" and VL.push_mode() == "live"
    assert LC.LUK_LIVE_WORDS == QUOTE and LC.LUK_LIVE_SINCE == "2026-11-01"
    assert LUK.send_setup == "notify_luk_setup" and LUK.send_potential == ""
    assert V.push_mode(LUK) == "shadow"          # GG's reader is NOT Luk's (GC has no LUK_PUSH_MODE) — documented


def test_the_keep_set_is_seven_and_the_prefs_script_derives_it():
    assert subs.OWNER_KEEP_SET == SEVEN
    assert S.on_kinds() == sorted(SEVEN) and "luk_setup" in S.on_kinds()
    assert "luk_setup" not in S.off_kinds()
    assert subs.owner_prefs()["luk_setup"] is True
    assert subs.default_prefs()["luk_setup"] is False                   # NEGATIVE: never ON for another user


def test_the_kind_is_registered_on_every_push_registry():
    assert "luk_setup" in gate.MARKET_ALERT_KINDS and "luk_setup" not in gate.PERSONAL_KINDS
    assert "luk_setup" not in subs.DISABLED_ALERT_KINDS
    assert recent.item_url("luk_setup", "ABC") == "/chart-maps?tab=luk&focus=ABC"
    assert callable(getattr(hooks, "notify_luk_setup", None))


# ── the default sender, end to end ───────────────────────────────────────────────────────────────────────────────
def test_the_default_sender_rings_the_owner_device_under_luk_setup(wire):
    st, coll = _store()
    c = AL.run_pass({"ABC": {"opening_range_high": aplus()}}, {}, at("09:36"), DAY, store=st)
    assert c["pushed"] == 1 and c["shadow"] == 0 and c["shadow_mode"] == 0
    assert wire["list"] == [("luk_setup", OWNER)]                      # the pref kind + the env owner
    (targets, payload), = wire["fan"]
    assert [t["endpoint"] for t in targets] == ["e-owner"]             # NEGATIVE: another user's device never rings
    assert payload["kind"] == "luk_setup" and payload["title"].startswith("🥇 ABC")
    assert payload["url"] == "/chart-maps?tab=luk&sub=opening_range_high&focus=ABC"
    key = GA.claim_key(DAY, "ABC", "opening_range_high", LUK)
    assert coll.docs[key]["state"] == "pushed" and coll.docs[key]["result"]["sent"] == 1
    assert not any(k.startswith("SHADOW:") for k in coll.docs)          # NEGATIVE: live writes no shadow row


def test_once_per_session_symbol_setup_through_the_real_chain(wire):
    st, _ = _store()
    reads = {"ABC": {"opening_range_high": aplus()}}
    AL.run_pass(reads, {}, at("09:36"), DAY, store=st)
    c = AL.run_pass(reads, {}, at("09:37"), DAY, store=st)
    assert c["claimed_before"] == 1 and c["pushed"] == 0 and len(wire["fan"]) == 1


def test_NEGATIVE_a_device_with_the_pref_off_is_no_target(wire, monkeypatch):
    st, coll = _store()
    monkeypatch.setattr(subs, "list_subscriptions", lambda filter_kind=None, user_email=None: [])
    c = AL.run_pass({"ABC": {"opening_range_high": aplus()}}, {}, at("09:36"), DAY, store=st)
    assert c["no_target"] == 1 and c["pushed"] == 0
    assert [t for t, _p in wire["fan"]] == [[]]                         # fanned out to zero devices — nothing rang
    assert coll.docs[GA.claim_key(DAY, "ABC", "opening_range_high", LUK)]["state"] == "no_target"


def test_NEGATIVE_the_sender_closed_day_drop_applies_to_luk_setup(wire, monkeypatch):
    monkeypatch.setattr(gate, "closed_reason", lambda now=None: "weekend")
    res = hooks.notify_luk_setup(owner=OWNER, payload={"title": "t"})
    assert res["sent"] == 0 and res["skipped"] == "weekend"
    assert wire["list"] == [] and wire["fan"] == []                    # no device looked up, nothing fanned out


def test_NEGATIVE_the_shadow_fallback_reaches_no_sender(wire, monkeypatch):
    monkeypatch.setattr(LC, "LUK_PUSH_MODE", "LIVE")                   # anything but exactly "live" = shadow
    st, coll = _store()
    c = AL.run_pass({"ABC": {"opening_range_high": aplus()}}, {}, at("09:36"), DAY, store=st)
    assert c["shadow"] == 1 and c["pushed"] == 0 and c["shadow_mode"] == 1
    assert wire["list"] == [] and wire["fan"] == []
    assert list(coll.docs) == [GA.shadow_key(DAY, "ABC", "opening_range_high", LUK)]


def test_the_default_owner_is_the_env_owner(monkeypatch):
    """The real GA._owner() (no patch): env PORTFOLIO_ALERT_OWNER first — the path the detached child rings on."""
    try:
        import portfolio.alerts  # noqa: F401
    except TypeError:
        pytest.skip("host 3.9 venv cannot import portfolio (portfolio/api.py:184 `str | None`, pre-existing) — "
                    "runs under the container's Python")
    monkeypatch.setenv("PORTFOLIO_ALERT_OWNER", OWNER.upper())
    assert GA._owner() == OWNER


# ── NEGATIVES — 🧪 stays shadow, no luk potential kind ───────────────────────────────────────────────────────────
def test_NEGATIVE_the_audited_variant_still_refuses_to_send(wire):
    with pytest.raises(RuntimeError) as e:
        GA._default_send(OWNER, {"title": "t"}, V.GGA)
    assert str(e.value) == AR.NEVER_SENDS
    assert wire["list"] == [] and wire["fan"] == []


def test_NEGATIVE_the_audited_kind_is_in_no_push_registry():
    assert not any("audited" in k for k in subs.OWNER_KEEP_SET)
    assert not any("audited" in k for k in S.on_kinds())
    assert not any(n.startswith("notify_gajjala_audited") for n in dir(hooks))
    assert V.GGA.send_setup == "" and V.GGA.send_potential == ""


def test_NEGATIVE_no_luk_potential_kind_exists_anywhere():
    for reg in (subs.OWNER_KEEP_SET, subs.default_prefs(), gate.MARKET_ALERT_KINDS, recent.ITEM_KINDS):
        assert "luk_potential" not in reg
    assert not any(n.startswith("notify_luk_") and n != "notify_luk_setup" for n in dir(hooks))
    assert [k for k in subs.OWNER_KEEP_SET if "luk" in k] == ["luk_setup"]
