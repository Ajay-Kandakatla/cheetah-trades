"""chart_maps/gajjala/alerts.py — the 🚩 gajjala_setup push gate (BUILD_SPEC §3.8, DECISIONS round A, 2026-10-13).

DECISIONS: owner-only kind, A+ only, 09:45–16:00 and 16:00–20:00 ET, never 09:30–09:45, silent on closed days, once
per (symbol, setup, ET day) — SHADOW first (2026-10-13…16: every A+ recorded on /alerts as "shadow — not sent", the
sender never called) + LIVE since 2026-10-16 (Ajay's call: "you alert me when that happens"); the shadow branch is
pinned explicitly (the `shadow` fixture). Negatives are the point here: a shadow pass that rings, a
premarket A+ that rings, a first-15-minutes A+ that rings or a second ring the same day would each put a push on his
phone he never asked for. The ledger is the in-memory FakeColl (tests/conftest.py refuses a real MongoClient).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from tests.test_gajjala_store import fake_store

ET = ZoneInfo("America/New_York")
S = date(2026, 10, 13)                                           # a Tuesday, NYSE open
HALF = date(2026, 11, 27)                                        # NYSE half day (supply_demand.timeframes.HALF_DAYS)
LABOR_DAY = date(2026, 9, 7)
B_WORD = "b" + "ounce"


def at(hh, mm, d=S):
    return datetime(d.year, d.month, d.day, hh, mm, 30, tzinfo=ET)


def stamp(hh, mm, d=S):
    return f"{d.isoformat()} {hh:02d}:{mm:02d}"


def read(setup="bull_flag", *, entry=None, frame="5m", state="aplus", trigger=11.0, stop=10.8125, **kw):
    entry = entry or stamp(10, 5)
    return dict({"setup": setup, "state": state, "frame": frame, "entry_bar_t": entry, "trigger": trigger,
                 "stop": stop, "risk_pct": (trigger - stop) / trigger * 100, "variant": None, "grade": None,
                 "reason": "", "meta": {"structure_alive": False}}, **kw)


def frames_at(t5, t15=None):
    return SimpleNamespace(as_of_bar_t={"5m": t5, "15m": t15 or t5})


class Spy:
    def __init__(self, result=None, raise_=None):
        self.calls = []
        self.result = result or {"sent": 1, "failed": 0, "total_targets": 1}
        self.raise_ = raise_

    def __call__(self, owner, payload):
        self.calls.append((owner, payload))
        if self.raise_:
            raise self.raise_
        return self.result


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")


# WIDENED 2026-10-16: Ajay flipped the A+ kind live ("you alert me when that happens") — the shadow branch stays (a
# flip back is one word), so its tests pin it instead of riding the shipped default
@pytest.fixture
def shadow(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "shadow")


def one(store, r, *, now=None, sym="GGA", frames=None, send=None, ctx=None, dry=False, session=S, mode=None):
    send = send if send is not None else Spy()
    fr = frames or frames_at(r["entry_bar_t"])
    counts = AL.run_pass({sym: {r["setup"]: r}}, {sym: fr}, now or at(10, 6), session, store=store, send=send,
                         owner="owner@example.com", dry=dry, ctx={sym: ctx or {}}, mode=mode)
    return counts, send


def ledger(store):
    return store.alerts_coll().docs


# ── mode ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_mode_ships_live():
    # WIDENED 2026-10-16: Ajay flipped the A+ kind live ("you alert me when that happens")
    assert GC.GAJJALA_PUSH_MODE == "live" and AL.push_mode() == "live"
    assert GC.PUSH_KIND == AL.KIND == "gajjala_setup"


def test_NEGATIVE_shadow_never_calls_the_sender_and_records_the_would_push(shadow):
    st = fake_store()
    counts, send = one(st, read())
    assert send.calls == []
    assert counts["shadow"] == 1 and counts["shadow_mode"] == 1 and counts["pushed"] == 0
    assert counts["shadow_session"] == 1
    doc = ledger(st)["SHADOW:GG:2026-10-13|GGA|bull_flag"]
    assert doc["state"] == "shadow" and doc["note"] == "shadow — not sent" and doc["mode"] == "shadow"
    assert doc["would_push"]["kind"] == "gajjala_setup" and doc["would_push"]["ticker"] == "GGA"
    assert "GG:2026-10-13|GGA|bull_flag" not in ledger(st)            # no live claim


@pytest.mark.parametrize("bad", ["LIVE", "armed", "", None, "on"])
def test_NEGATIVE_an_unknown_mode_fails_closed_to_shadow(monkeypatch, bad):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", bad)
    assert AL.push_mode() == "shadow"
    counts, send = one(fake_store(), read())
    assert send.calls == [] and counts["shadow"] == 1


def test_live_rings_once_with_the_composed_payload(live):
    st = fake_store()
    counts, send = one(st, read())
    assert counts["pushed"] == 1 and counts["shadow"] == 0 and counts["shadow_mode"] == 0
    assert len(send.calls) == 1
    owner, p = send.calls[0]
    assert owner == "owner@example.com"
    assert p["kind"] == "gajjala_setup" and p["ticker"] == "GGA"
    assert p["url"] == "/chart-maps?tab=gajjala&sub=bull_flag&focus=GGA"
    assert p["title"] == "🚩 GGA · Bull Flag A+ entry"                 # WIDENED 2026-10-16: Ajay flipped the A+ kind live ("you alert me when that happens")
    assert p["items"] == [{"symbol": "GGA", "text": p["items"][0]["text"]}] and p["items"][0]["text"].startswith("GGA")
    assert "UNMEASURED" in p["body"] and "not a buy signal" in p["body"]
    # WIDENED 2026-10-16: Ajay flipped the A+ kind live ("you alert me when that happens"); AMENDMENTS10 F9 — numbers first
    assert p["body"].startswith("broke 11.00 on the 5m bar closing 10:05 ET") and AL.entry_words("bull_flag") in p["body"]
    doc = ledger(st)["GG:2026-10-13|GGA|bull_flag"]
    assert doc["state"] == "pushed" and doc["result"]["sent"] == 1


# ── once per (symbol, setup, ET day) ─────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_second_aplus_same_symbol_setup_day_is_deduped(live):
    st = fake_store()
    send = Spy()
    one(st, read(entry=stamp(10, 5)), send=send)
    counts, _ = one(st, read(entry=stamp(11, 30)), now=at(11, 31), send=send)
    assert counts["claimed_before"] == 1 and counts["pushed"] == 0
    assert len(send.calls) == 1


def test_NEGATIVE_a_second_shadow_aplus_same_day_is_deduped_too(shadow):
    st = fake_store()
    one(st, read(entry=stamp(10, 5)))
    counts, _ = one(st, read(entry=stamp(11, 30)), now=at(11, 31))
    assert counts["claimed_before"] == 1 and counts["shadow"] == 0
    assert counts["shadow_session"] == 1


def test_a_new_day_rings_again(live):
    st = fake_store()
    send = Spy()
    one(st, read(entry=stamp(10, 5)), send=send)
    d2 = date(2026, 10, 14)
    counts, _ = one(st, read(entry=stamp(10, 5, d2)), now=at(10, 6, d2), session=d2, send=send)
    assert counts["pushed"] == 1 and len(send.calls) == 2


def test_a_different_setup_on_the_same_symbol_rings(live):
    st = fake_store()
    send = Spy()
    r1, r2 = read("bull_flag"), read("kiss_fly")
    counts = AL.run_pass({"GGA": {"bull_flag": r1, "kiss_fly": r2}}, {"GGA": frames_at(r1["entry_bar_t"])},
                         at(10, 6), S, store=st, send=send, owner="o")
    assert counts["pushed"] == 2 and [p["url"].split("sub=")[1].split("&")[0] for _o, p in send.calls] == \
        ["bull_flag", "kiss_fly"]


def test_NEGATIVE_a_key_recorded_in_shadow_is_not_claimable_live_the_same_day(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "shadow")             # WIDENED 2026-10-16: Ajay flipped the A+ kind live ("you alert me when that happens")
    st = fake_store()
    one(st, read(entry=stamp(10, 5)))                                # shadow records it
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")              # Ajay flips mid-session
    counts, send = one(st, read(entry=stamp(11, 0)), now=at(11, 1))
    assert send.calls == [] and counts["claimed_before"] == 1


def test_five_aplus_in_one_pass_are_five_single_pushes_no_digest(live):
    st = fake_store()
    send = Spy()
    reads, frames = {}, {}
    for i, sym in enumerate(["EEE", "AAA", "DDD", "BBB", "CCC"]):
        t = stamp(10, 5)
        reads[sym] = {"bull_flag": read(entry=t)}
        frames[sym] = frames_at(t)
    counts = AL.run_pass(reads, frames, at(10, 6), S, store=st, send=send, owner="o")
    assert counts["pushed"] == 5 and len(send.calls) == 5
    assert [p["ticker"] for _o, p in send.calls] == ["AAA", "BBB", "CCC", "DDD", "EEE"]   # entry bar, setup, symbol
    assert all(len(p["items"]) == 1 for _o, p in send.calls)


def test_order_is_entry_bar_then_setups_order(live):
    send = Spy()
    reads = {"ZZZ": {"intraday_vcp": read("intraday_vcp", entry=stamp(10, 5)),
                     "bull_flag": read("bull_flag", entry=stamp(10, 5))},
             "AAA": {"kiss_fly": read("kiss_fly", entry=stamp(10, 5))}}
    frames = {s: frames_at(stamp(10, 5)) for s in reads}
    AL.run_pass(reads, frames, at(10, 6), S, store=fake_store(), send=send, owner="o")
    assert [(p["ticker"], p["tag"]) for _o, p in send.calls] == [
        ("ZZZ", "gg-bull_flag-ZZZ"), ("AAA", "gg-kiss_fly-AAA"), ("ZZZ", "gg-intraday_vcp-ZZZ")]


# ── windows ───────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("label,frame,want", [
    ((9, 45), "5m", "suppressed_first15"),       # bar 09:40–09:45
    ((9, 35), "5m", "suppressed_first15"),       # bar 09:30–09:35
    ((9, 50), "5m", None),                       # bar 09:45–09:50
    ((16, 0), "5m", None),                       # bar 15:55–16:00
    ((16, 5), "5m", None),                       # bar 16:00–16:05
    ((20, 0), "5m", None),                       # bar 19:55–20:00
    ((20, 5), "5m", "suppressed_window"),        # NEGATIVE after 20:00
    ((9, 30), "5m", "suppressed_premarket"),     # NEGATIVE bar 09:25–09:30
    ((8, 0), "5m", "suppressed_premarket"),      # NEGATIVE pre-market
    ((9, 45), "15m", "suppressed_first15"),      # 15m bucket 09:30–09:45
    ((10, 0), "15m", None),                      # 15m bucket 09:45–10:00
])
def test_window_reason(label, frame, want):
    assert AL.window_reason(stamp(*label), S, frame) == want


@pytest.mark.parametrize("label,want", [((13, 5), None), ((17, 0), None), ((17, 5), "suppressed_window")])
def test_window_reason_on_a_half_day(label, want):
    assert AL.window_reason(stamp(*label, d=HALF), HALF, "5m") == want


def test_the_push_open_is_derived_from_his_15_minutes(monkeypatch):
    monkeypatch.setattr(GC, "NO_TRADE_AFTER_OPEN_MIN", 30)
    assert AL.window_reason(stamp(9, 55), S, "5m") == "suppressed_first15"
    assert AL.window_reason(stamp(10, 5), S, "5m") is None


def test_NEGATIVE_a_premarket_aplus_never_pushes_and_never_consumes_the_day(live):
    st = fake_store()
    send = Spy()
    counts, _ = one(st, read(entry=stamp(8, 35)), now=at(8, 36), send=send)
    assert counts["suppressed_premarket"] == 1 and send.calls == []
    assert "GG:2026-10-13|GGA|bull_flag#suppressed_premarket" in ledger(st)
    assert "GG:2026-10-13|GGA|bull_flag" not in ledger(st)
    counts, _ = one(st, read(entry=stamp(10, 5)), send=send)          # a fresh A+ after 09:45 still rings
    assert counts["pushed"] == 1 and len(send.calls) == 1


def test_NEGATIVE_a_premarket_aplus_never_records_shadow_either(shadow):
    st = fake_store()
    counts, _ = one(st, read(entry=stamp(8, 35)), now=at(8, 36))
    assert counts["suppressed_premarket"] == 1 and counts["shadow"] == 0 and counts["shadow_session"] == 0


def test_NEGATIVE_the_first_15_minutes_are_suppressed(live):
    st = fake_store()
    counts, send = one(st, read(entry=stamp(9, 40)), now=at(9, 41))
    assert counts["suppressed_first15"] == 1 and send.calls == []


def test_after_hours_aplus_rings_with_the_limit_order_line(live):
    counts, send = one(fake_store(), read(entry=stamp(16, 35)), now=at(16, 36))
    assert counts["pushed"] == 1
    assert "after-hrs · he uses limit orders and less size outside RTH" in send.calls[0][1]["body"]


def test_NEGATIVE_an_rth_body_carries_no_after_hours_line(live):
    _c, send = one(fake_store(), read(entry=stamp(11, 0)), now=at(11, 1))
    assert "after-hrs" not in send.calls[0][1]["body"]


def test_NEGATIVE_a_closed_day_never_claims_or_sends(live):
    st = fake_store()
    r = read(entry=stamp(10, 5, LABOR_DAY))
    counts, send = one(st, r, now=at(10, 6, LABOR_DAY), session=LABOR_DAY)
    assert counts["suppressed_closed"] == 1 and send.calls == []
    assert not any(not k.endswith("#suppressed_closed") for k in ledger(st))


def test_NEGATIVE_the_sender_drops_the_kind_on_a_closed_day(monkeypatch):
    from market_hours import gate
    from push import sender, subs
    monkeypatch.setattr(gate, "_now_et", lambda: datetime(2026, 9, 7, 10, 0, tzinfo=gate._ET))
    monkeypatch.setattr(subs, "list_subscriptions", lambda **k: pytest.fail("no device may be targeted"))
    r = sender.send_to_user("owner@example.com", {"title": "x"}, kind="gajjala_setup")
    assert r["sent"] == 0 and r["skipped"] == "holiday 2026-09-07"


# ── per-frame latest bar ──────────────────────────────────────────────────────────────────────────────────────────
def test_a_15m_fade_aplus_is_judged_on_the_15m_clock(live):
    # the frame check: at 10:21 the 5m frame's latest bar is 10:20, the 15m frame's is 10:15
    fr = frames_at(stamp(10, 20), stamp(10, 15))
    r = read("horizontal_fade", entry=stamp(10, 15), frame="15m")
    assert AL.pushable(r, fr) is True
    assert AL.pushable(dict(r, frame="5m"), fr) is False             # NEGATIVE: against the 5m bar it would be late
    # the pass that first sees the 10:15 bar is 10:16 (BUILD_SPEC "✓ at 10:16 for the 10:15 bar")
    counts, send = one(fake_store(), r, now=at(10, 16), frames=frames_at(stamp(10, 15), stamp(10, 15)))
    assert counts["pushed"] == 1 and counts["late"] == 0
    assert "on the 15m bar closing 10:15 ET" in send.calls[0][1]["body"]


def test_the_15m_bar_seen_again_by_the_next_pass_is_claimed_before_not_late(live):
    # a 15-minute bar stays the frame's latest for three passes; the repeat is the day's claim, not a late A+
    st = fake_store()
    r = read("horizontal_fade", entry=stamp(10, 15), frame="15m")
    one(st, r, now=at(10, 16), frames=frames_at(stamp(10, 15), stamp(10, 15)))
    counts, send = one(st, r, now=at(10, 21), frames=frames_at(stamp(10, 20), stamp(10, 15)))
    assert counts["claimed_before"] == 1 and counts["late"] == 0 and send.calls == []
    assert "GG:2026-10-13|GGA|horizontal_fade#late" not in ledger(st)


def test_NEGATIVE_a_15m_bar_first_seen_a_pass_late_is_late_not_sent(live):
    # the 10:16 pass never ran (host sleep / budget): at 10:21 the 10:15 bar is 6.5 minutes old
    st = fake_store()
    r = read("horizontal_fade", entry=stamp(10, 15), frame="15m")
    counts, send = one(st, r, now=at(10, 21), frames=frames_at(stamp(10, 20), stamp(10, 15)))
    assert counts["late"] == 1 and counts["pushed"] == 0 and send.calls == []
    assert "GG:2026-10-13|GGA|horizontal_fade#late" in ledger(st)
    assert "GG:2026-10-13|GGA|horizontal_fade" not in ledger(st)    # the day's claim is not used up


def test_NEGATIVE_a_thin_names_hours_old_latest_bar_is_late_not_sent(live):
    # resample drops empty buckets: the frame's own latest bar is 16:35, the pass runs 18:01 → 86 minutes old
    st = fake_store()
    r = read(entry=stamp(16, 35))
    assert AL.pushable(r, frames_at(stamp(16, 35))) is True          # the frame check alone would ring it
    assert AL.pushable(r, frames_at(stamp(16, 35)), at(18, 1)) is False
    counts, send = one(st, r, now=at(18, 1), frames=frames_at(stamp(16, 35)))
    assert counts["aplus"] == 1 and counts["pushed"] == 0 and counts["late"] == 1 and send.calls == []
    assert "GG:2026-10-13|GGA|bull_flag#late" in ledger(st)


def test_NEGATIVE_the_same_thin_name_in_shadow_is_late_not_shadow(shadow):
    counts, send = one(fake_store(), read(entry=stamp(16, 35)), now=at(18, 1), frames=frames_at(stamp(16, 35)))
    assert counts["late"] == 1 and counts["shadow"] == 0 and send.calls == []


@pytest.mark.parametrize("age_sec,fresh", [(60, True), (AL.MAX_ENTRY_AGE_SEC, True), (AL.MAX_ENTRY_AGE_SEC + 1, False),
                                           (-1, False)])
def test_freshness_edge(age_sec, fresh):
    close = datetime(2026, 10, 13, 10, 5, tzinfo=ET)
    assert AL.is_fresh(read(entry=stamp(10, 5)), close + timedelta(seconds=age_sec)) is fresh


def test_the_freshness_limit_is_built_from_the_transport_constants():
    assert AL.MAX_ENTRY_AGE_SEC == GC.PASS_CADENCE_SEC + GC.BAR_SETTLE_SEC


def test_the_half_day_close_is_the_house_calendar_not_a_retyped_copy():
    import inspect
    from datetime import time as dtime
    from catalysts.medical.reaction import rth_close_time
    assert AL._closes(HALF) == (rth_close_time(HALF), dtime(17, 0))
    assert AL._closes(S) == (rth_close_time(S), dtime(20, 0))
    src = inspect.getsource(AL)
    assert "dtime(13" not in src and "time(13" not in src            # NEGATIVE: no third 13:00 copy
    assert ("momentum" + "_burst") not in src                       # NEGATIVE: the burst source guard stays whole


def test_NEGATIVE_a_catch_up_aplus_on_an_older_bar_is_late_not_sent(live):
    st = fake_store()
    counts, send = one(st, read(entry=stamp(10, 5)), now=at(10, 31), frames=frames_at(stamp(10, 30)))
    assert counts["late"] == 1 and send.calls == []
    assert "GG:2026-10-13|GGA|bull_flag#late" in ledger(st)


def test_NEGATIVE_pushable_refuses_non_aplus_states():
    fr = frames_at(stamp(10, 5))
    for state in ("triggered", "stopped", "forming", "partial", "invalid", "none"):
        assert AL.pushable(read(state=state), fr) is False
    assert AL.pushable(dict(read(), entry_bar_t=None), fr) is False
    assert AL.pushable(read(), None) is False                        # no frames → never pushable


# the long_flag band is empty since 2026-10-18 — synthetic variant, the mechanism is what is tested
@pytest.mark.parametrize("extra", [{"variant": "long_flag"}, {"variant": "near_kiss"}, {"grade": "B"}])
def test_NEGATIVE_a_listed_variant_never_rings_even_if_marked_aplus(live, extra):
    counts, send = one(fake_store(), read(**extra))
    assert counts["not_aplus_variant"] == 1 and send.calls == []


def test_NEGATIVE_a_setup_awaiting_a_placeholder_never_claims(live):
    st = fake_store()
    held = {"setup": "intraday_vcp", "state": "none", "reason": "awaiting Ajay's answer (H5)"}
    counts = AL.run_pass({"GGA": {"intraday_vcp": held}}, {"GGA": frames_at(stamp(10, 5))}, at(10, 6), S,
                         store=st, send=Spy(), owner="o")
    assert counts["awaiting_answer"] == 1 and counts["aplus"] == 0 and ledger(st) == {}


# ── dry / failures ───────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_dry_claims_and_sends_nothing(live):
    st = fake_store()
    counts, send = one(st, read(), dry=True)
    assert counts["dry"] == 1 and send.calls == [] and ledger(st) == {}
    counts, _ = one(st, read(entry=stamp(8, 0)), now=at(8, 1), dry=True)
    assert counts["suppressed_premarket"] == 1 and ledger(st) == {}


def test_a_raising_sender_is_failed_and_the_day_stays_claimed(live):
    st = fake_store()
    counts, _ = one(st, read(), send=Spy(raise_=RuntimeError("boom")))
    assert counts["failed"] == 1 and ledger(st)["GG:2026-10-13|GGA|bull_flag"]["state"] == "failed"


def test_nobody_targeted_is_no_target(live):
    counts, _ = one(fake_store(), read(), send=Spy(result={"sent": 0, "failed": 0, "total_targets": 0}))
    assert counts["no_target"] == 1 and counts["pushed"] == 0


# ── the two OFF switches (STRATEGY_SPEC D-HALT / D-AH) ──────────────────────────────────────────────────────────
def test_NEGATIVE_the_off_switches_change_nothing_by_default(live):
    assert GC.HALT_CALM_BARS is None and GC.AH_EXHAUSTION_MAX_PCT is None
    ctx = {"last_halt_resume_et": at(10, 3).isoformat(), "reg_gain_pct": 900.0}
    counts, _ = one(fake_store(), read(entry=stamp(10, 5)), ctx=ctx)
    assert counts["pushed"] == 1
    counts, _ = one(fake_store(), read(entry=stamp(17, 5)), now=at(17, 6), ctx=ctx)
    assert counts["pushed"] == 1


def test_halt_calm_bars_when_set(live, monkeypatch):
    monkeypatch.setattr(GC, "HALT_CALM_BARS", 2)
    resume = datetime(2026, 10, 13, 10, 1, 0, tzinfo=ET).isoformat()
    counts, _ = one(fake_store(), read(entry=stamp(10, 5)), ctx={"last_halt_resume_et": resume})
    assert counts["suppressed_halt"] == 1                             # 1 bar after the resumption
    counts, _ = one(fake_store(), read(entry=stamp(10, 15)), now=at(10, 16), ctx={"last_halt_resume_et": resume})
    assert counts["suppressed_halt"] == 0 and counts["pushed"] == 1   # NEGATIVE 3 bars after → rings


def test_ah_exhaustion_when_set(live, monkeypatch):
    monkeypatch.setattr(GC, "AH_EXHAUSTION_MAX_PCT", 150.0)
    counts, _ = one(fake_store(), read(entry=stamp(17, 5)), now=at(17, 6), ctx={"reg_gain_pct": 200.0})
    assert counts["suppressed_exhausted"] == 1
    counts, _ = one(fake_store(), read(entry=stamp(11, 5)), now=at(11, 6), ctx={"reg_gain_pct": 200.0})
    assert counts["pushed"] == 1                                      # NEGATIVE an RTH A+ on the same name rings


# ── wording ───────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("setup", GC.SETUPS)
def test_compose_every_setup(setup):
    p = AL.compose(read(setup, entry=stamp(16, 35)), "gga", {"float_text": "Float 3.1M"}, session=S)
    emoji, label = AL.SETUP_META[setup]
    # WIDENED 2026-10-16: Ajay flipped the A+ kind live ("you alert me when that happens"); AMENDMENTS10 F9 — the entry words ride the body and the item, after the numbers
    assert p["title"] == f"{emoji} GGA · {label} A+ entry" and AL.entry_words(setup) in p["body"]
    assert AL.entry_words(setup) in p["items"][0]["text"]
    assert p["url"] == f"/chart-maps?tab=gajjala&sub={setup}&focus=GGA"
    assert p["kind"] == "gajjala_setup" and p["ticker"] == "GGA" and p["tag"] == f"gg-{setup}-GGA"
    assert "Float 3.1M" in p["body"] and "UNMEASURED" in p["body"]
    for text in (p["title"], p["body"], p["items"][0]["text"]):
        assert B_WORD not in text.lower()


def test_compose_squeeze_label_and_stop_risk():
    p = AL.compose(read("reversal_squeeze", trigger=2.0, stop=1.9), "SQZ", {}, session=S)
    assert p["title"] == "🎾 SQZ · Reversal Squeeze A+ entry"         # WIDENED 2026-10-16: Ajay flipped the A+ kind live ("you alert me when that happens")
    assert "stop 1.90 (−5.0%)" in p["body"]


# ── registries ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_pref_and_the_keep_set():
    # LIVE since 2026-10-16 — default_prefs STAYS False for everyone else (AMENDMENTS10 F1: the 🧠 / 🎚️ precedent,
    # "everyone else starts off"); HIS devices are ON through OWNER_KEEP_SET. The send is owner-only either way.
    from push import subs
    assert subs.default_prefs()["gajjala_setup"] is False
    assert "gajjala_setup" in subs.OWNER_KEEP_SET
    assert subs.owner_prefs()["gajjala_setup"] is True


def test_the_hook_sends_owner_scoped_under_its_own_kind(monkeypatch):
    from push import hooks, sender
    seen = []
    monkeypatch.setattr(sender, "send_to_user", lambda email, payload, kind=None: seen.append((email, kind)) or
                        {"sent": 1, "failed": 0, "total_targets": 1})
    hooks.notify_gajjala_setup(owner="owner@example.com", payload={"title": "x"})
    assert seen == [("owner@example.com", "gajjala_setup")]


def test_the_alerts_row_is_registered():
    from supply_demand import alert_status as AS
    assert AS.GAJJALA_KIND == "gajjala_setup" and AS.GAJJALA_KIND in AS.PASS_KINDS
    assert AS.CADENCE_SEC[AS.GAJJALA_KIND] == GC.PASS_CADENCE_SEC == 300
    assert AS.PASS_KINDS.index("gajjala_setup") == AS.PASS_KINDS.index("med_catalyst") + 1


def test_the_item_url_resolves_the_sub_from_focus():
    from push import recent as R
    assert R.item_url("gajjala_setup", "NVDA") == "/chart-maps?tab=gajjala&focus=NVDA"
    assert "gajjala_setup" not in R.DIGEST_KINDS                      # NEGATIVE: every A+ its own push, no digest


# ── /alerts shadow items (2026-10-13, E3) ────────────────────────────────────────────────────────────────────────
# Ajay round A: "every A+ is RECORDED to the alerts ledger and shown on /alerts as shadow — not sent". The recorded
# row must carry everything the page lists (ET time · symbol · setup · trigger/stop · the push's own line · the link)
# and supply_demand.alert_status.read_gajjala_shadow must read exactly what run_pass wrote.
def test_a_shadow_aplus_reaches_the_alerts_page_list_with_the_push_line_and_link(shadow):
    from supply_demand import alert_status as AS
    st = fake_store()
    counts, send = one(st, read())
    items = AS.read_gajjala_shadow(st.alerts_coll(), at(10, 6))
    assert send.calls == [] and len(items) == 1 == counts["shadow_session"]
    it = items[0]
    payload = AL.compose(read(), "GGA", {}, session=S)
    assert it["symbol"] == "GGA" and it["setup"] == "bull_flag" and it["date"] == S.isoformat()
    assert it["url"] == payload["url"] == "/chart-maps?tab=gajjala&sub=bull_flag&focus=GGA"
    assert it["text"] == payload["items"][0]["text"] and "Bull Flag A+" in it["text"]
    assert it["trigger"] == 11.0 and it["stop"] == 10.8125 and it["entry_bar_t"] == stamp(10, 5)
    assert it["note"] == AL.SHADOW_NOTE == "shadow — not sent"
    assert it["at"] and it["at"].startswith(S.isoformat())
    assert B_WORD not in str(it).lower()


def test_NEGATIVE_a_live_push_is_never_listed_as_shadow(live):
    from supply_demand import alert_status as AS
    st = fake_store()
    counts, send = one(st, read())
    assert counts["pushed"] == 1 and len(send.calls) == 1
    assert AS.read_gajjala_shadow(st.alerts_coll(), at(10, 6)) == []


def test_NEGATIVE_a_held_aplus_and_yesterdays_shadow_are_not_todays_shadow_items(shadow):
    from supply_demand import alert_status as AS
    st = fake_store()
    one(st, read(entry=stamp(9, 35)), now=at(9, 36))                   # first 15 minutes → held, not shadow
    prev = date(2026, 10, 12)
    one(st, read(entry=stamp(10, 5, prev)), now=at(10, 6, prev), session=prev, sym="OLD")
    assert [i["symbol"] for i in AS.read_gajjala_shadow(st.alerts_coll(), at(10, 6, prev))] == ["OLD"]
    assert AS.read_gajjala_shadow(st.alerts_coll(), at(10, 6)) == []


# ── 🎯 the A+ entry LIVE (DECISIONS10 D1/D2/D9, AMENDMENTS10 F1/F5/F9/F10, 2026-10-16) ────────────────────────────────
# Ajay 2026-10-16: "you alert me when that happens". These tests ride the SHIPPED mode (no monkeypatch) — the point is
# that the default rings exactly once per key and never for a refused A+. Every one injects owner= and a Spy send=
# (via one()); none reaches alerts._owner() or push.hooks.
def _live_keys(st):
    return [k for k in ledger(st) if k.startswith("GG:") and "#" not in k]


def test_the_shipped_mode_rings_once_per_key():
    st = fake_store()
    send = Spy()
    counts, _ = one(st, read(), send=send)
    assert counts["pushed"] == 1 and counts["shadow"] == 0 and counts["shadow_mode"] == 0 and len(send.calls) == 1
    doc = ledger(st)["GG:2026-10-13|GGA|bull_flag"]
    assert doc["state"] == "pushed" and doc["mode"] == "live"
    assert "SHADOW:GG:2026-10-13|GGA|bull_flag" not in ledger(st)
    counts, _ = one(st, read(entry=stamp(11, 30)), now=at(11, 31), send=send)
    assert counts["claimed_before"] == 1 and counts["pushed"] == 0 and len(send.calls) == 1


def test_NEGATIVE_two_passes_on_the_same_key_send_once():
    """AMENDMENTS10 F10(a): two run_pass calls on the same store / now / A+ key (a re-run, an overlapping pass) →
    exactly ONE send — the claim upsert is the once-a-day gate."""
    st = fake_store()
    send = Spy()
    c1, _ = one(st, read(), send=send)
    c2, _ = one(st, read(), send=send)
    assert c1["pushed"] == 1 and c2["pushed"] == 0 and c2["claimed_before"] == 1
    assert len(send.calls) == 1 and _live_keys(st) == ["GG:2026-10-13|GGA|bull_flag"]


@pytest.mark.parametrize("case,want", [
    # the long_flag band is empty since 2026-10-18 — synthetic variant, the mechanism is what is tested
    ("long_flag", "not_aplus_variant"),
    ("near_kiss", "not_aplus_variant"),
    ("grade_b", "not_aplus_variant"),
    ("premarket", "suppressed_premarket"),
    ("first15", "suppressed_first15"),
    ("after_20", "suppressed_window"),
    ("closed_day", "suppressed_closed"),
    ("dry", "dry"),
])
def test_NEGATIVE_the_shipped_mode_never_rings_a_refused_aplus(case, want):
    st = fake_store()
    send = Spy()
    kw = {"send": send}
    if case == "long_flag":
        r = read(variant="long_flag")
    elif case == "near_kiss":
        r = read("kiss_fly", variant="near_kiss")
    elif case == "grade_b":
        r = read("intraday_vcp", grade="B")
    elif case == "premarket":
        r, kw["now"] = read(entry=stamp(8, 35)), at(8, 36)
    elif case == "first15":
        r, kw["now"] = read(entry=stamp(9, 40)), at(9, 41)
    elif case == "after_20":
        r, kw["now"] = read(entry=stamp(20, 5)), at(20, 6)
    elif case == "closed_day":
        r, kw["now"], kw["session"] = read(entry=stamp(10, 5, LABOR_DAY)), at(10, 6, LABOR_DAY), LABOR_DAY
    else:
        r, kw["dry"] = read(), True
    counts, _ = one(st, r, **kw)
    assert counts[want] == 1 and counts["pushed"] == 0
    assert send.calls == []
    assert _live_keys(st) == []                                          # no day's claim consumed


def test_NEGATIVE_the_toggle_off_drops_it_at_the_sender(monkeypatch):
    """The FakeSubs pattern of test_board_arrival.py: only a device whose stored pref is True is targeted — a False or
    a missing pref is never sent one (default_prefs stays False for everyone else, AMENDMENTS10 F1)."""
    from push import subs

    class FakeSubs:
        def __init__(self, rows): self.rows = rows
        def find(self, q):
            def ok(r):
                for k, v in q.items():
                    if k == "kind":
                        continue
                    cur = r
                    for part in k.split("."):
                        cur = (cur or {}).get(part) if isinstance(cur, dict) else None
                    if cur != v:
                        return False
                return True
            return [r for r in self.rows if ok(r)]

    rows = [{"user_email": "a@x", "prefs": {"gajjala_setup": False}},
            {"user_email": "b@x", "prefs": {}},
            {"user_email": "c@x", "prefs": {"gajjala_setup": True}}]
    db = type("DB", (), {"push_subscriptions": FakeSubs(rows)})()
    monkeypatch.setattr(subs, "_get_db", lambda: db)
    monkeypatch.setattr(subs, "_backfill", lambda _db: None)
    got = subs.list_subscriptions(filter_kind="gajjala_setup", honor_quiet_hours=False)
    assert [r["user_email"] for r in got] == ["c@x"]
    assert "gajjala_setup" not in subs.DISABLED_ALERT_KINDS and "gajjala_setup" not in subs.RETIRED_2026_09_20


def test_entry_words_cover_every_setup_and_no_other():
    from chart_maps.high_beta_tab import FORBIDDEN_WORDS
    assert list(AL.ENTRY_WORDS) == list(GC.SETUPS)
    for s in GC.SETUPS:
        w = AL.entry_words(s)
        assert w and w == w.strip(), s
        low = w.lower()
        assert B_WORD not in low and "fake" not in low
        assert not any(f.lower() in low for f in FORBIDDEN_WORDS), (s, w)
    for s, t in AL.ENTRY_WORDS.items():
        assert not any(ch.isdigit() for ch in t), (s, t)                # numbers come from orderflow.signals
    assert AL.entry_words("nope") == "" and AL.entry_words(None) == "" and AL.entry_words("") == ""   # NEGATIVE


def test_entry_words_follow_the_ema_constants(monkeypatch):
    assert "the 9 EMA" in AL.entry_words("kiss_fly")
    assert AL.entry_words("horizontal_fade").startswith("9 and 21 EMA")
    assert "the 21 EMA" in AL.entry_words("intraday_vcp")
    monkeypatch.setattr(GC, "EMA_FAST", 8)
    assert "the 8 EMA" in AL.entry_words("kiss_fly")
    assert AL.entry_words("horizontal_fade").startswith("8 and 21 EMA")
    monkeypatch.setattr(GC, "EMA_SLOW", 34)
    assert "the 34 EMA" in AL.entry_words("intraday_vcp")


def test_the_body_is_the_entry_story_in_order():
    """BUILD_SPEC10 §3.3 example as amended by AMENDMENTS10 F9 (numbers first)."""
    p = AL.compose(read("kiss_fly", entry=stamp(10, 35)), "gga", {"float_text": "Float 3.2M"}, session=S,
                   potential_at_et="10:05")
    assert p["title"] == "💋 GGA · EMA Kiss & Fly A+ entry"
    assert p["body"] == ("broke 11.00 on the 5m bar closing 10:35 ET · stop 10.81 (−1.7%) · Kissed and honored the 9 "
                         "EMA; entry = the kiss bar's high · 🧠 potential rang 10:05 ET · Float 3.2M · UNMEASURED — "
                         "his setup, not a buy signal")
    assert p["items"] == [{"symbol": "GGA", "text": "GGA · 💋 EMA Kiss & Fly A+ entry · broke 11.00 · stop 10.81 "
                                                    "(−1.7%) · Kissed and honored the 9 EMA; entry = the kiss bar's high"}]
    assert p["url"] == "/chart-maps?tab=gajjala&sub=kiss_fly&focus=GGA"
    bare = AL.compose(read("kiss_fly", entry=stamp(10, 35)), "gga", {"float_text": "Float 3.2M"}, session=S)
    assert "potential rang" not in bare["body"] and bare["body"].endswith(AL.UNMEASURED_TAIL)
    for bad in ("x", "9:5", None, 5, "10:05 ET", ""):                    # NEGATIVE: no clause from a malformed time
        q = AL.compose(read("kiss_fly", entry=stamp(10, 35)), "gga", {}, session=S, potential_at_et=bad)
        assert "potential rang" not in q["body"], bad
    ah = AL.compose(read("kiss_fly", entry=stamp(16, 35)), "gga", {"float_text": "Float 3.2M"}, session=S,
                    potential_at_et="16:10")
    b = ah["body"]
    assert b.index("🧠 potential rang 16:10 ET") < b.index("Float 3.2M") < b.index(AL.AH_TAG) < b.index(AL.UNMEASURED_TAIL)
    assert b.startswith("broke 11.00 on the 5m bar closing 16:35 ET")


def _seed_potential(st, *, session=S, sym="GGA", setup="bull_flag", push="__default__"):
    from chart_maps.gajjala import store as ST
    doc = {"_id": ST.potential_key(session, sym, setup), "date": session.isoformat(), "symbol": sym, "setup": setup}
    if push == "__default__":
        push = {"state": "pushed", "at_et": "09:55"}
    if push is not None:
        doc["push"] = push
    st.coll(ST.POTENTIALS).docs[doc["_id"]] = doc
    return doc


def test_the_potential_clause_rides_only_a_pushed_potential():
    st = fake_store()
    _seed_potential(st)
    counts, send = one(st, read())
    assert counts["pushed"] == 1 and len(send.calls) == 1
    body = send.calls[0][1]["body"]
    assert "🧠 potential rang 09:55 ET" in body
    assert body.index(AL.entry_words("bull_flag")) < body.index("🧠 potential rang")


@pytest.mark.parametrize("seed", [
    {"push": {"state": "no_target", "at_et": "09:55"}},
    {"push": {"state": "failed", "at_et": "09:55"}},
    {"push": {"state": "claimed", "at_et": "09:55"}},
    {"push": None},
    {"push": {"state": "pushed", "at_et": None}},
    {"push": {"state": "pushed", "at_et": "x"}},
    {"setup": "kiss_fly"},                                               # another setup's potential
    {"session": date(2026, 10, 12)},                                     # yesterday's potential
], ids=["no_target", "failed", "claimed", "no_push_block", "at_none", "at_garbage", "other_setup", "yesterday"])
def test_NEGATIVE_no_clause_without_todays_pushed_potential_of_the_same_key(seed):
    st = fake_store()
    _seed_potential(st, **seed)
    counts, send = one(st, read())
    assert counts["pushed"] == 1 and len(send.calls) == 1                # the A+ still rings, exactly once
    assert "potential rang" not in send.calls[0][1]["body"]


def test_NEGATIVE_a_raising_potential_read_still_pushes_without_the_clause(monkeypatch):
    st = fake_store()
    _seed_potential(st)

    def boom(*a, **k):
        raise RuntimeError("mongo down")
    monkeypatch.setattr(st, "get_potential", boom)
    counts, send = one(st, read())
    assert counts["pushed"] == 1 and counts["failed"] == 0 and len(send.calls) == 1
    assert "potential rang" not in send.calls[0][1]["body"]
    assert AL.potential_rang_at(None, S, "GGA", "bull_flag") is None   # no store → no clause


@pytest.mark.parametrize("case", ["dry", "premarket", "variant", "late"])
def test_NEGATIVE_a_dry_or_refused_pass_never_reads_the_potential(monkeypatch, case):
    st = fake_store()
    monkeypatch.setattr(st, "get_potential", lambda *a, **k: pytest.fail("the 🧠 potential was read for a %s A+" % case))
    kw = {}
    if case == "dry":
        r, kw["dry"] = read(), True
    elif case == "premarket":
        r, kw["now"] = read(entry=stamp(8, 35)), at(8, 36)
    # the long_flag band is empty since 2026-10-18 — synthetic variant, the mechanism is what is tested
    elif case == "variant":
        r = read(variant="long_flag")
    else:
        r, kw["now"], kw["frames"] = read(entry=stamp(10, 5)), at(10, 31), frames_at(stamp(10, 30))
    counts, send = one(st, r, **kw)
    assert counts["pushed"] == 0 and send.calls == []
