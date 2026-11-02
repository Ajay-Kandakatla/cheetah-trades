"""🥇 Luk's A+ gate (chart_maps/luk/alerts.py — BUILD_SPEC §3.8, WP-A4, 2026-11-01; LIVE 2026-11-01).

Ajay 2026-11-01: "look at other winners of US stocks champion ship and pic the next best one like Gajjala. Implement
their strategy please if they have online resources." Ajay 2026-11-01 (the go-live): "Lets make it live. also alerts
too."

THE SHADOW SECTION (the fail-closed fallback — an autouse fixture patches LC.LUK_PUSH_MODE to "shadow" and makes the
sender explode): one shadow claim per (date, SYM, setup) with the would-push payload and SHADOW_NOTE; a repeat →
claimed_before; the freshness clock = gajjala.alerts.max_entry_age_sec(LUK) = 330 s ([fixed: C1] a 1-minute A+ 4
minutes old is recorded, 6 minutes old is late); the first candle is NOT suppressed (Luk trades it); an entry bar outside
the regular session → #suppressed_outside_rth; the counters are gajjala.alerts.COUNT_KEYS exactly.
THE LIVE SECTION (go-live 2026-11-01, mirrors tests/test_gajjala_only_pushes_2026_10_29.py D2): each A+ calls the
sender ONCE with the 🥇 payload and settles "pushed"; the shadow-key guard; late / suppressed_window /
suppressed_closed / failed / no_target / dry never ring twice or at all. NEGATIVES throughout.
"""
from __future__ import annotations

import ast
import inspect
import pathlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import alerts as GA
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as GS
from chart_maps.luk import alerts as AL
from chart_maps.luk import constants as LC
from chart_maps.luk import store as ST
from chart_maps.luk import variant as VL
from chart_maps.luk.variant import LUK
from tests.test_gajjala_store import FakeColl

ET = ZoneInfo("America/New_York")
DAY = "2026-11-03"                                   # a Tuesday, a market day
OWNER = "owner-local-part" + chr(64) + "example.com"
OK_SEND = {"sent": 1, "failed": 0, "total_targets": 1}


def boom(*_a, **_k):
    raise AssertionError("the sender was called")


@pytest.fixture(autouse=True)
def _shadow_by_default(monkeypatch):
    """PATCHED 2026-11-01 (go-live): the shadow pins below run with LC.LUK_PUSH_MODE = "shadow" (the fail-closed
    fallback) and a sender that explodes if reached; the live section re-patches both."""
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.setattr(LC, "LUK_PUSH_MODE", "shadow")
    from push import hooks
    monkeypatch.setattr(hooks, "notify_luk_setup", boom, raising=False)


def live(monkeypatch, result=None, *, raise_exc=None) -> list:
    """LC.LUK_PUSH_MODE = "live" (the shipped value) + hooks.notify_luk_setup recording each call → the calls list."""
    from push import hooks
    monkeypatch.setattr(LC, "LUK_PUSH_MODE", "live")
    seen: list = []

    def _send(**k):
        seen.append(k)
        if raise_exc is not None:
            raise raise_exc
        return dict(OK_SEND) if result is None else result
    monkeypatch.setattr(hooks, "notify_luk_setup", _send, raising=False)
    return seen


def at(hhmm: str, sec: int = 0) -> datetime:
    return datetime.fromisoformat(f"{DAY}T{hhmm}:00").replace(tzinfo=ET) + timedelta(seconds=sec)


def mk_store():
    alerts = FakeColl()
    return ST.LukStore(colls={GS.ALERTS: alerts}), alerts


def aplus(bar: str = "09:32", *, frame: str = "1m", setup: str = "opening_range_high", **kw) -> dict:
    r = {"setup": setup, "state": "aplus", "frame": frame, "entry_bar_t": f"{DAY} {bar}", "trigger": 10.0,
         "stop": 9.7, "risk_pct": 3.0, "r_usd": 0.3, "stop_src": "lod",
         "facts": {"frame_text": "1-minute candle" if frame == "1m" else "5-minute candle"}}
    r.update(kw)
    return r


def run(reads, now, st, **kw):
    return AL.run_pass(reads, {}, now, DAY, store=st, **kw)


# ── the claim ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_one_shadow_claim_per_date_symbol_setup_with_the_would_push_payload():
    st, coll = mk_store()
    r = aplus()
    c = run({"abc": {"opening_range_high": r}}, at("09:36"), st, ctx={"ABC": {"price": 10.05}})
    assert c["aplus"] == 1 and c["shadow"] == 1 and c["shadow_mode"] == 1 and c["pushed"] == 0
    sk = GA.shadow_key(DAY, "ABC", "opening_range_high", LUK)
    assert sk == f"SHADOW:LUK:{DAY}|ABC|opening_range_high"
    doc = coll.docs[sk]
    assert doc["state"] == "shadow" and doc["note"] == GA.SHADOW_NOTE == AL.SHADOW_NOTE
    assert doc["would_push"] == AL.compose(dict(r), "ABC", {"price": 10.05}, session=DAY)
    assert doc["mode"] == "shadow" and doc["price"] == 10.05 and doc["kind"] == LUK.push_kind_setup
    assert doc["at"] == at("09:36").isoformat()
    assert list(coll.docs) == [sk]                                       # NEGATIVE: no live claim key exists
    assert c["shadow_session"] == 1


def test_a_second_pass_is_claimed_before_and_writes_no_second_row():
    st, coll = mk_store()
    reads = {"ABC": {"opening_range_high": aplus()}}
    run(reads, at("09:36"), st)
    n = len(coll.docs)
    c = run(reads, at("09:37"), st)                                      # still fresh: the house claim refuses
    assert c["claimed_before"] == 1 and c["shadow"] == 0 and len(coll.docs) == n
    c = run(reads, at("09:41"), st)                                      # stale now: the key on file → a repeat
    assert c["claimed_before"] == 1 and c["late"] == 0 and len(coll.docs) == n


def test_a_new_setup_or_symbol_the_same_day_is_its_own_claim():
    st, coll = mk_store()
    run({"ABC": {"opening_range_high": aplus()}}, at("09:36"), st)
    c = run({"ABC": {"inside_day_pdh": aplus(setup="inside_day_pdh")},
             "XYZ": {"opening_range_high": aplus()}}, at("09:36"), st)
    assert c["shadow"] == 2 and len(coll.docs) == 3


# ── the clock [fixed: C1] ────────────────────────────────────────────────────────────────────────────────────────
def test_the_freshness_window_is_the_luk_cadence_plus_the_settle():
    assert GA.max_entry_age_sec(LUK) == GC.PASS_CADENCE_SEC + GC.BAR_SETTLE_SEC == 330


def test_a_one_minute_aplus_four_minutes_old_is_recorded_six_minutes_old_is_late():
    st, coll = mk_store()
    c = run({"ABC": {"opening_range_high": aplus("09:32")}}, at("09:36"), st)
    assert c["shadow"] == 1 and c["late"] == 0
    st2, coll2 = mk_store()
    c = run({"ABC": {"opening_range_high": aplus("09:32")}}, at("09:38"), st2)
    assert c["late"] == 1 and c["shadow"] == 0                           # NEGATIVE: a skipped pass → late
    key = GA.claim_key(DAY, "ABC", "opening_range_high", LUK)
    assert list(coll2.docs) == [f"{key}#late"] and coll2.docs[f"{key}#late"]["state"] == "late"


@pytest.mark.parametrize("sec,state", [(GA.max_entry_age_sec(LUK), "shadow"),
                                       (GA.max_entry_age_sec(LUK) + 1, "late")])
def test_the_freshness_boundary(sec, state):
    st, _coll = mk_store()
    c = run({"ABC": {"opening_range_high": aplus("09:32")}}, at("09:32", sec), st)
    assert c[state] == 1


def test_a_late_record_never_consumes_the_days_claim():
    st, coll = mk_store()
    run({"ABC": {"opening_range_high": aplus("09:32")}}, at("09:40"), st)          # late, recorded #late
    c = run({"ABC": {"opening_range_high": aplus("09:41")}}, at("09:42"), st)      # a fresh A+ later the same day
    assert c["shadow"] == 1


# ── the session ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_first_one_minute_candle_is_not_suppressed():
    st, _coll = mk_store()
    c = run({"ABC": {"opening_range_high": aplus("09:31")}}, at("09:32"), st)
    assert c["shadow"] == 1
    assert all(c[k] == 0 for k in ("suppressed_first15", "suppressed_premarket", "suppressed_window"))


@pytest.mark.parametrize("bar,frame", [("16:05", "5m"), ("16:01", "1m"), ("09:30", "5m"), ("09:30", "1m")])
def test_NEGATIVE_an_entry_bar_outside_the_regular_session_is_suppressed_outside_rth(bar, frame):
    st, coll = mk_store()
    c = run({"ABC": {"opening_range_high": aplus(bar, frame=frame)}}, at(bar, 60), st)
    assert c["shadow"] == 0 and c[AL.OUTSIDE_RTH_COUNT_KEY] == 1
    key = GA.claim_key(DAY, "ABC", "opening_range_high", LUK)
    doc = coll.docs[f"{key}#{AL.SUPPRESSED_OUTSIDE_RTH}"]
    assert doc["state"] == "suppressed_outside_rth"
    assert not any(k.startswith("SHADOW:") for k in coll.docs)


@pytest.mark.parametrize("bar,frame", [("16:00", "5m"), ("16:00", "1m"), ("09:35", "5m"), ("09:31", "1m")])
def test_the_regular_session_edges_are_inside(bar, frame):
    assert AL.outside_rth(f"{DAY} {bar}", DAY, frame) is False


def test_a_half_day_closes_at_13_00():
    from supply_demand.timeframes import HALF_DAYS
    half = sorted(HALF_DAYS)[0]
    assert AL.outside_rth(f"{half} 13:00", half, "5m") is False
    assert AL.outside_rth(f"{half} 13:05", half, "5m") is True


def test_NEGATIVE_an_unreadable_stamp_is_outside():
    assert AL.outside_rth(None, DAY, "1m") is True and AL.outside_rth("junk", DAY, "5m") is True


# ── the shadow fallback never sends ───────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_shadow_never_reaches_the_sender():
    st, _coll = mk_store()
    c = run({"ABC": {"opening_range_high": aplus()}}, at("09:36"), st, owner=OWNER)   # the sender is `boom`
    assert c["shadow"] == 1 and c["shadow_mode"] == 1
    assert c["pushed"] == 0 and c["failed"] == 0 and c["no_target"] == 0


def test_the_shipped_constant_is_live_and_this_section_patches_it(monkeypatch):
    import importlib
    import chart_maps.luk.constants as fresh
    src = pathlib.Path(fresh.__file__).read_text(encoding="utf-8")
    assert 'LUK_PUSH_MODE = "live"' in src                              # shipped LIVE (Ajay 2026-11-01)
    assert LC.LUK_PUSH_MODE == "shadow" and VL.push_mode() == "shadow"   # the autouse patch, the fallback words
    assert importlib.import_module("chart_maps.luk.constants") is LC


# ── counters, dry, shapes ────────────────────────────────────────────────────────────────────────────────────────
def test_the_counters_are_the_gajjala_count_keys_exactly():
    st, _coll = mk_store()
    c = run({}, at("09:36"), st)
    assert tuple(c) == GA.COUNT_KEYS == AL.COUNT_KEYS
    assert AL.OUTSIDE_RTH_COUNT_KEY in GA.COUNT_KEYS
    assert AL.SUPPRESSED_OUTSIDE_RTH not in GA.COUNT_KEYS               # the state word, counted under GG's key


def test_dry_records_nothing_and_counts_dry():
    st, coll = mk_store()
    c = run({"ABC": {"opening_range_high": aplus()}, "OLD": {"opening_range_high": aplus("09:20")}},
            at("09:36"), st, dry=True)
    assert c["dry"] == 1 and c["shadow"] == 0 and c["late"] == 1 and c["shadow_session"] == 0
    assert coll.docs == {} and coll.writes == 0                         # NEGATIVE: nothing lands


def test_NEGATIVE_only_aplus_reads_are_candidates():
    st, coll = mk_store()
    reads = {"ABC": {s: dict(aplus(), state=s) for s in ("triggered", "forming", "listed", "stopped", "none")}}
    c = run(reads, at("09:36"), st)
    assert c["aplus"] == 0 and coll.docs == {}


def test_candidates_order_entry_bar_then_setups_order_then_symbol():
    reads = {"ZZZ": {"inside_day_pdh": aplus("09:33", setup="inside_day_pdh"),
                     "opening_range_high": aplus("09:33")},
             "AAA": {"opening_range_high": aplus("09:33"), "pullback_reversal": aplus("09:32",
                                                                                      setup="pullback_reversal")}}
    got = [(c[2], c[3]) for c in AL._candidates(reads)]
    assert got == [("AAA", "pullback_reversal"), ("AAA", "opening_range_high"), ("ZZZ", "opening_range_high"),
                   ("ZZZ", "inside_day_pdh")]
    assert tuple(LC.SETUPS) == ("pullback_reversal", "opening_range_high", "inside_day_pdh")


def test_compose_reads_the_read_only_and_says_unmeasured():
    p = AL.compose(aplus("09:32"), "abc", session=DAY)
    assert p["title"] == "🥇 ABC · Opening range A+ entry"
    assert p["body"].startswith("broke 10.00 on the 1-minute candle closing 09:32 ET · stop 9.70 (−3.0%) · R $0.30")
    assert AL.ENTRY_WORDS["opening_range_high"] in p["body"]
    assert p["body"].endswith("UNMEASURED — his setup, not a buy signal")
    assert p["url"] == "/chart-maps?tab=luk&sub=opening_range_high&focus=ABC" and p["tag"] == "luk-opening_range_high-ABC"
    assert p["kind"] == LUK.push_kind_setup and p["ticker"] == "ABC"
    words = " ".join([p["title"], p["body"], p["items"][0]["text"]] + list(AL.ENTRY_WORDS.values()))
    assert "boun" not in words.lower() and " edge" not in words.lower()   # NEGATIVE: "reversal", never the b-word


def test_NEGATIVE_compose_drops_a_missing_number_never_guesses():
    p = AL.compose(aplus(risk_pct=None, r_usd=None), "ABC", session=DAY)
    assert "(−" not in p["body"] and "R $" not in p["body"]


# ── LIVE (go-live 2026-11-01 — Ajay: "Lets make it live. also alerts too.") ───────────────────────────────────────
KEY = f"LUK:{DAY}|ABC|opening_range_high"


def test_live_one_aplus_calls_the_sender_once_with_the_luk_payload(monkeypatch):
    seen = live(monkeypatch)
    st, coll = mk_store()
    c = run({"ABC": {"opening_range_high": aplus()}}, at("09:36"), st, owner=OWNER, ctx={"ABC": {"price": 10.05}})
    assert c["pushed"] == 1 and c["shadow"] == 0 and c["shadow_mode"] == 0 and c["shadow_session"] == 0, c
    assert len(seen) == 1 and seen[0]["owner"] == OWNER
    p = seen[0]["payload"]
    assert p["title"] == "🥇 ABC · Opening range A+ entry" and p["kind"] == "luk_setup" == LC.LUK_KIND
    assert p["tag"] == "luk-opening_range_high-ABC"
    assert p["url"] == "/chart-maps?tab=luk&sub=opening_range_high&focus=ABC"
    assert p == AL.compose(aplus(), "ABC", {"price": 10.05}, session=DAY)
    assert KEY == GA.claim_key(DAY, "ABC", "opening_range_high", LUK)
    doc = coll.docs[KEY]
    assert doc["state"] == "pushed" and doc["at"] == at("09:36").isoformat() and doc["mode"] == "live"
    assert doc["result"]["sent"] == 1 and doc["result"]["total_targets"] == 1
    assert not [k for k in coll.docs if k.startswith("SHADOW:")]          # NEGATIVE: no shadow row when live


def test_live_the_default_owner_is_the_house_owner(monkeypatch):
    seen = live(monkeypatch)
    monkeypatch.setattr(GA, "_owner", lambda: OWNER)
    st, _coll = mk_store()
    c = run({"ABC": {"opening_range_high": aplus()}}, at("09:36"), st)
    assert c["pushed"] == 1 and seen[0]["owner"] == OWNER


def test_live_an_injected_send_is_used_and_the_hook_is_not(monkeypatch):
    seen_hook = live(monkeypatch)
    sent = []
    st, _coll = mk_store()
    c = run({"ABC": {"opening_range_high": aplus()}}, at("09:36"), st, owner=OWNER,
            send=lambda o, p: sent.append((o, p)) or OK_SEND)
    assert c["pushed"] == 1 and len(sent) == 1 and sent[0][0] == OWNER and seen_hook == []


def test_NEGATIVE_live_a_second_pass_is_claimed_before_and_never_rings_twice(monkeypatch):
    seen = live(monkeypatch)
    st, coll = mk_store()
    reads = {"ABC": {"opening_range_high": aplus()}}
    run(reads, at("09:36"), st, owner=OWNER)
    c = run(reads, at("09:37"), st, owner=OWNER)
    assert c["claimed_before"] == 1 and c["pushed"] == 0 and len(seen) == 1
    c = run(reads, at("09:41"), st, owner=OWNER)                          # stale now: the key on file → a repeat
    assert c["claimed_before"] == 1 and c["late"] == 0 and len(seen) == 1


def test_NEGATIVE_the_shadow_key_guard_refuses_the_live_claim(monkeypatch):
    """A key shadowed earlier the same session (before the flip) never rings after it."""
    st, coll = mk_store()
    first = run({"ABC": {"opening_range_high": aplus()}}, at("09:36"), st, owner=OWNER)     # autouse: shadow
    assert first["shadow"] == 1
    seen = live(monkeypatch)                                              # the flip, mid-session
    again = run({"ABC": {"opening_range_high": aplus()}}, at("09:37"), st, owner=OWNER)
    assert again["claimed_before"] == 1 and again["pushed"] == 0 and seen == []
    assert KEY not in coll.docs
    ok = run({"ABC": {"inside_day_pdh": aplus("09:36", setup="inside_day_pdh")}}, at("09:37"), st, owner=OWNER)
    assert ok["pushed"] == 1 and len(seen) == 1                           # control: a different setup rings


def test_NEGATIVE_live_only_aplus_reads_reach_the_sender(monkeypatch):
    seen = live(monkeypatch)
    st, coll = mk_store()
    reads = {"ABC": {s: dict(aplus(), state=s) for s in ("triggered", "forming", "listed", "stopped", "none")}}
    c = run(reads, at("09:36"), st, owner=OWNER)
    assert c["aplus"] == 0 and c["pushed"] == 0 and seen == [] and coll.docs == {}


def test_NEGATIVE_live_a_stale_read_is_late_and_never_rings(monkeypatch):
    seen = live(monkeypatch)
    st, coll = mk_store()
    c = run({"ABC": {"opening_range_high": aplus("09:32")}}, at("09:38"), st, owner=OWNER)   # 6 minutes on 1m
    assert c["late"] == 1 and c["pushed"] == 0 and seen == []
    assert list(coll.docs) == [f"{KEY}#late"]


@pytest.mark.parametrize("delta,rings", [(5, False), (-5, True)])
def test_live_the_five_minute_freshness_boundary_by_name(monkeypatch, delta, rings):
    """[C8] a 5-minute A+ bar read GA.max_entry_age_sec(LUK) ± 5 s after its close — the window by NAME."""
    seen = live(monkeypatch)
    st, coll = mk_store()
    c = run({"ABC": {"opening_range_high": aplus("09:40", frame="5m")}},
            at("09:40", GA.max_entry_age_sec(LUK) + delta), st, owner=OWNER)
    if rings:
        assert c["pushed"] == 1 and len(seen) == 1 and coll.docs[KEY]["state"] == "pushed"
    else:
        assert c["late"] == 1 and c["pushed"] == 0 and seen == [] and KEY not in coll.docs


@pytest.mark.parametrize("bar,frame,session", [("09:34", "5m", DAY), ("09:30", "1m", DAY), ("16:05", "5m", DAY)])
def test_NEGATIVE_live_an_entry_bar_outside_the_regular_session_never_rings(monkeypatch, bar, frame, session):
    seen = live(monkeypatch)
    st, coll = mk_store()
    c = run({"ABC": {"opening_range_high": aplus(bar, frame=frame)}}, at(bar, 60), st, owner=OWNER)
    assert c["suppressed_window"] == 1 and c["pushed"] == 0 and seen == []
    assert KEY not in coll.docs and f"{KEY}#{AL.SUPPRESSED_OUTSIDE_RTH}" in coll.docs


def test_NEGATIVE_live_a_half_day_bar_after_13_00_never_rings(monkeypatch):
    from supply_demand.timeframes import HALF_DAYS
    half = sorted(HALF_DAYS)[0]
    seen = live(monkeypatch)
    monkeypatch.setattr(GA, "_closed_reason", lambda _now: None)          # the half day itself is a market day
    st, _coll = mk_store()
    now = datetime.fromisoformat(f"{half}T13:06:00").replace(tzinfo=ET)
    c = AL.run_pass({"ABC": {"opening_range_high": aplus(frame="5m", entry_bar_t=f"{half} 13:05")}}, {}, now, half,
                    store=st, owner=OWNER)
    assert c["suppressed_window"] == 1 and c["pushed"] == 0 and seen == []


def test_NEGATIVE_live_a_closed_day_is_suppressed_closed_no_claim_no_send(monkeypatch):
    seen = live(monkeypatch)
    monkeypatch.setattr(GA, "_closed_reason", lambda _now: "weekend")
    st, coll = mk_store()
    c = run({"ABC": {"opening_range_high": aplus()}}, at("09:36"), st, owner=OWNER)
    assert c["suppressed_closed"] == 1 and c["pushed"] == 0 and seen == []
    assert KEY not in coll.docs and coll.docs[f"{KEY}#suppressed_closed"]["state"] == "suppressed_closed"


def test_live_a_raising_sender_settles_failed(monkeypatch):
    seen = live(monkeypatch, raise_exc=ValueError("down"))
    st, coll = mk_store()
    c = run({"ABC": {"opening_range_high": aplus()}}, at("09:36"), st, owner=OWNER)
    assert c["failed"] == 1 and c["pushed"] == 0 and len(seen) == 1
    assert coll.docs[KEY]["state"] == "failed" and coll.docs[KEY]["result"] == {"error": "ValueError"}


def test_live_zero_targets_settles_no_target_and_zero_sent_settles_failed(monkeypatch):
    live(monkeypatch, result={"sent": 0, "failed": 0, "total_targets": 0})
    st, coll = mk_store()
    c = run({"ABC": {"opening_range_high": aplus()}}, at("09:36"), st, owner=OWNER)
    assert c["no_target"] == 1 and c["pushed"] == 0 and coll.docs[KEY]["state"] == "no_target"
    live(monkeypatch, result={"sent": 0, "failed": 1, "total_targets": 1})
    st2, coll2 = mk_store()
    c = run({"ABC": {"opening_range_high": aplus()}}, at("09:36"), st2, owner=OWNER)
    assert c["failed"] == 1 and coll2.docs[KEY]["state"] == "failed"


def test_NEGATIVE_live_dry_claims_nothing_and_sends_nothing(monkeypatch):
    seen = live(monkeypatch)
    st, coll = mk_store()
    c = run({"ABC": {"opening_range_high": aplus()}}, at("09:36"), st, owner=OWNER, dry=True)
    assert c["dry"] == 1 and c["pushed"] == 0 and seen == [] and coll.docs == {} and coll.writes == 0


@pytest.mark.parametrize("junk", ["junk", "LIVE", None, ""])
def test_a_junk_mode_falls_back_to_lucks_own_reader(monkeypatch, junk):
    seen = live(monkeypatch)
    st, _coll = mk_store()
    c = run({"ABC": {"opening_range_high": aplus()}}, at("09:36"), st, owner=OWNER, mode=junk)
    assert c["pushed"] == 1 and len(seen) == 1                            # VL.push_mode() == "live"
    monkeypatch.setattr(LC, "LUK_PUSH_MODE", "shadow")
    st2, _c2 = mk_store()
    c = run({"ABC": {"opening_range_high": aplus()}}, at("09:36"), st2, owner=OWNER, mode=junk)
    assert c["shadow"] == 1 and len(seen) == 1                            # NEGATIVE: the fallback never sends


def test_an_explicit_mode_overrides_the_constant(monkeypatch):
    seen = live(monkeypatch)
    st, _coll = mk_store()
    c = run({"ABC": {"opening_range_high": aplus()}}, at("09:36"), st, owner=OWNER, mode="shadow")
    assert c["shadow"] == 1 and seen == []


def test_NEGATIVE_the_gate_reaches_the_sender_only_through_gajjala_default_send():
    src = inspect.getsource(AL)
    tree = ast.parse(src)
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m and m.startswith(("push", "portfolio")) for m in mods)
    code = ast.unparse(ast.Module(body=tree.body[1:], type_ignores=[]))      # the module docstring names the hook
    assert "notify_" not in code and "GA._default_send(o, p, LUK)" in code and "GA._owner()" in code
    assert not hasattr(AL, "refuse_send") and not hasattr(AL, "NEVER_SENDS") and not hasattr(AL, "MODE")
    assert "refuse_send" not in AL.__all__ and "NEVER_SENDS" not in AL.__all__
    params = inspect.signature(AL.run_pass).parameters
    assert all(p in params for p in ("send", "owner", "mode", "dry", "ctx", "store"))
