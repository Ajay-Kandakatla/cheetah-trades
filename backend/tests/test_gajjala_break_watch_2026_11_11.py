"""⚡ chart_maps/gajjala/break_watch.py — the intrabar break of an ARMED 🧠 plan (entry spec §3.1 / §5.1, WP-BRK).

Ajay 2026-11-11: "Here is how he enters please tell me to enter based on this". Pure `decide` / `compose` first, then the
print memo, the refresh (fresh docs only, the leave-diff that clears coverage), the ring chain against an in-memory
store. Every NEGATIVE leaves the claim (`brk`) free unless it says otherwise.
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import pathlib
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

import live_feed
from chart_maps.gajjala import alerts as GA
from chart_maps.gajjala import break_watch as BW
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as ST
from tests.test_gajjala_store import FakeColl, fake_store

ET = ZoneInfo("America/New_York")
DAY = "2026-11-11"                                   # a Wednesday, a trading day
ROOT = pathlib.Path(__file__).resolve().parents[1]
FLOOR = GC.K11_MIN_SESSION_VOLUME


def et(h, m, s=0, day=11, month=11):
    return datetime(2026, month, day, h, m, s, tzinfo=ET)


def ep(h, m, s=0):
    return et(h, m, s).timestamp()


def pdoc(sym="ABC", setup="bull_flag", kind="armed", trig=1.17, stop=1.12, bar_t="2026-11-11 10:05", sv=2_000_000,
         frame="5m", **extra):
    last = {"state": GC.POTENTIAL_STATE, "kind": kind, "ready": kind == "armed", "trigger": trig, "stop": stop,
            "bar_t": bar_t, "px": 1.15}
    if sv is not None:
        last["session_volume"] = sv
    last.update(extra.pop("last_extra", {}))
    d = {"_id": f"{DAY}|{sym}|{setup}", "date": DAY, "symbol": sym, "setup": setup, "frame": frame,
         "first_seen_mode": "normal", "last": last}
    d.update(extra)
    return d


def pr(sym, px, t, odd=False):
    return {"sym": sym, "p": px, "s": 50 if odd else 100, "c": [37] if odd else [], "t_ms": int(round(t * 1000)),
            "recv": t, "trfi": False, "kind": "regular"}


class Hooks:
    def __init__(self, res=None, boom=None):
        self.calls, self.res, self.boom = [], res if res is not None else {"sent": 1, "total_targets": 1}, boom

    def notify_gajjala_potential(self, *, owner, payload):
        self.calls.append(("gajjala_potential", owner, payload))
        if self.boom:
            raise self.boom
        return self.res

    def notify_gajjala_setup(self, *, owner, payload):
        self.calls.append(("gajjala_setup", owner, payload))
        return self.res


@pytest.fixture
def bw(monkeypatch):
    BW.reset()
    st = fake_store()
    clock = {"now": et(10, 6, 10)}
    hooks = Hooks()
    auth = {"v": 1000.0}
    monkeypatch.setattr(BW, "_store", lambda: st)
    monkeypatch.setattr(BW, "_now_et", lambda: clock["now"])
    monkeypatch.setattr(BW, "_submit", lambda fn, *a: fn(*a))              # the ring runs inline in the tests
    monkeypatch.setattr(BW, "_hooks", lambda: hooks)
    monkeypatch.setattr(GA, "_owner", lambda: "owner@test")
    monkeypatch.setattr(live_feed, "authed_since", lambda: auth["v"])
    monkeypatch.setattr(GC, "GAJJALA_BREAK_PUSH_MODE", "shadow")
    yield type("NS", (), {"st": st, "clock": clock, "hooks": hooks, "auth": auth})
    BW.reset()


def seed(st, *docs):
    c = st.coll(ST.POTENTIALS)
    for d in docs:
        c.docs[d["_id"]] = dict(d)


def get(st, sym="ABC", setup="bull_flag"):
    return st.coll(ST.POTENTIALS).docs[f"{DAY}|{sym}|{setup}"]


def covered(ns, sym="ABC", **kw):
    """SYM watched at 10:01 as a BUILDING plan (no plan), one print at 10:04 (coverage), then ARMED for the 10:05 bar
    and refreshed at 10:06:10 → plan open 10:05, close 10:10, covered from 10:04."""
    seed(ns.st, pdoc(sym, kind="building", bar_t="2026-11-11 10:00"))
    BW.refresh(DAY, et(10, 1, 10))
    BW.on_print(pr(sym, 1.15, ep(10, 4)))
    for p in kw.pop("early", ()):
        BW.on_print(pr(sym, *p))
    seed(ns.st, pdoc(sym, **kw))
    ns.clock["now"] = et(10, 6, 10)
    BW.refresh(DAY, et(10, 6, 10))


def plan(**kw):
    p = BW.plan_of_doc(pdoc(**kw))
    assert p is not None
    return p


# ── pure decide ────────────────────────────────────────────────────────────────────────────────────────────────
def test_B1_decide_breaks_on_a_round_lot_strictly_over_the_trigger():
    p = plan()
    assert (p["open_t"], p["close_t"]) == (ep(10, 5), ep(10, 10))
    t = p["open_t"] + 40
    assert BW.decide(p, [(t, 1.18)], [(t, 1.15)], p["open_t"] - 60, t) == ("break", t, 1.18)


def test_B3_a_fade_on_15_minute_bars_has_a_15_minute_window():
    p = plan(setup="horizontal_fade", frame="15m", bar_t="2026-11-11 10:00")
    assert p["close_t"] - p["open_t"] == 60 * GA.FRAME_MINUTES["15m"]
    t = ep(10, 12)
    assert BW.decide(p, [(t, 1.18)], [], p["open_t"] - 1, t) == ("break", t, 1.18)


def test_N1_a_print_at_the_trigger_is_not_a_break():
    p = plan()
    t = p["open_t"] + 30
    assert BW.decide(p, [(t, 1.17)], [], p["open_t"], t) == ("wait",)


def test_N3_pure_a_stop_print_first_or_at_the_same_time_wins():
    p = plan()
    a, b = p["open_t"] + 10, p["open_t"] + 20
    assert BW.decide(p, [(b, 1.18)], [(a, 1.11)], p["open_t"], b) == ("stopped_first", a, 1.11)
    assert BW.decide(p, [(a, 1.18)], [(a, 1.11)], p["open_t"], a) == ("stopped_first", a, 1.11)
    assert BW.decide(p, [(a, 1.18)], [(b, 1.11)], p["open_t"], b) == ("break", a, 1.18)   # stop AFTER the break


def test_N4_pure_coverage_after_the_open_is_blind():
    p = plan()
    t = p["open_t"] + 30
    assert BW.decide(p, [(t, 1.2)], [], p["open_t"] + 5, t) == ("blind",)
    assert BW.decide(p, [(t, 1.2)], [], None, t) == ("blind",)
    assert BW.decide(p, [(t, 1.2)], [], p["open_t"], t) == ("break", t, 1.2)          # covered exactly from the open


def test_N5_pure_after_the_close_is_expired():
    p = plan()
    t = p["close_t"] + 1
    assert BW.decide(p, [(t, 1.3)], [], p["open_t"] - 1, t) == ("expired",)
    assert BW.decide(p, [(p["open_t"] - 5, 1.3)], [], p["open_t"] - 10, p["open_t"] + 1) == ("wait",)   # before the bar


# 2026-11-11 review fix: the live bar is LEFT-closed [open_t, close_t) — the same buckets on_print fills
# (floor(t / BUCKET_SEC)) and the detector's minutes. A print at exactly close_t is the NEXT bar's first print.
def test_NEGATIVE_a_print_at_exactly_the_close_is_the_next_bar_never_a_break():
    p = plan()
    t = p["close_t"]
    assert BW.decide(p, [(t, 1.20)], [], p["open_t"] - 1, t) == ("expired",)
    assert BW.decide(p, [(t, 1.20)], [(t, 1.05)], p["open_t"] - 1, t - 1) == ("wait",)   # judged before the close
    assert BW.decide(p, [(t - 1, 1.20)], [], p["open_t"] - 1, t - 1) == ("break", t - 1, 1.20)   # control


def test_a_print_at_exactly_the_open_belongs_to_the_live_bar():
    p = plan()
    t = p["open_t"]
    assert BW.decide(p, [(t, 1.20)], [], t, t + 100) == ("break", t, 1.20)
    assert BW.decide(p, [], [(t, 1.05)], t, t + 100) == ("stopped_first", t, 1.05)
    assert BW.decide(p, [(t - 1, 1.20)], [], t - 1, t + 100) == ("wait",)              # NEGATIVE: the armed bar's own print


def test_N9_plan_of_doc_is_armed_only_and_needs_a_risk():
    assert BW.plan_of_doc(pdoc(kind="building")) is None
    assert BW.plan_of_doc(pdoc(trig=1.12, stop=1.12)) is None                       # ledger.plan_of no_risk
    assert BW.plan_of_doc(pdoc(trig=1.10, stop=1.12)) is None
    assert BW.plan_of_doc(pdoc(bar_t="not a bar")) is None
    d = pdoc()
    d["last"]["state"] = "partial"
    assert BW.plan_of_doc(d) is None
    assert BW.plan_of_doc(pdoc(frame="2h")) is None


def test_plan_risk_is_the_detectors_formula():
    from chart_maps.gajjala import detectors as GD
    r = {}
    GD._levels(r, 1.17, 1.12)
    assert plan()["risk_pct"] == pytest.approx(r["risk_pct"])


# ── compose ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_B6_compose_the_notebooklm_example_exactly():
    p = plan()
    pay = BW.compose(p, {"t": ep(10, 7, 12), "px": 1.18, "last_px": 1.18}, session=DAY)
    assert pay["title"] == "⚡ ABC · 🚩 Bull Flag — traded over the armed trigger 1.17"
    assert pay["body"] == ("traded 1.18 at 10:07:12 ET, over the trigger 1.17 · stop 1.12 (−4.3%) · Quiet shallow "
                           "flag; entry = the top of the pullback bar · the 5m bar has not closed — the A+ push still "
                           "waits for the close · UNMEASURED — an intrabar break of the armed plan, not a buy signal")
    body = pay["body"].replace("10:07:12", "").replace("5m", "")
    nums = set(re.findall(r"\d+(?:\.\d+)?", body))
    assert nums == {"1.18", "1.17", "1.12", "4.3"}
    assert pay["tag"] == "gg-brk-bull_flag-ABC" and not pay["tag"].startswith("gg-pot-")
    assert pay["kind"] == GC.GAJJALA_BREAK_PUSH_KIND and pay["ticker"] == "ABC"
    assert pay["url"] == "/chart-maps?tab=gajjala&sub=bull_flag&focus=ABC"
    assert pay["items"] == [{"symbol": "ABC", "text": pay["title"][len("⚡ "):]}]
    assert not re.search("b" + "ounc", pay["title"] + pay["body"], re.I)


def test_B2_compose_carries_the_last_print_when_it_differs():
    p = plan()
    body = BW.compose(p, {"t": ep(10, 5, 40), "px": 1.18, "last_px": 1.21}, session=DAY)["body"]
    assert body.startswith("traded 1.18 at 10:05:40 ET, over the trigger 1.17 · last 1.21 (+3.4% vs the trigger) · ")


def test_B7_after_hours_and_the_broker_flag():
    from chart_maps.gajjala import tab as GT
    p = plan(bar_t="2026-11-11 16:05")
    pay = BW.compose(p, {"t": ep(16, 6), "px": 1.18, "last_px": 1.18}, broker_text=GT.BROKER_FLAG_TEXT,
                     session=DAY)
    assert GA.AH_TAG in pay["body"] and GT.BROKER_FLAG_TEXT in pay["body"]
    assert pay["title"].endswith(" · " + GT.BROKER_FLAG_ICON)
    assert pay["body"].index(GA.AH_TAG) < pay["body"].index(GT.BROKER_FLAG_TEXT) < pay["body"].index(BW.TAIL)
    rth = BW.compose(plan(), {"t": ep(10, 6), "px": 1.18, "last_px": 1.18}, session=DAY)
    assert GA.AH_TAG not in rth["body"] and "🚫" not in rth["title"]


# ── the flow: memo → decide → ring (shadow default) ───────────────────────────────────────────────────────────────
def test_B5_shadow_records_the_payload_and_never_sends(bw):
    covered(bw)
    BW.on_print(pr("ABC", 1.18, ep(10, 7, 12)))
    brk = get(bw.st)["brk"]
    assert brk["state"] == "shadow" and brk["mode"] == "shadow" and brk["kind"] == GC.GAJJALA_BREAK_PUSH_KIND
    assert brk["print_px"] == 1.18 and brk["trigger"] == 1.17 and brk["stop"] == 1.12
    assert brk["bar_t"] == "2026-11-11 10:05" and brk["print_t"].startswith("2026-11-11T10:07:12")
    want = BW.compose(BW._plans["ABC"][0], {"t": ep(10, 7, 12), "px": 1.18, "last_px": 1.18}, session=DAY)
    assert brk["result"]["would_push"] == want
    assert bw.hooks.calls == []
    assert BW.track_text(get(bw.st)) == "⚡ break seen %s ET (shadow)" % brk["at_et"]


def test_B2_a_plan_landing_late_judges_the_bucket_seen_so_far(bw):
    covered(bw, early=[(1.18, ep(10, 5, 40)), (1.21, ep(10, 6, 5))])
    brk = get(bw.st)["brk"]
    assert brk["print_t"].startswith("2026-11-11T10:05:40") and brk["print_px"] == 1.18 and brk["last_px"] == 1.21
    assert "last 1.21 (+3.4% vs the trigger)" in brk["result"]["would_push"]["body"]


def test_B4_live_claims_sends_once_and_settles(bw, monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_BREAK_PUSH_MODE", "live")
    covered(bw)
    BW.on_print(pr("ABC", 1.18, ep(10, 7, 12)))
    BW.on_print(pr("ABC", 1.25, ep(10, 7, 30)))
    assert len(bw.hooks.calls) == 1
    kind, owner, payload = bw.hooks.calls[0]
    assert kind == GC.GAJJALA_BREAK_PUSH_KIND == payload["kind"] and owner == "owner@test"
    assert payload["tag"] == "gg-brk-bull_flag-ABC"
    brk = get(bw.st)["brk"]
    assert brk["state"] == "pushed" and brk["result"]["sent"] == 1
    assert BW.track_text(get(bw.st)) == "⚡ break rang %s ET" % brk["at_et"]
    assert BW.status()["rang"] == 1


@pytest.mark.parametrize("res,boom,state", [({"sent": 0, "total_targets": 0}, None, "no_target"),
                                            ({"sent": 0, "total_targets": 2}, None, "failed"),
                                            (None, RuntimeError("down"), "failed")])
def test_B4_live_no_target_and_failed(bw, monkeypatch, res, boom, state):
    monkeypatch.setattr(GC, "GAJJALA_BREAK_PUSH_MODE", "live")
    bw.hooks.res, bw.hooks.boom = res or {}, boom
    covered(bw)
    BW.on_print(pr("ABC", 1.18, ep(10, 7, 12)))
    assert get(bw.st)["brk"]["state"] == state and len(bw.hooks.calls) == 1


def test_N2_an_odd_lot_over_the_trigger_is_not_a_break(bw):
    covered(bw)
    BW.on_print(pr("ABC", 1.25, ep(10, 6, 30), odd=True))
    assert "brk" not in get(bw.st) and "brk_held" not in get(bw.st)
    BW.on_print(pr("ABC", 1.18, ep(10, 6, 40)))
    assert get(bw.st)["brk"]["print_px"] == 1.18


def test_N3_a_stop_print_first_is_held_once_and_the_claim_stays_free(bw):
    covered(bw)
    BW.on_print(pr("ABC", 1.11, ep(10, 6, 20), odd=True))       # an odd lot under the stop still counts as the stop
    BW.on_print(pr("ABC", 1.18, ep(10, 6, 40)))
    BW.on_print(pr("ABC", 1.19, ep(10, 6, 50)))
    d = get(bw.st)
    assert "brk" not in d
    assert [h["reason"] for h in d["brk_held"]] == ["stopped_first"]
    assert d["brk_held"][0]["bar_t"] == "2026-11-11 10:05" and d["brk_held"][0]["print_px"] == 1.11
    assert BW.status()["refused"]["stopped_first"] == 1


def test_N3_a_stop_print_landing_with_the_break_timestamp_is_stopped(bw):
    covered(bw)
    t = ep(10, 6, 20)
    BW.on_print(pr("ABC", 1.10, t, odd=True))                    # the stop print and …
    BW.on_print(pr("ABC", 1.18, t))                              # … a break print with the SAME SIP time
    d = get(bw.st)
    assert "brk" not in d and [h["reason"] for h in d["brk_held"]] == ["stopped_first"]


def test_N4_a_reauth_mid_bar_is_blind_then_covered_for_the_next_bar(bw):
    covered(bw)
    bw.auth["v"] = 2000.0                                        # the socket re-authenticated
    BW.on_print(pr("ABC", 1.18, ep(10, 7)))
    d = get(bw.st)
    assert "brk" not in d and [h["reason"] for h in d["brk_held"]] == ["blind"]
    BW.on_print(pr("ABC", 1.16, ep(10, 8)))                      # coverage restarts at 10:07
    seed(bw.st, dict(pdoc(bar_t="2026-11-11 10:10"), brk_held=d["brk_held"]))
    BW.refresh(DAY, et(10, 11, 10))
    BW.on_print(pr("ABC", 1.18, ep(10, 12)))
    assert get(bw.st)["brk"]["bar_t"] == "2026-11-11 10:10"


def test_N4_a_symbol_first_seen_after_the_open_is_blind(bw):
    seed(bw.st, pdoc())
    BW.refresh(DAY, et(10, 6, 10))                               # joins mid-bar, no print seen yet
    d = get(bw.st)
    assert "brk" not in d and [h["reason"] for h in d["brk_held"]] == ["blind"]
    BW.on_print(pr("ABC", 1.18, ep(10, 6, 15)))
    assert "brk" not in get(bw.st) and len(get(bw.st)["brk_held"]) == 1        # written ONCE per (id, bar)


def test_N5_a_print_after_the_close_writes_nothing(bw):
    covered(bw)
    BW.on_print(pr("ABC", 1.30, ep(10, 10, 1)))
    d = get(bw.st)
    assert "brk" not in d and "brk_held" not in d


@pytest.mark.parametrize("bar_t,reason", [("2026-11-11 09:40", "suppressed_first15"),
                                          ("2026-11-11 09:25", "suppressed_premarket"),
                                          ("2026-11-11 20:00", "suppressed_window")])
def test_N6_the_live_bar_is_judged_by_its_start(bw, bar_t, reason):
    seed(bw.st, pdoc(bar_t=bar_t))
    p = BW.plan_of_doc(pdoc(bar_t=bar_t))
    BW._ring(p, ("break", p["open_t"] + 30, 1.18), 1.18)
    d = get(bw.st)
    assert "brk" not in d and [h["reason"] for h in d["brk_held"]] == [reason]


def test_N6_closed_day(bw):
    from market_hours.reminder import ALL_HOLIDAYS
    assert "2026-11-26" in {str(x) for x in ALL_HOLIDAYS}
    bw.clock["now"] = et(10, 6, 10, day=26)
    seed(bw.st, pdoc())
    p = plan()
    BW._ring(p, ("break", p["open_t"] + 30, 1.18), 1.18)
    assert [h["reason"] for h in get(bw.st)["brk_held"]] == ["closed_day"]


@pytest.mark.parametrize("bar_t", ["2026-11-11 09:45", "2026-11-11 15:55", "2026-11-11 16:00",
                                   "2026-11-11 19:55"])
def test_B8_window_boundaries_ring(bw, bar_t):
    seed(bw.st, pdoc(bar_t=bar_t))
    p = BW.plan_of_doc(pdoc(bar_t=bar_t))
    BW._ring(p, ("break", p["open_t"] + 30, 1.18), 1.18)
    brk = get(bw.st)["brk"]
    assert brk["state"] == "shadow"
    ah = GA.AH_TAG in brk["result"]["would_push"]["body"]
    assert ah is (bar_t >= "2026-11-11 16:00")


@pytest.mark.parametrize("sv,reason", [(None, "floor_unknown"), (FLOOR - 1, "under_floor"), (True, "floor_unknown"),
                                       (float("nan"), "floor_unknown")])
def test_N7_the_floor(bw, sv, reason):
    seed(bw.st, pdoc(sv=sv))
    p = BW.plan_of_doc(pdoc(sv=sv))
    BW._ring(p, ("break", p["open_t"] + 30, 1.18), 1.18)
    d = get(bw.st)
    assert "brk" not in d and [h["reason"] for h in d["brk_held"]] == [reason]


def test_B9_the_floor_itself_rings(bw):
    seed(bw.st, pdoc(sv=FLOOR))
    p = BW.plan_of_doc(pdoc(sv=FLOOR))
    BW._ring(p, ("break", p["open_t"] + 30, 1.18), 1.18)
    assert get(bw.st)["brk"]["state"] == "shadow"


def test_N8_a_second_break_the_same_day_is_claimed_before(bw, monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_BREAK_PUSH_MODE", "live")
    covered(bw)
    BW.on_print(pr("ABC", 1.18, ep(10, 7)))
    assert len(bw.hooks.calls) == 1
    p2 = BW.plan_of_doc(pdoc(bar_t="2026-11-11 10:10"))
    BW._ring(p2, ("break", p2["open_t"] + 30, 1.18), 1.18)
    assert len(bw.hooks.calls) == 1 and BW.status()["refused"]["claimed_before"] == 1
    assert get(bw.st)["brk"]["bar_t"] == "2026-11-11 10:05"


def test_N9_building_is_watched_not_a_plan_joined_and_claimed_are_neither(bw):
    seed(bw.st, pdoc("BLD", kind="building"), pdoc("JND", first_seen_mode=ST.JOINED_MODE),
         pdoc("BRK", brk={"state": "shadow"}), pdoc("GRV", graveyard_on=DAY), pdoc("ARM"))
    BW.refresh(DAY, et(10, 6, 10))
    assert BW.symbols() == frozenset({"BLD", "ARM"})
    assert set(BW._plans) == {"ARM"}


def test_N10_mode_off_watches_nothing_and_writes_nothing(bw, monkeypatch):
    covered(bw)
    assert BW.symbols() == frozenset({"ABC"})
    monkeypatch.setattr(GC, "GAJJALA_BREAK_PUSH_MODE", "off")
    assert BW.symbols() == frozenset() and BW.mode() == "off"
    BW.on_print(pr("ABC", 1.18, ep(10, 7)))
    d = get(bw.st)
    assert "brk" not in d and "brk_held" not in d
    assert BW.refresh(DAY, et(10, 7, 10)) == 0
    assert BW.status()["text"].startswith("⚡ Break pushes: off.")


def test_NEGATIVE_an_unknown_mode_fails_closed_to_off(monkeypatch):
    for bad in ("LIVE", "on", None, 1):
        monkeypatch.setattr(GC, "GAJJALA_BREAK_PUSH_MODE", bad)
        assert BW.mode() == "off"


def test_N11_a_kind_without_a_sender_fails_and_never_sends(bw, monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_BREAK_PUSH_MODE", "live")
    monkeypatch.setattr(BW, "KIND", "gajjala_break")
    covered(bw)
    BW.on_print(pr("ABC", 1.18, ep(10, 7)))
    brk = get(bw.st)["brk"]
    assert brk["state"] == "failed" and brk["result"] == {"error": "RuntimeError"}
    assert bw.hooks.calls == []


def test_N12_the_cap_keeps_armed_first_and_counts_the_rest(bw):
    docs = [pdoc(f"A{i:03d}", sv=1_000_000 + i) for i in range(BW.WATCH_MAX)]
    docs += [pdoc(f"B{i}", kind="building", sv=9_000_000_000) for i in range(3)]
    seed(bw.st, *docs)
    BW.refresh(DAY, et(10, 6, 10))
    syms = BW.symbols()
    assert len(syms) == BW.WATCH_MAX and not any(s.startswith("B") for s in syms)
    assert BW.status()["refused"]["refused_cap"] == 3


def test_N12_inside_a_kind_the_bigger_volume_is_kept(bw):
    docs = [pdoc(f"A{i:03d}", sv=1_000_000 + i) for i in range(BW.WATCH_MAX + 2)]
    seed(bw.st, *docs)
    BW.refresh(DAY, et(10, 6, 10))
    assert "A000" not in BW.symbols() and "A001" not in BW.symbols() and "A002" in BW.symbols()


def test_N17_leave_and_come_back_is_blind_until_a_fresh_print(bw):
    seed(bw.st, pdoc(kind="building", bar_t="2026-11-11 09:55"))
    BW.refresh(DAY, et(9, 56, 10))                               # watched from the 09:55 pass
    BW.on_print(pr("ABC", 1.15, ep(9, 58, 40)))                  # prints from 09:58 → covered
    seed(bw.st, pdoc(bar_t="2026-11-11 10:00"))
    BW.refresh(DAY, et(10, 1, 10))                               # armed for the 10:00 bar, covered: no hold
    assert BW._mem["ABC"]["covered_from"] == ep(9, 58, 40) and "brk_held" not in get(bw.st)
    d = pdoc(bar_t="2026-11-11 10:05")
    d["last"]["state"] = "partial"                               # the ~10:06 refresh reads it partial → it LEAVES
    seed(bw.st, d)
    BW.refresh(DAY, et(10, 6, 10))
    assert "ABC" not in BW.symbols() and "ABC" not in BW._mem
    BW.on_print(pr("ABC", 1.16, ep(10, 8)))                      # the hub's copy lags: ignored
    assert "ABC" not in BW._mem
    seed(bw.st, pdoc(bar_t="2026-11-11 10:10"))
    BW.refresh(DAY, et(10, 11, 10))                              # re-added armed, open 10:10
    held = get(bw.st)["brk_held"]
    assert [h["reason"] for h in held] == ["blind"]
    BW.on_print(pr("ABC", 1.18, ep(10, 12)))
    assert "brk" not in get(bw.st)                               # never "break" on that bar
    seed(bw.st, dict(pdoc(bar_t="2026-11-11 10:15"), brk_held=held))
    BW.refresh(DAY, et(10, 16, 10))
    BW.on_print(pr("ABC", 1.18, ep(10, 16, 20)))
    assert get(bw.st)["brk"]["bar_t"] == "2026-11-11 10:15"     # covered since the 10:12 print


def test_N18_stale_plans_are_neither_watched_nor_counted(bw):
    fresh = [pdoc(f"F{i:03d}") for i in range(BW.WATCH_MAX + 3)]
    stale = [pdoc(f"S{i}", bar_t="2026-11-11 09:55", sv=9_000_000_000) for i in range(10)]
    seed(bw.st, *fresh, *stale)
    BW.refresh(DAY, et(10, 6, 10))
    syms = BW.symbols()
    assert len(syms) == BW.WATCH_MAX and not any(s.startswith("S") for s in syms)
    assert BW.status()["refused"]["refused_cap"] == 3
    assert not any(s.startswith("S") for s in BW._plans)


def test_N18_the_store_query_drops_the_graveyard(bw):
    seed(bw.st, pdoc("GRV", graveyard_on=DAY), pdoc("OK"))
    assert [d["symbol"] for d in bw.st.break_watch_docs(DAY)] == ["OK"]


def test_N19_switches_off_never_consult_the_extra_suppression(bw, monkeypatch):
    assert GC.HALT_CALM_BARS is None and GC.AH_EXHAUSTION_MAX_PCT is None
    monkeypatch.setattr(GA, "extra_suppression", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("never")))
    seed(bw.st, pdoc())
    p = plan()
    BW._ring(p, ("break", p["open_t"] + 30, 1.18), 1.18)
    assert get(bw.st)["brk"]["state"] == "shadow"


def test_N19_halt_calm_bars_on(bw, monkeypatch):
    monkeypatch.setattr(GC, "HALT_CALM_BARS", 2)
    ex = {"halt_resume_et": "2026-11-11T10:00:00-05:00", "reg_gain_pct": 10.0}
    seed(bw.st, pdoc(last_extra=ex))
    p = BW.plan_of_doc(pdoc(last_extra=ex))
    BW._ring(p, ("break", p["open_t"] + 30, 1.18), 1.18)
    d = get(bw.st)
    assert "brk" not in d and [h["reason"] for h in d["brk_held"]] == ["suppressed_halt"]


def test_N19_exhaustion_on_after_hours(bw, monkeypatch):
    monkeypatch.setattr(GC, "AH_EXHAUSTION_MAX_PCT", 50)
    ex = {"halt_resume_et": None, "reg_gain_pct": 80.0}
    seed(bw.st, pdoc(bar_t="2026-11-11 16:05", last_extra=ex))
    p = BW.plan_of_doc(pdoc(bar_t="2026-11-11 16:05", last_extra=ex))
    BW._ring(p, ("break", p["open_t"] + 30, 1.18), 1.18)
    assert [h["reason"] for h in get(bw.st)["brk_held"]] == ["suppressed_exhausted"]


def test_N19_a_switch_on_without_the_ctx_fails_closed(bw, monkeypatch):
    monkeypatch.setattr(GC, "HALT_CALM_BARS", 2)
    seed(bw.st, pdoc())
    p = plan()
    BW._ring(p, ("break", p["open_t"] + 30, 1.18), 1.18)
    d = get(bw.st)
    assert "brk" not in d and [h["reason"] for h in d["brk_held"]] == ["suppressed_unknown"]
    BW._ring(p, ("break", p["open_t"] + 40, 1.19), 1.19)
    assert len(get(bw.st)["brk_held"]) == 1                      # once per (plan id, bar)


# ── words ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_N20_track_and_summary_text_negatives():
    assert BW.track_text({}) is None and BW.track_text(None) is None
    for st in ("claimed", "failed", "no_target", "weird", None):
        assert BW.track_text({"brk": {"state": st, "at_et": "10:07:12"}}) is None
    assert BW.track_text({"brk": {"state": "pushed", "at_et": "10:07"}}) is None
    assert BW.track_text({"brk": {"state": "pushed", "at_et": "10:07:12"}}) == "⚡ break rang 10:07:12 ET"
    assert BW.summary_text([]) is None and BW.summary_text(None) is None
    assert BW.summary_text(["weird", "failed"]) is None


def test_summary_text_drops_zero_parts():
    assert BW.summary_text(["pushed", "shadow", "shadow"]) == (
        "⚡ break pushes today: 1 sent · 2 recorded in shadow — they ride the 🧠 toggle, so your phone's 🧠 count = "
        "the 🧠 pushes + these")
    # MOVED 2026-11-11 (review fix): a shadow-only day never says the 🧠-count clause — a shadow record never reaches
    # the phone, so "your phone's 🧠 count = the 🧠 pushes + these" would be false.
    assert BW.summary_text(["shadow"]) == "⚡ break pushes today: 1 recorded in shadow"


def test_NEGATIVE_a_shadow_only_summary_never_claims_the_phone_count():
    for states in (["shadow"], ["shadow", "shadow", "weird"]):
        assert "phone" not in BW.summary_text(states) and BW.SUMMARY_RIDES not in BW.summary_text(states)
    assert BW.summary_text(["pushed"]).endswith(BW.SUMMARY_RIDES)                       # control: one was sent


def test_B11_rules_line_and_status_follow_the_constants(monkeypatch):
    line = BW.rules_line()
    assert line.startswith(f"⚡ {GC.GAJJALA_BREAK_PUSH_KIND} (break of an armed 🧠 plan)")
    assert "1,000,000-share" in line and "before 09:45 ET" in line and "mode shadow" in line
    assert "inside the 5-minute bar" in line and line.endswith("UNMEASURED.")
    monkeypatch.setattr(GC, "NO_TRADE_AFTER_OPEN_MIN", 20)
    monkeypatch.setattr(GC, "K11_MIN_SESSION_VOLUME", 2_500_000)
    monkeypatch.setattr(GC, "GAJJALA_BREAK_PUSH_MODE", "live")
    line = BW.rules_line()
    assert "before 09:50 ET" in line and "2,500,000-share" in line and "mode live" in line
    monkeypatch.setattr(live_feed, "state_word", lambda *a, **k: ("live", "x"))
    assert BW.status()["text"] == BW.TEXTS["live"].format(mute_end="09:50")
    assert "from 09:50 ET" in BW.status()["text"]


def test_status_texts_by_mode_and_the_feed_word(monkeypatch):
    monkeypatch.setattr(live_feed, "state_word", lambda *a, **k: ("live", "🛰 live"))
    assert BW.status()["text"] == BW.TEXTS["shadow"] and BW.status()["mode"] == "shadow"
    assert "SHADOW" in BW.status()["text"] and "/alerts" in BW.status()["text"]
    assert not re.search(r"\d", BW.status()["text"])              # no in-memory count in the words [C7]
    monkeypatch.setattr(live_feed, "state_word", lambda *a, **k: ("kicked", "🛰 kicked 2× today"))
    assert BW.status()["text"] == BW.TEXTS["shadow"] + " 🛰 kicked 2× today"
    s = BW.status()
    assert set(s) == {"mode", "text", "watching", "plans", "rang", "shadow", "refused"}
    assert set(BW.REFUSALS) <= set(s["refused"])


# ── the store and the feed ─────────────────────────────────────────────────────────────────────────────────────
def test_store_claim_settle_hold_guards():
    st = fake_store()
    seed(st, pdoc(), pdoc("JND", first_seen_mode=ST.JOINED_MODE))
    pid = f"{DAY}|ABC|bull_flag"
    assert st.settle_potential_break(pid, {"state": "pushed"}) is False             # never creates a brk
    assert st.hold_potential_break(pid, [{"reason": "blind"}]) is True
    assert st.claim_potential_break(pid, {"state": "claimed", "at_et": "10:07:12"}) == "claimed"
    assert st.claim_potential_break(pid, {"state": "claimed"}) == "taken"
    assert st.hold_potential_break(pid, [{"reason": "x"}]) is False                 # never after the claim
    assert st.settle_potential_break(pid, {"state": "shadow", "at_et": "10:07:13", "kind": "IGNORED"}) is True
    d = get(st)
    assert d["brk"] == {"state": "shadow", "at_et": "10:07:13"} and d["brk_held"] == [{"reason": "blind"}]
    assert "push" not in d and "held" not in d                                    # the 🧠 keys untouched
    assert st.claim_potential_break(f"{DAY}|JND|bull_flag", {"state": "claimed"}) == "taken"


def test_NEGATIVE_a_failing_coll_answers_soft_values():
    st = fake_store(**{ST.POTENTIALS: FakeColl(fail=True)})
    assert st.break_watch_docs(DAY) is None
    assert st.claim_potential_break("x", {}) == "error"
    assert st.settle_potential_break("x", {"state": "y"}) is False and st.hold_potential_break("x", []) is False


def test_NEGATIVE_a_read_fault_keeps_the_previous_watch(bw, monkeypatch):
    covered(bw)
    monkeypatch.setattr(bw.st, "break_watch_docs", lambda day: None)
    BW.refresh(DAY, et(10, 7, 10))
    assert BW.symbols() == frozenset({"ABC"}) and BW._plans["ABC"]


def test_N15_upsert_refuses_the_break_keys_and_track_keeps_them():
    from chart_maps.gajjala import potential as PT
    st = fake_store()
    pid = f"{DAY}|ABC|bull_flag"
    for banned in ("brk", "brk_held"):
        assert banned in ST.POTENTIAL_GUARDED
        assert st.upsert_potential(pid, {}, {banned: 1}) is False
        assert st.upsert_potential(pid, {banned: 1}, {"x": 1}) is False
    assert st.coll(ST.POTENTIALS).docs == {}
    seed(st, dict(pdoc(), brk={"state": "shadow", "at_et": "10:07:12"}, brk_held=[{"reason": "blind"}],
                  state_path=[{"state": "forming", "kind": "armed"}]))
    read = {"state": "forming", "ready": True, "trigger": 1.2, "stop": 1.15, "as_of_bar_t": "2026-11-11 10:10",
            "frame": "5m", "risk_pct": 4.1}
    doc, new = PT.track(st, DAY, "ABC", "bull_flag", read, "armed", et(10, 11, 10), px=1.18, values={})
    assert new is False and doc["brk"]["state"] == "shadow" and doc["brk_held"] == [{"reason": "blind"}]
    stored = get(st)
    assert stored["brk"] == {"state": "shadow", "at_et": "10:07:12"} and stored["last"]["trigger"] == 1.2


def test_N16_authed_since(monkeypatch):
    monkeypatch.setitem(live_feed.feed_state, "authed", False)
    monkeypatch.setitem(live_feed._link, "auth_ts", 123.0)
    assert live_feed.authed_since() is None
    monkeypatch.setitem(live_feed.feed_state, "authed", True)
    assert live_feed.authed_since() == 123.0


# ── source guards ─────────────────────────────────────────────────────────────────────────────────────────────
LANE_SHA = {"trading/gajjala_stream.py": "9f1b6bed38ed5134e9d018a9bb8a6fa0f55da9ea863adcd4f059cb74555378df",
            # re-pinned 2026-11-11: the 🏁 not-traded record (trading.gajjala_untraded) appended two display keys + one
            # read-only block to tab_payload — no order path line moved (test_gajjala_lane_untraded_2026_11_11.py pins that)
            "trading/gajjala_entry.py": "04b013e1c0d1fad6a048a28dc14113eccf08f3ee9504649538d3eee312a295fe"}


def test_N14_break_watch_imports_no_trading_module_and_the_lane_is_byte_identical():
    tree = ast.parse(inspect.getsource(BW))
    names = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            names += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            names.append(n.module or "")
    assert names and not [x for x in names if x == "trading" or x.startswith("trading.")]
    src = inspect.getsource(BW)
    assert "_submit_consumer" not in src and "live_hub.submit" not in src           # its OWN worker [C5]
    for rel, sha in LANE_SHA.items():                                              # stream = origin/main 5b2497e4; entry = that + the 11-11 not-traded display keys
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == sha, rel


def test_N14_the_pinned_equalities():
    import live_hub
    from orderflow import tape as OT
    from trading import gajjala_stream as GS
    assert BW.ODD_LOT_CONDITION == GS.ODD_LOT_CONDITION == 37 and 37 in OT.KEPT_DESPITE_FLAGS
    assert BW.WATCH_MAX == live_hub.INTEREST_MAX
    assert BW.BUCKET_SEC == GC.PASS_CADENCE_SEC
    assert BW.KIND == GC.GAJJALA_BREAK_PUSH_KIND == GC.POTENTIAL_PUSH_KIND
    from push import subs
    # WIDENED 2026-11-12: seven → EIGHT — 📅 long_term (Ajay 2026-11-12: "add an alert list when stocks reach Pankaj's zones …" / "Weekly and if something gets dropped let me know …")
    # The 8th kind is 📅 long_term — not a break-watch kind; the break watch still adds none (HIS CALL #2).
    assert BW.KIND in subs.OWNER_KEEP_SET and len(subs.OWNER_KEEP_SET) == 8
    assert "long_term" in subs.OWNER_KEEP_SET and not [k for k in subs.OWNER_KEEP_SET if "break" in k]


def test_NEGATIVE_on_print_never_raises(bw):
    covered(bw)
    for bad in ({}, {"sym": "ABC"}, {"sym": "ABC", "p": "x", "t_ms": 1}, {"sym": "ABC", "p": 1.2, "t_ms": None},
                {"sym": None, "p": 1.2, "t_ms": 5}):
        BW.on_print(bad)
    assert "brk" not in get(bw.st)


def test_rules_info_carries_the_break_line(monkeypatch):
    from supply_demand import rules_info as RI
    note = RI.sections()["gajjala"]["note"]
    assert " " + BW.rules_line() in note
    assert RI._gg_break_clause() == " " + BW.rules_line()
    monkeypatch.setattr(BW, "rules_line", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert RI._gg_break_clause() == ""
    assert "gajjala" in RI.sections()


def test_the_bar_stamp_is_et():
    assert BW._stamp(et(10, 5).astimezone(timezone.utc).timestamp()) == "2026-11-11 10:05"
