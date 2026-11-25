"""🔀 The ➖ Fade 9 / 21 EMA cross — marks on the card + one push per name per session (2026-11-15).

Ajay, verbatim: "I like how you put the 9 EMA and 21 ema cross over for OMH can you add an alert in horizonal fade when
that happens?" · "For any stocks that crossing over and add the same feedback in to that horizontal fade charts".

Pins: the ONE engine (chart_maps/gajjala/ema_cross.py — pure, closed bars, the house EMA, the EMA_FAST / EMA_SLOW spans),
the card block (tab.ema_cross_block / setup_tile: markers + served words, ➖ only), the push (alerts.run_fade_cross:
once per name per session, latch BEFORE send, owner-scoped, the 🧠 kind, the A+ window, the closed-day gate, GG's 1M
floor) and the pass wiring (run.Deps.fade_cross). NEGATIVES are the point: a push he never asked for is the failure.
"""
from __future__ import annotations

import math
from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ema_cross as EX
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from orderflow.signals import ema
from tests.test_gajjala_store import FakeColl, fake_store

ET = ZoneInfo("America/New_York")
S = date(2026, 10, 13)                                           # a Tuesday, NYSE open
PREV = date(2026, 10, 12)
LABOR_DAY = date(2026, 9, 7)
HF = "horizontal_fade"
OWNER = "owner@example.com"


def at(hh, mm, ss=30, d=S):
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=ET)


def stamp(hh, mm, d=S):
    return f"{d.isoformat()} {hh:02d}:{mm:02d}"


SHIPPED_FADE_CROSS_PUSH_MODE = GC.FADE_CROSS_PUSH_MODE         # captured at import, before _live_fade_cross patches it


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


@pytest.fixture(autouse=True)
def _live_fade_cross(monkeypatch):
    # 2026-11-24 — Ajay "ok remove EMA entry alerts and divergence alerts…" ships this push OFF; these tests prove the LIVE path,
    # so it is set "live" explicitly (never a weaker assertion)
    monkeypatch.setattr(GC, "FADE_CROSS_PUSH_MODE", GC.FADE_CROSS_PUSH_MODES[1])


class Spy:
    def __init__(self, result=None, raise_=None):
        self.calls, self.raise_ = [], raise_
        self.result = result or {"sent": 1, "failed": 0, "total_targets": 1}

    def __call__(self, owner, payload):
        self.calls.append((owner, payload))
        if self.raise_:
            raise self.raise_
        return self.result


# ── ema_cross: the ONE engine ──────────────────────────────────────────────────────────────────────────────────────
T4 = ["t0", "t1", "t2", "t3"]


def test_up_and_down_crosses_with_their_values():
    xs = EX.crosses_from_emas([1, 1, 3, 1], [2, 2, 2, 2], T4, [10, 11, 12, 13])
    assert xs == [{"i": 2, "ts": "t2", "dir": EX.UP, "ema_fast": 3.0, "ema_slow": 2.0, "close": 12.0},
                  {"i": 3, "ts": "t3", "dir": EX.DOWN, "ema_fast": 1.0, "ema_slow": 2.0, "close": 13.0}]


def test_prior_bar_at_equal_counts_as_at_or_below():
    assert [x["dir"] for x in EX.crosses_from_emas([2, 3], [2, 2], ["a", "b"])] == [EX.UP]
    assert [x["dir"] for x in EX.crosses_from_emas([2, 1], [2, 2], ["a", "b"])] == [EX.DOWN]


def test_NEGATIVE_no_cross_while_one_side_stays_above():
    assert EX.crosses_from_emas([3, 4, 5, 6], [2, 2, 2, 2], T4) == []
    assert EX.crosses_from_emas([2, 2], [2, 2], ["a", "b"]) == []          # equal → equal is not a cross


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), True, "3"])
def test_NEGATIVE_warm_up_and_junk_are_never_a_cross(bad):
    assert EX.crosses_from_emas([1, bad], [2, 2], ["a", "b"]) == []
    assert EX.crosses_from_emas([bad, 3], [2, 2], ["a", "b"]) == []


def test_NEGATIVE_the_first_bar_has_no_prior_and_short_input_never_raises():
    assert EX.crosses_from_emas([3], [2], ["a"]) == []
    assert EX.crosses_from_emas([], None, None) == []
    assert EX.crosses_from_emas([1, 3, 1], [2, 2], ["a", "b", "c"]) == [               # ragged → the shortest
        {"i": 1, "ts": "b", "dir": EX.UP, "ema_fast": 3.0, "ema_slow": 2.0, "close": None}]


def test_idx_limits_the_judged_bars_but_the_prior_bar_may_sit_outside():
    xs = EX.crosses_from_emas([1, 3, 1, 3], [2, 2, 2, 2], T4, idx=range(1, 2))
    assert [x["i"] for x in xs] == [1]
    assert [x["i"] for x in EX.crosses_from_emas([1, 3, 1, 3], [2, 2, 2, 2], T4, idx=range(3, 4))] == [3]


def _bars(closes, d=S, start=(9, 30), step=5):
    out, m = [], start[0] * 60 + start[1]
    for c in closes:
        m += step
        out.append({"t": f"{d.isoformat()} {m // 60:02d}:{m % 60:02d}", "c": c})
    return out


def test_crosses_runs_the_house_ema_with_the_constant_spans():
    closes = [10.0] * 25 + [9.0] * 10 + [12.0] * 6
    bars = _bars(closes)
    xs = EX.crosses(bars)
    s = pd.Series(closes)
    f, sl = B._masked_ema(s, GC.EMA_FAST), B._masked_ema(s, GC.EMA_SLOW)
    assert xs == EX.crosses_from_emas(f, sl, [b["t"] for b in bars], closes)
    assert [x["dir"] for x in xs] == [EX.DOWN, EX.UP]
    assert xs[-1]["ema_fast"] == pytest.approx(float(ema(s, GC.EMA_FAST).iloc[xs[-1]["i"]]), abs=1e-6)


def test_NEGATIVE_crosses_never_judges_the_live_bar_past_through():
    closes = [10.0] * 25 + [9.0] * 10 + [30.0]                  # only the LAST bar crosses up
    bars = _bars(closes)
    assert EX.latest_up_cross(EX.crosses(bars)) is not None
    assert EX.latest_up_cross(EX.crosses(bars, through=bars[-2]["t"])) is None


def test_NEGATIVE_crosses_warm_up_is_a_gap_and_start_skips_the_early_bars():
    assert EX.crosses(_bars([10.0, 9.0, 12.0, 8.0])) == []           # under 21 bars: no slow EMA yet
    closes = [10.0] * 25 + [9.0] * 10 + [12.0] * 6
    bars = _bars(closes)
    assert [x["dir"] for x in EX.crosses(bars, start=30)] == [EX.UP]
    assert EX.crosses([{"t": None, "c": 1}, "junk", {"t": "x", "c": float("nan")}]) == []


def test_latest_up_cross_and_session_filter():
    xs = [{"ts": stamp(10, 0, PREV), "dir": EX.UP}, {"ts": stamp(10, 5), "dir": EX.UP},
          {"ts": stamp(10, 30), "dir": EX.DOWN}]
    assert EX.latest_up_cross(xs)["ts"] == stamp(10, 5)
    assert EX.latest_up_cross(xs, S)["ts"] == stamp(10, 5)
    assert EX.latest_up_cross(xs, PREV)["ts"] == stamp(10, 0, PREV)
    assert EX.latest_up_cross([x for x in xs if x["dir"] == EX.DOWN]) is None        # NEGATIVE: a down cross only
    assert EX.session_crosses(xs, date(2026, 10, 14)) == []


def test_the_module_is_independent_of_the_fade_sub_and_of_any_timeframe():
    src = (B.__file__.rsplit("/", 1)[0] + "/ema_cross.py")
    text = open(src, encoding="utf-8").read()
    code = text.split('"""', 2)[2]                               # past the module docstring
    for word in ("horizontal_fade", "15m", "5m", "1m", "FADE_CROSS"):
        assert word not in code, word


# ── real frames: closed bars only (the live bucket is never judged) ────────────────────────────────────────────────
def _raw(d, start, end, price_of):
    t0 = pd.Timestamp(datetime(d.year, d.month, d.day, *start), tz=ET)
    t1 = pd.Timestamp(datetime(d.year, d.month, d.day, *end), tz=ET)
    idx_et = pd.date_range(t0, t1, freq="1min", inclusive="left")
    rows = []
    for i, ts in enumerate(idx_et):
        p = price_of(ts)
        m = ts.hour * 60 + ts.minute
        rows.append({"open": p, "high": p + 0.01, "low": p - 0.01, "close": p, "volume": 1000.0,
                     "session": "premarket" if m < 570 else ("rth" if m < 960 else "afterhours")})
    return pd.DataFrame(rows, index=idx_et.tz_convert("UTC").tz_localize(None))


def _today_price(ts):
    """Drifts DOWN all morning (9 under 21), then the 10:25–10:29 minutes (the 10:30 bucket) jump: the 9 crosses up
    on the 5-minute bar stamped 10:30 — and only there."""
    m = ts.hour * 60 + ts.minute
    if m >= 10 * 60 + 25:
        return 14.0
    return 10.0 - 0.002 * (m - 4 * 60)


def real_frames(now):
    return B.build_frames("OMH", S, now, _raw(PREV, (4, 0), (20, 0), lambda ts: 10.0),
                          _raw(S, (4, 0), (10, 30), _today_price))


def test_a_real_frame_crosses_up_on_the_jump_bar_and_frame_crosses_reads_today_only():
    fr = real_frames(at(10, 31))
    F = fr.frame("5m")
    xs = EX.frame_crosses(F)
    assert xs and xs[-1]["dir"] == EX.UP and xs[-1]["ts"] == stamp(10, 30) == F.t[-1]
    assert all(x["i"] in F.today for x in xs)
    assert xs == EX.crosses_from_emas(F.ema9, F.ema21, F.t, F.c, F.today)


def test_NEGATIVE_the_bucket_still_printing_is_not_a_cross():
    fr = real_frames(datetime(2026, 10, 13, 10, 30, GC.BAR_SETTLE_SEC - 5, tzinfo=ET))
    F = fr.frame("5m")
    assert stamp(10, 30) not in F.t
    assert EX.latest_up_cross(EX.frame_crosses(F), S) is None


# ── the card (tab.py) ──────────────────────────────────────────────────────────────────────────────────────────────
def _fr(f9, f21, tf="5m"):
    n = len(f9)
    bars = [{"t": stamp(10, 5 * (k + 1)), "o": 1, "h": 1, "l": 1, "c": 1.0 + k, "v": 1} for k in range(n)]
    return {"tf": tf, "bars": bars, "curves": [{"tone": "ema9", "label": "9 EMA", "values": f9},
                                               {"tone": "ema21", "label": "21 EMA", "values": f21}]}


def test_card_block_serves_every_cross_and_the_latest_as_the_one_line():
    blk = GT.ema_cross_block(_fr([1, 3, 1], [2, 2, 2]))
    up = "🔀 %d EMA crossed above %d EMA at 10:10 ET" % (GC.EMA_FAST, GC.EMA_SLOW)
    dn = "🔀 %d EMA crossed under %d EMA at 10:15 ET" % (GC.EMA_FAST, GC.EMA_SLOW)
    assert blk["crosses"] == [{"t": stamp(10, 10), "dir": "up", "text": up},
                              {"t": stamp(10, 15), "dir": "down", "text": dn}]
    assert blk["dir"] == "down" and blk["text"] == dn and blk["tf"] == "5m"


@pytest.mark.parametrize("f9,f21", [([3, 3, 3], [2, 2, 2]), ([None, None, 3], [2, 2, 2]), ([3], [2]), ([], [])])
def test_NEGATIVE_card_block_none_without_a_cross(f9, f21):
    assert GT.ema_cross_block(_fr(f9, f21)) is None


def test_NEGATIVE_card_block_without_curves_is_none():
    fr = _fr([1, 3], [2, 2])
    fr["curves"] = []
    assert GT.ema_cross_block(fr) is None


def _doc(setup_reads, f9, f21):
    fr = _fr(f9, f21)
    return {"symbol": "OMH", "setups": setup_reads,
            "tile": {"bars5": fr["bars"], "curves5": fr["curves"], "vol_avg5": None,
                     "bars15": fr["bars"], "curves15": fr["curves"], "vol_avg15": None}}


def _tile(doc, setup):
    return GT.setup_tile(doc, setup, "5m", scan_row={}, sess={}, listed=None)


def test_fade_card_marks_up_and_down_in_their_own_kinds_with_the_served_words():
    t = _tile(_doc({HF: {"setup": HF, "state": "forming", "frame": "5m"}}, [1, 3, 1], [2, 2, 2]), HF)
    kinds = [(m["kind"], m["date"], m["price"]) for m in t["markers"]]
    assert kinds == [("ema_cross_up", stamp(10, 10), 3.0), ("ema_cross_dn", stamp(10, 15), 1.0)]
    assert [m["label"] for m in t["markers"]] == [c["text"] for c in t["gajjala"]["ema_cross"]["crosses"]]
    assert "_marks" not in t["gajjala"]["ema_cross"]


def test_NEGATIVE_fade_card_without_a_cross_has_no_key_and_no_marker():
    t = _tile(_doc({HF: {"setup": HF, "state": "forming", "frame": "5m"}}, [3, 3, 3], [2, 2, 2]), HF)
    assert "ema_cross" not in t["gajjala"] and t["markers"] == []


def test_NEGATIVE_a_non_fade_card_is_never_marked():
    for setup in [s for s in GC.SETUPS if s not in GC.FADE_CROSS_SETUPS]:
        t = _tile(_doc({setup: {"setup": setup, "state": "forming", "frame": "5m"}}, [1, 3, 1], [2, 2, 2]), setup)
        assert "ema_cross" not in t["gajjala"], setup
        assert not [m for m in t["markers"] if str(m.get("kind", "")).startswith("ema_cross")], setup


def test_the_aplus_marker_stays_first_beside_the_cross_marks():
    read = {"setup": HF, "state": "aplus", "frame": "5m", "entry_bar_t": stamp(10, 15)}
    t = _tile(_doc({HF: read}, [1, 3, 3], [2, 2, 2]), HF)
    assert t["markers"][0]["kind"] == "buy" and t["markers"][0]["label"] == "A+"
    assert [m["kind"] for m in t["markers"][1:]] == ["ema_cross_up"]


# ── the push (alerts.run_fade_cross) ───────────────────────────────────────────────────────────────────────────────
def frame_stub(t, f9, f21, closes=None, tf="5m", today=None):
    return SimpleNamespace(t=list(t), ema9=list(f9), ema21=list(f21), c=list(closes or [1.0] * len(t)),
                           today=today if today is not None else range(len(t)), frame=tf)


def frames_stub(F5, F15=None):
    by = {"5m": F5, "15m": F15 if F15 is not None else F5}
    return SimpleNamespace(by=by, frame=lambda tf: by.get(tf, F5))


T_UP = [stamp(10, 20), stamp(10, 25), stamp(10, 30)]          # the 10:30 bar crosses up
UP9, UP21 = [1, 1, 3], [2, 2, 2]


def fade_read(state="forming", frame="5m"):
    return {"setup": HF, "state": state, "frame": frame}


def go(store, *, reads=None, frames=None, now=None, send=None, vol=2_000_000, dry=False, session=S, sym="OMH"):
    send = send if send is not None else Spy()
    reads = reads if reads is not None else {sym: {HF: fade_read()}}
    frames = frames if frames is not None else {sym: frames_stub(frame_stub(T_UP, UP9, UP21, [1.1, 1.2, 1.37]))}
    c = AL.run_fade_cross(reads, frames, now or at(10, 31), session, store=store, send=send, owner=OWNER,
                          dry=dry, volume={sym: vol})
    return c, send


def test_a_fresh_up_cross_rings_once_owner_scoped_on_the_potential_kind():
    st = fake_store()
    c, send = go(st)
    assert c["pushed"] == 1 and len(send.calls) == 1
    owner, p = send.calls[0]
    assert owner == OWNER and p["kind"] == GC.FADE_CROSS_PUSH_KIND == GC.POTENTIAL_PUSH_KIND
    assert p["ticker"] == "OMH" and p["url"] == "/chart-maps?tab=gajjala&sub=horizontal_fade&focus=OMH"
    assert "%d EMA crossed above %d EMA on the 5m bar closing 10:30 ET" % (GC.EMA_FAST, GC.EMA_SLOW) in p["body"]
    assert "UNMEASURED" in p["body"] and "information" in p["body"]
    assert not any(w in (p["body"] + p["title"]).lower().split() for w in ("buy", "buy.", "enter"))
    doc = st.alerts_coll().docs[AL.fade_cross_key(S, "OMH", HF)]
    assert doc["state"] == "cross_pushed" and doc["bar_t"] == stamp(10, 30) and doc["kind"] == GC.POTENTIAL_PUSH_KIND


def test_NEGATIVE_a_second_pass_and_a_second_cross_the_same_session_never_ring_again():
    st = fake_store()
    go(st)
    c, send = go(st)                                                       # the same bar re-read
    assert send.calls == [] and c["claimed_before"] == 1
    t2 = T_UP + [stamp(10, 35), stamp(10, 40)]
    later = frames_stub(frame_stub(t2, UP9 + [1, 3], UP21 + [2, 2]))         # down at 10:35, up AGAIN at 10:40
    c, send = go(st, frames={"OMH": later}, now=at(10, 41))
    assert send.calls == [] and c["claimed_before"] == 1 and c["pushed"] == 0


def test_the_latch_lands_BEFORE_the_send_a_raising_send_never_rings_twice():
    st = fake_store()
    c, _ = go(st, send=Spy(raise_=RuntimeError("down")))
    assert c["failed"] == 1 and st.alerts_coll().docs[AL.fade_cross_key(S, "OMH", HF)]["state"] == "cross_failed"
    c, send = go(st)
    assert send.calls == [] and c["claimed_before"] == 1

    seen = {}

    def peek(owner, payload):
        seen["claimed"] = AL.fade_cross_key(S, "OMH", HF) in st2.alerts_coll().docs
        return {"sent": 1, "total_targets": 1}
    st2 = fake_store()
    go(st2, send=peek)
    assert seen == {"claimed": True}


def test_NEGATIVE_no_cross_no_push():
    st = fake_store()
    c, send = go(st, frames={"OMH": frames_stub(frame_stub(T_UP, [3, 3, 3], [2, 2, 2]))})
    assert send.calls == [] and c["cross"] == 0 and st.alerts_coll().docs == {}


def test_NEGATIVE_a_bearish_cross_never_rings():
    st = fake_store()
    c, send = go(st, frames={"OMH": frames_stub(frame_stub(T_UP, [3, 3, 1], [2, 2, 2]))})
    assert send.calls == [] and c["cross"] == 0 and st.alerts_coll().docs == {}


def test_NEGATIVE_an_older_cross_is_late_never_rung():
    st = fake_store()
    old = frames_stub(frame_stub(T_UP, [1, 3, 3], [2, 2, 2]))               # crossed at 10:25, latest bar 10:30
    c, send = go(st, frames={"OMH": old})
    assert send.calls == [] and c["late"] == 1
    c, send = go(st, now=at(10, 45))                                       # the 10:30 cross read 15 min later
    assert send.calls == [] and c["late"] == 1


def test_NEGATIVE_the_live_bar_never_rings_through_real_frames():
    st = fake_store()
    reads = {"OMH": {HF: fade_read()}}
    early = datetime(2026, 10, 13, 10, 30, GC.BAR_SETTLE_SEC - 5, tzinfo=ET)
    c, send = go(st, reads=reads, frames={"OMH": real_frames(early)}, now=early)
    assert send.calls == [] and c["pushed"] == 0
    settled = datetime(2026, 10, 13, 10, 31, 0, tzinfo=ET)
    c, send = go(st, reads=reads, frames={"OMH": real_frames(settled)}, now=settled)
    assert c["pushed"] == 1 and len(send.calls) == 1                       # the same bar once it CLOSED


def test_NEGATIVE_a_non_fade_sub_never_rings():
    st = fake_store()
    reads = {"OMH": {"bull_flag": {"setup": "bull_flag", "state": "forming", "frame": "5m"},
                     "kiss_fly": {"setup": "kiss_fly", "state": "aplus", "frame": "5m"},
                     HF: {"setup": HF, "state": "none", "frame": "5m"}}}
    c, send = go(st, reads=reads)
    assert send.calls == [] and c["listed"] == 0


@pytest.mark.parametrize("state", ["none", "invalid"])
def test_NEGATIVE_a_fade_read_without_a_card_never_rings(state):
    c, send = go(fake_store(), reads={"OMH": {HF: fade_read(state)}})
    assert send.calls == [] and c["listed"] == 0


def test_NEGATIVE_a_closed_day_never_rings():
    st = fake_store()
    t = [stamp(10, 20, LABOR_DAY), stamp(10, 25, LABOR_DAY), stamp(10, 30, LABOR_DAY)]
    c, send = go(st, frames={"OMH": frames_stub(frame_stub(t, UP9, UP21))}, now=at(10, 31, d=LABOR_DAY),
                 session=LABOR_DAY)
    assert send.calls == [] and c["suppressed_closed"] == 1 and st.alerts_coll().docs == {}


@pytest.mark.parametrize("prev,bar,now,state", [
    ((9, 20), (9, 25), (9, 26), "suppressed_premarket"),       # the bar started 09:20
    ((9, 25), (9, 30), (9, 31), "suppressed_premarket"),       # 09:25–09:30 is still pre-market by its START
    ((9, 35), (9, 40), (9, 41), "suppressed_first15"),         # his first 15 minutes
    ((20, 0), (20, 5), (20, 6), "suppressed_window"),          # after the extended close
])
def test_NEGATIVE_outside_the_a_plus_push_window_never_rings(prev, bar, now, state):
    fr = frames_stub(frame_stub([stamp(*prev), stamp(*bar)], [1, 3], [2, 2]))
    c, send = go(fake_store(), frames={"OMH": fr}, now=at(*now))
    assert send.calls == [] and c[state] == 1


@pytest.mark.parametrize("vol", [GC.K11_MIN_SESSION_VOLUME - 1, None, float("nan"), True])
def test_NEGATIVE_under_ggs_session_floor_or_unknown_never_rings(vol):
    c, send = go(fake_store(), vol=vol)
    assert send.calls == [] and c["under_floor"] == 1


def test_at_the_floor_rings():
    c, send = go(fake_store(), vol=GC.K11_MIN_SESSION_VOLUME)
    assert c["pushed"] == 1


def test_NEGATIVE_mode_off_and_a_junk_mode_never_ring(monkeypatch):
    for m in ("off", "shadow", None, "LIVE"):
        monkeypatch.setattr(GC, "FADE_CROSS_PUSH_MODE", m)
        st = fake_store()
        c, send = go(st)
        assert send.calls == [] and c["off"] == 1 and st.alerts_coll().docs == {}, m


def test_NEGATIVE_dry_claims_nothing_and_sends_nothing():
    st = fake_store()
    c, send = go(st, dry=True)
    assert send.calls == [] and c["dry"] == 1 and st.alerts_coll().docs == {}


def test_NEGATIVE_the_one_minute_store_never_rings():
    st = ST.GajjalaStore(colls={n: FakeColl() for n in ST.ALL}, variant=V.GG1)
    c, send = go(st)
    assert send.calls == [] and sum(c.values()) == 0


def test_the_fifteen_minute_fade_read_rings_on_its_own_frame():
    F15 = frame_stub([stamp(10, 0), stamp(10, 15), stamp(10, 30)], UP9, UP21, tf="15m")
    F5 = frame_stub(T_UP, [3, 3, 3], [2, 2, 2])
    c, send = go(fake_store(), reads={"OMH": {HF: fade_read(frame="15m")}}, frames={"OMH": frames_stub(F5, F15)})
    assert c["pushed"] == 1 and "on the 15m bar closing 10:30 ET" in send.calls[0][1]["body"]
    c, send = go(fake_store(), reads={"OMH": {HF: fade_read(frame="5m")}}, frames={"OMH": frames_stub(F5, F15)})
    assert send.calls == []                                               # NEGATIVE: the 5m frame has no cross


def test_NEGATIVE_the_cross_claim_is_never_a_track_record_row():
    st = fake_store()
    go(st)
    doc = st.alerts_coll().docs[AL.fade_cross_key(S, "OMH", HF)]
    assert not doc["_id"].startswith(("GG:", AL.SHADOW_CLAIM_PREFIX))
    assert doc["state"] not in ST.LEDGER_ALERT_STATES
    assert st.alert_rows([S]) == []
    assert LG.alert_of(doc, LG.KINDS[1]) is None
    assert all(s not in ST.LEDGER_ALERT_STATES for s in AL.FADE_CROSS_STATES)


def test_NEGATIVE_the_a_plus_gate_is_untouched_by_a_cross():
    st = fake_store()
    counts = AL.run_pass({"OMH": {HF: fade_read()}}, {"OMH": SimpleNamespace(as_of_bar_t={"5m": stamp(10, 30)})},
                         at(10, 31), S, store=st, send=Spy(), owner=OWNER)
    assert counts["aplus"] == 0 and counts["pushed"] == 0


def test_the_constants_ride_the_existing_kind_and_add_no_number():
    assert GC.FADE_CROSS_PUSH_KIND == GC.POTENTIAL_PUSH_KIND == GC.GAJJALA_BREAK_PUSH_KIND
    # RE-PINNED 2026-11-24 — Ajay "ok remove EMA entry alerts and divergence alerts…": the shipped default is "off"
    assert GC.FADE_CROSS_SETUPS == (HF,) and SHIPPED_FADE_CROSS_PUSH_MODE == GC.FADE_CROSS_PUSH_MODES[0]
    assert GC.FADE_CROSS_PUSH_MODES == ("off", "live")
    from push import subs
    assert GC.FADE_CROSS_PUSH_KIND in subs.OWNER_KEEP_SET                 # no new keep-set kind: it is already there


def test_rules_panel_clause_rides_the_note():
    from supply_demand import rules_info as RI
    note = RI._gajjala_section()["note"]
    assert AL.fade_cross_rules_line() in note
    assert "%d EMA" % GC.EMA_FAST in AL.fade_cross_rules_line() and "UNMEASURED" in AL.fade_cross_rules_line()
    assert "{:,}".format(GC.K11_MIN_SESSION_VOLUME) in AL.fade_cross_rules_line()


# ── the pass wiring (run.py) ───────────────────────────────────────────────────────────────────────────────────────
from tests.test_gajjala_run import NOW, make_deps                      # noqa: E402


class Rec:
    def __init__(self, exc=None):
        self.calls, self.exc = [], exc

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        if self.exc:
            raise self.exc
        return {"pushed": 0}


def test_the_dep_defaults_off_and_the_cron_deps_carry_the_push():
    assert RUN.Deps().fade_cross is None and RUN.dry_deps().fade_cross is None
    assert make_deps()[0].fade_cross is None
    assert RUN._cron_deps().fade_cross is AL.run_fade_cross


def test_the_pass_calls_the_step_once_and_its_summary_stays_byte_equal():
    base = RUN.run_pass(NOW, store=fake_store(), deps=make_deps()[0])
    st = fake_store()
    deps = make_deps()[0]
    deps.fade_cross = Rec()
    out = RUN.run_pass(NOW, store=st, deps=deps)
    (a, k), = deps.fade_cross.calls
    assert a[2] == NOW and a[3] == S and k["store"] is st and "volume" in k and isinstance(a[0], dict)
    assert out == base


def test_NEGATIVE_a_dry_pass_and_an_open_never_call_the_step():
    deps = make_deps()[0]
    deps.fade_cross = Rec()
    RUN.run_pass(NOW, store=RUN.dry_store(fake_store()), deps=deps, dry=True)
    assert deps.fade_cross.calls == []


def test_NEGATIVE_a_raising_step_never_reaches_the_errors():
    base = RUN.run_pass(NOW, store=fake_store(), deps=make_deps()[0])
    deps = make_deps()[0]
    deps.fade_cross = Rec(exc=RuntimeError("boom"))
    out = RUN.run_pass(NOW, store=fake_store(), deps=deps)
    assert len(deps.fade_cross.calls) == 1 and out == base and out["errors"] == []
