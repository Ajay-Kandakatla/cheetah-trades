"""➖ 9/21 EMA rank on the Horizontal Fade sub, all three tabs (SPEC gg-zones §3.4 / WP be-zones-rank, 2026-11-08).

Ajay 2026-11-08, verbatim: "On the horizonal fade I need a ranking in horizontal fade when the stock 9 EMA and 21 EMA
are converging or close to converge on all tabs".

tab.order_key: a ➖ card built by setup_tile carries `_ema_gap_pct` (the k6_merge number, parsed off its served value)
→ GC.HF_EMA_SORT "pre_break" (built, MINE): forming AND partial ranked together by the gap ascending, unknown last;
A+ / held / triggered / stopped keep today's key on top. [C3] A snapshot — "closest to merged", never "converging".
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_tab import NOW, R, latest, read_doc, scan_doc, store_with

HF, BF, KF, VCP, RS = "horizontal_fade", "bull_flag", "kiss_fly", "intraday_vcp", "reversal_squeeze"
GGA_OWN = (ST.ALERTS, ST.STATE, ST.LEDGER, ST.OVERLAY, ST.EXITS)
CONST_LINES = Path(GC.__file__).read_text(encoding="utf-8").splitlines()


def merge_row(gap, ok=None):
    """The k6_merge criterion exactly as detectors._fade_checks serves it ("EMAs 1.88% apart" / "EMAs —% apart")."""
    value = "EMAs —% apart" if gap is None else f"EMAs {gap:.2f}% apart"
    if ok is None:
        ok = gap is not None and gap <= GC.K6_MERGE_PCT
    return {"key": "k6_merge", "label": "K6 merged", "ok": ok, "value": value, "need": ""}


def fade(state, gap, **kw):
    crit = [{"key": "k3_vol", "label": "K3", "ok": True, "value": "", "need": ""}, merge_row(gap)]
    r = R(HF, state, base={"bars": 3}, criteria=crit, **kw)
    return r


def _shared(reads):
    return store_with(reads=[read_doc(s, {r["setup"]: r}) for s, r in reads.items()],
                      scans=[scan_doc(s) for s in reads], passes=[latest()])


def _store(reads, v=None):
    if v is V.GG1:
        own = {n: FakeColl() for n in ST.OWN}
        own[ST.READS] = FakeColl([read_doc(s, {r["setup"]: r}) for s, r in reads.items()])
        own[ST.PASSES] = FakeColl([latest()])
        return ST.GajjalaStore(colls=own, variant=V.GG1, shared=_shared(reads))
    if v is V.GGA:
        return ST.GajjalaStore(colls={n: FakeColl() for n in GGA_OWN}, variant=V.GGA, shared=_shared(reads))
    return _shared(reads)


def syms(reads, sub=HF, v=None):
    out = GT.build(sub, now=NOW, store=_store(reads, v), variant=v)
    return [t["symbol"] for t in out["tiles"]]


# ── the number ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_gap_round_trips_off_the_detector_value():
    """The parsed number IS the detector's own print (2 dp) — a reworded value would break this pin loudly."""
    r = D.fade_on(FX.hf_frame(gap_frac=0.0051))
    assert GT._ema_gap_pct(r) == 0.51
    merged = D.fade_on(FX.hf_frame())
    assert GT._ema_gap_pct(merged) <= GC.K6_MERGE_PCT
    part = D.fade_on(FX.hf_frame(gap_frac=0.0051, entry=None))                        # [C2] a FULL base, EMAs apart
    assert part["state"] == "partial" and part["missed"] == ["k6_merge"]
    assert GT._ema_gap_pct(part) == 0.51                                               # partial keeps its number


def test_NEGATIVE_unknown_gaps_are_none():
    assert GT._ema_gap_pct({"criteria": [merge_row(None)]}) is None                    # EMAs warming
    assert GT._ema_gap_pct({"criteria": [{"key": "k3_vol", "ok": True, "value": "EMAs 0.10% apart"}]}) is None
    for junk in (None, {}, {"criteria": None}, {"criteria": ["x", 3]},
                 {"criteria": [{"key": "k6_merge", "value": "EMAs 1.2 % apart"}]},
                 {"criteria": [{"key": "k6_merge", "value": None}]}):
        assert GT._ema_gap_pct(junk) is None, junk


# ── the order ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_forming_fades_order_by_the_gap_unknown_last():
    """Symbols chosen against the gap order, so the gap is what moved them."""
    reads = {"AAA": fade("forming", None), "BBB": fade("forming", 2.61), "CCC": fade("forming", 1.88),
             "DDD": fade("forming", 0.42)}
    assert syms(reads) == ["DDD", "CCC", "BBB", "AAA"]


WORKED = {"A": fade("forming", 2.61),                                                  # a pending young base
          "B": fade("partial", 0.60, missed=["k6_merge"]),                             # full base, EMAs just apart
          "C": fade("aplus", 3.0, entry_bar_t="2026-10-13 10:25", broke=True)}         # rung


@pytest.mark.parametrize("mode,want", (("pre_break", ["C", "B", "A"]), ("within_state", ["C", "A", "B"]),
                                       ("global", ["B", "A", "C"])))
def test_the_worked_example_under_every_sort(monkeypatch, mode, want):
    """[C2][C6] §3.4 worked example, pinned under all three HF_EMA_SORT values."""
    assert mode in GC.HF_EMA_SORTS
    monkeypatch.setattr(GC, "HF_EMA_SORT", mode)
    assert syms(WORKED) == want


def test_pre_break_keeps_two_aplus_fades_newest_entry_first():
    """[C6] rung cards keep today's key byte-identical: the newer entry first whatever its gap."""
    reads = {"OLD": fade("aplus", 0.1, entry_bar_t="2026-10-13 10:00", broke=True),
             "NEW": fade("aplus", 3.0, entry_bar_t="2026-10-13 10:30", broke=True)}
    assert syms(reads) == ["NEW", "OLD"]
    for s, r in reads.items():
        t = {"symbol": s, "gajjala": dict(r, _ema_gap_pct=GT._ema_gap_pct(r))}
        assert GT.order_key(t) == GT._state_key(t["gajjala"], s)


def test_pre_break_stopped_below_every_pre_break_read_and_unknown_above_stopped():
    reads = {"STP": fade("stopped", 0.05, entry_bar_t="2026-10-13 10:30", broke=True),
             "UNK": fade("forming", None), "FAR": fade("partial", 4.0, missed=["k6_merge"]),
             "TRG": fade("triggered", 5.0, entry_bar_t="2026-10-13 10:10", broke=True)}
    assert syms(reads) == ["TRG", "FAR", "UNK", "STP"]


def test_pre_break_equal_gaps_fall_back_to_todays_key():
    """Equal gaps → today's key: ready forming, then forming, then partial."""
    reads = {"PAR": fade("partial", 0.3, missed=["k6_tight"]), "FRM": fade("forming", 0.3),
             "RDY": fade("forming", 0.3, ready=True)}
    assert syms(reads) == ["RDY", "FRM", "PAR"]


def test_the_rank_constant_is_defined_once_and_is_todays_ready_rank():
    assert GT._PRE_BREAK_RANK == GT._state_key({"state": "forming", "ready": True}, "X")[0]
    src = Path(GT.__file__).read_text(encoding="utf-8")
    assert len(re.findall(r"^_PRE_BREAK_RANK = ", src, re.M)) == 1


@pytest.mark.parametrize("v", (V.GG1, V.GGA), ids=("gg1", "gga"))
def test_gg1_and_gga_serve_the_same_fade_order_as_gg5(v, monkeypatch):
    reads = dict(WORKED, D=fade("forming", None), E=fade("forming", 0.2))
    for mode in GC.HF_EMA_SORTS:
        monkeypatch.setattr(GC, "HF_EMA_SORT", mode)
        assert syms(reads, v=v) == syms(reads), mode


# ── NEGATIVES: nothing else moves ─────────────────────────────────────────────────────────────────────────────────
def _other(setup, state, gap, **kw):
    return R(setup, state, base={"bars": 3}, criteria=[merge_row(gap)], **kw)


@pytest.mark.parametrize("setup", (BF, KF, VCP, RS))
def test_NEGATIVE_other_setup_subs_ignore_the_gap(setup, monkeypatch):
    """A k6_merge-looking row on another setup's read never reorders it (the stash is ➖-only)."""
    reads = {"AAA": _other(setup, "forming", 0.1), "BBB": _other(setup, "forming", 3.0),
             "CCC": _other(setup, "partial", 0.0, missed=["k3_vol"]),
             "DDD": _other(setup, "aplus", 9.0, entry_bar_t="2026-10-13 10:25", broke=True)}
    want = None
    for mode in GC.HF_EMA_SORTS:
        monkeypatch.setattr(GC, "HF_EMA_SORT", mode)
        got = syms(reads, sub=setup)
        want = want or got
        assert got == want, (setup, mode)
    assert want == ["DDD", "AAA", "BBB", "CCC"]                                        # today's §3.4.1 key


def test_NEGATIVE_the_potential_sub_order_is_never_the_gap(monkeypatch):
    """🧠 tiles are ordered by potential.order_key — the fade gap moves none of them, under any HF_EMA_SORT."""
    reads = {s: fade("forming", g, ready=True) for s, g in (("AAA", 3.0), ("BBB", 0.1), ("CCC", None))}
    flat = {s: fade("forming", 0.25, ready=True) for s in reads}
    base = syms(flat, sub=GC.POTENTIAL_SUB)
    assert sorted(base) == ["AAA", "BBB", "CCC"]
    for mode in GC.HF_EMA_SORTS:
        monkeypatch.setattr(GC, "HF_EMA_SORT", mode)
        assert syms(reads, sub=GC.POTENTIAL_SUB) == base, mode


def test_NEGATIVE_the_focus_pick_key_is_todays_key_for_a_fade():
    """The cross-setup focus pick (tab.py resolve) builds its key WITHOUT the stash → today's key byte-identical."""
    r = fade("partial", 0.2, missed=["k6_tight"])
    t = {"symbol": "X", "gajjala": dict(r, _last=4.0, _bars_to_go=3)}
    assert GT.order_key(t) == GT._state_key(t["gajjala"], "X")


def test_order_note_on_every_sub_and_variant():
    reads = {"AAA": fade("forming", 1.0)}
    for v in (None, V.GG1, V.GGA):
        st = _store(reads, v)
        for sub in GC.SETUPS:
            out = GT.build(sub, now=NOW, store=st, variant=v)
            want = {HF: GT.HF_ORDER_TEXT, RS: GT.RS_ORDER_TEXT}.get(sub, GT.VOL_ORDER_TEXT)   # 2026-11-09: every sub a word
            if sub in GC.RVOL_SORT_SETUPS:                       # UPDATED 2026-11-11 — 💋 rel volume first (its own word)
                want = GT.KF_ORDER_TEXT[GC.KF_EMA_SORT]
            assert "order_note" in out and out["order_note"] == want, (v, sub)
        for sub in ("premarket", "postmarket", "playbook"):
            assert GT.build(sub, now=NOW, store=st, variant=v).get("order_note") is None, (v, sub)


def test_the_order_word_says_closest_never_converging():
    """[C3] the gap is a snapshot at the read's ref bar — no direction word anywhere it is served."""
    assert GT.HF_ORDER_TEXT == "➖ 9 and 21 EMA closest to merged on top · then highest volume"   # 2026-11-09: + the volume key
    assert "closest" in GT.HF_ORDER_TEXT and "converg" not in GT.HF_ORDER_TEXT.lower()
    assert "HF_ORDER_TEXT" in GT.__all__


@pytest.mark.parametrize("v", (None, V.GG1, V.GGA), ids=("gg5", "gg1", "gga"))
def test_NEGATIVE_no_private_key_reaches_a_served_fade_tile(v):
    out = GT.build(HF, now=NOW, store=_store(WORKED, v), variant=v)
    assert len(out["tiles"]) == 3
    for t in out["tiles"]:
        assert "_ema_gap_pct" not in json.dumps(t)
        assert not [k for k in t["gajjala"] if k.startswith("_")]


# ── the constant ─────────────────────────────────────────────────────────────────────────────────────────────────
def _line(name):
    return next(ln for ln in CONST_LINES if ln.startswith(name + " = "))


def test_hf_ema_sort_is_mine_well_formed_and_not_a_cheetah_default():
    assert GC.HF_EMA_SORT in GC.HF_EMA_SORTS and GC.HF_EMA_SORT == "pre_break"
    assert GC.HF_EMA_SORTS == ("pre_break", "within_state", "global")
    line = _line("HF_EMA_SORT")
    assert line.split("#", 1)[1].strip().startswith("MINE") and "HIS CALL" in line
    assert "converge on all tabs" in line                                              # his words, dated
    assert "HF_EMA_SORT" not in GC.CHEETAH_DEFAULTS and "HF_EMA_SORTS" not in GC.CHEETAH_DEFAULTS
