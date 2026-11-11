"""💋 EMA Kiss & Fly: relative volume first, then closest to the 9 EMA (2026-11-11) + the "lifting off the 9 EMA" flag.

Ajay 2026-11-11 ~12:50 ET, verbatim: "Sort by relative volume, and closer to the EMA." · "This filter is needed for EMA
Kiss atleast". Display order only — no gate, rule, threshold, push or count change. UNMEASURED.

What is pinned (spec rev 2 §3.2–3.4 + the main session's addendum "Served" section):
- `tab.order_key` on the 💋 sub: state rank › rel volume ↓ › 9 EMA distance ↑ › volume ↓ › float ↑ › today's key; each
  unknown = inf (last in its state, never 0, never below a lower state); `GC.KF_EMA_SORT` "ema_first" swaps the two.
- The stash (`_rvol` = ctx["rvol"]["rvol"], the house engine `drop10_tab.rvol_read`; `_kiss_gap_pct` = the K5 row's
  printed number) is set ONLY by build's setup-sub call (`kf_rank=True`) — the 🧠 tiles, the banner and the focus
  resolve keep today's key byte-identical; it is popped before serving.
- The "Rel volume" stat = `drop10_tab.rvol_text(rv)` verbatim, right after Volume, only when known.
- `list_note` on 💋 only on a MIXED board; the 💋 `order_note` = `KF_ORDER_TEXT[GC.KF_EMA_SORT]`.
- `kiss_now` (tile level, the 💋 sub only): True = A+ / triggered / forming-ready; False = partial / stopped / a forming
  read whose K5 row says not kissing; None = unknown (never False). `kiss_filter` words on the 💋 sub only.
NEGATIVES everywhere: other subs, other setups, no stash, pre-market dicts, unknown rows, banned words.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from chart_maps import drop10_tab as DT
from chart_maps.gajjala import audited_rules as AUD
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from supply_demand import momentum_burst as MB
from tests import test_gajjala_potential_tab as PTT
from tests.test_gajjala_broker_flags import flag
from tests.test_gajjala_fade_ema_rank_2026_11_08 import GGA_OWN
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_tab import NOW, R, latest, ordering_store, read_doc, scan_doc, store_with

KF, BF, HF, VCP, RS = "kiss_fly", "bull_flag", "horizontal_fade", "intraday_vcp", "reversal_squeeze"
INF = float("inf")
BANNED = ("edge", "probabil", "bounc")


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


# ── builders ─────────────────────────────────────────────────────────────────────────────────────────────────────
def k5(ok, value):
    return {"key": "k5_kiss", "label": "K5 pullback touched the 9 EMA (the kiss)", "ok": ok, "value": value,
            "need": "a low no more than 0.5% above the 9 EMA and a close above it"}


def kf(state="ready", gap="low 0.3% above the 9 EMA", **kw):
    """A 💋 read. "ready" = forming-ready (kissing now); "forming" = waiting for the kiss; else the state as given."""
    if state == "ready":
        base = dict(ready=True, trigger=4.10, criteria=[k5(True, gap)])
        return R(KF, "forming", **dict(base, **kw))
    if state == "forming":
        base = dict(ready=False, base={"bars": 0}, reason="waiting", criteria=[k5(False, gap)])
        return R(KF, "forming", **dict(base, **kw))
    if state in ("aplus", "triggered", "stopped"):
        base = dict(entry_bar_t="2026-10-13 10:25", broke=True, criteria=[k5(True, "kiss bar 2026-10-13 10:20")])
        return R(KF, state, **dict(base, **kw))
    return R(KF, state, **kw)


def rv(vol, avg=1e6, tape="afterhours", frac=1.0):
    """The house engine's own dict (what WP-CTX stores as ctx["rvol"])."""
    return DT.rvol_read({"volume": vol}, {"avg_vol50": avg}, tape=tape, frac=frac, half_day=False)


def _docs(cards: dict, setup=KF):
    return [read_doc(s, {setup: r}, ctx=({"rvol": x} if x is not None else None)) for s, (r, x) in cards.items()]


def _shared(cards, setup=KF, vols=None):
    vols = vols or {}
    return store_with(reads=_docs(cards, setup), scans=[scan_doc(s, volume=vols.get(s, 2e6)) for s in cards],
                      passes=[latest()])


def _store(cards: dict, v=None, setup=KF, vols=None):
    if v is V.GG1:
        own = {n: FakeColl() for n in ST.OWN}
        own[ST.READS] = FakeColl(_docs(cards, setup))
        own[ST.PASSES] = FakeColl([latest()])
        return ST.GajjalaStore(colls=own, variant=V.GG1, shared=_shared(cards, setup, vols))
    if v is V.GGA:
        return ST.GajjalaStore(colls={n: FakeColl() for n in GGA_OWN}, variant=V.GGA,
                               shared=_shared(cards, setup, vols))
    return _shared(cards, setup, vols)


def build(cards, sub=KF, v=None, setup=KF, **kw):
    return GT.build(sub, now=NOW, store=_store(cards, v, setup), variant=v, **kw)


def syms(out):
    return [t["symbol"] for t in out["tiles"]]


def key(setup, state, **g):
    return GT.order_key({"symbol": "X", "gajjala": dict({"setup": setup, "state": state}, **g)})


def today(setup, state, **g):
    return GT._state_key(dict({"setup": setup, "state": state}, **g), "X")


READY = dict(ready=True, trigger=4.10, _last=4.05)
WAIT = dict(ready=False, _bars_to_go=None)


# ── the constants ────────────────────────────────────────────────────────────────────────────────────────────────
def test_constants_scope_knob_and_placement():
    assert GC.RVOL_SORT_SETUPS == ("kiss_fly",) and set(GC.RVOL_SORT_SETUPS) <= set(GC.SETUPS)
    assert GC.KF_EMA_SORT == "rvol_first" and GC.KF_EMA_SORT in GC.KF_EMA_SORTS == ("rvol_first", "ema_first")
    assert set(GT.KF_ORDER_TEXT) == set(GC.KF_EMA_SORTS)
    assert GC.RS_FLOAT_SORT == "within_state"        # "A+ … kissing … on top" holds only while the slot sits in-state
    for s in ("premarket", "postmarket", "playbook", GC.POTENTIAL_SUB, GC.LEDGER_SUB):    # NEGATIVE: list subs
        assert s not in GC.RVOL_SORT_SETUPS


# ── order_key ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_exact_key_state_then_rvol_then_gap_then_volume_then_float_then_todays_key():
    t = today(KF, "forming", **READY)
    got = key(KF, "forming", _rvol=2.0, _kiss_gap_pct=0.3, _volume=5e6, _float_shares=1e6, **READY)
    assert got == t[:1] + (-2.0, 0.3, -5e6, 1e6) + t[1:]


def test_higher_rvol_first_inside_a_state_and_unknown_is_inf_last():
    hi = key(KF, "forming", _rvol=5.0, _kiss_gap_pct=0.3, **READY)
    lo = key(KF, "forming", _rvol=1.0, _kiss_gap_pct=0.0, **READY)
    unk = key(KF, "forming", _rvol=None, _kiss_gap_pct=0.0, **READY)
    assert hi < lo < unk and unk[1] == INF


def test_NEGATIVE_unknown_rvol_never_reads_as_zero_and_never_drops_below_a_lower_state():
    unk = key(KF, "forming", _rvol=None, _kiss_gap_pct=None, **READY)
    zero = key(KF, "forming", _rvol=0.0, _kiss_gap_pct=None, **READY)
    assert zero < unk                                                  # a 0× read is known, an unknown is last
    assert unk < key(KF, "forming", _rvol=99.0, _kiss_gap_pct=0.0, **WAIT)        # a lower state never rises
    assert unk < key(KF, "partial", _rvol=99.0, _kiss_gap_pct=0.0, missed=["k3_vol"])


def test_NEGATIVE_kissing_now_at_0_1x_beats_a_waiting_card_at_50x_and_aplus_beats_both():
    ready = key(KF, "forming", _rvol=0.1, _kiss_gap_pct=0.4, **READY)
    waiting = key(KF, "forming", _rvol=50.0, _kiss_gap_pct=0.0, **WAIT)
    aplus = key(KF, "aplus", _rvol=0.01, _kiss_gap_pct=None, entry_bar_t="2026-10-13 10:30")
    assert aplus < ready < waiting
    assert key(KF, "triggered", _rvol=0.01, _kiss_gap_pct=None, entry_bar_t="2026-10-13 10:30") < ready


def test_rvol_tie_falls_to_the_9_ema_distance_unknown_distance_last():
    near = key(KF, "forming", _rvol=2.0, _kiss_gap_pct=0.1, **READY)
    far = key(KF, "forming", _rvol=2.0, _kiss_gap_pct=0.4, **READY)
    unk = key(KF, "forming", _rvol=2.0, _kiss_gap_pct=None, **READY)
    assert near < far < unk and unk[2] == INF


def test_ema_first_swaps_the_two_keys(monkeypatch):
    monkeypatch.setattr(GC, "KF_EMA_SORT", "ema_first")
    t = today(KF, "forming", **READY)
    assert key(KF, "forming", _rvol=2.0, _kiss_gap_pct=0.3, **READY) == t[:1] + (0.3, -2.0) + t[1:]
    assert (key(KF, "forming", _rvol=0.5, _kiss_gap_pct=0.1, **READY)
            < key(KF, "forming", _rvol=9.0, _kiss_gap_pct=0.4, **READY))


def test_global_placement_still_puts_the_slot_first(monkeypatch):
    monkeypatch.setattr(GC, "RS_FLOAT_SORT", "global")
    t = today(KF, "forming", **READY)
    assert key(KF, "forming", _rvol=2.0, _kiss_gap_pct=0.3, **READY) == (0, -2.0, 0.3) + t


@pytest.mark.parametrize("setup", [s for s in GC.SETUPS if s != KF])
def test_NEGATIVE_another_setup_carrying_the_stash_keeps_todays_exact_key(setup):
    g = dict(ready=True, trigger=4.10, _last=4.05, _volume=5e6, _float_shares=1e6)
    if setup == HF:
        g["_ema_gap_pct"] = 0.4
    assert key(setup, "forming", _rvol=9.0, _kiss_gap_pct=0.0, **g) == key(setup, "forming", **g)


def test_NEGATIVE_a_kiss_card_without_the_stash_keeps_todays_exact_key():
    """The banner / the focus resolve / the 🧠 tiles build no stash → the 📊 key byte-identical."""
    g = dict(ready=True, trigger=4.10, _last=4.05, _volume=5e6, _float_shares=1e6)
    t = today(KF, "forming", **g)
    assert key(KF, "forming", **g) == t[:1] + (-5e6, 1e6) + t[1:]
    assert GT._kf_slot({"setup": KF, "state": "forming", "_kiss_gap_pct": 0.1}) == ()   # a gap alone is no stash
    assert GT.order_key({"symbol": "X", "gajjala": dict({"setup": KF, "state": "forming"}, **READY)}) == today(
        KF, "forming", **READY)


# ── _kiss_gap_pct: the K5 row's printed number ───────────────────────────────────────────────────────────────────
def _kiss_text(low, e9):
    return D._kiss_text(SimpleNamespace(l=[low], ema9=[e9]), 0)


@pytest.mark.parametrize("low, e9, want", [(10.03, 10.0, 0.3), (9.95, 10.0, 0.5), (11.25, 10.0, 12.5),
                                           (10.001, 10.0, 0.0), (8.0, 10.0, 20.0)])
def test_kiss_gap_round_trips_the_detectors_own_words(low, e9, want):
    text = _kiss_text(low, e9)
    assert GT._kiss_gap_pct({"criteria": [k5(None, text)]}) == want, text


@pytest.mark.parametrize("value", ["9 EMA warming up", "no pullback yet", "flew without touching the 9 EMA",
                                   "kiss bar 10:35", "kiss bar 2026-10-13 10:20", "low —% above the 9 EMA", "", None,
                                   "low 0.3% above the 21 EMA", "the low 0.3% above the 9 EMA"])
def test_NEGATIVE_kiss_gap_is_none_for_every_other_value(value):
    assert GT._kiss_gap_pct({"criteria": [k5(True, value)]}) is None


def test_NEGATIVE_kiss_gap_none_without_a_k5_row_and_the_warming_text_parses_none():
    assert GT._kiss_gap_pct({"criteria": [{"key": "k3_vol", "value": "low 0.3% above the 9 EMA"}]}) is None
    assert GT._kiss_gap_pct({}) is None and GT._kiss_gap_pct(None) is None
    assert GT._kiss_gap_pct({"criteria": [k5(None, _kiss_text(10.0, None))]}) is None


# ── the board order ──────────────────────────────────────────────────────────────────────────────────────────────
ORDER_CARDS = {
    "AAA": (kf("ready", "low 0.4% above the 9 EMA"), rv(1e6)),          # 1.0×
    "BBB": (kf("ready", "low 0.4% above the 9 EMA"), rv(5e6)),          # 5.0×
    "CCC": (kf("ready", "low 0.1% above the 9 EMA"), None),             # unknown rel volume → last of the ready
    "DDD": (kf("ready", "low 0.1% under the 9 EMA"), rv(3e6)),          # 3.0×, tie with EEE → closer first
    "EEE": (kf("ready", "low 0.3% above the 9 EMA"), rv(3e6)),
    "FFF": (kf("forming", "low 2.0% above the 9 EMA"), rv(50e6)),       # waiting for the kiss: below every ready card
    "GGG": (kf("aplus"), rv(0.1e6)),                                    # flew: on top at any rvol
}
ORDER_WANT = ["GGG", "BBB", "DDD", "EEE", "AAA", "CCC", "FFF"]


def test_build_serves_the_kiss_order_and_its_word():
    out = build(ORDER_CARDS)
    assert syms(out) == ORDER_WANT
    assert out["order_note"] == GT.KF_ORDER_TEXT["rvol_first"]


def test_build_ema_first_order_and_word(monkeypatch):
    monkeypatch.setattr(GC, "KF_EMA_SORT", "ema_first")
    out = build(ORDER_CARDS)
    assert syms(out) == ["GGG", "DDD", "CCC", "EEE", "BBB", "AAA", "FFF"]
    assert out["order_note"] == GT.KF_ORDER_TEXT["ema_first"]


def test_NEGATIVE_no_private_key_is_served():
    out = build(ORDER_CARDS)
    blob = json.dumps(out, default=str)
    assert '"_rvol"' not in blob and '"_kiss_gap_pct"' not in blob
    assert all(not k.startswith("_") for t in out["tiles"] for k in t["gajjala"])


def test_NEGATIVE_counts_and_the_sub_strip_do_not_move_with_ctx_rvol():
    bare = {s: (r, None) for s, (r, _x) in ORDER_CARDS.items()}
    a, b = build(ORDER_CARDS), build(bare)
    assert a["counts"] == b["counts"] and a["subs"] == b["subs"]
    assert sorted(syms(a)) == sorted(syms(b))


def test_NEGATIVE_without_any_average_the_order_is_distance_then_todays_key():
    """All-unknown (deploy day / pre-market): the rvol key is constant, so the 9 EMA distance orders the ready cards."""
    bare = {s: (r, None) for s, (r, _x) in ORDER_CARDS.items()}
    assert syms(build(bare)) == ["GGG", "CCC", "DDD", "EEE", "AAA", "BBB", "FFF"]


@pytest.mark.parametrize("v", [V.GG1, V.GGA])
def test_one_minute_and_audited_serve_the_same_kiss_order(v):
    out = build(ORDER_CARDS, v=v)
    assert syms(out) == ORDER_WANT and out["order_note"] == GT.KF_ORDER_TEXT["rvol_first"]


def test_a_broker_flagged_name_with_the_top_rvol_still_sits_last():
    st = flag(_store(ORDER_CARDS), "BBB")
    out = GT.build(KF, now=NOW, store=st)
    assert syms(out) == [s for s in ORDER_WANT if s != "BBB"] + ["BBB"]


def test_focus_five_marks_the_first_five_of_the_new_order():
    assert len(ORDER_CARDS) > GC.FOCUS_N
    out = build(ORDER_CARDS)
    assert [t["symbol"] for t in out["tiles"] if t.get("focus")] == ORDER_WANT[:GC.FOCUS_N]


# ── the "Rel volume" stat ────────────────────────────────────────────────────────────────────────────────────────
def test_stat_is_the_house_words_right_after_volume():
    proj = rv(3e6, tape="rth", frac=0.4)
    assert proj["basis"] == "projected"
    out = build({"AAA": (kf("ready"), proj)})
    stats = out["tiles"][0]["stats"]
    assert [s["k"] for s in stats] == ["Change", "Volume", GT.RVOL_STAT_KEY]
    assert stats[2]["v"] == DT.rvol_text(proj) and GT.RVOL_STAT_KEY == "Rel volume"


def test_NEGATIVE_a_premarket_dict_prints_no_stat_and_sorts_unknown():
    pm = rv(3e6, tape="premarket", frac=None)
    assert pm["rvol"] is None and pm["code"] == "premarket"
    out = build({"AAA": (kf("ready", "low 0.4% above the 9 EMA"), pm),
                 "BBB": (kf("ready", "low 0.4% above the 9 EMA"), rv(0.2e6))})
    assert syms(out) == ["BBB", "AAA"]
    aaa = out["tiles"][1]
    assert GT.RVOL_STAT_KEY not in [s["k"] for s in aaa["stats"]]


@pytest.mark.parametrize("ctx_rv", [None, "junk", {"rvol": None}, {"basis": "session"}])
def test_NEGATIVE_no_or_bad_ctx_rvol_prints_no_stat(ctx_rv):
    doc = read_doc("AAA", {KF: kf("ready")}, ctx={"rvol": ctx_rv} if ctx_rv is not None else None)
    st = store_with(reads=[doc], scans=[scan_doc("AAA")], passes=[latest()])
    out = GT.build(KF, now=NOW, store=st)
    assert [s["k"] for s in out["tiles"][0]["stats"]] == ["Change", "Volume"]


@pytest.mark.parametrize("setup", [s for s in GC.SETUPS if s != KF])
def test_NEGATIVE_no_stat_and_no_kiss_flag_on_another_setup_sub_even_with_ctx_rvol(setup):
    cards = {"AAA": (R(setup, "forming", ready=True, trigger=4.10), rv(5e6)),
             "BBB": (R(setup, "forming", ready=True, trigger=4.10), None)}
    out = build(cards, sub=setup, setup=setup)
    assert out["tiles"]
    for t in out["tiles"]:
        assert GT.RVOL_STAT_KEY not in [s["k"] for s in t["stats"]]
        assert "kiss_now" not in t
    assert "kiss_filter" not in out
    assert out.get("list_note") is None or setup == VCP


def test_NEGATIVE_C5_the_potential_tiles_never_take_the_kiss_stash(monkeypatch):
    """🧠 cards (`_potential_tiles`) call setup_tile WITHOUT kf_rank: a 💋-primary 🧠 card with ctx rvol shows no
    "Rel volume" stat and no kiss flag; only build's setup-sub call passes kf_rank=True."""
    st = PTT.day_store()
    st.upsert_read(PTT.S, "HHH", PTT.read_doc("HHH", {KF: PTT.kf_building()}, ctx=dict(PTT.ctx("HHH"), rvol=rv(5e6))),
                   now=PTT.NOW)
    seen = []
    real = GT.setup_tile

    def spy(*a, **kw):
        seen.append((a[1], kw.get("kf_rank", False)))
        return real(*a, **kw)

    monkeypatch.setattr(GT, "setup_tile", spy)
    out = GT.build(GC.POTENTIAL_SUB, now=PTT.NOW, store=st)
    hhh = [t for t in out["tiles"] if t["symbol"] == "HHH"]
    assert hhh and hhh[0]["gajjala"]["setup"] == KF
    assert GT.RVOL_STAT_KEY not in [s["k"] for s in hhh[0]["stats"]] and "kiss_now" not in hhh[0]
    assert seen and all(k is False for _s, k in seen)
    assert "kiss_filter" not in out
    seen.clear()
    GT.build(KF, now=PTT.NOW, store=st)
    assert seen and all(k is True for _s, k in seen)


# ── list_note ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_list_note_on_a_mixed_board_counts_before_the_cut():
    out = build(ORDER_CARDS, limit=1)
    want = (f"💋 1 of {len(ORDER_CARDS)} have no relative volume yet (fewer than {MB.VOL_AVG_BARS} trading days, or "
            f"not read yet) — they sit last in their state")
    assert out["list_note"] == want and len(out["tiles"]) == 1


def test_NEGATIVE_list_note_none_when_all_unknown_or_all_known():
    every = {s: (r, None) for s, (r, _x) in ORDER_CARDS.items()}
    assert build(every)["list_note"] is None
    known = {s: (r, x if x is not None else rv(1e6)) for s, (r, x) in ORDER_CARDS.items()}
    assert build(known)["list_note"] is None
    pm = {s: (r, rv(3e6, tape="premarket", frac=None)) for s, (r, _x) in ORDER_CARDS.items()}
    assert build(pm)["list_note"] is None                         # pre-market: every card unknown, silent by design


def test_NEGATIVE_list_note_none_on_the_bull_flag_and_the_vcp_note_unchanged():
    cards = {"AAA": (R(BF, "forming", ready=True, trigger=4.10), rv(5e6)),
             "BBB": (R(BF, "forming", ready=True, trigger=4.10), None)}
    assert build(cards, sub=BF, setup=BF)["list_note"] is None
    assert GT.build(VCP, now=NOW, store=ordering_store())["list_note"] == GT.vcp_list_note(0)


def test_kf_list_note_unit():
    t = lambda **g: {"gajjala": dict({"setup": KF}, **g)}                     # noqa: E731
    assert GT.kf_list_note([t(_rvol=1.0), t(_rvol=None), t(_rvol=None)]).startswith("💋 2 of 3 ")
    assert GT.kf_list_note([t(_rvol=1.0), t()]) is None                       # no stash = not counted as unknown
    assert GT.kf_list_note([]) is None and GT.kf_list_note(None) is None


# ── kiss_now (the addendum's flag) ───────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("read, want", [
    (kf("aplus"), True),
    (kf("triggered"), True),
    (kf("ready"), True),
    (kf("forming", "low 2.0% above the 9 EMA"), False),
    (kf("forming", "no pullback yet"), False),
    (kf("partial", missed=["k3_vol"]), False),
    (kf("stopped"), False),
    (kf("forming", "9 EMA warming up", criteria=[k5(None, "9 EMA warming up")]), None),
    (kf("forming", criteria=[]), None),                                     # no K5 row → unknown
    (kf("forming", criteria=[k5(True, "low 0.2% above the 9 EMA")], unjudged=["k5_uptrend"]), None),
    ({"state": AUD.HELD_STATE, "audit": {}}, None),                          # 🧪 held — not one of the named reads
    ({"state": "invalid"}, None),
    ({}, None),
])
def test_kiss_now_off_the_existing_reads(read, want):
    assert GT.kiss_now_of(read) is want


def test_kiss_now_is_served_on_every_kiss_card_null_included():
    cards = {"AAA": (kf("aplus"), None), "BBB": (kf("ready"), None), "CCC": (kf("forming"), None),
             "DDD": (kf("forming", criteria=[k5(None, "9 EMA warming up")]), None),
             "EEE": (kf("partial", missed=["k3_vol"]), None)}
    out = build(cards)
    got = {t["symbol"]: t["kiss_now"] for t in out["tiles"]}
    assert got == {"AAA": True, "BBB": True, "CCC": False, "DDD": None, "EEE": False}
    assert all("kiss_now" in t for t in out["tiles"])               # null is SERVED (unknown ≠ absent ≠ False)


@pytest.mark.parametrize("v", [V.GG1, V.GGA])
def test_kiss_now_on_the_one_minute_and_audited_kiss_sub(v):
    out = build({"AAA": (kf("ready"), None), "BBB": (kf("forming"), None)}, v=v)
    assert {t["symbol"]: t["kiss_now"] for t in out["tiles"]} == {"AAA": True, "BBB": False}


def test_NEGATIVE_kiss_now_absent_on_the_bull_flag_board():
    out = GT.build(BF, now=NOW, store=ordering_store())
    assert out["tiles"] and all("kiss_now" not in t for t in out["tiles"])


# ── kiss_filter (the toggle's words) ─────────────────────────────────────────────────────────────────────────────
def test_kiss_filter_words_served_on_the_kiss_sub():
    out = build(ORDER_CARDS)
    assert out["kiss_filter"] == {"label": GT.KF_FILTER_LABEL, "hint": GT.KF_FILTER_HINT,
                                  "hidden_text_template": GT.KF_FILTER_LINE}
    assert GT.KF_FILTER_LABEL == "💋 lifting off the 9 EMA only"
    line = GT.KF_FILTER_LINE.format(shown=5, hidden=2, unknown=1)
    assert line == "5 shown · 2 hidden (not at the 9 EMA now) · 1 unknown kept"


def test_kiss_filter_served_on_an_empty_kiss_board_and_every_variant():
    assert GT.build(KF, now=NOW, store=ordering_store())["kiss_filter"] == GT.kiss_filter_block()
    for v in (V.GG1, V.GGA):
        assert build(ORDER_CARDS, v=v)["kiss_filter"] == GT.kiss_filter_block()


def test_NEGATIVE_kiss_filter_absent_on_every_other_sub():
    st = ordering_store()
    for sub in [s for s in GC.SETUPS if s != KF] + ["premarket", "postmarket", "playbook", GC.POTENTIAL_SUB]:
        assert "kiss_filter" not in GT.build(sub, now=NOW, store=st), sub


# ── the words ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_no_banned_word_in_any_new_served_string():
    note = GT.kf_list_note([{"gajjala": {"_rvol": 1.0}}, {"gajjala": {"_rvol": None}}])
    words = list(GT.KF_ORDER_TEXT.values()) + [note, GT.RVOL_STAT_KEY, GT.KF_FILTER_LABEL, GT.KF_FILTER_HINT,
                                               GT.KF_FILTER_LINE] + list(GT.kiss_filter_block().values())
    for w in words:
        assert w and not any(b in w.lower() for b in BANNED), w


def test_NEGATIVE_no_b_word_anywhere_in_the_served_kiss_board():
    blob = json.dumps(build(ORDER_CARDS), default=str, ensure_ascii=False).lower()
    assert "bounc" not in blob


def test_order_words_name_the_ranks_his_words_and_the_volume():
    for w in GT.KF_ORDER_TEXT.values():
        assert w.startswith("💋 A+ and triggered, then kissing the 9 EMA now, on top")
        assert "highest relative volume" in w and "closest to the 9 EMA" in w and "volume" in w
