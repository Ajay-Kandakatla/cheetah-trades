"""🩳🔀 The 🩳 High SI sub's 9-over-21 EMA cross push — the pass step, the pass wiring, the count script (2026-11-23).

Ajay, verbatim (2026-11-23, voice-typed — "talks" = stocks): "And also add alerts for these talks when they are crossing
EMA, 9 EMA over 21 EMA." His answer: the 5-min and the 15-min chart, closed bar only, each frame on its own cross,
04:00–20:00 ET, ONE push per name per frame per cross, a NEW kind.

Pins chart_maps/gajjala/high_si_cross.py (spec highsi §3.5), the run.Deps wiring (§3.6) and
scripts/gajjala_high_si_cross_count.py (§3.7). The push is BUILT OFF: every positive here MONKEYPATCHES the mode to
live — nothing in this file (or any executor) writes the live word into constants.py, and no test pins the mode to a
literal. NEGATIVES are the point: a push he never asked for is the failure.
"""
from __future__ import annotations

import ast
import inspect
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import high_si as HS
from chart_maps.gajjala import high_si_cross as HSX
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import constants as WC
from short_interest import read as SR
from tests.test_gajjala_store import FakeColl, fake_store

ROOT = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")
S = date(2026, 11, 24)                                           # a Tuesday, NYSE open
PREV = date(2026, 11, 23)
THANKSGIVING = date(2026, 11, 26)                                # NYSE closed
HALF = date(2026, 11, 27)                                        # NYSE half day (extended close 17:00)
SATURDAY = date(2026, 11, 28)
OWNER = "owner-local-part" + chr(64) + "example.com"
SYM = "ABC"
LIVE = GC.HIGH_SI_CROSS_PUSH_MODES[1]
OFF = GC.HIGH_SI_CROSS_PUSH_MODES[0]
TAIL = AL.FADE_CROSS_TAIL + " · " + HS.NOT_ADVICE


def at(hh, mm, ss=30, d=S):
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=ET)


def stamp(hh, mm, d=S):
    return f"{d.isoformat()} {hh:02d}:{mm:02d}"


@pytest.fixture(autouse=True)
def _live(monkeypatch):
    """Every test runs with the push monkeypatched LIVE (the built mode is OFF); the mode tests set their own."""
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.setattr(GC, "HIGH_SI_CROSS_PUSH_MODE", LIVE)


class Spy:
    def __init__(self, result=None, raise_=None):
        self.calls, self.raise_ = [], raise_
        self.result = result if result is not None else {"sent": 1, "failed": 0, "total_targets": 1}

    def __call__(self, owner, payload):
        self.calls.append((owner, payload))
        if self.raise_:
            raise self.raise_
        return self.result


def frame_stub(t, f9, f21, closes=None, tf="5m", today=None):
    return SimpleNamespace(t=list(t), ema9=list(f9), ema21=list(f21), c=list(closes or [1.0] * len(t)),
                           today=today if today is not None else range(len(t)), frame=tf)


NONE5 = frame_stub([stamp(10, 20), stamp(10, 25), stamp(10, 30)], [3, 3, 3], [2, 2, 2])
NONE15 = frame_stub([stamp(10, 0), stamp(10, 15), stamp(10, 30)], [3, 3, 3], [2, 2, 2], tf="15m")
T_UP = [stamp(10, 20), stamp(10, 25), stamp(10, 30)]             # the 10:30 bar crosses up
UP9, UP21 = [1, 1, 3], [2, 2, 2]


def frames_stub(F5=None, F15=None):
    return SimpleNamespace(by={"5m": F5 if F5 is not None else NONE5, "15m": F15 if F15 is not None else NONE15})


def up5(t=None, closes=None, d=S):
    return frame_stub(t or [stamp(10, 20, d), stamp(10, 25, d), stamp(10, 30, d)], UP9, UP21,
                      closes or [1.1, 1.2, 1.37])


def up15(t=None):
    return frame_stub(t or [stamp(10, 0), stamp(10, 15), stamp(10, 30)], UP9, UP21, [1.1, 1.2, 1.41], tf="15m")


# the short-interest record (high_si.classify's input) + the pass's float read
def blk(tier=SR.TIER_HIGH, si=1_000_000, rec=3_000_000, status="ok", fc=SR.FLOAT_CONFIRMED, chip="🩳 SI chip"):
    return {"status": status, "tier": tier, "float_check": fc, "si_shares": si, "float_shares": rec, "chip": chip}


def fr(shares=4_000_000, src="float"):
    return {"shares": shares, "src": src}


def go(st=None, *, frames=None, now=None, session=S, blocks=None, floats=None, vol=2_000_000, send=None,
       dry=False, sho=None, flags=frozenset(), sym=SYM):
    st = st if st is not None else fake_store()
    send = send if send is not None else Spy()
    frames = frames if frames is not None else {sym: frames_stub(up5())}
    blocks = blocks if blocks is not None else {sym: blk()}
    floats = floats if floats is not None else {sym: fr()}
    sho_read = sho if callable(sho) else (lambda now: sho if sho is not None else {"items": {}, "complete": True})
    c = HSX.run_step(st, frames, now or at(10, 31), session, floats=floats, volume={sym: vol}, owner=OWNER,
                     send=send, dry=dry, si_read=lambda syms: blocks, sho_read=sho_read, flags=flags)
    return c, send, st


def claims(st):
    return st.alerts_coll().docs


# ── the positives ────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_member_with_a_fresh_5_min_up_cross_rings_once_and_settles_pushed():
    c, send, st = go()
    assert c["pushed"] == 1 and c["listed"] == 1 and c["cross"] == 1 and len(send.calls) == 1
    owner, p = send.calls[0]
    assert owner == OWNER and p["kind"] == GC.HIGH_SI_CROSS_PUSH_KIND
    key = HSX.claim_key(S, SYM, "5m", stamp(10, 30))
    doc = claims(st)[key]
    assert doc["state"] == AL.FADE_CROSS_STATES[1] and doc["kind"] == GC.HIGH_SI_CROSS_PUSH_KIND
    assert doc["bar_t"] == stamp(10, 30) and doc["frame"] == "5m" and doc["tier"] == SR.TIER_HIGH
    assert doc["float_shares"] == 4_000_000 and doc["si_float_shares"] == 3_000_000
    assert doc["result"] == {"sent": 1, "failed": 0, "total_targets": 1, "skipped": None}


def test_the_same_on_the_15_min_frame():
    c, send, st = go(frames={SYM: frames_stub(F15=up15())})
    assert c["pushed"] == 1 and len(send.calls) == 1
    assert HSX.claim_key(S, SYM, "15m", stamp(10, 30)) in claims(st)
    assert "15-min bar closing 10:30 ET" in send.calls[0][1]["body"]


def test_both_frames_crossing_on_one_pass_ring_twice_two_claims_two_tags():
    c, send, st = go(frames={SYM: frames_stub(up5(), up15())})
    assert c["pushed"] == 2 and len(send.calls) == 2 and len(claims(st)) == 2
    tags = [p["tag"] for _o, p in send.calls]
    assert tags == ["ggs-5m-ABC-1030", "ggs-15m-ABC-1030"]


# ── the mode (built OFF; fail closed) ────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("m", [OFF, "shadow", None, "LIVE", " live", 1, True])
def test_NEGATIVE_mode_off_and_junk_modes_never_send_or_claim(monkeypatch, m):
    monkeypatch.setattr(GC, "HIGH_SI_CROSS_PUSH_MODE", m)
    c, send, st = go()
    assert send.calls == [] and c["off"] == 1 and c["pushed"] == 0 and claims(st) == {}


def test_one_mode_read_and_the_constants_agree():
    assert HSX.mode is HS.push_mode
    assert GC.HIGH_SI_CROSS_LATCHES == WC.LATCHES
    assert GC.HIGH_SI_CROSS_PUSH_MODES == GC.FADE_CROSS_PUSH_MODES
    assert GC.HIGH_SI_CROSS_PUSH_MODE in GC.HIGH_SI_CROSS_PUSH_MODES       # never a literal pin
    assert set(HS.REASONS) <= set(HSX.COUNT_KEYS)
    assert HSX.rules_line() == HS.push_text()


# ── the latch ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_second_pass_on_the_same_bar_is_claimed_before():
    st = fake_store()
    go(st)
    c, send, _ = go(st, now=at(10, 32))
    assert send.calls == [] and c["claimed_before"] == 1


def test_a_later_up_cross_the_same_session_rings_again_a_new_claim_id():
    st = fake_store()
    go(st)
    t2 = T_UP + [stamp(10, 35), stamp(10, 40)]
    later = frames_stub(frame_stub(t2, UP9 + [1, 3], UP21 + [2, 2]))          # down at 10:35, up AGAIN at 10:40
    c, send, _ = go(st, frames={SYM: later}, now=at(10, 41))
    assert c["pushed"] == 1 and len(send.calls) == 1 and send.calls[0][1]["tag"] == "ggs-5m-ABC-1040"
    assert HSX.claim_key(S, SYM, "5m", stamp(10, 40)) in claims(st) and len(claims(st)) == 2


def test_NEGATIVE_the_session_latch_holds_the_later_cross(monkeypatch):
    monkeypatch.setattr(GC, "HIGH_SI_CROSS_LATCH", GC.HIGH_SI_CROSS_LATCHES[0])
    st = fake_store()
    go(st)
    t2 = T_UP + [stamp(10, 35), stamp(10, 40)]
    later = frames_stub(frame_stub(t2, UP9 + [1, 3], UP21 + [2, 2]))
    c, send, _ = go(st, frames={SYM: later}, now=at(10, 41))
    assert send.calls == [] and c["claimed_before"] == 1


@pytest.mark.parametrize("latch", ["junk", None, "CROSS", ""])
def test_NEGATIVE_an_unknown_latch_fails_closed_to_session(monkeypatch, latch):
    monkeypatch.setattr(GC, "HIGH_SI_CROSS_LATCH", latch)
    assert HSX.claim_key(S, "abc", "5m", stamp(10, 30)) == "GGS:2026-11-24|ABC|5m"
    monkeypatch.setattr(GC, "HIGH_SI_CROSS_LATCH", GC.HIGH_SI_CROSS_LATCHES[1])
    assert HSX.claim_key(S, "abc", "5m", stamp(10, 30)) == "GGS:2026-11-24|ABC|5m|2026-11-24 10:30"


def test_the_claim_lands_BEFORE_the_send():
    seen = {}
    st = fake_store()

    def peek(owner, payload):
        seen["claimed"] = HSX.claim_key(S, SYM, "5m", stamp(10, 30)) in st.alerts_coll().docs
        return {"sent": 1, "total_targets": 1}
    go(st, send=peek)
    assert seen == {"claimed": True}


# ── NEGATIVE: not a member — the SAME classify as the board ─────────────────────────────────────────────────────
CAP = GC.HIGH_SI_MAX_FLOAT
MEMBER_FLIPS = {
    "no_si": (None, fr()),
    "stale": (blk(status="stale"), fr()),
    "no_tier": (blk(tier=None), fr()),
    "not_high": (blk(tier=SR.TIER_LOW, si=10_000), fr()),
    "floats_disagree": (blk(tier=SR.TIER_HIGH, si=12_722, rec=20_235), fr(361_428)),     # the GMEX shape
    "float_unknown": (blk(), None),
    "float_over": (blk(si=5_000_000), fr(CAP + 1)),
    "si_float_over": (blk(rec=CAP + 1), fr()),
}


def test_the_flips_cover_every_reason():
    assert set(MEMBER_FLIPS) == set(HS.REASONS)


@pytest.mark.parametrize("reason", sorted(MEMBER_FLIPS))
def test_NEGATIVE_a_non_member_with_a_perfect_cross_never_rings(reason):
    b, f = MEMBER_FLIPS[reason]
    assert HS.classify(b, f)["reason"] == reason                     # the board's own function says so
    c, send, st = go(blocks={SYM: b} if b is not None else {}, floats={SYM: f})
    assert send.calls == [] and c[reason] == 1 and c["listed"] == 0 and c["cross"] == 0 and claims(st) == {}


def test_NEGATIVE_the_kitt_shape_floats_disagree_never_rings():
    b, f = blk(tier=SR.TIER_LOW, si=204_000, rec=5_527_831), fr(1_612_787)                 # Low on the record, High on the card
    c, send, _ = go(blocks={SYM: b}, floats={SYM: f})
    assert send.calls == [] and c["floats_disagree"] == 1


# ── NEGATIVE: no cross, a down cross, not its own bar, the first bar ─────────────────────────────────────────────
def test_NEGATIVE_no_cross_and_a_down_cross_never_ring():
    for f9 in ([3, 3, 3], [3, 3, 1]):
        c, send, st = go(frames={SYM: frames_stub(frame_stub(T_UP, f9, UP21))})
        assert send.calls == [] and c["cross"] == 0 and c["listed"] == 1 and claims(st) == {}, f9


def test_NEGATIVE_a_cross_that_is_not_the_latest_bar_is_late():
    old = frames_stub(frame_stub(T_UP, [1, 3, 3], UP21))                     # crossed 10:25, latest bar 10:30
    c, send, _ = go(frames={SYM: old})
    assert send.calls == [] and c["late"] == 1


def test_NEGATIVE_331_seconds_old_is_late_330_rings():
    c, send, _ = go(now=at(10, 30, 0) + timedelta(seconds=AL.MAX_ENTRY_AGE_SEC + 1))
    assert send.calls == [] and c["late"] == 1
    c, send, _ = go(now=at(10, 30, 0) + timedelta(seconds=AL.MAX_ENTRY_AGE_SEC))
    assert c["pushed"] == 1 and AL.MAX_ENTRY_AGE_SEC == 330


def test_NEGATIVE_late_with_a_claim_on_file_counts_claimed_before():
    st = fake_store()
    go(st)
    c, send, _ = go(st, now=at(10, 45))
    assert send.calls == [] and c["claimed_before"] == 1 and c["late"] == 0


def test_NEGATIVE_todays_first_bar_is_never_a_cross_the_watch_rule():
    t = [stamp(19, 55, PREV), stamp(10, 30)]
    F = frame_stub(t, [1, 3], [2, 2], today=range(1, 2))                    # today's FIRST bar crosses over the prior bar
    c, send, _ = go(frames={SYM: frames_stub(F)})
    assert send.calls == [] and c["cross"] == 0
    F2 = frame_stub([stamp(10, 25)] + t[1:], [1, 3], [2, 2], today=range(0, 2))   # the same cross as today's second bar
    c, send, _ = go(frames={SYM: frames_stub(F2)})
    assert c["pushed"] == 1


# ── NEGATIVE: closed day, hours ───────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("d", [SATURDAY, THANKSGIVING])
def test_NEGATIVE_a_closed_day_never_rings(d):
    c, send, st = go(frames={SYM: frames_stub(up5(d=d))}, now=at(10, 31, d=d), session=d)
    assert send.calls == [] and c["closed_day"] == 1 and claims(st) == {}


@pytest.mark.parametrize("bars,now,d", [
    (((3, 45), (3, 50), (3, 55)), (3, 59), S),                   # before 04:00 on the pass clock
    (((19, 50), (19, 55), (20, 0)), (20, 1), S),                 # the bar closing AT the extended close is read after it
    (((16, 50), (16, 55), (17, 0)), (17, 1), HALF),              # the half day's extended close is 17:00
])
def test_NEGATIVE_outside_the_hours_never_rings(bars, now, d):
    F = frame_stub([stamp(hh, mm, d) for hh, mm in bars], UP9, UP21)
    c, send, _ = go(frames={SYM: frames_stub(F)}, now=at(*now, d=d), session=d)
    assert send.calls == [] and c["outside_hours"] == 1


def test_a_half_day_before_its_extended_close_rings():
    F = frame_stub([stamp(16, 40, HALF), stamp(16, 45, HALF), stamp(16, 50, HALF)], UP9, UP21)
    c, send, _ = go(frames={SYM: frames_stub(F)}, now=at(16, 51, d=HALF), session=HALF)
    assert c["pushed"] == 1


# ── NEGATIVE: the first-15 mute is judged by the candle's START ──────────────────────────────────────────────────
def test_NEGATIVE_the_0946_pass_holds_the_15_min_candle_closing_0945():
    F = frame_stub([stamp(9, 15), stamp(9, 30), stamp(9, 45)], UP9, UP21, tf="15m")
    assert PT.window_reason(at(9, 46), S) is None                      # the wall clock would have rung it
    c, send, _ = go(frames={SYM: frames_stub(F15=F)}, now=at(9, 46))
    assert send.calls == [] and c["muted"] == 1


def test_NEGATIVE_the_0946_pass_holds_the_5_min_candle_closing_0945():
    F = frame_stub([stamp(9, 35), stamp(9, 40), stamp(9, 45)], UP9, UP21)
    c, send, _ = go(frames={SYM: frames_stub(F)}, now=at(9, 46))
    assert send.calls == [] and c["muted"] == 1


@pytest.mark.parametrize("bar", [(9, 35), (9, 40)])
def test_NEGATIVE_the_0936_and_0941_passes_hold_their_candles(bar):
    hh, mm = bar
    F = frame_stub([stamp(hh, mm - 10), stamp(hh, mm - 5), stamp(hh, mm)], UP9, UP21)
    c, send, _ = go(frames={SYM: frames_stub(F)}, now=at(hh, mm + 1))
    assert send.calls == [] and c["muted"] == 1


def test_the_5_min_candle_closing_0950_rings_at_0951():
    F = frame_stub([stamp(9, 40), stamp(9, 45), stamp(9, 50)], UP9, UP21)
    c, send, _ = go(frames={SYM: frames_stub(F)}, now=at(9, 51))
    assert c["pushed"] == 1


def test_the_15_min_candle_closing_1000_rings_at_1001():
    F = frame_stub([stamp(9, 30), stamp(9, 45), stamp(10, 0)], UP9, UP21, tf="15m")
    c, send, _ = go(frames={SYM: frames_stub(F15=F)}, now=at(10, 1))
    assert c["pushed"] == 1


def test_the_premarket_candle_closing_0930_rings_at_0931_his_call_5():
    F = frame_stub([stamp(9, 20), stamp(9, 25), stamp(9, 30)], UP9, UP21)
    assert AL.window_reason(stamp(9, 30), S, "5m") == "suppressed_premarket"   # pre-market is NOT a refusal here
    assert PT.window_reason(at(9, 31), S) == "muted"                           # …and the wall-clock mute is not read
    c, send, _ = go(frames={SYM: frames_stub(F)}, now=at(9, 31))
    assert c["pushed"] == 1


def test_NEGATIVE_the_step_never_reads_the_wall_clock_muted_answer(monkeypatch):
    monkeypatch.setattr(PT, "window_reason", lambda now, session: "muted")
    F = frame_stub([stamp(9, 30), stamp(9, 45), stamp(10, 0)], UP9, UP21, tf="15m")
    c, send, _ = go(frames={SYM: frames_stub(F15=F)}, now=at(10, 1))
    assert c["pushed"] == 1 and c["muted"] == 0


# ── NEGATIVE: GG's floor, dry, the store, the SI read, the variant ───────────────────────────────────────────────
@pytest.mark.parametrize("vol", [None, float("nan"), True, "1e6", GC.K11_MIN_SESSION_VOLUME - 1, 999_999])
def test_NEGATIVE_under_ggs_session_floor_or_unknown_never_rings(vol):
    c, send, st = go(vol=vol)
    assert send.calls == [] and c["under_floor"] == 1 and claims(st) == {}


def test_at_the_floor_rings():
    assert GC.K11_MIN_SESSION_VOLUME == 1_000_000
    c, send, _ = go(vol=1_000_000)
    assert c["pushed"] == 1


def test_NEGATIVE_dry_never_sends_or_claims():
    c, send, st = go(dry=True)
    assert send.calls == [] and c["dry"] == 1 and claims(st) == {}


def test_NEGATIVE_no_alert_collection_is_no_store_and_no_send():
    st = fake_store(**{ST.ALERTS: None})
    c, send, _ = go(st)
    assert send.calls == [] and c["no_store"] == 1 and c["pushed"] == 0


@pytest.mark.parametrize("bad", [None, "junk", ["ABC"]])
def test_NEGATIVE_an_unread_short_interest_read_rings_nothing(bad):
    st = fake_store()
    c = HSX.run_step(st, {SYM: frames_stub(up5())}, at(10, 31), S, floats={SYM: fr()}, volume={SYM: 2e6},
                     send=Spy(), si_read=lambda syms: bad)
    assert c["si_unread"] == 1 and c["listed"] == 0 and c["cross"] == 0 and c["pushed"] == 0 and claims(st) == {}


def test_NEGATIVE_a_raising_short_interest_read_rings_nothing():
    def boom(_syms):
        raise RuntimeError("mongo down")
    send = Spy()
    c = HSX.run_step(fake_store(), {SYM: frames_stub(up5())}, at(10, 31), S, floats={SYM: fr()},
                     volume={SYM: 2e6}, send=send, si_read=boom)
    assert c["si_unread"] == 1 and send.calls == []


def test_NEGATIVE_a_non_gg5_store_is_zero_counts():
    for v in (V.GG1, V.GGA):
        st = SimpleNamespace(variant=v, alerts_coll=lambda: FakeColl())
        send = Spy()
        c = HSX.run_step(st, {SYM: frames_stub(up5())}, at(10, 31), S, floats={SYM: fr()}, volume={SYM: 2e6},
                         send=send, si_read=lambda syms: {SYM: blk()})
        assert c == {k: 0 for k in HSX.COUNT_KEYS} and send.calls == [], v


def test_the_si_read_is_one_call_with_every_name():
    seen = []
    HSX.run_step(fake_store(), {"b": frames_stub(up5()), "A": frames_stub(up5())}, at(10, 31), S,
                 floats={"A": fr(), "B": fr()}, volume={"A": 2e6, "B": 2e6}, send=Spy(),
                 si_read=lambda syms: seen.append(list(syms)) or {})
    assert seen == [["A", "B"]]


# ── send faults ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_raising_sender_counts_failed_and_settles_cross_failed_never_twice():
    st = fake_store()
    c, _s, _ = go(st, send=Spy(raise_=RuntimeError("down")))
    assert c["failed"] == 1
    assert claims(st)[HSX.claim_key(S, SYM, "5m", stamp(10, 30))]["state"] == AL.FADE_CROSS_STATES[3]
    c, send, _ = go(st, now=at(10, 32))
    assert send.calls == [] and c["claimed_before"] == 1


def test_no_device_took_it_is_no_target():
    c, _s, st = go(send=Spy(result={"sent": 0, "failed": 0, "total_targets": 0}))
    assert c["no_target"] == 1 and c["pushed"] == 0
    assert claims(st)[HSX.claim_key(S, SYM, "5m", stamp(10, 30))]["state"] == AL.FADE_CROSS_STATES[2]


# ── the payload ───────────────────────────────────────────────────────────────────────────────────────────────────
def _payload(**kw):
    c, send, _ = go(**kw)
    assert c["pushed"] == 1, c
    return send.calls[0][1]


def test_the_payload_shape_no_items_the_kind_the_tag_the_url_the_tail():
    p = _payload()
    assert "items" not in p and p["kind"] == GC.HIGH_SI_CROSS_PUSH_KIND and p["ticker"] == SYM
    assert p["tag"] == "ggs-5m-ABC-1030"
    assert p["url"] == "/chart-maps?tab=gajjala&sub=high_si&tf=5m&focus=ABC"
    assert p["body"].endswith("UNMEASURED — information only, not an entry · Not advice.")
    assert p["body"].endswith(TAIL)
    assert p["title"] == "%s🔀 ABC · %d EMA over %d EMA (5-min)" % (GT.SUB_META[GC.HIGH_SI_SUB][0], GC.EMA_FAST,
                                                                     GC.EMA_SLOW)
    assert p["body"].startswith("%d EMA crossed above %d EMA on the 5-min bar closing 10:30 ET · close "
                                % (GC.EMA_FAST, GC.EMA_SLOW))


def test_the_body_carries_the_si_chip_and_both_floats_each_labelled():
    p = _payload()
    assert "🩳 SI chip" in p["body"]
    both = HS.floats_text(fr(), blk())
    assert both and both in p["body"]
    assert "on this card" in both and "on the short-interest record" in both


def test_the_sho_tag_appears_only_when_the_name_is_on_a_list():
    on = {"items": {SYM: {"short": "🔒 Reg SHO list · 11/20"}}, "complete": True}
    assert "🔒 Reg SHO list · 11/20" in _payload(sho=on)["body"]
    off = _payload(sho={"items": {"ZZZ": {"short": "🔒 other"}}, "complete": False})
    assert "🔒" not in off["body"] and "no list" not in off["body"].lower()


def test_the_add_tag_appears_only_when_the_read_doc_carries_one():
    st = fake_store()
    st.get_read = lambda session, sym: {"ctx": {"trader_text": "📌 algo888", "promo_text": "🎪 promo"}}
    assert "📌 algo888 · 🎪 promo" in _payload(st=st)["body"]
    st2 = fake_store()
    st2.get_read = lambda session, sym: {"ctx": {}}
    assert "📌" not in _payload(st=st2)["body"] and "🎪" not in _payload(st=fake_store())["body"]


def test_the_broker_words_and_icon_appear_only_when_flagged():
    p = _payload(flags=frozenset({SYM}))
    assert GT.BROKER_FLAG_TEXT in p["body"] and p["title"].endswith(" · " + GT.BROKER_FLAG_ICON)
    q = _payload(flags=frozenset({"ZZZ"}))
    assert GT.BROKER_FLAG_TEXT not in q["body"] and GT.BROKER_FLAG_ICON not in q["title"]


def test_a_raising_sho_tag_or_broker_read_drops_only_its_clause(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("down")
    st = fake_store()
    st.get_read = boom
    monkeypatch.setattr(GT, "broker_text_for", boom)
    p = _payload(st=st, sho=boom, flags=frozenset({SYM}))
    assert p["body"].endswith(TAIL) and "🩳 SI chip" in p["body"]
    assert GT.BROKER_FLAG_TEXT not in p["body"] and "🔒" not in p["body"]


def test_the_broker_list_is_read_from_the_store_when_no_flags_are_handed():
    st = fake_store()
    send = Spy()
    HSX.run_step(st, {SYM: frames_stub(up5())}, at(10, 31), S, floats={SYM: fr()}, volume={SYM: 2e6},
                 owner=OWNER, send=send, si_read=lambda syms: {SYM: blk()}, sho_read=lambda now: {"items": {}})
    assert send.calls and GT.BROKER_FLAG_TEXT not in send.calls[0][1]["body"]


def test_NEGATIVE_no_bounce_buy_squeeze_or_on_no_list_in_any_title_or_body():
    on = {"items": {SYM: {"short": "🔒 Reg SHO list · 11/20"}}, "complete": True}
    st = fake_store()
    st.get_read = lambda session, sym: {"ctx": {"trader_text": "📌 algo888"}}
    for p in (_payload(), _payload(sho=on, st=st, flags=frozenset({SYM})),
              _payload(frames={SYM: frames_stub(F15=up15())})):
        text = (p["title"] + " " + p["body"]).lower()
        for w in ("bounce", "buy", "squeeze", "no list", "not on any"):
            assert w not in text, (w, text)


# ── the claim never reaches the 🏁 ────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_the_claim_id_and_state_never_read_as_an_a_plus_row():
    c, _s, st = go()
    (key, doc), = claims(st).items()
    assert key.startswith(GC.HIGH_SI_CROSS_CLAIM_PREFIX + ":")
    assert not key.startswith(("GG:", "GGX:", "GGW:"))
    assert doc["state"] not in ST.LEDGER_ALERT_STATES
    assert all(s not in ST.LEDGER_ALERT_STATES for s in AL.FADE_CROSS_STATES)
    assert st.alert_rows([S]) == []


# ── source guards ─────────────────────────────────────────────────────────────────────────────────────────────────
def _src(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_SOURCE_GUARD_high_si_cross_reuses_the_engines_and_never_fetches_streams_or_trades():
    src = _src("chart_maps/gajjala/high_si_cross.py")
    for bad in (".ewm(", "signals.ema(", "_masked_ema(", "ema9", "ema21", "send_to_all", "requests", "websocket",
                "frames_for(", "load_day", "import trading", "from trading"):
        assert bad not in src, bad
    for good in ("EX.latest_up_cross(watch_crosses(F)", "AL.window_reason(", "PT.window_reason(", "HS.classify(",
                 "AL.is_fresh(", "AL._closed_reason(", "GC.K11_MIN_SESSION_VOLUME", "AL.FADE_CROSS_TAIL",
                 "HS.NOT_ADVICE", "claim_key as _claim"):
        assert good in src, good
    tree = ast.parse(src)
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    mods |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not [m for m in mods if m.split(".")[0] in ("trading", "requests", "websocket", "websockets")]


def test_SOURCE_GUARD_the_claim_comes_before_the_send_in_the_source():
    body = inspect.getsource(HSX.run_step)
    assert body.index("_claim(coll, key, doc)") < body.index("send(owner or AL._owner(), payload)")
    assert body.index("if coll is None:") < body.index("_claim(coll, key, doc)")


def test_NEGATIVE_the_lane_never_trades_these_alerts():
    for p in (ROOT / "trading").rglob("*.py"):
        t = p.read_text(encoding="utf-8")
        assert "gajjala_si_cross" not in t and "GGS:" not in t and "high_si_cross" not in t, p


# ── the pass (run.py) ─────────────────────────────────────────────────────────────────────────────────────────────
class Rec:
    def __init__(self, exc=None, ret=None):
        self.calls, self.exc, self.ret = [], exc, ret

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        if self.exc:
            raise self.exc
        return self.ret if self.ret is not None else {"names": 1, "listed": 0}


def _pass_deps(**kw):
    from tests.test_gajjala_run import make_deps
    deps, _snap, send, _status = make_deps()
    for k, v in kw.items():
        setattr(deps, k, v)
    return deps, send


def test_the_deps_default_off_and_the_cron_deps_carry_both():
    assert RUN.Deps().high_si_cross is None and RUN.Deps().record_high_si_status is None
    assert RUN.dry_deps().high_si_cross is None and RUN.dry_deps().record_high_si_status is None
    cd = RUN._cron_deps()
    assert cd.high_si_cross is HSX.run_step and cd.record_high_si_status is RUN._record_high_si_status


def test_the_pass_calls_the_step_once_with_its_own_reads_and_the_summary_is_byte_equal():
    from tests.test_gajjala_run import NOW as RNOW
    base = RUN.run_pass(RNOW, store=fake_store(), deps=_pass_deps()[0])
    st = fake_store()
    step, row = Rec(), Rec(ret=True)
    deps, _ = _pass_deps(high_si_cross=step, record_high_si_status=row)
    out = RUN.run_pass(RNOW, store=st, deps=deps)
    (a, k), = step.calls
    assert a[0] is st and a[2] == RNOW and a[3] == date(2026, 10, 13) and isinstance(a[1], dict) and a[1]
    assert set(k) == {"floats", "volume", "owner"} and isinstance(k["floats"], dict) and isinstance(k["volume"], dict)
    (ra, _rk), = row.calls
    assert ra[0] == {"names": 1, "listed": 0} and ra[2] is None
    assert out == base and "high_si" not in json.dumps(sorted(out))


def test_NEGATIVE_a_dry_pass_and_an_open_never_call_the_step_or_write_the_row():
    from tests.test_gajjala_run import NOW as RNOW
    step, row = Rec(), Rec()
    deps, _ = _pass_deps(high_si_cross=step, record_high_si_status=row)
    RUN.run_pass(RNOW, store=RUN.dry_store(fake_store()), deps=deps, dry=True)
    RUN.run_on_demand(RNOW, store=fake_store(), deps=deps)
    assert step.calls == [] and row.calls == []


def test_NEGATIVE_a_raising_step_never_reaches_errors_and_records_the_row_with_the_reason():
    from tests.test_gajjala_run import NOW as RNOW
    base = RUN.run_pass(RNOW, store=fake_store(), deps=_pass_deps()[0])
    row = Rec(ret=True)
    deps, _ = _pass_deps(high_si_cross=Rec(exc=RuntimeError("boom")), record_high_si_status=row)
    out = RUN.run_pass(RNOW, store=fake_store(), deps=deps)
    assert out["errors"] == [] and out == base
    (ra, _rk), = row.calls
    assert ra[0] == {} and ra[2] == "pass error: high SI cross"


def test_NEGATIVE_a_raising_row_writer_never_reaches_errors():
    from tests.test_gajjala_run import NOW as RNOW
    deps, _ = _pass_deps(high_si_cross=Rec(), record_high_si_status=Rec(exc=RuntimeError("row down")))
    out = RUN.run_pass(RNOW, store=fake_store(), deps=deps)
    assert out["errors"] == []


def test_the_real_step_on_the_pass_sends_nothing_with_the_mode_off(monkeypatch):
    from tests.test_gajjala_run import NOW as RNOW
    monkeypatch.setattr(GC, "HIGH_SI_CROSS_PUSH_MODE", OFF)
    sends = []
    row = Rec(ret=True)
    deps, send = _pass_deps(high_si_cross=lambda *a, **k: HSX.run_step(*a, **k, send=lambda o, p: sends.append(p),
                                                                      si_read=lambda s: {}),
                            record_high_si_status=row)
    out = RUN.run_pass(RNOW, store=fake_store(), deps=deps)
    assert out["errors"] == [] and sends == []
    (ra, _rk), = row.calls
    assert set(ra[0]) == set(HSX.COUNT_KEYS) and ra[0]["names"] >= 1 and ra[0]["pushed"] == 0


def test_SOURCE_GUARD_one_hook_never_errors_never_an_open():
    src = inspect.getsource(RUN.run_pass)
    assert "if deps.high_si_cross is not None and not push_dry:" in src
    tree = ast.parse(_src("chart_maps/gajjala/run.py"))
    hooks = [n for n in ast.walk(tree) if isinstance(n, ast.If)
             and ast.unparse(n.test).replace("(", "").replace(")", "") == "deps.high_si_cross is not None and not push_dry"]
    assert len(hooks) == 1 and "errors" not in ast.unparse(hooks[0]) and "out[" not in ast.unparse(hooks[0])


def test_the_row_writer_records_the_kind_from_constants(monkeypatch):
    from supply_demand import alert_status as AS
    seen = []
    monkeypatch.setattr(AS, "record_pass", lambda kind, counts, now, reason=None: seen.append((kind, reason)) or True)
    assert RUN._record_high_si_status({"names": 1}, at(10, 31), "r") is True
    assert seen == [(GC.HIGH_SI_CROSS_PUSH_KIND, "r")]


# ── the count script (scripts/gajjala_high_si_cross_count.py) ───────────────────────────────────────────────────
from scripts import gajjala_high_si_cross_count as CNT                     # noqa: E402

DAY = S.isoformat()


def _tile(closes_vol, f9, f21, *, d=S, start=(9, 50), step=5):
    m = start[0] * 60 + start[1]
    bars = []
    for c, v in closes_vol:
        bars.append({"t": f"{d.isoformat()} {m // 60:02d}:{m % 60:02d}", "o": c, "h": c, "l": c, "c": c, "v": v})
        m += step
    curves = [{"tone": "ema9", "label": "9 EMA", "values": f9}, {"tone": "ema21", "label": "21 EMA", "values": f21}]
    return bars, curves


def _read(sym, bars5, curves5, bars15=None, curves15=None, fl=4_000_000):
    return {"_id": ST.key(S, sym), "date": DAY, "symbol": sym, "ctx": {"float": fr(fl)},
            "tile": {"bars5": bars5, "curves5": curves5, "vol_avg5": None,
                     "bars15": bars15 or [], "curves15": curves15 or [], "vol_avg15": None}}


def _count_store(reads, scans):
    st = fake_store()
    for d in reads:
        st.coll(ST.READS).docs[d["_id"]] = d
    for d in scans:
        st.coll(ST.SCAN).docs[d["_id"]] = d
    return st


def _scan(sym, fq=None, d=S):
    doc = {"_id": ST.key(d, sym), "date": d.isoformat(), "symbol": sym, "last": {"volume": 2e6}}
    if fq is not None:
        doc["first_qualified_at"] = fq
    return doc


def test_count_script_counts_through_classify_and_a_floats_disagree_name_is_never_counted():
    bars, cur = _tile([(1.0, 600_000), (1.1, 600_000), (1.2, 600_000)], [1, 1, 3], [2, 2, 2])   # up at 10:00
    reads = [_read("AAA", bars, cur), _read("GMX", bars, cur, fl=361_428)]
    st = _count_store(reads, [_scan("AAA"), _scan("GMX")])
    blocks = {"AAA": blk(), "GMX": blk(si=12_722, rec=20_235)}
    res = CNT.run(1, store=st, si_read=lambda syms: blocks, today=S)
    (row,) = res["sessions"]
    assert row["members"] == ["AAA"] and row["reasons"] == {"floats_disagree": 1}
    assert row["literal"] == ["AAA", "GMX"]                               # his answer #1 read literally lists GMX
    assert row["up_crosses"] == {"5m": 1, "15m": 0}                      # GMX's cross is NOT counted (not a member)
    assert row["rings"]["cross"]["floor"]["total"] == 1
    assert set(res["honesty"]) == set(CNT.HONESTY)


def test_count_script_mutes_by_candle_start_and_sums_only_todays_volume():
    # the 5-min cross bar closes 09:45 (started 09:40 — in his first 15 minutes): muted
    bars, cur = _tile([(1.0, 600_000), (1.1, 600_000), (1.2, 600_000)], [1, 1, 3], [2, 2, 2], start=(9, 35))
    st = _count_store([_read("AAA", bars, cur)], [_scan("AAA")])
    row = CNT.run(1, store=st, si_read=lambda s: {"AAA": blk()}, today=S)["sessions"][0]
    assert row["up_crosses"]["5m"] == 1 and row["rings"]["cross"]["no_floor"]["total"] == 0
    # a cross at 10:00 with 900k today + a huge PRIOR-session bar → under the floor (prior volume never counts)
    prior = [{"t": f"{PREV.isoformat()} 19:55", "o": 1, "h": 1, "l": 1, "c": 1, "v": 50_000_000}]
    bars2, cur2 = _tile([(1.0, 300_000), (1.1, 300_000), (1.2, 300_000)], [1, 1, 1, 3], [2, 2, 2, 2])
    st2 = _count_store([_read("AAA", prior + bars2, cur2)], [_scan("AAA")])
    row2 = CNT.run(1, store=st2, si_read=lambda s: {"AAA": blk()}, today=S)["sessions"][0]
    assert row2["rings"]["cross"]["no_floor"]["total"] == 1 and row2["rings"]["cross"]["floor"]["total"] == 0


def test_count_script_never_counts_a_cross_before_the_name_was_listed():
    bars, cur = _tile([(1.0, 600_000), (1.1, 600_000), (1.2, 600_000)], [1, 1, 3], [2, 2, 2])   # up at 10:00
    late = datetime(2026, 11, 24, 15, 30)                                     # 10:30 ET (naive = UTC, the store's stamp)
    st = _count_store([_read("AAA", bars, cur)], [_scan("AAA", fq=late)])
    row = CNT.run(1, store=st, si_read=lambda s: {"AAA": blk()}, today=S)["sessions"][0]
    assert row["up_crosses"]["5m"] == 1 and row["rings"]["cross"]["no_floor"]["total"] == 0
    early = datetime(2026, 11, 24, 14, 50)                                    # 09:50 ET → the 10:00 cross counts
    st2 = _count_store([_read("AAA", bars, cur)], [_scan("AAA", fq=early)])
    row2 = CNT.run(1, store=st2, si_read=lambda s: {"AAA": blk()}, today=S)["sessions"][0]
    assert row2["rings"]["cross"]["floor"]["total"] == 1


def test_count_script_both_latches_and_writes_nothing():
    # two up crosses on the 5-min tile (10:00 and 10:10): per cross 2, per session 1
    bars, cur = _tile([(1.0, 600_000)] * 5, [1, 1, 3, 1, 3], [2, 2, 2, 2, 2])
    st = _count_store([_read("AAA", bars, cur)], [_scan("AAA")])
    before = {n: st.coll(n).writes for n in ST.ALL}
    res = CNT.run(1, store=st, si_read=lambda s: {"AAA": blk()}, today=S, pushes=True,
                  pushes_read=lambda day: {"gajjala_potential": 3})
    row = res["sessions"][0]
    assert row["rings"]["cross"]["floor"]["total"] == 2 and row["rings"]["session"]["floor"]["total"] == 1
    assert row["pushes"] == {"gajjala_potential": 3}
    assert {n: st.coll(n).writes for n in ST.ALL} == before


def test_NEGATIVE_count_script_an_unread_short_interest_read_counts_nothing():
    bars, cur = _tile([(1.0, 600_000)] * 3, [1, 1, 3], [2, 2, 2])
    st = _count_store([_read("AAA", bars, cur)], [_scan("AAA")])
    (row,) = CNT.run(1, store=st, si_read=lambda s: None, today=S)["sessions"]
    assert row == {"session": DAY, "error": "short interest unread"}


def test_SOURCE_GUARD_count_script_is_read_only_and_reuses_classify():
    src = _src("scripts/gajjala_high_si_cross_count.py")
    assert "HS.classify(" in src and "AL.window_reason(" in src and "PT.window_reason(" in src
    for bad in ("insert_one", "update_one", "replace_one", "delete_", "create_index", "requests", "frames_for(",
                "_get_coll(", "send_to"):
        assert bad not in src, bad
    for h in CNT.HONESTY:
        assert h in ("frequency only — not an edge", "membership uses today's short-interest read",
                     "assumes every pass ran")
