"""chart_maps/gajjala/potential.py — 🧠 potential · 📈 track · 🔔 gajjala_potential (BUILD_SPEC4 §3.2–§3.8, 2026-10-15).

Ajay 2026-10-15: "In Gajjalas setup I wanna find potential stocks this shows me what has happened I am trying to setup
for this tab to act like Gajjalas brain. So create a potential category in this section." / "In all the sub tab and add
a track and alert to show me new potential is added everyday." / "Give me an alert all continous tracker on these
specifically when I get alert I will jump on to ride the wave".

Real detector reads (tests/fixtures/gajjala/detector_frames.py — never hand-typed prices) where a read is needed; the
store is the in-memory FakeColl set (tests/conftest.py refuses a real MongoClient). NEGATIVES are mandatory: a partial
never pushes, nothing pushes twice, the mute / closed day / outside hours / stale tape hold, the A+ kind stays shadow,
the D9 join rule never rings, and no composed string carries a forecast word.
"""
from __future__ import annotations

import ast
import copy
import pathlib
import re
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import store as ST
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_store import FakeColl, fake_store

ET = ZoneInfo("America/New_York")
S = date(2026, 10, 13)                          # a Tuesday, a market day
LABOR_DAY = date(2026, 9, 7)
HALF_DAY = date(2026, 11, 27)                   # supply_demand.timeframes.HALF_DAYS
SRC = pathlib.Path(PT.__file__).read_text(encoding="utf-8")
B_WORD = re.compile("b" + "ounc", re.I)
OK_SEND = {"sent": 1, "failed": 0, "total_targets": 1}


def at(hh, mm, d=S, ss=0):
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=ET)


# ── real detector reads ──────────────────────────────────────────────────────────────────────────────────────────
def bf_armed():
    return D.bull_flag(FX.frame(FX.bf_bars(entry=None)))                     # forming, ready, 2-bar pullback


def kf_building():
    return D.kiss_fly(FX.kf_frame(kiss_above_pct=0.6, entry=False))          # forming, waiting for the kiss


def bf_no_pullback():
    return D.bull_flag(FX.frame(FX.bf_bars([], entry=None)))                 # forming, base None


def vcp_no_pullback():
    return D.intraday_vcp(FX.vcp_frame(FX.VCP_BARS[:6], entry=None))         # forming, base None


def four_bar_flag():
    """WIDENED 2026-10-18 (DECISIONS13 D1): the 4-bar flat-pull flag with no break — a listed partial "long flag" until
    2026-10-18 (was `real_partials()["long_flag"]`), a FORMING read (trigger armed) since 1–5 bars = A+."""
    return D.bull_flag(FX.frame(FX.bf_bars(FX.flat_pull(4), entry=None)))


def real_partials():
    return {"near_kiss": D.kiss_fly(FX.kf_near_kiss()),
            "vcp_b": D.intraday_vcp(FX.vcp_frame(FX.vcp_replace(r13=(10.1875, 10.25, 9.8, 10.125, 40_000)),
                                                 e21_at={13: 9.8}))}


def one_per_setup():
    """A real potential read of every setup."""
    return {"bull_flag": bf_armed(), "kiss_fly": kf_building(),
            "horizontal_fade": D.horizontal_fade(None, FX.hf_frame(FX.HF_BASE[:5], entry=None, tf="5m")),
            "intraday_vcp": D.intraday_vcp(FX.vcp_frame(entry=None)),
            "reversal_squeeze": D.reversal_squeeze(FX.rs_frame(entry=None), float_read=FX.float_read(5e6))}


# ── pass plumbing ────────────────────────────────────────────────────────────────────────────────────────────────
class Rec:
    def __init__(self, ret=None):
        self.calls, self.ret = [], ret

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        if isinstance(self.ret, Exception):
            raise self.ret
        return self.ret


def frame_at(now, px=10.9, *, age_min=1):
    """A bars.Frames stand-in: the 5-minute frame's latest closed bar closed `age_min` minutes before the pass."""
    stamp = (now.astimezone(ET) - timedelta(minutes=age_min)).strftime("%Y-%m-%d %H:%M")
    return SimpleNamespace(as_of_bar_t={"5m": stamp, "15m": stamp}, f5=SimpleNamespace(c=[px]))


def ctx_for(shares=5_000_000, rot=None, halts=None):
    c = {"float": FX.float_read(shares), "rotation": rot, "halts": halts}
    return c


def seed(st, d=S, sym="SEED", setup="kiss_fly"):
    """One tracker doc already on file for the session (a pass ran before) — the D9 join rule stays out of the way."""
    assert st.upsert_potential(ST.potential_key(d, sym, setup), {"date": d.isoformat(), "symbol": sym, "setup": setup},
                               {"at": at(4, 6, d)})


def go(st, now, reads, *, send=None, frames=None, px=10.9, age_min=1, dry=False, ctx=None, rows=None, session=None,
       tape="rth", live_rows=None):
    session = session or now.astimezone(ET).date()
    frames = frames if frames is not None else {s: frame_at(now, px, age_min=age_min) for s in reads}
    return PT.run_pass(reads, frames, now, session, store=st, ctx=ctx or {s: ctx_for() for s in reads},
                       rows=rows or {s: {"volume": 2_000_000, "price": 11.2} for s in reads},
                       send=send, owner="owner@example.com", dry=dry, tape=tape, live_rows=live_rows)


def doc_of(st, sym="AAA", setup="bull_flag", d=S):
    return st.get_potential(d, sym, setup)


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


@pytest.fixture
def no_ab_sender(monkeypatch):
    """The A+ sender must never be reached by the potential gate."""
    from chart_maps.gajjala import alerts as AL
    from push import hooks
    boom = Rec(AssertionError("the A+ sender was called"))
    monkeypatch.setattr(AL, "_default_send", boom)
    monkeypatch.setattr(hooks, "notify_gajjala_setup", boom)
    return boom


# ── K1: potential_kind ───────────────────────────────────────────────────────────────────────────────────────────
def test_potential_kind_armed_and_building_on_real_reads():
    assert PT.potential_kind(bf_armed()) == "armed"                         # bull flag at its pullback bar
    assert PT.potential_kind(kf_building()) == "building"                   # kiss & fly before the kiss
    assert {k: PT.potential_kind(r) for k, r in one_per_setup().items()} == {
        "bull_flag": "armed", "kiss_fly": "building", "horizontal_fade": "building", "intraday_vcp": "building",
        "reversal_squeeze": "armed"}


@pytest.mark.parametrize("state", ["aplus", "triggered", "stopped", "partial", "invalid", "none"])
def test_NEGATIVE_any_other_state_is_never_a_potential(state):
    r = dict(bf_armed(), state=state)
    assert PT.potential_kind(r) is None


def test_NEGATIVE_the_real_aplus_and_the_partials_are_never_a_potential():
    assert PT.potential_kind(D.bull_flag(FX.bf_aplus())) is None
    for name, r in real_partials().items():
        assert r["state"] == "partial", name
        assert PT.potential_kind(r) is None, name
    # the long_flag band is empty since 2026-10-18 — synthetic variant, the mechanism is what is tested
    assert PT.potential_kind(dict(bf_armed(), variant="long_flag")) is None     # a future forming variant: still None
    assert PT.potential_kind(dict(bf_armed(), variant="some_future_variant")) is None
    assert PT.potential_kind(dict(bf_armed(), grade="B")) is None


def test_a_4_bar_forming_flag_is_a_potential_since_2026_10_18():
    """WIDENED 2026-10-18 (DECISIONS13 D1, Ajay "make the change for Long flags"): the 4-bar flag waiting for its break
    is a forming read with no variant — a 🧠 potential, trigger armed (it was a partial long flag, never a potential)."""
    r = four_bar_flag()
    assert r["state"] == "forming" and r["variant"] is None and r["ready"] is True and r["base"]["bars"] == 4
    assert PT.potential_kind(r) == "armed"
    assert PT.potential_kind(D.bull_flag(FX.frame(FX.bf_bars(FX.flat_pull(6), entry=None)))) is None   # NEGATIVE: 6 = invalid


def test_NEGATIVE_a_forming_read_with_no_sideways_bar_is_not_a_potential():
    for r in (bf_no_pullback(), vcp_no_pullback()):
        assert r["state"] == "forming" and r["base"] is None
        assert PT.potential_kind(r) is None
    assert PT.potential_kind(dict(bf_armed(), base={"bars": 0})) is None
    assert PT.potential_kind(None) is None and PT.potential_kind("forming") is None


def test_NEGATIVE_a_truthy_ready_is_building_not_armed():
    assert PT.potential_kind(dict(bf_armed(), ready="yes")) == "building"
    assert PT.potential_kind(dict(bf_armed(), ready=1)) == "building"


def test_the_needs_base_knob_bites(monkeypatch):
    monkeypatch.setattr(GC, "POTENTIAL_NEEDS_BASE", False)
    assert PT.potential_kind(bf_no_pullback()) == "building"
    # WIDENED 2026-10-20 (BUILD_SPEC18 D4): the no-pullback 🌀 read now carries cycles 0 — under K4's contractions it
    # is never a potential; with the listing switch off the knob still bites on it exactly as before
    assert PT.potential_kind(vcp_no_pullback()) is None
    monkeypatch.setattr(GC, "VCP_LIST_FROM_K4", False)
    assert PT.potential_kind(vcp_no_pullback()) == "building"


def test_NEGATIVE_unknown_float_squeeze_is_none_never_a_potential():
    r = D.reversal_squeeze(FX.rs_frame(entry=None), float_read=FX.float_read(None))
    assert r["state"] == "none" and PT.potential_kind(r) is None


# ── GG's tells ───────────────────────────────────────────────────────────────────────────────────────────────────
def _values(**over):
    kw = dict(ctx=ctx_for(3_100_000, rot={"x": 4.1, "text": "🔄 float ×4.1"}, halts={"n": 2, "text": "⏸ halted ×2"}),
              scan_row={"volume": 12_000_000},
              ah_prev={"names": {"AAA": {"ah_move_pct": 12.34}}},
              prev_scan={"date": "2026-10-12", "symbol": "AAA", "max_change_pct": 87.6}, also=["kiss_fly"],
              again=True)
    kw.update(over)
    return PT.tell_values("aaa", "bull_flag", **kw)


def test_every_tell_badge_with_its_cite():
    t = {x["key"]: x for x in PT.tells(_values())}
    assert list(t) == list(PT.TELL_ORDER)
    assert t["float"]["text"] == "Float 3.1M" and "21:04" in t["float"]["cite"]
    assert t["rotation"]["text"] == "🔄 float ×4.1" and "1:15:24" in t["rotation"]["cite"]
    assert t["halts"]["text"] == "⏸ halted ×2 today" and t["halts"]["cite"].startswith("S9")
    assert t["ah_mover"]["text"] == "🌙 after-hours mover last session +12.3%" and "13:21" in t["ah_mover"]["cite"]
    assert t["prior_day"]["text"] == "📅 on his scanner 2026-10-12, up to +88%" and "2:02:47" in t["prior_day"]["cite"]
    assert t["also"]["text"] == "🧩 also forming: 💋 EMA Kiss & Fly" and "1:59:01" in t["also"]["cite"]
    assert t["again"]["text"] == PT.AGAIN_TEXT == "↻ also a potential last session" and "1:17:32" in t["again"]["cite"]


def test_NEGATIVE_an_unknown_float_has_no_badge_never_zero_and_sorts_after_a_known_one():
    v = _values(ctx=ctx_for(None, rot={"x": 9.9, "text": "🔄 float ×9.9"}))
    assert v["float_shares"] is None and v["float_text"] is None
    assert v["rotation_text"] is None                                       # rotation is None with an unknown float
    texts = " ".join(x["text"] for x in PT.tells(v))
    assert "float" not in {x["key"] for x in PT.tells(v)} and "rotation" not in {x["key"] for x in PT.tells(v)}
    assert not re.search(r"\b0\b|None|unknown", texts)
    big = _values(ctx=ctx_for(50_000_000))
    assert PT.order_key("armed", big, "bull_flag", "BBB") < PT.order_key("armed", v, "bull_flag", "AAA")


def test_NEGATIVE_a_suspect_float_under_ineligible_is_unknown(monkeypatch):
    fr = dict(FX.float_read(3_000_000), suspect="float_exceeds_shares")
    v = _values(ctx={"float": fr, "rotation": {"x": 2.0, "text": "🔄 float ×2.0"}})
    assert GC.FLOAT_SUSPECT_POLICY == "ineligible" and v["float_shares"] is None and v["rotation_text"] is None
    monkeypatch.setattr(GC, "FLOAT_SUSPECT_POLICY", "shares_out")
    assert _values(ctx={"float": fr})["float_shares"] == 3_000_000


def test_NEGATIVE_no_carry_no_prior_no_halt_no_also_means_no_badges():
    v = _values(ctx=ctx_for(None), ah_prev=None, prev_scan=None, also=[], again=None)
    assert PT.tells(v) == []
    assert _values(ah_prev={"names": {"ZZZ": {"ah_move_pct": 15.0}}})["ah_move_pct"] is None   # name absent
    assert _values(also=["bull_flag"])["also"] == []                        # its own setup is never "also"


# ── order ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_order_key_armed_first_then_float_up_unknown_last_volume_down_symbol_last():
    def v(fl, vol):
        return {"float_shares": fl, "volume": vol}
    keys = {
        "building_tiny": PT.order_key("building", v(100_000, 9e9), "bull_flag", "AAA"),
        "armed_huge": PT.order_key("armed", v(900_000_000, 1), "bull_flag", "ZZZ"),
        "armed_small": PT.order_key("armed", v(2_000_000, 1), "bull_flag", "YYY"),
        "armed_unknown": PT.order_key("armed", v(None, 9e9), "bull_flag", "AAA"),
        "armed_small_loud": PT.order_key("armed", v(2_000_000, 5e6), "bull_flag", "XXX"),
        "armed_small_noVol": PT.order_key("armed", v(2_000_000, None), "bull_flag", "AAA"),
    }
    got = sorted(keys, key=keys.get)
    assert got == ["armed_small_loud", "armed_small", "armed_small_noVol", "armed_huge", "armed_unknown",
                   "building_tiny"]
    assert PT.order_key("armed", v(1, 1), "bull_flag", "BBB") < PT.order_key("armed", v(1, 1), "kiss_fly", "AAA")
    assert PT.order_key("armed", v(1, 1), "bull_flag", "AAA") < PT.order_key("armed", v(1, 1), "bull_flag", "BBB")


# ── K2: the window ───────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("hm,want", [((4, 1), None), ((9, 29), None), ((9, 45), None), ((19, 56), None),
                                     ((9, 30), "muted"), ((9, 44), "muted"), ((3, 59), "outside_hours"),
                                     ((20, 1), "outside_hours")])
def test_window_reason(hm, want):
    assert PT.window_reason(at(*hm), S) == want


def test_window_reason_on_a_half_day():
    assert PT.window_reason(at(16, 56, HALF_DAY), HALF_DAY) is None
    assert PT.window_reason(at(17, 1, HALF_DAY), HALF_DAY) == "outside_hours"


def test_the_mute_follows_the_constant(monkeypatch):
    monkeypatch.setattr(GC, "NO_TRADE_AFTER_OPEN_MIN", 20)
    assert PT.window_reason(at(9, 46), S) == "muted" and PT.window_reason(at(9, 50), S) is None


def test_pass_times_and_the_crontab_minute():
    assert PT.pass_times(S) == ("04:01", "19:56")
    assert PT.pass_times(HALF_DAY) == ("04:01", "16:56")
    cron = (pathlib.Path(__file__).resolve().parents[1] / "crontab").read_text().splitlines()
    line = [ln for ln in cron if re.search(r"-m market_hours\.gate chart_maps\.gajjala\.run(\s|$)", ln)
            and not ln.lstrip().startswith("#")]
    assert len(line) == 1
    minute = line[0].split()[0]
    assert int(minute.split("-")[0]) == GC.PASS_MINUTE_OFFSET
    assert int(minute.split("/")[1]) * 60 == GC.PASS_CADENCE_SEC


def test_fresh_tape_is_the_a_plus_age_rule():
    from chart_maps.gajjala.alerts import MAX_ENTRY_AGE_SEC
    now = at(10, 6)
    assert PT.fresh_tape(frame_at(now, age_min=1), now)
    assert PT.fresh_tape(frame_at(now, age_min=MAX_ENTRY_AGE_SEC // 60), now)
    assert not PT.fresh_tape(frame_at(now, age_min=MAX_ENTRY_AGE_SEC // 60 + 1), now)
    assert not PT.fresh_tape(frame_at(now, age_min=-5), now)                 # a bar from the future
    assert not PT.fresh_tape(None, now) and not PT.fresh_tape(SimpleNamespace(as_of_bar_t={}), now)


# ── 📈 track ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_track_first_sighting_writes_first_fields_at_the_pass_clock():
    st = fake_store()
    now = at(10, 6)
    r = bf_armed()
    vals = _values()
    doc, new = PT.track(st, S, "aaa", "bull_flag", r, "armed", now, px=10.9, values=vals)
    assert new is True and doc["_id"] == "2026-10-13|AAA|bull_flag"
    d = doc_of(st)
    assert d["first_seen"] == now.astimezone(timezone.utc) and d["first_seen_et"] == "10:06"
    assert d["first_kind"] == "armed" and d["first_px"] == 10.9 and d["first_seen_mode"] == "normal"
    assert (d["first_trigger"], d["first_stop"], d["first_bar_t"]) == (r["trigger"], r["stop"], r["as_of_bar_t"])
    assert d["first_tells"] == vals and d["date"] == "2026-10-13" and d["frame"] == "5m"
    assert d["last"]["state"] == "forming" and d["last"]["kind"] == "armed" and d["last"]["px"] == 10.9
    assert d["state_path"] == [{"at": now.astimezone(timezone.utc).isoformat(), "at_et": "10:06", "state": "forming",
                                "kind": "armed", "bar_t": r["as_of_bar_t"]}]
    assert d["url"] == "/chart-maps?tab=gajjala&sub=bull_flag&focus=AAA" and d["line"].startswith("AAA · 🚩 Bull Flag")
    assert d["move_pct"] == 0.0 and "push" not in d and "held" not in d and "graveyard_on" not in d


def test_a_replayed_pass_leaves_the_doc_byte_identical():
    st = fake_store()
    now = at(10, 6)
    PT.track(st, S, "AAA", "bull_flag", bf_armed(), "armed", now, px=10.9, values={})
    before = copy.deepcopy(doc_of(st))
    doc, new = PT.track(st, S, "AAA", "bull_flag", bf_armed(), "armed", now, px=10.9, values={})
    assert new is False and doc_of(st) == before


def test_track_follows_every_state_change_and_only_on_change():
    st = fake_store()
    r = kf_building()
    PT.track(st, S, "AAA", "kiss_fly", r, "building", at(10, 6), px=10.4, values={})
    PT.track(st, S, "AAA", "kiss_fly", r, "building", at(10, 11), px=10.45, values={})      # no change
    PT.track(st, S, "AAA", "kiss_fly", dict(r, ready=True), "armed", at(10, 16), px=10.46, values={})
    PT.track(st, S, "AAA", "kiss_fly", dict(r, state="aplus"), None, at(10, 21), px=10.6, values={})
    PT.track(st, S, "AAA", "kiss_fly", dict(r, state="stopped"), None, at(10, 26), px=10.3, values={})
    d = doc_of(st, setup="kiss_fly")
    assert [(e["at_et"], e["state"], e["kind"]) for e in d["state_path"]] == [
        ("10:06", "forming", "building"), ("10:16", "forming", "armed"), ("10:21", "aplus", None),
        ("10:26", "stopped", None)]
    assert d["first_kind"] == "building" and d["first_px"] == 10.4 and d["last"]["px"] == 10.3
    assert d["move_pct"] == round((10.3 / 10.4 - 1) * 100, 2)
    assert d["vs_trigger_pct"] == round((10.3 / r["trigger"] - 1) * 100, 2)
    assert "armed" in d["line"]                                             # the latest POTENTIAL's line is kept


def test_NEGATIVE_a_read_that_is_never_a_potential_creates_no_doc():
    st = fake_store()
    for r in (dict(bf_armed(), state="partial"), D.bull_flag(FX.bf_aplus()), bf_no_pullback()):
        assert PT.track(st, S, "AAA", "bull_flag", r, PT.potential_kind(r), at(10, 6), px=1.0, values={}) == \
            (None, False)
    assert st.coll(ST.POTENTIALS).docs == {}
    st2 = fake_store()
    go(st2, at(10, 6), {"AAA": {"bull_flag": dict(bf_armed(), state="partial")}}, send=Rec(OK_SEND))
    assert st2.coll(ST.POTENTIALS).docs == {}


def test_graveyard_marks_every_unmarked_doc_of_the_symbol_once():
    st = fake_store()
    PT.track(st, date(2026, 10, 8), "OLD", "bull_flag", bf_armed(), "armed", at(10, 6, date(2026, 10, 8)), px=1.0,
             values={})
    PT.track(st, date(2026, 10, 9), "OLD", "kiss_fly", kf_building(), "building", at(10, 6, date(2026, 10, 9)),
             px=1.0, values={})
    assert PT.mark_graveyard(st, S, ["OLD"], at(10, 6)) == 2
    assert PT.mark_graveyard(st, S, ["OLD"], at(10, 11)) == 0
    for d in st.potential_docs_for_symbol("OLD"):
        assert d["graveyard_on"] == "2026-10-13" and d["state_path"][-1]["state"] == "graveyard"
        assert [e["state"] for e in d["state_path"]].count("graveyard") == 1
    assert PT.state_word("graveyard", None, on="2026-10-13") == "🪦 graveyard 2026-10-13"


def test_the_pass_marks_the_graveyard_from_the_tabs_own_list():
    st = fake_store()
    gone = date(2026, 10, 8)                                                # dropped off the 3-session window today
    st.record_qualifiers(gone, at(10, 1, gone), [{"symbol": "OLD", "price": 2.0, "change_pct": 40.0}], "rth")
    PT.track(st, gone, "OLD", "bull_flag", bf_armed(), "armed", at(10, 6, gone), px=1.0, values={})
    seed(st)
    out = go(st, at(10, 6), {}, send=Rec(OK_SEND))
    assert out["graveyard"] == 1 and doc_of(st, "OLD", d=gone)["graveyard_on"] == "2026-10-13"


# ── 🔔 the push gate ─────────────────────────────────────────────────────────────────────────────────────────────
def test_a_first_sighting_in_the_window_rings_exactly_once_with_the_copy(no_ab_sender):
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    r = bf_armed()
    out = go(st, at(10, 6), {"AAA": {"bull_flag": r}}, send=send,
             ctx={"AAA": ctx_for(3_100_000, rot={"x": 4.1, "text": "🔄 float ×4.1"})})
    assert len(send.calls) == 1 and out["pushed"] == 1 and out["new"] == 1 and out["armed"] == 1
    (owner, p), _ = send.calls[0]
    assert owner == "owner@example.com"
    assert set(p) == {"title", "body", "tag", "url", "kind", "ticker", "items"}
    assert p["title"] == "🧠 AAA · 🚩 Bull Flag — trigger armed · UNMEASURED"
    assert p["url"] == "/chart-maps?tab=gajjala&sub=bull_flag&focus=AAA" and p["tag"] == "gg-pot-bull_flag-AAA"
    assert p["kind"] == "gajjala_potential" == GC.POTENTIAL_PUSH_KIND and p["ticker"] == "AAA"
    assert p["items"] == [{"symbol": "AAA", "text": PT.line("AAA", "bull_flag", r, "armed")}]
    bits = p["body"].split(" · ")
    assert bits[0] == "trigger 10.97" and bits[1].startswith("stop 10.81 (−1.4%)")
    assert bits[2] == PT.TAIL                                               # D8: the tail right after trigger / stop
    assert "first seen 10:06 ET" in bits and bits[-2:] == ["Float 3.1M", "🔄 float ×4.1"]   # tells last
    assert len(p["title"] + " " + " · ".join(bits[:3])) <= 180               # the lock screen shows the tail
    d = doc_of(st)
    assert d["push"]["state"] == "pushed" and d["push"]["kind_at_push"] == "armed"
    assert d["push"]["result"] == {"sent": 1, "failed": 0, "total_targets": 1, "skipped": None}
    assert no_ab_sender.calls == []


def test_a_building_push_says_not_armed_yet_and_carries_the_stop():
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    r = kf_building()
    go(st, at(10, 6), {"AAA": {"kiss_fly": r}}, send=send, tape="afterhours")
    (_o, p), _ = send.calls[0]
    assert p["title"] == "🧠 AAA · 💋 EMA Kiss & Fly — building · UNMEASURED"
    bits = p["body"].split(" · ")
    assert bits[:4] == [r["reason"], "trigger 10.48 (not armed yet)", "stop 10.42 (−0.6%)", PT.TAIL]
    assert "🌙 after-hours" in bits


def test_NEGATIVE_a_second_pass_never_rings_twice():
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    reads = {"AAA": {"bull_flag": bf_armed()}}
    go(st, at(10, 6), reads, send=send)
    out = go(st, at(10, 11), reads, send=send)
    out3 = go(st, at(10, 16), {"AAA": {"bull_flag": dict(bf_armed(), ready=False)}}, send=send)   # armed → building
    assert len(send.calls) == 1 and out["pushed"] == 0 and out3["pushed"] == 0 and out["new"] == 0


def test_NEGATIVE_a_partial_never_pushes(no_ab_sender):
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    reads = {f"P{i}": {r["setup"]: r} for i, r in enumerate(real_partials().values())}
    out = go(st, at(10, 6), reads, send=send)
    assert send.calls == [] and out["potential"] == 0 and out["pushed"] == 0


def test_the_mute_holds_then_the_0946_pass_rings_with_the_first_sighting_time():
    st = fake_store()
    send = Rec(OK_SEND)
    reads = {"AAA": {"bull_flag": bf_armed()}}
    out = go(st, at(9, 36), reads, send=send)
    assert send.calls == [] and out["muted"] == 1
    assert [h["reason"] for h in doc_of(st)["held"]] == ["muted"]
    out = go(st, at(9, 46), reads, send=send)
    assert len(send.calls) == 1 and out["pushed"] == 1
    assert "first seen 09:36 ET" in send.calls[0][0][1]["body"]


def test_THREE_PASS_NEGATIVE_muted_then_one_send_then_no_send():
    st = fake_store()
    send = Rec(OK_SEND)
    reads = {"AAA": {"bull_flag": bf_armed()}}
    for hm in ((9, 36), (9, 46), (9, 51)):
        go(st, at(*hm), reads, send=send)
    assert len(send.calls) == 1 and "first seen 09:36 ET" in send.calls[0][0][1]["body"]


def test_NEGATIVE_with_defer_off_a_muted_sighting_never_rings(monkeypatch):
    monkeypatch.setattr(GC, "POTENTIAL_DEFER_REFUSED", False)
    st = fake_store()
    send = Rec(OK_SEND)
    reads = {"AAA": {"bull_flag": bf_armed()}}
    go(st, at(9, 36), reads, send=send)
    out = go(st, at(9, 46), reads, send=send)
    assert send.calls == [] and out["pushed"] == 0


def test_NEGATIVE_D3_muted_then_partial_then_forming_again_never_rings():
    st = fake_store()
    send = Rec(OK_SEND)
    go(st, at(9, 36), {"AAA": {"bull_flag": bf_armed()}}, send=send)
    go(st, at(9, 41), {"AAA": {"bull_flag": dict(bf_armed(), state="partial")}}, send=send)
    out = go(st, at(9, 46), {"AAA": {"bull_flag": bf_armed()}}, send=send)
    assert send.calls == [] and out["pushed"] == 0
    assert [e["state"] for e in doc_of(st)["state_path"]] == ["forming", "partial", "forming"]


def test_NEGATIVE_a_closed_day_never_rings():
    st = fake_store()
    seed(st, d=LABOR_DAY)
    send = Rec(OK_SEND)
    out = go(st, at(10, 6, LABOR_DAY), {"AAA": {"bull_flag": bf_armed()}}, send=send)
    assert send.calls == [] and out["closed_day"] == 1
    assert [h["reason"] for h in doc_of(st, d=LABOR_DAY)["held"]] == ["closed_day"]


def test_NEGATIVE_2001_never_rings():
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    out = go(st, at(20, 1), {"AAA": {"bull_flag": bf_armed()}}, send=send)
    assert send.calls == [] and out["outside_hours"] == 1


def test_stale_tape_waits_then_a_fresh_print_rings():
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    reads = {"AAA": {"bull_flag": bf_armed()}}
    out = go(st, at(10, 6), reads, send=send, age_min=11)
    assert send.calls == [] and out["stale_tape"] == 1
    out = go(st, at(10, 11), reads, send=send, age_min=1)
    assert len(send.calls) == 1 and out["pushed"] == 1


def test_the_fresh_tape_knob_bites(monkeypatch):
    monkeypatch.setattr(GC, "POTENTIAL_FRESH_TAPE", False)
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    go(st, at(10, 6), {"AAA": {"bull_flag": bf_armed()}}, send=send, age_min=60)
    assert len(send.calls) == 1


def test_NEGATIVE_dry_sends_nothing_and_writes_nothing():
    st = fake_store()
    send = Rec(OK_SEND)
    seed(st)
    coll = st.coll(ST.POTENTIALS)
    w0 = coll.writes
    out = go(st, at(10, 6), {"AAA": {"bull_flag": bf_armed()}}, send=send, dry=True)
    assert send.calls == [] and out["dry"] == 1 and coll.writes == w0 and doc_of(st) is None


def test_NEGATIVE_a_send_that_raises_is_failed_and_never_retried():
    st = fake_store()
    seed(st)
    reads = {"AAA": {"bull_flag": bf_armed()}}
    boom = Rec(RuntimeError("push down"))
    out = go(st, at(10, 6), reads, send=boom)
    assert out["failed"] == 1 and doc_of(st)["push"]["state"] == "failed"
    ok = Rec(OK_SEND)
    out = go(st, at(10, 11), reads, send=ok)
    assert ok.calls == [] and out["failed"] == 0


def test_no_target_when_no_device_takes_it():
    st = fake_store()
    seed(st)
    out = go(st, at(10, 6), {"AAA": {"bull_flag": bf_armed()}},
             send=Rec({"sent": 0, "failed": 0, "total_targets": 0}))
    assert out["no_target"] == 1 and doc_of(st)["push"]["state"] == "no_target"


def test_NEGATIVE_the_potential_pass_never_touches_the_a_plus_kind_or_its_ledger(no_ab_sender):
    # WIDENED 2026-10-16: Ajay flipped the A+ kind live ("you alert me when that happens") — the mode clause is dropped (the A+ kind is live);
    # the potential pass still never writes the A+ ledger nor calls the A+ sender (the AST guard below unchanged)
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    reads = {"AAA": {k: r for k, r in one_per_setup().items()}, "BBB": {"bull_flag": D.bull_flag(FX.bf_aplus())}}
    out = go(st, at(10, 6), reads, send=send)
    assert out["pushed"] == len(send.calls) == 5                            # one push per (name, setup) — K3
    assert st.alerts_coll().docs == {} and no_ab_sender.calls == []
    tree = ast.parse(SRC)
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef)) and n.body and isinstance(n.body[0], ast.Expr)}
    idents = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {
        n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    code_strings = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                    and id(n) not in docs}
    assert not ({"GAJJALA_PUSH_MODE", "alerts_coll", "notify_gajjala_setup", "push_mode"} & idents)
    assert not [x for x in code_strings if "gajjala_alerts" in x or "gajjala_setup" in x]
    assert {p["kind"] for (_o, p), _k in send.calls} == {"gajjala_potential"}


def test_also_forming_names_the_other_setups_of_the_same_name():
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    go(st, at(10, 6), {"AAA": {"bull_flag": bf_armed(), "kiss_fly": kf_building()}}, send=send)
    d = doc_of(st)
    assert d["first_tells"]["also"] == ["kiss_fly"] and doc_of(st, setup="kiss_fly")["first_tells"]["also"] == \
        ["bull_flag"]


def test_the_pass_pushes_in_order_key_order():
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    reads = {"BIG": {"kiss_fly": kf_building()}, "SML": {"bull_flag": bf_armed()}, "MID": {"bull_flag": bf_armed()}}
    ctx = {"BIG": ctx_for(1_000_000), "SML": ctx_for(9_000_000), "MID": ctx_for(None)}
    go(st, at(10, 6), reads, send=send, ctx=ctx)
    assert [p["ticker"] for (_o, p), _k in send.calls] == ["SML", "MID", "BIG"]   # armed first; unknown float last


# ── Revision 1 ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_OVERLAP_NEGATIVE_a_stale_read_never_wipes_the_claim_and_never_rings_twice(monkeypatch):
    st = fake_store()
    send = Rec(OK_SEND)
    reads = {"AAA": {"bull_flag": bf_armed()}}
    go(st, at(9, 36), reads, send=send)                                     # held muted, unclaimed
    stale = copy.deepcopy(doc_of(st))                                       # pass B read the doc here …
    go(st, at(9, 46), reads, send=send)                                     # … pass A claims and sends
    assert len(send.calls) == 1
    real = st.get_potential
    calls = []

    def b_get(session, sym, setup):
        calls.append(1)
        return copy.deepcopy(stale) if len(calls) == 1 else real(session, sym, setup)
    monkeypatch.setattr(st, "get_potential", b_get)
    out = go(st, at(9, 46, ss=20), reads, send=send)                        # pass B writes + gates
    assert out["claimed_before"] == 1 and out["failed"] == 0 and len(send.calls) == 1
    assert doc_of(st)["push"]["state"] == "pushed"


class SpyColl(FakeColl):
    def __init__(self, *a, raise_on_claim=False, **k):
        super().__init__(*a, **k)
        self.calls, self.raise_on_claim = [], raise_on_claim

    def replace_one(self, q, doc, upsert=False):
        raise AssertionError("a whole-doc replace on gajjala_potentials")

    def update_one(self, q, upd, upsert=False):
        self.calls.append((copy.deepcopy(q), copy.deepcopy(upd), upsert))
        if self.raise_on_claim and "push" in (upd.get("$set") or {}):
            raise RuntimeError("mongo hiccup on the claim")
        return super().update_one(q, upd, upsert=upsert)


def test_WRITE_SHAPE_disjoint_keys_and_track_never_names_the_guarded_fields():
    spy = SpyColl()
    st = fake_store(**{ST.POTENTIALS: spy})
    seed(st)
    reads = {"AAA": {"bull_flag": bf_armed()}}
    go(st, at(10, 6), reads, send=Rec(OK_SEND))
    claimed = copy.deepcopy(doc_of(st)["push"])
    go(st, at(10, 11), {"AAA": {"bull_flag": dict(bf_armed(), state="aplus")}}, send=Rec(OK_SEND))
    upserts = [(q, u) for q, u, ups in spy.calls if ups]
    assert upserts
    for _q, u in upserts:
        ins, sets = set(u.get("$setOnInsert") or {}), set(u.get("$set") or {})
        assert not (ins & sets), ins & sets
        assert not ({"push", "held", "graveyard_on"} & (ins | sets))
    assert doc_of(st)["push"] == claimed                                    # byte-identical through a later track()
    before = copy.deepcopy(doc_of(st))
    assert st.hold_potential(ST.potential_key(S, "AAA", "bull_flag"), [{"reason": "muted"}]) is False
    assert doc_of(st) == before


def test_WRITE_MISS_counts_failed_not_claimed_before_then_the_next_pass_rings(monkeypatch):
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    reads = {"AAA": {"bull_flag": bf_armed()}}
    real = st.upsert_potential
    lost = {"on": True}
    monkeypatch.setattr(st, "upsert_potential", lambda *a, **k: False if lost["on"] else real(*a, **k))
    out = go(st, at(10, 6), reads, send=send)
    assert out["failed"] == 1 and out["claimed_before"] == 0 and send.calls == [] and doc_of(st) is None
    lost["on"] = False
    out = go(st, at(10, 11), reads, send=send)
    assert out["new"] == 1 and len(send.calls) == 1


@pytest.mark.parametrize("defer", [True, False])
def test_CLAIM_ERROR_holds_claim_error_and_the_next_healthy_pass_rings(monkeypatch, defer):
    monkeypatch.setattr(GC, "POTENTIAL_DEFER_REFUSED", defer)                # a store fault retries whatever P1 says
    spy = SpyColl(raise_on_claim=True)
    st = fake_store(**{ST.POTENTIALS: spy})
    seed(st)
    send = Rec(OK_SEND)
    reads = {"AAA": {"bull_flag": bf_armed()}}
    out = go(st, at(10, 6), reads, send=send)
    assert out["failed"] == 1 and send.calls == []
    assert [h["reason"] for h in doc_of(st)["held"]] == ["claim_error"]
    spy.raise_on_claim = False
    out = go(st, at(10, 11), reads, send=send)
    assert len(send.calls) == 1 and out["pushed"] == 1


def test_TIMESTAMPS_every_stamp_is_the_pass_clock():
    st = fake_store()
    seed(st)
    now = at(10, 6, ss=30)
    go(st, now, {"AAA": {"bull_flag": bf_armed()}}, send=Rec(OK_SEND))
    d = doc_of(st)
    u = now.astimezone(timezone.utc)
    assert d["first_seen"] == u and d["last"]["at"] == u and d["updated_at"] == u and d["at"] == u
    assert [e["at"] for e in d["state_path"]] == [u.isoformat()] and d["push"]["at"] == u.isoformat()
    assert d["first_seen_et"] == d["last"]["at_et"] == d["state_path"][0]["at_et"] == d["push"]["at_et"] == "10:06"


# ── AMENDMENTS4 D2 (price) and D9 (the join rule) ────────────────────────────────────────────────────────────────
def test_D2_last_px_follows_the_bars_and_move_pct_moves():
    st = fake_store()
    seed(st)
    reads = {"AAA": {"bull_flag": bf_armed()}}
    go(st, at(10, 6), reads, send=Rec(OK_SEND), px=10.0)
    go(st, at(10, 11), reads, send=Rec(OK_SEND), px=10.5, rows={"AAA": {"price": 99.0, "volume": 1}})
    d = doc_of(st)
    assert d["first_px"] == 10.0 and d["last"]["px"] == 10.5 and d["move_pct"] == 5.0


def test_D2_the_row_price_is_used_only_as_this_passs_fallback():
    st = fake_store()
    seed(st)
    now = at(10, 6)
    nof5 = {"AAA": SimpleNamespace(as_of_bar_t=frame_at(now).as_of_bar_t, f5=SimpleNamespace(c=[]))}
    go(st, now, {"AAA": {"bull_flag": bf_armed()}}, send=Rec(OK_SEND), frames=nof5,
       rows={"AAA": {"price": 99.0}}, live_rows={"AAA": {"price": 11.2}})
    assert doc_of(st)["first_px"] == 11.2
    st2 = fake_store()
    seed(st2)
    go(st2, now, {"AAA": {"bull_flag": bf_armed()}}, send=Rec(OK_SEND), frames=nof5, rows={"AAA": {"price": 99.0}})
    assert doc_of(st2)["first_px"] is None                                  # NEGATIVE: never the stored row


def test_D9_zero_docs_at_0401_is_a_normal_day_and_rings():
    st = fake_store()
    send = Rec(OK_SEND)
    out = go(st, at(4, 1), {"AAA": {"bull_flag": bf_armed()}}, send=send, tape="premarket")
    assert len(send.calls) == 1 and out["joined"] == 0 and doc_of(st)["first_seen_mode"] == "normal"
    assert "☀️ pre-market" in send.calls[0][0][1]["body"]


def test_D9_NEGATIVE_zero_docs_at_1006_joins_and_never_rings():
    st = fake_store()
    send = Rec(OK_SEND)
    reads = {"AAA": {"bull_flag": bf_armed()}, "BBB": {"kiss_fly": kf_building()}}
    out = go(st, at(10, 6), reads, send=send)
    assert send.calls == [] and out["joined"] == 2 and out["new"] == 2 and out["pushed"] == 0
    for sym, setup in (("AAA", "bull_flag"), ("BBB", "kiss_fly")):
        d = doc_of(st, sym, setup)
        assert d["first_seen_mode"] == "joined" and [h["reason"] for h in d["held"]] == ["joined_midsession"]
    out = go(st, at(10, 11), reads, send=send)                              # NEVER rings later either
    assert send.calls == [] and out["pushed"] == 0
    assert PT.HELD_WORDS["joined_midsession"] == "joined mid-session: tracking, not ringing"


def test_D9_one_existing_doc_at_1006_lets_a_new_sighting_ring():
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    out = go(st, at(10, 6), {"AAA": {"bull_flag": bf_armed()}}, send=send)
    assert len(send.calls) == 1 and out["joined"] == 0 and doc_of(st)["first_seen_mode"] == "normal"


def test_D9_NEGATIVE_a_quiet_morning_is_not_a_join_its_first_potential_after_0945_rings():
    """No potential before 09:45, but the gate ran every pass since 04:01 (its pass docs carry a `potential` block):
    the first sighting at 10:06 is a normal first sighting and rings (K3) — the join rule is for a mid-session deploy."""
    st = fake_store()
    st.record_pass(S, at(10, 1), {"status": "ok", "potential": {k: 0 for k in PT.COUNT_KEYS}})
    send = Rec(OK_SEND)
    out = go(st, at(10, 6), {"AAA": {"bull_flag": bf_armed()}}, send=send)
    assert len(send.calls) == 1 and out["joined"] == 0 and doc_of(st)["first_seen_mode"] == "normal"


def test_D9_a_pass_doc_from_before_this_build_still_joins():
    st = fake_store()
    st.record_pass(S, at(10, 1), {"status": "ok", "alerts": {}})            # an old pass doc: no `potential` block
    st.record_pass(S, at(10, 11), {"status": "ok", "potential": {}})        # a LATER pass (a replayed clock)
    send = Rec(OK_SEND)
    out = go(st, at(10, 6), {"AAA": {"bull_flag": bf_armed()}}, send=send)
    assert send.calls == [] and out["joined"] == 1


def test_D9_a_later_first_sighting_after_a_join_rings_normally():
    st = fake_store()
    send = Rec(OK_SEND)
    go(st, at(10, 6), {"AAA": {"bull_flag": bf_armed()}}, send=send)        # the join pass
    out = go(st, at(10, 11), {"AAA": {"bull_flag": bf_armed()}, "NEW": {"kiss_fly": kf_building()}}, send=send)
    assert [p["ticker"] for (_o, p), _k in send.calls] == ["NEW"] and out["pushed"] == 1


# ── fix round 1 (2026-10-15): the join rule reads the IMMEDIATELY previous pass; a joined doc never rings; D3 needs
#    a potential at every step; a read fault never re-creates a doc ──────────────────────────────────────────────
SIX = ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF")


def _gate_pass(st, now):
    """A pass doc as run._finish writes it for a pass whose 🧠 gate ran and found nothing."""
    st.record_pass(now.astimezone(ET).date(), now, {"status": "ok", "potential": {k: 0 for k in PT.COUNT_KEYS}})


def test_D9_NEGATIVE_early_empty_passes_then_a_3_hour_gap_then_1101_joins_and_never_rings():
    """The host-sleep / cron-restart burst D9 was written to stop: the gate ran at 04:01, 04:06, 07:56 (nothing
    forming), the chain broke, the 11:01 pass finds six armed flags — tracked as joined, zero sends."""
    st = fake_store()
    for hm in ((4, 1), (4, 6), (7, 56)):
        _gate_pass(st, at(*hm))
    send = Rec(OK_SEND)
    reads = {s: {"bull_flag": bf_armed()} for s in SIX}
    out = go(st, at(11, 1), reads, send=send)
    assert send.calls == [] and out["joined"] == 6 and out["pushed"] == 0 and out["new"] == 6
    assert all(doc_of(st, s)["first_seen_mode"] == "joined" for s in SIX)
    out = go(st, at(11, 6), reads, send=send)                               # and never later either
    assert send.calls == [] and out["pushed"] == 0


def test_D9_an_unbroken_chain_with_nothing_forming_lets_the_1101_sightings_ring():
    st = fake_store()
    for hm in ((4, 1), (4, 6), (7, 56), (10, 56)):
        _gate_pass(st, at(*hm))
    send = Rec(OK_SEND)
    out = go(st, at(11, 1), {s: {"bull_flag": bf_armed()} for s in SIX}, send=send)
    assert len(send.calls) == 6 and out["joined"] == 0 and out["pushed"] == 6


def test_D9_the_previous_pass_window_is_one_cadence_plus_the_lease():
    span = GC.PASS_CADENCE_SEC + GC.LEASE_SEC
    for gap, joins in ((span, False), (span + 1, True)):
        st = fake_store()
        _gate_pass(st, at(11, 1) - timedelta(seconds=gap))
        out = go(st, at(11, 1), {"AAA": {"bull_flag": bf_armed()}}, send=Rec(OK_SEND))
        assert (out["joined"] == 1) is joins and (out["pushed"] == 0) is joins


def test_NEGATIVE_D9_an_unreadable_previous_pass_fails_closed():
    st = fake_store(**{ST.PASSES: FakeColl(fail=True)})
    send = Rec(OK_SEND)
    out = go(st, at(11, 1), {"AAA": {"bull_flag": bf_armed()}}, send=send)
    assert send.calls == [] and out["joined"] == 1


def test_NEGATIVE_D9_a_joined_doc_whose_hold_write_failed_still_never_rings(monkeypatch):
    st = fake_store()
    send = Rec(OK_SEND)
    reads = {"AAA": {"bull_flag": bf_armed()}}
    real, lost = st.hold_potential, {"on": True}
    monkeypatch.setattr(st, "hold_potential", lambda *a, **k: False if lost["on"] else real(*a, **k))
    out = go(st, at(10, 6), reads, send=send)                               # the join pass; its hold is lost
    assert out["joined"] == 1 and send.calls == []
    d = doc_of(st)
    assert d["first_seen_mode"] == "joined" and "held" not in d
    lost["on"] = False
    out = go(st, at(10, 11), reads, send=send)                              # a healthy store: still no ring
    assert send.calls == [] and out["pushed"] == 0
    assert not PT.eligible({"first_seen_mode": "joined"}, False, "armed")
    assert PT.eligible({"first_seen_mode": "joined"}, True, "armed")       # the join pass itself records the hold


def test_NEGATIVE_D3_muted_then_a_baseless_forming_read_then_armed_never_rings():
    st = fake_store()
    send = Rec(OK_SEND)
    go(st, at(9, 36), {"AAA": {"bull_flag": bf_armed()}}, send=send)        # held muted
    nb = bf_no_pullback()
    assert nb["state"] == "forming" and PT.potential_kind(nb) is None
    go(st, at(9, 41), {"AAA": {"bull_flag": nb}}, send=send)                # a new leg, not the same structure
    out = go(st, at(9, 46), {"AAA": {"bull_flag": bf_armed()}}, send=send)
    assert send.calls == [] and out["pushed"] == 0
    assert [(e["state"], e["kind"]) for e in doc_of(st)["state_path"]] == [
        ("forming", "armed"), ("forming", None), ("forming", "armed")]


def test_NEGATIVE_a_read_fault_on_a_doc_on_file_never_rewrites_its_timeline(monkeypatch):
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    reads = {"AAA": {"bull_flag": bf_armed()}}
    go(st, at(10, 6), reads, send=send, px=10.0)
    go(st, at(10, 11), {"AAA": {"bull_flag": dict(bf_armed(), state="partial")}}, send=send, px=10.4)
    before = copy.deepcopy(doc_of(st))
    assert len(before["state_path"]) == 2 and before["move_pct"] == 4.0
    real, fault = st.get_potential, {"on": True}
    monkeypatch.setattr(st, "get_potential", lambda *a: None if fault["on"] else real(*a))
    out = go(st, at(10, 16), reads, send=send, px=12.0)
    assert out["failed"] == 1 and out["new"] == 0 and len(send.calls) == 1
    fault["on"] = False
    assert doc_of(st) == before                                             # path, move and first_* untouched


def test_NEGATIVE_a_read_fault_on_an_unclaimed_doc_skips_the_gate_then_the_next_pass_rings(monkeypatch):
    st = fake_store()
    send = Rec(OK_SEND)
    reads = {"AAA": {"bull_flag": bf_armed()}}
    go(st, at(9, 36), reads, send=send)                                     # held muted, unclaimed
    real, fault = st.get_potential, {"on": True}
    monkeypatch.setattr(st, "get_potential", lambda *a: None if fault["on"] else real(*a))
    out = go(st, at(9, 46), reads, send=send)
    assert send.calls == [] and out["failed"] == 1 and out["new"] == 0
    fault["on"] = False
    assert len(doc_of(st)["state_path"]) == 1 and doc_of(st)["last"]["at_et"] == "09:36"
    out = go(st, at(9, 51), reads, send=send)
    assert len(send.calls) == 1 and out["pushed"] == 1


# ── eligible ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_eligible_table():
    path = [{"state": "forming", "kind": "armed"}]
    assert PT.eligible({}, True, "armed")
    assert PT.eligible({"state_path": path}, False, "armed")                 # unclaimed, never held — it never rang
    assert PT.eligible({"held": [{"reason": "claim_error"}], "state_path": path + [{"state": "partial"}]}, False,
                       "armed")
    assert PT.eligible({"held": [{"reason": "muted"}], "state_path": path}, False, "armed")
    assert not PT.eligible({"held": [{"reason": "muted"}], "state_path": path + [{"state": "aplus"}]}, False, "armed")
    assert not PT.eligible({"held": [{"reason": "muted"}], "state_path": path + [{"state": "forming", "kind": None}]},
                           False, "armed")                                 # D3: a base-less forming read breaks it
    assert PT.eligible({"held": [{"reason": "muted"}], "state_path": path + [{"state": "forming",
                                                                              "kind": "building"}]}, False, "armed")
    assert not PT.eligible({"held": [{"reason": "joined_midsession"}, {"reason": "claim_error"}], "state_path": path},
                           False, "armed")
    assert not PT.eligible({"push": {"state": "failed"}}, True, "armed")
    assert not PT.eligible({}, True, None)


# ── words ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_state_words():
    want = {("forming", "armed"): "trigger armed", ("forming", "building"): "building",
            ("aplus", None): "A+ — broke the trigger", ("triggered", None): "A+ (triggered)",
            ("stopped", None): "stopped", ("partial", None): "partial — a rule failed",
            ("invalid", None): "invalid — the structure died", ("none", None): "no setup"}
    for (s, k), w in want.items():
        assert PT.state_word(s, k) == w
    assert PT.state_word("graveyard", None) == "🪦 graveyard"


def test_row_text_and_line():
    r = kf_building()
    assert PT.row_text("aaa", "kiss_fly", r, "building", "09:36") == (
        f"AAA · building — {r['reason']} · trigger 10.48 (not armed yet) · stop 10.42 (−0.6%) · first seen 09:36 ET")
    a = bf_armed()
    assert PT.row_text("AAA", "bull_flag", a, "armed", None) == "AAA · trigger armed · trigger 10.97 · stop 10.81 (−1.4%)"
    assert PT.line("AAA", "bull_flag", a, "armed") == "AAA · 🚩 Bull Flag · trigger armed · trigger 10.97 · stop 10.81"
    assert PT.row_text("AAA", "bull_flag", {"reason": "x"}, "armed", None) == "AAA · trigger armed"


def test_push_note_prints_the_clock_and_the_pass_schedule():
    t = PT.push_note(S)
    assert "04:00–20:00 ET on the 5-minute pass (passes from 04:01 to 19:56 ET), never 09:30–09:45 (his first 15 " \
           "minutes)" in t
    assert t.endswith(PT.TAIL + ".") and "first possible" not in t and "Cheetah default, not his" in t
    h = PT.push_note(HALF_DAY)
    assert "04:00–17:00 ET" in h and "to 16:56 ET" in h


def test_rules_lines_three_tagged_clauses_that_follow_their_constants(monkeypatch):
    a, b = PT.rules_lines()
    assert a.count("Cheetah default, not his") == 3 and "No rule of its own" not in a
    assert "SHADOW" not in a + b and "gajjala_potential" in b and "🧠" in a
    assert not re.search(r"04:01|19:56|17:00", a + b)
    base = PT.rules_lines()[0]
    flips = {"POTENTIAL_NEEDS_BASE": ("at least one sideways bar", "no sideways bar is needed"),
             "POTENTIAL_FRESH_TAPE": ("waits for a print", "does not wait for a fresh print"),
             "POTENTIAL_DEFER_REFUSED": ("rings at the next pass", "never rings that session")}
    for name, (on, off) in flips.items():
        monkeypatch.setattr(GC, name, False)
        flipped = PT.rules_lines()[0]
        assert on not in flipped and off in flipped and flipped.count("Cheetah default, not his") == 3
        others = [c for n, _v, c in PT.defaults_clauses() if n != name]
        assert all(c in flipped for c in others) or name == "POTENTIAL_FRESH_TAPE"
        monkeypatch.setattr(GC, name, True)
    assert PT.rules_lines()[0] == base
    monkeypatch.setattr(GC, "POTENTIAL_FRESH_TAPE", False)
    c3 = PT.defaults_clauses()[2][2]
    assert "or by a missing print" not in c3 and "or by a missing print" in base


def test_defaults_sentence_names_only_the_true_ones(monkeypatch):
    assert PT.defaults_sentence() == ("Needing a sideways bar, waiting for a fresh print and ringing a held first "
                                      "sighting on the next pass are Cheetah defaults, not his (ℹ️ Rules).")
    monkeypatch.setattr(GC, "POTENTIAL_FRESH_TAPE", False)
    assert PT.defaults_sentence() == ("Needing a sideways bar and ringing a held first sighting on the next pass are "
                                      "Cheetah defaults, not his (ℹ️ Rules).")
    monkeypatch.setattr(GC, "POTENTIAL_NEEDS_BASE", False)
    assert PT.defaults_sentence() == "Ringing a held first sighting on the next pass is a Cheetah default, not his " \
                                     "(ℹ️ Rules)."
    monkeypatch.setattr(GC, "POTENTIAL_DEFER_REFUSED", False)
    assert PT.defaults_sentence() == ""


def _all_composed() -> list:
    out = [PT.TAIL, PT.AGAIN_TEXT, PT.CONCEPT[0], PT.defaults_sentence(), PT.push_note(S), PT.push_note(HALF_DAY)]
    out += PT.rules_lines() + list(PT.HELD_WORDS.values()) + list(PT.KIND_LABEL.values())
    out += [c for _n, _v, c in PT.defaults_clauses()]
    out += [PT.state_word(s, k) for s in D.STATES + ("graveyard",) for k in (None, "armed", "building")]
    out += [t["text"] for t in PT.tells(_values())] + [t["cite"] for t in PT.tells(_values())]
    for setup, r in one_per_setup().items():
        for kind in GC.POTENTIAL_KINDS:
            for tape in ("premarket", "rth", "afterhours"):
                p = PT.compose("AAA", setup, r, kind, _values(), first_seen_et="09:36", tape=tape)
                out += [p["title"], p["body"]] + [i["text"] for i in p["items"]]
            out += [PT.row_text("AAA", setup, r, kind, "09:36"), PT.line("AAA", setup, r, kind)]
    return out


def test_NEGATIVE_D6_no_composed_string_carries_a_forecast_word_another_method_or_the_b_word():
    from chart_maps.high_beta_tab import FORBIDDEN_WORDS                    # the house forecast list (TEST-only import)
    strings = _all_composed()
    assert len(strings) > 100
    for s in strings:
        low = s.lower()
        assert not [w for w in FORBIDDEN_WORDS if w in low], s
        assert not B_WORD.search(s), s
        assert not re.search(r"\bSEPA\b|Minervini|Bonde|TLSW|TTLAC", s), s
        assert not re.search(r"\bNaN\b|\bNone\b|undefined", s), s
    assert "potential to" not in " ".join(strings).lower()


# ── source guards ────────────────────────────────────────────────────────────────────────────────────────────────
def test_AST_no_numeric_literal_outside_the_allowed_set():
    tree = ast.parse(SRC)
    lits = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
            and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)}
    assert lits <= {0, 1, 2, 60, 100}, lits


def test_AST_never_reads_the_wall_clock():
    tree = ast.parse(SRC)
    bad = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
            if (n.value.id, n.attr) in {("datetime", "now"), ("datetime", "utcnow"), ("date", "today"),
                                        ("time", "time"), ("time", "monotonic")}:
                bad.append(f"{n.value.id}.{n.attr}")
    assert bad == []
    assert "import time" not in SRC


def test_NEGATIVE_the_guards_bite_on_a_planted_literal_and_clock():
    planted = ast.parse("x = 330\ny = datetime.now()")
    lits = {n.value for n in ast.walk(planted) if isinstance(n, ast.Constant) and isinstance(n.value, int)}
    assert not lits <= {0, 1, 2, 60, 100}
    assert any(isinstance(n, ast.Attribute) and n.attr == "now" for n in ast.walk(planted))


def test_NEGATIVE_no_tab_module_and_no_other_method_imported_at_module_level():
    tree = ast.parse(SRC)
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    mods = [getattr(n, "module", None) or "" for n in top] + [a.name for n in top for a in n.names]
    assert not [m for m in mods if "tab" in m or m.startswith("sepa") or "high_beta" in m], mods
    assert "high_beta_tab" not in SRC and "FORBIDDEN_WORDS" not in SRC
    assert not B_WORD.search(SRC)


# ── fix round 2 (2026-10-15, final critic): the join rule needs a COMPLETE previous count; D3 runs before shortcuts ──
def _record(st, now, block):
    """A pass doc whose `potential` block is `block` — what run._finish stores (run.py stores {} when the gate raised)."""
    st.record_pass(now.astimezone(ET).date(), now, {"status": "ok", "potential": block})


def test_gate_block_ok_table():
    assert PT._gate_block_ok({k: 0 for k in PT.COUNT_KEYS})                 # a quiet, complete count
    assert PT._gate_block_ok(dict({k: 0 for k in PT.COUNT_KEYS}, joined=2, tracked_today=2))
    assert not PT._gate_block_ok({})                                       # the gate raised (run.py's {})
    assert not PT._gate_block_ok(None)
    assert not PT._gate_block_ok("ok")
    assert not PT._gate_block_ok({"potential": 3, "joined": 0})            # no tracked_today: not run_pass's count
    assert not PT._gate_block_ok(dict({k: 0 for k in PT.COUNT_KEYS}, joined=2, tracked_today=0))   # writes lost


def test_NEGATIVE_D9_a_failed_gate_pass_does_not_count_as_ran_so_the_next_pass_joins():
    st = fake_store()
    _record(st, at(10, 1), {})                                             # 10:01: the 🧠 gate raised
    send = Rec(OK_SEND)
    out = go(st, at(10, 6), {s: {"bull_flag": bf_armed()} for s in SIX}, send=send)
    assert send.calls == [] and out["joined"] == 6 and out["pushed"] == 0


def test_NEGATIVE_D9_a_join_pass_with_every_write_lost_then_the_next_pass_at_plus_5_never_rings(monkeypatch):
    st = fake_store()
    send = Rec(OK_SEND)
    reads = {s: {"bull_flag": bf_armed()} for s in SIX}
    real, lost = st.upsert_potential, {"on": True}
    monkeypatch.setattr(st, "upsert_potential", lambda *a, **k: False if lost["on"] else real(*a, **k))
    out = go(st, at(10, 6), reads, send=send)                              # the join pass; Mongo drops every write
    assert out["joined"] == 6 and out["tracked_today"] == 0 and send.calls == []
    _record(st, at(10, 6), out)
    lost["on"] = False
    out = go(st, at(10, 11), reads, send=send)                             # +5 min, healthy store: joins again
    assert send.calls == [] and out["pushed"] == 0 and out["joined"] == 6
    assert all(doc_of(st, s)["first_seen_mode"] == "joined" for s in SIX)


def test_D9_a_complete_quiet_previous_count_still_lets_the_first_sighting_ring():
    st = fake_store()
    _record(st, at(10, 1), {k: 0 for k in PT.COUNT_KEYS})
    send = Rec(OK_SEND)
    out = go(st, at(10, 6), {"AAA": {"bull_flag": bf_armed()}}, send=send)
    assert len(send.calls) == 1 and out["joined"] == 0 and out["pushed"] == 1


def test_NEGATIVE_D3_muted_then_claim_error_then_partial_then_forming_never_rings():
    path = [{"state": "forming", "kind": "building"}, {"state": "partial", "kind": None},
            {"state": "forming", "kind": "armed"}]
    held = [{"reason": "muted"}, {"reason": "claim_error"}]
    assert not PT.eligible({"_id": "x", "first_seen_mode": "normal", "held": held, "state_path": path}, False, "armed")
    ok = [{"state": "forming", "kind": "building"}, {"state": "forming", "kind": "armed"}]
    assert PT.eligible({"_id": "x", "first_seen_mode": "normal", "held": held, "state_path": ok}, False, "armed")


def test_NEGATIVE_D3_a_doc_with_no_hold_and_a_broken_path_never_rings():
    """A lost hold write must not open the store / no-hold shortcut around D3."""
    path = [{"state": "forming", "kind": "building"}, {"state": "partial", "kind": None},
            {"state": "forming", "kind": "armed"}]
    assert not PT.eligible({"_id": "y", "first_seen_mode": "normal", "state_path": path}, False, "armed")
    assert not PT.eligible({"_id": "y", "first_seen_mode": "normal", "state_path": []}, False, "armed")


def test_NEGATIVE_D3_with_P1_off_a_rule_hold_beside_a_store_hold_never_rings(monkeypatch):
    monkeypatch.setattr(GC, "POTENTIAL_DEFER_REFUSED", False)
    path = [{"state": "forming", "kind": "armed"}]
    assert not PT.eligible({"held": [{"reason": "muted"}, {"reason": "claim_error"}], "state_path": path}, False,
                           "armed")
    assert PT.eligible({"held": [{"reason": "claim_error"}], "state_path": path}, False, "armed")   # store: retried


def test_NEGATIVE_D3_muted_then_lost_hold_then_partial_then_forming_end_to_end_never_rings(monkeypatch):
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    monkeypatch.setattr(st, "hold_potential", lambda *a, **k: False)       # every hold write is lost
    go(st, at(9, 36), {"AAA": {"bull_flag": bf_armed()}}, send=send)        # muted — the hold never lands
    assert "held" not in doc_of(st)
    go(st, at(9, 41), {"AAA": {"bull_flag": dict(bf_armed(), state="partial")}}, send=send)
    out = go(st, at(9, 46), {"AAA": {"bull_flag": bf_armed()}}, send=send)
    assert send.calls == [] and out["pushed"] == 0


# ── final critic 2026-10-15 (MED): a tracker READ FAULT is not an empty tracker ──────────────────────────────────
def _tracker_read_fault(st):
    """The potentials collection's READS raise while its writes still work (a read timeout on a live Mongo). Returns the
    restore callable."""
    coll = st.coll(ST.POTENTIALS)
    real_find, real_find_one = coll.find, coll.find_one

    def boom(*_a, **_k):
        raise RuntimeError("read timeout")

    coll.find = coll.find_one = boom

    def restore():
        coll.find, coll.find_one = real_find, real_find_one

    return restore


def test_NEGATIVE_a_tracker_read_fault_never_rings_the_joined_docs_nor_rewrites_their_timelines():
    """Final critic 2026-10-15: read as [], the 10:11 pass saw AAA / BBB / CCC — joined at 10:06 (D9) — as first
    sightings, claimed all three, rang them in one burst and replaced each timeline. The gate now skips the pass."""
    st = fake_store()
    send = Rec(OK_SEND)
    reads = {s: {"bull_flag": bf_armed()} for s in ("AAA", "BBB", "CCC")}
    out = go(st, at(10, 6), reads, send=send)
    _record(st, at(10, 6), out)
    assert out["joined"] == 3 and send.calls == []
    before = {s: copy.deepcopy(doc_of(st, s)) for s in reads}
    for s in reads:
        assert "push" not in before[s] and before[s]["first_seen_mode"] == "joined" and len(before[s]["state_path"]) == 1
    restore = _tracker_read_fault(st)
    out2 = go(st, at(10, 11), reads, send=send)
    restore()
    assert send.calls == [] and out2["pushed"] == 0 and out2["new"] == 0 and out2["claimed_before"] == 0
    assert out2["potential"] == 3 and out2["failed"] == 3
    assert "tracked_today" not in out2 and not PT._gate_block_ok(out2)      # D9 continuity: "the gate did not run"
    for s in reads:
        assert doc_of(st, s) == before[s]                                   # no claim, no path entry, no rewrite
    _record(st, at(10, 11), out2)
    out3 = go(st, at(10, 16), dict(reads, DDD={"bull_flag": bf_armed()}), send=send)   # the reads work again
    assert out3["joined"] == 0 and out3["pushed"] == 1 and len(send.calls) == 1        # DDD, a real first sighting
    assert doc_of(st, "DDD")["push"]["state"] == "pushed"
    for s in reads:
        assert "push" not in doc_of(st, s)                                  # the joined three still never ring


def test_D9_a_tracker_read_fault_on_a_quiet_morning_makes_the_next_pass_a_join():
    """Cheetah default, not his (P12): a skipped pass breaks the one-cadence continuity, so a zero-doc pass after it
    past 09:45 joins — tracked, never rung — rather than ringing names it cannot prove are new."""
    st = fake_store()
    send = Rec(OK_SEND)
    _gate_pass(st, at(10, 1))                                               # 10:01 ran the gate: nothing forming
    restore = _tracker_read_fault(st)
    out = go(st, at(10, 6), {"AAA": {"bull_flag": bf_armed()}}, send=send)  # 10:06: the tracker is unreadable
    restore()
    _record(st, at(10, 6), out)
    assert send.calls == [] and doc_of(st) is None and out["failed"] == 1
    out2 = go(st, at(10, 11), {"AAA": {"bull_flag": bf_armed()}}, send=send)
    assert out2["joined"] == 1 and send.calls == [] and doc_of(st)["first_seen_mode"] == "joined"


def test_NEGATIVE_the_claim_itself_refuses_a_joined_doc():
    """The second guard, end to end: even a joined doc handed straight to the claim stays unclaimed."""
    st = fake_store()
    out = go(st, at(10, 6), {"AAA": {"bull_flag": bf_armed()}}, send=Rec(OK_SEND))
    assert out["joined"] == 1
    d = doc_of(st)
    assert "push" not in d and st.claim_potential_push(d["_id"], {"state": "claimed"}) == "taken"
    assert "push" not in doc_of(st) and ST.JOINED_MODE == PT.FIRST_SEEN_MODES[1]


# ── 🏁 2026-10-16 (BUILD_SPEC9 §3.9): the claim records the plan the push carried — the Track record's plan ─────────
def test_a_rung_push_records_the_reads_trigger_stop_and_the_frame_close():
    st = fake_store()
    seed(st)
    r = bf_armed()
    go(st, at(10, 6), {"AAA": {"bull_flag": r}}, send=Rec(OK_SEND), px=10.93)
    push = doc_of(st)["push"]
    assert (push["trigger"], push["stop"], push["px"]) == (PT._num(r["trigger"]), PT._num(r["stop"]), 10.93)
    assert push["trigger"] is not None and push["stop"] is not None


@pytest.mark.parametrize("ret,state", [(OK_SEND, "pushed"), ({"sent": 0, "failed": 0, "total_targets": 0}, "no_target"),
                                       (RuntimeError("down"), "failed")])
def test_NEGATIVE_the_settle_never_drops_the_recorded_plan(ret, state):
    st = fake_store()
    seed(st)
    r = bf_armed()
    go(st, at(10, 6), {"AAA": {"bull_flag": r}}, send=Rec(ret), px=10.93)
    push = doc_of(st)["push"]
    assert push["state"] == state
    assert (push["trigger"], push["stop"], push["px"]) == (PT._num(r["trigger"]), PT._num(r["stop"]), 10.93)


def test_NEGATIVE_a_held_first_sighting_records_no_plan_and_no_push():
    st = fake_store()
    seed(st)
    go(st, at(9, 36), {"AAA": {"bull_flag": bf_armed()}}, send=Rec(OK_SEND))          # his first 15 minutes
    assert "push" not in doc_of(st)
