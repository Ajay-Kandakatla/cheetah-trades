"""🧘 GG-like — the tracking half (2026-11-27, spec gg-like rev 2 §3.6-§3.7, WP `be-track`). NEGATIVES mandatory.

Ajay 2026-11-27: "...Continue to track the runners we might evolve and find patterns in the current runners too but I want
to make sure we are finding similar setups to Gajjala". Hermetic: the in-memory FakeColl store (tests/conftest.py refuses
a real MongoClient), injected loaders / split looks / cache stamps — never the network. The ONE real read is the stored
DKI 11-25 doc of tests/fixtures/gajjala/gg_like_reads_2026_11_25.json (be-engine's fixture, read here, never edited).
"""
from __future__ import annotations

import copy
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import divergence as DV
from chart_maps.gajjala import gg_like as GL
from chart_maps.gajjala import gg_like_track as GLT
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import nightly as NG
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import constants as WC
from chart_maps.gajjala_watch import runseat as RS
from chart_maps.gajjala_watch import runtrack as RT
from tests.test_gajjala_store import FakeColl, fake_store
from tests.test_gajjala_watch_runtrack_2026_11_26 import (RUN, WIN, Coll, aplus_run, entry, frame, full_bars, rdoc,
                                                          run_night, seams)   # noqa: F401 — `seams` is a fixture

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
S = date(2026, 11, 25)                                          # the ring session (Wed)
HALF = date(2026, 11, 27)                                       # a market day (half day) — tonight's nightly
NOW = datetime(2026, 11, 27, 21, 0, tzinfo=ET).astimezone(UTC)  # after 11-25's 20:00 + settle: due
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "gajjala" / "gg_like_reads_2026_11_25.json"
RS_ = "reversal_squeeze"
R_FIG = re.compile(r"[+-]?\d+(\.\d+)?R\b")


def et(d, hh, mm) -> datetime:
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET).astimezone(UTC)


def dki_doc() -> dict:
    docs = json.loads(FIXTURE.read_text(encoding="utf-8"))["docs"]
    return copy.deepcopy(next(d for d in docs if d.get("_id") == "2026-11-25|DKI"))


def dki_block() -> dict:
    blk = GL.doc_blocks(dki_doc())[RS_]
    assert GL.from_stamp(blk) is blk and blk["verdict"] == "not"
    return blk


def blk_of(verdict="gg_like", setup=RS_) -> dict:
    """SYNTHETIC: the real DKI block with its verdict / setup swapped (from_stamp is a shape guard — it accepts it)."""
    b = copy.deepcopy(dki_block())
    b["verdict"], b["setup"] = verdict, setup
    b["failed"] = [] if verdict != "not" else b["failed"]
    return b


def claim(sym="DKI", setup=RS_, d=S, at=None, trig=1.29, stop=1.19, gg=None, ebt="2026-11-25 16:50", frame_="5m",
          state="pushed"):
    at = at or et(d, 10, 30)
    doc = {"_id": f"GG:{d.isoformat()}|{sym}|{setup}", "date": d.isoformat(), "symbol": sym, "setup": setup,
           "trigger": trig, "stop": stop, "state": state, "at": at.isoformat(), "entry_bar_t": ebt, "frame": frame_,
           "price": trig}
    if gg is not None:
        doc["gg_like"] = gg
    return doc


def pot(sym="AAA", setup="kiss_fly", d=S, gg=None, trig=1.0, stop=0.9):
    push = {"state": "pushed", "at": et(d, 10, 0).isoformat(), "at_et": "10:00", "trigger": trig, "stop": stop, "px": 0.95}
    if gg is not None:
        push["gg_like"] = gg
    return {"_id": ST.potential_key(d, sym, setup), "date": d.isoformat(), "symbol": sym, "setup": setup,
            "first_seen_et": "10:00", "first_seen_mode": "normal", "first_trigger": trig, "first_stop": stop,
            "first_px": 0.95, "push": push}


def lid(sym="DKI", setup=RS_, d=S, kind="aplus"):
    return LG.ledger_id(d.isoformat(), sym, setup, kind)


def ledger_doc(sym="DKI", setup=RS_, d=S, kind="aplus", **extra):
    doc = {"_id": lid(sym, setup, d, kind), "date": d.isoformat(), "symbol": sym, "setup": setup, "kind": kind,
           "line": "live", "alert": {"trigger": 1.29}, "same": {"entry": "no_entry", "version": 1},
           "next": {"entry": "no_entry"}, "graded_at": "x", "version": GC.LEDGER_GRADE_VERSION}
    doc.update(extra)
    return doc


def store(alerts=(), ledger=(), reads=(), pots=(), fail=None):
    colls = {ST.ALERTS: FakeColl(list(alerts)), ST.LEDGER: FakeColl(list(ledger)), ST.READS: FakeColl(list(reads)),
             ST.POTENTIALS: FakeColl(list(pots))}
    if fail:
        colls[fail] = FakeColl(fail=True)
    return fake_store(**colls)


class Spy:
    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def __call__(self, *a):
        self.calls.append(a)
        return self.answer(*a) if callable(self.answer) else self.answer


def bars_up(d=S, hi=1.35, at=(11, 0)) -> list:
    """SYNTHETIC 1-minute bars (t_utc START, o, h, l, c): flat 1.0 from 09:30, one minute at `hi`."""
    out, t = [], et(d, 9, 30)
    while t < et(d, 19, 59):
        out.append((t, 1.0, 1.0, 1.0, 1.0))
        t += timedelta(minutes=1)
    out.append((et(d, *at), 1.0, hi, 1.0, hi))
    return sorted(out)


def night(st, **kw):
    kw.setdefault("load_day", Spy(lambda sym, day: (bars_up(day), False)))
    kw.setdefault("split_look", Spy(False))
    kw.setdefault("cached_at", Spy({}))
    return GLT.record_night(kw.pop("now", NOW), store=st, **kw), kw


# ── store.annotate_ledger [C8] ───────────────────────────────────────────────────────────────────────────────────
def test_annotate_ledger_sets_only_the_note_keys_on_an_existing_doc():
    doc = ledger_doc()
    st = store(ledger=[doc])
    assert st.annotate_ledger(doc["_id"], {"win30": {"measured": True}, "gg_like": {"v": 1}}) == "matched"
    got = st.coll(ST.LEDGER).docs[doc["_id"]]
    assert got["win30"] == {"measured": True} and got["gg_like"] == {"v": 1}
    for k in ("alert", "same", "next", "date", "graded_at", "version"):
        assert got[k] == doc[k]


def test_NEGATIVE_annotate_ledger_with_no_doc_is_unmatched_and_creates_nothing():
    st = store()
    assert st.annotate_ledger(lid(), {"win30": {"measured": False}}) == "unmatched"
    assert st.coll(ST.LEDGER).docs == {}


@pytest.mark.parametrize("bad", [{"same": {}}, {"alert": {}}, {"date": "2026-11-25"}, {"win30": {}, "next": {}}, {}])
def test_NEGATIVE_annotate_ledger_refuses_a_key_outside_the_note_keys(bad):
    st = store(ledger=[ledger_doc()])
    assert st.annotate_ledger(lid(), bad) == "refused"
    assert st.coll(ST.LEDGER).writes == 0


def test_NEGATIVE_annotate_ledger_on_a_faulting_or_missing_collection_is_error():
    assert store(fail=ST.LEDGER).annotate_ledger(lid(), {"win30": {}}) == "error"
    assert ST.GajjalaStore(colls={n: None for n in ST.ALL}).annotate_ledger(lid(), {"win30": {}}) == "error"


def test_ledger_keys_are_unchanged_and_upsert_ledger_still_refuses_the_notes():
    assert ST.LEDGER_KEYS == frozenset({"date", "symbol", "setup", "kind", "line", "alert", "same", "next",
                                        "graded_at", "version"})
    assert ST.LEDGER_NOTE_KEYS == frozenset({"gg_like", "win30"}) and not (ST.LEDGER_NOTE_KEYS & ST.LEDGER_KEYS)
    st = store()
    assert st.upsert_ledger(lid(), {"gg_like": {}}) is False and st.upsert_ledger(lid(), {"win30": {}}) is False
    assert st.coll(ST.LEDGER).docs == {}


def test_annotate_ledger_has_a_module_delegate(monkeypatch):
    st = store(ledger=[ledger_doc()])
    monkeypatch.setattr(ST, "default", lambda: st)
    assert ST.annotate_ledger(lid(), {"win30": {"measured": True}}) == "matched"


# ── ledger.alert_of passthrough ──────────────────────────────────────────────────────────────────────────────────
def test_alert_of_carries_a_valid_ring_stamp_on_an_aplus_and_a_potential_row():
    b = dki_block()
    a = LG.alert_of(claim(gg=b), "aplus")
    assert a["gg_like"] == b
    p = LG.alert_of(pot(gg=blk_of("gg_like", "kiss_fly")), "potential")
    assert p["gg_like"]["verdict"] == "gg_like"


@pytest.mark.parametrize("bad", [None, {"v": 1, "verdict": "maybe", "checks": []}, {"v": True, "verdict": "not",
                                                                                     "checks": []}, ["not"]])
def test_NEGATIVE_no_or_a_malformed_stamp_leaves_the_row_byte_equal(bad):
    plain = LG.alert_of(claim(), "aplus")
    got = LG.alert_of(claim(gg=bad) if bad is not None else claim(), "aplus")
    assert "gg_like" not in got and got == plain
    pplain = LG.alert_of(pot(), "potential")
    pgot = LG.alert_of(pot(gg=bad) if bad is not None else pot(), "potential")
    assert "gg_like" not in pgot and pgot == pplain


def test_NEGATIVE_a_replay_row_never_carries_the_stamp():
    d = S.isoformat()
    doc = {"_id": LG.replay_id(d, "DKI", RS_), "date": d, "symbol": "DKI", "setup": RS_, "state": LG.REPLAY_STATE,
           "kind": "aplus", "alert": {"at": et(S, 10, 30).isoformat(), "trigger": 1.29, "stop": 1.19},
           "gg_like": dki_block()}
    row = LG.alert_of(doc, "aplus")
    assert row["line"] == "replayed" and "gg_like" not in row


# ── later_block ──────────────────────────────────────────────────────────────────────────────────────────────────
def later_row(**over):
    r = dict(LG.alert_of(claim(), "aplus"), entry_bar_t="2026-11-25 16:50", frame="5m")
    r.update(over)
    return r


def test_later_block_on_the_stored_dki_read_is_the_engines_block():
    assert GLT.later_block(later_row(), dki_doc()) == dki_block()


@pytest.mark.parametrize("over", [{"entry_bar_t": "2026-11-25 16:45"}, {"trigger": 1.30}, {"stop": 1.18},
                                  {"frame": "15m"}, {"entry_bar_t": None}, {"kind": "potential"}])
def test_NEGATIVE_later_block_needs_the_claims_own_bar_trigger_stop_and_frame(over):
    assert GLT.later_block(later_row(**over), dki_doc()) is None


def test_NEGATIVE_later_block_with_no_read_or_a_read_that_did_not_break():
    assert GLT.later_block(later_row(), None) is None
    doc = dki_doc()
    doc["setups"][RS_]["broke"] = False
    assert GLT.later_block(later_row(), doc) is None
    doc2 = dki_doc()
    doc2["setups"].pop(RS_)
    assert GLT.later_block(later_row(), doc2) is None


# ── R before / after costs [C6] ──────────────────────────────────────────────────────────────────────────────────
ROW = {"plan": "ok", "thin": False, "r": 0.10, "stop": 0.90, "trigger": 1.0}


def _net_by_hand(x, e, r):
    cx = GC.DIVERGENCE_COST_BPS + GC.DIVERGENCE_SLIP_USD / x
    ce = GC.DIVERGENCE_COST_BPS + GC.DIVERGENCE_SLIP_USD / e
    return round(((x * (1 - cx) - e * (1 + ce)) / e * 100) / 100 * e / r, 2)


@pytest.mark.parametrize("same,x,gross", [
    ({"entry": "filled", "fill_px": 1.0, "outcome": "win", "target_px": 1.10}, 1.10, 1.0),
    ({"entry": "filled", "fill_px": 1.0, "outcome": "loss"}, 0.90, -1.0),
    ({"entry": "filled", "fill_px": 1.0, "outcome": "open", "close_pct": 5.0}, 1.05, 0.5)])
def test_r_before_and_after_costs_by_hand_and_through_net_pct(same, x, gross):
    assert GLT.r_gross(ROW, same) == gross
    net = GLT.r_after_costs(ROW, same)
    assert net == _net_by_hand(x, 1.0, 0.10) == round(DV.net_pct(x, 1.0) / 100 * 1.0 / 0.10, 2)
    assert net < gross


@pytest.mark.parametrize("row,same", [
    (ROW, {"entry": "no_entry"}), (ROW, None),
    (ROW, {"entry": "filled", "fill_px": 1.0, "outcome": "win", "target_px": 1.1, "reason": "split"}),
    (ROW, {"entry": "filled", "fill_px": 1.0, "outcome": "win", "target_px": 1.1, "provisional": True}),
    (dict(ROW, thin=True), {"entry": "filled", "fill_px": 1.0, "outcome": "win", "target_px": 1.1}),
    (dict(ROW, plan="no_risk", r=None), {"entry": "filled", "fill_px": 1.0, "outcome": "win", "target_px": 1.1})])
def test_NEGATIVE_no_r_without_a_final_filled_ok_trade(row, same):
    assert GLT.r_gross(row, same) is None and GLT.r_after_costs(row, same) is None


# ── ring_facts / split / split_block [C2, C6] ────────────────────────────────────────────────────────────────────
def fact(kind="aplus", setup=RS_, group="not", source="ring", counted=True, filled=True, outcome="win", rg=1.0,
         rn=0.8, r_pct=5.0, win30=True):
    return {"kind": kind, "setup": setup, "group": group, "source": source, "counted": counted, "filled": filled,
            "outcome": outcome, "thin": rg is None, "r_pct": r_pct, "r_gross": rg, "r_net": rn, "win30": win30}


def test_ring_facts_reads_win30_only_for_a_ring_stamped_aplus():
    ring_row = LG.alert_of(claim(gg=dki_block()), "aplus")
    doc = ledger_doc(win30={"measured": True, "passed": True})
    f = GLT.ring_facts(ring_row, None, doc)
    assert f["source"] == "ring" and f["group"] == "not" and f["win30"] is True
    later_doc = ledger_doc(win30={"measured": True, "passed": True}, gg_like=dict(dki_block(), source="computed_later"))
    f2 = GLT.ring_facts(LG.alert_of(claim(), "aplus"), None, later_doc)
    assert f2["source"] == "computed_later" and f2["win30"] is None                     # NEGATIVE [C2]
    f3 = GLT.ring_facts(LG.alert_of(pot(gg=blk_of()), "potential"), None, doc)
    assert f3["source"] == "ring" and f3["win30"] is None                               # NEGATIVE: 🧠
    f4 = GLT.ring_facts(LG.alert_of(claim(), "aplus"), None, ledger_doc())
    assert f4["group"] == "none" and f4["source"] is None


def test_NEGATIVE_a_provisional_same_column_counts_no_fill_no_outcome_no_r():
    row = dict(LG.alert_of(claim(gg=dki_block(), trig=1.0, stop=0.9), "aplus"))
    same = {"entry": "filled", "fill_px": 1.0, "outcome": "win", "target_px": 1.1}
    assert GLT.ring_facts(row, same, None)["r_gross"] == 1.0
    f = GLT.ring_facts(row, same, None, provisional=True)
    assert f["filled"] is False and f["outcome"] is None and f["r_gross"] is None and f["r_net"] is None


def test_a_ring_stamp_is_never_shadowed_by_a_later_block():
    row = LG.alert_of(claim(gg=blk_of("gg_like")), "aplus")
    blk, src = GLT.stamp_of(row, ledger_doc(gg_like=dict(dki_block(), source="computed_later")))
    assert src == "ring" and blk["verdict"] == "gg_like"


def test_NEGATIVE_a_ledger_block_without_the_computed_later_source_is_not_a_stamp():
    assert GLT.stamp_of({}, ledger_doc(gg_like=dki_block())) == (None, None)


def test_split_parts_are_disjoint_and_computed_later_is_in_no_cell():
    s = GLT.split([fact(), fact(source="computed_later"), fact(source=None, group="none"),
                   fact(kind="potential", source=None, group="none")])
    assert list(s["cells"]) == [("aplus", RS_, "not")] and s["cells"][("aplus", RS_, "not")]["n"] == 1
    assert s["later"] == {(RS_, "not"): {"n": 1}} and s["later_total"] == 2
    assert s["none"] == {"aplus": {"n": 1}, "potential": {"n": 1}}


def test_split_block_lines_per_setup_with_r_before_and_after_and_the_median_stop():
    facts = [fact(r_pct=4.0), fact(outcome="loss", rg=-1.0, rn=-1.2, r_pct=6.0, win30=False),
             fact(setup="kiss_fly", rg=1.0, rn=0.7, r_pct=1.0, win30=None),
             fact(counted=False, rg=5.0, rn=5.0),                                   # a duplicate: out entirely
             fact(rg=None, rn=None, r_pct=3.0, outcome="open")]                     # a thin row: out of the R sums
    b = GLT.split_block(facts)
    rs_lines = [ln for ln in b["lines"] if "Reversal" in ln]
    kf_lines = [ln for ln in b["lines"] if "Kiss" in ln]
    assert len(rs_lines) == 1 and len(kf_lines) == 1                                # two setups → TWO lines
    rs = rs_lines[0]
    assert "3 rings" in rs and "2 of 3 ran +30% from the trigger" in rs                  # the thin ring still ran
    assert "3 filled — 1 +1R, 1 stopped, 1 open" in rs
    assert "+0.00R before costs, -0.40R after" in rs                                # 1.0 − 1.0 / 0.8 − 1.2
    assert "stop 4.0% wide (median)" in rs                                          # median of 4, 6, 3
    assert "ran +" not in kf_lines[0]                                               # no measured day → clause dropped
    for ln in b["lines"]:
        low = ln.lower()
        assert "average" not in low and " mean" not in low and "avg" not in low
        assert not re.search(r"\d+% of|win rate|% win", low)
    assert b["lines"].index(kf_lines[0]) < b["lines"].index(rs)                     # GC.SETUPS order
    assert "UNMEASURED" in b["title"] and b["label"] == f"{GL.CHIP_OK} vs not"


def test_split_block_kind_order_and_no_30_clause_on_the_potential_lines():
    b = GLT.split_block([fact(kind="potential", setup="kiss_fly", win30=True), fact()])
    assert b["lines"][0].startswith("🎯 A+") and b["lines"][1].startswith("🧠 armed")
    assert "ran +" not in b["lines"][1]


def test_NEGATIVE_computed_later_is_never_in_a_result_line():
    b = GLT.split_block([fact(setup="kiss_fly"), fact(source="computed_later", setup=RS_, group="gg_like"),
                         fact(source=None, group="none")])
    later = [ln for ln in b["lines"] if ln.startswith("Older A+ rings")]
    assert len(later) == 1
    assert "(1 of 2 still matched)" in later[0] and "GG-like 1 · not GG-like 0 · can't tell 0" in later[0]
    assert not R_FIG.search(later[0]) and "+30" not in later[0] and "ran +" not in later[0]
    assert not [ln for ln in b["lines"] if "Reversal" in ln]                         # its setup has no result line
    assert "No check on file: 1 A+ · 0 🧠" in b["lines"]


def test_NEGATIVE_a_cell_with_no_ring_prints_nothing_and_no_stamp_at_all_prints_the_one_line():
    b = GLT.split_block([fact(source="computed_later"), fact(source=None, group="none")])
    assert b["lines"][0] == GLT.NO_RING_LINE
    assert not [ln for ln in b["lines"] if ln.startswith("🎯") or ln.startswith("🧠")]
    assert GLT.split_block([])["lines"] == [GLT.NO_RING_LINE]


def test_split_block_note_reads_its_numbers_from_the_constants(monkeypatch):
    n = GLT.split_block([])["note"]
    assert f"+{WC.RUNNERS_SEAT_APLUS_PCT}%" in n and "0.10%" in n and "$0.01" in n and "20:00 ET" in n
    monkeypatch.setattr(WC, "RUNNERS_SEAT_APLUS_PCT", 31)
    monkeypatch.setattr(GC, "DIVERGENCE_COST_BPS", 0.002)
    n2 = GLT.split_block([fact()])
    assert "+31%" in n2["note"] and "0.20%" in n2["note"] and "ran +31% from the trigger" in n2["lines"][0]


def test_sources_equal_the_engines():
    assert GLT.SOURCES == GL.SOURCES and tuple(GLT.GROUPS[:3]) == GL.VERDICTS


# ── record_night [C2, C8] ────────────────────────────────────────────────────────────────────────────────────────
def test_record_night_measures_a_ring_stamped_aplus_once_and_a_second_run_writes_and_loads_nothing():
    st = store(alerts=[claim(trig=1.0, stop=0.9, gg=dki_block())], ledger=[ledger_doc()])
    out, kw = night(st)
    assert out["written"] == 1 and out["win30"] == 1 and out["loads"] == 1 and not out["read_fault"]
    w = st.coll(ST.LEDGER).docs[lid()]["win30"]
    m = RS.from_trigger(bars_up(S), S, et(S, 10, 30), 1.0)
    assert {k: w[k] for k in RS.FROM_TRIGGER_KEYS} == {k: m[k] for k in RS.FROM_TRIGGER_KEYS}
    assert w["passed"] is True and w["measured"] is True and w["min_pct"] == WC.RUNNERS_SEAT_APLUS_PCT
    assert "gg_like" not in st.coll(ST.LEDGER).docs[lid()]                            # a ring stamp: no later block
    out2, kw2 = night(st)
    assert out2["written"] == 0 and out2["loads"] == 0 and kw2["load_day"].calls == [] and kw2["split_look"].calls == []


def test_win30_reaches_on_decimals_0_9_to_1_17():
    st = store(alerts=[claim(trig=0.9, stop=0.8, gg=dki_block())], ledger=[ledger_doc()])
    night(st, load_day=Spy(lambda sym, day: (bars_up(day, hi=1.17), False)))
    assert st.coll(ST.LEDGER).docs[lid()]["win30"]["passed"] is True


def test_NEGATIVE_a_stored_split_verdict_is_final_and_never_re_read():
    split_doc = ledger_doc(win30={"measured": False, "why": "split", "at": "x"})
    st = store(alerts=[claim(gg=dki_block())], ledger=[split_doc])
    out, kw = night(st)
    assert out["written"] == 0 and kw["split_look"].calls == [] and kw["load_day"].calls == []
    assert st.coll(ST.LEDGER).docs[lid()]["win30"] == split_doc["win30"]


def test_a_split_answer_writes_the_final_split_verdict_with_no_load():
    st = store(alerts=[claim(gg=dki_block())], ledger=[ledger_doc()])
    out, kw = night(st, split_look=Spy("2026-11-26"))
    assert out["win30_split"] == 1 and kw["load_day"].calls == []
    w = st.coll(ST.LEDGER).docs[lid()]["win30"]
    assert w["measured"] is False and w["why"] == "split"


def test_NEGATIVE_an_unanswered_split_check_writes_nothing_and_is_retried():
    st = store(alerts=[claim(gg=dki_block())], ledger=[ledger_doc()])
    out, kw = night(st, split_look=Spy(None))
    assert out["split_unchecked"] == 1 and out["written"] == 0 and kw["load_day"].calls == []
    assert "win30" not in st.coll(ST.LEDGER).docs[lid()]
    out2, _kw = night(st)
    assert out2["written"] == 1


def test_a_day_cached_on_the_ring_day_needs_no_split_look():
    st = store(alerts=[claim(gg=dki_block())], ledger=[ledger_doc()])
    stamp = datetime(2026, 11, 25, 22, 0, tzinfo=ET).astimezone(UTC)                 # a datetime, as Mongo hands it
    out, kw = night(st, cached_at=Spy(lambda sym, isos: {isos[0]: stamp}))
    assert kw["split_look"].calls == [] and out["win30"] == 1


def test_NEGATIVE_a_row_with_no_ledger_doc_reads_nothing_writes_nothing_creates_nothing():
    st = store(alerts=[claim(gg=dki_block()), claim(sym="TOPP")], reads=[dki_doc()])
    out, kw = night(st)
    assert out["no_ledger_doc"] == 2 and out["loads"] == 0 and out["written"] == 0
    assert kw["load_day"].calls == [] and kw["split_look"].calls == []
    assert st.coll(ST.LEDGER).docs == {} and st.coll(ST.LEDGER).writes == 0


def test_NEGATIVE_a_play_day_not_ended_is_not_due():
    d = HALF
    st = store(alerts=[claim(d=d, gg=dki_block())], ledger=[ledger_doc(d=d)])
    out, kw = night(st, now=datetime(2026, 11, 27, 15, 0, tzinfo=ET).astimezone(UTC))
    assert out["not_due"] == 1 and out["written"] == 0 and kw["load_day"].calls == []


def test_NEGATIVE_dry_writes_nothing():
    st = store(alerts=[claim(gg=dki_block())], ledger=[ledger_doc()])
    out, _kw = night(st, dry=True)
    assert out["dry"] is True and out["win30"] == 1 and out["written"] == 0
    assert st.coll(ST.LEDGER).writes == 0


@pytest.mark.parametrize("which", [ST.LEDGER, ST.ALERTS])
def test_NEGATIVE_a_read_fault_writes_nothing(which):
    st = store(alerts=[claim(gg=dki_block())], ledger=[ledger_doc()], fail=which)
    out, kw = night(st)
    assert out["read_fault"] is True and out["written"] == 0 and kw["load_day"].calls == []


def test_NEGATIVE_a_potential_row_is_never_written():
    p = pot(gg=blk_of("gg_like", "kiss_fly"))
    st = store(pots=[p], ledger=[ledger_doc("AAA", "kiss_fly", kind="potential")])
    out, kw = night(st)
    assert out["rows"] == 0 and out["written"] == 0 and st.coll(ST.LEDGER).writes == 0


def test_computed_later_block_is_written_once_and_never_measured():
    st = store(alerts=[claim()], ledger=[ledger_doc()], reads=[dki_doc()])
    out, kw = night(st, later=True)
    assert out["later"] == 1 and out["written"] == 1 and out["win30"] == 0 and kw["load_day"].calls == []
    g = st.coll(ST.LEDGER).docs[lid()]["gg_like"]
    assert g["source"] == "computed_later" and g["computed_at"] == NOW.isoformat()
    assert {k: v for k, v in g.items() if k not in ("source", "computed_at")} == dki_block()
    assert "win30" not in st.coll(ST.LEDGER).docs[lid()]
    out2, kw2 = night(st, later=True)
    assert out2["written"] == 0 and kw2["load_day"].calls == []


def test_NEGATIVE_the_nightly_default_never_writes_a_computed_later_block(monkeypatch):
    """HIS CALL #11: without his go the record starts clean — the default (the 20:15 nightly) reads no stored read and
    writes no "computed later" block, on the very row the one-time run would annotate."""
    st = store(alerts=[claim()], ledger=[ledger_doc()], reads=[dki_doc()])
    reads = Spy(None)
    monkeypatch.setattr(st, "get_read", reads)
    out, kw = night(st)
    assert out["later_on"] is False and out["later"] == 0 and out["later_no_match"] == 0 and out["written"] == 0
    assert reads.calls == [] and kw["load_day"].calls == [] and st.coll(ST.LEDGER).writes == 0
    assert "gg_like" not in st.coll(ST.LEDGER).docs[lid()]


def test_NEGATIVE_only_a_literal_true_turns_the_computed_later_pass_on():
    for v in (False, None, 0, 1, "yes", "true"):
        st = store(alerts=[claim()], ledger=[ledger_doc()], reads=[dki_doc()])
        out, _kw = night(st, later=v)
        assert out["later"] == 0 and out["written"] == 0 and "gg_like" not in st.coll(ST.LEDGER).docs[lid()], v
    st = store(alerts=[claim()], ledger=[ledger_doc()], reads=[dki_doc()])
    out, _kw = night(st, later=True)
    assert out["later_on"] is True and out["later"] == 1 and out["written"] == 1


def test_the_default_still_measures_a_ring_stamped_row():
    st = store(alerts=[claim(trig=1.0, stop=0.9, gg=dki_block())], ledger=[ledger_doc()], reads=[dki_doc()])
    out, _kw = night(st)
    assert out["later_on"] is False and out["win30"] == 1 and out["written"] == 1
    assert "gg_like" not in st.coll(ST.LEDGER).docs[lid()]


def test_NEGATIVE_a_moved_on_read_is_no_match_and_writes_nothing():
    st = store(alerts=[claim(ebt="2026-11-25 10:30")], ledger=[ledger_doc()], reads=[dki_doc()])
    out, _kw = night(st, later=True)
    assert out["later_no_match"] == 1 and out["written"] == 0 and "gg_like" not in st.coll(ST.LEDGER).docs[lid()]


def test_NEGATIVE_the_load_cap_and_a_load_failure_defer_and_retry():
    st = store(alerts=[claim(gg=dki_block())], ledger=[ledger_doc()])
    out, _kw = night(st, max_loads=0)
    assert out["deferred_cap"] == 1 and out["written"] == 0
    out2, _kw2 = night(st, load_day=Spy((None, True)))
    assert out2["load_failed"] == 1 and out2["written"] == 0
    out3, _kw3 = night(st)
    assert out3["written"] == 1


def test_NEGATIVE_an_unmatched_or_refused_note_is_counted_never_written(monkeypatch):
    st = store(alerts=[claim(gg=dki_block())], ledger=[ledger_doc()])
    monkeypatch.setattr(st, "annotate_ledger", lambda _id, sets: "unmatched")
    out, _kw = night(st)
    assert out["no_ledger_doc"] == 1 and out["written"] == 0
    monkeypatch.setattr(st, "annotate_ledger", lambda _id, sets: "error")
    out2, _kw2 = night(st)
    assert out2["write_failed"] == 1


def test_main_dry_run_prints_the_counts(monkeypatch, capsys):
    seen = {}
    monkeypatch.setattr(GLT, "record_night", lambda now, **k: seen.update(k) or {"written": 0})
    assert GLT.main(["--once", "--dry-run", "--sessions", "3"]) == 0
    assert seen == {"sessions": 3, "dry": True, "later": False} and json.loads(capsys.readouterr().out) == {"written": 0}
    assert GLT.main([]) == 2


def test_main_later_flag_is_the_only_way_to_the_computed_later_pass(monkeypatch, capsys):
    seen = {}
    monkeypatch.setattr(GLT, "record_night", lambda now, **k: seen.update(k) or {"written": 0})
    assert GLT.main(["--once", "--later"]) == 0 and seen["later"] is True
    seen.clear()
    assert GLT.main(["--once"]) == 0 and seen["later"] is False                         # NEGATIVE


# ── served_block (GG5) ───────────────────────────────────────────────────────────────────────────────────────────
def _strip(block):
    b = copy.deepcopy(block)
    b.pop("gg_like_split", None)

    def walk(x):
        if isinstance(x, dict):
            x.pop("gg_like", None)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(b)
    return b


def _tr_store():
    return store(alerts=[claim(gg=dki_block()), claim(sym="GLXG", trig=1.41, stop=1.385)],
                 ledger=[ledger_doc(win30={"measured": True, "passed": False}),
                         ledger_doc("GLXG", gg_like=dict(blk_of("unknown"), source="computed_later"))])


def test_served_block_carries_the_split_and_the_row_chips():
    b = LG.served_block(_tr_store(), S, NOW, span="today")
    rows = {r["symbol"]: r for d in b["days"] for r in d["rows"]}
    assert rows["DKI"]["gg_like"]["source"] == "ring" and rows["DKI"]["gg_like"]["verdict"] == "not"
    assert rows["GLXG"]["gg_like"]["source"] == "computed_later"
    assert rows["GLXG"]["gg_like"]["source_text"] == "computed later from the stored read"
    sp = b["gg_like_split"]
    assert set(sp) == {"label", "title", "lines", "note"}
    assert any(ln.startswith("🎯 A+ · ") and "0 of 1 ran +30%" in ln for ln in sp["lines"])
    assert any(ln.startswith("Older A+ rings checked later") for ln in sp["lines"])


def test_NEGATIVE_every_existing_key_equals_a_build_with_the_new_code_patched_out(monkeypatch):
    a = LG.served_block(_tr_store(), S, NOW, span="today")
    monkeypatch.setattr(LG, "_gg_like_stamp", lambda doc, kind: {})
    monkeypatch.setattr(LG, "_gg_like_post", lambda *x, **k: None)
    b = LG.served_block(_tr_store(), S, NOW, span="today")
    assert _strip(a) == _strip(b)
    assert "gg_like" not in json.dumps(_strip(a), ensure_ascii=False)


def test_NEGATIVE_a_raising_tracker_leaves_the_block_served_with_no_chip(monkeypatch):
    def boom(facts):
        raise RuntimeError("down")
    monkeypatch.setattr(GLT, "split_block", boom)
    b = LG.served_block(_tr_store(), S, NOW, span="today")
    assert b["gg_like_split"] is None
    assert all("gg_like" not in r for d in b["days"] for r in d["rows"])


def _variant_block(v, st=None):
    st = st or ST.GajjalaStore(colls={n: FakeColl() for n in ST.ALL}, variant=v, shared=fake_store())
    return LG.served_block(st, S, NOW, span="today", variant=v)


def test_NEGATIVE_an_audited_block_carries_no_new_key():
    assert "gg_like_split" not in _variant_block(V.GGA)


def test_a_gg1_block_serves_the_split_key_as_none_for_the_1m_5m_parity_pin():
    """REFIX 2026-11-27: tests/test_gajjala_track_parity_2026_11_05.py allows no block-key difference between the 1m and
    the 5m 🏁 — GG1 serves `gg_like_split: None` (never a split, never read), so the two blocks keep the same keys."""
    b1 = _variant_block(V.GG1)
    assert "gg_like_split" in b1 and b1["gg_like_split"] is None
    b5 = LG.served_block(store(), S, NOW, span="today")
    assert set(b1) == set(b5)


def test_NEGATIVE_a_gg1_block_never_reads_the_tracker_and_its_rows_carry_no_chip(monkeypatch):
    seen = []
    monkeypatch.setattr(LG, "_gg_like_post", lambda *a, **k: seen.append(1) or {"label": "x"})
    colls = {n: FakeColl() for n in ST.ALL}
    colls[ST.ALERTS] = FakeColl([claim(gg=dki_block())])
    b = _variant_block(V.GG1, ST.GajjalaStore(colls=colls, variant=V.GG1, shared=fake_store()))
    assert seen == [] and b["gg_like_split"] is None
    assert all("gg_like" not in r for d in b["days"] for r in d["rows"])


# ── runseat passthrough + runtrack ───────────────────────────────────────────────────────────────────────────────
def test_aplus_rings_pass_the_ring_stamp_through():
    st = store(alerts=[claim(gg=dki_block()), claim(sym="GLXG")])
    rings = {r["symbol"]: r for r in RS.aplus_rings([S], stores={V.GG5.key: st, V.GG1.key: store()})}
    assert rings["DKI"]["gg_like"] == dki_block() and rings["GLXG"]["gg_like"] is None


def _ring(rid, gg=None):
    return {"id": rid, "page": "gajjala", "date": RUN, "symbol": "AIMD", "setup": RS_, "at_et": "09:40",
            "play_day": RUN, "gg_like": gg}


def test_runtrack_open_doc_rings_gain_the_three_keys(seams, monkeypatch):
    coll = Coll()
    seams["rings"] = [_ring("R1", dki_block()), _ring("R2"), _ring("R3")]
    notes = {"R1": {"win30": {"measured": True, "passed": True}},
             "R2": {"gg_like": dict(blk_of("gg_like"), source="computed_later"),
                    "win30": {"measured": True, "passed": True}}}
    monkeypatch.setattr(RT, "_notes", lambda dates, stores: notes)
    run_night(RUN, coll, rdoc([entry("AIMD", aplus_run(ring_id="R1"))]), {"AIMD": frame(full_bars())})
    by = {a["id"]: a for a in coll.docs[f"{RUN}|AIMD"]["aplus"]}
    assert (by["R1"]["gg_like"], by["R1"]["gg_like_source"], by["R1"]["win30"]) == ("not", "ring", True)
    assert (by["R2"]["gg_like"], by["R2"]["gg_like_source"], by["R2"]["win30"]) == ("gg_like", "computed_later", None)
    assert (by["R3"]["gg_like"], by["R3"]["gg_like_source"], by["R3"]["win30"]) == (None, None, None)


def test_NEGATIVE_a_closed_runtrack_doc_is_never_rewritten(seams, monkeypatch):
    closed = {"_id": f"{RUN}|OLD", "symbol": "OLD", "run_day": RUN, "state": "closed", "aplus": [], "window": WIN,
              "closed": {"closed_by": "window"}}
    coll = Coll([closed])
    seams["rings"] = [dict(_ring("R9", dki_block()), symbol="OLD")]
    monkeypatch.setattr(RT, "_notes", lambda dates, stores: {})
    run_night(WIN[-1], coll, rdoc([]), {})
    assert f"{RUN}|OLD" not in coll.writes and coll.docs[f"{RUN}|OLD"]["aplus"] == []


def test_runtrack_gg_like_text_counts_only_and_later_is_never_in_a_30_count():
    docs = [{"aplus": [{"id": "A", "gg_like": "gg_like", "gg_like_source": "ring", "win30": True},
                       {"id": "B", "gg_like": "not", "gg_like_source": "ring", "win30": False},
                       {"id": "C", "gg_like": "not", "gg_like_source": "ring", "win30": None},
                       {"id": "D", "gg_like": "gg_like", "gg_like_source": "computed_later", "win30": True},
                       {"id": "E", "gg_like": None, "gg_like_source": None, "win30": None}]},
            {"aplus": [{"id": "A", "gg_like": "gg_like", "gg_like_source": "ring", "win30": True}]}]   # dup id
    t = RT.gg_like_text(docs)
    assert t == ("🧘 A+ rings on these runners, frozen when they rang: GG-like 1 (1 of 1 ran +30%) · not GG-like 2 "
                 "(0 of 1) · checked later 1 · no check on file 1 — UNMEASURED, counts only")
    assert not R_FIG.search(t) and "can't tell" not in t                            # a zero part is dropped


def test_NEGATIVE_runtrack_gg_like_text_is_none_with_no_ring_and_payload_serves_it():
    assert RT.gg_like_text([{"aplus": []}, {}]) is None
    docs = [{"_id": f"{RUN}|AIMD", "symbol": "AIMD", "run_day": RUN, "state": "open", "window": WIN,
             "aplus": [{"id": "A", "gg_like": "not", "gg_like_source": "ring", "win30": None}]}]
    p = RT.payload(datetime(2026, 11, 30, 21, 0, tzinfo=UTC), coll=Coll(docs))
    assert p["gg_like_text"].startswith("🧘 A+ rings") and "not GG-like 1" in p["gg_like_text"]
    assert RT.payload(datetime(2026, 11, 30, 21, 0, tzinfo=UTC), coll=Coll([]))["gg_like_text"] is None


# ── the nightly fence ────────────────────────────────────────────────────────────────────────────────────────────
def _main(monkeypatch, capsys, record):
    from chart_maps.gajjala import si_track as SIT
    from chart_maps.gajjala import vol_dried as VD
    from chart_maps.gajjala_watch import runtrack as RTK
    order = []
    monkeypatch.setattr(ST, "default", lambda: fake_store())
    monkeypatch.setattr(NG, "run", lambda *a, **k: {"errors": []})
    monkeypatch.setattr(NG, "grade_1m", lambda now, **k: {})
    monkeypatch.setattr(NG, "grade_audited", lambda now, **k: {})
    monkeypatch.setattr(DV, "grade_divergence", lambda now, **k: {})
    monkeypatch.setattr(VD, "grade_night", lambda now: {})
    monkeypatch.setattr(SIT, "record_night", lambda now, **k: order.append("si_track") or {})
    monkeypatch.setattr(RTK, "nightly", lambda now, **k: order.append("runtrack") or {})
    if record is not None:
        monkeypatch.setattr(GLT, "record_night", lambda now, **k: order.append("gg_like") or record(now))
    code = NG.main(["--steps", "grade"])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    return code, out, order


def test_nightly_runs_the_record_between_the_si_track_and_the_runners_record(monkeypatch, capsys):
    code, out, order = _main(monkeypatch, capsys, lambda now: {"written": 2})
    assert code == 0 and order == ["si_track", "gg_like", "runtrack"] and out["gajjala_gg_like"] == {"written": 2}


def test_NEGATIVE_the_nightly_never_passes_the_computed_later_switch(monkeypatch, capsys):
    """HIS CALL #11 — nightly.py:394-399 runs every night; it must call record_night with later=False, and the real
    record_night under those exact kwargs writes no "computed later" block on a row whose stored read still matches."""
    seen = {}
    _main(monkeypatch, capsys, lambda now: {})                       # stubs the fence's neighbours (kept for this test)
    monkeypatch.setattr(GLT, "record_night", lambda now, **k: seen.update(k) or {})
    NG.main(["--steps", "grade"])
    capsys.readouterr()
    assert seen.get("later") is False
    monkeypatch.undo()
    st = store(alerts=[claim()], ledger=[ledger_doc()], reads=[dki_doc()])
    out, _kw = night(st, **seen)
    assert out["later"] == 0 and out["written"] == 0 and "gg_like" not in st.coll(ST.LEDGER).docs[lid()]


def test_NEGATIVE_a_raising_record_night_is_fenced(monkeypatch, capsys):
    def boom(now):
        raise RuntimeError("down")
    code, out, order = _main(monkeypatch, capsys, boom)
    assert code == 0 and out["errors"] == [] and out["gajjala_gg_like"] == {"error": "record: RuntimeError"}
    assert order[-1] == "runtrack"


def test_NEGATIVE_a_broken_module_is_fenced_too(monkeypatch, capsys):
    import chart_maps.gajjala as pkg
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala.gg_like_track", None)
    monkeypatch.delattr(pkg, "gg_like_track", raising=False)
    code, out, _order = _main(monkeypatch, capsys, None)
    assert code == 0 and out["errors"] == [] and out["gajjala_gg_like"]["error"].startswith("record: ")


# ── words ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_no_b_word_and_no_other_methods_name_in_the_new_module():
    src = (Path(GLT.__file__)).read_text(encoding="utf-8")
    assert not re.search("b" + "ounc", src, re.I) and not re.search("s" + "epa", src, re.I)


# ── the Watch surface this module names (HIS CALL: the hook pin) ─────────────────────────────────────────────────
def test_NEGATIVE_gg_like_track_names_the_watch_only_for_the_pct_cut_and_the_runseat_engine():
    # tests/test_gajjala_watch_hook_2026_11_15.py::test_only_gajjala_run_py_names_the_watch reads "nothing else may
    # join (owner's note)". gg_like_track.py names the Watch because the spec's one-engine rule needs runseat's
    # from_trigger + split guard and C.RUNNERS_SEAT_APLUS_PCT. That pin is NOT widened here (his call). This guard
    # fixes the surface so a widening is exactly these reads — never the Watch's switch, loop, build, store, payload,
    # cross engine or colls.
    import ast
    src = Path(GLT.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods = sorted({f"{n.module}.{a.name}" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                   and (n.module or "").startswith("chart_maps.gajjala_watch") for a in n.names}
                  | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
                     if a.name.startswith("chart_maps.gajjala_watch")})
    assert mods == ["chart_maps.gajjala_watch.constants", "chart_maps.gajjala_watch.runseat"]

    def reads(alias):
        return sorted({n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
                       and isinstance(n.value, ast.Name) and n.value.id == alias})
    assert reads("WC") == ["RUNNERS_SEAT_APLUS_PCT"]
    assert reads("RS") == ["FROM_TRIGGER_KEYS", "_default_cached_at", "fetched_on", "from_trigger", "measure_end",
                           "play_day", "split_look"]
    for name in ("RS", "WC"):
        assert all(getattr(RS if name == "RS" else WC, a, None) is not None for a in reads(name)), name
    for banned in ("gajjala_watch import colls", "gajjala_watch import loop", "gajjala_watch import build",
                   "gajjala_watch import payload", "gajjala_watch import store", "gajjala_watch import tags",
                   "gajjala_watch import runtrack", "gajjala_watch.cross_alerts", "gajjala_watch import cross_alerts",
                   "_popen", "spawn_child", "spawn_loop", "WCO."):
        assert banned not in src, banned


def test_NEGATIVE_the_watch_imports_of_gg_like_track_stay_inside_functions():
    # A module-level import would load the Watch package on every `import gg_like_track` (the ledger's serve path).
    import ast
    tree = ast.parse(Path(GLT.__file__).read_text(encoding="utf-8"))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not any("gajjala_watch" in ((getattr(n, "module", None) or "") + " ".join(a.name for a in n.names))
                   for n in top)
