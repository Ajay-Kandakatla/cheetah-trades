"""🎾 float key on EVERY Gajjala setup sub (2026-11-09) — display order only.

Ajay 2026-11-09, verbatim: "Are the reversal squeeze tickers sorted by high probability can you update other tabs in
the same way I like how they are realtime updating the prices of now" then "When I say all tabs with in Gajjalas only".
Binding earlier calls: Ajay 2026-10-18 "for the float lower the better is what I wanna follow so sort it by lowest on
top" (DECISIONS13 D3 → GC.RS_FLOAT_SORT) and Ajay 2026-11-07 (➖ GC.HF_EMA_SORT, the 9/21 EMA gap FIRST).

tab.order_key: every setup in GC.FLOAT_SORT_SETUPS = (state rank, float ascending — unknown last —, today's key…);
➖ keeps the gap first and takes the float right after it. The stash is the float chip's own read (_float_read:
ctx first, the 🎾 daily doc only on 🎾) — no new fetch. ☀️ / 🌙 / 🧠 orders never move. No probability is claimed.
"""
from __future__ import annotations

import json

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests.test_gajjala_fade_ema_rank_2026_11_08 import GGA_OWN, fade
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_tab import (NOW, PREV, R, _daily, _pm_store, _post_store, latest, read_doc, scan_doc,
                                    store_with, utc)

BF, KF, HF, VCP, RS = "bull_flag", "kiss_fly", "horizontal_fade", "intraday_vcp", "reversal_squeeze"
INF = float("inf")
APLUS_T = "2026-10-13 10:30"
NEWEST = -202610131030.0


def _ctx(shares, suspect=None):
    return {"float": {"shares": shares, "src": "float", "text": None, "suspect": suspect}}


def _docs(setup_reads: dict, floats: dict):
    """{sym: read} → read docs whose ctx carries the float (the chip's own read); a missing float = no ctx float."""
    return [read_doc(s, {r["setup"]: r}, ctx=_ctx(floats[s]) if floats.get(s) is not None else None)
            for s, r in setup_reads.items()]


def _shared(reads: dict, floats: dict, daily=()):
    return store_with(reads=_docs(reads, floats), scans=[scan_doc(s) for s in reads], passes=[latest()],
                      daily=list(daily))


def _store(reads: dict, floats: dict, v=None):
    if v is V.GG1:
        own = {n: FakeColl() for n in ST.OWN}
        own[ST.READS] = FakeColl(_docs(reads, floats))
        own[ST.PASSES] = FakeColl([latest()])
        return ST.GajjalaStore(colls=own, variant=V.GG1, shared=_shared(reads, floats))
    if v is V.GGA:
        return ST.GajjalaStore(colls={n: FakeColl() for n in GGA_OWN}, variant=V.GGA, shared=_shared(reads, floats))
    return _shared(reads, floats)


def syms(reads, floats, sub, v=None):
    out = GT.build(sub, now=NOW, store=_store(reads, floats, v), variant=v)
    return [t["symbol"] for t in out["tiles"]]


def key(setup, state, fl="absent", **g):
    gg = dict({"setup": setup, "state": state}, **g)
    if fl != "absent":
        gg["_float_shares"] = fl
    return GT.order_key({"symbol": "X", "gajjala": gg})


NON_FADE = tuple(s for s in GC.FLOAT_SORT_SETUPS if s != HF)


# ── the constant ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_float_sort_setups_is_every_setup_sub_read_off_setups():
    assert GC.FLOAT_SORT_SETUPS == GC.SETUPS
    assert set(GC.FLOAT_SORT_SETUPS) == {k for k, _e, _l in GC.SUBS if k in GC.SETUPS}
    for s in ("premarket", "postmarket", "playbook", GC.POTENTIAL_SUB, GC.LEDGER_SUB):    # NEGATIVE: list subs
        assert s not in GC.FLOAT_SORT_SETUPS
    assert GC.RS_FLOAT_SORT == "within_state"                                             # the ONE mode knob


# ── the key, per setup ───────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("setup", NON_FADE)
def test_key_is_state_rank_then_float_then_todays_key(setup):
    today = key(setup, "aplus", entry_bar_t=APLUS_T)
    assert today == (0, NEWEST, 0.0, "X")
    assert key(setup, "aplus", 3_000_000, entry_bar_t=APLUS_T) == (0, 3_000_000.0, NEWEST, 0.0, "X")
    assert key(setup, "aplus", None, entry_bar_t=APLUS_T) == (0, INF, NEWEST, 0.0, "X")        # unknown last
    assert key(setup, "aplus", 0, entry_bar_t=APLUS_T)[1] == INF                                  # 0 = unknown
    f = key(setup, "forming", 2_000_000, _bars_to_go=2)
    assert f[:2] == (3, 2_000_000.0) and f[2:] == GT._state_key({"state": "forming", "_bars_to_go": 2}, "X")[1:]


@pytest.mark.parametrize("setup", GC.FLOAT_SORT_SETUPS)
def test_unknown_float_sorts_last_within_its_state_never_below_a_lower_state(setup):
    reads = {"UNK": R(setup, "forming", base={"bars": 0}), "BIG": R(setup, "forming", base={"bars": 0}),
             "LOW": R(setup, "forming", base={"bars": 0}),
             "PAR": R(setup, "partial", missed=["k2"])}
    if setup == HF:
        reads = {s: fade(r["state"], 0.3, missed=r["missed"]) for s, r in reads.items()}
    floats = {"BIG": 9_000_000, "LOW": 1_000_000, "PAR": 500_000}
    got = syms(reads, floats, setup)
    if setup == HF:                                           # pre_break: forming + partial ONE bucket, gaps equal →
        assert got == ["PAR", "LOW", "BIG", "UNK"]            # the float decides across the bucket, unknown last
    else:
        assert got == ["LOW", "BIG", "UNK", "PAR"]            # partial stays below forming whatever its float


@pytest.mark.parametrize("setup", NON_FADE)
def test_symbols_against_the_float_so_the_float_is_what_moved_them(setup):
    reads = {s: R(setup, "forming", base={"bars": 0}) for s in ("AAA", "BBB", "CCC")}
    assert syms(reads, {}, setup) == ["AAA", "BBB", "CCC"]                          # NEGATIVE: no float → symbol
    assert syms(reads, {"AAA": 9e6, "BBB": 4e6, "CCC": 1e6}, setup) == ["CCC", "BBB", "AAA"]


@pytest.mark.parametrize("setup", NON_FADE)
def test_aplus_stays_above_forming_whatever_the_float(setup):
    reads = {"APL": R(setup, "aplus", entry_bar_t="2026-10-13 10:20", broke=True),
             "FRM": R(setup, "forming", base={"bars": 0})}
    assert syms(reads, {"APL": 9_000_000, "FRM": 1_000_000}, setup) == ["APL", "FRM"]


@pytest.mark.parametrize("setup", NON_FADE)
def test_equal_floats_keep_todays_tiebreaks(setup):
    reads = {"OLD": R(setup, "aplus", entry_bar_t="2026-10-13 10:00", broke=True),
             "NEW": R(setup, "aplus", entry_bar_t="2026-10-13 10:30", broke=True),
             "LOW": R(setup, "aplus", entry_bar_t="2026-10-13 09:50", broke=True)}
    assert syms(reads, {"OLD": 4e6, "NEW": 4e6, "LOW": 1e6}, setup) == ["LOW", "NEW", "OLD"]


# ── 🎾 byte-identical ────────────────────────────────────────────────────────────────────────────────────────────
def test_squeeze_key_is_byte_identical_to_before(monkeypatch):
    def before(g, sym="X"):                                     # the 2026-11-08 🎾 branch, verbatim
        k = GT._state_key(g, sym)
        fl = g.get("_float_shares")
        fk = float(fl) if fl else INF
        return (0, fk) + k if GC.RS_FLOAT_SORT == "global" else k[:1] + (fk,) + k[1:]
    cases = [dict(state="aplus", entry_bar_t=APLUS_T), dict(state="forming", ready=True, trigger=4.1, _last=4.0),
             dict(state="forming", _bars_to_go=3), dict(state="partial", missed=["k2"]),
             dict(state="stopped", entry_bar_t=APLUS_T), dict(state="triggered", entry_bar_t=APLUS_T)]
    for mode in ("within_state", "global"):
        monkeypatch.setattr(GC, "RS_FLOAT_SORT", mode)
        for c in cases:
            for fl in (2_500_000, None, 0):
                g = dict(c, setup=RS, _float_shares=fl)
                assert GT.order_key({"symbol": "X", "gajjala": g}) == before(g), (mode, c, fl)


def test_squeeze_still_reads_its_daily_doc_float():
    """🎾's stash keeps its second source (the daily doc) — a squeeze read with no ctx float still sorts by it."""
    reads = {s: R(RS, "forming", base={"bars": 0}) for s in ("AAA", "BBB")}
    st = _shared(reads, {}, daily=[_daily("AAA", 9_000_000), _daily("BBB", 2_000_000)])
    assert [t["symbol"] for t in GT.build(RS, now=NOW, store=st)["tiles"]] == ["BBB", "AAA"]


# ── ➖ the gap stays FIRST ───────────────────────────────────────────────────────────────────────────────────────
def test_fade_gap_first_then_float_then_todays_key():
    g = dict(fade("forming", 0.4), _ema_gap_pct=0.4, _bars_to_go=1)
    assert GT.order_key({"symbol": "X", "gajjala": dict(g, _float_shares=2e6)})[:3] == (GT._PRE_BREAK_RANK, 0.4, 2e6)
    assert GT.order_key({"symbol": "X", "gajjala": dict(g, _float_shares=None)})[:3] == (GT._PRE_BREAK_RANK, 0.4, INF)


@pytest.mark.parametrize("mode", GC.HF_EMA_SORTS)
def test_NEGATIVE_a_smaller_float_with_a_larger_gap_stays_below(mode, monkeypatch):
    monkeypatch.setattr(GC, "HF_EMA_SORT", mode)
    reads = {"TINY": fade("forming", 2.0), "HUGE": fade("forming", 0.2)}
    assert syms(reads, {"TINY": 100_000, "HUGE": 90_000_000}, HF) == ["HUGE", "TINY"]


@pytest.mark.parametrize("mode", GC.HF_EMA_SORTS)
def test_fade_equal_gaps_fall_to_the_float(mode, monkeypatch):
    monkeypatch.setattr(GC, "HF_EMA_SORT", mode)
    reads = {"AAA": fade("forming", 0.3), "BBB": fade("forming", 0.3), "CCC": fade("forming", 0.3)}
    assert syms(reads, {"AAA": 8e6, "BBB": 3e6}, HF) == ["BBB", "AAA", "CCC"]


def test_fade_within_state_and_global_put_the_float_right_after_the_gap(monkeypatch):
    g = dict(fade("partial", 0.7, missed=["k2"]), _ema_gap_pct=0.7, _float_shares=5e6)
    monkeypatch.setattr(GC, "HF_EMA_SORT", "within_state")
    assert GT.order_key({"symbol": "X", "gajjala": g})[:3] == (4, 0.7, 5e6)
    monkeypatch.setattr(GC, "HF_EMA_SORT", "global")
    assert GT.order_key({"symbol": "X", "gajjala": g})[:3] == (0, 0.7, 5e6)


def test_fade_rung_cards_take_the_float_like_every_setup():
    """pre_break rung cards carry no gap key — they take the float after the state rank (the 🎾 way)."""
    reads = {"BIG": fade("aplus", 0.1, entry_bar_t="2026-10-13 10:30", broke=True),
             "LOW": fade("aplus", 3.0, entry_bar_t="2026-10-13 10:00", broke=True),
             "FRM": fade("forming", 0.05)}
    assert syms(reads, {"BIG": 9e6, "LOW": 1e6, "FRM": 1e5}, HF) == ["LOW", "BIG", "FRM"]


# ── a setup NOT in the tuple ─────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("setup", GC.SETUPS)
def test_NEGATIVE_a_setup_outside_the_tuple_keeps_todays_key(setup, monkeypatch):
    monkeypatch.setattr(GC, "FLOAT_SORT_SETUPS", tuple(s for s in GC.SETUPS if s != setup))
    g = {"setup": setup, "state": "aplus", "entry_bar_t": APLUS_T, "_float_shares": 1}
    assert GT.order_key({"symbol": "X", "gajjala": g}) == (0, NEWEST, 0.0, "X")
    if setup != HF:
        reads = {s: R(setup, "forming", base={"bars": 0}) for s in ("AAA", "BBB")}
        assert syms(reads, {"AAA": 9e6, "BBB": 1e6}, setup) == ["AAA", "BBB"]


def test_NEGATIVE_a_fade_outside_the_tuple_keeps_the_gap_key_only(monkeypatch):
    monkeypatch.setattr(GC, "FLOAT_SORT_SETUPS", tuple(s for s in GC.SETUPS if s != HF))
    g = dict(fade("forming", 0.4), _ema_gap_pct=0.4, _bars_to_go=1, _float_shares=2e6)
    assert GT.order_key({"symbol": "X", "gajjala": g}) == (GT._PRE_BREAK_RANK, 0.4) + GT._state_key(g, "X")


def test_NEGATIVE_no_stash_keeps_todays_key_for_every_setup():
    """The cross-setup focus pick builds its key without the stash → today's key, every setup."""
    for setup in GC.SETUPS:
        g = {"setup": setup, "state": "partial", "missed": ["k2"]}
        assert GT.order_key({"symbol": "X", "gajjala": g}) == GT._state_key(g, "X"), setup


# ── "global" mode ────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("setup", GC.FLOAT_SORT_SETUPS)
def test_global_mode_puts_the_float_above_the_state_rank(setup, monkeypatch):
    monkeypatch.setattr(GC, "RS_FLOAT_SORT", "global")
    if setup == HF:                                     # ➖: the gap stays first; its rung cards take the float on top
        reads = {"APL": fade("aplus", 0.1, entry_bar_t="2026-10-13 10:20", broke=True),
                 "TRG": fade("triggered", 0.1, entry_bar_t="2026-10-13 10:25", broke=True)}
    else:
        reads = {"APL": R(setup, "aplus", entry_bar_t="2026-10-13 10:20", broke=True),
                 "FRM": R(setup, "forming", base={"bars": 0})}
    low = "TRG" if setup == HF else "FRM"
    assert syms(reads, {"APL": 9_000_000, low: 1_000_000}, setup) == [low, "APL"]
    monkeypatch.setattr(GC, "RS_FLOAT_SORT", "within_state")
    assert syms(reads, {"APL": 9_000_000, low: 1_000_000}, setup) == ["APL", low]      # NEGATIVE: state first


# ── the stash: ONE source, no new read, never served ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("setup", NON_FADE[:-1] if NON_FADE[-1] == RS else NON_FADE)
def test_stash_is_the_float_chips_read_and_no_daily_doc_is_read(setup, monkeypatch):
    reads = {s: R(setup, "forming", base={"bars": 0}) for s in ("AAA", "BBB")}
    st = _shared(reads, {"AAA": 9_000_000}, daily=[_daily("BBB", 1_000_000)])
    calls = []
    real = st.get_daily
    monkeypatch.setattr(st, "get_daily", lambda *a, **k: calls.append(a) or real(*a, **k))
    out = GT.build(setup, now=NOW, store=st)
    assert calls == []                                          # the non-🎾 card adds ZERO get_daily reads
    assert [t["symbol"] for t in out["tiles"]] == ["AAA", "BBB"]  # NEGATIVE: BBB's daily doc is not its source
    chip = {t["symbol"]: t["gajjala"]["chips"]["float"] for t in out["tiles"]}
    assert chip["AAA"]["shares"] == 9_000_000 and chip["BBB"] is None   # the chip shows exactly what sorted


def test_squeeze_get_daily_count_is_unchanged():
    """🎾 reads its daily doc once per carded name — as before (no new read on any sub)."""
    reads = {s: R(RS, "forming", base={"bars": 0}) for s in ("AAA", "BBB", "CCC")}
    st = _shared(reads, {})
    calls = []
    real = st.get_daily
    st.get_daily = lambda *a, **k: calls.append(a[1]) or real(*a, **k)
    GT.build(RS, now=NOW, store=st)
    assert sorted(calls) == ["AAA", "BBB", "CCC"]


@pytest.mark.parametrize("setup", GC.FLOAT_SORT_SETUPS)
def test_stash_never_reaches_a_served_tile(setup):
    reads = {s: R(setup, "forming", base={"bars": 0}) for s in ("AAA", "BBB")}
    if setup == HF:
        reads = {s: fade("forming", 0.3) for s in reads}
    out = GT.build(setup, now=NOW, store=_shared(reads, {"AAA": 9e6, "BBB": 1e6}))
    assert out["tiles"]
    for t in out["tiles"]:
        assert "_float_shares" not in json.dumps(t)
        assert not [k for k in t["gajjala"] if k.startswith("_")]


def test_suspect_float_is_unknown_on_every_setup(monkeypatch):
    monkeypatch.setattr(GC, "FLOAT_SUSPECT_POLICY", "ineligible")
    docs = [read_doc("SUS", {BF: R(BF, "forming", base={"bars": 0})}, ctx=_ctx(1e6, "float_exceeds_shares_out")),
            read_doc("OKK", {BF: R(BF, "forming", base={"bars": 0})}, ctx=_ctx(8e6))]
    st = store_with(reads=docs, scans=[scan_doc("SUS"), scan_doc("OKK")], passes=[latest()])
    assert [t["symbol"] for t in GT.build(BF, now=NOW, store=st)["tiles"]] == ["OKK", "SUS"]


# ── the variants follow (shared order_key / setup_tile — no special case) ────────────────────────────────────────
@pytest.mark.parametrize("v", (V.GG1, V.GGA), ids=("gg1_1min", "gga_audited"))
@pytest.mark.parametrize("setup", NON_FADE)
def test_one_minute_and_audited_serve_the_same_float_order(v, setup):
    reads = {s: R(setup, "forming", base={"bars": 0}) for s in ("AAA", "BBB", "CCC")}
    floats = {"AAA": 9e6, "BBB": 2e6}
    want = syms(reads, floats, setup)
    assert want == ["BBB", "AAA", "CCC"]
    assert syms(reads, floats, setup, v=v) == want


# ── NEGATIVES: ☀️ / 🌙 / 🧠 never move ─────────────────────────────────────────────────────────────────────────
def _pm_with_reads(reads=()):
    """tests/test_gajjala_tab._pm_store's day (BIGV 9M pm volume, BIGC 2M, CARY carried) + read docs."""
    scans = [scan_doc("BIGV", sessions={"premarket": True, "rth": True}), scan_doc("BIGC", sessions={"premarket": True}),
             scan_doc("RTHO", sessions={"rth": True})]
    levels = {"BIGV": {"volume": 9e6, "high": 4.6, "low": 3.2, "last": 4.2},
              "BIGC": {"volume": 2e6, "high": 5.8, "low": 3.1, "last": 5.7},
              "RTHO": {"volume": 9e9, "high": 9.0, "low": 1.0, "last": 5.0}}
    carry = [{"_id": PREV.isoformat(), "date": PREV.isoformat(), "pass_at": utc(20, 1, PREV),
              "names": {"CARY": {"ah_move_pct": 14.0, "ah_last": 2.0, "reg_close": 1.75}}}]
    return store_with(reads=list(reads), scans=scans, carry=carry,
                      passes=[latest(premarket={"pm_levels": levels})])


def test_NEGATIVE_premarket_keeps_its_volume_order_with_floats_on_file():
    assert [t["symbol"] for t in GT.build("premarket", now=NOW, store=_pm_store())["tiles"]] == ["BIGV", "BIGC", "CARY"]
    reads = [read_doc("BIGV", {BF: R(BF, "forming")}, ctx=_ctx(90e6)),        # the biggest float on the most volume
             read_doc("BIGC", {BF: R(BF, "forming")}, ctx=_ctx(1e6))]
    out = GT.build("premarket", now=NOW, store=_pm_with_reads(reads))
    assert [t["symbol"] for t in out["tiles"]] == ["BIGV", "BIGC", "CARY"]
    out = GT.build("premarket", sort="change", now=NOW, store=_pm_with_reads(reads))
    assert [t["symbol"] for t in out["tiles"]] == ["BIGC", "BIGV", "CARY"]


def test_NEGATIVE_postmarket_keeps_its_ah_gain_order():
    out = GT.build("postmarket", now=utc(19, 58), store=_post_store())
    assert [t["symbol"] for t in out["tiles"]] == ["HIGG", "LOWG"]


def test_NEGATIVE_potential_sub_keeps_potential_order_key(monkeypatch):
    """🧠 tiles keep potential.order_key (its own float tell, S8 21:04 — unchanged): the same order with the
    2026-11-09 tuple emptied, i.e. tab.order_key never orders that sub."""
    reads = {s: R(BF, "forming", ready=True, base={"bars": 1}) for s in ("AAA", "BBB", "CCC")}
    floats = {"AAA": 9e6, "BBB": 5e6, "CCC": 1e6}
    now = syms(reads, floats, GC.POTENTIAL_SUB)
    monkeypatch.setattr(GC, "FLOAT_SORT_SETUPS", ())
    assert syms(reads, floats, GC.POTENTIAL_SUB) == now == ["CCC", "BBB", "AAA"]
