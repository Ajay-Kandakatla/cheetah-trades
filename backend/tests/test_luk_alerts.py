"""🥇 Luk's shadow gate (chart_maps/luk/alerts.py — BUILD_SPEC §3.8, WP-A4, 2026-11-01).

Ajay 2026-11-01: "look at other winners of US stocks champion ship and pic the next best one like Gajjala. Implement
their strategy please if they have online resources."

Pins: one shadow claim per (date, SYM, setup) with the would-push payload and SHADOW_NOTE; a repeat → claimed_before;
the freshness clock = gajjala.alerts.max_entry_age_sec(LUK) = 330 s ([fixed: C1] a 1-minute A+ 4 minutes old is
recorded, 6 minutes old is late); the first candle is NOT suppressed (Luk trades it); an entry bar outside the regular
session → #suppressed_outside_rth; nothing is ever sent (refuse_send raises and is never reached); the counters are
gajjala.alerts.COUNT_KEYS exactly. NEGATIVES throughout.
"""
from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import alerts as GA
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as GS
from chart_maps.luk import alerts as AL
from chart_maps.luk import constants as LC
from chart_maps.luk import store as ST
from chart_maps.luk.variant import LUK
from tests.test_gajjala_store import FakeColl

ET = ZoneInfo("America/New_York")
DAY = "2026-11-03"                                   # a Tuesday, a market day


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


# ── never sends ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_refuse_send_raises_never_sends():
    with pytest.raises(RuntimeError) as e:
        AL.refuse_send("owner", {"title": "x"})
    assert str(e.value) == AL.NEVER_SENDS and "never sends" in AL.NEVER_SENDS


def test_NEGATIVE_refuse_send_is_never_reached_and_nothing_is_sent(monkeypatch):
    seen: list = []
    monkeypatch.setattr(AL, "refuse_send", lambda *a, **k: seen.append(a))
    st, _coll = mk_store()
    c = run({"ABC": {"opening_range_high": aplus()}}, at("09:36"), st)
    assert c["shadow"] == 1 and seen == []
    assert c["pushed"] == 0 and c["failed"] == 0 and c["no_target"] == 0


def test_NEGATIVE_the_gate_has_no_sender_no_owner_no_live_branch():
    src = inspect.getsource(AL)
    tree = ast.parse(src)
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m and m.startswith(("push", "portfolio")) for m in mods)
    assert "notify_" not in src and "_default_send" not in src and "_owner" not in src
    params = inspect.signature(AL.run_pass).parameters
    assert "send" not in params and "owner" not in params and "mode" not in params


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
    words = " ".join([p["title"], p["body"], p["items"][0]["text"]] + list(AL.ENTRY_WORDS.values()) + [AL.NEVER_SENDS])
    assert "boun" not in words.lower() and " edge" not in words.lower()   # NEGATIVE: "reversal", never the b-word


def test_NEGATIVE_compose_drops_a_missing_number_never_guesses():
    p = AL.compose(aplus(risk_pct=None, r_usd=None), "ABC", session=DAY)
    assert "(−" not in p["body"] and "R $" not in p["body"]
