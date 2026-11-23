"""👀 Gajjala's Watch — the 1-minute 9-over-21 EMA cross push (spec 2026-11-15 §3.6, WP-B).

Ajay, verbatim (2026-11-15): "from the videos I notice that when ever 9 EMA crosses over 21 EMA on uptrend is where the
bullish momentum started I need alerts on these from 1 min to I can be ready... I think the cross over is slow but once
it picks up its very rapid..".

Pins: the ONE engine (ema_cross, minus today's first bar — the chart's marks), the fade-cross gate order, the GGW: latch
BEFORE the send in the watch's own collection, the 🧠 kind with NO `items`, the never-late rule (missed_fetch), the held
out-param, the ℹ️ clause. NEGATIVES are the point: a push he never asked for is the failure.
"""
from __future__ import annotations

import re
import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as DT
from chart_maps.gajjala import ema_cross as EX
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import cross_alerts as XA
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_build_2026_11_15 import PREV, S, at, raw_day, stamp

ET = ZoneInfo("America/New_York")
THANKSGIVING = date(2026, 11, 26)
OWNER = "owner@example.com"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


class Spy:
    def __init__(self, result=None, raise_=None):
        self.calls, self.raise_ = [], raise_
        self.result = result or {"sent": 1, "failed": 0, "total_targets": 1}

    def __call__(self, owner, payload):
        self.calls.append((owner, payload))
        if self.raise_:
            raise self.raise_
        return self.result


class SF:
    """A Frame stand-in: closed bars oldest first, today = every bar unless given."""
    def __init__(self, t, f9, f21, closes=None, frame="1m", today=None):
        self.t, self.ema9, self.ema21 = list(t), list(f9), list(f21)
        self.c = list(closes or [1.0 + i / 100 for i in range(len(t))])
        self.today = today if today is not None else range(len(t))
        self.frame = frame

    def __len__(self):
        return len(self.t)


def frames_stub(F1, F15=None, F5=None, vol=2_000_000):
    # RE-PINNED 2026-11-23 (frames 1 / 5 / 15): the second slot is the 15-min frame (was 3m)
    by = {"1m": F1}
    if F15 is not None:
        by["15m"] = F15
    if F5 is not None:
        by["5m"] = F5
    return SimpleNamespace(by=by, frame=lambda tf: by.get(tf, F1), vol=vol, session=S.isoformat())


@pytest.fixture(autouse=True)
def _stub_volume(monkeypatch):
    real = B.session_volume
    monkeypatch.setattr(B, "session_volume", lambda fr: fr.vol if hasattr(fr, "vol") else real(fr))


def m(hh, mm, d=S):
    return stamp(d, hh, mm)


def up_at(hh, mm, d=S, n=4):
    """1m bars ending at hh:mm; the 9 crosses above the 21 on the LAST bar."""
    base = hh * 60 + mm
    t = [stamp(d, (base - k) // 60, (base - k) % 60) for k in range(n - 1, -1, -1)]
    return SF(t, [1.0] * (n - 1) + [3.0], [2.0] * n)


def go(coll, *, frames=None, now=None, session=S, send=None, seen=None, held=None, dry=False):
    send = send if send is not None else Spy()
    frames = frames if frames is not None else {"OMH": frames_stub(up_at(10, 6))}
    c = XA.run(frames, now or at(S, 10, 6, 30), session, coll=coll, send=send, owner=OWNER, dry=dry, seen=seen,
               held=held)
    return c, send


def key(tf="1m", d=S, sym="OMH", bar_t=None):
    return XA.claim_key(d, sym, tf, bar_t or m(10, 6, d))


# ── the ring ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_fresh_1m_up_cross_claims_once_and_sends_once_on_the_potential_kind_without_items():
    coll, held = FakeColl(), {}
    c, send = go(coll, held=held)
    assert c["pushed"] == 1 and c["cross"] == 1 and c["names"] == 1 and len(send.calls) == 1
    owner, p = send.calls[0]
    assert owner == OWNER and p["kind"] == GC.FADE_CROSS_PUSH_KIND == C.PUSH_KIND == GC.POTENTIAL_PUSH_KIND
    assert "items" not in p and p["ticker"] == "OMH"
    assert p["url"] == "/chart-maps?tab=gajjala_watch&focus=OMH" and p["tag"] == "ggw-1m-OMH"
    assert list(coll.docs) == ["GGW:2026-11-13|OMH|1m"]
    doc = coll.docs["GGW:2026-11-13|OMH|1m"]
    assert doc["state"] == "cross_pushed" and doc["bar_t"] == m(10, 6) and doc["kind"] == C.PUSH_KIND
    assert doc["frame"] == "1m" and doc["date"] == S.isoformat() and "uptrend_cross" in doc and "uptrend_5m" in doc
    assert held == {"OMH": {"1m": {"bar_t": m(10, 6), "reason": "pushed"}}}


def test_NEGATIVE_the_next_iteration_is_claimed_before_and_never_sends_again():
    coll = FakeColl()
    go(coll)
    nxt = SF(up_at(10, 6).t + [m(10, 7)], [1, 1, 1, 3, 3], [2, 2, 2, 2, 2])
    held = {}
    c, send = go(coll, frames={"OMH": frames_stub(nxt)}, now=at(S, 10, 7, 30), held=held)
    assert send.calls == [] and c["claimed_before"] == 1 and c["pushed"] == 0 and held == {}


def _second_cross():
    t = [m(10, 3), m(10, 4), m(10, 5), m(10, 6), m(10, 7), m(10, 8)]
    return frames_stub(SF(t, [1, 1, 1, 3, 1, 3], [2] * 6))          # up 10:06, down 10:07, up AGAIN 10:08


def test_NEGATIVE_a_second_up_cross_the_same_session_is_claimed_before_under_the_session_latch():
    coll = FakeColl()
    go(coll)
    held = {}
    c, send = go(coll, frames={"OMH": _second_cross()}, now=at(S, 10, 8, 30), held=held)
    assert send.calls == [] and c["claimed_before"] == 1 and held == {}


def test_under_the_cross_latch_the_second_up_cross_rings(monkeypatch):
    monkeypatch.setattr(C, "LATCH", "cross")
    coll = FakeColl()
    go(coll)
    c, send = go(coll, frames={"OMH": _second_cross()}, now=at(S, 10, 8, 30))
    assert c["pushed"] == 1 and len(send.calls) == 1
    assert sorted(coll.docs) == ["GGW:2026-11-13|OMH|1m|2026-11-13 10:06", "GGW:2026-11-13|OMH|1m|2026-11-13 10:08"]


@pytest.mark.parametrize("latch", ["session", "junk", None])
def test_claim_key_shapes_and_a_junk_latch_fails_closed_to_session(monkeypatch, latch):
    monkeypatch.setattr(C, "LATCH", latch)
    assert XA.claim_key(S, "omh", "1m", m(10, 6)) == "GGW:2026-11-13|OMH|1m"


def test_NEGATIVE_a_down_cross_never_sends():
    coll = FakeColl()
    dn = SF(up_at(10, 6).t, [3, 3, 3, 1], [2, 2, 2, 2])
    c, send = go(coll, frames={"OMH": frames_stub(dn)})
    assert send.calls == [] and c["cross"] == 0 and coll.docs == {}


def test_NEGATIVE_5m_and_15m_crosses_are_drawn_only():
    # RE-PINNED 2026-11-23: 3m → 15m — "15m" IS on alerts.FRAME_MINUTES, so C.PUSH_FRAMES ("1m",) alone keeps it silent
    coll, held = FakeColl(), {}
    flat1 = SF(up_at(10, 6).t, [3] * 4, [2] * 4)
    F15 = SF([m(9, 15), m(9, 30), m(9, 45), m(10, 0)], [1, 1, 1, 3], [2] * 4, frame="15m")
    F5 = SF([m(9, 50), m(9, 55), m(10, 0), m(10, 5)], [1, 1, 1, 3], [2] * 4, frame="5m")
    c, send = go(coll, frames={"OMH": frames_stub(flat1, F15, F5)}, now=at(S, 10, 6, 30), held=held)
    assert c["not_push_frame"] == 2 and c["cross"] == 2 and send.calls == [] and coll.docs == {} and held == {}


def test_NEGATIVE_a_push_frame_missing_from_the_alerts_clock_fails_closed(monkeypatch):
    # RE-PINNED 2026-11-23: every tf of C.FRAMES (1m / 5m / 15m) is on alerts.FRAME_MINUTES, so the fail-closed fence is
    # exercised by handing the watch a frame the alerts clock does not know ("3m") and naming it a push frame
    monkeypatch.setattr(C, "FRAMES", C.FRAMES + (("3m", "3min"),))
    monkeypatch.setattr(C, "PUSH_FRAMES", ("1m", "3m"))
    assert "3m" not in AL.FRAME_MINUTES
    F3 = SF([m(10, 0), m(10, 3), m(10, 6)], [1, 1, 3], [2] * 3, frame="3m")
    stub = frames_stub(SF(up_at(10, 6).t, [3] * 4, [2] * 4))
    stub.by["3m"] = F3
    c, send = go(FakeColl(), frames={"OMH": stub})
    assert c["not_push_frame"] == 1 and send.calls == []


# ── never late ───────────────────────────────────────────────────────────────────────────────────────────────────
def _latest_minus_one():
    return frames_stub(SF(up_at(10, 6).t + [m(10, 7)], [1, 1, 1, 3, 3], [2] * 5))


def test_C1_3_NEGATIVE_a_cross_the_last_good_read_never_held_is_missed_fetch_never_sent():
    coll, held = FakeColl(), {}
    c, send = go(coll, frames={"OMH": _latest_minus_one()}, now=at(S, 10, 7, 30), seen={"OMH": m(10, 5)},
                 held=held)
    assert c["missed_fetch"] == 1 and send.calls == [] and coll.docs == {}
    assert held == {"OMH": {"1m": {"bar_t": m(10, 6), "reason": "missed_fetch"}}}
    held = {}
    c, _ = go(coll, frames={"OMH": _latest_minus_one()}, now=at(S, 10, 7, 30), seen={}, held=held)
    assert c["missed_fetch"] == 1 and held["OMH"]["1m"]["reason"] == "missed_fetch"   # no read on file at all


def test_NEGATIVE_the_same_cross_after_a_good_read_is_late_and_writes_no_held():
    coll, held = FakeColl(), {}
    c, send = go(coll, frames={"OMH": _latest_minus_one()}, now=at(S, 10, 7, 30), seen={"OMH": m(10, 6)},
                 held=held)
    assert c["late"] == 1 and c["missed_fetch"] == 0 and send.calls == [] and held == {}


def test_NEGATIVE_a_cross_read_91_s_after_its_close_is_late():
    coll, held = FakeColl(), {}
    assert AL.max_entry_age_sec(V.GG1) == 90
    c, send = go(coll, now=at(S, 10, 7, 31), seen={}, held=held)
    assert c["late"] == 1 and send.calls == [] and held == {} and coll.docs == {}
    c, send = go(coll, now=at(S, 10, 7, 30))                                     # 90 s: still its own minute
    assert c["pushed"] == 1


# ── the gates ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_closed_day_never_rings():
    coll, held = FakeColl(), {}
    c, send = go(coll, frames={"OMH": frames_stub(up_at(10, 6, d=THANKSGIVING))},
                 now=at(THANKSGIVING, 10, 6, 30), session=THANKSGIVING, held=held)
    assert c["suppressed_closed"] == 1 and send.calls == [] and coll.docs == {}
    assert held["OMH"]["1m"]["reason"] == "suppressed_closed"


@pytest.mark.parametrize("hh,mm,state", [(9, 20, "suppressed_premarket"), (9, 30, "suppressed_premarket"),
                                         (9, 31, "suppressed_first15"), (9, 45, "suppressed_first15"),
                                         (20, 1, "suppressed_window")])
def test_NEGATIVE_outside_the_a_plus_window_never_rings(hh, mm, state):
    coll, held = FakeColl(), {}
    c, send = go(coll, frames={"OMH": frames_stub(up_at(hh, mm))}, now=at(S, hh, mm, 30), held=held)
    assert c[state] == 1 and send.calls == [] and coll.docs == {}
    assert held["OMH"]["1m"]["reason"] == state


def test_the_first_minute_after_his_15_rings():
    c, send = go(FakeColl(), frames={"OMH": frames_stub(up_at(9, 46))}, now=at(S, 9, 46, 30))
    assert c["pushed"] == 1


@pytest.mark.parametrize("vol", [GC.K11_MIN_SESSION_VOLUME - 1, None, float("nan"), True])
def test_NEGATIVE_under_ggs_floor_or_unknown_never_rings(vol):
    coll, held = FakeColl(), {}
    c, send = go(coll, frames={"OMH": frames_stub(up_at(10, 6), vol=vol)}, held=held)
    assert c["under_floor"] == 1 and send.calls == [] and held["OMH"]["1m"]["reason"] == "under_floor"


def test_at_the_floor_rings():
    c, _ = go(FakeColl(), frames={"OMH": frames_stub(up_at(10, 6), vol=GC.K11_MIN_SESSION_VOLUME)})
    assert c["pushed"] == 1


@pytest.mark.parametrize("mode", ["off", "shadow", None, "LIVE"])
def test_NEGATIVE_mode_off_or_junk_never_claims_or_sends(monkeypatch, mode):
    monkeypatch.setattr(C, "PUSH_MODE", mode)
    coll, held = FakeColl(), {}
    c, send = go(coll, held=held)
    assert XA.mode() == "off" and c["off"] == 1 and send.calls == [] and coll.docs == {}
    assert held["OMH"]["1m"]["reason"] == "off"


def test_NEGATIVE_dry_never_claims_or_sends_and_writes_no_held():
    coll, held = FakeColl(), {}
    c, send = go(coll, dry=True, held=held)
    assert c["dry"] == 1 and send.calls == [] and coll.docs == {} and held == {}


def test_C3_5_NEGATIVE_no_store_never_sends_claim_less():
    held = {}
    c, send = go(None, held=held)
    assert c["no_store"] == 1 and send.calls == [] and held["OMH"]["1m"]["reason"] == "no_store"


def test_a_raising_send_is_failed_and_the_claim_stays_so_it_never_rings_twice():
    coll, held = FakeColl(), {}
    c, _ = go(coll, send=Spy(raise_=RuntimeError("down")), held=held)
    assert c["failed"] == 1 and coll.docs[key()]["state"] == "cross_failed"
    assert held["OMH"]["1m"]["reason"] == "failed"
    c, send = go(coll)
    assert send.calls == [] and c["claimed_before"] == 1


def test_no_device_is_no_target_and_the_latch_lands_before_the_send():
    coll = FakeColl()
    seen = {}

    def peek(owner, payload):
        seen["claimed"] = key() in coll.docs
        return {"sent": 0, "total_targets": 0}
    held = {}
    c, _ = go(coll, send=peek, held=held)
    assert seen == {"claimed": True} and c["no_target"] == 1
    assert coll.docs[key()]["state"] == "cross_no_target" and held["OMH"]["1m"]["reason"] == "no_target"


def test_held_reasons_are_the_constants_words():
    # 🤖 2026-11-17 (spec ggwauto §4 WP-A re-pin): "suppressed_auto" is recorded by auto.hold_crosses, outside the
    # cross engine (byte-identical) — the one held reason that is not a COUNT_KEYS word.
    assert set(C.HELD_REASONS) <= set(XA.COUNT_KEYS) | {"failed", "no_target", C.AUTO_HELD_REASON}
    assert "late" not in C.HELD_REASONS and "claimed_before" not in C.HELD_REASONS


def test_list_order_and_every_name_counted():
    send = Spy()
    frames = {"ZZZ": frames_stub(up_at(10, 6)), "AAA": frames_stub(up_at(10, 6)), "NOP": None}
    c, _ = go(FakeColl(), frames=frames, send=send)
    order = [p["ticker"] for _o, p in send.calls]
    assert order == ["ZZZ", "AAA"] and c["names"] == 3 and c["pushed"] == 2


# ── the trend filter (HIS CALL #4) ───────────────────────────────────────────────────────────────────────────────
def real_cross(vol=5000.0):
    def price(ts):
        mm_ = ts.hour * 60 + ts.minute
        return 14.0 if mm_ >= 10 * 60 + 5 else 10.0 - 0.002 * (mm_ - 4 * 60)
    return B.build_frames("OMH", S, at(S, 10, 6, 30), raw_day(PREV, price=lambda ts: 10.0),
                          raw_day(S, end=(10, 7), price=price, volume=vol), rules=C.FRAMES)


def test_real_frames_ring_the_1m_cross_and_nothing_else():
    # RE-PINNED 2026-11-23 (frames 1 / 5 / 15): was "…and hold the 3m one" (the 3m 10:06 cross). No 5m / 15m bar has
    # closed past the 10:05 jump at 10:06:30 → nothing drawn-only here; the 15-min drawn-only case on REAL frames is
    # pinned in test_gajjala_watch_frames_1_5_15_2026_11_23.py.
    fr = real_cross()
    F1 = fr.frame("1m")
    x = EX.latest_up_cross(XA.watch_crosses(F1), S)
    assert x["ts"] == m(10, 6) == F1.t[-1]
    coll = FakeColl()
    c, send = go(coll, frames={"OMH": fr}, now=at(S, 10, 6, 30))
    assert c["pushed"] == 1 and c["not_push_frame"] == 0 and len(send.calls) == 1
    k5 = DT.uptrend(F1, x["i"])
    assert coll.docs[key()]["uptrend_cross"] is k5
    assert f"K5 uptrend at the cross: 1-min {XA.MARK[k5]}" in send.calls[0][1]["body"]


def k5_false_cross():
    """An up cross on the latest 1m bar while the 21 EMA is still LOWER than 3 bars ago → K5 False."""
    F = SF(up_at(10, 6).t, [1.0, 1.2, 1.5, 2.5], [2.6, 2.4, 2.3, 2.2])
    assert DT.uptrend(F, 3) is False and EX.latest_up_cross(XA.watch_crosses(F))["i"] == 3
    return frames_stub(F)


def test_NEGATIVE_with_no_filter_a_k5_false_cross_still_rings():
    assert C.UPTREND_FILTER is None
    coll = FakeColl()
    c, send = go(coll, frames={"OMH": k5_false_cross()})
    assert c["pushed"] == 1 and coll.docs[key()]["uptrend_cross"] is False
    assert "K5 uptrend at the cross: 1-min ✗ · 5-min —" in send.calls[0][1]["body"]


def test_NEGATIVE_the_k5_cross_frame_filter_holds_a_non_uptrend_cross(monkeypatch):
    monkeypatch.setattr(C, "UPTREND_FILTER", "k5_cross_frame")
    coll, held = FakeColl(), {}
    c, send = go(coll, frames={"OMH": k5_false_cross()}, held=held)
    assert c["not_uptrend"] == 1 and send.calls == [] and coll.docs == {}
    assert held["OMH"]["1m"]["reason"] == "not_uptrend"


def test_the_k5_cross_frame_filter_rings_a_k5_true_cross(monkeypatch):
    monkeypatch.setattr(C, "UPTREND_FILTER", "k5_cross_frame")
    F = SF(up_at(10, 6).t, [1.0, 1.2, 1.5, 2.5], [2.0, 2.05, 2.1, 2.2])
    assert DT.uptrend(F, 3) is True
    c, _ = go(FakeColl(), frames={"OMH": frames_stub(F)})
    assert c["pushed"] == 1


@pytest.mark.parametrize("filt", ["k5_5m", "junk"])
def test_NEGATIVE_the_5m_filter_and_a_junk_filter_hold_when_k5_is_not_true(monkeypatch, filt):
    monkeypatch.setattr(C, "UPTREND_FILTER", filt)
    c, send = go(FakeColl(), frames={"OMH": k5_false_cross()})      # no 5m frame → K5 5m unknown → held
    assert c["not_uptrend"] == 1 and send.calls == []


def test_the_real_volume_floor_is_read_from_the_frames():
    c, _ = go(FakeColl(), frames={"OMH": real_cross(vol=1000.0)}, now=at(S, 10, 6, 30))
    assert c["under_floor"] == 1                                    # 366 minutes × 1,000 < the 1M floor


# ── [C1.5] today's first bar ─────────────────────────────────────────────────────────────────────────────────────
def test_C1_5_NEGATIVE_a_cross_on_todays_first_bar_is_not_a_watch_cross_and_the_chart_agrees():
    def prev_price(ts):
        return 12.0 - 0.004 * (ts.hour * 60 + ts.minute - 240)       # falling into the close: 9 under 21
    fr = B.build_frames("OMH", S, at(S, 4, 1, 30), raw_day(PREV, price=prev_price),
                        raw_day(S, end=(4, 1), price=lambda ts: 30.0), rules=C.FRAMES)
    F = fr.frame("1m")
    raw = EX.frame_crosses(F)
    assert [x["i"] for x in raw] == [F.today.start] and raw[0]["dir"] == "up"
    assert XA.watch_crosses(F) == []
    p = B.tile_payload(fr, "1m")
    assert GT.ema_cross_block({"tf": "1m", "bars": p["bars"], "curves": p["curves"]}) is None
    c, send = go(FakeColl(), frames={"OMH": fr}, now=at(S, 4, 1, 30))
    assert c["cross"] == 0 and send.calls == []
    assert XA.watch_crosses(None) == []


# ── compose / sender ─────────────────────────────────────────────────────────────────────────────────────────────
X = {"i": 3, "ts": m(10, 6), "dir": "up", "ema_fast": 3.0, "ema_slow": 2.0, "close": 4.4612}


def test_compose_every_field_and_the_unmeasured_tail():
    p = XA.compose("omh", "1m", X, False, None)
    assert p["title"] == f"🔀 OMH · 👀 Watch · {GC.EMA_FAST} EMA over {GC.EMA_SLOW} EMA (1-min)"
    want = AL.FADE_CROSS_BODY.format(fast=GC.EMA_FAST, slow=GC.EMA_SLOW, frame="1-min", hhmm="10:06",
                                     px=AL._px(4.4612))
    assert p["body"] == " · ".join((want, "K5 uptrend at the cross: 1-min ✗ · 5-min —", AL.FADE_CROSS_TAIL))
    assert set(p) == {"title", "body", "tag", "url", "kind", "ticker"}


def test_C3_6_compose_fills_the_body_by_keyword(monkeypatch):
    monkeypatch.setattr(AL, "FADE_CROSS_BODY", "{px}|{hhmm}|{frame}|{slow}|{fast}")
    p = XA.compose("OMH", "1m", X, True, True)
    assert p["body"].startswith(f"{AL._px(4.4612)}|10:06|1-min|{GC.EMA_SLOW}|{GC.EMA_FAST} · ")
    assert "1-min ✓ · 5-min ✓" in p["body"]


def test_NEGATIVE_no_buy_word_anywhere():
    for up in (True, False, None):
        p = XA.compose("OMH", "1m", X, up, up)
        assert not re.search(r"\bbuy\b", (p["title"] + " " + p["body"]).lower())
        assert "UNMEASURED" in p["body"]


def test_NEGATIVE_nothing_lands_in_gajjala_alerts_or_a_GG_id():
    coll = FakeColl()
    go(coll)
    assert coll.docs and all(k.startswith("GGW:") for k in coll.docs)
    assert C.CLAIM_PREFIX not in {v.claim_prefix for v in V.VARIANTS} and C.CLAIM_PREFIX != AL.FADE_CROSS_PREFIX
    src = Path(XA.__file__).read_text(encoding="utf-8")
    code = src.split('"""', 2)[2]
    assert "gajjala_alerts" not in code and "alerts_coll" not in code and "AL.claim_key" not in code


def test_the_sender_maps_the_kind_to_the_variants_hook(monkeypatch):
    from push import hooks
    calls = []
    monkeypatch.setattr(hooks, "notify_gajjala_potential", lambda **kw: (calls.append(kw), {"sent": 1})[1])
    assert XA._send(OWNER, {"x": 1}) == {"sent": 1} and calls == [{"owner": OWNER, "payload": {"x": 1}}]


def test_NEGATIVE_an_unmapped_kind_raises_before_push_hooks_is_imported(monkeypatch):
    import push
    monkeypatch.setattr(C, "PUSH_KIND", "gajjala_watch_new_kind")
    monkeypatch.setitem(sys.modules, "push.hooks", None)            # any import of push.hooks would now fail
    monkeypatch.delattr(push, "hooks", raising=False)
    with pytest.raises(RuntimeError, match="no sender"):
        XA._send(OWNER, {})


# ── the ℹ️ clause ────────────────────────────────────────────────────────────────────────────────────────────────
def test_rules_line_carries_the_latch_consequence_and_the_fade_double():
    line = XA.rules_line()
    assert "uses that ticker's one ring for the day, even inside a down-trend" in line
    assert "a later cross is still drawn, not rung" in line
    assert "can ring a second 🔀 from the Fade's 15- or 5-min frame" in line
    assert "never sent late" in line and "UNMEASURED" in line and "mode live" in line
    assert "{:,}".format(GC.K11_MIN_SESSION_VOLUME) in line and "09:45" in line
    # RE-PINNED 2026-11-23 (Ajay: "So 1 min, 5 and 15 accross board") — built from C.FRAMES, never typed
    assert "1-, 5- and 15-min charts" in line and "5- and 15-min crosses are marked only" in line
    assert "3-" not in line


def test_rules_line_follows_the_constants(monkeypatch):
    base = XA.rules_line()
    monkeypatch.setattr(C, "PUSH_MODE", "off")
    off = XA.rules_line()
    assert off != base and "mode off" in off
    monkeypatch.setattr(C, "PUSH_MODE", "live")
    monkeypatch.setattr(C, "UPTREND_FILTER", "k5_cross_frame")
    assert "even inside a down-trend" not in XA.rules_line()
    monkeypatch.setattr(C, "LATCH", "cross")
    assert "on every up cross" in XA.rules_line() and "one ring for the day" not in XA.rules_line()


def test_the_rules_panel_note_carries_the_clause_and_survives_a_broken_module(monkeypatch):
    from supply_demand import rules_info as RI
    assert XA.rules_line() in RI._gajjala_section()["note"]
    monkeypatch.setattr(XA, "rules_line", lambda: 1 / 0)
    assert RI._gg_watch_cross_clause() == ""
    assert "Gajjala's Watch marks" not in RI._gajjala_section()["note"]


def test_k5_5m_reads_the_last_5m_bar_at_or_before_the_cross():
    F5 = SF([m(9, 50), m(9, 55), m(10, 0), m(10, 5), m(10, 10)], [1, 1, 1, 2, 0], [0.5, 0.5, 0.5, 1, 5], frame="5m")
    fr = frames_stub(up_at(10, 6), F5=F5)
    assert XA.k5_5m_at(fr, m(10, 6)) is True                        # the 10:05 bar
    assert XA.k5_5m_at(fr, m(10, 10)) is False                      # the 10:10 bar
    assert XA.k5_5m_at(fr, m(9, 45)) is None                        # NEGATIVE: no 5m bar yet
    assert XA.k5_5m_at(frames_stub(up_at(10, 6)), m(10, 6)) is None  # NEGATIVE: no 5m frame


# ── the read-only count script (HIS CALL #3 / #4 / #5 / #16 counts) ──────────────────────────────────────────────
def test_the_count_script_uses_the_charts_crosses_and_counts_window_latch_and_burst():
    from scripts import gajjala_watch_cross_count as CNT
    fr = real_cross()
    one = CNT.count_session({"OMH": fr, "AMD": real_cross(), "NONE": None}, S)
    row = one["per"]["OMH"]["1m"]
    ups = [x for x in XA.watch_crosses(fr.frame("1m")) if x["dir"] == "up"]
    assert row["up"] == len(ups) and row["in_window"] == 1 and row["latch_loss"] is False
    assert row["premarket"] + row["first15"] + row["after_close"] + row["in_window"] == row["up"]
    assert one["burst_first"] is True and one["burst_first_max"] == 2          # both names ring the same minute
    out = CNT.summarize({S.isoformat(): one})
    assert out["n_names"] == 2 and out["n_sessions"] == 1 and out["burst_sessions_first_ring"] == 1
    assert out["frames"]["1m"]["up"]["n"] == 2 and out["frames"]["1m"]["latch_loss_name_sessions"] == 0
    assert "not an edge" in out["note"]


def test_NEGATIVE_the_count_script_window_judges_the_15m_bar_on_the_1m_clock():
    # RE-PINNED 2026-11-23 (frames 1 / 5 / 15): the 15-min bar is judged by its START as the 1-minute bar (never on a
    # clock of its own)
    from scripts import gajjala_watch_cross_count as CNT
    assert CNT._window({"ts": m(9, 45)}, S, "15m") == "suppressed_first15"        # the 09:30–09:45 bar
    assert CNT._window({"ts": m(9, 30)}, S, "15m") == "suppressed_premarket"      # 09:15–09:30
    assert CNT._window({"ts": m(10, 0)}, S, "15m") is None                        # starts 09:45
    assert "3m" not in AL.FRAME_MINUTES
    assert CNT._sessions(3, S) == [date(2026, 11, 11), PREV, S]
    assert CNT._sessions(1, date(2026, 11, 15)) == [S]                            # a Sunday end → Friday
