"""🌀 Gajjala's Intraday VCP — the sub cards only names with at least K4's contractions (BUILD_SPEC18, 2026-10-20).

Ajay 2026-10-20 (verbatim): "Hey, Can you actually show me stocks only that have 2 contractions. in Gajjallas I don't
see a point of seeing the ones with one contraction do you?"

One switch (constants.VCP_LIST_FROM_K4) and one number (K4_VCP_MIN_CYCLES, read at call time): a 🌀 read with fewer
contractions is COUNTED on the counts line, never carded, never a 🧠 potential; the served `list_note` says how many.
A read stored without `cycles` lists as before (fail-open). NEGATIVES: the switch off restores the old board; every
other setup is untouched; a bool is never a count; the A+ read and the counts never move.
"""
from __future__ import annotations

import re

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import tab as GT
from supply_demand import rules_info as RI
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_tab import NOW, R, latest, read_doc, scan_doc, store_with

V = "intraday_vcp"
B_WORD = re.compile("b" + "ounc", re.I)
M = GC.K4_VCP_MIN_CYCLES

# the hand fixture day: every 🌀 shape the live tab showed on 2026-10-20 (F2)
READS = {
    "ONEF": R(V, "forming", cycles=M - 1, base={"bars": 2}, reason=f"{M - 1} of {M} cycles"),
    "ONEP": R(V, "partial", cycles=M - 1, missed=["k4_cycles"], base={"bars": 3}),
    "TWOB": R(V, "partial", cycles=M, grade=GC.VCP_B_GRADE, missed=["k7_ratio"], base={"bars": 4}),
    "THREE": R(V, "partial", cycles=M + 1, missed=["k3_vol"], base={"bars": 6}),
    "NOKEY": R(V, "partial", missed=["k4_cycles"], base={"bars": 3}),             # stored by the previous code
    "ZERO": R(V, "forming", cycles=0, base=None, reason="no pullback yet — the leg is still printing highs"),
    "INV": R(V, "invalid", cycles=M - 1, reason="lower low — not contracting up"),
}
LISTED = {"TWOB", "THREE", "NOKEY"}
HELD = {"ONEF", "ONEP", "ZERO"}                     # TILE_STATES reads with fewer than K4's contractions


def _store(reads=None):
    reads = READS if reads is None else reads
    docs = [read_doc(s, {V: r}) for s, r in reads.items()]
    return store_with(reads=docs, scans=[scan_doc(s) for s in reads], passes=[latest()])


def _syms(out):
    return {t["symbol"] for t in out["tiles"]}


def _sub_count(out, key=V):
    return next(s["count"] for s in out["subs"] if s["key"] == key)


# ── the helper and the switch ────────────────────────────────────────────────────────────────────────────────────
def test_helper_follows_the_switch_and_k4_at_call_time(monkeypatch):
    assert GC.VCP_LIST_FROM_K4 is True and GC.vcp_list_min_cycles() == GC.K4_VCP_MIN_CYCLES
    monkeypatch.setattr(GC, "K4_VCP_MIN_CYCLES", M + 1)
    assert GC.vcp_list_min_cycles() == M + 1                        # no second number: K4 IS the rule
    monkeypatch.setattr(GC, "VCP_LIST_FROM_K4", False)
    assert GC.vcp_list_min_cycles() is None


def test_vcp_listed_rule():
    assert GT._vcp_listed(V, {"cycles": M}) is True
    assert GT._vcp_listed(V, {"cycles": M + 1}) is True
    assert GT._vcp_listed(V, {"cycles": M - 1}) is False
    assert GT._vcp_listed(V, {"cycles": 0}) is False


def test_NEGATIVE_vcp_listed_fails_open_and_never_judges_another_setup(monkeypatch):
    assert GT._vcp_listed(V, {}) is True                            # stored without the key → as before
    assert GT._vcp_listed(V, {"cycles": None}) is True
    assert GT._vcp_listed(V, {"cycles": False}) is True             # a bool is never a count
    assert GT._vcp_listed(V, {"cycles": True}) is True
    assert GT._vcp_listed(V, {"cycles": "1"}) is True
    assert GT._vcp_listed(V, None) is True
    for s in GC.SETUPS:
        if s != V:
            assert GT._vcp_listed(s, {"cycles": 0}) is True, s
    monkeypatch.setattr(GC, "VCP_LIST_FROM_K4", False)
    assert GT._vcp_listed(V, {"cycles": 0}) is True


# ── the 🌀 sub ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_vcp_sub_cards_only_reads_with_k4_contractions():
    out = GT.build(V, now=NOW, store=_store())
    assert _syms(out) == LISTED
    assert _sub_count(out) == len(out["tiles"]) == len(LISTED)      # the strip agrees with the cards
    for t in out["tiles"]:
        assert "cycles" in t["gajjala"], t["symbol"]                 # every 🌀 card serves its count (critic 2026-10-20)
        n = t["gajjala"]["cycles"]
        if t["symbol"] == "NOKEY":
            assert n is None                                        # stored by the previous code — carded, no count
        else:
            assert isinstance(n, int) and not isinstance(n, bool) and n >= M, t["symbol"]


def _pm_scan(sym):
    return scan_doc(sym, sessions={"premarket": True, "rth": True}, tape="premarket", volume=3e6)


def _watch_syms(out):
    w = out.get("watch") or {}
    found = set()
    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("symbol"), str):
                found.add(o["symbol"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(w)
    return found


def test_a_held_back_name_still_counts_as_structure_on_the_watch_line():
    """D3 (critic 2026-10-20 M6): a one-contraction 🌀 name is held off the cards, but it HAS structure — the 👀 "no
    structure yet" line must not list it even when it is a premarket mover. NEGATIVE: a premarket mover with no read at
    all IS on the line."""
    docs = [read_doc(s, {V: r}) for s, r in READS.items()]
    scans = [scan_doc(s) for s in READS] + [_pm_scan("ONEF"), _pm_scan("NOREAD")]
    out = GT.build("potential", now=NOW, store=store_with(reads=docs, scans=scans, passes=[latest()]))
    syms = _watch_syms(out)
    assert "NOREAD" in syms
    assert "ONEF" not in syms


def test_a_focus_link_never_opens_the_vcp_sub_for_a_held_back_name():
    """resolve_sub applies the same rule (critic 2026-10-20): a stored href for a one-contraction name resolves away
    from the 🌀 sub; NEGATIVE: a listed name's focus still resolves to it."""
    out = GT.build("", focus="ONEF", now=NOW, store=_store())
    assert out["sub"] != V and out["sub_resolved_from"] != "focus_read"
    out = GT.build("", focus="THREE", now=NOW, store=_store())
    assert out["sub"] == V and out["sub_resolved_from"] == "focus_read"
    out = GT.build("", focus="NOKEY", now=NOW, store=_store())
    assert out["sub"] == V and out["sub_resolved_from"] == "focus_read"     # fail-open, as the card is


def test_counts_line_still_counts_every_read():
    """Nothing disappears silently (D10): forming / partial / invalid count every read, carded or not."""
    out = GT.build(V, now=NOW, store=_store())
    c = out["counts"]
    assert c["forming"] == 2 and c["partial"] == 4 and c["invalid"] == 1
    assert c["listed"] == len(READS)


def test_list_note_carries_the_count_and_the_constant():
    out = GT.build(V, now=NOW, store=_store())
    k = len(HELD)
    assert out["list_note"] == (f"🌀 {k} with fewer than {M} contractions counted, not listed — his K4: a VCP needs "
                                f"at least {M} contractions, each tighter than the one before (S8 33:50)")
    assert out["list_note"] == GT.vcp_list_note(k)
    assert not B_WORD.search(out["list_note"])


def test_a_patched_k4_moves_the_cards_and_the_note(monkeypatch):
    monkeypatch.setattr(GC, "K4_VCP_MIN_CYCLES", M + 1)
    out = GT.build(V, now=NOW, store=_store())
    assert _syms(out) == {"THREE", "NOKEY"}
    assert f"{len(HELD) + 1} with fewer than {M + 1} contractions" in out["list_note"]


def test_NEGATIVE_no_list_note_off_the_vcp_sub():
    for sub in ("bull_flag", "kiss_fly", "horizontal_fade", "reversal_squeeze", "potential", "premarket",
                "postmarket", "playbook"):
        out = GT.build(sub, now=NOW, store=_store())
        assert out.get("list_note") is None, sub


def test_NEGATIVE_no_list_note_when_nothing_was_held_back():
    out = GT.build(V, now=NOW, store=_store({s: READS[s] for s in LISTED}))
    assert _syms(out) == LISTED and out["list_note"] is None
    assert GT.vcp_list_note(0) is None and GT.vcp_list_note(True) is None


def test_NEGATIVE_switch_off_cards_every_read_as_before(monkeypatch):
    on = GT.build(V, now=NOW, store=_store())
    monkeypatch.setattr(GC, "VCP_LIST_FROM_K4", False)
    off = GT.build(V, now=NOW, store=_store())
    assert _syms(off) == LISTED | HELD                              # every TILE_STATES read carded
    assert _sub_count(off) == len(off["tiles"]) == len(LISTED | HELD)
    assert off["list_note"] is None and GT.vcp_list_note(3) is None
    assert off["counts"] == on["counts"]                            # the counts never depended on the rule


def test_NEGATIVE_another_setup_is_never_held_back():
    """A bull-flag read carrying a stray low `cycles` is still carded — only the 🌀 sub has the rule."""
    reads = {"AAA": R("bull_flag", "forming", cycles=0, base={"bars": 1}),
             "BBB": R("bull_flag", "partial", cycles=1, missed=["k3_vol"])}
    docs = [read_doc(s, {"bull_flag": r}) for s, r in reads.items()]
    out = GT.build("bull_flag", now=NOW, store=store_with(reads=docs, scans=[scan_doc(s) for s in reads],
                                                          passes=[latest()]))
    assert _syms(out) == {"AAA", "BBB"} and out["list_note"] is None


# ── 🧠 potential_kind follows the same rule ──────────────────────────────────────────────────────────────────────
def _pr(setup=V, **kw):
    r = {"setup": setup, "state": GC.POTENTIAL_STATE, "ready": False, "base": {"bars": 2}, "variant": None,
         "grade": None}
    r.update(kw)
    return r


def test_potential_kind_one_contraction_is_never_a_potential():
    assert PT.potential_kind(_pr(cycles=M - 1)) is None
    assert PT.potential_kind(_pr(cycles=M - 1, ready=True)) is None
    assert PT.potential_kind(_pr(cycles=0)) is None


def test_potential_kind_two_contractions_building_or_armed():
    assert PT.potential_kind(_pr(cycles=M)) == GC.POTENTIAL_KINDS[1]
    assert PT.potential_kind(_pr(cycles=M, ready=True)) == GC.POTENTIAL_KINDS[0]
    assert PT.potential_kind(_pr(cycles=M + 1, ready=True)) == GC.POTENTIAL_KINDS[0]


def test_NEGATIVE_potential_kind_other_setups_and_old_reads_unaffected(monkeypatch):
    assert PT.potential_kind(_pr("kiss_fly", base={"bars": 1})) == GC.POTENTIAL_KINDS[1]
    assert PT.potential_kind(_pr("kiss_fly", base={"bars": 1}, cycles=0)) == GC.POTENTIAL_KINDS[1]
    assert PT.potential_kind(_pr()) == GC.POTENTIAL_KINDS[1]                    # no `cycles` key → as before
    assert PT.potential_kind(_pr(cycles=True)) == GC.POTENTIAL_KINDS[1]         # a bool is never a count
    assert PT.potential_kind(_pr(cycles=M, grade=GC.VCP_B_GRADE)) is None       # "B" stays never-a-potential
    monkeypatch.setattr(GC, "VCP_LIST_FROM_K4", False)
    assert PT.potential_kind(_pr(cycles=M - 1)) == GC.POTENTIAL_KINDS[1]         # switch off → as before


def test_potential_kind_on_real_detector_reads():
    one = D.intraday_vcp(FX.vcp_frame(FX.VCP_BARS[:11], entry=None))
    assert (one["state"], one["cycles"]) == ("forming", 1)
    assert PT.potential_kind(one) is None
    building = D.intraday_vcp(FX.vcp_frame(entry=None))
    assert building["cycles"] == M and PT.potential_kind(building) == GC.POTENTIAL_KINDS[1]
    armed = D.intraday_vcp(FX.vcp_frame(entry=None, after=[(10.125, 10.4375, 10.0, 10.375, 40_000)]))
    assert armed["cycles"] == M and PT.potential_kind(armed) == GC.POTENTIAL_KINDS[0]


def test_the_potential_sub_follows_the_rule(monkeypatch):
    reads = {"ONEF": READS["ONEF"], "TWOF": R(V, "forming", cycles=M, base={"bars": 3})}
    out = GT.build("potential", now=NOW, store=_store(reads))
    assert _syms(out) == {"TWOF"} and _sub_count(out, "potential") == 1
    monkeypatch.setattr(GC, "VCP_LIST_FROM_K4", False)
    out = GT.build("potential", now=NOW, store=_store(reads))
    assert _syms(out) == {"ONEF", "TWOF"}                            # NEGATIVE: switch off → as before


# ── ℹ️ the rules line ────────────────────────────────────────────────────────────────────────────────────────────
def _vcp_line():
    sec = RI.sections()["gajjala"]
    return next(p for p in sec["picks"] if p.startswith(RI._gg_label(V)))


def test_rules_line_carries_the_listing_clause():
    t = _vcp_line()
    assert ", carded from %d contractions (fewer are counted, not listed)" % M in t
    assert "≥%d contractions each ≤ %g×" % (M, GC.K7_CONTRACTION) in t        # the pinned K4/K7 clause intact


def test_NEGATIVE_rules_line_has_no_clause_with_the_switch_off(monkeypatch):
    monkeypatch.setattr(GC, "VCP_LIST_FROM_K4", False)
    t = _vcp_line()
    assert "carded from" not in t
    assert "≥%d contractions each ≤ %g×" % (M, GC.K7_CONTRACTION) in t
    assert not B_WORD.search(t)
