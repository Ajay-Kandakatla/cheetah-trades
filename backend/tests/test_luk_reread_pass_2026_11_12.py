"""🥇 Luk — step 13b, the board re-read (chart_maps/luk/run.py — luk realtime cards spec §3.2, WP-A, 2026-11-12).

Ajay 2026-11-12, verbatim: "Luks scan is not realtime I see all dated values can you make it realtime"

After the push gate, every card the board shows (the board's own engine: luk.tab.tiles_for + luk.tab._clip_focus over
today's docs with this pass's ring reads overlaid [C4]) plus today's 🥇 alert cards, minus the shortlist, is re-read on
the pass budget left. A re-read is DISPLAY ONLY: never handed to the push gate, never moves the 1-minute clock, and its
doc carries `refresh_only` + `cron_setups`, so `_carried` (the shortlist, what can ring) is unchanged. A re-read A+ whose
gate claim ids are both absent carries `not_rung` [C2]. The whole step sits in ONE try that re-raises `_Superseded` [C1].
NEGATIVES throughout. Reuses tests/test_luk_run.py's fakes.
"""
from __future__ import annotations

import copy
from datetime import date

import pytest

from chart_maps.gajjala import alerts as GA
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as GS
from chart_maps.luk import alerts as AL
from chart_maps.luk import bars as BA
from chart_maps.luk import constants as LC
from chart_maps.luk import detectors as DT
from chart_maps.luk import run as LR
from chart_maps.luk import screens as SC
from chart_maps.luk import store as ST
from chart_maps.luk import tab as TB
from chart_maps.luk.variant import LUK
from tests.test_luk_run import (DAY, FakeF, _aplus, _shadow_by_default, at, fake_deps, fake_steps,  # noqa: F401
                                mk_colls, mk_store)

D = date.fromisoformat(DAY)
ORH = "opening_range_high"
PBR = "pullback_reversal"
IDP = "inside_day_pdh"
RING = ("AAA", "BBB")                                    # the fake shortlist = the fake universe
OLD = at("09:31")
REAL_GATE = AL.run_pass                                  # captured once: a second spy never wraps the first


def _r(setup, state, **kw):
    return {setup: dict({"setup": setup, "state": state, "frame": "1m", "entry_bar_t": kw.pop("entry", None),
                         "trigger": 10.0, "stop": 9.5}, **kw)}


def seed(colls, sym, setups, *, when=OLD, **extra):
    colls[GS.READS].docs[f"{DAY}|{sym}"] = dict({"_id": f"{DAY}|{sym}", "date": DAY, "symbol": sym, "setups": setups,
                                                 "updated_at": when, "at": when}, **extra)


def alert_doc(colls, _id, sym, setup, state, at_iso):
    colls[GS.ALERTS].docs[_id] = {"_id": _id, "date": DAY, "symbol": sym, "setup": setup, "state": state,
                                  "at": at_iso}


def steps(monkeypatch, *, ring=None, reread=None, t1=at("09:35"), rt1=None, fail=(), raise_read=(),
          raise_second=False):
    """fake_steps + a frames_for / read_all that know the symbol: ring names read `ring`, every other name `reread`."""
    spies = fake_steps(monkeypatch, t1=t1, t5=t1)
    spies["read_syms"] = []

    def frames_for(names, session, now, *, load_day, budget_sec, stats):
        spies["frames_for"].append({"names": list(names), "budget_sec": budget_sec})
        if raise_second and len(spies["frames_for"]) == 2:
            raise RuntimeError("second frames_for")
        out = {}
        for s in names:
            load_day(s, D, force=True, include_premarket=True, include_afterhours=True)
            if s in fail:
                stats["failed"] = stats.get("failed", 0) + 1
                continue
            F = FakeF(t1 if s in RING else (rt1 or t1), t1 if s in RING else (rt1 or t1))
            F.sym = s
            out[s] = F
            stats["loaded"] = stats.get("loaded", 0) + 1
        return out

    def read_all(F, facts, iso, *, prev_through_1m=None):
        spies["read_all"].append(prev_through_1m)
        spies["read_syms"].append((F.sym, facts, prev_through_1m))
        if F.sym in raise_read:
            raise RuntimeError("detector")
        return copy.deepcopy(((ring if F.sym in RING else reread) or {}).get(F.sym) or {})

    monkeypatch.setattr(BA, "frames_for", frames_for)
    monkeypatch.setattr(DT, "read_all", read_all)
    return spies


def spy_gate(monkeypatch) -> list:
    seen: list = []

    def spy(reads, *a, **k):
        seen.append(copy.deepcopy(reads))
        return REAL_GATE(reads, *a, **k)
    monkeypatch.setattr(AL, "run_pass", spy)
    return seen


def run(st, monkeypatch=None, hhmm="09:36", sec=7, **kw):
    return LR.run_pass(at(hhmm, sec), store=st, deps=kw.pop("deps", None) or fake_deps(), **kw)


def doc(colls, sym):
    return colls[GS.READS].docs[f"{DAY}|{sym}"]


# ── positives ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_card_read_at_an_earlier_pass_is_re_read_this_pass(monkeypatch):
    st, colls = mk_store()
    seed(colls, "CCC", _r(PBR, "forming"))
    steps(monkeypatch, reread={"CCC": _r(PBR, "triggered", entry=f"{DAY} 09:34")})
    out = run(st)
    d = doc(colls, "CCC")
    assert d["updated_at"] == at("09:36", 7) and d["refresh_only"] is True
    assert d["cron_setups"] == _r(PBR, "forming") and d["setups"] == _r(PBR, "triggered", entry=f"{DAY} 09:34")
    assert d["not_rung"] == [] and "on_demand" not in d
    rf = out["refresh"]
    assert rf["on"] is True and rf["asked"] == ["CCC"] and rf["read_n"] == 1 and rf["not_read"] == []
    assert rf["skipped"] is None and set(rf) == set(LR.REFRESH_KEYS)
    assert out["n_read"] == 2 and "CCC" not in out["shortlist"]["symbols"]     # NEGATIVE: never a ring read


def test_budget_order_the_shortlist_first_then_the_board_interleaved_then_the_alert_names(monkeypatch):
    st, colls = mk_store()
    seed(colls, "P1", _r(PBR, "aplus", entry=f"{DAY} 09:33"))
    seed(colls, "P2", _r(PBR, "forming"))
    seed(colls, "O1", _r(ORH, "triggered", entry=f"{DAY} 09:32"))
    seed(colls, "I1", _r(IDP, "listed"))
    alert_doc(colls, "a1", "Z1", ORH, "pushed", f"{DAY}T09:33:00")
    alert_doc(colls, "a2", "Z2", ORH, "shadow", f"{DAY}T09:40:00")
    alert_doc(colls, "a3", "P1", PBR, "pushed", f"{DAY}T09:34:00")             # already a board name: listed once
    spies = steps(monkeypatch)
    out = run(st)
    assert [c["names"] for c in spies["frames_for"]] == [list(RING), ["P1", "O1", "I1", "P2", "Z2", "Z1"]]
    assert 0 < spies["frames_for"][1]["budget_sec"] <= LC.LUK_PASS_BUDGET_SEC - LC.LUK_GRADE_BUDGET_SEC
    assert out["refresh"]["board_n"] == 6 and out["refresh"]["asked_n"] == 6
    assert out["calls"]["minute_today"] == len(RING) + 6                         # the re-read is counted


# ── NEGATIVE: the gate never sees a re-read ──────────────────────────────────────────────────────────────────────
def test_NEGATIVE_the_push_gate_never_sees_a_re_read(monkeypatch):
    seen = spy_gate(monkeypatch)
    st, colls = mk_store()
    seed(colls, "CCC", _r(ORH, "forming"))
    steps(monkeypatch, ring={"AAA": _aplus()}, reread={"CCC": _r(ORH, "aplus", entry=f"{DAY} 09:35")})
    out = run(st)
    assert len(seen) == 1 and set(seen[0]) == {"AAA", "BBB"}
    assert not [k for k in colls[GS.ALERTS].docs if "CCC" in k]                  # no claim for the re-read A+
    assert out["aplus"] == [{"symbol": "AAA", "setup": ORH, "entry_bar_t": f"{DAY} 09:35"}]
    assert out["states"]["aplus"] == 1 and doc(colls, "CCC")["setups"][ORH]["state"] == "aplus"


# ── [C2] the "did not ring" flag ─────────────────────────────────────────────────────────────────────────────────
def _pill(monkeypatch, prep=None):
    st, colls = mk_store()
    seed(colls, "CCC", _r(ORH, "forming"))
    if prep:
        prep(st, colls)
    steps(monkeypatch, ring={"AAA": _aplus()}, reread={"CCC": _r(ORH, "aplus", entry=f"{DAY} 09:35")})
    out = run(st)
    return out, colls


def test_C2_a_re_read_aplus_with_no_claim_doc_is_flagged_not_rung(monkeypatch):
    out, colls = _pill(monkeypatch)
    assert doc(colls, "CCC")["not_rung"] == [ORH]
    assert out["refresh"]["aplus_not_rung"] == [f"CCC|{ORH}"]


def test_NEGATIVE_C2_a_shadow_claim_means_it_rang(monkeypatch):
    out, colls = _pill(monkeypatch, lambda st, c: alert_doc(c, GA.shadow_key(D, "CCC", ORH, LUK), "CCC", ORH,
                                                            "shadow", f"{DAY}T09:33:00"))
    assert doc(colls, "CCC")["not_rung"] == [] and out["refresh"]["aplus_not_rung"] == []


def test_NEGATIVE_C2_a_live_claim_settled_failed_means_it_rang(monkeypatch):
    out, colls = _pill(monkeypatch, lambda st, c: alert_doc(c, GA.claim_key(D, "CCC", ORH, LUK), "CCC", ORH,
                                                            "failed", f"{DAY}T09:33:00"))
    assert doc(colls, "CCC")["not_rung"] == [] and out["refresh"]["aplus_not_rung"] == []


def test_C2_only_a_late_refusal_doc_is_still_not_rung(monkeypatch):
    out, colls = _pill(monkeypatch, lambda st, c: alert_doc(c, GA.claim_key(D, "CCC", ORH, LUK) + "#late", "CCC",
                                                            ORH, "late", f"{DAY}T09:33:00"))
    assert doc(colls, "CCC")["not_rung"] == [ORH]


def test_NEGATIVE_C2_no_alerts_handle_fails_closed(monkeypatch):
    out, colls = _pill(monkeypatch, lambda st, c: setattr(st, "alerts_coll", lambda: None))
    assert doc(colls, "CCC")["not_rung"] == [] and out["refresh"]["aplus_not_rung"] == []


def test_NEGATIVE_C2_a_raising_claim_read_fails_closed(monkeypatch):
    def prep(st, c):
        def boom(*a, **k):
            raise RuntimeError("mongo down")
        c[GS.ALERTS].find_one = boom
    out, colls = _pill(monkeypatch, prep)
    assert doc(colls, "CCC")["not_rung"] == [] and out["refresh"]["aplus_not_rung"] == []


def test_NEGATIVE_C2_rang_unit():
    coll = mk_colls()[GS.ALERTS]
    assert LR._rang(None, D, "CCC", ORH) is None
    assert LR._rang(coll, D, "CCC", ORH) is False
    coll.docs["x"] = {"_id": GA.claim_key(D, "CCC", ORH, LUK) + "#late"}
    assert LR._rang(coll, D, "CCC", ORH) is False                                # a refusal never matches
    coll.docs["y"] = {"_id": GA.claim_key(D, "CCC", PBR, LUK)}
    assert LR._rang(coll, D, "CCC", ORH) is False                                # another setup's claim
    coll.docs["z"] = {"_id": GA.claim_key(D, "CCC", ORH, LUK)}
    assert LR._rang(coll, D, "CCC", ORH) is True


def test_NEGATIVE_C2_a_ring_read_aplus_never_carries_not_rung(monkeypatch):
    out, colls = _pill(monkeypatch)
    a = doc(colls, "AAA")
    assert "not_rung" not in a and "refresh_only" not in a and "cron_setups" not in a


# ── NEGATIVE: the switch ─────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_switch_off_the_ring_reads_gate_input_and_clock_are_byte_equal(monkeypatch):
    def once(on):
        monkeypatch.setattr(LC, "LUK_REREAD_SHOWN", on)
        seen = spy_gate(monkeypatch)
        st, colls = mk_store()
        seed(colls, "CCC", _r(ORH, "forming"))
        spies = steps(monkeypatch, ring={"AAA": _aplus()}, reread={"CCC": _r(ORH, "aplus", entry=f"{DAY} 09:35")})
        out = run(st)
        return out, colls, seen, spies
    on_out, on_c, on_seen, _ = once(True)
    off_out, off_c, off_seen, off_spies = once(False)
    assert len(off_spies["frames_for"]) == 1
    assert off_out["refresh"] == LR._refresh_skipped(LR.SKIP_REFRESH_OFF)
    for s in RING:
        assert doc(on_c, s) == doc(off_c, s)
    def claims(c):                                                               # claimed_at = the wall clock
        return {k: {f: v for f, v in d.items() if f != "claimed_at"} for k, d in c[GS.ALERTS].docs.items()}
    assert on_seen == off_seen and claims(on_c) == claims(off_c) and claims(on_c)
    assert (on_c[GS.STATE].docs[LC.LUK_STATE_BARS_THROUGH] == off_c[GS.STATE].docs[LC.LUK_STATE_BARS_THROUGH])
    assert doc(off_c, "CCC")["updated_at"] == OLD and "refresh_only" not in doc(off_c, "CCC")


# ── NEGATIVE: _carried and the clock ─────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_carried_is_unchanged_by_a_re_read(monkeypatch):
    st, colls = mk_store()
    seed(colls, "CCC", _r(PBR, "forming"))
    seed(colls, "DDD", _r(PBR, "aplus", entry=f"{DAY} 09:30"))                  # not carried before
    before = LR._carried(st, D)
    steps(monkeypatch, reread={"CCC": _r(PBR, "stopped", entry=f"{DAY} 09:34"),
                               "DDD": _r(PBR, "forming")})
    run(st)
    assert doc(colls, "CCC")["setups"][PBR]["state"] == "stopped"
    assert LR._carried(st, D) == before and "CCC" in before and "DDD" not in before
    spies = steps(monkeypatch, reread={"CCC": _r(PBR, "stopped", entry=f"{DAY} 09:34"), "DDD": _r(PBR, "forming")})
    run(st, hhmm="09:41")
    assert spies["shortlist"] == [before]                                        # the next shortlist's carry set
    assert doc(colls, "CCC")["cron_setups"] == _r(PBR, "forming")               # a re-read of a re-read keeps it


def test_NEGATIVE_the_one_minute_clock_never_moves_from_a_re_read_frame(monkeypatch):
    st, colls = mk_store()
    colls[GS.STATE].docs[LC.LUK_STATE_BARS_THROUGH] = {"_id": LC.LUK_STATE_BARS_THROUGH, "session": DAY,
                                                        "t1": at("09:30"), "t5": at("09:30")}
    seed(colls, "CCC", _r(PBR, "forming"))
    spies = steps(monkeypatch, t1=at("09:35"), rt1=at("09:40"), reread={"CCC": _r(PBR, "forming")})
    out = run(st)
    assert colls[GS.STATE].docs[LC.LUK_STATE_BARS_THROUGH]["t1"] == at("09:35")
    assert out["bars_through"] == {"t1_et": "09:35", "t5_et": "09:35"}
    assert [p for s, _f, p in spies["read_syms"] if s == "CCC"] == [at("09:30")]   # the SAME prev_t1


def test_NEGATIVE_a_shown_name_on_the_shortlist_is_read_once(monkeypatch):
    st, colls = mk_store()
    seed(colls, "AAA", _r(PBR, "forming"))
    seed(colls, "CCC", _r(PBR, "forming"))
    spies = steps(monkeypatch, ring={"AAA": _r(PBR, "forming")}, reread={"CCC": _r(PBR, "forming")})
    run(st)
    assert spies["frames_for"][1]["names"] == ["CCC"]
    assert [s for s, _f, _p in spies["read_syms"]].count("AAA") == 1


def test_NEGATIVE_only_shortlist_cards_shown_means_no_second_call(monkeypatch):
    st, colls = mk_store()
    seed(colls, "AAA", _r(PBR, "forming"))
    spies = steps(monkeypatch, ring={"AAA": _r(PBR, "forming")})
    out = run(st)
    assert len(spies["frames_for"]) == 1
    assert out["refresh"]["asked"] == [] and out["refresh"]["board_read_n"] == out["refresh"]["board_n"] == 1


# ── NEGATIVE: a failed re-read keeps the old doc and the board tags it ────────────────────────────────────────────
@pytest.mark.parametrize("how", ["failed", "raised"])
def test_NEGATIVE_a_failed_re_read_keeps_the_old_doc_and_the_board_tags_it(monkeypatch, how):
    st, colls = mk_store()
    seed(colls, "CCC", _r(PBR, "forming"))
    seed(colls, "DDD", _r(PBR, "forming"))
    steps(monkeypatch, ring={"AAA": _r(PBR, "forming")}, reread={"DDD": _r(PBR, "forming")},
          fail=("CCC",) if how == "failed" else (), raise_read=("CCC",) if how == "raised" else ())
    out = run(st)
    assert doc(colls, "CCC")["updated_at"] == OLD and "refresh_only" not in doc(colls, "CCC")
    assert out["refresh"]["not_read"] == ["CCC"] and out["refresh"]["read_n"] == 1
    assert out["status"] == "ok" and "refresh" not in out["errors"]
    assert (f"reread:CCC" in out["errors"]) is (how == "raised")
    board = TB.build(PBR, now=at("09:37"), store=st)
    tiles = {t["symbol"]: t for t in board["tiles"]}
    assert tiles["CCC"]["not_reread"] is True and "09:31" in tiles["CCC"]["not_reread_text"]
    assert tiles["DDD"]["not_reread"] is False and tiles["AAA"]["not_reread"] is False


def test_NEGATIVE_budget_spent_no_second_call_and_every_asked_name_not_read(monkeypatch):
    st, colls = mk_store()
    seed(colls, "CCC", _r(PBR, "forming"))
    seed(colls, "DDD", _r(ORH, "listed"))
    ticks = iter([0.0])
    spies = steps(monkeypatch)
    out = run(st, deps=fake_deps(clock=lambda: next(ticks, 1000.0)))
    assert len(spies["frames_for"]) == 1
    rf = out["refresh"]
    assert rf["budget_s"] == 0.0 and rf["read_n"] == 0
    assert rf["not_read"] == rf["asked"] == ["CCC", "DDD"] and rf["bars"]["over_budget"] == rf["asked_n"] == 2
    assert out["ledger"] == {"rows": 0}                                          # the grade step still ran


# ── the on-demand pass and the A8 stop ───────────────────────────────────────────────────────────────────────────
def test_the_on_demand_pass_re_reads_too_dry_gate_no_clock(monkeypatch):
    st, colls = mk_store()
    steps(monkeypatch, ring={"AAA": _r(PBR, "forming")})
    run(st)
    clock = copy.deepcopy(colls[GS.STATE].docs[LC.LUK_STATE_BARS_THROUGH])
    seed(colls, "CCC", _r(PBR, "forming"))
    steps(monkeypatch, ring={"AAA": _r(PBR, "forming")}, t1=at("09:37"),
          reread={"CCC": _r(PBR, "aplus", entry=f"{DAY} 09:37")})
    out = LR.run_on_demand(at("09:38", 10), store=st, deps=fake_deps())
    d = doc(colls, "CCC")
    assert d["on_demand"] is True and d["refresh_only"] is True and d["cron_setups"] == _r(PBR, "forming")
    assert out["refresh"]["read_n"] == 1 and out["alerts"]["dry"] == 0           # the re-read A+ never reached it
    assert colls[GS.STATE].docs[LC.LUK_STATE_BARS_THROUGH] == clock
    assert colls[GS.ALERTS].writes == 0


class _FlipStore(ST.LukStore):
    """The lease is taken over by a cron right after the k-th upsert_read."""

    def __init__(self, colls, k):
        super().__init__(colls=colls)
        self.k, self.n_reads, self.ref = k, 0, colls

    def upsert_read(self, *a, **kw):
        super().upsert_read(*a, **kw)
        self.n_reads += 1
        if self.n_reads == self.k:
            self.ref[GS.STATE].docs["lease"] = {"_id": "lease", "status": "running", "held_by": GS.LEASE_CRON,
                                                "token": "CRON", "claimed_at": at("09:41", 7)}


def test_C1_superseded_inside_13b_is_not_swallowed(monkeypatch):
    colls = mk_colls()
    seed(colls, "CCC", _r(PBR, "forming"))
    seed(colls, "DDD", _r(PBR, "forming"))
    st = _FlipStore(colls, len(RING))                                            # flips after the LAST ring read
    steps(monkeypatch, reread={"CCC": _r(PBR, "triggered", entry=f"{DAY} 09:37"), "DDD": _r(PBR, "forming")})
    out = LR.run_on_demand(at("09:38", 10), store=st, deps=fake_deps())
    assert out["status"] == "superseded" and out["superseded"] == 1
    assert "refresh" not in out["errors"] and "refresh" not in out
    assert st.n_reads == len(RING)                                               # nothing more written
    assert doc(colls, "CCC")["updated_at"] == OLD and doc(colls, "DDD")["updated_at"] == OLD


# ── [C1] a whole-step fault keeps the grade and the clock ────────────────────────────────────────────────────────
@pytest.mark.parametrize("where", ["board_names", "alert_rows", "frames_for"])
def test_NEGATIVE_C1_a_whole_step_fault_keeps_the_grade_and_the_clock(monkeypatch, where):
    st, colls = mk_store()
    seed(colls, "CCC", _r(PBR, "forming"))
    spies = steps(monkeypatch, raise_second=(where == "frames_for"))

    def boom(*a, **k):
        raise RuntimeError(where)
    if where == "board_names":
        monkeypatch.setattr(LR, "_board_names", boom)
    elif where == "alert_rows":
        monkeypatch.setattr(st, "alert_rows", boom)
    out = run(st)
    assert out["status"] == "ok" and out["errors"] == ["refresh"]
    assert out["refresh"] == LR._refresh_skipped(LR.SKIP_REFRESH_ERROR)
    assert out["ledger"] == {"rows": 0} and len(spies["grade"]) == 1
    assert colls[GS.STATE].docs[LC.LUK_STATE_BARS_THROUGH]["t1"] == at("09:35")
    assert colls[GS.PASSES].docs["latest"]["refresh"]["skipped"] == LR.SKIP_REFRESH_ERROR
    assert doc(colls, "CCC")["updated_at"] == OLD


def test_NEGATIVE_symbols_skip_the_re_read(monkeypatch):
    st, colls = mk_store()
    seed(colls, "CCC", _r(PBR, "forming"))
    spies = steps(monkeypatch)
    out = run(st, symbols=["aaa"])
    assert len(spies["frames_for"]) == 1
    assert out["refresh"] == LR._refresh_skipped(LR.SKIP_REFRESH_SYMBOLS)


# ── ONE engine + the [C4] overlay ────────────────────────────────────────────────────────────────────────────────
def test_one_engine_board_names_equal_the_board_tiles():
    st, colls = mk_store()
    n = GC.TILE_LIMIT_DEFAULT + 5
    for i in range(n):
        seed(colls, f"O{i:02d}", _r(ORH, "triggered", entry=f"{DAY} 09:{30 + i % 29:02d}"))
    for i in range(3):
        seed(colls, f"P{i}", _r(PBR, "forming"))
    seed(colls, "I0", _r(IDP, "listed"))
    seed(colls, "NN", _r(PBR, "none"))                                          # never carded
    docs = st.reads(D)
    shown = set()
    for setup in LC.SETUPS:
        shown |= {t["symbol"] for t in TB.build(setup, now=at("09:37"), store=st)["tiles"]}
    names = LR._board_names(docs, [])
    assert set(names) == shown and len(names) == len(set(names)) == GC.TILE_LIMIT_DEFAULT + 4
    assert "NN" not in names and len(names) <= LC.LUK_REREAD_MAX


def test_C4_a_card_entering_the_cut_because_a_ring_read_re_sorted_others_is_re_read(monkeypatch):
    st, colls = mk_store()
    lim = GC.TILE_LIMIT_DEFAULT
    seed(colls, "AAA", _r(ORH, "listed"))                                        # sorts first; on the shortlist
    names = [f"S{i:02d}" for i in range(1, lim + 1)]                             # S{lim} sits (lim+1)-th → cut
    for s in names:
        seed(colls, s, _r(ORH, "listed"))
    x = names[-1]
    assert x not in LR._board_names(st.reads(D), [])                             # NEGATIVE: cut without the overlay
    spies = steps(monkeypatch, ring={"AAA": {}})                                 # the ring read moves AAA to none
    out = run(st)
    assert x in spies["frames_for"][1]["names"] and "AAA" not in spies["frames_for"][1]["names"]
    assert doc(colls, x)["refresh_only"] is True and out["refresh"]["not_read"] == []


def test_NEGATIVE_overlay_is_pure_and_appends_new_ring_symbols_sorted():
    today = [{"symbol": "AAA", "setups": {"x": 1}}, {"symbol": "CCC", "setups": {"x": 2}}, "junk"]
    ring = {"ZZZ": {"symbol": "ZZZ"}, "AAA": {"symbol": "AAA", "setups": {"x": 9}}, "MMM": {"symbol": "MMM"}}
    t0, r0 = copy.deepcopy(today), copy.deepcopy(ring)
    got = LR._overlay(today, ring)
    assert today == t0 and ring == r0
    assert [d["symbol"] for d in got] == ["AAA", "CCC", "MMM", "ZZZ"]
    assert got[0]["setups"] == {"x": 9}


# ── NEGATIVE: pending facts ──────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_pending_facts_fall_back_to_stored_facts_never_a_stored_pending(monkeypatch):
    st, colls = mk_store()
    stored = {"tier": "lead", "adr20_pct": 6.0}
    seed(colls, "BBB", _r(PBR, "forming"), facts=dict(stored))                  # in the universe, facts Pending
    seed(colls, "CCC", _r(PBR, "forming"), facts={"pending": True, "pending_text": "x"})
    seed(colls, "DDD", _r(PBR, "forming"), facts=dict(stored))                  # not in the universe at all
    spies = steps(monkeypatch, reread={s: _r(PBR, "forming") for s in ("BBB", "CCC", "DDD")})
    monkeypatch.setattr(SC, "shortlist", lambda lists, carried: (spies["shortlist"].append(set(carried))
                                                                 or (["AAA"], 0)))
    run(st, deps=fake_deps(fetch=None))                                          # every warm fact is a Pending
    seen = {s: f for s, f, _p in spies["read_syms"]}
    assert seen["BBB"] == stored and seen["DDD"] == stored
    assert not seen["CCC"]                                                       # a stored pending is never used
    assert not seen["AAA"]                                                       # a ring read keeps the Pending
    assert doc(colls, "BBB")["facts"] == stored


# ── the pass doc carries `refresh` with exactly REFRESH_KEYS ──────────────────────────────────────────────────────
@pytest.mark.parametrize("mode", ["on", "off", "symbols", "error"])
def test_the_pass_doc_carries_refresh_with_exactly_the_keys(monkeypatch, mode):
    st, colls = mk_store()
    seed(colls, "CCC", _r(PBR, "forming"))
    steps(monkeypatch, reread={"CCC": _r(PBR, "forming")})
    if mode == "off":
        monkeypatch.setattr(LC, "LUK_REREAD_SHOWN", False)
    if mode == "error":
        monkeypatch.setattr(LR, "_board_names", lambda *a: 1 / 0)
    out = run(st, symbols=["AAA"] if mode == "symbols" else None)
    rf = colls[GS.PASSES].docs["latest"]["refresh"]
    assert set(rf) == set(LR.REFRESH_KEYS) and rf == out["refresh"]
    assert rf["on"] is (mode == "on")
    assert rf["skipped"] == {"on": None, "off": LR.SKIP_REFRESH_OFF, "symbols": LR.SKIP_REFRESH_SYMBOLS,
                             "error": LR.SKIP_REFRESH_ERROR}[mode]
    assert set(rf["bars"]) == {"loaded", "no_bars", "failed", "over_budget"}


def test_cron_setups_rule():
    assert LR._cron_setups(None) is None and LR._cron_setups("x") is None
    assert LR._cron_setups({"setups": 1, "cron_setups": 2}) == 1
    assert LR._cron_setups({"setups": 1, "cron_setups": 2, "on_demand": True}) == 2
    assert LR._cron_setups({"setups": 1, "cron_setups": 2, "refresh_only": True}) == 2
    assert LR._cron_setups({"setups": 1, "refresh_only": True}) is None


def test_the_constants_are_read_by_name_never_retyped():
    import inspect
    src = inspect.getsource(LR._board_reread) + inspect.getsource(LR._board_names)
    assert "LC.LUK_PASS_BUDGET_SEC - LC.LUK_GRADE_BUDGET_SEC" in src and "LC.LUK_REREAD_MAX" in src
    assert "GC.TILE_LIMIT_DEFAULT" in src and "TB.tiles_for" in src and "TB._clip_focus" in src
    assert "_exists(" not in inspect.getsource(LR._rang)                         # never the fail-open read
